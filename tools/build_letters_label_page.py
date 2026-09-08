#!/usr/bin/env python3
"""A page for drawing letter cuts by hand: docs/defects/letters_label.html

    python3 tools/build_letters_label_page.py --pairs "لك,عل,لح,كل,فل,كف,ته,فس,كت,بم" --per 40

For each sampled run the word is drawn large; click two points to draw a cut line
across the stroke (the first click starts a line, the second ends it), one line per
joint you want to give, right to left. Drag nothing; a wrong line is removed with
its ✕. "Copy" exports JSON lines {page, wid, run, text, cuts: [[[x,y],[x,y]]…]} in the
page-path coordinate system — the same units as the tajweed hand cuts — for
docs/defects/letters_hand_cuts.jsonl, which build_letter_labels.py reads as extra
hand cuts. Nothing here edits code.
"""
import argparse
import glob
import html
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

OUT = os.path.join(L.ROOT, "docs", "defects", "letters_label.html")


PALE = ["#f4a3b5", "#a9dbb0", "#a8b8ec", "#f9c89a", "#c9a0d6", "#a5e8f8", "#f6a4f0", "#d9c3a0"]


SPLIT_JS = r"""
// ---- live preview: the pieces the drawn lines actually make -----------------
// Same rules as build_letter_labels.drawn_cut_labels + order_pieces, in the
// browser: 4 px per unit, lines 3 px wide extended 1u, components of ink minus
// lines, a contour no line touches is its own piece only after a letter that
// never joins left, pieces ordered along the chain the lines make.
const NOJOIN = new Set(Array.from('اأإآٱدذرزوؤءةى'));
const COLS = ['#e6194b','#3cb44b','#4363d8','#f58231','#911eb4','#42d4f4','#f032e6','#9a6324','#808000','#000075'];
const Z = 4, MINPX = 12;

function maskOf(ctx, W, H) {
  const px = ctx.getImageData(0, 0, W, H).data, m = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) m[i] = px[i * 4 + 3] > 127 ? 1 : 0;
  return m;
}
function newCtx(g, W, H) {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d', {willReadFrequently: true});
  ctx.setTransform(Z, 0, 0, -Z, -g.x0 * Z, g.y1 * Z);      // page (x,y) → canvas px
  return ctx;
}
function paintLines(g, W, H, cuts, ext) {
  const ctx = newCtx(g, W, H);
  ctx.strokeStyle = '#000'; ctx.lineWidth = 3 / Z; ctx.lineCap = 'butt';
  for (const c of cuts) {
    let [a, b] = [c[0], c[c.length - 1]];
    const dx = b[0] - a[0], dy = b[1] - a[1], nn = Math.hypot(dx, dy) || 1e-9;
    const p0 = [a[0] - dx / nn * ext, a[1] - dy / nn * ext];
    const p1 = [b[0] + dx / nn * ext, b[1] + dy / nn * ext];
    ctx.beginPath(); ctx.moveTo(p0[0], p0[1]);
    for (const q of c) ctx.lineTo(q[0], q[1]);
    ctx.lineTo(p1[0], p1[1]); ctx.stroke();
  }
  return maskOf(ctx, W, H);
}
function label(mask, W, H, eight) {
  const lab = new Int32Array(W * H).fill(0), sizes = [0], st = [];
  let cur = 0;
  const nb = eight ? [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]]
                   : [[0,-1],[-1,0],[1,0],[0,1]];
  for (let i = 0; i < W * H; i++) {
    if (!mask[i] || lab[i]) continue;
    cur++; let n = 0; st.length = 0; st.push(i); lab[i] = cur;
    while (st.length) {
      const j = st.pop(); n++;
      const x = j % W, y = (j / W) | 0;
      for (const [dx, dy] of nb) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        const k = ny * W + nx;
        if (mask[k] && !lab[k]) { lab[k] = cur; st.push(k); }
      }
    }
    sizes.push(n);
  }
  return {lab, n: cur, sizes};
}
function bboxOf(lab, W, H, id) {
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, n = 0, sx = 0;
  for (let i = 0; i < W * H; i++) if (lab[i] === id) {
    const x = i % W, y = (i / W) | 0;
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
    n++; sx += x;
  }
  return {x0, x1, y0, y1, n, mx: sx / Math.max(n, 1)};
}
function nearestMap(lab, ids, W, H) {                       // multi-source BFS
  const out = new Int32Array(W * H).fill(-1), q = [];
  for (let i = 0; i < W * H; i++) if (ids.has(lab[i])) { out[i] = lab[i]; q.push(i); }
  for (let h = 0; h < q.length; h++) {
    const j = q[h], x = j % W, y = (j / W) | 0;
    for (const [dx, dy] of [[0,-1],[-1,0],[1,0],[0,1]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      const k = ny * W + nx;
      if (out[k] === -1) { out[k] = out[j]; q.push(k); }
    }
  }
  return out;
}
function splitRun(g, cuts) {
  const W = Math.ceil(g.w * Z), H = Math.ceil(g.h * Z), n = g.letters.length;
  const ictx = newCtx(g, W, H);
  ictx.fillStyle = '#000';
  for (const d of g.ds) ictx.fill(new Path2D(d), 'evenodd');
  const ink = maskOf(ictx, W, H);
  const line = paintLines(g, W, H, cuts, 1.0);
  const free = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) free[i] = ink[i] && !line[i] ? 1 : 0;
  const C = label(free, W, H, false), whole = label(ink, W, H, true);
  const touched = new Set();
  for (let i = 0; i < W * H; i++) if (line[i] && ink[i]) touched.add(whole.lab[i]);
  let pieces = [], extras = [];
  for (let c = 1; c <= C.n; c++) {
    if (C.sizes[c] < MINPX) continue;
    let wc = 0;
    for (let i = 0; i < W * H; i++) if (C.lab[i] === c) { wc = whole.lab[i]; break; }
    (touched.has(wc) ? pieces : extras).push(c);
  }
  // a contour no line touches is its own letter only after one that never joins left
  if (pieces.length < n) {
    const allowed = g.letters.slice(0, -1).filter(ch => NOJOIN.has(ch)).length;
    extras.sort((a, b) => C.sizes[b] - C.sizes[a]);
    const take = Math.min(allowed, n - pieces.length);
    for (const c of extras.slice(0, take)) pieces.push(c);
    extras = extras.filter(c => !pieces.includes(c));
  }
  const box = {};
  for (const c of pieces.concat(extras)) box[c] = bboxOf(C.lab, W, H, c);
  // order along the chain the lines make, from the rightmost end
  const ids = new Set(pieces), near = nearestMap(C.lab, ids, W, H), adj = {};
  for (const c of pieces) adj[c] = new Set();
  for (const cut of cuts) {
    const one = paintLines(g, W, H, [cut], 0), cnt = {};
    for (let i = 0; i < W * H; i++) if (one[i] && ink[i] && near[i] > 0) cnt[near[i]] = (cnt[near[i]] || 0) + 1;
    const top = Object.keys(cnt).map(Number).sort((a, b) => cnt[b] - cnt[a]).slice(0, 2);
    if (top.length === 2) { adj[top[0]].add(top[1]); adj[top[1]].add(top[0]); }
  }
  const seen = new Set(), chains = [];
  const byX = [...pieces].sort((a, b) => box[b].mx - box[a].mx);
  const ends = byX.filter(c => adj[c].size <= 1);
  for (const start of ends.concat(byX)) {
    if (seen.has(start)) continue;
    const ch = [start]; seen.add(start);
    for (;;) {
      const nx = [...adj[ch[ch.length - 1]]].filter(k => !seen.has(k));
      if (!nx.length) break;
      ch.push(nx[0]); seen.add(nx[0]);
    }
    chains.push(ch);
  }
  chains.sort((a, b) => Math.max(...b.map(c => box[c].mx)) - Math.max(...a.map(c => box[c].mx)));
  const order = [].concat(...chains);
  // every remaining pixel joins a piece: extras by x-overlap, line pixels by distance
  const out = new Int32Array(W * H).fill(-1);
  order.forEach((c, k) => { for (let i = 0; i < W * H; i++) if (C.lab[i] === c) out[i] = k; });
  for (const c of extras) {
    const b = box[c];
    let best = 0, bestv = -1e9;
    order.forEach((pc, k) => {
      const q = box[pc], ov = Math.min(b.x1, q.x1) - Math.max(b.x0, q.x0);
      const v = ov >= 0 ? ov : -Math.abs(b.mx - q.mx);
      if (v > bestv) { bestv = v; best = k; }
    });
    for (let i = 0; i < W * H; i++) if (C.lab[i] === c) out[i] = best;
  }
  const have = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) have[i] = out[i] >= 0 ? 1 : 0;
  const fill = nearestMap(out.map(v => v + 1), new Set([...order.keys()].map(k => k + 1)), W, H);
  for (let i = 0; i < W * H; i++) if (ink[i] && out[i] < 0 && fill[i] > 0) out[i] = fill[i] - 1;
  return {lab: out, W, H, k: order.length, n};
}
function centroid(lab, W, H, k) {
  let n = 0, sx = 0, sy = 0;
  for (let i = 0; i < W * H; i++) if (lab[i] === k) { n++; sx += i % W; sy += (i / W) | 0; }
  return {n, x: sx / Math.max(n, 1), y: sy / Math.max(n, 1)};
}
function tile(r, g, k, letterIdx) {
  const b = bboxOf(r.lab.map(v => v + 1), r.W, r.H, k + 1);
  if (!b.n) return null;
  const w = b.x1 - b.x0 + 3, h = b.y1 - b.y0 + 3, s = 2;
  const cv = document.createElement('canvas');
  cv.width = w * s; cv.height = h * s;
  const ctx = cv.getContext('2d'), im = ctx.createImageData(w * s, h * s);
  const col = COLS[letterIdx % COLS.length];
  const rgb = [parseInt(col.slice(1, 3), 16), parseInt(col.slice(3, 5), 16), parseInt(col.slice(5, 7), 16)];
  for (let y = 0; y < h * s; y++) for (let x = 0; x < w * s; x++) {
    const sx = b.x0 - 1 + ((x / s) | 0), sy = b.y0 - 1 + ((y / s) | 0);
    if (sx < 0 || sy < 0 || sx >= r.W || sy >= r.H) continue;
    if (r.lab[sy * r.W + sx] !== k) continue;
    const o = (y * w * s + x) * 4;
    im.data[o] = rgb[0]; im.data[o + 1] = rgb[1]; im.data[o + 2] = rgb[2]; im.data[o + 3] = 255;
  }
  ctx.putImageData(im, 0, 0);
  const cell = document.createElement('div');
  cell.className = 'piece';
  cell.title = 'click: give this piece to the next letter';
  cell.appendChild(cv);
  const lb = document.createElement('div');
  lb.className = 'plab';
  lb.textContent = g.letters[letterIdx] || '?';
  lb.style.color = col;
  cell.appendChild(lb);
  return cell;
}
function render(card) {
  const r = card._r, g = card._g, assign = card._assign;
  const box = card.querySelector('.pieces'), status = card.querySelector('.status');
  box.textContent = '';
  for (let k = 0; k < r.k; k++) {
    const cell = tile(r, g, k, assign[k]);
    if (!cell) continue;
    cell.onclick = () => { card._assign[k] = (card._assign[k] + 1) % r.n; render(card); };
    box.appendChild(cell);
  }
  const held = new Set(assign);
  const missing = [];
  for (let i = 0; i < r.n; i++) if (!held.has(i)) missing.push(g.letters[i]);
  if (!missing.length && r.k === r.n) {
    status.className = 'status ok';
    status.textContent = '✓ ' + r.n + ' letters, ' + r.k + ' pieces';
  } else if (!missing.length) {
    status.className = 'status warn';           // more pieces than letters: check each one
    status.textContent = '⚠ ' + r.k + ' pieces for ' + r.n + ' letters — check the letter under each piece, click to change';
  } else {
    status.className = 'status bad';
    status.textContent = '✗ no ink for ' + missing.join(' ') + ' — draw another line, or click a piece to give it that letter';
  }
}
// The split as it stands, one letter at a time. Most cuts are already right, and
// redrawing a right one wastes the only scarce thing here, so the page opens on the
// current answer and asks for a verdict; a line is only needed where the answer is wrong.
function currentTile(g, k) {
  const ds = (g.model || [])[k] || [];
  if (!ds.length) return null;
  const pad = 0.4, S = 11;
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  const paths = ds.map(d => new Path2D(d));
  for (const d of ds) {
    for (const m of d.matchAll(/-?\d+(?:\.\d+)?/g)) { /* bbox from the numbers */ }
  }
  const nums = ds.join(' ').match(/-?\d+(?:\.\d+)?/g) || [];
  for (let i = 0; i + 1 < nums.length; i += 2) {
    const x = +nums[i], y = +nums[i + 1];
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  if (x1 < x0) return null;
  const w = Math.max(1, (x1 - x0 + 2 * pad)), h = Math.max(1, (y1 - y0 + 2 * pad));
  const cv = document.createElement('canvas');
  cv.width = Math.round(w * S); cv.height = Math.round(h * S);
  const ctx = cv.getContext('2d');
  ctx.setTransform(S, 0, 0, -S, -(x0 - pad) * S, (y1 + pad) * S);
  ctx.fillStyle = COLS[k % COLS.length];
  for (const p of paths) ctx.fill(p, 'evenodd');
  const cell = document.createElement('div');
  cell.className = 'piece';
  cell.appendChild(cv);
  const lb = document.createElement('div');
  lb.className = 'plab';
  lb.textContent = g.letters[k] || '?';
  lb.style.color = COLS[k % COLS.length];
  cell.appendChild(lb);
  return cell;
}
function showCurrent(card, g) {
  const box = card.querySelector('.pieces'), status = card.querySelector('.status');
  box.textContent = '';
  let shown = 0;
  for (let k = 0; k < g.letters.length; k++) {
    const cell = currentTile(g, k);
    if (cell) { box.appendChild(cell); shown++; }
  }
  const v = card.dataset.verdict || '';
  status.className = 'status' + (v === 'ok' ? ' ok' : v === 'bad' ? ' bad' : '');
  status.textContent = !shown
    ? g.letters.length + ' letters — nothing split yet, draw a line across each joint'
    : v === 'ok' ? '\u2713 confirmed right as it stands'
    : v === 'bad' ? '\u2717 marked wrong — draw the lines that fix it'
    : 'the split as it stands, ' + shown + ' of ' + g.letters.length
      + ' letters — is it right?';
}
function preview(card) {
  const g = JSON.parse(card.querySelector('.rundata').textContent);
  const cuts = [...card.querySelectorAll('.cutlist span')].map(s => JSON.parse(s.dataset.cut));
  const status = card.querySelector('.status');
  if (!cuts.length) {
    showCurrent(card, g);
    card._assign = null;
    return;
  }
  let r = splitRun(g, cuts);
  r = subdivideByModel(g, r);
  card._r = r; card._g = g;
  const sig = JSON.stringify(cuts);
  if (!card._assign || card._sig !== sig || card._assign.length !== r.k) {
    card._assign = seedAssign(g, r);
    card._sig = sig;
  }
  render(card);
}
// A drawn line is a correction, not the whole answer. Abdullah drew one line across
// أسه, whose three letters the build already separates, and the card threw the build's
// split away and reported "no ink for ا". His lines are authoritative BOUNDARIES: a
// piece may not cross one. Inside a piece, though, the build's own split still knows
// where the letters are, so a piece holding more than one of them is subdivided by it.
// Where he disagrees with the build his line still wins, because the subdivision happens
// strictly inside the region his lines made.
function modelOwner(g, W, H) {
  const ds = g.model || [];
  const owner = new Int32Array(W * H).fill(-1);
  for (let i = 0; i < ds.length; i++) {
    if (!ds[i] || !ds[i].length) continue;
    const ctx = newCtx(g, W, H);
    ctx.fillStyle = '#000';
    for (const d of ds[i]) ctx.fill(new Path2D(d), 'evenodd');
    const m = maskOf(ctx, W, H);
    for (let j = 0; j < owner.length; j++) if (m[j] && owner[j] < 0) owner[j] = i;
  }
  return owner;
}
function subdivideByModel(g, r) {
  if (!g.model || r.k >= r.n) return r;
  const owner = modelOwner(g, r.W, r.H);
  const lab = Int32Array.from(r.lab);
  let next = r.k;
  for (let k = 0; k < r.k; k++) {
    const cnt = new Int32Array(r.n);
    let tot = 0;
    for (let j = 0; j < lab.length; j++)
      if (lab[j] === k && owner[j] >= 0) { cnt[owner[j]]++; tot++; }
    if (!tot) continue;
    const here = [];
    for (let i = 0; i < r.n; i++) if (cnt[i] >= 0.12 * tot) here.push(i);
    if (here.length < 2) continue;                 // one letter in this piece: leave it
    here.sort((a, b) => a - b);
    const idOf = {};
    idOf[here[0]] = k;                             // the first keeps the piece's own id
    for (let t = 1; t < here.length; t++) idOf[here[t]] = next++;
    for (let j = 0; j < lab.length; j++) {
      if (lab[j] !== k || owner[j] < 0) continue;
      let best = here[0], bd = Infinity;
      for (const i of here) { const d = Math.abs(i - owner[j]); if (d < bd) { bd = d; best = i; } }
      lab[j] = idOf[best];
    }
  }
  if (next === r.k) return r;
  return Object.assign({}, r, {lab: lab, k: next});
}
function seedAssign(g, r) {
  // each piece starts on the letter whose model ink it covers most; a piece the model
  // has nothing for falls back to its place in reading order
  // reading order for the first n pieces; a piece beyond them takes the letter of the
  // nearest one, which is right far more often than dropping it on the last letter
  const cen = [];
  for (let k = 0; k < r.k; k++) cen.push(centroid(r.lab, r.W, r.H, k));
  const out = [];
  for (let k = 0; k < r.k; k++) {
    if (k < r.n) { out.push(k); continue; }
    let best = 0, bd = Infinity;
    for (let i = 0; i < r.n; i++) {
      const d = (cen[i].x - cen[k].x) ** 2 + (cen[i].y - cen[k].y) ** 2;
      if (d < bd) { bd = d; best = i; }
    }
    out.push(best);
  }
  const ds = g.model || [];
  if (!ds.length) return out;
  const owner = new Int32Array(r.W * r.H).fill(-1);
  for (let i = 0; i < ds.length; i++) {
    if (!ds[i] || !ds[i].length) continue;
    const ctx = newCtx(g, r.W, r.H);
    ctx.fillStyle = '#000';
    for (const d of ds[i]) ctx.fill(new Path2D(d), 'evenodd');
    const m = maskOf(ctx, r.W, r.H);
    for (let j = 0; j < owner.length; j++) if (m[j] && owner[j] < 0) owner[j] = i;
  }
  for (let k = 0; k < r.k; k++) {
    const cnt = new Int32Array(r.n);
    let any = false;
    for (let j = 0; j < owner.length; j++) if (r.lab[j] === k && owner[j] >= 0) { cnt[owner[j]]++; any = true; }
    if (!any) continue;
    let best = 0;
    for (let i = 1; i < r.n; i++) if (cnt[i] > cnt[best]) best = i;
    out[k] = best;
  }
  // The seeding above copies the model, so where the model is wrong the labels inherit
  // the error: on حكم it put two pieces on the kaf and none on the ha, and the card then
  // asked for a line that was already drawn. Two things the script itself guarantees fix
  // that. Letters do not interleave, so the assignment must not decrease along reading
  // order; and if a letter still ends with no piece while there are pieces enough to go
  // round, the model's opinion is worth less than reading order, so drop it.
  for (let k = 1; k < r.k; k++) if (out[k] < out[k - 1]) out[k] = out[k - 1];
  const held = new Set(out);
  let missing = false;
  for (let i = 0; i < r.n; i++) if (!held.has(i)) missing = true;
  if (missing && r.k >= r.n) {
    for (let k = 0; k < r.k; k++) out[k] = Math.min(k, r.n - 1);
  }
  return out;
}
function assignOf(card) {                       // [[x, y, letter], …] in page units
  if (!card._r || !card._assign) return null;
  const r = card._r, g = card._g;
  const plain = r.k === r.n && card._assign.every((v, i) => v === i);
  if (plain) return null;                       // one piece per letter, nothing to say
  return card._assign.map((k, i) => {
    const c = centroid(r.lab, r.W, r.H, i);
    return [+(g.x0 + c.x / Z).toFixed(3), +(g.y1 - c.y / Z).toFixed(3), k];
  });
}
"""


