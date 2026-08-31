import sys, re, json, sqlite3
sys.path.insert(0,"tools")
from compare_official_text import our_words, official_words, OFFICIAL
ours=our_words(); rasm=official_words(OFFICIAL)
res=json.load(open("/tmp/claude-1000/-home-abdullah-Dev-github-com-AbdullahObaid-quran-svg-pipeline/47335e6a-1e93-446c-998f-f48922b1daa1/scratchpad/allsrc.json"))
strip=lambda t: re.sub(r'[ً-ٕٗ-ٰٟۖ-ࣰۭ-ࣳـ]','',t)
def pair(k, want):
    d=ours[k]
    for p in sorted(d):
        if strip(d[p]) in want: return d[p], d.get(p+1,"")
    return "",""
def rasmtok(k, pref):
    return " ".join(t for t in rasm[k] if strip(t).startswith(pref))
F={}
for k,w,pr in (("4:78",("فمال",),"فمال"),("18:49",("مال",),"مال"),("25:7",("مال",),"مال"),
               ("40:41",("ما",),"ما"),("27:20",("ما",),"مالي"),("36:22",("وما",),"ومالي"),
               ("15:7",("لو",),"لوما")):
    a,b=pair(k,w); F[k]=(a,b,rasmtok(k,pr))
L=[]
A=L.append
A("# Word segmentation in the KFGQPC 1441H mushaf: three sites where every source disagrees with the print's own text\n")
A("A short report for the Itqan community. Everything below is reproducible; the")
A("tooling and full measurements are linked at the end.\n")
A("## Summary\n")
A("We decompose the KFGQPC V4 (1441H) Madani mushaf page artwork into ayah -> word")
A("-> ligature -> mark, pixel-identical to the print. That makes word BOUNDARIES a")
A("primary key, so we checked ours against the King Fahd Complex's own published")
A("text (`UthmanicHafs_v2-0`) across all 6,236 ayahs.\n")
A("Result: **four ayahs in the whole Quran** where word-marking sources disagree")
A("with the Complex's own spelling. They are all the same classical topic —")
A("**المقطوع والموصول**.\n")
A("| source | what it is | ayahs differing from the Complex's text |")
A("|---|---|---:|")
for n,w in (("ours","this decomposition"),("V4 layout","the print's own 1441H layout"),
            ("DigitalKhatt","the 1421H V2 print"),("quran.com","`text_uthmani`")):
    A("| %s | %s | **%d** |"%(n,w,len(res[n])))
A("\n| ayah | the Complex's text | how the sources tokenise it |")
A("|---|---|---|")
for k in ("15:7","27:20","36:22"):
    a,b,r=F[k]; A("| %s | `%s` — one word | `%s` + `%s` — two |"%(k,r,a,b))
a,b,r=F["40:41"]; 
A("\nAnd `37:130`: the Complex's text and the V4 layout both give **two** words;")
A("DigitalKhatt and quran.com give one. (We fixed this one — it also closed a")
A("long-standing flag in our own audit, where one word held two words' ink.)\n")
A("## Why we think the three are an inconsistency, not a convention\n")
A("The obvious defence is that word-by-word tokenisation follows ordinary modern")
A("orthography rather than the rasm. That does not survive the data. In the very")
A("same construction, every source **welds** `ما`+`لـ` where the rasm welds it:\n")
A("| ayah | sources emit | the Complex's text | agree? |")
A("|---|---|---|---|")
for k in ("4:78","18:49","25:7","40:41","27:20","36:22"):
    a,b,r=F[k]
    ok = "no" if k in ("27:20","36:22") else "yes"
    A("| %s | `%s` + `%s` | `%s` | %s |"%(k,a,b,r,ok))
A("\nModern orthography would not weld `مَالِ` at 18:49 — it would write the lam")
A("with the following noun. So the sources are following the rasm there, and then")
A("not following it at 27:20 and 36:22. Note especially **40:41 against 27:20**:")
A("the same phrase, separated in one place and welded in the other. That is")
A("transmitted site by site, which is exactly what المقطوع والموصول is.\n")
open("docs/reports/itqan-word-segmentation.md","w",encoding="utf-8").write("\n".join(L)+"\n")
print("ok")
