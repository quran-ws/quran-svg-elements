#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools>=4.60",
#   "skia-pathops>=0.8.0",
# ]
# ///
"""Add the official KFGQPC surah frame to a quran-svg page.

Pages 3–604 carry one compact cartouche per title. The integrated opening-page
frames belong to page furniture and are prepared separately by `prepare_page_frames.py`.

Run this after `add_line_structure.py`. Every cartouche is bound explicitly to its surah
and printed line, so neither line assignment nor the semantic pipeline infers ownership
from geometry or document order.

    uv run tools/add_surah_ornaments.py 604.ai mushafs/hafs/kfqc/svg/604.svg \
      --headers 112:1,113:5,114:10
"""

import argparse
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pathops
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
PATH_RE = re.compile(
    r'<path\b(?=[^>]*\bdata-kind="ornament")'
    r'(?=[^>]*\bdata-surah-ornament="1")'
    r'(?=[^>]*\bdata-surah="(?P<surah>\d+)")[^>]*/>'
)


def multiply(left, right):
    a, b, c, d, e, f = left
    g, h, i, j, k, l = right
    return (
        a * g + c * h,
        b * g + d * h,
        a * i + c * j,
        b * i + d * j,
        a * k + c * l + e,
        b * k + d * l + f,
    )


def inverse(matrix):
    a, b, c, d, e, f = matrix
    determinant = a * d - b * c
    if abs(determinant) < 1e-12:
        raise ValueError("singular source transform")
    return (
        d / determinant,
        -b / determinant,
        -c / determinant,
        a / determinant,
        (c * f - d * e) / determinant,
        (b * e - a * f) / determinant,
    )


def parse_transform(value):
    if not value:
        return IDENTITY
    result = IDENTITY
    for name, arguments in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", value):
        values = [float(item) for item in re.split(r"[ ,]+", arguments.strip()) if item]
        if name == "matrix" and len(values) == 6:
            current = tuple(values)
        elif name == "translate" and 1 <= len(values) <= 2:
            current = (1.0, 0.0, 0.0, 1.0, values[0], values[1] if len(values) == 2 else 0.0)
        elif name == "scale" and 1 <= len(values) <= 2:
            current = (values[0], 0.0, 0.0, values[1] if len(values) == 2 else values[0], 0.0, 0.0)
        else:
            raise ValueError(f"unsupported SVG transform: {name}({arguments})")
        result = multiply(result, current)
    return result


def transformed(path, matrix):
    output = pathops.Path()
    path.draw(TransformPen(output.getPen(), matrix))
    output.fillType = path.fillType
    return output


def parse_svg_path(data, matrix, even_odd):
    output = pathops.Path()
    parse_path(data, TransformPen(output.getPen(), matrix))
    output.fillType = pathops.FillType.EVEN_ODD if even_odd else pathops.FillType.WINDING
    return output


def number(value, places=6):
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def path_data(path):
    commands = []
    for verb, points in path.segments:
        places = 3 if verb == "moveTo" else 6
        values = " ".join(number(value, places) for point in points for value in point)
        if verb == "moveTo":
            commands.append("M" + values)
        elif verb == "lineTo":
            commands.append("L" + values)
        elif verb == "curveTo":
            commands.append("C" + values)
        elif verb == "qCurveTo":
            commands.append("Q" + values)
        elif verb == "closePath":
            commands.append("Z")
        elif verb == "endPath":
            pass
        else:
            raise ValueError(f"unsupported path verb: {verb}")
    return "".join(commands)


def read_source_svg(source, mutool):
    with tempfile.TemporaryDirectory(prefix="surah-ornament-") as directory:
        output = Path(directory) / "page-%d.svg"
        subprocess.run(
            [mutool, "draw", "-q", "-F", "svg", "-o", str(output), str(source), "1"],
            check=True,
        )
        page = Path(directory) / "page-1.svg"
        if not page.exists():
            raise RuntimeError("MuPDF did not write page-1.svg")
        return page.read_text()


def source_paths(svg):
    # MuPDF writes an unescaped ampersand in layer names such as
    # "Header & Marks & Page No.". Repair only bare ampersands before parsing.
    svg = re.sub(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|\w+;)", "&amp;", svg)
    root = ET.fromstring(svg)
    view_box = [float(value) for value in root.get("viewBox", "").split()]
    if len(view_box) != 4:
        raise ValueError("source SVG has no four-number viewBox")
    rows = []

    def walk(node, parent=IDENTITY, layer=None, fill="black", fill_rule="nonzero"):
        matrix = multiply(parent, parse_transform(node.get("transform")))
        layer = node.get("data-name", layer)
        fill = node.get("fill", fill)
        fill_rule = node.get("fill-rule", fill_rule)
        if node.tag.rsplit("}", 1)[-1] == "path":
            path = parse_svg_path(node.get("d", ""), matrix, fill_rule == "evenodd")
            rows.append({"layer": layer or "", "fill": fill.lower(), "matrix": matrix, "path": path})
        for child in node:
            walk(child, matrix, layer, fill, fill_rule)

    walk(root)
    return view_box, rows


