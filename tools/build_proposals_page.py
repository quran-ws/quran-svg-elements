#!/usr/bin/env python3
"""Render docs/defects/proposals.json as an interactive decision page.

Serve through the review server (http://127.0.0.1:8777/proposals) so each card
can fetch /api/page/N and show the word's actual ink. For every item Abdullah
picks: approve the proposal, pick an alternative, reject, or comment — state
persists in localStorage and the Copy button exports the decisions to paste
back to Claude, where they become data (overrides / labels / policy).

    python3 tools/build_proposals_page.py
"""
import html as _html
import json, os

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "defects", "proposals.json")
OUT = os.path.join(ROOT, "docs", "defects", "proposals.html")


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    cards = []
    for it in data["items"]:
        s, a, w = it["key"].split(":")
        alts = "".join(
            '<label><input type="radio" name="d-%s" value="alt%d"> %s</label>'
            % (it["id"], i, _html.escape(alt))
            for i, alt in enumerate(it.get("alternatives", [])))
        st = it.get("state", "pending")
        badge = ("" if st == "pending" else
                 '<div class="badge b-%s">%s — %s</div>'
                 % (st, st.upper(), _html.escape(it.get("state_note", ""))))
        cards.append(
            '<div class="card st-%s" data-state="%s" data-id="%s" data-page="%d" data-s="%s"'
            ' data-a="%s" data-w="%s" data-fx="%s" data-fy="%s">'
            '%s<h3>%s — <a href="/?page=%d&step=audit&word=%s" target=_blank>'
            'p%d %s</a></h3>'
            '<div class="ink"><span class="wait">…</span></div>'
            '%s'
            '<p class="ev">%s</p>'
            '<p class="prop"><b>Proposal:</b> %s</p>'
            '<div class="choices">'
            '<label><input type="radio" name="d-%s" value="approve">'
            ' ✓ approve the proposal</label>%s'
            '<label><input type="radio" name="d-%s" value="reject">'
            ' ✗ reject — leave as is</label>'
            '</div>'
            '<textarea class="note" dir="auto" placeholder="comment…"></textarea>'
            '</div>'
            % (st, st, it["id"], it["page"], s, a, w,
               it.get("focus_x") if it.get("focus_x") is not None else "",
               it.get("focus_y") if it.get("focus_y") is not None else "", badge,
               _html.escape(it["title"]), it["page"], it["key"], it["page"],
               it["key"],
               ('<p class="fx"><b>Found:</b> %s<br><b>Expected:</b> %s</p>'
                % (_html.escape(it["found"]), _html.escape(it["expected"]))
                if it.get("found") else ""),
               "" if it.get("found") else _html.escape(it["evidence"]),
               _html.escape(it["proposal"]), it["id"], alts, it["id"]))
    doc = _TMPL.replace("__CARDS__", "\n".join(cards)) \
               .replace("__N__", str(len(data["items"])))
    open(OUT, "w", encoding="utf-8").write(doc)
    print("wrote %s (%d items) — open http://127.0.0.1:8777/proposals"
          % (OUT, len(data["items"])))


