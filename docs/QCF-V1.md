# Hafs 1405H QCF V1 source and vector build

This pipeline targets the **Hafs 1405H QCF V1 print**. It joins pinned source records to exact
font outlines and emits tagged SVG that Quran Engine can encode as QVP. It does not render the
source fonts at runtime.

## Current boundary

The work has seven distinct layers:

1. **Source ownership is mapped across all 604 pages.** Canonical word keys and readable text
   are joined to V1 page and line ownership, QCF V1 body glyph codes, ayahinfo rectangles,
   QPC V4 header identities, and the `qpc-old` page index.
2. **Whole-glyph body output covers all 604 pages.** The body builder preserves the selected
   print's page, line, word, ayah-mark, and source-glyph ownership. Body, dot and vowel contours
   remain whole unless an independently owned source glyph proves a narrower boundary.
3. **Waqf ownership is source-glyph-qualified.** Canonical text contains 4,272 waqf signs.
   Exactly 4,221 are independently positioned final source glyphs and are emitted as typed
   `data-kind="mark"` paths in the `waqf` family. The other 51 are fused inside one source word
   glyph and deliberately remain `data-kind="other"` pending contour-level verification.
4. **Division and sajdah ownership is source-qualified.** All 240 rubu-al-hizb boundaries carry
   juz, hizb, nisf and quarter metadata. The print has 199 standalone division rosettes and 15
   sajdah marks. Fourteen sajdah marks come from mapped source glyphs; the missing page-454 sign
   is restored from the exact pinned page-font glyph and semantic-source frame. The other 41
   rubu-al-hizb boundaries remain semantic boundaries without invented artwork.
5. **The one shared printed unit is implemented end to end.** Page 254 retains canonical words
   `13:37:8` and `13:37:9` while storing and drawing their single U+FB8F printed unit once.
6. **QPC V4 header placement is mechanically qualified.** All 114 complete headings and 112
   basmalahs use one scan-calibrated global placement that has zero body-ink collisions across
   the 116 header pages and improves agreement with the 1405H scans. Human typographic review
   remains a publication gate; mechanical qualification is not a claim of final taste.
7. **The source-qualified HQ overlay covers most words.** Exactly 60,739
   Qualified HQ outlines replace verified fallback words: 78.4417% of the corpus. The build
   admits direct source vectors and exact PDF-recovered vectors, pins their complete evidence,
   preserves every independently owned waqf, division and sajdah path, and applies a deterministic
   page-calibrated optical-weight correction inside each verified word box.

The source map, body geometry, shared-word contract, SVG/QVP conversion path, and HQ publication
path are complete enough for integration. The mushaf is not yet finely decomposed,
human-reviewed end to end, application-integrated, or released.

## Source authority

Each source has one bounded responsibility:

- **QUL layout 15** owns V1 page membership, line membership, line type, and source grouping.
- **quran-ios Hafs 1405 ayahinfo** owns one 1920 × 3106 rectangle per printed body glyph.
- **QCF V1 page fonts and `mushaf.txt`** own body glyph outlines and the reviewed body code
  stream.
- **Quran Engine's canonical index** owns canonical word keys and readable text forms.
- **QCF4 layout data** owns header type and Surah ownership. It is evidence for identity, not
  V1 page placement.
- **`QCF_SurahHeader_COLOR-Regular.ttf`** owns each complete high-quality QPC V4 Surah
  ornament/title glyph. The explicit 114-codepoint QUL `surah_header_code` order is pinned in
  the source manifest; it is deliberately non-contiguous.
- **QCF4 U+F8DD in `QCF4_Hafs_01_W.ttf`** owns the reusable V4 basmalah outline. The same
  outline, bounds, and advance were verified across all QCF4 Hafs page fonts that use it.
- **`qpc-old.json`** owns printed page numbers 1–604, every page's first-ayah boundary, and
  every ayah mark's cumulative source-glyph position.
- **The pinned 1405H semantic map and canonical division-start table** jointly own printed
  rubu-al-hizb and sajdah identity, exact source frames, and all 240 rubu-al-hizb boundaries.
  They are cross-checked against the canonical map and the exact 604 page fonts.

Every input digest is pinned. Changed or incomplete input fails before output publication.
The low-quality V1 `QCF_BSML.TTF` asset is not used.

## Canonical words and printed units

Canonical word identity and printed geometry are distinct layers. At [13:37], `13:37:8`
(`بَعْدَ`) and `13:37:9` (`مَا`) remain two canonical words, while this print has one U+FB8F
glyph and one rectangle at the `بعدما` / `بعد ما` boundary.

The map therefore:

