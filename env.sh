# Source before running any pipeline/audit command:  . env.sh
#
# QSVG_ROOT is the data root: the directory holding mushafs/, tools/, .cache/.
# It is a sparse git worktree of quranpedia/quran-svg pinned at f8ea2002, with
# the working set symlinked in, so `git show HEAD:mushafs/...` still resolves
# (verify_render.py needs it) while the pipeline repo stays the single source of
# truth for code. The checkout lives in a different place on each machine, so
# take the first candidate that exists; an already-set QSVG_ROOT always wins.
if [ -z "$QSVG_ROOT" ]; then
  for _qsvg_c in \
    /home/abdullah/Dev/github.com/AbdullahObaid/quran-svg-work \
    /Users/abdullah/Documents/Github/quran-svg-work
  do
    [ -d "$_qsvg_c/mushafs" ] && { QSVG_ROOT=$_qsvg_c; break; }
  done
  unset _qsvg_c
fi
export QSVG_ROOT
export QSVG_SWEEPS="$QSVG_ROOT/.cache/sweeps"
export PYTHONDONTWRITEBYTECODE=1
alias qsvg="cd $QSVG_ROOT"