_TMPL = r"""<!doctype html><html><head><meta charset="utf-8">
<title>proposals — decisions needed</title><style>
@font-face{font-family:"QPC Hafs";src:url("/assets/UthmanicHafs_V22.ttf");font-display:swap}
body{font:14px system-ui;margin:0;background:#f7f5ef;color:#231f20}
header{position:sticky;top:0;background:#fffdf8;border-bottom:1px solid #ddd7c6;
  padding:10px 18px;display:flex;gap:16px;align-items:center;z-index:5}
header h1{font-size:16px;margin:0}
header button{font:inherit;padding:6px 14px;border:1px solid #999;border-radius:6px;
  background:#fff;cursor:pointer}
header button:hover{border-color:#245a9e;color:#245a9e}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));
  gap:14px;padding:16px}
.card{border:1px solid #ddd7c6;border-radius:8px;background:#fff;padding:12px 14px}
.card.decided{box-shadow:0 0 0 2px #245a9e;border-color:#245a9e}
.badge{font-size:12px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:6px}
.b-done{background:#e2f2e6;color:#1a7a3a}.b-superseded{background:#eee;color:#666}
.b-partial{background:#fdf3dd;color:#8a6d00}
.card.st-done,.card.st-superseded{opacity:.6}
.card h3{margin:0 0 6px;font-size:14.5px}
.card h3 a{color:#245a9e}
.ink{min-height:90px;display:flex;align-items:center;justify-content:center;
  background:#fffdf8;border-radius:4px;margin-bottom:6px}
.ink svg{max-width:100%;max-height:120px}
.wait{color:#8a8577}
.fx{font-size:14px;background:#fbf9f2;padding:8px 10px;border-radius:4px}
.fx b{color:#245a9e}
.ev{font-size:13px;color:#555;margin:6px 0}
.prop{font-size:13.5px;margin:6px 0}
.choices{display:flex;flex-direction:column;gap:4px;font-size:13px;margin:8px 0}
.note{width:100%;box-sizing:border-box;border:1px solid #e4dfd2;border-radius:4px;
  font:12.5px system-ui;padding:4px 6px;min-height:26px;background:#fffdf8}
</style></head><body>
<header><h1>Decisions needed</h1>
<span><b id="ndec">0</b>/__N__ decided</span>
<button id="copyBtn">Copy decisions</button>
</header>
<div class="grid" id="grid">__CARDS__</div>
<script>
const cards = [...document.querySelectorAll(".card")];
const KEY = "proposal-decisions";
let dec = JSON.parse(localStorage.getItem(KEY) || "{}");
// a resolved card's old decision/comment is history — drop it automatically
cards.forEach(c => {
  if (c.dataset.state === "done" || c.dataset.state === "superseded")
    delete dec[c.dataset.id];
});
localStorage.setItem(KEY, JSON.stringify(dec));
function sync(){
  cards.forEach(c => {
    const d = dec[c.dataset.id];
    c.classList.toggle("decided", !!(d && (d.choice || (d.note||"").trim())));
    if (d && d.choice) {
      const r = c.querySelector(`input[value="${d.choice}"]`);
      if (r) r.checked = true;
    }
    // never rewrite a focused textarea (it eats the space you just typed)
    const ta = c.querySelector(".note");
    if (d && d.note !== undefined && document.activeElement !== ta)
      ta.value = d.note;
  });
  document.getElementById("ndec").textContent =
    Object.values(dec).filter(d => d.choice || (d.note||"").trim()).length;
  localStorage.setItem(KEY, JSON.stringify(dec));
}
cards.forEach(c => {
  const id = c.dataset.id;
  c.querySelectorAll("input[type=radio]").forEach(r =>
    r.addEventListener("change", () => {
      dec[id] = dec[id] || {};
      dec[id].choice = r.value;
      dec[id].label = r.parentElement.textContent.trim();
      sync();
    }));
  c.querySelector(".note").addEventListener("input", e => {
    dec[id] = dec[id] || {};
    dec[id].note = e.target.value;   // trim only at copy time
    sync();
  });
});
document.getElementById("copyBtn").onclick = () => {
  const out = cards.map(c => {
    const d = dec[c.dataset.id];
    if (!d || (!d.choice && !d.note)) return null;
    return {id: c.dataset.id, page: +c.dataset.page,
            key: `${c.dataset.s}:${c.dataset.a}:${c.dataset.w}`,
            decision: d.label || d.choice || "", note: d.note || ""};
  }).filter(Boolean);
  navigator.clipboard.writeText(JSON.stringify(out, null, 1));
};
sync();
/* ink previews — same machinery as the confidence page */
const pageCache = new Map();
function pageHolder(pg){
  if (!pageCache.has(pg))
    pageCache.set(pg, fetch("/api/page/" + pg).then(r => r.json()).then(d => {
      const h = document.createElement("div");
      h.style.cssText = "position:absolute;left:-100000px;top:0;width:900px";
      document.body.appendChild(h); h.innerHTML = d.svg; return h;
    }));
  return pageCache.get(pg);
}
const NS = "http://www.w3.org/2000/svg";
async function renderInk(c){
  const holder = await pageHolder(+c.dataset.page);
  const svg = holder.querySelector("svg");
  const sel = `g.word[data-surah="${c.dataset.s}"][data-ayah="${c.dataset.a}"]` +
              `[data-word="${c.dataset.w}"]`;
  const gs = [...svg.querySelectorAll(sel)];
  const box = c.querySelector(".ink");
  if (!gs.length) { box.innerHTML = "<span class=wait>not in build</span>"; return; }
  let X1=1e9,Y1=1e9,X2=-1e9,Y2=-1e9; const clones=[];
  for (const g of gs) {
    let bb; try { bb = g.getBBox(); } catch(e){ continue; }
    const m = g.getCTM();
    for (const [px,py] of [[bb.x,bb.y],[bb.x+bb.width,bb.y],
                           [bb.x,bb.y+bb.height],[bb.x+bb.width,bb.y+bb.height]]) {
      const x = m.a*px+m.c*py+m.e, y = m.b*px+m.d*py+m.f;
      X1=Math.min(X1,x); Y1=Math.min(Y1,y); X2=Math.max(X2,x); Y2=Math.max(Y2,y);
    }
    const wrap = document.createElementNS(NS,"g");
    wrap.setAttribute("transform",`matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
    wrap.appendChild(g.cloneNode(true)); clones.push(wrap);
  }
  // highlight the problem element in RED, wherever it lives on the page
  let fx = parseFloat(c.dataset.fx), fy = parseFloat(c.dataset.fy);
  if (!isNaN(fx) && !isNaN(fy)) {
    // focus coords are PAGE units; getCTM maps to viewport px — rescale
    const vb = svg.viewBox.baseVal;
    const sc = (svg.clientWidth || 900) / (vb && vb.width || 345);
    fx = (fx - (vb ? vb.x : 0)) * sc;
    fy = (fy - (vb ? vb.y : 0)) * sc;
    const tol = 1.8 * sc, toly = 3 * sc;
    // one-time geometry index per page (avoids re-walking every path per card)
    if (!holder._idx) {
      holder._idx = [];
      for (const p of svg.querySelectorAll("g.word path")) {
        let bb; try { bb = p.getBBox(); } catch(e){ continue; }
        const m = p.getCTM();
        holder._idx.push({p, bb, m,
          cx: m.a*bb.x + m.c*bb.y + m.e,
          cy: m.b*bb.x + m.d*bb.y + m.f,
          cy2: m.b*bb.x + m.d*(bb.y+bb.height) + m.f});
      }
    }
    for (const it of holder._idx) {
      const {p, bb, m, cx, cy, cy2} = it;
      if (Math.abs(cx - fx) < tol &&
          (Math.abs(cy - fy) < toly || Math.abs(cy2 - fy) < toly)) {
        const wrap = document.createElementNS(NS,"g");
        wrap.setAttribute("transform",`matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
        const cl = p.cloneNode(true); cl.setAttribute("fill", "#b3261e");
        wrap.appendChild(cl); clones.push(wrap);
        for (const [px,py] of [[bb.x,bb.y],[bb.x+bb.width,bb.y+bb.height]]) {
          const x = m.a*px+m.c*py+m.e, y = m.b*px+m.d*py+m.f;
          X1=Math.min(X1,x-3); Y1=Math.min(Y1,y-3);
          X2=Math.max(X2,x+3); Y2=Math.max(Y2,y+3);
        }
        break;
      }
    }
  }
  const mini = document.createElementNS(NS,"svg");
  mini.setAttribute("viewBox",`${X1-4} ${Y1-4} ${X2-X1+8} ${Y2-Y1+8}`);
  clones.forEach(cl => mini.appendChild(cl));
  box.innerHTML = ""; box.appendChild(mini);
}
const io = new IntersectionObserver(es => {
  for (const en of es) if (en.isIntersecting) {
    io.unobserve(en.target);
    renderInk(en.target).catch(e => {
      en.target.querySelector(".ink").innerHTML =
        "<span class=wait>preview failed — use the p-link above</span>";
    });
  }
}, {rootMargin: "300px"});
cards.forEach(c => io.observe(c));
</script></body></html>
"""

if __name__ == "__main__":
    main()
