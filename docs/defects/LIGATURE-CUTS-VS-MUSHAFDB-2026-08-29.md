# Our ligature cut vs MushafDatabase's — 2026-08-29

**Three real thefts found, five words, on p58, p324 and p455.** They are the
first stolen body pieces found by anything other than Abdullah's eye. Four of
the five words are clean in every existing audit; the fifth, p58
`وَٱلْإِنجِيلُ`, is one of the 195 rows `audit_ligatures.py` calls `empty` —
a class that cannot say whether the ink went to the neighbouring GROUP or to the
neighbouring WORD, and which is 34-to-1 the former. This comparison is what
separates them. Two disagreements go against
MushafDatabase. Everything else is one systematic emitter defect (2,687 words)
plus 157 cases neither side's rules can settle.

Tools: `tools/audit_ligcuts.py` (the comparison),
`tools/build_ligcuts_page.py` (the visual page).
Output: `docs/defects/ligature_cuts.json`, `docs/defects/ligature_cuts.html`.

```
python3 tools/audit_ligcuts.py 1 604 --jobs 32 --dist     # ~1 min on 32 workers
python3 tools/audit_ligcuts.py --proof                    # the registration proof
python3 tools/build_ligcuts_page.py
```

---

## What was compared, and how the two sides were made comparable

MushafDatabase publishes the same KFGQPC artwork with, per word, one
`<g id="md-ligature-…">` per run of ink, each holding one
`<path data-type="text" data-text="…">` naming that run's letters. That is
exactly our `<g class="ligature" data-text="…">`. Nobody had compared at that
level before; `audit_reference.py` only used their line numbers.

### Word alignment

Reused from `audit_reference.py`: the reference counts a conjunction waw
(`data-waw-alatf`) and a standalone stop sign as words of their own, so both are
folded back into the neighbour that owns them in our numbering before positions
are compared.

### Letter folding — and a correction to CLAUDE.md

The two sources encode the same letter with different carriers: ٱ أ إ آ for ا,
ؤ for و, ئ and ى for ي, plus tatweel. Folding those to their bases before
comparing is what makes the comparison possible.

CLAUDE.md says `audit_reference.py` is blind to "words the two sources split
differently (~12%)". **That 12% is an encoding artefact, not a split
difference.** Measured here over all 604 pages, after folding:

| | words |
|---|---|
| aligned by (surah, ayah, position) | 77,431 |
| **excluded — the two sides really do spell/split the word differently** | **9** |
| only in the reference | 1 |
| only ours | 1 |
| **comparable** | **77,422** |

The nine are three sites, not nine independent ones:

* **p11 2:72:4** `فَٱدَّٰرَٰءۡتُمۡ` vs our `فَٱدَّٰرَْٰٔتُمْ` — a hamza-above
  encoded two ways. One word.
* **p262 15:7** — they write `لَّوۡمَا` as ONE word, we write `لَّوْ` + `مَا`.
  Every position in the ayah shifts by one, so seven words plus one only-ours
  fall out of the comparison. This is the same family as the `بعد/ما` split
  recorded in CLAUDE.md.
* **p451 37:130** — `إِلْ يَاسِينَ` is one word for us, two for them.

So 99.988% of words are comparable, not 88%.

### Geometric registration — the fit, and the proof

Their coordinate system and ours differ by ONE affine map per page. Fitting our
word-ink centres against theirs, per page:

```
p3    n=127  ours = 1.33323 * theirs + -54.940   residual med 0.073  p90 0.351  max 0.874
p50   n=135  ours = 1.33336 * theirs + -114.891  residual med 0.131  p90 0.396  max 0.840
p143  n=130  ours = 1.33340 * theirs + -54.956   residual med 0.077  p90 0.304  max 0.608
p300  n=132  ours = 1.33359 * theirs + -114.973  residual med 0.106  p90 0.393  max 0.670
p384  n=143  ours = 1.33354 * theirs + -114.982  residual med 0.097  p90 0.327  max 0.751
p500  n=127  ours = 1.33341 * theirs + -114.937  residual med 0.106  p90 0.414  max 0.661
p579  n=147  ours = 1.33356 * theirs + -55.020   residual med 0.061  p90 0.210  max 0.922
```

The scale is 4/3 on every page and the offset takes one of two values by page
parity. **The fit is not a fudge factor — it recovers our own page transform.**
Our emitted `076.svg` carries `<g transform="matrix(1.3333 0 0 -1.3333 -115 640)">`
and the fit for an even page returns 1.3334 and −114.94. Two independent
derivations of the same numbers.

Because the residual is 0.10 units median on words 20–45 units wide, run edges
are compared DIRECTLY. Nothing is normalised per word or per line — normalising
per word would have hidden exactly the defect being hunted.

---

