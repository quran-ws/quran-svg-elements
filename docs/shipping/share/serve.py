#!/usr/bin/env python3
"""Serve this folder to the local network.

Bound to 0.0.0.0 on purpose: any device on the LAN (or the tailnet) can reach
it. "/" lands on home.html rather than the demo, so the folder introduces
itself; the demo keeps index.html, which is also what a plain file:// copy
opens.
"""
import http.server, socketserver, os, socket

PORT = int(os.environ.get("PORT", "8080"))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class H(http.server.SimpleHTTPRequestHandler):
    # EVERYTHING HERE IS UTF-8, and it must say so. Without an explicit charset
    # a browser falls back to a legacy encoding and every Arabic string renders
    # as mojibake — which is exactly what happened to the sign catalogue, whose
    # own file declared no charset either. Python's default map sends bare
    # "text/html", so the charset is spelled out for every text type.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8",
                      ".htm": "text/html; charset=utf-8",
                      ".css": "text/css; charset=utf-8",
                      ".js": "text/javascript; charset=utf-8",
                      ".mjs": "text/javascript; charset=utf-8",
                      ".md": "text/plain; charset=utf-8",
                      ".txt": "text/plain; charset=utf-8",
                      ".json": "application/json; charset=utf-8",
                      ".svg": "image/svg+xml; charset=utf-8",
                      ".br": "application/octet-stream"}
    def do_GET(self):
        if self.path in ("/", "/index"):
            self.send_response(302); self.send_header("Location", "/home.html")
            self.end_headers(); return
        return super().do_GET()
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), H) as httpd:
    ip = socket.gethostbyname(socket.gethostname())
    print("hafs-svg on http://%s:%d/  (and every other address of this host)" % (ip, PORT))
    httpd.serve_forever()
