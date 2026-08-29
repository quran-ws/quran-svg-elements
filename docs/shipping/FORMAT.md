# Format specification — Quran page SVGs, Hafs / KFGQPC Madani

Edition id `hafs-kfgqpc` · 604 pages · 77,432 words · 6,236 ayahs · 114 surahs.
Artwork: the **KFGQPC Madani mushaf, V2 1421H print**.

This document ships with the files. Everything in it was verified against the
real build; every count is a measurement over all 604 pages, not an estimate.
Where the files are inconsistent, this document says so (§9) rather than
describing an ideal that does not exist.

> **Status.** This describes the build of **2026-08-29**. It documents the DEV
> profile that exists today; the production profile
> (`docs/shipping/SHIPPED-ARTIFACT-2026-08-29.md` §3) removes `data-eid`,
> `data-sig`, `data-mark-family` and the `<g class="ligature">` wrapper. Every
> other statement holds for both.

---

## 1. What these files are

Each file is one printed page of the mushaf, as **vector outlines**, with the
ink semantically decomposed:

- every **word** is exactly one `<g class="word">` — 77,432 groups, 77,432
  distinct `data-wid`, **no duplicates anywhere in the corpus**;
- every **letter shape** is a `<path data-kind="body">`;
- every **diacritic and sign** is a `<path data-kind="mark" data-mark="…">`
  drawn from a closed vocabulary of 34 names (§6).

The pages are **pixel-identical to the original print artwork** — the
decomposition regroups ink, it never moves or redraws it.

### What these files are NOT

- **There are no `<text>` elements.** All ink is paths. Browser find-in-page,
  text selection and copy of the Quranic text **do not work**. Search must go
  through the shipped index (`words.json`), not the SVG.
- **There is no letter-level decomposition.** The `<g class="ligature">`
  grouping is a *rendering run*, not a spelling. It is not a reliable letter
  segmentation — see §9.4.
- **No audio, no translation, no tafsir, no word timings.**

---

## 2. Quick start

```js
const doc = new DOMParser()
  .parseFromString(await (await fetch('pages/003.svg')).text(), 'image/svg+xml');

// the text of ayah 2:6, in reading order
[...doc.querySelectorAll('g.word')]
  .filter(w => w.dataset.wid.startsWith('2:6:'))
  .map(w => w.dataset.uthmani).join(' ');
// => "إِنَّ ٱلَّذِينَ كَفَرُوا۟ سَوَآءٌ عَلَيْهِمْ ..."

// highlight the whole ayah (NOTE: several fragments — one per printed line)
doc.querySelectorAll('g.ayah[data-aid="2:6"]').forEach(g => g.classList.add('hl'));

// one word
doc.querySelector('g.word[data-wid="2:6:3"]');
```

---

## 3. Document structure

A real fragment of `pages/003.svg`, with `d=` values trimmed:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:ayah="https://quranpedia.net"
     version="1.1" viewBox="0 0 345 550" xml:space="preserve">

 <g transform="matrix(1.3333 0 0 -1.3333 -55 640)">          <!-- page frame; y is FLIPPED -->

  <g id="ayah_markers" class="ayah_markers">                 <!-- all medallions, one layer -->
   <g class="ayah-marker" data-aid="2:6">
    <g transform="translate(45.272 87.116) scale(0.011 -0.011)">
     <path data-kind="ayah-marker-ornament" fill="#231f20" d="m1248,4q…"/></g>
    <g transform="translate(49.652 83.898)" ayah:x="14.53" ayah:y="530.03">
     <path data-kind="ayah-number" fill="#231f20" fill-rule="evenodd" d="M…"/></g>
   </g>
   …
  </g>

  <g id="content">
   <g class="line" data-line="1">
    <g transform="translate(206.04 112.26)">                 <!-- the LINE's own frame -->
     <g class="ayah" data-aid="2:6">
      <g class="word" data-wid="2:6:2" data-uthmani="ٱلَّذِينَ" data-rasm="ٱلذين"
                      data-imlaei="الَّذِينَ" data-qpc="ٱلَّذِينَ">
       <g class="ligature" data-text="ا">
        <path data-eid="e8"  data-kind="mark" data-mark="wasla"
              data-sig="120ca2e4516fb37a" d="M69.13 357.86…" fill="#231f20" fill-rule="evenodd"/>
        <path data-eid="e9"  data-kind="body"
              data-sig="609954a81633ef06" d="M67.99 354.70…" fill="#231f20" fill-rule="evenodd"/></g>
       <g class="ligature" data-text="لذ">
        <path data-eid="e10" data-kind="mark" data-mark="fatha"  data-sig="c9b82d57cfff4954" d="M…"/>
        <path data-eid="e11" data-kind="body"                    data-sig="82866803714f71bd" d="M…"/>
        <path data-eid="e12" data-kind="mark" data-mark="shadda" data-sig="db5a2ef9afc8c2c9" d="M…"/>
        <path data-eid="e13" data-kind="mark" data-mark="kasra"  data-sig="d7a8b5e19121fbe4" d="M…"/>
        <path data-eid="e14" data-kind="mark" data-mark="dot" data-mark-family="dots"
                                                             data-sig="d2506e4f8b4e28e5" d="M…"/></g>
       …
      </g>
     </g>
    </g>
   </g>
   …                                                          <!-- 15 lines -->
  </g>
 </g>

 <path class="ayahPolygon" fill-opacity="0" id="verse-13"
       number="002006" ayah="6" surah="2" d="M…"/>            <!-- hit region, UNFLIPPED frame -->
 …
