# mushaf.js — API reference

Every public function: signature, parameters, what it returns, what it mutates, and a
runnable example. You should not need to read the source.

Working name; see [README](README.md#mushafjs). Licence: **[to be decided — no terms
are stated in this directory].**

**Conventions used throughout**

- **`target`** — anything [`page.resolve()`](#pageresolvetarget) accepts: `'page'`,
  an ayah key `'2:255'`, a word key `'2:255:3'`, `{line: 7}`, `{ayah, wids, surah}`,
  a `Word`, an `Ayah`, a `Line`, an element, or an array of any of those.
- **`form`** — one of `'uthmani' | 'imlaei' | 'qpc' | 'rasm' | 'search'`
  (`TEXT_FORMS`). Default `'uthmani'` for display, `'search'` for searching.
- **Handles.** Every mutating call returns an object with **`.remove()`** that undoes
  exactly what it did and nothing else. There is no global reset.
- **Ownership.** `MushafPage.load()` and `page.clone()` give you a page you own.
  `new MushafPage(el)` wraps an element **without cloning**, so a later mutating call
  changes *your* element.

**Contents** · [Loading](#loading) · [Identity](#identity) ·
[Metadata](#metadata) · [Words, ayahs, lines](#words-ayahs-and-lines) ·
[Text](#text) · [Search](#search) · [Highlighting](#highlighting) ·
[Hit testing](#hit-testing) · [Marks](#marks) · [Theme](#theme) ·
[Ayah markers](#ayah-end-markers) · [Layout](#layout) · [Crop](#crop) ·
[Overlay, hover, tap](#overlay-hover-and-tap) · [Selection](#selection-and-copy) ·
[Memorisation](#memorisation) · [Accessibility](#accessibility) ·
[View](#view) · [Raster](#raster-export) · [Atlas](#atlas-cross-page-lookup) ·
[Arabic text tools](#arabic-text-tools) · [Traps](#traps) · [Testing](#testing)

---

## Loading

### `createLoader(options)`

Returns `async load(n)`. Caches parsed pages and **hands out a clone every time**, so
two callers can never disturb each other.

| option | default | |
|---|---|---|
| `baseUrl` | `'pages/'` | prefixed to the file name |
| `pad`, `ext` | `3`, `'.svg'` | `42` → `pages/042.svg` |
| `name` | – | `n => …` to build the file name yourself |
| `fetch` | `globalThis.fetch` | inject your own |
| `cache` | `true` | |
| `stripPolygons` | `true` | drop the dev-only `path.ayahPolygon` layer (§5.3 of FORMAT: different frame, sits on top, swallows pointer events) |

```js
const load = createLoader({ baseUrl: '/quran/pages/' });
const page = await load(42);
```

### `MushafPage.load(n, options)`

One-shot convenience over `createLoader`. Same options.

### `MushafPage.parse(svgText, options)`

Parse a string. Returns a page you own. Throws on a parse error.

### `new MushafPage(svgElement, {number, stripPolygons})`

Wrap an `<svg>` already in your document. **Does not clone and does not mutate.**

### `page.clone()` → `MushafPage`

Deep copy with every `id` namespaced (and `data-marker` kept in step), so two copies
can live in one document without id collisions.

---

## Identity

### `page.el`
The `<svg>` element.

### `page.number`
The page number, if one was supplied. `null` for a wrapped element.

### `page.profile` → `'dev' | 'production'`
Detected by whether `g.ligature` is present. The files do not announce it.

### `page.viewBox` → `{x, y, w, h}`
**Read off the file.** Never assume `0 0 345 550` — pages 1 and 2 are
`-53.3109 -198.4777 345 550`.

### `page.info()`
Everything at once: profile, viewBox, line and word and ayah counts, surah numbers,
marker count, decorative-rosette count, sajdahs, rosettes, divisions.

### `page.dropPolygons()` → `number`
Remove the dev-only polygon layer. Mutates. The loader does it for you.

### `page.refreshGeometry()`
Invalidate cached boxes and line bands. Call after you move things yourself.

---

## Metadata

*The "no database" story: these read attributes the files already carry.*

### `page.surahs()` → `Surah[]`

`{number, arabic, latin, english, revelationPlace, ayahCount, hasBanner, hasBasmalah}`.

Banner attributes exist **only on a surah's first page**. A surah merely *present* on
the page comes back with `hasBanner: false` and only its `number` — read out of
`data-wid`, so you always get a complete list.

```js
(await load(582)).surahs();
// [{number: 78, arabic: 'النبإ', latin: 'An-Naba', english: 'The Tidings',
//   revelationPlace: 'makkah', ayahCount: 40,
//   hasBanner: true, hasBasmalah: true}]
// On a page that continues a surah, that surah comes back with only its
// number and hasBanner: false — the banner attributes exist nowhere else.
```

### `page.divisions()` → `{juz, hizb, nisf, rub}`

Divisions that **start** on this page: `{n, aid, line}[]`, sorted. All 240 rubʿ
boundaries are tagged even where no rosette is drawn.

```js
(await load(582)).divisions().juz;   // [{n: 30, aid: '78:1', line: 3}]
```

### `page.rosettes()` → the *drawn* `g.hizb-mark`

`{el, aid, rub, rubInHizb, nisf, hizb, juz}[]`. 199 exist for 240 boundaries — use
`divisions()` for the boundaries, this for the drawing.

### `page.sajdahs()` → `{el, sign, aid, line}[]`

Counted by `data-mark="sajdah-sign"`, **not** by group: two sites in the corpus are
split into two groups with unreliable `data-aid`.

### `page.markers()` → `{el, aid, id, ring, numeral}[]`

**Real ayah medallions only.** Pages 1–2 carry 12 decorative rosettes with no
`data-aid`; they are excluded here and by `styleMarkers`.

### `page.allMarkerGroups()` → `Element[]`
Every `.ayah-marker`, decorative rosettes included.

### `page.ayahKeys()` → `string[]`
Ayah keys in reading order, deduplicated.

---

## Words, ayahs and lines

### `page.words(selector)` → `Word[]`
`{line}`, `{ayah}`, `{surah}`, `{wids}` — combinable. No selector: every word.

### `page.word(wid)` → `Word | null`

A **`Word`** has `el`, `wid`, `parts`, `surah`, `ayah`, `index`, `aid`, `line`,
`text` (all five forms), `form(which)`, `paths()`, and `box()`.

### `word.box()` → `{x, y, w, h, x0, y0, x1, y1}`

**In the page's own viewBox units**, through the full transform chain — every
`g.line` has its own frame and the page matrix flips y. Do not use `getBBox()`
yourself; it reports a group's own user space and ignores every transform above it.

### `page.ayah(aid)` → `Ayah | null`

**An ayah is several fragments, one per printed line — see [Traps](#traps).** This
returns *all* of them.

`Ayah` has `aid`, `surah`, `number`, `fragments`, `parts`, `complete`, `markerId`,
`marker`, `lines`, `words()`, `text(form)`.

### `page.ayahs()` → `Ayah[]`

### `page.lines()` / `page.line(n)` / `page.textLines()` / `page.lineNumbers()`

`Line` has `number`, `words()`, `text(form)`, `isHeader` (true for the 226 banner
lines that hold no words), `box()`.

### `page.wordCount`

### `page.resolve(target)` → `Word[]`
The resolver every other method uses. Useful for building your own helpers.

---

## Text

### `page.text(target, {form, wordSep, lineSep})` → `string`

Text of anything, in any form. Line breaks are **the mushaf's own**.

```js
page.text('2:255');                        // the ayah, with its printed line breaks
page.text({line: 7});                      // one printed line
page.text('page', {form: 'search'});       // the whole page, bare
page.text(hits.map(h => h.word));          // whatever you just found
```

Never tokenise the result on whitespace to recover words: one printed word can contain
a space (`إِلْ يَاسِينَ`, and 367 `data-search` values). `data-wid` is the only key.

---

## Search

### `page.search(query, options)` → `Match[]`

`Match` is `{word, wid, value, index}` — the `Word` object, so you can highlight or
scroll to it directly.

| option | default | |
|---|---|---|
| `form` | `'search'` | the diacritic-free key. **Never use `'rasm'` for a search box** — it is the *uthmani* skeleton, so stripping deletes long vowels written as combining marks |
| `mode` | `'includes'` | `'exact'`, `'prefix'`, `'regex'` |
| `normalize` | `true` | apply [`normalizeQuery`](#normalizequerys) to both sides |
| `loose` | `true` | if the strict pass found **nothing**, retry with [`looseKey`](#loosekeys). Never widens a query that already matched |
| `limit` | `Infinity` | |

```js
page.search('الله', {mode: 'exact'}).map(m => m.wid);
// p42 → ['2:253:10','2:253:24','2:253:45','2:253:49','2:255:1']

(await load(1)).search('الرحمان', {mode: 'exact'}).map(m => m.wid);
// ['1:1:3','1:3:1'] — the printed word is الرحمن with a dagger alef, which is
// not in data-search at all. The loose pass is what makes this work.

page.highlight(page.search('الله').map(m => m.word), {fill: '#c0392b'});
```

---

## Highlighting

### `page.band(target, options)` → handle

**ONE `<path>`** covering every printed line the target occupies — not one rectangle
per line. Mutates the page.

| option | default | |
|---|---|---|
| `padX` | `1.2` | viewBox units, horizontal only |
| `fill`, `opacity` | `'#d6a326'`, `0.30` | |
| `height` | `'pitch'` | `'ink'` to use the words' own heights plus `padY` |
| `padY` | `0` | only with `height: 'ink'` |
| `seam` | `0.25` | vertical overlap between neighbouring lines, in viewBox units |
| `className` | `'mushaf-band'` | |

Handle: **`{el, path, d, bands, boxes, seam, remove()}`**. `el` is the group (it carries
the `opacity` and `pointer-events: none`); `path` is the single `<path>`; `boxes` is
`{line, x0, x1, y0, y1}[]` in viewBox units, **before** the seam overlap is applied.

> **Changed.** This used to return `rects` — an array of `<rect>` elements, one per
> line. It now returns `path` and `d`. `rects` is gone.

Why one path:

- A stack of separate rects shows an **antialiasing hairline at every join** — two
  abutting antialiased edges do not add up to opaque — so a six-line ayah reads as six
  stripes rather than one highlight.
- Each line is a **subpath**, all wound the same direction, and the path declares
  **`fill-rule="nonzero"`**, which *unions* them. That is what lets neighbouring
  subpaths overlap by `seam` to kill the hairline without the overlap painting twice
  and darkening.
- **`fill-rule` is set explicitly on the element and must stay that way.** The page's
  own ink is `evenodd`, where overlapping contours inside one path *cancel*; inheriting
  it would turn every overlap into a hole — the same trap that once filled the counter
  of a ح as a solid blob. There is a test asserting the attribute is present, because
  this is the regression most likely to be reintroduced by tidying.
- The seam overlap is applied **only where two bands actually meet**, so a highlight on
  lines 3 and 9 does not grow tails into the untouched lines between them.

Horizontal extent still comes from the words' **ink**, so a band never overhangs the
text at a line end; vertical extent still comes from the **line pitch**. The group is
the first child of `<svg>` — behind the ink, and unable to eat a click.

```js
const b = page.band('2:255', {fill: '#d6a326'});
b.bands;                            // 6 on page 42 — six printed lines (8-13)
b.el.children.length;               // 1
b.path.getAttribute('fill-rule');   // 'nonzero'
b.remove();
```

Every band the library draws goes through this one method — ayah highlight, word
highlight and the selection band alike.

### `page.highlight(target, {className, fill, opacity})` → handle

Recolours the ink itself. `remove()` restores the exact previous inline values.

### `page.highlightAyah(aid, options)` → handle

Band plus an ink class, the common case. `{band, ink, bands, remove()}`. Pass
`{ink: false}` for band only, or `{band: {...}, ink: {...}}` to configure each.

### `page.clearBands(className?)` → `number`
Remove every band this library drew.

### `page.lineBands()` → `Map<lineNumber, {y0, y1, mid, inkY0, inkY1}>`
The pitch-derived vertical band of each printed line, in viewBox units. Cached.

---

## Hit testing

### `page.hitTest(x, y, options)` → `{word, wid, aid, line, distance, exact} | null`

**Pure geometry — no DOM, no overlay.** The opt-out path.

| option | default | |
|---|---|---|
| `space` | `'client'` | `'view'` for viewBox units |
| `maxDistance` | `Infinity` | refuse a hit further than this (viewBox units) |
| `gapBias` | `0.6` | share of a gap awarded to the **preceding** word |

**Nearest with direction, not naive nearest.** The point is resolved to a printed line
by its band, then to a word on that line; a point in the gap between two words is
biased toward the *preceding* (right-hand) word, because in this print a word's
trailing ink — the tanween of a final `ة`, the small waw of a pronominal suffix — is
drawn *into* the following gap. Naive nearest gets those gaps wrong systematically,
always in the same direction. `distance` is measured to the chosen word's own box.

### `page.enableHitTargets({halo})` → handle

Widen the tap target **without changing a pixel**: a transparent stroke behind the fill
is still hit-tested. `halo` is in viewBox units, default `1.6`.

### `page.onTap(handler, options)` → handle

One delegated listener giving you the word the user *meant*, gaps included.
`{level: 'word'|'ayah', event: 'click', halo, maxDistance, gapBias, root}`.
Listens on the page's container, so it works whether the ink or the shared hit layer
owns pointer events.

```js
page.onTap(({wid, aid, exact}) => console.log(wid, aid, exact));
```

If you are already using the hit layer, prefer [`onWordClick`](#onwordclickpage-handler-options)
— same answer, one fewer listener.

---

## Marks

Families and categories are resolved through an **embedded copy of the taxonomy
registry**, to `data-mark` names — never through the `data-mark-family` attribute,
which does not match `FORMAT.md` in the current build (see [Traps](#traps)).

### `page.marks(selector)` → `Element[]`
`{name, family, category, wid, ayah, line}`. `name` may be a string or an array.

Families: `dots`, `waqf`, `tanween`, `sifr`, `sajdah`, `reading-sign`, plus the
convenience aliases `diacritic` (harakat + tanween + maddah — what the files
themselves write), `haraka` and `vowels`.
Categories: `haraka`, `tanween`, `letter-dot`, `orthographic`, `dabt`,
`reading-sign`, `waqf`, `standalone`.

### `page.styleMarks(selectorOrPaths, style)` → handle
CSS properties as an object. `remove()` restores the previous inline style.

### `page.hideMarks(selector)` → handle

```js
page.hideMarks({family: 'diacritic'});   // vowels gone; dots and waqf signs untouched
page.styleMarks({family: 'dots'}, {fill: '#b03030'});
page.marks({name: 'meem-iqlab'});        // the iqlab meems ON THIS PAGE
                                         // (3 on page 42; 609 corpus-wide)
```

### `markNames({family, category, name})` · `familyOf(name)` · `categoryOf(name)` · `MARK_REGISTRY`

---

## Theme

### `page.theme(colours)` → handle

`{paper, ink, diacritics, dots, waqf, sifr, marker, numeral, marks: {name: colour}}`.

Every ink path in the mushaf ships as `fill="#231f20"`, so one rule reaches all of
them. Injects a scoped `<style>` inside the `<svg>`; **`paper` becomes a background
`<rect>` sized to the viewBox**, so the theme survives cropping and raster export
instead of living on a container the export cannot see.

```js
page.theme({paper: '#0d1b2a', ink: '#cfe3ff', diacritics: '#7fb0e8'});
```

---

## Ayah end-markers

### `page.styleMarkers(options)` → handle

| option | |
|---|---|
| `ring` | colour of the ornament ring |
| `numeral` | colour of the printed numeral, independently |
| `scale` | scales the whole medallion about its centre |
| `hide` | `true` for a reading view with no markers |
| `replaceRing` | `true` for a plain circle, or `fn({x,y,w,h,cx,cy,r}, marker) → Element` for your own shape, **keeping the printed numeral** |

Only real markers (`g.ayah-marker[data-aid]`) are touched; the 12 decorative rosettes
on pages 1–2 are left alone.

### `page.hideMarkers()` → handle

---

## Layout

### `setLineGap(page, gap, {pad, carryMarkers})` → handle

Moves each `g.line` apart and grows the viewBox so nothing is cropped. Every printed
line is its own group, so nothing is scaled or re-set and no glyph is touched.
Medallions live outside the lines and are carried with their ayah's **last** fragment.
Handle carries `{gap, viewBox, lines, remove()}` and restores the transforms and the
viewBox exactly.

### `gapToFill({pageW, pageH, lines, viewW, viewH, max})` → `number`

**Pure arithmetic, no DOM.** The leading that makes the page fill a viewport:

```
needed = pageW · viewH / viewW          gap = (needed − pageH) / (lines − 1)
```

**Clamped at zero**: a viewport already wider-for-its-height than the page needs no
leading, and a negative one would overlap lines.

| device | | wasted fitting to width | gap |
|---|---|---|---|
| iPhone SE | 375×667 | 10.4% | 4.5 |
| iPhone 14 | 390×844 | 26.3% | 14.0 |
| Pixel 7 | 412×915 | 28.2% | 15.4 |
| Galaxy S21 | 360×800 | 28.3% | 15.5 |
| iPad 10.9 portrait | 820×1180 | fits by height | 0 |

### `wastedFraction({pageW, pageH, viewW, viewH})` → `0..1`

### `fitToViewport(page, options)` → handle

Measures, solves, applies. **The line count and the viewBox come off the file**, so
this is correct on pages 1–2 (8 lines, their own box) too.

| option | default | |
|---|---|---|
| `element` | – | measure this element |
| `width`, `height` | – | or give the numbers |
| *(neither)* | | the window |
| `maxGap` | `Infinity` | |
| `observe` | `false` | keep filling through a rotation with a `ResizeObserver`. **Opt-in, and `remove()` disconnects it.** |

```js
const fit = fitToViewport(page, {element: stage, observe: true});
fit.state;   // {gap: 14.0, lines: 15, viewport: {...}, wasted: 0.263, viewBox: '…'}
fit.remove();
```

Two methods and not one with a mode: `setLineGap` is a setter, `fitToViewport` is a
solver that computes a number and calls the setter.

---

## Crop

### `page.crop(target, {pad, keepMarkers, background})` → `{el, page, viewBox, words, toString(), toDataUrl()} | null`

A standalone SVG around anything, usable as an image anywhere. **Does not touch the
original page** — it clones. A medallion is kept only when the *whole* ayah survived,
otherwise a one-word crop frames itself around a marker at the far end of the ayah.

```js
const c = page.crop('2:255');            // one ayah
page.crop('2:255:1');                    // one word
page.crop({line: 4});                    // one printed line
img.src = c.toDataUrl();
```

### `page.refit(pad)` → `string`
Refit the viewBox around whatever the page now contains. Mutates.

---

## Overlay, hover and tap

See [the layer model](README.md#the-layer-model--read-this-before-combining-features).

### `acquireHitLayer(page, {mount, form, pad})` → handle

The shared per-word hit layer, built on first call. **Reference counted — every caller
must `release()` exactly once**, and the layer is torn down when the last one does.
The page must be mounted in the document.

Handle: `layer`, `stage`, `count`, `refs`, `form`, `setForm(f)`, `spans()`,
`spanOf(wid)`, `widOf(node)`, `rebuild()`, `onRebuild(fn) → off`,
`wordAt(clientX, clientY, opts)`, `release()`.

Each span carries `data-wid`, `data-line`, `data-aid` and `data-ink`
(`"x y w h"` of the word's **ink** box, relative to the layer — for drawing).
The span's own geometry is the **hit** box.

### `hasHitLayer(page)` → `boolean`

### `onWordHover(page, handler, options)` → handle

Fires **once per word entered**. `{level: 'word'|'ayah', maxDistance, gapBias, onLeave}`
plus any `acquireHitLayer` option.

```js
const h = onWordHover(page, ({word}) => tip.textContent = word.text.uthmani);
h.remove();     // releases its reference to the layer; other consumers keep theirs
```

### `onWordClick(page, handler, options)` → handle
Same, on `click` (or any `event` you name). Gap-aware.

### `wordAt(page, clientX, clientY, options)`
One-shot query; acquires and releases the layer around the call.

---

## Selection and copy

### `attachSelection(page, options)` → handle

Adds drag-select, Ctrl+C / right-click-Copy of real Quranic text, and a painted band —
on top of the shared hit layer. The page must be mounted.

| option | default | |
|---|---|---|
| `mount` | the svg's parent | the positioned container |
| `form` | `'uthmani'` | what the spans carry **and** what Ctrl+C copies |
| `citation` | `false` | `true` → `"…text… (2:255)"`; or `fn(words, text, aids) → string` |
| `onSelect` | – | `({text, words, aids})` on every change |
| `copy` | `true` | install the `copy` handler |
| `paintBand` | `true` | draw the selection band |
| `bandFill`, `bandOpacity`, `bandPadX` | `'#2d6fd6'`, `0.25`, `0.6` | |

Handle: `layer`, `hitLayer`, `form`, `setForm(f)`, `setCopyForm(f)`, `count`,
`rebuild()`, `spans()`, `words()`, `text(form)`, `payload(form)`,
`selectWords(wids)`, `clear()`, `band`, `repaint()`, `detach()`.

```js
const sel = attachSelection(page, {citation: true, onSelect: s => ui.show(s.text)});
sel.text('search');    // the SAME drag, as the bare form, for a search box
sel.payload();         // "…text… (2:255)" — only the selection knows the ayahs
sel.detach();
```

The layer also emits a bubbling **`mushaf:copy`** event with `{detail: {text}}`.

**Selection is whole-word, always.** The range is snapped out before anything reads
it, so the painted band, the copied text and any ayah logic derive from one word list
and cannot disagree; native `::selection` is suppressed so a partial-word range cannot
even be painted. The band is drawn through [`page.band`](#pagebandtarget-options), so a
multi-line selection is **one path**, seams and all handled there. Sub-word selection would be a separate opt-in mode; it does not
exist today.

---

## Memorisation

### `mask(page, target, options)` → handle

Hide or mask an arbitrary set of words and reveal them progressively.

| option | default | |
|---|---|---|
| `mode` | `'hide'` | `'block'` (opaque rect), `'blur'` (SVG filter) |
| `color`, `blur`, `rx`, `padX`, `padY` | | for `block` / `blur` |
| `order` | `'reading'` | `'reverse'` |

Handle: `words`, `hidden`, `hiddenCount`, `revealedCount`, `reveal(n)`, `revealNext()`,
`hide(n)`, `revealWord(wid)`, `revealAll()`, `hideAll()`, `remove()`.

```js
const m = mask(page, '2:255');
m.revealNext();          // one word at a time, in reading order
m.remove();
```

`'hide'` uses `visibility: hidden`, so the printed page keeps its shape and spacing —
which is the point.

### `maskFrom(page, wid, options)` → handle
Mask everything from a word onward.

---

## Accessibility

### `annotate(page, options)` → handle

An SVG of paths is silent to a screen reader. Adds `role` + `aria-label` on the
`<svg>`, a `<title>` and label per word, a label per ayah fragment (saying which part
of how many), and names the surah-name and basmalah banners.

`{form, level: 'word'|'ayah'|'both', label, lang, deferToTextLayer}`.

**`deferToTextLayer: true`** instead marks the SVG `aria-hidden` — use it when a
selection layer is attached, because that layer is real DOM text in reading order and
is the better surface; this prevents the page being announced twice.

Honest limit: a `<title>` is announced on focus or hover, not read as flowing prose.

---

## View

### `scrollIntoView(page, target, options)` → `{box, container} | null`

`{container, behavior, block: 'center'|'start'|'end'|'nearest', inline, margin}`.
Finds the scroll parent itself if you do not name one. Exists because the coordinate
work is what callers get wrong — scrolling to `getBBox().y` sends you to the wrong end
of the page.

---

## Raster export

The pages reference nothing external — every path is inline, one colour, no fonts, no
images — so the canvas is never tainted.

### `toPngDataUrl(src, {scale, background, width})` → `Promise<string>`
### `toPngBlob(src, options)` → `Promise<Blob>`
### `toCanvas(src, options)` → `Promise<HTMLCanvasElement>`
### `toSvgDataUrl(src, {background})` → `string`
No canvas, no rasterising, and it scales.

`src` is a `MushafPage`, a `crop()` result, or an `<svg>`. `scale` defaults to `4`;
`width` overrides it. Give a `background` unless you want transparent paper.

```js
img.src = await toPngDataUrl(page.crop('2:255'), {scale: 4, background: '#fbf9f4'});
```

---

## Atlas (cross-page lookup)

A single page file cannot answer "which page is 2:255 on". **Nothing in the core
imports this**; the library works without the index and gains this when it is present.
Generate with `python3 build-atlas.py <pages-dir> -o atlas.json`.

### `loadAtlas(url, {fetch})` → `Promise<MushafAtlas>`
### `atlasFrom(data)` → `MushafAtlas`

`pageOf(aid)`, `pageOfWord(wid)`, `pageRange(n)`, `surah(n)`, `pageOfSurah(n)`,
`surahs`, `findSurah(text)`, `juz(n)`, `hizb(n)`, `rub(n)`, `nisf(n)`,
`pagesOfJuz(n)`, `juzAt(aid)`, `hizbAt(aid)`, `rubAt(aid)`, `divisionAt(kind, aid)`.

```js
const atlas = await loadAtlas('atlas.json');
atlas.pageOf('2:255');        // 42
atlas.juz(30);                // {n: 30, aid: '78:1', page: 582}
atlas.pagesOfJuz(30);         // [582, 604]
atlas.findSurah('The Cow');   // [{n: 2, latin: 'Al-Baqarah', page: 2, …}]
```

`pageOf` is a binary search over one first-ayah key per page — valid because **no ayah
spans two pages**.

---

## Arabic text tools

### `normalizeQuery(s)`
Strip + fold + collapse whitespace. The default search key.

### `stripArabicMarks(s)`
Harakat, tanween (including the open forms U+08F0–08F2 this print uses), the dagger
alef, the waqf/dabt block, tatweel, and the rubʿ sign.

### `foldArabic(s)`
`أإآٱ→ا`, `ى→ي`, `ة→ه`, `ؤ→و`, `ئ→ي`. **Nothing is folded in the stored data on
purpose** — fold on your side and keep the file as written.

### `looseKey(s)`
Additionally drops bare alef and hamza, so a typed `الرحمان` finds the printed
`الرحمن`. Used only as the second pass in `search`.

### `TEXT_FORMS`, `SVGNS`, `version`
### `boxInView(svg, el)` · `measured(el, fn)`
The geometry primitives, exported for building your own helpers.

---

## Traps

**An ayah is not a subtree.** It is emitted once per printed line, so
`querySelector('g.ayah[data-aid="2:255"]')` gives you fragment 1 of N. `page.ayah()`
returns all of them; `ayah.parts` and `ayah.complete` tell you whether you have the
lot. On page 42, 2:255 is six fragments on six printed lines (8–13).

**Pages 1 and 2 are the opening spread.** Different viewBox, different page matrix,
**8 printed lines instead of 15**, and **12 decorative rosettes with no `data-aid`**.
Nothing in this library hardcodes `15` or `0 0 345 550`; if you extend it, read both
off the file. `page.markers()` already excludes the rosettes.

**`getBBox()` lies about position.** It reports a group's own user space and ignores
every transform above it — it will put line 1 at the bottom of the page. **`getCTM()`
lies about units**: it maps to the nearest *viewport*, i.e. CSS pixels after the
viewBox scaling, so anything you write back as a viewBox coordinate lands in the wrong
place. Use `word.box()` / `boxInView()`, which compose the screen CTMs.

**Never key on `data-eid` or `data-sig`.** The first is explicitly not stable across
builds; the second is a shape hash, not an identity (98 signatures serve more than one
mark name). This library uses neither.

**`data-mark-family` is not a reliable selector.** It does not match `FORMAT.md` and
it has changed shape during this project. FORMAT §6.5 documents `dots, tanween, waqf,
sifr, sajdah, reading-sign`; the build emitted `diacritic, dots, waqf, sifr, sajdah`
(no `tanween` at all, `diacritic` undocumented), and now emits the **multi-valued**
`data-mark-family="diacritic tanween"` on tanween paths. Every exact-match selector —
including FORMAT §11's own recipes — breaks on at least one of those builds; `~=`
would be needed today. `page.marks({family: …})` is unaffected because it resolves a
family to `data-mark` **names** and selects on those.

**Things you must tear down.** `attachSelection().detach()`, `onWordHover().remove()`,
`onWordClick().remove()`, `acquireHitLayer().release()`, `page.onTap().remove()`,
`fitToViewport({observe: true}).remove()`, `mask().remove()`, `annotate().remove()`.
Each releases its own listeners and observers; the shared hit layer goes away when the
last holder releases it.

**A mark can be drawn outside its word**, so word boxes overlap and a hit box can be
narrower than the ink it names. Trust `data-wid`, never geometry, for ownership.

---

## Testing

217 assertions run in Chromium against real pages — **1** (opening spread, 8 lines,
decorative rosettes), **42** (rubʿ rosette, 2:255), **48** (2:282, fifteen fragments),
**176** (sajdah), **582** (juz 30 opens, banner + basmalah), **604** (last page, three
banners) — plus the interactive checks: a genuine mouse drag across a line break,
Ctrl+C, hover, a click in a 6.96 px gap, and a window resize. Zero console errors, no
failed requests.

Measured, not asserted loosely: the layer's ink boxes sit on the ink to **0.005 px**
across 147 words, and to **0.002 px** after a resize.

**Not covered:** the OS clipboard handoff. The headless environment has no system
clipboard (a plain two-textarea control fails identically), so the tests assert the
`copy` event payload — the exact string handed to `clipboardData.setData` — and not
what a real paste produces. Everything up to the OS boundary is verified.
