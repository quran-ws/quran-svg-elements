# Demo page — proposal

Plan only. No design, no implementation. Visual design happens afterwards with
Claude's design skill.

Framing (Abdullah, 2026-08-29): **the page is a developer landing page for a
product, not a report about the pipeline.** It answers three questions in order —
what we offer, why they need it, how to use it. Nothing about audits, defect
counts, the pixel gate, overrides, or how the ink was assigned. A visitor does
not care that it was hard.

Every claim below was checked against the SVGs emitted tonight
(`.cache/words-svg/hafs-kfqc/`, all 604 files written 2026-08-29 21:17–21:19).

---

## 0. State of the working tree

`docs/demo/index.html` is **byte-identical to HEAD** (`git diff HEAD --
docs/demo/index.html` is empty). I made no writes anywhere in `docs/demo/`.
The one modified file, `docs/demo/build_embed.py`, was already modified when I
arrived — my first directory listing showed its mtime as `29 Aug 21:16`, before
my first tool call — and it belongs to whoever is doing the `data-word-key`
migration. I have left it alone.

---

## 1. What exists, and what it is worth

| file | size | verdict |
|---|---|---|
| `template.html` | 52 KB, 1053 lines | source of truth for `index.html`. **Its JS is dead against the current schema.** Keep the CSS and ~4 of 8 sections; rewrite the JS. |
| `index.html` | 783 KB | built artefact, frozen on the *old* schema. Regenerate. |
| `003-embed.svg` | 792 KB | page 3 + `<view>`s + `:target` CSS. Clever; keep the mechanism, shrink the ambition (§4). |
| `build_embed.py` | 175 lines | already half-migrated to `data-word-key`. Not mine to edit. |
| `nojs-template.html` / `nojs.html` | 11 KB → **2.5 MB** | inlines the 792 KB embed SVG **three times**. See §4 — I propose dropping it as a separate page and folding its idea into one section. |
| `build.py` | 19 lines | fine as-is. |
| `geom.json` | 6 KB | measured-in-browser bounding boxes for page 3. **Now obsolete** — see §3.4. |

### What genuinely works and must survive

- **The inspector.** Hover any stroke, and a readout names the word, the
  ligature, the element kind, the mark and its shape signature. Verified live:
  127 `g.word`, highlight follows word and ligature separately. This is the
  single most convincing thing on the current page — it makes "every stroke is
  addressable" a fact you feel rather than a sentence you read.
- **The crop function** (`template.html:659`) — clone, drop the words you don't
  want, drop emptied wrappers, `getBBox()`, write a new `viewBox`. Twelve lines,
  no dependencies, and it is the operation half the use cases are built from.
- **The palette and type system.** Spectral / Public Sans / IBM Plex Mono /
  Amiri, three-state theming done correctly (bare `:root`, a
  `prefers-color-scheme` block guarded with `:not([data-theme="light"])`, and an
  explicit `[data-theme="dark"]`). Keep verbatim.
- **The recolour section's proof:** every path ships `fill="#231f20"` and a CSS
  rule beats the attribute, so meaning-driven colour needs no re-export.

### What is weak

1. **It is broken as of tonight, and silently.** `template.html` reads
   `w.dataset.ayah` / `.word` / `.surah`; the emitter now writes
   `data-word-key="2:6:1"`. I built a probe copy from tonight's `003.svg` and loaded
   it: it throws at `template.html:637`

   ```
   TypeError: Cannot read properties of null (reading 'getBoundingClientRect')
   ```

   inside one IIFE, so **every interactive section on the page dies at once**.
   The shipped `index.html` still works only because it has the November schema
   frozen inside it. Any rebuild ships a dead page.
2. **It talks about the pipeline.** The masthead — "taken apart and still
   identical", "1010 named elements", "proved against the original artwork two
   ways" — is about us. A visitor cannot tell what they would build.
3. **No search.** The headline capability of the current files has no section.
4. **No metadata.** Surah name, juz, hizb, rubʿ are all in the files now
   (§2.2) and the page never mentions them.
5. **No addressing.** No `#2:255`, no deep link, no "here is how you point at an
   ayah from your app".
6. **No accessibility story**, and the files currently have nothing to tell one
   with (§3.3).
7. **One page, one surah, no reader.** Everything is page 3 of surah 2. A
   developer building a *reader* sees no reader.
8. **The ornament-swapping section is a novelty.** Six alternate rosettes is
   charming and nobody adopts a mushaf corpus because they can turn the ayah
   marker into a diamond. Cut to a single line inside the styling section.
9. **`nojs.html` costs 2.5 MB to make a purist point.**

---

## 2. Use cases, ranked by how much they would make a stranger adopt this

