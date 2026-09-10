/* ornaments.mjs — another printed mushaf's furniture on this print.
 *
 * A printed mushaf has three decorative parts around its text: the medallion
 * that closes an ayah, the banner behind a surah's name, and the border around
 * the page. In these files each of them is a named group —
 *
 *   <g class="ayah-mark" data-ayah-key="114:6">   the medallion
 *   <g class="surah-name" data-sid="112">          the printed surah name
 *   the page's own viewBox                          the text block
 *
 * — so each can be found, MEASURED, and dressed in the corresponding ornament
 * of a different mushaf entirely, while every glyph of this print stays exactly
 * where the King Fahd Complex put it.
 *
 * ─── nothing is redistributed ───────────────────────────────────────────────
 *
 * No ornament ships with this library. `loadOrnamentSet()` takes a base URL and
 * fetches `catalog.json` and each asset at runtime. The reference set is
 *
 *   https://github.com/quran-ws/quran-assets
 *
 * whose assets are traced from scans of eight printed mushafs and are
 * `CC-BY-NC-SA-4.0`, status `provisional`, `redistributable: false` while
 * written permission is sought from the publishers. Every record names its
 * source mushaf, archive.org item and PDF page; `set.licence(style)` hands the
 * terms straight through so a caller can honour them. This library states no
 * licence terms and grants none; it is the mechanism, not the material.
 *
 * ─── the rule the whole module is built on ──────────────────────────────────
 *
 * NOTHING IS PLACED AT A FIXED OFFSET. The medallion is sized from the printed
 * ring's box, the banner from the surah name's box, the border from the page's
 * own viewBox. That is why the same code lands correctly on all 604 pages of a
 * print these ornaments were never drawn for, and on pages 1-2 whose viewBox
 * and page matrix are different again. Every measurement goes through
 * `boxInView()`, which composes the screen CTMs: the page frame is
 * `matrix(1.3333 0 0 -1.3333 …)` and a ring sits under a further
 * `scale(0.011 -0.011)`, so two raw `getBBox()` results are neither in the same
 * space nor the same way up.
 *
 * Every ornament goes into ONE `<g class="mushaf-ornaments">` at the FRONT of
 * the root, so it renders behind the print — which is the whole trick with the
 * ayah numbers. They are this print's own ink and they simply stay on top of
 * whatever replaced the ring around them. This module never draws a number.
 *
 * ─── three things that are not obvious ──────────────────────────────────────
 *
 * 1. COLOUR IS AN ATTRIBUTE HERE, NOT A STYLESHEET. Everywhere else in this
 *    library and on the demo page, a CSS rule beating a presentation attribute
 *    is the answer. Not here: these designs are symmetric, they draw one
 *    quadrant and mirror it with `<use>`, and a `<use>` instance is a shadow
 *    copy that a selector does not reach. A rule recolours the original in
 *    `<defs>` and leaves the copies on screen exactly as printed — which looks
 *    like the colour control doing nothing at all. `colourOrnaments()` paints
 *    the original's `fill` (or `stroke`, for the `line` part) and every
 *    instance inherits it.
 *
 * 2. LINE ART COSTS NO SECOND FILE. Every colour asset already carries its
 *    constant-width strokes as `<g data-part="line">`, path for path what the
 *    published `line.svg` holds. `lineArt: true` drops the fill parts and keeps
 *    that group — which also gives the TILED border line art, where fetching
 *    `line.svg` would not have, since `slices/` publishes one variant only.
 *
 * 3. A BORDER SLICE CARRIES a sliver of the text-area shape its crop cut
 *    through. Whole, those slivers are the interior; tiled, they are four stubs
 *    in the corners — invisible while the slot is transparent, four coloured
 *    bars the moment anyone fills it. An assembled border keeps no `slot`.
 */

import { SVGNS, whileRendered, boxInView } from './core.mjs';

/* our name for each concept -> the catalogue's type. DESIGN §0: the medallion
   is an "ayah mark" everywhere, a surah's printed title is its "banner"
   (page.surahs().hasBanner), and the frame around the text is the "border". */
export const ORNAMENT_TYPES = Object.freeze({
  ayahMark: 'ayah-markers',
  surahBanner: 'surah-headers',
  pageBorder: 'page-frames'
});

