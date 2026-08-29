# `mushaf.js` — API plan

Working name only. **`mushaf` / `MushafPage` / the global `Mushaf` are placeholders**
and are defined in exactly one place (`NAME` in `build-global.js`, and the class name in
`core.mjs`) so renaming is a two-line change. Naming and packaging are Abdullah's call.

The library packages what `docs/demo` teaches by hand: everything below is a technique the
demo demonstrates, or a direct consequence of the schema in `../FORMAT.md`.

---

## 1. Shape of the thing

**A small core class plus separate opt-in modules.** Not one god object.

```
core.mjs        MushafPage — load, identity, metadata, text, search,
                highlight, hit-test, marks, theme, markers, crop
layout.mjs      line gap, fit-to-viewport
selection.mjs   the transparent text layer (drag-select + copy)
memorize.mjs    masking / progressive reveal
a11y.mjs        accessible text for screen readers
atlas.mjs       cross-page lookup, backed by a generated index file
view.mjs        scroll a word or ayah into view
raster.mjs      crop -> PNG
mushaf.mjs      barrel: re-exports everything (this is what the global build wraps)
```

Why this split and not `page.everything()`:

- **Tree-shaking is real only if the extras are not reachable from the core.** A caller who
  wants `highlightAyah` imports `core.mjs` and never pulls in the selection layer, the
  masking module or the raster encoder. If those were methods on `MushafPage` they would be
  in every bundle.
- The extras are therefore **free functions taking a page**: `attachSelection(page, …)`,
  `mask(page, …)`, `fitToViewport(page, …)`. Uniform, obvious, and greppable.
- Everything in the core is something you cannot render a useful page without.

Two rules hold across the whole surface:

- **Nothing mutates a page you did not hand it.** `MushafPage.load()` returns a page you
  own. `page.clone()` gives you a second one. Every mutating method says so in its name or
  its doc line, and **every one returns a handle with `.remove()`** that undoes exactly what
  it did — no `resetEverything()`, no global state.
- **No `data-eid`, no `data-sig`.** Neither is stable or an identity (FORMAT §6.5, §9.0e).
  `data-wid` and `data-aid` are the only keys.

---

## 2. Core

### Loading and identity

| | |
|---|---|
| `createLoader({baseUrl, fetch, cache, stripPolygons})` | returns `load(n)`; caches parsed pages and hands out clones |
| `MushafPage.load(n, opts)` | one-shot convenience over the same path |
| `MushafPage.parse(svgText, opts)` / `new MushafPage(svgEl, opts)` | wrap what you already have; **does not clone, does not mutate** |
| `page.clone()` | deep copy with `id`s namespaced so two copies can share a document |
| `page.el` | the `<svg>` element |
| `page.profile` | `'dev'` \| `'production'`, detected by `g.ligature` (FORMAT §2) |
| `page.viewBox` | `{x, y, w, h}` **read off the file** — never assumed |
| `page.info()` | one object: profile, viewBox, line numbers, word/ayah counts, surahs |

Pages 1–2 have a different viewBox, a different page matrix and 8 lines. Nothing in the
library hardcodes `0 0 345 550` or `15`; both come from the file, and page 1 is in the test
suite for exactly this reason.

### Metadata — the "no database" story

- `page.surahs()` → `{number, arabic, latin, english, revelationPlace, ayahCount, hasBanner, hasBasmalah}[]`
  from the banner attributes, plus surahs merely *present* on the page (read out of
  `data-wid`) with `hasBanner: false` — because those attributes only exist on a surah's
  first page (FORMAT §6.6).
- `page.divisions()` → `{juz, hizb, nisf, rub}`, each an array of `{n, aid, line}` for the
  divisions that **start** on this page, from `data-*-start` on `g.ayah`. All 240 rubʿ
  boundaries are tagged even where no rosette is drawn (FORMAT §9.6).
- `page.rosettes()` → the *drawn* `g.hizb-mark` with `{rub, rubInHizb, nisf, hizb, juz, aid}`.
- `page.sajdahs()` → sites, counted by `data-mark="sajdah-sign"` (15 corpus-wide), not by
  group, because two sites are split into two groups with unreliable `data-aid` (§10.6).
- `page.ayahKeys()`, `page.lineNumbers()`, `page.wordCount`.

### Words, ayahs, lines

`page.words({ayah, line, wids, surah})`, `page.word(wid)`, `page.ayahs()`, `page.ayah(aid)`,
`page.lines()`, `page.line(n)`.