Rank = how much it moves a build/don't-build decision. "Today?" = works against
the files as emitted tonight, with no emitter change.

### 2.1 Search the whole mushaf, then land on the ink — **highest value, today**

**Demonstrates:** these are not pictures. Type `الله`, get every occurrence,
click one, and the exact printed word lights up on its exact printed page.

**What makes it possible:** every `g.word` carries
`data-rasm` (consonantal skeleton) and `data-rasm-imlai` alongside `data-rasm-uthmani`
and `data-qpc`. Verified on `003.svg`:

```
data-word-key="2:6:2" data-rasm-uthmani="ٱلَّذِينَ" data-rasm="ٱلذين"
                 data-rasm-imlai="الَّذِينَ" data-qpc="ٱلَّذِينَ"
```

`data-rasm` is a clean skeleton — **36 distinct characters mushaf-wide**, no
harakahs at all, 14,809 distinct tokens.

**The one thing the demo must teach, with the number that proves it:**
`data-rasm` preserves orthographic hamzah forms and U+0671 ALEF HAMZAT_AL_WASL, so a naive
substring match fails. Measured across all 604 pages:

| query | raw `data-rasm` matches | after a 9-character fold |
|---|---|---|
| `الله` | **2** | **2557** |
| `الذين` | 0 | 1000 |
| `على` | 770 | 1663 |
| `انا` | 54 | 407 |

The fold is one line the reader can paste:

```js
const fold = s => s.replace(/[ٱأإآ]/g,'ا').replace(/ى/g,'ي')
                   .replace(/ة/g,'ه').replace(/ؤ/g,'و').replace(/ئ/g,'ي')
                   .replace(/ء/g,'');
```

This is the best section on the page precisely *because* there is a trap in it:
we hand them the trap and the fix together, and they trust the rest.

**Scope:** in-page search over the loaded page is trivially today. **Mushaf-wide
search is also today**, because `docs/shipping/out/words.json` already exists —
all 77,432 words as `["word_key", page, rasm, rasm_imlai]`, **3.5 MB raw / 792 KB
gzipped**. Search that, get `wordKey` + page, fetch that one page SVG, highlight.
Dependency: that file must actually ship (§5).

### 2.2 Metadata without a database — **today**

**Demonstrates:** you do not need to bundle a Quran metadata package. Open the
file and read it off.

**What makes it possible** (all verified present tonight):

```html
<g class="surah-name" data-sid="2" data-surah-name-ar="البقرة"
   data-surah-name-latin="Baqarah" data-surah-name-en="The Cow"
   data-revelation-place="madinah" data-ayah-count="286">
<g class="basmalah" data-sid="2" …same six attributes…>
<g class="ayah-fragment" data-ayah-key="2:142" data-juz-start="2" data-hizb-start="3"
   data-rubu-al-hizb-start="9">
<g class="ayah-fragment" data-ayah-key="2:44" data-nisf-start="1" data-rubu-al-hizb-start="3">
```

Mushaf-wide counts I measured: 110 `surah-name` groups on 94 pages, 113
`basmalah` groups, and complete division coverage — **30 distinct
`data-juz-start`, 60 `data-hizb-start`, 60 `data-nisf-start`, 240
`data-rubu-al-hizb-start`**. That is every juz, every hizb, every half and every quarter.

**The demo:** a "what is on this page?" panel that is populated by nine lines of
DOM reading, no fetch, no JSON — surah name in Arabic and English, revelation
place, ayah range, and a badge when a juz/hizb/rubʿ opens here.

**Honest limit to print on the page:** four surahs have no `surah-name` group
yet — **27, 33, 37, 47** (starting on pages 377, 418, 446, 507). The demo should
degrade to the `data-word-key` surah number rather than pretend.

### 2.3 Pin a translation or tafsir to a word via `data-word-key` — **today, and nobody expects it**

**Demonstrates:** the word ids are a join key to the rest of the ecosystem. Hover
a printed word, get its gloss.

**What makes it possible:** `data-word-key="surah:ayah:word"` and the fact that this
is the standard quran.com word key. I tested the join on page 3 against the
cached word-by-word-translation-translation data: **127 of 127 words joined, zero misses.** The payload
for a whole page, reduced to `{wordKey: {en, translit}}`, is **5.9 KB**.

```js
const gloss = await (await fetch('gloss/003.json')).json();
svg.querySelectorAll('g.word').forEach(w => {
  const g = gloss[w.dataset.wordKey];
  if (g) w.insertAdjacentHTML('afterbegin', `<title>${g.en}</title>`);
});
```

The same key carries an `audio_url` per word (`word_by_word_translation/002_006_001.mp3`), so
word-level highlight-during-recitation is the same join — worth *stating* as a
one-liner even if we do not host audio.

