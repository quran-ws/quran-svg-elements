"""Render each stray mark over the real artwork so a person can judge the move."""
import sys, os, io, re, json, contextlib, importlib.util
ROOT = os.environ["QSVG_ROOT"]
sp = importlib.util.spec_from_file_location("assign_words", os.path.join(ROOT,"tools","assign_words.py"))
aw = importlib.util.module_from_spec(sp); sys.modules["assign_words"] = aw; sp.loader.exec_module(aw)
CAP = {}; _o = aw.rewrite
aw.rewrite = lambda p, a: (CAP.__setitem__("a", a), _o(p, a))[1]
GAP, REACH = 60.0, 20.0

def artwork(pg, keep=None):
    """The page as one grey backdrop, trimmed to the lines actually in view.

    The artwork holds one compound <path> per line, so dropping the lines outside the
    crop is exact — nothing that could be drawn in the visible band is thrown away —
    and it takes the page from ~700 KB to the two or three lines the reader is looking
    at, which is what keeps seventeen of these on one page."""
    s = io.open(os.path.join(ROOT, "mushafs/hafs/kfqc/svg/%03d.svg" % pg),
                encoding="utf-8").read()
    m = re.search(r"<svg\b([^>]*)>", s)
    vb = re.search(r'viewBox="([^"]*)"', m.group(1))
    body = s[m.end():s.rindex("</svg>")]
    if keep:
        # `data-line` sits on the <g class="line"> wrapper, not the paths. Walk the
        # tag stream and copy through only the wrappers we want; a line group's
        # contents are self-contained, so dropping one is exact.
        out, depth, skip = [], 0, None
        for tok in re.split(r'(<[^>]*>)', body):
            if tok.startswith("<") and not tok.startswith("</"):
                mm = re.match(r'<g\b[^>]*class="line"[^>]*data-line="(\d+)"', tok)
                if mm and skip is None and int(mm.group(1)) not in keep:
                    skip, depth = 0, 0
                if skip is not None:
                    if not tok.endswith("/>"):
                        depth += 1
                    continue
            elif tok.startswith("</") and skip is not None:
                depth -= 1
                if depth <= 0:
                    skip = None
                continue
            if skip is None:
                out.append(tok)
        body = "".join(out)
    body = re.sub(r'fill="[^"]*"', 'fill="#cfcac4"', body)
    body = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", body)
    return (vb.group(1) if vb else "0 0 345 550"), body

def cases(pg):
    os.environ["QSVG_STRAY"] = "0"
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    R = []
    for w, at in CAP["a"]:
        if not w: continue
        els = [e for a in at for e in a["els"]]
        b = [e for e in els if e["kind"] == "body"]
        if not b: continue
        ln = [e.get("line") for e in b if e.get("line")]
        R.append({"w": w, "els": els, "b": b,
                  "ln": max(set(ln), key=ln.count) if ln else 0,
                  "k": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])})
    def ovl(bs, e):
        return max(min(x["x2"], e["x2"]) - max(x["x1"], e["x1"]) for x in bs)
    byln = {}
    for r in R: byln.setdefault(r["ln"], []).append(r)
    out = []
    for r in R:
        for e in r["els"]:
            if e["kind"] == "body" or e.get("mkpart"): continue
            if ovl(r["b"], e) > -GAP: continue
            cands = [t for t in byln.get(e.get("line") or r["ln"], ()) if t is not r]
            if not cands: continue
            t = max(cands, key=lambda x: ovl(x["b"], e))
            out.append({
                "page": pg, "mark": e.get("mark") or e["kind"],
                "gap": round(-ovl(r["b"], e), 1),
                "reachable": ovl(t["b"], e) >= -REACH,
                "e": [e["x1"], e["y1"], e["x2"], e["y2"]],
                "holder": {"k": r["k"], "t": r["w"]["rasm_uthmani"], "ln": r["ln"],
                           "box": [min(x["x1"] for x in r["b"]), min(x["y1"] for x in r["b"]),
                                   max(x["x2"] for x in r["b"]), max(x["y2"] for x in r["b"])]},
                "target": {"k": t["k"], "t": t["w"]["rasm_uthmani"], "ln": t["ln"],
                           "box": [min(x["x1"] for x in t["b"]), min(x["y1"] for x in t["b"]),
                                   max(x["x2"] for x in t["b"]), max(x["y2"] for x in t["b"])]}})
    return out

def panel(pg, cs, vb, body):
    x1 = min([c["e"][0] for c in cs] + [c["holder"]["box"][0] for c in cs] + [c["target"]["box"][0] for c in cs])
    y1 = min([c["e"][1] for c in cs] + [c["holder"]["box"][1] for c in cs] + [c["target"]["box"][1] for c in cs])
    x2 = max([c["e"][2] for c in cs] + [c["holder"]["box"][2] for c in cs] + [c["target"]["box"][2] for c in cs])
    y2 = max([c["e"][3] for c in cs] + [c["holder"]["box"][3] for c in cs] + [c["target"]["box"][3] for c in cs])
    px, py = 8, 10
    vbc = "%.1f %.1f %.1f %.1f" % (x1 - px, y1 - py, (x2 - x1) + 2 * px, (y2 - y1) + 2 * py)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s" class="pv">' % vbc, body]
    for c in cs:
        hb, tb, e = c["holder"]["box"], c["target"]["box"], c["e"]
        ex, ey = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="hold"/>'
                 % (hb[0], hb[1], hb[2] - hb[0], hb[3] - hb[1]))
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="tgt"/>'
                 % (tb[0], tb[1], tb[2] - tb[0], tb[3] - tb[1]))
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="wrong"/>'
                 % (ex, ey, (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2))
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="right"/>'
                 % (ex, ey, (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2))
        o.append('<circle cx="%.1f" cy="%.1f" r="6" class="mk"/>' % (ex, ey))
    o.append("</svg>")
    return "".join(o)

if __name__ == "__main__":
    pages = [int(x) for x in sys.argv[1].split(",")]
    all_c = {}
    for pg in pages:
        cs = cases(pg)
        if cs: all_c[pg] = cs
    json.dump({str(k): v for k, v in all_c.items()}, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    panels = {}
    for pg, cs in all_c.items():
        keep = set()
        for c in cs:
            keep |= {c["holder"]["ln"], c["target"]["ln"],
                     c["holder"]["ln"] - 1, c["holder"]["ln"] + 1}
        vb, body = artwork(pg, keep)
        panels[pg] = panel(pg, cs, vb, body)
    json.dump({str(k): v for k, v in panels.items()}, open(sys.argv[3], "w"), ensure_ascii=False)
    print("cases on %d pages: %d" % (len(all_c), sum(len(v) for v in all_c.values())))
    for pg, cs in sorted(all_c.items()):
        for c in cs:
            print("   p%-4d %-10s %-6.1fu  %-11s %-14s -> %-11s %-14s %s"
                  % (pg, c["mark"], c["gap"], c["holder"]["k"], c["holder"]["t"],
                     c["target"]["k"], c["target"]["t"],
                     "" if c["reachable"] else "(NOT under the target)"))
