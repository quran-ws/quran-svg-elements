# Source before running any pipeline/audit command:  . env.sh
#
# QSVG_ROOT is the data root: the directory holding mushafs/, tools/, .cache/.
# On this machine it is a sparse git worktree of quranpedia/quran-svg pinned at
# f8ea2002, with the working set symlinked in, so `git show HEAD:mushafs/...`
# still resolves (verify_render.py needs it) while the pipeline repo stays the
# single source of truth for code.
export QSVG_ROOT=/home/abdullah/Dev/github.com/AbdullahObaid/quran-svg-work
export QSVG_SWEEPS="$QSVG_ROOT/.cache/sweeps"
export PYTHONDONTWRITEBYTECODE=1
alias qsvg="cd $QSVG_ROOT"
