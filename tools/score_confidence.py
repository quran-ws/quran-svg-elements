#!/usr/bin/env python3
"""Unified multi-level confidence scorer: mark -> word -> page.

Every existing audit sees one failure mode and is blind to the rest. This tool
computes ALL of their measurements in one pass per page and combines them into a
calibrated per-entity probability of defect, so a word can be ranked, not just
flagged, and a "100% broken" word is separated from a "worth a look" word.

Evidence model (the repo's own epistemology, CLAUDE.md "empty-band proofs"):

  PROOF-class metrics -- an arithmetic fact or a violation of a measured
  empty band in the mushaf-wide distribution. Any single proof makes the
  entity CERTAIN (P = 1.0). The bands, measured over all 604 pages:
    - ligature surplus: joining rules cap a word's piece count (segment_word);
      more effective bodies than the spelling allows is stolen ink, full stop.
    - bodyless: a word holding no letter ink at all.
    - rtl-order: within a line, words must advance right-to-left.
    - stray >= 40u: mark-to-own-letters horizontal gap is bimodal -- 2,735
      within 2u, NOTHING between 40u and 150u, then 17 at 280-308u.
    - band-out >= 15u: 4,203 marks sit 5-10u outside their line's band, 26 at
      10-15u -- a 160x cliff. 15u is past everything legitimate.
    - size outside [1/3, 3] x family median: each family's drawn area is a
      point, not a range (sukun 13.0 at median AND p99). Both tails.

  SOFT metrics -- priors mapped to a suspicion p in [0,1) by piecewise curves
  anchored on the same distributions, combined by noisy-OR:
      P(defect) = 1 - prod(1 - p_i)
  A mark's P folds into its word's P (a certain mark makes a certain word);
  words aggregate into the page score.

Tiers: CERTAIN (any proof) | HIGH (P >= 0.50) | REVIEW (P >= 0.20) | CLEAN.

Usage:
  python3 tools/score_confidence.py 1 604 --jobs 8          # scan + score
  python3 tools/score_confidence.py 350 350 --top 20        # one page
  python3 tools/score_confidence.py 1 604 --html            # + ranked HTML

Raw scans are cached per page under .cache/confidence/raw/ (resumable, like
full_sweep); delete a page's raw JSON after a pipeline change to re-scan it.
Family area medians are computed from the run when it covers >= 50 pages and
cached to .cache/confidence/family_medians.json otherwise the cache is used.
"""
import argparse, contextlib, io, importlib.util, json, math, os, sys
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))
CONF = os.path.join(ROOT, ".cache", "confidence")
RAW = os.path.join(CONF, "raw")

from audit_marks import TEXT_WANT, _DOTU, POLY_SUSPECT  # noqa: E402  (text budgets)

# ---------------------------------------------------------------- scan phase

AW, CAP = None, {}


def _load():
    global AW
    if AW is None:
        sp = importlib.util.spec_from_file_location("assign_words", PIPE)
        AW = importlib.util.module_from_spec(sp)
        sys.modules["assign_words"] = AW
        sp.loader.exec_module(AW)
        _o = AW.rewrite

        def spy(page, a):
            CAP["p"], CAP["a"] = page, a
            return _o(page, a)

        AW.rewrite = spy
    return AW


def _label_status(sig, table):
    v = table.get(sig)
    if v is None:
        return "none"
    return "auto" if (isinstance(v, dict) and v.get("auto")) else "human"


