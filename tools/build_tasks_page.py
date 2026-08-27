#!/usr/bin/env python3
"""One page with ONLY what needs Abdullah's action, in simple words.

Merges the confidence board (open cards needing an eye) and the proposals
page (pending decisions) into docs/defects/tasks.html. Each row: the word,
one plain-language task, one link to the right place to do it.

    python3 tools/build_tasks_page.py
"""
import glob, html, json, os

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def simple_task(r):
    m = list(r.get("metrics", {}))
    txt = " ".join(m)
    if any("RE-REVIEW" in k for k in m):
        return "This word changed after your last review. Look again: OK now?"
    if any("REOPENED" in k for k in m):
        return "You said this is still broken. Check the fresh build: fixed now?"
    if r.get("proofs"):
        return "Certain defect. Look at the red mark: which word owns it?"
    if "width" in txt:
        return "Word looks too wide or too narrow. Did it take ink from a neighbour?"
    if "pair" in txt or "deficit" in txt or "surplus" in txt:
        return "A mark may belong to the word next to it. Which word owns it?"
    return "Check this word: is anything extra, missing, or misnamed?"


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, ".cache", "confidence",
                                           "pages", "*.json"))):
        d = json.load(open(f))
        for r in d.get("words", []):
            t = r.get("tier")
            stale = r.get("human_stale")
            if t in ("certain", "high") and not r.get("human") or stale:
                rows.append((0 if t == "certain" else (1 if stale else 2),
                             d["page"], r["key"], r.get("text", ""),
                             simple_task(r)))
    pj = os.path.join(ROOT, "docs", "defects", "proposals.json")
    if os.path.exists(pj):
        d = json.load(open(pj, encoding="utf-8"))
        items = d.get("items", [])
        decided = set(d.get("decisions", {}) or {})
        for p in items:
            st = (p.get("state") or "").lower()
            if st in ("done", "superseded", "rejected", "applied", "resolved"):
                continue
            if str(p.get("id")) in decided or p.get("decision"):
                continue
            rows.append((3, p.get("page", 0), p.get("id", "?"), p.get("title", "")[:40],
                         "Decide this proposal: " + (p.get("ask") or p.get("summary")
                                                     or p.get("title") or "")[:120]))
    # standing manual tasks that live outside the two boards
    rows.append((4, 0, "labels", "61 shapes",
                 "Name each shape on the label sheet (hamza sections)."))
    rows.append((4, 27, "2:181", "بَعْدَ مَا",
                 "One glance: are the two words on the right lines? (line 15)"))
    rows.append((4, 177, "8:6", "بَعْدَ مَا",
                 "One glance: are the two words on the right lines? (line 12)"))
    rows.sort()
    order = {0: "CERTAIN — do these first", 1: "CHANGED — review again",
             2: "LIKELY — one look each", 3: "DECISIONS",
             4: "QUICK CHECKS"}
    out = ["""<!doctype html><html dir="ltr"><head><meta charset="utf-8">
<title>Your tasks</title><style>
body{font-family:system-ui;margin:20px auto;max-width:900px;background:#fafafa}
h1{font-size:22px} h2{font-size:16px;margin:26px 0 8px;color:#444}
.row{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 14px;
margin:6px 0;display:flex;gap:14px;align-items:center}
.w{font-size:22px;font-family:'KFGQPC Uthmanic Script HAFS',serif;min-width:130px;text-align:center}
.t{flex:1;font-size:14px;color:#222}
a.go{background:#2563eb;color:#fff;padding:6px 14px;border-radius:6px;
text-decoration:none;font-size:13px;white-space:nowrap}
.k{color:#888;font-size:12px}</style></head><body>
<h1>Your tasks</h1>
<p>One row = one look. Click GO, judge the word, come back.</p>"""]
    cur = None
    for grp, pg, key, text, task in rows:
        if grp != cur:
            out.append("<h2>%s (%d)</h2>" % (order[grp],
                       sum(1 for g, *_ in rows if g == grp)))
            cur = grp
        if grp == 3:
            link = "/proposals"
        elif grp == 4:
            link = ("/docs/defects/label_sheet.html" if key == "labels"
                    else "/?page=%d&step=audit&user=abdullah" % pg)
        else:
            link = "/confidence?focus=%s" % key
        out.append(
            '<div class="row"><div class="w">%s<div class="k">p%s · %s</div></div>'
            '<div class="t">%s</div><a class="go" href="%s">GO</a></div>'
            % (html.escape(str(text)), pg, html.escape(str(key)),
               html.escape(task), html.escape(link)))
    out.append("</body></html>")
    p = os.path.join(ROOT, "docs", "defects", "tasks.html")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s (%d tasks) — open http://127.0.0.1:8777/docs/defects/tasks.html"
          % (p, len(rows)))


if __name__ == "__main__":
    main()
