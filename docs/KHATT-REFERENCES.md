# The calligraphy references, and what they are allowed to decide

Three books Abdullah supplied, read 2026-09-08. Index of pages: `docs/khatt_plates.json`.

| | pages | what it is |
|---|---|---|
| **ميزان الخط العربي** — عباس شاكر جودي البغدادي | 65 | connection drills (10-25), then letter anatomy with nuqta measurements (26-42), then Qur'anic specimens |
| **قواعد الخط العربي** | 78 | one plate per letter, its forms and its joins, each numbered against a note |
| **كراس الخط النسخ** — هاشم البغدادي | 17 | a teaching workbook: how to hold the pen and form each letter |

## What they cannot be

**Not ground truth, and not registrable.** They are pen Naskh drawn by hand, not the
KFGQPC V4 typeface, and they are scans with no vectors and no labels. Nothing in them
can be aligned to our ink the way the QUL tajweed layers are, so nothing in them can
train the model or gate a build.

**Not a better size prior either.** The anatomy plates state each letter's proportions in
rhombic dots, which is a real measurement — but we already measure size bands directly
from 322,758 letters of this very artwork, and a band measured on the thing itself beats
a band measured on its ancestor. The plates stay a sanity check, not a source.

## What they are for

**Convention.** Our hard cases are not "where is the ink" but "who owns this stroke":
a shared لك stem, a medial ك+ل that is an arm plus a bowl plus a stem plus a foot, the
connecting stroke into a final ه. No amount of our own data answers that, because both
answers reproduce the same ink. It is a fact about how the script is built, and the
drills state it letter by letter.

So the books are consulted when:

1. **a pair has nothing taught** — `tools/pairs_worklist.py` ranks every pair by joints
   still guessed and names the drill page for each, so a drawing session starts from the
   page that shows the join rather than from memory;
2. **a drawn correction and the model disagree** on which side of a stroke a letter ends;
3. **a convention has to be written down** — the answer goes into the code as a rule with
   the plate cited, not as a one-off fix.

## The worklist as it stands

`python3 tools/pairs_worklist.py` over the rebuilt labels, 2026-09-08:

```
657 pairs over 164,429 joints | 128,246 joints still guessed (78%) | 190 pairs with nothing taught at all
nothing taught, worst first: بم(389) عذ(323) هذ(271) فم(228) حك(220) رة(198) شه(192) ثل(191) سه(177)
```

The top of the ranked list is لا 4,348 guessed joints, هم 3,945, لم 3,013, ين 2,999,
من 2,987, عل 2,904 — every one of which the mizan drills draw by hand, at the page the
tool names.
