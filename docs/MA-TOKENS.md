# How `ما` and `وما` are treated

Generated from the emitted pages by `scratchpad/mkmd.py` — no text typed by hand.

Ours = the tokens we emit. Rasm = whitespace tokens of the Complex's 1441H text.


## 1. The inventory — every token starting with `ما` or `وما`

26 distinct tokens, 1777 occurrences.


| token | n | first site | as emitted |
|---|---:|---|---|
| `ما` | 1013 | 2:17:8 | `مَا` |
| `وما` | 646 | 2:4:6 | `وَمَآ` |
| `ماء` | 35 | 2:22:11 | `مَآءࣰ` |
| `ماذا` | 22 | 2:26:24 | `مَاذَآ` |
| `مائة` | 8 | 2:259:19 | `مِا۟ئَةَ` |
| `مال` | 8 | 6:152:3 | `مَالَ` |
| `مالا` | 7 | 11:29:5 | `مَالًاۖ` |
| `ماله` | 6 | 2:264:11 | `مَالَهُۥ` |
| `ماب` | 6 | 13:29:8 | `مَـَٔابࣲ` |
| `وماتوا` | 4 | 2:161:4 | `وَمَاتُوا۟` |
| `ماتوا` | 3 | 3:156:21 | `مَاتُوا۟` |
| `مات` | 2 | 3:144:11 | `مَّاتَ` |
| `مائدة` | 2 | 5:112:13 | `مَآئِدَةࣰ` |
| `مائتين` | 2 | 8:65:13 | `مِا۟ئَتَيْنِۚ` |
| `مابا` | 2 | 78:22:2 | `مَـَٔابࣰا` |
| `وماذا` | 1 | 4:39:1 | `وَمَاذَا` |
| `ماءك` | 1 | 11:44:4 | `مَآءَكِ` |
| `ماؤها` | 1 | 18:41:3 | `مَآؤُهَا` |
| `مارب` | 1 | 20:18:12 | `مَـَٔارِبُ` |
| `مارد` | 1 | 37:7:5 | `مَّارِدࣲ` |
| `مارج` | 1 | 55:15:4 | `مَّارِجࣲ` |
| `وماء` | 1 | 56:31:1 | `وَمَآءࣲ` |
| `مانعتهم` | 1 | 59:2:19 | `مَّانِعَتُهُمْ` |
| `ماؤكم` | 1 | 67:30:5 | `مَآؤُكُمْ` |
| `ماليه` | 1 | 69:28:4 | `مَالِيَهْۜ` |
| `ماءها` | 1 | 79:31:3 | `مَآءَهَا` |

## 2. The `ما` + `لـ` family — where the seam actually is

Every site where a `ما`/`مال` token is followed by `هذا`, `هؤلاء` or `لي`.


| ayah | ours | the rasm | agree? |
|---|---|---|---|
| 4:78 | `فَمَالِ` + `هَٰٓؤُلَآءِ` | `فَمَالِ هَٰٓؤُلَآءِ` | ✅ |
| 12:31 | `مَا` + `هَٰذَا` | `مَا هَٰذَا هَٰذَآ` | ✅ |
| 18:49 | `مَالِ` + `هَٰذَا` | `مَالِ هَٰذَا مَا` | ✅ |
| 21:65 | `مَا` + `هَٰٓؤُلَآءِ` | `مَا هَٰٓؤُلَآءِ` | ✅ |
| 23:24 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ مَّا` | ✅ |
| 23:33 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ` | ✅ |
| 25:7 | `مَالِ` + `هَٰذَا` | `مَالِ هَٰذَا` | ✅ |
| 27:20 | `مَا` + `لِىَ` | `مَالِيَ` | ❌ rasm welds, we split |
| 28:36 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ` | ✅ |
| 34:43 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ مَا` | ✅ |
| 34:43 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ مَا` | ✅ |
| 36:22 | `وَمَا` + `لِىَ` | `وَمَالِيَ` | ❌ rasm welds, we split |
| 40:41 | `مَا` + `لِىٓ` | `مَا لِيٓ` | ✅ |
| 46:17 | `مَا` + `هَٰذَآ` | `مَا هَٰذَآ` | ✅ |

## 3. What this shows

The `ما` + `لـ` family is decided **per site by the rasm**, and we already follow
it at four of the six sites:

* 4:78, 18:49, 25:7 — the rasm welds `ما`+`لـ` into one token, and so do we.
* 40:41 — the rasm separates them, and so do we.
* 27:20 and 36:22 — the rasm welds, and we split.

40:41 against 27:20 is the crux. It is the **same phrase**, spelled separated in
one place and welded in the other. That is not a rule anyone can derive; it is
transmitted, site by site — which is exactly what المقطوع والموصول is.

So the two remaining sites are not a defensible convention, they are an
**internal inconsistency**: we treat one construction two different ways, and the
side we get wrong is the side the print's own text disagrees with. The earlier
explanation in `MAQTU-MAWSUL.md` — that our unit is the "word-by-word token" and
follows ordinary modern orthography — does not survive this table, because
ordinary orthography would not weld `مَالِ` at 18:49 either, and we do weld it.

15:7 `لَّوۡمَا` is the same shape of error outside this family.

## 4. What is NOT affected

The prefixed `و` is untouched by any of this: `وما` is one token at all 646
sites, and there are **0** bare `و`/`ف`/`ب`/`ل` words in the whole mushaf. The
question of where `ما` welds to what follows is independent of the particle that
precedes it.

## 5. Ours vs theirs — every source, all 6,236 ayahs

Word-count disagreement with the Complex's own 1441H text, measured over the
whole Quran. Lower is closer to the print's own spelling.

| source | what it is | ayahs differing from the rasm |
|---|---|---:|
| **ours** | this pipeline | **3** |
| **V4 layout** | the print's own 1441H layout | **3** |
| **DigitalKhatt** | the 1421H V2 print | **4** |
| **quran.com** | `text_uthmani` | **7** |

The union of every disagreement, so nothing is hidden by a total:

| ayah | rasm | ours | V4 layout | DigitalKhatt | quran.com |
|---|---:|---:|---:|---:|---:|
| 2:181 | 14 | · | · | · | 13 |
| 8:6 | 12 | · | · | · | 11 |
| 13:37 | 20 | · | · | · | 19 |
| 15:7 | 7 | 8 | 8 | 8 | 8 |
| 27:20 | 11 | 12 | 12 | 12 | 12 |
| 36:22 | 7 | 8 | 8 | 8 | 8 |
| 37:130 | 4 | · | · | 3 | 3 |

`·` = agrees with the rasm.

**Reading it:**

* **15:7, 27:20, 36:22 — every source disagrees, including the print's own V4
  layout.** No word-marking source gets these right; only the Complex's text
  does. This is the shared inherited inconsistency of section 3.
* **37:130** — DigitalKhatt and quran.com still hold one word where the rasm and
  V4 have two. We used to, and no longer do; that fix is what brings us level
  with the print's own layout.
* **2:181, 8:6, 13:37** — quran.com fuses `بَعْدَ مَا`. We already split these
  (`_DKSEG_SPLITS`), forced independently by p254's line break.

So we now match the print's own layout exactly, and are ahead of DigitalKhatt
and quran.com. The only remaining gap is the three sites where V4 itself
departs from the Complex's text — and closing those would put this
decomposition ahead of every source measured here.
