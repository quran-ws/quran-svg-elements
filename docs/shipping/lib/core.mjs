/* mushaf.js — core
 *
 * Zero dependencies. Browser-first ES module. Operates on the Quran page SVGs
 * described in ../FORMAT.md; it never ships, bundles or writes them.
 *
 * Two rules hold everywhere in this file:
 *   - nothing mutates a page the caller did not hand us;
 *   - every mutating method returns a handle with .remove().
 */

export const SVGNS = 'http://www.w3.org/2000/svg';
export const XHTMLNS = 'http://www.w3.org/1999/xhtml';

/** The five text forms carried on every <g class="word">. FORMAT §6.1. */
export const TEXT_FORMS = ['uthmani', 'imlaei', 'qpc', 'rasm', 'search'];

/* ---------------------------------------------------------------- taxonomy */

/* An embedded copy of .cache/schema/mark-taxonomy.v2.json (schema
 * mark-taxonomy, version 2.0), name -> {category, family}.
 *
 * We resolve families through THIS table and select on data-mark, never on the
 * data-mark-family attribute. The emitted attribute and the registry disagree
 * in the current build: the files write "diacritic" for harakat AND tanween,
 * and never write "tanween" or "reading-sign" at all. Selecting by name works
 * under either vocabulary. See DESIGN.md §6. */
export const MARK_REGISTRY = Object.freeze({
  fatha:          { category: 'haraka',       family: null },
  kasra:          { category: 'haraka',       family: null },
  damma:          { category: 'haraka',       family: null },
  sukun:          { category: 'haraka',       family: null },
  shadda:         { category: 'haraka',       family: null },
  fathatan:       { category: 'tanween',      family: 'tanween' },
  kasratan:       { category: 'tanween',      family: 'tanween' },
  dammatan:       { category: 'tanween',      family: 'tanween' },
  dot:            { category: 'letter-dot',   family: 'dots' },
  'two-dots':     { category: 'letter-dot',   family: 'dots' },
  'three-dots':   { category: 'letter-dot',   family: 'dots' },
  hamza:          { category: 'orthographic', family: null },
  wasla:          { category: 'orthographic', family: null },
  'small-alef':   { category: 'orthographic', family: null },
  maddah:         { category: 'orthographic', family: null },
  'small-waw':    { category: 'orthographic', family: null },
  'small-ya':     { category: 'orthographic', family: null },
  'small-noon':   { category: 'orthographic', family: null },
  'sifr-mustadir':{ category: 'dabt',         family: 'sifr' },
  'sifr-mustatil':{ category: 'dabt',         family: 'sifr' },
  'meem-iqlab':   { category: 'dabt',         family: null },
  'waqf-jaiz':    { category: 'waqf',         family: 'waqf' },
  'wasl-awla':    { category: 'waqf',         family: 'waqf' },
  'waqf-awla':    { category: 'waqf',         family: 'waqf' },
  'waqf-lazim':   { category: 'waqf',         family: 'waqf' },
  muanaqah:       { category: 'waqf',         family: 'waqf' },
  pause:          { category: 'waqf',         family: 'waqf' },
  saktah:         { category: 'reading-sign', family: 'reading-sign' },
  'seen-reading': { category: 'reading-sign', family: 'reading-sign' },
  imalah:         { category: 'reading-sign', family: 'reading-sign' },
  ishmam:         { category: 'reading-sign', family: 'reading-sign' },
  tashil:         { category: 'reading-sign', family: 'reading-sign' },
  'sajdah-sign':  { category: 'standalone',   family: 'sajdah' },
  'sajdah-line':  { category: 'standalone',   family: 'sajdah' },
  hizb:           { category: 'standalone',   family: null }
});

/* The name the FILES use for harakat + tanween. Not in the registry, not in
 * FORMAT.md, but it is what is emitted — so we accept it as a family alias. */
const FAMILY_ALIASES = {
  diacritic: ['fatha', 'kasra', 'damma', 'sukun', 'shadda',
              'fathatan', 'kasratan', 'dammatan', 'maddah'],
  haraka:    ['fatha', 'kasra', 'damma', 'sukun', 'shadda'],
  vowels:    ['fatha', 'kasra', 'damma', 'fathatan', 'kasratan', 'dammatan']
};

/** Every data-mark name in a registry family or category. */
export function markNames({ family, category, name } = {}) {
  if (name) return Array.isArray(name) ? name.slice() : [name];
  if (family && FAMILY_ALIASES[family]) return FAMILY_ALIASES[family].slice();
  return Object.keys(MARK_REGISTRY).filter(n =>
    (family ? MARK_REGISTRY[n].family === family : true) &&
    (category ? MARK_REGISTRY[n].category === category : true));
}

/** Registry family of a mark name (null for the many that have none). */
export function familyOf(name) { return MARK_REGISTRY[name]?.family ?? null; }
/** Registry category of a mark name. */
export function categoryOf(name) { return MARK_REGISTRY[name]?.category ?? null; }

/* ------------------------------------------------------- Arabic text tools */

/* Harakat, tanween (incl. the open forms U+08F0-08F2 this print uses), the
 * dagger alef, the waqf/dabt block U+06D6-06ED, the Quranic annotation block,
 * and tatweel. FORMAT §9.8: the open tanween is orthography, not mojibake. */
const MARK_RE = /[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08F0-\u08F3\u0640]/g;
/* The rubʿ sign lives in the word text but never in its ink. FORMAT §9.6. */
const RUB_RE = /\u06DE/g;

/** Strip every diacritic, sign and tatweel. Leaves the letters. */
export function stripArabicMarks(s) {
  return String(s ?? '').replace(RUB_RE, '').replace(MARK_RE, '');
}

/** Fold the letter distinctions typists do not make. Nothing is folded in the
 *  stored data on purpose (FORMAT §6.1) — fold on your side. */
