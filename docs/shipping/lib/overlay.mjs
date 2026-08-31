/* mushaf.js — the shared per-word hit layer.
 *
 * THE ONE OVERLAY. Selection, hover, click/tap and "which word is under this
 * point" all read from it. Building a second overlay is what breaks
 * composition: two transparent layers compete for pointer events and whichever
 * is on top wins, so turning on selection silently kills hover.
 *
 * The layer stack, and it is deliberate:
 *
 *   band / highlight layer   inside the <svg>, first child   pointer-events: none
 *   the SVG ink              the page itself                 pointer-events: none
 *   the per-word hit layer   a sibling div over the svg      THE ONLY TAKER
 *
 * One <span> per word, absolutely positioned on that word's rendered box,
 * carrying its data-wid and its real Unicode. That is simultaneously what
 * native text selection needs, what hover needs, and what a gap-aware tap
 * needs, so it is measured once and shared.
 *
 * It is REFERENCE COUNTED. attachSelection() and onWordHover() can be turned
 * on and off independently; detaching one never pulls the layer out from under
 * the other. The layer is measured in screen pixels, so it rebuilds on resize
 * — once, for every consumer.
 *
 * A caller who wants none of this can ignore the module entirely and use
 * page.hitTest(), which is pure geometry and touches no DOM.
 */

const CSS_ID = 'mushaf-overlay-css';
const OVERLAY_CSS = `
.mushaf-hitlayer{position:absolute;inset:0;z-index:2}
.mushaf-hitlayer{pointer-events:none}
.mushaf-hitlayer span{position:absolute;color:transparent;white-space:pre;cursor:text;
  pointer-events:auto;-webkit-text-fill-color:transparent}
/* Native ::selection paints each span's OWN box, so heights vary word to word
   and the gaps between them show as notches — it reads as broken. Suppress it
   and let attachSelection() draw one rect per printed line instead. */
.mushaf-hitlayer span::selection{background:transparent}
.mushaf-hitlayer span::-moz-selection{background:transparent}
.mushaf-inkoff svg{pointer-events:none}
`;

/* one record per page element */
const LAYERS = new WeakMap();

function ensureCss(doc) {
  if (doc.getElementById(CSS_ID)) return;
  const s = doc.createElement('style');
  s.id = CSS_ID;
  s.textContent = OVERLAY_CSS;
  doc.head.appendChild(s);
}

/**
 * Get the page's hit layer, building it the first time. Every caller must
 * release() exactly once; the layer is torn down when the last one does.
 *
 * @param mount  the positioned container holding the <svg>. Defaults to the
 *               svg's parent; given position:relative if it is static.
 * @param form   which text form the spans carry (what a drag copies)
 * @param pad    extra px around each word's box, for fat fingers
 */
