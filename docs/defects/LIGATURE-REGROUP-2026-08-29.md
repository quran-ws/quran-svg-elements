# Diacritics in the wrong ligature group — cause, fix, measurement

2026-08-29. Starting point: `tools/audit_ligatures.py` reported **1206 `misplaced`**
rows over 604 pages — a mark with no horizontal overlap with the ink of the
`<g class="ligature">` holding it, and real overlap with a different group's ink in
the same word. Intra-word only: the word ownership was already right.

**Result: `misplaced` 1206 → 6, and the six are audit false positives.**
`empty` 712 → 195 as a side effect. Zero ownership changes over all 604 pages,
all four gates green.

---

## 1. Cause taxonomy

Attribution was measured, not guessed: pages 1-40 were run with `QSVG_TRACE=all`
(every `_omove` hand-off prints its caller's line number) plus a wrapper on
`put_in_ligature`, and each `misplaced` mark was matched to the passes that had
touched it.

| cause | share of pages 1-40 | mushaf-wide estimate |
|---|---|---|
| **A. the neighbour-transfer trial's undo** (`_omove` at lines 4992/5019) | **76 of 82 (93%)** | ~1120 |
| **B. the mark sits in the GAP between two pieces** and `cluster_line` guessed | 6 of 82 (7%) | ~90 |
| anything else | **0** | 0 |

Nothing else accounted for more than one mark. In particular the `at[0]` family that
`put_in_ligature` was written for is already extinct: the four remaining direct
`atoms[0]["els"].append(...)` sites (lines 4787, 6798, 9199, and the
`QSVG_OVRLIG=0` fallback) all place `mkpart` members, which the audit excludes.

### Cause A — an undo that re-decides instead of restoring

The neighbour-transfer loop moves a piece to the neighbouring word, scores both
words, and moves it straight back:

```python
_omove(e, v, r)          # trial
d = _oscore(r) + _oscore(v)
...
_omove(e, r, v)          # undo
```

`_omove` chose its target atom by **nearest centre x**. That is a reasonable rule for
a real move and a wrong rule for an undo: the piece comes back to the word it started
in but not to the atom it started in, so a trial that was rejected still leaves a
permanent footprint on the ligature grouping.

Type case, p12 `ٱلْكِتَٰبَ`, traced:

```
MOVE line4992  mark/sukun x 100.8-105.2  ٱلْكِتَٰبَ -> بِهِۦ
MOVE line5019  mark/sukun x 100.8-105.2  بِهِۦ -> ٱلْكِتَٰبَ
```

The sukun of the article spans 100.8-105.2. The `لكتب` atom spans 55.0-105.8 and
contains it outright; the bare `ٱ` atom spans 107.2-109.9 and does not touch it. But
the alef's nearest element centre is 5.5u away and `لكتب`'s is 17.6u, so the undo put
the sukun in `<g data-text="ا">`.

### Cause B — the gap between two pieces

Where a mark is drawn in the gap between two ligature pieces, `cluster_line`'s
geometric choice is a coin toss, and the two families where the coin lands wrong are
systematic:

* **small-alef (91 of the 184 left after cause A was fixed)** — the dagger alef after
  a non-joining `ذ`/`د` is drawn past the end of its own piece. p37 `ذَٰلِكُمْ`: the
  alef spans 168.3-170.3 with `ذ` at 170.8-176.2 and `لكم` at 143.3-167.4 — 0.5u from
  the piece that owns it, 0.9u from the piece holding it.
* **tanween (87)** — the open `ࣰ ࣱ ࣲ` of a final `ء` or `ة` is drawn over the piece
  BEFORE it. p85 `مَآءࣰ`, p20 `أُمَّةࣰ`, p27 `حَيَوٰةࣱ`.

---

## 2. What was measured, and the distributions behind the thresholds

**Overlap, not centre distance.** This is `audit_ligatures.py`'s own measurement and
the fix reuses it: comparing mark centres to group centres calls **26,525 marks
misplaced** — a third of every mark in the mushaf — because ligature groups sit side
by side and a mark near a boundary is legitimately nearer the next group's middle.
Comparing horizontal OVERLAP calls 1206. A mark belongs to the letters it touches.
Threshold −0.6u is the audit's; it is quoted in the pipeline comment so a future
change to one moves the other.

**The text budget, per segment.** `segment_word()` already returns each piece's mark
list, e.g. `مَآءࣰ → [('ما', [fatha, maddah]), ('ء', [fathatan])]`. That is the second
signal, and it is what makes the geometry safe to act on. It also refuses moves that
geometry alone would get wrong: in `أُمَّةࣰ` the damma of `أُ` overlaps the `مة` group
and belongs to the alef, so a purely geometric rule would move it the wrong way. It is
left alone because the alef group is not short of a damma by the overlap test.

**Element-level diff of all 604 emitted pages** (word key, `data-kind`, `data-mark`,
`d` — never `data-eid`, which is not stable across builds):

| | vs. the pinned baseline |
|---|---|
| words whose element multiset changed (ownership, naming, geometry) | **0** |
| words whose ligature partition changed | 4599 |

---

## 3. The two fixes

### Fix 1 — `_omove(e, src, dst, into=None)`: an exact undo

`_omove` now returns the atom the piece left, and the undo passes it back as `into=`.
An undo restores; it does not re-decide. Real moves are untouched.

`misplaced` 1206 → **184**. `empty` 712 → **195** — the same bug had been shuffling
BODY ink between the atoms of a word, so 533 groups that named letters and held none
got their letters back. Examples, all verified by reading the emitted groups:

```
p79  أُخْتࣱ    before: one group  خت  holding both bodies
               after:  ا | خت
p323 هَٰذَا    before: one group  هذ  holding both bodies
               after:  هذ | ا
p575 خَيْرࣰا   before: one group  خير holding both bodies
               after:  خير | ا
```

### Fix 2 — `QSVG_LIGFIX`: a late ligature reconciliation pass

Runs immediately before `rewrite()`, after every mover. For each word it builds the
groups exactly the way the emitter does (consecutive atoms sharing `atom["lig"]`, not
one atom per group) and moves a mark only when **both** signals agree:

* geometry — the mark has no overlap with its own group's letters (`> -0.6` fails) and
  real overlap with exactly ONE other group's letters; and
* budget — the text says its own group does not want that mark and the target group
  does. Ambiguity (two candidate groups) is left alone.

`misplaced` 184 → **6**.

The pass is pixel-free by construction: it re-parents an element inside its own word
and never renames or re-owns one. `QSVG_LIGFIX=0` reverts it.

---

## 4. Collateral, classified

The rule is: no changed element outside the intended ones may go unexplained.

| class | count | |
|---|---|---|
| **RIGHT** — the intended fix | 1200 marks regrouped + 533 groups given their letter ink back | proved above |
| **WRONG** | **3 words** | written to `docs/defects/ligature-regroup-for-eye.json` |
| **AUDIT ARTEFACT** | 1 word | p455 `وَشَرَابࣱ` — emitted SVG identical before and after; the audit counts an empty atom the emitter never emits |
| **UNCLEAR** | 0 | |
| NEW `misplaced` | **0** | the 6 that remain are all in the original 1206 |

The three WRONG ones are `p244 قَالُوا۟`, `p375 ٱلْأَوَّلِينَ`, `p447 إِذَا`. In each,
a BODY that `cluster_line` had merged into the wrong atom used to be moved to a better
atom by the buggy undo, purely by accident; the exact undo hands it back to the atom
the cut put it in. The defect is the cut, and it was masked, not introduced. Kept
because the same change gives 533 other groups their letters back; not fixed here
because a body-regrouping rule needs its own measured distribution and this work is
about diacritics. Full detail in the for-eye file.

---

## 5. What could NOT be fixed, and why

* **The 6 residual `misplaced` rows are audit false positives.** Read atom by atom,
  every one sits in the group whose `data-text` names the letter it is a mark of, and
  misses the overlap test by 0.4-1.7u because it is drawn just past the end of that
  letter's ink: p187 `وَأَذَٰنࣱ`, p272 `دَٰخِرُونَ`, p315 `هَٰذَٰنِ`, p468 `وَذَٰلِكَ`,
  p535 `وِلْدَٰنࣱ`, p549 `بُرَءَٰٓؤُا۟`. The budget signal refuses to move them, which is
  the right answer. If zero is wanted here the change belongs in `audit_ligatures.py`,
  not in the pipeline: a mark whose own group names the letter it belongs to is not
  misplaced.
* **The 195 remaining `empty` groups** are a BODY problem (a group that names letters
  and holds none) and out of scope here. `p447 إِذَا` shows the shape of it —
  `cluster_line` merged three separate narrow bodies (alef-hamza, `ذ`, alef) into one
  atom, so no regrouping pass downstream can separate them. That is the next piece of
  work in this area and it is a change to the CUT, not to the grouping.
* **Reciprocal exchanges were tried and abandoned.** In `أُمَّةࣰ` the budgets are
  satisfied exactly by a MUTUAL swap — fathatan to `مة`, damma to `ا`. Only the
  fathatan half has both signals; the damma half has the text and the geometry against
  it. A mutual exchange would have been count-perfect and half of it unproven, so only
  the proven half ships. The damma stays where the ink puts it.

---

## 6. Gate numbers

| gate | required | measured |
|---|---|---|
| `tools/audit_pixels.py 1 604` | 0 failures | **FAILURES: 0**, every page pixel-identical |
| `scratchpad/bench.py` | SCORE 137, no failures | **SCORE 137, FAILURES: none**, pixelfail 0, budget-mismatch 0/2706 |
| `tools/audit_taxonomy.py` | OK | **OK** — 35 mark names, 3 muʿānaqah pairs, sifr 3970/66 |
| fresh sweep (`.cache/sweeps/ligreg2`) | marks 0, intervals 1 (p350) | **marks 0, intervals 1 — p350 only**, 0 pages worse |
| `tools/audit_ligatures.py 1 604` | — | misplaced **1206 → 6**, empty **712 → 195**, count 0, order 1 |