export function foldArabic(s) {
  return String(s ?? '')
    .replace(/[\u0623\u0625\u0622\u0671\u0672\u0673\u0675]/g, '\u0627') // أإآٱ -> ا
    .replace(/\u0649/g, '\u064A')   // ى -> ي
    .replace(/\u0629/g, '\u0647')   // ة -> ه
    .replace(/\u0624/g, '\u0648')   // ؤ -> و
    .replace(/\u0626/g, '\u064A');  // ئ -> ي
}

/** The default match key: strip, fold, collapse whitespace. */
export function normalizeQuery(s) {
  return foldArabic(stripArabicMarks(s)).replace(/\s+/g, ' ').trim();
}

/** A deliberately blunter key used only as a SECOND pass when the strict pass
 *  finds nothing: it also drops bare alef and hamza, so a typed الرحمان finds
 *  the printed الرحمن, whose alef is a dagger alef and is absent from
 *  data-search entirely. Never widens a query that already matched. */
export function looseKey(s) {
  return normalizeQuery(s).replace(/[\u0627\u0621]/g, '');
}

/* ------------------------------------------------------------- DOM plumbing */

let hiddenHost = null;
/** A hidden, rendered host. getBBox()/getCTM() need the element in a rendered
 *  document; crops and offscreen pages are parked here and removed again. */
function host() {
  if (hiddenHost && hiddenHost.isConnected) return hiddenHost;
  hiddenHost = document.createElement('div');
  hiddenHost.setAttribute('aria-hidden', 'true');
  hiddenHost.style.cssText =
    'position:absolute;left:-99999px;top:0;width:1px;height:1px;overflow:hidden';
  document.body.appendChild(hiddenHost);
  return hiddenHost;
}

/** Run fn with `el` guaranteed to be rendered, restoring it afterwards. */
export function measured(el, fn) {
  if (el.isConnected) return fn();
  const parent = el.parentNode, next = el.nextSibling;
  host().appendChild(el);
  try { return fn(); }
  finally {
    el.remove();
    if (parent) parent.insertBefore(el, next);
  }
}

function svgEl(name, attrs) {
  const e = document.createElementNS(SVGNS, name);
  for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, String(attrs[k]));
  return e;
}

let uid = 0;
const nextId = p => p + '-' + (++uid).toString(36) + Date.now().toString(36).slice(-4);

/* ------------------------------------------------------------------- Word  */

export class Word {
  constructor(el, page) { this.el = el; this._page = page; }
  get wid()   { return this.el.dataset.wid; }
  get parts() { return this.wid.split(':').map(Number); }
  get surah() { return this.parts[0]; }
  get ayah()  { return this.parts[1]; }
  get index() { return this.parts[2]; }
  get aid()   { return this.surah + ':' + this.ayah; }
  get line()  { const l = this.el.closest('g.line'); return l ? Number(l.dataset.line) : null; }
  /** All five forms. FORMAT §6.1 — every word has all of them. */
  get text() {
    const d = this.el.dataset;
    return { uthmani: d.uthmani, imlaei: d.imlaei, qpc: d.qpc, rasm: d.rasm, search: d.search };
  }
  form(which = 'uthmani') { return this.el.dataset[which]; }
  /** Bounding box in the page's own viewBox units. */
  box() { return boxInView(this._page.el, this.el); }
  paths() { return [...this.el.querySelectorAll('path')]; }
  toString() { return this.wid; }
}

export class Ayah {
  constructor(aid, fragments, page) { this.aid = aid; this.fragments = fragments; this._page = page; }
  get surah() { return Number(this.aid.split(':')[0]); }
  get number() { return Number(this.aid.split(':')[1]); }
  /** How many fragments the file says this ayah has on this page (FORMAT §7). */
  get parts() { return Number(this.fragments[0]?.dataset.ayahParts || this.fragments.length); }
  get complete() { return this.parts === this.fragments.length; }
  get markerId() { return this.fragments[0]?.dataset.marker || null; }
  get marker() { const id = this.markerId; return id ? this._page.el.querySelector('#' + CSS.escape(id)) : null; }
  get lines() { return [...new Set(this.fragments.map(f => Number(f.closest('g.line').dataset.line)))]; }
  words() { return this.fragments.flatMap(f => [...f.querySelectorAll('g.word')]).map(e => new Word(e, this._page)); }
  text(form = 'uthmani') { return this.words().map(w => w.form(form)).join(' '); }
}

export class Line {
  constructor(el, page) { this.el = el; this._page = page; }
  get number() { return Number(this.el.dataset.line); }
  words() { return [...this.el.querySelectorAll('g.word')].map(e => new Word(e, this._page)); }
  text(form = 'uthmani') { return this.words().map(w => w.form(form)).join(' '); }
  /** true for the 226 header lines that hold a banner and no words. */
  get isHeader() { return !this.el.querySelector('g.word'); }
  box() { return boxInView(this._page.el, this.el); }
}

/* ------------------------------------------------------------- geometry ---- */

/** An element's box in the root <svg>'s viewBox units.
 *  Every g.line has its own frame (FORMAT §5.2) and the page frame flips y,
 *  so a raw getBBox() is meaningless across lines — compose the CTM. */
