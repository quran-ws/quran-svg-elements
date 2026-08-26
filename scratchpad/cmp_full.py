import json, os, sys
from collections import Counter
S = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(S)
# Sweep results are bulk generated data: one JSON per page, per build. They live
# outside git but must outlive a session, because the pinned "before" build is
# compared against for every change.
SWEEPS = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps"))

def sweep_dir(name):
    """A sweep is named (under SWEEPS) or given as a path; either may end at /pages."""
    # the /pages form first: a sweep directory also contains its own parent name, and
    # matching the parent silently compares two empty directories and reports no change
    for cand in (os.path.join(name, "pages"), name,
                 os.path.join(SWEEPS, name, "pages"), os.path.join(SWEEPS, name)):
        if os.path.isdir(cand) and any(f.endswith(".json") for f in os.listdir(cand)):
            return cand
    raise SystemExit("no such sweep: %s (looked under %s)" % (name, SWEEPS))

A = sweep_dir(os.environ.get("QSVG_BASE", "baseline"))
B = sweep_dir(sys.argv[1] if len(sys.argv) > 1 else "cand2")
print("baseline  %s\ncandidate %s" % (A, B))
def load(d):
    out={}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"): continue
        r=json.load(open(os.path.join(d,f)))
        out[r["page"]]=r
    return out
a,b=load(A),load(B)
common=sorted(set(a)&set(b))
def fams(r):
    c=Counter()
    for x in r.get("marks",[]):
        for y in x["bad"]: c[y[0]]+=1
    return c
ma=sum(len(a[p].get("marks",[])) for p in common)
mb=sum(len(b[p].get("marks",[])) for p in common)
ia=sum(len(a[p].get("intervals",[])) for p in common)
ib=sum(len(b[p].get("intervals",[])) for p in common)
ca=sum(1 for p in common if not a[p].get("marks") and not a[p].get("intervals"))
cb=sum(1 for p in common if not b[p].get("marks") and not b[p].get("intervals"))
print("pages compared: %d"%len(common))
print("MARK flags     %5d -> %5d  (%+d)"%(ma,mb,mb-ma))
print("INTERVAL flags %5d -> %5d  (%+d)"%(ia,ib,ib-ia))
print("fully clean    %5d -> %5d  (%+d)"%(ca,cb,cb-ca))
FA,FB=Counter(),Counter()
for p in common: FA+=fams(a[p]); FB+=fams(b[p])
print("\n%-12s %7s %7s %7s"%("family","before","after","delta"))
for k in sorted(set(FA)|set(FB), key=lambda k:-FA[k]):
    if FA[k] or FB[k]:
        print("%-12s %7d %7d %+7d"%(k,FA[k],FB[k],FB[k]-FA[k]))
# Both audits, not marks alone. Counting only `marks` reported nine pages worse on a
# run that had fixed 328 mark flags and 180 interval flags: p454 and p136 each traded
# ONE mark flag for THREE interval flags — a two-flag improvement each — and were listed
# as regressions. The accept rule is read off this line, so a measure that calls an
# improvement a regression costs real fixes.
def _tot(d): return len(d.get("marks",[]))+len(d.get("intervals",[]))
worse=[(_tot(b[p])-_tot(a[p]),p) for p in common]
worse=[t for t in worse if t[0]>0]
worse.sort(reverse=True)
print("\npages that got WORSE (marks + intervals): %d"%len(worse))
for d,p in worse[:12]: print("   p%-4d %+d"%(p,d))
_mo=[(len(b[p].get("marks",[]))-len(a[p].get("marks",[])),p) for p in common]
_mo=[t for t in _mo if t[0]>0 and _tot(b[t[1]])<=_tot(a[t[1]])]
if _mo:
    print("   (%d more gained a mark flag but lost as many or more interval flags: %s)"
          %(len(_mo),", ".join("p%d"%p for _,p in sorted(_mo,key=lambda t:t[1]))))
