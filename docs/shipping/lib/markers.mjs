/* markers.mjs — swappable, recolourable ayah end-marks.
 *
 * The medallion at the end of an ayah is
 *
 *   <g class="ayah-mark" data-ayah-key="2:256">
 *     <g transform="translate(…) scale(0.011 -0.011)">
 *       <path data-kind="ayah_mark_ornament" d="…"/>   the RING
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
 * No marker outline ships with this library. `loadMarkSet()` takes a base URL
 * and fetches `collection.json` and each marker SVG at runtime. The reference
 * set is
 *
 *   https://github.com/quranpedia/ayah-marks
 *
 * whose outlines are traced from twenty type families and carry THOSE families'
 * licences, which differ from one another. Read `collection.json` — every
 * marker names its `sources[]` — before you redistribute anything. This library
 * states no licence terms and grants none; it is the mechanism, not the
 * material.
 *
 * ─── what this module used to do, and no longer has to ──────────────────────
 *
 * Upstream once shipped each marker as ONE <path> holding every contour, with a
 * separate annotations.json saying which contour belonged to which colourable
 * part. Cutting that up here was the hard part of this file: the counters — the
 * holes that make a ring a ring — are winding-based, and a hole and the shape
 * it punches routinely belong to different parts, so every layer had to
 * re-include the earlier-layer contours lying inside it and draw `evenodd`.
 * Upstream now ships the markers already layered — one <g data-part> per part,
 * fill-rule and re-inclusion applied — so that whole apparatus is gone and the
 * groups are taken verbatim. If a marker draws solid, it draws solid upstream.
 *
 * ─── how a marker is coloured ───────────────────────────────────────────────
 *
 * Colour is upstream's contract, not ours. Each group carries
 *
 *   style="fill:var(--fill-base,#fff8e7)"
 *
 * so setting `--fill-base`, `--fill-1`, `--fill-2`, `--fill-3`, `--ink-base`,
 * `--ink-1` or `--ink-2` on ANY ancestor recolours the drawing with no
 * JavaScript at all. `colourAyahMarks()` is a convenience over
 * `element.style.setProperty`, nothing more. Each design uses only some of the
 * parts; `outline.parts` lists the ones it actually draws.
 */

import { whileRendered } from './core.mjs';

const NS = 'http://www.w3.org/2000/svg';   /* core.mjs exports SVGNS; the flat
   global build puts every module in one scope, so the name must be local */

/* one MarkSet per base URL, so two consumers share the fetches */
const SETS = new Map();

/* the original ring of every marker group we have touched */
const ORIGINALS = new WeakMap();

/* ------------------------------------------------------------------ fetch */

/**
 * Load a marker set's index. Fetches `collection.json` once; the outlines
 * themselves are fetched lazily, on first use of each.
 *
 *   const set = await loadMarkSet('https://example.org/ayah-marks/');
 *   set.list()                       // [{id, family, weight, sources, …}, …]
 *   await set.outline('017-regular') // {viewBox, box, parts, number, …}
 *
 * Rejects with a message naming the URL if the set cannot be read — a consumer
 * that may be offline should catch it and say so, not show an empty pane.
 *
 * @param baseUrl  directory holding collection.json and markers/
 * @param fetch    an override, for tests or for a caller with its own client
 * @param cache    false to bypass the per-URL cache (a retry after a failure)
 */
