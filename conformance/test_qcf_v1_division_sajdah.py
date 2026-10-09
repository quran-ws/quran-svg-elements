#!/usr/bin/env python
"""Contracts for QCF V1 division boundaries and sajdah source ownership."""

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_qcf_v1_division_sajdah_source as source_builder
import build_qcf_v1_svg as qcf

SOURCE = ROOT / "conformance/qcf-v1-division-sajdah-source.json"
HQ_SOURCE = ROOT / "conformance/qcf-v1-hq-word-source.json"
MANIFEST = ROOT / "conformance/qcf-v1-vector-source.json"


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def semantics() -> qcf.DivisionSajdahSemantics:
    return qcf.DivisionSajdahSemantics(SOURCE, manifest())


def dummy_glyph(seed: int) -> dict:
    return {
        "box": [seed, seed, seed + 10, seed + 20],
        "codepoint": "U+FB51",
        "glyph_id": seed + 1,
    }


def synthetic_page(value: qcf.DivisionSajdahSemantics, page_number: int) -> dict:
    words = {}
    for record in value.divisions_by_page.get(page_number, []):
        source = record["source_glyph"]
        if source is None:
            glyphs = [dummy_glyph(record["rubu_al_hizb"] * 10)]
        else:
            glyphs = [copy.deepcopy(source), dummy_glyph(record["rubu_al_hizb"] * 10)]
        words[record["word_key"]] = {
            "word_key": record["word_key"],
            "line": record["line"],
            "text": {"rasm_uthmani": "word"},
            "glyphs": glyphs,
        }
    for number, record in enumerate(value.sajdahs_by_page.get(page_number, []), 1):
        source = record["source_glyph"]
        if record["source"] == "mapped-word":
            glyphs = [dummy_glyph(1000 + number), copy.deepcopy(source)]
        else:
            glyphs = [dummy_glyph(1000 + number)]
        words[record["word_key"]] = {
            "word_key": record["word_key"],
            "line": record["anchor_line"],
            "text": {"rasm_uthmani": "word۩"},
            "glyphs": glyphs,
        }
    return {
        "page": page_number,
        "words": list(words.values()),
        "shared_groups": [],
    }


def write_source(root: Path, value: dict) -> tuple[Path, dict]:
    path = root / "source.json"
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True))
    config = manifest()
    config["inputs"]["division_sajdah_source_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    return path, config


def semantic_page(page: int, decorations: list[dict]) -> dict:
    return {
        "schema": "quran-svg-elements/qcf-v1-mapping-page",
        "schema_version": "1.0.0",
        "edition": "hafs-qcf-v1",
        "page": page,
        "coordinate_space": [1920, 3106],
        "grid_lines": [],
        "words": [],
        "decorations": decorations,
        "deferred": [],
    }


def write_semantic_source(root: Path) -> None:
    page_digests = {}
    for page in range(1, 605):
        decorations = []
        if page <= 199:
            decorations.append(
                {
                    "kind": "rubu_al_hizb",
                    "word_key": f"2:{page}:1",
                    "ayah_key": f"2:{page}",
                    "line": 1,
                    "glyphs": [],
                }
            )
        if page <= 15:
            decorations.append(
                {
                    "kind": "sajdah",
                    "word_key": f"3:{page}:1",
                    "ayah_key": f"3:{page}",
                    "line": 2,
                    "glyphs": [],
                }
            )
        path = root / "pages" / f"{page:03}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(semantic_page(page, decorations), sort_keys=True))
        page_digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "quran-svg-elements/qcf-v1-mapping",
        "schema_version": "1.0.0",
        "edition": "hafs-qcf-v1",
        "status": "partial",
        "coordinate_space": [1920, 3106],
        "counts": source_builder.SEMANTIC_COUNTS,
        "source": {"source_manifest_sha256": "a" * 64},
        "pages": page_digests,
        "deferred_decisions": [],
        "normalizations": {},
        "pinned_next_phase": {},
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))


def test_source_builder_derives_and_verifies_external_identities():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        fonts = root / "fonts"
        fonts.mkdir()
        for page in range(1, 605):
            (fonts / f"QCF_P{page:03}.TTF").write_bytes(f"font-{page}".encode())
        expected = source_builder.tree_sha256(sorted(fonts.iterdir()))
        assert source_builder.page_font_tree_sha256(fonts) == expected
        (fonts / "QCF_P604.TTF").unlink()
        try:
            source_builder.page_font_tree_sha256(fonts)
        except ValueError as error:
            assert "font inventory differs" in str(error)
        else:
            raise AssertionError("accepted an incomplete page-font corpus")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_semantic_source(root)
        decorations, digest = source_builder.semantic_decorations(root)
        assert len(decorations["rubu_al_hizb"]) == 199
        assert len(decorations["sajdah"]) == 15
        assert digest == source_builder.tree_sha256(
            sorted((root / "pages").glob("[0-9][0-9][0-9].json"))
        )

        page = root / "pages/454.json"
        page.write_text(page.read_text() + "\n")
        try:
            source_builder.semantic_decorations(root)
        except ValueError as error:
            assert "page digests differ" in str(error)
        else:
            raise AssertionError("accepted semantic page drift")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_semantic_source(root)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["counts"]["sajdah_marks"] = 14
        manifest_path.write_text(json.dumps(manifest, sort_keys=True))
        try:
            source_builder.semantic_decorations(root)
        except ValueError as error:
            assert "identity differs" in str(error)
        else:
            raise AssertionError("accepted another semantic-source identity")


