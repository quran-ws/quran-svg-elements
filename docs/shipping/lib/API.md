# mushaf.js — API reference

Every public function: signature, parameters, what it returns, what it mutates, and a
runnable example. You should not need to read the source.

Working name; see [README](README.md#mushafjs). Licence: **[to be decided — no terms
are stated in this directory].**

**Conventions used throughout**

- **`target`** — anything [`page.resolve()`](#pageresolvetarget) accepts: `'page'`,
  an ayah key `'2:255'`, a word key `'2:255:3'`, `{line: 7}`, `{ayah, wordKeys, surah}`,
  a `Word`, an `Ayah`, a `Line`, an element, or an array of any of those.
- **`form`** — one of `'rasm_uthmani' | 'rasm_imlai' | 'qpc' | 'rasm' | 'search'`
  (`TEXT_FORMS`). Default `'rasm_uthmani'` for display, `'search'` for searching.
  A production page carries only `rasm_uthmani` inline; the other four come from the
  page's sidecar `index/by-page/NNN.json` once attached (`createLoader({words:
  true})` or `page.attachWords()`), and read as `null` before that.
- **Handles.** Every mutating call returns an object with **`.remove()`** that undoes
  exactly what it did and nothing else. There is no global reset.
- **Ownership.** `MushafPage.load()` and `page.clone()` give you a page you own.
  `new MushafPage(el)` wraps an element **without cloning**, so a later mutating call
  changes *your* element.

**Contents** · [Loading](#loading) · [Identity](#identity) ·
[Metadata](#metadata) · [Words, ayahs, lines](#words-ayahs-and-lines) ·
[Text](#text) · [Search](#search) · [Highlighting](#highlighting) ·
[Hit testing](#hit-testing) · [Marks](#marks) · [Theme](#theme) ·
[Ayah markers](#ayah-end-marks) · [Ornaments](#another-mushafs-ornaments) ·
[Layout](#layout) · [Crop](#crop) ·
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
| `words` | `null` | also fetch and attach the page's text sidecar `index/by-page/NNN.json` (FORMAT §6.1). `true` → `baseUrl + '../index/by-page/'`; a string → that base; a function → `n => url`. A production page has only `data-rasm-uthmani` inline, so `search()` and the other four forms need this. A sidecar that fails to fetch throws. |

```js
const load = createLoader({ baseUrl: '/quran/pages/', words: true });
const page = await load(42);            // page.search() works: the sidecar is attached
```

### `page.attachWords(sidecar)` → `number`

Attach `index/by-page/NNN.json` by hand (the object, its `words` array, or a
wordKey-keyed object / `Map`). Returns the record count. Carried by `clone()`. After
this, `word.form()`, `word.text`, `page.text()` and `page.search()` read the four
derived forms from it; an inline attribute (dev profile) always wins.

### `page.hasForm(form)` → `boolean`

Whether `form` is readable on this page — inline or attached. `rasm_uthmani` always is.

### `MushafPage.load(n, options)`

One-shot convenience over `createLoader`. Same options.

### `MushafPage.parse(svgText, options)`

Parse a string. Returns a page you own. Throws on a parse error.

### `new MushafPage(svgElement, {number, stripPolygons})`

Wrap an `<svg>` already in your document. **Does not clone and does not mutate.**

### `page.clone()` → `MushafPage`

Deep copy with every `id` namespaced (and `data-mark` kept in step), so two copies
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

### `page.summary()`
Everything at once: profile, viewBox, line and word and ayah counts, surah numbers,
marker count, decorative-rosette count (always 0 on pages built since 2026-09-04 — every
marker group now carries `data-ayah-key`), sajdahs, rosettes, divisions.

### `page.stripPolygons()` → `number`
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
`data-word-key`, so you always get a complete list.

```js
(await load(582)).surahs();
// [{number: 78, arabic: 'النبإ', latin: 'Naba', english: 'The Tidings',
//   revelationPlace: 'makkah', ayahCount: 40,
//   hasBanner: true, hasBasmalah: true}]
// On a page that continues a surah, that surah comes back with only its
// number and hasBanner: false — the banner attributes exist nowhere else.
```

### `page.divisions()` → `{juz, hizb, nisf, rubu_al_hizb}`

Divisions that **start** on this page: `{n, ayahKey, line}[]`, sorted. All 240 rubʿ
boundaries are tagged even where no rosette is drawn.

```js
(await load(582)).divisions().juz;   // [{n: 30, ayahKey: '78:1', line: 3}]
```

### `page.divisionMarks()` → the *drawn* `g.division-mark`

`{el, ayahKey, rubu_al_hizb, rubuAlHizbInHizb, nisf, hizb, juz}[]`. 199 exist for 240 boundaries — use
`divisions()` for the boundaries, this for the drawing.

### `page.sajdahs()` → `{el, sign, ayahKey, line}[]`

Counted by `data-mark="sajdah_mark"`, **not** by group: two sites in the corpus are
split into two groups with unreliable `data-ayah-key`.

### `page.ayahMarks()` → `{el, ayahKey, id, ring, numeral}[]`

`g.ayah-mark[data-ayah-key]` — one per ayah. On pages 1–2 the group holds a second
ornament path tagged `data-duplicate="1"` (the artwork draws the ring twice; FORMAT
§9.2); `ring` is the first. Page files built before 2026-09-04 carried 12 id-less
"decorative" groups on those pages; they are excluded here and by `styleMarks`.

### `page.ayahMarkGroups()` → `Element[]`
Every `.ayah-mark`, id-less groups of older page files included.

### `page.ayahKeys()` → `string[]`
Ayah keys in reading order, deduplicated.

---

## Words, ayahs and lines

### `page.words(selector)` → `Word[]`
`{line}`, `{ayah}`, `{surah}`, `{wordKeys}` — combinable. No selector: every word.

### `page.word(wordKey)` → `Word | null`

A **`Word`** has `el`, `wordKey`, `surah`, `ayah`, `number` (which word of its
ayah it is — the third number of the word key), `ayahKey`, `line`,
`text` (all five forms), `form(which)`, `paths()`, and `box()`.

### `word.box()` → `{x, y, w, h, x0, y0, x1, y1}`

**In the page's own viewBox units**, through the full transform chain — every
`g.line` has its own frame and the page matrix flips y. Do not use `getBBox()`
yourself; it reports a group's own user space and ignores every transform above it.

### `page.ayah(ayahKey)` → `Ayah | null`

**An ayah is several fragments, one per printed line — see [Traps](#traps).** This
returns *all* of them.

`Ayah` has `ayahKey`, `surah`, `number`, `fragments` (the groups on this page),
`fragmentCount` (how many the file says the ayah has here), `isComplete`,
`markId` and `mark` (its end-mark's id and element), `lines`, `words()`,
`text(form)`.

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
a space (`إِلْ يَاسِينَ`, and 367 `data-search` values). `data-word-key` is the only key.

---

## Search

### `page.search(query, options)` → `Match[]`

`Match` is `{word, wordKey, value, index}` — the `Word` object, so you can highlight or
scroll to it directly.

| option | default | |
|---|---|---|
| `form` | `'search'` | the diacritic-free key. **Never use `'rasm'` for a search box** — it is the *rasm_uthmani* skeleton, so stripping deletes long vowels written as combining marks. On a production page the form lives in the sidecar: load with `createLoader({words: true})` or call `page.attachWords()` first, or `search()` throws an error that says so |
| `mode` | `'includes'` | `'exact'`, `'prefix'`, `'regex'` |
| `normalize` | `true` | apply [`normalizeQuery`](#normalizequerys) to both sides |
| `loose` | `true` | if the strict pass found **nothing**, retry with [`loosenQuery`](#loosekeys). Never widens a query that already matched |
| `limit` | `Infinity` | |

```js
page.search('الله', {mode: 'exact'}).map(m => m.wordKey);
// p42 → ['2:253:10','2:253:24','2:253:45','2:253:49','2:255:1']