## The one modelling error that had to be fixed first

The first version modelled our ligature groups the way `audit_ligatures.py`
does — one group per atom, consecutive atoms sharing a `lig` merged. Checked
against the actual cached page SVGs it **disagreed with the real output for 20%
of the flagged words** (122 of 600 sampled).

Cause: `rewrite()` opens a `<g class="ligature">` only when it is about to emit
an element. **An atom holding no elements never opens a group at all.** p502
`هَٰذَا` has an atom `ا` with `els == []`; the emitter writes ONE group
`data-text="هذ"` holding the alif's ink as a second body path. Modelling it as
two groups invented a defect that is not in the file.

After the fix the model reproduces the emitted `data-text` sequence exactly on
**1,015 of 1,015 words** across eight pages. `audit_ligatures.py` still has this
flaw and over-reports its `empty` class; worth a look.

---

## What was found

| tier | | words | verdict |
|---|---|---|---|
| A | **ink changed hands** — the word's edge moves past the empty band | **5** | OURS-WRONG (3 sites) |
| B | their run joins through a letter that never joins forward | 2 | THEIRS-WRONG |
| C | neither side convicted by the joining rules | 157 | UNDECIDED |
| D | a group names letters whose ink sits in another group of the SAME word | 34 | OURS-WRONG (grouping only) |
| E | we emit one group where the rules AND they say two | 2,687 | OURS-WRONG |
| — | their lam-alif limb convention (not a defect) | 44 | excluded |

### The thresholds, and the empty bands behind them

Word-edge disagreement (|our edge − their edge|, our units), over the 74,495
words whose run sequences agree:

```
   p50  0.21u   p90  0.86u   p99  1.52u   p99.9  2.74u   max 12.81u
    0- 1u  69903 ############################################################
    1- 2u   4410 ############################################################
    2- 3u    173 ####
    3- 4u      7
    4-12u      0        <-- EMPTY
   12-13u      2
```

Over the 2,848 rows where the run sequences differ:

```
    0- 1u  2762      1- 2u  77      2- 3u  5      3- 4u  2
    4- 5u     0        <-- EMPTY
    5- 6u     1      7- 8u   1
```

Both distributions have a real empty band immediately above 4u, so the 4.0u
threshold sits inside a gap and the tier-A verdicts are proof-class by this
project's own rule, not a ranked prior. **This is the headline number: our word
boundaries agree with an independent decomposition of the same artwork on
77,417 of 77,422 words.**

---

## The six (nine) cases adjudicated by reading the ink

### 1. p58 `وَٱلْإِنجِيلُ` 3:65:10 loses its waw to `ٱلتَّوْرَىٰةُ` — OURS-WRONG, proof

Our elements:

```
3:65:9  ٱلتَّوْرَىٰةُ  atom3 seg "ىة"  body 235.77..248.98   <- the real ىة
                                      body 222.96..232.87   <- a SECOND, detached body
3:65:10 وَٱلْإِنجِيلُ  atom0 seg "و"   mark fatha 226.09..232.36   and NO BODY AT ALL
```

Three independent signals agree:

* **They draw it.** Their `و` run is at 222.8–233.0 in our units.
* **We do not.** Our `و` group holds a fatha and no letter ink.
* **Our own mark says so.** The waw's fatha sits at 226.1–232.4, directly over
  the disputed stroke at 223.0–232.9 and nowhere near anything else.

`audit_ligatures.py` does flag this word as `empty` — but it flags 195 words
that way and 34 of the other 35 in this comparison turn out to be ink in the
neighbouring group of the SAME word, which is harmless. The `empty` class on its
own cannot tell the two apart. `ٱلتَّوْرَىٰةُ`, the word that actually holds the
ink, is clean in every audit.

This word IS in `stolen_letters.json` — but ranked 0.198 on ink ratio, far down
a 453-row list with no empty band, which is exactly why that hunt could not use
it. The other two sites are not in that list at all.

### 2. p324 `يُؤْمِنُونَ` 21:30:18 takes the alif of `أَفَلَا` — OURS-WRONG

```
21:30:17 أَفَلَا     ours [ا | فلا]      theirs [أ | فلا | ا]  (ا = 184.6..193.9)
21:30:18 يُؤْمِنُونَ ours group "يو" holds TWO bodies: 184.48..193.61 and 167.27..180.84
                    theirs "يؤ" = 167.0..181.0 only
```

* `يؤ` is one connected run, so it is one contour; ours holds two.
* The extra contour is at 184.5–193.6, which is to the RIGHT of the word's first
  letter — outside the word entirely in a right-to-left line.
* It sits in `أَفَلَا`'s y band (305.3–316.2 against 303.6–320.1) and its left
  edge (184.48) reaches past the lam-alif's own (185.20), which is what the
  alif limb of a `لا` does.
