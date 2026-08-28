# SVG attribute schema — current state and proposal

Design doc only (2026-08-28). No code changed. Companion to
`docs/defects/mark_taxonomy.md`; vocabulary enforced by `tools/audit_taxonomy.py`;
emission lives in `emit(e)` inside `rewrite()` (`tools/assign_words.py` ~2077).

Hard constraints honoured throughout: pixel identity (attributes/grouping only);
no `+` compound names; one mark = one countable unit (`data-mark-part` counts
through its master); waqf budgets stay FAMILY-level (the editions disagree on
WHICH sign at 424/4,416 positions); human review data stays in `.cache`.

---

## 1. Current schema

### Path-level (`<path>`)

| attribute | values | meaning |
|---|---|---|
| `data-eid` | `e1…eN` per page | element id, emission order |
| `data-kind` | `body` `mark` `header-ink` `ornament` `ayah-marker-ornament` `ayah-number` | what layer of the artwork this ink is |
| `data-mark` | ALLOWED_MARKS (audit_taxonomy.py:39) — harakat, tanween, dots, waqf subtypes, rare signs, sifrs, sajdah split, `hizb` | the SPECIFIC sign, master outline only |
| `data-mark-part` | same vocabulary | welded member; counts through its master (same name) |
| `data-mark-family` | `waqf` `tanween` `dots` `sifr` `sajdah` `reading-sign` | only on subtyped families (`_MFAM`, assign_words.py:2065) |
| `data-sig` | 12-hex shape signature | one labelling decision mushaf-wide (`labels.json`) |
| `data-form` | `stacked` `staggered` | tanween pair arrangement only (geometry, `_TAN_STAG`) |
| `data-pair` | `mnq-S-A-N` | muanaqah partner id, exactly 2 per id |
| `data-iqlab` | `iq-S-A-P` | iqlab unit id linking small م with its haraka (tanween iqlab) or alone (noon iqlab) |
| `data-fused` | `1` | one outline that carries two marks and cannot be cut |
| `data-standalone` + `data-surah`/`data-ayah` | `1`, ints | sign between words (hizb, sajdah) |
| `transform` | matrix | frame compensation for cross-path emission — never semantic |

### Group-level (`<g>`)

| group | attributes |
|---|---|
| `class="ayah"` | `data-surah` `data-ayah` |
| `class="word"` | `data-surah` `data-ayah` `data-word` `data-uthmani` `data-imlaei` `data-qpc` |
| `class="ligature"` | `data-text` (joining-rule segment) |
| `class="surah-name"` / `"basmalah"` | `data-surah`; interior paths are one-item `data-kind="header-ink"` |
| `class="hizb-mark"` / `"sajdah-mark"` | `data-mark` (family name), `data-surah` `data-ayah` |
| `class="ayah-marker"` | (medallion wrapper) |

---

## 2. Proposed schema

Principle: **an attribute appears exactly when it adds information the reader
cannot get from the mark name or the enclosing group.** Family = a real group of
distinct names that count together; form = a variant of one name; unit = ink in
several outlines that means one thing; named-by = where the name came from.

| attribute | values | carried by | example | change |
|---|---|---|---|---|
| `data-eid` | `eN` | every decomposed path | `e214` | none |
| `data-kind` | as today | every decomposed path | `mark` | none |
| `data-mark` / `data-mark-part` | as today | master / welded member | `waqf-jaiz` | none |
| `data-mark-family` | `haraka` `tanween` `letter-dots` `small-letter` `waqf` `sifr` `sajdah` `reading-sign` | every mark in a multi-name family | fatha → `haraka` | ADD haraka + small-letter; RENAME dots→letter-dots; singletons (shadda, sukun, maddah, hamza, wasla, meem-iqlab, hizb) stay bare |
| `data-form` | per-mark legal sets: tanween `stacked\|staggered`; seen-reading `above\|below`; meem-iqlab `high\|low` | the mark the variant belongs to | 52:37 seen → `below` | GENERALIZE (was tanween-only) |
| `data-unit` | `mnq-S-A-N` (2 members) · `iq-S-A-P` (1–2) · `sjd-S-A` (2+) | every member of a multi-outline semantic unit | both halves of a sajdah site → `sjd-32-15` | REPLACES `data-pair` and `data-iqlab`; ADDS sajdah ids |
| `data-unit-kind` | `noon-iqlab` `tanween-iqlab` | iqlab unit members only | 4:73:9 م → `noon-iqlab` | NEW |
| `data-named-by` | `sig` `place` `position` `text` | subtype-resolved marks (waqf, rare signs, recovered superscripts) | a waqf typed from `waqf_places.json` → `place` | NEW, scoped |
| `data-sig` | as today | any element with a signature | | none |
| `data-fused` | `1` | as today | | none |
| `data-standalone` + surah/ayah | as today | standalone sign paths | | none |
| word/ligature/ayah/header groups | as today | | | none |

