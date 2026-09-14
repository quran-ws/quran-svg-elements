"""Word spans on one page/line, under two builds, side by side."""
import importlib.util, io, contextlib, os, sys
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT+"/tools")
def run(pipe, pg):
    spec=importlib.util.spec_from_file_location("assign_words", pipe)
    aw=importlib.util.module_from_spec(spec); sys.modules["assign_words"]=aw
    spec.loader.exec_module(aw)
    cap={}; orig=aw.rewrite
    def spy(p,a): cap["a"]=a; return orig(p,a)
    aw.rewrite=spy
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, ROOT+"/.cache/words")
    out={}
    for w,at in cap["a"]:
        if not w: continue
        els=[e for a in at for e in a["els"]]
        bods=[e for e in els if e["kind"]=="body"]
        if not bods: continue
        out["%d:%d:%d"%(w["surah"],w["ayah"],w["pos"])]=(
            w["rasm_uthmani"], min(e["x1"] for e in bods), max(e["x2"] for e in bods),
            len(bods), bods[0].get("line"))
    return out
pg=int(sys.argv[1]); keys=sys.argv[2:]
a=run(ROOT+"/tools/_pipeline_baseline.py", pg)
b=run(ROOT+"/tools/assign_words.py", pg)
print("%-11s %-16s %-22s %s"%("key","word","BASELINE span/bodies","NOW span/bodies"))
for k in keys:
    ra,rb=a.get(k),b.get(k)
    f=lambda r: "-" if not r else "%6.1f-%-6.1f b%d L%s"%(r[1],r[2],r[3],r[4])
    mark="" if (ra and rb and abs(ra[1]-rb[1])<0.5 and abs(ra[2]-rb[2])<0.5 and ra[3]==rb[3]) else "  <-- CHANGED"
    print("%-11s %-16s %-22s %s%s"%(k,(rb or ra or ["?"])[0], f(ra), f(rb), mark))
