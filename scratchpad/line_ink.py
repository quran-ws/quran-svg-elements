import importlib.util, os, sys
ROOT="/Users/abdullah/Documents/Github/quran-svg"
sys.path.insert(0, ROOT+"/tools")
spec=importlib.util.spec_from_file_location("assign_words", ROOT+"/tools/assign_words.py")
aw=importlib.util.module_from_spec(spec); sys.modules["assign_words"]=aw
spec.loader.exec_module(aw)
cap={}; orig=aw.rewrite
def spy(p,a): cap["a"]=a; return orig(p,a)
aw.rewrite=spy
pg=int(sys.argv[1]); ln=int(sys.argv[2])
lo=float(sys.argv[3]); hi=float(sys.argv[4])
aw.assign_page("hafs/kfqc", pg, ROOT+"/.cache/words")
rows=[]
for w,at in cap["a"]:
    for a in at:
        for e in a["els"]:
            if e.get("line")!=ln: continue
            cx=(e["x1"]+e["x2"])/2
            if not (lo<=cx<=hi): continue
            rows.append((cx,e,w))
for cx,e,w in sorted(rows, key=lambda t:-t[0]):
    print("   %-6s %-12s x %6.1f-%-6.1f y %6.1f-%-6.1f  owner=%s"
          %(e["kind"], e.get("mark") or e.get("lab") or "", e["x1"], e["x2"],
            e["y1"], e["y2"], (w or {}).get("uthmani","(none)")))
