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

from audit_marks import TEXT_WANT, _DOTU, POLY_SUSPECT, RARE_SITES  # noqa: E402  (text budgets)

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
            # span over ALL elements, but a mark stranded 40u+ from the
            # body ink is a DEFECT (audit_strayink's empty band), not width:
            # p418's stray fathas stretched وكفى to 2.7x and poisoned 11
            # neighbouring words' shares (width_diagnosis.md, class c2)
            _bx1 = min(e["x1"] for e in bods); _bx2 = max(e["x2"] for e in bods)
            _in = [e for e in els
                   if e["x1"] >= _bx1 - 40 and e["x2"] <= _bx2 + 40]
            rec["x1"] = min(e["x1"] for e in _in)
            rec["x2"] = max(e["x2"] for e in _in)
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
    # expected width via the pipeline's own hybrid (aw.letters): QCF advance
    # when plausible against the calibrated letter sum, the letter sum where
    # the drift pages scrambled the table (_QCF_SUSPECT is already set by the
    # page build we just captured). This retires the raw-QCF shares that made
    # p592-600 look like chaos (width_diagnosis.md).
    width = {}
    for ln, ws in byline.items():
        exp_l = {}
        _suspect = bool(getattr(aw, "_QCF_SUSPECT", [False])[0])
        for x in ws:
            s0, a0, p0 = (int(v) for v in x["k"].split(":"))
            if _suspect:
                # drift page: the table is scrambled and even plausible
                # advances can belong to other words — pure letter sum,
                # consistent across the whole line
                exp_l[x["k"]] = sum(aw.letter_width(t["text"]) for t in
                                    aw.segment_word(x["t"])) or 3.0
            else:
                exp_l[x["k"]] = aw.letters({"surah": s0, "ayah": a0,
                                            "pos": p0, "uthmani": x["t"]})
        tl = sum(exp_l.values())
        ta = sum(x["x2"] - x["x1"] for x in ws)
        if not tl or not ta:
            continue
        # two-metric agreement (width_diagnosis.md §5): QCF-share and
        # letter-share must BOTH call the word off before width flags it —
        # the ~400 single-metric disagreements are table-vs-ink noise, not
        # defects. On suspect pages only the letter metric exists and stands
        # alone.
        _tq2 = sum(q.get(x["k"], 0) for x in ws)
        for x in ws:
            exp = exp_l[x["k"]] / tl * ta
            wd = x["x2"] - x["x1"]
            r1 = wd / max(exp, 1e-6)
            if not _suspect and _tq2:
                qw = q.get(x["k"], 0)
                if qw:
                    r2 = wd / max(qw / _tq2 * ta, 1e-6)
                    both_off = (min(r1, r2) > 1.5 or max(r1, r2) < 0.62)
                    if not both_off:
                        r1 = 1.0          # metrics disagree -> not a width flag
            width[x["k"]] = (round(r1, 3), round(abs(wd - exp), 2))

    # rtl order violations per line (audit_marks' mechanism)
    rtl_bad = set()
    for ln, ws in byline.items():
        if ln is None or len(ws) < 2:
            continue
        ws2 = sorted(ws, key=lambda x: tuple(int(v) for v in x["k"].split(":")))
        for i in range(len(ws2) - 1):
            if " " in ws2[i]["t"].strip() or " " in ws2[i + 1]["t"].strip():
                continue  # letter-space compound straddles the break
            if ws2[i + 1]["x2"] > ws2[i]["x2"] + 1.0:
                rtl_bad.add(ws2[i]["k"])

    out = []
    for x in W:
        txt, els, bods = x["t"], x["els"], x["b"]
        # effective pieces: a stroke over a wider sibling is not a piece, and
        # pieces whose boxes overlap end-to-end are ONE stroke thinned to a
        # pen-lift (visually verified on p203/p219/p189; genuinely foreign
        # pieces have positive gaps — p451). Mirrors audit_marks exactly.
        parent = list(range(len(bods)))
        def _find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, b in enumerate(bods):
            wb = b["x2"] - b["x1"]
            for j, o in enumerate(bods):
                if o is b:
                    continue
                xov = min(o["x2"], b["x2"]) - max(o["x1"], b["x1"])
                yov = min(o["y2"], b["y2"]) - max(o["y1"], b["y1"])
                if (xov >= 0.6 * wb and (o["x2"] - o["x1"]) > wb) \
                        or (xov > 0.5 and yov > 3.0):
                    parent[_find(i)] = _find(j)
        eff = {_find(i) for i in range(len(bods))}
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


