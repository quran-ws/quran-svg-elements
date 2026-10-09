#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools==4.66.1",
# ]
# ///
"""Build the pinned QCF V1 waqf source-glyph ownership ledger.

The canonical text identifies the waqf sign and the mapped source run identifies its final
source glyph. Source glyphs already owned by the pinned division/sajdah ledger do not count as
word-body glyphs. The final glyph is a separate waqf mark only when more than one non-semantic
glyph remains; otherwise body and waqf remain fused. The optional analysis records the source
evidence behind every decision.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_qcf_v1_svg import PageFont, parse_codepoint
from qcf_v1_division_sajdah import DivisionSajdahSemantics

MARK_BY_CHAR = {
    "ۖ": "waqf_jaiz_wasl_awla",
    "ۗ": "waqf_jaiz_waqf_awla",
    "ۘ": "waqf_lazim",
    "ۚ": "waqf_jaiz_mustawi_al_tarafayn",
    "ۛ": "waqf_al_muanaqah",
}


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def json_bytes(value: object, *, sort_keys: bool = False) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"
    ).encode()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def named_digest(paths: list[Path]) -> str:
    value = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        value.update(path.name.encode())
        value.update(b"\0")
        value.update(path.read_bytes())
    return value.hexdigest()


def records_digest(records: list[dict]) -> str:
    value = hashlib.sha256()
    for record in records:
        value.update((json.dumps(record, sort_keys=True) + "\n").encode())
    return value.hexdigest()


def box_size(box: list[int] | None) -> tuple[int | None, int | None]:
    if box is None:
        return None, None
    return box[2] - box[0], box[3] - box[1]


def preceding_maxima(glyphs: list[dict]) -> tuple[int | None, int | None]:
    sizes = [box_size(glyph.get("box")) for glyph in glyphs]
    widths = [width for width, _ in sizes if width is not None]
    heights = [height for _, height in sizes if height is not None]
    return (max(heights) if heights else None, max(widths) if widths else None)


def page_records(
    page: dict,
    font: PageFont,
    semantic_source_indices: dict[str, set[int]],
) -> tuple[list[dict], int, int, int, int, int]:
    records = []
    words = page.get("words")
    if not isinstance(words, list):
        raise TypeError(f"page {page.get('page')}: words must be a list")
    source_glyphs = 0
    for word in words:
        glyphs = word.get("glyphs")
        text = word.get("text", {}).get("rasm_uthmani")
        if not isinstance(glyphs, list) or not glyphs or not isinstance(text, str):
            raise ValueError(
                f"page {page['page']}: invalid word {word.get('word_key')}"
            )
        source_glyphs += len(glyphs)
        signs = [
            (index, char) for index, char in enumerate(text) if char in MARK_BY_CHAR
        ]
        if not signs:
            continue
        if len(signs) != 1 or signs[0][0] != len(text) - 1:
            raise ValueError(
                f"page {page['page']}: waqf text sign is not unique and final for "
                f"{word.get('word_key')}"
            )
        _, sign = signs[0]
        glyph_index = len(glyphs) - 1
        semantic_indices = semantic_source_indices.get(word["word_key"], set())
        if (
            not all(
                type(index) is int and 0 <= index < len(glyphs)
                for index in semantic_indices
            )
            or glyph_index in semantic_indices
        ):
            raise ValueError(
                f"page {page['page']}: semantic and waqf source ownership conflicts for "
                f"{word['word_key']}"
            )
        glyph = glyphs[glyph_index]
        codepoint = glyph.get("codepoint")
        path, _ = font.outline(parse_codepoint(codepoint))
        if not path:
            raise ValueError(
                f"page {page['page']}: empty waqf candidate for {word.get('word_key')}"
            )
        box = glyph.get("box")
        if box is not None and (
            not isinstance(box, list)
            or len(box) != 4
            or not all(isinstance(value, int) for value in box)
        ):
            raise TypeError(
                f"page {page['page']}: invalid waqf box for {word.get('word_key')}"
            )
        width, height = box_size(box)
        preceding_height, preceding_width = preceding_maxima(glyphs[:glyph_index])
        record = {
            "page": page["page"],
            "word_key": word["word_key"],
            "text_codepoint": f"U+{ord(sign):04X}",
            "mark": MARK_BY_CHAR[sign],
            "source_codepoint": codepoint,
            "glyph_id": glyph.get("glyph_id"),
            "glyph_index": glyph_index,
            "glyph_count": len(glyphs),
            "box": box,
            "box_width": width,
            "box_height": height,
            "outline_sha256": hashlib.sha256(path.encode()).hexdigest(),
            "preceding_box_max_height": preceding_height,
            "preceding_box_max_width": preceding_width,
        }
        if semantic_indices:
            record["semantic_glyph_indices"] = sorted(semantic_indices)
        records.append(record)
    shared_groups = page.get("shared_groups", [])
    if not isinstance(shared_groups, list):
        raise TypeError(f"page {page.get('page')}: shared_groups must be a list")
    shared_words = 0
    shared_glyphs = 0
    for group in shared_groups:
        canonical_words = group.get("canonical_words")
        glyphs = group.get("glyphs")
        if not isinstance(canonical_words, list) or not isinstance(glyphs, list):
            raise TypeError(f"page {page.get('page')}: invalid shared group")
        for word in canonical_words:
            text = word.get("text", {}).get("rasm_uthmani")
            if not isinstance(text, str):
                raise TypeError(f"page {page.get('page')}: invalid shared word text")
            if any(char in MARK_BY_CHAR for char in text):
                raise ValueError(
                    f"page {page['page']}: shared word {word.get('word_key')} has waqf text"
                )
        shared_words += len(canonical_words)
        shared_glyphs += len(glyphs)
    return (
        records,
        len(words),
        source_glyphs,
        len(shared_groups),
        shared_words,
        shared_glyphs,
    )


def distributions(records: list[dict], field: str) -> list[dict]:
    counts = Counter((record["mark"], record[field]) for record in records)
    return [
        {"mark": mark, field: value, "words": words}
        for (mark, value), words in sorted(counts.items())
    ]


def smallness(records: list[dict], text_counts: Counter) -> dict:
    by_mark = defaultdict(list)
    for record in records:
        by_mark[record["mark"]].append(record)
    result = {}
    for mark, count in text_counts.most_common():
        rows = by_mark[mark]
        widths = [row["box_width"] for row in rows if row["box_width"] is not None]
        heights = [row["box_height"] for row in rows if row["box_height"] is not None]
        signatures = Counter(row["outline_sha256"] for row in rows)
        result[mark] = {
            "count": count,
            "width": {"min": min(widths), "max": max(widths)},
            "height": {"min": min(heights), "max": max(heights)},
            "candidate_is_shorter_than_every_preceding_glyph": sum(
                row["box_height"] is not None
                and row["preceding_box_max_height"] is not None
                and row["box_height"] < row["preceding_box_max_height"]
                for row in rows
            ),
            "exact_outline_signatures": len(signatures),
            "top_signatures": signatures.most_common(12),
        }
    return result


def shared_signatures(records: list[dict]) -> dict[str, list[str]]:
    marks = defaultdict(set)
    for record in records:
        marks[record["outline_sha256"]].add(record["mark"])
    return {
        signature: sorted(values)
        for signature, values in sorted(marks.items())
        if len(values) > 1
    }


def analysis_report(
    args: argparse.Namespace,
    records: list[dict],
    direct_words: int,
    direct_source_glyphs: int,
    shared_groups: int,
    shared_canonical_words: int,
    shared_source_glyphs: int,
) -> dict:
    text_counts = Counter(record["mark"] for record in records)
    return {
        "schema": "quran-svg-elements/qcf-v1-waqf-source-analysis",
        "schema_version": 2,
        "map": str(args.map_dir / "pages"),
        "fonts": str(args.fonts_dir),
        "division_sajdah_source": str(args.division_sajdah_source),
        "counts": {
            "pages": 604,
            "direct_words": direct_words,
            "direct_source_glyphs": direct_source_glyphs,
            "shared_groups": shared_groups,
            "shared_canonical_words": shared_canonical_words,
            "shared_source_glyphs": shared_source_glyphs,
            "waqf_text_signs": len(records),
            "candidate_source_glyphs": len(records),
            "candidate_is_final_source_glyph": len(records),
        },
        "text_counts": dict(sorted(text_counts.items())),
        "glyph_count_distribution": distributions(records, "glyph_count"),
        "glyph_index_distribution": distributions(records, "glyph_index"),
        "smallness": smallness(records, text_counts),
        "shared_exact_outline_signatures_between_mark_types": shared_signatures(
            records
        ),
        "outliers": [
            {
                "kind": "unboxed_candidate",
                "page": record["page"],
                "word_key": record["word_key"],
                "mark": record["mark"],
                "source_codepoint": record["source_codepoint"],
                "glyph_id": record["glyph_id"],
            }
            for record in records
            if record["box"] is None
        ],
        "records_sha256": records_digest(records),
        "records": records,
    }


def ledger(
    map_digest: str,
    font_digest: str,
    division_sajdah_digest: str,
    records: list[dict],
) -> dict:
    separate = []
    fused = []
    count_fields = {
        "text_signs": 0,
        "separate_source_glyphs": 0,
        "fused_source_glyphs": 0,
        "text_signs_by_mark": Counter(),
        "separate_source_glyphs_by_mark": Counter(),
        "fused_source_glyphs_by_mark": Counter(),
    }
    for record in records:
        semantic_indices = record.get("semantic_glyph_indices", [])
        status = (
            "separate" if record["glyph_count"] - len(semantic_indices) > 1 else "fused"
        )
        reduced = {
            "page": record["page"],
            "word_key": record["word_key"],
            "text_codepoint": record["text_codepoint"],
            "mark": record["mark"],
            "source_codepoint": record["source_codepoint"],
            "source_glyph_index": record["glyph_index"],
            "source_glyph_count": record["glyph_count"],
        }
        if semantic_indices:
            reduced["source_semantic_glyph_indices"] = semantic_indices
        (separate if status == "separate" else fused).append(reduced)
        count_fields["text_signs"] += 1
        count_fields[f"{status}_source_glyphs"] += 1
        count_fields["text_signs_by_mark"][record["mark"]] += 1
        count_fields[f"{status}_source_glyphs_by_mark"][record["mark"]] += 1
    counts = {
        name: dict(sorted(value.items())) if isinstance(value, Counter) else value
        for name, value in count_fields.items()
    }
    return {
        "schema": "quran-svg-elements/qcf-v1-waqf-source-glyphs",
        "schema_version": 2,
        "edition": "hafs-qcf-v1",
        "source": {
            "map": "authoritative schema-3 QCF V1 1405H source map",
            "map_page_files_sha256": map_digest,
            "page_font_tree_sha256": font_digest,
            "division_sajdah_source_sha256": division_sajdah_digest,
            "analysis_records_sha256": records_digest(records),
        },
        "text_marks": {
            f"U+{ord(char):04X}": mark for char, mark in MARK_BY_CHAR.items()
        },
        "counts": counts,
        "separate": separate,
        "fused": fused,
    }


def build(args: argparse.Namespace) -> tuple[dict, dict]:
    page_paths = sorted(args.map_dir.glob("pages/[0-9][0-9][0-9].json"))
    font_paths = sorted(args.fonts_dir.glob("QCF_P[0-9][0-9][0-9].TTF"))
    if len(page_paths) != 604 or len(font_paths) != 604:
        raise ValueError(
            f"expected 604 map pages and fonts, got {len(page_paths)} and {len(font_paths)}"
        )
    summary = read_json(args.map_dir / "summary.json")
    map_digest = named_digest(page_paths)
    if summary.get("page_files_sha256") != map_digest:
        raise ValueError("QCF V1 map summary does not match its page files")
    font_digest = named_digest(font_paths)
    division_sajdah_digest = sha256(args.division_sajdah_source)
    semantics = DivisionSajdahSemantics(
        args.division_sajdah_source,
        {
            "edition": "hafs-qcf-v1",
            "inputs": {
                "division_sajdah_source_sha256": division_sajdah_digest,
                "map_page_files_sha256": map_digest,
                "page_font_tree_sha256": font_digest,
            },
        },
    )
    semantic_indices_by_page: dict[int, dict[str, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for records_by_page in (semantics.divisions_by_page, semantics.sajdahs_by_page):
        for page_number, semantic_records in records_by_page.items():
            for semantic_record in semantic_records:
                source_glyph = semantic_record.get("source_glyph")
                if source_glyph is not None and source_glyph["index"] is not None:
                    semantic_indices_by_page[page_number][
                        semantic_record["word_key"]
                    ].add(source_glyph["index"])

    records = []
    direct_words = 0
    direct_source_glyphs = 0
    shared_groups = 0
    shared_canonical_words = 0
    shared_source_glyphs = 0
    for page_path in page_paths:
        page = read_json(page_path)
        page_number = int(page_path.stem)
        if page.get("page") != page_number:
            raise ValueError(f"map page identity differs: {page_path}")
        with PageFont(args.fonts_dir / f"QCF_P{page_number:03}.TTF") as font:
            (
                page_output,
                page_words,
                page_glyphs,
                page_shared_groups,
                page_shared_words,
                page_shared_glyphs,
            ) = page_records(page, font, semantic_indices_by_page.get(page_number, {}))
        records.extend(page_output)
        direct_words += page_words
        direct_source_glyphs += page_glyphs
        shared_groups += page_shared_groups
        shared_canonical_words += page_shared_words
        shared_source_glyphs += page_shared_glyphs

    inventory = {
        "direct_words": direct_words,
        "direct_source_glyphs": direct_source_glyphs,
        "shared_groups": shared_groups,
        "shared_canonical_words": shared_canonical_words,
        "shared_source_glyphs": shared_source_glyphs,
        "waqf_text_signs": len(records),
    }
    expected_inventory = {
        "direct_words": 77430,
        "direct_source_glyphs": 82008,
        "shared_groups": 1,
        "shared_canonical_words": 2,
        "shared_source_glyphs": 1,
        "waqf_text_signs": 4272,
    }
    if inventory != expected_inventory:
        raise ValueError(
            "QCF V1 waqf source inventory differs:\n"
            + json.dumps(
                {"expected": expected_inventory, "actual": inventory}, indent=2
            )
        )
    analysis = analysis_report(
        args,
        records,
        direct_words,
        direct_source_glyphs,
        shared_groups,
        shared_canonical_words,
        shared_source_glyphs,
    )
    ownership = ledger(map_digest, font_digest, division_sajdah_digest, records)
    args.ledger_out.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_out.write_bytes(json_bytes(ownership, sort_keys=True))
    if args.analysis_out is not None:
        args.analysis_out.parent.mkdir(parents=True, exist_ok=True)
        args.analysis_out.write_bytes(json_bytes(analysis))
    print(
        json.dumps(
            {
                "ledger": str(args.ledger_out),
                "ledger_sha256": sha256(args.ledger_out),
                "analysis": str(args.analysis_out) if args.analysis_out else None,
                "analysis_records_sha256": analysis["records_sha256"],
                "counts": ownership["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return analysis, ownership


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--map-dir", type=Path, required=True)
    command.add_argument("--fonts-dir", type=Path, required=True)
    command.add_argument("--division-sajdah-source", type=Path, required=True)
    command.add_argument("--ledger-out", type=Path, required=True)
    command.add_argument("--analysis-out", type=Path)
    return command


def main() -> None:
    args = parser().parse_args()
    for name in (
        "map_dir",
        "fonts_dir",
        "division_sajdah_source",
        "ledger_out",
        "analysis_out",
    ):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    build(args)


if __name__ == "__main__":
    main()
