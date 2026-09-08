#!/usr/bin/env python3
"""Build the shippable bundle: pages, indexes, schemas, checksums, archive.

One command produces the whole distributable. It replaces the three proofs of
concept that used to live in docs/shipping/ (index_poc.py, profile_poc.py,
wordbox_poc.py) — there is exactly one way to produce each shipped file.

    python3 tools/build_bundle.py                     # full build into dist/
    python3 tools/build_bundle.py --out /tmp/b        # elsewhere
    python3 tools/build_bundle.py --no-archive --no-gzip

DETERMINISM. Running this twice over the same inputs gives byte-identical
output, and `tools/verify_bundle.py --compare A B` proves it. The rules:

  * no timestamp, hostname or path appears in any data file — the build date
    lives in VERSION.json alone, and is a DATE (UTC), not a clock reading;
  * every JSON object is written with sorted keys and a fixed separator;
  * floats are rounded to a fixed number of decimal places and formatted by
    repr, which is shortest-round-trip and stable across CPython versions;
  * gzip is written with mtime=0, and the tar with a fixed member mtime, uid,
    gid and name, in sorted path order;
  * CHECKSUMS.txt is sorted by path and generated last.

NOTHING here touches the pipeline, the emitter or the artwork. The page SVGs
come from tools/emit_pages.py, which only calls assign_page().
"""
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bundle_extract                                          # noqa: E402
import emit_pages                                              # noqa: E402

try:
    import brotli
except ImportError:                                            # pragma: no cover
    brotli = None

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
# the docs live in the pipeline repo, which is not necessarily QSVG_ROOT
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITION = "hafs/kfqc"
EDITION_ID = "hafs-kfgqpc"
BUNDLE_NAME = "quran-svg-" + EDITION_ID
SCHEMA_VERSION = "1.0.0"

# Every JSON file carries these two so a consumer can tell what it is holding
# without inspecting the shape.  `schema` is the file's kind; `schema_version`
# is the bundle-wide version, bumped together for every file.
_BOX_DP = 2          # decimal places on word boxes; see README "Coordinates"


# ------------------------------------------------------------------ helpers

def jdump(obj, path):
    """Write JSON deterministically: sorted keys, compact, UTF-8, no newline."""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(text.encode())


def envelope(kind, payload):
    d = {"schema": kind, "schema_version": SCHEMA_VERSION,
         "edition": EDITION_ID}
    d.update(payload)
    return d


def rbox(b):
    return [round(v, _BOX_DP) for v in b]


def git_commit(repo):
    """(commit, dirty) for `repo`, or (None, None) if it is not a git repo.

    `dirty` matters: the artwork worktree carries add_line_structure.py's
    in-place rewrite of every page, so it is dirty by design and the commit
    alone does not identify what was built from.
    """
    def run(*args):
        return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                              text=True, check=True).stdout
    try:
        return run("rev-parse", "HEAD").strip(), bool(run("status",
                                                          "--porcelain").strip())
    except Exception:                                          # noqa: BLE001
        return None, None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_gzip(src, dest):
    """gzip with mtime=0 and no stored filename: byte-identical every run."""
    raw = open(src, "rb").read()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(raw)
    with open(dest, "wb") as fh:
        fh.write(buf.getvalue())


def write_brotli(src, dest, quality=11):
    raw = open(src, "rb").read()
    with open(dest, "wb") as fh:
        fh.write(brotli.compress(raw, quality=quality))


def _compress_one(job):
    path, do_gz, do_br, quality = job
    if do_gz:
        write_gzip(path, path + ".gz")
    if do_br:
        write_brotli(path, path + ".br", quality)
    return path


# -------------------------------------------------------------- the indexes

