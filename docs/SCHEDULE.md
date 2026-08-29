# Remaining work, in execution order — 2026-08-29 23:47

Abdullah is away and asked for everything remaining to be scheduled and done.
Order matters: **the two SCHEMA changes come first**, because the format spec
and the demo are written against the schema and would otherwise be built twice.

State at the start of this schedule (verified, not inherited): pixel identity
**604/604** · taxonomy **OK** · bench **SCORE 137, no failures** · sweep
**marks 0, intervals 1** (p350, examined by eye).

---

## 1. Structural defects  *(agent running)*
Two things that are wrong in the product and change DATA, not shape.
- **54 words on 51 pages sit in the wrong `<g class="line">`.** Detector to be
  rebuilt first as `tools/audit_wordline.py` so it can be measured before and
  after and can never silently return.
- **Surahs 27, 33, 37, 47 have no `<g class="surah-name">`** — their banner is
  mislabelled `basmalah`, which is also the source of all 79 orphan named
  marks. Surah 17's basmalah is split in two (113 groups for 112 surahs).
- Must establish whether the DigitalKhatt layout DB is wrong or our reading of
  it is, with evidence.

## 2. Ayah-marker linking — **SCHEMA CHANGE**
Decided with Abdullah: an ayah is emitted once per LINE, so it is not a
subtree and nesting cannot express the relation. Link instead:
- stable `id` on each `<g class="ayah-marker">` (e.g. `mk-2-6`)
- `data-marker="mk-2-6"` on every `<g class="ayah">` fragment
- `data-ayah-parts="N"` / `data-part="i"` so a consumer knows an ayah is split
- the same relation as a record in the phase-1 annotation graph
**Zero ink moves**, so the numeral cannot drift and pixel identity is untouched
— which also dissolves the earlier question about re-centring the medallion.

## 3. Production profile — **SCHEMA CHANGE**
One `<g class="word">` per word, marks kept as separate paths, ligature groups
dropped. Measured basis: path `d` data is **80.9% of all bytes**, so collapsing
a word to a single `<path>` buys only 6.8% brotli while deleting all 436,708
named marks. The ligature layer stays in the DEV profile, where the audits that
find stolen letters and misplaced diacritics live.
Deliverable: a profile switch, both profiles gated, and the size of each
measured on real pages.

**Also decided (Abdullah 2026-08-30 00:07): DROP `class="ayahPolygon"` from the
production profile, keep it in dev.** They were how ayah highlighting and
click-detection worked before there were word elements. Word level supersedes
both: a click lands on a word path and walks up to `<g class="ayah" data-aid>`
— which also says WHICH WORD, something the polygon never could — and
`[data-aid="2:6"]` selects every fragment for styling.
Measured cost if kept: 6,236 paths, 1.23 MiB, **0.27% of the corpus** — so this
is a semantics decision, not a size one.
What a consumer loses, and it is real: the polygon is a CONTINUOUS BAND across
the full line width, while words are ink only. So (a) tapping in the gap
BETWEEN two words of one ayah now hits nothing, which matters on touch, and
(b) band-style highlighting must be computed from the word boxes per line
rather than handed over. Both are ~10 lines of JS, and the ayah-crop proof of
concept already computes that union without polygons — so a convenience is
being removed, not a capability.
The pipeline itself is unaffected: it reads polygons from the SOURCE artwork to
derive ayah membership (`assign_words.py` skips them when building elements),
never from its own output.
If band-highlighting later proves to matter, the right answer is PER-LINE BOXES
in the annotation graph, not invisible paths in every page.

## 4. Refresh `docs/shipping/FORMAT.md`
Already 930 lines and already stale — it has no `data-search` (added 23:40).
After steps 2 and 3 it also needs: the marker-link attributes, BOTH profiles
described, and the corrected header counts from step 1.

## 5. Build the demo site
`docs/demo/DEMO-PLAN.md` (729 lines) is the plan; the page is not built and the
current `index.html` is BROKEN against the new schema. Structure it as Abdullah
framed it — **what we offer / why they need it / how to use it** — with the
King Fahd Complex provenance and the pixel guarantee above the fold, and no
licence terms anywhere. **Visual design with Claude's design skill, per his
instruction, once the content is right.**

## 6. Regenerate `docs/defects/ink_identity.json`
Per-page tests overwrote the 604-page file with single-page output.

---

## Standing rules for all of it
1. **Pixel identity is inviolable** — `audit_pixels 1 604`, zero failures,
   after every change.
2. bench **SCORE 137 no failures** · taxonomy OK · sweep marks 0, intervals 1.
3. **Measure before writing a rule.** Print the distribution; a threshold is a
   proof only inside an EMPTY BAND, and the histogram goes in the code comment.
4. **No invisible collateral change.** Full-mushaf element diff by (word key,
   kind, mark, d-string) — NEVER by `data-eid`, which is not stable across
   builds. Classify every change WRONG / RIGHT / UNCLEAR; unclear goes to a
   file for Abdullah, never ships silently.
5. **Honest flags beat green numbers.** A number that goes up may be a defect
   becoming visible, not a regression.
6. **Verify agent results independently** before adopting. Several agent
   conclusions were wrong today and every one was caught this way.
7. Never commit Claude attribution.

## Deferred deliberately — NOT in this schedule
- The word-boundary fix (88 overrides). Not a blocker now that the product is
  the SVGs; matters only if the artwork is re-pulled or Warsh comes into scope.
- Tier C's 157 undecided cut rows — invisible in the production profile and no
  rule is violated.
- Tier E's 2,687 under-cut words — matters for LETTER-level decomposition
  later. The measured reference-free fix (refusing the width-prior DP when the
  atom count already equals the rule's piece count) takes cut 2,848 -> 1,020
  with no outside data; `QSVG_MDBCUT` reaches 24 but makes another project's
  decomposition a build input.
- The shared structural cache — dev speed only.
- Licensing, the domain choice, and the medallion re-fit values: Abdullah's.
