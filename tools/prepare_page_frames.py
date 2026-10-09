#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools>=4.60",
#   "skia-pathops>=0.8.0",
# ]
# ///
"""Restore the native KFGQPC page frame to every prepared page.

The 1441H source corpus contains one integrated opening frame on pages 1–2 and
an ordinary recto/verso frame on pages 3–604. A corpus audit found eight exact
ordinary path variants; the manifest maps each page to one of those source
outlines without normalising away the small source differences.

Run after line-structure preparation and before semantic page emission:

    uv run tools/prepare_page_frames.py --root /path/to/quran-svg
    uv run tools/prepare_page_frames.py --root /path/to/quran-svg --offline --check
"""

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from add_surah_ornaments import (
    number,
    parse_transform,
    path_data,
    read_source_svg,
    source_paths,
    transformed,
)
from prepare_surah_ornaments import fetch_source
from svg_lines import transform_box

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO / "conformance" / "page-frames.json"
DEFAULT_CACHE = REPO / ".cache" / "page-frames"
VARIANT_FIELDS = {
    "role", "source_page", "bytes", "crc32", "sha256", "frame_sha256",
}
PAGE_FRAME_RE = re.compile(
    r'<path\b(?=[^>]*\bdata-kind="ornament")'
    r'(?=[^>]*\bdata-page-frame="(?P<variant>[^"]+)")[^>]*/>',
    re.DOTALL,
)


def load_manifest(path=DEFAULT_MANIFEST):
    data = json.loads(Path(path).read_text())
    if data.get("schema") != "page-frames" or data.get("schema_version") != "1.0.0":
        raise ValueError("unsupported page-frame manifest")
    if data.get("edition") != "hafs-kfgqpc":
        raise ValueError("page-frame manifest must target hafs-kfgqpc")

    source = data.get("source")
    audit = data.get("corpus_audit")
    defaults = data.get("defaults")
    overrides = data.get("overrides")
    variants = data.get("variants")
    if not isinstance(source, dict):
        raise TypeError("page-frame source must be an object")
    if audit != {
        "pages": 604,
        "ordinary_variants": 8,
        "max_variant_coordinate_delta": 0.001007080078125,
    }:
        raise ValueError("unexpected page-frame corpus audit")
    if defaults is None or set(defaults) != {"odd", "even"}:
        raise ValueError("page-frame defaults must contain odd and even")
    if not isinstance(overrides, dict) or not isinstance(variants, dict):
        raise TypeError("page-frame overrides and variants must be objects")
    if source.get("archive") != "1441-AI-hafs.zip" or source.get("archive_bytes") != 466430736:
        raise ValueError("unexpected official page-frame source archive")
    if not re.fullmatch(r"[0-9a-f]{64}", source.get("archive_sha256", "")):
        raise ValueError("page-frame source needs the archive SHA-256")
    if not source.get("base_url", "").startswith("https://"):
        raise ValueError("page-frame source needs an HTTPS base URL")
    if source.get("filename") != "{page:03d}___Hafs39__DM.ai":
        raise ValueError("unexpected official page-frame filename pattern")

    source_pages = set()
    frame_hashes = set()
    for name, variant in variants.items():
        if not isinstance(name, str) or not name or not isinstance(variant, dict):
            raise ValueError("invalid page-frame variant")
        if set(variant) != VARIANT_FIELDS:
            raise ValueError(f"page-frame variant {name!r} has unexpected fields")
        role = variant["role"]
        page = variant["source_page"]
        if role not in {"opening", "odd", "even"}:
            raise ValueError(f"page-frame variant {name!r} has invalid role")
        if not isinstance(page, int) or not 1 <= page <= 604 or page in source_pages:
            raise ValueError(f"page-frame variant {name!r} has invalid source page")
        if role == "opening" and page not in {1, 2}:
            raise ValueError(f"opening page-frame variant {name!r} has invalid source page")
        if role in {"odd", "even"} and (page < 3 or (page % 2 == 1) != (role == "odd")):
            raise ValueError(f"page-frame variant {name!r} has the wrong parity")
        if not isinstance(variant["bytes"], int) or variant["bytes"] <= 0:
            raise ValueError(f"page-frame variant {name!r} has invalid source size")
        if not re.fullmatch(r"[0-9a-f]{8}", variant["crc32"]):
            raise ValueError(f"page-frame variant {name!r} has invalid CRC32")
        if not re.fullmatch(r"[0-9a-f]{64}", variant["sha256"]):
            raise ValueError(f"page-frame variant {name!r} has invalid SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", variant["frame_sha256"]):
            raise ValueError(f"page-frame variant {name!r} has invalid frame SHA-256")
        if variant["frame_sha256"] in frame_hashes:
            raise ValueError(f"page-frame variant {name!r} duplicates another frame")
        source_pages.add(page)
        frame_hashes.add(variant["frame_sha256"])

    if any(name not in variants for name in defaults.values()):
        raise ValueError("page-frame defaults name unknown variants")
    parsed_overrides = {}
    for raw_page, name in overrides.items():
        if not re.fullmatch(r"[1-9]\d*", raw_page):
            raise ValueError(f"invalid page-frame override page {raw_page!r}")
        page = int(raw_page)
        if not 1 <= page <= 604 or name not in variants:
            raise ValueError(f"invalid page-frame override {raw_page!r}: {name!r}")
        parsed_overrides[page] = name

    assignments = {}
    for page in range(1, 605):
        name = parsed_overrides.get(page)
        if name is None:
            if page <= 2:
                raise ValueError(f"opening page {page} needs an explicit page-frame variant")
            name = defaults["odd" if page % 2 else "even"]
        role = variants[name]["role"]
        expected = "opening" if page <= 2 else ("odd" if page % 2 else "even")
        if role != expected:
            raise ValueError(f"page {page} uses {role} page-frame variant {name!r}")
        assignments[page] = name
    for name, variant in variants.items():
        if assignments[variant["source_page"]] != name:
            raise ValueError(f"variant {name!r} is not assigned to its source page")
    return source, variants, assignments


