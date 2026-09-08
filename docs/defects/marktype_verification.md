# Adversarial verification of the mark-type audit (marktype_flags.json, 1,093 flags)

Independent check, 2026-08-26. Method: (1) external arbitration of R7 against
MushafDatabase's decomposition of the same artwork, by registered geometry, not
labels; (2) a blind visual pass — 68 flags sampled across all adopted rules +
30 matched unflagged controls, shuffled, judged from rendered crops BEFORE the
rule id or claim was unsealed. Working files: `docs/defects/marktype_verify/`
(track1_r7*.json, blind/qNN.png, blind_public.json, blind_manifest.json,
blind_judgments.json).

**Headline: the DETECTIONS hold up almost perfectly. The single largest
CORRECTION is wrong.** R7's 926 flags are real mis-labels, but the flagged ink
is not "the tanwin pair's second stroke" — in 60 of 60 arbitrated samples it
is a LETTER of the word (ر، ء، د، م، ن، ة، و…), bbox-identical to the piece
MushafDatabase labels as letter text. The trial corrector's branch (b), which
renames these to `tanwin-part`, would convert ~900 letters into marks
mushaf-wide while every existing gate stays green. Do not adopt it.

---

## Track 1 — R7 vs MushafDatabase (60 flagged + 20 unflagged small_meem words)

Word identity was verified by rasm skeleton on every sample (80/80 matched);
per-page registration by word-body landmarks, median residual 0.02u.

### Agreement table

| population | n | QPC writes ۢ/ۭ | rasm_uthmani writes ۢ/ۭ | MushafDatabase word holds a meem/iqlab label | MushafDatabase holds successive-tanwin instead |
|---|---|---|---|---|---|
| R7-flagged | 60 | 0/60 | 60/60 | **0/60** | 60/60 (30 successive tanwin_al_kasr, 19 tanwin_al_damm, 11 tanwin_al_fath) |
| unflagged small_meem | 20 | 20/20 | 20/20 | **20/20** (7 dammah iqlab, 6 fathah iqlab, 3 kasrah iqlab, 4 small meem) | 0/20 |

So R7's core claim — the print draws NO small م at idgham/ikhfa tanwin, only
at true iqlab, and the QPC encoding is the reliable witness — is **confirmed
100% by the independent decomposition**, both directions. The 571 unflagged
meems are one uniform glyph (w 3.2–3.3); the flagged elements are 4.4–11.8
wide.

### But the flagged ink is not what R7 says it is

Mapping each flagged element's box into the reference frame
(`track1_r7_ident.json`):

| what the flagged "small_meem" turns out to be | n / 60 |
|---|---|
| bbox-IDENTICAL (all 4 edges < 0.5u) to a reference **letter** piece | 58 |
| bbox-identical to the reference's `kaf-hamzah` letter_part (the ك dagger of شَكٍّۢ) | 2 |
| identical or overlapping the reference's successive-tanwin stroke | **0** |

Letter identities across the 60: ء ×10, د ×5+, ر ×5+, م (word-final) ×6, ن ×4,
ة ×5, و، ب، يد، شك … Every case is the word's FINAL letter (or its last
letter_part) at exactly the position rasm_uthmani's meem-rescue key expected a small
م. And in **all 60 words the tanwin pair is already complete on our side**
(exactly one tanwin master welded from exactly 2 strokes) — so the flagged
element is a THIRD element: the letter, missing from the word's body. Examples:
وَفَسَادٌۭ p186 (bodies hold و + فسا; the د is the "small_meem"), هُزُوًۭا p300
(the و), أَعْدَآءًۭ p549 (the ء), قَوْمٍۢ p522 (the م).

**Consequences.**

- R7 as a DETECTOR is right: no meem exists, the name is wrong, and the family
  is invisible to every count audit exactly as claimed.
- R7's diagnosis ("the pair's second stroke or its welded outline") and the
  proposed correction `tanwin-part` are WRONG for the sampled population.
  The right correction is restore-to-body as the word's letter.
- **Trial corrector branch (b) is dangerous**: all 60 sampled elements sit
  within its 16u gate (max observed distance 6.8u, most < 4u), so it would
  rename letters into welded tanwin parts across ~900 words. Bench, pixel
  checks and audit_marks stay green through that (renames move no ink and
  small_meem is never count-demanded) — the same "clean score, broken word"
  trap CLAUDE.md warns about.