A `Word` carries `wid, surah, ayah, index, aid, line, el`, `text` (all five forms) and
`box()` in the page's own viewBox units. An `Ayah` carries `aid, fragments[], words[],
parts, markerId, marker`, and knows it is **several fragments** (FORMAT §7) — `page.ayah()`
never returns fragment 1 of N pretending to be the ayah.

### Text

`page.text(target, {form, wordSep, lineSep})` where `target` is `'page'`, an aid string, a
`{line}`, a `{wids}`, or an array of words. Line breaks are the mushaf's own. This is #3
from the brief and it is four lines of code that everybody writes wrong once.

### Search

`page.search(query, {form='search', mode='includes'|'exact'|'prefix'|'regex', normalize=true, loose=true, limit})`
→ `Match[]` of `{word, value, index}`.

Normalisation is exported on its own, because it is the difference between a search box that
works and one that demos:

- `stripArabicMarks(s)` — harakat, tanween (including the open forms U+08F0–08F2), the
  dagger alef, the waqf and dabt block, tatweel.
- `foldArabic(s)` — `أإآٱ→ا`, `ى→ي`, `ة→ه`, `ؤ→و`, `ئ→ي`, `ء` kept.
- `normalizeQuery(s)` — strip + fold + collapse whitespace. **The default match key.**
- `looseKey(s)` — additionally drops bare alef, so a typed `الرحمان` finds the printed
  `الرحمن`, whose alef is a dagger alef and is not in `data-search` at all (FORMAT §6.1).
  Used only as a **second pass when the strict pass finds nothing**, so it cannot silently
  widen a query that already worked.

`data-search` is the default form, per FORMAT §6.1. `data-rasm` is offered but documented as
the wrong choice for a search box.

### Highlighting

- `page.highlight(target, {className, fill, opacity})` — recolours ink; handle `.remove()`
  restores the exact previous inline value.
- `page.band(target, {padX, padY, fill, opacity, rx})` — one rect per printed line, in a
  **single group carrying one `opacity`**, so bands that overlap where an ascender overruns
  stay one flat tone (the demo's §4 finding). Painted as the first child of `<svg>`, so the
  ink is never touched.
- `page.highlightAyah(aid, opts)` = band + highlight, the common case.
- `page.clearHighlights()`.

All of them take the same `target` as `text()`, and all handle an ayah being several
fragments across several lines.

### Hit testing

- `page.enableHitTargets({halo})` — the transparent-stroke widening from the demo's §3.
  Changes no pixel; returns a disposer.
- `page.hitTest(x, y, {space:'client'|'view', maxDistance, gapBias})` →
  `{word, ayah, exact, distance}`.
  **Nearest-with-direction, not naive nearest.** The point is first resolved to a printed
  *line* by its band, then to a word on that line; a point in the gap between two words is
  awarded with a bias toward the **preceding** word (`gapBias`, default 0.6), because in
  this print a word's trailing ink — the tanween of a final ة, the small waw of a pronominal
  suffix — is drawn *into* the following gap (FORMAT §9.9, §9.10). Naive nearest gets those
  gaps wrong systematically, always in the same direction.
- `page.onTap(handler, {level:'word'|'ayah', halo, maxDistance})` — one delegated listener,
  returns a disposer. Gap-aware: handler is called with the word the user *meant*.

### Marks

`page.marks({name, family, category, ayah, line, wid})`, `page.styleMarks(sel, style)`,
`page.hideMarks(sel)`.

**Family and category are resolved through an embedded copy of the taxonomy registry, not
through `data-mark-family`.** See §6 — the emitted attribute does not agree with
`FORMAT.md` in the current build, and selecting `[data-mark-family="tanween"]` finds nothing.
Resolving a family to its list of `data-mark` names is correct under both vocabularies.
`MARK_REGISTRY`, `markNames({family})` and `familyOf(name)` are exported.

### Theme

`page.theme({paper, ink, diacritics, dots, waqf, sifr, marker, numeral, mark:{…}})`.

Injects one scoped `<style>` inside the `<svg>` and, for `paper`, a background `<rect>`
sized to the viewBox as the first child — so the theme survives cropping and raster export
instead of living on a container the export does not see. Returns a disposer.

### Crop

`page.crop(target, {pad, keepMarkers, background})` → `{el, viewBox, toString(), toDataUrl()}`.

Clone → drop the words you did not ask for → drop the emptied `g.ayah` / `g.line` wrappers →
`getBBox()` → write the viewBox back. A medallion is kept only when the **whole** ayah
survived, otherwise a one-word crop frames itself around a marker at the far end of the ayah.
Measuring needs the element rendered, so the library parks it in a hidden host and removes
it again; the caller sees only the result.

---

## 3. The modules

### `layout.mjs`

- `setLineGap(page, gap, {pad, carryMarkers})` — moves each `g.line` apart and carries each
  medallion with its ayah's **last** fragment, then grows the viewBox. Returns the new
  viewBox and a disposer.
- `gapToFill({pageW, pageH, lines, viewW, viewH, max})` — **pure arithmetic, no DOM.**
  `needed = pageW * viewH / viewW; gap = (needed - pageH) / (lines - 1)`, **clamped at 0**
  so a viewport that is already wider-for-its-height than the page (iPad portrait) gets a
  gap of zero rather than a negative leading that would overlap lines.
- `fitToViewport(page, {width, height, element, maxGap, observe})` — measures, solves,
  applies. `observe: true` attaches a `ResizeObserver` so the page keeps filling through a
  rotation; **opt-in and detachable**, never a silent global listener.

**Two methods, not one with a mode.** `setLineGap` is a setter — the caller knows the number
they want. `fitToViewport` is a solver that computes a number and then calls the setter.
Folding them into one would make the parameter mean two different things depending on a
flag, and would hide the pure arithmetic that is worth testing on its own.

Measured, page 3–604 (345×550, 15 lines): iPhone 14 reclaims 26.3% of the display at a gap
of 14.0 units; Galaxy S21 28.3% at 15.5. Page 1 (8 lines, its own viewBox) solves to a
different gap from the same formula, which is why the line count and the box are read off
the file.

### `selection.mjs`

`attachSelection(page, {mount, form, citation, onSelect})` → `{rebuild, detach, text(form), words, setForm}`.

Everything the prototype in `docs/demo/parts/` paid for in debugging is inherited:

- measure with **`getBoundingClientRect()`**, not `getBBox()` — the latter reports a group's
  own user space and ignores the transforms above it, which puts line 1 at the bottom of the
  page. Residual error 0.016 px over 127 words.
- **snap the range out to whole words** — inside a transparent span the caret follows the
  fallback font's advances, not the ink.
- **size spans to the word box, never the line box** — a line's rect includes ascenders that
  overrun the neighbouring line, so line-sized bands overlap and darken.
- **no `\n` in the DOM** — build the clipboard payload in a `copy` handler from the selected
  words, which is also what lets the caller choose the text form.
- **rebuild on resize.** The layer is measured in screen pixels; the prototype does not do
  this and that is a real bug, not an inherited one. A `ResizeObserver` on the mount, torn
  down by `detach()`.

`citation: true` copies `…text… (2:255)`; `citation: fn(words, text)` for a caller format.
This is #2 from the brief: only the selection layer knows which ayahs the selection spans.

### `memorize.mjs`

`mask(page, target, {mode:'hide'|'blur'|'block', color, blur})` →
`{reveal(n), revealNext(), revealAll(), hideAll(), remove()}`.

`hide` = `visibility:hidden` on the word group (the printed page keeps its shape and its
spacing, which is the whole point); `block` = an opaque rect over the word box; `blur` = an
SVG filter. Progressive reveal walks the words in `data-wid` order. Impossible with a page
image, three lines with per-word groups.

### `a11y.mjs`

`annotate(page, {form, level})` — an SVG of paths is silent to a screen reader. Adds
`role="img"` + `aria-label` on the `<svg>`, `<title>` per `g.word`, and `aria-label` per
`g.ayah` fragment carrying its ayah key.

It does **not** duplicate the selection layer. Where a page already has a selection layer
attached, that layer is real DOM text in reading order and is the better screen-reader
surface; `annotate` marks the SVG `aria-hidden` in that case so the text is not announced
twice. Documented, and the two are tested together.

### `atlas.mjs` — cross-page lookup

A single page file cannot answer "which page is 2:255 on". `atlas.mjs` reads a small
generated index:

```json
{ "schema": "mushaf-atlas", "version": 1, "edition": "hafs-kfgqpc", "pages": 604,
  "pageFirstAyah": ["1:1", "2:1", …],
  "surahs":  [{"n":1,"ar":"الفاتحة","latin":"Al-Fatihah","en":"The Opener",
               "place":"makkah","ayahs":7,"page":1}, …],
  "juz": [{"n":1,"aid":"1:1","page":1}, …], "hizb": […], "nisf": […], "rub": […] }
