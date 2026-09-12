<div align="center">

<img src=".github/banner.svg" alt="Quran SVG Elements — Pages & Assets, Beta" width="820">

**Fully decomposed Mushaf pages where words, marks, and other page elements can be addressed programmatically.**

<a href="https://quran.ws/blocks/quran-svg-elements"><img alt="See it work" src="https://img.shields.io/badge/See_it_work-15705D?style=for-the-badge&labelColor=102F29"></a>
<a href="https://quran.ws/docs/reference/quran-svg-elements"><img alt="Documentation" src="https://img.shields.io/badge/Documentation-102F29?style=for-the-badge&labelColor=102F29"></a>

</div>

Use it when your application needs interaction at word or mark level, such as recitation highlighting, learning tools, word-level audio, meanings, or linguistic data.

> صفحات مصحف مفصّلة إلى عناصر يمكن الوصول إليها برمجيًا، من الكلمات إلى العلامات الدقيقة داخل الصفحة.
>
> استخدمها عندما تحتاج التفاعل على مستوى الكلمة أو العلامة، مثل التظليل أثناء التلاوة، والتعليم، وربط الكلمات بالصوت أو المعاني أو البيانات اللغوية.

| | |
|---|---|
| **Words · marks** | 77,432 · 436,398 |
| **Split so far** | Hafs (KFGQPC) |
| **Licence** | CC BY 4.0 (the work) · KFGQPC terms (the artwork) |

```sh
gh release download v1.0.0 -R quran-ws/quran-svg-elements
```

## Where the documentation is

Everything about using it lives on the site. This repository is the source.

| | |
|---|---|
| **Overview and demo** | [quran.ws/blocks/quran-svg-elements](https://quran.ws/blocks/quran-svg-elements) |
| **Reference** | [quran.ws/docs/reference/quran-svg-elements](https://quran.ws/docs/reference/quran-svg-elements) |
| **Make words clickable** | [quran.ws/docs/build/clickable-words](https://quran.ws/docs/build/clickable-words) |
| **Crop an ayah as an image** | [quran.ws/docs/build/crop-ayah-image](https://quran.ws/docs/build/crop-ayah-image) |
| **Highlight an ayah** | [quran.ws/docs/build/highlight-ayah](https://quran.ws/docs/build/highlight-ayah) |
| **Licensing in full** | [quran.ws/docs/reference/licensing](https://quran.ws/docs/reference/licensing) |

## What is in here

| | |
|---|---|
| `tools/` | the decomposition pipeline, the audits, and the review platform |
| `conformance/` | the gates that must stay green |
| `docs/` | the process, the shape labels, and how to work on this repository |
| `LICENSES/` | per-file licence texts |

Issues and pull requests are welcome here. Everything that is not about *changing* this repository is on the site.
