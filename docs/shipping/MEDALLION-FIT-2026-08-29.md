# How well the ayah-mark rings fit — all 6,248 of them

**2026-08-29.** Measurement only; no artwork was changed.

The ornament rings are your addition, drawn around numerals that were already
there, so their size and position are parameters you control. This measures all
of them and says whether those parameters are right.

**Short answer.** The ring *size* is right and should not change globally: no
numeral anywhere touches its ring, and the tightest one still has a visible gap.
Three things are wrong, all local and all fixable without touching the design:

| | count | what it is |
|---|---|---|
| **Ring ink fused with word ink** | **85** | the ring's lower wing draws straight through a neighbouring letter stroke |
| Ring within 0.3 units of word ink | 136 more | not fused, but no gap you could call a gap |
| Ring not centred on its numeral | 228 | same numeral, two different placements across the mushaf |
| Ring drawn twice, one on top of the other | 12 | pages 1 and 2 only, byte-identical duplicates |

Everything below is in **rendered page units** — the SVG user space of
`viewBox="0 0 345 550"`. For scale: a ring is 18.30 units wide, a numeral about
6.2 units tall, so 1 unit ≈ 5.5% of a ring's width.

---

## Method, and the proof that the coordinates are one space

`tools/audit_medallions.py` reads the artwork (`mushafs/hafs/kfqc/svg/NNN.svg`),
flattens every path to points, and pushes every point through its full ancestor
chain — the root `matrix(1.3333 0 0 -1.3333 -55 640)` with its negative y-scale,
composed with each marker's own `translate(...) scale(0.011 -0.011)`. All three
measurements are then taken between point clouds in that one space; nothing is
compared across spaces.

**The proof.** The artwork itself records each medallion's centre on the numeral
group as `ayah:x`/`ayah:y`. Our independently computed numeral-bbox centre must
land on it, and does: median residual **0.032 units**, which is the two-decimal
rounding of the attribute itself. Where the residual is larger it is the
attribute that is stale, not the transform — on p113 every `ayah:y` is ~3 units
off while the numerals sit dead centre in their rings (verified by rendering).

Ayah identity comes from **position**, not document order: each marker is named
by the ayah polygon whose recorded centre it sits on. The known `tag_ayah_marks`
reversal bug (441 pages) is therefore not inherited here.

Accuracy: curves are flattened to 8 chords and then resampled so no gap exceeds
0.04 units, so every distance below is good to ±0.02.

Counts: **6,248 marker groups over 604 pages**, of which 6,236 are real
medallions — exactly the ayah count — and 12 are duplicates (see below).

---

## 1. Containment — is the numeral inside the ring?

**Yes, every single one.** All 6,236 numerals are fully inside the ring's central
opening by a point-in-polygon test, and none touches the ring ink.

Distance from the numeral's ink to the ring's ink:

```
numeral-to-ring gap, main ring (n=6,224), bin 0.1 units
  0.5-0.6      1
  0.6-0.7      3
  0.7-0.8      1
  0.8-1.1      0            <- empty
  1.1-1.2     12
  1.2-1.4      0            <- EMPTY BAND
  1.4-1.5      3
  1.5-1.6     10
  1.6-1.7  ****************                                    504
  1.7-1.8  *************************                           759
  1.8-1.9  **********************************************     1395
  1.9-2.0  **************************************************  1512
  2.0-2.1  *************************                           776
  2.1-2.2  *********************                               639
  2.2-2.3  **********                                          326
  2.3-2.4  ***                                                 118
  2.4-2.5  *                                                    59
  2.5-2.7      0
  2.7-3.3    106     (the short "٥٥"-type numerals, sitting in a tall opening)
```

min 0.587 · median 1.924 · max 3.293

There is a clean **empty band at 1.2–1.4**, so "gap < 1.3" is a threshold with a
proof behind it rather than a taste: **17 markers** are tight, and they are two
recognisable families.

**The four widest numerals** — 255 and 155 — plus one high-sitting 2:

| page | ayah | gap | numeral | left / right / top / bottom margin in the opening |
|---|---|---|---|---|
| 42 | 2:255 | **0.587** | 10.55 × 6.08 | 2.68 / 3.46 / 4.40 / 1.62 |
| 70 | 3:155 | 0.634 | 10.30 × 6.19 | 2.70 / 3.69 / 4.34 / 1.57 |
| 103 | 4:155 | 0.636 | 10.30 × 6.19 | 2.70 / 3.69 / 4.34 / 1.57 |
| 452 | 37:155 | 0.636 | 10.30 × 6.19 | 2.70 / 3.69 / 4.34 / 1.57 |
| 293 | 18:2 | 0.774 | 2.68 × 6.08 | 7.36 / 6.64 / **1.80** / 4.21 |
| 24 | 2:155 | 1.115 | 10.30 × 6.19 | 2.70 / 3.69 / 3.77 / 2.14 |

Crop: `medallion/tightest-numeral-p042-2_255.png` (2:255 — tight, but a real gap;
this one is fine as drawn, and it is the case that limits how far the ring can
ever be shrunk).

**Eleven "٥٥" markers** at gap 1.18 — these are not a size problem, they are the
centring problem in section 3.

Centring, measured as the numeral's ink-box centre against the ring's centre:
median **0.005 horizontal, 0.007 vertical**. The ring is centred on the numeral's
ink box, and that rule holds almost everywhere.

---

## 2. Clearance — does the ring touch other ink?

Distance from the ring's outer silhouette to the nearest non-mark ink on the
page (words and marks; other medallions are handled separately):

```
clearance histogram (n=6,246)
  0.000 - 0.001      2
  0.001 - 0.010     54      <- fused
  0.010 - 0.050     49
  0.050 - 0.100     21
  0.100 - 0.200     42
  0.200 - 0.300     53
  0.300 - 0.500     116
  0.500 - 1.000     462
  1.000 - 2.000    1794
  2.000 - 3.000    2179
  3.000 - 4.000    1147
  4.000 - 7.000     327
```

p1 0.011 · p5 0.460 · median **2.237** · p95 4.035 · max 6.337

**This distribution has no empty band.** It is a continuum, so no threshold on
clearance alone can be called a proof. One thing here *is* proof-class, and it is
the one that matters: a signed test of whether foreign ink lies **inside** the
ring's outer silhouette. That is not a prior, it is an overlap.

### 85 markers where word ink is inside the ring

Ranked by penetration depth. Full machine-readable list, all 221 flagged markers,
in `medallion/flagged.json`.

| # | page | ayah | depth | clearance | crop |
|---|---|---|---|---|---|
| 1 | 520 | 50:44 | 0.618 | 0.005 | `overlap-01-p520-50_44.png` |
| 2 | 575 | 74:7 | 0.555 | 0.008 | `overlap-02-p575-74_7.png` |
| 3 | 575 | 74:3 | 0.548 | 0.013 | `overlap-03-p575-74_3.png` |
| 4 | 585 | 80:15 | 0.467 | 0.002 | `overlap-04-p585-80_15.png` |
| 5 | 449 | 37:84 | 0.368 | 0.010 | `overlap-05-p449-37_84.png` |
| 6 | 579 | 76:6 | 0.368 | 0.018 | `overlap-06-p579-76_6.png` |
| 7 | 585 | 80:33 | 0.337 | 0.006 | |
| 8 | 569 | 70:19 | 0.328 | 0.008 | |
| 9 | 585 | 80:5 | 0.327 | 0.008 | |
| 10 | 575 | 74:6 | 0.322 | 0.0005 | |
| … | | | | | 75 more in `flagged.json` |

The crops carry a red circle at the contact point. **I looked at every one of the
six before writing this**: they are real. In p520 and p576 the ring's lower-right
wing and the tail stroke of the neighbouring word are a single connected blob of
ink — not a near miss.

**The mechanism is the wings, sideways.** 776 of the 799 close contacts are on
the ring's left or right, at |Δy| ≈ 6 units from the ring centre — that is the
height of the upper and lower flourish tips, which are the widest part of the
ornament (the ring is 18.30 wide at the wings, and the central oval is narrower).
Vertical clearance is not a problem: only 21 contacts are above or below, because
the line pitch leaves room. Crop `vertical-p576-74_29.png` is the worst of those.

Pages are not uniform: **34 of the 85 overlaps are on pages 574–586** (the short
juz-30 surahs, many medallions in tightly-set lines); p576 alone has 7.

### 136 more within 0.3, not overlapping

Worst: p290 17:80 (0.007), p239 12:31 (0.010), p285 17:34 (0.011),
p567 69:26 (0.016), p585 80:9 (0.016). Crop: `nearmiss-p290-17_80.png`.

### Ring against ring

