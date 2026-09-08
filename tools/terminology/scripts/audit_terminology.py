#!/usr/bin/env python3
"""Audit a codebase against the Quranic Software Terminology Standard.

Reads the identifiers in a tree and reports the names that the standard would
have written differently: a deprecated name, a spelling that is not the
canonical one, an English gloss standing in for a Quranic term, an Arabic
plural used as a collection name.

    python3 audit_terminology.py PATH [PATH ...]
    python3 audit_terminology.py src --by file          # or concept (default), rule
    python3 audit_terminology.py src --json
    python3 audit_terminology.py src --strict           # exit 1 if there are errors

Every finding names the rule, the section of the standard behind it, the
canonical name to use instead, and the layer the file belongs to, so that a
report can separate the cheap internal rename from the one that needs a
migration. Nothing is rewritten: the script reports, and the decision to
rename stays with whoever knows the code.

A project tells the audit what it already knows in `.terminology.json` at the
audited root (or `--config PATH`); `assets/terminology.example.json` documents
every key. A single line is excused with the words `terminology: ignore` in a
comment on it.

Exit codes: 0 ran; 1 errors found and --strict; 2 nothing to audit (a path
that does not exist, a tree with no files the audit reads, unreadable data).
"""
import argparse
import fnmatch
import json
import os
import re
import signal
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data", "terminology.json")
CONFIG_NAME = ".terminology.json"

CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".kt", ".swift", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".dart",
    ".sql", ".graphql", ".gql", ".proto", ".json", ".yml", ".yaml", ".toml",
    ".prisma", ".vue", ".svelte", ".scala", ".ex", ".exs", ".sh", ".html",
    ".xml", ".csv", ".tsv", ".ini", ".env", ".blade.php",
}
PROSE_SUFFIXES = {".md", ".mdx", ".txt", ".rst", ".adoc"}
EXTRA_NAMES = {".env.example", ".env.sample"}
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target",
    "__pycache__", ".venv", "venv", ".next", ".nuxt", ".cache", "coverage",
    ".mypy_cache", ".pytest_cache", "migrations_backup",
}
MAX_BYTES = 2_000_000
IGNORE_LINE = re.compile(r"terminology:\s*ignore", re.I)

# An identifier as it is written in any of the languages above, before it is
# split: dots and hyphens included, so `ayah.aya_key` and `verse-list` are one
# run of text and their parts are checked together.
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]*")
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

RULES = {
    "deprecated": ("error", "A deprecated name: it names a different concept (section 20)."),
    "spelling": ("error", "Not the canonical code spelling (sections 4-8)."),
    "arabic_plural": ("error", "An Arabic plural used as a name (section 11)."),
    "member": ("error", "A member of a closed set written in a spelling that is not its "
                        "registry code (sections 12-13)."),
    "display_in_code": ("warning", "The display name, used as an identifier (section 9)."),
    "gloss": ("warning", "An English gloss standing in for a Quranic term (sections 3, 19)."),
    "generic": ("warning", "An ordinary English word that is also a recorded spelling of a "
                           "concept; a finding only if the identifier is about that concept."),
}
RULE_ORDER = ("deprecated", "spelling", "arabic_plural", "member", "display_in_code", "gloss",
              "generic")
# Registries whose members are proper names — a rawi, a numbering system, a
# rule — so a recorded spelling of one is unambiguous wherever it is written.
# A surah or a tariq is often named by an ordinary word (`elephant`, `sad`),
# so a single-word spelling there is only a hint, like GENERIC_WORDS.
PROPER_NAME_KINDS = {"qiraah", "rawi", "riwayah", "ayah_numbering_system", "tajwid_ruling"}
ASCII_FORM = re.compile(r"^[a-z][a-z0-9_]*$")

