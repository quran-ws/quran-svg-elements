# Override retirement audit — 2026-08-29

Goal: make the pipeline produce the SAME results without the hand-written
geometry overrides, by fixing causes, breaking nothing.

**Headline: `.cache/review/overrides.json` went 426 → 247 entries (152 → 114
pages). All 604 emitted pages are BYTE-IDENTICAL to the 426-entry build.**
Separately, `QSVG_SLASHFIX` was deleted — its only effect mushaf-wide was to
emit three body paths into the wrong `<g class="word">` on two pages.

---

## Method — why "byte-identical" and not "audit numbers"

Audit counts are the wrong acceptance test for this job: a word can lose a
letter with perfectly correct mark counts (CLAUDE.md's standing warning), so
"marks still 0" would have let silent re-ownership through. Every claim below
is proved by a **full-mushaf element-level diff**: build all 604 pages twice
and compare the emitted SVGs byte for byte. Byte identity is strictly stronger
than the required per-word multiset of `(word key, data-kind, data-mark,
d-string)` — it also pins ligature grouping, eids and ordering.

One new switch was needed to A/B an override subset:

- **`QSVG_OVR`** — path to an alternative overrides file. All four reader
  sites in `assign_words.py` now go through `_ovr_file()`. Unset, the path is
  the old hard-coded one and the build is byte-identical (verified).

Builds were written with `--out-dir` into private directories, because a
second agent was rebuilding `.cache/words-svg/hafs-kfqc` concurrently in the
same tree. That contamination was caught (p144 — a page with no overrides at
all — differed between two of my own builds) and every conclusion here was
re-derived in isolated directories.

### The three passes

1. **All-or-nothing per page.** Build all 604 with an EMPTY overrides file.
   114 of the 152 override pages changed; **38 pages did not** — every
   override on them is inert, 93 entries.
2. **Greedy per-entry minimisation** on the 114 live pages: drop one entry,
   rebuild the page, keep the drop only if the page stays byte-identical to
   the baseline build; repeat cumulatively. 447 page builds. **86 more
   entries fell.**
3. **Whole-set re-proof.** Build all 604 with the 247-entry keep set in
   isolated dirs: **0 pages differ.** Then write the reduced file and build
   again from it: **0 pages differ.**

---

## Classification of all 426

### Retired — 179 entries (42%)

`docs/defects/overrides-retired-2026-08-29.json` lists every one.

| how it died | entries |
|---|---|
| whole page inert (38 pages) | 93 |
| individually inert given the rest of its page | 86 |
| of which named (`\|mark`) | 11 |
| of which plain re-owns | 168 |

These are answers the pipeline now derives on its own. The largest single
blocks were **p350 (19)**, **p583 (11)**, **p254 (10)** — old body-partition
patches from before the DK line table and the taxonomy passes landed, plus
57 entries of one shape family (9.9 × 10.8/10.9 boxes) that the mark
machinery now names unaided. `tools/audit_overrides.py` had only ever seen
14 of these as dead (its key-presence test runs *after* the overrides have
already moved things, so a live-looking key can still be doing nothing).

### Kept — 247 entries

`docs/defects/overrides-kept-2026-08-29.json` carries every one with its
class and reason. Classified against a build made with **no** overrides, so
"what the override does" is measured, not guessed:

| family | entries | what the entry does |
|---|---|---|
| MOVE-only, body | 117 | re-owns a LETTER piece between words |
| MOVE-only, mark | 67 | re-owns a mark (fatha 20, dot 11, pause 9, kasra 6, …) |
| MOVE + RENAME | 33 | name inversion — the stroke arrives wearing the opposite name |
| CONTOUR-SPLIT | 14 | fused pair: one element, two touching strokes |
| RENAME-only | 10 | fused letter+mark, or a shape the table cannot separate |
| PIN-only | 6 | inert alone, load-bearing with the rest of the page |

By reason for keeping:

| class | entries |
|---|---|
| systemic cause not yet fixed (line-partition cascade) | 88 |
| no discriminating signal | 129 |
| artwork fact | 24 |
| guard | 6 |

---

## THE BIG FINDING — 88 of the 247 are not art facts, they are 14 line errors

The 247 are not 247 independent decisions. **88 of them are 14 whole-word
boundary errors**, each written out piece by piece.

Measured: for every override that re-owns ink, take the shift in word
position within the same ayah. The distribution is not a spread — it is
**almost entirely ±1** (115 at −1, 68 at +1, 26 across ayahs, 10 stragglers).
And those ±1 moves clump: 14 (page, ayah, direction) sites carry 3 to 13
entries each, every entry shifting the SAME way.

| page | ayah | shift | entries |
|---|---|---|---|
| 418 | 33:3 | −1 | 13 |
| 548 | 59:19 | −1 | 12 |
| 555 | 63:10 | −1 | 8 |
| 367 | 26:14 | −1 | 7 |
| 131 | 6:34 | −1 | 6 |
| 535 | 56:44 | −1 | 6 |
| 145 | 6:136 | +1 | 6 |
| 506 | 46:32 | +1 | 6 |
| 543 | 58:7 | +1 | 5 |
| 341 | 22:73 | +1 | 5 |
| 586 | 81:21 | +1 | 4 |
| 535 | 56:33 | −1 | 4 |
| 576 | 74:37 | −1 | 3 |
| 413 | 31:23 | −1 | 3 |

p548 59:19 reads as a textbook cascade — every word on the line draws the
next word's ink:

```
59:19:3 كَٱلَّذِينَ  ->  59:19:2 تَكُونُوا۟
59:19:4 نَسُوا۟      ->  59:19:3 كَٱلَّذِينَ
59:19:5 ٱللَّهَ      ->  59:19:4 نَسُوا۟
59:19:6 فَأَنسَىٰهُمْ ->  59:19:5 ٱللَّهَ
```

and the no-override build shows why: consecutive words have **overlapping
x-ranges** (word 3 at 24.4–87.0 against word 4 at 8.2–34.6). The partition
points on that line are all shifted, not the individual pieces.

**Corroboration from outside.** Three of these 14 sites — p131 6:34,
p341 22:73, p543 58:7 — are exactly three of the four entries in
`docs/defects/reference_confirmed.json`, the line errors MushafDatabase found
independently. The override cascades and the confirmed line errors are the
same defect seen from two directions.

**This is the highest-value follow-up in the file: one fix at the
word-boundary stage retires 88 overrides at once.** It is the standing
"line partition" queue item, and it now has 14 named, reproducible sites.

I did not write a rule for it. A boundary fix moves body ink on live pages;
under the standing constraint every such move must be enumerated and judged,
and the right judge for a boundary is the eye plus the DK layout DB, not a
threshold I could justify tonight.

---

## `QSVG_SLASHFIX` — measured, and DELETED

The handoff asked: make it work, tighten it, or retire it.

**Measurement.** Full-mushaf build with `QSVG_SLASHFIX=0` against the same
build with it on: **exactly 2 pages differ, p384 and p579.** Not one of the
name-inversion or fused-pair sites it was written for — those are all pinned
by overrides, so it never reaches them.

**What the 2 pages are.** On both, the *only* difference is body paths
landing in a different `<g class="word">`. Comparing the emitted grouping
with `assign_page`'s own `assignment` (which is IDENTICAL either way):

| page | ayah | emitted bodies per word, SLASHFIX on | with it off | the assignment says |
|---|---|---|---|---|
| 384 | 27:78 | 6/7/8 = **3/3/1** | 2/3/2 | 2/3/2 |
| 579 | 76:11 | 1/2 = **3/1** | 2/2 | 2/2 |

With SLASHFIX on, the emitted SVG contradicts the pipeline's own decision:
one body of `ٱلْعَلِيمُ` is emitted inside `وَهُوَ`'s group on p384, and one
body of `ٱللَّهُ` inside `فَوَقَىٰهُمُ`'s on p579. Mechanism: renaming a
slash early enough shifts a later pass's ink mass and flips `rewrite()`'s
"wrapper holding most of the ink" vote. **Mark and interval counts stayed 0
through all of it** — precisely the blind spot CLAUDE.md names.

**Verdict: deleted.** The three elements it was mis-emitting go back to the
word the pipeline assigned them to. Nothing else changes.

---

## Collateral changes

Full-mushaf element-level diff, final code + reduced overrides against the
426-entry baseline. Every changed element, enumerated:

| page | element | old state | new state | class | evidence |
|---|---|---|---|---|---|
| 384 | 1 body path, 27:78 | emitted in `وَهُوَ` (word 6) | emitted in `ٱلْعَزِيزُ` (word 7) | **(b) RIGHT** | matches `assignment`: word 6 holds 2 bodies, 7 holds 3, 8 holds 2 |
| 384 | 1 body path, 27:78 | emitted in `ٱلْعَزِيزُ` (word 7) | emitted in `ٱلْعَلِيمُ` (word 8) | **(b) RIGHT** | same |
| 579 | 1 body path, 76:11 | emitted in `فَوَقَىٰهُمُ` (word 1) | emitted in `ٱللَّهُ` (word 2) | **(b) RIGHT** | matches `assignment`: 2/2, not 3/1 |

**No class (a) and no class (c).** `docs/defects/collateral-for-eye-2026-08-29.json`
is therefore empty — nothing needs Abdullah's eye from this change.

Retiring the 179 overrides on its own changed **zero** elements on **zero**
pages; that is the whole point of the proof and it was verified twice, in
isolated output directories.

### One disclosure that is not a semantic change

p548 emits the same elements before and after, but two of them swap order:
in 59:19:5 a `fatha` (e258/e259) and a `shadda` exchange positions, and with
them their sequential `data-eid` labels. Same owner, same name, same
d-string, same pixels; the element multiset is identical.

It is **not** caused by the deletion in any semantic sense — reconstructing
the pre-deletion file and running it with `QSVG_SLASHFIX=0` (the same code
path as deletion) reproduces the OLD order, so the trigger is the source
file's length, not its behaviour. That means some ordering in the emitter is
sensitive to Python object `id()` values, which shift with unrelated edits.

**This is a real latent defect worth its own item:** `data-eid` is not stable
across builds, and the review platform hands eids to the applier. The
handoff's rule "always drift-check the picked eids' d-strings" is not a
precaution, it is load-bearing. I did not chase the exact line; the candidates
are the id-keyed structures around `assign_words.py:1968`, `2361`, `3255`,
`4069`.

---

## Overrides that could NOT be retired

Full list with per-entry reasons: `docs/defects/overrides-kept-2026-08-29.json`.

**1. Systemic cause not yet fixed — 88 entries, 14 sites.**
The line-partition cascades in the table above. Not artwork facts. Retire
them by fixing the word-boundary stage; they are the single largest prize
left in this file.

**2. Artwork fact — 24 entries.**
- **CONTOUR-SPLIT, 14.** Two strokes drawn touching share one element, so the
  pair counts once (p303 18:85:1, p552 61:6:25, p337 22:46:1, p298 18:44:7,
  p535 56:30:1 and 56:32, …). The contours are already separate — only their
  grouping changes, no ink is ever cut. A rule needs a proof that a
  two-contour slash element is a PAIR and not a letter with an `evenodd`
  hole; the p218 ظ-loop cost one wrong fix exactly there.
- **RENAME-only, 10.** Ink that is identical to another sign and can only be
  named, never derived: p341 22:76:4 and p324 21:28:4 (the hamza drawn
  connected to its alif — Abdullah's standing ruling "name it, never cut
  it"); p251 13:14:24 small-alef; p552 61:10:7 kasratan half; p585 80:39:2
  dammatan. `audit_overrides.py` reports the two hamzas as CONTRADICTS only
  because its `CHARS` table has no entry for the pre-composed `أ`.

**3. No discriminating signal — 129 entries.**
Isolated body re-owns (not part of a cascade), mark re-owns, and the 33
name-inversion pairs. For every one of these the two candidate words are
adjacent, both plausible on geometry, and the text budget alone does not say
which. The project has already measured and rejected letting the width prior
carry a body move (`QSVG_WDECIDE`, off by default: "buys nothing, breaks
words visibly"), and driving repairs from the interval audit (detector, not
corrector). No new empty-band quantity was found for them.

**4. Guard — 6 entries.**
p407, p418 ×2, p30, p590, p437. Individually they change nothing against a
no-override build, but removing them changes the page, because they pin a
piece against a later mover that only becomes reachable once the other
overrides on that page have run.

---

## Rules tried and abandoned

- **A rule for the cascade family.** Abandoned deliberately, not for lack of
  a signal — the signal is strong (overlapping word x-ranges, and MushafDatabase
  agreeing on three of the sites). Abandoned because a boundary rule moves body
  ink on live pages and every such move has to be judged one by one; that is a
  phase with the eye in the loop, not a threshold.
- **Reviving SLASHFIX.** Its Rule A (position-impossible rename) and Rule B
  (side-by-side contour split) never fire on any unpinned site today, so
  tightening it could not be measured against anything. Retiring it cost
  nothing and fixed two pages.

---

## Gate numbers

Measured on the final code with the reduced overrides file (sweep
`.cache/sweeps/r24`, baseline `.cache/sweeps/r22`/`r23`):

| gate | before | after |
|---|---|---|
| `audit_pixels 1 604` | 0 failures | **0 failures**, every page pixel-identical |
| `audit_taxonomy` | OK | **OK** — 35 mark names, 3 muanaqah pairs, 8 rare sites |
| `bench.py` | SCORE 137, no failures | **SCORE 137, FAILURES none**, pixelfail 0, budget-mismatch 0/2706 |
| mark flags (sweep, 604 pages) | 0 | **0** |
| open interval records | 1 (p350, pre-existing) | **1 (p350, pre-existing)** |
| overrides | 426 on 152 pages | **247 on 114 pages** |
| pages differing from the 426-entry build | — | **0** (except the 3 SLASHFIX elements above) |