export function loadMarkSet(baseUrl, { fetch: f = null, cache = true } = {}) {
  const base = String(baseUrl || '').replace(/\/?$/, '/');
  if (cache && SETS.has(base)) return SETS.get(base);

  const fetcher = f || ((...a) => globalThis.fetch(...a));

  const p = (async () => {
    let res;
    const url = base + 'collection.json';
    try { res = await fetcher(url); }
    catch (e) { throw new Error(`could not reach ${url}: ${e.message}`); }
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    const collection = await res.json();
    const records = (collection.markers || []).map(m => {
      const family = String(m.id).split('-')[0];
      return {
        id: m.id, family, weight: String(m.id).slice(family.length + 1),
        codepoint: m.codepoint, file: m.file, width: m.width, upem: m.upem,
        // Where the ayah number goes, in the outline's own coordinates: ONE
        // centre, {cx, cy}, with {width, height, r} describing the room it has.
        // U+06DD is a prefixed format control — it is defined to ENCLOSE the
        // digits after it — so a font that implements it has already answered
        // this, and upstream publishes the answer rather than a provenance
        // story about it. Carried through WHOLE and unpicked: upstream is still
        // moving, so read what you need and ignore the rest. Absent on sets
        // published before this field existed; a consumer must cope with that.
        number: m.number,
        sources: (m.sources || []).map(s => ({
          source: s.source, family: s.family, variant: s.variant,
          // The source font's own terms. Carried through so a consumer can
          // honour them; the sets we do not redistribute say so themselves.
          license: s.license }))
      };
    });
    return new MarkSet(base, records, fetcher);
  })();

  if (cache) {
    SETS.set(base, p);
    p.catch(() => SETS.delete(base));   // a failed load must not be cached
  }
  return p;
}

class MarkSet {
  constructor(base, records, fetcher) {
    this.baseUrl = base;
    this.name = null;
    this._records = records;
    this._fetch = fetcher;
    this._outlines = new Map();
  }

  /** Every marker in the set: id, family, weight, sources, number. */
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
   * The outline, fetched and parsed on first ask, then cached.
   * `box` is the drawing's own bounding box in its own units, measured once —
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
      return readOutline(await res.text(), rec);
    })();
    this._outlines.set(id, p);
    p.catch(() => this._outlines.delete(id));
    return p;
  }
}

/* ------------------------------------------------------- reading a marker */

/**
 * Read one already-layered marker file.
 *
 * The `<g data-part="…">` groups are taken VERBATIM — their `fill-rule`, their
 * `var(--part, default)` style and the contours inside them are upstream's
 * answer, not ours. All this does is measure the box and remember the groups.
 */
export function readOutline(svgText, rec = {}) {
  const doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
  if (doc.querySelector('parsererror')) throw new Error(`${rec.id || 'marker'}: not parseable SVG`);
  const root = doc.documentElement;
  const groups = [...root.querySelectorAll('g[data-part]')];
  if (!groups.length) throw new Error(`${rec.id || 'marker'}: no <g data-part> in the file`);

  /* Measure the drawing in a probe that `measured` parks in the document —
     getBBox() is meaningless on a detached, unrendered tree. */
  const probe = document.createElementNS(NS, 'svg');
  for (const g of groups) probe.appendChild(document.importNode(g, true));
  const box = whileRendered(probe, () => {
    const b = probe.getBBox();
    return { x: b.x, y: b.y, w: b.width, h: b.height };
  });

  return {
    id: rec.id || null,
    viewBox: root.getAttribute('viewBox'),
    box,
    // the parsed groups, cloned per swap; never mutated
    groups,
    parts: groups.map(g => g.getAttribute('data-part')),
    // Where this design wants the ayah number, in the outline's own
    // coordinates — one centre, {cx, cy}, verbatim from collection.json.
    number: rec.number || null
  };
}

/**
 * The centre this design wants the ayah number on, or null.
 *
 * `cx`/`cy` are the whole contract. Whatever else the record carries — the
 * room the number has (`width`, `height`, `r`), or fields published after this
 * was written — is passed through untouched on `outline.number` and ignored
 * here. A consumer that breaks when a publisher trims a field is a consumer
 * nobody can rely on.
 *
 * NO record at all is fine, and means "box-centre me". A record that is there
 * but carries no usable `cx`/`cy` is broken, and throws rather than silently
 * hanging the design off the wrong point.
 */
export function numberCentre(outline) {
  const n = outline && outline.number;
  if (n == null) return null;          // published no centre — box-centre it
  if (!isFinite(n.cx) || !isFinite(n.cy))
    throw new Error(`${(outline && outline.id) || 'marker'}: number record has ` +
      'no usable cx/cy');              // present but malformed — say so
  return { cx: n.cx, cy: n.cy };
}