**Caveat for the page:** the gloss is third-party (quran.com) and must be
attributed and shipped separately from the SVGs, not implied to be ours.

### 2.4 Ayah addressing and deep links — **today**

**Demonstrates:** `yoursite.com/read#2:255` scrolls to the ayah and lights it up.
This is the first thing anyone building a reader needs and the thing they most
often get wrong.

**What makes it possible:** `g.ayah-fragment[data-ayah-key="2:255"]`, plus
`g.ayah-mark[data-ayah-key]` which names the ayah the marker *closes* — so you no
longer need geometry to pair a marker with its ayah (§3.4).

**Must be shown correctly, because this is the trap (§3.1):** an ayah is
**several nodes**, so the correct idiom is `querySelectorAll`, and the highlight
is a class on all of them:

```js
document.querySelectorAll(`g.ayah-fragment[data-ayah-key="${id}"]`)
        .forEach(g => g.classList.add('lit'));
```

### 2.5 Style by meaning — **today; upgrade the existing section**

**Demonstrates:** one file, many renderings, no re-export.

Beyond the current paper/letters/marks/dots controls, three toggles that are
genuinely useful to a reader author and are one selector each:

- **Hide all diacritics** — `path[data-kind="mark"]{display:none}`. Page 3 has
  698 of them; the letters underneath are untouched.
- **Waqf marks only** — `path[data-mark-family="waqf"]`. Four on page 3, and it
  is exactly what a tajwid app wants to colour.
- **Colour by family** — the vocabulary really present: `data-kind` is
  `body` (2348 on my sample) / `mark` (5988) / `header_ink` (487) /
  `ayah_mark_ornament` / `ayah_number`; `data-mark-family` is
  `dots` / `tanwin` / `sifr` / `waqf`; `data-mark` names 12+ marks on page 3
  alone (`fathah` 201, `dot` 104, `dammah` 81, `kasrah` 71, `sukun` 55,
  `two_dots` 49, `hamzah` 28, `shaddah` 28, `hamzat_al_wasl` 20, `rounded_zero` 15,
  `omitted_alif` 15, `maddah` 14).

The existing section is close; it needs the vocabulary printed and the toggles
added, not a rewrite.

### 2.6 Copy the text out — **today, small, and it closes a doubt**

**Demonstrates:** select a run of words on the *image* and get real text.

Verified: joining `data-rasm-uthmani` over `2:6:*` on page 3 reproduces
`إِنَّ ٱلَّذِينَ كَفَرُوا۟ سَوَآءٌ عَلَيْهِمْ ءَأَنذَرْتَهُمْ أَمْ لَمْ تُنذِرْهُمْ لَا يُؤْمِنُونَ`
exactly. Offer all four scripts (`rasm_uthmani` / `rasm` / `rasm_imlai` / `qpc`) from one
selection — that four-way choice is itself the selling point.

### 2.7 A reader view — **today, and it is the "why" section made visible**

**Demonstrates:** the corpus is a reader, not a gallery. Two pages side by side,
RTL order (right page = lower number), keyboard `←`/`→` to turn, ayah highlight
persisting across the turn, and the surah header banner read from the file.

This is the section that proves the product rather than describing it, and it is
the natural home for the "why" argument: the print is exact *and* the ayah is
selectable, simultaneously.

**Cost note:** two pages inline is ~1.5 MB raw. Fetch on demand instead of
inlining (§4).

### 2.8 Accessibility — **NOT possible today; say so on the page**

**What a screen reader gets from a shipped page right now: nothing.** I checked
`003.svg`: no `<title>`, no `<desc>`, no `role`, no `aria-*`, no `lang`
anywhere in the file.

But the ingredients are all there, and `build_embed.py` already proves the
pattern by injecting `<title>` per word. The honest section is: *here is the
15-line function that makes a page readable*, with a live "what a screen reader
hears" transcript beside it —

```js
svg.setAttribute('role','img');
svg.setAttribute('lang','ar');
svg.querySelectorAll('g.word').forEach(w => {
  w.setAttribute('role','text');
  w.insertAdjacentHTML('afterbegin', `<title>${w.dataset.rasm_uthmani}</title>`);
});
```

— and a flat statement that this is not yet baked into the shipped files, with
the reason (it is a real size cost per page and belongs behind a build flag).
Saying "not yet, here is the workaround" is more persuasive than silence.

### 2.9 Overlay our render on the source and report the difference — **candidate, shows the guarantee instead of asserting it**

**Demonstrates:** §A2's pixel guarantee, made self-evident.