# Ordinary English words that some entry records as a spelling. Alone they say
# nothing about the Quran — `segment` is an audio segment far more often than a
# morpheme — so a single-word hit on one of these is a warning to check, never
# an error. A project adds its own under `ignore_words`.
GENERIC_WORDS = {
    "segment", "segments", "reading", "readings", "stop", "sign", "mark", "dot", "dots",
    "place", "count", "number", "line", "page", "word", "letter", "root", "text",
    "character", "glyph", "translation", "position", "index", "order", "part", "unit",
    "quarter", "half", "eighth", "chain", "path", "way", "style", "pace", "school",
    "pos", "simple",
}

# Where a file sits says what a rename costs. A database column or a wire
# format is a compatibility surface: renaming it is a migration, not an edit.
LAYERS = (
    ("compatibility surface", re.compile(
        r"(^|/)(migrations?|schema|db|database|sql|prisma|proto|graphql|openapi|swagger|"
        r"api-spec|contracts?)(/|$)|\.(sql|prisma|proto|graphql|gql)$|"
        r"(^|/)(openapi|swagger|schema)[^/]*\.(json|ya?ml)$", re.I)),
    ("ui", re.compile(
        r"\.(tsx|jsx|vue|svelte|html|blade\.php)$|(^|/)(components?|views?|templates?|"
        r"pages|screens|ui|locales?|i18n|lang)(/|$)", re.I)),
)


def load(path=DATA):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["_member_display"] = member_displays(data, os.path.join(os.path.dirname(path), "registries"))
    return data


def member_displays(data, registries):
    """`kind:code` → the member's display name, read from the registry beside the data."""
    out = {}
    if not os.path.isdir(registries):
        return out
    for kind in data.get("registry_members", {}):
        name = (data["concepts"].get(kind) or {}).get("registry")
        path = os.path.join(registries, f"{name}.tsv") if name else None
        if not path or not os.path.exists(path):
            continue
        header, rows = [], []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#"):
                    fields = [c.strip() for c in line.lstrip("#").split("\t")]
                    if len(fields) > 1:
                        header = fields
                elif line.strip():
                    rows.append([c.strip() for c in line.split("\t")])
        col = {c: i for i, c in enumerate(header)}
        if "code" not in col:
            continue
        for row in rows:
            code = row[col["code"]] if col["code"] < len(row) else ""
            display = row[col["display"]] if "display" in col and col["display"] < len(row) else code
            out[f"{kind}:{code}"] = display or code
    return out


def name_of(data, concept):
    """(canonical, display) for a concept, for a `kind:code` registry member, or
    for `a|b`, a form shared by the values of two classifications."""
    if "|" in concept:
        pairs = [name_of(data, c) for c in concept.split("|")]
        codes = sorted({c for c, _ in pairs})
        return " or ".join(codes), " or ".join(d for _, d in pairs)
    if ":" in concept:
        kind, code = concept.split(":", 1)
        display = data.get("_member_display", {}).get(concept, code)
        return code, f"{display}, a {data['concepts'].get(kind, {}).get('display') or kind}"
    e = data["concepts"][concept]
    return e["code"], e.get("display")


def suffix_of(name):
    lower = name.lower()
    if lower.endswith(".blade.php"):
        return ".blade.php"
    if lower in EXTRA_NAMES:
        return ".env"
    return os.path.splitext(lower)[1]


def parts_of(identifier):
    """Split an identifier into lowercase words, however it is cased."""
    out = []
    for chunk in re.split(r"[_.\-]+", identifier):
        if chunk:
            out += [p.lower() for p in CAMEL.split(chunk) if p]
    return out


def ngrams(parts, longest=4):
    """Every run of parts, longest first, so `waqf_lazim` beats `waqf`."""
    for size in range(min(longest, len(parts)), 0, -1):
        for start in range(0, len(parts) - size + 1):
            yield start, size, "_".join(parts[start:start + size])


