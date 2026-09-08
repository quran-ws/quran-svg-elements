# Body-steal repairs — approved batch (P9, P7, P8, P6, P2)

2026-08-27. The five approved repairs from `docs/defects/proposals.json`
(`decisions` block). All implemented as DATA — geometry-keyed entries in
`.cache/review/overrides.json`, `.cache/review/kinds.json`,
`.cache/review/marks.json` — plus two small changes to how the override stage
applies an entry (below). Backups of all three data files:
`~/Documents/quran-svg-backups/bodyfix-1787778061/`.

Evidence renders are COLORIZED: every word gets its own fill, marks at 0.62
opacity (`scratchpad/color_words.py` + `scratchpad/crop_evidence.py`), so
ownership is visible even though repairs change zero pixels. Before = the build
before this session's edits; after = the current build. All in
`docs/defects/bodyfix_evidence/`.

## Gate summary

- `scratchpad/bench.py`: **SCORE 79, FAILURES none, pixelfail 0** (gate ≤79 ✓),
  run after the final code state.
- 31-page audit scan (the 5 repaired pages + 26 override-carrying pages, since
  the override-application change touches them all) vs `.cache/sweeps/vlabels`:
  **4 pages better, 26 unchanged, 1 page +1 interval** (p418, see below —
  added visibility of a baseline-flagged defect, marks unchanged).

| page | marks (base→now) | intervals (base→now) |
|---|---|---|
| p59 | 1 → **0** | 0 → 0 |
| p341 | 5 → **1** | 0 → 0 |
| p437 | 2 → **1** | 2 → **0** |
| p535 | 5 → **4** | 10 → **5** |
| p596 | 0 → 0 | 0 → 0 |
| p418 | 3 → 3 | 5 → 6 (visibility, see below) |

The five pages' cached SVGs (`.cache/words-svg/hafs-kfqc/NNN.svg`) are
regenerated from the final build, so the review platform serves the result.

---

## P9 — p341, the لَهُۥ chain (PRE-APPROVED; "show the result after")

**Re-verified before acting** (`find_word.py`): exactly as diagnosed.
ٱجْتَمَعُوا۟ (22:73:17) held لَهُۥ's whole body (13.9–23.8), its ۖ waqf, its
dammah AND its fathah; لَهُۥ (22:73:18) held only وَإِن's و (321.4–331.4) plus
وَإِن's fathah; مِنْهُ (22:73:25) held لَهُۥ's small_waw ۥ (6.7–12.2, drawn in
line 2's band at the page's far left).

**Done:** 7 overrides on p341 — body/waqf/dammah/fathah → 22:73:18; و body +
fathah → 22:73:19; small_waw → 22:73:18. Each piece one step back, exactly the
approved chain (the fathah over ل had to travel with the body or both words'
slash budgets stay broken; measured below).

**Result:** page flags 5 → 1; the survivor (22:76:4 hamzah 0/1) is unrelated and
pre-existing. لَهُۥ now holds body+fathah+dammah+waqf+small_waw — its complete
spelling — and all its ink sits on line 2, which also resolves the p341 entry
of `reference_confirmed.json` (لَهُۥ pulled to line 3). Intervals 0.

**Evidence:** `p341_line2-3_before.png` (لَهُۥ drawn in ٱجْتَمَعُوا۟'s color at
line 2's end; وَإِن's و in لَهُۥ's color at line 3's start) vs
`p341_line2-3_after.png` (لَهُۥ its own color, وَإِن whole).

## P7 — p59, bodyless مَا (3:75:19)

**Re-verified:** يُؤَدِّهِۦٓ (3:75:8) held 4 bodies; the 4th (299.9–311.7 ×
339.5–355.6) sits in line 10's band exactly at مَا's slot; مَا held only a
fathah. Diagnosis unchanged.