def _lsum(txt):
    """Letter weight of a word: base letters only (marks stripped). Fallback
    width share for lines where the QCF advance table is scrambled (the 26
    layout-drift pages, reported.json item 21: on p599 a 2-letter word
    carries advance 1.71 while a 6-letter one carries 0.58)."""
    import unicodedata
    n = 0
    for c in txt:
        if unicodedata.category(c) == "Mn":
            continue
        if c in " \u06d6\u06d7\u06d8\u06d9\u06da\u06db\u06dc\u06e9\u08f0\u08f1\u08f2\u0640":
            continue
        n += 1
    return max(n, 1)


def _line_expected(pairs):
    """[(key, txt, qcf, drawn_w)] -> {key: expected_w}. QCF shares unless the
    line is suspect (any word's qcf-share/letter-share off by >2.2x or
    <0.45x), then letter-sum shares. Measured: correlation 0.89-0.93 on
    normal pages, 0.59-0.69 on the drift pages."""
    tq = sum(p[2] for p in pairs)
    tl = sum(_lsum(p[1]) for p in pairs)
    ta = sum(p[3] for p in pairs)
    if not tq or not tl or not ta:
        return {}
    suspect = False
    for k, txt, qw, _ in pairs:
        if not qw:
            suspect = True
            break
        r = (qw / tq) / (_lsum(txt) / tl)
        if r > 2.2 or r < 0.45:
            suspect = True
            break
    out = {}
    for k, txt, qw, _ in pairs:
        share = (_lsum(txt) / tl) if suspect else (qw / tq)
        out[k] = share * ta
    return out


