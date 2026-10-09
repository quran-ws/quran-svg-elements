#!/usr/bin/env python
"""Contracts for the source-qualified QCF V1 HQ word overlay."""

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE = ROOT / "tools/build_qcf_v1_hq_word_overlay.py"
spec = importlib.util.spec_from_file_location("qcf_hq_overlay", MODULE)
qcf = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qcf
spec.loader.exec_module(qcf)

BASE_D = "M0 0H10V10H0Z"
HQ_D = "M0 0H9V10H0Z"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def word_key(page: int) -> str:
    return f"1:{page}:1"


def word_text(page: int) -> str:
    return f"word-{page}"


def base_page(page: int) -> bytes:
    key = word_key(page)
    kind = (
        'data-kind="mark" data-mark="waqf_lazim" data-mark-family="waqf"'
        if page == 4
        else 'data-kind="other"'
    )
    division = (
        f'<g class="division-mark" data-word-key="{key}">'
        f'<path data-kind="mark" data-mark="hizb" d="{BASE_D}" '
        'transform="matrix(1 0 0 -1 180 210)"/></g>'
        if page == 5
        else ""
    )
    return (
        f'<svg xmlns="{qcf.hq.SVG_NAMESPACE}" viewBox="0 0 345 558.1094" '
        f'data-page="{page}"><g class="line" data-line="1">'
        f'<g class="ayah-fragment" data-ayah-key="1:{page}">'
        f'<g class="word" data-word-key="{key}" data-rasm-uthmani="{word_text(page)}">'
        f'<path {kind} d="{BASE_D}" transform="matrix(1 0 0 -1 200 210)"/>'
        f"</g>{division}</g></g></svg>\n"
    ).encode()


def candidate_page(page: int) -> bytes:
    text = "different" if page == 6 else word_text(page)
    recovered = (
        ' data-resolved-from-shape="recovered:' + "a" * 64 + '"' if page == 7 else ""
    )
    return (
        f'<svg xmlns="{qcf.hq.SVG_NAMESPACE}" viewBox="0 0 345 558.1094" '
        f'data-page="{page}"><g class="line" data-line="1">'
        f'<g class="word" data-word-key="{word_key(page)}" '
        f'data-rasm-uthmani="{text}"{recovered}><path data-kind="other" d="{HQ_D}" '
        'transform="matrix(1 0 0 -1 200 210)"/></g></g></svg>\n'
    ).encode()


def fit_record(page: int) -> dict:
    recovered = page == 7
    return {
        "text": word_text(page),
        "line": 2 if page == 8 else 1,
        "flags": (
            ["print-resolved", "pdf-recovered"]
            if recovered
            else (["review"] if page >= 10 else [])
        ),
        "audit": None
        if recovered
        else {"shift": 0.0, "gain": 0.0, "scale_locked": True},
        "substituted": None,
        "contours": [],
        "iou": 0.39 if page == 9 else 0.8,
        "scale_vs_page": None if recovered else 1.0,
        "bbox_svg": [200.0, 200.0, 9.0, 10.0],
        **({"resolved_from_shape": "recovered:" + "a" * 64} if recovered else {}),
    }