def frame_path(source_svg, opening):
    view_box, rows = source_paths(source_svg)
    _, _, width, height = view_box
    candidates = []
    for row in rows:
        x0, y0, x1, y1 = row["path"].bounds
        path_width, path_height = x1 - x0, y1 - y0
        layer = row["layer"].strip().lower().rstrip("s")
        if layer != "ornament":
            continue
        if opening:
            selected = path_width > width * 0.5 and path_height > height * 0.4
        else:
            selected = path_width > width * 0.65 and path_height > height * 0.65
        if selected:
            candidates.append(row["path"])
    if len(candidates) != 1:
        raise ValueError(f"found {len(candidates)} native page frames, expected one")
    frame = candidates[0]
    import pathops  # imported lazily so metadata-only bundle checks need no geometry dependency
    if frame.fillType != pathops.FillType.EVEN_ODD:
        raise ValueError("native page frame must use even-odd fill")
    contours = sum(verb == "moveTo" for verb, _ in frame.segments)
    expected = 3 if opening else 2
    if contours != expected:
        raise ValueError(f"native page frame has {contours} contours, expected {expected}")
    return view_box, frame


def prepared_tag(source_svg, variant_name, variant):
    opening = variant["role"] == "opening"
    view_box, frame = frame_path(source_svg, opening)
    source_d = path_data(frame)
    got = hashlib.sha256(source_d.encode()).hexdigest()
    if got != variant["frame_sha256"]:
        raise ValueError(
            f"page-frame variant {variant_name!r} has source geometry {got}, "
            f"expected {variant['frame_sha256']}"
        )
    _, _, _, height = view_box
    local = transformed(frame, (1.0, 0.0, 0.0, -1.0, 0.0, height))
    bounds = " ".join(number(value) for value in local.bounds)
    return (
        f'<path data-kind="ornament" data-page-frame="{variant_name}" '
        f'data-page-frame-box="{bounds}" fill="#231f20" '
        f'fill-rule="evenodd" d="{path_data(local)}"/>'
    )


def target_path(root, page):
    return Path(root) / "mushafs" / "hafs" / "kfqc" / "svg" / f"{page:03}.svg"