def lookup(parts, index):
    """The findings in one identifier: the longest match wins its span."""
    found, taken = [], set()
    for start, size, gram in ngrams(parts):
        span = set(range(start, start + size))
        if span & taken:
            continue
        hit = index.get(gram)
        if hit:
            taken |= span
            found.append((gram, hit))
    return found


def build_index(data, ignore_words):
    """One map from a written form to (rule, concept, the form without its `s`)."""
    index = {}

    def put(form, rule, concept):
        form = form.lower().replace("-", "_").replace(" ", "_")
        if not form or form == concept:
            return
        index.setdefault(form, (rule, concept, form))

    # Order decides which rule claims a form, so the most specific goes first:
    # `tajweed` is the display name before it is merely a spelling.
    for concept, e in data["concepts"].items():
        for name in e.get("deprecated") or []:
            put(name, "deprecated", concept)
    for concept, e in data["concepts"].items():
        if e.get("display"):
            put(e["display"], "display_in_code", concept)
        for plural in e.get("arabic_plurals") or []:
            put(plural, "arabic_plural", concept)
        for gloss in e.get("english_glosses") or []:
            put(gloss, "gloss", concept)
    # A member's code is canonical wherever it is written, and it comes before
    # the concept spellings because a registry is its own namespace (section 13):
    # `kufi` is the stored value of the numbering system, not a short spelling
    # of the entry `ayah_numbering_kufi`.
    for kind, forms in data.get("registry_members", {}).items():
        for code in set(forms.values()):
            index.setdefault(code, ("canonical", f"{kind}:{code}", code))
    for form, concept in data["aliases"].items():
        if isinstance(concept, list):
            # A form shared by the values of two classifications (section 14).
            # It is canonical when it is the code of each; otherwise the finding
            # names both, and the column decides.
            codes = {data["concepts"][c]["code"] for c in concept}
            key = form.lower().replace("-", "_").replace(" ", "_")
            rule = "canonical" if codes == {key} else "spelling"
            index.setdefault(key, (rule, "|".join(concept), key))
            continue
        put(form, "spelling", concept)
    # The members of the closed sets, keyed `kind:code` so a member and a
    # concept never share a slot. A concept's spelling wins a form they share
    # (`hamzah` is the mark before it is the imam); a form that is itself a
    # member's code anywhere is never a finding (`hafs` names the rawi and is
    # also a recorded short form of the riwayah).
    codes = {code for kind in data.get("registry_members", {}).values() for code in kind.values()}
    for kind, forms in sorted(data.get("registry_members", {}).items()):
        for form, code in forms.items():
            key = form.lower().replace("-", "_").replace(" ", "_")
            if key == code or key in codes or len(key) < 3 or not ASCII_FORM.match(key):
                continue
            rule = "member" if ("_" in key or kind in PROPER_NAME_KINDS) else "generic"
            index.setdefault(key, (rule, f"{kind}:{code}", key))
    # The canonical name itself, so that a tree writing it both ways is seen.
    for concept, e in data["concepts"].items():
        have = index.get(e["code"])
        if have and have[0] == "canonical" and "|" in have[1]:
            continue
        index[e["code"]] = ("canonical", concept, e["code"])
    # A collection is named by adding `s` (section 11), so `suras` is `sura`
    # made plural: the same finding, counted under the singular. Only `s` is
    # added — `es` would make `boxes` a plural of `box`.
    for form, hit in list(index.items()):
        index.setdefault(form + "s", hit)
    # A single ordinary word is a hint, not a ruling.
    for form, (rule, concept, base) in list(index.items()):
        if rule == "spelling" and "_" not in form and form in GENERIC_WORDS:
            index[form] = ("generic", concept, base)
    for word in ignore_words:
        for form in (word, word + "s"):
            index.pop(form.lower().replace("-", "_").replace(" ", "_"), None)
    return index


# --- configuration ---------------------------------------------------------

CONFIG_KEYS = {"exclude", "ignore_words", "allow_gloss_in", "compatibility", "paths",
               "external_names"}


