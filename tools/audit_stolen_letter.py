#!/usr/bin/env python3
"""A word's ligature group holds no ink, and a NEIGHBOUR is drawing it.

`audit_ligatures` reports ~671 "empty" groups — a `<g class="ligature"
data-text="X">` that holds no body ink at all. Most are NOT defects: an empty
`ا` group in an ٱل- word usually means the CUT is wrong (alif-lam is drawn as
one connected run), and the letter's ink is simply in the word's own next
group. That is a segmentation question, not a theft.

The actionable subset is different and provable: the missing letter's ink is
inside ANOTHER WORD. Test, for each empty group:

  1. the word's OTHER groups leave a horizontal gap where the empty group's
     letter must be drawn (between the neighbouring groups' ink, or past the
     word's edge on the side the missing letter belongs to), and
  2. a different word on the SAME LINE holds body ink inside that gap.

Both signals are geometric and independent of any mark count — which is why
this reaches the family every count-based audit is blind to (a stolen body
piece keeps every mark count perfect: p71 غَالِبَ, p413 يَحْزُنكَ, p546 وَمَآ
were all found by eye for exactly that reason).

Reports the gap, the intruding word, and how much of the gap it covers.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assign_words as aw  # noqa: E402


def scan(pg):
    cap = {}
    _o = aw.rewrite

    def spy(p, a):
        cap["a"] = a
        return _o(p, a)
    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as exc:
        return pg, [], str(exc)
    finally:
        aw.rewrite = _o

    # every word's ink, per line, plus its groups
    words = []
    for w, at in cap.get("a", []):
        if not w:
            continue
        # Build the EMITTER's groups, not the atom list: a new
        # <g class="ligature"> opens only when atom["lig"] changes, and its
        # data-text comes from atom["seg"]. Pairing by atom index named the
        # wrong piece for 3.7% of words — the first version of this filter
        # inherited that bug and reported بِمَا as missing "بما".
        groups = []
        for ai, a in enumerate(at):
            lk = a.get("lig", ai)
            if groups and groups[-1]["lig"] == lk:
                groups[-1]["els"].extend(a["els"])
            else:
                groups.append({"lig": lk, "els": list(a["els"]),
                               "text": (a.get("seg") or {}).get("text", "")})
        for g in groups:
            bod = [e for e in g["els"] if e["kind"] == "body"]
            g["x1"] = min((b["x1"] for b in bod), default=None)
            g["x2"] = max((b["x2"] for b in bod), default=None)
            g["n"] = len(bod)
        allb = [e for a in at for e in a["els"] if e["kind"] == "body"]
        lines = [e.get("line") for a in at for e in a["els"] if e.get("line")]
        words.append({
            "key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
            "text": w["rasm_uthmani"], "groups": groups,
            "line": max(set(lines), key=lines.count) if lines else None,
            "x1": min((b["x1"] for b in allb), default=None),
            "x2": max((b["x2"] for b in allb), default=None),
            "bodies": [(b["x1"], b["x2"], b["y1"], b["y2"]) for b in allb],
        })

    out = []
    for wi, w in enumerate(words):
        filled = [g for g in w["groups"] if g["n"]]
        if not filled:
            continue                      # bodyless word: audit_bodyless owns it
        for gi, g in enumerate(w["groups"]):
            if g["n"]:
                continue
            # where must this letter be drawn? between the neighbouring
            # groups' ink, or past the word's edge if it is first/last.
            before = next((x for x in w["groups"][gi + 1:] if x["n"]), None)
            after = next((x for x in reversed(w["groups"][:gi]) if x["n"]),
                         None)
            # RTL: earlier groups are further RIGHT (higher x)
            if after and before:
                lo, hi = before["x2"], after["x1"]
            elif before:                  # missing letter is the word's first
                lo, hi = before["x2"], before["x2"] + 22.0
            elif after:
                lo, hi = after["x1"] - 22.0, after["x1"]
            else:
                continue
            if hi - lo < 1.0:
                continue                  # no room: the cut, not a theft
            # "the neighbour's ink covers the gap" is NOT evidence when the
            # missing letter is the word's first or last: the gap is then a
            # window I invent past the word's edge, and the neighbour fills
            # it simply by being the next word. The real signal is a
            # SEPARATE body element inside the gap that is DETACHED from the
            # neighbour's own ink — i.e. a stroke the neighbour draws but is
            # not connected to. p384 27:78 وَهُوَ held ٱلْعَزِيزُ's alif as
            # exactly such a detached 2.4x15.0 stroke; p579 فَوَقَىٰهُمُ held
            # ٱللَّهُ's as a 2.7x15.0 one.
            for w2 in words:
                if w2 is w or w2["line"] != w["line"]:
                    continue
                cov, det = 0.0, None
                for k2, (bx1, bx2, by1, by2) in enumerate(w2["bodies"]):
                    ov = min(bx2, hi) - max(bx1, lo)
                    if ov <= 0:
                        continue
                    inside = ov / max(1e-6, bx2 - bx1)
                    if inside < 0.6:
                        continue        # mostly outside: the neighbour's own run
                    sep = min((max(ox1 - bx2, bx1 - ox2)
                               for j, (ox1, ox2, _, _)
                               in enumerate(w2["bodies"]) if j != k2),
                              default=99.0)
                    # measured on the three confirmed thefts (p384 x2,
                    # p579): the stolen letter is a NARROW TALL stroke —
                    # 2.4-3.0 wide, 14.9-15.8 tall — carrying only 6-9% of
                    # its holder's ink. Every false positive of the earlier
                    # versions was the holder's WHOLE WORD, 18-35u wide.
                    # Ratio to the holder's remaining ink is the quantity;
                    # its distribution is printed by --hist.
                    others = [(ox1, ox2, oy1, oy2)
                              for j, (ox1, ox2, oy1, oy2)
                              in enumerate(w2["bodies"]) if j != k2]
                    htot = sum((a2 - a1) * (b2 - b1)
                               for a1, a2, b1, b2 in others)
                    area = (bx2 - bx1) * (by2 - by1)
                    ratio = area / htot if htot > 0 else 99.0
                    if ov > cov:
                        cov, det = ov, (bx1, bx2, by1, by2, sep, ratio)
                if det is not None:
                    out.append({
                        "page": pg, "key": w["key"], "word": w["text"],
                        "missing": g["text"], "group": gi,
                        "gap": [round(lo, 1), round(hi, 1)],
                        "held_by": w2["key"], "held_by_word": w2["text"],
                        "covered": round(cov, 1),
                        "frac": round(cov / (hi - lo), 2),
                        "stroke": [round(det[0], 1), round(det[1], 1),
                                   round(det[2], 1), round(det[3], 1)],
                        "size": "%.1fx%.1f" % (det[1] - det[0],
                                               det[3] - det[2]),
                        "detached_by": round(det[4], 1),
                        "ink_ratio": round(det[5], 3),
                    })
                    break
    return pg, out, None


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    rows, errs = [], []
    with ProcessPoolExecutor(max_workers=int(
            os.environ.get("QSVG_JOBS", "32"))) as ex:
        for pg, out, err in ex.map(scan, range(a, b + 1)):
            rows.extend(out)
            if err:
                errs.append((pg, err))
    rows.sort(key=lambda r: r["ink_ratio"])
    import collections
    hist = collections.Counter()
    for r in rows:
        v = r["ink_ratio"]
        hist[("%.2f" % v) if v < 1 else ">=1"] += 1
    print("ink_ratio distribution (stroke area / holder's remaining ink):")
    for k in sorted(hist, key=lambda x: (x == ">=1", x)):
        print("   %-6s %d" % (k, hist[k]))
    print()
    print("empty ligature groups whose ink a NEIGHBOUR holds: %d "
          "(pages %d-%d)" % (len(rows), a, b))
    if errs:
        print("  %d pages errored" % len(errs))
    print("\n%-6s %-11s %-16s %-6s %-16s %-10s %s"
          % ("page", "word key", "word", "letter", "held by", "stroke",
             "ink ratio"))
    for r in rows[:60]:
        print("p%-5d %-11s %-16s %-6s %-16s %-10s %.3f"
              % (r["page"], r["key"], r["word"], r["missing"],
                 r["held_by_word"], r["size"], r["ink_ratio"]))
    dst = os.path.join(ROOT, "docs", "defects", "stolen_letters.json")
    json.dump(rows, open(dst, "w"), ensure_ascii=False, indent=1)
    print("\nwrote %s" % dst)


if __name__ == "__main__":
    main()
