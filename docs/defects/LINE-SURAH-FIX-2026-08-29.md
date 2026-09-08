# The line-membership and header-group defects — measured, fixed, gated

2026-08-29/30. Both defects are from `docs/shipping/SHIPPED-ARTIFACT-2026-08-29.md`
§8.2 and §8.3, both are consumer-visible in the emitted SVG, and both are fixed
at cause in `tools/assign_words.py`. Nothing here moves ink: every page is still
pixel-identical to the artwork.

| | before | after |
|---|---:|---:|
| words in the wrong `<g class="line">` | **58** on 52 pages | **0** |
| pages whose reading order breaks across a line boundary | 51 | 0 |
| `<g class="surah-name">` groups | **110** (27, 33, 37, 47 missing) | **114** |
| `<g class="basmalah">` groups | **113** for 112 surahs (17 split in two) | **112** |
| named marks orphaned outside any group, on text lines | **79** on 4 pages | **0** |
| elements in the corpus | 622,801 | 622,801 |

---

## 0. The new detector — `tools/audit_wordline.py`

Built first, so the defect could be measured before and after and can never
return silently. It reads the **emitted product**, not the pipeline, needs no
reference decomposition and no eye, and takes 40 s over all 604 pages.

```
python3 tools/audit_wordline.py [first] [last] [--dir D] [--json OUT] [--hist]
```

Two independent signals, and a word only counts when they agree:

- **GEOMETRY proposes.** Every line's band is the MEDIAN top and bottom of the
  words filed under it — a median so that a misfiled word cannot drag the band
  it is being tested against. A word belongs to the line its own box overlaps
  most.
- **ORDER disposes.** Concatenating a page's words line by line, right to left,
  must give the mushaf's own word order. Applying the whole page's geometric
  moves must leave that order unbroken, and where it was broken it must repair
  it.

The two are blind to each other's evidence: ORDER never looks at where ink is
drawn, GEOMETRY never looks at the text.

### The distribution that makes this a proof, not a prior

`--hist`, own-band overlap minus the best rival band, all 77,432 words:

```
BEFORE                                        AFTER
[  -inf,  -8.0)      58                       [  -inf,  -8.0)       0
[  -8.0,  -4.0)       0                       ... every bucket      0
[  -4.0,  -2.0)       0
[  -2.0,  -1.0)       0
[  -1.0,  -0.5)       0
[  -0.5,   0.0)       0
[   0.0,   0.5)       0
[   0.5,   1.0)       0
[   1.0,   2.0)       0
[   2.0,   4.0)       0
[   4.0,   8.0)       0
[   8.0,  +inf)   77374                       [   8.0,  +inf)   77432
```

**An empty band 16 units wide.** 77,374 words beat their nearest rival by more
than 8 units; 58 lose to it by more than 8; nothing at all lies between. The
threshold (0) sits in the middle of the gap, not at its edge. This is the same
standing as the mushaf-wide empty bands already used in this project.

Confirmation from the other side: the 58 geometric moves repair the reading
order on all 51 pages where it was broken and disturb it on none of the other
553. (The 58 exceed the 51 because on p103, p548, p549 and p552 two adjacent
words move together, and a single break can only expose one of them.)

Also reported, and true both before and after: **within a line, the word order
is right on 8,820 of 8,820 lines that hold words.** The sequence only ever broke
at a line boundary — which is what said "line MEMBERSHIP", not "ordering".

---

## 1. Defect 1 — 58 words in the wrong `<g class="line">`

### Cause

`rewrite()` sends every element of a word to one wrapper — "the source path
holding most of that word's ink". **A source path is not a line.** The artwork
keeps one compound `<path>` per line group, but a handful of contours per page
are drawn inside the NEIGHBOURING line's compound path, while
`add_line_structure` tags them — geometrically, by the band they are drawn
in — to the line they actually belong to.

Measured on p2 (`e["path"]` -> the `line` tags of its elements):

```
path 0 {1: 24}      path 4 {5: 72, 6: 2}
path 1 {2: 31}      path 5 {6: 63}
path 2 {3: 46, 4: 1} path 6 {6: 2, 7: 53}
path 3 {4: 70}      path 7 {8: 15}
```

