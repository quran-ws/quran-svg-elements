"""Chunk IDENTITY audit: does each word hold ink drawn to ITS OWN letters?

Piece-COUNT audits are identity-blind: on p254 the body chunks rotated one word
over (بعد ما held هم+بعد's ink; جاءك held ما's) and every count stayed legal —
caught only by eye. This audit scores, for every multi-chunk word in the FINAL
assignment, how well its body chunks' widths fit the widths its own
letter-segments should have, using align_segs_atoms — the same monotone
alignment (with MERGE handling) the clusterer itself uses, so legitimate swash
merges (ـوا۟, ـرًا joined across a non-joining boundary) score well. A naive
1:1 chunk↔segment width comparison was tried first and its top tail was ALL
swash merges; the alignment is what makes the metric usable.

Two signals convict a rotation: the word's own worst-chunk residual is high AND
that chunk — sitting at the word edge — fits a contiguous segment run of the
ADJACENT word on that side markedly better (the rotation signature).

Calibration (clean subset = multi-chunk words with no flag in the lscnt sweep,
no adverse reference verdict, not in reference_words flags; 45,946 of 48,110):

    worst-chunk residual, in mean-segment units (wres):
      p50 0.14  p90 0.40  p99 0.83  p99.9 1.53  max 4.06
      1.5-1.75: 21   1.75-2.0: 6   2.0-2.5: 5   2.5-3.0: 2   3.0+: 2
    alignment cost: p99 0.35, p99.9 0.68, max 2.18
    the clean tail >=1.75 is 15 words in 45,946 (0.03%) — thin, not empty; a
    hard proof band does not exist for widths alone, which is WHY the
    conviction needs the second signal (cross-fit). Thresholds sit at
    wres>=1.20 (clean beyond it: 82 = 0.18%) for a REPORT, and rotation
    conviction additionally needs cross_u <= 0.5*own_u with cross_norm <= 0.35.

Confounders enumerated and tested (see docs/defects/chunkfit_report.md):
swash merges (handled by the aligner's merge move), kashida stretch at
justified line ends (absorbed by per-LINE alpha; line-end words' wres median
0.16 vs 0.14 overall), pen-lift splits (many-atoms↔one-seg groups are legal),
letter-space compounds (each half aligns to its own segs; the inter-half gap
never enters a group span), juz 30 (flag rate reported per region, threshold
not region-tuned).

    python3 tools/audit_chunkfit.py 1 604 8 docs/defects/chunkfit_flags.json
    python3 tools/audit_chunkfit.py 1 604 8 out.json --dump all.json
    python3 tools/audit_chunkfit.py --from-dump all.json out.json

Detection only. Nothing here changes the pipeline.
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter

ROOT = os.environ["QSVG_ROOT"]
AW = None
CAP = {}

# ---- thresholds (from the calibration histogram above) ----
THR_RES = 1.20      # worst-chunk residual (mean-segment units) that earns a report
THR_ROT = 0.90      # residual floor for a rotation conviction (needs cross-fit too)
THR_COST = 0.80     # whole-word alignment cost that earns a report on its own
X_RATIO = 0.50      # cross fit must beat own fit by 2x ...
X_NORM = 0.35       # ... and be a genuinely GOOD fit for the neighbour


def _load_aw():
    global AW
    if AW is None:
        sp = importlib.util.spec_from_file_location(
            "assign_words", os.path.join(ROOT, "tools", "assign_words.py"))
        AW = importlib.util.module_from_spec(sp)
        sys.modules["assign_words"] = AW
        sp.loader.exec_module(AW)
        _o = AW.rewrite
        AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), _o(p, a))[1]
    return AW


def analyze(assignment, pg):
    """Score one page's FINAL assignment. Returns one record per multi-chunk word."""
    aw = _load_aw()
    W = []
    for w, at in assignment:
        if not w:
            continue
        chunks = []
        for a in at:
            b = [e for e in a["els"] if e["kind"] == "body"]
            if not b:
                continue
            ln = [e.get("line") for e in b if e.get("line")]
            chunks.append({"x1": min(e["x1"] for e in b), "x2": max(e["x2"] for e in b),
                           "ln": max(set(ln), key=ln.count) if ln else 0})
        if not chunks:
            continue
        chunks.sort(key=lambda c: -(c["x1"] + c["x2"]))     # RTL reading order
        lns = [c["ln"] for c in chunks if c["ln"]]
        segs = aw.segment_word(w["uthmani"])
        W.append({"k": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                  "t": w["uthmani"], "ch": chunks, "segs": segs,
                  "ln": max(set(lns), key=lns.count) if lns else 0,
                  "lens": [aw.letter_width(s["text"]) for s in segs]})

    # per-LINE absolute per-letter width: line ink span / expected letter total.
    # Justification (kashida stretch, wide word gaps) cancels through this, the
    # same way alpha_cal cancels it inside the clusterer.
    span, need = {}, {}
    for x in W:
        for c in x["ch"]:
            ln = c["ln"] or x["ln"]
            lo, hi = span.get(ln, (1e9, -1e9))
            span[ln] = (min(lo, c["x1"]), max(hi, c["x2"]))
        need[x["ln"]] = need.get(x["ln"], 0.0) + sum(x["lens"])
    alpha = {ln: (span[ln][1] - span[ln][0]) / max(1e-9, need.get(ln, 0.0))
             for ln in span if need.get(ln)}

    out = []
    for wi, x in enumerate(W):
        if len(x["ch"]) < 2 or not x["segs"] or x["segs"][0]["bad"]:
            continue
        al = alpha.get(x["ln"])
        if not al or al <= 0:
            continue
        groups, cost = aw.align_segs_atoms(x["ch"], x["segs"], al)
        mean_len = sum(x["lens"]) / len(x["lens"])
        unit = al * mean_len
        if cost == float("inf"):
            out.append({"p": pg, "k": x["k"], "t": x["t"], "ln": x["ln"],
                        "nch": len(x["ch"]), "nseg": len(x["segs"]),
                        "cost": None, "wres": None, "cat": "align-fail",
                        "chunks": [[round(c["x1"], 1), round(c["x2"], 1)]
                                   for c in x["ch"]]})
            continue
        # per-group residual, absolute and in mean-segment units
        rows = []
        for gi, (ga, gs) in enumerate(groups):
            if not ga or not gs:
                continue
            sp_ = ga[0]["x2"] - ga[-1]["x1"]
            exp = al * sum(aw.letter_width(s["text"]) for s in gs)
            xline = len({c["ln"] for c in ga if c["ln"]}) > 1
            rows.append((abs(sp_ - exp), gi, ga, gs, xline))
        if not rows:
            continue
        own_u, gi, ga, gs, xline = max(rows, key=lambda r: r[0])
        wres = own_u / unit
        side = ("first" if gi == 0 else "last" if gi == len(groups) - 1 else "mid")
        # cross-fit: the suspect chunk against contiguous seg runs of the
        # adjacent word ON THAT SIDE (first group ↔ previous word, last ↔ next;
        # rotations move edge chunks, so only edge groups can convict)
        sp_ = ga[0]["x2"] - ga[-1]["x1"]
        cross = None
        nbs = []
        if side in ("first", "mid") and wi > 0:
            nbs.append(W[wi - 1])
        if side in ("last", "mid") and wi + 1 < len(W):
            nbs.append(W[wi + 1])
        for nb in nbs:
            if not nb["segs"] or nb["segs"][0]["bad"]:
                continue
            anb = alpha.get(nb["ln"]) or al
            mnb = sum(nb["lens"]) / max(1, len(nb["lens"]))
            for i in range(len(nb["lens"])):
                tot = 0.0
                for j in range(i, len(nb["lens"])):
                    tot += nb["lens"][j]
                    d = abs(sp_ - anb * tot)
                    if cross is None or d < cross["u"]:
                        cross = {"u": round(d, 2), "norm": round(d / max(1e-9, anb * mnb), 2),
                                 "nb": nb["k"], "nb_t": nb["t"],
                                 "run": "".join(s["text"] for s in nb["segs"][i:j + 1])}
        rec = {"p": pg, "k": x["k"], "t": x["t"], "ln": x["ln"],
               "wx": [round(min(c["x1"] for c in x["ch"]), 1),
                      round(max(c["x2"] for c in x["ch"]), 1)],
               "lx": round(span.get(x["ln"], (0, 0))[0], 1),
               "nch": len(x["ch"]), "nseg": len(x["segs"]),
               "cost": round(cost, 3), "wres": round(wres, 3),
               "own_u": round(own_u, 2), "unit": round(unit, 2),
               "side": side, "gi": gi, "xline": xline,
               "chunk_x": [round(ga[-1]["x1"], 1), round(ga[0]["x2"], 1)],
               "seg_text": "".join(s["text"] for s in gs), "cross": cross}
        out.append(rec)
    return out


