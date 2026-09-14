#!/usr/bin/env python3
"""Per-word audit against the text: every mark family, letter dots, ligature
count from Arabic joining rules, and right-to-left order within a line.

Every mark family, letter dots, ligature count from the Arabic joining rules,
and right-to-left order within a line, checked per WORD against the text this
print was set from. A word may hold the right NUMBER of marks and still be
wrong, so this is one gate among several — but it is the one that names the
family, and the one that caught p540's split open tanwin.

Usage: python3 tools/audit_marks.py [first] [last] [--jobs N]
       QSVG_WORDDUMP=DIR  also dump EVERY word's expected-vs-detected counts
Writes .cache/marks_pages/NNN.json per page (resumable) and marks_report.txt.
Exits non-zero when any word is flagged, so it can gate a merge.
"""
import io, contextlib, json, os, sys
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")
PIPE = os.environ.get("QSVG_PIPE", ROOT + "/tools/assign_words.py")
# Resumable per-page flag files. They are derived output, never committed, so
# they live in .cache with every other build product — this tool used to sit in
# scratchpad/ and write beside itself, which put derived JSON in the source
# tree. QSVG_MARKSOUT relocates them for an A/B run.
OUT = os.environ.get("QSVG_MARKSOUT") or os.path.join(ROOT, ".cache", "marks_pages")
# QSVG_WORDDUMP=DIR: write EVERY word's expected-vs-detected family counts to
# DIR/NNN.json, not just the words that disagree. The flag files answer "is
# anything wrong"; this answers "what does each word expect, and what did the
# ink give it" — the question you cannot ask of a report that only lists
# failures. p540's split tanwin is the case that made it necessary: the flag
# file for that page is `[]`.
WORDDUMP_DIR = os.environ.get("QSVG_WORDDUMP")
WORDDUMP = None

_DOTU = {"dot": 1, "two_dots": 2, "three_dots": 3}

# pages whose ayah-polygon data is known broken and is being repaired upstream
POLY_SUSPECT = {294, 305, 431, 551, 602, 604}

TEXT_WANT = {
    "fathah": ("َ",), "kasrah": ("ِ",), "dammah": ("ُ",),
    "tanwin_al_fath": ("ً", "ࣰ"), "tanwin_al_kasr": ("ٍ", "ࣲ"), "tanwin_al_damm": ("ٌ", "ࣱ"),
    "sukun": ("ْ", "ۡ"), "shaddah": ("ّ",), "maddah": ("ٓ", "ۤ"),
    "omitted_alif": ("ٰ",), "hamzat_al_wasl": ("ٱ",), "small_waw": ("ۥ",),
    "small_yaa": ("ۦ", "ۧ"),
    # taxonomy phase 1: the two zeros are different signs with different rules
    # (U+06DF round, U+06E0 upright); no word carries both, so the text splits
    # the family exactly (3988 + 66 sites, measured mushaf-wide)
    "rounded_zero": ("۟",), "rectangular_zero": ("۠",),
    "hamzah": ("أ", "إ", "ؤ", "ئ", "ٔ", "ٕ"),
    # ۜ (U+06DC) left this bucket: it is a saktah at five sites and a reading
    # sign at two, named BY JOB from the place table below. ۣ (U+06E3, 52:37)
    # stays: phase 1 did not rename the seen-below/imalah/ishmam/tashil dots.
    "waqf": ("ۖ", "ۗ", "ۘ", "ۙ", "ۚ"),
    "waqf_al_muanaqah": ("ۛ",),
    "small_noon": ("ۨ",),
    "small_meem": ("ۢ", "ۭ"),
    "saktah": ("ۜ",), "seen_al_qiraah": ("ۜ", "ۣ"),
    # phase-3 rare dots (Abdullah 2026-08-28): each is ONE site mushaf-wide
    "imalah": ("۪",), "ishmam": ("۬", "۫"), "tashil": ("۬",),
}
# The U+06DC sites by JOB (mirrors .cache/marks/rare_places.json, which the
# pipeline's naming pass reads): the same character is a saktah on one page and
# a seen-for-saad on another, so the budget is place-gated — a site demands its
# OWN job's family and zero of the other.
RARE_SITES = {(18, 1): "saktah", (36, 52): "saktah", (75, 27): "saktah",
              (83, 14): "saktah", (69, 28): "saktah",
              (2, 245): "seen_al_qiraah", (7, 69): "seen_al_qiraah",
              # U+06E3 seen-below, one site
              (52, 37): "seen_al_qiraah",
              # U+06EC serves TWO jobs, split by site exactly like U+06DC:
              # 12:11 تَأْمَ۬نَّا is the ishmam, 41:44 ءَا۬عْجَمِى the tashil
              (12, 11): "ishmam", (41, 44): "tashil",
              (11, 41): "imalah"}
