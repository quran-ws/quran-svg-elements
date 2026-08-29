# Self-contained metadata, one identity attribute, RTL element order

**2026-08-29. Schema v2 phase 1, with Abdullah's four rulings folded in.**

His brief: *"we need to improve our structure so the svgs will be an alternative
to quran metadata database … complete metadata for surah — name, number, arabic
and english; each hizb mark should also hold its rubua, nisf, juz number; also
juz starts; also the words should have a clean one for search; also we should
use better tag ids so for word instead of surah/ayah/word attributes maybe one
surah:ayah:word attribute is enough … the order of elements should match the
order in arabic RTL, so if a word has three dammas the tags for them should
start right to left."*

All of it is in. Everything below is measured, not asserted.

---

## 1. The attribute schema, before and after

### `<g class="word">` — one identity attribute, two search keys

```
before  <g class="word" data-surah="2" data-ayah="6" data-word="3"
                        data-uthmani="سَوَآءٌ" data-imlaei="سواء" data-qpc="سَوَآءٌ">

after   <g class="word" data-wid="2:6:3"
                        data-uthmani="سَوَآءٌ" data-rasm="سواء"
                        data-imlaei="سواء" data-qpc="سَوَآءٌ">
```

`data-surah` / `data-ayah` / `data-word` are **gone**, replaced by `data-wid`.
This is the breaking option, chosen knowingly; §4 lists every consumer migrated
in the same change and the proof each still works.

### `<g class="ayah">` — `data-aid`, plus the division it opens

```
before  <g class="ayah" data-surah="2" data-ayah="142">
after   <g class="ayah" data-aid="2:142" data-juz-start="2" data-hizb-start="3"
                        data-rub-start="9">
```

`data-juz-start` / `-hizb-start` / `-nisf-start` / `-rub-start` appear **only on
the ayah that begins that division**, so "where does juz 15 start" is answerable
from the pages alone. Counts across the mushaf: 30 juz starts, 60 hizb starts,
60 nisf starts, 240 rubʿ starts.

An ayah is emitted once per LINE it occupies, so these attributes repeat on
every fragment of that ayah — they describe the ayah, not the fragment.

### `<g class="surah-name">` and `<g class="basmalah">` — the surah's card

```
before  <g class="surah-name" data-surah="79">
after   <g class="surah-name" data-sid="79" data-surah-name-ar="النازعات"
             data-surah-name-latin="An-Nazi'at" data-surah-name-en="Those who drag forth"
             data-revelation-place="makkah" data-ayah-count="46">
```

Carried on both banner kinds (108 surah-name groups + 113 basmalah groups), so a
surah opening always has its card even on the six pages whose surah-name line the
DK layout DB carries on the previous page.

### `<g class="hizb-mark">` — which division the rosette opens

```
before  <g class="hizb-mark" data-mark="hizb" data-surah="2" data-ayah="142">
after   <g class="hizb-mark" data-mark="hizb" data-aid="2:142" data-rub="9"
             data-rub-in-hizb="1" data-nisf="1" data-hizb="3" data-juz="2">
```

### `<g class="ayah-marker">`, `<g class="sajdah-mark">`, standalone `<path>`

```
before  <g class="ayah-marker" data-surah="2" data-ayah="6">
after   <g class="ayah-marker" data-aid="2:6">

before  <g class="sajdah-mark" data-mark="sajdah" data-surah="16" data-ayah="50">
after   <g class="sajdah-mark" data-mark="sajdah" data-aid="16:50">

before  <path data-standalone="1" data-surah="16" data-ayah="50" …>
after   <path data-standalone="1" data-aid="16:50" …>
```

Unchanged: `data-eid`, `data-kind`, `data-mark`, `data-mark-part`,
`data-mark-family`, `data-sig`, `data-form`, `data-pair`, `data-iqlab`,
`data-fused`, `data-line`, `data-text`, `data-uthmani`, `data-imlaei`,
`data-qpc`.

### The search key

`data-rasm` is the uthmani spelling with every combining mark removed:

