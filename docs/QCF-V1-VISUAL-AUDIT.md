# QCF V1 adversarial visual audit

The existing source contracts prove counts, ownership, and deterministic output. They do not prove that every local result looks correct. A page-wide ink total can remain excellent while one word touches its neighbour, loses a counter, or becomes worse than the verified fallback.

`tools/qcf_v1_visual_audit.py` is the fail-closed local-quality gate. It diagnoses fixed-page source geometry; it does not repair placement and does not add any Quran Engine runtime behavior.

## Checks

The audit streams one page at a time and checks:

- logical/physical word inventory, line order, finite geometry, and page containment;
- separately rendered adjacent-word ink at 1920 px and reading size, so empty bounding-box regions do not become false collisions;
- solid overlap, soft antialiased contact, tight clearance, and reading-size merging; a candidate-only overlap becomes explicit review only when the registered scan supports every overlap pixel at that same render width and the local pair remains within the existing scan-quality bounds;
- severe ink, component, and counter loss relative to the verified QCF fallback;
- local word and whole-line regression against the pinned 1405H scan, with registration bounded to two pixels;
- HQ source transforms that stretch a word vertically by more than 8%; the finding is review by itself and becomes a non-waivable blocker when the pinned 1405H scan independently shows a material regression;
- line-centre drift;
- source optical-copy count and cardinal symmetry when the source SVG retains that representation;
- exact ornament inventory and rendered-geometry preservation;
- optional CairoSVG/resvg drift on selected pages.

The pinned scan is review evidence, not source authority. It may classify an otherwise new-overlap blocker as explicit review only when the overlap itself is supported at the same render width; high-resolution evidence cannot excuse a reading-size merge. Missing, weak, or unsupported evidence remains blocking. The scan never admits an HQ candidate or changes source output.

## Findings and review

Blockers cannot be waived. Review findings need an explicit source-grounded entry in `conformance/qcf-v1-visual-review.json`. `open` remains release-blocking, unreviewed findings block, and stale ledger entries fail.

The committed ledger is intentionally empty. The current corpus is expected to remain red until its findings are fixed or individually resolved from source evidence.

## Release command

`conformance/run_qcf_v1_visual_gate.sh` requires explicit `QCF_V1_*` paths and refuses to overwrite an existing evidence directory. QVP conversion flattens SVG transforms, so the release gate also requires the exact `source-qualified.ndjson` ledger through `QCF_V1_SOURCE_RECORDS`; the ledger digest and coverage are checked against the HQ map and bound into the audit identity. It runs all 604 pages by default. A typical invocation sets:

```text
QCF_V1_QVP_DIR
QCF_V1_CONVERTER
QCF_V1_BASE_DIR
QCF_V1_INDEX_DIR
QCF_V1_REFERENCE_DIR
QCF_V1_HQ_MAP
QCF_V1_SOURCE_RECORDS
QCF_V1_VISUAL_OUT
QCF_V1_RESVG              # optional cross-renderer checks
QCF_V1_BASELINE_REPORT    # optional new/resolved/unchanged delta
```

Outputs are `report.json`, `findings.ndjson`, `summary.json`, and `report.html`.
