# Mark taxonomy — the mushaf's full sign inventory vs what the pipeline calls things

Source: `~/Downloads/mushaf-signs_1.json` / `.html` — the sign catalog built from the
official mushaf's own appendix (KFGQPC Madinah, Uthman Taha, Hafs). This is an
INVENTORY AND PROPOSAL only. Nothing in the pipeline, labels, or caches was changed.
Machine table: `docs/defects/mark_taxonomy.json`.

---

## DECISIONS (Abdullah, 2026-08-27 22:25, via walkthrough)

All nine questions answered. In simple words:

1. p329 small noon: FIX the label (verify by render).
2. p159 seen-on-sad tagged shadda: FIX the label (measure first).
3. Two zeros: SPLIT -> `sifr-mustadir` (round) / `sifr-mustatil` (upright).
4. Small seen: name BY JOB -> `saktah` / `seen-reading`, from a 7-row place table.
5. Tanween arrangement: YES -> `data-form="stacked|staggered"` on the pair.
6. Muanaqah: YES -> same `data-pair` id on both signs.
7. Sajdah: SPLIT -> `sajdah-line` (groups with the word it covers) / `sajdah-sign`.
8. Waqf types: RENAME to `waqf-lazim`, `waqf-awla`, `waqf-jaiz`, `wasl-awla`,
   `muanaqah`.
9. Furniture: tag margin hizb/sajdah MEDALLIONS now; borders/headers later.

Rollout: TWO PHASES. Phase 1 = pure naming (1,2,3,4,7,8,9). Phase 2 = new
attributes (5,6) after phase 1 gates clean.

---

## 1. What the catalog says the mushaf contains

Six waqf signs (one, ۙ "la", NOT used in this print — but it DOES appear 68 times in
quran.com's uthmani text, one more face of the known 203-site waqf disagreement; the
pipeline already takes waqf from KFGQPC, which is why this has not bitten).

Dabt marks: two zeros, sukun, two idgham conventions (encoded by ABSENCE of marks —
no ink, nothing for us to tag), the iqlab meem in high and low form, the miniature
letters (dagger alif, small waw, small ya, small noon), hamzat al-wasl, madd.

Structural: ayah medallion, juz/hizb divider, sajdah (overline + mihrab), saktah.

Single-place marks — the rare ones, each verified below against our built SVGs:

| sign | word | ref | page | what we emit today |
|---|---|---|---|---|
| Imalah dot (below) U+06EA | مَجْر۪ىٰهَا | 11:41 | 226 | `pause` |
| Ishmam dot (above) U+06EB | تَأْمَ۬نَّا | 12:11 | 236 | `pause` |
| Tashil dot U+06EC | ءَا۬عْجَمِىٌّ | 41:44 | 481 | `pause` |
| Seen above sad U+06DC | وَيَبْصُۜطُ | 2:245 | 39 | `pause` |
| Seen above sad U+06DC | بَصْۜطَةً | 7:69 | 159 | see Q2 — maybe `shadda` |
| Seen below sad U+06E3 | ٱلْمُصَۣيْطِرُونَ | 52:37 | 525 | `pause` |
| Bare sad (no sign) | بِمُصَيْطِرٍ | 88:22 | 592 | nothing — correct, absence is the sign |
| Small high noon U+06E8 | نُـۨجِى | 21:88 | 329 | NOT EMITTED — see Q1 |
| Saktah ×5 U+06DC | 18:1, 36:52, 75:27, 83:14, 69:28 | | 293, 443, 578, 588, 567 | `pause` (verified p293, p567, p578, p588) |

All of these DO exist as drawable ink and are owned by the right word — the problem
is purely the name. Every one of them says `pause`, because `TEXT_WANT["pause"]`
lists `۬ ۪ ۫ ۣ ۜ` beside the five waqf signs. One bucket holds five different
tajwid phenomena plus all waqf.

## 2. What the pipeline already covers well

- All six harakat + shadda + sukun + maddah, the dot family, hamza, `wasla`
  (hamzat al-wasl, 13,482×), `small-alef` (9,725×), `small-waw` (1,257×),
  `small-ya` (995 + 38 of the ۧ variant), `meem-iqlab`, `hizb`, `sajdah`.
- Waqf signs are already TYPED by ink signature + place
  (`.cache/marks/waqf_types.json`, `waqf_places.json` → `data-waqf`), including the
  muanaqah recorded by place because its triangle of dots has no clean signature.
  Verified on p2 (2:2): both ۛ carry `data-waqf="waqf taanuq"`. The five values in
  use map 1:1 onto the catalog's five signs.
- Composite outlines keep the `+` convention (`fatha+hamza` …) — matches the
  catalog's reality of fused ink; no change proposed.
- Ayah medallions live at a different layer (`data-kind="ayah-marker-ornament"` /
  `"ayah-number"`) — correct, they are structure, not diacritics.
- The idgham conventions and the "deliberately bare alif" need no tag: the catalog
  itself defines them as the ABSENCE of marks.

## 3. The gaps, in one list