| kept | dropped |
|---|---|
| Unicode category **Lo** — 47 code points, the Arabic letters | **Mn** (24 code points: every haraka, tanween, sukun, shadda, superscript alef, every small high/low sign) |
| | **Lm** — U+0640 tatweel ×6,736, U+06E5 small waw ×1,257, U+06E6 small yeh ×957 |
| | **So** — U+06DE rub sign ×199, U+06E9 sajdah ×15 |
| | **Cf** — U+200F RLM ×1 |

Measured over all 77,429 words of the cached uthmani text: exactly 72 distinct
code points occur, and the two groups are disjoint by Unicode category — so the
rule is a category test, not a hand-written list that can drift.

**Nothing is folded.** ا/أ/إ/آ/ٱ stay distinct, ى stays distinct from ي, ة from
ه — per Abdullah's explicit ruling. So `ٱلرَّحْمَٰنِ` → `ٱلرحمن`, keeping the alef
wasla. **One thing to flag:** his own example wrote the result as `الرحمن` with a
plain alef, which would mean folding ٱ→ا. The explicit "do not normalise
ا/أ/إ/آ/ٱ" won, and this is a one-line change in `quran_meta.rasm` if he meant
the example instead.

The second search attribute is `data-imlaei`, unchanged. **Honest note:** 77,409
of the 77,429 imlaei strings still carry diacritics, so `data-rasm` is the only
attribute that is actually "clean" today. Stripping imlaei too is one line and
was not done because the brief said the imlaei form is "the one we already
hold".

---

## 2. Where every metadata field comes from

Nothing is hand-typed. `tools/quran_meta.py` is the single reader.

| field | source |
|---|---|
| surah number, `name_arabic`, `name_simple`, `name_complex`, English translated name, `revelation_place`, `revelation_order`, `verses_count`, `bismillah_pre`, page range | quran.com `GET /api/v4/chapters?language=en`, fetched once and cached verbatim at **`.cache/meta/chapters.json`** — the same API and the same cache-on-first-use pattern `page_words()` uses for `/verses/by_page` |
| juz number, hizb number, rubʿ number of every ayah | **`.cache/words/page-*.json`** — the per-page word cache the pipeline already reads. Every verse record carries `juz_number`, `hizb_number`, `rub_el_hizb_number` |
| the 240 rubʿ START positions | derived from the same records (first verse per `rub_el_hizb_number`), memoised at `.cache/meta/rub_starts.json` |
| nisf (half-hizb) | arithmetic: quarters 1-2 of a hizb are nisf 1, quarters 3-4 are nisf 2 |
| pages, lines per page, layout name, font | **`.cache/digitalkhatt/digital-khatt-15-lines.db`**, `info` table |
| rare-sign sites | `.cache/marks/rare_places.json` |
| sifr word counts, muanaqah pairs, sajdah sites | measured mushaf-wide, already gated by `tools/audit_taxonomy.py` |

**The juz/hizb/rubʿ numbers are self-consistent.** Over all 6,236 verses,
`juz = ceil(rub/8)` and `hizb = ceil(rub/4)` hold with **zero exceptions**, so
the global rubʿ index 1-240 is the only key stored and everything else derives
from it.

### A measured finding: 199 rosettes for 240 quarters

The print draws the ۞ at 199 of the 240 rubʿ boundaries. All 199 sit **exactly**
on a rubʿ start (199 of 199). Of the 41 that are absent, **41 of 41 fall on an
ayah 1** — the rubʿ coincides with a surah opening, where the banner marks the
division instead. No exceptions in either direction; this is why the emitter can
read the rosette's division straight off the ayah under it.

---

## 3. Element order: right to left, one rule

**The rule.** Inside a word, its ligature groups come out right to left; inside
each ligature group, its elements come out right to left, by `x2` descending
(tie-break `x1` descending, then original order). Letter bodies and marks alike
— one rule, no exception. So a word with three dammas emits them rightmost
first.

**What is NOT reordered**, deliberately:

* **contours inside an element** — `build_d()` keeps a contour's source text
  while it still follows its predecessor and only writes an absolute moveto when
  it does not, so re-ordering contours changes d-strings and can move ink.
  Elements only. `build_d` is called once per element and depends on nothing
  outside it, which is why every d-string in the mushaf is byte-identical before
  and after (§5).
* **word-less ink** — header ink and the standalone sajdah/hizb groups are
  emitted after their own ayah on purpose; those entries are stepped over
  untouched.
* **word blocks and ayah runs** — document order of words is unchanged, so the
  `<g class="ayah">` grouping cannot move.

**Why it is pixel-safe:** every path in this artwork is `fill="#231f20"`, so
same-colour coverage composites order-independently — the identical property
that already lets `rewrite()` regroup elements at all.

**Before / after, all 604 pages** (`scratchpad/rtl_order_scan.py`, which rebuilds
each page with `QSVG_EIDMAP` so every emitted path carries its box):

| | ligature groups not in RTL order | words whose ligature groups are not in RTL order |
|---|---|---|
| `QSVG_RTL=0` (old behaviour) | **109,522** of 156,707 (69.9%) | **146** of 77,432 |
| `QSVG_RTL=1` (default now) | **0** | **0** |

The switch `QSVG_RTL=0` restores the old order for A/B.

Note the rule does **not** make a whole word's element list monotone in x, and
should not: ligature groups overlap in x because a mark can overhang its
neighbour. RTL holds within each group and between groups by their rightmost
element, which is the reading order.

---

## 3b. DEFECT FIXED: 5,881 of 6,236 ayah medallions were labelled with the wrong ayah

The most consumer-visible bug in the product: anything using a medallion to
locate its ayah got the wrong ayah on 598 of 604 pages.

**The cause.** `tag_ayah_markers()` paired the Nth marker in DOCUMENT ORDER with
the Nth ayah of the page's sorted ayah list, on its docstring's claim that
"markers appear in ayah order". The artwork's marker layer is usually ordered
**bottom-to-top**, so the claim is false: on p3 the first marker in the file
closes 2:16 and was being labelled 2:6.

**The fix is by POSITION, not by order** — reversal would be another positional
assumption and it is wrong on 8 pages. A medallion closes the ayah whose LAST
WORD it follows. The anchor is that word's leftmost body ink at its vertical
centre, taken from the final assignment; the marker centre is the `ayah:x` /
`ayah:y` the artwork already carries. Both are page coordinates.

**Measured, all 604 pages, 6,236 markers** (`scratchpad/marker_match.py`,
Manhattan distance):

```
nearest ayah end     min  5.5   p50 13.3   p90 15.7   p99 18.3   max 25.5
margin to 2nd nearest min 14.6  p1  22.2   p10 31.7   p50 73.7
pages where two markers claim the same ayah:  0 of 604
```

distance histogram   5-10: 214 · 10-15: 4,946 · 15-20: 1,059 · 20-25: 14 · 25-30: 3
margin histogram     10-15: 1 · 15-20: 19 · 20-25: 136 · 25-30: 315 · … · 60+: 4,062

So every medallion's own ayah end is within 25.5 units and the runner-up is
never less than 14.6 units further behind. There is no near-tie anywhere, the
assignment is 1:1 on every page, and **no threshold is applied at all** — the
rule is "nearest anchor, one ayah per marker", and the margin distribution is
what says that is safe rather than a guess. (Implementation still resolves a
double-claim by letting the losing marker fall to its next-nearest ayah, so a
future page that did tie would produce a 1:1 answer rather than a silent
duplicate.)

**Second, independent signal.** Plain reversal of the sorted ayah list gives the
same answer on **6,172 of 6,236** markers. The 64 it differs on are exactly why
reversal is not the fix — the layer order is not uniform:

| pages | layer order | was it already right? |
|---|---|---|
| p1, p2, p84, p162, p175 (+1 single-marker page) | FORWARD | yes — these 6 do not change |
| 596 pages | bottom-to-top | no |
| p313, p507, p577 | MIXED — p313 draws 20:13's marker first, then 20:37 down to 20:14 | no |

Only position explains all three shapes.

**Effect and proof of no collateral.** Full-mushaf element diff against the
build immediately before this fix:

