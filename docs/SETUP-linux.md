# Running this on Linux — what the install actually needs

The `Setting this up on a new machine` recipe in `CLAUDE.md` was written on the
macOS box the work started on. Two things in it do not survive the move, and
both fail *silently or late*, so they are recorded here.

## The layout used on this machine

```
Dev/github.com/quranpedia/quran-svg          the user's own clone — NOT touched
Dev/github.com/AbdullahObaid/
    quran-svg-pipeline/                      this repo: the working set, git-tracked
    quran-svg-work/                          the DATA ROOT (QSVG_ROOT)
    MushafDatabase-Ligature-Based-SVG/       the outside reference
```

`quran-svg-work` is a **sparse git worktree** of `quranpedia/quran-svg` pinned at
`b91d39e1`, checking out only `mushafs/hafs` (491 MB of 6.7 GB), with the
working set symlinked in:

```bash
git -C ../../quranpedia/quran-svg worktree add --no-checkout --detach ../../AbdullahObaid/quran-svg-work b91d39e1
git -C ../quran-svg-work sparse-checkout init --cone
git -C ../quran-svg-work sparse-checkout set mushafs/hafs
git -C ../quran-svg-work checkout
cd ../quran-svg-work && for d in tools docs scratchpad .cache CLAUDE.md; do ln -sfn "$PWD/../quran-svg-pipeline/$d" .; done
```

Why a worktree and not a copy:

- `verify_render.py` reads the pre-change page with `git show HEAD:mushafs/...`
  in `ROOT`. It only works if `ROOT` is a git repo whose HEAD holds the pristine
  artwork. A plain copy into a gitignored `mushafs/` breaks it on every page.
- `add_line_structure.py` **rewrites all 604 page SVGs in place.** Running it in
  the user's own clone would leave 604 modified files in a repo they are using
  for other work. The worktree keeps that blast radius at zero.
- Symlinks, not copies, for the working set: `os.path.abspath` does not resolve
  symlinks, so `ROOT = dirname(dirname(abspath(__file__)))` still resolves to
  `quran-svg-work` — while every code edit lands in the git-tracked repo.
  (Nothing in the tree uses `os.path.realpath`; if something starts to, this
  breaks.)

The pin was `f8ea2002` until 2026-09-08 and is now `b91d39e1`, today's `main`.
The move matters: it restores the surah name on the opening spread at the full
page size (page 1 was drawn at `0 0 235 235` with 7 lines), and it re-centres
every ayah medallion's ring on its numeral across 423 of the 604 pages. Bench
is unchanged at SCORE 136 — medallion ink is not word ink — and every page is
still pixel-identical.

## Blocker 1 — sixteen absolute macOS paths

Thirteen files hard-coded `ROOT = "/Users/abdullah/Documents/Github/quran-svg"`
and three more hard-coded a *dead Claude session scratchpad* under
`/private/tmp/claude-501/...` — which is where the pinned baseline sweep lived.
All now resolve as:

```python
ROOT   = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEPS = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps"))
```

Both branches agree in this layout, and the env var still lets an audit be
pointed at a different tree. `. env.sh` sets them.

## Blocker 2 — the pinned baseline sweep is not in the repo

`cmp_full.py` and `cmp_pages.py` compare against `baseline/pages`, 604 JSON
files that lived only in that dead scratchpad. They are **gone**. What survived
is the thing that matters: `tools/_pipeline_baseline.py`, the pinned *build* —
currently byte-identical to `tools/assign_words.py`. So the baseline is
regenerated, not recovered:

```bash
. env.sh
QSVG_OUT="$QSVG_SWEEPS/baseline/pages" QSVG_PIPE="$QSVG_ROOT/tools/_pipeline_baseline.py" \
QSVG_JOBS=8 python3 scratchpad/full_sweep.py 1 604
```

`full_sweep.py` also never created its own output directory (it would crash on
a fresh machine) and hard-coded `Pool(2)`; both are fixed, jobs via `QSVG_JOBS`.

## Verified on this machine

| step | expected | got |
|---|---|---|
| `add_line_structure.py --mushaf hafs/kfqc --no-brotli` | 0 failed | 722 pages, 720 at 15 lines, 2 opening-page exceptions, **0 failed** |
| `verify_render.py hafs/kfqc` | max alpha change 17/255 | **17/255**, 146 byte-identical, 0 errors, 0.0015% pixels differ |
| `bench.py` | SCORE 77, no failures, pixelfail 0 | **SCORE 77, FAILURES none, pixelfail 0** |

`--no-brotli` was used: nothing in the decomposition loop reads `svg-br/`, and
quality-11 recompression of 604 pages buys nothing here. If the ayah-polygon
audits are ever run from this tree, drop the flag first — `svg-br/` is now stale
relative to `svg/`.

Deps present: python 3.12, numpy 1.26, pillow 10.2, brotli 1.1, rsvg-convert.