def find_config(paths, explicit):
    """`--config`, else the nearest .terminology.json above the audited paths."""
    if explicit:
        return explicit
    for path in paths:
        here = os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path) or ".")
        while True:
            candidate = os.path.join(here, CONFIG_NAME)
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(here)
            if parent == here:
                break
            here = parent
    return None


def load_config(path):
    if not path:
        return {"root": os.getcwd(), "exclude": [], "ignore_words": [],
                "allow_gloss_in": [], "compatibility": [], "paths": [],
                "external_names": [], "external": None, "file": None}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    unknown = sorted(k for k in raw if k not in CONFIG_KEYS and not k.startswith(("_", "$")))
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}; the keys are {sorted(CONFIG_KEYS)}")
    cfg = {key: list(raw.get(key) or []) for key in CONFIG_KEYS}
    cfg["root"] = os.path.dirname(os.path.abspath(path))
    cfg["file"] = path
    cfg["external"] = compile_external(cfg["external_names"], path)
    return cfg


def compile_external(patterns, path):
    """One pattern for the names the project quotes rather than chooses."""
    if not patterns:
        return None
    try:
        return re.compile("|".join(f"(?:{p})" for p in patterns))
    except re.error as exc:
        raise ValueError(f"{path}: external_names is not a regular expression: {exc}") from exc


def matches(rel, patterns):
    """A path matches a glob when the glob covers it or any directory above it."""
    rel = rel.replace(os.sep, "/")
    for pattern in patterns:
        pattern = pattern.rstrip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern + "/*"):
            return True
        # `src/poetry/**` and `src/poetry` both mean the directory and everything in it.
        bare = pattern[:-3] if pattern.endswith("/**") else pattern
        if rel == bare or rel.startswith(bare + "/"):
            return True
    return False


# --- scanning --------------------------------------------------------------

def files(paths, cfg):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(names):
                if name == CONFIG_NAME:
                    continue
                full = os.path.join(root, name)
                if suffix_of(name) in CODE_SUFFIXES or suffix_of(name) in PROSE_SUFFIXES:
                    if not matches(os.path.relpath(full, cfg["root"]), cfg["exclude"]):
                        yield full


def shown_path(path):
    """A path an agent can open from where it stands: relative to the cwd when
    the file is under it, otherwise as it was given."""
    rel = os.path.relpath(path)
    return rel if not rel.startswith("..") else path


def layer_of(rel, suffix, cfg):
    if matches(rel, cfg["compatibility"]):
        return "compatibility surface"
    if suffix in PROSE_SUFFIXES:
        return "prose"
    for name, pattern in LAYERS:
        if pattern.search(rel.replace(os.sep, "/")):
            return name
    return "internal"


def scan(paths, index, data, cfg):
    findings, used, counted = {}, {}, {"files": 0, "ignored_lines": 0, "allowed_glosses": 0,
                                       "external_names": 0}
    for path in files(paths, cfg):
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        counted["files"] += 1
        suffix = suffix_of(os.path.basename(path))
        prose = suffix in PROSE_SUFFIXES
        rel = os.path.relpath(path, cfg["root"])
        layer = layer_of(rel, suffix, cfg)
        gloss_allowed = matches(rel, cfg["allow_gloss_in"])
        for number, line in enumerate(text.splitlines(), 1):
            if IGNORE_LINE.search(line):
                counted["ignored_lines"] += 1
                continue
            if cfg["external"]:
                line, hidden = cfg["external"].subn(lambda m: " " * len(m.group(0)), line)
                counted["external_names"] += hidden
            for match in IDENTIFIER.finditer(line):
                identifier = match.group(0)
                for form, (rule, concept, base) in lookup(parts_of(identifier), index):
                    used.setdefault(concept, {}).setdefault(base, 0)
                    used[concept][base] += 1
                    if rule == "canonical":
                        continue
                    # Prose is meant to carry the display name and may quote a
                    # gloss, so only a wrong name is a finding there.
                    if prose and rule in ("display_in_code", "gloss", "generic"):
                        continue
                    if gloss_allowed and rule in ("gloss", "generic"):
                        counted["allowed_glosses"] += 1
                        continue
                    key = (path, number, identifier, form)
                    if key in findings:
                        findings[key]["count"] += 1
                        continue
                    canonical, display = name_of(data, concept)
                    findings[key] = {
                        "rule": rule,
                        "severity": RULES[rule][0],
                        "file": shown_path(path),
                        "line": number,
                        "identifier": identifier,
                        "found": form,
                        "concept": concept,
                        "canonical": canonical,
                        "display": display,
                        "layer": layer,
                        "known": layer == "compatibility surface" and bool(cfg["compatibility"]),
                        "count": 1,
                    }
    return list(findings.values()), used, counted