def scan_page(pg):
    """One assign_page run -> raw, score-free observations (pickleable)."""
    aw = _load()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as e:
        return pg, {"error": "%s: %s" % (type(e).__name__, e)}
    page, assignment = CAP["p"], CAP["a"]
    part_key, _ = aw.part_key_for(page)
    table = aw.shape_labels()
    q = aw.qcf_widths()
    # human-confirmed waqf-by-place (the muʿānaqah ۛ has no usable signature;
    # its identity — and therefore its size — is confirmed by geometry key)
    wp = os.path.join(ROOT, ".cache", "marks", "waqf_places.json")
    places = (json.load(open(wp)).get(str(pg), {}) if os.path.exists(wp) else {})

    W = []
    for w, at in assignment:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        rec = {"k": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
               "t": w["uthmani"], "qpc": w.get("qpc"), "els": els, "b": bods}
        if bods:
            ln = [e.get("line") for e in bods if e.get("line")]
            rec["ln"] = max(set(ln), key=ln.count) if ln else 0
            # span over ALL elements, as bench does: a suffix ۥ/ۦ is a MARK
            # here, and a body-only span under-measures exactly those words
            # while their QCF advance counts the suffix
            rec["x1"] = min(e["x1"] for e in els)
            rec["x2"] = max(e["x2"] for e in els)
        W.append(rec)

    # line bands from every word's body ink (audit_crossband's mechanism)
    band = {}
    for x in W:
        if not x["b"]:
            continue
        lo, hi = band.get(x["ln"], (1e9, -1e9))
        band[x["ln"]] = (min(lo, min(e["y1"] for e in x["b"])),
                        max(hi, max(e["y2"] for e in x["b"])))

    # width shares per line (audit_width's mechanism)
    byline = defaultdict(list)
    for x in W:
        if x["b"]:
            byline[x["ln"]].append(x)
    width = {}
    for ln, ws in byline.items():
        tq = sum(q.get(x["k"], 0) for x in ws)
        ta = sum(x["x2"] - x["x1"] for x in ws)
        if not tq:
            continue
        for x in ws:
            qw = q.get(x["k"])
            if not qw:
                continue
            exp = qw / tq * ta
            wd = x["x2"] - x["x1"]
            width[x["k"]] = (round(wd / max(exp, 1e-6), 3), round(abs(wd - exp), 2))

    # rtl order violations per line (audit_marks' mechanism)
    rtl_bad = set()
    for ln, ws in byline.items():
        if ln is None or len(ws) < 2:
            continue
        ws2 = sorted(ws, key=lambda x: tuple(int(v) for v in x["k"].split(":")))
        for i in range(len(ws2) - 1):
            if ws2[i + 1]["x2"] > ws2[i]["x2"] + 1.0:
                rtl_bad.add(ws2[i]["k"])

    out = []
    for x in W:
        txt, els, bods = x["t"], x["els"], x["b"]
        # effective pieces: a stroke drawn over a wider sibling is not a piece
        eff = []
        for b in bods:
            wb = b["x2"] - b["x1"]
            if not any(o is not b
                       and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"]) >= 0.6 * wb
                       and (o["x2"] - o["x1"]) > wb for o in bods):
                eff.append(b)
        have, dots = Counter(), 0
        marks = []
        for e in els:
            if e["kind"] == "body" or e.get("mkpart") or e.get("standalone"):
                continue
            fam = e.get("mark") or ""
            for part in fam.split("+"):
                if part in _DOTU:
                    dots += _DOTU[part]
                elif part:
                    have[part] += 1
            if not fam:
                continue
            gap = 0.0
            if bods:
                gap = -max(min(o["x2"], e["x2"]) - max(o["x1"], e["x1"]) for o in bods)
            lo, hi = band.get(x.get("ln"), (None, None))
            cy = (e["y1"] + e["y2"]) / 2.0
            bout = max(lo - cy, cy - hi, 0.0) if lo is not None else 0.0
            try:
                sig = part_key(e) if part_key else None
            except Exception:
                sig = None
            marks.append({
                "mark": fam,
                "area": round((e["x2"] - e["x1"]) * (e["y2"] - e["y1"]), 2),
                "gap": round(max(gap, 0.0), 1),
                "band_out": round(bout, 1),
                "label": _label_status(sig, table),
                "sig": sig,
                "place_ok": ("%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"],
                             e["x2"], e["y2"])) in places,
                "x": round(e["x1"], 1), "y": round(e["y1"], 1),
            })
        out.append({
            "key": x["k"], "text": txt, "qpc": x["qpc"], "line": x.get("ln"),
            "n_eff": len(eff), "n_seg": max(1, len(aw.segment_word(txt))),
            "bodyless": not bods,
            "dots": dots, "dot_want": aw.dot_budget(txt),
            "have": dict(have),
            "width": width.get(x["k"]),
            "rtl_bad": x["k"] in rtl_bad,
            "marks": marks,
        })
    return pg, {"words": out}


# ---------------------------------------------------------------- score phase
# Piecewise suspicion curves. Every anchor below is a measured mushaf-wide
# distribution, quoted in the module docstring; thresholds sit INSIDE the
# empty band, not at its edge.

def _ramp(v, a, b, pa, pb):
    if v <= a:
        return pa
    if v >= b:
        return pb
    return pa + (pb - pa) * (v - a) / (b - a)


