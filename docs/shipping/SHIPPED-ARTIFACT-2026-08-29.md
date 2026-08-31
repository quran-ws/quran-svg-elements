# The shipped artifact — what we publish, and how

2026-08-29. Design and analysis only. Nothing in this document changes the
pipeline; the two proof-of-concept scripts beside it (`profile_poc.py`,
`index_poc.py`, `wordbox_poc.py`) only measure.

**The framing, from Abdullah:** *"the goal is not to publish the pipeline, the
product is the svgs."* Every recommendation below is judged by what a CONSUMER
of the files can do. Pipeline reproducibility is explicitly not a goal, and no
recommendation here is justified by "it makes our tooling easier".

Everything is measured against the build in `.cache/words-svg/hafs-kfqc/`
as of 2026-08-29 21:17 (604 pages, 454.1 MiB). Where a number is quoted, the
command that produced it is named.

---

## 0. Executive summary

1. **Size is not the axis to optimise.** 80.9 % of the bytes are path `d` data.
   Every structural choice on the table — dropping dev attributes, dropping
   ligature groups, collapsing a word to one path — moves the *brotli* total by
   at most 10 %. So the dev/production split must be argued on **meaning and
   support burden**, not on kilobytes. Measured: §2.
2. **Recommended bundle:** 604 production SVGs + 3 small index files +
   the format spec + a version manifest + the taxonomy registry.
   **70 MiB brotli / 454 MiB raw** for the pages, plus **1.4 MiB brotli** for
   everything else. §5.
3. **Recommended production profile:** keep every mark as its own `<path>`
   inside `<g class="word">`; drop only `data-eid` and `data-sig`; dissolve the
   `<g class="ligature">` wrapper. Costs 5 % of the bytes, keeps every
   capability the demo demonstrated. §3.
4. **Recommended publishing:** a GitHub repo of raw files as the canonical
   citable artifact (this is what MushafDatabase does and it works), **plus** a
   versioned CDN path for web consumers. §7.
5. **Three defects block shipping**, all found while measuring for this
   document and all verified independently:
   - the ayah-marker `data-aid` is **reversed** on 441 pages (§8.1) — the demo
     already routes around it;
   - 54 words on 51 pages sit in the wrong `<g class="line">` (§8.2);
   - 4 surahs have no `<g class="surah-name">` anywhere, and surah 17's
     basmalah is emitted as two groups (§8.3).
6. **`data-wid` is drop-in compatible with quran.com's word keys** — verified:
   1:1 = 4 words, 2:255 = 50, 77,432 in the corpus. Every word-keyed dataset in
   the open-source ecosystem (timings from `quran-align`, word-by-word
   translations, morphology) joins to our ink with no mapping table. §6b.
7. **The format documentation ships with the bundle** —
   `docs/shipping/FORMAT.md`, written for a consumer who has never seen the
   pipeline. It is a first-class deliverable, not an appendix.
8. **Licensing is Abdullah's call.** The facts are gathered in §10 — the
   upstream artwork repo carries a CC0 + KFGQPC-terms LICENSE and NOTICE.md,
   and MushafDatabase ships a "Sadaqa-e-Jaria" open-permission grant. I have
   written no LICENSE file and recommend none.

---

## 1. What the demo proves a consumer can do

`docs/demo/` was built by another agent from a single page and is the best
evidence we have of what the files support. It demonstrates, with no external
data of any kind:

hover inspection of any stroke (word text, `surah:ayah word n of N`, printed
line, ligature, kind/mark/family) · word and ligature highlight · ayah hit
regions · whole-page embed · cropping one ayah, or an arbitrary word run,
to a new `viewBox` · text extraction of the crop · recolouring by meaning
(paper / letters / marks / dots / ayah ends) · ayah emphasis · swapping the
ayah end-ornament while the printed numeral stays exactly as printed · opening
up line and word spacing · and a **script-free** twin of most of that, driven
by `<view>` elements and `:target`.

That is a strong result and it should be the headline of the README.

**What it could NOT do from the files alone**, and this is the actionable half:

| it needed | why | verdict |
|---|---|---|
| `geom.json` — 5,966 B of bounding boxes measured **in a browser** | the pipeline emits no bbox at any level. The build is not reproducible without opening the page in a browser and pasting numbers back | **ship boxes** (§5.3) |
| a hand-derived marker→ayah pairing | `data-aid` on markers is wrong (§8.1) | **fix, do not document** |
| word index within its line, words-per-line, last word of an ayah | counted by regex over document order | ship in the index |
| the ayah number split back out of `data-wid` | CSS has no substring match on an attribute | acceptable; note in the spec |
| a minted `id` per word | words carry no `id`, and `:target` needs one | **ship `id` per word** — free, enables the no-script mode |
| the page matrix `1.3333 / -55` retyped as a literal | markers live in the flipped frame, crops in viewBox units | document the frames (§6) |
| a surah NAME | at demo build time there was none. There is now (`data-surah-name-ar` etc. on the header groups) but it is only present on a surah's FIRST page | ship the page→surah index |
| Amiri from Google Fonts | `data-uthmani` is *text*, not ink; rendering it needs a font | consumer's problem, but say so |

And the one thing that is **impossible in principle**: there are no `<text>`
nodes, so browser find-in-page, text selection and copy of the Quranic text do
not work. Search must be done against an index. This is inherent to a
paths-only rendering and must be stated in the spec, not glossed.

Sizes, for calibration: `index.html` is **93.6 % SVG**; the demo's entire
HTML/CSS/JS scaffolding is 51,516 B. `build_embed.py` adds 62,005 B (+8.2 %) of
`<view>`s and CSS to one page to get the no-script behaviour — **10.4× more
than shipping the same information once as a 5,966 B sidecar**.

---

## 2. Size: measured, and why it settles the profile argument

`docs/shipping/profile_poc.py`, 31-page stratified sample (every 20th page),
extrapolated to 604. Raw / gzip -9 / brotli q11.

