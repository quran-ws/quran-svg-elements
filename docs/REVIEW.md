# For Abdullah's review

Everything needing your decision or your eye, in one place.
Written overnight 2026-08-29/30. Nothing here was decided on your behalf; where
I acted it says so, and every action is reversible.

**State of the build, verified after every change:**
604/604 pixel-identical · bench SCORE 137, no failures, pixelfail 0 ·
audit_taxonomy OK · validate_annotations OK · sweep marks 0, intervals 1 (p350).

---

## A. Decisions still open

### A1. Where the site lives
quran.ws, quranpedia.net, or GitHub Pages. It sets the base URLs in the demo and
the bundle README. Wired through single constants (`FORMAT_BASE`, `PAGES`) so it
is one edit — but it cannot stay unset at publication.

### A2. Push the medallion correction upstream
Branch `centre-ayah-medallion-rings`, commit `fa8dd398`, in your
`quranpedia/quran-svg` clone. 2,879 files across all five mushafs. I did not push
to your upstream. Detail in §C1.

### A3. Should the production profile strip `data-eid` / `data-sig`?
Today both ship in **both** profiles (`FORMAT.md` §6.5). My recommendation is to
strip them in production:

- `data-eid` is explicitly **not stable across builds**. Shipping an unstable
  identifier invites consumers to key on it, and we then support it forever or
  break them.
- `data-sig` is a review-loop shape hash meaningless to a consumer.
- They are large: 598,407 and 598,392 occurrences.

Against: useful to anyone doing their own analysis, and removing later is a
breaking change while adding back is not.

### A4. The demo is 65 KiB over its size target
**965 KiB raw / 266 KiB gzipped**, against a 900 KiB target. All the growth is
scaffolding from the sections added tonight.

The only meaningful lever: **stop inlining the hero page.** It is 745 of the 965
KiB. Fetching page 42 like every other page takes the file to roughly **220 KiB
raw / 55 KiB gzipped** — a 4.4× cut — at the cost of the hero arriving one
round-trip after load. Nothing else is within an order of magnitude.

A judgement about first impressions, so it is yours.

### A5. Make `quranpedia/quran-svg` the home?
You suggested it, and I think yes. Our pages are the same pages plus structure,
pixel-identical, so they **replace** the published SVGs rather than sitting
beside them — measured cost **+33% raw, +22% gzip, +18% brotli** for the whole
semantic layer. The repo already has the `mushafs/<riwayah>/<edition>/` layout,
already carries `qiraahs_map.py` and the ayah-count dataset, and is already public
under CC0 with the KFGQPC grant.

**One condition, and it is not optional.** Our pixel gate proves each page
identical *against the artwork*. If the decomposed page replaces the artwork
file, the gate compares our output to itself and the proof becomes circular.
Before any release lands there, pin a pristine pre-decomposition baseline — a
tag, a branch, or a preserved `svg-plain/` — and re-point `audit_pixels` at it.

Lesser cautions: the repo is already ~2.5 GB across five mushafs, so release per
mushaf version rather than per build; and keeping the pipeline private is a
separate decision this one does not force.

### A6. `data-mark-part` — RESOLVED: the mark was merged, the attribute retired

Investigated on your instruction, and then you overruled the conclusion — rightly.

On p146 `6:141:14` (مُتَشَٰبِهࣰا) the ش three-dot cluster was drawn across **two
source paths**: one holding two of the dots, the other holding the third. My first
finding was that flagging the second as `data-mark-part` was correct. Your
instruction was that all three dots should be **one mark, not split**.

That is now what happens. The members' contours are folded into the primary's
path, so the cluster is a single element carrying `data-mark="three_dots"` with
three contours, and `data-mark-part` is **retired** — zero occurrences in the
corpus, removed from the specification.

