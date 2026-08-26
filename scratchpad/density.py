"""Is the text denser where the defects are?"""
import importlib.util, io, contextlib, json, os, sys
from collections import defaultdict
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT+"/tools")
spec=importlib.util.spec_from_file_location("assign_words", ROOT+"/tools/assign_words.py")
aw=importlib.util.module_from_spec(spec); sys.modules["assign_words"]=aw
spec.loader.exec_module(aw)
cap={}; orig=aw.rewrite
def spy(p,a): cap["a"]=a; return orig(p,a)
aw.rewrite=spy

def scan(pg):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg, ROOT+"/.cache/words")
    except Exception:
        return None
    lines=defaultdict(list)
    ayahs=set()
    for w,at in cap["a"]:
        if not w: continue
        b=[e for a in at for e in a["els"] if e["kind"]=="body"]
        if not b: continue
        ln=b[0].get("line")
        lines[ln].append((min(e["x1"] for e in b), max(e["x2"] for e in b)))
        ayahs.add((w["surah"],w["ayah"]))
    if not lines: return None
    wpl=[]; gaps=[]; widths=[]
    for ln,ws in lines.items():
        ws.sort(key=lambda t:-t[1])
        wpl.append(len(ws))
        for x1,x2 in ws: widths.append(x2-x1)
        for a,b2 in zip(ws,ws[1:]):
            gaps.append(max(a[0]-b2[1], 0.0))
    n=sum(wpl)
    return {"page":pg,"words":n,"ayahs":len(ayahs),"lines":len(lines),
            "words_per_line":n/len(lines),
            "mean_width":sum(widths)/len(widths),
            "mean_gap":sum(gaps)/len(gaps) if gaps else 0.0}

if __name__=="__main__":
    pages=[int(x) for x in sys.argv[1:]] or list(range(1,605,1))
    from multiprocessing import Pool
    out=[]
    with Pool(2, maxtasksperchild=8) as pool:
        for r in pool.imap_unordered(scan, pages):
            if r: out.append(r)
    json.dump(out, open(ROOT+"/docs/defects/density.json","w"), indent=1)
    w=json.load(open(ROOT+"/docs/defects/width.json"))
    from collections import Counter
    dz=Counter(r["page"] for r in w)
    j=[r for r in out if r["page"]>=582]; o=[r for r in out if r["page"]<582]
    def show(tag, rows):
        if not rows: return
        f=lambda k: sum(r[k] for r in rows)/len(rows)
        d=sum(dz[r["page"]] for r in rows)/len(rows)
        print("  %-22s words/page %5.1f  ayahs %5.1f  words/line %4.1f  "
              "mean width %5.2f  mean gap %4.2f   defects/page %4.1f"
              %(tag,f("words"),f("ayahs"),f("words_per_line"),
                f("mean_width"),f("mean_gap"),d))
    show("juz 30 (p582-604)", j)
    show("rest (p1-581)", o)
