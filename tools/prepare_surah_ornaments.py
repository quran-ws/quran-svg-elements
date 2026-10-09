#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools>=4.60",
#   "skia-pathops>=0.8.0",
# ]
# ///
"""Restore every printed surah frame after line assignment.

The prepared tree stays pinned and clean. `add_line_structure.py` first builds its
ignored line-structured working tree; this command then downloads only the official
AI pages named by the manifest, verifies them, and adds compact cartouches to that
derived tree. Pages 1–2 use the separate page-frame pipeline.

    uv run tools/prepare_surah_ornaments.py --root /path/to/quran-svg --jobs 8
    uv run tools/prepare_surah_ornaments.py --root /path/to/quran-svg --offline --check
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO / "conformance" / "surah-ornaments.json"
DEFAULT_CACHE = REPO / ".cache" / "surah-ornaments"
PAGE_FIELDS = {"page", "bytes", "crc32", "sha256", "headers"}
HEADER_FIELDS = {"surah", "line"}
PREPARED_RE = re.compile(
    r'<path\b(?=[^>]*\bdata-kind="ornament")'
    r'(?=[^>]*\bdata-surah-ornament="1")'
    r'(?=[^>]*\bdata-surah="(?P<surah>\d+)")[^>]*/>'
)


def load_manifest(path=DEFAULT_MANIFEST):
    data = json.loads(Path(path).read_text())
    if data.get("schema") != "surah-ornaments" or data.get("schema_version") != "1.0.0":
        raise ValueError("unsupported surah-ornament manifest")
    if data.get("edition") != "hafs-kfgqpc":
        raise ValueError("surah-ornament manifest must target hafs-kfgqpc")
    rows = data.get("pages")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("surah-ornament pages must be objects")
    validate_manifest(data.get("source"), rows)
    return data["source"], rows


def validate_manifest(source, rows):
    if not isinstance(source, dict):
        raise ValueError("manifest source must be an object")
    pages = [row.get("page") for row in rows]
    if len(rows) != 96 or pages != sorted(set(pages)) or any(
        not isinstance(page, int) or page < 1 or page > 604 for page in pages
    ):
        raise ValueError("manifest must contain 96 distinct sorted surah-frame pages")

    headers = []
    for row in rows:
        page = row["page"]
        if set(row) != PAGE_FIELDS:
            raise ValueError(f"page {page} has unexpected manifest fields")
        if not isinstance(row["bytes"], int) or row["bytes"] <= 0:
            raise ValueError(f"page {page} has invalid source size")
        if not re.fullmatch(r"[0-9a-f]{8}", row["crc32"]):
            raise ValueError(f"page {page} has invalid CRC32")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError(f"page {page} has invalid SHA-256")
        if not isinstance(row["headers"], list) or not row["headers"]:
            raise ValueError(f"page {page} has no headers")
        if any(not isinstance(header, dict) or set(header) != HEADER_FIELDS
               for header in row["headers"]):
            raise ValueError(f"page {page} has invalid header records")
        lines = [header["line"] for header in row["headers"]]
        if lines != sorted(set(lines)) or any(
            not isinstance(line, int) or line < 1 or line > 15 for line in lines
        ):
            raise ValueError(f"page {page} has invalid header lines")
        headers.extend(row["headers"])

    surahs = [header["surah"] for header in headers]
    if surahs != list(range(3, 115)):
        raise ValueError("manifest must cover surahs 3–114 exactly once in order")
    if source.get("archive") != "1441-AI-hafs.zip" or source.get("archive_bytes") != 466430736:
        raise ValueError("unexpected official source archive")
    if not re.fullmatch(r"[0-9a-f]{64}", source.get("archive_sha256", "")):
        raise ValueError("manifest source needs the archive SHA-256")
    if not source.get("base_url", "").startswith("https://"):
        raise ValueError("manifest source needs an HTTPS base URL")
    if source.get("filename") != "{page:03d}___Hafs39__DM.ai":
        raise ValueError("unexpected official source filename pattern")


def parse_pages(value):
    if not value:
        return None
    pages = set()
    for part in value.split(","):
        bounds = part.strip().split("-", 1)
        try:
            first = int(bounds[0])
            last = int(bounds[-1])
        except ValueError as error:
            raise ValueError(f"invalid page selection: {part!r}") from error
        if first > last:
            raise ValueError(f"invalid page range: {part!r}")
        pages.update(range(first, last + 1))
    return pages


def file_identity(path):
    sha256 = hashlib.sha256()
    crc32 = 0
    size = 0
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            size += len(chunk)
            sha256.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)
    return size, f"{crc32 & 0xffffffff:08x}", sha256.hexdigest()


def source_matches(path, row):
    return Path(path).is_file() and file_identity(path) == (
        row["bytes"], row["crc32"], row["sha256"]
    )


def fetch_source(source, row, cache, offline=False, retries=3):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    filename = source["filename"].format(page=row["page"])
    target = cache / filename
    if source_matches(target, row):
        return target, "cached"
    if offline:
        raise ValueError(f"page {row['page']}: source missing or corrupt in {cache}")

    target.unlink(missing_ok=True)
    descriptor, name = tempfile.mkstemp(
        dir=target.parent, prefix=target.name + ".download.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary = Path(name)
    url = source["base_url"] + urllib.parse.quote(filename)
    last_error = None
    for attempt in range(retries):
        temporary.unlink(missing_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "quran-svg-elements/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                while chunk := response.read(1 << 20):
                    output.write(chunk)
            if not source_matches(temporary, row):
                got = file_identity(temporary)
                raise ValueError(
                    f"page {row['page']}: source identity {got}, expected "
                    f"{(row['bytes'], row['crc32'], row['sha256'])}"
                )
            temporary.replace(target)
            return target, "downloaded"
        except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            if attempt + 1 < retries:
                time.sleep(attempt + 1)
    raise last_error


def target_path(root, row):
    return Path(root) / "mushafs" / "hafs" / "kfqc" / "svg" / f"{row['page']:03d}.svg"


def prepared_surahs(svg):
    return [int(match.group("surah")) for match in PREPARED_RE.finditer(svg)]


def validate_targets(root, rows, require_prepared=False):
    errors = []
    for row in rows:
        target = target_path(root, row)
        if not target.is_file():
            errors.append(f"page {row['page']}: missing {target}")
            continue
        svg = target.read_text()
        for header in row["headers"]:
            matches = re.findall(
                r'<g class="line" data-line="%d"[^>]*>\s*<g transform="translate\(' % header["line"],
                svg,
            )
            if len(matches) != 1:
                errors.append(
                    f"page {row['page']}: line {header['line']} has {len(matches)} target groups; "
                    "run add_line_structure.py first"
                )
        expected = [header["surah"] for header in row["headers"]]
        actual = prepared_surahs(svg)
        if actual and actual != expected:
            errors.append(f"page {row['page']}: prepared surahs {actual}, expected {expected}")
        if actual:
            for header in row["headers"]:
                owned = re.findall(
                    r'<g class="line" data-line="%d"[^>]*>\s*'
                    r'<g transform="translate\([^)]+\)">\s*'
                    r'<path\b(?=[^>]*data-kind="ornament")'
                    r'(?=[^>]*data-surah-ornament="1")'
                    r'(?=[^>]*data-surah="%d")[^>]*/>'
                    % (header["line"], header["surah"]),
                    svg,
                )
                if len(owned) != 1:
                    errors.append(
                        f"page {row['page']}: surah {header['surah']} frame is not on "
                        f"line {header['line']}"
                    )
        if require_prepared and actual != expected:
            errors.append(f"page {row['page']}: native surah frames are not prepared")
    if errors:
        raise ValueError("invalid surah-ornament artwork:\n  " + "\n  ".join(errors))


def check_prepared_artwork(root, manifest=DEFAULT_MANIFEST):
    _, rows = load_manifest(manifest)
    validate_targets(root, rows, require_prepared=True)
    expected = {target_path(root, row) for row in rows}
    marker = 'data-surah-ornament="1"'
    extras = [
        path for path in (Path(root) / "mushafs/hafs/kfqc/svg").glob("*.svg")
        if path not in expected and marker in path.read_text()
    ]
    if extras:
        raise ValueError(
            "native surah frames exist outside the manifest: "
            + ", ".join(path.name for path in extras[:10])
        )


def check_emitted_surah_frames(pages, prepared_root=None, manifest=DEFAULT_MANIFEST):
    """Require semantic output to preserve every prepared manifest frame."""
    _, rows = load_manifest(manifest)
    expected = [
        (row["page"], header["line"], header["surah"])
        for row in rows
        for header in row["headers"]
    ]
    actual = []
    errors = []
    prepared = {}

    def placement(node, parents):
        transform = None
        line = None
        while node in parents:
            node = parents[node]
            if transform is None and node.get("transform"):
                transform = node.get("transform")
            if node.tag.rsplit("}", 1)[-1] == "g" and node.get("class") == "line":
                try:
                    line = int(node.get("data-line"))
                except (TypeError, ValueError):
                    pass
                break
        return line, transform

    if prepared_root is not None:
        for row in rows:
            page = row["page"]
            root = ET.fromstring(target_path(prepared_root, row).read_text())
            parents = {child: parent for parent in root.iter() for child in parent}
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "path" or node.get("data-surah-ornament") != "1":
                    continue
                line, transform = placement(node, parents)
                key = (page, line, int(node.get("data-surah")))
                if key in prepared:
                    errors.append(f"page {page}: duplicate prepared frame for surah {key[2]}")
                prepared[key] = (transform, node.get("d"), node.get("fill-rule"))
        if list(prepared) != expected:
            errors.append("prepared frame placement does not match the manifest order")

    for path in sorted(Path(pages).glob("*.svg")):
        svg = path.read_text()
        if 'data-kind="ornament"' not in svg:
            continue
        page = int(path.stem)
        try:
            root = ET.fromstring(svg)
        except ET.ParseError as error:
            raise ValueError(f"page {page}: invalid emitted SVG: {error}") from error
        parents = {child: parent for parent in root.iter() for child in parent}
        for group in root.iter():
            if group.tag.rsplit("}", 1)[-1] != "g" or group.get("class") != "surah-name":
                continue
            paths = [child for child in group if child.tag.rsplit("}", 1)[-1] == "path"]
            ornaments = [child for child in paths if child.get("data-kind") == "ornament"]
            if not ornaments:
                continue
            try:
                surah = int(group.get("data-sid"))
            except (TypeError, ValueError):
                errors.append(f"page {page}: ornament title has no valid data-sid")
                continue
            line, transform = placement(group, parents)
            key = (page, line, surah)
            actual.append(key)
            kinds = [child.get("data-kind") for child in paths]
            if kinds != ["ornament", "header_ink"]:
                errors.append(f"page {page}: surah {surah} title paths are {kinds!r}")
            frame = ornaments[0]
            if not frame.get("d"):
                errors.append(f"page {page}: surah {surah} frame lost its path")
            if prepared and prepared.get(key) != (transform, frame.get("d"), frame.get("fill-rule")):
                errors.append(f"page {page}: surah {surah} frame geometry or placement changed during emission")
            if frame.get("data-surah-ornament") is not None or frame.get("data-surah") is not None:
                errors.append(f"page {page}: surah {surah} frame retains preparation attributes")
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        errors.append(f"emitted surah frames do not match manifest; missing={missing[:10]}, extra={extra[:10]}")
    if errors:
        raise ValueError("invalid emitted surah frames:\n  " + "\n  ".join(errors))


def prepare_page(source_path, target, headers, mutool="mutool", check=False):
    from add_surah_ornaments import prepared_page, read_source_svg

    target = Path(target)
    before = target.read_text()
    pairs = [(header["surah"], header["line"]) for header in headers]
    after = prepared_page(read_source_svg(source_path, mutool), before, pairs)
    if before == after:
        return "ok" if check else "unchanged"
    if check:
        return "stale"
    with tempfile.NamedTemporaryFile(
        mode="w", dir=target.parent, prefix=target.name + ".surah-ornaments.",
        suffix=".tmp", delete=False,
    ) as output:
        output.write(after)
        temporary = Path(output.name)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return "updated"


def main(argv=None):
    root_default = os.environ.get("QSVG_ROOT")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--root", type=Path, default=Path(root_default) if root_default else None,
        required=root_default is None, help="line-structured quran-svg working root",
    )
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--pages", help="comma-separated pages or ranges, e.g. 50,587-604")
    parser.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--mutool", default="mutool")
    parser.add_argument("--offline", action="store_true", help="refuse to download missing sources")
    parser.add_argument("--check", action="store_true", help="fail if prepared artwork is stale")
    args = parser.parse_args(argv)

    source, rows = load_manifest(args.manifest)
    selected = parse_pages(args.pages)
    if selected is not None:
        known = {row["page"] for row in rows}
        unknown = sorted(selected - known)
        if unknown:
            parser.error(f"pages outside the surah-frame manifest: {unknown}")
        rows = [row for row in rows if row["page"] in selected]
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    validate_targets(args.root, rows)
    fetched = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(fetch_source, source, row, args.cache, args.offline): row
            for row in rows
        }
        for future in as_completed(futures):
            row = futures[future]
            fetched[row["page"]] = future.result()

    stale = []
    counts = {}
    for row in rows:
        source_path, source_status = fetched[row["page"]]
        status = prepare_page(
            source_path, target_path(args.root, row), row["headers"], args.mutool, args.check
        )
        counts[source_status] = counts.get(source_status, 0) + 1
        counts[status] = counts.get(status, 0) + 1
        print(f"{row['page']:03d}: {source_status}, {status}")
        if status == "stale":
            stale.append(row["page"])

    print(
        f"\n{len(rows)} pages, {sum(len(row['headers']) for row in rows)} surah frames; "
        + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    )
    if stale:
        print("stale pages: " + ", ".join(f"{page:03d}" for page in stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
