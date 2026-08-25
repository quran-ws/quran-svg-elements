import json, os, sys
from collections import Counter
S="/private/tmp/claude-501/-Users-abdullah-Documents-Github-quran-svg/e2b2f3f9-54a9-433b-9cdb-4a0da8c551b9/scratchpad"
A=S+"/baseline/pages"; B=S+"/"+(sys.argv[1] if len(sys.argv)>1 else "cand2")+"/pages"
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
worse=[(len(b[p].get("marks",[]))-len(a[p].get("marks",[])),p) for p in common]
worse=[t for t in worse if t[0]>0]
worse.sort(reverse=True)
print("\npages that got WORSE: %d"%len(worse))
for d,p in worse[:12]: print("   p%-4d %+d"%(p,d))