def word_svg(word, run_eids, pad=2.0, scale=10, letters_word=None):
    """The word, the run to cut in dark grey; with `letters_word` (the model build's
    version) the model's letters are shown in pale colours under it as a hint."""
    polys = [poly for p in word["paths"] if p["d"] and p["kind"] == "body" for poly in L.flatten(p["d"])]
    if not polys:
        return "", None
    x0, y0, x1, y1 = L.bbox(polys)
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    parts = ['<svg class="art" data-x0="%.3f" data-y1="%.3f" data-w="%.3f" data-h="%.3f" viewBox="0 0 %.2f %.2f" width="%d" height="%d">'
             % (x0 - pad, y1 + pad, w, h, w, h, int(w * scale), int(h * scale))]
    # page-path y is UP: flip inside the group, so screen (sx, sy) ↔ page (x0-pad+sx, y1+pad-sy)
    parts.append('<g transform="translate(%.3f %.3f) scale(1 -1)">' % (-(x0 - pad), y1 + pad))
    shown = set()
    if letters_word:
        import re
        for k, m in enumerate(re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', letters_word["inner"], re.S)):
            at = L.parse_attrs(m.group(1))
            if at.get("data-unsplit") == "1":
                continue
            col = PALE[int(at.get("data-index", k)) % len(PALE)]
            for pm in re.finditer(r'<path ([^>]*?)/>', m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    base = pa.get("data-eid", "").rsplit("-", 1)[0] if pa.get("data-cut") == "1" else pa.get("data-eid")
                    if base in run_eids:
                        parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (pa["d"], col))
                        shown.add(base)
    for p in word["paths"]:
        if p["kind"] != "body" or not p["d"]:
            continue
        if p["eid"] in shown:
            continue
        col = "#222" if p["eid"] in run_eids else "#bbb"
        parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (p["d"], col))
    parts.append('</g><g class="lines"></g></svg>')
    ds = [p["d"] for p in word["paths"] if p["kind"] == "body" and p["d"] and p["eid"] in run_eids]
    return "".join(parts), {"x0": round(x0 - pad, 3), "y1": round(y1 + pad, 3),
                            "w": round(w, 3), "h": round(h, 3), "ds": ds}