A slider or a difference-blend between the source artwork and our decomposed
render of the same page, with a live pixel-difference readout that stays at
zero. Better than any sentence we could write, and it is the only place on the
page where our rigour is allowed to appear — as something the visitor verifies,
not something we claim.

**Feasibility, honestly:** this needs the *source* artwork page shipped beside
the decomposed one, which roughly doubles the payload for that section, and both
must be rasterised in-browser to be compared. Rendering two SVGs to canvas and
differencing them is straightforward; matching the audit's exact discipline
(1400 px, tolerance 24/255) in a browser is not, and we must not present a
loose in-browser comparison as if it were the gate. Two acceptable forms:
(a) a visual A/B slider with no numbers, captioned by the real audit's
parameters; or (b) a genuine canvas difference with the readout labelled as an
in-browser illustration, and the gate described separately. **Do not** show a
number that implies it is the audit's number.

### 2.10 Two of my own, both cheap and both convincing

- **"Any crop is a component."** One word for a vocabulary card, one ayah for a
  citation, one line for a header — the same twelve-line `crop()`, three
  filters, three live results side by side, each with a download-as-SVG button.
  This is the section a developer screenshots and sends to their team.
- **A styled-vs-print A/B slider.** Drag it: left is your styling (spacing
  opened, marks recoloured, diacritics off), right is the untouched print. It
  makes the guarantee — *styling and selection never alter the print* —
  something you verify with your own eyes in two seconds, without us ever
  mentioning a pixel audit.

### Ranked, with a proposed cut line

| # | use case | today? | verdict |
|---|---|---|---|
| 1 | Search (in-page → mushaf-wide) | yes | headline |
| 2 | Ayah addressing / deep link | yes | headline |
| 3 | Translation pinned by `data-word-key` | yes | headline |
| 4 | Reader view / two-page spread | yes | headline |
| 5 | Metadata without a database | yes | strong |
| 6 | Style by meaning (upgraded) | yes | strong |
| 7 | Inspector (kept from today) | needs JS rewrite | strong |
| 8 | Crop-as-component | yes | strong |
| 9 | Copy text out, four scripts | yes | keep, small |
| 10 | Print/style A/B slider | yes | keep, small |
| 11 | Source-vs-render overlay (§2.9) | needs the source page shipped too | candidate, high value |
| 12 | Accessibility | **no** | keep as an honest "not yet" |
| — | *cut line* | | |
| 13 | Ornament swapping | yes | demote to one line |
| 14 | Spacing sliders | yes | demote into the A/B slider |
| 15 | JS-free twin as its own 2.5 MB page | yes | drop as a page (§4) |

---

## 3. Traps every demo must handle, with evidence

### 3.1 An ayah is several nodes — measured

Across all 604 pages: **13,510 `g.ayah-fragment` nodes for 6,236 distinct ayahs**.
**4,458 ayahs are split across more than one node.** Anything using
`querySelector` for an ayah silently gets a fragment.

It is worse than "one per line". On **page 144**, ayah `6:128` has **35
`g.ayah-fragment` nodes on a 15-line page** — I dumped line 3 and every single word is
wrapped in its own `g.ayah-fragment`:

```
AYAH 6:125 → word 6:125:18
AYAH 6:125 → word 6:125:19
AYAH 6:125 → word 6:125:20   … nine in a row
```

Four pages are in this state — **017, 144, 535, 585** (`g.ayah-fragment` count > 3× line
count). The other 600 group normally (page 3: 24 nodes for 11 ayahs). This is
somebody else's bug to fix, not mine; the demo must be correct regardless, which
is exactly why the "always `querySelectorAll`, always `.forEach`" idiom is the
thing to teach.

### 3.2 An ayah does **not** currently span pages — correct the brief

I checked every `data-word-key` on every page: **zero ayahs have words on two pages,
and zero `data-ayah-key` values appear on two pages.** Every page ends on a complete
ayah (p105 ends `4:175:15`, p106 begins `4:176:1`, and 4:176's marker is on
p106).

So the "an ayah can span pages" warning is **not true of tonight's build**. The
demo should not teach a workaround for something that does not happen — but it
*should* be written so it would still be correct if it started happening
(collect nodes per page, then concatenate across pages), and the plan should
flag the discrepancy: either the layout genuinely never breaks an ayah across a
page in this print, or the page-membership repair is forcing whole ayahs onto
pages. **Worth one line of confirmation from whoever owns the layout stage
before we write a sentence about it on a public page.**

### 3.3 The `data-word-key` migration is live and the demo is downstream of it

Old (in shipped `index.html`): `data-surah` / `data-ayah` / `data-word`.
New (tonight): `data-word-key="2:6:1"`, `data-rasm`, and `g.ayah-fragment[data-ayah-key]`.