</svg>
```

### The groups, and what each one means

| group | count (corpus) | meaning |
|---|---:|---|
| `<g id="ayah_markers">` | 604 | **all** ayah medallions of the page, in one layer, outside `#content`. See §9.1 — the ayah link on these is currently wrong. |
| `<g class="ayah-marker">` | 6,248 | one medallion: an ornament ring path + a numeral path. 6,236 carry `data-aid`; the other 12 are decorative rosettes on pages 1–2 with no ayah. |
| `<g id="content">` | 604 | all page text. |
| `<g class="line" data-line="N">` | 9,046 | one printed line. `N` is 1..15 (1..8 on pages 1–2). Its single child `<g transform="translate(…)">` carries the line's frame. |
| `<g class="ayah" data-aid="s:a">` | 13,510 | **one line's run of one ayah.** An ayah occupying three lines has three of these. Never treat it as "the ayah". |
| `<g class="word" data-wid="s:a:w">` | 77,432 | **one word. Globally unique. This is the anchor of the format.** |
| `<g class="ligature" data-text="…">` | 156,707 | a joined run of letters, as a rendering unit. Dev profile only. See §9.4 for its limits. |
| `<g class="surah-name" data-sid="N">` | 110 | the surah-name banner. **Missing for surahs 27, 33, 37, 47** — §9.2. |
| `<g class="basmalah" data-sid="N">` | 113 | the basmalah banner. 112 distinct surahs; surah 17's is split in two — §9.2. |
| `<g class="sajdah-mark" data-mark="sajdah" data-aid>` | 17 | the prostration sign (۩) and its overline. 15 sites; two are split into two groups — §8.5. |
| `<g class="hizb-mark" data-mark="hizb" …>` | 199 | a rubʿ / hizb / juz rosette (۞). 199 drawn for 240 boundaries — §8.6. |
| `<path class="ayahPolygon">` | 6,236 | invisible hit region per ayah, from the upstream artwork. **Outside the page frame** — §4.3. |

### Nesting rules

```
svg
└ g[transform=matrix …]              page frame
  ├ g#ayah_markers
  │ └ g.ayah-marker[data-aid]
  │   ├ g[transform] > path[data-kind=ayah-marker-ornament]
  │   └ g[transform] > path[data-kind=ayah-number]
  └ g#content
    └ g.line[data-line]
      └ g[transform]                 line frame
        ├ g.ayah[data-aid]
        │ └ g.word[data-wid]
        │   └ g.ligature[data-text]  (dev profile)
        │     └ path[data-kind]
        ├ g.surah-name | g.basmalah  → path[data-kind=header-ink] only
        ├ g.sajdah-mark              → path[data-mark=sajdah-sign|sajdah-line]
        └ g.hizb-mark                → path[data-mark=hizb]
path.ayahPolygon                     siblings of the page frame, at the end
```

---

## 4. Coordinates, frames and reading order

### 4.1 The page frame

| | pages 3–604 | pages 1–2 |
|---|---|---|
| `viewBox` | `0 0 345 550` (602 pages) | `-53.3109 -198.4777 345 550` |
| page frame | `matrix(1.3333 0 0 -1.3333 -55 640)` on odd pages, `… -115 640)` on even | `matrix(1.3333 0 0 -1.3333 -136 482)` |
| `<g class="line">` | 15 | 8 |

**The y scale is negative.** Inside the page frame, y increases *upward*.
Screen y = `640 − 1.3333 · y` on a normal page. A consumer computing positions
must apply the matrix; raw path coordinates are not viewBox coordinates.

The odd/even split means the same raw x is 60 units apart on recto and verso.
**Never compare raw coordinates across pages.**

### 4.2 The line frame

Each `<g class="line">` has exactly one child `<g transform="translate(x y)">`.
On **600 of 604 pages every line shares the same translate**, so it looks
redundant — but on pages 1, 2, 17 and 144 each line has its own. Always compose
`page frame × line frame`; never hoist the translate out.

To convert a path coordinate to viewBox space:

```
(x_view, y_view) = PAGE_MATRIX ∘ LINE_TRANSLATE applied to (x_path, y_path)
```

`docs/shipping/wordbox_poc.py` is a 157-line reference implementation.

### 4.3 The `ayahPolygon` layer is in a different frame

The 6,236 `<path class="ayahPolygon">` are **siblings of the page frame**, not
children of it. Their coordinates are plain, unflipped viewBox units. They also
come last in document order, so they sit on top and swallow pointer events —
set `pointer-events: none` on them, or remove them before calling `getBBox()`.

They use a second, legacy attribute vocabulary from the upstream artwork:
`id="verse-13" number="002006" ayah="6" surah="2"`, not `data-aid`. Both
identify the same ayah.

### 4.4 Reading order

- **Words within a line are in reading order.** Verified: on **9,046 of 9,046
  lines** the `data-wid` sequence is strictly ascending. Document order is
  reading order — right to left — and you should rely on it rather than on
  geometry (bounding boxes overlap, because a mark may legitimately be drawn
  over the neighbouring word: see §8.9).
- **Lines are in document order 1..15**, top to bottom.
- **Across line boundaries the sequence breaks on 51 pages, 54 times** — a word
  is emitted in the wrong `<g class="line">`. See §9.3.
- **Paths within a word are NOT yet ordered right to left.** Measured: only
  15,160 of 77,432 words (19.6 %) have their paths in descending x. Do not
  infer mark order from document order inside a word; use the path geometry.
  *(RTL element ordering is in progress; this section will change.)*

---

## 5. Attribute reference

Counts are over all 604 pages of the current build.

### 5.1 On `<g class="word">` — always present, all five

| attribute | count | format | example | notes |
|---|---:|---|---|---|
| `data-wid` | 77,432 | `surah:ayah:word`, 1-based | `2:6:3` | **The key.** Globally unique. Key on this. |
| `data-uthmani` | 77,432 | Arabic, full diacritics | `ٱلَّذِينَ` | The text of record. Composite source: quran.com `text_uthmani` + KFGQPC waqf + DigitalKhatt at iqlab sites (§8.7). |
| `data-rasm` | 77,432 | Arabic, diacritics stripped | `ٱلذين` | For rasm-level search and matching. |
| `data-imlaei` | 77,432 | Arabic, modern spelling | `الَّذِينَ` | For search by how a word is normally written. **Do not tokenise on it** — 4,933 values contain spaces by convention (§8.4). |
| `data-qpc` | 77,432 | Arabic, KFGQPC encoding | `ٱلَّذِينَ` | The QPC codepoints (e.g. `ۡ` U+06E1 for sukun, `ٗ ٞ ٖ` for tanween). |