/* one OrnamentSet per base URL, so two consumers share the fetches */
const ORNAMENT_SETS = new Map();

/* page element -> the live handle, for resetOrnaments()/hasOrnaments() */
const DRESSED = new WeakMap();

/* ------------------------------------------------------------------ fetch */

/**
 * Load an ornament set's catalogue. Fetches `catalog.json` once; the assets
 * themselves are fetched lazily, per style, on first use.
 *
 *   const set = await loadOrnamentSet('https://example.org/quran-assets/');
 *   set.styles()                 // ['douri', 'hafs-adi', …] — the mushafs
 *   await set.ornaments('qalon') // {ayahMark, surahBanner, pageBorder, licence}
 *
 * Rejects with a message naming the URL if the catalogue cannot be read — a
 * consumer that may be offline should catch it and say so, not show an empty
 * pane.
 *
 * @param baseUrl  directory holding catalog.json and assets/
 * @param fetch    an override, for tests or for a caller with its own client
 * @param cache    false to bypass the per-URL cache (a retry after a failure)
 */
export function loadOrnamentSet(baseUrl, { fetch: f = null, cache = true } = {}) {
  const base = String(baseUrl || '').replace(/\/?$/, '/');
  if (cache && ORNAMENT_SETS.has(base)) return ORNAMENT_SETS.get(base);

  const fetcher = f || ((...a) => globalThis.fetch(...a));

  const p = (async () => {
    let res;
    const url = base + 'catalog.json';
    try { res = await fetcher(url); }
    catch (e) { throw new Error(`could not reach ${url}: ${e.message}`); }
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    const catalog = await res.json();
    return new OrnamentSet(base, catalog.assets || [], fetcher);
  })();

  if (cache) {
    ORNAMENT_SETS.set(base, p);
    p.catch(() => ORNAMENT_SETS.delete(base));   // a failed load must not be cached
  }
  return p;
}

class OrnamentSet {
  constructor(base, assets, fetcher) {
    this.baseUrl = base;
    this._assets = assets;
    this._fetch = fetcher;
    this._styles = new Map();
  }

  /** The mushafs this set holds ornaments for — what a picker wants to show. */
  styles() { return [...new Set(this._assets.map(a => a.style))].sort(); }

  /** Every catalogue record, untouched. */
  list() { return this._assets.map(a => ({ ...a })); }

  /**
   * One record, by OUR name for the concept: 'ayahMark', 'surahBanner' or
   * 'pageBorder'. The catalogue's own type strings work too, so a caller
   * reading the catalogue directly is not forced to translate.
   */
  record(type, style) {
    const t = ORNAMENT_TYPES[type] || type;
    return this._assets.find(a => a.type === t && a.style === style) || null;
  }

  has(style) { return this._assets.some(a => a.style === style); }

  /**
   * The terms this style is published under, verbatim from the catalogue, or
   * null. Carried through WHOLE and unpicked: read `id`, `status` and
   * `redistributable`, and pass the rest on. Check it before you ship anything.
   */
  licence(style) {
    const rec = this._assets.find(a => a.style === style && a.license);
    return rec ? { ...rec.license } : null;
  }

  /**
   * Everything one mushaf's ornaments need, fetched and parsed on first ask,
   * then cached. A style that publishes only some of the three gets only
   * those; `dressPage` draws what it is given and reports what was missing.
   */
  ornaments(style) {
    if (this._styles.has(style)) return this._styles.get(style);
    if (!this.has(style))
      return Promise.reject(new Error(`no "${style}" in ${this.baseUrl}`));

    const p = (async () => {
      const out = { style, baseUrl: this.baseUrl, riwaya: null,
                    licence: this.licence(style), palette: [], parts: [] };
      for (const key in ORNAMENT_TYPES) {
        const rec = this.record(key, style);
        if (!rec || !rec.variants || !rec.variants.color) continue;
        out.riwaya = out.riwaya || rec.riwaya || null;
        const asset = readOrnament(await this._text(rec.variants.color), rec);
        asset.record = rec;
        out[key] = asset;
        for (const p2 of rec.palette || [])
          if (!out.palette.some(q => q.name === p2.name)) out.palette.push({ ...p2 });
        /* A BORDER IS NOT ONE FIXED SHAPE. Where it tiles, the corner and the
           two repeat units are published separately so the corner can keep its
           shape at any page aspect; where it does not, there are no slices and
           the whole drawing has to be scaled, which `dressPage` reports. */
        if (key === 'pageBorder' && rec.slices && rec.slices.files) {
          asset.slices = { corner: rec.slices.corner, repeat: rec.slices.repeat,
                           cornerMode: rec.slices.corner_mode, art: {} };
          for (const name in rec.slices.files)
            asset.slices.art[name] = readOrnament(await this._text(rec.slices.files[name]), rec);
        }
      }
      out.parts = out.palette.map(p2 => p2.name);
      if (!out.ayahMark && !out.surahBanner && !out.pageBorder)
        throw new Error(`"${style}" in ${this.baseUrl} publishes no colour variant`);
      return out;
    })();

    this._styles.set(style, p);
    p.catch(() => this._styles.delete(style));
    return p;
  }

