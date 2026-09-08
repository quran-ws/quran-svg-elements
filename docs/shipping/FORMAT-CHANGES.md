# What changed in `FORMAT.md` — 2026-09-04

Driven by a consumer's converter report (`docs/defects/upstream_svg_issues.md`),
measured on the emitted corpus and gated by `tools/audit_export.py` (all six
properties hold on every one of the 604 pages) and `tools/audit_pixels.py`.

| section | was | is | evidence |
|---|---|---|---|
| §9.2, §6.3, groups table | "12 `<g class="ayah-marker">` groups with no id — decorative rosettes"; 6,248 marker groups | The artwork draws each ornament of the opening spread **twice**, byte-identical and in place (7 pairs on p1, 5 on p2, no other page). The copy used to become its own marker and shift every id by one. Now it sits inside its ayah's group as `data-duplicate="1"`; 6,236 groups, all with `id` + `data-aid`. Not removed: collapsing it darkens the anti-aliased rim by up to 57/255 (3,264 px on p1). | `tag_ayah_markers`; raster diff. |
| §5.1 | pages 1–2 use `viewBox="-53.3109 -198.4777 345 550"` | every page uses `0 0 345 550`; the offset is folded into the page frame (`-82.6891 680.4777`) and into `ayah:x`/`ayah:y`. Pixel-identical. Word boxes for p1–2 in the index are in the new frame. | `normalize_frame`; `audit_pixels` 1–2 clean. |
| §5.2 | "72 ink paths on p17 and p144 carry a `transform`" | none does: all 72 were pure translations, now baked into the absolute movetos. | `_reframe` + `build_d(shift)`; raster diff on p17/p144. |
| §6.5 | 4 paths on p17 without `data-kind` | `page-number` (2) and `running-head` (2): p17's page furniture, outside the viewBox. | `tag_page_furniture`. |
| §5.2 (new paragraph) | absolute movetos written as exact float repr (`166.17999999999796`) | three decimals: every contour start is within 7.3e-12 of a three-decimal number (1.86 M measured). ~3% smaller pages. | `svg_lines.fmt`; `audit_pixels` all 604. |
| §2, §6.1, §10.9 | all six text attributes on every word group in both profiles | **production carries `data-wid`, `data-w` + `data-uthmani` only**; `rasm`, `imlaei`, `search`, `qpc` ship in `index/by-page/NNN.json` and `words.json`, from the same cache and derivations; dev keeps them inline. Library: `createLoader({words: true})`, `page.attachWords()`. | emitter `_PROD` branch; `bundle_extract.text_forms`; `verify_bundle` cross-check. |
| §6.1 (new) | — | **`data-w`**, the global word id of the word-by-word source (KFGQPC UthmanicHafs v3.0 release), on every word group in both profiles and as `w` in `index/by-page/NNN.json` and `words.json` (new second column). Derived by `tools/build_wbw_map.py`; page membership of the source agrees with ours on all 604 pages; segmentation on 6,235 of 6,236 ayahs (15:7's two pieces share one id). | `docs/HAFS-JSON-SOURCE.md`. |

Refused, with measurement, from the same report: sharing ayah-number digit
glyphs (13,648 distinct digit outlines among ~14,000 — the ink is per-instance),
sharing surah-name / basmalah frames (3,500 of 3,501 contours unique), and
per-letter segmentation (not derivable from the artwork).

---

# What changed in `FORMAT.md` — 2026-08-30

Every statement in the new `FORMAT.md` was re-measured against the **emitted
corpus**, `.cache/words-svg/hafs-kfqc/*.svg` (604 files, dev profile, build of
2026-08-30 00:28). Nothing was inherited from the previous revision without a
check; where a claim could not be verified it was removed rather than softened.

Page 3 was rebuilt from scratch in both profiles to confirm the cache is
current — `python3 tools/assign_words.py hafs/kfqc 3` reproduces the cached
file exactly (753,435 characters / 758,232 bytes).

---

## New sections

| section | why |
|---|---|
| **§2 The two profiles** | `QSVG_PROFILE=production` did not exist when the document was written. |
| **§7 An ayah is not a subtree** | The marker link (`id` / `data-marker` / `data-part` / `data-ayah-parts`) is new, and this is the thing consumers get wrong. Worked queries for "select the whole ayah", "from an ayah find its medallion", "from a word find everything". |
| **§6.1** rewritten | `data-search` is new. All six text attributes are now documented together with an explicit "which to use for what". |
| **§6.2** rewritten | The `*-start` division attributes were documented in the wrong place (see below). |

## Corrections — claims that were WRONG and are now right

| was | is | evidence |
|---|---|---|
| Status note: "the production profile removes `data-eid`, `data-sig`, `data-mark-family` and the ligature wrapper" | Production removes the **ligature groups and the ayah polygons only**. `data-eid`, `data-sig` and `data-mark-family` are in both. | `_PROD` is referenced at exactly three places in `assign_words.py` (2673 polygons, 2892 ligatures, 12394 polygon strip); byte-for-byte, `production` == `dev` minus those two things — proven by transforming the dev p3 into the prod p3 and comparing (`match: True`, 739,866 chars each). |
| `data-juz-start` / `data-hizb-start` / `data-nisf-start` / `data-rub-start` listed under `<g class="hizb-mark">` with counts 73 / 141 / 168 / 671 | They are on **`<g class="ayah">`**, repeated on each fragment: 72 / 140 / 168 / 669 attribute instances, covering **30 / 60 / 60 / 240 distinct ayahs** — complete coverage of every division boundary. | corpus scan; the 199 `g.hizb-mark` groups carry only `data-mark`, `data-aid`, `data-rub`, `data-rub-in-hizb`, `data-nisf`, `data-hizb`, `data-juz`. |
| §9.1 "the ayah-marker's `data-aid` is REVERSED on 441 pages — do not use it" | **Fixed.** Markers are bound by position. On p3, `mk-2-6` now sits at screen y 57.9 (top, where 2:6 is printed) and `mk-2-16` at 523.8. | marker translate y, all 11 medallions on p3, descending correctly. |
| §9.2 "four surah banners missing (27, 33, 37, 47); 110 `surah-name`; 113 `basmalah` for 112 surahs; 79 orphan named marks" | **114 `surah-name` (114 distinct surahs), 112 `basmalah` (absent only for surahs 1 and 9), 0 orphan named marks.** No basmalah is split. | corpus scan; `docs/defects/LINE-SURAH-FIX-2026-08-29.md`. |
| §9.3 "54 words are in the wrong `<g class="line">`, on 51 pages" | **0.** Concatenating each page's words line by line gives the mushaf's own word order on all 604 pages. | corpus scan; `tools/audit_wordline.py`. |
| §9.10 "the edition manifest's `surah_name_groups_emitted` is stale (108 vs 110)" | Manifest is current: `surah_name_groups_emitted: 114`, `basmalah_groups: 112`. Section deleted; the *companion index* is what is now stale (new §10.9). | `.cache/schema/edition-hafs-kfgqpc.json`. |
| "34 emitted names ... `pause` is a legacy fallback" (no registry accounting) | **34 emitted**, registry declares **36**, **35 active** (`waqf-mamnu` inactive), `pause` active-but-never-emitted. `audit_taxonomy.py` prints `35 mark names` — that is the registry's active set, not the emitted set. Both numbers now explained. | `.cache/schema/mark-taxonomy.v2.json`; `audit_taxonomy` output. |
| §8.4 "space census: `data-imlaei` 4,933 — an imlaei convention, not word boundaries" | Kept, **plus** the new `data-search` row: 367 spaced values, 348 the `يا ` vocative and 19 others including `سواء السبيل` (60:1:48) and `نذير مبين` (71:2:6) — one printed word rendered as two modern words. | corpus scan. |
| §7.5 "a `data-sig` is not an identity" (two anecdotes) | Now quantified: **98 of 2,152 signatures serve more than one mark name**; `d2506e4f8b4e28e5` is `dot` 63,233 ×, `two-dots` 498 ×, `three-dots` 38 ×, `muanaqah` 3 ×; 85 signatures serve both `fatha` and `kasra`. | corpus scan. |
| §7.2 fused-hamza sites given as `21:28:4` p324, `22:76:4` p341 with no text | Confirmed; both are `أَيْدِيهِمْ`, and the `data-text="ا"` ligature holds exactly two paths (hamza + fatha) and **no** body. | direct read of p324/p341. |

## Claims REMOVED (could not be verified)

- **"926 words carry a tanween pair with no meem at ikhfa/idgham positions."**
  Not reproducible from the emitted files with any defensible definition (a
  naive count of tanween-without-meem words gives 8,547). Dropped rather than
  restated.
- **"ayahs spanning two pages: 0"** — *kept*, and re-proved independently:
  6,236 ayahs, 6,236 distinct (page, ayah) pairs, no ayah appearing on two
  pages. This also makes `mk-<surah>-<ayah>` globally unique, which the new §7
  relies on.

## Counts refreshed (small drifts from the rebuild)

`g.ayah` 13,510 → **13,489** · ayahs with >1 fragment 4,458 → **4,455** ·
`data-kind=mark` 436,708 → **436,629** · `body` 161,819 → **161,778** ·
named marks 436,706 → **436,627** · `header-ink` 5,550 → **5,670**
(2,300 surah-name + 3,370 basmalah) · `data-eid` 598,527 → **598,407** ·
`data-sig` 598,512 → **598,392** · `data-mark-family` 122,203 → **122,191** ·
`fatha` 123,074 → **123,054** · `kasra` 46,089 → **46,069** ·
`dot` 63,619 → **63,611** · `wasla` 13,495 → **13,483** ·
paths in descending x 19.6% → **19.5%** (15,102 of 77,432).

The ligature-vs-rasm table (§10.3) was re-measured with a **different**
normalisation from the old one (this run also folds alef forms, `ى`/`ي` and
`ة`/`ه`, and does not separate "reversed" from "other permutation"), so
76,725 → 76,702 exact and 151 → 156 fewer-letters are not a like-for-like
drift. The shape of the finding is unchanged: ~99.1% reproduce the rasm, a few
hundred are out of order, ~150 spell fewer letters, and **none** spell more.

Sizes re-measured, both profiles:

| | raw | gzip -9 | brotli q11 |
|---|---:|---:|---:|
| dev, per page | 774.2 KiB | 188.3 KiB | 119.1 KiB |
| production, per page | 761.7 KiB | 186.2 KiB | 118.0 KiB |
| dev, corpus | 456.7 MiB | 111.0 MiB | 70.2 MiB |
| production, corpus | 449.3 MiB | 109.8 MiB | 69.6 MiB |

## New facts found while verifying

- **4 paths on p17 carry no `data-kind` at all** — page ornaments outside both
  `#content` and `#ayah_markers`, passed through from the artwork. p17 is the
  only page with them, so "`data-kind` is on every path except `ayahPolygon`"
  was not quite true. Now §10.5.
- **226 of the 9,046 lines hold no words** — exactly 114 surah-name + 112
  basmalah header lines. `g.line` count and word coverage now reconcile.
- **No `<g>` inside a `<g class="word">` carries a `transform`**, on any page.
  That is what makes `word.getBBox()` directly usable in the line frame, which
  the band-highlight recipe depends on.
- **The `*-start` attributes cover all 240 rubʿ boundaries**, including the 41
  with no drawn rosette — so divisions should be read from `g.ayah`, never from
  the rosettes. Called out in §9.6.
- **`data-form` is absent on 48 of the 8,554 tanween paths** (fathatan 4,
  dammatan 14, kasratan 30). The old text implied it was always present.
- **`small-noon` is the only *orthographic* sign with no family** — the old
  text called it "the only reading sign with no family", but the registry does
  not classify it as a reading sign at all.

## Verified unchanged (spot-checked in the real files)

All of §9's special cases: the 6 saktah/seen/imalah/ishmam/tashil/small-noon
sites (p293, p443, p567, p578, p588, p39, p159, p525, p226, p236, p481, p329);
the 3 muʿānaqah pairs (p2, p112, p114) and their word texts; `إِلْ يَاسِينَ`
p451 `37:130:3`; the 15 sajdah sites and the two split groups (p379, p480); the
199 rosettes with all 41 gaps at an ayah 1; iqlab p104 `4:165:9` high form and
p85 `4:41:6` low form, 605 ids / 335 complete / 270 meem-only / 4 untagged
meems; p350 `24:2:12` dammatan drawn outside its word; p272 `16:48:10`
small-waw; p11 `2:70:1` sifr in the previous ligature; the unnamed mark p1
`1:2:1` `e34`; the single `data-mark-part` p146 `6:141:14`; the 15 paths with
no `data-sig`; p7 as the only file with `xmlns:xlink`; p17/p144 as the only
pages emitting one `g.ayah` per word (216 reopened groups); pages 1–2 with 8
lines, medallion scale 0.0075 and 12 numberless rosettes; the 4 pages whose
lines do not share one translate (1, 2, 17, 144); page matrices 301 odd / 301
even / 2 opening.

Every CSS selector printed in §11 was executed against `003.svg` with
`lxml.cssselect` and returned the documented result.

## Not changed, and flagged instead of fixed

Per the brief, output problems were reported, not repaired:

1. **`docs/shipping/out/` is stale** (built 21:40, before tonight's changes).
   `index.json` still declares `basmalah_groups: 113` and `lines_per_page: 15`
   for page 1, and `words.json` has no `data-search` column. Documented as
   §10.9 with the instruction to read the file's own `fields` array; the index
   should be rebuilt before the bundle ships.
2. **`data-iqlab` remains incomplete** (270 of 605 sites tag only the meem).
3. **Path order inside a word is still not right-to-left** (19.5%).
4. **Two sajdah groups are still split across the wrong ayah ids** (p379, p480).