/**
 * The printed numeral's centre, expressed in `host`'s coordinate system.
 *
 * THE TWO ARE NOT IN THE SAME SPACE, and this is the whole difficulty. A
 * marker group holds two children with different transforms:
 *
 *   <g transform="translate(…) scale(0.011 -0.011)">  the ring — FONT units
 *   <g transform="translate(…)">                      the numeral — PAGE units
 *
 * so `ring.getBBox()` counts in thousands while `num.getBBox()` counts in tens,
 * and comparing them directly puts the replacement a long way from the number.
 * Go through the screen CTMs, which compose every transform above each element
 * — including the y-flip — and land the point in the space the swap's own
 * transform is written in.
 */
function numeralCentreIn(group, host) {
  const num = group.querySelector('[data-kind="ayah_number"]');
  if (!num || !host || !num.getScreenCTM || !host.getScreenCTM) return null;
  const b = num.getBBox();
  if (!(b.width > 0 && b.height > 0)) return null;
  const hostCTM = host.getScreenCTM(), numCTM = num.getScreenCTM();
  if (!hostCTM || !numCTM) return null;
  const svg = num.ownerSVGElement;
  const pt = svg.createSVGPoint();
  pt.x = b.x + b.width / 2;
  pt.y = b.y + b.height / 2;
  return pt.matrixTransform(hostCTM.inverse().multiply(numCTM));
}

/* ------------------------------------------------------------- the swap */

/**
 * Put `outline` in place of the printed ring on every real ayah marker.
 *
 * The numeral is not touched: the replacement is positioned so that the
 * design's OWN number-centre lands on the printed numeral, and scaled from the
 * box the ring occupied.
 *
 * Only `g.ayah-mark[data-ayah-key]` groups are touched. Since 2026-09-04 that is
 * every marker; page files built before it carried 12 id-less groups on pages
 * 1-2 ("decorative rosettes" — in fact the artwork's doubled rings), and
 * `decorative: true` includes those. On current pages the doubled ring sits
 * INSIDE the marker group as `[data-duplicate]` and is hidden with the ring.
 *
 * @param page     a MushafPage
 * @param outline  what `set.outline(id)` resolved to
 * @param target   'page' (default), an ayah key '2:255', an Ayah, or an array
 * @param size     factor on the fitted size; 1 matches the ring's box
 * @param colours  {part: colour} — sets upstream's --<part> variables on the page
 * @returns {count, remove()} — remove() restores the printed rings exactly
 */
export function setAyahMark(page, outline, {
  target = 'page', size = 1, colours = null,
  decorative = false, anchorOnNumber = true
} = {}) {
  if (!outline || !Array.isArray(outline.groups))
    throw new TypeError('setAyahMark needs an outline from set.outline(id)');

  const groups = markGroups(page, target, decorative);
  const undo = [];
  let swapped = 0;

  for (const g of groups) {
    const ring = currentRing(g);
    if (!ring) continue;

    const box = whileRendered(page.el, () => bboxOf(ring));
    if (!(box.w > 0 && box.h > 0)) continue;
    if (!ORIGINALS.has(g)) ORIGINALS.set(g, { ring, parent: ring.parentNode, next: ring.nextSibling });

    // MOVE THE MARKER, NEVER THE NUMBER.
    //
    // The numeral is the print's own ink and stays exactly where the King Fahd
    // Complex put it. What moves is the furniture around it: each design records
    // where IT expects the number to sit, so the replacement is positioned so
    // that its own number-centre lands on the printed numeral.
    //
    // Centring the outline's bounding box on the ring's would be wrong the
    // moment a design is not symmetric — a disc with a pendant flourish has its
    // box centre on the join, and box-centring would hang the disc above the
    // number instead of around it.
    const anchor = anchorOnNumber
      ? whileRendered(page.el, () => numeralCentreIn(g, ring.parentNode))
      : null;

    const swap = buildSwap(outline, box, size, anchor);
    const parent = ring.parentNode, next = ring.nextSibling;
    ring.replaceWith(swap);
    undo.push(() => { swap.remove(); parent.insertBefore(ring, next); });
    swapped++;
    // pages 1-2: the artwork's second copy of the ring (FORMAT §9.2) would
    // show through the replacement — hide it with the ring it duplicates.
    // The presentation attribute, not el.style: once Chrome's inline-style
    // object has been touched, removing the attribute still serialises an
    // empty style="", and remove() must give the group back byte for byte.
    for (const c of g.querySelectorAll('[data-kind="ayah_mark_ornament"][data-duplicate]')) {
      const prev = c.getAttribute('display');
      c.setAttribute('display', 'none');
      undo.push(() => prev == null ? c.removeAttribute('display') : c.setAttribute('display', prev));
    }
  }

  const paint = colours ? colourAyahMarks(page, colours) : null;

  return {
    count: swapped,
    marker: outline.id,
    remove() {
      undo.reverse().forEach(f => f());
      undo.length = 0;
      if (paint) paint.remove();
    }
  };
}