  async _text(path) {
    const url = this.baseUrl + path;
    let res;
    try { res = await this._fetch(url); }
    catch (e) { throw new Error(`could not reach ${url}: ${e.message}`); }
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return res.text();
  }
}

/* ------------------------------------------------------ reading an asset */

let ornSeq = 0;

/**
 * Read one ornament file.
 *
 * The nodes are taken VERBATIM — the `<g data-part>` layering, the `fill-rule`
 * and the `<use>` mirrors are upstream's answer, not ours. Two things happen on
 * the way in and nothing else:
 *
 *   * `<metadata>` is dropped. It is a JSON provenance blob repeated in the
 *     catalogue, and it would be cloned once per medallion on the page.
 *   * IDS ARE RENAMED. They are FILE-local — every marker defines `<g id="q">`
 *     and mirrors it with `<use href="#q">` — so two assets in one document is
 *     a duplicate id, and every `<use>` then silently draws the FIRST one. That
 *     is one mirrored half drawn twice on the same side, with no error.
 *
 * `slot` is the transparent window the design leaves for the surah name, the
 * text area or the ayah number, in the asset's own units, or null.
 */
export function readOrnament(svgText, rec = {}) {
  const doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
  if (doc.querySelector('parsererror'))
    throw new Error(`${(rec && rec.id) || 'ornament'}: not parseable SVG`);
  const root = doc.documentElement;
  for (const m of [...root.querySelectorAll('metadata')]) m.remove();

  const tag = '-orn' + (++ornSeq).toString(36);
  for (const n of [...root.querySelectorAll('[id]')]) {
    const old = n.id;
    for (const u of [...root.querySelectorAll('use')]) {
      const href = u.getAttribute('href') || u.getAttribute('xlink:href');
      if (href === '#' + old) u.setAttribute('href', '#' + old + tag);
    }
    n.id = old + tag;
  }

  const vb = String(root.getAttribute('viewBox') || '0 0 100 100').trim().split(/\s+/).map(Number);
  const s = String(root.getAttribute('data-slot') || '').trim().split(/\s+/).map(Number);
  return {
    id: (rec && rec.id) || null,
    viewBox: root.getAttribute('viewBox'),
    vb,
    slot: s.length === 4 && s.every(n => isFinite(n))
          ? { x: s[0], y: s[1], w: s[2], h: s[3] } : null,
    /* the parsed children, cloned per placement; never mutated */
    nodes: [...root.childNodes],
    parts: [...new Set([...root.querySelectorAll('[data-part]')]
                       .map(g => g.getAttribute('data-part')))]
  };
}

/* --------------------------------------------------------------- the swap */

/**
 * Dress `page` in `ornaments`, and hand back a handle that undoes exactly it.
 *
 * The parallel to `setAyahMark()` is deliberate: same contract, three parts
 * instead of one. `remove()` puts every printed ring back, takes the layer out
 * and restores the viewBox the border grew.
 *
 * @param page         a MushafPage
 * @param ornaments    what `set.ornaments(style)` resolved to
 * @param ayahMark     draw the medallions (default true)
 * @param surahBanner  draw the banner behind each printed surah name
 * @param pageBorder   draw the border, and grow the page to fit it
 * @param gap          breathing space between the text and the border, in page units
 * @param size         factor on each medallion's fitted size; 1 matches the ring's box
 * @param lineArt      keep the constant-width strokes only, and drop the fills
 * @param colours      {part: colour} — painted on the ornaments, not the print
 * @returns {ayahMarks, surahBanners, border, repeats, stretched, missing, el, remove()}
 */
