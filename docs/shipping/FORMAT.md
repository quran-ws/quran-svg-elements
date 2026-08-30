# Format specification — Quran page SVGs, Hafs / KFGQPC Madani

Edition id `hafs-kfgqpc` · 604 pages · 77,432 words · 6,236 ayahs · 114 surahs.
Artwork: the **KFGQPC Madani mushaf, V2 1421H print**.

This document ships with the files. Everything in it was verified against the
real build; every count is a measurement over all 604 emitted pages, not an
estimate. Where the files are inconsistent, this document says so (§10) rather
than describing an ideal that does not exist.

> **Status.** Build of **2026-08-30**. Two profiles now exist (§2); every
> statement below says which one it applies to when they differ.
>
> Changes since the 2026-08-29 revision, all consumer-visible:
> `data-search` added; ayah fragments and medallions linked by `id` /
> `data-marker`; medallion labels rebound by position (they were wrong on 598
> pages); 58 misfiled words returned to their printed line; the four missing
> surah banners restored; the production profile introduced.

---

## 1. What these files are

Each file is one printed page of the mushaf, as **vector outlines**, with the
ink semantically decomposed:

- every **word** is exactly one `<g class="word">` — 77,432 groups, 77,432
  distinct `data-wid`, **no duplicates anywhere in the corpus**;
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
- **There is no letter-level decomposition.** The `<g class="ligature">`
  grouping is a *rendering run*, not a spelling. It is not a reliable letter
  segmentation — see §10.3 — and it is not in the production profile at all.
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
| `<g class="ligature">` inside a word | **yes** — 156,707 groups | **dropped** |
| `<path class="ayahPolygon">` | **yes** — 6,236 | **dropped** |
| `data-eid`, `data-sig`, `data-mark-family` | yes | yes |
| everything else in this document | identical | identical |

**The two render identically.** Measured on page 3: 758,232 bytes dev vs
744,103 bytes production, with all 127 words, all 698 marks and all 988 ink
paths present in both, and a raster diff of the two showing no difference.
Corpus-wide the production profile is 449.3 MiB raw / 109.8 MiB gzip / 69.6 MiB
brotli, against 456.7 / 111.0 / 70.2 MiB for dev — **1.6% smaller raw, 0.9%
smaller brotli.** Size is not the reason for the split; semantics is.

```js
// which profile is this file?
const isDev = doc.querySelector('g.ligature') !== null;
```

### What production removes, and what replaces it

**The ligature layer.** It is a dev instrument: an empty `<g class="ligature">`
is how a stolen letter is detected. It is *not* a spelling of the word (§10.3),
so a consumer that treats it as one gets 156 words wrong. The word's text of
record is `data-uthmani` / `data-rasm` on the `<g class="word">`, and that is
present in both profiles.

**The invisible ayah polygons.** These were how ayah highlighting and
click-detection worked before there were word elements. Word level supersedes
both, **and is exact where the polygon is not**: the polygon is a rectangular
band cut on a straight vertical line, while the real boundary between two ayahs
that share a printed line is jagged — letters interleave and marks overhang.
Measured over six sample pages, **8 of 6,243 elements (0.13%, about one in 750)
have ink sitting inside a *neighbouring* ayah's polygon**, e.g. on page 3 a
22.1 × 1.0 unit piece of ayah 2:8 lies inside 2:9's polygon. Highlighting from
polygons paints part of the wrong ayah or misses ink of its own. Highlighting
from words cannot: **the ayah's ink *is* its words.**

Two conveniences do go away, and both are about ten lines of JS:

```js
// (a) CLICK / TAP -> which ayah?  Hit a word path, walk up.
svg.addEventListener('click', e => {
  const word = e.target.closest('g.word');
  if (!word) return;                       // tapped bare paper
  const ayah = word.closest('g.ayah');
  console.log(ayah.dataset.aid, word.dataset.wid);   // "2:8"  "2:8:3"
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
  for (const w of doc.querySelectorAll(`g.ayah[data-aid="${aid}"] g.word`)) {
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
  .filter(w => w.dataset.wid.startsWith('2:6:'))
  .map(w => w.dataset.uthmani).join(' ');
// => "إِنَّ ٱلَّذِينَ كَفَرُوا۟ سَوَآءٌ عَلَيْهِمْ …"

// highlight the whole ayah (NOTE: several fragments — one per printed line)
doc.querySelectorAll('g.ayah[data-aid="2:6"]').forEach(g => g.classList.add('hl'));

// one word
doc.querySelector('g.word[data-wid="2:6:3"]');

// search: strip marks, use data-search
[...doc.querySelectorAll('g.word')].filter(w => w.dataset.search === 'الذين');
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
   <g class="ayah-marker" id="mk-2-16" data-aid="2:16">
    <g transform="translate(45.272 87.116) scale(0.011 -0.011)">
     <path data-kind="ayah-marker-ornament" d="m1248,4q…" fill="#231f20"/></g>
    <g transform="translate(49.652 83.898)" ayah:x="14.53" ayah:y="530.03">
     <path data-kind="ayah-number" fill="#231f20" fill-rule="evenodd" d="M…"/></g>
   </g>
   …
  </g>

  <g id="content">
   <g class="line" data-line="1">
    <g transform="translate(206.04 112.26)">               <!-- the LINE's own frame -->
     <g class="ayah" data-aid="2:6" data-marker="mk-2-6" data-part="1" data-ayah-parts="2">
      <g class="word" data-wid="2:6:1" data-uthmani="إِنَّ" data-rasm="إن"
                      data-imlaei="إِنَّ" data-search="إن" data-qpc="إِنَّ">
       <g class="ligature" data-text="ا">
        <path data-eid="e1" data-kind="mark" data-mark="kasra"
              data-sig="b631f71b4956be63" d="M84.59 339.69…"
              fill="#231f20" fill-rule="evenodd"/>
        <path data-eid="e2" data-kind="mark" data-mark="hamza"
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

 <path class="ayahPolygon" fill-opacity="0" id="verse-13"
       number="002006" ayah="6" surah="2" d="M…"/>          <!-- dev only; UNFLIPPED frame -->
 …
</svg>
```

### The groups, and what each one means

| group | count (corpus) | meaning |
|---|---:|---|
| `<g id="ayah_markers">` | 604 | **all** ayah medallions of the page, in one layer, outside `#content`. |
| `<g class="ayah-marker" id="mk-s-a">` | 6,248 | one medallion: an ornament ring path + a numeral path. 6,236 carry `id` + `data-aid`; the other 12 are decorative rosettes on pages 1–2 with no ayah (§9.2). |
| `<g id="content">` | 604 | all page text. |
| `<g class="line" data-line="N">` | 9,046 | one printed line. `N` is 1..15 (1..8 on pages 1–2). Its single child `<g transform="translate(…)">` carries the line's frame. **8,820 hold words; the other 226 are the header lines** (114 surah-name + 112 basmalah). |
| `<g class="ayah" data-aid="s:a">` | 13,489 | **one line's run of one ayah.** An ayah on three lines has three of these. Never treat one as "the ayah" — §7. |
| `<g class="word" data-wid="s:a:w">` | 77,432 | **one word. Globally unique. This is the anchor of the format.** |
| `<g class="ligature" data-text="…">` | 156,707 | a joined run of letters, as a rendering unit. **Dev profile only.** See §10.3 for its limits. |
| `<g class="surah-name" data-sid="N">` | 114 | the surah-name banner. One per surah, all 114 present. |
| `<g class="basmalah" data-sid="N">` | 112 | the basmalah banner. Absent only for **surah 1** (its basmalah IS ayah 1:1) and **surah 9** (which has none). |
| `<g class="sajdah-mark" data-mark="sajdah" data-aid>` | 17 | the prostration sign (۩) and its overline. 15 sites; two are split into two groups — §9.5. |
| `<g class="hizb-mark" data-mark="hizb" …>` | 199 | a rubʿ / hizb / juz rosette (۞). 199 drawn for 240 boundaries — §9.6. |
| `<path class="ayahPolygon">` | 6,236 | invisible legacy hit region per ayah, from the upstream artwork. **Dev profile only**, and **outside the page frame** — §5.3. Do not build on it; see §2. |