```

`pageFirstAyah` is 604 entries and answers `pageOf(aid)` by binary search, because **no ayah
spans two pages** (FORMAT §12). ~30 KB raw, ~8 KB gzip. `build-atlas.py` generates it from
the real SVGs; nothing is hand-typed.

API: `loadAtlas(url)` → `pageOf(aid)`, `pageOfSurah(n)`, `surah(n)`, `findSurah(text)`,
`juz(n)`, `hizb(n)`, `rub(n)`, `nisf(n)`, `pageRange(n)`, `pagesOfJuz(n)`.

**Whether an extra data file ships alongside the SVGs is Abdullah's decision.** The library
works without it — every core method operates on the page in hand — and gains cross-page
lookup when it is present. Nothing in the core imports `atlas.mjs`.

### `view.mjs`

`scrollIntoView(page, target, {container, behavior, block})` — resolves the target's box
through the transform chain and scrolls its container. Small, and the coordinate work is
exactly what a caller gets wrong.

### `raster.mjs`

`toPngDataUrl(svgEl, {scale, background})`, `toPngBlob(…)` — serialise, `Image`, `canvas`.
Verified headless before being promised (test 12).

---

## 4. What was proposed and dropped, and why

- **`fitWidth(page, container)`** — one CSS line (`svg { width: 100% ; height: auto }`).
  A library method for it would be dressing. `fitToViewport` earns its place because it does
  arithmetic; this does not.
- **Two-page spread** — that is a reader's layout, not a page operation. Two pages side by
  side in a flex row, with `dir="rtl"` so page N+1 lands on the left. Two lines in the
  README, no API.
- **Anything keyed on `data-eid` / `data-sig`.** Explicitly not stable, explicitly not an
  identity.
- **A word-level polygon or letter API.** There is no letter segmentation and the ligature
  layer is not one (FORMAT §10.3); an API implying otherwise would be a lie.
- **A built-in translation store.** The demo's gloss join is `data-wid` → your JSON. The
  library has no opinion about whose translation it is, and shipping one would be a
  licensing question, not a technical one.
- **`page.polygons()`** — the `ayahPolygon` layer is dev-only, in a different frame, and
  approximate (FORMAT §2: 0.13% of elements sit inside a neighbouring ayah's polygon). The
  loader **removes it** by default rather than exposing it.

---

## 5. Testing

Playwright against a real browser, real page files, `python3 -m http.server`. Pages 1
(8 lines, 12 decorative rosettes, own viewBox), 42 (rubʿ rosette, 2:255), 176 (sajdah),
582 (juz 30 opens, banner + basmalah), 604 (last page, three banners). Search asserted
against exact word-id sets derived from the pages' own `data-search`. Zero console errors
asserted throughout. Results in the README and the final report — honestly, including what
does not work.

---

## 6. Findings against `FORMAT.md`

Recorded here because the plan depends on them; repeated in the final report.

1. **`data-mark-family` does not match FORMAT §6.5, and its shape CHANGED during this
   session.** FORMAT documents the vocabulary `dots, tanween, waqf, sifr, sajdah,
   reading-sign`. Three states were observed against real builds:

   | build | tanween paths carry | `[data-mark-family="tanween"]` |
   |---|---|---|
   | FORMAT.md as written | `tanween` | works |
   | build of 2026-08-29 | `diacritic` (undocumented; `tanween` never emitted) | finds nothing |
   | build of 2026-08-30 02:17 | **`diacritic tanween`** — multi-valued | finds nothing |

   So FORMAT §8.2's `data-mark-family="tanween"` and §11's family selectors are wrong
   against both builds, and the demo's `[data-mark-family="diacritic"]` — right against
   the first, undocumented — is now wrong too: the current attribute needs `~=`, not `=`.
   The registry (`mark-taxonomy.v2.json`) agrees with FORMAT, not with either emitter.
   **This is exactly why the library resolves a family through the registry to
   `data-mark` names and never selects on the attribute** — the 217-assertion suite
   passes unchanged against both builds.
2. **`data-form` is emitted but the `tanween` family was not**, so FORMAT §6.5's "only on
   the `tanween` family" was unverifiable from the attribute alone on the older build.
3. FORMAT's §11 "colour the dots differently" recipe is correct (`dots` is emitted as a
   single value); `[data-mark-family="waqf"]` is correct; the tanween and reading-sign
   families are the affected ones.
