/* mushaf.js — swappable, recolourable ayah end-markers.
 *
 * The medallion at the end of an ayah is
 *
 *   <g class="ayah-marker" data-aid="2:256">
 *     <g transform="translate(…) scale(0.011 -0.011)">
 *       <path data-kind="ayah-marker-ornament" d="…"/>   the RING
 *     </g>
 *     … the numeral group …
 *   </g>
 *
 * This module replaces the RING with an outline from an external marker set,
 * fitted into the box the ring occupied, and leaves the NUMERAL exactly as
 * printed. The number is the print's own ink; it is never substituted with a
 * font's digits. Only the furniture around it changes.
 *
 * ─── nothing is redistributed ───────────────────────────────────────────────
 *
 * No marker outline ships with this library. `loadMarkerSet()` takes a base URL
 * and fetches `collection.json`, `annotations.json` and each marker SVG at
 * runtime. The reference set is
 *
 *   https://github.com/quranpedia/ayah-markers
 *
 * whose outlines are traced from twenty type families (Google Fonts and
 * fonts.quran.ws) and carry THOSE families' licences, which differ from one
 * another. Read `collection.json` — every marker names its `sources[]` — before
 * you redistribute anything. This library states no licence terms and grants
 * none; it is the mechanism, not the material.
 *
 * ─── the geometry is easy, and that is not an accident ──────────────────────
 *
 * The set's outlines are in the same coordinate space as ours — font units,
 * y-up, ~1000 upem (some are 2048 or 3000, so nothing here assumes a number).
 * The replacement is inserted where the ring was, so it inherits the ring's
 * parent transform, including that group's y-flip; there is no flip to undo.
 * The fit is derived from two measured bounding boxes and nothing else.
 *
 * ─── the trap, and it is real (measured 2026-08-31, 47 markers) ─────────────
 *
 * Every upstream file is ONE <path> holding every contour, and the counters —
 * the holes that make a ring a ring rather than a disc — are winding-based.
 * Splitting that path into one <path> per colourable part destroys them: a
 * naive split turned 39 of 47 markers into solid blobs, ~31% of the rendered
 * pixels wrong. It is not enough to keep document order, and it is not fixed
 * by switching fill-rule.
 *
 * The reason is that a hole and the shape it punches routinely belong to
 * DIFFERENT parts, by design — "ink-2" is a petal outline and "fill-1" is the
 * region inside it. So when a part is emitted as its own path, every contour
 * that lies inside one of its own contours and belongs to an earlier layer has
 * to be RE-INCLUDED in that path, with fill-rule="evenodd", so it punches the
 * hole again. `buildLayers()` below does that; containment is decided by
 * SVGGeometryElement.isPointInFill on a real rendered path, not by arithmetic.
 * This is the same rule the upstream customizer uses.
 *
 * MEASURED, all 47 markers, rasterised at 320px and diffed against the original
 * single path with every ink layer black and every fill layer `none`:
 *
 *   naive split, document order preserved   1,499,224 differing px
 *   this rule                                   18,582
 *   this rule, widened to any other layer       21,955
 *
 * 45 of the 47 come out at 24 differing pixels or fewer — antialiasing on the
 * seams. The two that do not:
 *   · 014-regular-bold (Noto Nastaliq Urdu) — 18,555. Its lower flourish draws
 *     solid instead of outlined, because those counters are annotated into a
 *     LATER layer, which the rule above deliberately does not reach back for.
 *     The upstream customizer renders it the same way; this is the annotation,
 *     not the port.
 *   · 021-regular — 24 px, a seam.
 * Re-run `docs/shipping/lib/test/` §M when the upstream annotations change.
 *
 * ─── how a marker is coloured ───────────────────────────────────────────────
 *
 * Seven parts, painted in this order: fill-base, fill-1, fill-2, fill-3,
 * ink-base, ink-1, ink-2. Each becomes one <path> whose fill is
 *
 *   var(--ayah-marker-<part>, <fallback>)
 *
 * so a caller recolours with CSS custom properties on any ancestor, or by
 * passing `colours` to setAyahMarker(). The `ink-*` fallback is the ring's own
 * printed fill; the `fill-*` fallback is `none`, because those layers are
 * backgrounds behind the drawing and a monochrome medallion wants them empty.
 * The upstream files hardcode fill="#0b7771" on their root <svg>; only the `d`
 * is ever read here, so that colour cannot reach the page.
 *
 * Two things the annotation file does that are worth knowing:
 *   · a contour listed in NO part is drawn as `ink-base` — 8 of the 47 markers
 *     annotate nothing at all, and 6 more leave two contours out.
 *   · a marker with no annotations borrows them from another weight of the same
 *     numeric family (003-black takes 003-thin's), which is why those 8 still
 *     colour. `annotationFor()`.
 */

