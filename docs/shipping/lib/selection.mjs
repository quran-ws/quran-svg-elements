/* mushaf.js — drag-select and copy real Quranic text.
 *
 * The files have no <text>, so native selection has nothing to grab. This adds
 * selection BEHAVIOUR on top of the shared per-word hit layer (overlay.mjs) —
 * it does not build an overlay of its own, which is what lets selection,
 * hover, tap and highlighting all run at once on the same page.
 *
 * Every non-obvious line below is a debugging finding, not a preference:
 *   - the layer measures with getBoundingClientRect(), not getBBox(): the
 *     latter reports a group's own user space and ignores the transforms above
 *     it, which puts line 1 at the bottom of the page (residual error is then
 *     0.016 px across 127 words);
 *   - snap the range out to whole words: inside a transparent span the caret
 *     follows the FALLBACK FONT's advances, not the ink, so a mid-word drag
 *     cuts at an arbitrary letter;
 *   - spans are sized to the HIT box, not the ink box, so the layer has no
 *     dead zones (overlay.mjs); the painted band is drawn from the INK boxes
 *     and from the line PITCH, never from a line's bounding box, which
 *     includes ascenders that overrun its neighbour and would make adjacent
 *     bands overlap and darken;
 *   - native ::selection is suppressed and the band is drawn as ONE rect per
 *     printed line, because ::selection paints each span's own box and the
 *     varying heights and gaps read as notches;
 *   - never carry \n in the DOM: inside a span it makes the span two text
 *     lines tall and its band spills over; in its own span it collapses and
 *     disappears from the copy. The payload is built in the copy handler from
 *     the selected words instead — which is also what lets the caller choose
 *     which text form is copied;
 *   - the layer is measured in SCREEN PIXELS and is rebuilt on resize by
 *     overlay.mjs, once for every consumer.
 */

import { acquireHitLayer } from './overlay.mjs';

/**
 * @param form      which text form Ctrl+C copies
 * @param citation  true -> "…text… (2:255)"; or fn(words, text, ayahKeys) -> string
 * @param onSelect  {text, words, ayahKeys} on every selection change
 */