Consequences:
- Every code sample must read `data-word-key` and split it, or use
  `[data-word-key^="2:6:"]`.
- **CSS cannot substring-match `data-word-key`.** `[data-word-key^="2:6:"]` works for
  prefix, but "ayah 6, words 4–7" does not express in CSS from `data-word-key` alone.
  `build_embed.py` already works around this by injecting a demo-local
  `data-ayah`/`data-ge`/`data-le`; the plan should either keep that as an
  openly-labelled demo-local convenience, or drop the CSS-only range demo.
  **I lean drop** — it was the least valuable section and it is now the most
  expensive to keep.
- Anything written now must tolerate a missing attribute
  (`w.dataset.rasm ?? ''`) because the schema is still moving.

### 3.4 `geom.json` and the geometric mark-pairing are now dead weight

`template.html:633-646` pairs each ayah with its end-mark by comparing
`getBoundingClientRect()` — same line band, nearest to the left — and
`geom.json` stores a hand-measured `closes` table for the same reason.
**Both are obsolete:** `g.ayah-mark` now carries `data-ayah-key`, which states
directly which ayah it closes (verified on p3: markers `2:6`…`2:16` for ayahs
6–16; on p106 the first marker is `4:176`). Delete ~30 lines of geometry and
the `geom.json` dependency with it.

### 3.5 Header ink belongs to no word

`data-kind="header_ink"` — **5,550 paths mushaf-wide** — lives inside
`g.surah-name` and `g.basmalah`, never inside a `g.word`, and carries no
`data-word-key`, no `data-rasm-uthmani`, no ligature. So:

- "Extract the text of this page" by walking `g.word` **silently omits every
  surah title and every basmalah**. Page 106 draws two of them.
- A crop that keeps words and drops empty wrappers will drop the header, which
  is usually right for an ayah crop and wrong for a page crop.
- The surah title's *text* is available only as the `data-surah-name-ar`
  attribute on the wrapper, not as glyph-level structure.

The demo should show the header as a first-class thing — read the banner from
the wrapper, and say plainly that header ink is decorative and unsegmented.

### 3.6 Two pages have a different `viewBox`

602 pages are `viewBox="0 0 345 550"`. **Pages 1 and 2 are
`viewBox="-53.3109 -198.4777 345 550"`.** Every sample that hardcodes
`0 0 345 550` — and `template.html:1037` and `build_embed.py:144` both do —
is wrong on the two most-linked pages in the mushaf. Read the attribute.

### 3.7 Markers are drawn before the text

`<g id="ayah_markers">` is the **first** child of the page, before
`g.line` 1. Document order is therefore *not* reading order at the top level,
even though within a line it is (page 105 line 1 emits `4:171:1 … 4:171:9` in
order). Text extraction and reader views must interleave markers by their
`data-ayah-key`, not by position in the DOM.

---

## 4. Shape of the page

Structure and content only. No visual design.

### Section order

**A. What we offer** — one screen, no scrolling required.
A real mushaf page rendered live, and beside it the same page with one ayah lit.
One sentence: *the 604 pages of the Madinah Mushaf as SVG — every ayah, word and
mark addressable, searchable and styleable, and the page still renders exactly
as the source artwork.* Three facts as chips: 604 pages · 77,432 words ·
6,236 ayahs. One primary action ("search it"), one secondary ("get the files").
No project history, no counts of what we named.

Two elements below the headline are **REQUIRED, not optional** — a developer
landing page for a Quran artifact is not credible without them, and they are
each stronger than anything we could say about ourselves.

#### A1. Provenance — whose artwork this is

The first question anyone asks about a mushaf artifact is *whose text is this,
and can I trust it?* One line answers it:

> Built on the Madinah Mushaf published by the **King Fahd Glorious Quran
> Printing Complex** — مجمع الملك فهد لطباعة المصحف الشريف — as advanced vector
> artwork, from their digital mushaf portal
> <https://dm.qurancomplex.gov.sa>

Quote the Complex's own description of what they publish, in Arabic with an
English rendering beside it (reproduce the Arabic **exactly** — it is quoted
material):

> مصحف المدينة النبوية لأعمال الطباعة. مصحف المدينة النبوية على هيئة ملفات رقمية باستخدام رسم المتجهات المتقدمة Vectors إنشاء صور رقمية ذات جودة غير محدودة

> *The Madinah Mushaf for printing purposes. The Madinah Mushaf as digital files
> using advanced vector artwork — producing digital images of unlimited quality.*

**Three cautions, binding on whoever writes the copy:**

- **No endorsement, no affiliation.** State the provenance of the **artwork**
  and nothing more. The Complex did not produce, review, or approve this
  decomposition, and the page must never read as though it did.
