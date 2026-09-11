# Quran SVG Elements

**Printed Qurʾān pages as vector artwork with the ink taken apart: every word is a group you can select, and every diacritical mark is its own named shape.**

A *muṣḥaf* is a physical printed copy of the Qurʾān. This repository publishes 604 pages of one — the King Fahd Complex Madani print, V4 1441H — as SVG files that look exactly like the paper, and that a browser can address. Ask for word 3 of verse 2:255 and you get the shapes the printer laid down for it. Ask for every `hamzat_al_wasl` on the page and you get 14 paths, in one CSS selector, with no glyph analysis and no text layer.

| Package | Version | Pages | Addressable words |
|---|---|---|---|
| not published yet — download the release bundle | `v1.0.0` (bundle, built 2026-09-09) | 604 | 77,432 |

<sub>Terms: a **muṣḥaf** is a printed copy of the Qurʾān; a **riwayah** is one named transmitter's version of a canonical reading, and it changes the letters on the page, not only the styling. Glossary: <https://quran.ws/docs/concepts/glossary/#mushaf></sub>

```html
<!-- as it ships, in pages/001.svg -->
<g class="word" data-word-key="1:1:2" data-rasm-uthmani="ٱللَّهِ">
  <path data-kind="mark" data-mark="hamzat_al_wasl" data-mark-family="diacritic" d="…"/>
  <path data-kind="body" d="…"/>
</g>
```

```js
svg.querySelector('g.word[data-word-key="1:1:2"]');        // one word
svg.querySelectorAll('path[data-mark="hamzat_al_wasl"]');  // 14, on page 1
svg.querySelectorAll('path[data-mark-family~="dots"]');    // 38, on page 1
```

## What it provides

**604 whole, displayable pages.** They are ordinary SVG files: put one in an `<object>` and it renders, pixel-identical to the print. Nothing here is a fragment or a preview.

**A stable key on every word.** `data-word-key` is `surah:ayah:word` — `2:255:3`. It is the same identifier the rest of the project uses, so someone else's word-level timings, translations or tafsīr join to the artwork by string equality, with no alignment step.

**Every mark named, from a closed vocabulary.** 436,841 paths across the 604 pages carry `data-mark` (measured, see Provenance), drawn from the 36 names in `schema/mark-taxonomy.json` — `fathah`, `kasrah`, `sukun`, `shaddah`, `hamzat_al_wasl`, `omitted_alif`, `rounded_zero`, `small_meem` and the rest. `data-mark-family` groups them (`diacritic`, `dots`, `tanwin`, `sifr`, `waqf`) and is a space-separated token list like `class`, so match it with `~=`.

**A JSON sidecar per page.** `index/by-page/NNN.json` gives every word on that page five text forms, its printed line number and its exact bounding box in the page's own `viewBox` units — usable server-side, with no browser and no SVG parsing.

**Corpus indexes.** `index/words.json` (77,432 rows, every word with its page, line, printed text and a search form), `index/pages.json`, `index/surahs.json`, `index/divisions.json` (30 juz, 60 hizb, 240 rubʿ boundaries), and a JSON Schema for each.

**A specification, not a guess.** `schema/FORMAT.md` is 1,315 lines covering structure, attributes, the mark taxonomy, coordinate spaces and — in §10 — the format's own known defects, page by page.

## Use it when you need

- Word-level interaction on the web: tap a word, highlight a verse, show a translation beside the printed line.
- To colour or style a single diacritic — one mark of one word — which is what makes a *tajwīd* colouring (the rules governing how the Qurʾān is recited) or a beginner-reader mode possible over real print.
- To lift a word or a verse out of the page as its own image, still at printed proportions.
- Word geometry outside a browser: cropping, thumbnailing, or a text layer over a raster render.

## Not for

