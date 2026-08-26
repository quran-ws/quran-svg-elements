# CERTAIN-Tier Defect Elimination Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the 47 proof-class (CERTAIN) defects found by `tools/score_confidence.py` to zero — by root cause, not word by word — without regressing anything.

**Architecture:** The 47 defects collapse into six causal families. One agent per family: diagnose (read-only, parallelizable), then fix serially — every fix funnels through the same `tools/assign_words.py`, so concurrent edits would conflict. Every fix passes the repo's gate before the next family starts. A defect that turns out to be genuine artwork is recorded as data (override / `reported.json`), never as a code special-case.

**Tech stack:** Python 3, the existing pipeline (`assign_words.py`), audits, `score_confidence.py`, review platform.

**Spec:** the CERTAIN list in `.cache/confidence/pages/*.json` (proof strings are the requirements); family tables below.

## Global constraints (every task, non-negotiable)

- Run everything from `$QSVG_ROOT` (`~/Dev/github.com/AbdullahObaid/quran-svg-work`) after `. env.sh`.
- A fix is accepted only if: `scratchpad/bench.py` shows SCORE ≤ 76, no FAILURE, pixelfail 0; `scratchpad/cmp_pages.py` on the target pages improves; a full sweep shows total falls and **no page worsens by more than +1**.
- Two signals or a proof: a mark moves only where the text budget says a move is owed AND the ink confirms which mark and direction — or where a single proof-class fact (empty band, joining rules) stands alone.
- Never move fatha/kasra-family strokes between words (measured: +2 on four pages). Never use nearest-word for gap ink — direction beats distance.
- Movers must use `put_in_ligature()` / `_omove()`, never `at[0]`.
- Human decisions become data: labels → `apply_labels.py` (measured with `label_bisect.py`), places → geometry-keyed overrides.
- Every hard-won fix gets a bench case in `scratchpad/bench.py` `CASES`.
- After each accepted fix: `rm .cache/confidence/raw/<page>.json` for touched pages, re-run `score_confidence.py` on the family's pages, confirm the family's proofs are gone; append the outcome to `docs/defects/reported.json`.

---

### Task 0: Pin the baseline

**Files:** none created; verifies environment.

