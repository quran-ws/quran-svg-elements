# Demo build notes

2026-08-30. Implementation of `DEMO-PLAN.md` against the schema in
`docs/shipping/FORMAT.md`, plus the corrections Abdullah sent during the build.

**The framing this page was built to.** The product is the SVG files, not the
pipeline. This is a developer landing page for those files. Nothing on the page
is about audits, defect counts, sweeps, overrides or review state. The project's
rigour appears in exactly one place, as a **guarantee to the consumer** — the
ink is unchanged — and it is worded in the consumer's terms.

---

## How to run it

```bash
cd ~/Dev/github.com/AbdullahObaid/quran-svg-work
export QSVG_ROOT=$PWD
python3 docs/demo/build_search_index.py     # ~20 s, 604 files in parallel
python3 docs/demo/build.py                  # inlines the hero page
python3 -m http.server 8778 --bind 127.0.0.1
# http://127.0.0.1:8778/docs/demo/index.html
```

Port **8778**, not 8777 — `tools/review_server.py` owns 8777 and serves only
`/docs/defects`, so it 404s on `/docs/demo/`.

`build.py` reads `.cache/words-svg/hafs-kfqc/042.svg`. **Rebuild the page SVGs
first if the emitter has changed** (`python3 tools/assign_words.py hafs/kfqc 42`,
~1.6 s per page; all 604 in ~35 s with `xargs -P 32`). This build was made
against pages rebuilt after `data-mark-family="diacritic"` landed.

| file | what |
|---|---|
| `template.html` | the source of truth — all HTML, CSS and JS. 89 KB. |
| `build.py` | inlines ONE page into `template.html` → `index.html`; writes the gloss file. |
| `build_search_index.py` | builds the mushaf-wide search index from the pages' own `data-search`. |
| `index.html` | the built page. **Generated — edit `template.html`.** |
| `data/search-index.json` | 77,432 rows of `[wid, page, search]`. Fetched only when someone searches. |
| `data/gloss-042.json` | `{wid: [english, transliteration]}` for the hero page. quran.com data. |
| `DEMO-PLAN.md` | the brief this was built from. |

### The hero page is 42

It carries **Ayat al-Kursi (2:255)** across six printed lines, a juz boundary
(juz 3), a hizb boundary, a rubʿ boundary and a drawn `۞` rosette — so the
multi-fragment lesson, the band highlight and the metadata story all have
something real on one file. The hero's own "highlight" button lights **the first
ayah on the page**, read from the file (`2:253`, six fragments), not a
hardcoded id.

### The inlined page is the PRODUCTION profile

`build.py` converts on the way in: strips `<path class="ayahPolygon">`, dissolves
the `<g class="ligature">` wrappers, and strips `data-eid` / `data-sig`. That is
exactly what `QSVG_PROFILE=production` emits, so **every selector printed on the
page is one that ships**. 803 KB dev → 746 KB production for page 42, with no
rendered difference. Verified in the browser: 0 `data-eid`, 0 `data-sig`,
0 `g.ligature`, 0 `ayahPolygon`, 147 words, 771 marks.

Pages fetched at runtime come from the dev build in `.cache/`, so `getPage()`
removes `path.ayahPolygon` after parsing — that layer is in a different
coordinate frame, comes last in document order and swallows pointer events.

### Where pages are fetched from

One constant at the top of the script:

```js
const PAGES = '../../.cache/words-svg/hafs-kfqc/';
```

In the shipped bundle this becomes `pages/`. Everything else is path-agnostic.

---

## Structure

### The opening

Plain language first, per Abdullah's correction. Two short labelled paragraphs —
**What this is** and **Why you would want it** — with no jargon at all (no
"addressable", "semantic", "pixel-identical", "profile", "schema"), then the live
page and one obvious button. Provenance (King Fahd Complex, the Arabic quotation
character-for-character from the plan, the portal URL, an explicit
no-endorsement line) and the pixel guarantee follow **below** the demonstration,
because credibility only matters once the reader knows what is on offer.

### Every capability section is a live editor

The requirement was that the reader edits the code and sees the result
immediately. One shared `makeLab()` builds all thirteen:

- **The code on screen is the code that runs.** There is no second copy, so the
  page cannot drift into lying about itself.
- **Re-runs on input** (280 ms debounce), on <kbd>⌘/Ctrl+Enter</kbd>, and on a
  visible **Run** button.
- **Reset** restores the snippet *and* rebuilds the page from `PRISTINE`, a clone
  taken before anything on the page touches the SVG. So a reset page is the file
  exactly as loaded: no leftover rects, no changed fills, no orphaned classes.
  Verified: after editing to a broken snippet and pressing Reset, the demo is
  back to 6 fragments / 6 bands.
