#!/usr/bin/env python3
"""Fetch the word timings for the demo's hero page and cache them.

Source: quran.com's recitation API. Reciter 9 is Mohamed Siddiq al-Minshawi,
Murattal. `fields=segments` is REQUIRED — without it the API returns
`segments: null` with no error, which reads as a bug in your own code.

A segment is [segment_index, word_number, start_ms, end_ms], and `word_number`
is 1-based within the ayah — the third component of our `data-word-key`, so the join
needs no mapping table.

There is ONE MP3 PER AYAH and each ayah's times are relative to its own file.

Writes data/ayah-timings-042.json (~2 KB), which build.py inlines so the section
still works with no network. Run it again to refresh.

Run:  python3 docs/demo/build_ayah_timings.py [page]
"""
import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
RECITER = 9
PAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 42
URL = (f"https://api.quran.com/api/v4/recitations/{RECITER}"
       f"/by_page/{PAGE}?fields=segments&per_page=60")


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    out = {}
    for entry in data["audio_files"]:
        segs = sorted(entry.get("segments") or [], key=lambda s: s[1])
        if not segs:
            raise SystemExit(f"no segments for {entry['verse_key']} — was "
                             f"fields=segments dropped from the query?")
        out[entry["verse_key"]] = [entry["url"], [[s[2], s[3]] for s in segs]]
    blob = json.dumps(out, separators=(",", ":"))
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / f"data/timings-{PAGE:03d}.json").write_text(blob, encoding="utf-8")
    print(f"page {PAGE:03d}: {len(out)} ayahs, "
          f"{sum(len(v[1]) for v in out.values())} word segments, "
          f"{len(blob)} bytes")


if __name__ == "__main__":
    main()
