#!/usr/bin/env bash
# Publish one release of the element SVG to cdn.quran.ws/svg/elements/.
#
#   scripts/publish-cdn.sh v1.1.1               # download the release, verify, upload
#   scripts/publish-cdn.sh v1.1.1 --stage-only  # build the tree and the manifest, upload nothing
#
# The GitHub release is the canonical artefact and the CDN is a mirror of it, so the files
# come from the release tarball and never from a working tree. The tarball's own sha256 is
# checked before anything is read out of it.
#
# Pages go up one object each, because a reader wants page 42 and not 108 MB. They are stored
# raw: a Compression Rule on cdn.quran.ws negotiates zstd, brotli or gzip per client, which
# beats one fixed encoding and still lets a client verify the bytes against the manifest.
#
# Needs: curl (>= 7.75, for --aws-sigv4), tar, sha256sum/shasum, jq, gh.
# Credentials: see scripts/cdn-put.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/cdn-put.sh

VERSION="${1:?usage: publish-cdn.sh <tag> [--stage-only]}"; shift
STAGE_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --stage-only) STAGE_ONLY=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

FAMILY=svg/elements
PREFIX="$FAMILY/$(cdn_version "$VERSION")"
ASSET=quran-svg-elements-hafs-kfgqpc.tar.gz
SRC="dist/cdn/$VERSION/src"
STAGE="dist/cdn/$VERSION"

# 1. The release tarball, verified against the checksum published beside it.
echo "== fetching $VERSION"
rm -rf "$STAGE" && mkdir -p "$SRC"
gh release download "$VERSION" --repo quran-ws/quran-svg-elements --clobber -D "$STAGE" \
  -p "$ASSET" -p "$ASSET.sha256"
want=$(cut -d' ' -f1 < "$STAGE/$ASSET.sha256"); got=$(sha256 "$STAGE/$ASSET")
[ "$want" = "$got" ] || { echo "sha256 mismatch: want $want got $got" >&2; exit 1; }

# `--strip-components=1` drops the single directory the tarball wraps everything in. BSD tar
# takes --include, GNU tar takes --wildcards, so try one and fall back to the other.
tar -xzf "$STAGE/$ASSET" -C "$SRC" --strip-components=1 --include='*/pages/*' --include='*/index/*' 2>/dev/null \
  || tar -xzf "$STAGE/$ASSET" -C "$SRC" --strip-components=1 --wildcards '*/pages/*' '*/index/*'
[ -f "$SRC/pages/001.svg" ] || { echo "the release did not contain pages/001.svg" >&2; exit 1; }

# 2. The manifest, so a client can prefetch a range of pages and check what it got without
#    one HEAD request per file. Paths are relative to the version folder.
echo "== staging $PREFIX"
( cd "$SRC" && find pages index -type f ! -name '.*' | sort ) > "$STAGE/.files"
: > "$STAGE/.files.tsv"
while IFS= read -r f; do
  printf '%s\t%s\t%s\n' "$f" "$(wc -c < "$SRC/$f" | tr -d ' ')" "$(sha256 "$SRC/$f")" >> "$STAGE/.files.tsv"
done < "$STAGE/.files"

jq -n --arg version "$(cdn_version "$VERSION")" --arg base "https://$CDN_HOST/$PREFIX/" \
      --arg release "$VERSION" --arg edition "hafs-kfgqpc" \
      --rawfile tsv "$STAGE/.files.tsv" '
  {version: $version, release: $release, edition: $edition, base: $base, encoding: "identity",
   files: ($tsv | rtrimstr("\n") | split("\n") | map(split("\t") |
     {name: .[0], bytes: (.[1]|tonumber), sha256: .[2]}))}
' > "$STAGE/manifest.json"
echo "   $(wc -l < "$STAGE/.files" | tr -d ' ') objects + manifest, $(du -sh "$SRC" | cut -f1) raw"

[ "$STAGE_ONLY" = 1 ] && { echo "== staged only: $STAGE"; exit 0; }

# 3. Upload. Nothing is rewritten, so what is published is byte for byte what the release
#    signed, and a version that already exists is never overwritten.
cdn_init
cdn_guard "$PREFIX" || exit 1

echo "== uploading to r2://$BUCKET/$PREFIX"
export PREFIX SRC
xargs -P 16 -I{} bash -c 'cdn_put "$PREFIX/{}" "$SRC/{}"' < "$STAGE/.files"
cdn_put "$PREFIX/manifest.json" "$STAGE/manifest.json" "public, max-age=300"
cdn_latest "$FAMILY" "$(cdn_version "$VERSION")"

echo "== published https://$CDN_HOST/$PREFIX/manifest.json"
