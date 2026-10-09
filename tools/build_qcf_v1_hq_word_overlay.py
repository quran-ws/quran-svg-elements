#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools==4.66.1",
# ]
# ///

"""Build the source-qualified QCF V1 HQ word corpus.

A word is replaced only when its pinned source identity and geometry pass the committed source
policy, replacing it cannot erase independently owned semantics, and its exact source identity is
not in the reviewed-fallback ledger. Target-scan comparison never drives automatic admission; it
may support an explicit source-bound fallback decision recorded in that ledger.
"""

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import qcf_v1_hq_candidate as hq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "conformance/qcf-v1-hq-word-source.json"
DEFAULT_OUT_DIR = ROOT / ".cache/qcf-v1/svg-1405-hq"
OPTICAL_SCHEMA = "quran-svg-elements/qcf-v1-optical-radius-calibration"
REVIEWED_FALLBACK_SCHEMA = "quran-svg-elements/qcf-v1-hq-reviewed-fallbacks"
REVIEWED_FALLBACK_QUALIFICATION = "complete-corpus-visual-audit-reviewed"

SVG = hq.SVG
EXPECTED_EXCLUSIONS = {
    "aspect-ratio": 456,
    "candidate-missing": 52,
    "excluded-page": 62,
    "excluded-word": 1,
    "fit-audit": 39,
    "reported-centre": 1198,
    "reported-size": 1490,
    "review-marked": 759,
    "reviewed-fallback": 62,
    "scale-drift": 1070,
    "scan-iou": 69,
    "semantic-owner": 214,
    "text-differs": 1957,
    "typed-owner": 4221,
    "unsupported-source": 5043,
}