(await load(1)).search('الرحمان', {mode: 'exact'}).map(m => m.wordKey);
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

### `page.highlightAyah(ayahKey, options)` → handle

Band plus an ink class, the common case. `{band, ink, bands, remove()}`. Pass
`{ink: false}` for band only, or `{band: {...}, ink: {...}}` to configure each.

### `page.clearBands(className?)` → `number`
Remove every band this library drew.

### `page.lineBands()` → `Map<lineNumber, {y0, y1, mid, inkY0, inkY1}>`
The pitch-derived vertical band of each printed line, in viewBox units. Cached.

---

## Hit testing

### `page.hitTest(x, y, options)` → `{word, wordKey, ayahKey, line, distance, exact} | null`

**Pure geometry — no DOM, no overlay.** The opt-out path.

| option | default | |
|---|---|---|
| `space` | `'client'` | `'view'` for viewBox units |
| `maxDistance` | `Infinity` | refuse a hit further than this (viewBox units) |
| `gapBias` | `0.6` | share of a gap awarded to the **preceding** word |

**Nearest with direction, not naive nearest.** The point is resolved to a printed line
by its band, then to a word on that line; a point in the gap between two words is
biased toward the *preceding* (right-hand) word, because in this print a word's
trailing ink — the tanwin of a final `ة`, the small waw of a pronominal suffix — is
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
page.onTap(({wordKey, ayahKey, exact}) => console.log(wordKey, ayahKey, exact));
```

If you are already using the hit layer, prefer [`onWordClick`](#onwordclickpage-handler-options)
— same answer, one fewer listener.

---

## Marks

Families and categories are resolved through an **embedded copy of the taxonomy
registry**, to `data-mark` names — never through the `data-mark-family` attribute,
which does not match `FORMAT.md` in the current build (see [Traps](#traps)).

### `page.marks(selector)` → `Element[]`
`{name, family, category, wordKey, ayah, line}`. `name` may be a string or an array.

Families: `dots`, `waqf`, `tanwin`, `sifr`, `sajdah`, `reading_sign`, plus the
convenience aliases `diacritic` (harakahs + tanwin + maddah — what the files
themselves write), `harakah` and `vowels`.
Categories: `harakah`, `tanwin`, `letter_dot`, `orthographic`, `dabt`,
`reading_sign`, `waqf`, `standalone`.

### `page.styleMarks(selectorOrPaths, style)` → handle
CSS properties as an object. `remove()` restores the previous inline style.

### `page.hideMarks(selector)` → handle

```js
page.hideMarks({family: 'diacritic'});   // vowels gone; dots and waqf signs untouched
page.styleMarks({family: 'dots'}, {fill: '#b03030'});
page.marks({name: 'small_meem'});        // the iqlab meems ON THIS PAGE
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

