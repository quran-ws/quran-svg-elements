# Making the data mushaf-aware, before the second edition ships

Internal design note, 2026-08-30. **Not for the demo or the public docs.**

Hafs is first, but four more editions already exist upstream at 604 pages each:
`douri`, `qalon`, `shubah`, `warsh`. Everything below is what has to change so
the second edition is a configuration rather than a rewrite — and, more
importantly, so the **files we ship for Hafs today are still correct** once they
sit beside four siblings.

The cheapest moment to fix an identity model is before anything depends on it.

---

## 1. The identity is a triple, and we currently record none of it

A page belongs to **(qiraa, riwaya, edition)**. Upstream's `tools/qiraat_map.py`
already states the mapping for the five:

| directory | qiraa | rawi |
|---|---|---|
| `hafs` | `asim` | `hafs` |
| `shubah` | `asim` | `shuba` |
| `warsh` | `nafi` | `warsh` |
| `qalon` | `nafi` | `qalun` |
| `douri` | `abu-amr` | `duri` |

**The directory name is the riwaya, not the qiraa.** Hafs and Shuʿba are two
transmissions of the same reading (ʿĀṣim); Warsh and Qālūn likewise (Nāfiʿ). A
schema that records only "hafs" cannot answer "show me both transmissions of
ʿĀṣim", and one that calls it a *qiraa* is simply wrong.

The third element is the **edition** — here the King Fahd Complex printing. The
same riwaya printed by another publisher is a different artefact with different
page breaks, so `hafs` alone never identifies a page.

**Today a page file says nothing at all about which mushaf it is.** Download
`042.svg` on its own and it is unidentifiable. That is the first thing to fix.

### Proposed: the root `<svg>` carries the identity

Every value below comes from the vendored `quranpedia/qiraat-ayah-map` dataset
(`tools/data/qiraat-ayah-map/`), which gives Arabic and English names for all
ten qiraat, their rawis, and the counting systems. **Nothing here is invented.**

    data-mushaf="hafs-kfqc"              the directory/bundle key
    data-qiraa="asim"
    data-riwaya="hafs"
    data-edition="kfgqpc-1441"
    data-riwaya-name-ar="حفص عن عاصم"    the conventional name: rawi عن qiraa
    data-riwaya-name-en="Hafs 'an Asim"
    data-ayah-numbering="kufi"           see §2 — must be explicit
    data-ayah-total="6236"               a PROPERTY of the counting system
    data-decomposition="word"            how far this edition is decomposed
    data-page="42"

Ten attributes on one element per page. 604 elements in the whole corpus, so
the size cost is nil, and every file becomes self-describing: a page downloaded
on its own can say what it is, in both languages, without fetching anything.

**Ids on the page, full records in `catalogue.json`.** Do not repeat the
descriptions, the transmission notes or the counting-system prose on 604 pages.
The page carries stable machine ids plus the one display string a consumer
actually renders; the catalogue carries the rest — `name_ar`/`name_en` for the
qiraa, the rawi and the counting system, the totals, the descriptions, and the
provenance of the numbering choice (§2).

### Editions ship at different DEPTHS, and the file must say which

**Abdullah, 2026-08-30: until every mushaf is released, the README and the
structure must say which editions are ayah-level and which are v2-ready.**

Two depths exist and will coexist for some time:

| `data-decomposition` | what the file holds | which editions |
|---|---|---|
| `ayah` | page ink, ayah polygons and markers; nothing below the ayah | what `quranpedia/quran-svg` publishes today |
| `word` | every word, ligature and named mark addressable | Hafs, from this pipeline |

**Put it on the page, not only in the catalogue.** A consumer holding one file
must be able to ask what it contains. The alternative is inferring depth from
which mushaf it is — which breaks the day an edition is upgraded — or from
whether a `querySelector('g.word')` happened to return null, which cannot
distinguish "this edition is ayah-level" from "this page failed to load".

Consequences to carry through:

- **`catalogue.json` lists the depth per edition**, so a consumer can choose what
  to fetch before fetching it.
- **The README states it in a table**, prominently. Someone arriving expecting
  word-level Warsh should learn that in the README, not from an empty selector.
- **The library degrades honestly.** `page.words()` on an ayah-level file should
  say the edition is ayah-level, not return an empty array — an empty array is
  indistinguishable from a bug.
- **Upgrading an edition changes this value**, and that is a version bump for
  that edition alone. It is not a breaking change: `ayah` -> `word` only adds.

### The ayah total is not a constant

`counting-systems.json` gives a different total per system:

| system | total | used by |
|---|---:|---|
| `kufi` | 6,236 | ʿĀṣim, Ḥamza, al-Kisāʾī, Khalaf |
| `madani-last` | 6,214 | Nāfiʿ |
| `basri` | — | Abū ʿAmr |

So **6,236 is a Hafs fact, not a Quran fact.** Warsh will have 6,214 ayah
markers, and `data-aid` values that do not exist in Hafs — and Hafs values that
do not exist in Warsh.

This is already hardcoded in our tooling: `validate_annotations.py` asserts
6,236 ayah markers and 114 surahs. The surah count is safe; the ayah count is
not. It must come from the edition's declared counting system before a second
mushaf is validated, or the validator will report a correct Warsh build as
broken.

---

## 2. The ayah numbering system is a property of the EDITION, not the qiraa

This is the subtle one, and upstream has already been bitten by it.

The ten qiraat do not agree where every ayah ends, so `data-aid="37:5"` denotes
**different ink in different mushafs**. A consumer joining our data to an
external ayah database gets silently wrong results unless the counting madhhab
(نظام العد) is known.