export function boxInView(svg, el) {
  return measured(svg, () => {
    const b = el.getBBox();
    let m = null;
    /* getCTM() maps to the nearest VIEWPORT — that is CSS pixels, AFTER the
     * viewBox scaling, so it silently returns the wrong units for anything
     * you then write back into the file as a viewBox coordinate. Compose the
     * screen CTMs instead: svg.getScreenCTM() maps viewBox units to screen,
     * so its inverse takes the element's screen box back into viewBox units. */
    const s = svg.getScreenCTM(), e = el.getScreenCTM();
    if (s && e) m = s.inverse().multiply(e);
    if (!m) { try { m = el.getCTM(); } catch (_) { /* detached */ } }
    if (!m) return { x: b.x, y: b.y, w: b.width, h: b.height, x0: b.x, y0: b.y, x1: b.x + b.width, y1: b.y + b.height };
    const pt = (x, y) => {
      const p = svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(m);
    };
    const c = [pt(b.x, b.y), pt(b.x + b.width, b.y),
               pt(b.x, b.y + b.height), pt(b.x + b.width, b.y + b.height)];
    const xs = c.map(p => p.x), ys = c.map(p => p.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0, x0, y0, x1, y1 };
  });
}

function unionBox(boxes) {
  if (!boxes.length) return null;
  return boxes.reduce((a, b) => ({
    x0: Math.min(a.x0, b.x0), y0: Math.min(a.y0, b.y0),
    x1: Math.max(a.x1, b.x1), y1: Math.max(a.y1, b.y1)
  }), boxes[0]);
}
const withWH = b => b && ({ ...b, x: b.x0, y: b.y0, w: b.x1 - b.x0, h: b.y1 - b.y0 });

/* ------------------------------------------------------------- MushafPage -- */

export class MushafPage {
  /**
   * Wrap an <svg> element. Does NOT clone and does NOT mutate it — if you
   * pass a live page and then call a mutating method, your page changes.
   * Use .clone() first if that is not what you want.
   */
  constructor(el, { number = null, stripPolygons = false } = {}) {
    if (!el || el.nodeName.toLowerCase() !== 'svg') throw new TypeError('MushafPage needs an <svg> element');
    this.el = el;
    this.number = number;
    if (stripPolygons) this.dropPolygons();
  }

  /** Parse SVG source. Returns a page you own. */
  static parse(text, opts = {}) {
    const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
    if (doc.querySelector('parsererror')) throw new Error('could not parse page SVG');
    const el = document.importNode(doc.documentElement, true);
    return new MushafPage(el, { stripPolygons: true, ...opts });
  }

  /** Fetch + parse one page. `n` is 1..604. */
  static async load(n, opts = {}) { return createLoader(opts)(n); }

  /* ---- identity ---- */

  /** dev | production, by whether the ligature layer is present (FORMAT §2). */
  get profile() { return this.el.querySelector('g.ligature') ? 'dev' : 'production'; }

