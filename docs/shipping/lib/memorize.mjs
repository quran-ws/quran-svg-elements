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
 * @param target  anything MushafPage#resolve accepts: '2:255', {line: 7}, wordKeys…
 * @param mode    'hide' | 'block' | 'blur'
 * @param order   'reading' (data-word-key order) | 'reverse'
 */
export function mask(page, target = 'page', {
  mode = 'hide', color = '#d8d3c6', blur = 2.2, rx = 1.2, padX = 0.6, padY = 0.8, order = 'reading'
} = {}) {
  const words = page.resolve(target).slice().sort(byWordKey);
  if (order === 'reverse') words.reverse();

  const hidden = new Set(words.map(w => w.wordKey));
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
      if (rects.has(w.wordKey)) { rects.get(w.wordKey).style.display = ''; return; }
      const b = w.box();
      const r = document.createElementNS(SVGNS, 'rect');
      r.setAttribute('x', (b.x0 - padX).toFixed(3));
      r.setAttribute('y', (b.y0 - padY).toFixed(3));
      r.setAttribute('width', (b.x1 - b.x0 + 2 * padX).toFixed(3));
      r.setAttribute('height', (b.y1 - b.y0 + 2 * padY).toFixed(3));
      r.setAttribute('rx', String(rx));
      r.setAttribute('fill', color);
      cover.appendChild(r);
      rects.set(w.wordKey, r);
    } else {
      const r = rects.get(w.wordKey);
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
        if (!hidden.has(w.wordKey)) continue;
        hidden.delete(w.wordKey); paint(w, false); done++;
      }
      return api.revealedCount;
    },
    revealNext() { return api.reveal(1); },
    /** Hide the last n revealed words again. */
    hide(n = 1) {
      let done = 0;
      for (let i = words.length - 1; i >= 0 && done < n; i--) {
        const w = words[i];
        if (hidden.has(w.wordKey)) continue;
        hidden.add(w.wordKey); paint(w, true); done++;
      }
      return api.revealedCount;
    },
    revealWord(wordKey) {
      const w = words.find(x => x.wordKey === wordKey);
      if (w && hidden.has(wordKey)) { hidden.delete(wordKey); paint(w, false); }
      return api.revealedCount;
    },
    revealAll() { for (const w of words) if (hidden.has(w.wordKey)) { hidden.delete(w.wordKey); paint(w, false); } return words.length; },
    hideAll() { for (const w of words) if (!hidden.has(w.wordKey)) { hidden.add(w.wordKey); paint(w, true); } return 0; },
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
export function maskFrom(page, wordKey, opts = {}) {
  const all = page.words().sort(byWordKey);
  const i = all.findIndex(w => w.wordKey === wordKey);
  return mask(page, i < 0 ? [] : all.slice(i), opts);
}

/**
 * Progressive reveal: the whole page greyed, and the reading position inked.
 *
 * The CLOCK is not the library's business — a transport bar, a recitation, a
 * scroll position or a keypress all drive the same handle through goto(i).
 * What the library owns is the part that is easy to get wrong:
 *
 *   · greying every ink path at once, through one scoped rule (page.theme),
 *     rather than touching a thousand paths one at a time;
 *   · the step list in READING order, words or ayahs;
 *   · a medallion belongs to the ayah it CLOSES, so it lights when that
 *     ayah's last word is reached, not when its first is.
 *
 * @param lit      how many steps stay at full ink behind the position
 * @param byAyah   step an ayah at a time instead of a word at a time
 * @param markers  light each ayah's medallion once that ayah is finished
 */
export function reveal(page, {
  lit = 1, byAyah = false, grey = '#c9c4b8', ink = '#231f20', markers = true, at = 0
} = {}) {
  const theme = page.theme({ ink: grey });
  const steps = byAyah ? page.ayahKeys() : page.words().map(w => w.wordKey);

  const closes = new Map();
  if (markers) {
    for (const mk of page.ayahMarks()) {
      const ayah = page.ayah(mk.ayahKey);
      const last = ayah && ayah.words().pop();
      if (last) closes.set(mk.ayahKey, steps.indexOf(byAyah ? mk.ayahKey : last.wordKey));
    }
  }

  let held = [], pos = -1;
  function paint(i) {
    held.forEach(h => h.remove());
    held = [];
    pos = i;
    if (i < 0) return;
    const keys = steps.slice(Math.max(0, i - lit + 1), i + 1);
    if (keys.length) held.push(page.highlight(keys, { fill: ink }));
    for (const [ayahKey, k] of closes)
      if (k >= 0 && i >= k) held.push(inkPaths(page.ayah(ayahKey).mark, ink));
  }
  paint(Math.min(steps.length - 1, Math.max(0, at)));

  return {
    steps, closes, count: steps.length,
    get at() { return pos; },
    get key() { return steps[pos]; },
    goto(i) { paint(Math.min(steps.length - 1, Math.max(0, i))); return pos; },
    remove() { held.forEach(h => h.remove()); held = []; theme.remove(); }
  };
}

/* A medallion is NOT a word, and page.highlight() resolves an element to the
 * g.word groups inside it — of which a medallion has none, so highlighting one
 * silently paints nothing. Paint its own paths instead, with the same
 * handle shape as highlight() so the caller cannot tell them apart. */
function inkPaths(el, fill) {
  const paths = el ? [...el.querySelectorAll('path')] : [];
  const prev = paths.map(p => [p, p.style.fill]);
  for (const p of paths) p.style.fill = fill;
  return {
    paths, count: paths.length,
    remove() { for (const [p, f] of prev) p.style.fill = f || ''; }
  };
}

function byWordKey(a, b) {
  return (a.surah - b.surah) || (a.ayah - b.ayah) || (a.number - b.number);
}