The four text attributes **legitimately disagree** at iqlab sites and around
tanween (§8.7, §8.8). That is not corruption.

### 5.2 On `<g class="ayah">` and `<g class="ayah-marker">`

| attribute | count | format | notes |
|---|---:|---|---|
| `data-aid` | 20,191 | `surah:ayah` | On ayah groups (13,510), markers (6,236), sajdah groups (17+15 on paths), hizb groups (199). |

### 5.3 On `<g class="line">`

| attribute | count | format |
|---|---:|---|
| `data-line` | 9,046 | `1`–`15` (`1`–`8` on pages 1–2). The printed line number, top to bottom. |

### 5.4 On `<path>`

| attribute | count | values | notes |
|---|---:|---|---|
| `data-kind` | 616,561 | `mark` 436,708 · `body` 161,819 · `ayah-marker-ornament` 6,248 · `ayah-number` 6,236 · `header-ink` 5,550 | **Always present on every path except `ayahPolygon`.** `body` = letter ink. |
| `data-mark` | 436,706 (paths) | 34 names, §6 | Present on every `data-kind="mark"` path but **two**: one unnamed (p1 `e34`) and one carrying `data-mark-part` instead (p146). |
| `data-mark-family` | 122,203 | `dots` 105,282 · `tanween` 8,554 · `waqf` 4,272 · `sifr` 4,054 · `sajdah` 30 · `reading-sign` 11 | Only on marks that have a family. **Derivable from `mark-taxonomy.json`** — prefer the registry. Dropped in the production profile. |
| `data-eid` | 598,527 | `e1`, `e2`, … | **DEV ONLY. Not stable across builds. Never key on it.** Unique within a page. |
| `data-sig` | 598,512 | 16 hex | **DEV ONLY.** Outline shape signature used by the review loop. Not an identity: one signature can serve two mark names, and two names can share a signature (§7.5). |
| `data-form` | 8,506 | `stacked` 1,908 · `staggered` 6,598 | Only on the `tanween` family: how the pair of strokes is drawn. |
| `data-iqlab` | 940 | `iq-<surah>-<ayah>-<word>` | Links a haraka to its small meem at an iqlab site. **Incomplete — §9.5.** |
| `data-pair` | 6 | `mnq-<surah>-<ayah>-<n>` | Links the two halves of a muʿānaqah. Exactly 6 in the corpus (§8.3). |
| `data-standalone` | 229 | `1` | Marks that belong to no word: 199 hizb + 30 sajdah. |
| `data-mark-part` | 1 | `three-dots` | A path that is part of a mark named on another path (p146 `6:141:14`). See §9.6. |
| `data-aid` | — | `surah:ayah` | Also on sajdah and hizb paths. |
| `fill` / `fill-rule` | all ink | `#231f20` / `evenodd` | Every path in the mushaf is the same colour. |

### 5.5 On `<g class="surah-name">` and `<g class="basmalah">`

| attribute | count | example |
|---|---:|---|
| `data-sid` | 223 | `2` |
| `data-surah-name-ar` | 223 | `البقرة` |
| `data-surah-name-latin` | 223 | `Al-Baqarah` |
| `data-surah-name-en` | 223 | `The Cow` |
| `data-revelation-place` | 223 | `makkah` / `madinah` |
| `data-ayah-count` | 223 | `286` |

Real fragment:

```xml
<g class="surah-name" data-sid="2" data-surah-name-ar="البقرة"
   data-surah-name-latin="Al-Baqarah" data-surah-name-en="The Cow"
   data-revelation-place="madinah" data-ayah-count="286">
```

**These attributes appear only on a surah's first page.** To know the surah of
an arbitrary page, use `index.json` (or the surah number in any `data-wid`).

### 5.6 On `<g class="hizb-mark">`

```xml
<g class="hizb-mark" data-mark="hizb" data-aid="2:75"
   data-rub="5" data-rub-in-hizb="1" data-nisf="1" data-hizb="2" data-juz="1">
  <path data-eid="e268" data-kind="mark" data-mark="hizb"
        data-standalone="1" data-aid="2:75" d="…"/></g>
```

| attribute | count | meaning |
|---|---:|---|
| `data-rub` | 199 | rubʿ number 1..240 |
| `data-rub-in-hizb` | 199 | 1..4 |
| `data-nisf` | 199 | half of the hizb, 1 or 2 |
| `data-hizb` | 199 | 1..60 |
| `data-juz` | 199 | 1..30 |
| `data-juz-start` / `data-hizb-start` / `data-nisf-start` / `data-rub-start` | 73 / 141 / 168 / 671 | present when this point starts that division |

---

## 6. The mark taxonomy — all 34 emitted names

Codepoints are what appears in `data-uthmani`. Families are what
`mark-taxonomy.json` declares; `category` is the registry's grouping.

### 6.1 Harakat (vowels and their companions)

| `data-mark` | Arabic | codepoint | family | count |
|---|---|---|---|---:|
| `fatha` | فتحة | U+064E `َ` | — | 123,074 |
| `kasra` | كسرة | U+0650 `ِ` | — | 46,089 |
| `damma` | ضمة | U+064F `ُ` | — | 37,454 |
| `sukun` | سكون | U+0652 `ْ`, U+06E1 `ۡ` | — | 37,156 |
| `shadda` | شدة | U+0651 `ّ` | — | 22,685 |

### 6.2 Tanween — always `data-mark-family="tanween"`, always `data-form`

| `data-mark` | Arabic | codepoint | count |
|---|---|---|---:|
| `fathatan` | تنوين فتح | U+064B `ً`, **U+08F0 `ࣰ`** | 3,635 |
| `kasratan` | تنوين كسر | U+064D `ٍ`, **U+08F2 `ࣲ`** | 2,534 |
| `dammatan` | تنوين ضم | U+064C `ٌ`, **U+08F1 `ࣱ`** | 2,385 |

