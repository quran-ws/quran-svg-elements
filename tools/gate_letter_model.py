#!/usr/bin/env python3
"""The gate a new letter labeller has to pass, one command per checkpoint.

    python3 tools/gate_letter_model.py .cache/letters/model_ft5.pt --tag ctl

Four measures, because no one of them has ever been enough:

  1. held-out exact-pixel accuracy      (tools/eval_letter_model.py)
  2. joint error against the hand cuts  (same)
  3. agreement with the labels a person drew or confirmed (same)
  4. hard cut failures over pages 1-60  -- what actually ships

Every model trained after `model_ft5` was better at 1 and worse at 4, which is why 4 is
here: a label map can be right about where a boundary goes and still leave a letter with
a sliver the cutter cannot realise. Adopt only on all four.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

ROOT = L.ROOT


def cut_failures(tag, first, last):
    cuts = os.path.join(ROOT, ".cache", "letters", "cuts-" + tag if tag else "cuts")
    bad, why, runs = 0, Counter(), 0
    for p in range(first, last + 1):
        f = os.path.join(cuts, "%03d.json" % p)
        if not os.path.exists(f):
            continue
        rec = json.load(open(f, encoding="utf-8"))
        for w in rec["words"].values():
            for r in w["runs"]:
                runs += 1
                for fl in r["flags"]:
                    if fl.startswith("cut-failed:"):
                        bad += 1
                        why[fl.split(":", 1)[1]] += 1
                        break
    return runs, bad, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--tag", default="probe", help="build tag, keeps this build beside the others")
    ap.add_argument("--pages", type=int, nargs=2, default=(1, 60))
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--skip-build", action="store_true", help="reuse the cuts already under --tag")
    a = ap.parse_args()
    print("== %s ==" % a.model, flush=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_letter_model.py"),
                    "--model", a.model], check=True)
    if not a.skip_build:
        env = dict(os.environ, QSVG_LETTERS_TAG=a.tag)
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_letter_cuts.py"),
                        str(a.pages[0]), str(a.pages[1]), "--jobs", str(a.jobs),
                        "--model", a.model], check=True, env=env,
                       stdout=subprocess.DEVNULL)
    runs, bad, why = cut_failures(a.tag, *a.pages)
    print("hard cut failures, pages %d-%d: %d of %s runs" % (a.pages[0], a.pages[1], bad,
                                                             "{:,}".format(runs)))
    for k, v in why.most_common():
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