def fam_want(word):
    """(lo, hi) budget per family; pause becomes a RANGE where the two text
    editions disagree (audit_marks' rule -- neither edition can be quoted as
    the expectation, so an editorial difference is never convicted)."""
    txt, qpc = word["text"], word.get("qpc")
    _site = tuple(int(v) for v in word["key"].split(":")[:2])
    out = {}
    for fam, chars in TEXT_WANT.items():
        n = sum(txt.count(c) for c in chars)
        if fam in ("saktah", "seen-reading") and RARE_SITES.get(_site) != fam:
            n = 0                 # the ۜ here belongs to the OTHER job (place table)
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
    # Measured against 94 human verdicts (visual_verdicts.json round 3): a
    # width flag with NO companion signal is a false positive far more often
    # than not — justified stretch, the م glyph-shape mismatch, or collateral
    # of a single neighbour's defect. Width alone points, it does not convict.
    if not proofs and soft and all(n.startswith("width") for n, _ in soft):
        P = min(P, 0.45)
    return {"key": word["key"], "text": word["text"], "qpc": word.get("qpc"),
            "line": word["line"],
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
    # human visual verdicts (docs/defects/visual_verdicts.json): a no-issue
    # verdict is a human who looked at the ink — it outranks every metric and
    # removes the word from the report; a confirmed verdict is annotated
    verd = {}
    vp = os.path.join(ROOT, "docs", "defects", "visual_verdicts.json")
    if os.path.exists(vp):
        for rnd in json.load(open(vp)).get("rounds", []):
            for v in rnd.get("verdicts", []):
                verd[(v["page"], v["key"])] = (v["status"], v.get("note", ""),
                                               v.get("sig"))

    tiers, worst, fam_agg = Counter(), [], Counter()
    for pg, rec in sorted(raws.items()):
        if "error" in rec:
            tiers["page-error"] += 1
            continue
        rows = [score_word(w, med, ref.get(pg, ())) for w in rec["words"]]
        # Every steal is a PAIR (Abdullah): a family SURPLUS in one word has a
        # matching DEFICIT nearby — flag BOTH sides and cross-link them, so the
        # victim never audits clean while the thief is flagged.
        deltas = {}
        for r, w0 in zip(rows, rec["words"]):
            have = Counter(w0["have"])
            for fam, (lo, hi) in fam_want(w0).items():
                h = have.get(fam, 0)
                if h > hi:
                    deltas.setdefault(fam, {"sur": [], "def": []})["sur"].append(r)
                elif h < lo:
                    deltas.setdefault(fam, {"sur": [], "def": []})["def"].append(r)
        # rank candidates the way steals actually happen (Abdullah): the word
        # BEFORE/AFTER on the same line first, then ABOVE/BELOW with x-overlap;
        # one counterpart per surplus, nearest rank wins
        order = {r["key"]: i for i, r in enumerate(rows)}
        def _xspan(r):
            xs = [m["x"] for m in r.get("marks", [])]
            return (min(xs), max(xs)) if xs else None
        def _rank(rs, rd):
            if rs.get("line") is None or rd.get("line") is None:
                return None
            dl = abs(rs["line"] - rd["line"])
            di = abs(order[rs["key"]] - order[rd["key"]])
            if dl == 0 and di == 1:
                return (0, di)                        # before/after
            if dl == 1 and di == 1:
                return (1, di)                        # across the line break
                                                      # (the 280-308u family)
            if dl == 1:
                a, b = _xspan(rs), _xspan(rd)
                if a and b and min(a[1], b[1]) - max(a[0], b[0]) > -3.0:
                    return (2, di)                    # above/below, overlapping
            if dl == 0:
                return (3, di)                        # same line, further away
            return None
        for fam, dd in deltas.items():
            for rs in dd["sur"]:
                best = None
                for rd in dd["def"]:
                    if rs is rd:
                        continue
                    rk = _rank(rs, rd)
                    if rk is not None and (best is None or rk < best[0]):
                        best = (rk, rd)
                if best is None:
                    continue
                rd = best[1]
                rs.setdefault("counterparts", []).append(
                    {"key": rd["key"], "fam": fam, "role": "deficit"})
                rd.setdefault("counterparts", []).append(
                    {"key": rs["key"], "fam": fam, "role": "surplus"})
                for x in (rs, rd):
                    if x["tier"] == "clean" and x.get("human") != "no-issue":
                        x["tier"] = "review"
                        x["P"] = max(x["P"], 0.25)
                        x["metrics"]["pair:" + fam] = 0.25
        for r in rows:
            # signature of the card's defect content: a verdict binds to THIS
            # state; when a later build changes it, the verdict goes stale and
            # the card returns for re-review (Abdullah 2026-08-27: "if
            # resolved we need delete my prev review and make me review again")
            import hashlib as _hl
            r["sig"] = _hl.md5(json.dumps(
                [r["tier"], sorted(r["proofs"]), sorted(r["metrics"])],
                ensure_ascii=False).encode()).hexdigest()[:8]
            st = verd.get((pg, r["key"]))
            if not st:
                continue
            if len(st) > 2 and st[2] and st[2] != r["sig"]:
                r["human_stale"] = st          # changed since his verdict
                continue
            r["human"], r["human_note"] = st[0], st[1]
            if st[0] == "no-issue" and r["tier"] != "clean":
                r["tier"], r["P"] = "clean", 0.0
                r["proofs"] = []
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
            elif r.get("human") == "reopened":
                # the eye says still broken even though counts are clean —
                # identity-blind audits cannot see it; never show as fixed
                r2 = dict(r)
                r2["tier"], r2["P"] = "review", max(r2["P"], 0.6)
                r2["metrics"] = {"REOPENED by eye: "
                                 + (r.get("human_note") or ""): 0.6}
                worst.append((pg, r2))
                tiers["review"] += 1
            elif r.get("human_stale"):
                st = r["human_stale"]
                r2 = dict(r)
                r2["tier"], r2["P"] = "review", max(r2["P"], 0.5)
                r2["metrics"] = {"RE-REVIEW: this word CHANGED since your "
                                 "verdict (%s%s)" % (st[0],
                                 (" — " + st[1]) if st[1] else ""): 0.5}
                worst.append((pg, r2))
                tiers["review"] += 1
            elif r.get("human") == "confirmed":
                # a word the reviewer CONFIRMED as defective that now scores
                # clean was FIXED — keep it on the page (green) so the fix can
                # be verified by eye instead of silently vanishing
                r2 = dict(r)
                r2["tier"] = "fixed"
                r2["metrics"] = {"was: " + (r.get("human_note")
                                            or "confirmed defect"): 0.0}
                worst.append((pg, r2))
                tiers["fixed"] += 1

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
    """Interactive visual review page. Serve it THROUGH the review server
    (http://127.0.0.1:8777/confidence) so it can fetch /api/page/N same-origin
    and render each word's actual ink beside its evidence. Cards start
    inactive; a click marks a word as a visually-confirmed defect (persisted
    in localStorage); the toolbar copies the active list to share."""
    import html as _html
    cards = []
    for pg, r in worst:
        why = "; ".join(r["proofs"]) if r["proofs"] else \
              "; ".join("%s %.2f" % kv for kv in
                        sorted(r["metrics"].items(), key=lambda kv: -kv[1]))
        for cp in r.get("counterparts", []):
            why += " ↔ %s of %s (%s)" % (cp["role"], cp["key"], cp["fam"])
        s, a, w = r["key"].split(":")
        # coarse evidence types for the header filter
        types = set()
        for pr in r["proofs"]:
            p0 = pr.split(" ")[0].split(":")[0]
            types.add({"ligature": "ligature-surplus", "mark": None,
                       "rtl-order": "rtl-order", "bodyless": "bodyless"}
                      .get(p0, p0) or "")
            if "outside its line band" in pr:
                types.add("band")
            if "stray" in pr:
                types.add("stray")
            if "size" in pr:
                types.add("size")
        for name, _ in r["metrics"].items():
            if name.startswith("was:"):
                types.add("fixed")
                continue
            n0 = name.split(" ")[0].split(":")[0]
            types.add({"width": "width", "dots": "dots", "mark": "mark-metrics",
                       "ref-line": "ref-line"}.get(n0, "family:" + n0))
        types.discard("")
        # the KFGQPC text of THIS print under the printed ink, never the other
        # edition (the two disagree at 424 waqf positions)
        shown = r.get("qpc") or r["text"]
        cards.append(
            '<div class="card" data-page="%d" data-s="%s" data-a="%s" data-w="%s"'
            ' data-tier="%s" data-p="%.2f" data-flags="%s" data-why="%s">'
            '<button class="xbtn" title="no issue — false positive">✗</button>'
            '<div class="ink"><span class="wait">…</span></div>'
            '<div class="artxt" dir="rtl">%s</div>'
            '<div class="meta"><span class="tier t-%s">%s</span> P=%.2f · '
            '<a href="/?page=%d&step=audit&word=%s" target=_blank>p%d %s</a></div>'
            '<div class="why">%s</div>'
            '<textarea class="note" dir="auto" placeholder="comment…"></textarea>'
            '</div>'
            % (pg, s, a, w, r["tier"], r["P"], " ".join(sorted(types)),
               _html.escape(why, quote=True),
               _html.escape(shown), r["tier"], r["tier"], r["P"],
               pg, r["key"], pg, r["key"], _html.escape(why)))
    doc = _CONF_TMPL.replace("__CARDS__", "\n".join(cards)) \
                    .replace("__N__", str(len(worst)))
    open(path, "w").write(doc)
    print("wrote %s (%d cards) — open http://127.0.0.1:8777/confidence"
          % (path, len(worst)))


_CONF_TMPL = r"""<!doctype html><html><head><meta charset="utf-8">
<title>defect confidence — visual review</title><style>
@font-face{font-family:"QPC Hafs";
  src:url("/assets/UthmanicHafs_V22.ttf") format("truetype");
  font-display:swap}
:root{--certain:#b3261e;--high:#c77700;--review:#946f00;--muted:#8a8577}
body{font:14px system-ui;margin:0;background:#f7f5ef;color:#231f20}
header{position:sticky;top:0;background:#fffdf8;border-bottom:1px solid #ddd7c6;
  padding:10px 18px;display:flex;gap:16px;align-items:center;z-index:5;flex-wrap:wrap}
header h1{font-size:16px;margin:0}
header .count{color:var(--muted)}
header button{font:inherit;padding:6px 14px;border:1px solid #999;border-radius:6px;
  background:#fff;cursor:pointer}
header button:hover{border-color:#245a9e;color:#245a9e}
#banner{background:#fbeeec;color:#b3261e;padding:8px 18px;display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:12px;padding:16px}
.card{border:1px solid #ddd7c6;border-radius:8px;background:#fff;padding:8px;
  cursor:pointer;opacity:.55;transition:opacity .15s, box-shadow .15s;
  position:relative}
.card:hover{opacity:.85}
.card.active{opacity:1;box-shadow:0 0 0 2px #245a9e;border-color:#245a9e}
.card.active::after{content:"✓ confirmed";color:#245a9e;font-weight:600;font-size:12px}
.card.rejected{opacity:.9;box-shadow:0 0 0 2px #8a8577;border-color:#8a8577;
  background:#f3f1ea}
.card.rejected::after{content:"✗ no issue";color:#6c675d;font-weight:600;font-size:12px}
.card.rejected .ink,.card.rejected .artxt{opacity:.45}
.xbtn{position:absolute;top:6px;left:6px;z-index:2;width:24px;height:24px;
  border:1px solid #c9c3b2;border-radius:50%;background:#fff;color:#6c675d;
  font:14px/1 system-ui;cursor:pointer;opacity:0;transition:opacity .15s}
.card:hover .xbtn{opacity:1}
.card.rejected .xbtn{opacity:1;background:#6c675d;color:#fff;border-color:#6c675d}
.xbtn:hover{border-color:#8d3b2f;color:#8d3b2f}
.card.rejected .xbtn:hover{color:#fff}
.ink{height:110px;display:flex;align-items:center;justify-content:center;
  background:#fffdf8;border-radius:4px}
.ink svg{max-width:100%;max-height:106px}
.wait{color:var(--muted)}
.artxt{font-family:"QPC Hafs",serif;font-size:26px;text-align:center;margin:4px 0}
.note{width:100%;box-sizing:border-box;margin-top:6px;border:1px solid #e4dfd2;
  border-radius:4px;font:12.5px system-ui;padding:4px 6px;resize:vertical;
  min-height:26px;height:26px;background:#fffdf8;display:block}
.note:focus{height:56px;border-color:#245a9e;outline:none}
.card.noted .note{border-color:#946f00;background:#fdf8ec}
.meta{font-size:12.5px}
.tier{font-weight:700;text-transform:uppercase;font-size:11px}
.t-certain{color:var(--certain)}.t-high{color:var(--high)}.t-review{color:var(--review)}
.t-fixed{color:#1a7a3a}
.card[data-tier="fixed"]{opacity:.85;border-color:#bcd8c4}
.card[data-tier="fixed"] .ink{background:#f2f8f3}
.why{font-size:11.5px;color:var(--muted);margin-top:2px;line-height:1.35}
.meta a{color:#245a9e}
</style></head><body>
<header><h1>Defect confidence — visual review</h1>
<span class="count"><b id="nact">0</b> confirmed · <b id="nrej">0</b> no-issue of __N__</span>
<button id="copyBtn">Copy confirmed list</button>
<button id="copyJson">Copy as JSON</button>
<button id="clearBtn">Clear all</button>
<label><input type="checkbox" id="onlyCertain"> certain only</label>
<select id="flagSel"><option value="">all evidence types</option></select>
</header>
<div id="banner">Open this page through the review server —
<code>http://127.0.0.1:8777/confidence</code> — so word previews can load.</div>
<div class="grid" id="grid">__CARDS__</div>
<script>
const grid = document.getElementById("grid");
const cards = [...grid.querySelectorAll(".card")];
const KEY = "confidence-active", RKEY = "confidence-rejected";
let active = new Set(JSON.parse(localStorage.getItem(KEY) || "[]"));
let rejected = new Set(JSON.parse(localStorage.getItem(RKEY) || "[]"));
const widOf = c => `${c.dataset.page}:${c.dataset.s}:${c.dataset.a}:${c.dataset.w}`;
function sync(){
  cards.forEach(c => {
    const k = widOf(c);
    c.classList.toggle("active", active.has(k));
    c.classList.toggle("rejected", rejected.has(k));
  });
  document.getElementById("nact").textContent = active.size;
  document.getElementById("nrej").textContent = rejected.size;
  localStorage.setItem(KEY, JSON.stringify([...active]));
  localStorage.setItem(RKEY, JSON.stringify([...rejected]));
}
cards.forEach(c => c.onclick = e => {
  if (e.target.closest("a") || e.target.closest(".note")) return;
  const k = widOf(c);
  if (e.target.closest(".xbtn")) {          // ✗ = false positive, no issue
    rejected.has(k) ? rejected.delete(k) : (rejected.add(k), active.delete(k));
  } else {
    active.has(k) ? active.delete(k) : (active.add(k), rejected.delete(k));
  }
  sync();
});

/* ---- per-word comments, persisted like the active set ---- */
const NKEY = "confidence-notes";
let notes = JSON.parse(localStorage.getItem(NKEY) || "{}");
cards.forEach(c => {
  const ta = c.querySelector(".note");
  const k = widOf(c);
  if (notes[k]) { ta.value = notes[k]; c.classList.add("noted"); }
  ta.addEventListener("input", () => {
    if (ta.value.trim()) notes[k] = ta.value.trim();
    else delete notes[k];
    c.classList.toggle("noted", !!notes[k]);
    localStorage.setItem(NKEY, JSON.stringify(notes));
  });
});
document.getElementById("clearBtn").onclick = () => {
  active.clear(); rejected.clear(); sync();
};
/* evidence-type filter: options built from what the cards actually carry */
const flagSel = document.getElementById("flagSel");
{
  const all = new Set();
  cards.forEach(c => (c.dataset.flags || "").split(" ").forEach(t => t && all.add(t)));
  for (const tr of ["certain","high","review","fixed"]) {
    const n = cards.filter(c => c.dataset.tier === tr).length;
    if (!n) continue;
    const o = document.createElement("option");
    o.value = "tier:" + tr; o.textContent = `tier: ${tr} (${n})`;
    flagSel.appendChild(o);
  }
  [...all].sort().forEach(t => {
    const n = cards.filter(c => (" "+c.dataset.flags+" ").includes(" "+t+" ")).length;
    const o = document.createElement("option");
    o.value = t; o.textContent = `${t} (${n})`;
    flagSel.appendChild(o);
  });
}
function applyFilters(){
  const certOnly = document.getElementById("onlyCertain").checked;
  const t = flagSel.value;
  cards.forEach(c => {
    const okTier = !certOnly || c.dataset.tier === "certain";
    const okFlag = !t || (t.startsWith("tier:")
        ? c.dataset.tier === t.slice(5)
        : (" "+c.dataset.flags+" ").includes(" "+t+" "));
    c.style.display = (okTier && okFlag) ? "" : "none";
  });
}
document.getElementById("onlyCertain").onchange = applyFilters;
flagSel.onchange = applyFilters;
function statusOf(k){
  return active.has(k) ? "CONFIRMED" : rejected.has(k) ? "NO-ISSUE"
                       : "commented";
}
function lineOf(c){
  const k = widOf(c);
  return `p${c.dataset.page} ${c.dataset.s}:${c.dataset.a}:${c.dataset.w} ` +
         `${c.querySelector(".artxt").textContent.trim()} [${statusOf(k)} ` +
         `${c.dataset.tier} P=${c.dataset.p}] ${c.dataset.why}` +
         (notes[k] ? `\n    note: ${notes[k]}` : "");
}
/* the shareable set: confirmed + rejected + commented */
function pickedCards(){
  return cards.filter(c => active.has(widOf(c)) || rejected.has(widOf(c))
                           || notes[widOf(c)]);
}
document.getElementById("copyBtn").onclick = () => {
  const picked = pickedCards();
  const t = `VISUAL REVIEW (${picked.length} words: ${active.size} confirmed, ` +
            `${rejected.size} no-issue, ${Object.keys(notes).length} with notes)\n` +
            picked.map(lineOf).join("\n");
  navigator.clipboard.writeText(t);
};
document.getElementById("copyJson").onclick = () => {
  const t = JSON.stringify(pickedCards().map(c => ({
    page: +c.dataset.page, key: `${c.dataset.s}:${c.dataset.a}:${c.dataset.w}`,
    text: c.querySelector(".artxt").textContent.trim(),
    tier: c.dataset.tier, P: +c.dataset.p, evidence: c.dataset.why,
    status: statusOf(widOf(c)).toLowerCase(),
    note: notes[widOf(c)] || ""})), null, 1);
  navigator.clipboard.writeText(t);
};
sync();

/* ---- lazy ink previews, one /api/page fetch per page ---- */
const pageCache = new Map();          // page -> Promise<holder div>
function pageHolder(pg){
  if (!pageCache.has(pg)) {
    pageCache.set(pg, fetch("/api/page/" + pg).then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(d => {
      const h = document.createElement("div");
      h.style.cssText = "position:absolute;left:-100000px;top:0;width:900px";
      document.body.appendChild(h);
      h.innerHTML = d.svg;
      return h;
    }).catch(e => {
      document.getElementById("banner").style.display = "block";
      throw e;
    }));
  }
  return pageCache.get(pg);
}
const NS = "http://www.w3.org/2000/svg";
async function renderInk(c){
  const holder = await pageHolder(+c.dataset.page);
  const svg = holder.querySelector("svg");
  const sel = `g.word[data-surah="${c.dataset.s}"][data-ayah="${c.dataset.a}"]` +
              `[data-word="${c.dataset.w}"]`;
  const gs = [...svg.querySelectorAll(sel)];
  const box = c.querySelector(".ink");
  if (!gs.length) { box.innerHTML = "<span class=wait>not in build</span>"; return; }
  let X1=1e9, Y1=1e9, X2=-1e9, Y2=-1e9; const clones=[];
  for (const g of gs) {
    let bb; try { bb = g.getBBox(); } catch(e){ continue; }
    if (!bb.width && !bb.height) continue;
    const m = g.getCTM();
    for (const [px,py] of [[bb.x,bb.y],[bb.x+bb.width,bb.y],
                           [bb.x,bb.y+bb.height],[bb.x+bb.width,bb.y+bb.height]]) {
      const x = m.a*px + m.c*py + m.e, y = m.b*px + m.d*py + m.f;
      X1=Math.min(X1,x); Y1=Math.min(Y1,y); X2=Math.max(X2,x); Y2=Math.max(Y2,y);
    }
    const wrap = document.createElementNS(NS, "g");
    wrap.setAttribute("transform",
      `matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
    wrap.appendChild(g.cloneNode(true));
    clones.push(wrap);
  }
  if (!clones.length) { box.innerHTML = "<span class=wait>empty</span>"; return; }
  const mini = document.createElementNS(NS, "svg");
  const pad = 3;
  mini.setAttribute("viewBox",
    `${X1-pad} ${Y1-pad} ${X2-X1+2*pad} ${Y2-Y1+2*pad}`);
  clones.forEach(cl => mini.appendChild(cl));
  box.innerHTML = ""; box.appendChild(mini);
}
const io = new IntersectionObserver(entries => {
  for (const en of entries) if (en.isIntersecting) {
    io.unobserve(en.target);
    renderInk(en.target).catch(() => {});
  }
}, {rootMargin: "300px"});
cards.forEach(c => io.observe(c));
// ?focus=s:a:p from the tasks page: scroll to that card and flash it
(function(){
  var q = new URLSearchParams(location.search).get('focus');
  if (!q) return;
  var p = q.split(':');
  var el = document.querySelector(
    '.card[data-s="'+p[0]+'"][data-a="'+p[1]+'"][data-w="'+p[2]+'"]');
  if (!el) return;
  el.scrollIntoView({block:'center'});
  el.style.outline = '3px solid #f59e0b';
  setTimeout(function(){ el.style.outline=''; }, 4000);
})();
</script></body></html>
"""


if __name__ == "__main__":
    main()