import { measured } from './core.mjs';

const NS = 'http://www.w3.org/2000/svg';   /* core.mjs exports SVGNS; the flat
   global build puts every module in one scope, so the name must be local */

/** Paint order. `fill-*` are backgrounds, `ink-*` is the drawing on top. */
export const MARKER_PARTS = Object.freeze(
  ['fill-base', 'fill-1', 'fill-2', 'fill-3', 'ink-base', 'ink-1', 'ink-2']);

/** The CSS custom property a part reads. */
export const partVar = part => '--ayah-marker-' + part;

/* one MarkerSet per base URL, so two consumers share the fetches */
const SETS = new Map();

/* the original ring of every marker group we have touched */
const ORIGINALS = new WeakMap();

/* ------------------------------------------------------------------ fetch */

/**
 * Load a marker set's index. Fetches `collection.json` and `annotations.json`
 * once; the outlines themselves are fetched lazily, on first use of each.
 *
 *   const set = await loadMarkerSet('https://example.org/ayah-markers/');
 *   set.list()                       // [{id, family, weight, sources, …}, …]
 *   await set.outline('017-regular') // {viewBox, box, layers:[{part, d}], …}
 *
 * Rejects with a message naming the URL if the set cannot be read — a consumer
 * that may be offline should catch it and say so, not show an empty pane.
 *
 * @param baseUrl  directory holding collection.json, annotations.json, markers/
 * @param fetch    an override, for tests or for a caller with its own client
 * @param cache    false to bypass the per-URL cache (a retry after a failure)
 */
