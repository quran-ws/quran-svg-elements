import json, io, html, os, sys
SRC = "/home/abdullah/Dev/github.com/AbdullahObaid/quran-svg-pipeline/docs/defects/reported.json"
d = json.load(io.open(SRC, encoding="utf-8"))
items = d["items"]
ORDER = ["diagnosed, not fixed", "partly fixed", "mostly fixed", "fixed", "answered"]
CLS = {"fixed": "ok", "answered": "info", "mostly fixed": "warn",
       "partly fixed": "warn", "diagnosed, not fixed": "open"}
LABEL = {"fixed": "Fixed", "answered": "Answered", "mostly fixed": "Mostly fixed",
         "partly fixed": "Partly fixed", "diagnosed, not fixed": "Open"}
counts = {}
for i in items:
    counts[i["status"]] = counts.get(i["status"], 0) + 1

def ar(s):
    return '<span class="ar">%s</span>' % html.escape(s)

def wordbits(ws):
    out = []
    for w in ws:
        parts = w.split(" ", 1)
        if len(parts) == 2:
            out.append('<span class="wb"><code>%s</code>%s</span>'
                       % (html.escape(parts[0]), ar(parts[1])))
        else:
            out.append('<span class="wb">%s</span>' % ar(w))
    return "".join(out)

cards = []
for st in ORDER:
    sel = [i for i in items if i["status"] == st]
    if not sel:
        continue
    cards.append('<h2 class="grp"><span class="chip %s">%s</span>'
                 '<span class="gn">%d item%s</span></h2>'
                 % (CLS[st], LABEL[st], len(sel), "" if len(sel) == 1 else "s"))
    for i in sel:
        pg = ('<a class="pg" href="http://127.0.0.1:8777/?page=%d&step=audit&user=abdullah">page %d</a>'
              % (i["page"], i["page"])) if i["page"] else '<span class="pg none">no single page</span>'
        cards.append(
            '<article class="card %s">'
            '<header><span class="num">%02d</span>%s%s</header>'
            '<dl><dt>Reported</dt><dd class="said">%s</dd>'
            '<dt>What it was</dt><dd>%s</dd>'
            '<dt>Where it stands</dt><dd>%s</dd></dl></article>'
            % (CLS[st], i["id"], pg,
               ('<div class="words">%s</div>' % wordbits(i["words"])) if i["words"] else "",
               html.escape(i["reported"]),
               html.escape(i["cause"]),
               html.escape(i["detail"])))

summary = "".join(
    '<div class="sq %s"><b>%d</b><span>%s</span></div>' % (CLS[s], counts[s], LABEL[s])
    for s in ORDER if s in counts)

