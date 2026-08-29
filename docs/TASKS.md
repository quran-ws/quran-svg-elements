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

---

# UPDATE — 2026-08-29 22:27

Gates re-verified mid-migration: **pixel 604/604 · taxonomy OK · marks 0 ·
intervals 1 (p350, examined) · overrides 270**.

## Reframing that changed the priorities

**"The goal is not to publish the pipeline, the product is the SVGs."**
So pipeline independence stopped being a blocker. The 270 overrides are how we
PRODUCED correct files; nobody consumes the pipeline. The word-boundary fix
dropped from "biggest blocker" to optional — it only matters if the artwork is
re-pulled (as pages 1-2 just were) or if Warsh comes into scope, where Hafs
overrides buy nothing.

**Production emits ONE ELEMENT PER WORD**, so the ligature layer is a DEV
instrument. Measured consequence: NOT ONE of the 2,848 cut disagreements
changes which ink a word holds (`missing-ink 0 | boundary 0 | extent 0`), so
Tier C and Tier E are invisible in the product. They matter only as the
foundation for LETTER-level decomposition later.

**Path data is 80.9% of all bytes** — so collapsing a word to a single
`<path>` buys 6.8% brotli and destroys all 436,708 named marks. One GROUP per
word with marks kept as paths is the recommendation.

## Defects found today, proved, not yet all fixed

1. **Ayah-marker labels REVERSED on 441 of 604 pages.** `tag_ayah_markers`
   pairs the Nth marker in document order with the Nth ayah ascending, but the
   artwork's marker layer runs BOTTOM-TO-TOP. Proved on p3 in ONE coordinate
   space: each ayah's true marker is 10-17u from where that ayah ends and the
   index sequence is 10,9,8...0, eleven for eleven. Visible in the product —
   an ayah-crop of 2:255 draws a medallion reading ٢٥٤. **Assigned to the
   metadata agent; must be fixed BY POSITION, not by reversing the list** (163
   pages are already correct, so ordering is not uniform).
2. **54 words on 51 pages are in the wrong `<g class="line">`** — found by a
   pure reading-order test (within-line order is 9,046/9,046 correct; the
   sequence only breaks across line boundaries). A cheap new whole-corpus
   detector needing no reference and no eye. NOT yet fixed.
3. **Surahs 27, 33, 37, 47 have no `<g class="surah-name">` at all** — the
   banner is mislabelled `basmalah`, which is also the source of all 79 orphan
   named marks. Surah 17's basmalah is split in two (113 groups for 112
   surahs). NOT yet fixed.
4. **The demo page is dead against the new schema** — `template.html` still
   reads `data-surah`/`data-ayah`/`data-word`.

## Corrections to things previously believed

- **No ayah crosses a page boundary** — 6,236 ayahs, 6,236 (page, ayah) pairs,
  confirmed independently in the DigitalKhatt layout DB. TASKS §4 assumed
  otherwise.
- **`data-wid` matches quran.com's word keys EXACTLY** (77,432 words), so any
  word-keyed dataset in that ecosystem joins with no mapping table.
- **CLAUDE.md's "~12% of words split differently" is an encoding artefact** —
  the real number is 9 words in 77,431.
- **p71 غَالِبَ, p413 يَحْزُنكَ, p546 وَمَآ ARE thefts** — a reference
  comparison run AFTER a fix cannot testify about whether the defect existed.
  Proved by rebuilding p71 with the one override disabled: بَعْدِهِۦ's left
  edge moves 7.3u.
- **p587/p277 are SOURCE differences**, not a defect on either side: same shape
  to 0.01-0.02u, drawn 1.4-2.6u apart, and our output is pixel-identical to
  OUR artwork.

## Delivered today (design, not yet built)

- `docs/shipping/SHIPPED-ARTIFACT-2026-08-29.md` — bundle manifest, profiles,
  capability matrix, publishing, licensing FACTS (upstream is CC0 + a KFGQPC
  grant; this repo has no licence file — Abdullah's decision).
- `docs/shipping/FORMAT.md` — the consumer spec that ships WITH the bundle.
- `docs/shipping/DEVELOPER-SERVICES-2026-08-29.md` — the ayah-embed API, with a
  WORKING proof of concept (`poc/ayah_crop_poc.py`, verified by rendering
  2:255). Pre-generating all 6,236 ayahs = 88 MiB brotli, so the flagship is a
  CDN path, not a server; words stay dynamic (149 MiB). PNG after pngquant is
  14.0 KiB mean — same bandwidth as brotli SVG.
- `docs/demo/DEMO-PLAN.md` — developer-facing: what we offer / why they need it
  / how to use it. Provenance (King Fahd Complex) and the pixel guarantee are
  REQUIRED above the fold. Visual design deferred to Claude's design skill.

## Order from here

1. Both agents land → **I re-run all four gates myself** (nothing is trusted
   until then).
2. Fix defects 2 and 3 (line grouping, missing surah-name groups).
3. Build the production profile (one group per word).
4. Ayah-marker linking by id.
5. Rebuild the demo with the design skill.
6. Regenerate `docs/defects/ink_identity.json` — per-page tests overwrote it.