No two distinct medallions come near each other anywhere. The only ring-ring
overlaps in the whole mushaf are the 12 duplicates below.

---

## 3. Fit quality — is one ring size right for every number?

**The ring is a constant.** Two sizes exist in the whole mushaf:

| ring | page units | markers | where |
|---|---|---|---|
| main, `scale(0.011)` | 18.304 × 24.419, opening 16.69 × 12.10 | 6,224 | pages 3–604 |
| small, `scale(0.0075)` | 12.480 × 16.650, opening 11.38 × 8.25 | 12 | pages 1–2 |

The numerals it has to hold are not constant — they vary **5.9× in width**:

| digits | n | numeral width (med / min / max) | numeral height | side margin in the opening | tightest gap |
|---|---|---|---|---|---|
| 1 | 955 | 3.30 / 2.06 / 4.14 | 6.14 | **6.69** | 0.77 |
| 2 | 4,303 | 7.26 / 4.74 / 9.73 | 6.17 | 4.71 | 1.18 |
| 3 | 966 | 9.75 / 7.60 / 12.09 | 6.19 | **3.47** | 0.59 |

So a one-digit ayah number sits with 6.7 units of white on each side and a
three-digit one with 3.5 — the ring is nearly twice as loose on the narrowest as
on the widest. Vertically it is loose for everyone: numerals are ~6.2 tall in a
12.1 opening.

**Should the scale adapt to digit count? No — and the measurement says why.**
Here is what a uniform shrink of the ring about its own centre buys and costs:

In the two tables that follow, "fused" means clearance < 0.01 — the
machine-checkable stand-in for the signed overlap test, which cannot be re-run at
a hypothetical scale. Today 56 markers are under 0.01 and 85 actually overlap;
every overlap is under 0.018, so the two agree closely.

| scale | ring width | fused (< 0.01) | < 0.1 | < 0.3 | min numeral gap, 1 / 2 / 3-digit |
|---|---|---|---|---|---|
| **1.00 (now)** | 18.30 | **56** | 126 | 221 | 0.77 / 1.18 / 0.59 |
| 0.98 | 17.94 | 29 | 73 | 142 | 0.68 / 1.05 / 0.46 |
| 0.96 | 17.57 | 15 | 33 | 83 | 0.58 / 0.93 / 0.33 |
| 0.95 | 17.39 | 8 | 24 | 64 | 0.54 / 0.87 / 0.26 |
| 0.93 | 17.02 | 4 | 11 | 31 | 0.44 / 0.75 / **0.13** |
| 0.92 | 16.84 | 1 | 7 | 24 | 0.39 / 0.69 / **0.07** |
| 0.90 | 16.47 | 0 | 0 | 8 | 0.30 / 0.56 / **0.01** |
| 0.85 | 15.56 | 0 | 0 | 0 | **0.07** / 0.26 / **0.00** |

Read the last column: the shrink that clears the outside (0.90 or smaller) closes
the inside on the three-digit numerals — at 0.90 the 2:255 medallion's numeral is
0.01 units from the ring, i.e. touching. A single global shrink cannot satisfy
both, and it is blocked by exactly **four markers** (2:255, 3:155, 4:155, 37:155).

A per-digit-count scale does better but is still not clean, and it makes
medallions visibly different sizes down the same page:

| policy (1 / 2 / 3-digit) | fused | < 0.1 | < 0.3 | min numeral gap |
|---|---|---|---|---|
| 1.00 / 1.00 / 1.00 (now) | 56 | 126 | 221 | 0.77 / 1.18 / 0.59 |
| 0.96 uniform | 15 | 33 | 83 | 0.58 / 0.93 / 0.33 |
| 0.90 / 0.92 / 1.00 | 3 | 11 | 28 | 0.30 / 0.69 / 0.59 |
| 0.88 / 0.90 / 0.98 | 1 | 3 | 13 | 0.21 / 0.56 / 0.46 |

None of them reaches zero, and all of them change 6,000 medallions that were
already fine to fix 221 that were not.

**A per-mark shrink, applied only where it is needed, reaches zero and costs
nothing anywhere else.** Requiring clearance ≥ 0.3 *and* numeral gap ≥ 0.5:

```
all 221 flagged markers are fixable; 0 failures
scale needed:  0.98 × 79   0.96 × 59   0.95 × 19   0.94 × 20
               0.93 × 13   0.92 ×  7   0.91 ×  9   0.90 ×  7   0.88 × 8
```

