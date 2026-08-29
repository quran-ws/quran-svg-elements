# New detector dimensions — 2026-08-29

Written after a full-mushaf audit hunt. Starting position: the mark-count
audit, the interval/territory audit, `audit_topmost`, `audit_slashpos` and
`audit_crossline` were **all at zero over 604 pages**, and pixel identity was
proven 604/604. So nothing here comes from tightening an existing threshold —
every idea below is a dimension nothing in the repo measured before.

Everything was measured over **all 604 pages / 77,432 words / 781,732 contour
boxes** by capturing the pipeline's own assignment (spying on `aw.rewrite`),
never by parsing the emitted SVG.

> **Provenance caveat — read before quoting a number.** Every figure here was
> measured between 04:00 and 04:35 on 2026-08-29. A **concurrent session was
> editing `tools/assign_words.py` at the same time** (its mtime moved to 04:36,
> and `tools/build_remaining.py`, `.cache/review/explained.json` and
> `docs/defects/ligatures.json` all moved at 04:16). I changed none of those.
> The counts below are therefore true of the build as it stood during the run,
> not necessarily of `HEAD` now. All four detectors are cheap (≈2.5 min each) —
> **re-run them before acting on a count**, and re-check the empty bands with
> `--hist`, which is exactly why that flag prints the distribution.

Headline, per Abdullah's mid-task priority: **the stolen BODY piece**. Four of
the six sections below are about body ink ownership, and two of the three
rejected ideas were rejected *for* it. The result is one detector that finds
body theft with high precision on repeated word-forms, one proof-class
detector for null ink, one proof-class detector for intra-word ligature
grouping, one proof-class detector for a mark shape/name swap — and an honest
account of the body thefts that **none of them can see**.

---

## Summary

| detector | dimension | empty band? | flags / 604 pages | class |
|---|---|---|---|---|
| `audit_nullink.py` | a contour that draws no ink | **YES**, 0.0442 → 0.7322 (17x) | **47** (32 whole body elements, 14 mark sub-contours) | PROOF |
| `audit_ligorder.py` | intra-word ligature geometry, 2 laws | **YES**, 3.24 → 24.54 and 4.83 → 13.95 | **2** | PROOF |
| `audit_sigfamily.py` | one outline, one mark family | **YES**, the whole open interval | **2** (one swap) | PROOF |
| `audit_formshape.py` | the same word-form drawn differently here | no (integer deviation) | **27** (8 CONTOURS, 19 RUNS, 3 PAIRED) | PRIOR, graded |
| — body territory (marks→bodies) | a body piece in another word's span | **NO** | rejected | — |
| — per-form ink AREA | word too heavy for its form | **NO** | rejected | — |
| — bodyless *ligature* | a group whose text names letters holds no ink | **NO** | rejected (713, mostly weld artefacts) | — |

Total genuinely new candidate defects: **78**, of which **51 are proof-class**
and, at the time of writing, **none of them appears in the r22 sweep**
(cross-checked: r22 carries exactly 1 flagged word-key in the whole mushaf).

---

## 1. `audit_nullink.py` — ink that is not ink · KEPT · PROOF · 47 flags

**What I measured.** The transformed drawn area of every contour of every
element, all 604 pages: 781,732 boxes.

**Distribution, sorted ascending.**

```
0.00048 .. 0.0442     47 contours
------------------- EMPTY BAND, a factor of 17 -------------------
0.7322 .. 1.2148 (p0.001) .. 17.50 (median) .. 805 (p0.99) .. up
                     781,685 contours
```

Nothing at all between 0.0442 and 0.7322. Measured over **body** contours
alone the band is wider still — 0.0443 → 1.578, a factor of 35; the marks
supply the 0.73 lower edge. Threshold put inside the band at **0.5**, the same
constant `QSVG_NULLMARK` already uses for whole elements.

**Why it was invisible.** `QSVG_NULLMARK` retires a degenerate *mark element*.
Nothing retires a degenerate *body* element, and nothing looks *inside* a
multi-contour mark. A null blob therefore still counts as a letter piece
against the joining-rule budget, and it paints no pixel, so `audit_pixels`
cannot object.

