# Taking the ligature CUT from MushafDatabase — the measured A/B

2026-08-29. Abdullah's question: *"their ligature cuts are much better than ours
… what if we audit their ligature, adapt them, re-run our pipeline and see …
maybe many issues will be resolved without overrides."*

**Two answers, and they point in opposite directions.**

* **On the ligature layer it works, completely.** `audit_ligcuts`' cut
  disagreement falls **2,848 → 24**, `audit_ligatures`' `empty` **193 → 1** and
  `misplaced` **6 → 0**, with pixel identity 604/604, mark flags 0, interval
  records 1 (p350), bench and taxonomy unchanged, and **zero** changes to which
  element any word holds anywhere in the mushaf.
* **On the overrides it does nothing at all.** Of the 270 human overrides,
  **0** become redundant. Rebuilt with the overrides removed, the two arms
  disagree on **not one entry**. That is not a surprise once measured: every
  override is an element→word OWNERSHIP fact, and this change never moves an
  element between words.

And the most useful thing the experiment produced is not the reference data at
all — it is the attribution below, which shows **two thirds of the defect is
fixable from our own rules with no outside source**.

Tools: `tools/build_mdb_runs.py` (extract), `QSVG_MDBCUT=1` in
`tools/assign_words.py` (apply). Cache: `.cache/mdb_runs.json`.

```bash
python3 tools/build_mdb_runs.py 1 604 --jobs 32     # ~80 s, writes 5.9 MB
QSVG_MDBCUT=1 python3 tools/audit_ligcuts.py 1 604 --jobs 24
```

---

## 1. Extraction and coverage

MushafDatabase publishes one `<g id="md-ligature-…">` per run of ink per word.
`build_mdb_runs.py` expresses that partition in OUR element space:

| stage | how | result |
|---|---|---|
| contours | `svg_lines.subpaths` on BOTH sides — it solves the Bezier derivative for an EXACT box. `audit_inkidentity`'s control-point hull is fine there (applied to both sides) but inflates a box by up to 0.4u, and our own elements carry exact boxes | 790,333 our contours |
| registration | `audit_inkidentity.estimate` unchanged: one affine per page, seeded at 4/3 with a modal vote on the offset, refined by least squares on the pairs | scale 4/3 both axes, residual 0.010u median |
| pairing | `audit_inkidentity.match` unchanged — size within 0.15u, centre within 0.6u, inside the measured **empty band 0.1u‥2.0u** | **779,888 paired (98.68%)** |
| element → run | the run holding the element's paired contours | see below |

**The key measurement, and it is proof-class.** For every one of the 10,716
body elements on pages 3‑42 with a `--dist` run, **the contours of an element
are UNANIMOUS about which reference run they belong to — 100.00%, no second
bucket at all.** Mushaf-wide the same check reports `contours disagree 0`. Our
elements are never split across two of their runs, so the whole disagreement
lives at the ATOM level and nothing has to be cut.

```
pages mapped 602 | excluded 2 | no reference page 0
   p1  artwork differs (paired 1 of 334)      <- the ornate opening spread is
   p2  artwork differs (paired 1 of 487)         set at a different size
contours 790333 | paired 779888 (98.678%)
body elements 163885 | run resolved 159482 (97.313%) | contours disagree 0 | unpaired 4403
```

**Excluded, as the brief required:** p1 and p2 (65 words — the reference draws
that spread at another size, no single scale aligns it), and the nine words at
p11 2:72:4, p262 15:7 (`لَّوۡمَا` is one word for them, two for us) and p451
37:130 (`إِلْ يَاسِينَ` is two for them, one for us). `audit_ligcuts` reports
**77,422 comparable words of 77,431 aligned by index** in both arms.

**Fallback rate at build time** — `mdb_recut` returns `None` and today's cut is
kept when no body of the word is in the reference:

```
words recut 77362 | fallback 70 (0.09%)
   atom count unchanged 75689 | more atoms 830 | fewer atoms 843
   alignment: identity 76978 | width-prior DP 384
```

The 4,403 unpaired body elements do **not** cause a fallback: a body the
reference does not cover keeps an atom of its own unless it overlaps an
existing atom by ≥60% of its own width, which is `cluster_line`'s own
stacked-stroke threshold.

