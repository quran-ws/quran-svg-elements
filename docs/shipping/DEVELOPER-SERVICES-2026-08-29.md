# Developer services — a hosted SVG delivery and rendering layer

2026-08-29. **Design and analysis only.** Nothing here changes the pipeline.
The one proof of concept beside it — `docs/shipping/poc/ayah_crop_poc.py` —
only reads pages and writes crops into `docs/shipping/poc/out/`.

**Scope, from Abdullah, twice narrowed:**

1. *"the hosted services are an addition to the file bundle — NOT an
   alternative."* The bundle in `SHIPPED-ARTIFACT-2026-08-29.md` ships
   regardless. The question here is only: **given that anyone can download the
   files, what does a hosted service add that downloading cannot?**
2. *"I meant like the api for embedding an ayah."* and *"all for svgs — not
   quran api for anything else."*

So this is an **SVG delivery and rendering service**. It serves ink. It is not
a Quran API. Verse text as JSON, translations, tafsir, audio, morphology and
search-as-a-service are all explicitly out of scope — §2 says what to use
instead and why that is a feature.

Everything measured against `.cache/words-svg/hafs-kfqc/` as built 2026-08-29
21:17 (604 pages, 454.1 MiB). Every number names the command that produced it
(appendix).

---

## 0. Executive summary

1. **The flagship earns its place, and it is smaller than it looks.** An ayah
   embed endpoint is real work a consumer should not have to do: crop a
   multi-line ayah out of a page, compose three transforms through a negative
   y-scale, and hand back a standalone SVG. I built it and it works — §3.3,
   with `2:255` and `112:1` rendered as proof.
2. **A fact that collapses the hard case: no ayah crosses a page boundary.**
   Verified two ways — every one of the 6,236 `data-aid` values appears on
   exactly one page in our SVGs, and independently in the DigitalKhatt layout
   DB (`.cache/dk_lines.json`), 6,236/6,236 single-page. So `/ayah/{s}:{a}` is
   always one page, one crop, no stitching. Only *ranges* can span pages, and
   only at 603 of 6,235 adjacent-ayah boundaries (9.7 %). §3.3.
3. **Pre-generating every ayah SVG is affordable and is the right default.**
   Measured over 300 real crops: mean 67.8 KiB raw / 14.5 KiB brotli →
   **413 MiB raw / 88 MiB brotli for all 6,236**, about 14 single-core minutes
   to build. That makes the flagship a **CDN path, not a server**. §3.5.
4. **Pre-generating every WORD loses.** 77,432 word crops measure
   **451 MiB raw / 149 MiB brotli** — more than the entire page corpus
   (70 MiB brotli) for the least-wanted granularity. Words stay dynamic, or
   better, client-side. §4.
5. **PNG is the one genuinely additive computation, and it is cheap.** Measured
   over 60 ayah crops: `rsvg-convert -w 800` takes **62 ms mean** (153 ms max)
   and produces **55 KiB mean, 14.0 KiB after 8-bit quantisation** — the same
   bandwidth as the brotli SVG. 1M PNG renders/month is 17 core-hours
   *uncached*; at a normal CDN hit rate it is under two. §3.7, §6.
6. **Our edge survives contact with the ecosystem, in a narrowed form.** The
   defensible claim is **not** "nobody has mark-level SVG" (MushafDatabase
   does) and **not** "nobody renders the Madani page pixel-exactly" (the QPC
   per-page fonts do, at 15–190 KB/page, and they are excellent). It is:
   **nobody serves mushaf page geometry over HTTP at all, and nothing anywhere
   returns a cropped region of the real print on demand.** §2.
7. **The whole service surface is four endpoints.** Ayah, word, page, range —
   plus `.png` on each. Everything else I considered is rejected in §5 with
   reasons, mostly "the bundle already does that" or "that is quran.com's job".
8. **One blocker is fatal to the flagship and it is already known.** The
   ayah-marker `data-aid` is reversed on 441 of 604 pages
   (`SHIPPED-ARTIFACT-2026-08-29.md` §8.1). I hit it directly: cropping `112:1`
   *with* its marker gives a box spanning the whole page (86.5–336.0 ×
   76.3–547.4) instead of the correct one-line box (238.1–336.0 × 76.3–115.5),
   and the `2:255` crop draws a marker reading ٢٥٤. **The embed endpoint cannot
   ship until that is fixed.** §7.
9. **Cost is not the interesting constraint.** At 1M ayah requests/month the
   service moves ~14 GB and burns a couple of core-hours. The interesting
   constraint is **the promise**: once a developer pastes `<img src="…">` into
   a page, the URL must never change and the ink behind it must never change.
   §6.3 says how versioning ties the service to the bundle so a consumer mixing
   both cannot get a mismatch.

---

## 1. The test every service has to pass

Because the bundle ships anyway, "useful" is not enough. Each candidate is
classified twice.