export function loadMarkerSet(baseUrl, { fetch: f = null, cache = true } = {}) {
  const base = String(baseUrl || '').replace(/\/?$/, '/');
  if (cache && SETS.has(base)) return SETS.get(base);

  const fetcher = f || ((...a) => globalThis.fetch(...a));
  const json = async name => {
    let res;
    try { res = await fetcher(base + name); }
    catch (e) { throw new Error(`could not reach ${base + name}: ${e.message}`); }
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${base + name}`);
    return res.json();
  };

  const p = (async () => {
    const [collection, annotations] = await Promise.all([
      json('collection.json'), json('annotations.json')]);
    const records = (collection.markers || []).map(m => {
      const family = String(m.id).split('-')[0];
      return {
        id: m.id, family, weight: String(m.id).slice(family.length + 1),
        codepoint: m.codepoint, file: m.file, width: m.width, upem: m.upem,
        sources: (m.sources || []).map(s => ({
          source: s.source, family: s.family, variant: s.variant }))
      };
    });
    return new MarkerSet(base, records, annotations, fetcher);
  })();

  if (cache) {
    SETS.set(base, p);
    p.catch(() => SETS.delete(base));   // a failed load must not be cached
  }
  return p;
}

class MarkerSet {
  constructor(base, records, annotations, fetcher) {
    this.baseUrl = base;
    this.name = null;
    this._records = records;
    this._ann = annotations && annotations.markers || {};
    this._fetch = fetcher;
    this._outlines = new Map();
    for (const r of records) r.parts = partsOf(this._ann, r.id, records);
  }

  /** Every marker in the set: id, family, weight, sources, colourable parts. */
  list() { return this._records.map(r => ({ ...r, sources: r.sources.map(s => ({ ...s })) })); }
  ids() { return this._records.map(r => r.id); }
  has(id) { return this._records.some(r => r.id === id); }
  record(id) { return this._records.find(r => r.id === id) || null; }

  /** Designs, each with its weights — what a picker wants to show. */
  families() {
    const by = new Map();
    for (const r of this._records) {
      if (!by.has(r.family)) by.set(r.family, { family: r.family, weights: [] });
      by.get(r.family).weights.push(r);
    }
    return [...by.values()].sort((a, b) => a.family.localeCompare(b.family));
  }

  /**
   * The outline, fetched and cut into layers on first ask, then cached.
   * `box` is the outline's own bounding box in its own units, measured once —
   * the fit reads it and never the viewBox, which carries padding.
   */
  outline(id) {
    if (this._outlines.has(id)) return this._outlines.get(id);
    const rec = this.record(id);
    if (!rec) return Promise.reject(new Error(`no marker "${id}" in ${this.baseUrl}`));
    const url = this.baseUrl + rec.file;
    const p = (async () => {
      let res;
      try { res = await this._fetch(url); }
      catch (e) { throw new Error(`could not reach ${url}: ${e.message}`); }
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      return cutOutline(await res.text(), annotationFor(this._ann, id, this._records), rec);
    })();
    this._outlines.set(id, p);
    p.catch(() => this._outlines.delete(id));
    return p;
  }
}

/* ------------------------------------------------------- reading a marker */

/** Contours, in document order. Every command in this set is absolute. */
export function splitContours(d) { return String(d).match(/M[^M]*/g) || []; }

/** A marker with no assignments of its own borrows another weight's. */
function annotationFor(all, id, records) {
  const has = a => a && ['parts', 'interiorFills', 'generatedFills']
    .some(k => Object.values(a[k] || {}).some(v => v.length));
  const own = all[id];
  if (has(own)) return own;
  const family = String(id).split('-')[0];
  for (const r of records)
    if (r.family === family && has(all[r.id])) return all[r.id];
  return own || { parts: {} };
}

function partsOf(all, id, records) {
  const a = annotationFor(all, id, records);
  const out = new Set();
  for (const k of ['parts', 'interiorFills', 'generatedFills'])
    for (const part in (a[k] || {})) if (a[k][part].length) out.add(part);
  return MARKER_PARTS.filter(p => out.has(p));
}

/**
 * Cut one marker file into per-part paths.
 *
 * Layer i's path holds its own contours PLUS every contour of an EARLIER layer
 * that sits inside one of them and is not itself inside another such contour —
 * re-included so `fill-rule="evenodd"` punches the counter back out. Without
 * this the medallion fills solid; see the header.
 */
export function cutOutline(svgText, annotation, rec = {}) {
  const doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
  if (doc.querySelector('parsererror')) throw new Error(`${rec.id || 'marker'}: not parseable SVG`);
  const root = doc.documentElement;
  const paths = [...root.querySelectorAll('path')];
  if (!paths.length) throw new Error(`${rec.id || 'marker'}: no <path> in the file`);

  /* id -> contour, keyed the way annotations.json keys them */
  const contours = new Map();
  paths.forEach((p, pi) => splitContours(p.getAttribute('d')).forEach(
    (c, ci) => contours.set(`path-${pi}-contour-${ci}`, c)));

  /* The upstream set is entirely absolute (M Q C L H V Z, 322 contours, zero
   * lowercase). A relative contour would be positioned against wherever the
   * previous one ended, so cutting it off would silently misplace it. Fail
   * loudly rather than draw something wrong. */
  for (const [id, c] of contours)
    if (/[a-z]/.test(c.replace(/[eE][-+]?\d/g, '')))
      throw new Error(`${rec.id || 'marker'}: ${id} uses relative path commands, ` +
        'which cannot be split off safely');

  const assigned = new Map();
  for (const part in (annotation.parts || {}))
    for (const id of annotation.parts[part]) assigned.set(id, part);

  /* One rendered path per contour, so containment is decided by the renderer.
   * They live in a detached <svg> that `measured` parks in the document. */
  const probe = document.createElementNS(NS, 'svg');
  const placed = [];
  for (const [id, d] of contours) {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', d);
    p.setAttribute('fill-rule', 'evenodd');
    probe.appendChild(p);
    placed.push({ id, d, part: assigned.get(id) || 'ink-base', el: p });
  }

  const { layers, box } = measured(probe, () => {
    for (const it of placed) it.point = interiorPoint(it.el);
    const rank = p => MARKER_PARTS.indexOf(p);
    const out = [];
    for (const part of MARKER_PARTS) {
      const own = placed.filter(x => x.part === part);
      if (!own.length) continue;
      /* Only EARLIER layers are pulled back in. Widening it to any other layer
       * was measured and is worse — 21,955 differing pixels across the 47
       * against 18,582 — so the restriction stays. */
      const inside = placed.filter(o => o.part !== part && rank(o.part) < rank(part)
        && own.some(x => x.el.isPointInFill(o.point)));
      const holes = inside.filter(o => !inside.some(q => q !== o && q.el.isPointInFill(o.point)));
      out.push({ part, d: [...own, ...holes].map(x => x.d).join(' ') });
    }
    return { layers: out, box: bboxOf(probe) };
  });

  /* Shapes the annotation SYNTHESISES rather than takes from the file — five
   * markers back `fill-base` with an ellipse that is in no contour. They are
   * drawn behind everything, and are invisible while `fill-*` defaults to
   * `none`, which is the monochrome default. */
  const generated = [];
  for (const part in (annotation.generatedFills || {}))
    for (const s of annotation.generatedFills[part]) generated.push({ part, shape: s });
  for (const part in (annotation.interiorFills || {}))
    for (const id of annotation.interiorFills[part])
      if (contours.has(id)) generated.push({ part, shape: { type: 'path', d: contours.get(id) } });

  return {
    id: rec.id || null,
    viewBox: root.getAttribute('viewBox'),
    box, layers, generated,
    parts: layers.map(l => l.part),
    contours: contours.size
  };
}

/* A point genuinely inside the contour — a bbox centre can miss a crescent. */
function interiorPoint(path) {
  const b = path.getBBox();
  for (let r = 1; r < 8; r++) for (let c = 1; c < 8; c++) {
    const p = { x: b.x + b.width * c / 8, y: b.y + b.height * r / 8 };
    if (path.isPointInFill(p)) return p;
  }
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
}

function bboxOf(el) {
  const b = el.getBBox();
  return { x: b.x, y: b.y, w: b.width, h: b.height };
}

/* ------------------------------------------------------------- the swap */

/**
 * Put `outline` in place of the printed ring on every real ayah marker.
 *
 * The numeral is not touched: the replacement is fitted into the box the ring
 * occupied, so whatever centred the number still centres it.
 *
 * DECORATIVE ROSETTES ARE LEFT ALONE. Pages 1-2 carry 12 `g.ayah-marker`
 * groups with no `data-aid` — the frame of the opening spread, closing no ayah.
 * Pass `decorative: true` to include them.
 *
 * @param page     a MushafPage
 * @param outline  what `set.outline(id)` resolved to (or the id, with `set`)
 * @param target   'page' (default), an ayah key '2:255', an Ayah, or an array
 * @param size     factor on the fitted size; 1 matches the ring's box
 * @param colours  {part: colour} — sets --ayah-marker-<part> on each medallion
 * @param ink      fallback colour for the ink-* layers (default: the ring's own)
 * @param fills    fallback colour for the fill-* layers (default 'none')
 * @returns {count, remove()} — remove() restores the printed rings exactly
 */
export function setAyahMarker(page, outline, {
  target = 'page', size = 1, colours = null, ink = null, fills = 'none',
  decorative = false
} = {}) {
  if (!outline || !Array.isArray(outline.layers))
    throw new TypeError('setAyahMarker needs an outline from set.outline(id)');

  const groups = markerGroups(page, target, decorative);
  const undo = [];

  for (const g of groups) {
    const ring = currentRing(g);
    if (!ring) continue;

    const box = measured(page.el, () => bboxOf(ring));
    if (!(box.w > 0 && box.h > 0)) continue;
    if (!ORIGINALS.has(g)) ORIGINALS.set(g, { ring, parent: ring.parentNode, next: ring.nextSibling });

    const swap = buildSwap(outline, box, size, colours, ink || ring.getAttribute('fill') || 'currentColor', fills);
    const parent = ring.parentNode, next = ring.nextSibling;
    ring.replaceWith(swap);
    undo.push(() => { swap.remove(); parent.insertBefore(ring, next); });
  }

  return {
    count: undo.length,
    marker: outline.id,
    remove() { undo.reverse().forEach(f => f()); undo.length = 0; }
  };
}

/** Put every printed ring back, exactly as it was drawn. */
export function resetAyahMarkers(page, { decorative = true } = {}) {
  let n = 0;
  for (const g of markerGroups(page, 'page', decorative)) {
    const rec = ORIGINALS.get(g);
    if (!rec) continue;
    const swap = g.querySelector('g.ayah-marker-swap');
    if (!swap) continue;
    swap.replaceWith(rec.ring);
    n++;
  }
  return { count: n };
}

/** Is this page showing a swapped marker? */
export function hasSwappedMarkers(page) {
  return !!page.el.querySelector('g.ayah-marker-swap');
}

/**
 * Recolour whatever is already on the page, without rebuilding it. Sets the
 * custom properties on the <svg>, so it reaches every medallion at once.
 */
export function colourAyahMarkers(page, colours = {}) {
  const el = page.el, prev = [];
  for (const part in colours) {
    prev.push([partVar(part), el.style.getPropertyValue(partVar(part))]);
    if (colours[part] == null) el.style.removeProperty(partVar(part));
    else el.style.setProperty(partVar(part), String(colours[part]));
  }
  return { remove() { for (const [k, v] of prev) v ? el.style.setProperty(k, v) : el.style.removeProperty(k); } };
}

/* ------------------------------------------------------------- internals */

function markerGroups(page, target, decorative) {
  const sel = decorative ? 'g.ayah-marker' : 'g.ayah-marker[data-aid]';
  if (target == null || target === 'page' || target === '*')
    return [...page.el.querySelectorAll(sel)];
  const keys = new Set((Array.isArray(target) ? target : [target]).map(
    t => typeof t === 'string' ? t : (t && t.aid) || null).filter(Boolean));
  return [...page.el.querySelectorAll(sel)].filter(g => keys.has(g.dataset.aid));
}

/* The ring, or the group that stands in its place. */
function currentRing(g) {
  return g.querySelector('[data-kind="ayah-marker-ornament"]') ||
         g.querySelector('g.ayah-marker-swap');
}

/**
 * Fit the outline's box onto the ring's box. Uniform scale — the aspect ratios
 * differ marker to marker and stretching an ornament to match is worse than
 * leaving air around it — then translate so the two centres coincide.
 */
export function fitTransform(from, to, size = 1) {
  const s = Math.min(to.w / from.w, to.h / from.h) * size;
  const cx = to.x + to.w / 2, cy = to.y + to.h / 2;
  const fx = from.x + from.w / 2, fy = from.y + from.h / 2;
  return { scale: s, tx: cx - s * fx, ty: cy - s * fy,
           toString() { return `translate(${round4(this.tx)} ${round4(this.ty)}) scale(${round4(this.scale, 6)})`; } };
}

const round4 = (v, d = 4) => Number(v.toFixed(d));

function buildSwap(outline, box, size, colours, ink, fills) {
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('class', 'ayah-marker-swap');
  g.setAttribute('data-marker', outline.id || '');
  g.setAttribute('data-kind', 'ayah-marker-ornament');
  g.setAttribute('transform', String(fitTransform(outline.box, box, size)));

  for (const gen of outline.generated) {
    const el = document.createElementNS(NS, gen.shape.type);
    for (const k in gen.shape) if (k !== 'type') el.setAttribute(k, String(gen.shape[k]));
    paint(el, gen.part);
    g.appendChild(el);
  }
  for (const layer of outline.layers) {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', layer.d);
    p.setAttribute('fill-rule', 'evenodd');   // the counters depend on it
    p.setAttribute('data-part', layer.part);
    paint(p, layer.part);
    g.appendChild(p);
  }
  return g;

  /* The colour goes in an inline STYLE, not the `fill` attribute. var() inside
   * a presentation attribute is not reliably substituted; inside a style
   * declaration it always is. */
  function paint(el, part) {
    const given = colours && colours[part];
    const fallback = given != null ? String(given) : (part.startsWith('fill') ? fills : ink);
    el.setAttribute('style', `fill:var(${partVar(part)}, ${fallback})`);
  }
}
