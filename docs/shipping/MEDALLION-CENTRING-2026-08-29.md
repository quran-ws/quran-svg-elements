# Every ayah medallion's ring is now centred on its numeral — in all five mushafs

**2026-08-29/30.** You asked why some ayah markers do not have the number
centred, and whether they could all be fixed. They can, and they are: **12,290
rings across the five mushafs were off-centre; 0 are now.**

This is an **ARTWORK change**. It lives in `quranpedia/quran-svg` — the repo
where you drew the rings — and **must be pushed upstream**. Nothing in the
decomposition pipeline changed.

---

## The rule

You drew the ornament rings. The numerals are the original KFGQPC ink. So when
the two disagree, **the ring moves, never the number.**

> For each marker, measure the numeral's own ink bounding box and the ring's,
> and add the difference of their centres to the ring group's `translate(...)`.

One rule, no per-case table, correct by construction — including for ayah
numbers nobody has ever looked at. `tools/centre_medallions.py`.

The alternative was a table of measured deltas from the earlier audit
(`docs/shipping/medallion/offcentre.json`, 228 entries). That was **not** used:
a table fixes exactly the cases someone happened to measure. The derived rule
reproduces all 228 of those deltas **exactly** (max disagreement 0.0000 page
units) and then goes on to fix 12,062 more.

## Why any of them were off: the digit ٥

In Hafs, al-Dūrī and Shu'bah the defect is not scattered — it is one digit.

| mushaf | ayah numbers containing ٥ | ayah numbers without ٥ |
|---|---|---|
| al-Dūrī | n=1383, **52.6%** off-centre, median 0.87u | n=6874, 13.6%, median 0.04u |
| Hafs | n=1394, **37.7%** off-centre, median 0.13u | n=6909, **0.1%**, median 0.03u |
| Shu'bah | n=1394, **52.9%** off-centre, median 1.10u | n=6909, 13.2%, median 0.04u |
| Qālūn | n=1378, 64.1%, median 0.39u | n=6880, 51.9%, median 0.32u |
| Warsh | n=1379, 41.6%, median 0.24u | n=6885, 49.6%, median 0.30u |

Read the Hafs row: a number without a ٥ in it is misplaced **one time in a
thousand**; a number with one is misplaced **377 times in a thousand**. The
Arabic-Indic ٥ has a glyph origin unlike the other digits, so the numeral's
optical centre drifts inside a ring that was positioned from the number's
nominal spot. The worst Hafs cases are 5, 15, 25, 45, 55, 65, 105, 115, 135,
145, 150, 155, 255 — every one of them.

The drift is **quantised**, which is the clinching evidence. Of the 49 markers
drawing `٥٥`, twenty sit dead centre, six sit 0.58 units low, and fifteen sit
2.16 units low and left. Same two glyphs, same size, three different ring
placements. At least two of the three are wrong, and since the numeral is
original ink it is the ring that moved.

**Qālūn and Warsh are a different story.** There the ٥ effect is present but
small, and *everything* is loose: about half of all rings, ٥ or not, sit
0.3–3.1 units off, in a continuous spread with no empty band. Their ring
placement was simply less precise. The same rule fixes them.

## Before and after

Offsets in **rendered page units** (viewBox 345 × 550; a ring is 18.3 units
wide, so 1 unit ≈ 5.5% of a ring). Counts are per FILE, so the 118 surah-variant
re-crops in each mushaf count their markers again.

| mushaf | markers | off-centre >0.3u before | after | median before | median after | worst before |
|---|---|---|---|---|---|---|
| al-Dūrī | 8,268 | 1,666 (20.1%) | **0** | 0.038 | 0.026 | 2.80 |
| Hafs | 8,303 | 533 (6.4%) | **0** | 0.036 | 0.028 | 2.14 |
| Qālūn | 8,258 | 4,454 (53.9%) | **0** | 0.336 | 0.000 | 3.23 |
| Shu'bah | 8,303 | 1,647 (19.8%) | **0** | 0.038 | 0.026 | 2.80 |
| Warsh | 8,264 | 3,990 (48.3%) | **0** | 0.283 | 0.002 | 3.08 |
| **all** | **41,396** | **12,290 (29.7%)** | **0** | 0.082 | 0.024 | 3.23 |

Counting distinct medallions on the 604 pages only:

| mushaf | medallions | off-centre before |
|---|---|---|
| al-Dūrī | 6,218 | 1,348 (21.7%) |
| Hafs | 6,236 | 377 (6.0%) |
| Qālūn | 6,210 | 3,448 (55.5%) |
| Shu'bah | 6,236 | 1,350 (21.6%) |
| Warsh | 6,214 | 3,079 (49.5%) |

### Why the threshold is 0.30 units

Over the Hafs medallions the offset distribution has an **empty band**:

```
  <=0.25   5,861        0.25 - 0.38   1        >=0.38   375
```

Below 0.25 is the rounding of the two-decimal `translate` the artwork writes;
above 0.38 is real misplacement; between them there is nothing. The same band is
present in al-Dūrī and Shu'bah. It is **not** present in Qālūn and Warsh, whose
error is a continuum — there 0.30 is not a proof, it is a "do not churn the file
for an invisible amount" cut. What is left untouched anywhere is at most 0.30
units, i.e. **1.6% of a ring's width**. `--tol 0.05` would take even those.

## What changed on disk

**2,879 SVG files**, in the artwork repository (branch `main`, on top of
`1b427fab`):

| mushaf | files changed (of 722) |
|---|---|
| `mushafs/duri/kfqc/svg` | 540 |
| `mushafs/hafs/kfqc/svg` | 423 |
| `mushafs/qalun/kfqc/svg` | 703 |
| `mushafs/shubah/kfqc/svg` | 530 |
| `mushafs/warsh/kfqc/svg` | 683 |

