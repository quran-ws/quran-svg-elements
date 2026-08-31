# Word numbering: المقطوع والموصول, and how we defend each decision

Word ids (`data-wid="surah:ayah:position"`) are the pipeline's primary key —
audits, overrides, the line table and every consumer are keyed on them. So the
question "is this one word or two?" is not cosmetic, and each answer has to be
defensible from a source, not from a reading of the drawing.

This file defines what a word is here, the policy for defending that, and the
four sites where it bites.

---

## What a word IS here

**A word is the mushaf's word-by-word token — the unit the print's own V4 layout
marks.** Not the rasm's written token, and not the grammatical word.

This has to be said explicitly, because Arabic gives three different answers and
the project ran for a long time without naming which one it meant. Taking
`وَمَالِيَ` (36:22):

| definition | `وَمَالِيَ` | `بَعْدَ مَا` | matches us? |
|---|---:|---:|---|
| **rasm** — how it is written | 1 | 2 | no |
| **إعراب** — grammar: `و` + `مَا` + `لِـ` + `يَ` | 3–4 | 2 | no |
| **word-by-word / layout token** | **2** | **2** | **yes** |

- The **rasm** joins whatever is written without a space, so it keeps
  `مَالِيَ` as one. It cannot be our rule: we split it.
- The **إعراب** separates every particle, so it splits the prefixed `و` — a
  حرف عطف, a word in its own right. It cannot be our rule either: we never
  split a prefixed `و`/`ف`/`ب`/`لـ`.
- The **word-by-word token** keeps prefixed particles attached and separates
  `مَا` from `لِيَ`, because each takes its own gloss. That is what we do, at
  every one of the 6,236 ayahs.

It is a **convention**, not a derivation — but an external, published one, shared
by the V4 layout, DigitalKhatt, MushafDatabase, quran.com and every word-by-word
translation keyed to this mushaf. Consumers of `data-wid` expect exactly it.

Two guards against re-opening this from the wrong end:

> An ink-gap rule is not available. `و` does not join forward, so `وَمَا` has a
> break in the ink; any gap-width criterion splits the waw. Gap width was never
> our criterion, and reasoning from the drawing will keep suggesting it.

> The rasm looks like it explains the waw — it keeps it attached — but only
> because the rasm never splits anything written attached. That is circular, and
> it does not survive `مَالِيَ`.

The other two layers are still real and worth carrying, just not as `data-wid`:
the rasm form is what someone searching `مالي` types, and it can be exposed as an
attribute on the pair without touching segmentation.

---

## The precedence rule

**Segmentation claims come only from sources that mark words.**

| rank | source | what it is competent to say |
|---|---|---|
| 1 | **KFGQPC V4 layout** — the print's own | word positions; the only KFGQPC source that marks words, and the definition above |
| 2 | the **ink** of the 1441H print | which ink belongs to a word once the boundary is known — NOT where the boundary is |
| 3 | **MushafDatabase**, **DigitalKhatt** | independent word markings — but DK models the *1421H* print |
| 4 | **quran.com** `text_uthmani` | word markings, weakest — known to fuse and to carry typos |
| — | **KFGQPC UthmanicHafs text** | **spelling only.** Ayah-level; states the rasm, not word boundaries |

The last row is the one that has already caused an error, so it is stated as a
rule rather than a footnote:

> A text file states spelling. A layout table states words. Splitting an ayah
> string on whitespace and calling the result a word list measures the rasm's
> joining convention, not our segmentation — and turns every mawṣūl pair in the
> Quran into a false defect.

The ink is demoted deliberately. It settles ownership and placement, and it is
final for those — but it cannot state a boundary, because the only boundary
signal it carries is gap width, and gap width splits the waw.

Where sources at the same rank disagree, the tie is broken by a **falsifiable
geometric test**, not by counting sources. The one that has decided a case here:

> **If a pair can land on two lines, it must be two positioned units.**
> One word cannot express a line break running through it.

That is what settled `بَعْدَ مَا` — on p254 the pair straddles a line break, which
quran.com's single fused word could not represent (`reported.json` item 20).

---

## The rule the spelling is expressing

In the Uthmani rasm some word pairs are written **joined** (موصول) where ordinary
spelling separates them, and a few **separated** (مقطوع) where spelling joins
them. It is fixed by transmission rather than derived from grammar, so it must be
carried as data — no rule generates it.

The standard classical authorities for the convention:

- Abū ʿAmr al-Dānī (d. 444 AH), *al-Muqniʿ fī maʿrifat marsūm maṣāḥif al-amṣār*
- al-Shāṭibī (d. 590 AH), *ʿAqīlat atrāb al-qaṣāʾid* — the versification of
  al-Muqniʿ, and the form the rule is usually taught in