**Result.** 47 flags on 38 pages: 33 body contours (**32 of them the whole
element** — a `<g class="ligature">` piece drawing nothing) and 14 sub-contours
of a real 2-contour mark, which is exactly why the element-level test missed
them.

**Spot-checked by ink.**

- **p536 56:61:7 `مَا`** — a body element whose only contour is
  `[128.047, 195.767] → [128.066, 195.795]`: **0.019 × 0.028 units**. The
  word's real body sits at `[127.5, 195.8, 138.0, 211.1]`. The null piece is a
  second `<path>` inside the same ligature. Verified: it is why `مَا` counts 3
  body contours on this page where its other 712 occurrences count 2.
- **p2 2:4:4 `أُنزِلَ`** — null contour area 0.00364 in seg `نز`. The same
  word at 2:4:7 on the same page has one too (0.00444). Both are whole
  elements.
- **p346 23:61:6 `لَهَا`** — a *mark* case: the `fatha` element has two
  contours, one real and one of area 0.00060. Six of the fourteen mark cases
  are `لَهَا`/`وَلَهَا` fathas (p262, p346 twice, p370, p453, p590), which is a
  strong hint they share one upstream cause rather than being fourteen
  accidents.

**Caveat, stated honestly:** a null contour changes no pixel, so this is a
*bookkeeping* defect, not a visible one. Its cost is that it inflates the piece
count that `segment_word()`'s budget and `score_both.py`'s piece-surplus metric
are compared against. It was also responsible for **33 of the 712** raw
outliers in §4, which is why §4 filters it out first.

---

## 2. `audit_ligorder.py` — intra-word ligature geometry · KEPT · PROOF · 2 flags

Every position law in the repo is **inter-word** (`audit_intervals`,
`audit_strayink`, `audit_crossband`, `audit_crossline`, `audit_topmost`,
`audit_slashpos`). A word can hold exactly its own ink, exactly its own marks,
and still share that ink out among **its own** `<g class="ligature">` groups
wrongly. No count moves, no pixel moves, and the emitted `data-text` lies.

Two laws, both purely geometric, both with an empty band.

### LAW 1 — right-to-left order

Groups are numbered in text order, so group *i+1* must not draw ink to the
**right** of where group *i* ends. Overshoot = `right_edge(i+1) − right_edge(i)`
over **78,718** consecutive group pairs:

```
-60.7 (p99.9) ....... -8.2 (median) ....... -2.5 (p1)   negative: fine
 0.00 ..  3.24    60 pairs   a following kaf/ain/haa arm or a kashida
                             reaching back over a preceding non-joining
                             letter — real calligraphy
--------- EMPTY BAND, 3.24 → 24.54, twenty-one units ---------
24.54             1 pair
```

### LAW 2 — contiguity

A group is by construction one *joined* run, so its body pieces must touch.
Largest hole inside a group, over the 855 groups holding two or more
x-disjoint body pieces:

```
 0.06 ..  4.83   854 groups   the ordinary hairline inside one run
--------- EMPTY BAND, 4.83 → 13.95, nine units ---------
13.95             1 group
```

Threshold for both: **8.0 units** — inside both bands, 2.5x clear of the
largest legitimate value on law 1, 1.7x on law 2, and about two thirds of a
letter body's height, so no pen overhang reaches it.

**Both hits verified by reading the ink.**

- **p366 25:68:20 `ذَٰلِكَ` (LAW 1)** — group 0 is `ذ` and holds a body at
  `[257.0, 261.9]`. Group 1 is `لك` and holds two bodies: the main run
  `[240.1, 275.7]` **and a piece at `[280.6, 286.4]` with a `dot` directly
  above it at `[280.7, 291.6]`**. A ذ has a dot; the piece at 257.0 has none.
  So the **real ذ** (rightmost, dotted) is filed under `data-text="لك"`, and a
  piece of the لك run is filed under `data-text="ذ"`. The word's mark counts
  are perfect and its total ink is correct — only the grouping is scrambled.
