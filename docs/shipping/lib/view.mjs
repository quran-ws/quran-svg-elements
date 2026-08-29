/* mushaf.js — bring a word or an ayah into view.
 *
 * The only reason this is a function and not a one-liner is the coordinate
 * work: a word's box lives in its LINE's frame under a y-flipping page matrix,
 * so scrolling to getBBox().y sends you to the wrong end of the page.
 */

/**
 * @param target    anything MushafPage#resolve accepts
 * @param container the scrolling element; defaults to the page's scroll parent
 * @param block     'center' | 'start' | 'nearest'
 */
export function scrollIntoView(page, target, {
  container = null, behavior = 'smooth', block = 'center', inline = 'center', margin = 0
} = {}) {
  const words = page.resolve(target);
  if (!words.length) return null;

  const rects = words.map(w => w.el.getBoundingClientRect()).filter(r => r.width || r.height);
  if (!rects.length) return null;
  const box = {
    left: Math.min(...rects.map(r => r.left)), right: Math.max(...rects.map(r => r.right)),
    top: Math.min(...rects.map(r => r.top)), bottom: Math.max(...rects.map(r => r.bottom))
  };

  const el = container || scrollParent(page.el);
  if (!el || el === document.scrollingElement) {
    const y = window.scrollY + pos(box.top - margin, box.bottom + margin, 0, window.innerHeight, block);
    const x = window.scrollX + pos(box.left - margin, box.right + margin, 0, window.innerWidth, inline);
    window.scrollTo({ top: y, left: x, behavior });
    return { box, container: null };
  }
  const c = el.getBoundingClientRect();
  el.scrollTo({
    top: el.scrollTop + pos(box.top - margin, box.bottom + margin, c.top, c.bottom, block),
    left: el.scrollLeft + pos(box.left - margin, box.right + margin, c.left, c.right, inline),
    behavior
  });
  return { box, container: el };
}

function pos(a, b, lo, hi, mode) {
  if (mode === 'start') return a - lo;
  if (mode === 'end') return b - hi;
  if (mode === 'nearest') return a < lo ? a - lo : b > hi ? b - hi : 0;
  return (a + b) / 2 - (lo + hi) / 2;              // center
}

function scrollParent(el) {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const s = getComputedStyle(p);
    if (/(auto|scroll|overlay)/.test(s.overflowY + s.overflowX)) return p;
  }
  return document.scrollingElement;
}