def frame_paths(source_svg, expected):
    view_box, rows = source_paths(source_svg)
    _, _, width, height = view_box
    ornaments = []
    white = []
    text = []
    fallback_text = []
    for row in rows:
        x0, y0, x1, y1 = row["path"].bounds
        path_width, path_height = x1 - x0, y1 - y0
        layer = row["layer"].strip().lower().rstrip("s")
        if layer == "ornament" and path_width > width * 0.5 and path_height < height * 0.12:
            ornaments.append(row["path"])
        source_layer = row["layer"].strip().lower()
        if source_layer == "quran text":
            if row["fill"] in {"#fff", "#ffffff", "white"}:
                white.append(row["path"])
            elif row["fill"] in {"black", "#000", "#000000"}:
                text.append(row)
        elif source_layer == "layer 1" and row["fill"] in {"black", "#000", "#000000"}:
            # Pages 545 and 598 are the only 1441H files whose body group lost the
            # `Quran Text` layer name. Each has exactly one `Layer 1` body path, and
            # prepared_page independently checks its transform against every target line.
            fallback_text.append(row)
    ornaments.sort(key=lambda path: path.bounds[1])
    if len(ornaments) != expected:
        raise ValueError(f"found {len(ornaments)} surah cartouches, expected {expected}")
    if not text:
        if len(fallback_text) != 1:
            raise ValueError(
                f"source SVG has no Quran Text path and {len(fallback_text)} Layer 1 candidates"
            )
        text = fallback_text
    text_record = max(text, key=lambda row: (row["path"].bounds[2] - row["path"].bounds[0])
                                      * (row["path"].bounds[3] - row["path"].bounds[1]))
    knockout = None
    for path in white:
        knockout = path if knockout is None else pathops.op(
            knockout, path, pathops.PathOp.UNION
        )
    frames = []
    for ornament in ornaments:
        # Normal pages use both source forms. Keep an ornament that already carries an
        # even-odd opening byte-for-byte at the vector level; only invoke path boolean
        # operations where separate white artwork must become transparent.
        frame = ornament
        if knockout is not None:
            frame = pathops.op(frame, knockout, pathops.PathOp.DIFFERENCE)
            frame.fillType = pathops.FillType.WINDING
        x0, y0, x1, y1 = frame.bounds
        if frame.contains(((x0 + x1) / 2.0, (y0 + y1) / 2.0)):
            raise ValueError("surah cartouche has no transparent centre")
        frames.append(frame)
    return view_box, text_record["matrix"], frames


def line_target(svg, line):
    pattern = re.compile(
        r'<g class="line" data-line="%d"[^>]*>\s*'
        r'<g transform="translate\(([-\d.]+)[ ,]+([-\d.]+)\)">' % line
    )
    matches = list(pattern.finditer(svg))
    if len(matches) != 1:
        raise ValueError("printed line %d has %d target groups" % (line, len(matches)))
    match = matches[0]
    return match, (float(match.group(1)), float(match.group(2)))


def prepared_page(source_svg, target_svg, headers):
    requested = [surah for surah, _ in headers]
    lines = [line for _, line in headers]
    if (not headers or len(set(requested)) != len(headers)
            or len(set(lines)) != len(headers)):
        raise ValueError("headers must contain distinct surah and line numbers")
    if lines != sorted(lines):
        raise ValueError("headers must be listed in top-to-bottom line order")
    existing = [int(match.group("surah")) for match in PATH_RE.finditer(target_svg)]
    if existing and existing != requested:
        raise ValueError(
            "target already has surah ornaments for %r, not %r" % (existing, requested)
        )
    if any(surah in {1, 2} for surah in requested):
        raise ValueError("opening surahs use the page-frame pipeline")
    view_box, text_matrix, frames = frame_paths(source_svg, len(headers))
    target_svg = PATH_RE.sub("", target_svg)
    _, _, _, source_height = view_box
    *_, e, f = text_matrix
    expected = (e, source_height - f)
    to_line = inverse(text_matrix)
    for (surah, line), frame in zip(headers, frames):
        opening, translation = line_target(target_svg, line)
        if any(abs(actual - wanted) > 0.02 for actual, wanted in zip(translation, expected)):
            raise ValueError(
                "source Quran Text frame does not match line %d: source=%r, target=%r"
                % (line, expected, translation)
            )
        local = transformed(frame, to_line)
        fill_rule = (
            ' fill-rule="evenodd"'
            if local.fillType == pathops.FillType.EVEN_ODD else ""
        )
        tag = (
            '<path data-kind="ornament" data-surah-ornament="1" '
            'data-surah="%d" fill="#231f20"%s d="%s"/>'
            % (surah, fill_rule, path_data(local))
        )
        at = opening.end()
        target_svg = target_svg[:at] + tag + target_svg[at:]
    return target_svg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="official Illustrator/PDF page")
    parser.add_argument("target", type=Path, help="quran-svg page to update")
    parser.add_argument("--headers", required=True, help="comma-separated surah:line pairs, top to bottom")
    parser.add_argument("--mutool", default="mutool", help="MuPDF executable")
    parser.add_argument("--check", action="store_true", help="fail when the target is not current")
    args = parser.parse_args(argv)
    try:
        headers = [tuple(int(part) for part in value.split(":"))
                   for value in args.headers.split(",") if value]
    except ValueError:
        parser.error("--headers must contain surah:line integer pairs")
    if (not headers or any(len(header) != 2 for header in headers)
            or len({header[0] for header in headers}) != len(headers)
            or len({header[1] for header in headers}) != len(headers)):
        parser.error("--headers must contain distinct surah:line pairs")
    if [line for _, line in headers] != sorted(line for _, line in headers):
        parser.error("--headers must be listed in top-to-bottom line order")
    before = args.target.read_text()
    after = prepared_page(read_source_svg(args.source, args.mutool), before, headers)
    if args.check:
        if before != after:
            print(f"stale: {args.target}")
            return 1
        print(f"ok: {args.target}")
        return 0
    if before == after:
        print(f"unchanged: {args.target}")
    else:
        args.target.write_text(after)
        print(f"updated: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