| # | problem | size |
|---|---|---|
| 1 | `pause` bucket holds waqf + saktah + imalah + ishmam + tashil + both seens | 12 rare sites misnamed; waqf fine via `data-waqf` |
| 2 | `small-noon` never emitted at its one site (p329) | 1 site, missing |
| 3 | `small-circle` = both zeros (U+06DF and U+06E0), different rules | 66 of 4,054 misnamed |
| 4 | `meem-iqlab` does not distinguish high (510) vs low (99) form | naming only; low form often fused with the kasratan in this print |
| 5 | sajdah overline vs mihrab undifferentiated; 4/15 sites span two verses | 15 sites |
| 6 | tanwin arrangement (stacked/staggered) not encoded anywhere | mushaf-wide, new information |
| 7 | p159 seen possibly labelled `shadda` | 1 site, needs eye |
| 8 | `data-waqf` value names don't match the print's sign vocabulary | rename only |

Also worth knowing: `pause` sits in `_ABOVE_ONLY`, but three of its current tenants
are BELOW-the-line marks (imalah ۪, seen-below ۣ, and the low iqlab meem context) —
the misnaming actively fights a real constraint.

## 4. Proposed naming scheme (kebab-case, catalog-aligned)

Principle: `data-mark` carries the mark's FUNCTION name; shape signatures in
`labels.json` may keep coarser families where the ink is genuinely one shape
(the seen family), with a small site table carrying the function for the 12 rare
sites — exactly the mechanism `waqf_places.json` already uses.

| old (emitted today) | new | notes |
|---|---|---|
| `pause` (waqf sites) | `waqf` + `data-waqf="waqf-lazim\|waqf-awla\|waqf-jaiz\|wasl-awla\|muanaqah"` | value rename: `waqf qila`→`waqf-awla`, `waqf sali`→`wasl-awla`, `waqf taanuq`→`muanaqah`, spaces→hyphens |
| `pause` (18:1, 36:52, 75:27, 83:14, 69:28) | `saktah` | 5 sites, by place |
| `pause` (2:245, 7:69) | `seen-above` | reading sign, not a pause |
| `pause` (52:37) | `seen-below` | |
| `pause` (11:41) | `imalah` | |
| `pause` (12:11) | `ishmam` | |
| `pause` (41:44) | `tashil` | |
| `small-circle` (U+06DF sites) | `sifr-mustadir` | or keep `small-circle`; see Q3 |
| `small-circle` (U+06E0 sites, 66) | `sifr-mustatil` | the 66 words are enumerable from the text |
| `meem-iqlab` | `meem-iqlab` + `data-pos="above\|below"` | keep the tag; position is derivable |
| `sajdah` | `sajdah-line` / `sajdah-sign` | see Q7 |
| — (not emitted) | `small-noon` | fix the p329 site first (Q1) |
| everything else | unchanged | fatha, kasra, damma, fathatan, kasratan, dammatan, sukun, shadda, maddah, hamza, wasla, small-alef, small-waw, small-ya, dot, two-dots, three-dots, hizb, `+`-composites |

Optionally, per Q5: `data-form="stacked|staggered"` on tanwin pairs.

SVG structure — no structural change proposed beyond: (a) the two sajdah sub-tags,
(b) optional `data-pair` on muanaqah partners, (c) the existing conventions
(`data-mark-part` for split outlines, `data-waqf`, `+` composites) stay as they are.

## 5. What a rename ripples into (why NOT to do it casually)

- `scratchpad/audit_marks.py` `TEXT_WANT` — the `pause` tuple must split so budgets
  still balance (a saktah site must DEMAND a saktah, not a pause).
- `.cache/marks/labels.json` — 141 signatures say `pause`; `waqf_types.json`'s
  `we_call` field; both are data migrations, `apply_labels.py`-style, backed up.
- `tools/assign_words.py` — `_ABOVE_ONLY`, `_DUAL_SIZE_CAP`, `_MARKFAM`,
  and every string equality on `"pause"` / `"small-circle"`.
- `tools/label_sheet.py` `ALL` / `COMMON` lists.
- `tools/audit_marksize.py` — family medians CHANGE when a family splits (5 saktahs
  leaving `pause` moves both tails). Re-baseline after.
- Bench expectations, `sig_flags`, queue family names, `score_confidence` priors,
  and the sweep baseline: any rename invalidates flag-name comparisons against
  `.cache/sweeps/*` — re-measure, don't diff names across the rename.

Sequencing if adopted: (1) settle the questions above; (2) build the 12-site rare
table + the U+06E0 word list as DATA in `.cache/marks/`; (3) rename in one measured
change with `label_bisect.py`-style before/after on the full sweep; (4) re-pin
family medians and the clean-page figures.

## 6. Count reconciliation notes

- Codepoint counts above come from the cached quran.com uthmani text and match the
  catalog where the catalog gives counts (wasla 13,482≈13,483; dagger alif
  9,725≈9,726; small waw 1,257=1,257; madd 5,373≈5,376; round zero 3,988=3,988;
  rect zero 66=66; sajdah 15=15; saktah+seen U+06DC 7=7).
- Do NOT read U+06E2/U+06ED counts from the uthmani TEXT as iqlab site counts: that
  corpus appends a small meem to tanwins for other rules too (e.g. هُدًۭى), giving
  ~7,250 text hits against the catalog's 510+99 printed meems. The print's iqlab
  handling is already settled (one haraka + small م, see CLAUDE.md).
- Emitted-tag tallies in this report are from the 117 pages currently in
  `.cache/words-svg/hafs-kfqc/` plus 5 pages built fresh (39, 329, 525, 578, 598);
  they are vocabulary evidence, not mushaf-wide counts.
