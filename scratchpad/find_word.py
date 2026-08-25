import importlib.util, os, sys
ROOT = "/Users/abdullah/Documents/Github/quran-svg"
sys.path.insert(0, ROOT + "/tools")
spec = importlib.util.spec_from_file_location("assign_words", ROOT + "/tools/assign_words.py")
aw = importlib.util.module_from_spec(spec); sys.modules["assign_words"] = aw
spec.loader.exec_module(aw)
cap = {}; orig = aw.rewrite
def spy(page, a): cap["a"] = a; return orig(page, a)
aw.rewrite = spy
pg = int(sys.argv[1]); needle = sys.argv[2]
aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
for w, at in cap["a"]:
    if not w:
        continue
    key = "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])
    if needle not in w["uthmani"] and needle != key:
        continue
    els = [e for a in at for e in a["els"]]
    if not els: continue
    ln = els[0].get("line")
    print("\n%s  (%d:%d:%d)  line %s" % (w["uthmani"], w["surah"], w["ayah"], w["pos"], ln))
    for e in sorted(els, key=lambda e: -(e["x1"]+e["x2"])/2):
        print("   L%-3s %-6s %-13s x %6.1f-%-6.1f y %6.1f-%-6.1f%s"
              % (e.get("line"), e["kind"], e.get("mark") or "",
                 e["x1"], e["x2"], e["y1"], e["y2"],
                 "  STANDALONE" if e.get("standalone") else ""))
