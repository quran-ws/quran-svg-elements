# Width-flag diagnosis: p592–600 cluster + outside samples (2026-08-28, read-only)

**Verdict up front:** the juz-30 width cluster is not, in the main, a body-partition
defect. It is the width METRIC lying on exactly those pages. Of the 92 confidence
width flags on p592–600, ~88 evaporate when the expected width comes from the
calibrated letter-sum instead of the raw QCF advance table — because the QCF table
is scrambled on the 26 layout-drift pages, a fact `assign_words.letters()` already
knows and guards against, but `audit_width.py` and `score_confidence.py` do not.
Two genuine boundary mis-cuts (class a) were found in the cluster, both provable
by piece arithmetic alone: **p596 L1 إِذَا↔تَرَدَّىٰٓ** and **p600 L1
لِرَبِّهِۦ↔لَكَنُودࣱ**.

Everything below was measured on the CURRENT build (the one behind sweep
`.cache/sweeps/i39full`), fresh `assign_page` runs, nothing modified.

---

## 1. The three mechanisms behind the width family

### Mechanism C1 — the QCF advance table is scrambled on the drift pages

`.cache/qcf_widths.json` was paired word-by-word per QCF page font using
quran.com's mushaf-2 layout. On the 25-26 pages where that layout lies about page
membership (reported.json item 21: p121–123, p145, p532–534, p565, p568, p570,
p576, p584, p586, p588–600) the pairing is rotated, so words carry OTHER WORDS'
advances. `assign_words.py:975-983` documents this ("لا wider than يموت") and
falls back to the letter-sum via `_QCF_SUSPECT` — **but only inside the
pipeline**. The audits read `qcf_widths()` raw:

- `tools/audit_width.py:62` — `q.get("%d:%d:%d" ...)` with no guard
- `tools/score_confidence.py:140` — `q.get(x["k"])` with no guard

Direct evidence the table is wrong there (raw values, p599 98:6):

| word | raw QCF advance | sanity |
|---|---|---|
| إِنَّ (98:6:1) | 1.685 | a 2-letter word given the width of a long one |
| ٱلَّذِينَ (98:6:2) | 0.582 | a 5-piece word given a short word's width |
| خَٰلِدِينَ (98:6:11) | 0.636 | same |
| شَرُّ (98:6:15) | 1.842 | a 2-letter word, huge advance |
| أُو۟لَٰٓئِكَ (98:6:13) | 0.431 | smallest advance on the line |

Correlation of QCF advance vs letter-sum per page (Pearson, all words with an
advance): **normal pages 0.89–0.93** (p2, p50, p200, p341, p418, p450, p500);
**drift pages 0.59–0.69** on p593/596/599/600, 0.81–0.85 on p121/122. The
collapse is exactly where the flags cluster.

Re-scoring every flagged line with the letter-sum share instead (same
thresholds 0.70/1.45, MIN_OFF 4): on the 20 flagged lines of p592–600 + p121,
**124 words flag under raw QCF, 10 under letter-sum** — and the piece counts
(held vs `segment_word` allowance) match on every one of those 124 except the
two class-(a) pairs below and the benign detached-ك family (§4).

Example, p596 L2 (the eye-verdict line), current build:

| word | held/allowed | drawn | ratio vs QCF | ratio vs letter-sum |
|---|---|---|---|---|
| لَلْهُدَىٰ | 2/2 | 38.0 | 0.62 ⚑ | 1.10 |
| وَإِنَّ | 3/3 | 20.5 | 0.52 ⚑ | 1.07 |
| لَنَا | 1/1 | 12.7 | 0.67 ⚑ | 0.84 |
| لَلْـَٔاخِرَةَ | 3/3 | 36.2 | 1.21 | 0.93 |
| وَٱلْأُولَىٰ | 5/5 | 40.6 | 1.98 ⚑ | 1.03 |
| فَأَنذَرْتُكُمْ | 4/4 | 52.8 | 2.67 ⚑ | 0.92 |
| نَارࣰا | 3/3 | 19.9 | 0.49 ⚑ | 0.97 |
| تَلَظَّىٰ | 1/1 | 30.0 | 1.44 | 1.19 |