def build_indexes(out, recs, manifest):
    """Write index/ from the extracted page records. Returns count summary."""
    idx = os.path.join(out, "index")
    by_page = os.path.join(idx, "by-page")
    os.makedirs(by_page, exist_ok=True)

    # ---- index/pages.json: one summary record per page ----------------
    pages = []
    for r in recs:
        aids = r["ayat"]
        pages.append({
            "page": r["page"],
            "view_box": r["view_box"],
            "lines": len(r["lines"]),
            "words": len(r["words"]),
            "marks": r["marks"],
            "surahs": r["surahs"],
            "banners": r["banners"],
            "first_ayah": aids[0] if aids else None,
            "last_ayah": aids[-1] if aids else None,
            "ayahs": len(aids),
            "divisions": r["divisions"],
        })
    jdump(envelope("quran-svg/pages", {
        "count": len(pages),
        "description": "one record per printed page; boxes and word text are "
                       "in index/by-page/NNN.json",
        "pages": pages}), os.path.join(idx, "pages.json"))

    # ---- index/surahs.json: the 114 surah records ---------------------
    surahs = []
    for s in sorted(manifest["surahs"], key=lambda s: s["number"]):
        surahs.append({
            "number": s["number"],
            "name_arabic": s["name_arabic"],
            "name_latin": s["name_complex"],
            "name_english": s["name_english"],
            "revelation_place": s["revelation_place"],
            "revelation_order": s["revelation_order"],
            "ayah_count": s["ayah_count"],
            "pages": s["pages"],
            "has_basmalah": bool(s.get("bismillah_pre")),
        })
    jdump(envelope("quran-svg/surahs",
                   {"count": len(surahs), "surahs": surahs}),
          os.path.join(idx, "surahs.json"))

    # ---- index/divisions.json: juz / hizb / nisf / rubʿ ----------------
    # Taken from the SVGs (data-*-start), so the file cannot drift from the
    # pages; the manifest supplies only the page each division starts on.
    page_of = {}
    for r in recs:
        for aid in r["ayat"]:
            page_of.setdefault(aid, r["page"])
    # Each of the four attributes is present only on the ayah that STARTS that
    # division, so an ayah's record carries whichever subset applies to it.
    starts = []
    for r in recs:
        for aid, d in sorted(r["divisions"].items()):
            starts.append((aid, page_of.get(aid, r["page"]), d))
    # Each division kind gets its own list: the boundaries of that kind, in
    # order, each with the ayah it begins at and that ayah's page.  The SVG
    # carries an attribute only on the ayah that BEGINS a division (30 juz,
    # 60 hizb, 60 nisf, 240 rubʿ — measured), so the lists come straight from
    # it.  `hizb` and `rub_in_hizb` on a rubʿ record are arithmetic (a rubʿ is
    # a quarter of a hizb) and are ASSERTED against the 60 ayahs that state
    # their hizb, rather than assumed.
    #
    # `data-nisf-start` is NOT 1/2: it is emitted on the 60 ayahs whose
    # rub_in_hizb is 3 — the start of each hizb's second half — and its value
    # is that boundary's ordinal, 1..60.  It is listed as its own series here
    # for that reason; the 1-or-2 half a rubʿ falls in is `half`.
    rubs = []
    for aid, pg, d in starts:
        if "rub" not in d:
            continue
        n = d["rub"]
        hz, rih = (n + 3) // 4, (n - 1) % 4 + 1
        if d.get("hizb") not in (None, hz):
            raise AssertionError(
                "rub %d: page says hizb=%s, arithmetic says %d"
                % (n, d.get("hizb"), hz))
        rubs.append({"rub": n, "hizb": hz, "rub_in_hizb": rih,
                     "half": 1 if rih <= 2 else 2,
                     "juz": d.get("juz"), "ayah": aid, "page": pg})
    rubs.sort(key=lambda x: x["rub"])
    juz = sorted(
        [{"juz": d["juz"], "ayah": aid, "page": pg}
         for aid, pg, d in starts if "juz" in d], key=lambda x: x["juz"])
    hizb = sorted(
        [{"hizb": d["hizb"], "ayah": aid, "page": pg}
         for aid, pg, d in starts if "hizb" in d], key=lambda x: x["hizb"])
    nisf = sorted(
        [{"nisf": d["nisf"], "ayah": aid, "page": pg}
         for aid, pg, d in starts if "nisf" in d], key=lambda x: x["nisf"])
    jdump(envelope("quran-svg/divisions", {
        "description": "every juz, hizb, half-hizb and rubʿ boundary, with "
                       "the ayah it begins at and that ayah's page. A rubʿ "
                       "record's `half` is which half of its hizb it is in; "
                       "the `nisf` series lists the 60 second-half starts.",
        "juz": juz, "hizb": hizb, "nisf": nisf, "rub": rubs}),
        os.path.join(idx, "divisions.json"))

    # ---- index/words.json: the corpus-wide SEARCH index ----------------
    # Columnar, because at 77,432 rows the repeated object keys cost 4.1 MiB
    # raw (measured: 7.5 MiB columnar vs 11.6 MiB object form) and this is the
    # one file a consumer parses in full.  Per-page sidecars are objects; the
    # saving there was 0.6 KiB brotli against a 121 KiB page, so readability
    # won.  Always read `fields` rather than assuming the column order.
    fields = ["wid", "w", "page", "line", "uthmani", "search"]
    rows = [[w["wid"], w["w"], r["page"], w["line"], w["uthmani"], w["search"]]
            for r in recs for w in r["words"]]
    jdump(envelope("quran-svg/words", {
        "description": "every word in the corpus, in mushaf order. `w` is "
                       "the global word id shared with the word-by-word "
                       "source (the same number for this word in every "
                       "mushaf that has it; the two pieces of 15:7 لَّوْ مَا "
                       "share one). `search` is the fold-ready key; "
                       "`uthmani` is the text of record. Full text forms "
                       "and boxes: index/by-page/.",
        "count": len(rows), "fields": fields, "rows": rows}),
        os.path.join(idx, "words.json"))

    # ---- index/by-page/NNN.json: everything about one page -------------
    for r in recs:
        words = []
        for w in r["words"]:
            words.append({
                "wid": w["wid"], "w": w["w"], "ayah": w["aid"], "line": w["line"],
                "uthmani": w["uthmani"], "rasm": w["rasm"],
                "imlaei": w["imlaei"], "search": w["search"], "qpc": w["qpc"],
                "box": rbox(w["box"]) if w["box"] else None,
            })
        jdump(envelope("quran-svg/page-words", {
            "page": r["page"], "view_box": r["view_box"],
            "box_space": "viewBox units of pages/%03d.svg" % r["page"],
            "count": len(words), "words": words}),
            os.path.join(by_page, "%03d.json" % r["page"]))

    return {"pages": len(pages), "surahs": len(surahs), "words": len(rows),
            "rub": len(rubs)}