# legacy input names (an older build under QSVG_PIPE) fold into the new family
# the word's own text selects
_LEGACY_ZERO = "small_circle"
# The iqlab meem WAS excluded here on the grounds that it is "fused into the
# tanwin glyph in this art". That is true of the LOW form (U+06ED ۭ, often
# fused) but NOT of the HIGH form (U+06E2 ۢ), which CLAUDE.md itself records as
# "a separate glyph". The exclusion therefore left every iqlab site unguarded,
# and on 2026-08-29 p455 مُغْتَسَلُۢ was found holding NO meem at all — its
# sign was sitting in بَارِدࣱ as anonymous body ink, invisible to every audit.
# MushafDatabase caught the ownership; Abdullah's eye named the ink.
# Measured before adding it: 510 words carry the high form and 99 the low, and
# ALL 609 hold their mark today, so demanding it costs zero flags and buys a
# permanent gate. It is demanded as a FAMILY (either form) because the print
# and the reference text disagree about which form a site uses.


def dot_want(txt, aw):
    raw = aw._LETTER.findall(txt)
    # a hamzah seat (ئ ؤ أ إ) is drawn WITHOUT the dots of its base letter
    sk = [(aw.HAMZAH_MAP[c][0] if c in aw.HAMZAH_MAP else c, c in aw.HAMZAH_MAP)
          for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in aw.DOTS:
            continue
        if ch == "ي" and (i == len(sk) - 1
                          or (i + 1 < len(sk) and sk[i + 1][0] == "ء")):
            # A final ya is drawn undotted here, and so is a ya carrying a following
            # hamzah: شَيۡءٖ is drawn with three dots, not five. Ours and MushafDatabase's
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
    global WORDDUMP
    WORDDUMP = [] if WORDDUMP_DIR else None
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
    piece_led = []
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
            if (" " in a["rasm_uthmani"].strip() or " " in b["rasm_uthmani"].strip()):
                continue  # a letter-space compound straddles the break legitimately
            # trust DRAWN position over the line tag (p59 إليك/إلا: a stale
            # tag grouped a line-9 end with a line-10 start): words whose
            # y-bands do not overlap are on different drawn lines — reading
            # order across a line break is not an x question
            ay = [ (min(e["y1"] for a9 in at9 for e in a9["els"] if e["kind"]=="body"),
                    max(e["y2"] for a9 in at9 for e in a9["els"] if e["kind"]=="body"))
                   for w9, at9 in cap["a"] if w9 is a or w9 is b ]
            if len(ay) == 2 and (ay[0][1] < ay[1][0] - 2 or ay[1][1] < ay[0][0] - 2):
                continue
            if bx2 > ax2 + 1.0:       # the next word sits right of this one
                rows.append(("%d:%d:%d" % (a["surah"], a["ayah"], a["pos"]),
                             a["rasm_uthmani"], [("rtl-order", int(ax2), int(bx2))]))
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        txt = w["rasm_uthmani"]
        have, dots = Counter(), 0
        _zero_fam = ("rectangular_zero" if "۠" in txt else "rounded_zero")
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
        # from quran.com's rasm_uthmani. The two are different editions: they disagree about
        # the waqf sign at 424 of 4,416 positions — 87 of them where the text says قلى
        # and the page draws ج — and taking the expectation from the wrong edition
        # reported 181 of 202 `waqf` defects that were not defects at all. Every other
        # family still reads rasm_uthmani, whose spelling conventions the rest of this table
        # and segment_word() are built around.
        wtxt = w.get("qpc") or txt
        bad = []
        detail = {}          # family -> [detected, expected]  for EVERY word
        for fam, chars in TEXT_WANT.items():
            if fam == "waqf" and wtxt is not txt:
                # Where the two editions disagree about a waqf sign, neither one can be
                # quoted as the expectation, so the budget becomes a RANGE and the audit
                # says nothing. Measured over all 77,429 words the sources differ at only
                # 190 — 0.245% — and the drawn ink follows the KFGQPC text at 164 of them,
                # quran.com's rasm_uthmani at 9, and neither at 17. Those 9 are what a
                # single-source budget gets wrong: `بَعْدِى` (p20), `ٱلْخَيْرَٰتِ` (p64),
                # `كَذَٰلِكَ` (p303) and four more were each reported missing a صلى that
                # the page does not draw and that the other edition does not ask for.
                # Widening the budget costs nothing real — in the 164 the ink matches the
                # KFGQPC text, so it was already inside the range and already silent —
                # and it keeps the audit from convicting us of an editorial difference.
                lo, hi = sorted((sum(txt.count(c) for c in chars),
                                 sum(wtxt.count(c) for c in chars)))
                detail[fam] = [have.get(fam, 0), lo if lo == hi else [lo, hi]]
                if not (lo <= have.get(fam, 0) <= hi):
                    bad.append((fam, have.get(fam, 0), hi))
                continue
            src = wtxt if fam == "waqf" else txt
            want = sum(src.count(c) for c in chars)
            if fam in ("saktah", "seen_al_qiraah", "imalah", "ishmam",
                       "tashil") \
                    and RARE_SITES.get((w["surah"], w["ayah"])) != fam:
                want = 0              # this char here belongs to the OTHER job
            detail[fam] = [have.get(fam, 0), want]
            if want != have.get(fam, 0):
                bad.append((fam, have.get(fam, 0), want))
        dw = dot_want(txt, aw)
        detail["dots"] = [dots, dw]
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
        piece_led.append((w, len(eff), nseg))
        detail["pieces"] = [len(eff), nseg]
        if WORDDUMP is not None:
            WORDDUMP.append({
                "page": pg,
                "word_key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                "text": txt,
                # only families the word's text or its ink actually involves;
                # a word is not "missing" 19 marks it never spells
                "marks": {f: v for f, v in detail.items() if v[0] or v[1]},
                "mismatch": [b[0] for b in bad],
            })
        if bad:
            rows.append(("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), txt, bad))
    # BODY CHAIN SIGNATURE (Abdullah 2026-08-29, the 56:18 lesson): a piece
    # DEFICIT alone is usually the art joining letters — but a deficit word
    # within three positions of a SURPLUS word is a theft pair, the body
    # layer's version of the count-perfect chain. Flag both.
    for i1, (w1, e1, n1) in enumerate(piece_led):
        if e1 >= n1:
            continue
        for w2, e2, n2 in piece_led:
            if e2 <= n2 or w2 is w1:
                continue
            if w1["surah"] == w2["surah"] \
                    and abs((w1["ayah"] * 1000 + w1["pos"])
                            - (w2["ayah"] * 1000 + w2["pos"])) <= 3:
                rows.append(("%d:%d:%d" % (w1["surah"], w1["ayah"],
                                           w1["pos"]), w1["rasm_uthmani"],
                             [("pieces", e1, n1)]))
                break
    if WORDDUMP is not None:
        os.makedirs(WORDDUMP_DIR, exist_ok=True)
        with open(os.path.join(WORDDUMP_DIR, "%03d.json" % pg), "w",
                  encoding="utf-8") as fh:
            json.dump(WORDDUMP, fh, ensure_ascii=False)
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
        for word_key, txt, bad in rows:
            total += 1
            per[pg] += 1
            for k, got, want in bad:
                fam[k] += 1
                key = "%s %d/%d" % (k, got, want)
                pat[key] += 1
                if len(ex[key]) < 6:
                    ex[key].append("p%d %s %s" % (pg, word_key, txt))
    with open(os.path.join(OUT, "marks_report.txt"), "w") as fh:
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
    for pg, n in sorted(per.items()):
        for word_key, txt, bad in json.load(
                open(os.path.join(OUT, "%03d.json" % pg))):
            print("  p%d %s %s: %s" % (pg, word_key, txt, ", ".join(
                "%s detected %s, expected %s" % (k, g, w) for k, g, w in bad)))
    return total


if __name__ == "__main__":
    argv = sys.argv[1:]
    jobs, args = 2, []
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--jobs":                 # `--jobs 8`, the form every other
            jobs = int(argv[i + 1])       # tool here takes. It used to fall
            i += 2                        # through to the default of 2 and
            continue                      # eat the 8 as a page number.
        if x.startswith("--jobs="):
            jobs = int(x.split("=", 1)[1])
        elif not x.startswith("--"):
            args.append(x)
        i += 1
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
    flagged = report(a, b)
    # Non-zero on any flagged word: this runs as a merge gate, and a gate that
    # always exits 0 is a gate that does no work.
    sys.exit(1 if flagged else 0)
