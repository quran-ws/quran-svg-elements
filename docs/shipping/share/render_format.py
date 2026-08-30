#!/usr/bin/env python3
"""Render FORMAT.md to a standalone HTML page for the share.

GitHub Pages renders a repository's Markdown for us; a plain folder on the
network does not, so the share carries its own copy. The heading ids are the
GitHub-style slugs, because the demo's 19 documentation links already point at
those anchors — change the slug rule and every one of them breaks.

    render_format.py FORMAT.md FORMAT.html
"""
import html
import re
import sys

from markdown_it import MarkdownIt


def slug(text):
    """GitHub's heading slug: strip tags, lowercase, drop punctuation, hyphenate.

    Arabic is kept — several headings carry it, and dropping it would collide
    two sections onto the same empty anchor.
    """
    t = re.sub(r"<[^>]+>", "", text).lower().strip()
    t = re.sub(r"[^\w\s؀-ۿ-]", "", t)
    return re.sub(r"\s+", "-", t)


CSS = """
 :root{--ink:#231f20;--paper:#fbf9f4;--rule:#ddd8cc;--accent:#8a6d3b}
 @media(prefers-color-scheme:dark){
   :root{--ink:#e8e4da;--paper:#14161b;--rule:#2c313a;--accent:#c8a25a}}
 body{background:var(--paper);color:var(--ink);margin:0;
      font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
 main{max-width:56rem;margin:0 auto;padding:2rem 1.25rem 6rem}
 h1,h2,h3,h4{line-height:1.25;margin:2.2em 0 .6em;scroll-margin-top:1rem}
 h1{font-size:1.9rem}
 h2{font-size:1.45rem;border-bottom:1px solid var(--rule);padding-bottom:.3em}
 code,pre{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
 code{background:rgba(128,128,128,.14);padding:.12em .35em;border-radius:3px;font-size:.9em}
 pre{background:rgba(128,128,128,.1);padding:1rem;border-radius:6px;overflow-x:auto}
 pre code{background:none;padding:0}
 table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;margin:1rem 0}
 th,td{border:1px solid var(--rule);padding:.45rem .6rem;text-align:left;vertical-align:top}
 th{background:rgba(128,128,128,.1)}
 blockquote{border-left:3px solid var(--accent);margin:1rem 0;padding:.2rem 0 .2rem 1rem;opacity:.9}
 a{color:var(--accent)}
 :lang(ar),[dir=rtl]{direction:rtl;text-align:right}
"""


def render(md_path, out_path):
    src = open(md_path, encoding="utf-8").read()
    md = MarkdownIt("commonmark", {"html": True}).enable("table").enable("strikethrough")
    body = md.render(src)
    body = re.sub(r"<h([1-6])>(.*?)</h\1>",
                  lambda m: '<h%s id="%s">%s</h%s>' % (m.group(1), slug(m.group(2)),
                                                       m.group(2), m.group(1)),
                  body, flags=re.S)
    title = "FORMAT — the Madinah Mushaf SVG specification"
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>%s</title>\n<style>%s</style></head><body><main>\n%s\n"
            "</main></body></html>\n" % (html.escape(title), CSS, body))
    open(out_path, "w", encoding="utf-8").write(page)
    print("  FORMAT.html: %d KiB" % (len(page.encode("utf-8")) // 1024))


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
