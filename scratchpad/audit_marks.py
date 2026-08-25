#!/usr/bin/env python3
"""Per-word audit against the text: every mark family, letter dots, ligature
count from Arabic joining rules, and right-to-left order within a line.

Usage: python3 audit_marks.py [first] [last] [--jobs N]
Writes marks_pages/NNN.json per page (resumable) and marks_report.txt.
"""
import io, contextlib, json, os, sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/abdullah/Documents/Github/quran-svg/tools")
PIPE = os.environ.get("QSVG_PIPE",
    "/Users/abdullah/Documents/Github/quran-svg/tools/assign_words.py")
ROOT = "/Users/abdullah/Documents/Github/quran-svg"
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
    "small-ya": ("ۦ", "ۧ"), "small-circle": ("۟", "۠"),
    "hamza": ("أ", "إ", "ؤ", "ئ", "ٔ", "ٕ"),
    "pause": ("ۖ", "ۗ", "ۘ", "ۙ", "ۚ", "ۛ", "ۜ",
              "۬", "۪", "۫", "ۣ"),
    "small-noon": ("ۨ",),
}
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
        if ch == "ي" and i == len(sk) - 1:
            continue                  # a final ya is drawn undotted here
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
            if bx2 > ax2 + 1.0:       # the next word sits right of this one
                rows.append(("%d:%d:%d" % (a["surah"], a["ayah"], a["pos"]),
                             a["uthmani"], [("rtl-order", int(ax2), int(bx2))]))
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        txt = w["uthmani"]
        have, dots = Counter(), 0
        for e in els:
            if e.get("mkpart"):
                continue              # a welded twin counts through its master
            for part in (e.get("mark") or "").split("+"):
                if part in _DOTU:
                    dots += _DOTU[part]
                elif part:
                    have[part] += 1
        bad = []
        for fam, chars in TEXT_WANT.items():
            want = sum(txt.count(c) for c in chars)
            if want != have.get(fam, 0):
                bad.append((fam, have.get(fam, 0), want))
        dw = dot_want(txt, aw)
        if dots != dw:
            bad.append(("dots", dots, dw))
        bods = [e for e in els if e["kind"] == "body"]
        eff = []
        for b in bods:      # a stroke drawn over a wider sibling is not a piece
            wb = b["x2"] - b["x1"]
            if not any(o is not b
                       and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"]) >= 0.6 * wb
                       and (o["x2"] - o["x1"]) > wb for o in bods):
                eff.append(b)
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
