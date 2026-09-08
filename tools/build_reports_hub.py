#!/usr/bin/env python3
"""One-page reports hub: every defect report + evidence image inline.

Writes docs/defects/index.html; the review server serves it at
/docs/defects/ (append ?list=1 for the raw file listing).
    python3 tools/build_reports_hub.py
"""
import glob, html, json, os, re

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs", "defects")


PLAIN = {
 "waqf_dammah_report": ("Fixed: all 11 waqf signs you flagged (they were drawn "
   "but held by the wrong word or counted as letters) and 3 missing dammahs. "
   "Also lists 7 words we could NOT fix safely, each with the reason."),
 "compound_sajdah_report": ("Fixed: p254's بعد ما (the two-part word that broke "
   "its whole line) and the sajdah signs (checked all 15; fixed 2)."),
 "lsolve_report": ("The new solver that moves each mark back to the word it is "
   "drawn over, whole line at a time. Fixed p350, p371, p599 and more. "
   "3 cases need your eye — listed at the end."),
 "bodyfix_report": ("The 5 word-theft repairs you approved (p341 chain, p59, "
   "p535, p437, p596). Before/after pictures are at the bottom of this page."),
 "visual_labels_report": ("An agent looked at every unnamed mark shape (332) "
   "and named 271 safely. 61 need YOU: mostly hamzah shapes only a human may "
   "call. Sections B and C are your list."),
 "marktype_verification": ("A second agent double-checked the rules agent. "
   "It confirmed the detections but caught one WRONG fix before it shipped "
   "(it would have turned ~900 letters into marks silently)."),
 "marktype_rules": ("The measured rules for what each mark family may look "
   "like (position, size, pairs). Technical reference."),
 "xband_proposals": ("The cross-line steal fixes: which marks were returned "
   "to the word above/below, and which cases were refused and why."),
 "iqlab_notation": ("Why this print writes iqlab as ONE stroke + small م, "
   "and everything in the code that had to learn that."),
 "manual_review": ("Older manual review notes."),
}

ORDER = ["waqf_dammah_report", "compound_sajdah_report", "lsolve_report",
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
        plain = PLAIN.get(name, "")
        secs.append('<section id="%s"><h1>%s</h1>'
                    '<p class="plain">%s</p>'
                    '<details><summary>full technical report</summary>%s</details>'
                    '</section>'
                    % (name, name.replace("_", " "), html.escape(plain),
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
.plain{font-size:16px;background:#fffdf8;border-left:4px solid #245a9e;
 padding:10px 14px;max-width:70ch}
details summary{cursor:pointer;color:#245a9e;font-size:13.5px;margin:8px 0}
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
<a href="?list=1">raw files</a><br>%s</header><main>
<section><h1>what you need to do</h1><ol style="font-size:16px;line-height:2">
<li><a href="/proposals">Proposals page</a> — 6 pending cards. Pick an answer on each, press Copy, paste to Claude.</li>
<li><a href="/confidence">Confidence page</a> — filter "certain" (16 cards): mark each ✓ real or ✗ not.</li>
<li>Same page, filter "fixed" (green cards): quick glance that the repairs look right.</li>
<li>Below on THIS page: "visual labels report" sections B and C — the hamzah shapes only you can name.</li>
</ol></section>%s</main></body></html>""" % (
        head, nav, "\n".join(secs))
    out = os.path.join(D, "index.html")
    open(out, "w", encoding="utf-8").write(doc)
    print("wrote %s (%d sections) — http://127.0.0.1:8777/docs/defects/"
          % (out, len(secs)))


if __name__ == "__main__":
    main()
