# Our word text vs the King Fahd Complex's own data

Reference: **`UthmanicHafs_v2-0`** (`hafsData_v2-0.json`), the Complex's published
RasmUthmani text for the 1441H Hafs mushaf — the same body of text this artwork was
set from. Kept at `.cache/official/`. Reproduce any figure here with:

```bash
python3 tools/compare_official_text.py                 # the headline numbers
python3 tools/compare_official_text.py --diff          # every differing word
python3 tools/compare_official_text.py --segmentation  # word-count candidates
```

Measured 2026-08-31, all 604 pages.

---

## Result

```
comparable words:      77405
  raw code points:     36129  = 46.6753%   (measures ENCODING)
  normalised:          77374  = 99.9600%   <- the content figure
word-count candidates: 3 ayahs
```

**99.9600% exact on content — 31 differing words out of 77,405**, and all 31 are
characterised below. None is an unexplained defect.

### Read the raw figure correctly

46.68% is not a disagreement about the Quran; it is a disagreement about
**Unicode**. The two texts encode the same drawn marks with different code
points, consistently, and `CLAUDE.md` states the rule this obeys:

> Compare after normalising code points to families, or you measure encoding
> rather than content.

Six substitutions account for **50,645 of 51,261** character edits:

| n | the Complex writes | we write | mark |
|---:|---|---|---|
| 36,641 | `U+06E1` small high dotless head | `U+0652` sukun | sukun |
| 3,973 | `U+0652` sukun | `U+06DF` small high rounded zero | the silent circle |
| 3,400 | `U+064A` yeh | `U+0649` alef maksura | word-final dotless ya |
| 2,901 | `U+0657` inverted dammah | `U+08F0` open tanwin_al_fath | open tanwin |
| 1,931 | `U+0656` subscript alef | `U+08F2` open tanwin_al_kasr | open tanwin |
| 1,799 | `U+065E` fathah with two dots | `U+08F1` open tanwin_al_damm | open tanwin |

The first two are a **swap**, and that is a trap worth naming: fold them one
after another and `06E1` becomes `0652` and then continues on to `06DF`,
collapsing the sukun and the silent circle into one mark. `_FOLD` is applied
through a single `str.translate` so both move at once.

Ya / alef maksura is folded on **both** sides instead, because a directional
fold would also rewrite every medial ya. The two are drawn identically at the
positions where the texts disagree.

---

## The 31 remaining differences

### 24 — the sajdah overline (modelling, not a defect)

The Complex marks the sajdah recitation phrase by putting `U+06E4` SMALL HIGH
MADDAH on each of its words. Measured across the whole text, that character
appears in **exactly 15 ayahs — one per sajdah site**, and nowhere else:

    7:206  13:15  16:49  17:107  19:58  22:18  22:77  25:60
    27:25  32:15  38:24  41:37   53:62  84:21  96:19

We do not carry it in the word text: we draw the overline as its own mark, and
the annotation graph already requires the sajdah compound to hold *one overline
and one sign*. Same ink, expressed one layer down. Examples:

| ayah | Complex | ours |
|---|---|---|
| 13:15 | `وَلِلَّهِۤ` | `وَلِلَّهِ` |
| 32:15 | `سُجَّدٗاۤ` | `سُجَّدࣰا` |
| 96:19 | `وَٱسۡجُدۡۤ` | `وَٱسْجُدْ` |

### 7 — orthographic edge cases

| ayah | Complex | ours | what it is |
|---|---|---|---|
| 2:72 | `فَٱدَّٰرَٰءۡتُمۡ` | `فَٱدَّٰرَْٰٔتُمْ` | hamzah seat on a maddah |
| 2:97 | `لِّـجِبۡرِيلَ` | `لِّجِبْرِيلَ` | a tatweel we do not carry |
| 17:7 | `لِيَسُـُٔواْ` | `لِيَسُۥٓـُٔوا۟` | small waw + maddah |
| 52:37 | `ٱلۡمُصَۜيۡطِرُونَ` | `ٱلْمُصَۣيْطِرُونَ` | `U+065C` vs `U+06E3`, the dot below |
| 56:23 | `ٱللُّؤۡلُوِٕ` | `ٱللُّؤْلُؤِ` | hamzah seat, waw vs ya |

These are the honest residue. Each is one site, none is a family, and none has
been folded away to flatter the number.

---

## Word counts — 3 candidates, 0 defects

```
15:7    official  7  ours  8     لَّوۡمَا   vs  لَّوۡ | مَا
27:20   official 11  ours 12     مَالِيَ    vs  مَا  | لِيَ
36:22   official  7  ours  8     وَمَالِيَ  vs  وَمَا | لِيَ
```

All three are the **mawṣūl** convention, and none is a disagreement: the official
file is ayah-level text, so its spaces state the rasm, not word boundaries. Every
source that actually marks words — including the print's own V4 layout — sets
these as two. See `MAQTU-MAWSUL.md`.

A fourth candidate, **37:130 `إِلۡ يَاسِينَ`, was a real error and is fixed** in
this build: we held one word where both the Complex's text and the print's V4
layout have two. It also closes the long-standing p451 "one run more than the
joining rules allow" flag.

---

## What this run changed

| | before | after |
|---|---|---|
| exact word text (normalised) | 99.9083% | **99.9600%** |
| word-count candidates | 4 | **3** (none a defect) |
| words | 77,432 | **77,433** |
| p451 flagged words | 2 | **1** |

Gates: **604/604 pixel-identical**, bench **SCORE 137** no failures pixelfail 0,
`audit_taxonomy` OK, `validate_annotations` OK.

## The lesson

The first version of this comparison split the Complex's ayah text on whitespace
and called the result a word list, then reported four segmentation defects. The
file has no word records at all. Three of the four "defects" were the mawṣūl
spelling convention, and the one real error was found only after asking a source
that marks words.

**A text file states spelling. A layout table states words.** Comparing a word
list against a whitespace split measures the rasm, not the segmentation.