def categorize(r):
    """None = clean; else 'rotation-suspect'|'infeasible'|'width-anomaly'|'unexplained'.

    - infeasible: align_segs_atoms found NO legal alignment — the joining rules
      cannot express the chunks the word holds (a جاءك missing its floating ء,
      or holding a piece that leaves none for a mandatory segment). Same
      standing as segment_word()'s piece count: a proof, not a prior.
    - rotation-suspect: the two-signal conviction — the word's own worst chunk
      misfits ITS letters (wres >= THR_ROT) AND that chunk fits a contiguous
      segment run of the adjacent word at least twice as well, and well in
      absolute terms. Only an edge chunk, or any chunk of a word holding MORE
      chunks than its segments (surplus — where absorbed foreign ink lands
      mid-alignment, as أهواءهم absorbing بعد did on p254), can convict.
    """
    if r.get("cat") == "align-fail":
        return "infeasible"
    if r["wres"] is None:
        return None
    c = r.get("cross")
    edge = r["side"] in ("first", "last")
    surplus = r["nch"] > r["nseg"]
    if (c and (edge or surplus) and r["wres"] >= THR_ROT
            and c["u"] <= X_RATIO * r["own_u"] and c["norm"] <= X_NORM):
        return "rotation-suspect"
    if r["wres"] >= THR_RES:
        return "width-anomaly"
    if (r["cost"] or 0) >= THR_COST:
        return "unexplained"
    return None


