#!/usr/bin/env python3
"""Regression gate for assign_words.py.

Named cases are ink-level facts verified by eye on the page; the aggregate
metrics catch drift the named cases would miss. SCORE is the judge (lower is
better) and any FAILURE blocks a change.
Usage: python3 bench.py [path-to-candidate]
"""
import importlib.util, json, math, os, subprocess, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT + "/tools")
path = sys.argv[1] if len(sys.argv) > 1 else ROOT + "/tools/assign_words.py"
spec = importlib.util.spec_from_file_location("assign_words", path)
aw = importlib.util.module_from_spec(spec)
sys.modules["assign_words"] = aw
spec.loader.exec_module(aw)

cap = {}
orig = aw.rewrite
def spy(page, assignment):
    cap["a"] = assignment
    return orig(page, assignment)
aw.rewrite = spy

def nbody(els):
    return len([e for e in els if e["kind"] == "body"])

def span(els):
    return max(e["x2"] for e in els) - min(e["x1"] for e in els)

CASES = {
    (453, (38, 1, 3)): ("dhi has 2 bodies", lambda e: nbody(e) == 2),
    (453, (38, 6, 12)): ("yuraad 3 bodies + 2 damma-family",
        lambda e: nbody(e) == 3 and sum(1 for x in e if x.get("mark") in
                                        ("damma", "dammatan") and not x.get("mkpart")) == 2),
    (454, (38, 23, 4)): ("lahu fatha+damma+small-waw",
        lambda e: {"fatha", "damma", "small-waw"} <= {x.get("mark") for x in e}),
    (133, (6, 47, 8)): ("aw 2 bodies with fatha",
        lambda e: nbody(e) == 2 and any(x.get("mark") == "fatha" for x in e)),
    (133, (6, 48, 10)): ("falaa 2 bodies", lambda e: nbody(e) == 2),
    (7, (2, 13, 8)): ("qaaluu 3 bodies", lambda e: nbody(e) == 3),
    (7, (2, 13, 9)): ("a-nu'minu keeps hamza-alef", lambda e: nbody(e) >= 3),
    (2, (2, 4, 7)): ("unzila p2 has its damma",
        lambda e: any(x.get("mark") == "damma" for x in e)),
    (3, (2, 12, 3)): ("hum p3 two dammas",
        lambda e: sum(1 for x in e if x.get("mark") == "damma") == 2),
    (3, (2, 13, 8)): ("qaaluu p3 span>=25", lambda e: span(e) >= 25),
    (3, (2, 14, 5)): ("qaaluu 2:14:5 span<=33", lambda e: span(e) <= 33),
    (3, (2, 14, 4)): ("aamanuu span>=25", lambda e: span(e) >= 25),
    (3, (2, 16, 3)): ("ishtarawu span>=38", lambda e: span(e) >= 38),
    (1, (1, 1, 1)): ("bismi p1 span>=18", lambda e: span(e) >= 18),
    (1, (1, 7, 5)): ("ghayri p1 span>=10", lambda e: span(e) >= 10),
    # the letter meem must stay letter ink, not the iqlab sign (p307 cascade)
    (307, (19, 33, 5)): ("wa-yawma 3 bodies", lambda e: nbody(e) == 3),
    (307, (19, 34, 3)): ("ibna 2 bodies", lambda e: nbody(e) == 2),
    # iqlab is ONE haraka + small م in this print (docs/defects/iqlab_notation.md):
    # the م must be a MARK, not a fourth letter piece
    (143, (6, 124, 26)): ("shadid iqlab: 2 bodies + meem mark",
        lambda e: nbody(e) == 2
        and any(x.get("mark") == "meem-iqlab" for x in e)),
    # 4 raw bodies is CORRECT here: the restored ك stroke is letter ink riding
    # over the wider ك, so the audit's effective piece count is 3
    (222, (11, 12, 2)): ("tarik iqlab: 4 bodies + meem mark",
        lambda e: nbody(e) == 4
        and any(x.get("mark") == "meem-iqlab" for x in e)),
    # the word-anchored signs stay seated: wasla rides ITS word's alef and the
    # suffix ۥ trails ITS word's ha, even in a tight-kerned ٱلْX ٱلْY pair or a
    # ـهُۥ chain (QSVG_RESEAT; the 27+26 frozen wasla/small-waw flags)
    (273, (16, 60, 11)): ("aziz keeps exactly 1 wasla",
        lambda e: sum(1 for x in e if x.get("mark") == "wasla"
                      and not x.get("mkpart")) == 1),
    (273, (16, 60, 12)): ("hakim has its wasla",
        lambda e: any(x.get("mark") == "wasla" for x in e)),
    (205, (9, 114, 13)): ("lahu 9:114 has its small-waw",
        lambda e: any(x.get("mark") == "small-waw" for x in e)),
    (205, (9, 114, 15)): ("aduww holds no small-waw",
        lambda e: not any(x.get("mark") == "small-waw" for x in e)),
    # header ink is inviolable: the word above سورة البروج must hold nothing
    # from the title line below it (reported.json item 33)
    (590, (84, 25, 5)): ("salihat holds no title-line ink",
        lambda e: all(x.get("line") == 1 for x in e)),
}