export function acquireHitLayer(page, { mount = null, form = 'uthmani', pad = 0 } = {}) {
  const svg = page.el;
  let rec = LAYERS.get(svg);

  if (!rec) {
    const doc = svg.ownerDocument;
    const stage = mount || svg.parentElement;
    if (!stage) throw new Error('the page must be mounted before a hit layer can be built');
    ensureCss(doc);

    const prevPos = stage.style.position;
    if (getComputedStyle(stage).position === 'static') stage.style.position = 'relative';
    stage.classList.add('mushaf-inkoff');        // the ink stops taking pointer events

    const layer = doc.createElement('div');
    layer.className = 'mushaf-hitlayer';
    layer.setAttribute('dir', 'rtl');
    layer.setAttribute('aria-hidden', 'false');
    stage.appendChild(layer);

    rec = {
      page, svg, doc, stage, layer, prevPos, refs: 0, form, pad,
      byWid: new Map(), ro: null, listeners: new Set()
    };
    LAYERS.set(svg, rec);

    /* ------------------------------------------------------------------
     * TWO BOXES PER WORD, and the distinction is load-bearing. Do not
     * "simplify" it into one.
     *
     *   INK box  — the word's own getBoundingClientRect(). Used for DRAWING:
     *              a highlight band's horizontal extent comes from this, or
     *              the band overhangs the text at the ends of a line.
     *   HIT box  — the ink box grown horizontally to meet its neighbours
     *              (each gap split down the middle) and vertically to the
     *              full line band. Used for HITTING: pointer events, caret
     *              placement, native selection.
     *
     * Without the hit box the layer has DEAD ZONES: the gaps between words hit
     * nothing, so a tap between two words returns null and grabbing the first
     * or last word of an intended drag is fiddly. With it, every point on a
     * printed line belongs to exactly one word.
     *
     * The vertical extent is the line PITCH — the midpoints between adjacent
     * line centres — and NOT the line group's bounding box, which includes
     * ascenders that overrun into the neighbouring line and would make
     * adjacent hit boxes (and any band built from them) overlap.
     * ------------------------------------------------------------------ */
    rec.build = () => {
      /* a consumer that re-mounts the page (stage.replaceChildren(svg)) drops
       * the layer without releasing it — put it back rather than leaving every
       * holder pointing at a detached node */
      if (!layer.isConnected && rec.stage.isConnected) rec.stage.appendChild(layer);

      /* A rebuild replaces every span, which would silently destroy a live
       * selection — the user resizes the window and loses what they had
       * highlighted. Remember which WORDS were selected and put the selection
       * back on the new spans afterwards. */
      const keep = selectedWidsIn(rec);

      const origin = layer.getBoundingClientRect();
      layer.textContent = '';
      rec.byWid.clear();

      /* pass 1: measure the ink, grouped by printed line */
      const rows = new Map();
      for (const g of svg.querySelectorAll('g.word')) {
        const r = g.getBoundingClientRect();      // the WHOLE transform chain
        if (!r.width || !r.height) continue;
        const line = g.closest('g.line')?.dataset.line || '';
        const rec1 = {
          g, line, wid: g.dataset.wid, aid: g.closest('g.ayah')?.dataset.aid || '',
          ink: { left: r.left, top: r.top, right: r.right, bottom: r.bottom,
                 width: r.width, height: r.height }
        };
        if (!rows.has(line)) rows.set(line, []);
        rows.get(line).push(rec1);
      }

      /* pass 2: line pitch, from the ink centres of the lines that hold words */
      const centres = [...rows.entries()]
        .map(([line, ws]) => ({
          line,
          mid: (Math.min(...ws.map(w => w.ink.top)) + Math.max(...ws.map(w => w.ink.bottom))) / 2,
          top: Math.min(...ws.map(w => w.ink.top)),
          bottom: Math.max(...ws.map(w => w.ink.bottom))
        }))
        .sort((a, b) => a.mid - b.mid);
      const bandOf = new Map();
      centres.forEach((c, i) => {
        const prev = centres[i - 1], next = centres[i + 1];
        const up = prev ? (c.mid - prev.mid) / 2 : (next ? (next.mid - c.mid) / 2 : c.bottom - c.top);
        const down = next ? (next.mid - c.mid) / 2 : (prev ? (c.mid - prev.mid) / 2 : c.bottom - c.top);
        bandOf.set(c.line, { top: c.mid - up, bottom: c.mid + down });
      });

      /* pass 3: split each gap, then emit one span per word */
      for (const [line, ws] of rows) {
        /* reading order is right to left: descending x */
        ws.sort((a, b) => b.ink.right - a.ink.right);
        const gaps = [];
        for (let i = 0; i < ws.length - 1; i++) gaps.push(ws[i].ink.left - ws[i + 1].ink.right);
        const median = gaps.length
          ? gaps.slice().sort((a, b) => a - b)[gaps.length >> 1]
          : 0;
        const outer = Math.max(0, median) / 2;
        const band = bandOf.get(line) || null;

        ws.forEach((w, i) => {
          const prev = ws[i - 1], next = ws[i + 1];   // prev is to the RIGHT
          const right = prev ? (prev.ink.left + w.ink.right) / 2 : w.ink.right + outer;
          const left = next ? (w.ink.left + next.ink.right) / 2 : w.ink.left - outer;
          w.hit = {
            left, right,
            top: band ? band.top : w.ink.top,
            bottom: band ? band.bottom : w.ink.bottom
          };
        });

        for (const w of ws) {
          const s = doc.createElement('span');
          s.textContent = (w.g.dataset[rec.form] || w.g.dataset.uthmani || '') + ' ';
          s.dataset.wid = w.wid;
          s.dataset.line = w.line;
          s.dataset.aid = w.aid;
          /* the ink box travels with the span so a consumer drawing a band
             never has to re-measure — and never uses the hit box by mistake */
          s.dataset.ink = [w.ink.left - origin.left, w.ink.top - origin.top,
                           w.ink.width, w.ink.height].map(v => v.toFixed(2)).join(' ');
          s.style.left = (w.hit.left - origin.left - rec.pad) + 'px';
          s.style.top = (w.hit.top - origin.top - rec.pad) + 'px';
          s.style.width = (w.hit.right - w.hit.left + 2 * rec.pad) + 'px';
          s.style.height = (w.hit.bottom - w.hit.top + 2 * rec.pad) + 'px';
          s.style.fontSize = s.style.lineHeight = w.ink.height + 'px';
          layer.appendChild(s);
          rec.byWid.set(w.wid, s);
        }
      }
      if (keep.length) restoreSelection(rec, keep);
      for (const fn of rec.listeners) fn(rec);
      return rec.byWid.size;
    };
    rec.build();

    if (typeof ResizeObserver === 'function') {
      /* ResizeObserver fires once immediately on observe(); we have just
       * built, so skip that one rather than rebuilding twice on load. */
      let first = true;
      rec.ro = new ResizeObserver(() => { if (first) { first = false; return; } rec.build(); });
      rec.ro.observe(stage);
    }
  }

  rec.refs++;
  let released = false;

  return {
    get layer() { return rec.layer; },
    get stage() { return rec.stage; },
    get count() { return rec.byWid.size; },
    get refs() { return rec.refs; },
    get form() { return rec.form; },
    /** Change the text the spans carry (what a drag copies). Rebuilds once. */
    setForm(f) { rec.form = f; rec.build(); },
    spans() { return [...rec.layer.querySelectorAll('span')]; },
    spanOf(wid) { return rec.byWid.get(wid) || null; },
    widOf(node) {
      const el = node && (node.nodeType === 1 ? node : node.parentElement);
      return el?.closest('.mushaf-hitlayer span')?.dataset.wid || null;
    },
    rebuild() { return rec.build(); },
    /** Called after every rebuild, so a consumer can re-apply its own state. */
    onRebuild(fn) { rec.listeners.add(fn); return () => rec.listeners.delete(fn); },
    /**
     * Which word is under this client point? A span hit first — then, for a
     * point in the GAP between words, the page's own nearest-with-direction
     * geometry (page.hitTest).
     */
    wordAt(clientX, clientY, opts = {}) {
      const hit = rec.doc.elementFromPoint(clientX, clientY);
      const wid = this.widOf(hit);
      if (wid) {
        const w = page.word(wid);
        return w && { word: w, wid, aid: w.aid, line: w.line, distance: 0, exact: true };
      }
      return page.hitTest(clientX, clientY, opts);
    },
    release() {
      if (released) return;
      released = true;
      if (--rec.refs > 0) return;
      rec.ro && rec.ro.disconnect();
      rec.layer.remove();
      rec.stage.classList.remove('mushaf-inkoff');
      rec.stage.style.position = rec.prevPos;
      rec.listeners.clear();
      LAYERS.delete(svg);
    }
  };
}

