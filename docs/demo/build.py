#!/usr/bin/env python3
"""Assemble docs/demo/index.html.

NOTHING IS INLINED ANY MORE. The hero (page 42, Ayahs al-Kursi) used to be
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

`data-element-id` / `data-sig` used to be stripped here as well, purely to save the
~45 KB they cost in an inlined page. Nothing inlines a page now, so nothing
strips them, and the demo is closer to a file you would actually download.

This script now only writes:
  data/gloss-042.json   {wordKey: [english, transliteration]}  (source: quran.com)

and inlines, at the /*TIMINGS*/ placeholder, the cached word timings for the
hero page written by build_ayah_timings.py. They are ~2 KB and exist only so the
audio section still renders and explains itself with no network. The section
itself fetches live; this is the fallback.

data/search-index.json is built separately by build_search_index.py

It also vendors ONE mushaf's ornaments from a clone of quran-ws/quran-assets
into data/ornaments/, as the offline fallback for the "dress the page" section.
See vendor_ornaments() for what is copied and why it is only one style.

Run:  QSVG_ROOT=$PWD python3 docs/demo/build.py
"""
import json
import os
import pathlib
import shutil

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("QSVG_ROOT") or HERE.parent.parent).resolve()
SVGDIR = ROOT / ".cache/words-svg/hafs-kfqc"
HERO = 42

# ── the ornament fallback ──────────────────────────────────────────────────
# The section fetches quran-ws/quran-assets at runtime and ships no outline of
# its own — except this one set, so the section is never simply dead. It is ONE
# style because the whole catalogue is 2.9 MB of colour/mono/line and this is a
# fallback, not the product; the live fetch is where the other seven mushafs
# come from.
#
# Only `color.svg` is taken. Mono and line are the same drawing with the paint
# removed, and the section recolours through CSS anyway — a `line` variant would
# add ~120 KB to say what a stylesheet already says.
#
# LICENSING. Every asset in that repository is `redistributable: false` while
# written permission is sought from the mushaf publishers (its LICENSE.md and
# docs/PLAN.md §6). What is copied here is copied under the same terms and the
# catalogue entry carries them; the section prints them on screen. Publishing
# this demo publishes them, so read that file before you do.
ORNAMENT_STYLE = "qalon"
ORNAMENT_TYPES = ("ayah-markers", "surah-headers", "page-frames")


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


def vendor_ornaments() -> str:
    """Copy one style out of a quran-assets clone, with a catalog cut to it.

    The clone is found at $QURAN_ASSETS, or beside the repository, or through
    the docs/demo/ornaments symlink a developer may already have made. Missing
    is not an error: the vendored copy that is already committed stays, and a
    checkout that has never had one gets a section that falls back to nothing
    and says so.
    """
    dest = HERE / "data/ornaments"
    cand = [os.environ.get("QURAN_ASSETS"), HERE / "ornaments",
            ROOT.parent / "quran-assets", ROOT / "../quran-assets"]
    src = next((pathlib.Path(c) for c in cand
                if c and (pathlib.Path(c) / "catalog.json").exists()), None)
    if src is None:
        have = (dest / "catalog.json").exists()
        return ("ornaments  no quran-assets clone found; "
                + ("keeping the vendored fallback" if have else "no fallback vendored")
                + " (set QURAN_ASSETS=/path/to/quran-assets)")

    cat = json.loads((src / "catalog.json").read_text(encoding="utf-8"))
    keep, files = [], 0
    for a in cat["assets"]:
        if a["style"] != ORNAMENT_STYLE or a["type"] not in ORNAMENT_TYPES:
            continue
        # the delivered catalog names only what is delivered: a variant listed
        # but not copied is a 404 the section cannot tell from a dead host
        paths = [a["variants"]["color"]]
        a["variants"] = {"color": a["variants"]["color"]}
        a.pop("source_crop", None)
        paths += list((a.get("slices") or {}).get("files", {}).values())
        for rel in paths:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / rel, dest / rel)
            files += 1
        keep.append(a)
    if not keep:
        raise SystemExit(f"{src} holds no {ORNAMENT_STYLE} assets — wrong clone?")

    cat["assets"] = keep
    cat["count"] = len(keep)
    cat["fallback"] = {
        "of": "quran-ws/quran-assets",
        "style": ORNAMENT_STYLE,
        "note": "one style, colour variant only. The live fetch carries all 8 mushafs.",
        "pipeline_commit": keep[0].get("pipeline_commit"),
    }
    (dest / "catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = sum(f.stat().st_size for f in dest.rglob("*.svg")) / 1024
    return f"ornaments  {ORNAMENT_STYLE}, {files} files, {kb:.0f} KB from {src}"


def main() -> None:
    if not (SVGDIR / f"{HERO:03d}.svg").exists():
        raise SystemExit(f"page {HERO:03d} missing from {SVGDIR} — the demo "
                         "fetches it at runtime and cannot show the hero without it")

    (HERE / "data").mkdir(exist_ok=True)
    gloss = build_gloss(HERO)
    (HERE / f"data/gloss-{HERO:03d}.json").write_bytes(gloss)

    ayah_timings_path = HERE / f"data/timings-{HERO:03d}.json"
    if not ayah_timings_path.exists():
        raise SystemExit(f"{ayah_timings_path.name} missing — run build_ayah_timings.py")
    timings = ayah_timings_path.read_text(encoding="utf-8").strip()

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
    print(vendor_ornaments())
    print(f"page {HERO:03d} is NOT inlined — fetched at runtime like every other page")


if __name__ == "__main__":
    main()
