#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "cairosvg==2.8.2",
#   "fonttools==4.66.1",
#   "numpy==2.3.3",
#   "pillow==11.3.0",
#   "scipy==1.16.2",
# ]
# ///
"""Adversarial visual audit for the fixed-page QCF V1 corpus.

The audit is deliberately diagnostic. It compares isolated printed units, the verified QCF
fallback, and the pinned 1405H scan. It never repairs placement and never changes HQ admission.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from itertools import pairwise
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import cairosvg
import numpy as np
import qcf_v1_hq_candidate as hq
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, label

SVG = hq.SVG
SCHEMA = "quran-svg-elements/qcf-v1-visual-audit"
FINDING_SCHEMA = "quran-svg-elements/qcf-v1-visual-finding"
ORNAMENT_CLASSES = {
    "ayah-mark",
    "division-mark",
    "sajdah-mark",
    "surah-name",
    "basmalah",
}

DEFAULT_POLICY = {
    "high_width": 1920,
    "reading_width": 690,
    "low_alpha": 24,
    "solid_alpha": 160,
    "pair_prefilter_page_units": 1.25,
    "solid_overlap_pixels": 0,
    "soft_overlap_pixels": 3,
    "high_clearance_pixels": 2.0,
    "reading_clearance_pixels": 1.0,
    "minimum_ink_ratio": 0.58,
    "maximum_ink_ratio": 1.65,
    "component_loss": 2,
    "maximum_hq_vertical_scale_ratio": 1.08,
    "line_center_drift_page_units": 1.5,
    "line_reference_floor": 0.84,
    "line_reference_regression": 0.045,
    "word_reference_floor": 0.68,
    "word_reference_regression": 0.08,
    "reference_tolerance_pixels": 2,
    "reference_registration_pixels": 2,
    "cross_renderer_floor": 0.995,
}


def parse_pages(value: str) -> list[int]:
    pages: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            raise ValueError("empty page range")
        parts = item.split("-", 1)
        start = int(parts[0])
        end = int(parts[-1])
        if start < 1 or end > 604 or start > end:
            raise ValueError(f"invalid page range: {item}")
        pages.update(range(start, end + 1))
    return sorted(pages)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def finding_id(finding: dict) -> str:
    identity = {
        key: finding.get(key)
        for key in ("category", "page", "line", "word_key", "right", "left", "owner")
    }
    return hashlib.sha256(json_bytes(identity)).hexdigest()[:20]


def finding(category: str, severity: str, **values: object) -> dict:
    row = {
        "schema": FINDING_SCHEMA,
        "category": category,
        "severity": severity,
        **values,
    }
    row["id"] = finding_id(row)
    return row


def read_policy(path: Path | None) -> dict:
    policy = dict(DEFAULT_POLICY)
    if path:
        value = json.loads(path.read_text())
        unknown = sorted(set(value) - set(policy))
        if unknown:
            raise ValueError(f"unknown visual-policy fields: {unknown}")
        policy.update(value)
    numeric = [value for value in policy.values() if isinstance(value, (int, float))]
    if not all(math.isfinite(float(value)) for value in numeric):
        raise ValueError("visual policy contains a non-finite number")
    if not 0 <= policy["low_alpha"] < policy["solid_alpha"] <= 255:
        raise ValueError("invalid alpha thresholds")
    if policy["maximum_hq_vertical_scale_ratio"] <= 1:
        raise ValueError("invalid vertical-scale threshold")
    return policy


def locate_page(root: Path, page: int) -> Path:
    for candidate in (
        root / "pages" / f"{page:03}.svg",
        root / f"{page:03}.svg",
        root / f"page{page:03}.svg",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"page {page} is missing under {root}")


def locate_index(root: Path, page: int) -> Path:
    for candidate in (
        root / "index" / "by-page" / f"{page:03}.json",
        root / "by-page" / f"{page:03}.json",
        root / f"{page:03}.json",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"page index {page} is missing under {root}")


def source_page(job: dict, temporary: Path) -> Path:
    if job.get("candidate_dir"):
        return locate_page(Path(job["candidate_dir"]), job["page"])
    qvp = Path(job["qvp_dir"]) / f"{job['page']:03}.qvp"
    if not qvp.is_file():
        raise FileNotFoundError(qvp)
    output = temporary / f"{job['page']:03}.svg"
    subprocess.run(
        [job["converter"], "qvp2svg", qvp, output],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return output


def transformed_box(path: ElementTree.Element, cache: dict) -> list[float]:
    return (
        hq.transformed_bounds(path, cache)
        if path.get("transform")
        else hq.intrinsic_bounds(path, cache)
    )


def union_box(boxes: list[list[float]]) -> list[float]:
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def box_intersects(
    first: list[float], second: list[float], margin: float = 0.0
) -> bool:
    return not (
        first[2] + margin < second[0]
        or second[2] + margin < first[0]
        or first[3] + margin < second[1]
        or second[3] + margin < first[1]
    )


def page_to_pixel_box(
    box: list[float], viewbox: list[float], width: int, height: int, margin: int = 2
) -> tuple[int, int, int, int]:
    vx, vy, vw, vh = viewbox
    return (
        max(0, math.floor((box[0] - vx) * width / vw) - margin),
        max(0, math.floor((box[1] - vy) * height / vh) - margin),
        min(width, math.ceil((box[2] - vx) * width / vw) + margin),
        min(height, math.ceil((box[3] - vy) * height / vh) + margin),
    )


def render_svg(root: ElementTree.Element, width: int) -> np.ndarray:
    viewbox = [float(value) for value in root.get("viewBox", "").split()]
    if len(viewbox) != 4 or min(viewbox[2:]) <= 0:
        raise ValueError("invalid SVG viewBox")
    height = max(1, round(width * viewbox[3] / viewbox[2]))
    png = cairosvg.svg2png(
        bytestring=ElementTree.tostring(root, encoding="utf-8"),
        output_width=width,
        output_height=height,
    )
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


def render_reference(path: Path, width: int, height: int) -> np.ndarray:
    image = Image.open(path).convert("L")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(image)


def empty_shell(root: ElementTree.Element) -> ElementTree.Element:
    return ElementTree.Element(f"{SVG}svg", {"viewBox": root.get("viewBox")})


def word_shell(
    root: ElementTree.Element, groups: list[ElementTree.Element]
) -> ElementTree.Element:
    shell = empty_shell(root)
    for group in groups:
        shell.append(deepcopy(group))
    return shell


def threshold(alpha: np.ndarray, value: int) -> np.ndarray:
    return alpha >= value


def crop(mask: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return mask[y0:y1, x0:x1]


def component_count(mask: np.ndarray, minimum_area: int = 3) -> int:
    components, count = label(mask)
    return sum(
        int((components == item).sum()) >= minimum_area for item in range(1, count + 1)
    )


def hole_count(mask: np.ndarray, minimum_area: int = 3) -> int:
    if not mask.any():
        return 0
    inverse, count = label(~mask)
    holes = 0
    for item in range(1, count + 1):
        ys, xs = np.where(inverse == item)
        if len(xs) < minimum_area:
            continue
        if (
            xs.min() == 0
            or ys.min() == 0
            or xs.max() == mask.shape[1] - 1
            or ys.max() == mask.shape[0] - 1
        ):
            continue
        holes += 1
    return holes


def tolerant_score(
    candidate: np.ndarray, reference: np.ndarray, tolerance: int
) -> dict:
    cp = int(candidate.sum())
    rp = int(reference.sum())
    if not cp or not rp:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "candidate_pixels": cp,
            "reference_pixels": rp,
        }
    near_ref = binary_dilation(reference, iterations=tolerance)
    near_candidate = binary_dilation(candidate, iterations=tolerance)
    precision = float((candidate & near_ref).sum() / cp)
    recall = float((reference & near_candidate).sum() / rp)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "candidate_pixels": cp,
        "reference_pixels": rp,
    }


def shifted(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    result = np.zeros_like(mask)
    sy0, sy1 = max(0, -dy), min(mask.shape[0], mask.shape[0] - dy)
    sx0, sx1 = max(0, -dx), min(mask.shape[1], mask.shape[1] - dx)
    if sy0 < sy1 and sx0 < sx1:
        result[sy0 + dy : sy1 + dy, sx0 + dx : sx1 + dx] = mask[sy0:sy1, sx0:sx1]
    return result


def registered_score(
    candidate: np.ndarray, reference: np.ndarray, tolerance: int, search: int
) -> dict:
    best = None
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            score = tolerant_score(shifted(candidate, dx, dy), reference, tolerance)
            rank = (
                score["f1"],
                score["precision"],
                score["recall"],
                -abs(dx) - abs(dy),
            )
            if best is None or rank > best[0]:
                best = (rank, {**score, "dx": dx, "dy": dy})
    return best[1]


def read_source_records(path: Path | None, hq_keys: set[str]) -> dict[str, dict]:
    if path is None:
        return {}
    records = {}
    required = {"page", "word_key", "text", "transform"}
    with path.open() as stream:
        lines = enumerate(stream, 1)
        for number, line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid HQ source record at line {number}"
                ) from error
            if not isinstance(row, dict) or not required <= set(row):
                raise ValueError(f"HQ source-record fields differ at line {number}")
            key = row["word_key"]
            transform = row["transform"]
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"\d+:\d+:\d+", key)
                or key in records
                or type(row["page"]) is not int
                or not 1 <= row["page"] <= 604
                or not isinstance(row["text"], str)
                or not row["text"]
                or not isinstance(transform, list)
                or len(transform) != 6
                or not all(
                    type(value) in {int, float} and math.isfinite(value)
                    for value in transform
                )
                or abs(transform[1]) > 1e-9
                or abs(transform[2]) > 1e-9
                or abs(transform[0]) < 1e-12
                or abs(transform[3]) < 1e-12
            ):
                raise ValueError(f"HQ source-record identity differs at line {number}")
            records[key] = row
    if set(records) != hq_keys:
        raise ValueError("HQ source-record coverage differs")
    return records


def read_hq_map(path: Path | None) -> tuple[set[str], str | None]:
    if path is None:
        return set(), None
    value = json.loads(path.read_text())
    pattern = re.compile(r"^\d+:\d+:\d+$")
    keys: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if isinstance(key, str) and pattern.fullmatch(key):
                    keys.add(key)
                if (
                    key in {"word_key", "key"}
                    and isinstance(child, str)
                    and pattern.fullmatch(child)
                ):
                    keys.add(child)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str) and pattern.fullmatch(item):
            keys.add(item)

    visit(value)
    source_records_sha256 = value.get("source_records_sha256")
    if source_records_sha256 is not None and (
        not isinstance(source_records_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_records_sha256)
    ):
        raise ValueError("HQ map source-record digest differs")
    return keys, source_records_sha256


def page_inventory(
    root: ElementTree.Element,
    index: dict,
    hq_keys: set[str],
) -> tuple[list[dict], dict[str, dict], list[float], list[dict]]:
    viewbox = [float(value) for value in root.get("viewBox", "").split()]
    if len(viewbox) != 4 or min(viewbox[2:]) <= 0:
        raise ValueError("invalid page viewBox")
    groups = root.findall(f'.//{SVG}g[@class="word"]')
    group_map: dict[str, ElementTree.Element] = {}
    for group in groups:
        key = group.get("data-word-key")
        if not key or key in group_map:
            raise ValueError(f"duplicate or missing word group key: {key!r}")
        group_map[key] = group
    words = index.get("words")
    if not isinstance(words, list):
        raise TypeError("page index words must be a list")
    cache: dict = {}
    rows = []
    by_key = {}
    findings = []
    expected_lines: dict[int, list[str]] = defaultdict(list)
    for ordinal, word in enumerate(words):
        key = word.get("word_key")
        line = int(word["line"])
        expected_lines[line].append(key)
        group = group_map.get(key)
        if group is None:
            findings.append(
                finding(
                    "word-group-missing",
                    "blocker",
                    page=index.get("page"),
                    line=line,
                    word_key=key,
                )
            )
            continue
        paths = group.findall(f".//{SVG}path")
        shared = group.get("data-shared-paths-with")
        boxes = [transformed_box(path, cache) for path in paths]
        row = {
            "ordinal": ordinal,
            "key": key,
            "text": word.get("rasm_uthmani") or group.get("data-rasm-uthmani") or "",
            "line": line,
            "group": group,
            "paths": paths,
            "box": union_box(boxes) if boxes else None,
            "index_box": [float(value) for value in word["box"]],
            "shared_owner": shared,
            "hq": key in hq_keys
            or group.get("data-vector-source") == "qpc-resize-hq"
            or any(path.get("data-source") == "qpc-resize-hq" for path in paths),
        }
        if not paths and not shared:
            findings.append(
                finding(
                    "word-ink-missing",
                    "blocker",
                    page=index.get("page"),
                    line=line,
                    word_key=key,
                    text=row["text"],
                )
            )
        rows.append(row)
        by_key[key] = row
    extras = sorted(set(group_map) - set(by_key))
    if extras:
        findings.append(
            finding(
                "word-group-extra",
                "blocker",
                page=index.get("page"),
                keys=extras[:20],
                count=len(extras),
            )
        )
    line_groups = root.findall(f'.//{SVG}g[@class="line"]')
    actual_lines = [int(line.get("data-line")) for line in line_groups]
    if actual_lines != list(range(1, 16)):
        findings.append(
            finding(
                "line-inventory", "blocker", page=index.get("page"), actual=actual_lines
            )
        )
    for line in line_groups:
        number = int(line.get("data-line"))
        actual = [
            group.get("data-word-key")
            for group in line.findall(f'.//{SVG}g[@class="word"]')
        ]
        expected = expected_lines.get(number, [])
        if actual != expected:
            findings.append(
                finding(
                    "line-word-order",
                    "blocker",
                    page=index.get("page"),
                    line=number,
                    actual=actual,
                    expected=expected,
                )
            )
    return rows, by_key, viewbox, findings


def render_parity(
    root: ElementTree.Element,
    rows: list[dict],
    width: int,
) -> tuple[np.ndarray, np.ndarray]:
    shells = [empty_shell(root), empty_shell(root)]
    physical_by_line: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["paths"]:
            physical_by_line[row["line"]].append(row)
    for line, line_rows in sorted(physical_by_line.items()):
        wrappers = [
            ElementTree.SubElement(
                shell, f"{SVG}g", {"class": "line", "data-line": str(line)}
            )
            for shell in shells
        ]
        for index, row in enumerate(line_rows):
            wrappers[index % 2].append(deepcopy(row["group"]))
    return tuple(render_svg(shell, width)[:, :, 3] for shell in shells)


def pair_metrics(
    alpha_a: np.ndarray,
    alpha_b: np.ndarray,
    box_a: tuple[int, int, int, int],
    box_b: tuple[int, int, int, int],
    low_alpha: int,
    solid_alpha: int,
) -> dict:
    x0 = min(box_a[0], box_b[0])
    y0 = min(box_a[1], box_b[1])
    x1 = max(box_a[2], box_b[2])
    y1 = max(box_a[3], box_b[3])
    a = alpha_a[y0:y1, x0:x1]
    b = alpha_b[y0:y1, x0:x1]
    low_a = a >= low_alpha
    low_b = b >= low_alpha
    solid_a = a >= solid_alpha
    solid_b = b >= solid_alpha
    solid_overlap = int((solid_a & solid_b).sum())
    soft_overlap = int((low_a & low_b).sum())
    if low_a.any() and low_b.any():
        distance = float(distance_transform_edt(~low_b)[low_a].min())
    else:
        distance = None
    return {
        "solid_overlap_pixels": solid_overlap,
        "soft_overlap_pixels": soft_overlap,
        "minimum_distance_pixels": distance,
    }


def pair_reference_evidence(
    candidate_pair: tuple[np.ndarray, np.ndarray],
    fallback_pair: tuple[np.ndarray, np.ndarray],
    candidate_boxes: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
    fallback_boxes: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
    reference: np.ndarray,
    policy: dict,
) -> dict | None:
    margin = int(policy["reference_tolerance_pixels"]) + int(
        policy["reference_registration_pixels"]
    )
    boxes = (*candidate_boxes, *fallback_boxes)
    crop_box = (
        max(0, min(box[0] for box in boxes) - margin),
        max(0, min(box[1] for box in boxes) - margin),
        min(reference.shape[1], max(box[2] for box in boxes) + margin),
        min(reference.shape[0], max(box[3] for box in boxes) + margin),
    )
    x0, y0, x1, y1 = crop_box
    if x0 >= x1 or y0 >= y1:
        return None
    low_alpha = int(policy["low_alpha"])
    solid_alpha = int(policy["solid_alpha"])
    candidate = crop(
        (candidate_pair[0] >= low_alpha) | (candidate_pair[1] >= low_alpha), crop_box
    )
    fallback = crop(
        (fallback_pair[0] >= low_alpha) | (fallback_pair[1] >= low_alpha), crop_box
    )
    overlap = crop(
        (candidate_pair[0] >= solid_alpha) & (candidate_pair[1] >= solid_alpha),
        crop_box,
    )
    target = crop(reference, crop_box)
    if not overlap.any() or not target.any():
        return None
    tolerance = int(policy["reference_tolerance_pixels"])
    search = int(policy["reference_registration_pixels"])
    candidate_score = registered_score(candidate, target, tolerance, search)
    fallback_score = registered_score(fallback, target, tolerance, search)
    aligned_overlap = shifted(overlap, candidate_score["dx"], candidate_score["dy"])
    supported = binary_dilation(target, iterations=tolerance) if tolerance else target
    support = float((aligned_overlap & supported).sum() / aligned_overlap.sum())
    quality_acceptable = candidate_score["f1"] >= float(
        policy["word_reference_floor"]
    ) and candidate_score["f1"] >= fallback_score["f1"] - float(
        policy["word_reference_regression"]
    )
    return {
        "attested": quality_acceptable and support == 1.0,
        "quality_acceptable": quality_acceptable,
        "overlap_support_fraction": support,
        "candidate_score": candidate_score,
        "fallback_score": fallback_score,
    }


def pair_findings(
    page: int,
    candidate_root: ElementTree.Element,
    candidate_rows: list[dict],
    base_root: ElementTree.Element,
    base_by_key: dict[str, dict],
    viewbox: list[float],
    reference_path: Path | None,
    policy: dict,
    candidate_rendered: dict[int, tuple[np.ndarray, np.ndarray]],
    base_rendered: dict[int, tuple[np.ndarray, np.ndarray]],
) -> tuple[list[dict], int]:
    by_line: dict[int, list[dict]] = defaultdict(list)
    for row in candidate_rows:
        if row["paths"]:
            by_line[row["line"]].append(row)
    widths = (int(policy["high_width"]), int(policy["reading_width"]))
    references = {}
    findings = []
    pairs = 0
    for line, line_rows in sorted(by_line.items()):
        for index, (right, left) in enumerate(pairwise(line_rows)):
            pairs += 1
            if (
                right["shared_owner"] == left["key"]
                or left["shared_owner"] == right["key"]
            ):
                continue
            base_right = base_by_key.get(right["key"])
            base_left = base_by_key.get(left["key"])
            if (
                not base_right
                or not base_left
                or not base_right["paths"]
                or not base_left["paths"]
            ):
                continue
            if not (
                box_intersects(
                    right["box"],
                    left["box"],
                    float(policy["pair_prefilter_page_units"]),
                )
                or box_intersects(
                    base_right["box"],
                    base_left["box"],
                    float(policy["pair_prefilter_page_units"]),
                )
            ):
                continue
            pair_box = union_box([right["box"], left["box"]])
            candidate_contaminated = any(
                other_index not in {index, index + 1}
                and other_index % 2 in {index % 2, (index + 1) % 2}
                and box_intersects(other["box"], pair_box, 0.25)
                for other_index, other in enumerate(line_rows)
            )
            base_line_rows = [base_by_key[row["key"]] for row in line_rows]
            base_pair_box = union_box([base_right["box"], base_left["box"]])
            fallback_contaminated = any(
                other_index not in {index, index + 1}
                and box_intersects(other["box"], base_pair_box, 0.25)
                for other_index, other in enumerate(base_line_rows)
            )
            metrics = {"candidate": {}, "fallback": {}}
            reference_evidence = {}
            for width in widths:
                if candidate_contaminated:
                    candidate_pair = (
                        render_svg(word_shell(candidate_root, [right["group"]]), width)[
                            :, :, 3
                        ],
                        render_svg(word_shell(candidate_root, [left["group"]]), width)[
                            :, :, 3
                        ],
                    )
                else:
                    candidate_pair = (
                        candidate_rendered[width][index % 2],
                        candidate_rendered[width][(index + 1) % 2],
                    )
                if fallback_contaminated:
                    fallback_pair = (
                        render_svg(word_shell(base_root, [base_right["group"]]), width)[
                            :, :, 3
                        ],
                        render_svg(word_shell(base_root, [base_left["group"]]), width)[
                            :, :, 3
                        ],
                    )
                else:
                    fallback_pair = (
                        base_rendered[width][base_right["physical_index"] % 2],
                        base_rendered[width][base_left["physical_index"] % 2],
                    )
                height = candidate_pair[0].shape[0]
                candidate_boxes = (
                    page_to_pixel_box(right["box"], viewbox, width, height),
                    page_to_pixel_box(left["box"], viewbox, width, height),
                )
                fallback_boxes = (
                    page_to_pixel_box(base_right["box"], viewbox, width, height),
                    page_to_pixel_box(base_left["box"], viewbox, width, height),
                )
                metrics["candidate"][str(width)] = pair_metrics(
                    candidate_pair[0],
                    candidate_pair[1],
                    candidate_boxes[0],
                    candidate_boxes[1],
                    int(policy["low_alpha"]),
                    int(policy["solid_alpha"]),
                )
                metrics["fallback"][str(width)] = pair_metrics(
                    fallback_pair[0],
                    fallback_pair[1],
                    fallback_boxes[0],
                    fallback_boxes[1],
                    int(policy["low_alpha"]),
                    int(policy["solid_alpha"]),
                )
                candidate_metrics = metrics["candidate"][str(width)]
                fallback_metrics = metrics["fallback"][str(width)]
                if (
                    reference_path
                    and candidate_metrics["solid_overlap_pixels"]
                    > int(policy["solid_overlap_pixels"])
                    and fallback_metrics["solid_overlap_pixels"]
                    <= int(policy["solid_overlap_pixels"])
                ):
                    if width not in references:
                        references[width] = (
                            render_reference(reference_path, width, height) < 220
                        )
                    evidence = pair_reference_evidence(
                        candidate_pair,
                        fallback_pair,
                        candidate_boxes,
                        fallback_boxes,
                        references[width],
                        policy,
                    )
                    if evidence is not None:
                        reference_evidence[str(width)] = evidence
            high = metrics["candidate"][str(widths[0])]
            base_high = metrics["fallback"][str(widths[0])]
            reading = metrics["candidate"][str(widths[1])]
            base_reading = metrics["fallback"][str(widths[1])]
            common = {
                "page": page,
                "line": line,
                "right": right["key"],
                "left": left["key"],
                "right_text": right["text"],
                "left_text": left["text"],
                "right_hq": right["hq"],
                "left_hq": left["hq"],
                "metrics": metrics,
            }
            if reference_evidence:
                common["reference_evidence"] = reference_evidence
            if high["solid_overlap_pixels"] > int(policy["solid_overlap_pixels"]):
                category = (
                    "adjacent-new-solid-overlap"
                    if base_high["solid_overlap_pixels"]
                    <= int(policy["solid_overlap_pixels"])
                    else "adjacent-inherited-solid-overlap"
                )
                evidence = reference_evidence.get(str(widths[0]))
                if (
                    category == "adjacent-new-solid-overlap"
                    and evidence
                    and evidence["attested"]
                ):
                    category = "adjacent-scan-attested-overlap"
                severity = (
                    "blocker" if category == "adjacent-new-solid-overlap" else "review"
                )
                findings.append(finding(category, severity, **common))
            elif high["soft_overlap_pixels"] > int(
                policy["soft_overlap_pixels"]
            ) and base_high["soft_overlap_pixels"] <= int(
                policy["soft_overlap_pixels"]
            ):
                findings.append(
                    finding("adjacent-new-soft-overlap", "review", **common)
                )
            else:
                candidate_distance = high["minimum_distance_pixels"]
                fallback_distance = base_high["minimum_distance_pixels"]
                if (
                    candidate_distance is not None
                    and fallback_distance is not None
                    and candidate_distance <= float(policy["high_clearance_pixels"])
                    and candidate_distance + 1 < fallback_distance
                ):
                    findings.append(
                        finding("adjacent-clearance-regression", "review", **common)
                    )
            if reading["solid_overlap_pixels"] > int(
                policy["solid_overlap_pixels"]
            ) and base_reading["solid_overlap_pixels"] <= int(
                policy["solid_overlap_pixels"]
            ):
                evidence = reference_evidence.get(str(widths[1]))
                findings.append(
                    finding(
                        "reading-size-scan-attested-merge"
                        if evidence and evidence["attested"]
                        else "reading-size-new-solid-merge",
                        "review" if evidence and evidence["attested"] else "blocker",
                        **common,
                    )
                )
            else:
                candidate_distance = reading["minimum_distance_pixels"]
                fallback_distance = base_reading["minimum_distance_pixels"]
                if (
                    candidate_distance is not None
                    and fallback_distance is not None
                    and candidate_distance <= float(policy["reading_clearance_pixels"])
                    and candidate_distance + 1 < fallback_distance
                ):
                    findings.append(
                        finding("reading-size-clearance-regression", "review", **common)
                    )
    return findings, pairs


def assign_physical_indices(rows: list[dict]) -> None:
    by_line: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["paths"]:
            by_line[row["line"]].append(row)
    for line_rows in by_line.values():
        for index, row in enumerate(line_rows):
            row["physical_index"] = index


def mask_box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def hq_scale(
    row: dict, source_record: dict | None = None
) -> tuple[float, float, float] | None:
    """Return x scale, y scale, and y/x from canonical HQ source geometry."""

    if not row["hq"]:
        return None
    if source_record is not None:
        matrices = [source_record["transform"]]
    else:
        if not row["paths"]:
            return None
        matrices = []
        for path in row["paths"]:
            transform = path.get("transform")
            if not transform:
                return None
            try:
                matrices.append(hq.parse_matrix(transform))
            except ValueError:
                return None
    linear = {tuple(round(value, 9) for value in matrix[:4]) for matrix in matrices}
    if len(linear) != 1:
        return None
    a, b, c, d = matrices[0][:4]
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    if min(scale_x, scale_y) <= 0:
        return None
    return scale_x, scale_y, scale_y / scale_x


def vertical_stretch_finding(
    page: int,
    row: dict,
    policy: dict,
    *,
    source_record: dict | None = None,
    scan_regression: bool = False,
    candidate_score: dict | None = None,
    fallback_score: dict | None = None,
) -> dict | None:
    scale = hq_scale(row, source_record)
    if scale is None:
        return None
    scale_x, scale_y, ratio = scale
    maximum = float(policy["maximum_hq_vertical_scale_ratio"])
    if ratio <= maximum:
        return None
    values = {
        "page": page,
        "line": row["line"],
        "word_key": row["key"],
        "text": row["text"],
        "hq": True,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "vertical_scale_ratio": ratio,
        "maximum_hq_vertical_scale_ratio": maximum,
        "scan_corroborated": scan_regression,
        "scale_source": "source-record"
        if source_record is not None
        else "svg-transform",
    }
    if candidate_score is not None and fallback_score is not None:
        values.update(candidate_score=candidate_score, fallback_score=fallback_score)
    return finding(
        "hq-vertical-stretch", "blocker" if scan_regression else "review", **values
    )


def comparison_findings(
    page: int,
    candidate_root: ElementTree.Element,
    base_root: ElementTree.Element,
    candidate_rows: list[dict],
    base_by_key: dict[str, dict],
    viewbox: list[float],
    reference_path: Path | None,
    policy: dict,
    candidate_rendered: dict[int, tuple[np.ndarray, np.ndarray]],
    base_rendered: dict[int, tuple[np.ndarray, np.ndarray]],
    source_records: dict[str, dict],
) -> tuple[list[dict], dict]:
    high_width = int(policy["high_width"])
    reading_width = int(policy["reading_width"])
    candidate_high = candidate_rendered[high_width]
    base_rows = [
        base_by_key[row["key"]] for row in candidate_rows if row["key"] in base_by_key
    ]
    candidate_keys = {row["key"] for row in candidate_rows}
    base_rows = [row for row in base_rows if row["key"] in candidate_keys]
    assign_physical_indices(base_rows)
    base_high = base_rendered[high_width]
    candidate_reading = candidate_rendered[reading_width]
    base_reading = base_rendered[reading_width]
    high_height = candidate_high[0].shape[0]
    reading_height = candidate_reading[0].shape[0]
    reference_high = None
    if reference_path and reference_path.is_file():
        reference_high = render_reference(reference_path, high_width, high_height) < 220
    findings = []
    counters = Counter()
    for row in candidate_rows:
        if not row["paths"]:
            continue
        base = base_by_key.get(row["key"])
        if base is None or not base["paths"]:
            continue
        candidate_box = row["box"]
        base_box = base["box"]
        index_box = row["index_box"]
        page_box = union_box([candidate_box, base_box, index_box])
        high_box = page_to_pixel_box(
            page_box, viewbox, high_width, high_height, margin=4
        )
        reading_box = page_to_pixel_box(
            page_box, viewbox, reading_width, reading_height, margin=2
        )
        c_high = crop(
            threshold(
                candidate_high[row["physical_index"] % 2], int(policy["low_alpha"])
            ),
            high_box,
        )
        b_high = crop(
            threshold(base_high[base["physical_index"] % 2], int(policy["low_alpha"])),
            high_box,
        )
        c_reading = crop(
            threshold(
                candidate_reading[row["physical_index"] % 2], int(policy["low_alpha"])
            ),
            reading_box,
        )
        b_reading = crop(
            threshold(
                base_reading[base["physical_index"] % 2], int(policy["low_alpha"])
            ),
            reading_box,
        )
        cp = int(c_high.sum())
        bp = int(b_high.sum())
        common = {
            "page": page,
            "line": row["line"],
            "word_key": row["key"],
            "text": row["text"],
            "hq": row["hq"],
        }
        if not cp:
            findings.append(finding("word-raster-missing", "blocker", **common))
            continue
        if bp:
            ratio = cp / bp
            if ratio < float(policy["minimum_ink_ratio"]) or ratio > float(
                policy["maximum_ink_ratio"]
            ):
                findings.append(
                    finding(
                        "word-ink-ratio-outlier",
                        "review",
                        **common,
                        candidate_pixels=cp,
                        fallback_pixels=bp,
                        ratio=ratio,
                    )
                )
            components_candidate = component_count(c_high)
            components_base = component_count(b_high)
            if components_candidate + int(policy["component_loss"]) <= components_base:
                findings.append(
                    finding(
                        "word-component-loss",
                        "review",
                        **common,
                        candidate_components=components_candidate,
                        fallback_components=components_base,
                    )
                )
            holes_candidate = hole_count(c_high)
            holes_base = hole_count(b_high)
            if holes_candidate < holes_base and row["hq"]:
                findings.append(
                    finding(
                        "word-counter-loss",
                        "review",
                        **common,
                        candidate_holes=holes_candidate,
                        fallback_holes=holes_base,
                    )
                )
            reading_components = component_count(c_reading, minimum_area=2)
            base_reading_components = component_count(b_reading, minimum_area=2)
            if (
                reading_components + int(policy["component_loss"])
                <= base_reading_components
            ):
                findings.append(
                    finding(
                        "reading-size-component-loss",
                        "review",
                        **common,
                        candidate_components=reading_components,
                        fallback_components=base_reading_components,
                    )
                )
        scan_regression = False
        candidate_score = None
        fallback_score = None
        if row["hq"] and reference_high is not None:
            ref = crop(reference_high, high_box)
            if int(ref.sum()) >= 12:
                tolerance = int(policy["reference_tolerance_pixels"])
                search = int(policy["reference_registration_pixels"])
                candidate_score = registered_score(c_high, ref, tolerance, search)
                fallback_score = registered_score(b_high, ref, tolerance, search)
                counters["hq_words_scan_compared"] += 1
                scan_regression = fallback_score["f1"] >= float(
                    policy["word_reference_floor"]
                ) and candidate_score["f1"] < (
                    fallback_score["f1"] - float(policy["word_reference_regression"])
                )
        stretch = vertical_stretch_finding(
            page,
            row,
            policy,
            source_record=source_records.get(row["key"]),
            scan_regression=scan_regression,
            candidate_score=candidate_score,
            fallback_score=fallback_score,
        )
        if stretch is not None:
            findings.append(stretch)
        elif scan_regression:
            findings.append(
                finding(
                    "hq-scan-regression",
                    "review",
                    **common,
                    candidate_score=candidate_score,
                    fallback_score=fallback_score,
                )
            )
    # Whole-line checks use complete page ink; unlike word crops they intentionally include all words.
    candidate_page = render_svg(candidate_root, high_width)[:, :, 3]
    base_page = render_svg(base_root, high_width)[:, :, 3]
    by_line: dict[int, list[dict]] = defaultdict(list)
    for row in candidate_rows:
        if row["paths"]:
            by_line[row["line"]].append(row)
    for line, line_rows in sorted(by_line.items()):
        line_box = union_box([row["index_box"] for row in line_rows])
        pixel = page_to_pixel_box(line_box, viewbox, high_width, high_height, margin=8)
        candidate_mask = crop(
            threshold(candidate_page, int(policy["low_alpha"])), pixel
        )
        base_mask = crop(threshold(base_page, int(policy["low_alpha"])), pixel)
        cb = mask_box(candidate_mask)
        bb = mask_box(base_mask)
        if cb and bb:
            candidate_center = (cb[1] + cb[3]) / 2
            base_center = (bb[1] + bb[3]) / 2
            drift = abs(candidate_center - base_center) * viewbox[3] / high_height
            if drift > float(policy["line_center_drift_page_units"]):
                findings.append(
                    finding(
                        "line-vertical-drift",
                        "review",
                        page=page,
                        line=line,
                        drift_page_units=drift,
                    )
                )
        if reference_high is not None:
            ref = crop(reference_high, pixel)
            if ref.any():
                tolerance = int(policy["reference_tolerance_pixels"])
                search = int(policy["reference_registration_pixels"])
                candidate_score = registered_score(
                    candidate_mask, ref, tolerance, search
                )
                fallback_score = registered_score(base_mask, ref, tolerance, search)
                counters["lines_scan_compared"] += 1
                if fallback_score["f1"] >= float(
                    policy["line_reference_floor"]
                ) and candidate_score["f1"] < fallback_score["f1"] - float(
                    policy["line_reference_regression"]
                ):
                    findings.append(
                        finding(
                            "line-scan-regression",
                            "review",
                            page=page,
                            line=line,
                            candidate_score=candidate_score,
                            fallback_score=fallback_score,
                        )
                    )
    return findings, dict(counters)


def ornament_groups(root: ElementTree.Element) -> list[ElementTree.Element]:
    return [
        group
        for class_name in ORNAMENT_CLASSES
        for group in root.findall(f'.//{SVG}g[@class="{class_name}"]')
    ]


def ornament_inventory(counter: Counter) -> list[dict]:
    rows = []
    for identity, count in sorted(
        counter.items(), key=lambda item: tuple(value or "" for value in item[0])
    ):
        rows.append(
            {
                "class": identity[0],
                "ayah_key": identity[1],
                "word_key": identity[2],
                "sid": identity[3],
                "count": count,
            }
        )
    return rows


def ornament_findings(
    page: int,
    candidate_root: ElementTree.Element,
    base_root: ElementTree.Element,
    policy: dict,
) -> list[dict]:
    candidate_groups = ornament_groups(candidate_root)
    base_groups = ornament_groups(base_root)

    def identity(group: ElementTree.Element) -> tuple:
        return (
            group.get("class"),
            group.get("data-ayah-key"),
            group.get("data-word-key"),
            group.get("data-sid"),
        )

    candidate_inventory = Counter(identity(group) for group in candidate_groups)
    base_inventory = Counter(identity(group) for group in base_groups)
    if candidate_inventory != base_inventory:
        return [
            finding(
                "ornament-inventory-drift",
                "blocker",
                page=page,
                candidate=ornament_inventory(candidate_inventory),
                fallback=ornament_inventory(base_inventory),
            )
        ]
    if not candidate_groups and not base_groups:
        return []
    width = int(policy["high_width"])
    candidate_alpha = render_svg(word_shell(candidate_root, candidate_groups), width)[
        :, :, 3
    ]
    base_alpha = render_svg(word_shell(base_root, base_groups), width)[:, :, 3]
    candidate_mask = threshold(candidate_alpha, int(policy["low_alpha"]))
    base_mask = threshold(base_alpha, int(policy["low_alpha"]))
    score = tolerant_score(candidate_mask, base_mask, tolerance=1)
    if score["f1"] < 0.995 or component_count(candidate_mask) != component_count(
        base_mask
    ):
        return [
            finding(
                "ornament-geometry-drift",
                "blocker",
                page=page,
                score=score,
                candidate_components=component_count(candidate_mask),
                fallback_components=component_count(base_mask),
            )
        ]
    return []


def optical_copy_findings(page: int, rows: list[dict]) -> list[dict]:
    findings = []
    for row in rows:
        if not row["hq"] or len(row["paths"]) not in {1, 5}:
            if row["hq"] and row["paths"]:
                findings.append(
                    finding(
                        "optical-copy-count",
                        "blocker",
                        page=page,
                        line=row["line"],
                        word_key=row["key"],
                        text=row["text"],
                        path_count=len(row["paths"]),
                    )
                )
            continue
        if len(row["paths"]) == 1:
            continue
        paths = row["paths"]
        # Source SVG keeps one path and five transforms. QVP-to-SVG may flatten each copy;
        # the raster checks remain authoritative there.
        if len({path.get("d") for path in paths}) != 1 or any(
            not path.get("transform") for path in paths
        ):
            continue
        try:
            matrices = [hq.parse_matrix(path.get("transform")) for path in paths]
        except ValueError:
            continue
        if (
            len({tuple(round(value, 9) for value in matrix[:4]) for matrix in matrices})
            != 1
        ):
            findings.append(
                finding(
                    "optical-copy-transform",
                    "blocker",
                    page=page,
                    line=row["line"],
                    word_key=row["key"],
                    text=row["text"],
                )
            )
            continue
        points = [(matrix[4], matrix[5]) for matrix in matrices]
        centre = min(
            points,
            key=lambda point: sum(math.dist(point, other) for other in points),
        )
        offsets = {
            (round(x - centre[0], 9), round(y - centre[1], 9)) for x, y in points
        }
        horizontal = sorted(abs(x) for x, y in offsets if x and not y)
        vertical = sorted(abs(y) for x, y in offsets if y and not x)
        valid = (
            (0.0, 0.0) in offsets
            and len(offsets) == 5
            and len(horizontal) == 2
            and len(vertical) == 2
            and abs(horizontal[0] - horizontal[1]) <= 1e-8
            and abs(vertical[0] - vertical[1]) <= 1e-8
        )
        if not valid:
            findings.append(
                finding(
                    "optical-copy-transform",
                    "blocker",
                    page=page,
                    line=row["line"],
                    word_key=row["key"],
                    text=row["text"],
                    offsets=sorted(offsets),
                )
            )
    return findings


def path_findings(
    page: int, root: ElementTree.Element, viewbox: list[float]
) -> list[dict]:
    vx, vy, vw, vh = viewbox
    limits = [vx, vy, vx + vw, vy + vh]
    cache: dict = {}
    findings = []
    parents = {child: parent for parent in root.iter() for child in parent}
    for number, path in enumerate(root.findall(f".//{SVG}path"), 1):
        try:
            box = transformed_box(path, cache)
        except (TypeError, ValueError) as error:
            findings.append(
                finding(
                    "invalid-path-geometry",
                    "blocker",
                    page=page,
                    owner=f"path:{number}",
                    detail=str(error),
                )
            )
            continue
        if not all(math.isfinite(value) for value in box):
            findings.append(
                finding(
                    "nonfinite-path-geometry",
                    "blocker",
                    page=page,
                    owner=f"path:{number}",
                )
            )
            continue
        if (
            box[0] < limits[0] - 1
            or box[1] < limits[1] - 1
            or box[2] > limits[2] + 1
            or box[3] > limits[3] + 1
        ):
            node = path
            owner = None
            while node in parents:
                node = parents[node]
                if node.tag != f"{SVG}g":
                    continue
                owner = (
                    node.get("data-word-key")
                    or node.get("data-ayah-key")
                    or node.get("class")
                )
                if owner:
                    break
            findings.append(
                finding(
                    "ink-outside-page",
                    "blocker",
                    page=page,
                    owner=owner or f"path:{number}",
                    box=box,
                    viewbox=viewbox,
                )
            )
    return findings


def cross_renderer_finding(
    page: int,
    source: Path,
    root: ElementTree.Element,
    resvg: Path,
    policy: dict,
) -> dict | None:
    width = int(policy["reading_width"])
    cairo = render_svg(root, width)[:, :, 3]
    with TemporaryDirectory(prefix=f"qcf-v1-resvg-{page:03}-") as directory:
        png = Path(directory) / "page.png"
        subprocess.run(
            [resvg, "-w", str(width), source, png],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        other = np.asarray(Image.open(png).convert("RGBA"))[:, :, 3]
    candidate = threshold(cairo, int(policy["low_alpha"]))
    reference = threshold(other, int(policy["low_alpha"]))
    score = tolerant_score(candidate, reference, tolerance=1)
    candidate_components = component_count(candidate)
    reference_components = component_count(reference)
    if (
        score["f1"] < float(policy["cross_renderer_floor"])
        or candidate_components != reference_components
    ):
        return finding(
            "cross-renderer-drift",
            "review",
            page=page,
            score=score,
            cairo_components=candidate_components,
            resvg_components=reference_components,
        )
    return None


def audit_page(job: dict) -> dict:
    page = int(job["page"])
    policy = job["policy"]
    hq_keys = set(job["hq_keys"])
    findings = []
    counters = Counter()
    with TemporaryDirectory(prefix=f"qcf-v1-audit-{page:03}-") as directory:
        temporary = Path(directory)
        candidate_path = source_page(job, temporary)
        base_path = locate_page(Path(job["base_dir"]), page)
        index_path = locate_index(Path(job["index_dir"]), page)
        candidate_root = ElementTree.parse(candidate_path).getroot()
        base_root = ElementTree.parse(base_path).getroot()
        index = json.loads(index_path.read_text())
        index.setdefault("page", page)
        candidate_rows, _candidate_by_key, viewbox, inventory_findings = page_inventory(
            candidate_root, index, hq_keys
        )
        source_records = job.get("source_records", {})
        if job.get("require_source_records"):
            hq_rows = {row["key"]: row for row in candidate_rows if row["hq"]}
            if set(source_records) != set(hq_rows):
                raise ValueError(f"HQ source-record page coverage differs: {page}")
            if any(
                record["page"] != page or record["text"] != hq_rows[key]["text"]
                for key, record in source_records.items()
            ):
                raise ValueError(f"HQ source-record page identity differs: {page}")
        base_rows, base_by_key, base_viewbox, base_inventory_findings = page_inventory(
            base_root, index, set()
        )
        assign_physical_indices(candidate_rows)
        assign_physical_indices(base_rows)
        findings.extend(inventory_findings)
        if base_inventory_findings:
            findings.append(
                finding(
                    "fallback-inventory-invalid",
                    "blocker",
                    page=page,
                    count=len(base_inventory_findings),
                )
            )
        if viewbox != base_viewbox:
            findings.append(
                finding(
                    "page-viewbox-drift",
                    "blocker",
                    page=page,
                    candidate=viewbox,
                    fallback=base_viewbox,
                )
            )
        counters["logical_words"] += len(candidate_rows)
        counters["physical_words"] += sum(bool(row["paths"]) for row in candidate_rows)
        counters["hq_words"] += sum(row["hq"] for row in candidate_rows)
        findings.extend(path_findings(page, candidate_root, viewbox))
        findings.extend(optical_copy_findings(page, candidate_rows))
        reference_path = None
        if job.get("reference_dir"):
            reference_path = Path(job["reference_dir"]) / f"page{page:03}.png"
            if not reference_path.is_file():
                findings.append(finding("reference-page-missing", "blocker", page=page))
                reference_path = None
        widths = (int(policy["high_width"]), int(policy["reading_width"]))
        candidate_rendered = {
            width: render_parity(candidate_root, candidate_rows, width)
            for width in widths
        }
        base_rendered = {
            width: render_parity(base_root, base_rows, width) for width in widths
        }
        pair_rows, pair_count = pair_findings(
            page,
            candidate_root,
            candidate_rows,
            base_root,
            base_by_key,
            viewbox,
            reference_path,
            policy,
            candidate_rendered,
            base_rendered,
        )
        findings.extend(pair_rows)
        counters["adjacent_pairs"] += pair_count
        comparison, comparison_counts = comparison_findings(
            page,
            candidate_root,
            base_root,
            candidate_rows,
            base_by_key,
            viewbox,
            reference_path,
            policy,
            candidate_rendered,
            base_rendered,
            source_records,
        )
        findings.extend(comparison)
        counters.update(comparison_counts)
        findings.extend(ornament_findings(page, candidate_root, base_root, policy))
        if job.get("cross_renderer"):
            cross = cross_renderer_finding(
                page, candidate_path, candidate_root, Path(job["resvg"]), policy
            )
            if cross:
                findings.append(cross)
        return {
            "page": page,
            "candidate_sha256": sha256(candidate_path),
            "fallback_sha256": sha256(base_path),
            "source_record_count": len(source_records),
            "counters": dict(counters),
            "findings": findings,
        }


def read_review_ledger(path: Path | None) -> dict:
    if path is None:
        return {
            "schema": "qcf-v1/visual-review-ledger",
            "schema_version": 1,
            "findings": [],
        }
    value = json.loads(path.read_text())
    if (
        value.get("schema") != "qcf-v1/visual-review-ledger"
        or value.get("schema_version") != 1
    ):
        raise ValueError("unsupported visual-review ledger")
    rows = value.get("findings")
    if not isinstance(rows, list):
        raise TypeError("visual-review findings must be a list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise TypeError("invalid visual-review finding")
        if row["id"] in seen:
            raise ValueError(f"duplicate visual-review finding: {row['id']}")
        seen.add(row["id"])
        if row.get("status") not in {"accepted", "open"}:
            raise ValueError(f"invalid visual-review status: {row['id']}")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError(f"visual-review finding has no reason: {row['id']}")
    return value


def apply_review(findings: list[dict], ledger: dict) -> dict:
    decisions = {row["id"]: row for row in ledger["findings"]}
    current = {row["id"] for row in findings}
    accepted = []
    open_rows = []
    unreviewed = []
    for row in findings:
        decision = decisions.get(row["id"])
        row["review"] = decision
        if row["severity"] == "blocker":
            if decision:
                row["review_ignored"] = True
            continue
        if decision is None:
            unreviewed.append(row["id"])
        elif decision["status"] == "open":
            open_rows.append(row["id"])
        else:
            accepted.append(row["id"])
    return {
        "accepted": accepted,
        "open": open_rows,
        "unreviewed": unreviewed,
        "stale": sorted(set(decisions) - current),
    }


def baseline_delta(findings: list[dict], path: Path | None) -> dict:
    if path is None:
        return {"new": [], "resolved": [], "unchanged": []}
    previous = json.loads(path.read_text())
    old = {row["id"] for row in previous.get("findings", [])}
    new = {row["id"] for row in findings}
    return {
        "new": sorted(new - old),
        "resolved": sorted(old - new),
        "unchanged": sorted(old & new),
    }


def report_html(report: dict) -> str:
    rows = []
    for row in report["findings"]:
        location = ":".join(
            str(value)
            for value in (
                row.get("page"),
                row.get("line"),
                row.get("word_key") or row.get("right"),
            )
            if value is not None
        )
        review = row.get("review") or {}
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(row['id'])}</code></td>"
            f"<td>{html.escape(row['severity'])}</td>"
            f"<td>{html.escape(row['category'])}</td>"
            f"<td>{html.escape(location)}</td>"
            f"<td dir=rtl>{html.escape(row.get('text') or row.get('right_text') or '')}</td>"
            f"<td>{html.escape(review.get('status', 'unreviewed'))}</td>"
            "</tr>"
        )
    summary = {
        "status": report["status"],
        "counts": report["counts"],
        "review": {key: len(value) for key, value in report["review"].items()},
    }
    return f"""<!doctype html><meta charset="utf-8"><title>QCF V1 visual audit</title>
