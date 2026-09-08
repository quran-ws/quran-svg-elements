"""Which published Quran text was this mushaf set from?

Judged against MushafDatabase's own labelling of the same artwork — an independent
decomposition, so neither our pipeline nor our text choice is on trial here. For each
word the marks the reference says are DRAWN are compared with the marks each candidate
text SPELLS, family by family. The source that agrees most often is the one the print
follows.

Code points are normalised first: the same mark is written differently by different
conventions (KFGQPC writes sukun U+06E1 and the silent circle U+0652, quran.com's
rasm_uthmani writes them U+0652 and U+06DF), so a raw comparison measures encoding, not
content.
"""
import sys, os, io, json, gzip, glob, re
from collections import Counter, defaultdict
ROOT = os.environ["QSVG_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "tools"))
import refdb                                                        # noqa: E402

SP = os.path.dirname(os.path.abspath(__file__))
REFDIR = sys.argv[1]

# ---- the reference's label vocabulary, folded to families -------------------
# The iqlab variants fold into their tanwin: this art fuses the iqlab meem into the
# tanwin glyph, and quran.com's rasm_uthmani writes one U+064B for the pair. Folding is what
# makes the two comparable — 734 + 2901 + 106 is exactly the 3741 U+064B it writes.
REF_FAM = {
    "fathah": "fathah", "kasrah": "kasrah", "dammah": "dammah",
    "sukun": "sukun", "shaddah": "shaddah",
    "hamzah": "hamzah", "hamzat_al_wasl": "hamzat_al_wasl",
    "superscript alef": "omitted_alif", "maddah": "maddah",
    "rounded zero": "small_circle", "rectangular zero": "rect-zero",
    "tanwin_al_fath": "tanwin_al_fath", "successive tanwin_al_fath": "tanwin_al_fath", "fathah iqlab": "tanwin_al_fath",
    "tanwin_al_kasr": "tanwin_al_kasr", "successive tanwin_al_kasr": "tanwin_al_kasr", "kasrah iqlab": "tanwin_al_kasr",
    "tanwin_al_damm": "tanwin_al_damm", "successive tanwin_al_damm": "tanwin_al_damm", "dammah iqlab": "tanwin_al_damm",
    "small waw": "small_waw", "small yeh": "small_yaa",
    "small meem": "meem", "small seen": "small-seen", "small noon": "small_noon",
    "vowel sign": None,
}
WAQF_CP = set(range(0x06D6, 0x06DD)) | {0x06E9}

# ---- code point -> family, per convention ----------------------------------
BASE = {
    0x064E: "fathah", 0x0650: "kasrah", 0x064F: "dammah",
    0x064B: "tanwin_al_fath", 0x064D: "tanwin_al_kasr", 0x064C: "tanwin_al_damm",
    0x08F0: "tanwin_al_fath", 0x08F2: "tanwin_al_kasr", 0x08F1: "tanwin_al_damm",
    0x0651: "shaddah", 0x0653: "maddah", 0x06E4: "maddah",
    0x0670: "omitted_alif", 0x06E0: "rect-zero",
    0x06E5: "small_waw", 0x06E6: "small_yaa", 0x06E7: "small_yaa",
    0x06E2: "meem", 0x06ED: "meem", 0x06E8: "small_noon",
    0x06DC: "small-seen", 0x06E3: "small-seen",
    0x0654: "hamzah", 0x0655: "hamzah",
}
# KFGQPC writes the open tanwin with these; quran.com's rasm_uthmani has no separate
# code point for them and writes the plain tanwin instead.
QPC_EXTRA = {0x06E1: "sukun", 0x0652: "small_circle",
             0x0657: "tanwin_al_fath", 0x0656: "tanwin_al_kasr", 0x065E: "tanwin_al_damm"}
UTH_EXTRA = {0x0652: "sukun", 0x06DF: "small_circle",
             0x0657: "tanwin_al_damm", 0x0656: "tanwin_al_kasr", 0x065E: "tanwin_al_fath"}
# The reference takes a hamzah SEAT apart: `أ` is a text alef plus a `hamzah` diacritic,
# and the same for إ ؤ ئ — 16,385 hamzah diacritics against 773 combining U+0654 in the
# text, so the seats must be counted. A bare `ء` is not a seat; it is its own letter and
# the reference labels it `text`. Counting it as well charged 2,715 false disagreements
# (`سَوَآءٌ` was said to spell a hamzah the page does not draw); counting no letters at
# all charged 15,198.
HAMZAH_LETTERS = set("أإؤئ")
HAMZAT_AL_WASL_LETTERS = {0x0671}

# families the ink and the text can actually be compared on. `meem` is out: this art
# fuses the iqlab meem into the tanwin glyph, so the reference draws 270 where the
# rasm_uthmani text spells 7,252.
FAMS = ("fathah", "kasrah", "dammah", "tanwin_al_fath", "tanwin_al_kasr", "tanwin_al_damm",
        "shaddah", "sukun", "small_circle", "rect-zero", "maddah",
        "omitted_alif", "small_waw", "small_yaa", "hamzah", "hamzat_al_wasl")


def text_counts(t):
    """Per-family counts for one word of text, under whichever convention it uses."""
    style = QPC_EXTRA if "ۡ" in t else UTH_EXTRA
    c = Counter()
    for ch in t:
        o = ord(ch)
        fam = BASE.get(o) or style.get(o)
        if fam:
            c[fam] += 1
        elif ch in HAMZAH_LETTERS:
            c["hamzah"] += 1
        elif o in HAMZAT_AL_WASL_LETTERS:
            c["hamzat_al_wasl"] += 1
        elif o in WAQF_CP:
            c["waqf"] += 1
    return c


def ref_counts(rec):
    c = Counter()
    for kind, label, _b in rec["pieces"]:
        if kind == "diacritic":
            fam = REF_FAM.get(label)
            if fam:
                c[fam] += 1
        elif kind == "waqf":
            c["waqf"] += 1
    return c


def qc_page(pg):
    p = os.path.join(SP, "texts", "qc", "%03d.json" % pg)
    if not os.path.exists(p):
        return {}
    d = json.load(io.open(p, encoding="utf-8"))
    out = {}
    for v in d.get("verses", []):
        s, a = (int(x) for x in v["verse_key"].split(":"))
        i = 0
        for w in v.get("words", []):
            if w.get("char_type_name") != "word":
                continue
            i += 1
            out[(s, a, i)] = w
    return out


def qp_words():
    """quranpedia mushaf-2: ayah text, split on whitespace into words."""
    f = os.path.join(SP, "texts", "quranpedia-mushafs-2.json.gz")
    d = json.load(gzip.open(f, "rt", encoding="utf-8"))["data"]
    out = {}
    for su in d["surahs"]:
        for ay in su["ayahs"]:
            s, a = int(ay["surah"]), int(ay["number"])
            for i, tok in enumerate(ay["text"].split(), 1):
                out[(s, a, i)] = tok
    return out


FIELDS = ["text_uthmani", "text_qpc_hafs", "text_imlaei", "text_indopak",
          "text_uthmani_simple", "text_imlaei_simple"]


def dk_words():
    import sqlite3
    db = sqlite3.connect(os.path.join(ROOT, ".cache", "digitalkhatt",
                                      "digital-khatt-v2.db"))
    out = {}
    for loc, txt in db.execute("SELECT location, text FROM words"):
        if loc.count(":") == 2 and not txt.startswith("\u06dd"):
            out[loc] = txt
    return out


def qpc_cache():
    out = {}
    import glob
    for f in glob.glob(os.path.join(ROOT, ".cache", "words-qpc", "page-*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for v in d.get("verses", []):
            i = 0
            for w in v.get("words", []):
                if w.get("char_type_name") != "word":
                    continue
                i += 1
                t = w.get("qpc_uthmani_hafs") or w.get("text") or ""
                if t:
                    out["%s:%d" % (v["verse_key"], i)] = t
    return out


_dump = {}


def main():
    QPC = qpc_cache()
    try:
        QP = qp_words()
    except Exception:
        QP = {}
    DK = dk_words()
    tally = defaultdict(Counter)
    famtal = defaultdict(Counter)
    examples = defaultdict(list)
    scored = pages = 0
    for pg in range(1, 605):
        rp = os.path.join(REFDIR, "%03d.svg" % pg)
        if not os.path.exists(rp):
            continue
        try:
            ref = refdb.fold(refdb.read_page(rp))
        except Exception:
            continue
        qc = qc_page(pg)
        if not qc:
            continue
        pages += 1
        for key, rec in ref.items():
            w = qc.get(key)
            if not w:
                continue
            # only where the two agree on which letters the word HAS, so a different
            # word split never counts as a text disagreement
            if refdb.skeleton(rec["hafs"]) != refdb.skeleton(w.get("text_uthmani") or ""):
                continue
            scored += 1
            rc = ref_counts(rec)
            cand = {f: (w.get(f) or "") for f in FIELDS}
            cand["quranpedia_m2"] = QP.get(key, "")
            cand["text_qpc_hafs"] = QPC.get("%d:%d:%d" % key, "")
            _dkk = "%d:%d:%d" % key
            if (key[0], key[1]) in ((2, 181), (8, 6), (13, 37)):
                _dkk = None            # split ayahs: indexing shifts, skip
            cand["digitalkhatt (print)"] = DK.get(_dkk, "") if _dkk else ""
            # What this pipeline actually uses: rasm_uthmani for every mark, the KFGQPC text
            # for the waqf signs alone. Each is the best available source for its own
            # part, and neither is best for both.
            cand["rasm_uthmani + kfgqpc waqf"] = (
                "".join(c for c in (w.get("text_uthmani") or "") if ord(c) not in WAQF_CP)
                + "".join(c for c in QPC.get("%d:%d:%d" % key, "") if ord(c) in WAQF_CP))
            cand["mushafdatabase_own"] = rec["hafs"]
            for name, t in cand.items():
                if not t:
                    tally[name]["no text"] += 1
                    continue
                tc = text_counts(t)
                ok = True
                for fam in FAMS + ("waqf",):
                    if tc.get(fam, 0) != rc.get(fam, 0):
                        ok = False
                        famtal[name][fam] += 1
                        if os.environ.get("QSVG_TXDUMP"):
                            _dump.setdefault(name, []).append(
                                {"key": "%d:%d:%d" % key, "fam": fam,
                                 "ref": rec["hafs"], "cand": t,
                                 "spells": tc.get(fam, 0),
                                 "drawn": rc.get(fam, 0)})
                        if len(examples[(name, fam)]) < 40:
                            examples[(name, fam)].append(
                                (pg, "%d:%d:%d" % key, rec["hafs"], t,
                                 tc.get(fam, 0), rc.get(fam, 0)))
                tally[name]["exact" if ok else "differs"] += 1
    print("pages %d | words scored %d\n" % (pages, scored))
    print("%-22s %10s %10s %9s" % ("source", "exact", "differs", "rate"))
    order = sorted(tally, key=lambda n: -tally[n]["exact"])
    for name in order:
        t = tally[name]
        n = t["exact"] + t["differs"]
        print("%-22s %10d %10d %8.3f%%"
              % (name, t["exact"], t["differs"], 100.0 * t["exact"] / max(1, n)))
    print("\nwhere each source goes wrong (words, by family):")
    if os.environ.get("QSVG_TXDUMP"):
        json.dump(_dump, open(os.environ["QSVG_TXDUMP"], "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    hdr = [f for f in FAMS + ("waqf",) if any(famtal[n][f] for n in order)]
    print("%-22s %s" % ("source", " ".join("%9s" % f[:9] for f in hdr)))
    for name in order:
        print("%-22s %s" % (name, " ".join("%9d" % famtal[name][f] for f in hdr)))
    best = order[0]
    print("\n%s — its remaining disagreements:" % best)
    for fam in hdr:
        for pg, k, h, t, got, want in examples[(best, fam)][:2]:
            print("   %-12s p%-4d %-11s ref-text %-18s cand %-18s spells %d, drawn %d"
                  % (fam, pg, k, h.strip()[:18], t.strip()[:18], got, want))
    if len(sys.argv) > 2:
        json.dump({n: dict(tally[n]) for n in tally}, open(sys.argv[2], "w"), indent=1)


main()
