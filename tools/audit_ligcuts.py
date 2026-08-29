#!/usr/bin/env python3
"""Compare OUR ligature cut against MushafDatabase's, run by run.

Every audit in this repo judges our decomposition against the TEXT or against
our own geometry. Both are blind to one family: a body piece held by the wrong
word. Mark counts stay perfect, the territory audit and the position laws look
only at marks, and our own geometry cannot tell a real theft from the silent
alef of واو الجماعة because the two are geometrically identical
(docs/defects/STOLEN-LETTERS-2026-08-29.md). The only thing that can is an
OUTSIDE opinion at the ligature-cut level.

MushafDatabase decomposes the same KFGQPC artwork and publishes, per word, one
`<g id="md-ligature-...">` per run with a `data-text` naming the run's letters
and a path carrying its ink. That is exactly our `<g class="ligature">`.

REGISTRATION (measured, not assumed). Their page and ours are the same artwork
in two coordinate systems related by one affine map per page: fitting our word
centres against theirs gives scale 1.3333 (= 4/3) on every page and a constant
offset, with residual median 0.10 our-units and max 0.87 over ~130 words a
page. `--proof` prints the fit and its residuals. So run edges are compared
DIRECTLY in our units; nothing is normalised per word or per line.

WORD ALIGNMENT reuses audit_reference.py's folding: the reference counts a
conjunction waw and a stop sign as words of their own, so both are folded back
into the neighbour they belong to in our numbering before positions are
compared. A word enters the comparison only when the two sides' LETTER
SKELETONS agree, after folding hamza carriers to their bases (ٱأإآ→ا, ؤ→و,
ئى→ي) and dropping tatweel — the two sources encode the carriers differently
and without that fold 30% of words look different when only the encoding is.

Four things are reported, in falling order of how provable they are:

  * missing-ink  — a run both sides name, drawn by them, EMPTY in ours.
                   Its letters are somewhere else. Proof-class.
  * cut          — the run/letter sequences disagree: different number of runs,
                   or the same number covering different letters.
  * extent       — same runs, but our word's ink reaches past theirs (or falls
                   short) by more than the threshold. A ranked prior.
  * ref-empty    — a run WE draw and THEY leave empty (their side's blank).

    python3 tools/audit_ligcuts.py --ref <ref-dir> 1 604 --jobs 32
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
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
NS = "{http://www.w3.org/2000/svg}"
DEFAULT_REF = os.path.expanduser(
    "~/Dev/github.com/AbdullahObaid/MushafDatabase-Ligature-Based-SVG/SVG V1.01")

# ---------------------------------------------------------------- text folding

_LETTERS = set(range(0x0621, 0x064B)) | {0x0671, 0x0672, 0x0673, 0x0675}
# the two sources spell the same letter with different carriers; a cut
# comparison must not see that as a difference.
_FOLD = {0x0671: "ا", 0x0623: "ا", 0x0625: "ا", 0x0622: "ا",
         0x0672: "ا", 0x0673: "ا", 0x0675: "ا",
         0x0624: "و", 0x0626: "ي", 0x0649: "ي"}


def skel(t):
    """The letters only, hamza carriers folded to their base, no tatweel."""
    out = []
    for c in t or "":
        n = ord(c)
        if n == 0x0640:
            continue
        if n in _FOLD:
            out.append(_FOLD[n])
        elif n in _LETTERS:
            out.append(c)
    return "".join(out)


WAQF = "ۖۗۘۙۚۛۜ۝۞۩"

# ---------------------------------------------------------------- joining rules
# The letters that never join to the letter AFTER them. A run of ink (one
# ligature) may therefore contain a non-connector only as its LAST letter;
# anything else is a run the script cannot draw. This is the one piece of
# evidence that convicts a cut without an eye, and it applies to BOTH sides.
_NONCONN = set("اأإآٱٲٳٵدذرزوؤىةء")


def joins_wrong(raw):
    """The letters of `raw` that are non-connectors and not last. Empty = legal."""
    ls = [c for c in raw or "" if ord(c) in _LETTERS or ord(c) in _FOLD]
    return [c for c in ls[:-1] if c in _NONCONN]


def classify(row):
    """OURS-WRONG / THEIRS-WRONG / UNDECIDED, with the evidence, for a cut row."""
    ours = [c for r in row["our_raw"] for c in joins_wrong(r)]
    theirs = [c for r in row["ref_raw"] for c in joins_wrong(r)]
    if ours and not theirs:
        return "OURS-WRONG", ("our run(s) join through %s, which never joins to "
                              "the letter after it" % "/".join(sorted(set(ours))))
    if theirs and not ours:
        return "THEIRS-WRONG", ("their run(s) join through %s, which never joins "
                                "to the letter after it" % "/".join(sorted(set(theirs))))
    if ours and theirs:
        return "UNDECIDED", "both sides draw a run the joining rules forbid"
    return "UNDECIDED", "both cuts are legal under the joining rules"

# ---------------------------------------------------------------- path bbox

_TOK = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?)")
_NARG = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)


def _xspan(d):
    """(min x, max x) of a path's ``d``. Control points count, which for a run
    extent is within a fraction of a unit and needs no curve flattening."""
    toks = [(m.group(1), m.group(2)) for m in _TOK.finditer(d)]
    i, cmd, x, y, sx, sy = 0, None, 0.0, 0.0, 0.0, 0.0
    xs = []
    while i < len(toks):
        if toks[i][0]:
            cmd = toks[i][0]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                continue
        if cmd is None:
            break
        n = _NARG[cmd.upper()]
        a = []
        while len(a) < n and i < len(toks) and toks[i][1] is not None:
            a.append(float(toks[i][1]))
            i += 1
        if len(a) < n:
            break
        rel, c = cmd.islower(), cmd.upper()
        if c == "M":
            x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1])
            sx, sy = x, y
            cmd = "l" if rel else "L"
        elif c == "L":
            x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1])
        elif c == "H":
            x = x + a[0] if rel else a[0]
        elif c == "V":
            y = y + a[0] if rel else a[0]
        elif c in "CSQT":
            pts = [(a[j], a[j + 1]) for j in range(0, len(a), 2)]
            for px, py in pts:
                xs.append(x + px if rel else px)
            x, y = (x + pts[-1][0], y + pts[-1][1]) if rel else pts[-1]
        elif c == "A":
            x, y = (x + a[5], y + a[6]) if rel else (a[5], a[6])
        xs.append(x)
    return (min(xs), max(xs)) if xs else (None, None)


# ---------------------------------------------------------------- their side


def ref_page(pg, refdir):
    """{(surah, ayah, our-pos): {line, hafs, runs:[(text, x1, x2)]}}.

    Folding of waw-alatf and standalone stop signs follows audit_reference.py,
    so the positions key the same words ours do.
    """
    p = os.path.join(refdir, "%03d.svg" % pg)
    if not os.path.exists(p):
        return {}
    root = ET.parse(p).getroot()
    seq = {}
    for w in root.iter(NS + "g"):
        if not (w.get("id") or "").startswith("md-word-"):
            continue
        if w.get("data-type") != "text":
            continue
        try:
            sa = (int(w.get("data-surah")), int(w.get("data-aya")))
            idx = int(w.get("data-word-index-in-ayah"))
        except (TypeError, ValueError):
            continue
        runs = []
        for lig in w:
            if not (lig.get("id") or "").startswith("md-ligature-"):
                continue
            tp = [x for x in lig
                  if x.tag == NS + "path" and x.get("data-type") == "text"]
            if not tp:
                runs.append(("", None, None))
                continue
            spans = [_xspan(x.get("d") or "") for x in tp]
            spans = [s for s in spans if s[0] is not None]
            txt = "".join(x.get("data-text") or "" for x in tp)
            if spans:
                runs.append((txt, min(s[0] for s in spans),
                             max(s[1] for s in spans)))
            else:
                runs.append((txt, None, None))
        seq.setdefault(sa, []).append(
            (idx, int(w.get("data-line-number") or 0), w.get("data-hafs") or "",
             w.get("data-waw-alatf") == "true", runs))
    out = {}
    for sa, items in seq.items():
        items.sort()
        merged, pend_t, pend_r = [], "", []
        for _, ln, txt, waw, runs in items:
            if waw:
                pend_t += txt
                pend_r += runs
                continue
            if txt and all(c in WAQF or c.isspace() for c in txt) and merged:
                continue
            merged.append((ln, pend_t + txt, pend_r + runs))
            pend_t, pend_r = "", []
        if pend_t and merged:
            merged.append((merged[-1][0], pend_t, pend_r))
        for i, (ln, txt, runs) in enumerate(merged, 1):
            out[(sa[0], sa[1], i)] = {"line": ln, "hafs": txt, "runs": runs}
    return out


# ---------------------------------------------------------------- our side

AW = None
CAP = {}


def _load():
    global AW
    if AW is not None:
        return
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    AW = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = AW
    spec.loader.exec_module(AW)
    orig = AW.rewrite
    AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), orig(p, a))[1]


def our_page(pg):
    """{(surah, ayah, pos): {uthmani, runs, segs}} with the EMITTER's groups.

    A `<g class="ligature">` opens only when atom["lig"] changes and its
    data-text is that atom's `seg`; pairing groups to atoms or to
    segment_word() by index names the wrong piece for 3.7% of words (the bug
    audit_ligatures.py fixed on 2026-08-29).
    """
    _load()
    with contextlib.redirect_stdout(io.StringIO()):
        AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    out = {}
    for w, atoms in CAP["a"]:
        if not w:
            continue
        # AN ATOM WITH NO ELEMENTS EMITS NO GROUP. rewrite() opens a
        # <g class="ligature"> when it is about to emit an element whose
        # lig_key changed, so an atom holding nothing never opens one. Checked
        # against the cached page SVGs: modelling one group per atom
        # disagreed with the real output for 20% of the flagged words
        # (p502 هَٰذَا emits ONE group "هذ" holding the alif's ink as a second
        # body, not two groups). Those atoms are kept aside as `unemitted`.
        groups, unemitted = [], []
        for ai, a in enumerate(atoms):
            els = a.get("els") or []
            named = (a.get("seg") or {}).get("text", "")
            if not els:
                unemitted.append(named)
                continue
            lk = a.get("lig", ai)
            if groups and groups[-1]["lig"] == lk:
                groups[-1]["els"].extend(els)
            else:
                groups.append({"lig": lk, "els": list(els), "named": named})
        runs = []
        for g in groups:
            body = [e for e in g["els"] if e["kind"] == "body"]
            runs.append((g["named"],
                         min((e["x1"] for e in body), default=None),
                         max((e["x2"] for e in body), default=None),
                         len(body)))
        out[(w["surah"], w["ayah"], w["pos"])] = {
            "uthmani": w["uthmani"], "runs": runs, "unemitted": unemitted,
            "segs": [s["text"] for s in (AW.segment_word(w["uthmani"]) or [])]}
    return out


# ---------------------------------------------------------------- registration


def fit(ref, mine, keys):
    """Least-squares (scale, offset) from their x to ours, on word centres,
    refit once without residual outliers. Returns (a, b, residuals)."""
    X, Y = [], []
    for k in keys:
        rr = [t for t in ref[k]["runs"] if t[1] is not None]
        oo = [t for t in mine[k]["runs"] if t[1] is not None]
        if not rr or not oo:
            continue
        X.append((min(t[1] for t in rr) + max(t[2] for t in rr)) / 2.0)
        Y.append((min(t[1] for t in oo) + max(t[2] for t in oo)) / 2.0)
    if len(X) < 12:
        return None
    for _ in range(2):
        n = len(X)
        mx, my = sum(X) / n, sum(Y) / n
        den = sum((x - mx) ** 2 for x in X)
        if den <= 0:
            return None
        b = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / den
        a = my - b * mx
        res = [abs(a + b * x - y) for x, y in zip(X, Y)]
        s = sorted(res)
        cut = max(1.0, 6 * s[len(s) // 2])
        keep = [(x, y) for x, y, r in zip(X, Y, res) if r <= cut]
        if len(keep) < 12 or len(keep) == len(X):
            break
        X, Y = [p[0] for p in keep], [p[1] for p in keep]
    return a, b, sorted(res)


# ---------------------------------------------------------------- comparison

EXTENT = 4.0        # our units; see --dist for the distribution behind it


def compare(pg, refdir, extent=EXTENT):
    try:
        ref = ref_page(pg, refdir)
    except Exception as exc:
        return pg, [], Counter({"ref-error": 1}), []
    if not ref:
        return pg, [], Counter({"no-ref-page": 1}), []
    try:
        mine = our_page(pg)
    except Exception:
        return pg, [], Counter({"page-error": 1}), []

    both = sorted(set(ref) & set(mine))
    stats = Counter()
    stats["only_ref"] = len(set(ref) - set(mine))
    stats["only_ours"] = len(set(mine) - set(ref))
    comparable = [k for k in both if skel(ref[k]["hafs"]) == skel(mine[k]["uthmani"])]
    stats["words_both_index"] = len(both)
    stats["excluded_text"] = len(both) - len(comparable)
    f = fit(ref, mine, comparable)
    if not f:
        return pg, [], Counter({"fit-failed": 1}), []
    a, b, res = f
    stats["fit_n"] = len(res)
    rows, gaps = [], []
    for k in comparable:
        stats["comparable"] += 1
        key = "%d:%d:%d" % k
        rr = ref[k]["runs"]
        oo = mine[k]["runs"]
        rtx = [skel(t) for t, _, _ in rr]
        otx = [skel(t[0]) for t in oo]
        sg = [skel(s) for s in mine[k]["segs"]]
        base = {"page": pg, "key": key, "word": mine[k]["uthmani"],
                "hafs": ref[k]["hafs"], "line": ref[k]["line"],
                "ref_runs": rtx, "our_runs": otx, "segs": sg,
                "ref_raw": [t for t, _, _ in rr], "our_raw": [t[0] for t in oo],
                "our_bodies": [t[3] for t in oo],
                "unemitted": mine[k]["unemitted"],
                "segs_match_ref": sg == rtx}
        # word-level ink extent, theirs mapped into our units. This is the
        # signal that separates a letter that LEFT THE WORD from a letter
        # merely grouped into a neighbouring run of the same word.
        rx = [t for t in rr if t[1] is not None]
        ox = [t for t in oo if t[1] is not None]
        if rx and ox:
            r1 = a + b * min(t[1] for t in rx)
            r2 = a + b * max(t[2] for t in rx)
            o1 = min(t[1] for t in ox)
            o2 = max(t[2] for t in ox)
            base.update(d_left=round(o1 - r1, 2), d_right=round(o2 - r2, 2),
                        ours_x=[round(o1, 1), round(o2, 1)],
                        theirs_x=[round(r1, 1), round(r2, 1)])
        if rtx != otx:
            # THEIR CONVENTION, not our defect: a word whose run ends in a
            # lam-alif gets one extra run named "ا" for the alif limb, whose
            # ink overlaps the run before it. 2,163 words mushaf-wide.
            limb = False
            for i in range(len(rtx)):
                if (rtx[i] == "ا" and i and rtx[i - 1].endswith("لا")
                        and rtx[:i] + rtx[i + 1:] == otx):
                    limb = True
                    break
            verdict, why = classify(base)
            if limb:
                verdict, why = ("CONVENTION",
                                "their extra \"ا\" run is the alif limb of a "
                                "lam-alif they list separately; the ink is the "
                                "same on both sides")
            if limb:
                stats["cut-convention"] += 1
                continue
            # A cut row whose WORD EDGE also disagrees past the empty band is
            # not a grouping difference at all — the ink itself changed hands.
            # Measured over the 2,848 cut rows: 2,762 under 1u, nothing at all
            # between 4u and 5u, then two words at 5.7u and 7.7u.
            gap = max(abs(base.get("d_left", 0.0)), abs(base.get("d_right", 0.0)))
            kind = "boundary" if gap > extent else "cut"
            if kind == "boundary":
                verdict = "OURS-WRONG"
                why = ("the WORD EDGE moves too: our word's ink reaches %.1fu "
                       "past theirs, past the %.0fu empty band — a piece has "
                       "changed hands, not just a group" % (gap, extent))
            stats[kind] += 1
            rows.append(dict(base, kind=kind, verdict=verdict, evidence=why,
                             sev=(300 + gap) if kind == "boundary"
                                 else (abs(len(rtx) - len(otx)) or 1),
                             detail="ref %d run(s) [%s] vs ours %d [%s]%s"
                                    % (len(rtx), "|".join(rtx), len(otx),
                                       "|".join(otx),
                                       "; our own segment_word agrees with them"
                                       if sg == rtx else
                                       "; our segment_word says [%s]"
                                       % "|".join(sg))))
            continue
        # same runs, same letters: now the ink
        miss = [i for i, (r, o) in enumerate(zip(rr, oo))
                if r[1] is not None and o[1] is None and skel(r[0])]
        refempty = [i for i, (r, o) in enumerate(zip(rr, oo))
                    if r[1] is None and o[1] is not None]
        if miss:
            # did the letter LEAVE THE WORD, or is it merely in a neighbouring
            # run of the same word? The word's own ink extent settles it: a
            # word that lost a letter is short on the side that letter sits.
            short = max(base.get("d_left", 0.0), -base.get("d_right", 0.0))
            gone = short > extent
            stats["missing-ink" + ("" if gone else "(regrouped)")] += 1
            rows.append(dict(base, kind="missing-ink",
                             sev=(200 if gone else 100) + len(miss),
                             left_word=gone,
                             verdict="OURS-WRONG",
                             evidence=("the letter has LEFT THE WORD: they draw "
                                       "it, we hold no ink for it, and our word "
                                       "is short by more than the %.0fu empty "
                                       "band" % extent) if gone else
                                      ("grouping only: the ink is in a "
                                       "neighbouring run of the SAME word, so "
                                       "the word's extent still matches theirs "
                                       "— the group's data-text names letters "
                                       "it does not hold"),
                             detail="run(s) %s named %s are drawn by them and "
                                    "hold no ink in ours; our word's ink is "
                                    "%.1fu %s than theirs"
                                    % (miss, [rtx[i] for i in miss], abs(short),
                                       "SHORTER" if short > 0 else "longer")))
            continue
        if refempty:
            stats["ref-empty"] += 1
            rows.append(dict(base, kind="ref-empty", sev=1,
                             verdict="THEIRS-WRONG",
                             evidence="we draw ink for a run they leave empty",
                             detail="run(s) %s hold ink in ours and none in "
                                    "theirs" % refempty))
            continue
        if not rx or not ox:
            continue
        # right edge is x2 (RTL: the word starts at the right)
        d_left, d_right = base["d_left"], base["d_right"]
        gaps.append(max(abs(d_left), abs(d_right)))
        if max(abs(d_left), abs(d_right)) > extent:
            stats["extent"] += 1
            side = "left" if abs(d_left) > abs(d_right) else "right"
            d = d_left if side == "left" else d_right
            rows.append(dict(base, kind="extent",
                             sev=min(99, max(abs(d_left), abs(d_right))),
                             verdict="UNDECIDED",
                             evidence="word-edge disagreement past the %.0fu "
                                      "empty band; adjudicate against the "
                                      "neighbour on the same line" % extent,
                             detail="our ink %s the %s edge by %.1fu "
                                    "(ours %.1f..%.1f, theirs %.1f..%.1f)"
                                    % ("overruns" if (d < 0) == (side == "left")
                                       else "falls short of", side, abs(d),
                                       o1, o2, r1, r2)))
    return pg, rows, stats, gaps


def _job(args):
    return compare(*args)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--ref", default=DEFAULT_REF)
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("QSVG_JOBS", 32)))
    ap.add_argument("--extent", type=float, default=EXTENT)
    ap.add_argument("--proof", action="store_true",
                    help="print the registration fit and its residuals")
    ap.add_argument("--dist", action="store_true",
                    help="print the word-edge disagreement distribution")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects",
                                                  "ligature_cuts.json"))
    args = ap.parse_args(argv)

    if args.proof:
        for pg in (3, 50, 143, 300, 384, 500, 579):
            ref, mine = ref_page(pg, args.ref), our_page(pg)
            comp = [k for k in sorted(set(ref) & set(mine))
                    if skel(ref[k]["hafs"]) == skel(mine[k]["uthmani"])]
            f = fit(ref, mine, comp)
            if not f:
                print("p%-4d fit failed" % pg)
                continue
            a, b, res = f
            n = len(res)
            print("p%-4d n=%3d  ours = %.5f * theirs + %.3f   "
                  "residual med %.3f  p90 %.3f  max %.3f"
                  % (pg, n, b, a, res[n // 2], res[int(n * .9)], res[-1]))
        return 0

    from multiprocessing import Pool
    rows, stats, gaps = [], Counter(), []
    todo = [(p, args.ref, args.extent) for p in range(args.first, args.last + 1)]
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, r, s, g in pool.imap_unordered(_job, todo):
            rows += r
            stats.update(s)
            gaps += g

    print("pages %d-%d | words aligned by index %d | excluded (the two sources "
          "split the ayah differently) %d"
          % (args.first, args.last, stats["words_both_index"],
             stats["excluded_text"]))
    print("only in reference %d | only ours %d | page errors %d"
          % (stats["only_ref"], stats["only_ours"],
             stats["page-error"] + stats["ref-error"] + stats["fit-failed"]))
    print("COMPARABLE WORDS %d\n" % stats["comparable"])
    for k in ("missing-ink", "missing-ink(regrouped)", "boundary",
              "cut", "cut-convention", "extent", "ref-empty"):
        print("   %-12s %6d" % (k, stats[k]))
    if args.dist and gaps:
        gaps.sort()
        n = len(gaps)
        print("\nword-edge disagreement, %d words:" % n)
        for q in (50, 75, 90, 95, 99, 99.5, 99.9):
            print("   p%-5s %6.2fu" % (q, gaps[min(n - 1, int(n * q / 100))]))
        print("   max    %6.2fu" % gaps[-1])
        hist = Counter(min(20, int(g)) for g in gaps)
        for i in range(0, 21):
            print("   %2d-%2du %6d %s" % (i, i + 1, hist[i],
                                          "#" * min(60, hist[i] // 40)))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows.sort(key=lambda r: (-r["sev"], r["page"]))
    json.dump(rows, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote %s (%d rows)" % (args.out, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
