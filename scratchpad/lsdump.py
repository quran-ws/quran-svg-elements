#!/usr/bin/env python3
"""Dump per-line word/mark state for one page: each word's marks with the
x-gap to its own body ink and the vertical distance outside its line band —
the two violation tests the line-set solver triggers on.

Usage: python3 scratchpad/lsdump.py <page> [line ...]
"""
import io, contextlib, json, os, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")
PIPE = os.environ.get("QSVG_PIPE", ROOT + "/tools/assign_words.py")


def _load():
    import importlib.util
    if "assign_words" in sys.modules:
        return sys.modules["assign_words"]
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    m = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = m
    spec.loader.exec_module(m)
    return m


def main():
    pg = int(sys.argv[1])
    only = {int(x) for x in sys.argv[2:]} or None
    aw = _load()
    cap = {}
    orig = aw.rewrite

    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")

    recs = []
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        b = [e for e in els if e["kind"] == "body"]
        if not b:
            print("BODYLESS %d:%d:%d %s" % (w["surah"], w["ayah"], w["pos"], w["rasm_uthmani"]))
            continue
        ls = [e.get("line") for e in b if e.get("line")]
        recs.append({"w": w, "els": els, "b": b,
                     "ln": max(set(ls), key=ls.count) if ls else 0})
    band = {}
    for r in recs:
        lo, hi = band.get(r["ln"], (1e9, -1e9))
        band[r["ln"]] = (min(lo, min(b["y1"] for b in r["b"])),
                         max(hi, max(b["y2"] for b in r["b"])))

    def ovl(bs, e):
        return max((min(b["x2"], e["x2"]) - max(b["x1"], e["x1"])) for b in bs)

    for r in sorted(recs, key=lambda r: (r["ln"], -max(b["x2"] for b in r["b"]))):
        if only and r["ln"] not in only:
            continue
        w = r["w"]
        bx1 = min(b["x1"] for b in r["b"]); bx2 = max(b["x2"] for b in r["b"])
        print("L%d %d:%d:%d %s  body x %.1f-%.1f" % (
            r["ln"], w["surah"], w["ayah"], w["pos"], w["rasm_uthmani"], bx1, bx2))
        lo, hi = band[r["ln"]]
        for e in r["els"]:
            if e["kind"] == "body" or e.get("mkpart"):
                continue
            cy = (e["y1"] + e["y2"]) / 2
            gap = -ovl(r["b"], e)
            out = max(lo - cy, cy - hi, 0.0)
            flag = ""
            if gap > 0:
                flag += " XGAP"
            if out >= 15:
                flag += " OUTBAND"
            elif out > 0:
                flag += " out%.1f" % out
            print("   %-12s x %6.1f-%6.1f y %6.1f-%6.1f ln=%s%s%s" % (
                e.get("mark"), e["x1"], e["x2"], e["y1"], e["y2"],
                e.get("line"), (" standalone" if e.get("standalone") else ""), flag))


if __name__ == "__main__":
    main()