### 6.3 Letter dots — always `data-mark-family="dots"`

| `data-mark` | count | notes |
|---|---:|---|
| `dot` | 63,619 | one dot |
| `two-dots` | 38,124 | drawn as one path |
| `three-dots` | 3,538 | drawn as one path |

Dots are the letters' own dots (nuqaṭ), not diacritics — but in this schema
they are `data-kind="mark"`. A hamza seat (`ئ ؤ أ إ`) is drawn **without** the
dots of its base letter.

### 6.4 Orthographic signs

| `data-mark` | Arabic | codepoint | count | notes |
|---|---|---|---:|---|
| `hamza` | همزة | U+0621 `ء` and the seats U+0623/0625/0624/0626, U+0654/0655 | 16,388 | **Identical ink to a letter-hamza** — §7.2 |
| `wasla` | همزة وصل | U+0671 `ٱ` | 13,495 | |
| `small-alef` | ألف خنجرية | U+0670 `ٰ` | 9,726 | |
| `maddah` | مدة | U+0653 `ٓ`, U+06E4 `ۤ` | 5,376 | |
| `small-waw` | واو صغيرة | U+06E5 `ۥ` | 1,257 | pronominal suffix — §8.10 |
| `small-ya` | ياء صغيرة | U+06E6 `ۦ`, U+06E7 `ۧ` | 995 | pronominal suffix — §8.10 |
| `small-noon` | نون صغيرة | U+06E8 `ۨ` | **1** | 21:88 only — §8.1 |

### 6.5 Dabt (recitation-aid signs)

| `data-mark` | Arabic | codepoint | family | count | notes |
|---|---|---|---|---:|---|
| `sifr-mustadir` | صفر مستدير | U+06DF `۟` | `sifr` | 3,988 | round zero: the letter is **not** pronounced, ever |
| `sifr-mustatil` | صفر مستطيل | U+06E0 `۠` | `sifr` | 66 | upright zero: not pronounced in waṣl, pronounced in waqf. **A different sign with different rules** |
| `meem-iqlab` | ميم الإقلاب | U+06E2 `ۢ` (high) ×510, U+06ED `ۭ` (low) ×99 | — | 609 | §8.7 |

### 6.6 Waqf (pause) signs — always `data-mark-family="waqf"`

Verified empirically by pairing each word's waqf codepoint with its emitted
mark name over all 604 pages.

| `data-mark` | codepoint | conventional name | count |
|---|---|---|---:|
| `waqf-jaiz` | U+06DA `ۚ` | جائز — pausing permitted | 2,083 |
| `wasl-awla` | U+06D6 `ۖ` | صلى — continuing is better | 1,651 |
| `waqf-awla` | U+06D7 `ۗ` | قلى — pausing is better | 511 |
| `waqf-lazim` | U+06D8 `ۘ` | لازم — pause obligatory | 21 |
| `muanaqah` | U+06DB `ۛ` | معانقة — stop at one of a pair | 6 |

**Note the names are the ACTION, not the letters of the sign.** U+06D6 (ۖ,
"ṣalā") is emitted as `wasl-awla`, and U+06D7 (ۗ, "qilā") as `waqf-awla`. Map
by this table, not by the sign's Arabic abbreviation.

**U+06D9 `ۙ` (لا, "do not stop") does not occur in this print** — zero
occurrences in the text, zero marks. `waqf-mamnu` is reserved in the registry
with `active: false`.

`pause` appears in the registry as a legacy fallback name and is **never
emitted** (0 occurrences).

### 6.7 Reading signs — `data-mark-family="reading-sign"`

Each of these occurs at a handful of sites, named **by site, not by shape**
(§8.1).

| `data-mark` | Arabic | codepoint | count |
|---|---|---|---:|
| `saktah` | سكتة | U+06DC `ۜ` | 5 |
| `seen-reading` | سين القراءة | U+06DC `ۜ`, U+06E3 `ۣ` | 3 |
| `imalah` | إمالة | U+06EA `۪` | 1 |
| `ishmam` | إشمام | U+06EC `۬` | 1 |
| `tashil` | تسهيل | U+06EC `۬` | 1 |

### 6.8 Standalone signs (belong to no word — `data-standalone="1"`)

| `data-mark` | Arabic | family | count |
|---|---|---|---:|
| `sajdah-sign` | ۩ | `sajdah` | 15 |
| `sajdah-line` | the overline | `sajdah` | 15 |
| `hizb` | ۞ | — | 199 |

`sajdah` and `hizb` also appear as **group-level** `data-mark` (17 and 199).

---

## 7. Five things a drawing cannot tell you

These cost this project more time than anything else. They are properties of
Arabic orthography and of this print, not quirks of the file.

### 7.1 `fatha` and `kasra` are the SAME STROKE, named by position

So are `fathatan`/`kasratan`, and `damma`/`dammatan`. The name comes from
where the stroke sits relative to the word's letters and from the word's
spelling — nothing in the outline distinguishes them. Two consequences:

- a mark that is mis-owned always arrives wearing the **opposite** name: a
  stolen fatha hangs below its new holder's letters and is therefore called
  `kasra`. If you see a "kasra" above the letters, the name is a symptom, not a
  second fact.
- you cannot infer a mark's name from its `data-sig`. `d7a8b5e19121fbe4` is
  `kasra` in one word and `fatha` in another, in the same page.

### 7.2 `hamza` and a letter-hamza are IDENTICAL ink

`data-mark="hamza"` is a diacritic. A hamza that is a *letter* of the word is
`data-kind="body"`. The ink is the same; only the spelling decides. If you
count `[data-mark="hamza"]` you are counting diacritic hamzas only, which is
usually what you want — but it is not "all hamzas drawn on the page".

