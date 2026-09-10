# Demo build notes

2026-08-30. Implementation of `DEMO-PLAN.md` against the schema in
`docs/shipping/FORMAT.md`, plus the corrections Abdullah sent during the build.

**The framing.** The product is the SVG files, not the pipeline. This is a
developer landing page for those files. Nothing on the page is about audits,
defect counts, sweeps or review state. The project's rigour appears once, as a
**guarantee to the consumer** — the ink is unchanged — in the consumer's terms.

---

## 2026-09-10 — `#dress`: another mushaf's ornaments on this print

Abdullah: *"add a new demo to replace/recolour assets using
https://github.com/quran-ws/quran-assets"*. One new card in **Change how it
looks**, `#dress`, `lab-dress`, on **page 604** (three surah bands, 15
medallions, 416 KB — the smallest page that exercises all three parts). It
dresses the page in a Qālūn print's ayah medallion, surah band and border while
every glyph of the KFGQPC text stays where it was printed.

### Where the ornaments come from, and why the section can look dead

`quran-ws/quran-assets` is **private**, its Pages job is deliberately off, and
every asset is `CC-BY-NC-SA-4.0`, status `provisional`, `redistributable: false`
while the publishers are asked for permission (its `LICENSE.md`, `docs/PLAN.md`
§6). So the section resolves **three sources in order** and says on screen which
one it drew:

| | |
|---|---|
| `?ornaments=<url>` | a reader or developer pointing at their own copy |
| `ornaments/` served locally, else `https://quran-ws.github.io/quran-assets/` | the full 8-mushaf set |
| `data/ornaments/` | the one style `build.py` vendors, so the section is never dead |

`docs/demo/ornaments` is a **gitignored symlink** to a local clone — make one
with `ln -s /path/to/quran-assets docs/demo/ornaments`, or point `build.py` at a
clone with `QURAN_ASSETS=`. Published, the live tier is a 404 until somebody
sets `PUBLISH_DEMO=true` on that repository, and the reader silently gets the
vendored Qālūn instead. **Abdullah chose to vendor a fallback** knowing it
copies provisional assets; `vendor_ornaments()` carries the reasoning and copies
`color.svg` only (~293 KB), never mono or line.

### The two things that were wrong the first time

**A stylesheet does not recolour these ornaments.** Every design is symmetric:
it draws one quadrant and mirrors it with `<use>`. A `<use>` instance is a
shadow copy, so `.ornaments [data-part="c2"]{fill:…}` matches the original in
`<defs>` and never reaches the four copies on screen — the colour control
appeared to do nothing at all while `getComputedStyle` on the original said the
rule had applied. The section paints the **attribute** on the original instead,
and every instance inherits it. This is the one place on the page where "a CSS
rule beats a presentation attribute" is not the answer, and the card says so.

