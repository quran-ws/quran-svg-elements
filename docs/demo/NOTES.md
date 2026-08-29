# Demo build notes

2026-08-30. Implementation of `DEMO-PLAN.md` against the schema in
`docs/shipping/FORMAT.md`, plus the corrections Abdullah sent during the build.

**The framing.** The product is the SVG files, not the pipeline. This is a
developer landing page for those files. Nothing on the page is about audits,
defect counts, sweeps or review state. The project's rigour appears in one
place, as a **guarantee to the consumer** — the ink is unchanged — worded in the
consumer's terms.

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
`/docs/defects`.

> **Hazard.** `.cache/words-svg/hafs-kfqc/` was wiped twice by something outside
> this work while I was building (most likely `review_server.py`'s
> `clear_cache`). It is derived output; regenerate with
> `seq 1 604 | xargs -P 32 -I{} python3 tools/assign_words.py hafs/kfqc {}`
> (~35 s) before running `build.py`, and **always** after an emitter change.

| file | what |
|---|---|
| `template.html` | the source of truth — all HTML, CSS and JS. 118 KB. |
| `build.py` | inlines ONE page into `template.html` → `index.html`; writes the gloss file. |
| `build_search_index.py` | builds the mushaf-wide search index from the pages' own `data-search`. |
| `index.html` | the built page. **Generated — edit `template.html`.** |
| `data/search-index.json` | 77,432 rows of `[wid, page, search]`. Fetched only on the first search. |
| `data/gloss-042.json` | `{wid: [english, transliteration]}` for the hero page. quran.com data. |
| `DEMO-PLAN.md` | the brief this was built from. |

`parts/selection-prototype.html` was folded into §7 and deleted; nothing else
lives outside the files above.

### The hero page is 42

It carries **Ayat al-Kursi (2:255)** across six printed lines, a juz boundary, a
hizb boundary, a rubʿ boundary and a drawn `۞` rosette. The hero's own button
highlights **the first ayah on the page**, read from the file (`2:253`, six
fragments), never a hardcoded id.

### What `build.py` does to the inlined page — and the one thing it is not

It strips `<path class="ayahPolygon">` and dissolves the `<g class="ligature">`
wrappers. **Those two are the production profile**, so every selector on the page
is one that ships.

It also strips `data-eid` / `data-sig`, and **that is not a production-profile
property.** `FORMAT.md` §2 and §6.5 are explicit that both attributes are present
in *both* profiles; a shipped production page still carries them. The demo drops
them purely for size (~45 KB on this page) and reads neither. An earlier draft of
these notes and of `build.py` claimed production omits them — corrected, and the
page's reference tail now states plainly that both profiles carry them and that
the inlined page has them stripped.

---

## Structure

### The opening

Plain language, no jargon: **What this is**, **Why you would want it**, and
**It also replaces your Quran metadata database** — the field inventory, the
"CSS selector, not a query" line, and the point that geometry is the thing a
database cannot give you. Per Abdullah's follow-up the intro **ends on the
capability**; the scope boundary (translation, tafsir, audio, timings,
transliteration, ruku, manzil) is recorded far below in the honest-limits list,
phrased as scope rather than absence.

Provenance (King Fahd Complex, the Arabic quotation character-for-character from
the plan, the portal URL, an explicit no-endorsement line) and the pixel
guarantee follow the live page, not precede it.

### Fifteen capability sections, every one a live editor

One shared `makeLab()`:

- **The code on screen is the code that runs.** No second copy.
- Re-runs on input (280 ms debounce), on <kbd>⌘/Ctrl+Enter</kbd>, and on **Run**.
- **Reset** restores the snippet, every bound control, *and* the page — rebuilt
  from `PRISTINE`, a clone taken before anything touches the SVG.
- Each lab gets its own clone with namespaced ids; nothing leaks between labs.
- Syntax and runtime errors render in the result pane with name and message.
- Plain `<textarea>`; <kbd>Escape</kbd> leaves it. **No editor library.**
- Labs build on first intersection, so a dozen 800 KB pages are never in the DOM.
- CSS panes are scoped by rewriting selectors with the lab's own `#id`.
- A snippet gets `svg`, `stage`, `out`, `log`, `H` and **`signal`** — an
  `AbortSignal` fired on re-run, so document listeners and observers a snippet
  attaches are torn down instead of piling up.