export function dressPage(page, ornaments, {
  ayahMark = true, surahBanner = true, pageBorder = true,
  gap = 5, size = 1, lineArt = false, colours = null
} = {}) {
  if (!ornaments || typeof ornaments !== 'object')
    throw new TypeError('dressPage needs an ornament set from set.ornaments(style)');

  const svg = page.el;
  const undo = [];
  const missing = [];
  const layer = ornEl('g', { class: 'mushaf-ornaments', 'data-style': ornaments.style || '' });

  /* AT THE FRONT: everything here renders behind the print, so this print's
     own ayah numerals stay on top of the ornaments that replaced their rings. */
  svg.insertBefore(layer, svg.firstChild);
  undo.push(() => layer.remove());

  const out = { ayahMarks: 0, surahBanners: 0, border: false, repeats: 0,
                stretched: false, missing, el: layer,
                style: ornaments.style || null, licence: ornaments.licence || null };

  whileRendered(svg, () => {
    if (pageBorder) {
      if (ornaments.pageBorder && ornaments.pageBorder.slot)
        ornBorder(page, layer, ornaments.pageBorder, gap, out, undo);
      else missing.push('pageBorder');
    }
    if (surahBanner) {
      if (ornaments.surahBanner && ornaments.surahBanner.slot)
        ornBanners(page, layer, ornaments.surahBanner, out);
      else missing.push('surahBanner');
    }
    if (ayahMark) {
      if (ornaments.ayahMark) ornAyahMarks(page, layer, ornaments.ayahMark, size, out, undo);
      else missing.push('ayahMark');
    }
  });

  /* LINE ART is the same drawing with the fills taken away — see the head of
     this file. One ink left means one colour to choose. */
  if (lineArt) {
    for (const g of [...layer.querySelectorAll('[data-part]')])
      if (g.getAttribute('data-part') !== 'line') g.remove();
  }

  const paint = colours ? colourOrnaments(page, colours) : null;

  const handle = {
    ...out,
    lineArt,
    remove() {
      if (paint) paint.remove();
      undo.reverse().forEach(f => f());
      undo.length = 0;
      if (DRESSED.get(svg) === handle) DRESSED.delete(svg);
    }
  };
  DRESSED.set(svg, handle);
  return handle;
}

/** Take the ornaments off, exactly restoring the page. */
export function resetOrnaments(page) {
  const h = DRESSED.get(page.el);
  if (!h) return { count: 0 };
  h.remove();
  return { count: 1 };
}

/** Is this page wearing ornaments? */
export function hasOrnaments(page) {
  return !!page.el.querySelector('g.mushaf-ornaments');
}

/**
 * Recolour what is already on the page, without rebuilding it.
 *
 * `line` is a stroke; every other part is a fill. This sets the ATTRIBUTE and
 * not a custom property or a CSS rule, because these designs mirror themselves
 * with `<use>` and a selector does not reach a shadow instance — see the head
 * of this file. Painting the original is what makes every copy follow.
 *
 * A part the chosen design does not draw is simply not there, and painting it
 * is a no-op rather than an error: `ornaments.parts` says what a picker should
 * offer.
 */
export function colourOrnaments(page, colours = {}) {
  const layer = page.el.querySelector('g.mushaf-ornaments');
  const prev = [];
  if (!layer) return { count: 0, remove() {} };
  let n = 0;
  for (const part in colours) {
    const attr = part === 'line' ? 'stroke' : 'fill';
    for (const g of layer.querySelectorAll(`[data-part="${part}"]`)) {
      prev.push([g, attr, g.getAttribute(attr)]);
      if (colours[part] == null) g.removeAttribute(attr);
      else g.setAttribute(attr, String(colours[part]));
      n++;
    }
  }
  return {
    count: n,
    remove() {
      for (const [g, attr, was] of prev)
        was == null ? g.removeAttribute(attr) : g.setAttribute(attr, was);
    }
  };
}

/* ------------------------------------------------------------- internals */