**Why this merge is safe when three earlier ones were not.** The basmalah band,
the muʿānaqah and the ظ white loop all had **overlapping** contours, where
`fill-rule="evenodd"` cancels and fusing filled a counter solid. Three dots are
disjoint, so there is nothing to cancel — and `audit_pixels` proves it page by
page rather than the argument being taken on trust.

Verified: **604/604 pixel-identical**, and **436,627 logical marks — the same
count as before the merge**, which is what shows the change altered how a mark is
drawn and not how many marks exist.

If a part ever survives unmerged — its master in a different source path, which
the fold cannot cross — the emitter now prints a warning rather than emitting a
lone fragment that would look like an ordinary mark and inflate every count.

---

## B. Things that need your eye

- **p82 `4:25:49`** — the last per-word ink disagreement with MushafDatabase.
  Everything else reconciled to 99.968%.
- **Four paths on p17 with no `data-kind`** — unclassified ink, unexplained.
- **Qālūn: 11 ayah numerals with no ink** (pages 141, 381, 589 and variants). The
  ring is drawn, the number group is empty. A defect in the source artwork, not
  in our decomposition. Reported, not fixed.
- **12 duplicate ayah rings on every mushaf's opening spread.** The centring pass
  moved each duplicate by the same delta so they stay superimposed — moving one
  would have made an invisible duplicate visible. Deleting them deserves its own
  pass.

---

## C. What changed while you were away

### C1. Medallion ring centring — all five mushafs
**12,290 of 41,396 markers were off-centre; now 0.** duri 1,348 · hafs 377 ·
qalun 3,448 · shubah 1,350 · warsh 3,079.

Derived, not tabulated: measure the numeral's ink box and the ring's, shift the
ring so the centres coincide. **The numeral never moves** — it is the print's own
ink. The rule reproduces all 228 hand-measured deltas to 0.0000 and then fixes
12,062 more.

Cause: the Arabic-Indic digit **٥** has a different glyph origin, so any number
containing it drifts inside its ring. In Hafs, a number without a ٥ is misplaced
0.1% of the time; with a ٥, **37.7%**. Qālūn and Warsh differ — about half of all
their rings are loose regardless, a continuum with no empty band, so cruder
placement rather than the digit bug. Same fix serves both.

All 2,879 changed files verified byte-identical outside the ring's `translate()`.

### C2. Artwork pulled to `1b427fab`
Five commits, touching only pages 1-2 of each mushaf (the opening-spread surah
name, drawn twice then fixed) plus `tools/`. Hafs 1-2 rebuilt, full gate green.

### C3. `data-mark-family` is now a token list — **corrects a regression I caused**
Adding the `diacritic` family gave `tanwin_al_fath`/`tanwin_al_kasr`/`tanwin_al_damm` the value
`diacritic`, which silently **emptied the `tanwin` family** documented in §8.2.
`[data-mark-family="tanwin"]` matched nothing.

Both groupings are real, so the attribute carries both, like `class`:

    data-mark-family="diacritic tanwin"

Match with `~=`, not `=`. Single-family marks keep one token. `tanwin` is back to
**8,554** — the exact figure it had before, which is what tells us the old
semantics were restored rather than new ones invented.

### C4. Page identity on the root `<svg>`
Nine attributes per page, so a file downloaded alone is self-describing:
`data-mushaf`, `data-qiraah`, `data-riwayah`, `data-edition`,
`data-riwayah-name-ar`, `data-riwayah-name-en`, `data-ayah-numbering`,
`data-ayah-total`, `data-page`. Values from the vendored
`quranpedia/qiraahs-ayah-map` dataset. See `docs/MULTI-MUSHAF-DESIGN.md`.

### C5. A division opens once — **the bug you spotted**
`rubu_al_hizb 230 opens at 73:20` printed seven times because 73:20 spans seven lines and
every fragment carried `data-rubu-al-hizb-start`. Emitted on `data-part="1"` alone, the
attribute counts become the division counts exactly:

| | before | after | canonical |
|---|---:|---:|---:|
| juz | 72 | **30** | 30 |
| hizb | 140 | **60** | 60 |
| rubʿ | 669 | **240** | 240 |
| nisf | 168 | **60** | 60 |