### Decision: family on ALL marks? — No; family on all REAL families.

Putting `data-mark-family="fatha"`-style singletons on every mark makes 60%+ of
family values duplicate the mark name — pure noise, and every selector that
means "the subtyped families" breaks. But two real families are missing today:

- **haraka** (fatha, kasra, damma) — the pipeline treats them as one derived
  stroke family everywhere (`_POS_SWAP`, iqlab pairing pool); the output should
  say so. Tanween stays its own family (it counts differently: pair = one unit).
- **small-letter** (small-alef, small-waw, small-ya, small-noon) — one
  behaviour class (text-driven recovery, `_ABOVE_ONLY` exemptions).

Rule after the change: `data-mark-family` present ⇔ the family has ≥2 member
names. Consistent AND selectable, no noise.

### Decision: letter dots stay `data-kind="mark"`.

They ARE letter structure, not diacritics — the schema says so via
`data-mark-family="letter-dots"` (renamed from `dots`, which read as a
diacritic family). A `data-kind` split was rejected: every audit
(`audit_marks`, `audit_intervals`, `audit_marksize`, `score_confidence`)
selects marks by kind, and dots are budgeted against the text exactly like
diacritics; a kind split re-keys every budget and every sweep baseline for a
distinction the family attribute already carries at zero migration cost
(the family attr shipped today; only `audit_taxonomy.py:131` whitelists it).

### Decision: `data-form` is the one variant axis.

Legal values are gated PER MARK (audit_taxonomy extends its current
"form only on tanween" check to a `{mark: legal-forms}` table). No second
attribute (`data-pos`, `data-variant`) — one axis, closed sets.

### 2b. Headers — basmalah and surah names (added after Abdullah's review)

The agent's draft left the header groups "untouched"; they need three things:

| gap | fix | why |
|---|---|---|
| header-ink paths carry no `data-eid`/`data-sig` | every header path gets an eid (sig optional) | the ONLY ink that cannot be referenced from a review — the muanaqah dots hid inside a basmalah group and the p453 reports could not be pointed at |
| the Fatiha's basmalah IS ayah 1 but says only `data-surah="1"` | `data-ayah="1"` on that one group | the other 111 basmalahs are unnumbered openings; surah 9 has none |
| the one-item law is behaviour, not a gate | audit_taxonomy rules: exactly one basmalah group per surah start except surah 9; exactly one surah-name group per surah; NO `data-mark` inside either | Abdullah's law from 2026-08-28 morning, currently unenforced |

No text attributes beyond the number — surah names derive from `data-surah`;
hand-typing Quranic text is forbidden by the ground rules.

### Decision: one `data-unit` id, kind in the prefix.

`mnq-`/`iq-`/`sjd-` share one grammar: `<kind>-<surah>-<ayah>[-<word|n>]`.
Cardinality is checked per kind (mnq exactly 2 on a page; iq 1 for noon-iqlab,
2 for tanween-iqlab; sjd ≥2). The sajdah id closes today's gap: the
`sajdah-line` and `sajdah-sign` of one site share only a `<g>` today, and the
4/15 sites whose line spans two verses cannot be reassembled from the group
alone.

---

## 3. Newly-exposed details, and where the pipeline already knows each

| detail | new attribute/value | where it is known today (mechanical source) |
|---|---|---|
| iqlab kind: noon vs tanween | `data-unit-kind` | `assign_words.py` ~10117: `_tanween_iqlab = _ptx[_iqi-1] in _hset` (char before ۢ/ۭ); set it on `_m0`/`_h0` beside `iqpair` |
| open vs closed tanween | already `data-form` | geometry `tanform` ~9881, cross-checked 8,515/8,516 vs text U+08F0-08F2 (header comment ~35-45). No text attribute added: geometry is the print, and the one disagreement (p208 مُّبِينٌ) is resolved geometry-wins |
| seen-reading above vs below | `data-form="above\|below"` | the word's text codepoint: U+06DC (2:245 p39, 7:69 p159) vs U+06E3 (52:37 p525) — `rare_places()` ~943 keys the sites; add the form to `rare_places.json` rows (data, not code) |
| meem-iqlab high vs low | `data-form="high\|low"` | `HARAKA` table :1548 — ۢ→("meem-iqlab","a"), ۭ→("meem-iqlab","b"); catalog 510 high / 99 low; the low form is usually `data-fused` with its haraka |
| sajdah site linkage | `data-unit="sjd-S-A"` | the sajdah ejection/split pass ~6738-6780 already groups line+sign per (surah, ayah) key |
| waqf name source | `data-named-by="sig\|place"` | `emit()` :2085-2089 already branches `waqf_types()` (sig) vs `waqf_places()` (place fallback) — one line each branch |
| rare-sign / recovery provenance | `data-named-by="place\|text\|position"` | rare signs: `rare_places()`; superscript recoveries (`QSVG_SUP`/`QSVG_SUFFIX`): the recovering pass; slash names: `_POS_SWAP` = `position`. Scoped rollout: waqf + rare + recoveries first; blanket `position` on every fatha/kasra deferred (it is the default, so it carries little until a `sig`-table override exists for those) |
| hizb surah:ayah | none needed | already consistent: group `data-surah`/`data-ayah` + path `data-standalone` |