At two sites the print draws the hamza **fused to its alif as one contour**
(21:28:4 on p324, 22:76:4 on p341). The ruling is: name it `hamza`, never cut
it. Consequence: the `<g class="ligature" data-text="ا">` there holds **no
`data-kind="body"` path** — the alif's ink *is* the hamza path.

### 7.3 Composite marks: one outline, two marks

One drawn outline can carry two marks (`fatha+hamza`, `damma+shadda`). These
are handled internally and **no `+`-compound name survives into the emitted
files** — verified, zero occurrences. But it is why counting *paths* is not the
same as counting *signs*: see §7.4.

### 7.4 Path count ≠ sign count

- **Fused pairs.** Two slash strokes drawn touching share one path, so the pair
  counts once.
- **Split signs.** A sign whose contours the artwork put in different paths
  emits as more than one path. Exactly one such case survives
  (`data-mark-part`, p146) — see §9.6.
- **Muʿānaqah is ONE sign of three dots**, and it comes in **pairs** across two
  words. Three pairs mushaf-wide = 6 emitted `muanaqah` paths. **Do not count
  six signs, and do not count three dots per sign.**

If you need exact sign counts, use the annotation records rather than the
paths.

### 7.5 A `data-sig` is not an identity

The signature is the outline's shape. One signature serves several meanings and
one meaning has several signatures:

- `d2506e4f8b4e28e5` is a plain letter `dot` **and** three of the six
  `muanaqah` paths. The outlines are the same circle.
- `meem-iqlab`: all 510 high-form meems share `a8dfd9e5f7bb5cd5`, and so do 78
  of the 99 low-form ones. High vs low is only recoverable from the word text.

`data-sig` ships in the dev profile for the review loop. **A consumer should
not use it.**

---

## 8. Special cases

Every one is verified in a real page. Page numbers and `data-wid` keys are
exact.

### 8.1 Once-in-the-mushaf signs — and the same character meaning two things

| sign | `data-mark` | sites |
|---|---|---|
| saktah | `saktah` | p293 `18:1:11` عِوَجَاۜ · p443 `36:52:6` مَّرْقَدِنَاۜۗ · p567 `69:28:4` مَالِيَهْۜ · p578 `75:27:2` مَنْۜ · p588 `83:14:2` بَلْۜ |
| seen-for-sad | `seen-reading` | p39 `2:245:14` وَيَبْصُۜطُ · p159 `7:69:22` بَصْۜطَةࣰۖ · p525 `52:37:7` ٱلْمُصَۣيْطِرُونَ |
| imalah | `imalah` | p226 `11:41:6` مَجْر۪ىٰهَا |
| ishmam | `ishmam` | p236 `12:11:6` تَأْمَ۬نَّا |
| tashil | `tashil` | p481 `41:44:9` ءَا۬عْجَمِىࣱّ |
| small noon | `small-noon` | p329 `21:88:7` نُـۨجِى |

**U+06DC is a `saktah` at five sites and a `seen-reading` at two.** **U+06EC is
`ishmam` at 12:11 and `tashil` at 41:44.** The same character, two names, and
the drawing is the same. **Never map a codepoint to a mark name from a Unicode
table.** Trust `data-mark`, or key on (surah, ayah).

At 52:37 `data-uthmani` writes U+06E3 (seen below) but `data-qpc` writes
U+06DC — so `data-qpc` has eight U+06DC sites, not seven.

```xml
<g class="word" data-wid="21:88:7" data-uthmani="نُـۨجِى" data-rasm="ننجى"
   data-imlaei="نُنْجِي" data-qpc="نُـۨجِي">
```

### 8.2 Pages 1 and 2 are the opening spread

Different `viewBox`, different page matrix, **8 lines instead of 15**, and the
medallion scale is `0.0075` instead of `0.011`. They also carry **12
`<g class="ayah-marker">` groups with no `data-aid` and no numeral** — the
decorative rosettes of the frame (7 on p1, 5 on p2). So
`querySelectorAll('.ayah-marker')` returns 14 on a 7-ayah page.

### 8.3 Muʿānaqah — one sign, three dots, in pairs

`data-pair` links the two halves. It occurs exactly 6 times in the corpus.

```xml
<g class="word" data-wid="2:2:4" data-uthmani="رَيْبَۛ" …>
  <path data-eid="e32" data-kind="mark" data-mark="muanaqah" data-mark-family="waqf"
        data-sig="a482216d539513a5" data-pair="mnq-2-2-1" d="…"/>
<g class="word" data-wid="2:2:5" data-uthmani="فِيهِۛ" …>
  <path data-eid="e38" data-kind="mark" data-mark="muanaqah" data-mark-family="waqf"
        data-sig="a349de70f401f061" data-pair="mnq-2-2-1" d="…"/>
```

| pair | page | words |
|---|---|---|
| `mnq-2-2-1` | 2 | `2:2:4` ↔ `2:2:5` |
| `mnq-5-26-1` | 112 | `5:26:4` ↔ `5:26:6` (two words apart) |
| `mnq-5-41-1` | 114 | `5:41:16` ↔ `5:41:19` (three words apart) |

The partners are **not adjacent**. Join on `data-pair`, never on proximity, and
never on the drawing — three of the six share the plain-`dot` signature.

### 8.4 `إِلْ يَاسِينَ` — a word token containing a SPACE

Exactly one in the whole corpus: p451, `data-wid="37:130:3"`.

```xml
<g class="word" data-wid="37:130:3" data-uthmani="إِلْ يَاسِينَ" data-rasm="إل ياسين"
   data-imlaei="إِلْ يَاسِينَ" data-qpc="إِلۡ يَاسِينَ">
  <g class="ligature" data-text="ا">…</g>
  <g class="ligature" data-text="ل">…</g>
  <g class="ligature" data-text="يا">…</g>
  <g class="ligature" data-text="سين">…</g></g>
```

The space breaks the Arabic join, so it draws four runs — but **no attribute
says where the word break falls**; concatenating the four `data-text` values
gives `الياسين`.

Space census over all 604 pages, all five text attributes:

| attribute | tokens containing a space |
|---|---:|
| `data-uthmani` | **1** (this one) |
| `data-rasm` | **1** |
| `data-qpc` | 209 — 199 are the `۞ ` prefix, 9 a spaced trailing waqf sign, 1 this word |
| `data-imlaei` | 4,933 — an imlaei convention (`رَيْبَ ۛ`, `يَا أَيُّهَا`), **not word boundaries** |
| `data-text` (ligature) | 0 |

**Never tokenise a page by splitting text on whitespace.** `data-wid` is the
only word key. Related: `بَعْدَ مَا` (2:181 p27, 8:6 p177, 13:37 p254) is
**two words** in this print's segmentation, not one spaced token.

### 8.5 Sajdah — 15 places, 30 paths, 17 groups

The sign (۩) and the overline belong together and are `data-standalone="1"` —
they are **never** inside a word.

```xml
<!-- p176, complete -->
<g class="sajdah-mark" data-mark="sajdah" data-aid="7:206">
  <path data-eid="e1008" data-kind="mark" data-mark="sajdah-sign" data-mark-family="sajdah"
        data-standalone="1" data-aid="7:206" d="…"/>
  <path data-eid="e1009" data-kind="mark" data-mark="sajdah-line" data-mark-family="sajdah"
        data-standalone="1" data-aid="7:206" d="…"/></g>
```

The 15 sites: p176 (7:206), p251 (13:15), p272 (16:50), p293 (17:109), p309
(19:58), p334 (22:18), p341 (22:77), p365 (25:60), p379 (27:24 + 27:26), p416
(32:15), p454 (38:24), p480 (41:37 + 41:38), p528 (53:62), p589 (84:21), p598
(96:19).

**Two sites are split into two groups with different `data-aid`** (p379, p480)
— see §9.7. **Count `data-mark="sajdah-sign"` (15), not the groups (17).**

Note the print draws the 96:19 sajdah on **p598**, not p597.

### 8.6 Hizb / rubʿ — 199 rosettes for 240 boundaries

All 41 missing rosettes fall on an ayah 1 — a surah start, where the banner
marks the division instead. Verified 41 of 41, both directions, no exceptions.

The rubʿ character U+06DE `۞` **is in the word text but never in the word's
ink**: 199 words carry it in `data-uthmani`/`data-qpc`/`data-imlaei`, while the
rosette is a standalone path in its own `<g class="hizb-mark">`.

```xml
<g class="word" data-wid="2:26:1" data-uthmani="۞إِنَّ" data-rasm="إن"
   data-imlaei="۞ إِنَّ" data-qpc="۞ إِنَّ">…</g>
```

**Strip U+06DE before matching word text.** Note the space is present in
`data-qpc`/`data-imlaei` and absent in `data-uthmani`.

### 8.7 Iqlab: ONE haraka + a small meem, not tanween + meem

This print writes a single vowel plus a small م. 609 sites: **510 high form
(U+06E2 ۢ) and 99 low form (U+06ED ۭ)**; the low form is often fused into
neighbouring ink.

```xml
<!-- p104, high form -->
<g class="word" data-wid="4:165:9" data-uthmani="حُجَّةُۢ" data-rasm="حجة"
   data-imlaei="حُجَّةٌ" data-qpc="حُجَّةُۢ">
  <path data-eid="e404" data-kind="mark" data-mark="damma"      data-iqlab="iq-4-165-9" d="…"/>
  <path data-eid="e405" data-kind="mark" data-mark="meem-iqlab" data-iqlab="iq-4-165-9" d="…"/></g>

<!-- p85, low form -->
<g class="word" data-wid="4:41:6" data-uthmani="أُمَّةِۭ" data-imlaei="أُمَّةٍ" data-qpc="أُمَّةِۭ">
  <path data-eid="e405" data-kind="mark" data-mark="kasra"      data-iqlab="iq-4-41-6" d="…"/>
  <path data-eid="e406" data-kind="mark" data-mark="meem-iqlab" data-iqlab="iq-4-41-6" d="…"/></g>
```

Three consequences:

1. **`data-uthmani` here is deliberately NOT quran.com's `text_uthmani`.** It
   writes `ُ` / `ِ` where quran.com writes `ٌ` / `ٍ`, matching `data-qpc` and
   the ink. `data-imlaei` still carries the tanween. **The three attributes
   disagree on purpose at all 609 sites.**
2. **`data-mark="meem-iqlab"` does not say which form it is.** Take it from
   the word text.
3. `data-iqlab` pairs the haraka with the meem, but only at 335 of 605 sites —
   see §9.5.

### 8.8 Open tanween (U+08F0–U+08F2)

`data-uthmani` uses the open forms: U+08F0 `ࣰ` ×2,901, U+08F1 `ࣱ` ×1,807,
U+08F2 `ࣲ` ×1,935 (6,643 total). `data-qpc` uses the QPC forms instead
(`سَنَةٗ` where uthmani has `سَنَةࣰ`).

**These are not mojibake and not a non-standard encoding — they are this
print's orthography.** Normalise to families for comparison; never re-encode
the stored value.

Related: 926 words carry a tanween pair with **no** meem at ikhfa/idgham
positions where other texts write `ٌ`+`ۢ`. That is the same convention.

### 8.9 A mark can be drawn outside its word

The tanween of a word-final `ة` floats into the gap toward the next word. p350
`24:2:12`:

```xml
<g class="word" data-wid="24:2:12" data-uthmani="رَأْفَةࣱ" data-qpc="رَأۡفَةٞ">
  … <path data-eid="e197" data-kind="mark" data-mark="dammatan"
          data-mark-family="tanween" data-form="staggered" d="…"/></g>
```

**Never assign a mark to a word by nearest ink or by bounding-box
containment.** The `data-wid` of the enclosing group is the answer.

The same holds at 90:4-ish sites where a kasratan is drawn **inside the bowl of
a ج** (p90 `بروج`) — an art fact of this print.

### 8.10 The pronominal suffix's small waw and small ya