  /** Read off the file. Pages 1-2 do not use 0 0 345 550. */
  get viewBox() {
    const v = (this.el.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (v.length !== 4 || v.some(Number.isNaN)) throw new Error('page has no usable viewBox');
    return { x: v[0], y: v[1], w: v[2], h: v[3] };
  }

  /** The dev-only invisible ayahPolygon layer: different frame, last in
   *  document order, swallows pointer events. Removed by default on load. */
  dropPolygons() {
    const n = this.el.querySelectorAll('path.ayahPolygon');
    n.forEach(p => p.remove());
    return n.length;
  }

  /** Deep copy, with every id namespaced so two copies can share a document. */
  clone() {
    const svg = this.el.cloneNode(true);
    const tag = nextId('m') + '-';
    svg.removeAttribute('id');
    svg.querySelectorAll('[id]').forEach(e => { e.id = tag + e.id; });
    svg.querySelectorAll('g.ayah[data-marker]').forEach(g => { g.dataset.marker = tag + g.dataset.marker; });
    return new MushafPage(svg, { number: this.number });
  }

  /* ---- structure ---- */

  lineNumbers() { return this.lines().map(l => l.number); }
  lines() { return [...this.el.querySelectorAll('g.line')].map(e => new Line(e, this)); }
  line(n) { const e = this.el.querySelector(`g.line[data-line="${n}"]`); return e ? new Line(e, this) : null; }
  /** Printed lines that hold words (header lines excluded). */
  textLines() { return this.lines().filter(l => !l.isHeader); }

  get wordCount() { return this.el.querySelectorAll('g.word').length; }

  words(sel = {}) {
    let list = [...this.el.querySelectorAll('g.word')];
    if (sel.line != null) list = list.filter(w => w.closest('g.line')?.dataset.line === String(sel.line));
    if (sel.ayah) list = list.filter(w => w.closest('g.ayah')?.dataset.aid === sel.ayah);
    if (sel.surah != null) list = list.filter(w => w.dataset.wid.startsWith(sel.surah + ':'));
    if (sel.wids) { const s = new Set(sel.wids); list = list.filter(w => s.has(w.dataset.wid)); }
    return list.map(e => new Word(e, this));
  }
  word(wid) {
    const e = this.el.querySelector(`g.word[data-wid="${cssq(wid)}"]`);
    return e ? new Word(e, this) : null;
  }

  /** Ayah keys on this page, in reading order, deduplicated. */
  ayahKeys() {
    const seen = new Set(), out = [];
    for (const g of this.el.querySelectorAll('g.ayah')) {
      const a = g.dataset.aid;
      if (a && !seen.has(a)) { seen.add(a); out.push(a); }
    }
    return out;
  }
  ayahs() { return this.ayahKeys().map(a => this.ayah(a)); }
  /** The WHOLE ayah — all its fragments. Never fragment 1 of N. FORMAT §7. */
  ayah(aid) {
    const frags = [...this.el.querySelectorAll(`g.ayah[data-aid="${cssq(aid)}"]`)];
    return frags.length ? new Ayah(aid, frags, this) : null;
  }

  /* ---- metadata: the "no database" story ---- */

  /** Surah records. Banner attributes exist only on a surah's first page
   *  (FORMAT §6.6); surahs merely present on the page come back with
   *  hasBanner:false and only their number. */
  surahs() {
    const out = new Map();
    for (const g of this.el.querySelectorAll('g.surah-name, g.basmalah')) {
      const d = g.dataset, n = Number(d.sid);
      const rec = out.get(n) || { number: n, hasBanner: false, hasBasmalah: false };
      rec.arabic = d.surahNameAr; rec.latin = d.surahNameLatin; rec.english = d.surahNameEn;
      rec.revelationPlace = d.revelationPlace;
      rec.ayahCount = d.ayahCount != null ? Number(d.ayahCount) : undefined;
      if (g.classList.contains('surah-name')) rec.hasBanner = true; else rec.hasBasmalah = true;
      out.set(n, rec);
    }
    for (const w of this.el.querySelectorAll('g.word')) {
      const n = Number(w.dataset.wid.split(':')[0]);
      if (!out.has(n)) out.set(n, { number: n, hasBanner: false, hasBasmalah: false });
    }
    return [...out.values()].sort((a, b) => a.number - b.number);
  }

  /** Divisions that START on this page. All 240 rubʿ boundaries are tagged
   *  even where no rosette is drawn (FORMAT §9.6). */
  divisions() {
    const out = { juz: [], hizb: [], nisf: [], rub: [] };
    const keys = { juz: 'juzStart', hizb: 'hizbStart', nisf: 'nisfStart', rub: 'rubStart' };
    for (const k in keys) {
      const seen = new Set();
      for (const g of this.el.querySelectorAll(`g.ayah[data-${k}-start]`)) {
        const n = Number(g.dataset[keys[k]]), aid = g.dataset.aid;
        const id = n + '@' + aid;
        if (seen.has(id)) continue;      // repeated on every fragment
        seen.add(id);
        out[k].push({ n, aid, line: Number(g.closest('g.line').dataset.line) });
      }
      out[k].sort((a, b) => a.n - b.n);
    }
    return out;
  }

  /** The DRAWN hizb/rubʿ rosettes (199 corpus-wide for 240 boundaries). */
  rosettes() {
    return [...this.el.querySelectorAll('g.hizb-mark')].map(g => ({
      el: g, aid: g.dataset.aid,
      rub: Number(g.dataset.rub), rubInHizb: Number(g.dataset.rubInHizb),
      nisf: Number(g.dataset.nisf), hizb: Number(g.dataset.hizb), juz: Number(g.dataset.juz)
    }));
  }

  /** Sajdah sites, counted by the SIGN not the group: two sites in the corpus
   *  are split into two groups with unreliable data-aid (FORMAT §10.6). */
  sajdahs() {
    return [...this.el.querySelectorAll('path[data-mark="sajdah-sign"]')].map(p => {
      const g = p.closest('g.sajdah-mark');
      return { el: g || p, sign: p, aid: (g && g.dataset.aid) || p.dataset.aid || null,
               line: g ? Number(g.closest('g.line')?.dataset.line) || null : null };
    });
  }

  /** Real ayah medallions only. Pages 1-2 carry 12 decorative rosettes with
   *  no ayah, which is why this filters on [data-aid] (FORMAT §9.2). */
  markers() {
    return [...this.el.querySelectorAll('g.ayah-marker[data-aid]')].map(g => ({
      el: g, aid: g.dataset.aid, id: g.id,
      ring: g.querySelector('[data-kind="ayah-marker-ornament"]'),
      numeral: g.querySelector('[data-kind="ayah-number"]')
    }));
  }
  /** Every .ayah-marker group, decorative rosettes included. */
  allMarkerGroups() { return [...this.el.querySelectorAll('g.ayah-marker')]; }

  info() {
    const vb = this.viewBox, lines = this.lines();
    return {
      page: this.number, profile: this.profile,
      viewBox: vb, lines: lines.length,
      textLines: lines.filter(l => !l.isHeader).length,
      words: this.wordCount, ayahs: this.ayahKeys().length,
      surahs: this.surahs().map(s => s.number),
      markers: this.markers().length,
      decorativeRosettes: this.allMarkerGroups().length - this.markers().length,
      sajdahs: this.sajdahs().length, rosettes: this.rosettes().length,
      divisions: this.divisions()
    };
  }

  /* ---- targets: everything below accepts the same `target` ---- */

  /**
   * Resolve a target to Word[].
   *   'page' | '*'            every word
   *   '2:255'                 an ayah (all its fragments, all its lines)
   *   '2:255:3'               one word
   *   {line: 7} {ayah}{wids}{surah}   a selector
   *   Word | Word[] | Element | Element[]
   */
  resolve(target) {
    if (target == null || target === 'page' || target === '*') return this.words();
    if (typeof target === 'string') {
      const n = target.split(':').length;
      if (n === 3) { const w = this.word(target); return w ? [w] : []; }
      if (n === 2) { const a = this.ayah(target); return a ? a.words() : []; }
      return this.words({ surah: Number(target) });
    }
    if (Array.isArray(target)) return target.flatMap(t => this.resolve(t));
    if (target instanceof Word) return [target];
    if (target instanceof Ayah) return target.words();
    if (target instanceof Line) return target.words();
    if (target && target.nodeType === 1) {
      if (target.classList.contains('word')) return [new Word(target, this)];
      return [...target.querySelectorAll('g.word')].map(e => new Word(e, this));
    }
    if (typeof target === 'object') return this.words(target);
    return [];
  }

  /* ---- text ---- */

  /**
   * Text of any target, in any form. Line breaks are the mushaf's own.
   * FORMAT §9.4: never tokenise on whitespace — data-wid is the word key.
   */
  text(target = 'page', { form = 'uthmani', wordSep = ' ', lineSep = '\n' } = {}) {
    const words = this.resolve(target);
    let out = '', prevLine = null;
    for (const w of words) {
      const v = w.form(form);
      if (v == null) continue;
      if (out) out += (prevLine !== null && w.line !== prevLine) ? lineSep : wordSep;
      out += v;
      prevLine = w.line;
    }
    return out;
  }

  /* ---- search ---- */

  /**
   * Search this page's words.
   * Defaults to data-search, the diacritic-free form, normalised — so a plain
   * typed query works. FORMAT §6.1: never use data-rasm for a search box.
   */
  search(query, {
    form = 'search', mode = 'includes', normalize = true, loose = true, limit = Infinity
  } = {}) {
    const q0 = String(query ?? '');
    if (!q0.trim()) return [];
    const words = this.words();
    const key = normalize ? normalizeQuery : (s => String(s ?? ''));

    const run = (needle, keyFn) => {
      const out = [];
      let re = null;
      if (mode === 'regex') re = needle instanceof RegExp ? needle : new RegExp(needle, 'u');
      for (const w of words) {
        const raw = w.form(form);
        if (raw == null) continue;
        const hay = keyFn(raw);
        let hit = false, index = -1;
        if (mode === 'regex') { const m = re.exec(hay); hit = !!m; index = m ? m.index : -1; }
        else if (mode === 'exact') { hit = hay === needle; index = hit ? 0 : -1; }
        else if (mode === 'prefix') { hit = hay.startsWith(needle); index = hit ? 0 : -1; }
        else { index = hay.indexOf(needle); hit = index >= 0; }
        if (hit) { out.push({ word: w, wid: w.wid, value: raw, index }); if (out.length >= limit) break; }
      }
      return out;
    };

    let hits = run(mode === 'regex' ? q0 : key(q0), key);
    /* second pass only when the strict pass found nothing, so a query that
     * already worked is never silently widened */
    if (!hits.length && loose && mode !== 'regex' && normalize) hits = run(looseKey(q0), looseKey);
    return hits;
  }

  /* ---- highlighting ---- */

  /** Recolour a target's ink. Returns a handle that restores the exact
   *  previous inline value. Mutates THIS page. */
  highlight(target, { className = null, fill = '#c0392b', opacity = null } = {}) {
    const paths = this.resolve(target).flatMap(w => w.paths());
    const prev = paths.map(p => [p, p.style.fill, p.style.opacity]);
    for (const p of paths) {
      if (className) p.classList.add(className);
      if (fill) p.style.fill = fill;
      if (opacity != null) p.style.opacity = String(opacity);
    }
    return {
      paths, count: paths.length,
      remove() {
        for (const [p, f, o] of prev) {
          if (className) p.classList.remove(className);
          p.style.fill = f || ''; p.style.opacity = o || '';
        }
      }
    };
  }

  /**
   * The vertical band of each printed line, derived from the line PITCH — the
   * midpoints between neighbouring lines — and NOT from each line's bounding
   * box.
   *
   * This distinction is the whole reason the method exists. A line group's box
   * includes ascenders and descenders that overrun into its neighbours, so
   * bands built from it OVERLAP: two adjacent highlighted lines then paint
   * each other's edges twice and the seam reads as a dark stripe. Pitch-derived
   * bands stack flush by construction and cannot overlap. The first and last
   * lines have only one neighbour, so they are clamped to half the pitch on
   * the open side.
   *
   * Values are in viewBox units, keyed by line number. Cached; invalidated by
   * refreshGeometry().
   */
  lineBands() {
    if (this._lineBands) return this._lineBands;
    const rows = [];
    for (const l of this.lines()) {
      const words = l.words();
      if (!words.length) continue;                 // header lines have no band
      const u = unionBox(words.map(w => w.box()));
      rows.push({ line: l.number, mid: (u.y0 + u.y1) / 2, y0: u.y0, y1: u.y1 });
    }
    rows.sort((a, b) => a.mid - b.mid);
    const out = new Map();
    for (let i = 0; i < rows.length; i++) {
      const prev = rows[i - 1], next = rows[i + 1], r = rows[i];
      const halfUp = prev ? (r.mid - prev.mid) / 2 : (next ? (next.mid - r.mid) / 2 : (r.y1 - r.y0));
      const halfDown = next ? (next.mid - r.mid) / 2 : (prev ? (r.mid - prev.mid) / 2 : (r.y1 - r.y0));
      out.set(r.line, { line: r.line, y0: r.mid - halfUp, y1: r.mid + halfDown, mid: r.mid,
                        inkY0: r.y0, inkY1: r.y1 });
    }
    return (this._lineBands = out);
  }

  /**
   * The coloured stripe behind a target: ONE rect per printed line it occupies
   * — never one per word, which would show the gaps between words as notches
   * and vary in height word to word.
   *
   * Horizontal extent comes from the words' INK boxes, so a band never
   * overhangs the text at a line end. Vertical extent comes from the line
   * PITCH (see lineBands()), so bands on adjacent lines stack flush instead of
   * overlapping.
   *
   * All the rects live in ONE group carrying ONE opacity, so where two do
   * touch they stay a single flat tone, and the group is the first child of
   * <svg> with pointer-events:none — behind the ink, and unable to eat a click.
   */
  band(target, {
    padX = 1.2, padY = 0, fill = '#d6a326', opacity = 0.30, rx = 1.2,
    className = 'mushaf-band', height = 'pitch'
  } = {}) {
    const byLine = new Map();
    for (const w of this.resolve(target)) {
      const b = w.box();                            // INK box: horizontal extent
      const c = byLine.get(w.line);
      byLine.set(w.line, c ? unionBox([c, b]) : b);
    }
    const bands = height === 'pitch' ? this.lineBands() : null;
    const layer = svgEl('g', { class: className, opacity, 'pointer-events': 'none' });
    const rects = [];
    for (const [ln, b] of byLine) {
      const v = bands && bands.get(ln);
      const y0 = v ? v.y0 : b.y0 - padY;
      const y1 = v ? v.y1 : b.y1 + padY;
      rects.push({ line: ln, x0: b.x0 - padX, x1: b.x1 + padX, y0, y1 });
      layer.appendChild(svgEl('rect', {
        x: (b.x0 - padX).toFixed(3), y: y0.toFixed(3),
        width: (b.x1 - b.x0 + 2 * padX).toFixed(3),
        height: (y1 - y0).toFixed(3), rx, fill
      }));
    }
    this.el.insertBefore(layer, this.el.firstChild);
    return {
      el: layer, bands: byLine.size, boxes: rects,
      rects: [...layer.children],
      remove() { layer.remove(); }
    };
  }

  /** Band + ink highlight, the common case. */
  highlightAyah(aid, opts = {}) {
    const band = this.band(aid, opts.band || opts);
    const ink = opts.ink === false ? null : this.highlight(aid, opts.ink || { fill: null, className: 'mushaf-ayah-hl' });
    return { band, ink, bands: band.bands, remove() { band.remove(); ink && ink.remove(); } };
  }

  /** Remove every band this library drew on this page. */
  clearBands(className = 'mushaf-band') {
    const n = this.el.querySelectorAll('g.' + className);
    n.forEach(g => g.remove());
    return n.length;
  }

  /* ---- hit testing ---- */

  /**
   * Widen the tap target without changing a pixel: a transparent stroke
   * behind the fill is still hit-tested. `halo` is in page units.
   */
  enableHitTargets({ halo = 1.6 } = {}) {
    const style = svgEl('style', {});
    style.textContent =
      `g.word path{stroke:transparent;stroke-width:${halo};paint-order:stroke fill;pointer-events:all}`;
    this.el.insertBefore(style, this.el.firstChild);
    return { el: style, remove() { style.remove(); } };
  }

  /** Convert a client (screen) point into this page's viewBox units. */
  clientToView(x, y) {
    const m = this.el.getScreenCTM();
    if (!m) return null;
    const p = this.el.createSVGPoint(); p.x = x; p.y = y;
    return p.matrixTransform(m.inverse());
  }

  /**
   * Which word did the user mean?  Nearest-WITH-DIRECTION, not naive nearest.
   *
   * The point is resolved to a printed line first (by vertical band), then to
   * a word on that line. A point in the GAP between two words is awarded with
   * a bias toward the PRECEDING word, because in this print a word's trailing
   * ink — the tanween of a final ة, the small waw of a pronominal suffix —
   * is drawn into the following gap (FORMAT §9.9, §9.10). Naive nearest gets
   * those gaps wrong systematically, always in the same direction.
   *
   * @param gapBias 0..1, share of a gap awarded to the preceding word.
   */
  hitTest(x, y, { space = 'client', maxDistance = Infinity, gapBias = 0.6 } = {}) {
    let px = x, py = y;
    if (space === 'client') {
      const p = this.clientToView(x, y);
      if (!p) return null;
      px = p.x; py = p.y;
    }
    const cache = this._hitCache || (this._hitCache = new Map());
    const boxes = [];
    for (const w of this.words()) {
      let b = cache.get(w.wid);
      if (!b) { b = w.box(); cache.set(w.wid, b); }
      boxes.push({ w, b });
    }
    if (!boxes.length) return null;

    /* exact hit first */
    for (const { w, b } of boxes) {
      if (px >= b.x0 && px <= b.x1 && py >= b.y0 && py <= b.y1) return hit(w, 0, true);
    }

    /* choose the printed line by vertical distance to its band */
    const byLine = new Map();
    for (const e of boxes) {
      const k = e.w.line;
      const g = byLine.get(k) || [];
      g.push(e); byLine.set(k, g);
    }
    let best = null;
    for (const [ln, group] of byLine) {
      const u = unionBox(group.map(e => e.b));
      const dy = py < u.y0 ? u.y0 - py : py > u.y1 ? py - u.y1 : 0;
      if (!best || dy < best.dy) best = { ln, group, dy, u };
    }
    if (!best) return null;

    /* on that line, award the gap with direction.
     * Reading order is right-to-left, so the PRECEDING word is the one with
     * the larger x. Sort by descending x0 = reading order. */
    const row = best.group.slice().sort((a, b) => b.b.x1 - a.b.x1);
    let chosen = null;
    for (let i = 0; i < row.length; i++) {
      const cur = row[i], nxt = row[i + 1];
      if (px <= cur.b.x1 && px >= cur.b.x0) { chosen = cur; break; }
      if (nxt && px < cur.b.x0 && px > nxt.b.x1) {
        /* the gap between cur (preceding, to the right) and nxt (following) */
        const edge = cur.b.x0 - (cur.b.x0 - nxt.b.x1) * gapBias;
        chosen = px >= edge ? cur : nxt;
        break;
      }
    }
    if (!chosen) {
      /* outside the row entirely: nearest end */
      let d0 = Infinity;
      for (const e of row) {
        const d = gapTo(e.b);
        if (d < d0) { d0 = d; chosen = e; }
      }
    }
    /* distance is always to the CHOSEN WORD's own box, never to the line
     * band — otherwise a point a line's height away reports zero. */
    const dist = chosen ? gapTo(chosen.b) : Infinity;
    if (!chosen || dist > maxDistance) return null;
    return hit(chosen.w, dist, false);

    function gapTo(b) {
      const dx = px < b.x0 ? b.x0 - px : px > b.x1 ? px - b.x1 : 0;
      const dy = py < b.y0 ? b.y0 - py : py > b.y1 ? py - b.y1 : 0;
      return Math.hypot(dx, dy);
    }

    function hit(w, distance, exact) {
      return { word: w, wid: w.wid, aid: w.aid, line: w.line, distance, exact };
    }
  }

  /** Invalidate the cached geometry (after a layout change). */
  refreshGeometry() { this._hitCache = null; this._lineBands = null; }

  /**
   * One delegated listener that gives you the word or ayah the user MEANT,
   * including taps that land between ink.
   *
   * This is the OVERLAY-FREE path: it listens on the page's container, so it
   * keeps working whether the ink takes pointer events or the shared hit layer
   * does (overlay.mjs). If you are already using the hit layer, prefer
   * onWordClick(page, …) — same answer, one fewer listener.
   */
  onTap(handler, {
    level = 'word', event = 'click', halo = 1.6, maxDistance = 14, gapBias = 0.6, root = null
  } = {}) {
    const targets = halo ? this.enableHitTargets({ halo }) : null;
    const self = this;
    const host = root || this.el.parentElement || this.el;
    const fn = ev => {
      const direct = ev.target.closest ? ev.target.closest('g.word') : null;
      const wid = direct ? direct.dataset.wid
        : (ev.target.closest && ev.target.closest('[data-wid]')?.dataset.wid) || null;
      let res;
      if (wid && self.word(wid)) {
        const w = self.word(wid);
        res = { word: w, wid: w.wid, aid: w.aid, line: w.line, distance: 0, exact: true };
      } else {
        res = self.hitTest(ev.clientX, ev.clientY, { maxDistance, gapBias });
      }
      if (!res) return;
      if (level === 'ayah') handler({ ...res, ayah: self.ayah(res.aid) }, ev);
      else handler(res, ev);
    };
    host.addEventListener(event, fn);
    return { remove() { host.removeEventListener(event, fn); targets && targets.remove(); } };
  }

  /* ---- marks ---- */

  /**
   * Select mark paths by name, registry family or registry category.
   * Resolved to data-mark names, never to the data-mark-family attribute —
   * see DESIGN.md §6.
   */
  marks(sel = {}) {
    const names = (sel.name || sel.family || sel.category) ? markNames(sel) : null;
    let list = [...this.el.querySelectorAll('path[data-kind="mark"]')];
    if (names) { const s = new Set(names); list = list.filter(p => s.has(p.dataset.mark)); }
    if (sel.wid) list = list.filter(p => p.closest('g.word')?.dataset.wid === sel.wid);
    if (sel.ayah) list = list.filter(p => p.closest('g.ayah')?.dataset.aid === sel.ayah);
    if (sel.line != null) list = list.filter(p => p.closest('g.line')?.dataset.line === String(sel.line));
    return list;
  }

  /** Restyle marks. Handle restores the previous inline values. */
  styleMarks(sel, style = {}) {
    const paths = Array.isArray(sel) ? sel : this.marks(sel);
    const prev = paths.map(p => [p, p.getAttribute('style')]);
    for (const p of paths) for (const k in style) p.style.setProperty(k, String(style[k]));
    return {
      paths, count: paths.length,
      remove() { for (const [p, s] of prev) s == null ? p.removeAttribute('style') : p.setAttribute('style', s); }
    };
  }

  /** Hide diacritics without touching dots or waqf signs:
   *  page.hideMarks({family: 'diacritic'})  */
  hideMarks(sel) { return this.styleMarks(sel, { display: 'none' }); }

  /* ---- theme ---- */

  /**
   * Every ink path in the mushaf ships as fill="#231f20", so one rule reaches
   * all of them. `paper` becomes a background <rect> sized to the viewBox and
   * inserted first, so the theme survives cropping and raster export instead
   * of living on a container the export does not see.
   */
  theme({ paper, ink, diacritics, dots, waqf, sifr, marker, numeral, marks: byName } = {}) {
    const cls = nextId('mushaf-theme');
    this.el.classList.add(cls);
    const s = [], p = `.${cls} `;
    const nameSel = names => names.map(n => `path[data-mark="${n}"]`).join(',');
    if (ink) s.push(`${p}path{fill:${ink}}`);
    if (diacritics) s.push(names(p, markNames({ family: 'diacritic' }), diacritics));
    if (dots) s.push(names(p, markNames({ family: 'dots' }), dots));
    if (waqf) s.push(names(p, markNames({ family: 'waqf' }), waqf));
    if (sifr) s.push(names(p, markNames({ family: 'sifr' }), sifr));
    if (marker) s.push(`${p}[data-kind="ayah-marker-ornament"]{fill:${marker}}`);
    if (numeral) s.push(`${p}[data-kind="ayah-number"]{fill:${numeral}}`);
    if (byName) for (const n in byName) s.push(`${p}path[data-mark="${n}"]{fill:${byName[n]}}`);

    const style = svgEl('style', {});
    style.textContent = s.join('\n');
    this.el.insertBefore(style, this.el.firstChild);

    let rect = null;
    if (paper) {
      const vb = this.viewBox;
      rect = svgEl('rect', { x: vb.x, y: vb.y, width: vb.w, height: vb.h, fill: paper,
                             class: 'mushaf-paper', 'pointer-events': 'none' });
      this.el.insertBefore(rect, this.el.firstChild);
    }
    const el = this.el;
    return { style, rect, className: cls,
             remove() { style.remove(); rect && rect.remove(); el.classList.remove(cls); } };

    function names(prefix, list, fill) { return `${prefix}:is(${nameSel(list)}){fill:${fill}}`; }
  }

  /* ---- ayah end-markers ---- */

  /**
   * Restyle the ring and the numeral independently, scale the medallion,
   * replace the ring with a shape of your own while keeping the printed
   * numeral, or hide markers entirely.
   * Only real markers (g.ayah-marker[data-aid]) are touched — pages 1-2 carry
   * 12 decorative rosettes with no ayah.
   */
  styleMarkers({ ring, numeral, scale, hide = false, replaceRing = null } = {}) {
    const undo = [];
    for (const m of this.markers()) {
      const g = m.el, prevStyle = g.getAttribute('style');
      undo.push(() => prevStyle == null ? g.removeAttribute('style') : g.setAttribute('style', prevStyle));
      if (hide) { g.style.display = 'none'; continue; }
      if (scale != null) {
        g.style.transformBox = 'fill-box';
        g.style.transformOrigin = 'center';
        g.style.transform = `scale(${scale})`;
      }
      if (numeral && m.numeral) {
        const prev = m.numeral.getAttribute('fill');
        m.numeral.setAttribute('fill', numeral);
        undo.push(() => m.numeral.setAttribute('fill', prev));
      }
      if (!m.ring) continue;
      if (replaceRing) {
        const b = m.ring.getBBox();
        const made = typeof replaceRing === 'function'
          ? replaceRing({ x: b.x, y: b.y, w: b.width, h: b.height,
                          cx: b.x + b.width / 2, cy: b.y + b.height / 2,
                          r: Math.max(b.width, b.height) / 2 }, m)
          : circleRing(b, ring || '#b08d2e');
        if (made) {
          const old = m.ring, parent = old.parentNode, next = old.nextSibling;
          old.replaceWith(made);
          undo.push(() => { made.remove(); parent.insertBefore(old, next); });
          continue;
        }
      }
      if (ring) {
        const prev = m.ring.getAttribute('fill');
        m.ring.setAttribute('fill', ring);
        undo.push(() => m.ring.setAttribute('fill', prev));
      }
    }
    return { count: this.markers().length, remove() { undo.reverse().forEach(f => f()); } };

    function circleRing(b, colour) {
      return svgEl('circle', {
        cx: b.x + b.width / 2, cy: b.y + b.height / 2,
        r: Math.max(b.width, b.height) / 2, fill: 'none', stroke: colour,
        'stroke-width': Math.max(b.width, b.height) / 14
      });
    }
  }

  hideMarkers() { return this.styleMarkers({ hide: true }); }

  /* ---- viewBox ---- */

  /** Refit the viewBox around whatever the page now contains. */
  refit(pad = 4) {
    const svg = this.el;
    const vb = measured(svg, () => {
      const b = svg.getBBox(), r = v => Math.round(v * 1000) / 1000;
      return [r(b.x - pad), r(b.y - pad), r(b.width + 2 * pad), r(b.height + 2 * pad)].join(' ');
    });
    svg.setAttribute('viewBox', vb);
    this.refreshGeometry();
    return vb;
  }

  /* ---- crop ---- */

  /**
   * A standalone SVG around any target, usable as an image anywhere.
   * A medallion is kept only when the WHOLE ayah survived — otherwise a
   * one-word crop frames itself around a marker at the far end of the ayah.
   */
  crop(target, { pad = 4, keepMarkers = true, background = null } = {}) {
    const keep = new Set(this.resolve(target).map(w => w.wid));
    if (!keep.size) return null;
    const copy = this.clone();
    const svg = copy.el;
    svg.querySelectorAll('g.word').forEach(w => { if (!keep.has(w.dataset.wid)) w.remove(); });
    svg.querySelectorAll('g.ayah, g.line').forEach(g => { if (!g.querySelector('g.word')) g.remove(); });
    svg.querySelectorAll('g.ayah-marker').forEach(m => {
      const aid = m.dataset.aid;
      if (!keepMarkers || !aid) { m.remove(); return; }
      const sel = `g.ayah[data-aid="${cssq(aid)}"] g.word`;
      if (svg.querySelectorAll(sel).length !== this.el.querySelectorAll(sel).length) m.remove();
    });
    svg.querySelectorAll('g.surah-name, g.basmalah, g.hizb-mark, g.sajdah-mark')
       .forEach(g => { if (!g.querySelector('g.word')) g.remove(); });
    const layer = svg.querySelector('[id$="ayah_markers"]');
    if (layer && !layer.children.length) layer.remove();

    const viewBox = copy.refit(pad);
    if (background) {
      const v = copy.viewBox;
      svg.insertBefore(svgEl('rect', { x: v.x, y: v.y, width: v.w, height: v.h, fill: background }), svg.firstChild);
    }
    return {
      el: svg, page: copy, viewBox,
      words: [...svg.querySelectorAll('g.word')].map(e => e.dataset.wid),
      toString() { return new XMLSerializer().serializeToString(svg); },
      toDataUrl() {
        return 'data:image/svg+xml;charset=utf-8,' +
          encodeURIComponent(new XMLSerializer().serializeToString(svg));
      }
    };
  }
}

/* CSS attribute-selector value: the keys are [0-9:] so this is belt and
 * braces, but a caller can pass anything. */
function cssq(v) { return String(v).replace(/["\\]/g, '\\$&'); }

/* ------------------------------------------------------------------ loader */

/**
 * A page loader with its own cache. Every call hands out a CLONE, so two
 * callers can never disturb each other.
 *   const load = createLoader({baseUrl: 'pages/'});
 *   const page = await load(42);
 */
export function createLoader({
  baseUrl = 'pages/', pad = 3, ext = '.svg', fetch: f = null,
  cache = true, stripPolygons = true, name = null
} = {}) {
  const store = new Map();
  const fetcher = f || ((...a) => globalThis.fetch(...a));
  const url = n => baseUrl + (name ? name(n) : String(n).padStart(pad, '0') + ext);

  return async function load(n) {
    const key = String(n);
    if (cache && store.has(key)) return (await store.get(key)).clone();
    const p = (async () => {
      const res = await fetcher(url(n));
      if (!res.ok) throw new Error(`HTTP ${res.status} for page ${n} (${url(n)})`);
      const page = MushafPage.parse(await res.text(), { number: Number(n), stripPolygons });
      return page;
    })();
    if (cache) store.set(key, p);
    try { return (await p).clone(); }
    catch (e) { store.delete(key); throw e; }
  };
}

export const version = '0.1.0';
