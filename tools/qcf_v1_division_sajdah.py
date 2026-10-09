"""Pinned QCF V1 division-boundary and sajdah ownership semantics."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_codepoint(value: str) -> int:
    if not isinstance(value, str) or not value.startswith("U+"):
        raise ValueError(f"invalid codepoint: {value!r}")
    return int(value.replace("U+", "0x"), 0)


class DivisionSajdahSemantics:
    SOURCE_FIELDS = frozenset(
        {
            "division_starts_sha256",
            "map_page_files_sha256",
            "page_font_tree_sha256",
            "semantic_manifest_sha256",
            "semantic_page_files_sha256",
        }
    )
    COUNT_FIELDS = frozenset(
        {
            "division_starts",
            "mapped_sajdah_source_glyphs",
            "printed_rubu_al_hizb",
            "restored_sajdah_source_glyphs",
            "sajdah_marks",
            "unprinted_rubu_al_hizb",
        }
    )

    def __init__(self, path: Path, manifest: dict):
        self.sha256 = _sha256(path)
        if self.sha256 != manifest["inputs"].get("division_sajdah_source_sha256"):
            raise ValueError("division/sajdah source digest differs")
        value = _read_json(path)
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "counts",
                "divisions",
                "edition",
                "sajdahs",
                "schema",
                "schema_version",
                "source",
            }
            or value["schema"] != "quran-svg-elements/qcf-v1-division-sajdah-source"
            or value["schema_version"] != 1
            or value["edition"] != manifest["edition"]
        ):
            raise ValueError("division/sajdah source identity differs")
        source = value["source"]
        counts = value["counts"]
        if (
            not isinstance(source, dict)
            or set(source) != self.SOURCE_FIELDS
            or not isinstance(counts, dict)
            or set(counts) != self.COUNT_FIELDS
            or any(
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                for digest in source.values()
            )
            or source["map_page_files_sha256"]
            != manifest["inputs"].get("map_page_files_sha256")
            or source["page_font_tree_sha256"]
            != manifest["inputs"].get("page_font_tree_sha256")
            or any(not isinstance(count, int) or count < 0 for count in counts.values())
        ):
            raise ValueError("division/sajdah source contract differs")

        divisions = value["divisions"]
        sajdahs = value["sajdahs"]
        if not isinstance(divisions, list) or not isinstance(sajdahs, list):
            raise TypeError("division/sajdah source inventories must be arrays")
        self.divisions_by_page = defaultdict(list)
        self.sajdahs_by_page = defaultdict(list)
        seen_ayahs = set()
        seen_words = set()
        printed = 0
        for expected, record in enumerate(divisions, 1):
            if (
                not isinstance(record, dict)
                or set(record)
                != {
                    "ayah_key",
                    "line",
                    "page",
                    "rubu_al_hizb",
                    "source_glyph",
                    "word_key",
                }
                or record["rubu_al_hizb"] != expected
                or record["word_key"] != f"{record['ayah_key']}:1"
                or record["ayah_key"] in seen_ayahs
                or record["word_key"] in seen_words
                or not all(
                    isinstance(record[name], int) and record[name] > 0
                    for name in ("page", "line")
                )
            ):
                raise ValueError("division source inventory differs")
            glyph = record["source_glyph"]
            if glyph is not None:
                self._verify_glyph(glyph)
                if glyph["index"] != 0 or glyph["word_glyph_count"] != 2:
                    raise ValueError("printed rubu-al-hizb source glyph differs")
                printed += 1
            seen_ayahs.add(record["ayah_key"])
            seen_words.add(record["word_key"])
            self.divisions_by_page[record["page"]].append(record)

        mapped = 0
        restored = 0
        seen_sajdahs = set()
        for record in sajdahs:
            if (
                not isinstance(record, dict)
                or set(record)
                != {
                    "anchor_line",
                    "ayah_key",
                    "line",
                    "page",
                    "source",
                    "source_glyph",
                    "word_key",
                }
                or record["source"] not in {"mapped-word", "restored-semantic-source"}
                or record["word_key"] in seen_sajdahs
                or not all(
                    isinstance(record[name], int) and record[name] > 0
                    for name in ("page", "line", "anchor_line")
                )
            ):
                raise ValueError("sajdah source inventory differs")
            glyph = record["source_glyph"]
            self._verify_glyph(glyph)
            if record["source"] == "mapped-word":
                if (
                    glyph["word_glyph_count"] != 2
                    or glyph["index"] != 1
                    or record["line"] != record["anchor_line"]
                ):
                    raise ValueError("mapped sajdah source glyph differs")
                mapped += 1
            else:
                if glyph["word_glyph_count"] != 1 or glyph["index"] is not None:
                    raise ValueError("restored sajdah source glyph differs")
                restored += 1
            seen_sajdahs.add(record["word_key"])
            self.sajdahs_by_page[record["page"]].append(record)

        actual = {
            "division_starts": len(divisions),
            "mapped_sajdah_source_glyphs": mapped,
            "printed_rubu_al_hizb": printed,
            "restored_sajdah_source_glyphs": restored,
            "sajdah_marks": len(sajdahs),
            "unprinted_rubu_al_hizb": len(divisions) - printed,
        }
        if counts != actual or actual != {
            "division_starts": 240,
            "mapped_sajdah_source_glyphs": 14,
            "printed_rubu_al_hizb": 199,
            "restored_sajdah_source_glyphs": 1,
            "sajdah_marks": 15,
            "unprinted_rubu_al_hizb": 41,
        }:
            raise ValueError("division/sajdah source counts differ")
        self.expected_counts = counts

    @staticmethod
    def _verify_glyph(glyph: object) -> None:
        if (
            not isinstance(glyph, dict)
            or set(glyph)
            != {"box", "codepoint", "glyph_id", "index", "word_glyph_count"}
            or not isinstance(glyph["box"], list)
            or len(glyph["box"]) != 4
            or not all(isinstance(value, int) for value in glyph["box"])
            or glyph["box"][0] >= glyph["box"][2]
            or glyph["box"][1] >= glyph["box"][3]
            or not isinstance(glyph["codepoint"], str)
            or not glyph["codepoint"].startswith("U+")
            or not isinstance(glyph["glyph_id"], int)
            or glyph["glyph_id"] <= 0
            or (
                glyph["index"] is not None
                and (not isinstance(glyph["index"], int) or glyph["index"] < 0)
            )
            or not isinstance(glyph["word_glyph_count"], int)
            or glyph["word_glyph_count"] <= 0
        ):
            raise ValueError("semantic source glyph differs")
        _parse_codepoint(glyph["codepoint"])

    @staticmethod
    def _match_glyph(word: dict, source: dict) -> None:
        glyphs = word.get("glyphs", [])
        index = source["index"]
        if (
            len(glyphs) != source["word_glyph_count"]
            or index is None
            or index >= len(glyphs)
            or any(
                glyphs[index].get(name) != source[name]
                for name in ("box", "codepoint", "glyph_id")
            )
        ):
            raise ValueError(f"semantic source glyph drifted: {word['word_key']}")

    def page(self, page: dict) -> dict:
        page_number = page["page"]
        words = {word["word_key"]: word for word in page["words"]}
        if len(words) != len(page["words"]):
            raise ValueError(f"page {page_number}: repeated direct word key")
        shared_signs = [
            word["word_key"]
            for group in page.get("shared_groups", [])
            for word in group["canonical_words"]
            if "۞" in word["text"]["rasm_uthmani"]
            or "۩" in word["text"]["rasm_uthmani"]
        ]
        if shared_signs:
            raise ValueError(f"page {page_number}: shared semantic signs differ")

        boundaries = {}
        divisions = {}
        skips = set()
        counts = Counter()
        for record in self.divisions_by_page.get(page_number, []):
            word = words.get(record["word_key"])
            if (
                word is None
                or word["line"] != record["line"]
                or word["word_key"] != f"{record['ayah_key']}:1"
            ):
                raise ValueError(
                    f"page {page_number}: division anchor differs for {record['ayah_key']}"
                )
            boundaries[record["ayah_key"]] = record
            counts["division_starts"] += 1
            source = record["source_glyph"]
            if source is not None:
                self._match_glyph(word, source)
                skips.add((word["word_key"], source["index"]))
                divisions[record["ayah_key"]] = record
                counts["printed_rubu_al_hizb"] += 1
            else:
                counts["unprinted_rubu_al_hizb"] += 1

        sajdah_after = defaultdict(list)
        sajdah_at_line_start = defaultdict(list)
        restored = []
        sajdah_records = self.sajdahs_by_page.get(page_number, [])
        expected_sajdah_words = {record["word_key"] for record in sajdah_records}
        actual_sajdah_words = {
            word["word_key"]
            for word in page["words"]
            if "۩" in word["text"]["rasm_uthmani"]
        }
        if expected_sajdah_words != actual_sajdah_words:
            raise ValueError(f"page {page_number}: canonical sajdah ownership differs")
        for record in sajdah_records:
            word = words[record["word_key"]]
            if word["line"] != record["anchor_line"]:
                raise ValueError(
                    f"page {page_number}: sajdah anchor line differs for {record['word_key']}"
                )
            source = record["source_glyph"]
            if record["source"] == "mapped-word":
                self._match_glyph(word, source)
                skips.add((word["word_key"], source["index"]))
                sajdah_after[record["ayah_key"]].append(record)
                counts["mapped_sajdah_source_glyphs"] += 1
            else:
                if len(word.get("glyphs", [])) != source["word_glyph_count"]:
                    raise ValueError(
                        f"page {page_number}: restored sajdah anchor differs for {record['word_key']}"
                    )
                sajdah_at_line_start[record["line"]].append(record)
                restored.append(source)
                counts["restored_sajdah_source_glyphs"] += 1
            counts["sajdah_marks"] += 1

        return {
            "boundaries": boundaries,
            "counts": counts,
            "divisions": divisions,
            "restored_glyphs": restored,
            "sajdah_after": dict(sajdah_after),
            "sajdah_at_line_start": dict(sajdah_at_line_start),
            "skips": skips,
        }

    def verify_complete(self, pages: list[int], counts: Counter) -> None:
        if pages == list(range(1, 605)):
            actual = {name: counts[name] for name in self.COUNT_FIELDS}
            if actual != self.expected_counts:
                raise ValueError("complete division/sajdah output counts differ")


def division_values(rubu_al_hizb: int) -> dict[str, int]:
    return {
        "rubu_al_hizb": rubu_al_hizb,
        "rubu_al_hizb_in_hizb": (rubu_al_hizb - 1) % 4 + 1,
        "nisf": (rubu_al_hizb - 1) % 4 // 2 + 1,
        "hizb": (rubu_al_hizb - 1) // 4 + 1,
        "juz": (rubu_al_hizb - 1) // 8 + 1,
    }


def boundary_attributes(record: dict) -> str:
    rubu_al_hizb = record["rubu_al_hizb"]
    values = division_values(rubu_al_hizb)
    attributes = []
    if (rubu_al_hizb - 1) % 8 == 0:
        attributes.append(f'data-juz-start="{values["juz"]}"')
    if (rubu_al_hizb - 1) % 4 == 0:
        attributes.append(f'data-hizb-start="{values["hizb"]}"')
    if (rubu_al_hizb - 1) % 4 == 2:
        attributes.append(f'data-nisf-start="{(rubu_al_hizb + 1) // 4}"')
    attributes.append(f'data-rubu-al-hizb-start="{rubu_al_hizb}"')
    return " " + " ".join(attributes)