These are the authorities the printed mushaf follows, and they are cited here to
name the convention. **They are not what this pipeline reads.** Our decisions are
made from the sources in the table above, so that every one of them can be
re-verified by running a command rather than by consulting a manuscript
tradition. Where a classical statement and the 1441H ink appear to disagree, the
ink is what this project decomposes.

---

## The four sites

These four are the complete list of ayahs where our word count differs from a
whitespace split of the Complex's text — measured over all 6,236 ayahs,
2026-08-31.

| ayah | Complex's **text** (spelling) | **V4 layout** (words) | DigitalKhatt (1421H) | quran.com | ours | verdict |
|---|---|---|---|---|---|---|
| 15:7 | `لَّوۡمَا` joined | **two** | two | two | two | ✅ correct |
| 27:20 | `مَالِيَ` joined | **two** | two | two | two | ✅ correct |
| 36:22 | `وَمَالِيَ` joined | **two** | two | two | two | ✅ correct |
| 37:130 | `إِلۡ` `يَاسِينَ` separated | **two** | one | one | ~~one~~ → **two** | 🔧 fixed |

### The three mawṣūl pairs are not defects

`مَالِيَ` is **one word by rasm and two positioned units on the page**, and both
statements are true at once. Every source that marks words — including the
print's own V4 layout — sets them as two, and we already match. The apparent
disagreement was an artefact of the comparison method, not a finding.

### 37:130 `إِلۡ يَاسِينَ` was a real error

The Complex's text writes the two **with a space** — the maqṭūʿ spelling — and
the print's own V4 layout gives the ayah **four** word positions. Only
DigitalKhatt fuses them, and `assign_words.py` had recorded DK as its reason:

> The other two letter-space compounds stay ONE word because the DK DB fuses
> them too: 37:130:3 إِلْ يَاسِينَ

DK models the **1421H V2** print, not this one (`EDITION-1441-FINDING.md`), so it
was never evidence about this artwork. With the edition question settled the
reason is void, and the fix is one entry in `_DKSEG_SPLITS`.

**It also closes the p451 open item.** `إِلْ يَاسِينَ` had been flagged for years
as drawing *"one run more than the joining rules allow"* — which is exactly what
one word holding two words' ink measures as. It was never a defect in the
decomposition; the word source was from the other printing. p451 went from 2
flagged words to 1, and the surplus flag is gone.

After the split: `إِلۡ` holds `ا` + `ل`, `يَاسِينَ` holds `يا` + `سين` — four
ligature groups, the same ink, now correctly distributed across two words.

---

## Consequences of a split, and why nothing else had to be patched

Splitting a word shifts every later position in its ayah, so the change reaches
more than the emitter. `_DKSEG_SPLITS` is the single place that expresses it, and
everything else derives:

- **word text** — `_dkseg_split_data` splits the fused quran.com record
- **QPC text** — `_dkseg_qpc` maps our positions back through the fused cache
- **advance widths** — `_dkseg_widths` divides the compound's QCF advance between
  the halves in proportion to their calibrated letter widths
- **line table** — V4 is already keyed split, so it needs no conversion; it is
  where the extra position was already waiting
- **the annotation graph** — a derived cache, rebuilt, not patched

One place that did need work: **`_dktext`**. DK segments the three `بَعْدَ مَا`
pairs itself, so its positions track ours there — but it *fuses* 37:130, so after
our split its positions run one behind. Without that mapping, `37:130:3` took
DK's whole `"إِلْ يَاسِينَ"` and the split produced a word holding both halves'
text beside a word holding one of them. Whether a source fuses a given compound
is now **asked of the source** (`_dk_fuses`, which tests DK's own text for an
internal space) rather than kept in a hand-written list, so a DK update cannot
leave the list quietly wrong.

`5:52:12` `دَآئِرَ ةٌ` still stays **one** word: there quran.com's internal space
is its own typo, and DK and MushafDatabase both write one word.

---

## Re-verifying any of this

```bash
# the complete list of word-count candidates vs the Complex's text
python3 tools/compare_official_text.py --segmentation
# and the word-text agreement behind it (see OFFICIAL-TEXT-COMPARISON.md)
python3 tools/compare_official_text.py

# what each source marks at one site
python3 -c "import sqlite3;print([r[1] for r in sqlite3.connect(
  '.cache/digitalkhatt/digital-khatt-v2.db').execute(
  'select word,text from words where surah=37 and ayah=130 order by word')])"
python3 -c "import json;d=json.load(open('.cache/v4_lines.json'));
print(sorted(k for k in d['451'] if k.startswith('37:130:')))"
```

Gates after the change: **604/604 pixel-identical**, bench **SCORE 137** with no
failures and pixelfail 0, `audit_taxonomy` OK, `validate_annotations` OK at
**77,433 words** — one more than before, which is the whole of the change.
Word-count candidates fell 4 -> 3, and the three that remain are the mawṣūl
pairs, which are correct as they stand.
