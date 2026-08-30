#!/usr/bin/env python3
"""Assemble docs/demo/index.html.

Inlines ONE page (the hero, page 42 — Ayat al-Kursi) into template.html.
Every other page the demo shows is fetched at runtime from PAGES_BASE.

The inlined page is brought to the PRODUCTION profile on the way in:
  * <path class="ayahPolygon"> removed  (dev-only; different frame, sits on top)
  * <g class="ligature"> wrappers dissolved, their paths kept in place
Those two ARE the production profile, so every selector on the demo page is one
that ships.

One further strip goes BEYOND production, and only for size:
  * data-eid / data-sig removed  (~45 KB on this page)
FORMAT.md §2 and §6.5 are explicit that both attributes are present in BOTH
profiles — a shipped production page still carries them. They are review
instruments, `data-eid` is documented as not stable across builds, and nothing
in the demo reads either, so dropping them costs the demo nothing. Do not let
this be mistaken for a statement about what production emits.

Also writes:
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
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("QSVG_ROOT") or HERE.parent.parent).resolve()
SVGDIR = ROOT / ".cache/words-svg/hafs-kfqc"
HERO = 42


def strip_polygons(svg: str) -> str:
    return re.sub(r'<path class="ayahPolygon"[^>]*/>\s*', "", svg)


def drop_dev_attrs(svg: str) -> str:
    """Strip data-eid / data-sig from the inlined page.

    NOT a production-profile property: shipped production pages keep both
    (FORMAT.md §2, §6.5). This is a size-only saving for the demo, which reads
    neither attribute. See the module docstring.
    """
    return re.sub(r'\s(?:data-eid|data-sig)="[^"]*"', "", svg)


def dissolve_ligatures(svg: str) -> str:
    """Remove <g class="ligature" …> … </g> wrappers, keeping their children.

    Depth-counts <g>/</g> from each ligature open tag to find its own close.
    Safe here because the file is machine-generated and well-formed.
    """
    out = []
    i = 0
    open_rx = re.compile(r'<g class="ligature"[^>]*>')
    tag_rx = re.compile(r"<g\b|</g>")
    while True:
        m = open_rx.search(svg, i)
        if not m:
            out.append(svg[i:])
            break
        out.append(svg[i:m.start()])
        depth = 1
        j = m.end()
        while depth:
            t = tag_rx.search(svg, j)
            if not t:
                raise ValueError("unbalanced <g> after ligature at %d" % m.start())
            depth += 1 if t.group(0) == "<g" else -1
            if depth == 0:
                out.append(svg[j:t.start()])
                i = t.end()
            else:
                j = t.end()
    return "".join(out)


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
    raw = (SVGDIR / f"{HERO:03d}.svg").read_text(encoding="utf-8")
    svg = raw.split("?>", 1)[1].strip()
    before = len(svg)
    svg = drop_dev_attrs(dissolve_ligatures(strip_polygons(svg)))
    svg = svg.replace("<svg ", '<svg id="hero" data-page="%d" ' % HERO, 1)

    (HERE / "data").mkdir(exist_ok=True)
    gloss = build_gloss(HERO)
    (HERE / f"data/gloss-{HERO:03d}.json").write_bytes(gloss)

    timings_path = HERE / f"data/timings-{HERO:03d}.json"
    if not timings_path.exists():
        raise SystemExit(f"{timings_path.name} missing — run build_timings.py")
    timings = timings_path.read_text(encoding="utf-8").strip()

    def assemble(tpl_name: str, out_name: str) -> None:
        """Inline the hero page and the cached timings into one template.

        Runs over template.html and, when it exists, template.ar.html — the
        Arabic edition. Both carry the same placeholders, so the Arabic page
        gets the identical artwork: the translation never touches the SVG.
        """
        tpl = (HERE / tpl_name).read_text(encoding="utf-8")
        if "<!--SVG-->" not in tpl:
            raise SystemExit(f"{tpl_name} has no <!--SVG--> placeholder")
        if "/*TIMINGS*/null" not in tpl:
            raise SystemExit(f"{tpl_name} has no /*TIMINGS*/null placeholder")
        out = tpl.replace("<!--SVG-->", svg).replace("/*TIMINGS*/null", timings, 1)
        (HERE / out_name).write_text(out, encoding="utf-8")
        print(f"{out_name:15s} {len(out.encode())/1024:.0f} KB")

    print(f"page {HERO:03d}: {before/1024:.0f} KB dev -> {len(svg)/1024:.0f} KB "
          f"(production profile, less data-eid/data-sig)")
    assemble("template.html", "index.html")
    if (HERE / "template.ar.html").exists():
        assemble("template.ar.html", "index.ar.html")
    print(f"gloss-{HERO:03d}   {len(gloss)/1024:.1f} KB")
    print(f"timings-{HERO:03d} {len(timings)/1024:.1f} KB inlined")


if __name__ == "__main__":
    main()