Every word holds exactly its joining-rule piece count, the spans are strictly
RTL-ordered with no interleaving, and against the letter-sum the whole line sits
in 0.84–1.19. The 6 flags are the scrambled table, not the partition.

### Mechanism C2 — one stray mark poisons a whole line's shares (p418 only)

`score_confidence._scan_page` measures a word's span over ALL elements
(deliberate, for the ۥ/ۦ suffix family — `score_confidence.py:111-116`).
p418 33:3:4 وَكَفَىٰ still carries two fathas with `gap≈290u` (the confirmed
ref-line/slashx defect from round 10), so its span reads 267u wide → width 5.5x,
and every other word on p418 L6 dilutes to ~0.5x. **All 11 of p418's off-drift
width flags sit on lines poisoned this way; mushaf-wide, p418 is the only such
page** (no other off-drift page has a width flag on a line with a >60u-gap
mark). `audit_width` (body-only spans) sees the same lines nearly clean.
Fix the one mark defect (already queued in the slashx family) and p418's width
cluster collapses; independently, the span used for the WIDTH shares should
exclude marks further than a line-height from the word's body ink.

### Mechanism B — genuine print layout (kashida stretch / compression)

Words whose piece counts are exact and which are the "wrong" size under BOTH
metrics. Mushaf-wide my two-metric scan finds **99 such words**; ~75 are
stretched short function words at line ends — إِنَّ at 1.85–2.04x (p341 twice,
p597 L14), مِن/مِّنْ at 1.5–1.9x (p341 L12, p76, p199…), فِى at 1.5–2.3x,
كَلَّا 1.6x (p598 L3), and the compressed بَرِيَّة pair on p599 (0.77/0.79 in
both ayahs — systematic, the print really draws it tight). These are facts about
the artwork to record, not defects. (A sub-family inside the 99 is an artifact of
body-only spans: لَهُۥ measuring 0.5–0.7x eight times because its ۥ is a mark —
`score_confidence`'s all-element span already handles it; `audit_width` doesn't.)

### Mechanism A — real boundary mis-cuts (the class the task asked about)

Signature: an ADJACENT pair on one line where one word holds MORE pieces than
`segment_word` allows and its neighbour holds FEWER — piece arithmetic wrong on
both sides, in compensating directions. Sweeping all 20 diagnosed lines of
p592–600 + p121/p341/p418, exactly **two** pairs match:

**p600 L1 — لِرَبِّهِۦ (1/2) ↔ لَكَنُودࣱ (3/2)** — the textbook case:

| piece | span | belongs to |
|---|---|---|
| لر | 258.2–272.0 | لِرَبِّهِۦ holds it — its only piece |
| **به** | **251.6–261.8** | **held by لَكَنُودࣱ, drawn overlapping لربه's span, 9u clear of لكنود's own ink** |
| لكنو | 216.6–242.5 | لَكَنُودࣱ |
| د | 214.6–219.9 | لَكَنُودࣱ |

لربه draws 13.9u where the letter-sum expects ~25 (0.55x); لكنود draws 47.2 vs
~40. Move the به piece one word right and both words' counts and widths land.