function ornEl(name, attrs) {
  const e = document.createElementNS(SVGNS, name);
  for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, String(attrs[k]));
  return e;
}

/**
 * An asset placed as a NESTED <svg>: it keeps its own viewBox and coordinate
 * system, and all it is given is a box on the page. No transform arithmetic to
 * get wrong, and no chance of inheriting the page frame's y-flip by accident.
 */
function ornPlace(asset, x, y, w, h, fit) {
  const box = ornEl('svg', { viewBox: asset.vb.join(' '), x, y, width: w, height: h,
                             preserveAspectRatio: fit || 'xMidYMid meet' });
  for (const n of asset.nodes) box.appendChild(document.importNode(n, true));
  return box;
}

/**
 * The border, at this page's aspect.
 *
 * A border publishes its TEXT AREA as `data-slot`. Map the page's text block
 * onto that slot and the band thickness follows at the source mushaf's own
 * proportions — one uniform scale, never a stretch to the page box, which is
 * what makes side borders fatter than top ones.
 *
 * THE BORDER IS DRAWN AROUND THE TEXT, so the page grows by the band it added.
 * Nothing is scaled and no word moves.
 */
function ornBorder(page, layer, border, gap, out, undo) {
  const vb = page.viewBox, slot = border.slot;
  const unit = (vb.w + 2 * gap) / slot.w;            // page units per border unit
  const boxX = vb.x - gap - slot.x * unit;
  const boxY = vb.y - gap - slot.y * unit;
  const unitW = border.vb[2];                        // border units across
  const unitH = (vb.h + 2 * gap) / unit + 2 * slot.y;// and down — this page's aspect
  const boxW = unitW * unit, boxH = unitH * unit;

  if (border.slices && border.slices.art && border.slices.art.corner) {
    const S = border.slices;
    const cw = S.corner.w, ch = S.corner.h, turn = S.cornerMode === 'rotate';
    const inner = ornEl('svg', {
      viewBox: `0 0 ${ornRound(unitW)} ${ornRound(unitH)}`,
      x: boxX, y: boxY, width: boxW, height: boxH, preserveAspectRatio: 'none' });
    const defs = ornEl('defs');
    for (const name in S.art) {
      const g = ornEl('g', { id: `mushaf-slice-${name}-${++ornSeq}` });
      for (const n of S.art[name].nodes) g.appendChild(document.importNode(n, true));
      /* the slot slivers a crop cut through — see the head of this file */
      for (const s of [...g.querySelectorAll('[data-part="slot"]')]) s.remove();
      defs.appendChild(g);
      S.art[name]._useId = g.id;
    }
    inner.appendChild(defs);
    const put = (name, t) =>
      inner.appendChild(ornEl('use', { href: '#' + S.art[name]._useId, transform: t }));

    put('corner', 'translate(0 0)');
    put('corner', turn ? `matrix(-1 0 0 -1 ${ornRound(unitW)} ${ornRound(ch)})`
                       : `translate(${ornRound(unitW)} 0) scale(-1 1)`);
    put('corner', turn ? `matrix(-1 0 0 -1 ${ornRound(cw)} ${ornRound(unitH)})`
                       : `translate(0 ${ornRound(unitH)}) scale(1 -1)`);
    put('corner', turn ? `translate(${ornRound(unitW - cw)} ${ornRound(unitH - ch)})`
                       : `matrix(-1 0 0 -1 ${ornRound(unitW)} ${ornRound(unitH)})`);

    /* A WHOLE NUMBER OF REPEATS, each nudged to fit exactly. A motif cut off
       half-drawn at the end of a run is the thing the eye catches. */
    const run = (total, u) => { const n = Math.max(1, Math.round(total / u)); return { n, step: total / n }; };
    let repeats = 4;
    if (S.art['edge-h']) {
      const across = run(unitW - 2 * cw, S.repeat.h);
      for (let i = 0; i < across.n; i++) {
        const x = cw + i * across.step, k = across.step / S.repeat.h;
        put('edge-h', `translate(${ornRound(x)} 0) scale(${ornRound(k, 6)} 1)`);
        put('edge-h', `translate(${ornRound(x)} ${ornRound(unitH)}) scale(${ornRound(k, 6)} -1)`);
      }
      repeats += across.n * 2;
    }
    if (S.art['edge-v']) {
      const down = run(unitH - 2 * ch, S.repeat.v);
      for (let i = 0; i < down.n; i++) {
        const y = ch + i * down.step, k = down.step / S.repeat.v;
        put('edge-v', `translate(0 ${ornRound(y)}) scale(1 ${ornRound(k, 6)})`);
        put('edge-v', `translate(${ornRound(unitW)} ${ornRound(y)}) scale(-1 ${ornRound(k, 6)})`);
      }
      repeats += down.n * 2;
    }
    layer.appendChild(inner);
    out.repeats = repeats;
  } else {
    /* this border does not tile: there is nothing to do but scale it whole,
       and a caller that cares should say so rather than pretend */
    layer.appendChild(ornPlace(border, boxX, boxY, boxW, boxH, 'none'));
    out.stretched = true;
  }

  const svg = page.el, was = svg.getAttribute('viewBox');
  svg.setAttribute('viewBox',
    [boxX, boxY, boxW, boxH].map(n => ornRound(n)).join(' '));
  undo.push(() => was == null ? svg.removeAttribute('viewBox') : svg.setAttribute('viewBox', was));
  out.border = true;
}