- This family is a real, previously uncounted semantic divergence from
  MushafDatabase: they carry these 900-odd letters as letters; we carry them
  as marks. The "25 words separate us" figure does not include it.
- Caveat on shape statistics: a true low-form ۭ meem can be 9.6u wide
  (مَّكَانٍۭ p434, confirmed `kasrah iqlab` by the reference), inside the
  flagged-width band — the split must stay text-driven (QPC), never geometric.

---

## Track 2 — blind visual pass

68 flags + 30 controls, judged cold from ~50u context crops (target red,
band edges dashed). Control sanity: 28/30 controls judged clean; the 2
exceptions are listed in the residue (one was my own error — بَثَّ p486's
"missing" third dot is the master's welded member, which is precisely R8's
bbox confounder working as documented).

| rule | sampled | verified defect | claim-consistent bookkeeping (data-checked) | refuted / benign | uncertain |
|---|---|---|---|---|---|
| R1 fathah-below | 9 | 9 | — | 0 | 0 |
| R2 kasrah-above | 4 | 4 | — | 0 | 0 |
| R2 tanwin-al-kasr-above | 5 | 5 | — | 0 | 0 |
| R4 half-pair | 9 | — | 9 (master `mem=0` in every flagged word; controls all `mem=1`; the twin visible unwelded in ink) | 0 | 0 |
| R7 meem-not-in-print | 10 | 10 (all letters: ر ×6, ء ×3, ة ×1; the true meems in the control set — p41 ۢ, p322 ۭ, p572 ۢ, p501 ۢ — were all judged correct meems blind) | — | 0 | 0 |
| R8 dot-content-weak | 4 | 0 | — | 0 | 4 (by design "needs eyes"; my eyes could not settle them either) |
| R9 outband | 9 | 7 | 1 (مَثَلًۭا p576: mark sits correctly on its word, the word's recorded band is another line — real word-level anomaly) | 1 (مَّرْقَدِنَا p443: the text's own stacked ۜ + ۗ between lines) | 0 |
| R10 waqf-vs-ink | 9 | 2 (both sides of the كَيْدَهُنَّۚ→إِنَّهُۥ waqf steal p239; مُسْتَمِعُهُم p525 holding المصيطرون's ۜ) | 6 (deficits real: the sign is drawn in ink but held by no word as a waqf — عَمِلُوا۟ۖ p504, بَصْۜطَةًۭ p159's ۜ, تَقُولُۖ p91, وَٱلسَّلْوَىٰۖ p171, خَلْفَهُمْۖ p42, لَهُۥۖ-type) | 0 | 1 (ٱلْقَوْمِ p112 surplus) |
| R11 dammah-deficit | 9 | 1 (أَعْيُنٌۭ p175: the tanwin_al_damm holds THREE welded outlines — it swallowed the يُ dammah; visible) | 7 (deficits real in data; the كُلٌّۭ ×4 all show the same 3-outline tanwin_al_damm) | 0 | 1 (يَـٰٓأَيُّهَا p544 fused curl) |

Notes and refutations argued from the ink:

- **R1's blanket `proposed: kasrah` (all 40 flags) is wrong for most of its own
  population.** The sample splits into (a) لأيات-family open-tanwin-al-kasr strokes
  below the band (q01, q26, q57, q69, q73, and likely q56) — the right name is
  the welded tanwin_al_kasr PAIR, not a plain kasrah, and the R2 corrector's guarded
  swap already owns that pattern; and (b) cross-line fathah steals
  (أَلَمْ p543 → the fathah sits on النجوى's line; وَتَتَّقُوا۟ p99 → the fathah
  of the next line's وَأَن) where the ink IS a fathah of another word and
  renaming it "kasrah" would be a second wrong. Detection: adopt. Rename: no.
- **R2-kasrah-above**: 4/4 are real strokes above the band top. Rename→fathah is
  right where the word's text owes a fathah (مِنَ p415, إِلَّا p431/p576) and
  wrong for فِى p599, whose text has no fathah — that stroke belongs to a
  neighbour, and the fix is ownership, not name. One exclusion.
- **R2-tanwin-al-kasr-above**: 5/5 visually confirmed exactly as described — two
  welded strokes riding above the word top, the word's true tanwin_al_kasr below
  named fathah+fathah (q64/q73 are the two halves of the same p216 word).
  `fathah+fathah` is the correct correction; corrector branch (a)'s guards
  (fathah budget match + below-band strokes present) held in every sample.
- **R9**: 7/9 are genuine steals, including two that are simultaneously R7-type
  letter mis-names (بِخَيْرٍۢ p129 holding the next line's ه/ۦ piece of
  عِبَادِهِۦ; حَسَنًۭا p231 holding the UPPER line's قَوْمِ letter م). The one
  benign hit is مَّرْقَدِنَا ۜ ۗ p443, whose own text draws both signs between
  the lines — R3 exempts text-carried low stops but R9 has no such exemption;
  add one.
- **R10/R11 are word-level count claims; a crop of the anchor mark cannot
  refute them**, so they were re-verified from the data. Every sampled deficit
  is real in the assignment. R11's recurring mechanism is now identifiable:
  the tanwin_al_damm weld absorbs a third waw (the word's plain dammah), leaving the
  dammah count short with zero stray ink — أَعْيُنٌۭ p175 shows it plainly, and
  all four كُلٌّۭ samples repeat it. That is a narrower and more actionable
  root cause than the flag notes suggest.

---

## Verdicts

| rule | verdict |
|---|---|
| **R7 detection** (926 flags: "no meem in this print here") | **SAFE TO ADOPT** — externally confirmed 60/60 + 20/20 |
| **R7 proposed fix / corrector branch (b)** (`tanwin-part` rename) | **DO NOT ADOPT** — the flagged ink is the word's final LETTER in 60/60 arbitrated samples; the correct fix is restore-to-body, per word, with the reference as the witness |
| R1 detection | SAFE TO ADOPT |
| R1 proposed `kasrah` rename | DO NOT ADOPT as a blanket — split the population: лأيات-family → the R2 pair-swap; R9-adjacent steals → ownership repair first |
| R2 tanwin-al-kasr-above + corrector branch (a) | SAFE TO ADOPT (guards verified in every sample) |
| R2 kasrah-above | ADOPT WITH EXCLUSION — rename only where the word's text owes a fathah (excludes فِى p599-type; fix those as transfers) |
| R4 | SAFE TO ADOPT (detection; every flagged master twin-less in data, pair visible in print) |
| R8 | ADOPT AS "FOR EYES" ONLY (as designed; none of the 4 resolvable, even visually) |
| R9 | SAFE TO ADOPT as ownership-suspect detector; add an exemption for words whose own text carries the drawn sign (p443 type) |
| R10 | SAFE TO ADOPT (detector); the كيدهن/إنه p239 pair and p525 confirmed |
| R11 | SAFE TO ADOPT (detector); root cause refined: 3-outline tanwin_al_damm welds |

## Residue — one-glance items for Abdullah

| image | question |
|---|---|
| `marktype_verify/blind/q94.png` | ٱلْقَوْمِ p112 (5:25:12): three dot-sized blobs below the word, one held as a surplus "waqf". A split ۛ, a neighbour's letter dots, or stray ink? |
| `marktype_verify/blind/q38.png` + `q68.png` | وَٱلشَّهَـٰدَةِ p548: the ش cluster is held as three_dots(2 blobs)+two_dots(1 blob) = 3 units, but the word's budget is 5 (ش3+ة2) — where are the ة dots held? |
| `marktype_verify/blind/q23.png` + `q29.png` | بِثَلَـٰثَةِ p66: same question — held dot units sum to 7 against a budget of 9 |
| `marktype_verify/blind/q63.png` | تَغِيضُ p250 (control, unflagged): its fathah sits ~10u above the band top, higher than every neighbour's — legitimate short-word high fathah, or a stolen stroke the "fathah-above is always legit" assumption hides? |
| `marktype_verify/blind/q85.png` | يَـٰٓأَيُّهَا p544 (R11): a curl welded beside the fathah over أَيُّ — is that the missing dammah fused into the fathah outline? |
| `marktype_verify/blind/q33.png` | مَثَلًۭا p576 (74:31:38): the marks sit correctly on the word, but the word's recorded band is 17u away on another line — which layer is wrong? |
| `marktype_verify/blind/q92.png` | خَلْفَهُمْۖ p42: the drawn ۖ sits high-left of the word; which element holds it, and as what? |

Method caveats on my own work: crops colour every mark path within 1.5u of the
target, so red sometimes covers an adjacent mark; weld members further than
1.5u stay black, so "the twin is black" never proved unwelded (R4 was verified
from `mem` counts, not colour). Blind-sample crops were rendered from freshly
generated page SVGs (current pipeline), not the possibly stale review cache.