/** Is a hit layer already up for this page? */
export function hasHitLayer(page) { return LAYERS.has(page.el); }

/* Which words does the current selection cover, if it is inside this layer? */
function selectedWidsIn(rec) {
  const sel = rec.doc.defaultView.getSelection();
  if (!sel || !sel.rangeCount || sel.isCollapsed) return [];
  const r = sel.getRangeAt(0);
  const out = [];
  for (const s of rec.layer.querySelectorAll('span')) if (r.intersectsNode(s)) out.push(s.dataset.wid);
  return out;
}

function restoreSelection(rec, wids) {
  const a = rec.byWid.get(wids[0]), b = rec.byWid.get(wids[wids.length - 1]);
  if (!a || !b) return;
  const r = rec.doc.createRange();
  r.setStartBefore(a);
  r.setEndAfter(b);
  const sel = rec.doc.defaultView.getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
}

/* ------------------------------------------------------------- pointer API */

function pointerBinding(page, handler, {
  event, level, layerOpts, maxDistance, gapBias, leaveHandler = null
} = {}) {
  const hl = acquireHitLayer(page, layerOpts);
  let lastWid = null;

  const fn = ev => {
    const res = hl.wordAt(ev.clientX, ev.clientY, { maxDistance, gapBias });
    if (!res) {
      if (leaveHandler && lastWid) { lastWid = null; leaveHandler(ev); }
      return;
    }
    if (event === 'pointermove') {
      if (res.wid === lastWid) return;
      lastWid = res.wid;
    }
    handler(level === 'ayah' ? { ...res, ayah: page.ayah(res.aid) } : res, ev);
  };

  /* listen on the STAGE, so both the spans and the gaps between them are
   * covered by one listener */
  hl.stage.addEventListener(event, fn);
  return {
    layer: hl,
    remove() { hl.stage.removeEventListener(event, fn); hl.release(); }
  };
}