The tempting model is to derive it: qiraa → counting system, which is what
`qiraat.json` does (`nafi` → `madani-last`, `abu-amr` → `basri`, and so on).
**That model is wrong, and the al-Dūrī edition proves it.** From upstream's own
note:

> This King Fahd Al-Duri edition says otherwise in its own colophon ("huwa
> al-maʿruf bi-l-ʿadad al-awwal li-ahl al-Madinah"), and the pages agree:
> against First Madinan they match in **110 of 114** surahs, against Basran in
> **72**.

So the printed edition declares its own count, and it is not the one its qiraa
would imply. Deriving would have mislabelled 604 pages.

**Therefore `data-ayah-numbering` must be an explicit, per-edition field**,
recorded from the edition's colophon and verified against its pages — never
computed from the qiraa. Store the evidence alongside it.

Note also that four surahs (37, 67, 80, 81) remain genuinely unsettled in ʿilm
al-fawāṣil. Those are reported, not hidden. Our schema should be able to say
"disputed" without pretending to a precision nobody has.

---

## 3. `data-wid` is not portable across mushafs

The riwayat differ in orthography, in word segmentation, and — via §2 — in ayah
boundaries. So word counts differ, and `2:255:4` in Warsh is not necessarily
`2:255:4` in Hafs.

Consequences:

- **A word id is only meaningful within one mushaf.** Any cross-mushaf reference
  needs the mushaf key: `hafs-kfqc/2:255:4`. Decide this now, because the moment
  a second edition ships someone will try to join them.
- **Do not add a "same word across riwayat" link yet.** It is a real research
  problem (the alignment is not one-to-one), and inventing a half-correct
  mapping is worse than offering none. If it is wanted later it belongs in a
  separate alignment dataset, not in the page files.
- The library's atlas, the search index and the word/box files are all
  **per-mushaf**. None of them may be shared.

---

## 4. Folder structure

Mirror upstream, which already solved this, and put the mushaf key at the top:

    <root>/
      catalogue.json                     the list of available mushafs
      mushafs/
        hafs-kfqc/
          VERSION.json                   identity + counts + artwork commit
          pages/001.svg … 604.svg
          index/…                        pages, surahs, words, word-boxes, atlas
          schema/FORMAT.md
        warsh-kfqc/
          …
      schema/
        mark-taxonomy.json               the SHARED core — see §5
        *.schema.json

`catalogue.json` is what a consumer fetches first: which editions exist, their
identity triples, their counting systems, their page counts, their versions.
Without it, discovering the second edition means guessing a URL.

**Version each mushaf independently.** Warsh will be corrected on its own
schedule; a single global version number would force meaningless bumps and make
"what changed" unanswerable.

---

## 5. The mark taxonomy is shared core plus per-mushaf extension

Hafs emits 35 mark names. Warsh will not emit the same set — it has signs Hafs
does not use, and vice versa.

So: a shared registry of every mark the project knows, and a per-mushaf
declaration of which subset that edition actually uses. Two rules follow:

- **The taxonomy audit must not hardcode Hafs's names.** `audit_taxonomy.py`
  currently validates against a fixed set; it needs to read the edition's
  declared subset. Same for the family list — which, as of tonight, is a
  space-separated token list, so per-token validation is already in place.
- **A name means the same thing in every edition.** If Warsh needs a distinction
  Hafs lacks, add a name to the shared registry; never redefine an existing one
  per mushaf. That is how a taxonomy rots.

---

## 6. What in the pipeline is Hafs-specific

Established earlier and still true: the pipeline ports, but three inputs do not.

- **The word/text source.** Budgets come from the DigitalKhatt DB, keyed to this
  Hafs text. Each riwaya needs its own verified source, and the ground rule
  stands: never hand-type Quranic text.
- **The mark label table** (`.cache/marks/labels.json`) maps shape signatures to
  labels. Signatures are per-artwork; Warsh needs its own table, and applying
  Hafs's would be a silent corruption of hundreds of marks at once.
- **The geometry-keyed overrides** (270 of them) are facts about places in the
  Hafs artwork. They must be namespaced per mushaf, or they will match
  coordinates in another edition by accident. **This is a live risk today** —
  check the override key format before Warsh is built.

Everything else — the line cut, the emitter, the audits, the pixel gate — is
edition-agnostic and should stay that way.

---

## 7. What to change now, while only Hafs exists

Cheap now, expensive later:

1. **Put the identity on the root `<svg>`** (§1). Six attributes; makes every
   shipped file self-describing. Do this before publication.
2. **Record `data-ayah-numbering` explicitly** (§2), with its evidence, and never
   derive it.
3. **Namespace the overrides and the label table by mushaf** (§6) before a second
   edition can collide with them.
4. **Put the mushaf key in the bundle path** (§4) even while there is one mushaf,
   so no consumer hardcodes a path that has to change.
5. **Add `catalogue.json`** with a single entry. A one-entry catalogue costs
   nothing and means the second edition needs no new concept.
6. **Make the taxonomy audit read the edition's declared name set** (§5).
7. **Drive the ayah total from the counting system, not a literal.**
   `validate_annotations.py:268` asserts `nmark != 6236`. That is true for Hafs
   and false for Nāfiʿ (6,214), so the validator would fail a correct Warsh
   build. Cheap to fix now, confusing to debug later.

Deliberately NOT now: cross-riwaya word alignment (§3), and any attempt to model
the disputed fawāṣil beyond recording "disputed".

---

## 8. The one thing that would be hardest to undo

If Hafs ships without the identity attributes and the mushaf key in the path,
consumers will write code that assumes there is exactly one mushaf and that a
word id is globally unique. Both assumptions become wrong the day Warsh ships,
and by then they are someone else's code.

Everything else in this note can be added later. That part cannot.