### Nesting rules

```
svg
├ g[transform=matrix …]              page frame
│ ├ g#ayah_markers
│ │ └ g.ayah-marker[id][data-aid]
│ │   ├ g[transform] > path[data-kind=ayah-marker-ornament]
│ │   └ g[transform] > path[data-kind=ayah-number]
│ └ g#content
│   └ g.line[data-line]
│     └ g[transform]                 line frame
│       ├ g.ayah[data-aid][data-marker][data-part][data-ayah-parts]
│       │ └ g.word[data-wid]
│       │   └ g.ligature[data-text]  (dev profile only)
│       │     └ path[data-kind]
│       ├ g.surah-name | g.basmalah  → path[data-kind=header-ink] only
│       ├ g.sajdah-mark              → path[data-mark=sajdah-sign|sajdah-line]
│       └ g.hizb-mark                → path[data-mark=hizb]
└ path.ayahPolygon                   siblings of the page frame, at the end (dev only)
```

`g.word` is always inside `g.ayah`, which is always inside a line frame inside
`g.line`. There is **no** case of a word outside an ayah group, and (since
2026-08-30) no named mark loose on a text line outside any group.

---

## 5. Coordinates, frames and reading order

### 5.1 The page frame

| | pages 3–604 | pages 1–2 |
|---|---|---|
| `viewBox` | `0 0 345 550` (602 pages) | `-53.3109 -198.4777 345 550` |
| page frame | `matrix(1.3333 0 0 -1.3333 -55 640)` on odd pages (301), `… -115 640)` on even (301) | `matrix(1.3333 0 0 -1.3333 -136 482)` |
| `<g class="line">` | 15 | 8 |

**The y scale is negative.** Inside the page frame, y increases *upward*.
Screen y = `640 − 1.3333 · y` on a normal page. A consumer computing positions
must apply the matrix; raw path coordinates are not viewBox coordinates.

The odd/even split means the same raw x is 60 units apart on recto and verso.
**Never compare raw coordinates across pages.**

### 5.2 The line frame

Each `<g class="line">` has exactly one child `<g transform="translate(x y)">`.
On **600 of 604 pages every line shares the same translate**, so it looks
redundant — but on **pages 1, 2, 17 and 144** the lines differ (2, 2, 15 and 15
distinct translates respectively). Always compose
`page frame × line frame`; never hoist the translate out.

```
(x_view, y_view) = PAGE_MATRIX ∘ LINE_TRANSLATE applied to (x_path, y_path)
```

`tools/bundle_geom.py` (exact Bezier extents) and `tools/bundle_extract.py`
are the reference implementation — note they honour a path's own `transform`,
which 72 ink paths on p17 and p144 carry. In a browser,
`getBBox()` on a `g.word` already returns coordinates in that word's own line
frame; `getCTM()` composes the rest.

### 5.3 The `ayahPolygon` layer is in a different frame (dev profile only)

The 6,236 `<path class="ayahPolygon">` are **siblings of the page frame**, not
children of it. Their coordinates are plain, unflipped viewBox units. They also
come last in document order, so they sit on top and swallow pointer events —
set `pointer-events: none` on them, or remove them before calling `getBBox()`.
The production profile does not have them, which is one reason to prefer it.

They use a second, legacy attribute vocabulary from the upstream artwork:

```xml
<path class="ayahPolygon" fill-opacity="0" id="verse-13"
      number="002006" ayah="6" surah="2" d="M…"/>
```

`number` is `%03d%03d` of surah and ayah. Both vocabularies name the same ayah;
`data-aid` is the one to use. **These polygons are an approximation — see §2.**

### 5.4 Reading order

- **Words within a line are in reading order.** Verified: on **8,820 of 8,820
  lines that hold words** the `data-wid` sequence is strictly ascending.
  Document order is reading order — right to left — and you should rely on it
  rather than on geometry (bounding boxes overlap, because a mark may
  legitimately be drawn over the neighbouring word: see §9.9).
- **Lines are in document order 1..15**, top to bottom.
- **Across line boundaries the sequence is now unbroken on all 604 pages.**
  Concatenating a page's words line by line gives the mushaf's own word order
  exactly. (Until 2026-08-30, 58 words on 52 pages were emitted inside the
  wrong `<g class="line">`; they are not any more.)
- **Paths within a word are NOT ordered right to left.** Measured: only 15,102
  of 77,432 words (19.5%) have their paths in descending x. Do not infer mark
  order from document order inside a word; use the path geometry. §10.7.

---

## 6. Attribute reference

Counts are over all 604 pages of the current build, both profiles unless noted.

### 6.1 On `<g class="word">` — always present, all six

```xml
<g class="word" data-wid="2:6:2" data-uthmani="ٱلَّذِينَ" data-rasm="ٱلذين"
   data-imlaei="الَّذِينَ" data-search="الذين" data-qpc="ٱلَّذِينَ">
```

| attribute | count | what it is | example (2:6:2) |
|---|---:|---|---|
| `data-wid` | 77,432 | `surah:ayah:word`, 1-based. **The key.** Globally unique. | `2:6:2` |
| `data-uthmani` | 77,432 | **the print's own text**, full diacritics | `ٱلَّذِينَ` |
| `data-rasm` | 77,432 | skeleton of `data-uthmani` — the **ink** | `ٱلذين` |
| `data-imlaei` | 77,432 | modern spelling, **with** marks | `الَّذِينَ` |
| `data-search` | 77,432 | skeleton of `data-imlaei` — **the search key** | `الذين` |
| `data-qpc` | 77,432 | the same text in KFGQPC codepoints | `ٱلَّذِينَ` |

**Which one to use, and this is the part people get wrong:**

- **Displaying the text of the page → `data-uthmani`.** It is the text of
  record, matching the ink. Composite source: quran.com `text_uthmani` +
  KFGQPC waqf + DigitalKhatt at iqlab sites (§9.7).
- **Matching text to the glyphs on the page → `data-rasm`.** It is the uthmani
  skeleton, so it says what shapes are actually drawn.
- **A search box → `data-search`. Never `data-rasm`.** The rasm is the uthmani
  skeleton, and the uthmani spelling writes several long vowels as *combining
  marks*, which stripping deletes outright. Nobody types the result:

  | word | `data-uthmani` | `data-rasm` (not searchable) | `data-search` (searchable) |
  |---|---|---|---|
  | p3 `2:6:2` | `ٱلَّذِينَ` | `ٱلذين` — starts with alef **wasla** U+0671 | `الذين` |
  | p10 `2:63:3` | `مِيثَٰقَكُمْ` | `ميثقكم` — the dagger alef U+0670 is gone | `ميثاقكم` |
  | p272 `16:48:10` | `ظِلَٰلُهُۥ` | `ظلله` | `ظلاله` |
  | p329 `21:88:7` | `نُـۨجِى` | `نجى` | `ننجي` |

  Character-set proof over all 77,432 words: `data-rasm` uses **36** distinct
  characters including 13,483 alef-wasla (U+0671) and **no** alef-maddah
  (U+0622); `data-search` uses **37**, no alef-wasla at all, 1,511 alef-maddah,
  and 43,542 plain alef against the rasm's 25,184.

**Nothing is folded in any of them.** This is deliberate. `ا أ إ آ ٱ` stay
distinct, `ى` and `ي` stay distinct, `ة` and `ه` stay distinct — `data-search`
contains all of `ء أ إ آ ؤ ئ ة ى ي` as separate characters. If your users
expect a forgiving search, fold on **your** side and keep the stored value as
written:

```js
const fold = s => s.replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
const hits = [...doc.querySelectorAll('g.word')]
  .filter(w => fold(w.dataset.search).includes(fold(query)));
```

The six attributes **legitimately disagree** at iqlab sites and around tanween
(§9.7, §9.8). That is not corruption. Two further cautions: **367
`data-search` values contain a space** (the vocative convention, `يَا أَيُّهَا` →
`يا أيها`) and 4,933 `data-imlaei` values do — see §9.4, and never tokenise on
whitespace.

### 6.2 On `<g class="ayah">`

| attribute | count | format | notes |
|---|---:|---|---|
| `data-aid` | 13,489 | `surah:ayah` | which ayah this fragment belongs to |
| `data-marker` | 13,489 | `mk-<surah>-<ayah>` | the `id` of this ayah's medallion — §7 |
| `data-part` | 13,489 | `1`..`N` | which fragment this is, in reading order |
| `data-ayah-parts` | 13,489 | `N` | how many fragments the ayah has on this page |
| `data-juz-start` | 30 ayahs | `1`..`30` | this ayah begins that juz |
| `data-hizb-start` | 60 ayahs | `1`..`60` | begins that hizb |
| `data-nisf-start` | 60 ayahs | `1`..`60` | begins that half-hizb boundary, numbered 1..60 through the mushaf |
| `data-rub-start` | 240 ayahs | `1`..`240` | begins that rubʿ |

Each appears **once**, on `data-part="1"` of the ayah that opens the division —
so the attribute counts ARE the division counts: 30, 60, 60 and 240.

They used to be repeated on every fragment (72, 140, 168 and 669 instances),
which made a consumer looping over `[data-rub-start]` print the same rubʿ seven
times on p575, where 73:20 spans seven lines. A division opens once. An ayah
never spans pages (6,236 ayahs, 6,236 page-ayah pairs), so part 1 is always on
the page the division opens on.

They are complete: all 30 juz, all 60 hizb, all 240 rubʿ boundaries are marked,
including the 41 that have no drawn rosette (§9.6).

`data-nisf-start` is NOT the `1`/`2` half-index — that is `data-nisf` on the
hizb rosette (§6.4). It numbers the 60 half-hizb BOUNDARIES through the mushaf,
1 at 2:44 to 60 at 94:1, and lands on exactly the ayahs whose `rub_in_hizb` is
3, i.e. the start of each hizb's second half.

```js
// where does juz 30 begin?
doc.querySelector('g.ayah[data-juz-start="30"]')?.dataset.aid;   // "78:1" on p582
```

### 6.3 On `<g class="ayah-marker">`

| attribute | count | format |
|---|---:|---|
| `id` | 6,236 | `mk-<surah>-<ayah>`. **Globally unique** — no ayah spans two pages (§11). |
| `data-aid` | 6,236 | `surah:ayah` |

12 markers on pages 1–2 have neither: they are the decorative rosettes of the
opening frame (§9.2).

### 6.4 On `<g class="line">`

| attribute | count | format |
|---|---:|---|
| `data-line` | 9,046 | `1`–`15` (`1`–`8` on pages 1–2). The printed line number, top to bottom. **Correct for all 77,432 words** since 2026-08-30. |

### 6.5 On `<path>`

| attribute | count | values | notes |
|---|---:|---|---|
| `data-kind` | 616,561 | `mark` 436,629 · `body` 161,778 · `ayah-marker-ornament` 6,248 · `ayah-number` 6,236 · `header-ink` 5,670 | Present on **every** path except the 6,236 `ayahPolygon` and 4 page-ornament paths on p17 (§10.5). `body` = letter ink. |
| `data-mark` | 436,843 | 35 names, §8 | Attribute occurrences. The **logical** mark count is 436,627 — a mark drawn as more than one path is one mark. On every `data-kind="mark"` path but **two**: one unnamed (p1 `e34`) and one carrying `data-mark-part` instead (p146). |
| `data-mark-family` | 393,970 | **token list** — `diacritic` 280,333 · `dots` 105,270 · `tanween` 8,554 · `waqf` 4,272 · `sifr` 4,054 · `sajdah` 30 · `reading-sign` 11 | **Space-separated, like `class` — match with `~=`, not `=`.** See below. Only on marks that have a family. **Derivable from `mark-taxonomy.v2.json`** — prefer the registry, which also covers `small-noon` (§10.5). |
| `data-eid` | 598,407 | `e1`, `e2`, … | **Not stable across builds. Never key on it.** Unique within a page. Only on word/standalone ink — never on marker, header or polygon paths. |
| `data-sig` | 598,392 | 16 hex | Outline shape signature used by the review loop. **Not an identity** — §8.5. |
| `data-form` | 8,506 | `staggered` 6,598 · `stacked` 1,908 | Only on the `tanween` family: how the pair of strokes is drawn. 48 of the 8,554 tanween paths have none. |
| `data-iqlab` | 940 | `iq-<surah>-<ayah>-<word>` | Links a haraka to its small meem at an iqlab site. **Incomplete — §10.4.** |
| `data-pair` | 6 | `mnq-<surah>-<ayah>-<n>` | Links the two halves of a muʿānaqah. Exactly 6 in the corpus (§9.3). |
| `data-standalone` | 229 | `1` | Marks that belong to no word: 199 hizb + 30 sajdah. |
| `data-aid` | 229 | `surah:ayah` | On those same 229 standalone paths. |
| `data-mark-part` | 1 | `three-dots` | A path that is part of a mark named on another path (p146 `6:141:14`). §10.5. |
| `fill` / `fill-rule` | all ink | `#231f20` / `evenodd` | Every ink path in the mushaf is the same colour. |

`data-eid`, `data-sig` and `data-mark-family` are present in **both** profiles.
`data-eid` and `data-sig` exist for the review loop; a consumer should not key
on either.

#### `data-mark-family` is a token list — use `~=`, never `=`

A mark can belong to more than one family, so the attribute holds
space-separated tokens exactly like `class`:

```css
[data-mark-family~="diacritic"] { }   /* correct */
[data-mark-family="diacritic"]  { }   /* WRONG — misses every tanween */
```

Only the three tanween carry two tokens today (`"diacritic tanween"`, 8,554
paths). They are vowel marks *and* they are the tanween, and both groupings are
real: hiding the diacritics must reach them, and §8.2 groups on them. Every
other family is single-token, so `=` happens to work there — but it is the wrong
habit and will break the next time a mark needs two families. Always `~=`.

### 6.6 Page identity — nine attributes on the root `<svg>`

Every page states which mushaf it belongs to, so a file downloaded on its own is
self-describing:

```xml
<svg data-mushaf="hafs-kfqc" data-qiraa="asim" data-riwaya="hafs"
     data-edition="kfgqpc-1421"
     data-mushaf-name-ar="حفص عن عاصم" data-mushaf-name-en="Hafs 'an Asim"
     data-ayah-numbering="kufi" data-ayah-total="6236" data-page="42" …>
```

Each appears exactly 604 times, once per page. Values come from the
`quranpedia/qiraat-ayah-map` dataset; the full records — names, descriptions and
the provenance of the numbering choice — belong in the bundle's `catalogue.json`
rather than being repeated on every page.

Three of these are easy to misread:

- **`data-riwaya` is not `data-qiraa`.** Ḥafṣ is a *transmission* of ʿĀṣim's
  *reading*; Shuʿba is the other. Warsh and Qālūn are both Nāfiʿ. "The Ḥafṣ
  qiraa" is an error — say the Ḥafṣ riwaya, or the reading of ʿĀṣim.
- **`data-ayah-numbering` is a property of the printed EDITION, not of the
  qiraa.** It must never be derived. The King Fahd al-Dūrī edition proves why:
  its qiraa (Abū ʿAmr) implies the Basran count, but its colophon declares the
  First Madinan, and its pages agree with First Madinan in 110 of 114 surahs
  against 72 for Basran.
