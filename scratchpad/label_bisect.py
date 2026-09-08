"""Which of the confirmed labels actually help, measured one at a time."""
import json, os, shutil, sys
ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,S)
TAB=ROOT+"/.cache/marks/labels.json"
import audit_marks as AM
PAGES=[3,20,44,99,127,130,200,286,350,400,500]

def measure():
    aw=AM._load()
    aw._SHAPE_LABELS=None                      # force the table to be re-read
    shutil.rmtree(ROOT+"/.cache/words-svg/hafs-kfqc", ignore_errors=True)
    tot=hz=0
    for pg in PAGES:
        _,rows=AM.scan(pg)
        tot+=len(rows)
        hz+=sum(1 for r in rows for b in r[2] if b[0]=="hamzah")
    return tot,hz

orig=json.load(open("/tmp/labels.orig.json"))
withall=json.load(open("/tmp/labels.with26.json"))
changed={sg:v for sg,v in withall.items()
         if (orig.get(sg) or {}).get("label")!=v.get("label")}
print("labels differing from the original table: %d"%len(changed), flush=True)
json.dump(orig, open(TAB,"w"), ensure_ascii=False, indent=0)
base=measure(); print("baseline: flags %d hamzah %d"%base, flush=True)
rows=[]
for sg,v in changed.items():
    t=dict(orig); t[sg]=v
    json.dump(t, open(TAB,"w"), ensure_ascii=False, indent=0)
    f,h=measure()
    d=f-base[0]
    rows.append((d,h-base[1],sg,(orig.get(sg) or {}).get("label"),v.get("label")))
    print("  %+3d flags %+3d hamzah   %s  %s -> %s"%(d,h-base[1],sg[:12],
          rows[-1][3],rows[-1][4]), flush=True)
good={sg:withall[sg] for d,_,sg,_,_ in rows if d<=0}
keep=dict(orig); keep.update(good)
json.dump(keep, open(TAB,"w"), ensure_ascii=False, indent=0)
print("\nkept %d of %d changed labels"%(len(good),len(rows)))
print("final:", measure())