def canonical_uses(data, used):
    """Concepts written more than one way in this tree (section 26)."""
    out = []
    for concept, forms in sorted(used.items()):
        code = name_of(data, concept)[0]
        spellings = sorted(forms)
        if len(spellings) > 1:
            out.append({"concept": concept, "canonical": code,
                        "spellings": {f: forms[f] for f in spellings}})
    return out


def summarise(findings, mixed, counted, data, cfg):
    live = [f for f in findings if not f["known"]]
    by_layer = {}
    for f in live:
        by_layer.setdefault(f["layer"], {"errors": 0, "warnings": 0})
        by_layer[f["layer"]]["errors" if f["severity"] == "error" else "warnings"] += 1
    version = data.get("version") or {}
    return {
        "files_scanned": counted["files"],
        "findings": len(live),
        "errors": sum(1 for f in live if f["severity"] == "error"),
        "warnings": sum(1 for f in live if f["severity"] == "warning"),
        "known": len(findings) - len(live),
        "ignored_lines": counted["ignored_lines"],
        "allowed_glosses": counted["allowed_glosses"],
        "external_names": counted["external_names"],
        "concepts_mixed": len(mixed),
        "layers": by_layer,
        "config": cfg["file"],
        "snapshot": version.get("snapshot") or version.get("commit"),
        "entries": len(data["concepts"]),
        "draft_entries": sum(1 for e in data["concepts"].values() if e["status"] != "adopted"),
    }


# --- reporting -------------------------------------------------------------

def line_of(f):
    times = f" ×{f['count']}" if f["count"] > 1 else ""
    return (f"  {f['file']}:{f['line']}: {f['identifier']!r} has {f['found']!r}{times} "
            f"→ `{f['canonical']}` ({f['display']})  [{f['layer']}]")