**Done:** 1 override (the body → 3:75:19). `QSVG_TRACE` located the original
theft: the cross-line repair at `assign_words.py:5276` moved it AND retagged
its line to 9, which is why the returned word first registered on line 9 and
tripped rtl-order — hence the band-retag added to the override stage (below).
Plus 1 `marks.json` entry: the stroke 310.3–316.0 × 320.6–323.7 drawn BELOW
the دّ renamed fathah→kasrah (text gives دِّ a kasrah; the stolen body had dragged
the word's baseline down and the positional namer read it as a fathah).

**Result:** p59 fully clean — 1 flagged word → **0**. Emitted SVG verified:
مَا = 1 body + 1 fathah; يُؤَدِّهِۦٓ = 3 bodies (its allowed count).

**Evidence:** `p059_ma_before.png` (مَا drawn in يُؤَدِّهِۦٓ's red) vs
`p059_ma_after.png`.

## P8 — p535, بَارِدٍۢ swallowed لَّا (56:44:1)

**Re-verified with a twist:** بارد held لا's body (319.5–331.5, the lam-alef at
line 12's start) + its shaddah + its fathah, as approved — and لا meanwhile held
two pieces of يَحْمُومٍۢ from line 11's end: its final م (23.3–34.3) and the
second stroke of its tanwin_al_kasr pair (28.5–33.4; idgham tanwin is drawn as a
stroke PAIR in this print, reported.json item 23).

**Done:** 5 overrides — body+shaddah+fathah → 56:44:1; the م and the twin stroke
→ 56:43:3. Plus 2 `marks.json` entries naming both unpaired idgham twins
`tanwin_al_kasr` (28.5… in يحموم, 286.8–291.1 in بارد) — truthful family names; the
pair-welding itself is the known open tanwin-al-kasr-pairing family
(shape_notes), not part of this batch.

**Result:** flags 5 → 4, intervals 10 → **5**. لَّا is complete and clean;
بارد holds exactly its 3 pieces, and its real ب fathah (307.8–316.2, previously
misnamed kasrah) renamed itself once the foreign fathah left. The two remaining
tanwin_al_kasr 2/1 flags (يحموم, بارد) are the unpaired twins counting as two — same
defect family, now correctly named and owned, queued for the pairing fix.

**Evidence:** `p535_la-barid_before.png` (لا in بارد's color; يحموم's م in
لا's) vs `p535_la-barid_after.png`.

## P6 — p596, فَأَنذَرْتُكُمْ / نَارًۭا — ALREADY FIXED

**Re-verified with dk_lines active (the brief's instruction):** the case no
longer exists. فأنذرتكم holds 4 bodies = its 4 joining-rule pieces, spanning
78.1–130.9 (فأ، نذ، ر، تكم all its own); نارا holds نا + را-welded + its ۭ
iqlab meem and tanwin_al_fath pair. Mark audit 0 flags, intervals 0 (baseline
`vlabels` agrees). The zoomed colorized render shows no cross-word ink. The
residual `audit_width` ratios on this page (2.67x/0.49x) are the known juz-30
expected-width key-shift — quran.com's wrong page boundary feeding the width
table — i.e. the line-partition work already planned, not a body defect.
**No action taken; recorded as fixed by the dk_lines adoption (item 21).**

**Evidence:** `p596_line2_before.png` / `p596_line2_after.png` (identical
ownership, both correct).

## P2 — p437, the two م-shaped glyphs at جُدَدٌۢ / بِيضٌۭ

**Re-verified:** still as decided. جدد held the piece 304.1–309.5 as its
small_meem MARK (it is the second د) and had 1 body for 2 allowed pieces; بيض
held the true iqlab م (301.4–304.7, w3.3) as a surplus BODY (ligatures 2/1
flag + two BODY-STEAL intervals).

**Done, exactly Abdullah's resolution:** 1 override (301.4… → 35:27:16) + 1
`kinds.json` entry (304.1… → body). No mark table entry needed: with the
surplus piece present and the false meem demoted, the existing late
`QSVG_IQLATE` self-rescue names 301.4–304.7 `small_meem` from the word's own
tanwin anchor — the two-signals rule doing the naming rather than a forced
label.

**Result:** جدد = جد + د bodies + small_meem mark + dammah/fathah/tanwin_al_damm/dot;
بيض = 1 body (its allowed count). Page: 2 mark flags + 2 intervals →
1 mark flag (35:29:14, unrelated pre-existing) + **0 intervals**.

**Evidence:** `p437_judad_before.png` (د drawn as a translucent mark; the م in
بيض's color) vs `p437_judad_after.png` (both د solid in جدد's color, the م a
translucent mark of جدد).

---

## Code changes (override stage only, both env-gated, default ON)

`tools/assign_words.py`, in the reviewer-overrides block:

1. **`QSVG_OVRLIG` (default 1):** an overridden piece now lands via
   `put_in_ligature()` (nearest group by ink) instead of `_dat[0]` — the rule
   CLAUDE.md already mandates for every mover; a returned letter/mark lands in
   the ligature it is drawn in.
2. **`QSVG_OVRLN` (default 1):** a returned BODY whose line tag was rewritten
   by an earlier mover (the cross-line repair does `e5["line"] = dst5["ln"]`)
   is re-tagged to the band its centre is drawn in — bodies only ("geometry is
   the truth for bodies"); marks keep their letter's line, since retagging
   marks by band manufactured a p418 flag in the A/B.

### p418, the one +1 (intervals 5 → 6, marks unchanged 3 → 3)

A/B isolates it to `QSVG_OVRLIG`. It is added VISIBILITY, not a new defect:
وَكَفَىٰ (33:3:4) holds fathah 5/3 in the baseline too, and its two surplus
fathahs are drawn at line 5's far left over ٱللَّهِ (8.0–13.6 and 14.4–22.2,
y≈156–180). Baseline registered one of them against جَوْفِهِۦ on line 6 (the
wrong line); now both register against الله on the line they are drawn in.
Ownership and counts identical to baseline — same precedent as the iqlab
naming-visibility interval rise in CLAUDE.md. The word is the p418 33:3
tangle already carrying 13 overrides, and the surplus itself is line-set
solver material (P1 family).
