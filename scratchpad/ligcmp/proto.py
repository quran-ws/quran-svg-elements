import os, sys, io, re, json, contextlib
os.environ.setdefault('QSVG_ROOT', os.getcwd())
ROOT = os.environ['QSVG_ROOT']
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import xml.etree.ElementTree as ET
import polygon_lib as pl

NS = '{http://www.w3.org/2000/svg}'
REF = os.path.expanduser('~/Dev/github.com/AbdullahObaid/MushafDatabase-Ligature-Based-SVG/SVG V1.01')

_KEEP = set(range(0x0621, 0x064B)) | {0x0671, 0x0672, 0x0673, 0x0675, 0x0640}
def skel(t):
    return "".join(c for c in (t or "") if ord(c) in _KEEP)

WAQF = "ۖۗۘۙۚۛۜ۝۞۩"


def ref_page(pg):
    """{(s,a,pos): dict(line, hafs, runs=[(text,x1,x2)])} using audit_reference folding."""
    p = os.path.join(REF, '%03d.svg' % pg)
    if not os.path.exists(p):
        return {}
    root = ET.parse(p).getroot()
    seq = {}
    for w in root.iter(NS + 'g'):
        wid = w.get('id') or ''
        if not wid.startswith('md-word-'):
            continue
        if w.get('data-type') != 'text':
            continue
        try:
            sa = (int(w.get('data-surah')), int(w.get('data-aya')))
            idx = int(w.get('data-word-index-in-ayah'))
        except (TypeError, ValueError):
            continue
        runs = []
        for L in w:
            if not (L.get('id') or '').startswith('md-ligature-'):
                continue
            tp = [x for x in L if x.tag == NS + 'path' and x.get('data-type') == 'text']
            if not tp:
                runs.append((None, None, None))
                continue
            txt = "".join(x.get('data-text') or '' for x in tp)
            bb = [pl._glyph_bbox(x.get('d')) for x in tp]
            x1 = min(b[0] for b in bb); x2 = max(b[2] for b in bb)
            runs.append((txt, x1, x2))
        seq.setdefault(sa, []).append((idx, int(w.get('data-line-number') or 0),
                                       w.get('data-hafs') or '',
                                       w.get('data-waw-alatf') == 'true', runs))
    out = {}
    for sa, items in seq.items():
        items.sort()
        merged = []
        pend_t, pend_r = "", []
        for _, ln, txt, waw, runs in items:
            if waw:
                pend_t += txt; pend_r += runs; continue
            if txt and all(c in WAQF or c.isspace() for c in txt):
                if merged:
                    continue
            merged.append([ln, pend_t + txt, pend_r + runs])
            pend_t, pend_r = "", []
        if pend_t and merged:
            merged.append([merged[-1][0], pend_t, pend_r])
        for i, (ln, txt, runs) in enumerate(merged, 1):
            out[(sa[0], sa[1], i)] = dict(line=ln, hafs=txt, runs=runs)
    return out


CAP = {}
import assign_words as aw
_orig = aw.rewrite
aw.rewrite = lambda p, a: (CAP.__setitem__('a', a), _orig(p, a))[1]


def our_page(pg):
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page('hafs/kfqc', pg, os.path.join(ROOT, '.cache', 'words'))
    out = {}
    for w, atoms in CAP['a']:
        if not w:
            continue
        groups = []
        for ai, a in enumerate(atoms):
            lk = a.get('lig', ai)
            els = a.get('els') or []
            if groups and groups[-1]['lig'] == lk:
                groups[-1]['els'].extend(els)
            else:
                groups.append({'lig': lk, 'els': list(els),
                               'named': (a.get('seg') or {}).get('text', '')})
        runs = []
        for g in groups:
            body = [e for e in g['els'] if e['kind'] == 'body']
            runs.append((g['named'],
                         min((e['x1'] for e in body), default=None),
                         max((e['x2'] for e in body), default=None)))
        out[(w['surah'], w['ayah'], w['pos'])] = dict(
            uthmani=w['uthmani'], runs=runs,
            segs=[s['text'] for s in (aw.segment_word(w['uthmani']) or [])])
    return out


if __name__ == '__main__':
    pg = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    r = ref_page(pg); o = our_page(pg)
    both = sorted(set(r) & set(o))
    print('ref %d ours %d both %d' % (len(r), len(o), len(both)))
    n_txt = n_same = 0
    for k in both:
        if skel(r[k]['hafs']) != skel(o[k]['uthmani']):
            n_txt += 1; continue
        rr = [skel(t) for t, a, b in r[k]['runs']]
        oo = [skel(t) for t, a, b in o[k]['runs']]
        if rr == oo:
            n_same += 1
        else:
            print('%-11s %-16s ref=%s | ours=%s | segs=%s' % (
                '%d:%d:%d' % k, o[k]['uthmani'], rr, oo, [skel(s) for s in o[k]['segs']]))
    print('text-mismatch %d, run-seq identical %d / %d' % (n_txt, n_same, len(both) - n_txt))