def report(findings, mixed, summary, by, limit):
    print(f"audited {summary['files_scanned']} files against snapshot "
          f"{summary['snapshot'] or 'unstamped'} ({summary['entries']} entries, "
          f"{summary['draft_entries']} draft)"
          + (f", config {summary['config']}" if summary['config'] else ""))
    live = [f for f in findings if not f["known"]]
    known = [f for f in findings if f["known"]]
    if not live:
        print("ok — every name in this tree resolves to its canonical form")

    if by == "rule":
        groups = [(r, [f for f in live if f["rule"] == r]) for r in RULE_ORDER]
        title = lambda r, g: f"{len(g)} {RULES[r][0]}: {r} — {RULES[r][1]}"
    elif by == "file":
        names = sorted({f["file"] for f in live})
        groups = [(n, [f for f in live if f["file"] == n]) for n in names]
        title = lambda n, g: f"{n} — {len(g)} findings [{g[0]['layer']}]"
    else:
        order = sorted({f["concept"] for f in live},
                       key=lambda c: (-sum(1 for f in live if f["concept"] == c), c))
        groups = [(c, [f for f in live if f["concept"] == c]) for c in order]

        def title(c, g):
            forms = {}
            for f in g:
                forms[f["found"]] = forms.get(f["found"], 0) + f["count"]
            errors = sum(1 for f in g if f["severity"] == "error")
            return (f"`{g[0]['canonical']}` ({g[0]['display']}) — {len(g)} findings, "
                    f"{errors} errors: " + ", ".join(f"{k} ×{v}" for k, v in sorted(forms.items())))

    for key, group in groups:
        if not group:
            continue
        print(f"\n{title(key, group)}")
        group = sorted(group, key=lambda f: (f["severity"] != "error", f["file"], f["line"]))
        for f in group[:limit]:
            print(line_of(f))
        if len(group) > limit:
            print(f"  … and {len(group) - limit} more (raise --limit, or --json)")

    if known:
        print(f"\n{len(known)} on a compatibility surface — known, leave alone unless a "
              f"migration is planned:")
        seen = set()
        for f in known:
            k = (f["identifier"], f["found"])
            if k not in seen:
                seen.add(k)
                print(f"  {f['identifier']!r} has {f['found']!r} → `{f['canonical']}`  "
                      f"(first at {f['file']}:{f['line']})")
    if mixed:
        print(f"\n{len(mixed)} concepts written more than one way (section 26):")
        for m in mixed:
            forms = ", ".join(f"{k} ×{v}" for k, v in m["spellings"].items())
            print(f"  {m['canonical']}: {forms}")
    layers = ", ".join(f"{k}: {v['errors']}e/{v['warnings']}w" for k, v in
                       sorted(summary["layers"].items()))
    print(f"\n{summary['errors']} errors, {summary['warnings']} warnings, "
          f"{summary['findings']} findings" + (f" — {layers}" if layers else "")
          + (f"; {summary['known']} known" if summary["known"] else "")
          + (f"; {summary['ignored_lines']} lines ignored" if summary["ignored_lines"] else "")
          + (f"; {summary['external_names']} external names quoted"
             if summary.get("external_names") else ""))


def main(argv=None):
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or directories to audit")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    ap.add_argument("--strict", action="store_true", help="exit 1 when there are errors")
    ap.add_argument("--by", choices=("concept", "file", "rule"), default="concept",
                    help="how to group the report (default: concept)")
    ap.add_argument("--limit", type=int, default=20, help="findings printed per group")
    ap.add_argument("--config", help=f"project configuration (default: nearest {CONFIG_NAME})")
    ap.add_argument("--data", default=DATA, help="path to terminology.json")
    args = ap.parse_args(argv)

    try:
        data = load(args.data)
    except (OSError, ValueError) as exc:
        print(f"could not read the dictionary at {args.data}: {exc}", file=sys.stderr)
        return 2
    try:
        cfg = load_config(find_config(args.paths or ["."], args.config))
    except (OSError, ValueError) as exc:
        print(f"could not read the configuration: {exc}", file=sys.stderr)
        return 2
    paths = args.paths or cfg["paths"] or ["."]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print("no such path: " + ", ".join(missing), file=sys.stderr)
        return 2

    index = build_index(data, cfg["ignore_words"])
    findings, used, counted = scan(paths, index, data, cfg)
    if counted["files"] == 0:
        print("nothing audited: no file the audit reads under " + ", ".join(paths)
              + (f" (exclude patterns: {cfg['exclude']})" if cfg["exclude"] else ""),
              file=sys.stderr)
        return 2
    findings.sort(key=lambda f: (f["file"], f["line"], f["identifier"]))
    mixed = canonical_uses(data, used)
    summary = summarise(findings, mixed, counted, data, cfg)

    if args.json:
        json.dump({"summary": summary, "findings": findings, "mixed": mixed}, sys.stdout,
                  ensure_ascii=False, indent=1)
        print()
    else:
        report(findings, mixed, summary, args.by, args.limit)
    return 1 if (args.strict and summary["errors"]) else 0


if __name__ == "__main__":
    sys.exit(main())