- **p585 80:38:1 `وُجُوهࣱ` (LAW 2)** — group 0 is `و` and holds `[39.60, 44.07]`
  **and** `[58.02, 67.83]`, a 13.95-unit hole between them. Group 1 is `جوه`
  and spans `[39.9, 62.5]` — so group 0's left piece sits *inside* group 1's
  run. The final ه of وجوه is grouped with the initial و.

---

## 3. `audit_sigfamily.py` — one outline, one mark family · KEPT · PROOF · 2 flags

`.cache/marks/labels.json` is the forward map, signature → label. Nobody had
run it **backwards** as an outlier hunt.

The pipeline legitimately gives one signature several *names* — fatha / kasra /
fathatan / kasratan are one stroke named by position, and a dot cluster's
members share the single-dot outline. What it must never give one signature is
two **families**:

```
slash = fatha | kasra | fathatan | kasratan
damma = damma | dammatan
dots  = dot | two-dots | three-dots | muanaqah
everything else is its own family
```

**Measured**, 436,383 mark elements, 2,142 distinct signatures. Of the 90
signatures seen 50+ times, the share of occurrences outside their own dominant
family:

```
share = 0.000000   88 of 90 signatures   PERFECT
--------- EMPTY BAND: the entire open interval ---------
share = 0.000018   sig d7a8b5e19121fbe4  (slash outline, 54,276x) once "two-dots"
share = 0.000040   sig a316a3b8eb2508b0  (two-dots outline, 24,854x) once "fatha"
```

There is no threshold to tune. Every other outline in the book is 100.000% one
family.

**The one hit, verified by ink — and it is a clean swap.** Both violations are
on **p337 22:46:8 `يَعْقِلُونَ`**:

| element | outline | outline used elsewhere | named | drawn at y |
|---|---|---|---|---|
| `[265.6, 483.9, 271.8, 487.2]` | `d7a8b5e1…` | slash, 54,276x | **two-dots** | 483.9 — **above** the letters |
| `[268.1, 499.1, 272.6, 501.9]` | `a316a3b8…` | two-dots, 24,854x | **fatha** | 499.1 — **below** the letters |

The ya's two dots belong below and the fatha above; both the shape and the
position say the two names are exchanged. It is **mark-count neutral** — one
fatha and one two-dots either way — so no counting audit can ever see it, and
`audit_slashpos` cannot either, because it only reasons about marks *already
named* as slashes.

---

## 4. `audit_formshape.py` — the same word, drawn differently here · KEPT · PRIOR · 27 flags

**This is the body-theft detector.** A stolen letter piece leaves every mark
count perfect, sits exactly where it always sat (so the territory audits are
silent), and overlaps its victim (so `audit_width` stays in range). The one
thing it *must* change is the ink topology of the two words involved.

Two invariants, both computed per word-form across all its occurrences, with
null contours (§1) removed first:

- **CONTOURS** — separate closed outlines the word's bodies draw, counters
  included.
- **RUNS** — x-disjoint ink clusters.

**Measured**, 21,201 distinct forms; 458 seen 20+ times, 36,082 occurrences:

```
CONTOURS   419 of 458 forms (91.5%) draw ONE count always
           deviation:  -1: 454    0: 35,391    +1: 237   (nothing beyond ±1)
RUNS       300 of 458 forms (65.5%) draw ONE count always
           deviation:  -2: 16   -1: 2,925    0: 32,780   +1: 361

minority-count k (CONTOURS): k=1: 8  k=2: 4  k=3: 3  k=4: 4  k=5: 5  k=6: 18 …
share k/N of a k=1 hit: 0.0014 … 0.0455, then a 0.030 gap to 0.0759
```

**There is NO empty band in the integer deviation.** This is a strong prior,
not a proof, and the tool says so. The band that exists is in *rarity* and is
shallow, so the rule takes its conservative end: `MIN_N=20` and `k==1` — the
form is drawn 20+ times and exactly once differently. That leaves **27 flags**
(8 CONTOURS + 19 RUNS) out of 712 raw outliers.