| profile | raw MiB | gzip MiB | brotli MiB | raw % | br % |
|---|---:|---:|---:|---:|---:|
| P0 dev, as emitted today | 429.5 | 104.3 | 66.4 | 100.0 | 100.0 |
| P1 = P0 − `data-eid`, `data-sig` | 406.3 | 98.5 | 63.3 | 94.6 | 95.3 |
| P2 = P1 − `<g class="ligature">` | 400.5 | 97.6 | 62.9 | 93.2 | 94.7 |
| P3 = P2 − `data-mark-family`, − `data-rasm/imlaei/qpc` | 392.1 | 95.7 | 61.8 | 91.3 | 93.1 |
| P4 = P2 + `fill` moved to CSS | 392.1 | 97.2 | 62.8 | 91.3 | 94.5 |
| P6 = one `<path>` per word, no marks at all | 358.9 | 94.2 | 61.9 | 83.6 | 93.2 |

Exact whole-corpus figures for P0 (all 604 pages, not sampled):
**raw 454.1 MiB · gzip 110.3 MiB · brotli 70.0 MiB**; per page 770 / 187 /
119 KiB; largest page 150 KiB brotli, smallest 37 KiB.

**The finding:** `d` attributes are **80.9 %** of all bytes (365.6 MiB of
451.7 MiB, measured over all 604 files). Destroying the entire semantic layer —
every mark, every ligature, every dev attribute — buys **6.8 % of the brotli
total**. Keeping it costs almost nothing.

### Coordinate precision — the one lever that is actually large

Rounding the numbers inside `d` only:

| precision | raw | brotli | rendered difference at 1400 px wide |
|---|---:|---:|---|
| 3 dp | 97.1 % | 96.9 % | **0 differing pixels of 3,124,800. Max delta 0/255.** |
| 2 dp | 85.3 % | **63.3 %** | 70,488 px differ (2.26 %), 4,166 of them by more than 24/255, max 51 |
| 1 dp | 71.5 % | **43.6 %** | 111,596 px differ (3.57 %), 45,782 over 24/255 |

Rendered with `rsvg-convert -w 1400` and compared with PIL, page 3.

- **3 dp is free and provably identical** — it removes binary-float tails like
  `357.86800000000005` and changes nothing. Recommend it.
- **2 dp saves 37 % of the brotli bundle** but would fail `audit_pixels` at its
  own 24/255 tolerance (4,166 pixels over it on one page). It is a real
  trade — 70 MiB → ~44 MiB — but it breaks the project's inviolable gate.
  **This is Abdullah's decision, not mine** (§9, D-4).

---

## 3. The production profile — precisely, and what it costs

### 3.1 Recommendation

```
<g class="word" id="w-2-6-2" data-wid="2:6:2"
   data-uthmani="ٱلَّذِينَ" data-rasm="ٱلذين" data-imlaei="الَّذِينَ" data-qpc="ٱلَّذِينَ">
  <path data-kind="mark" data-mark="wasla"     d="…"/>
  <path data-kind="body"                        d="…"/>
  <path data-kind="mark" data-mark="fatha"      d="…"/>
  …
</g>
```

- **One `<g class="word">` per word — this already holds.** Measured: 77,432
  word groups, 77,432 distinct `data-wid`, zero duplicates anywhere in the
  corpus. Every word in the mushaf is exactly one node. This is the single
  strongest structural property of the product and it should be the first
  sentence of the spec.
- **Marks stay separate paths** carrying `data-kind` and `data-mark`.
- **`data-mark-family` is dropped** — it is derivable from the shipped
  taxonomy registry, and the registry has to ship anyway.
- **`data-eid` and `data-sig` are dropped.** They are review-loop identity, are
  explicitly documented as *not stable across builds*, and shipping an unstable
  id invites consumers to key on it.
- **The `<g class="ligature">` wrapper is dropped.** Justification below.
- **`id="w-s-a-w"` is added** on each word, mirroring `data-wid`. Free, and it
  is the one thing the demo had to mint 127 of by hand.

### 3.2 "One element per word" — what it would mean, and why not that

Abdullah's note in `docs/TASKS.md` §5 reads "production will emit ONE element
per word, not per ligature". There are two readings and they are very different:

| reading | what it means | what it costs |
|---|---|---|
| **(a) one GROUP per word** — the ligature wrapper goes, the paths stay | every mark keeps its `data-mark`; recolouring, mark-level highlighting, dot/haraka styling all keep working | 5.3 % of raw bytes vs today (P2) |
| **(b) one PATH per word** — the whole word becomes a single `d` | `data-mark` disappears entirely; 436,708 named marks become anonymous ink | 16.4 % raw / **6.8 % brotli** — and it deletes the thing that makes this product different from a page image |

**Recommend (a).** Reading (b) buys 6.8 % of the transfer size and destroys
capabilities 8, 9 and 10 of the demo (recolour by meaning, mark styling,
ornament swap) — the capabilities that are the entire reason to ship vectors
with semantics instead of a PNG. If the argument for (b) was size, the
measurement refutes it. If the argument was simplicity, note that (a) is
*already* simpler than what a naive consumer expects: one node per word.

The ligature layer itself: dropping it is right. `docs/TASKS.md` §5 records the
measurement that no ligature-cut disagreement changes which ink a word holds
(`missing-ink 0 | boundary 0 | extent 0`), and 195 `<g class="ligature">`
groups are currently EMPTY. Shipping an empty group is a bug report waiting to
be filed by a consumer. The layer stays in the dev profile where the audits
live.

### 3.3 What is lost by the production profile, honestly

- **Mark-part / fused-mark detail.** Some signs are one contour carrying two
  marks (`fatha+hamza`) or two contours carrying one sign (muʿānaqah's three
  dots). Schema v2 solves this with logical-mark records; until phase 3 lands,
  a consumer counting `[data-mark="fatha"]` paths gets the *path* count, not
  the *sign* count. **This must be stated in the spec** and is why the
  annotation sidecar (§5.4) matters.
- **The letter/ligature boundary.** Nothing in the production file says where
  one Arabic letter ends and the next begins. Letter-level decomposition is
  future work (`docs/TASKS.md` §5) and the spec must not imply otherwise.
- **Shape signatures.** `data-sig` is how the review loop keys shapes. Nobody
  outside the project has a use for it.

---

## 4. Is there more than one artifact? Yes — two, and they are not the same file

