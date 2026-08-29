#!/usr/bin/env python3
"""Express MushafDatabase's ligature CUT in OUR element space.

MushafDatabase publishes the same KFGQPC artwork with one
``<g id="md-ligature-...">`` per run of ink per word.  Our own emitter derives
the run partition geometrically (``cluster_line`` builds atoms, then
``align_segs_atoms`` reconciles the rule-derived segmentation onto them), and
loses it for 2,687 words: we emit ONE ``<g class="ligature">`` where both the
joining rules and the reference say TWO.  This tool writes their partition down
in a form the pipeline can consume, so ``QSVG_MDBCUT`` can use it as the cut
instead of inventing one.

Method:

  contours       BOTH sides are measured with ``svg_lines.subpaths``, which
                 solves the Bezier derivative for an EXACT bounding box.  The
                 control-point hull ``audit_inkidentity`` uses is fine there
                 (it is applied to both sides) but inflates a box by up to
                 0.4u, and our own elements carry exact boxes, so mixing the
                 two conventions loses the size test.
  registration   ``audit_inkidentity.estimate`` unchanged: one affine per page,
                 seeded at the known scale 4/3 with a modal vote on the offset
                 and refined by least squares on the contour pairs.
  pairing        ``audit_inkidentity.match`` unchanged -- size within 0.15u,
                 centre within 0.6u, inside the measured empty band 0.1u..2.0u.
  element runs   our element's run is the run holding its paired contours.
                 An element is recorded only when its contours are UNANIMOUS;
                 see ``--dist`` for how often they are not.

Output: ``.cache/mdb_runs.json`` -- ``{page: {element-bbox-key: run-id}}`` where
the key is ``"x1,y1,x2,y2"`` at one decimal (the pipeline's own element key,
the same one ``QSVG_EIDMAP`` writes) and the run-id is ``"surah:ayah:pos#i"``.

    python3 tools/build_mdb_runs.py 1 604 --jobs 32
    python3 tools/build_mdb_runs.py 3 42 --dist
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import audit_inkidentity as II          # noqa: E402  registration + pairing
import svg_lines as SL                  # noqa: E402  exact contour boxes

NS = II.NS
DEFAULT_REF = II.DEFAULT_REF


# ---------------------------------------------------------------- their side

def _exact_sigs(d, M):
    """[(cx, cy, w, h, 0)] for a path's contours, in the frame M maps to."""
    out = []
    for sp in SL.subpaths(d):
        x1, y1, x2, y2 = SL.transform_box(M, sp["xmin"], sp["ymin"],
                                          sp["xmax"], sp["ymax"])
        out.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1, 0))
    return out


def their_runs(pg, refdir):
    """[(run-id, is_body, signature)] for one reference page, in their units."""
    p = os.path.join(refdir, "%03d.svg" % pg)
    if not os.path.exists(p):
        return None
    root = ET.parse(p).getroot()
    pos = II.their_positions(root)
    out = []
    seen = Counter()
    for w in root.iter(NS + "g"):
        gid = w.get("id") or ""
        if not gid.startswith("md-word-") or w.get("data-type") != "text":
            continue
        key = pos.get(gid)
        if key is None:
            continue
        for lig in w:
            if not (lig.get("id") or "").startswith("md-ligature-"):
                continue
            rid = "%s#%d" % (key, seen[key])
            seen[key] += 1
            _walk(lig, (1, 0, 0, 1, 0, 0), rid, out)
    return out


def _walk(node, M, rid, out):
    for ch in node.iter():
        pass
    _rec(node, M, rid, out)


def _rec(node, M, rid, out):
    for ch in node:
        M2 = II._mul(M, II._mat(ch.get("transform"))) if ch.get("transform") else M
        tag = ch.tag.split("}")[-1]
        if tag == "path" and ch.get("d"):
            body = ch.get("data-type") == "text"
            for s in _exact_sigs(ch.get("d"), M2):
                out.append((rid, body, s))
        else:
            _rec(ch, M2, rid, out)


# ---------------------------------------------------------------- our side

AW = None
CAP = {}


def _load():
    global AW
    if AW is not None:
        return AW
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    AW = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = AW
    spec.loader.exec_module(AW)
    orig = AW.rewrite

    def hook(p, a):
        CAP["page"], CAP["a"] = p, a
        return orig(p, a)
    AW.rewrite = hook
    return AW


def ekey(e):
    return "%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])