def validate_manifest(
    value: object,
) -> tuple[dict, dict, dict, dict, dict, dict, dict | None]:
    required = {
        "schema",
        "schema_version",
        "edition",
        "print_year_hijri",
        "base",
        "candidate",
        "source_policy",
        "reviewed_fallbacks",
        "optical_calibration",
        "expected",
        "qualified_output",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("HQ source manifest fields differ")
    if (
        value["schema"] != "quran-svg-elements/qcf-v1-hq-word-source"
        or value["schema_version"] != 7
        or value["edition"] != "hafs-qcf-v1"
        or value["print_year_hijri"] != 1405
    ):
        raise ValueError("wrong HQ source manifest identity")
    base = value["base"]
    candidate = value["candidate"]
    policy = value["source_policy"]
    reviewed = value["reviewed_fallbacks"]
    optical = value["optical_calibration"]
    expected = value["expected"]
    qualified = value["qualified_output"]
    if not all(
        isinstance(item, dict)
        for item in (base, candidate, policy, reviewed, optical, expected)
    ):
        raise TypeError("HQ source manifest sections must be objects")

    base_fields = {
        "summary_sha256",
        "summary_schema",
        "summary_schema_version",
        "pages_sha256",
        "qualified_geometry_pages_sha256",
        "header_qualified_geometry_pages_sha256",
        "path_geometry",
        "index_sha256",
        "pages",
        "words",
        "header_qualification",
        "waqf_source_glyphs_sha256",
        "waqf",
        "division_sajdah_source_sha256",
        "division_sajdah",
    }
    if set(base) != base_fields:
        raise ValueError("HQ base fields differ")
    digest_fields = {
        "summary_sha256",
        "pages_sha256",
        "qualified_geometry_pages_sha256",
        "header_qualified_geometry_pages_sha256",
        "index_sha256",
        "waqf_source_glyphs_sha256",
        "division_sajdah_source_sha256",
    }
    if not all(hq.valid_sha256(base[name]) for name in digest_fields):
        raise ValueError("HQ base digest differs")
    hq.validate_path_geometry(base["path_geometry"])
    if (
        base["summary_schema"] != "quran-svg-elements/qcf-v1-vector-slice"
        or base["summary_schema_version"] != 5
        or base["pages"] != 604
        or base["words"] != 77432
        or base["header_qualification"] != "mechanically-qualified"
        or base["waqf"]
        != {
            "qualification": "source-glyph-qualified",
            "text_signs": 4272,
            "separate_source_glyphs": 4221,
            "fused_source_glyphs": 51,
        }
        or base["division_sajdah"]
        != {"qualification": "source-owned", **hq.DIVISION_SAJDAH_COUNTS}
    ):
        raise ValueError("HQ base identity differs")

    candidate_fields = {
        "source",
        "source_print_year_hijri",
        "target_print_year_hijri",
        "svg_fit_tree_sha256",
        "files",
        "pages",
        "positions_with_vector",
    }
    if set(candidate) != candidate_fields:
        raise ValueError("HQ candidate fields differ")
    if (
        not isinstance(candidate["source"], str)
        or not candidate["source"]
        or candidate["source_print_year_hijri"] != 1406
        or candidate["target_print_year_hijri"] != 1405
        or not hq.valid_sha256(candidate["svg_fit_tree_sha256"])
        or candidate["files"] != 1208
        or candidate["pages"] != 604
        or candidate["positions_with_vector"] != 77374
    ):
        raise ValueError("HQ candidate identity differs")

    policy_fields = {
        "exclude_pages",
        "exclude_word_keys",
        "text_identity",
        "required_path_count",
        "source_classes",
        "maximum_audit_shift",
        "minimum_scan_iou_1406",
        "source_reported_center_delta_max",
        "source_reported_size_ratio",
        "source_target_aspect_ratio",
        "minimum_fitted_fill",
        "placement",
        "path_kind",
    }
    if set(policy) != policy_fields:
        raise ValueError("HQ source policy fields differ")
    if (
        policy["exclude_pages"] != [1, 2]
        or policy["exclude_word_keys"] != ["13:37:8", "13:37:9"]
        or policy["text_identity"]
        != "NFC equality across the base index, base SVG, candidate SVG, and fit report"
        or policy["required_path_count"] != 1
        or policy["source_classes"]
        != {
            "direct": {
                "required_flags": [],
                "require_fit_audit": True,
                "scale_vs_page": [0.97, 1.03],
            },
            "pdf-recovered": {
                "required_flags": ["print-resolved", "pdf-recovered"],
                "require_fit_audit": False,
                "scale_vs_page": None,
            },
        }
        or policy["placement"]
        != (
            "fit source ink to the target ink bounds minus the calibrated optical inset, "
            "then draw the centre and four cardinal copies"
        )
        or policy["path_kind"] != "other"
    ):
        raise ValueError("HQ source policy semantics differ")
    for name in (
        "source_reported_size_ratio",
        "source_target_aspect_ratio",
    ):
        bounds = policy[name]
        if not hq.finite_list(bounds, 2) or bounds[0] <= 0 or bounds[0] > bounds[1]:
            raise ValueError(f"invalid HQ source policy: {name}")
    for name in (
        "minimum_scan_iou_1406",
        "maximum_audit_shift",
        "source_reported_center_delta_max",
        "minimum_fitted_fill",
    ):
        if not hq.finite_number(policy[name]) or policy[name] < 0:
            raise ValueError(f"invalid HQ source policy: {name}")
    if set(reviewed) != {"path", "sha256", "schema_version", "words", "pairs"}:
        raise ValueError("HQ reviewed-fallback fields differ")
    if (
        not isinstance(reviewed["path"], str)
        or not reviewed["path"]
        or not hq.valid_sha256(reviewed["sha256"])
        or reviewed["schema_version"] != 2
        or type(reviewed["words"]) is not int
        or reviewed["words"] < 0
        or type(reviewed["pairs"]) is not int
        or reviewed["pairs"] < 0
    ):
        raise ValueError("HQ reviewed-fallback identity differs")

    if set(optical) != {"path", "sha256", "schema_version"}:
        raise ValueError("HQ optical-calibration fields differ")
    if (
        not isinstance(optical["path"], str)
        or not optical["path"]
        or not hq.valid_sha256(optical["sha256"])
        or optical["schema_version"] != 1
    ):
        raise ValueError("HQ optical-calibration identity differs")

    if set(expected) != {
        "hq_words",
        "fallback_words",
        "pages_with_hq",
        "source_exclusions",
    }:
        raise ValueError("HQ expected fields differ")
    exclusions = expected["source_exclusions"]
    if (
        not all(
            type(expected[name]) is int and expected[name] >= 0
            for name in ("hq_words", "fallback_words", "pages_with_hq")
        )
        or expected["hq_words"] + expected["fallback_words"] != base["words"]
        or expected["pages_with_hq"] > base["pages"]
        or not isinstance(exclusions, dict)
        or not exclusions
        or any(
            not isinstance(name, str) or type(count) is not int or count < 0
            for name, count in exclusions.items()
        )
    ):
        raise ValueError("HQ expected result differs")
    if qualified is not None:
        if not isinstance(qualified, dict) or set(qualified) != {
            "pages_sha256",
            "qualified_geometry_pages_sha256",
            "index_sha256",
            "source_records_sha256",
        }:
            raise ValueError("HQ qualified-output fields differ")
        if not all(hq.valid_sha256(item) for item in qualified.values()):
            raise ValueError("HQ qualified-output digest differs")
    return base, candidate, policy, reviewed, optical, expected, qualified


def load_reviewed_fallbacks(
    manifest_path: Path,
    contract: dict,
    candidate: dict,
    base: dict,
) -> tuple[dict, dict[str, dict]]:
    path = manifest_path.parent / contract["path"]
    if not path.is_file() or hq.sha256(path) != contract["sha256"]:
        raise ValueError("HQ reviewed-fallback digest differs")
    value = hq.read_json(path)
    required = {
        "schema",
        "schema_version",
        "edition",
        "print_year_hijri",
        "qualification",
        "source_candidate_tree_sha256",
        "base_pages_sha256",
        "evidence",
        "words",
    }
    evidence = value.get("evidence") if isinstance(value, dict) else None
    words = value.get("words") if isinstance(value, dict) else None
    evidence_fields = {
        "visual_policy_sha256",
        "visual_review_sha256",
        "baseline_report_sha256",
        "pair_ablation_report_sha256",
        "sparse_variant_report_sha256",
        "sparse_variant_scan_sha256",
        "newly_eligible_after_base_sha256",
        "vertical_stretch_decision_sha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["schema"] != REVIEWED_FALLBACK_SCHEMA
        or value["schema_version"] != contract["schema_version"]
        or value["edition"] != "hafs-qcf-v1"
        or value["print_year_hijri"] != 1405
        or value["qualification"] != REVIEWED_FALLBACK_QUALIFICATION
        or value["source_candidate_tree_sha256"] != candidate["svg_fit_tree_sha256"]
        or value["base_pages_sha256"] != base["pages_sha256"]
        or not isinstance(evidence, dict)
        or set(evidence) != evidence_fields
        or not all(
            isinstance(name, str) and hq.valid_sha256(digest)
            for name, digest in evidence.items()
        )
        or not isinstance(words, list)
        or len(words) != contract["words"]
    ):
        raise ValueError("HQ reviewed-fallback ledger identity differs")

    records = {}
    order = []
    fields = {"page", "word_key", "text", "source_class", "source_path_sha256"}
    for record in words:
        if not isinstance(record, dict) or set(record) != fields:
            raise ValueError("HQ reviewed-fallback word fields differ")
        key = record["word_key"]
        try:
            numeric = hq.numeric_key(key)
        except (TypeError, ValueError) as error:
            raise ValueError("HQ reviewed-fallback word key differs") from error
        if (
            type(record["page"]) is not int
            or record["page"] < 1
            or not isinstance(record["text"], str)
            or not record["text"]
            or record["source_class"] not in {"direct", "pdf-recovered"}
            or not hq.valid_sha256(record["source_path_sha256"])
            or key in records
        ):
            raise ValueError("HQ reviewed-fallback word identity differs")
        records[key] = record
        order.append(numeric)
    if order != sorted(order):
        raise ValueError("HQ reviewed-fallback word order differs")
    return value, records


def load_optical_calibration(
    manifest_path: Path, contract: dict
) -> tuple[dict, list[float]]:
    path = manifest_path.parent / contract["path"]
    if not path.is_file() or hq.sha256(path) != contract["sha256"]:
        raise ValueError("HQ optical-calibration digest differs")
    value = hq.read_json(path)
    required = {
        "schema",
        "schema_version",
        "edition",
        "print_year_hijri",
        "calibration_input",
        "reference",
        "method",
        "radius",
        "pages",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("HQ optical-calibration fields differ")
    if (
        value["schema"] != OPTICAL_SCHEMA
        or value["schema_version"] != contract["schema_version"]
        or value["edition"] != "hafs-qcf-v1"
        or value["print_year_hijri"] != 1405
        or not isinstance(value["calibration_input"], dict)
        or not isinstance(value["reference"], dict)
        or not isinstance(value["method"], str)
        or not value["method"]
        or not isinstance(value["radius"], dict)
        or not isinstance(value["pages"], list)
        or len(value["pages"]) != 604
    ):
        raise ValueError("HQ optical-calibration identity differs")
    maximum = value["radius"].get("maximum")
    if not hq.finite_number(maximum) or maximum < 0:
        raise ValueError("HQ optical-calibration radius differs")
    radii = []
    for expected_page, row in enumerate(value["pages"], 1):
        if (
            not isinstance(row, dict)
            or set(row) != {"page", "radius", "reference_ink", "candidate_ink"}
            or row["page"] != expected_page
            or not hq.finite_number(row["radius"])
            or not 0 <= row["radius"] <= maximum
            or type(row["reference_ink"]) is not int
            or row["reference_ink"] <= 0
            or type(row["candidate_ink"]) is not int
            or row["candidate_ink"] <= 0
        ):
            raise ValueError(f"HQ optical-calibration page differs: {expected_page}")
        radii.append(row["radius"])
    return value, radii


def typed_owner_keys(root: ElementTree.Element) -> set[str]:
    owners = set()
    for group in root.findall(f'.//{SVG}g[@class="word"]'):
        if any(
            path.get("data-kind") not in {None, "", "other"}
            for path in group.findall(f".//{SVG}path")
        ):
            key = group.get("data-word-key")
            if not key:
                raise ValueError("typed path has no word owner")
            owners.add(key)
    return owners


def apply_source(group: ElementTree.Element, source: dict) -> None:
    if any(
        path.get("data-kind") not in {None, "", "other"}
        for path in group.findall(f".//{SVG}path")
    ):
        raise ValueError(
            f"HQ replacement would erase typed ownership: {source['word_key']}"
        )
    paths = group.findall(f"{SVG}path")
    if not paths or any(path not in list(group) for path in paths):
        raise ValueError(f"base word has nested or missing paths: {source['word_key']}")
    first = list(group).index(paths[0])
    for path in paths:
        group.remove(path)
    radius = source["optical_radius"]
    offsets = [(0.0, 0.0)]
    if radius:
        offsets.extend([(radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius)])
    for copy_index, (dx, dy) in enumerate(offsets):
        matrix = list(source["matrix"])
        matrix[4] += dx
        matrix[5] += dy
        path = ElementTree.Element(f"{SVG}path")
        path.set("data-kind", "other")
        path.set("data-source", "qpc-resize-hq")
        path.set("data-source-class", source["source_class"])
        path.set("data-source-fit-iou-1406", hq.number(source["scan_iou_1406"]))
        path.set("data-source-path-sha256", source["source_path_sha256"])
        path.set("data-optical-radius", hq.number(radius))
        path.set("data-optical-copy", str(copy_index))
        path.set("d", source["d"])
        path.set(
            "transform", f"matrix({' '.join(hq.number(value) for value in matrix)})"
        )
        if source["fill_rule"]:
            path.set("fill-rule", source["fill_rule"])
        group.insert(first + copy_index, path)
    group.set("data-vector-source", "qpc-resize-hq")


def build(
    base_dir: Path, candidate_dir: Path, manifest_path: Path, out_dir: Path
) -> dict:
    manifest = json.loads(manifest_path.read_text())
    (
        base,
        candidate,
        policy,
        reviewed_contract,
        optical_contract,
        expected,
        qualified_output,
    ) = validate_manifest(manifest)
    reviewed_ledger, reviewed_fallbacks = load_reviewed_fallbacks(
        manifest_path, reviewed_contract, candidate, base
    )
    optical_calibration, optical_radii = load_optical_calibration(
        manifest_path, optical_contract
    )
    base_summary, pages = hq.verify_base(base_dir, manifest, base)
    hq.verify_candidate(candidate_dir, pages, candidate)
    if out_dir.exists():
        raise ValueError(f"output exists: {out_dir}")
    temporary = out_dir.with_name(out_dir.name + ".tmp")
    if temporary.exists():
        raise ValueError(f"temporary output exists: {temporary}")
    (temporary / "pages").mkdir(parents=True)
    (temporary / "index/by-page").mkdir(parents=True)

    exclusions = Counter()
    reviewed_seen = set()
    records = []
    pages_with_hq = 0
    try:
        for page in pages:
            base_path = base_dir / "pages" / f"{page:03}.svg"
            candidate_path = candidate_dir / f"page{page:03}.svg"
            fit_path = candidate_dir / f"page{page:03}.fit.json"
            index_path = base_dir / "index/by-page" / f"{page:03}.json"
            root = ElementTree.parse(base_path).getroot()
            candidate_root = ElementTree.parse(candidate_path).getroot()
            if root.get("data-page") != str(page) or candidate_root.get(
                "data-page"
            ) != str(page):
                raise ValueError(f"page identity differs at {page}")
            groups = hq.word_groups(root)
            candidate_groups = hq.word_groups(candidate_root)
            words = hq.index_words(index_path)
            if set(groups) != set(words):
                raise ValueError(f"base SVG/index word coverage differs at page {page}")
            fit = hq.read_json(fit_path)
            fit_words = fit.get("words") if isinstance(fit, dict) else None
            if not isinstance(fit_words, dict):
                raise TypeError(f"candidate fit report differs at page {page}")
            semantic_owners = hq.semantic_owner_keys(root)
            typed_owners = typed_owner_keys(root)
            cache: dict[str, tuple[float, ...]] = {}
            replaced = 0
            for key, word in words.items():
                if key in semantic_owners:
                    exclusions["semantic-owner"] += 1
                    continue
                if key in typed_owners:
                    exclusions["typed-owner"] += 1
                    continue
                record = fit_words.get(key)
                candidate_group = candidate_groups.get(key)
                if record is None or candidate_group is None:
                    exclusions["candidate-missing"] += 1
                    continue
                source, reason = hq.qualify_candidate(
                    page,
                    key,
                    record,
                    word,
                    candidate_root,
                    candidate_group,
                    groups[key],
                    policy,
                    optical_radii[page - 1],
                    cache,
                )
                if source is None:
                    exclusions[reason] += 1
                    continue
                reviewed = reviewed_fallbacks.get(key)
                if reviewed is not None:
                    identity = {
                        "page": page,
                        "word_key": key,
                        "text": source["text"],
                        "source_class": source["source_class"],
                        "source_path_sha256": source["source_path_sha256"],
                    }
                    expected_identity = {name: reviewed[name] for name in identity}
                    if identity != expected_identity:
                        raise ValueError(
                            f"HQ reviewed-fallback source identity differs: {key}"
                        )
                    exclusions["reviewed-fallback"] += 1
                    reviewed_seen.add(key)
                    continue
                apply_source(groups[key], source)
                records.append(
                    {
                        "page": page,
                        "word_key": key,
                        "text": source["text"],
                        "source_class": source["source_class"],
                        "source_line_1406": source["source_line_1406"],
                        "target_line_1405": source["target_line_1405"],
                        "source_fit_iou_1406": source["scan_iou_1406"],
                        "source_path_sha256": source["source_path_sha256"],
                        "optical_radius": source["optical_radius"],
                        "optical_copies": source["optical_copies"],
                        "target_bounds": source["target_bounds"],
                        "final_bounds": source["final_bounds"],
                        "transform": [round(value, 9) for value in source["matrix"]],
                    }
                )
                replaced += 1
            page_data = hq.page_bytes(root) if replaced else base_path.read_bytes()
            (temporary / "pages" / f"{page:03}.svg").write_bytes(page_data)
            shutil.copyfile(index_path, temporary / "index/by-page" / f"{page:03}.json")
            pages_with_hq += replaced > 0

        if reviewed_seen != set(reviewed_fallbacks):
            raise ValueError("HQ reviewed-fallback coverage differs")

        page_paths = [temporary / "pages" / f"{page:03}.svg" for page in pages]
        index_paths = [
            temporary / "index/by-page" / f"{page:03}.json" for page in pages
        ]
        records.sort(key=lambda row: hq.numeric_key(row["word_key"]))
        record_data = b"".join(hq.json_bytes(row) for row in records)
        source_exclusions = dict(sorted(exclusions.items()))
        counts = {
            "pages": len(pages),
            "words": base["words"],
            "hq_words": len(records),
            "fallback_words": base["words"] - len(records),
            "pages_with_hq": pages_with_hq,
        }
        actual = {**counts, "source_exclusions": source_exclusions}
        wrong = {
            name: {"expected": value, "actual": actual.get(name)}
            for name, value in expected.items()
            if actual.get(name) != value
        }
        if wrong:
            raise ValueError(
                "HQ source-qualified result differs:\n" + json.dumps(wrong, indent=2)
            )
        digests = {
            "pages_sha256": hq.named_digest(page_paths),
            "qualified_geometry_pages_sha256": hq.named_transformed_digest(
                page_paths, hq.qualified_geometry_svg
            ),
            "index_sha256": hq.named_digest(index_paths),
            "source_records_sha256": hashlib.sha256(record_data).hexdigest(),
        }
        if qualified_output is not None and digests != qualified_output:
            raise ValueError(
                "qualified HQ output digest differs:\n"
                + json.dumps(
                    {"expected": qualified_output, "actual": digests}, indent=2
                )
            )

        record_path = temporary / "source-qualified.ndjson"
        record_path.write_bytes(record_data)
        summary = {
            "schema": "quran-svg-elements/qcf-v1-hq-word-corpus",
            "schema_version": 10,
            "edition": manifest["edition"],
            "print_year_hijri": manifest["print_year_hijri"],
            "qualification": "source-qualified",
            "pages": pages,
            "counts": counts,
            "coverage_percent": len(records) / base["words"] * 100,
            "base_summary_sha256": base["summary_sha256"],
            "base_pages_sha256": base["pages_sha256"],
            "base_qualified_geometry_pages_sha256": base[
                "qualified_geometry_pages_sha256"
            ],
            "base_header_qualified_geometry_pages_sha256": base[
                "header_qualified_geometry_pages_sha256"
            ],
            "base_path_geometry": base["path_geometry"],
            "base_index_sha256": base["index_sha256"],
            "base_waqf_source_glyphs_sha256": base["waqf_source_glyphs_sha256"],
            "waqf": base_summary["waqf"],
            "base_division_sajdah_source_sha256": base["division_sajdah_source_sha256"],
            "division_sajdah": base["division_sajdah"],
            "source_candidate_tree_sha256": candidate["svg_fit_tree_sha256"],
            "source_manifest_sha256": hq.sha256(manifest_path),
            "source_policy": policy,
            "reviewed_fallbacks_path": reviewed_contract["path"],
            "reviewed_fallbacks_sha256": reviewed_contract["sha256"],
            "reviewed_fallbacks": {
                "qualification": reviewed_ledger["qualification"],
                "words": reviewed_contract["words"],
                "pairs": reviewed_contract["pairs"],
            },
            "optical_calibration_path": optical_contract["path"],
            "optical_calibration_sha256": optical_contract["sha256"],
            "optical_calibration": optical_calibration,
            "source_exclusions": source_exclusions,
            "source_records_path": record_path.name,
            "source_records_bytes": len(record_data),
            **digests,
            "base_source_manifest_sha256": base_summary.get("source_manifest_sha256"),
        }
        (temporary / "summary.json").write_bytes(hq.json_bytes(summary, pretty=True))
        temporary.rename(out_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(json.dumps(summary, indent=2))
    return summary


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--base-dir", type=Path, required=True)
    command.add_argument("--candidate-dir", type=Path, required=True)
    command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    command.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return command


def main() -> None:
    args = parser().parse_args()
    build(args.base_dir, args.candidate_dir, args.manifest, args.out_dir)


if __name__ == "__main__":
    main()