- **`data-ayah-total` follows the counting system, not the Quran.** 6,236 is
  Kufan; Nāfiʿ counts 6,214. Any consumer that hardcodes 6,236 will reject a
  correct edition of another riwaya.

### 6.6 On `<g class="surah-name">` and `<g class="basmalah">`

```xml
<g class="surah-name" data-sid="2" data-surah-name-ar="البقرة"
   data-surah-name-latin="Al-Baqarah" data-surah-name-en="The Cow"
   data-revelation-place="madinah" data-ayah-count="286">
```

| attribute | count | example |
|---|---:|---|
| `data-sid` | 226 | `2` |
| `data-surah-name-ar` | 226 | `البقرة` |
| `data-surah-name-latin` | 226 | `Al-Baqarah` |
| `data-surah-name-en` | 226 | `The Cow` |
| `data-revelation-place` | 226 | `makkah` / `madinah` |
| `data-ayah-count` | 226 | `286` |

226 = 114 surah-name groups + 112 basmalah groups; the basmalah group repeats
its surah's metadata. **These attributes appear only on a surah's first page.**
To know the surah of an arbitrary page, read the surah number out of any
`data-wid`, or use the companion `index.json`.

### 6.7 On `<g class="hizb-mark">`

```xml
<g class="hizb-mark" data-mark="hizb" data-aid="2:75"
   data-rub="5" data-rub-in-hizb="1" data-nisf="1" data-hizb="2" data-juz="1">
  <path data-eid="e791" data-kind="mark" data-mark="hizb" data-sig="91526b27f4bc5bb9"
        data-standalone="1" data-aid="2:75" d="…"/></g>
```

| attribute | count | meaning |
|---|---:|---|
| `data-mark` | 199 | always `hizb` |
| `data-aid` | 199 | the ayah the rosette stands before |
| `data-rub` | 199 | rubʿ number, 1..240 |
| `data-rub-in-hizb` | 199 | 1..4 |
| `data-nisf` | 199 | half of the hizb, 1 or 2 |
| `data-hizb` | 199 | 1..60 |
| `data-juz` | 199 | 1..30 |

The `*-start` attributes are **not** here — they are on `<g class="ayah">`
(§6.2), because 41 boundaries have no rosette.

---

## 7. An ayah is not a subtree — read this before selecting one

**The single most common mistake with this format.** An ayah is emitted once
per printed LINE it occupies, so it is several sibling nodes and there is no
single node that "is" the ayah. 6,236 ayahs are emitted as 13,489
`<g class="ayah">` fragments; **4,455 ayahs have more than one**. The record is
2:282 on p48, which fills all 15 lines of its page and so has 15 fragments
(pages 17 and 144 go higher for a different reason — §10.5).

Every fragment says so, and the fragments are linked to the medallion:

```xml
<!-- page 3, line 1 -->
<g class="ayah" data-aid="2:6" data-marker="mk-2-6" data-part="1" data-ayah-parts="2">…</g>
<!-- page 3, line 2 -->
<g class="ayah" data-aid="2:6" data-marker="mk-2-6" data-part="2" data-ayah-parts="2">…</g>

<!-- page 3, in #ayah_markers -->
<g class="ayah-marker" id="mk-2-6" data-aid="2:6">…</g>
```

Verified corpus-wide: **all 13,489 fragments carry `data-marker`, every one
resolves to a marker `id` on the same page, and every ayah's `data-part` values
are exactly `1..data-ayah-parts` in document order.**

```js
// ---- select the WHOLE ayah (all its fragments, all its words) ----
const frags = doc.querySelectorAll('g.ayah[data-aid="2:6"]');       // 2 nodes
const words = doc.querySelectorAll('g.ayah[data-aid="2:6"] g.word'); // all its words
// frags[0].dataset.ayahParts === "2"   -> and you got 2, so the ayah is complete

// ---- from an ayah, find its medallion ----
const medallion = doc.getElementById(frags[0].dataset.marker);      // <g id="mk-2-6">

// ---- from a medallion, find its ayah ----
const back = doc.querySelectorAll(`g.ayah[data-marker="${medallion.id}"]`);

// ---- from a word, find everything ----
const w = doc.querySelector('g.word[data-wid="2:6:3"]');
w.closest('g.ayah').dataset.aid;      // "2:6"
w.closest('g.line').dataset.line;     // "1"
doc.getElementById(w.closest('g.ayah').dataset.marker);   // its medallion
```

**Do not** use `firstElementChild` / `lastElementChild` of one fragment to find
the ayah's first or last word — use `data-wid` order across all fragments. **Do
not** assume `querySelector` (singular) on `g.ayah[data-aid=…]` gives you the
ayah; it gives you fragment 1 of N.

`data-ayah-parts` is also your completeness check: since **no ayah spans two
pages** (§11), if you loaded the right page you will always find all N.

> **Version note.** Before 2026-08-30 the medallions carried the wrong ayah
> label: 5,881 of 6,236 markers on 598 pages were mislabelled, effectively
> reversed down the page. They are now bound by position and correct. If you
> have an older bundle, the marker labels are not usable — check for `id="mk-…"`
> on `<g class="ayah-marker">`; the fix and the link landed together.

---

## 8. The mark taxonomy — 35 emitted names

The registry is `.cache/schema/mark-taxonomy.v2.json` (schema `mark-taxonomy`,
version 2.0). It declares **36** names: **35 active**, 1 reserved-inactive
(`waqf-mamnu`, §8.6). Of the 35 active, **34 are actually emitted**; `pause` is
a legacy fallback name with **0** occurrences. `tools/audit_taxonomy.py` gates
this and reports `35 mark names`, counting the registry's active set.

Two further names appear only as **group-level** `data-mark`, never on a path:
`sajdah` (17 groups) and `hizb` — `hizb` is also a path name (199).

Codepoints below are what appears in `data-uthmani`. `family` is what the
registry declares as `data-mark-family`; `category` is the registry's grouping.

### 8.1 Harakat (vowels and their companions) — category `haraka`

| `data-mark` | Arabic | codepoint | family | count |
|---|---|---|---|---:|
| `fatha` | فتحة | U+064E `َ` | — | 123,054 |
| `kasra` | كسرة | U+0650 `ِ` | — | 46,069 |
| `damma` | ضمة | U+064F `ُ` | — | 37,454 |
| `sukun` | سكون | U+0652 `ْ`, U+06E1 `ۡ` | — | 37,148 |
| `shadda` | شدة | U+0651 `ّ` | — | 22,678 |

### 8.2 Tanween — `data-mark-family~="tanween"`, `data-form` on all but 48

| `data-mark` | Arabic | codepoint | count |
|---|---|---|---:|
| `fathatan` | تنوين فتح | U+064B `ً`, **U+08F0 `ࣰ`** | 3,635 |
| `kasratan` | تنوين كسر | U+064D `ٍ`, **U+08F2 `ࣲ`** | 2,534 |
| `dammatan` | تنوين ضم | U+064C `ٌ`, **U+08F1 `ࣱ`** | 2,385 |

### 8.3 Letter dots — `data-mark-family="dots"`

| `data-mark` | count | notes |
|---|---:|---|
| `dot` | 63,611 | one dot |
| `two-dots` | 38,120 | drawn as one path |
| `three-dots` | 3,538 | drawn as one path |

Dots are the letters' own dots (nuqaṭ), not diacritics — but in this schema
they are `data-kind="mark"`. A hamza seat (`ئ ؤ أ إ`) is drawn **without** the
dots of its base letter.

### 8.4 Orthographic signs — category `orthographic`