`ـهُۥ` / `ـهِۦ`. These are `data-mark="small-waw"` / `"small-ya"` — **marks,
not letters** — and they sit clear of their own word's ink, always **nearer the
next word**.

```xml
<g class="word" data-wid="16:48:10" data-uthmani="ظِلَٰلُهُۥ" data-rasm="ظلله"
   data-imlaei="ظِلَالُهُ" data-qpc="ظِلَٰلُهُۥ">
 <g class="ligature" data-text="ظلله">
  … <path data-eid="e536" data-kind="mark" data-mark="small-waw" d="…"/></g></g>
```

`data-rasm` has no waw; `data-imlaei` drops the ۥ entirely.

### 8.11 The silent alef of واو الجماعة

The alef **is** drawn — a `data-kind="body"` path of its own. The round zero
that marks it silent (`sifr-mustadir`, U+06DF) is emitted in the **previous**
ligature group, not on the alef.

```xml
<g class="word" data-wid="2:70:1" data-uthmani="قَالُوا۟" data-qpc="قَالُواْ">
 <g class="ligature" data-text="قا">…</g>
 <g class="ligature" data-text="لو">
  <path data-eid="e4" data-kind="body" d="…"/>
  <path data-eid="e5" data-kind="mark" data-mark="damma" d="…"/>
  <path data-eid="e6" data-kind="mark" data-mark="sifr-mustadir" data-mark-family="sifr" d="…"/></g>
 <g class="ligature" data-text="ا"><path data-eid="e7" data-kind="body" d="…"/></g></g>
```

### 8.12 Header ink is not decomposed — and that is deliberate

5,550 paths carry `data-kind="header-ink"`: 2,211 inside `<g class="surah-name">`
and 3,339 inside `<g class="basmalah">`. **None of them carries `data-mark`.**
Banner ink is identified, never decomposed. A consumer iterating words will not
see it, and that is correct.

Marks that belong to no word: 229 legitimate (`data-standalone="1"`: 199 hizb +
30 sajdah) plus **79 that are a defect** — §9.2.

### 8.13 One calligraphic stroke can be two contours

Where the pen lifts mid-stroke, a single stroke is drawn as two contours
(`9:102:6 صَـٰلِحًۭا` p203, `9:20:9` p189, `10:92:2` p219). Their boxes
*overlap* end to end; genuinely separate pieces have a positive gap. **Contour
count is not piece count.**

---

## 9. Known limits and defects — stated honestly

### 9.1 The ayah-marker's `data-aid` is REVERSED on 441 pages — do not use it

Sorting each page's markers by `data-aid` and checking whether they run down
the page:

```
strictly REVERSED   441 pages
mixed                160 pages   (two markers on one line, not strictly monotonic)
strictly correct       2 pages   (84, 162)
```

On page 3 the marker labelled `data-aid="2:6"` is drawn at screen y 523.8 — the
bottom of the page — while ayah 2:6 occupies printed lines 1–2 at y ≈ 37–49.
The marker that actually closes 2:6 is labelled `2:16`.

**Until this is fixed, pair a marker with an ayah geometrically** (the marker
in the same line band, immediately left of the ayah's last word), or ignore the
markers.

### 9.2 Four surah banners are missing, and their basmalah ink is loose

`<g class="surah-name">` exists for **110 of 114 surahs**. Missing: **27, 33,
37, 47** (pages 377, 418, 446, 507). On those pages the *banner* is wrapped as
`<g class="basmalah">` and the *real basmalah* is emitted as bare paths
directly under the line group — 10–11 `body` paths and 19–20 named marks with
no word.

```xml
<!-- p377 line 2: the basmalah, unwrapped -->
<g class="line" data-line="2"><g transform="translate(152.3 442.76)">
  <path data-eid="e2" data-kind="mark" data-mark="wasla" d="…"/>
  <path data-eid="e4" data-kind="mark" data-mark="wasla" d="…"/>
  <path data-eid="e6" data-kind="mark" data-mark="fatha" d="…"/>
  …
```

Those 79 paths are the whole of the "named marks that belong to no word and
carry no `data-standalone`" population.

Separately, **surah 17's basmalah is split into two groups** on p282 (one
holding a single path), which is why there are 113 basmalah groups for 112
surahs.

### 9.3 54 words are in the wrong `<g class="line">`

Within a line the words are always in order (9,046/9,046). Across line
boundaries the reading sequence breaks 54 times on 51 pages. Confirmed
geometrically: p2 `2:4:11` is tagged line 7 but drawn in line 6's band; p8
`2:54:22` is tagged line 9 but drawn in line 10; p42 `2:255:23` is tagged line
11 but drawn in line 10.

Pages: 2, 8, 38, 42, 51, 56, 61, 77, 80, 86, 96, 103, 109, 110, 113, 114, 116,
122, 131, 137, 170, 182, 184, 199, 211, 212, 213, 214, 224, 231, 246, 269, 276,
317, 380, 381, 408, 427, 431, 435, 451, 454, 471, 475, 480, 510, 512, 542, 549,
552, 584.

**`data-line` is right for 77,378 of 77,432 words.** If you need certainty, use
the geometry.

### 9.4 The ligature layer is not a letter segmentation

Comparing each word's concatenated `data-text` against its `data-rasm`
(normalising hamza seats):

| | words |
|---|---:|
| document order reproduces the rasm | 76,725 (99.09 %) |
| groups in reversed order | 324 |
| groups in another permutation | 232 |
| groups spell **fewer** letters than the rasm | **151** |
| groups spell more letters than the rasm | 0 |

Examples: p15 `2:98:5` `وملئكته` emits one group `['و']`; p17 `2:110:2`
`ٱلصلوة` emits `['ا','لصلو']` and the `ة` has no group at all. 37 groups hold
zero `body` paths.

**Use `data-uthmani`/`data-rasm` on the word as the text of record.** Treat
`data-text` as a hint about which letters a group's ink covers, never as a
spelling, and never pair group *i* with letter run *i*.

The ligature layer is dropped in the production profile for this reason.