**`input` on a colour well is one full re-run per pixel of drag** (Abdullah:
*"its so slow, no need to change color in each drag only when close the color
picker"*). `bindPartColours` now listens on `change`, so a colour costs one run,
not fifty. That is a change to the shared widget: `lab-marks` gets it too.

**Line art needs no second file** (Abdullah: *"add a check box to show it in
(Line) mode"*, then *"in that only choose one color"*). Every colour file
already carries its constant-width strokes as `<g data-part="line">`, and that
group is path-for-path identical to the published `line.svg` — checked by
hashing the `d` attributes of `ayah-markers/qalon`'s two variants. So `LINE`
drops the fill parts and keeps that one group, which also gives the tiled border
line art for free, where fetching `line.svg` would not have (`slices/` ships one
variant). One ink left means one swatch: `bindToggle` gained an `onChange` so a
toggle can rebuild the colour wells, and offering six for parts the drawing no
longer has would misdescribe what is on screen.

Two smaller ones, both measured on screen:

- Ids inside an ornament are file-local (`<g id="q">` in every marker). Two in
  one document is a duplicate id and every `<use>` then draws the first — one
  mirrored half drawn twice on the same side. `ornParse()` renames them on the
  way in.
- A page-frame **slice** carries the sliver of the text-area shape its crop cut
  through. Tiled, those slivers are four stubs in the corners: invisible while
  the slot is transparent, four coloured bars the moment anyone fills it. The
  assembled border keeps no `slot`.

### The library variant

Every lab on this page is written twice, and `#dress` is no exception: the same
result through `mushaf.js` (`loadOrnamentSet` / `set.ornaments(style)` /
`dressPage`), added 2026-09-10 when the technique moved into
`docs/shipping/lib/ornaments.mjs`. The library takes ONE base URL, so the
three-source order stays the caller's to express — which is right, since which
ornaments a page may draw is a licensing question and not something a library
should decide. `H.ORNAMENT_SOURCES` is that list, so the library snippet can
show it.

### The measurement rule, which is the actual point of the card

Nothing is placed at a fixed offset. The medallion is sized from the printed
ring's box, the band from the surah name's box, the border from the page's own
`viewBox` — so the same twenty lines land correctly on all 604 pages of a print
these ornaments were never drawn for. `H.pageBox()` is new and exists for this:
the page frame is `matrix(1.3333 0 0 -1.3333 …)` and a ring sits under a further
`scale(0.011 -0.011)`, so two raw `getBBox()` results are neither in the same
space nor the same way up. Composing the screen CTMs leaves exactly one space to
think about. Ornaments go into one `g.ornaments` at the **front** of the root,
so they render behind the print and the ayah numerals stay on top of whatever
replaced their rings.

The border is assembled from `slices/` — corner plus two repeat units, a whole
number of repeats each nudged to fit — not stretched, and the page's `viewBox`
grows by the band it added rather than the border covering a word. A frame with
no slices is scaled whole and the readout says so.

The technique is adapted from `quran-assets`' own `demo/index.html`, which
dresses a KFGQPC page the same way; the frame geometry here is derived from
`catalog.json` (`slots[0]` and `slices`) instead of that demo's extra
`data-band` / `data-frame-w` attributes, which the catalogue does not publish.

---

## 2026-09-09 — the prose rewritten against the Quran.ws writing guides

Abdullah: *"use … writing-guides.md and writing-style.md to rewrite all of the
contents of the demo pages in both languages"*, and then the standard that
outranks them: *"show first, explain second, reveal complexity only when needed,
and optimize for the developer who wants to get something working now."*

**The guides are in a private repo.** `raw.githubusercontent.com` returns 404 for
`quran-ws/guidelines`; `gh api repos/…/contents/…` reads it. Fetch the **English**
`writing-style.md` too — the Arabic §13 carries no English rules and points at it,
and the two pages are meant to state the same rule.

### Show first

The hero opened with three dense paragraphs — what it is, why you want it, the
metadata argument — before the reader saw a line of code. It now opens with one
sentence and a snippet: fetch, parse, three queries. The three annotations are
measured against `042.svg`, not illustrative:

| the snippet says | measured |
|---|---|
| `querySelectorAll('g.word').length` | **147** |
| `[data-word-key="2:255:1"].dataset.rasmUthmani` | **ٱللَّهُ** |
| `g.ayah-fragment[data-ayah-key="2:255"]` | **6** |

Re-check them if the artwork pin moves; a hero snippet that lies is worse than no
hero snippet.

### Headings name what the reader is looking for

| was | is |
|---|---|
| The trap — use `search`, never `rasm` | Searching on `rasm` matches almost nothing |
| Five things that go wrong, and what to do instead | Five problems with a selection layer, and the fix for each |
| Why building the payload yourself is the good part | Build the payload yourself, and choose the spelling at copy time |
| How they coexist | Give the pointer to one layer only |
| What this section is, and is not | Where the audio comes from |
| Honest limits | Known limits |
| 18 · A library, if you want one | A library, if you want one |

### What was cut, and why

Writing-style §3 is *state the rule, not how it was reached*. The guarantee no
longer narrates the empty-band measurement behind the 10 px seam allowance, the
library section no longer explains that each callout was once somebody's bug, and
the attribute table no longer argues that a section promising "every" and listing
two thirds is worse than one promising nothing. The rules those sentences carried
all survive; the derivations went. Two reference blobs that were one paragraph
each — the editor contract, the versioning contract — are lists, because they are
consulted rather than read.

### The Arabic rules that have no English counterpart

All applied by script over the whole file, with `<code>`, `<pre>`, `<script>`,
Quranic `span.ar` and tag attributes masked out first:

| rule | sites |
|---|---|
| tanwin al-fath before the alif (§1) — `كاملاً` → `كاملًا` | **290** |
| §10's error table — `بدون` → `دون` | 5 |
| Western digits (§1), in prose and in code comments | 2 blocks |
| a Latin word inside an Arabic sentence takes code marks, and the waw does not glue to it (§8) | 204 → 251 code runs |
| a heading that gives an order opens with a verb (§12) | `ابنِ` `اجعل` `استبدل` `أخفِ` `اقرأ` |

**Zero Quranic spans were touched by the tanwin sweep** — checked before running
it, because `اً` is a legitimate sequence in some rasm and a blind replace would
have edited the text of record.

### The trap in the pattern

**After the tanwin sweep the file writes shadda *then* tanwin** — `يّ` + `ً` + `ا`
— because that is what moving the tanwin off the alif produces. A search string
typed by hand the other way round (`ً` then `ّ`) is a different byte sequence and
matches nothing. Two replacement batches failed on exactly this, silently looking
like the text had already changed. Every batch script now normalises both halves
of every pair through one `_n()` before matching.

### Four defects found while rewriting, all older than this pass

- **`Ayahs al-Kursi`** — the terminology adoption's `ayat` → `ayahs` rule ran over
  a proper name. It is *Ayat al-Kursi*. The Arabic side (`آية الكرسي`) was never
  wrong, which is the tell: a rename that damages one language only is a rename
  that ran on text, not on meaning.
- **`a memorisation ayahKey wants`** — the same family. Something ate "aid".
- **The library is tested with 321 assertions, not 217.** `lib/test/README.md` and
  the harness both say 321; the page had never been re-measured after the suite
  grew.
- **Every `§3` / `§7` / `§10` / `§11` cross-reference resolved to nothing.** They
  are the old numbered layout's, left behind by the capability-grid restructure
  below. They are links to the cards now (`#tap`, `#select`, `#translate`,
  `#compose`, `#reveal`, `#ayah`). The `§` numbers still in *this* file, and in the
  `FORMAT.md` handoff map, are a different scheme and are correct.

### What this pass verified

Both templates build; tag balance is zero-sum on `div`/`p`/`section`/`details`/
`ul`/`li`/`figure` in both editions; no console errors on either page; the hero
snippet's three annotations re-measured against the artwork. Opening 7 cards
staged 12 labs, of which **10 ran**; `lab-meta` and `lab-ayah` reported "not run
yet" — **reproduced on the committed pre-change `index.html`**, so it is the
`IntersectionObserver` behaviour already recorded under "Still to do", not a
regression. (The commit message for this pass says "12 of 14", which counted the
staged labs rather than the ones that ran. 10 of 12 is the number.)

**The "Verified" section below predates the capability-grid restructure.** Its 12
combinations × 17 labs sweep has not been re-run since; the lab count is still
right (17 labs across 13 cards, the extras being tab panes) but nothing in it has
been re-asserted against the current text.

---

## 2026-09-09 — eighteen sections became a capability grid

Abdullah, on the page as it stood: *"many examples that are repeating itself …
we want to show the use cases in a way that a dev who visits the site sees
different capabilities without being overwhelmed."*

**What was wrong, measured.** The document was **32,896px** — about forty
screens — of eighteen numbered sections that all had the same silhouette:
eyebrow, selector line, numbered `<h2>`, paragraph, paper, editor, note. Equal
weight for everything means no weight for anything. And eighteen sections were
demonstrating five mechanisms:

| the one mechanism | the sections that each showed it again |
|---|---|
| select by `data-*`, then paint | 2 highlight · 3 hit-test · 4 band · 7 drag-copy · 11 all-at-once |
| a CSS rule beats the `fill` attribute | 12 marks · 13 theme · 14 medallions |
| iterate `g.word`, act per word | 8 reveal · 9 audio · 10 hover-gloss |
| read text and attributes off the file | 1 fetch · 5 search (twice) · 6 word · 17 metadata |
| move geometry | 15 leading · 16 crop |

**What it is now.** One `#can` section: **thirteen cards in four bands**, each a
closed `<details>` showing a drawn thumbnail, a title and one line. Opening a
card gives it the whole row, in place, with the section that used to sit inline.
**Nothing written was thrown away** — every body survives verbatim; the four
groups that were one mechanism told three times are one card with tabs
(`#ayah` + `#band`; `#style` + `#theme` + `#markers`; `#crop` + `#spacing`).
Every old anchor still resolves: a card keeps its id, a merged half becomes
`#pane-band`, and `mod('caps')` opens whatever card the hash lands in.

**32,896px → 9,173px at rest**, and the whole capability map fits on one and a
bit screens. The attribute table — 5,893px of it, 41% of what was left — is
behind a disclosure, because it is consulted, not read.

### Two bugs this uncovered, both older than the restructure

- **`dataset` was being asked for snake_case names.** Twelve sites read
  `w.dataset.rasm_uthmani`, which cannot exist: `data-rasm-uthmani` arrives as
  `dataset.rasmUthmani`. Left behind by the terminology adoption, and silent —
  words came out blank rather than throwing.
- **The sidecar reader keyed on `wordKey` where the shipped JSON writes
  `word_key`.** Every lookup missed, so `forms()` returned undefined for every
  word and the search section threw. Both spellings are accepted now, the way
  the audits learned to over `data-aya`/`data-ayah`.

### The trap in the pattern

A lab builds itself on an `IntersectionObserver`, so a card nobody opens fetches
nothing. **That observer does not fire for an element that goes from
`display:none` to laid out** — which is exactly what opening a `<details>` does.
Every card opened on an editor reading "not run yet", with no error anywhere.
`whenVisible()` takes the card's `toggle` as well; whichever signal arrives
first wins.

---

## How to run it

```bash
cd ~/Dev/github.com/AbdullahObaid/quran-svg-work
export QSVG_ROOT=$PWD
python3 docs/demo/build_search_index.py     # ~20 s, 604 files in parallel
python3 docs/demo/build_attrs.py            # ~1 s, the attribute measurement
python3 docs/demo/build_ayah_timings.py          # word timings for the hero page
python3 docs/demo/build.py                  # fills in the cached timings
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
| `build.py` | writes the gloss and inlines the cached timings → `index.html`. **Inlines no page.** |
| `build_search_index.py` | mushaf-wide search index from the pages' own `data-search`. |
| `build_attrs.py` | **every attribute in the corpus**, with counts and sample values. Feeds the reference table, which is no longer hand-maintained. |
| `build_ayah_timings.py` | caches the hero page's word timings from quran.com. |
| `data/*.json` | search index (2.0 MiB), gloss (5 KB), timings (2 KB). |

### The hero page is 42

Ayahs al-Kursi across six printed lines, a juz/hizb/rubʿ boundary and a drawn
rosette. The hero button lights **the first ayah on the page**, read from the
file (`2:253`, six fragments), never a hardcoded id.

### The hero is FETCHED, not inlined — 2026-08-30

Abdullah's call, and it is the whole size story: page 42 was **745 of the
965 KiB** `index.html` weighed. It is now fetched like every other page, and
`build.py` inlines nothing at all.

**One request, not eighteen.** The hero goes through the *same* `getPage`
memo as every lab, so page 42 is fetched once however many sections stage it.
`heroReady` is that one promise; `makeLab`'s intersection handler awaits it for
any lab that has no `cfg.page` of its own. Asserted in the browser: exactly
one request for `042.svg` per page load, on all twelve viewport/theme/language
combinations.

**The load must not read as broken**, so three things:

- The paper reserves the page's own printed proportion —
  `aspect-ratio: 345/550`, from the viewBox — so nothing reflows when the ink
  lands. Asserted: paper height identical before and after, to the pixel.
- The placeholder says what it is doing (`fetching page 42 · 794 KiB`) and, if
  the fetch fails, says *that* instead, in plain words. Never a dead area.
  Asserted by aborting `042.svg` at the network layer.
- The five buttons and Reset ship `disabled` and are enabled at the end of the
  hero module. A button that throws is worse than a button you cannot press.

**Two consequences worth knowing.** The production-profile transform moved
into the browser: `getPage` already drops `path.ayahPolygon` for every page,
and `heroReady` dissolves `g.ligature` on the hero only — the fetched pages
keep theirs, because §"Two profiles" teaches detecting the dev profile by
looking for that layer. And `data-element-id`/`data-sig` are **no longer stripped**;
that was a size saving for an inlined page and there is no inlined page. The
demo is now closer to a file you would actually download, and the parenthetical
in the reference tail that explained the stripping is gone.

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
carrying its real Unicode and `data-word-key`, on that word's own box. It is HTML
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

Abdullah, on the ayah_number `<select>`: the ornate brackets faced outward.

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
sample values including `data-riwayah-name-ar`, and the mushaf-wide search's
no-match message.

One deliberate exception: **the copy payload gets no isolates.** It is data
going to the clipboard, and a citation must paste as the characters the print
uses. The preview of it in the readout is isolated; the clipboard string is not.

A run must include the spaces BETWEEN Arabic words. Wrapping each word
separately leaves those spaces neutral, and two adjacent isolates in an LTR
paragraph lay out left to right — which reverses the word order.

## The attribute table is generated, not maintained

The old table listed **22 of 36** attributes and four (`data-hizb`, `data-juz`,
`data-rubu-al-hizb-in-hizb`, `data-mark-part`) appeared nowhere on the site. A section
promising "every" and delivering 61% is worse than one that promises nothing.

`build_attrs.py` scans all 604 pages (0.9 s wall, 32 workers) and writes
`data/attrs.json`: scope, attribute, element count, distinct values and samples.
**73 rows.** The page builds the table from that file; the prose is the only
hand-written part, and an attribute with no note still gets a row saying so, so
nothing can go missing by being forgotten. There is a scope filter, and a
"production profile only" filter that hides `g.ligature`, `path.ayahPolygon`,
`data-element-id` and `data-sig`.

The nine new root `<svg>` identity attributes are all there, with a callout on
the two subtle ones: the directory name is the **riwayah**, not the qiraah (Hafs
and Shuʿbah both transmit ʿĀṣim), and **6,236 is a Hafs fact, not a Quran
fact** — the Kufi count; Nāfiʿ's Madani count is 6,214.

**`data-mark-family` is a space-separated token list.** `tanwin_al_fath`/`tanwin_al_kasr`/
`tanwin_al_damm` carry `"diacritic tanwin"`. All 14 exact-match selectors on the page
were rewritten to `~=`, and §12 now teaches why: `=` looks like it works,
because it still matches the six single-family marks, and drops the three
tanwin without an error.

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

## Where this is published — ONE constant, and it is an ASSUMPTION

**Abdullah chose "GitHub Pages on the repo" but did not name the repo.** What is
set is `SITE_BASE = 'https://quranpedia.github.io/quran-svg/'`, and the reasoning
is written into the code beside it:

- the decomposition is to be published from **`quranpedia/quran-svg`** (Abdullah's
  decision, 2026-08-29), which is public;
- **`AbdullahObaid/quran-svg-pipeline` is private and cannot serve Pages**, so it
  cannot be the host.

**This needs confirming before the site goes up.** It is one line. Everything the
page fetches or links to derives from it:

| what | published | local checkout |
|---|---|---|
| `PAGES` | `SITE_BASE + 'pages/'` | `../../.cache/words-svg/hafs-kfqc/` |
| `FORMAT_BASE` | `SITE_BASE + 'FORMAT.html'` | `../shipping/FORMAT.md` |

The `LOCAL` branch exists so the page can still be served and *verified* out of a
checkout, where the pages are derived output under `.cache/` and the spec is still
raw Markdown. It tests `file:`, `localhost` and `127.0.0.1` only — anything else
is treated as published. **Caveat:** serving the demo over the tailnet, as
`review_server.py` is set up to be, therefore counts as "published" and the page
would try to fetch from `quranpedia.github.io`. Add the host to the `LOCAL` test
if that becomes a way you look at it. `FORMAT.html` is the name GitHub Pages gives a rendered
`FORMAT.md`, and its heading slugs are the ones these 19 anchors were generated
from, so the anchors should survive the move; that is worth one click to confirm
once the spec is actually up.

---

## Which editions are word-level, and which are ayah-level

Every page now carries **`data-decomposition`** on its root `<svg>`, and the demo
says so in three places, in both languages:

- a generated row in the attribute table (73 rows, unchanged count — the new
  attribute arrived as `data-mark-part` left);
- a short **"Two levels of decomposition"** block beside "Two profiles" in *The
  bundle*, with the one-line guard
  `if (doc.documentElement.dataset.decomposition !== 'word')`;
- the factual sentence itself: **Hafs is `word`; Warsh, Qālūn, al-Dūrī and Shuʿba
  are `ayah` today.**

Stated as a fact, not a roadmap. The point of saying it here is that a developer
arriving expecting word-level Warsh learns it from the page rather than from a
selector that matches nothing — which is the failure mode, since an `ayah` page
makes `g.word` selectors *empty*, not *wrong*.

---

## §10's English gloss on the Arabic page — relabelled, not removed

Abdullah's call: keep the mechanism, frame it as an example. So §10 is now
**"ربط أي بيانات تملكها بكل كلمة"** — joining any per-word data you already have —
and the second paragraph leads with **«وما يظهر هنا مثال، لا ميزة»**: the gloss is
word-by-word-translation-translation English from quran.com, chosen because it is open data anyone can
check, and *the point is the join, not the language*. The SVGs ship no
translations, and the page says so in both editions.

The English page said most of this already; it now leads with the same "an
example, not a feature" framing so the two editions agree.

Wording checked against the `arabic-writer` skill (`reference/01`, `reference/02`
and `technical-writing.md`) and `docs/arabic-glossary.md`. Terms reused, not
reinvented: `علامة` vs `حركة`, `الحبر` never `رسم`, `مُحدِّد`, `وضع الإنتاج`,
Western digits, `<code>` runs left in Latin.

**The brief said `.quote-en` glosses Arabic into English on the Arabic page. It
does not.** On `template.ar.html` that class carries a *modern-Arabic paraphrase*
of the KFGQPC portal's own Arabic sentence; only the class name is a leftover from
the English edition. Nothing to translate; flagging it because the name misleads.

**Two genuinely untranslated strings were found and fixed** while in there, both
in §9's Arabic snippet: `'جارٍ الجلب ' + ayahKey + ' from the CDN'` and a
`'Everything else on this page still works.'` inside an Arabic error message.

---

## §7's heading said four over five items

Counted: the list has five, and all five are real and distinct — `getBBox`, caret
placement, line-box sizing, newlines in a span, and the mousedown-on-a-selection
drag. The fifth was appended when that bug was found and the heading was never
updated. Heading corrected in both editions; no item removed.

---

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

Measured with `gzip -9` on the built files, before and after the hero stopped
being inlined. Both numbers in a row come from the same command, so the ratio
is honest even though `gzip -9` reports a little less than the figure in the
previous revision of these notes.

| | raw | gzip -9 |
|---|---:|---:|
| `index.html` **before** | 988,498 B / 965 KiB | 258,638 B / 253 KiB |
| `index.html` **after** | **227,017 B / 222 KiB** | **69,907 B / 68 KiB** |
| | **4.36x smaller** | **3.70x smaller** |
| `index.ar.html` **before** | 1,027,363 B / 1003 KiB | 268,715 B / 262 KiB |
| `index.ar.html` **after** | **266,477 B / 260 KiB** | **80,002 B / 78 KiB** |
| | **3.86x smaller** | **3.36x smaller** |
| `data/search-index.json` | 2.0 MiB | 477 KiB |
| `data/attrs.json` | 15 KiB | 1.9 KiB |
| `lib/mushaf.global.js` (fetched on demand) | 91 KiB | 29 KiB |

**Both pages are now comfortably inside the plan's 900 KiB target** — 222 KiB
and 260 KiB against it. The gzipped figure came out at 68 KiB rather than the
~55 KiB predicted: the prediction subtracted the inlined page's *raw* share
from the gzipped total, and 745 KiB of repetitive path data compresses far
better than the prose and code that remain.

The Arabic page is 39 KiB larger than the English one for the ordinary reason —
Arabic is two bytes per character in UTF-8, and the page is mostly prose.

## Verified

Chromium via Playwright. Harness: `scratchpad/verify_demo.mjs` (in the session
scratchpad, not the repo). **Twelve combinations** — `index.html` and
`index.ar.html` × 360/768/1280 px × light/dark — and in every one:

- **all 17 labs green in BOTH the `plain JS` and the `library` variant** (34
  green panes per combination, 408 in total), asserted on the result pane's own
  `ok`/`err` class rather than on its text;
- **zero console errors, zero page errors, zero failed requests**;
- **no horizontal overflow** — document scrollWidth equals the viewport at all
  three widths;
- **`042.svg` requested exactly once** per load, shared by the hero and every lab
  that stages it;
- **the hero's paper does not reflow** — identical height, to the pixel, before
  and after the page lands (480 px at 360, 1130 px at 768, 908 px at 1280);
- the fetched hero is the production profile: **zero `g.ligature`, zero
  `path.ayahPolygon`**, 147 words, `id="hero"`.

Plus the failure path, asserted by aborting `042.svg` at the network layer on
both editions: the placeholder switches to its failed style and says so, the
buttons **stay** disabled, and nothing throws.

**One harness trap worth recording.** The first version keyed "has this lab run?"
off the string `not run yet` — which is `لم يُشغَّل بعد` on the Arabic page, so all
six Arabic combinations reported green while nothing had actually run. Assert on
a class, never on user-visible text, when the text is translated.

Earlier verification, still standing: dark body `rgb(19,20,25)`, every one of the
19 Contents entries lands with its heading clear of the sticky bar, and the
live-edit, syntax-error and Reset round-trips.

## Still to do

- **The OS clipboard handoff** still needs one manual check in a real browser.
  Everything up to the boundary is asserted — the `copy` event fires and the
  exact string handed to `clipboardData.setData` is checked — but the headless
  browser has no system clipboard, so what a real paste produces is unproven.
- **The publishing host is an ASSUMPTION and needs Abdullah's word.** See
  "Where this is published" above. `SITE_BASE` is set to
  `https://quranpedia.github.io/quran-svg/` and everything — the 19 `FORMAT.md`
  handoff links and the page fetches — derives from it. If the site lands
  anywhere else it is a one-line fix.
- **`FORMAT.md` has two `### 6.6` headings** (see above). Not mine to fix.
- ~~`data-mark-part`~~ **retired 2026-08-30.** A mark is now always exactly one
  path. It is gone from the corpus (verified: zero hits across all 604 SVGs),
  `data/attrs.json` dropped it on the next `build_attrs.py` run without any
  help, and its hand-written row has been deleted from both language editions.
- **§8's lab (`lab-reveal`) does not build if you only scroll past it once.**
  Not a regression — reproduced on the pre-change `index.html` too. Building the
  labs above it grows the document, so a single top-to-bottom sweep leaves it
  below the fold and its `IntersectionObserver` never fires. A real reader
  scrolling at human speed hits it; an automated single sweep does not. The
  verification harness now sweeps repeatedly until every lab has run. Worth
  deciding whether the labs should instead build on a `requestIdleCallback`
  chain rather than purely on intersection.
- Abdullah's confirmation of the Arabic quotation and portal URL; the licence.