**Second signal.** A stolen piece leaves a complementary hole: the thief is +1
and the victim −1. A flag with a neighbour on the page deviating the opposite
way is promoted to **PAIRED** — 3 of the 27.

### The find that justifies the whole detector: the p384 theft chain

`وَهُوَ ٱلْعَزِيزُ ٱلْعَلِيمُ` (27:78) — read by ink, element by element:

| word | should hold | actually holds |
|---|---|---|
| `وَهُوَ` | one run, 6 contours | 7 contours — **plus a 2.4 × 15.0 stroke at `[251.5, 264.9]`**, an alif, and وهو has no alif |
| `ٱلْعَزِيزُ` | group 0 = `ا`, then `لعز`, `يز` | **group 0 holds NO body.** Its own alif is next door in `وَهُوَ`. Inside group `يز` sits a 2.9 × 15.8 stroke at `[215.1, 218.1]` — at the word's far LEFT edge, where the *next* word begins |
| `ٱلْعَلِيمُ` | 3 contours, 2 runs | 2 contours, 1 run — **its alif is gone**, held by ٱلْعَزِيزُ |

Each word has taken its left neighbour's alif. **`ٱلْعَزِيزُ`, the middle link,
is invisible on the CONTOURS axis** — it lost one and gained one, net zero.
Only the RUNS axis reports it (1 run where its other 45 occurrences draw 2).
That is precisely why both axes are kept.

### Other flags I read by ink

- **p579 76:11:2 `ٱللَّهُ`** (2 contours vs 3, in 660 occurrences) — **REAL.**
  Its ligature group 0, seg `ا`, holds only a `wasla` mark and **no body at
  all**. The previous word `فَوَقَىٰهُمُ` holds an extra body at
  `[42.489, 122.963, 45.216, 137.930]` — a 2.7 × 15.0 stroke, an alif — and
  `ٱللَّهُ`'s own group-0 atom declares its x-range as `[42.489, 45.216]`,
  exactly that box. The atom knows where its alif is; the element went to the
  neighbour. Textbook stolen body piece, and the highest-confidence new defect
  in this document.
- **p435 35:6:3 `لَكُمْ`** (1 contour vs 2, in 143 occurrences) — plausible,
  needs eyes. One body element, `[81.3, 83.6, 96.4, 116.9]`: **33.3 units
  tall**, against 21.9 for `ٱلشَّيْطَٰنَ` beside it on the same line. The
  meem's counter is missing.
- **p579 76:19:2 `عَلَيْهِمْ`** and **p579 76:15:2 `عَلَيْهِم`** (both 3 vs 4)
  — **downgraded by me to REVIEW.** Two occurrences of the same letters on the
  *same page* both deviating the same way is more consistent with a page-local
  glyph variant than with two independent defects. Do not treat as certain.

### The RUNS axis has a measured false-positive mode — stated plainly

I spot-checked four RUNS hits by ink. **Three were artefacts, one was real:**

- p556 64:3:3 `وَٱلْأَرْضَ` (1 run vs 3) — artefact. Every piece merely
  *overlaps* its neighbour on this tightly-set line: `[119.8,122.5]`,
  `[118.8,128.7]`, `[108.0,118.4]`, `[100.5,109.8]`, `[88.6,105.9]`.
- p271 16:38:16 `ٱلنَّاسِ` (2 vs 3) — artefact. The `س` at `[108.2,124.7]`
  touches `لنا` at `[125.2,143.7]`.
- p604 113:3:1 `وَمِن` (2 vs 1) — artefact, the opposite way: a 1.3-unit gap
  opens where the two normally touch.
- p384 27:78:7 `ٱلْعَزِيزُ` (1 vs 2) — **real**, as above.

Cause: how tightly a line is set decides whether two letter boxes touch, and
the 0.6-unit merge slack cannot know that. So **a bare RUNS hapax is graded
REVIEW, never a claim**; only a complementary neighbour lifts it. Roughly one
in four is expected to be real.

### The blind spot, measured — do not read a clean run as an absent defect

