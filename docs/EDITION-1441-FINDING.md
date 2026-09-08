# The print is 1441H, and we had been comparing against 1421H

2026-08-31. Abdullah: *"the svg is based on king fahd complex 1441 not 1421"*,
then *"1421 vs 1441 is a drift, I think we used wrong layout to compare with"*.

Both were right, and the second is the more consequential.

---

## The two editions are different documents

QUL's own catalogue lists them separately:

| layout | id | print |
|---|---|---|
| KFGQPC V2 | 10 | 1421H |
| **Digital Khatt (KFGQPC V2 1421H print)** | **21** | **1421H** |
| **KFGQPC V4** | **19** | **1441H** |

`.cache/digitalkhatt/digital-khatt-15-lines.db` says so itself, in its own
`info` table, in a string that ships with the download and was not written here:

    Digital Khatt (QPC v2 1421H layout

So the layout source this project adopted models the **1421H** printing, while
the artwork is the **1441H** one.

## Measured against the ink

Word-level line assignment, all 77,432 words, against the emitted pages:

| layout source | agreement | pages differing |
|---|---:|---:|
| DigitalKhatt V2 (1421H) | 96.33% | 121 |
| **KFGQPC V4 (1441H)** | **100.0000%** | **0** |

The V4 comparison used `github.com/MohamadHajjRabee/quran-qcf4`, which publishes
the 1441H layout as per-page JSON with `verse_key` and `position` per word.

**118 of the 121 DK-differing pages have every word shifted by the SAME amount**
— 2,750 of 2,843 differing words, +1 on 2,757 and −1 on 85. That is a layout
offset between two printings, not scattered disagreement, and it is why the
figure never looked like ordinary noise.

### The 16 V4 words we do not hold

Fifteen are the sajdah signs — exactly the fifteen sajdah locations (7:206,
13:15, 16:50, 17:109, 19:58, 22:18, 22:77, 25:60, 27:26, 32:15, 38:24, 41:38,
53:62, 84:21, 96:19). V4 counts the sign as a word; we hold it as a mark. A
modelling difference, not a disagreement.

The sixteenth is real: **p451 `37:130:4` `يَاسِينَ`**. V4 splits `إِلْ يَاسِينَ`
into two words where we hold one — which closes the open item in `CLAUDE.md`
that read *"draws one run more than the joining rules allow"*. It was never a
defect in our decomposition; the word source was from the other printing.

## What the drift has been costing

Per-page reflow flags in the current build, cross-referenced with the pages where
DK's layout disagrees with the ink:

    pages the pipeline had to reflow             71
    of those, explained by DK's 1421 drift       50
    of those, the known quran.com disagreements  21   (122, 123, 144, 145, 532,
                                                       534, 564, 570, 575, 576,
                                                       583, 588 …)

121 of 604 pages carry DK drift, so chance alone would put ~14 of the 71 in the
overlap. There are **50**. The pipeline has been doing real work to reconcile a
1421H word source against 1441H ink, and calling the result a reflow.

## What this does NOT settle: the text

The word TEXT is a separate question and this evidence does not answer it.

- QCF4's `text` field is a **display rendering**, not the print's orthography:
  78.7% exact against our `data-rasm-imlai`, 0.04% against our skeleton fields, and
  it carries its own conventions — decomposed `ء+ا` for `آ`, `ى` where we write
  `ا`, embedded ZWJ, different word-spacing. Differences from it are not
  evidence of drift.
- Decoding QCF4's PUA codes does not help. Its glyphs are named `glyph4`,
  `glyph5` … — anonymous word-pictures. There is no text to recover.
- **DigitalKhatt DOES have a 1441 project**, `github.com/DigitalKhatt/madinafont`
  — but it is a FONT (`madina.otf`, MetaFont sources, `features.fea`,
  `parameters.json`). No text, no layout table; the demo at
  `digitalkhatt.org/hb/newmedina` shapes and justifies at runtime.

Our text is rasm_uthmani + KFGQPC waqf, measured at 99.974% against MushafDatabase's
labelling of **this** artwork. That validation was against the ink, not against
DigitalKhatt, so it survives this finding intact.

`QSVG_DKTEXT=1` does read budgets from the DK DB, which is the 1421H edition —
so the concern is legitimate. Against it: the current build has **zero
mark-budget flags across all 604 pages**. Whatever orthographic drift exists
between the printings does not reach the mark counts.

---

## What follows

1. **Move the line table from DK to V4.** Decisive evidence, and our line
   assignment is geometric anyway, so the risk is low. Expect most of the 50
   drift-driven reflows to disappear.
2. **`إِلْ يَاسِينَ` is two words.** Close the open item.
3. **Keep `madinafont` as the reference** for letterform and justification
   questions — right edition, and better than inferring from ink.
4. **Leave the text source alone** until there is an authoritative 1441H text.
   The empirical case for it is currently sound; the provenance is not.

## The lesson worth keeping

The evidence was in hand and misread. The sign catalogue Abdullah supplied on
2026-08-30 records `"printed": "1441 AH"`, and the note written on the share that
day said the catalogue came from the 1441 printing *"while the artwork here is
the 1421 H V2 print"* — treating our own figure as the reliable one and the new
source as the anomaly. It was the other way round.

`CLAUDE.md` had asserted the 1421H identity since 2026-08-26 and everything
downstream inherited it. A number repeated in a project's own documentation
stops being read as a claim and starts being read as a fact.