Path *i* is the compound path of line *i+1*. Path 6 (line 7's path) carries two
contours tagged line 6; path 4 (line 5's path) carries two more. Word `2:4:11`
holds a dammah in path 5 (23.2 u²) and a sukun plus its whole body in path 6
(254.9 u²) — every element tagged **line 6**, but the heavier path is line 7's,
so the word came out inside `<g class="line" data-line="7">`, between line 6's
`2:4:10` and `2:4:12`.

### The fix, and why it is not just "use the line tag"

Using the geometric `line` tag instead fixed all 58 and broke **three new ones**:
p59 `3:75:19`, p549 `60:4:22` and p577 `74:53:1` each hold one body element
tagged a line above the one it is drawn in, and the body outweighs the rest of
the word. So *neither label is trustworthy on its own* — the source path's
group is wrong for 58 words, the geometric tag is wrong for 3.

The emitter now decides it the way the audit does, **on the ink**: each line's
band from the median top and bottom of the words provisionally in it, then each
word to the band its own box overlaps most, and finally the heaviest of that
word's own paths *inside that line's group* (falling back to the group's path
with `_reframe` compensation if the word has none there). The empty band above
is what licenses this: the decision is never marginal.

`QSVG_LINEHOME=0` restores the old path-only choice for A/B.

---

## 2. Defect 2 — four surahs with no banner, and one basmalah split in two

### Cause: our reading of the DB, not the DB

The DigitalKhatt layout DB is **right about which surahs have a banner** — 114
`surah_name` rows for 114 distinct surahs, 112 `basmallah` rows — and **wrong
for this artwork about which LINE they are on**. For surahs 27, 33, 37 and 47
the DB carries the banner as line 15 of the PREVIOUS page:

```
sqlite> SELECT * FROM pages WHERE page_number=376 ORDER BY line_number;   -- tail
(376, 13, 'ayah'), (376, 14, 'ayah'), (376, 15, 'surah_name', 27)
sqlite> SELECT * FROM pages WHERE page_number=377 ORDER BY line_number;
(377, 1, 'basmallah'), (377, 2..15, 'ayah')          -- 14 text lines
```

The artwork draws p376 with 15 text lines and p377 as `banner | basmalah | 13
text lines`. So a page-local read of the DB never sees surah 27's banner at
all, and DK's 14 text lines have to be squeezed into the art's 13.

`rewrite()` mapped DK line numbers to art lines by a majority vote over
`dk_line - art_line` across the page's words. That vote assumes a UNIFORM shift.
On p377 the shift is not uniform — it drifts from −1 at the top to 0 at the
bottom, exactly because 14 lines are being fitted into 13:

```
p377 offset votes:  0 -> 80 words   |   -1 -> 58 words
```

The vote picked 0. `hdr_art` became `{1: ("basmalah", 27)}` — so the **banner
line was labelled `basmalah`**, and the real basmalah on line 2 was never
claimed at all and came out as bare `<path>`s, which is where all 79 orphan
named marks lived (p377, p418, p446, p507; fathah 20, kasrah 20, hamzat_al_wasl 12, sukun
8, dot 8, shaddah 7, two_dots 4).

Surah 17's split basmalah on p282 has a second, smaller cause: one contour of
the basmalah is drawn inside line 1's compound path while tagged line 2, so the
emitter opened a `basmalah` group of 1 path in line 1's wrapper and another of
31 in line 2's — 113 groups for 112 surahs.

### What the artwork says, measured over all 604 pages

A line that holds no word is a header line, and those lines come in runs:

```
runs of consecutive wordless art lines:   114
  of length 2:                            112
  of length 1:                              2   (p1 surah 1, p187 surah 9)
  of length 3 or more:                      0
runs immediately followed by word 1 of ayah 1 of a surah:  114 of 114
```

A clean bijection with the mushaf's 114 surahs, and the two singletons are
exactly the two surahs with no basmalah of their own — al-Fatiha, whose
basmalah IS ayah 1:1, and at-Tawba, which has none. So a run reads top-down as
`[surah-name, basmalah]`, or `[surah-name]` alone when it is one line, and its
surah is the surah of the first word beneath it. **114 banners, 112 basmalahs.**

### The fix

`hdr_art` is now derived from the art (the wordless-line runs) and **confirmed
against the DB** (`dk_header_surahs()` — the surah sets, with the line numbers
dropped). A run is only labelled when both agree. `QSVG_HDRART=0` restores the
DK-line-number mapping for A/B.

Two supporting corrections fell out of it, both measured:

1. **"Wordless" means no word BODY.** A word's MARK can legitimately carry a
   header line's tag — the ۦ after the basmalah on p359 and p570 is
   override-pinned to its word and HDRGUARD may not evict it. Counting that as
   "this line has words" hid three more banners and three basmalahs (surahs 25,
   37, 71). No text line is bodyless.

2. **HDRGUARD now requires the ink to be IN the header band.** With p446's
   basmalah line correctly identified, HDRGUARD evicted the ت dots of
   `فَٱلزَّٰجِرَٰتِ` (37:2:1) into the basmalah group because they carry a stale
   line-2 tag. Measured over all 604 pages, **exactly 5 word elements in the
   whole mushaf carry a header line's tag**, and every one clears that line's
   own ink by a wide margin:

   | | page | word | mark | element y | header ink y | gap |
   |---|---|---|---|---|---|---:|
   | above | 446 | 37:2:1 | two_dots | 95.2–97.9 | 49.7–74.1 | **21.0** |
   | above | 570 | 71:1:5 | small_yaa | 241.2–245.8 | 194.3–218.8 | **22.3** |
   | below | 570 | 70:44:5 | omitted_alif | 129.3–135.3 | 158.5–182.1 | **23.1** |
   | above | 359 | 25:1:6 | small_yaa | 456.7–461.4 | 408.6–433.1 | **23.7** |
   | below | 570 | 70:44:4 | tanwin_al_damm | 120.6–127.0 | 158.5–182.1 | **31.5** |

   Not one overlaps. Requiring overlap therefore evicts nothing that was being
   evicted for a reason, and stops the one false eviction.

---

## 3. Collateral — full-mushaf element diff

Keyed by **(group class, owner, `data-kind`, `data-mark`, line) x `d`-string**,
never by `data-eid`. Before = the same working tree with `QSVG_LINEHOME=0
QSVG_HDRART=0`, so the diff isolates exactly these two changes.

```
elements before 622,801     after 622,801        (nothing added, nothing removed)
changed d-strings 615 on 57 pages
```

| classification | rows | |
|---|---:|---|
| **RIGHT** — line group corrected, group/owner/kind/mark all identical | 406 | defect 1, on 53 pages (the 52 the audit names, plus p282's stray basmalah contour) |
| **RIGHT** — bare header path joined its basmalah group | 120 | defect 2, p377/418/446/507 |
| **RIGHT** — mislabelled banner regrouped `basmalah` -> `surah-name` | 89 | defect 2, the same four pages |
| **WRONG** | 0 | |
| **UNCLEAR** | 0 | `docs/defects/line-surah-for-eye.json` is empty |

No element changed owner, kind or mark. No word gained or lost ink.

---

## 4. Also changed

- `tools/build_schema_registry.py` — `basmalah_groups` 113 -> **112**,
  `surah_name_groups_emitted` 108 -> **114**. The manifest had encoded the
  defect as if it were the edition (four banners emitted as basmalahs plus one
  basmalah split in two cancelled out to 113).
- `tools/build_annotations.py` — the ayah-mark regex assumed
  `class="ayah-mark" data-aid=` were adjacent. The marker group has since
  gained an `id` between them (the ayah->marker link landing in the same tree),
  so the pattern matched nothing on all 604 pages and
  `validate_annotations` failed with `marker: graph [] svg [...]` everywhere.
  Made attribute-order independent. **Not caused by the work in this document**
  — recorded here because it blocked the gate.

---

## 5. Gates — all run on the final build

| gate | required | measured |
|---|---|---|
| `tools/audit_pixels.py 1 604` | 0 failures | **FAILURES: 0** — every page pixel-identical (tol 24/255, seam 10 px, 1400 px) |
| `scratchpad/bench.py` | SCORE 137, no failures | **SCORE 137**, FAILURES none, pixelfail 0, budget-mismatch 0/2706 |
| `tools/audit_taxonomy.py` | OK | **OK** — 35 mark names, 3 waqf_al_muanaqah pairs, sifr 3970/66 |
| fresh sweep `.cache/sweeps/linesurah` | marks 0, intervals 1 | **603 of 604 pages `marks=0 iv=0`; p350 `marks=0 iv=1`** (the one examined by eye) |
| `tools/validate_annotations.py 1 604` | OK | **OK** — 77,432 words, 436,627 logical marks, 6,236 ayah markers, **114 surahs** |
| `tools/audit_wordline.py 1 604` | new | **0 misplaced**, 0 pages with a reading-order break |
| header groups | 114 / 112 | **114 surah-name (114 distinct), 112 basmalah (missing only surahs 1 and 9)** |
| orphan named marks on text lines | 0 | **0** |
