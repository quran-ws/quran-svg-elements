# Licence and attribution

`LICENSE` is the **Creative Commons Attribution 4.0 International** licence
(CC BY 4.0), verbatim and unmodified. This file says what it covers, what it
cannot cover, and the attribution it asks you to carry.

This work is a waqf, offered seeking the reward of Allah, published so that it
may be of the widest possible benefit with the fewest possible restrictions.

## What is licensed

Everything in this bundle that this project authored:

| | |
|---|---|
| the decomposition of each page into ayah, word, ligature and labelled mark | `pages/` — the structure and every `data-` attribute |
| the derived indexes | `index/` — words, per-page sidecars, divisions, surahs, pages, mark taxonomy |
| the schemas and the format specification | `schema/` |
| provenance and integrity | `VERSION.json`, `CHECKSUMS.txt` |
| documentation | `README.md` |

Every top-level entry in the bundle is named above.

The decomposition is **derived** here: no source package contains it. Which ink
belongs to which word, which contour is a `fathah` and which a `maddah`, where
one ligature ends and the next begins — that analysis, and the indexes built on
it, are the work being licensed.

## The attribution requirement is waived for use inside a product

As the rights holder in our own data, we waive the attribution requirement of
CC BY 4.0 (section 3(a)) for all users, everywhere, at no cost, irrevocably,
**when the material is used inside** an app, site, service, API, bot, tool,
research or product — free or commercial. You do not have to show our name,
logo or link to your end users merely to use this inside a product, and that
includes bundling the data in an app for offline use.

This permission **enlarges** what you may do. It adds no condition to CC BY 4.0
and touches no other clause of it.

## Attribution is asked when you republish

The test: can whoever receives what you distribute obtain the data **as data**?
Then it is republication and CC BY 4.0's attribution terms apply.

| republication — attribution asked | use — not asked |
|---|---|
| datasets, bulk dumps, downloadable exports | bundling in an app for offline use |
| mirrors and re-hosting | an API answering individual requests |
| APIs handing over the whole corpus at once | search, display and analysis features |
| modified or derived copies published as resources in their own right | derived output that does not reconstitute the data |
| a repository vendoring these files as a data file | internal use inside an organisation |

Machine learning: training, fine-tuning, evaluating, indexing and retrieval are
**use**. Publishing our data inside a training set you distribute is
republication.

    Data from "<resource name>" by Quran.ws, licensed CC BY 4.0.
    Source: <canonical URL>. Version: <VERSION.json build_date and commit>.
    Modified: yes/no.

Please keep the provenance fields in `VERSION.json` inside the data even where
visible attribution is waived, so whoever finds a copy years from now can tell
what it is and find its corrections. That is a request, not a condition.

## What is not licensed here

**The printed page artwork is not this project's to license.**

| | |
|---|---|
| the glyph outlines drawn in `pages/` | the King Fahd Glorious Qurʾān Printing Complex's artwork |
| the Qurʾānic text and the muṣḥaf's vocalisation | KFGQPC, read from their published packages |
| KFGQPC fonts, where referenced | KFGQPC, as received |

These remain subject to the rights, licences and conditions of their owners. We
acquired no right in them by decomposing, labelling, correcting, organising,
converting or distributing them. Nothing in `LICENSE` grants you any right in
them, and this project makes no claim about what KFGQPC permits — satisfy
yourself before redistributing.

`pages/` therefore carries **both**: their ink, and our structure over it. The
licence covers the second, not the first.

## Names, logos and marks

These licences grant rights in data and content. They grant **no** right in our
names, logos, domains or trademarks, nor in those of the King Fahd Glorious
Qurʾān Printing Complex. Use of this material does not mean we endorse, review,
approve or are affiliated with any product built on it.

## Accuracy, and your duty if you publish Qurʾānic text

The material is provided **as is, without warranty of any kind**, as CC BY 4.0
(sections 5 and 6) provides.

Errors can occur in the text, the rasm, the vocalisation or the decomposition,
and releases are corrected over time. **Whoever publishes Qurʾānic text to
users is responsible for checking it against an approved printed muṣḥaf and for
following our corrections.** We are not responsible for errors another party
introduces into their copy, nor for releases that have been superseded.

If you build systems on this material, please take care not to present
generated or paraphrased output as Qurʾānic text, and keep a path back to the
trusted source wherever you can.

## Contributions and intent

Unless a contributor states otherwise in writing, contributions are offered
under the same licence as the material contributed to: MIT for code, CC BY 4.0
for data and content.

The benefit intended by this waqf is that which accords with Islam. We do not
intend this work to be used in what contradicts that. That is the intent behind
offering it; the legal terms of its use remain governed by the licence above,
which is standard and unmodified.

  Corrections: <corrections@quran.ws>
  Licensing:   <legal@quran.ws>

The Quran.ws licensing policy is published in Arabic and English; where they
differ, **the Arabic is authoritative**.

Copyright 2026 Quran.ws. Rights are retained to protect the waqf, not to
restrict people's benefit from it.
