# Errata for `schema/FORMAT.md`

`schema/FORMAT.md` ships inside the v1.0.0 bundle and is the best thing in it. These are the
places where it does not match the files, verified against the shipped bundle. They are recorded
here rather than on <https://quran.ws> because they are about a file in this repository, not about
how to consume the data — the site documents what the files actually do.

## Known gaps in `schema/FORMAT.md`

Verified against the shipped v1.0.0 bundle. The specification is otherwise the best thing in it — but these recipes will not run as written:

- §6.2, §7 and §11 name the fragment→medallion attribute `data-mark` / `dataset.marker`. The files emit **`data-ayah-mark`**. (`data-mark` is real, but it lives on mark paths.)
- Code samples read `w.dataset.rasm_uthmani`, which is always `undefined` — `dataset` camel-cases, so it is **`rasmUthmani`**.
- §3 and §11 search recipes read `data-search`, which the published production profile does not carry.
- §11's Python recipes open `index/index.json` and `index/wordboxes.json`; neither is in the bundle. Use `index/pages.json` and `index/by-page/NNN.json`.
- §4 calls the medallion layer `class="ayah_marks"`; the files emit `class="ayah_markers"`.
- §8 points at `.cache/schema/mark-taxonomy.v2.json`; the bundle ships `schema/mark-taxonomy.json`.
- §6.1 refers to a shipping library (`page.attachWords`, `createLoader`). No such library exists in this repository or in the release.

## A caution about the names

The repository, the release asset and the schema ids are all still named after `quran-svg`. A reader sent to "the quran-svg bundle" can land on [`quran-ws/quran-svg`](https://github.com/quran-ws/quran-svg) instead, which has a v1.0.0 release of its own — a different product, five muṣḥafs at ayah level. It will load and contain no `g.word`. The bundle you want is `quran-svg-hafs-kfgqpc.tar.gz`, from this repository.