def model_letters(letters_word, lidx):
    """The model's ink for each letter of the run, from the letters build: a list of
    path `d` strings per run position. The drawing page seeds each piece's letter from
    this, so a piece the lines produce starts on the model's opinion rather than on the
    last letter of the run."""
    out = [[] for _ in lidx]
    if not letters_word:
        return out
    import re
    where = {v: i for i, v in enumerate(lidx)}
    for m in re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', letters_word["inner"], re.S):
        at = L.parse_attrs(m.group(1))
        if at.get("data-unsplit") == "1":
            continue
        try:
            k = where.get(int(at.get("data-index", -1)))
        except ValueError:
            k = None
        if k is None:
            continue
        for pm in re.finditer(r'<path ([^>]*?)/>', m.group(2)):
            pa = L.parse_attrs(pm.group(1))
            if pa.get("data-kind") == "body" and pa.get("d"):
                out[k].append(pa["d"])
    return out


def pair_coverage(pairs):
    """Per pair: joints in the mushaf, joints the tajweed layers cut, joints drawn by
    hand — read from the label masks (a joint is covered when both letters have
    single-bit pixels), so the ranking is measured, not kept by hand."""
    import numpy as np
    from tools.build_letter_labels import LABELS_DIR
    allp, cov, drawn = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(LABELS_DIR, "*.npz"))):
        z = np.load(f)
        meta = json.loads(str(z["meta"]))
        mask = z["mask"]
        for smp, m in zip(meta, mask):
            t = smp["text"]
            if len(t) != smp["n"]:
                continue
            single = m[(m & (m - 1)) == 0]
            bits = {int(np.log2(b)) for b in np.unique(single[single > 0])}
            for i in range(len(t) - 1):
                pr = t[i:i + 2]
                if pr not in pairs:
                    continue
                allp[pr] = allp.get(pr, 0) + 1
                if smp.get("drawn"):
                    drawn[pr] = drawn.get(pr, 0) + 1
                elif i in bits and i + 1 in bits:
                    cov[pr] = cov.get(pr, 0) + 1
    return {pr: (allp.get(pr, 0), cov.get(pr, 0), drawn.get(pr, 0)) for pr in pairs}