```
d-strings ADDED 0 · REMOVED 0
non-marker element multisets differing: 0 pages
<g class="ayah-marker"> data-aid changed: 5,881 markers on 598 pages
```

Exactly the number the measurement predicted, and nothing else moved. Ring
position and scale are untouched — this writes an attribute.

The graph carries it too: each page's annotation record now holds an
`ayah-marker` relation per medallion, and `validate_annotations` checks the set
matches the SVG page for page and totals 6,236 mushaf-wide.

---

## 4. Consumer migration — every one found by grep, every one verified

Found with `grep -rln 'data-surah|data-ayah|data-word'` over `tools/`,
`scratchpad/`, `docs/`, then read one by one.

| consumer | change | verified by |
|---|---|---|
| `tools/review-platform/index.html` (2 sites: the audit-grid key, and `wid(w)`) | `g.dataset.wid` | **live**: served `?page=350&step=audit&user=abdullah&word=24:1:5` in a real browser — 138 word cards built, the deep-linked card focused, only console error is `favicon.ico` 404 |
| `tools/review_server.py` (3 sites) | `el.get("data-wid")`, `data-wid="([^"]*)"` | server started, page + `/svg/350.svg` served, platform above driven through it |
| `tools/audit_taxonomy.py` | word key = `data-wid`; rare-site ref = first two fields of it | `audit_taxonomy 1 604` **OK** (§5) |
| `tools/audit_inkidentity.py` | `keyof` returns `data-wid` | `ours(350)` → 1,707 rows, 1,509 keyed `24:1:1`… |
| `tools/eid_lookup.py` | `data-wid="…" data-uthmani="…"` | `eid_lookup 350 e10 e20` resolves both to `24:1:2 أَنزَلْنَٰهَا` |
| `tools/build_mismatch_page.py` | `<g class="word" data-wid="s:a:w"` | `mismatches.html` rebuilt, 106 cards |
| `tools/build_ligcuts_page.py` | same, plus `data-rasm` added to the attribute stripper | `ligature_cuts.html` rebuilt, 5.8 MB, 7,449 ink paths |
| `tools/build_proposals_page.py`, `tools/score_confidence.py` | JS selector → `g.word[data-wid="…"]` | selector strings; both are one-line template selectors |
| `docs/demo/build_embed.py` (3 sites) | word/marker regexes read `data-wid`/`data-aid`; a **demo-local** `data-ayah` is written back onto each word because CSS has no substring match on `data-wid` | `003-embed.svg` rebuilt: 153 views, 306 isolation rules, 127 words, 33 markers |
| `tools/build_eye_batch.py`, `tools/build_remaining.py`, `tools/build_variants_page.py` | none needed (they key on `data-uthmani` / `data-sig` / eids) | `eye_batch.html` 112 words, `remaining.html` 0 mark flags / 0 open intervals, `variants.html` 2,396 shapes — all rebuilt clean |

**Deliberately NOT migrated** — these read the *MushafDatabase* reference SVGs,
whose schema is `data-surah` / `data-aya` / `data-word-index-in-ayah` and is not
ours: `tools/refdb.py`, `tools/audit_ligcuts.py` (lines 186-187),
`tools/build_ligcuts_page.py` (line 143), `scratchpad/ligcmp/proto.py`.

`tools/_pipeline_baseline.py` is the pinned pre-change build and is left alone by
design.

---

## 5. Gates

| gate | result |
|---|---|
| `tools/audit_pixels.py 1 604` | **FAILURES: 0** — every page pixel-identical (tol 24/255, seam allowance 10 px, at 1400 px) |
| `tools/audit_taxonomy.py 1 604` | **OK** — 35 mark names, 3 muanaqah pairs, sifr words 3970/66, all 8 rare sites |
| fresh sweep (`.cache/sweeps/schema3`, stale caches removed first) | **marks 0, intervals 1** (p350 only, the one examined by eye) |
| `scratchpad/bench.py` | **SCORE 337, FAILURES `coverage-p1`, `coverage-p2`** — see the box below; NOT caused by this change |
| `tools/validate_annotations.py 1 604` | **OK** — 77,432 words, 436,706 logical marks in 34 names, 199 hizb rosettes, **6,236 ayah markers**, 30 juz starts, 114 surahs |