- [ ] **Step 1:** `. env.sh && cd $QSVG_ROOT && python3 scratchpad/bench.py` — expect SCORE 76, no failures, pixelfail 0. If not, STOP.
- [ ] **Step 2:** Snapshot the current sweep as the "before": `QSVG_OUT=$QSVG_SWEEPS/certfix-base python3 scratchpad/full_sweep.py 1 604` (~25 min; run once, reuse for every family's comparison).
- [ ] **Step 3:** Record the current confidence totals (47/426/516) in `docs/defects/reported.json` as the starting point.

---

### Task 1: Family A — iqlab-tanween ligature surplus (12 words) — ✅ DONE 2026-08-26

Fixed in three parts (`_IQTAN` early-exit decoupled; next-word meem claim may claim a
word's own piece; late position-aware self-rescue `QSVG_IQLATE` anchored on the word's
own tanween). 10 of 12 fixed; p203/p219 turned out to be pen-lift contour splits —
counting fixed in `audit_marks`/`score_confidence` (reported.json items 18-19). Bench
cases added for p143/p222. Open remainder: p437 `بِيضٌۭ` second م-piece needs a visual
verdict; +32 interval flags are naming-visibility on tight iqlab kerning (see
CLAUDE.md state table note). Steps below kept for the record.

`أُمَّةٍۭ p85, حُجَّةٌۢ p104, أَلِيمٌۢ p136, شَدِيدٌۢ p143+p454, صَـٰلِحًۭا p203, تَارِكٌۢ p222, جِنَّةٌۢ p346+p429, بَارِدٍۢ p535, وَعَادٌۢ p566, نُنَجِّيكَ p219` — 11 of 12 end in tanween + iqlab meem (`ٌۢ ٍۢ ًۭ`); the previews show a stray م drawn near the word counted as a letter piece.

**Files:** Modify: `tools/assign_words.py` (likely the iqlab/tanween passes near `:4917` and `:5416`, or classify). Test: bench + `cmp_pages`.

**Root cause CONFIRMED** (see `docs/defects/iqlab_notation.md`, reported.json item 18): this print draws iqlab as ONE haraka + small م, never a tanween pair. The `_IQTAN` pass at `assign_words.py:4917` knows this, but exits early (`continue  # already named`) whenever the tanween is already named by the shape table — skipping the meem rescue, so the م stays counted as a letter piece.

- [ ] **Step 1 (verify per word):** For p143 `شَدِيدٌۢ`: `QSVG_TRACE=<x-of-the-م> python3 tools/assign_words.py hafs/kfqc 143`; confirm the surplus piece is the small م near the tanween stroke and that `_IQTAN`'s "already named" branch is what skips it (add a temporary print or use `QSVG_ODBG`). Check the four `ۭ` words (p85, p203, p535, p566) specially — `:5416` claims the low form leaves no standalone glyph, yet they measure +1 piece.
- [ ] **Step 2 (fix):** In `_IQTAN` (`:4917`), decouple the meem rescue from the tanween rename: run the rescue whenever the text has `ۢ`/`ۭ` and the word holds no `meem-iqlab` mark, regardless of whether the tanween is already named. Keep the existing size window (w 1.5–12u, h 3–12u) but measure whether d<14u reaches all 12 words before widening anything — widen only inside a measured empty band.
- [ ] **Step 4 (gate):** `python3 scratchpad/bench.py` (SCORE ≤ 76, pixelfail 0); `python3 scratchpad/cmp_pages.py 85 104 136 143 203 219 222 346 429 454 535 566`.
- [ ] **Step 5 (family sweep):** Rescan those pages with `score_confidence.py`; expect the 12 `ligature surplus` proofs gone and no new proofs anywhere on those pages.
- [ ] **Step 6:** Add a bench case for `شَدِيدٌۢ` p143 (`nbody(e) == 2` after the joining rules) and re-run bench. Append the outcome to `reported.json`. Commit.

---

## Expanded targets — 2026-08-26 visual round

Abdullah reviewed the CERTAIN tier by eye (`docs/defects/visual_verdicts.json`, 21
verdicts, with the STEAL DIRECTION named per word — that note is the second signal the
correctors below must consume). Expansions measured mushaf-wide from the post-iqlab-fix
rescan:

- **Vertical band steals: 55 marks ≥10u outside their line band** (his 12 confirmed +
  43 siblings). Sub-families: 11 pause marks (all the "stole صلى from the word
  above/below" shape — 3 confirmed + 8 in the 10–14u zone: p45 p93 p108 p140 p149
  p214 p443 p525); ~30 fathas; 4 meem-iqlab; the rest singletons.
- **The real unit of repair is the LINE, not the word.** The width-swallow expansion
  (99 words ≤0.55x expected) clusters onto ~9 lines: p254 line 7 (13:37 — 12 words,
  contains the space-word بَعْدَ مَا), p350 24:3 (10 words — the original وَٱلزَّانِيَةُ
  line), p371 26:95–97 (11 words), p535 56:33–35 (6), p576 74:31 (5 band fathas, juz
  30), p599 98:6–7, p507 47:4–8, p593/p596/p600 (juz-30 short-word lines). Fix the
  line's partition once and its whole word list clears.
- **Letter-space words are a closed family of 5**: بَعْدَ مَا p27/p177/p254,
  دَآئِرَ ةٌ p117, إِلْ يَاسِينَ p451 (human-verified no-issue — the joining-rule
  surplus proof does NOT apply to it; keep that as data, not a code exception).
  p27/p177/p117 need one visual check each.
- **p254 ROOT CAUSE FOUND (Abdullah, reported.json item 20):** the print draws
  بَعْدَ at line 6's end and مَا at line 7's start — the compound breaks ACROSS the
  line boundary, which the one-word-one-line text model cannot express. The pipeline
  forced the whole word onto line 7; بعد's line-6 ink folded into أَهْوَآءَهُم (4/5
  pieces — its "extra" fathas/sukun are بعد's), and the word took a piece from
  جَآءَكَ (2/3). The entire 12-word width cluster, the mushaf's only rtl-order flag,
  and this page's interval flags are ONE defect. Fix: let a letter-space compound
  split at the space across a line boundary during reflow/clustering (its parts are
  layout pseudo-words); before choosing the emission shape, check how MushafDatabase
  segments بَعْدَ مَا. Only this instance straddles a break — p27/p177 sit within
  their lines and are clean.
- **Multi-family mark hoarders: only 4 in the mushaf** — p254 أَهْوَآءَهُم (his "3
  fathas, no dot" note), p223 افْتَرَاهُ, p239 إِنَّهُۥ, p341 ٱجْتَمَعُوا۟ (same line
  as the confirmed p341 small-waw steal → p341 is a line cluster too).
- **rtl-order flags are collateral**, not defects: all three no-issue rtl verdicts sit
  beside a stray-holder; the audit-level rtl flag count for the whole mushaf is 1
  (p254). Fix the strays and rtl clears itself.

## The ownership rule (Abdullah, 2026-08-26) — contract for the line-set solver

One rule resolves every mix-up family instead of a pass per shape:
1. POSITION OWNS: a mark belongs to the word whose letter ink it is drawn over
   (measured against bands/ink, never a stage's tag).
2. THE TEXT CONSTRAINS: each word's per-family counts equal its budget (waqf
   range, iqlab single-haraka+م, pen-lift welds included).
3. NAMES FOLLOW POSITION: slash names are derived relative to the OWNER
   (renaming is part of reassignment).
4. RESOLVE GLOBALLY: on any violation of (1), re-solve the whole line-set's
   mark assignment at once, minimum total displacement subject to (2) —
   pairwise transfers are what created the rotations.
5. UNIQUENESS OR EYES: unique solution → apply; ties → the proposals page.

Test cases, in gate order: p350 line 6 (the color-rotation image), p599
البرية←شر←أولئك chain, p371 strays, p267, p535 stray pair. Implement behind
an env switch, measure like every pass; expect it to eventually subsume the
orphan/stray/xband passes but do not remove them until measured.

### Task 2: Family B — line-edge exchange: stray 280–308u + rtl-order (7 words, 5 pages)

`p350 24:3:6/24:3:9, p371 26:97:3/26:97:4, p418 33:3:4, p535 56:33:3, p599 98:6:14` (+ p599's HIGH cluster `98:6:15..98:7:3` the reviewer flagged by eye). The last word of a line and the first of the next are neighbours in reading order; marks are crossing that boundary. `QSVG_STRAY` was built for exactly this and fixed 17 — these survive it or regressed (p350 24:3:9 is marked *fixed* in `reported.json` but measures broken now).

**Files:** Modify: `tools/assign_words.py` (the stray pass `:6435`, orphan pass `:6160`). Test: bench + `cmp_pages 350 371 418 535 599`.

- [ ] **Step 1 (diagnose):** For each of the 5 pages, `QSVG_TRACE` the stray mark's x; determine which pass gives it to the line-end word and why `QSVG_STRAY` declines it (its guard requires the mark to land over a word *on its own line* — check what `line` the mark's element carries; the crossband audit's lesson is that the tag is wrong exactly at line edges, so the guard may be testing the tag instead of position).
- [ ] **Step 2 (check the regression first):** `git log`/`git diff` any recent change to the stray/orphan passes; p350 was fixed once — find what un-fixed it before writing anything new.
- [ ] **Step 3 (fix):** Repair the guard in the existing pass (position, not tag). Do NOT widen it: the fatha/kasra slash families stay excluded from cross-word moves — where the stray mark IS a slash (p350, p418, p535 are fathas), route the repair through the rtl/exchange evidence: both words sit on the same line in reading order, so the move is line-internal, not cross-line.
- [ ] **Step 4 (gate):** bench; `cmp_pages 350 371 418 535 599`.
- [ ] **Step 5:** Rescan those pages with `score_confidence.py`; expect all 7 stray/rtl proofs gone AND the p599 HIGH cluster (98:6:15, 98:6:16, 98:7:1, 98:7:2, 98:7:3) to fall out of HIGH — they are the same exchange seen from the other side.
- [ ] **Step 6:** Bench case for p350 24:3:9 (fatha count = text budget). `reported.json`: update the p350 entry from "fixed" to re-fixed with cause. Commit.

---

### Task 3: Family C — mark drawn in another line's band, 16–41u (23 marks)

Sub-groups: pause signs 37–41u (`p63, p64, p436`), meem-iqlab 17–26u (`p129, p231, p415`), line-end fathas 17–36u (`p71, p234, p267, p446, p507×3, p576×2, p577`), singletons (hamza `p222, p260`; small-waw `p341`; maddah `p439`; kasra `p567, p599`; damma `p507`).

**Files:** Modify: `tools/assign_words.py` (mark re-lining `:2176`, orphan pass `:6160`). Test: bench + targeted pages.

- [ ] **Step 1 (diagnose, one sub-group at a time):** These are probably Family B's mechanism at smaller distances — the mark belongs to a word on the adjacent line directly above/below. For each sub-group pick one exemplar, `QSVG_TRACE` it, and answer: which word SHOULD hold it (text budget of the words above/below), and which pass attached it here.
- [ ] **Step 2 (fix):** Extend the orphan/crossband repair to act on the 10–15u+ proof band with the two-signals rule: the vertical distance is the proof, the receiving word's budget must confirm. Threshold inside the empty band (≥ 15u), per the crossband histogram (4,203 ≤ 10u, 26 in 10–15u). p341 `مِنْهُ ۚ` is one of the four reference-confirmed line errors — expect it to need the word itself re-lined, not the mark.
- [ ] **Step 3 (gate):** bench; `cmp_pages 63 64 71 129 222 231 234 260 267 341 415 436 439 446 507 567 576 577 599`.
- [ ] **Step 4:** Rescan with `score_confidence.py`: all 23 band proofs gone, no new ones.
- [ ] **Step 5:** Bench case for one pause (p63) and one fatha (p576). `reported.json`. Commit.

---

### Task 4: Family D — bodyless words (3)

`p59 مَا 3:75:19, p549 بِكُمْ 60:4:22, p577 كَلَّا ۖ 74:53:1`.

- [ ] **Step 1 (diagnose):** For each: read the emitted SVG around the word — who holds its letters? `audit_bodyless.py` sees these; `audit_intervals` should say whose exclusive core the ink sits in. Remember body-less words never enter `wrec` — work from `assignment`.
- [ ] **Step 2 (fix):** These are word-boundary errors (the neighbour swallowed the word). Fix via the segment-budget mechanism (`:5108`): neighbour has a piece surplus exactly matching this word's deficit. If the cut is genuinely ambiguous, a geometry-keyed override from the review platform is the correct fix — record it there, not in code.
- [ ] **Step 3 (gate):** bench; `cmp_pages 59 549 577`; rescan; bench case for p59; `reported.json`. Commit.

---

### Task 5: Family E — sajdah word `يَسْجُدُونَ ۩` p589 (1)

- [ ] **Step 1:** The ۩ sign is standalone (`:5740` treats hizb/rub/division stars as no word's ink) — check whether the sajdah overline/sign here is counted as a word piece instead. Abdullah's `shape_notes.json` already says the sajdah line should group with the word below — read that note first.
- [ ] **Step 2 (fix):** Route the sajdah sign like the other standalone signs (or attach as non-counting decoration per the note); the word's piece count returns to 3.
- [ ] **Step 3 (gate):** bench; `cmp_pages 589`; rescan; `reported.json`. Commit.

---

### Task 6: Full re-gate and close-out

- [ ] **Step 1:** `QSVG_OUT=$QSVG_SWEEPS/certfix-after python3 scratchpad/full_sweep.py 1 604`; `python3 scratchpad/cmp_full.py $QSVG_SWEEPS/certfix-after` vs the pinned baseline — total falls, no page worse than +1.
- [ ] **Step 2:** `rm -rf .cache/confidence/raw && python3 tools/score_confidence.py 1 604 --jobs 8 --html` — expect CERTAIN ≈ 0 (any survivor is either a genuine artwork fact to record as data, or a mis-calibrated proof to fix in the scorer — decide which, in writing, per word).
- [ ] **Step 3:** Update `CLAUDE.md` "Where the work stands" numbers; append the full campaign summary to `reported.json`.
- [ ] **Step 4:** Ask Abdullah to spot-check the confidence page (`http://127.0.0.1:8777/confidence`) — the visual confirm loop — and fold his confirmed list back in.
