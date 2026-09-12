#!/usr/bin/env bash
# Assemble the network share: the bundle, both demos, the spec and the
# reference material, in one folder any device on the LAN can browse.
#
# Everything here is REPRODUCIBLE from the repository. The share itself is
# 750 MB of generated output and is not committed; this script is.
#
#   docs/shipping/share/make_share.sh [target]
#
# Default target: ~/Public/hafs-svg
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="${QSVG_ROOT:-$HOME/Dev/github.com/AbdullahObaid/quran-svg-work}"
SHARE="${1:-$HOME/Public/hafs-svg}"
BUNDLE="$REPO/dist/quran-svg-elements-hafs-kfgqpc"

[ -d "$BUNDLE" ] || { echo "no bundle at $BUNDLE — run tools/build_bundle.py first" >&2; exit 1; }

echo "assembling $SHARE"
rm -rf "$SHARE"; mkdir -p "$SHARE"

# 1. the bundle
cp -r "$BUNDLE"/pages "$BUNDLE"/index "$BUNDLE"/schema "$SHARE"/
cp "$BUNDLE"/VERSION.json "$BUNDLE"/CHECKSUMS.txt "$BUNDLE"/LICENSE \
   "$BUNDLE"/NOTICE.md "$BUNDLE"/README.md "$SHARE"/
cp -r "$REPO/docs/shipping/lib" "$SHARE"/lib
[ -f "$REPO/dist/quran-svg-elements-hafs-kfgqpc.tar.gz" ] &&
  cp "$REPO/dist/quran-svg-elements-hafs-kfgqpc.tar.gz"* "$SHARE"/

# 2. both demos, with every path made RELATIVE.
#    The built pages point at the published host; served from a folder they
#    must address their own directory instead, so the same files work over the
#    LAN, over the tailnet, and from file:// on a copy.
python3 - "$WORK/docs/demo" "$SHARE" <<'PY'
import re, sys, os
src, dst = sys.argv[1], sys.argv[2]
for f in ("index.html", "index.ar.html"):
    s = open(os.path.join(src, f), encoding="utf-8").read()
    s2 = re.sub(r"const SITE_BASE = '[^']*';",
                "const SITE_BASE = './';   /* local share: everything is relative */",
                s, count=1)
    assert s2 != s, f + ": SITE_BASE not found — has the demo changed?"
    open(os.path.join(dst, f), "w", encoding="utf-8").write(s2)
    print("  demo:", f)
PY
cp -r "$WORK/docs/demo/data" "$SHARE"/data          # attrs, gloss, search index

# 3. the spec as HTML, so the demo's 19 documentation links resolve
python3 "$REPO/docs/shipping/share/render_format.py" \
        "$REPO/docs/shipping/FORMAT.md" "$SHARE/FORMAT.html"

# 4. reference material, if present
if [ -d "$REPO/docs/reference" ]; then
  mkdir -p "$SHARE/reference"; cp -r "$REPO/docs/reference/." "$SHARE/reference/"
fi

# 5. the landing page and the server
cp "$REPO/docs/shipping/share/home.html" "$REPO/docs/shipping/share/serve.py" "$SHARE"/
chmod +x "$SHARE/serve.py"

echo "done: $(du -sh "$SHARE" | cut -f1) at $SHARE"
echo "serve it with:  systemctl --user restart hafs-svg   (or python3 $SHARE/serve.py)"
