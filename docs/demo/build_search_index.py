#!/usr/bin/env python3
"""Build docs/demo/data/search-index.json from the DEV pages' data-search.

77,432 rows of [wordKey, page, search]. ~2.1 MB raw / ~480 KB gzipped, and the demo
fetches it only when someone types in the search box. Reads the dev-profile
cache, which still carries data-search inline; a production page does not
(FORMAT §6.1, 2026-09-04) — its search key is in index/words.json, which is
the same value.

Run:  QSVG_ROOT=$PWD python3 docs/demo/build_search_index.py
"""
import gzip
import json
import os
import pathlib
import re
from concurrent.futures import ProcessPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("QSVG_ROOT") or HERE.parent.parent).resolve()
SVGDIR = ROOT / ".cache/words-svg/hafs-kfqc"
RX = re.compile(r'<g class="word" data-word-key="([^"]+)"[^>]*data-search="([^"]*)"')


def one(page: int):
    text = (SVGDIR / f"{page:03d}.svg").read_text(encoding="utf-8")
    return [[wordKey, page, search] for wordKey, search in RX.findall(text)]


def main() -> None:
    with ProcessPoolExecutor(32) as ex:
        rows = [r for part in ex.map(one, range(1, 605)) for r in part]
    blob = json.dumps(
        {"fields": ["word_key", "page", "search"], "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data/search-index.json").write_bytes(blob)
    print(f"{len(rows)} rows  {len(blob)/1024:.0f} KB raw  "
          f"{len(gzip.compress(blob, 9))/1024:.0f} KB gzipped")


if __name__ == "__main__":
    main()
