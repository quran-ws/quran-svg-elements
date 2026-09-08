# Vendored data

`counting-systems.json`, `qiraahs.json` and `book-boundary-primitives.json` are copied
verbatim from [quranpedia/qiraahs-ayah-map](https://github.com/quranpedia/qiraahs-ayah-map)
(MIT). Commit 076255281ec6f76241d7e901e27072733d02a18d, fetched 2026-08-24.

They map ayah numbering between the six canonical counting systems. `tools/qiraahs_map.py`
uses them to derive each counting system's per-surah ayah counts from the Kufan reference,
so the audit can check that a mushaf's ayah identities match the counting system its
qiraah actually follows.
