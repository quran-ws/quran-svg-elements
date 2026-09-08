#!/usr/bin/env python3
"""Taxonomy audit: the catalog vocabulary, permanently gated.

After the 2026-08-27 taxonomy rollout (docs/defects/mark_taxonomy.md) the
emitted vocabulary is a closed set. This audit rebuilds every page and holds
five lines at once:

  1. every rare-sign site in .cache/marks/rare_places.json emits its named
     tag on the page that draws it (saktah x5, seen-reading x2), plus the
     one small-noon at 21:88 (p329);
  2. no emitted data-mark / data-mark-part / data-kind value falls outside
     the canonical vocabulary — any '+' compound is an instant fail;
  3. no stale waqf name (pre-rename "waqf qila"/"waqf sali"/"waqf taanuq",
     or anything but the five catalog values) reaches a data-waqf;
  4. the two zeros are text-derived, so their word counts are exact:
     3,970 words hold a sifr-mustadir (3,988 codepoint occurrences — 18
     words such as أُو۟لُوا۟ carry two) and 66 a sifr-mustatil, mushaf-wide;
  5. every muanaqah master carries a data-pair shared with exactly one
     partner, and every data-form value is legal.

    python3 tools/audit_taxonomy.py [first last [jobs]]   # default 1 604 16

Exit 1 with a per-page FAIL list on any violation; exit 0 with a one-line
summary otherwise. Counts (4) and pair completeness (5) are enforced only
when the run covers the full 1..604 range.
"""
import json, os, re, subprocess, sys
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))

# The closed vocabulary, mirrored from what tools/assign_words.py can emit:
# harakat + their tanweens, the fixed signs, the letter-dot family, the
# taxonomy names of 2026-08-27 (two zeros, the seven U+06DC jobs, the sajdah
# split, small-noon), and the two standalone ornaments. `pause` remains the
# name of the waqf family (typed via data-waqf) and of the three dotted rare
# signs not yet split (imalah/ishmam/tashil — decision pending).
ALLOWED_MARKS = {
    "fatha", "kasra", "damma", "fathatan", "kasratan", "dammatan",
    "shadda", "sukun", "maddah", "hamza", "wasla",
    "small-alef", "small-waw", "small-ya", "small-noon",
    "sifr-mustadir", "sifr-mustatil", "meem-iqlab",
    "dot", "two-dots", "three-dots",
    "pause", "saktah", "seen-reading", "imalah", "ishmam", "tashil",
    "muanaqah", "wasl-awla", "waqf-awla", "waqf-jaiz", "waqf-lazim",
    "sajdah-line", "sajdah-sign", "hizb",
}
ALLOWED_KINDS = {"body", "mark", "ayah-marker-ornament", "ayah-number",
                 "header-ink", "ornament",   # one-item headers + banner decoration (2026-08-28)
                 "page-number", "running-head"}   # p17's page furniture (2026-09-04)
# the standalone <g class="sajdah-mark"> keeps the family name "sajdah" at
# GROUP level; its paths carry the split names sajdah-line / sajdah-sign
ALLOWED_GROUP_MARKS = {"sajdah", "hizb"}
ALLOWED_WAQF = {"waqf-lazim", "waqf-awla", "waqf-jaiz", "wasl-awla",
                "muanaqah"}
ALLOWED_FORM = {"stacked", "staggered"}
# text-derived, tolerance 0: WORDS containing the sign, mushaf-wide. The
# catalog's 3,988 for the round zero counts CODEPOINTS; 18 words (أُو۟لُوا۟
# and its kin, plus تَا۟يْـَٔسُوا۟) carry two, so 3,988 - 18 = 3,970 words.
# No word carries two upright zeros, so 66 = 66 either way.
SIFR_MUSTADIR_WORDS = 3970
SIFR_MUSTATIL_WORDS = 66