def our_contours(pg):
    """[(element key, kind, signature)] from a FRESH in-process build.

    Element contours, not emitted paths: an element is the pipeline's own unit
    and ``e["contours"]`` carries the exact per-contour boxes in the source
    path's frame, which ``page.paths[e["path"]]["M"]`` maps into page space.
    """
    _load()
    with contextlib.redirect_stdout(io.StringIO()):
        AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    paths = CAP["page"].paths
    out = []
    seen = set()
    for word, atoms in CAP["a"]:
        for a in atoms:
            for e in a["els"]:
                if id(e) in seen:
                    continue
                seen.add(id(e))
                M = paths[e["path"]]["M"]
                k = ekey(e)
                for c in e.get("contours") or ():
                    sp = c["sp"]
                    x1, y1, x2, y2 = SL.transform_box(M, sp["xmin"], sp["ymin"],
                                                      sp["xmax"], sp["ymax"])
                    out.append((k, e["kind"],
                                ((x1 + x2) / 2.0, (y1 + y2) / 2.0,
                                 x2 - x1, y2 - y1, 0)))
    return out


# ---------------------------------------------------------------- one page

def page(args):
    pg, refdir, want_dist = args
    try:
        tr = their_runs(pg, refdir)
        if tr is None:
            return pg, None, None
        ours = our_contours(pg)
    except Exception as exc:
        return pg, {"err": "%s: %s" % (type(exc).__name__, str(exc)[:90])}, None
    if len(ours) < 50 or len(tr) < 50:
        return pg, {"err": "too few contours"}, None
    ow = [s for _, _, s in ours]
    tw = [s for _, _, s in tr]
    T = II.estimate(ow, tw)
    if T is None:
        return pg, {"err": "registration failed"}, None
    pairs, _o_only, _t_only = II.match(ow, tw, T)
    if len(pairs) < 0.5 * len(ow):
        # p1/p2 only: the ornate opening spread is set at a DIFFERENT SIZE in
        # the reference and no single scale aligns the two (audit_inkidentity).
        return pg, {"err": "artwork differs (paired %d of %d)"
                    % (len(pairs), len(ow))}, None

    votes = defaultdict(Counter)
    for i, j in pairs:
        if ours[i][1] != "body" or not tr[j][1]:
            continue                      # body ink decides the CUT
        votes[ours[i][0]][tr[j][0]] += 1
    out, split, dist = {}, 0, []
    for k, c in votes.items():
        if want_dist:
            dist.append(c.most_common(1)[0][1] / float(sum(c.values())))
        if len(c) == 1:
            out[k] = c.most_common(1)[0][0]
        else:
            split += 1
    nbody = len({k for k, kind, _ in ours if kind == "body"})
    return pg, {"map": out, "bodies": nbody, "resolved": len(out),
                "split": split, "unpaired": nbody - len(votes),
                "T": [round(v, 5) for v in T],
                "pairs": len(pairs), "contours": len(ow)}, (dist or None)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--ref", default=DEFAULT_REF)
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("QSVG_JOBS", 32)))
    ap.add_argument("--dist", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, ".cache", "mdb_runs.json"))
    args = ap.parse_args(argv)

    from multiprocessing import Pool
    tot = Counter()
    data, dists, bad = {}, [], []
    todo = [(p, args.ref, args.dist) for p in range(args.first, args.last + 1)]
    with Pool(args.jobs, maxtasksperchild=4) as pool:
        for pg, r, d in pool.imap_unordered(page, todo):
            if r is None:
                tot["no-ref"] += 1
                continue
            if "err" in r:
                tot["excluded-pages"] += 1
                bad.append((pg, r["err"]))
                continue
            tot["pages"] += 1
            for k in ("bodies", "resolved", "split", "unpaired", "pairs",
                      "contours"):
                tot[k] += r[k]
            data[str(pg)] = r["map"]
            if d:
                dists += d
    print("pages mapped %d | excluded %d | no reference page %d"
          % (tot["pages"], tot["excluded-pages"], tot["no-ref"]))
    for p, e in bad[:10]:
        print("   p%-4d %s" % (p, e))
    print("contours %d | paired %d (%.3f%%)"
          % (tot["contours"], tot["pairs"],
             100.0 * tot["pairs"] / max(1, tot["contours"])))
    print("body elements %d | run resolved %d (%.3f%%) | contours disagree %d "
          "| unpaired %d"
          % (tot["bodies"], tot["resolved"],
             100.0 * tot["resolved"] / max(1, tot["bodies"]),
             tot["split"], tot["unpaired"]))
    if dists:
        dists.sort()
        n = len(dists)
        print("\nunanimity of an element's contours, %d elements:" % n)
        h = Counter(min(19, int(f * 20)) for f in dists)
        for i in range(20):
            print("   %.2f-%.2f %6d %s" % (i / 20.0, (i + 1) / 20.0, h[i],
                                           "#" * min(60, h[i] // 50)))
    if not args.dist:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        print("\nwrote %s (%.1f MB)"
              % (args.out, os.path.getsize(args.out) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
