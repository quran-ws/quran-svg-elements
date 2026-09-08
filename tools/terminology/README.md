# The terminology standard, pinned

A snapshot of [`quran-ws/guidelines`](https://github.com/quran-ws/guidelines)
`skills/quranic-terminology` — the dictionary and the audit — so CI can run the
gate without credentials. That repository is private; a workflow cannot clone
it, and a gate that cannot run is not a gate.

    snapshot   499bc74667765196     180 entries, all `draft`
    vendored   2026-09-08

Only two files are copied: `data/terminology.json` and
`scripts/audit_terminology.py`. Nothing here is edited — a name that lives only
in one codebase is the problem the standard exists to fix. To refresh, run
`scripts/update_check.py` from the installed skill; when it says *behind*,
re-copy both files and re-run the audit.

Locally, prefer the installed skill (it carries `lookup.py`, `propose.py`,
the registries and the standard itself):

    python3 ~/.claude/skills/quranic-terminology/scripts/audit_terminology.py --strict

The two must agree. CI runs the vendored copy:

    python3 tools/terminology/scripts/audit_terminology.py --strict
