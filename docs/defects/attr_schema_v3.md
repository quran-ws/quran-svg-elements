# Schema v2 adoption plan (attr_schema_v3)

Status: **v2 ADOPTED** (Abdullah, 2026-08-28). The external proposal
(`svg_annotation_schema_v2_proposal.md`) is the target schema. This document is
not a merge and not a counter-design: it is the plan that lands v2 in THIS repo
without breaking a single audit, baseline, or the live review loop. It
supersedes `docs/defects/attr_schema.md` as the design of record; that file
stays as history (its section 2b resurfaces in the escalations below).

Everything not listed under section 5 (ESCALATIONS) is adopted exactly as v2
specifies. Design only — no code changed by this document.

---

## 1. What v2 changes here — requirement → the code/data it touches

| v2 requirement | current reality | exact touch points |
|---|---|---|
| Root contract (`data-schema/-version/-profile/-edition/-page/-text-digest`, §5) | bare `<svg>` from the artwork | `rewrite()` page assembly in `tools/assign_words.py`; digest computed over the composite text source (rasm_uthmani + KFGQPC waqf + DK budgets — see §4.1 below) |
| `data-role` replacing `data-kind`; `body`→`letter` (§6.2) | `emit()` writes `data-kind` at assign_words.py:2094; `ALLOWED_KINDS` audit_taxonomy.py:49 | emit() string; audit_taxonomy whitelist; `tools/build_variants_page.py`, `scratchpad/color_words.py`. **Internal** `e["kind"]` vocabulary is NOT renamed in the bridge phases — `scratchpad/audit_marks.py`, `audit_intervals/width/marksize`, `score_confidence` all select on the internal records, not the SVG, so they stay untouched until phase 4 |
| `data-role="letter_dot"` + `data-dot-count` (§6.2, §11.2) | dots emit as `data-kind="mark" data-mark="dot|two_dots|three_dots" data-mark-family="dots"` | emit() + `_MFAM` :2079; dot-count is mechanical from the current name. TEXT_WANT budgeting of dots is internal-record–based and unchanged through the bridge (v2 §6.2 itself licenses a combined processing bucket) |
| Logical marks + `data-mark-ids`/`data-marks`; fused = several records on one path; split = one record on several paths; **count records, never paths** (§7) | master + `data-mark-part` (counts through master) + `data-fused="1"` (emit:2109, 2123) | new sidecar builder (phase 1); emit() dual-emission (phase 3); `audit_pixels.py` compound gate :82 extended to forbid `+`/`,` inside `data-marks` tokens; `build_variants_page.py:118` reads `data-mark-part` |
| Relations replacing `data-pair`/`data-iqlab`/proposed `data-unit` (§8) | `data-pair` (emit:2119, audit_taxonomy:140-159 exactly-2 gate), `data-iqlab` (emit:2121, display-only), sajdah linkage only via the `<g>` (split pass ~6738-6780) | relation records in the sidecar; `data-relation-ids` on paths in phase 3; audit_taxonomy pair check becomes per-relation-type cardinality. Iqlab subtype source: `_tanwin_iqlab` at ~10117 |
| Taxonomy registry; no emitted `data-mark-family` (§9) | `_MFAM` table emit:2074-2084; whitelist audit_taxonomy:131; the family attr is ONE DAY old, only audit_taxonomy reads it — cheapest retirement in the whole plan | new `.cache/schema/mark-taxonomy.v2.json`; `_MFAM` becomes a registry load; family attr dropped at phase 4 |
| `data-placement` / `data-arrangement` axes (§12) | `data-form` = tanwin-only `stacked|staggered` (emit:2117, ALLOWED_FORM :56). Seen above/below and meem high/low are NOT emitted today (see correction C2) | emit(); audit_taxonomy :134-139; seen sites keyed by `rare_places.json` rows (data, not code); meem placement from the `HARAKAH` table :1548 (ۢ above ×510, ۭ below ×99) |
| `waqf` removed as canonical name (§11.4) | `waqf` is (a) the fallback when neither `waqf_types()` (sig) nor `waqf_places()` (place) resolves a subtype (emit:2100-2107) and (b) the TEXT_WANT budget key for the five waqf codepoints. imalah/ishmam/tashil/saktah/seen_al_qiraah are ALREADY split-out canonical names (audit_marks TEXT_WANT + RARE_SITES; audit_taxonomy ALLOWED_MARKS) — v2's claim they still hide in `waqf` is stale (correction C4) | residue measurement in phase 0 (escalation E3); waqf family-level budgets stay per the 424/4,416 edition-disagreement rule — v2 §16.5 permits exactly this |
| Provenance → diagnostic sidecar, no `data-named-by` (§14) | never emitted (was proposal-only); the sig-vs-place branch lives at emit:2100-2104; recovery passes `QSVG_SUP`/`QSVG_SUFFIX` | resolution records in the diagnostic sidecar only. Zero public-SVG cost |
| Review split: shape / semantic / segmentation / state (§15) | one-label-per-sig `labels.json` (4,112 entries) + per-occurrence `eid_flags.jsonl` + `decisions.jsonl`/`sig_labels.jsonl`; served by `tools/review_server.py`, `build_variants_page.py`, folded by `apply_labels.py` (refuses composite collapse) | phase 2. The central rule is PROVEN here: tonight the mushaf-wide table label for the small_noon dot leaked onto the jeem-sign dot because the shapes are shared — exactly "a signature must never by itself determine the semantic mark" |
| Sig: one canonical full length (§16.1, §18 P0) | **stored 16 hex** (all 4,112 labels.json keys measured), displayed 12; at least one code path compares on `[:12]` (assign_words.py:8169 `_SUF_SIG`) | canonical = 16; inventory and fix every `[:12]` comparison in phase 0/3; UI truncation stays presentation-only |
| Edition manifest (§5, §13, §16.5) | constants baked into audit_taxonomy (SIFR word counts 3,970/66, rare-site table, 113-basmalah expectation implicit) and audit_marks (RARE_SITES) | new `.cache/schema/edition-hafs-kfgqpc.json`; audits load it instead of literals; the "one basmalah per surah start except 9, one surah-name per surah, no data-marks inside" law becomes manifest-driven validation |
| Two profiles, public + diagnostic (§4) | one output | profile switch in `rewrite()`; both must pass `audit_pixels` identically (v2 §16.1 demands identical visible pixels — our audit already proves this property page-wide) |

