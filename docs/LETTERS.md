# Letter-level decomposition

Every word of the emitted mushaf becomes a sequence of `<g class="letter">` groups, one
per letter of its text, each holding the letter's body ink and its own marks. The
output is `.cache/letters-svg/hafs-kfqc/NNN.svg`, a post-pass over the word build in
`.cache/words-svg/hafs-kfqc/`. Pixel identity holds up to the chord seams (below).

Spec: `docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md`.
Plan: `docs/superpowers/plans/2026-09-05-letter-level-decomposition.md`.

## Run

```bash
python3 tools/fetch_tajweed_fonts.py                 # once: 604 QUL V4 tajweed page fonts, ~160 MB
python3 tools/build_letter_cuts.py 1 604 --jobs 32    # → .cache/letters/cuts/NNN.json   (~3 min)
python3 tools/emit_letters.py 1 604 --jobs 32         # → .cache/letters-svg/hafs-kfqc/  (~1 min)
python3 tools/audit_letters.py 1 604 --jobs 32        # the gate: PROOF FAILURES must be 0
python3 tools/audit_letters.py 1 604 --calib          # DK cuts vs hand cuts, per joint pair
python3 tools/build_letters_page.py                   # docs/defects/letters_review.html
python3 -m unittest tools.tests.test_letters -v       # unit tests
```

Needs `uharfbuzz` and `skia-pathops` (`pip install --user --break-system-packages
uharfbuzz skia-pathops`), `rsvg-convert`, and the word build present for the pages.

## Output

```xml
<g class="word" data-wid="3:3:5" data-uthmani="مُصَدِّقࣰا" …>
  <g class="letter" data-text="م" data-index="0" data-run="0" data-src="tajweed" data-conf="1.00">
    <path data-eid="e83-0" data-kind="body" data-cut="1" d="…"/>
    <path data-eid="e84" data-kind="mark" data-mark="damma" …/>
  </g>
  …
  <path data-kind="mark" data-mark="waqf-jaiz" …/>       <!-- word-level marks stay on the word -->
</g>
```

- `data-index` — letter position in the word's text (0 = first read). `data-text` — the
  letter as written (`ٱ`, `أ`, `ة` kept).
- `data-run` — which connected stroke the letter belongs to (dev information; the
  `ligature` wrapper is gone).
- `data-src` — where the cuts bounding the letter came from: `tajweed` (a hand cut lifted
  from the QUL tajweed font), `dk` (a DigitalKhatt-template joint), `none` (a run of one
  letter), or `tajweed+dk`. `data-conf` — the lowest confidence of those cuts.
- A run the builder could not cut is emitted UNSPLIT: one group with the run's whole
  text and `data-unsplit="1"`. A word whose ligature texts do not concatenate to its
  rasm is left exactly as the word build had it. Never a guess.
- Cut pieces carry `data-cut="1"` and the source contour's `data-eid` suffixed `-k`;
  every other path is byte-identical to the word build.

## How a run is cut

1. **Hand cuts.** The QUL "QPC V4 Tajweed" page fonts are this same 1441H artwork with
   every tajweed-coloured letter cut by hand into a COLR layer. Each word glyph is
   registered onto our word ink (one scale per page, ICP translation per word, accepted
   at ≥97% outline coverage — on p50 every word registers at 100%). Where a layer's
   outline runs through the inside of our stroke, that stretch is the hand's cut.
2. **DigitalKhatt joints.** The DK font shaped with HarfBuzz gives one glyph per letter.
   Registered to the run as templates (global correlation, then each template slid
   locally, reading order kept), every ink pixel takes the nearest template's label and
   each letter gets a reference point on its own ink. For a joint the hand did not cut,
   the stroke's centre line is walked from letter i's reference point to letter i+1's;
   every point is tried for the shortest crossing of the stroke through it, a crossing
   counts only if painting it separates the two reference points (a chord across a
   loop's wall never does — the ring connects around it — so a loop letter is cut
   right after its loop); of the crossings that count, the last one before letter
   i+1's template region begins is the joint: the connecting stroke stays with the
   letter it leaves.
3. **The cut itself** (`letters_lib.cut_run`). All chords of a run are painted three
   pixels wide over its raster (8 px/u); each letter is the connected side holding its
   reference point; the exact piece is the run intersected with that side's one-pixel
   envelope, and inside the painted strip with the chord's half-plane — so every
   boundary curve is the run's own except the chord. Checks: every chord separates
   letters k and k+1, no empty piece, areas conserve to 0.5%. Any failure is a flag,
   and the run is emitted unsplit.
4. **Marks.** Each letter's expected marks come from the text (`letters_of`, using the
   pipeline's own tables). Every (mark, letter) pair whose family fits an open slot is
   scored by the distance from the mark's centre to the letter's outline, and pairs are
   taken nearest first. Word-level marks (waqf signs, hizb…) stay on the word.

## The gate (`tools/audit_letters.py`)

| row | what | class |
|---|---|---|
| count | letters emitted == letters in the text, every letter with body ink | proof |
| ink | every non-cut path verbatim in both builds; cut pieces sum to their contour ±0.5% | proof |
| pixels | raster diff letters vs words at 1400 px: max ≤ 72/255 and over-24 pixels ≤ 10 + 8 × cuts | proof |
| marks | per-letter mark counts vs the text (tanween ≈ haraka; iqlab meem ignored) | prior |
| unsplit | runs/words emitted unsplit | count |

**Why the pixel row has a per-cut budget.** A chord is an abutting seam: two anti-aliased
edges meet and the pixel lightens by up to ~64/255 on 1–3 pixels per cut. `audit_pixels.py`
measured the same for split strokes (26–60) against 100+ for a real defect. Overlapping
the pieces to hide the seam makes it worse (measured: 0.1u overlap → 46/255), so pieces
never overlap.

## Numbers

Filled in by the 2026-09-05 full run — see the end of this file.

## Human loop

`docs/defects/letters_review.html` shows every flagged run and a seeded 2% blind sample of
accepted DigitalKhatt cuts, each letter in its own colour with the chords drawn, with a
verdict selector and a note box. "Copy decisions" emits JSON lines for
`docs/defects/letters_verdicts.jsonl`. Decisions become data (an override for a place, a
threshold for a joint pair), never code.