That the part-1 subset already matched the canonical totals is what makes this a
correction rather than a preference.

It also exposed a documentation error: **`data-nisf-start` is a 1..60 ordinal**
through the mushaf, not the `1`/`2` half-index the table claimed — that is
`data-nisf` on the hizb rosette. Measured: 60 sites, 1 at 2:44 to 60 at 94:1.

### C6. Licensing — your instruction, implemented
`LICENSE` and `NOTICE.md` follow `quran-svg`'s model: CC0 for our own
contribution, the publishers' terms untouched for the ink. One line upstream
cannot state: since **no ink is altered** and every page is gate-verified
pixel-identical, the KFGQPC grant applies to the glyphs exactly as it does
upstream, and what is dedicated is the structure placed around them.

### C7. The shipping bundle
`tools/build_bundle.py` — one deterministic builder, byte-identical across runs.
Verified: 3,647 checksums, JSON Schema validation, and a cross-reference over all
604 pages confirming every index word id resolves to the right word group in
document order.

Measured: **457.0 MiB raw / 110.3 gzip / 69.7 brotli**. Showing page 42 costs
**126.5 KiB** brotli; searching the whole corpus **506.8 KiB**. Pre-compressed
`.br`/`.gz` ship beside each file for static hosts.

It found a real box bug: 72 ink paths on p17 and p144 carry their own
`transform`, which both retired proof-of-concept scripts ignored.

### C8. The JavaScript library
`docs/shipping/lib/` — zero dependencies, ES module plus a `<script>` build.
**228 assertions, zero failures**, verified in Chromium against six pages. One
shared reference-counted hit layer, so selection, hover, click and hit-testing
compose instead of fighting. Highlight bands are one path with `fill-rule`
`nonzero`.

### C9. The demo
18 sections, 17 live labs, each with a `plain JS` / `library` switch. The
cross-line drag bug was **mis-diagnosed in the notes, and by me** — cross-line
drags were never broken. A `mousedown` on already-selected text starts a native
drag-and-drop, freezing the old selection; it bites on the second attempt. Found
by measuring a drag step by step.

### C10. The `arabic-writer` skill
Installed globally, built on `kamalyaser31/arabic-guide` (MIT, derived from
Aramco's Arabic Editing Guide). **Arabeyes removed entirely at your instruction.**

A research agent fabricated a quotation during this work. It was caught on
verification and never reached the skill; the skill now records it in a
do-not-cite table so it cannot be reintroduced. That prompted a re-check of all
seven Microsoft quotes against the PDF — all verbatim, but the check found a real
flaw: Microsoft's maṣdar rule is scoped to **tooltips**, and an ellipsis had
quietly widened it to buttons. The wider scope is licensed by the §5.4.6 menu
table instead, now cited explicitly.

---

## D. Still running

The Arabic translation of the demo, against the now-frozen English page.

---

## E. Deferred deliberately

- **The word-boundary fix (88 overrides)** — not a blocker now the product is the
  SVGs; matters only if the artwork is re-pulled or Warsh comes into scope.
- **Tier C's 157 undecided cut rows** — invisible in production, no rule violated.
- **Tier E's 2,687 under-cut words** — matters for letter-level decomposition.
- **The shared structural cache** — dev speed only.
- **Merging basmalah / surah-name into one path** — tested and REJECTED: it breaks
  the ink. `fill-rule="evenodd"` makes overlapping contours cancel, filling the
  counter of the ح in ٱلرَّحْمَٰن as a black blob (228 pixels changed on p50).
  The group is already the semantic unit. Third appearance of the same trap:
  express "these pieces are one thing" through the GROUP, never by fusing
  geometry.
- **Cross-riwayah word alignment** — a real research problem; a half-correct
  mapping would be worse than none. See `docs/MULTI-MUSHAF-DESIGN.md` §3.
