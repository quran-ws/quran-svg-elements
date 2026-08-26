"""Are the broken words the ones standing next to an ayah medallion?"""
import importlib.util, io, contextlib, json, sys, os
from collections import defaultdict
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT+"/tools")
spec=importlib.util.spec_from_file_location("assign_words", ROOT+"/tools/assign_words.py")
aw=importlib.util.module_from_spec(spec); sys.modules["assign_words"]=aw
spec.loader.exec_module(aw)
cap={}; orig=aw.rewrite
def spy(p,a): cap["a"]=a; return orig(p,a)
aw.rewrite=spy
bad=defaultdict(set)
for r in json.load(open(ROOT+"/docs/defects/width.json")):
    bad[r["page"]].add(r["key"])

def scan(pg):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg, ROOT+"/.cache/words")
    except Exception:
        return None
    # last word of an ayah stands immediately before its medallion
    last=set(); allw=set()
    seen={}
    for w,at in cap["a"]:
        if not w: continue
        k=(w["surah"],w["ayah"])
        seen[k]=max(seen.get(k,0), w["pos"])
        allw.add("%d:%d:%d"%(w["surah"],w["ayah"],w["pos"]))
    for (s,a),mx in seen.items(): last.add("%d:%d:%d"%(s,a,mx))
    first={"%d:%d:1"%(s,a) for (s,a) in seen}
    b=bad.get(pg,set())
    return (len(allw&b), len(allw), len((last|first)&b), len(last|first))

if __name__=="__main__":
    from multiprocessing import Pool
    tb=tw=eb=ew=0
    with Pool(2, maxtasksperchild=8) as pool:
        for r in pool.imap_unordered(scan, range(1,605)):
            if not r: continue
            tb+=r[0]; tw+=r[1]; eb+=r[2]; ew+=r[3]
    edge_rate=eb/ew*100 if ew else 0
    mid_b=tb-eb; mid_w=tw-ew
    mid_rate=mid_b/mid_w*100 if mid_w else 0
    print("words touching an ayah boundary (first or last of an ayah):")
    print("   %d of %d are the wrong size = %.1f%%"%(eb,ew,edge_rate))
    print("words in the middle of an ayah:")
    print("   %d of %d are the wrong size = %.1f%%"%(mid_b,mid_w,mid_rate))
    if mid_rate: print("\n   a word beside a medallion is %.1fx more likely to be broken"%(edge_rate/mid_rate))