**p596 L1 — إِذَا (2/3) ↔ تَرَدَّىٰٓ (4/3)**: إذا holds 108.2–116.6 (two
pieces); تردى holds 104.0–107.0 (a 3.0u alef-sized piece adjacent to إذا, 2u
from تردى's own ink at ≤102.3) plus its own تر|د|ى at 73.4–102.3. The 3u piece
is إذا's final ا. إذا reads 0.31x under QCF, 0.77x under letter-sum.

Off the diagnosed set, the same both-sides-arithmetic signature marks the
already-known six boundary words (وَمَآ p546, يَدَهُۥ p164, فَوْقَ p129,
قَالُوا۟ p549, بَعْدِهِۦ p71, يَحْزُنكَ p413 — يحزنك and وما show held 1/2 in
the scan) and p123 5:95:27 أَوْ (1/2, drawn 2.9u — Abdullah's round-10 أَوۡ
trio). Class (a) mushaf-wide is on the order of **10–15 word PAIRS**, not
hundreds.

---

## 2. The eye-verdict acceptance cases, re-measured on the current build

Abdullah's round-10 verdicts (27 Aug ~20:30) predate the i39full build
(28 Aug 00:42). Re-measured now:

- **p596 92:14:1 فَأَنذَرْتُكُمْ / 92:14:2 نَارࣰا**: counts 4/4 and 3/3, spans
  strictly ordered, letter-sum ratios 0.92 / 0.97. The theft he saw is *not
  measurable in the current assignment*. The review server serves cached SVGs —
  **rebuild p596 and re-eye before writing any corrector for this line**; if his
  verdict still stands against the fresh render, the cut is wrong in a way piece
  arithmetic cannot see and the line goes to the proposals page, not to a pass.
- **p599 98:6:2 / :11 / :13**: his notes name kasra/fatha thefts — MARK defects
  (slashx / band family, 98:6:13 has `fatha 1/2`), not body-boundary defects.
  Body counts on those words are exact (the 4/3 on أولئك is the detached-ك
  stroke, §4). Their width flags are mechanism C1.

## 3. Per-line classification (all 20 diagnosed lines)

Machine version in `width_lines.json`. Classes: **a** = boundary mis-cut,
**b** = print layout fact, **c1** = QCF-scramble metric artifact, **c2** =
stray-mark-poisoned span (score_confidence only).

| line | flags | class | residue after metric fix |
|---|---|---|---|
| p592 L1 | 5 | c1 | — |
| p592 L2 | 6 | c1 | تَزَكَّىٰ 0.61x both metrics, counts exact → eye |
| p593 L1, L2, L6 | 7+4+1 | c1 | — |
| p594 L1, L2, L13, L14 | 6+2+1+3 | c1 | — |
| p595 L1 | 1 | c1 | — |
| p596 L1 | 7 | **a** + c1 | move تردى's 104.0–107.0 piece → إذا |
| p596 L2 | 6 | c1 | re-eye 92:14:1/2 on a FRESH render |
| p597 L1, L2 | 6+6 | c1 | — |
| p597 L14 | 1 | b | إِنَّ stretched 1.85x, counts exact |
| p598 L1, L2 | 3+2 | c1 | — |
| p598 L3 | 4 | c1 + b | كَلَّا 1.6x stretch; وَٱقْتَرِب۩ 0.78 (۩ shares) |
| p599 L1 | 6 | c1 | (98:6:2 verdict = mark family) |
| p599 L2 | 5 | c1 + b | البرية 0.79x print-tight; 98:6:13 fatha = slashx |
| p599 L3 | 4 | c1 + b | البرية 0.77x (same, second instance) |
| p600 L1 | 8 | **a** + c1 | move لكنود's 251.6–261.8 piece → لربه |
| p600 L2, L14 | 5+1 | c1 | — |
| p121 L13, L14, L15 | 2+3+6 | c1 (drift page) | مِنَ 1.75x → b |
| p341 L5, L6, L7, L10, L11, L12 | 8 total | b | إِنَّ 2.04x/1.87x, فِى 1.53x, مِن 1.69x — all counts exact, kashida |
| p418 L5, L6, L11, L12 | 15 (confidence) | c2 | root = 33:3:4 stray fathas (known, slashx queue) |

## 4. Trap for any repair pass: the detached-ك / pen-lift surplus family

Raw body counts show held = allowed+1 on ذَٰلِكَ، رَبِّكَ، لَكَ، ذِكْرَكَ،
ظَهْرَكَ، أُو۟لَٰٓئِكَ، فَكُّ، هُمْ… across these pages: the miniature stroke
inside final ك (and some pen-lifts) is a separate contour. It appears on BOTH
instances of a word (both p599 أولئك hold 4/3) — systematic drawing, not theft.
A count-driven re-deal must use effective pieces (the overlap-merge in
`score_confidence.py:162-182` — noting that merge currently over-collapses:
ظَهْرَكَ raw 3 → n_eff 1) or it will "repair" hundreds of healthy words.

## 5. Proposed systemic repairs, in order

1. **Fix the metric (biggest win, zero pipeline risk).** Make both consumers
   respect the drift guard: in `audit_width.py` and `score_confidence._scan_page`,
   take expected width from `aw.letters(word)` (which already falls back to the
   letter-sum when `_QCF_SUSPECT` is set / the advance is implausible) instead of
   raw `q.get()` — or equivalently, distrust an advance whose est/letter-sum ratio
   is outside [0.5, 1.45] on pages where page-membership drift was detected.
   Detector-only change; the pinned-baseline comparison rules (bench, cmp_full)
   still apply because sweep flag counts shift.
   *Acceptance:* p592–600 width flags fall 92 → ≈10; p121 similarly; no
   body/mark ownership changes anywhere (pixelfail 0 trivially — no emission
   change); the surviving flags are §3's residue column.
2. **score_confidence span hygiene:** exclude marks more than a line-height
   (~40u, inside the measured empty band of the stray audit) from the WIDTH span
   only. Kills p418's 11 collateral flags without touching the suffix-ۥ rationale.
3. **Class (a) corrector — a late line-level piece re-deal**, hosted as a new
   pass at the END of `assign_page` (beside the QSVG_RESEAT block,
   `assign_words.py:~9302`), switch `QSVG_LREDEAL`, default off until measured:
   - *Trigger (proof-class only):* adjacent word pair on one line with
     compensating effective-piece errors (+k / −k) against `segment_word`.
   - *Action:* transfer the boundary-side body piece(s) — the surplus word's
     piece(s) nearest the deficient neighbour, on the correct side in reading
     order — until both counts match. Bodies only; marks follow later via the
     existing orphan/stray logic (never move slash-family strokes). Use
     `_omove`/`put_in_ligature`, never `at[0]`.
   - *Never width-driven:* width is not even a tiebreaker here (QSVG_WDECIDE
     lesson); the piece allowance is the whole constraint, reading order picks
     which piece moves.
   - *Acceptance cases:* p600 L1 لربه/لكنود and p596 L1 إذا/تردى flip to exact
     counts and letter-sum ratios in [0.7,1.45]; the six known boundary words
     (p546/p164/p129/p549/p71/p413) and p123 أَوْ clear where the pair signature
     holds; Abdullah re-eyes p596/p599 fresh renders.
   - *Regression guards:* none of p592–600/121/341/418 are DKSEG/RESEAT pages
     (p254/p27/p177 بَعْدَ مَا, wasla/small-waw reseat) — still, skip
     letter-space compounds and any word pair straddling a line boundary; skip
     pairs where the surplus is the detached-ك family (§4: surplus piece
     overlaps its own word's span — the لكنود piece does NOT, it overlaps the
     NEIGHBOUR's); full-sweep gate: total falls, no page worse than +1,
     bench + pixelfail 0, `audit_lines`, `verify_render`.

## 6. Numbers for the 591-word family (task 5)

Current confidence cache holds **646** width-metric words on 321 pages (the 591
figure is the same family measured a build earlier); the raw `audit_width`
equivalent on the current build is 1573 words (matches the tool exactly on
spot-checks).

| bucket | words (confidence family) | what clears them |
|---|---|---|
| drift-page QCF scramble (26 pages) | 147, of which ~130–135 | repair 1 (metric guard) |
| p418 stray-mark span poisoning | 11 | repair 2 / the queued slashx fix |
| class (a) boundary mis-cuts | ~20–30 (10–15 pairs, both sides flag) | repair 3 |
| class (b) print facts (stretch/compression, counts exact) | ~75–90 | record, never "fix" |
| remaining QCF-vs-print single-word noise (advance ≠ this instance, letter-sum agrees with the ink) | the rest (~400) | mostly falls out of repair 1 generalised: flag only when BOTH metrics agree |

Bottom line: a class-(a) re-deal is worth building for its ~10–15 real pairs
(they include the words Abdullah keeps catching by eye), but it will NOT move
the 591 number much. The 591 number is moved by making the width metric stop
trusting a table the pipeline itself already distrusts.

---

*Method: fresh `assign_page` per page with a `rewrite` spy (audit_width's own
mechanism), per-line reconstruction of piece spans vs QCF-share slots, and a
mushaf-wide two-metric scan (both `audit_width` thresholds). Scripts in the
session scratchpad (`width_diag.py`, `width_scan.py`); no repo file was
modified. Confidence caches read from `.cache/confidence/{pages,raw}` (rebuilt
28 Aug 00:48–00:50, current).*
