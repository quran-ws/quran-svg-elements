#!/usr/bin/env python3
"""Publish the shippable part of this clone to the public repo, and nothing else.

    python3 tools/publish.py                          # dry run: say exactly what would go
    python3 tools/publish.py -m "message"             # commit it in the publish worktree
    python3 tools/publish.py -m "message" --push      # and push

This clone is the lab notebook: it holds the drawings, the review data, the sweeps and the
scratchpad, and its history starts from a different root than the public repo's (the public
history was rewritten to strip exactly this material -- going from a local commit to the
matching public one is 308,209 deletions and zero insertions). The two can never be merged,
and they should not be: one is how the work was done, the other is what the work produced.

So publishing is a copy under an ALLOWLIST, never a push of this branch:

  * a path already tracked on the public branch may be updated -- that is what "already
    public" means, and it needs no list to maintain;
  * a path that is NOT there yet is published only if `publish.allow` names it;
  * `publish.deny` wins over both, for things that must never leave even though a sibling
    of theirs is public (a font we may not redistribute, a backup file).

A denylist alone would leak the first time a new private directory appeared. An allowlist
cannot: a new directory is invisible to publishing until someone writes it down.
"""
import argparse
import fnmatch
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKTREE = os.path.join(ROOT, ".cache", "publish")
ALLOW = os.path.join(ROOT, "publish.allow")
DENY = os.path.join(ROOT, "publish.deny")


def git(*args, cwd=ROOT, check=True):
    env = dict(os.environ, PUBLISH_OK="1")      # the pre-push hook lets only this script by
    r = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode:
        sys.exit("git %s failed:\n%s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.rstrip("\n")


def patterns(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def matches(rel, pats):
    return any(fnmatch.fnmatch(rel, p) or rel.startswith(p.rstrip("*").rstrip("/") + "/")
               for p in pats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="feat/letter-splitting", help="public branch to publish onto")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("-m", "--message", help="commit message; without it this is a dry run")
    ap.add_argument("--push", action="store_true", help="push the publish branch after committing")
    ap.add_argument("--allow-deletions", action="store_true",
                    help="also delete public files this clone no longer has")
    a = ap.parse_args()

    allow, deny = patterns(ALLOW), patterns(DENY)
    ref = "%s/%s" % (a.remote, a.branch)
    git("fetch", a.remote, a.branch)
    public = set(git("ls-tree", "-r", "--name-only", ref).splitlines())
    local = set(git("ls-tree", "-r", "--name-only", "HEAD").splitlines())

    take, new, blocked, gone = [], [], [], []
    for rel in sorted(local):
        if matches(rel, deny):
            if rel in public:
                blocked.append(rel)      # already published: left exactly as it is
            continue
        if rel in public:
            take.append(rel)
        elif matches(rel, allow):
            new.append(rel)
    for rel in sorted(public - local):
        if not matches(rel, deny):
            gone.append(rel)

    # A symlink is published as a symlink. 604 of tools/texts/qc/*.json point into
    # .cache/words/, which is gitignored and fetched on first use -- following them would
    # publish the word cache itself, 604 files of derived text, and report every one as
    # changed. git stores a link's target as the blob, so compare and copy the target.
    changed = []
    for rel in take + new:
        src = os.path.join(ROOT, rel)
        if not os.path.lexists(src):
            continue
        pub = git("show", "%s:%s" % (ref, rel), check=False) if rel in public else None
        if os.path.islink(src):
            if pub is None or pub.strip() != os.readlink(src):
                changed.append(rel)
            continue
        h_local = git("hash-object", src)
        h_pub = git("rev-parse", "%s:%s" % (ref, rel), check=False) if rel in public else ""
        if h_local != h_pub:
            changed.append(rel)

    print("publishing onto %s" % ref)
    print("  %d paths already public, %d new (named in publish.allow), %d changed" %
          (len(take), len(new), len(changed)))
    if new:
        print("\n  NEW public paths:")
        for rel in new:
            print("    + %s" % rel)
    if changed:
        print("\n  changed:")
        for rel in changed:
            print("    M %s" % rel)
    if blocked:
        print("\n  denied by publish.deny but already public -- left untouched (%d):" % len(blocked))
        for rel in blocked[:6]:
            print("    = %s" % rel)
    if gone:
        print("\n  on the public branch, absent here (%d, kept unless --allow-deletions):" % len(gone))
        for rel in gone[:10]:
            print("    - %s" % rel)
    withheld = len(local) - len(take) - len(new)
    print("\n  withheld from the public repo: %d paths of this clone" % withheld)
    if not a.message:
        print("\ndry run. pass -m \"message\" to commit in the publish worktree, then --push.")
        return

    if os.path.isdir(WORKTREE):
        git("worktree", "remove", "--force", WORKTREE, check=False)
        shutil.rmtree(WORKTREE, ignore_errors=True)
    git("worktree", "add", "--detach", WORKTREE, ref)
    for rel in take + new:
        src, dst = os.path.join(ROOT, rel), os.path.join(WORKTREE, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.islink(src):
            if os.path.lexists(dst):
                os.remove(dst)
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
    if a.allow_deletions:
        for rel in gone:
            os.remove(os.path.join(WORKTREE, rel))
    git("add", "-A", cwd=WORKTREE)
    staged = git("diff", "--cached", "--name-only", cwd=WORKTREE).splitlines()
    leak = [r for r in staged if matches(r, deny) or (r not in public and not matches(r, allow))]
    if leak:
        sys.exit("REFUSING: %d staged paths are not allowed to be published:\n  %s"
                 % (len(leak), "\n  ".join(leak[:20])))
    if not staged:
        print("nothing to publish.")
        return
    git("commit", "-q", "-m", a.message, cwd=WORKTREE)
    print("committed %d paths in %s" % (len(staged), WORKTREE))
    print(git("log", "-1", "--stat", cwd=WORKTREE))
    if a.push:
        head = git("rev-parse", "HEAD", cwd=WORKTREE)
        print(git("push", a.remote, "%s:refs/heads/%s" % (head, a.branch), cwd=WORKTREE))
    else:
        print("\nnot pushed. review it, then:  python3 tools/publish.py -m ... --push")


if __name__ == "__main__":
    main()
