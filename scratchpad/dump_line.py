import importlib.util, os, sys, json
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")
spec = importlib.util.spec_from_file_location("assign_words", ROOT + "/tools/assign_words.py")
aw = importlib.util.module_from_spec(spec); sys.modules["assign_words"] = aw
spec.loader.exec_module(aw)
cap = {}; orig = aw.rewrite
def spy(page, a): cap["a"] = a; return orig(page, a)
aw.rewrite = spy
pg, target = int(sys.argv[1]), int(sys.argv[2])
aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
q = json.load(open(ROOT + "/.cache/qcf_widths.json"))
rows = []
for w, at in cap["a"]:
    if not w: continue
    els = [e for a in at for e in a["els"]]
    if not els or els[0].get("line") != target: continue
    b = [e for e in els if e["kind"] == "body"]
    if not b: continue
    rows.append((min(e["x1"] for e in b), max(e["x2"] for e in b), w, els, b))
rows.sort(key=lambda r: -r[1])
print("p%d line %d, RTL order:" % (pg, target))
print("%-16s %-14s %5s %5s %6s  %s" % ("word","x-span","bods","width","qcf-w","marks"))
tot_a = sum(r[1]-r[0] for r in rows)
tot_q = sum(q.get("%d:%d:%d"%(r[2]["surah"],r[2]["ayah"],r[2]["pos"]),0) for r in rows)
for x1,x2,w,els,b in rows:
    key = "%d:%d:%d"%(w["surah"],w["ayah"],w["pos"])
    qw = q.get(key,0)
    exp = (qw/tot_q*tot_a) if tot_q else 0
    mks = [e.get("mark") for e in els if e["kind"]=="mark" and not e.get("mkpart")]
    print("%-16s %6.1f-%-6.1f %4d %6.1f %6.1f  %s" % (w["uthmani"], x1, x2, len(b),
          x2-x1, exp, " ".join(m or "?" for m in mks)))