| # | section | what it demonstrates |
|---|---|---|
| 1 | Fetch a page | real `fetch` + `DOMParser`, counts, text of 2:6 |
| 2 | Highlight an ayah | the several-nodes trap; break it and watch 45 of 50 words go dark |
| 3 | Tap in the gap | transparent-stroke halo, live width, hit/miss counter |
| 4 | Band highlighting | the whole function; **padding slider** |
| 5 | Search | `data-search` with the fold; plus the mushaf-wide index |
| 6 | Read a word | pointer inspector over all five text forms |
| 7 | **Select and copy** | drag, Ctrl+C or right-click → real Quranic text |
| 8 | **Reveal word by word** | grey page, ink reading position, animated advance |
| 9 | Pin a translation | 5 KB gloss joined on `data-wid`, native `<title>` |
| 10 | Style marks by meaning | live CSS; three-way specimen above it |
| 11 | Page theme | ink and ground as live CSS, six presets |
| 12 | Swap ayah markers | ring vs numeral; **scale slider**, swap and hide toggles |
| 13 | Open up the leading | **line-gap slider** + "fill a phone screen" |
| 14 | Crop | **from / to / padding sliders** |
| 15 | Metadata + reader | banner, divisions, sajdah, page-turn |

---

## §7 · Select and copy — integrated from the coordinator's prototype

The mechanism is the prototype's and was not redesigned: a PDF.js-style text
layer, one absolutely-positioned `<span>` per `g.word` carrying the real Unicode,
painted `color: transparent` over the word's own rendered box. The four traps the
coordinator listed are all respected and all written up on the page:
`getBoundingClientRect()` not `getBBox()`; snap the range out to whole spans on
`mouseup`; size to the **word**, not the line; and build the clipboard payload in
a `copy` handler rather than putting newlines in spans.

**The featured part** is that the payload is looked up from `data-wid`, so one
drag yields uthmani, imlaei or the bare search form. The live readout shows all
three at once, and a `copy as` selector in the toolbar rewrites the `WHICH` line
in the snippet — so the control and the code never disagree.

Two things I added beyond the prototype:

1. **Rebuild on resize.** The layer is measured in screen pixels, so a
   `ResizeObserver` rebuilds it, torn down via `signal`. This was the real bug
   the coordinator flagged. Verified: worst misalignment 0.0156 px at 1280 px and
   **0.0155 px at 900 px** after a live resize.
2. **A defect the prototype had, found by driving a real mouse.** With
   `font-size` set to the box *height* and an explicit `width`, the fallback
   font's run is far wider than the box and overflows across neighbouring lines,
   stealing their hits — a drag aimed at five words on line 3 selected eighteen
   words on lines 2–3. The fix is what PDF.js actually does: give the span **no
   width**, let it take its natural width, then `transform: scaleX(target /
   natural)` with `transform-origin: left top`. My first attempt at this kept the
   explicit width and scaled the whole element, which shrank the box (worst error
   43.3 px) — the working form scales a naturally-sized span. After the fix a real
   drag selects **exactly** the words aimed at, excludes both neighbours, and the
   payload matches the highlight.

**Not verified:** the handoff to the OS clipboard. This headless Chromium has no
clipboard backing. The `copy` event, `preventDefault`, and the exact payload are
tested; the page says so in as many words and claims nothing more. **Please check
Ctrl+C and right-click → Copy by hand in a real browser once.**

## §8 · Reveal word by word

Every word grey, the reading position full ink, the boundary advancing with a
fade. The colour is set on the **group**, and one CSS rule
(`.q-reveal g.word path { fill: inherit }`) hands each path back to it — needed
because every ink path ships `fill="#231f20"` as a presentation attribute, and a
rule beats one. So a tick sets one property on one element, and the browser
interpolates; transitioning `fill` stays smooth without touching 1,061 paths.

The advance is driven by a **pluggable `schedule(i)`** returning a millisecond
per word. Today a constant tempo; an array of per-word times from a recitation
aligner drops in unchanged. **No audio anywhere**, and the page says outright
that the animation is a metronome and is not synced to a recitation — only that
`data-wid` is the key such datasets are published under. Transport (play/pause,
scrubber) is built by the snippet itself; speed, lit-count and a by-ayah toggle
are toolbar controls. `prefers-reduced-motion` disables the transition.

Verified on the hero (147 words, advance, pause, scrub-to-end lights the last
word) and on **page 1** — 8 lines, the different opening-spread viewBox, 29
words, `1:1:1` → `1:7:9`, first ink and second grey.

