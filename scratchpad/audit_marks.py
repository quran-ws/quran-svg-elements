#!/usr/bin/env python3
"""Per-word audit against the text: every mark family, letter dots, ligature
count from Arabic joining rules, and right-to-left order within a line.

Usage: python3 audit_marks.py [first] [last] [--jobs N]
Writes marks_pages/NNN.json per page (resumable) and marks_report.txt.
"""
import io, contextlib, json, os, sys
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")
PIPE = os.environ.get("QSVG_PIPE", ROOT + "/tools/assign_words.py")
S = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(S, "marks_pages")

_DOTU = {"dot": 1, "two-dots": 2, "three-dots": 3}

# pages whose ayah-polygon data is known broken and is being repaired upstream
POLY_SUSPECT = {294, 305, 431, 551, 602, 604}

TEXT_WANT = {
    "fatha": ("َ",), "kasra": ("ِ",), "damma": ("ُ",),
    "fathatan": ("ً", "ࣰ"), "kasratan": ("ٍ", "ࣲ"), "dammatan": ("ٌ", "ࣱ"),
    "sukun": ("ْ", "ۡ"), "shadda": ("ّ",), "maddah": ("ٓ", "ۤ"),
    "small-alef": ("ٰ",), "wasla": ("ٱ",), "small-waw": ("ۥ",),
    "small-ya": ("ۦ", "ۧ"),
    # taxonomy phase 1: the two zeros are different signs with different rules
    # (U+06DF round, U+06E0 upright); no word carries both, so the text splits
    # the family exactly (3988 + 66 sites, measured mushaf-wide)
    "sifr-mustadir": ("۟",), "sifr-mustatil": ("۠",),
    "hamza": ("أ", "إ", "ؤ", "ئ", "ٔ", "ٕ"),
    # ۜ (U+06DC) left this bucket: it is a saktah at five sites and a reading
    # sign at two, named BY JOB from the place table below. ۣ (U+06E3, 52:37)
    # stays: phase 1 did not rename the seen-below/imalah/ishmam/tashil dots.
    "pause": ("ۖ", "ۗ", "ۘ", "ۙ", "ۚ"),
    "muanaqah": ("ۛ",),
    "small-noon": ("ۨ",),
    "saktah": ("ۜ",), "seen-reading": ("ۜ", "ۣ"),
    # phase-3 rare dots (Abdullah 2026-08-28): each is ONE site mushaf-wide
    "imalah": ("۪",), "ishmam": ("۬", "۫"), "tashil": ("۬",),
}
# The U+06DC sites by JOB (mirrors .cache/marks/rare_places.json, which the
# pipeline's naming pass reads): the same character is a saktah on one page and
# a seen-for-sad on another, so the budget is place-gated — a site demands its
# OWN job's family and zero of the other.
RARE_SITES = {(18, 1): "saktah", (36, 52): "saktah", (75, 27): "saktah",
              (83, 14): "saktah", (69, 28): "saktah",
              (2, 245): "seen-reading", (7, 69): "seen-reading",
              # U+06E3 seen-below, one site
              (52, 37): "seen-reading",
              # U+06EC serves TWO jobs, split by site exactly like U+06DC:
              # 12:11 تَأْمَ۬نَّا is the ishmam, 41:44 ءَا۬عْجَمِى the tashil
              (12, 11): "ishmam", (41, 44): "tashil",
              (11, 41): "imalah"}
# legacy input names (an older build under QSVG_PIPE) fold into the new family
# the word's own text selects
_LEGACY_ZERO = "small-circle"
# the iqlab meem is fused into the tanween glyph in this art (measured), so it
# is not demanded as a separate mark