def collect(pairs, per, seed, words=()):
    """`words` are (page, wid) asked for by name; they come first, marked "redo"."""
    rnd = random.Random(seed)
    by_pair = {p: [] for p in pairs}
    named = []
    for path in sorted(glob.glob(os.path.join(L.CUTS_DIR, "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        for wid, wrec in rec["words"].items():
            for ri, run in enumerate(wrec["runs"]):
                if len(run["letters"]) < 2:
                    continue
                if (rec["page"], wid) in words:
                    named.append(("redo", rec["page"], wid, ri, run["text"], run.get("eid", []), run["letters"]))
                for pr in pairs:
                    if pr in run["text"]:
                        by_pair[pr].append((rec["page"], wid, ri, run["text"], run.get("eid", []),
                                            run["letters"], bool(run.get("flags"))))
    out = list(named)
    for pr, items in by_pair.items():
        rnd.shuffle(items)
        items.sort(key=lambda it: (not it[-1], len(it[3])))   # runs the builder could not cut first, shortest first
        out += [(pr,) + it[:-1] for it in items[:per]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="لك,عل,لح,كل,فل,كف,ته,فس,كت,بم")
    ap.add_argument("--per", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--words", default="", help="page:wid,... to show first (a drawing to redo)")
    ap.add_argument("--rank", action="store_true", help="order pairs by uncut joints, with a heading per pair")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    words = {(int(w.split(":")[0]), w.split(":", 1)[1]) for w in a.words.split(",") if w}
    pairs = [p for p in a.pairs.split(",") if p]
    stats = pair_coverage(pairs) if a.rank else {}
    if a.rank:                                             # most uncut joints first
        pairs.sort(key=lambda pr: -(stats[pr][0] - stats[pr][1] - stats[pr][2]))
    items = collect(pairs, a.per, a.seed, words)
    cards = []
    cache = {}
    last = None
    for pr, page, wid, ri, text, eids, lidx in items:
        if a.rank and pr != last:
            if pr == "redo":
                cards.append('<h2 class="sec">Redo</h2>')
            else:
                n, c, d = stats[pr]
                cards.append('<h2 class="sec"><span class="ar">%s</span> — %d joints in the mushaf, %d cut by the tajweed layers, %d drawn</h2>'
                             % (pr, n, c, d))
            last = pr
        if page not in cache:
            words, _ = L.read_words(page)
            lw = {}
            lpath = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
            if os.path.exists(lpath):
                lws, _ = L.read_words(page, L.LETTERS_SVG)
                lw = {w["wid"]: w for w in lws}
            cache[page] = ({w["wid"]: w for w in words}, lw)
        word = cache[page][0].get(wid)
        if word is None:
            continue
        svg, geom = word_svg(word, set(eids), letters_word=cache[page][1].get(wid))
        if not svg:
            continue
        # the run's real letters, which are not always the group's text: the word build
        # sometimes files a letter's ink in the next group and align_runs re-keys it
        try:
            wl = L.letters_of(word["uthmani"])
            geom["letters"] = [wl[i]["ch"] for i in lidx]
        except Exception:
            geom["letters"] = list(text)
        geom["model"] = model_letters(cache[page][1].get(wid), lidx)
        cards.append('<div class="card" data-page="%d" data-wid="%s" data-run="%d" data-text="%s">%s'
                     '<script type="application/json" class="rundata">%s</script>'
                     '<div class="meta"><b>%s</b> p%d %s <span class="ar">%s</span> run <span class="ar">%s</span>'
                     ' <span class="count">0 cuts</span></div><div class="cutlist"></div>'
                     '<div class="split"><div class="verdict">'
                     '<button class="yes" onclick="verdict(this,\'ok\')">\u2713 right as it is</button>'
                     '<button class="no" onclick="verdict(this,\'bad\')">\u2717 wrong</button>'
                     '</div><div class="status"></div><div class="pieces"></div></div></div>'
                     % (page, wid, ri, html.escape(text), svg,
                        json.dumps(geom, ensure_ascii=False).replace("<", "\\u003c"),
                        pr, page, wid, html.escape(word["uthmani"]), html.escape(text)))
    page = ("<!doctype html><meta charset=utf-8><title>Letter cuts — draw</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px}"
            "svg.art{max-width:100%;height:auto;cursor:crosshair;background:#fff}"
            ".ar{font-size:22px;direction:rtl}.meta{font-size:13px;margin-top:4px}.cutlist span{margin-right:8px;font-size:12px}"
            ".cutlist button{font-size:11px}button.copy{position:fixed;top:10px;right:10px;padding:8px 14px}"
            "h2.sec{grid-column:1/-1;margin:18px 0 4px;font-size:18px;border-bottom:1px solid #ccc}"
            ".split{margin-top:6px;border-top:1px dashed #ddd;padding-top:6px}"
            ".pieces{display:flex;direction:rtl;gap:10px;align-items:flex-end;overflow-x:auto;padding-bottom:2px}"
            ".piece{text-align:center;cursor:pointer}.piece canvas{display:block;image-rendering:pixelated}"
            ".piece:hover{outline:1px solid #999}"
            ".plab{font-size:20px;direction:rtl}.status{font-size:12px;margin-bottom:4px}"
            ".status.ok{color:#2a7}.status.bad{color:#b00}.status.warn{color:#b70}"
            ".verdict{margin:2px 0 4px}.verdict button{font-size:11px;margin-right:6px;padding:2px 8px}"
            ".card.ok{border-color:#2a7;background:#f6fffa}.card.bad{border-color:#b00;background:#fff7f7}"
            "#tally{position:fixed;top:10px;right:150px;background:#fff;border:1px solid #ccc;"
            "border-radius:6px;padding:8px 12px;font-size:13px;z-index:9}</style>"
            "<button class=copy onclick='copyAll()'>Copy</button><div id=tally></div>"
            "<h1>Draw the letter cuts</h1><p><b>Each card opens on the split as it stands, "
            "letter by letter.</b> Most are already right, so say so with \u2713 and move on \u2014 "
            "a confirmation is as good a label as a drawing, and costs a click instead of two "
            "lines. Only where it is wrong do you need to draw: mark it \u2717, then "
            "click two points to draw one cut line across the stroke, "
            "one line per joint, from right to left. ✕ removes a line. Then Copy and paste into "
            "<code>docs/defects/letters_hand_cuts.jsonl</code>. Under each word the pieces your lines make are "
            "shown one letter at a time, in reading order, exactly as the label builder cuts them. Where no line can give one "
            "piece per letter — the medial \u0643+\u0644 ligature, where the kaf is an arm plus a bowl and the lam a stem plus a foot — "
            "cut the strokes apart and then <b>click a piece to give it to the next letter</b>.</p>"
            "<div class=grid>" + "".join(cards) + "</div>"
            "<script>" + SPLIT_JS +
            "document.querySelectorAll('svg.art').forEach(svg=>{let pending=null;"
            "svg.addEventListener('click',e=>{const r=svg.getBoundingClientRect();const vb=svg.viewBox.baseVal;"
            "const sx=(e.clientX-r.left)/r.width*vb.width, sy=(e.clientY-r.top)/r.height*vb.height;"
            "if(!pending){pending=[sx,sy];return;}const a=pending;pending=null;"
            "const ln=document.createElementNS('http://www.w3.org/2000/svg','line');"
            "ln.setAttribute('x1',a[0]);ln.setAttribute('y1',a[1]);ln.setAttribute('x2',sx);ln.setAttribute('y2',sy);"
            "ln.setAttribute('stroke','#e00');ln.setAttribute('stroke-width','0.35');svg.querySelector('.lines').appendChild(ln);"
            "const card=svg.closest('.card');const x0=+svg.dataset.x0,y1=+svg.dataset.y1;"
            "const cut=[[x0+a[0],y1-a[1]],[x0+sx,y1-sy]];"
            "const item=document.createElement('span');item.textContent='cut';const b=document.createElement('button');b.textContent='✕';"
            "b.onclick=()=>{ln.remove();item.remove();update(card)};item.appendChild(b);item.dataset.cut=JSON.stringify(cut);"
            "card.querySelector('.cutlist').appendChild(item);update(card);});});"
            "function update(card){const n=card.querySelectorAll('.cutlist span').length;"
            "card.querySelector('.count').textContent=n+' cuts';try{preview(card)}catch(e){"
            "card.querySelector('.status').textContent='preview failed: '+e.message}}"
            "document.querySelectorAll('.card').forEach(c=>{try{preview(c)}catch(e){}});"
            "function verdict(btn,v){const c=btn.closest('.card');"
            "c.dataset.verdict=(c.dataset.verdict===v?'':v);"
            "c.classList.remove('ok');c.classList.remove('bad');"
            "if(c.dataset.verdict)c.classList.add(c.dataset.verdict);"
            "preview(c);tally();"
            "try{const o={};document.querySelectorAll('.card').forEach(x=>{if(x.dataset.verdict)"
            "o[x.dataset.page+'|'+x.dataset.wid+'|'+x.dataset.run]=x.dataset.verdict});"
            "localStorage.setItem(KEY,JSON.stringify(o))}catch(e){}}"
            "const KEY='letters_label_'+location.pathname.split('/').pop();"
            "function tally(){const t=document.querySelectorAll('.card').length;"
            "const ok=document.querySelectorAll('.card.ok').length;"
            "const bad=document.querySelectorAll('.card.bad').length;"
            "const drawn=[...document.querySelectorAll('.card')].filter(c=>c.querySelector('.cutlist span')).length;"
            "document.getElementById('tally').textContent="
            "ok+' right, '+bad+' wrong, '+drawn+' drawn, of '+t;}"
            "(function(){try{const o=JSON.parse(localStorage.getItem(KEY)||'{}');"
            "document.querySelectorAll('.card').forEach(c=>{"
            "const v=o[c.dataset.page+'|'+c.dataset.wid+'|'+c.dataset.run];"
            "if(v){c.dataset.verdict=v;c.classList.add(v);}});}catch(e){}"
            "document.querySelectorAll('.card').forEach(c=>preview(c));tally();})();"
            "function copyAll(){const out=[];document.querySelectorAll('.card').forEach(c=>{"
            "const cuts=[...c.querySelectorAll('.cutlist span')].map(s=>JSON.parse(s.dataset.cut));"
            "const v=c.dataset.verdict||'';"
            "if(!cuts.length&&!v)return;"
            "const o={page:+c.dataset.page,wid:c.dataset.wid,run:+c.dataset.run,text:c.dataset.text};"
            "if(cuts.length){o.cuts=cuts;const as=assignOf(c);if(as)o.assign=as;}"
            "if(v)o.verdict=(v==='ok'?'right':'wrong');"
            "out.push(o)});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));"
            "alert(out.length+' words copied');}"
            "</script>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d cards" % (a.out, len(cards)))


if __name__ == "__main__":
    main()
