#!/usr/bin/env python3
"""One-page reports hub: every defect report + evidence image inline.

Writes docs/defects/index.html; the review server serves it at
/docs/defects/ (append ?list=1 for the raw file listing).
    python3 tools/build_reports_hub.py
"""
import glob, html, json, os, re

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs", "defects")

ORDER = ["pause_damma_report", "compound_sajdah_report", "lsolve_report",
         "bodyfix_report", "visual_labels_report", "marktype_verification",
         "marktype_rules", "xband_proposals", "iqlab_notation", "manual_review"]


def md2html(text):
    out, in_code, in_table, in_list = [], False, False, False
    def close():
        nonlocal in_table, in_list
        if in_table:
            out.append("</table></div>")
            in_table = False
        if in_list:
            out.append("</ul>")
            in_list = False
    for ln in text.split("\n"):
        if ln.strip().startswith("```"):
            close()
            out.append("<pre>" if not in_code else "</pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(ln))
            continue
        e = html.escape(ln)
        e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
        e = re.sub(r"`([^`]+)`", r"<code>\1</code>", e)
        if ln.startswith("|"):
            if not in_table:
                close()
                out.append('<div class="tw"><table>')
                in_table = True
            if set(ln.replace("|", "").strip()) <= set("-: "):
                continue
            cells = [c.strip() for c in e.strip().strip("|").split("|")]
            out.append("<tr>" + "".join("<td>%s</td>" % c for c in cells) + "</tr>")
            continue
        close_needed = True
        m = re.match(r"(#{1,4}) (.*)", e)
        if m:
            close()
            n = len(m.group(1)) + 1
            out.append("<h%d>%s</h%d>" % (n, m.group(2), n))
        elif ln.lstrip().startswith(("- ", "* ")):
            if not in_table:
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append("<li>%s</li>" % e.lstrip()[2:])
                close_needed = False
        elif ln.strip():
            close()
            out.append("<p>%s</p>" % e)
        if ln.lstrip().startswith(("- ", "* ")) is False and close_needed and not ln.strip():
            close()
    close()
    return "\n".join(out)


def main():
    secs = []
    # header numbers from the confidence data
    try:
        from collections import Counter
        t = Counter()
        for f in glob.glob(os.path.join(ROOT, ".cache", "confidence", "pages", "*.json")):
            for w in json.load(open(f))["words"]:
                t[w["tier"]] += 1
        head = ("certain %d · high %d · review %d · fixed-cards %d" %
                (t["certain"], t["high"], t["review"], t.get("fixed", 0)))
    except Exception:
        head = ""
    nav = " · ".join('<a href="#%s">%s</a>' % (n, n.replace("_", " "))
                     for n in ORDER if os.path.exists(os.path.join(D, n + ".md")))
    for name in ORDER:
        p = os.path.join(D, name + ".md")
        if not os.path.exists(p):
            continue
        secs.append('<section id="%s"><h1>%s</h1>%s</section>'
                    % (name, name.replace("_", " "),
                       md2html(open(p, encoding="utf-8").read())))
    # evidence galleries
    for sub in sorted(glob.glob(os.path.join(D, "*"))):
        if not os.path.isdir(sub):
            continue
        pngs = sorted(glob.glob(os.path.join(sub, "**", "*.png"), recursive=True))
        if not pngs:
            continue
        rel = os.path.basename(sub)
        imgs = "".join(
            '<figure><img loading="lazy" src="/docs/defects/%s/%s">'
            "<figcaption>%s</figcaption></figure>"
            % (rel, os.path.relpath(f, sub), os.path.relpath(f, sub))
            for f in pngs[:80])
        secs.append('<section id="%s"><h1>%s (%d images)</h1>'
                    '<div class="gal">%s</div></section>' % (rel, rel, len(pngs), imgs))
    doc = """<!doctype html><html><head><meta charset="utf-8">
<title>defect reports</title><style>
body{font:15px/1.6 system-ui;margin:0;color:#231f20;background:#f7f5ef}
header{position:sticky;top:0;background:#fffdf8;border-bottom:1px solid #ddd7c6;
 padding:10px 22px;z-index:5}
header a{color:#245a9e;text-decoration:none;margin-right:2px}
main{max-width:1000px;margin:0 auto;padding:10px 22px 80px}
section{border-bottom:2px solid #ddd7c6;padding:14px 0 26px}
h1{font-size:22px} h2{font-size:18px} h3{font-size:16px}
.tw{overflow-x:auto} table{border-collapse:collapse;font-size:13.5px}
td{border:1px solid #e0dccc;padding:4px 9px;vertical-align:top}
pre{background:#f0eee5;padding:10px;overflow-x:auto;font-size:12.5px}
code{background:#f0eee5;padding:1px 4px;border-radius:3px}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.gal img{max-width:100%%;background:#fff;border:1px solid #ddd}
figcaption{font-size:11.5px;color:#6c675d}
</style></head><body>
<header><b>All defect reports</b> — %s ·
<a href="/confidence">confidence</a> · <a href="/proposals">proposals</a> ·
<a href="?list=1">raw files</a><br>%s</header><main>%s</main></body></html>""" % (
        head, nav, "\n".join(secs))
    out = os.path.join(D, "index.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("wrote %s (%d sections) — http://127.0.0.1:8777/docs/defects/"
          % (out, len(secs)))


if __name__ == "__main__":
    main()
