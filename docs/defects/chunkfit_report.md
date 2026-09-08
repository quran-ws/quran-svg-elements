# Chunk-identity audit (`tools/audit_chunkfit.py`) — first mushaf-wide run

Measured 2026-08-27 on the post-R7 build (false-meem family eliminated),
52,105 multi-chunk words scored. Detection only; nothing in the pipeline
changed. Flags: `docs/defects/chunkfit_flags.json`.

## Plain-language summary

The p254 fear — body chunks rotated one word over with every piece COUNT
staying legal — now has a detector. For every word holding two or more body
chunks, the audit asks: do these chunks' widths fit the letters this word is
supposed to draw, using the pipeline's own alignment machinery
(`align_segs_atoms`, so legitimate ـوا۟ / ـرًا swash merges score well)? And
when a chunk does not fit, does it fit the NEIGHBOUR's letters better, with
the neighbour itself damaged on the facing side — the signature of an
exchange?

**The reconstructed pre-fix p254 rotation is caught** (أَهْوَآءَهُم convicted
as rotation-suspect: its worst chunk fits the neighbour's ما 3.6x better, the
donor بَعْدَ مَا misfits 0.68 on the facing edge). All known-negatives are
clean: the p27/p177 بَعْدَ مَا compounds (wres 0.22 / 0.01), p451
إِلْ يَاسِينَ (0.11), and all 2,901 ـوا۟ swash words (0 above threshold).

**Mushaf-wide, no second p254 exists.** Two low-grade rotation-suspects
survive all three gates and need eyes; 20 non-convention width anomalies and
4 unexplained alignments are ranked review candidates; the other 81 flags are
one identified calligraphic convention (below), recorded but low priority.

## What Abdullah should look at, in order

1. **Two rotation-suspects** (all three signals agree, neither is in any
   existing flag list):
   - p115 `5:44:10` ٱلَّذِينَ — its first chunk (x 87-104) misfits its own
     letters (wres 1.07) and fits the previous word ٱلنَّبِيُّونَ's ن at
     5.1u; the donor misfits 0.79 on the facing side.
   - p474 `40:63:3` ٱلَّذِينَ — its last chunk (x 200-230) misfits (0.93) and
     fits the next word كَانُوا۟'s كا at 4.0u; donor misfits 0.73 facing.
   Caveat: both donors' damage could still be the stretch convention; these
   are suspects, not convictions of the p254 grade.
2. **4 unexplained** (whole-word alignment cost ≥ 0.8 with no single guilty
   chunk): p215 أَذِنَ, p319 أَذِنَ, p478 ءَامَنُوا۟ `41:18:3` (already
   convicted `verdict-OURS` by the reference — the audit found it
   independently), p508 ذِكْرَىٰهُمْ.
3. **20 width anomalies** outside the conventions, wres 1.20-2.39 — top of
   the list: p417 & p366 ذَٰلِكَ (likely the ذٰ dagger-alef widening the ذ
   beyond its table width — probably a letter-width model gap, not a defect),
   p301 أَذْكُرَهُۥ, p584 فَأَرَىٰهُ, p600 لَكَنُودٌۭ (juz-30 pages), three
   ٱلْأَرْض words whose final ض runs long. Two of the 20 are places the
   reference disagrees with us and the adjudicator sided with THEM (p129
   عِبَادِهِۦ, p455 بِأَمْرِهِۦ) — so at least those two are real.
4. **81 `final-nun-stretch`** — see below. Nothing to fix unless the
   letter-width table learns the convention.

## The metric

Per multi-chunk word, on the FINAL emitted assignment (the layer the p254
rotation actually escaped through): `align_segs_atoms(chunks, segments,
line_alpha)` with the line's absolute per-letter width (justification cancels
through it), per-group residual `|drawn span − α·expected|` in mean-segment
units (`wres`), and a cross-fit of the worst chunk against contiguous segment
runs of the adjacent word.

Two artefact families had to be handled inside the metric before the numbers
meant anything:

- **Dual hamzah model.** `segment_word` expects a standalone ء as its own tiny
  body, but the print draws many of them as a diacritic. Scoring only the
  body model put the whole ٱلسَّمَآءِ family at wres 2.4-2.5 (a solid false
  band) and made رَءَا infeasible. The audit scores both models and keeps the
  one the ink prefers; align-fails went 11 → 0.
- **`final-nun-stretch`.** The elongated final ن of إِنَّ / أَنَّ before the
  following word — 74 of the clean top-100. Tagged, never convicted.

