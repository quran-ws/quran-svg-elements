import sys, os, re, json, glob, sqlite3, collections
sys.path.insert(0,"tools")
from compare_official_text import our_words, official_words, OFFICIAL
ROOT=os.environ["QSVG_ROOT"]
rasm=official_words(OFFICIAL)
ours={k:len(v) for k,v in our_words().items()}
# DigitalKhatt
dk=collections.Counter()
for loc,txt in sqlite3.connect(".cache/digitalkhatt/digital-khatt-v2.db").execute("select location,text from words"):
    if loc.count(":")==2 and not txt.startswith("۝"):
        dk[":".join(loc.split(":")[:2])]+=1
# quran.com raw cache
qc=collections.Counter()
for f in glob.glob(os.path.join(ROOT,".cache","words","page-*.json")):
    for v in json.load(open(f,encoding="utf-8")).get("verses",[]):
        n=sum(1 for w in v["words"] if w.get("char_type_name")=="word")
        qc[v["verse_key"]]=max(qc[v["verse_key"]], n)
# V4 layout
v4=collections.Counter()
for pg,d in json.load(open(".cache/v4_lines.json")).items():
    for k in d: v4[":".join(k.split(":")[:2])]+=1
srcs={"ours":ours,"DigitalKhatt":dk,"quran.com":qc,"V4 layout":v4}
res={}
for name,src in srcs.items():
    diff=[]
    for k,toks in rasm.items():
        if k in src and src[k]!=len(toks): diff.append((k,len(toks),src[k]))
    res[name]=sorted(diff,key=lambda r:[int(x) for x in r[0].split(":")])
json.dump(res, open("/tmp/claude-1000/-home-abdullah-Dev-github-com-AbdullahObaid-quran-svg-pipeline/47335e6a-1e93-446c-998f-f48922b1daa1/scratchpad/allsrc.json","w"), ensure_ascii=False, indent=1)
for name in srcs:
    cov=sum(1 for k in rasm if k in srcs[name])
    print("%-14s covered %d ayahs, differs from the rasm on %d"%(name,cov,len(res[name])))
    for k,a,b in res[name][:8]: print("      %-9s rasm %2d  %s %2d"%(k,a,name,b))