Nothing else: no JSON, no `svg-br`, no other directory.

**Inside those files, the only thing that changed is the ring group's
`translate(...)`.** Proved, not asserted: every one of the 2,879 files was
compared with its committed version after masking out exactly that one substring
in each ornament group, and **all 2,879 are byte-identical outside it**. The
numeral paths, the ring `scale`, the word ink, the polygons, the `ayah:x`/`ayah:y`
attributes — all untouched. No numeral moved.

## Proofs the numbers are in one coordinate space

Coordinates are the trap on this project, so the transform is proved against a
quantity the tool does not use.

1. **The artwork's own `ayah:x`/`ayah:y`.** Each numeral group records the
   medallion centre in page coordinates. Our independently computed numeral-box
   centre must land on it: over 41,396 markers the residual is **median 0.0040,
   p99 0.0073 page units** — the two-decimal rounding of the attribute itself,
   and nothing more. (Exceptions, all pre-existing source defects, below.)
2. **Ring and numeral are siblings.** They share every ancestor, so all geometry
   is computed with each group's OWN transform only; ancestors — the root
   `matrix(1.3333 0 0 -1.3333 …)` with its negative y scale, and the ~120
   different viewBoxes of the variant crops — are composed *only* to report page
   units. No number is ever compared across spaces.
3. **Agreement with the earlier, independently written audit.** All 228 entries
   of `offcentre.json` matched, `|our delta − theirs|` **max 0.0000**.
4. **Variant re-crops.** 590 surah-variant files share their parent page's
   geometry. Each was corrected independently; afterwards every variant's set of
   ring transforms is still a subset of its parent's — **590 of 590**, exactly as
   before the change.
5. **Idempotency.** A second `--apply` run over all five mushafs rewrites
   **0 files**, on every mushaf.

## Looked at, not just measured

`docs/shipping/medallion/centred/` — before/after crops, rendered from the
committed and the working file, framed on the numeral (which does not move) so
the ring's movement is the only thing that changes.

| crop | what it shows |
|---|---|
| `hafs-p117-5_55.png` | the worst Hafs case, 5:55, off 2.14u — the two ٥s were high and right of the ring's centre |
| `hafs-p117-5_57-control.png` | 5:57 on the same page, off 0.14u — **byte-identical before and after**, the control |
| `hafs-p005-2_25.png` | a typical ٥ case, 0.42u |
| `douri-p158.png` | al-Dūrī, 2.80u |
| `douri-p002-spread.png` | the opening spread, 2.49u |
| `shubah-p456.png` | Shu'bah ٥٧, 2.80u |
| `warsh-p503.png` | Warsh ١١ sitting low in its ring, 3.08u |
| `qalon-p445.png` | Qālūn ٧٧ sitting low, 3.23u |

## Gates (Hafs only — it is the only mushaf with a decomposition)

Run against the **corrected** artwork, so a green result means our output tracks
the new source exactly.

| gate | result |
|---|---|
| `tools/audit_pixels.py 1 604` | **604/604 pixel-identical, FAILURES 0** |
| `scratchpad/bench.py` | **SCORE 137, FAILURES none, pixelfail 0** |
| `tools/audit_taxonomy.py` | **OK**, pages 1-604, 35 mark names, 3 waqf_al_muanaqah pairs |
| full sweep `1 604` (`.cache/sweeps/medcentre`) | **marks 0, intervals 1** — p350 only, the standing one |
| `centre_medallions.py` (2nd run) | 0 files to rewrite, all five mushafs |

The other four mushafs have no pipeline to gate against, so they are proved
directly instead — by the byte-level diff, the variant self-check, the
`ayah:x`/`ayah:y` residual, the rendered crops and the idempotency re-run above.

## Source defects found on the way (reported, not fixed)

These are pre-existing and were left alone:

* **11 numerals with no ink at all.** Qālūn `141.svg` (2), `381.svg` (1) and
  `589.svg` + its two surah variants (1 each): the numeral group is written but
  empty — `<g transform="…" ayah:x="…" ayah:y="…"></g>`. A ring with no number
  in it. The tool reports them (`numeral has no ink 6`, counting one per parent
  page plus variants) and skips them.
* **`ayah:x`/`ayah:y` are scrambled in Qālūn**, and on the al-Dūrī opening
  spread. The residual against them there is ~460 page units, i.e. the attribute
  names a different marker. This is the known `tag_ayah_marks` ordering bug; it
  does not affect the correction, which never reads those attributes.
* **12 rings drawn twice** on the opening spread of every mushaf (7 on page 1,
  4–5 on page 2), byte-identical duplicates one on top of the other. The tool
  detects the duplicate run and moves **every copy by the same delta**, so they
  stay exactly superimposed — moving one of a pair would have turned an invisible
  duplicate into two visibly offset rings. Deleting the duplicates is still worth
  doing, separately.
* **A few stale `ayah:y` values in Hafs and Shu'bah** (residual up to 7.3 units
  on a handful of markers, e.g. Hafs p113) where the attribute is stale but the
  ink is right.

## Reproducing

```bash
cd <the quranpedia/quran-svg clone>
export QSVG_ROOT=$PWD
python3 tools/centre_medallions.py --proof --hist       # check, ~30 s on 32 cores
python3 tools/centre_medallions.py --apply
python3 tools/centre_medallions.py                      # must report 0 to rewrite
```

`--mushaf`, `--files`, `--skip` and `--tol` narrow it. `--json` dumps every
marker's ring box, numeral box and offset.

## Push this upstream

The change is in the artwork, not the pipeline. It needs to go to
**`github.com/quranpedia/quran-svg`** — that is where the rings were drawn and
where every consumer of this artwork gets them from. Until it is pushed, only
this machine has centred medallions.