| `data-mark` | Arabic | codepoint | count | notes |
|---|---|---|---:|---|
| `hamza` | همزة | U+0621 `ء` and the seats U+0623/0625/0624/0626, U+0654/0655 | 16,388 | **Identical ink to a letter-hamza** — §8.7 |
| `wasla` | همزة وصل | U+0671 `ٱ` | 13,483 | |
| `small-alef` | ألف خنجرية | U+0670 `ٰ` | 9,726 | |
| `maddah` | مدة | U+0653 `ٓ`, U+06E4 `ۤ` | 5,376 | |
| `small-waw` | واو صغيرة | U+06E5 `ۥ` | 1,257 | pronominal suffix — §9.10 |
| `small-ya` | ياء صغيرة | U+06E6 `ۦ`, U+06E7 `ۧ` | 995 | pronominal suffix — §9.10 |
| `small-noon` | نون صغيرة | U+06E8 `ۨ` | **1** | 21:88 only — §9.1. **The only orthographic sign with no family** |

### 8.5 Dabt (recitation-aid signs) — category `dabt`

| `data-mark` | Arabic | codepoint | family | count | notes |
|---|---|---|---|---:|---|
| `sifr-mustadir` | صفر مستدير | U+06DF `۟` | `sifr` | 3,988 | round zero: the letter is **not** pronounced, ever |
| `sifr-mustatil` | صفر مستطيل | U+06E0 `۠` | `sifr` | 66 | upright zero: not pronounced in waṣl, pronounced in waqf. **A different sign with different rules** |
| `meem-iqlab` | ميم الإقلاب | U+06E2 `ۢ` (high) ×510, U+06ED `ۭ` (low) ×99 | — | 609 | §9.7 |

### 8.6 Waqf (pause) signs — `data-mark-family="waqf"`

Verified empirically by pairing each word's waqf codepoint with its emitted
mark name over all 604 pages.

| `data-mark` | codepoint | conventional name | count |
|---|---|---|---:|
| `waqf-jaiz` | U+06DA `ۚ` | جائز — pausing permitted | 2,083 |
| `wasl-awla` | U+06D6 `ۖ` | صلى — continuing is better | 1,651 |
| `waqf-awla` | U+06D7 `ۗ` | قلى — pausing is better | 511 |
| `waqf-lazim` | U+06D8 `ۘ` | لازم — pause obligatory | 21 |
| `muanaqah` | U+06DB `ۛ` | معانقة — stop at one of a pair | 6 |

**The names are the ACTION, not the letters of the sign.** U+06D6 (ۖ, "ṣalā")
is emitted as `wasl-awla`, and U+06D7 (ۗ, "qilā") as `waqf-awla`. Map by this
table, not by the sign's Arabic abbreviation. The registry's `aliases` block
records the older names (`waqf qila` → `waqf-jaiz`, `waqf sali` → `wasl-awla`,
`waqf taanuq` → `muanaqah`, `sajdah` → `sajdah-sign`).

**U+06D9 `ۙ` (لا, "do not stop") does not occur in this print** — zero
occurrences in the text, zero marks. `waqf-mamnu` is the one registry entry
with `active: false`.

### 8.7 Reading signs — `data-mark-family="reading-sign"`

Each occurs at a handful of sites, named **by site, not by shape** (§9.1).

| `data-mark` | Arabic | codepoint | count |
|---|---|---|---:|
| `saktah` | سكتة | U+06DC `ۜ` | 5 |
| `seen-reading` | سين القراءة | U+06DC `ۜ`, U+06E3 `ۣ` | 3 |
| `imalah` | إمالة | U+06EA `۪` | 1 |
| `ishmam` | إشمام | U+06EC `۬` | 1 |
| `tashil` | تسهيل | U+06EC `۬` | 1 |

### 8.8 Standalone signs — `data-standalone="1"`, category `standalone`

| `data-mark` | Arabic | family | count |
|---|---|---|---:|
| `sajdah-sign` | ۩ | `sajdah` | 15 |
| `sajdah-line` | the overline | `sajdah` | 15 |
| `hizb` | ۞ | — | 199 |

---

## 9. Things a drawing cannot tell you, and special cases

Every one is verified in a real page. Page numbers and `data-wid` keys are
exact.

### 9.0 Five properties of the script, not quirks of the file