### 9.5 `data-iqlab` is incomplete

605 distinct ids over 940 paths. **335 sites** tag both the haraka and the meem;
**270 sites** tag only the meem, so the vowel it belongs with is unfindable.
**Four meems carry no `data-iqlab` at all** (p45 `2:265:12`, p446 `37:11:12`,
p455 `38:42:4`, p577 `74:51:3`), and p577's is also the only `meem-iqlab` in
the corpus with no `data-sig`.

### 9.6 Sole survivors of otherwise-uniform rules

A strict consumer must special-case these:

- **1 unnamed mark** — p1 `1:2:1` `ٱلْحَمْدُ`, `data-eid="e34"`:
  `data-kind="mark"` with no `data-mark`.
- **1 `data-mark-part`** — p146 `6:141:14` `مُتَشَٰبِهࣰا`: the ش's third dot
  emits as a second path carrying `data-mark-part="three-dots"` instead of
  `data-mark`. A consumer selecting `[data-mark]` misses its ink; one selecting
  `[data-kind="mark"]` finds a path with no name.
- **15 paths of 598,527 have no `data-sig`** (split or synthesised outlines).
- **`small-noon` is the only reading sign with no `data-mark-family`.**
  `[data-mark-family="reading-sign"]` silently drops it.
- **p7 is the only file declaring `xmlns:xlink`.**
- **p17 and p144 emit one `<g class="ayah">` per WORD**, not per (ayah, line):
  139 and 117 groups respectively. All 216 "reopened" ayah groups in the corpus
  are on these two pages.

### 9.7 Two sajdah groups are incomplete

p379 emits the An-Naml sajdah as two sibling `sajdah-mark` groups, one holding
only the line (`data-aid="27:24"`) and one only the sign (`data-aid="27:26"`).
p480 does the same with `41:37` / `41:38`. Neither `data-aid` on those four
groups is reliably the sajdah ayah.

### 9.8 Words split differently from other decompositions

About 9 word-level segmentation disagreements with MushafDatabase remain
(p11, p262 `لَّوۡمَا`, p451). Word boundaries otherwise agree on
**77,417 of 77,422** words, and line placement on **99.994 %**.

### 9.9 Element order inside a word is not right-to-left

Only 19.6 % of words have their paths in descending x. Word order within a
line is correct; path order within a word is not yet normalised.

### 9.10 The edition manifest's `surah_name_groups_emitted` is stale

It declares 108; the build emits 110. Validating a correct file against the
manifest will fail on that field.

---

## 10. Recipes

```js
// ---- highlight ayah 2:255 (all its line fragments) ----
doc.querySelectorAll('g.ayah[data-aid="2:255"] g.word')
   .forEach(w => w.querySelectorAll('path')
                  .forEach(p => p.setAttribute('fill', '#0a7')));

// ---- link to a word ----
// production files carry id="w-2-255-3" mirroring data-wid; until then:
doc.querySelector('g.word[data-wid="2:255:3"]');

// ---- extract the plain text of a printed line ----
[...doc.querySelectorAll('g.line[data-line="7"] g.word')]
  .map(w => w.dataset.uthmani).join(' ');

// ---- colour the dots differently from the harakat ----
// families come from mark-taxonomy.json; in the dev profile you can also use
// [data-mark-family="dots"]
doc.querySelectorAll('path[data-mark="dot"],path[data-mark="two-dots"],'
                   + 'path[data-mark="three-dots"]')
   .forEach(p => p.setAttribute('fill', '#b03030'));

// ---- crop to one ayah ----
// 1. remove path.ayahPolygon first (different frame, and it sits on top)
// 2. drop every g.word whose data-wid is not in the ayah
// 3. drop the now-empty g.ayah / g.line wrappers
// 4. getBBox() on #content, pad, write it back as the viewBox

// ---- every waqf sign on the page, with the word it belongs to ----
[...doc.querySelectorAll('path[data-mark-family="waqf"]')]
  .map(p => [p.closest('g.word')?.dataset.wid, p.dataset.mark]);

// ---- muanaqah partners ----
const id = p.dataset.pair;                    // "mnq-5-26-1"
doc.querySelectorAll(`path[data-pair="${id}"]`);   // exactly two
```

```python
# ---- search (index, no SVG needed) ----
rows = json.load(open("index/words.json"))["rows"]   # [wid, page, rasm, imlaei]
hits = [r for r in rows if r[2] == "الرحمن"]

# ---- which page is 2:255 on? ----
idx = json.load(open("index/index.json"))
def num(aid): s, a = aid.split(":"); return (int(s), int(a))
page = next(p["page"] for p in idx["page_index"]
            if num(p["first_ayah"]) <= (2, 255) <= num(p["last_ayah"]))

# ---- where is a word on the page? ----
boxes = json.load(open("index/wordboxes.json"))["pages"]["42"]
box   = next(b for b in boxes if b[0] == "2:255:3")   # [wid, line, x0, y0, x1, y1]
```

---

## 11. Reference facts, all measured

| fact | value |
|---|---|
| pages | 604 (602 with 15 lines, 2 with 8) |
| words / distinct `data-wid` | 77,432 / 77,432 |
| ayahs / `<g class="ayah">` groups | 6,236 / 13,510 |
| ayahs emitted as >1 group on their page | 4,458 |
| **ayahs spanning two pages** | **0 — every page begins and ends on an ayah boundary** |
| lines | 9,046 |
| paths | 622,801 |
| named marks | 436,706 |
| letter (`body`) paths | 161,819 |
| distinct `data-mark` values | 34 on paths (+2 group-level) |
| surahs with a `surah-name` group | 110 of 114 |
| basmalah groups / distinct surahs | 113 / 112 |
| hizb rosettes / rubʿ boundaries | 199 / 240 |
| sajdah signs / groups | 15 / 17 |
| page size, raw / gzip / brotli | 770 / 187 / 119 KiB average |
| corpus size, raw / gzip / brotli | 454.1 / 110.3 / 70.0 MiB |