**Delivery class** (the coordinator's original axis):

- **static** — a file that exists; serving it is a file server's job;
- **pre-generated static** — a file that does not exist yet but could be built
  once, offline, and then served as static;
- **dynamic** — must be computed per request, because the parameter space is
  too large to enumerate.

**Justification class** (the axis that actually decides):

- **(a) the bundle already covers it** → do not build it;
- **(b) thin CDN convenience over the same files** → must beat "put the GitHub
  repo behind jsDelivr", which costs nothing and is already how this ecosystem
  distributes data (verified: qpc-fonts, quranpedia/quran-svg and
  MushafDatabase are all served that way today);
- **(c) genuinely additive computation** → the service does work the consumer
  would otherwise have to do, or produces something too large to ship.

Only **(b)** and **(c)** are proposed. Everything that landed in **(a)** is in
§5, because a short list of rejected ideas with reasons is more useful than a
long list of endpoints.

---

## 2. What we are not, and what to use instead

This section belongs verbatim in the service's own README. It is a feature, not
an apology.

We serve **ink**. For everything else the ecosystem is already good, and our
keys join to it for free.

| you need | use | how it joins to us |
|---|---|---|
| verse text, translations, tafsir, transliteration | Quran Foundation API (`apis.quran.foundation/content/api/v4`) | `data-aid` = their verse key; `data-wid` = their `location` |
| word morphology, roots, grammar | quranic-corpus-derived datasets | `data-wid` |
| audio, per-word timings | `audio.quran.com`, `quran-align` | `data-aid` / `data-wid` |
| full-text search | `alfanous`, or the bundle's `words.json` | resolves to a `data-wid`, which is a URL here |

**The interoperability fact this rests on** (verified in
`SHIPPED-ARTIFACT-2026-08-29.md` §6b, and re-confirmed here against the
DigitalKhatt word table): `data-wid` is quran.com's word key exactly — 1:1 = 4
words, 2:255 = 50, 77,432 in the corpus, and
`.cache/digitalkhatt/digital-khatt-v2.db` uses the identical `location` string
(`'1:1:1'`). **No mapping table exists because none is needed.** They are the
data half; we are the rendering half; the join is free.

### Testing the "nobody else does this" claim

Researched 2026-08-29 across the hosted APIs, the font route, and the image
datasets. The claim as originally stated is **too strong in two places** and
should be narrowed before it goes on a landing page.

| the thing | who has it | verdict on our claim |
|---|---|---|
| pixel-exact Madani page rendering | **the QPC per-page fonts** — one font per page, each *word* a PUA glyph. KFGQPC originated it; `nuqayah/qpc-fonts`, quran.com's CDN and effectively every serious mushaf app ship it. Measured 15–83 KB/page (v1 woff2), 41–190 KB (v2 woff2) | **We are not first, and we are 1–3× larger per page** (119 KiB brotli). Do not claim exclusivity here. Claim the *addressability* instead. |
| mark-level SVG decomposition | **MushafDatabase-Ligature-Based-SVG** — 604 SVGs decomposed to lines/words/ligatures/diacritics | **Exists.** Narrow the claim from "nobody has it" to "nobody *serves* it". |
| per-word geometry, served | nobody. The closest is `ayahinfo_{width}.db` (`quran/ayah-detection`), a downloadable SQLite of `min_x/max_x/min_y/max_y` per word — **axis-aligned rectangles, bound to one raster width, nothing below the word**, distributed as a 2.2 MB zip | **True and defensible.** |
| a hosted endpoint returning page geometry | **none.** quran.com's API returns `page_number`, `line_number`, `position`, `code_v1/v2` — ordinals and font codepoints, never coordinates. DigitalKhatt has no HTTP API at all (its `/api/*` paths return the Angular shell) | **True.** |
| an on-demand render of an arbitrary ayah or range as image/SVG | **none.** The entire category is one pre-rendered fixed PNG set: `cdn.islamic.network/quran/images/{s}_{a}.png` (2_255.png = 16 KB; high-resolution = 41 KB). Fixed set, no ranges, no recolouring, no geometry, and it is not this print's decomposed ink | **True, and this is the flagship's whole justification.** |

**The defensible sentence**, and it should be the landing page's first line:

> The KFGQPC Madani page as vector ink, addressable down to the mark, with any
> ayah, word, range or page croppable to its own SVG or PNG by URL. Nobody
> serves mushaf geometry over HTTP; nothing anywhere returns a cropped region
> of the real print on demand.

**Be fair about the fonts in the docs.** They are tiny, universally supported,
free, and text selection falls out of the DOM. What they cannot do is the
entire reason to use us: a word is one indivisible glyph, so there is no
selecting, colouring or querying a shadda, a fatha, a waqf sign or a letter;
no geometry comes from the server; and cropping "just 2:255" means measuring
shaped text yourself. Say that plainly rather than pretending we replace them.

---

## 3. The flagship — the ayah embed endpoint

> A developer pastes one URL and gets the ayah in the real KFGQPC print. No
> download, no build step, no SVG knowledge, no font to install.

### 3.1 The URL

**Canonical form:**

```
https://<host>/v1/ayah/2:255.svg
https://<host>/v1/ayah/2:255.png
```

Full surface:

| path | returns |
|---|---|
| `/v1/ayah/2:255.svg` | one ayah, cropped to its ink |
| `/v1/ayah/2:255-2:257.svg` | an inclusive ayah range |
| `/v1/word/2:255:4.svg` | one word |
| `/v1/page/042.svg` | the whole page, uncropped (this one is the bundle file) |
| `/v1/surah/112.svg` | a surah — only where it fits one page; otherwise 400 with a list of page URLs (§5, rejected as a first-class endpoint) |

**Decisions and the alternatives rejected:**

- **Colon-separated keys, not `/2/255/`.** `2:255` is the string quran.com,
  DigitalKhatt and every word-keyed dataset already use, and it is what
  `data-aid` literally contains. A consumer holding a verse key can build the
  URL by concatenation. *Rejected:* `/surah/2/ayah/255` — more path segments,
  more to get wrong, and it forces a mapping in the consumer's code that
  currently does not exist. `:` is legal in a path segment (RFC 3986
  `pchar`), and is already used this way by the Quran Foundation API.
- **The extension selects the format, not `Accept`, not `?format=`.**
  `<img src>` cannot set an `Accept` header, and CDNs cache poorly on `Vary:
  Accept`. The extension is visible in logs, is a distinct cache key by
  construction, and is what a developer can eyeball in their HTML. *Rejected:*
  content negotiation — it is the technically tidier answer and the practically
  worse one for an embed URL.
- **A range is `A-B` in one segment**, not two parameters. It keeps ranges and
  single ayahs in the same route and the same cache namespace.
- **Version in the path (`/v1/`), and it pins the ink** — see §6.3. `/v1/` is
  not just an API version; it is a promise about what the pixels are.

### 3.2 The parameters — deliberately five

Every parameter is a cache key and a support burden forever. The cache space is
the product of them all, so this list is short on purpose.

| param | values | default | why it is here |
|---|---|---|---|
| `w` | integer 100–4000 | intrinsic (SVG) / 800 (PNG) | PNG needs a size. SVG accepts it so `<img>` sizing is predictable. Quantise server-side to a **fixed ladder** — 200/400/800/1200/1600/2400 — and 302 anything else to the nearest. Turns an unbounded cache space into six entries. |
| `ink` | `#rrggbb` or a named preset | `#231f20` | **The single best selling point and it is nearly free.** Every path in the mushaf is `fill="#231f20"` and a CSS rule beats a presentation attribute, so recolouring is one injected `<style>` — verified in the emitted markup. |
| `bg` | `#rrggbb` or `none` | `none` (SVG) / `white` (PNG) | transparent SVG composites onto any page; PNG needs a decision or it looks broken in email. |
| `theme` | `light` \| `dark` \| `auto` | `light` | `auto` emits a `prefers-color-scheme` block *inside the SVG* so one URL adapts. This is the answer to "dark mode" that does not double the cache. PNG cannot do `auto` — 400 it. |
| `marker` | `0` \| `1` | `1` | whether the ayah end-ornament is inside the crop. Genuinely wanted both ways — inline in prose you usually want it, in a heading you usually do not. |

**Rejected parameters, with reasons:**

- `pad` — an arbitrary float multiplies the cache space for a value the
  embedder can set in CSS. Fixed at 4 viewBox units; the crop is tight and the
  page has its own margins anyway.
- `marks=0` (hide diacritics) — trivially possible
  (`[data-kind="mark"]{display:none}`) but it produces a rasm-only rendering
  of the Quran, which is a scholarly artefact, not an embed option, and we
  should not be the ones shipping it casually as a query parameter. Document
  the CSS selector in the format spec instead and let the consumer own that
  decision.
- `font`, `translation`, `text` — out of scope (§2).
- `quality`, `dpr`, `format=webp` — measure first. WebP q90 at 800 px was
  57 KiB against a quantised PNG's 14 KiB on the same crop; PNG wins for
  black-on-white line art, so WebP buys nothing here.

### 3.3 How the ayah is actually extracted — proved, not asserted

This is the technical heart, so I built it: **`docs/shipping/poc/ayah_crop_poc.py`**.

**The three traps, and how they are handled.**

1. **An ayah is not one node.** Measured over the whole corpus: 6,236 ayahs are
   emitted as 12,868 `<g class="ayah">` nodes. **4,458 ayahs (71.5 %) are
   multi-node** — one per printed line they occupy.

   | nodes per ayah | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 15 |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|
   | ayahs | 1778 | 2762 | 1113 | 387 | 103 | 47 | 13 | 13 | 6 | 2 | 1 | 1 |

   Pathological cases exist and must not crash the crop: **6:128 has 35 nodes**,
   2:109 has 33, 6:125 has 28, 6:130 has 27. The crop is the **union** of their
   boxes, always.

2. **The root frame has a negative y-scale** —
   `matrix(1.3333 0 0 -1.3333 E 640)`, with `E` varying per page (−55 on p3,
   −115 on p42). Reading min/max off raw path coordinates gives an upside-down
   box. And each `<g class="line">` carries its own inner `translate(...)`.

   **The strategy that avoids all of it: keep the ancestor chain.** Copy the
   root `<g>` and each line wrapper verbatim, delete only the sibling content,
   and the transforms compose themselves exactly as they do in the page. The
   box is then measured in the final frame, where "up" is up. No matrix is
   ever retyped as a literal — which is what the demo had to do
   (`SHIPPED-ARTIFACT` §1) and is a bug waiting to happen.

3. **No ayah crosses a page boundary.** Verified two independent ways: all
   6,236 `data-aid` values appear on exactly one page in our SVGs, and the
   DigitalKhatt layout DB (`.cache/dk_lines.json`, the authoritative model of
   this 1441H print) agrees 6,236/6,236. So the endpoint never stitches. This
   is a property of the Madani print, not of our pipeline, and it removes the
   single hardest case from the design. **Ranges still can span** — 603 of
   6,235 adjacent-ayah boundaries (9.7 %) fall on a page break; see §3.6.

**The proof.**

```
$ python3 docs/shipping/poc/ayah_crop_poc.py 2:255 --page 42
{"page": 42, "key": "2:255", "nodes": 6, "box": [2.98, 252.52, 339.09, 474.88],
 "bytes": 262711}
$ rsvg-convert -w 1000 -b white out/2-255-p042.svg -o 2-255.png
```

Renders Ayat al-Kursi, six line fragments, correct RTL, real KFGQPC ink, and
the crop still carries every `data-wid`, `data-uthmani` and `data-mark` — it is
addressable, not a picture. `112:1` renders as a clean single line
(`قل هو الله أحد`, 700 px, box 238.08–335.95 × 76.29–115.46).

Box caveat, inherited from `wordbox_poc.py`: these are the **control-point
hull** of the path data, a slight superset of the true outline. A production
implementation takes exact extents from the pipeline, which already computes
them. That makes the crop marginally tighter, never wrong.

**Where it currently breaks — and it is the known blocker.** With
`marker=1`, `112:1` returns a box of **86.54–335.95 × 76.29–547.43**: the full
page height, because the marker tagged `2:255`-style `data-aid` is on the wrong
ayah (`SHIPPED-ARTIFACT` §8.1, reversed on 441 of 604 pages). With `marker=0`
the same crop is **238.08–335.95 × 76.29–115.46** — correct. The `2:255` crop
visibly draws a marker reading **٢٥٤**. §7.

### 3.4 What the developer pastes

Four options, measured against what an embedder actually has.

| mechanism | interactive? | dark mode | CSP/CMS friendliness | verdict |
|---|---|---|---|---|
| `<img src="…svg">` | no — SVG loaded via `<img>` is a closed document; no external CSS, no JS, no DOM access | only via `theme=auto` inside the file, which **does** work in `<img>` | works everywhere, including GitHub READMEs, most CMSs, RSS | **the documented default** |
| `<img src="…png">` | no | no | works where SVG does not: email, some CMSs, social/OG cards | **the fallback, and a real one** — §3.7 |
| inline `<svg>` (fetch + insert) | yes — `data-wid`, `data-mark`, everything | yes | needs a fetch and a CSP allowance | **document it**; it is the whole differentiator |
| `<object>` / `<iframe>` | partly | yes | heavier, focus and sizing quirks | **document `<object>`, do not recommend `<iframe>`** |

**Recommend `<img>` as the default** precisely because it is the lowest-friction
thing that exists, and lead the docs with the inline-SVG upgrade path — the
addressability is why anyone would choose us over a font.

A worked example, everything real:

```html
<!-- simplest thing that works, anywhere -->
<img src="https://quran.ws/v1/ayah/2:255.svg" alt="Qur'an 2:255"
     width="900" style="max-width:100%">

<!-- adapts to the reader's theme, still one static file -->
<img src="https://quran.ws/v1/ayah/2:255.svg?theme=auto" alt="Qur'an 2:255">

<!-- an email or a GitHub README -->
<img src="https://quran.ws/v1/ayah/2:255.png?w=800&bg=white" alt="Qur'an 2:255">

<!-- addressable: fetch it inline and light up one word -->
<div id="a"></div>
<script>
fetch('https://quran.ws/v1/ayah/2:255.svg')
  .then(r => r.text()).then(t => {
    document.getElementById('a').innerHTML = t;
    document.querySelector('[data-wid="2:255:4"] path')
            .setAttribute('fill', '#b03030');
  });
</script>
```

`alt` text is the consumer's job — we serve ink and hold no opinion about which
text rendering belongs in an `alt` attribute. Note this in the docs; it is the
one accessibility duty the URL cannot discharge.

### 3.5 Static or dynamic — measured, and the answer is mostly static

`ayah_crop_poc.py --estimate 300`, over 300 real ayahs from 60 pages:

| | mean per ayah | × 6,236 |
|---|---:|---:|
| raw SVG | 67.8 KiB | **412.9 MiB** |
| gzip -9 | 19.1 KiB | 116.4 MiB |
| brotli q11 | 14.5 KiB | **88.1 MiB** |
| build time (single core, incl. full page parse) | 132 ms | ~14 min |

For scale, the whole 604-page bundle is 454.1 MiB raw / 70.0 MiB brotli.

**Finding: pre-generating every ayah costs roughly what the page bundle costs,
and about a quarter-hour of one core.** That is cheap, trivially parallel, and
it turns the flagship into **a CDN path with no server behind it**. It is worth
saying plainly: *the "API" for the canonical form is a directory of files.*

Note that the ayah set brotlis to *more* than the page set (88 vs 70 MiB)
despite covering the same ink: crops compress alone, without the cross-page
redundancy the page files enjoy. Do not assume slicing shrinks things.

**Where the line falls.** The parameter space multiplies:
6 widths × 2 markers × N inks × 3 themes. Inks are unbounded, so full
enumeration is out.

| form | class | why |
|---|---|---|
| `/v1/ayah/{key}.svg` with defaults | **pre-generated static (c)** | 6,236 files, 88 MiB brotli. Build once per bundle version, upload, done. |
| `?theme=auto`, `?marker=0` | **pre-generated static** | two more small enumerable variants; ~3× the set, still under 270 MiB brotli. Build them or compute them — measure before deciding. |
| `?ink=`, `?w=` on SVG | **dynamic, but trivial** | a text substitution and an attribute. Sub-millisecond; cache on the CDN. |
| `.png` at any `w` | **dynamic (c)** | §3.7 |
| `/v1/word/{key}.svg` | **dynamic** | pre-generating loses badly — §4 |
| `/v1/page/{n}.svg` | **static (b)** | it *is* the bundle file |

**Recommendation: pre-generate the canonical form; compute variants on demand
behind the CDN.** That is the shape that costs almost nothing and still answers
every reasonable request.

### 3.6 Ranges

`/v1/ayah/2:255-2:257.svg`. Same machinery: select every `<g class="ayah">`
whose `data-aid` falls in the range, union the boxes.

**Ranges are dynamic (c)**, not pre-generated: there are ~19.4M valid
same-surah ranges. They are also the one place the page-boundary question
returns — 603 of 6,235 (9.7 %) adjacent-ayah boundaries cross a page.

For a range that spans pages, three options and I recommend the third:

1. return only the first page's part — silently wrong, reject;
2. stitch the pages into one canvas — requires deciding line spacing and
   margins that the print does not define across a page break; we would be
   inventing layout, which this project does not do;
3. **return one `<svg>` per page segment inside a wrapping `<svg>`, stacked
   vertically with a documented gap** — honest, and it visually reads as what
   it is: two pages' worth of ink. Document that a cross-page range returns a
   multi-segment result, and expose `?pages=first` for consumers who want a
   single flat image.

Cap the range length (say 20 ayahs, and reject ranges spanning >2 pages) —
otherwise `/v1/ayah/2:1-2:286.svg` is a whole-juz render behind a single GET,
and someone will loop it.

### 3.7 PNG — the strongest case for anything dynamic

SVG does not render in email clients, in many CMS rich-text fields, in most
social/OG card contexts, or in some README renderers. That is a real, common,
first-use barrier and PNG removes it.

Measured over 60 ayah crops, `rsvg-convert -w 800 -b white`:

| | mean | median | max |
|---|---:|---:|---:|
| render time (1 core) | **62 ms** | 55 ms | 153 ms |
| PNG (24-bit) | 54.9 KiB | 40.4 KiB | 202.4 KiB |
| PNG after `pngquant` 8-bit | **14.0 KiB** | — | — |

Ayat al-Kursi specifically, at 800 px: PNG 149 KiB → pngquant 38 KiB → WebP q90
57 KiB. Its brotli SVG is 47 KiB.

**Three findings worth stating:**

1. **Quantised PNG costs the same bandwidth as the brotli SVG** (14.0 vs
   14.5 KiB mean). PNG is not a bloated fallback here — for black-on-white line
   art it is a peer. Always run `pngquant`; it is a 4× saving for free.
2. **WebP is not worth adding.** It lost to quantised PNG on the one case
   measured (57 vs 38 KiB) and costs another format in the cache. Rejected.
3. **The compute is negligible.** 1M PNG renders/month = 17.2 core-hours *if
   every one misses cache*. At a realistic 90 % CDN hit rate it is 1.7
   core-hours/month — a $5 VM, idle most of the time. The cost of PNG is
   operational (a process that can crash, a queue that can back up), not
   financial.

Guard rails, because a render endpoint is the one thing here that can be
weaponised: quantise `w` to the six-step ladder, cap at 4000, cap the range
length, and give `rsvg-convert` a hard timeout and a memory cap. The 153 ms max
becomes the SLO, not the mean.

---

## 4. The rest of the surface, ranked

Ranked by (value to a developer) ÷ (cost to run). Every row carries both
classifications from §1.

| # | service | delivery | justification | needs from the pipeline | effort |
|---|---|---|---|---|---|
| 1 | **`/v1/ayah/{key}.svg`** | pre-generated static | **(c)** | ayah-marker fix (§7); exact extents | small — the PoC is 300 lines |
| 2 | **`/v1/ayah/{key}.png`** | dynamic | **(c)** — SVG does not render where this is wanted | nothing new | small |
| 3 | **`/v1/ayah/{key}` with `ink` / `theme`** | dynamic (trivial) | **(c)** — one colour of ink makes this nearly free, and it is the thing a font cannot do at all | nothing new | tiny |
| 4 | **`/v1/page/{n}.svg`** | static | **(b)** | nothing | none — it is the bundle file |
| 5 | **`/v1/ayah/{A}-{B}.svg`** | dynamic | **(c)** | cross-page policy (§3.6) | small |
| 6 | **`/v1/word/{key}.svg` / `.png`** | dynamic | **(c)**, but weakly | nothing new | tiny |
| 7 | **`/v1/locate/{key}` → 302 to the page URL** | pre-generated static (a 6,236-row table) | **(b)** — metadata, but only the metadata needed to *serve ink* | the ayah→page table (already in `index.json`) | tiny |

**On #4:** serving pages is `(b)`, thin convenience, and it has to beat
jsDelivr-over-the-repo, which is free, brotli-encoded and immutable on tagged
paths. It earns its place only as **the same origin** as #1–3 — one host, one
CORS policy, one cache story — not on its own merits. If the service is not
built, this row disappears and jsDelivr does the job.

**On #6, and why words are dynamic:** measured over 300 real word crops,
mean **5.96 KiB raw / 1.96 KiB brotli**, extrapolating to **450.7 MiB raw /
148.6 MiB brotli** for all 77,432 — *more than double* the page bundle's
brotli, for the granularity least likely to be embedded on its own. Compute is
34 ms per crop. Pre-generation is firmly rejected; serve dynamically, and
document that a consumer who already has the page can do it client-side with
`getBBox()` in about twelve lines (the demo does exactly this).

**On #7:** the only metadata endpoint proposed, and only because you cannot
serve `/page/N` without knowing which N. Everything else metadata-shaped is
`index.json` in the bundle, and the bundle is a download away.

---

## 5. Rejected — services that should not exist

More useful than another endpoint table.

| idea | why not |
|---|---|
| **Per-ayah pre-generated files as a *download*** | **(a)** — 88 MiB brotli on top of a 70 MiB bundle covering the same ink. If someone wants them offline they can run our crop script over the bundle. Ship the script, not the files. |
| **A search endpoint** | Out of scope (§2), and **(a)** — `words.json` is 478 KiB brotli in the bundle. A consumer can search the entire mushaf client-side in a fetch smaller than one page SVG. Running a search service would be strictly worse than what they already have. |
| **Text / translation / tafsir / audio endpoints** | Out of scope by instruction, and we would be a worse quran.com. §2. |
| **A tajweed colour API** | The colouring is a CSS file over `data-mark` — **(a)**, and it is also a scholarly opinion. Publish a stylesheet as a separate artifact if at all; do not put an opinion behind a URL we operate. |
| **A memorisation / masking endpoint** | **(a)** — `g.word[data-wid^="2:255:"]{visibility:hidden}`. It is one CSS rule on files the consumer already has. Put it in the docs as an example; a server adds nothing. |
| **Word-timing / audio-sync overlays** | Out of scope. The join is `data-wid` and `quran-align` already emits it. A 20-line README example, not an endpoint. |
| **An interactive `<iframe>` embed widget** | Heavier than `<img>`, harder to style, and everything it would do is available by fetching the SVG inline. Ship a documented snippet instead. |
| **An OG / share-card renderer** (ayah on a branded background) | Tempting, and genuinely dynamic — but it is a *design* product, not an ink product. It needs typography, a background, a logo and a brand. Out of the narrowed scope, and it invites us to composite the Quranic text into decorated images we then serve. If ever built, build it *on top of* `/v1/ayah/{key}.png`, as someone else's layer. |
| **A `/v1/surah/{n}.svg` first-class endpoint** | Almost every surah spans many pages, so it is a range render with a friendlier name and all the cross-page problems. Support it only where the surah fits one page; otherwise 400 with the list of page URLs. |
| **An account system / API keys** | See §6.5. |

---

## 6. Operational reality

### 6.1 Hosting shape

**Recommended: object storage + CDN, with one small render worker.**

```
quran.ws
 ├── /v1/ayah/{key}.svg   -> R2/S3 object, pre-generated       (static)
 ├── /v1/page/{n}.svg     -> R2/S3 object, the bundle file      (static)
 └── everything else      -> render worker, cached by the CDN   (dynamic)
```

Any of Cloudflare (R2 + Workers), Bunny (storage + CDN + a $5 VM), or a plain
VPS behind Cloudflare will do. The service has **no database and no state** —
which is the whole point of §3.5 and is what makes uptime cheap.

*Rejected:* a general application server in front of everything. It puts a
process in the path of requests that are literally files, and it is how a
static problem acquires an on-call rotation.

### 6.2 Cost, at the two volumes asked for

Bandwidth is the only variable cost. Per-response sizes are measured, not
assumed: ayah SVG 14.5 KiB brotli, ayah PNG 14.0 KiB quantised, page SVG
119 KiB brotli.

| | 10k req/month | 1M req/month |
|---|---|---|
| all ayah SVG | 0.14 GB | **14.2 GB** |
| all ayah PNG | 0.14 GB | 13.7 GB |
| all page SVG | 1.2 GB | **116 GB** |
| realistic mix (80 % ayah, 20 % page) | 0.35 GB | 34 GB |
| PNG compute, 0 % cached | 10 min core | 17.2 core-hours |
| PNG compute, 90 % cached | 1 min | 1.7 core-hours |

At 10k/month this is a **free tier on any provider**. At 1M/month the mix is
~34 GB — under $1 on Bunny ($0.01/GB), $0 egress on Cloudflare R2, and the
compute fits a single $5 VM with room to spare. **Cost is not a reason to
avoid this.** The reasons, if any, are the promise (§6.3) and the on-call.

The number that would actually hurt is **page** traffic at scale — 116 GB at
1M requests. That is the row to watch, and it is also the row jsDelivr will
serve for free (§4, #4).

### 6.3 Versioning, and how the service cannot drift from the bundle

This is the part that matters more than the cost, because an `<img>` tag lives
forever in someone's page.

- **`/v1/` pins the ink, not just the shapes of responses.** Define it that
  way in the docs: *a `/v1/` URL returns the same pixels forever.*
- **Every response carries the bundle version it was cut from** — as
  `data-bundle-version="1.0.0"` on the root of every SVG (already proposed for
  the bundle, `SHIPPED-ARTIFACT` §5.5) and as a
  `X-Quran-Bundle: 1.0.0` response header on SVG and PNG alike. A consumer
  mixing a downloaded bundle with service responses can then *check*, offline,
  that they match.
- **Rebuild the whole pre-generated set from one bundle tag, atomically.** Never
  crop from a working tree. The build input is a git tag; the output directory
  is named for it; the CDN alias flips once. Half-updated is the failure mode
  that would produce a mismatch and it is designed out rather than monitored.
- **A new bundle with corrected ink gets a new prefix**, `/v2/`, and `/v1/`
  keeps serving the old pixels. This is expensive in storage (88 MiB per ayah
  set, 70 MiB per page set — pennies) and cheap in trust. *Rejected:*
  silently updating `/v1/` when a defect is fixed. It is the tempting thing and
  it breaks the one promise the URL makes.
- **Expose `/v1/version.json`** — bundle version, build date, page/ayah/word
  counts, and the gate results. One file, static, and it is how a consumer or a
  monitor answers "what am I actually being served?"

Note that this interacts with the ongoing defect work: a `/v1/` that promises
frozen pixels means **fix the blockers before minting `/v1/`**, not after.

### 6.4 Caching

- Pre-generated and page paths: `Cache-Control: public, max-age=31536000,
  immutable`. Safe because `/v1/` never changes (§6.3).
- Parameterised renders: same, keyed on the normalised query. **Normalise
  before caching** — sort parameters, lowercase hex, drop defaults, snap `w` to
  the ladder — or the cache fragments into near-duplicates.
- `ETag` from the bundle version plus the normalised key; support
  `If-None-Match` so an embedder's revalidation is a 304.
- `Vary: Accept-Encoding` only. Never `Vary: Accept` (§3.1).
- `Access-Control-Allow-Origin: *` — required for the inline-SVG path, and
  there is nothing to protect.

### 6.5 Rate limiting and auth

**No auth. No API keys. No accounts.** Everything served is public,
non-personal, cacheable static content, and an account system would add a
database, a signup flow, a support burden and a privacy surface to a service
whose entire job is to hand out files. It is also a barrier to the exact
first-use moment the flagship exists to remove.

*Rejected:* keys "so we can see who uses it". Aggregate CDN logs answer that.

Rate limiting, however, **is** needed, and only on the dynamic paths:

- static paths: none — the CDN absorbs it;
- render paths: per-IP token bucket (say 60/min burst 120), plus the structural
  caps from §3.6/§3.7 (range length, `w` ladder, render timeout, memory cap).
  The caps matter more than the bucket: they bound the *worst* request, which
  is what actually takes a service down.

### 6.6 What breaks if it gets popular

| failure | trigger | mitigation |
|---|---|---|
| render worker saturates | a crawler walking `?w=` and `?ink=` | the `w` ladder (six values), normalised cache keys, per-IP bucket |
| one huge render | `/v1/ayah/2:1-2:286.png?w=4000` | range cap, page-span cap, `w` cap, hard timeout |
| bandwidth bill | page traffic at 1M+ | move `/v1/page/` to jsDelivr-over-the-tag and 302 to it |
| hotlink concentration | one popular site embeds one ayah | this is the *success* case and the CDN handles it entirely |
| the origin dies | anything | pre-generated paths keep serving from the CDN; only PNG and variants degrade. Design the failure so the flagship survives it. |
| a defect is found in the ink | the audits keep finding them | `/v2/`, never a silent `/v1/` rewrite (§6.3) |

---

## 7. What the service needs from the pipeline that does not exist yet

| # | need | status | blocks |
|---|---|---|---|
| 1 | **ayah-marker `data-aid` corrected** | broken on 441/604 pages (`SHIPPED-ARTIFACT` §8.1); reproduced here — `112:1` with marker gives a whole-page box instead of a one-line box, and the `2:255` crop draws ٢٥٤ | **the flagship, hard.** `marker=1` is the default and it is wrong nearly everywhere |
| 2 | **exact ink extents per word/ayah**, emitted by the pipeline | the pipeline computes them; nothing writes them out. The PoC uses a control-point hull (slightly loose, never wrong) | crop tightness; also `wordboxes.json` in the bundle |
| 3 | **`id` per word**, mirroring `data-wid` | proposed in the bundle (`SHIPPED-ARTIFACT` §3.1) | `:target`-based no-script embeds; nice, not blocking |
| 4 | **correct `<g class="line">` membership** | 54 words on 51 pages are in the wrong line group (§8.2 there) | line-granular crops only; ayah crops are unaffected because they select on `data-aid` |
| 5 | **a stable root `data-bundle-version`** | not emitted today | §6.3's whole mechanism |
| 6 | **the ayah→page table** as a shipped file | exists inside `index.json` (bundle) | `/v1/locate/`, and knowing which page to crop without scanning 604 files |

Only #1 is a blocker. Everything else degrades gracefully.

---

## 8. Domains

The choice is Abdullah's; the practical differences are these.

| | `quran.ws` | `quranpedia.net` |
|---|---|---|
| shape | a short, product-shaped domain with nothing else on it | an existing property with an audience and an existing API (`api.quranpedia.net`, which already offers downloadable SVG/PNG mushaf packages) |
| what a URL says | `quran.ws/v1/ayah/2:255.svg` — reads as a service; short matters when it is pasted into HTML | `quranpedia.net/svg/v1/…` — inherits recognition, but also a namespace already in use |
| coupling | independent uptime, independent reputation; if the service is retired, nothing else is affected | ties the service's uptime to the main property's, in both directions |
| discovery | starts at zero | starts with existing traffic and an existing developer audience |
| coherence with the artwork's origin | none | the page artwork comes from `quranpedia/quran-svg`; serving it under the same name is a coherent story |

Two notes that are not preferences:

- **Whichever is chosen, the hostname is part of the permanent promise.** An
  `<img src>` outlives the decision, so a later migration means keeping the old
  host serving 301s indefinitely. Decide once.
- **Do not serve this from a subdirectory of a site that also serves an app.**
  Cache policy, CORS and rate limiting all differ; a subdomain
  (`svg.quranpedia.net`) or its own domain keeps them separable.

---

## 9. Needs Abdullah's decision

Nothing below is decided here.

**S-1. Run a service at all?** The measured case is that the flagship is worth
it (§3) and that it is nearly free to run (§6.2) — but it is still an
operational commitment that the bundle alone does not carry. Everything else
proposed can be cut without touching the flagship.

**S-2. Which domain** (§8), and whether the service gets its own subdomain
regardless.

**S-3. Does `/v1/` promise frozen pixels?** §6.3 recommends yes, which means the
blockers must be fixed *before* `/v1/` is minted and that fixing ink later costs
a `/v2/`. The alternative — a mutable `/v1/` — is cheaper and breaks the one
promise the URL makes.

**S-4. Is `marks=0` (a rasm-only rendering) ever an option we serve?** I
recommend not as a query parameter, and documenting the CSS selector instead
(§3.2). That is a judgement about what we should make one-click easy, and it is
his.

**S-5. Do we serve PNG at all?** It is the strongest case for dynamic compute
and it removes a real barrier — but it also produces rasterised Quranic ink
that we no longer control the fidelity of once it is resized by someone else's
CMS. Measured cost says yes; the judgement is his.

**S-6. Does `/v1/page/` exist, or does jsDelivr serve pages?** §4 #4 — it earns
its place only as same-origin convenience, and it is the largest bandwidth row.

**S-7. Where does the service's code live?** The bundle proposal recommends a
separate publication repo (§9 D-3 there). A service is a third thing again.

---

## Appendix — how every number here was produced

Run from the work dir with `export QSVG_ROOT=$PWD`.

| number | command |
|---|---|
| corpus size, 604 pages, 454.1 MiB | `du` + per-file `os.path.getsize` over `.cache/words-svg/hafs-kfqc/*.svg` |
| per-page gzip/brotli (mean 176.8 / 112.6 KiB on a 31-page sample) | `gzip.compress(q=9)` / `brotli.compress(quality=11)`, every 20th page. Agrees within 6 % with the whole-corpus 119 KiB in `SHIPPED-ARTIFACT` §2, whose figure I quote |
| ayah node counts, fragmentation histogram, worst cases | `python3 docs/shipping/poc/ayah_crop_poc.py --survey` |
| no ayah crosses a page (6,236/6,236) | the same survey, plus an independent check against `.cache/dk_lines.json` (page → {wid: line}) |
| 603 of 6,235 adjacent-ayah boundaries cross a page | last `data-wid` of page N vs first of page N+1, all 603 boundaries |
| ayah crop sizes and build time (67.8 / 19.1 / 14.5 KiB, 132 ms) | `python3 docs/shipping/poc/ayah_crop_poc.py --estimate 300` |
| word crop sizes (5.96 / 1.96 KiB, 34 ms) | 300 crops over 12 random pages, same module |
| `2:255` crop: 6 nodes, box, 262,711 B | `ayah_crop_poc.py 2:255 --page 42` |
| `112:1` marker on/off boxes | `crop(604, '112:1', marker=True/False)` |
| PNG render time and size (62 ms, 54.9 / 14.0 KiB) | `rsvg-convert -w 800 -b white` + `pngquant --quality 60-90` over 60 crops from 20 random pages |
| WebP comparison (57 KiB) | `cwebp -q 90` on the 800 px `2:255` render |
| `data-wid` = DigitalKhatt `location` | `select * from words limit 3` on `.cache/digitalkhatt/digital-khatt-v2.db` |
| ecosystem facts in §2 | live fetches of `api.quran.com/api/v4`, `apis.quran.foundation`, `static.qurancdn.com/fonts/quran/hafs/v{1,2}/woff2/`, `files.quran.app/hafs/madani/`, `cdn.islamic.network/quran/images/`, `digitalkhatt.org/api/*`, plus the repos named inline |