> ### The bench failure is not this change — proof
>
> `mushafs/hafs/kfqc/svg/001.svg` and `002.svg` were **regenerated at 21:13** by
> a concurrent agent's opening-page work (committed as *"Segment the opening
> pages' surah name as a band of its own"*), between this session's before- and
> after-snapshots. Three independent checks:
>
> 1. bench with **`QSVG_RTL=0`** (this change disabled): same two failures, same
>    SCORE 337.
> 2. bench run against **`git show HEAD:tools/assign_words.py`** — the committed
>    file with none of this session's edits: same two failures, same SCORE 337.
> 3. building p1 and p2 with `QSVG_RTL=0` on the current artwork reproduces the
>    after-snapshot's d-string multiset **exactly** (0 added, 0 removed), while
>    both differ from the before-snapshot by the same 6 and 11 contours.
>
> On the pre-21:13 artwork this change was bench-neutral. The p1/p2 coverage
> regression belongs to that agent's work and needs their attention, not this
> one's.

---

## 6. Full-mushaf element diff

`scratchpad/element_snap.py` snapshots every `<path>` of every page as
**(group key, `data-kind`, `data-mark`, d-string)** in document order —
by content, never by `data-eid`, which is not stable across builds. Both
snapshots were taken from a complete 604-page rebuild.

**Pages 3-604 (the 602 pages the concurrent artwork change did not touch):**

```
d-strings ADDED   : 0
d-strings REMOVED : 0
elements whose (group, kind, mark, d) changed: 0
groups whose element ORDER changed: 110,469 of 161,739  (602 pages)
```

So: **not one element changed owner, kind, name or ink.** Every change is either
an attribute rename/addition or the RTL reorder.

Group attribute-set changes, all of them intended:

| before | after | count |
|---|---|---|
| `data-surah,data-ayah,data-word,data-uthmani,data-imlaei,data-qpc` | `data-wid,data-uthmani,data-rasm,data-imlaei,data-qpc` | 77,367 |
| `data-surah,data-ayah` | `data-aid` | 19,044 |
| `data-text` | `data-text` (same attribute, different ligature — the RTL reorder pairing) | 1,148 |
| `data-surah,data-ayah` | `data-aid,data-rub-start` | 362 |
| `data-surah` | `data-sid` + the five surah-card fields | 220 |
| `data-surah,data-ayah,data-mark` | `data-aid,data-mark,data-rub,data-rub-in-hizb,data-nisf,data-hizb,data-juz` | 199 |
| `data-surah,data-ayah` | `data-aid,data-nisf-start,data-rub-start` | 168 |
| `data-surah,data-ayah` | `data-aid,data-juz-start,data-hizb-start,data-rub-start` | 72 |
| `data-surah,data-ayah` | `data-aid,data-hizb-start,data-rub-start` | 68 |
| `data-surah,data-ayah,data-mark` | `data-aid,data-mark` (sajdah) | 17 |

The 1,148 `data-text → data-text` rows are the diff tool pairing ligature groups
positionally after they were reordered. Checked directly: **all 77,367 words keep
exactly the same multiset of ligature texts — 0 words differ**, so the cut did
not move.

**Pages 1-2:** 2 d-strings added, 17 removed, 632 elements regrouped into
`surah-name`. Attributed above to the concurrent artwork change and reproduced
with this change disabled.

---

## 7. Schema v2 phase 1 — the files

