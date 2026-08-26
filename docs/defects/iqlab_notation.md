# Iqlab is drawn as ONE haraka + small meem, not tanween + meem

Reported by Abdullah 2026-08-26. Verified against the texts and the ink.

## The convention, measured

At an iqlab position the three sources disagree about what exists:

| source | writes |
|---|---|
| quran.com uthmani | full tanween + meem: `ٌ`+`ۢ` (U+064C U+06E2), `ٍ`+`ۭ` (U+064D U+06ED), `ً`+`ۭ` |
| KFGQPC text of this print | **single haraka** + meem: `ُ`+`ۢ` (U+064F U+06E2), `ِ`+`ۭ` (U+0650 U+06ED), and U+0657 forms |
| the drawn ink | **one vowel stroke** + a small م — the stroke pair is never doubled |

Verified examples (from `.cache/confidence/raw/`): p104 `حُجَّةٌۢ` uthmani `…U+064C U+06E2`
vs QPC `…U+064F U+06E2`; p85 `أُمَّةٍۭ` uthmani `…U+064D U+06ED` vs QPC `…U+0650 U+06ED`;
p203 `صَـٰلِحًۭا` QPC writes U+0657 and no meem char at all.

The small م itself: the high form `ۢ` (U+06E2) is drawn as a **separate glyph** whose
outline is a letter م; the low form `ۭ` (U+06ED) usually leaves **no standalone glyph**
(`assign_words.py:5416`) — but p85/p203/p535/p566 (`ۭ` words) still measure one surplus
piece, so the "no glyph" claim needs re-verification per word.

## A live internal contradiction

- `assign_words.py:4917` (correct): "this script does not double the stroke — it draws
  ONE vowel stroke plus a small meem."
- `scratchpad/audit_marks.py:33` and `tools/ref_kinds.py:88` (half-true): "the iqlab
  meem is fused into the tanween glyph in this art (measured)". True only for the low
  `ۭ` at some words; the high `ۢ` is separate ink. Because of this comment,
  `TEXT_WANT` deliberately does NOT demand `meem-iqlab` — so a meem left as letter ink
  is invisible to the mark audit and surfaces only as a LIGATURE/piece surplus.

## Root cause of the 12 CERTAIN "ligature surplus" words

`assign_words.py:4934`: the `_IQTAN` pass renames the single stroke to its tanween name
AND rescues the meem — but exits early (`continue  # already named`) whenever the
tanween is **already named** (single-outline dammatan glyph labelled by the shape
table, or an earlier weld). The early exit skips the meem rescue, and the م stays
counted as a letter piece. All 12 surplus words (`أُمَّةٍۭ حُجَّةٌۢ أَلِيمٌۢ شَدِيدٌۢ×2
صَـٰلِحًۭا تَارِكٌۢ جِنَّةٌۢ×2 بَارِدٍۢ وَعَادٌۢ` + likely `نُنَجِّيكَ`) fit this shape.

## Every site the convention touches

### tools/assign_words.py
| line | what it does | exposure |
|---|---|---|
| `:1070-1083` | `HARAKA`: segment_word predicts `fathatan/dammatan/kasratan` + `meem-iqlab` from uthmani | prediction matches ink only AFTER the renames below fire; `label_marks` zips by these names |
| `:4917` | `_IQTAN`: single stroke → tanween name, then meem rescue (w 1.5–12u, h 3–12u, d<14u of the stroke) | **the early-exit bug above**; also the d<14 window fails when the meem sits further out |
| `:5416` | next-word meem recovery — a small م forced into the NEXT word as body | only handles `ۢ`; assumes `ۭ` never leaves a glyph |
| `:3600, :3664, :4070` | tanween welds / pair reunification / strict pair transfer — all assume a tanween is a **stroke PAIR** | at an iqlab position there is only ONE stroke; a pair-seeking pass pointed at an iqlab word can steal a neighbour's stroke |
| `:4290` | reverse guard: meem-iqlab no text demands is the LETTER م | correct, and the reason `ذَٰلِكَ`'s ذ was recovered |
| `:6867` | `QSVG_IQFIX`: post-override, an iqlab meem sitting ON the baseline is a letter | correct |
| `:2189` | mark re-lining allows the iqlab meem to hang in the inter-line gap | correct |
| `:1477` | `mark_shape_table()` skips `meem-iqlab` labels — only the text may promote a م outline | correct; means every meem rescue is text-driven, so the `:4917`/`:5416` passes are the ONLY rescuers |

### audits and scorers
| file | exposure |
|---|---|
| `scratchpad/audit_marks.py:22-33` | demands `fathatan/kasratan/dammatan` per uthmani; correct only because the pipeline renames the single stroke. If the rename fails the word double-flags (`fatha 1/0` + `fathatan 0/1`). Never demands `meem-iqlab` (comment half-true, above) — a lost meem is invisible here |
| `scratchpad/bench.py:60` | budget lumps the slash and damma families, so it is insensitive to single-vs-pair naming (by design) |
| `tools/audit_marksize.py` / family medians | `dammatan` (etc.) mixes three different drawings under one name: the single-outline glyph, welded stroke pairs, and the renamed single iqlab stroke — the "each family's area is a point" claim is weak exactly for the tanween families. Per-signature medians (score_confidence) absorb this |
| `tools/score_confidence.py` | `fam_want` uses uthmani `TEXT_WANT` (same exposure as audit_marks); `meem-iqlab` is excluded from family-surplus conviction for this reason; size metric uses per-sig medians |
| `tools/score_both.py` | its piece-count metric is what catches the lost meem (as surplus vs the joining rules) — this is why iqlab words dominated the 25-word gap |
| `tools/ref_kinds.py:76-91` | documents the p222 hazard: promoting a kasratan at an iqlab word left the word with none |
| `tools/audit_ref_marks.py:22` | MushafDatabase's vocabulary fuses iqlab as `fatha iqlab` — no per-name mapping between the two vocabularies is attempted, deliberately |
| `tools/make_queue.py:62` | routes the derived families (fatha/fathatan…) as "auto" — single iqlab strokes ride along |

## What follows

- Fix Family A of `docs/superpowers/plans/2026-08-26-certain-defect-fixes.md` at
  `:4917`: run the meem rescue INDEPENDENTLY of whether the tanween is already named.
- Re-verify the "`ۭ` leaves no glyph" claim word-by-word before touching `:5416`.
- When comparing against the QPC text (`data-qpc`), remember its single-haraka
  encoding: counting QPC's `ُ` as a plain damma at an iqlab position is wrong the same
  way counting uthmani's `ٌ` as a stroke pair is.
- Correct the stale comments in `audit_marks.py:33` and `ref_kinds.py:88` when touched.
