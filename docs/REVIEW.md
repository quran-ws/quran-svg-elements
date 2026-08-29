# For Abdullah's review

Everything that needs your decision or your eye, in one place.
Started 2026-08-30 02:30, while you were away. Appended to, never rewritten.

Nothing in this file has been decided on your behalf. Where I acted, it says so
and why, and the action is reversible.

---

## A. Decisions only you can make

### A1. Licensing — blocking publication
The upstream artwork repo is CC0 with a King Fahd Complex grant. **This
repository has no LICENSE file**, and the library, the bundle and the demo all
need one before anything is published. Agents have been instructed throughout
never to choose a licence, never to copy one in, and never to state terms — so
every artefact currently carries a marked placeholder.

You need to decide: the SVG corpus, the JS library, and the documentation may
each want a different answer (data vs code vs prose).

### A2. Where the site lives
quran.ws, quranpedia.net, or GitHub Pages on the repo. This determines the base
URLs in the demo and the bundle README, so it is wired through one constant and
can be changed once — but it cannot stay unset at publication.

### A3. Push the medallion correction upstream
Branch `centre-ayah-medallion-rings`, commit `fa8dd398`, in your
`quranpedia/quran-svg` clone. 2,879 files across all five mushafs. I deliberately
did not push to your upstream. Details in §C1.

### A4. Should the production profile strip `data-eid` / `data-sig`?
Today both ship in **both** profiles (`FORMAT.md:439`). My recommendation is to
strip them in production:

- `data-eid` is explicitly **not stable across builds** — shipping an unstable
  identifier invites consumers to key on it, and we would then have to support
  it forever or break them.
- `data-sig` is a review-loop shape hash with no meaning to a consumer.
- Both are large: 598,407 and 598,392 occurrences.

Against: they are useful for anyone doing their own analysis, and removing them
later is a breaking change while adding them back is not.

The demo's `build.py` already strips them from its inlined page, so the demo is
currently *cleaner than what ships* — that inconsistency needs resolving either
way.

---

## B. Things that need your eye

### B1. p82 `4:25:49` — the last MushafDatabase ink difference
The one remaining per-word ink disagreement with the outside reference. Everything
else reconciled to 99.968%.

### B2. Four paths on p17 with no `data-kind`
Unclassified ink. Small, but unexplained.

### B3. Qālūn: 11 ayah numerals with no ink
Found during the medallion pass on pages 141, 381, 589 and their variants: the
ring is drawn, the number group is empty. This is a defect in the source artwork,
not in our decomposition. Reported, not fixed.

### B4. 12 duplicate ayah rings on the opening spread of every mushaf
Two identical rings drawn on top of each other. The centring pass moved every
copy by the same delta so they stay superimposed — moving one would have made an
invisible duplicate visible. Deleting the duplicates is worth its own pass.

---

## C. What I changed while you were away

### C1. Medallion ring centring — all five mushafs
**12,290 of 41,396 markers were off-centre; now 0.** douri 1,348 · hafs 377 ·
qalon 3,448 · shubah 1,350 · warsh 3,079.

The rule is derived, not tabulated: measure the numeral's ink box and the ring's,
shift the ring so the centres coincide. **The numeral never moves** — it is the
print's own ink. The derived rule reproduces all 228 deltas from the original
measured table to 0.0000 and then fixes 12,062 more.

Cause: the Arabic-Indic digit **٥** has a different glyph origin, so any number
containing it drifts inside its ring. In Hafs a number without a ٥ is misplaced
0.1% of the time; one with a ٥, **37.7%**. Qālūn and Warsh differ — about half of
all their rings are loose regardless, a continuum with no empty band, meaning
cruder placement rather than the digit bug. The same fix serves both.

Every one of the 2,879 changed files is byte-identical to its committed version
outside the ring's `translate(...)`, verified programmatically on all of them.

Gates after the change: **604/604 pixel-identical · bench 137 · taxonomy OK ·
sweep marks 0, intervals 1** (p350, previously examined by eye).

### C2. Artwork pulled to `1b427fab`
The clone was 5 commits behind. They touch only pages 1 and 2 of every mushaf
(the opening-spread surah name, drawn twice then fixed) plus `tools/`. Hafs 1-2
were rebuilt and the full gate re-run green.

### C3. `data-mark-family` is now a space-separated token list
**This corrects a regression I introduced earlier the same night.**

Adding the `diacritic` family gave `fathatan`, `kasratan` and `dammatan` the value
`diacritic`, which silently **emptied the `tanween` family** that `FORMAT.md` §8.2
documents. `[data-mark-family="tanween"]` returned nothing.

Both groupings are real — a fathatan is a vowel mark *and* a tanween — so the
attribute now carries both tokens, the way `class` does:

    data-mark-family="diacritic tanween"

Match with `[data-mark-family~="tanween"]`, not `=`. Single-family marks keep one
token, so `=` still works for `dots`, `waqf`, `sifr`, `sajdah` and `reading-sign`.

Nothing has shipped yet, so this is the right moment to fix it rather than
document a dead family.

---

## D. Still in flight when this was written

- **The demo** — grey-to-ink reveal, audio-synced recitation (al-Minshawi
  Murattal), hover-for-meaning, select-and-copy with ayah numbers, one selection
  band per line, the shared hit layer so sections compose, plain-JS/library
  toggles, a TOC replacing the crowded sticky nav.
- **The JS library** — zero-dependency ES module, 193 tests passing at last
  check, owns the overlay model so capabilities compose.
- **The shipping bundle** — layout, file formats and granularity being
  reconsidered, with measurements.
- **`arabic-writer` skill and the Arabic RTL demo** — skill built on
  `kamalyaser31/arabic-guide` (MIT, derived from Aramco's Arabic Editing Guide).
  Translation waits until the English demo settles.

---

## E. Deferred deliberately, with reasons

Carried from `SCHEDULE.md`; unchanged.

- **The word-boundary fix (88 overrides)** — not a blocker now that the product
  is the SVGs; matters only if the artwork is re-pulled or Warsh comes into scope.
- **Tier C's 157 undecided cut rows** — invisible in the production profile, no
  rule violated.
- **Tier E's 2,687 under-cut words** — matters for letter-level decomposition
  later.
- **The shared structural cache** — dev speed only.
- **Merging basmalah / surah-name into one path** — tested and REJECTED: it
  breaks the ink. `fill-rule="evenodd"` makes overlapping contours in one path
  cancel, filling the counter of the ح in ٱلرَّحْمَٰن as a black blob (228 pixels
  changed on p50). The group is already the semantic unit. Third appearance of the
  same trap: express "these pieces are one thing" through the GROUP, never by
  fusing geometry.