def _box(value, what):
    try:
        values = [float(part) for part in value.replace(",", " ").split()]
    except (AttributeError, ValueError) as error:
        raise ValueError(f"{what} must contain four numbers") from error
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        raise ValueError(f"{what} must contain x, y, positive width and height")
    return values


def _bounds(value, what):
    try:
        values = [float(part) for part in value.replace(",", " ").split()]
    except (AttributeError, ValueError) as error:
        raise ValueError(f"{what} must contain four numbers") from error
    if len(values) != 4 or values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError(f"{what} must contain x0, y0, x1 and y1")
    return values


def _format_visual_box(values):
    return " ".join(number(value, 3) for value in values)


def _format_content_box(values):
    return " ".join(number(value, 6) for value in values)


def _visual_box(svg, tag):
    root = re.search(r'<svg\b[^>]*>', svg)
    if root is None:
        raise ValueError("target has no SVG root")
    root_tag = root.group(0)
    view = re.search(r'\bviewBox="([^"]+)"', root_tag)
    if view is None:
        raise ValueError("target SVG has no viewBox")
    content = re.search(r'\bdata-content-view-box="([^"]+)"', root_tag)
    content_box = _box(content.group(1) if content else view.group(1), "content viewBox")
    # Canonicalise the persisted content box before deriving the visual box. Keep
    # enough precision to preserve pages 1–2 byte-for-byte after normalisation; the
    # visual paper box alone is rounded outward to three decimal places.
    content_box = [float(value) for value in _format_content_box(content_box).split()]

    page_root = re.search(r'<g\s+transform="matrix\(([^)]*)\)">', svg)
    if page_root is None:
        raise ValueError("target has no root page transform")
    matrix = parse_transform("matrix(" + page_root.group(1) + ")")
    bounds = re.search(r'\bdata-page-frame-box="([^"]+)"', tag)
    if bounds is None:
        raise ValueError("prepared page frame has no local bounds")
    x0, y0, x1, y1 = _bounds(bounds.group(1), "page-frame bounds")
    fx0, fy0, fx1, fy1 = transform_box(matrix, x0, y0, x1, y1)
    cx, cy, cw, ch = content_box
    content_edges = (cx, cy, cx + cw, cy + ch)
    # Pages 1–2 already use their whole paper as the logical canvas. Their integrated
    # frame is inside it; PDF/SVG conversion may overshoot an edge by less than a
    # thousandth. Keep the original paper box exactly instead of rounding it outward.
    # Ordinary borders extend tens of units beyond the content box and never match.
    if (fx0 >= content_edges[0] - 0.002 and fy0 >= content_edges[1] - 0.002
            and fx1 <= content_edges[2] + 0.002 and fy1 <= content_edges[3] + 0.002):
        return root, root_tag, content_box, content_box
    x0 = math.floor(min(cx, fx0) * 1000.0) / 1000.0
    y0 = math.floor(min(cy, fy0) * 1000.0) / 1000.0
    x1 = math.ceil(max(cx + cw, fx1) * 1000.0) / 1000.0
    y1 = math.ceil(max(cy + ch, fy1) * 1000.0) / 1000.0
    return root, root_tag, content_box, [x0, y0, x1 - x0, y1 - y0]


def prepare_target(svg, tag):
    if '<g class="page-frame"' in svg:
        raise ValueError("semantic page-frame group cannot be used as preparation input")
    matches = list(PAGE_FRAME_RE.finditer(svg))
    if len(matches) > 1:
        raise ValueError("target contains more than one prepared page frame")
    svg = PAGE_FRAME_RE.sub("", svg)
    root, root_tag, content_box, visual_box = _visual_box(svg, tag)
    root_tag = re.sub(r'\sdata-content-view-box="[^"]+"', "", root_tag)
    visual_text = (
        _format_content_box(visual_box)
        if visual_box == content_box else _format_visual_box(visual_box)
    )
    root_tag = re.sub(r'\bviewBox="[^"]+"', f'viewBox="{visual_text}"', root_tag)
    root_tag = root_tag[:-1] + (
        f' data-content-view-box="{_format_content_box(content_box)}">'
    )
    svg = svg[:root.start()] + root_tag + svg[root.end():]
    page_root = re.search(r'<g\s+transform="matrix\([^)]*\)">', svg)
    return svg[:page_root.end()] + tag + svg[page_root.end():]


