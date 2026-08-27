# Letter-space compounds (p254) and sajdah policy P5 — 2026-08-27

Both tasks adopted default-ON, each behind its own env switch for A/B
(`QSVG_SPACESPLIT`, `QSVG_SAJ`). All edits in `tools/assign_words.py`.

## Task 1 — p254 بَعْدَ مَا (13:37:8), reported.json item 20

### What was actually wrong

The layout input was already right: quran.com/QCF put 13:37:8 on line 6 and
جَآءَكَ opening line 7, agreeing with DigitalKhatt. The raw line-6 artwork holds
both halves — بعد at 28.4–45.2, ما at 8.8–29.1. Two pipeline stages broke it:

1. **`cluster_line` cannot see a word-space inside a word.** `segment_word`
   skips spaces, so the compound's internal gap earns no boundary reward and its
   width prior treats both chunks + gap as one contiguous run. The DP preferred
   handing بعد to أَهْوَآءَهُم (5/4 pieces).
2. **The density hill-climb ejected the word to line 7** (traced with the new
   `QSVG_LDBG`: `13:37:8 line 6 -> 7, d0=1.14 d1=0.92`) — the bad line-6
   clustering made ejection look like an improvement, and on line 7 the word
   grabbed جَآءَكَ's first piece and its fathas.

### The fix (`QSVG_SPACESPLIT`, default ON)

- `_space_halves()` detects the compound family: a space with skeleton letters
  on BOTH sides after stripping ۞/۩ (trailing-waqf spaces like `بَعْضٍۢ ۚ` have
  no letter after the space and do not match). Exactly 5 words mushaf-wide:
  بَعْدَ مَا p27/p177/p254, دَآئِرَ ةٌ p117, إِلْ يَاسِينَ p451.
- `cluster_line` partitions with the compound split into its two halves — each
  half gets its own width prior (`letters()` refuses the full compound's QCF
  advance for a half via the `half` flag) and the internal space earns the
  normal inter-word gap reward — then merges the halves' clusters back into
  one, so every caller still sees one cluster per layout word and the emitted
  group stays ONE `<g class="word">` keyed 13:37:8 (homing keeps it in line 6's
  wrapper).
- The hill-climb never moves a letter-space compound across a line boundary —
  it is the one word whose width prior cannot be trusted at a line edge.

### Measured

| | before | after |
|---|---|---|
| 13:37:8 placement | forced to line 7, spanning 8.8–333.5 | line 6, its two chunks 8.8–45.2 |
| أَهْوَآءَهُم | 5 pieces (holds بعد) | 4 pieces = its text |
| جَآءَكَ | 2/3 pieces, fatha 2/3 | all pieces + 3 fathas back |
| rtl-order flag (mushaf's only one) | 1 | 0 |
| p254 mark flags vs lsolve | 3 | 2 |
| p254 interval flags vs lsolve | 4 (BODY-STEAL ×4) | 1 |
| p27 / p117 / p177 / p451 | clean | **byte-identical** |
| controls p1 / p3 / p350 | — | **byte-identical** |
| bench | 79, no failures, pixelfail 0 | 79, no failures, pixelfail 0 |

Remaining p254 residue (pre-existing families, out of scope here):
`بَعْدَ مَا fatha 2/3` — the third fatha sits at x≈48–52 held by أَهْوَآءَهُم
under the name damma (the one interval flag left); `جَآءَكَ ligatures 4/3` — a
7.1×3.6 fatha-shaped outline at x310.8 counted as a body (letter-vs-mark
family).

## Task 2 — Sajdah policy P5

Policy: the sajdah overline + ۩ are ONE standalone sign, grouped with the
sajdah word on the line below the bar, never counted as any word's mark or
letter.

### Per-site verification (15 sites; the ۩ of 96:19 is drawn on p598)

| page | site | state found | action |
|---|---|---|---|
| 176, 251, 293, 309, 334, 341, 365, 416, 454, 528 | one each | bar+sign standalone, right ayah | none |
| 379 | 27:26 | standalone; the bar (over أَلَّا يَسْجُدُوا۟, lines 3–4) keyed 27:24 by the polygon under it | none (ayah label residue) |
| 480 | 41:38 | standalone; overline pieces keyed 41:37 (they overline 41:37's command words) | none |
| **272** | 16:50 | **overline renamed `kasra`, counted in ظِلَـٰلُهُۥ (16:48:10) — the page's only mark flag** | bar ejection now accepts a renamed hairline (h<2.5 ≤ w) and drops the name |
| **589** | 84:21 | **۩ counted as يَسْجُدُونَ's 4th body** — its outline signature (`e1cdcfa73d5a830f`) is a variant not in the shape table (table knows `8097cfaa6e9371be`, same 7.9×11.1 size) | text-driven recovery: word text carries ۩ + sign geometry (nested contours) ⇒ standalone; piece count back to 3 |
| **597** | 96:19 | **no sajdah ink on the page at all** — the print ends p597 at 96:12 (DigitalKhatt line 15 = 96:10:2..96:12:4); 96:13–19 with the sign are on p598 (item-21 layout family) | none needed — p598 already handles both bar and sign, keyed 96:19 |

### Grouping fix (`rewrite()`)

Standalone sajdah groups are now homed to the wrapper holding the sajdah
word's ink (fallback: the page's single ۩ word), so the bar and the sign come
out in the same tag in the word's line — implementing the shape_notes entry
"sajdah line — belongs with the word BELOW, and in the same tag as the
following sajdah mark". Verified: every sajdah page emits its group(s) inside
the sajdah word's line wrapper (272→11, 589→14, 176→15, 251→4, 293→6, 309→8,
334→8, 341→9, 365→7, 379→6, 416→8, 454→11, 480→15, 528→9, 598→3).

### Measured

Mark flags on the 16 pages vs lsolve: 8 → 7 (p272 −1, none worse). Interval
flags: 0 → 0. Word budgets untouched except removing the two pieces of ink
that were never the words' (the p272 fake kasra, the p589 ۩). Bench 79, no
failures, pixelfail 0; controls byte-identical with both switches off ⇔ on
except the 5 compound + 16 sajdah pages.

## Bookkeeping

- `reported.json`: item 20 status → fixed; item 27 appended (P5 verification).
- New env switches: `QSVG_SPACESPLIT` (compound split, default ON),
  `QSVG_SAJ` (sajdah recovery + homing, default ON),
  `QSVG_LDBG` (trace `_ink_refine` / hill-climb line moves).