| You want | Use instead |
|---|---|
| A muṣḥaf that has not been split. One edition is split here, and splitting is hard — not every muṣḥaf will ever be | [Quran SVG](https://quran.ws/blocks/quran-svg/) — the archive of vectorised muṣḥafs, addressable at ayah level, and growing by contribution |
| Mobile or native, where SVG of this density stops performing. This is a boundary, not a tuning problem | [Quran Engine](https://quran.ws/blocks/quran-engine/) — the same addressing on the split muṣḥafs, fast |
| Tapping whole verses, where an ayah region is all the precision you need | [Quran SVG](https://quran.ws/blocks/quran-svg/) |
| The Qurʾānic text as characters to search, store or compare | [Quran Text](https://quran.ws/blocks/quran-text/) |
| Tajwīd rule spans to colour with | [Quran Tajweed](https://quran.ws/blocks/quran-tajweed/) — this repository names what a mark *is*, never what rule applies to it |
| Letter-level addressing | Nothing yet. A word and a named mark are the smallest units today. Letter split is the goal, and this is how far it has got — which is why the block is not named after a granularity |

Three blocks publish muṣḥaf pages, and they are not a queue. **Coverage narrows as addressing deepens:**

| | Coverage | The smallest thing you can address |
|---|---|---|
| [Quran SVG](https://quran.ws/blocks/quran-svg/) | every vectorised muṣḥaf, and growing by contribution | an ayah |
| **Quran SVG Elements** | only the muṣḥafs that have been split | a word, a mark — a letter, later |
| [Quran Engine](https://quran.ws/blocks/quran-engine/) | those split muṣḥafs, on mobile | the same, fast |

Elements ships 604 whole displayable pages, exactly as Quran SVG does. The difference is not pages versus parts — it is what you can *address* once a page is on screen.

## See it work

- **[quran.ws/blocks/quran-svg-elements/](https://quran.ws/blocks/quran-svg-elements/)** — six panels running on a page from this bundle: follow a recitation word by word, search the page, colour a mark family, crop a word for sharing, click a word for its five text forms, and highlight a whole verse across the lines it occupies.
- **[quran.ws/demo/](https://quran.ws/demo/)** — the same page layered with the other blocks.
- **[png.quran.ws](https://png.quran.ws)** — a tool built on these files: choose a verse range, get an image of the printed ink.

## Supported riwayat

One, today.

| Edition id | Riwayah | Print | Ayah numbering |
|---|---|---|---|
| `hafs-kfgqpc` | Ḥafṣ ʿan ʿĀṣim | KFGQPC Madani muṣḥaf, V4 1441H | Kufan, 6,236 ayat |

Treat that as the coverage, not as a snapshot of a queue.

The numbering is a property of this printed edition, declared on every page as `data-ayah-numbering="kufi"` and `data-ayah-total="6236"`. Six traditional schools divide the identical text at different points, so 6,236 is not a constant of the Qurʾān — read it from the file you loaded. See [ayah-counting systems](https://quran.ws/docs/concepts/ayah-counting/).

## Provenance

- **Source artwork.** The vectorised KFGQPC Madani pages. The pipeline regroups the ink and never moves or redraws it, so output is pixel-identical to the print.
- **Build record.** `VERSION.json` carries the edition, build date, profile, the artwork and pipeline commits, and the corpus counts: 604 pages, 114 surahs, 6,236 ayat, 77,432 words, 436,398 marks, 199 division marks.
- **Counts, measured rather than quoted.** Reading all 604 shipped pages gives 77,432 `g.word` groups (matching `index/words.json`), 13,489 `g.ayah-fragment` nodes for 6,236 ayat, and 436,841 paths carrying `data-mark`. The mark total differs from `VERSION.json` and from `FORMAT.md` §6.5, which count marks differently; cite the measurement you need and say which it is.
- **Integrity.** `CHECKSUMS.txt` covers every file in the bundle; the release also publishes a `.sha256` for the tarball itself. Both verified against the published v1.0.0 while writing this.
- **Reproducibility.** `VERSION.json` for v1.0.0 records `pipeline_dirty: true` and `artwork_dirty: true`, so the two commits it names do not reproduce the released bytes on their own. The build is deterministic from its inputs; the inputs are not yet addressable by commit.
- **Licence: CC BY 4.0** for our own contribution, with the King Fahd Complex's terms untouched for the artwork and the text. See below.

## Quick start

**There is no install line, and no library.** There is no npm package and no JavaScript in this repository; `@quran-ws/svg-elements` is not published. The files are plain SVG and JSON and need no runtime — what follows is the whole of it.

The distribution is one tarball on the release. There is no per-file host yet, so getting one page costs the whole corpus: **108 MB compressed, 433 MiB unpacked.**

```sh
gh release download v1.0.0 -R quran-ws/quran-svg-elements -p 'quran-svg-hafs-kfgqpc.tar.gz*'
shasum -a 256 -c quran-svg-hafs-kfgqpc.tar.gz.sha256
tar xzf quran-svg-hafs-kfgqpc.tar.gz
cd quran-svg-hafs-kfgqpc
shasum -a 256 --ignore-missing -c CHECKSUMS.txt     # 1223 files OK
```

`--ignore-missing` is required: `CHECKSUMS.txt` lists 3,647 files, including the 2,424 pre-compressed `.svg.br` / `.svg.gz` copies that the tarball deliberately excludes. Without the flag the command warns on all 2,424 and exits non-zero on a bundle that is in fact intact.

Then serve `pages/` and `index/` as static files, and put a page in the document:

```js
const host = document.querySelector("#page");
host.innerHTML = await (await fetch("/pages/001.svg")).text();
const svg = host.querySelector("svg");

svg.dataset.decomposition;          // "word" — how deep this file goes
svg.querySelectorAll("g.word").length;                       // 29 on page 1
svg.querySelector('g.word[data-word-key="1:1:2"]').dataset.rasmUthmani;   // ٱللَّهِ
```

An `<img src="001.svg">` renders the same pixels and gives you nothing to select. The decomposition exists only when the SVG is part of your DOM.

One listener on the root turns any tap into a reference:

```js
svg.addEventListener("click", (e) => {
  const word = e.target.closest("g.word");
  if (!word) return;                                    // tapped bare paper
  console.log(
    word.dataset.wordKey,                               // "2:253:1"
    word.closest("g.ayah-fragment").dataset.ayahKey,    // "2:253"
    word.closest("g.line").dataset.line,                // "1"
  );
});
```

Only the ink is hit-testable, so a tap between two words hits nothing. On touch, widen the target without changing a pixel: `g.word path { stroke: transparent; stroke-width: 1.5; paint-order: stroke fill; }`.

### Read this before you highlight a verse

**An ayah is not one node.** A verse is emitted once per printed *line* it occupies, so a verse running over six lines is six sibling `g.ayah-fragment` nodes and there is no single node that is the verse. Corpus-wide: 6,236 ayat, 13,489 fragments, 4,455 of them spanning more than one line.

```js
// wrong — 10 of the 52 words of 2:253, and nothing throws
svg.querySelector('g.ayah-fragment[data-ayah-key="2:253"]').querySelectorAll("g.word");

// right — all 52, and the file tells you how many fragments to expect
const frags = svg.querySelectorAll('g.ayah-fragment[data-ayah-key="2:253"]');
frags.length === Number(frags[0].dataset.ayahFragments);   // true on page 42
```

It looks correct on every short verse you test with. No ayah spans two pages, so the right page always holds all of a verse's fragments.

### Four more things that cost time

| | |
|---|---|
| **The text is not text** | There are no `<text>` elements. Find-in-page, selection and copy do not work on the Qurʾānic ink. The words are carried as data instead: `data-rasm-uthmani` on the page, and five forms per word in `index/by-page/NNN.json`. |
| **Search on `search`, and fold both sides** | The printed spelling writes some long vowels as marks; strip the marks and the vowel vanishes from the string, so a user's query returns nothing, quietly. Match against the `search` field, which is derived from the modern spelling. It is in the sidecar and in `index/words.json`, not on the page — the released bundle is the production profile and does not carry `data-search`. **`search` is deliberately not folded** — it keeps `أ`, `ة`, `ى` as the modern spelling writes them — so comparing a raw query against it misses every word whose letter forms the user typed differently, which is 29% of the distinct keys. Run both the query and the stored value through `tools/search_fold.match_fold` (docs/SEARCH-FOLD.md); it is the same fold quran-text and quran-engine use. |
| **`data-mushaf` is misspelt in the pages** | Pages declare `data-mushaf="hafs-kfqc"` while `VERSION.json` and every index file say `hafs-kfgqpc`. Any equality check across the two fails on the missing letter. Key on `data-edition`, or on the bundle you loaded, until this is fixed. |
| **Fetch the page sidecar, not the corpus index** | `index/words.json` is 3.6 MiB and exists for searching everything. `index/by-page/042.json` is 31 KiB and answers everything about one page. |

### Known gaps in `schema/FORMAT.md`

Verified against the shipped v1.0.0 bundle. The specification is otherwise the best thing in it — but these recipes will not run as written:

- §6.2, §7 and §11 name the fragment→medallion attribute `data-mark` / `dataset.marker`. The files emit **`data-ayah-mark`**. (`data-mark` is real, but it lives on mark paths.)
- Code samples read `w.dataset.rasm_uthmani`, which is always `undefined` — `dataset` camel-cases, so it is **`rasmUthmani`**.
- §3 and §11 search recipes read `data-search`, which the published production profile does not carry.
- §11's Python recipes open `index/index.json` and `index/wordboxes.json`; neither is in the bundle. Use `index/pages.json` and `index/by-page/NNN.json`.
- §4 calls the medallion layer `class="ayah_marks"`; the files emit `class="ayah_markers"`.
- §8 points at `.cache/schema/mark-taxonomy.v2.json`; the bundle ships `schema/mark-taxonomy.json`.
- §6.1 refers to a shipping library (`page.attachWords`, `createLoader`). No such library exists in this repository or in the release.

### A caution about the names

The repository, the release asset and the schema ids are all still named after `quran-svg`. A reader sent to "the quran-svg bundle" can land on [`quran-ws/quran-svg`](https://github.com/quran-ws/quran-svg) instead, which has a v1.0.0 release of its own — a different product, five muṣḥafs at ayah level. It will load and contain no `g.word`. The bundle you want is `quran-svg-hafs-kfgqpc.tar.gz`, from this repository.

## Works with

| Block | Why |
|---|---|
| [Quran Engine](https://quran.ws/blocks/quran-engine/) | The runtime that consumes these shapes where SVG will not perform. |
| [Quran Text](https://quran.ws/blocks/quran-text/) | The same `surah:ayah:word` identity, as characters. |
| [Quran Tajweed](https://quran.ws/blocks/quran-tajweed/) | Rule spans to colour with, now that a single mark is addressable. |
| [Qiraat Ayah Map](https://quran.ws/blocks/qiraat-ayah-map/) | Translate a reference between counting systems before you look for it on a Kufan-numbered page. |

## Documentation

- **[Reference: Quran SVG Elements](https://quran.ws/docs/reference/quran-svg-elements/)** — every file, every selector, and working code for the seven things people do first.
- **`schema/FORMAT.md`** in the bundle — the full specification, including §7 on ayah fragments and §10 on known defects. Read the gaps listed above alongside it.
- **[Glossary](https://quran.ws/docs/concepts/glossary/)** — muṣḥaf, riwayah, rasm, tajwīd, in plain English.
- **[Ayah-counting systems](https://quran.ws/docs/concepts/ayah-counting/)** — why 6,236 is a property of this edition.

## Licence

**CC BY 4.0**, the same notice every Quran.ws repository publishes: code under MIT, data and content under Creative Commons Attribution 4.0 International. The root `LICENSE` is the authoritative text and `NOTICE.md` states what it does not cover.

This settles a contradiction. There used to be four answers: the bundle's own `LICENSE` was a placeholder saying no licence had been chosen and the contents were all rights reserved; every JSON file in the same bundle declared `CC-BY-4.0`; the bundle README's file table said CC0 1.0; and the root `LICENSE` was CC BY 4.0. The placeholder shipped in `v1.0.0` because the bundle was built before the root `LICENSE` was committed and released fifty minutes after it. The builder no longer has a placeholder to fall back on — a missing licence now stops the build.

**`v1.0.0` still carries the placeholder**, because it is the published bytes rather than the source. It has to be re-cut before the terms above apply to anything anyone can download.

Separately and regardless: the page artwork and the Qurʾānic text are the **King Fahd Glorious Qurʾān Printing Complex's**, and are not this project's to license.