def p_size(area, med, proof_ok=True):
    """A shape's drawn area is a point: outside [1/3, 3] x median is a proof.
    proof_ok=False (pause family, composite labels) caps it as soft evidence:
    the muʿānaqah ۛ is a legitimately tiny member of the pause family, and a
    composite outline's area is the sum of two glyphs."""
    if not med or not area:
        return 0.0, None
    r = area / med
    if r >= 3.0 or r <= 1 / 3.0:
        if proof_ok:
            return 1.0, "size %.1fx median" % r
        return 0.60, None
    if r > 2.0:
        return _ramp(r, 2.0, 3.0, 0.15, 0.60), None
    if r < 0.5:
        return _ramp(1 / r, 2.0, 3.0, 0.15, 0.60), None
    return 0.0, None


def p_stray(gap):
    """Nothing exists between 40u and 150u from a mark's own word."""
    if gap >= 40.0:
        return 1.0, "stray %.0fu from its word" % gap
    if gap <= 2.0:
        return 0.0, None
    return _ramp(gap, 2.0, 40.0, 0.05, 0.65), None


def p_band(d):
    """4,203 marks within 10u of the band, 26 in 10-15u: a 160x cliff."""
    if d >= 15.0:
        return 1.0, "%.0fu outside its line band" % d
    if d <= 5.0:
        return 0.0, None
    if d <= 10.0:
        return 0.05, None
    return _ramp(d, 10.0, 15.0, 0.35, 0.70), None


def p_label(status):
    """A mark whose shape no confirmed label covers is a weak prior only.
    Kept as a per-mark metric; folded into the word only past FOLD_MIN, so a
    word of ten auto-labelled marks does not accumulate false suspicion."""
    return {"none": 0.15, "auto": 0.03, "human": 0.0}[status]


# a mark's P folds into its word only when it is individually meaningful
FOLD_MIN = 0.15


def p_width(w):
    """Ratio outside [0.70, 1.45] AND absolute error >= 4u (audit_width)."""
    if not w:
        return 0.0
    r, off = w
    if off < 4.0 or 0.70 <= r <= 1.45:
        return 0.0
    x = max(r, 1.0 / max(r, 1e-6))
    if x >= 2.0:
        return 0.85
    return _ramp(x, 1.45, 2.0, 0.20, 0.60)


def noisy_or(ps):
    keep = 1.0
    for p in ps:
        keep *= (1.0 - min(max(p, 0.0), 0.999999))
    return 1.0 - keep


def fam_want(word):
    """(lo, hi) budget per family; pause becomes a RANGE where the two text
    editions disagree (audit_marks' rule -- neither edition can be quoted as
    the expectation, so an editorial difference is never convicted)."""
    txt, qpc = word["text"], word.get("qpc")
    out = {}
    for fam, chars in TEXT_WANT.items():
        n = sum(txt.count(c) for c in chars)
        if fam == "pause" and qpc and qpc != txt:
            m = sum(qpc.count(c) for c in chars)
            out[fam] = (min(n, m), max(n, m))
        elif fam == "pause" and qpc:
            n = sum(qpc.count(c) for c in chars)
            out[fam] = (n, n)
        else:
            out[fam] = (n, n)
    return out


def load_ref_lines(path):
    """page -> {key} of words whose LINE disagrees with the outside
    decomposition (audit_reference's reference_lines.json). A page where most
    compared words disagree by one constant offset is a NUMBERING artifact
    (the ornate opening spread), not seventy defects -- drop such pages."""
    if not path or not os.path.exists(path):
        return {}
    rows = json.load(open(path))
    bypg = defaultdict(list)
    for r in rows:
        bypg[r["page"]].append(r)
    out = {}
    for pg, rs in bypg.items():
        offs = Counter(r["ref_line"] - r["our_line"] for r in rs)
        off, n = offs.most_common(1)[0]
        if off != 0 and n >= max(5, 0.8 * len(rs)):
            continue                      # constant-offset numbering artifact
        out[pg] = {r["key"] for r in rs}
    return out