- **Each lab gets its own clone**, with element `id`s namespaced, so one section
  cannot corrupt another and the document never holds duplicate ids.
- **Errors are visible.** Syntax errors are caught at `AsyncFunction`
  construction, runtime errors at invocation; both render in the result pane with
  name and message. Verified: `const x = ;` → "SyntaxError Unexpected token ';'".
- **Plain `<textarea>`**, monospace, tabbable, <kbd>Escape</kbd> moves focus to
  the Run button, no focus trap. **No editor library** — the page still has no
  external dependency beyond the four Google Fonts.
- **Cost control:** the page inlines exactly ONE page SVG. Labs build themselves
  on first intersection (`IntersectionObserver`, 400 px margin), so a dozen
  copies of an 800 KB page are never in the DOM at once.
- **CSS panes** (§8 style, §9 theme) are scoped: the stylesheet's selectors are
  rewritten with the lab's own `#id` prefix before being applied. Verified: the
  dark theme preset changes the §9 page and leaves the hero at `#231f20`.

Sandbox contract, stated on the page above the first editor: a snippet gets
`svg`, `stage`, `out(html)`, `log(…)` and `H` (`band`, `clearBands`, `fold`,
`crop`, `refit`, `getPage`, `toRoot`). Everything else is plain DOM.

### The thirteen sections

| # | section | what it demonstrates |
|---|---|---|
| 1 | Fetch a page | real `fetch` + `DOMParser`, counts, text of 2:6, renders it |
| 2 | Highlight an ayah | the several-nodes trap; edit `querySelectorAll` → `querySelector` and watch 45 of 50 words go dark |
| 3 | Tap in the gap | transparent-stroke halo, live width, running hit/miss counter |
| 4 | Band highlighting | the whole `band()` function, editable padding/colour/ayah |
| 5 | Search | `data-search` with the fold; swap in `data-rasm` and the hits vanish. Plus the mushaf-wide index |
| 6 | Read a word | pointer inspector over all five text forms and the path's kind/mark/family |
| 7 | Pin a translation | 5 KB gloss joined on `data-wid`, native `<title>` tooltips |
| 8 | Style marks by meaning | live CSS; three-way specimen above it |
| 9 | **Page theme** | ink and ground as live CSS, six presets including a true dark mode |
| 10 | **Ayah markers** | ring vs numeral as separate paths: recolour, scale, swap the ring for a circle, hide all |
| 11 | **Line height** | move whole lines apart, carry the medallions with them, refit the viewBox |
| 12 | Crop | word / run of words / ayah / line from one `crop()` |
| 13 | Metadata + reader | banner, divisions, sajdah, page-turn buttons and `←`/`→` keys |

Bold = added after Abdullah's review of what the old demo had.

---

## Diacritics: hide the vowels, never the dots

Abdullah's correction, and it is now the shape of §8. Every diacritic, every
letter dot and every pause sign is a `data-kind="mark"` path, so a naive
`path[data-kind="mark"]{display:none}` deletes all three. That destroys letter
identity — ب ت ث differ by nothing but their dots — and throws away recitation
information that is not a vowel at all.

The emitter now carries `data-mark-family="diacritic"` on the nine vowel marks
(fatha, kasra, damma, sukun, shadda, maddah, fathatan, kasratan, dammatan), so
the demo uses the **one-selector** form, `[data-mark-family="diacritic"]`, both
in the hero button and in the CSS pane. The page says in so many words which
marks are kept and why.

The three-way specimen above the editor shows one printed line **as printed**,
**with the vowel marks hidden** (33 removed on that line; the letters are still
themselves) and **with every mark hidden** (53 removed; the dots went too, so
ب ت ث collapse to one shape). That last panel is the argument, made visible.

---

## The highlight is a band behind the ink

Abdullah asked for a real highlight, then for the overlap treatment, then
corrected the overlap fix. Final state:

- **One rect per printed line**, from the union of that line's word boxes,
  inserted as the **first child of `<svg>`** so it paints behind everything.
- **The ink is never touched:** no fill change, no stroke, no filter. That
  matters because "the print is unaltered" is a headline claim on the same page.
- **Boxes are converted to viewBox space** with `getScreenCTM()`, because every
  `<g class="line">` has its own frame and one layer has to hold them all.
- **Overlap is allowed.** Arabic ink overruns its line (ل ك up, ج ي down), so
  consecutive bands intersect. The geometry is *not* clamped — that was asked for
  and then withdrawn, and it is the honest shape of the ink.
