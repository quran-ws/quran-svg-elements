# Format specification — Quran page SVGs, Hafs / KFGQPC Madani

Edition id `hafs-kfgqpc` · 604 pages · 77,432 words · 6,236 ayahs · 114 surahs.
(37:130 is four words: the print writes `إِلْ` and `يَاسِينَ` apart —
`docs/MAQTU-MAWSUL.md`. The count of 77,432 includes that.)
Artwork: the **KFGQPC Madani mushaf, V4 1441H print**.

This document ships with the files. Everything in it was verified against the
real build. Where the files are inconsistent, this document says so (§10) rather
than describing an ideal that does not exist.

> **Status.** Build of **2026-11-22**, release **2.0.0**. It is published as
> **two bundles, side by side**: the **word bundle** (schema 1.0.0), whose pages
> are what this document described until now, and the **letter bundle**
> (schema 2.0.0), whose pages also divide every word into its letters
> (§6.9). A page says which it is in `data-decomposition` on its root (§6.6):
> `word` or `letter`. Two profiles exist (§2); every statement below says
> which bundle or profile it applies to when they differ.
>
> **New in this build.** The letter bundle: inside every `<g class="word">`
> one `<g class="letter">` per letter, with `data-index`, `data-text` and
> `data-at`, holding the letter's own ink and marks; cut outlines carry
> `data-cut="1"` (§6.5, §6.9, limits in §10.10). The division of joined
> strokes into letters is the output of **DigitalKhatt's
> medinamushafanalyzer** (commit `056191f`, MIT), joined onto this project's
> words; `NOTICE.md` carries the credit. It is a **breaking** change for a
> reader that selects `g.word > path`, which is why it is a separate bundle
> with a new major version. In **both** bundles: every word group carries
> `data-w` again (§6.1), and the word source is the quran-text release (§6.1).
> Corrected: `data-element-id` and `data-sig` are **dev-profile only**; the
> production pages carry neither (§6.5).
>
> This document carries no build counts; the counts of a release are in its
> release notes.
>
> Changes since the 2026-08-30 revision (see `FORMAT-CHANGES.md`): every page
> now uses `viewBox="0 0 345 550"` (§5.1); no `<path>` carries a `transform`
> (§5.2); every `<path>` carries `data-kind` (§6.5); the opening spread's
> doubled ornaments are inside their ayah's marker with correct ids (§9.2);
> absolute movetos are written to three decimals; the word and ayah keys are
> spelled out as `data-word-key` and `data-ayah-key` (they were `data-word-key` /
> `data-aid`), and `data-word-key` is now the ONLY word key — the cross-mushaf
> `data-w` was withdrawn (it is back from release 2.0.0, §6.1); and **the
> production profile carries `data-word-key`, `data-w` and `data-rasm-uthmani`
> only** on a word group — the other four
> text forms ship once, in `index/by-page/NNN.json` (§6.1).
>
> Changes in the 2026-08-30 revision: `data-search` added; ayah fragments and
> medallions linked by `id` / `data-mark`; medallion labels rebound by
> position; misfiled words returned to their printed line; the missing
> surah banners restored; the production profile introduced.

---

## 1. What these files are

Each file is one printed page of the mushaf, as **vector outlines**, with the
ink semantically decomposed:

- every **word** is exactly one `<g class="word">` — one group per word,
  every `data-word-key` distinct, **no duplicates anywhere in the corpus**;
- every **letter shape** is a `<path data-kind="body">`;
- every **diacritic and sign** is a `<path data-kind="mark" data-mark="…">`
  drawn from a closed vocabulary of 35 emitted names (§8).

The pages are **pixel-identical to the original print artwork** — the
decomposition regroups ink, it never moves or redraws it.

### What these files are NOT

- **There are no `<text>` elements.** All ink is paths. Browser find-in-page,
  text selection and copy of the Quranic text **do not work**. Search goes
  through `data-search` on the word groups (§6.1), or through a companion
  index built from them.
- **The word bundle has no letter-level decomposition.** The letter bundle
  does (§6.9). In either, the dev profile's `<g class="ligature">` grouping is
  a *rendering run*, not a spelling. It is not a letter segmentation — see
  §10.3 — and it is not in the production profile at all.
- **No audio, no translation, no tafsir, no word timings.**

---

## 2. The two profiles

The same pipeline emits two builds of every page. They are selected at build
time with `QSVG_PROFILE`; the files themselves do not announce which one they
are, so **tell them apart by whether `<g class="ligature">` is present**.

| | DEV (`QSVG_PROFILE=dev`, the default) | PRODUCTION (`QSVG_PROFILE=production`) |
|---|---|---|
| `<g class="word">` per word | 1 | 1 |
| marks as their own `<path data-mark>` | yes | yes |
| `<g class="ligature">` inside a word | **yes** | **dropped** |
| `<path class="ayahPolygon">` | **yes** — one per ayah | **dropped** |
| `data-rasm`, `data-rasm-imlai`, `data-search`, `data-qpc` on a word | **yes** | **dropped** — read them from `index/by-page/NNN.json` (§6.1) |
| `data-mark-family` | yes | yes |
| `data-element-id`, `data-sig` | yes | **dropped** |
| everything else in this document | identical | identical |

**The two render identically.** Measured on page 3: all words, all marks and
all ink paths are present in both, and a raster diff of the two shows no
difference. Size is not the reason for the split; semantics is.

```js
// which profile is this file?
const isDev = doc.querySelector('g.ligature') !== null;
```

### What production removes, and what replaces it

**The ligature layer.** It is a dev instrument: an empty `<g class="ligature">`
is how a stolen letter is detected. It is *not* a spelling of the word (§10.3),
so a consumer that treats it as one gets words wrong. The word's text of
record is `data-rasm-uthmani` on the `<g class="word">`, present in both profiles.

**The four derived text forms.** `data-rasm`, `data-rasm-imlai`, `data-search` and
`data-qpc` are a text index, not geometry: they never vary per instance, and
repeating them on every word group made every page larger. In
production they ship once, in `index/by-page/NNN.json` (every word, all five
forms, line and box) and `index/words.json` (the search key). The dev profile
keeps them inline because it is the review instrument.

**The invisible ayah polygons.** These were how ayah highlighting and
click-detection worked before there were word elements. Word level supersedes
both, **and is exact where the polygon is not**: the polygon is a rectangular
band cut on a straight vertical line, while the real boundary between two ayahs
that share a printed line is jagged — letters interleave and marks overhang.
**Elements can have ink sitting inside a *neighbouring* ayah's polygon**: on
page 3 a 22.1 × 1.0 unit piece of ayah 2:8 lies inside 2:9's polygon. Highlighting from
polygons paints part of the wrong ayah or misses ink of its own. Highlighting
from words cannot: **the ayah's ink *is* its words.**

Two conveniences do go away, and both are about ten lines of JS:

```js
// (a) CLICK / TAP -> which ayah?  Hit a word path, walk up.
svg.addEventListener('click', e => {
  const word = e.target.closest('g.word');
  if (!word) return;                       // tapped bare paper
  const ayah = word.closest('g.ayah-fragment');
  console.log(ayah.dataset.ayahKey, word.dataset.wordKey);   // "2:8"  "2:8:3"
});

// A tap in the GAP between two words of one ayah now hits nothing, which
// matters on touch. Widen the target instead of restoring the polygons —
// a transparent stroke behind the fill is still hit-tested, and changes
// no pixel:
//   g.word path { stroke: transparent; stroke-width: 1.5;
//                 paint-order: stroke fill; pointer-events: all; }

// (b) BAND HIGHLIGHT -> union the word boxes, one box per printed line.
function ayahBands(doc, aid) {
  const byLine = new Map();
  for (const w of doc.querySelectorAll(`g.ayah-fragment[data-ayah-key="${aid}"] g.word`)) {
    const ln = w.closest('g.line').dataset.line;
    const b  = w.getBBox();                // in the LINE frame; see §5.2
    const cur = byLine.get(ln);
    byLine.set(ln, cur
      ? {x: Math.min(cur.x, b.x), y: Math.min(cur.y, b.y),
         x2: Math.max(cur.x2, b.x + b.width),
         y2: Math.max(cur.y2, b.y + b.height)}
      : {x: b.x, y: b.y, x2: b.x + b.width, y2: b.y + b.height});
  }
  return [...byLine].map(([line, r]) =>
    ({line, x: r.x, y: r.y, w: r.x2 - r.x, h: r.y2 - r.y}));
}
// -> one rect per line the ayah occupies. Pad it and draw it behind the ink.
```

---

## 3. Quick start

```js
const doc = new DOMParser()
  .parseFromString(await (await fetch('pages/003.svg')).text(), 'image/svg+xml');

// the text of ayah 2:6, in reading order
[...doc.querySelectorAll('g.word')]
  .filter(w => w.dataset.wordKey.startsWith('2:6:'))
  .map(w => w.dataset.rasmUthmani).join(' ');
// => "إِنَّ ٱلَّذِينَ كَفَرُوا۟ سَوَآءٌ عَلَيْهِمْ …"

// highlight the whole ayah (NOTE: several fragments — one per printed line)
doc.querySelectorAll('g.ayah-fragment[data-ayah-key="2:6"]').forEach(g => g.classList.add('hl'));

// one word
doc.querySelector('g.word[data-word-key="2:6:3"]');

// search: use data-search — but fold BOTH sides, never compare raw.
// data-search keeps أ/ة/ى as modern spelling writes them, so a raw === misses
// انعمت against the stored أنعمت. See docs/SEARCH-FOLD.md.
const fold = s => s.normalize('NFKC')
  .replace(/[\p{Mn}\p{Me}\p{Lm}\p{Sk}\p{So}\p{Cf}]/gu, '')
  .replace(/[\u0671\u0623\u0625\u0622]/gu, '\u0627')
  .replace(/[\u0649\u0626]/gu, '\u064A')
  .replace(/\u0624/gu, '\u0648').replace(/\u0629/gu, '\u0647');
const q = fold('الذين');
// `data-search` exists in the DEV profile only — it is dropped from the
// published bundle (see the profile table in §2). Against a released bundle,
// read `search` from index/by-page/NNN.json instead; §6.1 has that form.
[...doc.querySelectorAll('g.word')].filter(w => fold(w.dataset.search) === q);
```

---

## 4. Document structure