# --------------------------------------------------------------- JSON Schema

def _divisions_schema(base, env_props, env_req, aid):
    """One series per division kind; a rubʿ record carries its rollups."""
    def series(key, extra=None):
        props = {key: {"type": "integer"}, "ayah": aid,
                 "page": {"type": "integer"}}
        props.update(extra or {})
        return {"type": "array", "items": {
            "type": "object", "required": [key, "ayah", "page"],
            "properties": props}}

    return dict(base, title="quran-svg/divisions", type="object",
                required=env_req + ["juz", "hizb", "nisf", "rub"],
                properties=dict(
                    env_props, description={"type": "string"},
                    juz=series("juz"), hizb=series("hizb"),
                    nisf=series("nisf"),
                    rub=series("rub", {
                        "hizb": {"type": "integer"},
                        "rub_in_hizb": {"type": "integer", "minimum": 1,
                                        "maximum": 4},
                        "half": {"type": "integer", "minimum": 1,
                                 "maximum": 2},
                        "juz": {"type": ["integer", "null"]}})))


def build_schemas(out):
    """Emit JSON Schema (2020-12) for each shipped data file."""
    sd = os.path.join(out, "schema")
    os.makedirs(sd, exist_ok=True)
    base = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
    env_props = {
        "schema": {"type": "string"},
        "schema_version": {"type": "string"},
        "edition": {"type": "string"},
    }
    env_req = ["schema", "schema_version", "edition"]
    aid = {"type": "string", "pattern": r"^\d+:\d+$"}
    wid = {"type": "string", "pattern": r"^\d+:\d+:\d+$"}

    schemas = {
        "pages.schema.json": dict(base, title="quran-svg/pages", type="object",
            required=env_req + ["count", "pages"], properties=dict(env_props,
                count={"type": "integer"},
                description={"type": "string"},
                pages={"type": "array", "items": {
                    "type": "object",
                    "required": ["page", "view_box", "lines", "words", "marks",
                                 "surahs", "ayahs"],
                    "properties": {
                        "page": {"type": "integer", "minimum": 1,
                                 "maximum": 604},
                        "view_box": {"type": "string"},
                        "lines": {"type": "integer"},
                        "words": {"type": "integer"},
                        "marks": {"type": "integer"},
                        "ayahs": {"type": "integer"},
                        "surahs": {"type": "array",
                                   "items": {"type": "integer"}},
                        "banners": {"type": "array",
                                    "items": {"type": "integer"}},
                        "first_ayah": {"type": ["string", "null"]},
                        "last_ayah": {"type": ["string", "null"]},
                        "divisions": {"type": "object"}}}})),

        "surahs.schema.json": dict(base, title="quran-svg/surahs",
            type="object", required=env_req + ["count", "surahs"],
            properties=dict(env_props, count={"type": "integer"},
                surahs={"type": "array", "minItems": 114, "maxItems": 114,
                    "items": {"type": "object",
                        "required": ["number", "name_arabic", "name_latin",
                                     "name_english", "revelation_place",
                                     "ayah_count", "pages", "has_basmalah"],
                        "properties": {
                            "number": {"type": "integer", "minimum": 1,
                                       "maximum": 114},
                            "name_arabic": {"type": "string"},
                            "name_latin": {"type": "string"},
                            "name_english": {"type": "string"},
                            "revelation_place": {"enum": ["makkah",
                                                          "madinah"]},
                            "revelation_order": {"type": "integer"},
                            "ayah_count": {"type": "integer"},
                            "pages": {"type": "array",
                                      "items": {"type": "integer"},
                                      "minItems": 2, "maxItems": 2},
                            "has_basmalah": {"type": "boolean"}}}})),

        "divisions.schema.json": _divisions_schema(base, env_props, env_req,
                                                   aid),

        "words.schema.json": dict(base, title="quran-svg/words", type="object",
            required=env_req + ["count", "fields", "rows"],
            properties=dict(env_props, count={"type": "integer"},
                description={"type": "string"},
                fields={"type": "array", "items": {"type": "string"}},
                rows={"type": "array", "items": {
                    "type": "array", "minItems": 6, "maxItems": 6,
                    "prefixItems": [wid, {"type": "integer", "minimum": 1},
                                    {"type": "integer"}, {"type": "integer"},
                                    {"type": "string"}, {"type": "string"}]}})),

        "page-words.schema.json": dict(base, title="quran-svg/page-words",
            type="object",
            required=env_req + ["page", "view_box", "count", "words"],
            properties=dict(env_props,
                page={"type": "integer", "minimum": 1, "maximum": 604},
                view_box={"type": "string"},
                box_space={"type": "string"},
                count={"type": "integer"},
                words={"type": "array", "items": {"type": "object",
                    "required": ["wid", "w", "ayah", "line", "uthmani", "rasm",
                                 "imlaei", "search", "qpc", "box"],
                    "properties": {
                        "wid": wid, "ayah": aid,
                        "w": {"type": "integer", "minimum": 1,
                              "description": "global word id, shared with the "
                                             "word-by-word source"},
                        "line": {"type": "integer"},
                        "uthmani": {"type": "string"},
                        "rasm": {"type": "string"},
                        "imlaei": {"type": "string"},
                        "search": {"type": "string"},
                        "qpc": {"type": "string"},
                        "box": {"type": ["array", "null"], "minItems": 4,
                                "maxItems": 4,
                                "items": {"type": "number"}}}}})),

        "version.schema.json": dict(base, title="quran-svg/version",
            type="object",
            required=["schema", "schema_version", "edition", "profile",
                      "build_date", "counts"],
            properties={"schema": {"type": "string"},
                        "schema_version": {"type": "string"},
                        "edition": {"type": "string"},
                        "print": {"type": "string"},
                        "profile": {"enum": ["production", "dev"]},
                        "build_date": {"type": "string",
                                       "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                        "artwork_commit": {"type": ["string", "null"]},
                        "artwork_dirty": {"type": ["boolean", "null"]},
                        "artwork_note": {"type": "string"},
                        "pipeline_commit": {"type": ["string", "null"]},
                        "pipeline_dirty": {"type": ["boolean", "null"]},
                        "counts": {"type": "object"},
                        "compression": {"type": "object"}}),
    }
    for name, doc in schemas.items():
        jdump(doc, os.path.join(sd, name))
    return sorted(schemas)


# ------------------------------------------------------------------- README

README = """\
# Quran page SVGs — {edition}

604 pages of the **{print_name}**, as vector outlines with the ink semantically
decomposed: every word is one `<g class="word">` with a stable `data-wid`, and
every diacritic is its own `<path data-mark="…">`. The pages are pixel-identical
to the print artwork.

The full specification is **[`schema/FORMAT.md`](schema/FORMAT.md)**. This file
covers only what the bundle contains and how to serve it.

## Quick start

```html
<!-- show a page -->
<object data="pages/042.svg" type="image/svg+xml"></object>
```

```js
// the words of page 42, with their boxes — no SVG parsing needed
const page = await (await fetch('index/by-page/042.json')).json();
page.words[0];   // {{ wid:"2:245:1", line:1, uthmani:"…", box:[x0,y0,x1,y1] }}
```

```js
// search the whole corpus
const idx = await (await fetch('index/words.json')).json();
const col = Object.fromEntries(idx.fields.map((f, i) => [f, i]));   // never assume order
const fold = s => s.replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه');
const hits = idx.rows.filter(r => fold(r[col.search]).includes(fold('الرحمن')));
```

## What is in here

| path | what it answers |
|---|---|
| `pages/NNN.svg` | the page itself, 001–604 |
| `pages/NNN.svg.br`, `.svg.gz` | the same bytes, pre-compressed for static serving |
| `index/pages.json` | page → surahs, first/last ayah, word/mark/line counts, divisions starting there |
| `index/surahs.json` | the 114 surah records: names, revelation place, ayah count, page range |
| `index/divisions.json` | every juz, hizb, half-hizb and rubʿ boundary, with its ayah and page |
| `index/words.json` | every word in the corpus with its page and search key — the search index |
| `index/by-page/NNN.json` | one page's words: all five text forms, line, and bounding box. **The page itself carries `data-uthmani` only** — rasm, imlaei, search and qpc live here |
| `schema/FORMAT.md` | the format specification: structure, attributes, mark taxonomy, known limits |
| `schema/mark-taxonomy.json` | the closed vocabulary of mark names, with category and family |
| `schema/*.schema.json` | JSON Schema (2020-12) for every data file above |
| `VERSION.json` | schema version, build date, source commits, corpus counts |
| `CHECKSUMS.txt` | sha256 of every other file — `sha256sum -c CHECKSUMS.txt` |
| `LICENSE` | CC0 1.0 for this project's own contribution; the publishers' terms for the ink |
| `NOTICE.md` | source editions, attribution and the publishers' grants |
{lib_row}
## Naming rules

So that nothing has to be guessed:

- **kebab-case** for multi-word file names (`by-page`, `page-words.schema.json`);
- **no file is named after its own directory** — the per-page sidecars are
  `index/by-page/042.json`, not `index/index.json`;
- **plural names for collections** (`pages.json`, `surahs.json`, `words.json`);
- `.json` for data, `.md` for prose, `.txt` only where a standard tool expects
  it (`CHECKSUMS.txt`, for `sha256sum -c`);
- **every JSON file carries `schema` and `schema_version`** at its top level, so
  a consumer can tell what it is holding without inspecting the shape;
- **columnar files always carry a `fields` array** — read the column order from
  it, never assume it.

## Two granularities, on purpose

`index/by-page/NNN.json` and `index/words.json` deliberately overlap. They serve
different consumers, and the sizes are the reason:

| to do this | fetch | over the wire |
|---|---|---|
| show page 42 and highlight its words | `pages/042.svg` + `index/by-page/042.json` | {show_page} |
| search the whole corpus | `index/words.json` | {search_all} |

(Both figures are the brotli copies, which is what a host with content
negotiation sends — see the next section.)

A reader that had to take the corpus index to draw one page would download
{search_all} of index to obtain 147 words. That is what the split avoids.

## Serving the pre-compressed pages

`pages/042.svg.br` and `pages/042.svg.gz` are the same bytes as `pages/042.svg`
after decompression — nothing is dropped and nothing is added. They exist so a
static host can serve {br_page} instead of {raw_page} for a page. Both nginx and
Caddy find them by name, with no build step:

```nginx
# nginx, with ngx_brotli built in
brotli_static on;
gzip_static   on;
location /pages/ {{ types {{ image/svg+xml svg; }} }}
```

```caddyfile
# Caddy 2
file_server {{ precompressed br gzip }}
```

If your host cannot do content negotiation, serve `pages/NNN.svg` and let the
CDN compress; the `.br`/`.gz` copies are then unused and can be deleted.

{archive_section}## Verifying what you downloaded

```sh
sha256sum -c CHECKSUMS.txt        # from the bundle root
```

`CHECKSUMS.txt` covers every file in the bundle except itself.

## Coordinates

Word boxes in `index/by-page/NNN.json` are **viewBox units of that page's SVG**
— the page frame and the line frame are already applied, so a box can be drawn
straight onto the rendered page as an overlay. They are exact outline extents
(Bezier extrema solved for, not control-point hulls), rounded to {box_dp}
decimal places. `view_box` in the same file is the page's own `viewBox`
attribute, which differs on pages 1–2 (FORMAT.md §5.1).

In a browser the boxes are redundant — `getBBox()` gives the same answer. They
are here for the cases where there is no browser: server-side cropping and
thumbnailing, hit-testing before the SVG has loaded, and building a text layer
over a raster render.

## Rebuilding this bundle

```sh
python3 tools/build_bundle.py --out dist
```

Deterministic: two builds of the same inputs produce byte-identical files, which
`python3 tools/verify_bundle.py --compare dist/{bundle} other/{bundle}` checks.
`python3 tools/verify_bundle.py dist/{bundle}` validates a bundle on its own —
every advertised file present, every checksum correct, every JSON parsing,
pages 1–604 covered, and every `data-wid` in the index resolving to a word group
in the page it names.
"""

ARCHIVE_SECTION = """\
## Taking the whole corpus at once

`{bundle}.tar.gz` sits **beside** this directory, with its own `.sha256`. It
holds the raw bundle — every file you see here except the `.br` and `.gz`
copies, which a bulk downloader does not need. One request instead of
{file_count}.

```sh
tar xzf {bundle}.tar.gz
cd {bundle} && sha256sum -c CHECKSUMS.txt
```

The archive lives outside the bundle on purpose: it contains `CHECKSUMS.txt`,
so it cannot also be listed in it.

"""

LICENSE_PLACEHOLDER = """\
PLACEHOLDER — NOT A LICENCE
===========================

No licence has been chosen for this bundle yet, and no terms are stated here.

Nothing in this file grants any permission. Until this file is replaced with a
real licence text by the copyright holder, treat the contents of this bundle as
"all rights reserved" and ask before redistributing.

The Quranic text and the page artwork have their own provenance, recorded in
VERSION.json and in schema/FORMAT.md; their terms are not this file's to state.

If you are the copyright holder: replace this file wholesale, and re-run
tools/build_bundle.py so CHECKSUMS.txt matches.
"""


# --------------------------------------------------------------------- build

def human(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def build(out_root, *, profile="production", jobs=32, gzip_pages=True,
          brotli_pages=True, archive=True, lib=None, reuse_pages=False,
          quiet=False):
    if brotli is None and brotli_pages:
        raise SystemExit("brotli module not installed; --no-brotli to skip")

    bundle = os.path.join(out_root, BUNDLE_NAME)
    if os.path.isdir(bundle):
        shutil.rmtree(bundle)           # a bundle is built whole, never patched
    os.makedirs(os.path.join(bundle, "pages"), exist_ok=True)

    # ---- 1. pages -----------------------------------------------------
    say = (lambda *a: None) if quiet else print
    # Re-emit by default. The staging cache cannot tell that the emitter has
    # changed since it was filled, and a bundle built from half-old pages is
    # the worst possible failure — silent and plausible. Emission is a few
    # minutes; --reuse-pages is for iterating on the packaging alone.
    say("1/7 emitting %s-profile pages%s…"
        % (profile, "" if not reuse_pages else " (reusing the cache)"))
    stage = emit_pages.emit(EDITION, profile, 1, 604, jobs=jobs,
                            force=not reuse_pages, quiet=quiet)
    for p in range(1, 605):
        shutil.copyfile(os.path.join(stage, "%03d.svg" % p),
                        os.path.join(bundle, "pages", "%03d.svg" % p))

    # ---- 2. read the pages back (they are the authority) --------------
    say("2/7 reading %d pages for the index…" % 604)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(jobs) as ex:
        recs = list(ex.map(bundle_extract.read_page_n,
                           [(os.path.join(bundle, "pages"), p)
                            for p in range(1, 605)]))

    # ---- 3. indexes ---------------------------------------------------
    say("3/7 building indexes…")
    manifest = json.load(open(
        os.path.join(ROOT, ".cache", "schema",
                     "edition-hafs-kfgqpc.json"), encoding="utf-8"))
    counts = build_indexes(bundle, recs, manifest)

    # ---- 4. schema + docs ---------------------------------------------
    say("4/7 schemas and docs…")
    build_schemas(bundle)
    shutil.copyfile(os.path.join(REPO, "docs", "shipping", "FORMAT.md"),
                    os.path.join(bundle, "schema", "FORMAT.md"))
    tax = json.load(open(os.path.join(ROOT, ".cache", "schema",
                                      "mark-taxonomy.v2.json"),
                         encoding="utf-8"))
    # the registry ships verbatim apart from the bundle envelope: its own
    # `version` (the taxonomy's) is kept, `schema_version` (the bundle's) added
    tax["schema_version"] = SCHEMA_VERSION
    tax["edition"] = EDITION_ID
    jdump(tax, os.path.join(bundle, "schema", "mark-taxonomy.json"))
    # The real licence, decided by Abdullah 2026-08-30: follow quran-svg's
    # model — CC0 for our own contribution, the publishers' terms untouched for
    # the ink. Copied from the repository root so there is ONE source of truth;
    # the placeholder below is kept only as the fallback for a checkout that
    # somehow lacks them, and a bundle built that way says so plainly.
    _lic = os.path.join(ROOT, "LICENSE")
    _notice = os.path.join(ROOT, "NOTICE.md")
    if os.path.exists(_lic):
        shutil.copyfile(_lic, os.path.join(bundle, "LICENSE"))
    else:
        with open(os.path.join(bundle, "LICENSE"), "w", encoding="utf-8") as fh:
            fh.write(LICENSE_PLACEHOLDER)
    if os.path.exists(_notice):
        shutil.copyfile(_notice, os.path.join(bundle, "NOTICE.md"))

    # optional: the JS library, when there is one to ship (--lib DIR)
    if lib and os.path.isdir(lib):
        dest = os.path.join(bundle, "lib")
        os.makedirs(dest, exist_ok=True)
        for f in sorted(os.listdir(lib)):
            src = os.path.join(lib, f)
            if os.path.isfile(src) and not f.startswith("."):
                shutil.copyfile(src, os.path.join(dest, f))

    # ---- 5. compression ------------------------------------------------
    targets = []
    if gzip_pages or brotli_pages:
        say("5/7 pre-compressing…")
        for p in range(1, 605):
            targets.append(os.path.join(bundle, "pages", "%03d.svg" % p))
        for name in ("pages.json", "surahs.json", "divisions.json",
                     "words.json"):
            targets.append(os.path.join(bundle, "index", name))
        for p in range(1, 605):
            targets.append(os.path.join(bundle, "index", "by-page",
                                        "%03d.json" % p))
        with ProcessPoolExecutor(jobs) as ex:
            list(ex.map(_compress_one,
                        [(t, gzip_pages, brotli_pages, 11) for t in targets]))
    else:
        say("5/7 pre-compression skipped")

    # ---- 6. VERSION.json + README --------------------------------------
    say("6/7 VERSION, README…")
    marks = sum(r["marks"] for r in recs)
    art_commit, art_dirty = git_commit(ROOT)
    pipe_commit, pipe_dirty = git_commit(REPO)
    version = {
        "schema": "quran-svg/version",
        "schema_version": SCHEMA_VERSION,
        "edition": EDITION_ID,
        "print": manifest.get("print"),
        "profile": profile,
        # a DATE, not a clock reading: two builds on the same day are identical
        "build_date": datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%d"),
        "artwork_commit": art_commit,
        "artwork_dirty": art_dirty,
        "artwork_note": "the artwork worktree carries add_line_structure.py's "
                        "in-place per-line rewrite, so it is dirty by design",
        "pipeline_commit": pipe_commit,
        "pipeline_dirty": pipe_dirty,
        "counts": {
            "pages": counts["pages"],
            "surahs": counts["surahs"],
            "ayahs": len({a for r in recs for a in r["ayat"]}),
            "words": counts["words"],
            "marks": marks,
            "rub_boundaries": counts["rub"],
        },
        "compression": {"brotli": bool(brotli_pages) and "quality 11",
                        "gzip": bool(gzip_pages) and "level 9, mtime 0"},
    }
    jdump(version, os.path.join(bundle, "VERSION.json"))

    def sz(rel):
        return human(os.path.getsize(os.path.join(bundle, rel)))

    nfiles = 2 + sum(1 for _dp, _dn, fn in os.walk(bundle) for f in fn
                     if not f.endswith((".br", ".gz")))   # +README/+CHECKSUMS
    archive_section = "" if not archive else ARCHIVE_SECTION.format(
        bundle=BUNDLE_NAME, file_count="{:,}".format(nfiles))
    lib_row = ("| `lib/` | the JavaScript helper library |\n"
               if os.path.isdir(os.path.join(bundle, "lib")) else "")
    readme = README.format(
        archive_section=archive_section, lib_row=lib_row,
        edition=EDITION_ID, print_name=manifest.get("print", ""),
        bundle=BUNDLE_NAME, box_dp=_BOX_DP,
        raw_page=sz("pages/042.svg"),
        br_page=sz("pages/042.svg.br") if brotli_pages else "the compressed page",
        show_page=human(os.path.getsize(os.path.join(bundle, "pages/042.svg.br"))
                        + os.path.getsize(os.path.join(
                            bundle, "index/by-page/042.json.br")))
        if brotli_pages else "—",
        search_all=sz("index/words.json.br") if brotli_pages else "—")
    with open(os.path.join(bundle, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(readme)

    # ---- 7. checksums, then the archive --------------------------------
    say("7/7 checksums…")
    rows = []
    for dirpath, dirnames, filenames in os.walk(bundle):
        dirnames.sort()
        for f in sorted(filenames):
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, bundle)
            if rel == "CHECKSUMS.txt":
                continue
            rows.append((rel, sha256_file(full)))
    rows.sort()
    with open(os.path.join(bundle, "CHECKSUMS.txt"), "w",
              encoding="utf-8") as fh:
        for rel, h in rows:
            fh.write("%s  %s\n" % (h, rel))

    arc = None
    if archive:
        say("    archive…")
        arc = os.path.join(out_root, BUNDLE_NAME + ".tar.gz")
        members = []
        for dirpath, dirnames, filenames in os.walk(bundle):
            dirnames.sort()
            for f in sorted(filenames):
                full = os.path.join(dirpath, f)
                # the archive carries the RAW bundle only; a bulk downloader
                # decompresses once and does not need per-file .br/.gz copies
                if full.endswith((".br", ".gz")):
                    continue
                members.append(full)
        members.sort()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for full in members:
                ti = tf.gettarinfo(full,
                                   arcname=os.path.join(
                                       BUNDLE_NAME,
                                       os.path.relpath(full, bundle)))
                ti.mtime = 0
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                ti.mode = 0o644
                with open(full, "rb") as fh:
                    tf.addfile(ti, fh)
        gz = io.BytesIO()
        with gzip.GzipFile(fileobj=gz, mode="wb", compresslevel=9,
                           mtime=0) as g:
            g.write(buf.getvalue())
        with open(arc, "wb") as fh:
            fh.write(gz.getvalue())
        with open(arc + ".sha256", "w", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (sha256_file(arc), os.path.basename(arc)))

    say("\nbundle: %s" % bundle)
    if arc:
        say("archive: %s (%s)" % (arc, human(os.path.getsize(arc))))
    return bundle


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(REPO, "dist"),
                    help="directory the bundle is written into (default dist/)")
    ap.add_argument("--profile", default="production",
                    choices=("production", "dev"))
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--no-gzip", dest="gzip", action="store_false")
    ap.add_argument("--no-brotli", dest="brotli", action="store_false")
    ap.add_argument("--no-archive", dest="archive", action="store_false")
    ap.add_argument("--reuse-pages", action="store_true",
                    help="trust the staged pages instead of re-emitting; only "
                         "safe when the pipeline has not changed since")
    ap.add_argument("--lib", default=None,
                    help="directory of JS library files to ship as lib/")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    build(a.out, profile=a.profile, jobs=a.jobs, gzip_pages=a.gzip,
          brotli_pages=a.brotli, archive=a.archive, lib=a.lib,
          reuse_pages=a.reuse_pages, quiet=a.quiet)


if __name__ == "__main__":
    main()
