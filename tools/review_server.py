#!/usr/bin/env python3
"""Local review platform server for the quran-svg semantic layer.

Serves the review frontend (tools/review-platform/index.html), annotated page
SVGs from .cache/words-svg/<edition>/ (generating missing pages lazily via
tools/assign_words.py) and a small JSON API.  All review state lives under
.cache/review/ as append-only JSONL files; nothing here touches the source
SVGs or the pipeline.

Usage:  python3 tools/review_server.py [--port 8777] [--edition hafs/kfqc]
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PLATFORM = os.path.join(TOOLS, "review-platform")
REVIEW_DIR = os.path.join(ROOT, ".cache", "review")
EDITS_PATH = os.path.join(REVIEW_DIR, "edits.jsonl")
DECISIONS_PATH = os.path.join(REVIEW_DIR, "decisions.jsonl")
STATUS_PATH = os.path.join(REVIEW_DIR, "status.json")

EDITION = "hafs/kfqc"
NUM_PAGES = 604
SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)
ET.register_namespace("ayah", "https://quranpedia.net")

_lock = threading.Lock()          # serializes writes to review files
_gen_lock = threading.Lock()      # serializes lazy SVG generation

EDIT_KINDS = {"move-element", "relabel-mark", "label-unlabeled",
              "merge-words", "split-word", "note"}
REVIEW_ACTIONS = {"approve", "reject", "amend"}


# ---------------------------------------------------------------- data access

def load_known_labels():
    """Read the KNOWN label list out of tools/cluster_marks.py (source of truth)."""
    src = open(os.path.join(TOOLS, "cluster_marks.py"), encoding="utf-8").read()
    m = re.search(r"KNOWN\s*=\s*(\[.*?\])", src, re.S)
    if not m:
        raise RuntimeError("KNOWN list not found in cluster_marks.py")
    return ast.literal_eval(m.group(1))


KNOWN_LABELS = load_known_labels()


def edition_dir():
    return os.path.join(ROOT, ".cache", "words-svg", EDITION.replace("/", "-"))


def page_paths(page):
    d = edition_dir()
    return (os.path.join(d, "%03d.svg" % page),
            os.path.join(d, "%03d.report.json" % page))


def ensure_page(page):
    """Lazily generate the annotated SVG for a page if it is missing."""
    svg_path, rep_path = page_paths(page)
    if os.path.exists(svg_path) and os.path.exists(rep_path):
        return svg_path, rep_path
    with _gen_lock:
        if not (os.path.exists(svg_path) and os.path.exists(rep_path)):
            subprocess.run(
                [sys.executable, os.path.join(TOOLS, "assign_words.py"),
                 EDITION, str(page)],
                cwd=ROOT, check=True, capture_output=True, timeout=300)
    return svg_path, rep_path


def clear_cache(page=None):
    """Drop generated page SVGs so the next request rebuilds them.

    Every pipeline change leaves this cache holding the previous build, and the server
    hands it out unchanged — which reads as "your fix did nothing", or worse, as a
    regression that was really a stale file. `ensure_page` regenerates through a
    subprocess, so deleting the files is the whole of it; nothing in this process needs
    reloading.

    Only the two names this server generates are removed, and only from the edition
    directory, so a stray file someone put there is left alone.
    """
    d = edition_dir()
    if not os.path.isdir(d):
        return 0
    pages = [page] if page else range(1, NUM_PAGES + 1)
    n = 0
    with _gen_lock:
        for pg in pages:
            for name in ("%03d.svg" % pg, "%03d.report.json" % pg):
                f = os.path.join(d, name)
                if os.path.exists(f):
                    try:
                        os.remove(f)
                        n += 1
                    except OSError:
                        pass
    return n


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def append_jsonl(path, record):
    os.makedirs(REVIEW_DIR, exist_ok=True)
    with _lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_status():
    if os.path.exists(STATUS_PATH):
        return json.load(open(STATUS_PATH, encoding="utf-8"))
    return {}


def save_status(status):
    os.makedirs(REVIEW_DIR, exist_ok=True)
    with _lock:
        tmp = STATUS_PATH + ".tmp"
        json.dump(status, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, STATUS_PATH)


def latest_decisions():
    """edit id -> last decision record."""
    out = {}
    for d in read_jsonl(DECISIONS_PATH):
        out[d.get("id")] = d
    return out


def edit_state(edit, decisions):
    d = decisions.get(edit["id"])
    if d is None:
        return "proposed"
    return {"approve": "approved", "reject": "rejected", "amend": "approved",
            "withdraw": "withdrawn"}.get(d.get("action"), "proposed")


def page_status_for(page, edits, status_file):
    """Effective status per step: done > in-review > pending."""
    saved = status_file.get(str(page), {})
    out = {}
    for step in ("words", "marks"):
        if saved.get(step) == "done":
            out[step] = "done"
        elif any(e["page"] == page and e["step"] == step for e in edits):
            out[step] = "in-review"
        else:
            out[step] = "pending"
    return out


# ------------------------------------------------------------ snippet extract

def _strip_ns(tag):
    return tag.split("}")[-1]


def word_audit_state(page, payload):
    """Expected-vs-held mark families for the word an edit points at, from the
    current sweep — so the queue shows the FLAG, not only the picture."""
    w = payload.get("word") or payload.get("from") or payload.get("to")
    if not w:
        return None
    import glob
    for d in ("tax2", "tax1"):
        f = os.path.join(ROOT, ".cache", "sweeps", d, "%03d.json" % int(page))
        if not os.path.exists(f):
            continue
        try:
            j = json.load(open(f))
        except Exception:
            return None
        for m in j.get("marks", []):
            if m.get("key") == w:
                return {"flagged": True,
                        "bad": ["%s: held %s, expected %s" % (b[0], b[1], b[2])
                                for b in m["bad"]]}
        return {"flagged": False, "bad": []}
    return None


def extract_context(page, payload):
    """Return a small standalone SVG snippet (ancestor transform chain kept)
    around the word/element an edit touches.  Client tightens the viewBox."""
    try:
        svg_path, _ = page_paths(page)
        if not os.path.exists(svg_path):
            return None
        tree = ET.parse(svg_path)
        root = tree.getroot()
        parents = {c: p for p in root.iter() for c in p}

        eid = payload.get("eid")
        wanted_words = set()
        for key in ("from", "to", "word"):
            v = payload.get(key)
            if isinstance(v, str) and v.count(":") == 2:
                wanted_words.add(v)
        for v in payload.get("words", []) or []:
            if isinstance(v, str):
                wanted_words.add(v)

        targets = []
        for el in root.iter():
            if eid and el.get("data-eid") == eid:
                targets.append(el)
            elif el.get("class") == "word" and wanted_words:
                saw = "%s:%s:%s" % (el.get("data-surah"), el.get("data-ayah"),
                                    el.get("data-word"))
                if saw in wanted_words:
                    targets.append(el)
        if not targets:
            return None

        # Climb from each target to its enclosing word group, keep the
        # ancestor transform chain up to the root.
        pieces = []
        for t in targets[:3]:
            node, group = t, t
            while node in parents:
                if node.get("class") == "word":
                    group = node
                node = parents[node]
            chain = []
            node = parents.get(group)
            while node is not None and _strip_ns(node.tag) != "svg":
                tr = node.get("transform")
                if tr:
                    chain.append(tr)
                node = parents.get(node)
            markup = ET.tostring(group, encoding="unicode")
            for tr in chain:  # innermost first -> wrap outwards
                markup = '<g transform="%s">%s</g>' % (tr, markup)
            pieces.append(markup)
        vb = root.get("viewBox", "0 0 345 550")
        markup = "".join(pieces)
        markup = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", markup)
        return ('<svg xmlns="%s" viewBox="%s">%s</svg>' % (SVGNS, vb, markup))
    except Exception:
        return None


# ------------------------------------------------------------------- handlers

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # -- helpers
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        try:
            data = open(path, "rb").read()
        except OSError:
            return self.send_json({"error": "not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            return None

    # -- routing
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/" or path == "/index.html":
                return self.send_file(os.path.join(PLATFORM, "index.html"),
                                      "text/html; charset=utf-8")
            if path == "/confidence":
                # score_confidence.py --html writes this; serving it same-origin
                # lets it fetch /api/page/N for the inline word previews
                return self.send_file(
                    os.path.join(ROOT, "docs", "defects", "confidence.html"),
                    "text/html; charset=utf-8")
            if path.startswith("/docs/defects"):
                # browse the defect reports: listing + files, no traversal
                base = os.path.realpath(os.path.join(ROOT, "docs", "defects"))
                rel = path[len("/docs/defects"):].lstrip("/")
                tgt = os.path.realpath(os.path.join(base, rel))
                if not tgt.startswith(base):
                    return self.send_json({"error": "bad path"}, 400)
                if os.path.isdir(tgt):
                    idx = os.path.join(tgt, "index.html")
                    if os.path.exists(idx) and "list=1" not in (parsed.query or ""):
                        return self.send_file(idx, "text/html; charset=utf-8")
                    rows = "".join(
                        '<li><a href="/docs/defects/%s">%s</a></li>' % (f, f)
                        for f in sorted(os.listdir(tgt))
                        if not f.startswith("."))
                    body = ("<!doctype html><meta charset=utf-8><title>defects"
                            "</title><body style='font:14px system-ui;margin:24px'>"
                            "<h2>docs/defects</h2><ul>%s</ul>" % rows).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    return self.wfile.write(body)
                if os.path.exists(tgt):
                    ct = ("text/html; charset=utf-8" if tgt.endswith(".html")
                          else "image/png" if tgt.endswith(".png")
                          else "application/json; charset=utf-8"
                          if tgt.endswith(".json")
                          else "text/plain; charset=utf-8")
                    return self.send_file(tgt, ct)
                return self.send_json({"error": "not found"}, 404)
            if path == "/proposals":
                # build_proposals_page.py writes this — decisions needing a human
                return self.send_file(
                    os.path.join(ROOT, "docs", "defects", "proposals.html"),
                    "text/html; charset=utf-8")
            m = re.match(r"^/api/page/(\d+)$", path)
            if m:
                return self.api_page(int(m.group(1)))
            if path == "/api/labels":
                return self.send_json({"labels": KNOWN_LABELS})
            if path == "/api/queue":
                return self.api_queue()
            if path == "/api/export":
                return self.api_export()
            if path == "/api/refresh":
                q = parse_qs(parsed.query)
                pg = q.get("page", [None])[0]
                pg = int(pg) if pg and pg.isdigit() else None
                n = clear_cache(pg)
                return self.send_json({"cleared": n,
                                       "scope": ("page %d" % pg) if pg else "all pages"})
            if path == "/api/overview":
                return self.api_overview()
            m = re.match(r"^/svg/(\d+)\.svg$", path)
            if m:
                svg_path, _ = ensure_page(int(m.group(1)))
                return self.send_file(svg_path, "image/svg+xml; charset=utf-8")
            # Static assets, chiefly the QPC Hafs font. Reviewing a word against the
            # printed page in a substitute face is guesswork: Amiri draws a sukun the
            # print does not use and joins letters the print keeps apart, so the text
            # under a card and the ink above it cannot be compared stroke for stroke.
            m = re.match(r"^/assets/([A-Za-z0-9._-]+)$", path)
            if m:
                name = m.group(1)
                ext = os.path.splitext(name)[1].lower()
                ctype = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff",
                         ".woff2": "font/woff2", ".css": "text/css; charset=utf-8",
                         ".js": "text/javascript; charset=utf-8"}.get(ext,
                                                                     "application/octet-stream")
                return self.send_file(os.path.join(PLATFORM, "assets", name), ctype)
            return self.send_json({"error": "not found"}, 404)
        except Exception as exc:  # keep the server alive, report the error
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self.read_body()
        if body is None:
            return self.send_json({"error": "invalid JSON body"}, 400)
        try:
            if path == "/api/edit":
                return self.api_edit(body)
            if path == "/api/edit/delete":
                return self.api_edit_delete(body)
            if path == "/api/review":
                return self.api_review(body)
            if path == "/api/page-status":
                return self.api_page_status(body)
            return self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    # -- API endpoints
    def api_page(self, page):
        if not 1 <= page <= NUM_PAGES:
            return self.send_json({"error": "page out of range"}, 400)
        svg_path, rep_path = ensure_page(page)
        svg = open(svg_path, encoding="utf-8").read()
        svg = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg)
        report = json.load(open(rep_path, encoding="utf-8"))
        edits = [e for e in read_jsonl(EDITS_PATH) if e.get("page") == page]
        decisions = latest_decisions()
        for e in edits:
            e["state"] = edit_state(e, decisions)
        edits = [e for e in edits if e["state"] != "withdrawn"]
        return self.send_json({
            "page": page,
            "svg": svg,
            "report": report,
            "edits": edits,
            "status": page_status_for(page, [e for e in edits
                                             if e["state"] != "rejected"],
                                      load_status()),
            "labels": KNOWN_LABELS,
        })

    def api_edit(self, body):
        required = ("page", "step", "kind", "payload", "editor")
        missing = [k for k in required
                   if k not in body or body[k] is None or body[k] == ""]
        if missing:
            return self.send_json(
                {"error": "missing fields: %s" % ", ".join(missing)}, 400)
        if body["step"] not in ("words", "marks"):
            return self.send_json({"error": "step must be words|marks"}, 400)
        if body["kind"] not in EDIT_KINDS:
            return self.send_json(
                {"error": "kind must be one of %s" % sorted(EDIT_KINDS)}, 400)
        try:
            page = int(body["page"])
        except (TypeError, ValueError):
            return self.send_json({"error": "page must be an integer"}, 400)
        if not isinstance(body["payload"], dict):
            return self.send_json({"error": "payload must be an object"}, 400)
        record = {
            "id": str(uuid.uuid4()),
            "page": page,
            "step": body["step"],
            "kind": body["kind"],
            "payload": body["payload"],
            "editor": str(body["editor"]),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "proposed",
        }
        append_jsonl(EDITS_PATH, record)
        return self.send_json({"ok": True, "record": record})

    def api_edit_delete(self, body):
        eid = body.get("id")
        editor = body.get("editor")
        if not eid or not editor:
            return self.send_json({"error": "missing id or editor"}, 400)
        if not any(e.get("id") == eid for e in read_jsonl(EDITS_PATH)):
            return self.send_json({"error": "unknown edit id"}, 404)
        append_jsonl(DECISIONS_PATH, {
            "id": eid, "action": "withdraw", "by": str(editor),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        return self.send_json({"ok": True})

    def api_review(self, body):
        if not body.get("id") or body.get("action") not in REVIEW_ACTIONS:
            return self.send_json(
                {"error": "need id and action approve|reject|amend"}, 400)
        edits = {e["id"]: e for e in read_jsonl(EDITS_PATH)}
        if body["id"] not in edits:
            return self.send_json({"error": "unknown edit id"}, 404)
        if body["action"] == "amend" and \
                not isinstance(body.get("amended_payload"), dict):
            return self.send_json(
                {"error": "amend requires amended_payload object"}, 400)
        record = {
            "id": body["id"],
            "action": body["action"],
            "reviewer": str(body.get("reviewer") or "anonymous"),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if body["action"] == "amend":
            record["amended_payload"] = body["amended_payload"]
        if body.get("note"):
            record["note"] = str(body["note"])[:2000]
        append_jsonl(DECISIONS_PATH, record)
        return self.send_json({"ok": True, "record": record})

    def api_page_status(self, body):
        try:
            page = int(body.get("page"))
        except (TypeError, ValueError):
            return self.send_json({"error": "page must be an integer"}, 400)
        step = body.get("step")
        if step not in ("words", "marks"):
            return self.send_json({"error": "step must be words|marks"}, 400)
        value = body.get("status", "done")
        if value not in ("done", "pending"):
            return self.send_json({"error": "status must be done|pending"}, 400)
        status = load_status()
        entry = status.setdefault(str(page), {})
        entry[step] = value
        entry["%s_by" % step] = str(body.get("user") or "anonymous")
        entry["%s_ts" % step] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_status(status)
        return self.send_json({"ok": True, "page": page, "step": step,
                               "status": value})

    def api_queue(self):
        decisions = latest_decisions()
        out = []
        for e in read_jsonl(EDITS_PATH):
            state = edit_state(e, decisions)
            if state != "proposed":
                continue
            e = dict(e)
            e["state"] = state
            e["context_svg"] = extract_context(e["page"], e.get("payload", {}))
            e["audit"] = word_audit_state(e["page"], e.get("payload", {}))
            out.append(e)
        out.sort(key=lambda e: e.get("ts", ""), reverse=True)
        return self.send_json({"queue": out, "count": len(out)})

    def api_export(self):
        decisions = latest_decisions()
        pages = {}
        for e in read_jsonl(EDITS_PATH):
            d = decisions.get(e["id"])
            if d is None or d["action"] == "reject":
                continue
            payload = d.get("amended_payload") if d["action"] == "amend" \
                else e["payload"]
            pages.setdefault(str(e["page"]), []).append({
                "id": e["id"],
                "step": e["step"],
                "kind": e["kind"],
                "payload": payload,
                "editor": e["editor"],
                "reviewer": d.get("reviewer"),
                "amended": d["action"] == "amend",
                "ts": e["ts"],
            })
        return self.send_json({
            "edition": EDITION,
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pages": pages,
            "total": sum(len(v) for v in pages.values()),
        })

    def api_overview(self):
        edits = read_jsonl(EDITS_PATH)
        decisions = latest_decisions()
        live = [e for e in edits if edit_state(e, decisions) != "rejected"]
        pending = [e for e in edits if edit_state(e, decisions) == "proposed"]
        status_file = load_status()
        pages = {}
        touched = set(e["page"] for e in edits) | \
            set(int(k) for k in status_file)
        for p in touched:
            entry = page_status_for(p, live, status_file)
            entry["pending"] = sum(1 for e in pending if e["page"] == p)
            pages[str(p)] = entry
        done_w = sum(1 for v in pages.values() if v["words"] == "done")
        done_m = sum(1 for v in pages.values() if v["marks"] == "done")
        return self.send_json({
            "num_pages": NUM_PAGES,
            "pages": pages,
            "totals": {
                "words_done": done_w,
                "marks_done": done_m,
                "pending_edits": len(pending),
                "total_edits": len(edits),
            },
        })


def main():
    global EDITION
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--edition", default="hafs/kfqc")
    args = ap.parse_args()
    EDITION = args.edition
    os.makedirs(REVIEW_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("review platform: http://127.0.0.1:%d/  (edition %s)"
          % (args.port, EDITION))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