## Calibration — and why width alone is not adopted as a proof

Clean subset (no r7fix sweep flag, no reference verdict, not in
reference_words): 51,815 of 52,105.

    wres: p50 0.233  p90 0.492  p99 0.814  p99.9 1.485  max 2.39
    tail: 1.0-1.2: 127 | 1.2-1.5: 48 | 1.5-1.75: 30 | 1.75-2.0: 16
          2.0-2.5: 4 | 2.5+: 0

**There is no empty band.** The tail thins continuously and is dominated by
the stretch convention, so per the project's empty-band rule the width
residual is NOT adopted as a standalone proof — it ranks a review list. The
conviction category (`rotation-suspect`) instead requires three signals:

1. own worst-chunk residual ≥ 0.90;
2. that chunk fits a contiguous segment run of the adjacent word at least 2x
   better, and well absolutely (≤ 0.35 mean-segment units);
3. the donor itself misfits ≥ 0.60 **on the side facing the suspect** (or is
   alignment-infeasible). An exchange damages both parties, on facing edges.

## Challenge log — confounders enumerated, tested, and the flags they reversed

| confounder | n (clean) | at wres ≥ 1.2 | outcome |
|---|---|---|---|
| ـوا۟ swash merge | 2,901 | 0 | the naive 1:1 prototype's ENTIRE top tail; the aligner's merge move absorbs it |
| ـرًا / ًا endings | 443 | 0 | same mechanism |
| letter-space compounds | 4 | 0 | each half aligns to its own segments; the inter-half gap never enters a group span |
| line-end / justified words | 6,381 | 5 (0.08%) | per-LINE alpha absorbs justification |
| juz 30 pages | 1,563 | 3 (0.19%) | mildly elevated vs 0.19% overall — no region tuning needed; only 3 of 107 final flags are juz-30 |
| pen-lift splits (nch<nseg) | 1,539 | 4 | many-chunks↔one-segment groups are legal in the aligner |
| surplus chunks (nch>nseg) | 1,069 | 1 | absorbed by merge groups |
| standalone-ء drawn as mark | — | was ~40 words incl. every ٱلسَّمَآءِ | reversed by the dual hamzah model |
| إنّ ٱللَّه final-ن stretch | — | 74 of clean top-100 | reversed 220 → 16 rotation flags by the pair-damage gate |
| ٱللَّه 'لله' width model (donor misfit 0.60-0.65, far side) | — | ~10 fake pairs | reversed 16 → 2 by the facing-side condition |

## Category totals

| category | n | meaning |
|---|---|---|
| rotation-suspect | 2 | all three exchange signals agree |
| width-anomaly (non-convention) | 20 | a chunk the wrong size for its letters; no exchange evidence |
| width-anomaly `final-nun-stretch` | 81 | the identified convention, recorded for completeness |
| unexplained | 4 | whole-word alignment cost ≥ 0.8, no single guilty chunk |
| infeasible | 0 | joining rules cannot express the held chunks (0 on this build after the dual hamzah model) |

103 of the 107 flags appear in no existing internal or reference list — this
audit sees a different axis than the count/interval/width audits.

## Known-positive / known-negative record

- Pre-fix p254 rotation (rebuilt with `QSVG_SPACESPLIT=0` and the p254
  overrides filtered at load; harness in the session scratchpad,
  `chunkfit_kp.py`): أَهْوَآءَهُم → **rotation-suspect**. PASS.
- p27 `2:181:3`, p177 `8:6:4` (بَعْدَ مَا), p451 `37:130:3`
  (إِلْ يَاسِينَ): clean, wres ≤ 0.22. PASS.
- ـوا۟ family: 0 flags. PASS.

## Honest limitations

- A rotation whose foreign chunks happen to match the word's own expected
  widths is invisible to this metric — width is the only identity evidence
  used; nothing reads the letter SHAPES.
- The two surviving suspects clear gates whose donors could still be the
  stretch convention; they are review items, not convictions.
- The `final-nun-stretch` and ذٰ dagger-alef families are letter-width model
  gaps; teaching `letter-widths.json` those two conventions would clean the
  width-anomaly list substantially.

## Repro

    . env.sh
    python3 tools/audit_chunkfit.py 1 604 14 docs/defects/chunkfit_flags.json
    # or re-categorize an existing dump without re-running pages:
    python3 tools/audit_chunkfit.py --from-dump <dump.json> <flags.json>
