# Line-set solver (`QSVG_LSOLVE`) — trial report, 2026-08-27

The ownership rule implemented as a global re-solve, per the contract in
`docs/superpowers/plans/2026-08-26-certain-defect-fixes.md`. **Default OFF**;
enable with `QSVG_LSOLVE=1`. Lives at the very end of `assign_page` in
`tools/assign_words.py`, after the overrides and every other pass, immediately
before `rewrite()`.

## Design

1. **POSITION OWNS.** A violation is a slash/dammah-family mark with zero
   x-overlap with its owner's body ink (0.6u tolerance, the orphan pass's
   measured constant) or drawn ≥15u outside its owner's line band (the
   crossband empty band). Bands are measured from body ink, never the `line`
   tag.
2. **THE TEXT CONSTRAINS.** Per-word, per-family |held − want| over
   fathah/kasrah/tanwin_al_fath/tanwin_al_kasr/dammah/tanwin_al_damm, counted after naming.
   **Hard receiver-room**: an arriving mark may fill a deficit, never create a
   surplus (+50 penalty = reject). Without it, p535 line 1 parked a tanwin_al_kasr
   on يُنزِفُونَ, which spells no tanwin, because the global ledger still
   improved.
3. **NAMES FOLLOW POSITION.** A touched word's slash names are re-derived
   from the side of the letters under each stroke (`_POS_SWAP`, the orphan
   pass's `_rename` precedent). Two single strokes within 8u, at least one
   newly arrived, weld into one tanwin named by the pair's side — **only if
   the word's text still owes that tanwin** (two signals). The iqlab
   convention is applied TEXT-driven: a word whose text carries ۢ/ۭ that is
   short its tanwin and long its same-side base has its leftmost base stroke
   renamed to the tanwin (reported.json items 18/23; never geometric, per
   the marktype refutation).
4. **RESOLVE GLOBALLY.** Triggered lines expand to the line-set (±1 line's
   words). Entities = violating marks, plus same-set marks of contested words
   that overlap another word within 3u (the p350 fathah-at-x50.7 kind — never
   itself orphaned, but the rotation cannot close without it). Candidates per
   mark: current owner + up to 2 words whose ink is under the mark (≥−3u), on
   the drawn band's line ±1, ranked by geometric cost (x-gap + band-out) —
   ranking by raw x-overlap was wrong, vertically adjacent words always
   overlap in x. Entities factor into connected components over shared
   candidate words; each component is solved exactly (deterministic exhaustive
   product, ceiling 20 000 combos / 12 entities, else a "too large" record).
   Objective: minimise V = positional violations + count violations (+hard
   penalties), then total displacement.
5. **UNIQUENESS OR EYES.** Apply only if the optimum is strictly better than
   the current assignment (V falls). If the second-best distinct solution has
   equal V and cost within 10%, it is a tie: nothing moves, a proposal record
   is written. A component that keeps its violations (a chain the budgets
   cannot close) is also recorded for eyes. Moves go through
   `put_in_ligature()` only, with line retag to the receiver's band and
   mkmembers carried.

**Human decisions are inputs.** Elements geometry-keyed in
`.cache/review/overrides.json` never move. Elements already on the proposals
page (`docs/defects/proposals.json`, e.g. p350's x14.9 stroke, P1) are under
adjudication: they neither move **nor testify in any budget** — a disputed
identity cannot be counted.

**Scope.** Slash + dammah families only. small_waw/small_yaa are never
entities (a trailing ۥ/ۦ legitimately sits x-clear of its word — direction
beats distance). Standalone signs, mkparts, and composite members are
skipped; masters carry their members.

Knobs: `QSVG_LSOLVE=1` (on), `QSVG_LSDBG=1` (every group/decision to
stderr), `QSVG_LSOLVE_OUT=<file>` (JSONL of applied/kept/tie records — the
proposals file was built from it).

## Gate cases

| case | expectation | result |
|---|---|---|
| 1. p350 lines 6–7 | لَا 24:3:9's true fathah (x327.9, over its own body) returns from يَنكِحُهَآ; the مشركة/والزانية tail re-owned; x14.9 (P1) untouched | **PASS.** fathah 327.9→لَا applied. Tail rotation applied: kasrah 47.5→وَٱلزَّانِيَةُ (renamed fathah, its وَ), fathah 62.4→مُشْرِكَةًۭ (its كَ), kasrah 66.9→مُشْرِكَةًۭ (its رِ), tanwin_al_fath 101.6→زَانِيَةً (welded with its sitting pair-stroke at 98.4, counts as one ةً), مشركة's x50.7 stroke stays and is promoted to its iqlab tanwin_al_fath (text ًۭ). x14.9 left exactly where it stands; excluded from ledgers as P1-pending. Bonus: fathah 304.9→يَرْمُونَ closes the pre-existing يرمون 1/2 flag (matches the interval audit's MARK-STEAL evidence). No rtl-order flags. |
| 2. p599 98:6 chain | أولئك's fathah back from شر, شر's back from البرية | **PASS.** fathah 187.4 (البرية)→شَرُّ, fathah 221.2 (شر)→أُو۟لَـٰٓئِكَ; أولئك 2/2, شر 1/1. The audit flag moves to the chain's end (البرية 1/2 — its second fathah is genuinely absent from the ledger; deficit, non-silent). NEIGHBOUR-BAD 2→0. A second 3-cycle on lines 1–2 also resolved (الذين→ءامنوا→نار→الذين) — flagged below for Abdullah. |
| 3a. p371 26:97 strays | the two kasrahs held by لَفِى resolved | **PASS, page fully clean** (2 flags → 0; intervals 2 → 0). kasrah 305.6→ضَلَـٰلٍۢ, welded with ضلال's own mis-named stroke at 300.5 into its ٍۢ tanwin_al_kasr; kasrah 324.0→ضلال renamed fathah (its لَ). لفى 1/1. |
| 3b. p267 | 16:2:10/11 stray | **Correctly refused, proposal emitted.** أَنْ cannot take its fathah back while it holds the y427 line-12 stroke, and no line-12 word has room for that stroke (السماوات family-full) — the same chain the xband pass refused. V unchanged → kept, recorded for eyes. No change to the page. |
| 3c. p535 56:33 stray pair | وَلَا's two stray fathahs resolved | **PASS.** The pair (x8.3/x11.3, drawn at line 7's end, 3u apart) moves to مَقْطُوعَةٍۢ and welds into its ٍۢ tanwin_al_kasr (y246–252, where every tanwin_al_kasr on that line sits). ولا 4/2 fixed. The suspicious sitting element at (20,233) is re-derived by position to tanwin_al_fath → the flag moves onto it (tanwin_al_fath 1/0) — Abdullah's "(20,233) is suspicious" note made visible. Page 4 flags → 4, intervals 5 → 3. |
| 4. Controls | p1, p3, p133, p307 + 10 random clean pages bit-identical ON vs OFF | **PASS.** All 14 SVGs byte-identical (md5): p1 p3 p133 p307 p16 p66 p71 p89 p147 p165 p183 p452 p522 p524 (clean pages seeded random.seed(42) over the 421 vlabels-clean pages). Determinism: two ON runs of p350 byte-identical. |

## Measurements

- **bench**: OFF — SCORE 79, FAILURES none, pixelfail 0. ON — SCORE 79,
  FAILURES none, pixelfail 0. (Identical; the pass renames/regroups and moves
  marks between same-fill words, so pixels cannot change.)
- **audit_marks + audit_intervals**, ON vs OFF (current pipeline; vlabels
  agrees with OFF on the gate pages), 5 gate + 33 known-defect pages:

| page | marks off→on | intervals off→on | combined |
|---|---|---|---|
| 350 | 2 → 5 | 7 → 2 | 9 → **7** |
| 371 | 2 → 0 | 2 → 0 | 4 → **0** |
| 267 | 0 → 0 | 1 → 1 | 1 → 1 |
| 535 | 4 → 4 | 5 → 3 | 9 → **7** |
| 599 | 1 → 1 | 6 → 1 | 7 → **2** |
| 446 | 1 → 1 | 1 → 0 | 2 → **1** |
| 526 | 1 → 1 | 3 → 2 | 4 → **3** |
| 543 | 3 → 3 | 1 → 0 | 4 → **3** |
| 576 | 1 → 1 | 4 → 3 | 5 → **4** |
| other 29 sample pages | unchanged | unchanged | unchanged |
| **total (38 pages)** | 37 → 38 | 40 → 23 | **77 → 61** |

  Every touched page falls on the combined count; no page worsens on it.
- **p350 marks +3 — the visibility proof** (the one per-audit worsening,
  gate-permitted with element dumps):
  - `لَا 2/1`: holds its returned true fathah (x327.9–334.8, y226.5–230.1,
    squarely over its body 321.8–333.1 — Abdullah's confirmed verdict) plus
    the P1-pending x14.9 stroke, which the solver may not touch and the audit
    still counts. Resolves to 1/1 the moment P1 is decided.
  - `يَنكِحُهَآ 1/2` and `ٱلْمُحْصَنَـٰتِ 1/2`: donors of returned strays;
    each is now short the fathah its spelling owes because that ink is
    genuinely absent from its ledger (welded or missing) — a pre-existing
    silent defect made visible as a non-silent deficit (precedent:
    reported.json item 25).
  - `وَٱلزَّانِيَةُ 2/3`: its third fathah is either the P1 stroke or ink not
    in the ledger — P1's own open question, now visible.
- **Proposals**: 31 kept-component records over the 38 pages, none moved —
  24 unresolved chains for eyes, 7 classified trailing-tanwin-after-hamzah
  (the شَىْءٍۢ drawing, probably legitimate; the trigger fires on the gap the
  ء leaves). 0 ties within the 10% margin were hit on these pages. File:
  `docs/defects/lsolve_proposals.json` (applied records included for
  reference).
- **Cost**: ~0.16s extra on p350 (busiest gate page), ~3% of the page build.

## For Abdullah — three things to eye-check

1. **p599 lines 1–2 rotation** (applied): الذين's stray → ءَامَنُوا۟'s وَ;
   the stroke at x42–49/y38–41 → نَارِ as its رِ kasrah; نار's held kasrah at
   x65.5–71.8/y37–40 → ٱلَّذِينَ **renamed fathah** at y38.8, above الذين's
   letters. The first two look right; the third is the ledger-optimal close
   of the cycle but the stroke sits high — is it الذين's لَّ fathah, or فِى's
   kasrah (فى is budget-blocked by the x75.8 stray it still holds — that
   residual chain is in the proposals)?
2. **p535 مَقْطُوعَةٍۢ tanwin_al_fath 1/0**: the (20,233) element your note called
   suspicious now carries the flag directly. If it is not a mark at all, it
   is a P1-type proposals-page candidate.
3. **p350 tanwin_al_fath residue**: مشركة's iqlab ًۭ is now its x50.7 stroke
   (promoted), and the x98.8 stroke welds into زانية's pair — please confirm
   against the print.

## Recommendation

Adopt for a full-mushaf trial run (the orchestrator's sweep) with
`QSVG_LSOLVE=1`: on everything measured here it strictly reduces combined
defects (−16 over 38 pages), leaves clean pages bit-identical, keeps bench at
SCORE 79 / pixelfail 0, is deterministic, and refuses every chain it cannot
prove — writing it to the proposals page instead. The one caveat to carry
into the sweep gate: it deliberately converts silent mis-ownership into
non-silent deficits (flags can MOVE to the chain's end word, and p350-style
pages can rise on audit_marks alone while falling combined), so the sweep
comparison should be read on marks+intervals combined, with element dumps for
any page that rises. Do not remove the orphan/stray/xband passes yet — this
pass runs after them and was measured with them on.
