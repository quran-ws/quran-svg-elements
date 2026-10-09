#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the KFGQPC V1 glyph-to-word map from pinned source records.

QUL layout 15 owns the printed word grouping and line semantics. The quran-ios
Hafs 1405 ayahinfo database owns one rectangle per glyph code. The Quran Engine
index owns canonical word keys and readable text forms.

Acquisition and normalization are separate:

  python tools/build_qcf_v1_map.py fetch --pages-dir .cache/qcf-v1/qul-pages
  python tools/build_qcf_v1_map.py build \
    --pages-dir .cache/qcf-v1/qul-pages \
    --canonical-index /path/to/quran-engine/index/by-page \
    --ayahinfo-db /path/to/ayahinfo_1920.db \
    --font-text /path/to/qpc-fonts/mushaf.txt \
    --fonts-dir /path/to/qpc-fonts/mushaf
"""

import argparse
import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES_DIR = ROOT / ".cache/qcf-v1/qul-pages"
DEFAULT_OUT_DIR = ROOT / ".cache/qcf-v1/map"
DEFAULT_MANIFEST = ROOT / "conformance/qcf-v1-source.json"
DEFAULT_SEG_PLAN = ROOT / ".cache/word_by_word_translation/seg_plan.json"
BASE_URL = "https://qul.tarteel.ai/resources/mushaf-layout/15?page={page}"  # terminology: ignore
QCF4_HEADER = "Sura,Verse,PageNo,LineNo,FontFile,FontCode,Type"  # terminology: ignore
QCF4_COLUMNS = tuple(QCF4_HEADER.split(","))
QCF4_FIELDS = (
    "surah",
    "ayah",
    "page",
    "line",
    "font_file_id",
    "font_code",
    "type",
)
QCF4_BASMALAH_CODE = 2013
USER_AGENT = "Mozilla/5.0 Chrome/153 Safari/537.36"
TEXT_FIELDS = ("rasm_uthmani", "rasm_imlai", "qpc", "rasm", "search")


def json_bytes(value: object, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        )
    return text.encode()


def write_json(path: Path, value: object, pretty: bool = False) -> bytes:
    data = json_bytes(value, pretty)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    return data


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


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


def numeric_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(":"))


def ayah_key(location: str) -> str:
    return location.rsplit(":", 1)[0]


def codepoints(text: str) -> list[str]:
    return [f"U+{ord(char):04X}" for char in text]


class LayoutPageParser(HTMLParser):
    def __init__(self, expected_page: int):
        super().__init__()
        self.expected_page = expected_page
        self.page = None
        self.current_line = None
        self.current_item = None
        self.in_item_link = False
        self.lines: dict[int, dict] = {}
        self.items: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "div":
            element_id = attributes.get("id") or ""
            if element_id.startswith("page-") and element_id[5:].isdigit():
                self.page = int(element_id[5:])
            if "line-container" in classes:
                self.current_line = int(attributes["data-line"])
                self.lines.setdefault(
                    self.current_line,
                    {
                        "line": self.current_line,
                        "type": "ayah",
                        "is_centered": False,
                        "surah": None,
                    },
                )
            elif "line" in classes and self.current_line is not None:
                line = self.lines[self.current_line]
                if "line--surah-name" in classes:
                    line["type"] = "surah_name"
                elif "line--bismillah" in classes:  # terminology: ignore
                    line["type"] = "basmalah"
                line["is_centered"] = (
                    "line--center" in classes or line["type"] != "ayah"
                )

        if tag == "span" and "char" in classes:
            if self.current_item is not None:
                raise ValueError("nested QUL char spans")
            if "char-word" in classes:
                kind = "word"
            elif "char-end" in classes:
                kind = "end"
            else:
                kind = next(
                    (
                        name.removeprefix("char-")
                        for name in classes
                        if name.startswith("char-")
                    ),
                    "unknown",
                )
            self.current_item = {
                "kind": kind,
                "line": self.current_line,
                "location": attributes.get("data-location"),
                "source_word_id": int(attributes["data-word-id"])
                if attributes.get("data-word-id")
                else None,
                "source_record_id": int(attributes["data-id"])
                if attributes.get("data-id")
                else None,
                "source_position": int(attributes["data-position"])
                if attributes.get("data-position")
                else None,
                "text_parts": [],
            }
        elif tag == "a" and self.current_item is not None:
            self.in_item_link = True

    def handle_data(self, data: str) -> None:
        if self.in_item_link and self.current_item is not None:
            self.current_item["text_parts"].append("".join(data.split()))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.in_item_link = False
        elif tag == "span" and self.current_item is not None:
            item = self.current_item
            item["text"] = "".join(item.pop("text_parts"))
            if item["line"] is None or not item["location"] or not item["text"]:
                raise ValueError(f"incomplete QUL item: {item}")
            item["page"] = self.expected_page
            item["page_order"] = len(self.items)
            self.items.append(item)
            self.current_item = None


def parse_page(text: str, expected_page: int) -> dict:
    parser = LayoutPageParser(expected_page)
    parser.feed(text)
    parser.close()
    if parser.page != expected_page:
        raise ValueError(f"QUL page says {parser.page}, expected {expected_page}")
    if not parser.lines or not parser.items:
        raise ValueError(f"QUL page {expected_page} has no mapped content")

    lines = [parser.lines[number] for number in sorted(parser.lines)]
    for line in lines:
        if line["type"] == "ayah":
            continue
        following = next(
            (item for item in parser.items if item["line"] > line["line"]),
            None,
        )
        if following is not None:
            line["surah"] = int(following["location"].split(":", 1)[0])

    return {
        "schema": "quran-svg-elements/qcf-v1-qul-page",
        "schema_version": 1,
        "layout_id": 15,
        "page": expected_page,
        "lines": lines,
        "items": parser.items,
    }


def validate_cached_page(value: dict, expected_page: int) -> None:
    if value.get("schema") != "quran-svg-elements/qcf-v1-qul-page":
        raise ValueError(f"page {expected_page}: wrong source schema")
    if value.get("page") != expected_page or value.get("layout_id") != 15:
        raise ValueError(f"page {expected_page}: wrong page or layout id")
    if not value.get("lines") or not value.get("items"):
        raise ValueError(f"page {expected_page}: empty source page")


def fetch_one(page: int, pages_dir: Path, refresh: bool, retries: int) -> str:
    destination = pages_dir / f"{page:03}.json"
    if destination.exists() and not refresh:
        validate_cached_page(read_json(destination), page)
        return "cached"

    request = urllib.request.Request(
        BASE_URL.format(page=page),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                page_data = parse_page(response.read().decode(), page)
            write_json(destination, page_data)
            return "fetched"
        except (OSError, UnicodeError, urllib.error.URLError, ValueError) as caught:
            error = caught
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"page {page}: {error}")


def fetch_pages(args: argparse.Namespace) -> None:
    args.pages_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(fetch_one, page, args.pages_dir, args.refresh, args.retries)
            for page in range(1, args.pages + 1)
        ]
        for done, future in enumerate(as_completed(futures), 1):
            try:
                counts[future.result()] += 1
            except RuntimeError as error:
                errors.append(str(error))
            if done % 25 == 0 or done == len(futures):
                print(
                    f"pages {done}/{len(futures)} "
                    f"fetched={counts['fetched']} cached={counts['cached']} errors={len(errors)}"
                )
    if errors:
        raise SystemExit("\n".join(errors))

    paths = [args.pages_dir / f"{page:03}.json" for page in range(1, args.pages + 1)]
    report = {
        "schema": "quran-svg-elements/qcf-v1-fetch",
        "schema_version": 1,
        "base_url": BASE_URL,
        "layout_id": 15,
        "pages": args.pages,
        "pages_sha256": tree_sha256(paths),
    }
    write_json(args.pages_dir.parent / "fetch.json", report, pretty=True)
    print(json.dumps(report, indent=2))


def complete_header_line_owners(pages: dict[int, dict]) -> None:
    headings = []
    basmalahs = []
    for page in sorted(pages):
        for line in pages[page]["lines"]:
            if line["type"] == "surah_name":
                headings.append(line)
            elif line["type"] == "basmalah":
                basmalahs.append(line)

    if len(headings) != 114:
        raise ValueError(f"QUL has {len(headings)} surah headings, expected 114")
    for surah, line in enumerate(headings, 1):
        if line["surah"] not in (None, surah):
            raise ValueError(
                f"QUL surah heading order differs at {surah}: {line['surah']}"
            )
        line["surah"] = surah

    expected_basmalahs = [surah for surah in range(2, 115) if surah != 9]
    observed_basmalahs = [line["surah"] for line in basmalahs]
    if observed_basmalahs != expected_basmalahs:
        raise ValueError(
            "QUL basmalah ownership differs: "
            f"{observed_basmalahs} != {expected_basmalahs}"
        )


def load_qcf4_header_assets(path: Path, manifest: dict) -> dict[str, dict[int, dict]]:
    lines = path.read_text().splitlines()
    if not lines or tuple(lines[0].split(",")) != QCF4_COLUMNS:
        raise ValueError("wrong QCF4 layout columns")

    records = []
    for line_number, line in enumerate(lines[1:], 2):
        if not line:
            continue
        values = line.split(",")
        if len(values) != len(QCF4_COLUMNS):
            raise ValueError(f"bad QCF4 row {line_number}")
        try:
            records.append(dict(zip(QCF4_FIELDS, map(int, values), strict=True)))
        except ValueError as error:
            raise ValueError(f"bad QCF4 row {line_number}") from error

    settings = manifest.get("header_assets")
    if not isinstance(settings, dict):
        raise TypeError("missing QPC V4 header asset settings")
    surah_settings = settings.get("surah_name")
    basmalah_settings = settings.get("basmalah")
    if not isinstance(surah_settings, dict) or not isinstance(basmalah_settings, dict):
        raise TypeError("wrong QPC V4 header asset settings")
    heading_codepoints = surah_settings.get("codepoints")
    if (
        surah_settings.get("count") != 114
        or surah_settings.get("source_font") != "QCF_SurahHeader_COLOR-Regular.ttf"
        or surah_settings.get("asset_path") != "surah/{surah:03}.svg"
        or not isinstance(heading_codepoints, list)
        or len(heading_codepoints) != 114
        or len(set(heading_codepoints)) != 114
    ):
        raise ValueError("wrong QPC V4 complete-header contract")
    try:
        parsed_heading_codepoints = [
            int(value.replace("U+", "0x"), 0)
            for value in heading_codepoints
            if isinstance(value, str) and value.startswith("U+")
        ]
    except ValueError as error:
        raise ValueError("bad QPC V4 complete-header codepoint") from error
    if len(parsed_heading_codepoints) != 114:
        raise ValueError("bad QPC V4 complete-header codepoint")
    if (
        basmalah_settings.get("count") != 112
        or basmalah_settings.get("source_font") != "QCF4_Hafs_01_W.ttf"
        or basmalah_settings.get("font_file_id") != 1
        or basmalah_settings.get("font_code") != QCF4_BASMALAH_CODE
        or basmalah_settings.get("codepoint") != "U+F8DD"
        or basmalah_settings.get("asset_path") != "basmalah.svg"
    ):
        raise ValueError("wrong QPC V4 basmalah contract")

    headings = [record for record in records if record["type"] == 5]
    basmalahs = [record for record in records if record["type"] == 4]
    if [record["surah"] for record in headings] != list(range(1, 115)):
        raise ValueError("QCF4 surah-heading ownership differs")
    expected_basmalahs = [surah for surah in range(2, 115) if surah != 9]
    if [record["surah"] for record in basmalahs] != expected_basmalahs:
        raise ValueError("QCF4 basmalah ownership differs")

    heading_assets = {}
    for record in headings:
        surah = record["surah"]
        if (
            record["ayah"] != 0
            or record["font_file_id"] != 0
            or record["font_code"] != surah - 1
        ):
            raise ValueError(f"QCF4 surah-heading contract differs at surah {surah}")
        heading_assets[surah] = {
            "family": "qpc-v4-surah-header",
            "source_font": surah_settings["source_font"],
            "codepoint": heading_codepoints[surah - 1],
            "asset_path": surah_settings["asset_path"].format(surah=surah),
            "qcf4_layout_font_file_id": record["font_file_id"],
            "qcf4_layout_font_code": record["font_code"],
            "qcf4_source_page": record["page"],
            "qcf4_source_line": record["line"],
        }

    basmalah_assets = {}
    for record in basmalahs:
        surah = record["surah"]
        if record["ayah"] != 0 or record["font_code"] != QCF4_BASMALAH_CODE:
            raise ValueError(f"QCF4 basmalah contract differs at surah {surah}")
        basmalah_assets[surah] = {
            "family": "qpc-v4-basmalah",
            "source_font": basmalah_settings["source_font"],
            "font_file_id": basmalah_settings["font_file_id"],
            "source_font_file_id": record["font_file_id"],
            "font_code": record["font_code"],
            "codepoint": basmalah_settings["codepoint"],
            "asset_path": basmalah_settings["asset_path"],
            "qcf4_source_page": record["page"],
            "qcf4_source_line": record["line"],
        }
    return {"surah_name": heading_assets, "basmalah": basmalah_assets}


def attach_header_assets(
    pages: dict[int, dict], assets: dict[str, dict[int, dict]]
) -> None:
    claimed = {"surah_name": set(), "basmalah": set()}
    for page in sorted(pages):
        for line in pages[page]["lines"]:
            kind = line["type"]
            if kind not in claimed:
                continue
            surah = line["surah"]
            asset = assets[kind].get(surah)
            if asset is None or surah in claimed[kind]:
                raise ValueError(f"QPC V4 {kind} ownership differs at surah {surah}")
            line["asset"] = asset
            claimed[kind].add(surah)

    expected = {
        "surah_name": set(range(1, 115)),
        "basmalah": {surah for surah in range(2, 115) if surah != 9},
    }
    if claimed != expected:
        raise ValueError(f"QPC V4 header coverage differs: {claimed} != {expected}")


def load_page_number_source(
    path: Path, pages: dict[int, dict], ayah_order: list[str]
) -> tuple[dict[int, dict], list[list[int]]]:
    source = read_json(path)
    if not isinstance(source, dict):
        raise TypeError("qpc-old page index must be an object")
    starts = source.get("mushaf_pgs")
    raw_stops = source.get("stops")
    if (
        not isinstance(starts, list)
        or len(starts) != 604
        or not all(isinstance(value, int) and value > 0 for value in starts)
        or starts != sorted(set(starts))
    ):
        raise ValueError("qpc-old page starts differ")
    if not isinstance(raw_stops, list) or len(raw_stops) != 604:
        raise ValueError("qpc-old stop rows differ")

    stops = []
    for page, raw in enumerate(raw_stops, 1):
        if not isinstance(raw, str):
            raise TypeError(f"qpc-old page {page} stop positions must be a string")
        values = [int(value) for value in raw.split(",") if value]
        if not values or values != sorted(set(values)):
            raise ValueError(
                f"qpc-old page {page} stop positions must be sorted and unique"
            )
        stops.append(values)

    ordinal = {key: index for index, key in enumerate(ayah_order, 1)}
    result = {}
    for page in range(1, 605):
        page_ayahs = {ayah_key(item["location"]) for item in pages[page]["items"]}
        first = min(page_ayahs, key=numeric_key)
        expected = ordinal[first]
        if starts[page - 1] != expected:
            raise ValueError(
                f"qpc-old page {page} starts at {starts[page - 1]}, "
                f"but V1 starts at {first} ({expected})"
            )
        result[page] = {
            "dataset": "qpc-old",
            "first_ayah_id": expected,
        }
    return result, stops


def verify_ayah_mark_positions(
    pages: dict[int, dict], expected_stops: list[list[int]]
) -> int:
    if len(expected_stops) != len(pages):
        raise ValueError("qpc-old stop rows differ from mapped page count")
    verified = 0
    for page_number in sorted(pages):
        page = pages[page_number]
        word_glyphs = Counter()
        for word in page["words"]:
            word_glyphs[word["ayah_key"]] += len(word["glyphs"])
        for group in page["shared_groups"]:
            word_glyphs[group["ayah_key"]] += len(group["glyphs"])

        marker_glyphs = {}
        for marker in page["ayah_markers"]:
            key = marker["ayah_key"]
            if key in marker_glyphs:
                raise ValueError(f"page {page_number}: duplicate ayah marker {key}")
            marker_glyphs[key] = len(marker["glyphs"])

        ayahs = sorted(word_glyphs, key=numeric_key)
        if not ayahs or set(ayahs) != set(marker_glyphs):
            raise ValueError(f"page {page_number}: qpc-old ayah coverage differs")

        body_glyphs = 0
        marker_count = 0
        positions = []
        for key in ayahs:
            body_glyphs += word_glyphs[key]
            marker_count += marker_glyphs[key]
            positions.append(body_glyphs + marker_count - 1)
        expected = expected_stops[page_number - 1]
        if positions != expected:
            raise ValueError(
                f"page {page_number}: ayah marker positions differ: "
                f"{positions} != {expected}"
            )
        verified += 1
    return verified


def line_content(
    words: list[dict], shared_groups: list[dict], markers: list[dict]
) -> list[dict]:
    entries = [
        (
            numeric_key(word["word_key"]),
            {"kind": "word", "word_key": word["word_key"]},
        )
        for word in words
    ]
    entries.extend(
        (
            numeric_key(group["canonical_word_keys"][0]),
            {
                "kind": "shared_group",
                "id": group["id"],
                "canonical_word_keys": group["canonical_word_keys"],
            },
        )
        for group in shared_groups
    )
    entries.extend(
        (
            numeric_key(marker["ayah_key"]) + (1_000_000,),
            {"kind": "ayah_mark", "ayah_key": marker["ayah_key"]},
        )
        for marker in markers
    )
    entries.sort(key=lambda item: item[0])
    return [entry for _, entry in entries]


def load_pages(pages_dir: Path, count: int) -> dict[int, dict]:
    pages = {}
    for page in range(1, count + 1):
        path = pages_dir / f"{page:03}.json"
        if not path.exists():
            raise ValueError(f"missing QUL page {page}: {path}")
        data = read_json(path)
        validate_cached_page(data, page)
        pages[page] = data
    complete_header_line_owners(pages)
    return pages


def load_canonical(index_dir: Path) -> tuple[dict[str, list[dict]], list[str]]:
    canonical: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    files = sorted(index_dir.glob("[0-9][0-9][0-9].json"))
    if len(files) != 604:
        raise ValueError(f"canonical index has {len(files)} pages, expected 604")
    for path in files:
        data = read_json(path)
        for source in data["words"]:
            key = source["word_key"]
            if key in seen:
                raise ValueError(f"duplicate canonical word {key}")
            seen.add(key)
            record = {"word_key": key, "ayah_key": source["ayah_key"]}
            for field in TEXT_FIELDS:
                record[field] = source.get(field, "")
            canonical[record["ayah_key"]].append(record)
    for words in canonical.values():
        words.sort(key=lambda word: numeric_key(word["word_key"]))
    ayahs = sorted(canonical, key=numeric_key)
    return dict(canonical), ayahs


def load_font_text(path: Path, ayahs: list[str]) -> dict[str, dict]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line:
            continue
        try:
            page, text = line.split(",", 1)
            rows.append({"page": int(page), "text": text})
        except ValueError as error:
            raise ValueError(f"bad mushaf.txt row {line_number}") from error
    if len(rows) != len(ayahs):
        raise ValueError(f"mushaf.txt has {len(rows)} ayahs, expected {len(ayahs)}")
    return dict(zip(ayahs, rows, strict=True))


def normalize_box(source_box: list[int]) -> list[int]:
    return [
        min(source_box[0], source_box[2]),
        min(source_box[1], source_box[3]),
        max(source_box[0], source_box[2]),
        max(source_box[1], source_box[3]),
    ]


def load_boxes(path: Path) -> dict[str, list[dict]]:
    database = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    database.row_factory = sqlite3.Row
    boxes: dict[str, list[dict]] = defaultdict(list)
    query = """
        SELECT glyph_id, page_number, line_number, sura_number, ayah_number,
               position, min_x, max_x, min_y, max_y
        FROM glyphs
        ORDER BY sura_number, ayah_number, position
    """
    for row in database.execute(query):
        key = f"{row['sura_number']}:{row['ayah_number']}"
        source_box = [row["min_x"], row["min_y"], row["max_x"], row["max_y"]]
        box = normalize_box(source_box)
        if not (box[0] <= box[2] and box[1] < box[3]):
            raise ValueError(
                f"invalid ayahinfo box at {key}:{row['position']}: {source_box}"
            )
        boxes[key].append(
            {
                "glyph_id": row["glyph_id"],
                "page": row["page_number"],
                "line": row["line_number"],
                "position": row["position"],
                "source_box": source_box,
                "box": box,
            }
        )
    database.close()
    for key, rows in boxes.items():
        positions = [row["position"] for row in rows]
        if positions != list(range(1, len(rows) + 1)):
            raise ValueError(f"ayahinfo positions are not contiguous for {key}")
    return dict(boxes)


def collect_items(pages: dict[int, dict]) -> dict[str, list[dict]]:
    items_by_ayah: dict[str, list[dict]] = defaultdict(list)
    for page in pages.values():
        for item in page["items"]:
            items_by_ayah[ayah_key(item["location"])].append(item)
    return dict(items_by_ayah)


def verify_placement(key: str, item: dict, row: dict) -> None:
    if row["page"] != item["page"] or row["line"] != item["line"]:
        raise ValueError(
            f"QUL/ayahinfo placement differs at {key}:{row['position']}: "
            f"QUL {item['page']}:{item['line']}, "
            f"ayahinfo {row['page']}:{row['line']}"
        )


def glyph_record(
    char: str,
    row: dict,
    qul_positions: list[int],
    font_position: int,
) -> dict:
    return {
        "text": char,
        "codepoint": f"U+{ord(char):04X}",
        "qul_ayah_positions": qul_positions,
        "font_ayah_position": font_position,
        "ayahinfo_position": row["position"],
        "glyph_id": row["glyph_id"],
        "source_box": row["source_box"],
        "box": row["box"],
    }


def align_standard_ayah(key: str, items: list[dict], rows: list[dict]) -> None:
    flattened = [(item, char) for item in items for char in item["text"]]
    if len(flattened) != len(rows):
        raise ValueError(
            f"QUL/ayahinfo glyph count differs at {key}: {len(flattened)} != {len(rows)}"
        )
    for position, ((item, char), row) in enumerate(
        zip(flattened, rows, strict=True), 1
    ):
        if row["position"] != position:
            raise ValueError(f"ayahinfo position drift at {key}:{position}")
        verify_placement(key, item, row)
        item["glyphs"].append(glyph_record(char, row, [position], position))


def align_font_stream_ayah(
    key: str,
    items: list[dict],
    rows: list[dict],
    actual_text: str,
    plan: dict | None,
) -> dict | None:
    if len(actual_text) != len(rows):
        raise ValueError(
            f"font/ayahinfo glyph count differs at {key}: {len(actual_text)} != {len(rows)}"
        )
    for item in items:
        item["qul_text"] = item["text"]

    group_items = []
    group_start = None
    if plan:
        positions = plan["source_word_positions"]
        group_items = [
            item
            for item in items
            if item["kind"] == "word" and item["source_position"] in positions
        ]
        if [item["source_position"] for item in group_items] != positions:
            raise ValueError(f"shared-glyph source positions changed at {key}")
        if plan["glyph_count"] != 1:
            raise ValueError(f"unsupported shared-glyph count at {key}")
        indices = [items.index(item) for item in group_items]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError(f"shared-glyph source items are not consecutive at {key}")
        group_start = indices[0]
        if len({(item["page"], item["line"]) for item in group_items}) != 1:
            raise ValueError(f"shared-glyph words cross a page or line at {key}")

    qul_cursor = 0
    font_cursor = 0
    deferred = None
    index = 0
    while index < len(items):
        item = items[index]
        if plan and index == group_start:
            qul_count = sum(len(member["qul_text"]) for member in group_items)
            char = actual_text[font_cursor]
            row = rows[font_cursor]
            verify_placement(key, group_items[0], row)
            glyph = glyph_record(
                char,
                row,
                list(range(qul_cursor + 1, qul_cursor + qul_count + 1)),
                font_cursor + 1,
            )
            deferred = {
                "id": plan["id"],
                "reason": plan["reason"],
                "ayah_key": key,
                "canonical_word_keys": plan["canonical_word_keys"],
                "page": row["page"],
                "line": row["line"],
                "source_locations": [member["location"] for member in group_items],
                "source_word_ids": [member["source_word_id"] for member in group_items],
                "source_record_ids": [
                    member["source_record_id"] for member in group_items
                ],
                "source_positions": [
                    member["source_position"] for member in group_items
                ],
                "qul_text": "".join(member["qul_text"] for member in group_items),
                "source_text": char,
                "glyphs": [glyph],
                "box": row["box"],
            }
            for member in group_items:
                member["shared_group"] = plan["id"]
                member["glyphs"] = []
            qul_cursor += qul_count
            font_cursor += 1
            index += len(group_items)
            continue

        count = len(item["qul_text"])
        segment = actual_text[font_cursor : font_cursor + count]
        selected_rows = rows[font_cursor : font_cursor + count]
        if len(segment) != count or len(selected_rows) != count:
            raise ValueError(f"font stream ended inside {item['location']}")
        item["text"] = segment
        item["glyphs"] = []
        for offset, (char, row) in enumerate(zip(segment, selected_rows, strict=True)):
            verify_placement(key, item, row)
            item["glyphs"].append(
                glyph_record(
                    char,
                    row,
                    [qul_cursor + offset + 1],
                    font_cursor + offset + 1,
                )
            )
        qul_cursor += count
        font_cursor += count
        index += 1

    qul_count = sum(len(item["qul_text"]) for item in items)
    if qul_cursor != qul_count or font_cursor != len(actual_text):
        raise ValueError(
            f"font-stream alignment did not consume {key}: "
            f"QUL {qul_cursor}/{qul_count}, font {font_cursor}/{len(actual_text)}"
        )
    if bool(plan) != bool(deferred):
        raise ValueError(f"shared-glyph plan did not resolve at {key}")
    return deferred


def attach_boxes(
    pages: dict[int, dict],
    boxes: dict[str, list[dict]],
    font_text: dict[str, dict],
    font_stream_ayahs: list[str],
    shared_plans: list[dict],
) -> tuple[dict[str, list[dict]], list[dict]]:
    items_by_ayah = collect_items(pages)
    for key, items in items_by_ayah.items():
        for item in items:
            item["ayah_key"] = key
            item["glyphs"] = []

    if set(items_by_ayah) != set(boxes):
        missing_html = sorted(set(boxes) - set(items_by_ayah), key=numeric_key)
        missing_boxes = sorted(set(items_by_ayah) - set(boxes), key=numeric_key)
        raise ValueError(
            f"QUL/ayahinfo ayahs differ: missing HTML={missing_html[:5]}, "
            f"missing boxes={missing_boxes[:5]}"
        )

    stream_keys = set(font_stream_ayahs)
    plans = {plan["ayah"]: plan for plan in shared_plans}
    if not set(plans).issubset(stream_keys):
        raise ValueError("every shared-glyph ayah must use the pinned font stream")

    deferred = []
    for key, items in items_by_ayah.items():
        if key in stream_keys:
            group = align_font_stream_ayah(
                key,
                items,
                boxes[key],
                font_text[key]["text"],
                plans.get(key),
            )
            if group:
                deferred.append(group)
        else:
            align_standard_ayah(key, items, boxes[key])
    if {group["ayah_key"] for group in deferred} != set(plans):
        raise ValueError("shared-glyph plan coverage changed")
    return dict(items_by_ayah), deferred


def observed_source_differences(
    font_text: dict[str, dict], items_by_ayah: dict[str, list[dict]]
) -> list[dict]:
    differences = []
    for key in sorted(font_text, key=numeric_key):
        source = font_text[key]
        items = items_by_ayah[key]
        pages = sorted({item["page"] for item in items})
        if len(pages) != 1:
            raise ValueError(f"V1 ayah crosses pages: {key} -> {pages}")
        layout_text = "".join(item["text"] for item in items)
        if source["page"] == pages[0] and source["text"] == layout_text:
            continue
        differences.append(
            {
                "ayah": key,
                "font_page": source["page"],
                "layout_page": pages[0],
                "font_glyph_count": len(source["text"]),
                "layout_glyph_count": len(layout_text),
                "font_codepoints": codepoints(source["text"]),
                "layout_codepoints": codepoints(layout_text),
            }
        )
    return differences


def difference_signature(record: dict) -> tuple:
    return (
        record["ayah"],
        record["font_page"],
        record["layout_page"],
        record["font_glyph_count"],
        record["layout_glyph_count"],
        tuple(record["font_codepoints"]),
        tuple(record["layout_codepoints"]),
    )


def verify_source_differences(observed: list[dict], manifest: dict) -> None:
    accepted = manifest["accepted_source_differences"]
    observed_signatures = {difference_signature(record) for record in observed}
    accepted_signatures = {difference_signature(record) for record in accepted}
    if observed_signatures != accepted_signatures:
        raise ValueError(
            "source differences changed:\n"
            + json.dumps(
                {"observed": observed, "accepted": accepted},
                ensure_ascii=False,
                indent=2,
            )
        )


def verify_inputs(args: argparse.Namespace, manifest: dict) -> None:
    page_files = sorted(args.pages_dir.glob("[0-9][0-9][0-9].json"))
    canonical_files = sorted(args.canonical_index.glob("[0-9][0-9][0-9].json"))
    font_files = sorted(args.fonts_dir.glob("QCF_*.TTF"))
    checks = {
        "qul_pages_sha256": tree_sha256(page_files),
        "mushaf_text_sha256": sha256(args.font_text),
        "ayahinfo_sha256": sha256(args.ayahinfo_db),
        "canonical_index_sha256": tree_sha256(canonical_files),
        "seg_plan_sha256": sha256(args.seg_plan),
        "font_tree_sha256": tree_sha256(font_files),
        "qcf4_layout_sha256": sha256(args.qcf4_data),
        "qpc4_surah_header_font_sha256": sha256(args.qpc4_surah_header_font),
        "qcf4_basmalah_font_sha256": sha256(args.qcf4_basmalah_font),
        "page_number_source_sha256": sha256(args.page_number_source),
    }
    expected = manifest["inputs"]
    wrong = {
        name: {"expected": expected.get(name), "actual": actual}
        for name, actual in checks.items()
        if expected.get(name) != actual
    }
    if wrong:
        raise ValueError("source digest mismatch:\n" + json.dumps(wrong, indent=2))


def group(
    items: list[dict], glyphs: list[dict] | None = None, source_part: int | None = None
) -> dict:
    pages = {item["page"] for item in items}
    lines = {item["line"] for item in items}
    if len(pages) != 1 or len(lines) != 1:
        raise ValueError(f"one canonical word crosses source pages or lines: {items}")
    result = {
        "page": next(iter(pages)),
        "line": next(iter(lines)),
        "items": items,
        "glyphs": glyphs
        if glyphs is not None
        else [glyph for item in items for glyph in item["glyphs"]],
    }
    if source_part is not None:
        result["source_glyph_part"] = source_part
    return result


def reconcile_words(
    key: str,
    source_words: list[dict],
    canonical_words: list[dict],
    seg_plan: dict,
) -> tuple[list[dict], dict | None]:
    groups = [group([item]) for item in source_words]
    adjustment = None
    if len(groups) != len(canonical_words):
        split = seg_plan.get("splits", {}).get(key)
        fuse = seg_plan.get("fuses", {}).get(key)
        if split and len(canonical_words) == len(groups) + 1:
            position = int(split[0])
            target = source_words[position - 1]
            if len(target["glyphs"]) != 2:
                raise ValueError(
                    f"cannot split {target['location']}: expected two glyphs, got {len(target['glyphs'])}"
                )
            groups[position - 1 : position] = [
                group([target], [glyph], source_part)
                for source_part, glyph in enumerate(target["glyphs"])
            ]
            adjustment = {
                "ayah": key,
                "kind": "split",
                "source_positions": [position],
                "canonical_positions": [position, position + 1],
            }
        elif fuse and len(canonical_words) == len(groups) - int(fuse[1]) + 1:
            position, count = (int(value) for value in fuse)
            selected = source_words[position - 1 : position - 1 + count]
            groups[position - 1 : position - 1 + count] = [group(selected)]
            adjustment = {
                "ayah": key,
                "kind": "fuse",
                "source_positions": list(range(position, position + count)),
                "canonical_positions": [position],
            }
        else:
            raise ValueError(
                f"unresolved word boundaries at {key}: "
                f"QUL={len(source_words)}, canonical={len(canonical_words)}"
            )

    if len(groups) != len(canonical_words):
        raise ValueError(f"boundary adjustment did not reconcile {key}")

    mapped = []
    for source, canonical in zip(groups, canonical_words, strict=True):
        items = source["items"]
        glyphs = source["glyphs"]
        record = {
            "word_key": canonical["word_key"],
            "ayah_key": canonical["ayah_key"],
            "page": source["page"],
            "line": source["line"],
            "source_locations": [item["location"] for item in items],
            "source_word_ids": [item["source_word_id"] for item in items],
            "source_record_ids": [item["source_record_id"] for item in items],
            "source_positions": [item["source_position"] for item in items],
            "source_text": "".join(glyph["text"] for glyph in glyphs),
            "text": {field: canonical[field] for field in TEXT_FIELDS},
            "glyphs": glyphs,
            "box": union_box(glyphs),
        }
        if "source_glyph_part" in source:
            record["source_glyph_part"] = source["source_glyph_part"]
        mapped.append(record)
    return mapped, adjustment


def union_box(glyphs: list[dict]) -> list[int] | None:
    boxes = [glyph["box"] for glyph in glyphs if glyph.get("box") is not None]
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def public_line(line: dict) -> dict:
    result = {
        "line": line["line"],
        "type": line["type"],
        "is_centered": line["is_centered"],
        "surah": line["surah"],
        "word_keys": [],
        "shared_word_keys": [],
        "ayah_keys": [],
        "content": [],
    }
    if "asset" in line:
        result["asset"] = line["asset"]
    return result


def build_map(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    verify_inputs(args, manifest)
    canonical, ayah_order = load_canonical(args.canonical_index)
    canonical_by_key = {
        word["word_key"]: word for words in canonical.values() for word in words
    }
    font_text = load_font_text(args.font_text, ayah_order)
    boxes = load_boxes(args.ayahinfo_db)
    pages = load_pages(args.pages_dir, manifest["expected"]["pages"])
    attach_header_assets(pages, load_qcf4_header_assets(args.qcf4_data, manifest))
    page_number_source, expected_ayah_mark_positions = load_page_number_source(
        args.page_number_source, pages, ayah_order
    )

    differences = observed_source_differences(font_text, collect_items(pages))
    verify_source_differences(differences, manifest)
    items_by_ayah, shared_groups = attach_boxes(
        pages,
        boxes,
        font_text,
        manifest.get("font_stream_ayahs", []),
        manifest.get("shared_glyph_groups", []),
    )
    shared_by_ayah = {group["ayah_key"]: group for group in shared_groups}
    seg_plan = read_json(args.seg_plan)

    output_pages = {
        page: {
            "schema": "quran-svg-elements/qcf-v1-map-page",
            "schema_version": 3,
            "edition": manifest["edition"],
            "page": page,
            "page_number_source": page_number_source[page],
            "coordinate_space": manifest["coordinate_space"],
            "lines": [public_line(line) for line in pages[page]["lines"]],
            "words": [],
            "ayah_markers": [],
            "shared_groups": [],
        }
        for page in pages
    }
    line_lookup = {
        (page, line["line"]): line
        for page, output in output_pages.items()
        for line in output["lines"]
    }

    adjustments = []
    unknown_types = Counter()
    mapped_keys = set()
    shared_keys = set()
    font_glyphs = set()
    boxed_glyphs = set()
    markers = 0

    def claim_glyph(key: str, glyph: dict) -> None:
        font_identity = (key, glyph["font_ayah_position"])
        box_identity = (key, glyph["ayahinfo_position"])
        if font_identity in font_glyphs:
            raise ValueError(f"font glyph owned twice: {font_identity}")
        if box_identity in boxed_glyphs:
            raise ValueError(f"ayahinfo box owned twice: {box_identity}")
        font_glyphs.add(font_identity)
        boxed_glyphs.add(box_identity)

    for key in ayah_order:
        items = items_by_ayah[key]
        shared = shared_by_ayah.get(key)
        shared_word_keys = set(shared["canonical_word_keys"]) if shared else set()
        source_words = [
            item
            for item in items
            if item["kind"] == "word" and "shared_group" not in item
        ]
        canonical_words = [
            word for word in canonical[key] if word["word_key"] not in shared_word_keys
        ]
        source_markers = [item for item in items if item["kind"] == "end"]
        unknown_types.update(
            item["kind"] for item in items if item["kind"] not in {"word", "end"}
        )

        mapped, adjustment = reconcile_words(
            key, source_words, canonical_words, seg_plan
        )
        if adjustment:
            adjustments.append(adjustment)
        for word in mapped:
            if word["word_key"] in mapped_keys or word["word_key"] in shared_keys:
                raise ValueError(f"duplicate mapped word {word['word_key']}")
            mapped_keys.add(word["word_key"])
            output_pages[word["page"]]["words"].append(word)
            line = line_lookup[(word["page"], word["line"])]
            line["word_keys"].append(word["word_key"])
            if key not in line["ayah_keys"]:
                line["ayah_keys"].append(key)
            for glyph in word["glyphs"]:
                claim_glyph(key, glyph)

        if shared:
            shared["canonical_words"] = [
                {
                    "word_key": word_key,
                    "text": {
                        field: canonical_by_key[word_key][field]
                        for field in TEXT_FIELDS
                    },
                }
                for word_key in shared["canonical_word_keys"]
            ]
            output_pages[shared["page"]]["shared_groups"].append(shared)
            line = line_lookup[(shared["page"], shared["line"])]
            line["shared_word_keys"].extend(shared["canonical_word_keys"])
            if key not in line["ayah_keys"]:
                line["ayah_keys"].append(key)
            for word_key in shared["canonical_word_keys"]:
                if word_key in mapped_keys or word_key in shared_keys:
                    raise ValueError(f"shared word owned twice: {word_key}")
                shared_keys.add(word_key)
            for glyph in shared["glyphs"]:
                claim_glyph(key, glyph)

        if len(source_markers) != 1:
            raise ValueError(
                f"expected one ayah marker at {key}, got {len(source_markers)}"
            )
        marker = source_markers[0]
        marker_record = {
            "ayah_key": key,
            "page": marker["page"],
            "line": marker["line"],
            "source_location": marker["location"],
            "source_word_id": marker["source_word_id"],
            "source_record_id": marker["source_record_id"],
            "source_text": marker["text"],
            "glyphs": marker["glyphs"],
            "box": union_box(marker["glyphs"]),
        }
        output_pages[marker["page"]]["ayah_markers"].append(marker_record)
        line = line_lookup[(marker["page"], marker["line"])]
        if key not in line["ayah_keys"]:
            line["ayah_keys"].append(key)
        for glyph in marker["glyphs"]:
            claim_glyph(key, glyph)
        markers += 1

    verified_ayah_mark_positions = verify_ayah_mark_positions(
        output_pages, expected_ayah_mark_positions
    )

    for output in output_pages.values():
        words_by_line: dict[int, list[dict]] = defaultdict(list)
        shared_by_line: dict[int, list[dict]] = defaultdict(list)
        markers_by_line: dict[int, list[dict]] = defaultdict(list)
        for word in output["words"]:
            words_by_line[word["line"]].append(word)
        for group in output["shared_groups"]:
            shared_by_line[group["line"]].append(group)
        for marker in output["ayah_markers"]:
            markers_by_line[marker["line"]].append(marker)
        for line in output["lines"]:
            line["content"] = line_content(
                words_by_line[line["line"]],
                shared_by_line[line["line"]],
                markers_by_line[line["line"]],
            )

    canonical_keys = set(canonical_by_key)
    covered_keys = mapped_keys | shared_keys
    if covered_keys != canonical_keys:
        missing = sorted(canonical_keys - covered_keys, key=numeric_key)
        extra = sorted(covered_keys - canonical_keys, key=numeric_key)
        raise ValueError(
            f"canonical word coverage differs: missing={missing[:5]}, extra={extra[:5]}"
        )

    source_glyph_count = sum(len(rows) for rows in boxes.values())
    if (
        len(font_glyphs) != source_glyph_count
        or len(boxed_glyphs) != source_glyph_count
    ):
        raise ValueError(
            "source glyph coverage differs: "
            f"font={len(font_glyphs)}, boxes={len(boxed_glyphs)}, expected={source_glyph_count}"
        )

    actual_adjustments = {(item["ayah"], item["kind"]) for item in adjustments}
    expected_adjustments = {
        (item["ayah"], item["kind"])
        for item in manifest["expected"]["boundary_adjustments"]
    }
    if actual_adjustments != expected_adjustments:
        raise ValueError(
            f"boundary adjustments changed: {sorted(actual_adjustments)} != "
            f"{sorted(expected_adjustments)}"
        )
    if unknown_types:
        raise ValueError(f"unknown QUL char types: {dict(unknown_types)}")

    qul_layout_glyphs = sum(
        len(item.get("qul_text", item["text"]))
        for items in items_by_ayah.values()
        for item in items
    )
    counts = {
        "pages": len(output_pages),
        "lines": sum(len(page["lines"]) for page in output_pages.values()),
        "ayahs": len(items_by_ayah),
        "canonical_words": len(covered_keys),
        "direct_words": len(mapped_keys),
        "shared_canonical_words": len(shared_keys),
        "shared_glyph_groups": len(shared_groups),
        "ayah_markers": markers,
        "page_numbers": len(page_number_source),
        "header_assets": sum(
            "asset" in line for page in output_pages.values() for line in page["lines"]
        ),
        "surah_headings": sum(
            line["type"] == "surah_name"
            for page in output_pages.values()
            for line in page["lines"]
        ),
        "basmalahs": sum(
            line["type"] == "basmalah"
            for page in output_pages.values()
            for line in page["lines"]
        ),
        "qul_layout_glyphs": qul_layout_glyphs,
        "font_glyphs": len(font_glyphs),
        "boxed_glyphs": len(boxed_glyphs),
        "reversed_source_boxes": sum(
            row["source_box"] != row["box"] for rows in boxes.values() for row in rows
        ),
        "zero_width_boxes": sum(
            row["box"][0] == row["box"][2] for rows in boxes.values() for row in rows
        ),
        "zero_height_boxes": sum(
            row["box"][1] == row["box"][3] for rows in boxes.values() for row in rows
        ),
        "multi_glyph_words": sum(
            len(word["glyphs"]) > 1
            for page in output_pages.values()
            for word in page["words"]
        ),
    }
    wrong_counts = {
        name: {"expected": value, "actual": counts.get(name)}
        for name, value in manifest["expected"].items()
        if isinstance(value, int) and counts.get(name) != value
    }
    if wrong_counts:
        raise ValueError("mapped counts differ:\n" + json.dumps(wrong_counts, indent=2))

    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.out_dir}")
    pages_dir = args.out_dir / "pages"
    page_digest = hashlib.sha256()
    for page in range(1, manifest["expected"]["pages"] + 1):
        destination = pages_dir / f"{page:03}.json"
        data = write_json(destination, output_pages[page])
        page_digest.update(destination.name.encode())
        page_digest.update(b"\0")
        page_digest.update(data)

    shared_summary = [
        {
            "id": group["id"],
            "ayah_key": group["ayah_key"],
            "canonical_word_keys": group["canonical_word_keys"],
            "page": group["page"],
            "line": group["line"],
            "source_text": group["source_text"],
        }
        for group in shared_groups
    ]
    summary = {
        "schema": "quran-svg-elements/qcf-v1-map",
        "schema_version": 3,
        "edition": manifest["edition"],
        "source_manifest_sha256": sha256(args.manifest),
        "input_digests": manifest["inputs"],
        "sources": manifest["sources"],
        "counts": counts,
        "page_files_sha256": page_digest.hexdigest(),
        "accepted_source_differences": differences,
        "boundary_adjustments": adjustments,
        "shared_glyph_groups": shared_summary,
        "page_index": {
            "pages": len(page_number_source),
            "page_starts": len(page_number_source),
            "ayah_mark_positions": verified_ayah_mark_positions,
            "source_sha256": sha256(args.page_number_source),
        },
        "deferred": manifest["deferred"],
    }
    write_json(args.out_dir / "summary.json", summary, pretty=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subcommands = command.add_subparsers(dest="command", required=True)

    fetch = subcommands.add_parser("fetch", help="cache normalized QUL layout records")
    fetch.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES_DIR)
    fetch.add_argument("--pages", type=int, default=604)
    fetch.add_argument("--workers", type=int, default=4)
    fetch.add_argument("--retries", type=int, default=3)
    fetch.add_argument("--refresh", action="store_true")
    fetch.set_defaults(run=fetch_pages)

    build = subcommands.add_parser(
        "build", help="join QUL ownership, glyph boxes and canonical words"
    )
    build.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES_DIR)
    build.add_argument("--canonical-index", type=Path, required=True)
    build.add_argument("--ayahinfo-db", type=Path, required=True)
    build.add_argument("--font-text", type=Path, required=True)
    build.add_argument("--fonts-dir", type=Path, required=True)
    build.add_argument("--qcf4-data", type=Path, required=True)
    build.add_argument("--qpc4-surah-header-font", type=Path, required=True)
    build.add_argument("--qcf4-basmalah-font", type=Path, required=True)
    build.add_argument("--page-number-source", type=Path, required=True)
    build.add_argument("--seg-plan", type=Path, default=DEFAULT_SEG_PLAN)
    build.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    build.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    build.set_defaults(run=build_map)
    return command


def main() -> None:
    args = parser().parse_args()
    for name in (
        "pages_dir",
        "canonical_index",
        "ayahinfo_db",
        "font_text",
        "fonts_dir",
        "qcf4_data",
        "qpc4_surah_header_font",
        "qcf4_basmalah_font",
        "page_number_source",
        "seg_plan",
        "manifest",
        "out_dir",
    ):
        value = getattr(args, name, None)
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    args.run(args)


if __name__ == "__main__":
    main()
