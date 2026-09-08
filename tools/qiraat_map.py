#!/usr/bin/env python3
"""Which counting system does a mushaf follow, and how many ayahs does each surah have in it?

The ten qiraahs do not agree on where every ayah ends, so a mushaf's ayah identities can only
be checked against the counting madhhab (``نظام العد``) its qiraah actually follows.  The
mapping and the disputed boundaries come from the vendored
`quranpedia/qiraahs-ayah-map <https://github.com/quranpedia/qiraahs-ayah-map>`_ dataset in
``tools/data/qiraahs-ayah-map`` — see ``SOURCE.md`` there.

The dataset states its boundaries relative to the Kufi reference: for a surah it lists the
kufi ayah ends that some systems do *not* count (``end``) and the extra ends inside a kufi
ayah that some systems *do* count (``internal``).  A system's count for a surah is therefore

    kufi_count + (internal points that system counts) - (kufi ends that system omits)

Undisputed kufi ends are implicit and omitted from the dataset, which is why the Kufi counts
have to be supplied; ``kufi_counts_from_surah_json`` reads them from a mushaf that follows the
Kufi system and checks the total is 6236 before trusting them.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "qiraahs-ayah-map")

# The five editions in this repository, and the qiraah/rawi each one transmits.
MUSHAFS = {
    "hafs":   ("asim",    "hafs"),
    "shubah": ("asim",    "shubah"),
    "warsh":  ("nafi",    "warsh"),
    "qalun":  ("nafi",    "qalun"),
    "duri":  ("abu-amr", "duri"),
}

KUFI_TOTAL = 6236


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def dataset():
    """(counting_systems, qiraahs, boundary_primitives)"""
    return (_load("counting-systems.json"),
            _load("qiraahs.json"),
            _load("book-boundary-primitives.json"))


def counting_system(mushaf):
    """The counting madhhab this mushaf follows, e.g. 'hafs' -> 'kufi'."""
    if mushaf not in MUSHAFS:
        raise KeyError("unknown mushaf %r; known: %s" % (mushaf, ", ".join(sorted(MUSHAFS))))
    qiraah, rawi = MUSHAFS[mushaf]
    _, qiraahs, _ = dataset()
    if qiraah not in qiraahs:
        raise KeyError("qiraah %r is not in qiraahs.json" % qiraah)
    if rawi not in qiraahs[qiraah]["rawis"]:
        raise KeyError("rawi %r is not listed under qiraah %r" % (rawi, qiraah))
    return qiraahs[qiraah]["counting_system"]


def kufi_counts_from_surah_json(path):
    """Per-surah Kufi ayah counts, read from a Kufi mushaf's surah.json and sanity-checked."""
    with open(path, encoding="utf-8") as fh:
        surahs = json.load(fh)
    counts = {int(s["number"]): int(s["ayahCount"]) for s in surahs}
    if len(counts) != 114:
        raise ValueError("%s lists %d surahs, expected 114" % (path, len(counts)))
    total = sum(counts.values())
    if total != KUFI_TOTAL:
        raise ValueError("%s totals %d ayahs, which is not the Kufi %d — it cannot be used as "
                         "the Kufi reference" % (path, total, KUFI_TOTAL))
    return counts


def ayah_counts(system, kufi_counts):
    """Per-surah ayah counts for one counting system, derived from the Kufi counts."""
    systems, _, prim = dataset()
    if system not in systems:
        raise KeyError("unknown counting system %r" % system)
    counts = dict(kufi_counts)
    for surah, points in prim["surahs"].items():
        s = int(surah)
        delta = 0
        for _, point in points.items():
            end = point.get("end")
            if end is not None and system not in end["counted_by"]:
                delta -= 1                       # a kufi ayah end this system does not count
            for extra in point.get("internal", []):
                if system in extra["counted_by"]:
                    delta += 1                   # an extra end inside a kufi ayah
        counts[s] = counts.get(s, 0) + delta
    return counts


def expected_total(system):
    """The total this system is documented to have, for cross-checking a derivation."""
    systems, _, _ = dataset()
    return systems[system]["total_ayahs"]


def describe(system):
    systems, _, _ = dataset()
    s = systems[system]
    return "%s (%s) — %d ayahs" % (s["name_en"], s["name_ar"], s["total_ayahs"])


if __name__ == "__main__":
    import sys
    repo = os.path.dirname(HERE)
    kufi = kufi_counts_from_surah_json(
        os.path.join(repo, "mushafs", "hafs", "kfqc", "json", "surah.json"))
    print("Kufi reference: 114 surahs, %d ayahs\n" % sum(kufi.values()))
    print("%-8s %-8s %-14s %8s %8s  %s" % ("mushaf", "qiraah", "counting", "derived", "stated", ""))
    ok = True
    for mushaf in sorted(MUSHAFS):
        system = counting_system(mushaf)
        derived = sum(ayah_counts(system, kufi).values())
        stated = expected_total(system)
        flag = "ok" if derived == stated else "MISMATCH"
        ok &= derived == stated
        print("%-8s %-8s %-14s %8d %8d  %s"
              % (mushaf, MUSHAFS[mushaf][0], system, derived, stated, flag))
    sys.exit(0 if ok else 1)
