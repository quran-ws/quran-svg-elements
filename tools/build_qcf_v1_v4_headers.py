#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools==4.66.1",
# ]
# ///
"""Export exact QPC V4 surah-banner and basmalah outlines.

This produces standalone source assets only. It does not choose their scale or
placement on the Hafs 1405H V1 page layout.
"""

import argparse
import hashlib
import json
import shutil
import tempfile
from html import escape
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "conformance/qcf-v1-source.json"
DEFAULT_OUT_DIR = ROOT / ".cache/qcf-v1/v4-header-assets"


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


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: float) -> str:
    if abs(value) < 5e-10:
        value = 0.0
    return f"{value:.9f}".rstrip("0").rstrip(".")


def parse_codepoint(value: str) -> int:
    if not isinstance(value, str) or not value.startswith("U+"):
        raise ValueError(f"invalid codepoint: {value!r}")
    return int(value.replace("U+", "0x"), 0)


def source_settings(manifest: dict) -> dict:
    if manifest.get("schema") != "quran-svg-elements/qcf-v1-source":
        raise ValueError("wrong QCF V1 source manifest schema")
    if manifest.get("schema_version") != 2:
        raise ValueError("wrong QCF V1 source manifest version")
    if manifest.get("edition") != "hafs-qcf-v1":
        raise ValueError("wrong QCF V1 edition")
    if manifest.get("print_year_hijri") != 1405:
        raise ValueError("QCF V1 header assets must target the 1405H print")

    assets = manifest.get("header_assets")
    if not isinstance(assets, dict) or set(assets) != {"surah_name", "basmalah"}:
        raise ValueError("wrong QCF V1 header asset settings")
    surah = assets["surah_name"]
    basmalah = assets["basmalah"]
    codepoints = surah.get("codepoints")
    if (
        surah.get("count") != 114
        or surah.get("source_font") != "QCF_SurahHeader_COLOR-Regular.ttf"
        or surah.get("codepoint_order") != "QUL surah_header_code"
        or surah.get("asset_path") != "surah/{surah:03}.svg"
        or not isinstance(codepoints, list)
        or len(codepoints) != 114
        or len(set(codepoints)) != 114
    ):
        raise ValueError("wrong QPC V4 complete-header contract")
    parsed = [parse_codepoint(value) for value in codepoints]
    if len(parsed) != 114:
        raise ValueError("wrong QPC V4 complete-header contract")
    if (
        basmalah.get("count") != 112
        or basmalah.get("source_font") != "QCF4_Hafs_01_W.ttf"
        or basmalah.get("font_file_id") != 1
        or basmalah.get("font_code") != 2013
        or basmalah.get("codepoint") != "U+F8DD"
        or basmalah.get("asset_path") != "basmalah.svg"
    ):
        raise ValueError("wrong QPC V4 basmalah asset contract")
    return assets


def asset_plan(manifest: dict) -> list[dict]:
    settings = source_settings(manifest)
    codepoints = settings["surah_name"]["codepoints"]
    assets = [
        {
            "kind": "surah-name",
            "surah": surah,
            "codepoint": codepoints[surah - 1],
            "path": settings["surah_name"]["asset_path"].format(surah=surah),
            "font": "surah",
        }
        for surah in range(1, 115)
    ]
    assets.append(
        {
            "kind": "basmalah",
            "codepoint": settings["basmalah"]["codepoint"],
            "path": settings["basmalah"]["asset_path"],
            "font": "basmalah",
        }
    )
    return assets


def svg_asset(
    kind: str,
    codepoint: str,
    path: str,
    box: tuple[float, float, float, float],
    advance: float,
    units_per_em: int,
    surah: int | None = None,
) -> bytes:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0 or not path:
        raise ValueError(f"empty {kind} outline at {codepoint}")
    attributes = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'viewBox="0 0 {number(width)} {number(height)}"',
        f'width="{number(width)}"',
        f'height="{number(height)}"',
        f'data-kind="{escape(kind, quote=True)}"',
        f'data-codepoint="{escape(codepoint, quote=True)}"',
        f'data-advance="{number(advance)}"',
        f'data-units-per-em="{units_per_em}"',
    ]
    if surah is not None:
        attributes.append(f'data-surah="{surah}"')
    transform = f"matrix(1 0 0 -1 {number(-x0)} {number(y1)})"
    return (
        f"<svg {' '.join(attributes)}>"
        f'<path data-kind="{escape(kind, quote=True)}" '
        f'd="{escape(path, quote=True)}" transform="{transform}"/>'
        "</svg>\n"
    ).encode()