---

## 2. Rollout — v2 §18 made concrete for this repo

Every phase ends with every existing audit green. Where v2 retires an attribute
an audit reads, the old attribute keeps being emitted until the phase that
flips that audit's reader (dual-emission bridge).

### Phase 0 — freeze and measure (no code changes)

- Pin the current sweep as the v1 freeze: `.cache/sweeps/<v1-freeze>` via
  `full_sweep.py 1 604`; keep `tools/_pipeline_baseline.py` as-is.
- Record: pixel proof (`audit_pixels` 1-604), vocabulary census
  (audit_taxonomy's `marks_seen`), logical budgets (audit_marks totals).
- Measure the `waqf` residue: count emitted `data-mark="waqf"` sites where
  neither sig nor place resolved a subtype (grep the rebuilt pages). Feeds E3.
- Inventory every `[:12]` sig comparison (`grep -n '\[:12\]' tools/`) and
  declare canonical length 16.
- Gate: `bench.py` (no failures, pixelfail 0), `audit_pixels 1 604`,
  `audit_taxonomy 1 604`, `cmp_full` vs pinned baseline — all unchanged by
  definition.

### Phase 1 — registry, edition manifest, annotation graph (additive)

- New: `.cache/schema/mark-taxonomy.v2.json` (canonical names, categories,
  allowed features, aliases per v2 §9/§11), `.cache/schema/edition-hafs-kfgqpc.json`
  (pages, 113 basmalah expectation, waqf FAMILY budget, sajdah sites, rare
  sites, sifr word counts), `tools/build_annotations.py` (builds per-page
  logical-mark + relation records from the pipeline's internal element records
  — master/part/fused/pair/iqlab/sajdah-key — the same records `emit()` reads),
  `tools/validate_annotations.py` (v2 §16.2-16.5).
- Edit: `tools/assign_words.py` gains an env-gated structured dump beside the
  existing `QSVG_EIDMAP` hook (:2046) — zero SVG-byte change.
- Prove: logical mark counts == current master-path counts, family by family,
  mushaf-wide; relation cardinalities (waqf_al_muanaqah 2, sajdah line+sign, iqlab by
  subtype) hold on all pages.
- Files: 4 new, 1 edited.
- Gate: phase-0 list unchanged (emitted SVG is byte-identical), plus
  `validate_annotations 1 604` green.

### Phase 2 — review semantics split (tooling + data migration, no emission change)

- New: `tools/sig_conflicts.py` — signatures occurring under conflicting
  textual/positional expectations (the small_noon/jeem-dot class); its output
  BLOCKS mushaf-wide semantic propagation for those sigs.
- Edit: `tools/review_server.py`, `tools/build_variants_page.py`,
  `tools/apply_labels.py` / `apply_review_edits.py` — four decision layers
  (shape, semantic, segmentation, workflow state per v2 §15); segmentation
  values (`letter`, `letter_dot`, `header_ink`, …) never offered beside
  semantic names; workflow states never stored as taxonomy values.
- Data migration (backed up first, append-only preserved): `labels.json`,
  `decisions.jsonl`, `sig_labels.jsonl`, `eid_flags.jsonl` classified into the
  layers. Non-conflicting sig labels remain valid as shape+semantic in one
  step; only conflict-listed sigs demand occurrence-level re-review.
- Files: 1 new, ~4 edited, 4 caches migrated.
- Gate: `label_bisect.py` sample after migration (no flag increase), bench,
  audit_taxonomy; the live review campaign's timing is escalation E6.

### Phase 3 — dual emission (v1 attrs + v2 attrs + sidecar)

- Edit `emit()` / `rewrite()` in `tools/assign_words.py`: root contract attrs;
  `data-role` BESIDE `data-kind`; `data-mark-ids`/`data-marks` BESIDE
  `data-mark`/`data-mark-part`/`data-fused`; `data-relation-ids` BESIDE
  `data-pair`/`data-iqlab`; `data-placement`/`data-arrangement` (new
  information — nothing to dual-emit except tanwin, which also keeps
  `data-form` for the window); JSON sidecar per page (diagnostic profile).
- Edit `tools/audit_taxonomy.py`: validate BOTH vocabularies; per-relation
  cardinality; per-mark feature legality from the registry; manifest-driven
  counts.
- Edit `tools/audit_pixels.py`: compound gate extended — no `+` in any
  `data-marks` token, every `data-mark-ids`/`data-relation-ids` reference
  resolves.
- Files: 3 edited.
- Gate (the heavy one): bench, `audit_pixels 1 604` (attributes only — pixel
  identity must be untouched), `audit_taxonomy 1 604`, **`full_sweep` +
  `cmp_full` flag-identical to the phase-0 freeze** (flag records must not
  move: this phase adds attributes, it does not re-decide ownership),
  variants page renders, review server serves.

### Phase 4 — v2 public profile, retire v1 attrs

- Flip the SVG-attribute readers to v2 selectors: `audit_taxonomy.py`,
  `build_variants_page.py`, `review_server.py`, `audit_pixels.py` regex,
  `scratchpad/color_words.py`. (audit_marks/intervals/width/marksize/
  score_confidence read internal records; they change only if the internal
  `kind` vocabulary is renamed — a separate, optional cleanup with its own
  measured gate.)
- Stop emitting `data-kind`, `data-mark`, `data-mark-part`, `data-fused`,
  `data-pair`, `data-iqlab`, `data-mark-family`, tanwin `data-form`.
- **Re-pin the sweep baseline exactly once** at this boundary, only after a
  dual-emit sweep has proven flag-identity (escalation E4 governs the
  mechanics).
- Files: ~5 edited, 1 baseline re-pin.
- Gate: the full phase-3 list, run against the NEW baseline, plus one
  eyes-on-page session with Abdullah on the variants flow before v1 emission
  is deleted.

---

## 3. Corrections — required amendments to v2 (factual conflicts only)

- **C1 — §11.2 small_noon.** "add the currently missing occurrence after
  visual verification": it is not missing. The 21:88 small_noon (p329) is
  emitted and permanently gated — audit_taxonomy fails the mushaf run if the
  site is ever absent (audit_taxonomy.py:242), and TEXT_WANT budgets ۨ.
  Amend to "already present and audit-gated".
- **C2 — §17 migration map sources that do not exist.** The rows
  `data-form="stacked|staggered"` → arrangement is real; but
  seen `data-form="above|below"` and meem `data-form="high|low"` were never
  emitted — they exist only in the in-house PROPOSAL. Current emission carries
  no placement axis at all (audit_taxonomy:138 rejects `data-form` on anything
  but tanwin). Amend those rows to "nothing → `data-placement`", populated
  from `rare_places.json` rows (seen) and the `HARAKAH` table (meem, ۢ×510
  above / ۭ×99 below).
- **C3 — §18 P0 sig length, confirmed and sharpened.** v2's catch is right and
  is now measured: all 4,112 `labels.json` keys are 16 hex; 12 is display
  truncation. Amendment: the migration surface also includes code that
  COMPARES on the truncation — at least `assign_words.py:8169`
  (`(sig)[:12] in _SUF_SIG`) — so phase 0 must inventory `[:12]` matches, not
  just documentation.
- **C4 — §11.4 scope of the `waqf` removal.** "saktah / seen_al_qiraah /
  imalah / ishmam / tashil ... replace contextual `waqf`" describes a state
  this repo has already left: all five are canonical names today
  (ALLOWED_MARKS; TEXT_WANT budgets them at their single sites, place-gated by
  job — U+06DC is saktah×5 / seen×2, U+06EC is ishmam at 12:11 and tashil at
  41:44). What `waqf` still names is only (a) the unresolved-subtype waqf
  fallback and (b) the family-level budget key. Amend the section to target
  that residue — and note the removal cannot be unconditional while the
  editions disagree on WHICH waqf sign at 424/4,416 positions (family budgets
  stay, per v2's own §16.5).
- **C5 — §7.1/§6.1 stable occurrence identity is missing.** v2 correctly says
  eids must not anchor persistent review decisions across regenerations, but
  offers no replacement key — and the live review writes `eid_flags.jsonl`
  keyed (page, eid) tonight. The repo's proven answer is geometry keying
  (`build_overrides.py`, `waqf_places.json` both key on rounded bbox and
  survive pipeline changes). Amendment: the annotation graph needs a
  persistent occurrence key; see escalation E1 for the choice.

---

## 4. v2 §19 open decisions — recommendation each, for this repo

1. **Standalone SVG + embedded metadata vs SVG + JSON sidecar → sidecar.**
   Every tool here is file-based and diff-driven; a per-page sidecar diffs in
   review, keeps the SVG small for the pixel/raster tooling, and lets the
   public SVG stay attribute-only. Embedded `<metadata>` can be a later
   flag on the same builder if a consumer demands one file.
2. **`data-sig` in public output → yes during the compatibility window, then
   diagnostic-only.** The whole live review loop (review_server, variants,
   label_sheet, apply_review_edits, sig_scan) keys on it; dropping it from
   public before the review campaign ends breaks the loop for zero gain.
   Full 16-hex wherever emitted.
3. **`waqf_mamnu` token → reserve, do not activate.** This print emits no لا
   sign (ALLOWED_WAQF is the five-value set and audit_taxonomy holds it).
   Keep the token reserved in the registry with `active: false`; final
   scholarly token is Abdullah's call when a لا edition is ever ingested.
4. **Singleton category assignments → adopt v2's table as registry-only
   fields.** They are never emitted (no `data-mark-family` in v2 public), so
   the cost of a later re-categorization is one registry edit; take
   `small_meem: dabt` etc. as written and move on.
5. **Compatibility window for `data-mark`/`data-waqf`/master-part → event-
   gated, not calendar-gated.** Dual-emit from phase 3; retire v1 only after
   (a) every reader in the phase-4 list is flipped, (b) one full dual-emit
   sweep is flag-identical to the freeze, and (c) one Abdullah eyes-on
   review session runs clean on v2 selectors. `data-waqf` is already legacy
   (subtype lives in `data-mark`); its fallback readers (`refdb.py`,
   `waqf_places.py`) retire in the same commit that flips them.

---

## 5a. RULINGS (Abdullah, 2026-08-28 22:28)

All six escalations decided **as recommended**: E1 geometry occurrence key ·
E2 header eids adopted (role, no marks) · E3 waqf blocks public until residue
zero · E4 one clean baseline re-pin after proven flag-identity · E5 the live
review campaign continues uninterrupted · E6 the letter_dot bridge seam is
blessed (emitted role flips, internal counting projects until its own
measured cleanup).

Profile decision (resolves v2 §19.1-19.2): TWO artifacts from one graph —
the **dev SVG** (diagnostic profile: data-eid, data-sig, provenance, dot
detail, everything reviewable) and the **production SVG** (public profile:
lean; dev-only attributes removed or combined into the logical layer; exact
final attribute cut decided at phase 4 design, reviewed by Abdullah).

## 5. ESCALATIONS — for Abdullah's decision

Nothing here is decided by this plan. Everything below is either a gap in v2
that this repo must fill, or an in-house position defensible on this repo's
evidence. Everything NOT listed here is adopted per v2.

- **E1 (v2 misses it): what is the persistent occurrence key?**
  Question: when the graph replaces eids as the durable identity, what keys a
  reviewed occurrence across regenerations?
  Options: (a) geometry key — rounded bbox, the convention `build_overrides.py`
  and `waqf_places.json` already use and that has survived every pipeline
  change; (b) (page, mark-ordinal within word) — human-readable but re-numbers
  whenever ownership repairs move a mark.
  Recommendation: (a) geometry key as the graph's occurrence id, eid stays
  artifact-local — it is the only key in this repo with a proven survival
  record.

- **E2 (v2 vs a one-day-old ruling): eids inside header groups.**
  Question: v2 §13 requires every path inside `surah-name`/`basmalah` to carry
  a `data-eid`; the one-item law (Abdullah, 2026-08-28 morning, emit:2163-2170)
  deliberately emits header ink PLAIN — and our own section 2b wanted header
  eids too, after the p453 waqf_al_muanaqah dots hid un-referenceable inside a
  basmalah group.
  Options: (a) adopt v2 — eid + `data-role="header_ink"` per path, still no
  `data-marks` inside headers (referenceable without being decomposed);
  (b) keep the one-item law byte-for-byte and reference header ink only
  through the group.
  Recommendation: (a) — it serves the p453 lesson and does not violate the
  SPIRIT of the one-item law (no semantic decomposition) — but it reverses the
  letter of a ruling Abdullah made yesterday, so it is his call.

- **E3 (ours is defensible on residue): when does `waqf` actually die?**
  Question: emit() still falls back to `data-mark="waqf"` when neither the
  sig table nor the place table resolves a waqf subtype; the residue count is
  unmeasured.
  Options: (a) block the v2 public profile until residue is zero (label the
  remaining sigs/places, the existing waqf_types/waqf_places machinery already
  does this); (b) let v2 public ship with `waqf` as a documented legacy alias.
  Recommendation: (a) — v2 §16.4 forbids emitting legacy aliases, and the
  residue is likely small (the sig table already names the overwhelming
  majority); measure in phase 0 before promising a date.

- **E4 (ours is defensible on evidence): sweep-baseline continuity.**
  Question: the flag-record baselines in `.cache/sweeps` are the project's
  entire regression memory; phase 4's selector flip forces a baseline event.
  Options: (a) re-pin once at the phase-4 boundary, only after a dual-emit
  sweep proves flag-identity with the freeze; (b) translate old baselines
  into v2 vocabulary so history stays comparable.
  Recommendation: (a) — the repo's own history (the pause-budget correction
  made old baselines "not comparable to today's") shows a clean re-pin with a
  proven-identical build is safer than a translated history nobody re-verifies.

- **E5 (ours is defensible tonight): the live review campaign during phase 2.**
  Question: Abdullah is actively reviewing on the variants+eye flow tonight;
  phase 2 rebuilds that tool and migrates its caches.
  Options: (a) keep the campaign running on the v1 flow — its records are
  append-only (`decisions.jsonl`, `eid_flags.jsonl`), so migration can absorb
  them whenever it lands, and the UI flips between campaigns; (b) waqf the
  campaign until the split-decision UI exists, so no decision is captured in
  the layer-ambiguous v1 form.
  Recommendation: (a) — the append-only design was built for exactly this,
  and the sig-conflict detector can be run FIRST as a standalone tool so
  tonight's known leak class (small_noon dot ↔ jeem-sign dot) is fenced even
  before the UI changes. Timing is Abdullah's.

- **E6 (v2 misses the counting seam, we can defend the bridge): letter_dot
  role vs the counting audits.**
  Question: v2 demands dots stop being semantic marks; every counting audit
  (audit_marks TEXT_WANT, marksize, intervals) budgets dots against the text
  exactly like diacritics, and the sweep baselines encode that.
  Options: (a) the bridge in this plan — emitted role changes at phase 3/4,
  internal `kind` vocabulary and TEXT_WANT buckets unchanged (v2 §6.2
  explicitly permits a combined processing bucket), internal rename deferred
  to its own measured cleanup; (b) rename internal and emitted together at
  phase 4 and re-key TEXT_WANT/baselines in one motion.
  Recommendation: (a) — it keeps every audit green through every phase at the
  cost of one internal/external naming seam, documented in code; (b) is the
  big-bang this plan exists to avoid. Flagged because it means the "semantic
  layer" v2 wants is, internally, a projection for a while — Abdullah should
  bless that explicitly.