def score_word(word, med, ref_keys=()):
    proofs, soft = [], []
    mk_out = []
    want = fam_want(word)
    have = Counter(word["have"])
    # only families the text budget actually tracks can be in surplus; the
    # iqlab meem is fused into the tanween glyph in this art and is deliberately
    # absent from TEXT_WANT, so it must never be convicted of surplus here
    surplus_f = {f for f in have
                 if f in want and have[f] > want[f][1]}

    for m in word["marks"]:
        mproofs, msoft = [], []
        fam = m["mark"].split("+")[0]
        med_fam, med_sig = med
        # a signature's median beats its family's: each SHAPE has one size,
        # while a family (pause especially) mixes glyphs of very different sizes
        m_med = med_sig.get(m.get("sig")) or med_fam.get(fam)
        size_proof_ok = ("+" not in m["mark"] and fam != "pause"
                         and m.get("sig") in med_sig)
        if m.get("place_ok"):        # identity confirmed by a human, by place
            m_med = None
        for name, (p, pr) in (("size", p_size(m["area"], m_med, size_proof_ok)),
                              ("stray", p_stray(m["gap"])),
                              ("band", p_band(m["band_out"]))):
            if pr:
                mproofs.append(pr)
            elif p:
                msoft.append((name, p))
        p = p_label(m["label"])
        if p:
            msoft.append(("label:" + m["label"], p))
        if fam in surplus_f or (fam in _DOTU and word["dots"] > word["dot_want"]):
            msoft.append(("family-surplus", 0.35))
        P = 1.0 if mproofs else noisy_or([p for _, p in msoft])
        mk_out.append({**{k: m[k] for k in ("mark", "area", "gap", "band_out",
                                            "label", "x", "y")},
                       "P": round(P, 3), "proofs": mproofs,
                       "metrics": {k: round(v, 3) for k, v in msoft},
                       "tier": tier(P, bool(mproofs))})

    if word["n_eff"] > word["n_seg"]:
        proofs.append("ligature surplus %d/%d" % (word["n_eff"], word["n_seg"]))
    if word["bodyless"]:
        proofs.append("bodyless")
    if word["rtl_bad"]:
        proofs.append("rtl-order")
    if word["dots"] != word["dot_want"]:
        # arithmetic, but the label table can misread a blob: near-certain
        soft.append(("dots %d/%d" % (word["dots"], word["dot_want"]), 0.80))
    for fam, (lo, hi) in want.items():
        h = have.get(fam, 0)
        if not (lo <= h <= hi):
            soft.append(("%s %d/%d" % (fam, h, hi), 0.55))
    pw = p_width(word["width"])
    if pw:
        soft.append(("width %.2fx" % word["width"][0], pw))
    if word["key"] in ref_keys:
        # an independent decomposition puts this word on another line; over
        # 67,765 comparable words the two agree on 99.994%, so a real
        # disagreement is strong -- but registration/numbering artifacts
        # exist, so it stays soft, not proof
        soft.append(("ref-line", 0.60))

    # a certain mark makes a certain word; soft marks fold in by noisy-OR
    for mk in mk_out:
        if mk["proofs"]:
            proofs.append("mark %s: %s" % (mk["mark"], mk["proofs"][0]))
        elif mk["P"] >= FOLD_MIN:
            soft.append(("mark:" + mk["mark"], mk["P"]))
    P = 1.0 if proofs else noisy_or([p for _, p in soft])
    return {"key": word["key"], "text": word["text"], "line": word["line"],
            "P": round(P, 3), "tier": tier(P, bool(proofs)),
            "proofs": proofs,
            "metrics": {k: round(v, 3) for k, v in soft},
            "pieces": [word["n_eff"], word["n_seg"]],
            "dots": [word["dots"], word["dot_want"]],
            "width": word["width"], "marks": mk_out}


def tier(P, proven):
    if proven:
        return "certain"
    if P >= 0.50:
        return "high"
    if P >= 0.20:
        return "review"
    return "clean"


# ---------------------------------------------------------------- driver