def dot_want(txt, aw):
    raw = aw._LETTER.findall(txt)
    # a hamza seat (ئ ؤ أ إ) is drawn WITHOUT the dots of its base letter
    sk = [(aw.HAMZA_MAP[c][0] if c in aw.HAMZA_MAP else c, c in aw.HAMZA_MAP)
          for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in aw.DOTS:
            continue
        if ch == "ي" and (i == len(sk) - 1
                          or (i + 1 < len(sk) and sk[i + 1][0] == "ء")):
            # A final ya is drawn undotted here, and so is a ya carrying a following
            # hamza: شَيۡءٖ is drawn with three dots, not five. Ours and MushafDatabase's
            # decompositions independently agree on three, against a budget counting the
            # ya's two — and every one of the 21 words where the two decompositions
            # agreed and the budget did not was شيء or بشيء.
            continue
        n += _DOTU.get(aw.DOTS[ch][0], 0)
    return n


def _load():
    import importlib.util
    if "assign_words" in sys.modules:
        return sys.modules["assign_words"]
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    m = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = m
    spec.loader.exec_module(m)
    return m


def scan(pg):
    aw = _load()
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    except Exception as e:
        return (pg, [("PAGE", "-", [("error", 0, 0)])])
    rows = []
    byline = {}
    for w, at in cap["a"]:
        if not w:
            continue
        bods = [e for a in at for e in a["els"] if e["kind"] == "body"]
        if not bods:
            continue
        ln = min((e.get("line") for e in bods if e.get("line")), default=None)
        byline.setdefault(ln, []).append((w, max(e["x2"] for e in bods)))
    for ln, ws in byline.items():
        if ln is None or len(ws) < 2:
            continue
        ws.sort(key=lambda t: (t[0]["surah"], t[0]["ayah"], t[0]["pos"]))
        for i in range(len(ws) - 1):
            a, ax2 = ws[i]
            b, bx2 = ws[i + 1]
            if (" " in a["uthmani"].strip() or " " in b["uthmani"].strip()):
                continue  # a letter-space compound straddles the break legitimately
            if bx2 > ax2 + 1.0:       # the next word sits right of this one
                rows.append(("%d:%d:%d" % (a["surah"], a["ayah"], a["pos"]),
                             a["uthmani"], [("rtl-order", int(ax2), int(bx2))]))
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        txt = w["uthmani"]
        have, dots = Counter(), 0
        _zero_fam = ("sifr-mustatil" if "۠" in txt else "sifr-mustadir")
        for e in els:
            if e.get("mkpart"):
                continue              # a welded twin counts through its master
            for part in (e.get("mark") or "").split("+"):
                if part == _LEGACY_ZERO:
                    part = _zero_fam  # old emitted name, accepted on input
                if part in _DOTU:
                    dots += _DOTU[part]
                elif part:
                    have[part] += 1
        # The waqf budget comes from the King Fahd Complex's own text of THIS print, not
        # from quran.com's uthmani. The two are different editions: they disagree about
        # the waqf sign at 424 of 4,416 positions — 87 of them where the text says قلى
        # and the page draws ج — and taking the expectation from the wrong edition
        # reported 181 of 202 `pause` defects that were not defects at all. Every other
        # family still reads uthmani, whose spelling conventions the rest of this table
        # and segment_word() are built around.
        wtxt = w.get("qpc") or txt
        bad = []
        for fam, chars in TEXT_WANT.items():
            if fam == "pause" and wtxt is not txt:
                # Where the two editions disagree about a waqf sign, neither one can be
                # quoted as the expectation, so the budget becomes a RANGE and the audit
                # says nothing. Measured over all 77,429 words the sources differ at only
                # 190 — 0.245% — and the drawn ink follows the KFGQPC text at 164 of them,
                # quran.com's uthmani at 9, and neither at 17. Those 9 are what a
                # single-source budget gets wrong: `بَعْدِى` (p20), `ٱلْخَيْرَٰتِ` (p64),
                # `كَذَٰلِكَ` (p303) and four more were each reported missing a صلى that
                # the page does not draw and that the other edition does not ask for.
                # Widening the budget costs nothing real — in the 164 the ink matches the
                # KFGQPC text, so it was already inside the range and already silent —
                # and it keeps the audit from convicting us of an editorial difference.
                lo, hi = sorted((sum(txt.count(c) for c in chars),
                                 sum(wtxt.count(c) for c in chars)))
                if not (lo <= have.get(fam, 0) <= hi):
                    bad.append((fam, have.get(fam, 0), hi))
                continue
            src = wtxt if fam == "pause" else txt
            want = sum(src.count(c) for c in chars)
            if fam in ("saktah", "seen-reading", "imalah", "ishmam",
                       "tashil") \
                    and RARE_SITES.get((w["surah"], w["ayah"])) != fam:
                want = 0              # this char here belongs to the OTHER job
            if want != have.get(fam, 0):
                bad.append((fam, have.get(fam, 0), want))
        dw = dot_want(txt, aw)
        if dots != dw:
            bad.append(("dots", dots, dw))
        bods = [e for e in els if e["kind"] == "body"]
        # Two counting rules, both about ink that is ONE piece drawn as two:
        #  - a stroke drawn over a wider sibling (the ك armature) is not a piece
        #  - pieces whose boxes OVERLAP end-to-end are one stroke thinned to a
        #    pen-lift (p203 صَـٰلِحًۭا, p219 نُنَجِّيكَ, p189 وَأَنفُسِهِمْ —
        #    all visually verified correct, overlaps 1.4-4.7u). Genuinely
        #    foreign pieces have POSITIVE gaps (p451 إِلْ يَاسِينَ: +1.0 to
        #    +3.3u) — the empty band between the two cases is the rule.
        parent = list(range(len(bods)))
        def _find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, b in enumerate(bods):
            wb = b["x2"] - b["x1"]
            for j, o in enumerate(bods):
                if o is b:
                    continue
                xov = min(o["x2"], b["x2"]) - max(o["x1"], b["x1"])
                yov = min(o["y2"], b["y2"]) - max(o["y1"], b["y1"])
                wider = (xov >= 0.6 * wb and (o["x2"] - o["x1"]) > wb)
                joint = (xov > 0.5 and yov > 3.0)
                if wider or joint:
                    parent[_find(i)] = _find(j)
        eff = {_find(i) for i in range(len(bods))}
        nseg = max(1, len(aw.segment_word(txt)))
        # a deficit is dominated by the art joining letters and goes to the
        # visual review sheet; a SURPLUS is unambiguous stolen ink
        if len(eff) > nseg:
            bad.append(("ligatures", len(eff), nseg))
        if bad:
            rows.append(("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), txt, bad))
    return (pg, rows)


def report(a, b):
    fam, pat, per, ex = Counter(), Counter(), Counter(), defaultdict(list)
    total, clean, pages = 0, 0, 0
    for pg in range(a, b + 1):
        f = os.path.join(OUT, "%03d.json" % pg)
        if not os.path.exists(f):
            continue
        pages += 1
        rows = json.load(open(f))
        if not rows:
            clean += 1
        for wid, txt, bad in rows:
            total += 1
            per[pg] += 1
            for k, got, want in bad:
                fam[k] += 1
                key = "%s %d/%d" % (k, got, want)
                pat[key] += 1
                if len(ex[key]) < 6:
                    ex[key].append("p%d %s %s" % (pg, wid, txt))
    with open(os.path.join(S, "marks_report.txt"), "w") as fh:
        fh.write("pages %d | fully clean %d | flagged words %d "
                 "(%d on polygon-suspect pages)\n\n"
                 % (pages, clean, total, sum(per[p] for p in POLY_SUSPECT)))
        fh.write("== by family ==\n")
        for k, n in fam.most_common():
            fh.write("%-14s %d\n" % (k, n))
        fh.write("\n== by pattern ==\n")
        for k, n in pat.most_common(40):
            fh.write("%-22s %5d   %s\n" % (k, n, "; ".join(ex[k][:3])))
        fh.write("\n== worst pages ==\n")
        for pg, n in per.most_common(25):
            fh.write("p%-4d %d\n" % (pg, n))
    print("pages %d | clean %d | flagged %d" % (pages, clean, total))
    print("families:", dict(fam.most_common(10)))


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    jobs = 2
    for x in sys.argv[1:]:
        if x.startswith("--jobs"):
            jobs = int(x.split("=")[1]) if "=" in x else 2
    a = int(args[0]) if args else 1
    b = int(args[1]) if len(args) > 1 else 604
    os.makedirs(OUT, exist_ok=True)
    todo = [pg for pg in range(a, b + 1)
            if not os.path.exists(os.path.join(OUT, "%03d.json" % pg))]
    if jobs <= 1:
        for pg in todo:
            pg, rows = scan(pg)
            json.dump(rows, open(os.path.join(OUT, "%03d.json" % pg), "w"),
                      ensure_ascii=False)
            print("ok %d (%d)" % (pg, len(rows)), flush=True)
    else:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for pg, rows in pool.imap_unordered(scan, todo):
                json.dump(rows, open(os.path.join(OUT, "%03d.json" % pg), "w"),
                          ensure_ascii=False)
                print("ok %d (%d)" % (pg, len(rows)), flush=True)
    report(a, b)