I calibrated against the three body thefts Abdullah confirmed by eye. **This
detector cannot see any of them**, and the reason is structural:

| case | form occurrences in the whole mushaf | seen? |
|---|---|---|
| p71 `غَالِبَ` / `بَعْدِهِۦۗ` | 2 and 2 | no — below `MIN_N` |
| p413 `يَحْزُنكَ` | 5 | no — below `MIN_N` |
| p546 `وَمَآ` | (form present, no deviation) | no |

The method needs the form **repeated**. It covers the common vocabulary, which
is most of the book *by occurrence* and almost none of it *by form*. I also
tried pushing the reference down to the **ligature** level, where `ا` has
29,815 occurrences and `ه` has 402 — far more statistical power. It does not
help these cases either (`بَعْدِهِۦۗ`'s groups `بعد` and `ه` both sit exactly
on their modes), and it is much noisier: only 44.1% of seg-texts seen 50+ times
are constant, giving 104 hapaxes. **Not shipped** — it would be a worse
detector wearing a bigger number.

---

## 5. Ideas measured and REJECTED

These are as much of the result as the kept ones.

### 5a. Body territory — the interval audit, extended from marks to bodies

The strongest-looking idea, and it fails. `audit_intervals` iterates only over
`kind == "mark"`, so the obvious move is to ask the same question of body ink:
*is a word's body piece drawn inside another word's exclusive span?*

Measured over all 604 pages, restricted to pieces sitting outside their own
word's remaining mass: **885 such pieces**. Penetration depth into the foreign
word:

```
33.12  26.10  24.66  |  6.04  5.64  5.62  5.19  5.05  4.64  4.60 …  0.02 (p99)
```

An apparent band at 24.66 → 6.04. **All three top hits are false.** They are
`ٱلرَّحِيمِ` inside `ٱلرَّحْمَٰنِ` — p1 1:1:4, p379 27:30:8, p548 59:22:13 —
and in the basmalah those two words *genuinely interleave* in x. Reading p548:
`ٱلرَّحْمَٰنُ` spans 241.9–313.9 and `ٱلرَّحِيمُ` spans 225.6–276.4; the
"penetrating" 2.9 × 15.8 stroke at `[273.5, 276.4]` is `ٱلرَّحِيمُ`'s **own
alif**, drawn exactly where the print draws it.

I then added the obvious second signal — require that the two words are **not**
mutually nested — and re-measured. 781 pieces, depths
`6.04, 5.62, 5.05, 4.17, 3.84, 3.76 …`: **no band at all**, a smooth decay, and
the whole tail is one legitimate pattern — the wasla-alif of `ٱل…` tucking
under the previous word's final ر/ز/م (`وَبَشِّرِ ٱلْمُؤْمِنِينَ`,
`نَحْشُرُ ٱلْمُتَّقِينَ`, `ذِكْرِ ٱللَّهِ`, and about fifty more of the same
shape). **Rejected.** The mark version of this audit works because a mark is
small and its word's territory is well defined; body ink is large, kerned, and
routinely overlapping, so the territory idea has no purchase.

### 5b. Per-form ink AREA — "a word holding a foreign piece is too heavy"

Measured: total body ink area per occurrence, robust z-score against the form's
own median (MAD-normalised), 36,082 occurrences of forms seen 20+ times.

**Rejected outright.** The top of the list is z = 29,077 for `مِن` on p498:
area 536 against a median of 191. The next nineteen entries are all `مِن`,
`مِنْ`, `مِّن`, `مَن`, `مِّنَ`. The cause is **justification**: the print sets
a line by stretching short words, so the same word legitimately spans a **2.8x
area range**, while MAD is near zero because most occurrences are identical.
Area is not stretch-invariant, which is exactly why `audit_formshape` counts
contours and runs instead — a kashida stretches a run, it does not open a hole.

### 5c. Body-piece detachment gap

Abdullah's suggestion: measure, for every body element, the distance to the
nearest other body element of the **same** word, and look for a band.