def fixture(root: Path) -> argparse.Namespace:
    base = root / "base"
    candidate = root / "candidate"
    page_paths = []
    index_paths = []
    for page in range(1, 605):
        page_path = base / "pages" / f"{page:03}.svg"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(base_page(page))
        page_paths.append(page_path)
        index_path = base / "index/by-page" / f"{page:03}.json"
        write_json(
            index_path,
            {
                "page": page,
                "words": [
                    {
                        "word_key": word_key(page),
                        "line": 1,
                        "rasm_uthmani": word_text(page),
                        "box": [200, 200, 210, 210],
                    }
                ],
            },
        )
        index_paths.append(index_path)
        (candidate / f"page{page:03}.svg").parent.mkdir(parents=True, exist_ok=True)
        (candidate / f"page{page:03}.svg").write_bytes(candidate_page(page))
        write_json(
            candidate / f"page{page:03}.fit.json",
            {"words": {word_key(page): fit_record(page)}},
        )

    pages_sha256 = qcf.hq.named_digest(page_paths)
    qualified_geometry_pages_sha256 = qcf.hq.named_transformed_digest(
        page_paths, qcf.hq.qualified_geometry_svg
    )
    emitted_pages_sha256 = qcf.hq.named_path_geometry_digest(page_paths)
    emitted_paths = sum(
        len(ElementTree.parse(path).getroot().findall(f".//{qcf.SVG}path"))
        for path in page_paths
    )
    index_sha256 = qcf.hq.named_digest(index_paths)
    path_geometry = {
        "qualification": "base-order-preserved",
        "base_paths": emitted_paths - 1,
        "emitted_paths": emitted_paths,
        "restored_paths": 1,
        "base_pages_sha256": "5" * 64,
        "emitted_pages_sha256": emitted_pages_sha256,
    }
    waqf = {
        "qualification": "source-glyph-qualified",
        "text_signs": 4272,
        "separate_source_glyphs": 4221,
        "fused_source_glyphs": 51,
    }
    division_sajdah = {
        "qualification": "source-owned",
        **qcf.hq.DIVISION_SAJDAH_COUNTS,
    }
    summary_path = base / "summary.json"
    write_json(
        summary_path,
        {
            "schema": "quran-svg-elements/qcf-v1-vector-slice",
            "schema_version": 5,
            "edition": "hafs-qcf-v1",
            "print_year_hijri": 1405,
            "pages": list(range(1, 605)),
            "counts": {
                "pages": 604,
                "words": 77432,
                **qcf.hq.DIVISION_SAJDAH_COUNTS,
            },
            "pages_sha256": pages_sha256,
            "qualified_geometry_pages_sha256": qualified_geometry_pages_sha256,
            "header_qualified_geometry_pages_sha256": qualified_geometry_pages_sha256,
            "path_geometry": path_geometry,
            "index_sha256": index_sha256,
            "header_placement": {"qualification": "mechanically-qualified"},
            "source_manifest_sha256": "1" * 64,
            "waqf_source_glyphs_sha256": "4" * 64,
            "waqf": waqf,
            "division_sajdah_source_sha256": "7" * 64,
        },
    )
    candidate_digest, candidate_files = qcf.hq.candidate_digest(
        candidate, list(range(1, 605))
    )
    optical_path = root / "optical.json"
    write_json(
        optical_path,
        {
            "schema": qcf.OPTICAL_SCHEMA,
            "schema_version": 1,
            "edition": "hafs-qcf-v1",
            "print_year_hijri": 1405,
            "calibration_input": {"qualification": "fixture"},
            "reference": {"qualification": "fixture"},
            "method": "fixture cardinal-copy optical calibration",
            "radius": {"units": "QVP page units", "maximum": 0.24},
            "pages": [
                {
                    "page": page,
                    "radius": 0.1,
                    "reference_ink": 100,
                    "candidate_ink": 100,
                }
                for page in range(1, 605)
            ],
        },
    )
    reviewed_path = root / "reviewed.json"
    write_json(
        reviewed_path,
        {
            "schema": qcf.REVIEWED_FALLBACK_SCHEMA,
            "schema_version": 2,
            "edition": "hafs-qcf-v1",
            "print_year_hijri": 1405,
            "qualification": qcf.REVIEWED_FALLBACK_QUALIFICATION,
            "source_candidate_tree_sha256": candidate_digest,
            "base_pages_sha256": pages_sha256,
            "evidence": {
                "visual_policy_sha256": "1" * 64,
                "visual_review_sha256": "2" * 64,
                "baseline_report_sha256": "3" * 64,
                "pair_ablation_report_sha256": "4" * 64,
                "sparse_variant_report_sha256": "5" * 64,
                "sparse_variant_scan_sha256": "6" * 64,
                "newly_eligible_after_base_sha256": "7" * 64,
                "vertical_stretch_decision_sha256": "8" * 64,
            },
            "words": [],
        },
    )
    manifest_path = root / "manifest.json"
    write_json(
        manifest_path,
        {
            "schema": "quran-svg-elements/qcf-v1-hq-word-source",
            "schema_version": 7,
            "edition": "hafs-qcf-v1",
            "print_year_hijri": 1405,
            "base": {
                "summary_sha256": qcf.hq.sha256(summary_path),
                "summary_schema": "quran-svg-elements/qcf-v1-vector-slice",
                "summary_schema_version": 5,
                "pages_sha256": pages_sha256,
                "qualified_geometry_pages_sha256": qualified_geometry_pages_sha256,
                "header_qualified_geometry_pages_sha256": qualified_geometry_pages_sha256,
                "path_geometry": path_geometry,
                "index_sha256": index_sha256,
                "pages": 604,
                "words": 77432,
                "header_qualification": "mechanically-qualified",
                "waqf_source_glyphs_sha256": "4" * 64,
                "waqf": waqf,
                "division_sajdah_source_sha256": "7" * 64,
                "division_sajdah": division_sajdah,
            },
            "candidate": {
                "source": "fixture source",
                "source_print_year_hijri": 1406,
                "target_print_year_hijri": 1405,
                "svg_fit_tree_sha256": candidate_digest,
                "files": candidate_files,
                "pages": 604,
                "positions_with_vector": 77374,
            },
            "source_policy": {
                "exclude_pages": [1, 2],
                "exclude_word_keys": ["13:37:8", "13:37:9"],
                "text_identity": (
                    "NFC equality across the base index, base SVG, candidate SVG, "
                    "and fit report"
                ),
                "required_path_count": 1,
                "source_classes": {
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
                },
                "maximum_audit_shift": 0.4,
                "minimum_scan_iou_1406": 0.4,
                "source_reported_center_delta_max": 0.75,
                "source_reported_size_ratio": [0.95, 1.05],
                "source_target_aspect_ratio": [0.85, 1.15],
                "minimum_fitted_fill": 0.85,
                "placement": (
                    "fit source ink to the target ink bounds minus the calibrated optical "
                    "inset, then draw the centre and four cardinal copies"
                ),
                "path_kind": "other",
            },
            "reviewed_fallbacks": {
                "path": reviewed_path.name,
                "sha256": qcf.hq.sha256(reviewed_path),
                "schema_version": 2,
                "words": 0,
                "pairs": 0,
            },
            "optical_calibration": {
                "path": optical_path.name,
                "sha256": qcf.hq.sha256(optical_path),
                "schema_version": 1,
            },
            "expected": {
                "hq_words": 3,
                "fallback_words": 77429,
                "pages_with_hq": 3,
                "source_exclusions": {
                    "excluded-page": 2,
                    "scan-iou": 1,
                    "semantic-owner": 1,
                    "text-differs": 1,
                    "typed-owner": 1,
                    "unsupported-source": 595,
                },
            },
            "qualified_output": None,
        },
    )
    return argparse.Namespace(
        base_dir=base,
        candidate_dir=candidate,
        manifest=manifest_path,
        out_dir=root / "output",
    )


