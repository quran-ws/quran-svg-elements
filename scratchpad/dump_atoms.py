import importlib.util, os, sys
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
want = set(sys.argv[3:])
rows = []
for w, at in cap["a"]:
    if not w: continue
    els = [e for a in at for e in a["els"]]
    if not els or els[0].get("line") != target: continue
    rows.append((w, at, els))
rows.sort(key=lambda r: -max(e["x2"] for e in r[2]))
for w, at, els in rows:
    if want and w["uthmani"] not in want: continue
    print("\n%s  (%d:%d:%d)   %d atom(s)" % (w["uthmani"], w["surah"], w["ayah"], w["pos"], len(at)))
    for a in sorted(at, key=lambda a: -a["x2"]):
        bod = [e for e in a["els"] if e["kind"] == "body"]
        print("   atom x %6.1f-%-6.1f  %d els (%d body)  bodies: %s"
              % (a["x1"], a["x2"], len(a["els"]), len(bod),
                 ", ".join("%.1f-%.1f" % (b["x1"], b["x2"]) for b in bod)))