Measured over 137,596 body elements in multi-piece words. Percentiles
`6.87 (max) / 3.90 (p0.1) / 2.95 (p1) / 1.13 (p25) / 0.00 (median)`.
**No band whatsoever** — a smooth decay. The entire top of the list is one
legitimate form: `ذَٰلِكَ`'s ذ, which is genuinely detached from the لك by
about 4.7 units in every one of its hundreds of occurrences, plus
`إِۦلَٰفِهِمْ`, `سَوْءَٰتِهِمَا`, `مَّعْدُودَٰتࣲ`. **Rejected as a raw
quantity.** Detachment is a property of the *letters*, not of ownership; the
useful version of it is per-form, which is §4.

### 5d. Bodyless *ligature* group

A `<g class="ligature">` whose `data-text` names letters but which holds no
body element at all. `audit_bodyless` does this per **word**; per group it is
much finer, and it is how the p579 `ٱللَّهُ` theft shows itself.

Measured: **713** of 156,863 groups. **Rejected as a standalone detector** —
the great majority are `align_segs_atoms` artefacts, not defects. The dominant
pattern is seg `ا` inside words like `وَإِذَا`, `ءَامَنَّا`, `قَالُوا۟`, where
the alif welds into a neighbouring run and the segment-to-atom alignment hands
the `ا` segment an atom that carries only marks. A 713-flag list that is mostly
noise is worse than nothing. It survives *inside* §4 as corroboration for a
word already flagged on the contour axis, which is the only place it carries
weight.

### 5e. Per-ligature mark inventory vs the segment's expected marks

`atom["seg"]["marks"]` is text-derived, so comparing a group's held marks
against it looked like a clean route to "a mark of the right name in the wrong
place within its own word".

Measured: **28,055 of 129,648 groups disagree (22%)**; restricted to words
whose *word-level* mark multiset is correct, still **12,623 words (16%)**.
**Rejected.** Two reasons, and the first is fatal: `label_marks()` names marks
*from* the group's merged seg list, so for anything the late movers did not
touch the comparison is **circular**. What is left is dominated by
`align_segs_atoms` merge imprecision — e.g. p1 1:1:4 `ٱلرَّحِيمِ`, where the
shadda and fatha of the ر are filed under group `ا`. A 16% flag rate is not a
detector. The non-circular version of this question is geometric, and that is
§2, which does have empty bands.

### 5f. Runs vs ligature-groups-holding-ink

Count a word's x-disjoint body runs and compare with how many ligature groups
actually hold body ink; `runs > groups` means one group holds two runs while
another holds none. Measured: `runs > groups` in **310 of 77,432 words**, but
the list is led by `وَإِذَا`, `ءَامَنَّا`, `هَٰذِهِ` — the same weld artefact
as §5d, not theft. **Rejected**; kept only as the intuition behind §2 LAW 2,
which asks the same question with a distance and does have a band.

---

## 6. Ranked shortlist for Abdullah's eye

Ranked by my confidence. Everything here I read element-by-element myself.

