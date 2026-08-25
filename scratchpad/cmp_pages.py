import json, os, sys
S="/private/tmp/claude-501/-Users-abdullah-Documents-Github-quran-svg/e2b2f3f9-54a9-433b-9cdb-4a0da8c551b9/scratchpad"
sys.path.insert(0,S)
from audit_marks import scan
BASE=S+"/baseline/pages"
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