/**
 * A banner behind each printed surah name.
 *
 * `g.surah-name` exists only on a surah's FIRST page (FORMAT §6.7), so most
 * pages get none and that is not a failure. The banner spans the text column
 * and the printed name sits in the design's own `data-slot` — not in the middle
 * of the drawing, which is a different point on every design.
 *
 * The column is the union of the page's line boxes rather than any one id:
 * `page.clone()` namespaces ids, and a library that asks for `#content` breaks
 * on the copy it handed out itself.
 */
function ornBanners(page, layer, banner, out) {
  const svg = page.el;
  const names = [...svg.querySelectorAll('g.surah-name')];
  if (!names.length) return;

  const column = ornUnion(page.lines().map(l => boxInView(svg, l.el)));
  if (!column) return;
  const slot = banner.slot, vbw = banner.vb[2];
  const k = column.w / vbw;
  for (const name of names) {
    const b = boxInView(svg, name);
    layer.appendChild(ornPlace(banner, column.x,
                               b.y + b.h / 2 - (slot.y + slot.h / 2) * k,
                               vbw * k, 100 * k, 'none'));
    out.surahBanners++;
  }
}

/**
 * The medallions.
 *
 * The printed ring is HIDDEN, not removed, and the numeral is never touched.
 * Measure the ring BEFORE hiding it — `display:none` has no box.
 *
 * `display` as a presentation attribute rather than `el.style`: once Chrome's
 * inline-style object has been touched, removing the attribute still serialises
 * an empty `style=""`, and `remove()` must give the group back byte for byte.
 * This is the same lesson `setAyahMark()` learned about the duplicate rings.
 */
function ornAyahMarks(page, layer, mark, size, out, undo) {
  const svg = page.el;
  const hidden = [];
  for (const m of page.ayahMarks()) {
    if (!m.ring) continue;
    const b = boxInView(svg, m.ring);
    if (!(b.w > 0 && b.h > 0)) continue;
    for (const r of [m.ring, ...m.ringCopies]) {
      const was = r.getAttribute('display');
      r.setAttribute('display', 'none');
      hidden.push([r, was]);
    }
    /* height matches the printed ring; width follows the design's own aspect */
    const h = b.h * size, w = h * mark.vb[2] / 100;
    layer.appendChild(ornPlace(mark, b.x + b.w / 2 - w / 2, b.y + (b.h - h) / 2, w, h));
    out.ayahMarks++;
  }
  undo.push(() => {
    for (const [r, was] of hidden)
      was == null ? r.removeAttribute('display') : r.setAttribute('display', was);
  });
}

function ornUnion(boxes) {
  const bs = boxes.filter(b => b && b.w > 0 && b.h > 0);
  if (!bs.length) return null;
  const x0 = Math.min(...bs.map(b => b.x)), y0 = Math.min(...bs.map(b => b.y));
  const x1 = Math.max(...bs.map(b => b.x + b.w)), y1 = Math.max(...bs.map(b => b.y + b.h));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

const ornRound = (v, d = 4) => Number(Number(v).toFixed(d));
