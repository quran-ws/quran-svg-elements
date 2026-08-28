#!/usr/bin/env python3
"""Assign each ink element to its word, producing MushafDatabase-style word groups.

Pipeline stage 2, after split_line_elements.py. For every line the verified word list
(quran.com v4, KFGQPC layout) says how many words the line holds and what each one reads;
the elements on the line are clustered into exactly that many words by cutting at the
widest inter-element gaps. Because all KFGQPC prints share the same words per line across
qiraat, one Hafs layout drives every edition; the uthmani/imlaei strings attached are the
Hafs forms and per-riwayah spellings can be swapped in later without touching geometry.

Every line gets a confidence record: the margin between the cut gaps and the widest gap
kept inside a word, plus sanity flags (a word made only of floating marks, a count
mismatch, a line the source has no words for). Low-margin or flagged lines are the manual
review queue; the rest are safe automatic assignments.

    tools/assign_words.py hafs/kfqc 3                 # one page -> svg + report
    tools/assign_words.py hafs/kfqc 3 --words-cache DIR --out-dir DIR
"""

import argparse
import json
import math
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from page import Page

# Taxonomy phase 2 (decision 5). |dx| of a tanween pair's two stroke centers
# (lower minus upper), measured over ALL 604 pages before choosing
# (empty-band rule), 8,516 pairs on 2026-08-27:
#
#   fathatan (3,630)  stacked cluster |dx| 0.00-0.92 | EMPTY | open 2.18-5.4
#   kasratan (2,515)  stacked cluster |dx| 0.00-0.82 | EMPTY | open 1.29-7.7
#   dammatan (2,371)  stacked cluster |dx| 0.28-0.39 | EMPTY | open 3.55-3.9
#
# The signed direction differs (open fathatan shifts the lower stroke right,
# open kasratan left, open dammatan either), so the threshold is on |dx|,
# per family, INSIDE each band. Cross-checked against the text's own
# open/closed tanween encoding (U+08F0-08F2 = idgham/ikhfa = staggered):
# 8,515 of 8,516 agree; the one disagreement is p208 10:2 مُّبِينٌ, a closed
# tanween welded at |dx|=7.65 (geometry wins: it carries staggered).
_TAN_STAG = {"fathatan": 1.5, "kasratan": 1.05, "dammatan": 1.5}
# QSVG_TANDUMP: collect every tanween master/twin geometry record here for
# the measuring script; None (the default) costs nothing.
TAN_DUMP = [] if os.environ.get("QSVG_TANDUMP") else None
from svg_lines import transform_box
from split_line_elements import group_elements, PATH_RE

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = ("https://api.quran.com/api/v4/verses/by_page/%d?words=true&mushaf=2"
       "&word_fields=line_number,text_uthmani,text_imlaei&per_page=50")


# ---------------------------------------------------------------------------
# Verified word list per line (never hand-typed; cached verbatim from the API)
# ---------------------------------------------------------------------------

def page_words(page_no, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, "page-%03d.json" % page_no)
    if os.path.exists(cache):
        data = json.load(open(cache, encoding="utf-8"))
    else:
        req = urllib.request.Request(API % page_no,
                                     headers={"User-Agent": "quran-svg-tools/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        json.dump(data, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    if _dkseg_on():
        _dkseg_split_data(data)
    # The art is the KFGQPC madani print, which the QCF v2 page fonts replicate
    # line-for-line; quran.com's own line numbers drift from it on some pages
    # (p4: end-of-line word wrapped). Prefer the QCF layout when we have it.
    qcf_lines = _qcf_lines().get(str(page_no), {})
    qpc = qpc_words(page_no)

    # The QCF layout is normally the better of the two, but on a few pages it
    # is self-contradictory: p599 puts 100:6 on line 1 while surah 100 does not
    # begin until line 14, so a word sits above its own surah's opening. Text
    # runs one way down a page, and a layout that runs backwards cannot be
    # right. Where it does, fall back to the line numbers that came with the
    # words. 22 pages are affected, 12 of them in juz 30, where the short
    # surahs put a page break in the middle of almost every one.
    def _monotonic(pick):
        first = {}
        for verse in data["verses"]:
            s0, a0 = (int(x) for x in verse["verse_key"].split(":"))
            for w in verse["words"]:
                if w["char_type_name"] != "word":
                    continue
                ln = pick(verse["verse_key"], w)
                if ln is None:
                    continue
                key = (s0, a0, w["position"])
                if ln not in first or key < first[ln]:
                    first[ln] = key
        seq = [first[ln] for ln in sorted(first)]
        return all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))

    use_qcf = bool(qcf_lines) and _monotonic(
        lambda vk, w: qcf_lines.get("%s:%s" % (vk, w["position"])))
    if qcf_lines and not use_qcf and _QCF_WARN is not None:
        _QCF_WARN.add(page_no)

    lines = {}
    for verse in data["verses"]:
        surah, ayah = verse["verse_key"].split(":")
        for w in verse["words"]:
            if w["char_type_name"] != "word":     # 'end' = medallion, kept out of #content
                continue
            ln = (qcf_lines.get("%s:%s" % (verse["verse_key"], w["position"]),
                                w["line_number"]) if use_qcf
                  else w["line_number"])
            ut = w["text_uthmani"]
            if _dktext_on():
                dt = _dktext(int(surah), int(ayah), w["position"])
                # 5:52:12 دَآئِرَ ةٌ: the print draws two chunks and the
                # composite's internal space carries that to _space_halves;
                # the DK DB writes one token, so keep the composite there —
                # a letter-space compound must not lose its space.
                if dt is not None and not (_space_halves({"uthmani": ut})
                                           and " " not in dt):
                    ut = dt
            lines.setdefault(ln, []).append({
                "surah": int(surah), "ayah": int(ayah), "pos": w["position"],
                "uthmani": ut, "imlaei": w["text_imlaei"],
                "qpc": _dkseg_qpc(qpc, int(surah), int(ayah), w["position"]),
            })
    return lines


# ---------------------------------------------------------------------------
# QSVG_DKTEXT: mark budgets from the DigitalKhatt text — the print's own model
# ---------------------------------------------------------------------------
# The DK text (digital-khatt-v2.db, QUL export of the KFGQPC V2 1421H print)
# won the ink adjudication 5-0 against the uthmani+QPC composite on every
# genuinely disputed site (docs/defects/text_contest_eyes.json), and its 339
# iqlab sites carry the print's real convention (ONE haraka + small م —
# docs/defects/iqlab_notation.md) natively, so the tanween-pair rewrites stop
# being needed where it is on. Off by default until accepted; when on, the
# word's "uthmani" field carries the normalised DK text and every budget
# reader downstream follows it unchanged.
#
# _dk_norm maps DK's encoding onto the conventions this file's tables
# (HARAKA / HAMZA_MAP / DOTS / NONJOIN) are built around. Measured over all
# 77,432 words against the composite (2026-08-27): after this normalisation
# the two texts agree EXACTLY on segment count (0 diffs), letter dots
# (0 diffs) and skeleton (2 diffs: 11:13:3, where quran.com writes the typo
# افْتَرَاهُ, and one ر-seated hamza) — the only surviving budget deltas are
# the documented content families: 6,643 phantom low meems dropped, 339 iqlab
# tanween→haraka+م, 190 waqf, 3 maddah, 1 hamza, 1 wasla.
_DK_TEXT = None


def _dktext_on():
    # Default ON since 2026-08-27: DK won the ink adjudication 5-0, the
    # gate-ON build is better on every aggregate (marks 109->103, clean
    # 489->494, bench 84->81), and Abdullah eye-confirmed the two exposed
    # pages (p446, p90) as real pre-existing defects surfaced, not caused.
    return os.environ.get("QSVG_DKTEXT", "1") == "1"


def _dk_norm(t):
    # rarities first: U+034F CGJ (5 sites) is invisible; U+08F3 SMALL HIGH WAW
    # (17:7:12 only) is the suffix ۥ this art draws — fold to U+06E5 so the
    # small-waw budget sees it.
    t = t.replace("͏", "").replace("ࣳ", "ۥ")
    # the imala dot of 11:41:6 مَجْرٜىٰهَا: DK writes U+065C, the composite
    # U+06EA — same drawn dot, and the audit's pause table knows only U+06EA
    t = t.replace("ٜ", "۪")
    # DK writes every hamza/wasla seat decomposed (0 precomposed أإؤئ in the
    # whole DB; seats are base + U+0654/0655, the final ya seat is ى+U+0654).
    # Recompose to the precomposed forms HAMZA_MAP/dot_want key on — without
    # this, a medial seat ي is charged its two dots (921 sites).
    for a, b in (("أ", "أ"), ("إ", "إ"),
                 ("ؤ", "ؤ"), ("ئ", "ئ"),
                 ("ىٔ", "ئ")):
        t = t.replace(a, b)
    # Dotless-ya convention: DK writes ي where the composite writes ى at the
    # 3,691 word-final / pre-ء positions (drawn dotless either way). Fold so
    # letter_width and the per-segment dot prediction see the same letter.
    ch = list(t)
    for i, c in enumerate(ch):
        if c != "ي":
            continue
        j = next((k for k in range(i + 1, len(ch))
                  if _LETTER.match(ch[k])), None)
        if j is None or ch[j] == "ء":
            ch[i] = "ى"
    return "".join(ch)


def _dktext(s0, a0, pos):
    """Normalised DK text for a word, in whichever keying QSVG_DKSEG selects."""
    global _DK_TEXT
    if _DK_TEXT is None:
        _DK_TEXT = {}
        p = os.path.join(ROOT, ".cache", "digitalkhatt", "digital-khatt-v2.db")
        if os.path.exists(p):
            import sqlite3
            db = sqlite3.connect(p)
            for loc, txt in db.execute("SELECT location, text FROM words"):
                if loc.count(":") == 2 and not txt.startswith("۝"):
                    _DK_TEXT[loc] = _dk_norm(txt)
            db.close()
    if not _DK_TEXT:
        return None                       # DB absent: fall back to composite
    if _dkseg_on():
        return _DK_TEXT.get("%d:%d:%d" % (s0, a0, pos))
    # fused keying: the compound position holds both DK halves
    sp = _DKSEG_SPLITS.get((s0, a0), (None, None))[0]
    if sp is None or pos < sp:
        return _DK_TEXT.get("%d:%d:%d" % (s0, a0, pos))
    if pos == sp:
        a = _DK_TEXT.get("%d:%d:%d" % (s0, a0, sp))
        b = _DK_TEXT.get("%d:%d:%d" % (s0, a0, sp + 1))
        return "%s %s" % (a, b) if a and b else None
    return _DK_TEXT.get("%d:%d:%d" % (s0, a0, pos + 1))


_QPC = {}


def qpc_words(page_no):
    """The King Fahd Complex's own word text for a page, keyed surah:ayah:position.

    `text_uthmani` from quran.com is a different edition from the print this pipeline
    decomposes. Their waqf systems disagree at 424 of 4,416 positions — the text puts a
    قلى on 2:61 where the page draws ج, and 87 more like it — so anything that takes the
    printed page's marks from `text_uthmani` is checking the artwork against the wrong
    book. `qpc_uthmani_hafs` is the Printing Complex's text of this print, and it is also
    the text MushafDatabase labels its words with, so the three sources finally agree on
    what the page says.

    Cached under .cache/words-qpc/ by scratchpad/warm_qpc.py. Absent, everything falls
    back to `text_uthmani` exactly as before.
    """
    if page_no in _QPC:
        return _QPC[page_no]
    f = os.path.join(ROOT, ".cache", "words-qpc", "page-%03d.json" % page_no)
    out = {}
    if os.path.exists(f):
        try:
            for v in json.load(open(f, encoding="utf-8"))["verses"]:
                for w in v["words"]:
                    t = w.get("qpc_uthmani_hafs")
                    if t:
                        out["%s:%s" % (v["verse_key"], w["position"])] = t
        except Exception:
            out = {}
    _QPC[page_no] = out
    return out


_QCF_LINES = None


_QCF_WARN = set()


def _qcf_lines():
    global _QCF_LINES
    if _QCF_LINES is None:
        # The DigitalKhatt layout DB is an exact model of THIS print (KFGQPC V2
        # 1421H) and, unlike quran.com's mushaf-2 layout, is right about which
        # words are on the page for all 604 pages (25 pages differ, 18 in juz
        # 29-30 — reported.json item 21, adjudicated against MushafDatabase).
        # tools/build_dk_words.py --lines writes it in this table's format.
        # QSVG_DKLINES=0 falls back to the QCF v2 font layout for A/B.
        p = os.path.join(ROOT, ".cache", "dk_lines.json")
        dk_file = (os.environ.get("QSVG_DKLINES", "1") == "1"
                   and os.path.exists(p))
        if not dk_file:
            p = os.path.join(ROOT, ".cache", "qcf_lines.json")
        tbl = json.load(open(p)) if os.path.exists(p) else {}
        # dk_lines.json is keyed DK-canonical (the print's own segmentation of
        # the بَعْدَ مَا compounds, _DKSEG_SPLITS); qcf_lines.json is keyed
        # quran.com-fused. Convert to whichever keying QSVG_DKSEG selects.
        if tbl:
            if dk_file and not _dkseg_on():
                tbl = _dkseg_lines_convert(tbl, to_dk=False)
            elif not dk_file and _dkseg_on():
                tbl = _dkseg_lines_convert(tbl, to_dk=True)
        _QCF_LINES = tbl
    return _QCF_LINES


_DK_HEADERS = None


def dk_header_lines():
    """{page: {dk_line: ("surah-name"|"basmalah", surah)}} from the DK layout DB.

    The DigitalKhatt layout DB (same authority as dk_lines.json) declares each
    line's type: 'surah_name' rows carry the surah number directly; a
    'basmallah' line takes its surah from the first ayah word after it on the
    page (joined through digital-khatt-v2.db word ids — every basmallah in the
    DB has a following ayah line on its own page, checked over all 604 pages).
    Line numbers here are DK's; rewrite() maps them to art lines through the
    word anchors, because the ornate spreads' art omits DK line 1 (p1, p2).
    """
    global _DK_HEADERS
    if _DK_HEADERS is None:
        _DK_HEADERS = {}
        lay_p = os.path.join(ROOT, ".cache", "digitalkhatt",
                             "digital-khatt-15-lines.db")
        wdb_p = os.path.join(ROOT, ".cache", "digitalkhatt",
                             "digital-khatt-v2.db")
        if os.path.exists(lay_p) and os.path.exists(wdb_p):
            import sqlite3
            lay = sqlite3.connect(lay_p)
            wdb = sqlite3.connect(wdb_p)
            wsurah = {int(r[0]): int(r[1].split(":")[0]) for r in
                      wdb.execute("SELECT id, location FROM words")}
            rows = lay.execute(
                "SELECT page_number, line_number, line_type,"
                " CAST(surah_number AS INT), CAST(first_word_id AS INT)"
                " FROM pages ORDER BY page_number, line_number").fetchall()
            by_page = {}
            for pg, ln, lt, su, fw in rows:
                by_page.setdefault(pg, []).append((ln, lt, su, fw))
            for pg, lns in by_page.items():
                for i, (ln, lt, su, fw) in enumerate(lns):
                    if lt == "surah_name" and su:
                        _DK_HEADERS.setdefault(pg, {})[ln] = ("surah-name", su)
                    elif lt == "basmallah":
                        # surah of the first ayah word below it on the page
                        for ln2, lt2, _su2, fw2 in lns[i + 1:]:
                            if lt2 == "ayah" and fw2 in wsurah:
                                _DK_HEADERS.setdefault(pg, {})[ln] = (
                                    "basmalah", wsurah[fw2])
                                break
            lay.close()
            wdb.close()
    return _DK_HEADERS


# ---------------------------------------------------------------------------
# The print's own segmentation of the بَعْدَ مَا compounds (QSVG_DKSEG)
# ---------------------------------------------------------------------------
# DigitalKhatt's word DB of THIS print — and MushafDatabase, independently —
# segment بَعْدَ مَا as TWO words in all three ayahs it occurs; quran.com fuses
# each pair into one word with an internal space (reported.json item 20: the
# p254 pair straddles a line break, which one fused word cannot express). The
# DK keying is canonical here: the compound splits at position `fused` into
# `fused` (بَعْدَ) and `fused+1` (مَا) and every later position shifts +1.
# The other two letter-space compounds stay ONE word because the DK DB fuses
# them too: 37:130:3 إِلْ يَاسِينَ, and 5:52:12 where quran.com's internal
# space is its own typo (DK and MushafDatabase both write one word).
# QSVG_DKSEG=0 reverts everything to quran.com's fused keying.
_DKSEG_SPLITS = {(2, 181): (3, 27), (8, 6): (4, 177), (13, 37): (8, 254)}
_DKSEG_HALVES = {}


def _dkseg_on():
    return os.environ.get("QSVG_DKSEG", "1") == "1"


def _dkseg_fused(s0, a0, pos):
    """DK-canonical position -> (quran.com fused position, half or None)."""
    sp = _DKSEG_SPLITS.get((s0, a0), (None, None))[0]
    if sp is None or pos < sp:
        return pos, None
    if pos == sp:
        return sp, 0
    if pos == sp + 1:
        return sp, 1
    return pos - 1, None


def _dkseg_split_data(data):
    """Rewrite a quran.com page payload in place to the print's segmentation."""
    for verse in data.get("verses", []):
        s0, a0 = (int(x) for x in verse["verse_key"].split(":"))
        sp = _DKSEG_SPLITS.get((s0, a0), (None, None))[0]
        if sp is None:
            continue
        comp = next((w for w in verse["words"]
                     if w.get("char_type_name") == "word"
                     and w["position"] == sp
                     and " " in (w.get("text_uthmani") or "")), None)
        if comp is None:
            continue                     # not the page holding the compound,
        nw = []                          # or the cache no longer fuses it
        for w in verse["words"]:
            if w is comp:
                hu = [t for t in w["text_uthmani"].split(" ") if t]
                hi = [t for t in (w.get("text_imlaei") or "").split(" ") if t]
                if len(hi) != len(hu):
                    hi = hu
                for k in range(len(hu)):
                    h = dict(w)
                    h["position"] = sp + k
                    h["text_uthmani"] = hu[k]
                    h["text_imlaei"] = hi[k]
                    nw.append(h)
            else:
                if w["position"] > sp:
                    w = dict(w)
                    w["position"] += 1
                nw.append(w)
        verse["words"] = nw


def _dkseg_qpc(qpc, s0, a0, pos):
    """QPC text for a word: the cache is fused-keyed, so DK positions map back
    through the split and the compound's halves split its (two-token) text."""
    if not _dkseg_on():
        return qpc.get("%d:%d:%d" % (s0, a0, pos), "")
    fp, half = _dkseg_fused(s0, a0, pos)
    t = qpc.get("%d:%d:%d" % (s0, a0, fp), "")
    if half is None:
        return t
    parts = [x for x in t.split(" ") if x]
    return parts[half] if len(parts) == 2 else ""


def _dkseg_lines_convert(tbl, to_dk):
    """Convert a {page: {"s:a:p": line}} table between the two keyings.
    Fused -> DK gives both halves the fused word's line (the straddling p254
    pair is corrected by the DK-canonical dk_lines.json, not by this shim)."""
    out = {}
    for pg, d in tbl.items():
        nd = {}
        for k, ln in d.items():
            s0, a0, p = (int(x) for x in k.split(":"))
            sp = _DKSEG_SPLITS.get((s0, a0), (None, None))[0]
            if sp is None or p < sp:
                nd[k] = ln
            elif to_dk:
                if p == sp:
                    nd[k] = ln
                    nd["%d:%d:%d" % (s0, a0, sp + 1)] = ln
                else:
                    nd["%d:%d:%d" % (s0, a0, p + 1)] = ln
            else:
                if p == sp:
                    nd[k] = ln            # the fused word takes بَعْدَ's line
                elif p > sp + 1:
                    nd["%d:%d:%d" % (s0, a0, p - 1)] = ln
        out[pg] = nd
    return out


def _dkseg_half_lw(s0, a0):
    """Calibrated letter-width share of each compound half, from the cached
    quran.com text of the page the compound is printed on (never hand-typed)."""
    key = (s0, a0)
    if key in _DKSEG_HALVES:
        return _DKSEG_HALVES[key]
    sp, pg = _DKSEG_SPLITS[key]
    res = None
    f = os.path.join(ROOT, ".cache", "words", "page-%03d.json" % pg)
    if os.path.exists(f):
        for v in json.load(open(f, encoding="utf-8"))["verses"]:
            if v["verse_key"] != "%d:%d" % (s0, a0):
                continue
            for w in v["words"]:
                if w.get("char_type_name") == "word" and w["position"] == sp:
                    parts = [t for t in (w.get("text_uthmani") or "").split(" ") if t]
                    if len(parts) == 2:
                        res = [max(1e-6, sum(letter_width(sg["text"])
                                             for sg in segment_word(t)))
                               for t in parts]
    _DKSEG_HALVES[key] = res
    return res


def _dkseg_widths(q):
    """Remap the fused-keyed QCF advance table to DK-canonical keys; the
    compound's advance splits between its halves in proportion to their
    calibrated letter widths (CLAUDE.md: the width prior stays a prior)."""
    out = dict(q)
    for (s0, a0), (sp, _pg) in _DKSEG_SPLITS.items():
        pre = "%d:%d:" % (s0, a0)
        ent = {int(k.split(":")[2]): v for k, v in q.items()
               if k.startswith(pre)}
        if not ent:
            continue
        for p in ent:
            del out[pre + str(p)]
        lw = _dkseg_half_lw(s0, a0)
        for p, v in ent.items():
            if p < sp:
                out[pre + str(p)] = v
            elif p == sp:
                if lw:
                    out[pre + str(sp)] = v * lw[0] / (lw[0] + lw[1])
                    out[pre + str(sp + 1)] = v * lw[1] / (lw[0] + lw[1])
            else:
                out[pre + str(p + 1)] = v
    return out


# ---------------------------------------------------------------------------
# Elements with page-space geometry, grouped by line
# ---------------------------------------------------------------------------

def line_of(chain):
    for tag in chain:
        m = re.search(r'data-line="(\d+)"', tag)
        if m:
            return int(m.group(1))
    return None


def page_elements(page):
    """[(line, path_index, element contours, page-space bbox)] for all glyph paths.

    Ink wholly outside the viewBox is invisible (the renderer clips to it); the
    ornate opening spreads carry off-canvas leftovers that must never join words.
    """
    vb = re.search(r'viewBox="([\d.eE+-]+)[,\s]+([\d.eE+-]+)[ ,\s]+([\d.eE+-]+)'
                   r'[ ,\s]+([\d.eE+-]+)"', page.svg)
    if vb:
        vx, vy, vw, vh = (float(g) for g in vb.groups())
        vlim = (vx, vy, vx + vw, vy + vh)
    else:
        vlim = None
    out = []
    for pi, p in enumerate(page.paths):
        if "ayahPolygon" in p["text"]:
            continue
        ln = line_of(p["chain"])
        for el in group_elements(p["d"]):
            xs, ys = [], []
            for c in el:
                sp = c["sp"]
                x1, y1, x2, y2 = transform_box(p["M"], sp["xmin"], sp["ymin"],
                                               sp["xmax"], sp["ymax"])
                xs += [x1, x2]
                ys += [y1, y2]
            bx1, bx2, by1, by2 = min(xs), max(xs), min(ys), max(ys)
            off = bool(vlim and (bx2 < vlim[0] or by2 < vlim[1]
                                 or bx1 > vlim[2] or by1 > vlim[3]))
            out.append({"line": ln, "path": pi, "contours": el, "offcanvas": off,
                        "x1": bx1, "x2": bx2, "y1": by1, "y2": by2})
    return out


# Shapes whose normalised outline has a letter twin (a dagger-alef looks like a full
# alef once scale is removed) may only force-mark when the drawn size fits the mark.
# Marks this art never draws below their letter (fatha/kasra and the dot family
# are two-sided and stay unrestricted).
_ABOVE_ONLY = {"damma", "dammatan", "pause", "sukun", "shadda", "small-circle",
               "meem-iqlab", "small-waw", "small-alef", "maddah", "wasla"}

_DUAL_SIZE_CAP = {"small-alef": 12.0, "small-waw": 8.0, "small-ya": 9.5,
                  "pause": 9.5, "sukun": 4.8, "wasla": 6.5, "shadda": 8.5,
                  "small-circle": 4.8, "dot": 4.0, "meem-iqlab": 6.0, "letter-part": 11.5,
                  "fatha": 12.0, "kasra": 12.0, "fathatan": 12.0, "kasratan": 12.0}



def _human_letter_label(e):
    """True when a HUMAN table entry says this outline is letter ink
    (letter-hamza / letter / letter-part): the iqlab-م rescues must never
    press it into service as the sign (Abdullah 2026-08-28: the seated ء
    82bbe2d7 and the ك armature 7d3b5bf2 were both taken on iqlab words)."""
    try:
        sg = e.get("sig") or sig_key(signature(el_points(e)))
    except Exception:
        return False
    v = shape_labels().get(sg)
    lb = v.get("label") if isinstance(v, dict) else v
    auto = (v.get("auto", v.get("ai", False))
            if isinstance(v, dict) else False)
    return (not auto) and lb in ("letter-hamza", "letter", "letter-part")

def classify(elements, lines_info, part_key=None, mark_shapes=None):
    """Tag each element body/mark: known mark shapes first, then baseline geometry.

    Shape identity outranks position — a damma hovering low over a flat letter dips
    into the baseline zone, and a dagger-alef is taller than the height ceiling, but
    both ARE marks and their outlines are in the confirmed shape table. Geometry
    decides only what the table does not know: letter bodies stand on the baseline
    (a standalone ء included — this art draws it baseline-height, so it is a body),
    and a letter raised in a stacked composition is tall where no unknown mark is.
    """
    info = {li["lineNumber"]: li for li in lines_info}
    hs = sorted((li.get("height") or (li["bottom"] - li["top"]))
                for li in lines_info) if lines_info else []
    med_h = hs[len(hs) // 2] if hs else None
    for e in elements:
        li = info.get(e["line"])
        if li is None:
            e["kind"] = "body"
            continue
        if mark_shapes and part_key:
            lab = mark_shapes.get(part_key(e))
            if lab:
                e["lab"] = lab            # remembered for position/attachment rules
            if lab in ("letter-hamza", "letter", "letter-part"):
                # letter ink — whole letters (ر د و ا…) and detached pieces (the
                # ك armature) both cluster into words as bodies; as marks they
                # could re-line onto a neighbouring line's word.
                e["kind"] = "body"
                continue
            if lab:
                cap = _DUAL_SIZE_CAP.get(lab)
                size = max(e["x2"] - e["x1"], e["y2"] - e["y1"])
                # the sukun of this script is an OPEN curve: a ringed twin is a
                # letter ه/ة, never a sukun
                # the sukun of this script is an OPEN curve: a ringed twin is a
                # letter ه/ة, never a sukun; likewise the dot family is solid —
                # a contour nested inside another is a ring (a ة head), not dots
                ok = not (lab == "sukun" and len(e["contours"]) > 1)
                if ok and lab in ("dot", "two-dots", "three-dots") \
                        and len(e["contours"]) > 1:
                    bbs = [c["sp"] for c in e["contours"]]
                    for i2, a2 in enumerate(bbs):
                        for b2 in bbs[i2 + 1:]:
                            if (a2["xmin"] <= b2["xmin"] and a2["xmax"] >= b2["xmax"]
                                    and a2["ymin"] <= b2["ymin"]
                                    and a2["ymax"] >= b2["ymax"]) or \
                               (b2["xmin"] <= a2["xmin"] and b2["xmax"] >= a2["xmax"]
                                    and b2["ymin"] <= a2["ymin"]
                                    and b2["ymax"] >= a2["ymax"]):
                                ok = False
                if ok and (cap is None or size <= cap):
                    e["kind"] = "mark"
                    continue
        size = max(e["x2"] - e["x1"], e["y2"] - e["y1"])
        _bh = e["y2"] - e["y1"]
        _bw = e["x2"] - e["x1"]
        # the sajdah overline is a hairline: its length varies with the words
        # it spans, its height barely at all — so recognise it by that ratio
        # rather than by an absolute length, and a short one still qualifies
        if _bh < 2.5 and _bw > 9.0 and _bw > 8.0 * max(_bh, 0.35):
            e["kind"] = "mark"
            e["lab"] = "sajdah"
            continue
        if size < 4.6:
            e["kind"] = "mark"            # no letter is this small; petals/dots are
            continue
        if size > 12.5:
            e["kind"] = "body"            # larger than every mark in this art
            continue
        # the line's "height" field is a padded art box; the band between top
        # and bottom is the geometric truth, and the smaller of the two keeps
        # a short baseline-hugging letter (a final meem) from being read as a
        # mark on pages whose padding runs wide
        h = min(li.get("height") or 1e9, li["bottom"] - li["top"])
        if med_h and h > 1.6 * med_h:
            h = med_h                     # merged/outlier band breaks the ratios
        base = li["baseline"]
        on_baseline = e["y2"] >= base - 0.18 * h and e["y1"] <= base - 0.20 * h
        tall = (e["y2"] - e["y1"]) > 0.22 * h
        e["kind"] = "body" if on_baseline or tall else "mark"


def composite_marks(elements, part_key=None, known=None):
    """Group mark elements drawn as one logical sign — the waqf ج is a ح curl plus a
    dot, small قلے/صلے are several strokes, a damma head and its tail. Members stack:
    x-ranges overlap and they touch or nearly touch. Two parts that EACH match an
    already-labeled single shape never merge — a fatha dipping onto a hamza is two
    marks, and the shape table knows both; a glyph's own fragments match nothing on
    their own and are free to rejoin. The largest member becomes the primary; the
    others point back to it and never count or label on their own.
    """
    known = known or {}
    DOTFAM = {"dot", "two-dots", "three-dots"}

    def label_of(e):
        return known.get(part_key(e)) if part_key is not None else None

    def waqf_of(e):
        """Which pause sign this is — ج, صلى, قلى — from the shape, not the text."""
        return waqf_types().get(part_key(e)) if part_key is not None else None

    for ln in {e["line"] for e in elements}:
        marks = [e for e in elements
                 if e["line"] == ln and e["kind"] == "mark"]
        marks.sort(key=lambda e: e["x1"])
        parent = list(range(len(marks)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        # Radial ornaments first: the hizb rosette ۞ is many tiny petals packed
        # into one small box; x-overlap chaining misses the radial arrangement, and
        # larger petal pairs can pass the baseline test — recruit any small piece.
        def tiny(x):
            return max(x["x2"] - x["x1"], x["y2"] - x["y1"]) < 3.2

        for e in elements:
            if e["line"] != ln or e["kind"] != "body" or not tiny(e):
                continue
            near = [x for x in elements if x["line"] == ln and x is not e
                    and tiny(x)
                    and abs((x["x1"] + x["x2"]) / 2 - (e["x1"] + e["x2"]) / 2) < 6
                    and abs((x["y1"] + x["y2"]) / 2 - (e["y1"] + e["y2"]) / 2) < 6]
            if len(near) >= 4:
                e["kind"] = "mark"
        marks = [x for x in elements if x["line"] == ln and x["kind"] == "mark"]
        marks.sort(key=lambda x: x["x1"])
        parent = list(range(len(marks)))
        used = set()
        pp = list(range(len(marks)))

        def pfind(i):
            while pp[i] != i:
                pp[i] = pp[pp[i]]
                i = pp[i]
            return i

        for i in range(len(marks)):
            for j in range(i + 1, len(marks)):
                a, b = marks[i], marks[j]
                if b["x1"] > a["x2"] + 1.4:
                    break
                if not (tiny(a) and tiny(b)):
                    continue              # only rosette-sized petals join radially
                gx = max(a["x1"], b["x1"]) - min(a["x2"], b["x2"])
                gy = max(a["y1"], b["y1"]) - min(a["y2"], b["y2"])
                if gx <= 1.3 and gy <= 1.3:
                    pp[pfind(j)] = pfind(i)
        rad = {}
        for i in range(len(marks)):
            rad.setdefault(pfind(i), []).append(i)
        for idxs in rad.values():
            if len(idxs) < 4:
                continue
            xs1 = min(marks[i]["x1"] for i in idxs)
            xs2 = max(marks[i]["x2"] for i in idxs)
            ys1 = min(marks[i]["y1"] for i in idxs)
            ys2 = max(marks[i]["y2"] for i in idxs)
            w0, h0 = xs2 - xs1, ys2 - ys1
            if w0 > 10 or h0 > 10 or len(idxs) < 5 \
                    or not 0.7 <= (w0 / max(h0, 1e-9)) <= 1.4:
                continue                  # rosettes are compact and square-ish
            mem = sorted((marks[i] for i in idxs),
                         key=lambda e: -(e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
            mem[0]["mkmembers"] = mem[1:]
            for e in mem[1:]:
                e["mkpart"] = True
            used.update(idxs)

        for i in range(len(marks)):
            if i in used:
                continue
            for j in range(i + 1, len(marks)):
                if j in used:
                    continue
                a, b = marks[i], marks[j]
                if b["x1"] > a["x2"] + 0.3:
                    break
                ov = min(a["x2"], b["x2"]) - max(a["x1"], b["x1"])
                if ov < 0.4 * min(a["x2"] - a["x1"], b["x2"] - b["x1"]):
                    continue
                vgap = max(a["y1"], b["y1"]) - min(a["y2"], b["y2"])
                # a waqf letter's dot can hang below its curl (ج): a tiny piece
                # centred within a larger unlabeled piece joins across a bigger gap
                small, big = (a, b) if (a["x2"] - a["x1"]) < (b["x2"] - b["x1"]) else (b, a)
                nested_dot = (max(small["x2"] - small["x1"],
                                  small["y2"] - small["y1"]) < 3.2
                              and big["x1"] - 0.3 <= (small["x1"] + small["x2"]) / 2
                              <= big["x2"] + 0.3)
                if vgap > (2.2 if nested_dot else 0.8):
                    continue
                la, lb = label_of(a), label_of(b)
                # a slash is a complete mark on its own: it never welds into a
                # larger unknown piece (the ء of إ under a kasra) — only true
                # fragments (a damma's tail, a waqf curl) rejoin the unknown
                SLASH = ("fatha", "kasra", "fathatan", "kasratan")
                if ((la in SLASH and not lb and not nested_dot)
                        or (lb in SLASH and not la and not nested_dot)):
                    continue
                if la and lb:
                    dx = abs((a["x1"] + a["x2"]) / 2 - (b["x1"] + b["x2"]) / 2)
                    tight = dx < 2.5 and vgap <= 0.6
                    dots_pair = la in DOTFAM and lb in DOTFAM and tight
                    # A waqf letter owns its dot: ج = pause curl + nested dot.
                    #
                    # Restricting this to ج was tried, on the reasoning that صلى and قلى
                    # have no dot below them and so must be swallowing a letter's dot —
                    # `بِٱلۡمَعۡرُوفِ` on p27 does exactly that. Measured, it is wrong:
                    # dot disagreements went from 66 over the whole mushaf to 150 over
                    # the first 120 pages. Un-welding turns a sign's own dot into an
                    # extra dot unit far more often than it recovers a letter's. p27 is
                    # a real defect but not this rule's fault.
                    waqf_dot = (nested_dot and "pause" in (la, lb)
                                and (la in DOTFAM or lb in DOTFAM))
                    pause_pair = la == lb == "pause" and vgap <= 2.2
                    if not (dots_pair or waqf_dot or pause_pair):
                        continue         # two complete marks stacked, not one glyph
                parent[find(j)] = find(i)

        groups = {}
        for i, e in enumerate(marks):
            if i in used:
                continue                  # radial composites keep their grouping
            groups.setdefault(find(i), []).append(e)
        for members in groups.values():
            members.sort(key=lambda e: -(e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
            primary = members[0]
            primary["mkmembers"] = members[1:]
            for e in members[1:]:
                e["mkpart"] = True


# ---------------------------------------------------------------------------
# Clustering: exactly N words per line, cut at the N-1 widest gaps
# ---------------------------------------------------------------------------

_LETTER = re.compile(r"[ء-غف-يٱ-ۓ]")

# Relative drawn widths (em-ish) of skeleton letters in this script; 1.0 = a tooth.
WIDTH = {"ا": 0.4, "أ": 0.4, "إ": 0.4, "آ": 0.5, "ٱ": 0.4, "ء": 0.5,
         "ر": 0.8, "ز": 0.8, "د": 0.8, "ذ": 0.8, "و": 0.8, "ؤ": 0.8,
         "ب": 1.4, "ت": 1.4, "ث": 1.4, "ن": 1.1, "ي": 1.2, "ئ": 1.0, "ى": 1.2,
         "س": 1.7, "ش": 1.7, "ص": 1.8, "ض": 1.8, "ك": 1.4, "ل": 0.9,
         "م": 1.0, "ه": 1.0, "ة": 1.0, "ف": 1.3, "ق": 1.3}


_CAL = None


def _calibrated():
    """Per-(letter, position) widths learned from the mushaf by calibrate_widths.py."""
    global _CAL
    if _CAL is None:
        p = os.path.join(ROOT, ".cache", "letter-widths.json")
        _CAL = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _CAL


def letter_widths_list(text):
    """Expected drawn width of each letter of one connected piece, right to left."""
    cal = _calibrated()
    n = len(text)
    out = []
    for i, ch in enumerate(text):
        pos = ("isolated" if n == 1 else "initial" if i == 0 else
               "final" if i == n - 1 else "medial")
        e = cal.get(ch, {})
        got = e.get(pos) or e.get("medial") or e.get("initial") or e.get("final") \
            or e.get("isolated")
        if got and got["samples"] >= 3:
            out.append(got["width"])
        else:
            out.append(WIDTH.get(ch, 1.0) * 8.0)   # hand table, scaled to page units
    return out


def letter_width(text):
    return sum(letter_widths_list(text)) or 3.0


_QCF = None


_WAQF = None

# Taxonomy phase 1 (Abdullah's decisions, 2026-08-27): the print's own sign
# vocabulary. Old values are still ACCEPTED on input — waqf_types.json /
# waqf_places.json may be rebuilt from MushafDatabase, whose vocabulary the
# left column is — but only the right column is ever emitted.
_WAQF_CANON = {"waqf lazim": "waqf-lazim", "waqf qila": "waqf-awla",
               "waqf sali": "wasl-awla", "waqf jaiz": "waqf-jaiz",
               "waqf taanuq": "muanaqah"}


def waqf_types():
    """{signature: waqf name} — evidence, built by tools/waqf_table.py, applied as data.

    Additive only: the element keeps its `pause` label, so nothing that counts marks
    changes behaviour. Missing file means no `data-waqf` is emitted and everything
    behaves exactly as before.
    """
    global _WAQF
    if _WAQF is None:
        p = os.path.join(ROOT, ".cache", "marks", "waqf_types.json")
        try:
            _WAQF = {k: _WAQF_CANON.get(v["waqf"], v["waqf"])
                     for k, v in json.load(open(p, encoding="utf-8")).items()}
        except Exception:
            _WAQF = {}
    return _WAQF


_MARKS = None


def _mark_table():
    """{page: {geometry: label}} — dot labels settled per place. Data, not a rule."""
    global _MARKS
    if _MARKS is None:
        p = os.path.join(ROOT, ".cache", "review", "marks.json")
        try:
            _MARKS = json.load(open(p, encoding="utf-8"))
        except Exception:
            _MARKS = {}
    return _MARKS


_KINDS = None


def _kind_table():
    """{page: {geometry: "body"}} — ink we call a mark that is a letter. Data, not a rule."""
    global _KINDS
    if _KINDS is None:
        p = os.path.join(ROOT, ".cache", "review", "kinds.json")
        try:
            _KINDS = json.load(open(p, encoding="utf-8"))
        except Exception:
            _KINDS = {}
    return _KINDS


_WAQF_PLACES = None


def waqf_places():
    """{page: {geometry: waqf name}} for signs no signature of ours corresponds to."""
    global _WAQF_PLACES
    if _WAQF_PLACES is None:
        p = os.path.join(ROOT, ".cache", "marks", "waqf_places.json")
        try:
            _WAQF_PLACES = json.load(open(p, encoding="utf-8"))
            for _pg in _WAQF_PLACES.values():
                for _g, _rec in _pg.items():
                    if isinstance(_rec, dict):
                        _rec["waqf"] = _WAQF_CANON.get(_rec.get("waqf"),
                                                       _rec.get("waqf"))
                    else:
                        _pg[_g] = _WAQF_CANON.get(_rec, _rec)
        except Exception:
            _WAQF_PLACES = {}
    return _WAQF_PLACES


_RARE_PLACES = None


def rare_places():
    """{(surah, ayah): job} for the seven U+06DC sites, named BY JOB (taxonomy
    phase 1, decision 4): `saktah` at the five saktah sites, `seen-reading` at
    the two seen-for-sad sites. A place table exactly like waqf_places() —
    the ۜ outline is not one shape (each site has its own signature, and one of
    them, 9a5430a7a9db4617, doubles as a letter س body at 69:17), so the shape
    table cannot carry the job; the PLACE does. Data: .cache/marks/rare_places.json."""
    global _RARE_PLACES
    if _RARE_PLACES is None:
        p = os.path.join(ROOT, ".cache", "marks", "rare_places.json")
        _RARE_PLACES = {}
        try:
            d = json.load(open(p, encoding="utf-8"))
            for job in ("saktah", "seen-reading"):
                for ref in d.get(job, ()):
                    su, ay = ref.split(":")
                    _RARE_PLACES[(int(su), int(ay))] = job
        except Exception:
            _RARE_PLACES = {}
    return _RARE_PLACES


def qcf_widths():
    """Per-word advance widths from the QCF v2 page fonts — the print's own metrics."""
    global _QCF
    if _QCF is None:
        p = os.path.join(ROOT, ".cache", "qcf_widths.json")
        _QCF = json.load(open(p)) if os.path.exists(p) else {}
        # the table is fused-keyed (quran.com pairing); under QSVG_DKSEG the
        # word keys are the print's own segmentation — remap once, here, so
        # every consumer sees one consistent keying
        if _QCF and _dkseg_on():
            _QCF = _dkseg_widths(_QCF)
    return _QCF


_QCF_SUSPECT = [False]


def letters(word):
    """Expected drawn width of a word: the QCF font's own advance when known
    (scaled to roughly page units), else the calibrated letter sum."""
    q = qcf_widths().get("%d:%d:%d" % (word["surah"], word["ayah"], word["pos"]))
    # a hizb-quarter word's QCF advance includes the ۞ ornament glyph, which this
    # art draws separately — the inflated width would make the word steal atoms
    ls = sum(letter_width(s["text"]) for s in segment_word(word["uthmani"])) or 3.0
    if q and not word.get("half") \
            and not any(m in word["uthmani"] for m in "۞۩") \
            and os.environ.get("QSVG_QCF", "1") == "1":
        est = q * 19.5                    # em -> page units (alpha absorbs residual)
        # a handful of cached advances are corrupt (page-boundary drift pages
        # pair glyphs with the wrong words: لا wider than يموت). A real QCF
        # advance tracks the letter-sum estimate; an implausible ratio means
        # the advance belongs to some other word — use the calibrated sum.
        if not _QCF_SUSPECT[0] or 0.5 * ls <= est <= 1.45 * ls:
            return est
    return ls


_RECT = re.compile(r"M ([\d.]+) ([\d.]+) L ([\d.]+) [\d.]+ L [\d.]+ ([\d.]+)")


def ayah_ranges_per_line(polys_json, lines_info):
    """{line: {(surah, ayah): (x1, x2)}} from the per-page ayah polygons.

    Each polygon is a stack of per-line rectangles, so the x-extent of an ayah on a
    given line is a hard boundary no word of that ayah may cross.
    """
    out = {}
    for p in polys_json:
        key = (p["surahNumber"], p["ayahNumber"])
        for m in _RECT.finditer(p.get("polygon", "")):
            x1, y1, x2, y2 = (float(m.group(1)), float(m.group(2)),
                              float(m.group(3)), float(m.group(4)))
            if abs(y2 - y1) < 8:
                continue                      # separator/boundary strip, not a band
            # A rect may cover ONE line (per-line rows) or SEVERAL at once
            # (a generator that merges consecutive full-width lines into a
            # single rectangle). Both describe the same region, so credit every
            # band the rect substantially covers — matching on the rect's own
            # height alone silently drops the merged form.
            for li in lines_info:
                band = max(1e-6, li["bottom"] - li["top"])
                ov = min(y2, li["bottom"]) - max(y1, li["top"])
                if ov > 0.5 * min(band, y2 - y1):
                    r = out.setdefault(li["lineNumber"], {}).get(key)
                    lo, hi = min(x1, x2), max(x1, x2)
                    out[li["lineNumber"]][key] = ((min(r[0], lo), max(r[1], hi))
                                                  if r else (lo, hi))
    # A stale rect doubles an ayah onto the NEXT line with the SAME x-span it
    # had above (p592 line 8 "held" 88:1-2 over 88:3-6; p585 line 4 held
    # 80:1-3). A genuine continuation has a different span there — keep those,
    # drop only the identical copies.
    lns = sorted(out)
    for i in range(1, len(lns)):
        d, prev = out[lns[i]], out[lns[i - 1]]
        dups = [k for k in d if k in prev
                and abs(d[k][0] - prev[k][0]) < 2.0
                and abs(d[k][1] - prev[k][1]) < 2.0]
        for k in dups:
            # an ayah filling consecutive FULL lines repeats its span
            # legitimately; a stale copy betrays itself by colliding with
            # the line's own (non-duplicated) ayahs
            lo, hi = d[k]
            clash = any(min(hi, d[k2][1]) - max(lo, d[k2][0])
                        > 0.3 * min(hi - lo, d[k2][1] - d[k2][0])
                        for k2 in d if k2 not in dups and k2 != k)
            if clash:
                del d[k]
    return out


_W_WIDTH = float(__import__("os").environ.get("QSVG_WW", "0.3"))
_W_DOTS = float(__import__("os").environ.get("QSVG_WD", "2.40"))
_SEG_GAP = float(__import__("os").environ.get("QSVG_SEGGAP", "6.0"))
_DOT_REACH = float(__import__("os").environ.get("QSVG_DOTREACH", "3.0"))
_DOT_SCORE = float(__import__("os").environ.get("QSVG_DOTSCORE", "0.25"))
_W_SURPLUS = float(__import__("os").environ.get("QSVG_WSURP", "0.6"))


def _space_halves(word):
    """The two chunks of a letter-space compound, or None.

    Five layout words in the mushaf carry a REAL word-space inside one word
    entry (بَعْدَ مَا p27/p177/p254, دَآئِرَ ةٌ p117, إِلْ يَاسِينَ p451): the
    print draws two chunks separated by a full space. Trailing waqf signs also
    follow a space (`بَعْضٍۢ ۚ`) but hold no skeleton letter, so requiring a
    letter on BOTH sides selects exactly the compound family.

    Under QSVG_DKSEG (default on) the three بَعْدَ مَا pairs arrive as two
    ordinary words each (_DKSEG_SPLITS — the print's own segmentation), so
    this fires only for p117 and p451, which the DK DB also keeps fused.
    """
    core = word["uthmani"].replace("۞", "").replace("۩", "").strip()
    parts = [p for p in core.split(" ") if p]
    if len(parts) != 2 or not all(_LETTER.search(p) for p in parts):
        return None
    return parts


def cluster_line(els, words, ayah_ranges=None, alpha_scale=1.0,
                 use_dots=True):
    """Split a line's elements into one cluster per word, right to left.

    Elements are first merged into atoms wherever their x-intervals overlap — a mark
    above its letters can never be cut away from them. Atoms are then partitioned into
    consecutive runs by dynamic programming: each word's span should be about its letter
    count times the line's per-letter width. Gap size alone fails on justified lines —
    a kashida-stretched word holds gaps wider than the space before a short word like
    أم — but stretched words are exactly the ones the width prior expects to be wide.

    Returns (clusters, deviation): deviation is the worst |span − expected| relative to
    the line's mean word width; small = trustworthy, large = manual-review queue.
    """
    bodies = [e for e in els if e["kind"] == "body"]
    marks = [e for e in els if e["kind"] != "body"]
    if not bodies:
        bodies, marks = els, []
    # a letter fragment (the ك armature stroke) is drawn stacked over its base
    # letter: it joins that letter's atom instead of standing alone, where the
    # boundary search could hand it to the neighbouring word
    def armature(b):
        # the ك upper stroke: small, wider than tall-thin, drawn OVER its base —
        # a detached alef or a big letter chunk must keep its own atom
        w = b["x2"] - b["x1"]; h = b["y2"] - b["y1"]
        return max(w, h) <= 9.0 and h < 3.0 * w
    frags = [b for b in bodies if b.get("lab") == "letter-part" and armature(b)]
    bases = [b for b in bodies if b not in frags] or bodies
    atoms = [{"x1": b["x1"], "x2": b["x2"], "els": [b]} for b in bases]
    for f in frags:
        if f in bases:
            continue
        def ov(a):
            return min(a["x2"], f["x2"]) - max(a["x1"], f["x1"])
        fc = (f["x1"] + f["x2"]) / 2
        cands = [a for a in atoms
                 if ov(a) >= 0.5 * (f["x2"] - f["x1"])
                 and f["y2"] <= max(e["y2"] for e in a["els"]) + 1.0]
        if cands:
            # the ك stroke floats INSIDE its bowl: the atom whose span contains
            # the fragment's centre wins over a mere edge overlap
            best = max(cands, key=lambda a: (a["x1"] <= fc <= a["x2"], ov(a)))
            best["els"].append(f)
            best["x1"] = min(best["x1"], f["x1"])
            best["x2"] = max(best["x2"], f["x2"])
        else:
            atoms.append({"x1": f["x1"], "x2": f["x2"], "els": [f]})
    for mk in marks:
        if mk.get("mkpart"):
            continue                     # follows its composite's primary below
        cx = (mk["x1"] + mk["x2"]) / 2

        def fit(a):
            # overlap with the body's span first, then sheer distance
            ov = min(a["x2"], mk["x2"]) - max(a["x1"], mk["x1"])
            return (-ov, abs((a["x1"] + a["x2"]) / 2 - cx))

        best = min(atoms, key=fit)
        # identity-guarded: a member may already sit in this atom (the late
        # re-weld meets the original weld) and an element must be listed once
        for _e in [mk] + mk.get("mkmembers", []):
            if not any(x is _e for x in best["els"]):
                best["els"].append(_e)
    # a SMALL body atom sitting mostly inside a wider atom's span is a stacked
    # stroke of the same ligature (the second stroke of a lam-alef, a broken
    # letter piece) — the boundary search must not be able to separate them
    atoms.sort(key=lambda a: a["x2"] - a["x1"])
    merged_away = set()
    for i, sm in enumerate(atoms):
        wsm = sm["x2"] - sm["x1"]
        if wsm > 13.0 or id(sm) in merged_away:
            continue
        for big in atoms[i + 1:]:
            if id(big) in merged_away:
                continue
            wb = big["x2"] - big["x1"]
            if wb < 1.3 * wsm:
                continue
            ov = min(sm["x2"], big["x2"]) - max(sm["x1"], big["x1"])
            # stacked strokes sit ABOVE the base (lam-alef's second stroke, the
            # ك armature); a neighbour's final letter merely OVERLAPS sideways
            sm_cy = sum((e["y1"] + e["y2"]) / 2 for e in sm["els"]) / len(sm["els"])
            big_cy = sum((e["y1"] + e["y2"]) / 2 for e in big["els"]) / len(big["els"])
            # ... and INTERIOR to its span: a neighbour's standalone alef over
            # this word's sweeping tail rides the extreme edge, while a piece
            # of the letter itself (the silent alef of ـوا۟ over its waw) sits
            # well inside it. Measure that clearance RELATIVE to the letter's
            # own width — an absolute one cannot separate a 1.5u overhang on a
            # 15u sweep from a 2.45u inset on a 10u waw.
            sm_cx = (sm["x1"] + sm["x2"]) / 2
            edge = min(abs(sm_cx - big["x1"]), abs(sm_cx - big["x2"]))
            if ov >= 0.6 * wsm and sm_cy < big_cy - 1.5 \
                    and edge > max(1.2, 0.18 * wb):
                big["els"].extend(sm["els"])
                big["x1"] = min(big["x1"], sm["x1"])
                big["x2"] = max(big["x2"], sm["x2"])
                merged_away.add(id(sm))
                break
    atoms = [a for a in atoms if id(a) not in merged_away]

    # A letter-space compound is ONE layout word drawn as TWO chunks with a
    # real word-space between them. The DP below treats each word as one
    # contiguous run, so the internal space either blows up the width prior or
    # hands the right half to the neighbouring word (p254 بَعْدَ folded into
    # أَهْوَآءَهُم). Partition with the compound split into its halves — each
    # half gets its own width prior and the space earns its boundary reward —
    # then merge the two clusters back into one so every caller still sees one
    # cluster per layout word.
    merge_src = None
    if os.environ.get("QSVG_SPACESPLIT", "1") == "1":
        xw, src = [], []
        for wi, w in enumerate(words):
            hs = _space_halves(w)
            if hs:
                for h in hs:
                    pw = dict(w)
                    pw["uthmani"] = h
                    pw["half"] = True     # letters() must not use the full
                    xw.append(pw)         # compound's QCF advance per half
                    src.append(wi)
            else:
                xw.append(w)
                src.append(wi)
        if len(xw) != len(words):
            merge_src = src
            words = xw

    def _merge_halves(cls):
        if not merge_src:
            return cls
        out, last = [], None
        for wi, cl in zip(merge_src, cls):
            if out and wi == last:
                out[-1].extend(cl)
            else:
                out.append(list(cl))
            last = wi
        return out

    n = len(words)
    if n <= 0 or not atoms:
        return [[a] for a in atoms], 0.0
    if len(atoms) < n:
        return [[a] for a in atoms], float("inf")

    atoms.sort(key=lambda a: -(a["x1"] + a["x2"]))   # rightmost first = reading order
    m = len(atoms)
    lens = [letters(w) for w in words]
    span_total = atoms[0]["x2"] - atoms[-1]["x1"]
    alpha = span_total / sum(lens) * alpha_scale

    def width(i, j):                      # atoms i..j inclusive, RTL order
        return atoms[i]["x2"] - atoms[j]["x1"]

    # Gap before atom j in reading order — the space between it and its right neighbour.
    gap = [0.0] + [max(0.0, atoms[i - 1]["x1"] - atoms[i]["x2"]) for i in range(1, m)]

    # The cost of giving a word an atom run is how badly those atoms align to the
    # word's own expected letter structure (align_segs_atoms) — so the boundary search
    # knows that ءأنذرتهم expects a tiny floating ء at its right edge and عليهم expects
    # none. A real inter-word space still earns a reward, so a true boundary can pay
    # for a slightly worse width fit without splitting kashida-stretched words.
    GAP_REWARD = 1.0
    all_segs = [segment_word(w["uthmani"]) for w in words]
    # two width systems: word-level lens may be QCF-font based, but the letter
    # alignment works in calibrated letter units — give it its own absolute alpha
    cal_total = sum(letter_width(sg["text"]) for segs in all_segs for sg in segs)
    alpha_cal = span_total / max(1e-9, cal_total)
    n_letters = sum(len("".join(_LETTER.findall(w["uthmani"]))) for w in words) or 1
    mean_letter = span_total / n_letters       # scale-free gap normalisation

    # The skeleton fixes how many DOT units a word owns — a signal the split
    # search had been ignoring, though it is often the only thing that says
    # where one word ends: ٱلْمُحْصَنَـٰتِ (3) absorbing ثُمَّ (3) reads as 6.
    _DOTU_C = {"dot": 1, "two-dots": 2, "three-dots": 3}

    def _dots_of_word(w6):
        raw = _LETTER.findall(w6["uthmani"])
        sk = [(HAMZA_MAP[c][0] if c in HAMZA_MAP else c, c in HAMZA_MAP)
              for c in raw]
        t = 0
        for i6, (ch, seat) in enumerate(sk):
            if seat or ch not in DOTS:
                continue
            if ch == "\u064a" and i6 == len(sk) - 1:
                continue
            t += _DOTU_C.get(DOTS[ch][0], 0)
        return t

    _wdots = [_dots_of_word(w6) for w6 in words]

    def _dots_in(j6, i6):
        t = 0
        for a6 in atoms[j6:i6]:
            for e6 in a6["els"]:
                if e6.get("mkpart"):
                    continue
                t += _DOTU_C.get(e6.get("mark") or e6.get("lab"), 0)
        return t

    def group_cost(j, i, k):              # atoms j..i-1 as word k, in letter units
        if ayah_ranges:
            r = ayah_ranges.get((words[k - 1]["surah"], words[k - 1]["ayah"]))
            if r:
                # a word may not leave its ayah's polygon on this line
                overflow = (max(0.0, atoms[j]["x2"] - r[1] - 1.2)
                            + max(0.0, r[0] - atoms[i - 1]["x1"] - 1.2))
                if overflow > 0:
                    return 4.0 + overflow / alpha
        _, c = align_segs_atoms(atoms[j:i], all_segs[k - 1], alpha_cal)
        if c == float("inf"):
            c = abs(width(j, i - 1) - alpha * lens[k - 1]) / alpha + 2.0
        else:
            c *= len(all_segs[k - 1]) or 1
        # The art joins letters but never invents pieces: more atoms than expected
        # segments means the word is absorbing a neighbour's fragment — unless it
        # carries a hamza or tanween, whose tiny floats legitimately add atoms.
        surplus = max(0, (i - j) - len(all_segs[k - 1]))
        if surplus:
            floaty = any(ch in "ءأإؤئآ" for ch in words[k - 1]["uthmani"]) or \
                any(ch in "ًࣰٌࣱٍࣲ" for ch in words[k - 1]["uthmani"])
            c += surplus * (0.15 if floaty else _W_SURPLUS)
        # Direct word-width prior: the page font's own advance for this word is
        # ground truth (justification cancels through alpha). Letter alignment
        # alone lets a boundary drift a whole piece; this term pays for it.
        c += _W_WIDTH * abs(width(j, i - 1) - alpha * lens[k - 1]) / alpha
        # ... and the dot budget, which pins a boundary the widths cannot: a
        # surplus is charged harder than a deficit, since dots drawn over a
        # neighbour's letters are common but invented dots are not.
        dd = _dots_in(j, i) - _wdots[k - 1]
        if dd and not use_dots:
            dd = dd * _DOT_SCORE      # weaker voice when only SCORING a line
        if dd:
            c += (_W_DOTS * dd) if dd > 0 else (0.4 * _W_DOTS * -dd)
        return c

    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(m + 1)]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for k in range(1, n + 1):
        for i in range(k, m - (n - k) + 1):
            for j in range(k - 1, i):     # word k takes atoms j..i-1
                if dp[j][k - 1] == INF:
                    continue
                c = (dp[j][k - 1] + group_cost(j, i, k)
                     - (GAP_REWARD * gap[j] / mean_letter if j else 0.0))
                if c < dp[i][k]:
                    dp[i][k] = c
                    back[i][k] = j
    if dp[m][n] == INF:
        return [[a] for a in atoms], float("inf")

    bounds, i = [], m
    for k in range(n, 0, -1):
        j = back[i][k]
        bounds.append((j, i - 1))
        i = j
    bounds.reverse()

    clusters = [atoms[j:i + 1] for j, i in bounds]

    # Boundary repair: the DP is contiguous in reading order; keep it that way
    # and only SHIFT each word boundary by up to three atoms, scored by the QCF
    # width prior plus what the text says about edge atoms (a word ending in
    # \u0627/\u0629 owns the tall stroke / ring at its left edge; a word not starting
    # with an alef cannot open with a lone tall stroke). Order-preserving shifts
    # cannot interleave clusters, unlike free atom moves.
    def spanw(cl):
        return (max(a["x2"] for a in cl) - min(a["x1"] for a in cl)) if cl else 0.0

    def skel(w):
        return "".join(_LETTER.findall(w["uthmani"]))

    def alef_atom(a):
        b = max((e for e in a["els"] if e["kind"] == "body"), default=None,
                key=lambda e: (e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
        if b is None:
            return False
        w = b["x2"] - b["x1"]; h = b["y2"] - b["y1"]
        return h >= 8.5 and w <= 5.0 and h >= 2.6 * w   # a raa tail is squatter

    def ring_atom(a):
        b = max((e for e in a["els"] if e["kind"] == "body"), default=None,
                key=lambda e: (e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
        if b is None:
            return False
        w = b["x2"] - b["x1"]; h = b["y2"] - b["y1"]
        # nested contour is the signal: a ة drawn ring+tail as one path runs
        # to ~11 units, still unmistakably a ring letter
        return 3.0 <= max(w, h) <= 7.5 and 0.6 <= w / max(h, 1e-6) <= 1.7 \
            and len(b["contours"]) > 1

    ALEFS = "\u0627\u0623\u0625\u0622\u0671"
    sks = [skel(w) for w in words]

    def poly_pen(cl, k):
        # the ayah polygons are the art's own truth: an atom whose centre sits
        # outside its word's ayah extent on this line is on the wrong side
        if not ayah_ranges or not cl:
            return 0.0
        r = ayah_ranges.get((words[k]["surah"], words[k]["ayah"]))
        if not r:
            return 0.0
        lo, hi = r
        n_out = sum(1 for a in cl
                    if not (lo - 1.5 <= (a["x1"] + a["x2"]) / 2 <= hi + 1.5))
        return 4.0 * alpha * n_out

    def _nseg_band(w):
        segs = segment_word(w["uthmani"])
        hi = max(1, len(segs))
        soft = sum(1 for sg in segs if sg["text"] == "\u0621")
        # a lam-alef ligature may be drawn as TWO strokes (one extra piece)
        sk = "".join(_LETTER.findall(w["uthmani"]))
        laa = sum(sk.count("\u0644" + a) for a in "\u0627\u0623\u0625\u0622")
        return (max(1, hi - soft), hi + laa)

    nseg_band = [_nseg_band(w) for w in words]
    nsegs = [b[1] for b in nseg_band]

    def bscore(k, cl_r, cl_l):
        sk_r, sk_l = sks[k], sks[k + 1]
        c = (abs(spanw(cl_r) - alpha * lens[k])
             + abs(spanw(cl_l) - alpha * lens[k + 1])
             + poly_pen(cl_r, k) + poly_pen(cl_l, k + 1))
        # the text fixes how many detached pieces each word has: a stolen ذ or
        # ن leaves one word a segment short and its neighbour one over. The
        # first unit of mismatch matters most; chronic welds (fewer drawn
        # pieces than text segments, e.g. القرءان) add a flat offset that
        # cannot flip a boundary decision.
        def _segpen(cnt, band):
            lo, hi = band
            if lo <= cnt <= hi:
                return 0.0
            if cnt > hi:
                return 2.5 * (cnt - hi)   # surplus is always suspicious
            d = lo - cnt
            return d if d <= 1 else 1.0 + 0.25 * (d - 1)   # welds under-count
        c += 2.0 * alpha * (_segpen(len(cl_r), nseg_band[k])
                            + _segpen(len(cl_l), nseg_band[k + 1]))
        # provable theft of a short non-joining letter (dhal dal raa zay waw):
        # one side opens/ends with one per its text but is a piece short,
        # while the other holds a squat letter-sized piece at the boundary
        def _squat(a):
            b = max((e for e in a["els"] if e["kind"] == "body"), default=None,
                    key=lambda e: (e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
            if b is None:
                return False
            w2 = b["x2"] - b["x1"]; h2 = b["y2"] - b["y1"]
            if len(b["contours"]) > 1:
                return False
            return 4.0 <= max(w2, h2) <= 13.0 and h2 < 1.8 * w2 + 4.0
        if cl_r and cl_l and sk_l and sk_l[0] in "\u0630\u062f\u0631\u0632\u0648" \
                and len(cl_l) < nsegs[k + 1] and _squat(cl_r[-1]):
            c += 14.0 * alpha
        if cl_r and cl_l and sk_r and sk_r[-1] in "\u0630\u062f\u0631\u0632\u0648" \
                and len(cl_r) < nsegs[k] and _squat(cl_l[0]):
            c += 14.0 * alpha
        # a word expects a STANDALONE trailing alef only when its previous
        # letter is non-joining; after a joining letter the alef is fused into
        # a ligature and a lone alef at the boundary belongs to the neighbour
        r_ends_alef = (len(sk_r) >= 2 and sk_r[-1] in "\u0627\u0622"
                       and sk_r[-2] in "\u0648\u0630\u0631\u0632\u062f\u0621"
                                       "\u0627\u0623\u0625\u0622\u0671")
        l_starts_alef = bool(sk_l) and sk_l[0] in ALEFS
        if not cl_r or not cl_l:
            return c
        # penalise only PROVABLE thefts: the right word misses its trailing
        # stroke while the left word opens with one it has no textual right to
        # (a word starting with a tall lam must never be disturbed)
        if r_ends_alef and not l_starts_alef \
                and not alef_atom(cl_r[-1]) and alef_atom(cl_l[0]):
            c += 14.0 * alpha
        if os.environ.get("QSVG_DEBUG_BSC") and "\u063a\u062a" in sk_r:
            print("BSC r=%s l=%s r_ends=%s l_starts=%s aA(cl_r[-1])=%s aA(cl_l[0])=%s"
                  % (sk_r, sk_l, r_ends_alef, l_starts_alef,
                     alef_atom(cl_r[-1]), alef_atom(cl_l[0])), file=sys.stderr)
        if l_starts_alef and not r_ends_alef \
                and not alef_atom(cl_l[0]) and alef_atom(cl_r[-1]):
            c += 14.0 * alpha
        if r_ends_alef and l_starts_alef:
            if len(cl_r) >= 2 and alef_atom(cl_r[-1]) and alef_atom(cl_r[-2]) \
                    and not alef_atom(cl_l[0]):
                c += 14.0 * alpha
            if len(cl_l) >= 2 and alef_atom(cl_l[0]) and alef_atom(cl_l[1]) \
                    and not alef_atom(cl_r[-1]):
                c += 14.0 * alpha
        if sk_r.endswith("\u0629") and not ring_atom(cl_r[-1]) \
                and ring_atom(cl_l[0]) and not (sk_l and sk_l[0] in "\u0647\u0629"):
            c += 14.0 * alpha
        return c
    _dbg_pair = os.environ.get("QSVG_DEBUG_PAIR")
    if _dbg_pair:
        _orig_bscore = bscore
        def bscore(k, cl_r, cl_l):
            c = _orig_bscore(k, cl_r, cl_l)
            if _dbg_pair in sks[k]:
                w_r = abs(spanw(cl_r) - alpha * lens[k])
                w_l = abs(spanw(cl_l) - alpha * lens[k + 1])
                print("PAIR %s|%s nr=%d nl=%d tot=%.2f wr=%.2f wl=%.2f band_r=%s band_l=%s"
                      % (sks[k], sks[k + 1], len(cl_r), len(cl_l), c, w_r, w_l,
                         nseg_band[k], nseg_band[k + 1]), file=sys.stderr)
            return c

    for _ in range(2):
        changed = False
        for k in range(n - 1):
            cl_r, cl_l = clusters[k], clusters[k + 1]
            base = bscore(k, cl_r, cl_l)
            best = (base, 0)
            for j in (1, 2, 3):                        # take j atoms from the left word
                if len(cl_l) > j:
                    d = bscore(k, cl_r + cl_l[:j], cl_l[j:])
                    if d < best[0]:
                        best = (d, j)
            for j in (1, 2, 3):                        # give j atoms to the left word
                if len(cl_r) > j:
                    d = bscore(k, cl_r[:-j], cl_r[-j:] + cl_l)
                    if d < best[0]:
                        best = (d, -j)
            if os.environ.get("QSVG_DEBUG_BND"):
                print("BND %-10s|%-10s base %.2f best %.2f shift %d" % (
                    words[k]["uthmani"][:10], words[k + 1]["uthmani"][:10],
                    base, best[0], best[1]), file=sys.stderr)
            if best[1] and best[0] < base - 0.3 * alpha:
                j = best[1]
                if j > 0:
                    clusters[k] = cl_r + cl_l[:j]
                    clusters[k + 1] = cl_l[j:]
                else:
                    clusters[k] = cl_r[:j]
                    clusters[k + 1] = cl_r[j:] + cl_l
                changed = True
        if not changed:
            break

    mean_w = span_total / n
    worst = 0.0
    for k, cl in enumerate(clusters):
        if cl:
            span_k = spanw(cl)
            worst = max(worst, abs(span_k - alpha * lens[k]) / mean_w)
    return _merge_halves(clusters), worst


# ---------------------------------------------------------------------------
# Letter level: ligature segmentation and mark prediction from the word's text
# ---------------------------------------------------------------------------
# A connected letter-body IS a ligature: Arabic non-joining letters break the
# connected groups, so the expected ligature split is computable from the text
# alone (ٱلَّذِينَ → ٱ / لذ / ين). Marks (harakat, hamza, i'jam dots) are separate
# small elements; each one's label is predicted from the Unicode marks plus the
# dot pattern of the skeleton letters, then matched to the atom's observed mark
# elements above/below the body in right-to-left order. Any count mismatch is
# flagged, never guessed.

HARAKA = {
    "ً": ("fathatan", "a"), "ٌ": ("dammatan", "a"),
    "ٍ": ("kasratan", "b"), "َ": ("fatha", "a"),
    "ُ": ("damma", "a"), "ِ": ("kasra", "b"),
    "ّ": ("shadda", "a"), "ْ": ("sukun", "a"),
    "ٓ": ("maddah", "a"), "ٔ": ("hamza", "a"), "ٕ": ("hamza", "b"),
    "ٰ": ("small-alef", "a"), "۟": ("small-circle", "a"),
    "۠": ("small-circle", "a"), "ۡ": ("sukun", "a"),
    "ۢ": ("meem-iqlab", "a"), "ۭ": ("meem-iqlab", "b"),
    "ۤ": ("maddah", "a"), "ۥ": ("small-waw", "a"),
    "ۦ": ("small-ya", "a"), "ۧ": ("small-ya", "a"),
    "ۖ": ("pause", "a"), "ۗ": ("pause", "a"), "ۘ": ("pause", "a"),
    "ۙ": ("pause", "a"), "ۚ": ("pause", "a"), "ۛ": ("pause", "a"),
    "ۜ": ("pause", "a"), "ࣰ": ("fathatan", "a"),
    "ࣱ": ("dammatan", "a"), "ࣲ": ("kasratan", "b"),
}
# skeleton letter -> (dots label, above/below); final ya is dotless in this script
DOTS = {
    "ب": ("dot", "b"), "ت": ("two-dots", "a"), "ث": ("three-dots", "a"),
    "ج": ("dot", "b"), "خ": ("dot", "a"), "ذ": ("dot", "a"), "ز": ("dot", "a"),
    "ش": ("three-dots", "a"), "ض": ("dot", "a"), "ظ": ("dot", "a"),
    "غ": ("dot", "a"), "ف": ("dot", "a"), "ق": ("two-dots", "a"),
    "ن": ("dot", "a"), "ي": ("two-dots", "b"), "ة": ("two-dots", "a"),
}
HAMZA_MAP = {
    "أ": ("ا", ("hamza", "a")), "إ": ("ا", ("hamza", "b")),
    "آ": ("ا", ("maddah", "a")), "ٱ": ("ا", ("wasla", "a")),
    "ؤ": ("و", ("hamza", "a")), "ئ": ("ي", ("hamza", "a")),
}
NONJOIN = set("اأإآٱدذرزوؤةى")


def segment_word(uthmani):
    """Expected ligatures of a word: [{'text', 'marks': [(label, pos)…], 'bad'}].

    `text` is the skeleton (rasm) the body path draws. A standalone ء is drawn as a
    floating mark in this art, so it joins the neighbouring segment's marks instead of
    counting as a body of its own.
    """
    segs, cur, pend, bad = [], None, [], False
    for ch in uthmani:
        if ch in " ـ":
            continue
        if ch == "ء":                       # drawn at baseline: its own tiny body
            cur = {"text": "ء", "marks": pend, "closed": True}
            segs.append(cur)
            pend = []
            continue
        if ch in HARAKA:
            if cur:
                cur["marks"].append(HARAKA[ch])
            else:
                pend.append(HARAKA[ch])
            continue
        if ch in HAMZA_MAP:
            base, extra = HAMZA_MAP[ch]
        elif "ء" <= ch <= "ي" or ch == "ى":
            base, extra = ch, None
        else:
            bad = True          # a char these tables don't know — review, not guess
            continue
        if cur is None or cur["closed"]:
            cur = {"text": "", "marks": pend, "closed": False}
            segs.append(cur)
            pend = []
        cur["text"] += base
        if extra:
            cur["marks"].append(extra)      # hamza carriers are drawn dotless
        elif base in DOTS:
            cur["marks"].append(DOTS[base])
        if ch in NONJOIN:
            cur["closed"] = True
    if pend and segs:
        segs[0]["marks"] = pend + segs[0]["marks"]
    # final ya and alef maqsura are drawn dotless in the Madinah script
    if segs and segs[-1]["text"].endswith("ي"):
        m = segs[-1]["marks"]
        if ("two-dots", "b") in m:
            m.remove(("two-dots", "b"))
    for s in segs:
        s["bad"] = bad
    return segs


def align_segs_atoms(atoms, segs, alpha=None):
    """Monotone alignment of drawn bodies to expected ligatures, both right-to-left.

    The nominal split rule and the art disagree in places — كفروا can be inked as one
    connected piece (one atom, three segments), a hamza or a stray piece can add an
    atom. Each aligned group is one atom run ↔ one segment run, where at least one side
    is a single item; groups are scored by the same width prior as word clustering.
    Returns (groups, cost): groups = [(atom_list, seg_list)…], cost normalised to the
    word's per-letter width (high = review).
    """
    n, m = len(atoms), len(segs)
    if not n or not m:
        return [(atoms, segs)] if atoms or segs else [], float("inf")
    lens = [letter_width(s["text"]) for s in segs]
    if alpha is None:                     # scale from the word itself; a caller that
        span_total = atoms[0]["x2"] - atoms[-1]["x1"]  # compares words must pass the
        alpha = span_total / sum(lens)                 # line's absolute per-letter width

    def span(pi, i):                                    # atoms pi..i-1, with gaps
        return atoms[pi]["x2"] - atoms[i - 1]["x1"]

    mean_seg = alpha * (sum(lens) / len(lens))
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            for pi in range(0, i):
                for pj in range(0, j):
                    if (i - pi > 1) and (j - pj > 1):
                        continue                    # one side must be a single item
                    if dp[pi][pj] == INF:
                        continue
                    c = dp[pi][pj] + abs(span(pi, i) - alpha * sum(lens[pj:j]))
                    if j - pj > 1:
                        # Merging expected segments means the art joined across a
                        # non-joining boundary — possible (a وا swash) but rare, and
                        # never possible for a standalone ء, which touches nothing.
                        if any(s["text"] == "ء" for s in segs[pj:j]):
                            continue
                        c += 0.12 * mean_seg * (j - pj - 1)
                    if c < dp[i][j]:
                        dp[i][j] = c
                        back[i][j] = (pi, pj)
    if dp[n][m] == INF:      # e.g. a lone atom asked to hold text ending in ء
        return [(atoms, segs)], float("inf")
    groups, i, j = [], n, m
    while i or j:
        pi, pj = back[i][j]
        groups.append((atoms[pi:i], segs[pj:j]))
        i, j = pi, pj
    groups.reverse()
    # Cost in fractions of a mean expected segment, so it is scale-free whether the
    # letter widths are relative table values or calibrated absolute units.
    mean_seg = alpha * (sum(lens) / len(lens))
    return groups, dp[n][m] / max(mean_seg, 1e-9) / max(1, len(groups))


def put_in_ligature(atoms, e):
    """Place `e` in the ligature group of `atoms` whose ink it actually sits over.

    A word is emitted as one `<g class="ligature">` per piece the joining rules allow, so
    appending to `atoms[0]` puts the mark in the word's FIRST group whatever it is drawn
    over. Abdullah caught this on p591: `ٱلسَّمَآءِ`'s final kasra was moved into the
    right word and landed in `data-text="وا"`, the group holding the initial و at the
    other end of the word, instead of the group holding the hamza it sits under.

    Same rule `_omove` uses for every one of the older movers — nearest by centre x.
    """
    tgt = min(atoms, key=lambda a: min(
        (abs((x["x1"] + x["x2"]) / 2 - (e["x1"] + e["x2"]) / 2) for x in a["els"]),
        default=1e9))
    for _e in [e] + e.get("mkmembers", []):
        if not any(x is _e for x in tgt["els"]):
            tgt["els"].append(_e)
    return tgt


def mark_pos(e, baseline, body):
    """'a' above the line's writing level, 'b' below — fatha vs kasra territory."""
    cy = (e["y1"] + e["y2"]) / 2
    if baseline is not None:
        return "a" if cy < baseline else "b"
    return "a" if cy < (body["y1"] + body["y2"]) / 2 else "b"


def label_marks(group_atoms, marks, baseline=None):
    """Attach predicted labels to a ligature group's observed marks; True if matched."""
    body = group_atoms[0]["els"][0]
    obs = {"a": [], "b": []}
    for a in group_atoms:
        for e in a["els"][1:]:
            if e.get("mkpart"):
                continue                 # a composite counts once, via its primary
            if e["kind"] != "mark":
                continue                 # a welded letter sliver is not a mark
            obs[mark_pos(e, baseline, body)].append(e)
    ok = True
    for pos in ("a", "b"):
        pred = [lab for lab, p in marks if p == pos]
        got = sorted(obs[pos], key=lambda e: -(e["x1"] + e["x2"]))
        if len(pred) == len(got):
            for lab, e in zip(pred, got):
                e["mark"] = lab
                for part in e.get("mkmembers", []):
                    part["mark"] = lab
        else:
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Rewrite: word groups inside each line group
# ---------------------------------------------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def rewrite(page, assignment):
    """Wrap elements in <g class="word"> / <g class="ligature"> with full metadata.

    Regrouping reorders elements within one original path; ink pieces never overlap
    (proved page-wide by the split verifier), so evenodd parity cannot change. A word
    or ligature whose elements span several source <path> wrappers is emitted once per
    wrapper with the same metadata.
    """
    # For waqf signs recorded by place rather than by shape — see waqf_places().
    _page_no = str(int(os.path.splitext(page.name)[0].split("-")[0].lstrip("0") or 0))
    from add_line_structure import build_d

    # Surah-header and basmalah lines: the DK layout DB says which lines they
    # are (dk_header_lines()); their ink otherwise comes out as anonymous bare
    # paths. Map DK line numbers to art lines through the words already
    # assigned — on 114 of the 116 header pages the numberings are identical,
    # but the ornate spreads' art omits DK line 1 (p1, p2), so every art line
    # runs one behind there. Majority vote over (dk_line - art_line) of all
    # anchored words settles the page's offset without any per-page rule.
    hdr_art = {}
    _hdr_dk = (dk_header_lines().get(int(_page_no) if _page_no.isdigit()
                                     else 0, {})
               if os.environ.get("QSVG_HDR", "1") == "1" else {})
    if _hdr_dk:
        _wtab = _qcf_lines().get(_page_no, {})
        _votes = {}
        for word, atoms in assignment:
            if not word:
                continue
            dk_ln = _wtab.get("%d:%d:%d" % (word["surah"], word["ayah"],
                                            word["pos"]))
            if dk_ln is None:
                continue
            arts = [e["line"] for a in atoms for e in a["els"] if e.get("line")]
            if not arts:
                continue
            art_ln = max(set(arts), key=arts.count)
            _votes[dk_ln - art_ln] = _votes.get(dk_ln - art_ln, 0) + 1
        _off = max(_votes, key=_votes.get) if _votes else 0
        hdr_art = {ln - _off: v for ln, v in _hdr_dk.items() if ln - _off >= 1}
        # the art draws a surah BANNER line that DK carries on the previous
        # page (p453-style): a wordless art line directly above a mapped
        # basmalah is that banner — map it as the surah-name line
        _wlines = set()
        for _wv, _av in assignment:
            if not _wv:
                continue
            for _aa in _av:
                for e in _aa["els"]:
                    if e.get("line"):
                        _wlines.add(e["line"])
        for _lnb, (_knd, _su) in list(hdr_art.items()):
            if _knd == "basmalah" and _lnb - 1 >= 1 \
                    and _lnb - 1 not in _wlines \
                    and _lnb - 1 not in hdr_art:
                hdr_art[_lnb - 1] = ("surah-name", _su)

    # Header ink is inviolable: a word may never hold an element drawn on a
    # header/basmalah line, unless the word itself lives on that line (p1/p2,
    # where the basmalah IS ayah 1:1). Measured mushaf-wide (reported.json
    # item 33): 9 thefts on 8 pages, 8 of them a last-line word reaching into
    # the title below — the superscript recoveries hunt small glyphs and read
    # title letters as small-waw/small-alef/maddah (p590: ٱلصَّـٰلِحَـٰتِ took
    # the dot of the ب in سورة البروج). Evicted ink rejoins the wordless pool,
    # where the header wrapper below picks it up; fabricated mark names are
    # left in place — titles carry real diacritics and are not audited, so a
    # wrong label here is display-only and visible in the header group.
    # ORNAMENT demotion, HEADER CONTEXT ONLY (Abdullah 2026-08-28): a
    # wordless unnamed fragment whose shape the table calls "ignore" AND that
    # sits on a basmalah/surah-name line is banner decoration — plain
    # ornament ink. Anywhere else an unnamed mark stays visible in the
    # UNNAMED review section: an unknown shape could be a stolen real mark.
    if os.environ.get("QSVG_ORNDBG"):
        print("ORNDBG hdr_art=%s wordless-entries=%d" % (
            hdr_art, sum(1 for w, _ in assignment if not w)), file=sys.stderr)
    if hdr_art:
        for _wo9, _ao9 in assignment:
            if _wo9:
                continue
            for _a9 in _ao9:
                for e in _a9["els"]:
                    if (e["kind"] == "mark" and not e.get("mark")
                            and e.get("line") in hdr_art):
                        v9 = shape_labels().get(e.get("sig") or "")
                        lb9 = v9.get("label") if isinstance(v9, dict) else v9
                        if os.environ.get("QSVG_ORNDBG"):
                            print("ORNDBG line=%s sig=%s lb=%s" % (
                                e.get("line"), (e.get("sig") or "")[:8], lb9),
                                file=sys.stderr)
                        if lb9 == "ignore":
                            e["kind"] = "ornament"
                            e.pop("mkpart", None)

    if hdr_art and os.environ.get("QSVG_HDRGUARD", "1") == "1":
        # Exception, p349-measured: a last-line word's own suffix mark (ـهُۥ's
        # ۥ, a maddah) genuinely dips into the header band and the line cut
        # files it under the header line. Such a mark sits at the band's TOP
        # EDGE and inside its word's own x-span; title ink sits at band depth
        # (p590's stolen ب dot: mid-band). Keep only what passes BOTH tests.
        _btop = {}
        for word, atoms in assignment:
            for a in atoms:
                for e in a["els"]:
                    ln = e.get("line")
                    if ln in hdr_art:
                        _btop[ln] = min(_btop.get(ln, 1e9), e["y1"])
        _evicted = []
        for word, atoms in assignment:
            if not word:
                continue
            _lns = [e.get("line") for a in atoms for e in a["els"]
                    if e.get("line")]
            if not _lns:
                continue
            if max(set(_lns), key=_lns.count) in hdr_art:
                continue
            _bx = [(e["x1"], e["x2"]) for a in atoms for e in a["els"]
                   if e["kind"] == "body" and e.get("line") not in hdr_art]
            _wx1 = min((x1 for x1, _ in _bx), default=0)
            _wx2 = max((x2 for _, x2 in _bx), default=0)
            for a in atoms:
                keep = []
                for e in a["els"]:
                    ln = e.get("line")
                    if ln in hdr_art:
                        cx = (e["x1"] + e["x2"]) / 2
                        # left margin 8u: the suffix ۥ/ۦ/maddah trails the
                        # word on ITS LEFT (the next-word side — the p349
                        # trio measured 1.4-2.5u past the body span).
                        # Depth 12u sits in a measured empty band: genuine
                        # dips reach top+8.7 (p570 ذلك's dagger alef), the
                        # one true theft sits at top+19.2 (p590's title dot).
                        dip = (e["kind"] == "mark"
                               and _wx1 - 8 <= cx <= _wx2 + 2
                               and e["y1"] <= _btop.get(ln, 0) + 12.0)
                        # an override-pinned piece is a human verdict —
                        # HDRGUARD never overrules it (p359/p570: the ۦ
                        # after a basmalah, stale header line-tag, seated
                        # by eye).
                        (keep if dip or e.get("_ovr") else _evicted).append(e)
                    else:
                        keep.append(e)
                a["els"] = keep
        if _evicted:
            assignment = assignment + [(None, [{"els": _evicted}])]

    # A word is one thing on the page, but its ink can straddle the boundary
    # between two line paths — a descender dips below it, a mark rides above —
    # and emitting the word once per wrapper leaves half of it inside a line it
    # does not belong to, where that line's ayah polygon cannot reach it. Send
    # every element of a word to the wrapper holding most of that word's ink,
    # so the word is emitted exactly once, in the line it is written on.
    # Nothing about the picture changes: each element is written as its own
    # <path> either way, and every path in this art is the same colour, so
    # coverage composites to the same result whatever order it arrives in.
    home = {}
    for word, atoms in assignment:
        if not word:
            continue
        weight = {}
        for atom in atoms:
            for e in atom["els"]:
                area = max(e["x2"] - e["x1"], 0.01) * max(e["y2"] - e["y1"], 0.01)
                weight[e["path"]] = weight.get(e["path"], 0.0) + area
        if weight:
            home[id(word)] = max(weight, key=weight.get)

    # Policy P5 (Abdullah): the sajdah overline and ۩ are ONE standalone sign,
    # grouped with the sajdah word on the line below the bar — so the whole
    # ejected group is homed to the wrapper holding that word's ink, and the
    # bar and sign come out in the same tag instead of one per source path.
    sa_home = {}
    if os.environ.get("QSVG_SAJ", "1") == "1":
        _sajw = {}
        for word, atoms in assignment:
            if word and "۩" in word["uthmani"] and id(word) in home:
                _sajw[(word["surah"], word["ayah"])] = home[id(word)]
        for word, atoms in assignment:
            if word is not None:
                continue
            for atom in atoms:
                sa = atom.get("sa")
                if not sa or sa[0] != "sajdah":
                    continue
                tgt = _sajw.get((sa[1], sa[2]))
                if tgt is None and len(_sajw) == 1:
                    tgt = next(iter(_sajw.values()))
                if tgt is not None:
                    sa_home[id(atom)] = tgt

    # Invariant: an element is drawn exactly once. Movers that carry a welded
    # master between atoms adopt its mkmembers into the target without pulling
    # them out of their origin atom (p123's doubled dammatan strokes, AA-dark
    # edges on 168 pages). Keep the occurrence that sits beside its master —
    # the atom whose els list it in some mkmembers — else the first.
    occ = {}
    for word, atoms in assignment:
        for atom in atoms:
            for e in atom["els"]:
                occ.setdefault(id(e), []).append(atom)
    for eid_, ats in occ.items():
        if len(ats) < 2:
            continue
        keep = next((a for a in ats
                     if any(any(m is x for m in y.get("mkmembers", []))
                            for y in a["els"] for x in a["els"]
                            if id(x) == eid_)), ats[0])
        for a in ats:
            if a is not keep:
                a["els"] = [x for x in a["els"] if id(x) != eid_]
            else:
                seen_self = False
                kept = []
                for x in a["els"]:
                    if id(x) == eid_:
                        if seen_self:
                            continue
                        seen_self = True
                    kept.append(x)
                a["els"] = kept

    # A dot-family mark is ONE mark (Abdullah, item 36): a three-dots drawn
    # as 2+1 contour groups must emit as a single <path>. Absorb each member's
    # contours into its master when both come from the same source path (same
    # frame — build_d absolutizes separated contours, so coordinates hold and
    # contour conservation is untouched). Cross-path members keep their own
    # path with _reframe, as before.
    if os.environ.get("QSVG_DOTMERGE", "1") == "1":
        # generalized (Abdullah 2026-08-28): EVERY welded sign is ONE mark —
        # a kasratan pair, the ج with its dot, the hizb with its ornament —
        # so occurrence counts are exact. Same-source-frame merge only;
        # cross-path members keep their own reframed path as before.
        for word, atoms in assignment:
            for atom in atoms:
                for e in atom["els"]:
                    if (e.get("mark") and not e.get("mkpart")
                            and e.get("mkmembers")):
                        keepm = []
                        for m in e["mkmembers"]:
                            # the member may sit in ANY atom of the same
                            # word (49 open-kasratan pairs emitted split
                            # because the twin lived one atom over)
                            _hostm = next((a2 for a2 in atoms
                                           if m in a2["els"]), None)
                            if (m.get("path") == e.get("path")
                                    and _hostm is not None):
                                e["contours"] = list(e["contours"]) + \
                                    list(m["contours"])
                                if _hostm is atom:
                                    m["_absorbed"] = True
                                else:
                                    _hostm["els"].remove(m)
                            else:
                                keepm.append(m)
                        e["mkmembers"] = keepm
                if any(x.get("_absorbed") for x in atom["els"]):
                    atom["els"] = [x for x in atom["els"]
                                   if not x.pop("_absorbed", False)]

    per_path = {}
    consumed = set()
    for word, atoms in assignment:
        tgt = home.get(id(word)) if word else None
        for ai, atom in enumerate(atoms):
            tgt_a = tgt if tgt is not None else sa_home.get(id(atom))
            lig = (id(word), atom.get("lig", ai))
            for e in atom["els"]:
                consumed.add(e["path"])
                per_path.setdefault(e["path"] if tgt_a is None else tgt_a,
                                    []).append((word, lig, atom, e))

    if os.environ.get("QSVG_EMDBG"):
        for _pi, _lst in per_path.items():
            for _w4, _lg4, _a4, _e4 in _lst:
                if _e4.get("mkpart") or _e4.get("mark") == "pause":
                    print("EMDBG path=%s word=%s mark=%s mkpart=%s nc=%d line=%s"
                          % (_pi, (_w4 or {}).get("uthmani"), _e4.get("mark"),
                             _e4.get("mkpart"), len(_e4["contours"]),
                             _e4.get("line")), file=sys.stderr)

    def _reframe(src_pi, tgt_pi):
        """transform attribute that repositions contours written in path
        src_pi's local frame so they render identically under path tgt_pi's
        wrappers: inv(M_tgt) . M_src. The p17 قلى pair proved regrouping is
        pixel-free ONLY within one frame — every cross-path emission must
        carry this compensation."""
        ms = page.paths[src_pi]["M"]
        mt = page.paths[tgt_pi]["M"]
        if ms == mt:
            return ""
        a, b, c, d, e_, f_ = mt
        det = a * d - b * c
        inv = (d / det, -b / det, -c / det, a / det,
               (c * f_ - d * e_) / det, (b * e_ - a * f_) / det)
        a1, b1, c1, d1, e1, f1 = inv
        a2, b2, c2, d2, e2, f2 = ms
        comp = (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
                a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
                a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)
        if all(abs(v - w) < 1e-9 for v, w in zip(comp, (1, 0, 0, 1, 0, 0))):
            return ""
        return 'transform="matrix(%g %g %g %g %g %g)" ' % comp

    svg = page.svg
    eid = [0]
    _EIDMAP = []
    if os.environ.get("QSVG_EIDMAP"):
        import atexit as _ae
        def _dump_eidmap(_l=_EIDMAP):
            try:
                json.dump(_l, open(os.environ["QSVG_EIDMAP"], "w"))
            except Exception:
                pass
        _ae.register(_dump_eidmap)
    out, pos = [], 0
    for pi, p in enumerate(page.paths):
        s, t = p["span"]
        out.append(svg[pos:s])
        pos = t
        if pi not in per_path:
            # A path whose elements ALL now live under other homes must not
            # fall back to its original text: that re-draws every contour a
            # second time (the unlabelled قلى duplicates on p17).
            if pi not in consumed:
                out.append(p["text"])
            continue
        a, b = p["d_span"][0] - s, p["d_span"][1] - s
        head, tail = p["text"][:a], p["text"][b:]

        # data-mark carries the SPECIFIC sign; data-mark-family groups the
        # subtyped families (Abdullah 2026-08-28). Budgets stay family-level
        # in the audits — the editions disagree on WHICH waqf sign at 424 of
        # 4,416 positions, so the ink's signature names the subtype while
        # the count answers to the family.
        _MFAM = {"wasl-awla": "waqf", "waqf-awla": "waqf",
                 "waqf-jaiz": "waqf", "waqf-lazim": "waqf",
                 "muanaqah": "waqf", "pause": "waqf",
                 "fathatan": "tanween", "kasratan": "tanween",
                 "dammatan": "tanween",
                 "dot": "dots", "two-dots": "dots", "three-dots": "dots",
                 "sifr-mustadir": "sifr", "sifr-mustatil": "sifr",
                 "sajdah-line": "sajdah", "sajdah-sign": "sajdah",
                 "saktah": "reading-sign", "seen-reading": "reading-sign",
                 "imalah": "reading-sign", "ishmam": "reading-sign",
                 "tashil": "reading-sign"}

        def emit(e):
            eid[0] += 1
            if os.environ.get("QSVG_EIDMAP"):
                _EIDMAP.append({"eid": "e%d" % eid[0],
                                "x1": round(e["x1"], 1), "y1": round(e["y1"], 1),
                                "x2": round(e["x2"], 1), "y2": round(e["y2"], 1),
                                "kind": e["kind"], "mark": e.get("mark"),
                                "part": bool(e.get("mkpart"))})
            extra = '<path data-eid="e%d" data-kind="%s" ' % (eid[0], e["kind"])
            wq = None
            if e.get("sig"):
                # Which pause sign this is: the shapes are distinct outlines,
                # so the signature settles it from the ink
                # (`.cache/marks/waqf_types.json`), by place as fallback.
                wq = waqf_types().get(e["sig"])
                if not wq:
                    _rec = waqf_places().get(_page_no, {}).get(
                        "%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"]))
                    wq = _rec.get("waqf") if isinstance(_rec, dict) else _rec
            nm = e.get("mark")
            if nm == "pause" and wq and wq != "muanaqah":
                nm = wq
            if nm:
                extra += ('data-mark-part="%s" ' if e.get("mkpart")
                          else 'data-mark="%s" ') % nm
                fam = _MFAM.get(nm)
                if fam:
                    extra += 'data-mark-family="%s" ' % fam
            if e.get("sig"):
                extra += 'data-sig="%s" ' % e["sig"]
            if e.get("tanform"):
                extra += 'data-form="%s" ' % e["tanform"]
            if e.get("mnqpair"):
                extra += 'data-pair="%s" ' % e["mnqpair"]
            if e.get("iqpair"):
                extra += 'data-iqlab="%s" ' % e["iqpair"]
            if e.get("fused"):
                extra += 'data-fused="1" '
            if e.get("standalone"):
                extra += ('data-standalone="1" data-surah="%d" data-ayah="%d" '
                          % e["standalone"])
            if e["path"] != pi:
                extra += _reframe(e["path"], pi)
            out.append(head.replace("<path ", extra, 1) + build_d(e["contours"]) + tail)

        open_word = open_lig = None
        open_ayah = None
        open_sa = None
        open_hdr = None
        for word, lig_key, atom, e in per_path[pi]:
            sa = atom.get("sa") if not word else None
            if id(atom) != open_sa and open_sa is not None:
                out.append("</g>")
                open_sa = None
            # A wordless element on a DK-declared header line joins that
            # line's <g class="surah-name"/"basmalah"> group; consecutive
            # clusters of the same line share one group. Pure regrouping in
            # the element's own frame — nothing moves, so pixels cannot.
            hd = hdr_art.get(e.get("line")) \
                if (word is None and not sa and not e.get("offcanvas")) \
                else None
            if open_hdr is not None and hd != open_hdr:
                out.append("</g>")
                open_hdr = None
            if hd is not None:
                if open_hdr is None:
                    if open_lig is not None:
                        out.append("</g>")
                        open_lig = None
                    if open_word is not None:
                        out.append("</g>")
                        open_word = None
                    if open_ayah is not None:
                        out.append("</g>")
                        open_ayah = None
                    out.append('<g class="%s" data-surah="%d">' % hd)
                    open_hdr = hd
                # ONE ITEM per header (Abdullah 2026-08-28): inside a surah
                # name or basmalah the block is the semantic unit — emit the
                # ink plain, no data-eid/kind/mark decomposition. Header
                # glyphs stop polluting the mark inventories too.
                out.append(head.replace(
                    "<path ", '<path data-kind="header-ink" ', 1)
                    + build_d(e["contours"]) + tail)
                continue
            wkey = id(word) if word else None
            if sa and open_sa is None:
                if open_lig is not None:
                    out.append("</g>")
                    open_lig = None
                if open_word is not None:
                    out.append("</g>")
                    open_word = None
                if open_ayah is not None:
                    out.append("</g>")
                    open_ayah = None
                out.append('<g class="%s-mark" data-mark="%s"%s>'
                           % (sa[0], sa[0],
                              (' data-surah="%d" data-ayah="%d"'
                               % (sa[1], sa[2])) if sa[1] else ""))
                open_sa = id(atom)
                emit(e)
                continue
            if wkey != open_word:
                if open_lig is not None:
                    out.append("</g>")
                    open_lig = None
                if open_word is not None:
                    out.append("</g>")
                open_word = None
                akey = (word["surah"], word["ayah"]) if word else None
                if akey != open_ayah:
                    if open_ayah is not None:
                        out.append("</g>")
                    open_ayah = None
                    if akey:
                        out.append('<g class="ayah" data-surah="%d" data-ayah="%d">'
                                   % akey)
                        open_ayah = akey
                if word:
                    # data-qpc is the King Fahd Complex's own text of THIS print, which
                    # is not the same edition as quran.com's uthmani — see qpc_words().
                    # Emitted alongside rather than instead of, so nothing downstream
                    # that reads data-uthmani changes behaviour.
                    out.append('<g class="word" data-surah="%d" data-ayah="%d" '
                               'data-word="%d" data-uthmani="%s" data-imlaei="%s"%s>'
                               % (word["surah"], word["ayah"], word["pos"],
                                  esc(word["uthmani"]), esc(word["imlaei"]),
                                  (' data-qpc="%s"' % esc(word["qpc"]))
                                  if word.get("qpc") else ""))
                    open_word = wkey
            if word and lig_key != open_lig:
                if open_lig is not None:
                    out.append("</g>")
                seg = atom.get("seg")
                out.append('<g class="ligature"%s>'
                           % (' data-text="%s"' % esc(seg["text"]) if seg else ""))
                open_lig = lig_key
            emit(e)
        if open_lig is not None:
            out.append("</g>")
        if open_word is not None:
            out.append("</g>")
        if open_ayah is not None:
            out.append("</g>")
        if open_sa is not None:
            out.append("</g>")
        if open_hdr is not None:
            out.append("</g>")
    out.append(svg[pos:])
    return "".join(out)


# ---------------------------------------------------------------------------

def part_key_for(page):
    """(part_key, known) for composite vetoes: shape id of one element's outer contour."""
    table = shape_labels()
    if not table:
        return None, {}
    from split_line_elements import contour_polylines
    from svg_lines import apply as xform
    from markshape import resample, signature, sig_key
    polys, memo = {}, {}

    from markshape import element_points

    def part_key(e):
        k = id(e)
        if k not in memo:
            pi = e["path"]
            if pi not in polys:
                polys[pi] = contour_polylines(page.paths[pi]["d"])
            cps = [[xform(page.paths[pi]["M"], x, y)
                    for x, y in polys[pi][c["sp"]["index"]]] for c in e["contours"]]
            memo[k] = sig_key(signature(element_points(cps)))
        return memo[k]

    return part_key, {k: v["label"] for k, v in table.items()}


# Auto (vote-derived) labels may force-mark only unambiguous families; anything a
# letter can imitate (pause vs ر, damma vs ء curl, hamza) needs a HUMAN-confirmed
# label before it may override geometry.
_SAFE_AUTO = {"fatha", "kasra", "fathatan", "kasratan", "dot", "two-dots",
              "three-dots", "shadda", "small-circle", "meem-iqlab", "maddah",
              "small-alef", "wasla"}


def _raw_label(sig):
    v = shape_labels().get(sig)
    return v["label"] if isinstance(v, dict) else v


def mark_shape_table():
    out = {}
    for k, v in shape_labels().items():
        lab = v["label"]
        if lab in ("word", "ignore", "hamza", "meem-iqlab"):
            # ء twins stay letters at classify time; apply still labels. The
            # iqlab meem shares its outline with a final letter م, and only
            # the word's text can tell them apart — so it stays letter ink
            # here and is promoted to a mark later, where the text is known.
            continue
        if v.get("auto") and lab not in _SAFE_AUTO:
            continue
        out[k] = lab
    return out


_SHAPE_LABELS = None


def shape_labels():
    """Human-confirmed shape->label table from cluster_marks.py, if present."""
    global _SHAPE_LABELS
    if _SHAPE_LABELS is None:
        p = os.path.join(ROOT, ".cache", "marks", "labels.json")
        _SHAPE_LABELS = (json.load(open(p, encoding="utf-8"))
                         if os.path.exists(p) else {})
    return _SHAPE_LABELS


# The same stroke is a fatha above the letter and a kasra below it; the shape table
# stores one name, the drawn position picks the final label.
_DOTU_F = {"dot": 1, "two-dots": 2, "three-dots": 3}


def dot_budget(txt):
    """Dot units a word's letters own, by the rule audit_marks.dot_want uses.

    A final ya is drawn undotted here, and so is a ya carrying a following hamza —
    شَيۡءٖ is three dots, not five, which our decomposition and MushafDatabase's agree on
    independently.
    """
    raw = _LETTER.findall(txt)
    sk = [(HAMZA_MAP[c][0] if c in HAMZA_MAP else c, c in HAMZA_MAP) for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in DOTS:
            continue
        if ch == "\u064a" and (i == len(sk) - 1
                                or (i + 1 < len(sk) and sk[i + 1][0] == "\u0621")):
            continue
        n += _DOTU_F.get(DOTS[ch][0], 0)
    return n


_POS_SWAP_FAM = ("fatha", "kasra", "fathatan", "kasratan")
_POS_SWAP = {("fatha", "b"): "kasra", ("kasra", "a"): "fatha",
             ("fathatan", "b"): "kasratan", ("kasratan", "a"): "fathatan"}


def apply_shape_labels(page, assignment, baselines):
    """Label every mark element by its outline shape; returns (labeled, total)."""
    table = {k: v["label"] for k, v in shape_labels().items()}
    if not table:
        return 0, 0
    from split_line_elements import contour_polylines
    from svg_lines import apply as xform
    from markshape import resample, signature, sig_key

    polys = {}
    body_pts = {}

    def poly_pts(el, outer_only=False):
        pi = el["path"]
        if pi not in polys:
            polys[pi] = contour_polylines(page.paths[pi]["d"])
        out = []
        for c in (el["contours"][:1] if outer_only else el["contours"]):
            out += [xform(page.paths[pi]["M"], x, y)
                    for x, y in polys[pi][c["sp"]["index"]]]
        return out

    def local_pos(e, atom):
        """Above or below the letter's own ink at the mark's x — not the line.

        A kasra under a letter stacked high in the composition sits above the
        baseline, and a fatha over low teeth like س sits below the line's middle;
        only the ink directly at the mark's x-window resolves both.
        """
        if id(atom) not in body_pts:
            body_pts[id(atom)] = poly_pts(atom["els"][0])
        cy = (e["y1"] + e["y2"]) / 2
        sel = [y for x, y in body_pts[id(atom)]
               if e["x1"] - 0.5 <= x <= e["x2"] + 0.5]
        if not sel:
            sel = [y for _, y in body_pts[id(atom)]]
        return "a" if cy < (min(sel) + max(sel)) / 2 else "b"

    from markshape import composite_signature, element_points

    def el_points(el):
        pi = el["path"]
        if pi not in polys:
            polys[pi] = contour_polylines(page.paths[pi]["d"])
        return element_points([[xform(page.paths[pi]["M"], x, y)
                                for x, y in polys[pi][c["sp"]["index"]]]
                               for c in el["contours"]])

    _MARKY = {"fatha", "kasra", "damma", "fathatan", "kasratan", "dammatan",
              "sukun", "shadda", "hamza", "maddah", "small-alef", "wasla",
              "dot", "two-dots", "three-dots", "pause", "small-circle",
              "small-ya", "small-waw", "small-meem", "small-noon",
              "saktah", "seen-reading", "imalah", "ishmam", "tashil"}
    labeled = total = 0
    for word, atoms in assignment:
        for atom in atoms:
            for e in atom["els"]:
                if e["kind"] != "mark":
                    # a mark-sized blob the baseline test kept as a body: if
                    # its outline is a known mark shape, that wins
                    if (e["kind"] == "body"
                            and max(e["x2"] - e["x1"], e["y2"] - e["y1"]) <= 8.5
                            and not e.get("mark")):
                        try:
                            sg = sig_key(signature(el_points(e)))
                        except Exception:
                            continue
                        lb = table.get(sg)
                        if lb and all(p in _MARKY for p in lb.split("+")):
                            e["kind"] = "mark"
                            e["sig"] = sg
                            e["mark"] = lb
                            labeled += 1
                            total += 1
                    continue             # merged atoms carry several bodies
                if e.get("mkpart"):
                    continue             # labeled through its composite's primary
                total += 1
                members = e.get("mkmembers", [])
                if members:
                    sig = composite_signature([el_points(x) for x in [e] + members])
                else:
                    sig = signature(el_points(e))
                e["sig"] = sig_key(sig)   # exported as data-sig: one decision
                                          # on this shape applies mushaf-wide
                lab = table.get(e["sig"])
                # the dot family is SOLID ink: a nested contour is a ring — a
                # ه/ة head — mislabeled by the auto pass; it is letter ink
                if lab in ("dot", "two-dots", "three-dots") \
                        and len(e.get("contours", [])) > 1:
                    bbs = [c["sp"] for c in e["contours"]]
                    for _i, _a in enumerate(bbs):
                        for _b in bbs[_i + 1:]:
                            if (_a["xmin"] <= _b["xmin"] and _a["xmax"] >= _b["xmax"]
                                    and _a["ymin"] <= _b["ymin"]
                                    and _a["ymax"] >= _b["ymax"]) or \
                               (_b["xmin"] <= _a["xmin"] and _b["xmax"] >= _a["xmax"]
                                    and _b["ymin"] <= _a["ymin"]
                                    and _b["ymax"] >= _a["ymax"]):
                                lab = "letter-part"
                if lab in ("ignore", "word", "letter-part", "letter-hamza", "letter"):
                    if lab in ("letter", "letter-part", "letter-hamza"):
                        e["kind"] = "body"   # letter ink misfiled as a mark
                    labeled += 1          # identified as non-mark ink: accounted for
                    continue
                if not lab and members:
                    # a composite of dot glyphs is the letter's full dot group:
                    # ث draws three-dots as a two-dot path plus a one-dot path
                    DOTN = {"dot": 1, "two-dots": 2, "three-dots": 3}
                    pl = [table.get(sig_key(signature(el_points(x))))
                          for x in [e] + members]
                    if "ignore" in pl:
                        # invisible sliver welded to a real mark: judge the rest
                        core = [l for l in pl if l != "ignore"]
                        if len(core) == 1 and core[0]:
                            lab = core[0]
                        pl = core
                    if pl and all(l in DOTN for l in pl):
                        lab = {1: "dot", 2: "two-dots", 3: "three-dots"}.get(
                            sum(DOTN[l] for l in pl))
                    elif pl and all(l == "pause" or l in DOTN for l in pl) \
                            and "pause" in pl:
                        lab = "pause"     # waqf letter + its dot(s)
                    elif pl and all(pl) and not any(
                            l in ("word", "ignore", "letter", "letter-hamza",
                                  "letter-part") for l in pl):
                        # every part is individually known: a stacked group whose
                        # welded outline was never seen — name it top-to-bottom and
                        # let the compound splitter cut it back into single marks
                        order = sorted(zip([e] + members, pl),
                                       key=lambda t: t[0]["y1"])
                        lab = "+".join(l for _, l in order)
                if not lab and (e["y2"] - e["y1"]) < 2.5 \
                        and (e["x2"] - e["x1"]) > 15.0:
                    lab = "sajdah"        # overline bars have per-length outlines
                if not lab or lab in ("ignore", "word", "letter-part", "letter-hamza", "letter"):
                    if not lab and os.environ.get("QSVG_DEBUG_UNACC"):
                        print("UNACC sig", e["sig"], "x%.1f..%.1f y%.1f..%.1f members %d"
                              % (e["x1"], e["x2"], e["y1"], e["y2"], len(members)),
                          file=sys.stderr)
                    continue
                if "+" in lab:
                    # compound label for a stacked group drawn touching: names are
                    # top-to-bottom; parts split into name-groups at the largest
                    # vertical gaps (a pause sign's own dot stays with its curl)
                    names = [x.strip() for x in lab.split("+")]
                    parts = sorted([e] + members,
                                   key=lambda x: (x["y1"] + x["y2"]) / 2)
                    if len(parts) >= len(names):
                        gaps = sorted(range(1, len(parts)),
                                      key=lambda i: (parts[i]["y1"] + parts[i]["y2"])
                                      - (parts[i-1]["y1"] + parts[i-1]["y2"]),
                                      reverse=True)[:len(names) - 1]
                        cuts = sorted(gaps)
                        gi = 0
                        for i, pt in enumerate(parts):
                            if gi < len(cuts) and i >= cuts[gi]:
                                gi += 1
                            pt["mark"] = names[min(gi, len(names) - 1)]
                        labeled += 1
                    else:
                        # the art drew the stack as one connected contour: the
                        # ink cannot be cut without redrawing it, so the single
                        # path keeps the compound name, flagged as fused
                        e["mark"] = lab
                        e["fused"] = True
                        labeled += 1
                    continue
                pos = local_pos(e, atom)
                final = _POS_SWAP.get((lab, pos), lab)
                e["mark"] = final
                for part in members:
                    part["mark"] = final
                labeled += 1
            compose_tanween(atom)
    return labeled, total


def compose_tanween(atom):
    """Two stacked identical strokes are one tanween: fatha+fatha -> fathatan.

    The dammatan glyph is drawn as one outline and labels directly; the stroke
    tanweens are drawn as two separate strokes, so without this pass the taxonomy
    would be inconsistent across the three.
    """
    # KFQC tucks a shadda's kasra UNDER the shadda but ABOVE the letter, where the
    # letter-relative rule would read it as fatha. When a stroke shares x-range
    # with a shadda, the shadda is the reference: below it = kasra, above = fatha.
    shaddas = [e for e in atom["els"][1:] if e.get("mark") == "shadda"]
    if shaddas:
        for e in atom["els"][1:]:
            if e.get("mark") not in ("fatha", "kasra"):
                continue
            for sh in shaddas:
                ov = min(e["x2"], sh["x2"]) - max(e["x1"], sh["x1"])
                if ov < 0.5 * min(e["x2"] - e["x1"], sh["x2"] - sh["x1"]):
                    continue
                below = (e["y1"] + e["y2"]) / 2 > (sh["y1"] + sh["y2"]) / 2
                e["mark"] = "kasra" if below else "fatha"
                break

    # A dammatan drawn as two curls: one piece often matches the damma shape and
    # the other a dedicated fragment labeled dammatan; touching pieces weld.
    pool = [e for e in atom["els"][1:] if e.get("mark") in ("damma", "dammatan")]
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if "dammatan" not in (a.get("mark"), b.get("mark")):
                continue
            dx = abs((a["x1"] + a["x2"]) / 2 - (b["x1"] + b["x2"]) / 2)
            dy = abs((a["y1"] + a["y2"]) / 2 - (b["y1"] + b["y2"]) / 2)
            if dx < 7.0 and dy < 6.0:
                a["mark"] = b["mark"] = "dammatan"

    def _weld_pairs():
        # a tanween's two strokes (or two damma curls) present as ONE mark: the
        # top piece is the master, the other becomes its part
        for lab in ("fathatan", "kasratan", "dammatan"):
            grp = [e for e in atom["els"][1:] if e.get("mark") == lab
                   and not e.get("mkpart")]
            grp.sort(key=lambda e: (e["y1"] + e["y2"]))
            while len(grp) >= 2:
                master, part = grp[0], grp[1]
                dx = abs((master["x1"] + master["x2"]) / 2
                         - (part["x1"] + part["x2"]) / 2)
                dy = abs((master["y1"] + master["y2"]) / 2
                         - (part["y1"] + part["y2"]) / 2)
                if dx < 8.0 and dy < 7.0:
                    part["mkpart"] = True
                    master.setdefault("mkmembers", []).append(part)
                    grp = [master] + grp[2:]
                    grp = grp[1:]        # master consumed one part; next pair
                else:
                    grp = grp[1:]

    for base, tan in (("fatha", "fathatan"), ("kasra", "kasratan")):
        strokes = [e for e in atom["els"][1:] if e.get("mark") == base]
        for i, a in enumerate(strokes):
            for b in strokes[i + 1:]:
                dx = abs((a["x1"] + a["x2"]) / 2 - (b["x1"] + b["x2"]) / 2)
                dy = abs((a["y1"] + a["y2"]) / 2 - (b["y1"] + b["y2"]) / 2)
                # measured on real tanween: parallel strokes nearly level,
                # side-stepped ~3.4 units; neighbouring letters' fathas differ
                # by dy >= 4 or dx >= 5
                lim = 4.2 if base == "fatha" else 5.5
                if dx < lim and dy < 2.2:
                    a["mark"] = b["mark"] = tan


def map_lines(art_widths, api_lines):
    """Order-preserving map from API word-lines to art lines, skipping ornament lines.

    A surah-header page dedicates one or two drawn lines to the header frame and the
    bismillah; the layout data numbers only word-bearing lines, so numbers drift by
    the count of ornament lines above. Match each API line (expected width from its
    words' letters) to an art line (measured ink width) in order, allowing art lines
    to be skipped at a cost — on ordinary pages the identity mapping wins untouched.
    """
    arts = sorted(art_widths)
    apis = sorted(api_lines)
    if not arts or not apis:
        return {}
    exp = {j: sum(letters(w) for w in api_lines[j]) for j in apis}
    total_ink = sum(art_widths[i] for i in arts)
    alpha = total_ink / max(1e-9, sum(exp.values()))

    INF = float("inf")
    n, m = len(arts), len(apis)
    if m > n:
        return {j: j for j in apis}          # malformed; keep identity
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    SKIP = 1.0
    for i in range(1, n + 1):
        for j in range(0, m + 1):
            # skip art line i (ornament)
            if dp[i - 1][j] + SKIP < dp[i][j]:
                dp[i][j] = dp[i - 1][j] + SKIP
                back[i][j] = "skip"
            if j:
                c = abs(art_widths[arts[i - 1]] - alpha * exp[apis[j - 1]]) \
                    / max(1e-9, alpha * exp[apis[j - 1]])
                if dp[i - 1][j - 1] + c < dp[i][j]:
                    dp[i][j] = dp[i - 1][j - 1] + c
                    back[i][j] = "match"
    mapping, i, j = {}, n, m
    while i and back[i][j]:
        if back[i][j] == "match":
            mapping[arts[i - 1]] = apis[j - 1]
            j -= 1
        i -= 1
    return mapping


def reflow_words(words_by_line, art_widths, prev_tail=None, next_head=None,
                 page_ayahs=None):
    """Redistribute the page's word sequence over the art's text lines by width.

    Surah-opening pages in this print pack the text into fewer, wider lines than any
    public layout records (page 77: 13 art lines vs 14 layout lines), so the layout's
    per-line lists cannot be trusted there. The word ORDER is identical, so partition
    the flow into consecutive per-line groups whose expected widths fit the measured
    line widths. Ornament lines (surah title, bismillah) are the narrow ones and get
    no words.
    """
    api_ids = sorted(words_by_line)
    if not api_ids or not art_widths:
        return words_by_line, {}
    wmax = max(art_widths.values())
    text_lines = [ln for ln in sorted(art_widths) if art_widths[ln] >= 0.72 * wmax]
    if len(api_ids) == len(text_lines):
        return words_by_line, {}          # counts agree; trust the layout's lists
    # The page boundary itself can differ between prints (art page 590 starts at
    # 84:25 while the layout's does at 85:1), so the candidate stream includes the
    # neighbouring pages' edge words, and the fit chooses the window: any prefix
    # may stay unused (previous page's ink) and any suffix likewise.
    core = [w for j in api_ids for w in words_by_line[j]]
    pre = len(prev_tail or [])
    flow = (prev_tail or []) + core + (next_head or [])
    core_end = pre + len(core)
    widths = [art_widths[ln] for ln in text_lines]
    lens = [letters(w) for w in flow]
    # letters() is in calibrated absolute units; the residual scale is spacing/
    # justification overhead (measured median 1.088). Solve once with that seed,
    # then re-estimate from the solution's own window and solve again — an edge
    # page's totals cannot bias the seed the way whole-page ratios did.
    alpha = 1.088
    n, m = len(flow), len(text_lines)
    MAXW = 22                             # words per line never exceed this
    SKIP_W = 0.8                          # dropping a current-page word costs its width
    INF = float("inf")

    # The page's own ayah polygons say exactly which ayahs have ink here: the
    # window must contain every word of the interior ayahs and may only trim
    # within the first and last (page-straddling) ayahs.
    if page_ayahs:
        keys = [(w["surah"], w["ayah"]) for w in flow]
        first, last = page_ayahs[0], page_ayahs[-1]
        idx_first = [i for i, k in enumerate(keys) if k == first]
        idx_last = [i for i, k in enumerate(keys) if k == last]
        start_lo = idx_first[0] if idx_first else 0
        start_hi = (idx_first[-1] + 1) if idx_first else n
        end_lo = idx_last[0] + 1 if idx_last else 0
        end_hi = (idx_last[-1] + 1) if idx_last else n
    else:
        start_lo, start_hi, end_lo, end_hi = 0, n, 0, n

    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(start_lo, start_hi + 1):
        dp[i][0] = 0.0
    for k in range(1, m + 1):
        for i in range(k, n + 1):
            for j in range(max(k - 1, i - MAXW), i):
                if dp[j][k - 1] == INF:
                    continue
                c = dp[j][k - 1] + abs(alpha * sum(lens[j:i]) - widths[k - 1])
                if c < dp[i][k]:
                    dp[i][k] = c
                    back[i][k] = j
    cand = [i for i in range(max(m, end_lo), min(n, end_hi) + 1)
            if dp[i][m] < INF]
    if not cand:
        return words_by_line, {}
    end = min(cand, key=lambda i: dp[i][m])
    bounds, i = [], end
    for k in range(m, 0, -1):
        j = back[i][k]
        bounds.append((j, i))
        i = j
    bounds.reverse()
    return ({ln: flow[j:i] for ln, (j, i) in zip(text_lines, bounds)},
            {"reflowed": True})


def poly_ayahs(edition, page_no):
    """The set of (surah, ayah) a page's polygons draw; empty if unknown."""
    pth = os.path.join(ROOT, "mushafs", edition, "json", "%03d.json" % page_no)
    if not os.path.exists(pth):
        return set()
    try:
        return {(p["surahNumber"], p["ayahNumber"])
                for p in json.load(open(pth))}
    except Exception:
        return set()


def ayah_stream(page_no, cache_dir, page_ayahs):
    """Every word of every ayah the page's polygons draw, in text order.

    The QCF layout's page boundaries can differ from this print by whole
    ayahs, so a fixed-size window of the neighbouring pages' words can miss
    the ones the art actually draws. The polygons name the ayahs; collect
    their words from the pages around this one and let the reflow DP (which
    trims the first and last ayah freely) decide where they sit.
    """
    want = set(page_ayahs or ())
    if not want:
        return []
    out = {}
    for pn in range(max(1, page_no - 2), min(604, page_no + 2) + 1):
        try:
            wl = page_words(pn, cache_dir)
        except Exception:
            continue
        for j in wl:
            for w in wl[j]:
                if (w["surah"], w["ayah"]) in want:
                    out[(w["surah"], w["ayah"], w["pos"])] = w
    return [out[k] for k in sorted(out)]


def polygon_reflow(page_ayahs, ay_ranges, stream, use_qcf=False,
                   free_head=True, free_tail=True):
    """Per-line word lists derived from the ayah polygons themselves.

    Each ayah's polygon says exactly which lines it inks and how wide each portion
    is, so its words partition across those lines by width — no page-level window
    guessing. A page-straddling first (last) ayah keeps a suffix (prefix) of its
    words, sized by its measured ink here.
    """
    per_line = {}
    # per-word QCF advance widths partition far better than letter counts;
    # calibrate their scale against the total drawn width of this page's ayahs
    _q = qcf_widths()

    def _qw(w):
        return _q.get("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                      2.5 * max(1, letters(w)))
    _tw = _tq = 0.0
    for key in page_ayahs:
        for ln, r in ay_ranges.items():
            if key in r:
                _tw += r[key][1] - r[key][0]
        for w in stream:
            if (w["surah"], w["ayah"]) == key:
                _tq += _qw(w)
    _s = (_tw / _tq) if (_tq and use_qcf) else 1.088
    for idx, key in enumerate(page_ayahs):
        segs = sorted(((ln, r[key]) for ln, r in ay_ranges.items() if key in r),
                      key=lambda t: t[0])
        words_k = [w for w in stream if (w["surah"], w["ayah"]) == key]
        if not segs or not words_k:
            continue
        widths = [x2 - x1 for _, (x1, x2) in segs]
        lens = ([_qw(w) for w in words_k] if use_qcf
                else [letters(w) for w in words_k])
        n, m = len(words_k), len(segs)
        # the first ayah keeps a free prefix only when the PREVIOUS page's
        # polygons also draw it; otherwise every one of its words is here
        free_prefix = idx == 0 and free_head
        free_suffix = idx == len(page_ayahs) - 1 and free_tail
        INF = float("inf")
        dp = [[INF] * (m + 1) for _ in range(n + 1)]
        back = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            if i == 0 or free_prefix:
                dp[i][0] = 0.0
        for k in range(1, m + 1):
            for i in range(k, n + 1):
                for j in range(k - 1, i):
                    if dp[j][k - 1] == INF:
                        continue
                    c = dp[j][k - 1] + abs(_s * sum(lens[j:i]) - widths[k - 1])
                    if c < dp[i][k]:
                        dp[i][k] = c
                        back[i][k] = j
        ends = range(m, n + 1) if free_suffix else [n]
        cand = [i for i in ends if dp[i][m] < INF]
        if not cand:
            continue
        end = min(cand, key=lambda i: dp[i][m])
        bounds, i = [], end
        for k in range(m, 0, -1):
            j = back[i][k]
            bounds.append((j, i))
            i = j
        bounds.reverse()
        for (ln, (x1, x2)), (j, i) in zip(segs, bounds):
            per_line.setdefault(ln, []).append((x2, words_k[j:i]))
    return {ln: [w for _, ws in sorted(items, key=lambda t: -t[0]) for w in ws]
            for ln, items in per_line.items()}


def anchored_reflow(words_by_line, art_widths):
    """Re-fit the layout's per-line lists to the drawn line widths, gently.

    The art's line breaks occasionally drift a word or two from the public layout
    mid-page (page 3 lines 8-10). Partition the page's word sequence into the drawn
    lines minimizing width misfit plus a per-word anchor penalty for leaving its
    layout line — an exact page stays exactly as listed, drift moves only where the
    ink demands it.
    """
    api_ids = sorted(words_by_line)
    wmax = max(art_widths.values()) if art_widths else 0
    text_lines = [ln for ln in sorted(art_widths) if art_widths[ln] >= 0.72 * wmax]
    if len(api_ids) != len(text_lines):
        return words_by_line
    flow, api_ord = [], []
    for oi, j in enumerate(api_ids):
        for w in words_by_line[j]:
            flow.append(w)
            api_ord.append(oi)
    widths = [art_widths[ln] for ln in text_lines]
    lens = [letters(w) for w in flow]
    alpha = sum(widths) / max(1e-9, sum(lens))
    ANCHOR = 3.0
    n, m = len(flow), len(text_lines)
    MAXW = 22
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    pre_pen = [[0.0] * (m + 1)]
    for i in range(1, n + 1):
        pre_pen.append([pre_pen[-1][k] + abs(api_ord[i - 1] - k) * ANCHOR
                        for k in range(m + 1)])
    for k in range(1, m + 1):
        for i in range(k, n - (m - k) + 1):
            for j in range(max(k - 1, i - MAXW), i):
                if dp[j][k - 1] == INF:
                    continue
                c = (dp[j][k - 1] + abs(alpha * sum(lens[j:i]) - widths[k - 1])
                     + (pre_pen[i][k - 1] - pre_pen[j][k - 1]))
                if c < dp[i][k]:
                    dp[i][k] = c
                    back[i][k] = j
    if dp[n][m] == INF:
        return words_by_line
    bounds, i = [], n
    for k in range(m, 0, -1):
        j = back[i][k]
        bounds.append((j, i))
        i = j
    bounds.reverse()
    return {ln: flow[j:i] for ln, (j, i) in zip(text_lines, bounds)}


def tag_ayah_markers(svg, polys_json):
    """Give every ayah medallion its own identified group.

    The art draws each marker as two sibling groups inside #ayah_markers — the
    ornament ring (a scaled glyph) followed by the numeral ink. Markers appear
    in ayah order, so pairing them with the page's sorted ayah list names them.
    The pair is wrapped in <g class="ayah-marker" data-surah data-ayah>, with
    data-kind on the ornament and the numeral separately.
    """
    i = svg.find('<g id="ayah_markers"')
    if i < 0 or not polys_json:
        return svg
    depth = 0
    j = i
    for m in re.finditer(r"<g\b|</g>", svg[i:]):
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            j = i + m.end()
            break
    block = svg[i:j]

    seen = []
    for pl in polys_json:
        key = (pl["surahNumber"], pl["ayahNumber"])
        if key not in seen:
            seen.append(key)
    seen.sort()

    kids = list(re.finditer(r"<g\b[^>]*>(?:(?!</?g\b).)*</g>", block, re.S))
    pairs = []
    k = 0
    while k < len(kids):
        if "scale(" in kids[k].group(0) and k + 1 < len(kids) \
                and "ayah:x" in kids[k + 1].group(0):
            pairs.append((kids[k], kids[k + 1]))
            k += 2
        else:
            pairs.append((kids[k], None))
            k += 1

    out = []
    pos = 0
    for idx, (orn, dig) in enumerate(pairs):
        su, ay = seen[idx] if idx < len(seen) else (None, None)
        ident = (' data-surah="%d" data-ayah="%d"' % (su, ay)) if su else ""
        out.append(block[pos:orn.start()])
        piece = orn.group(0).replace(
            "<path ", '<path data-kind="ayah-marker-ornament" ', 1)
        if dig is not None:
            piece += block[orn.end():dig.start()]
            piece += dig.group(0).replace(
                "<path ", '<path data-kind="ayah-number" ', 1)
            pos = dig.end()
        else:
            pos = orn.end()
        out.append('<g class="ayah-marker"%s>%s</g>' % (ident, piece))
    out.append(block[pos:])
    return svg[:i] + "".join(out) + svg[j:]


def assign_page(edition, page_no, cache_dir):
    src = os.path.join(ROOT, "mushafs", edition, "svg", "%03d.svg" % page_no)
    page = Page(src)
    words_by_line = page_words(page_no, cache_dir)
    elements = page_elements(page)
    # Ink clipped away by the viewBox is invisible: keep it out of classification
    # and word clustering, but re-emit it unassigned so no ink is ever dropped.
    offcanvas = [e for e in elements if e.get("offcanvas")]
    elements = [e for e in elements if not e.get("offcanvas")]
    for e in offcanvas:
        e["kind"] = "body"
    lines_path = os.path.join(ROOT, "mushafs", edition, "lines", "%03d.json" % page_no)
    lines_info = json.load(open(lines_path)) if os.path.exists(lines_path) else []
    pk, known = part_key_for(page)
    mark_shapes = mark_shape_table()
    classify(elements, lines_info, pk, mark_shapes)
    composite_marks(elements, pk, known)
    baselines = {li["lineNumber"]: li["baseline"] for li in lines_info}

    # A letter BODY belongs to the band its center falls in — the ornate pages'
    # art groups occasionally tag ink with the neighbouring line, which lets a
    # word swallow pieces from the line above or below. Geometry is the truth
    # for bodies (marks are handled by their own re-liner below).
    if lines_info:
        bands = sorted(((li["lineNumber"],
                         li.get("top", li["baseline"] - 12),
                         li.get("bottom", li["baseline"] + 3))
                        for li in lines_info), key=lambda t: t[1])
        for e in elements:
            if not e["line"]:
                continue
            cy = (e["y1"] + e["y2"]) / 2
            best = None
            for ln2, top, bot in bands:
                if top <= cy <= bot:
                    best = ln2
                    break
                d = min(abs(cy - top), abs(cy - bot))
                if best is None or isinstance(best, tuple) and d < best[1]:
                    best = (ln2, d)
            if isinstance(best, tuple):
                # marks float in the inter-band gap by design: snap to nearest
                # band always; a body far from every band keeps its art tag
                best = best[0] if (e["kind"] == "mark" or best[1] < 6.0) else None
            if best and best != e["line"]:
                e["line"] = best

    # A mark belongs to its LETTER, not to whatever line band its ink fell into:
    # a deep kasra under line N sits in line N+1's band and would attach to the
    # word below. Re-line each mark to the nearest overlapping body in ln-1..ln+1.
    bodies_by_line = {}
    for e in elements:
        if e["kind"] == "body" and e["line"]:
            bodies_by_line.setdefault(e["line"], []).append(e)
    for e in elements:
        if e["kind"] != "mark" or e.get("mkpart") or not e["line"]:
            continue
        cx = (e["x1"] + e["x2"]) / 2
        cy = (e["y1"] + e["y2"]) / 2
        # These marks are only ever drawn ABOVE their letter in this art: a damma,
        # waqf sign or iqlab-meem hanging in the gap between two lines belongs to
        # the line BELOW it, never to the word whose ink ends above it.
        lab_pos = e.get("lab") or _raw_label(pk(e)) if pk else e.get("lab")
        above_only = lab_pos in _ABOVE_ONLY
        best = None
        for ln2 in (e["line"] - 1, e["line"], e["line"] + 1):
            for b in bodies_by_line.get(ln2, []):
                if above_only and cy > b["y2"]:
                    continue              # mark below this word: impossible owner
                ov = min(e["x2"], b["x2"]) - max(e["x1"], b["x1"])
                # a mark over a THIN letter (an alef) hangs to its left in this
                # art — plain x-overlap misses the pairing entirely
                thin_near = (b["x2"] - b["x1"]) <= 4.5 and \
                    abs((b["x1"] + b["x2"]) / 2 - cx) <= 3.5
                if ov < 0.3 * (e["x2"] - e["x1"]) and not thin_near:
                    continue
                # distance to the body's natural mark zones (just above its top
                # or just below its bottom) — sitting BESIDE a deep descender is
                # not ownership, so being inside the body's y-band earns no bonus
                vd = (abs(cy - b["y1"]) if above_only
                      else min(abs(cy - b["y1"]), abs(cy - b["y2"])))
                if ln2 != e["line"]:
                    vd += 2.5             # stay on your own line unless clearly closer
                score = (vd, -ov, abs((b["x1"] + b["x2"]) / 2 - cx))
                if best is None or score < best[0]:
                    best = (score, ln2)
        if best is None:
            # no x-overlapping body anywhere: a dot leaning off its letter's
            # edge — take the nearest body sideways
            for ln2 in (e["line"] - 1, e["line"], e["line"] + 1):
                for b in bodies_by_line.get(ln2, []):
                    gap = max(b["x1"] - e["x2"], e["x1"] - b["x2"], 0.0)
                    if gap > 6.0:
                        continue
                    vd = min(abs(cy - b["y1"]), abs(cy - b["y2"]))
                    if ln2 != e["line"]:
                        vd += 2.5
                    score = (vd + gap, 0, 0)
                    if best is None or score < best[0]:
                        best = (score, ln2)
        if best and best[1] != e["line"]:
            e["line"] = best[1]
            for part in e.get("mkmembers", []):
                part["line"] = best[1]
    # Line-break refinement by ink amount: the art sometimes breaks a line a
    # word earlier or later than every public layout. Ink amount per line is
    # immune to justification: move boundary words while both lines' ink-vs-
    # expected errors clearly improve.
    _ink = {}
    for e in elements:
        if e["kind"] == "body" and e.get("line"):
            _ink[e["line"]] = _ink.get(e["line"], 0.0) + (e["x2"] - e["x1"])

    def _ink_refine(wbl):
        lns = sorted(ln for ln in wbl if wbl[ln] and ln in _ink)
        if len(lns) < 2:
            return
        exp = {ln: sum(letters(w) for w in wbl[ln]) for ln in lns}
        k = sum(_ink[ln] for ln in lns) / (sum(exp[ln] for ln in lns) or 1.0)
        for _ in range(4):
            best = None
            for i in range(len(lns) - 1):
                L, L2 = lns[i], lns[i + 1]
                for dirn in (0, 1):
                    src = L if dirn == 0 else L2
                    if len(wbl[src]) < 2:
                        continue
                    wm = wbl[L][-1] if dirn == 0 else wbl[L2][0]
                    dl = -letters(wm) if dirn == 0 else letters(wm)
                    b1 = abs(_ink[L] - k * exp[L])
                    b2 = abs(_ink[L2] - k * exp[L2])
                    a1 = abs(_ink[L] - k * (exp[L] + dl))
                    a2 = abs(_ink[L2] - k * (exp[L2] - dl))
                    gain = (b1 + b2) - (a1 + a2)
                    # both lines must individually get closer to their ink
                    if a1 < b1 and a2 < b2 \
                            and gain > 0.75 * k * letters(wm) \
                            and (best is None or gain > best[0]):
                        best = (gain, L, L2, dirn, wm)
            if best is None:
                break
            _, L, L2, dirn, wm = best
            if os.environ.get("QSVG_LDBG"):
                print("LDBG ink_refine move %d:%d:%d %s -> %s"
                      % (wm["surah"], wm["ayah"], wm["pos"],
                         L if dirn == 0 else L2, L2 if dirn == 0 else L),
                      file=sys.stderr)
            if dirn == 0:
                wbl[L].pop()
                wbl[L2].insert(0, wm)
                exp[L] -= letters(wm)
                exp[L2] += letters(wm)
            else:
                wbl[L2].pop(0)
                wbl[L].append(wm)
                exp[L2] -= letters(wm)
                exp[L] += letters(wm)

    polys_path = os.path.join(ROOT, "mushafs", edition, "json", "%03d.json" % page_no)
    ay_ranges = (ayah_ranges_per_line(json.load(open(polys_path)), lines_info)
                 if os.path.exists(polys_path) else {})
    # A page's polygons can omit a whole text line (p599 draws 98:6's first
    # ten words on line 1, but its first polygon row starts in line 2's band).
    # The reflow then has nothing to hang that ink on and the words are drawn
    # by no page at all. Ink is the truth: give an unclaimed full-width line
    # to the page's first (above every claimed line) or last (below) ayah, so
    # the partition DP can spread that ayah's words across both lines.
    if ay_ranges and os.path.exists(polys_path):
        _seen0 = []
        for _p0 in json.load(open(polys_path)):
            _k0 = (_p0["surahNumber"], _p0["ayahNumber"])
            if _k0 not in _seen0:
                _seen0.append(_k0)
        _seen0 = sorted(_seen0)
        _ink0 = {}
        for _e0 in elements:
            if _e0["kind"] == "body" and _e0.get("line"):
                _x1, _x2 = _ink0.get(_e0["line"], (_e0["x1"], _e0["x2"]))
                _ink0[_e0["line"]] = (min(_x1, _e0["x1"]), max(_x2, _e0["x2"]))
        if _ink0 and _seen0:
            _wmax0 = max(b - a for a, b in _ink0.values())
            _claimed = set(ay_ranges)
            _lo_c, _hi_c = min(_claimed), max(_claimed)
            for _ln0, (_x1, _x2) in sorted(_ink0.items()):
                if _ln0 in _claimed or _x2 - _x1 < 0.72 * _wmax0:
                    continue
                if _ln0 < _lo_c:
                    _key0 = _seen0[0]
                elif _ln0 > _hi_c:
                    _key0 = _seen0[-1]
                else:
                    continue
                ay_ranges.setdefault(_ln0, {})[_key0] = (_x1, _x2)
    _ay_lines = {}
    for _ln2, _rngs in ay_ranges.items():
        for _key in _rngs:
            _ay_lines.setdefault(_key, set()).add(_ln2)

    # Clustering the same line with the same word list is pure: the boundary
    # hill-climb re-scores whole pages to move ONE word, so without a memo a
    # 15-line page is clustered thousands of times (p350: 8,416 calls, 507s).
    # The key carries a fingerprint of the line's ink so a reclaim pass that
    # turns marks into bodies is never served a stale split.
    _cl_memo = {}

    def _cl(els4, words4, ayr4, alpha4=1.0, use_dots=True):
        # key on the element OBJECTS, not their statistics: p604's three
        # identical basmalah lines collided on (len, body-count) and lines
        # 6/11 were handed line 2's cached atoms — line-2 ink emitted three
        # times while 6/11's own went back to passthrough.
        key = (id(ayr4), round(alpha4, 4), use_dots,
               tuple(id(e) for e in els4),
               tuple((w["surah"], w["ayah"], w["pos"]) for w in words4))
        hit = _cl_memo.get(key)
        if hit is None:
            hit = cluster_line(els4, words4, ayr4, alpha4, use_dots=use_dots)
            _cl_memo[key] = hit
        cls4, dev4 = hit
        # hand out fresh containers: consumers mutate atom["els"] downstream
        return [[{"x1": a4["x1"], "x2": a4["x2"], "els": list(a4["els"])}
                 for a4 in cl4] for cl4 in cls4], dev4

    def _ayah_allowed(w5, ln5):
        # the polygons are the art's own statement of which ayahs occupy which
        # line: a word may never be moved onto a line its ayah does not touch
        rows5 = ay_ranges.get(ln5)
        if not ay_ranges or not rows5:
            return True
        return (w5["surah"], w5["ayah"]) in rows5

    def _count_conflicts(wbl):
        # forward: a wide polygon row whose ayah has no words on the line;
        # reverse: words on a line their ayah's polygon never touches. A lone
        # reverse hit is usually a filtered-out thin polygon row, so it only
        # counts once the disagreement is dense.
        nf = nr = 0
        for _ln, _ws in wbl.items():
            have = {(w["surah"], w["ayah"]) for w in _ws}
            for _key, (_lo, _hi) in ay_ranges.get(_ln, {}).items():
                if _hi - _lo >= 18 and _key not in have:
                    nf += 1
            for _key in have:
                if _key in _ay_lines and _ln not in _ay_lines[_key]:
                    nr += 1
        return nf + (nr if nr >= 3 else 0)

    # only pages where the polygons disagree with the layout get the ink-based
    # boundary moves; everywhere else the layout is already the art's truth
    if ay_ranges and _count_conflicts(words_by_line) >= 3:
        _ink_refine(words_by_line)

    def run_pass(words_by_line, grounded=False):
        assignment, report = [], []
        art_widths = {}
        for ln in {e["line"] for e in elements if e["line"]}:
            bs = [e for e in elements if e["line"] == ln and e["kind"] == "body"]
            art_widths[ln] = (max(b["x2"] for b in bs) - min(b["x1"] for b in bs)) if bs else 0.0
        prev_tail = next_head = None
        try:
            if page_no > 1:
                pw = page_words(page_no - 1, cache_dir)
                # TEXT order, not line order: QCF wraps overflow words onto
                # "lines 1-2" of the same page, which sort first by line and
                # would fall out of a line-ordered tail
                prev_tail = sorted((w for j in pw for w in pw[j]),
                                   key=lambda w: (w["surah"], w["ayah"],
                                                  w["pos"]))[-25:]
            if page_no < 604:
                nw = page_words(page_no + 1, cache_dir)
                next_head = sorted((w for j in nw for w in nw[j]),
                                   key=lambda w: (w["surah"], w["ayah"],
                                                  w["pos"]))[:25]
        except Exception:
            pass
        page_ayahs = None
        if os.path.exists(polys_path):
            seen = []
            for p in json.load(open(polys_path)):
                k = (p["surahNumber"], p["ayahNumber"])
                if k not in seen:
                    seen.append(k)
            page_ayahs = sorted(seen)
        # The layout's own line numbers usually match the art directly — the
        # 15-line KFGQPC grid counts header and bismillah lines too. Trust the
        # identity mapping whenever every layout line has ink and the per-line
        # ink-per-QCF-width densities are mutually consistent; the width-rank
        # heuristics below misfire on multi-surah pages whose short centered
        # lines drop below any "text line" width threshold.
        _qb0 = qcf_widths()
        ident = bool(words_by_line) and \
            all(art_widths.get(_ln, 0) > 0 for _ln in words_by_line)
        # a layout line whose ayahs this page's art doesn't draw (QCF page
        # boundaries can drift a few words against this print) breaks identity
        _drift = False
        _QCF_SUSPECT[0] = False
        if page_ayahs:
            _pa = set(page_ayahs)
            _drift = any((w["surah"], w["ayah"]) not in _pa
                         for _wl in words_by_line.values() for w in _wl)
            # ...and the converse: ink drawn here for an ayah whose words the
            # layout list doesn't carry (they wrapped onto a neighbouring QCF
            # page) — those words must come in through the reflow stream
            _la = {(w["surah"], w["ayah"])
                   for _wl in words_by_line.values() for w in _wl}
            if any(k not in _la for k in _pa):
                _drift = True
            if _drift:
                ident = False
                # the cached QCF advances were paired word-by-word per QCF
                # page; on drift pages that pairing is scrambled — distrust
                # implausible advances here (and only here)
                _QCF_SUSPECT[0] = True
        # dk_lines FIXED the word lists, which retired the drift detection
        # above — but the advance TABLE still carries the old scrambled
        # pairing on those pages. The set is derived from data
        # (dk_lines vs qcf_lines, 36 pages) and marks the table suspect
        # whether or not the live word lists still drift.
        _dpf = os.path.join(ROOT, ".cache", "qcf_drift_pages.json")
        if os.path.exists(_dpf) and page_no in json.load(open(_dpf)):
            _QCF_SUSPECT[0] = True
        if ident:
            _rr = []
            for _ln, _wl in words_by_line.items():
                _qs = sum(_qb0.get("%d:%d:%d" % (w["surah"], w["ayah"],
                                                 w["pos"]),
                          2.5 * max(1, letters(w))) for w in _wl)
                _rr.append(art_widths[_ln] / max(1e-9, _qs))
            _md = sorted(_rr)[len(_rr) // 2]
            # every line within a band of the median: a single outlier line
            # (a bismillah paired with real words on a shifted page) breaks
            # identity even when the overall spread looks tame
            ident = all(0.62 * _md <= _v <= 1.6 * _md for _v in _rr)
            # every substantial text line in the ART must be claimed by the
            # layout — an unclaimed full line means the print used one more
            # line than the QCF layout and identity cannot hold (p76)
            if ident:
                _wm = max(art_widths.values())
                ident = all(_ln in words_by_line for _ln, _v in
                            art_widths.items() if _v >= 0.72 * _wm)
        # trigger reflow only when the layout's line count disagrees with the art
        wmax = max(art_widths.values()) if art_widths else 0
        n_text = sum(1 for v in art_widths.values() if v >= 0.72 * wmax)
        reflow_info = {}
        if not ident and page_ayahs \
                and (_drift or len(words_by_line) != n_text):
            stream = ayah_stream(page_no, cache_dir, page_ayahs) or \
                ((prev_tail or [])
                 + [w for j in sorted(words_by_line) for w in words_by_line[j]]
                 + (next_head or []))
            _fh = bool(page_ayahs) and \
                page_ayahs[0] in poly_ayahs(edition, page_no - 1)
            _ft = bool(page_ayahs) and \
                page_ayahs[-1] in poly_ayahs(edition, page_no + 1)

            def _order_repaired(rng):
                # Reading order is strict: once an ayah has ended on a line,
                # it cannot reappear lower down. Where the polygons say ayah A
                # both ends on line N (B starts beside it) AND continues on
                # line N+1 with the very same x-range, one of the two rows is
                # a generator artifact — the alternative is that A owns line N
                # whole. Build that alternative; the ink decides below.
                lns = sorted(rng)
                out = {ln: dict(r) for ln, r in rng.items()}
                changed = False
                for i, ln in enumerate(lns[:-1]):
                    nxt = lns[i + 1]
                    for a in sorted(out.get(ln, {})):
                        if a not in rng.get(nxt, {}):
                            continue
                        if rng[ln][a] != rng[nxt][a]:
                            continue
                        later = [b for b in out[ln] if b > a]
                        if not later:
                            continue
                        lo = min(out[ln][b][0] for b in later)
                        hi = max(out[ln][b][1] for b in later)
                        for b in later:
                            del out[ln][b]
                        out[ln][a] = (min(out[ln][a][0], lo),
                                      max(out[ln][a][1], hi))
                        changed = True
                return out if changed else None

            _alt = _order_repaired(ay_ranges)
            _fl = polygon_reflow(page_ayahs, ay_ranges, stream,
                                 free_head=_fh, free_tail=_ft)
            _fq = polygon_reflow(page_ayahs, ay_ranges, stream, use_qcf=True,
                                 free_head=_fh, free_tail=_ft)
            _fa = _fb = None
            if _alt:
                _ak = sorted({k for r in _alt.values() for k in r})
                _fa = polygon_reflow(_ak, _alt, stream,
                                     free_head=_fh, free_tail=_ft)
                _fb = polygon_reflow(_ak, _alt, stream, use_qcf=True,
                                     free_head=_fh, free_tail=_ft)

            def _flow_dev(fl):
                if not fl:
                    return float("inf")
                t = 0.0
                for _ln, _wl in fl.items():
                    ea = [e for e in elements if e["line"] == _ln]
                    if not ea or not _wl:
                        continue
                    cls, _ = _cl(ea, _wl, ay_ranges.get(_ln), use_dots=False)
                    spans = [(max(a["x2"] for a in cl) - min(a["x1"] for a in cl))
                             if cl else 0.0 for cl in cls]
                    tot = sum(spans)
                    tl = sum(letters(w) for w in _wl) or 1
                    alpha = tot / tl if tot else 1.0
                    t += sum(abs(sp - alpha * letters(w)) / max(alpha, 1e-6)
                             for sp, w in zip(spans, _wl))
                return t
            flowed = None
            _cands = [c for c in (_fl, _fq, _fa, _fb) if c]
            if _cands:
                flowed = min(_cands, key=_flow_dev)
                if _alt and flowed in (_fa, _fb):
                    # the repaired rows won on the ink: adopt them in place so
                    # every later stage sees the same geometry
                    ay_ranges.clear()
                    ay_ranges.update(_alt)
            if flowed:
                words_by_line = flowed
                reflow_info = {"reflowed": True}
        line_map = ({} if (ident or reflow_info)
                    else map_lines(art_widths, words_by_line))
        if os.environ.get("QSVG_DEBUG_MAP"):
            print("MAP ident=%s reflow=%s drift=%s n_text=%d layout=%d map=%s"
                  % (ident, bool(reflow_info), _drift, n_text,
                     len(words_by_line), line_map), file=sys.stderr)


        # The layout's line numbers come from the QCF mushaf, whose breaks
        # can differ from this print by one word (p27: QCF ends line 14 with
        # فإنمآ; KFGQPC starts it on line 15). The ink is the truth: when the
        # per-line ink-per-QCF-width densities of two adjacent lines disagree,
        # trial-cluster both lines with the boundary word moved and keep the
        # move if the actual clustering deviation improves.
        _qb = qcf_widths()
        _rows = []
        for _ln in sorted({e["line"] for e in elements if e["line"]}):
            _wl = words_by_line.get(line_map.get(_ln), []) if line_map else \
                words_by_line.get(_ln, [])
            if _wl and art_widths.get(_ln):
                _rows.append((_ln, _wl))

        def _qsum(_wl):
            if _drift or grounded or reflow_info:
                # drift pages: the raw advance table is scrambled — letters()
                # already distrusts it there
                return sum(letters(_w) for _w in _wl)
            t = 0.0
            for _w in _wl:
                _k = "%d:%d:%d" % (_w["surah"], _w["ayah"], _w["pos"])
                t += _qb.get(_k, 2.5 * max(1, letters(_w)))
            return t

        _thr = 0.08

        def _polyfit(_w, _dst, _dwl):
            # the ayah polygons cap how much of an ayah each line holds: a
            # move is legal only if the destination segment can absorb the
            # word alongside the ayah's words already there
            seg = ay_ranges.get(_dst, {}).get((_w["surah"], _w["ayah"]))
            if not ay_ranges:
                return True
            if seg is None:
                return False
            tot = letters(_w) + sum(letters(x) for x in _dwl
                                    if (x["surah"], x["ayah"])
                                    == (_w["surah"], _w["ayah"]))
            return tot <= 1.45 * (seg[1] - seg[0]) + 6.0

        _dev_cache = {}

        def _piece_pen(_ln, _wl, cls):
            # how badly the split had to violate the words' own ligature counts
            pen = 0.0
            for _w8, cl8 in zip(_wl, cls):
                bods8 = [e for a8 in cl8 for e in a8["els"]
                         if e["kind"] == "body"]
                eff8 = []
                for b8 in bods8:
                    wb8 = b8["x2"] - b8["x1"]
                    hb8 = b8["y2"] - b8["y1"]
                    if not any(o8 is not b8
                               and min(o8["x2"], b8["x2"]) - max(o8["x1"], b8["x1"])
                               >= 0.6 * wb8
                               and (o8["x2"] - o8["x1"]) > wb8
                               and hb8 <= (o8["y2"] - o8["y1"]) + 1.0
                               for o8 in bods8):
                        eff8.append(b8)
                ns8 = max(1, len(segment_word(_w8["uthmani"])))
                if len(eff8) > ns8:        # holding ink its text cannot own
                    pen += 0.5 * (len(eff8) - ns8)
            return pen

        def _dev1(_ln, _wl):
            key = (_ln, tuple(id(w) for w in _wl))
            if key not in _dev_cache:
                ea = [e for e in elements if e["line"] == _ln]
                if _wl and ea:
                    cls8, dev8 = _cl(ea, list(_wl), ay_ranges.get(_ln),
                                     use_dots=False)
                    _dev_cache[key] = dev8 + _piece_pen(_ln, list(_wl), cls8)
                else:
                    _dev_cache[key] = 0.0
            return _dev_cache[key]

        def _devpair(_lna, _wla, _lnb, _wlb):
            return _dev1(_lna, _wla) + _dev1(_lnb, _wlb)

        for _pass in range(3):
            _shifted = False
            for _i in range(len(_rows) - 1):
                _lnr, _wr = _rows[_i]
                _lnl, _wll = _rows[_i + 1]
                if not _wr or not _wll:
                    continue
                sr = art_widths[_lnr] / max(1e-9, _qsum(_wr))
                sl = art_widths[_lnl] / max(1e-9, _qsum(_wll))
                if abs(math.log(max(sr, 1e-6) / max(sl, 1e-6))) < 0.06:
                    continue
                d0 = _devpair(_lnr, _wr, _lnl, _wll)
                # a letter-space compound at a line edge is the one word whose
                # width prior cannot be trusted across a boundary: the print
                # draws it as two chunks (p254 بَعْدَ مَا straddles the very
                # gap the density test reads as crowding) — never move it
                _ssp = os.environ.get("QSVG_SPACESPLIT", "1") == "1"
                if sr < sl and len(_wr) > 1 \
                        and not (_ssp and _space_halves(_wr[-1])) \
                        and _polyfit(_wr[-1], _lnl, _wll):  # upper crowded
                    d1 = _devpair(_lnr, _wr[:-1], _lnl, [_wr[-1]] + _wll)
                    if d1 < d0 - _thr:
                        if os.environ.get("QSVG_LDBG"):
                            _wm9 = _wr[-1]
                            print("LDBG hillclimb %d:%d:%d line %s -> %s (d0=%.2f d1=%.2f)"
                                  % (_wm9["surah"], _wm9["ayah"], _wm9["pos"],
                                     _lnr, _lnl, d0, d1), file=sys.stderr)
                        _wll.insert(0, _wr.pop())
                        _shifted = True
                elif sr > sl and len(_wll) > 1 \
                        and not (_ssp and _space_halves(_wll[0])) \
                        and _polyfit(_wll[0], _lnr, _wr):   # lower crowded
                    d1 = _devpair(_lnr, _wr + [_wll[0]], _lnl, _wll[1:])
                    if d1 < d0 - _thr:
                        if os.environ.get("QSVG_LDBG"):
                            _wm9 = _wll[0]
                            print("LDBG hillclimb %d:%d:%d line %s -> %s (d0=%.2f d1=%.2f)"
                                  % (_wm9["surah"], _wm9["ayah"], _wm9["pos"],
                                     _lnl, _lnr, d0, d1), file=sys.stderr)
                        _wr.append(_wll.pop(0))
                        _shifted = True
            if not _shifted:
                break

        for ln in sorted({e["line"] for e in elements if e["line"]}):
            els = [e for e in elements if e["line"] == ln]
            words = words_by_line.get(line_map.get(ln), []) if line_map else \
                words_by_line.get(ln, [])
            clusters, deviation = _cl(els, words, ay_ranges.get(ln))
            # Repair pass: an overflowing last word is drawn small and raised, so its ink
            # was classified as marks and its cluster came out far too narrow. Reclaim
            # word-sized mark elements from the starved word's expected region as bodies
            # and recluster the line once.
            if words and clusters:
                span_line = (max(a["x2"] for cl in clusters for a in cl if cl)
                             - min(a["x1"] for cl in clusters for a in cl if cl))
                alpha_l = span_line / sum(letters(w) for w in words)
                reclaimed = False
                for k, (w, cl) in enumerate(zip(words, clusters)):
                    if not cl:
                        continue
                    ratio = (cl[0]["x2"] - cl[-1]["x1"]) / max(1e-9, alpha_l * letters(w))
                    if ratio >= 0.4:
                        continue
                    lo = (clusters[k + 1][0]["x2"] - 2 if k + 1 < len(clusters)
                          and clusters[k + 1] else -1e9)
                    hi = (clusters[k - 1][-1]["x1"] + 2 if k > 0
                          and clusters[k - 1] else 1e9)
                    for e in els:
                        if (e["kind"] == "mark" and not e.get("mkpart")
                                and (e["x2"] - e["x1"]) >= 3.5
                                and e.get("lab") not in
                                ("fatha", "kasra", "fathatan", "kasratan",
                                 "damma", "dammatan")
                                and lo <= (e["x1"] + e["x2"]) / 2 <= hi):
                            for x in [e] + e.get("mkmembers", []):
                                x["kind"] = "body"
                                x.pop("mkpart", None)
                            e.pop("mkmembers", None)
                            reclaimed = True
                if reclaimed:
                    clusters, deviation = _cl(els, words, ay_ranges.get(ln))

            # Layout-vs-geometry mismatch retry: when a word's span is far off what its
            # letters predict, the line's width calibration is suspect — re-solve under
            # alternative calibrations and keep the solution with the fewest violations.
            def violations(cls):
                if not words or not cls:
                    return 99, 0.0
                span_l = (max(a["x2"] for cl in cls for a in cl if cl)
                          - min(a["x1"] for cl in cls for a in cl if cl))
                al = span_l / sum(letters(w) for w in words)
                v = 0
                worst = 0.0
                for w, cl in zip(words, cls):
                    if not cl:
                        v += 2
                        continue
                    r = (cl[0]["x2"] - cl[-1]["x1"]) / max(1e-9, al * letters(w))
                    if r < 0.4 or (r > 2.4 and len(cl) > len(segment_word(w["uthmani"]))):
                        v += 1
                    worst = max(worst, abs(r - 1))
                return v, worst

            if words:
                v0, w0 = violations(clusters)
                if v0:
                    best = (v0, w0, clusters, deviation)
                    for sc in (0.9, 1.1, 0.8, 1.2):
                        cl2, dev2 = _cl(els, words, ay_ranges.get(ln), sc)
                        v2, w2 = violations(cl2)
                        if (v2, w2) < (best[0], best[1]):
                            best = (v2, w2, cl2, dev2)
                    clusters, deviation = best[2], best[3]
            flags = []
            if not words:
                flags.append("no-words-for-line")       # surah header / bismillah art
            if len(clusters) != len(words) and words:
                flags.append("count-mismatch:%d-clusters" % len(clusters))
            # completeness: every word must own a sensible share of the line's ink
            if words and clusters:
                span_line = (max(a["x2"] for cl in clusters for a in cl)
                             - min(a["x1"] for cl in clusters for a in cl))
                alpha_l = span_line / sum(letters(w) for w in words)
            for w, cl in zip(words, clusters):
                if not cl:
                    flags.append("word-missing:%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]))
                    continue
                if not any(e["kind"] == "body" for a in cl for e in a["els"]):
                    flags.append("marks-only-word:%d" % w["pos"])
                ratio = (cl[0]["x2"] - cl[-1]["x1"]) / max(1e-9, alpha_l * letters(w))
                # Oversize alone is legal — a line-end word can carry a huge kashida —
                # unless the word also holds more pieces than its letters justify.
                over = ratio > 2.4 and len(cl) > len(segment_word(w["uthmani"]))
                if ratio < 0.4 or over:
                    flags.append("word-size:%d:%d:%d(x%.1f)"
                                 % (w["surah"], w["ayah"], w["pos"], ratio))
                pr = (ay_ranges.get(ln) or {}).get((w["surah"], w["ayah"])) \
                    if ay_ranges else None
                if pr:
                    n_out = sum(1 for a in cl if not (
                        pr[0] - 1.5 <= (a["x1"] + a["x2"]) / 2 <= pr[1] + 1.5))
                    if n_out:
                        flags.append("polygon:%d:%d:%d(%d out)"
                                     % (w["surah"], w["ayah"], w["pos"], n_out))
                # A word taller than ~1.5 line bands holds ink from another
                # line: always a defect, never calligraphy.
                els_cl = [e for a in cl for e in a["els"]]
                hh = (max(e["y2"] for e in els_cl) - min(e["y1"] for e in els_cl))
                band = None
                for _li in lines_info:
                    if _li["lineNumber"] == ln:
                        band = (_li.get("height")
                                or (_li["bottom"] - _li["top"]))
                if band and hh > 1.55 * band:
                    flags.append("word-height:%d:%d:%d(x%.1f)"
                                 % (w["surah"], w["ayah"], w["pos"], hh / band))
                segs = segment_word(w["uthmani"])
                groups, cost = align_segs_atoms(cl, segs)
                if cost > 0.6:
                    flags.append("ligatures:%d(cost=%.1f)" % (w["pos"], cost))
                for gi, (g_atoms, g_segs) in enumerate(groups):
                    if not g_atoms:
                        continue
                    merged = {"text": "".join(s["text"] for s in g_segs),
                              "marks": [mk for s in g_segs for mk in s["marks"]],
                              "bad": any(s["bad"] for s in g_segs)}
                    for atom in g_atoms:
                        atom["seg"] = merged
                        atom["lig"] = gi
                    if not label_marks(g_atoms, merged["marks"],
                                       baselines.get(ln)) or merged["bad"]:
                        flags.append("marks:%d" % w["pos"])
                assignment.append((w, cl))
            # clusters[len(words):] is ALL clusters when words is empty, so the
            # old extra `if not words` loop emitted every header/bismillah
            # cluster twice (p604's stacked-basmalah halo).
            for cl in clusters[len(words):]:
                assignment.append((None, cl))
            hard = [f for f in flags if not f.startswith("marks:")]
            if reflow_info:
                hard = hard + ["page-reflowed"] if ln == min(
                    {e["line"] for e in elements if e["line"]}) else hard
            report.append({"line": ln, "words": len(words), "clusters": len(clusters),
                           "deviation": None if deviation == float("inf")
                           else round(deviation, 2),
                           "flags": hard,
                           "marks_unmatched": len(flags) - len(hard),
                           "review": bool(hard) or deviation == float("inf")
                           or deviation > 0.55})
        nviol = sum(1 for r in report for f in r.get("flags", [])
                    if f.startswith(("word-size", "word-missing")))
        return assignment, report, nviol

    def _anom_count(a):
        # number of words failing width or budget checks — the audit's view
        n = 0
        rows = {}
        for w2, at2 in a:
            if not w2:
                continue
            els2 = [e for a3 in at2 for e in a3["els"]]
            if els2:
                rows.setdefault(els2[0].get("line"), []).append((w2, els2))
        for ln2, sub in rows.items():
            tq = sum(letters(w2) for w2, _ in sub) or 1.0
            ta = sum(max(e["x2"] for e in els2) - min(e["x1"] for e in els2)
                     for _, els2 in sub)
            for w2, els2 in sub:
                sp = max(e["x2"] for e in els2) - min(e["x1"] for e in els2)
                rr = sp / (letters(w2) / tq * ta) if ta else 1.0
                bad = rr < 0.6 or rr > 1.6
                c3 = w2["uthmani"].count
                hv = sum(1 for e in els2 if e.get("mark") in
                         ("fatha", "kasra", "fathatan", "kasratan")
                         and not e.get("mkpart"))
                wv = (c3("\u064e") + c3("\u0650") + c3("\u064b")
                      + c3("\u064d") + c3("\u08f0") + c3("\u08f2"))
                hd = sum(1 for e in els2 if e.get("mark") in
                         ("damma", "dammatan") and not e.get("mkpart"))
                wd = c3("\u064f") + c3("\u064c") + c3("\u08f1")
                if bad or hv != wv or hd != wd:
                    n += 1
        return n

    def _anom_lines(a, width_only=False):
        # lines holding a word whose assigned span disagrees badly
        # with its QCF share — the tell of a one-word break miss
        rows = {}
        for w2, at2 in a:
            if not w2:
                continue
            els2 = [e for a3 in at2 for e in a3["els"]]
            if els2:
                rows.setdefault(els2[0].get("line"), []).append(
                    (w2, els2))
        bad = set()
        for ln2, sub in rows.items():
            tq = sum(letters(w2) for w2, _ in sub) or 1.0
            ta = sum(max(e["x2"] for e in els2)
                     - min(e["x1"] for e in els2)
                     for _, els2 in sub)
            for w2, els2 in sub:
                sp = (max(e["x2"] for e in els2)
                      - min(e["x1"] for e in els2))
                rr = sp / (letters(w2) / tq * ta) if ta else 1.0
                if rr < 0.6 or rr > 1.6:
                    bad.add(ln2)
                if width_only:
                    continue
                c3 = w2["uthmani"].count
                hv = sum(1 for e in els2 if e.get("mark") in
                         ("fatha", "kasra", "fathatan", "kasratan")
                         and not e.get("mkpart"))
                wv = (c3("\u064e") + c3("\u0650") + c3("\u064b")
                      + c3("\u064d") + c3("\u08f0") + c3("\u08f2"))
                hd = sum(1 for e in els2 if e.get("mark") in
                         ("damma", "dammatan") and not e.get("mkpart"))
                wd = c3("\u064f") + c3("\u064c") + c3("\u08f1")
                if hv != wv or hd != wd:
                    bad.add(ln2)
        return bad

    def _overcap_end(a, ln):
        # slash marks beyond the text budget on a line's LAST word: the tell
        # that the next line's first word was really drawn at this line's end
        rows = {}
        for w2, at2 in a:
            if not w2:
                continue
            els2 = [e for a3 in at2 for e in a3["els"]]
            if els2:
                rows.setdefault(els2[0].get("line"), []).append((w2, els2))
        sub = rows.get(ln)
        if not sub:
            return 0
        w2, els2 = min(sub, key=lambda t: min(e["x1"] for e in t[1]))
        c3 = w2["uthmani"].count
        hv = sum(1 for e in els2 if e.get("mark") in
                 ("fatha", "kasra", "fathatan", "kasratan")
                 and not e.get("mkpart"))
        wv = (c3("\u064e") + c3("\u0650") + c3("\u064b")
              + c3("\u064d") + c3("\u08f0") + c3("\u08f2"))
        return max(0, hv - wv)

    def _hillclimb(wbl, a2, r2, v2, d2, mode="conflict"):
        # single-word boundary hill-climb, truth-scored by run_pass: any
        # per-line word list can miss a break by one word; try shifting one
        # word across each anomalous boundary and keep real improvements
        n2 = _anom_count(a2)
        for _ in range(8):
            anoms = _anom_lines(a2, width_only=(mode == "width"))
            if not anoms:
                break
            lns3 = sorted(ln3 for ln3 in wbl if wbl[ln3])
            bestmv = None
            for i3 in range(len(lns3) - 1):
                La, Lb = lns3[i3], lns3[i3 + 1]
                if La not in anoms and Lb not in anoms:
                    continue
                for dirn3 in (0, 1):
                    src = La if dirn3 == 0 else Lb
                    if len(wbl[src]) < 2:
                        continue
                    if dirn3 == 0:
                        if not _ayah_allowed(wbl[La][-1], Lb):
                            continue
                    elif not _ayah_allowed(wbl[Lb][0], La):
                        continue
                    trial = {ln3: list(ws3)
                             for ln3, ws3 in wbl.items()}
                    if dirn3 == 0:
                        trial[Lb].insert(0, trial[La].pop())
                    else:
                        trial[La].append(trial[Lb].pop(0))
                    a4, r4, v4 = run_pass(trial)
                    d4 = sum((r.get("deviation") or 3.0)
                             for r in r4)
                    n4 = _anom_count(a4)
                    if dirn3 == 1 and _overcap_end(a2, La) >= 2:
                        n4 -= 3     # strong boundary-orphan signal
                    if mode == "width":
                        ok4 = v4 <= v2 and (n4 < n2 or
                                            (n4 == n2 and d4 < d2 - 0.05))
                    else:
                        ok4 = (v4 < v2 or (v4 == v2 and d4 < d2 - 0.05)
                               or (v4 == v2 and n4 <= n2 - 2
                                   and d4 < d2 + 0.5))
                    if ok4 and (bestmv is None
                                or (v4, n4, d4) < bestmv[0]):
                        bestmv = ((v4, n4, d4), trial, a4, r4)
            if bestmv is None:
                break
            (v2, n2, d2), wbl, a2, r2 = bestmv
        return wbl, a2, r2, v2, d2

    assignment, report, nviol = run_pass(words_by_line)
    # The art's line breaks can drift from the public layout even mid-page; the
    # ayah polygons are the art's own truth. Dense violations => re-derive the
    # per-line word lists from the polygons and keep the better assignment.
    layout_conflicts = _count_conflicts(words_by_line) if ay_ranges else 0
    if (nviol >= 3 or layout_conflicts) and os.path.exists(polys_path):
        seen = []
        for p in json.load(open(polys_path)):
            k = (p["surahNumber"], p["ayahNumber"])
            if k not in seen:
                seen.append(k)
        try:
            pw = page_words(page_no - 1, cache_dir) if page_no > 1 else {}
            prev_tail = sorted((w for j in pw for w in pw[j]),
                               key=lambda w: (w["surah"], w["ayah"],
                                              w["pos"]))[-25:]
            nw = page_words(page_no + 1, cache_dir) if page_no < 604 else {}
            next_head = sorted((w for j in nw for w in nw[j]),
                               key=lambda w: (w["surah"], w["ayah"],
                                              w["pos"]))[:25]
        except Exception:
            prev_tail, next_head = [], []
        stream = ayah_stream(page_no, cache_dir, sorted(seen)) or \
            (prev_tail + [w for j in sorted(words_by_line)
                          for w in words_by_line[j]] + next_head)
        _sk = sorted(seen)
        flowed = polygon_reflow(
            _sk, ay_ranges, stream,
            free_head=bool(_sk) and _sk[0] in poly_ayahs(edition, page_no - 1),
            free_tail=bool(_sk) and _sk[-1] in poly_ayahs(edition, page_no + 1))
        if flowed:
            if layout_conflicts >= 3:
                _ink_refine(flowed)
            a2, r2, v2 = run_pass(flowed, grounded=True)
            d1 = sum((r.get("deviation") or 3.0) for r in report)
            d2 = sum((r.get("deviation") or 3.0) for r in r2)

            if layout_conflicts >= 3 and v2 <= nviol:
                flowed, a2, r2, v2, d2 = _hillclimb(flowed, a2, r2, v2, d2)


            c2 = _count_conflicts(flowed)
            if v2 < nviol or (layout_conflicts and v2 <= nviol
                              and (d2 < d1 or c2 < layout_conflicts)):
                for r in r2:
                    r.setdefault("flags", []).append("line-reflowed") if r is r2[0] else None
                assignment, report, nviol = a2, r2, v2

    if _anom_lines(assignment, width_only=True):
        # a crushed or bloated word without polygon disagreement still marks a
        # missed break (a crowded line): hill-climb the current lists
        cur_wbl = {}
        for w4, at4 in assignment:
            if not w4:
                continue
            els4 = [e for a4 in at4 for e in a4["els"]]
            if els4:
                cur_wbl.setdefault(els4[0].get("line"), []).append(w4)
        d0 = sum((r.get("deviation") or 3.0) for r in report)
        _, a5, r5, v5, d5 = _hillclimb(cur_wbl, assignment, report, nviol, d0,
                                       mode="width")
        assignment, report, nviol = a5, r5, v5

    assignment = assignment + [(None, [{"els": [e]}]) for e in offcanvas]
    labeled, total_marks = apply_shape_labels(page, assignment, baselines)

    # ------------------------------------------------------------------
    # Global mark reconciliation. The text of each word fixes exactly how
    # many marks of each family it carries; geometry alone keeps mis-homing
    # marks that hang in the gap between lines or over a neighbour's edge.
    # Assign every identity-strong mark to the best word that still has
    # capacity for it, considering words on the mark's own line and the two
    # neighbouring lines within an x-window. One mechanism instead of a
    # rule per failure mode.
    # ------------------------------------------------------------------
    _FAM = {"fatha": "slash", "kasra": "slash", "damma": "damma",
            "fathatan": "slash", "kasratan": "slash", "dammatan": "damma",
            "sukun": "sukun", "hamza": "hamza", "wasla": "wasla",
            "small-alef": "small-alef", "maddah": "maddah",
            "shadda": "shadda", "small-circle": "small-circle",
            "meem-iqlab": "meem-iqlab", "pause": "pause",
            "small-waw": "small-waw", "small-ya": "small-ya"}
    # small-waw/small-ya are SUBSCRIPT letters (ride at or below baseline)
    _ABOVE_FAM = {"damma", "sukun", "wasla", "small-alef", "maddah", "shadda",
                  "small-circle", "meem-iqlab", "pause"}

    def _cap(txt, fam):
        c = txt.count
        if fam == "slash":
            # tanween fathatan/kasratan are drawn as stroke PAIRS in this art
            return (c("\u064e") + c("\u0650")
                    + c("\u064b") + c("\u064d")
                    + c("\u08f0") + c("\u08f2"))
        if fam == "damma":
            return c("\u064f") + c("\u064c") + c("\u08f1")
        if fam == "sukun":
            return c("\u0652") + c("\u06e1")
        if fam == "hamza":
            # bare \u0621 is a LETTER body in this art, not a mark
            return (sum(c(x) for x in "\u0623\u0625\u0624\u0626")
                    + c("\u0654") + c("\u0655"))
        if fam == "wasla":
            return c("\u0671")
        if fam == "small-alef":
            return c("\u0670")
        if fam == "maddah":
            return c("\u0653") + c("\u06e4")
        if fam == "shadda":
            return c("\u0651")
        if fam == "small-circle":
            return c("\u06df") + c("\u06e0")
        if fam == "meem-iqlab":
            return c("\u06e2") + c("\u06ed")
        if fam == "pause":
            return sum(c(x) for x in "\u06d6\u06d7\u06d8\u06d9\u06da\u06db\u06dc")
        if fam == "small-waw":
            return c("\u06e5")
        if fam == "small-ya":
            return c("\u06e6") + c("\u06e7")
        return 0

    wrec = []
    for w, at in assignment:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        if not bods:
            continue
        wrec.append({
            "w": w, "at": at, "els": els,
            "line": bods[0].get("line"),
            "x1": min(e["x1"] for e in bods), "x2": max(e["x2"] for e in bods),
            "top": min(e["y1"] for e in bods), "bot": max(e["y2"] for e in bods),
        })

    fams = {}
    for r in wrec:
        for e in r["els"]:
            fam = _FAM.get(e.get("mark"))
            if not fam or e.get("mkpart") or e.get("mkmembers"):
                continue
            fams.setdefault(fam, []).append((e, r))

    for fam, marks in fams.items():
        caps = {id(r): _cap(r["w"]["uthmani"], fam) for r in wrec}
        pairs = []
        for e, home in marks:
            cx = (e["x1"] + e["x2"]) / 2
            cy = (e["y1"] + e["y2"]) / 2
            for r in wrec:
                if r["line"] is None or home["line"] is None:
                    continue
                if abs(r["line"] - home["line"]) > 1:
                    continue
                rare = fam in ("pause", "small-ya", "small-waw",
                               "meem-iqlab", "wasla", "maddah")
                win = 6.0 if rare else 3.0
                if not (r["x1"] - win < cx < r["x2"] + win):
                    continue
                if fam == "slash" and r is not home \
                        and r["line"] != home["line"]:
                    continue    # slashes cross lines only via strict
                                # surplus->deficit capacity repair
                if fam in _ABOVE_FAM and cy > r["bot"]:
                    continue                        # above-marks never sit below
                vz = (abs(cy - r["top"]) if fam in _ABOVE_FAM
                      else min(abs(cy - r["top"]), abs(cy - r["bot"])))
                if r is home:
                    pen = 0.0
                elif r["line"] == home["line"]:
                    pen = 1.5             # neighbour word, same line: cheap
                else:
                    # rare identity-certain families follow the text anywhere
                    pen = 2.0 if rare else 6.0
                cost = vz + pen
                pairs.append((cost, id(e), e, home, r))
        pairs.sort(key=lambda t: t[0])
        placed = set()
        # two rounds: honour capacities first; a mark nobody had room for then
        # goes to its cheapest candidate that STILL has capacity (its home word
        # is over budget by construction, so staying put is the worst choice)
        for _round in (0, 1):
            for cost, eid_, e, home, r in pairs:
                if eid_ in placed or caps.get(id(r), 0) <= 0:
                    continue
                placed.add(eid_)
                caps[id(r)] -= 1
                if r is home:
                    continue
                for a in home["at"]:                # move the element across
                    if e in a["els"]:
                        a["els"].remove(e)
                        break
                home["els"].remove(e)
                tgt = min(r["at"], key=lambda a2: min(abs((x["x1"] + x["x2"]) / 2
                          - (e["x1"] + e["x2"]) / 2) for x in a2["els"])
                          if a2["els"] else 1e9)
                tgt["els"].append(e)
                r["els"].append(e)

    # Capacity repair: greedy order can keep a neighbour's stray and bump the
    # word's own mark instead (equal counts, wrong members). While a word holds
    # more of a family than its text allows and a candidate within reach has
    # room, hand over the member whose relocation costs least.
    _labs_by_fam = {}
    for _lab, _f in _FAM.items():
        _labs_by_fam.setdefault(_f, []).append(_lab)
    for fam in fams:
        labs = tuple(_labs_by_fam.get(fam, ()))
        for _ in range(3):
            moved = False
            for r in wrec:
                capr = _cap(r["w"]["uthmani"], fam)
                mine = [e for e in r["els"] if e.get("mark") in labs
                        and not e.get("mkpart") and not e.get("mkmembers")]
                if len(mine) <= capr:
                    continue
                best = None
                for e in mine:
                    cx = (e["x1"] + e["x2"]) / 2
                    cy = (e["y1"] + e["y2"]) / 2
                    for r2 in wrec:
                        if r2 is r or r2["line"] is None or r["line"] is None:
                            continue
                        if abs(r2["line"] - r["line"]) > 1:
                            continue
                        if not (r2["x1"] - 12.0 < cx < r2["x2"] + 12.0):
                            continue
                        if fam in _ABOVE_FAM and cy > r2["bot"]:
                            continue
                        n2 = sum(1 for x in r2["els"] if x.get("mark") in labs
                                 and not x.get("mkpart"))
                        if n2 >= _cap(r2["w"]["uthmani"], fam):
                            continue
                        vz = (abs(cy - r2["top"]) if fam in _ABOVE_FAM
                              else min(abs(cy - r2["top"]), abs(cy - r2["bot"])))
                        vz += 0.0 if r2["line"] == r["line"] else 3.0
                        if best is None or vz < best[0]:
                            best = (vz, e, r2)
                if best and best[0] < 12.0:
                    _, e, r2 = best
                    for a in r["at"]:
                        if e in a["els"]:
                            a["els"].remove(e)
                            break
                    r["els"].remove(e)
                    tgt = min(r2["at"], key=lambda a2: min(abs((x["x1"] + x["x2"]) / 2
                              - (e["x1"] + e["x2"]) / 2) for x in a2["els"])
                              if a2["els"] else 1e9)
                    tgt["els"].append(e)
                    r2["els"].append(e)
                    moved = True
            if not moved:
                break

    # a tanween's two strokes (and a dammatan's two curls) present as ONE
    # mark: the top piece is the master, its twin becomes a part. The text
    # says how many tanweens the word carries — pairs of plain damma/fatha/
    # kasra beyond the word's singles budget ARE its tanweens.
    for r in wrec:
        txt = r["w"]["uthmani"]
        for single, tan, chars_s, chars_t in (
                ("damma", "dammatan", "\u064f", "\u064c\u08f1"),):
            want_t = sum(txt.count(ch) for ch in chars_t)
            if not want_t:
                continue
            singles = [e for e in r["els"] if e.get("mark") == single
                       and not e.get("mkpart")]
            want_s = sum(txt.count(ch) for ch in chars_s)
            spare = len(singles) - want_s
            while spare >= 2 and want_t > 0:
                best = None
                for i, a in enumerate(singles):
                    for b in singles[i + 1:]:
                        dx = abs((a["x1"] + a["x2"]) / 2 - (b["x1"] + b["x2"]) / 2)
                        dy = abs((a["y1"] + a["y2"]) / 2 - (b["y1"] + b["y2"]) / 2)
                        if dx < 8.0 and dy < 7.0 and (best is None
                                                      or dx + dy < best[0]):
                            best = (dx + dy, a, b)
                if not best:
                    break
                _, a, b = best
                a["mark"] = b["mark"] = tan
                singles.remove(a)
                singles.remove(b)
                spare -= 2
                want_t -= 1
        # fathatan/kasratan: the table labels every slash "fatha" or "kasra"
        # regardless of position, so pool BOTH kinds; the pair's position
        # against the body midline says which tanween it is
        want_ft = txt.count("\u064b") + txt.count("\u08f0")
        want_kt = txt.count("\u064d") + txt.count("\u08f2")
        if want_ft or want_kt:
            pool = [e for e in r["els"] if e.get("mark") in ("fatha", "kasra")
                    and not e.get("mkpart") and not e.get("mkmembers")]
            spare = (len(pool) - txt.count("\u064e") - txt.count("\u0650"))
            mid = (r["top"] + r["bot"]) / 2
            while (spare >= 2 or want_ft or want_kt) and (want_ft or want_kt):
                best = None
                for i, a in enumerate(pool):
                    for b in pool[i + 1:]:
                        dx = abs((a["x1"] + a["x2"]) / 2
                                 - (b["x1"] + b["x2"]) / 2)
                        dy = abs((a["y1"] + a["y2"]) / 2
                                 - (b["y1"] + b["y2"]) / 2)
                        if dx < 8.0 and dy < 7.0 and (best is None
                                                      or dx + dy < best[0]):
                            best = (dx + dy, a, b)
                if not best:
                    break
                _, a, b = best
                if spare < 2:
                    # the plain budget is short (a vowel of this word is still
                    # missing), so only unmistakable stacking proves a tanween
                    dxb = abs((a["x1"] + a["x2"]) / 2 - (b["x1"] + b["x2"]) / 2)
                    dyb = abs((a["y1"] + a["y2"]) / 2 - (b["y1"] + b["y2"]) / 2)
                    if not (dxb < 4.5 and dyb < 5.0):
                        break
                pcy = (a["y1"] + a["y2"] + b["y1"] + b["y2"]) / 4
                if want_kt and (not want_ft or pcy > mid):
                    tan = "kasratan"
                    want_kt -= 1
                else:
                    tan = "fathatan"
                    want_ft -= 1
                a["mark"] = b["mark"] = tan
                pool.remove(a)
                pool.remove(b)
                spare -= 2
        for lab in ("fathatan", "kasratan", "dammatan"):
            grp = [e for e in r["els"] if e.get("mark") == lab
                   and not e.get("mkpart")]
            grp.sort(key=lambda e: (e["y1"] + e["y2"]))
            i = 0
            while i + 1 < len(grp):
                master, part = grp[i], grp[i + 1]
                dx = abs((master["x1"] + master["x2"]) / 2
                         - (part["x1"] + part["x2"]) / 2)
                dy = abs((master["y1"] + master["y2"]) / 2
                         - (part["y1"] + part["y2"]) / 2)
                if dx < 8.0 and dy < 7.0:
                    part["mkpart"] = True
                    master.setdefault("mkmembers", []).append(part)
                    i += 2
                else:
                    i += 1

    # muanaqah (\u06db): drawn as a floating dot-trio well above the word; its
    # ink matches letter-dot shapes, so only the text can name it
    for r in wrec:
        n_mu = r["w"]["uthmani"].count("\u06db")
        if not n_mu:
            continue
        cands = [e for e in r["els"]
                 if e.get("mark") in ("dot", "two-dots", "three-dots")
                 and not e.get("mkpart")
                 and (e["y1"] + e["y2"]) / 2 < r["top"] - 2.0]
        # The sign is ONE stop drawn as a tight triangle of dots, and a word
        # can have a real letter dot floating up there too — the fa of فِيهِ.
        # Renaming every candidate turns one sign into three stops and eats
        # the letter's dot as well, so group the ink first and spend exactly
        # the number of signs the text asks for, highest cluster first.
        cands.sort(key=lambda e: (e["y1"] + e["y2"]) / 2)
        groups = []
        for e in cands:
            cx = (e["x1"] + e["x2"]) / 2
            cy = (e["y1"] + e["y2"]) / 2
            for g in groups:
                if any(abs(cx - (o["x1"] + o["x2"]) / 2) <= 6.0
                       and abs(cy - (o["y1"] + o["y2"]) / 2) <= 6.0
                       for o in g):
                    g.append(e)
                    break
            else:
                groups.append([e])
        for g in groups[:n_mu]:
            g.sort(key=lambda e: -e["x1"])
            g[0]["mark"] = "pause"
            for x in g[1:]:
                x["mkpart"] = True    # welded twins count through their master

    # Every waqf sign floats above the line, clear of the letters. Most of
    # them are ligatures of real letters — قلى, صلى, the lone م — so the
    # classifier reads their ink as a letter and the word ends up one piece
    # heavy and one pause short, with the qaf's two dots counted as letter
    # dots on top of that. Nothing in the ink says "this is a stop"; only the
    # text does. So take the COUNT from the text and the POSITION from the
    # ink: pieces standing clear above the word's own letters.
    # The stop signs only. U+06DD ends an ayah and U+06DE (۞) marks a rub
    # el hizb: both are ornaments, not stops, and turning them into pause
    # marks invents a stop the text never asked for.
    _WAQF = "\u06d6\u06d7\u06d8\u06d9\u06da\u06dc"
    for r in wrec:
        want = sum(r["w"]["uthmani"].count(c) for c in _WAQF)
        if not want:
            continue
        have = sum(1 for e in r["els"]
                   if e.get("mark") == "pause" and not e.get("mkpart"))
        if have >= want:
            continue
        bods = [e for e in r["els"] if e["kind"] == "body"]
        if len(bods) < 2:
            continue
        # the letters' own band, taken from the median letter so one floating
        # piece cannot drag the reference up to meet itself
        mids = sorted((e["y1"] + e["y2"]) / 2 for e in bods)
        band = mids[len(mids) // 2]
        float_up = [e for e in bods if e["y2"] < band - 2.0]
        float_up.sort(key=lambda e: e["y2"])
        for e in float_up[:want - have]:
            e["kind"] = "mark"
            e["mark"] = "pause"
            e["lab"] = "pause"
            # the dots of the ligature ride with it and are not letter dots
            for d in r["els"]:
                if d is e or d.get("mkpart") or d["kind"] != "mark":
                    continue
                if d.get("mark") not in ("dot", "two-dots", "three-dots"):
                    continue
                if (d["x1"] >= e["x1"] - 1.5 and d["x2"] <= e["x2"] + 1.5
                        and (d["y1"] + d["y2"]) / 2 < band - 2.0):
                    d["mkpart"] = True

    # A superscript letter — the iqlab meem ۢ, the small waw ۥ and small ya ۦ
    # of the pronoun suffixes — is a real letter shape drawn small and clear
    # of the line. Its ink looks exactly like a letter to the classifier, so
    # the word ends up one piece heavy and one mark short, and the surplus
    # reads as stolen ink from a neighbour. Nothing in the ink says
    # "superscript"; the spelling does. So take the COUNT from the text and
    # the POSITION from the ink: a piece whose foot stands well above the
    # word's own baseline is not standing on the line, and no letter does that.
    _SUP = ({} if os.environ.get("QSVG_SUP") == "0" else
            {"\u06e2": "meem-iqlab", "\u06e5": "small-waw",
             "\u06e6": "small-ya"})
    for r in wrec:
        for ch, name in _SUP.items():
            want = r["w"]["uthmani"].count(ch)
            if not want:
                continue
            have = sum(1 for e in r["els"]
                       if e.get("mark") == name and not e.get("mkpart"))
            if have >= want:
                continue
            bods = [e for e in r["els"] if e["kind"] == "body"]
            if len(bods) < 2:
                continue
            base = max(e["y2"] for e in bods)
            hgt = max(base - min(e["y1"] for e in bods), 1e-6)
            big = max(bods, key=lambda e: ((e["x2"] - e["x1"])
                                           * (e["y2"] - e["y1"])))
            big_a = max((big["x2"] - big["x1"]) * (big["y2"] - big["y1"]), 1e-6)
            # A letter belonging to the NEXT word can be small and lifted
            # too, and calling it a mark is worse than leaving it: the word
            # stops counting as a piece heavy, so the surplus that would have
            # exposed the theft disappears and the audit falls silent. A
            # stolen letter gives itself away by the company it keeps — the
            # dot and the vowel of the word it really belongs to stand on it.
            # Taken from the assignment, not from wrec: a word that has been
            # stripped of every letter never enters wrec, and that is exactly
            # the word whose letter has gone missing — the one whose marks are
            # the evidence.
            _foreign = [e2 for w2, at2 in assignment if w2 is not r["w"]
                        for a2 in at2 for e2 in a2["els"]
                        if e2["kind"] == "mark" and not e2.get("mkpart")
                        and e2.get("line") == r["line"]]

            def _owned_by_other(e0):
                for o in _foreign:
                    if min(o["x2"], e0["x2"]) - max(o["x1"], e0["x1"]) <= 0.5:
                        continue
                    if 0.0 <= e0["y1"] - o["y2"] <= 6.0:
                        return True       # its vowel or dot rides above it
                    if 0.0 <= o["y1"] - e0["y2"] <= 6.0:
                        return True       # or hangs below it
                return False

            cands = []
            for e in bods:
                if e is big or _owned_by_other(e):
                    continue
                # These pieces ARE letter fragments — the classifier is not
                # wrong about that — so "letter-part" cannot rule them out.
                # What separates a superscript from a tall letter standing on
                # a deep descender's line is that it is short as well as
                # lifted: the alef of أَلِيمٌۢ clears the baseline too, but it
                # is half the word tall, where the meem is a third.
                area = (e["x2"] - e["x1"]) * (e["y2"] - e["y1"])
                lift = base - e["y2"]
                if (lift >= 0.25 * hgt and area <= 0.40 * big_a
                        and (e["y2"] - e["y1"]) <= 0.45 * hgt):
                    cands.append((lift, e))
            cands.sort(key=lambda t: -t[0])
            for _, e in cands[:want - have]:
                e["kind"] = "mark"
                e["mark"] = name
                e["lab"] = name

    # A hamza is two different things wearing one outline, which is why a
    # shape table can never settle it. Riding on a carrier — أ إ ؤ ئ — it is a
    # MARK and the spelling counts it. Standing on its own, ء is a LETTER and
    # the spelling wants no mark at all. Only the position separates them: the
    # mark sits clear above or below its carrier, while the letter stands on
    # the line, in sequence with the rest of the word.
    _CARRIER = "\u0623\u0625\u0624\u0626\u0654\u0655"

    # The other direction. أَ is drawn as a stack: the hamza sits on the alef
    # and the fatha sits on the hamza. Both are the same small stroke to the
    # position labeller, so it names them both fatha and the word comes out a
    # hamza short and a fatha long — two budgets pointing at one fix. The
    # lower of the pair is the one touching the carrier, and that is the hamza.
    for r in wrec:
        txt = r["w"]["uthmani"]
        want_h = sum(txt.count(c) for c in _CARRIER)
        if not want_h:
            continue
        have_h = sum(1 for e in r["els"] if e.get("mark") == "hamza"
                     and not e.get("mkpart"))
        if have_h >= want_h:
            continue
        if os.environ.get("QSVG_HZB") == "0":
            continue
        _TAN = {"fatha": "\u064b\u08f0", "kasra": "\u064d\u08f2",
                "damma": "\u064c\u08f1"}
        _PLAIN = {"fatha": "\u064e", "kasra": "\u0650", "damma": "\u064f"}
        for fam in ("fatha", "kasra", "damma"):
            if have_h >= want_h:
                break
            pool = [e for e in r["els"] if e.get("mark") == fam]
            free = len([e for e in pool if not e.get("mkpart")])
            spare = free - sum(txt.count(c) for c in _PLAIN[fam])
            has_tan = any(c in txt for c in _TAN[fam])
            # Shape identity outranks position (Abdullah's e1025, item 38):
            # an element whose HUMAN-confirmed table label is hamza is the
            # hamza — no seating geometry needed, the outline is the proof.
            # classify() deliberately keeps hamza out of lab (ء twins), so
            # consult the raw table by signature here. The position test
            # below serves only shapes the table cannot tell apart.
            def _tab_hamza(q):
                v = shape_labels().get(q.get("sig"))
                lb = v.get("label") if isinstance(v, dict) else v
                auto = v.get("auto", False) if isinstance(v, dict) else False
                return lb == "hamza" and not auto
            for e in sorted(pool, key=lambda q: (not _tab_hamza(q),
                                                 -(q["y1"] + q["y2"]))):
                if have_h >= want_h:
                    break
                if _tab_hamza(e) and not e.get("mkpart"):
                    e["mark"] = "hamza"
                    e["lab"] = "hamza"
                    have_h += 1
                    spare -= 1
                    continue
                # A welded twin is spare capacity too. Two of the same stroke
                # are welded as a tanween, but this word's spelling has none —
                # so the pair is not a doubled vowel at all. It is the hamza
                # with its vowel stacked on top, which is how أَ is drawn.
                twin = bool(e.get("mkpart"))
                if twin:
                    if has_tan:
                        continue
                elif spare <= 0:
                    continue
                cx = (e["x1"] + e["x2"]) / 2
                on_carrier = any(
                    b["kind"] == "body" and (b["x2"] - b["x1"]) <= 7.0
                    and (b["y2"] - b["y1"]) >= 6.0
                    and b["x1"] - 1.5 <= cx <= b["x2"] + 1.5
                    and -1.0 <= b["y1"] - e["y2"] <= 5.0
                    for b in r["els"])
                above = any(o is not e and o["kind"] == "mark"
                            and min(o["x2"], e["x2"]) - max(o["x1"], e["x1"]) > 0.5
                            and -1.0 <= e["y1"] - o["y2"] <= 5.0
                            for o in r["els"])
                if not (on_carrier and above):
                    continue
                if twin:
                    e["mkpart"] = False
                    for o in r["els"]:
                        if e in (o.get("mkmembers") or []):
                            o["mkmembers"] = [m for m in o["mkmembers"]
                                              if m is not e]
                else:
                    spare -= 1
                e["mark"] = "hamza"
                e["lab"] = "hamza"
                have_h += 1

    # rename slashes inside each word by its own fatha/kasra budget: the ones
    # below the body midline are the kasras, capacity permitting
    for r in wrec:
        sl = [e for e in r["els"] if e["kind"] == "mark"
              and e.get("mark") in ("fatha", "kasra")
              and not e.get("mkpart") and not e.get("mkmembers")]
        if not sl:
            continue
        want_k = r["w"]["uthmani"].count("\u0650")
        # A kasra already carried by a welded mark — the hamza-with-kasra
        # under the alef of إِيَّاكَ — is not in this list and must still be
        # paid for out of the budget. Left uncounted, the loop below finds no
        # slash below the midline to spend the budget on and forces one ABOVE
        # into a kasra, which no kasra can be.
        want_k -= sum(1 for e in r["els"]
                      if e["kind"] == "mark" and e not in sl
                      and not e.get("mkpart")
                      and "kasra" in (e.get("mark") or "").split("+"))
        want_k = max(0, want_k)
        mid = (r["top"] + r["bot"]) / 2
        sl.sort(key=lambda e: -(e["y1"] + e["y2"]))     # lowest first
        for i, e in enumerate(sl):
            below = (e["y1"] + e["y2"]) / 2 > mid
            e["mark"] = "kasra" if (i < want_k and below) or                 (below and i < want_k + 1 and want_k) else                 ("kasra" if i < want_k and not any(
                    (x["y1"] + x["y2"]) / 2 > mid for x in sl) else "fatha")
        # simple pass: lowest want_k slashes that sit below mid become kasra
        for e in sl:
            e["mark"] = "fatha"
        k = 0
        for e in sl:
            if k < want_k and (e["y1"] + e["y2"]) / 2 > mid:
                e["mark"] = "kasra"
                k += 1
        if k < want_k:
            for e in sl:
                if k >= want_k:
                    break
                if e["mark"] == "fatha":
                    e["mark"] = "kasra"
                    k += 1
                    break

    # A ring is never dots. Letter dots are SOLID ink; a glyph whose outline
    # nests one contour inside another is a ring — the head of a ة or ه — and
    # several such shapes are auto-labelled "two-dots" in the table. Whatever
    # path named them, they are letter ink: strip the mark globally so the dot
    # budgets below count only real dots.
    for _w3, _at3 in assignment:
        for _a3 in _at3:
            for _e3 in _a3["els"]:
                if _e3.get("mark") not in ("dot", "two-dots", "three-dots"):
                    continue
                _cs = _e3.get("contours") or []
                if len(_cs) < 2:
                    continue
                _bbs = [c["sp"] for c in _cs]
                _ring = False
                for _i3, _a4 in enumerate(_bbs):
                    for _b4 in _bbs[_i3 + 1:]:
                        if (_a4["xmin"] <= _b4["xmin"] and _a4["xmax"] >= _b4["xmax"]
                                and _a4["ymin"] <= _b4["ymin"]
                                and _a4["ymax"] >= _b4["ymax"]) or \
                           (_b4["xmin"] <= _a4["xmin"] and _b4["xmax"] >= _a4["xmax"]
                                and _b4["ymin"] <= _a4["ymin"]
                                and _b4["ymax"] >= _a4["ymax"]):
                            _ring = True
                if _ring:
                    _e3.pop("mark", None)
                    _e3.pop("mkpart", None)
                    _e3["kind"] = "body"
                    _e3["lab"] = "letter-part"

    coverage = (labeled, total_marks)

    # Letter ink never carries a diacritic identity: positional labelers can
    # hand a mark name to a letter-part (the ك dagger reads as a slash, a tall
    # stem as a damma). The shape table is the authority — strip those labels.
    for _, atoms in assignment:
        for a in atoms:
            for e in a["els"]:
                if e.get("lab") in ("letter", "letter-part", "letter-hamza") \
                        and e.get("mark"):
                    del e["mark"]
                    e.pop("mkpart", None)

    # In-word tanween weld by TEXT: a kasratan drawn tucked against the
    # letter (the عٍ of ضريع/جوع) arrives as two plain slashes that the
    # positional namer calls fathas. When the text wants a tanween the word
    # does not yet have, its two stacked surplus slashes ARE that tanween.
    _TXTW = {"fathatan": ("\u064b", "\u08f0", ("fatha", "kasra")),
             "kasratan": ("\u064d", "\u08f2", ("fatha", "kasra")),
             "dammatan": ("\u064c", "\u08f1", ("damma",))}
    for _w, _atoms in assignment:
        if not _w:
            continue
        txt = _w["uthmani"]
        _els = [e for a in _atoms for e in a["els"]]
        for tan, (c1, c2, plains) in _TXTW.items():
            want_t = txt.count(c1) + txt.count(c2)
            if not want_t:
                continue
            have_t = sum(1 for e in _els if e.get("mark") == tan
                         and not e.get("mkpart"))
            if have_t >= want_t:
                continue
            plain_want = (txt.count("\u064e") + txt.count("\u0650")
                          if "fatha" in plains else txt.count("\u064f"))
            cand = [e for e in _els if e.get("mark") in plains + (tan,)
                    and not e.get("mkpart") and not e.get("mkmembers")]
            if len(cand) - plain_want < 2:
                continue                  # no surplus pair to claim
            best = None
            for i in range(len(cand)):
                for j in range(i + 1, len(cand)):
                    a2, b2 = cand[i], cand[j]
                    dx = abs((a2["x1"] + a2["x2"]) / 2
                             - (b2["x1"] + b2["x2"]) / 2)
                    dy = abs((a2["y1"] + a2["y2"]) / 2
                             - (b2["y1"] + b2["y2"]) / 2)
                    if dx < 4.5 and 0.8 < dy < 7.0:
                        d = dx + dy
                        if best is None or d < best[0]:
                            best = (d, a2, b2)
            if best:
                _, a2, b2 = best
                top, bot = (a2, b2) if a2["y1"] <= b2["y1"] else (b2, a2)
                top["mark"] = bot["mark"] = tan
                bot["mkpart"] = True
                top["mkmembers"] = top.get("mkmembers", []) + [bot]

    # Two dammatan-labeled pieces side by side in one word are ONE dammatan
    # drawn as a damma pair: weld early so later passes move them as a unit.
    for _w, _atoms in assignment:
        if not _w:
            continue
        # same for the stroke tanweens: two same-label kasratan/fathatan
        # singles side by side are ONE pair (p540/p568 twins, Abdullah)
        dt = [e for a in _atoms for e in a["els"]
              if e.get("mark") in ("dammatan", "kasratan", "fathatan")
              and not e.get("mkpart") and not e.get("mkmembers")]
        for i in range(len(dt)):
            for j in range(i + 1, len(dt)):
                a2, b2 = dt[i], dt[j]
                if a2.get("mkpart") or b2.get("mkpart"):
                    continue
                if a2.get("mark") != b2.get("mark"):
                    continue
                dx = abs((a2["x1"] + a2["x2"]) / 2 - (b2["x1"] + b2["x2"]) / 2)
                dy = abs((a2["y1"] + a2["y2"]) / 2 - (b2["y1"] + b2["y2"]) / 2)
                if dx < 5.0 and dy < 5.0:
                    b2["mkpart"] = True
                    a2.setdefault("mkmembers", []).append(b2)

    # Tanween pair reunification: a tanween's two strokes can land in
    # neighbouring words (even across a line break at the column edge), each
    # hiding inside a "balanced" plain-slash count. The text names the owner:
    # the word that wants the tanween claims the nearest matching stroke pair,
    # welds it, and oracle repair below settles the displaced plain budgets.
    _TXTT = {"fathatan": ("\u064b", "\u08f0"), "kasratan": ("\u064d", "\u08f2"),
             "dammatan": ("\u064c", "\u08f1")}
    _TPLAIN = {"fathatan": ("fatha",), "kasratan": ("kasra",),
               "dammatan": ("damma",)}
    _recs = []
    for _w, _atoms in assignment:
        if not _w:
            continue
        _els = [e for a in _atoms for e in a["els"]]
        _recs.append((_w, _atoms, _els))
    def _plain_ct(els):
        return sum(1 for e in els if e.get("mark") in ("fatha", "kasra")
                   and not e.get("mkpart") and not e.get("mkmembers"))
    for _w, _atoms, _els in _recs:
        txt = _w["uthmani"]
        pw_own = txt.count("\u064e") + txt.count("\u0650")
        for tan, chars in _TXTT.items():
            want_t = sum(txt.count(c) for c in chars)
            if not want_t:
                continue
            welded = sum(1 for e in _els if e.get("mark") == tan
                         and e.get("mkmembers"))
            if welded >= want_t:
                continue
            bods = [e for e in _els if e["kind"] == "body"]
            if not bods:
                continue
            mid = (min(e["y1"] for e in bods) + max(e["y2"] for e in bods)) / 2
            seeds = [e for e in _els if e.get("mark") == tan
                     and not e.get("mkpart") and not e.get("mkmembers")
                     and mid - 25.0 < (e["y1"] + e["y2"]) / 2 < mid + 20.0]
            if not seeds and tan == "dammatan":
                # a dammatan drawn as TWO damma curls inside the word: weld the
                # closest surplus pair into one unit
                dms = [e for e in _els if e.get("mark") == "damma"
                       and not e.get("mkpart") and not e.get("mkmembers")
                       and mid - 25.0 < (e["y1"] + e["y2"]) / 2 < mid + 20.0]
                # a TIGHT side-by-side pair is the ٌ curls even when the م's
                # own damma strayed to a neighbour — welding exposes the
                # deficit and the strict pass then fetches the stray
                tight = False
                for i1 in range(len(dms)):
                    for i2 in range(i1 + 1, len(dms)):
                        if abs(dms[i1]["x1"] - dms[i2]["x1"]) < 6.0 \
                                and abs(dms[i1]["y1"] - dms[i2]["y1"]) < 5.0:
                            tight = True
                if len(dms) >= (2 if tight else 2 + txt.count("\u064f")):
                    best_p = None
                    for i1 in range(len(dms)):
                        for i2 in range(i1 + 1, len(dms)):
                            a1, b1 = dms[i1], dms[i2]
                            d = (abs((a1["x1"] + a1["x2"]) / 2
                                     - (b1["x1"] + b1["x2"]) / 2)
                                 + abs((a1["y1"] + a1["y2"]) / 2
                                       - (b1["y1"] + b1["y2"]) / 2))
                            if d < 9.0 and (best_p is None or d < best_p[0]):
                                best_p = (d, a1, b1)
                    if best_p:
                        _, a1, b1 = best_p
                        top, bot = (a1, b1) if a1["x1"] >= b1["x1"] else (b1, a1)
                        top["mark"] = bot["mark"] = tan
                        bot["mkpart"] = True
                        top["mkmembers"] = top.get("mkmembers", []) + [bot]
                        continue
                # a lone curl seeds the cross-word search: its twin strayed
                # into a neighbouring word (even a line below)
                if not seeds:
                    seeds = dms
            if not seeds and tan != "dammatan" and _plain_ct(_els) > pw_own:
                seeds = [e for e in _els
                         if e.get("mark") in ("fatha", "kasra")
                         and not e.get("mkpart") and not e.get("mkmembers")
                         and (((e["y1"] + e["y2"]) / 2 > mid)
                              == (tan == "kasratan"))]
            # both strokes may already sit in the word as unwelded plain
            # slashes (a kasratan pair under مؤمنٰتٍ): weld in place first.
            # the ع descender can push the word's midline BELOW the upper
            # stroke, so pair from all spare slashes, not just the seeds
            pool = [e for e in _els
                    if e.get("mark") in ("fatha", "kasra", tan)
                    and not e.get("mkpart") and not e.get("mkmembers")]
            if len(pool) >= 2 and _plain_ct(_els) >= pw_own + 2:
                seeds = pool
            if len(seeds) >= 2 and _plain_ct(_els) >= pw_own + 2:
                bp = None
                for i1 in range(len(seeds)):
                    for i2 in range(i1 + 1, len(seeds)):
                        a1, b1 = seeds[i1], seeds[i2]
                        dx = abs((a1["x1"] + a1["x2"]) / 2
                                 - (b1["x1"] + b1["x2"]) / 2)
                        dy = abs((a1["y1"] + a1["y2"]) / 2
                                 - (b1["y1"] + b1["y2"]) / 2)
                        if dx < 4.5 and dy < 7.0 and (bp is None
                                                      or dx + dy < bp[0]):
                            bp = (dx + dy, a1, b1)
                if bp:
                    _, a1, b1 = bp
                    top, bot = (a1, b1) if a1["y1"] <= b1["y1"] else (b1, a1)
                    top["mark"] = bot["mark"] = tan
                    bot["mkpart"] = True
                    top["mkmembers"] = top.get("mkmembers", []) + [bot]
                    continue
            best = None
            for s1 in seeds:
                c1 = ((s1["x1"] + s1["x2"]) / 2, (s1["y1"] + s1["y2"]) / 2)
                for _w2, _at2, _els2 in _recs:
                    if _w2 is _w:
                        continue
                    t2 = _w2["uthmani"]
                    for s2 in _els2:
                        if s2.get("mkpart") or s2.get("mkmembers") \
                                or s2.get("standalone"):
                            continue
                        mk2 = s2.get("mark")
                        if mk2 == tan:
                            if sum(t2.count(c) for c in chars):
                                continue        # donor entitled to it
                        elif tan == "dammatan" and mk2 == "damma":
                            c2d = t2.count("\u064f")
                            h2d = sum(1 for x in _els2
                                      if x.get("mark") == "damma"
                                      and not x.get("mkpart"))
                            if h2d <= c2d:
                                continue        # donor not surplus
                        elif mk2 in ("fatha", "kasra"):
                            if tan == "dammatan":
                                continue
                            if _plain_ct(_els2) <= t2.count("\u064e") \
                                    + t2.count("\u0650"):
                                continue        # donor not surplus
                        else:
                            continue
                        c2 = ((s2["x1"] + s2["x2"]) / 2,
                              (s2["y1"] + s2["y2"]) / 2)
                        if not (mid - 25.0 < c2[1] < mid + 20.0):
                            continue      # from another line's band
                        dx = abs(c1[0] - c2[0]); dy = abs(c1[1] - c2[1])
                        if dx < 12.0 and dy < 6.0:
                            d = dx + dy
                            if best is None or d < best[0]:
                                best = (d, s1, s2, _at2, _els2)
            if best:
                _, s1, s2, _at2, _els2 = best
                _els2.remove(s2)
                for a in _at2:
                    if s2 in a["els"]:
                        a["els"].remove(s2)
                        break
                _atoms[0]["els"].append(s2)
                _els.append(s2)
                top, bot = (s1, s2) if s1["y1"] <= s2["y1"] else (s2, s1)
                top["mark"] = bot["mark"] = tan
                bot["mkpart"] = True
                top["mkmembers"] = top.get("mkmembers", []) + [bot]


    # ------------------------------------------------------------------
    # Oracle repair: the final authority. Whatever upstream stage erred, a
    # word that fails its oracles — piece count vs its own letter segments,
    # mark-family budgets from its text, line-band consistency, ayah-polygon
    # containment — trades elements with its geometric neighbours until the
    # joint score stops improving. Encodes verify-and-keep-fixing in code.
    # ------------------------------------------------------------------
    def _o_fams(txt):
        return {f: _cap(txt, f) for f in
                ("slash", "damma", "sukun", "hamza", "wasla", "small-alef",
                 "maddah", "shadda", "small-circle", "pause",
                 "small-waw", "small-ya")}

    _OFAM = {"fatha": "slash", "kasra": "slash", "fathatan": "slash",
             "kasratan": "slash", "damma": "damma", "dammatan": "damma",
             "sukun": "sukun", "hamza": "hamza", "wasla": "wasla",
             "small-alef": "small-alef", "maddah": "maddah", "shadda": "shadda",
             "small-circle": "small-circle", "pause": "pause",
             "meem-iqlab": "meem-iqlab",
             "small-waw": "small-waw", "small-ya": "small-ya"}

    owords = []
    for w, at in assignment:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        if not els:
            continue
        bods = [e for e in els if e["kind"] == "body"]
        lns = [e.get("line") for e in (bods or els) if e.get("line")]
        ln0 = max(set(lns), key=lns.count) if lns else None
        owords.append({"w": w, "at": at, "ln": ln0,
                       "nseg": max(1, len(segment_word(w["uthmani"]))),
                       "top": min(e["y1"] for e in (bods or els)),
                       "bot": max(e["y2"] for e in (bods or els)),
                       "caps": _o_fams(w["uthmani"])})

    _ordix = {id(_r0): _i0 for _i0, _r0 in enumerate(owords)}

    def _ospan(r):
        els = [e for a in r["at"] for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"] or els
        if not bods:
            return r.get("span0", (0.0, 0.0))
        sp = (min(e["x1"] for e in bods), max(e["x2"] for e in bods))
        r.setdefault("span0", sp)
        return sp

    def _oscore(r):
        els = [e for a in r["at"] for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        eff = []
        for b in bods:                     # a stroke nested inside a sibling is
            wb = b["x2"] - b["x1"]         # part of the same letter, not a piece
            hb = b["y2"] - b["y1"]
            # a stroke DRAWN OVER a letter (the kaf armature, a lam-alef's
            # second stroke) sits within its host's height; a piece that rises
            # ABOVE its host is a letter of its own — the silent alef standing
            # on the waw of ـوا۟ — and must keep counting as a piece.
            inside = any(o is not b
                         and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"])
                         >= 0.6 * wb
                         and (o["x2"] - o["x1"]) > wb
                         and hb <= (o["y2"] - o["y1"]) + 1.0
                         for o in bods)
            if not inside:
                eff.append(b)
        sc = 3.0 * abs(len(eff) - r["nseg"])
        have = {}
        for e in els:
            f = _OFAM.get(e.get("mark"))
            if f and not e.get("mkpart"):
                have[f] = have.get(f, 0) + 1
        for f, want in r["caps"].items():
            sc += 2.0 * abs(have.get(f, 0) - want)
        if r["ln"]:
            sc += 2.0 * sum(1 for e in els
                            if e.get("line") and abs(e["line"] - r["ln"]) >= 1)
        return sc

    def _rtl_ok(a, b):
        """True when a and b still read in the right order on their line.

        Arabic runs right to left, so the word that comes first must keep the
        higher x. Words legitimately overlap — a sweeping tail runs under its
        neighbour — so this checks the two spans do not CROSS, not that they
        stay apart.
        """
        if a["ln"] is None or a["ln"] != b["ln"]:
            return True

        def _bspan(r):
            bs = [e for at in r["at"] for e in at["els"]
                  if e["kind"] == "body"]
            if not bs:
                return None
            return min(e["x1"] for e in bs), max(e["x2"] for e in bs)

        # Letter ink alone fixes a word's place on the line. Marks reach well
        # past it -- the hamza of أَوْ stands almost as far left as the whole
        # of مشركة -- so measuring with them makes a crossing look legal.
        fa, fb = _bspan(a), _bspan(b)
        if fa is None or fb is None:
            return False          # a word stripped of every letter is not a fix
        first, second = (a, b) if _ordix[id(a)] < _ordix[id(b)] else (b, a)
        f1, f2 = _bspan(first)
        s1, s2 = _bspan(second)
        return f1 >= s1 - 1.0 and f2 >= s2 - 1.0

    _TRACE = os.environ.get("QSVG_TRACE")
    # Letting the width prior carry a body move the oracle cannot judge is OFF.
    # Measured over all 604 pages it changes the number of wrong-sized words by
    # five — noise — while doing real damage in particular places: it fixed أَوْ
    # on p350 by taking sixteen units from وٱلزانية, and fixed إلى on p574 by
    # robbing أرسلنا. A rule that buys nothing and breaks words visibly is not
    # worth keeping. QSVG_WDECIDE=<gain> re-enables it for experiments.
    _WDECIDE = float(os.environ.get("QSVG_WDECIDE", "0"))

    def _omove(e, src, dst):
        if isinstance(e, dict) and e.get("_ovr"):
            return False              # overridden pieces never move again
        # QSVG_TRACE=<x1> prints every hand-off of one piece of ink, which is
        # how a word that ends up with the wrong letter gets traced back to
        # the pass that took it.
        # QSVG_TRACE=all traces every hand-off on the page, which is how a whole
        # sweep is attributed to the passes that cause it rather than one word at
        # a time.
        if _TRACE and (_TRACE == "all"
                       or any(abs(e["x1"] - float(_t)) < 0.5
                              for _t in _TRACE.split(","))):
            import traceback as _tb
            _fr = _tb.extract_stack()[-2]
            sys.stderr.write("MOVE line%-5d %-6s/%s x %.1f-%.1f  %s -> %s\n"
                             % (_fr.lineno, e["kind"], e.get("mark"), e["x1"], e["x2"],
                                src["w"]["uthmani"], dst["w"]["uthmani"]))
        for a in src["at"]:
            if e in a["els"]:
                a["els"].remove(e)
                for m in e.get("mkmembers", []):
                    if m in a["els"]:
                        a["els"].remove(m)
                break
        tgt = min(dst["at"], key=lambda a2: min(abs((x["x1"] + x["x2"]) / 2
                  - (e["x1"] + e["x2"]) / 2) for x in a2["els"])
                  if a2["els"] else 1e9)
        tgt["els"].append(e)
        tgt["els"].extend(e.get("mkmembers", []))

    for _round in range(3):
        improved = False
        for r in owords:
            base_r = _oscore(r)
            if base_r <= 0:
                continue
            rx1, rx2 = _ospan(r)
            for v in owords:
                if v is r or v["ln"] is None or r["ln"] is None:
                    continue
                if abs(v["ln"] - r["ln"]) > 1:
                    continue
                vx1, vx2 = _ospan(v)
                if vx2 < rx1 - 20 or vx1 > rx2 + 20:
                    continue
                base = base_r + _oscore(v)
                def _wdev(x):
                    # width deviation vs the word's QCF share of its line
                    ln0 = x["ln"]
                    rs0 = [y for y in owords if y["ln"] == ln0]
                    ta = tq = 0.0
                    for y in rs0:
                        y1, y2 = _ospan(y)
                        ta += y2 - y1
                        tq += letters(y["w"])
                    if not tq or not ta:
                        return 0.0
                    x1, x2 = _ospan(x)
                    exp = letters(x["w"]) / tq * ta
                    import math as _m
                    return abs(_m.log(max((x2 - x1) / max(exp, 1e-6), 1e-3)))

                best = None
                for e in [x for a in v["at"] for x in a["els"]]:
                    if e.get("mkpart") or e.get("standalone"):
                        continue
                    if e["kind"] == "body" and v["ln"] != r["ln"]:
                        continue          # letter ink never crosses lines
                    if e["kind"] == "body" and e.get("lab") in \
                            ("letter-part", "letter", "letter-hamza"):
                        continue          # fragments stay with their base
                    cx = (e["x1"] + e["x2"]) / 2
                    win = 18.0 if e["kind"] == "body" else 4.0
                    if not (rx1 - win < cx < rx2 + win):
                        continue
                    far = e["kind"] == "body" and not (rx1 - 2 < cx < rx2 + 2)
                    if e["kind"] == "body":
                        wj0 = _wdev(r) + _wdev(v)
                        wj0_worst = max(_wdev(r), _wdev(v))
                    _omove(e, v, r)
                    d = _oscore(r) + _oscore(v)
                    ok_w = True
                    if e["kind"] == "body":
                        gain = wj0 - (_wdev(r) + _wdev(v))
                        # a far body must EARN its move with a real width gain;
                        # nearby pieces only need to not hurt
                        ok_w = gain >= (0.08 if far else -0.02)
                        # Width measures a span, not which piece fills it, so
                        # it is equally happy when two words trade the wrong
                        # letters. Reading order is what pins the piece down:
                        # on the line, an earlier word's ink stays right of a
                        # later one's. Letting أَوْ hand its alef away and take
                        # مشركة's waw satisfies both widths and puts the words
                        # in the wrong order on the page.
                        if ok_w and not _rtl_ok(r, v):
                            ok_w = False
                        # The gain is a SUM, so a word left far too short can
                        # hide behind a neighbour that lands perfectly. On
                        # p350 مشركة finished at 33.2 against 33.4 wanted by
                        # taking 16u from وٱلزانية, which ended at 25 against
                        # 41 — a good score for the pair, a broken word on the
                        # page. Neither side may be left badly out of size.
                        if ok_w:
                            worst_now = max(_wdev(r), _wdev(v))
                            if worst_now > 0.35 and worst_now > wj0_worst:
                                ok_w = False
                    _omove(e, r, v)
                    # The oracle counts marks, so it is flat on a body move
                    # that leaves both words' mark budgets intact — a letter
                    # piece sitting in the wrong word scores exactly like one
                    # sitting in the right word. Demanding it improve throws
                    # away moves the ink itself settles: on p350 the waw of
                    # أَوْ scored d == base while the width prior gained 0.60,
                    # leaving the word one piece where أ and و must give two.
                    # When the oracle is indifferent, let the widths decide,
                    # but only on a decisive gain.
                    take = ok_w and d < base - 0.5
                    if (_WDECIDE and not take and ok_w and e["kind"] == "body"
                            and d <= base + 1e-9 and gain >= _WDECIDE):
                        take = True
                    if take and (best is None or d < best[0]):
                        best = (d, e)
                if best:
                    _omove(best[1], v, r)
                    improved = True
                    base_r = _oscore(r)
        if not improved:
            break

    # Welded tanween masters are identity-strong: only a word whose text
    # carries that tanween may own the pair. Strict surplus->deficit transfer.
    for lab, chars in (("fathatan", "\u064b\u08f0"),
                       ("kasratan", "\u064d\u08f2"),
                       ("dammatan", "\u064c\u08f1")):
        for r in owords:
            want_r = sum(r["w"]["uthmani"].count(ch) for ch in chars)
            mine = [e for a in r["at"] for e in a["els"]
                    if e.get("mark") == lab and not e.get("mkpart")]
            if len(mine) <= want_r:
                continue
            for v in owords:
                if v is r or v["ln"] is None or r["ln"] is None \
                        or abs(v["ln"] - r["ln"]) > 1:
                    continue
                want_v = sum(v["w"]["uthmani"].count(ch) for ch in chars)
                have_v = sum(1 for a in v["at"] for e in a["els"]
                             if e.get("mark") == lab and not e.get("mkpart"))
                if have_v >= want_v:
                    continue
                vx1, vx2 = _ospan(v)
                cands = [e for e in mine
                         if vx1 - 12.0 < (e["x1"] + e["x2"]) / 2 < vx2 + 12.0]
                if not cands:
                    continue
                mv = min(cands, key=lambda e: abs((vx1 + vx2) / 2
                                                  - (e["x1"] + e["x2"]) / 2))
                _omove(mv, r, v)
                mine.remove(mv)
                if len(mine) <= want_r:
                    break

    # Line-balanced family refill: when a line's total of a family equals the
    # line's total budget but members are shuffled through a chain of words,
    # re-deal the marks in reading order against each word's quota (a mark may
    # only land in a word whose span, widened, actually reaches it).
    _lines_of = {}
    for r in owords:
        if r["ln"]:
            _lines_of.setdefault(r["ln"], []).append(r)
    for ln2, rs in _lines_of.items():
        rs.sort(key=lambda r: -sum(_ospan(r)) / 2)
        for fam in ("slash", "damma"):
            labs = tuple(l for l, f in _OFAM.items() if f == fam)
            want = {id(r): _cap(r["w"]["uthmani"], fam) for r in rs}
            pool = []
            for r in rs:
                for e in [x for a in r["at"] for x in a["els"]]:
                    if e.get("mark") in labs and not e.get("mkpart"):
                        pool.append((e, r))
            if sum(want.values()) != len(pool) or not pool:
                continue
            if all(sum(1 for e, r0 in pool if r0 is r) == want[id(r)]
                   for r in rs):
                continue
            pool.sort(key=lambda t: -(t[0]["x1"] + t[0]["x2"]) / 2)
            quota = dict(want)
            plan = []
            wi = 0
            ok = True
            for e, r0 in pool:
                while wi < len(rs) and quota[id(rs[wi])] <= 0:
                    wi += 1
                if wi >= len(rs):
                    ok = False
                    break
                tgt = rs[wi]
                x1, x2 = _ospan(tgt)
                cx = (e["x1"] + e["x2"]) / 2
                if not (x1 - 12.0 < cx < x2 + 12.0):
                    ok = False
                    break
                quota[id(tgt)] -= 1
                plan.append((e, r0, tgt))
            if ok:
                for e, r0, tgt in plan:
                    if r0 is not tgt:
                        _omove(e, r0, tgt)


    # Final strict pass: after every layer, any family surplus standing next
    # to a deficit (same or adjacent line, within reach) is resolved. Runs to
    # fixpoint; strictly budget-guarded, so it can only reduce mismatches.
    for _rounds in range(3):
        moved_any = False
        for fam in set(_OFAM.values()):
            labs = tuple(l for l, f in _OFAM.items() if f == fam)
            for r in owords:
                cap_r = _cap(r["w"]["uthmani"], fam)
                mine = [e for a in r["at"] for e in a["els"]
                        if e.get("mark") in labs and not e.get("mkpart")]
                if len(mine) <= cap_r:
                    continue
                for v in owords:
                    if v is r or v["ln"] is None or r["ln"] is None \
                            or abs(v["ln"] - r["ln"]) > 1:
                        continue
                    cap_v = _cap(v["w"]["uthmani"], fam)
                    have_v = sum(1 for a in v["at"] for e in a["els"]
                                 if e.get("mark") in labs
                                 and not e.get("mkpart"))
                    if have_v >= cap_v:
                        continue
                    vx1, vx2 = _ospan(v)
                    _reach = 14.0 if v["ln"] == r["ln"] else 20.0
                    cands = [e for e in mine
                             if vx1 - _reach < (e["x1"] + e["x2"]) / 2
                             < vx2 + _reach
                             and not (fam in _ABOVE_FAM
                                      and (e["y1"] + e["y2"]) / 2 > v["bot"])]
                    if not cands:
                        continue
                    mv = min(cands, key=lambda e: abs((vx1 + vx2) / 2
                             - (e["x1"] + e["x2"]) / 2))
                    _omove(mv, r, v)
                    mine.remove(mv)
                    moved_any = True
                    if len(mine) <= cap_r:
                        break
        if not moved_any:
            break

    # Text-gated trust for auto damma shapes: the shape table's UNCONFIRMED
    # damma/dammatan entries are ignored at classify time (a stem can match
    # them), so on some pages the real damma lands as a small "body". When a
    # word's text still WANTS a damma-family mark and it holds a small body
    # whose outline the table calls damma/dammatan, the text confirms the
    # shape — reclassify it as that mark.
    _full_tab = shape_labels()
    for r in owords:
        want_d = _cap(r["w"]["uthmani"], "damma")
        if not want_d:
            continue
        def _dunits(_r=r):
            return sum(1 for a in _r["at"] for x in a["els"]
                       if x.get("mark") in ("damma", "dammatan")
                       and not x.get("mkpart"))
        if _dunits() >= want_d:
            continue
        for a in r["at"]:
            for e in a["els"]:
                if e["kind"] != "body" or e.get("mark"):
                    continue
                w2 = e["x2"] - e["x1"]; h2 = e["y2"] - e["y1"]
                if not (3.0 <= max(w2, h2) <= 9.0):
                    continue
                v = _full_tab.get(pk(e))
                lab = (v.get("label") if isinstance(v, dict) else v) if v else None
                if lab in ("damma", "dammatan"):
                    e["kind"] = "mark"
                    e["mark"] = lab
                    if _dunits() >= want_d:
                        break

    # A slash-family "mark" whose ink sits INSIDE a letter's own box is the
    # letter's armature (the ك dagger) mislabeled by a shape collision — a
    # real fatha rides above the ink, a kasra below. Only a word whose slash
    # count exceeds its text budget may reclassify, most-interior first.
    for r in owords:
        want_s = _cap(r["w"]["uthmani"], "slash")
        def _shave(_r=r):
            return sum(1 for a in _r["at"] for x in a["els"]
                       if _OFAM.get(x.get("mark")) == "slash"
                       and not x.get("mkpart"))
        if _shave() <= want_s:
            continue
        bods = [x for a in r["at"] for x in a["els"] if x["kind"] == "body"
                and (x["y2"] - x["y1"]) >= 8.0]
        cands = []
        for e in [x for a in r["at"] for x in a["els"]
                  if x.get("mark") in ("fatha", "kasra")
                  and not x.get("mkpart") and not x.get("mkmembers")]:
            cx = (e["x1"] + e["x2"]) / 2
            cy = (e["y1"] + e["y2"]) / 2
            for b in bods:
                if b["x1"] <= cx <= b["x2"] \
                        and b["y1"] + 1.5 <= cy <= b["y2"] - 1.5:
                    depth = min(cy - b["y1"], b["y2"] - cy)
                    cands.append((depth, e))
                    break
        for _, e in sorted(cands, key=lambda t: -t[0]):
            if _shave() <= want_s:
                break
            e["kind"] = "body"
            del e["mark"]

    # Absorb stranded damma-family surplus: a word that wants NONE of the
    # family but holds a piece, with every neighbour numerically satisfied,
    # is carrying half of a neighbour's two-piece damma/dammatan — weld the
    # piece into the closest adjacent same-family unit instead.
    for r in owords:
        for e in [x for a in r["at"] for x in a["els"]
                  if x.get("mark") in ("damma", "dammatan")
                  and not x.get("mkpart") and not x.get("mkmembers")]:
            if _cap(r["w"]["uthmani"], "damma") >= sum(
                    1 for a in r["at"] for x in a["els"]
                    if x.get("mark") in ("damma", "dammatan")
                    and not x.get("mkpart")):
                break
            cx = (e["x1"] + e["x2"]) / 2
            cy = (e["y1"] + e["y2"]) / 2
            best = None
            for v in owords:
                if v is r or v["ln"] is None or r["ln"] is None \
                        or abs(v["ln"] - r["ln"]) > 1:
                    continue
                for u in [x for a in v["at"] for x in a["els"]
                          if x.get("mark") in ("damma", "dammatan")
                          and not x.get("mkpart")]:
                    dx = abs((u["x1"] + u["x2"]) / 2 - cx)
                    dy = abs((u["y1"] + u["y2"]) / 2 - cy)
                    if dx < 7.0 and dy < 7.0 and (best is None
                                                  or dx + dy < best[0]):
                        best = (dx + dy, u, v)
            if best:
                _, u, v = best
                _omove(e, r, v)
                e["mkpart"] = True
                u.setdefault("mkmembers", []).append(e)

    # A meem-iqlab that no text demands is the LETTER meem: give it back to
    # the ink. (Left as a mark it may re-line onto a neighbouring line — the
    # م of يَوْمَ landing on ٱبْنُ below it, and the hole it leaves pulling a
    # piece off each following word.)
    # THE PRINT's text decides, not uthmani: quran.com writes tanween+\u06e2 at
    # idgham/ikhfa positions where this print draws NO small م (QPC open-tanween
    # encoding is the drawing convention — reported.json items 23/24). Abdullah
    # sampled 16/16 of the residue by eye: all letters. So the demote keys on
    # the QPC text where present.
    for r in owords:
        _ptxt = r["w"].get("qpc") or r["w"]["uthmani"]
        if "\u06e2" in _ptxt or "\u06ed" in _ptxt:
            continue
        for a in r["at"]:
            for e in a["els"]:
                if e.get("mark") == "meem-iqlab" and not e.get("mkpart"):
                    e.pop("mark", None)
                    e["kind"] = "body"
                    e["lab"] = "letter-part"

    # Every mark has a natural owner: the word whose letters it is drawn
    # against, on the correct side — fatha, damma, sukun, shadda, madda,
    # small-alef and wasla ride above; kasra and kasratan hang below. Budgets
    # cannot recover this, because three words can hold one another's marks in
    # a cycle with every count still balancing. So compute each mark's natural
    # owner from the ink alone and apply the moves together, which unwinds a
    # cycle in one pass.
    _SIDE_ABOVE = {"fatha", "damma", "sukun", "shadda", "maddah",
                   "small-alef", "wasla", "fathatan", "dammatan",
                   "small-circle", "meem-iqlab"}
    _SIDE_BELOW = {"kasra", "kasratan"}
    for _round in range(3):
        _ink = {}
        for r in owords:
            bs = [e for a in r["at"] for e in a["els"] if e["kind"] == "body"]
            if bs:
                _ink[id(r)] = (min(e["x1"] for e in bs), max(e["x2"] for e in bs),
                               min(e["y1"] for e in bs), max(e["y2"] for e in bs))

        def _fit(v, mk, cx, cy):
            sp = _ink.get(id(v))
            if not sp or not (sp[0] - 1.0 <= cx <= sp[1] + 1.0):
                return None
            gap = (sp[2] - cy) if mk in _SIDE_ABOVE else (cy - sp[3])
            if gap < -2.0 or gap > 16.0:
                return None               # not drawn against this word's ink
            return (gap, abs(cx - (sp[0] + sp[1]) / 2))

        moves = []
        for r in owords:
            if id(r) not in _ink:
                continue
            for a in r["at"]:
                for e in a["els"]:
                    if e["kind"] != "mark" or e.get("mkpart") \
                            or e.get("standalone"):
                        continue
                    mk = e.get("mark")
                    if mk not in _SIDE_ABOVE and mk not in _SIDE_BELOW:
                        continue
                    cx = (e["x1"] + e["x2"]) / 2
                    cy = (e["y1"] + e["y2"]) / 2
                    here = _fit(r, mk, cx, cy)
                    best = None
                    for v in owords:
                        if v["ln"] is None or r["ln"] is None \
                                or abs(v["ln"] - r["ln"]) > 1:
                            continue
                        f = _fit(v, mk, cx, cy)
                        if f is None:
                            continue
                        if best is None or f < best[0]:
                            best = (f, v)
                    if best is None or best[1] is r:
                        continue
                    # only when the other word is a clearly better fit
                    if here is not None and here[0] <= best[0][0] + 2.0:
                        continue
                    moves.append((e, r, best[1]))
        if not moves:
            break
        # Keep only moves that CLOSE: every word involved must give away as
        # many marks of a family as it receives. That is exactly the cycle
        # case, where each word ends with its own ink and no budget changes —
        # a lone move is a guess about ink nobody else claims, so it is
        # dropped and left for the audit to surface.
        fam_of = lambda e: _OFAM.get(e.get("mark")) or e.get("mark")
        out_c, in_c = {}, {}
        for e, src, dst in moves:
            f = fam_of(e)
            out_c[(id(src), f)] = out_c.get((id(src), f), 0) + 1
            in_c[(id(dst), f)] = in_c.get((id(dst), f), 0) + 1
        keep = [(e, src, dst) for e, src, dst in moves
                if out_c.get((id(src), fam_of(e)), 0)
                == in_c.get((id(src), fam_of(e)), 0)
                and out_c.get((id(dst), fam_of(e)), 0)
                == in_c.get((id(dst), fam_of(e)), 0)]
        if not keep:
            break
        for e, src, dst in keep:
            e["line"] = dst["ln"]
            _omove(e, src, dst)

    # A mark belongs to the line it is DRAWN in. Marks ride above and below
    # their letters, so some overshoot is normal, but ink sitting squarely in
    # a neighbouring band was drawn for a word there. The budgets cannot see
    # this — the holder's counts can balance perfectly — only the geometry can.
    _bands = {li0["lineNumber"]: (li0["top"], li0["bottom"])
              for li0 in lines_info}
    if _bands:
        _byline = {}
        for r in owords:
            if r["ln"] is not None:
                _byline.setdefault(r["ln"], []).append(r)
        for r in owords:
            if r["ln"] not in _bands:
                continue
            top0, bot0 = _bands[r["ln"]]
            h0 = max(1e-6, bot0 - top0)
            for a in list(r["at"]):
                for e in list(a["els"]):
                    if e["kind"] != "mark" or e.get("mkpart") \
                            or e.get("standalone"):
                        continue
                    cy = (e["y1"] + e["y2"]) / 2
                    tgt_ln, depth = None, 0.0
                    for ln0, (t0, b0) in _bands.items():
                        if t0 <= cy <= b0 and abs(ln0 - r["ln"]) <= 2:
                            tgt_ln = ln0
                            # how far inside that band it sits, as a share
                            depth = min(cy - t0, b0 - cy) / max(1e-6, b0 - t0)
                            break
                    if tgt_ln is None or tgt_ln == r["ln"]:
                        continue
                    fam0 = _OFAM.get(e.get("mark"))
                    cx = (e["x1"] + e["x2"]) / 2
                    best = None
                    for v in _byline.get(tgt_ln, []):
                        sp = _ospan(v)
                        # the mark must stand over this word's OWN ink: on the
                        # target line, containment is the evidence, not nearness
                        if not (sp[0] - 0.5 <= cx <= sp[1] + 0.5):
                            continue
                        short = 0
                        if fam0:
                            capv = _cap(v["w"]["uthmani"], fam0)
                            havev = sum(1 for a2 in v["at"] for x2 in a2["els"]
                                        if _OFAM.get(x2.get("mark")) == fam0
                                        and not x2.get("mkpart"))
                            short = 1 if havev < capv else 0
                        # a short word's claim is decisive; otherwise the
                        # mark must sit deep inside the other band, not merely
                        # dip into it the way a low kasra does
                        if not short and depth < 0.25:
                            continue
                        d = abs(cx - (sp[0] + sp[1]) / 2)
                        key = (-short, d)
                        if best is None or key < best[0]:
                            best = (key, v)
                    if best is None:
                        continue
                    e["line"] = tgt_ln
                    _omove(e, r, best[1])

    # Two words can hold each other's marks: the counts then balance in both,
    # so no budget check can see it — but the geometry is unambiguous. A mark
    # sitting outside its own word's ink and over a neighbour's, matched by one
    # going the other way, is a swap. Exchanging them keeps every budget intact
    # and can only move ink closer to the letters it was drawn on.
    def _mspan(rec):
        bs = [e for a in rec["at"] for e in a["els"] if e["kind"] == "body"]
        if not bs:
            return None
        return (min(e["x1"] for e in bs), max(e["x2"] for e in bs))

    _SWAP_FAM = {"fatha": "slash", "kasra": "slash", "damma": "damma",
                 "sukun": "sukun", "shadda": "shadda", "maddah": "maddah",
                 "small-alef": "small-alef", "hamza": "hamza",
                 "dot": "dots", "two-dots": "dots", "three-dots": "dots"}
    for r in owords:
        sp_r = _mspan(r)
        if sp_r is None:
            continue
        for v in owords:
            if v is r or v["ln"] is None or r["ln"] is None \
                    or abs(v["ln"] - r["ln"]) > 1:
                continue
            sp_v = _mspan(v)
            if sp_v is None:
                continue
            def _stray(src, own, other):
                out = []
                for a in src["at"]:
                    for e in a["els"]:
                        if e["kind"] != "mark" or e.get("mkpart"):
                            continue
                        fam = _SWAP_FAM.get(e.get("mark"))
                        if not fam:
                            continue
                        cx = (e["x1"] + e["x2"]) / 2

                        def _d(sp):
                            return 0.0 if sp[0] <= cx <= sp[1] else \
                                min(abs(cx - sp[0]), abs(cx - sp[1]))
                        # judge by which ink it is nearer to, not by a hard
                        # boundary: a mark can overhang its letter slightly
                        if _d(own) <= _d(other) + 1.0:
                            continue
                        out.append((fam, e))
                return out
            mine = _stray(r, sp_r, sp_v)
            theirs = _stray(v, sp_v, sp_r)
            if not mine or not theirs:
                continue
            for fam1, e1 in list(mine):
                match = next(((f2, e2) for f2, e2 in theirs if f2 == fam1), None)
                if match is None:
                    continue
                theirs.remove(match)
                _omove(e1, r, v)
                _omove(match[1], v, r)

    # A dammatan drawn as ONE glyph, and the small waw: both share the damma's
    # outline, so the table names all three "damma". The text separates them —
    # the tanween rides above the word's last letter, the small waw sits down
    # at writing level after it.
    for r in owords:
        txt = r["w"]["uthmani"]
        els9 = [e for a in r["at"] for e in a["els"]]
        # a welded pair counts through its master, and that master is exactly
        # what needs the tanween's name
        dms = [e for e in els9 if e.get("mark") == "damma"
               and not e.get("mkpart")]
        if not dms:
            continue
        plain = txt.count("\u064f")
        want_dt = txt.count("\u064c") + txt.count("\u08f1")
        want_sw = txt.count("\u06e5")
        have_dt = sum(1 for e in els9 if e.get("mark") == "dammatan"
                      and not e.get("mkpart"))
        have_sw = sum(1 for e in els9 if e.get("mark") == "small-waw"
                      and not e.get("mkpart"))
        bods9 = [e for e in els9 if e["kind"] == "body"]
        if not bods9:
            continue
        top9 = min(e["y1"] for e in bods9)
        bot9 = max(e["y2"] for e in bods9)
        lx9 = min(e["x1"] for e in bods9)
        # the small waw first: it is the one sitting AT writing level
        for _ in range(max(0, want_sw - have_sw)):
            cands = [e for e in dms
                     if (e["y1"] + e["y2"]) / 2 > top9 + 0.45 * (bot9 - top9)]
            if len(dms) <= plain or not cands:
                break
            mv = min(cands, key=lambda e: abs((e["x1"] + e["x2"]) / 2 - lx9))
            mv["mark"] = "small-waw"
            dms.remove(mv)
        # then the tanween: the surplus curl nearest the end of the word
        for _ in range(max(0, want_dt - have_dt)):
            if len(dms) <= plain:
                break
            mv = min(dms, key=lambda e: abs((e["x1"] + e["x2"]) / 2 - lx9))
            mv["mark"] = "dammatan"
            for _m in mv.get("mkmembers", []):
                _m["mark"] = "dammatan"
            dms.remove(mv)

    # The hamza of a seated alef: أ ؤ ئ carry it ABOVE, إ carries it BELOW.
    # Its outline is not always in the shape table, and where it sits under an
    # alef the position labeller can even read it as a wasla — which is
    # impossible, since a wasla only ever sits above. The text says the word
    # carries a hamza; the geometry says which mark it is.
    for r in owords:
        txt = r["w"]["uthmani"]
        want_h = (sum(txt.count(c) for c in "\u0623\u0625\u0624\u0626")
                  + txt.count("\u0654") + txt.count("\u0655"))
        if not want_h:
            continue
        els9 = [e for a in r["at"] for e in a["els"]]
        have_h = sum(1 for e in els9 if e.get("mark") == "hamza"
                     and not e.get("mkpart"))
        if have_h >= want_h:
            continue
        below = ("\u0625" in txt or "\u0655" in txt)
        has_wasla_text = "\u0671" in txt
        alefs = [e for e in els9 if e["kind"] == "body"
                 and (e["x2"] - e["x1"]) <= 7.0
                 and (e["y2"] - e["y1"]) >= 8.0]
        if not alefs:
            continue
        for _ in range(want_h - have_h):
            best = None
            for e in els9:
                if e["kind"] != "mark" or e.get("mkpart"):
                    continue
                mk = e.get("mark")
                if mk == "hamza":
                    continue
                if mk is None:
                    pass                  # unnamed ink: the likeliest hamza
                elif mk == "wasla" and not has_wasla_text and below:
                    pass                  # a wasla cannot sit below an alef
                else:
                    continue
                cx = (e["x1"] + e["x2"]) / 2
                for al in alefs:
                    if not (al["x1"] - 2.5 <= cx <= al["x2"] + 2.5):
                        continue
                    d = (e["y1"] - al["y2"]) if below else (al["y1"] - e["y2"])
                    if not (-2.0 <= d <= 5.0):
                        continue
                    if best is None or d < best[0]:
                        best = (d, e)
            if best is None:
                break
            best[1]["mark"] = "hamza"

    # Put every wasla over the alef it is drawn on, BEFORE the pass below
    # pulls alefs toward the words holding them. A wasla rides at the far left
    # of the word before it, standing over the NEXT word's opening alef, and
    # the split search — which sees overlap, not spelling — hands it to the
    # word it overlaps. Left uncorrected first, the pass below reads the stray
    # mark as proof and drags a second word's alef across to join it.
    def _alef6(e):
        return (e["kind"] == "body" and not e.get("mark")
                and (e["x2"] - e["x1"]) <= 6.0
                and (e["y2"] - e["y1"]) >= 6.0)

    def _stands_on(wa, e):
        ovx = min(e["x2"], wa["x2"]) - max(e["x1"], wa["x1"])
        d = e["y1"] - wa["y2"]
        return (ovx, d) if ovx > 0.5 and -1.5 <= d <= 5.0 else None

    for r in owords:
        # Only a word whose spelling has no ٱ at all is certainly not the
        # owner. Words that do have one keep their mark: neighbouring words
        # overlap — ٱلرَّحْمَـٰنِ and ٱلرَّحِيمِ share 18u on page 1 — so one
        # word's alef routinely lies under the other's wasla, and geometry
        # alone would hand the mark to the wrong one.
        if "\u0671" in r["w"]["uthmani"]:
            continue
        stray6 = [e for a in r["at"] for e in a["els"]
                  if e.get("mark") == "wasla" and not e.get("mkpart")]
        for wa in stray6:
            wcx = (wa["x1"] + wa["x2"]) / 2
            best = None
            for v in owords:
                if v is r or v["ln"] != r["ln"]:
                    continue
                txt6 = v["w"]["uthmani"]
                if "\u0671" not in txt6:
                    continue
                # No budget test here on purpose. These misplacements come in
                # chains — هُوَ holds ٱلسَّمِيعُ's wasla while ٱلسَّمِيعُ holds
                # ٱلْعَلِيمُ's — so every word in the middle already counts
                # right and a budget guard refuses the one move that would
                # start unwinding it. The alef underneath is proof enough.
                for a7 in v["at"]:
                    for e7 in a7["els"]:
                        if not _alef6(e7):
                            continue      # an alef is narrow and tall
                        hit = _stands_on(wa, e7)
                        if hit is None:
                            continue
                        ovx, d7 = hit
                        if best is None or (d7, -ovx) < (best[0], -best[1]):
                            best = (d7, ovx, v)
            if best:
                _omove(wa, r, best[2])

    # A wasla sits on an ALEF, always. So when a word whose text opens with ٱ
    # owns the wasla mark, the alef directly beneath it is that word's — even
    # where the previous word's tail sweeps underneath and the split search,
    # which can only cut consecutive runs, had to hand it over.
    for r in owords:
        if "\u0671" not in r["w"]["uthmani"]:
            continue
        wl6 = [e for a in r["at"] for e in a["els"]
               if e.get("mark") == "wasla" and not e.get("mkpart")]
        if not wl6:
            continue
        # holding more waslas than the spelling allows means one of them is a
        # neighbour's; pulling an alef under it would steal a letter too
        if len(wl6) > r["w"]["uthmani"].count("\u0671"):
            continue
        own = [e for a in r["at"] for e in a["els"] if e["kind"] == "body"]
        for wa in wl6:
            wcx = (wa["x1"] + wa["x2"]) / 2
            if any(b["x1"] - 1.0 <= wcx <= b["x2"] + 1.0
                   and (b["x2"] - b["x1"]) <= 6.0
                   and (b["y2"] - b["y1"]) >= 6.0
                   and -1.5 <= b["y1"] - wa["y2"] <= 4.0 for b in own):
                continue                  # its own alef is already here
            best = None
            for v in owords:
                if v is r or v["ln"] != r["ln"]:
                    continue
                for a7 in v["at"]:
                    for e7 in a7["els"]:
                        if e7["kind"] != "body" or e7.get("mark"):
                            continue
                        w7 = e7["x2"] - e7["x1"]
                        if w7 > 6.0 or (e7["y2"] - e7["y1"]) < 6.0:
                            continue      # an alef is narrow and tall
                        if not (e7["x1"] - 1.0 <= wcx <= e7["x2"] + 1.0):
                            continue      # must stand under the wasla
                        d7 = e7["y1"] - wa["y2"]
                        if not (-1.5 <= d7 <= 4.0):
                            continue
                        if best is None or d7 < best[0]:
                            best = (d7, e7, v)
            if best:
                _, e7, v = best
                _omove(e7, v, r)

    # Budget and ink corroborating one another. Where a word holds a surplus
    # of one family and the word beside it is short of exactly that family,
    # the counts say a transfer is owed; the ink then says WHICH mark and
    # confirms the direction. Neither signal is trusted alone here — counts
    # cannot see a swap that balances on both sides, and geometry alone moves
    # marks that were never misplaced — so the move is made only where the two
    # agree, and the mark must sit nearer the word that is short of it.
    _WANTC = {
        "fatha": "\u064e", "kasra": "\u0650", "damma": "\u064f",
        "fathatan": "\u064b\u08f0", "kasratan": "\u064d\u08f2",
        "dammatan": "\u064c\u08f1", "sukun": "\u0652\u06e1",
        "shadda": "\u0651", "maddah": "\u0653\u06e4",
        "small-alef": "\u0670", "wasla": "\u0671",
        "small-waw": "\u06e5", "small-ya": "\u06e6\u06e7",
        "small-circle": "\u06df\u06e0",
        "hamza": "\u0623\u0625\u0624\u0626\u0654\u0655",
    }
    _ABOVE8 = {"fatha", "damma", "sukun", "shadda", "maddah", "small-alef",
               "wasla", "fathatan", "dammatan", "small-circle", "hamza"}

    def _txt8(r, fam):
        t = r["w"]["uthmani"]
        return sum(t.count(c) for c in _WANTC[fam])

    def _held8(r, fam):
        return [e for a in r["at"] for e in a["els"]
                if e.get("mark") == fam and not e.get("mkpart")
                and not e.get("standalone")]

    def _bbox8(r):
        bs = [e for a in r["at"] for e in a["els"] if e["kind"] == "body"]
        if not bs:
            return None
        return (min(e["x1"] for e in bs), max(e["x2"] for e in bs),
                min(e["y1"] for e in bs), max(e["y2"] for e in bs))

    _byln8 = {}
    for _r8 in owords:
        if _r8["ln"] is not None:
            _byln8.setdefault(_r8["ln"], []).append(_r8)

    # Decide every transfer against ONE frozen reading of the page, then apply
    # them together. Deciding and moving in the same sweep lets a corrected
    # pair feed the next comparison: on p508 a fatha returned to ءَاسِنٍۢ was
    # immediately handed on again, leaving that word with none and its
    # neighbour with two. A move is also capped at the smaller of the two
    # imbalances, so a pair can never overshoot into the opposite error.
    _plan8 = []
    _spent8 = {}
    for _ln8, _grp8 in ({} if os.environ.get("QSVG_NB") == "0"
                        else _byln8).items():
        for a8 in _grp8:
            for b8 in _grp8:
                if a8 is b8:
                    continue
                wa, wb = a8["w"], b8["w"]
                if wa["surah"] != wb["surah"] or wa["ayah"] != wb["ayah"]:
                    continue
                if abs(wa["pos"] - wb["pos"]) != 1:
                    continue          # only the word right beside it
                bb = _bbox8(b8)
                ba = _bbox8(a8)
                if bb is None or ba is None:
                    continue
                for fam in _WANTC:
                    # The slash families are not settled here. A fatha and a
                    # kasra are the same stroke, named later from where it sits
                    # and what the word's budget allows, so handing one across
                    # a word boundary re-opens that decision for BOTH words and
                    # the renaming can come back differently — on p508 a kasra
                    # that landed correctly under غَيْرِ left both words with
                    # the wrong fatha count. Families whose name is fixed by
                    # shape alone have no such second act.
                    if fam in ("fatha", "kasra", "fathatan", "kasratan"):
                        continue
                    held = _held8(a8, fam)
                    if len(held) - _txt8(a8, fam) <= 0:
                        continue      # no surplus to give
                    if _txt8(b8, fam) - len(_held8(b8, fam)) <= 0:
                        continue      # the neighbour is not short of it
                    best = None
                    for e in held:
                        cx = (e["x1"] + e["x2"]) / 2
                        cy = (e["y1"] + e["y2"]) / 2
                        da = max(ba[0] - cx, cx - ba[1], 0.0)
                        db = max(bb[0] - cx, cx - bb[1], 0.0)
                        if db >= da:
                            continue  # not nearer the word that wants it
                        gap = (bb[2] - cy) if fam in _ABOVE8 else (cy - bb[3])
                        if gap < -3.0 or gap > 16.0:
                            continue  # not drawn against that word's letters
                        if best is None or (db, gap) < best[0]:
                            best = ((db, gap), e)
                    if best:
                        # Cap by WORD, not by pair: a word short of one fatha
                        # has two neighbours, and letting each hand one over
                        # leaves it holding two. Give only what the source can
                        # spare and take only what the destination lacks.
                        give = _spent8.get(("give", id(a8), fam), 0)
                        take = _spent8.get(("take", id(b8), fam), 0)
                        if (give < len(held) - _txt8(a8, fam)
                                and take < _txt8(b8, fam) - len(_held8(b8, fam))):
                            _spent8[("give", id(a8), fam)] = give + 1
                            _spent8[("take", id(b8), fam)] = take + 1
                            _plan8.append((best[1], a8, b8))

    _moved8 = set()
    for e8, src8, dst8 in _plan8:
        if id(e8) in _moved8:
            continue                  # one piece of ink moves once
        _moved8.add(id(e8))
        _omove(e8, src8, dst8)

    # A hamza standing on its own — ء — is a LETTER, and the spelling wants
    # no mark for it. Riding on a carrier it is a mark. The outline is the
    # same, so only the position tells them apart: the mark sits clear above
    # or below its carrier, while the letter stands on the line in sequence.
    # This runs late on purpose. Demote it any earlier and the passes that
    # name hamzas simply put the mark back, and the word ends up holding one
    # more than its spelling allows.
    _CARRIER9 = "\u0623\u0625\u0624\u0626\u0654\u0655"
    for r in owords:
        txt = r["w"]["uthmani"]
        if "\u0621" not in txt or os.environ.get("QSVG_HZA") == "0":
            continue
        want = sum(txt.count(c) for c in _CARRIER9)
        els = [e for a in r["at"] for e in a["els"]]
        hz = [e for e in els if e.get("mark") == "hamza"
              and not e.get("mkpart")]
        if len(hz) <= want:
            continue
        bods = [e for e in els if e["kind"] == "body"]
        if not bods:
            continue
        top = min(e["y1"] for e in bods)
        bot = max(e["y2"] for e in bods)
        inline = [e for e in hz
                  if e["y1"] >= top - 1.5 and e["y2"] <= bot + 1.5]
        inline.sort(key=lambda e: -((e["x2"] - e["x1"]) * (e["y2"] - e["y1"])))
        for e in inline[:len(hz) - want]:
            # Anything welded to it was counting through it. Turning the
            # master into letter ink would take its twins out of the count
            # with it, so free them first — a kasratan welded to the ء still
            # belongs to the word.
            for m in (e.get("mkmembers") or []):
                m["mkpart"] = False
            e["mkmembers"] = []
            e["kind"] = "body"
            e["mark"] = None
            e["lab"] = "letter-hamza"

    def _eff_pieces(bods):
        # a stroke drawn over/inside a wider sibling (the kaf armature, the
        # second stroke of a lam-alef) is part of that letter, not a piece
        out = []
        for b in bods:
            wb = b["x2"] - b["x1"]
            hb = b["y2"] - b["y1"]
            # a stroke DRAWN OVER a letter (the kaf armature, a lam-alef's
            # second stroke) sits within its host's height; a piece that rises
            # ABOVE its host is a letter of its own — the silent alef standing
            # on the waw of ـوا۟ — and must keep counting as a piece.
            inside = any(o is not b
                         and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"])
                         >= 0.6 * wb
                         and (o["x2"] - o["x1"]) > wb
                         and hb <= (o["y2"] - o["y1"]) + 1.0
                         for o in bods)
            if not inside:
                out.append(b)
        return out

    # ... and that alef marks where the word STARTS. A piece reaching well to
    # the right of it is the PREVIOUS word's tail, swept underneath and handed
    # over by the consecutive-run split — but only give it back when that word
    # is provably short of pieces, so ordinary overlap is left alone.
    for r in owords:
        if "\u0671" not in r["w"]["uthmani"]:
            continue
        own = [e for a in r["at"] for e in a["els"] if e["kind"] == "body"]
        wl8 = [e for a in r["at"] for e in a["els"]
               if e.get("mark") == "wasla" and not e.get("mkpart")]
        alef = None
        for wa in wl8:
            wcx = (wa["x1"] + wa["x2"]) / 2
            for b in own:
                if (b["x1"] - 1.0 <= wcx <= b["x2"] + 1.0
                        and (b["x2"] - b["x1"]) <= 6.0
                        and -1.5 <= b["y1"] - wa["y2"] <= 4.0):
                    if alef is None or b["x2"] > alef["x2"]:
                        alef = b
        if alef is None:
            continue
        stray = [b for b in own if b is not alef and b["x2"] > alef["x2"] + 6.0]
        if not stray:
            continue
        prev = None
        for v in owords:
            if v is r or v["ln"] != r["ln"]:
                continue
            pb = [e for a in v["at"] for e in a["els"] if e["kind"] == "body"]
            if not pb or min(e["x1"] for e in pb) < alef["x2"] - 1.0:
                continue
            if len(_eff_pieces(pb)) >= v["nseg"]:
                continue                  # not short: leave its ink alone
            if prev is None or min(e["x1"] for e in pb) < prev[0]:
                prev = (min(e["x1"] for e in pb), v)
        if prev:
            pb2 = [e for a in prev[1]["at"] for e in a["els"]
                   if e["kind"] == "body"]
            px1 = min(e["x1"] for e in pb2)
            px2 = max(e["x2"] for e in pb2)
            for b in stray:
                # the tail must actually touch the word it is given back to
                if max(px1 - b["x2"], b["x1"] - px2, 0.0) > 4.0:
                    continue
                _omove(b, r, prev[1])

    # Iqlab tanween (ً ٌ ٍ followed by ۢ or ۭ): the nunation becomes a MEEM, so
    # this script does not double the stroke — it draws ONE vowel stroke plus a
    # small meem. Reading it as a plain vowel leaves the word a tanween short
    # and the meem filed as letter ink. The text names both.
    _IQTAN = {"\u064b": ("fathatan", "fatha", "\u064e"),
              "\u064c": ("dammatan", "damma", "\u064f"),
              "\u0650" if False else "\u064d": ("kasratan", "kasra", "\u0650")}
    for r in owords:
        txt = r["w"]["uthmani"]
        # tanween NAMING keys on uthmani (needed at idgham too); only the
        # MEEM rescue below keys on the print's text
        _ptx = r["w"].get("qpc") or txt
        _print_meem = "\u06e2" in _ptx or "\u06ed" in _ptx
        want = [_IQTAN[txt[i]] + (True,) for i in range(len(txt) - 1)
                if txt[i] in _IQTAN and txt[i + 1] in ("\u06e2", "\u06ed")]
        if _dktext_on():
            # The DK text writes the print's OWN encodings, which the composite
            # only implies: (a) the open tanween U+08F0-2 where quran.com
            # writes plain tanween + a phantom \u06ed \u2014 the phantom was what fired
            # this pass's stroke NAMING at all ~6,643 idgham/ikhfa sites, so
            # the open char must fire it too (no meem rescue: _print_meem is
            # false there); (b) true iqlab as PLAIN haraka + \u06e2/\u06ed \u2014 the budget
            # wants the plain name, so no renaming, but the meem rescue and
            # the demote of a shape-table tanween name still run (rename
            # False). Both triggers are gated so QSVG_DKTEXT=0 is untouched.
            _open = {"\u08f0": "\u064b", "\u08f1": "\u064c", "\u08f2": "\u064d"}
            _plain = {"\u064e": "\u064b", "\u064f": "\u064c", "\u0650": "\u064d"}
            want += [_IQTAN[_open[c]] + (True,) for c in txt if c in _open]
            want += [_IQTAN[_plain[txt[i]]] + (False,)
                     for i in range(len(txt) - 1)
                     if txt[i] in _plain and txt[i + 1] in ("\u06e2", "\u06ed")]
        if not want:
            continue
        els = [e for a in r["at"] for e in a["els"]]
        rx1 = min((e["x1"] for e in els if e["kind"] == "body"), default=None)
        if rx1 is None:
            continue
        for tan, base, plain_ch, rename in want:
            # The stroke may ALREADY carry the tanween name (a single-outline
            # dammatan glyph labels straight from the shape table). That must
            # not skip the meem rescue below: this print draws iqlab as ONE
            # haraka plus a small م (docs/defects/iqlab_notation.md), and an
            # early exit here left the م counted as a letter piece in 12 words.
            mv = next((e for e in els
                       if e.get("mark") == tan and not e.get("mkpart")), None)
            if mv is not None and not rename:
                # DK iqlab: the budget says PLAIN haraka, so a shape-table
                # tanween name on the single stroke is demoted to it (only a
                # lone outline — a welded pair is two real strokes, not this)
                if not mv.get("mkmembers"):
                    mv["mark"] = base
            if mv is None and not rename:
                # anchor on the plain stroke the budget names, without renaming
                fams = ("damma",) if base == "damma" else ("fatha", "kasra")
                pool = [e for e in els if e.get("mark") in fams
                        and not e.get("mkpart") and not e.get("mkmembers")]
                if not pool:
                    continue
                bods = [e for e in els if e["kind"] == "body"]
                mid = ((min(e["y1"] for e in bods) + max(e["y2"] for e in bods))
                       / 2 if bods else 0.0)
                below = tan == "kasratan"
                zone = [e for e in pool
                        if ((e["y1"] + e["y2"]) / 2 > mid) == below] or pool
                mv = min(zone, key=lambda e: abs((e["x1"] + e["x2"]) / 2 - rx1))
            if mv is None:
                if base == "damma":
                    pool = [e for e in els if e.get("mark") == "damma"
                            and not e.get("mkpart") and not e.get("mkmembers")]
                    spare = len(pool) - txt.count(plain_ch)
                else:
                    # the table names every slash by position alone, so a lone
                    # kasratan stroke can arrive called "fatha": pool both.
                    pool = [e for e in els if e.get("mark") in ("fatha", "kasra")
                            and not e.get("mkpart") and not e.get("mkmembers")]
                    spare = len(pool) - txt.count("\u064e") - txt.count("\u0650")
                if spare <= 0 or not pool:
                    continue                  # no stroke to spare: nothing to name
                bods = [e for e in els if e["kind"] == "body"]
                mid = ((min(e["y1"] for e in bods) + max(e["y2"] for e in bods)) / 2
                       if bods else 0.0)
                below = tan == "kasratan"
                zone = [e for e in pool
                        if ((e["y1"] + e["y2"]) / 2 > mid) == below] or pool
                # the tanween sits at the END of the word — nearest its left edge
                mv = min(zone, key=lambda e: abs((e["x1"] + e["x2"]) / 2 - rx1))
                mv["mark"] = tan
            # ... and its meem rides just beside it, usually filed as letter ink
            if not _print_meem:
                continue          # the PRINT draws no م here (items 23/24)
            if any(e.get("mark") == "meem-iqlab" and not e.get("mkpart")
                   for e in els):
                continue
            cx = (mv["x1"] + mv["x2"]) / 2
            cy = (mv["y1"] + mv["y2"]) / 2
            if os.environ.get("QSVG_DKDBG"):
                print("IQTAN-RESCUE %s tan=%s rename=%s mv=(%.0f,%.0f) cand=%s"
                      % (txt, tan, rename, cx, cy,
                         [(round(e["x1"]), round(e["y1"]),
                           round(e["x2"]-e["x1"],1), round(e["y2"]-e["y1"],1))
                          for e in els if not e.get("mark") and e is not mv]))
            best = None
            for e in els:
                if e.get("mark") or e is mv:
                    continue
                w2 = e["x2"] - e["x1"]; h2 = e["y2"] - e["y1"]
                if not (1.5 <= w2 <= 12.0 and 3.0 <= h2 <= 12.0):
                    continue
                if _human_letter_label(e):
                    continue
                d = abs((e["x1"] + e["x2"]) / 2 - cx) \
                    + abs((e["y1"] + e["y2"]) / 2 - cy)
                if d < 14.0 and (best is None or d < best[0]):
                    best = (d, e)
            if best:
                e2 = best[1]
                e2["kind"] = "mark"
                e2["mark"] = "meem-iqlab"
                e2.pop("lab", None)

    # Fathatan and kasratan are the SAME pair of strokes — only their position
    # tells them apart, and the table names them by shape alone. The text is
    # authoritative: rename by what the word actually carries, lowest strokes
    # first, then weld any pair still standing as two units into one mark.
    for r in owords:
        txt = r["w"]["uthmani"]
        want_ft = txt.count("\u064b") + txt.count("\u08f0")
        want_kt = txt.count("\u064d") + txt.count("\u08f2")
        if not (want_ft or want_kt):
            continue
        els = [e for a in r["at"] for e in a["els"]]
        have = [e for e in els if e.get("mark") in ("fathatan", "kasratan")
                and not e.get("mkpart")]
        if not have:
            continue
        if len(have) == want_ft + want_kt:
            have.sort(key=lambda e: -(e["y1"] + e["y2"]))    # lowest first
            for i, e in enumerate(have):
                nm = "kasratan" if i < want_kt else "fathatan"
                e["mark"] = nm
                for m in e.get("mkmembers", []):
                    m["mark"] = nm
            continue
        # more units than the text allows: the strokes of one tanween are
        # still standing apart — weld the closest same-named pair
        for nm, wn in (("fathatan", want_ft), ("kasratan", want_kt)):
            grp = [e for e in els if e.get("mark") == nm and not e.get("mkpart")]
            while len(grp) > wn and wn >= 0:
                best = None
                for i, a1 in enumerate(grp):
                    for b1 in grp[i + 1:]:
                        dx = abs((a1["x1"] + a1["x2"]) / 2
                                 - (b1["x1"] + b1["x2"]) / 2)
                        dy = abs((a1["y1"] + a1["y2"]) / 2
                                 - (b1["y1"] + b1["y2"]) / 2)
                        if dx < 8.0 and dy < 7.0 and (best is None
                                                      or dx + dy < best[0]):
                            best = (dx + dy, a1, b1)
                if not best:
                    break
                _, a1, b1 = best
                top, bot = (a1, b1) if a1["y1"] <= b1["y1"] else (b1, a1)
                bot["mkpart"] = True
                top["mkmembers"] = top.get("mkmembers", []) + [bot]
                grp.remove(bot)

    _DOTUNIT = {"dot": 1, "two-dots": 2, "three-dots": 3}

    # A letter's dot GROUP can be drawn as several pieces (the three dots of
    # sheen as a two-dot path plus a one-dot path). When a word holds more dot
    # pieces than its skeleton has dotted letters, but the right number of dot
    # UNITS, the touching pieces are one group: weld them into a single mark.
    def _dot_groups(txt):
        raw = _LETTER.findall(txt)
        sk = [(HAMZA_MAP[ch][0] if ch in HAMZA_MAP else ch, ch in HAMZA_MAP)
              for ch in raw]
        out = []
        for i, (ch, seat) in enumerate(sk):
            if seat or ch not in DOTS:
                continue
            if ch == "\u064a" and i == len(sk) - 1:
                continue
            out.append(_DOTUNIT.get(DOTS[ch][0], 0))
        return out

    for r in owords:
        groups = _dot_groups(r["w"]["uthmani"])
        pieces = [e for a in r["at"] for e in a["els"]
                  if e.get("mark") in _DOTUNIT and not e.get("mkpart")]
        if len(pieces) <= len(groups):
            continue
        units = sum(_DOTUNIT[e["mark"]] for e in pieces)
        if units != sum(groups) or 3 not in groups:
            continue                  # only a 3-dot group splits in this art
        best = None
        for i, a1 in enumerate(pieces):
            for b1 in pieces[i + 1:]:
                if _DOTUNIT[a1["mark"]] + _DOTUNIT[b1["mark"]] != 3:
                    continue
                dx = abs((a1["x1"] + a1["x2"]) / 2 - (b1["x1"] + b1["x2"]) / 2)
                dy = abs((a1["y1"] + a1["y2"]) / 2 - (b1["y1"] + b1["y2"]) / 2)
                if dx < 6.0 and dy < 6.0 and (best is None or dx + dy < best[0]):
                    best = (dx + dy, a1, b1)
        if best:
            _, a1, b1 = best
            top, bot = (a1, b1) if a1["y1"] <= b1["y1"] else (b1, a1)
            top["mark"] = "three-dots"
            bot["mark"] = "three-dots"
            bot["mkpart"] = True
            top["mkmembers"] = top.get("mkmembers", []) + [bot]

    # Containment repair: a letter piece drawn INSIDE another word's ink
    # belongs to that word. The tanween alef of a word like شَرًّۭا is drawn
    # tucked under its own body, so a neighbour whose cluster reached across
    # can hold it while the owner is left a segment short.
    def _bodies(r):
        return [e for a in r["at"] for e in a["els"] if e["kind"] == "body"]

    for v in owords:
        vb = _bodies(v)
        if len(vb) < 2:
            continue
        for e in list(vb):
            if e.get("lab") in ("letter", "letter-part", "letter-hamza"):
                pass                    # letter ink is exactly what may move
            for r in owords:
                if r is v or r["ln"] is None or v["ln"] is None \
                        or r["ln"] != v["ln"]:
                    continue
                rb = _bodies(r)
                if not rb or len(rb) >= r["nseg"]:
                    continue            # only a word short of pieces claims
                rx1 = min(x["x1"] for x in rb)
                rx2 = max(x["x2"] for x in rb)
                if not (rx1 - 0.5 <= e["x1"] and e["x2"] <= rx2 + 0.5):
                    continue            # must be strictly inside its ink
                others = [x for x in vb if x is not e]
                if not others:
                    continue
                ox1 = min(x["x1"] for x in others)
                ox2 = max(x["x2"] for x in others)
                if ox1 - 0.5 <= e["x1"] and e["x2"] <= ox2 + 0.5:
                    continue            # also inside its holder: ambiguous
                _omove(e, v, r)
                vb.remove(e)
                break

    # Segment budgets: Arabic joining rules fix how many disconnected letter
    # groups a word is drawn with. A word holding MORE pieces than its text
    # allows, next to one holding fewer, has taken its neighbour's ligature —
    # hand back the piece that touches the short word's ink.
    for _round in range(3):
        moved_any = False
        for v in owords:
            vb0 = [e for a in v["at"] for e in a["els"] if e["kind"] == "body"]
            vb = _eff_pieces(vb0)
            if len(vb) <= v["nseg"]:
                continue
            for r in owords:
                if r is v or r["ln"] is None or v["ln"] is None \
                        or abs(r["ln"] - v["ln"]) > 1:
                    continue
                rb0 = [e for a in r["at"] for e in a["els"]
                       if e["kind"] == "body"]
                rb = _eff_pieces(rb0)
                if not rb or len(rb) >= r["nseg"]:
                    continue
                rx1 = min(e["x1"] for e in rb0)
                rx2 = max(e["x2"] for e in rb0)
                # only the piece at the very edge facing the short word can
                # be its ligature — an interior piece is the donor's own
                # which side the short word lies on — by centre, since two
                # words' ink commonly overlaps where a tail sweeps across
                left = ((rx1 + rx2) / 2
                        < (min(e["x1"] for e in vb)
                           + max(e["x2"] for e in vb)) / 2)
                edge = (min(vb, key=lambda e: e["x1"]) if left
                        else max(vb, key=lambda e: e["x2"]))
                best = None
                for e in vb:
                    if left and e["x1"] > edge["x1"] + 1.0:
                        continue
                    if not left and e["x2"] < edge["x2"] - 1.0:
                        continue
                    gap = max(rx1 - e["x2"], e["x1"] - rx2, 0.0)
                    if gap > _SEG_GAP:
                        continue          # must be near the short word's ink
                    if r["ln"] != v["ln"]:
                        # across a line break the ink must sit clearly in the
                        # receiver's band, not merely near its column
                        cy = (e["y1"] + e["y2"]) / 2
                        if not (r["top"] - 2.0 <= cy <= r["bot"] + 2.0):
                            continue
                        if v["top"] - 2.0 <= cy <= v["bot"] + 2.0:
                            continue      # equally at home in its holder
                    rest = [x for x in vb if x is not e]
                    if len(rest) < v["nseg"]:
                        continue          # never fall below the donor's own
                    if best is None or gap < best[0]:
                        best = (gap, e)
                if best is None:
                    continue
                _omove(best[1], v, r)
                vb.remove(best[1])
                moved_any = True
                if len(vb) <= v["nseg"]:
                    break
        if not moved_any:
            break

    # Dot budgets: a word's skeleton says exactly how many letter dots it
    # carries, and dots are drawn wherever the calligraphy has room — the two
    # dots of an initial ya can sit over the PREVIOUS word's raa. A word that
    # holds more dot units than its letters can own gives the surplus to a
    # neighbour that is short, when the ink is within reach of that neighbour.
    # Ink drawn in another line's territory. A word can steal from the line
    # above or below it, not just from its neighbour along the line, and
    # nothing here could see that: once a word absorbs a stolen letter, the
    # letter joins its outline and the word looks close to ink it should never
    # have held. Measuring the ink against the word's OTHER letters exposes it.
    # The victim is not required to stand over the ink either — robbed of a
    # letter, its span stops short of the very thing it is missing.
    _CROSS_X = 8.0          # about one letter's reach beside the victim's ink
    _byln5 = {}
    for _r5 in owords:
        if _r5["ln"] is not None:
            _byln5.setdefault(_r5["ln"], []).append(_r5)

    def _span5(bods):
        return (min(b["x1"] for b in bods), max(b["x2"] for b in bods),
                min(b["y1"] for b in bods), max(b["y2"] for b in bods))

    _plan5 = []
    for r in owords:
        if r["ln"] is None:
            continue
        els = [e for a in r["at"] for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        if len(bods) < 2:
            continue
        for e in els:
            if e.get("mkpart") or e.get("standalone"):
                continue
            rest = [b for b in bods if b is not e]
            if not rest:
                continue
            _, _, ry1, ry2 = _span5(rest)
            cx = (e["x1"] + e["x2"]) / 2
            cy = (e["y1"] + e["y2"]) / 2
            own = max(ry1 - cy, cy - ry2, 0.0)
            if own <= 8.0:
                continue          # sitting with its own word, as ink should
            best = None
            for dl in (-1, 1):
                for v in _byln5.get(r["ln"] + dl, ()):
                    vb = [b for a in v["at"] for b in a["els"]
                          if b["kind"] == "body"]
                    if not vb:
                        continue
                    vx1, vx2, vy1, vy2 = _span5(vb)
                    xd = max(vx1 - e["x2"], e["x1"] - vx2, 0.0)
                    if xd > _CROSS_X:
                        continue
                    d = max(vy1 - cy, cy - vy2, 0.0)
                    if best is None or (d + xd) < (best[0] + best[1]):
                        best = (d, xd, v)
            if best is None:
                continue
            d, xd, v = best
            if d + 5.0 >= own:
                continue          # not decisively the other line's
            if e["kind"] == "body":
                # the victim must actually be short of a letter piece
                vb = [b for a in v["at"] for b in a["els"]
                      if b["kind"] == "body"]
                if len(_eff_pieces(vb)) >= v["nseg"]:
                    continue
            else:
                fam = e.get("mark")
                if fam not in _WANTC:
                    continue
                # Not the slash families. A fatha and a kasra are one stroke
                # named later from where it sits and what the word's budget
                # allows, so carrying one to another line re-opens that
                # decision for both words and the renaming can come back
                # differently — p446 and p576 each lost two words that way.
                if fam in ("fatha", "kasra", "fathatan", "kasratan"):
                    continue
                txt_r = r["w"]["uthmani"]
                have_r = sum(1 for q in els if q.get("mark") == fam
                             and not q.get("mkpart"))
                if have_r <= sum(txt_r.count(c) for c in _WANTC[fam]):
                    continue      # the holder is not carrying a surplus
            _plan5.append((e, r, v))

    _done5 = set()
    for e5, src5, dst5 in _plan5:
        if id(e5) in _done5:
            continue
        _done5.add(id(e5))
        e5["line"] = dst5["ln"]
        _omove(e5, src5, dst5)

    def _dots_want(txt):
        raw = _LETTER.findall(txt)
        # a hamza-carrying seat (ئ ؤ أ إ) is drawn WITHOUT its letter's dots
        sk = [(HAMZA_MAP[ch][0] if ch in HAMZA_MAP else ch, ch in HAMZA_MAP)
              for ch in raw]
        n = 0
        for i, (ch, seat) in enumerate(sk):
            if seat or ch not in DOTS:
                continue
            if ch == "\u064a" and i == len(sk) - 1:
                continue              # a final ya is drawn undotted here
            n += _DOTUNIT.get(DOTS[ch][0], 0)
        return n

    def _dots_have(r):
        return sum(_DOTUNIT[e["mark"]] for a in r["at"] for e in a["els"]
                   if e.get("mark") in _DOTUNIT and not e.get("mkpart"))

    for _round in range(2):
        moved_any = False
        for r in owords:
            want_r = _dots_want(r["w"]["uthmani"])
            have_r = _dots_have(r)
            if have_r <= want_r:
                continue
            mine = [e for a in r["at"] for e in a["els"]
                    if e.get("mark") in _DOTUNIT and not e.get("mkpart")]
            for v in owords:
                if v is r or v["ln"] is None or r["ln"] is None \
                        or abs(v["ln"] - r["ln"]) > 1:
                    continue
                want_v = _dots_want(v["w"]["uthmani"])
                have_v = _dots_have(v)
                if have_v >= want_v:
                    continue
                vx1, vx2 = _ospan(v)
                rx1, rx2 = _ospan(r)
                cands = []
                for e in mine:
                    u = _DOTUNIT[e["mark"]]
                    if have_r - u < want_r or have_v + u > want_v:
                        continue          # the move must fix, not overshoot
                    cx = (e["x1"] + e["x2"]) / 2
                    if not (vx1 - _DOT_REACH < cx < vx2 + _DOT_REACH):
                        continue          # must sit over the receiver's ink
                    cy = (e["y1"] + e["y2"]) / 2
                    if not (v["top"] - 9.0 < cy < v["bot"] + 9.0):
                        continue          # ... and at its writing level
                    # prefer ink the donor cannot plausibly own: nearer the
                    # receiver's centre than the donor's
                    dv = abs(cx - (vx1 + vx2) / 2)
                    dr = abs(cx - (rx1 + rx2) / 2)
                    cands.append((dv - dr, dv, e))
                if not cands:
                    continue
                cands.sort(key=lambda t: (t[0], t[1]))
                _, _, mv = cands[0]
                _omove(mv, r, v)
                mine.remove(mv)
                mv["line"] = v["ln"]
                have_r -= _DOTUNIT[mv["mark"]]
                moved_any = True
                if have_r <= want_r:
                    break
        if not moved_any:
            break

    # Letter-ink rescue: an UNLABELED mark of letter size is stranded letter
    # ink — a ن bowl classified as a mark and re-lined onto a neighbouring
    # line's word. Hand it, as a body, to the word (same or adjacent line,
    # x-overlapping) whose QCF width ratio improves most; its dot rides along.
    _qall = qcf_widths()

    def _wlog(r, extra=None, drop=()):
        els = [e for a in r["at"] for e in a["els"] if e not in drop]
        if extra is not None:
            els = els + [extra]
        bods = [e for e in els if e["kind"] == "body"
                or e.get("mark") in ("small-ya", "small-waw")
                or e is extra]          # a rescued piece counts as letter ink
        if not bods:
            return None
        span = max(e["x2"] for e in bods) - min(e["x1"] for e in bods)
        qw = _qall.get("%d:%d:%d" % (r["w"]["surah"], r["w"]["ayah"],
                                     r["w"]["pos"]))
        if not qw or any(m in r["w"]["uthmani"] for m in "\u06de\u06e9"):
            return None
        rs = [y for y in owords if y["ln"] == r["ln"]]
        ta = tq = 0.0
        for y in rs:
            sp = _ospan(y)
            ta += sp[1] - sp[0]
            tq += _qall.get("%d:%d:%d" % (y["w"]["surah"], y["w"]["ayah"],
                                          y["w"]["pos"]), 0)
        if not tq or not ta:
            return None
        return abs(math.log(max(span / (qw / tq * ta), 1e-3)))

    for r in owords:
        strays = [e for a in r["at"] for e in a["els"]
                  if e["kind"] == "mark" and not e.get("mark")
                  and not e.get("mkpart")
                  and max(e["x2"] - e["x1"], e["y2"] - e["y1"]) >= 7.5]
        if strays and os.environ.get("QSVG_DBG_RESC"):
            print("RESC strays in %s: %s" % (r["w"]["uthmani"],
                  ["x%.0f..%.0f y%.0f..%.0f" % (e["x1"], e["x2"], e["y1"], e["y2"])
                   for e in strays]), file=sys.stderr)
        for e in strays:
            riders = [x for a in r["at"] for x in a["els"]
                      if x is not e and x["kind"] == "mark"
                      and not x.get("mkpart")
                      and (not x.get("mark") or x.get("mark") in
                           ("dot", "two-dots", "three-dots"))
                      and x["x1"] > e["x1"] - 2.5 and x["x2"] < e["x2"] + 2.5
                      and x["y1"] > e["y1"] - 6.0 and x["y2"] < e["y2"] + 6.0]
            cur = _wlog(r, drop=[e] + riders)
            cur0 = _wlog(r)
            best = None
            for v in owords:
                if v is r or v["ln"] is None or r["ln"] is None \
                        or abs(v["ln"] - r["ln"]) > 1:
                    continue
                vx1, vx2 = _ospan(v)
                cx = (e["x1"] + e["x2"]) / 2
                # a word missing its FINAL letter has a span that stops short
                # on the left — reach further in the reading direction
                if not (vx1 - 12.0 < cx < vx2 + 4.0):
                    continue
                w_now = _wlog(v)
                w_with = _wlog(v, extra=e)
                if w_now is None or w_with is None:
                    continue
                gain = w_now - w_with
                if os.environ.get("QSVG_DBG_RESC"):
                    print("RESC cand v=%s gain=%.2f now=%.2f with=%.2f"
                          % (v["w"]["uthmani"], gain, w_now, w_with),
                          file=sys.stderr)
                if gain > 0.2 and (best is None or gain > best[0]):
                    best = (gain, v)
            if best is None:
                continue
            hold_gain = 0.0 if cur is None or cur0 is None else cur0 - cur
            if best[0] + hold_gain <= 0.25:
                continue
            v = best[1]
            e["kind"] = "body"
            e["line"] = v["ln"]
            _omove(e, r, v)
            for x in riders:
                x["line"] = v["ln"]
                _omove(x, r, v)

    # Iqlab meem recovery: the small م of نۢ shares its outline with letter
    # fragments, so the table can force it into the NEXT word as body ink.
    # The text names its owner: a word with a ۢ budget and no meem-iqlab
    # claims a small م-sized body piece standing at its left edge.
    for r in owords:
        # only ۢ (U+06E2) is drawn as a separate small م in this art; the
        # low ۭ of iqlab tanween leaves no standalone glyph to claim
        want_m = r["w"]["uthmani"].count("\u06e2")
        _ptx2 = r["w"].get("qpc") or r["w"]["uthmani"]
        if not want_m or "\u06e2" not in _ptx2:
            continue          # the PRINT draws no م here (items 23/24)
        have_m = sum(1 for a in r["at"] for e in a["els"]
                     if e.get("mark") == "meem-iqlab" and not e.get("mkpart"))
        if have_m >= want_m:
            continue
        rx1, rx2 = _ospan(r)
        best = None
        for v in owords:
            # v is r is allowed: the small م can already be OWNED by the word,
            # drawn as one of its body pieces (p136 أَلِيمٌۢ) — the deficit and
            # the donor-need guard below make self-claiming safe: the word must
            # still keep enough bodies for its letter segments.
            if v["ln"] is None or r["ln"] is None \
                    or abs(v["ln"] - r["ln"]) > 1:
                continue
            for a in v["at"]:
                for e in a["els"]:
                    if e["kind"] != "body" or e.get("mark"):
                        continue
                    w2 = e["x2"] - e["x1"]; h2 = e["y2"] - e["y1"]
                    if os.environ.get("QSVG_DBG_MEEM") and abs(e["x1"] - 291) < 3 \
                            and r["w"]["uthmani"].startswith("\u0645"):
                        print("MEEM-CAND x%.0f..%.0f y%.0f..%.0f w%.1f h%.1f donor=%s"
                              % (e["x1"], e["x2"], e["y1"], e["y2"], w2, h2,
                                 v["w"]["uthmani"]), file=sys.stderr)
                    if not (2.0 <= w2 <= 6.0 and 5.0 <= h2 <= 12.0):
                        continue
                    if _human_letter_label(e):
                        continue
                    cx = (e["x1"] + e["x2"]) / 2
                    d = abs(cx - rx1)          # iqlab م trails at the LEFT edge
                    if d > 8.0:
                        continue
                    # ... at its word's writing level or riding just above it
                    # (ۢ is a superscript م), never a stroke from another line
                    # (the ك armature of the line above sits far higher)
                    rb = [x for a2 in r["at"] for x in a2["els"]
                          if x["kind"] == "body"]
                    if rb:
                        ry1 = min(x["y1"] for x in rb)
                        ry2 = max(x["y2"] for x in rb)
                        cy = (e["y1"] + e["y2"]) / 2
                        if not (ry1 - 12.0 <= cy <= ry2 + 2.0):
                            if os.environ.get("QSVG_DBG_MEEM"):
                                print("MEEM-YREJ cy=%.0f ry=%.0f..%.0f w=%s"
                                      % (cy, ry1, ry2, r["w"]["uthmani"]),
                                      file=sys.stderr)
                            continue
                    # the donor must not need the piece as a letter segment
                    vb = [x for a2 in v["at"] for x in a2["els"]
                          if x["kind"] == "body" and x is not e]
                    if len(vb) < max(1, v["nseg"]):
                        if os.environ.get("QSVG_DBG_MEEM"):
                            print("MEEM-REJ nseg donor=%s piece x%.0f nseg=%d nb=%d"
                                  % (v["w"]["uthmani"], e["x1"], v["nseg"],
                                     len(vb)), file=sys.stderr)
                        continue
                    if best is None or d < best[0]:
                        best = (d, e, v)
        if os.environ.get("QSVG_DBG_MEEM"):
            print("MEEM want=%d have=%d word=%s rx1=%.0f best=%s"
                  % (want_m, have_m, r["w"]["uthmani"], rx1,
                     "None" if best is None else "d=%.1f x%.0f..%.0f y%.0f..%.0f"
                     % (best[0], best[1]["x1"], best[1]["x2"],
                        best[1]["y1"], best[1]["y2"])), file=sys.stderr)
        if best:
            _, e, v = best
            e["kind"] = "mark"
            e["mark"] = "meem-iqlab"
            e.pop("lab", None)
            e["line"] = r["ln"]
            _omove(e, v, r)

    # Unassigned strays: a mark sitting in no word joins an adjacent word that
    # still has budget for its family — including the letter-dot budget derived
    # from the word's own skeleton.
    _DOTU = {"dot": 1, "two-dots": 2, "three-dots": 3}

    def _dot_want(txt):
        raw = _LETTER.findall(txt)
        sk = [(HAMZA_MAP[ch][0] if ch in HAMZA_MAP else ch, ch in HAMZA_MAP)
              for ch in raw]
        n = 0
        for i, (ch, seat) in enumerate(sk):
            if seat or ch not in DOTS:
                continue
            if ch == "\u064a" and i == len(sk) - 1:
                continue
            n += _DOTU.get(DOTS[ch][0], 0)
        return n

    free = []
    for w0, at0 in assignment:
        if w0:
            continue
        for a0 in at0:
            for e in a0["els"]:
                if e["kind"] == "mark" and not e.get("mkpart") \
                        and not e.get("offcanvas") and not e.get("standalone"):
                    free.append((e, a0))
    for e, a0 in free:
        cx = (e["x1"] + e["x2"]) / 2
        fam = _OFAM.get(e.get("mark"))
        dotu = _DOTU.get(e.get("mark"), 0)
        best = None
        for r in owords:
            if r["ln"] is None or e.get("line") is None \
                    or abs(r["ln"] - e["line"]) > 1:
                continue
            rx1, rx2 = _ospan(r)
            if not (rx1 - 2.0 < cx < rx2 + 2.0):
                continue
            els_r = [x for a in r["at"] for x in a["els"]]
            need = False
            if fam:
                have = sum(1 for x in els_r
                           if _OFAM.get(x.get("mark")) == fam
                           and not x.get("mkpart"))
                need = have < r["caps"].get(fam, 0)
            elif dotu:
                have = sum(_DOTU.get(x.get("mark"), 0) for x in els_r
                           if not x.get("mkpart"))
                need = have + dotu <= _dot_want(r["w"]["uthmani"])
            if not need:
                continue
            d = abs((rx1 + rx2) / 2 - cx)
            if best is None or d < best[0]:
                best = (d, r)
        if best is None:
            continue
        r = best[1]
        if e in a0["els"]:
            a0["els"].remove(e)
            for m in e.get("mkmembers", []):
                if m in a0["els"]:
                    a0["els"].remove(m)
            tgt = min(r["at"], key=lambda a2: min(abs((x["x1"] + x["x2"]) / 2
                      - (e["x1"] + e["x2"]) / 2) for x in a2["els"])
                      if a2["els"] else 1e9)
            tgt["els"].append(e)
            tgt["els"].extend(e.get("mkmembers", []))

    # Re-run tanween pairing/welding: the repair layers may have reunited a
    # pair that was split at first-weld time.
    for r in owords:
        txt = r["w"]["uthmani"]
        els_r = [e for a in r["at"] for e in a["els"]]
        for single, tan, chars_s, chars_t in (
                ("damma", "dammatan", "\u064f", "\u064c\u08f1"),
                ("fatha", "fathatan", "\u064e", "\u064b\u08f0"),
                ("kasra", "kasratan", "\u0650", "\u064d\u08f2")):
            want_t = sum(txt.count(ch) for ch in chars_t)
            if not want_t:
                continue
            have_t = sum(1 for e in els_r if e.get("mark") == tan
                         and not e.get("mkpart"))
            singles = [e for e in els_r if e.get("mark") == single
                       and not e.get("mkpart")]
            want_s = sum(txt.count(ch) for ch in chars_s)
            # a pair drawn with mixed labels: lone tan-master absorbs the
            # nearest spare single as its part
            tans = [e for e in els_r if e.get("mark") == tan
                    and not e.get("mkpart") and not e.get("mkmembers")]
            for tm in tans:
                if len(singles) - want_s < 1:
                    break
                near = [e for e in singles
                        if abs((e["x1"] + e["x2"]) / 2
                               - (tm["x1"] + tm["x2"]) / 2) < 8.0
                        and abs((e["y1"] + e["y2"]) / 2
                                - (tm["y1"] + tm["y2"]) / 2) < 7.0]
                if not near:
                    continue
                pt = min(near, key=lambda e: abs((e["x1"] + e["x2"]) / 2
                                                 - (tm["x1"] + tm["x2"]) / 2))
                pt["mark"] = tan
                pt["mkpart"] = True
                tm.setdefault("mkmembers", []).append(pt)
                singles.remove(pt)
            while len(singles) - want_s >= 2 and have_t < want_t:
                best = None
                for i2, a2 in enumerate(singles):
                    for b2 in singles[i2 + 1:]:
                        dx = abs((a2["x1"] + a2["x2"]) / 2
                                 - (b2["x1"] + b2["x2"]) / 2)
                        dy = abs((a2["y1"] + a2["y2"]) / 2
                                 - (b2["y1"] + b2["y2"]) / 2)
                        if dx < 8.0 and dy < 7.0 and (best is None
                                                      or dx + dy < best[0]):
                            best = (dx + dy, a2, b2)
                if not best:
                    break
                _, a2, b2 = best
                top, bot2 = (a2, b2) if (a2["y1"] + a2["y2"]) \
                    <= (b2["y1"] + b2["y2"]) else (b2, a2)
                top["mark"] = tan
                bot2["mark"] = tan
                bot2["mkpart"] = True
                top.setdefault("mkmembers", []).append(bot2)
                singles.remove(a2)
                singles.remove(b2)
                have_t += 1
            # the art's tanween halves are not always labeled alike: a spare
            # single (or a duplicate tan half) hugging a tan master is that
            # master's second curl
            masters = [e for e in els_r if e.get("mark") == tan
                       and not e.get("mkpart")]
            def _near(a3, b3):
                return (abs((a3["x1"] + a3["x2"]) / 2
                            - (b3["x1"] + b3["x2"]) / 2) < 8.0
                        and abs((a3["y1"] + a3["y2"]) / 2
                                - (b3["y1"] + b3["y2"]) / 2) < 7.0)
            while len(masters) > want_t:
                pair = next(((m1, m2) for i3, m1 in enumerate(masters)
                             for m2 in masters[i3 + 1:] if _near(m1, m2)), None)
                if not pair:
                    break
                m1, m2 = pair
                m2["mark"] = tan
                m2["mkpart"] = True
                m1.setdefault("mkmembers", []).append(m2)
                masters.remove(m2)
            while len(singles) > want_s and masters:
                pair = next(((sgl, m1) for sgl in singles for m1 in masters
                             if not m1.get("mkmembers") and _near(sgl, m1)),
                            None)
                if not pair:
                    break
                sgl, m1 = pair
                sgl["mark"] = tan
                sgl["mkpart"] = True
                m1.setdefault("mkmembers", []).append(sgl)
                singles.remove(sgl)
            # kasratan/fathatan strokes carry whatever slash name the position
            # pass guessed: weld two spare slash strokes of any name
            if tan in ("fathatan", "kasratan") and have_t < want_t:
                other = "kasra" if single == "fatha" else "fatha"
                spare2 = [e for e in els_r
                          if e.get("mark") in (single, other)
                          and not e.get("mkpart")]
                nsl = (txt.count("َ") + txt.count("ِ"))
                while len(spare2) - nsl >= 2 and have_t < want_t:
                    pair = next(((s1, s2) for i3, s1 in enumerate(spare2)
                                 for s2 in spare2[i3 + 1:] if _near(s1, s2)),
                                None)
                    if not pair:
                        break
                    s1, s2 = pair
                    top2 = s1 if (s1["y1"] + s1["y2"]) <= (s2["y1"] + s2["y2"]) \
                        else s2
                    bot3 = s2 if top2 is s1 else s1
                    top2["mark"] = tan
                    bot3["mark"] = tan
                    bot3["mkpart"] = True
                    top2.setdefault("mkmembers", []).append(bot3)
                    spare2.remove(s1)
                    spare2.remove(s2)
                    have_t += 1

    # a stray tanween half that drifted onto the previous word snaps back to
    # the master it hugs on the neighbouring word
    for ri, r in enumerate(owords):
        txt = r["w"]["uthmani"]
        for singles_n, tans_n, chars_s, chars_t in (
                (("damma",), ("dammatan",), "ُ", "ٌࣱ"),
                (("fatha", "kasra"), ("fathatan", "kasratan"),
                 "َِ", "ًࣰٍࣲ")):
            fam = singles_n + tans_n
            els_r = [e for a in r["at"] for e in a["els"]]
            have = sum(1 for e in els_r
                       if e.get("mark") in fam
                       and not e.get("mkpart"))
            want = (sum(txt.count(ch) for ch in chars_s)
                    + sum(txt.count(ch) for ch in chars_t))
            if have <= want:
                continue
            spare3 = [e for e in els_r if e.get("mark") in fam
                      and not e.get("mkpart")]
            for nb in owords:
                if nb is r or have <= want:
                    continue
                nb_els = [e for a in nb["at"] for e in a["els"]]
                nb_txt = nb["w"]["uthmani"]
                nb_want_t = sum(nb_txt.count(ch) for ch in chars_t)
                nb_have_t = sum(1 for e in nb_els if e.get("mark") in tans_n
                                and not e.get("mkpart"))
                for m1 in nb_els:
                    if m1.get("mkpart") or m1.get("mkmembers"):
                        continue
                    if m1.get("mark") in tans_n:
                        tan = m1["mark"]
                    elif m1.get("mark") in singles_n \
                            and nb_want_t > nb_have_t:
                        # the tanween the neighbour's text actually wants
                        tan = next((t for t, ch2 in zip(
                            tans_n, ("ًࣰ", "ٍࣲ") if len(tans_n) == 2
                            else ("ٌࣱ",))
                            if any(c in nb_txt for c in ch2)), None)
                        if tan is None:
                            continue
                    else:
                        continue
                    hit = next((e for e in spare3
                                if abs((e["x1"] + e["x2"]) / 2
                                       - (m1["x1"] + m1["x2"]) / 2) < 8.0
                                and abs((e["y1"] + e["y2"]) / 2
                                        - (m1["y1"] + m1["y2"]) / 2) < 7.0),
                               None)
                    if hit is None:
                        continue
                    for a0 in r["at"]:
                        if hit in a0["els"]:
                            a0["els"].remove(hit)
                    m1["mark"] = tan
                    hit["mark"] = tan
                    hit["mkpart"] = True
                    m1.setdefault("mkmembers", []).append(hit)
                    nb["at"][0]["els"].append(hit)
                    spare3.remove(hit)
                    have -= 1

    # The ۩ sign's outline on p589 differs from the table's confirmed signature
    # and classify read it as a letter body inside يَسْجُدُونَ (a 4th piece
    # where the joining rules allow 3). The TEXT says the word carries ۩; take
    # the count from the text and the identity from the geometry — the ۩ is
    # ~7.9x11.1 with nested contours, unlike any letter this size — and hand it
    # back to the standalone-sign ejection below. (Policy P5: the sajdah sign
    # is never any word's mark or letter.)
    if os.environ.get("QSVG_SAJ", "1") == "1":
        for _ws, _ats in assignment:
            if not _ws or "۩" not in _ws["uthmani"]:
                continue
            for _as in _ats:
                for _es in _as["els"]:
                    if _es["kind"] != "body" or _es.get("mark") \
                            or _es.get("lab"):
                        continue
                    _w9 = _es["x2"] - _es["x1"]
                    _h9 = _es["y2"] - _es["y1"]
                    if 6.5 <= _w9 <= 9.5 and 9.8 <= _h9 <= 12.5 \
                            and len(_es.get("contours", [])) >= 3:
                        _es["kind"] = "mark"
                        _es["mark"] = "sajdah"
                        _es["lab"] = "sajdah"

    # Standalone signs (hizb / rub markers, division stars) belong to no word:
    # eject them and stamp the ayah whose polygon holds them
    _rects_sa = []
    if os.path.exists(polys_path):
        for _pl in json.load(open(polys_path)):
            for _m in _RECT.finditer(_pl.get("polygon", "")):
                _x1, _y1, _x2, _y2 = (float(_m.group(1)), float(_m.group(2)),
                                      float(_m.group(3)), float(_m.group(4)))
                _rects_sa.append((min(_x1, _x2), min(_y1, _y2), max(_x1, _x2),
                                  max(_y1, _y2), _pl["surahNumber"],
                                  _pl["ayahNumber"]))

    def _ayah_at(x, y):
        best = None
        for (rx1, ry1, rx2, ry2, su, ay) in _rects_sa:
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                return su, ay
            d = max(rx1 - x, x - rx2, 0) + max(ry1 - y, y - ry2, 0)
            if best is None or d < best[0]:
                best = (d, su, ay)
        return (best[1], best[2]) if best else (None, None)

    ejected = {}
    bars = []
    for w, at in assignment:
        if not w:
            continue
        for a in at:
            for e in list(a["els"]):
                # the sajdah overline is a hairline bar: variable length, all
                # but fixed height. It belongs to the sajdah sign, never to a
                # word — collect it even though it carries no mark name.
                # ... and a later mark-namer can have called the hairline a
                # vowel (p272: the bar over 16:48-49 renamed kasra and counted
                # in ظِلَـٰلُهُۥ's budget) — the geometry says bar, so the name
                # is dropped and the bar is ejected all the same.
                is_bar = (e.get("lab") == "sajdah" and not e.get("mkpart")
                          and (not e.get("mark")
                               or (os.environ.get("QSVG_SAJ", "1") == "1"
                                   and e.get("mark") != "sajdah"
                                   and (e["y2"] - e["y1"]) < 2.5
                                   <= (e["x2"] - e["x1"]))))
                if is_bar:
                    e.pop("mark", None)
                    a["els"].remove(e)
                    bars.append(e)
                    continue
                if e.get("mark") in ("hizb", "sajdah") and not e.get("mkpart"):
                    grp = [e] + [m for m in e.get("mkmembers", []) if m in a["els"]]
                    for x in grp:
                        a["els"].remove(x)
                    su, ay = _ayah_at((e["x1"] + e["x2"]) / 2,
                                      (e["y1"] + e["y2"]) / 2)
                    key = (e["mark"], su, ay)
                    for x in grp:
                        x["standalone"] = (su, ay)
                    ejected.setdefault(key, []).extend(grp)
    # each bar joins the nearest sajdah sign on the page; with none to join it
    # still stands on its own rather than inside a word
    for e in bars:
        cx = (e["x1"] + e["x2"]) / 2
        cy = (e["y1"] + e["y2"]) / 2
        best = None
        for key, grp in ejected.items():
            if key[0] != "sajdah":
                continue
            gx = sum((x["x1"] + x["x2"]) / 2 for x in grp) / len(grp)
            gy = sum((x["y1"] + x["y2"]) / 2 for x in grp) / len(grp)
            d = abs(cx - gx) + abs(cy - gy)
            if best is None or d < best[0]:
                best = (d, key)
        if best is not None:
            key = best[1]
            e["standalone"] = (key[1], key[2])
            ejected[key].append(e)
        else:
            su, ay = _ayah_at(cx, cy)
            e["standalone"] = (su, ay)
            ejected.setdefault(("sajdah", su, ay), []).append(e)
    # Taxonomy phase 1 (decision 7): the sajdah compound splits by NAME into
    # its two components — `sajdah-line` (the hairline overline, which the
    # appendix says identifies the word making prostration) and `sajdah-sign`
    # (the ۩ mihrab glyph). Grouping is untouched (Policy P5 still holds one
    # standalone group); only the per-element data-mark changes. The bar test
    # is the same ratio classify() uses: hairline height, many times wider.
    if os.environ.get("QSVG_TAX", "1") == "1":
        for (lab, su, ay), grp in ejected.items():
            if lab != "sajdah":
                continue
            for e in grp:
                _bh = e["y2"] - e["y1"]
                _bw = e["x2"] - e["x1"]
                e["mark"] = ("sajdah-line" if _bh < 2.5 and _bw >= 8.0
                             else "sajdah-sign")
            # ONE overline per site: p480's hairline is digitized as two
            # segments and both were masters — 16 lines over 15 signs. The
            # segments weld, rightmost (first in reading order) counting.
            _sl = sorted((e for e in grp if e["mark"] == "sajdah-line"),
                         key=lambda e: -e["x1"])
            for e in _sl[1:]:
                e["mkpart"] = True
                _sl[0].setdefault("mkmembers", []).append(e)
    for (lab, su, ay), grp in ejected.items():
        # document order follows recitation (Abdullah 2026-08-28): the sign
        # emits right after the last word of the ayah it belongs to, not at
        # the end of the page
        _entry = (None, [{"els": grp, "sa": (lab, su, ay)}])
        _idx = max((i for i, (w, _) in enumerate(assignment)
                    if w and w["surah"] == su and w["ayah"] == ay),
                   default=None)
        if _idx is None:
            assignment = assignment + [_entry]
        else:
            assignment.insert(_idx + 1, _entry)



    # A mark that changed hands keeps the name its old word gave it, which its
    # new word may not want at all — a tanween landing on a word whose text has
    # none, or a plain vowel landing where a tanween belongs. The text decides
    # again, by position.
    for _w7, _at7 in assignment:
        if _w7 is None:
            continue
        txt7 = _w7["uthmani"]
        els7 = [e for a in _at7 for e in a["els"]]
        bods7 = [e for e in els7 if e["kind"] == "body"]
        if not bods7:
            continue
        mid7 = (min(e["y1"] for e in bods7) + max(e["y2"] for e in bods7)) / 2
        for tan7, plain7, chars7 in (
                ("fathatan", "fatha", "\u064b\u08f0"),
                ("kasratan", "kasra", "\u064d\u08f2"),
                ("dammatan", "damma", "\u064c\u08f1")):
            want7 = sum(txt7.count(c) for c in chars7)
            got7 = [e for e in els7 if e.get("mark") == tan7
                    and not e.get("mkpart")]
            for e in got7[want7:]:        # a tanween this word never carries
                if tan7 == "dammatan":
                    e["mark"] = "damma"
                else:
                    cy7 = (e["y1"] + e["y2"]) / 2
                    e["mark"] = "kasra" if cy7 > mid7 else "fatha"
                for m7 in e.get("mkmembers", []):
                    m7["mark"] = e["mark"]
            if want7 > len(got7):
                # ... and the tanween it does carry, arriving as a plain vowel
                pool7 = [e for e in els7 if e.get("mark") == plain7
                         and not e.get("mkpart")]
                spare7 = len(pool7) - txt7.count(
                    {"fatha": "\u064e", "kasra": "\u0650",
                     "damma": "\u064f"}[plain7])
                lx7 = min(e["x1"] for e in bods7)
                for e in sorted(pool7,
                                key=lambda x: abs((x["x1"] + x["x2"]) / 2 - lx7)):
                    if spare7 <= 0 or want7 <= len(got7):
                        break
                    e["mark"] = tan7
                    for m7 in e.get("mkmembers", []):
                        m7["mark"] = tan7
                    got7.append(e)
                    spare7 -= 1

    # Re-run the slash renamer: oracle repair moves slashes between words after
    # the first naming pass, so a mark can keep the identity its OLD word gave
    # it (a fatha arriving above a new word still called kasra). Position and
    # the new word's own kasra budget decide again.
    for _w, atoms in assignment:
        if _w is None:
            continue
        els = [e for a in atoms for e in a["els"]]
        sl = [e for e in els if e["kind"] == "mark"
              and e.get("mark") in ("fatha", "kasra")
              and not e.get("mkpart") and not e.get("mkmembers")]
        if not sl:
            continue
        bods = [e for e in els if e["kind"] == "body"] or els
        mid = (min(e["y1"] for e in bods) + max(e["y2"] for e in bods)) / 2
        want_k = _w["uthmani"].count("\u0650")
        # a kasra welded into another mark still spends the word's budget
        want_k -= sum(1 for e in els
                      if e["kind"] == "mark" and e not in sl
                      and not e.get("mkpart")
                      and "kasra" in (e.get("mark") or "").split("+"))
        want_k = max(0, want_k)
        sl.sort(key=lambda e: -(e["y1"] + e["y2"]))     # lowest first
        for e in sl:
            e["mark"] = "fatha"
        k = 0
        for e in sl:
            if k < want_k and (e["y1"] + e["y2"]) / 2 > mid:
                e["mark"] = "kasra"
                k += 1
        if k < want_k:
            for e in sl:
                if k >= want_k:
                    break
                if e["mark"] == "fatha":
                    e["mark"] = "kasra"
                    k += 1
                    break

    # Late two-stroke damma weld: oracle repair can reunite an ornate damma's
    # curl and tail after the early weld ran — join touching stacked pieces.
    for _w, atoms in assignment:
        if _w is None:
            continue
        dm = [e for a in atoms for e in a["els"]
              if e.get("mark") == "damma" and not e.get("mkpart")]
        dm.sort(key=lambda e: e["y1"])
        for i in range(len(dm)):
            for j in range(i + 1, len(dm)):
                top, bot = dm[i], dm[j]
                if top.get("mkpart") or bot.get("mkpart"):
                    continue
                xov = min(top["x2"], bot["x2"]) - max(top["x1"], bot["x1"])
                gap = bot["y1"] - top["y2"]
                if xov > 2.0 and -1.5 < gap < 1.0 \
                        and bot["y2"] - top["y1"] < 9.5:
                    bot["mkpart"] = True
                    top.setdefault("mkmembers", []).append(bot)
        # a dammatan drawn as two side-by-side dammas: weld the two pieces
        dt = [e for a in atoms for e in a["els"]
              if e.get("mark") == "dammatan" and not e.get("mkpart")
              and not e.get("mkmembers")]
        for i in range(len(dt)):
            for j in range(i + 1, len(dt)):
                a2, b2 = dt[i], dt[j]
                if a2.get("mkpart") or b2.get("mkpart"):
                    continue
                if a2.get("mark") != b2.get("mark"):
                    continue
                dx = abs((a2["x1"] + a2["x2"]) / 2 - (b2["x1"] + b2["x2"]) / 2)
                dy = abs((a2["y1"] + a2["y2"]) / 2 - (b2["y1"] + b2["y2"]) / 2)
                if dx < 5.0 and dy < 5.0:
                    b2["mkpart"] = True
                    a2.setdefault("mkmembers", []).append(b2)

    # The shape table is the strongest identity: repairs and welds sometimes
    # rename a stroke across structural families (a slash pressed into service
    # as a dot or a tanween half). Where the single-shape table disagrees
    # across families, it wins; fatha/kasra stay position-resolved.
    _tbl_fix = {k: (v["label"] if isinstance(v, dict) else v)
                for k, v in shape_labels().items()}
    from markshape import signature as _sg2, sig_key as _sk2, \
        element_points as _ep2
    from split_line_elements import contour_polylines as _cp2
    from svg_lines import apply as _xf2

    _cp_cache = {}

    def _late_sig(e):
        if e.get("sig"):
            return e["sig"]
        try:
            pi = e["path"]
            if pi not in _cp_cache:
                _cp_cache[pi] = _cp2(page.paths[pi]["d"])
            polys2 = _cp_cache[pi]
            pts = _ep2([[_xf2(page.paths[pi]["M"], x, y)
                         for x, y in polys2[c["sp"]["index"]]]
                        for c in e["contours"]])
            e["sig"] = _sk2(_sg2(pts))
        except Exception:
            return None
        return e["sig"]

    for _w2, _at2 in assignment:
        for _a2 in _at2:
            bods2 = [e for e in _a2["els"] if e["kind"] == "body"]
            for _e2 in _a2["els"]:
                if _e2.get("mkpart") or _e2.get("fused"):
                    continue
                if _e2.get("mkmembers"):
                    # the p85 ذَرَّةࣲ knot (Abdullah's e298/e304 verdict): a
                    # slash stroke wearing "two-dots" as a MASTER with the
                    # letter's real dot pair welded beneath it. Free the
                    # members (they are the ة's two-dots) and let the table
                    # rename the slash; everything else with members stays.
                    _tk = _tbl_fix.get(_late_sig(_e2))
                    if (_e2.get("mark") == "two-dots"
                            and _tk in ("fatha", "kasra")
                            and (_e2["x2"] - _e2["x1"]) >= 4.5):
                        for _mmb in _e2["mkmembers"]:
                            _mmb["mkpart"] = False
                        _e2["mkmembers"] = []
                    else:
                        continue
                t = _tbl_fix.get(_late_sig(_e2))
                cur = _e2.get("mark")
                if not t or not cur or t == cur:
                    continue
                fix = None
                if cur in ("dot", "two-dots") and t in ("fatha", "kasra") \
                        and (_e2["x2"] - _e2["x1"]) >= 4.5:
                    # p85 ذَرَّةࣲ: the kasratan's slash half wore
                    # "two-dots" as a master, its real pair welded under it
                    fix = "slash"
                elif cur in ("damma", "dammatan") and t in ("fatha", "kasra"):
                    fix = "slash"
                elif cur in ("fatha", "kasra", "damma", "dammatan")                         and t == "shadda":
                    fix = "shadda"
                elif cur == "pause" and t in ("dot", "two-dots",
                                              "three-dots"):
                    # a letter's dots taken as a waqf sign (p548
                    # وَٱلشَّهَٰدَةِۖ: the ة pair named pause). Welded
                    # sign satellites are mkpart and never reach here.
                    _e2["mark"] = t
                elif cur == "small-waw" and t == "damma":
                    _e2["mark"] = "damma"
                if fix == "slash":
                    ref = bods2[0] if bods2 else None
                    below = ref is not None and                         (_e2["y1"] + _e2["y2"]) / 2 > (ref["y1"] + ref["y2"]) / 2
                    _e2["mark"] = "kasra" if below else "fatha"
                elif fix == "shadda":
                    _e2["mark"] = "shadda"

    # kind follows the final identity: a piece that ended up carrying a mark
    # name is a mark whatever the size heuristic first said, and vice versa
    _MARKFAM = {"fatha", "kasra", "damma", "fathatan", "kasratan", "dammatan",
                "sukun", "shadda", "hamza", "maddah", "small-alef", "wasla",
                "dot", "two-dots", "three-dots", "pause", "small-circle",
                "small-ya", "small-waw", "small-meem", "small-noon",
                "saktah", "seen-reading", "imalah", "ishmam", "tashil"}
    for _w2, _at2 in assignment:
        for _a2 in _at2:
            for _e2 in _a2["els"]:
                mk = _e2.get("mark")
                if mk and _e2["kind"] == "body" \
                        and all(p in _MARKFAM for p in mk.split("+")):
                    _e2["kind"] = "mark"

    # Reviewer overrides have the last word. A human looked at this page and
    # said which word owns this piece of ink; no inference outranks that. They
    # are keyed by geometry, not by element id, so they survive pipeline
    # changes — and each one is also a standing regression test.
    # A waqf sign recorded by place is a waqf sign, not letter dots. The muʿānaqah is
    # drawn as three dots in a triangle, and this pipeline sees three dots: on p112 the
    # `ٱلْقَوْمِ` under one of them came out holding five dot units where its spelling
    # allows two. Welding the pieces of one occurrence into a single `pause` makes the
    # count agree with both the spelling and the reference — the text does ask for a
    # pause there, since the QPC text carries the `ۛ`.
    _places = waqf_places().get(
        str(int(os.path.splitext(page.name)[0].split("-")[0].lstrip("0") or 0)), {})
    if _places:
        for _wp, _atp in assignment:
            if not _wp:
                continue
            _byocc = {}
            for _a in _atp:
                for _e in _a["els"]:
                    _r = _places.get("%.1f,%.1f,%.1f,%.1f"
                                     % (_e["x1"], _e["y1"], _e["x2"], _e["y2"]))
                    if isinstance(_r, dict):
                        _byocc.setdefault(_r["occ"], []).append(_e)
            for _grp in _byocc.values():
                _grp.sort(key=lambda e: -(e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
                _grp[0]["mark"] = "pause"
                _grp[0]["mkmembers"] = _grp[1:]
                _grp[0].pop("mkpart", None)
                for _m in _grp[1:]:
                    _m["mark"] = "pause"
                    _m["mkpart"] = True

    # A dot label names how many dots the CLUSTER stands for, and the art draws dots at
    # one fixed size — measured over six pages, every `dot` is 2.38 units wide, every
    # `two-dots` between 4.43 and 4.72, and every welded twin 2.38. So a piece of ink
    # says how many blobs it holds: its width divided by a single dot's.
    #
    # `three-dots` masters are the bimodal case, and the reason a word can be credited
    # with ink the page does not draw. Some are 4.55 wide — two blobs, plus a 2.38 twin
    # makes three, and the label is right. Others are 2.38, one blob, and with a 2.38
    # twin the cluster is only two: `شَىْءٍۢ` on p142 draws the ش as three separate blobs
    # held as a `dot` plus such a pair, and the word counts four where three are drawn.
    #
    # Only ever narrowed to the blobs measured, never widened; nothing moves.
    #
    # Two earlier rewrites of this rested on false premises and the gate caught both:
    # renaming by contour count took mark flags 659 -> 32,772 (every dot element has
    # exactly one contour, `two-dots` included), and renaming by welded-member count
    # took dot errors 13 -> 9,705 (a `two-dots` has no members at all).
    if os.environ.get("QSVG_DOTLBL", "1") == "1":
        _DOT_W = 2.38                      # one drawn dot, in page units
        _BYN = {1: "dot", 2: "two-dots", 3: "three-dots"}
        _VAL = {"dot": 1, "two-dots": 2, "three-dots": 3}

        def _blobs(e):
            return max(1, int(round((e["x2"] - e["x1"]) / _DOT_W)))

        for _wl, _atl in assignment:
            if not _wl:
                continue
            for _al in _atl:
                for _el in _al["els"]:
                    if (_el.get("mark") or "") not in _VAL or _el.get("mkpart"):
                        continue
                    _n = _blobs(_el) + sum(_blobs(_m) for _m in (_el.get("mkmembers") or [])
                                           if (_m.get("mark") or "") in _VAL)
                    if _n < _VAL[_el["mark"]] and _n in _BYN:
                        _el["mark"] = _BYN[_n]

    _ovr_path = os.path.join(ROOT, ".cache", "review", "overrides.json")
    if os.path.exists(_ovr_path):
        try:
            _ovr = json.load(open(_ovr_path)).get(str(page_no), {})
        except Exception:
            _ovr = {}
        if _ovr:
            _by_word = {}
            for _w9, _at9 in assignment:
                if _w9:
                    _by_word["%d:%d:%d" % (_w9["surah"], _w9["ayah"],
                                           _w9["pos"])] = (_w9, _at9)
            for _w9, _at9 in assignment:
                for _a9 in list(_at9):
                    for _e9 in list(_a9["els"]):
                        _k9 = "%.1f,%.1f,%.1f,%.1f" % (_e9["x1"], _e9["y1"],
                                                       _e9["x2"], _e9["y2"])
                        _tgt = _ovr.get(_k9)
                        if os.environ.get("QSVG_OVRDBG") and _k9 in (
                                "231.3,517.6,237.6,521.0",):
                            print("OVRDBG key=%s tgt=%r in_by_word=%s"
                                  % (_k9, _tgt, _tgt in _by_word
                                     if _tgt else None), file=sys.stderr)
                        if not _tgt and len(_e9.get("contours", [])) > 1:
                            # CONTOUR-level override (Abdullah 2026-08-28,
                            # p535 e420: a fused pair whose halves belong to
                            # different WORDS). If a key matches one
                            # contour's transformed bbox, split that contour
                            # out as its own element and move only it.
                            _pM9 = page.paths[_e9["path"]]["M"]
                            for _c9 in list(_e9["contours"]):
                                sp9 = _c9["sp"]
                                bx1, by1, bx2, by2 = transform_box(
                                    _pM9, sp9["xmin"], sp9["ymin"],
                                    sp9["xmax"], sp9["ymax"])
                                _ck = "%.1f,%.1f,%.1f,%.1f" % (
                                    min(bx1, bx2), min(by1, by2),
                                    max(bx1, bx2), max(by1, by2))
                                _ct = _ovr.get(_ck)
                                if _ct and _ct in _by_word:
                                    _e9["contours"] = [
                                        c for c in _e9["contours"]
                                        if c is not _c9]
                                    _ne9 = dict(_e9)
                                    _ne9["contours"] = [_c9]
                                    _ne9["x1"], _ne9["y1"] = (
                                        min(bx1, bx2), min(by1, by2))
                                    _ne9["x2"], _ne9["y2"] = (
                                        max(bx1, bx2), max(by1, by2))
                                    _ne9.pop("mkmembers", None)
                                    _ne9.pop("sig", None)
                                    _ne9.pop("tanform", None)
                                    _ne9["_ovr"] = 1
                                    _dw9, _dat9 = _by_word[_ct]
                                    put_in_ligature(_dat9, _ne9)
                                    # the stranded remainder re-fits its own
                                    # bbox
                                    _rb = [transform_box(
                                        _pM9, c["sp"]["xmin"], c["sp"]["ymin"],
                                        c["sp"]["xmax"], c["sp"]["ymax"])
                                        for c in _e9["contours"]]
                                    _e9["x1"] = min(min(a, c) for a, b, c, d in _rb)
                                    _e9["y1"] = min(min(b, d) for a, b, c, d in _rb)
                                    _e9["x2"] = max(max(a, c) for a, b, c, d in _rb)
                                    _e9["y2"] = max(max(b, d) for a, b, c, d in _rb)
                        if not _tgt or _tgt not in _by_word:
                            continue
                        _dw, _dat = _by_word[_tgt]
                        if _dw is _w9:
                            continue          # already where it belongs
                        _e9["_ovr"] = 1     # human placement: no later
                                            # mover may relocate this piece
                        _a9["els"].remove(_e9)
                        # an override move BREAKS any weld: a piece pinned
                        # to a word by the eye may not keep counting
                        # through a master in another word (p535 e420)
                        if _e9.get("mkpart"):
                            _e9["mkpart"] = False
                            for _wq9, _atq9 in assignment:
                                for _aq9 in _atq9:
                                    for _x9 in _aq9["els"]:
                                        if _e9 in (_x9.get("mkmembers")
                                                   or []):
                                            _x9["mkmembers"].remove(_e9)
                        for _m9 in _e9.get("mkmembers", []):
                            if _m9 in _a9["els"]:
                                _a9["els"].remove(_m9)
                        # Nearest ligature group, not blindly the first one —
                        # the same rule every mover follows (see
                        # put_in_ligature's docstring: appending to atoms[0]
                        # put p591's kasra in the group at the far end of its
                        # word). put_in_ligature also carries mkmembers.
                        if os.environ.get("QSVG_OVRLIG", "1") == "1":
                            put_in_ligature(_dat, _e9)
                        else:
                            _dat[0]["els"].append(_e9)
                            _dat[0]["els"].extend(_e9.get("mkmembers", []))
                        # A mover may have retagged the piece's line to keep
                        # its old word together (the cross-line repair does:
                        # e5["line"] = dst5["ln"]), and a stale tag makes the
                        # returned word register on the wrong line — p59's
                        # مَا read as line 9 ink and tripped rtl-order. The
                        # band its centre is drawn in is the truth, same rule
                        # as the body re-liner above.
                        # Bodies only: "geometry is the truth for bodies", but
                        # a mark belongs to its LETTER and may legitimately sit
                        # in the neighbouring band (a deep kasra), so marks
                        # keep the tag their letter gave them — the same split
                        # the two re-liners above this stage make.
                        if _e9["kind"] != "body" or os.environ.get("QSVG_OVRLN", "1") != "1":
                            continue
                        _cy9 = (_e9["y1"] + _e9["y2"]) / 2
                        for _li9 in lines_info:
                            if _li9["top"] <= _cy9 <= _li9["bottom"]:
                                if _e9.get("line") != _li9["lineNumber"]:
                                    _e9["line"] = _li9["lineNumber"]
                                    for _m9 in _e9.get("mkmembers", []):
                                        _m9["line"] = _li9["lineNumber"]
                                break

    # Ink held in the right word but read as a mark where it is a letter. Adjudicated,
    # geometry-keyed, written by tools/ref_kinds.py — see there for why these are facts
    # about places rather than a rule.
    _kinds = _kind_table().get(
        str(int(os.path.splitext(page.name)[0].split("-")[0].lstrip("0") or 0)), {})
    if _kinds:
        for _wk, _atk in assignment:
            if not _wk:
                continue
            for _ak in _atk:
                for _ek in _ak["els"]:
                    _kk = _kinds.get("%.1f,%.1f,%.1f,%.1f"
                                     % (_ek["x1"], _ek["y1"], _ek["x2"], _ek["y2"]))
                    if _kk == "body":
                        _ek["kind"] = "body"
                        _ek.pop("mark", None)
                        _ek.pop("mkpart", None)
                    # The inverse fact, same table: ink read as a LETTER where a human
                    # confirmed it is a mark (round-7 pause verdicts, R11 damma blobs —
                    # a ۖ or a slightly clipped damma outline the classifier called
                    # letter ink). The value names the mark. Two signals stand behind
                    # every entry: the word's text budget is short exactly this family,
                    # and the drawn blob was identified by eye (and for the waqf signs
                    # by its signature in waqf_types.json).
                    elif _kk in _MARKFAM and os.environ.get("QSVG_KINDMK", "1") == "1":
                        _ek["kind"] = "mark"
                        _ek["mark"] = _kk
                        _ek.pop("mkpart", None)

    # Late same-label tanween pair re-weld: kinds/override arrivals above can
    # name a pair's second stroke after the early weld already ran (p540/p568
    # kasratan twins, Abdullah). Same geometry gate as the early weld.
    for _wq2, _atq2 in assignment:
        if not _wq2:
            continue
        _tp = [e for a in _atq2 for e in a["els"]
               if e.get("mark") in ("dammatan", "kasratan", "fathatan")
               and not e.get("mkpart") and not e.get("mkmembers")]
        for _i2 in range(len(_tp)):
            for _j2 in range(_i2 + 1, len(_tp)):
                _a3, _b3 = _tp[_i2], _tp[_j2]
                if _a3.get("mark") != _b3.get("mark") or _b3.get("mkpart"):
                    continue
                if (abs((_a3["x1"] + _a3["x2"]) / 2 - (_b3["x1"] + _b3["x2"]) / 2) < 5.0
                        and abs((_a3["y1"] + _a3["y2"]) / 2
                                - (_b3["y1"] + _b3["y2"]) / 2) < 5.0):
                    _b3["mkpart"] = True

    # Dot clusters whose label overstates the ink they cover — the residue the measured
    # blob width cannot separate. Adjudicated, geometry-keyed; see tools/ref_marks.py.
    _mk = _mark_table().get(
        str(int(os.path.splitext(page.name)[0].split("-")[0].lstrip("0") or 0)), {})
    if _mk:
        for _wm, _atm in assignment:
            if not _wm:
                continue
            for _am in _atm:
                for _em in _am["els"]:
                    _nn = _mk.get("%.1f,%.1f,%.1f,%.1f"
                                  % (_em["x1"], _em["y1"], _em["x2"], _em["y2"]))
                    if _nn:
                        _em["mark"] = _nn

    # A diacritic sits ON a letter. If none of its word's letters overlaps it
    # horizontally, it is not sitting on anything that word owns — it is floating above a
    # neighbour's letters. Abdullah found this on p590, where `وَعَمِلُوا۟` had lost a
    # fatha and a kasra to `ٱلصَّٰلِحَٰتِ`, which had lost two of its own to `لَهُمْ`.
    # Mushaf-wide the test finds 178 such marks, 140 of them invisible to the
    # MushafDatabase comparison, which reads letter extents and dot counts only.
    #
    # Geometry proposes; the text budget disposes — but a line at a time, not a mark at a
    # time. p590 is a CHAIN: the middle word balances, because the two marks it is owed
    # and the two it wrongly holds cancel in the count. Judged one move at a time both
    # transfers are refused (donor not over budget, receiver has no room) and the chain
    # survives; applied together they resolve. So every floating mark on a line is moved
    # to the neighbour whose ink it sits over, and the line is kept only if it ends with
    # fewer words whose marks disagree with their spelling than it started with.
    #
    # Counted per FAMILY GROUP, never per family: fatha and kasra are one stroke named
    # afterwards from which side of the letter it lands on, so a word can be short a
    # kasra and long a fatha and be wrong in neither column. Same for damma/dammatan.
    #
    # Only the immediate neighbour, because a diacritic drifts onto the word beside it and
    # does not cross the page: without that, a word which is itself on the wrong line has
    # all of its marks look orphaned — its letters sit at the far end of the line — and
    # they get handed to whatever happens to lie under them. On p526 that turned one flag
    # into five. A misplaced word is a line defect and belongs to the line audits.
    if os.environ.get("QSVG_ORPHAN", "1") == "1":
        _GRP = {"fatha": "slash", "kasra": "slash",
                "fathatan": "slash", "kasratan": "slash",
                "damma": "damma", "dammatan": "damma",
                "dot": "dots", "two-dots": "dots", "three-dots": "dots"}
        _UNITS = {"dot": 1, "two-dots": 2, "three-dots": 3}
        _CHARS = {"slash": "\u064e\u0650\u064b\u064d\u08f0\u08f2",
                  "damma": "\u064f\u064c\u08f1"}

        def _held(els, grp):
            n = 0
            for e in els:
                if e.get("mkpart") or _GRP.get(e.get("mark")) != grp:
                    continue
                n += _UNITS.get(e["mark"], 1)
            return n

        def _want(w, grp):
            if grp == "dots":
                return dot_budget(w["uthmani"])
            return sum(w["uthmani"].count(c) for c in _CHARS[grp])

        def _rename(rec):
            """Re-derive every slash name in this word from the side of the letter it sits on."""
            for e in rec["els"]:
                if e.get("mark") not in _POS_SWAP_FAM or e.get("mkpart"):
                    continue
                u = [b for b in rec["b"]
                     if min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]) > -0.6] or rec["b"]
                mid = (min(b["y1"] for b in u) + max(b["y2"] for b in u)) / 2
                side = "a" if (e["y1"] + e["y2"]) / 2 < mid else "b"
                nm = _POS_SWAP.get((e["mark"], side), e["mark"])
                if nm != e["mark"]:
                    e["mark"] = nm
                    for m in e.get("mkmembers", []):
                        m["mark"] = nm

        def _rename1(rec, e):
            """Re-derive ONE mark's name from the letters it now sits on.

            The whole-word version is right for the orphan pass, where both words are
            neighbours and every name is in play. It is wrong across a page: on p371 it
            renamed `ضَلَـٰلٍۢ`'s own correct fatha to a kasra while installing the mark
            that arrived — fatha 1/2 became fatha 0/2, kasra 2/0. Only the arriving mark
            carries a name earned over someone else's letters; the marks already there
            earned theirs where they sit.
            """
            if e.get("mark") not in _POS_SWAP_FAM or e.get("mkpart"):
                return
            u = [b for b in rec["b"]
                 if min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]) > -0.6] or rec["b"]
            mid = (min(b["y1"] for b in u) + max(b["y2"] for b in u)) / 2
            side = "a" if (e["y1"] + e["y2"]) / 2 < mid else "b"
            nm = _POS_SWAP.get((e["mark"], side), e["mark"])
            if nm != e["mark"]:
                e["mark"] = nm
                for m in e.get("mkmembers", []):
                    m["mark"] = nm

        # open tanween U+08F0-2 included: under QSVG_DKTEXT the budget text
        # writes them at ~6,643 words, and a counter blind to them sees
        # phantom mismatches — on p576 that made a wrong exchange look like
        # an improvement.
        _FAMCH = {"fatha": "\u064e", "kasra": "\u0650",
                  "fathatan": "\u064b\u08f0", "kasratan": "\u064d\u08f2",
                  "damma": "\u064f", "dammatan": "\u064c\u08f1"}

        def _off(rec):
            """How many ways this word's marks disagree with its spelling.

            Counted per FAMILY — fatha against fatha, kasra against kasra — not per
            group. Abdullah's point, and it is what exposes an exchange: on p591
            `وَٱلسَّمَآءِ` and `وَٱلطَّارِقِ` each hold one of the other's marks, so every
            group total stays right and the line looks untouched. Per family it does not.
            This is only sound because the names are re-derived from position after each
            move; before that, a slash carried across a word keeps a name earned on the
            other side of a letter and the family counts are meaningless.
            """
            n = 0
            for fam, chs in _FAMCH.items():
                if sum(1 for e in rec["els"]
                       if e.get("mark") == fam and not e.get("mkpart")) \
                        != sum(rec["w"]["uthmani"].count(c) for c in chs):
                    n += 1
            if _held(rec["els"], "dots") != _want(rec["w"], "dots"):
                n += 1
            return n

        _recs = []
        for _wo, _ato in assignment:
            if not _wo:
                continue
            _e2 = [e for a in _ato for e in a["els"]]
            _b2 = [e for e in _e2 if e["kind"] == "body"]
            if not _b2:
                continue
            _l2 = [e.get("line") for e in _b2 if e.get("line")]
            _recs.append({"w": _wo, "at": _ato, "els": _e2, "b": _b2,
                          "ln": max(set(_l2), key=_l2.count) if _l2 else 0})

        def _ovl(bs, e):
            return max((min(b["x2"], e["x2"]) - max(b["x1"], e["x1"])) for b in bs) if bs else -9e9

        # the y extent of each line's letters, used to tell a mark that merely hangs low
        # from one drawn in the next line's band
        _band = {}
        for _rb in _recs:
            _lo0, _hi0 = _band.get(_rb["ln"], (1e9, -1e9))
            _band[_rb["ln"]] = (min(_lo0, min(b["y1"] for b in _rb["b"])),
                                max(_hi0, max(b["y2"] for b in _rb["b"])))

        for _ln in {r["ln"] for r in _recs}:
            _line = sorted([r for r in _recs if r["ln"] == _ln],
                           key=lambda x: -max(b["x2"] for b in x["b"]))
            if len(_line) < 2:
                continue
            # Settle the naming first, then look for moves. A slash's name is derived from
            # the side of the letter it sits on, so a wrongly-owned mark can carry a name
            # earned over someone else's letters — and two such names can cancel, leaving
            # every count correct while the ink is plainly misplaced. p591's
            # `وَٱلسَّمَآءِ`/`وَٱلطَّارِقِ` sit in exactly that hole: nothing is out of
            # balance, so no move can improve anything, and the pair is frozen. Naming
            # every mark from where it actually sits first is what makes the counts mean
            # something before they are used to judge a transfer.
            # OFF by default: measured, it makes things worse. Naming every mark from the
            # box midpoint of the letters under it is cruder than the pipeline's own
            # local_pos(), which uses the letters' actual contour points — so a blanket
            # re-derivation overwrites good names with worse ones. p591 went from two
            # balanced words to two mismatched, p350 from three right to one. The naming
            # after a MOVE still happens, because there the old name was earned over
            # another word's letters and is worthless; it is the untouched marks that
            # must be left alone.
            if os.environ.get("QSVG_RENAME", "0") == "1":
                for _r in _line:
                    _rename(_r)
            _plan = []
            for _i, _r in enumerate(_line):
                for _e in _r["els"]:
                    if _e["kind"] == "body" or _e.get("mkpart") or _e.get("mark") not in _GRP:
                        continue
                    _own9 = _ovl(_r["b"], _e)
                    if _own9 > -0.6:
                        # touching its own word is not owning it: the measured
                        # residue (50 one-way drifts, 2026-08-28) all have own
                        # coverage under a quarter of the stroke while a
                        # neighbour holds 60%+ — propose those too; the
                        # line-budget accept still judges every move.
                        _w9 = _e["x2"] - _e["x1"]
                        _nb9 = max((_ovl(_line[_j]["b"], _e)
                                    for _j in (_i - 1, _i + 1)
                                    if 0 <= _j < len(_line)), default=-9e9)
                        if not (_own9 < 0.25 * _w9 and _nb9 > 0.6 * _w9):
                            continue
                    # Ink drawn in ANOTHER LINE'S BAND is a vertical defect and belongs
                    # to audit_crossline.py, not here; letting it in poisoned p350, where
                    # `لَا` holds a fatha drawn a line above its own letters.
                    #
                    # Tested by POSITION, not by the element's `line` tag. The tag is
                    # wrong exactly where this matters: on p591 `وَٱلطَّارِقِ` holds the
                    # kasra belonging under `ٱلسَّمَآءِ`'s hamza, drawn at y 103.7-107.0
                    # squarely inside line 3's band of 88-108, and tagged line 4 because
                    # it hangs low. The tag test skipped it, so only one half of the
                    # exchange was ever proposed and the pair could never resolve — the
                    # defect Abdullah reported three times. Same at 86:11:1.
                    #
                    # 10 units is measured: across all 604 pages 4,203 marks sit between
                    # 5 and 10 units outside their word's band and only 26 between 10 and
                    # 15, a 160x cliff, so the band plus ten units is the whole of what a
                    # mark legitimately does vertically.
                    _lo, _hi = _band.get(_r["ln"], (-1e9, 1e9))
                    _cy = (_e["y1"] + _e["y2"]) / 2
                    if _cy < _lo - 10.0 or _cy > _hi + 10.0:
                        continue
                    _best, _bo = None, -0.6
                    for _j in (_i - 1, _i + 1):
                        if not (0 <= _j < len(_line)):
                            continue
                        _o = _ovl(_line[_j]["b"], _e)
                        if _o > _bo:
                            _bo, _best = _o, _line[_j]
                    if _best is not None:
                        _plan.append((_r, _best, _e))
            if not _plan:
                continue
            # Accept when the line does not get WORSE, not only when it gets better.
            # Requiring improvement cannot pass a mutual exchange: on p591 `وَٱلسَّمَآءِ`
            # and `وَٱلطَّارِقِ` each hold one of the other's marks, so every count stays
            # exactly right and the line never improves — while the ink is plainly in the
            # wrong word, the kasra sitting under `ٱلسَّمَآءِ`'s hamza and the fatha over
            # `ٱلطَّارِقِ`'s letters. Geometry justifies each move on its own; the budget's
            # job here is only to veto a move that breaks a count.
            #
            # The whole line's set is tried first, because an exchange only works applied
            # together — moving half of it leaves one word short and the other long, and a
            # move-by-move test would reject the first and never reach the second. Only if
            # the set as a whole makes things worse is it retried one move at a time, so a
            # single bad proposal costs its own move rather than the whole line's.
            def _apply(mv):
                _was = [(e, e.get("mark")) for r, t, e in mv]
                for _r, _t, _e in mv:
                    _r["els"].remove(_e)
                    _t["els"].append(_e)
                _touched = {id(x): x for m in mv for x in (m[0], m[1])}
                _snap = [(e, e.get("mark")) for x in _touched.values() for e in x["els"]]
                # Name ONLY the arriving marks (the p371 lesson: the marks
                # already in place earned their names where they sit; the
                # whole-word midpoint rename scrambled them — p90's bowl
                # kasratan became a fathatan and every exchange judged worse).
                # The receiver's budget names the arrival when exactly one
                # slash family is short (two signals: geometry moved it,
                # budget names it); position decides only when budget cannot.
                for _r0, _t0, _e0 in mv:
                    if _e0.get("mark") not in _POS_SWAP_FAM:
                        continue
                    _defs = []
                    for _fam0, _chs0 in (("fatha", "\u064e"),
                                         ("kasra", "\u0650"),
                                         ("fathatan", "\u064b\u08f0"),
                                         ("kasratan", "\u064d\u08f2")):
                        _wv = sum(_t0["w"]["uthmani"].count(c) for c in _chs0)
                        _hv = sum(1 for x in _t0["els"]
                                  if x is not _e0
                                  and x.get("mark") == _fam0
                                  and not x.get("mkpart"))
                        if _hv < _wv:
                            _defs.append(_fam0)
                    if len(_defs) == 1:
                        _e0["mark"] = _defs[0]
                        for _m0 in _e0.get("mkmembers", []):
                            _m0["mark"] = _defs[0]
                    else:
                        _rename1(_t0, _e0)
                return _snap + _was

            def _undo(mv, snap):
                for _r, _t, _e in mv:
                    _t["els"].remove(_e)
                    _r["els"].append(_e)
                for e, nm in snap:
                    if nm is None:
                        e.pop("mark", None)
                    else:
                        e["mark"] = nm

            _before = sum(_off(r) for r in _line)
            if os.environ.get("QSVG_ODBG"):
                sys.stderr.write("ODBG line %s: %d proposal(s), line off=%d\n"
                                 % (_ln, len(_plan), _before))
                for _r0, _t0, _e0 in _plan:
                    sys.stderr.write("   %-16s -> %-16s %-10s x %.1f-%.1f  (off %d -> ?)\n"
                                     % (_r0["w"]["uthmani"], _t0["w"]["uthmani"],
                                        _e0.get("mark"), _e0["x1"], _e0["x2"], _off(_r0)))
            _snap = _apply(_plan)
            if os.environ.get("QSVG_ODBG"):
                sys.stderr.write("   after the whole set: line off=%d %s\n"
                                 % (sum(_off(r) for r in _line),
                                    "ACCEPT" if sum(_off(r) for r in _line) <= _before else "REJECT"))
                for _r0, _t0, _e0 in _plan:
                    sys.stderr.write("      %-16s off=%d   %-16s off=%d\n"
                                     % (_r0["w"]["uthmani"], _off(_r0),
                                        _t0["w"]["uthmani"], _off(_t0)))
            if sum(_off(r) for r in _line) > _before \
                    and os.environ.get("QSVG_SLASHX", "1") == "1":
                # Exchange completion (Abdullah's p586 هو/بقول, item 32): the
                # geometric proposal finds only the leg with NO own-ink
                # coverage; the counterpart stroke touches its holder's span
                # (tight kerning) and is never proposed, so the half-exchange
                # worsens counts and everything is rejected. When the one-way
                # set fails, license ONE reciprocal per move: the receiving
                # word's slash mark that most covers the donor's letters.
                # Applied together and re-judged by the same line budget.
                _undo(_plan, _snap)
                _aug = list(_plan)
                _moved = {id(m[2]) for m in _plan}
                for _r, _t, _e in _plan:
                    # geometry decides the reciprocal: it must cover the
                    # donor's letters MORE than its own holder's (p586's
                    # e784 sits over بقول's ب while merely touching هو).
                    # Budget cannot judge these — a true mutual exchange is
                    # exactly count-neutral — so the count below only vetoes.
                    _cands = [x for x in _t["els"]
                              if x.get("mark") in ("fatha", "kasra",
                                                   "fathatan", "kasratan")
                              and not x.get("mkpart") and id(x) not in _moved
                              and _ovl(_r["b"], x)
                              > 0.4 * (x["x2"] - x["x1"])]
                    if _cands:
                        _cand = max(_cands, key=lambda x: _ovl(_r["b"], x))
                        _aug.append((_t, _r, _cand))
                        _moved.add(id(_cand))
                _adopted = False
                if len(_aug) > len(_plan):
                    _snap2 = _apply(_aug)
                    # A true exchange is count-NEUTRAL (p586 هو/بقول: the two
                    # misnames cancel, off 0 -> 0), so improvement can never
                    # be the test. The test is PERFECTION: leg 1 is
                    # geometrically certain (a floating mark over the other
                    # word's letters), the reciprocal is budget-forced — and
                    # a right exchange snaps EVERY touched word to exact
                    # budget. Anything less is vetoed.
                    _tch = {id(x): x for m in _aug for x in (m[0], m[1])}
                    if (sum(_off(r) for r in _line) <= _before
                            and all(_off(x) == 0 for x in _tch.values())):
                        _plan, _snap, _adopted = _aug, _snap2, True
                    else:
                        _undo(_aug, _snap2)
                if not _adopted:
                    # leave the state exactly as the original flow expects:
                    # plan applied, judged by the outer test (p576's silent
                    # half-commit came from skipping this re-apply)
                    _snap = _apply(_plan)
            if sum(_off(r) for r in _line) > _before:
                _undo(_plan, _snap)
                _kept = []
                for _mv in _plan:
                    _b1 = sum(_off(r) for r in _line)
                    _s1 = _apply([_mv])
                    if sum(_off(r) for r in _line) > _b1:
                        _undo([_mv], _s1)
                    else:
                        _kept.append(_mv)
                _plan = _kept
            if not _plan:
                continue
            for _r, _t, _e in _plan:              # commit to the atoms, and rename
                for _a in _r["at"]:
                    if _e in _a["els"]:
                        _a["els"].remove(_e)
                        for _m in _e.get("mkmembers", []):
                            if _m in _a["els"]:
                                _a["els"].remove(_m)
                        break
                put_in_ligature(_t["at"], _e)

        # ---- ink stranded a line's width from the word holding it --------------
        #
        # The orphan pass above deliberately walks past these: it only ever hands a mark
        # to the word immediately beside it, because a word that is itself on the wrong
        # line has all of its marks look orphaned. What it leaves behind is a much smaller
        # and much louder defect, and one that can be proved rather than argued.
        #
        # Measured across all 604 pages, the distance from a mark to the nearest letter of
        # the word holding it is bimodal with an EMPTY BAND:
        #
        #     0-2u    2735    2-5u  112    5-10u  30    10-20u  8    20-40u  2
        #     40-150u    0
        #     150-308u  17
        #
        # Nothing in the mushaf sits between 40 and 150 units from its word, and the two
        # widest legitimate gaps are 20-40. So a mark 60 units clear is not a mark that
        # drifted — it is a mark filed under the wrong word, and the distance says so
        # without needing the text to agree.
        #
        # All 17 are one defect. In every case the holder is the word at one END of a line
        # and the mark is drawn at the opposite end, in the band of the line above or
        # below: p350 `لَا` is the first word of line 7 and holds a fatha at x18 tagged
        # line 6; p543 `بِمَا` is the last word of line 3 and holds two marks at x322-325
        # tagged line 4. The last word of a line and the first word of the next are
        # neighbours in READING order and a page apart on the paper, and the ownership has
        # followed the text. The element's own `line` tag is already correct — only the
        # word is wrong — so the tag is what says where to put it back.
        #
        # Two of the four line errors the outside reference confirmed, p543 `بِمَا` and
        # p599 `لَهَا`, are in this set: same cause, and the note that "the layout stage
        # was given the correct boundary in every case, so a later stage moves them" is
        # this wrap.
        if os.environ.get("QSVG_STRAY", "1") != "0":
            _STRAY_GAP = 60.0                 # inside the empty band, far from both modes
            _STRAY_REACH = 20.0               # a target must actually be under the ink
            _byln = {}
            for _r in _recs:
                _byln.setdefault(_r["ln"], []).append(_r)
            for _r in _recs:
                for _e in list(_r["els"]):
                    if _e["kind"] == "body" or _e.get("mkpart"):
                        continue
                    if _e.get("mark") not in _GRP or _e.get("standalone"):
                        continue
                    if _ovl(_r["b"], _e) > -_STRAY_GAP:
                        continue
                    _cands = [t for t in _byln.get(_e.get("line") or _r["ln"], ())
                              if t is not _r]
                    if not _cands:
                        continue
                    _t = max(_cands, key=lambda t: _ovl(t["b"], _e))
                    if _ovl(_t["b"], _e) < -_STRAY_REACH:
                        continue
                    # The move is justified by the distance alone. The budget's only job
                    # is to veto one that breaks a count — the same division of labour as
                    # the orphan pass, where geometry proposes and the text disposes.
                    _b0 = _off(_r) + _off(_t)
                    _snap = [(x, x.get("mark")) for x in _r["els"] + _t["els"]]
                    _r["els"].remove(_e)
                    _t["els"].append(_e)
                    _rename1(_t, _e)
                    if _off(_r) + _off(_t) > _b0 and \
                            os.environ.get("QSVG_STRAY") != "2":
                        _t["els"].remove(_e)
                        _r["els"].append(_e)
                        for _x, _nm in _snap:
                            if _nm is None:
                                _x.pop("mark", None)
                            else:
                                _x["mark"] = _nm
                        continue
                    for _a in _r["at"]:
                        if _e in _a["els"]:
                            _a["els"].remove(_e)
                            for _m in _e.get("mkmembers", []):
                                if _m in _a["els"]:
                                    _a["els"].remove(_m)
                            break
                    put_in_ligature(_t["at"], _e)

    # Ink that draws nothing, counted as a mark.
    #
    # A drawn dot in this art is 2.38 units wide and 5.6 square units in area; measured
    # over all 604 pages the width distribution is
    #
    #     0.0-0.5u  17    0.5-1.5u  0    1.5-2.0u  57    2.0-2.5u  68128    4.5-6.0u  39914
    #
    # so there is nothing at all between half a unit and one and a half. The seventeen
    # below half a unit are degenerate contours — 0.02 wide, enclosing no area, drawing
    # no ink on the page — and eleven of them carry a mark label. Ten are `dot`s, and
    # every one of those ten sits in a word holding exactly ONE dot more than its
    # spelling allows: `مَا` on p536 spells no dot at all and is credited with one.
    # The other is a `small-alef` on p2. The remaining six are welded twins, counted
    # through their master, so they were already harmless.
    #
    # Nothing moves and nothing is deleted — the element stays exactly where it is and
    # keeps drawing exactly what it drew, which is nothing. Only the claim that it is a
    # mark is withdrawn, so the counts stop including ink the page does not have.
    if os.environ.get("QSVG_NULLMARK", "1") != "0":
        _NULL_AREA = 0.5          # inside the empty band; the smallest real mark is ~2.0
        for _wz, _atz in assignment:
            if not _wz:
                continue
            for _az in _atz:
                for _ez in _az["els"]:
                    if not _ez.get("mark") or _ez["kind"] == "body":
                        continue
                    if (_ez["x2"] - _ez["x1"]) * (_ez["y2"] - _ez["y1"]) >= _NULL_AREA:
                        continue
                    _ez.pop("mark", None)
                    _ez.pop("mkmembers", None)
                    _ez["mkpart"] = True      # never counted, never a transfer candidate

    # An iqlab meem drawn between two lines and filed with the wrong one.
    #
    # `ٍۭ` at the end of a line puts the tanween on the last letter and the little meem
    # BELOW it, in the gap between that line and the next — closer to the line below than
    # to the word it belongs to. Abdullah found it on p313, where `نَفْسٍۭ` ends line 3
    # and its meem is held by `هَوَىٰهُ` on line 4, as a letter.
    #
    # This art normally fuses the meem into the tanween glyph — a measured finding of this
    # project, and why audit_marks never asks for one — so almost every word spelling `ۭ`
    # rightly holds no separate meem. That is what makes the exception safe to act on:
    #
    #     words spelling an iqlab meem                        7,248
    #        already hold a separate one                        445
    #        hold none                                        6,664
    #           ... and a meem-sized body sits directly under
    #               the tanween, in the ADJACENT line            29   <- the defect
    #
    # Twenty-nine, and 28 of them are the same 31.1-unit glyph. Text says the word owns a
    # meem, geometry says which piece of ink it is, and the line gap says why it went
    # astray — the three signals this project asks for before anything moves.
    if os.environ.get("QSVG_IQLINE", "1") != "0":
        _IQ_TAN = ("kasratan", "fathatan", "dammatan")
        _iqw = []
        for _wi2, _ati2 in assignment:
            if not _wi2:
                continue
            _eli = [e for a in _ati2 for e in a["els"]]
            _bli = [e for e in _eli if e["kind"] == "body"]
            if not _bli:
                continue
            _lni = [e.get("line") for e in _bli if e.get("line")]
            _iqw.append({"w": _wi2, "at": _ati2, "els": _eli,
                         "ln": max(set(_lni), key=_lni.count) if _lni else 0})
        for _src in _iqw:
            _ti = _src["w"]["uthmani"]
            if not any(c in _ti for c in "\u06ed\u06e2"):
                continue
            if any((e.get("mark") or "") == "meem-iqlab" for e in _src["els"]):
                continue
            _anch = [e for e in _src["els"]
                     if e.get("mark") in _IQ_TAN and not e.get("mkpart")]
            if not _anch and _dktext_on():
                # Under QSVG_DKTEXT the iqlab stroke is budgeted (and named)
                # PLAIN — fatha/kasra/damma — so the tanween-name anchor never
                # exists. Anchor instead on the plain stroke of the haraka the
                # DK text writes before its ۢ/ۭ, nearest the word's left edge
                # (the iqlab always ends the word); the tight geometric window
                # below is unchanged and still does the deciding.
                _pf = next((("damma",) if _ti[i] == "ُ"
                            else ("fatha", "kasra")
                            for i in range(len(_ti) - 1)
                            if _ti[i] in "َُِ" and _ti[i + 1] in "ۭۢ"), None)
                if _pf:
                    _pool = [e for e in _src["els"]
                             if e.get("mark") in _pf and not e.get("mkpart")]
                    if _pool:
                        _anch = [min(_pool, key=lambda e: e["x1"])]
            for _tan in _anch:
                _tcx = (_tan["x1"] + _tan["x2"]) / 2
                for _oth in _iqw:
                    if _oth is _src or abs(_oth["ln"] - _src["ln"]) != 1:
                        continue
                    for _ei in list(_oth["els"]):
                        if _ei["kind"] != "body" or _ei.get("mkpart"):
                            continue
                        _ari = (_ei["x2"] - _ei["x1"]) * (_ei["y2"] - _ei["y1"])
                        if not (18.0 <= _ari <= 45.0):
                            continue
                        if _human_letter_label(_ei):
                            continue
                        if abs((_ei["x1"] + _ei["x2"]) / 2 - _tcx) > 3.5:
                            continue
                        if not (_tan["y2"] - 1.0 <= _ei["y1"] <= _tan["y2"] + 6.0):
                            continue
                        for _ai in _oth["at"]:
                            if _ei in _ai["els"]:
                                _ai["els"].remove(_ei)
                                break
                        _oth["els"] = [x for x in _oth["els"] if x is not _ei]
                        put_in_ligature(_src["at"], _ei)
                        _src["els"].append(_ei)
                        _ei["kind"] = "mark"
                        _ei["mark"] = "meem-iqlab"
                        break

    # A letter's dots welded into the waqf sign above them.
    #
    # The same mistake as the tanween weld, in the other composer: a stop sign takes in
    # the blobs beneath it, and beneath a stop sign at the end of a word are that word's
    # last letter's dots. `حَرْثِهِۦ ۖ` on p485 ends holding NO dots at all where its
    # spelling asks for three — the ث's dot and two-dots are both inside the صلى.
    #
    # A sign really is drawn in several pieces, so most welds are right; what separates
    # them is that a piece of the SIGN overlaps the sign vertically, while a letter's
    # dots sit clear of it, towards the letters. Usually those letters are the sign's own
    # word; on p556 they are not — `صُوَرَكُمْ ۖ` on line 6 holds `بَصِيرٌ`'s ب dot, drawn
    # ABOVE its own sign and inside `بَصِيرٌ`'s letters on line 5 — so the blob is offered
    # to the sign's word first and, if that word's dots are already right, to the word
    # whose letters it is actually drawn among. With the text as the third signal:
    #
    #     overlaps the sign                            2,598   leave alone
    #     clear of it, dot-sized, word's dots are right   13    leave alone
    #     clear of it, dot-sized, word SHORT of dots        8   <- the defect
    #
    # Eight pieces, seven words. How many dots each stands for comes from its width, the
    # measured 2.38 units per blob, and only widths that land squarely on a whole number
    # of blobs are taken.
    if os.environ.get("QSVG_PAUSEDOT", "1") != "0":
        _PD_BYN = {1: "dot", 2: "two-dots", 3: "three-dots"}
        _pdw = []
        for _w0, _a0 in assignment:
            if not _w0:
                continue
            _e0 = [e for a in _a0 for e in a["els"]]
            _b0 = [e for e in _e0 if e["kind"] == "body"]
            if not _b0:
                continue
            _pdw.append({"w": _w0, "at": _a0, "els": _e0,
                         "x1": min(e["x1"] for e in _b0), "x2": max(e["x2"] for e in _b0),
                         "y1": min(e["y1"] for e in _b0), "y2": max(e["y2"] for e in _b0)})

        def _pd_short(rec):
            return dot_budget(rec["w"]["uthmani"]) - sum(
                {"dot": 1, "two-dots": 2, "three-dots": 3}.get(e.get("mark") or "", 0)
                for e in rec["els"] if not e.get("mkpart"))

        for _host in _pdw:
            for _mp in list(_host["els"]):
                if (_mp.get("mark") or "") != "pause" or _mp.get("mkpart"):
                    continue
                for _mem in list(_mp.get("mkmembers") or []):
                    if not (_mem["y1"] > _mp["y2"] + 0.05 or _mem["y2"] < _mp["y1"] - 0.05):
                        continue              # a piece of the sign itself
                    _bl = (_mem["x2"] - _mem["x1"]) / 2.38
                    _np = int(round(_bl))
                    if _np not in _PD_BYN or abs(_bl - _np) >= 0.28:
                        continue              # not a whole number of drawn dots
                    # whose dots are they: the sign's own word if it is short, else the
                    # word whose LETTERS the blob is drawn among
                    _own = _host if _pd_short(_host) > 0 else None
                    if _own is None:
                        _cx = (_mem["x1"] + _mem["x2"]) / 2
                        _cy = (_mem["y1"] + _mem["y2"]) / 2
                        for _cand in _pdw:
                            if _cand is _host or _pd_short(_cand) <= 0:
                                continue
                            if not (_cand["x1"] - 1.0 <= _cx <= _cand["x2"] + 1.0):
                                continue
                            if not (_cand["y1"] - 2.0 <= _cy <= _cand["y2"] + 2.0):
                                continue
                            _own = _cand
                            break
                    if _own is None:
                        continue
                    _mem["mark"] = _PD_BYN[_np]
                    _mem.pop("mkpart", None)
                    _mp["mkmembers"] = [x for x in _mp["mkmembers"] if x is not _mem]
                    if _own is not _host:
                        for _a2 in _host["at"]:
                            if _mem in _a2["els"]:
                                _a2["els"].remove(_mem)
                                break
                        _host["els"] = [x for x in _host["els"] if x is not _mem]
                        put_in_ligature(_own["at"], _mem)
                        _own["els"].append(_mem)

    # A letter's dots welded into the mark above them.
    #
    # `compose_tanween` joins a vowel to the stroke below it, which is right when the word
    # spells a tanween and wrong when what is below is simply the dots of the letter the
    # vowel sits on. Registering MushafDatabase's decomposition on p210 makes it
    # unmistakable: their `two dots` for `تُتْلَىٰ` is at 300.88..305.24 / 19.54..22.11 and
    # our welded `damma` twin is at 300.88..305.23 / 19.53..22.11 — the same ink to a
    # hundredth of a unit, one of us calling it dots and the other half a dammatan.
    #
    # It happens under other marks too: a dot under a shadda on p117, under a kasra on
    # p216, under a small-circle on p519. So the host is not the signal. Two things are:
    # the twin's SHAPE — a whole number of 2.38-unit blobs, area 3 to 18, where a
    # tanween's second stroke is 26 to 35 — and whether the word is SHORT of dots. Over
    # 604 pages that pair is exact:
    #
    #     dot-shaped twin, word's dots already right   5,766   leave alone
    #     dot-shaped twin, word SHORT of dots              9   <- the defect
    #
    # The word's own spelling is deliberately NOT used to veto: `قُرْبَةٌۭ` on p202 does
    # spell a dammatan, and holds a real one (areas 30.5 and 26.8) somewhere else; the
    # 13.8-unit blob welded to its damma is the ة's two dots. Testing "does the word spell
    # a tanween" kept that one broken.
    if os.environ.get("QSVG_UNWELD", "1") != "0":
        _UW_BYN = {1: "dot", 2: "two-dots", 3: "three-dots"}
        # One drawn dot, measured on THIS page. 2.38 units is the mushaf-wide figure and
        # it is wrong on the pages that are set at their own scale: p2 draws its dots
        # 1.70 wide and its two-dots 3.64, so a constant threshold reads every blob there
        # as a fraction of a dot and the rule silently skips the page. `يُنفِقُونَ`
        # stayed two dots short for exactly that reason.
        _pdots = sorted((e["x2"] - e["x1"])
                        for _w0, _a0 in assignment if _w0
                        for _a1 in _a0 for e in _a1["els"]
                        if (e.get("mark") or "") == "dot" and not e.get("mkpart"))
        _DW = _pdots[len(_pdots) // 2] if _pdots else 2.38
        _ASCALE = (_DW / 2.38) ** 2
        for _wu, _atu in assignment:
            if not _wu:
                continue
            _elu = [e for a in _atu for e in a["els"]]
            if sum({"dot": 1, "two-dots": 2, "three-dots": 3}.get(e.get("mark") or "", 0)
                   for e in _elu if not e.get("mkpart")) >= dot_budget(_wu["uthmani"]):
                continue                      # not short: nothing to recover
            for _mu in _elu:
                if _mu.get("mkpart") or (_mu.get("mark") or "") in (
                        "", "pause", "dot", "two-dots", "three-dots"):
                    # A waqf sign is QSVG_PAUSEDOT's business. A DOT cluster is nobody's:
                    # its label already says how many blobs it stands for, so its welded
                    # twin is counted through the master and unwelding it counts the same
                    # ink twice. `حَيْثُ`'s ث is drawn as a two-dots and a dot welded
                    # together; separating them credited the word with four where three
                    # are drawn. Six words went wrong that way before this line existed.
                    continue
                for _eu in list(_mu.get("mkmembers") or []):
                    _wdu = _eu["x2"] - _eu["x1"]
                    _aru = _wdu * (_eu["y2"] - _eu["y1"])
                    _bl = _wdu / _DW
                    _nu = int(round(_bl))
                    if _nu not in _UW_BYN or abs(_bl - _nu) >= 0.28:
                        continue              # not a whole number of drawn dots
                    if not (3.0 * _ASCALE <= _aru <= 18.0 * _ASCALE):
                        continue              # a tanween's second stroke is 26-35
                    _eu["mark"] = _UW_BYN[_nu]
                    _eu.pop("mkpart", None)
                    _mu["mkmembers"] = [x for x in _mu["mkmembers"] if x is not _eu]

    # The rare stop marks, read as letter dots.
    #
    # `۪` `۫` `۬` are small round stops that look like a dot and are drawn about twice the
    # size of one — a dot in this art is 2.38 x 2.36, area 5.6, everywhere. Over all 604
    # pages exactly THREE `dot` elements exceed twice that area, and all three sit in a
    # word whose spelling carries one of these characters; the other 64,586 dots are
    # normal size, including the 70 that share a word with one of these stops and really
    # are the word's own dots. Size and spelling agree, with nothing in between.
    #
    # They are labelled `pause`, which is what audit_marks already calls them: its
    # TEXT_WANT["pause"] lists `۬ ۪ ۫ ۣ` beside the waqf signs. So one correction settles
    # both counts — the word stops being credited with a dot it does not have and starts
    # holding the stop its spelling asks for.
    if os.environ.get("QSVG_RARESTOP", "1") != "0":
        _RARE_CH = "\u06ea\u06eb\u06ec\u06e3"
        _DOT_AREA = 5.6
        for _wr, _atr in assignment:
            if not _wr or not any(c in _wr["uthmani"] for c in _RARE_CH):
                continue
            for _ar in _atr:
                for _er in _ar["els"]:
                    if (_er.get("mark") or "") != "dot" or _er.get("mkpart"):
                        continue
                    if (_er["x2"] - _er["x1"]) * (_er["y2"] - _er["y1"]) <= 2.0 * _DOT_AREA:
                        continue
                    _er["mark"] = "pause"
                    for _mr in _er.get("mkmembers", []):
                        _mr["mark"] = "pause"

    # A mark the wrong SIZE for what it is called, drawn in another line's band.
    #
    # The art draws one glyph per mark, so a family's drawn area is a point rather than a
    # range — measured over all 604 pages, sukun is 13.0 at both the median and the 99th
    # percentile, damma 35.4/35.4, wasla 22.6/22.6, fatha 25.1/32.8. Only 46 elements in
    # the whole mushaf fall outside a third to three times their family's median, and
    # once the fused iqlab meem and the muʿānaqah are set aside, exactly FIVE of those are
    # also drawn outside their own word's line band. Two independent impossibilities on
    # the same element.
    #
    # Four are the same defect: a fatha of area ~80.4 against a median of 25.1, sitting in
    # the band of the line above or below, touching a word there that is short of exactly
    # one letter piece by the joining rules — p467 `وَٱلْأَحْزَابُ` 5 of 6, p576
    # `يَرْتَابَ` 2 of 3, p529 `ٱلْكَذَّابُ` 3 of 4, p589 `مُدَّتْ` 1 of 2. The blob is
    # that word's missing letter. On p589 it is one defect wearing two faces: `مُدَّتْ`
    # measures 63% of its share of the line while `يَـٰٓأَيُّهَا`, holding its `ت`, counts
    # three pieces where two are allowed.
    #
    # The fifth is the opposite tail. Abdullah found `ٱلصَّـٰلِحَـٰتِ` on p590 holding a
    # "kasra" of area 4.4 where its own two kasras are 21 — a dot, 37 units below the
    # word, in the gap BETWEEN two lines where the ayah marker sits. There is no word to
    # give it to, so the only correction is to stop counting it.
    if os.environ.get("QSVG_MISCLASS", "1") != "0":
        # measured medians, in square page units
        _MED = {"fatha": 25.1, "kasra": 21.2, "damma": 35.4, "sukun": 13.0,
                "shadda": 14.0, "hamza": 15.6, "wasla": 22.6, "small-alef": 12.5,
                "maddah": 21.0, "small-circle": 13.0, "fathatan": 17.5,
                "kasratan": 17.5, "dammatan": 30.4, "small-waw": 31.7,
                "small-ya": 29.8, "dot": 5.6, "two-dots": 12.4, "three-dots": 12.4}
        _BAND_PAD = 10.0          # from the 160x cliff at 10 units

        _mrecs = []
        for _wm2, _atm2 in assignment:
            if not _wm2:
                continue
            _em2 = [e for a in _atm2 for e in a["els"]]
            _bm2 = [e for e in _em2 if e["kind"] == "body"]
            if not _bm2:
                continue
            _lm2 = [e.get("line") for e in _bm2 if e.get("line")]
            _mrecs.append({"w": _wm2, "at": _atm2, "els": _em2, "b": _bm2,
                           "ln": max(set(_lm2), key=_lm2.count) if _lm2 else 0})
        _mband = {}
        for _r2 in _mrecs:
            _lo2, _hi2 = _mband.get(_r2["ln"], (1e9, -1e9))
            _mband[_r2["ln"]] = (min(_lo2, min(b["y1"] for b in _r2["b"])),
                                 max(_hi2, max(b["y2"] for b in _r2["b"])))

        def _runs(bods):
            """Connected runs of ink, the same count score_both and the audits use."""
            sp2 = sorted((b["x1"], b["x2"]) for b in bods)
            if not sp2:
                return 0
            n2, cur2 = 1, sp2[0][1]
            for a2, b2 in sp2[1:]:
                if a2 <= cur2 + 0.4:
                    cur2 = max(cur2, b2)
                else:
                    n2 += 1
                    cur2 = b2
            return n2

        for _r2 in _mrecs:
            for _e2 in list(_r2["els"]):
                _fam2 = _e2.get("mark")
                if _e2["kind"] == "body" or _e2.get("mkpart") or _fam2 not in _MED:
                    continue
                _ar2 = (_e2["x2"] - _e2["x1"]) * (_e2["y2"] - _e2["y1"])
                _big = _ar2 > 3.0 * _MED[_fam2]
                _small = _ar2 < _MED[_fam2] / 3.0
                if not (_big or _small):
                    continue
                _lo2, _hi2 = _mband.get(_r2["ln"], (-1e9, 1e9))
                _cy2 = (_e2["y1"] + _e2["y2"]) / 2
                if _lo2 - _BAND_PAD <= _cy2 <= _hi2 + _BAND_PAD:
                    # Inside its own line, so nothing about its PLACE is wrong — but a
                    # blob three times too big for the mark it is called, in a word that
                    # draws fewer connected runs of ink than the joining rules allow, is
                    # that word's missing letter. Over 604 pages only four marks exceed
                    # three times their family's median at all, and two of them are in a
                    # word short of pieces: `فَٱلزَّٰجِرَٰتِ` on p446, whose 82.8-unit
                    # "kasra" is the ت (MushafDatabase draws `text ت` at the same
                    # 189.24..201.14), and `يُكَذِّبُ` on p588. Nothing moves; only the
                    # claim that it is a mark is withdrawn, which also restores the word's
                    # letter extent so its own dots can be found around it.
                    if _big and _runs(_r2["b"]) < max(1, len(segment_word(
                            _r2["w"]["uthmani"]))):
                        _e2["kind"] = "body"
                        _e2.pop("mark", None)
                        _r2["b"].append(_e2)
                        for _m3 in _e2.get("mkmembers", []):
                            _m3["kind"] = "body"
                            _m3.pop("mark", None)
                    continue                  # right size question, wrong place to ask it
                _home = [L for L, (lo, hi) in _mband.items()
                         if lo - _BAND_PAD <= _cy2 <= hi + _BAND_PAD]
                if _big and _home:
                    # a letter: give it to the word it touches on the band it is drawn
                    # in, and only if that word is SHORT of pieces — the third signal
                    _cand = None
                    for _L in _home:
                        for _t2 in _mrecs:
                            if _t2["ln"] != _L or _t2 is _r2:
                                continue
                            _ov2 = max(min(b["x2"], _e2["x2"]) - max(b["x1"], _e2["x1"])
                                       for b in _t2["b"])
                            if _ov2 < -2.0:
                                continue
                            if _runs(_t2["b"]) >= max(1, len(segment_word(
                                    _t2["w"]["uthmani"]))):
                                continue      # it already has every piece it may have
                            if _cand is None or _ov2 > _cand[1]:
                                _cand = (_t2, _ov2)
                    if _cand is None:
                        continue
                    for _a2 in _r2["at"]:
                        if _e2 in _a2["els"]:
                            _a2["els"].remove(_e2)
                            for _m2 in _e2.get("mkmembers", []):
                                if _m2 in _a2["els"]:
                                    _a2["els"].remove(_m2)
                            break
                    put_in_ligature(_cand[0]["at"], _e2)
                    _e2["kind"] = "body"
                    _e2.pop("mark", None)
                    for _m2 in _e2.get("mkmembers", []):
                        _m2["kind"] = "body"
                        _m2.pop("mark", None)
                elif _small and not _home:
                    # too small for what it is called and in no line's band at all: it is
                    # ornament, not this word's diacritic. Nothing moves; it stops being
                    # counted.
                    _e2.pop("mark", None)
                    _e2.pop("mkmembers", None)
                    _e2["mkpart"] = True

    # The mirror image: a MARK the classifier already named, kept as a letter.
    #
    # `apply_shape_labels` writes `lab` on every element from its outline, whatever the
    # baseline test decided the element was. Where the two disagree the label is often
    # right and the kind wrong, and the disagreement is settled by two further facts that
    # are already to hand: whether the blob is the right SIZE for the mark it is called,
    # and whether the word's spelling still asks for one.
    #
    # All three together are decisive. Over 604 pages there are 105 bodies the classifier
    # called a fatha that are the right size for one, and of those only 15 sit in a word
    # short of a fatha; a further 701 are the wrong size and are left alone. Those 15 are
    # the other half of the exchange the size rule above uncovers — on p589
    # `يَـٰٓأَيُّهَا` gives up an 80-unit blob that is `مُدَّتْ`'s missing `ت` and takes
    # back a 12.6-unit blob that is its own third fatha — and they also close
    # `ٱلْمُحْصَنَـٰتِ` on p350 and `ٱلصَّـٰلِحَـٰتِ` on p590, both reported by eye.
    #
    # Runs AFTER the size rule, so a blob demoted to a letter there is not promoted
    # straight back; it cannot be, since it fails the size test that sent it there.
    if os.environ.get("QSVG_LABKIND", "1") != "0":
        _LK_MED = {"fatha": 25.1, "kasra": 21.2, "damma": 35.4, "sukun": 13.0,
                   "shadda": 14.0, "small-alef": 12.5, "maddah": 21.0,
                   "fathatan": 17.5, "kasratan": 17.5, "dammatan": 30.4,
                   "small-waw": 31.7, "small-ya": 29.8, "two-dots": 12.4}
        _LK_CH = {"fatha": "\u064e", "kasra": "\u0650", "damma": "\u064f",
                  "sukun": "\u0652", "shadda": "\u0651", "small-alef": "\u0670",
                  "maddah": "\u0653", "fathatan": "\u064b", "kasratan": "\u064d",
                  "dammatan": "\u064c", "small-waw": "\u06e5", "small-ya": "\u06e6"}
        for _wk, _atk in assignment:
            if not _wk:
                continue
            _elk = [e for a in _atk for e in a["els"]]
            for _ek in _elk:
                if _ek["kind"] != "body" or _ek.get("mkpart"):
                    continue
                _lk = _ek.get("lab")
                if _lk not in _LK_MED or _lk not in _LK_CH:
                    continue
                _ark = (_ek["x2"] - _ek["x1"]) * (_ek["y2"] - _ek["y1"])
                _mk2 = _LK_MED[_lk]
                if not (_mk2 / 3.0 <= _ark <= 3.0 * _mk2):
                    continue
                _need = _wk["uthmani"].count(_LK_CH[_lk]) - sum(
                    1 for x in _elk if x.get("mark") == _lk and not x.get("mkpart"))
                if _need <= 0:
                    continue
                _ek["kind"] = "mark"
                _ek["mark"] = _lk

    # The small waw `ۥ` and small ya `ۦ` of a pronominal suffix, left as LETTERS.
    #
    # These are the marks CLAUDE.md records as the session's biggest single win — read
    # from the text because nothing in the ink says "mark". Ten of them the recovery
    # never reached, and they are still classified as body, which is why the words
    # holding them draw more connected runs of ink than the Arabic joining rules allow:
    # `كِتَـٰبَهُۥ` is one piece `كتبه` and comes out as two. Six of the eight words in the
    # whole mushaf with a piece surplus are this, and the piece surplus is one of the two
    # measures where MushafDatabase is still ahead of us.
    #
    # Three outline signatures carry it, and they are exact: over all 604 pages they
    # appear on ten elements, every one a body, and nine sit in a word whose spelling has
    # a `ۥ` or a `ۦ` and which holds no such mark. The tenth is `كَانَ` on p589, which
    # spells neither and stands next to `إِنَّهُۥ`, which spells one and has none — so the
    # shape says what the ink is and the text says whose it is, the two signals this
    # project requires before anything moves.
    #
    # The label comes from the OWNER'S SPELLING, not from the signature: a shape table
    # that names the mark would be a third thing to keep right, and the text already
    # knows which of the two it is.
    if os.environ.get("QSVG_SUFFIX", "1") != "0":
        _SUF_SIG = ("3678ca350617", "bc4bcbe3ab5b", "232f8e292d3e")
        _swords = [(w, at) for w, at in assignment if w]

        def _suf_need(w, els, fam):
            ch = "\u06e5" if fam == "small-waw" else "\u06e6"
            alt = "" if fam == "small-waw" else "\u06e7"
            n = w["uthmani"].count(ch) + (w["uthmani"].count(alt) if alt else 0)
            held = sum(1 for e in els
                       if e.get("mark") == fam and not e.get("mkpart"))
            return n - held

        for _i, (_w, _at) in enumerate(_swords):
            for _e in [x for a in _at for x in a["els"]]:
                if _e["kind"] != "body" or (_e.get("sig") or "")[:12] not in _SUF_SIG:
                    continue
                # whose is it: this word, else the neighbour in reading order
                _tgt = None
                for _j in (_i, _i - 1, _i + 1):
                    if not (0 <= _j < len(_swords)):
                        continue
                    _w2, _at2 = _swords[_j]
                    _els2 = [x for a in _at2 for x in a["els"]]
                    for _fam in ("small-waw", "small-ya"):
                        if _suf_need(_w2, _els2, _fam) > 0:
                            _tgt = (_j, _fam)
                            break
                    if _tgt:
                        break
                if not _tgt:
                    continue                  # already accounted for; leave it alone
                _j, _fam = _tgt
                if _j != _i:
                    for _a in _at:
                        if _e in _a["els"]:
                            _a["els"].remove(_e)
                            break
                    put_in_ligature(_swords[_j][1], _e)
                _e["kind"] = "mark"
                _e["mark"] = _fam
                for _m in _e.get("mkmembers", []):
                    _m["kind"] = "mark"
                    _m["mark"] = _fam

    # A mark belonging to no word at all, drawn among a word's letters.
    #
    # 3,396 marks end up owned by nothing, and almost all of them are page furniture with
    # no word's letters anywhere near. A handful are not: the ت's two dots in
    # `فَٱلزَّٰجِرَٰتِ` on p446 sit at 192.69..197.24, squarely inside that word, and the
    # word is short by exactly two dot units.
    #
    # It runs after the size rule above, and has to: the word's letter extent only reaches
    # those dots once its ت has stopped being called a kasra. Before that the dots fall
    # two units outside the word and nothing claims them.
    if os.environ.get("QSVG_ADOPT", "1") != "0":
        _ad_orph, _ad_w, _ad_seen = [], [], set()
        for _wa, _ata in assignment:
            _ela = [e for a in _ata for e in a["els"]]
            if _wa is None:
                for _ea in _ela:
                    _sg = (round(_ea["x1"], 2), round(_ea["y1"], 2), _ea["kind"])
                    if _sg not in _ad_seen:
                        _ad_seen.add(_sg)
                        _ad_orph.append((_ea, _ata))
                continue
            _ba = [e for e in _ela if e["kind"] == "body"]
            if _ba:
                _ad_w.append({"w": _wa, "at": _ata, "els": _ela,
                              "x1": min(e["x1"] for e in _ba), "x2": max(e["x2"] for e in _ba),
                              "y1": min(e["y1"] for e in _ba), "y2": max(e["y2"] for e in _ba)})
        for _ea, _ata in _ad_orph:
            _u = {"dot": 1, "two-dots": 2, "three-dots": 3}.get(_ea.get("mark") or "", 0)
            if not _u or _ea["kind"] == "body" or _ea.get("mkpart") or _ea.get("standalone"):
                continue
            _cxa = (_ea["x1"] + _ea["x2"]) / 2
            _cya = (_ea["y1"] + _ea["y2"]) / 2
            for _ha in _ad_w:
                if not (_ha["x1"] - 1.0 <= _cxa <= _ha["x2"] + 1.0):
                    continue
                if not (_ha["y1"] - 9.0 <= _cya <= _ha["y2"] + 9.0):
                    continue
                if dot_budget(_ha["w"]["uthmani"]) - sum(
                        {"dot": 1, "two-dots": 2, "three-dots": 3}.get(x.get("mark") or "", 0)
                        for x in _ha["els"] if not x.get("mkpart")) != _u:
                    continue              # only if it accounts for the whole shortfall
                for _aa in _ata:
                    if _ea in _aa["els"]:
                        _aa["els"].remove(_ea)
                        break
                put_in_ligature(_ha["at"], _ea)
                _ha["els"].append(_ea)
                break

    # These three corrections run AFTER the overrides, because they read the finished
    # assignment. Placed before it they saw the wrong owner: on p27 the iqlab meem that
    # `ذَٰلِكَ` ends up holding is still inside `بِإِحْسَـٰنٍۢ` at that point — a word
    # that really does spell one — so the rule correctly skipped it and the defect
    # survived. None of the three moves ink between words, so running them last cannot
    # override a human's or the adjudicator's placement.
    # An iqlab meem the word does not spell, sitting on the baseline, is a LETTER.
    #
    # `ۢ` is a superscript meem: it rides above the letters. Measured over every seventh
    # page, all 62 iqlab marks in words that spell one sit at a median of 0.09 of the
    # body's height — near its top — while the only two in words that spell none sit at
    # 0.70 and 0.77, down among the letters. Both are `ذَٰلِكَ`, whose `ذ` is read as an
    # iqlab meem and so drops out of the word's letter ink: the word measures two thirds
    # of its share of the line, four times over in the width audit.
    #
    # Both signals are needed. Seven of the 62 genuine marks also sit below the middle,
    # so position alone would take real iqlabs away; and the text alone cannot say which
    # piece of ink is meant. Together they are exact — the same two-signals rule that
    # governs every other transfer here.
    # Late iqlab-meem self-rescue. By now every mover has run, and a word's own
    # small م can have ARRIVED as one of its body pieces after both early
    # recoveries already passed (p136 أَلِيمٌۢ receives it from بِمَا
    # mid-pipeline, where the next-word claim rightly refused a donor it would
    # have left bodyless). Same evidence as the early passes: the text's ۢ/ۭ
    # budget, a م-sized piece at the word's left edge, and the joining rules —
    # it only ever runs on a PIECE SURPLUS, so it can never eat a real letter.
    if os.environ.get("QSVG_IQLATE", "1") == "1":
        for _wq, _atq in assignment:
            if not _wq:
                continue
            _txt = _wq["uthmani"] or ""
            _ptx3 = _wq.get("qpc") or _txt
            _wantm = _txt.count("ۢ") + _txt.count("ۭ")
            if not _wantm or not ("ۢ" in _ptx3 or "ۭ" in _ptx3):
                continue      # the PRINT draws no م here
            _els = [e for a in _atq for e in a["els"]]
            _bod = [e for e in _els if e["kind"] == "body"]
            if not _bod:
                continue
            _y1 = min(e["y1"] for e in _bod)
            _y2 = max(e["y2"] for e in _bod)
            _mks = [e for e in _els if e.get("mark") == "meem-iqlab"
                    and not e.get("mkpart")]

            # ۢ is a SUPERSCRIPT م and rides high beside its tanween; a
            # "meem-iqlab" sitting in the lower half of the word's band is a
            # letter stroke mislabeled (p222 تَارِكٌۢ carved it out of the ك)
            # and does not satisfy the budget
            def _high(e):
                return ((e["y1"] + e["y2"]) / 2 - _y1) / max(1e-6,
                                                             _y2 - _y1) <= 0.5
            _good = [e for e in _mks if _high(e)] if "ۢ" in _txt else _mks
            if len(_good) >= _wantm:
                continue
            _nseg = max(1, len(segment_word(_txt)))
            if len(_bod) <= _nseg:
                continue              # no surplus piece: nothing to rescue
            # SECOND SIGNAL, same as _IQTAN's rescue: the true م rides beside
            # the word's OWN iqlab tanween stroke. Anchoring on the left edge
            # alone misfired at consecutive-iqlab boundaries (p414 صَبَّارٍۢ
            # beside شَكُورٍۢ), naming the neighbour's pieces.
            _anchor = [e for e in _els
                       if e.get("mark") in ("fathatan", "kasratan", "dammatan",
                                            "fatha", "kasra", "damma")
                       and not e.get("mkpart")]
            if not _anchor:
                continue
            _an = min(_anchor, key=lambda e: e["x1"])   # word-final tanween
            _ax = (_an["x1"] + _an["x2"]) / 2
            _ay = (_an["y1"] + _an["y2"]) / 2
            _rx1 = min(e["x1"] for e in _bod)
            _cand = [e for e in _bod
                     if 2.0 <= e["x2"] - e["x1"] <= 6.0
                     and 5.0 <= e["y2"] - e["y1"] <= 12.0
                     and (e["x1"] + e["x2"]) / 2 - _rx1 <= 8.0
                     and abs((e["x1"] + e["x2"]) / 2 - _ax)
                     + abs((e["y1"] + e["y2"]) / 2 - _ay) <= 14.0]
            if not _cand:
                continue
            _e = min(_cand, key=lambda e: e["x1"])
            _e["kind"] = "mark"
            _e["mark"] = "meem-iqlab"
            _e.pop("lab", None)
            # the true م found: a low impostor goes back to the letter it was
            # carved from
            for _m in _mks:
                if not _high(_m):
                    _m["kind"] = "body"
                    _m.pop("mark", None)

    # Cross-LINE band steal repair. Validated over all 604 pages 2026-08-26:
    # -10 mark flags, intervals flat, +5 clean pages, zero pages worse
    # (.cache/sweeps/xband vs dk-lines). QSVG_XBAND=0 reverts.
    #
    # A word can hold a mark drawn in the ADJACENT line's band — stolen from the
    # word directly above or below it on the page. The orphan pass deliberately
    # refuses these (its band guard stops at +/-10u), and the stray pass only ever
    # hands ink to a word on the mark's own tagged line, so the family survives
    # both. The measured empty band is the proof (CLAUDE.md): 4,203 marks sit
    # <=10u outside their line band, 26 in 10-15u, and nothing legitimate at
    # 15u or beyond; horizontally nothing at all sits 40-150u from its word.
    #
    # Two signals, or no move: the position proof (>=15u outside the band, or a
    # >=40u horizontal gap) AND the receiving word — the word whose band the ink
    # is actually drawn in, whose letters sit under/over it — must have text-budget
    # capacity for the mark's family AFTER position-aware renaming (a "fatha"
    # descending to the word below becomes that word's kasra candidate, _POS_SWAP).
    # A move that would leave the DONOR below its own budget is refused. Slash
    # families are normally forbidden from cross-word transfer; here the budget
    # gate is the same test the exception demands (receiver group deficit AND
    # donor group surplus), so no slash moves without both.
    #
    # QSVG_XBDBG=1 prints every candidate and the decision; QSVG_XBOUT=<file>
    # appends one JSON line per candidate for the trial report.
    if os.environ.get("QSVG_XBAND", "1") == "1":
        _XB_FAMS = {"pause", "meem-iqlab", "hamza", "small-waw", "small-ya",
                    "maddah", "small-alef", "sukun", "shadda", "small-circle",
                    "fatha", "kasra", "fathatan", "kasratan", "damma",
                    "dammatan"}
        _XB_SLASH = {"fatha", "kasra", "fathatan", "kasratan"}
        _XB_DAMMA = {"damma", "dammatan"}
        _XB_SLASH_CH = "ًࣰٍࣲَِ"
        _XB_DAMMA_CH = "ٌࣱُ"
        _XB_CH = {
            "sukun": "ْۡ", "shadda": "ّ",
            "maddah": "ٓۤ", "small-alef": "ٰ",
            "small-waw": "ۥ", "small-ya": "ۦۧ",
            "small-circle": "۟۠",
            "hamza": "أإؤئٕٔ",
            "meem-iqlab": "ۭۢ",
            "pause": "ۖۗۘۙۚۛۜ",
        }

        def _xb_txt(w, fam):
            t = w["uthmani"] or ""
            if fam == "pause":
                # the waqf budget comes from the KFGQPC text of THIS print
                t = w.get("qpc") or t
            if fam in _XB_SLASH:
                return sum(t.count(c) for c in _XB_SLASH_CH)
            if fam in _XB_DAMMA:
                return sum(t.count(c) for c in _XB_DAMMA_CH)
            return sum(t.count(c) for c in _XB_CH[fam])

        def _xb_held(rec, fam):
            fams = (_XB_SLASH if fam in _XB_SLASH
                    else _XB_DAMMA if fam in _XB_DAMMA else (fam,))
            return sum(1 for e in rec["els"]
                       if e.get("mark") in fams and not e.get("mkpart")
                       and not e.get("standalone"))

        _xrec = []
        for _wx, _atx in assignment:
            if not _wx:
                continue
            _ex = [e for a in _atx for e in a["els"]]
            _bx = [e for e in _ex if e["kind"] == "body"]
            if not _bx:
                continue
            _lx = [e.get("line") for e in _bx if e.get("line")]
            _xrec.append({"w": _wx, "at": _atx, "els": _ex, "b": _bx,
                          "ln": max(set(_lx), key=_lx.count) if _lx else 0})
        # line bands from BODY ink, never the `line` tag — the tag is wrong
        # exactly at line edges (the crossband audit's lesson)
        _xband = {}
        for _rx in _xrec:
            _lo0, _hi0 = _xband.get(_rx["ln"], (1e9, -1e9))
            _xband[_rx["ln"]] = (min(_lo0, min(b["y1"] for b in _rx["b"])),
                                 max(_hi0, max(b["y2"] for b in _rx["b"])))
        _xbyln = {}
        for _rx in _xrec:
            _xbyln.setdefault(_rx["ln"], []).append(_rx)

        def _xovl(bs, e):
            return max((min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]))
                       for b in bs) if bs else -9e9

        _xb_page = int(os.path.splitext(page.name)[0].split("-")[0]
                       .lstrip("0") or 0)
        _xb_out = os.environ.get("QSVG_XBOUT")
        _xb_dbg = os.environ.get("QSVG_XBDBG")

        def _xb_log(rec):
            if _xb_dbg:
                sys.stderr.write("XBAND %s\n" % json.dumps(rec, ensure_ascii=False))
            if _xb_out:
                with open(_xb_out, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        def _xb_move(src, dst, e, name):
            if e.get("_ovr"):
                return                    # human placement outranks the
                                          # crossband corrections (p129 e910)
            """The one way ink changes hands here: atoms via put_in_ligature."""
            for _a in src["at"]:
                if e in _a["els"]:
                    _a["els"].remove(e)
                    for _m in e.get("mkmembers", []):
                        if _m in _a["els"]:
                            _a["els"].remove(_m)
                    break
            if e in src["els"]:
                src["els"].remove(e)
            for _m in e.get("mkmembers", []):
                if _m in src["els"]:
                    src["els"].remove(_m)
            put_in_ligature(dst["at"], e)
            dst["els"].append(e)
            dst["els"].extend(e.get("mkmembers", []))
            # the ink is drawn in the receiver's band — retag it there, or the
            # audits that key on the tag put the receiving WORD on the old line
            if dst.get("ln"):
                e["line"] = dst["ln"]
                for _m in e.get("mkmembers", []):
                    _m["line"] = dst["ln"]
            if name and name != e.get("mark"):
                e["mark"] = name
                for _m in e.get("mkmembers", []):
                    _m["mark"] = name

        def _xb_side(t, e):
            _u = [b for b in t["b"]
                  if min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]) > -0.6] \
                 or t["b"]
            _mid = (min(b["y1"] for b in _u) + max(b["y2"] for b in _u)) / 2
            return "a" if (e["y1"] + e["y2"]) / 2 < _mid else "b"

        def _xb_nearln(cy):
            _tl, _td = None, 1e9
            for _l2, (_l1, _h1) in _xband.items():
                _d2 = max(_l1 - cy, cy - _h1, 0.0)
                if _d2 < _td:
                    _td, _tl = _d2, _l2
            return _tl

        # first sweep: every mark carrying the position proof
        _xcands = []
        for _rx in _xrec:
            for _e in _rx["els"]:
                if _e["kind"] == "body" or _e.get("mkpart") \
                        or _e.get("standalone"):
                    continue
                _fam = _e.get("mark")
                if _fam not in _XB_FAMS:
                    continue
                _lo, _hi = _xband.get(_rx["ln"], (-1e9, 1e9))
                _cy = (_e["y1"] + _e["y2"]) / 2
                _out = max(_lo - _cy, _cy - _hi, 0.0)
                _gap = -_xovl(_rx["b"], _e)
                if _out < 15.0 and _gap < 40.0:
                    continue          # inside both measured bands: legitimate
                # which line's band the ink is actually drawn in — own line
                # allowed only for the horizontal (gap) proof
                _tl = _xb_nearln(_cy)
                if _tl is None or abs(_tl - _rx["ln"]) > 1:
                    continue          # only the adjacent line: a mark drifts
                                      # to a neighbour, it does not cross a page
                if _tl == _rx["ln"] and _gap < 40.0:
                    continue
                _xcands.append((_rx, _e, _fam, _out, _gap, _tl, _cy))

        _xdone = set()
        for _rx, _e, _fam, _out, _gap, _tl, _cy in _xcands:
            if id(_e) in _xdone:
                continue
            _cands = [t for t in _xbyln.get(_tl, ()) if t is not _rx]
            _t = max(_cands, key=lambda t: _xovl(t["b"], _e), default=None)
            _rec = {"page": _xb_page,
                    "holder": "%d:%d:%d" % (_rx["w"]["surah"],
                                            _rx["w"]["ayah"],
                                            _rx["w"]["pos"]),
                    "holder_text": _rx["w"]["uthmani"],
                    "mark": _fam,
                    "x": round((_e["x1"] + _e["x2"]) / 2, 1),
                    "y": round(_cy, 1),
                    "band_out": round(_out, 1), "gap": round(_gap, 1),
                    "holder_line": _rx["ln"], "ink_line": _tl}
            if _t is None or _xovl(_t["b"], _e) < -2.0:
                _rec["decision"] = "refused: no word drawn under the mark"
                _xb_log(_rec)
                continue
            # position-aware rename against the RECEIVER's letters
            _nm = _fam
            if _fam in _POS_SWAP_FAM:
                _nm = _POS_SWAP.get((_fam, _xb_side(_t, _e)), _fam)
            _rec.update({
                "receiver": "%d:%d:%d" % (_t["w"]["surah"],
                                          _t["w"]["ayah"], _t["w"]["pos"]),
                "receiver_text": _t["w"]["uthmani"],
                "new_name": _nm,
                "recv_have": _xb_held(_t, _nm),
                "recv_want": _xb_txt(_t["w"], _nm),
                "donor_have": _xb_held(_rx, _fam),
                "donor_want": _xb_txt(_rx["w"], _fam)})

            # A standalone ء is a LETTER wearing the hamza outline. Where the
            # receiver under the ink spells one and holds none, the stolen
            # "hamza" mark is that letter: it moves and is demoted the same way
            # the late hamza pass demotes an in-word ء (kind body, letter-hamza).
            # p222 كَنزٌ and p260 لِى both hold the ء of a شَىْءٍۢ on the line
            # they poke into.
            if _fam == "hamza" and "ء" in (_t["w"]["uthmani"] or ""):
                _lh_want = _t["w"]["uthmani"].count("ء")
                _lh_have = sum(1 for x in _t["els"]
                               if x.get("lab") == "letter-hamza")
                if _lh_have < _lh_want \
                        and _rec["donor_have"] - 1 >= _rec["donor_want"]:
                    _rec["new_name"] = "letter-hamza"
                    _rec["decision"] = "moved as the receiver's letter ء"
                    _xb_log(_rec)
                    # anything welded to the ء (p260: the ٍ pair of شَىْءٍۢ)
                    # was stolen with it and moves with it — but a LETTER
                    # cannot speak for a mark's count, so the twins re-master
                    # on their own, first stroke counting, the rest welded
                    _mem = list(_e.get("mkmembers") or [])
                    _xb_move(_rx, _t, _e, None)
                    _e["kind"] = "body"
                    _e["mark"] = None
                    _e["lab"] = "letter-hamza"
                    _e["mkmembers"] = []
                    if _mem:
                        _mem[0]["mkpart"] = False
                        _mem[0]["mkmembers"] = _mem[1:]
                        for _m in _mem[1:]:
                            _m["mkpart"] = True
                    _xdone.add(id(_e))
                    continue

            # Two slash strokes side by side are ONE tanween. Where the donor
            # holds a proved PAIR (both carry the position proof, drawn within
            # 8u of each other over the same receiver) and the receiver is
            # missing exactly its tanween, the pair moves as one welded sign —
            # p535 وَلَا holds مَقْطُوعَةٍۢ's kasratan as two stray "fathas".
            _mate = None
            if _fam in _XB_SLASH:
                for _rx2, _e2, _f2, _o2, _g2, _tl2, _cy2 in _xcands:
                    if _e2 is _e or id(_e2) in _xdone or _rx2 is not _rx:
                        continue
                    if _f2 not in _XB_SLASH or _tl2 != _tl:
                        continue
                    if abs((_e2["x1"] + _e2["x2"]) / 2
                           - (_e["x1"] + _e["x2"]) / 2) \
                            + abs(_cy2 - _cy) <= 8.0:
                        _mate = _e2
                        break
            if _mate is not None:
                _tn = "fathatan" if _xb_side(_t, _e) == "a" else "kasratan"
                _tn_ch = {"fathatan": "ًࣰ", "kasratan": "ٍࣲ"}[_tn]
                _tn_want = sum((_t["w"]["uthmani"] or "").count(c)
                               for c in _tn_ch)
                _tn_have = sum(1 for x in _t["els"]
                               if x.get("mark") == _tn and not x.get("mkpart"))
                if _tn_have < _tn_want \
                        and _rec["donor_have"] - 2 >= _rec["donor_want"]:
                    _rec.update({"new_name": _tn,
                                 "decision": "moved as a welded %s pair" % _tn})
                    _xb_log(_rec)
                    _xb_move(_rx, _t, _e, _tn)
                    _xb_move(_rx, _t, _mate, _tn)
                    _mate["mkpart"] = True
                    _e.setdefault("mkmembers", []).append(_mate)
                    _xdone.add(id(_e))
                    _xdone.add(id(_mate))
                    continue

            _recv_ok = _rec["recv_have"] < _rec["recv_want"]
            _don_ok = _rec["donor_have"] - 1 >= _rec["donor_want"]
            # A slash or damma family is counted as a GROUP (the stroke is one
            # and the name positional), but a group test alone let p371 install
            # a surplus fatha on a word missing its kasratan — group balanced,
            # family worse. The move must also improve BOTH families it touches:
            # receiver short of the arriving NAME, donor long of the leaving one.
            if _fam in _XB_SLASH or _fam in _XB_DAMMA:
                _fch = {"fatha": "َ", "kasra": "ِ", "fathatan": "ًࣰ",
                        "kasratan": "ٍࣲ", "damma": "ُ", "dammatan": "ٌࣱ"}

                def _heldf(rec, f):
                    return sum(1 for x in rec["els"]
                               if x.get("mark") == f and not x.get("mkpart")
                               and not x.get("standalone"))

                def _wantf(w, f):
                    return sum((w["uthmani"] or "").count(c) for c in _fch[f])

                _recv_ok = _recv_ok and _heldf(_t, _nm) < _wantf(_t["w"], _nm)
                _don_ok = _don_ok and _heldf(_rx, _fam) > _wantf(_rx["w"], _fam)
            if _recv_ok and _don_ok:
                _rec["decision"] = "moved"
                _xb_log(_rec)
                _xb_move(_rx, _t, _e, _nm)
                _xdone.add(id(_e))
                continue

            # A full receiver can be the other half of an EXCHANGE: it holds a
            # mark of the same group that is itself out of ITS band, drawn over
            # the donor's letters (p577 إِلَّآ / يَخَافُونَ, p599, p439). The
            # 10u threshold is the crossband histogram's edge — the partner is
            # corroborated by the proved mark pointing the other way, so the
            # 10-15u zone (26 marks mushaf-wide) is admissible for it. A swap
            # is budget-neutral, so no count can break.
            if not _recv_ok:
                _grp = (_XB_SLASH if _fam in _XB_SLASH
                        else _XB_DAMMA if _fam in _XB_DAMMA else {_fam})
                _tlo, _thi = _xband.get(_t["ln"], (-1e9, 1e9))
                _back = None
                for _e2 in _t["els"]:
                    if _e2["kind"] == "body" or _e2.get("mkpart") \
                            or _e2.get("standalone") or id(_e2) in _xdone:
                        continue
                    if _e2.get("mark") not in _grp:
                        continue
                    _cy2 = (_e2["y1"] + _e2["y2"]) / 2
                    if max(_tlo - _cy2, _cy2 - _thi, 0.0) < 10.0:
                        continue
                    if _xb_nearln(_cy2) != _rx["ln"]:
                        continue
                    # the give-back mark must be drawn over the donor's own
                    # letters. Relaxing this to -6u admits p577's إِلَّآ /
                    # يَخَافُونَ exchange, but the returned fatha lands in
                    # يَذْكُرُونَ's exclusive core (+1 interval flag): the
                    # mark most probably belongs to يذكرون, a three-way chain
                    # a pairwise swap cannot settle. Strict, measured.
                    if _xovl(_rx["b"], _e2) < -2.0:
                        continue
                    _back = _e2
                    break
                if _back is not None:
                    _nm2 = _back.get("mark")
                    if _nm2 in _POS_SWAP_FAM:
                        _nm2 = _POS_SWAP.get((_nm2, _xb_side(_rx, _back)),
                                             _nm2)
                    _rec.update({"decision": "exchanged",
                                 "back_mark": _back.get("mark"),
                                 "back_new_name": _nm2,
                                 "back_x": round((_back["x1"]
                                                  + _back["x2"]) / 2, 1),
                                 "back_y": round((_back["y1"]
                                                  + _back["y2"]) / 2, 1)})
                    _xb_log(_rec)
                    _xb_move(_rx, _t, _e, _nm)
                    _xb_move(_t, _rx, _back, _nm2)
                    _xdone.add(id(_e))
                    _xdone.add(id(_back))
                    continue

            _rec["decision"] = ("refused: " +
                                ("receiver full" if not _recv_ok
                                 else "donor would go below budget"))
            _xb_log(_rec)

    if os.environ.get("QSVG_IQFIX", "1") == "1":
        for _wq, _atq in assignment:
            if not _wq:
                continue
            _txt = (_wq["uthmani"] or "") + (_wq.get("qpc") or "")
            if any(_c in _txt for _c in "\u06e2\u06ed"):
                continue                      # the word really does carry one
            _els = [e for a in _atq for e in a["els"]]
            _bod = [e for e in _els if e["kind"] == "body"]
            if not _bod:
                continue
            _top = min(e["y1"] for e in _bod)
            _bot = max(e["y2"] for e in _bod)
            for _e in _els:
                if _e.get("mark") != "meem-iqlab":
                    continue
                _f = ((_e["y1"] + _e["y2"]) / 2 - _top) / max(1e-6, _bot - _top)
                if _f > 0.5:
                    _e["kind"] = "body"
                    _e.pop("mark", None)
                    _e.pop("mkpart", None)

    # Dot budgets, settled from the text where the ink is already in the right word.
    #
    # A dot welded into a neighbouring glyph's group stops being counted: the master's
    # label speaks for the whole group. Most of those welds are right — a ج really does
    # own the dot below its curl — but a صلى does not, and when one absorbs the dot of
    # the ف beside it (p27 `بِٱلۡمَعۡرُوفِ`) the word comes out holding one dot where its
    # spelling and MushafDatabase both read two.
    #
    # Un-welding every non-ج pause was tried and is much worse: dot disagreements went
    # from 66 over the mushaf to 150 over the first 120 pages, because the weld is
    # usually correct and breaking it invents a dot. What separates the two cases is not
    # in the ink at all — it is the spelling. So the count comes from the text and the
    # position from the ink, the same way the waqf signs and small waws were recovered:
    # a word the text says is SHORT of dots, holding exactly that many welded dot twins,
    # gets them back. It can never invent a dot, because it only ever runs on a deficit.
    if os.environ.get("QSVG_DOTFIX", "1") == "1":

        for _wd, _atd in assignment:
            if not _wd:
                continue
            _els = [e for a in _atd for e in a["els"]]
            _have = sum(_DOTU_F.get(e.get("mark") or "", 0)
                        for e in _els if not e.get("mkpart"))
            _want = dot_budget(_wd["uthmani"])
            if _have >= _want:
                continue
            _twins = [e for e in _els
                      if e.get("mkpart") and (e.get("mark") or "") in _DOTU_F]
            if not _twins:
                continue
            # The deficit is in UNITS, and a twin inherits its master's label rather
            # than describing itself: the third dot of the `ث` in `فَبَعَثَ` is welded
            # to a `two-dots` master and carries that name, so releasing it at face
            # value adds two where one is owed. Where the twin is narrower than its
            # master it is plainly the smaller mark, and it is renamed down to exactly
            # the units still owed — never up, and never past the deficit.
            _need = _want - _have
            _twins.sort(key=lambda e: _DOTU_F[e["mark"]])
            for _t in _twins:
                if _need <= 0:
                    break
                _u = _DOTU_F[_t["mark"]]
                if _u > _need:
                    _mst = next((m for m in _els if _t in (m.get("mkmembers") or [])), None)
                    if _mst is None or (_t["x2"] - _t["x1"]) >= (_mst["x2"] - _mst["x1"]):
                        continue     # not obviously the smaller of the pair: leave it
                    _name = {1: "dot", 2: "two-dots", 3: "three-dots"}.get(_need)
                    if not _name:
                        continue
                    _t["mark"] = _name
                    _u = _need
                _t.pop("mkpart", None)
                for _m in _els:
                    if _t in (_m.get("mkmembers") or []):
                        _m["mkmembers"] = [x for x in _m["mkmembers"] if x is not _t]
                _need -= _u

    # Mark-TYPE repair (trial, DEFAULT OFF — QSVG_MTYPE=1 to enable).
    # Renames and regroups only; never moves ink between words, never touches
    # atoms, zero pixel change, zero count change. Two families, each with an
    # empty-band proof AND a text confirmation (tools/audit_marktype.py,
    # docs/defects/marktype_rules.md):
    #
    # (a) The لأيات name-crossing. A kasratan can NEVER sit above its word's
    #     band top — clean-subset sabove is empty from -4 to +1 (n=2,585) and
    #     the only 10 above are this pattern: the word's two stacked fathas
    #     welded as a "kasratan pair" at the top, while its true kasratan pair
    #     (QPC open tanween ٖ, drawn as two strokes BELOW) is named
    #     fatha+fatha. Both budgets stay exactly satisfied after the swap, so
    #     the repair is a pure re-labeling.
    #
    # (b) A "meem-iqlab" in a word whose QPC text draws NO meem (open-tanween
    #     encoding ٖ/ٗ/ٞ — uthmani writes the small meem at every non-izhar
    #     tanween, the print draws it only at iqlab). The element is the
    #     tanween's second stroke or its welded outline: QPC-confirmed meems
    #     measure a uniform 3.2x9.5 glyph, these measure w 4.5-11 (926
    #     mushaf-wide). Renamed to the word's tanween as a welded part —
    #     meem-iqlab is never counted and the tanween master count is
    #     unchanged, so no budget moves.
    # REFUTED by blind verification (docs/defects/marktype_verification.md,
    # reported.json item 24): branch (b) renames what is actually the word's
    # FINAL LETTER (~900 words, MDB-arbitrated 58/60) into a mark. Do NOT
    # enable as built; the letter-restore fix ships separately.
    if os.environ.get("QSVG_MTYPE", "0") == "1":
        for _wm, _atm in assignment:
            if not _wm:
                continue
            _els = [e for a in _atm for e in a["els"]]
            _bod = [e for e in _els if e["kind"] == "body"]
            if not _bod:
                continue
            _u = _wm["uthmani"] or ""
            _q = _wm.get("qpc") or ""
            _top = min(e["y1"] for e in _bod)
            _bot = max(e["y2"] for e in _bod)

            # (a) kasratan welded pair above the band top
            _kt = next((e for e in _els
                        if e.get("mark") == "kasratan" and not e.get("mkpart")
                        and any(m.get("mark") == "kasratan"
                                for m in e.get("mkmembers", []))
                        and _top - (e["y1"] + e["y2"]) / 2 > 0.0), None)
            if _kt is not None:
                _fw = _u.count("َ")
                _fh = [e for e in _els if e.get("mark") == "fatha"
                       and not e.get("mkpart") and not e.get("mkmembers")]
                _low = sorted([e for e in _fh
                               if (e["y1"] + e["y2"]) / 2 - _bot > 1.5],
                              key=lambda e: (e["y1"] + e["y2"]))
                if len(_fh) == _fw and len(_low) >= 2:
                    _a2, _b2 = _low[0], _low[1]
                    if abs((_a2["x1"] + _a2["x2"]) / 2
                           - (_b2["x1"] + _b2["x2"]) / 2) < 8.0 \
                            and abs((_a2["y1"] + _a2["y2"]) / 2
                                    - (_b2["y1"] + _b2["y2"]) / 2) < 8.0:
                        # top pair -> the word's two fathas
                        for _m in list(_kt.get("mkmembers", [])):
                            if _m.get("mark") == "kasratan":
                                _m["mark"] = "fatha"
                                _m.pop("mkpart", None)
                                _kt["mkmembers"].remove(_m)
                        if not _kt["mkmembers"]:
                            _kt.pop("mkmembers", None)
                        _kt["mark"] = "fatha"
                        # bottom two strokes -> the kasratan pair
                        _a2["mark"] = _b2["mark"] = "kasratan"
                        _b2["mkpart"] = True
                        _a2["mkmembers"] = _a2.get("mkmembers", []) + [_b2]

            # (b) meem-iqlab at a QPC-meemless word -> tanween part
            if _q and not any(c in _q for c in "ۭۢ"):
                for _e in _els:
                    if _e.get("mark") != "meem-iqlab" or _e.get("mkpart"):
                        continue
                    _tans = [t for t in _els
                             if t.get("mark") in ("fathatan", "kasratan",
                                                  "dammatan")
                             and not t.get("mkpart") and t is not _e]
                    if not _tans:
                        continue
                    _t = min(_tans, key=lambda t:
                             abs((t["x1"] + t["x2"]) / 2
                                 - (_e["x1"] + _e["x2"]) / 2)
                             + abs((t["y1"] + t["y2"]) / 2
                                   - (_e["y1"] + _e["y2"]) / 2))
                    _d = (abs((_t["x1"] + _t["x2"]) / 2
                              - (_e["x1"] + _e["x2"]) / 2)
                          + abs((_t["y1"] + _t["y2"]) / 2
                                - (_e["y1"] + _e["y2"]) / 2))
                    if _d > 16.0:
                        continue      # p95 of measured distances is 13.6
                    _e["mark"] = _t["mark"]
                    _e["mkpart"] = True
                    _t.setdefault("mkmembers", []).append(_e)

    # ------------------------------------------------------------------
    # The muʿānaqah weld, second pass. The weld above (see waqf_places()) runs
    # before the movers and the reviewer overrides, and either can deliver a
    # straggler dot of an occurrence to the owning word AFTER the weld ran:
    # p114's قُلُوبُهُمْۛ ended holding its triangle as a master+part PLUS one
    # loose `pause` dot that a later mover brought home — counted as pause 2/1.
    # Re-normalize: within one word, all recorded pieces of one occurrence are
    # one master and parts. Nothing moves between words here.
    if _places and os.environ.get("QSVG_WPL2", "1") == "1":
        for _wp, _atp in assignment:
            if not _wp:
                continue
            _byocc = {}
            for _a in _atp:
                for _e in _a["els"]:
                    _r = _places.get("%.1f,%.1f,%.1f,%.1f"
                                     % (_e["x1"], _e["y1"], _e["x2"], _e["y2"]))
                    if isinstance(_r, dict):
                        _byocc.setdefault(_r["occ"], []).append(_e)
            for _grp in _byocc.values():
                if len(_grp) < 2:
                    continue
                _grp.sort(key=lambda e: -(e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
                _grp[0]["mark"] = "pause"
                _grp[0]["mkmembers"] = _grp[1:]
                _grp[0].pop("mkpart", None)
                for _m in _grp[1:]:
                    _m["mark"] = "pause"
                    _m["mkpart"] = True
                    _m.pop("mkmembers", None)

    # The muʿānaqah triangle is THREE dots, always — independent of the
    # place table (p2 and half of p112/p114 have no recorded places at all).
    if os.environ.get("QSVG_MNQ3", "1") == "1":
        for _wp, _atp in assignment:
            if not _wp:
                continue
            # The place table only welds pieces it recorded; a muʿānaqah dot
            # the movers digitized differently (p2 رَيْبَ holding 2 of 3,
            # p112 سَنَةࣰۛ's unnamed fragment) stays loose. The occurrence
            # is THREE dots, always: weld nearby loose ink into the master —
            # an unnamed mark fragment freely, a dot-family mark only when
            # the word holds more of that family than its spelling allows
            # (the budget veto keeps the ب's own dot safe).

            if "\u06db" in (_wp.get("qpc") or _wp["uthmani"]):
                _elw = [e for _a in _atp for e in _a["els"]]
                _mst = [e for e in _elw if e.get("mark") == "pause"
                        and not e.get("mkpart")]
                _D1w = "\u0628\u062c\u062e\u0630\u0632\u0636\u0638\u063a\u0641\u0646"
                _txtw = _wp["uthmani"]
                for _m0 in _mst:
                    # a member welded by an earlier pass can be REFERENCED by
                    # two atoms at once — its word's and a wordless one whose
                    # stale header line-tag routes it into the basmalah group
                    # at emit (p2: both triangles complete in memory, a dot
                    # drawn as header ink). One reference only: the atom that
                    # holds the master.
                    _hatom = next((_a for _a in _atp
                                   if _m0 in _a["els"]), _atp[0])
                    for _mm in (_m0.get("mkmembers") or []):
                        for _wo2, _ao2 in assignment:
                            for _a3 in _ao2:
                                if _a3 is _hatom:
                                    continue
                                while _mm in _a3["els"]:
                                    _a3["els"].remove(_mm)
                        if _mm not in _hatom["els"]:
                            _hatom["els"].append(_mm)
                        _mm.pop("line", None) is None
                        _mm["line"] = _m0.get("line")
                    _tot = len(_m0["contours"]) + sum(
                        len(x["contours"]) for x in (_m0.get("mkmembers") or []))
                    if _tot >= 3:
                        continue
                    _cxm = (_m0["x1"] + _m0["x2"]) / 2
                    _cym = (_m0["y1"] + _m0["y2"]) / 2
                    _cand = []

                    def _consider(e, src_atom=None):
                        # a triangle dot may live in the word, in the OTHER
                        # word of the pair, or in no word at all (the p2
                        # fragments sit wordless in the line group) — the
                        # sign floats BETWEEN the words it binds
                        if e is _m0 or e.get("mkpart") or e.get("mkmembers"):
                            return
                        if (e["x2"] - e["x1"]) > 4.5 \
                                or (e["y2"] - e["y1"]) > 4.5:
                            return
                        _d = (((e["x1"] + e["x2"]) / 2 - _cxm) ** 2
                              + ((e["y1"] + e["y2"]) / 2 - _cym) ** 2) ** 0.5
                        if _d > 9.0:
                            return
                        _ar = (e["x2"] - e["x1"]) * (e["y2"] - e["y1"])
                        if not e.get("mark") and _ar <= 8.0:
                            # unnamed dot-sized ink at the triangle site
                            _cand.append((_d, e, src_atom))
                        elif e.get("mark") == "dot":
                            _hdw = sum(1 for x in _elw
                                       if x.get("mark") == "dot"
                                       and not x.get("mkpart"))
                            if _hdw > sum(_txtw.count(c) for c in _D1w):
                                _cand.append((_d, e, src_atom))

                    for e in _elw:
                        _consider(e)
                    if os.environ.get("QSVG_MNQDBG"):
                        print("MNQ %s master(%.0f,%.0f) tot=%d cand=%d"
                              % (_wp["uthmani"], _cxm, _cym, _tot,
                                 len(_cand)), file=sys.stderr)
                        for _wo, _ao in assignment:
                            if _wo:
                                continue
                            for _a2 in _ao:
                                for e in _a2["els"]:
                                    print("  wordless (%.0f,%.0f) %sx%s kind=%s mark=%s"
                                          % (e["x1"], e["y1"],
                                             round(e["x2"]-e["x1"],1),
                                             round(e["y2"]-e["y1"],1),
                                             e.get("kind"), e.get("mark")),
                                          file=sys.stderr)
                    for _wo, _ao in assignment:
                        if _wo:
                            continue
                        for _a2 in _ao:
                            for e in list(_a2["els"]):
                                _consider(e, _a2)
                    for _d, e, _src2 in sorted(_cand, key=lambda t: t[0]):
                        if _tot >= 3:
                            break
                        if e.get("_ovr"):
                            continue
                        if _src2 is not None:
                            _src2["els"].remove(e)
                            _atp[0]["els"].append(e)
                        e["kind"] = "mark"
                        e["mark"] = "pause"
                        e["lab"] = "pause"
                        e["mkpart"] = True
                        e.pop("mkmembers", None)
                        _m0.setdefault("mkmembers", []).append(e)
                        _tot += len(e["contours"])
                # the sign IS the muʿānaqah — its catalog name, not a pause
                # wearing an attribute (Abdullah 2026-08-28): each of the six
                # words holds exactly ONE mark named muanaqah
                for _m0 in _mst:
                    _m0["mark"] = "muanaqah"
                    _m0["lab"] = "muanaqah"
                    for _mm in (_m0.get("mkmembers") or []):
                        _mm["mark"] = "muanaqah"

    # LINE-SET SOLVER (trial, DEFAULT OFF — QSVG_LSOLVE=1 to enable).
    #
    # The ownership rule (Abdullah, 2026-08-26): POSITION OWNS a mark — it
    # belongs to the word whose letter ink it is drawn over, measured against
    # ink and bands, never a stage's `line` tag. THE TEXT CONSTRAINS — each
    # word's per-family counts equal its budget. NAMES FOLLOW POSITION — slash
    # names derive relative to the OWNER (_POS_SWAP), renaming is part of
    # reassignment. RESOLVE GLOBALLY — pairwise transfers are what created the
    # rotations (p350's tail, p599's أولئك←شر←البرية chain), so on any
    # violation the whole line-set's mark→word assignment is re-solved at
    # once, minimum total displacement subject to the budgets. UNIQUENESS OR
    # EYES — a unique optimum differing from the current assignment is
    # applied (put_in_ligature only); ties within 10% become a proposal
    # record (QSVG_LSOLVE_OUT), never a move.
    #
    # Scope is deliberately narrow: the six slash/damma families only — the
    # ones whose name is positional and whose rotations pairwise passes
    # cannot settle. Everything else (pause, meem-iqlab, hamza, small-waw…)
    # already has a measured pass with its own proof band. small-waw/small-ya
    # are NEVER entities here: a trailing ۥ/ۦ legitimately sits x-clear of
    # its word (direction beats distance, ~2000 suffixes).
    #
    # Runs LAST, after the overrides, because a human's placement is an input
    # it must respect: an element whose geometry key is in overrides.json
    # never moves, and an element already on the proposals page
    # (docs/defects/proposals.json, e.g. p350's x14.9 stroke, P1) is under
    # adjudication — it neither moves nor testifies in any budget.
    if os.environ.get("QSVG_LSOLVE", "1") == "1":
        _LS_SLASH = ("fatha", "kasra", "fathatan", "kasratan")
        _LS_FAMS = _LS_SLASH + ("damma", "dammatan")
        _LS_CH = {"fatha": "َ", "kasra": "ِ",
                  "fathatan": "ًࣰ", "kasratan": "ٍࣲ",
                  "damma": "ُ", "dammatan": "ٌࣱ"}
        _LS_GAP = 0.6          # the orphan pass's measured overlap tolerance
        _LS_BAND = 15.0        # the crossband empty band (26 marks in 10-15u)
        _LS_NEAR = 3.0         # a candidate's ink must be under the mark
        _LS_PAIR = 8.0         # two strokes this close are ONE tanween
        _LS_TIE = 0.10         # ties within 10% go to eyes, not to a move
        _LS_CAP = 20000        # combinatorial ceiling; beyond it, propose

        _ls_dbg = os.environ.get("QSVG_LSDBG")
        _ls_out = os.environ.get("QSVG_LSOLVE_OUT")
        _ls_page = int(os.path.splitext(page.name)[0].split("-")[0]
                       .lstrip("0") or 0)

        def _ls_log(rec):
            if _ls_dbg:
                sys.stderr.write("LSOLVE %s\n" % json.dumps(rec, ensure_ascii=False))
            if _ls_out:
                with open(_ls_out, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # -- human decisions are inputs -----------------------------------
        _ls_skip = set()          # geometry keys that must not move
        try:
            for _k in json.load(open(os.path.join(
                    ROOT, ".cache", "review", "overrides.json"))).get(
                        str(_ls_page), {}):
                _ls_skip.add(_k)
        except Exception:
            pass
        _ls_pending = []          # (x1, y1) of elements queued for eyes
        try:
            for _it in json.load(open(os.path.join(
                    ROOT, "docs", "defects", "proposals.json"))).get("items", []):
                if _it.get("page") == _ls_page and "focus_x" in _it:
                    _ls_pending.append((float(_it["focus_x"]),
                                        float(_it["focus_y"])))
        except Exception:
            pass

        def _ls_key(e):
            return "%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])

        def _ls_is_pending(e):
            return any(abs(e["x1"] - px) < 1.5 and abs(e["y1"] - py) < 1.5
                       for px, py in _ls_pending)

        _lrec = []
        for _wl, _atl in assignment:
            if not _wl:
                continue
            _el = [e for a in _atl for e in a["els"]]
            _bl = [e for e in _el if e["kind"] == "body"]
            if not _bl:
                continue
            _ll = [e.get("line") for e in _bl if e.get("line")]
            _lrec.append({"w": _wl, "at": _atl, "els": _el, "b": _bl,
                          "ln": max(set(_ll), key=_ll.count) if _ll else 0})
        _lband = {}
        for _r in _lrec:
            _lo0, _hi0 = _lband.get(_r["ln"], (1e9, -1e9))
            _lband[_r["ln"]] = (min(_lo0, min(b["y1"] for b in _r["b"])),
                                max(_hi0, max(b["y2"] for b in _r["b"])))

        def _ls_ovl(bs, e):
            return max((min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]))
                       for b in bs) if bs else -9e9

        def _ls_out_of(ln, cy):
            _lo, _hi = _lband.get(ln, (-1e9, 1e9))
            return max(_lo - cy, cy - _hi, 0.0)

        def _ls_nearln(cy):
            _tl, _td = None, 1e9
            for _l2, (_l1, _h1) in _lband.items():
                _d2 = max(_l1 - cy, cy - _h1, 0.0)
                if _d2 < _td:
                    _td, _tl = _d2, _l2
            return _tl

        def _ls_cost(r, e):
            _cy = (e["y1"] + e["y2"]) / 2
            return (max(0.0, -_ls_ovl(r["b"], e))
                    + _ls_out_of(r["ln"], _cy))

        def _ls_viol(r, e):
            _cy = (e["y1"] + e["y2"]) / 2
            return (-_ls_ovl(r["b"], e) > _LS_GAP
                    or _ls_out_of(r["ln"], _cy) >= _LS_BAND)

        def _ls_movable(e):
            return (e["kind"] != "body" and not e.get("mkpart")
                    and not e.get("standalone")
                    and e.get("mark") in _LS_FAMS
                    and _ls_key(e) not in _ls_skip
                    and not _ls_is_pending(e))

        # -- violations, and the line-sets they trigger -------------------
        _viols = []               # (holder rec, element)
        for _r in _lrec:
            for _e in _r["els"]:
                if _ls_movable(_e) and _ls_viol(_r, _e):
                    _viols.append((_r, _e))

        def _ls_count(r, marks_named):
            """Per-family |held-want| over the six families.

            marks_named: list of (element, name). Pending-adjudication
            elements are excluded — a disputed identity cannot testify.
            """
            _have = {f: 0 for f in _LS_FAMS}
            for _e, _nm in marks_named:
                if _nm in _have:
                    _have[_nm] += 1
            _t = r["w"]["uthmani"] or ""
            return sum(abs(_have[f] - sum(_t.count(c) for c in _LS_CH[f]))
                       for f in _LS_FAMS)

        def _ls_sitting(r):
            """The word's countable slash/damma marks as (element, name)."""
            return [(e, e["mark"]) for e in r["els"]
                    if e["kind"] != "body" and not e.get("mkpart")
                    and not e.get("standalone")
                    and e.get("mark") in _LS_FAMS
                    and not _ls_is_pending(e)]

        # Triggered lines come from POSITIONAL violations only: a bare count
        # violation has no displaced ink for this solver to re-own, and it
        # was pulling whole extra lines into one solve (p350's first run
        # merged lines 6-8 into a 3^17 product). A count-bad word still
        # constrains — and is repaired by — any solve whose line-set it
        # falls in.
        _trig = set()
        for _r, _e in _viols:
            _trig.add(_r["ln"])
            _dl = _ls_nearln((_e["y1"] + _e["y2"]) / 2)
            if _dl is not None:
                _trig.add(_dl)

        # COUNT-PAIR TRIGGER (trial, DEFAULT OFF — QSVG_LSCNT=1 to enable).
        # A surplus mark drawn over the boundary sits comfortably inside its
        # holder's ink, so it is never a positional violation — yet rounds 5-6
        # confirmed a whole family of `fatha 3/2` words whose neighbour is
        # short the same stroke (p44 2:262:15/16, p51, p100, p319, p361,
        # p486, p543 …). The two signals here: BOTH words' counts disagree
        # with their spelling, AND a movable mark of one overlaps the other's
        # letter ink. Only such pairs trigger; a lone count-bad word still
        # cannot (nothing displaced, and it merged whole extra lines on
        # p350's first run). The solve itself is unchanged — receiver-room
        # guarded, applied only on a strict, unique improvement.
        if os.environ.get("QSVG_LSCNT", "1") == "1":
            _cbad = {id(r): r for r in _lrec
                     if _ls_count(r, _ls_sitting(r))}
            for _r in _cbad.values():
                for _e in _r["els"]:
                    if not _ls_movable(_e):
                        continue
                    for _t in _cbad.values():
                        if _t is _r or abs(_t["ln"] - _r["ln"]) > 1:
                            continue
                        if _ls_ovl(_t["b"], _e) > -_LS_NEAR:
                            _trig.add(_r["ln"])
                            _trig.add(_t["ln"])

        # merge triggered lines whose ±1 word sets would overlap
        _groups = []
        for _ln in sorted(_trig):
            if _groups and _ln - _groups[-1][-1] <= 2:
                _groups[-1].append(_ln)
            else:
                _groups.append([_ln])

        def _ls_side(r, e):
            """'a' above the letters under the mark, 'b' below — orphan rule."""
            _u = [b for b in r["b"]
                  if min(b["x2"], e["x2"]) - max(b["x1"], e["x1"]) > -0.6] \
                 or r["b"]
            _mid = (min(b["y1"] for b in _u) + max(b["y2"] for b in _u)) / 2
            return "a" if (e["y1"] + e["y2"]) / 2 < _mid else "b"

        def _ls_name_word(r, final):
            """Re-derive a TOUCHED word's slash names from position, then weld
            arriving pairs. Returns ([(element, name)], [(master, part, name)]).

            The whole-word re-derivation is the orphan pass's precedent: a
            mark that changed hands carries a name earned over someone else's
            letters, and its arrival re-opens the naming of the word it joins.
            Two single strokes within 8u, at least one of them newly arrived,
            are one tanween named by the side the pair sits on ("two side by
            side = tanween" — the derived-family rule).
            """
            named, welds = [], []
            for _e, _arr in final:
                _nm = _e["mark"]
                if _nm in _LS_SLASH:
                    _nm = _POS_SWAP.get((_nm, _ls_side(r, _e)), _nm)
                named.append([_e, _nm])
            singles = [it for it in named
                       if it[1] in _LS_SLASH and not it[0].get("mkmembers")]
            singles.sort(key=lambda it: (it[0]["x1"], it[0]["y1"]))
            used = set()
            arrived = {id(e) for e, a in final if a}
            for i in range(len(singles)):
                if id(singles[i][0]) in used:
                    continue
                for j in range(i + 1, len(singles)):
                    _a, _b = singles[i][0], singles[j][0]
                    if id(_b) in used:
                        continue
                    if id(_a) not in arrived and id(_b) not in arrived:
                        continue
                    _d = (abs((_a["x1"] + _a["x2"]) - (_b["x1"] + _b["x2"])) / 2
                          + abs((_a["y1"] + _a["y2"]) - (_b["y1"] + _b["y2"])) / 2)
                    if _d > _LS_PAIR:
                        continue
                    _me = {"x1": min(_a["x1"], _b["x1"]),
                           "x2": max(_a["x2"], _b["x2"]),
                           "y1": min(_a["y1"], _b["y1"]),
                           "y2": max(_a["y2"], _b["y2"])}
                    _tn = ("fathatan" if _ls_side(r, _me) == "a"
                           else "kasratan")
                    # two signals: proximity says pair, the TEXT must say the
                    # word owns that tanween and is still short of it —
                    # without this, two of يُنزِفُونَ's plain fathas welded
                    # into a fathatan it does not spell (p535 line 1)
                    _tw = sum((r["w"]["uthmani"] or "").count(c)
                              for c in _LS_CH[_tn])
                    _th = (sum(1 for it in named if it[1] == _tn
                               and id(it[0]) not in (id(_a), id(_b)))
                           - sum(1 for m, p, n in welds if n == _tn))
                    if _th >= _tw:
                        continue
                    singles[i][1] = _tn
                    singles[j][1] = _tn
                    used.add(id(_a))
                    used.add(id(_b))
                    welds.append((_a, _b, _tn))
                    break
            # a welded part stops counting: drop it from the named list
            _parts = {id(p) for m, p, n in welds}
            named = [it for it in named if id(it[0]) not in _parts]
            # The iqlab convention, TEXT-driven (reported.json items 18/23):
            # this print draws iqlab as ONE haraka + small م, so a word whose
            # text carries ۢ/ۭ owns its tanween as a single stroke. Where such
            # a word is short its tanween and long its same-side base after
            # the side naming, the LEFTMOST base stroke (word-final position)
            # is the tanween. Never geometric, never on a non-iqlab word.
            _t = r["w"]["uthmani"] or ""
            if "ۢ" in _t or "ۭ" in _t:
                for _base, _tn in (("fatha", "fathatan"),
                                   ("kasra", "kasratan")):
                    _wb = sum(_t.count(c) for c in _LS_CH[_base])
                    _wt = sum(_t.count(c) for c in _LS_CH[_tn])
                    _hb = [it for it in named if it[1] == _base]
                    _ht = sum(1 for it in named if it[1] == _tn)
                    while _ht < _wt and len(_hb) > _wb:
                        _hb.sort(key=lambda it: it[0]["x1"])
                        _hb[0][1] = _tn
                        _hb = _hb[1:]
                        _ht += 1
            return named, welds

        for _lines in _groups:
            _set = [r for r in _lrec
                    if _lines[0] - 1 <= r["ln"] <= _lines[-1] + 1]
            if len(_set) < 2:
                continue
            _byid = {id(r): r for r in _set}
            # entities: violating marks, plus same-group marks a contested
            # word holds that overlap another word of the set (the p350
            # fatha-at-50.7 kind — never itself orphaned, but the rotation
            # cannot close without it)
            _vset = {id(e) for r, e in _viols if id(r) in _byid}
            _vwords = {id(r) for r, e in _viols if id(r) in _byid}
            for _r in _set:
                if _ls_count(_r, _ls_sitting(_r)):
                    _vwords.add(id(_r))
            _ents = []
            for _r in _set:
                for _e in _r["els"]:
                    if not _ls_movable(_e):
                        continue
                    if id(_e) in _vset:
                        _ents.append((_r, _e))
                    elif id(_r) in _vwords:
                        # near-boundary mark of a contested word
                        _sh = [t for t in _set if t is not _r
                               and _ls_ovl(t["b"], _e) > -_LS_NEAR
                               and abs(t["ln"] - _r["ln"]) <= 1]
                        if _sh:
                            _ents.append((_r, _e))
            if not _vset and not (os.environ.get("QSVG_LSCNT", "1") == "1"
                                  and _ents):
                continue          # count trigger alone, nothing displaced
            _ents.sort(key=lambda t: (t[1]["x1"], t[1]["y1"]))

            # candidates per entity: words whose body ink is under the mark,
            # on the line the mark is drawn in or the one beside it
            _cands = []
            for _r, _e in _ents:
                _cy = (_e["y1"] + _e["y2"]) / 2
                _dl = _ls_nearln(_cy)
                _cs = [_r]
                for _t in _set:
                    if _t is _r or _ls_ovl(_t["b"], _e) <= -_LS_NEAR:
                        continue
                    if _dl is not None and abs(_t["ln"] - _dl) > 1:
                        continue
                    if _ls_out_of(_t["ln"], _cy) >= _LS_BAND:
                        continue      # would be a violation there too
                    _cs.append(_t)
                # nearest-fitting alternatives by GEOMETRY (gap + band), not
                # by raw x-overlap: vertically adjacent words always overlap
                # in x, and ranking by overlap dropped p350's لَا behind the
                # line above and the line below
                _cs = [_cs[0]] + sorted(
                    _cs[1:], key=lambda t: (_ls_cost(t, _e),
                                            -_ls_ovl(t["b"], _e)))[:2]
                _cands.append(_cs)

            # entities with nowhere else to go are constants of the solve
            _mob = [i for i in range(len(_ents)) if len(_cands[i]) > 1]
            if not _mob:
                continue
            # Independent contests factor: two entities interact only when
            # their candidate-word sets share a word (directly or through a
            # chain). Each connected component is its own exact solve — the
            # p350 tail rotation and the لَا/يَنكِحُهَآ exchange are separate
            # components of the same line-set and multiply to nothing.
            _parent = list(range(len(_ents)))

            def _find(i):
                while _parent[i] != i:
                    _parent[i] = _parent[_parent[i]]
                    i = _parent[i]
                return i

            for i in _mob:
                for j in _mob:
                    if j <= i:
                        continue
                    if set(id(w) for w in _cands[i]) \
                            & set(id(w) for w in _cands[j]):
                        _parent[_find(i)] = _find(j)
            _comps = {}
            for i in _mob:
                _comps.setdefault(_find(i), []).append(i)

            if _ls_dbg:
                _ls_log({"page": _ls_page, "lines": _lines, "debug": "group",
                         "entities": [{"mark": e.get("mark"),
                                       "x": round((e["x1"] + e["x2"]) / 2, 1),
                                       "holder": r["w"]["uthmani"],
                                       "cands": ["%s ln%d ovl%.1f c%.1f"
                                                 % (t["w"]["uthmani"], t["ln"],
                                                    _ls_ovl(t["b"], e),
                                                    _ls_cost(t, e))
                                                 for t in _cands[k]]}
                                      for k, (r, e) in enumerate(_ents)],
                         "components": len(_comps)})
            import itertools as _it
            for _ck in sorted(_comps, key=lambda k: min(_comps[k])):
                _idx = sorted(_comps[_ck])
                _np = 1
                for i in _idx:
                    _np *= len(_cands[i])
                if _np > _LS_CAP or len(_idx) > 12:
                    _ls_log({"page": _ls_page, "lines": _lines,
                             "decision": "skipped: component too large",
                             "entities": len(_idx), "combos": _np})
                    continue
                # only this component's words can gain or lose anything
                _wids = set()
                for i in _idx:
                    _wids.add(id(_ents[i][0]))
                    for _t in _cands[i]:
                        _wids.add(id(_t))
                _cset = [r for r in _set if id(r) in _wids]

                def _eval(choice, _idx=_idx, _cset=_cset):
                    """(violations, cost) for one component assignment."""
                    _own = {}
                    for k, i in enumerate(_idx):
                        _own[id(_ents[i][1])] = choice[k]
                    _touched = set()
                    for k, i in enumerate(_idx):
                        _r, _e = _ents[i]
                        if choice[k] is not _r:
                            _touched.add(id(_r))
                            _touched.add(id(choice[k]))
                    _V = 0
                    _C = 0.0
                    for k, i in enumerate(_idx):
                        _r, _e = _ents[i]
                        _t = choice[k]
                        _C += _ls_cost(_t, _e)
                        if _ls_viol(_t, _e):
                            _V += 1
                    for _r in _cset:
                        _final = []
                        for _e2, _nm in _ls_sitting(_r):
                            _o = _own.get(id(_e2))
                            if _o is None or _o is _r:
                                _final.append((_e2, False))
                        for k, i in enumerate(_idx):
                            _r2, _e2 = _ents[i]
                            if _own[id(_e2)] is _r and _r2 is not _r:
                                _final.append((_e2, True))
                        if id(_r) in _touched:
                            _named, _ = _ls_name_word(_r, _final)
                        else:
                            _named = [(e, e["mark"]) for e, _a in _final]
                        _V += _ls_count(_r, _named)
                        # HARD receiver-room: an arriving mark may fill a
                        # deficit, never create a surplus — the two-signals
                        # rule every adopted pass obeys. Without it p535's
                        # line 1 parked a kasratan on يُنزِفُونَ, a word that
                        # spells no tanween at all, because the ledger still
                        # improved.
                        _arrN = {}
                        for _fi, (_e3, _a3) in enumerate(_final):
                            if not _a3:
                                continue
                            _nm3 = next((n for e4, n in _named
                                         if e4 is _e3), None)
                            if _nm3 is not None:
                                _arrN[_nm3] = 1
                        for _nm3 in _arrN:
                            _t3 = _r["w"]["uthmani"] or ""
                            _hl = sum(1 for e4, n in _named if n == _nm3)
                            if _hl > sum(_t3.count(c)
                                         for c in _LS_CH.get(_nm3, "")):
                                _V += 50
                    return _V, _C

                _cur = tuple(0 for i in _idx)      # slot 0 is the holder
                # exhaustive, deterministic
                _best, _second = None, None
                for _ch in _it.product(*[range(len(_cands[i]))
                                         for i in _idx]):
                    _sc = _eval(tuple(_cands[_idx[k]][c]
                                      for k, c in enumerate(_ch)))
                    _row = (_sc[0], _sc[1], _ch)
                    if _best is None or _row < _best:
                        _second = _best
                        _best = _row
                    elif _second is None or _row < _second:
                        _second = _row
                _curV, _curC = _eval(tuple(_cands[_idx[k]][c]
                                           for k, c in enumerate(_cur)))
                _bV, _bC, _bch = _best
                if _bch == _cur or _bV >= _curV:
                    # a component that keeps its violations is a chain the
                    # budgets cannot close — exactly what the proposals page
                    # is for ("uniqueness or eyes")
                    if _ls_dbg or (_ls_out and _curV > 0):
                        _ls_log({"page": _ls_page, "lines": _lines,
                                 "decision": "kept: no improvement",
                                 "V": [_curV, _bV],
                                 "entities": [
                                     {"mark": _ents[i][1].get("mark"),
                                      "x": round((_ents[i][1]["x1"]
                                                  + _ents[i][1]["x2"]) / 2, 1),
                                      "holder": _ents[i][0]["w"]["uthmani"],
                                      "cands": [t["w"]["uthmani"]
                                                for t in _cands[i]]}
                                     for i in _idx]})
                    continue      # nothing strictly better than what stands
                _tie = (_second is not None and _second[0] == _bV
                        and _second[1] <= _bC * (1.0 + _LS_TIE)
                        and _second[2] != _cur)
                _moves = []
                for k, i in enumerate(_idx):
                    _r, _e = _ents[i]
                    _t = _cands[i][_bch[k]]
                    if _t is not _r:
                        _moves.append((_r, _t, _e))
                _rec = {"page": _ls_page, "lines": _lines,
                        "V": [_curV, _bV], "cost": round(_bC, 1),
                        "moves": [{"mark": e.get("mark"),
                                   "x": round((e["x1"] + e["x2"]) / 2, 1),
                                   "y": round((e["y1"] + e["y2"]) / 2, 1),
                                   "from": "%d:%d:%d %s" % (r["w"]["surah"],
                                                            r["w"]["ayah"],
                                                            r["w"]["pos"],
                                                            r["w"]["uthmani"]),
                                   "to": "%d:%d:%d %s" % (t["w"]["surah"],
                                                          t["w"]["ayah"],
                                                          t["w"]["pos"],
                                                          t["w"]["uthmani"])}
                                  for r, t, e in _moves]}
                if _tie:
                    _rec["decision"] = "tie: proposal, no change"
                    _rec["second"] = {"V": _second[0],
                                      "cost": round(_second[1], 1)}
                    _ls_log(_rec)
                    continue
                _rec["decision"] = "applied"
                _ls_log(_rec)
                # apply: atoms via put_in_ligature, the one lawful hand-off
                _touched = set()
                _arrived_ids = {id(e) for _r0, _t0, e in _moves}
                for _r, _t, _e in _moves:
                    for _a in _r["at"]:
                        if _e in _a["els"]:
                            _a["els"].remove(_e)
                            for _m in _e.get("mkmembers", []):
                                if _m in _a["els"]:
                                    _a["els"].remove(_m)
                            break
                    if _e in _r["els"]:
                        _r["els"].remove(_e)
                    for _m in _e.get("mkmembers", []):
                        if _m in _r["els"]:
                            _r["els"].remove(_m)
                    put_in_ligature(_t["at"], _e)
                    _t["els"].append(_e)
                    _t["els"].extend(_e.get("mkmembers", []))
                    if _t.get("ln"):
                        _e["line"] = _t["ln"]
                        for _m in _e.get("mkmembers", []):
                            _m["line"] = _t["ln"]
                    _touched.add(id(_r))
                    _touched.add(id(_t))
                # names follow position, welds included — same code the
                # evaluation ran, now committed
                for _r in _cset:
                    if id(_r) not in _touched:
                        continue
                    _final = [(e, id(e) in _arrived_ids)
                              for e, _nm in _ls_sitting(_r)]
                    _named, _welds = _ls_name_word(_r, _final)
                    for _e2, _nm in _named:
                        if _nm != _e2["mark"]:
                            _e2["mark"] = _nm
                            for _m in _e2.get("mkmembers", []):
                                _m["mark"] = _nm
                    for _mst, _prt, _tn in _welds:
                        _mst["mark"] = _tn
                        _prt["mark"] = _tn
                        _prt["mkpart"] = True
                        _mst.setdefault("mkmembers", []).append(_prt)

    # LATE LINE RE-DEAL of body pieces (QSVG_LREDEAL=0 reverts): the width
    # diagnosis (docs/defects/width_diagnosis.md) proved exactly two boundary
    # mis-cuts by compensating piece arithmetic — p600 L1 لِرَبِّهِۦ(1/2)
    # holds one piece too few while لَكَنُودࣱ(3/2) holds its به piece 9u clear
    # of its own ink, and p596 L1 إِذَا(2/3)/تَرَدَّىٰٓ(4/3). The trigger is
    # the COMPENSATING PAIR: adjacent words where one is exactly one body
    # piece under its joining-rule allowance and the other exactly one over —
    # never width (QSVG_WDECIDE's grave), and single-sided surpluses are
    # excluded (the detached-ك family holds allowance+1 with no shorted
    # neighbour). The moved piece is the surplus word's piece nearest the
    # short word's span; it must sit closer to the short word's ink than to
    # the rest of its holder's.
    if os.environ.get("QSVG_LREDEAL", "1") == "1":
        _lr_lines = {}
        for _wl, _al in assignment:
            if not _wl:
                continue
            _bl = [e for a in _al for e in a["els"] if e["kind"] == "body"]
            if not _bl:
                continue
            _lnl = [e.get("line") for e in _bl if e.get("line")]
            if not _lnl:
                continue
            _lr_lines.setdefault(max(set(_lnl), key=_lnl.count), []).append(
                (_wl, _al, _bl))
        for _lnq, _wsq in _lr_lines.items():
            _wsq.sort(key=lambda t: -max(e["x2"] for e in t[2]))
            for _iq in range(len(_wsq) - 1):
                for _aq, _bq in ((_iq, _iq + 1), (_iq + 1, _iq)):
                    _wA, _atA, _bA = _wsq[_aq]     # short one
                    _wB, _atB, _bB = _wsq[_bq]     # long one
                    _allowA = len(segment_word(_wA["uthmani"]))
                    _allowB = len(segment_word(_wB["uthmani"]))
                    if not (len(_bA) == _allowA - 1
                            and len(_bB) == _allowB + 1):
                        continue
                    _spanA = (min(e["x1"] for e in _bA),
                              max(e["x2"] for e in _bA))
                    # candidate: B's piece nearest A's span
                    def _dA(e):
                        c = (e["x1"] + e["x2"]) / 2
                        return max(_spanA[0] - c, c - _spanA[1], 0.0)
                    _cand = min(_bB, key=_dA)
                    _rest = [e for e in _bB if e is not _cand]
                    if not _rest:
                        continue
                    _dther = min(abs((_cand["x1"] + _cand["x2"]) / 2
                                     - (e["x1"] + e["x2"]) / 2)
                                 for e in _rest)
                    if _dA(_cand) + 2.0 >= _dther:
                        continue          # not clearly nearer the short word
                    for _a2 in _atB:
                        if _cand in _a2["els"]:
                            _a2["els"].remove(_cand)
                            break
                    put_in_ligature(_atA, _cand)
                    _bA.append(_cand)
                    _bB.remove(_cand)
                    break

    # LATE RE-SEAT of the two word-ANCHORED sign families (QSVG_RESEAT=0 reverts).
    #
    # wasla ٱ rides above its word's INITIAL alef; the suffix ۥ trails after its
    # word's FINAL ha. Both signs sit in the kerned gap between two words, and the
    # neighbour's tail sweeps under them, so collection hands each to the word one
    # step EARLIER in reading order. The mid-pipeline reconcilers cannot repair it:
    # measured on p273 (QSVG_TRACE + oracle instrumentation), at oracle time
    # ٱلْعَزِيزُ held only the STOLEN wasla — its own was still with وَهُوَ — so
    # every budget test saw it at-cap and the trial move scored flat (base=2, d=2)
    # and was reverted. The chain unwinds link by link across later passes and the
    # surplus/deficit pair only exists AFTER the last mover, where nothing ran.
    # Mushaf-wide these two families sat frozen at 27+26 flags through every fix
    # wave: 13 wasla pairs (all ٱلْX ٱلْY divine-name pairs), 10 small-waw
    # pair/chains, 5 small-waw captured by unowned furniture, 2 singletons left
    # alone here (p223 = quran.com text bug, p337 = unexplained extra outline).
    #
    # (1) Per line, per family: if the words' TEXT budget balances in total but
    # not per word, re-deal the marks in reading order (rightmost mark to the
    # first slot — both sign and slot orders are monotonic on the line) and only
    # commit when EVERY reseated mark sits within its new owner's reach. Budget-
    # neutral across the line by construction; text and geometry must both agree.
    if os.environ.get("QSVG_RESEAT", "1") != "0":
        _rs_words = []
        for _wr, _atr in assignment:
            if not _wr:
                continue
            _elr = [e for a in _atr for e in a["els"]]
            _bdr = [e for e in _elr if e["kind"] == "body"]
            if not _bdr:
                continue
            _lnr = [e.get("line") for e in _bdr if e.get("line")]
            _rs_words.append({
                "w": _wr, "at": _atr,
                "ln": max(set(_lnr), key=_lnr.count) if _lnr else None,
                "x1": min(e["x1"] for e in _bdr), "x2": max(e["x2"] for e in _bdr),
                "y1": min(e["y1"] for e in _bdr), "y2": max(e["y2"] for e in _bdr)})
        _RS_CHAR = {"wasla": ("ٱ",), "small-waw": ("ۥ",)}
        for _fam, _chs in _RS_CHAR.items():
            _byline = {}
            for _r in _rs_words:
                if _r["ln"] is not None:
                    _byline.setdefault(_r["ln"], []).append(_r)
            for _ln, _rs in _byline.items():
                _caps = [sum(_r["w"]["uthmani"].count(c) for c in _chs)
                         for _r in _rs]
                _held = []
                for _r in _rs:
                    _held.append([e for a in _r["at"] for e in a["els"]
                                  if e.get("mark") == _fam
                                  and not e.get("mkpart")
                                  and not e.get("standalone")])
                if sum(_caps) == 0 or sum(len(h) for h in _held) != sum(_caps):
                    continue
                if all(len(h) == c for h, c in zip(_held, _caps)):
                    continue
                _marks = [(e, _r) for h, _r in zip(_held, _rs) for e in h]
                _marks.sort(key=lambda t: -(t[0]["x1"] + t[0]["x2"]))
                _slots = [_r for _r, c in zip(_rs, _caps) for _ in range(c)]
                _plan, _ok = [], True
                for (_e, _src), _dst in zip(_marks, _slots):
                    if _dst is _src:
                        continue
                    _cx = (_e["x1"] + _e["x2"]) / 2
                    if not (_dst["x1"] - 8.0 <= _cx <= _dst["x2"] + 8.0):
                        _ok = False
                        break
                    _plan.append((_e, _src, _dst))
                if not _ok or not _plan:
                    continue
                for _e, _src, _dst in _plan:
                    for _a in _src["at"]:
                        if _e in _a["els"]:
                            _a["els"].remove(_e)
                            for _m in _e.get("mkmembers", []):
                                if _m in _a["els"]:
                                    _a["els"].remove(_m)
                            break
                    put_in_ligature(_dst["at"], _e)
                    if _dst["ln"]:
                        _e["line"] = _dst["ln"]
                        for _m in _e.get("mkmembers", []):
                            _m["line"] = _dst["ln"]
        # (2) A ۥ hanging low off its ha descends toward the next line, and the
        # line cut hands it to an UNOWNED furniture atom there (the ayah
        # medallion below) — the owner simply loses it and no count audit can
        # see furniture. All five open cases (p255/293/396/603/604) are this,
        # each drawn in the OWNER'S band (y within it) while tagged one line
        # down. Claim it back only when the text owes one, the sign sits inside
        # the word's own band and reach, and exactly ONE word qualifies.
        for _wu, _atu in assignment:
            if _wu is not None:
                continue
            for _au in _atu:
                for _eu in list(_au["els"]):
                    if (_eu.get("mark") != "small-waw" or _eu.get("mkpart")
                            or _eu.get("standalone")):
                        continue
                    _cxu = (_eu["x1"] + _eu["x2"]) / 2
                    _cyu = (_eu["y1"] + _eu["y2"]) / 2
                    _cands = []
                    for _r in _rs_words:
                        _cap = _r["w"]["uthmani"].count("ۥ")
                        if not _cap:
                            continue
                        _n = sum(1 for a in _r["at"] for e in a["els"]
                                 if e.get("mark") == "small-waw"
                                 and not e.get("mkpart"))
                        if _n >= _cap:
                            continue
                        if not (_r["x1"] - 8.0 <= _cxu <= _r["x2"] + 2.0):
                            continue
                        if not (_r["y1"] - 6.0 <= _cyu <= _r["y2"] + 8.0):
                            continue
                        _cands.append(_r)
                    if len(_cands) != 1:
                        continue
                    _r = _cands[0]
                    _au["els"].remove(_eu)
                    for _m in _eu.get("mkmembers", []):
                        if _m in _au["els"]:
                            _au["els"].remove(_m)
                    put_in_ligature(_r["at"], _eu)
                    if _r["ln"]:
                        _eu["line"] = _r["ln"]
                        for _m in _eu.get("mkmembers", []):
                            _m["line"] = _r["ln"]

    # A pause sign always carries its own dots (Abdullah 2026-08-27): the ج
    # has one, the قلى has the two of its ق. Measured mushaf-wide: 96 pause
    # signs had their dots as loose separate elements. Adopt a dot-family
    # element as mark-part of the sign only when its CENTER lies inside the
    # sign's box (a ث's three dots beside a ج stay letter dots — sali and
    # lazim signs have no dots at all and adopt nothing).
    if os.environ.get("QSVG_PAUSEDOTS", "1") == "1":
        _wtypes = waqf_types()
        _CAP = {"waqf-jaiz": ("dot",), "waqf-awla": ("dot", "two-dots")}
        _allat = [(a, e) for _w9, _at9 in assignment for a in _at9
                  for e in a["els"]]
        for _pa, _pe in _allat:
            if _pe.get("mark") != "pause" or _pe.get("mkpart"):
                continue
            _typ = _wtypes.get(_pe.get("sig"))
            _ok = _CAP.get(_typ if isinstance(_typ, str) else
                           (_typ or {}).get("waqf") if isinstance(_typ, dict)
                           else None)
            if not _ok:
                continue
            _room = 2 if "two-dots" in _ok else 1
            for _da, _de in _allat:
                if _room <= 0:
                    break
                if _de.get("mark") not in _ok or _de.get("mkpart") or _de is _pe:
                    continue
                _cx = (_de["x1"] + _de["x2"]) / 2
                _cy = (_de["y1"] + _de["y2"]) / 2
                if not (_pe["x1"] - 1 <= _cx <= _pe["x2"] + 1
                        and _pe["y1"] - 1 <= _cy <= _pe["y2"] + 1):
                    continue
                _de["mkpart"] = True
                _de["mark"] = "pause"
                _pe.setdefault("mkmembers", []).append(_de)
                if _da is not _pa:
                    if _de in _da["els"]:
                        _da["els"].remove(_de)
                    _pa["els"].append(_de)
                    _de["line"] = _pe.get("line")
                _room -= 2 if _de.get("mark") == "two-dots" else 1

    # ------------------------------------------------------------------
    # Taxonomy phase 1 (Abdullah, 2026-08-27) — PURE NAMING, the last thing
    # before rewrite() so no mover ever sees the new names. Nothing changes
    # hands, nothing changes kind; only what a mark is CALLED.
    #  - the two zeros split by the TEXT (measured mushaf-wide: 3988 ۟ words,
    #    66 ۠ words, no word carries both; the aspect distributions confirm —
    #    round zero h/w <= 1.34, upright >= 1.44, an empty band between);
    #  - the seven U+06DC sites are named BY JOB from rare_places();
    #  - at 7:69 the seen is mislabeled `shadda` (its own signature,
    #    c63853f10a0002de, sole occurrence) — renamed by the same place rule,
    #    guarded by the word's text demanding no shadda.
    if os.environ.get("QSVG_TAX", "1") == "1":
        _rare = rare_places()
        for _wt, _att in assignment:
            if not _wt:
                continue
            _txtt = _wt["uthmani"]
            _zero = ("sifr-mustatil" if "۠" in _txtt else
                     "sifr-mustadir" if "۟" in _txtt else None)
            _job = (_rare.get((_wt["surah"], _wt["ayah"]))
                    if "ۜ" in _txtt else None)
            if not _zero and not _job:
                continue
            _els_t = [e for a in _att for e in a["els"]]
            for e in _els_t:
                mk = e.get("mark")
                if not mk:
                    continue
                if _zero and "small-circle" in mk:
                    e["mark"] = "+".join(_zero if p2 == "small-circle" else p2
                                         for p2 in mk.split("+"))
            if _job:
                # the sign to rename: a `pause` that no waqf table names —
                # the word's true waqf (if any) keeps its data-waqf identity
                _page_no_t = str(int(os.path.splitext(page.name)[0]
                                     .split("-")[0].lstrip("0") or 0))
                _wp = waqf_places().get(_page_no_t, {})
                _cand = [e for e in _els_t
                         if e.get("mark") == "pause" and not e.get("mkpart")
                         and not waqf_types().get(e.get("sig"))
                         and not _wp.get("%.1f,%.1f,%.1f,%.1f"
                                         % (e["x1"], e["y1"], e["x2"], e["y2"]))]
                if not _cand and "ّ" not in _txtt \
                        and (_wt.get("qpc") or "").count("ّ") == 0:
                    _cand = [e for e in _els_t
                             if e.get("mark") == "shadda"
                             and not e.get("mkpart")]
                if len(_cand) == 1:
                    _cand[0]["mark"] = _job
                    for _m in _cand[0].get("mkmembers", []):
                        _m["mark"] = _job

    # ------------------------------------------------------------------
    # Taxonomy phase 2 (Abdullah, 2026-08-27) — NEW ATTRIBUTES, decisions
    # 5 and 6. Pure metadata: nothing changes hands, name, or kind.
    #  - decision 5: every tanween PAIR (master + its same-name welded twin)
    #    gets data-form="stacked|staggered" on the master, derived from the
    #    two strokes' horizontal center offset |dx|. Thresholds and the
    #    mushaf-wide histogram live at _TAN_STAG (top of file). A dammatan
    #    drawn as ONE fused glyph has no twin and carries no data-form.
    #  - decision 6: the muanaqah's two signs pair within their ayah: both
    #    MASTERS carry data-pair="mnq-<surah>-<ayah>-<n>". Three sites in
    #    this print (2:2 p2, 5:26 p112, 5:41 p114) — quran.com's uthmani
    #    writes three more (2:195, 7:172, 14:9) where the print draws a
    #    jaiz or nothing (faces of the known 203-site waqf disagreement);
    #    waqf_places, built from the ink, is the authority.
    if os.environ.get("QSVG_TAX2", "1") == "1":
        _TANW = ("fathatan", "kasratan", "dammatan")
        _pg2 = str(int(os.path.splitext(page.name)[0].split("-")[0]
                       .lstrip("0") or 0))
        _wp2 = waqf_places().get(_pg2, {})
        _mnq2 = {}
        for _wi2, (_w3, _at3) in enumerate(assignment):
            if not _w3:
                continue
            for _a3 in _at3:
                for e in _a3["els"]:
                    mk = e.get("mark")
                    if not mk or e.get("mkpart"):
                        continue
                    if mk in _TANW:
                        _tw = [m for m in e.get("mkmembers", [])
                               if m.get("mark") == mk]
                        if len(_tw) == 1:
                            _m3 = _tw[0]
                            _up, _lo = ((e, _m3)
                                        if (e["y1"] + e["y2"])
                                        <= (_m3["y1"] + _m3["y2"])
                                        else (_m3, e))
                            _dx = ((_lo["x1"] + _lo["x2"]) / 2
                                   - (_up["x1"] + _up["x2"]) / 2)
                            e["tanform"] = ("staggered"
                                            if abs(_dx) >= _TAN_STAG[mk]
                                            else "stacked")
                        if TAN_DUMP is not None:
                            TAN_DUMP.append({
                                "page": int(_pg2), "s": _w3["surah"],
                                "a": _w3["ayah"],
                                "pos": _w3.get("pos"),
                                "uthmani": _w3.get("uthmani"),
                                "mark": mk, "ntwin": len(_tw),
                                "master": [e["x1"], e["y1"],
                                           e["x2"], e["y2"]],
                                "twin": ([_tw[0]["x1"], _tw[0]["y1"],
                                          _tw[0]["x2"], _tw[0]["y2"]]
                                         if len(_tw) == 1 else None)})
                    elif mk == "muanaqah":
                        # the name IS the identity now (set at the MNQ3
                        # weld); the place table only ever covered the
                        # p112/p114 recordings, p2 paired by luck of the
                        # waqf_types sig match
                        _mnq2.setdefault(
                            (_w3["surah"], _w3["ayah"]),
                            []).append((_wi2, -e["x1"], e))
        for (_s4, _a4), _lst4 in sorted(_mnq2.items()):
            _lst4.sort(key=lambda t: (t[0], t[1]))
            for _k4 in range(0, len(_lst4) - 1, 2):
                _pid = "mnq-%d-%d-%d" % (_s4, _a4, _k4 // 2 + 1)
                _lst4[_k4][2]["mnqpair"] = _pid
                _lst4[_k4 + 1][2]["mnqpair"] = _pid

    # UNNAMED STANDALONE PIECES: the hizb ۞ / sajdah signs' companion
    # contours were emitted as bare kind=mark with no name (169 mushaf-wide,
    # on the hizb-quarter pages). An unnamed wordless fragment joins the
    # standalone sign whose ink it sits beside (same atom, or within 15u of
    # a named sign) as a part — one sign, one mark. Anything that matches no
    # sign stays visible in the UNNAMED review section.
    _signs = []
    for _wu, _au in assignment:
        for _a in _au:
            for e in _a["els"]:
                if e.get("mark") in ("hizb", "sajdah-sign", "sajdah-line") \
                        and not e.get("mkpart"):
                    _signs.append(e)
    for _wu, _au in assignment:
        if _wu:
            continue
        for _a in _au:
            _named = [e for e in _a["els"] if e.get("mark")]
            _sa9 = _a.get("sa")
            _base = (_named[0] if _named else None)
            for e in _a["els"]:
                if e["kind"] != "mark" or e.get("mark"):
                    continue
                _tgt = _base
                if _tgt is None and _sa9:
                    e["mark"] = _sa9[0]
                    e["mkpart"] = True
                    continue
                if _tgt is None:
                    _cx = (e["x1"] + e["x2"]) / 2
                    _cy = (e["y1"] + e["y2"]) / 2
                    _near = [t for t in _signs
                             if t["x1"] - 15 <= _cx <= t["x2"] + 15
                             and t["y1"] - 15 <= _cy <= t["y2"] + 15]
                    if len(_near) == 1:
                        _tgt = _near[0]
                if _tgt is not None:
                    e["mark"] = _tgt["mark"]
                    e["mkpart"] = True
                    _tgt.setdefault("mkmembers", []).append(e)
    # ROTATED TANWEEN PAIR (Abdullah 2026-08-28, لَـَٔايَٰتࣲ p499/p268): two
    # adjacent fathas at a word's TOP get welded and named kasratan, while the
    # word's real kasratan below wears two fatha names — a perfectly
    # count-neutral rotation only an eye caught. Position doctrine applied to
    # PAIRS: a kasratan pair must sit BELOW the word's letters. When a
    # kasratan-named pair sits clearly ABOVE the word's letter mid-line AND
    # at least two below-the-letters marks are named fatha AND the budget
    # wants no fathatan, rotate: unweld the top pair into two fathas, weld
    # the two lowest below-fathas as the kasratan.
    if os.environ.get("QSVG_TANROT", "1") == "1":
        for _wr2, _ar2 in assignment:
            if not _wr2:
                continue
            _t2 = _wr2["uthmani"]
            if not any(c in _t2 for c in "\u064d\u08f2"):
                continue           # word owns no kasratan
            if any(c in _t2 for c in "\u064b\u08f0"):
                continue           # fathatan present: ambiguous, leave
            _e2s = [e for a in _ar2 for e in a["els"]]
            _b2s = [e for e in _e2s if e["kind"] == "body"]
            if not _b2s:
                continue
            _mid2 = (min(b["y1"] for b in _b2s) + max(b["y2"] for b in _b2s)) / 2
            _pairs = [e for e in _e2s if e.get("mark") == "kasratan"
                      and not e.get("mkpart") and e.get("mkmembers")]
            for _p2 in _pairs:
                _cy2 = (_p2["y1"] + _p2["y2"]) / 2
                if _cy2 >= _mid2 - 1.0:
                    continue       # pair is not clearly above
                _low_f = sorted([e for e in _e2s if e.get("mark") == "fatha"
                                 and not e.get("mkpart")
                                 and (e["y1"] + e["y2"]) / 2 > _mid2],
                                key=lambda e: -(e["y1"] + e["y2"]))
                if len(_low_f) < 2:
                    continue
                if os.environ.get("QSVG_TANDBG"):
                    print("TANROT p? %d:%d:%d %s" % (
                        _wr2["surah"], _wr2["ayah"], _wr2["pos"],
                        _wr2["uthmani"]), file=sys.stderr)
                # rotate: top pair -> two fathas
                for _m2 in _p2.get("mkmembers", []):
                    _m2["mkpart"] = False
                    _m2["mark"] = "fatha"
                    _m2["lab"] = "fatha"
                _p2["mkmembers"] = []
                _p2["mark"] = "fatha"
                _p2["lab"] = "fatha"
                _p2.pop("tanform", None)     # no longer a tanween pair
                # two lowest below-fathas -> the kasratan pair
                _ma2, _mb2 = _low_f[0], _low_f[1]
                _mb2["mkpart"] = True
                _mb2["mark"] = "kasratan"
                _ma2["mark"] = "kasratan"
                _ma2["lab"] = "kasratan"
                _ma2.setdefault("mkmembers", []).append(_mb2)
                break

    # IQLAB UNIT (Abdullah 2026-08-28): the print draws iqlab as ONE unit —
    # a haraka + the small م. Late reconciliation: at every print-iqlab word
    # (ۢ/ۭ in the print text), the م must wear meem-iqlab (his p531 e236 was
    # unnamed with a CORRECT table label; p577 e122 wore "pause"), and both
    # halves carry one data-iqlab pair id. Names stay catalog-true: the
    # haraka keeps fatha/kasra/damma — recitation changes, ink does not.
    # IQLAB SIGN BY TABLE IDENTITY (Abdullah 2026-08-28: قَوْمِۭ p93/p186
    # took its own letter م as the sign; زَوْجِۭ p518 took a letter piece
    # while the real ۭ outline sat as body). The rescues choose by geometry;
    # where a HUMAN table entry identifies the sign outline, identity wins:
    # that element is the م, and any other element wearing the name whose
    # human label calls it letter ink gives it back.
    if os.environ.get("QSVG_IQTAB", "1") == "1":
        _qtab = shape_labels()
        def _qlb(e):
            try:
                sg = e.get("sig") or sig_key(signature(el_points(e)))
            except Exception:
                return (None, True)
            e.setdefault("sig", sg)
            v = _qtab.get(sg)
            lb = v.get("label") if isinstance(v, dict) else v
            auto = v.get("auto", v.get("ai", True)) if isinstance(v, dict) else True
            return (lb, auto)
        for _wq, _aq in assignment:
            if not _wq:
                continue
            _ptq = _wq.get("qpc") or _wq["uthmani"]
            if not any(c in _ptq for c in "\u06e2\u06ed"):
                continue
            _elq = [e for a in _aq for e in a["els"]]
            _tabm = []
            _imp = []
            for e in _elq:
                if e.get("mkpart"):
                    continue
                lb, auto = _qlb(e)
                if auto:
                    continue
                if lb == "meem-iqlab":
                    _tabm.append(e)
                elif lb in ("letter", "letter-hamza", "letter-part")                         and e.get("mark") == "meem-iqlab":
                    _imp.append(e)
            # a letter-labelled impostor yields even when the true sign is
            # not yet identified — a missing sign flags honestly; a letter
            # wearing the sign lies twice (Abdullah: قَسْوَرَةِۭ p577 kept
            # its ر as the م because the word had no table sign to trade)
            for e in _imp:
                e["kind"] = "body"
                e["mark"] = None
                e["lab"] = None
            if not _tabm:
                continue
            for e in _tabm:
                if e.get("mark") != "meem-iqlab":
                    e["kind"] = "mark"
                    e["mark"] = "meem-iqlab"
                    e["lab"] = "meem-iqlab"
            # one sign per ۢ/ۭ: surplus impostors NOT letter-labelled but
            # geometry-named stay only while the table holds fewer than the
    # text wants — with the table sign present, a second named element
            # that the table cannot vouch for yields
            _wantq = sum(_ptq.count(c) for c in "\u06e2\u06ed")
            _named = [e for e in _elq if e.get("mark") == "meem-iqlab"
                      and not e.get("mkpart")]
            if len(_named) > _wantq:
                for e in sorted(_named, key=lambda x: x not in _tabm):
                    if len(_named) <= _wantq:
                        break
                    if e not in _tabm:
                        e["kind"] = "body"
                        e["mark"] = None
                        e["lab"] = None
                        _named.remove(e)

    if os.environ.get("QSVG_IQPAIR", "1") == "1":
        for _wi, _ai in assignment:
            if not _wi:
                continue
            _ptx = _wi.get("qpc") or _wi["uthmani"]
            if not any(c in _ptx for c in "\u06e2\u06ed"):
                continue
            _eli = [e for a in _ai for e in a["els"]]
            _meem = [e for e in _eli if e.get("mark") == "meem-iqlab"
                     and not e.get("mkpart")]
            if not _meem:
                for e in _eli:
                    v = shape_labels().get(e.get("sig") or "")
                    lb = v.get("label") if isinstance(v, dict) else v
                    if lb == "meem-iqlab" and not e.get("mkpart"):
                        e["kind"] = "mark"
                        e["mark"] = "meem-iqlab"
                        e["lab"] = "meem-iqlab"
                        _meem = [e]
                        break
            if not _meem:
                for e in _eli:
                    if (e.get("mark") == "pause" and not e.get("mkpart")
                            and (e["x2"] - e["x1"]) <= 6.5
                            and (e["y2"] - e["y1"]) <= 6.5
                            and not _human_letter_label(e)):
                        e["mark"] = "meem-iqlab"
                        e["lab"] = "meem-iqlab"
                        _meem = [e]
                        break
            if not _meem:
                continue
            _m0 = _meem[0]
            # NOON iqlab vs TANWEEN iqlab (Abdullah 2026-08-28, 4:73:9): when
            # the print writes the م over a BARE ن (the char before ۢ/ۭ is a
            # letter, not a haraka), no haraka belongs to the unit — a nearby
            # damma is its own letter's. Pair a haraka ONLY for tanween iqlab.
            _hset = "\u064b\u064c\u064d\u064e\u064f\u0650\u08f0\u08f1\u08f2"
            _iqi = max(_ptx.find("\u06e2"), _ptx.find("\u06ed"))
            _tanween_iqlab = _iqi > 0 and _ptx[_iqi - 1] in _hset
            if not _tanween_iqlab:
                _m0["iqpair"] = "iq-%d-%d-%d" % (_wi["surah"], _wi["ayah"],
                                                 _wi["pos"])
                continue
            _cxm = (_m0["x1"] + _m0["x2"]) / 2
            _har = [e for e in _eli
                    if e.get("mark") in ("fatha", "kasra", "damma",
                                         "fathatan", "kasratan", "dammatan")
                    and not e.get("mkpart")]
            if _har:
                # the unit's haraka is named by the TEXT (the char before
                # ۭ/ۢ — Abdullah 2026-08-28, p531 كَلَمْحِۭ). Prefer the
                # nearest stroke ALREADY wearing that name; rename the
                # nearest slash only when none does (position misread it).
                _hnm = {"\u064e": "fatha", "\u0650": "kasra",
                        "\u064f": "damma"}.get(_ptx[_iqi - 1])
                _same = [e for e in _har if e.get("mark") == _hnm]
                _pool0 = _same or _har
                _h0 = min(_pool0, key=lambda e:
                          abs((e["x1"] + e["x2"]) / 2 - _cxm))
                _pid = "iq-%d-%d-%d" % (_wi["surah"], _wi["ayah"], _wi["pos"])
                _m0["iqpair"] = _pid
                _h0["iqpair"] = _pid
                if _hnm and not _same \
                        and _h0.get("mark") in ("fatha", "kasra", "damma"):
                    _h0["mark"] = _hnm
                    _h0["lab"] = _hnm

    # Shape identity outranks position, applied LAST (item 38, both faces).
    # By now every sig exists and every namer has spoken; where the word's
    # budget disagrees with the names, the human-confirmed shape table gets
    # the final word: (a) a slash-named mark whose outline is a confirmed
    # hamza becomes the word's missing hamza (p583 إِذْ, 9-flag family);
    # (b) a BODY whose outline is a confirmed mark shape becomes the word's
    # missing mark of that family (p418 e295, the labeled fatha demoted to
    # letter ink). Budget deficit is the license in both directions — a
    # balanced word is never touched.
    if os.environ.get("QSVG_SHAPEFIRST", "1") == "1":
        _CARR8 = "\u0623\u0625\u0624\u0626\u0654\u0655"
        _SLASH8 = {"fatha": "\u064e", "kasra": "\u0650",
                   "fathatan": "\u064b\u08f0", "kasratan": "\u064d\u08f2"}
        def _tabl(sig):
            v = shape_labels().get(sig or "")
            lb = v.get("label") if isinstance(v, dict) else v
            # {'ai': True} marks the auto pass; a plain {'label': x} entry
            # is a HUMAN decision from before the flag existed
            auto = (v.get("auto", v.get("ai", False))
                    if isinstance(v, dict) else True)
            return (lb, auto)
        for _w8, _at8 in assignment:
            if not _w8:
                continue
            _txt8 = _w8["uthmani"]
            _els8 = [e for a in _at8 for e in a["els"]]
            # (e) HUMAN letter labels outrank every namer: an element wearing
            # a mark name whose confirmed table label calls it letter ink is
            # letter ink (p159: the seated ء named "damma"). The one twin
            # exception: letter-hamza ink named "hamza" stays — the final ء
            # reconciliation decides that pair by carrier budget.
            for e in _els8:
                if e.get("mkpart") or e["kind"] != "mark" or not e.get("mark"):
                    continue
                lbE, autoE = _tabl(e.get("sig"))
                if autoE:
                    continue
                if lbE in ("letter", "letter-part") or                         (lbE == "letter-hamza" and e["mark"] != "hamza"):
                    for m in (e.get("mkmembers") or []):
                        m["mkpart"] = False
                    e["mkmembers"] = []
                    e["kind"] = "body"
                    e["mark"] = None
                    e["lab"] = lbE
            # (a) missing hamza, held by a slash name on a confirmed-hamza shape
            _wanth = sum(_txt8.count(c) for c in _CARR8) + _txt8.count("\u0621")
            _haveh = sum(1 for e in _els8 if e.get("mark") == "hamza"
                         and not e.get("mkpart"))
            if _haveh < _wanth:
                for e in _els8:
                    if _haveh >= _wanth:
                        break
                    if (e["kind"] == "mark" and not e.get("mkpart")
                            and e.get("mark") in _SLASH8):
                        lb, auto = _tabl(e.get("sig"))
                        if lb == "hamza" and not auto:
                            e["mark"] = "hamza"
                            e["lab"] = "hamza"
                            _haveh += 1
            # (c) كُلࣱّ family (item 37, 11 flags): the word's own damma
            # welded into the dammatan stack as a third curl. When the text
            # wants a plain damma AND a dammatan, and a dammatan master
            # carries two welded twins (3 curls), one twin is the damma —
            # peel the bottom-most (nearest the letters) back out.
            _wantd = _txt8.count("\u064f")
            _haved = sum(1 for e in _els8 if e.get("mark") == "damma"
                         and not e.get("mkpart"))
            if _wantd > _haved and any(c in _txt8 for c in "\u064c\u08f1"):
                for e in _els8:
                    if _haved >= _wantd:
                        break
                    if (e.get("mark") == "dammatan" and not e.get("mkpart")
                            and len(e.get("mkmembers", [])) >= 2):
                        mem = sorted(e["mkmembers"],
                                     key=lambda m: -(m["y1"] + m["y2"]))[0]
                        e["mkmembers"] = [m for m in e["mkmembers"]
                                          if m is not mem]
                        mem["mkpart"] = False
                        mem["mark"] = "damma"
                        mem["lab"] = "damma"
                        _haved += 1
            # (b) missing slash mark, its ink demoted to body
            for fam, chs in _SLASH8.items():
                _want = sum(_txt8.count(c) for c in chs)
                if not _want:
                    continue
                grp = ("fatha", "fathatan") if fam in ("fatha", "fathatan") \
                    else ("kasra", "kasratan")
                _have = sum(1 for e in _els8 if e.get("mark") in grp
                            and not e.get("mkpart"))
                _wgrp = sum(_txt8.count(c) for f2 in grp
                            for c in _SLASH8[f2])
                if _have >= _wgrp:
                    continue
                for e in _els8:
                    if _have >= _wgrp:
                        break
                    if e["kind"] == "body" and not e.get("mkpart"):
                        lb, auto = _tabl(e.get("sig"))
                        # the table stores one canonical slash name; the
                        # drawn position picks fatha vs kasra, so any slash
                        # label licenses the deficit family
                        if lb in ("fatha", "kasra", "fathatan", "kasratan"):
                            e["kind"] = "mark"
                            e["mark"] = fam
                            e["lab"] = lb
                            _have += 1

    # A BODY wearing a waqf outline is the waqf (Abdullah 2026-08-28,
    # p548 وَٱلشَّهَٰدَةِۖ: its صلے sat as letter ink and the word read as
    # missing its sign — the only body+data-waqf emission in the mushaf).
    # Budget is the license: only a word still OWED a pause may promote.
    if os.environ.get("QSVG_WQBODY", "1") == "1":
        _wqt = waqf_types()
        _WQC2 = "\u06d6\u06d7\u06d8\u06d9\u06da\u06dc"
        for _wb, _ab in assignment:
            if not _wb:
                continue
            _ptb = _wb.get("qpc") or _wb["uthmani"]
            _budb = sum(_ptb.count(c) for c in _WQC2)
            if not _budb:
                continue
            _elb = [e for a in _ab for e in a["els"]]
            _hvb = sum(1 for e in _elb if e.get("mark") == "pause"
                       and not e.get("mkpart"))
            if _hvb >= _budb:
                continue
            for e in _elb:
                if _hvb >= _budb:
                    break
                if e["kind"] != "body" or e.get("mkpart") or e.get("mark"):
                    continue
                try:
                    _sg = e.get("sig") or sig_key(signature(el_points(e)))
                except Exception:
                    continue
                if _sg in _wqt:
                    e.setdefault("sig", _sg)
                    e["kind"] = "mark"
                    e["mark"] = "pause"
                    e["lab"] = "pause"
                    _hvb += 1

    # A waqf sign OWNS its satellite ink (Abdullah 2026-08-28, p14
    # مَعَهُمْۗ: the قلي's two lower dots auto-labelled as a second
    # "pause"). When a word holds more pause MASTERS than its text has waqf
    # characters, and two of them overlap in x within a line's height, the
    # smaller is the sign's own satellite — weld it in.
    if os.environ.get("QSVG_WQOWN", "1") == "1":
        _WQCH = "\u06d6\u06d7\u06d8\u06d9\u06da\u06dc"
        for _ww, _aw in assignment:
            if not _ww:
                continue
            _ptw = _ww.get("qpc") or _ww["uthmani"]
            _bud = sum(_ptw.count(c) for c in _WQCH)
            _elz = [e for a in _aw for e in a["els"]]
            _pm = [e for e in _elz if e.get("mark") == "pause"
                   and not e.get("mkpart")]
            # a pause held with NO waqf budget belongs to the PREVIOUS word
            # (Abdullah 2026-08-28: pause sits at its word's LEFT end —
            # measured p5 of rel-x is 0.82; p239 إِنَّهُۥ held one at
            # -1.33). Return it when the previous word is owed one.
            if not _bud and _pm:
                _wi5 = next((i5 for i5, (w5, _) in enumerate(assignment)
                             if w5 is _ww), None)
                if _wi5 is not None and _wi5 > 0:
                    _wpv, _apv = assignment[_wi5 - 1]
                    if _wpv:
                        _ptv = _wpv.get("qpc") or _wpv["uthmani"]
                        _bpv = sum(_ptv.count(c) for c in _WQCH)
                        _hpv = sum(1 for a5 in _apv for x in a5["els"]
                                   if x.get("mark") == "pause"
                                   and not x.get("mkpart"))
                        if _bpv > _hpv:
                            for e in list(_pm):
                                for _a5 in _aw:
                                    if e in _a5["els"]:
                                        _a5["els"].remove(e)
                                        break
                                put_in_ligature(_apv, e)
                                for m in (e.get("mkmembers") or []):
                                    m["line"] = _wpv and e.get("line")
                                _pm.remove(e)
                                _hpv += 1
                                if _hpv >= _bpv:
                                    break
            if not _bud or len(_pm) <= _bud:
                continue
            _pm.sort(key=lambda e: -(e["x2"] - e["x1"]) * (e["y2"] - e["y1"]))
            for e in _pm[_bud:]:
                _host = min(_pm[:_bud], key=lambda h: abs(
                    (h["x1"] + h["x2"]) / 2 - (e["x1"] + e["x2"]) / 2))
                if (min(_host["x2"], e["x2"]) - max(_host["x1"], e["x1"])
                        < -1.0):
                    continue
                if abs((_host["y1"] + _host["y2"]) / 2
                       - (e["y1"] + e["y2"]) / 2) > 12.0:
                    continue
                e["mkpart"] = True
                e.pop("mkmembers", None)
                _host.setdefault("mkmembers", []).append(e)

    # OVERRIDE ENFORCEMENT — the LAST word, literally (Abdullah 2026-08-29,
    # p129 e910: the mid-pipeline override applied and a later pass undid
    # it). Re-pin every overridden piece to its human-placed owner after all
    # movers; an optional "|mark" suffix on the value also names it, so a
    # human weld verdict (p85 e298 "|kasra") feeds the pair welds that run
    # after this point.
    def _enforce_overrides(rename=True):
        _ovp = os.path.join(ROOT, ".cache", "review", "overrides.json")
        if os.path.exists(_ovp):
            try:
                _ov2 = json.load(open(_ovp)).get(str(page_no), {})
            except Exception:
                _ov2 = {}
            if _ov2:
                _bw2 = {}
                for _w9, _at9 in assignment:
                    if _w9:
                        _bw2["%d:%d:%d" % (_w9["surah"], _w9["ayah"],
                                           _w9["pos"])] = (_w9, _at9)
                for _w9, _at9 in assignment:
                    for _a9 in list(_at9):
                        for _e9 in list(_a9["els"]):
                            _k9 = "%.1f,%.1f,%.1f,%.1f" % (
                                _e9["x1"], _e9["y1"], _e9["x2"], _e9["y2"])
                            _v9 = _ov2.get(_k9)
                            if not _v9 and len(_e9.get("contours", [])) > 1:
                                # contour-level key at ENFORCEMENT time: pairs
                                # that fuse after the mid-pass override (p126
                                # بإذني) split here, with the last word.
                                _pM9 = page.paths[_e9["path"]]["M"]
                                for _c9 in list(_e9["contours"]):
                                    sp9 = _c9["sp"]
                                    bx1, by1, bx2, by2 = transform_box(
                                        _pM9, sp9["xmin"], sp9["ymin"],
                                        sp9["xmax"], sp9["ymax"])
                                    _ck = "%.1f,%.1f,%.1f,%.1f" % (
                                        min(bx1, bx2), min(by1, by2),
                                        max(bx1, bx2), max(by1, by2))
                                    _cv = _ov2.get(_ck)
                                    if not _cv:
                                        continue
                                    _ct, _, _cn = _cv.partition("|")
                                    if _ct not in _bw2:
                                        continue
                                    _e9["contours"] = [
                                        c for c in _e9["contours"]
                                        if c is not _c9]
                                    _ne9 = dict(_e9)
                                    _ne9["contours"] = [_c9]
                                    _ne9["x1"], _ne9["y1"] = (
                                        min(bx1, bx2), min(by1, by2))
                                    _ne9["x2"], _ne9["y2"] = (
                                        max(bx1, bx2), max(by1, by2))
                                    _ne9.pop("mkmembers", None)
                                    _ne9.pop("sig", None)
                                    _ne9.pop("tanform", None)
                                    _ne9["_ovr"] = 1
                                    _ne9["mkpart"] = False
                                    if _cn:
                                        _ne9["mark"] = _cn
                                        _ne9["lab"] = _cn
                                    put_in_ligature(_bw2[_ct][1], _ne9)
                                    _rb = [transform_box(
                                        _pM9, c["sp"]["xmin"], c["sp"]["ymin"],
                                        c["sp"]["xmax"], c["sp"]["ymax"])
                                        for c in _e9["contours"]]
                                    _e9["x1"] = min(min(a, c) for a, b, c, d in _rb)
                                    _e9["y1"] = min(min(b, d) for a, b, c, d in _rb)
                                    _e9["x2"] = max(max(a, c) for a, b, c, d in _rb)
                                    _e9["y2"] = max(max(b, d) for a, b, c, d in _rb)
                                continue
                            if not _v9:
                                continue
                            _tgt, _, _nm9 = _v9.partition("|")
                            if _tgt not in _bw2:
                                continue
                            _e9["_ovr"] = 1
                            if _nm9 and rename:
                                _e9["kind"] = "mark"
                                _e9["mark"] = _nm9
                                _e9["lab"] = _nm9
                                _e9.pop("mkpart", None)
                                for _mm9 in (_e9.pop("mkmembers", None) or []):
                                    _mm9["mkpart"] = False
                                # and leave any master that held IT — a named
                                # override is its own mark (p126 بإذني: the
                                # second kasra was a member of the first, so
                                # emit merged the pair and it counted once).
                                for _wq9, _atq9 in assignment:
                                    for _aq9 in _atq9:
                                        for _x9 in _aq9["els"]:
                                            if _e9 in (_x9.get("mkmembers")
                                                       or []):
                                                _x9["mkmembers"].remove(_e9)
                            _dw9, _dat9 = _bw2[_tgt]
                            if _dw9 is _w9:
                                continue
                            if _e9.get("mkpart"):
                                _e9["mkpart"] = False
                                for _wq9, _atq9 in assignment:
                                    for _aq9 in _atq9:
                                        for _x9 in _aq9["els"]:
                                            if _e9 in (_x9.get("mkmembers")
                                                       or []):
                                                _x9["mkmembers"].remove(_e9)
                            _a9["els"].remove(_e9)
                            put_in_ligature(_dat9, _e9)

    # ORPHANED-PART REPAIR: an element flagged mkpart whose master no
    # longer references it counts for NOBODY (p85: the ة pair after its
    # master was renamed by override). Free it — it is its own mark.
        _allm = set()
        for _wo9, _ato9 in assignment:
            for _ao9 in _ato9:
                for _eo9 in _ao9["els"]:
                    for _mm9 in (_eo9.get("mkmembers") or []):
                        _allm.add(id(_mm9))
        for _wo9, _ato9 in assignment:
            for _ao9 in _ato9:
                for _eo9 in _ao9["els"]:
                    if _eo9.get("mkpart") and id(_eo9) not in _allm:
                        _eo9["mkpart"] = False

    # SLASHFIX (Abdullah 2026-08-29: "it doesn't need manual work") — the
    # two species his eye kept finding, automated with two signals each:
    #   A. NAME INVERSION: fatha/kasra are one stroke named by position
    #      relative to the word that HOLDS it, so a mis-owned or mis-dealt
    #      stroke arrives wearing the opposite name. Proof: a "kasra" lying
    #      ABOVE the word's letter ink (or a "fatha" fully below it) is
    #      impossible in the script. Direction: the word's own budget
    #      deficit. Both must agree before renaming (e603 p218, e290 p385,
    #      e274 p518).
    #   B. FUSED PAIR: two slash strokes drawn touching share one MARK
    #      element and count once. Proof: a mark element with side-by-side
    #      slash-sized contours (never nested — nested = an evenodd hole,
    #      the p218 ظ-loop trap; and never body elements). Direction: the
    #      family's budget deficit (e458 p126, e607 p218, e292 p385,
    #      e312 p459, e180 p552).
    if os.environ.get("QSVG_SLASHFIX", "1") == "1":
        for _wf, _atf in assignment:
            if not _wf:
                continue
            _txf = _wf["uthmani"]
            _wantf = {"fatha": _txf.count("\u064e"),
                      "kasra": _txf.count("\u0650")}
            if not (_wantf["fatha"] or _wantf["kasra"]):
                continue
            _elf = [e for a in _atf for e in a["els"]]
            _bods = [e for e in _elf if e.get("kind") == "body"]
            if not _bods:
                continue
            _btop = min(e["y1"] for e in _bods)
            _bbot = max(e["y2"] for e in _bods)

            def _havef(fam):
                return [e for e in _elf if e.get("mark") == fam
                        and not e.get("mkpart")]
            # A: rename by impossible position + deficit
            for _fam, _oth, _side in (("fatha", "kasra", "top"),
                                      ("kasra", "fatha", "bot")):
                _def = _wantf[_fam] - len(_havef(_fam))
                if _def <= 0:
                    continue
                _cands = [e for e in _havef(_oth)
                          if len(e["contours"]) == 1
                          and not e.get("mkmembers")
                          and not e.get("_ovr")
                          and ((_side == "top" and e["y2"] <= _btop + 2.0)
                               or (_side == "bot"
                                   and e["y1"] >= _bbot - 2.0))]
                _cands.sort(key=lambda e: e["y1"]
                            if _side == "top" else -e["y2"])
                for _e in _cands[:_def]:
                    _e["mark"] = _fam
                    _e["lab"] = _fam
                    _e.pop("tanform", None)
            # B: split fused side-by-side pairs up to the deficit
            for _fam in ("fatha", "kasra"):
                _def = _wantf[_fam] - len(_havef(_fam))
                if _def <= 0:
                    continue
                for _e in list(_havef(_fam)):
                    if _def <= 0:
                        break
                    if len(_e["contours"]) < 2 or _e.get("_ovr"):
                        continue
                    _pMf = page.paths[_e["path"]]["M"]
                    _cbs = []
                    for _c in _e["contours"]:
                        sp = _c["sp"]
                        b = transform_box(_pMf, sp["xmin"], sp["ymin"],
                                          sp["xmax"], sp["ymax"])
                        _cbs.append((min(b[0], b[2]), min(b[1], b[3]),
                                     max(b[0], b[2]), max(b[1], b[3]), _c))
                    _ok = [cb for cb in _cbs
                           if 3.0 <= cb[2] - cb[0] <= 11.0
                           and 2.0 <= cb[3] - cb[1] <= 6.0
                           and not any(o is not cb
                                       and o[0] <= cb[0] and o[1] <= cb[1]
                                       and o[2] >= cb[2] and o[3] >= cb[3]
                                       for o in _cbs)]
                    if len(_ok) < 2:
                        continue
                    _ok.sort(key=lambda cb: cb[0])
                    _keep = _ok[0]
                    for cb in _ok[1:]:
                        if _def <= 0:
                            break
                        if abs(((cb[0] + cb[2]) / 2)
                               - ((_keep[0] + _keep[2]) / 2)) < 3.0:
                            continue
                        _e["contours"] = [c for c in _e["contours"]
                                          if c is not cb[4]]
                        _ne = dict(_e)
                        _ne["contours"] = [cb[4]]
                        _ne["x1"], _ne["y1"], _ne["x2"], _ne["y2"] = cb[:4]
                        _ne.pop("mkmembers", None)
                        _ne.pop("sig", None)
                        _ne.pop("tanform", None)
                        _ne["mkpart"] = False
                        put_in_ligature(_atf, _ne)
                        _elf.append(_ne)
                        _def -= 1
                    _e["x1"] = min(cb[0] for cb in _cbs
                                   if cb[4] in _e["contours"])
                    _e["y1"] = min(cb[1] for cb in _cbs
                                   if cb[4] in _e["contours"])
                    _e["x2"] = max(cb[2] for cb in _cbs
                                   if cb[4] in _e["contours"])
                    _e["y2"] = max(cb[3] for cb in _cbs
                                   if cb[4] in _e["contours"])

    _enforce_overrides()

    # SMALL-NOON COMPLETION (Abdullah 2026-08-28, the mushaf's one ۨ site,
    # 21:88 نُـۨجِى p329): the superscript sign is a noon BOWL plus its dot.
    # The dot carries the table label; the bowl wears the letter-ن outline
    # (identical ink, 672 real letters share the sig) so no table entry can
    # name it — the SITE does. Weld the adjacent bowl into the unit.
    if os.environ.get("QSVG_SMALLNOON", "1") == "1":
        for _wn, _an in assignment:
            if not _wn or "\u06e8" not in _wn["uthmani"]:
                continue
            _eln = [e for a in _an for e in a["els"]]
            _m0 = next((e for e in _eln if e.get("mark") == "small-noon"
                        and not e.get("mkpart")), None)
            if _m0 is None:
                # the dot outline is SHARED with the jeem-sign dot, so no
                # table label may name it (it leaked onto p68). The SITE
                # names it: in the one U+06E8 word, the unnamed dot-sized
                # mark is the small-noon dot.
                _m0 = next((e for e in _eln if e["kind"] == "mark"
                            and not e.get("mark") and not e.get("mkpart")
                            and (e["x2"] - e["x1"]) < 4.0
                            and (e["y2"] - e["y1"]) < 4.0), None)
                if _m0 is not None:
                    _m0["mark"] = "small-noon"
                    _m0["lab"] = "small-noon"
            if _m0 is None or _m0.get("mkmembers"):
                continue
            _cx0 = (_m0["x1"] + _m0["x2"]) / 2
            _cy0 = (_m0["y1"] + _m0["y2"]) / 2
            _bowl = min((e for e in _eln if e["kind"] == "body"
                         and (e["x2"] - e["x1"]) * (e["y2"] - e["y1"]) < 30.0
                         and abs((e["x1"] + e["x2"]) / 2 - _cx0) < 6.0
                         and abs((e["y1"] + e["y2"]) / 2 - _cy0) < 6.0),
                        key=lambda e: abs((e["x1"] + e["x2"]) / 2 - _cx0)
                        + abs((e["y1"] + e["y2"]) / 2 - _cy0),
                        default=None)
            if _bowl is not None:
                _bowl["kind"] = "mark"
                _bowl["mark"] = "small-noon"
                _bowl["mkpart"] = True
                _bowl.pop("mkmembers", None)
                _m0.setdefault("mkmembers", []).append(_bowl)

    # COMPOSITE RESOLUTION — no "x+y" ever ships (Abdullah 2026-08-28).
    # A table label naming two marks describes ONE piece of artwork carrying
    # both. classify names the halves but leaves them welded, so the member
    # half counts through the master's name only and one mark vanishes from
    # every budget (p159 وَءَابَآؤُكُم lost the ؤ's damma). Resolve late,
    # after every namer: a welded member whose name differs from its
    # master's is its own mark — free it; a single element whose contours
    # can carry the names splits into one element per name, top-to-bottom.
    if os.environ.get("QSVG_CSPLIT", "1") == "1":
        _ctab = shape_labels()
        for _wc, _atc in assignment:
            if not _wc:
                continue
            for _ac in _atc:
                _addc = []
                for e in _ac["els"]:
                    if e.get("mkpart") or e["kind"] != "mark":
                        continue
                    _vc = _ctab.get(e.get("sig") or "")
                    _lbc = _vc.get("label") if isinstance(_vc, dict) else _vc
                    if not _lbc or "+" not in _lbc:
                        continue
                    _names = [x.strip() for x in _lbc.split("+")]
                    _mems = [m for m in (e.get("mkmembers") or [])
                             if m.get("mark") and m["mark"] != e.get("mark")]
                    if _mems:
                        for m in _mems:
                            m["mkpart"] = False
                        e["mkmembers"] = [m for m in e["mkmembers"]
                                          if m not in _mems]
                        if "+" in (e.get("mark") or ""):
                            e["mark"] = _names[0]
                            e["lab"] = _names[0]
                        continue
                    if len(e["contours"]) >= len(_names)                             and not e.get("mkmembers"):
                        _pM = page.paths[e["path"]]["M"]
                        _cbs = []
                        for c in e["contours"]:
                            sp = c["sp"]
                            bx1, by1, bx2, by2 = transform_box(
                                _pM, sp["xmin"], sp["ymin"],
                                sp["xmax"], sp["ymax"])
                            _cbs.append((c, min(by1, by2), max(by1, by2),
                                         min(bx1, bx2), max(bx1, bx2)))
                        _cbs.sort(key=lambda t: t[1] + t[2])
                        _gaps = sorted(range(1, len(_cbs)),
                                       key=lambda i: _cbs[i][1] - _cbs[i-1][2],
                                       reverse=True)[:len(_names) - 1]
                        _grpc, _prev = [], 0
                        for _cu in sorted(_gaps) + [len(_cbs)]:
                            _grpc.append(_cbs[_prev:_cu]); _prev = _cu
                        for _gi, _grp in enumerate(_grpc):
                            _bb = (min(t[3] for t in _grp),
                                   min(t[1] for t in _grp),
                                   max(t[4] for t in _grp),
                                   max(t[2] for t in _grp))
                            if _gi == 0:
                                e["contours"] = [t[0] for t in _grp]
                                e["mark"] = _names[0]
                                e["lab"] = _names[0]
                                e["x1"], e["y1"], e["x2"], e["y2"] = _bb
                            else:
                                _ne = dict(e)
                                _ne["contours"] = [t[0] for t in _grp]
                                _ne["mark"] = _names[_gi]
                                _ne["lab"] = _names[_gi]
                                _ne["x1"], _ne["y1"], _ne["x2"], _ne["y2"] = _bb
                                _ne.pop("sig", None)
                                _addc.append(_ne)
                if _addc:
                    _ac["els"].extend(_addc)

    # Final ء reconciliation. The mid-pipeline demote (see "runs late on
    # purpose" above) is no longer last: movers and table-label passes added
    # since can name a standalone ء "hamza" after it has run. Same rule,
    # re-applied once nothing renames after it: a hamza mark beyond the
    # word's carrier budget, standing inside the letter band of a word that
    # spells a bare ء, is that letter (p582 شَىْءٍ / p591 وَٱلسَّمَآءِ,
    # promoted by the r11 table label "hamza" — identical-ink trap #3).
    if os.environ.get("QSVG_HZA") != "0":
        _CARR10 = "\u0623\u0625\u0624\u0626\u0654\u0655"
        for _w10, _at10 in assignment:
            if not _w10 or "\u0621" not in _w10["uthmani"]:
                continue
            _txt10 = _w10["uthmani"]
            _els10 = [e for a in _at10 for e in a["els"]]
            _want10 = sum(_txt10.count(c) for c in _CARR10)
            _hz10 = [e for e in _els10 if e.get("mark") == "hamza"
                     and not e.get("mkpart")]
            if len(_hz10) <= _want10:
                continue
            _bod10 = [e for e in _els10 if e["kind"] == "body"]
            if not _bod10:
                continue
            _top10 = min(e["y1"] for e in _bod10)
            _bot10 = max(e["y2"] for e in _bod10)
            _inl10 = [e for e in _hz10
                      if e["y1"] >= _top10 - 1.5 and e["y2"] <= _bot10 + 1.5]
            _inl10.sort(key=lambda e: -((e["x2"] - e["x1"])
                                        * (e["y2"] - e["y1"])))
            for e in _inl10[:len(_hz10) - _want10]:
                for m in (e.get("mkmembers") or []):
                    m["mkpart"] = False
                e["mkmembers"] = []
                e["kind"] = "body"
                e["mark"] = None
                e["lab"] = "letter-hamza"

    # Text-driven dot REGROUPING (Abdullah 2026-08-28, p230 شيخا / p33 فبعث
    # family, 527 words). The digitizer draws a ث/ش triangle or a ي/ة pair as
    # separate outlines; every unit is present, only the grouping is wrong.
    # The text gives the grouping, the ink gives the positions. Welds happen
    # ONLY when the word's dot-unit total already equals its budget and the
    # weld makes the group vector match EXACTLY — counts can veto, never
    # approve (the SLASHX rule). Distance chooses between candidate partners
    # where arithmetic leaves a choice: measured mushaf-wide, wrong-grouping
    # nearest-dot distances are 1.6-2.1 (the 1+2 ث welds reach 2.7) while the
    # closest CORRECT distinct-letter dots sit at 2.3 with p1 = 3.2 and
    # p5 = 4.0 — 4.5 is far outside every weld actually owed and below
    # nothing that must stay apart.
    if os.environ.get("QSVG_DOTGROUP", "1") == "1":
        _D1 = "\u0628\u062c\u062e\u0630\u0632\u0636\u0638\u063a\u0641\u0646"
        _D2 = "\u062a\u0642\u0629\u064a"
        _D3 = "\u062b\u0634"
        _DFAM = {"dot": 1, "two-dots": 2, "three-dots": 3}
        _DNAME = {1: "dot", 2: "two-dots", 3: "three-dots"}
        for _wd, _atd in assignment:
            if not _wd:
                continue
            _txtd = _wd["uthmani"]
            _exp = {"dot": sum(_txtd.count(c) for c in _D1),
                    "two-dots": sum(_txtd.count(c) for c in _D2),
                    "three-dots": sum(_txtd.count(c) for c in _D3)}
            if not any(_exp.values()):
                continue
            _mast = [e for a in _atd for e in a["els"]
                     if e.get("mark") in _DFAM and not e.get("mkpart")]
            _nh = {k: sum(1 for e in _mast if e["mark"] == k) for k in _DFAM}
            if _nh == _exp:
                continue
            _ue = sum(_DFAM[k] * v for k, v in _exp.items())
            _uh = sum(_DFAM[k] * v for k, v in _nh.items())
            if _ue != _uh:
                continue        # a unit is missing or surplus — not a regroup
            # deficits must be strictly in BIGGER groups: outlines only weld
            _defs = [(k, _exp[k] - _nh[k]) for k in ("three-dots", "two-dots")
                     if _exp[k] > _nh[k]]
            if any(_exp[k] > _nh[k] for k in ("dot",)):
                continue        # would need splitting an outline — impossible
            _ctr = lambda e: ((e["x1"] + e["x2"]) / 2, (e["y1"] + e["y2"]) / 2)
            _dist = lambda a, b: ((_ctr(a)[0] - _ctr(b)[0]) ** 2
                                  + (_ctr(a)[1] - _ctr(b)[1]) ** 2) ** 0.5
            _plan = []
            _free = list(_mast)
            _ok = True
            for _fam, _need in _defs:
                _tgt = _DFAM[_fam]
                for _ in range(_need):
                    _best = None
                    _sm = [e for e in _free if e["mark"] != _fam]
                    # every subset of 2-3 smaller masters whose units sum to
                    # the target, tightest cluster first
                    import itertools as _it
                    for _r in (2, 3):
                        for _cmb in _it.combinations(_sm, _r):
                            if sum(_DFAM[e["mark"]] for e in _cmb) != _tgt:
                                continue
                            _dm = max(_dist(a, b)
                                      for i, a in enumerate(_cmb)
                                      for b in _cmb[i + 1:])
                            if _dm >= 4.5:
                                continue
                            if _best is None or _dm < _best[0]:
                                _best = (_dm, _cmb)
                    if _best is None:
                        _ok = False
                        break
                    _plan.append((_fam, _best[1]))
                    for e in _best[1]:
                        _free.remove(e)
                if not _ok:
                    break
            if not _ok or not _plan:
                continue
            # prove the resulting vector before touching anything
            _sim = dict(_nh)
            for _fam, _cmb in _plan:
                _sim[_fam] += 1
                for e in _cmb:
                    _sim[e["mark"]] -= 1
            if _sim != _exp:
                continue
            for _fam, _cmb in _plan:
                _hd = max(_cmb, key=lambda e: (e["x2"] - e["x1"])
                          * (e["y2"] - e["y1"]))
                _hd["mark"] = _fam
                _hd["lab"] = _fam
                for e in _cmb:
                    if e is _hd:
                        continue
                    e["mkpart"] = True
                    _hd.setdefault("mkmembers", []).append(e)

    # LATE TANWEEN PAIR REJOIN (Abdullah 2026-08-28: 23 single-stroke
    # tanween masters mushaf-wide — p535 held five). The mid-pipeline weld
    # runs before the movers and the late renames, and either can leave a
    # master standing alone while its twin sits beside it wearing "fatha"/
    # "kasra". Two signals to weld: pair geometry (dx<8, dy<7 — the measured
    # tanween pair envelope) AND the twin must be SURPLUS to its own
    # family's budget. Same-name surplus masters weld the same way.
    if os.environ.get("QSVG_TANPAIR", "1") == "1":
        _TP = {"fathatan": ("\u064b\u08f0", ("fatha",), "\u064e"),
               "kasratan": ("\u064d\u08f2", ("kasra",), "\u0650"),
               "dammatan": ("\u064c\u08f1", ("damma",), "\u064f")}
        for _wt2, _at2 in assignment:
            if not _wt2:
                continue
            _txv = _wt2["uthmani"]
            _elv = [e for a in _at2 for e in a["els"]]
            for _fam, (_tch, _sng, _sch) in _TP.items():
                _want = sum(_txv.count(c) for c in _tch)
                if not _want:
                    # the word has NO budget for this tanween at all — a
                    # single stroke wearing its name escaped every check
                    # below (p535 مَقْطُوعَةࣲ, the last survivor of the
                    # 19). It is the single vowel; multi-stroke pairs stay
                    # (a stolen whole pair is an ownership question).
                    for _m1 in _elv:
                        if _m1.get("mark") == _fam \
                                and not _m1.get("mkpart") \
                                and not _m1.get("mkmembers") \
                                and len(_m1["contours"]) == 1:
                            _m1["mark"] = _sng[0]
                            _m1["lab"] = _sng[0]
                            _m1.pop("tanform", None)
                    continue
                _mst = [e for e in _elv if e.get("mark") == _fam
                        and not e.get("mkpart")]
                # surplus same-name masters first
                while len(_mst) > _want:
                    _bp = None
                    for i, a1 in enumerate(_mst):
                        for b1 in _mst[i + 1:]:
                            dx = abs((a1["x1"] + a1["x2"]) / 2
                                     - (b1["x1"] + b1["x2"]) / 2)
                            dy = abs((a1["y1"] + a1["y2"]) / 2
                                     - (b1["y1"] + b1["y2"]) / 2)
                            if dx < 8.0 and dy < 7.0 and (
                                    _bp is None or dx + dy < _bp[0]):
                                _bp = (dx + dy, a1, b1)
                    if not _bp:
                        break
                    _, a1, b1 = _bp
                    b1["mkpart"] = True
                    for m in (b1.pop("mkmembers", None) or []):
                        m["mkpart"] = True
                        a1.setdefault("mkmembers", []).append(m)
                    a1.setdefault("mkmembers", []).append(b1)
                    _mst.remove(b1)
                # single-stroke masters missing their twin
                for _m1 in _mst:
                    if _m1.get("mkmembers") or len(_m1["contours"]) > 1:
                        continue
                    _own = sum(_txv.count(c) for c in _sch)
                    _hld = [e for e in _elv if e.get("mark") in _sng
                            and not e.get("mkpart")]
                    if len(_hld) <= _own:
                        continue          # no surplus single — nothing owed
                    _cx1 = (_m1["x1"] + _m1["x2"]) / 2
                    _cy1 = (_m1["y1"] + _m1["y2"]) / 2
                    _tw = min((e for e in _hld
                               if abs((e["x1"] + e["x2"]) / 2 - _cx1) < 8.0
                               and abs((e["y1"] + e["y2"]) / 2 - _cy1) < 7.0),
                              key=lambda e: abs((e["x1"] + e["x2"]) / 2 - _cx1)
                              + abs((e["y1"] + e["y2"]) / 2 - _cy1),
                              default=None)
                    if _tw is None:
                        continue
                    _tw["mkpart"] = True
                    _tw["mark"] = _fam
                    _m1.setdefault("mkmembers", []).append(_tw)
                # TWIN RETRIEVAL (Abdullah 2026-08-28: "tanween is always
                # at the END of the word — a stroke at the next word's right
                # edge, mostly outside its ink, is the rest of the previous
                # word's tanween", the 8eb38c verdict). Gate: the master is
                # single-stroke (budget-proven deficit) AND the candidate in
                # the FOLLOWING word lies within the measured pair envelope
                # (dx<8, dy<7). Slash strokes never cross words on position
                # alone — this pass moves only what a deficit demands.
                for _m1 in _mst:
                    if _m1.get("mkmembers") or len(_m1["contours"]) > 1:
                        _later = False
                        continue
                    _cx1 = (_m1["x1"] + _m1["x2"]) / 2
                    _cy1 = (_m1["y1"] + _m1["y2"]) / 2
                    _wi9 = next((i9 for i9, (w9, _) in enumerate(assignment)
                                 if w9 is _wt2), None)
                    if _wi9 is None or _wi9 + 1 >= len(assignment):
                        continue
                    _wnx, _anx = assignment[_wi9 + 1]
                    if not _wnx:
                        continue
                    _cand9 = None
                    _SCH9 = {"fatha": "\u064e", "kasra": "\u0650",
                             "damma": "\u064f"}
                    _nb9 = [x for a9 in _anx for x in a9["els"]
                            if x["kind"] == "body"]
                    _nbr = max((x["x2"] for x in _nb9), default=None)
                    for _a9 in _anx:
                        for e9 in _a9["els"]:
                            if (e9.get("mark") not in ("fatha", "kasra",
                                                       "damma")
                                    or e9.get("_ovr")
                                    or e9.get("mkpart")
                                    or abs((e9["x1"] + e9["x2"]) / 2
                                           - _cx1) >= 8.0
                                    or abs((e9["y1"] + e9["y2"]) / 2
                                           - _cy1) >= 7.0):
                                continue
                            # the holder must not need it: surplus to its
                            # own budget, OR drawn mostly OUTSIDE the
                            # holder's ink past its right edge (the
                            # boundary rule)
                            # PROOF only: the stroke's hull must lie at
                            # least 3/4 outside the holder's body hull —
                            # surplus alone cannot say WHICH stroke, and a
                            # first-letter fatha legitimately floats right
                            # of its word's body start (p77 re-taught the
                            # forbidden-slash-move lesson)
                            _nbl = min((x["x1"] for x in _nb9), default=None)
                            if _nbr is None or _nbl is None:
                                continue
                            _w9 = e9["x2"] - e9["x1"]
                            _ov9 = (min(e9["x2"], _nbr)
                                    - max(e9["x1"], _nbl))
                            if _w9 > 0 and _ov9 / _w9 < 0.25:
                                _cand9 = (e9, _a9)
                                break
                        if _cand9:
                            break
                    if not _cand9:
                        continue
                    e9, _a9 = _cand9
                    _a9["els"].remove(e9)
                    put_in_ligature(_at2, e9)
                    e9["mkpart"] = True
                    e9["mark"] = _fam
                    e9["lab"] = _fam
                    e9["line"] = _m1.get("line")
                    _m1.setdefault("mkmembers", []).append(e9)
                # a tanween NAME requires two strokes (Abdullah 2026-08-28,
                # d7a8b5/c9b82d verdicts: these are single fathas). A master
                # still standing on one contour with no twin found does not
                # get to wear the pair's name — it is the single vowel, and
                # the missing twin flags honestly in the budget audit.
                for _m1 in list(_mst):
                    if _m1.get("mkmembers") or len(_m1["contours"]) > 1:
                        continue
                    _m1["mark"] = _sng[0]
                    _m1["lab"] = _sng[0]
                    _m1.pop("tanform", None)
                    _mst.remove(_m1)     # the deficit must become VISIBLE
                                         # to the missing-master branch
                # MISSING MASTER (Abdullah 2026-08-28: p131 رُسُلࣱ held a
                # fused dammatan outline named "damma"; p585's pair half the
                # same). When the word is OWED a tanween and no master
                # exists: a surplus single with two-plus contours IS the
                # fused pair — rename it; else two surplus singles in the
                # pair envelope on the word's end side weld.
                if len(_mst) < _want:
                    # a slash pair's twins can be misnamed ACROSS fatha and
                    # kasra (one stroke, position-named): pool both for the
                    # slash tanweens (Abdullah's p529 أَمْرࣲ verdict —
                    # kasra e361 + "fatha" e362 are the kasratan)
                    if _fam in ("fathatan", "kasratan"):
                        _pool_nm = ("fatha", "kasra")
                        _ownw = _txv.count("\u064e") + _txv.count("\u0650")
                    else:
                        _pool_nm = (_sng[0],)
                        _ownw = sum(_txv.count(c) for c in _sch)
                    _sgl2 = [e for e in _elv if e.get("mark") in _pool_nm
                             and not e.get("mkpart")]
                    if len(_sgl2) > _ownw:
                        _fx1 = min((b["x1"] for a2_ in _at2
                                    for b in a2_["els"]
                                    if b["kind"] == "body"), default=None)
                        _fx2 = max((b["x2"] for a2_ in _at2
                                    for b in a2_["els"]
                                    if b["kind"] == "body"), default=None)
                        def _endside(e):
                            if _fx1 is None or _fx2 - _fx1 < 8.0:
                                return True
                            return (_fx2 - (e["x1"] + e["x2"]) / 2) \
                                / (_fx2 - _fx1) > 0.5
                        for e in _sgl2:
                            if len(_mst) >= _want:
                                break
                            _units2 = len(e["contours"]) + sum(
                                len(x["contours"])
                                for x in (e.get("mkmembers") or []))
                            if _units2 >= 2 and _endside(e):
                                e["mark"] = _fam
                                e["lab"] = _fam
                                for x in (e.get("mkmembers") or []):
                                    x["mark"] = _fam
                                _mst.append(e)
                        if len(_mst) < _want:
                            for i2, a2 in enumerate(_sgl2):
                                if len(_mst) >= _want:
                                    break
                                for b2 in _sgl2[i2 + 1:]:
                                    dx = abs((a2["x1"] + a2["x2"]) / 2
                                             - (b2["x1"] + b2["x2"]) / 2)
                                    dy = abs((a2["y1"] + a2["y2"]) / 2
                                             - (b2["y1"] + b2["y2"]) / 2)
                                    if dx < 8.0 and dy < 7.0 \
                                            and _endside(a2):
                                        a2["mark"] = _fam
                                        a2["lab"] = _fam
                                        b2["mkpart"] = True
                                        b2["mark"] = _fam
                                        a2.setdefault("mkmembers",
                                                      []).append(b2)
                                        _mst.append(a2)
                                        break
                # POSITION SWAP (Abdullah 2026-08-28, p208 مُّبِينٌ):

                # kasratan/dammatan end their word — a master welded at the
                # word's START while two loose same-family singles stand
                # interlocked at the END is inverted. Two signals: the
                # master fails the position law AND a true pair (two
                # singles within the pair envelope) exists on the end side.
                if _fam in ("kasratan", "dammatan"):
                    _bx1 = min((b["x1"] for a2_ in _at2
                                for b in a2_["els"]
                                if b["kind"] == "body"), default=None)
                    _bx2 = max((b["x2"] for a2_ in _at2
                                for b in a2_["els"]
                                if b["kind"] == "body"), default=None)
                    if _bx1 is not None and _bx2 is not None \
                            and _bx2 - _bx1 > 8.0:
                        _spn = _bx2 - _bx1
                        for _m1 in list(_mst):
                            _rel = (_bx2 - (_m1["x1"] + _m1["x2"]) / 2) / _spn
                            if _rel > 0.45:
                                continue      # master already end-side
                            _sgl = [e for e in _elv
                                    if e.get("mark") == _sng[0]
                                    and not e.get("mkpart")]
                            _prq = None
                            for i2, a2 in enumerate(_sgl):
                                for b2 in _sgl[i2 + 1:]:
                                    dx = abs((a2["x1"] + a2["x2"]) / 2
                                             - (b2["x1"] + b2["x2"]) / 2)
                                    dy = abs((a2["y1"] + a2["y2"]) / 2
                                             - (b2["y1"] + b2["y2"]) / 2)
                                    _r2 = (_bx2 - (a2["x1"] + a2["x2"]) / 2) \
                                        / _spn
                                    if dx < 8.0 and dy < 7.0 and _r2 > 0.55:
                                        _prq = (a2, b2)
                                        break
                                if _prq:
                                    break
                            if not _prq:
                                continue
                            a2, b2 = _prq
                            # the pair takes the name; the master unwelds to
                            # its singles (their surplus flags honestly)
                            a2["mark"] = _fam
                            a2["lab"] = _fam
                            b2["mkpart"] = True
                            b2["mark"] = _fam
                            a2.setdefault("mkmembers", []).append(b2)
                            for _mm2 in (_m1.pop("mkmembers", None) or []):
                                _mm2["mkpart"] = False
                                _mm2["mark"] = _sng[0]
                                _mm2["lab"] = _sng[0]
                            _m1["mark"] = _sng[0]
                            _m1["lab"] = _sng[0]
                            _m1.pop("tanform", None)
                            _mst.remove(_m1)
                            _mst.append(a2)
    # BODY RETURN (Abdullah 2026-08-28, 3:75:19: the whole rasm of ما
    # held by يؤده on the line above). Proof class on BOTH sides: the
    # victim holds ZERO bodies; the holder counts more pieces than the
    # joining rules allow (segment_word). The nearest such surplus piece
    # overlapping the victim's mark-span comes home.
    if os.environ.get("QSVG_BODYRET", "1") == "1":
        _wlist = [(w, at) for (w, at) in assignment if w]
        for _wV, _atV in _wlist:
            _elV = [e for a in _atV for e in a["els"]]
            if any(e["kind"] == "body" for e in _elV):
                continue
            _mks = [e for e in _elV if e["kind"] == "mark"]
            if not _mks:
                continue
            _vx1 = min(e["x1"] for e in _mks) - 6.0
            _vx2 = max(e["x2"] for e in _mks) + 6.0
            _vy = sum((e["y1"] + e["y2"]) / 2 for e in _mks) / len(_mks)
            _best = None
            for _wH, _atH in _wlist:
                if _wH is _wV:
                    continue
                _bH = [e for a in _atH for e in a["els"]
                       if e["kind"] == "body" and not e.get("mkpart")]
                try:
                    _allow = max(1, len(segment_word(_wH["uthmani"])))
                except Exception:
                    continue
                if len(_bH) <= _allow:
                    continue        # holder is not over its piece budget
                for e in _bH:
                    _cx = (e["x1"] + e["x2"]) / 2
                    _cy = (e["y1"] + e["y2"]) / 2
                    if not (_vx1 <= _cx <= _vx2):
                        continue
                    _d = abs(_cy - _vy)
                    if _d > 45.0:
                        continue
                    if _best is None or _d < _best[0]:
                        _best = (_d, e, _atH)
            if _best is None:
                continue
            _, _eB, _atH = _best
            for _a in _atH:
                if _eB in _a["els"]:
                    _a["els"].remove(_eB)
                    break
            put_in_ligature(_atV, _eB)

    # BUDGET RETURN for unambiguous marks (Abdullah 2026-08-28, p431
    # رَبُّكُمْۖ wearing إِلَّا's hamza): the holder has NO budget for the
    # family, a vertically-adjacent word overlapping the ink's x has an
    # unfilled budget — surplus meets deficit and the shape is not a
    # derived slash/damma, so the move is exact on both sides. The mark
    # returns and re-seats in the right ligature.
    if os.environ.get("QSVG_BUDGETRET", "1") == "1":
        _URFAM = {"hamza": ("\u0623\u0625\u0624\u0626\u0654\u0655", 1),
                  "meem-iqlab": ("\u06e2\u06ed", 1),
                  "sukun": ("\u0652\u06e1", 1),
                  "shadda": ("\u0651", 1),
                  "maddah": ("\u0653\u06e4", 1)}
        _widr = [(w, at) for (w, at) in assignment if w]
        for _wH, _atH in _widr:
            _elH = [e for a in _atH for e in a["els"]]
            for _fam9, (_chs9, _) in _URFAM.items():
                _bud9 = sum((_wH.get("qpc") or _wH["uthmani"]).count(c)
                            for c in _chs9)
                _held9 = [e for e in _elH if e.get("mark") == _fam9
                          and not e.get("mkpart")]
                if len(_held9) <= _bud9:
                    continue
                for _eH in list(_held9[_bud9:]):
                    if _eH.get("_ovr"):
                        continue
                    _cxh = (_eH["x1"] + _eH["x2"]) / 2
                    _best9 = None
                    for _wR, _atR in _widr:
                        if _wR is _wH:
                            continue
                        _bR = [e for a in _atR for e in a["els"]
                               if e["kind"] == "body"]
                        if not _bR:
                            continue
                        _rx1 = min(e["x1"] for e in _bR)
                        _rx2 = max(e["x2"] for e in _bR)
                        if not (_rx1 - 2.0 <= _cxh <= _rx2 + 2.0):
                            continue
                        _bud_r = sum((_wR.get("qpc")
                                      or _wR["uthmani"]).count(c)
                                     for c in _chs9)
                        _held_r = sum(1 for a in _atR for e in a["els"]
                                      if e.get("mark") == _fam9
                                      and not e.get("mkpart"))
                        _ry1 = min(e["y1"] for e in _bR)
                        _ry2 = max(e["y2"] for e in _bR)
                        _rename_to = None
                        if _held_r >= _bud_r:
                            # the family is full — but a SLASH-shaped piece
                            # wearing this name may be the receiver's owed
                            # fatha/kasra (p431: إلا's kasra rode along
                            # named "hamza"). Ratio test + deficit.
                            _wq9 = _eH["x2"] - _eH["x1"]
                            _hq9 = _eH["y2"] - _eH["y1"] or 0.1
                            if _wq9 / _hq9 < 1.8:
                                continue
                            _txR = _wR["uthmani"]
                            _fb = _txR.count("\u064e")
                            _kb = _txR.count("\u0650")
                            _fh = sum(1 for a in _atR for e in a["els"]
                                      if e.get("mark") == "fatha"
                                      and not e.get("mkpart"))
                            _kh = sum(1 for a in _atR for e in a["els"]
                                      if e.get("mark") == "kasra"
                                      and not e.get("mkpart"))
                            _rmid = (_ry1 + _ry2) / 2 if _bR else 0
                            _cyh2 = (_eH["y1"] + _eH["y2"]) / 2
                            _owed = []
                            if _kh < _kb:
                                _owed.append("kasra")
                            if _fh < _fb:
                                _owed.append("fatha")
                            if len(_owed) == 1:
                                # unique deficit names the arrival — the
                                # stroke was drawn displaced, so its
                                # position cannot testify
                                _rename_to = _owed[0]
                            elif len(_owed) == 2:
                                _rename_to = ("kasra" if _cyh2 > _rmid
                                              else "fatha")
                            else:
                                continue
                        # vertical adjacency: receiver band within a line
                        # height of the ink
                        _cyh = (_eH["y1"] + _eH["y2"]) / 2
                        _dv = 0.0 if _ry1 - 18.0 <= _cyh <= _ry2 + 18.0 \
                            else 1e9
                        if _dv < 1e9 and (_best9 is None):
                            _best9 = (_wR, _atR, _rename_to)
                    if _best9 is None:
                        continue
                    _wR, _atR, _rename_to = _best9
                    for _a9 in _atH:
                        if _eH in _a9["els"]:
                            _a9["els"].remove(_eH)
                            break
                    put_in_ligature(_atR, _eH)
                    if _best9 and _rename_to:
                        _eH["mark"] = _rename_to
                        _eH["lab"] = _rename_to
                    _held9.remove(_eH)

    # BOUNDARY SLASH RETURN (Abdullah 2026-08-28, the كَانَ picture): a
    # stroke named "fatha" drawn BELOW its word's letter band at the edge
    # toward a neighbour is that neighbour's kasra (and symmetrically). The
    # SLASHX veto guards it: the move is applied ONLY when it makes BOTH
    # words' plain fatha AND kasra counts exactly match their budgets —
    # counts can veto, never approve.
    if os.environ.get("QSVG_SLASHRET", "1") == "1":
        _widx = [(i, w, at) for i, (w, at) in enumerate(assignment) if w]
        def _scnt(at_):
            f = k = 0
            for a_ in at_:
                for e_ in a_["els"]:
                    if e_.get("mkpart"):
                        continue
                    if e_.get("mark") == "fatha":
                        f += 1
                    elif e_.get("mark") == "kasra":
                        k += 1
            return f, k
        for _pi9 in range(len(_widx) - 1):
            for (_, _wA, _atA), (_, _wB, _atB) in (
                    (_widx[_pi9], _widx[_pi9 + 1]),
                    (_widx[_pi9 + 1], _widx[_pi9])):
                _bA = [e for a in _atA for e in a["els"]
                       if e["kind"] == "body"]
                _bB = [e for a in _atB for e in a["els"]
                       if e["kind"] == "body"]
                if not _bA or not _bB:
                    continue
                _topA = min(e["y1"] for e in _bA)
                _botA = max(e["y2"] for e in _bA)
                # same line only
                _topB = min(e["y1"] for e in _bB)
                if abs(_topA - _topB) > 12.0:
                    continue
                _fbA = _wA["uthmani"].count("\u064e")
                _kbA = _wA["uthmani"].count("\u0650")
                _fbB = _wB["uthmani"].count("\u064e")
                _kbB = _wB["uthmani"].count("\u0650")
                _fA, _kA = _scnt(_atA)
                _fB, _kB = _scnt(_atB)
                for _aX in _atA:
                    for _eX in list(_aX["els"]):
                        mkX = _eX.get("mark")
                        if mkX not in ("fatha", "kasra") \
                                or _eX.get("_ovr") \
                                or _eX.get("mkpart") \
                                or _eX.get("mkmembers"):
                            continue
                        _cy = (_eX["y1"] + _eX["y2"]) / 2
                        if mkX == "fatha" and _cy > _botA + 1.0:
                            _nm = "kasra"
                        elif mkX == "kasra" and _cy < _topA - 1.0:
                            _nm = "fatha"
                        else:
                            continue
                        # the veto: BOTH words exact after the move
                        _fA2 = _fA - (mkX == "fatha")
                        _kA2 = _kA - (mkX == "kasra")
                        _fB2 = _fB + (_nm == "fatha")
                        _kB2 = _kB + (_nm == "kasra")
                        if not (_fA2 == _fbA and _kA2 == _kbA
                                and _fB2 == _fbB and _kB2 == _kbB):
                            continue
                        _aX["els"].remove(_eX)
                        put_in_ligature(_atB, _eX)
                        _eX["mark"] = _nm
                        _eX["lab"] = _nm
                        _fA, _kA = _fA2, _kA2
                        _fB, _kB = _fB2, _kB2

    # INVERTED SLASH PAIR (Abdullah 2026-08-28, e707/e710: a "kasra" at the
    # TOP of its word with a "fatha" at the BOTTOM — the names are swapped).
    # Swapping back is COUNT-NEUTRAL: both family budgets keep their exact
    # totals, position law is restored, nothing moves. The only safe
    # automatic slash rename.
    if os.environ.get("QSVG_SLASHSWAP", "1") == "1":
        for _ws2, _as2 in assignment:
            if not _ws2:
                continue
            _el2 = [e for a in _as2 for e in a["els"]]
            _kas = [e for e in _el2 if e.get("mark") == "kasra"
                    and not e.get("mkpart")]
            _fat = [e for e in _el2 if e.get("mark") == "fatha"
                    and not e.get("mkpart")]
            # the full law: ALL of a word's fathas ride above ALL its
            # kasras. When the current names violate that order, re-deal
            # them by height — top N stay fathas, bottom M kasras. Exactly
            # count-neutral by construction.
            _fb0 = _ws2["uthmani"].count("\u064e")
            _kb0 = _ws2["uthmani"].count("\u0650")
            _all0 = _kas + _fat
            if _all0 and len(_all0) == _fb0 + _kb0 \
                    and (len(_fat) != _fb0 or len(_kas) != _kb0
                         or (_kas and _fat
                             and any(k["y2"] < f["y1"] - 0.5
                                     for k in _kas for f in _fat))):
                # total matches the budget but the split or the order is
                # wrong (p482 إلا: TWO "fathas", zero kasras, budget 1+1)
                # — deal by height against the BUDGET: top fathas, bottom
                # kasras. Count-neutral against the text by construction.
                _all0.sort(key=lambda e: (e["y1"] + e["y2"]) / 2)
                for i9, e in enumerate(_all0):
                    nm = "fatha" if i9 < _fb0 else "kasra"
                    e["mark"] = nm
                    e["lab"] = nm

    out_svg = rewrite(page, assignment)
    polys_all = json.load(open(polys_path)) if os.path.exists(polys_path) else []
    out_svg = tag_ayah_markers(out_svg, polys_all)
    return page, out_svg, report, coverage


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("edition")
    ap.add_argument("page", type=int)
    ap.add_argument("--words-cache", default=os.path.join(ROOT, ".cache", "words"))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    page, out_svg, report, (labeled, total_marks) = assign_page(
        args.edition, args.page, args.words_cache)

    out_dir = args.out_dir or os.path.join(ROOT, ".cache", "words-svg",
                                           args.edition.replace("/", "-"))
    os.makedirs(out_dir, exist_ok=True)
    svg_path = os.path.join(out_dir, "%03d.svg" % args.page)
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(out_svg)
    rep_path = os.path.join(out_dir, "%03d.report.json" % args.page)
    json.dump(report, open(rep_path, "w"), indent=1)

    need = [r for r in report if r["review"]]
    print("wrote %s — %d lines, %d flagged for review; marks shape-labeled %d/%d"
          % (svg_path, len(report), len(need), labeled, total_marks))
    for r in need:
        print("  line %2d: words=%d clusters=%d deviation=%s flags=%s"
              % (r["line"], r["words"], r["clusters"], r["deviation"], r["flags"]))


if __name__ == "__main__":
    main()