def check_prepared_artwork(root, manifest=DEFAULT_MANIFEST):
    _, _, assignments = load_manifest(manifest)
    errors = []
    for page, variant in assignments.items():
        path = target_path(root, page)
        if not path.is_file():
            errors.append(f"page {page}: missing {path}")
            continue
        svg = path.read_text()
        matches = list(PAGE_FRAME_RE.finditer(svg))
        if len(matches) != 1:
            errors.append(f"page {page}: has {len(matches)} prepared page frames")
            continue
        if matches[0].group("variant") != variant:
            errors.append(
                f"page {page}: has page-frame variant {matches[0].group('variant')!r}, "
                f"expected {variant!r}"
            )
        root_group = re.search(r'<g\s+transform="matrix\([^)]*\)">', svg)
        markers = svg.find('<g id="ayah_markers"')
        if root_group is None or markers < 0 or not root_group.end() <= matches[0].start() < markers:
            errors.append(f"page {page}: prepared page frame is not first in paint order")
        try:
            _, root_tag, content_box, visual_box = _visual_box(svg, matches[0].group(0))
            actual = re.search(r'\bviewBox="([^"]+)"', root_tag)
            content = re.search(r'\bdata-content-view-box="([^"]+)"', root_tag)
            if content is None or _box(content.group(1), "content viewBox") != content_box:
                errors.append(f"page {page}: prepared page has no stable content viewBox")
            if actual is None or any(
                abs(a - b) > 0.001
                for a, b in zip(_box(actual.group(1), "visual viewBox"), visual_box)
            ):
                errors.append(f"page {page}: visual viewBox does not fit its native frame")
        except ValueError as error:
            errors.append(f"page {page}: {error}")
    if errors:
        raise ValueError("invalid prepared page frames:\n  " + "\n  ".join(errors))


def _clean_prepared_attributes(node):
    attrs = dict(node.attrib)
    attrs.pop("data-page-frame", None)
    attrs.pop("data-page-frame-box", None)
    return attrs


def check_emitted_page_frames(pages, prepared_root=None, manifest=DEFAULT_MANIFEST):
    _, _, assignments = load_manifest(manifest)
    prepared = {}
    errors = []
    if prepared_root is not None:
        for page in assignments:
            root = ET.fromstring(target_path(prepared_root, page).read_text())
            nodes = [node for node in root.iter()
                     if node.tag.rsplit("}", 1)[-1] == "path"
                     and node.get("data-page-frame") is not None]
            if len(nodes) != 1:
                errors.append(f"page {page}: prepared source has {len(nodes)} page frames")
            else:
                visual = _box(root.get("viewBox"), "prepared visual viewBox")
                content = _box(root.get("data-content-view-box"), "prepared content viewBox")
                dx, dy = -content[0], -content[1]
                normalized_visual = [visual[0] + dx, visual[1] + dy, visual[2], visual[3]]
                normalized_content = [0.0, 0.0, content[2], content[3]]
                prepared[page] = (
                    _clean_prepared_attributes(nodes[0]), normalized_visual, normalized_content,
                )

    seen = []
    for page in range(1, 605):
        path = Path(pages) / f"{page:03}.svg"
        if not path.is_file():
            errors.append(f"page {page}: emitted page is missing")
            continue
        try:
            root = ET.fromstring(path.read_text())
        except ET.ParseError as error:
            errors.append(f"page {page}: invalid emitted SVG: {error}")
            continue
        groups = [node for node in root.iter()
                  if node.tag.rsplit("}", 1)[-1] == "g" and node.get("class") == "page-frame"]
        if len(groups) != 1:
            errors.append(f"page {page}: has {len(groups)} emitted page-frame groups")
            continue
        group = groups[0]
        paths = [node for node in group if node.tag.rsplit("}", 1)[-1] == "path"]
        if len(paths) != 1:
            errors.append(f"page {page}: page-frame group has {len(paths)} direct paths")
            continue
        frame = paths[0]
        if frame.get("data-kind") != "ornament" or frame.get("fill-rule") != "evenodd" or not frame.get("d"):
            errors.append(f"page {page}: emitted page frame has an invalid path contract")
        if frame.get("data-page-frame") is not None or frame.get("data-page-frame-box") is not None:
            errors.append(f"page {page}: emitted page frame retains a preparation attribute")
        try:
            visual = _box(root.get("viewBox"), "emitted visual viewBox")
            content = _box(root.get("data-content-view-box"), "emitted content viewBox")
        except ValueError as error:
            errors.append(f"page {page}: {error}")
            visual = content = [0.0, 0.0, 1.0, 1.0]
        if prepared:
            expected = prepared.get(page)
            if expected is None or expected[0] != dict(frame.attrib):
                errors.append(f"page {page}: emitted page-frame attributes changed")
            elif expected[1:] != (visual, content):
                errors.append(f"page {page}: emitted page-frame viewBox contract changed")
        cx, cy, cw, ch = content
        vx, vy, vw, vh = visual
        if vx > cx or vy > cy or vx + vw < cx + cw or vy + vh < cy + ch:
            errors.append(f"page {page}: visual viewBox does not contain the content viewBox")
        parents = {child: parent for parent in root.iter() for child in parent}
        parent = parents.get(group)
        if parent is None or list(parent).index(group) != 0:
            errors.append(f"page {page}: emitted page frame is not first in paint order")
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "path" or node.get("data-kind") != "ornament":
                continue
            ancestor = parents.get(node)
            while ancestor is not None and ancestor.get("class") not in {"page-frame", "surah-name"}:
                ancestor = parents.get(ancestor)
            if ancestor is None:
                errors.append(f"page {page}: ornament path is outside page-frame and surah-name")
        seen.append(page)
    if seen != list(range(1, 605)):
        errors.append("emitted page-frame coverage is incomplete")
    if errors:
        raise ValueError("invalid emitted page frames:\n  " + "\n  ".join(errors))