/** Hover: fires once per word entered, with the word the pointer is over. */
export function onWordHover(page, handler, {
  level = 'word', maxDistance = 14, gapBias = 0.6, onLeave = null, ...layerOpts
} = {}) {
  return pointerBinding(page, handler, {
    event: 'pointermove', level, layerOpts, maxDistance, gapBias, leaveHandler: onLeave
  });
}

/** Click / tap: gap-aware, so a tap between two words still lands on one. */
export function onWordClick(page, handler, {
  level = 'word', event = 'click', maxDistance = 14, gapBias = 0.6, ...layerOpts
} = {}) {
  return pointerBinding(page, handler, { event, level, layerOpts, maxDistance, gapBias });
}

/**
 * A tooltip that follows the word under the pointer.
 *
 * The library owns the PLACEMENT, not the look: it makes one absolutely
 * positioned <div> in the stage, and every pixel of styling comes from the
 * className the caller passes. Placement is the part worth sharing — prefer
 * above the word, fall back to below when there is no room, and clamp to the
 * stage so a word at either margin does not push the tip off the page.
 *
 * `render(word, hit)` returns HTML, a Node, or null/false to stay hidden —
 * which is how "no entry for this word" is expressed without a second call.
 *
 * @param className    the caller's class; the library adds nothing else
 * @param visibleClass toggled on the element while the tip is showing
 * @param gap          px between the word's box and the tip
 * @param pad          px kept clear of the stage edges
 */
export function wordTooltip(page, render, {
  mount = null, className = 'mushaf-tip', visibleClass = 'on', gap = 8, pad = 4, ...hoverOpts
} = {}) {
  const svg = page.el;
  const doc = svg.ownerDocument;
  const stage = mount || svg.parentElement;
  if (!stage) throw new Error('the page must be mounted before a tooltip can be placed');

  const tip = doc.createElement('div');
  tip.className = className;
  tip.setAttribute('role', 'tooltip');
  tip.style.position = 'absolute';       /* the one rule placement depends on */
  stage.appendChild(tip);

  const hide = () => tip.classList.remove(visibleClass);

  const hover = onWordHover(page, (hit, ev) => {
    const body = render(hit.word, hit, ev);
    if (body == null || body === false) return hide();
    if (body instanceof Node) tip.replaceChildren(body);
    else tip.innerHTML = String(body);
    tip.classList.add(visibleClass);

    const host = stage.getBoundingClientRect();
    const box = (hit.span || hit.word.el).getBoundingClientRect();
    const above = box.top - host.top - tip.offsetHeight - gap;
    tip.style.top = (above > pad ? above : box.bottom - host.top + gap) + 'px';
    const x = box.left - host.left + box.width / 2 - tip.offsetWidth / 2;
    tip.style.left = Math.max(pad, Math.min(x, host.width - tip.offsetWidth - pad)) + 'px';
  }, { mount: stage, ...hoverOpts, onLeave: hide });

  return { el: tip, hide, remove() { hover.remove(); tip.remove(); } };
}

/** One-shot query without keeping a binding alive. */
export function wordAt(page, clientX, clientY, opts = {}) {
  const hl = acquireHitLayer(page, opts);
  try { return hl.wordAt(clientX, clientY, opts); } finally { hl.release(); }
}
