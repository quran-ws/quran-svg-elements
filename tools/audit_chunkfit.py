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

Calibration (clean subset = multi-chunk words with no flag in the r7fix sweep,
no reference verdict, not in reference_words flags; 51,815 of 52,105 scored,
measured 2026-08-27 on the post-R7 build):

    worst-chunk residual, in mean-segment units (wres):
      p50 0.233  p90 0.492  p99 0.814  p99.9 1.485  max 2.39
      1.0-1.2: 127   1.2-1.5: 48   1.5-1.75: 30   1.75-2.0: 16
      2.0-2.5: 4     2.5+: 0
    alignment cost: p99 0.465, p99.9 0.842, max 1.79

    There is NO empty band: the clean tail thins but never empties, and it is
    dominated by one calligraphic convention — the elongated final ن of
    إِنَّ / أَنَّ before the next word (74 of the top-100). So the width
    residual alone is a REVIEW signal, never a proof, and the audit does not
    pretend otherwise: a rotation CONVICTION needs three signals agreeing —
    (1) own worst-chunk residual >= THR_ROT, (2) that chunk fits a contiguous
    segment run of the adjacent word 2x better and well absolutely, and
    (3) the donor word itself misfits >= NB_DAMAGE on the side FACING the
    suspect (a real exchange damages both parties, on facing edges).
    Dropping any one gate was measured: without (3) the list is 220 words,
    ~95% the إنّ ٱللَّه stretch; with (3) but ignoring WHICH side the donor
    misfits on, 16, ~10 of them الله's systematic 0.60-0.65 'لله' model error.

Confounders enumerated and tested (counts on the clean subset; see
docs/defects/chunkfit_report.md for the reversed-flag audit):
swash وا۟ merges n=2,901, 0 at wres>=1.2 (the aligner's merge move absorbs
them — the naive 1:1 prototype's whole top tail was this family); ـرًا endings
n=443, 0; letter-space compounds n=4, 0 (each half aligns to its own segments;
the inter-half gap never enters a group span); line-end words n=6,381, 5
(0.08%, per-LINE alpha absorbs justification); juz 30 n=1,563, 3 (0.19%);
pen-lift splits nch<nseg n=1,539, 4 (many-atoms-to-one-segment groups are
legal); surplus nch>nseg n=1,069, 1. Two artefact families were found by this
calibration and are handled IN the metric: the standalone-ء the print draws as
a diacritic (dual hamza model below — before it, the ٱلسَّمَآءِ/رَءَا family
sat at wres 2.4-2.5 and رَءَا was infeasible outright), and the إنّ final-ن
stretch (tagged fam=final-nun-stretch in the output, never convicted).

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
NB_DAMAGE = 0.60    # the donor word must itself misfit (pair-damage gate)


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
        # Two hamza models. segment_word expects a standalone ء as its own tiny
        # body, but the print draws many of them as a DIACRITIC above the join
        # (the whole ٱلسَّمَآءِ / رَءَا family) — scoring only the body model
        # put every such word in the residual tail (wres ~2.4, a solid band of
        # audit artefacts) and made رَءَا infeasible outright. Score both and
        # keep the model the ink itself prefers.
        cands = [("b", x["segs"], x["lens"])]
        if any(s["text"] == "ء" for s in x["segs"]):
            sB = [s for s in x["segs"] if s["text"] != "ء"]
            if sB:
                cands.append(("m", sB, [aw.letter_width(s["text"]) for s in sB]))
        best = None
        for hz, sgs, lens in cands:
            groups, cost = aw.align_segs_atoms(x["ch"], sgs, al)
            if best is None or (cost < best[1]):
                best = (groups, cost, hz, sgs, lens)
        groups, cost, hz, sgs, lens = best
        mean_len = sum(lens) / len(lens)
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
               "nch": len(x["ch"]), "nseg": len(sgs), "hz": hz,
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


def flag_records(recs):
    """Apply categorize + the PAIR-DAMAGE gate; returns the flagged list.

    A genuine exchange damages BOTH parties: the word that absorbed foreign ink
    misfits, and the word it was taken from is short. Without this gate the
    rotation rule's list is ~95% one calligraphic convention — إِنَّ / أَنَّ
    with the final ن stretched before ٱللَّهِ, whose stretch happens to equal
    الله's expected width (measured: 214 clean-word hits, the إن family the
    bulk). Requiring the cross-fit neighbour to ALSO score wres >= NB_DAMAGE,
    or be infeasible, keeps p254's conviction (its neighbour scored 0.68) and
    drops the stretch family (their neighbours are clean).
    """
    by_key = {r["k"]: r for r in recs}

    def _kt(k):
        return tuple(int(x) for x in k.split(":"))

    out = []
    for r in recs:
        cat = categorize(r)
        if not cat:
            continue
        if cat == "rotation-suspect":
            nbk = (r.get("cross") or {}).get("nb", "")
            nb = by_key.get(nbk)
            # The damage must be on the donor's side FACING the suspect. All
            # ~10 إِنَّ→ٱللَّهِ pairs that slipped the plain wres gate had the
            # donor الله misfitting mildly (0.60-0.65) on its FAR side ('لله',
            # last) — a systematic لله-ligature width error, not a donation.
            facing = "first" if _kt(nbk) > _kt(r["k"]) else "last"
            damaged = nb and (nb.get("cat") == "align-fail"
                              or ((nb.get("wres") or 0) >= NB_DAMAGE
                                  and nb.get("side") == facing))
            if not damaged:
                cat = "width-anomaly" if r["wres"] >= THR_RES else None
        if not cat:
            continue
        f = dict(r, cat=cat)
        # the elongated final ن before the next word (إِنَّ ٱللَّهَ and kin) is
        # a calligraphic CONVENTION this script uses freely — mark the family
        # so the review list does not drown in it
        if cat == "width-anomaly" and r.get("seg_text") == "ن" and r["side"] == "last":
            f["fam"] = "final-nun-stretch"
        out.append(f)
    return out


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
    flags = flag_records(recs)
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