Abdullah already ruled this (`attr_schema_v3.md` §5a): a **dev SVG**
(diagnostic profile) and a **production SVG** (public profile). This document
does not re-open it; it fills in the cut.

| | dev profile | production profile |
|---|---|---|
| audience | this project, the review loop, the audits | everyone else |
| `data-eid`, `data-sig` | yes | no |
| `<g class="ligature">` | yes | no |
| `data-mark-family` | yes | no (in the registry) |
| annotation sidecar | yes, per page | shipped once as a corpus file, optional |
| where it lives | `.cache/words-svg/` — never published | the bundle |
| size, 604 pages | 454 MiB raw / 70.0 MiB br | ~400 MiB raw / ~63 MiB br |

**Do not publish the dev profile as a "full" option.** It contains `data-eid`
values that change on every build; a consumer who keys on them will be broken
by a rebuild and will blame the format. If a research consumer wants
everything, give them the **annotation sidecar** instead — it is stable,
documented, and 8× smaller than the difference it represents.

---

## 5. The bundle — itemised, with the rule used to decide

**The rule.** A file ships if and only if a consumer needs it *to use the
SVGs*. Three exclusions follow directly and are not negotiable:
(i) anything that records where WE think the decomposition is wrong — a defect
board is an invitation to misquote our own honesty as a defect list for the
Quran; (ii) anything that records a human's private working state; (iii)
anything whose value depends on being regenerated (caches, sweeps, baselines).

### 5.1 SHIP

| item | what | size |
|---|---|---|
| `pages/001.svg` … `604.svg` | the product, production profile, flat, zero-padded 3 digits (same convention as MushafDatabase) | ~400 MiB raw / 63 MiB brotli |
| `FORMAT.md` | the format specification — see `docs/shipping/FORMAT.md` | ~60 KB |
| `README.md` | what this is, one worked example, how to cite, where the artwork comes from | ~10 KB |
| `index.json` | edition manifest + page→(surahs, first/last ayah, word count) + juz/hizb/rubʿ starts + sajdah sites + the 114 surah records | **99 KiB raw / 10 KiB brotli** |
| `words.json` | 77,432 rows of `[wid, page, rasm, imlaei]` — the search index | **3,497 KiB raw / 478 KiB brotli** |
| `wordboxes.json` | 77,432 rows of `[wid, line, x0, y0, x1, y1]` in page viewBox units | **3,118 KiB raw / 896 KiB brotli** |
| `mark-taxonomy.json` | the 36 mark names, their category, family and features — a consumer cannot interpret `data-mark` without it. Copy of `.cache/schema/mark-taxonomy.v2.json` | 4 KiB |
| `VERSION.json` | see §5.5 | < 1 KiB |
| `CHECKSUMS.txt` | sha256 per file | ~50 KiB |

`index.json`, `words.json` and `wordboxes.json` are built by
`docs/shipping/index_poc.py` and `docs/shipping/wordbox_poc.py` and the sizes
above are real measurements of the files they wrote.

**Total index + docs: 6.7 MiB raw, 1.4 MiB brotli** — 2 % of the bundle for
every capability in §6 that the SVGs alone cannot provide.

### 5.2 Brotli copies — ship them, but not in the git repo

`mushafs/hafs/kfqc/svg-br/` already proves the pattern: 722 `.br` files,
71.0 MiB against 413.9 MiB raw. For our pages the equivalent is
**70.0 MiB brotli against 454.1 MiB raw — 6.5× smaller**.

- **In a git repo:** ship raw only. Pre-compressed blobs do not delta-compress,
  so committing both doubles the clone forever, and GitHub already serves
  gzip on raw fetches.
- **On a CDN:** ship `.br` (and `.gz` as fallback), served with
  `Content-Encoding`. This is where the 6.5× actually reaches the user.
- **In a release tarball:** the tarball's own compression does the job; do not
  include `.br` inside it.

### 5.3 Why boxes, specifically

A consumer cannot highlight, crop, or hit-test a word without knowing where it
is. Today that requires parsing path data and composing three transforms — I
wrote it (`wordbox_poc.py`, 157 lines) to prove it is possible, and it is, but
it is 60 s of CPU for the corpus and it is the *fourth* time this project has
written that code (the demo measured it in a browser instead). 896 KiB brotli
removes the need permanently.

Caveat to document: the POC boxes are the **control-point hull** of the path
data, a slight superset of the true outline. A production builder must take
exact extents from the pipeline, which already computes them.

### 5.4 The annotation sidecar — ship a corpus-level subset, not 604 files

`.cache/annotations/NNN.json` already exists (schema v2 phase 1) and is
**75.2 MiB** over 604 files. On page 3 the split is: `marks` 101,489 B (84 %),
`words` 18,148 B, `ayat` 984 B, `surahs` 241 B, `relations` 68 B.

- The `words` / `ayat` / `surahs` / `relations` part is small and useful →
  it is what `index.json` and `words.json` above are built from.
- The `marks` part duplicates, in JSON, information already in the SVG, plus
  boxes. Shipping it at 75 MiB alongside a 400 MiB bundle is a 19 % increase
  for a research audience that has not asked yet.

**Recommend:** ship the derived indexes now; offer the full per-page annotation
JSON as a **separate optional download** if anyone asks. Do not put it in the
default bundle.

### 5.5 Versioning — what a consumer pins to

```json
{
  "schema": "quran-svg-bundle",
  "version": "1.0.0",
  "edition": "hafs-kfgqpc",
  "print": "KFGQPC Madani mushaf, V2 1441H",
  "pages": 604, "words": 77432, "ayat": 6236, "surahs": 114,
  "profile": "production",
  "format_spec": "FORMAT.md@1.0",
  "built": "2026-08-29",
  "text_sources": ["uthmani (quran.com)", "KFGQPC waqf", "DigitalKhatt budgets"],
  "layout_source": "DigitalKhatt QPC v2 1441H layout DB",
  "gates": {"pixel_identical_pages": 604, "taxonomy": "ok", "mark_flags": 0}
}
```

Also stamp the root of every SVG: `data-bundle-version="1.0.0"` and
`data-page="3"`. MushafDatabase does exactly this with `data-md-version` and it
is why its two directories can be told apart at a glance. Today our root
carries **no** version, no page number and no `id` — the demo had to add an
`id` itself in three places.