A real fragment of `pages/003.svg`, `d=` values trimmed, dev profile:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:ayah="https://quranpedia.net"
     version="1.1" viewBox="0 0 345 550" xml:space="preserve">

 <g transform="matrix(1.3333 0 0 -1.3333 -55 640)">        <!-- page frame; y is FLIPPED -->

  <g id="ayah_markers" class="ayah_markers">               <!-- all medallions, one layer -->
   <g class="ayah-mark" id="mk-2-16" data-ayah-key="2:16">
    <g transform="translate(45.272 87.116) scale(0.011 -0.011)">
     <path data-kind="ayah_mark_ornament" d="m1248,4q…" fill="#231f20"/></g>
    <g transform="translate(49.652 83.898)" ayah:x="14.53" ayah:y="530.03">
     <path data-kind="ayah_number" fill="#231f20" fill-rule="evenodd" d="M…"/></g>
   </g>
   …
  </g>

  <g id="content">
   <g class="line" data-line="1">
    <g transform="translate(206.04 112.26)">               <!-- the LINE's own frame -->
     <g class="ayah-fragment" data-ayah-key="2:6" data-ayah-mark="mk-2-6" data-fragment="1" data-ayah-fragments="2">
      <g class="word" data-word-key="2:6:1" data-rasm-uthmani="إِنَّ" data-rasm="إن"
                      data-rasm-imlai="إِنَّ" data-search="إن" data-qpc="إِنَّ">
       <g class="ligature" data-text="ا">
        <path data-element-id="e1" data-kind="mark" data-mark="kasrah"
              data-sig="b631f71b4956be63" d="M84.59 339.69…"
              fill="#231f20" fill-rule="evenodd"/>
        <path data-element-id="e2" data-kind="mark" data-mark="hamzah"
              data-sig="47c49c400b93c632" d="M81.21 341.31…"
              fill="#231f20" fill-rule="evenodd"/></g>
       …
      </g>
     </g>
    </g>
   </g>
   …                                                        <!-- 15 lines -->
  </g>
 </g>

 <path class="ayahPolygon" fill-opacity="0" id="ayah-13"
       number="002006" ayah="6" surah="2" d="M…"/>          <!-- dev only; UNFLIPPED frame -->
 …
</svg>
```

### The groups, and what each one means

| group | meaning |
|---|---|
| `<g id="ayah_markers">` | **all** ayah medallions of the page, in one layer, outside `#content`. |
| `<g class="ayah-mark" id="mk-s-a">` | one medallion: an ornament ring path + a numeral path, one per ayah, every one with `id` + `data-ayah-key`. |
| `<g id="content">` | all page text. |
| `<g class="line" data-line="N">` | one printed line. `N` is 1..15 (1..8 on pages 1–2). Its single child `<g transform="translate(…)">` carries the line's frame. **A line holds words or is a header line** (surah-name or basmalah). |
| `<g class="ayah-fragment" data-ayah-key="s:a">` | **one line's run of one ayah.** An ayah on three lines has three of these. Never treat one as "the ayah" — §7. |
| `<g class="word" data-word-key="s:a:w">` | **one word. Globally unique. This is the anchor of the format.** |
| `<g class="letter" data-index data-text data-at>` | **one letter** of a word, with its own body ink and marks. **Letter bundle only** — §6.9. |
| `<g class="ligature" data-text="…">` | a joined run of letters, as a rendering unit. **Dev profile only.** See §10.3 for its limits. |
| `<g class="surah-name" data-sid="N">` | the surah-name banner. One per surah, all 114 present. |
| `<g class="basmalah" data-sid="N">` | the basmalah banner. Absent only for **surah 1** (its basmalah IS ayah 1:1) and **surah 9** (which has none). |
| `<g class="sajdah-mark" data-mark="sajdah" data-ayah-key>` | the sajdah sign (۩) and its overline, one group per site — §9.5. |
| `<g class="division-mark" data-mark="hizb" …>` | a rubʿ / hizb / juz rosette (۞). 199 drawn for 240 boundaries — §9.6. |
| `<path class="ayahPolygon">` | invisible legacy hit region per ayah, from the upstream artwork. **Dev profile only**, and **outside the page frame** — §5.3. Do not build on it; see §2. |

### Nesting rules

```
svg
├ g[transform=matrix …]              page frame
│ ├ g#ayah_markers
│ │ └ g.ayah-mark[id][data-ayah-key]
│ │   ├ g[transform] > path[data-kind=ayah_mark_ornament]
│ │   └ g[transform] > path[data-kind=ayah_number]
│ └ g#content
│   └ g.line[data-line]
│     └ g[transform]                 line frame
│       ├ g.ayah-fragment[data-ayah-key][data-ayah-mark][data-fragment][data-ayah-fragments]
│       │ └ g.word[data-word-key]
│       │   ├ g.ligature[data-text]  (word bundle, dev profile only)
│       │   │ └ path[data-kind]
│       │   ├ g.letter[data-index]   (letter bundle only, §6.9)
│       │   │ └ path[data-kind]      the letter's body, then its marks
│       │   └ path[data-kind=mark]   (letter bundle: a mark of the word, not of one letter)
│       ├ g.surah-name | g.basmalah  → path[data-kind=header_ink] only
│       ├ g.sajdah-mark              → path[data-mark=sajdah_mark|sajdah_line]
│       └ g.division-mark                → path[data-mark=hizb]
└ path.ayahPolygon                   siblings of the page frame, at the end (dev only)
```

`g.word` is always inside `g.ayah-fragment`, which is always inside a line frame inside
`g.line`. There is **no** case of a word outside an ayah group, and (since
2026-08-30) no named mark loose on a text line outside any group.

---

## 5. Coordinates, frames and reading order

### 5.1 The page frame

| | pages 3–604 | pages 1–2 |
|---|---|---|
| `viewBox` | `0 0 345 550` | `0 0 345 550` |
| page frame | `matrix(1.3333 0 0 -1.3333 -55 640)` on odd pages, `… -115 640)` on even | `matrix(1.3333 0 0 -1.3333 -82.6891 680.4777)` |
| `<g class="line">` | 15 | 8 |

**Every page uses the same viewBox** since 2026-09-04. The artwork draws the
opening spread under `-53.3109 -198.4777 345 550`; the emitter folds that offset
into the page frame's translation (and into `ayah:x` / `ayah:y`), which renders
pixel-identically and leaves raw path coordinates untouched. Word boxes in
`index/by-page/001.json` and `002.json` are in the normalised frame.

**The y scale is negative.** Inside the page frame, y increases *upward*.
Screen y = `640 − 1.3333 · y` on a normal page. A consumer computing positions
must apply the matrix; raw path coordinates are not viewBox coordinates.

The odd/even split means the same raw x is 60 units apart on recto and verso.
**Never compare raw coordinates across pages.**

### 5.2 The line frame

Each `<g class="line">` has exactly one child `<g transform="translate(x y)">`.
On every page except **1, 2, 17 and 144** every line shares the same
translate, so it looks redundant — but on those four pages the lines differ.
Always compose
`page frame × line frame`; never hoist the translate out.

```
(x_view, y_view) = PAGE_MATRIX ∘ LINE_TRANSLATE applied to (x_path, y_path)
```