_TAG = re.compile(r"<g\b[^>]*>|</g>|<path\b[^>]*?/?>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def scan_page(pg):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import assign_words as aw
    _, svg, _, _ = aw.assign_page("hafs/kfqc", pg,
                                  os.path.join(ROOT, ".cache", "words"))
    rare = json.load(open(os.path.join(ROOT, ".cache", "marks",
                                       "rare_places.json")))
    rare_refs = {ref: name for name, refs in rare.items()
                 if isinstance(refs, list) for ref in refs}

    viol = []
    stack = []                      # attr dicts of open <g>
    word_marks = {}                 # word key -> set of mark names inside it
    pairs = Counter()
    mnq_masters = 0
    mnq_paired = 0
    marks_seen = Counter()

    def word_ctx():
        for at in reversed(stack):
            if at.get("class") == "word":
                return at
        return None

    for m in _TAG.finditer(svg):
        t = m.group(0)
        if t == "</g>":
            if stack:
                stack.pop()
            continue
        at = dict(_ATTR.findall(t))
        if t.startswith("<g"):
            # standalone <g ... data-mark="hizb|sajdah-*"> groups carry the
            # mark name at group level; vocabulary applies there too
            gm = at.get("data-mark")
            if gm:
                marks_seen[gm] += 1
                if "+" in gm or gm not in (ALLOWED_MARKS
                                           | ALLOWED_GROUP_MARKS):
                    viol.append("vocab: group data-mark=%r" % gm)
            if not t.endswith("/>"):
                stack.append(at)
            continue
        # <path ...>
        kd = at.get("data-kind")
        if kd is not None and kd not in ALLOWED_KINDS:
            viol.append("kind: data-kind=%r" % kd)
        mk = at.get("data-mark")
        mp = at.get("data-mark-part")
        for v, part in ((mk, False), (mp, True)):
            if v is None:
                continue
            marks_seen[v] += 1
            if "+" in v or v not in ALLOWED_MARKS:
                viol.append("vocab: data-mark%s=%r"
                            % ("-part" if part else "", v))
        wq = at.get("data-waqf")            # legacy; new emissions put the
        if wq is None and (mk or mp) in (   # type in data-mark itself
                "wasl-awla", "waqf-awla", "waqf-jaiz", "waqf-lazim"):
            wq = mk or mp
        if wq is not None and wq not in ALLOWED_WAQF:
            viol.append("waqf: data-waqf=%r" % wq)
        # data-mark-family is a SPACE-SEPARATED token list, like `class`: a
        # mark can belong to more than one family, and the three tanween
        # belong to two ("diacritic tanween") because they are vowel marks
        # AND the tanween. Validate each token, never the whole string.
        mf = at.get("data-mark-family")
        if mf is not None:
            bad = [t for t in mf.split()
                   if t not in {"waqf", "tanween", "dots", "sifr",
                                "sajdah", "reading-sign", "diacritic"}]
            if bad or not mf.split():
                viol.append("family: data-mark-family=%r" % mf)
        fm = at.get("data-form")
        if fm is not None:
            if fm not in ALLOWED_FORM:
                viol.append("form: data-form=%r" % fm)
            if mk not in ("fathatan", "kasratan", "dammatan"):
                viol.append("form: data-form on data-mark=%r" % mk)
        pr = at.get("data-pair")
        if pr is not None:
            pairs[pr] += 1
        if (wq == "muanaqah" or mk == "muanaqah") and mk is not None:
            mnq_masters += 1
            if pr is not None:
                mnq_paired += 1
        w = word_ctx()
        if w is not None and (mk or mp):
            key = w.get("data-wid")
            word_marks.setdefault((key, w.get("data-uthmani", "")),
                                  set()).add(mk or mp)

    if mnq_masters != mnq_paired:
        viol.append("pair: %d muanaqah master(s) without data-pair"
                    % (mnq_masters - mnq_paired))
    for pid, n in pairs.items():
        if n != 2:
            viol.append("pair: %s appears %dx on page (want 2)" % (pid, n))

    sifr_d = sum(1 for (_k, _u), mks in word_marks.items()
                 if "sifr-mustadir" in mks)
    sifr_t = sum(1 for (_k, _u), mks in word_marks.items()
                 if "sifr-mustatil" in mks)

    # rare sites: a word on this page whose text carries the U+06DC (or the
    # small noon U+06E8) must hold the job-named tag
    rare_hit = []
    for (key, uth), mks in word_marks.items():
        # key is the word's data-wid, "surah:ayah:word"; the rare-site table is
        # keyed "surah:ayah"
        ref = ":".join((key or "").split(":")[:2])
        if "ۜ" in uth and ref in rare_refs:
            name = rare_refs[ref]
            rare_hit.append(ref)
            if name not in mks:
                viol.append("rare: %s wants %s, word emits %s"
                            % (ref, name, sorted(mks)))
        if "ۨ" in uth:
            rare_hit.append("%s(small-noon)" % ref)
            if "small-noon" not in mks:
                viol.append("rare: %s wants small-noon, word emits %s"
                            % (ref, sorted(mks)))

    return {"page": pg, "violations": viol, "pairs": dict(pairs),
            "sifr_mustadir_words": sifr_d, "sifr_mustatil_words": sifr_t,
            "rare_hit": rare_hit, "marks": dict(marks_seen)}


def main():
    args = [a for a in sys.argv[1:] if a.isdigit()]
    a = int(args[0]) if args else 1
    b = int(args[1]) if len(args) > 1 else a if args else 604
    jobs = int(args[2]) if len(args) > 2 else 16
    if os.environ.get("QSVG_TXCHILD"):
        print(json.dumps(scan_page(a)))
        return
    import concurrent.futures as cf

    def run(pg):
        env = dict(os.environ, QSVG_TXCHILD="1", QSVG_ROOT=ROOT)
        out = subprocess.run([sys.executable, os.path.abspath(__file__),
                              str(pg)], capture_output=True, text=True,
                             env=env)
        try:
            return json.loads(out.stdout.strip().splitlines()[-1])
        except Exception:
            return {"page": pg, "violations":
                    ["error: %s" % (out.stderr or out.stdout)[-300:]],
                    "pairs": {}, "sifr_mustadir_words": 0,
                    "sifr_mustatil_words": 0, "rare_hit": [], "marks": {}}

    fails = []
    pairs = Counter()
    sifr_d = sifr_t = 0
    rare_hit = []
    vocab = Counter()
    with cf.ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(run, range(a, b + 1)):
            if r["violations"]:
                fails.append((r["page"], r["violations"]))
            pairs.update(r["pairs"])
            sifr_d += r["sifr_mustadir_words"]
            sifr_t += r["sifr_mustatil_words"]
            rare_hit.extend(r["rare_hit"])
            vocab.update(r["marks"])

    full = (a, b) == (1, 604)
    if full:
        if sifr_d != SIFR_MUSTADIR_WORDS:
            fails.append(("mushaf", ["sifr-mustadir words %d != %d"
                                     % (sifr_d, SIFR_MUSTADIR_WORDS)]))
        if sifr_t != SIFR_MUSTATIL_WORDS:
            fails.append(("mushaf", ["sifr-mustatil words %d != %d"
                                     % (sifr_t, SIFR_MUSTATIL_WORDS)]))
        rare = json.load(open(os.path.join(ROOT, ".cache", "marks",
                                           "rare_places.json")))
        want_refs = {r for k, v in rare.items()
                     if isinstance(v, list) for r in v}
        missing = want_refs - set(rare_hit)
        if missing:
            fails.append(("mushaf", ["rare site(s) never seen: %s"
                                     % sorted(missing)]))
        if not any("small-noon" in h for h in rare_hit):
            fails.append(("mushaf", ["small-noon site (21:88) never seen"]))
    for pid, n in pairs.items():
        if n != 2:
            fails.append(("mushaf", ["pair %s appears %dx (want 2)"
                                     % (pid, n)]))

    if fails:
        for pg, vs in sorted(fails, key=lambda t: str(t[0])):
            for v in vs:
                print("FAIL p%s: %s" % (pg, v))
        print("audit_taxonomy: %d page(s) FAILED" % len(fails))
        sys.exit(1)
    print("audit_taxonomy OK: pages %d-%d, %d mark names, "
          "%d muanaqah pairs %s, sifr words %d/%d, rare sites %s"
          % (a, b, len(vocab), len(pairs), sorted(pairs), sifr_d, sifr_t,
             sorted(set(rare_hit))))


if __name__ == "__main__":
    main()