def build(args: argparse.Namespace) -> dict:
    with redirect_stdout(StringIO()):
        return qcf.build(args.base_dir, args.candidate_dir, args.manifest, args.out_dir)


def rewrite_manifest(args: argparse.Namespace, change) -> None:
    value = json.loads(args.manifest.read_text())
    change(value)
    write_json(args.manifest, value)


def rewrite_reviewed(
    args: argparse.Namespace, words: list[dict], pairs: int | None = None
) -> None:
    manifest = json.loads(args.manifest.read_text())
    path = args.manifest.parent / manifest["reviewed_fallbacks"]["path"]
    value = json.loads(path.read_text())
    value["words"] = words
    write_json(path, value)
    manifest["reviewed_fallbacks"].update(
        {
            "sha256": qcf.hq.sha256(path),
            "words": len(words),
            "pairs": len(words) if pairs is None else pairs,
        }
    )
    write_json(args.manifest, manifest)


def reviewed_word(page: int = 3) -> dict:
    key = word_key(page)
    return {
        "page": page,
        "word_key": key,
        "text": word_text(page),
        "source_class": "direct",
        "source_path_sha256": hashlib.sha256(HQ_D.encode()).hexdigest(),
    }


def assert_no_output(args: argparse.Namespace) -> None:
    assert not args.out_dir.exists()
    assert not args.out_dir.with_name(args.out_dir.name + ".tmp").exists()


