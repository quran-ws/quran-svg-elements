/* mushaf.js — memorisation masking.
 *
 * Hide or mask an arbitrary set of words and reveal them progressively.
 * Trivial with per-word groups; impossible with a page image.
 *
 * 'hide' uses visibility:hidden, so the printed page keeps its shape and its
 * spacing — the reader still sees the line, just not the words. That is the
 * whole point; display:none would not change the layout either (SVG groups do
 * not reflow) but visibility keeps the element measurable for a 'block' mask.
 */

import { SVGNS } from './core.mjs';

/**
 * @param target  anything MushafPage#resolve accepts: '2:255', {line: 7}, wids…
 * @param mode    'hide' | 'block' | 'blur'
 * @param order   'reading' (data-wid order) | 'reverse'
 */
export function mask(page, target = 'page', {
  mode = 'hide', color = '#d8d3c6', blur = 2.2, rx = 1.2, padX = 0.6, padY = 0.8, order = 'reading'
} = {}) {
  const words = page.resolve(target).slice().sort(byWid);
  if (order === 'reverse') words.reverse();

  const hidden = new Set(words.map(w => w.wid));
  const undo = [];
  let filter = null, cover = null;

  if (mode === 'blur') {
    const id = 'mushaf-mask-blur-' + Math.random().toString(36).slice(2, 8);
    filter = document.createElementNS(SVGNS, 'filter');
    filter.setAttribute('id', id);
    filter.setAttribute('x', '-20%'); filter.setAttribute('y', '-20%');
    filter.setAttribute('width', '140%'); filter.setAttribute('height', '140%');
    const fe = document.createElementNS(SVGNS, 'feGaussianBlur');
    fe.setAttribute('stdDeviation', String(blur));
    filter.appendChild(fe);
    page.el.insertBefore(filter, page.el.firstChild);
    filter.dataset.mushafFilterId = id;
  }
  if (mode === 'block') {
    cover = document.createElementNS(SVGNS, 'g');
    cover.setAttribute('class', 'mushaf-mask');
    cover.setAttribute('pointer-events', 'none');
    page.el.appendChild(cover);          // last child = painted on top
  }

  const rects = new Map();

  function paint(w, on) {
    if (mode === 'hide') { w.el.style.visibility = on ? 'hidden' : ''; return; }
    if (mode === 'blur') {
      w.el.style.filter = on ? `url(#${filter.getAttribute('id')})` : '';
      return;
    }
    /* block */
    if (on) {
      if (rects.has(w.wid)) { rects.get(w.wid).style.display = ''; return; }
      const b = w.box();
      const r = document.createElementNS(SVGNS, 'rect');
      r.setAttribute('x', (b.x0 - padX).toFixed(3));
      r.setAttribute('y', (b.y0 - padY).toFixed(3));
      r.setAttribute('width', (b.x1 - b.x0 + 2 * padX).toFixed(3));
      r.setAttribute('height', (b.y1 - b.y0 + 2 * padY).toFixed(3));
      r.setAttribute('rx', String(rx));
      r.setAttribute('fill', color);
      cover.appendChild(r);
      rects.set(w.wid, r);
    } else {
      const r = rects.get(w.wid);
      if (r) r.style.display = 'none';
    }
  }

  for (const w of words) { undo.push(w); paint(w, true); }

  const api = {
    words, mode,
    get hidden() { return [...hidden]; },
    get hiddenCount() { return hidden.size; },
    get revealedCount() { return words.length - hidden.size; },
    /** Reveal the next n words in reading order. */
    reveal(n = 1) {
      let done = 0;
      for (const w of words) {
        if (done >= n) break;
        if (!hidden.has(w.wid)) continue;
        hidden.delete(w.wid); paint(w, false); done++;
      }
      return api.revealedCount;
    },
    revealNext() { return api.reveal(1); },
    /** Hide the last n revealed words again. */
    hide(n = 1) {
      let done = 0;
      for (let i = words.length - 1; i >= 0 && done < n; i--) {
        const w = words[i];
        if (hidden.has(w.wid)) continue;
        hidden.add(w.wid); paint(w, true); done++;
      }
      return api.revealedCount;
    },
    revealWord(wid) {
      const w = words.find(x => x.wid === wid);
      if (w && hidden.has(wid)) { hidden.delete(wid); paint(w, false); }
      return api.revealedCount;
    },
    revealAll() { for (const w of words) if (hidden.has(w.wid)) { hidden.delete(w.wid); paint(w, false); } return words.length; },
    hideAll() { for (const w of words) if (!hidden.has(w.wid)) { hidden.add(w.wid); paint(w, true); } return 0; },
    remove() {
      for (const w of undo) { w.el.style.visibility = ''; w.el.style.filter = ''; }
      filter && filter.remove();
      cover && cover.remove();
      rects.clear(); hidden.clear();
    }
  };
  return api;
}

/** Mask everything from a word onward — the usual "cover the rest" drill. */
export function maskFrom(page, wid, opts = {}) {
  const all = page.words().sort(byWid);
  const i = all.findIndex(w => w.wid === wid);
  return mask(page, i < 0 ? [] : all.slice(i), opts);
}

function byWid(a, b) {
  const x = a.parts, y = b.parts;
  return (x[0] - y[0]) || (x[1] - y[1]) || (x[2] - y[2]);
}