export function attachSelection(page, {
  mount = null, form = 'rasm_uthmani', citation = false, onSelect = null, copy = true,
  paintBand = true, bandFill = '#2d6fd6', bandOpacity = 0.25, bandPadX = 0.6
} = {}) {
  const hl = acquireHitLayer(page, { mount, form });
  const doc = page.el.ownerDocument;
  let copyForm = form;

  const spanOf = n => (n && (n.nodeType === 1 ? n : n.parentElement))
    ?.closest('.mushaf-hitlayer span') || null;

  /* Snap out to whole words. */
  function snap() {
    const sel = doc.defaultView.getSelection();
    if (!sel || !sel.rangeCount || sel.isCollapsed) return;
    const r = sel.getRangeAt(0);
    const a = spanOf(r.startContainer), b = spanOf(r.endContainer);
    if (!a || !b) return;
    const out = doc.createRange();
    out.setStartBefore(a);
    out.setEndAfter(b);
    sel.removeAllRanges();
    sel.addRange(out);
  }

  function selectedSpans() {
    const sel = doc.defaultView.getSelection();
    if (!sel || !sel.rangeCount || sel.isCollapsed) return [];
    const r = sel.getRangeAt(0);
    return hl.spans().filter(s => r.intersectsNode(s));
  }
  function selectedWords() {
    return selectedSpans().map(s => page.word(s.dataset.wordKey)).filter(Boolean);
  }

  /** The payload, built from data-word-key — the mushaf's own line breaks kept. */
  function text(which = copyForm) {
    let out = '', prevLine = null;
    for (const s of selectedSpans()) {
      const w = page.word(s.dataset.wordKey);
      const v = w && w.form(which);
      if (!v) continue;
      out += (prevLine !== null && s.dataset.line !== prevLine ? '\n' : (out ? ' ' : '')) + v;
      prevLine = s.dataset.line;
    }
    return out;
  }

  /** Only the selection knows which ayahs a drag spans, so only it can copy
   *  "…text… (2:255)". */
  function payload(which = copyForm) {
    const body = text(which);
    if (!body || !citation) return body;
    const words = selectedWords();
    const ayahKeys = [...new Set(words.map(w => w.ayahKey))];
    if (typeof citation === 'function') return citation(words, body, ayahKeys);
    const ref = ayahKeys.length === 1 ? ayahKeys[0]
      : ayahKeys[0] + '–' + ayahKeys[ayahKeys.length - 1].split(':')[1];
    return `${body} (${ref})`;
  }

  /* ------------------------------------------------------------------
   * WORD GRANULARITY IS A PROPERTY OF THE LIBRARY, not something a caller
   * has to remember to ask for. The range is snapped to whole words on
   * every selectionchange, BEFORE anything reads it, so the painted band,
   * the copied text and any ayah logic all derive from one word list and
   * cannot disagree. Native ::selection is suppressed (overlay.mjs), so a
   * partial-word range cannot even be painted — the failure mode is
   * removed rather than corrected after the fact.
   * ------------------------------------------------------------------ */
  let painting = false, bandHandle = null;

  function repaint() {
    if (bandHandle) { bandHandle.remove(); bandHandle = null; }
    const words = selectedWords();
    if (!words.length) return null;
    /* one rect per printed line: horizontal extent from the words' INK,
     * vertical extent from the line pitch. Behind the ink, pointer-events
     * none — see MushafPage#band. */
    bandHandle = page.band(words, {
      fill: bandFill, opacity: bandOpacity, padX: bandPadX, className: 'mushaf-selband'
    });
    return bandHandle;
  }

  const onChange = () => {
    if (painting) return;
    painting = true;
    try {
      snap();
      if (paintBand) repaint();
      if (onSelect) {
        const words = selectedWords();
        onSelect({ text: text(), words, ayahKeys: [...new Set(words.map(w => w.ayahKey))] });
      }
    } finally { painting = false; }
  };
  doc.addEventListener('selectionchange', onChange);
  const onMouseUp = () => onChange();
  doc.addEventListener('mouseup', onMouseUp);
  /* the layer is rebuilt on resize; the band is in viewBox units and does not
   * need re-measuring, but the selection may have been dropped */
  const offRebuild = hl.onRebuild(() => { page.refreshGeometry(); });

  const onCopy = e => {
    const out = payload();
    if (!out) return;                      // selection elsewhere: leave it alone
    e.clipboardData.setData('text/plain', out);
    e.preventDefault();
    hl.layer.dispatchEvent(new CustomEvent('mushaf:copy', { bubbles: true, detail: { text: out } }));
  };
  if (copy) doc.addEventListener('copy', onCopy);

  return {
    layer: hl.layer, hitLayer: hl,
    get form() { return copyForm; },
    /** Change both what the spans carry and what Ctrl+C copies. */
    setForm(f) { copyForm = f; hl.setForm(f); },
    /** Copy a different form from the same drag without rebuilding. */
    setCopyForm(f) { copyForm = f; },
    get count() { return hl.count; },
    rebuild: () => hl.rebuild(),
    spans: () => hl.spans(),
    words: selectedWords, text, payload,
    selectWords(wordKeys) {
      const list = wordKeys.map(w => hl.spanOf(w)).filter(Boolean);
      if (!list.length) return false;
      const r = doc.createRange();
      r.setStartBefore(list[0]);
      r.setEndAfter(list[list.length - 1]);
      const sel = doc.defaultView.getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      onChange();
      return true;
    },
    clear() { doc.defaultView.getSelection().removeAllRanges(); if (bandHandle) { bandHandle.remove(); bandHandle = null; } },
    /** The band rectangles currently painted — one per printed line. */
    get band() { return bandHandle; },
    repaint,
    detach() {
      doc.removeEventListener('selectionchange', onChange);
      doc.removeEventListener('mouseup', onMouseUp);
      if (copy) doc.removeEventListener('copy', onCopy);
      offRebuild();
      if (bandHandle) { bandHandle.remove(); bandHandle = null; }
      hl.release();
    }
  };
}