def test_committed_manifest_pins_reviewed_source_coverage():
    manifest = json.loads(qcf.DEFAULT_MANIFEST.read_text())
    qcf.validate_manifest(manifest)
    expected = manifest["expected"]
    assert expected["hq_words"] == 60739
    assert expected["fallback_words"] == 16693
    assert expected["pages_with_hq"] == 602
    assert expected["source_exclusions"] == qcf.EXPECTED_EXCLUSIONS
    assert expected["hq_words"] / 77432 * 100 == 78.44172951751214
    assert manifest["reviewed_fallbacks"] == {
        "path": "qcf-v1-hq-reviewed-fallbacks.json",
        "sha256": qcf.hq.sha256(ROOT / "conformance/qcf-v1-hq-reviewed-fallbacks.json"),
        "schema_version": 2,
        "words": 62,
        "pairs": 48,
    }
    ledger = json.loads(
        (ROOT / "conformance/qcf-v1-hq-reviewed-fallbacks.json").read_text()
    )
    assert ledger["schema_version"] == 2
    assert ledger["evidence"]["vertical_stretch_decision_sha256"] == (
        "02a894516573331962def9fc4373afb1edb4367ca8cba1f47e056e1cd8e7c866"
    )
    assert {
        "2:15:2",
        "2:85:9",
        "7:186:4",
        "9:43:4",
        "12:21:13",
        "12:40:17",
        "22:18:5",
        "22:18:6",
        "30:19:9",
        "39:71:29",
        "84:21:5",
    } <= {row["word_key"] for row in ledger["words"]}
    assert "selection" not in manifest
    assert "target_scan" not in json.dumps(manifest)


def test_build_uses_every_safe_source_and_preserves_semantic_owners():
    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        base_pages = {
            page: (args.base_dir / "pages" / f"{page:03}.svg").read_bytes()
            for page in (1, 2, 4, 5, 6, 9, 10)
        }
        report = build(args)
        assert report["schema_version"] == 10
        assert report["qualification"] == "source-qualified"
        assert report["counts"] == {
            "pages": 604,
            "words": 77432,
            "hq_words": 3,
            "fallback_words": 77429,
            "pages_with_hq": 3,
        }
        assert report["source_exclusions"] == {
            "excluded-page": 2,
            "scan-iou": 1,
            "semantic-owner": 1,
            "text-differs": 1,
            "typed-owner": 1,
            "unsupported-source": 595,
        }
        for page, original in base_pages.items():
            assert (args.out_dir / "pages" / f"{page:03}.svg").read_bytes() == original
        page = ElementTree.parse(args.out_dir / "pages/003.svg").getroot()
        paths = page.findall(f'.//{qcf.SVG}path[@data-source="qpc-resize-hq"]')
        assert len(paths) == 5
        assert {path.get("d") for path in paths} == {HQ_D}
        assert [path.get("data-optical-copy") for path in paths] == [
            "0",
            "1",
            "2",
            "3",
            "4",
        ]
        assert {path.get("data-optical-radius") for path in paths} == {"0.1"}
        assert page.find(f'.//{qcf.SVG}path[@data-mark-family="waqf"]') is None
        page4 = ElementTree.parse(args.out_dir / "pages/004.svg").getroot()
        assert page4.find(f'.//{qcf.SVG}path[@data-mark-family="waqf"]') is not None
        page5 = ElementTree.parse(args.out_dir / "pages/005.svg").getroot()
        assert page5.find(f'.//{qcf.SVG}g[@class="division-mark"]') is not None
        records = [
            json.loads(line)
            for line in (args.out_dir / "source-qualified.ndjson")
            .read_text()
            .splitlines()
        ]
        assert len(records) == 3
        assert all("d" not in record for record in records)
        assert [record["word_key"] for record in records] == [
            word_key(3),
            word_key(7),
            word_key(8),
        ]
        assert [record["source_class"] for record in records] == [
            "direct",
            "pdf-recovered",
            "direct",
        ]
        assert records[1]["source_line_1406"] == records[1]["target_line_1405"] == 1
        assert records[2]["source_line_1406"] == 2
        assert records[2]["target_line_1405"] == 1
        assert {record["optical_radius"] for record in records} == {0.1}
        assert {record["optical_copies"] for record in records} == {5}
        final = qcf.hq.union_boxes(
            [qcf.hq.transformed_bounds(path, {}) for path in paths]
        )
        assert [round(value, 6) for value in final] == [200.0, 200.0, 210.0, 210.0]