* The words overlap by 8.4u if we are right, and do not if they are.

### 3. p455 `بَارِدࣱ` / `وَشَرَابࣱ` 38:42:5–6 — a two-step shift, OURS-WRONG

The whole line is displaced by one piece:

```
                 ours                                theirs
مُغْتَسَلُۢ      85.6..127.9  (1 body)               85.4..128.1
بَارِدࣱ         "با" 2 bodies 76.1..89.8             "با" 76.3..84.1
                "رد" 1 body 66.2..75.5               "ر" 66.3..75.7   "د" 64.3..69.8
وَشَرَابࣱ       "و"  64.2..69.6                      "و" 51.7..61.9
                "شر" 3 bodies incl. 51.7..61.6       "شر" 33.2..55.6
```

Read right to left: `وَشَرَابࣱ`'s group named `و` actually holds
**`بَارِدࣱ`'s final dal** (64.2–69.6 = their 64.3–69.8), and the real waw
(51.7–61.6) has been pushed into the `شر` group. Meanwhile `بَارِدࣱ`'s `با`
group holds a second detached contour at 86.5–89.8 — high (y 514.7–524.2), in
`مُغْتَسَلُۢ`'s span, which they give to `مُغْتَسَلُۢ`. `با` is a connected run
and cannot be two contours.

Nothing in our own geometry could see this: every mark count is right, both
words hold plausible ink, and `audit_ligatures.py`, `audit_intervals.py` and
the chunk-fit flags are all clean on 38:42:4, 5 and 6.

### 4. p546 `ءَاتَىٰكُمُ` 59:7:25 — THEIRS-WRONG

They draw it as `ء | ا | تىكم`. **ى never joins to the letter after it**, so
`تىكم` is a run the script cannot draw. Our `ء | ا | تى | كم` is legal and is
what `segment_word()` says. Note this is only visible in the RAW text — the
ى→ي fold used for matching hides it, so the joining-rule test is applied to the
unfolded strings.

### 5. p548 `فَأَنسَىٰهُمْ` 59:19:6 — THEIRS-WRONG

Same letter, same rule: their `فا | نسىهم` joins through ى. Ours is
`فا | نسى | هم`.

### 6. p69 `مَوْلَىٰكُمْۖ` 3:150:3 — BOTH WRONG, and that is the honest answer

The word is م و ل ى ك م and the rules allow exactly three runs: `مو | لى | كم`.
Ours emits `مولى | كم` (joining through و, impossible). Theirs emits
`مو | لىكم` (joining through ى, impossible). Each side merges a different
legal break. Neither can be called right. Sixteen more rows are of this shape
(`هَدَىٰنَا`, `مَجْر۪ىٰهَا`, `لَهَدَىٰكُمْ`, `نَجْوَىٰكُمْ`, `بُشْرَىٰكُمُ`,
`ذِكْرَىٰهَآ`, `بِطَغْوَىٰهَآ` …) — all the same ـىٰ + suffix shape.

### 7. p76 `أُو۟لَٰٓئِكَ` 3:199:22 — OURS-WRONG, read straight out of the emitted file

```
<g class="word" … data-uthmani="أُو۟لَٰٓئِكَ">
  <g class="ligature" data-text="اوليك">   ← ONE group, four body paths
```

`data-text="اوليك"` names a run containing both ا and و in non-final position.
No such run can be drawn. They emit `ا | و | ليك`; our own `segment_word()`
emits `ا | و | ليك`. Only the emitter disagrees. This is tier E's exemplar.

### 8–9. The three words the handoff called confirmed thefts are NOT thefts

`p71 غَالِبَ / بَعْدِهِۦ`, `p413 يَحْزُنكَ`, `p546 وَمَآ` are the words
`score_both.py` adjudicates OURS on width alone. Measured against the reference,
every word boundary on those three lines agrees to within 1.3u:

```
p71  3:160:5  غَالِبَ     ours 281.7..313.1  theirs 281.6..313.4
p71  3:160:14 بَعْدِهِۦۗ  ours 302.7..330.7  theirs 302.1..331.4
p413 31:23:4  يَحْزُنكَ   ours  72.0..108.4  theirs  71.8..108.7
p546 59:7:24  وَمَآ      ours 167.4..187.3  theirs 167.5..187.5
```

An independent decomposition draws exactly the ink we do. They were width
artefacts, and CLAUDE.md's decision not to chase the last width words is
confirmed from outside.

Likewise `p384 27:78:7/8` and `p579 76:11:2`, recorded as thefts, are **tier D,
not tier A**: the alif's ink is in the word, in the group next door. Their word
extents match the reference to 0.1–0.3u. They are a grouping defect, not an
ownership one.

---

## Tier E — one defect, 2,687 words, 586 pages