| # | page | word key | word | what is wrong | confidence |
|---|---|---|---|---|---|
| 1 | **384** | 27:78:6 / 7 / 8 | `وَهُوَ` `ٱلْعَزِيزُ` `ٱلْعَلِيمُ` | **A theft chain.** Each word holds its left neighbour's alif. `ٱلْعَزِيزُ`'s group 0 (`ا`) is empty while a 2.9 × 15.8 alif sits at its far-left edge inside group `يز`; `وَهُوَ` holds a 2.4 × 15.0 alif it has no letter for; `ٱلْعَلِيمُ` has lost its alif. | **very high** |
| 2 | **579** | 76:11:2 | `ٱللَّهُ` | **Its alif is held by `فَوَقَىٰهُمُ`.** Group 0 holds only the wasla, no body; the neighbour holds a 2.7 × 15.0 stroke at exactly the x-range group 0 declares (`[42.489, 45.216]`). | **very high** |
| 3 | **337** | 22:46:8 | `يَعْقِلُونَ` | **fatha and two-dots have swapped names.** The two-dots outline (24,854 uses) is called `fatha` and drawn *below*; the slash outline (54,276 uses) is called `two-dots` and drawn *above*. Count-neutral, so nothing else can see it. | **very high** |
| 4 | **366** | 25:68:20 | `ذَٰلِكَ` | **Ligature groups scrambled.** The real dotted ذ at `[280.6, 286.4]` is filed under `data-text="لك"`; a piece of the لك run is filed under `data-text="ذ"`. | **very high** |
| 5 | **585** | 80:38:1 | `وُجُوهࣱ` | **The final ه is grouped with the initial و.** Group `و` holds `[39.6, 44.1]` and `[58.0, 67.8]` with a 13.95-unit hole between; group `جوه` spans `[39.9, 62.5]` in between. | **very high** |
| 6 | **536** | 56:61:7 | `مَا` | A body element of area **0.00052** (0.019 × 0.028 units) counted as a letter piece. Draws nothing. | **certain, but cosmetic** |
| 7 | — | — | 46 more | The rest of `audit_nullink` — 31 further null body elements and 14 null mark contours. Six of the mark cases are `لَهَا`-family fathas (p262, p346 ×2, p370, p453, p590): likely one cause, not six. | **certain, but cosmetic** |
| 8 | **435** | 35:6:3 | `لَكُمْ` | 1 body contour where its other 142 occurrences draw 2 — the meem's counter is missing. The element is 33.3 units tall against 21.9 for its neighbour. | medium — needs eyes |
| 9 | **324** | 21:30:18 | `يُؤْمِنُونَ` | 7 contours vs 6 (85 occurrences) **and** 2 runs vs 1 — flagged on both axes independently. | medium |
| 10 | **203** | 9:102:6 | `صَٰلِحࣰا` | 4 contours vs 3, in a form whose spread is already split `3:14 / 2:13` — weaker than it looks. | low–medium |
| 11 | **579** | 76:19:2 + 76:15:2 | `عَلَيْهِمْ` `عَلَيْهِم` | Both 3 contours vs 4. Two same-letter words on the **same page** deviating the same way — I judge this a page-local glyph variant, not two defects. Listed so it is not re-found and mis-claimed. | **low — probably not a defect** |

---

## 7. How to run

```bash
cd ~/Dev/github.com/AbdullahObaid/quran-svg-work && export QSVG_ROOT=$PWD
python3 tools/audit_nullink.py    1 604 32 --hist   # → .cache/nullink.json
python3 tools/audit_ligorder.py   1 604 32 --hist   # → .cache/ligorder.json
python3 tools/audit_sigfamily.py  1 604 32          # → .cache/sigfamily.json
python3 tools/audit_formshape.py  1 604 32 --hist   # → .cache/formshape.json
```

Each is about 2.5 minutes at 32 workers. All four are **read-only** — they
capture `aw.rewrite` and never write the SVG cache. `audit_formshape` and
`audit_sigfamily` build their reference distribution from the pages scanned and
need the **full mushaf**; `audit_formshape` refuses a range under 200 pages
without `--force`.

`--hist` re-prints the distribution and locates the empty band at run time, so
a future change to the pipeline that moves a band shows up immediately rather
than silently invalidating the thresholds written into these comments.

---

## 8. What I did not get to

- **`audit_ligatures.py` soundness** — investigated separately; see the note
  appended by that review. Its `data-text`-holds-its-ink question overlaps §2,
  and §2 should be read as answering the *geometric* half of it only.
- **Cross-checking DigitalKhatt's layout DB or MushafDatabase at the
  LIGATURE level.** Both were compared at word level long ago (99.994% on line
  placement, statistically even on word metrics) but neither has ever been
  asked where the *cut inside a word* falls. That is the largest untouched
  outside-evidence dimension left, and it is the one that could see the body
  thefts §4 is structurally blind to, since it needs no repetition.
- **Reading order of elements within the emitted SVG** vs text order — I built
  the geometric version (§2) but not the emitted-order version.
- **Ayah-level and line-level invariants** (words per ayah, ayah-marker
  placement, ligature counts per line) — not measured at all.
