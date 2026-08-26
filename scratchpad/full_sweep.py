#!/usr/bin/env python3
"""Full-mushaf baseline: both audits per page, resumable, one JSON per page."""
import json, os, sys, time
S = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(S)
# Sweep results are bulk generated data: one JSON per page, per build. They live
# outside git but must outlive a session, because the pinned "before" build is
# compared against for every change.
SWEEPS = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps"))
sys.path.insert(0, S)
OUT = os.environ.get("QSVG_OUT", SWEEPS + "/baseline/pages")
os.makedirs(OUT, exist_ok=True)

def one(pg):
    import audit_marks, audit_intervals
    rec = {"page": pg}
    try:
        _, rows = audit_marks.scan(pg)
        rec["marks"] = [{"key": r[0], "word": r[1],
                         "bad": [[str(x) for x in b] for b in r[2]]} for r in rows]
    except Exception as e:
        rec["marks_err"] = str(e)[:120]
    try:
        rec["intervals"] = audit_intervals.scan(pg)
    except Exception as e:
        rec["intervals_err"] = str(e)[:120]
    return pg, rec

if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    todo = [p for p in range(a, b + 1)
            if not os.path.exists("%s/%03d.json" % (OUT, p))]
    print("todo %d pages" % len(todo), flush=True)
    from multiprocessing import Pool
    t0 = time.time()
    with Pool(int(os.environ.get("QSVG_JOBS", "2")), maxtasksperchild=6) as pool:
        for i, (pg, rec) in enumerate(pool.imap_unordered(one, todo), 1):
            json.dump(rec, open("%s/%03d.json" % (OUT, pg), "w"), ensure_ascii=False)
            el = time.time() - t0
            print("[%4d/%4d] p%-4d marks=%d iv=%d  %.0fs elapsed, eta %.0fmin"
                  % (i, len(todo), pg, len(rec.get("marks", [])),
                     len(rec.get("intervals", [])), el,
                     (el / i) * (len(todo) - i) / 60), flush=True)
    print("SWEEP DONE", flush=True)
