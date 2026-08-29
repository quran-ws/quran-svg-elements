/* mushaf.js — accessibility.
 *
 * An SVG of paths is silent. This gives a screen reader something to say.
 *
 * Note the honest limit: a <title> per group is announced on focus/hover, not
 * read as flowing prose. Where a page already has a selection layer attached
 * (selection.mjs), THAT layer is real DOM text in reading order and is the
 * better screen-reader surface — pass {deferToTextLayer: true} and this marks
 * the SVG aria-hidden so the page is not announced twice.
 */

/**
 * @param form   which text form is announced
 * @param level  'word' | 'ayah' | 'both'
 * @param label  the <svg>'s own accessible name
 */
export function annotate(page, {
  form = 'uthmani', level = 'both', label = null, lang = 'ar', deferToTextLayer = false
} = {}) {
  const svg = page.el;
  const undo = [];
  const set = (el, attr, val) => {
    const prev = el.getAttribute(attr);
    undo.push(() => prev == null ? el.removeAttribute(attr) : el.setAttribute(attr, prev));
    el.setAttribute(attr, val);
  };
  const addTitle = (el, text) => {
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    t.textContent = text;
    el.insertBefore(t, el.firstChild);
    undo.push(() => t.remove());
  };

  if (deferToTextLayer) {
    set(svg, 'aria-hidden', 'true');
    return { remove() { undo.reverse().forEach(f => f()); } };
  }

  const surahs = page.surahs();
  const named = surahs.find(s => s.arabic);
  const auto = label || (
    'Quran page' + (page.number ? ' ' + page.number : '') +
    (named ? ', surah ' + named.latin : '') +
    ', ayat ' + (page.ayahKeys()[0] || '?') + ' to ' + (page.ayahKeys().slice(-1)[0] || '?')
  );
  set(svg, 'role', 'group');
  set(svg, 'aria-label', auto);
  set(svg, 'lang', lang);

  let words = 0, ayahs = 0;
  if (level === 'word' || level === 'both') {
    for (const w of page.words()) {
      const t = w.form(form);
      if (!t) continue;
      set(w.el, 'role', 'img');
      set(w.el, 'aria-label', t);
      addTitle(w.el, t);
      words++;
    }
  }
  if (level === 'ayah' || level === 'both') {
    for (const a of page.ayahs()) {
      a.fragments.forEach((f, i) => {
        set(f, 'role', 'group');
        set(f, 'aria-label',
          `Ayah ${a.aid}` + (a.fragments.length > 1 ? `, part ${i + 1} of ${a.fragments.length}` : ''));
      });
      ayahs++;
    }
  }
  /* header banners are ink, never decomposed (FORMAT §9.12) — name them */
  for (const g of svg.querySelectorAll('g.surah-name, g.basmalah')) {
    const d = g.dataset;
    set(g, 'role', 'img');
    set(g, 'aria-label', g.classList.contains('surah-name')
      ? `Surah ${d.sid} ${d.surahNameAr || ''} (${d.surahNameLatin || ''})`.trim()
      : 'Bismillah ar-Rahman ar-Rahim');
  }

  return { words, ayahs, label: auto, remove() { undo.reverse().forEach(f => f()); } };
}
