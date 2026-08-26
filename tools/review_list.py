#!/usr/bin/env python3
"""What is left that a person has to decide, ranked by page.

Everything an automatic rule could settle has been settled. What remains falls into
kinds that differ in what they need from a reviewer, and this collects them into one
list with a direct link into the review platform for each page.

    python3 tools/review_list.py            # writes docs/defects/manual_review.md
    python3 tools/review_list.py --top 40   # just the worst pages, to the terminal
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF = os.path.join(ROOT, "docs", "defects")
SWEEPS = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps"))
PORT = os.environ.get("QSVG_REVIEW_PORT", "8777")


def load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=0, help="print only the worst N pages")
    ap.add_argument("--sweep", default="gate", help="which sweep directory to read")
    ap.add_argument("--out", default=os.path.join(DEF, "manual_review.md"))
    ap.add_argument("--user", default="abdullah")
    args = ap.parse_args(argv)

    items = defaultdict(list)          # page -> [(kind, key, word, note)]

    # 1. words the adjudicator convicted us on, that no override could reach
    verd = load(os.path.join(DEF, "reference_verdicts.json"), {}).get("verdicts", [])
    ovr = load(os.path.join(ROOT, ".cache", "review", "overrides.json"))
    fixed = {(int(p), t) for p, per in ovr.items() for t in set(per.values())}
    for v in verd:
        if v["verdict"] == "OURS" and (v["page"], v["key"]) not in fixed:
            items[v["page"]].append(("adjudicated ours", v["key"], v.get("word", ""),
                                     (v.get("why") or "")[:70]))
        elif v["verdict"] == "UNCLEAR":
            items[v["page"]].append(("unresolved", v["key"], v.get("word", ""),
                                     (v.get("why") or "")[:70]))
        elif v["verdict"] == "THEIRS":
            items[v["page"]].append(("we look right, confirm", v["key"], v.get("word", ""),
                                     (v.get("why") or "")[:70]))

    # 2. dot clusters no rule can separate
    for r in load("/dev/null", []) or []:
        pass
    dots = load(os.path.join(DEF, "dot_residue.json"), [])
    for r in dots:
        items[r[0]].append(("dot cluster", r[1], r[2],
                            "holds %d dot units, the spelling says %d" % (r[3], r[4])))

    # 3. words drawing more pieces than the joining rules permit
    for r in load(os.path.join(DEF, "piece_residue.json"), []):
        items[r[0]].append(("too many pieces", r[1], r[2],
                            "draws %d runs of ink, the spelling allows %d" % (r[3], r[4])))

    # 4. shapes with no confirmed label, which cost the most per decision
    sig = load(os.path.join(DEF, "sig_flags.json"), {})
    shapes = sorted(sig.items(), key=lambda t: -(t[1] if isinstance(t[1], int) else 0))[:40]

    order = sorted(items, key=lambda p: (-len(items[p]), p))
    if args.top:
        order = order[:args.top]

    kinds = Counter(k for v in items.values() for k, *_ in v)
    lines = []
    lines.append("# What still needs a person")
    lines.append("")
    lines.append("Everything a rule could settle has been settled. These are the decisions "
                 "left, and they are of four different kinds — each needs something "
                 "different from you.")
    lines.append("")
    lines.append("| what | how many | what the decision is |")
    lines.append("|---|---|---|")
    lines.append("| adjudicated ours | %d | our ink is wrong and no override could reach it "
                 "— usually because the fix crosses a line, or the neighbour it would move "
                 "ink to is one the adjudicator says the reference got wrong |"
                 % kinds.get("adjudicated ours", 0))
    lines.append("| unresolved | %d | we and MushafDatabase disagree and the QCF widths, "
                 "the joining rules and the text all fail to separate us. You look and say "
                 "which is right |" % kinds.get("unresolved", 0))
    lines.append("| dot cluster | %d | a cluster where the label, the contour count and the "
                 "welded-member count are identical between meaning two dots and meaning "
                 "three. Only the drawn extent separates them |" % kinds.get("dot cluster", 0))
    lines.append("| too many pieces | %d | the word draws more connected runs of ink than "
                 "its spelling allows, so it is provably holding a neighbour's fragment |"
                 % kinds.get("too many pieces", 0))
    lines.append("| we look right, confirm | %d | the adjudicator says **MushafDatabase** is "
                 "wrong here, not us. Worth a glance, because if it is right we have a "
                 "defect the measure is crediting us for |" % kinds.get("we look right, confirm", 0))
    lines.append("")
    lines.append("Start the platform with `python3 tools/review_server.py`, then follow the "
                 "links. Restart it and clear `.cache/words-svg/hafs-kfqc` after any "
                 "pipeline change or it serves a stale build.")
    lines.append("")
    lines.append("## Pages, worst first")
    lines.append("")
    for pg in order:
        rows = items[pg]
        lines.append("### [page %d](http://127.0.0.1:%s/?page=%d&step=audit&user=%s) — %d to look at"
                     % (pg, PORT, pg, args.user, len(rows)))
        lines.append("")
        lines.append("| word | key | what | why |")
        lines.append("|---|---|---|---|")
        for kind, key, word, note in sorted(rows, key=lambda r: r[1]):
            lines.append("| %s | `%s` | %s | %s |" % (word or "&nbsp;", key, kind, note))
        lines.append("")

    if shapes:
        lines.append("## Shapes, if you would rather answer once and fix many")
        lines.append("")
        lines.append("A shape signature names ink for the whole mushaf, so one answer "
                     "settles every occurrence. `python3 tools/label_sheet.py "
                     "docs/defects/sig_flags.json` builds a sheet showing each shape in "
                     "place; `tools/apply_labels.py` folds the answers back in. Measure "
                     "with `scratchpad/label_bisect.py` before adopting — one wrong entry "
                     "cost +527 flags last time.")
        lines.append("")

    os.makedirs(DEF, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("pages needing a look: %d   items: %d"
          % (len(items), sum(len(v) for v in items.values())))
    for k, n in kinds.most_common():
        print("   %-24s %4d" % (k, n))
    print("\nworst pages: %s"
          % ", ".join("p%d(%d)" % (p, len(items[p])) for p in order[:15]))
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
