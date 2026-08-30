#!/usr/bin/env python3
"""Assemble docs/demo/index.html.

NOTHING IS INLINED ANY MORE. The hero (page 42, Ayat al-Kursi) used to be
inlined and was 745 KiB of the 965 KiB index.html weighed. It is now fetched at
runtime from the same place and through the same cache as every other page the
demo shows, so page 42 costs one request however many sections stage it.

The production-profile transform that used to happen here happens in the
browser instead, in the `heroReady` block of the template:
  * <path class="ayahPolygon"> removed  (dev-only; different frame, sits on top)
    -- done for every page by getPage()
  * <g class="ligature"> wrappers dissolved, their paths kept in place
    -- done for the hero only, since the demo teaches how to detect the dev
       profile by looking for that layer on the pages it fetches

`data-eid` / `data-sig` used to be stripped here as well, purely to save the
~45 KB they cost in an inlined page. Nothing inlines a page now, so nothing
strips them, and the demo is closer to a file you would actually download.

This script now only writes:
  data/gloss-042.json   {wid: [english, transliteration]}  (source: quran.com)

and inlines, at the /*TIMINGS*/ placeholder, the cached word timings for the
hero page written by build_timings.py. They are ~2 KB and exist only so the
audio section still renders and explains itself with no network. The section
itself fetches live; this is the fallback.

data/search-index.json is built separately by build_search_index.py

Run:  QSVG_ROOT=$PWD python3 docs/demo/build.py
"""
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("QSVG_ROOT") or HERE.parent.parent).resolve()
SVGDIR = ROOT / ".cache/words-svg/hafs-kfqc"
HERO = 42


def build_gloss(page: int) -> bytes:
    src = ROOT / f".cache/words/page-{page:03d}.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    gloss = {}
    for v in data["verses"]:
        for w in v["words"]:
            if w.get("char_type_name") != "word":
                continue
            gloss[f"{v['verse_key']}:{w['position']}"] = [
                w["translation"]["text"],
                w["transliteration"]["text"],
            ]
    return json.dumps(gloss, ensure_ascii=False, separators=(",", ":")).encode()


def main() -> None:
    if not (SVGDIR / f"{HERO:03d}.svg").exists():
        raise SystemExit(f"page {HERO:03d} missing from {SVGDIR} — the demo "
                         "fetches it at runtime and cannot show the hero without it")

    (HERE / "data").mkdir(exist_ok=True)
    gloss = build_gloss(HERO)
    (HERE / f"data/gloss-{HERO:03d}.json").write_bytes(gloss)

    timings_path = HERE / f"data/timings-{HERO:03d}.json"
    if not timings_path.exists():
        raise SystemExit(f"{timings_path.name} missing — run build_timings.py")
    timings = timings_path.read_text(encoding="utf-8").strip()

    def assemble(tpl_name: str, out_name: str) -> None:
        """Inline the cached timings into one template.

        Runs over template.html and, when it exists, template.ar.html — the
        Arabic edition. Both carry the same placeholder.
        """
        tpl = (HERE / tpl_name).read_text(encoding="utf-8")
        if "<!--SVG-->" in tpl:
            raise SystemExit(f"{tpl_name} still has an <!--SVG--> placeholder — "
                             "the hero is fetched now, nothing fills that in")
        if "/*TIMINGS*/null" not in tpl:
            raise SystemExit(f"{tpl_name} has no /*TIMINGS*/null placeholder")
        out = tpl.replace("/*TIMINGS*/null", timings, 1)
        (HERE / out_name).write_text(out, encoding="utf-8")
        print(f"{out_name:15s} {len(out.encode())/1024:.0f} KB")

    assemble("template.html", "index.html")
    if (HERE / "template.ar.html").exists():
        assemble("template.ar.html", "index.ar.html")
    print(f"gloss-{HERO:03d}   {len(gloss)/1024:.1f} KB")
    print(f"timings-{HERO:03d} {len(timings)/1024:.1f} KB inlined")
    print(f"page {HERO:03d} is NOT inlined — fetched at runtime like every other page")


if __name__ == "__main__":
    main()