---

## 2. Where the cut is actually lost — the finding that matters

The first version of this pass ran where the atoms are built, right after
`cluster_line`. **It fixed almost nothing** (1 split over three pages) and it
took reading the ink of the Tier-E exemplar to see why.

p76 `أُو۟لَٰٓئِكَ` 3:199:22 — at clustering time the word's own cluster does
not contain the ink at all:

```
cluster for 3:199:21   atom0  299.7..333.0   (their run 3:199:21#0)
                       atom1  293.0..296.1   (their run 3:199:22#0  = the ا)
                       atom2  279.9..289.8   (their run 3:199:22#1  = the و)
```

A later mover hands those two bodies to word 22 and **appends them to an
existing atom** rather than opening one, so an early recut is undone
downstream. The pass therefore runs LAST, immediately before `QSVG_LIGFIX` and
after every mover.

### Two independent causes, separated by measurement

Three builds, same audit:

| build | cut rows |
|---|---|
| our atoms + our `align_segs_atoms` (today) | **2,848** |
| **their atoms** + our `align_segs_atoms` | 1,929 |
| **their atoms + identity alignment** | **24** |

* the **atom partition** explains **919 rows (32%)**;
* **`align_segs_atoms` explains 1,905 rows (67%)** — it merges atoms that were
  already correctly separated, because its width prior scores a merge cheaper.

Once the atoms are the runs, the alignment is forced and the DP has nothing to
decide. That is why the pass assigns 1:1 whenever `len(atoms) == len(segs)`
(76,978 words) and falls back to the DP only for the 384 where they differ.

**Ordering had to come from the run index, not from x.** p6 `وَكَانَ` draws its
`و` at 139.6‑149.5 *inside* `كا`'s 135.4‑149.6; sorting atoms by x2 puts `كا`
first, which breaks the monotone alignment and the emitted group sequence. With
x-sorting the score was 1,964; with run order it is 24.

---

## 3. The A/B, every metric, both directions

Both arms are the SAME pinned file, `QSVG_MDBCUT` 0 vs 1, run back to back.
(The repository was being edited by a parallel session throughout; every pair
below was produced from one pinned snapshot so nothing straddles a code
change.)

| metric | `QSVG_MDBCUT=0` | `QSVG_MDBCUT=1` | |
|---|---|---|---|
| `audit_pixels 1 604` | 0 failures | **0 failures** | gate held |
| emitted SVG vs the pre-change build | **byte-identical 604/604** | 593 pages differ | default is inert |
| element multiset (word key, kind, mark, d-string) | — | **0 pages changed** | no ink, naming or ownership moved |
| `audit_ligcuts` cut | 2,848 | **24** | |
| `audit_ligcuts` missing-ink(regrouped) — Tier D | 34 | **0** | |
| `audit_ligcuts` missing-ink / boundary / extent / ref-empty | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | |
| `audit_ligatures` empty | 193 | **1** | |
| `audit_ligatures` count | 0 | 0 | |
| `audit_ligatures` order | 1 | **3** | +2, explained below |
| `audit_ligatures` misplaced | 6 | **0** | |
| emitted `<g class="ligature">` | 156,707 | 159,579 | +2,872 |
| `audit_inkidentity` classes | ownership 12, subpath-split 532, ours-null 38, their-sajdah 26, position 4, region 1 | **identical, row for row** | ink identity untouched |
| full sweep — mark flags | 0 | **0** | 0 pages worse |
| full sweep — interval records | 1 (p350) | **1 (p350)** | |
| `scratchpad/bench.py` | SCORE 337, 2 failures | **SCORE 337, 2 failures** | identical |
| `tools/audit_taxonomy.py` | OK | **OK** | identical |
| overrides retired | — | **0 of 270** | §5 |

Byte identity of the OFF path was proved twice, on two different code states,
by md5 of the emitted SVG for all 604 pages against a build with the switch's
code physically removed.

### What changed, classified — no unexplained collateral

3,207 words have a different ligature partition:

| class | words | |
|---|---|---|
| **more groups** | 2,824 | RIGHT — the Tier E family |
| **same count, marks reseated** | 381 | RIGHT — the small-alef / tanween family §4 |
| **fewer groups** | 2 | WRONG-ish, see below |

The two are `أَيْدِيهِمْ` on p324 21:28:4 and p341 22:76:4:

```
OFF  ['ا', 'يد', 'يهم']      the ا group holds NO ink  (one of the 193 `empty`)
ON   ['ايد', 'يهم']          a run the script cannot draw
```

Our decomposition has only two body elements there: `group_elements` welded the
alef's contour into the `يد` element. Before, we invented a third group naming
`ا` and holding nothing; now we name the group after the letters it does hold.
Both are wrong in different ways and the real fix is a contour split. This is
the same trade that took `empty` from 193 to 1, applied twice in the wrong
direction.

`order` 1 → 3 is one convention: on p379 27:30:8 and p548 59:22:13 the
reference lists `ٱلرَّحِيم`'s alef run LAST (`لر|حيم|ا`), so taking their run
index as reading order emits the groups out of x order. Two words, cosmetic,
and the third row (p451 `إِلْ يَاسِينَ`) is the known incomparable word.

### Verified by reading the ink, not by counting

```
p76 3:199:22 أُو۟لَٰٓئِكَ
OFF  اوليك   bodies 230.4‑282.3, 245.7‑250.5, 279.9‑289.8, 293.0‑296.1
             marks  fatha maddah small-alef hamza kasra fatha damma hamza sifr
ON   ا       body 293.0‑296.1   marks damma, hamza        <- the أُ
     و       body 279.9‑289.8   marks sifr-mustadir       <- the و۟, its own circle
     ليك     bodies 230.4‑282.3, 245.7‑250.5  the rest

p8 2:54:16 ذَٰلِكُمْ
OFF  ذ    marks fatha, dot          لكم  marks small-alef, damma, sukun, kasra
ON   ذ    marks fatha, dot, small-alef   لكم  marks damma, sukun, kasra
```

The second is the dagger alef of `ذَٰ`, which the `QSVG_LIGFIX` work
(LIGATURE-REGROUP-2026-08-29.md §5) recorded as *unfixable* — 91 small-alef
cases where "`cluster_line` merged separate narrow bodies into one atom, so no
regrouping pass downstream can separate them". Changing the cut separates them.

---

## 4. The override question, answered plainly

`.cache/review/overrides.json` holds **270** entries over 123 pages (the "250"
in the brief has grown). Every entry has ONE form: an element geometry key →
the word that owns it, optionally with a `|mark` rename. **There is no
intra-word grouping override form at all**, so the intra/inter split the brief
asked for has a degenerate answer: 270 inter-word, 0 intra-word.

Measured with `QSVG_OVR` pointed at an empty file:

| | MDBCUT=0 | MDBCUT=1 |
|---|---|---|
| entries the unaided build already satisfies (word AND mark) | 8 | **8** |
| entries whose word is already right | 19 | **19** |
| entries still needed | 262 | **262** |
| **entries whose unaided outcome differs between the arms** | — | **0** |

Not one override moves. The reason is structural and is the same fact that
makes the change safe: the full-mushaf element diff shows **0 ownership
changes**, and every override is an ownership fact. The 99 entries concentrated
on 16 (page, ayah) line-error sites — p418 33:3 (15 entries), p548 59:19 (12),
p555 63:10 (8), p131 6:34, p341 22:73, p543 58:7 … — are exactly the family
TASKS.md §6 says needs one fix at the word-boundary stage, and this is not it.

**So: no, the overrides are not resolved by this. They are a different layer.**

---

## 5. The reference-free fix hiding inside the result

Because §2 attributes two thirds of the defect to `align_segs_atoms` rather
than to the atoms, most of it can be fixed with **no outside data whatsoever**.
Refusing to run the width-prior DP when the atom count already equals the
number of pieces the joining rules allow:

```python
segs = segment_word(w["uthmani"])
if len(cl) == len(segs):
    groups, cost = [([a], [s]) for a, s in zip(cl, segs)], 0.0
else:
    groups, cost = align_segs_atoms(cl, segs)
```

Measured over 604 pages, OUR atoms, no reference:

| | today | identity alignment |
|---|---|---|
| `audit_ligcuts` cut | 2,848 | **1,020** (−64%) |
| `audit_ligcuts` missing-ink(regrouped) | 34 | 38 |
| `audit_ligatures` empty | 193 | **211** |
| `audit_ligatures` misplaced | 6 | 5 |
| `audit_ligatures` order | 1 | 1 |
| sweep marks / intervals | 0 / 1 | **0 / 1** |

A real, cheap, self-contained gain, with a real cost: 18 more `empty` groups
and 4 more Tier D rows. It has NOT been through `audit_pixels` or bench and is
offered as a candidate, not a result. The variant is
`scratchpad/` `pin_ident.py` in this session's working directory; the change is
the four lines above, at `assign_words.py`'s `groups, cost = align_segs_atoms(cl, segs)`.

---

## 6. Two things found on the way

* **`audit_inkidentity.py` was reading retired attributes.** The emitter moved
  to a single `data-wid="surah:ayah:word"` on 2026-08-29; the audit still read
  `data-surah`/`data-ayah`/`data-word` and so keyed every contour on a page
  `"None:None:None"`, collapsing the whole page into one word. It was fixed by
  a parallel session while this experiment ran. Any ink-identity number quoted
  from a run before that fix is meaningless — including, possibly, the "22
  ownership words" in LIGATURE-CUTS-VS-MUSHAFDB-2026-08-29.md; the current
  figure on both arms is **12**, of which 10 are the known-incomparable p262 /
  p451 words and 2 are the p315 20:58 mark swap.
* **`scratchpad/bench.py` is not at TASKS.md's stated state.** It reports
  `SCORE 337` with `FAILURES: ['coverage-p1 (182, 194)', 'coverage-p2 (253,
  268)']`, not `SCORE 137, no failures`. Identical in both arms, so it is
  neutral for this A/B, but it is not the gate TASKS.md describes and someone
  should find out which of the two is stale.

---

## 7. Recommendation — ADOPT WITH CONDITIONS, and not as it stands

The measurement is unambiguous: on every metric that describes the ligature
layer this is a large, clean win, and on every gate it is neutral. If the
ligature cut were the only consideration, this would ship today.

It should not ship as it stands, for one reason that is not about the numbers:
**it makes another project's decomposition a build input.** The cut would stop
being derivable from the artwork plus our own rules and would become a 5.9 MB
table copied from `MushafDatabase-Ligature-Based-SVG`. That is a change of kind
from `QSVG_DKLINES`, which took a LAYOUT table from a source that models this
print; here we would be taking the answer to the very question the ligature
layer exists to answer, and the letter-level decomposition TASKS.md §5 is
aiming at would be built on it. It is also a licensing question the NOTICE file
should answer before, not after.

The conditions:

1. **Ship §5 first** — the identity alignment. It is ours, it needs no outside
   data, it recovers 64% of the defect, and it needs one gate run
   (`audit_pixels`, bench) that this experiment did not do for it. Then
   re-measure what MDBCUT is still worth on top; on today's numbers it would be
   the remaining ~1,000 cut rows plus the 381 mark reseatings.
2. **Keep `QSVG_MDBCUT` as an ORACLE either way.** The residue is now small
   enough to read: 24 cut rows, of which 17 are the known `ـىٰ`+suffix family
   where BOTH sides draw an illegal run, 4 are p1/p2 fallbacks, 2 are the
   `أَيْدِيهِمْ` contour weld and 1 is p239 `إِنَّهُۥ`. That is a finite list of
   real defects, which is exactly what an oracle is for.
3. **The 843 words where the reference has FEWER atoms than we do have not been
   adjudicated.** They are the other direction of the same disagreement — our
   clustering splitting one run — and nothing here proves the reference right
   about them. They are pixel-neutral and they need an eye before any of this
   is called settled.
4. **Do not expect anything for the overrides.** §4 is a measured zero and it
   will stay zero as long as this pass moves no ink between words.

If Abdullah's answer to the licensing/derivability question is "a reference
table is fine", then adopt: the switch is written, defaults off, is
byte-identical off, and is green on every gate on.
