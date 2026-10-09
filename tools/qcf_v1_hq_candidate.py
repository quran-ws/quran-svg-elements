"""Verify and source-qualify the external QCF V1 HQ word candidates."""

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from xml.etree import ElementTree

from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG = f"{{{SVG_NAMESPACE}}}"
MATRIX = re.compile(r"^matrix\(([^)]+)\)$")
WAQF_SEMANTICS = re.compile(
    rb'data-kind="mark" data-mark="waqf_[a-z_]+" data-mark-family="waqf"'
)
ElementTree.register_namespace("", SVG_NAMESPACE)

DIVISION_SAJDAH_COUNTS = {
    "division_starts": 240,
    "mapped_sajdah_source_glyphs": 14,
    "printed_rubu_al_hizb": 199,
    "restored_sajdah_source_glyphs": 1,
    "sajdah_marks": 15,
    "unprinted_rubu_al_hizb": 41,
}
PATH_GEOMETRY_ATTRIBUTES = ("d", "transform", "fill-rule", "clip-rule")
PATH_GEOMETRY_FIELDS = {
    "base_pages_sha256",
    "base_paths",
    "emitted_pages_sha256",
    "emitted_paths",
    "qualification",
    "restored_paths",
}
SEMANTIC_GROUP_CLASSES = ("division-mark", "sajdah-mark")


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_path_geometry(value: object) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != PATH_GEOMETRY_FIELDS
        or value["qualification"] != "base-order-preserved"
        or not all(
            type(value[name]) is int and value[name] >= 0
            for name in ("base_paths", "emitted_paths", "restored_paths")
        )
        or value["base_paths"] <= 0
        or value["restored_paths"] != 1
        or value["emitted_paths"] != value["base_paths"] + value["restored_paths"]
        or not valid_sha256(value["base_pages_sha256"])
        or not valid_sha256(value["emitted_pages_sha256"])
    ):
        raise ValueError("HQ base path-geometry contract differs")
    return value


def division_sajdah_summary(summary: dict) -> dict:
    counts = summary.get("counts", {})
    return {
        "qualification": "source-owned",
        **{name: counts.get(name) for name in sorted(DIVISION_SAJDAH_COUNTS)},
    }


def semantic_owner_keys(root: ElementTree.Element) -> set[str]:
    groups = [
        group
        for class_name in SEMANTIC_GROUP_CLASSES
        for group in root.findall(f'.//{SVG}g[@class="{class_name}"]')
    ]
    keys = [group.get("data-word-key") for group in groups]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("division/sajdah semantic owner keys differ")
    return set(keys)


def number(value: float) -> str:
    if abs(value) < 5e-10:
        value = 0.0
    return f"{value:.9f}".rstrip("0").rstrip(".")


def named_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def qualified_geometry_svg(data: bytes) -> bytes:
    return WAQF_SEMANTICS.sub(b'data-kind="other"', data)


def named_transformed_digest(paths: list[Path], transform) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(transform(path.read_bytes()))
    return digest.hexdigest()


def path_geometry_bytes(data: bytes) -> bytes:
    root = ElementTree.fromstring(data)
    records = []
    for element in root.iter(f"{{{SVG_NAMESPACE}}}path"):
        if not element.attrib.get("d"):
            raise ValueError("SVG path has no geometry")
        records.append(
            tuple(element.attrib.get(name, "") for name in PATH_GEOMETRY_ATTRIBUTES)
        )
    return json_bytes(records)


def named_path_geometry_digest(paths: list[Path]) -> str:
    return named_transformed_digest(paths, path_geometry_bytes)


def candidate_digest(root: Path, pages: list[int]) -> tuple[str, int]:
    digest = hashlib.sha256()
    files = []
    for page in pages:
        files.extend([root / f"page{page:03}.svg", root / f"page{page:03}.fit.json"])
    if not all(path.is_file() for path in files):
        raise ValueError("HQ candidate file set is incomplete")
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest(), len(files)


def nfc(value: object) -> str:
    return unicodedata.normalize("NFC", value if isinstance(value, str) else "")


def parse_matrix(value: str | None) -> list[float]:
    match = MATRIX.fullmatch(value or "")
    if not match:
        raise ValueError(f"unsupported path transform: {value!r}")
    values = [float(item) for item in match.group(1).replace(",", " ").split()]
    if len(values) != 6:
        raise ValueError(f"wrong path transform: {value!r}")
    if (
        abs(values[1]) > 1e-9
        or abs(values[2]) > 1e-9
        or abs(values[0]) < 1e-12
        or abs(values[3]) < 1e-12
    ):
        raise ValueError(f"non-axis path transform: {value!r}")
    return values