HTML = """<title>Reported by Eye</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Amiri:wght@400;700&display=swap">
<style>
:root{
  --paper:#f6f4f1;--card:#fffefc;--ink:#1b1a19;--dim:#6f6b66;--faint:#9c968f;
  --rule:#e2ddd6;--rule2:#efebe5;
  --ok:#0e6b74;--ok-bg:#e9f4f4;
  --warn:#a4661a;--warn-bg:#fbf1e4;
  --open:#b02f4c;--open-bg:#fbeef1;
  --info:#4a5568;--info-bg:#eef0f3;
  --shadow:0 1px 2px rgba(27,26,25,.05),0 8px 24px -12px rgba(27,26,25,.16);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#141518;--card:#1c1e22;--ink:#e9e5e0;--dim:#a09a93;--faint:#726d67;
  --rule:#2c2f34;--rule2:#24272b;
  --ok:#5fc9cf;--ok-bg:#132a2c;--warn:#e0a35c;--warn-bg:#2b2115;
  --open:#f2778f;--open-bg:#2c1a20;--info:#a9b4c4;--info-bg:#222630;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);}}
:root[data-theme="dark"]{
  --paper:#141518;--card:#1c1e22;--ink:#e9e5e0;--dim:#a09a93;--faint:#726d67;
  --rule:#2c2f34;--rule2:#24272b;
  --ok:#5fc9cf;--ok-bg:#132a2c;--warn:#e0a35c;--warn-bg:#2b2115;
  --open:#f2778f;--open-bg:#2c1a20;--info:#a9b4c4;--info-bg:#222630;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:400 16px/1.6 "IBM Plex Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:54px 24px 90px}
.eyebrow{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin:0 0 16px}
h1{font:600 clamp(30px,5vw,44px)/1.12 Spectral,Georgia,serif;margin:0 0 16px;
  letter-spacing:-.015em;text-wrap:balance;max-width:18ch}
.lede{font:400 clamp(16px,2vw,19px)/1.55 Spectral,Georgia,serif;color:var(--dim);
  max-width:62ch;margin:0}
.summary{display:flex;flex-wrap:wrap;gap:10px;margin:34px 0 8px}
.sq{flex:1 1 120px;background:var(--card);border:1px solid var(--rule);border-radius:9px;
  padding:14px 16px;display:flex;flex-direction:column;gap:2px;box-shadow:var(--shadow)}
.sq b{font:600 26px/1 "IBM Plex Sans",sans-serif;font-variant-numeric:tabular-nums}
.sq span{font-size:12.5px;color:var(--dim)}
.sq.ok b{color:var(--ok)} .sq.warn b{color:var(--warn)}
.sq.open b{color:var(--open)} .sq.info b{color:var(--info)}
.grp{display:flex;align-items:center;gap:12px;margin:44px 0 16px;
  font:600 15px/1 Spectral,Georgia,serif}
.gn{font:400 13px/1 "IBM Plex Mono",monospace;color:var(--faint)}
.chip{display:inline-block;padding:5px 11px;border-radius:999px;
  font:500 12px/1 "IBM Plex Sans",sans-serif;letter-spacing:.02em}
.chip.ok{background:var(--ok-bg);color:var(--ok)}
.chip.warn{background:var(--warn-bg);color:var(--warn)}
.chip.open{background:var(--open-bg);color:var(--open)}
.chip.info{background:var(--info-bg);color:var(--info)}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;
  padding:18px 22px 8px;margin:0 0 12px;box-shadow:var(--shadow);
  border-left:3px solid var(--rule)}
.card.ok{border-left-color:var(--ok)} .card.warn{border-left-color:var(--warn)}
.card.open{border-left-color:var(--open)} .card.info{border-left-color:var(--info)}
.card header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.num{font:500 12px/1 "IBM Plex Mono",monospace;color:var(--faint);
  border:1px solid var(--rule);border-radius:4px;padding:4px 6px}
.pg{font:500 13px/1 "IBM Plex Sans",sans-serif;color:var(--ink);text-decoration:none;
  border-bottom:1px solid var(--rule)}
.pg:hover{border-bottom-color:currentColor}
.pg.none{color:var(--faint);border:0}
.words{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}
.wb{display:inline-flex;align-items:baseline;gap:6px}
.wb code{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--faint)}
.ar{font-family:Amiri,"Traditional Arabic",serif;font-size:20px;line-height:1.9;direction:rtl}
dl{margin:0;display:grid;grid-template-columns:118px 1fr;gap:2px 16px}
dt{font:500 11px/1.6 "IBM Plex Mono",monospace;letter-spacing:.06em;
  text-transform:uppercase;color:var(--faint);padding:7px 0}
dd{margin:0;padding:7px 0;font-size:14.6px}
dd.said{font-family:Spectral,Georgia,serif;font-size:16px;color:var(--ink)}
dt+dd{border-top:1px solid var(--rule2)}
dl>dt:first-of-type,dl>dt:first-of-type+dd{border-top:0}
dl>dt:not(:first-of-type){border-top:1px solid var(--rule2)}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--rule);
  color:var(--faint);font-size:13.5px;max-width:70ch}
code{font-family:"IBM Plex Mono",monospace;font-size:.88em}
@media (max-width:620px){dl{grid-template-columns:1fr;gap:0}
  dt{padding-bottom:0}dt+dd{border-top:0}dl>dt:not(:first-of-type){border-top:1px solid var(--rule2)}}
</style>
<div class="wrap">
<p class="eyebrow">KFGQPC Madani · human review log</p>
<h1>Everything you caught by eye</h1>
<p class="lede">Twelve things spotted on the review pages that no audit had surfaced, what
each turned out to be, and where it stands. Several were not what they looked like, and
two of them opened up defect families that reach across the whole mushaf.</p>
<div class="summary">__SUMMARY__</div>
__CARDS__
<footer>Kept as data at <code>docs/defects/reported.json</code> so it survives and stays
appendable. Page links open the local review platform. Ordered worst-first: what is still
open sits at the top.</footer>
</div>
"""
out = HTML.replace("__SUMMARY__", summary).replace("__CARDS__", "".join(cards))
open(sys.argv[1], "w", encoding="utf-8").write(out)
print("wrote %s (%.0f KB)" % (sys.argv[1], os.path.getsize(sys.argv[1]) / 1024))