def family_medians(raws, min_pages=50, min_sig=10):
    """(family->median area, sig->median area). A signature needs min_sig
    samples before its own median is trusted over its family's."""
    cache = os.path.join(CONF, "family_medians.json")
    fam_a, sig_a = defaultdict(list), defaultdict(list)
    for rec in raws.values():
        for w in rec.get("words", ()):
            for m in w["marks"]:
                fam_a[m["mark"].split("+")[0]].append(m["area"])
                if m.get("sig"):
                    sig_a[m["sig"]].append(m["area"])
    med = ({f: sorted(v)[len(v) // 2] for f, v in fam_a.items() if v},
           {s: sorted(v)[len(v) // 2] for s, v in sig_a.items()
            if len(v) >= min_sig})
    if len(raws) >= min_pages:
        json.dump(list(med), open(cache, "w"))
        return med
    if os.path.exists(cache):
        f, s = json.load(open(cache))
        return f, s
    return med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--ref", default=os.path.join(ROOT, "docs", "defects",
                                                  "reference_lines.json"),
                    help="reference line-disagreement JSON ('' to disable)")
    args = ap.parse_args()
    a, b = args.first, args.last or args.first
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(os.path.join(CONF, "pages"), exist_ok=True)

    todo = [p for p in range(a, b + 1)
            if not os.path.exists(os.path.join(RAW, "%03d.json" % p))]
    if todo:
        if args.jobs <= 1 or len(todo) == 1:
            it = map(scan_page, todo)
        else:
            from multiprocessing import Pool
            pool = Pool(args.jobs, maxtasksperchild=8)
            it = pool.imap_unordered(scan_page, todo)
        for pg, rec in it:
            json.dump(rec, open(os.path.join(RAW, "%03d.json" % pg), "w"),
                      ensure_ascii=False)
            print("scan %d (%s)" % (pg, len(rec.get("words", [])) or rec.get("error")),
                  flush=True)

    raws = {}
    for pg in range(a, b + 1):
        f = os.path.join(RAW, "%03d.json" % pg)
        if os.path.exists(f):
            raws[pg] = json.load(open(f))
    med = family_medians(raws)
    ref = load_ref_lines(args.ref)

    tiers, worst, fam_agg = Counter(), [], Counter()
    for pg, rec in sorted(raws.items()):
        if "error" in rec:
            tiers["page-error"] += 1
            continue
        rows = [score_word(w, med, ref.get(pg, ())) for w in rec["words"]]
        page_rec = {"page": pg, "poly_suspect": pg in POLY_SUSPECT,
                    "tiers": dict(Counter(r["tier"] for r in rows)),
                    "words": rows}
        json.dump(page_rec, open(os.path.join(CONF, "pages", "%03d.json" % pg), "w"),
                  ensure_ascii=False)
        for r in rows:
            tiers[r["tier"]] += 1
            if r["tier"] != "clean":
                worst.append((pg, r))
                for name, _ in r["metrics"].items():
                    fam_agg[name.split(" ")[0].split(":")[0]] += 1
                for pr in r["proofs"]:
                    fam_agg["PROOF:" + pr.split(" ")[0].split(":")[0]] += 1

    total = sum(v for k, v in tiers.items() if k != "page-error")
    print("\nwords %d | certain %d | high %d | review %d | clean %d"
          % (total, tiers["certain"], tiers["high"], tiers["review"], tiers["clean"]))
    print("evidence, non-clean words:", dict(fam_agg.most_common(14)))
    worst.sort(key=lambda t: (-(t[1]["tier"] == "certain"), -t[1]["P"]))
    print("\nworst %d:" % min(args.top, len(worst)))
    for pg, r in worst[:args.top]:
        why = r["proofs"] or ["%s=%.2f" % kv for kv in
                              sorted(r["metrics"].items(), key=lambda kv: -kv[1])[:3]]
        print("  p%-4d %-11s %-18s %-7s P=%.2f  %s"
              % (pg, r["key"], r["text"], r["tier"], r["P"], "; ".join(map(str, why))))

    if args.html:
        write_html(worst, os.path.join(ROOT, "docs", "defects", "confidence.html"))


def write_html(worst, path):
    C = {"certain": "#b3261e", "high": "#c77700", "review": "#946f00"}
    rows = []
    for pg, r in worst:
        why = "; ".join(r["proofs"]) if r["proofs"] else \
              "; ".join("%s %.2f" % kv for kv in
                        sorted(r["metrics"].items(), key=lambda kv: -kv[1]))
        rows.append(
            "<tr><td>%d</td><td>%s</td><td class=ar>%s</td>"
            "<td style='color:%s;font-weight:600'>%s</td><td>%.2f</td><td>%s</td></tr>"
            % (pg, r["key"], r["text"], C.get(r["tier"], "#333"), r["tier"],
               r["P"], why))
    open(path, "w").write(
        "<!doctype html><meta charset=utf-8><title>confidence</title><style>"
        "body{font:14px system-ui;margin:24px}table{border-collapse:collapse}"
        "td,th{border-bottom:1px solid #ddd;padding:4px 10px;text-align:left}"
        ".ar{font-size:20px}</style><h2>Words ranked by defect confidence</h2>"
        "<p>certain = a proof-class violation (see score_confidence.py docstring); "
        "high/review = combined soft evidence.</p><table><tr><th>page</th>"
        "<th>word</th><th>text</th><th>tier</th><th>P</th><th>evidence</th></tr>"
        + "".join(rows) + "</table>")
    print("wrote", path)


if __name__ == "__main__":
    main()
