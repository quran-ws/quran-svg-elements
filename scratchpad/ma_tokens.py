import sys, re, collections
sys.path.insert(0,"tools")
from compare_official_text import our_words, official_words, OFFICIAL, normalise_official, normalise_ours
ours=our_words(); off=official_words(OFFICIAL)
strip=lambda t: re.sub(r'[ً-ٕٗ-ٰٟۖ-ࣰۭ-ࣳـ]','',t)

inv=collections.defaultdict(lambda: {"n":0,"sites":[]})
for k in ours:
    for p in sorted(ours[k]):
        s=strip(ours[k][p])
        if s=="ما" or s.startswith("ما") or s.startswith("وما"):
            e=inv[s]; e["n"]+=1
            if len(e["sites"])<1: e["sites"].append((k,p,ours[k][p]))
rows=sorted(inv.items(), key=lambda kv:-kv[1]["n"])

# the ما + لـ family: every site, ours vs rasm
fam=[]
for k in sorted(ours, key=lambda x:[int(y) for y in x.split(":")]):
    d=ours[k]
    for p in sorted(d):
        s=strip(d[p]); nx=strip(d.get(p+1,""))
        if s in ("ما","وما","فما","مال","فمال","ومال") and nx in ("هذا","هؤلاء","لي","لى"):
            rasm=[t for t in off.get(k,[]) if strip(t).startswith(("مال","فمال","ومال")) or strip(t) in ("ما","لي","لى","هذا","هؤلاء")]
            joined = any(strip(t).startswith(("مالي","ومالي","فمالي")) for t in off.get(k,[]))
            welded = strip(d[p]).endswith("ل")
            fam.append((k,d[p],d.get(p+1,""),rasm,joined,welded))

L=[]
L.append("# How `ما` and `وما` are treated\n")
L.append("Generated from the emitted pages by `scratchpad/mkmd.py` — no text typed by hand.\n")
L.append("Ours = the tokens we emit. Rasm = whitespace tokens of the Complex's 1441H text.\n")
L.append("\n## 1. The inventory — every token starting with `ما` or `وما`\n")
L.append("%d distinct tokens, %d occurrences.\n" % (len(rows), sum(e['n'] for _,e in rows)))
L.append("\n| token | n | first site | as emitted |")
L.append("|---|---:|---|---|")
for s,e in rows:
    k,p,t=e["sites"][0]
    L.append("| `%s` | %d | %s:%d | `%s` |" % (s,e["n"],k,p,t))

L.append("\n## 2. The `ما` + `لـ` family — where the seam actually is\n")
L.append("Every site where a `ما`/`مال` token is followed by `هذا`, `هؤلاء` or `لي`.\n")
L.append("\n| ayah | ours | the rasm | agree? |")
L.append("|---|---|---|---|")
for k,a,b,rasm,joined,welded in fam:
    ok = "❌ rasm welds, we split" if joined else "✅"
    L.append("| %s | `%s` + `%s` | `%s` | %s |" % (k, a, b, " ".join(rasm[:3]), ok))
open("docs/MA-TOKENS.md","w",encoding="utf-8").write("\n".join(L)+"\n")
print("wrote docs/MA-TOKENS.md — %d inventory rows, %d family rows"%(len(rows),len(fam)))
