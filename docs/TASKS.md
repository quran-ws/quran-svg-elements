# Remaining work — 2026-08-29 06:00

State when this list was written (all verified independently, not taken from an
agent's report): pixel identity **604/604**, taxonomy **OK**, bench **SCORE
137** no failures, mark flags **0**, open interval records **0** (1 examined by
eye, p350), `audit_ligatures`: misplaced **6**, empty **195**, count **0**,
order **1**. Overrides **250** (from 426).

Ordered. Each task says what "done" means and which gates must stay green.

---

## 1. Verify and land the meem-iqlab gate  *(in flight)*

`scratchpad/audit_marks.py` now demands `meem-iqlab` ("ۢ", "ۭ"). It was
excluded for years on the grounds that the meem is "fused into the tanween
glyph" — true of the LOW form, **false of the HIGH form**, which left all 609
iqlab sites unguarded. p455 `مُغْتَسَلُۢ` was found holding no meem at all (its
sign sat in `بَارِدࣱ` as anonymous body ink) — MushafDatabase caught the
ownership, Abdullah's eye named the ink.

Measured before the change: 510 words carry the high form, 99 the low, and all
609 hold their mark today, so it should cost **zero** flags.

**Done when:** a full sweep with the change reports marks 0. If it reports
more, they are REAL and must be triaged, not suppressed. Commit only after.

## 2. Per-word ink identity vs MushafDatabase  *(agent running)*

Abdullah's question: "pixel by pixel, word by word, regardless of marks and
groups — 100% match?" Boundaries agree on 77,417/77,422, but that is a weaker
claim than the ink inside each word being identical. The comparison agent was
resumed with this and has the proven registration (one affine per page, 0.10u
median residual).

**Done when:** we can state the exact number of words whose ink matches, with
the difference distribution (seam vs stroke separated by a measured threshold),
and every word differing by more than a seam classified OURS-WRONG /
THEIRS-WRONG / UNDECIDED and shown on `docs/defects/ligature_cuts.html`.

## 3. Shared per-page structural cache + schema v2 phase 1  *(one job, not two)*

CPU is saturated (load 33.6 on 32 cores) while RAM sits at 11 GB of 31 — because
every audit re-runs `assign_page` independently. Phase 1's
`tools/build_annotations.py` must emit a per-page structural dump anyway; that
dump IS the cache.

- Build `.cache/schema/mark-taxonomy.v2.json` (canonical names, categories,
  features, aliases) and `.cache/schema/edition-hafs-kfgqpc.json` (113
  basmalah, waqf FAMILY budgets, sajdah sites, rare sites, sifr counts).
- `tools/build_annotations.py` → per-page logical-mark + relation records.
- `tools/validate_annotations.py` (v2 §16.2-16.5).
- Convert the audits to read the cache; keep `--fresh` on every one, and make
  each PRINT which mode it ran in.
- **Cache invalidation is the risk** — the design is written in
  HANDOFF-2026-08-28.md under "Cache invalidation": key on the content hash of
  `assign_words.py` + every module it imports, this page's overrides entry,
  `labels.json` (global — one label changes hundreds of pages), the artwork and
  text sources, and every non-default `QSVG_*`. On mismatch REBUILD, never
  fall back. Atomic writes. A VERSION file to invalidate everything at once.

**Done when:** the emitted SVG is BYTE-IDENTICAL, logical mark counts equal
current master-path counts family by family over 604 pages, relation
cardinalities hold (muanaqah 2, sajdah line+sign, iqlab by subtype), and
`validate_annotations 1 604` is green.

## 4. The ayah marker belongs to its ayah — by LINK, not nesting

Decided with Abdullah: an ayah is emitted once per line and can span pages, so
it is not a subtree and nesting cannot express the fact. Instead:

- stable `id` on each `<g class="ayah-marker">` (e.g. `mk-2-6`),
- `data-marker="mk-2-6"` on every `<g class="ayah">` fragment,
- `data-ayah-parts="N"` / `data-part="i"` so a consumer knows an ayah is split,
- the same relation becomes a first-class record in phase 1.

Zero ink moves, so the numeral cannot drift and the pixel gate is untouched —
which also dissolves the earlier conflict about re-centring the medallion.
**Abdullah has not yet confirmed this replaces the nesting plan — ask first.**

## 5. The 2,687-word emitter grouping defect (586 pages)  ← RE-PRIORITISED

**Abdullah 2026-08-29 20:43, and it changes the weight of this task:** production
will emit ONE element per word, not per ligature — so on the surface every cut
disagreement (Tier C 157, Tier E 2,687) becomes invisible in the product. The
measurement supports that exactly: `missing-ink 0 | boundary 0 | extent 0` —
NOT ONE cut disagreement changes which ink a word holds or where it starts and
ends.

**But the ligature layer is the stepping stone to LETTER-level decomposition,
which he intends to attempt later and calls "a very hard task".** A run is a
connected stroke sequence, and letters can only be split WITHIN a run. So a
wrong run boundary poisons the foundation of that harder task:

- **Tier E is now the priority, not a curiosity.** We emit one group where the
  joining rules AND MushafDatabase both say two (`data-text="اوليك"` — a run
  the script cannot draw). Splitting that into letters later would mean
  splitting a run that should not exist. It is OURS ALONE and it is a bug, not
  a knowledge gap: our own `segment_word()` agrees with the reference in
  **2,685 of 2,687** — only the emitter loses it.
- **Tier C's "both wrong" family matters too** — the 17 مَوْلَىٰكُمْ-shaped
  words emit runs joining through ى or و, which the script cannot draw.
  Impossible runs; letters inside them would be meaningless.
- **The rest of Tier C can wait.** Two legal cuts disagreeing, neither
  violating a rule, is a convention difference — it describes letters
  differently, it does not block them.

**Order:** production ships one element per word now; the ligature layer stays
in schema v2's DEV profile where the audits live; Tier E is fixed as a RULE
VIOLATION (by rule, not by eye); undecided Tier C rows are left alone until
letters are actually on the table.

**Do not spend Abdullah's eye on Tier C rows that leave word extents
unchanged** — 157 rows that cannot affect the product and do not violate a
rule.

### The original note

MushafDatabase and our own `segment_word()` agree in 2,685 of 2,687 cases that
a word should emit TWO ligature groups where our emitter emits one (e.g.
`data-text="اوليك"` — a run the script cannot draw). Pixel-neutral. Related to
the 195 remaining `empty` groups, which the regrouping agent showed are a BODY
problem: `cluster_line` merged separate narrow bodies into one atom (p447
`إِذَا` is the clean example), so no downstream regrouping can separate them.
**This is a change to the CUT and needs its own measured distribution.**

## 6. The 14 line-error sites — 88 overrides waiting on one fix

The override agent found that 88 of the 250 keepers are not artwork facts but
**14 (page, ayah, direction) sites** where every word draws its neighbour's
ink, each carrying 3-13 entries all shifting the same way. Three of the 14 —
p131 6:34, p341 22:73, p543 58:7 — are exactly the line errors MushafDatabase
found independently (`reference_confirmed.json`). One fix at the word-boundary
stage retires 88 overrides at once. **Deliberately not automated:** a boundary
rule moves body ink on live pages and needs Abdullah's eye, not a threshold.

## 7. Eye-review queue for Abdullah

- `docs/defects/ligature-regroup-for-eye.json` — 3 words where the exact undo
  hands a body back to the atom the CUT put it in (p244 `قَالُوا۟`, p375
  `ٱلْأَوَّلِينَ`, p447 `إِذَا`). The defect is the cut, masked not introduced.
- **11 words too tall for their own form** (1.59x-2.46x) — p129 `بِخَيْرࣲ`,
  p267 `ٱلْمَلَٰٓئِكَةَ`/`أَنْ`/`ٱلسَّمَٰوَٰتِ`, p418 `وَكَفَىٰ`, p531
  `مُّدَّكِرࣲ`, p164 `إِنَّ`, p577 `يَخَافُونَ`/`إِلَّآ`, p437 `ٱلصَّلَوٰةَ`,
  p77 `مِّن`. p71 `غَالِبَ` came from this family and was a real theft.
- **159 UNDECIDED ligature-cut rows**, including 17 `مَوْلَىٰكُمْ`-shaped words
  where BOTH sides merge a different illegal break (truth is three runs).
- 1 open crossline row; 94 over-pitch words (mostly threshold noise, sorted
  worst-first).

## 8. Smaller open items

- **p146 `مُتَشَٰبِهࣰا`** — the ش's third dot still emits as a second path; the
  ONLY split welded part left in the mushaf. Narrowed: at the final sweep the
  part IS referenced by a master, yet at rewrite entry nothing references it.
- **p455 leftovers** — `وَشَرَابࣱ`'s `و` group empty with the real waw filed
  under `شر`; `بَارِدࣱ`'s first `با` empty. Both intra-word, both the cut.
- **`audit_ligatures` `empty` = 195** needs re-measuring: the comparison agent
  found that an atom with NO elements opens no group, which both tools model
  wrongly.
- **6 remaining `misplaced`** — verified audit false positives; fix the audit,
  not the pipeline.
- **`order` = 1** — one row left after the baseline guard; adjudicate it.
- Retire the unused `|weld:<family>` override form if it stays unused.

## 9. Standing, older

`docs/superpowers/plans/2026-08-26-certain-defect-fixes.md` (juz-30 width /
line-partition work), the LSOLVE proposals page decisions, the mismatches board
rebuild, and `reference_confirmed.json`'s 4th entry (p599 `لَهَا`).

---

## Rules that govern all of the above

1. **Pixel identity is inviolable** — `audit_pixels 1 604`, zero failures,
   after every change.
2. **Bench SCORE 137, no failures. Taxonomy OK. Marks 0. Open intervals 0.**
3. **Measure before writing a rule.** Print the distribution. Only an EMPTY
   BAND makes a threshold a proof; put it inside the band and write the
   histogram into the code comment.
4. **Two independent signals** before any automatic move or rename.
5. **No invisible collateral change.** Full-mushaf element diff by (word key,
   kind, mark, d-string) — never by `data-eid`, which is NOT stable across
   builds. Classify every change WRONG / RIGHT / UNCLEAR; unclear goes to
   Abdullah, never ships silently.
6. **Honest flags beat green numbers.** A number that went up may be a defect
   becoming visible (p589), not a regression.
7. **Verify agent results independently** before adopting — two agent
   conclusions were wrong tonight and both were caught this way.
8. **Never commit Claude attribution** to anything pushed.
