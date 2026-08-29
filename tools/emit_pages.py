#!/usr/bin/env python3
"""Emit page SVGs for a given QSVG_PROFILE into a staging cache.

Separate from build_bundle.py only because emitting 604 pages costs a few
minutes and is worth caching across bundle builds. build_bundle.py calls
main() directly; nothing here interprets the SVG.

    python3 tools/emit_pages.py --profile production [--jobs 32] [1 604]

Writes <cache>/<edition>-<profile>/NNN.svg where <cache> defaults to
$QSVG_ROOT/.cache/bundle-pages.  Idempotent: a page already present and
non-empty is skipped unless --force.
"""
import argparse
import os
import sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))


def stage_dir(edition="hafs/kfqc", profile="production", cache=None):
    cache = cache or os.path.join(ROOT, ".cache", "bundle-pages")
    return os.path.join(cache, "%s-%s" % (edition.replace("/", "-"), profile))


def _one(job):
    page, edition, out = job
    dest = os.path.join(out, "%03d.svg" % page)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return page, None
    sys.path.insert(0, TOOLS)
    import assign_words
    try:
        _, svg, _, _ = assign_words.assign_page(
            edition, page, os.path.join(ROOT, ".cache", "words"))
    except Exception as e:                       # noqa: BLE001 - reported, not swallowed
        return page, "%s: %s" % (type(e).__name__, e)
    tmp = dest + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(svg)
    os.replace(tmp, dest)
    return page, None


def emit(edition="hafs/kfqc", profile="production", first=1, last=604,
         jobs=32, cache=None, force=False, quiet=False):
    """Emit pages [first, last] and return the staging directory.

    Raises RuntimeError if any page failed: a bundle must never be built from
    a partial page set.
    """
    out = stage_dir(edition, profile, cache)
    os.makedirs(out, exist_ok=True)
    if force:
        for p in range(first, last + 1):
            f = os.path.join(out, "%03d.svg" % p)
            if os.path.exists(f):
                os.remove(f)
    os.environ["QSVG_PROFILE"] = profile
    jobslist = [(p, edition, out) for p in range(first, last + 1)]
    from concurrent.futures import ProcessPoolExecutor
    errs = []
    done = 0
    with ProcessPoolExecutor(jobs) as ex:
        for page, err in ex.map(_one, jobslist):
            done += 1
            if err:
                errs.append((page, err))
            if not quiet and done % 25 == 0:
                print("  emitted %d/%d" % (done, len(jobslist)), flush=True)
    if errs:
        raise RuntimeError("page emission failed on %d pages: %s"
                           % (len(errs), errs[:5]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--edition", default="hafs/kfqc")
    ap.add_argument("--profile", default="production",
                    choices=("production", "dev"))
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    out = emit(a.edition, a.profile, a.first, a.last, a.jobs, a.cache, a.force)
    print("staged in", out)


if __name__ == "__main__":
    main()