def test_committed_source_contract_is_complete():
    value = semantics()
    assert value.expected_counts == {
        "division_starts": 240,
        "mapped_sajdah_source_glyphs": 14,
        "printed_rubu_al_hizb": 199,
        "restored_sajdah_source_glyphs": 1,
        "sajdah_marks": 15,
        "unprinted_rubu_al_hizb": 41,
    }
    assert sum(map(len, value.divisions_by_page.values())) == 240
    assert sum(map(len, value.sajdahs_by_page.values())) == 15
    assert value.sha256 == manifest()["inputs"]["division_sajdah_source_sha256"]


def test_division_numbers_and_start_attributes_cover_the_complete_cycle():
    counts = Counter()
    for rubu_al_hizb in range(1, 241):
        values = qcf.division_values(rubu_al_hizb)
        assert values["rubu_al_hizb_in_hizb"] == (rubu_al_hizb - 1) % 4 + 1
        assert values["hizb"] == (rubu_al_hizb - 1) // 4 + 1
        assert values["juz"] == (rubu_al_hizb - 1) // 8 + 1
        attributes = qcf.boundary_attributes({"rubu_al_hizb": rubu_al_hizb})
        counts["rubu"] += 'data-rubu-al-hizb-start="' in attributes
        counts["hizb"] += 'data-hizb-start="' in attributes
        counts["nisf"] += 'data-nisf-start="' in attributes
        counts["juz"] += 'data-juz-start="' in attributes
    assert counts == {"rubu": 240, "hizb": 60, "nisf": 60, "juz": 30}


def test_page_454_restores_the_pinned_missing_sajdah_glyph():
    value = semantics()
    page = synthetic_page(value, 454)
    result = value.page(page)
    assert result["counts"]["restored_sajdah_source_glyphs"] == 1
    assert result["counts"]["sajdah_marks"] == 1
    assert result["sajdah_at_line_start"][12][0]["word_key"] == "38:24:32"
    assert result["restored_glyphs"] == [
        {
            "box": [1740, 2269, 1821, 2382],
            "codepoint": "U+FBEA",
            "glyph_id": 73659,
            "index": None,
            "word_glyph_count": 1,
        }
    ]

    changed = synthetic_page(value, 454)
    anchor = next(word for word in changed["words"] if word["word_key"] == "38:24:32")
    anchor["glyphs"].append(dummy_glyph(9000))
    try:
        value.page(changed)
    except ValueError as error:
        assert "restored sajdah anchor differs" in str(error)
    else:
        raise AssertionError("accepted a changed restored sajdah anchor")


def test_mapped_source_glyph_drift_fails_closed():
    value = semantics()
    page_number = next(
        record["page"]
        for records in value.sajdahs_by_page.values()
        for record in records
        if record["source"] == "mapped-word"
    )
    page = synthetic_page(value, page_number)
    result = value.page(page)
    assert result["counts"]["mapped_sajdah_source_glyphs"] >= 1
    record = next(
        record
        for record in value.sajdahs_by_page[page_number]
        if record["source"] == "mapped-word"
    )
    word = next(
        item for item in page["words"] if item["word_key"] == record["word_key"]
    )
    word["glyphs"][1]["glyph_id"] += 1
    try:
        value.page(page)
    except ValueError as error:
        assert "semantic source glyph drifted" in str(error)
    else:
        raise AssertionError("accepted changed mapped sajdah glyph ownership")


def test_ledger_digest_source_and_counts_fail_closed():
    source = json.loads(SOURCE.read_text())
    with TemporaryDirectory() as directory:
        root = Path(directory)
        changed = copy.deepcopy(source)
        changed["source"]["map_page_files_sha256"] = "0" * 64
        path, config = write_source(root, changed)
        try:
            qcf.DivisionSajdahSemantics(path, config)
        except ValueError as error:
            assert "source contract differs" in str(error)
        else:
            raise AssertionError("accepted a ledger for another map")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        changed = copy.deepcopy(source)
        changed["counts"]["printed_rubu_al_hizb"] -= 1
        path, config = write_source(root, changed)
        try:
            qcf.DivisionSajdahSemantics(path, config)
        except ValueError as error:
            assert "source counts differ" in str(error)
        else:
            raise AssertionError("accepted changed semantic counts")


def test_hq_source_contract_excludes_every_semantic_owner():
    value = json.loads(SOURCE.read_text())
    semantic_words = {
        record["word_key"]
        for record in value["divisions"]
        if record["source_glyph"] is not None
    }
    semantic_words.update(record["word_key"] for record in value["sajdahs"])
    hq = json.loads(HQ_SOURCE.read_text())
    assert len(semantic_words) == 214
    assert hq["expected"]["source_exclusions"]["semantic-owner"] == 214
    assert hq["expected"]["hq_words"] == 60739
    assert "selection" not in hq


def test_complete_output_counts_are_exact():
    value = semantics()
    counts = Counter(value.expected_counts)
    value.verify_complete(list(range(1, 605)), counts)
    counts["division_starts"] -= 1
    try:
        value.verify_complete(list(range(1, 605)), counts)
    except ValueError as error:
        assert "complete division/sajdah output counts differ" in str(error)
    else:
        raise AssertionError("accepted incomplete semantic output")


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
