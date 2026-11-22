# quran-svg-elements 2.0.0

One release, two bundles from one build of 2026-11-22, on the quran-svg
artwork **v1.1.1**. Each bundle is its own archive.

| bundle | archive | schema | for whom |
|---|---|---|---|
| words | `quran-svg-elements-hafs-kfgqpc-words.tar.gz` | 1.0.0 | everyone reading v1.1.2 today. The pages need no change. |
| letters | `quran-svg-elements-hafs-kfgqpc-letters.tar.gz` | 2.0.0 | whoever needs each letter as its own object |

Both archives unpack to a directory named `quran-svg-elements-hafs-kfgqpc`.
On the CDN the release is one version folder with a folder per bundle,
`v2.0.0/words/` and `v2.0.0/letters/`; versions up to v1.1.2 hold word pages
directly under the version folder.

Every figure below was measured on the built pages. The specification is
`schema/FORMAT.md` in each bundle; the letter layer is §6.9 and its limits §10.10.

## The word bundle

The page shape is that of v1.1.2 with one attribute added, so a reader of
v1.1.2 pages reads these unchanged.

- **Added: `data-w` on every word group**, and `w` on every word of
  `index/by-page/NNN.json`: the word's number in the quran-text release. It is
  not a key (its numbering has gaps); `data-word-key` stays the key.
- **The word source is the quran-text release**: segmentation into words, the
  mark budgets, and the `qpc` text form.
- **Fixes found by the reviewer's eye**, each recorded in
  `docs/defects/reported.json`:
  - p232 `11:91:12` drew two letters short: a waqf sign had been counted as a
    letter piece of the word before it (item 64).
  - p540 `57:22:12`: one stroke of its tanwin al-kasr was filed with the word on the
    line below (item 63).
  - p470 `40:27:9`, p567 `69:10:5`, p437 `35:29:14`: the tanwin was paired from
    strokes of two different letters (item 66).
  - p526: three words beside a hizb rosette held a neighbour's ink.
- Counts: 604 pages, 77,432 words, 436,627 named marks, 161,778 letter-ink
  paths. The pixel audit against the artwork passes on all 604 pages.

## The letter bundle

The same pages, with every word divided into its letters:

```xml
<g class="word" data-word-key="2:6:2" data-w="67" data-rasm-uthmani="ٱلَّذِينَ">
 <g class="letter" data-text="ٱ" data-index="0" data-at="0"> … </g>
 <g class="letter" data-text="ل" data-index="1" data-at="1"> … </g>
 <g class="letter" data-text="ذ" data-index="2" data-at="4"> … </g>
 <g class="letter" data-text="ي" data-index="3" data-at="6"> … </g>
 <g class="letter" data-text="ن" data-index="4" data-at="7"> … </g>
</g>
```

- One `<g class="letter">` per letter, in reading order, holding the letter's
  body ink and its own marks.
- `data-at` links each letter and each mark to the character it draws in the
  word's `qpc` text.
- Where letters are joined in the artwork, the outline is cut; each piece is a
  `<path data-cut="1">`.
- `index/pages.json` and `index/by-page/NNN.json` give letter counts;
  `VERSION.json` names the letter build.

### Why it is a major version

A word's paths are now one level deeper. **`g.word > path` no longer selects a
word's ink; `g.word path` does**, in both bundles. A joined outline that was
one `body` path is now one path per letter, and 1,670 strokes that are a
letter's whole body (the dagger alif, and two fused hamzah signs) read
`data-kind="body"` where the word pages read `data-kind="mark"`. Everything
else — keys, mark names, frames, the index files — is as in the word bundle,
with one exception: **the hizb rosette**. In the letter bundle each of the 199
rosettes is the first child of the word it stands before, and that word's
display text begins with `۞` and a no-break space, so the rosette's ink links
to a character. In the word bundle the rosette stands beside the word and the
sign is not in the text. Compare word text across the two with `rasm` or
`search`. `schema/FORMAT.md` §9.6 has the table.

### Where the letter division comes from

The division of joined strokes into letters, and the letter each mark belongs
to, is the output of **DigitalKhatt's
[medinamushafanalyzer](https://github.com/DigitalKhatt/medinamushafanalyzer)**
at commit `056191f` (MIT licence, Copyright (c) 2023-2026 Digitalkhatt), run on
the same vectors and used with the author's agreement. This project joined its
letters onto its own words, text and mark names, and added what `FORMAT.md`
§6.9 lists: 180 slivers given to the letter they touch, 12 cuts the reviewer
picked by eye, 3 marks he moved, 60 marks the analyzer left unplaced.

### The numbers

| | words | letters |
|---|---:|---:|
| words | 77,432 | 77,432 |
| letter groups | — | 333,220, every one linked to its character, every one with body ink |
| runs left undivided | — | 0 |
| contours cut / cut pieces | — | 89,844 / 261,953 |
| ink paths | 611,107 | 783,207 |
| pages, raw, all 604 | 421.0 MiB | 588.4 MiB |

### What is proven, and what is not

Proven on all 604 pages: each letter page holds the same words and the same
ink as its word page. Two separate checks, one on polygons and one on rendered
pixels, find **no word that loses ink, gains ink, or has two letters sharing
ink**, down to a strip 0.0125 units wide.

Not claimed: that every joint falls where a calligrapher would put it. No
accuracy figure is quoted because none was measured; the division is the
analyzer's convention, accepted by the reviewer's eye. See `FORMAT.md` §10.10
for the slivers, the hairline at a cut, and the 4 marks without a text offset.

## Rebuilding it

`tools/build_release.sh <analyzer letters dir> <out dir>` builds both bundles
and runs every check; it stops at the first one that fails. The inputs and
their digests are written to `INPUTS.txt` beside the bundles.
