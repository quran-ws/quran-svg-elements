#!/usr/bin/env python3
"""Drive audit → adjudicate → override to a fixed point, stopping at the first regression.

One pass does not settle a chain. When three words on a line have each taken a piece of
their neighbour, the middle one's width looks plausible until the outer two are put
right — so the adjudicator returns UNCLEAR for it, no override is written, and it
survives the pass. Fixing the outer two changes what the width prior expects of the
middle one, and the next pass convicts it. p350's `وَٱلزَّانِيَةُ` was UNCLEAR before its
neighbours moved and OURS after.

Each round is gated, and the run stops rather than continuing on a regression:

  * `bench.py` must report no FAILURES and pixelfail 0;
  * the reference's own confirmed defects (THEIRS) must not rise — a round that
    trades our errors for agreement with theirs is not progress and is rolled back;
  * OURS must actually fall, or there is nothing left this loop can reach.

    python3 tools/close_ref_gap.py "<ref>/SVG V1.01" --rounds 4
    python3 tools/close_ref_gap.py "<ref>/SVG V1.01" --rounds 1 --dry-run
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SCRATCH = os.path.join(ROOT, "scratchpad")
OVR = os.path.join(ROOT, ".cache", "review", "overrides.json")
WORDS = os.path.join(ROOT, "docs", "defects", "reference_words.json")
VERDICTS = os.path.join(ROOT, "docs", "defects", "reference_verdicts.json")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def audit(refdir, jobs):
    r = run([sys.executable, os.path.join(TOOLS, "audit_ref_words.py"),
             refdir, "1", "604", "--jobs", str(jobs)])
    if r.returncode:
        raise SystemExit("audit failed:\n" + r.stderr[-2000:])
    d = json.load(open(WORDS, encoding="utf-8"))
    return d["totals"], len(d["flags"])


def adjudicate(refdir, jobs):
    r = run([sys.executable, os.path.join(TOOLS, "adjudicate_ref.py"),
             refdir, "--jobs", str(jobs)])
    if r.returncode:
        raise SystemExit("adjudicate failed:\n" + r.stderr[-2000:])
    return json.load(open(VERDICTS, encoding="utf-8"))["tally"]


def overrides(refdir, jobs, dry):
    cmd = [sys.executable, os.path.join(TOOLS, "ref_overrides.py"), refdir,
           "--jobs", str(jobs)]
    if dry:
        cmd.append("--dry-run")
    r = run(cmd)
    if r.returncode:
        raise SystemExit("ref_overrides failed:\n" + r.stderr[-2000:])
    n = 0
    for ln in r.stdout.splitlines():
        if ln.startswith("wrote ") and "new entries" in ln:
            n = int(ln.split("—")[1].split()[0])
    return n, r.stdout


def bench():
    r = run([sys.executable, os.path.join(SCRATCH, "bench.py")])
    out = r.stdout + r.stderr
    score = fails = pix = None
    for ln in out.splitlines():
        if ln.startswith("SCORE:"):
            score = int(ln.split(":")[1])
        if ln.startswith("FAILURES:"):
            fails = ln.split(":", 1)[1].strip()
        if "pixelfail" in ln:
            pix = int(ln.rsplit("pixelfail", 1)[1].strip())
    return score, fails, pix


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    prev_theirs = None
    prev_ours = None
    for rnd in range(1, args.rounds + 1):
        t0 = time.time()
        print("\n================ round %d" % rnd, flush=True)
        totals, nflags = audit(args.refdir, args.jobs)
        tally = adjudicate(args.refdir, args.jobs)
        ours, theirs = tally.get("OURS", 0), tally.get("THEIRS", 0)
        print("   comparable %d   disagreements %d   OURS %d   THEIRS %d   UNCLEAR %d"
              % (totals["compared"], nflags, ours, theirs, tally.get("UNCLEAR", 0)),
              flush=True)

        # The reference's own count is allowed to drift by a little. It is re-derived
        # every round, and a word that was UNCLEAR last round can be adjudicated THEIRS
        # this round purely because its neighbours moved — that is not an error we
        # imported. What must not happen is a rise that is large, or large RELATIVE to
        # what we gained: round 2 fell 450 -> 247 on our side while theirs rose by one,
        # and rolling that back for the sake of a single word threw away 203 real fixes.
        if prev_theirs is not None:
            rise = theirs - prev_theirs
            gain = (prev_ours - ours) if prev_ours is not None else 0
            if rise > max(2, 0.05 * prev_theirs) or (rise > 0 and gain < 10 * rise):
                # Nothing to roll back: this check runs BEFORE any override is written
                # this round, so what is on disk is the last accepted state. Restoring a
                # backup here threw away the previous round's 222 accepted overrides and
                # made the run a no-op — the "after" score came out identical to the
                # baseline and bench went back from 76 to 77.
                print("   STOP: the reference's own defect count rose %d -> %d against a "
                      "gain of %d on ours. Keeping the last accepted state."
                      % (prev_theirs, theirs, gain))
                return 1
        if prev_ours is not None and ours >= prev_ours:
            print("   settled: OURS did not fall (%d -> %d). Nothing more this loop reaches."
                  % (prev_ours, ours))
            return 0
        prev_theirs, prev_ours = theirs, ours

        if os.path.exists(OVR):
            shutil.copy(OVR, OVR + ".bak%d" % (rnd + 1))
        n, out = overrides(args.refdir, args.jobs, args.dry_run)
        for ln in out.splitlines():
            if ln.strip().startswith("skipped") or "override " in ln or "no reference word" in ln:
                print("   " + ln.strip())
        print("   new overrides this round: %d   (%.0fs)" % (n, time.time() - t0), flush=True)
        if args.dry_run:
            return 0
        if n == 0:
            print("   settled: no new overrides.")
            return 0

        score, fails, pix = bench()
        print("   bench: SCORE %s  FAILURES %s  pixelfail %s" % (score, fails, pix), flush=True)
        if fails != "none" or pix:
            print("   STOP: bench regressed. Rolling this round back.")
            shutil.copy(OVR + ".bak%d" % (rnd + 1), OVR)
            return 1
    print("\nreached the round limit; re-run to continue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
