/* mushaf.js — raster export of a crop.
 *
 * Serialise -> data: URL -> <img> -> <canvas>. The pages reference nothing
 * external (every path is inline, one colour, no fonts, no images), so the
 * canvas is never tainted and toDataURL() works. Verified headless.
 *
 * Give it a background unless you want transparent paper.
 */

/** @param src a MushafPage, a crop() result, or an <svg> element. */
function svgOf(src) {
  if (!src) throw new TypeError('nothing to rasterise');
  if (src.nodeType === 1) return src;
  if (src.el && src.el.nodeType === 1) return src.el;
  throw new TypeError('expected an <svg>, a MushafPage or a crop() result');
}

function serialise(svg, background) {
  const clone = svg.cloneNode(true);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const vb = (clone.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
  if (background && vb.length === 4) {
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('x', vb[0]); r.setAttribute('y', vb[1]);
    r.setAttribute('width', vb[2]); r.setAttribute('height', vb[3]);
    r.setAttribute('fill', background);
    clone.insertBefore(r, clone.firstChild);
  }
  return { text: new XMLSerializer().serializeToString(clone), vb };
}

/** Render to a <canvas>. `scale` multiplies the viewBox units. */
export async function toCanvas(src, { scale = 4, background = null, width = null } = {}) {
  const svg = svgOf(src);
  const { text, vb } = serialise(svg, background);
  if (vb.length !== 4) throw new Error('cannot rasterise: the SVG has no viewBox');
  const k = width ? width / vb[2] : scale;
  const w = Math.max(1, Math.round(vb[2] * k)), h = Math.max(1, Math.round(vb[3] * k));

  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
  const img = new Image();
  img.decoding = 'sync';
  await new Promise((res, rej) => {
    img.onload = res;
    img.onerror = () => rej(new Error('the browser refused to decode the SVG'));
    img.src = url;
  });
  if (img.decode) { try { await img.decode(); } catch (_) { /* already loaded */ } }

  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (background) { ctx.fillStyle = background; ctx.fillRect(0, 0, w, h); }
  ctx.drawImage(img, 0, 0, w, h);
  return canvas;
}

export async function toPngDataUrl(src, opts = {}) {
  return (await toCanvas(src, opts)).toDataURL('image/png');
}

export async function toPngBlob(src, opts = {}) {
  const canvas = await toCanvas(src, opts);
  return new Promise(res => canvas.toBlob(res, 'image/png'));
}

/** The SVG itself as a data: URL — no canvas, no rasterising, and it scales. */
export function toSvgDataUrl(src, { background = null } = {}) {
  return 'data:image/svg+xml;charset=utf-8,' +
    encodeURIComponent(serialise(svgOf(src), background).text);
}