Semantic versioning with a stated contract:
- **patch** — path data or mark labels corrected, no attribute added or removed;
- **minor** — attributes or files added, nothing removed or renamed;
- **major** — anything removed or renamed. `FORMAT.md` carries the same major.

### 5.6 DO NOT SHIP — and why

| item | size | reason |
|---|---|---|
| `.cache/review/` | 18 MiB | 250 human geometry overrides, `decisions.jsonl`, `eid_flags.jsonl` — Abdullah's private working state, keyed on unstable eids |
| `docs/defects/*` | 55 MiB | internal defect boards naming specific pages and words as suspect. Publishing them publishes a list of "places the Quran is drawn wrong in our file", stripped of the context that most are our artefacts |
| `scratchpad/` | — | measurement scripts, bench, sweeps |
| `tools/` | — | the pipeline. Not the product (Abdullah's framing) |
| `.cache/sweeps/`, `.cache/confidence/`, `.cache/marktype/` | 439 MiB | regression memory; meaningless outside the repo |
| `.cache/marks/labels.json` + backups | 1.8 MiB | shape→label table. Internal; the taxonomy registry is the public form |
| `mushafs/` (the pinned artwork clone) | 495 MiB | upstream's artifact, not ours to redistribute as ours. Link to `quranpedia/quran-svg` instead |
| `.cache/words*`, `.cache/digitalkhatt/` | 85 MiB | third-party text and layout sources with their own terms (§10 D) |
| `.cache/annotations/` | 75 MiB | see §5.4 — optional, not default |
| `docs/demo/` | 4 MiB | **undecided.** It is the best advertisement we have, but `index.html` is currently broken against the new schema (§8.4). Ship it only after it is rebuilt and verified |

### 5.7 Bundle totals

| option | raw | brotli / compressed | notes |
|---|---:|---:|---|
| **A. pages only** | 400 MiB | 63 MiB | not recommended — no way to find a page |
| **B. pages + indexes + docs (RECOMMENDED)** | 407 MiB | 64 MiB | everything in §5.1 |
| **C. B + per-page annotation JSON** | 482 MiB | ~80 MiB | research option, on request |
| **D. B at 2 dp coordinates** | 347 MiB | **41 MiB** | 37 % smaller, breaks the pixel gate — Abdullah's call (§9 D-4) |

For scale: MushafDatabase ships **380 MiB per version directory, raw, no
compressed copies, no index**, and its repo is 883 MiB with two versions and
a shallow `.git`.

---

## 6. Capability matrix — what a consumer can do, and what enables it

"Ships" = present in the recommended production bundle. Selectors are real and
run against a real page.

| capability | what makes it possible | status |
|---|---|---|
| **Render a page** | the SVG. Fixed `viewBox`, all ink one colour | ✅ today |
| **Extract the text of a page, ayah or word** | `data-uthmani` / `data-rasm` / `data-imlaei` / `data-qpc` on 77,432 word groups | ✅ today |
| **Address a word** | `data-wid="2:6:3"` — globally unique, 77,432/77,432 | ✅ today |
| **Highlight an ayah** | `[data-aid="2:255"]` on `<g class="ayah">` | ✅ today, but see the fragment caveat below |
| **Highlight a word / a run of words** | `[data-wid]`, plus `id="w-2-6-3"` for `:target` | ⬅ needs the `id` (§3.1) |
| **Hit-test / hover a word without rendering** | `wordboxes.json` | ⬅ needs the index |
| **Crop to an ayah or a word run** | filter by `data-aid`/`data-wid`, recompute `viewBox` from the boxes | ⬅ needs the index (the demo used a browser) |
| **Search for a word** | `words.json` (rasm + imlaei per wid) → resolves to a page and a `data-wid` | ⬅ needs the index. **Impossible in the SVG itself** — there are no `<text>` nodes |
| **Find the page of an ayah** | `index.json` page index | ⬅ needs the index |
| **Render a range "2:255 → 2:257"** | `index.json` gives the pages; `data-aid` selects the fragments | ⬅ needs the index |
| **Style marks vs letters vs dots** | `data-kind="mark|body"`, `data-mark`, and the taxonomy registry for families | ✅ today |
| **Count the diacritics of a word** | `[data-mark]` paths inside the word | ⚠️ **paths, not signs** — fused and split marks make the two differ (§3.3) |
| **Reach an ayah's end-marker** | `<g class="ayah-marker" data-aid>` | ❌ **broken — reversed on 441 pages** (§8.1) |
| **Know surah / juz / hizb / rubʿ** | `data-surah-name-*` on header groups; `<g class="hizb-mark">` with `data-juz/-hizb/-rub/-nisf`; `index.json` | ⚠️ header attrs only on a surah's first page; the index closes it |
| **Know the reading line of a word** | `data-line="1".."15"` | ⚠️ wrong for 54 words on 51 pages (§8.2) |
| **Build a reader** | all of the above | ⬅ after the three fixes |
| **Letter-level anything** | — | ❌ not in scope; `docs/TASKS.md` §5 |
| **Audio / translation / tafsir / word timings** | — | ❌ out of scope, consumer supplies |

### Worked examples

```js
// the page SVG is inlined or fetched into `doc`
// 1. highlight ayah 2:255 — NOTE: several fragments, one per printed line
doc.querySelectorAll('g.ayah[data-aid="2:255"]')
   .forEach(g => g.classList.add('hl'));

// 2. the third word of that ayah
doc.querySelector('g.word[data-wid="2:255:3"]');

// 3. read the text of the whole ayah, in reading order
[...doc.querySelectorAll('g.word')]
  .filter(w => w.dataset.wid.startsWith('2:255:'))
  .map(w => w.dataset.uthmani).join(' ');

// 4. paint the dots differently from the harakat
//    (family comes from mark-taxonomy.json: dot|two-dots|three-dots => "dots")
doc.querySelectorAll('path[data-mark="dot"],path[data-mark="two-dots"],'
                   + 'path[data-mark="three-dots"]')
   .forEach(p => p.setAttribute('fill', '#b03030'));

// 5. every word of the 15th printed line
doc.querySelectorAll('g.line[data-line="15"] g.word');
```

```python
# 6. search, against the shipped index — no SVG needed
rows = json.load(open("words.json"))["rows"]           # [wid, page, rasm, imlaei]
hits = [r for r in rows if r[2] == "الرحمن"]
# -> [['1:3:1', 1, 'الرحمن', 'الرَّحْمَٰنِ'], ...]  then fetch pages/001.svg

# 7. where is 2:255?
idx  = json.load(open("index.json"))
page = next(p["page"] for p in idx["page_index"]
            if p["first_ayah"] <= "2:255" <= p["last_ayah"])   # compare numerically
```

```css
/* 8. script-free: dim everything except one ayah */
svg:has(g.ayah[data-aid="2:255"]) g.word { opacity: .25 }
svg g.ayah[data-aid="2:255"] g.word      { opacity: 1 }
```

---

## 6b. Who would use this, and what they need

Grounded in `github.com/tarekeldeeb/awesome-islamic-open-source-apps` — 170
open-source Quran projects, read 2026-08-29. Named projects below are real
entries from that list with their star counts, used as example consumers.

### The interoperability fact that makes all of this cheap

**Our `data-wid` is drop-in compatible with quran.com's word keys.** Verified
against the emitted files: 1:1 has 4 words, 2:255 has 50, surah 1 has 29, and
the corpus has **77,432** words — the same numbering and the same totals the
quran.com API, `quranwbw`, `Word-By-Word-Quran-Android` and `quran-align` all
use. A consumer already holding word-keyed data (timings, translations,
morphology) can join it to our ink with no mapping table. This should be the
second sentence of the README.

### Demand → what we serve

| recurring need in that ecosystem | example consumers | do we serve it? |
|---|---|---|
| **Mushaf-page rendering with real layout** | `quran_android` ⭐2192, `quran-ios` ⭐506, `quran.com-frontend` ⭐1023, `quran.com-images` ⭐448, `quran-pages-images`, `mushaf-imad-expo` | **Yes, and this is the strongest case.** These projects ship *raster page images* (quran.com-images is a whole repo of them) or hand-tune line breaks. We ship the real page geometry as vectors: resolution-independent, recolourable, and addressable. Nothing else in that list does this. |
| **Word-by-word display and word-level audio sync** | `quranwbw` ⭐76, `quranwbw.com`, `Word-By-Word-Quran-Android` ⭐97, `quran-align` ⭐229 (produces per-word timings) | **Yes.** `quran-align` emits `(surah, ayah, word)` timings; `data-wid` is that key exactly. Highlighting the current word during recitation is one selector. Today they highlight a *text* span; with our files they can highlight the actual printed ink. |
| **Search and verse lookup** | `alfanous` ⭐267, `quran-cli`, `quranize`, `quran-search-engine`, `lafzi-web`, `quranlookup` ⭐50 | **Only via the index.** There are no `<text>` nodes, so find-in-page is impossible in the SVG. `words.json` (478 KiB brotli) gives rasm + imlaei per `data-wid` and resolves a hit to a page. Honest boundary: we are not a search engine; we are what a search result can *point at*. |
| **Memorisation / hifz tools** | `quran_memorization_helper` ⭐27, `AyatuRabbi_Quran` ⭐17, `AL-Khatma` ⭐14, `qari-stats` | **Yes, unusually well.** Hide-and-reveal is a CSS rule on our structure: `g.word[data-wid^="2:255:"] { visibility: hidden }`, or reveal word by word by `data-wid` ordinal. Today these apps re-render text; with our files the *printed page the user memorised from* stays on screen with words masked. That is a materially better memorisation experience and it needs nothing new from us. |
| **Tajweed colouring** | `quran-tajweed` ⭐157, `tajweed` ⭐72, `TajweedParser` ⭐26, `colorful-quran` ⭐72 | **Partial — this is the honest one.** These tools emit rules as *character ranges in the uthmani text*. Mapping a character range to ink needs **letter-level** decomposition, which we do not have (§3.3). What we *can* colour directly is anything that is a named mark: `meem-iqlab` (iqlab, 609 sites), `shadda` (ghunnah), `maddah` (madd, 5,376), the `sifr` family (silent letters, 4,054), and every waqf sign. That already covers several tajweed classes with zero work. Full letter-level tajweed is blocked on the letter work in `docs/TASKS.md` §5. |
| **Multiple translations, tafsir** | `quran-api` ⭐784, `tafsir_api` ⭐109, `quran-json` ⭐471/⭐341, `quranic-universal-library` ⭐586 | **Out of scope, and correctly so** — but joinable, because `data-aid`/`data-wid` are the same keys those datasets use. We should say "bring your own translation" explicitly rather than leave it ambiguous. |
| **Audio recitation** | `audio.quran.com` ⭐140, `quranicaudio-app` ⭐82, `QuranFM` | **Out of scope.** The join key is `data-aid`. |
| **Offline access** | `quran_android`, `the-holy-quran-app` ⭐852, `Quran-Flutter` ⭐230 | **Yes, with a caveat: size.** 70 MiB brotli for the whole mushaf is fine for a desktop app and heavy for a phone. Per-page fetch is the right shape (119 KiB brotli per page). A mobile consumer wanting the whole thing offline is the one case where the 2 dp option (§9 D-4, 44 MiB) would matter. |
| **Quranic text validation** | `quran-validator` ⭐173, `PyQuran` ⭐144, `quran-words` ⭐11, `QURAN-NLP` ⭐117 | **Yes, and in a new way.** We are the only dataset in that list that ties text to *the ink of a specific printed edition*. `quran-validator` validates text against text; our files let it validate text against what a mushaf actually draws. Niche, but nobody else offers it. |
| **Video / image generation** | `QuranVideoMaker` ⭐33, `quran-image-generator` ⭐13, `Quran-Video-Studio` ⭐16, `QuranCaption` ⭐34 | **Yes — and the demo already proves it.** Cropping to an ayah or a word run and re-writing the `viewBox` is exactly what these tools need, at any resolution, with correct calligraphy. Today they render text with a font. This is probably the fastest-to-adopt use. |
| **Prayer times, qibla, hadith** | 61 projects in that list | Out of scope entirely. |

### Candidate adjacent artifacts

Ordered by (value to that ecosystem) ÷ (work). "In bundle" vs "separate" is my
recommendation; the ones marked ★ are decisions for Abdullah.

| artifact | what it needs from us | where | effort |
|---|---|---|---|
| **Search index** (`words.json`) | already built — `index_poc.py` | **in bundle** | done |
| **Word box index** (`wordboxes.json`) | exact extents from the pipeline instead of my control-point hull | **in bundle** | small |
| **Page/ayah index** (`index.json`) | already built | **in bundle** | done |
| **Word-timing overlay** keyed to `data-wid` | nothing from us — a consumer joins `quran-align` output directly. We should ship a 20-line *example*, not the data | README example | tiny |
| **Mark-level tajweed stylesheet** — a CSS file colouring `meem-iqlab`, `shadda`, `maddah`, `sifr-*`, waqf signs | nothing new; it is a stylesheet over existing attributes | **separate artifact**, linked from the README | small ★ (is a tajweed opinion ours to publish?) |
| **Memorisation demo** — mask/reveal by `data-wid` | nothing new | example in the README or the demo page | tiny |
| **Crop service / library** — "give me 2:255 as a standalone SVG" | word boxes + the polygon-removal rule; the demo already implements it in JS | **separate artifact** (a small JS/Python package) | medium |
| **Per-ayah pre-cropped SVGs** | the crop library, run over 6,236 ayahs | separate download; do NOT put 6,236 more files in the bundle | medium |
| **Accessibility layer** — `<title>` per word, `role`, `aria-label` on the page | the emitter adds `<title>` from `data-uthmani`; the demo already mints 127 per page | **in the production profile** — but measure the size first (≈4 KiB/page, +2.5 MiB corpus) | small ★ |
| **Full letter-level decomposition** | the hard work in `docs/TASKS.md` §5 | future major version | large |
| **Warsh / Qalun / other riwayat** | the pipeline ports (memory: `quran-svg-warsh-portability`); only the word source and mark labels are Hafs-specific | future editions in the same format | large |

### Where our boundary is — say this plainly in the README

We do **not** provide: translations, tafsir, audio, word timings, tajweed rule
data, prayer times, or a search engine. We provide **the printed page, with
every word and every mark addressable by the same keys those datasets already
use.** That is a clearer and more defensible product statement than trying to
be a Quran platform, and it is what makes 170 existing projects potential
consumers rather than competitors.

---

## 7. How to publish it

### The reference product, examined

`MushafDatabase-Ligature-Based-SVG` is the closest existing example and it is
instructive:

- **flat directories per version** — `SVG V1.0/` and `SVG V1.01/`, 604 files
  each, `001.svg`…`604.svg`, 380 MiB apiece. Both versions live in the same
  repo; the working tree is 763 MiB and the repo 883 MiB.
- **no manifest, no index, no compressed copies, no git tags.** Versioning is
  by directory name plus `data-md-version="1.01"` on the root.
- **one 928-line README that is the entire format specification** — 21
  numbered sections including a normative validation-rules section, JavaScript
  query examples, a page skeleton, and a complete attribute reference.
- a 704-byte `LICENSE`.

The README is the thing to learn from. The two-versions-in-one-repo layout is
the thing to avoid: it doubled the repo permanently.

### Options

| option | one page | whole set | versioning | verdict |
|---|---|---|---|---|
| **GitHub repo, raw files** | `raw.githubusercontent.com/…/pages/003.svg`, gzip on the wire | `git clone` = 407 MiB, or a tag tarball | git tags | **canonical artifact** |
| **Release tarball on a tag** | ✗ (must take the whole thing) | one download, ~64 MiB compressed | the tag | **ship alongside** |
| **CDN (jsDelivr over the same repo/tag, or a bucket)** | one fetch, brotli, immutable | 604 fetches | the tag in the URL | **for web consumers** |
| **npm package** | bundler-friendly, but 407 MiB in `node_modules` is hostile | ✗ | semver | **only for the indexes**, if at all |
| **static site that documents and serves** | ✓ | ✓ | whatever it is built from | **later**, built on the demo |

### Recommendation

1. **A dedicated GitHub repo** — `quran-svg-hafs-kfgqpc` or similar. Not this
   repo: this one holds the pipeline, the review state and the defect boards,
   and Abdullah's framing is that those are not the product. A separate repo
   also lets its issue tracker be about the *files*.
   Layout, flat and boring:
   ```
   README.md  FORMAT.md  LICENSE(?)  VERSION.json  CHECKSUMS.txt
   pages/001.svg … pages/604.svg
   index/index.json  index/words.json  index/wordboxes.json
   index/mark-taxonomy.json
   ```
   One version per tag, **never two version directories in one tree**.
2. **A git tag per release** (`v1.0.0`) with a GitHub Release carrying two
   assets: `quran-svg-hafs-kfgqpc-1.0.0.tar.zst` (~64 MiB) and
   `…-indexes-1.0.0.tar.gz` (~1.4 MiB, for consumers who only want to search).
3. **CDN by jsDelivr over the tag** — zero infrastructure, and the URL pins the
   version by construction:
   `https://cdn.jsdelivr.net/gh/<owner>/<repo>@v1.0.0/pages/003.svg`.
   jsDelivr serves brotli and sets `cache-control: max-age=31536000, immutable`
   on tagged paths. **Never publish a `@main` URL as the documented one** — an
   immutable cache plus a moving branch is how consumers get silently stale
   files. If a self-hosted bucket is preferred later, the same rule holds:
   version in the path, `immutable` on versioned paths, `no-cache` on
   `latest/`.
4. **What a consumer pins to:** the tag. `VERSION.json` and the root
   `data-bundle-version` let them check what they actually have offline.
5. **Communicating updates:** a `CHANGELOG.md` keyed to the semver contract in
   §5.5, plus the GitHub Releases feed. State the contract explicitly —
   "a patch release never changes an attribute name" is the promise consumers
   actually need.

---

## 8. Defects found while measuring — these block a 1.0

All four were found while writing this document and all are verified here, not
taken from another agent's report.

### 8.1 The ayah-marker `data-aid` is reversed on 441 of 604 pages — BLOCKER

Page 3, root matrix `matrix(1.3333 0 0 -1.3333 -55 640)` (y is flipped, so
screen y = 640 − 1.3333·y). Converting each marker's own translate:

```
marker data-aid="2:6"   -> screen y 523.8   (bottom of the page)
marker data-aid="2:16"  -> screen y  57.9   (top of the page)
```

But ayah 2:6's words are on printed lines 1–2 at screen y ≈ 37–49, and 2:16's
are on lines 14–15 at y ≈ 490+. **The labels are in exactly reversed order.**

Swept over all 604 pages by sorting each page's markers by `data-aid` and
checking whether screen y increases (reading order is top to bottom):

```
strictly REVERSED      441 pages
mixed (two markers on one line, so not strictly monotonic)  160
strictly ascending       2 pages   (84, 162)
too few markers          1
```

`tools/assign_words.py:3222` (`tag_ayah_markers`) states the assumption in its
own docstring — *"Markers appear in ayah order"* — and zips the page's sorted
ayah list onto the marker group in document order. The artwork's marker layer
is in bottom-to-top document order on almost every page.

The demo agent found this independently and routed around it geometrically
(`template.html:630-646`), which is why nobody noticed. **This is the single
most consumer-visible defect in the product** — the ayah↔marker link is one of
the headline capabilities, and it is wrong nearly everywhere. It should go in
`docs/defects/reported.json` and be fixed before any publication.

### 8.2 54 words are in the wrong `<g class="line">` — 51 pages

Within each printed line, the words are in ascending `data-wid` order on
**9,046 of 9,046 lines**. But across line boundaries the sequence breaks on 51
pages, 54 times. Verified geometrically against `wordboxes.json`:

- p2 `2:4:11` is tagged `data-line="7"`; its box is y 137.98–162.00, the same
  band as line 6's words (134.94–159.99), and its x sits between line 6's
  `2:4:12` and `2:4:10`. It is drawn on line 6.
- p8 `2:54:22` is tagged line 9; its box (y 325.9–358.9) is squarely in line
  10's band (328–360) and its x falls between `2:54:21` and `2:54:23`.
- p42 `2:255:23` is tagged line 11; drawn on line 10.

Pages: 2, 8, 38, 42, 51, 56, 61, 77, 80, 86, 96, 103, 109, 110, 113, 114, 116,
122, 131, 137, 170, 182, 184, 199, 211, 212, 213, 214, 224, 231, 246, 269, 276,
317, 380, 381, 408, 427, 431, 435, 451, 454, 471, 475, 480, 510, 512, 542, 549,
552, 584.

This overlaps `docs/defects/reference_confirmed.json` (p131 is on both lists)
but is 13× larger than the four confirmed line errors. **The reading-order
test is a new, cheap, whole-corpus detector and costs nothing to run** — it
needs no reference decomposition and no eye.

### 8.3 Header groups are incomplete and inconsistent

- **4 surahs have no `<g class="surah-name">` anywhere in the corpus**: 27, 33,
  37, 47. Their start pages (377, 418, 446, 507) carry a `basmalah` group and
  18–28 `header-ink` paths, but no name banner group. On p2, by contrast, both
  groups exist and carry 45 header-ink paths between them.
- **Surah 17's basmalah is emitted as two groups** on p282 — one holding 1
  path, the other 31. That is why the corpus has 113 `class="basmalah"` groups
  for 112 distinct `data-sid`. `edition-hafs-kfgqpc.json` expects
  `basmalah_groups: 113`, so the manifest currently encodes the split as if it
  were correct.
- Consequence for a consumer: `svg >>> g.surah-name[data-sid="27"]` returns
  nothing, and counting basmalahs gives 113 for 112 surahs.

### 8.4 The demo is broken against the current schema

`docs/demo/index.html` and `template.html` still read `data-surah` /
`data-ayah` / `data-word`; the emitter now writes `data-wid` / `data-aid`. The
selector at `template.html:637` returns `null` and throws, killing the script.
`build_embed.py` was updated, `build.py`/`template.html` were not. If the demo
is to ship as the advertisement (§5.6) it must be rebuilt and opened first.

### 8.5 Element order inside a word is not right-to-left yet

Measured: **77,432 words, 15,160 (19.6 %) have their paths in descending x**.
Word order within a line is correct (9,046/9,046 lines ascending by `data-wid`).
The brief says a concurrent agent is landing RTL element ordering; it is not in
this build. `FORMAT.md` documents the current state and must be updated when it
lands — a spec that promises an order the files do not have is worse than one
that admits it.

---

## 9. Needs Abdullah's decision

Nothing below is decided here.

**D-1. Does production keep marks as separate paths?** §3.2 lays out the two
readings of "one element per word". My recommendation is (a) one *group* per
word with marks kept as paths, because (b) buys 6.8 % of the brotli bundle and
deletes the product's differentiator. But "one element per word" is his phrase
and (b) is a legitimate reading of it.

**D-2. Does the demo ship?** It is the best advertisement we have and it is
currently broken (§8.4). Rebuild-and-ship, or keep it internal?

**D-3. One repo or two?** Recommending a separate publication repo so the
pipeline, the review state and the defect boards never travel with the product.
That is a workflow change and his to make.

**D-4. Coordinate precision.** 3 dp is free and proven pixel-identical — I
propose taking it. **2 dp cuts the bundle from 70 MiB to 44 MiB brotli** but
changes 2.26 % of rendered pixels on page 3, 4,166 of them past `audit_pixels`'
own 24/255 tolerance. Pixel identity is described in `docs/TASKS.md` as
inviolable, so this is not mine to trade.

**D-5. Licensing and attribution.** Facts in §10. I have written no LICENSE
file and make no recommendation.

**D-6. Do the three blockers (§8.1–8.3) gate 1.0, or does 1.0 ship with them
documented as known limits?** My view is that §8.1 gates it — a wrong ayah
link is worse than a missing one. §8.2 and §8.3 could ship as documented
limits. His call.

**D-7. Does `docs/defects/reported.json` get the §8.1 and §8.2 findings?** They
are pipeline defects found by an agent, and the house rule is that eye reports
go there. I have not written to it — another agent's territory and his file.

---

## 10. Licensing — facts only

Researched from the repos on this machine. **No recommendation, no LICENSE
file written.**

### The upstream artwork — `quranpedia/quran-svg`

There IS a licence. Three tracked files: `LICENSE`, `NOTICE.md`, `README.md`.

`LICENSE` header, verbatim:

> **OUR ORIGINAL CONTRIBUTION — CC0 1.0 (Public Domain Dedication)**
> All original content created by this project is dedicated to the public
> domain under CC0 1.0 Universal: the ayah-polygon hit-layer
> (`<path class="ayahPolygon">` overlays), the JSON metadata (per-page
> polygons, surah.json, markers.json), and the repository structure and
> tooling.
>
> **IMPORTANT — the underlying mushaf editions are NOT ours to license.**
> The rendered mushaf page glyphs / calligraphy embedded in the SVG files come
> from the publishers' printed editions and are governed by THEIR terms…
>
> King Fahd Glorious Qur'an Printing Complex — Mus'haf al-Madinah: The Complex
> grants FREE use of its digital Mus'haf for personal use, all individual
> businesses, governmental departments & agencies, private and national
> institutions, Qur'an printing, digital publishing, media use, websites,
> software, and similar — inside and outside Saudi Arabia. The ONLY
> restriction: PRINTING physical Qur'ans (or importing printed ones) for the
> purpose of commercial SALE is reserved to the Complex, per Saudi Royal
> Decrees No. 136/8 (1/2/1406 AH) and No. 9/B/46356 (28/9/1424 AH).

`NOTICE.md` §2.1 quotes the Complex's own stated usage rights at length
(approval of the Minister of Islamic Affairs; "these formats **can be used for
free** in all personal and individual businesses… Qur'an printing\*, digital
publishing, media use, and use in websites, software, and other similar
intermediates", with the footnote restricting commercial print-for-sale), and
§1 states the Qur'anic text "is not subject to copyright… however it must never
be altered, truncated, or misrepresented".

The upstream SVG and JSON files themselves carry **no** copyright or licence
string.

### The reference product — MushafDatabase

`LICENSE`, 704 bytes, complete text:

> **Legal Use and Open Permission (Sadaqa-e-Jaria)**
> This dataset is released as Sadaqa-e-Jaria for the benefit of Muslims
> worldwide. Permission is hereby granted to any person, without prior written
> approval, to use, copy, modify, publish, distribute, and create derivative
> works from this dataset, in whole or in part, for any lawful purpose,
> including personal, educational, research, nonprofit, and commercial use.
> Users must not knowingly alter the Quranic content in any way that
> misrepresents or compromises the integrity of the Holy Quran. This dataset is
> provided "as is", without warranty of any kind…

No SPDX identifier. The same text is repeated as README §20. Its KFGQPC
attribution is one sentence in README §1 naming the Madinah Mushaf, the
Complex, and the source portal `https://dm.qurancomplex.gov.sa/` — **no quoted
permission grant, no decree reference**. Publisher: Altara Innovation Group,
`info@altara.id`, `https://mushafdatabase.com/`.

### This repository

**There is no LICENSE, COPYING or NOTICE file** in `quran-svg-pipeline`, tracked
or untracked. A grep for `Copyright|copyright|حقوق|ملك فهد` across all
`.md/.py/.json/.html` outside `.cache/` returns exactly one line, and it is
descriptive prose (`docs/semantic-decomposition.md:51`). No `license` key in
`edition-hafs-kfgqpc.json`.

### Third-party inputs that would need their own notice

- **`DigitalKhattV2.otf`** — name table: `Copyright (c) 2020-2024 Amine Anane,
  Copyright © 2024 Tarteel Inc.`, licensed **SIL Open Font License 1.1**
  (nameID 13/14). Not currently shipped; if a rendering demo ever embeds it,
  OFL requires the licence to travel with it.
- **The DigitalKhatt DBs** (`.cache/digitalkhatt/*.db`) carry no licence data
  at all — no README, no licence file, no licence strings.
- **`tools/data/qiraat-ayah-map/`** — MIT, attributed in its own `SOURCE.md`.
- **Text sources**: quran.com `text_uthmani`, the KFGQPC text, and the
  DigitalKhatt text all have their own terms not examined here.

### The open questions, for Abdullah

1. Can this decomposition be redistributed at all, and under what terms? The
   upstream's reading is that KFGQPC's grant covers digital/software/web use
   and restricts only physical print-for-sale. That is the upstream's summary
   of the Complex's words, not a legal opinion, and this bundle is a
   *derivative* of that artwork.
2. If it ships, what does the attribution say, and where — a `LICENSE`, a
   `NOTICE.md` mirroring the upstream's, a line in the README, or a
   `<metadata>` block in every SVG?
3. Does our own contribution (the decomposition, the labels, the indexes) get
   its own licence separate from the artwork, as `quranpedia/quran-svg` does
   with CC0?
4. MushafDatabase's "Sadaqa-e-Jaria" grant is a precedent for exactly this
   product. Is that the model?

---

## Appendix — how every number here was produced

| number | command |
|---|---|
| profile sizes | `python3 docs/shipping/profile_poc.py` (31-page sample driver in the doc) |
| corpus raw/gzip/brotli | parallel `gzip.compress`/`brotli.compress` over all 604 emitted pages |
| `d`-attribute share | regex sum of `d="…"` lengths over all 604 pages |
| coordinate-rounding pixels | `rsvg-convert -w 1400` + PIL `ImageChops.difference`, page 3 |
| index sizes | `python3 docs/shipping/index_poc.py` |
| box index | `python3 docs/shipping/wordbox_poc.py --all` |
| marker reversal | per-page marker translate → screen y via the root matrix, sorted by `data-aid` |
| line-order breaks | per-line `data-wid` sequence, confirmed against `wordboxes.json` |
| header coverage | `data-sid` scan over all 604 pages |
| licence facts | verbatim quotes from `LICENSE`, `NOTICE.md`, `README.md` in each repo; `fontTools` name table for the OTF |
