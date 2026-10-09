#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools==4.66.1",
# ]
# ///
"""Emit tagged QCF V1 SVG pages from the verified glyph map.

This stage emits the mapped Hafs 1405H pages using exact QCF V1 body outlines
and exact QPC V4 header/basmalah outlines. Adjacent logical words may share one
physical path range through an explicit alias contract. Independently boxed
waqf source glyphs, division rosettes and source-owned sajdah marks are typed
from pinned ownership ledgers; fused waqf signs, body contours, dots and vowels
remain explicit later stages.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from xml.etree import ElementTree

from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from qcf_v1_division_sajdah import (
    DivisionSajdahSemantics,
    boundary_attributes,
    division_values,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_DIR = ROOT / ".cache/qcf-v1/map"
DEFAULT_OUT_DIR = ROOT / ".cache/qcf-v1/svg-body"
DEFAULT_MANIFEST = ROOT / "conformance/qcf-v1-vector-source.json"
DEFAULT_SURAH_NAMES = ROOT / "tools/data/surah_names.tsv"
DEFAULT_WAQF_SOURCE_GLYPHS = ROOT / "conformance/qcf-v1-waqf-source-glyphs.json"
DEFAULT_DIVISION_SAJDAH_SOURCE = ROOT / "conformance/qcf-v1-division-sajdah-source.json"
TEXT_FIELDS = ("rasm_uthmani", "rasm_imlai", "qpc", "rasm", "search")
WAQF_MARK_BY_CHAR = {
    "ۖ": "waqf_jaiz_wasl_awla",
    "ۗ": "waqf_jaiz_waqf_awla",
    "ۘ": "waqf_lazim",
    "ۚ": "waqf_jaiz_mustawi_al_tarafayn",
    "ۛ": "waqf_al_muanaqah",
}
HEADER_TYPES = {"surah_name": "surah-name", "basmalah": "basmalah"}
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


class DeferredPage(ValueError):
    """A valid mapped page whose remaining source semantics are intentionally deferred."""


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def json_bytes(value: object, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        )
    return text.encode()


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def relative_tree_sha256(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_pages(value: str) -> list[int]:
    pages = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = (int(item) for item in part.split("-", 1))
            if first > last:
                raise ValueError(f"descending page range: {part}")
            pages.update(range(first, last + 1))
        else:
            pages.add(int(part))
    if not pages:
        raise ValueError("no pages selected")
    if min(pages) < 1 or max(pages) > 604:
        raise ValueError("pages must be between 1 and 604")
    return sorted(pages)


def number(value: float) -> str:
    if abs(value) < 5e-10:
        value = 0.0
    return f"{value:.9f}".rstrip("0").rstrip(".")


def attr(value: object) -> str:
    return escape(str(value), quote=True)


def parse_codepoint(value: str) -> int:
    if not value.startswith("U+"):
        raise ValueError(f"invalid codepoint label: {value}")
    return int(value.replace("U+", "0x"), 0)


def transformed_box(box: list[int], factor: float) -> list[float]:
    return [round(value * factor, 4) for value in box]


def glyph_transform(
    box: list[int],
    font_bbox: tuple[int, int, int, int],
    units_per_em: int,
    em_pixels: float,
    page_factor: float,
) -> tuple[float, float, float]:
    x0, y0, x1, y1 = box
    gx0, gy0, gx1, gy1 = font_bbox
    scale_px = em_pixels / units_per_em
    tx_px = (x0 + x1) / 2 - scale_px * (gx0 + gx1) / 2
    baseline_top = y0 + scale_px * gy1
    baseline_bottom = y1 + scale_px * gy0
    baseline_px = (baseline_top + baseline_bottom) / 2
    return scale_px * page_factor, tx_px * page_factor, baseline_px * page_factor


def logical_word_maps(page: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    words = {word["word_key"]: word for word in page["words"]}
    groups = {group["id"]: group for group in page.get("shared_groups", [])}
    for group in groups.values():
        previous = None
        for index, canonical in enumerate(group["canonical_words"]):
            key = canonical["word_key"]
            words[key] = {
                "word_key": key,
                "ayah_key": group["ayah_key"],
                "line": group["line"],
                "box": group["box"],
                "text": canonical["text"],
                "glyphs": group["glyphs"] if index == 0 else [],
                "shared_group_id": group["id"],
                "shared_path_owner": previous,
            }
            previous = key
    return words, groups


def logical_words(page: dict) -> list[dict]:
    word_by_key, group_by_id = logical_word_maps(page)
    result = []
    for line in page["lines"]:
        for entry in line.get("content", []):
            if entry["kind"] == "word":
                result.append(word_by_key[entry["word_key"]])
            elif entry["kind"] == "shared_group":
                result.extend(
                    word_by_key[key]
                    for key in group_by_id[entry["id"]]["canonical_word_keys"]
                )
    return result


def line_fragments(page: dict) -> dict[int, list[dict]]:
    word_by_key, group_by_id = logical_word_maps(page)
    fragments = []
    for line in page["lines"]:
        current = None
        words = []
        ordered = []
        for entry in line.get("content", []):
            if entry["kind"] == "word":
                ordered.append(word_by_key[entry["word_key"]])
            elif entry["kind"] == "shared_group":
                ordered.extend(
                    word_by_key[key]
                    for key in group_by_id[entry["id"]]["canonical_word_keys"]
                )
        for word in ordered:
            key_ayah = word["ayah_key"]
            if current is not None and key_ayah != current:
                fragments.append(
                    {"line": line["line"], "ayah_key": current, "words": words}
                )
                words = []
            current = key_ayah
            words.append(word)
        if words:
            fragments.append(
                {"line": line["line"], "ayah_key": current, "words": words}
            )

    totals = Counter(fragment["ayah_key"] for fragment in fragments)
    seen = Counter()
    by_line = defaultdict(list)
    for fragment in fragments:
        key = fragment["ayah_key"]
        seen[key] += 1
        fragment["fragment"] = seen[key]
        fragment["fragments"] = totals[key]
        by_line[fragment["line"]].append(fragment)
    return dict(by_line)


class PageFont:
    def __init__(self, path: Path):
        self.font = TTFont(path)
        self.glyph_set = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.glyf = self.font["glyf"]
        self.hmtx = self.font["hmtx"]
        self.units_per_em = self.font["head"].unitsPerEm
        self.cache: dict[int, tuple[str, tuple[int, int, int, int]]] = {}
        self.ink_cache: dict[int, tuple[str, tuple[float, float, float, float]]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.font.close()

    def outline(self, codepoint: int) -> tuple[str, tuple[int, int, int, int]]:
        if codepoint in self.cache:
            return self.cache[codepoint]
        name = self.cmap.get(codepoint)
        if name is None:
            raise ValueError(f"font has no U+{codepoint:04X}")
        glyph = self.glyf[name]
        if glyph.numberOfContours == 0:
            raise ValueError(f"font glyph U+{codepoint:04X} has no outline")
        pen = SVGPathPen(self.glyph_set)
        self.glyph_set[name].draw(pen)
        path = pen.getCommands()
        if not path:
            raise ValueError(f"font glyph U+{codepoint:04X} produced no path")
        result = path, (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
        self.cache[codepoint] = result
        return result

    def body_bounds(
        self,
        codepoint: int,
        painted: tuple[int, int, int, int],
        source_box_width: float,
        em_pixels: float,
        maximum_rsb_em: float,
        minimum_advance_advantage_em: float,
    ) -> tuple[float, float, float, float]:
        """Move halfway toward the advance cell when both evidence signals agree."""
        name = self.cmap.get(codepoint)
        if name is None:
            raise ValueError(f"font has no U+{codepoint:04X}")
        advance, left_side_bearing = self.hmtx[name]
        painted_width = painted[2] - painted[0]
        right_side_bearing = advance - left_side_bearing - painted_width
        painted_pixels = painted_width * em_pixels / self.units_per_em
        advance_pixels = advance * em_pixels / self.units_per_em
        advance_advantage_em = (
            abs(source_box_width - painted_pixels)
            - abs(source_box_width - advance_pixels)
        ) / em_pixels
        if (
            right_side_bearing / self.units_per_em <= maximum_rsb_em
            and advance_advantage_em >= minimum_advance_advantage_em
        ):
            return (
                painted[0] / 2,
                painted[1],
                (painted[2] + advance) / 2,
                painted[3],
            )
        return painted

    def ink_outline(
        self, codepoint: int
    ) -> tuple[str, tuple[float, float, float, float]]:
        """Return ink-bearing contours, excluding move-only positioning contours."""
        if codepoint in self.ink_cache:
            return self.ink_cache[codepoint]
        name = self.cmap.get(codepoint)
        if name is None:
            raise ValueError(f"font has no U+{codepoint:04X}")

        source = DecomposingRecordingPen(self.glyph_set)
        self.glyph_set[name].draw(source)
        contours = []
        contour = []
        for operation, arguments in source.value:
            if operation == "moveTo" and contour:
                contours.append(contour)
                contour = []
            contour.append((operation, arguments))
            if operation in {"closePath", "endPath"}:
                contours.append(contour)
                contour = []
        if contour:
            contours.append(contour)

        filtered = RecordingPen()
        removed = False
        for contour in contours:
            recording = RecordingPen()
            for operation, arguments in contour:
                getattr(recording, operation)(*arguments)
            bounds = BoundsPen(self.glyph_set)
            area = AreaPen(self.glyph_set)
            recording.replay(bounds)
            recording.replay(area)
            box = bounds.bounds
            if (
                not any(
                    operation in {"lineTo", "qCurveTo", "curveTo"}
                    for operation, _ in contour
                )
                or box is None
                or box[0] >= box[2]
                or box[1] >= box[3]
                or abs(area.value) <= 1e-9
            ):
                removed = True
                continue
            recording.replay(filtered)
        if not removed:
            result = self.outline(codepoint)
            self.ink_cache[codepoint] = result
            return result

        svg = SVGPathPen(self.glyph_set)
        bounds = BoundsPen(self.glyph_set)
        filtered.replay(svg)
        filtered.replay(bounds)
        path = svg.getCommands()
        if not path or bounds.bounds is None:
            raise ValueError(f"font glyph U+{codepoint:04X} produced no ink outline")
        result = path, bounds.bounds
        self.ink_cache[codepoint] = result
        return result

    def body_ink_outline(
        self,
        codepoint: int,
        source_box_width: float,
        em_pixels: float,
        minimum_advantage_em: float,
        source_width_ratio: tuple[float, float] | list[float],
    ) -> tuple[str, tuple[float, float, float, float], bool]:
        """Use visible ink only when the mapped source box strongly confirms it."""
        path, painted = self.outline(codepoint)
        ink_path, ink = self.ink_outline(codepoint)
        if path == ink_path and painted == ink:
            return path, painted, False
        if source_box_width <= 0 or em_pixels <= 0:
            raise ValueError("body visible-ink evidence dimensions must be positive")
        minimum_ratio, maximum_ratio = source_width_ratio
        painted_pixels = (painted[2] - painted[0]) * em_pixels / self.units_per_em
        ink_pixels = (ink[2] - ink[0]) * em_pixels / self.units_per_em
        advantage_em = (
            abs(source_box_width - painted_pixels) - abs(source_box_width - ink_pixels)
        ) / em_pixels
        ratio = ink_pixels / source_box_width
        if (
            advantage_em >= minimum_advantage_em
            and minimum_ratio <= ratio <= maximum_ratio
        ):
            return ink_path, ink, True
        return path, painted, False


class SurahMetadata:
    def __init__(self, chapters_path: Path, names_path: Path, manifest: dict):
        expected = manifest["inputs"]
        actual = {
            "chapters_metadata_sha256": sha256(chapters_path),
            "surah_names_sha256": sha256(names_path),
        }
        wrong = {
            name: {"expected": expected.get(name), "actual": value}
            for name, value in actual.items()
            if expected.get(name) != value
        }
        if wrong:
            raise ValueError(
                "surah metadata digest mismatch:\n" + json.dumps(wrong, indent=2)
            )
        self.chapters_sha256 = actual["chapters_metadata_sha256"]
        self.names_sha256 = actual["surah_names_sha256"]

        names = {}
        for line_number, line in enumerate(names_path.read_text().splitlines(), 1):
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 4:
                raise ValueError(f"bad surah-name row {line_number}")
            number, code, arabic, display = fields
            try:
                surah = int(number)
            except ValueError as error:
                raise ValueError(f"bad surah-name row {line_number}") from error
            if (
                surah in names
                or surah < 1
                or surah > 114
                or not code
                or not arabic
                or not display
            ):
                raise ValueError(f"bad surah-name row {line_number}")
            names[surah] = {
                "code": code,
                "arabic": arabic,
                "latin": display,
            }
        if set(names) != set(range(1, 115)):
            raise ValueError("surah-name metadata coverage differs")

        source = read_json(chapters_path)
        chapters = source.get("chapters") if isinstance(source, dict) else None
        if not isinstance(chapters, list) or len(chapters) != 114:
            raise ValueError("chapter metadata coverage differs")
        self.by_surah = {}
        for chapter in chapters:
            if not isinstance(chapter, dict):
                raise TypeError("bad chapter metadata record")
            try:
                surah = int(chapter["id"])
                ayah_count = int(chapter["verses_count"])
                translated = chapter["translated_name"]["name"]
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("bad chapter metadata record") from error
            record = {
                "arabic": chapter.get("name_arabic"),
                "latin": names.get(surah, {}).get("latin"),
                "english": translated,
                "revelation_place": chapter.get("revelation_place"),
                "ayah_count": ayah_count,
            }
            if (
                surah in self.by_surah
                or surah < 1
                or surah > 114
                or ayah_count <= 0
                or any(
                    not isinstance(record[name], str) or not record[name]
                    for name in ("arabic", "latin", "english", "revelation_place")
                )
            ):
                raise ValueError(f"bad chapter metadata for surah {surah}")
            self.by_surah[surah] = record
        if set(self.by_surah) != set(range(1, 115)):
            raise ValueError("chapter metadata identities differ")

    def for_surah(self, surah: int) -> dict:
        try:
            return self.by_surah[surah]
        except KeyError as error:
            raise ValueError(f"missing metadata for surah {surah}") from error


class HeaderAssets:
    def __init__(self, root: Path, manifest: dict):
        self.root = root
        summary_path = root / "summary.json"
        if sha256(summary_path) != manifest["inputs"].get(
            "header_asset_summary_sha256"
        ):
            raise ValueError("V4 header asset summary digest differs")
        summary = read_json(summary_path)
        if (
            summary.get("schema") != "quran-svg-elements/qcf-v1-v4-header-assets"
            or summary.get("schema_version") != 1
            or summary.get("edition") != manifest["edition"]
            or summary.get("print_year_hijri") != manifest["print_year_hijri"]
            or summary.get("source_manifest_sha256")
            != manifest["inputs"].get("map_source_manifest_sha256")
            or summary.get("surah_assets") != 114
            or summary.get("basmalah_assets") != 1
        ):
            raise ValueError("wrong V4 header asset summary")

        records = summary.get("assets")
        if not isinstance(records, list) or len(records) != 115:
            raise ValueError("wrong V4 header asset inventory")
        expected_paths = {f"surah/{surah:03}.svg" for surah in range(1, 115)} | {
            "basmalah.svg"
        }
        if {record.get("path") for record in records} != expected_paths:
            raise ValueError("V4 header asset paths differ")

        paths = sorted(root / relative for relative in expected_paths)
        actual_paths = sorted(root.glob("surah/*.svg")) + [root / "basmalah.svg"]
        if set(paths) != set(actual_paths) or not all(path.is_file() for path in paths):
            raise ValueError("V4 header asset file set differs")
        self.files_sha256 = relative_tree_sha256(root, paths)
        if self.files_sha256 != summary.get(
            "asset_files_sha256"
        ) or self.files_sha256 != manifest["inputs"].get("header_asset_files_sha256"):
            raise ValueError("V4 header asset files digest differs")

        self.summary_sha256 = sha256(summary_path)
        self.by_path = {}
        for record in records:
            relative = record["path"]
            source = root / relative
            if sha256(source) != record.get("sha256"):
                raise ValueError(f"V4 header asset {relative} digest differs")
            box = record.get("box")
            if (
                not isinstance(box, list)
                or len(box) != 4
                or not all(isinstance(value, (int, float)) for value in box)
                or box[0] >= box[2]
                or box[1] >= box[3]
            ):
                raise ValueError(f"V4 header asset {relative} box differs")
            units_per_em = record.get("units_per_em")
            if not isinstance(units_per_em, int) or units_per_em <= 0:
                raise ValueError(f"V4 header asset {relative} em differs")

            root_element = ElementTree.parse(source).getroot()
            paths_in_svg = root_element.findall(f"{{{SVG_NAMESPACE}}}path")
            if len(paths_in_svg) != 1:
                raise ValueError(f"V4 header asset {relative} path count differs")
            path_element = paths_in_svg[0]
            kind = record.get("kind")
            width = box[2] - box[0]
            height = box[3] - box[1]
            expected_view_box = f"0 0 {number(width)} {number(height)}"
            expected_transform = f"matrix(1 0 0 -1 {number(-box[0])} {number(box[3])})"
            if (
                kind not in {"surah-name", "basmalah"}
                or root_element.get("data-kind") != kind
                or root_element.get("data-codepoint") != record.get("codepoint")
                or root_element.get("data-units-per-em") != str(units_per_em)
                or root_element.get("viewBox") != expected_view_box
                or path_element.get("data-kind") != kind
                or path_element.get("transform") != expected_transform
                or not path_element.get("d")
            ):
                raise ValueError(f"V4 header asset {relative} SVG contract differs")
            if kind == "surah-name":
                surah = record.get("surah")
                if (
                    not isinstance(surah, int)
                    or surah < 1
                    or surah > 114
                    or relative != f"surah/{surah:03}.svg"
                    or root_element.get("data-surah") != str(surah)
                ):
                    raise ValueError(f"V4 surah asset {relative} identity differs")
            elif relative != "basmalah.svg" or "surah" in record:
                raise ValueError("V4 basmalah asset identity differs")
            self.by_path[relative] = record | {"d": path_element.get("d")}

    def asset_for(self, line: dict) -> dict:
        line_type = line.get("type")
        kind = HEADER_TYPES.get(line_type)
        reference = line.get("asset")
        if kind is None or not isinstance(reference, dict):
            raise ValueError(f"line {line.get('line')} has no V4 header asset")
        relative = reference.get("asset_path")
        asset = self.by_path.get(relative)
        if asset is None or asset["kind"] != kind:
            raise ValueError(f"V4 header asset {relative!r} differs")
        surah = line.get("surah")
        if (
            not isinstance(surah, int)
            or surah < 1
            or surah > 114
            or reference.get("codepoint") != asset["codepoint"]
        ):
            raise ValueError(f"V4 header line {line.get('line')} identity differs")
        if line_type == "surah_name":
            if (
                asset.get("surah") != surah
                or reference.get("family") != "qpc-v4-surah-header"
                or reference.get("source_font") != "QCF_SurahHeader_COLOR-Regular.ttf"
                or reference.get("qcf4_layout_font_file_id") != 0
                or reference.get("qcf4_layout_font_code") != surah - 1
            ):
                raise ValueError(f"V4 surah line {line.get('line')} differs")
        elif (
            reference.get("family") != "qpc-v4-basmalah"
            or reference.get("source_font") != "QCF4_Hafs_01_W.ttf"
            or reference.get("font_file_id") != 1
            or not isinstance(reference.get("source_font_file_id"), int)
            or reference["source_font_file_id"] < 1
            or reference.get("font_code") != 2013
        ):
            raise ValueError(f"V4 basmalah line {line.get('line')} differs")
        return asset


def verify_glyphs(page_number: int, owner: str, glyphs: list[dict]) -> None:
    if not glyphs:
        raise ValueError(f"page {page_number}: no glyphs for {owner}")
    for glyph in glyphs:
        box = glyph.get("box")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError(f"page {page_number}: incomplete geometry for {owner}")
        x0, y0, x1, y1 = box
        if x0 > x1 or y0 >= y1:
            raise ValueError(f"page {page_number}: invalid geometry for {owner}: {box}")
        codepoint = parse_codepoint(glyph["codepoint"])
        if glyph.get("text") != chr(codepoint):
            raise ValueError(f"page {page_number}: codepoint/text mismatch for {owner}")


def ordered_ayah_keys(
    content: list[dict], word_by_key: dict[str, dict], group_by_id: dict[str, dict]
) -> list[str]:
    ayahs = []
    for entry in content:
        if entry["kind"] == "word":
            key = word_by_key[entry["word_key"]]["ayah_key"]
        elif entry["kind"] == "shared_group":
            key = group_by_id[entry["id"]]["ayah_key"]
        elif entry["kind"] == "ayah_mark":
            key = entry["ayah_key"]
        else:
            raise ValueError(f"unsupported body line content: {entry}")
        if key not in ayahs:
            ayahs.append(key)
    return ayahs


def verify_line_content(
    page_number: int,
    line: dict,
    word_by_key: dict[str, dict],
    group_by_id: dict[str, dict],
    marker_by_ayah: dict[str, dict],
) -> None:
    content = line.get("content")
    if not isinstance(content, list):
        raise TypeError(
            f"page {page_number}: line {line['line']} has no ordered content"
        )

    expected_words = line["word_keys"]
    expected_shared = line["shared_word_keys"]
    expected_markers = [
        key for key, marker in marker_by_ayah.items() if marker["line"] == line["line"]
    ]
    actual_words = []
    actual_shared = []
    actual_markers = []
    for entry in content:
        if not isinstance(entry, dict):
            raise TypeError(
                f"page {page_number}: line {line['line']} has invalid content"
            )
        if entry.get("kind") == "word" and set(entry) == {"kind", "word_key"}:
            key = entry["word_key"]
            if key not in word_by_key or word_by_key[key]["line"] != line["line"]:
                raise ValueError(
                    f"page {page_number}: line {line['line']} has misplaced word {key}"
                )
            actual_words.append(key)
        elif entry.get("kind") == "shared_group" and set(entry) == {
            "kind",
            "id",
            "canonical_word_keys",
        }:
            group = group_by_id.get(entry["id"])
            if (
                group is None
                or group["line"] != line["line"]
                or entry["canonical_word_keys"] != group["canonical_word_keys"]
            ):
                raise ValueError(
                    f"page {page_number}: line {line['line']} has misplaced shared group {entry}"
                )
            actual_shared.extend(group["canonical_word_keys"])
        elif entry.get("kind") == "ayah_mark" and set(entry) == {
            "kind",
            "ayah_key",
        }:
            key = entry["ayah_key"]
            marker = marker_by_ayah.get(key)
            if marker is None or marker["line"] != line["line"]:
                raise ValueError(
                    f"page {page_number}: line {line['line']} has misplaced marker {key}"
                )
            actual_markers.append(key)
        else:
            raise ValueError(
                f"page {page_number}: line {line['line']} has unsupported content {entry}"
            )

    if actual_words != expected_words:
        raise ValueError(f"page {page_number}: line {line['line']} word order differs")
    if actual_shared != expected_shared:
        raise ValueError(
            f"page {page_number}: line {line['line']} shared-word order differs"
        )
    if sorted(actual_markers, key=numeric_key) != sorted(
        expected_markers, key=numeric_key
    ):
        raise ValueError(
            f"page {page_number}: line {line['line']} marker coverage differs"
        )
    if len(actual_markers) != len(set(actual_markers)):
        raise ValueError(
            f"page {page_number}: line {line['line']} repeats an ayah marker"
        )

    groups = [group for group in group_by_id.values() if group["line"] == line["line"]]
    expected_content = [{"kind": "word", "word_key": key} for key in expected_words]
    expected_content.extend(
        {
            "kind": "shared_group",
            "id": group["id"],
            "canonical_word_keys": group["canonical_word_keys"],
        }
        for group in groups
    )
    expected_content.extend(
        {"kind": "ayah_mark", "ayah_key": key} for key in expected_markers
    )
    expected_content.sort(
        key=lambda entry: (
            numeric_key(entry["word_key"])
            if entry["kind"] == "word"
            else numeric_key(entry["canonical_word_keys"][0])
            if entry["kind"] == "shared_group"
            else numeric_key(entry["ayah_key"]) + (1_000_000,)
        )
    )
    if content != expected_content:
        raise ValueError(
            f"page {page_number}: line {line['line']} content order differs"
        )
    if ordered_ayah_keys(content, word_by_key, group_by_id) != line.get("ayah_keys"):
        raise ValueError(
            f"page {page_number}: line {line['line']} ordered ayahs differ"
        )


def numeric_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(":"))


class WaqfSourceGlyphs:
    def __init__(self, path: Path, manifest: dict):
        expected_sha256 = manifest["inputs"].get("waqf_source_glyphs_sha256")
        if sha256(path) != expected_sha256:
            raise ValueError("waqf source-glyph ledger digest differs")
        value = read_json(path)
        fields = {
            "schema",
            "schema_version",
            "edition",
            "source",
            "text_marks",
            "counts",
            "separate",
            "fused",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("waqf source-glyph ledger fields differ")
        if (
            value["schema"] != "quran-svg-elements/qcf-v1-waqf-source-glyphs"
            or value["schema_version"] != 2
            or value["edition"] != manifest["edition"]
        ):
            raise ValueError("waqf source-glyph ledger identity differs")

        text_marks = {
            f"U+{ord(char):04X}": mark for char, mark in WAQF_MARK_BY_CHAR.items()
        }
        if value["text_marks"] != text_marks:
            raise ValueError("waqf text-mark mapping differs")
        source = value["source"]
        if (
            not isinstance(source, dict)
            or set(source)
            != {
                "map",
                "map_page_files_sha256",
                "page_font_tree_sha256",
                "division_sajdah_source_sha256",
                "analysis_records_sha256",
            }
            or source["page_font_tree_sha256"]
            != manifest["inputs"].get("page_font_tree_sha256")
            or source["division_sajdah_source_sha256"]
            != manifest["inputs"].get("division_sajdah_source_sha256")
            or not all(
                isinstance(source[name], str)
                and len(source[name]) == 64
                and all(character in "0123456789abcdef" for character in source[name])
                for name in (
                    "map_page_files_sha256",
                    "page_font_tree_sha256",
                    "division_sajdah_source_sha256",
                    "analysis_records_sha256",
                )
            )
        ):
            raise ValueError("waqf source evidence differs")

        self.by_page: dict[int, dict[str, dict]] = defaultdict(dict)
        actual = {
            "text_signs": 0,
            "separate_source_glyphs": 0,
            "fused_source_glyphs": 0,
            "text_signs_by_mark": Counter(),
            "separate_source_glyphs_by_mark": Counter(),
            "fused_source_glyphs_by_mark": Counter(),
        }
        required_record_fields = {
            "page",
            "word_key",
            "text_codepoint",
            "mark",
            "source_codepoint",
            "source_glyph_index",
            "source_glyph_count",
        }
        semantic_indices_field = "source_semantic_glyph_indices"
        for status in ("separate", "fused"):
            records = value[status]
            if not isinstance(records, list):
                raise TypeError(f"waqf {status} records must be a list")
            for record in records:
                if not isinstance(record, dict) or set(record) not in (
                    required_record_fields,
                    required_record_fields | {semantic_indices_field},
                ):
                    raise ValueError(f"invalid waqf {status} record")
                page = record["page"]
                key = record["word_key"]
                try:
                    parsed_key = numeric_key(key)
                except (TypeError, ValueError) as error:
                    raise ValueError(f"invalid waqf word key: {key!r}") from error
                text_codepoint = record["text_codepoint"]
                mark = record["mark"]
                glyph_index = record["source_glyph_index"]
                glyph_count = record["source_glyph_count"]
                semantic_indices = record.get(semantic_indices_field, [])
                if (
                    not isinstance(page, int)
                    or page < 1
                    or page > 604
                    or len(parsed_key) != 3
                    or any(part <= 0 for part in parsed_key)
                    or text_marks.get(text_codepoint) != mark
                    or parse_codepoint(record["source_codepoint"]) <= 0
                    or not isinstance(glyph_index, int)
                    or not isinstance(glyph_count, int)
                    or glyph_count <= 0
                    or not isinstance(semantic_indices, list)
                    or any(type(index) is not int for index in semantic_indices)
                    or semantic_indices != sorted(set(semantic_indices))
                    or any(
                        index < 0 or index >= glyph_count for index in semantic_indices
                    )
                    or (semantic_indices_field in record and not semantic_indices)
                    or glyph_index != glyph_count - 1
                    or glyph_index in semantic_indices
                    or (
                        status == "separate"
                        and glyph_count - len(semantic_indices) <= 1
                    )
                    or (status == "fused" and glyph_count - len(semantic_indices) != 1)
                    or key in self.by_page[page]
                ):
                    raise ValueError(
                        f"invalid waqf {status} ownership for page {page}, {key}"
                    )
                self.by_page[page][key] = record | {"status": status}
                actual["text_signs"] += 1
                actual[f"{status}_source_glyphs"] += 1
                actual["text_signs_by_mark"][mark] += 1
                actual[f"{status}_source_glyphs_by_mark"][mark] += 1

        normalized = {
            name: dict(sorted(counts.items()))
            if isinstance(counts, Counter)
            else counts
            for name, counts in actual.items()
        }
        if value["counts"] != normalized:
            raise ValueError("waqf source-glyph counts differ")
        settings = manifest.get("waqf")
        if (
            not isinstance(settings, dict)
            or set(settings)
            != {
                "source",
                "qualification",
                "path_kind",
                "mark_family",
                "text_signs",
                "separate_source_glyphs",
                "fused_source_glyphs",
            }
            or settings["source"]
            != "canonical rasm sign plus pinned semantic-aware source-glyph ownership"
            or settings["qualification"] != "source-glyph-qualified"
            or settings["path_kind"] != "mark"
            or settings["mark_family"] != "waqf"
            or any(
                settings[name] != normalized[name]
                for name in (
                    "text_signs",
                    "separate_source_glyphs",
                    "fused_source_glyphs",
                )
            )
        ):
            raise ValueError("waqf output policy differs")
        self.expected_counts = normalized
        self.sha256 = expected_sha256

    def classify_page(self, page: dict) -> tuple[dict[tuple[str, int], str], Counter]:
        page_number = page["page"]
        expected = self.by_page.get(page_number, {})
        seen = set()
        paths = {}
        counts = Counter()
        for word in page["words"]:
            key = word["word_key"]
            signs = [
                char
                for char in word["text"]["rasm_uthmani"]
                if char in WAQF_MARK_BY_CHAR
            ]
            record = expected.get(key)
            if not signs:
                if record is not None:
                    raise ValueError(
                        f"page {page_number}: ledger assigns waqf to {key} without a sign"
                    )
                continue
            if len(signs) != 1 or record is None:
                raise ValueError(
                    f"page {page_number}: waqf ownership is missing or ambiguous for {key}"
                )
            char = signs[0]
            glyphs = word["glyphs"]
            index = record["source_glyph_index"]
            if (
                record["text_codepoint"] != f"U+{ord(char):04X}"
                or record["mark"] != WAQF_MARK_BY_CHAR[char]
                or record["source_glyph_count"] != len(glyphs)
                or index >= len(glyphs)
                or record["source_codepoint"] != glyphs[index]["codepoint"]
            ):
                raise ValueError(
                    f"page {page_number}: waqf source glyph differs for {key}"
                )
            status = record["status"]
            counts["text_signs"] += 1
            counts[f"text:{record['mark']}"] += 1
            counts[f"{status}_source_glyphs"] += 1
            counts[f"{status}:{record['mark']}"] += 1
            if status == "separate":
                paths[(key, index)] = record["mark"]
            seen.add(key)
        for group in page.get("shared_groups", []):
            for word in group["canonical_words"]:
                if any(
                    char in WAQF_MARK_BY_CHAR for char in word["text"]["rasm_uthmani"]
                ):
                    raise ValueError(
                        f"page {page_number}: shared word {word['word_key']} has unresolved waqf ownership"
                    )
        if seen != set(expected):
            missing = sorted(set(expected) - seen, key=numeric_key)
            raise ValueError(
                f"page {page_number}: unused waqf ledger records: {missing}"
            )
        return paths, counts

    def summary(self, counts: Counter) -> dict:
        marks = sorted(WAQF_MARK_BY_CHAR.values())
        return {
            "qualification": "source-glyph-qualified",
            "text_signs": counts["text_signs"],
            "separate_source_glyphs": counts["separate_source_glyphs"],
            "fused_source_glyphs": counts["fused_source_glyphs"],
            "text_signs_by_mark": {
                mark: counts[f"text:{mark}"] for mark in marks if counts[f"text:{mark}"]
            },
            "separate_source_glyphs_by_mark": {
                mark: counts[f"separate:{mark}"]
                for mark in marks
                if counts[f"separate:{mark}"]
            },
            "fused_source_glyphs_by_mark": {
                mark: counts[f"fused:{mark}"]
                for mark in marks
                if counts[f"fused:{mark}"]
            },
        }

    def verify_complete(self, pages: list[int], counts: Counter) -> None:
        if pages != list(range(1, 605)):
            return
        if self.summary(counts) != {
            "qualification": "source-glyph-qualified",
            **self.expected_counts,
        }:
            raise ValueError("complete waqf output counts differ")


def verify_page(page: dict, header_assets: HeaderAssets | None = None) -> None:
    page_number = page.get("page")
    if page.get("schema") != "quran-svg-elements/qcf-v1-map-page":
        raise ValueError(f"page {page_number}: wrong map schema")
    if page.get("schema_version") != 3:
        raise ValueError(f"page {page_number}: expected map schema 3")
    page_number_source = page.get("page_number_source")
    if (
        not isinstance(page_number_source, dict)
        or page_number_source.get("dataset") != "qpc-old"
        or not isinstance(page_number_source.get("first_ayah_id"), int)
        or page_number_source["first_ayah_id"] < 1
    ):
        raise ValueError(f"page {page_number}: invalid page-number source")
    lines = page.get("lines", [])
    line_numbers = [line["line"] for line in lines]
    if line_numbers != sorted(set(line_numbers)):
        raise ValueError(f"page {page_number}: line numbers are not unique and sorted")
    unknown = [
        line["type"] for line in lines if line["type"] not in {"ayah", *HEADER_TYPES}
    ]
    if unknown:
        raise ValueError(
            f"page {page_number}: unknown line types: {sorted(set(unknown))}"
        )

    words = page.get("words", [])
    word_by_key = {word["word_key"]: word for word in words}
    if len(word_by_key) != len(words):
        raise ValueError(f"page {page_number}: duplicate word keys")
    listed = [key for line in lines for key in line["word_keys"]]
    if len(listed) != len(set(listed)) or set(listed) != set(word_by_key):
        raise ValueError(f"page {page_number}: line word coverage differs")
    for line in lines:
        for key in line["word_keys"]:
            if word_by_key[key]["line"] != line["line"]:
                raise ValueError(
                    f"page {page_number}: {key} is listed on the wrong line"
                )
    for word in words:
        verify_glyphs(page_number, word["word_key"], word.get("glyphs", []))

    groups = page.get("shared_groups", [])
    if not isinstance(groups, list):
        raise TypeError(f"page {page_number}: shared groups must be a list")
    group_by_id = {}
    shared_word_by_key = {}
    for group in groups:
        if not isinstance(group, dict):
            raise TypeError(f"page {page_number}: invalid shared group")
        group_id = group.get("id")
        keys = group.get("canonical_word_keys")
        canonical = group.get("canonical_words")
        if not isinstance(group_id, str) or not group_id or group_id in group_by_id:
            raise ValueError(f"page {page_number}: invalid shared-group id")
        if (
            not isinstance(keys, list)
            or len(keys) < 2
            or not isinstance(canonical, list)
            or [word.get("word_key") for word in canonical] != keys
        ):
            raise ValueError(
                f"page {page_number}: shared group {group_id} word keys differ"
            )
        parsed = [numeric_key(key) for key in keys]
        if (
            any(len(key) != 3 for key in parsed)
            or any(key[:2] != parsed[0][:2] for key in parsed)
            or [key[2] for key in parsed]
            != list(range(parsed[0][2], parsed[0][2] + len(parsed)))
        ):
            raise ValueError(
                f"page {page_number}: shared group {group_id} keys are not consecutive"
            )
        ayah_key = f"{parsed[0][0]}:{parsed[0][1]}"
        if (
            group.get("page") != page_number
            or group.get("ayah_key") != ayah_key
            or group.get("line") not in line_numbers
            or not isinstance(group.get("box"), list)
            or len(group["box"]) != 4
        ):
            raise ValueError(
                f"page {page_number}: shared group {group_id} ownership differs"
            )
        glyphs = group.get("glyphs", [])
        verify_glyphs(page_number, f"shared group {group_id}", glyphs)
        glyph_box = [
            min(glyph["box"][0] for glyph in glyphs),
            min(glyph["box"][1] for glyph in glyphs),
            max(glyph["box"][2] for glyph in glyphs),
            max(glyph["box"][3] for glyph in glyphs),
        ]
        if group["box"] != glyph_box or group.get("source_text") != "".join(
            glyph["text"] for glyph in glyphs
        ):
            raise ValueError(
                f"page {page_number}: shared group {group_id} geometry differs"
            )
        for canonical_word in canonical:
            key = canonical_word["word_key"]
            text_fields = canonical_word.get("text")
            if (
                key in word_by_key
                or key in shared_word_by_key
                or not isinstance(text_fields, dict)
                or set(text_fields) != set(TEXT_FIELDS)
                or any(not isinstance(text_fields[field], str) for field in TEXT_FIELDS)
            ):
                raise ValueError(f"page {page_number}: invalid shared word {key}")
            shared_word_by_key[key] = {
                "word_key": key,
                "ayah_key": ayah_key,
                "line": group["line"],
                "box": group["box"],
                "text": text_fields,
            }
        group_by_id[group_id] = group

    listed_shared = [key for line in lines for key in line.get("shared_word_keys", [])]
    if len(listed_shared) != len(set(listed_shared)) or set(listed_shared) != set(
        shared_word_by_key
    ):
        raise ValueError(f"page {page_number}: line shared-word coverage differs")
    for line in lines:
        for key in line.get("shared_word_keys", []):
            if shared_word_by_key[key]["line"] != line["line"]:
                raise ValueError(
                    f"page {page_number}: shared word {key} is listed on the wrong line"
                )

    markers = page.get("ayah_markers", [])
    marker_by_ayah = {marker["ayah_key"]: marker for marker in markers}
    if len(marker_by_ayah) != len(markers):
        raise ValueError(f"page {page_number}: duplicate ayah markers")
    ayahs = {word["ayah_key"] for word in words} | {
        group["ayah_key"] for group in groups
    }
    if set(marker_by_ayah) != ayahs:
        raise ValueError(f"page {page_number}: ayah marker coverage differs")
    valid_lines = set(line_numbers)
    markers_by_line = defaultdict(list)
    for key, marker in marker_by_ayah.items():
        if marker["line"] not in valid_lines:
            raise ValueError(f"page {page_number}: marker {key} is on an unknown line")
        verify_glyphs(page_number, f"ayah marker {key}", marker.get("glyphs", []))
        markers_by_line[marker["line"]].append(key)

    for line in lines:
        if line["type"] in HEADER_TYPES:
            if any(
                line.get(name)
                for name in ("word_keys", "shared_word_keys", "ayah_keys", "content")
            ):
                raise ValueError(
                    f"page {page_number}: header line {line['line']} owns body content"
                )
            if line.get("is_centered") is not True:
                raise ValueError(
                    f"page {page_number}: header line {line['line']} is not centered"
                )
            if header_assets is None:
                raise DeferredPage(
                    f"page {page_number}: V4 placement asset required for {line['type']}"
                )
            header_assets.asset_for(line)
            continue

        declared = line.get("ayah_keys", [])
        expected = (
            {word_by_key[key]["ayah_key"] for key in line["word_keys"]}
            | {shared_word_by_key[key]["ayah_key"] for key in line["shared_word_keys"]}
            | set(markers_by_line[line["line"]])
        )
        if len(declared) != len(set(declared)) or set(declared) != expected:
            raise ValueError(
                f"page {page_number}: line {line['line']} ayah coverage differs"
            )
        verify_line_content(page_number, line, word_by_key, group_by_id, marker_by_ayah)


def vector_settings(
    manifest: dict,
) -> tuple[dict, float, dict[int, float], float, float, float]:
    if manifest.get("schema") != "quran-svg-elements/qcf-v1-vector-source":
        raise ValueError("wrong QCF V1 vector manifest schema")
    if manifest.get("schema_version") != 1 or manifest.get("edition") != "hafs-qcf-v1":
        raise ValueError("wrong QCF V1 vector manifest version or edition")
    if manifest.get("print_year_hijri") != 1405:
        raise ValueError("QCF V1 vector manifest must target the 1405H print")

    output = manifest.get("output")
    if not isinstance(output, dict) or output.get("path_kind") != "other":
        raise ValueError("QCF V1 body paths must remain data-kind=other")
    for name in ("source_width", "source_height", "page_width", "em_pixels"):
        value = output.get(name)
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"manifest {name.replace('_', ' ')} must be positive")
    maximum_rsb_em = output.get("body_advance_maximum_rsb_em")
    minimum_advance_advantage_em = output.get("body_advance_minimum_advantage_em")
    if maximum_rsb_em != -0.25:
        raise ValueError("body advance-cell RSB threshold must be exactly -0.25 em")
    if minimum_advance_advantage_em != 0.125:
        raise ValueError(
            "body advance-cell evidence threshold must be exactly 0.125 em"
        )
    if output.get("body_advance_blend") != 0.5:
        raise ValueError("body advance-cell blend must be exactly 0.5")
    if output.get("body_visible_ink_minimum_advantage_em") != 1.75:
        raise ValueError("body visible-ink evidence threshold must be exactly 1.75 em")
    if output.get("body_visible_ink_source_width_ratio") != [0.95, 1.05]:
        raise ValueError(
            "body visible-ink source-width ratio must be exactly [0.95, 1.05]"
        )

    raw_overrides = output.get("page_em_pixels", {})
    if not isinstance(raw_overrides, dict):
        raise TypeError("manifest page em pixels must be an object")
    overrides = {}
    for key, value in raw_overrides.items():
        if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key:
            raise ValueError(f"invalid page em override key: {key!r}")
        page = int(key)
        if page < 1 or page > 604:
            raise ValueError(f"page em override is out of range: {page}")
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"page {page} em pixels must be positive")
        overrides[page] = float(value)
    return (
        output,
        float(output["em_pixels"]),
        overrides,
        float(output["page_width"]),
        float(maximum_rsb_em),
        float(minimum_advance_advantage_em),
    )


def header_settings(manifest: dict) -> dict:
    settings = manifest.get("header_placement")
    required = {
        "source",
        "qualification",
        "path_kind",
        "line_grid",
        "center_x",
        "surah_name",
        "basmalah",
        "evidence",
    }
    if not isinstance(settings, dict) or set(settings) != required:
        raise ValueError("wrong V4 header placement fields")
    if (
        settings["source"] != "1405h-scan-calibrated-complete-v4-assets"
        or settings["qualification"] != "mechanically-qualified"
        or settings["path_kind"] != "header_ink"
    ):
        raise ValueError("wrong V4 header placement policy")
    line_grid = settings["line_grid"]
    if not isinstance(line_grid, dict) or set(line_grid) != {
        "first_line_center",
        "line_step",
    }:
        raise ValueError("wrong V1 line-grid fields")
    for name, value in line_grid.items():
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"line grid {name} must be positive")
    center_x = settings["center_x"]
    if not isinstance(center_x, (int, float)) or center_x <= 0:
        raise ValueError("header center x must be positive")
    for line_type in HEADER_TYPES:
        placement = settings[line_type]
        if not isinstance(placement, dict) or set(placement) != {
            "target_width",
            "center_y_offset",
        }:
            raise ValueError(f"wrong {line_type} placement fields")
        if (
            not isinstance(placement["target_width"], (int, float))
            or placement["target_width"] <= 0
            or not isinstance(placement["center_y_offset"], (int, float))
        ):
            raise ValueError(f"wrong {line_type} placement values")

    evidence = settings["evidence"]
    evidence_fields = {
        "reference_scan_tree_sha256",
        "comparison_report_sha256",
        "mechanical_audit_report_sha256",
        "clearance_search_sha256",
        "comparison_pages_sha256",
        "audited_pages_sha256",
        "qualified_pages_sha256",
        "qualified_index_sha256",
        "header_pages",
        "header_instances",
        "body_overlap_pages",
        "body_overlap_pixels",
        "mean_precision_10px",
        "mean_recall_10px",
        "mean_distance",
        "rejected_body_overlap_pages",
        "rejected_body_overlap_pixels",
        "rejected_mean_precision_10px",
        "rejected_mean_recall_10px",
        "rejected_mean_distance",
    }
    if not isinstance(evidence, dict) or set(evidence) != evidence_fields:
        raise ValueError("wrong header placement evidence fields")
    for name in (
        "reference_scan_tree_sha256",
        "comparison_report_sha256",
        "mechanical_audit_report_sha256",
        "clearance_search_sha256",
        "comparison_pages_sha256",
        "audited_pages_sha256",
        "qualified_pages_sha256",
        "qualified_index_sha256",
    ):
        value = evidence[name]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"wrong header placement evidence digest: {name}")
    if evidence["header_pages"] != 116 or evidence["header_instances"] != 226:
        raise ValueError("wrong header placement evidence coverage")
    if evidence["body_overlap_pages"] != 0 or evidence["body_overlap_pixels"] != 0:
        raise ValueError("qualified header placement overlaps body ink")
    for name in (
        "mean_precision_10px",
        "mean_recall_10px",
        "rejected_mean_precision_10px",
        "rejected_mean_recall_10px",
    ):
        value = evidence[name]
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"wrong header placement evidence metric: {name}")
    for name in (
        "mean_distance",
        "rejected_mean_distance",
        "rejected_body_overlap_pages",
        "rejected_body_overlap_pixels",
    ):
        value = evidence[name]
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"wrong header placement evidence metric: {name}")
    if (
        evidence["mean_precision_10px"] <= evidence["rejected_mean_precision_10px"]
        or evidence["mean_recall_10px"] <= evidence["rejected_mean_recall_10px"]
        or evidence["mean_distance"] >= evidence["rejected_mean_distance"]
    ):
        raise ValueError(
            "header placement evidence does not improve the rejected baseline"
        )
    return settings


def header_scale(line_type: str, asset: dict, settings: dict) -> float:
    x0, _, x1, _ = asset["box"]
    width = x1 - x0
    if width <= 0:
        raise ValueError(f"{line_type} asset has no visual width")
    return settings[line_type]["target_width"] / width


def header_source_box(
    line: dict,
    asset: dict,
    source_width: float,
    source_height: float,
    settings: dict,
) -> list[float]:
    scale = header_scale(line["type"], asset, settings)
    x0, y0, x1, y1 = asset["box"]
    width = (x1 - x0) * scale
    height = (y1 - y0) * scale
    centre_x = settings["center_x"]
    centre_y = (
        settings["line_grid"]["first_line_center"]
        + (line["line"] - 1) * settings["line_grid"]["line_step"]
        + settings[line["type"]]["center_y_offset"]
    )
    box = [
        centre_x - width / 2,
        centre_y - height / 2,
        centre_x + width / 2,
        centre_y + height / 2,
    ]
    if box[0] < 0 or box[2] > source_width or box[1] < 0 or box[3] > source_height:
        raise ValueError(
            f"line {line['line']} {line['type']} leaves the source page: {box}"
        )
    return box


def header_element(
    line: dict,
    asset: dict,
    chapter: dict,
    source_width: float,
    source_height: float,
    page_factor: float,
    settings: dict,
) -> str:
    box = header_source_box(line, asset, source_width, source_height, settings)
    scale = header_scale(line["type"], asset, settings)
    x0, _, _, y1 = asset["box"]
    final_scale = scale * page_factor
    tx = (box[0] - scale * x0) * page_factor
    baseline = (box[1] + scale * y1) * page_factor
    transform = (
        f"matrix({number(final_scale)} 0 0 {number(-final_scale)} "
        f"{number(tx)} {number(baseline)})"
    )
    class_name = HEADER_TYPES[line["type"]]
    target_width = settings[line["type"]]["target_width"]
    return (
        f'<g class="{class_name}" data-sid="{line["surah"]}" '
        f'data-surah-name-ar="{attr(chapter["arabic"])}" '
        f'data-surah-name-latin="{attr(chapter["latin"])}" '
        f'data-surah-name-en="{attr(chapter["english"])}" '
        f'data-revelation-place="{attr(chapter["revelation_place"])}" '
        f'data-ayah-count="{chapter["ayah_count"]}" '
        f'data-source="qpc-v4" data-codepoint="{asset["codepoint"]}" '
        f'data-asset-path="{attr(asset["path"])}" '
        f'data-placement-source="{settings["source"]}" '
        f'data-placement-qualification="{settings["qualification"]}" '
        f'data-target-width="{number(target_width)}">'
        f'<path data-kind="{settings["path_kind"]}" d="{attr(asset["d"])}" '
        f'transform="{transform}"/>'
        "</g>"
    )


def verify_coordinate_space(page: dict, output: dict) -> None:
    expected = {
        "width": output["source_width"],
        "height": output["source_height"],
        "origin": "top-left",
        "units": "pixels",
    }
    if page.get("coordinate_space") != expected:
        raise ValueError(
            f"page {page['page']}: coordinate space changed: "
            f"{page.get('coordinate_space')} != {expected}"
        )


def page_glyphs(page: dict):
    for word in page["words"]:
        yield from word["glyphs"]
    for group in page.get("shared_groups", []):
        yield from group["glyphs"]
    for marker in page["ayah_markers"]:
        yield from marker["glyphs"]


def preflight_font(page: dict, font: PageFont, semantics: dict | None = None) -> None:
    for glyph in page_glyphs(page):
        font.outline(parse_codepoint(glyph["codepoint"]))
    for glyph in (semantics or {}).get("restored_glyphs", []):
        font.outline(parse_codepoint(glyph["codepoint"]))


def path_element(
    glyph: dict,
    font: PageFont,
    em_pixels: float,
    page_factor: float,
    mark: str | None = None,
    *,
    kind: str | None = None,
    mark_family: str | None = None,
    standalone: bool = False,
    ayah_key: str | None = None,
    visible_horizontal: bool = False,
    body_advance_maximum_rsb_em: float | None = None,
    body_advance_minimum_advantage_em: float | None = None,
    body_visible_ink_minimum_advantage_em: float | None = None,
    body_visible_ink_source_width_ratio: tuple[float, float]
    | list[float]
    | None = None,
) -> str:
    codepoint = parse_codepoint(glyph["codepoint"])
    path, bbox = font.outline(codepoint)
    body_visible_ink = False
    if (body_visible_ink_minimum_advantage_em is None) != (
        body_visible_ink_source_width_ratio is None
    ):
        raise ValueError("body visible-ink policy is incomplete")
    if body_visible_ink_minimum_advantage_em is not None:
        path, bbox, body_visible_ink = font.body_ink_outline(
            codepoint,
            abs(glyph["box"][2] - glyph["box"][0]),
            em_pixels,
            body_visible_ink_minimum_advantage_em,
            body_visible_ink_source_width_ratio,
        )
    if (body_advance_maximum_rsb_em is None) != (
        body_advance_minimum_advantage_em is None
    ):
        raise ValueError("body advance-cell policy is incomplete")
    if body_advance_maximum_rsb_em is not None:
        bbox = font.body_bounds(
            codepoint,
            bbox,
            abs(glyph["box"][2] - glyph["box"][0]),
            em_pixels,
            body_advance_maximum_rsb_em,
            body_advance_minimum_advantage_em,
        )
    if visible_horizontal:
        path, ink_bbox = font.ink_outline(codepoint)
        bbox = (ink_bbox[0], bbox[1], ink_bbox[2], bbox[3])
    scale, tx, baseline = glyph_transform(
        glyph["box"], bbox, font.units_per_em, em_pixels, page_factor
    )
    transform = (
        f"matrix({number(scale)} 0 0 {number(-scale)} {number(tx)} {number(baseline)})"
    )
    if kind is None:
        kind = "mark" if mark is not None else "other"
    if mark is not None and mark_family is None and not standalone:
        mark_family = "waqf"
    attributes = [f'data-kind="{attr(kind)}"']
    if mark is not None:
        attributes.append(f'data-mark="{attr(mark)}"')
    if mark_family is not None:
        attributes.append(f'data-mark-family="{attr(mark_family)}"')
    if standalone:
        attributes.append('data-standalone="1"')
    if ayah_key is not None:
        attributes.append(f'data-ayah-key="{attr(ayah_key)}"')
    if body_visible_ink:
        attributes.append('data-source-bounds="visible-ink"')
    return f'<path {" ".join(attributes)} d="{attr(path)}" transform="{transform}"/>'


def division_element(
    record: dict, font: PageFont, em_pixels: float, page_factor: float
) -> str:
    values = division_values(record["rubu_al_hizb"])
    return (
        '<g class="division-mark" data-mark="hizb" '
        f'data-ayah-key="{record["ayah_key"]}" '
        f'data-word-key="{record["word_key"]}" '
        f'data-rubu-al-hizb="{values["rubu_al_hizb"]}" '
        f'data-rubu-al-hizb-in-hizb="{values["rubu_al_hizb_in_hizb"]}" '
        f'data-nisf="{values["nisf"]}" data-hizb="{values["hizb"]}" '
        f'data-juz="{values["juz"]}">'
        + path_element(
            record["source_glyph"],
            font,
            em_pixels,
            page_factor,
            kind="mark",
            mark="hizb",
            standalone=True,
            ayah_key=record["ayah_key"],
        )
        + "</g>"
    )


def sajdah_element(
    record: dict, font: PageFont, em_pixels: float, page_factor: float
) -> str:
    return (
        '<g class="sajdah-mark" data-mark="sajdah" '
        f'data-ayah-key="{record["ayah_key"]}" '
        f'data-word-key="{record["word_key"]}" data-source="{record["source"]}">'
        + path_element(
            record["source_glyph"],
            font,
            em_pixels,
            page_factor,
            kind="mark",
            mark="sajdah_mark",
            mark_family="sajdah",
            standalone=True,
            ayah_key=record["ayah_key"],
        )
        + "</g>"
    )


def build_page(
    page: dict,
    font: PageFont,
    em_pixels: float,
    page_width: float,
    body_advance_maximum_rsb_em: float,
    body_advance_minimum_advantage_em: float,
    header_assets: HeaderAssets | None = None,
    header_placement: dict | None = None,
    surah_metadata: SurahMetadata | None = None,
    waqf_paths: dict[tuple[str, int], str] | None = None,
    semantics: dict | None = None,
    *,
    body_visible_ink_minimum_advantage_em: float | None = None,
    body_visible_ink_source_width_ratio: tuple[float, float]
    | list[float]
    | None = None,
) -> tuple[bytes, bytes]:
    verify_page(page, header_assets)
    waqf_paths = waqf_paths or {}
    coordinate = page["coordinate_space"]
    page_factor = page_width / coordinate["width"]
    page_height = coordinate["height"] * page_factor
    fragments_by_line = line_fragments(page)
    marker_by_ayah = {marker["ayah_key"]: marker for marker in page["ayah_markers"]}
    semantics = semantics or {
        "boundaries": {},
        "divisions": {},
        "sajdah_after": {},
        "sajdah_at_line_start": {},
        "skips": set(),
    }

    body = []
    emitted_boundaries = set()
    emitted_divisions = set()
    emitted_markers = set()
    emitted_sajdahs = set()
    emitted_headers = 0
    for line in page["lines"]:
        line_number = line["line"]
        line_parts = [f'<g class="line" data-line="{line_number}">']
        if line["type"] in HEADER_TYPES:
            if semantics["sajdah_at_line_start"].get(line_number):
                raise ValueError(
                    f"page {page['page']}: semantic mark occupies a header line"
                )
            if (
                header_assets is None
                or header_placement is None
                or surah_metadata is None
            ):
                raise DeferredPage(
                    f"page {page['page']}: V4 header placement is unavailable"
                )
            line_parts.append(
                header_element(
                    line,
                    header_assets.asset_for(line),
                    surah_metadata.for_surah(line["surah"]),
                    coordinate["width"],
                    coordinate["height"],
                    page_factor,
                    header_placement,
                )
            )
            emitted_headers += 1
        else:
            for record in semantics["sajdah_at_line_start"].get(line_number, []):
                if record["word_key"] in emitted_sajdahs:
                    raise ValueError(
                        f"page {page['page']}: sajdah mark was emitted twice"
                    )
                line_parts.append(sajdah_element(record, font, em_pixels, page_factor))
                emitted_sajdahs.add(record["word_key"])

            fragments_by_ayah = defaultdict(list)
            for fragment in fragments_by_line.get(line_number, []):
                fragments_by_ayah[fragment["ayah_key"]].append(fragment)

            for key in line["ayah_keys"]:
                surah, ayah = key.split(":")
                marker_id = f"ayah-mark-{surah}-{ayah}"
                division = semantics["divisions"].get(key)
                if division is not None and division["line"] == line_number:
                    if division["word_key"] in emitted_divisions:
                        raise ValueError(
                            f"page {page['page']}: division mark was emitted twice"
                        )
                    line_parts.append(
                        division_element(division, font, em_pixels, page_factor)
                    )
                    emitted_divisions.add(division["word_key"])
                boundary = semantics["boundaries"].get(key)
                if boundary is not None and boundary["line"] != line_number:
                    boundary = None
                for fragment in fragments_by_ayah.get(key, []):
                    start = ""
                    if boundary is not None and fragment["fragment"] == 1:
                        if key in emitted_boundaries:
                            raise ValueError(
                                f"page {page['page']}: division boundary was emitted twice"
                            )
                        start = boundary_attributes(boundary)
                        emitted_boundaries.add(key)
                    line_parts.append(
                        f'<g class="ayah-fragment" data-ayah-key="{key}" '
                        f'data-fragment="{fragment["fragment"]}" '
                        f'data-ayah-fragments="{fragment["fragments"]}" '
                        f'data-ayah-mark="{marker_id}"{start}>'
                    )
                    for word in fragment["words"]:
                        shared_owner = word.get("shared_path_owner")
                        shared = (
                            f' data-shared-paths-with="{shared_owner}"'
                            if shared_owner
                            else ""
                        )
                        line_parts.append(
                            f'<g class="word" data-word-key="{word["word_key"]}" '
                            f'data-rasm-uthmani="{attr(word["text"]["rasm_uthmani"])}"'
                            f"{shared}>"
                        )
                        line_parts.extend(
                            path_element(
                                glyph,
                                font,
                                em_pixels,
                                page_factor,
                                kind="mark" if mark is not None else "other",
                                mark=mark,
                                mark_family="waqf" if mark is not None else None,
                                body_advance_maximum_rsb_em=(
                                    body_advance_maximum_rsb_em
                                    if len(word["glyphs"]) == 1 and mark is None
                                    else None
                                ),
                                body_advance_minimum_advantage_em=(
                                    body_advance_minimum_advantage_em
                                    if len(word["glyphs"]) == 1 and mark is None
                                    else None
                                ),
                                body_visible_ink_minimum_advantage_em=(
                                    body_visible_ink_minimum_advantage_em
                                    if mark is None
                                    else None
                                ),
                                body_visible_ink_source_width_ratio=(
                                    body_visible_ink_source_width_ratio
                                    if mark is None
                                    else None
                                ),
                            )
                            for index, glyph in enumerate(word["glyphs"])
                            if (word["word_key"], index) not in semantics["skips"]
                            for mark in [waqf_paths.get((word["word_key"], index))]
                        )
                        line_parts.append("</g>")
                    line_parts.append("</g>")

                for record in semantics["sajdah_after"].get(key, []):
                    if record["line"] != line_number:
                        continue
                    if record["word_key"] in emitted_sajdahs:
                        raise ValueError(
                            f"page {page['page']}: sajdah mark was emitted twice"
                        )
                    line_parts.append(
                        sajdah_element(record, font, em_pixels, page_factor)
                    )
                    emitted_sajdahs.add(record["word_key"])

                marker = marker_by_ayah.get(key)
                if marker and marker["line"] == line_number:
                    line_parts.append(
                        f'<g class="ayah-mark" id="{marker_id}" data-ayah-key="{key}">'
                    )
                    line_parts.extend(
                        path_element(
                            glyph,
                            font,
                            em_pixels,
                            page_factor,
                            visible_horizontal=True,
                        )
                        for glyph in marker["glyphs"]
                    )
                    line_parts.append("</g>")
                    emitted_markers.add(key)
        line_parts.append("</g>")
        body.extend(line_parts)

    expected_boundaries = set(semantics["boundaries"])
    expected_divisions = {
        record["word_key"] for record in semantics["divisions"].values()
    }
    expected_sajdahs = {
        record["word_key"]
        for records in (
            *semantics["sajdah_after"].values(),
            *semantics["sajdah_at_line_start"].values(),
        )
        for record in records
    }
    if emitted_boundaries != expected_boundaries:
        raise ValueError(
            f"page {page['page']}: not every division boundary was emitted"
        )
    if emitted_divisions != expected_divisions:
        raise ValueError(f"page {page['page']}: not every division mark was emitted")
    if emitted_sajdahs != expected_sajdahs:
        raise ValueError(f"page {page['page']}: not every sajdah mark was emitted")
    if emitted_markers != set(marker_by_ayah):
        raise ValueError(f"page {page['page']}: not every ayah marker was emitted")
    expected_headers = sum(line["type"] in HEADER_TYPES for line in page["lines"])
    if emitted_headers != expected_headers:
        raise ValueError(f"page {page['page']}: not every V4 header was emitted")

    view_box = f"0 0 {number(page_width)} {number(page_height)}"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{view_box}" width="{number(page_width)}" '
        f'height="{number(page_height)}" data-page="{page["page"]}">'
        + "".join(body)
        + "</svg>\n"
    ).encode()

    words = []
    for word in logical_words(page):
        record = {
            "ayah_key": word["ayah_key"],
            "box": transformed_box(word["box"], page_factor),
            "line": word["line"],
            "word_key": word["word_key"],
        }
        record.update({field: word["text"][field] for field in TEXT_FIELDS})
        words.append(record)
    index = {
        "box_space": f"viewBox units of pages/{page['page']:03}.svg",
        "count": len(words),
        "edition": "hafs-qcf-v1",
        "license": "CC-BY-4.0",
        "page": page["page"],
        "page_number_source": page["page_number_source"],
        "rights": (
            "CC BY 4.0 covers this project's decomposition, labels and indexes, "
            "with attribution waived for use inside a product. The page artwork and "
            "Quranic text are the King Fahd Glorious Quran Printing Complex's."
        ),
        "schema": "quran-svg-elements/page-words",
        "schema_version": "1.0.0",
        "view_box": view_box,
        "words": words,
    }
    return svg, json_bytes(index)


def verify_sources(map_dir: Path, fonts_dir: Path, manifest: dict) -> None:
    summary = read_json(map_dir / "summary.json")
    if summary.get("schema") != "quran-svg-elements/qcf-v1-map":
        raise ValueError("wrong QCF V1 map summary schema")
    if (
        summary.get("schema_version") != 3
        or summary.get("edition") != manifest["edition"]
    ):
        raise ValueError("wrong QCF V1 map summary version or edition")

    page_files = sorted((map_dir / "pages").glob("[0-9][0-9][0-9].json"))
    font_files = sorted(fonts_dir.glob("QCF_P[0-9][0-9][0-9].TTF"))
    if len(page_files) != 604 or len(font_files) != 604:
        raise ValueError(
            f"expected 604 map pages and page fonts, got "
            f"{len(page_files)} and {len(font_files)}"
        )
    actual_pages = tree_sha256(page_files)
    if actual_pages != summary.get("page_files_sha256"):
        raise ValueError("map summary does not match its page files")

    checks = {
        "map_page_files_sha256": actual_pages,
        "map_source_manifest_sha256": summary.get("source_manifest_sha256"),
        "page_font_tree_sha256": tree_sha256(font_files),
    }
    wrong = {
        name: {"expected": manifest["inputs"].get(name), "actual": actual}
        for name, actual in checks.items()
        if manifest["inputs"].get(name) != actual
    }
    if wrong:
        raise ValueError(
            "vector source digest mismatch:\n" + json.dumps(wrong, indent=2)
        )


def select_pages(
    map_dir: Path, value: str, header_assets: HeaderAssets | None = None
) -> tuple[list[dict], list[dict]]:
    if value != "supported":
        pages = [
            read_json(map_dir / "pages" / f"{number:03}.json")
            for number in parse_pages(value)
        ]
        for page in pages:
            verify_page(page, header_assets)
        return pages, []

    pages = []
    rejected = []
    for number in range(1, 605):
        page = read_json(map_dir / "pages" / f"{number:03}.json")
        try:
            verify_page(page, header_assets)
        except DeferredPage as error:
            rejected.append({"page": number, "reason": str(error)})
        else:
            pages.append(page)
    if not pages:
        raise ValueError("no supported QCF V1 pages")
    return pages, rejected


def qualified_geometry_svg(svg: bytes) -> bytes:
    for mark in WAQF_MARK_BY_CHAR.values():
        svg = svg.replace(
            (f'data-kind="mark" data-mark="{mark}" data-mark-family="waqf"').encode(),
            b'data-kind="other"',
        )
    return svg


PATH_GEOMETRY_ATTRIBUTES = ("d", "transform", "fill-rule", "clip-rule")


def path_geometry_records(svg: bytes) -> list[tuple[str, ...]]:
    root = ElementTree.fromstring(svg)
    records = []
    for element in root.iter(f"{{{SVG_NAMESPACE}}}path"):
        if not element.attrib.get("d"):
            raise ValueError("SVG path has no geometry")
        records.append(
            tuple(element.attrib.get(name, "") for name in PATH_GEOMETRY_ATTRIBUTES)
        )
    return records


def path_geometry_bytes(records: list[tuple[str, ...]]) -> bytes:
    return json_bytes(records)


def inserted_path_geometry(
    base: list[tuple[str, ...]], emitted: list[tuple[str, ...]]
) -> list[tuple[str, ...]]:
    if len(emitted) < len(base):
        raise ValueError("semantic output removed path geometry")
    base_index = 0
    inserted = []
    for record in emitted:
        if base_index < len(base) and record == base[base_index]:
            base_index += 1
        else:
            inserted.append(record)
    if base_index != len(base):
        raise ValueError("semantic output changed path geometry or order")
    return inserted


def path_element_geometry(value: str) -> tuple[str, ...]:
    element = ElementTree.fromstring(value)
    return tuple(element.attrib.get(name, "") for name in PATH_GEOMETRY_ATTRIBUTES)


def audited_header_svg(svg: bytes) -> bytes:
    return qualified_geometry_svg(svg).replace(
        b'data-placement-qualification="mechanically-qualified"',
        b'data-placement-qualification="candidate"',
    )


def verify_header_qualification_output(
    placement: dict,
    pages: list[dict],
    pages_sha256: str,
    audited_pages_sha256: str,
    index_sha256: str,
) -> None:
    page_numbers = [page["page"] for page in pages]
    if page_numbers != list(range(1, 605)):
        return
    evidence = placement["evidence"]
    if pages_sha256 != evidence["qualified_pages_sha256"]:
        raise ValueError("qualified header page digest differs")
    if audited_pages_sha256 != evidence["audited_pages_sha256"]:
        raise ValueError("audited header geometry digest differs")
    if index_sha256 != evidence["qualified_index_sha256"]:
        raise ValueError("qualified header index digest differs")


def build(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    (
        output,
        default_em_pixels,
        page_em_overrides,
        page_width,
        body_advance_maximum_rsb_em,
        body_advance_minimum_advantage_em,
    ) = vector_settings(manifest)
    body_visible_ink_minimum_advantage_em = float(
        output["body_visible_ink_minimum_advantage_em"]
    )
    body_visible_ink_source_width_ratio = tuple(
        map(float, output["body_visible_ink_source_width_ratio"])
    )
    placement = header_settings(manifest)
    headers = HeaderAssets(args.header_assets_dir, manifest)
    chapters = SurahMetadata(args.chapters_metadata, args.surah_names, manifest)
    waqf = WaqfSourceGlyphs(args.waqf_source_glyphs, manifest)
    semantics = DivisionSajdahSemantics(args.division_sajdah_source, manifest)
    verify_sources(args.map_dir, args.fonts_dir, manifest)

    pages, rejected = select_pages(args.map_dir, args.pages, headers)
    waqf_paths_by_page = {}
    semantics_by_page = {}
    waqf_counts = Counter()
    semantic_counts = Counter()
    for page in pages:
        verify_coordinate_space(page, output)
        waqf_paths, counts = waqf.classify_page(page)
        page_semantics = semantics.page(page)
        waqf_paths_by_page[page["page"]] = waqf_paths
        semantics_by_page[page["page"]] = page_semantics
        waqf_counts.update(counts)
        semantic_counts.update(page_semantics["counts"])
        font_path = args.fonts_dir / f"QCF_P{page['page']:03}.TTF"
        with PageFont(font_path) as font:
            preflight_font(page, font, page_semantics)
    page_numbers = [page["page"] for page in pages]
    waqf.verify_complete(page_numbers, waqf_counts)
    semantics.verify_complete(page_numbers, semantic_counts)

    if args.out_dir.exists():
        raise ValueError(f"output path already exists: {args.out_dir}")
    temporary_out = args.out_dir.with_name(args.out_dir.name + ".tmp")
    if temporary_out.exists():
        raise ValueError(
            f"temporary output path already exists; inspect interrupted build: {temporary_out}"
        )

    page_hash = hashlib.sha256()
    qualified_geometry_page_hash = hashlib.sha256()
    header_qualified_geometry_page_hash = hashlib.sha256()
    base_path_geometry_page_hash = hashlib.sha256()
    emitted_path_geometry_page_hash = hashlib.sha256()
    audited_page_hash = hashlib.sha256()
    index_hash = hashlib.sha256()
    total_words = 0
    total_glyphs = 0
    total_headers = 0
    total_base_paths = 0
    total_emitted_paths = 0
    total_body_visible_ink_paths = 0
    for page in pages:
        page_number = page["page"]
        em_pixels = page_em_overrides.get(page_number, default_em_pixels)
        waqf_paths = waqf_paths_by_page[page_number]
        page_semantics = semantics_by_page[page_number]
        with PageFont(args.fonts_dir / f"QCF_P{page_number:03}.TTF") as font:
            qualified_svg, qualified_index = build_page(
                page,
                font,
                em_pixels,
                page_width,
                body_advance_maximum_rsb_em,
                body_advance_minimum_advantage_em,
                headers,
                placement,
                chapters,
                waqf_paths,
                body_visible_ink_minimum_advantage_em=(
                    body_visible_ink_minimum_advantage_em
                ),
                body_visible_ink_source_width_ratio=(
                    body_visible_ink_source_width_ratio
                ),
            )
            svg, index = build_page(
                page,
                font,
                em_pixels,
                page_width,
                body_advance_maximum_rsb_em,
                body_advance_minimum_advantage_em,
                headers,
                placement,
                chapters,
                waqf_paths,
                page_semantics,
                body_visible_ink_minimum_advantage_em=(
                    body_visible_ink_minimum_advantage_em
                ),
                body_visible_ink_source_width_ratio=(
                    body_visible_ink_source_width_ratio
                ),
            )
            base_path_geometry = path_geometry_records(qualified_svg)
            emitted_path_geometry = path_geometry_records(svg)
            inserted_geometry = inserted_path_geometry(
                base_path_geometry, emitted_path_geometry
            )
            expected_inserted_geometry = [
                path_element_geometry(
                    path_element(
                        glyph, font, em_pixels, page_width / output["source_width"]
                    )
                )
                for glyph in page_semantics["restored_glyphs"]
            ]
            if inserted_geometry != expected_inserted_geometry:
                raise ValueError(
                    f"page {page_number}: semantic output path additions differ"
                )
        qualified_visible_ink = qualified_svg.count(b'data-source-bounds="visible-ink"')
        emitted_visible_ink = svg.count(b'data-source-bounds="visible-ink"')
        if qualified_visible_ink != emitted_visible_ink:
            raise ValueError(
                f"page {page_number}: semantic output changed visible-ink body paths"
            )
        total_body_visible_ink_paths += emitted_visible_ink
        if index != qualified_index:
            raise ValueError(
                f"page {page_number}: semantic output changed the word index"
            )
        svg_path = temporary_out / "pages" / f"{page_number:03}.svg"
        index_path = temporary_out / "index/by-page" / f"{page_number:03}.json"
        write_bytes(svg_path, svg)
        write_bytes(index_path, index)
        page_hash.update(svg_path.name.encode())
        page_hash.update(b"\0")
        page_hash.update(svg)
        qualified_geometry_page_hash.update(svg_path.name.encode())
        qualified_geometry_page_hash.update(b"\0")
        qualified_geometry_page_hash.update(qualified_geometry_svg(svg))
        header_qualified_geometry_page_hash.update(svg_path.name.encode())
        header_qualified_geometry_page_hash.update(b"\0")
        header_qualified_geometry_page_hash.update(
            qualified_geometry_svg(qualified_svg)
        )
        base_path_geometry_page_hash.update(svg_path.name.encode())
        base_path_geometry_page_hash.update(b"\0")
        base_path_geometry_page_hash.update(path_geometry_bytes(base_path_geometry))
        emitted_path_geometry_page_hash.update(svg_path.name.encode())
        emitted_path_geometry_page_hash.update(b"\0")
        emitted_path_geometry_page_hash.update(
            path_geometry_bytes(emitted_path_geometry)
        )
        audited_page_hash.update(svg_path.name.encode())
        audited_page_hash.update(b"\0")
        audited_page_hash.update(audited_header_svg(qualified_svg))
        index_hash.update(index_path.name.encode())
        index_hash.update(b"\0")
        index_hash.update(index)
        total_words += len(logical_words(page))
        total_glyphs += sum(1 for _ in page_glyphs(page)) + len(
            page_semantics["restored_glyphs"]
        )
        total_headers += sum(line["type"] in HEADER_TYPES for line in page["lines"])
        total_base_paths += len(base_path_geometry)
        total_emitted_paths += len(emitted_path_geometry)

    pages_sha256 = page_hash.hexdigest()
    qualified_geometry_pages_sha256 = qualified_geometry_page_hash.hexdigest()
    header_qualified_geometry_pages_sha256 = (
        header_qualified_geometry_page_hash.hexdigest()
    )
    base_path_geometry_pages_sha256 = base_path_geometry_page_hash.hexdigest()
    emitted_path_geometry_pages_sha256 = emitted_path_geometry_page_hash.hexdigest()
    audited_pages_sha256 = audited_page_hash.hexdigest()
    index_sha256 = index_hash.hexdigest()
    verify_header_qualification_output(
        placement,
        pages,
        header_qualified_geometry_pages_sha256,
        audited_pages_sha256,
        index_sha256,
    )

    page_height = output["source_height"] * page_width / output["source_width"]
    report = {
        "schema": "quran-svg-elements/qcf-v1-vector-slice",
        "schema_version": 5,
        "edition": manifest["edition"],
        "print_year_hijri": manifest["print_year_hijri"],
        "selection": args.pages,
        "pages": page_numbers,
        "rejected": rejected,
        "counts": {
            "pages": len(pages),
            "rejected_pages": len(rejected),
            "words": total_words,
            "glyphs": total_glyphs,
            "headers": total_headers,
            "body_visible_ink_paths": total_body_visible_ink_paths,
            **{name: semantic_counts[name] for name in sorted(semantics.COUNT_FIELDS)},
        },
        "em_pixels": default_em_pixels,
        "page_em_pixels": output.get("page_em_pixels", {}),
        "body_advance_maximum_rsb_em": body_advance_maximum_rsb_em,
        "body_advance_minimum_advantage_em": body_advance_minimum_advantage_em,
        "body_advance_blend": float(output["body_advance_blend"]),
        "body_visible_ink_minimum_advantage_em": (
            body_visible_ink_minimum_advantage_em
        ),
        "body_visible_ink_source_width_ratio": list(
            body_visible_ink_source_width_ratio
        ),
        "page_width": page_width,
        "page_height": page_height,
        "pages_sha256": pages_sha256,
        "qualified_geometry_pages_sha256": qualified_geometry_pages_sha256,
        "header_qualified_geometry_pages_sha256": (
            header_qualified_geometry_pages_sha256
        ),
        "path_geometry": {
            "qualification": "base-order-preserved",
            "base_paths": total_base_paths,
            "emitted_paths": total_emitted_paths,
            "restored_paths": total_emitted_paths - total_base_paths,
            "base_pages_sha256": base_path_geometry_pages_sha256,
            "emitted_pages_sha256": emitted_path_geometry_pages_sha256,
        },
        "audited_header_pages_sha256": audited_pages_sha256,
        "index_sha256": index_sha256,
        "source_manifest_sha256": sha256(args.manifest),
        "waqf_source_glyphs_sha256": waqf.sha256,
        "waqf": waqf.summary(waqf_counts),
        "division_sajdah_source_sha256": semantics.sha256,
        "header_asset_summary_sha256": headers.summary_sha256,
        "header_asset_files_sha256": headers.files_sha256,
        "chapters_metadata_sha256": chapters.chapters_sha256,
        "surah_names_sha256": chapters.names_sha256,
        "header_placement": placement,
        "deferred": manifest["deferred"],
    }
    write_bytes(temporary_out / "summary.json", json_bytes(report, pretty=True))
    temporary_out.replace(args.out_dir)
    print(json.dumps(report, indent=2))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--map-dir", type=Path, default=DEFAULT_MAP_DIR)
    command.add_argument("--fonts-dir", type=Path, required=True)
    command.add_argument("--header-assets-dir", type=Path, required=True)
    command.add_argument("--chapters-metadata", type=Path, required=True)
    command.add_argument("--surah-names", type=Path, default=DEFAULT_SURAH_NAMES)
    command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    command.add_argument(
        "--waqf-source-glyphs", type=Path, default=DEFAULT_WAQF_SOURCE_GLYPHS
    )
    command.add_argument(
        "--division-sajdah-source",
        type=Path,
        default=DEFAULT_DIVISION_SAJDAH_SOURCE,
    )
    command.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    command.add_argument(
        "--pages",
        default="supported",
        help="`supported`, or comma-separated pages and ranges",
    )
    return command


def main() -> None:
    args = parser().parse_args()
    for name in (
        "map_dir",
        "fonts_dir",
        "header_assets_dir",
        "chapters_metadata",
        "surah_names",
        "manifest",
        "waqf_source_glyphs",
        "division_sajdah_source",
        "out_dir",
    ):
        setattr(args, name, getattr(args, name).resolve())
    build(args)


if __name__ == "__main__":
    main()
