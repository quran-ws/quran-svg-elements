# Mark taxonomy — the mushaf's full sign inventory vs what the pipeline calls things

Source: `~/Downloads/mushaf-signs_1.json` / `.html` — the sign catalog built from the
official mushaf's own appendix (KFGQPC Madinah, Uthman Taha, Hafs). This is an
INVENTORY AND PROPOSAL only. Nothing in the pipeline, labels, or caches was changed.
Machine table: `docs/defects/mark_taxonomy.json`.

---

## QUESTIONS FOR ABDULLAH

1. **The small noon at 21:88 (نُـۨجِى, p329) is not emitted.** The tag `small-noon`
   exists in `TEXT_WANT` and `_MARKFAM`, but the built page emits only
   `['damma', 'dot', 'dot', 'kasra']` for that word — no `small-noon`. Two `dot`s
   where the word's letters need one suggests the small noon's ink was tagged `dot`
   or merged into the noon body. This is the ONLY occurrence in the whole mushaf.
   Please eye it on p329 in the review server: is the small ۨ drawn as separate ink,
   and what tag does it carry now?

2. **p159 `بَصْۜطَةࣰۖ` carries TWO catalog signs (the seen ۜ "read with seen" AND the
   waqf ۖ) but only ONE `pause` is emitted** — the mark list is
   `[pause, sukun, fatha, fatha, shadda, two-dots, dot, fathatan]`, and the word has
   no shadda in its text. Suspicion: the seen was labelled `shadda` and the `pause`
   is the waqf. Needs your eye before the seen gets its own name.

3. **Split `small-circle` into the two zeros?** The catalog distinguishes the round
   zero ۟ (U+06DF, never pronounced, 3,988×) from the upright rectangular zero ۠
   (U+06E0, silent in wasl only, 66×, almost all on أَنَا۠). Both are `small-circle`
   today. The outlines are genuinely different (circle vs upright oval), but I could
   not confirm whether one label SIGNATURE in `labels.json` covers both shapes. If
   one signature covers both, the split needs position/aspect or your eye, not just
   a rename. Do you want the split?

4. **One outline, two functions — name by function or by shape?** U+06DC is a small
   seen serving two unrelated jobs: saktah (5 places) and "read with seen instead of
   sad" (2 places). The catalog itself warns about this. The ink cannot decide; only
   the site can. Options: (a) one shape tag `small-seen` plus `data-function="saktah|
   seen-reading"`, or (b) function names directly in `data-mark` (`saktah`,
   `seen-above`), driven by a 7-row site table. I propose (b) — it matches how waqf
   is already typed by place — but it bakes function into the mark name. Your call.

5. **Encode the tanwin arrangement?** The catalog's biggest structural point: a
   tanwin's stacked vs staggered ARRANGEMENT encodes the tajwid ruling (izhar vs
   idgham/ikhfa), and Unicode does not carry it (U+064B/C/D cover both). Our two
   strokes per tanwin are already separate elements; a `data-form="stacked|staggered"`
   on the pair (derivable from the two strokes' relative offset) would capture what
   the print actually says. This ripples into nothing that exists today (no audit
   reads it) but is new surface. Worth doing?

6. **Muanaqah pairing.** The two ۛ signs of one embracing pause span two words
   (sometimes far apart). Today each carries `data-waqf="waqf taanuq"` separately.
   Should the pair be cross-referenced (e.g. `data-pair="p2-a"` on both) so a reader
   can find the partner?

7. **Sajdah structure.** Today one tag `sajdah` covers 2-3 contours per site
   (overline + mihrab ۩ pieces, undifferentiated). The catalog stresses these are two
   different anchors, on DIFFERENT verses in 4 of 15 places (16:49/50, 17:107/109,
   27:25/26, 41:37/38). Propose `sajdah-line` (the overline, owned by the word it
   covers) and `sajdah-sign` (the ۩ glyph). Also connects to your shape note that the
   sajdah line should group with the word below it. OK to split?

8. **Waqf sign naming.** Current `data-waqf` values use the Egyptian sign names
   (`waqf qila`, `waqf sali`) for signs this print does not draw as قلى/صلى — it
   draws ۗ and ۖ. Propose moving to the catalog's own terms: `waqf-lazim`,
   `waqf-awla`, `waqf-jaiz`, `wasl-awla`, `muanaqah`. Rename only, mapping is 1:1.

9. **Page furniture in scope?** Sura banners, basmalah lines, borders, running
   headers, margin hizb/sajdah medallions carry no tags today (only
   `ayah-marker-ornament` / `ayah-number` exist as `data-kind`). Is tagging them a
   goal, or out of scope for word decomposition?

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
