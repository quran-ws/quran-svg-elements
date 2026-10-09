#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools==4.66.1",
# ]
# ///
"""Measure QCF V1 connected glyph elements against reviewed shape labels.

This audit splits each mapped page-font glyph into outer-contour-plus-counter elements and
computes the established normalized shape signature. It reports exact reviewed-label
coverage only; it never guesses labels or rewrites page output.
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
from markshape import element_points, sig_key, signature
from split_line_elements import contour_polylines, group_elements

MARK_LABELS = {
    "dot",
    "two_dots",
    "three_dots",
    "fathah",
    "kasrah",
    "dammah",
    "tanwin_al_fath",
    "tanwin_al_kasr",
    "tanwin_al_damm",
    "sukun",
    "shaddah",
    "hamzah",
    "maddah",
    "omitted_alif",
    "hamzat_al_wasl",
    "waqf",
    "small_circle",
    "small_yaa",
    "small_waw",
    "small_meem",
    "small_noon",
    "saktah",
    "seen_al_qiraah",
    "imalah",
    "ishmam",
    "tashil",
    "sajdah",
    "hizb",
}
NONMARK_LABELS = {"letter", "letter_part", "letter_hamzah", "word", "ignore"}


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def named_digest(paths: list[Path]) -> str:
    value = hashlib.sha256()
    for path in paths:
        value.update(path.name.encode())
        value.update(b"\0")
        value.update(path.read_bytes())
    return value.hexdigest()


def glyph_records(page: dict):
    for owner_type, owners, owner_key in (
        ("word", page.get("words", []), "word_key"),
        ("shared_group", page.get("shared_groups", []), "id"),
        ("ayah_mark", page.get("ayah_markers", []), "ayah_key"),
    ):
        for owner in owners:
            for glyph in owner.get("glyphs", []):
                yield owner_type, owner.get(owner_key), glyph


def element_signature(path: str, element: list[dict], polylines: list[list]) -> str:
    contours = [polylines[item["sp"]["index"]] for item in element]
    return sig_key(signature(element_points(contours)))


def audit(args: argparse.Namespace) -> dict:
    pages = sorted(args.map_dir.glob("pages/[0-9][0-9][0-9].json"))
    fonts = sorted(args.fonts_dir.glob("QCF_P[0-9][0-9][0-9].TTF"))
    if len(pages) != 604 or len(fonts) != 604:
        raise ValueError(
            f"expected 604 map pages and fonts, got {len(pages)} and {len(fonts)}"
        )

    raw_labels = read_json(args.labels)
    if not isinstance(raw_labels, dict):
        raise TypeError("shape labels must be an object")
    labels = {
        key: record["label"]
        for key, record in raw_labels.items()
        if isinstance(key, str)
        and isinstance(record, dict)
        and isinstance(record.get("label"), str)
    }
    if len(labels) != len(raw_labels):
        raise TypeError("invalid shape-label record")

    counts = Counter()
    element_counts = Counter()
    signature_counts = Counter()
    label_counts = Counter()
    label_signatures = defaultdict(set)
    examples = defaultdict(list)

    for page_path in pages:
        page = read_json(page_path)
        page_number = page.get("page")
        if page_number != int(page_path.stem):
            raise ValueError(f"map page identity differs: {page_path}")
        with PageFont(args.fonts_dir / f"QCF_P{page_number:03}.TTF") as font:
            seen = set()
            for owner_type, owner, glyph in glyph_records(page):
                codepoint = parse_codepoint(glyph["codepoint"])
                name = font.cmap.get(codepoint)
                if name is None:
                    raise ValueError(f"page {page_number}: no U+{codepoint:04X}")
                path, glyph_box = font.outline(codepoint)
                elements = group_elements(path)
                polylines = contour_polylines(path)
                if not elements or not polylines:
                    raise ValueError(f"page {page_number}: empty U+{codepoint:04X}")

                counts["glyphs"] += 1
                counts["elements"] += len(elements)
                counts["contours"] += len(polylines)
                counts[
                    "composite_glyphs"
                    if font.glyf[name].isComposite()
                    else "simple_glyphs"
                ] += 1
                element_counts[len(elements)] += 1
                if codepoint not in seen:
                    seen.add(codepoint)
                    counts["unique_page_glyphs"] += 1

                glyph_has_match = False
                glyph_has_mark = False
                for index, element in enumerate(elements):
                    shape = element_signature(path, element, polylines)
                    signature_counts[shape] += 1
                    if len(examples[shape]) < args.examples:
                        examples[shape].append(
                            {
                                "page": page_number,
                                "owner_type": owner_type,
                                "owner": owner,
                                "codepoint": f"U+{codepoint:04X}",
                                "glyph_box": list(glyph_box),
                                "element": index,
                                "contours": len(element),
                            }
                        )
                    label = labels.get(shape)
                    if label is None:
                        counts["unmatched_elements"] += 1
                        continue
                    glyph_has_match = True
                    counts["matched_elements"] += 1
                    label_counts[label] += 1
                    label_signatures[label].add(shape)
                    parts = set(label.split("+"))
                    if parts and parts <= MARK_LABELS:
                        glyph_has_mark = True
                        counts["matched_mark_elements"] += 1
                    elif label in NONMARK_LABELS:
                        counts["matched_nonmark_elements"] += 1
                    else:
                        counts["matched_mixed_elements"] += 1
                counts[
                    "glyphs_with_match" if glyph_has_match else "glyphs_without_match"
                ] += 1
                if glyph_has_mark:
                    counts["glyphs_with_mark_match"] += 1

    matched_shapes = {shape for shape in signature_counts if shape in labels}
    counts["distinct_signatures"] = len(signature_counts)
    counts["distinct_matched_signatures"] = len(matched_shapes)
    counts["distinct_unmatched_signatures"] = len(signature_counts) - len(
        matched_shapes
    )

    ranked = signature_counts.most_common()
    report = {
        "schema": "quran-svg-elements/qcf-v1-glyph-element-audit",
        "schema_version": 1,
        "edition": "hafs-qcf-v1",
        "map": {
            "summary_sha256": digest(args.map_dir / "summary.json"),
            "page_files_sha256": named_digest(pages),
            "schema_version": read_json(args.map_dir / "summary.json").get(
                "schema_version"
            ),
        },
        "fonts": {"files": len(fonts), "tree_sha256": named_digest(fonts)},
        "labels": {"records": len(labels), "sha256": digest(args.labels)},
        "counts": dict(sorted(counts.items())),
        "coverage": {
            "exact_element_fraction": counts["matched_elements"] / counts["elements"],
            "exact_mark_element_fraction": counts["matched_mark_elements"]
            / counts["elements"],
        },
        "glyph_element_counts": {
            str(key): value for key, value in sorted(element_counts.items())
        },
        "labels_by_occurrence": dict(label_counts.most_common()),
        "label_signature_counts": {
            label: len(shapes) for label, shapes in sorted(label_signatures.items())
        },
        "matched_signatures": [
            {
                "signature": shape,
                "label": labels[shape],
                "occurrences": occurrences,
                "examples": examples[shape],
            }
            for shape, occurrences in ranked
            if shape in labels
        ][: args.top],
        "unmatched_signatures": [
            {
                "signature": shape,
                "occurrences": occurrences,
                "examples": examples[shape],
            }
            for shape, occurrences in ranked
            if shape not in labels
        ][: args.top],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-dir", type=Path, required=True)
    parser.add_argument("--fonts-dir", type=Path, required=True)
    parser.add_argument(
        "--labels", type=Path, default=ROOT / ".cache/marks/labels.json"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args()
    for name in ("map_dir", "fonts_dir", "labels", "out"):
        setattr(args, name, getattr(args, name).resolve())
    if args.top < 1 or args.examples < 1:
        raise ValueError("top and examples must be positive")
    audit(args)


if __name__ == "__main__":
    main()