/** Put every printed ring back, exactly as it was drawn. */
export function resetAyahMarks(page, { decorative = true } = {}) {
  let n = 0;
  for (const g of markGroups(page, 'page', decorative)) {
    const rec = ORIGINALS.get(g);
    if (!rec) continue;
    const swap = g.querySelector('g.ayah-mark-swap');
    if (!swap) continue;
    swap.replaceWith(rec.ring);
    n++;
  }
  return { count: n };
}

/** Is this page showing a swapped marker? */
export function hasSwappedMarks(page) {
  return !!page.el.querySelector('g.ayah-mark-swap');
}

/**
 * Recolour whatever is already on the page, without rebuilding it.
 *
 * These are UPSTREAM's variable names — `--fill-base`, `--fill-1`, `--fill-2`,
 * `--fill-3`, `--ink-base`, `--ink-1`, `--ink-2` — set here on the <svg> so
 * they reach every medallion at once. A stylesheet setting them on any ancestor
 * does exactly the same thing with no JavaScript.
 */
export function colourAyahMarks(page, colours = {}) {
  const el = page.el, prev = [];
  for (const part in colours) {
    const name = '--' + part;
    prev.push([name, el.style.getPropertyValue(name)]);
    if (colours[part] == null) el.style.removeProperty(name);
    else el.style.setProperty(name, String(colours[part]));
  }
  return { remove() { for (const [k, v] of prev) v ? el.style.setProperty(k, v) : el.style.removeProperty(k); } };
}

/* ------------------------------------------------------------- internals */

function markGroups(page, target, decorative) {
  const sel = decorative ? 'g.ayah-mark' : 'g.ayah-mark[data-ayah-key]';
  if (target == null || target === 'page' || target === '*')
    return [...page.el.querySelectorAll(sel)];
  const keys = new Set((Array.isArray(target) ? target : [target]).map(
    t => typeof t === 'string' ? t : (t && t.ayahKey) || null).filter(Boolean));
  return [...page.el.querySelectorAll(sel)].filter(g => keys.has(g.dataset.ayahKey));
}

/* The ring, or the group that stands in its place. */
function currentRing(g) {
  return g.querySelector('[data-kind="ayah_mark_ornament"]:not([data-duplicate])') ||
         g.querySelector('g.ayah-mark-swap');
}

function bboxOf(el) {
  const b = el.getBBox();
  return { x: b.x, y: b.y, w: b.width, h: b.height };
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

function buildSwap(outline, box, size, anchor = null) {
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('class', 'ayah-mark-swap');
  g.setAttribute('data-mark', outline.id || '');
  g.setAttribute('data-kind', 'ayah_mark_ornament');

  // Scale comes from the ring's box either way — the replacement should read
  // at the size the printed medallion did. Only the POSITION differs: with an
  // anchor, the design's own number-centre is put on the printed numeral;
  // without one, the two bounding boxes are centred on each other.
  const fit = fitTransform(outline.box, box, size);
  const nc = numberCentre(outline);
  if (anchor && nc) {
    fit.tx = anchor.x - fit.scale * nc.cx;
    fit.ty = anchor.y - fit.scale * nc.cy;
    g.setAttribute('data-anchored', 'numeral');   // a flag, not a provenance
  }
  g.setAttribute('transform', String(fit));

  /* Upstream's groups, verbatim — fill-rule, style and all. */
  for (const src of outline.groups) g.appendChild(document.importNode(src, true));
  return g;
}