| file | what it is |
|---|---|
| `tools/quran_meta.py` | the single reader for surah / juz / hizb / rubʿ metadata and the rasm rule. Fetches and caches `chapters.json`; derives and memoises `rub_starts.json` |
| `tools/build_schema_registry.py` | writes the two schema files below; `--check` fails if either is stale |
| `.cache/schema/mark-taxonomy.v2.json` | the closed mark vocabulary as DATA: 35 active names + 1 reserved (`waqf-mamnu`, inactive per §4.3), each with category, family and legal features; the emitted `data-kind` values; the feature value sets; the retired aliases |
| `.cache/schema/edition-hafs-kfgqpc.json` | the edition manifest: 604 pages / 15 lines (DK `info`), the 114-surah table, the 240 rubʿ starts with juz/hizb/nisf, the rare sites, and the measured expectations (113 basmalah, 3,970/66 sifr words, 3 muanaqah pairs, 15 sajdah sites, 199 hizb rosettes) |
| `tools/build_annotations.py` | per-page annotation graph → `.cache/annotations/NNN.json` (77 MB, derived, gitignored). Built from the pipeline's own internal element records via a spy on `rewrite()`, plus the eid map, so the graph can name the paths each record is drawn as |
| `tools/validate_annotations.py` | proves the graph and the SVG agree |

An annotation page record holds: the surahs on the page with their full card,
the divisions starting on it, every ayah with its juz/hizb/rubʿ/nisf, every word
with `wid` + uthmani + rasm + imlaei + qpc + its ligature texts, every **logical
mark** (one record however many paths draw it, with the eids it is drawn as),
and the relations — muanaqah, iqlab, sajdah, hizb (with its division numbers)
and ayah → marker.

### What the validator proves, mushaf-wide

1. **counting** — logical mark RECORDS == emitted MASTER paths, per name and per
   family, on every page. 436,706 records, 34 names, exact.
2. **references** — every eid a record names exists on its page; no eid claimed
   twice.
3. **words** — same `wid` set as the SVG, and matching uthmani / rasm / imlaei.
4. **metadata** — the surah card, the four division-start flags and the hizb
   rosette's rubʿ/nisf/hizb/juz read the same in the graph and in the SVG.
5. **relations** — muanaqah exactly 2 members; every iqlab relation names a
   `meem-iqlab`; sajdah signs 15 and overlines 15 mushaf-wide.
6. **vocabulary** — every emitted name is in the registry and active.
7. **markers** — the graph's medallion set equals the SVG's, page for page, no
   ayah closed twice on a page, 6,236 mushaf-wide.
8. **mushaf totals** — 199 rosettes, 30 juz starts, 114 surahs.

### Three things the build found on the way, all pre-existing

* **Six pages emit a whole banner line as marks.** p377, p418, p446, p507 and two
  others draw a surah-name line the DK header mapping did not claim, so its
  glyphs are classified as ordinary marks (19 of them on p377) rather than
  `header-ink`. Related to the 108-vs-114 surah-name group count. Not touched
  here; recorded so the graph and the SVG agree.
* **p379 and p480 split the sajdah compound.** The overline and the ۩ fall in
  different ayah polygons (27:24 vs 27:26; 41:37 vs 41:38), so the emitter
  already writes two `<g class="sajdah-mark">` groups. The graph mirrors that;
  the cardinality check moved to mushaf-wide totals (15 + 15) rather than
  pretend the per-site pairing holds.
* **Not every named element reaches the page as a mark.** Ink on a banner line
  emits as undecomposed `header-ink`, and HDRGUARD evicts a word's stolen title
  ink into the same group. Those elements never pass through `emit()` and so have
  no eid; the graph drops them, because a mark that is not drawn is not a mark.

---

## 8. What is not done

* **`data-imlaei` is still diacritic-bearing** (77,409 of 77,429 words). One line
  in the emitter if Abdullah wants both search attributes clean.
* **The rasm keeps ٱ, أ, إ, آ, ى, ة distinct** per his explicit ruling, which
  disagrees with the example in his own message. Flagged in §1; one line to
  change.
* **Phase 1 is additive only.** `data-role`, `data-mark-ids`, `data-relation-ids`,
  the root contract and the two profiles are phase 3 (`attr_schema_v3.md`), and
  the annotation cache is not yet wired as the audits' shared structural cache
  (docs/TASKS.md item 3) — the dump exists, the invalidation key does not.
* **The bench p1/p2 coverage regression is open** and belongs to the concurrent
  opening-page change (§5).