**(a) `fatha` and `kasra` are the SAME STROKE, named by position.** So are
`fathatan`/`kasratan` and `damma`/`dammatan`. The name comes from where the
stroke sits relative to the word's letters and from the word's spelling —
nothing in the outline distinguishes them. Two consequences: a mis-owned mark
always arrives wearing the **opposite** name (a stolen fatha hangs below its new
holder's letters and is therefore called `kasra`), and you cannot infer a name
from a `data-sig` — 85 signatures serve both `fatha` and `kasra`.

**(b) `hamza` and a letter-hamza are IDENTICAL ink.** `data-mark="hamza"` is a
diacritic; a hamza that is a *letter* of the word is `data-kind="body"`. The ink
is the same; only the spelling decides. Counting `[data-mark="hamza"]` counts
diacritic hamzas only — usually what you want, but not "all hamzas drawn".

At two sites the print draws the hamza **fused to its alif as one contour**
(p324 `21:28:4` and p341 `22:76:4`, both `أَيْدِيهِمْ`). The ruling: name it
`hamza`, never cut it. Consequence — the `<g class="ligature" data-text="ا">`
there holds **no `data-kind="body"` path at all**:

```xml
<g class="word" data-wid="21:28:4" data-uthmani="أَيْدِيهِمْ" data-rasm="أيديهم"
   data-imlaei="أَيْدِيهِمْ" data-search="أيديهم" data-qpc="أَيۡدِيهِمۡ">
 <g class="ligature" data-text="ا">
  <path data-eid="…" data-kind="mark" data-mark="hamza" data-sig="f2c96fa4a4a90766" d="…"/>
  <path data-eid="…" data-kind="mark" data-mark="fatha" data-sig="d7a8b5e19121fbe4" d="…"/></g>
```

**(c) Composite marks: one outline, two marks.** One drawn outline can carry two
marks (`fatha+hamza`, `damma+shadda`). These are resolved internally and **no
`+`-compound name survives into the emitted files** — verified, zero
occurrences.

**(d) Path count ≠ sign count.** Two slash strokes drawn touching share one
path, so the pair counts once. A sign whose contours the artwork put in
different paths emits as more than one path — exactly one such case survives
(`data-mark-part`, p146; §10.5). And muʿānaqah is ONE sign of three dots that
comes in **pairs** across two words: three pairs mushaf-wide = 6 emitted
`muanaqah` paths. **Do not count six signs, and do not count three dots per
sign.**

**(e) A `data-sig` is not an identity.** It is the outline's shape. **98 of the
2,152 signatures in the corpus serve more than one mark name.** The worst is
`d2506e4f8b4e28e5` — a plain circle — which is `dot` 63,233 times, `two-dots`
498 times, `three-dots` 38 times and `muanaqah` 3 times. Conversely one name has
many: `fatha` has 131 signatures, `meem-iqlab` 15. **A consumer should not use
`data-sig`.**

### 9.1 Once-in-the-mushaf signs — and one character meaning two things

| sign | `data-mark` | sites |
|---|---|---|
| saktah | `saktah` | p293 `18:1:11` عِوَجَاۜ · p443 `36:52:6` مَّرْقَدِنَاۜۗ · p567 `69:28:4` مَالِيَهْۜ · p578 `75:27:2` مَنْۜ · p588 `83:14:2` بَلْۜ |
| seen-for-sad | `seen-reading` | p39 `2:245:14` وَيَبْصُۜطُ · p159 `7:69:22` بَصْۜطَةࣰۖ · p525 `52:37:7` ٱلْمُصَۣيْطِرُونَ |
| imalah | `imalah` | p226 `11:41:6` مَجْر۪ىٰهَا |
| ishmam | `ishmam` | p236 `12:11:6` تَأْمَ۬نَّا |
| tashil | `tashil` | p481 `41:44:9` ءَا۬عْجَمِىࣱّ |
| small noon | `small-noon` | p329 `21:88:7` نُـۨجِى |

**U+06DC is a `saktah` at five sites and a `seen-reading` at two.** **U+06EC is
`ishmam` at 12:11 and `tashil` at 41:44.** Same character, two names, same
drawing. **Never map a codepoint to a mark name from a Unicode table.** Trust
`data-mark`, or key on (surah, ayah).

At 52:37 `data-uthmani` writes U+06E3 (seen below) but `data-qpc` writes U+06DC
— so `data-qpc` has eight U+06DC sites, not seven.

```xml
<g class="word" data-wid="21:88:7" data-uthmani="نُـۨجِى" data-rasm="نجى"
   data-imlaei="نُنجِي" data-search="ننجي" data-qpc="نُـۨجِي">
```

### 9.2 Pages 1 and 2 are the opening spread

Different `viewBox`, different page matrix, **8 lines instead of 15**, per-line
translates, and the medallion scale is `0.0075` instead of `0.011`. They also
carry **12 `<g class="ayah-marker">` groups with no `id`, no `data-aid` and no
numeral** — the decorative rosettes of the frame (7 on p1, 5 on p2). So
`querySelectorAll('.ayah-marker')` returns 14 on a 7-ayah page.

```js
// only the real medallions
doc.querySelectorAll('g.ayah-marker[data-aid]');
```

### 9.3 Muʿānaqah — one sign, three dots, in pairs

`data-pair` links the two halves. Exactly 6 paths, 3 pairs, in the corpus.

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
| `mnq-2-2-1` | 2 | `2:2:4` رَيْبَۛ ↔ `2:2:5` فِيهِۛ |
| `mnq-5-26-1` | 112 | `5:26:4` عَلَيْهِمْۛ ↔ `5:26:6` سَنَةࣰۛ (two words apart) |
| `mnq-5-41-1` | 114 | `5:41:16` قُلُوبُهُمْۛ ↔ `5:41:19` هَادُوا۟ۛ (three words apart) |

The partners are **not adjacent**. Join on `data-pair`, never on proximity, and
never on the drawing — three of the six share the plain-`dot` signature (§9.0e).

### 9.4 Word tokens containing a SPACE

One word in the whole corpus has a space in its own text: p451
`data-wid="37:130:3"`.

```xml
<g class="word" data-wid="37:130:3" data-uthmani="إِلْ يَاسِينَ" data-rasm="إل ياسين"
   data-imlaei="إِلْ يَاسِينَ" data-search="إل ياسين" data-qpc="إِلۡ يَاسِينَ">
  <g class="ligature" data-text="ا">…</g>
  <g class="ligature" data-text="ل">…</g>
  <g class="ligature" data-text="يا">…</g>
  <g class="ligature" data-text="سين">…</g></g>
```

The space breaks the Arabic join, so it draws four runs — but **no attribute
says where the word break falls**; concatenating the four `data-text` values
gives `الياسين`.

Space census over all 604 pages:

| attribute | tokens containing a space | what the spaces are |
|---|---:|---|
| `data-uthmani` | **1** | this word |
| `data-rasm` | **1** | this word |
| `data-qpc` | 209 | 199 the `۞ ` prefix, 9 a spaced trailing waqf sign, 1 this word |
| `data-search` | **367** | 348 the imlaei vocative convention (`يَٰٓأَيُّهَا` → `يا أيها`, `يَٰبَنِىٓ` → `يا بني`); 19 others — `ويا قوم`, `ها أنتم`, `سواء السبيل` (60:1:48), `نذير مبين` (71:2:6), `وأن لو` (72:16:1), and this word |
| `data-imlaei` | 4,933 | the same convention plus detached waqf signs (`رَيْبَ ۛ`) |
| `data-text` (ligature) | 0 | |

**Never tokenise a page by splitting text on whitespace.** `data-wid` is the
only word key — one printed word can be two words in the modern spelling
(`سواء السبيل`, `نذير مبين`) and it is still one `<g class="word">`. It also
means a naive `data-search === query` fails for `يا أيها`; match on a
normalised, space-stripped form if you want them to join. Related: `بَعْدَ مَا` (2:181 p27, 8:6 p177, 13:37 p254) is **two words** in this
print's segmentation, not one spaced token.

### 9.5 Sajdah — 15 places, 30 paths, 17 groups

The sign (۩) and the overline belong together and are `data-standalone="1"` —
they are **never** inside a word.

```xml
<!-- p176, complete -->
<g class="sajdah-mark" data-mark="sajdah" data-aid="7:206">
  <path data-eid="e1008" data-kind="mark" data-mark="sajdah-sign" data-mark-family="sajdah"
        data-sig="8097cfaa6e9371be" data-standalone="1" data-aid="7:206" d="…"/>
  <path data-eid="e1009" data-kind="mark" data-mark="sajdah-line" data-mark-family="sajdah"
        data-standalone="1" data-aid="7:206" d="…"/></g>
```

The 15 sites: p176 (7:206), p251 (13:15), p272 (16:50), p293 (17:109), p309
(19:58), p334 (22:18), p341 (22:77), p365 (25:60), p379 (27:24 + 27:26), p416
(32:15), p454 (38:24), p480 (41:37 + 41:38), p528 (53:62), p589 (84:21), p598
(96:19).

**Two sites are split into two groups with different `data-aid`** (p379, p480)
— §10.6. **Count `data-mark="sajdah-sign"` (15), not the groups (17).**

Note the print draws the 96:19 sajdah on **p598**, not p597.

### 9.6 Hizb / rubʿ — 199 rosettes for 240 boundaries

Verified: all 240 rubʿ boundaries carry `data-rub-start` on their ayah (§6.2),
and the 41 with no drawn rosette **all fall on an ayah 1** — a surah start,
where the banner marks the division instead. 41 of 41, no exceptions.

**Use `data-rub-start` / `data-hizb-start` / `data-juz-start` for divisions, and
`g.hizb-mark` only when you want the drawn rosette.**

The rubʿ character U+06DE `۞` **is in the word text but never in the word's
ink**: 199 words carry it in `data-uthmani` / `data-qpc` / `data-imlaei`, while
the rosette is a standalone path in its own `<g class="hizb-mark">`.

```xml
<g class="word" data-wid="2:26:1" data-uthmani="۞إِنَّ" data-rasm="إن"
   data-imlaei="۞ إِنَّ" data-search="إن" data-qpc="۞ إِنَّ">…</g>
```

**Strip U+06DE before matching word text** — or use `data-search`, which has
already dropped it. Note the space is present in `data-qpc` / `data-imlaei` and
absent in `data-uthmani`.

### 9.7 Iqlab: ONE haraka + a small meem, not tanween + meem

This print writes a single vowel plus a small م. 609 sites: **510 high form
(U+06E2 ۢ) and 99 low form (U+06ED ۭ)**; the low form is often fused into
neighbouring ink.

```xml
<!-- p104, high form -->
<g class="word" data-wid="4:165:9" data-uthmani="حُجَّةُۢ" data-rasm="حجة"
   data-imlaei="حُجَّةٌ" data-search="حجة" data-qpc="حُجَّةُۢ">
  <path data-eid="e404" data-kind="mark" data-mark="damma"      data-iqlab="iq-4-165-9" d="…"/>
  <path data-eid="e405" data-kind="mark" data-mark="meem-iqlab" data-iqlab="iq-4-165-9" d="…"/></g>

<!-- p85, low form -->
<g class="word" data-wid="4:41:6" data-uthmani="أُمَّةِۭ" data-rasm="أمة"
   data-imlaei="أُمَّةٍ" data-search="أمة" data-qpc="أُمَّةِۭ">
  <path data-eid="…" data-kind="mark" data-mark="kasra"      data-iqlab="iq-4-41-6" d="…"/>
  <path data-eid="…" data-kind="mark" data-mark="meem-iqlab" data-iqlab="iq-4-41-6" d="…"/></g>
```

Three consequences:

1. **`data-uthmani` here is deliberately NOT quran.com's `text_uthmani`.** It
   writes `ُ` / `ِ` where quran.com writes `ٌ` / `ٍ`, matching `data-qpc` and the
   ink. `data-imlaei` (and therefore `data-search`) still follows the tanween
   convention. **The attributes disagree on purpose at all 609 sites.**
2. **`data-mark="meem-iqlab"` does not say which form it is.** Take it from the
   word text.
3. `data-iqlab` pairs the haraka with the meem, but only at 335 of 605 sites —
   §10.4.

### 9.8 Open tanween (U+08F0–U+08F2)

`data-uthmani` uses the open forms: U+08F0 `ࣰ` ×2,901, U+08F1 `ࣱ` ×1,807,
U+08F2 `ࣲ` ×1,935 (6,643 total). `data-qpc` uses the QPC forms instead
(`سَنَةٗ` where uthmani has `سَنَةࣰ`); neither open form appears in `data-qpc`.

**These are not mojibake and not a non-standard encoding — they are this
print's orthography.** Normalise to families for comparison; never re-encode the
stored value. If your font lacks U+08F0–U+08F2 you will see tofu; that is a font
problem, not a data problem, and it never affects the drawn page (there is no
`<text>` here at all).

### 9.9 A mark can be drawn outside its word

The tanween of a word-final `ة` floats into the gap toward the next word. p350
`24:2:12`:

```xml
<g class="word" data-wid="24:2:12" data-uthmani="رَأْفَةࣱ" data-rasm="رأفة"
   data-imlaei="رَأْفَةٌ" data-search="رأفة" data-qpc="رَأۡفَةٞ">
  … <path data-eid="e197" data-kind="mark" data-mark="dammatan"
          data-mark-family="diacritic tanween" data-form="staggered" d="…"/></g>
```

**Never assign a mark to a word by nearest ink or by bounding-box
containment.** The `data-wid` of the enclosing group is the answer. This is also
why word bounding boxes overlap, and why §5.4 says to trust document order over
geometry for reading order.

The same holds where a kasratan is drawn **inside the bowl of a ج** — an art
fact of this print.

### 9.10 The pronominal suffix's small waw and small ya

`ـهُۥ` / `ـهِۦ`. These are `data-mark="small-waw"` / `"small-ya"` — **marks, not
letters** — and they sit clear of their own word's ink, always **nearer the next
word**.

```xml
<g class="word" data-wid="16:48:10" data-uthmani="ظِلَٰلُهُۥ" data-rasm="ظلله"
   data-imlaei="ظِلَالُهُ" data-search="ظلاله" data-qpc="ظِلَٰلُهُۥ">
 <g class="ligature" data-text="ظلله">
  … <path data-eid="e536" data-kind="mark" data-mark="small-waw" d="…"/></g></g>
```

`data-rasm` has no waw; `data-imlaei` and `data-search` drop the ۥ entirely.

### 9.11 The silent alef of واو الجماعة

The alef **is** drawn — a `data-kind="body"` path of its own. The round zero that
marks it silent (`sifr-mustadir`, U+06DF) is emitted in the **previous** ligature
group, not on the alef. p11 `2:70:1`:

```xml
<g class="word" data-wid="2:70:1" data-uthmani="قَالُوا۟" data-rasm="قالوا"
   data-imlaei="قَالُوا" data-search="قالوا" data-qpc="قَالُواْ">
 <g class="ligature" data-text="قا">…</g>
 <g class="ligature" data-text="لو">
  <path data-eid="e4" data-kind="body" d="…"/>
  <path data-eid="e5" data-kind="mark" data-mark="damma" d="…"/>
  <path data-eid="e6" data-kind="mark" data-mark="sifr-mustadir" data-mark-family="sifr" d="…"/></g>
 <g class="ligature" data-text="ا"><path data-eid="e7" data-kind="body" d="…"/></g></g>
```

### 9.12 Header ink is not decomposed — and that is deliberate

5,670 paths carry `data-kind="header-ink"`: **2,300 inside
`<g class="surah-name">` and 3,370 inside `<g class="basmalah">`**. **None
carries `data-mark`.** Banner ink is identified, never decomposed. A consumer
iterating words will not see it, and that is correct.

Marks that belong to no word: **229, all of them legitimate**
(`data-standalone="1"`: 199 hizb + 30 sajdah). Verified corpus-wide: **0 named
marks are loose on a text line outside every group.** (Older bundles have 79, on
pages 377, 418, 446 and 507, from the four missing surah banners; check
`document.querySelectorAll('g.surah-name').length === 1` on those pages.)

### 9.13 One calligraphic stroke can be two contours

Where the pen lifts mid-stroke, a single stroke is drawn as two contours
(p203 `9:102:6` صَٰلِحࣰا, p189 `9:20:9`, p219 `10:92:2`). Their boxes *overlap*
end to end; genuinely separate pieces have a positive gap. **Contour count is
not piece count.**

---

## 10. Known limits and defects — stated honestly

### 10.1 There are no `<text>` elements and no letter segmentation

Restated because it is the limit people meet first. See §1 and §10.3.

### 10.2 Reserved

*(Was: "the ayah-marker's `data-aid` is reversed on 441 pages". **Fixed
2026-08-30** — the markers are bound by position and every ayah fragment now
links to its own. See §7.)*

### 10.3 The ligature layer is not a letter segmentation *(dev profile)*

Comparing each word's concatenated `data-text` against its `data-rasm`
(normalising hamza seats, alef forms, `ى`/`ي` and `ة`/`ه`):

| | words |
|---|---:|
| document order reproduces the rasm | 76,702 (99.06%) |
| groups in a different order | 574 |
| groups spell **fewer** letters than the rasm | **156** |
| groups spell more letters than the rasm | **0** |

Examples: p15 `2:98:5` `وملئكته` emits one group `['و']`; p17 `2:110:2`
`ٱلصلوة` emits `['ا','لصلو']` and the `ة` has no group at all. **37 groups hold
zero `body` paths** (two of them legitimately — §9.0b).

**Use `data-uthmani` / `data-rasm` on the word as the text of record.** Treat
`data-text` as a hint about which letters a group's ink covers, never as a
spelling, and never pair group *i* with letter run *i*. This is why the layer is
dropped in the production profile.

### 10.4 `data-iqlab` is incomplete

605 distinct ids over 940 paths. **335 sites** tag both the haraka and the meem;
**270 sites** tag only the meem, so the vowel it belongs with is unfindable.
**Four of the 609 meems carry no `data-iqlab` at all** (p45 `2:265:12`, p446
`37:11:12`, p455 `38:42:4`, p577 `74:51:3`), and p577's is also the only
`meem-iqlab` in the corpus with no `data-sig`.

```js
// safe: pair only when both halves are tagged
const byId = new Map();
for (const p of doc.querySelectorAll('path[data-iqlab]')) {
  const id = p.dataset.iqlab;
  if (!byId.has(id)) byId.set(id, []);
  byId.get(id).push(p);
}
const complete = [...byId.values()].filter(v => v.length === 2);   // haraka + meem
```

### 10.5 Sole survivors of otherwise-uniform rules

A strict consumer must special-case these:

- **1 unnamed mark** — p1 `1:2:1` `ٱلْحَمْدُ`, `data-eid="e34"`:
  `data-kind="mark"` with no `data-mark`.
- **1 `data-mark-part`** — p146 `6:141:14` `مُتَشَٰبِهࣰا`: the ش's third dot
  emits as a second path carrying `data-mark-part="three-dots"` (and
  `data-mark-family="dots"`) instead of `data-mark`. A consumer selecting
  `[data-mark]` misses its ink; one selecting `[data-kind="mark"]` finds a path
  with no name.
- **15 paths of 598,407 have no `data-sig`** (split or synthesised outlines):
  p37, p38, p126 ×2, p146, p159, p342, p362, p431 ×2, p460, p485, p556, p567,
  p577.
- **4 paths on p17 have no `data-kind` at all** — page ornaments outside both
  `#content` and `#ayah_markers`, passed through from the artwork untouched.
  p17 is the only page with them.
- **`small-noon` is the only orthographic sign with no `data-mark-family`.**
  `[data-mark-family~="reading-sign"]` also silently drops it — it is not a
  reading sign in this registry.
- **p7 is the only file declaring `xmlns:xlink`.**
- **p17 and p144 emit one `<g class="ayah">` per WORD**, not per (ayah, line):
  139 and 117 groups. All **216** "reopened" ayah groups in the corpus are on
  these two pages, and their `data-ayah-parts` values run as high as 35. §7's
  contract still holds there (parts are `1..N` and all link to the marker) —
  there are just far more of them than lines.

### 10.6 Two sajdah groups are incomplete

p379 emits the An-Naml sajdah as two sibling `sajdah-mark` groups, one holding
only the line (`data-aid="27:24"`) and one only the sign (`data-aid="27:26"`).
p480 does the same with `41:37` / `41:38`. Neither `data-aid` on those four
groups is reliably the sajdah ayah.

### 10.7 Element order inside a word is not right-to-left

Only 15,102 of 77,432 words (19.5%) have their paths in descending x. Word order
within a line is correct (§5.4); path order within a word is not normalised.
Sort by geometry if you need it.

### 10.8 Words split differently from other decompositions

About 9 word-level segmentation disagreements with MushafDatabase remain
(p11, p262 `لَّوۡمَا`, p451). Word boundaries otherwise agree on **77,417 of
77,422** words, and line placement on **99.994%**.

### 10.9 The companion index predates `data-search`

`tools/build_bundle.py` builds `words.json` with
`fields: ["wid","page","rasm","imlaei"]` — it has no `data-search` column yet,
and `index.json` still carries the pre-2026-08-30 `basmalah_groups: 113`. **The
SVGs are authoritative**; always read the index's own `fields` array rather than
assuming a column order, and prefer `data-search` from the SVG for search. The
edition manifest `.cache/schema/edition-hafs-kfgqpc.json` is current
(`surah_name_groups_emitted: 114`, `basmalah_groups: 112`).

---

## 11. Recipes

```js
// ---- highlight ayah 2:255 (all its line fragments) ----
doc.querySelectorAll('g.ayah[data-aid="2:255"] g.word')
   .forEach(w => w.querySelectorAll('path')
                  .forEach(p => p.setAttribute('fill', '#0a7')));

// ---- click anywhere on the ink -> word + ayah ----
svg.addEventListener('click', e => {
  const w = e.target.closest('g.word');
  if (w) console.log(w.dataset.wid, w.closest('g.ayah').dataset.aid);
});

// ---- one word ----
doc.querySelector('g.word[data-wid="2:255:3"]');   // there is no id= on words

// ---- an ayah's medallion, and back again ----
const frag = doc.querySelector('g.ayah[data-aid="2:255"]');
const mk   = doc.getElementById(frag.dataset.marker);          // <g id="mk-2-255">
doc.querySelectorAll(`g.ayah[data-marker="${mk.id}"]`);        // all fragments

// ---- is this ayah complete on this page? ----
frag.dataset.ayahParts === String(
  doc.querySelectorAll(`g.ayah[data-aid="2:255"]`).length);    // always true

// ---- the plain text of a printed line ----
[...doc.querySelectorAll('g.line[data-line="7"] g.word')]
  .map(w => w.dataset.uthmani).join(' ');

// ---- search this page ----
const fold = s => s.replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
[...doc.querySelectorAll('g.word')]
  .filter(w => fold(w.dataset.search).includes(fold('الرحمن')))
  .map(w => w.dataset.wid);

// ---- colour the dots differently from the harakat ----
doc.querySelectorAll('path[data-mark-family~="dots"]')
   .forEach(p => p.setAttribute('fill', '#b03030'));
// equivalently, without relying on data-mark-family:
//   'path[data-mark="dot"],path[data-mark="two-dots"],path[data-mark="three-dots"]'

// ---- every waqf sign on the page, with the word it belongs to ----
[...doc.querySelectorAll('path[data-mark-family~="waqf"]')]
  .map(p => [p.closest('g.word')?.dataset.wid, p.dataset.mark]);

// ---- muanaqah partners ----
doc.querySelectorAll(`path[data-pair="${p.dataset.pair}"]`);   // exactly two

// ---- juz / hizb / rub boundaries on this page ----
[...doc.querySelectorAll('g.ayah[data-rub-start]')]
  .map(g => ({aid: g.dataset.aid, rub: +g.dataset.rubStart,
              juz: g.dataset.juzStart, hizb: g.dataset.hizbStart}));

// ---- crop to one ayah ----
// 1. (dev profile) remove path.ayahPolygon first — different frame, sits on top
// 2. drop every g.word whose data-wid is not in the ayah
// 3. drop the now-empty g.ayah / g.line wrappers
// 4. getBBox() on #content, pad, write it back as the viewBox
```

```python
# ---- which page is 2:255 on?  (companion index) ----
idx = json.load(open("index/index.json"))
def num(aid): s, a = aid.split(":"); return (int(s), int(a))
page = next(p["page"] for p in idx["page_index"]
            if num(p["first_ayah"]) <= (2, 255) <= num(p["last_ayah"]))

# ---- where is a word on the page? ----
wb    = json.load(open("index/wordboxes.json"))
cols  = wb["fields"]                      # read the columns, never assume them
boxes = wb["pages"]["42"]
box   = next(b for b in boxes if b[cols.index("wid")] == "2:255:3")
```

---

## 12. Reference facts, all measured

| fact | value |
|---|---|
| pages | 604 (602 with 15 lines, 2 with 8) |
| words / distinct `data-wid` | 77,432 / 77,432 |
| ayahs / `<g class="ayah">` fragments | 6,236 / 13,489 |
| ayahs emitted as >1 fragment on their page | 4,455 |
| **ayahs spanning two pages** | **0** — 6,236 ayahs, 6,236 (page, ayah) pairs. Every page begins and ends on an ayah boundary, so `mk-…` ids are globally unique. |
| lines | 9,046 (8,820 with words, 226 header lines) |
| words in the wrong `<g class="line">` | **0** |
| ink paths (excluding `ayahPolygon`) | 616,565 |
| paths incl. `ayahPolygon`, dev profile | 622,801 |
| named marks | 436,627 |
| letter (`body`) paths | 161,778 |
| `header-ink` paths | 5,670 (2,300 surah-name + 3,370 basmalah) |
| distinct `data-mark` values | 34 on paths (+`sajdah` group-level); registry declares 36, 35 active |
| ayah medallions | 6,248 groups, 6,236 with `id` + `data-aid` |
| surah-name / basmalah groups | 114 / 112 (basmalah absent for surahs 1 and 9) |
| named marks belonging to no word | 229, all `data-standalone="1"` (199 hizb + 30 sajdah) |
| hizb rosettes / rubʿ boundaries | 199 / 240 (all 240 carry `data-rub-start`) |
| sajdah signs / groups | 15 / 17 |
| ligature groups (dev only) | 156,707 |
| `ayahPolygon` paths (dev only) | 6,236 |
| page size, dev — raw / gzip / brotli | 774.2 / 188.3 / 119.1 KiB average |
| page size, production — raw / gzip / brotli | 761.7 / 186.2 / 118.0 KiB average |
| corpus size, dev — raw / gzip / brotli | 456.7 / 111.0 / 70.2 MiB |
| corpus size, production — raw / gzip / brotli | 449.3 / 109.8 / 69.6 MiB |
