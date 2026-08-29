#!/usr/bin/env python3
"""Assemble nojs.html from nojs-template.html and 003-embed.svg.

The page contains no script of any kind; the builder only fills in the
repetitive markup (one control and one <img> per ayah, per ornament).
"""
import pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
tpl = (HERE / "nojs-template.html").read_text(encoding="utf-8")
svg = (HERE / "003-embed.svg").read_text(encoding="utf-8")
svg = svg.split("?>", 1)[1].strip() if svg.startswith("<?xml") else svg

AYAHS = list(range(6, 17))
ORNS  = [("printed", None), ("ring", "ring"), ("double ring", "double"),
         ("diamond", "diamond"), ("star", "star"), ("rosette", "rosette"),
         ("brackets", "brackets")]

def radio(gid, rid, label, checked=False):
    c = " checked" if checked else ""
    return (f'<input class="ctl" type="radio" name="{gid}" id="{rid}"{c}>'
            f'<label for="{rid}">{label}</label>')

# --- ayah crops -------------------------------------------------------------
tpl = tpl.replace("<!--AYAH-PILLS-->",
    "".join(radio("ayah", f"a{a}", a, a == 10) for a in AYAHS))
tpl = tpl.replace("<!--AYAH-IMGS-->",
    "".join(f'<img class="i{a}" src="003-embed.svg#v-ayah-{a}" alt="Surah 2, ayah {a}">'
            for a in AYAHS))
tpl = tpl.replace("<!--CROP-CSS-->",
    ",\n".join(f"#crop:has(#a{a}:checked) .frame .i{a}" for a in AYAHS) + "{display:block}")

# --- ornaments --------------------------------------------------------------
tpl = tpl.replace("<!--ORN-PILLS-->",
    "".join(radio("orn", f"o{i}", name, i == 0) for i, (name, _) in enumerate(ORNS)))
tpl = tpl.replace("<!--ORN-IMGS-->",
    "".join(f'<img class="n{i}" src="003-embed.svg{"#set-" + key if key else ""}"'
            f' alt="Page 3, {name} ornament">'
            for i, (name, key) in enumerate(ORNS)))
tpl = tpl.replace("<!--ORN-CSS-->",
    ",\n".join(f"#orn:has(#o{i}:checked) .frame .n{i}" for i in range(len(ORNS)))
    + "{display:block}")

# --- the three inline copies ------------------------------------------------
tpl = tpl.replace("<!--SPACE-PILLS-->", "".join([
    radio("sp", "sp0", "as printed", True), radio("sp", "sp1", "lines"),
    radio("sp", "sp2", "words"), radio("sp", "sp3", "both")]))
tpl = tpl.replace("<!--COLOUR-PILLS-->", "".join([
    radio("c", "c0", "as printed", True), radio("c", "c1", "ink &amp; gold"),
    radio("c", "c2", "teaching"), radio("c", "c3", "letters only")]))
tpl = tpl.replace("<!--RUN-PILLS-->", "".join([
    radio("w", "w0", "all 19", True), radio("w", "w1", "1–4"),
    radio("w", "w2", "5–9"), radio("w", "w3", "12–19")]))

for i in (1, 2, 3):
    tpl = tpl.replace(f"<!--INLINE-SVG-{i}-->", svg.replace('id="page3"', f'id="inline{i}"', 1))

out = HERE / "nojs.html"
out.write_text(tpl, encoding="utf-8")
assert "<script" not in tpl.lower(), "a script slipped into the no-script page"
print(f"nojs.html  {len(tpl)/1024:.0f} KB  (no <script> anywhere)")