- **The alpha sits on the group, not on the rects.** Opaque fills inside a
  `<g opacity=".30">` composite flat first, so an overlap is one even tone
  instead of a darker seam. Verified by eye at the hero.

One function powers the hero highlight, §2 and §4 — so the thing that replaces
the polygon layer is visibly the thing driving the headline demo.

---

## What the old demo had, and where it is now

Read from `git show 5164b52:docs/demo/template.html` in the pipeline repo.

| old section | where it is now |
|---|---|
| `#hero` — inspector (word, ligature, kind, mark, signature) | **§6 Read a word**, as a live editor. `data-sig` is deliberately not shown: it is a review instrument, not stable, and 98 signatures serve more than one mark name. The ligature row is gone with the ligature layer (production profile). |
| `#hero` — "show ayah hit regions" (`.ayahPolygon` overlay) | **Removed deliberately** (Abdullah's requirement #3). The polygon layer does not ship, and §3/§4 show what replaces it. |
| `#page` — embed a whole page | **§1 Fetch a page.** |
| `#ayah` — embed a single ayah (pad, drop marker, tight/line framing) | **§12 Crop.** Padding is a live constant; the medallion rule is better than the old toggle — a marker is kept only when its whole ayah survived the crop, so a one-word crop is no longer framed around a marker at the far end of the ayah. |
| `#words` — "pick a run of words" | **§12 Crop**, as a commented-out filter in the editor (`n >= 1 && n <= 5`). Verified live: 5 words, `ٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ`. Not a separate section, because it is the same twelve-line function with a different predicate — which is the point of that section. |
| `#colour` — recolour paper / letters / marks / dots / ayah ends / emphasis, with presets | Split in two, because they are different jobs: **§8** recolours *by meaning* (mark families and mark names), **§9** themes *the page* (ink and ground, six presets). |
| `#markers` — swap the ayah end-marker: ornament shape, size, colour, numeral | **§10 Ayah markers**, extended: ring and numeral recoloured independently, whole-medallion scale, ring replaced by a shape of your own, and markers hidden entirely for a plain reading view. |
| `#lines` — spacing: line gap, word gap, show bands | **§11 Line height.** The line-gap control is back and better (medallions are carried with their line and the viewBox refits). **Word gap dropped** on Abdullah's instruction. "Show bands" dropped — it was a debugging aid for the spacing control, not a consumer capability. |
| `#markup` — what the markup carries | **§Reference**, updated to the current vocabulary and corpus counts. |
| ornament gallery (six alternate rosettes) | Folded into §10 as the `RE_RING` swap, which teaches the mechanism instead of offering a gallery. |
| `nojs.html` — the `<view>`/`:target` script-free twin | **Dropped as a page.** 2.5 MB, inlining the same 792 KB embed three times, to make a purity point no adopting developer decides on. Recoverable from git. |

New in this version and not in the old demo: search (in-page and mushaf-wide),
ayah deep links, tap-target widening, band highlighting, translation join,
metadata + reader, provenance, the pixel guarantee, the bundle description,
honest limits, and the licence placeholder.

---

## Sizes

| | raw | gzip |
|---|---:|---:|
| **`index.html` (initial payload)** | **859,413 B / 839 KiB** | **218,227 B / 213 KiB** |
| — of which the inlined page | 746 KiB | — |
| — of which HTML/CSS/JS scaffolding | 89 KiB | 27 KiB |
| `data/search-index.json` (on demand) | 2,130,914 B / 2.0 MiB | 483,821 B / 473 KiB |
| `data/gloss-042.json` (on demand) | 5,276 B | 1,995 B |

**839 KiB initial, under the plan's 900 KB target**, ≈213 KiB over the wire.
Everything else is fetched on demand — the same technique a real consumer would
use, so the demo follows its own advice. Stripping `data-eid`/`data-sig` (which
the production profile does anyway) took 45 KB off the hero page.

---

## Verified in a real browser

Chromium via Playwright, over `python3 -m http.server`, on the built
`index.html`, at 360 px, 1280 px and 1854 px, in light and dark.

- **Console: zero errors, zero warnings** on load and after exercising every
  control and every editor.
- Every JS block is wrapped in `mod(name, fn)` with its own `try/catch`, so a
  failure in one section can never take the page down the way the old
  `template.html:637` throw did.
- **All thirteen labs run green** after scrolling the page (none left at "not run
  yet", none in the error state).
- Specifically asserted: hero lights **2:253**, 6 fragments, 6 band rects,
  `data-ayah-parts` agrees · hide-vowels uses the single family selector ·
  fetch page 3 → 127 words, 24 fragments, 698 marks, 2:6's text read back
  correctly · `querySelectorAll`→`querySelector` edit gives 5 of 50 words and one
  band · syntax error reported, Reset restores 6/6 · tap with halo on resolves
  `2:253:37` → ayah 2:253 line 5, computed stroke `rgba(0,0,0,0)` at 1.6 ·
  in-page search `الله` → 7 hits · mushaf-wide `ننجي` → 5 words on 5 pages, page
  219 fetched and marked · gloss join **147/147** · marker lab: 4 rings replaced
  by 4 circles with 4 numerals intact, `HIDE_ALL` hides them · line height 6 → 14
  units grows the viewBox `663.35` → `812.68` and carries 4 medallions · crop of
  a word run → 5 words · theme preset "dark" gives ink `rgb(230,226,214)` on
  ground `rgb(20,22,27)` **and does not leak** into the hero (`rgb(35,31,32)`).
- **Responsive:** at 360 px the document scroll width is 345 px — no horizontal
  page scroll. The only overflow is inside `overflow-x:auto` containers (the
  sticky nav, the tables, the code panes), by design.
- **Dark mode:** body resolves to `rgb(19,20,25)`; the mushaf paper stays light
  in both themes, as a page of a mushaf should.
- **Keyboard:** all controls native and tabbable; the editors are plain
  textareas; <kbd>Escape</kbd> leaves an editor without trapping focus; the
  reader turns pages with `←`/`→` (left turns forward, the way the book does).

Numbers printed on the page are computed live wherever they describe the hero
page, so they cannot drift from the file.

---

## Measurements taken for this page

| claim on the page | how it was measured |
|---|---|
| `الله` 2 in `data-rasm` vs 2,555 in `data-search` | substring over both attributes, all 604 pages |
| `الذين` 0 → 999, `درجات` 0 → 14 | same |
| page 42: 794 KiB raw / 197 KiB gzipped, 771 named marks | `stat` + `gzip -c9`, regex count |
| gloss join 147/147 | `.cache/words/page-042.json` joined to `042.svg` on `wid` |
| search index 77,432 rows, 2.0 MiB / 473 KiB gz | `build_search_index.py` |

Everything else — corpus counts, mark totals, bundle sizes, special cases — is
quoted from `docs/shipping/FORMAT.md` §12 and `SHIPPED-ARTIFACT-2026-08-29.md`
§5, which are themselves whole-corpus measurements.

---

## Deliberately not stated on the page

- **No licence terms anywhere.** The bundle section carries a clearly-marked
  "terms to follow" placeholder and an explicit sentence that nothing on the page
  grants any rights. Provenance is stated; permission is not.
- **No claim of endorsement or affiliation** with the King Fahd Complex — said
  once in the provenance block and again in the footer.
- **The pixel guarantee is never blurred with the semantic labelling.** Separate
  paragraphs, and the second says so.
- **No accuracy comparison against another decomposition.** The plan flagged that
  the two candidate figures (77,417/77,422 words vs 67,761/67,765 for line
  placement) measure different things and neither should go out unchecked.
  Neither appears.

## Left as prose, on purpose

The bundle table, the two profiles, versioning, browser support, the honest
limits and the licence placeholder have no editor. They are the reference tail:
there is nothing to run, and an editor there would be decoration.

## To check before this is public

1. **The Arabic quotation and the portal URL** were copied character-for-character
   from `DEMO-PLAN.md` §A1, which asks for Abdullah's confirmation of both. That
   confirmation has not happened.
2. **The licence placeholder** is fine for a preview and not for a launch.
3. **`PAGES` must be repointed** at the real hosting path, and
   `data/search-index.json` and `data/gloss-042.json` need real URLs, before the
   page can be served anywhere but this machine.
4. **Accessibility is reported as "not yet"** on the page. If a
   `<title>`-per-word build flag lands, that row and that limit both change — and
   §7 already shows the code that does it.

## Not done

- **No two-page reader spread.** §13 is a single page with turn buttons and keys;
  a right/left spread was cut to keep one heavy page in the DOM at a time. It is
  the one headline item from the plan that is not built.
- **No source-vs-render overlay** (plan §2.9). It needs the *source* artwork page
  shipped beside the decomposed one, and the plan is explicit that an in-browser
  difference must never be presented as the audit's number. Left out rather than
  done loosely.
- **No automated snippet-execution gate** (plan §5, "every sample runs"). Making
  every snippet live removes most of the risk — a broken snippet now shows its
  error to the reader rather than silently displaying dead code — but nothing
  yet fails a build when the schema moves. That harness is the most valuable
  follow-up.
- **Word spacing** was dropped from §11 on Abdullah's instruction; only line
  height is built.