class OutlineFont:
    def __init__(self, path: Path):
        self.font = TTFont(path)
        self.glyph_set = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.metrics = self.font["hmtx"].metrics
        self.units_per_em = self.font["head"].unitsPerEm

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.font.close()

    def outline(
        self, codepoint: int
    ) -> tuple[str, tuple[float, float, float, float], int]:
        name = self.cmap.get(codepoint)
        if name is None:
            raise ValueError(f"font has no U+{codepoint:04X}")
        path_pen = SVGPathPen(self.glyph_set)
        bounds_pen = BoundsPen(self.glyph_set)
        self.glyph_set[name].draw(path_pen)
        self.glyph_set[name].draw(bounds_pen)
        path = path_pen.getCommands()
        if not path or bounds_pen.bounds is None:
            raise ValueError(f"font glyph U+{codepoint:04X} has no outline")
        return path, bounds_pen.bounds, self.metrics[name][0]


def verify_inputs(
    manifest: dict, surah_font: Path, basmalah_font: Path
) -> dict[str, str]:
    expected = manifest["inputs"]
    actual = {
        "qpc4_surah_header_font_sha256": sha256(surah_font),
        "qcf4_basmalah_font_sha256": sha256(basmalah_font),
    }
    wrong = {
        name: {"expected": expected.get(name), "actual": value}
        for name, value in actual.items()
        if expected.get(name) != value
    }
    if wrong:
        raise ValueError(
            "V4 header source digest mismatch:\n" + json.dumps(wrong, indent=2)
        )
    return actual


def build(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    plan = asset_plan(manifest)
    input_digests = verify_inputs(manifest, args.surah_font, args.basmalah_font)
    if args.out_dir.exists():
        raise ValueError(f"output path already exists: {args.out_dir}")

    parent = args.out_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{args.out_dir.name}.", dir=parent))
    records = []
    try:
        with (
            OutlineFont(args.surah_font) as surah_font,
            OutlineFont(args.basmalah_font) as basmalah_font,
        ):
            fonts = {"surah": surah_font, "basmalah": basmalah_font}
            for asset in plan:
                codepoint = parse_codepoint(asset["codepoint"])
                font = fonts[asset["font"]]
                path, box, advance = font.outline(codepoint)
                output = stage / asset["path"]
                data = svg_asset(
                    asset["kind"],
                    asset["codepoint"],
                    path,
                    box,
                    advance,
                    font.units_per_em,
                    asset.get("surah"),
                )
                write_bytes(output, data)
                records.append(
                    {key: value for key, value in asset.items() if key != "font"}
                    | {
                        "box": list(box),
                        "advance": advance,
                        "units_per_em": font.units_per_em,
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )

        asset_paths = sorted(path for path in stage.rglob("*.svg"))
        digest = hashlib.sha256()
        for path in asset_paths:
            relative = path.relative_to(stage)
            digest.update(relative.as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
        summary = {
            "schema": "quran-svg-elements/qcf-v1-v4-header-assets",
            "schema_version": 1,
            "edition": manifest["edition"],
            "print_year_hijri": manifest["print_year_hijri"],
            "source_manifest_sha256": sha256(args.manifest),
            "input_digests": input_digests,
            "surah_assets": 114,
            "basmalah_assets": 1,
            "asset_files_sha256": digest.hexdigest(),
            "placement": "deferred",
            "assets": records,
        }
        write_bytes(stage / "summary.json", json_bytes(summary, pretty=True))
        stage.replace(args.out_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps(summary, indent=2))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    command.add_argument("--surah-font", type=Path, required=True)
    command.add_argument("--basmalah-font", type=Path, required=True)
    command.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return command


def main() -> None:
    args = parser().parse_args()
    for name in ("manifest", "surah_font", "basmalah_font", "out_dir"):
        setattr(args, name, getattr(args, name).resolve())
    build(args)


if __name__ == "__main__":
    main()