## Ayah end-marks

### `page.styleAyahMarks(options)` → handle

| option | |
|---|---|
| `ring` | colour of the ornament ring |
| `numeral` | colour of the printed numeral, independently |
| `scale` | scales the whole medallion about its centre |
| `hide` | `true` for a reading view with no markers |
| `replaceRing` | `true` for a plain circle, or `fn({x,y,w,h,cx,cy,r}, marker) → Element` for your own shape, **keeping the printed numeral** |

Only `g.ayah-mark[data-ayah-key]` groups are touched — every marker on a current page;
older page files' 12 id-less groups on pages 1–2 are left alone.

### `page.hideAyahMarks()` → handle

---

## Layout

### `setLineGap(page, gap, {pad, carryMarks})` → handle

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

### `page.crop(target, {pad, keepMarks, background})` → `{el, page, viewBox, words, toString(), toDataUrl()} | null`

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
`spanOf(wordKey)`, `wordKeyOf(node)`, `rebuild()`, `onRebuild(fn) → off`,
`wordAt(clientX, clientY, opts)`, `release()`.

Each span carries `data-word-key`, `data-line`, `data-ayah-key` and `data-ink`
(`"x y w h"` of the word's **ink** box, relative to the layer — for drawing).
The span's own geometry is the **hit** box.

### `hasHitLayer(page)` → `boolean`

### `onWordHover(page, handler, options)` → handle

Fires **once per word entered**. `{level: 'word'|'ayah', maxDistance, gapBias, onLeave}`
plus any `acquireHitLayer` option.

```js
const h = onWordHover(page, ({word}) => tip.textContent = word.text.rasm_uthmani);
h.remove();     // releases its reference to the layer; other consumers keep theirs
```

### `wordTooltip(page, render, options)` → handle

The whole of a hover-tooltip in one call: one absolutely positioned `<div>` in the
stage, `render(word, hit, ev)` for its contents, and the placement — above the word,
below it when there is no room, clamped inside the stage. Returning `null` or `false`
from `render` leaves it hidden, which is how "no entry for this word" is said without a
second call.

**The library owns the placement, not the look.** Every pixel of styling comes from
the class you pass; the only rule it sets is `position: absolute`.

| option | default | |
|---|---|---|
| `className` | `'mushaf-tip'` | your class, and nothing is added to it |
| `visibleClass` | `'on'` | toggled while the tip is showing |
| `gap`, `pad` | `8`, `4` | px from the word, px kept clear of the stage edges |
| | | plus any `onWordHover` option except `onLeave` |

```js
const tip = wordTooltip(page, w => gloss[w.wordKey] || null, {className: 'q-tip'});
tip.remove();      // takes the element and the layer reference with it
```

`render` returning a string sets `innerHTML`; return a **Node** when the text is not
yours (a translation feed, a user's note) and the markup should not be interpreted.

Handle: `el`, `hide()`, `remove()`.

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
| `form` | `'rasm_uthmani'` | what the spans carry **and** what Ctrl+C copies |
| `citation` | `false` | `true` → `"…text… (2:255)"`; or `fn(words, text, ayahKeys) → string` |
| `onSelect` | – | `({text, words, ayahKeys})` on every change |
| `copy` | `true` | install the `copy` handler |
| `paintBand` | `true` | draw the selection band |
| `bandFill`, `bandOpacity`, `bandPadX` | `'#2d6fd6'`, `0.25`, `0.6` | |

Handle: `layer`, `hitLayer`, `form`, `setForm(f)`, `setCopyForm(f)`, `count`,
`rebuild()`, `spans()`, `words()`, `text(form)`, `payload(form)`,
`selectWords(wordKeys)`, `clear()`, `band`, `repaint()`, `detach()`.

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
`hide(n)`, `revealWord(wordKey)`, `revealAll()`, `hideAll()`, `remove()`.

```js
const m = mask(page, '2:255');
m.revealNext();          // one word at a time, in reading order
m.remove();
```

`'hide'` uses `visibility: hidden`, so the printed page keeps its shape and spacing —
which is the point.

### `reveal(page, options)` → handle

The page greyed, and the reading position inked — the reader-follows-along mechanism
as one call. **The clock is yours**: a transport bar, a recitation, a scroll position
or a keypress all drive the same handle through `goto(i)`.

| option | default | |
|---|---|---|
| `lit` | `1` | how many steps stay at full ink behind the position |
| `byAyah` | `false` | step an ayah at a time instead of a word at a time |
| `grey`, `ink` | `'#c9c4b8'`, `'#231f20'` | |
| `markers` | `true` | light each medallion with the ayah it **closes** |
| `at` | `0` | where to start |

```js
const show = reveal(page, {lit: 3});
show.goto(show.at + 1);         // one step on
show.remove();
```

Handle: `steps`, `closes`, `count`, `at`, `key`, `goto(i)`, `remove()`.

Three things it gets right that are easy to get wrong: the grey is **one scoped CSS
rule**, not a walk over a thousand paths (every path in the mushaf ships the same
fill); `steps` is document order, which **is** reading order; and a medallion belongs
to the ayah it closes, so it lights when that ayah's **last** word is reached.
A medallion is not a word, so it is painted directly — `page.highlight()` resolves an
element to the `g.word` groups inside it, and a medallion has none.

### `maskFrom(page, wordKey, options)` → handle
Mask everything from a word onward.

---

## Recitation

### `followRecitation(page, options)` → `Promise<handle>`

Word-by-word-translation follow-along against per-ayah audio. The library owns the **join** and
the **clock**; the caller owns the buttons.

| option | default | |
|---|---|---|
| `reciter` | `9` | quran.com recitation id (9 = Minshawi, murattal) |
| `timings` | – | `{ayahKey: [url, [[startMs, endMs]…]]}` — given, nothing is fetched |
| `endpoint`, `cdn`, `timeout` | quran.com, qurancdn, 6000 | |
| `paint` | `true` | `false` reports position and leaves the ink alone |
| `grey`, `ink` | `'#c9c4b8'`, `'#231f20'` | |
| `onWord` | – | `({ayahKey, index, count, file, files, whole})` on every change |
| `onEnd`, `onError` | – | |

```js
const f = await followRecitation(page, {onWord: w => bar.textContent = w.ayahKey});
await f.play();
f.pause(); f.remove();
```

Handle: `ayahs`, `mismatches`, `playing`, `file`, `index`, `segments`,
`play()`, `pause()`, `seek(i)`, `remove()`.

**The guard is the point.** Timings come from a different decomposition of the same
text, and two decompositions count words differently — p254 13:37 is 19 words there
and 20 here. Zipping the lists drifts silently from that word to the end of the ayah,
so where the counts disagree the ayah is followed **whole** and the disagreement is
reported in `mismatches` rather than hidden. Timings covering none of the page throw;
they are never a silent no-op.

Needs `page.number` (`new MushafPage(svg, {number})` or the loader) unless you pass
`timings` yourself.

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

## Swappable ayah end-marks (`markers.mjs`)

Replace the printed ornament **ring** on every medallion with an outline from an
external marker set, recolour it part by part, and put the print back exactly.

**The numeral never changes.** It is the print's own drawing of the number, not a font
rendering of it, and it is not touched by anything in this module. The replacement is
positioned so that the design's **own** number-centre lands on the printed numeral, and
scaled from the box the ring occupied.

**Nothing is redistributed.** No outline ships with this library. `loadMarkSet()`
takes a base URL and fetches at runtime. The reference set is
[`quranpedia/ayah-marks`](https://github.com/quranpedia/ayah-marks), which traces
its 47 markers (20 designs across weights) from twenty type families — fifteen from
Google Fonts, five from fonts.quran.ws. **They carry those families' licences, which
differ from one another**; every marker names its own `sources` in that repository's
`collection.json`. Read it before you redistribute anything. This library states no
licence terms and grants none: it is the mechanism, not the material.

### `loadMarkSet(baseUrl, {fetch, cache})` → `Promise<MarkSet>`

Fetches `collection.json` once. Cached per URL; a *failed* load is not cached, so a
retry when the network returns works. Rejects with the URL in the message — catch it
and say so rather than showing a dead pane.

```js
const set = await loadMarkSet('https://quranpedia.github.io/ayah-marks/');
set.list();       // [{id, family, weight, codepoint, width, upem, number, sources[]}, …]
set.families();   // [{family: '017', weights: [...]}, …]  — what a picker wants
set.record('017-regular').sources;   // the licence trail
```

### `set.outline(id)` → `Promise<{id, viewBox, box, groups, parts, number}>`

Fetches one marker SVG and reads it. Cached per id. The file arrives **already
layered** — one `<g data-part>` per colourable part — and those groups are taken
verbatim, so `groups` are upstream's own nodes and `parts` is the list of part names
in the order the design draws them. `box` is the drawing's **measured** bounding box,
not the padded `viewBox`.

`number` is the design's own answer to where the ayah number sits, in its own
coordinates, carried through **whole**: `{cx, cy, width, height, r}` today, whatever
upstream publishes tomorrow. `numberCentre(outline)` reads only `cx`/`cy` and returns
`{cx, cy}`; `null` if the design publishes no record at all, and it **throws** if a
record is present but has no usable centre — a trimmed field must not silently hang the
design off the wrong point.

### `setAyahMark(page, outline, options)` → handle

| option | | |
|---|---|---|
| `target` | `'page'` | `'page'`, an ayah key `'2:255'`, an `Ayah`, or an array of those |
| `size` | `1` | factor on the fitted size; `1` matches the ring's box |
| `colours` | `null` | `{part: colour}` — sets upstream's `--<part>` custom properties on the `<svg>` |
| `anchorOnNumber` | `true` | put the design's own number-centre on the printed numeral; `false` centres box on box |
| `decorative` | `false` | include the `g.ayah-mark` groups with **no** `data-ayah-key` (none on pages built since 2026-09-04; kept for older page files) |

**Only `g.ayah-mark[data-ayah-key]` is touched unless you ask for the rest.** On pages 1–2
the artwork draws each ring twice and the copy sits inside the same group as
`data-duplicate="1"`; `replaceRing` swaps the first ring and hides the copy.

`handle.remove()` restores the printed rings exactly — the original `<path>` node is
kept, not re-serialised — and unsets any custom properties `colours` set.

### `resetAyahMarks(page, {decorative})` → `{count}`
### `hasSwappedMarks(page)` → `boolean`
### `colourAyahMarks(page, colours)` → handle

Recolours what is already on the page by setting the custom properties on the `<svg>`,
without rebuilding anything. Pass `null` for a part to unset it.

### `readOutline(svgText, rec)` · `numberCentre(outline)` · `fitTransform(from, to, size)`

The primitives, exported for building your own.

### Recolouring is upstream's CSS contract, and needs no JavaScript

Seven part names — `fill-base`, `fill-1`, `fill-2`, `fill-3`, `ink-base`, `ink-1`,
`ink-2` — each drawn by upstream as a group carrying

```
style="fill:var(--ink-base,#083a3a)"
```

with a **baked-in default**, so a marker arrives coloured the way its designer coloured
it. Setting the custom property on any ancestor recolours it, live:

```css
.my-page { --ink-base: #b08d2e; --fill-base: #f6ecd9; }
```

```js
const set = await loadMarkSet(BASE);
const h = setAyahMark(page, await set.outline('017-regular'),
                        { colours: { 'ink-base': '#b08d2e' } });
colourAyahMarks(page, { 'ink-1': '#8a6d1f' });     // same thing, later
h.remove();                                          // the print is back
```

Each design uses only some of the seven; `outline.parts` lists the ones it draws, and a
control offering a part the design does not have is a lie about the drawing.

**The `--ayah-mark-<part>` names this library once used are retired.** They were a
workaround for a format that no longer exists.

### What this module used to do

Upstream once shipped each marker as one `<path>` holding every contour, with a
separate `annotations.json` saying which contour belonged to which part. Cutting that
up was the hard part of this file: the counters — the holes that make a ring a ring —
are winding-based, and a hole and the shape it punches routinely belong to different
parts, so every layer had to re-include the earlier-layer contours lying inside it and
draw `evenodd`. Getting it wrong turned 39 of the 47 markers into solid blobs. Upstream
now ships the layering, the `fill-rule` and the re-inclusion, so all of that is gone
and the groups are taken as they come. If a marker draws solid, it draws solid
upstream.

---

## Another mushaf's ornaments (`ornaments.mjs`)

Put a *different printed mushaf's* furniture on this print: the medallion that closes
an ayah, the banner behind a surah's printed name, and the border around the page —
while every glyph of this print stays exactly where the King Fahd Complex put it.

`markers.mjs` swaps the ring on one medallion. This is the same contract one layer up,
for all three decorative parts at once.

**Nothing is placed at a fixed offset.** Each ornament is sized from a *measurement* of
the group it dresses — the medallion from the printed ring's box, the banner from the
surah name's box, the border from the page's own `viewBox`. That is why the same call
lands correctly on all 604 pages, and on pages 1–2 whose viewBox and page matrix are
different again.

**Nothing is redistributed.** No ornament ships with this library. The reference set is
[`quran-ws/quran-assets`](https://github.com/quran-ws/quran-assets), traced from scans
of eight printed mushafs. Every asset is `CC-BY-NC-SA-4.0`, status **provisional**,
`redistributable: false` while written permission is sought from the publishers, and
each names its source mushaf, archive.org item and PDF page. `set.licence(style)` hands
the terms straight through so you can honour them. **Check it before you ship anything.**

### `loadOrnamentSet(baseUrl, {fetch, cache})` → `Promise<OrnamentSet>`

Fetches `catalog.json` once. Cached per URL; a *failed* load is not cached, so a retry
when the network returns works. Rejects with the URL in the message.

```js
const set = await loadOrnamentSet('https://example.org/quran-assets/');
set.styles();                       // ['douri', 'hafs-adi', 'qalon', …] — the mushafs
set.record('ayahMark', 'qalon');    // the catalogue record, by OUR name for the concept
set.record('ayah-markers', 'qalon');// or by the catalogue's own type string
set.licence('qalon');               // {id, status, redistributable, attribution, …}
```

`ORNAMENT_TYPES` is the mapping, and it is the vocabulary rule of this library applied
to someone else's names: the medallion is an **ayah mark** everywhere, a surah's printed
title is its **banner** (`page.surahs().hasBanner`), and the frame around the text is
the **border**.

| ours | the catalogue's |
|---|---|
| `ayahMark` | `ayah-markers` |
| `surahBanner` | `surah-headers` |
| `pageBorder` | `page-frames` |

### `set.ornaments(style)` → `Promise<{ayahMark, surahBanner, pageBorder, parts, palette, licence}>`

Everything one mushaf needs, fetched and parsed on first ask, then cached. A style that
publishes only some of the three gets only those. `parts` is the list of colourable part
names — **what a colour picker should offer**; a control for a part the design does not
draw would misdescribe the drawing.

Each asset carries `{viewBox, vb, slot, nodes, parts}`. `slot` is the transparent window
the design leaves for the surah name, the text area or the ayah number, in the asset's
own units.

### `dressPage(page, ornaments, {…})` → handle

```js
const h = dressPage(page, await set.ornaments('qalon'), {
  ayahMark: true, surahBanner: true, pageBorder: true,
  gap: 5, size: 1, lineArt: false, colours: { c1: '#fffdf7', line: '#3b2a12' }
});
h.ayahMarks;    // medallions drawn
h.surahBanners; // banners drawn — 0 on a page with no surah start, which is most pages
h.border;       // whether a border was drawn
h.repeats;      // pieces the border was assembled from
h.stretched;    // true when this border does not tile and was scaled whole
h.missing;      // ['surahBanner', …] — parts this style does not publish
h.remove();     // rings back, layer gone, viewBox restored
```

| option | | |
|---|---|---|
| `ayahMark` / `surahBanner` / `pageBorder` | `true` | which parts to draw |
| `gap` | `5` | breathing space between the text and the border, in page units |
| `size` | `1` | factor on each medallion; 1 matches the printed ring's box |
| `lineArt` | `false` | keep the constant-width strokes only, and drop the fills |
| `colours` | `null` | `{part: colour}`, painted on the ornaments and never on the print |

Everything goes into one `<g class="mushaf-ornaments">` at the **front** of the root, so
it renders behind the print. That is the whole trick with the ayah numbers: **this module
never draws a number.** The printed ring is *hidden*, the numeral is this print's own ink
and it stays on top of whatever replaced the ring around it.

**The border grows the page; it never covers a word.** It is drawn *around* the text, so
the `viewBox` is widened by the band that was added. Nothing is scaled and no word moves.
Where a border tiles, it is assembled from a corner and two repeat units — the corner
keeps its shape and only the straight run repeats, a whole number of times each nudged to
fit exactly. Where it does not tile, the whole drawing is scaled and `stretched` says so.

### `colourOrnaments(page, colours)` → `{count, remove()}`

Recolour what is on the page without rebuilding it. `line` is a stroke; every other part
is a fill. A part the design does not draw is a no-op, not an error.

> **This is the one place in the library where a stylesheet is the wrong tool.** These
> designs are symmetric — one quadrant mirrored with `<use>` — and a `<use>` instance is a
> shadow copy that your selector does not reach. A CSS rule recolours the original in
> `<defs>` and leaves the copies on screen exactly as printed, which reads as the colour
> control doing nothing at all while `getComputedStyle` on the original insists the rule
> applied. This paints the original's attribute, and every instance inherits it.

### `resetOrnaments(page)` / `hasOrnaments(page)`

`resetOrnaments` is `handle.remove()` for a caller who did not keep the handle.

### `readOrnament(svgText, record)` → `{viewBox, vb, slot, nodes, parts}`

Read one asset. Exposed because it is the whole parse, and because two things happen on
the way in that a caller doing this by hand will get wrong: `<metadata>` is dropped (a
provenance blob repeated in the catalogue, otherwise cloned once per medallion), and
**ids are renamed**. They are *file*-local — every marker defines `<g id="q">` and mirrors
it with `<use href="#q">` — so two assets in one document is a duplicate id and every
`<use>` then silently draws the first one: one mirrored half drawn twice on the same
side, with no error anywhere.

### Line art

`lineArt: true` keeps `<g data-part="line">` and drops the rest. That group is path for
path what the published `line.svg` holds, so **no second file is fetched** — and it gives
the *tiled* border line art too, which `line.svg` could not have, since `slices/`
publishes one variant only. One ink left means one colour to choose.

---

## Atlas (cross-page lookup)

A single page file cannot answer "which page is 2:255 on". **Nothing in the core
imports this**; the library works without the index and gains this when it is present.
Generate with `python3 build-atlas.py <pages-dir> -o atlas.json`.

### `loadAtlas(url, {fetch})` → `Promise<MushafAtlas>`
### `atlasFrom(data)` → `MushafAtlas`

`pageOf(ayahKey)`, `pageOfWord(wordKey)`, `pageRange(n)`, `surah(n)`, `pageOfSurah(n)`,
`surahs`, `findSurah(text)`, `juz(n)`, `hizb(n)`, `rubu_al_hizb(n)`, `nisf(n)`,
`pagesOfJuz(n)`, `juzAt(ayahKey)`, `hizbAt(ayahKey)`, `rubuAlHizbAt(ayahKey)`, `divisionAt(kind, ayahKey)`.

```js
const atlas = await loadAtlas('atlas.json');
atlas.pageOf('2:255');        // 42
atlas.juz(30);                // {n: 30, ayahKey: '78:1', page: 582}
atlas.pagesOfJuz(30);         // [582, 604]
atlas.findSurah('The Cow');   // [{n: 2, latin: 'Baqarah', page: 2, …}]
```

`pageOf` is a binary search over one first-ayah key per page — valid because **no ayah
spans two pages**.

---

## Arabic text tools

### `normalizeQuery(s)`
Strip + fold + collapse whitespace. The default search key.

### `stripArabicMarks(s)`
Harakahs, tanwin (including the open forms U+08F0–08F2 this print uses), the dagger
alef, the waqf/dabt block, tatweel, and the rubʿ sign.

### `foldArabic(s)`
`أإآٱ→ا`, `ى→ي`, `ة→ه`, `ؤ→و`, `ئ→ي`. **Nothing is folded in the stored data on
purpose** — fold on your side and keep the file as written.

### `loosenQuery(s)`
Additionally drops bare alef and hamzah, so a typed `الرحمان` finds the printed
`الرحمن`. Used only as the second pass in `search`.

### `TEXT_FORMS`, `SVGNS`, `version`
### `boxInView(svg, el)` · `whileRendered(el, fn)`
The geometry primitives, exported for building your own helpers.

---

## Traps

**An ayah is not a subtree.** It is emitted once per printed line, so
`querySelector('g.ayah-fragment[data-ayah-key="2:255"]')` gives you fragment 1 of N. `page.ayah()`
returns all of them; `ayah.fragments` and `ayah.isComplete` tell you whether you have the
lot. On page 42, 2:255 is six fragments on six printed lines (8–13).

**Pages 1 and 2 are the opening spread.** A different page matrix, **8 printed lines
instead of 15**, and every ornament ring drawn twice (the copy is `data-duplicate="1"`
inside its marker group). Since 2026-09-04 the viewBox is `0 0 345 550` on every page;
nothing in this library hardcodes `15` or the viewBox — if you extend it, read both off
the file.

**`getBBox()` lies about position.** It reports a group's own user space and ignores
every transform above it — it will put line 1 at the bottom of the page. **`getCTM()`
lies about units**: it maps to the nearest *viewport*, i.e. CSS pixels after the
viewBox scaling, so anything you write back as a viewBox coordinate lands in the wrong
place. Use `word.box()` / `boxInView()`, which compose the screen CTMs.

**Never key on `data-element-id` or `data-sig`.** The first is explicitly not stable across
builds; the second is a shape hash, not an identity (98 signatures serve more than one
mark name). This library uses neither.

**`data-mark-family` is not a reliable selector.** It does not match `FORMAT.md` and
it has changed shape during this project. FORMAT §6.5 documents `dots, tanwin, waqf,
sifr, sajdah, reading_sign`; the build emitted `diacritic, dots, waqf, sifr, sajdah`
(no `tanwin` at all, `diacritic` undocumented), and now emits the **multi-valued**
`data-mark-family="diacritic tanwin"` on tanwin paths. Every exact-match selector —
including FORMAT §11's own recipes — breaks on at least one of those builds; `~=`
would be needed today. `page.marks({family: …})` is unaffected because it resolves a
family to `data-mark` **names** and selects on those.

**Things you must tear down.** `attachSelection().detach()`, `onWordHover().remove()`,
`onWordClick().remove()`, `acquireHitLayer().release()`, `page.onTap().remove()`,
`fitToViewport({observe: true}).remove()`, `mask().remove()`, `annotate().remove()`.
Each releases its own listeners and observers; the shared hit layer goes away when the
last holder releases it.

**A mark can be drawn outside its word**, so word boxes overlap and a hit box can be
narrower than the ink it names. Trust `data-word-key`, never geometry, for ownership.

---

## Testing

357 assertions run in Chromium against real pages (362 with `?markers=<url>`) — **1** (opening spread, 8 lines,
doubled ornaments), **42** (rubʿ rosette, 2:255), **48** (2:282, fifteen fragments),
**176** (sajdah), **582** (juz 30 opens, banner + basmalah), **604** (last page, three
banners) — plus the interactive checks: a genuine mouse drag across a line break,
Ctrl+C, hover, a click in a 6.96 px gap, and a window resize. Zero console errors, no
failed requests.

The end-mark assertions run against a **synthetic** marker set served by a stub
`fetch` — a square ring whose counter is annotated into a different part, which is
exactly the shape of the real trap — because no outline may ship here. The ornament
assertions are stubbed for the same reason, and the synthetic set carries the traps that
matter: every asset mirrors itself with `<use>` off a file-local `id`, and its border
slices carry the text-area slivers their crops cut through. Point the page
at a real set with `?markers=<url>` and it additionally checks that set for
conformance: every marker cuts into at least one layer, every command is absolute, and
`#0b7771` survives nowhere.

Measured, not asserted loosely: the layer's ink boxes sit on the ink to **0.005 px**
across 147 words, and to **0.002 px** after a resize.

**Not covered:** the OS clipboard handoff. The headless environment has no system
clipboard (a plain two-textarea control fails identically), so the tests assert the
`copy` event payload — the exact string handed to `clipboardData.setData` — and not
what a real paste produces. Everything up to the OS boundary is verified.