`tools/bundle_geom.py` (exact Bezier extents) and `tools/bundle_extract.py`
are the reference implementation. **No `<path>` carries a `transform`**: the
ink paths on p17 and p144 that used to (ink regrouped from another source
path's frame) now have the translation baked into their absolute movetos,
which a raster diff proves pixel-identical. In a browser, `getBBox()` on a
`g.word` already returns coordinates in that word's own line frame;
`getCTM()` composes the rest.

Absolute movetos are written to at most three decimals: the artwork's relative
segments have three, so a contour's start is a three-decimal number plus float
noise, and the noise is not written.

### 5.3 The `ayahPolygon` layer is in a different frame (dev profile only)

The `<path class="ayahPolygon">` elements are **siblings of the page frame**, not
children of it. Their coordinates are plain, unflipped viewBox units. They also
come last in document order, so they sit on top and swallow pointer events —
set `pointer-events: none` on them, or remove them before calling `getBBox()`.
The production profile does not have them, which is one reason to prefer it.

They use a second, legacy attribute vocabulary from the upstream artwork:

```xml
<path class="ayahPolygon" fill-opacity="0" id="ayah-13"
      number="002006" ayah="6" surah="2" d="M…"/>
```

`number` is `%03d%03d` of surah and ayah. Both vocabularies name the same ayah;
`data-ayah-key` is the one to use. **These polygons are an approximation — see §2.**

### 5.4 Reading order

- **Words within a line are in reading order.** Verified: on **every line
  that holds words** the `data-word-key` sequence is strictly ascending.
  Document order is reading order — right to left — and you should rely on it
  rather than on geometry (bounding boxes overlap, because a mark may
  legitimately be drawn over the neighbouring word: see §9.9).
- **Lines are in document order 1..15**, top to bottom.
- **Across line boundaries the sequence is now unbroken on all 604 pages.**
  Concatenating a page's words line by line gives the mushaf's own word order
  exactly. (Until 2026-08-30, words could be emitted inside the wrong
  `<g class="line">`; none are any more.)
- **Standalone signs sit in reading order around their ayah** (changed
  2026-08-31 — before that they came out wherever the ink pass reached them,
  and rosettes were emitted *after* words of their own ayah).
  A `g.division-mark` opens a division, so it is emitted immediately **before** the
  first element of the ayah named by its `data-ayah-key` (in the letter bundle,
  as the first child of that ayah's first word — §9.6); a `g.sajdah-mark` closes
  its ayah, so it is emitted immediately **after** that ayah's last element.
  Verified for every rosette and every sajdah group. On p309 the two
  meet and read `…19:58 words · sajdah-mark 19:58 · division-mark 19:59 · 19:59
  words…`. A sign whose ayah has no ink in the same source-path wrapper is
  left where it was; there are none in this build.
- **The `#ayah_markers` layer is NOT in reading order.** Every medallion lives
  in one ornament layer near the top of the document, in *descending* ayah
  order — it is the artwork's own layer and is untouched. Reach a marker from
  its ayah through `data-mark` / `id="mk-S-A"` (§7), never by document
  position.
- **Paths within a word are NOT ordered right to left.** Most words do not
  have their paths in descending x. Do not infer mark order from document
  order inside a word; use the path geometry. §10.7.

---

## 6. Attribute reference

Attributes are in both profiles unless noted.

### 6.1 On `<g class="word">` — the key and the text of record; four more forms in the sidecar

```xml
<!-- production -->
<g class="word" data-word-key="2:6:2" data-w="67" data-rasm-uthmani="ٱلَّذِينَ">
<!-- dev -->
<g class="word" data-word-key="2:6:2" data-w="67" data-rasm-uthmani="ٱلَّذِينَ" data-rasm="ٱلذين"
   data-rasm-imlai="الَّذِينَ" data-search="الذين" data-qpc="ٱلَّذِينَ">
```

| form | on the word group | in `index/by-page/NNN.json` | what it is | example (2:6:2) |
|---|---|---|---|---|
| `word_key` | `data-word-key`, both profiles | `word_key` | `surah:ayah:word`, 1-based, all three ordinals and Hafs-specific. **The key, and the only one.** Dense, in order, unique across the corpus. Word N of an ayah is word N of that ayah in the word-by-word-translation-translation release (`docs/HAFS-JSON-SOURCE.md`) | `2:6:2` |
| `w` | `data-w`, both profiles | `w` | the word's number in the **quran-text** release, the same number in every riwayah it publishes. **Not a key of this format**: its space is 1–77,434 over 77,432 words (a number Hafs does not write is skipped, and `72:16:1` holds two), so never treat it as dense. Release 1.1.2 did not carry it; it is back from release 1.1.3, and is the only attribute added to the word pages. | `67` |
| `rasm_uthmani` | `data-rasm-uthmani`, both profiles | `rasm_uthmani` | **the print's own text**, full diacritics | `ٱلَّذِينَ` |
| `rasm` | `data-rasm`, dev only | `rasm` | skeleton of `rasm_uthmani` — the **ink** | `ٱلذين` |
| `rasm_imlai` | `data-rasm-imlai`, dev only | `rasm_imlai` | modern spelling, **with** marks | `الَّذِينَ` |
| `search` | `data-search`, dev only | `search` | skeleton of `rasm_imlai` — **the search key** | `الذين` |
| `qpc` | `data-qpc`, dev only | `qpc` | the same text in KFGQPC codepoints | `ٱلَّذِينَ` |

Every word has all five forms; in production the last four come from
the sidecar, keyed by `word_key`, built from the same source and the same
derivations as the dev attributes (`tools/bundle_extract.text_forms`). The
bundle checker proves the sidecar's `rasm_uthmani` equals every page's
`data-rasm-uthmani`. `index/words.json` carries `search` for the whole corpus in one
file. The shipping library reads inline first and the sidecar second
(`page.attachWords`, `createLoader({words: true})`).

**Which one to use, and this is the part people get wrong:**

- **Displaying the text of the page → `data-rasm-uthmani`.** It is the text of
  record, matching the ink. Composite source: quran.com `text_uthmani` +
  KFGQPC waqf + DigitalKhatt at iqlab sites (§9.7). From release 2.0.0 the
  **segmentation** into words, the mark budgets and the `qpc` form come from
  the quran-text release: `qpc` is its own string for the word, the KFGQPC
  UthmanicHafs v3 code points exactly as that release writes them.
- **Matching text to the glyphs on the page → `data-rasm`.** It is the rasm_uthmani
  skeleton, so it says what shapes are actually drawn.
- **A search box → `data-search`. Never `data-rasm`.** The rasm is the rasm_uthmani
  skeleton, and the rasm_uthmani spelling writes several long vowels as *combining
  marks*, which stripping deletes outright. Nobody types the result:

  | word | `data-rasm-uthmani` | `data-rasm` (not searchable) | `data-search` (searchable) |
  |---|---|---|---|
  | p3 `2:6:2` | `ٱلَّذِينَ` | `ٱلذين` — starts with alef **hamzat_al_wasl** U+0671 | `الذين` |
  | p10 `2:63:3` | `مِيثَٰقَكُمْ` | `ميثقكم` — the dagger alef U+0670 is gone | `ميثاقكم` |
  | p272 `16:48:10` | `ظِلَٰلُهُۥ` | `ظلله` | `ظلاله` |
  | p329 `21:88:7` | `نُـۨجِى` | `نجى` | `ننجي` |

  Character-set proof over every word: `data-rasm` uses alef-hamzat-al-wasl
  (U+0671) and **no** alef-maddah (U+0622); `data-search` uses **no**
  alef-hamzat-al-wasl at all, and does use alef-maddah.

**Nothing is folded in any of them.** This is deliberate. `ا أ إ آ ٱ` stay
distinct, `ى` and `ي` stay distinct, `ة` and `ه` stay distinct — `data-search`
contains all of `ء أ إ آ ؤ ئ ة ى ي` as separate characters. If your users
expect a forgiving search, fold on **your** side and keep the stored value as
written:

```js
const fold = s => s.replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
// DEV profile only: `data-search` is not in the published bundle (§2).
// For a released bundle, search the `search` column of index/words.json, or
// the `search` field of index/by-page/NNN.json.
const hits = [...doc.querySelectorAll('g.word')]
  .filter(w => fold(w.dataset.search).includes(fold(query)));
```

The six attributes **legitimately disagree** at iqlab sites and around tanwin
(§9.7, §9.8). That is not corruption. Two further cautions: **`data-search`
values can contain a space** (the vocative convention, `يَا أَيُّهَا` →
`يا أيها`), and so can `data-rasm-imlai` values — see §9.4, and never tokenise on
whitespace.

### 6.2 On `<g class="ayah-fragment">`

| attribute | format | notes |
|---|---|---|
| `data-ayah-key` | `surah:ayah` | which ayah this fragment belongs to |
| `data-mark` | `mk-<surah>-<ayah>` | the `id` of this ayah's medallion — §7 |
| `data-fragment` | `1`..`N` | which fragment this is, in reading order |
| `data-ayah-fragments` | `N` | how many fragments the ayah has on this page |
| `data-juz-start` | `1`..`30` | this ayah begins that juz |
| `data-hizb-start` | `1`..`60` | begins that hizb |
| `data-nisf-start` | `1`..`60` | begins that half-hizb boundary, numbered 1..60 through the mushaf |
| `data-rubu-al-hizb-start` | `1`..`240` | begins that rubʿ |

Each appears **once**, on `data-fragment="1"` of the ayah that opens the division —
so each attribute occurs exactly once per division it numbers.

They used to be repeated on every fragment, which made a consumer looping over `[data-rubu-al-hizb-start]` print the same rubʿ seven
times on p575, where 73:20 spans seven lines. A division opens once. An ayah
never spans pages, so part 1 is always on
the page the division opens on.

They are complete: all 30 juz, all 60 hizb, all 240 rubʿ boundaries are marked,
including the 41 that have no drawn rosette (§9.6).

`data-nisf-start` is NOT the `1`/`2` half-index — that is `data-nisf` on the
hizb rosette (§6.4). It numbers the 60 half-hizb BOUNDARIES through the mushaf,
1 at 2:44 to 60 at 94:1, and lands on exactly the ayahs whose `rubu_al_hizb_in_hizb` is
3, i.e. the start of each hizb's second half.

```js
// where does juz 30 begin?
doc.querySelector('g.ayah-fragment[data-juz-start="30"]')?.dataset.ayahKey;   // "78:1" on p582
```

### 6.3 On `<g class="ayah-mark">`

| attribute | format |
|---|---|
| `id` | `mk-<surah>-<ayah>`. **Globally unique** — no ayah spans two pages (§11). |
| `data-ayah-key` | `surah:ayah` |

Every marker group has both.

### 6.4 On `<g class="line">`

| attribute | format |
|---|---|
| `data-line` | `1`–`15` (`1`–`8` on pages 1–2). The printed line number, top to bottom. **Correct for every word** since 2026-08-30. |

### 6.5 On `<path>`

| attribute | values | notes |
|---|---|---|
| `data-kind` | `mark` · `body` · `ayah_mark_ornament` · `ayah_number` · `header_ink` · `page_number` · `running_head` | Present on **every** path except the dev-only `ayahPolygon`. The `page_number` / `running_head` paths are p17's page furniture, drawn by the artwork **entirely outside the viewBox** (y 583.7..588.2 on a 550-tall page, and y -62.2..-7.1), kept so no ink is ever silently dropped — §10.5. `body` = letter ink; in the letter bundle a joined outline is one path per letter. |
| `data-mark` | 35 names, §8 | On every `data-kind="mark"` path. **Letter bundle: also on the `data-kind="body"` paths that keep their `data-mark`** — a stroke that is its letter's whole body (§6.9). The two together equal the word bundle's mark paths in number. |
| `data-mark-family` | **token list** — `diacritic` · `dots` · `tanwin` · `waqf` · `sifr` · `sajdah` · `reading_sign` | **Space-separated, like `class` — match with `~=`, not `=`.** See below. Only on marks that have a family. **Derivable from `schema/mark-taxonomy.json`** — prefer the registry, which also covers `small_noon` (§10.5). |
| `data-element-id` | `e1`, `e2`, … | On every word and standalone ink path. **Dev profile only.** Not stable across builds. Never key on it. Unique within a page. Only on word/standalone ink — never on marker, header or polygon paths. |
| `data-sig` | 16 hex | On the same paths. **Dev profile only.** Outline shape signature used by the review loop. **Not an identity** — §8.5. |
| `data-cut` | `1` | **Letter bundle only.** The outline is a **piece cut from one of the artwork's contours**, not a contour the designer drew. Its points are written at up to six decimals (§5.2's three-decimal rule is about the designer's numbers). §6.9. |
| `data-at` | integer | **Letter bundle only**, on mark paths and on body paths that keep their `data-mark`: the code-point offset, in the word's `qpc` text, of the character this path draws (a dot points at its letter). Not every mark path carries one — §10.10. |
| `data-form` | `staggered` · `stacked` | Only on the `tanwin` family: how the pair of strokes is drawn. |
| `data-iqlab` | `iq-<surah>-<ayah>-<word>` | Links a harakah to its small meem at an iqlab site. **Incomplete — §10.4.** |
| `data-pair` | `mnq-<surah>-<ayah>-<n>` | Links the two halves of a muʿānaqah (§9.3). |
| `data-standalone` | `1` | Marks that belong to no word: the hizb rosettes and the sajdah paths. **Letter bundle: the sajdah paths only**; the hizb paths are there without the attribute. |
| `data-ayah-key` | `surah:ayah` | On those same standalone paths. |
| `fill` / `fill-rule` | `#231f20` / `evenodd` | On all ink. Every ink path in the mushaf is the same colour. |

`data-mark-family` is present in **both** profiles. `data-element-id` and
`data-sig` exist for the review loop and are in the **dev profile only**: the
production pages carry neither. (This paragraph used to say both profiles.)

#### `data-mark-family` is a token list — use `~=`, never `=`

A mark can belong to more than one family, so the attribute holds
space-separated tokens exactly like `class`:

```css
[data-mark-family~="diacritic"] { }   /* correct */
[data-mark-family="diacritic"]  { }   /* WRONG — misses every tanwin */
```

Only the three tanwin carry two tokens today (`"diacritic tanwin"`). They are vowel marks *and* they are the tanwin, and both groupings are
real: hiding the diacritics must reach them, and §8.2 groups on them. Every
other family is single-token, so `=` happens to work there — but it is the wrong
habit and will break the next time a mark needs two families. Always `~=`.

### 6.6 Page identity — nine attributes on the root `<svg>`

Every page states which mushaf it belongs to, so a file downloaded on its own is
self-describing:

```xml
<svg data-mushaf="hafs-kfqc" data-qiraah="asim" data-riwayah="hafs"
     data-edition="kfgqpc-1441"
     data-riwayah-name-ar="حفص عن عاصم" data-riwayah-name-en="Hafs 'an Asim"
     data-ayah-numbering="kufi" data-ayah-total="6236"
     data-decomposition="word" data-page="42" …>
```

Each appears exactly once on every page. Values come from the
`quranpedia/qiraahs-ayah-map` dataset; the full records — names, descriptions and
the provenance of the numbering choice — belong in the bundle's `catalogue.json`
rather than being repeated on every page.

Three of these are easy to misread:

- **`data-decomposition` says how deep this file goes.** `word` means every word,
  ligature and named mark is addressable — what this specification describes.
  `ayah` means page ink with ayah polygons and markers and nothing below the
  ayah, which is what `quranpedia/quran-svg` publishes for editions this pipeline
  has not yet processed. **Check it before selecting `g.word`**: on an
  `ayah`-level file that selector legitimately returns nothing, and an empty
  result there means "not decomposed", not "broken".
- **`data-riwayah-name-*` names the RIWAYAH, not the mushaf.** `حفص عن عاصم` is
  the conventional designation of a transmission — rawi عن qiraah — so it belongs
  with `data-riwayah`, not with `data-mushaf`. (It was briefly called
  `data-mushaf-name-*`; that was wrong and the name was corrected before
  publication.)
- **`data-riwayah` is not `data-qiraah`.** Ḥafṣ is a *transmission* of ʿĀṣim's
  *reading*; Shuʿba is the other. Warsh and Qālūn are both Nāfiʿ. "The Ḥafṣ
  qiraah" is an error — say the Ḥafṣ riwayah, or the reading of ʿĀṣim.
- **`data-ayah-numbering` is a property of the printed EDITION, not of the
  qiraah.** It must never be derived. The King Fahd al-Dūrī edition proves why:
  its qiraah (Abū ʿAmr) implies the Basri count, but its colophon declares the
  First Madani, and its pages agree with First Madani in 110 of 114 surahs
  against 72 for Basri.
- **`data-ayah-total` follows the counting system, not the Quran.** 6,236 is
  Kufi; Nāfiʿ counts 6,214. Any consumer that hardcodes 6,236 will reject a
  correct edition of another riwayah.

### 6.7 On `<g class="surah-name">` and `<g class="basmalah">`

```xml
<g class="surah-name" data-sid="2" data-surah-name-ar="البقرة"
   data-surah-name-latin="Baqarah" data-surah-name-en="The Cow"
   data-revelation-place="madinah" data-ayah-count="286">
```

| attribute | example |
|---|---|
| `data-sid` | `2` |
| `data-surah-name-ar` | `البقرة` |
| `data-surah-name-latin` | `Baqarah` |
| `data-surah-name-en` | `The Cow` |
| `data-revelation-place` | `makkah` / `madinah` |
| `data-ayah-count` | `286` |

They are on every surah-name group and every basmalah group; the basmalah
group repeats its surah's metadata. **These attributes appear only on a surah's first page.**
To know the surah of an arbitrary page, read the surah number out of any
`data-word-key`, or use the companion `index.json`.

### 6.8 On `<g class="division-mark">`

```xml
<g class="division-mark" data-mark="hizb" data-ayah-key="2:75"
   data-rubu-al-hizb="5" data-rubu-al-hizb-in-hizb="1" data-nisf="1" data-hizb="2" data-juz="1">
  <path data-element-id="e791" data-kind="mark" data-mark="hizb" data-sig="91526b27f4bc5bb9"
        data-standalone="1" data-ayah-key="2:75" d="…"/></g>
```

| attribute | meaning |
|---|---|
| `data-mark` | always `hizb` |
| `data-ayah-key` | the ayah the rosette stands before |
| `data-rubu-al-hizb` | rubʿ number, 1..240 |
| `data-rubu-al-hizb-in-hizb` | 1..4 |
| `data-nisf` | half of the hizb, 1 or 2 |
| `data-hizb` | 1..60 |
| `data-juz` | 1..30 |

The `*-start` attributes are **not** here — they are on `<g class="ayah-fragment">`
(§6.2), because 41 boundaries have no rosette.

### 6.9 On `<g class="letter">` — the letter layer *(letter bundle, schema 2.0.0)*

In the letter bundle every word group holds **one `<g class="letter">` per
letter** of the word, in the order of its spelling. A letter group holds that
letter's **body ink** — a whole contour of the artwork where the letter is drawn
apart, or a **piece cut from a contour** (`data-cut="1"`) where it is joined to
its neighbours — and **the letter's own marks**. A mark that belongs to the word
and not to one letter stays a direct child of the word group.

A real fragment of `pages/003.svg`, production profile, `d=` values trimmed:

```xml
<g class="word" data-word-key="2:6:2" data-w="67" data-rasm-uthmani="ٱلَّذِينَ">
 <g class="letter" data-text="ٱ" data-index="0" data-at="0">
   <path data-kind="body" d="M67.997 354.70…" fill="#231f20" fill-rule="evenodd"/>
   <path data-at="0" data-kind="mark" data-mark="hamzat_al_wasl" d="M69.134 357.86…" …/></g>
 <g class="letter" data-text="ل" data-index="1" data-at="1">
   <path data-kind="body" d="M64.559986 355…" … data-cut="1"/>
   <path data-at="3" data-kind="mark" data-mark="fathah" data-mark-family="diacritic" …/>
   <path data-at="2" data-kind="mark" data-mark="shaddah" data-mark-family="diacritic" …/></g>
 <g class="letter" data-text="ذ" data-index="2" data-at="4">
   <path data-kind="body" d="M65.057958 344…" … data-cut="1"/>
   <path data-at="5" data-kind="mark" data-mark="kasrah" data-mark-family="diacritic" …/>
   <path data-at="4" data-kind="mark" data-mark="dot" data-mark-family="dots" …/></g>
 <g class="letter" data-text="ي" data-index="3" data-at="6"> … </g>
 <g class="letter" data-text="ن" data-index="4" data-at="7"> … </g>
</g>
```

| attribute | on | values | meaning |
|---|---|---|---|
| `data-index` | every letter group | 0, 1, … | the letter's position in the word's letter sequence, in reading order. Unique within the word. |
| `data-text` | every letter group | one character | the letter as the word's text writes it (`ٱ`, `ل`, the dagger alif `ٰ` where it is drawn as a letter). |
| `data-at` | every letter group, and the paths inside it | integer | the code-point offset, in the word's `qpc` text (`index/by-page/NNN.json`), of the character this ink draws. On a mark path it is the mark's own character; a letter's dots point at the letter. |
| `data-cut` | a body path | `1` | the outline is a piece cut from a contour of the artwork (§6.5). |
| `data-mark` on a **body** path | a body path | `omitted_alif` · `hamzah` | the stroke is the letter's whole body and is also a named mark: the dagger alif drawn as a letter, and the two fused-hamzah sites (§9.0 (b), p324 `21:28:4` and p341 `22:76:4`). The word page has the same path, same `d`, as `data-kind="mark"`. Select these with `path[data-kind="body"][data-mark]`. |
| `data-unsplit` | a letter group | `1` | reserved: the ink of several letters that could not be divided, in one group, with all their characters in `data-text` and all their offsets in `data-at`. **No group carries it in this build.** |

**Paths inside a letter group are not in text order.** The body comes first;
the marks follow in the order the ink was found (above, the fathah at offset 3
is written before the shaddah at offset 2). Order them by `data-at`.

**Index into `qpc` by code point.** Every character of the Hafs text is in the
Basic Multilingual Plane, so `qpc[n]` is the `n`-th code point in JavaScript and
in Python alike.

#### Where the division comes from

Which ink is on the page, which word holds it, what each mark is called, and
the text are this project's, exactly as in the word bundle. **Where a joined
stroke is divided between two letters, and which letter a mark belongs to, is
the output of DigitalKhatt's `medinamushafanalyzer`** (commit `056191f`, MIT
licence), run on the same vectors. `tools/join_dk_letters.py` matches every
contour of the two by geometry and carries the analyzer's letters onto our
words: a contour the analyzer does not cut is copied byte for byte into its
letter, and a contour it cuts is replaced by its pieces.

What follows is **not** the analyzer's; the join adds it:

| what the join adds |
|---|
| ink of a cut contour that no piece covered, given to the letter piece it touches most (the reviewer's rule; §10.10) |
| a run the analyzer left uncut, divided by a cut the reviewer picked by eye |
| an analyzer cut the reviewer rejected, replaced by one he picked |
| a mark the reviewer moved to another letter of its word |
| a mark the analyzer gave to no letter of the word, given to the nearest letter of it |
| one unplaced mark and one sign without ink in the same word, linked |
| a contour under 0.05 square units that the analyzer drops, kept with the nearest letter |
| a sign the analyzer names as a letter of its own, seated on a kashida already given to a letter: it is that letter's mark |
| a letter with no body path takes the stroke stamped with its own character as its body (the dagger alif) |
| the alif of the two fused-hamzah sites takes the hamzah outline as its body |
| the maddah over a hamzah-alif is named `maddah` |

The cuts the reviewer picked are recorded as data, per word, in
`tools/data/dk_fills.json` of the pipeline; they were cut by this project's own
earlier letter build. A kashida in the text that seats no mark is typography,
not a letter, and has no group (`2:97:5`).

#### What is proven about the ink

Every letter group carries `data-at` and holds a body path; no body path of a
word sits outside a letter group; no group is unsplit.

- **The bundle build** proves every page against the word page of the same
  build: the same words, the same ink outside the words, every uncut path
  verbatim, every cut piece within 1/8 of a unit of the contour it came from
  (`tools/bundle_letters.py`; `tools/verify_bundle.py --words-ref` repeats it).
  Every page passes, with no exception list.
- **Two ink checks**, written separately from the join and from each other,
  compare each word's letter ink with its word ink. One works on polygons
  (`tools/audit_letter_ink.py`: any strip 0.0125 units wide and 0.002 square
  units or more that is lost, added, or held by two letters). One renders both
  at 160 px per unit (`tools/audit_letter_raster.py`: any patch 3 px, 0.019
  units, wide, and any path written twice). Over every word: **0 words lose
  ink, 0 gain ink, 0 pairs of letters overlap.**

So a letter page draws what its word page draws, to within a hairline at a cut
(§10.10). A consumer counting `path[data-kind="mark"]` finds fewer on a
letter page set than on the word pages; counting `path[data-mark]` finds the
same number.

**The index.** `index/pages.json` gives `letters` and `letters_unsplit` per
page; `index/by-page/NNN.json` gives the same two at the top and `letters` on
every word. `VERSION.json` carries the totals under `counts` and, under
`letters`, the analyzer commit, the digest of its 604 input pages and the proof
statement.

```js
// every letter of 2:6:2 with the KFGQPC character it draws
const side = await (await fetch('index/by-page/003.json')).json();
const qpc  = side.words.find(w => w.word_key === '2:6:2').qpc;
[...doc.querySelectorAll('g.word[data-word-key="2:6:2"] > g.letter')]
  .map(g => ({i: +g.dataset.index, text: g.dataset.text, qpc: qpc[+g.dataset.at]}));

// highlight one letter: style the group, its marks come with it
doc.querySelector('g.word[data-word-key="2:6:2"] > g.letter[data-index="1"]')
   .classList.add('hl');

// all the ink of a word, whichever bundle the page is from
doc.querySelectorAll('g.word[data-word-key="2:6:2"] path');   // not `g.word > path`
```

---

## 7. An ayah is not a subtree — read this before selecting one

**The single most common mistake with this format.** An ayah is emitted once
per printed LINE it occupies, so it is several sibling nodes and there is no
single node that "is" the ayah. The record is
2:282 on p48, which fills all 15 lines of its page and so has 15 fragments
(pages 17 and 144 go higher for a different reason — §10.5).

Every fragment says so, and the fragments are linked to the medallion:

```xml
<!-- page 3, line 1 -->
<g class="ayah-fragment" data-ayah-key="2:6" data-ayah-mark="mk-2-6" data-fragment="1" data-ayah-fragments="2">…</g>
<!-- page 3, line 2 -->
<g class="ayah-fragment" data-ayah-key="2:6" data-ayah-mark="mk-2-6" data-fragment="2" data-ayah-fragments="2">…</g>

<!-- page 3, in #ayah_markers -->
<g class="ayah-mark" id="mk-2-6" data-ayah-key="2:6">…</g>
```

Verified corpus-wide: **every fragment carries `data-mark`, every one
resolves to a marker `id` on the same page, and every ayah's `data-fragment` values
are exactly `1..data-ayah-fragments` in document order.**

```js
// ---- select the WHOLE ayah (all its fragments, all its words) ----
const frags = doc.querySelectorAll('g.ayah-fragment[data-ayah-key="2:6"]');       // 2 nodes
const words = doc.querySelectorAll('g.ayah-fragment[data-ayah-key="2:6"] g.word'); // all its words
// frags[0].dataset.ayahFragments === "2"   -> and you got 2, so the ayah is complete

// ---- from an ayah, find its medallion ----
const medallion = doc.getElementById(frags[0].dataset.marker);      // <g id="mk-2-6">

// ---- from a medallion, find its ayah ----
const back = doc.querySelectorAll(`g.ayah-fragment[data-mark="${medallion.id}"]`);

// ---- from a word, find everything ----
const w = doc.querySelector('g.word[data-word-key="2:6:3"]');
w.closest('g.ayah-fragment').dataset.ayahKey;      // "2:6"
w.closest('g.line').dataset.line;     // "1"
doc.getElementById(w.closest('g.ayah-fragment').dataset.marker);   // its medallion
```

**Do not** use `firstElementChild` / `lastElementChild` of one fragment to find
the ayah's first or last word — use `data-word-key` order across all fragments. **Do
not** assume `querySelector` (singular) on `g.ayah-fragment[data-ayah-key=…]` gives you the
ayah; it gives you fragment 1 of N.

`data-ayah-fragments` is also your completeness check: since **no ayah spans two
pages** (§11), if you loaded the right page you will always find all N.

> **Version note.** Before 2026-08-30 the medallions carried the wrong ayah
> label, effectively reversed down the page. They are now bound by position and correct. If you
> have an older bundle, the marker labels are not usable — check for `id="mk-…"`
> on `<g class="ayah-mark">`; the fix and the link landed together.

---

## 8. The mark taxonomy — 35 emitted names

The registry ships in the bundle as `schema/mark-taxonomy.json` (schema
`mark-taxonomy`, version 2.0). In the pipeline's working tree the same file is
built at `.cache/schema/mark-taxonomy.v2.json`; consumers want the bundled copy. It declares **36** names: **35 active**, 1 reserved-inactive
(`waqf_mamnu`, §8.6). Of the 35 active, `waqf` is a legacy fallback name with
**0** occurrences. `tools/audit_taxonomy.py` gates
this and reports `35 mark names`, counting the registry's active set.

Two further names appear only as **group-level** `data-mark`, never on a path:
`sajdah` and `hizb` — `hizb` is also a path name.

Codepoints below are what appears in `data-rasm-uthmani`. `family` is what the
registry declares as `data-mark-family`; `category` is the registry's grouping.

### 8.1 Harakahs (vowels and their companions) — category `harakah`

| `data-mark` | Arabic | codepoint | family |
|---|---|---|---|
| `fathah` | فتحة | U+064E `َ` | — |
| `kasrah` | كسرة | U+0650 `ِ` | — |
| `dammah` | ضمة | U+064F `ُ` | — |
| `sukun` | سكون | U+0652 `ْ`, U+06E1 `ۡ` | — |
| `shaddah` | شدة | U+0651 `ّ` | — |

### 8.2 Tanwin — `data-mark-family~="tanwin"`, `data-form` on most

| `data-mark` | Arabic | codepoint |
|---|---|---|
| `tanwin_al_fath` | تنوين فتح | U+064B `ً`, **U+08F0 `ࣰ`** |
| `tanwin_al_kasr` | تنوين كسر | U+064D `ٍ`, **U+08F2 `ࣲ`** |
| `tanwin_al_damm` | تنوين ضم | U+064C `ٌ`, **U+08F1 `ࣱ`** |

### 8.3 Letter dots — `data-mark-family="dots"`

| `data-mark` | notes |
|---|---|
| `dot` | one dot |
| `two_dots` | drawn as one path |
| `three_dots` | drawn as one path |

Dots are the letters' own dots (nuqaṭ), not diacritics — but in this schema
they are `data-kind="mark"`. A hamzah seat (`ئ ؤ أ إ`) is drawn **without** the
dots of its base letter.

### 8.4 Orthographic signs — category `orthographic`

| `data-mark` | Arabic | codepoint | notes |
|---|---|---|---|
| `hamzah` | همزة | U+0621 `ء` and the seats U+0623/0625/0624/0626, U+0654/0655 | **Identical ink to a letter_hamzah** — §8.7 |
| `hamzat_al_wasl` | همزة وصل | U+0671 `ٱ` | |
| `omitted_alif` | ألف خنجرية | U+0670 `ٰ` | |
| `maddah` | مدة | U+0653 `ٓ`, U+06E4 `ۤ` | |
| `small_waw` | واو صغيرة | U+06E5 `ۥ` | pronominal suffix — §9.10 |
| `small_yaa` | ياء صغيرة | U+06E6 `ۦ`, U+06E7 `ۧ` | pronominal suffix — §9.10 |
| `small_noon` | نون صغيرة | U+06E8 `ۨ` | 21:88 only — §9.1. **The only orthographic sign with no family** |

### 8.5 Dabt (recitation-aid signs) — category `dabt`

| `data-mark` | Arabic | codepoint | family | notes |
|---|---|---|---|---|
| `rounded_zero` | صفر مستدير | U+06DF `۟` | `sifr` | round zero: the letter is **not** pronounced, ever |
| `rectangular_zero` | صفر مستطيل | U+06E0 `۠` | `sifr` | upright zero: not pronounced in waṣl, pronounced in waqf. **A different sign with different rules** |
| `small_meem` | ميم الإقلاب | U+06E2 `ۢ` (high), U+06ED `ۭ` (low) | — | §9.7 |

### 8.6 Waqf (waqf) signs — `data-mark-family="waqf"`

Verified empirically by pairing each word's waqf codepoint with its emitted
mark name over all 604 pages.

| `data-mark` | codepoint | conventional name |
|---|---|---|
| `waqf_jaiz_mustawi_al_tarafayn` | U+06DA `ۚ` | جائز — pausing permitted |
| `waqf_jaiz_wasl_awla` | U+06D6 `ۖ` | صلى — continuing is better |
| `waqf_jaiz_waqf_awla` | U+06D7 `ۗ` | قلى — pausing is better |
| `waqf_lazim` | U+06D8 `ۘ` | لازم — waqf obligatory |
| `waqf_al_muanaqah` | U+06DB `ۛ` | معانقة — stop at one of a pair |

**The names are the ACTION, not the letters of the sign.** U+06D6 (ۖ, "ṣalā")
is emitted as `waqf_jaiz_wasl_awla`, and U+06D7 (ۗ, "qilā") as `waqf_jaiz_waqf_awla`. Map by this
table, not by the sign's Arabic abbreviation. The registry's `aliases` block
records the older names (`waqf qila` → `waqf_jaiz_mustawi_al_tarafayn`, `waqf sali` → `waqf_jaiz_wasl_awla`,
`waqf taanuq` → `waqf_al_muanaqah`, `sajdah` → `sajdah_mark`).

**U+06D9 `ۙ` (لا, "do not stop") does not occur in this print** — zero
occurrences in the text, zero marks. `waqf_mamnu` is the one registry entry
with `active: false`.

### 8.7 Reading signs — `data-mark-family="reading_sign"`

Each occurs at a handful of sites, named **by site, not by shape** (§9.1).

| `data-mark` | Arabic | codepoint |
|---|---|---|
| `saktah` | سكتة | U+06DC `ۜ` |
| `seen_al_qiraah` | سين القراءة | U+06DC `ۜ`, U+06E3 `ۣ` |
| `imalah` | إمالة | U+06EA `۪` |
| `ishmam` | إشمام | U+06EC `۬` |
| `tashil` | تسهيل | U+06EC `۬` |

### 8.8 Standalone signs — `data-standalone="1"`, category `standalone`

| `data-mark` | Arabic | family |
|---|---|---|
| `sajdah_mark` | ۩ | `sajdah` |
| `sajdah_line` | the overline | `sajdah` |
| `hizb` | ۞ | — |

---

## 9. Things a drawing cannot tell you, and special cases

Every one is verified in a real page. Page numbers and `data-word-key` keys are
exact.

### 9.0 Five properties of the script, not quirks of the file

**(a) `fathah` and `kasrah` are the SAME STROKE, named by position.** So are
`tanwin_al_fath`/`tanwin_al_kasr` and `dammah`/`tanwin_al_damm`. The name comes from where the
stroke sits relative to the word's letters and from the word's spelling —
nothing in the outline distinguishes them. Two consequences: a mis-owned mark
always arrives wearing the **opposite** name (a stolen fathah hangs below its new
holder's letters and is therefore called `kasrah`), and you cannot infer a name
from a `data-sig`: a signature can serve both `fathah` and `kasrah`.

**(b) `hamzah` and a letter_hamzah are IDENTICAL ink.** `data-mark="hamzah"` is a
diacritic; a hamzah that is a *letter* of the word is `data-kind="body"`. The ink
is the same; only the spelling decides. Counting `[data-mark="hamzah"]` counts
diacritic hamzahs only — usually what you want, but not "all hamzahs drawn".

At two sites the print draws the hamzah **fused to its alif as one contour**
(p324 `21:28:4` and p341 `22:76:4`, both `أَيْدِيهِمْ`). The ruling: name it
`hamzah`, never cut it. Consequence — the `<g class="ligature" data-text="ا">`
there holds **no `data-kind="body"` path at all**:

```xml
<g class="word" data-word-key="21:28:4" data-rasm-uthmani="أَيْدِيهِمْ" data-rasm="أيديهم"
   data-rasm-imlai="أَيْدِيهِمْ" data-search="أيديهم" data-qpc="أَيۡدِيهِمۡ">
 <g class="ligature" data-text="ا">
  <path data-element-id="…" data-kind="mark" data-mark="hamzah" data-sig="f2c96fa4a4a90766" d="…"/>
  <path data-element-id="…" data-kind="mark" data-mark="fathah" data-sig="d7a8b5e19121fbe4" d="…"/></g>
```

**(c) Composite marks: one outline, two marks.** One drawn outline can carry two
marks (`fathah+hamzah`, `dammah+shaddah`). These are resolved internally and **no
`+`-compound name survives into the emitted files** — verified, zero
occurrences.

**(d) Path count ≠ sign count.** Two slash strokes drawn touching share one
path, so the pair counts once. Where the artwork puts a sign's contours in
different paths, the emitter folds them into one path, so **a mark is always
exactly one path** — the last exception (p146) was merged 2026-08-30 and the
`data-mark-part` attribute retired with it. And muʿānaqah is ONE sign of three dots that
comes in **pairs** across two words: three pairs mushaf-wide = 6 emitted
`waqf_al_muanaqah` paths. **Do not count six signs, and do not count three dots per
sign.**

**(e) A `data-sig` is not an identity.** It is the outline's shape. **A
signature can serve more than one mark name.** `d2506e4f8b4e28e5` — a plain
circle — is `dot`, `two_dots`, `three_dots` and `waqf_al_muanaqah`. Conversely
one name can have more than one signature, as `fathah` and `small_meem` do.
**A consumer should not use `data-sig`.**

### 9.1 Once-in-the-mushaf signs — and one character meaning two things

| sign | `data-mark` | sites |
|---|---|---|
| saktah | `saktah` | p293 `18:1:11` عِوَجَاۜ · p443 `36:52:6` مَّرْقَدِنَاۜۗ · p567 `69:28:4` مَالِيَهْۜ · p578 `75:27:2` مَنْۜ · p588 `83:14:2` بَلْۜ |
| seen-for-sad | `seen_al_qiraah` | p39 `2:245:14` وَيَبْصُۜطُ · p159 `7:69:22` بَصْۜطَةࣰۖ · p525 `52:37:7` ٱلْمُصَۣيْطِرُونَ |
| imalah | `imalah` | p226 `11:41:6` مَجْر۪ىٰهَا |
| ishmam | `ishmam` | p236 `12:11:6` تَأْمَ۬نَّا |
| tashil | `tashil` | p481 `41:44:9` ءَا۬عْجَمِىࣱّ |
| small noon | `small_noon` | p329 `21:88:7` نُـۨجِى |

**U+06DC is a `saktah` at five sites and a `seen_al_qiraah` at two.** **U+06EC is
`ishmam` at 12:11 and `tashil` at 41:44.** Same character, two names, same
drawing. **Never map a codepoint to a mark name from a Unicode table.** Trust
`data-mark`, or key on (surah, ayah).

At 52:37 `data-rasm-uthmani` writes U+06E3 (seen below) but `data-qpc` writes U+06DC
— so `data-qpc` has eight U+06DC sites, not seven.

```xml
<g class="word" data-word-key="21:88:7" data-rasm-uthmani="نُـۨجِى" data-rasm="نجى"
   data-rasm-imlai="نُنجِي" data-search="ننجي" data-qpc="نُـۨجِي">
```

### 9.2 Pages 1 and 2 are the opening spread

A different page matrix (the artwork's offset viewBox, folded in — §5.1),
**8 lines instead of 15**, per-line translates, and the medallion scale is
`0.0075` instead of `0.011`. Each ayah has one marker group with one ornament
path, as on every other page: `querySelectorAll('.ayah-mark')` returns 7 on
the 7-ayah page.

The format document of release 1.1.2 described a second, identical ornament
path in each of these groups, tagged `data-duplicate="1"`. The pages of this
release, built on quran-svg v1.1.1, hold one ornament per ayah and no path
carries `data-duplicate`.

### 9.3 Muʿānaqah — one sign, three dots, in pairs

`data-pair` links the two halves. Exactly 6 paths, 3 pairs, in the corpus.

```xml
<g class="word" data-word-key="2:2:4" data-rasm-uthmani="رَيْبَۛ" …>
  <path data-element-id="e32" data-kind="mark" data-mark="waqf_al_muanaqah" data-mark-family="waqf"
        data-sig="a482216d539513a5" data-pair="mnq-2-2-1" d="…"/>
<g class="word" data-word-key="2:2:5" data-rasm-uthmani="فِيهِۛ" …>
  <path data-element-id="e38" data-kind="mark" data-mark="waqf_al_muanaqah" data-mark-family="waqf"
        data-sig="a349de70f401f061" data-pair="mnq-2-2-1" d="…"/>
```

| pair | page | words |
|---|---|---|
| `mnq-2-2-1` | 2 | `2:2:4` رَيْبَۛ ↔ `2:2:5` فِيهِۛ |
| `mnq-5-26-1` | 112 | `5:26:4` عَلَيْهِمْۛ ↔ `5:26:6` سَنَةࣰۛ (two words apart) |
| `mnq-5-41-1` | 114 | `5:41:16` قُلُوبُهُمْۛ ↔ `5:41:19` هَادُوا۟ۛ (three words apart) |

The partners are **not adjacent**. Join on `data-pair`, never on proximity, and
never on the drawing — they can share the plain-`dot` signature (§9.0e).

### 9.4 Word tokens containing a SPACE

One word in the whole corpus has a space in its own text: p451
`data-word-key="37:130:3"`.

```xml
<g class="word" data-word-key="37:130:3" data-rasm-uthmani="إِلْ يَاسِينَ" data-rasm="إل ياسين"
   data-rasm-imlai="إِلْ يَاسِينَ" data-search="إل ياسين" data-qpc="إِلۡ يَاسِينَ">
  <g class="ligature" data-text="ا">…</g>
  <g class="ligature" data-text="ل">…</g>
  <g class="ligature" data-text="يا">…</g>
  <g class="ligature" data-text="سين">…</g></g>
```

The space breaks the Arabic join, so it draws four runs — but **no attribute
says where the word break falls**; concatenating the four `data-text` values
gives `الياسين`.

Space census over all 604 pages:

| attribute | what the spaces are |
|---|---|
| `data-rasm-uthmani` | this word only |
| `data-rasm` | this word only |
| `data-qpc` | the `۞ ` prefix, a spaced trailing waqf sign, this word |
| `data-search` | the rasm_imlai vocative convention (`يَٰٓأَيُّهَا` → `يا أيها`, `يَٰبَنِىٓ` → `يا بني`); others — `ويا قوم`, `ها أنتم`, `سواء السبيل` (60:1:48), `نذير مبين` (71:2:6), `وأن لو` (72:16:1), and this word |
| `data-rasm-imlai` | the same convention plus detached waqf signs (`رَيْبَ ۛ`) |
| `data-text` (ligature) | none |

**Never tokenise a page by splitting text on whitespace.** `data-word-key` is the
only word key — one printed word can be two words in the modern spelling
(`سواء السبيل`, `نذير مبين`) and it is still one `<g class="word">`. It also
means a naive `data-search === query` fails for `يا أيها`; match on a
normalised, space-stripped form if you want them to join. Related: `بَعْدَ مَا` (2:181 p27, 8:6 p177, 13:37 p254) is **two words** in this
print's segmentation, not one spaced token.

### 9.5 Sajdah — 15 places

The sign (۩) and the overline belong together and are `data-standalone="1"` —
they are **never** inside a word. The group is emitted immediately **after** the
last element of its ayah (§5.4).

```xml
<!-- p176, complete -->
<g class="sajdah-mark" data-mark="sajdah" data-ayah-key="7:206">
  <path data-element-id="e1008" data-kind="mark" data-mark="sajdah_mark" data-mark-family="sajdah"
        data-sig="8097cfaa6e9371be" data-standalone="1" data-ayah-key="7:206" d="…"/>
  <path data-element-id="e1009" data-kind="mark" data-mark="sajdah_line" data-mark-family="sajdah"
        data-standalone="1" data-ayah-key="7:206" d="…"/></g>
```

The 15 sites: p176 (7:206), p251 (13:15), p272 (16:50), p293 (17:109), p309
(19:58), p334 (22:18), p341 (22:77), p365 (25:60), p379 (27:24 + 27:26), p416
(32:15), p454 (38:24), p480 (41:37 + 41:38), p528 (53:62), p589 (84:21), p598
(96:19).

Every site is one group holding both the sign and its line. At the two sites
that involve two ayahs (p379, p480) the group carries the later one, `27:26`
and `41:38` — §10.6.

Note the print draws the 96:19 sajdah on **p598**, not p597.

### 9.6 Hizb / rubʿ — 199 rosettes for 240 boundaries

Verified: all 240 rubʿ boundaries carry `data-rubu-al-hizb-start` on their ayah (§6.2),
and the 41 with no drawn rosette **all fall on an ayah 1** — a surah start,
where the banner marks the division instead. 41 of 41, no exceptions.

**Use `data-rubu-al-hizb-start` / `data-hizb-start` / `data-juz-start` for divisions, and
`g.division-mark` only when you want the drawn rosette.**

Where the rosette sits, and whether the rubʿ character U+06DE `۞` is in the
word text, **differs between the two bundles**:

| | word bundle | letter bundle |
|---|---|---|
| the rosette group | a standalone `<g class="division-mark">`, emitted immediately **before** the first element of that ayah (§5.4); its path has `data-standalone="1"` | the **first child of the ayah's first word**; its path has `data-at="0"` and no `data-standalone` |
| `۞` in the word's text | **absent** from every form | the display forms — `data-rasm-uthmani` on the page, `qpc`, `rasm_uthmani` and `rasm_imlai` in the index — begin with `۞` + U+00A0 NO-BREAK SPACE; `rasm` and `search` do not carry it |
| the word's `box` in the index | the word's letters | the letters **and the rosette** |

```xml
<!-- letter bundle -->
<g class="word" data-word-key="2:26:1" data-w="361" data-rasm-uthmani="۞ إِنَّ">
  <g class="division-mark" data-mark="hizb" data-ayah-key="2:26" …>
    <path data-at="0" data-kind="mark" data-mark="hizb" data-ayah-key="2:26" d="…"/></g>
  <g class="letter" …>…</g>
</g>
```

In the letter bundle the sign is a character of the word so that its ink links
to a character like every other path: `data-at` of every letter of such a word
counts from the start of the prefixed string. The form with the no-break space
is how the King Fahd Complex's own word-by-word data prints the sign.

**Compare word text across the two bundles with `rasm` or `search`**, or strip
a leading `۞` and U+00A0 first. `data-word-key` and `data-w` are the same in
both bundles.

### 9.7 Iqlab: ONE harakah + a small meem, not tanwin + meem

This print writes a single vowel plus a small م, in a **high form (U+06E2 ۢ)
or a low form (U+06ED ۭ)**; the low form is often fused into neighbouring ink.

```xml
<!-- p104, high form -->
<g class="word" data-word-key="4:165:9" data-rasm-uthmani="حُجَّةُۢ" data-rasm="حجة"
   data-rasm-imlai="حُجَّةٌ" data-search="حجة" data-qpc="حُجَّةُۢ">
  <path data-element-id="e404" data-kind="mark" data-mark="dammah"      data-iqlab="iq-4-165-9" d="…"/>
  <path data-element-id="e405" data-kind="mark" data-mark="small_meem" data-iqlab="iq-4-165-9" d="…"/></g>

<!-- p85, low form -->
<g class="word" data-word-key="4:41:6" data-rasm-uthmani="أُمَّةِۭ" data-rasm="أمة"
   data-rasm-imlai="أُمَّةٍ" data-search="أمة" data-qpc="أُمَّةِۭ">
  <path data-element-id="…" data-kind="mark" data-mark="kasrah"      data-iqlab="iq-4-41-6" d="…"/>
  <path data-element-id="…" data-kind="mark" data-mark="small_meem" data-iqlab="iq-4-41-6" d="…"/></g>
```

Three consequences:

1. **`data-rasm-uthmani` here is deliberately NOT quran.com's `text_uthmani`.** It
   writes `ُ` / `ِ` where quran.com writes `ٌ` / `ٍ`, matching `data-qpc` and the
   ink. `data-rasm-imlai` (and therefore `data-search`) still follows the tanwin
   convention. **The attributes disagree on purpose at every iqlab site.**
2. **`data-mark="small_meem"` does not say which form it is.** Take it from the
   word text.
3. `data-iqlab` pairs the harakah with the meem, but not at every site —
   §10.4.

### 9.8 Open tanwin (U+08F0–U+08F2)

`data-rasm-uthmani` uses the open forms: U+08F0 `ࣰ`, U+08F1 `ࣱ`,
U+08F2 `ࣲ`. `data-qpc` uses the QPC forms instead
(`سَنَةٗ` where rasm_uthmani has `سَنَةࣰ`); neither open form appears in `data-qpc`.

**These are not mojibake and not a non-standard encoding — they are this
print's orthography.** Normalise to families for comparison; never re-encode the
stored value. If your font lacks U+08F0–U+08F2 you will see tofu; that is a font
problem, not a data problem, and it never affects the drawn page (there is no
`<text>` here at all).

### 9.9 A mark can be drawn outside its word

The tanwin of a word-final `ة` floats into the gap toward the next word. p350
`24:2:12`:

```xml
<g class="word" data-word-key="24:2:12" data-rasm-uthmani="رَأْفَةࣱ" data-rasm="رأفة"
   data-rasm-imlai="رَأْفَةٌ" data-search="رأفة" data-qpc="رَأۡفَةٞ">
  … <path data-element-id="e197" data-kind="mark" data-mark="tanwin_al_damm"
          data-mark-family="diacritic tanwin" data-form="staggered" d="…"/></g>
```

**Never assign a mark to a word by nearest ink or by bounding-box
containment.** The `data-word-key` of the enclosing group is the answer. This is also
why word bounding boxes overlap, and why §5.4 says to trust document order over
geometry for reading order.

The same holds where a tanwin_al_kasr is drawn **inside the bowl of a ج** — an art
fact of this print.

### 9.10 The pronominal suffix's small waw and small ya

`ـهُۥ` / `ـهِۦ`. These are `data-mark="small_waw"` / `"small_yaa"` — **marks, not
letters** — and they sit clear of their own word's ink, always **nearer the next
word**.

```xml
<g class="word" data-word-key="16:48:10" data-rasm-uthmani="ظِلَٰلُهُۥ" data-rasm="ظلله"
   data-rasm-imlai="ظِلَالُهُ" data-search="ظلاله" data-qpc="ظِلَٰلُهُۥ">
 <g class="ligature" data-text="ظلله">
  … <path data-element-id="e536" data-kind="mark" data-mark="small_waw" d="…"/></g></g>
```

`data-rasm` has no waw; `data-rasm-imlai` and `data-search` drop the ۥ entirely.

### 9.11 The silent alef of واو الجماعة

The alef **is** drawn — a `data-kind="body"` path of its own. The round zero that
marks it silent (`rounded_zero`, U+06DF) is emitted in the **previous** ligature
group, not on the alef. p11 `2:70:1`:

```xml
<g class="word" data-word-key="2:70:1" data-rasm-uthmani="قَالُوا۟" data-rasm="قالوا"
   data-rasm-imlai="قَالُوا" data-search="قالوا" data-qpc="قَالُواْ">
 <g class="ligature" data-text="قا">…</g>
 <g class="ligature" data-text="لو">
  <path data-element-id="e4" data-kind="body" d="…"/>
  <path data-element-id="e5" data-kind="mark" data-mark="dammah" d="…"/>
  <path data-element-id="e6" data-kind="mark" data-mark="rounded_zero" data-mark-family="sifr" d="…"/></g>
 <g class="ligature" data-text="ا"><path data-element-id="e7" data-kind="body" d="…"/></g></g>
```

### 9.12 Header ink is not decomposed — and that is deliberate

Paths with `data-kind="header_ink"` sit **inside `<g class="surah-name">`
and `<g class="basmalah">`**. **None carries `data-mark`.** Banner ink is identified, never decomposed. A consumer
iterating words will not see it, and that is correct.

Marks that belong to no word are **all legitimate** (`data-standalone="1"`:
the hizb rosettes and the sajdah paths). Verified corpus-wide: **0 named
marks are loose on a text line outside every group.** (Older bundles have such
marks on pages 377, 418, 446 and 507, from the surah banners missing there; check
`document.querySelectorAll('g.surah-name').length === 1` on those pages.)

### 9.13 One calligraphic stroke can be two contours

Where the pen lifts mid-stroke, a single stroke is drawn as two contours
(p203 `9:102:6` صَٰلِحࣰا, p189 `9:20:9`, p219 `10:92:2`). Their boxes *overlap*
end to end; genuinely separate pieces have a positive gap. **Contour count is
not piece count.**

---

## 10. Known limits and defects — stated honestly

### 10.1 There are no `<text>` elements

Restated because it is the limit people meet first. See §1. The word bundle
has no letter segmentation either; the letter bundle is §6.9.

### 10.2 Reserved

*(Was: "the ayah-mark's `data-ayah-key` is reversed on 441 pages". **Fixed
2026-08-30** — the markers are bound by position and every ayah fragment now
links to its own. See §7.)*

### 10.3 The ligature layer is not a letter segmentation *(dev profile)*

Comparing each word's concatenated `data-text` against its `data-rasm`
(normalising hamzah seats, alef forms, `ى`/`ي` and `ة`/`ه`): in some words the
groups come in a different order from the rasm, and in some they spell
**fewer** letters than the rasm. In **no** word do they spell more.

Examples: p15 `2:98:5` `وملئكته` emits one group `['و']`; p17 `2:110:2`
`ٱلصلوة` emits `['ا','لصلو']` and the `ة` has no group at all. **Some groups hold
zero `body` paths** (legitimately at the two fused-hamzah sites — §9.0b).

**Use `data-rasm-uthmani` / `data-rasm` on the word as the text of record.** Treat
`data-text` as a hint about which letters a group's ink covers, never as a
spelling, and never pair group *i* with letter run *i*. This is why the layer is
dropped in the production profile.

### 10.4 `data-iqlab` is incomplete

At some sites both the harakah and the meem are tagged; **at others only the
meem is**, so the vowel it belongs with is unfindable. **These meems carry no
`data-iqlab` at all:** p45 `2:265:12`, p446 `37:11:12`, p455 `38:42:4`, p577
`74:51:3`; and p577's is also the only
`small_meem` in the corpus with no `data-sig`.

```js
// safe: pair only when both halves are tagged
const byId = new Map();
for (const p of doc.querySelectorAll('path[data-iqlab]')) {
  const id = p.dataset.iqlab;
  if (!byId.has(id)) byId.set(id, []);
  byId.get(id).push(p);
}
const complete = [...byId.values()].filter(v => v.length === 2);   // harakah + meem
```

### 10.5 Sole survivors of otherwise-uniform rules

A strict consumer must special-case these:

- **An unnamed mark** — p1 `1:2:1` `ٱلْحَمْدُ`, `data-element-id="e34"`:
  `data-kind="mark"` with no `data-mark`.
- **These paths have no `data-sig`** (split or synthesised outlines):
  p37, p38, p126 ×2, p146, p159, p342, p362, p431 ×2, p460, p485, p556, p567,
  p577.
- **p17 has paths with no `data-kind` at all** — page ornaments outside both
  `#content` and `#ayah_markers`, passed through from the artwork untouched.
  p17 is the only page with them.
- **`small_noon` is the only orthographic sign with no `data-mark-family`.**
  `[data-mark-family~="reading_sign"]` also silently drops it — it is not a
  reading sign in this registry.
- **p7 is the only file declaring `xmlns:xlink`.**
- **p17 and p144 emit one `<g class="ayah-fragment">` per WORD**, not per (ayah, line).
  All "reopened" ayah groups in the corpus are on these two pages, and their
  `data-ayah-fragments` values exceed the page's line count. §7's
  contract still holds there (parts are `1..N` and all link to the marker) —
  there are just far more of them than lines.

### 10.6 Two sajdah groups span two ayahs

The format document of release 1.1.2 described the sajdah on p379 as two
groups, the line keyed `27:24` and the sign `27:26`, and the one on p480 the
same way with `41:37` and `41:38`. In this release each is one `sajdah-mark`
group, holding the sign and the line, with `data-ayah-key` `27:26` and
`41:38`. A consumer that needs the ayah the line is drawn over must take it
from the geometry.

### 10.7 Element order inside a word is not right-to-left

Most words do not have their paths in descending x. Word order
within a line is correct (§5.4); path order within a word is not normalised.
Sort by geometry if you need it.

### 10.8 Words split differently from other decompositions

Some word-level segmentation disagreements with MushafDatabase remain, for
example p11, p262 `لَّوۡمَا` and p451.

### 10.9 The SVG is authoritative; the index is derived — with one exception

Every value in `index/` is read back out of the shipped pages, so the two
cannot drift unnoticed. The one exception, by design since 2026-09-04: the four
derived text forms (`rasm`, `rasm_imlai`, `search`, `qpc`) are not on a production
word group at all (§6.1) and come from the verified word cache, through the
same derivations the dev profile uses inline. The checker proves the cache and
every page agree on `rasm_uthmani`. Always read `words.json`'s own `fields` array
rather than assuming a column order.

### 10.10 The letter layer: what is and is not claimed *(letter bundle)*

**No accuracy figure is quoted, because none was measured.** The ink checks of
§6.9 prove that no ink is lost, added or shared. They say nothing about whether
a joint falls where a calligrapher would put it. That is the analyzer's
convention, published as it is: the reviewer accepted the division by eye, it
was not scored against a hand-cut truth set, and where exactly a joint falls
inside a connecting stroke is a convention of the tool, not a fact of the print.

**Known limits, stated rather than fixed:**

- **Slivers.** At some cuts the analyzer's pieces left a strip of the contour in
  no letter. Each strip lies between two neighbouring letters and touches both
  about equally (within 10% on every one), so which of the two takes it is close
  to arbitrary. The rule gives it to the piece it touches most; a kashida that
  only brushes it does not take it. No ink is lost either way. The reviewer has
  judged one of them by eye.
- **A hairline at a cut.** The pieces are the analyzer's re-drawing of our
  outlines, so the edge of a cut letter can differ from the artwork by less
  than 0.0125 units (a strip that wide is what the checks catch). For a
  print-exact outline, use the word bundle.
- **Seams.** Two pieces of one contour meet edge to edge. Rendered, the
  anti-aliased pixels on the cut can be lighter than in the word page; the ink
  is the same.
- **Marks placed by the join, not by the analyzer:** by position, and by
  count (§6.9). The reviewer checked the positional ones on a sheet; they are
  listed per page in the build's notes, not in the bundle.
- **Some mark paths carry no `data-at`.** The sajdah sign and its line are no
  character of a word. The others could not be paired with a character of
  `qpc` without a guess: p11 `2:72:4` (hamzah),
  p282 `17:7:12` (maddah, small waw), p525 `52:37:7` (seen al-qiraah).
- **Glyphs with no ink are a word-level matter.** Where a neighbouring word
  holds a letter's ink in the word bundle, no letter group of the right word
  can hold it either.

---

## 11. Recipes

```js
// ---- highlight ayah 2:255 (all its line fragments) ----
doc.querySelectorAll('g.ayah-fragment[data-ayah-key="2:255"] g.word')
   .forEach(w => w.querySelectorAll('path')
                  .forEach(p => p.setAttribute('fill', '#0a7')));

// ---- click anywhere on the ink -> word + ayah ----
svg.addEventListener('click', e => {
  const w = e.target.closest('g.word');
  if (w) console.log(w.dataset.wordKey, w.closest('g.ayah-fragment').dataset.ayahKey);
});

// ---- one word ----
doc.querySelector('g.word[data-word-key="2:255:3"]');   // there is no id= on words

// ---- an ayah's medallion, and back again ----
const frag = doc.querySelector('g.ayah-fragment[data-ayah-key="2:255"]');
const mk   = doc.getElementById(frag.dataset.marker);          // <g id="mk-2-255">
doc.querySelectorAll(`g.ayah-fragment[data-mark="${mk.id}"]`);        // all fragments

// ---- is this ayah complete on this page? ----
frag.dataset.ayahFragments === String(
  doc.querySelectorAll(`g.ayah-fragment[data-ayah-key="2:255"]`).length);    // always true

// ---- the plain text of a printed line ----
[...doc.querySelectorAll('g.line[data-line="7"] g.word')]
  .map(w => w.dataset.rasmUthmani).join(' ');

// ---- search this page (DEV profile: data-search is not in the bundle, §2) ----
const fold = s => s.replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
[...doc.querySelectorAll('g.word')]
  .filter(w => fold(w.dataset.search).includes(fold('الرحمن')))
  .map(w => w.dataset.wordKey);

// ---- colour the dots differently from the harakahs ----
doc.querySelectorAll('path[data-mark-family~="dots"]')
   .forEach(p => p.setAttribute('fill', '#b03030'));
// equivalently, without relying on data-mark-family:
//   'path[data-mark="dot"],path[data-mark="two_dots"],path[data-mark="three_dots"]'

// ---- every waqf sign on the page, with the word it belongs to ----
[...doc.querySelectorAll('path[data-mark-family~="waqf"]')]
  .map(p => [p.closest('g.word')?.dataset.wordKey, p.dataset.mark]);

// ---- waqf_al_muanaqah partners ----
doc.querySelectorAll(`path[data-pair="${p.dataset.pair}"]`);   // exactly two

// ---- juz / hizb / rubu_al_hizb boundaries on this page ----
[...doc.querySelectorAll('g.ayah-fragment[data-rubu-al-hizb-start]')]
  .map(g => ({aid: g.dataset.ayahKey, rubu_al_hizb: +g.dataset.rubuAlHizbStart,
              juz: g.dataset.juzStart, hizb: g.dataset.hizbStart}));

// ---- crop to one ayah ----
// 1. (dev profile) remove path.ayahPolygon first — different frame, sits on top
// 2. drop every g.word whose data-word-key is not in the ayah
// 3. drop the now-empty g.ayah-fragment / g.line wrappers
// 4. getBBox() on #content, pad, write it back as the viewBox
```

```python
# ---- which page is 2:255 on?  (companion index) ----
idx = json.load(open("index/pages.json"))
def num(aid): s, a = aid.split(":"); return (int(s), int(a))
page = next(p["page"] for p in idx["pages"]
            if num(p["first_ayah"]) <= (2, 255) <= num(p["last_ayah"]))

# ---- where is a word on the page? ----
# Boxes are per page, in pages/NNN.svg viewBox units — see `box_space`.
pg   = json.load(open("index/by-page/%03d.json" % page))
box  = next(w["box"] for w in pg["words"] if w["word_key"] == "2:255:3")
```

---

## 12. Reference facts, all measured

| fact | value |
|---|---|
| pages | 604 (602 with 15 lines, 2 with 8) |
| words | 77,432; one `<g class="word">` per word, every `data-word-key` distinct |
| ayahs | 6,236; one `<g class="ayah-fragment">` per line an ayah occupies |
| **ayahs spanning two pages** | **0** — every page begins and ends on an ayah boundary, so `mk-…` ids are globally unique. |
| lines | every line holds words or is a header line (surah-name or basmalah) |
| words in the wrong `<g class="line">` | **0** |
| `header_ink` paths | one per header line |
| `data-mark` vocabulary | registry declares 36, 35 active; `sajdah` is group-level only |
| ayah medallions | one group per ayah, each with `id` + `data-ayah-key` |
| surah-name / basmalah groups | 114 / 112 (basmalah absent for surahs 1 and 9) |
| named marks belonging to no word | all `data-standalone="1"`: the hizb rosettes and sajdah paths in the word bundle, the sajdah paths in the letter bundle, where a rosette is its word's first child (§9.6) |
| hizb rosettes / rubʿ boundaries | 199 / 240 (every boundary carries `data-rubu-al-hizb-start`) |
| sajdah signs | 15, one group per site |
| letter groups (letter bundle) | every one with `data-at` and a body path; 0 unsplit |
| `ayahPolygon` paths (dev only) | one per ayah |