## 4. Migration notes — who reads what, what breaks

| attribute | consumers (grep 2026-08-28) | impact |
|---|---|---|
| `data-mark` / `data-mark-part` | `audit_taxonomy.py`, `build_variants_page.py`, `audit_pixels.py` (compound gate), `review-platform/index.html` | UNCHANGED — no name changes in this proposal |
| `data-mark-family` | `audit_taxonomy.py:131` whitelist only | rename `dots`→`letter-dots`, add `haraka`/`small-letter`: one whitelist edit + `_MFAM` edit. Attribute is one day old; no sweep baseline keys on it |
| `data-form` | `audit_taxonomy.py:134-139` (restricts to tanween) | replace the tanween-only check with the per-mark legal table. `ALLOWED_FORM` grows `above below high low` |
| `data-pair` | `audit_taxonomy.py:140-159` (exactly-2 check), `mark_taxonomy.md` | RENAMED to `data-unit`. audit_taxonomy: accept both during rollout, gate on `data-unit` after; cardinality becomes per-prefix |
| `data-iqlab` | no tool reads it (docs/variants page display only) | RENAMED to `data-unit` — free |
| `data-waqf` | `refdb.py`, `waqf_places.py`, `build_variants_page.py`, `audit_taxonomy.py:124` | already legacy (subtype moved into `data-mark`); those readers keep their fallback paths; no new break |
| `data-sig` | `review_server.py`, `label_sheet.py`, `build_variants_page.py`, `apply_review_edits.py`, `sig_scan.py` | untouched |
| word/ligature groups | review platform, all audits | untouched |

Sequencing: (1) `data-unit`+`data-unit-kind`+sajdah ids and the `data-form`
generalization (pure additions apart from two renames no tool reads);
(2) family extension + `letter-dots` rename with the audit_taxonomy edit in the
same commit; (3) `data-named-by`, waqf+rare scope first. Each phase gated by
`audit_pixels` (byte-level ink identity is untouched — attributes only),
`audit_taxonomy`, and a bench run. Site data (seen forms, rare provenance)
goes into `.cache/marks/rare_places.json` rows, never into code.

## 5. Rejected alternatives

- **Family on literally every mark** (`shadda`→`shadda`): duplicates the name,
  breaks "family attr ⇒ subtyping exists" selectors, adds ~40k noise attributes.
- **`data-kind="letter-dot"`**: re-keys every audit's mark selection and every
  sweep baseline for information `data-mark-family="letter-dots"` already carries.
- **Per-variant attributes** (`data-pos`, `data-seen-variant`, `data-meem-form`):
  three axes for one concept; `data-form` with per-mark legal sets is one gate.
- **Keeping `data-pair`/`data-iqlab` separate and adding `data-sajdah`**: three
  attributes with one meaning ("members of unit X"); the prefix already carries
  the kind, and `data-unit-kind` carries the one distinction ids cannot.
- **Carrier-letter attribute on each mark**: the enclosing `<g class="ligature"
  data-text>` IS the carrier statement; a per-letter index needs group-i =
  segment-i pairing, which is meaningless for the 2,455 words where the counts
  disagree (the `audit_ligatures.py` lesson) — it would manufacture defects.
- **Text-encoded open/closed tanween as a second attribute beside `data-form`**:
  8,515/8,516 agreement makes it redundant; the one conflict is already
  adjudicated geometry-wins.
- **Blanket `data-named-by` on all ~300k marks now**: for slash marks
  "position" is the universal default, so it discriminates nothing yet;
  emit it where the source genuinely varies (waqf, rare, recoveries).
