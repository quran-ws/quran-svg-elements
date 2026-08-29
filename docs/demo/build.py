#!/usr/bin/env python3
"""Assemble docs/demo/index.html: template.html with page 003's SVG inlined.

Reads only .cache/words-svg/hafs-kfqc/003.svg. Run after rebuilding page 3.
"""
import pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SVG = ROOT / ".cache/words-svg/hafs-kfqc/003.svg"

svg = SVG.read_text(encoding="utf-8")
svg = svg.split("?>", 1)[1].strip()          # drop the XML declaration
svg = svg.replace("<svg ", '<svg id="master" ', 1)

tpl = (HERE / "template.html").read_text(encoding="utf-8")
out = tpl.replace("<!--SVG-->", svg)
(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"index.html  {len(out)/1024:.0f} KB  (svg {len(svg)/1024:.0f} KB)")
