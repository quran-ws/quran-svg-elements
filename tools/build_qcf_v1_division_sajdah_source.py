#!/usr/bin/env python
"""Build the compact QCF V1 division-boundary and sajdah ownership ledger."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "conformance/qcf-v1-division-sajdah-source.json"
RUBU_AL_HIZB = "۞"
SAJDAH = "۩"
SEMANTIC_MANIFEST_FIELDS = {
    "coordinate_space",
    "counts",
    "deferred_decisions",
    "edition",
    "normalizations",
    "pages",
    "pinned_next_phase",
    "schema",
    "schema_version",
    "source",
    "status",
}
SEMANTIC_PAGE_FIELDS = {
    "coordinate_space",
    "decorations",
    "deferred",
    "edition",
    "grid_lines",
    "page",
    "schema",
    "schema_version",
    "words",
}
SEMANTIC_COUNTS = {
    "ayah_marks": 6236,
    "ayahs": 6236,
    "canonical_words": 77432,
    "deferred_groups": 1,
    "deferred_words": 2,
    "glyphs": 88246,
    "mapped_words": 77430,
    "pages": 604,
    "qdc_line_differences": 81,
    "rubu_al_hizb_marks": 199,
    "sajdah_marks": 15,
    "source_type_anomalies": 1,
}


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


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


def codepoint(value: str) -> str:
    if len(value) != 1:
        raise ValueError(f"source glyph is not one codepoint: {value!r}")
    return f"U+{ord(value):04X}"


def numeric_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(":"))


def current_pages(root: Path) -> tuple[dict[int, dict], dict[str, tuple[dict, dict]]]:
    summary_path = root / "summary.json"
    summary = read_json(summary_path)
    paths = sorted((root / "pages").glob("[0-9][0-9][0-9].json"))
    if (
        not isinstance(summary, dict)
        or summary.get("schema") != "quran-svg-elements/qcf-v1-map"
        or summary.get("schema_version") != 3
        or len(paths) != 604
        or tree_sha256(paths) != summary.get("page_files_sha256")
    ):
        raise ValueError("current QCF V1 map identity differs")

    pages = {}
    words = {}
    for path in paths:
        page = read_json(path)
        number = int(path.stem)
        if page.get("page") != number:
            raise ValueError(f"current map page identity differs: {path.name}")
        pages[number] = page
        for word in page["words"]:
            key = word["word_key"]
            if key in words:
                raise ValueError(f"current map repeats word {key}")
            words[key] = (page, word)
        for group in page.get("shared_groups", []):
            for word in group["canonical_words"]:
                key = word["word_key"]
                if key in words:
                    raise ValueError(f"current map repeats word {key}")
                words[key] = (page, word | {"line": group["line"], "glyphs": []})
    return pages, words


def page_font_tree_sha256(root: Path) -> str:
    paths = sorted(root.glob("QCF_P[0-9][0-9][0-9].TTF"))
    names = [f"QCF_P{page:03}.TTF" for page in range(1, 605)]
    if [path.name for path in paths] != names:
        raise ValueError("page-font inventory differs")
    return tree_sha256(paths)


def semantic_decorations(root: Path) -> tuple[dict, str]:
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    paths = sorted((root / "pages").glob("[0-9][0-9][0-9].json"))
    names = [f"{page:03}.json" for page in range(1, 605)]
    if (
        not isinstance(manifest, dict)
        or set(manifest) != SEMANTIC_MANIFEST_FIELDS
        or manifest.get("schema") != "quran-svg-elements/qcf-v1-mapping"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("edition") != "hafs-qcf-v1"
        or manifest.get("status") != "partial"
        or manifest.get("coordinate_space") != [1920, 3106]
        or manifest.get("counts") != SEMANTIC_COUNTS
        or not isinstance(manifest.get("source"), dict)
        or not manifest["source"]
        or not all(
            isinstance(value, str)
            and len(value) == 64
            and set(value) <= set("0123456789abcdef")
            for value in manifest["source"].values()
        )
        or [path.name for path in paths] != names
    ):
        raise ValueError("semantic cross-check identity differs")

    page_digests = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    if manifest.get("pages") != page_digests:
        raise ValueError("semantic cross-check page digests differ")

    decorations = {"rubu_al_hizb": {}, "sajdah": {}}
    for number, path in enumerate(paths, 1):
        page = read_json(path)
        if (
            not isinstance(page, dict)
            or set(page) != SEMANTIC_PAGE_FIELDS
            or page.get("schema") != "quran-svg-elements/qcf-v1-mapping-page"
            or page.get("schema_version") != "1.0.0"
            or page.get("edition") != "hafs-qcf-v1"
            or page.get("page") != number
            or page.get("coordinate_space") != [1920, 3106]
            or not isinstance(page.get("decorations"), list)
        ):
            raise ValueError(f"semantic cross-check page identity differs: {path.name}")
        for record in page["decorations"]:
            kind = record.get("kind")
            if kind not in decorations:
                continue
            key = record.get("word_key")
            if not isinstance(key, str) or key in decorations[kind]:
                raise ValueError(f"semantic cross-check repeats {kind} {key}")
            decorations[kind][key] = record
    if len(decorations["rubu_al_hizb"]) != 199 or len(decorations["sajdah"]) != 15:
        raise ValueError("semantic cross-check counts differ")
    return decorations, tree_sha256(paths)


def glyph_record(glyph: dict, index: int, count: int) -> dict:
    return {
        "box": glyph["box"],
        "codepoint": glyph["codepoint"],
        "glyph_id": glyph["glyph_id"],
        "index": index,
        "word_glyph_count": count,
    }


def verify_old_glyph(record: dict, glyph: dict) -> None:
    old = record.get("glyphs")
    if (
        not isinstance(old, list)
        or len(old) != 1
        or old[0].get("glyph_id") != glyph.get("glyph_id")
        or old[0].get("frame") != glyph.get("box")
    ):
        raise ValueError(
            f"semantic source glyph differs for {record.get('kind')} {record.get('word_key')}"
        )


def build(args: argparse.Namespace) -> dict:
    pages, words = current_pages(args.map_dir)
    decorations, semantic_pages_sha256 = semantic_decorations(args.semantic_map_dir)
    font_tree_sha256 = page_font_tree_sha256(args.fonts_dir)
    starts_path = args.division_starts
    starts = read_json(starts_path)
    if not isinstance(starts, dict) or set(starts) != {
        str(index) for index in range(1, 241)
    }:
        raise ValueError("division-start inventory differs")

    printed = decorations["rubu_al_hizb"]
    divisions = []
    used_printed = set()
    for index in range(1, 241):
        value = starts[str(index)]
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(number, int) and number > 0 for number in value)
        ):
            raise ValueError(f"invalid division start {index}")
        ayah_key = f"{value[0]}:{value[1]}"
        word_key = f"{ayah_key}:1"
        if word_key not in words:
            raise ValueError(f"division start has no first word: {word_key}")
        page, word = words[word_key]
        source_glyph = None
        semantic = printed.get(word_key)
        if semantic is not None:
            glyphs = word.get("glyphs", [])
            if (
                len(glyphs) != 2
                or semantic.get("ayah_key") != ayah_key
                or semantic.get("line") != word["line"]
            ):
                raise ValueError(f"invalid printed rubu-al-hizb ownership: {word_key}")
            verify_old_glyph(semantic, glyphs[0])
            source_glyph = glyph_record(glyphs[0], 0, len(glyphs))
            used_printed.add(word_key)
        divisions.append(
            {
                "ayah_key": ayah_key,
                "line": word["line"],
                "page": page["page"],
                "rubu_al_hizb": index,
                "source_glyph": source_glyph,
                "word_key": word_key,
            }
        )
    if used_printed != set(printed):
        raise ValueError(
            "printed rubu-al-hizb records are not exactly the division starts"
        )

    sajdahs = []
    used_sajdah = set()
    for word_key, semantic in sorted(
        decorations["sajdah"].items(), key=lambda item: numeric_key(item[0])
    ):
        if word_key not in words:
            raise ValueError(f"sajdah anchor has no current word: {word_key}")
        page, word = words[word_key]
        if SAJDAH not in word["text"]["rasm_uthmani"]:
            raise ValueError(f"sajdah anchor lacks its canonical sign: {word_key}")
        old_glyph = semantic["glyphs"][0]
        source = "mapped-word"
        glyphs = word.get("glyphs", [])
        index = len(glyphs) - 1
        if (
            glyphs
            and old_glyph.get("glyph_id") == glyphs[index].get("glyph_id")
            and old_glyph.get("frame") == glyphs[index].get("box")
        ):
            source_glyph = glyph_record(glyphs[index], index, len(glyphs))
        else:
            if word_key != "38:24:32" or len(glyphs) != 1:
                raise ValueError(f"unexplained missing sajdah source glyph: {word_key}")
            source = "restored-semantic-source"
            source_glyph = {
                "box": old_glyph["frame"],
                "codepoint": codepoint(old_glyph["code_v1"]),
                "glyph_id": old_glyph["glyph_id"],
                "index": None,
                "word_glyph_count": len(glyphs),
            }
        sajdahs.append(
            {
                "anchor_line": word["line"],
                "ayah_key": semantic["ayah_key"],
                "line": semantic["line"],
                "page": page["page"],
                "source": source,
                "source_glyph": source_glyph,
                "word_key": word_key,
            }
        )
        used_sajdah.add(word_key)

    canonical_rubu = {
        word["word_key"]
        for page in pages.values()
        for word in page["words"]
        if RUBU_AL_HIZB in word["text"]["rasm_uthmani"]
    }
    canonical_sajdah = {
        word["word_key"]
        for page in pages.values()
        for word in page["words"]
        if SAJDAH in word["text"]["rasm_uthmani"]
    }
    shared_signs = [
        word["word_key"]
        for page in pages.values()
        for group in page.get("shared_groups", [])
        for word in group["canonical_words"]
        if RUBU_AL_HIZB in word["text"]["rasm_uthmani"]
        or SAJDAH in word["text"]["rasm_uthmani"]
    ]
    if canonical_rubu or canonical_sajdah != used_sajdah or shared_signs:
        raise ValueError("canonical semantic-sign ownership differs")

    counts = {
        "division_starts": len(divisions),
        "mapped_sajdah_source_glyphs": sum(
            record["source"] == "mapped-word" for record in sajdahs
        ),
        "printed_rubu_al_hizb": len(used_printed),
        "restored_sajdah_source_glyphs": sum(
            record["source"] == "restored-semantic-source" for record in sajdahs
        ),
        "sajdah_marks": len(sajdahs),
        "unprinted_rubu_al_hizb": len(divisions) - len(used_printed),
    }
    expected = {
        "division_starts": 240,
        "mapped_sajdah_source_glyphs": 14,
        "printed_rubu_al_hizb": 199,
        "restored_sajdah_source_glyphs": 1,
        "sajdah_marks": 15,
        "unprinted_rubu_al_hizb": 41,
    }
    if counts != expected:
        raise ValueError(f"semantic source counts differ: {counts}")

    map_summary = read_json(args.map_dir / "summary.json")
    value = {
        "counts": counts,
        "divisions": divisions,
        "edition": "hafs-qcf-v1",
        "sajdahs": sajdahs,
        "schema": "quran-svg-elements/qcf-v1-division-sajdah-source",
        "schema_version": 1,
        "source": {
            "division_starts_sha256": sha256(starts_path),
            "map_page_files_sha256": map_summary["page_files_sha256"],
            "page_font_tree_sha256": font_tree_sha256,
            "semantic_manifest_sha256": sha256(args.semantic_map_dir / "manifest.json"),
            "semantic_page_files_sha256": semantic_pages_sha256,
        },
    }
    data = json_bytes(value)
    if args.out.exists():
        raise ValueError(f"output already exists: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--map-dir", type=Path, required=True)
    command.add_argument("--semantic-map-dir", type=Path, required=True)
    command.add_argument("--division-starts", type=Path, required=True)
    command.add_argument("--fonts-dir", type=Path, required=True)
    command.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return command


def main() -> None:
    args = parser().parse_args()
    for name in ("map_dir", "semantic_map_dir", "division_starts", "fonts_dir", "out"):
        setattr(args, name, getattr(args, name).resolve())
    build(args)


if __name__ == "__main__":
    main()