- keeps both canonical keys and all five text forms;
- owns U+FB8F and its rectangle exactly once;
- records one shared group, `13:37:8-9`, in the line's ordered `content` sequence; and
- never duplicates geometry or rewrites the canonical keys to match the print.

The SVG contract emits the first logical word with the path and the adjacent logical alias with
`data-shared-paths-with="13:37:8"`. SVG → QVP reuses the exact path range. Runtime selection,
hit testing, styling, masking, highlighting, cropping, reveal, and reflow treat both logical
words as one indivisible printed unit; text, search, citation, and recitation retain both word
identities. QVP → SVG restores the same owner/alias contract without duplicating the path.

Two other reviewed boundary adjustments remain explicit:

- fuse QUL 15:7 positions 1–2 into canonical `15:7:1`;
- split QUL 37:130 position 3's two independently boxed glyphs across canonical
  `37:130:3` and `37:130:4`.

No other boundary adjustment is accepted.

## Edition-local layout

Canonical keys provide the cross-edition join; they do not make pagination universal. The map
preserves the selected 1405H page and line layout exactly. A later print placing the same word
on another page or line is evidence of an edition difference, not a mapping failure.

Every mapped line has one authoritative ordered `content` sequence. It interleaves ordinary
words, shared source groups, and ayah marks. The `word_keys`, `shared_word_keys`, and
`ayah_keys` fields remain indexes, not the ordering contract.

QCF4 and V1 disagree on placement for 43 Surah starts. The build therefore imports QPC V4
artwork and identity only. V1 remains the sole owner of the target page and line.

## QPC V4 headings and basmalah

`tools/build_qcf_v1_v4_headers.py` exports 115 exact-outline source assets:

- `surah/001.svg` through `surah/114.svg` from the official complete-header font, using the
  explicit QUL Surah-order codepoint list;
- `basmalah.svg` from QCF4 U+F8DD in `QCF4_Hafs_01_W.ttf`.

Every Surah SVG contains the complete ornament and title as one upstream glyph, not merely the
name text. All 114 heading outlines have an `8116 × 980` visual box. The upstream advances
vary by at most one font unit and are retained exactly.

```sh
python tools/build_qcf_v1_v4_headers.py \
  --surah-font /path/to/QCF_SurahHeader_COLOR-Regular.ttf \
  --basmalah-font /path/to/QCF4_Hafs_01_W.ttf \
  --out-dir .cache/qcf-v1/v4-header-assets
```

Source qualification and page placement are separate. The rejected wide calibration used a
1740-pixel heading and placed the basmalah 50 source pixels below its line center; it collided
with body ink on dozens of pages. The qualified placement instead uses a 1630-pixel heading and
a 750-pixel basmalah, both centered at x=956 and 10 source pixels below the measured V1 line
center. Across all 116 header pages it has zero body-ink collisions. Against the 1405H scans,
its mean 10-pixel candidate precision is 0.806, mean evidence recall is 0.600, and mean ink
distance is 7.45 source pixels—materially better than the rejected calibration. The manifest
pins both the audited candidate-page digest and the final qualified-page digest, plus the index
digest, the 604-page reference-scan tree, and the two audit-report digests. The two page corpora
are byte-identical after normalizing only the qualification label. A changed complete corpus
cannot retain the qualification without a fresh audit. Every emitted header records
`data-placement-qualification="mechanically-qualified"`.

## Page numbers

The map's `page` field is the printed number 1–604. Each page also carries
`page_number_source` with the `qpc-old` dataset and its first global ayah ID.

The map build checks:

- all 604 page starts; and
- all 604 per-page ayah-mark position ledgers against actual mapped body and mark glyph counts,
  including multi-glyph ayah marks.

This establishes page-number content, not ornamental styling or visual placement. Page frames
and running heads are intentionally out of scope.

## Build the source map

Acquisition and deterministic normalization are separate:

```sh
python tools/build_qcf_v1_map.py fetch \
  --pages-dir .cache/qcf-v1/qul-pages

python tools/build_qcf_v1_map.py build \
  --pages-dir .cache/qcf-v1/qul-pages \
  --canonical-index /path/to/quran-engine/index/by-page \
  --ayahinfo-db /path/to/hafs_1405/images_1920/databases/ayahinfo_1920.db \
  --font-text /path/to/qpc-fonts/mushaf.txt \
  --fonts-dir /path/to/qpc-fonts/mushaf \
  --qcf4-data /path/to/qcf4/data.txt \
  --qpc4-surah-header-font /path/to/QCF_SurahHeader_COLOR-Regular.ttf \
  --qcf4-basmalah-font /path/to/QCF4_Hafs_01_W.ttf \
  --page-number-source /path/to/qpc-old.json \
  --out-dir .cache/qcf-v1/map
```