## Sliders — restored, and wired to the code

Abdullah reported the lost line-height slider. Rather than replace the editors, a
`bindSlider()` helper writes the number into a `const NAME = <n>;` line in the
snippet and re-runs, rAF-throttled; `bindToggle()` does the same for booleans.
The reader sees the effect **and** the line that produced it, which is strictly
better than the old demo, where the slider existed and the code did not. Reset
puts every control back with the code.

| control | range | old demo |
|---|---|---|
| §13 line gap | 0–**18**, step 0.25 | `#lh` 0–10 — the old maximum could not reach the phone value |
| §12 marker scale | 0.5–1.8, step 0.05 | `#mk-size`, same range |
| §14 crop padding | 0–20, step 1 | `#ayah-pad`, same range |
| §14 from / to | 1–50, step 1 | `#w-from` / `#w-to` number inputs |
| §4 band padding | 0–6, step 0.2 | new |
| §8 ms/word, lit | 90–1200 / 1–12 | new |

A second defect found here: my number formatter stripped trailing zeros with
`/\.?0+$/`, which turned a slider value of **40 into 4**. Fixed with
`String(+(+v).toFixed(d))` and re-verified (`FROM = 40` → 11 words).

## §13 · The mobile case

Leads with it now, because it is why most developers will care. The page is
345 × 550; a phone is far narrower for its height, so fitting to width leaves
about a quarter of the screen empty. The device table is on the page. A **"fill a
phone screen"** button computes the gap from the page's own `viewBox` and line
count — measured from the *printed* page, not the already-spread one, which was a
bug in my first attempt (it read the grown viewBox and returned 5.25 instead of
14). Verified: **GAP 14** on the 15-line hero, matching the coordinator's figure,
and the same formula gives **28.09** on page 1, correctly, because 8 lines share
the space over 7 gaps. The page says in as many words to derive the gap from the
page and never from a constant.

---

## What the old demo had, and where it is now

Re-derived from `git show 5164b52:docs/demo/template.html` by enumerating every
`<button>`, `<input>` and `<select>` in it — not from my earlier notes, which
recorded the line-gap slider as restored when it was not.

| old control | old section | status now |
|---|---|---|
| `#hits` — ayah hit-region overlay | inspector | **Removed deliberately.** The polygon layer does not ship; §3 and §4 are what replaces it. |
| hover inspector | `#hero` | §6, as a live editor. `data-sig` deliberately not surfaced; the ligature row went with the ligature layer. |
| — embed a whole page | `#page` | §1. |
| `#ayah-pad` | embed an ayah | **Restored**, §14 padding slider, same 0–20/step 1. |
| `#ayah-marker` (drop the marker) | embed an ayah | **Superseded, not restored.** `crop()` now keeps a medallion only when its whole ayah survived, which is right in both directions without a toggle. |
| `#ayah-frame` (tight vs line width) | embed an ayah | **Not restored.** Genuinely lost; the crop always frames the kept ink. |
| `#w-ayah`, `#w-from`, `#w-to` | embed part of an ayah | **Restored**, §14, as `AID` + from/to sliders driving the same snippet. |
| `#c-paper` | recolour | §11 page theme. |
| `#c-body`, `#c-mark`, `#c-dots` | recolour | §10, as live CSS. |
| `#c-marker` | recolour | §12 (`RING` / `NUMBER`, now independently). |
| `#c-focus`, `#c-focus-col` (emphasis) | recolour | **Superseded** by the band highlight in §2/§4, which is more accurate than dimming. |
| `#mk-size` | ayah markers | **Restored**, §12 slider, same range. |
| `#mk-col`, `#mk-num` | ayah markers | §12, `RING` and `NUMBER`. |
| ornament gallery | ayah markers | Folded into §12's `RE_RING` swap, which teaches the mechanism. |
| `#lh` line gap | spacing | **Restored and extended**, §13, 0–18 with the phone preset. |
| `#wg` word gap | spacing | **Dropped on Abdullah's instruction.** |
| `#lh-bands` | spacing | Dropped — a debugging aid for the old slider, not a consumer capability. |
| — the markup table | `#markup` | §Reference, updated to the current vocabulary. |
| `nojs.html` | separate page | **Dropped.** 2.5 MB inlining one embed three times. Recoverable from git. |

