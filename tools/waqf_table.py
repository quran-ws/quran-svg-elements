#!/usr/bin/env python3
"""Build the signature -> waqf-sign table from MushafDatabase, as data.

Our pipeline gives every pause sign the single label `pause`, so the five signs the
KFGQPC print uses come out of the decomposition indistinguishable. They cannot be
recovered from the text either: quran.com's uthmani edition and this print disagree
about which sign is drawn at 424 of 4,416 positions — 87 of them where the text says
قلى and the page draws ج.

They can be recovered from the ink. Each sign is its own outline, so each has its own
`data-sig`, and MushafDatabase names every waqf path it draws. Over the mushaf that
makes the label a tally rather than a judgement — the four pause signatures came out
99.7% to 100% pure over a hundred pages.

Only signatures the reference names consistently are written. Nothing is guessed.

    python3 tools/waqf_table.py <sig_ref_labels.json>        # from an existing scan
    python3 tools/waqf_table.py <sig_ref_labels.json> --min-purity 0.95 --min-n 20
"""

import argparse
import json
import os
import sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "marks", "waqf_types.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evidence", help="the JSON written by tools/sig_labels_from_ref.py")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--min-purity", type=float, default=0.90)
    ap.add_argument("--min-n", type=int, default=10)
    args = ap.parse_args(argv)

    rows = json.load(open(args.evidence, encoding="utf-8"))["rows"]
    table, skipped = {}, []
    for r in rows:
        if r["ref_kind"] != "waqf":
            continue
        if r["n"] < args.min_n or r["purity"] < args.min_purity:
            skipped.append(r)
            continue
        # ref_label is MushafDatabase's vocabulary; the table is written in the
        # print's own (taxonomy phase 1, decision 8)
        _CANON = {"waqf lazim": "waqf-lazim", "waqf qila": "waqf-awla",
                  "waqf sali": "wasl-awla", "waqf jaiz": "waqf-jaiz",
                  "waqf taanuq": "muanaqah"}
        table[r["sig"]] = {"waqf": _CANON.get(r["ref_label"], r["ref_label"]),
                           "n": r["n"], "purity": r["purity"],
                           "we_call": r["ours"]}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1, sort_keys=True)

    print("%-18s %-13s %8s %8s   %s" % ("signature", "waqf sign", "n", "purity", "we call it"))
    for sig, v in sorted(table.items(), key=lambda t: -t[1]["n"]):
        print("%-18s %-13s %8d %7.1f%%   %s" % (sig, v["waqf"], v["n"],
                                                100 * v["purity"], v["we_call"]))
    print("\nwrote %s — %d signatures" % (args.out, len(table)))
    if skipped:
        print("not written (too few, or not consistent enough):")
        for r in skipped:
            print("   %-18s %-13s n=%-5d purity %.1f%%" % (r["sig"], r["ref_label"],
                                                           r["n"], 100 * r["purity"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
