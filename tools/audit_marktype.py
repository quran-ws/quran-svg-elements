#!/usr/bin/env python3
"""A mark whose NAME is geometrically inconsistent with what that family IS.

    python3 tools/audit_marktype.py 1 604 8 out.json

Companion doc: docs/defects/marktype_rules.md — the measured distribution behind
every threshold, the exceptions found while challenging each rule, the
confounders each rule was tested against, and the rules REJECTED and why.

Two phases. The COLLECTOR runs the pipeline once per page and caches every
mark's geometry plus its word's context to .cache/marktype/NNN.json (resumable,
like audit_marks; QSVG_MTCACHE overrides the directory for A/B runs). The
RULES phase reads only the cache, so thresholds are re-derivable without
touching the pipeline.

Method (CLAUDE.md's empty-band rule): every distribution was measured FIRST on
the CLEAN subset only — words with no flag in .cache/sweeps/xband and no
adverse visual verdict — so the baseline is not learned from the very defects
being audited (circularity). Rules are then applied to everything; a threshold
is trusted only where the clean-subset distribution shows an EMPTY BAND around
it, and it goes INSIDE the band, not at its edge.

What this audit does NOT do:
 - size vs family median: tools/audit_marksize.py owns that.
 - counts vs the text: scratchpad/audit_marks.py owns that.
 - cross-line ownership >=15u outside the band: QSVG_XBAND repairs it and
   tools/audit_crossband.py detects it; flags here in that zone are category
   "ownership-suspect" with the overlap noted, never a new verdict.
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter, defaultdict

ROOT = os.environ["QSVG_ROOT"]
CACHE = os.environ.get("QSVG_MTCACHE") or os.path.join(ROOT, ".cache", "marktype")

# ---------------------------------------------------------------------------
# text budgets (same tables the pipeline and audit_marks use; never hand-typed)
# ---------------------------------------------------------------------------
TANW = {"tanwin_al_fath": "ًࣰ", "tanwin_al_kasr": "ٍࣲ", "tanwin_al_damm": "ٌࣱ"}
# KFGQPC open-tanwin signs: drawn as a stroke PAIR (stacked/diagonal), no meem
# — measured on the لأيات family, whose QPC ends U+0656 and whose ink is two
# strokes below the word (marktype_rules.md §iqlab)
OPEN_TANW = {"tanwin_al_fath": "ٗ", "tanwin_al_kasr": "ٖ", "tanwin_al_damm": "٘"}
PLAIN_CH = {"tanwin_al_fath": "َ", "tanwin_al_kasr": "ِ", "tanwin_al_damm": "ُ"}
# marks this art never draws below their letter (assign_words._ABOVE_ONLY)
ABOVE_ONLY = {"dammah", "tanwin_al_damm", "waqf", "sukun", "shaddah", "small_circle",
              "rounded_zero", "rectangular_zero", "saktah", "seen_al_qiraah",
              "small_waw", "omitted_alif", "maddah", "hamzat_al_wasl"}
# waqf signs the TEXT itself places low (U+06EA/U+06E3 below-letter stops):
# p226 مَجْر۪ىٰهَا carries ۪ and its waqf sits 2.9u below the band — legal
LOW_WAQF = "۪ۣ"
DOTV = {"dot": 1, "two_dots": 2, "three_dots": 3}
DOT_W = 2.38          # one drawn dot blob, page units (QSVG_DOTLBL, measured)
# waqf signs, both editions' repertoires (same set audit_marks budgets with)
# ۜ (U+06DC) left with taxonomy phase 1: its marks are now named
# saktah/seen_al_qiraah by place, so it neither counts in the waqf budget nor
# in the held waqf marks -- both sides drop together.
WAQF_CH = "ۖۗۘۙۚۛ" + "۪ۣ۬۫"
DAMMAH_CH = "ٌࣱُ"


def iqlab_singles(u, q, fam):
    """Tanwin positions of `fam` the print draws as ONE stroke.

    The single-stroke convention is IQLAB's (docs/defects/iqlab_notation.md),
    and the reliable detector is the QPC text of THIS print: a PLAIN harakah
    followed by the small meem (U+06E2/U+06ED). Reading rasm_uthmani's tanwin+meem
    instead over-matches: at 6:99:42 لأيات rasm_uthmani writes U+064D U+06E2 but QPC
    writes U+0656 with NO meem, and the ink is a stroke PAIR — an open tanwin,
    not an iqlab. Measured: all 10 لأيات occurrences draw the pair below.
    """
    if q:
        return sum(1 for i in range(len(q) - 1)
                   if q[i] == PLAIN_CH[fam] and q[i + 1] in "ۭۢ")
    # no QPC text: fall back to rasm_uthmani tanwin+meem (over-matches open tanwin)
    return sum(1 for i in range(len(u) - 1)
               if u[i] in TANW[fam] and u[i + 1] in "ۭۢ")


# ---------------------------------------------------------------------------
# collector
# ---------------------------------------------------------------------------
AW = None
CAP = {}


def collect(pg):
    global AW
    if AW is None:
        sp = importlib.util.spec_from_file_location(
            "assign_words", os.path.join(ROOT, "tools", "assign_words.py"))
        AW = importlib.util.module_from_spec(sp)
        sys.modules["assign_words"] = AW
        sp.loader.exec_module(AW)
        _o = AW.rewrite
        AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), _o(p, a))[1]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as e:
        return pg, {"error": str(e)}
    words = []
    for w, at in CAP["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        ln = [e.get("line") for e in bods if e.get("line")]
        rec = {"key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
               "u": w["rasm_uthmani"], "q": w.get("qpc") or "",
               "ln": max(set(ln), key=ln.count) if ln else 0,
               "dots_budget": AW.dot_budget(w["rasm_uthmani"]),
               "b": [[round(e["x1"], 1), round(e["y1"], 1),
                      round(e["x2"], 1), round(e["y2"], 1)] for e in bods],
               "m": []}
        for e in els:
            if e["kind"] == "body" or e.get("mkpart"):
                continue
            mem = [[round(m["x1"], 1), round(m["y1"], 1), round(m["x2"], 1),
                    round(m["y2"], 1), m.get("mark") or ""]
                   for m in (e.get("mkmembers") or [])]
            rec["m"].append({"f": e.get("mark") or e["kind"],
                             "x1": round(e["x1"], 1), "y1": round(e["y1"], 1),
                             "x2": round(e["x2"], 1), "y2": round(e["y2"], 1),
                             "fused": bool(e.get("fused")),
                             "sa": bool(e.get("standalone")),
                             "sig": e.get("sig", ""), "mem": mem})
        words.append(rec)
    return pg, {"words": words}


def ensure_cache(a, b, jobs):
    os.makedirs(CACHE, exist_ok=True)
    todo = [p for p in range(a, b + 1)
            if not os.path.exists(os.path.join(CACHE, "%03d.json" % p))]
    if not todo:
        return
    from multiprocessing import Pool
    with Pool(jobs, maxtasksperchild=8) as pool:
        for pg, rec in pool.imap_unordered(collect, todo):
            json.dump(rec, open(os.path.join(CACHE, "%03d.json" % pg), "w"),
                      ensure_ascii=False)
            print("collected %d (%d words)" % (pg, len(rec.get("words", []))),
                  flush=True)


# ---------------------------------------------------------------------------
# clean subset: pages/words with no flag in the current sweep and no adverse
# human verdict — the baseline distributions come from HERE only (circularity
# guard: a rule learned on the defects it hunts codifies them)
# ---------------------------------------------------------------------------
def load_dirty():
    dirty = set()
    sw = os.path.join(ROOT, ".cache", "sweeps", "xband")
    if os.path.isdir(sw):
        for f in os.listdir(sw):
            try:
                d = json.load(open(os.path.join(sw, f)))
            except Exception:
                continue
            pg = d.get("page")
            for r in d.get("marks", []):
                dirty.add((pg, r["key"]))
            for r in d.get("intervals", []):
                dirty.add((pg, r.get("key")))
    vv = os.path.join(ROOT, "docs", "defects", "visual_verdicts.json")
    noissue = set()
    if os.path.exists(vv):
        for rnd in json.load(open(vv)).get("rounds", []):
            for v in rnd.get("verdicts", []):
                if v.get("status") == "confirmed":
                    dirty.add((v["page"], v["key"]))
                elif v.get("status") == "no-issue":
                    noissue.add((v["page"], v["key"]))
    return dirty, noissue


def blobs(w):
    return max(1, int(round(w / DOT_W)))


# ---------------------------------------------------------------------------
# the rules. Clean-subset histograms measured over all 604 pages, 2026-08-26,
# with .cache/sweeps/xband + confirmed visual verdicts as the dirty filter
# (~118k fathah, 44k kasrah, 36k dammah, 2.5k of each stroke tanwin).
# ---------------------------------------------------------------------------
def run_rules(pages, dirty, noissue, dist_only=False):
    flags = []
    stats = defaultdict(list)
    rule_n = Counter()
    fam_n = Counter()

    for pg in pages:
        f = os.path.join(CACHE, "%03d.json" % pg)
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        words = d.get("words", [])
        lb = {}
        for w in words:
            if not w["b"]:
                continue
            lo, hi = lb.get(w["ln"], (1e9, -1e9))
            lb[w["ln"]] = (min(lo, min(b[1] for b in w["b"])),
                           max(hi, max(b[3] for b in w["b"])))
        # header/basmalah/ornate lines distort vertical position (confounder:
        # band geometry): words on a line whose band is over 1.6x the page
        # median height are measured but never flagged
        hts = sorted(hi - lo for lo, hi in lb.values() if hi > lo)
        medh = hts[len(hts) // 2] if hts else 0.0

        for w in words:
            if not w["b"]:
                continue
            clean = (pg, w["key"]) not in dirty
            odd_line = medh and (lb[w["ln"]][1] - lb[w["ln"]][0]) > 1.6 * medh
            by1 = min(b[1] for b in w["b"])
            by2 = max(b[3] for b in w["b"])
            u, q = w["u"], w["q"]
            masters = [m for m in w["m"] if not m["sa"]]
            have = Counter(m["f"] for m in masters)

            def emit(rule, cat, m, note, fix=None):
                fam_n[m["f"]] += 1
                rule_n[rule] += 1
                flags.append({
                    "page": pg, "key": w["key"], "text": u, "rule": rule,
                    "category": cat, "mark": m["f"],
                    "x1": m["x1"], "y1": m["y1"], "x2": m["x2"], "y2": m["y2"],
                    "band_y1": round(by1, 1), "band_y2": round(by2, 1),
                    "note": note, "proposed": fix,
                    "verdict_no_issue": (pg, w["key"]) in noissue,
                    "clean_word": clean, "odd_line": bool(odd_line)})

            for m in masters:
                fam = m["f"]
                cy = (m["y1"] + m["y2"]) / 2
                sbelow = cy - by2          # +ve: centre below word band bottom
                sabove = by1 - cy          # +ve: centre above word band top
                llo, lhi = lb[w["ln"]]
                outband = max(llo - cy, cy - lhi, 0.0)
                stats[("cl" if clean and not odd_line else "dt", fam)].append(
                    (round(sbelow, 1), round(sabove, 1), round(outband, 1)))
                if dist_only or odd_line:
                    continue

                # R9 ownership-suspect: >10u outside its own line band.
                # Overlaps audit_crossband/QSVG_XBAND by design: XBAND repairs
                # >=15u where budgets agree, so what still shows here is the
                # residue XBAND refused (budget said no) plus the 10-15u zone
                # (26 marks mushaf-wide). 10u is the crossband cliff: 4,203
                # marks <=10u outside their band, 26 in 10-15u, ~0 legit
                # beyond. Worth eyes, never auto-repair from here.
                if outband > 10.0:
                    emit("R9-outband", "ownership-suspect", m,
                         "%.1fu outside own line band (crossband/XBAND "
                         "territory; a survivor here means the budget gate "
                         "refused the move)" % outband)
                    continue           # position is not owner-relative now

                # R1: a fathah-family slash BELOW its word's body band. Clean
                # subset, sbelow histogram (n=118,379 fathah):
                #   <=0: 118,343 | 0-1: 3 | 1-2: 3 | 2-3: 11 | 3-4: 0 |
                #   4-8: 15 | 8+: 4
                # The 0-2 stragglers are a final-letter fathah grazing the band
                # bottom (لَهُمْ p100 +0.3, رَيْبَ p501 +0.3) — legitimate.
                # Everything sampled at 2u+ was a defect: the لأيات
                # name-crossing cluster at ~2.5 (10 words, see R2) and stolen
                # strays at 4-15u (ٱلصَّلَوٰةَ p437 +14.6 holds تِجَـٰرَةًۭ's
                # fathah, confirmed by that word's fathah 1/2). Threshold 2.0 —
                # above every verified-legitimate case.
                if fam in ("fathah", "tanwin_al_fath") and sbelow > 2.0:
                    fix = {"fathah": "kasrah", "tanwin_al_fath": "tanwin_al_kasr"}[fam]
                    emit("R1-fathah-below", "name-swap", m,
                         "centre %.1fu BELOW its word's body band; a fathah "
                         "rides above its letter" % sbelow, fix)

                # R2: a kasrah-family mark ABOVE its word's band TOP (the
                # ascender top — a kasrah tucked under a shaddah still sits well
                # below it). Clean subset, sabove:
                #   kasrah   (n=44,437): 3 in 0-1, 1 at 2.3 (غَيْرِ p508, flag
                #           kept — matches the stolen-slash pattern), rest <=0
                #   tanwin_al_kasr (n=2,467): EMPTY from -4 to +1, then 8 — all the
                #           لأيات cluster. Threshold: kasrah 2.0, tanwin_al_kasr 0.0
                #           (inside the empty band, not at its edge).
                elif fam == "kasrah" and sabove > 2.0:
                    emit("R2-kasrah-above", "name-swap", m,
                         "centre %.1fu ABOVE its word's band top (above even "
                         "the ascenders); a kasrah hangs below" % sabove,
                         "fathah")
                elif fam == "tanwin_al_kasr" and sabove > 0.0:
                    emit("R2-tanwin-al-kasr-above", "name-swap", m,
                         "tanwin_al_kasr %.1fu above its word's band top — "
                         "impossible; where welded from two strokes these are "
                         "the word's fathahs, and its true tanwin_al_kasr pair sits "
                         "below named fathah+fathah (the لأيات pattern)"
                         % sabove, "fathah+fathah")

                # R3: an above-only family below the band. Clean subset:
                # dammah/tanwin_al_damm/tanwin_al_fath/maddah/shaddah/sukun/hamzat_al_wasl/
                # omitted_alif/small_circle/three_dots have NOTHING above
                # sbelow=-4 (n=36k dammah .. 2.4k tanwin_al_damm); waqf has ONE — the
                # low-stop ۪ of مَجْر۪ىٰهَا p226 (+2.9), exempted by its text.
                # small_meem is EXCLUDED: the low ۭ form legitimately hangs to
                # 11.5u below (19 clean words measured), and QSVG_IQFIX/IQLATE
                # already police the high ۢ with the text signal.
                elif fam in ABOVE_ONLY and sbelow > 2.0:
                    if fam == "waqf" and any(c in u or c in q
                                              for c in LOW_WAQF):
                        pass          # the text draws this stop low
                    else:
                        emit("R3-above-only-below", "unexplained", m,
                             "%s %.1fu below the word's body band; this art "
                             "never draws one there" % (fam, sbelow))

            if dist_only:
                continue

            # ---- pair rules ----
            for fam in ("tanwin_al_fath", "tanwin_al_kasr", "tanwin_al_damm"):
                want = sum(u.count(c) for c in TANW[fam])
                if not want and have.get(fam, 0) == 0:
                    continue
                singles_ok = iqlab_singles(u, q, fam)
                mine = [m for m in masters if m["f"] == fam]
                for m in mine:
                    same = [x for x in m["mem"] if x[4] == fam]
                    if same:
                        a = same[0]
                        dx = abs((m["x1"] + m["x2"]) / 2 - (a[0] + a[2]) / 2)
                        dy = abs((m["y1"] + m["y2"]) / 2 - (a[1] + a[3]) / 2)
                        # R5 intra-pair spacing. Clean welded pairs measured:
                        # dx <=6 for all but 10 tanwin_al_kasr at 6-8 — the OPEN
                        # tanwin ٖ drawn as a DIAGONAL pair (مُتَكَبِّرٍۢ
                        # p470 dx 7.4, شَجَرٍۢ p536 7.5 — verified legit);
                        # dy <=6 everywhere. Nothing beyond 8 on either axis
                        # (the weld windows cap at 8/7), so this is an
                        # invariant guard for future movers, not a live rule.
                        if dx > 8.0 or dy > 8.0:
                            emit("R5-pair-spacing", "pair-grouping", m,
                                 "welded %s strokes %.1f/%.1fu apart — "
                                 "implausible pair" % (fam, dx, dy))
                # R4: a stroke-tanwin master with NO twin where the print
                # draws a full pair. tanwin_al_fath/tanwin_al_kasr are drawn as TWO
                # strokes in this art (tanwin_al_damm alone has a one-outline glyph
                # and is exempt); single strokes are correct only at QPC
                # iqlab positions (plain harakah + small meem) or in a fused
                # compound. Only judged when masters == budget exactly, so
                # count errors stay with audit_marks. Measured: 4 words in
                # the whole mushaf (بَغْتَةً p133, زَانِيَةً p350 line 6,
                # فِدَآءً p507, جُرُفٍ p204) — every one in or beside a known
                # steal cluster.
                if fam in ("tanwin_al_fath", "tanwin_al_kasr") and want \
                        and len(mine) == want:
                    paired = sum(1 for m in mine
                                 if m["fused"] or any(x[4] == fam
                                                      for x in m["mem"]))
                    if paired < want - singles_ok:
                        m0 = next(m for m in mine if not m["fused"]
                                  and not any(x[4] == fam for x in m["mem"]))
                        emit("R4-half-pair", "pair-grouping", m0,
                             "%s named on ONE stroke; the print draws a full "
                             "pair here (not a QPC iqlab position) — its twin "
                             "is unwelded or lost" % fam)

            # R6: a tanwin the text wants, absent, while the word holds a
            # surplus PLAIN pair sitting within the weld windows — the residue
            # the weld passes (:3608, :3653, compose_tanwin) missed.
            for fam, plain in (("tanwin_al_damm", ("dammah",)),
                               ("tanwin_al_kasr", ("kasrah", "fathah"))):
                want = sum(u.count(c) for c in TANW[fam])
                if not want or have.get(fam, 0) >= want:
                    continue
                if iqlab_singles(u, q, fam):
                    continue            # a single stroke is CORRECT there
                pw = (u.count("ُ") if fam == "tanwin_al_damm"
                      else u.count("َ") + u.count("ِ"))
                pl = [m for m in masters if m["f"] in plain]
                if len(pl) - pw >= 2 * (want - have.get(fam, 0)):
                    cand = None
                    for i in range(len(pl)):
                        for j in range(i + 1, len(pl)):
                            dx = abs((pl[i]["x1"] + pl[i]["x2"]) / 2
                                     - (pl[j]["x1"] + pl[j]["x2"]) / 2)
                            dy = abs((pl[i]["y1"] + pl[i]["y2"]) / 2
                                     - (pl[j]["y1"] + pl[j]["y2"]) / 2)
                            if dx < 8.0 and dy < 8.0:
                                cand = (pl[i], dx, dy)
                    if cand:
                        emit("R6-unwelded-tanwin", "pair-grouping", cand[0],
                             "text wants %s, word holds a surplus plain pair "
                             "%.1f/%.1fu apart the welds missed"
                             % (fam, cand[1], cand[2]), fam)

            # R7: a small_meem element in a word whose QPC text draws NO meem.
            # rasm_uthmani writes tanwin + small meem (U+06E2/06ED) at EVERY
            # non-izhar tanwin — idgham and ikhfa included — while the print
            # only draws the م at IQLAB, encoded in QPC as plain harakah +
            # meem. At the other positions QPC writes the open signs ٖ/ٗ/ٞ
            # and the ink is a stroke PAIR with no meem (verified on the
            # لأيات family and p275/p536 stacked pairs). Keying the meem
            # rescue on rasm_uthmani therefore names the pair's second stroke (or
            # the whole welded pair outline) "small_meem": measured, the 571
            # QPC-confirmed meems are one uniform glyph (w 3.2-3.3, h 9.5)
            # while the 926 QPC-meemless "meems" are ragged (w 4.5-11.0,
            # h 6-10.5) — stroke ink, not a م. Invisible to every count
            # audit because small_meem is deliberately never demanded.
            if q and not any(c in q for c in "ۭۢ"):
                for m in masters:
                    if m["f"] != "small_meem":
                        continue
                    tans = [t for t in masters
                            if t["f"] in ("tanwin_al_fath", "tanwin_al_kasr", "tanwin_al_damm")]
                    near = min((abs((t["x1"] + t["x2"]) / 2
                                    - (m["x1"] + m["x2"]) / 2)
                                + abs((t["y1"] + t["y2"]) / 2
                                      - (m["y1"] + m["y2"]) / 2)
                                for t in tans), default=1e9)
                    emit("R7-meem-not-in-print", "name-swap", m,
                         "small_meem where this print draws no meem (QPC "
                         "writes an open tanwin, no ۢ/ۭ); w %.1f h %.1f, "
                         "%.1fu from the word's tanwin — the pair's second "
                         "stroke or its welded outline"
                         % (m["x2"] - m["x1"], m["y2"] - m["y1"],
                            near if near < 1e8 else -1),
                         "tanwin-part")

            # R10: the waqf budget against the held waqf marks, with the
            # DRAWN sign located where possible. The budget is a RANGE across
            # the two editions exactly as audit_marks treats it (they disagree
            # at 190 positions). Nine round-7 verdicts are deficits where the
            # sign IS drawn — held as letter ink, welded into a neighbour's
            # group, or an unlabeled blob — and two are muʿānaqah ۛ pieces
            # split/miscounted (p112/p114, waqf_places territory). Candidates
            # reported: unnamed mark elements, and letter-classified boxes
            # 3-13u square (a drawn صلى/قلى measures ~9x7-11).
            pu = sum(u.count(c) for c in WAQF_CH)
            pq = sum(q.count(c) for c in WAQF_CH) if q else pu
            lo_p, hi_p = min(pu, pq), max(pu, pq)
            p_have = have.get("waqf", 0)
            if not (lo_p <= p_have <= hi_p):
                cands = []
                for m in masters:
                    if m["f"] == "mark":
                        cands.append(("unnamed-mark", m["x1"], m["y1"],
                                      round(m["x2"] - m["x1"], 1),
                                      round(m["y2"] - m["y1"], 1)))
                for b in w["b"]:
                    bw, bh = b[2] - b[0], b[3] - b[1]
                    if 3.0 <= bw <= 13.0 and 3.0 <= bh <= 13.0:
                        cands.append(("letter-box", b[0], b[1],
                                      round(bw, 1), round(bh, 1)))
                anchor = (masters[0] if masters else
                          {"f": "waqf", "x1": w["b"][0][0], "y1": w["b"][0][1],
                           "x2": w["b"][0][2], "y2": w["b"][0][3]})
                pm = next((m for m in masters if m["f"] == "waqf"), anchor)
                emit("R10-waqf-vs-ink",
                     "pair-grouping" if p_have > hi_p else "unexplained", pm,
                     ("holds %d waqf mark(s), budget %s; " %
                      (p_have, ("%d" % lo_p if lo_p == hi_p
                                else "%d-%d" % (lo_p, hi_p)))
                      + ("drawn-sign candidates in word: %s" % (cands,)
                         if cands and p_have < lo_p else
                         "no candidate blob inside the word — the sign is "
                         "welded into a neighbour or classified as that "
                         "word's letter ink" if p_have < lo_p else
                         "surplus: a neighbour's sign or a split ۛ piece")))

            # R11: a dammah-family deficit with a dammah-sized blob available.
            # Dammah is excluded from auto shape labels (its curl matches a
            # hamzah outline), so UNLABELED dammah-shaped blobs are expected to
            # exist and only the text budget may promote one — the same
            # two-signal recovery as the waqf and small_waw families.
            # Candidates: unnamed mark elements, and letter-classified boxes
            # 3.5-9u square (a drawn dammah measures 5.3 x 6.6) in the upper
            # two thirds of the band or above it.
            dw_want = sum(u.count(c) for c in DAMMAH_CH)
            dw_have = have.get("dammah", 0) + have.get("tanwin_al_damm", 0)
            if dw_have < dw_want:
                cands = []
                for m in masters:
                    if m["f"] == "mark" and 3.0 <= m["x2"] - m["x1"] <= 9.0 \
                            and 3.0 <= m["y2"] - m["y1"] <= 9.5:
                        cands.append(("unnamed-mark", m["x1"], m["y1"],
                                      round(m["x2"] - m["x1"], 1),
                                      round(m["y2"] - m["y1"], 1)))
                for b in w["b"]:
                    bw, bh = b[2] - b[0], b[3] - b[1]
                    cyb = (b[1] + b[3]) / 2
                    if 3.5 <= bw <= 9.0 and 3.5 <= bh <= 9.5 \
                            and cyb < by1 + 0.67 * (by2 - by1):
                        cands.append(("letter-box", b[0], b[1],
                                      round(bw, 1), round(bh, 1)))
                dm = next((m for m in masters
                           if m["f"] in ("dammah", "tanwin_al_damm")), None)
                anchor = dm or (masters[0] if masters else None)
                if anchor is not None:
                    emit("R11-dammah-deficit",
                         "pair-grouping" if cands else "unexplained", anchor,
                         "holds %d of %d dammah-family marks; %s"
                         % (dw_have, dw_want,
                            ("recovery candidates: %s" % (cands,)) if cands
                            else "no dammah-sized blob inside the word — "
                                 "the curl is in a neighbour or welded"))

            # R8 dot label vs drawn content, width unit 2.38u/blob (measured,
            # QSVG_DOTLBL :6071 — that pass renames at :6071-time; what shows
            # here survived it, mostly because the label arrived later).
            # UNDER direction (label counts more dots than the ink draws):
            # 33 mushaf-wide, 24 of them one auto signature
            # (d2506e4f8b4e28e5, labeled 'dot') serving as a two/three_dots
            # master — the reviewer's 9514d038 note ("one outline covering
            # both 2 and 3 dots") measured. OVER direction (blob wider than
            # its label): ZERO in the whole mushaf.
            # Budget is the second signal: word dot units vs dot_budget
            # moving the SAME way = proof; balanced words go to review (the
            # cluster's other pieces may hold the remainder — bbox of a
            # diagonal pair lies about blob count).
            dot_have = sum(DOTV[m["f"]] for m in masters if m["f"] in DOTV)
            for m in masters:
                if m["f"] not in DOTV:
                    continue
                n = blobs(m["x2"] - m["x1"]) + sum(
                    blobs(x[2] - x[0]) for x in m["mem"] if x[4] in DOTV)
                if n == DOTV[m["f"]]:
                    continue
                gap = w["dots_budget"] - dot_have   # +ve: word under budget
                name = {1: "dot", 2: "two_dots", 3: "three_dots"}.get(n)
                if n > DOTV[m["f"]] and gap >= n - DOTV[m["f"]]:
                    emit("R8-dot-content", "pair-grouping", m,
                         "'%s' measures %d dot-widths and the word is %d "
                         "unit(s) SHORT of its text budget — label "
                         "under-counts the drawn dots" % (m["f"], n, gap),
                         name)
                elif n < DOTV[m["f"]] and gap <= n - DOTV[m["f"]]:
                    emit("R8-dot-content", "pair-grouping", m,
                         "'%s' measures only %d dot-width(s) and the word is "
                         "%d unit(s) OVER its text budget — label over-counts "
                         "the drawn ink" % (m["f"], n, -gap), name)
                else:
                    emit("R8-dot-content-weak", "unexplained", m,
                         "'%s' measures %d dot-width(s) but the word's dot "
                         "units balance — the cluster's other pieces may "
                         "hold the remainder; needs eyes (sig %s)"
                         % (m["f"], n, m["sig"][:16]))
    return flags, stats, rule_n, fam_n


def qtl(v, q):
    if not v:
        return float("nan")
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * q))]


def print_dists(stats):
    print("== clean-subset position summaries (full histograms: "
          "docs/defects/marktype_rules.md) ==")
    fams = sorted({f for (b, f) in stats if b == "cl"})
    for fam in fams:
        rows = stats[("cl", fam)]
        sb = [r[0] for r in rows]
        sa = [r[1] for r in rows]
        print("%-14s n=%-6d below-band p99/max %6.1f/%6.1f   "
              "above-top p99/max %6.1f/%6.1f"
              % (fam, len(rows), qtl(sb, .99), max(sb) if sb else 0,
                 qtl(sa, .99), max(sa) if sa else 0))


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    a, b = int(args[0]), int(args[1])
    jobs = int(args[2]) if len(args) > 2 else 4
    out = args[3] if len(args) > 3 else None
    dist_only = "--dist" in sys.argv
    ensure_cache(a, b, jobs)
    dirty, noissue = load_dirty()
    flags, stats, rule_n, fam_n = run_rules(
        list(range(a, b + 1)), dirty, noissue, dist_only)
    print_dists(stats)
    if dist_only:
        return
    print("\n== flags by rule ==")
    for k, n in rule_n.most_common():
        print("  %-24s %5d" % (k, n))
    print("== flags by family ==")
    for k, n in fam_n.most_common():
        print("  %-24s %5d" % (k, n))
    by_cat = Counter(f["category"] for f in flags)
    print("== flags by category ==")
    for k, n in by_cat.most_common():
        print("  %-24s %5d" % (k, n))
    nv = sum(1 for f in flags if f["verdict_no_issue"])
    print("\nflags total %d | on words a human called no-issue: %d "
          "(the verdict outranks the rule — review those rules)"
          % (len(flags), nv))
    if out:
        json.dump(flags, open(out, "w"), ensure_ascii=False, indent=1)
        print("wrote %s" % out)


if __name__ == "__main__":
    main()
