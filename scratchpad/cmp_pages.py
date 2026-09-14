import json, os, sys
S = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(S)
# Sweep results are bulk generated data: one JSON per page, per build. They live
# outside git but must outlive a session, because the pinned "before" build is
# compared against for every change.
SWEEPS = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps"))
sys.path.insert(0, os.path.join(ROOT, "tools"))   # audit_marks lives in tools/
from audit_marks import scan
BASE = os.environ.get("QSVG_BASE_DIR", SWEEPS + "/baseline/pages")
def base_n(pg):
    r=json.load(open("%s/%03d.json"%(BASE,pg)))
    return len(r.get("marks",[]))
if __name__=="__main__":
    pages=[int(x) for x in sys.argv[1:]]
    from multiprocessing import Pool
    with Pool(2) as p:
        res=dict((pg,len(rows)) for pg,rows in p.imap_unordered(scan,pages))
    t0=t1=0
    for pg in pages:
        b,m=base_n(pg),res[pg]; t0+=b; t1+=m
        print("p%-4d base %3d  now %3d  %+d %s"%(pg,b,m,m-b,"" if m==b else ("WORSE" if m>b else "better")))
    print("TOTAL %d -> %d  (%+d)"%(t0,t1,t1-t0))
