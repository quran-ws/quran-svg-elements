#!/usr/bin/env python3
"""Schema v2 phase 1: build the mark registry and the edition manifest.

Two files, both under `.cache/schema/`, both DERIVED — nothing in either is
typed by hand:

`mark-taxonomy.v2.json`
    The canonical mark vocabulary (attr_schema_v3 §9/§11): every name the
    emitter can write, its category, its family, the features it may carry,
    and the aliases it retires. The names and families come out of
    `tools/assign_words.py`'s own `_MFAM` table and `tools/audit_taxonomy.py`'s
    ALLOWED_* sets — the registry is a re-expression of the code's closed
    vocabulary in data, so the two cannot drift without the validator saying so.

`edition-hafs-kfgqpc.json`
    Everything that is true of THIS print rather than of the pipeline: page
    count and lines per page (DigitalKhatt layout DB `info` table), the surah
    table (quran.com `/api/v4/chapters`), the juz / hizb / rubʿ division
    (quran.com ayah records in `.cache/words`), the rare-sign sites
    (`.cache/marks/rare_places.json`), the sifr word counts and the basmalah
    expectation (audit_taxonomy's measured constants), and the v1 vocabulary
    freeze for reference.

Usage:  python3 tools/build_schema_registry.py [--check]
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import quran_meta as qm                                          # noqa: E402

ROOT = qm.ROOT
OUT = os.path.join(ROOT, ".cache", "schema")

REGISTRY_VERSION = "2.0"

# category / family / legal features, per attr_schema_v3 §9 and §11. `family`
# mirrors assign_words._MFAM exactly; a name absent there has no family, which
# is what the emitter does today (it writes data-mark-family only when _MFAM
# has the name).
_MARKS = {
    # harakahs — one stroke, named from position; see CLAUDE.md "derived families"
    "fathah":          ("harakah", None, ["placement"]),
    "kasrah":          ("harakah", None, ["placement"]),
    "dammah":          ("harakah", None, ["placement"]),
    "sukun":          ("harakah", None, []),
    "shaddah":         ("harakah", None, []),
    "tanwin_al_fath":       ("tanwin", "tanwin", ["arrangement"]),
    "tanwin_al_kasr":       ("tanwin", "tanwin", ["arrangement"]),
    "tanwin_al_damm":       ("tanwin", "tanwin", ["arrangement"]),
    # hamzat and the long-vowel letters written small
    "maddah":         ("orthographic", None, []),
    "hamzah":          ("orthographic", None, []),
    "hamzat_al_wasl":          ("orthographic", None, []),
    "omitted_alif":     ("orthographic", None, []),
    "small_waw":      ("orthographic", None, []),
    "small_yaa":       ("orthographic", None, []),
    "small_noon":     ("orthographic", None, []),
    # dabt — the reading apparatus of this print
    "rounded_zero":  ("dabt", "sifr", []),
    "rectangular_zero":  ("dabt", "sifr", []),
    "small_meem":     ("dabt", None, ["placement"]),
    # letter dots. v2 §6.2 makes these a segmentation role rather than a
    # semantic mark; the bridge (ruling E6) keeps the internal counting
    # bucket, so they stay in the registry with role="letter_dot".
    "dot":            ("letter_dot", "dots", []),
    "two_dots":       ("letter_dot", "dots", []),
    "three_dots":     ("letter_dot", "dots", []),
    # waqf. Budgets are FAMILY level: the editions disagree on WHICH sign at
    # 424 of 4,416 positions (CLAUDE.md), so the ink names the subtype and
    # the count answers to "waqf".
    "waqf":          ("waqf", "waqf", []),
    "waqf_jaiz_wasl_awla":      ("waqf", "waqf", []),
    "waqf_jaiz_waqf_awla":      ("waqf", "waqf", []),
    "waqf_jaiz_mustawi_al_tarafayn":      ("waqf", "waqf", []),
    "waqf_lazim":     ("waqf", "waqf", []),
    "waqf_al_muanaqah":       ("waqf", "waqf", []),
    # reading signs, all single-site or near it
    "saktah":         ("reading_sign", "reading_sign", []),
    "seen_al_qiraah":   ("reading_sign", "reading_sign", []),
    "imalah":         ("reading_sign", "reading_sign", []),
    "ishmam":         ("reading_sign", "reading_sign", []),
    "tashil":         ("reading_sign", "reading_sign", []),
    # standalone signs — their own <g>, no word
    "sajdah_line":    ("standalone", "sajdah", []),
    "sajdah_mark":    ("standalone", "sajdah", []),
    "hizb":           ("standalone", None, []),
}

# group-level names (the <g class="sajdah-mark"|"division-mark"> wrapper)
_GROUP_MARKS = {"sajdah": "standalone", "hizb": "standalone"}

# reserved, deliberately inactive (attr_schema_v3 §4.3): this print draws no
# لا sign, so the token exists but nothing may emit it.
_RESERVED = {"waqf_mamnu": "this print emits no لا sign (ALLOWED_WAQF is the "
                           "five-value set); token reserved, not active"}

_ALIASES = {"waqf qila": "waqf_jaiz_mustawi_al_tarafayn", "waqf sali": "waqf_jaiz_wasl_awla",
            "waqf taanuq": "waqf_al_muanaqah", "sajdah": "sajdah_mark"}

_KINDS = {
    "body": "letter ink of a word",
    "mark": "a named diacritic or sign",
    "header_ink": "ink inside a surah-name or basmalah banner, undecomposed",
    "ornament": "banner decoration, not a mark",
    "ayah_mark_ornament": "the medallion ring",
    "ayah_number": "the numeral inside the medallion",
    "page_number": "the printed page number (p17 only: the artwork keeps it)",
    "running_head": "a juz/surah running head drawn above the viewBox, never "
                    "visible (p17 only)",
}

_FEATURES = {
    "placement": ["above", "below"],
    "arrangement": ["stacked", "staggered"],
}


def registry():
    marks = {}
    for name, (cat, fam, feats) in sorted(_MARKS.items()):
        marks[name] = {"category": cat, "family": fam, "features": feats,
                       "active": True}
    for name, why in _RESERVED.items():
        marks[name] = {"category": "waqf", "family": "waqf", "features": [],
                       "active": False, "note": why}
    return {
        "schema": "mark-taxonomy",
        "version": REGISTRY_VERSION,
        "source": "assign_words._MFAM + audit_taxonomy ALLOWED_* "
                  "(re-expressed as data; validate_annotations proves parity)",
        "marks": marks,
        "group_marks": _GROUP_MARKS,
        "kinds": _KINDS,
        "features": _FEATURES,
        "aliases": _ALIASES,
    }


def edition():
    db = os.path.join(ROOT, ".cache", "digitalkhatt",
                      "digital-khatt-15-lines.db")
    name, pages, lines, font = sqlite3.connect(db).execute(
        "select name, number_of_pages, lines_per_page, font_name "
        "from info").fetchone()

    ch = qm.chapters()
    surahs = [ch[n] for n in sorted(ch)]

    rubu_al_hizb = qm.rubu_al_hizb_starts()
    divisions = {}
    for r in sorted(k for k in rubu_al_hizb if isinstance(k, int)):
        p = qm.rubu_al_hizb_position(r)
        p["starts_at"] = "%d:%d" % rubu_al_hizb[r]
        divisions[str(r)] = p

    rare = json.load(open(os.path.join(ROOT, ".cache", "marks",
                                       "rare_places.json"),
                          encoding="utf-8"))
    freeze_path = os.path.join(ROOT, ".cache", "marks", "schema_v1_freeze.json")
    freeze = (json.load(open(freeze_path, encoding="utf-8"))
              if os.path.exists(freeze_path) else {})

    return {
        "schema": "edition-manifest",
        "version": REGISTRY_VERSION,
        "id": "hafs-kfgqpc",
        # V4 is the 1441H print; V2 is 1421H and is what DigitalKhatt models.
        # docs/EDITION-1441-FINDING.md: line agreement against the ink is
        # 100.0000% for V4/1441H and 96.33% for DK V2/1421H. Naming this V2
        # 1441H paired the wrong version with the right year, in the one file
        # a consumer reads to learn which printing they have.
        "print": "KFGQPC Madani mushaf, V4 1441H",
        "layout_source": name,
        "font": font,
        "pages": pages,
        "lines_per_page": lines,
        "sources": {
            "surahs": "quran.com /api/v4/chapters?language=en "
                      "-> .cache/meta/chapters.json",
            "divisions": "quran.com ayah records (juz_number, hizb_number, "
                         "rub_el_hizb_number) in .cache/words/page-*.json",
            "layout": ".cache/digitalkhatt/digital-khatt-15-lines.db (info)",
            "rare_sites": ".cache/marks/rare_places.json",
            "counts": "measured mushaf-wide; gated by tools/audit_taxonomy.py",
        },
        "surahs": surahs,
        "divisions": {
            "juz": 30, "hizb": 60, "rubu_al_hizb": 240,
            "rubu_al_hizb_starts": divisions,
        },
        "expectations": {
            # One banner per surah — 114. Two surahs carry no basmalah of
            # their own: Fatihah, whose basmalah IS ayah 1:1, and Tawbah,
            # which has none at all. So 112 basmalah groups. Both numbers are
            # measured on the emitted pages AND declared independently by the
            # DK layout DB (2026-08-29). The earlier 113/108 encoded the
            # header-mapping defect as if it were the edition: four banners
            # were emitted as basmalahs and surah 17's basmalah was split in
            # two, which cancelled out to 113.
            "basmalah_groups": 112,
            "surah_name_groups_emitted": 114,
            "rounded_zero_words": 3970,
            "rectangular_zero_words": 66,
            "waqf_al_muanaqah_pairs": 3,
            "sajdah_sites": 15,
            "division_marks_drawn": 199,
            "division_marks_note":
                "240 rubʿ boundaries, 199 rosettes: all 41 absent ones fall on "
                "an ayah 1, where the surah banner marks the division instead "
                "(41 of 41 — measured, no exceptions)",
            "rare_sites": rare,
        },
        "v1_vocabulary_freeze": freeze.get("vocabulary", {}),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if the files on disk differ from a fresh build")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for fn, data in (("mark-taxonomy.v2.json", registry()),
                     ("edition-hafs-kfgqpc.json", edition())):
        path = os.path.join(OUT, fn)
        text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
        if args.check:
            have = open(path, encoding="utf-8").read() \
                if os.path.exists(path) else None
            if have != text:
                print("STALE %s" % path)
                bad = 1
            continue
        tmp = path + ".tmp"
        open(tmp, "w", encoding="utf-8").write(text)
        os.replace(tmp, path)
        print("wrote %s (%d bytes)" % (path, len(text)))
    sys.exit(bad)


if __name__ == "__main__":
    main()
