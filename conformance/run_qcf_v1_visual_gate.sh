#!/usr/bin/env bash
set -euo pipefail

: "${QCF_V1_QVP_DIR:?set QCF_V1_QVP_DIR}"
: "${QCF_V1_CONVERTER:?set QCF_V1_CONVERTER}"
: "${QCF_V1_BASE_DIR:?set QCF_V1_BASE_DIR}"
: "${QCF_V1_INDEX_DIR:?set QCF_V1_INDEX_DIR}"
: "${QCF_V1_REFERENCE_DIR:?set QCF_V1_REFERENCE_DIR}"
: "${QCF_V1_HQ_MAP:?set QCF_V1_HQ_MAP}"
: "${QCF_V1_SOURCE_RECORDS:?set QCF_V1_SOURCE_RECORDS}"
: "${QCF_V1_VISUAL_OUT:?set QCF_V1_VISUAL_OUT}"

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PAGES=${QCF_V1_VISUAL_PAGES:-1-604}
JOBS=${QCF_V1_VISUAL_JOBS:-8}
CROSS=${QCF_V1_CROSS_RENDERER_PAGES:-3,50,177,270,454,604}

[[ ! -e "$QCF_V1_VISUAL_OUT" ]] || {
  printf 'refusing existing output path: %s\n' "$QCF_V1_VISUAL_OUT" >&2
  exit 1
}

extra=()
if [[ -n ${QCF_V1_RESVG:-} ]]; then
  extra+=(--resvg "$QCF_V1_RESVG" --cross-renderer-pages "$CROSS")
fi
if [[ -n ${QCF_V1_BASELINE_REPORT:-} ]]; then
  extra+=(--baseline-report "$QCF_V1_BASELINE_REPORT")
fi

exec uv run --script "$ROOT/tools/qcf_v1_visual_audit.py" \
  --qvp-dir "$QCF_V1_QVP_DIR" \
  --converter "$QCF_V1_CONVERTER" \
  --base-dir "$QCF_V1_BASE_DIR" \
  --index-dir "$QCF_V1_INDEX_DIR" \
  --reference-dir "$QCF_V1_REFERENCE_DIR" \
  --hq-map "$QCF_V1_HQ_MAP" \
  --source-records "$QCF_V1_SOURCE_RECORDS" \
  --policy "$ROOT/conformance/qcf-v1-visual-policy.json" \
  --review-ledger "$ROOT/conformance/qcf-v1-visual-review.json" \
  --pages "$PAGES" \
  --jobs "$JOBS" \
  --out-dir "$QCF_V1_VISUAL_OUT" \
  --require-no-open \
  "${extra[@]}" \
  "$@"
