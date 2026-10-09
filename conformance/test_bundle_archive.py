#!/usr/bin/env python3
"""Contracts for the canonical-only release archive."""

import hashlib
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bundle import BUNDLE_NAME, canonical_files, write_archive


def digest(data):
    return hashlib.sha256(data).hexdigest()


def test_archive_checksum_manifest_matches_its_canonical_subset():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bundle = root / BUNDLE_NAME
        (bundle / "pages").mkdir(parents=True)
        canonical = {
            "LICENSE": b"terms\n",
            "NOTICE.md": b"sources\n",
            "README.md": b"release\n",
            "index/pages.json": b"{}\n",
            "index/by-page/001.json": b"{}\n",
            "pages/001.svg": b"<svg/>\n",
        }
        for rel, data in canonical.items():
            path = bundle / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (bundle / "pages/001.svg.gz").write_bytes(b"transport gzip")
        (bundle / "pages/001.svg.br").write_bytes(b"transport brotli")
        (bundle / "CHECKSUMS.txt").write_text("full bundle manifest\n")
        assert [rel for rel, _full in canonical_files(bundle)] == sorted(canonical)

        first = Path(write_archive(bundle, root / "one"))
        second = Path(write_archive(bundle, root / "two"))
        assert first.read_bytes() == second.read_bytes()
        assert (
            Path(str(first) + ".sha256").read_text()
            == f"{digest(first.read_bytes())}  {first.name}\n"
        )

        with tarfile.open(first, "r:gz") as archive:
            names = archive.getnames()
            prefix = BUNDLE_NAME + "/"
            assert names == sorted(names)
            assert names == [prefix + "CHECKSUMS.txt"] + [
                prefix + rel for rel in sorted(canonical)
            ]
            checksums = (
                archive.extractfile(prefix + "CHECKSUMS.txt")
                .read()
                .decode()
                .splitlines()
            )
            assert checksums == [
                f"{digest(data)}  {rel}" for rel, data in sorted(canonical.items())
            ]
            assert [line.split("  ", 1)[1] for line in checksums] == sorted(canonical)
            for line in checksums:
                want, rel = line.split("  ", 1)
                assert digest(archive.extractfile(prefix + rel).read()) == want


if __name__ == "__main__":
    tests = sorted(
        (name, fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