def test_reviewed_fallbacks_are_exact_and_source_bound():
    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        rewrite_reviewed(args, [reviewed_word()])
        manifest = json.loads(args.manifest.read_text())
        manifest["expected"].update(
            {
                "hq_words": 2,
                "fallback_words": 77430,
                "pages_with_hq": 2,
            }
        )
        manifest["expected"]["source_exclusions"]["reviewed-fallback"] = 1
        write_json(args.manifest, manifest)
        report = build(args)
        assert report["counts"]["hq_words"] == 2
        assert report["source_exclusions"]["reviewed-fallback"] == 1
        assert report["reviewed_fallbacks"] == {
            "qualification": qcf.REVIEWED_FALLBACK_QUALIFICATION,
            "words": 1,
            "pairs": 1,
        }
        assert (args.out_dir / "pages/003.svg").read_bytes() == base_page(3)
        records = [
            json.loads(line)
            for line in (args.out_dir / "source-qualified.ndjson")
            .read_text()
            .splitlines()
        ]
        assert [record["word_key"] for record in records] == [word_key(7), word_key(8)]

    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        word = reviewed_word()
        word["source_path_sha256"] = "0" * 64
        rewrite_reviewed(args, [word])
        manifest = json.loads(args.manifest.read_text())
        manifest["expected"].update(
            {
                "hq_words": 2,
                "fallback_words": 77430,
                "pages_with_hq": 2,
            }
        )
        manifest["expected"]["source_exclusions"]["reviewed-fallback"] = 1
        write_json(args.manifest, manifest)
        try:
            build(args)
        except ValueError as error:
            assert "reviewed-fallback source identity differs" in str(error)
        else:
            raise AssertionError("accepted a reviewed fallback for another source path")
        assert_no_output(args)


def test_candidate_tree_and_output_pins_fail_closed():
    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        manifest = json.loads(args.manifest.read_text())
        path = args.manifest.parent / manifest["optical_calibration"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        try:
            build(args)
        except ValueError as error:
            assert "optical-calibration digest differs" in str(error)
        else:
            raise AssertionError("accepted changed optical calibration")
        assert_no_output(args)

    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        path = args.candidate_dir / "page003.svg"
        path.write_bytes(path.read_bytes() + b" ")
        try:
            build(args)
        except ValueError as error:
            assert "candidate tree digest differs" in str(error)
        else:
            raise AssertionError("accepted changed candidate artwork")
        assert_no_output(args)

    with TemporaryDirectory() as directory:
        args = fixture(Path(directory))
        first = build(args)
        qualified = {
            name: first[name]
            for name in (
                "pages_sha256",
                "qualified_geometry_pages_sha256",
                "index_sha256",
                "source_records_sha256",
            )
        }
        shutil.rmtree(args.out_dir)
        rewrite_manifest(
            args, lambda value: value.update({"qualified_output": qualified})
        )
        second = build(args)
        assert second["pages_sha256"] == first["pages_sha256"]
        shutil.rmtree(args.out_dir)
        rewrite_manifest(
            args,
            lambda value: value["qualified_output"].update({"pages_sha256": "0" * 64}),
        )
        try:
            build(args)
        except ValueError as error:
            assert "qualified HQ output digest differs" in str(error)
        else:
            raise AssertionError("accepted changed qualified output")
        assert_no_output(args)


def test_manifest_and_cli_have_no_target_scan_gate():
    manifest = json.loads(qcf.DEFAULT_MANIFEST.read_text())
    for change, message in (
        (lambda value: value.update({"selection": {}}), "manifest fields differ"),
        (
            lambda value: value["expected"].update({"hq_words": 64}),
            "expected result differs",
        ),
        (
            lambda value: value["source_policy"].update({"minimum_scan_iou_1406": -1}),
            "invalid HQ source policy",
        ),
    ):
        changed = copy.deepcopy(manifest)
        change(changed)
        try:
            qcf.validate_manifest(changed)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError("accepted stale scan-gated manifest")
    args = qcf.parser().parse_args(
        ["--base-dir", "/tmp/base", "--candidate-dir", "/tmp/candidate"]
    )
    for name in (
        "reference_dir",
        "minimum_f1_delta",
        "selection",
        "replacements",
        "quality",
    ):
        assert not hasattr(args, name)


if __name__ == "__main__":
    tests = sorted(
        (name, function)
        for name, function in globals().items()
        if name.startswith("test_") and callable(function)
    )
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
