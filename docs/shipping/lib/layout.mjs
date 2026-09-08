/* mushaf.js — layout: leading, and filling a viewport with it. */

/**
 * Move the printed lines apart without touching a glyph, and grow the viewBox
 * so nothing is cropped.
 *
 * Every printed line is its own group, so this scales and re-sets nothing.
 * The page frame flips y (FORMAT §5.1), so a positive translate moves UP.
 * Medallions live in their own layer outside the lines and must be carried
 * along; each closes an ayah, so it belongs with that ayah's LAST fragment.
 *
 * Mutates the page you hand it. Handle restores the previous transforms and
 * viewBox exactly.
 */
export function setLineGap(page, gap, { pad = 6, carryMarks = true } = {}) {
  const svg = page.el;
  const lines = [...svg.querySelectorAll('g.line')];
  if (lines.length < 2) return { gap: 0, viewBox: svg.getAttribute('viewBox'), remove() {} };

  const prevVb = svg.getAttribute('viewBox');
  const undo = [];
  const remember = el => {
    const t = el.getAttribute('transform');
    undo.push(() => t == null ? el.removeAttribute('transform') : el.setAttribute('transform', t));
  };

  const mid = (lines.length - 1) / 2;
  const shift = new Map();
  lines.forEach((line, i) => {
    const dy = (mid - i) * gap;
    shift.set(line.dataset.line, dy);
    remember(line);
    line.setAttribute('transform', `translate(0 ${dy.toFixed(3)})`);
  });

  if (carryMarks) {
    for (const m of page.ayahMarks()) {
      const parts = svg.querySelectorAll(`g.ayah-fragment[data-ayah-key="${m.ayahKey}"]`);
      const last = parts[parts.length - 1];
      if (!last) continue;
      const dy = shift.get(last.closest('g.line').dataset.line) || 0;
      remember(m.el);
      m.el.setAttribute('transform', `translate(0 ${dy.toFixed(3)})`);
    }
  }

  const viewBox = page.refit(pad);
  return {
    gap, viewBox, lines: lines.length,
    remove() {
      undo.forEach(f => f());
      if (prevVb == null) svg.removeAttribute('viewBox'); else svg.setAttribute('viewBox', prevVb);
      page.refreshGeometry();
    }
  };
}

/**
 * PURE ARITHMETIC, no DOM. The leading that makes the page fill a viewport.
 *
 *   needed = pageW * viewH / viewW      the viewBox height that fills it
 *   gap    = (needed - pageH) / (lines - 1)
 *
 * Clamped at 0: a viewport that is already wider-for-its-height than the page
 * (iPad portrait) needs no leading, and a negative one would overlap lines.
 *
 * Measured for the 345x550 / 15-line pages:
 *   iPhone SE 375x667 -> 4.5   iPhone 14 390x844 -> 14.0
 *   Pixel 7 412x915   -> 15.4  Galaxy S21 360x800 -> 15.5
 *   iPad 10.9 820x1180 -> 0 (fits by height already)
 */
export function gapToFill({ pageW, pageH, lines, viewW, viewH, max = Infinity }) {
  if (!(viewW > 0) || !(viewH > 0) || !(lines > 1) || !(pageW > 0)) return 0;
  const needed = pageW * viewH / viewW;
  const gap = (needed - pageH) / (lines - 1);
  if (!(gap > 0)) return 0;
  return Math.min(gap, max);
}

/** How much of the viewport a page wastes when fitted to width, 0..1. */
export function wastedFraction({ pageW, pageH, viewW, viewH }) {
  if (!(viewW > 0) || !(viewH > 0)) return 0;
  const drawnH = viewW * pageH / pageW;
  return Math.max(0, 1 - drawnH / viewH);
}

/**
 * Measure, solve, apply. The line count and the viewBox come off the FILE, so
 * this is correct on pages 1-2 (8 lines, their own viewBox) too.
 *
 * `observe: true` keeps the page filling through a rotation with a
 * ResizeObserver — opt-in, and torn down by remove(). No silent global
 * listeners.
 */
export function fitToViewport(page, {
  width, height, element = null, maxGap = Infinity, pad = 6, carryMarks = true, observe = false
} = {}) {
  let applied = null, ro = null;

  const measure = () => {
    if (element) { const r = element.getBoundingClientRect(); return { w: r.width, h: r.height }; }
    if (width != null && height != null) return { w: width, h: height };
    return { w: globalThis.innerWidth, h: globalThis.innerHeight };
  };

  const apply = () => {
    if (applied) { applied.remove(); applied = null; }
    /* the ORIGINAL box, after any previous gap has been undone */
    const vb = page.viewBox;
    const lines = page.el.querySelectorAll('g.line').length;
    const v = measure();
    const gap = gapToFill({ pageW: vb.w, pageH: vb.h, lines, viewW: v.w, viewH: v.h, max: maxGap });
    const waste = wastedFraction({ pageW: vb.w, pageH: vb.h, viewW: v.w, viewH: v.h });
    if (gap <= 0) return { gap: 0, lines, viewport: v, wasted: waste, viewBox: page.el.getAttribute('viewBox') };
    applied = setLineGap(page, gap, { pad, carryMarks });
    return { gap, lines, viewport: v, wasted: waste, viewBox: applied.viewBox };
  };

  let state = apply();

  if (observe && element && typeof ResizeObserver === 'function') {
    ro = new ResizeObserver(() => { state = apply(); });
    ro.observe(element);
  }

  return {
    get gap() { return state.gap; },
    get state() { return state; },
    update() { state = apply(); return state; },
    remove() { ro && ro.disconnect(); applied && applied.remove(); applied = null; }
  };
}