The build emits 604 schema-3 page maps plus `summary.json`. It rejects changed input digests,
unreviewed code differences, page-index drift, incomplete header ownership, unresolved logical
boundaries, missing canonical keys, duplicate glyph ownership, or unowned ayahinfo rectangles.

## Build page SVGs

First derive the division and sajdah ledger. The builder verifies the complete semantic archive,
all 604 semantic-page digests, the canonical map, the division-start table, and the 604-font tree:

```sh
python tools/build_qcf_v1_division_sajdah_source.py \
  --map-dir .cache/qcf-v1/map \
  --semantic-map-dir /path/to/qcf-v1-semantic-map \
  --division-starts .cache/meta/rubu_al_hizb_starts.json \
  --fonts-dir /path/to/qpc-fonts/mushaf \
  --out conformance/qcf-v1-division-sajdah-source.json
```

Then derive the pinned waqf ownership ledger. It excludes source glyphs already owned by that
semantic ledger before deciding whether the final waqf glyph is separate or fused:

```sh
python tools/build_qcf_v1_waqf_source.py \
  --map-dir .cache/qcf-v1/map \
  --fonts-dir /path/to/qpc-fonts/mushaf \
  --division-sajdah-source conformance/qcf-v1-division-sajdah-source.json \
  --ledger-out conformance/qcf-v1-waqf-source-glyphs.json
```

Then build the pages:

```sh
python tools/build_qcf_v1_svg.py \
  --map-dir .cache/qcf-v1/map \
  --fonts-dir /path/to/qpc-fonts/mushaf \
  --header-assets-dir .cache/qcf-v1/v4-header-assets \
  --chapters-metadata /path/to/chapters.json \
  --waqf-source-glyphs conformance/qcf-v1-waqf-source-glyphs.json \
  --division-sajdah-source conformance/qcf-v1-division-sajdah-source.json \
  --pages supported \
  --out-dir .cache/qcf-v1/svg-1405
```

The current builder emits all **604 pages**, **77,432 logical words**, **88,247 physical source
glyphs**, and **226 mechanically qualified header decorations**, with no rejected page. It:

- preserves complete QCF body-glyph outlines without curve simplification or per-glyph
  stretching;
- uses a page-wide 121-pixel body em, except the reviewed 113.25-pixel page-270 override;
- moves ordinary one-glyph units halfway from painted-bounds placement toward the font advance
  cell only when their QCF right side bearing is at most -0.25 em and the mapped box agrees with
  advance width by at least 0.125 em more than painted width; all other body glyphs retain
  painted-bounds placement;
- preserves one physical U+FB8F path for the two page-254 logical words;
- emits 4,221 independently owned waqf source glyphs as typed marks, with exact per-mark counts
  pinned in `qcf-v1-waqf-source-glyphs.json`;
- emits 199 source-owned division rosettes and all 15 sajdah marks as standalone semantic marks;
- annotates all 240 rubu-al-hizb boundaries without inventing ink for the 41 unprinted starts;
- leaves all 51 fused waqf signs and every unresolved body, dot and vowel contour as
  `data-kind="other"` rather than guessing ownership;
- retains V1 page and line ownership; and
- publishes completed output atomically.

Two independent complete source trees were byte-identical. Waqf typing changes metadata only:
normalizing the 4,221 typed paths back to `data-kind="other"` reproduces the previously qualified
waqf geometry. The complete path-order gate proves that division and sajdah extraction changes no
existing path and adds exactly one pinned path: the restored page-454 sajdah glyph. Header
placement is mechanically qualified across all 116 header pages. QVP packaging, round-trip
verification, and publication remain downstream release gates for this source revision.

## Source-qualified HQ word overlay

The HQ build consumes the exact pinned candidate tree and its QPC V1 1406 source-fit
reports. Publication is decided by source identity and source geometry—not by whether one raster
comparison scores higher than the fallback.

The current overlay replaces **60,739 of 77,432 logical words: 78.4417%**. Those replacements occur
on **602 of 604 pages**. The other **16,693 words** retain their verified QCF outlines. Pages 1 and
2 remain explicitly excluded. The shared page-254 printed unit, all typed waqf owners, all
standalone division and sajdah owners, repaired or borrowed vectors, review-marked candidates,
text disagreements, bounded source-geometry failures, and 62 source-bound reviewed candidates
remain fallback. Forty-six candidates created adjacent-word overlap or reading-size merge blockers
under the complete visual gate. Five more became eligible only after the visible-ink base correction
and remain fallback so the build reproduces the audited collision result. Ten additional HQ fits are
vertically distorted by more than 8% and independently regress against the pinned 1405H scan. One
adjacent HQ word also remains fallback to preserve the verified pair geometry. Their exact source
identities, the 48 affected pairs, the base-transition evidence, and the vertical-stretch
audit are pinned in one reviewed-fallback ledger; changed source input invalidates the exclusion.

