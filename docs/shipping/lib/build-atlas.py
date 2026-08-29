#!/usr/bin/env python3
"""Generate the cross-page index atlas.mjs reads.

    python3 build-atlas.py <pages-dir> [-o atlas.json]

Everything is measured from the real page SVGs. Nothing is hand-typed, and no
Quranic text is written here: the surah names come out of the banner attributes
the files already carry.

The index leans on FORMAT §12: no ayah spans two pages, so one first-ayah key
per page answers "which page is 2:255 on" by binary search.
"""
import json, os, re, sys

AYAH = re.compile(r'<g class="ayah" data-aid="(\d+:\d+)"')
BANNER = re.compile(r'<g class="surah-name"([^>]*)>')
ATTR = re.compile(r'data-([a-z-]+)="([^"]*)"')
START = {k: re.compile(r'data-aid="(\d+:\d+)"[^>]*data-%s-start="(\d+)"' % k)
         for k in ('juz', 'hizb', 'nisf', 'rub')}
START_ALT = {k: re.compile(r'data-%s-start="(\d+)"[^>]*data-aid="(\d+:\d+)"' % k)
             for k in ('juz', 'hizb', 'nisf', 'rub')}


def main(pages_dir, out_path):
    files = sorted(f for f in os.listdir(pages_dir) if f.endswith('.svg'))
    first, last, surahs = [], [], {}
    div = {k: {} for k in START}

    for i, name in enumerate(files, 1):
        src = open(os.path.join(pages_dir, name), encoding='utf-8').read()
        aids = AYAH.findall(src)
        if not aids:
            raise SystemExit('%s: no ayah groups' % name)
        first.append(aids[0])
        last.append(aids[-1])

        for attrs in BANNER.findall(src):
            d = dict(ATTR.findall(attrs))
            n = int(d['sid'])
            surahs.setdefault(n, {
                'n': n, 'ar': d.get('surah-name-ar'), 'latin': d.get('surah-name-latin'),
                'en': d.get('surah-name-en'), 'place': d.get('revelation-place'),
                'ayahs': int(d['ayah-count']) if d.get('ayah-count') else None, 'page': i})

        for k in START:
            for a, b in START[k].findall(src):
                div[k].setdefault(int(b), {'n': int(b), 'aid': a, 'page': i})
            for b, a in START_ALT[k].findall(src):
                div[k].setdefault(int(b), {'n': int(b), 'aid': a, 'page': i})

    data = {
        'schema': 'mushaf-atlas', 'version': 1, 'edition': 'hafs-kfgqpc',
        'pages': len(files),
        'firstAyah': first[0], 'lastAyah': last[-1],
        'pageFirstAyah': first, 'pageLastAyah': last,
        'surahs': [surahs[n] for n in sorted(surahs)],
    }
    for k in ('juz', 'hizb', 'nisf', 'rub'):
        data[k] = [div[k][n] for n in sorted(div[k])]

    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    print('%s: %d pages, %d surahs, juz %d, hizb %d, nisf %d, rub %d, %.1f KB' % (
        out_path, data['pages'], len(data['surahs']), len(data['juz']),
        len(data['hizb']), len(data['nisf']), len(data['rub']),
        os.path.getsize(out_path) / 1024))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    out = 'atlas.json'
    if '-o' in sys.argv:
        out = sys.argv[sys.argv.index('-o') + 1]
        args = [a for a in args if a != out]
    if not args:
        raise SystemExit(__doc__)
    main(args[0], out)