def main(argv=None):
    root_default = os.environ.get("QSVG_ROOT")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--root", type=Path, default=Path(root_default) if root_default else None,
        required=root_default is None, help="line-structured quran-svg working root",
    )
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--mutool", default="mutool")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    source, variants, assignments = load_manifest(args.manifest)
    missing = [page for page in assignments if not target_path(args.root, page).is_file()]
    if missing:
        parser.error(f"prepared artwork is missing pages: {missing[:10]}")

    fetched = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {}
        for name, variant in variants.items():
            row = {
                "page": variant["source_page"], "bytes": variant["bytes"],
                "crc32": variant["crc32"], "sha256": variant["sha256"],
            }
            futures[pool.submit(fetch_source, source, row, args.cache, args.offline)] = name
        for future in as_completed(futures):
            fetched[futures[future]] = future.result()

    tags = {}
    source_counts = {}
    for name, variant in variants.items():
        source_path, status = fetched[name]
        source_counts[status] = source_counts.get(status, 0) + 1
        tags[name] = prepared_tag(
            read_source_svg(source_path, args.mutool), name, variant
        )

    stale = []
    pending = []
    try:
        for page, name in assignments.items():
            target = target_path(args.root, page)
            before = target.read_text()
            after = prepare_target(before, tags[name])
            if before == after:
                continue
            if args.check:
                stale.append(page)
                continue
            with tempfile.NamedTemporaryFile(
                mode="w", dir=target.parent, prefix=target.name + ".page-frame.",
                suffix=".tmp", delete=False,
            ) as output:
                output.write(after)
                temporary = Path(output.name)
            pending.append((temporary, target))
        if not args.check:
            for temporary, target in pending:
                temporary.replace(target)
    finally:
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)

    if not args.check:
        check_prepared_artwork(args.root, args.manifest)
    print(
        f"604 pages, {len(variants)} exact frame variants; "
        + ", ".join(f"{key}={value}" for key, value in sorted(source_counts.items()))
        + f", {'updated=' + str(len(pending)) if not args.check else 'stale=' + str(len(stale))}"
    )
    if stale:
        print("stale pages: " + ", ".join(f"{page:03}" for page in stale[:20]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