def intrinsic_bounds(
    path: ElementTree.Element, cache: dict[str, tuple[float, ...]]
) -> list[float]:
    data = path.get("d") or ""
    if not data:
        raise ValueError("path has no geometry")
    bounds = cache.get(data)
    if bounds is None:
        pen = BoundsPen(None)
        parse_path(data, pen)
        if pen.bounds is None:
            raise ValueError("path has no bounds")
        bounds = tuple(float(value) for value in pen.bounds)
        cache[data] = bounds
    return list(bounds)


def transformed_bounds(
    path: ElementTree.Element, cache: dict[str, tuple[float, ...]]
) -> list[float]:
    x0, y0, x1, y1 = intrinsic_bounds(path, cache)
    a, _, _, d, e, f = parse_matrix(path.get("transform"))
    xs = [a * x0 + e, a * x1 + e]
    ys = [d * y0 + f, d * y1 + f]
    return [min(xs), min(ys), max(xs), max(ys)]


def union_boxes(boxes: list[list[float]]) -> list[float]:
    if not boxes:
        raise ValueError("cannot union an empty box set")
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def dimensions(box: list[float]) -> tuple[float, float]:
    return box[2] - box[0], box[3] - box[1]


def centre(box: list[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def fit_record_box(record: dict) -> list[float]:
    box = record.get("bbox_svg")
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("candidate word has no fitted box")
    x, y, width, height = map(float, box)
    return [x, y, x + width, y + height]


def compose_optical_fit(
    source_matrix: list[float],
    source: list[float],
    target: list[float],
    radius: float,
) -> tuple[list[float], float, float]:
    source_width, source_height = dimensions(source)
    target_width, target_height = dimensions(target)
    inner_width = target_width - 2 * radius
    inner_height = target_height - 2 * radius
    if min(source_width, source_height, inner_width, inner_height) <= 0:
        raise ValueError("word bounds are empty after the optical inset")
    scale_x = inner_width / source_width
    scale_y = inner_height / source_height
    source_x, source_y = centre(source)
    target_x, target_y = centre(target)
    dx = target_x - scale_x * source_x
    dy = target_y - scale_y * source_y
    a, b, c, d, e, f = source_matrix
    matrix = [
        scale_x * a,
        scale_x * b,
        scale_y * c,
        scale_y * d,
        scale_x * e + dx,
        scale_y * f + dy,
    ]
    fill_x = inner_width / target_width
    fill_y = inner_height / target_height
    return matrix, fill_x, fill_y


def transformed_box_from_matrix(
    intrinsic: list[float], matrix: list[float]
) -> list[float]:
    x0, y0, x1, y1 = intrinsic
    a, _, _, d, e, f = matrix
    xs = [a * x0 + e, a * x1 + e]
    ys = [d * y0 + f, d * y1 + f]
    return [min(xs), min(ys), max(xs), max(ys)]


def numeric_key(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise TypeError(f"invalid word key: {value!r}")
    try:
        parts = tuple(int(part) for part in value.split(":"))
    except ValueError as error:
        raise ValueError(f"invalid word key: {value!r}") from error
    if len(parts) != 3 or any(part <= 0 for part in parts):
        raise ValueError(f"invalid word key: {value!r}")
    return parts


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def finite_list(value: object, length: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(finite_number(item) for item in value)
    )


def review_marked(element: ElementTree.Element) -> bool:
    return any(
        name.startswith("data-review") and value not in {"", "0", "none", "null"}
        for name, value in element.attrib.items()
    )


def verify_base(root: Path, manifest: dict, base: dict) -> tuple[dict, list[int]]:
    summary_path = root / "summary.json"
    if sha256(summary_path) != base["summary_sha256"]:
        raise ValueError("base summary digest differs")
    summary = read_json(summary_path)
    pages = summary.get("pages")
    if pages != list(range(1, 605)):
        raise ValueError("base page sequence differs")
    summary_waqf = summary.get("waqf", {})
    if (
        summary.get("schema") != base["summary_schema"]
        or summary.get("schema_version") != base["summary_schema_version"]
        or summary.get("edition") != manifest["edition"]
        or summary.get("print_year_hijri") != manifest["print_year_hijri"]
        or summary.get("counts", {}).get("words") != base["words"]
        or summary.get("header_placement", {}).get("qualification")
        != base["header_qualification"]
        or summary.get("pages_sha256") != base["pages_sha256"]
        or summary.get("index_sha256") != base["index_sha256"]
        or summary.get("qualified_geometry_pages_sha256")
        != base["qualified_geometry_pages_sha256"]
        or summary.get("header_qualified_geometry_pages_sha256")
        != base["header_qualified_geometry_pages_sha256"]
        or summary.get("path_geometry") != base["path_geometry"]
        or summary.get("waqf_source_glyphs_sha256") != base["waqf_source_glyphs_sha256"]
        or summary.get("division_sajdah_source_sha256")
        != base["division_sajdah_source_sha256"]
        or {
            "qualification": summary_waqf.get("qualification"),
            "text_signs": summary_waqf.get("text_signs"),
            "separate_source_glyphs": summary_waqf.get("separate_source_glyphs"),
            "fused_source_glyphs": summary_waqf.get("fused_source_glyphs"),
        }
        != base["waqf"]
        or division_sajdah_summary(summary) != base["division_sajdah"]
    ):
        raise ValueError("base corpus identity differs")
    page_paths = [root / "pages" / f"{page:03}.svg" for page in pages]
    index_paths = [root / "index/by-page" / f"{page:03}.json" for page in pages]
    if not all(path.is_file() for path in [*page_paths, *index_paths]):
        raise ValueError("base corpus file set is incomplete")
    if named_digest(page_paths) != base["pages_sha256"]:
        raise ValueError("base SVG page digest differs")
    if (
        named_transformed_digest(page_paths, qualified_geometry_svg)
        != base["qualified_geometry_pages_sha256"]
    ):
        raise ValueError("base qualified-geometry digest differs")
    if (
        named_path_geometry_digest(page_paths)
        != base["path_geometry"]["emitted_pages_sha256"]
    ):
        raise ValueError("base emitted path-geometry digest differs")
    if named_digest(index_paths) != base["index_sha256"]:
        raise ValueError("base word index digest differs")
    return summary, pages


def verify_candidate(root: Path, pages: list[int], candidate: dict) -> None:
    digest, count = candidate_digest(root, pages)
    if digest != candidate["svg_fit_tree_sha256"]:
        raise ValueError("HQ candidate tree digest differs")
    if count != candidate["files"] or len(pages) != candidate["pages"]:
        raise ValueError("HQ candidate inventory differs")


def index_words(path: Path) -> dict[str, dict]:
    source = read_json(path)
    words = source.get("words") if isinstance(source, dict) else None
    if not isinstance(words, list):
        raise TypeError(f"word index is invalid: {path}")
    result = {word.get("word_key"): word for word in words if isinstance(word, dict)}
    if len(result) != len(words) or None in result:
        raise ValueError(f"word index keys differ: {path}")
    return result


def word_groups(root: ElementTree.Element) -> dict[str, ElementTree.Element]:
    all_groups = root.findall(f'.//{SVG}g[@class="word"]')
    groups = {
        group.get("data-word-key"): group
        for group in all_groups
        if group.get("data-word-key")
    }
    if len(groups) != len(all_groups):
        raise ValueError("page has duplicate or missing word keys")
    return groups


def qualify_candidate(
    page: int,
    key: str,
    record: dict,
    base_word: dict,
    candidate_root: ElementTree.Element,
    candidate_group: ElementTree.Element,
    base_group: ElementTree.Element,
    policy: dict,
    optical_radius: float,
    cache: dict[str, tuple[float, ...]],
) -> tuple[dict | None, str]:
    if page in policy["exclude_pages"]:
        return None, "excluded-page"
    if key in policy["exclude_word_keys"]:
        return None, "excluded-word"
    texts = (
        nfc(base_word.get("rasm_uthmani")),
        nfc(base_group.get("data-rasm-uthmani")),
        nfc(candidate_group.get("data-rasm-uthmani")),
        nfc(record.get("text")),
    )
    if not texts[0] or len(set(texts)) != 1:
        return None, "text-differs"
    if review_marked(candidate_group):
        return None, "review-marked"

    flags = record.get("flags")
    resolved = candidate_group.get("data-resolved-from-shape")
    classes = policy["source_classes"]
    if flags == classes["direct"]["required_flags"] and resolved is None:
        source_class = "direct"
    elif (
        flags == classes["pdf-recovered"]["required_flags"]
        and isinstance(resolved, str)
        and re.fullmatch(r"recovered:[0-9a-f]{64}", resolved) is not None
        and record.get("resolved_from_shape") == resolved
    ):
        source_class = "pdf-recovered"
    else:
        return None, "unsupported-source"

    audit = record.get("audit")
    class_policy = classes[source_class]
    if class_policy["require_fit_audit"]:
        if (
            not isinstance(audit, dict)
            or set(audit) != {"shift", "gain", "scale_locked"}
            or not finite_number(audit["shift"])
            or not finite_number(audit["gain"])
            or not isinstance(audit["scale_locked"], bool)
            or abs(audit["shift"]) > policy["maximum_audit_shift"]
        ):
            return None, "fit-audit"
    elif audit is not None:
        return None, "fit-audit"
    if record.get("substituted") is not None or record.get("contours"):
        return None, "repaired"
    if (
        not finite_number(record.get("iou"))
        or record["iou"] < policy["minimum_scan_iou_1406"]
    ):
        return None, "scan-iou"
    scale_bounds = class_policy["scale_vs_page"]
    scale = record.get("scale_vs_page")
    if scale_bounds is None:
        if scale is not None:
            return None, "scale-drift"
    elif not finite_number(scale) or not scale_bounds[0] <= scale <= scale_bounds[1]:
        return None, "scale-drift"

    candidate_paths = candidate_group.findall(f".//{SVG}path")
    base_paths = base_group.findall(f".//{SVG}path")
    if len(candidate_paths) != policy["required_path_count"]:
        return None, "candidate-path-count"
    if any(review_marked(path) for path in candidate_paths):
        return None, "review-marked"
    if not base_paths:
        return None, "base-no-paths"
    if any(path not in list(base_group) for path in base_paths):
        return None, "base-nested-paths"
    candidate_path = candidate_paths[0]
    try:
        source_matrix = parse_matrix(candidate_path.get("transform"))
        source_intrinsic = intrinsic_bounds(candidate_path, cache)
        source = transformed_bounds(candidate_path, cache)
        target = union_boxes([transformed_bounds(path, cache) for path in base_paths])
        reported = fit_record_box(record)
    except ValueError:
        return None, "unsupported-geometry"

    source_width, source_height = dimensions(source)
    target_width, target_height = dimensions(target)
    reported_width, reported_height = dimensions(reported)
    if (
        min(
            source_width,
            source_height,
            target_width,
            target_height,
            reported_width,
            reported_height,
        )
        <= 0
    ):
        return None, "empty-bounds"
    source_x, source_y = centre(source)
    reported_x, reported_y = centre(reported)
    delta = policy["source_reported_center_delta_max"]
    if abs(source_x - reported_x) > delta or abs(source_y - reported_y) > delta:
        return None, "reported-centre"
    size_bounds = policy["source_reported_size_ratio"]
    if not (
        size_bounds[0] <= source_width / reported_width <= size_bounds[1]
        and size_bounds[0] <= source_height / reported_height <= size_bounds[1]
    ):
        return None, "reported-size"
    aspect = (source_width / source_height) / (target_width / target_height)
    aspect_bounds = policy["source_target_aspect_ratio"]
    if not aspect_bounds[0] <= aspect <= aspect_bounds[1]:
        return None, "aspect-ratio"

    if not finite_number(optical_radius) or optical_radius < 0:
        raise ValueError(f"invalid optical radius on page {page}: {optical_radius!r}")
    try:
        matrix, fill_x, fill_y = compose_optical_fit(
            source_matrix, source, target, optical_radius
        )
    except ValueError:
        return None, "optical-inset"
    if min(fill_x, fill_y) < policy["minimum_fitted_fill"]:
        return None, "fitted-fill"
    centre_bounds = transformed_box_from_matrix(source_intrinsic, matrix)
    final = [
        centre_bounds[0] - optical_radius,
        centre_bounds[1] - optical_radius,
        centre_bounds[2] + optical_radius,
        centre_bounds[3] + optical_radius,
    ]
    tolerance = 1e-6
    if any(abs(left - right) > tolerance for left, right in zip(final, target)):
        raise AssertionError(
            f"optically fitted HQ word differs from target bounds: {key}"
        )

    data = candidate_path.get("d") or ""
    return {
        "page": page,
        "word_key": key,
        "text": record["text"],
        "source_class": source_class,
        "source_line_1406": record.get("line"),
        "target_line_1405": base_word.get("line"),
        "scan_iou_1406": record["iou"],
        "scale_vs_page": scale,
        "source_path_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "source_bounds": [round(value, 6) for value in source],
        "target_bounds": [round(value, 6) for value in target],
        "centre_bounds": [round(value, 6) for value in centre_bounds],
        "final_bounds": [round(value, 6) for value in final],
        "fill": [round(fill_x, 6), round(fill_y, 6)],
        "optical_radius": optical_radius,
        "optical_copies": 5 if optical_radius else 1,
        "matrix": matrix,
        "d": data,
        "fill_rule": candidate_path.get("fill-rule"),
    }, "hq"


def page_bytes(root: ElementTree.Element) -> bytes:
    return (ElementTree.tostring(root, encoding="unicode") + "\n").encode()
