/* mushaf.js — cross-page lookup.
 *
 * A single page file cannot answer "which page is 2:255 on". This reads a
 * small generated index (build-atlas.py, ~30 KB raw / ~8 KB gzip).
 *
 * NOTHING IN THE CORE IMPORTS THIS. The library works without the index and
 * gains cross-page lookup when it is present. Whether the index ships beside
 * the SVGs is a packaging decision, not a technical one.
 *
 * The index leans on one fact from FORMAT §12: NO AYAH SPANS TWO PAGES. So the
 * first ayah of each page is enough to answer pageOf() by binary search.
 */

const num = aid => { const [s, a] = String(aid).split(':').map(Number); return s * 1000 + a; };

export class MushafAtlas {
  constructor(data) {
    if (!data || data.schema !== 'mushaf-atlas') throw new Error('not a mushaf-atlas index');
    this.data = data;
    this._first = data.pageFirstAyah.map(num);
    this._surahs = new Map(data.surahs.map(s => [s.n, s]));
  }

  get pages() { return this.data.pages; }
  get edition() { return this.data.edition; }

  /** Which page draws this ayah? */
  pageOf(aid) {
    const k = num(aid);
    const f = this._first;
    if (k < f[0]) return null;
    let lo = 0, hi = f.length - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (f[mid] <= k) lo = mid; else hi = mid - 1; }
    return lo + 1;
  }
  /** Which page is a whole word key on? */
  pageOfWord(wid) { const p = String(wid).split(':'); return this.pageOf(p[0] + ':' + p[1]); }

  /** The first and last ayah drawn on a page. */
  pageRange(n) {
    const d = this.data.pageFirstAyah;
    if (n < 1 || n > d.length) return null;
    return { page: n, first: d[n - 1], last: this.data.pageLastAyah[n - 1] };
  }

  surah(n) { return this._surahs.get(Number(n)) || null; }
  pageOfSurah(n) { return this.surah(n)?.page ?? null; }
  get surahs() { return this.data.surahs; }

  /** Fuzzy surah lookup by Arabic, Latin or English name, or by number. */
  findSurah(q) {
    const s = String(q).trim();
    if (/^\d+$/.test(s)) return this.surah(Number(s)) ? [this.surah(Number(s))] : [];
    const k = s.toLowerCase().replace(/[^a-z؀-ۿ ]/g, '');
    return this.data.surahs.filter(x =>
      (x.latin || '').toLowerCase().replace(/[^a-z ]/g, '').includes(k) ||
      (x.en || '').toLowerCase().includes(k) ||
      (x.ar || '').includes(s));
  }

  division(kind, n) { return (this.data[kind] || []).find(d => d.n === Number(n)) || null; }
  juz(n) { return this.division('juz', n); }
  hizb(n) { return this.division('hizb', n); }
  rub(n) { return this.division('rub', n); }
  nisf(n) { return this.division('nisf', n); }

  /** [firstPage, lastPage] of a juz. */
  pagesOfJuz(n) {
    const a = this.juz(n), b = this.juz(Number(n) + 1);
    if (!a) return null;
    return [a.page, b ? b.page : this.pages];
  }

  /** Which juz / hizb / rubʿ is this ayah in? */
  divisionAt(kind, aid) {
    const k = num(aid), list = this.data[kind] || [];
    let out = null;
    for (const d of list) { if (num(d.aid) <= k) out = d; else break; }
    return out;
  }
  juzAt(aid) { return this.divisionAt('juz', aid); }
  hizbAt(aid) { return this.divisionAt('hizb', aid); }
  rubAt(aid) { return this.divisionAt('rub', aid); }
}

export async function loadAtlas(url = 'atlas.json', { fetch: f = null } = {}) {
  const res = await (f || globalThis.fetch)(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return new MushafAtlas(await res.json());
}

export function atlasFrom(data) { return new MushafAtlas(data); }
