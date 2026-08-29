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

## ⚠️ Open regression — §7 cross-line drag selection

**Restructuring §7 onto the shared hit layer broke drag-selection across a line
break, and I did not find the cause.**

- Before the refactor, verified working: a real mouse drag from line 3 into
  line 4 selected 18 words, produced exactly one `\n`, snapped to whole words,
  and the copy payload matched the highlight.
- After the refactor, a diagonal drag **collapses to a single word**. The
  selection is already collapsed *during* the drag, before any of my handlers
  run.
- A drag **within one line still works** (verified: 4 words selected).
- Bisected and **ruled out**: full-height gap-filled boxes, horizontal-only gap
  filling, and `pointer-events: none` on the ink (`q-inert`). Reverting each
  individually did not restore it. `caretRangeFromPoint` resolves correctly at
  the drag start, adjacent boxes do not overlap, `user-select` is `auto`.

The page now states this as a measured limit rather than hiding it, but the
**page's claim is wider than the evidence** — it attributes the limit to box
size, which the bisect does not support. **That sentence should be corrected or
removed when the real cause is found.** Everything else in §7 (the layer, the
payload builder, ayah numbers, the format selectors) is verified.

Because of this, two of Abdullah's §7 requests are **not delivered**: one
rectangle per line for the selection band, and easier grabbing of the first and
last word of a range. The band code (`H.bandWords`, ink extents + line pitch,
one rect per line, no overlap) is written and is used correctly by §11; it
simply has no multi-line selection to draw in §7.

---

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
| `index.html` | **927,395 B / 906 KiB** | **240,276 B / 235 KiB** |
| — inlined page | 746 KiB | — |
| — HTML/CSS/JS | 153 KiB | 47 KiB |
| `data/search-index.json` | 2.0 MiB | 473 KiB |

**This now exceeds the plan's 900 KB initial target by ~27 KB**, all of it
scaffolding from the six sections added after the original build. Over the wire
it is 235 KiB. If the budget is firm, the cheapest fix is to stop inlining the
hero page and fetch it like every other page.

## Verified

Chromium via Playwright at 360, 768 and 1280 px, light and dark:
**all 17 labs green at every width, zero console errors, zero page errors**, no
horizontal overflow (doc width 345 at 360 px), dark body `rgb(19,20,25)`, every
one of the 19 Contents entries lands with its heading clear of the sticky bar.
Live-edit, syntax-error and Reset round-trips all assert correctly.

## Still to do

- **The library section, and the per-lab `plain JS` / `library` toggle.**
  Blocked: the library has not reported done, and I was told not to invent the
  API. Read its README and DESIGN doc, copy real signatures, run every snippet.
- **Links into the published format reference** from each capability section,
  with the base URL in one place. Not started.
- **The §7 regression above.**
- The OS clipboard handoff still needs one manual check in a real browser.
- Abdullah's confirmation of the Arabic quotation and portal URL; the licence.