- **State no licence.** Whether and how any of this may be redistributed is
  Abdullah's decision and possibly a legal one, and is being researched
  separately. If a "can I use this?" question is unavoidable in developer copy,
  leave a clearly-marked placeholder pointing at the licence section — do not
  invent terms, and do not let §D's "licence and attribution" bullet fill the
  gap with a guess.
- **Reproduce the Arabic and the URL character-for-character** from this plan,
  and have Abdullah check them before publishing.

#### A2. The pixel guarantee — why the trade-off disappears

Beside the provenance, as a headline claim. The developer's normal choice is
*exact print but a dead image* versus *live structure but not this print*. This
is the line that says: both.

> Every one of the 604 pages renders identically to the source artwork. Taking
> the page apart into ayahs, words and marks changes nothing about what is
> drawn.

Phrase it as a guarantee to the consumer. What backs it, stated accurately and
without overstating (`tools/audit_pixels.py`, all 604 pages, currently zero
failures — parameters read from the source: `TOL = 24`, `SEAM_PX = 10`,
`WIDTH = 1400`):

- **Contour conservation** — the multiset of drawn contours in the output is
  identical to the source: nothing added, nothing removed, nothing duplicated.
  This catches what a picture cannot show, such as a mark drawn twice in the
  same place.
- **Raster comparison against the source artwork**, so nothing has *moved*.
  Rendered at 1400 px wide (re-verified at 2200 px), tolerance 24/255, with a
  10 px seam allowance that sits inside a measured empty band: touching-contour
  anti-aliasing seams measure 1–3 px per page, while the smallest real defect
  ever found measured over 100 px. The allowance is in a genuine gap and hides
  nothing.
- **It is a gate, not a report.** It runs on every change, and a failure blocks.

**Two cautions, binding:**

- Say **"renders identically to the source artwork"**. Do **not** say identical
  to the printed book — that has not been tested.
- **Do not claim the semantic labelling is verified to this standard.** The
  pixel guarantee is about the **ink**. The naming of marks and the assignment
  of ink to words is a separate matter with separate evidence, and the two must
  never be blurred into one sentence. If the semantic agreement is worth stating
  at all, state it in its own sentence and in its own place: an independent
  decomposition (MushafDatabase) agrees with us on **77,417 of 77,422 words**.
  *Re-verify that figure before it goes on a public page* — the repository's own
  recorded figure is 67,761 of 67,765 for **line placement**, which is a
  different measurement, and `docs/defects/score_both.json` records 77,422 words
  scored. Someone must confirm which number means what before either is
  published.

Better than asserting A2 is showing it — see §2.9 for the overlay interactive,
which is the preferred form if it can be built without implying its in-browser
numbers are the audit's numbers.

**B. Why you need it** — the shortest section, and the only argumentative one.
A three-column comparison written from the reader-author's side:

| | page images | text + a font | these files |
|---|---|---|---|
| looks exactly like the source artwork | yes | no | **yes** |
| select / copy a word | no | yes | **yes** |
| search | no | yes | **yes** |
| link to an ayah | no | yes | **yes** |
| restyle marks, spacing, colour | no | partly | **yes** |
| screen reader | no | yes | **not yet — §2.8** |
| per-page line breaks you must hand-tune | n/a | **yes, 604 times** | none |

The last row is the argument. Everything else in this section is one paragraph.
Include the honest "not yet" row; it costs nothing and buys the whole table
credibility.

**C. How to use it** — the bulk of the page. Each demo is self-contained: a
visible live result, the few lines that produced it, a copy button, and one
sentence of what to watch for. In this order (each earning its place from §2):

1. Fetch a page and count what is in it *(the two-line "hello world")*
2. **Search** — in-page first, then the mushaf-wide index; the fold trap taught
   with the 2 → 2557 number
3. **Highlight ayah 2:255 and link to it** — `querySelectorAll`, the
   several-nodes idiom, and a working `#2:255` on this page