def page(pg):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _load_aw().assign_page("hafs/kfqc", pg,
                                   os.path.join(ROOT, ".cache", "words"))
    except Exception:
        return pg, [], Counter({"page-error": 1})
    recs = analyze(CAP["a"], pg)
    return pg, recs, Counter({"words": len(recs)})


def report(recs, out_path):
    import bisect
    ds = sorted(r["wres"] for r in recs if r.get("wres") is not None)
    print("multi-chunk words scored %d" % len(recs))
    print("\nworst-chunk residual, in mean-segment units:")
    for lo, hi in ((0, .25), (.25, .5), (.5, .75), (.75, 1.0), (1.0, 1.2),
                   (1.2, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 100)):
        n = bisect.bisect_left(ds, hi) - bisect.bisect_left(ds, lo)
        print("   %5s - %-5s %6d" % (lo, hi, n))
    flags = []
    for r in recs:
        cat = categorize(r)
        if cat:
            flags.append(dict(r, cat=cat))
    byc = Counter(f["cat"] for f in flags)
    print("\nflags %d: %s" % (len(flags), dict(byc)))
    rot = sorted([f for f in flags if f["cat"] == "rotation-suspect"],
                 key=lambda f: -f["wres"])
    print("\nrotation-suspects (own misfit + the chunk fits the neighbour):")
    for f in rot[:30]:
        c = f["cross"]
        print("   p%-4d %-10s %-16s chunk[%s] x %s wres %.2f own_u %.1f -> "
              "fits %s '%s' at %.1fu (norm %.2f)"
              % (f["p"], f["k"], f["t"], f["side"], f["chunk_x"], f["wres"],
                 f["own_u"], c["nb"], c["run"], c["u"], c["norm"]))
    json.dump(flags, open(out_path, "w"), ensure_ascii=False, indent=1)
    print("\nwrote %s (%d flags)" % (out_path, len(flags)))
    return flags


if __name__ == "__main__":
    if sys.argv[1] == "--from-dump":
        recs = json.load(open(sys.argv[2]))
        report(recs, sys.argv[3])
        sys.exit(0)
    from multiprocessing import Pool
    recs = []
    tot = Counter()
    with Pool(int(sys.argv[3]), maxtasksperchild=8) as pool:
        for pg, out, c in pool.imap_unordered(
                page, range(int(sys.argv[1]), int(sys.argv[2]) + 1)):
            recs += out
            tot.update(c)
    if tot.get("page-error"):
        print("page-errors: %d" % tot["page-error"])
    if "--dump" in sys.argv:
        dp = sys.argv[sys.argv.index("--dump") + 1]
        json.dump(recs, open(dp, "w"), ensure_ascii=False)
        print("dumped %d records to %s" % (len(recs), dp))
    report(recs, sys.argv[4])
