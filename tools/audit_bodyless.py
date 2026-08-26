"""Words holding no letter ink at all.

A word must have letters, so this is provable rather than probable — and it is the
blind spot CLAUDE.md names, since a body-less word never enters `wrec`. Four in the
whole mushaf. Only p371 `مبين` split cleanly at a body boundary (the QCF widths said
0.54 and the gap gave 0.55); the other three have overlapping or fused ink and need a
real split, not an override.

    python3 tools/audit_bodyless.py 1 604 6 out.json
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter
ROOT = os.environ["QSVG_ROOT"]
AW=None; CAP={}
def page(pg):
    global AW
    if AW is None:
        sp=importlib.util.spec_from_file_location("assign_words",os.path.join(ROOT,"tools","assign_words.py"))
        AW=importlib.util.module_from_spec(sp); sys.modules["assign_words"]=AW; sp.loader.exec_module(AW)
        _o=AW.rewrite; AW.rewrite=lambda p,a:(CAP.__setitem__("a",a), _o(p,a))[1]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT,".cache","words"))
    except Exception as e:
        return pg, [], Counter({"page-error":1})
    seq=[]
    for w,at in CAP["a"]:
        if not w: continue
        els=[e for a in at for e in a["els"]]
        b=[e for e in els if e["kind"]=="body"]
        ln=[e.get("line") for e in b if e.get("line")]
        seq.append({"k":"%d:%d:%d"%(w["surah"],w["ayah"],w["pos"]),"t":w["uthmani"],
                    "nb":len(b),"nm":len(els)-len(b),
                    "x":(min(e["x1"] for e in b),max(e["x2"] for e in b)) if b else None,
                    "ln":max(set(ln),key=ln.count) if ln else None})
    out=[]; c=Counter({"words":len(seq)})
    for i,s in enumerate(seq):
        if s["nb"]: continue
        c["body-less words"]+=1
        nb=[seq[j] for j in (i-1,i+1) if 0<=j<len(seq) and seq[j]["x"]]
        wide=max(nb,key=lambda z:z["x"][1]-z["x"][0]) if nb else None
        out.append({"page":pg,"k":s["k"],"t":s["t"],"marks":s["nm"],
                    "neighbour":wide["k"] if wide else None,
                    "ntext":wide["t"] if wide else None,
                    "nwidth":round(wide["x"][1]-wide["x"][0],1) if wide else None})
    return pg,out,c
if __name__=="__main__":
    from multiprocessing import Pool
    rows=[]; tot=Counter()
    with Pool(int(sys.argv[3]),maxtasksperchild=8) as pool:
        for pg,out,c in pool.imap_unordered(page,range(int(sys.argv[1]),int(sys.argv[2])+1)):
            rows+=out; tot.update(c)
    print("words %d | body-less %d (%.4f%%) | page errors %d"
          %(tot["words"],tot["body-less words"],
            100.0*tot["body-less words"]/max(1,tot["words"]),tot["page-error"]))
    print("\n%-6s %-11s %-16s %-6s %-11s %-16s %s"%("page","key","word","marks","neighbour","its text","its width"))
    for r in sorted(rows,key=lambda r:r["page"]):
        print("p%-5d %-11s %-16s %-6d %-11s %-16s %s"
              %(r["page"],r["k"],r["t"],r["marks"],r["neighbour"] or "-",
                r["ntext"] or "-",r["nwidth"]))
    json.dump(rows,open(sys.argv[4],"w"),ensure_ascii=False,indent=1)
    print("\nwrote %s"%sys.argv[4])