4. **Read a word** — hover for `wordKey`, four scripts, ligatures, marks
   *(this is today's inspector, reframed as "read a word", not "look how
   decomposed it is")*
5. **Pin a translation** to `data-word-key` — the 5.9 KB payload
6. **Style by meaning** — hide diacritics, waqf marks only, colour by family,
   plus the print/styled A/B slider that carries the "we never alter the print"
   guarantee
7. **Crop anything** — word / ayah / line as three components from one function
8. **Metadata off the page** — surah, juz, hizb, rubʿ, with the four-missing-
   headers caveat visible
9. **A reader** — two-page spread, keyboard turn, highlight surviving the turn

**D. What you get, and what it costs** — the practical tail, before anyone can
adopt anything:
- how to fetch (per-page URL, or the archive)
- what is in the bundle: 604 SVGs, the schema, and the index files
- **real sizes**, which I measured: mean page **770 KB raw**; page 3 is
  **736 KB raw / 187 KB gzipped**; the whole corpus **454 MB raw, ≈118 MB
  gzipped**; the search index `words.json` **3.5 MB / 792 KB gzipped**;
  `index.json` **101 KB / 15 KB gzipped**
- versioning and schema stability — and an explicit warning that `data-word-key` is
  new and the old `data-surah`/`data-ayah`/`data-word` attributes are gone
- browser support: this is plain SVG + DOM. The only modern thing used is
  `:has()` in the CSS-only tricks; the JS path needs nothing exotic
- **licence and attribution — placeholder only.** The page must **not** state
  redistribution terms for the artwork or the decomposition; that is Abdullah's
  decision and is being researched separately (§A1). This bullet is a
  clearly-marked "terms to follow" pointer plus the provenance attribution from
  §A1. Any third-party gloss (§2.3) is separate again and must be named
  independently.
- **honest limits** in their own box: no accessibility metadata in the shipped
  files yet; four surah headers untagged; `data-kind="header_ink"` is not
  segmented; four pages currently over-fragment `g.ayah-fragment`

**E. The full attribute reference** — keep today's table, updated to the real
current vocabulary (`data-word-key`, `data-ayah-key`, `data-rasm`, `data-sid`,
`data-surah-name-*`, `data-juz-start`, `data-hizb-start`, `data-nisf-start`,
`data-rubu-al-hizb-start`, `data-kind`, `data-mark`, `data-mark-family`, `data-form`,
`data-pair`, `data-iqlab`, `data-element-id`, `data-sig`), with counts. It is the page
people come back to.

### What to drop, and why

- **`nojs.html` as a separate page.** It costs **2.5 MB** — it inlines the
  792 KB embed SVG three times — to make a point about purity that no adopting
  developer is deciding on. Fold the good half into section C6 as one honest
  paragraph: *"crops and isolation also work from a plain `<img
  src="003-embed.svg#v-ayah-10">` with no JavaScript at all"*, with a live
  `<img>` beside it. That keeps the capability visible at a cost of one image
  tag. If Abdullah wants the full no-script page to survive, it should be a
  linked appendix, not a peer, and it should inline the SVG **once**.
- **The ornament gallery** → one sentence + one `<img>` in the styling section.
- **The CSS-only word-range demo** (`data-ge`/`data-le`) → drop; it depends on
  demo-local attributes that no longer follow from the shipped schema (§3.3).
- **`geom.json` and the geometric marker pairing** → delete (§3.4).

### Size budget

Today: `index.html` 783 KB, `nojs.html` 2.5 MB — **3.3 MB for the demo**.
Proposal: inline **one** page (~740 KB) for the always-visible hero and
inspector; **fetch every other page on demand** (the reader, the search results,
the second spread page). That is the same technique a real consumer would use,
so the demo demonstrates its own advice. Target: **≤ 900 KB initial HTML**,
≈220 KB over the wire gzipped, with fetches after. If the mushaf-wide search
index is included it is a separate 792 KB gzipped fetch, loaded only when the
reader types.

---

## 5. What I need that does not exist, and how we would know it is good

### Blocking, or the corresponding section cannot be honest

1. **`words.json` must actually ship somewhere fetchable.** It exists at
   `docs/shipping/out/words.json` (3.5 MB / 792 KB gz) but that directory is
   generated-on-demand and owned by another agent. Without a real URL,
   mushaf-wide search becomes an in-page-only demo — still good, much less
   impressive.
2. **A per-page gloss file.** The word-by-word-translation-translation English lives in
   `.cache/words/page-NNN.json` (50 KB/page). The demo needs the reduced 5.9 KB
   form, plus a decision on attribution and redistribution of quran.com data.
3. **A confirmation on §3.2** — does an ayah ever span a page in this print, or
   are we forcing it? One line from whoever owns the layout stage.
4. **A stable serving path.** `tools/review_server.py` serves only
   `/docs/defects` — `http://127.0.0.1:8777/docs/demo/index.html` returns
   **404** today (verified). Either add a `/docs/demo` route or standardise on
   `python3 -m http.server` from the repo root.
5. **Abdullah's sign-off on §A1** — the Arabic quotation, the portal URL, and
   the exact attribution wording. Quoted material on a public page cannot go out
   on an agent's transcription alone.
6. **The licence answer, or an explicit instruction to ship without one.** §D
   currently has a placeholder where a developer expects terms. That is
   acceptable for a preview and not for a launch.
7. **Confirmation of which MushafDatabase figure is which** (§A2): 77,417 of
   77,422 words vs the repository's recorded 67,761 of 67,765 for line
   placement. One of these goes on the page; neither goes on it unchecked.
8. **The source artwork page, shipped beside the decomposed one**, if §2.9's
   overlay is built. Roughly doubles that section's payload.

### Wanted, not blocking

9. **A `data-search` attribute** (folded rasm) emitted per word would remove the
   fold entirely. I would rather **not** have it: the fold is four lines and
   teaching it is one of the most convincing moments on the page.
10. **Accessibility behind a build flag** (§2.8) — turns an honest "not yet" into
   a headline.
11. **`g.ayah-fragment` fragmentation fixed on pages 017/144/535/585** (§3.1). Not
   blocking; the correct idiom survives it.
12. **A `data-sajdah` attribute.** The source data has `sajdah_number` per ayah
   and the emitter does not carry it. Fourteen places in the mushaf where a
   reader must draw a marker — cheap, and readers need it.

### How we would know the demo is good

- **Time to first paste.** A stranger reaches a runnable snippet in under 30
  seconds of scrolling. Measure by reading the page cold on a phone.
- **Every sample runs.** Automated: extract each `<pre>`, execute it against the
  shipped `003.svg` in a headless browser, assert the stated result. No sample
  ships that has not been executed. This is the gate that would have caught
  tonight's breakage the day the schema changed.
- **Zero console errors** on load and after exercising every control, at 360 px,
  768 px and 1440 px, in light and dark. Verified with a real browser, not by
  assertion.
- **Keyboard-only pass.** Every control reachable and operable; the reader turns
  pages with `←`/`→`.
- **Initial payload ≤ 900 KB** and the number stated on the page itself.
- **The three questions answerable from the page alone.** Hand it to someone who
  has never heard of the project and ask them: what is it, why would you use it
  instead of images or a font, and what is the first line of code you would
  write? If they can answer all three, it works.
- **Nothing on the page is about us, with exactly two exceptions.** A grep for
  "defect", "sweep", "override", "flags", "our pipeline" should come back empty.
  Our rigour is allowed to appear only as §A2's *guarantee to the consumer* —
  the ink is unchanged — preferably demonstrated (§2.9) rather than asserted.
- **Provenance and the pixel guarantee are both above the fold** (§A1, §A2),
  and the Arabic quotation and the portal URL match this plan
  character-for-character. Check both by eye, and have Abdullah confirm, before
  publishing.
- **No licence terms appear anywhere on the page** until Abdullah says what they
  are.

---

## Appendix — figures in this document, and how they were obtained

All from `/home/abdullah/Dev/github.com/AbdullahObaid/quran-svg-work` with
`QSVG_ROOT=$PWD`, against `.cache/words-svg/hafs-kfqc/*.svg` as emitted
2026-08-29 21:17–21:19.

| figure | method |
|---|---|
| 604 pages, 77,432 words, 6,236 ayahs, 13,510 `g.ayah-fragment` nodes, 4,458 split | regex scan of all 604 files |
| 0 cross-page ayahs | `data-word-key` → page set, and `data-ayah-key` → page set; both max 1 |
| 35 `g.ayah-fragment` for 6:128; pages 017/144/535/585 | per-page `g.ayah-fragment` count vs `g.line` count |
| `الله` 2 → 2557 | substring over all `data-rasm`, before and after the fold |
| 36 distinct rasm characters, 14,809 tokens | character histogram over every `data-rasm` |
| 30 juz / 60 hizb / 60 nisf / 240 rubu_al_hizb | distinct `data-*-start` values, all pages |
| 110 surah-name groups, 94 pages, missing 27/33/37/47 | `data-sid` set vs 1–114 |
| 5,550 header_ink paths | `data-kind="header_ink"` count |
| 2 pages with a shifted `viewBox` | `viewBox` histogram: 602 × `0 0 345 550`, 2 × `-53.3109 -198.4777 345 550` |
| 127/127 gloss join, 5.9 KB | join `.cache/words/page-003.json` to `003.svg` on `wordKey` |
| 736 KB / 187 KB gz; 454 MB total | `stat` + `gzip -c9` |
| index files 101 KB/15 KB, 3.5 MB/792 KB | `docs/shipping/out/*.json` |
| current demo works; rebuild throws at `template.html:637` | loaded both in a real browser over `python3 -m http.server`; console captured |
| review server 404s on `/docs/demo/` | `curl -o /dev/null -w '%{http_code}'` |
| pixel-gate parameters: TOL 24/255, seam 10 px, 1400 px, re-verified 2200 px | read from `tools/audit_pixels.py:25-27` and its docstring |
| 77,422 words scored against MushafDatabase | `docs/defects/score_both.json` → `totals.words` |