Our emitter puts two runs in one `<g class="ligature">` and names the group with
a string the script cannot draw. 1,503 distinct patterns; the most common:

| words | ours | theirs |
|---|---|---|
| 42 | `و ｜ اتقو ｜ ا` | `و ｜ ا ｜ تقو ｜ ا` |
| 41 | `ا ｜ لحيوة` | `ا ｜ لحيو ｜ ة` |
| 41 | `ا ｜ لاخرة` | `ا ｜ لا ｜ خر ｜ ة` |
| 36 | `و ｜ ان` | `و ｜ ا ｜ ن` |
| 33 | `ا ｜ لصلوة` | `ا ｜ لصلو ｜ ة` |
| 24 | `كفرو ｜ ا` | `كفر ｜ و ｜ ا` |

In 2,685 of the 2,687, **our own `segment_word()` agrees with
MushafDatabase** — the joining-rule segmentation is right and the emitted
grouping is what loses it. It is pixel-neutral (the ink is all present and in
the right word), so it costs nothing today; it costs whenever `data-text` is
believed. `audit_ligatures.py` already prices the deficit side of this as
`count-deficit(not reported)`.

## Their one convention, excluded (44 words)

A word whose run ends in a lam-alif gets an extra run named `ا` for the alif
limb, whose ink overlaps the run before it — `فلا | ا`, `صلا | ا | تهم`. Same
ink on both sides, different bookkeeping. Not counted as a disagreement.

---

## What did not work

* **Comparing by word text without folding hamza carriers.** 30% of words look
  different when only the encoding is; the real figure is 0.012%.
* **Normalising x per word.** The first plan. It divides out precisely the
  quantity that detects a stolen piece — a word that gained ink is wider, and
  per-word normalisation makes it the same width as everyone else. The global
  affine map has a 0.10u residual and needs no normalisation at all.
* **One ligature group per atom.** Wrong for 20% of flagged words; see above.
  Everything built on it is invalid, and it was invalid until it was checked
  against the emitted SVG rather than against the model.
* **Trusting `stolen_letters.json`'s ranking.** 173 of its 453 rows do appear
  somewhere in this comparison, but only one is a real theft, and it sits at
  rank ~0.198 in the middle of the list. The ranking is not informative for this
  family; the outside opinion is.

## Open

* Tier C's 157 UNDECIDED rows (159 UNDECIDED verdicts in all, two of them in tier A) are on the page for the eye. The ـىٰ+suffix family
  (17 rows) is the largest and both sides are wrong in it — fixing ours there is
  a pure win with no adjudication needed.
* Tier A's three sites are actionable now: p58 3:65:9→10 (waw), p324 21:30:17→18
  (alif limb), p455 38:42:4→5→6 (a two-step shift).
* `audit_ligatures.py` shares the atom-per-group modelling error and its
  `empty` count should be re-measured.

---

## CORRECTION (added after review, 2026-08-29 05:45)

**The claim "p71 غَالِبَ / بَعْدِهِۦ, p413 يَحْزُنكَ, p546 وَمَآ and the
p384/p579 alifs are NOT thefts" is WRONG, and it inverts its own evidence.**

This comparison ran 05:07-05:39. Every one of those defects had ALREADY BEEN
FIXED before it started: the p384 and p579 alifs at commit 689936e (~04:47),
and p71 / p413 / p546 earlier still, from Abdullah's eye. So the build it
compared was the CORRECTED build. Finding that our extents match
MushafDatabase there does not show the defects were imaginary — it shows the
REFERENCE AGREES WITH THE FIX.

Proved directly with the `QSVG_OVR` switch this agent itself added, by
rebuilding p71 with the one override removed:

```
3:160:14 بَعْدِهِۦ   WITH the fix   x 302.7 .. 330.7
3:160:14 بَعْدِهِۦ   WITHOUT the fix x 310.0 .. 330.7
```

The word's left edge moves by 7.3u — exactly the 302.7-307.5 body piece
Abdullah identified as stolen (e295). Before the fix our boundary was 310.0;
after it, 302.7; and the reference matches the FIXED value. Two independent
decompositions agreeing on the corrected state is the strongest confirmation
available that the correction was right.

**Method lesson, worth more than the finding:** when comparing against an
outside reference, record WHICH BUILD was measured. A reference comparison run
after a fix cannot say anything about whether the defect existed — it can only
say whether the fix agrees with the reference. To test a past defect, rebuild
with the fix disabled (`QSVG_OVR` makes that a one-liner) and compare BOTH
states.

Everything else in this report stands: the three new Tier-A thefts (p58, p324,
p455), the 2 THEIRS-WRONG cases, the 2,687 emitter grouping defect, the
proof-class registration, and the correction that "~12% of words split
differently" is really 9 words in 77,431.
