"""For each disputed word, ask the ink which line it is drawn in."""
import importlib.util, io, contextlib, json, os, sys
from collections import defaultdict
ROOT="/Users/abdullah/Documents/Github/quran-svg"
sys.path.insert(0, ROOT+"/tools")
spec=importlib.util.spec_from_file_location("assign_words", ROOT+"/tools/assign_words.py")
aw=importlib.util.module_from_spec(spec); sys.modules["assign_words"]=aw
spec.loader.exec_module(aw)
cap={}; orig=aw.rewrite
def spy(p,a): cap["a"]=a; return orig(p,a)
aw.rewrite=spy

def bands(pg):
    d=json.load(open("%s/mushafs/hafs/kfqc/lines/%03d.json"%(ROOT,pg)))
    ls=d.get("lines") if isinstance(d,dict) else d
    return {li["lineNumber"]:(li["top"],li["bottom"]) for li in ls}

rows=json.load(open(ROOT+"/docs/defects/reference_real.json"))
byp=defaultdict(list)
for r in rows: byp[r["page"]].append(r)
print("%-6s %-11s %-14s %-6s %-6s %-8s %s"%("page","key","word","ref","ours","ink in","verdict"))
verdict={}
for pg in sorted(byp):
    bd=bands(pg)
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, ROOT+"/.cache/words")
    idx={}
    for w,at in cap["a"]:
        if not w: continue
        b=[e for a in at for e in a["els"] if e["kind"]=="body"]
        if b: idx["%d:%d:%d"%(w["surah"],w["ayah"],w["pos"])]=b
    for r in byp[pg]:
        b=idx.get(r["key"])
        if not b:
            print("p%-5d %-11s %-14s  (not found)"%(pg,r["key"],r["word"])); continue
        cy=(min(e["y1"] for e in b)+max(e["y2"] for e in b))/2
        home=None
        for ln,(t,bo) in bd.items():
            if t<=cy<=bo: home=ln; break
        v = ("OURS WRONG" if home==r["ref_line"] else
             "reference differs" if home==r["our_line"] else "neither (%s)"%home)
        verdict[v]=verdict.get(v,0)+1
        print("p%-5d %-11s %-14s %-6d %-6d %-8s %s"%(pg,r["key"],r["word"],
              r["ref_line"],r["our_line"],str(home),v))
print("\n", verdict)