New and not in the old demo: search (page and mushaf-wide), ayah deep links, tap
targets, band highlighting, **select and copy**, **reveal word by word**,
translation join, metadata + reader, provenance, the pixel guarantee, the bundle,
honest limits, and the licence placeholder.

---

## Sizes

| | raw | gzip |
|---|---:|---:|
| **`index.html` (initial payload)** | **888,719 B / 868 KiB** | **227,998 B / 223 KiB** |
| — of which the inlined page | 746 KiB | — |
| — of which HTML/CSS/JS | 118 KiB | 36 KiB |
| `data/search-index.json` (on demand) | 2.0 MiB | 473 KiB |
| `data/gloss-042.json` (on demand) | 5,276 B | 1,995 B |

**868 KiB initial, under the plan's 900 KB target.** Everything else fetched on
demand.

---

## Verified in a real browser

Chromium via Playwright over `python3 -m http.server`, on the built `index.html`,
at 360, 900 and 1280 px, light and dark.

- **Console: zero errors, zero warnings** on load and after exercising every
  control and every editor.
- **All fifteen labs green** after a full scroll — none left at "not run yet",
  none in the error state. (Two intermediate runs showed one lab unbuilt; both
  were my test scrolling faster than the smooth-scroll animation, not the page.)
- Live-edit round trip: editing §2 to `querySelector` gives 5 of 50 words and one
  band; `const x = ;` reports "SyntaxError Unexpected token ';'"; **Reset**
  restores 6 fragments, 6 bands, the default code and every slider position.
- §7: 147 spans for 147 words · worst box misalignment **0.0156 px** (1280 px)
  and **0.0155 px** after resizing to 900 px · a **real mouse drag** selects
  exactly the five words aimed at, excludes both neighbours, snaps out to element
  boundaries · a drag across a line break yields 18 words and exactly **one**
  newline · `copy` fires, `defaultPrevented` true, payload matches the readout.
- §8: fade is `fill 0.22s` on paths inheriting from the group · advance, pause and
  scrub-to-end all work · verified on page 1 as well as the hero.
- §13: "fill a phone screen" → GAP **14**; page 1 gives **28.09** from 8 lines.
- §14: `FROM = 40` → 11 words, `2:255:40..50`.
- §11 theme: dark preset gives ink `rgb(230,226,214)` on `rgb(20,22,27)` and does
  **not** leak into the hero (`rgb(35,31,32)`).
- §12: `RE_RING` replaces 4 rings with 4 circles and keeps 4 numerals;
  `HIDE_ALL` hides them.
- Inlined page: 0 `data-eid`, 0 `data-sig`, 0 `g.ligature`, 0 `ayahPolygon`,
  147 words, 771 marks.
- Responsive: at 360 px document scroll width is 345 px; no overflow outside the
  `overflow-x:auto` containers.
- Keyboard: all controls native; editors are plain textareas; the reader turns
  pages with `←`/`→` (left turns forward, as the book does).

---

## Deliberately not stated on the page

- **No licence terms anywhere** — a marked "terms to follow" placeholder and an
  explicit sentence that nothing on the page grants rights.
- **No claim of endorsement or affiliation** with the King Fahd Complex.
- **The pixel guarantee is never blurred with the semantic labelling.**
- **No accuracy comparison against another decomposition** — the two candidate
  figures measure different things and neither should go out unchecked.
- **Nothing implying audio sync**, per §8.

## To check before this is public

1. **Ctrl+C and right-click → Copy by hand in a real browser** (§7). The OS
   clipboard handoff is the one step no automated test here could cover.
2. **The Arabic quotation and the portal URL** still need Abdullah's confirmation.
3. **The licence placeholder** is fine for a preview, not for a launch.
4. **`PAGES` must be repointed** at the real hosting path, and the two `data/`
   files need real URLs.
5. Whether production *should* strip `data-eid`/`data-sig` is with Abdullah; if
   he decides it should, the reference-tail wording changes.

## Not done

- **No two-page reader spread.** §15 is a single page with turn buttons.
- **No source-vs-render overlay** (plan §2.9).
- **No automated snippet-execution gate.** Live editors mean a broken snippet
  shows its error to the reader rather than silently displaying dead code, but
  nothing yet fails a build when the schema moves. Still the most valuable
  follow-up.
- **Word spacing** dropped from §13 on instruction; **`#ayah-frame`** not
  restored.
