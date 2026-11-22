#!/usr/bin/env bash
# Publish one release of the element SVG to cdn.quran.ws/svg/elements/.
#
#   scripts/publish-cdn.sh v2.0.0               # download the release, verify, upload
#   scripts/publish-cdn.sh v2.0.0 --stage-only  # build the tree and the manifests, upload nothing
#
# The GitHub release is the canonical artefact and the CDN is a mirror of it, so the files
# come from the release tarballs and never from a working tree. Each tarball's own sha256 is
# checked before anything is read out of it.
#
# A release holds the same pages at two levels, one archive each, and the version folder
# holds one folder per level:
#
#   svg/elements/v2.0.0/manifest.json            names the levels
#   svg/elements/v2.0.0/words/manifest.json      every file of the word pages
#   svg/elements/v2.0.0/words/pages/001.svg
#   svg/elements/v2.0.0/letters/manifest.json    the same pages, every word divided into letters
#   svg/elements/v2.0.0/letters/pages/001.svg
#
# (Versions up to v1.1.2 were word pages only, directly under the version folder.)
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
LEVELS="words letters"
STAGE="dist/cdn/$VERSION"
rm -rf "$STAGE" && mkdir -p "$STAGE"

for level in $LEVELS; do
  ASSET="quran-svg-elements-hafs-kfgqpc-$level.tar.gz"
  SRC="$STAGE/$level"; mkdir -p "$SRC"

  # 1. The release tarball, verified against the checksum published beside it.
  echo "== fetching $VERSION $level"
  gh release download "$VERSION" --repo quran-ws/quran-svg-elements --clobber -D "$STAGE" \
    -p "$ASSET" -p "$ASSET.sha256"
  want=$(cut -d' ' -f1 < "$STAGE/$ASSET.sha256"); got=$(sha256 "$STAGE/$ASSET")
  [ "$want" = "$got" ] || { echo "sha256 mismatch on $ASSET: want $want got $got" >&2; exit 1; }

  # `--strip-components=1` drops the single directory the tarball wraps everything in. BSD tar
  # takes --include, GNU tar takes --wildcards, so try one and fall back to the other.
  tar -xzf "$STAGE/$ASSET" -C "$SRC" --strip-components=1 --include='*/pages/*' --include='*/index/*' --include='*/VERSION.json' 2>/dev/null \
    || tar -xzf "$STAGE/$ASSET" -C "$SRC" --strip-components=1 --wildcards '*/pages/*' '*/index/*' '*/VERSION.json'
  [ -f "$SRC/pages/001.svg" ] || { echo "$ASSET did not contain pages/001.svg" >&2; exit 1; }

  # The archive's name is a claim; the bundle itself says what it is. Only a letter bundle's
  # VERSION.json has a `letters` record, and a swapped pair must not go out under the wrong folder.
  is=$(jq -r 'if has("letters") then "letters" else "words" end' "$SRC/VERSION.json")
  [ "$is" = "$level" ] || { echo "$ASSET is a $is bundle, not $level" >&2; exit 1; }
  rm "$SRC/VERSION.json"

  # 2. The manifest, so a client can prefetch a range of pages and check what it got without
  #    one HEAD request per file. Paths are relative to the level's folder.
  echo "== staging $PREFIX/$level"
  ( cd "$SRC" && find pages index -type f ! -name '.*' | sort ) > "$STAGE/.files.$level"
  : > "$STAGE/.files.$level.tsv"
  while IFS= read -r f; do
    printf '%s\t%s\t%s\n' "$f" "$(wc -c < "$SRC/$f" | tr -d ' ')" "$(sha256 "$SRC/$f")" >> "$STAGE/.files.$level.tsv"
  done < "$STAGE/.files.$level"

  jq -n --arg version "$(cdn_version "$VERSION")" --arg base "https://$CDN_HOST/$PREFIX/$level/" \
        --arg release "$VERSION" --arg edition "hafs-kfgqpc" --arg level "$level" \
        --rawfile tsv "$STAGE/.files.$level.tsv" '
    {version: $version, release: $release, edition: $edition, level: $level, base: $base,
     encoding: "identity",
     files: ($tsv | rtrimstr("\n") | split("\n") | map(split("\t") |
       {name: .[0], bytes: (.[1]|tonumber), sha256: .[2]}))}
  ' > "$SRC/manifest.json"
  echo "   $(wc -l < "$STAGE/.files.$level" | tr -d ' ') objects + manifest, $(du -sh "$SRC" | cut -f1) raw"
done

# The version's own manifest names the levels and where each one's manifest is.
jq -n --arg version "$(cdn_version "$VERSION")" --arg base "https://$CDN_HOST/$PREFIX/" \
      --arg release "$VERSION" --arg edition "hafs-kfgqpc" --arg levels "$LEVELS" '
  {version: $version, release: $release, edition: $edition, base: $base,
   levels: ($levels | split(" ") | map({key: ., value: {base: ($base + . + "/"),
                                                         manifest: ($base + . + "/manifest.json")}})
            | from_entries)}
' > "$STAGE/manifest.json"

[ "$STAGE_ONLY" = 1 ] && { echo "== staged only: $STAGE"; exit 0; }

# 3. Upload. Nothing is rewritten, so what is published is byte for byte what the release
#    signed, and a version that already exists is never overwritten. The version's manifest
#    goes up last: it is what marks the folder as published.
cdn_init
cdn_guard "$PREFIX" || exit 1

for level in $LEVELS; do
  echo "== uploading to r2://$BUCKET/$PREFIX/$level"
  DEST="$PREFIX/$level" SRC="$STAGE/$level"
  export DEST SRC
  xargs -P 16 -I{} bash -c 'cdn_put "$DEST/{}" "$SRC/{}"' < "$STAGE/.files.$level"
  cdn_put "$DEST/manifest.json" "$SRC/manifest.json" "public, max-age=300"
done
cdn_put "$PREFIX/manifest.json" "$STAGE/manifest.json" "public, max-age=300"
cdn_latest "$FAMILY" "$(cdn_version "$VERSION")"

echo "== published https://$CDN_HOST/$PREFIX/manifest.json"
