# Word segmentation in the KFGQPC 1441H mushaf: three sites where every source disagrees with the print's own text

A short report for the Itqan community. Everything below is reproducible; the
tooling and full measurements are linked at the end.

## Summary

We decompose the KFGQPC V4 (1441H) Madani mushaf page artwork into ayah -> word
-> ligature -> mark, pixel-identical to the print. That makes word BOUNDARIES a
primary key, so we checked ours against the King Fahd Complex's own published
text (`UthmanicHafs_v2-0`) across all 6,236 ayahs.

Result: **four ayahs in the whole Quran** where word-marking sources disagree
with the Complex's own spelling. They are all the same classical topic —
**المقطوع والموصول**.

| source | what it is | ayahs differing from the Complex's text |
|---|---|---:|
| ours | this decomposition | **3** |
| V4 layout | the print's own 1441H layout | **3** |
| DigitalKhatt | the 1421H V2 print | **4** |
| quran.com | `text_uthmani` | **7** |

| ayah | the Complex's text | how the sources tokenise it |
|---|---|---|
| 15:7 | `لَّوۡمَا` — one word | `لَّوْ` + `مَا` — two |
| 27:20 | `مَالِيَ` — one word | `مَا` + `لِىَ` — two |
| 36:22 | `وَمَالِيَ` — one word | `وَمَا` + `لِىَ` — two |

And `37:130`: the Complex's text and the V4 layout both give **two** words;
DigitalKhatt and quran.com give one. (We fixed this one — it also closed a
long-standing flag in our own audit, where one word held two words' ink.)

## Why we think the three are an inconsistency, not a convention

The obvious defence is that word-by-word tokenisation follows ordinary modern
orthography rather than the rasm. That does not survive the data. In the very
same construction, every source **welds** `ما`+`لـ` where the rasm welds it:

| ayah | sources emit | the Complex's text | agree? |
|---|---|---|---|
| 4:78 | `فَمَالِ` + `هَٰٓؤُلَآءِ` | `فَمَالِ` | yes |
| 18:49 | `مَالِ` + `هَٰذَا` | `مَالِ` | yes |
| 25:7 | `مَالِ` + `هَٰذَا` | `مَالِ` | yes |
| 40:41 | `مَا` + `لِىٓ` | `مَا` | yes |
| 27:20 | `مَا` + `لِىَ` | `مَالِيَ` | no |
| 36:22 | `وَمَا` + `لِىَ` | `وَمَالِيَ` | no |

Modern orthography would not weld `مَالِ` at 18:49 — it would write the lam
with the following noun. So the sources are following the rasm there, and then
not following it at 27:20 and 36:22. Note especially **40:41 against 27:20**:
the same phrase, separated in one place and welded in the other. That is
transmitted site by site, which is exactly what المقطوع والموصول is.

## Our questions to the community

1. **Is the split at 15:7 / 27:20 / 36:22 deliberate or inherited?** Every
   word-marking source we checked has it, including the print's own V4 layout.
   If it is a considered word-by-word decision, we would like to understand the
   reasoning — particularly how it sits with the welding at 4:78 / 18:49 / 25:7.

2. **What is the agreed definition of a "word" for this mushaf?** Three answers
   are defensible and they disagree: the rasm's written token, the grammatical
   word (`و` is a حرف عطف, so `وَمَآ` would be two), and the word-by-word gloss
   token. Consumers key translations, tajwid data and audio timings to word
   positions, so it matters that the definition is stated rather than assumed.

3. **If a boundary is corrected, how should word ids migrate?** Merging two words
   shifts every later position in that ayah. Is there an agreed practice, a
   versioned word-id scheme, or a mapping table that downstream projects can
   follow? This is the single biggest obstacle to fixing it, and it is a
   community problem rather than a per-project one.

4. **Is there an authoritative KFGQPC word-level segmentation we should key to?**
   The Complex publishes the text at ayah level; the word divisions we all use
   come from third parties. If an official word list exists, it would settle
   this and several related questions.

5. **37:130 `إِلۡ يَاسِينَ`** — the Complex's text and the V4 layout both give two
   words; DigitalKhatt and quran.com give one. Is a correction planned there?

## Our suggested approach

We are not proposing that everyone renumber. We suggest separating the layers,
which lets each source stay correct about what it is competent to state:

1. **Spelling authority: the Complex's own text.** It is ayah-level, and its
   whitespace states the rasm. It should not be turned into a word list by
   splitting on spaces — do that and every mawṣūl pair in the Quran reads as a
   defect. This is the mistake that started our investigation.

2. **Boundary authority: a source that marks words**, and the print's own V4
   layout is the closest for the 1441H print.

3. **Do not use ink gaps to decide boundaries.** `و` does not join forward, so
   `وَمَا` has a visible break; any gap-width rule splits the prefixed particle.

4. **Carry the rasm form alongside the tokens, without changing ids.** A pair
   that the rasm welds can expose the joined spelling as an attribute, so search
   for `مالي` works while `data-wid` stays stable. This is additive, breaks no
   consumer, and is what we would adopt first.

5. **Correct the boundary only with an agreed migration**, because of question 3.
   Our own view is that the three sites are an internal inconsistency and should
   eventually be welded — but not unilaterally, and not silently.

## Reproducing this

All figures come from published data and a small tool:

* the Complex's text — `UthmanicHafs_v2-0` (`hafsData_v2-0.json`)
* the 1441H layout — `github.com/MohamadHajjRabee/quran-qcf4`
* DigitalKhatt — `digital-khatt-v2.db`; quran.com — `text_uthmani`
* `tools/compare_official_text.py --segmentation` in our repository, plus
  `docs/MA-TOKENS.md` for the full per-token inventory and the four-source
  comparison over all 6,236 ayahs

One caveat we would flag for anyone repeating the text comparison: the two
encodings differ systematically — the Complex writes `U+06E1` where our source
writes `U+0652` for sukun, and `U+0652` where ours writes `U+06DF` for the silent
circle, among others. Compared raw, the texts agree on 46.7% of words; normalised
onto one convention, 99.96%. The first two substitutions are a swap, so folding
them one after another silently merges sukun with the silent circle.