Two thirds need a shrink of 4% or less. The worst eight need 12%.

### Pages 1–2 are proportionally tighter

The small ring's numerals sit at a median gap of **0.80** against 1.92 for the
main ring, with top/bottom margins of ~1.46 against ~2.96. Nothing touches, but
if you ever want these to look like the rest of the mushaf the small ring wants
about 8% more size, not less.

---

## 4. The numeral is not always centred — 228 markers

The rule the artwork follows is "centre the ring on the numeral's ink box", and it
holds to a median of 0.005 units. But **228 markers are placed differently from
the majority placement of their own numeral**, by up to 2.16 units.

This one needs no threshold argument: the same two glyphs, ٥٥, are drawn at
identical size in 41 places, and in 11 of them the ring sits 2.16 units away from
where it sits in the other 30. At least one placement is wrong, and since the
numeral is original ink, it is the ring that moved.

Compare:

* `medallion/centred-55-p403-29_55.png` — margins top 3.94 / bottom 3.94 / left 4.70 / right 4.73
* `medallion/offcentre-55-p117-5_55.png` — margins top **5.72** / bottom **2.16** / left 3.51 / right 5.92

The second is visibly low and to the left. Every number involved contains ٥ or ٠:
25 (33 markers), 5 (32), 15 (30), 55 (23), 75 (17), 35 (16), 45 (16), 50 (13).
It looks like the anchor used for the ring was computed from a metric that treats
those digits differently in some passes than in others.

`medallion/offcentre.json` lists all 228 with the correction, both in page units
(`page_dx`, `page_dy`) and as the delta to add to the group's own
`translate(...)` (`translate_dx`, `translate_dy` — already divided by the root
matrix's 1.3333 and y-flipped, so they can be applied directly).

---

## 5. Twelve rings are drawn twice

On page 1 (7 medallions) and page 2 (5 medallions) every ornament group appears
**twice in a row, byte-identical** — same `transform`, same `d`. No other page in
the mushaf does this. It is invisible in a raster but it is duplicate ink, it
doubles the stroke's opacity under any non-opaque rendering, and it will show up
in any contour-conservation check. Delete one of each pair.

---

## Recommendation

**1. Do not change the global ring scale.** `scale(0.011 -0.011)` is right.
Containment is comfortable everywhere (median gap 1.92, worst 0.59, nothing
touching), 96.5% of markers already have ≥ 0.3 clearance, and every global
alternative measured above trades 6,000 good medallions for 221 bad ones. The
one-digit rings do look loose beside the three-digit ones, but that is what a
constant-size medallion *is*, and shrinking them is what causes the collisions to
be unfixable at the other end.

**2. Shrink 221 rings individually**, from `medallion/flagged.json`. For each,
replace that marker's `scale(0.011 -0.011)` with `scale(0.011×f -0.011×f)` — the
file gives `f` as `recommended_scale_factor` and the finished number as
`artwork_scale`. Because the scale is about the group's own origin and the
translate is unchanged, the ring stays centred on its numeral. Result: zero
overlaps, nothing under 0.3 clearance, and no numeral closer than 0.5 to its ring.

If you would rather not carry a table: **0.96 for everything except three-digit
numbers**, which stay at 1.00. That takes fused markers from 56 to 16, markers
under 0.1 from 126 to 39, and markers under 0.3 from 221 to 92, while the worst
numeral gap only moves from 0.59 to 0.58. It does not finish the job, but it is
one number.

**3. Re-centre 228 rings**, from `medallion/offcentre.json`, by adding
`translate_dx`/`translate_dy` to each marker group's existing `translate(...)`.

**4. Delete the 12 duplicate ornament groups** on pages 1–2.

Do 1, 3 and 4 and the mushaf has no visible medallion defect left except the 221
clearance sites; do 2 as well and it has none.

---

## Reproducing this

```bash
export QSVG_ROOT=$PWD
python3 tools/audit_medallions.py --jobs 32 --proof      # ~2 min, all 604 pages
                                                         # -> .cache/medallions.json
```

`--proof` prints the transform residual against the artwork's own `ayah:x/y`.
Per-mark output carries the ring and numeral boxes, the containment margins on
all four sides, the clearance and its contact point, the overlap depth, and both
the clearance and the numeral gap re-measured at eleven candidate ring scales —
which is where every table above comes from.