def budget_mismatches(words):
    bad = 0
    for w, at in words:
        els = [e for a in at for e in a["els"]]
        c = w["uthmani"].count
        hv = sum(1 for e in els if e.get("mark") in
                 ("fatha", "kasra", "fathatan", "kasratan") and not e.get("mkpart"))
        wv = (c("َ") + c("ِ") + c("ً") + c("ٍ")
              + c("ࣰ") + c("ࣲ"))
        if hv != wv:
            bad += 1
            continue
        hv = sum(1 for e in els if e.get("mark") in ("damma", "dammatan")
                 and not e.get("mkpart"))
        wv = c("ُ") + c("ٌ") + c("ࣱ")
        if hv != wv:
            bad += 1
    return bad

q = json.load(open(ROOT + "/.cache/qcf_widths.json"))
case_fail, mism, nwords, tot, nw, badw, pixfail = [], 0, 0, 0.0, 0, 0, 0
for pg in (1, 2, 3, 7, 17, 133, 143, 200, 202, 205, 222, 273, 307, 453, 454, 590):
    try:
        _, svg, report, cov = aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    except Exception as e:
        print("PAGE %d CRASH: %s" % (pg, e))
        case_fail.append("crash-p%d" % pg)
        continue
    if cov[0] != cov[1]:
        case_fail.append("coverage-p%d %s" % (pg, cov))
    words = [(w, at) for w, at in cap["a"] if w]
    nwords += len(words)
    mism += budget_mismatches(words)
    for w, at in words:
        k = (pg, (w["surah"], w["ayah"], w["pos"]))
        if k in CASES:
            name, fn = CASES[k]
            els = [e for a in at for e in a["els"]]
            try:
                ok = fn(els)
            except Exception:
                ok = False
            print("%-4s %s" % ("PASS" if ok else "FAIL", name))
            if not ok:
                case_fail.append(name)
    rows = {}
    for word, atoms in words:
        els = [e for a in atoms for e in a["els"]]
        if els:
            rows.setdefault(els[0].get("line"), []).append((word, span(els)))
    for ln, sub in rows.items():
        tq = sum(q.get("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), 0) for w, _ in sub)
        ta = sum(wd for _, wd in sub)
        if not tq:
            continue
        for w, wd in sub:
            qw = q.get("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]))
            if not qw:
                continue
            r = wd / (qw / tq * ta)
            tot += abs(math.log(max(r, 1e-3)))
            nw += 1
            if r < 0.55 or r > 1.8:
                badw += 1
    if pg in (3, 17, 453):  # 17: the displaced/duplicated قلى pair (cross-frame emission)
        from PIL import Image, ImageChops
        open(S + "/bpx.svg", "w").write(svg)
        subprocess.run(["rsvg-convert", "-w", "900", "-b", "white",
                        ROOT + "/mushafs/hafs/kfqc/svg/%03d.svg" % pg,
                        "-o", S + "/bpx_a.png"], check=True)
        subprocess.run(["rsvg-convert", "-w", "900", "-b", "white",
                        S + "/bpx.svg", "-o", S + "/bpx_b.png"], check=True)
        a = Image.open(S + "/bpx_a.png").convert("L")
        b = Image.open(S + "/bpx_b.png").convert("L")
        if sum(ImageChops.difference(a, b).histogram()[100:]):
            pixfail += 1
            case_fail.append("pixel-p%d" % pg)

score = len(case_fail) * 100 + mism * 3 + badw * 5 + int(1000 * tot / max(1, nw))
print("budget-mismatch words: %d/%d | width bad %d/%d mean %.4f | pixelfail %d"
      % (mism, nwords, badw, nw, tot / max(1, nw), pixfail))
print("FAILURES:", case_fail if case_fail else "none")
print("SCORE:", score)
