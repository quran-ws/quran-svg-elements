# Upstream SVG data issues — a consumer's converter report, and what was done

Reported 2026-09-04 by the author of a converter that reads `pages/*.svg`
(`qvp-convert`). Each item below is the report's wording, condensed, followed
by the finding and the resolution. The gate for the fixed items is
`python3 tools/audit_export.py 1 604` (six properties, every page) plus
`tools/audit_pixels.py` (nothing added, removed or moved).

## 1. Pages 001 and 002: ayah markers duplicated and mis-attributed — FIXED

**Report.** Every marker position carries two `ayah-mark` groups, ids are
shifted by one, later groups have no `id` / `data-aid`.

**Finding.** The artwork itself draws every ornament of the opening spread
twice — byte-identical `translate(...) scale(...)` and `d`, back to back: 14
ornament groups on p1 for 7 ayahs, 10 on p2 for 5, no other page. The marker
pairing took the first copy as a marker on its own; the position binding then
gave the numeral's group the NEXT ayah's id. `FORMAT.md` had described the
result as "12 decorative rosettes with no ayah". They are duplicates.

**Resolution.** One `<g class="ayah-mark" id="mk-S-A" data-aid="S:A">` per
ayah, ornament + numeral, ids correct. The second copy rides inside the same
group as `<path data-kind="ayah_mark_ornament" data-duplicate="1">`. It is
**not** dropped: two identical fills darken the anti-aliased rim by up to
57/255 (measured: collapsing them moves 3,264 px on p1, 2,336 on p2), and
pixel identity with the artwork is a gated invariant here. A consumer wanting
one ornament removes `[data-duplicate]`.

## 2. Pages 001 and 002 use a different viewBox and root transform — FIXED

Every page is now `viewBox="0 0 345 550"`. The artwork's offset
(`-53.3109 -198.4777`) is folded into the page frame's translation
(`matrix(1.3333 0 0 -1.3333 -82.6891 680.4777)`) and into `ayah:x` / `ayah:y`.
Raster diff against the artwork: identical. Word boxes in
`index/by-page/001.json` / `002.json` are in the normalised frame.

## 3. Four `<path>` elements without `data-kind` — FIXED

All four on p17, the only page whose artwork keeps page furniture outside
`#content`: the page number ١٧ (two paths, 36 units below the bottom edge) and
two running heads, الجزء الأول and سورة البقرة (45 units above the top edge).
None of them renders. They are now `<g class="page_number">` /
`<g class="running_head">` with `data-kind` of the same name on the paths, and
both kinds are in the taxonomy.

## 4. 72 `<path>` elements carry an inline `transform` — FIXED

All 72 (p17 and p144) were the emitter's frame compensation for ink regrouped
from another source path — pure translations in every case. The translation is
now baked into each contour's absolute moveto; relative segments are
translation-invariant so nothing else changes. No `<path>` in the corpus
carries a `transform`.

## 5. Coordinate noise — FIXED

The noise was the float sum of the artwork's own relative segments, written
back exactly. Measured over all 1,857,168 contour starts in the mushaf, the
farthest any sum sits from a three-decimal number is 7.3e-12, so the emitter
now writes the three-decimal number when within 1e-9 of it and the exact repr
otherwise (never triggered). The report's "roughly a third" size estimate does
not hold: relative segments are copied verbatim from the artwork and were
never noisy; the saving is about 3% per page (25.7 KB of 900 KB on p36).

## 6. Per-word text forms repeated on every word group — FIXED

The production profile now carries `data-word-key` and `data-rasm-uthmani` only. `rasm`,
`rasm_imlai`, `search` and `qpc` ship once, in `index/by-page/NNN.json` (all five
forms, line, box) and `index/words.json` (the search key), built from the same
cache and the same derivations as the dev profile's inline attributes; the
bundle checker proves the sidecar's `rasm_uthmani` equals every page's
`data-rasm-uthmani`. The dev profile keeps them inline (it is the review
instrument). The shipping library reads inline first, sidecar second
(`createLoader({words: true})`, `page.attachWords()`).

## 7. No per-letter segmentation — NOT POSSIBLE FROM THIS DATA

Body paths are the artwork's connected strokes. The ligature layer of the dev
profile is the finest honest level; it is a letter-run cut, not a letter cut,
and is documented as such (FORMAT §10.3). A letter boundary would have to be
invented, and the project does not invent ink.

## 8. Ayah numbers as digit glyphs — NOT POSSIBLE PIXEL-IDENTICALLY

Measured over the 6,236 numerals: ~14,000 digit subpaths, **13,648 distinct
outlines** (position-normalised). The digits are per-instance ink, not
placements of ten glyphs; substituting a canonical glyph would change pixels.

## 9. Surah frames and basmalah as reusable glyphs — NOT POSSIBLE PIXEL-IDENTICALLY

3,500 of 3,501 surah-name contours are unique; 3,716 of 4,266 basmalah
contours. Same reason as 8.

## 10. Ayah ornament stays a shared glyph — UNCHANGED

Still one outline placed by `translate(...) scale(...)`; nothing bakes it.
