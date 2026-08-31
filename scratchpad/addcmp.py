import json, sys
res=json.load(open("/tmp/claude-1000/-home-abdullah-Dev-github-com-AbdullahObaid-quran-svg-pipeline/47335e6a-1e93-446c-998f-f48922b1daa1/scratchpad/allsrc.json"))
order=["ours","V4 layout","DigitalKhatt","quran.com"]
L=["\n## 5. Ours vs theirs — every source, all 6,236 ayahs\n",
   "Word-count disagreement with the Complex's own 1441H text, measured over the",
   "whole Quran. Lower is closer to the print's own spelling.\n",
   "| source | what it is | ayahs differing from the rasm |",
   "|---|---|---:|"]
what={"ours":"this pipeline","V4 layout":"the print's own 1441H layout",
      "DigitalKhatt":"the 1421H V2 print","quran.com":"`text_uthmani`"}
for n in order:
    L.append("| **%s** | %s | **%d** |"%(n,what[n],len(res[n])))
L.append("\nThe union of every disagreement, so nothing is hidden by a total:\n")
keys=sorted({k for n in order for k,_,_ in res[n]}, key=lambda x:[int(y) for y in x.split(":")])
L.append("| ayah | rasm | "+" | ".join(order)+" |")
L.append("|---|---:|"+"---:|"*len(order))
for k in keys:
    row=[]; rasm=None
    for n in order:
        hit=next(((a,b) for kk,a,b in res[n] if kk==k), None)
        if hit: rasm=hit[0]; row.append(str(hit[1]))
        else: row.append("·")
    L.append("| %s | %d | %s |"%(k, rasm, " | ".join(row)))
L += ["\n`·` = agrees with the rasm.\n",
 "**Reading it:**\n",
 "* **15:7, 27:20, 36:22 — every source disagrees, including the print's own V4",
 "  layout.** No word-marking source gets these right; only the Complex's text",
 "  does. This is the shared inherited inconsistency of section 3.",
 "* **37:130** — DigitalKhatt and quran.com still hold one word where the rasm and",
 "  V4 have two. We used to, and no longer do; that fix is what brings us level",
 "  with the print's own layout.",
 "* **2:181, 8:6, 13:37** — quran.com fuses `بَعْدَ مَا`. We already split these",
 "  (`_DKSEG_SPLITS`), forced independently by p254's line break.\n",
 "So we now match the print's own layout exactly, and are ahead of DigitalKhatt",
 "and quran.com. The only remaining gap is the three sites where V4 itself",
 "departs from the Complex's text — and closing those would put this",
 "decomposition ahead of every source measured here.\n"]
open("docs/MA-TOKENS.md","a",encoding="utf-8").write("\n".join(L))
print("\n".join(L[:14]))
