# Running the tests

307 assertions in a real browser — 312 with `?markers=<url>`. No test framework,
no install.

```bash
# from a directory that contains lib/ and the page SVGs
python3 -m http.server 8931
```

Then open, pointing at wherever the pages live:

```
http://127.0.0.1:8931/lib/test/?pages=/pages/&atlas=/atlas.json
```

`window.__RESULTS__` carries `{pass, fail, errors, tests[]}` when
`__RESULTS__.done` is true, so a runner can drive it headlessly:

```js
await page.waitForFunction(() => window.__RESULTS__?.done);
const r = await page.evaluate(() => window.__RESULTS__);
```

Add `&markers=<url>` — for example
`https://quranpedia.github.io/ayah-markers/` — to additionally check a real marker
set for conformance (§21.50-54). Without it the end-marker tests still run in full
against a synthetic set served by a stub `fetch`, because no marker outline may ship
in this repository.

Defaults point at this repository's own cache
(`.cache/words-svg/hafs-kfqc/`) and an `atlas.json` beside this file — build one
with `python3 ../build-atlas.py <pages-dir> -o atlas.json`. Without it the atlas
section fails and nothing else does.

**Cache-bust when you edit the library**: the page passes its own `?v=` through to
the module import, so reload with a new `v` (or disable the HTTP cache) or the
browser serves you the previous build and the run means nothing.

The suite leaves a live selection layer on page 42 as `window.__SEL__` /
`window.__P42__` / `window.__HOVER__`, for driving a real mouse drag, Ctrl+C, hover
and a resize from outside. Those interactive checks are not part of the 215.