Direct vectors retain their pinned 1406 fit audit and page-scale gate. Exact PDF-recovered vectors
are admitted only when the candidate and fit report name the same `recovered:<sha256>` identity;
the page-raster audit and page-scale fields do not apply to that source class. A 1406 line number is
not an admission gate because the 1406 and 1405 prints wrap differently; canonical word key and
exact NFC text remain authoritative.

The exclusions are mutually exclusive and pinned: 4,221 typed owners, 214 standalone semantic
owners, 5,043 unsupported source classes, 1,957 text disagreements, 1,490 source-size disagreements,
1,198 source-centre disagreements, 1,070 scale drifts, 759 review-marked candidates, 456 aspect-ratio
drifts, 69 weak source-scan fits, 62 reviewed fallbacks, and 154 other bounded source failures. No target-1405 comparative
score automatically admits or rejects a source candidate; every scan-supported fallback is an
explicit source-bound ledger decision.

Candidate placement no longer shrinks each HQ word into the old fallback ink width. The centre
outline is fitted to the complete verified 1405H target word box, after reserving a calibrated
optical inset. It therefore restores conspicuous under-width cases such as `لَا يُؤْمِنُونَ` on
page 3 without a word-specific exception.

HQ strokes are intrinsically lighter than the QCF fallback strokes. The pinned 604-page optical
table calibrates that difference against the verified fallback geometry at 1920-pixel width. For
each page, the builder shrinks the centre path by the selected radius and emits the unchanged source
path at the centre plus four cardinal offsets. Their union remains exactly inside the verified word
box. The mean absolute whole-page ink-ratio error falls from **8.3021%** to **0.3652%**; median error
is **0.2148%**, p95 is **1.7846%**, and the maximum is **3.4071%**. 54 pages need no
correction; the other 550 use radii from 0.01 to 0.24 QVP page units. This is canonical source/QVP
geometry, not a viewer-only filter.

Build the overlay from the pinned base and candidate trees:

```sh
python tools/build_qcf_v1_hq_word_overlay.py \
  --base-dir .cache/qcf-v1/svg-1405 \
  --candidate-dir /path/to/qpc-resize/batch/out4 \
  --out-dir .cache/qcf-v1/svg-1405-hq
```

`qcf-v1-hq-word-source.json` is the single contract. It pins the base corpus, candidate-tree
digest, source policy, exact admission and exclusion counts, and complete output digests. The
builder verifies all 1,208 candidate files before publication, copies the two excluded pages
byte-for-byte, keeps all 604 word indexes unchanged, writes compact pathless source evidence, and
publishes atomically.

The qualified output has page digest `b8daf7e0…`, qualified-geometry digest `b472e8bb…`, index
digest `27f787fa…`, source-record digest `05daa877…`, and optical-calibration digest `0003a2e6…`.
Two complete builds were byte-identical.
The output retains all 4,221 typed waqf paths, 199 printed division marks, all 240 division
boundaries, and all 15 sajdah marks.

Ayah markers use their mapped `qpc-old` boxes, but their visible ink is centred from ink-bearing
font contours rather than the raw TrueType glyph bounds. Seventy-three source glyphs contain
move-only positioning contours; those contours paint nothing and are removed from marker output.
This corrects nine materially displaced markers—including `2:6`—without changing any word,
header, waqf, division, sajdah, index, or vertical marker placement.

Target-1405 scan comparisons remain useful for diagnosis and prioritising visual review, but they
are not a usability definition. The former 64-word set proved only that those candidates beat the
fallback under one strict comparative raster policy; it did not measure available HQ coverage.

## Remaining work

1. Complete human typographic review of the mechanically qualified heading and basmalah
   placement.
2. Complete human typographic review of the calibrated HQ corpus at useful reading sizes. The
   optical-weight mismatch is mechanically corrected and pinned, but mechanical agreement is not
   final typographic approval.
3. Improve source fitting only where rejected candidates fail a concrete source-identity or
   geometry check; target-scan scores may prioritise review but must not replace those checks.
4. Separate body, dot and vowel contours, and the 50 fused waqf signs, only where reviewed
   contour evidence establishes ownership; do not infer them from size or position alone.
5. Review the restored page-454 sajdah path and every extracted division/sajdah mark at useful
   reading sizes even though their source ownership and geometry are mechanically pinned.
6. Decide whether page-number artwork is required, then complete consumer packaging, release
   integration, and end-to-end application review.

Page frames and running heads are not goals for this integration.