<style>body{{font:14px system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:6px;vertical-align:top}}th{{position:sticky;top:0;background:#fff}}code{{font-size:11px}}</style>
<h1>QCF V1 adversarial visual audit</h1><pre>{html.escape(json.dumps(summary, ensure_ascii=False, indent=2))}</pre>
<table><thead><tr><th>ID</th><th>Severity</th><th>Category</th><th>Location</th><th>Text</th><th>Review</th></tr></thead><tbody>{"".join(rows)}</tbody></table>"""


def run(args: argparse.Namespace) -> dict:
    pages = parse_pages(args.pages)
    policy = read_policy(args.policy)
    hq_keys, expected_source_records_sha256 = read_hq_map(args.hq_map)
    if args.qvp_dir and not args.converter:
        raise ValueError("--converter is required with --qvp-dir")
    if args.qvp_dir and hq_keys and not args.source_records:
        raise ValueError("--source-records is required for HQ QVP audit")
    if args.qvp_dir and hq_keys and not expected_source_records_sha256:
        raise ValueError("HQ QVP audit requires a source-record digest in the HQ map")
    if (
        args.source_records
        and expected_source_records_sha256
        and sha256(args.source_records) != expected_source_records_sha256
    ):
        raise ValueError("HQ source-record digest differs")
    source_records = read_source_records(args.source_records, hq_keys)
    records_by_page: dict[int, dict[str, dict]] = defaultdict(dict)
    for key, row in source_records.items():
        records_by_page[row["page"]][key] = row
    if args.out_dir.exists():
        raise FileExistsError(args.out_dir)
    args.out_dir.mkdir(parents=True)
    cross_pages = (
        set(parse_pages(args.cross_renderer_pages))
        if args.cross_renderer_pages
        else set()
    )
    common = {
        "policy": policy,
        "candidate_dir": str(args.candidate_dir.resolve())
        if args.candidate_dir
        else None,
        "qvp_dir": str(args.qvp_dir.resolve()) if args.qvp_dir else None,
        "converter": str(args.converter.resolve()) if args.converter else None,
        "base_dir": str(args.base_dir.resolve()),
        "index_dir": str(args.index_dir.resolve()),
        "reference_dir": str(args.reference_dir.resolve())
        if args.reference_dir
        else None,
        "hq_keys": sorted(hq_keys),
        "resvg": str(args.resvg.resolve()) if args.resvg else None,
        "require_source_records": bool(args.qvp_dir and hq_keys),
    }
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(
                audit_page,
                {
                    **common,
                    "page": page,
                    "cross_renderer": page in cross_pages,
                    "source_records": records_by_page.get(page, {}),
                },
            ): page
            for page in pages
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: row["page"])
    findings = [row for result in results for row in result["findings"]]
    findings.sort(
        key=lambda row: (
            0 if row["severity"] == "blocker" else 1,
            row.get("page", 0),
            row.get("line", 0),
            row["category"],
            row["id"],
        )
    )
    counters = Counter()
    for result in results:
        counters.update(result["counters"])
    counters.update(
        {
            "pages": len(results),
            "findings": len(findings),
            "blockers": sum(row["severity"] == "blocker" for row in findings),
            "review_findings": sum(row["severity"] == "review" for row in findings),
        }
    )
    categories = Counter(row["category"] for row in findings)
    ledger = read_review_ledger(args.review_ledger)
    review = apply_review(findings, ledger)
    delta = baseline_delta(findings, args.baseline_report)
    if counters["blockers"] or review["stale"]:
        status = "fail"
    elif review["unreviewed"] or (args.require_no_open and review["open"]):
        status = "review"
    else:
        status = "pass"
    identity = hashlib.sha256(
        json_bytes(
            {
                "candidate": [
                    (row["page"], row["candidate_sha256"]) for row in results
                ],
                "fallback": [(row["page"], row["fallback_sha256"]) for row in results],
                "policy": policy,
                "hq_map": sha256(args.hq_map) if args.hq_map else None,
                "source_records": sha256(args.source_records)
                if args.source_records
                else None,
            }
        )
    ).hexdigest()
    report = {
        "schema": SCHEMA,
        "schema_version": 1,
        "status": status,
        "input_identity": identity,
        "pages": pages,
        "policy": policy,
        "counts": {**dict(counters), "categories": dict(categories)},
        "review": review,
        "baseline_delta": delta,
        "source_records_sha256": sha256(args.source_records)
        if args.source_records
        else None,
        "findings": findings,
        "page_results": [
            {
                "page": row["page"],
                "candidate_sha256": row["candidate_sha256"],
                "fallback_sha256": row["fallback_sha256"],
                "source_record_count": row["source_record_count"],
                "counters": row["counters"],
                "finding_ids": [finding_row["id"] for finding_row in row["findings"]],
            }
            for row in results
        ],
    }
    (args.out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    (args.out_dir / "findings.ndjson").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in findings
        )
    )
    (args.out_dir / "report.html").write_text(report_html(report))
    summary = {
        "status": status,
        "input_identity": identity,
        "counts": report["counts"],
        "review": {key: len(value) for key, value in review.items()},
        "baseline_delta": {key: len(value) for key, value in delta.items()},
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return report


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate-dir", type=Path)
    source.add_argument("--qvp-dir", type=Path)
    command.add_argument("--converter", type=Path)
    command.add_argument("--base-dir", type=Path, required=True)
    command.add_argument("--index-dir", type=Path, required=True)
    command.add_argument("--reference-dir", type=Path)
    command.add_argument("--hq-map", type=Path)
    command.add_argument("--source-records", type=Path)
    command.add_argument("--policy", type=Path)
    command.add_argument("--review-ledger", type=Path)
    command.add_argument("--baseline-report", type=Path)
    command.add_argument("--resvg", type=Path)
    command.add_argument("--cross-renderer-pages", default="")
    command.add_argument("--pages", default="1-604")
    command.add_argument(
        "--jobs", type=int, default=max(1, min(8, os.cpu_count() or 1))
    )
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--report-only", action="store_true")
    command.add_argument("--require-no-open", action="store_true")
    return command


def main() -> None:
    args = parser().parse_args()
    report = run(args)
    if args.report_only:
        return
    if report["status"] == "fail":
        raise SystemExit(1)
    if report["status"] == "review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
