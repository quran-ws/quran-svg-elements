# Demo build notes

2026-08-30. Implementation of `DEMO-PLAN.md` against the schema in
`docs/shipping/FORMAT.md`, plus the corrections Abdullah sent during the build.

**The framing.** The product is the SVG files, not the pipeline. This is a
developer landing page for those files. Nothing on the page is about audits,
defect counts, sweeps or review state. The project's rigour appears once, as a
**guarantee to the consumer** — the ink is unchanged — in the consumer's terms.

---

## How to run it

```bash
cd ~/Dev/github.com/AbdullahObaid/quran-svg-work
export QSVG_ROOT=$PWD
python3 docs/demo/build_search_index.py     # ~20 s, 604 files in parallel
python3 docs/demo/build_attrs.py            # ~1 s, the attribute measurement
python3 docs/demo/build_timings.py          # word timings for the hero page
python3 docs/demo/build.py                  # inlines the hero page
python3 -m http.server 8778 --bind 127.0.0.1
# http://127.0.0.1:8778/docs/demo/index.html
```

Port **8778**, not 8777 — `tools/review_server.py` owns 8777.

> **Hazard.** `.cache/words-svg/hafs-kfqc/` was wiped **three times** by
> something outside this work during the build (most likely
> `review_server.py`'s `clear_cache`). It is derived output; regenerate with
> `seq 1 604 | xargs -P 32 -I{} python3 tools/assign_words.py hafs/kfqc {}`
> (~35 s) before `build.py`, and always after an emitter change.

| file | what |
|---|---|
| `template.html` | source of truth — all HTML, CSS and JS. 153 KB. |
| `build.py` | inlines ONE page + the gloss + the cached timings → `index.html`. |
| `build_search_index.py` | mushaf-wide search index from the pages' own `data-search`. |
| `build_attrs.py` | **every attribute in the corpus**, with counts and sample values. Feeds the reference table, which is no longer hand-maintained. |
| `build_timings.py` | caches the hero page's word timings from quran.com. |
| `data/*.json` | search index (2.0 MiB), gloss (5 KB), timings (2 KB). |

### The hero page is 42

Ayat al-Kursi across six printed lines, a juz/hizb/rubʿ boundary and a drawn
rosette. The hero button lights **the first ayah on the page**, read from the
file (`2:253`, six fragments), never a hardcoded id.

### What `build.py` does — and the one thing it is not

Strips `<path class="ayahPolygon">` and dissolves `<g class="ligature">`.
**Those two are the production profile.** It also strips `data-eid`/`data-sig`,
which is **not** a production-profile property — `FORMAT.md` §2 and §6.5 are
explicit that both are in *both* profiles. The demo drops them for size only,
and the page's reference tail says so. An earlier draft of these notes claimed
production omits them; that was wrong and is corrected.

---

## Structure

Plain-language opening (**What this is** / **Why you would want it** / **It also
replaces your Quran metadata database**), then the live page, then provenance and
the pixel guarantee. Per Abdullah the intro ends on the capability; the scope
boundary is recorded far below in the honest-limits list as scope, not absence.

**Seventeen capability sections, every one a live editor.** One shared
`makeLab()`: the code on screen is the code that runs; it re-runs on input
(280 ms), on ⌘/Ctrl+Enter and on **Run**; **Reset** restores the snippet, every
bound control *and* the page from `PRISTINE`; each lab has its own namespaced
clone; syntax and runtime errors render in the result pane; labs build on first
intersection; CSS panes are scoped to their own lab; snippets get `svg`, `stage`,
`out`, `log`, `H` and `signal` (an `AbortSignal` fired on re-run).

| # | section | |
|---|---|---|
| 1 | Fetch a page | |
| 2 | Highlight an ayah | the several-nodes trap, shown by letting you break it |
| 3 | Tap in the gap | gap-filled hit boxes; toggle the dead zones back on |
| 4 | Band highlighting | padding slider |
| 5 | Search | plus the mushaf-wide index |
| 6 | Read a word | |
| 7 | Select and copy | drag → Ctrl+C → real text, with ayah numbers |
| 8 | Reveal word by word | grey page, ink reading position |
| 9 | **Follow a recitation** | real per-word timings from quran.com |
| 10 | Hover a word for its meaning | |
| 11 | **All of it at once** | hover + copy + band on one page |
| 12–16 | Style marks · theme · markers · leading · crop | sliders throughout |
| 17 | Metadata + reader | |

### Navigation

The old sticky bar could not hold seventeen links. Replaced with a **slim bar**
(name · current section · Contents · a 2 px progress line) and a **generated
Contents section** — 19 entries in 5 groups, each with its number, title and a
line saying what you can do after it. It is built from the document's own
headings, so renumbering cannot desync it. `scroll-margin-top: 62px` on every
section; the bar hides on scroll-down and returns on scroll-up under 600 px.

Found while testing: `id="theme"` was on **both** the masthead button and the
theme section, so the Contents link jumped to the button. Button renamed
`theme-toggle`.

---

## The shared per-word hit layer

Abdullah: *"those are demos so the dev will use them together."* So the layers
are designed to coexist rather than documented around:

```
highlight bands   behind the ink, pointer-events: none
the SVG ink       pointer-events: none
per-word hit layer   the ONLY layer that takes the pointer
```

`H.hitLayer(svg, stage, opts)` builds one absolutely-positioned span per word,
carrying its real Unicode and `data-wid`, on that word's own box. It is HTML
because native selection needs real text nodes, and that one construction then
also serves hover, tap and click. §3, §7, §10 and §11 all use it.

Two measurement notes, both of which cost real time:

- **`getBoundingClientRect()`, never `getBBox()`** — `getBBox` ignores every
  transform above the group and lands line 1 near the bottom of the page.
- **Give the span no width.** At `font-size` = box height the fallback font's
  run is far wider than the word, overflows across neighbours and steals their
  hits — a drag aimed at five words selected eighteen. Let it take its natural
  width and squeeze with `scaleX`, as PDF.js does. My first attempt kept the
  width and scaled the element, which shrank the box (43 px error); scaling a
  naturally-sized span is the working form. Worst residual **0.0156 px** over
  147 words, and **0.0155 px** after a live resize (a `ResizeObserver` rebuilds
  it — the bug the prototype had).

---

## §7 cross-line drag selection — FOUND AND FIXED

**The previous note blamed box size. That was wrong, and the bisect never
supported it.** Cross-line drag-selection was never broken, and full-height
gap-filled boxes never broke it either. Both claims are now disproved by
measurement.

**The actual cause: a `mousedown` on text that is ALREADY SELECTED does not
start a new selection — the browser begins a native drag-and-drop of the
selected text.** The old selection then sits frozen for the whole gesture and
the new drag appears to do nothing. It bites hardest on the *second* attempt,
because after `snapToWords` the previous selection covers whole words and the
words under the pointer are exactly the ones just selected. That is why it read
as "diagonal drags collapse": the reader tries again, and the retry is the
broken case.

Measured in Chromium, per-step over a 14-step drag:

| drag | words selected, step by step |
|---|---|
| clean start, within one line | 1 1 2 2 2 3 3 3 4 4 6 6 6 6 |
| clean start, across a line break | – 1 1 1 1 1 1 **13** 13 13 13 13 13 13 |
| identical drag, started inside the previous selection | **6 6 6 6 6 6 6 6 6 6 6 6 6 6** — frozen |
| clean start, across a line break, FULL-HEIGHT boxes | 1 1 1 1 1 **12** 12 12 12 12 12 12 12 12 |

**The fix is two lines in `hitLayer()`**: clear the selection on `mousedown`,
and `preventDefault()` on `dragstart`. Plus a third thing worth keeping — a
rebuild replaces every span and would destroy a live selection, so the
`ResizeObserver` now defers its rebuild while the pointer is down.

**Consequences, both now delivered.** §7 moved to the same full-height
gap-filled boxes as §3, §10 and §11, so pointing and selecting finally share
one layer *and* one box size: no dead zones in either direction, and the first
and last word of a range need no deliberate aim. And the selection band is one
rectangle per line of a **single polygon** (below).

## Highlight bands are ONE polygon, not a stack of rectangles

Abdullah, on a screenshot of 2:253 on p42: one ayah read as five stripes.

Every band on the page — the ayah band, the selection band, the hero — is now a
single `<path>` with **one subpath per printed line**, `fill-rule="nonzero"`,
all subpaths wound the same direction, and a **0.25-unit vertical overlap**
applied *only where two bands actually meet* (so a highlight on lines 3 and 9
grows no tails into the lines between them).

Two abutting antialiased edges do not add up to opaque, which is what made the
seams. `nonzero` unions the subpaths, so the overlap paints once instead of
doubling its alpha — that is what makes the overlap free.

> **`fill-rule` is set explicitly and must stay that way.** The page's own ink
> is `evenodd`, where overlapping contours inside one path CANCEL. Inherit it
> here and every overlap becomes a hole. This is the trap that filled the
> counter of a ح as a black blob, and it has now bitten this project three
> times.

Correctness is unchanged: horizontal extent from the words' INK boxes, vertical
extent from the line PITCH, behind the ink, `pointer-events: none`.

Verified on p42/2:253: before, 6 `<rect>` children and visible seams; after, 1
`<path>` child, `fill-rule="nonzero"`, 6 subpaths, no seams.

## Bidi: isolate every Arabic run inside LTR UI

Abdullah, on the ayah-number `<select>`: the ornate brackets faced outward.

**The characters were correct; the context was wrong.** U+FD3E / U+FD3F are
direction-NEUTRAL, so inside an LTR control the bidi algorithm resolves them to
the surrounding direction. So do the spaces, commas and middle dots between an
Arabic word and the Latin id beside it.

> **The rule, for anything added to this page later: any Arabic string placed
> inside LTR UI must be ISOLATED — `<bdi>` in markup, U+2067 / U+2069 where
> markup is not available. NEVER fix a bidi symptom by reordering or
> substituting characters.** The text is data and must stay exactly as the file
> has it; only the context is wrong, and the next context breaks differently.

Applied at: the `<select>` options (character-level isolation, because CSS and
`dir` are unreliable inside `<option>`), every lab readout (`out()` and `log()`
wrap Arabic runs automatically — `log()` escapes first, so this is safe), the
word tooltips in §10 and §11, the hero's text readout, the attribute table's
sample values including `data-mushaf-name-ar`, and the mushaf-wide search's
no-match message.

One deliberate exception: **the copy payload gets no isolates.** It is data
going to the clipboard, and a citation must paste as the characters the print
uses. The preview of it in the readout is isolated; the clipboard string is not.

A run must include the spaces BETWEEN Arabic words. Wrapping each word
separately leaves those spaces neutral, and two adjacent isolates in an LTR
paragraph lay out left to right — which reverses the word order.

## The attribute table is generated, not maintained

The old table listed **22 of 36** attributes and four (`data-hizb`, `data-juz`,
`data-rub-in-hizb`, `data-mark-part`) appeared nowhere on the site. A section
promising "every" and delivering 61% is worse than one that promises nothing.

`build_attrs.py` scans all 604 pages (0.9 s wall, 32 workers) and writes
`data/attrs.json`: scope, attribute, element count, distinct values and samples.
**73 rows.** The page builds the table from that file; the prose is the only
hand-written part, and an attribute with no note still gets a row saying so, so
nothing can go missing by being forgotten. There is a scope filter, and a
"production profile only" filter that hides `g.ligature`, `path.ayahPolygon`,
`data-eid` and `data-sig`.

The nine new root `<svg>` identity attributes are all there, with a callout on
the two subtle ones: the directory name is the **riwaya**, not the qiraa (Hafs
and Shuʿbah both transmit ʿĀṣim), and **6,236 is a Hafs fact, not a Quran
fact** — the Kufan count; Nāfiʿ's Madani count is 6,214.

**`data-mark-family` is a space-separated token list.** `fathatan`/`kasratan`/
`dammatan` carry `"diacritic tanween"`. All 14 exact-match selectors on the page
were rewritten to `~=`, and §12 now teaches why: `=` looks like it works,
because it still matches the six single-family marks, and drops the three
tanween without an error.

## Two versions of every example, and a library section

Every lab bar carries a **`plain JS` / `library`** switch. Both variants are
real, editable and runnable; **plain JS is the default**, because it is the
teaching and it is the argument that these files need no library. Reset restores
whichever variant is showing, never the other. All 17 labs have both.

The library (`../shipping/lib/mushaf.global.js`, 94 KB raw / 29 KB gzipped) is
fetched on the **first** switch to a library snippet, never on page load. If it
fails to load the lab says so and points at the plain version.

§18 is the dedicated library section: how to import it (module or `<script>`),
the three rules it keeps everywhere (nothing mutates a page you did not hand it;
every mutating call returns a handle with `.remove()`; the shared hit layer is
reference counted), and the two places it is deliberately stricter than the
plain snippets — it never selects on `data-mark-family`, and its hit testing is
nearest-*with-direction*.

Where the two disagree, the library ships. Two notes from building against
`API.md`:

- `page.band()` already does the one-polygon work described above, seam and
  all, and `API.md` documents it correctly. The plain-JS version on the page was
  written to match it, not the other way round.
- Two labs are CSS in the plain variant and JavaScript in the library variant
  (§12 marks, §13 theme), so `makeLab` now carries the language per variant
  rather than per lab.

## Two smaller bugs found while testing

- **§16's `to` slider was dead**, and had been. The snippet declared
  `const FROM = 1, TO = 50;` on one line, and `bindSlider` rewrites a
  `const NAME =` line — there was no `const TO`, so the control moved its own
  label and changed nothing. **Rule: one bound const per line.** Caught by
  driving every slider and asserting the textarea changed, which is the only
  test that can see it; the lab was green throughout.
- **A backtick inside a snippet ends the snippet.** The labs are template
  literals, so a `` `const NAME =` `` in a *comment* inside one closes the
  literal and takes the whole script down with a syntax error. Use quotes in
  snippet comments. This cost a build; the page went blank below the fault.

## Handoff to the format reference

Every capability section ends with one line pointing into the relevant part of
`FORMAT.md` — 19 links. **The base URL is in ONE constant**, `FORMAT_BASE` near
the top of the script, because where the spec will be published is undecided.
The anchors were generated from FORMAT.md's own headings rather than guessed.

Found while doing it: **`FORMAT.md` has two `### 6.6` headings** — "Page
identity" and "On `<g class="surah-name">`". The anchors differ so the links are
unambiguous, but the numbering is wrong and 6.7 then collides conceptually.

## The hero has five buttons and a Reset

Highlight the first ayah · hide the vowel marks · **read the text out of it** ·
**crop to one ayah** · **spread the lines**, plus Reset.

They compose in any order and each is reversible, because there is no
accumulated state: the panel holds a five-flag state object and **re-renders the
page from a clean slate on every change**. Verified — pressing all five in
forward order and in reverse order gives byte-identical DOM state, and Reset
restores the untouched page exactly. Crop is done by hiding the other words and
reframing the `viewBox`, not by replacing the element, which is what keeps it
undoable. Spread runs before crop so the crop is framed on where the ink
actually is. A `#2:255` deep link now aims every button at the linked ayah.

## Other things worth knowing

- **§9 audio.** Reciter 9 (Minshawi, Murattal), one page only, play/pause only,
  no seek. Verified live: 4 ayahs, 147 word segments, word counts agree.
  The word-count guard is kept and printed even when it passes — I re-verified
  the coordinator's figures myself: pages 1, 3, 42, 582, 604 agree exactly;
  page 254 `13:37` is 19 theirs / 20 ours. **One MP3 per ayah**, each with its
  own time origin; the highlight runs off `currentTime`, never a timeout chain.
  The fetch is bounded by `AbortSignal.timeout(6000)` — without it a bad network
  does not fail, it *hangs*, and the section sat blank forever. That was a real
  bug caught in testing.
  **This section makes external network calls** to `api.quran.com` and
  `audio.qurancdn.com` — the only part of the page that does beyond fetching
  mushaf pages. A strict CSP will need both allowed.
- **§8 reveal.** Everything greys via one selector over the ink; a medallion
  lights when its ayah's last word is reached; hizb/sajdah light with their
  ayah; the surah banner lights with the first word; the 12 decorative rosettes
  on pages 1–2 stay grey by design, since they close no ayah. Verified on page 1
  (8 lines, 29 words) as well as 42.
- **Sliders** are bound to `const NAME = <n>;` lines and rewrite the code, so
  the control and the snippet never disagree; Reset restores both. A bug found
  here: my formatter's `/\.?0+$/` strip turned **40 into 4**.
- **§15 leading** leads with the mobile case, has the device table, and a "fill
  a phone screen" preset computed from the page's own viewBox and line count —
  measured from the *printed* page, not the already-spread one (that was a bug:
  it returned 5.25 instead of 14). Verified 14 on the hero, 28.09 on page 1.

## Sizes

| | raw | gzip |
|---|---:|---:|
| `index.html` | **988,075 B / 965 KiB** | **272,203 B / 266 KiB** |
| — inlined page 42 | 745 KiB | — |
| — HTML/CSS/JS | 212 KiB | — |
| `data/search-index.json` | 2.0 MiB | 477 KiB |
| `data/attrs.json` | 15 KiB | 1.9 KiB |
| `lib/mushaf.global.js` (fetched on demand) | 91 KiB | 29 KiB |

**This is 65 KiB over the plan's 900 KiB target**, up from 906 KiB. The growth
is 17 library snippets, the library section, the generated attribute table and
the hero's three new buttons — all scaffolding, none of it the artwork.

**The fix, if the budget is firm, is to stop inlining the hero page**: it is
745 of the 965 KiB. Fetching page 42 like every other page takes `index.html` to
**~220 KiB raw / ~55 KiB gzipped**, a 4.4x reduction, at the cost of the hero
appearing one network round-trip after load instead of with the document. That
is the only change worth making; nothing else on the page is within an order of
magnitude of it. It is Abdullah's call, so it has not been done.

## Verified

Chromium via Playwright at 360, 768 and 1280 px, light and dark:
**all 17 labs green at every width, zero console errors, zero page errors**, no
horizontal overflow (doc width 345 at 360 px), dark body `rgb(19,20,25)`, every
one of the 19 Contents entries lands with its heading clear of the sticky bar.
Live-edit, syntax-error and Reset round-trips all assert correctly.

## Still to do

- **The OS clipboard handoff** still needs one manual check in a real browser.
  Everything up to the boundary is asserted — the `copy` event fires and the
  exact string handed to `clipboardData.setData` is checked — but the headless
  browser has no system clipboard, so what a real paste produces is unproven.
- **Where `FORMAT.md` will be published.** The 19 handoff links resolve against
  `FORMAT_BASE`, currently the relative `../shipping/FORMAT.md`. Served as a raw
  `.md` file a browser will not honour the `#anchor`; that only starts working
  once the spec is rendered somewhere. One constant to change.
- **`FORMAT.md` has two `### 6.6` headings** (see above). Not mine to fix.
- **`data-mark-part` appears exactly once in the whole mushaf** (p146, one path,
  value `three-dots`). It is in the table because it is emitted, with a note
  saying nothing should key on it — but somebody should decide whether it is a
  real schema attribute or a leftover.
- **Size:** 965 KiB against a 900 KiB target. See Sizes above for the one change
  that fixes it and why it needs Abdullah's word.
- Abdullah's confirmation of the Arabic quotation and portal URL; the licence.
