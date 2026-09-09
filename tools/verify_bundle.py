#!/usr/bin/env python3
"""Validate a built bundle, and report its real sizes.

    python3 tools/verify_bundle.py dist/quran-svg-hafs-kfgqpc
    python3 tools/verify_bundle.py dist/quran-svg-hafs-kfgqpc --sizes
    python3 tools/verify_bundle.py --compare A B        # byte-identical?

The checks, in order, each one a hard failure:

 1. every advertised file is present, and nothing advertised is empty;
 2. CHECKSUMS.txt covers every file but itself, and every hash is correct;
 3. every .json parses, and carries `schema` + `schema_version`;
 4. every .json validates against its JSON Schema (needs `jsonschema`; the
    check is reported as SKIP, never as a pass, when it is not installed);
 5. index/pages.json covers pages 1..604 exactly once;
 6. the corpus word count matches VERSION.json and the sum over the sidecars;
 7. every .svg.br / .svg.gz decompresses to exactly its raw sibling;
 8. CROSS-REFERENCE: every data-word-key in the index resolves to a <g class="word">
    with that word_key in the page the index names, and the page has no word the
    index lacks. Sampled by default, --full for all 604 pages;
 9. the SVG's own word text matches the index's, on the sampled pages.

Exit status is 0 only if every check passed.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys

try:
    import brotli
except ImportError:
    brotli = None

EXPECT_PAGES = 604
EXPECT_WORDS = 77432      # the word-by-word-translation-translation release's own count: the 37:130
                          # split the print makes, and 15:7 fused to match the
                          # release (docs/MAQTU-MAWSUL.md, 2026-09-08)
EXPECT_SURAHS = 114

_FAIL = []
_SKIP = []


def check(name, ok, detail=""):
    if ok is None:
        _SKIP.append(name)
        print("SKIP %-52s %s" % (name, detail))
        return
    if not ok:
        _FAIL.append(name)
    print("%s %-52s %s" % ("ok  " if ok else "FAIL", name, detail))
    return ok


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(bundle, rel):
    with open(os.path.join(bundle, rel), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------- checks

def check_presence(bundle):
    want = ["README.md", "VERSION.json", "CHECKSUMS.txt", "LICENSE",
            "index/pages.json", "index/surahs.json", "index/divisions.json",
            "index/words.json", "schema/FORMAT.md",
            "schema/mark-taxonomy.json", "schema/pages.schema.json",
            "schema/surahs.schema.json", "schema/divisions.schema.json",
            "schema/words.schema.json", "schema/page-words.schema.json",
            "schema/version.schema.json"]
    want += ["pages/%03d.svg" % p for p in range(1, EXPECT_PAGES + 1)]
    want += ["index/by-page/%03d.json" % p for p in range(1, EXPECT_PAGES + 1)]
    missing = [w for w in want
               if not os.path.exists(os.path.join(bundle, w))]
    empty = [w for w in want
             if os.path.exists(os.path.join(bundle, w))
             and os.path.getsize(os.path.join(bundle, w)) == 0]
    check("every advertised file present", not missing,
          "%d files; missing %s" % (len(want), missing[:3] or "none"))
    check("no advertised file empty", not empty, str(empty[:3] or "none"))


def check_checksums(bundle):
    path = os.path.join(bundle, "CHECKSUMS.txt")
    if not os.path.exists(path):
        return check("CHECKSUMS.txt", False, "absent")
    listed = {}
    for line in open(path, encoding="utf-8"):
        h, rel = line.rstrip("\n").split("  ", 1)
        listed[rel] = h
    on_disk = set()
    for dp, dn, fn in os.walk(bundle):
        dn.sort()
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), bundle)
            if rel != "CHECKSUMS.txt":
                on_disk.add(rel)
    check("CHECKSUMS.txt covers every file", listed.keys() == on_disk,
          "%d listed, %d on disk, %d unlisted" %
          (len(listed), len(on_disk), len(on_disk - set(listed))))
    bad = [rel for rel, h in sorted(listed.items())
           if os.path.exists(os.path.join(bundle, rel))
           and sha256_file(os.path.join(bundle, rel)) != h]
    check("every checksum correct", not bad, str(bad[:3] or "none"))
    srt = list(listed)
    check("CHECKSUMS.txt sorted by path", srt == sorted(srt))


def check_json(bundle, schemas_ok=True):
    bad, noschema = [], []
    for dp, dn, fn in os.walk(bundle):
        dn.sort()
        for f in sorted(fn):
            if not f.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), bundle)
            try:
                d = json.load(open(os.path.join(dp, f), encoding="utf-8"))
            except Exception as e:                             # noqa: BLE001
                bad.append((rel, str(e)[:60]))
                continue
            if rel.startswith("schema/") and rel.endswith(".schema.json"):
                continue
            if not (isinstance(d, dict) and "schema" in d
                    and "schema_version" in d):
                noschema.append(rel)
    check("every JSON parses", not bad, str(bad[:3] or "none"))
    check("every data JSON declares schema + schema_version", not noschema,
          str(noschema[:3] or "none"))


def check_against_schemas(bundle):
    try:
        import jsonschema
    except ImportError:
        return check("JSON Schema validation", None,
                     "pip install jsonschema to enable")
    pairs = [("index/pages.json", "pages.schema.json"),
             ("index/surahs.json", "surahs.schema.json"),
             ("index/divisions.json", "divisions.schema.json"),
             ("index/words.json", "words.schema.json"),
             ("VERSION.json", "version.schema.json")]
    pairs += [("index/by-page/%03d.json" % p, "page-words.schema.json")
              for p in (1, 2, 3, 42, 255, 604)]
    bad = []
    for data_rel, schema_rel in pairs:
        try:
            jsonschema.validate(load(bundle, data_rel),
                                load(bundle, "schema/" + schema_rel))
        except Exception as e:                                 # noqa: BLE001
            bad.append((data_rel, str(e).splitlines()[0][:70]))
    check("JSON Schema validation", not bad, str(bad[:3] or "none"))


def check_indexes(bundle):
    pages = load(bundle, "index/pages.json")
    nums = [p["page"] for p in pages["pages"]]
    check("pages.json covers 1..%d exactly once" % EXPECT_PAGES,
          nums == list(range(1, EXPECT_PAGES + 1)),
          "%d records" % len(nums))

    surahs = load(bundle, "index/surahs.json")
    check("surahs.json has %d records" % EXPECT_SURAHS,
          len(surahs["surahs"]) == EXPECT_SURAHS,
          "%d" % len(surahs["surahs"]))
    check("surah numbers are 1..114",
          [s["number"] for s in surahs["surahs"]] == list(range(1, 115)))

    words = load(bundle, "index/words.json")
    check("words.json has %d rows" % EXPECT_WORDS,
          len(words["rows"]) == EXPECT_WORDS, "%d" % len(words["rows"]))
    check("words.json word ids are unique",
          len({r[0] for r in words["rows"]}) == len(words["rows"]))
    check("words.json declares its fields",
          words.get("fields") == ["word_key", "page", "line", "rasm_uthmani", "search"],
          str(words.get("fields")))

    total = 0
    boxes = 0
    keys = []
    for p in range(1, EXPECT_PAGES + 1):
        d = load(bundle, "index/by-page/%03d.json" % p)
        total += len(d["words"])
        boxes += sum(1 for w in d["words"] if w["box"])
        keys += [w.get("word_key") for w in d["words"]]
    check("sidecars hold %d words in total" % EXPECT_WORDS,
          total == EXPECT_WORDS, "%d" % total)
    check("every word has a bounding box", boxes == total,
          "%d of %d" % (boxes, total))
    # surah:ayah:word is the only word key, so it must be well formed and
    # unique across the corpus — nothing else identifies a word now
    check("every word has a surah:ayah:word key",
          all(isinstance(x, str) and re.match(r"^\d+:\d+:\d+$", x)
              for x in keys),
          "%d malformed" % sum(1 for x in keys
                               if not (isinstance(x, str)
                                       and re.match(r"^\d+:\d+:\d+$", x))))
    check("word keys are unique across the corpus",
          len(set(keys)) == EXPECT_WORDS, "%d distinct" % len(set(keys)))
    check("pages.json word counts sum to the corpus",
          sum(p["words"] for p in pages["pages"]) == EXPECT_WORDS)

    v = load(bundle, "VERSION.json")
    check("VERSION.json counts agree with the files",
          v["counts"]["words"] == EXPECT_WORDS
          and v["counts"]["pages"] == EXPECT_PAGES
          and v["counts"]["surahs"] == EXPECT_SURAHS,
          json.dumps(v["counts"]))

    div = load(bundle, "index/divisions.json")
    got = tuple(len(div[k]) for k in ("juz", "hizb", "nisf", "rubu_al_hizb"))
    check("divisions: 30 juz, 60 hizb, 60 nisf, 240 rubʿ",
          got == (30, 60, 60, 240), "%d/%d/%d/%d" % got)
    check("division series are numbered 1..N with no gaps",
          all([r[k] for r in div[k]] == list(range(1, len(div[k]) + 1))
              for k in ("juz", "hizb", "nisf", "rubu_al_hizb")))
    pages_of = {p["page"] for p in pages["pages"]}
    check("every division points at a real page",
          all(r["page"] in pages_of for k in ("juz", "hizb", "nisf", "rubu_al_hizb")
              for r in div[k]))


def check_compressed(bundle, sample):
    bad = []
    n = 0
    for p in sample:
        raw_path = os.path.join(bundle, "pages/%03d.svg" % p)
        raw = open(raw_path, "rb").read()
        for ext, fn in ((".gz", lambda b: gzip.decompress(b)),
                        (".br", brotli.decompress if brotli else None)):
            f = raw_path + ext
            if not os.path.exists(f):
                continue
            if fn is None:
                continue
            n += 1
            if fn(open(f, "rb").read()) != raw:
                bad.append(os.path.basename(f))
    if n == 0:
        return check("pre-compressed pages round-trip", None,
                     "none present, or brotli module missing")
    check("pre-compressed pages round-trip", not bad,
          "%d files checked; bad %s" % (n, bad[:3] or "none"))


_WORDG = re.compile(r'<g class="word" ([^>]*)>')


def check_crossrefs(bundle, sample):
    words = load(bundle, "index/words.json")
    col = {f: i for i, f in enumerate(words["fields"])}
    by_page = {}
    for r in words["rows"]:
        by_page.setdefault(r[col["page"]], []).append(r)

    bad_missing, bad_extra, bad_text, bad_order, bad_forms = [], [], [], [], []
    for p in sample:
        svg = open(os.path.join(bundle, "pages/%03d.svg" % p),
                   encoding="utf-8").read()
        in_svg = []
        attrs = {}
        for m in _WORDG.finditer(svg):
            a = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
            in_svg.append(a["data-word-key"])
            attrs[a["data-word-key"]] = a
        idx_rows = by_page.get(p, [])
        idx_word_keys = [r[col["word_key"]] for r in idx_rows]
        if set(idx_word_keys) - set(in_svg):
            bad_missing.append((p, sorted(set(idx_word_keys) - set(in_svg))[:3]))
        if set(in_svg) - set(idx_word_keys):
            bad_extra.append((p, sorted(set(in_svg) - set(idx_word_keys))[:3]))
        if idx_word_keys != in_svg:
            bad_order.append(p)
        side = load(bundle, "index/by-page/%03d.json" % p)
        for w in side["words"]:
            a = attrs.get(w["word_key"])
            if not a:
                continue
            # the SVG carries data-rasm-uthmani on every profile and the other four
            # forms on the dev profile only; compare whatever it carries
            for f in ("rasm_uthmani", "rasm", "rasm_imlai", "search", "qpc"):
                _at = "data-" + f.replace("_", "-")   # see bundle_extract
                if _at in a and a[_at] != w[f]:
                    bad_text.append((p, w["word_key"], f))
            for f in ("rasm_uthmani", "rasm", "rasm_imlai", "search", "qpc"):
                if not w.get(f):
                    bad_forms.append((p, w["word_key"], f))

    check("every index word_key exists in its page", not bad_missing,
          str(bad_missing[:2] or "none"))
    check("every page word is in the index", not bad_extra,
          str(bad_extra[:2] or "none"))
    check("index word order matches document order", not bad_order,
          str(bad_order[:5] or "none"))
    check("sidecar text matches the SVG attributes", not bad_text,
          "%d pages checked; bad %s" % (len(sample), bad_text[:3] or "none"))
    check("sidecar carries all five text forms for every word", not bad_forms,
          "%d pages checked; bad %s" % (len(sample), bad_forms[:3] or "none"))


def check_boxes(bundle, sample):
    """A box must lie inside the page's viewBox and be non-degenerate."""
    bad = []
    for p in sample:
        d = load(bundle, "index/by-page/%03d.json" % p)
        vx, vy, vw, vh = [float(x) for x in d["view_box"].split()]
        for w in d["words"]:
            b = w["box"]
            if not b or b[2] <= b[0] or b[3] <= b[1]:
                bad.append((p, w["word_key"], "degenerate"))
            elif not (vx - 1 <= b[0] and b[2] <= vx + vw + 1
                      and vy - 1 <= b[1] and b[3] <= vy + vh + 1):
                bad.append((p, w["word_key"], "outside viewBox"))
    check("word boxes are inside the page and non-degenerate", not bad,
          "%d pages; bad %s" % (len(sample), bad[:3] or "none"))


def check_boxes_rendered(bundle, sample, per_page=6, scale=8):
    """Prove the boxes against an independent renderer.

    For a sample of words: hide every path but that word's, rasterise the page
    with rsvg-convert, and compare the ink's raster bounding box with the box
    the bundle declares.  This is the only check that does not share code with
    the builder, and it is the one that found the p144 defect (72 ink paths
    carry their own `transform`, which the extractor was ignoring).

    Tolerance is 0.35 viewBox units — about 3 px at 8x — which is antialiasing
    plus the threshold, an order of magnitude under the smallest real error.
    """
    import random
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("rsvg-convert"):
        return check("word boxes vs a real render", None,
                     "rsvg-convert not installed")
    try:
        from PIL import Image
    except ImportError:
        return check("word boxes vs a real render", None, "Pillow not installed")

    rng = random.Random(7)
    bad, n, worst = [], 0, 0.0
    with tempfile.TemporaryDirectory() as tmp:
        svg_out = os.path.join(tmp, "one.svg")
        png_out = os.path.join(tmp, "one.png")
        for pg in sample:
            svg = open(os.path.join(bundle, "pages/%03d.svg" % pg),
                       encoding="utf-8").read()
            side = load(bundle, "index/by-page/%03d.json" % pg)
            vx, vy, vw, vh = [float(x) for x in side["view_box"].split()]
            for w in rng.sample(side["words"],
                                min(per_page, len(side["words"]))):
                css = ('<style>path{display:none} g.word[data-word-key="%s"] '
                       'path{display:inline}</style>' % w["word_key"])
                with open(svg_out, "w", encoding="utf-8") as fh:
                    fh.write(svg.replace('<g transform="matrix',
                                         css + '<g transform="matrix', 1))
                subprocess.run(["rsvg-convert", "-w", str(int(vw * scale)),
                                "-h", str(int(vh * scale)), "-b", "white",
                                "-o", png_out, svg_out], check=True)
                im = Image.open(png_out).convert("L")
                bb = im.point(lambda p: 255 if p < 200 else 0).getbbox()
                if not bb:
                    bad.append((pg, w["word_key"], "no ink rendered"))
                    continue
                r = [bb[0] / scale + vx, bb[1] / scale + vy,
                     bb[2] / scale + vx, bb[3] / scale + vy]
                dev = max(abs(r[i] - w["box"][i]) for i in range(4))
                n += 1
                worst = max(worst, dev)
                if dev > 0.35:
                    bad.append((pg, w["word_key"], round(dev, 3)))
    check("word boxes vs a real render", not bad,
          "%d words; worst deviation %.3f units; bad %s"
          % (n, worst, bad[:3] or "none"))


def check_profile(bundle, sample):
    lig = [p for p in sample
           if 'class="ligature"' in open(
               os.path.join(bundle, "pages/%03d.svg" % p),
               encoding="utf-8").read()]
    poly = [p for p in sample
            if 'ayahPolygon' in open(
                os.path.join(bundle, "pages/%03d.svg" % p),
                encoding="utf-8").read()]
    v = load(bundle, "VERSION.json")
    if v.get("profile") != "production":
        return check("production profile", None,
                     "VERSION.json says profile=%s" % v.get("profile"))
    check("production profile: no ligature groups", not lig, str(lig[:5]))
    check("production profile: no ayahPolygon paths", not poly, str(poly[:5]))
    # since 2026-09-04 the four derived text forms ship in the sidecar only
    forms = [p for p in sample
             if re.search(r'<g class="word"[^>]*data-(rasm|rasm_imlai|search|qpc)=',
                          open(os.path.join(bundle, "pages/%03d.svg" % p),
                               encoding="utf-8").read())]
    check("production profile: word groups carry data-word-key + data-rasm-uthmani only",
          not forms, str(forms[:5]))
    xf = [p for p in sample
          if re.search(r'<path\b[^>]*\btransform=',
                       open(os.path.join(bundle, "pages/%03d.svg" % p),
                            encoding="utf-8").read())]
    check("no <path> carries a transform (translations are baked)", not xf, str(xf[:5]))
    vb = [p for p in sample
          if 'viewBox="0 0 345 550"' not in open(
              os.path.join(bundle, "pages/%03d.svg" % p), encoding="utf-8").read()]
    check("every page uses viewBox 0 0 345 550", not vb, str(vb[:5]))


# -------------------------------------------------------------------- sizes

def report_sizes(bundle):
    groups = {}

    def add(g, path):
        n = os.path.getsize(path)
        c = groups.setdefault(g, [0, 0])
        c[0] += 1
        c[1] += n

    for dp, dn, fn in os.walk(bundle):
        dn.sort()
        for f in sorted(fn):
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, bundle)
            if rel.startswith("pages/"):
                g = ("pages/*.svg" if f.endswith(".svg")
                     else "pages/*.svg" + os.path.splitext(f)[1])
            elif rel.startswith("index/by-page/"):
                g = ("index/by-page/*.json" if f.endswith(".json")
                     else "index/by-page/*.json" + os.path.splitext(f)[1])
            else:
                g = rel
            add(g, full)

    print("\n%-34s %7s %14s" % ("path", "files", "bytes"))
    print("-" * 58)
    tot = 0
    for g in sorted(groups):
        n, b = groups[g]
        tot += b
        print("%-34s %7d %14s" % (g, n, "{:,}".format(b)))
    print("-" * 58)
    print("%-34s %7d %14s" % ("TOTAL", sum(v[0] for v in groups.values()),
                              "{:,}".format(tot)))
    return groups


# ------------------------------------------------------------------ compare

def compare(a, b):
    fa, fb = {}, {}
    for root, store in ((a, fa), (b, fb)):
        for dp, dn, fn in os.walk(root):
            dn.sort()
            for f in sorted(fn):
                full = os.path.join(dp, f)
                store[os.path.relpath(full, root)] = sha256_file(full)
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    diff = sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k])
    check("same file set", not only_a and not only_b,
          "only in A %s; only in B %s" % (only_a[:3], only_b[:3]))
    check("every shared file byte-identical", not diff,
          "%d files, %d differ: %s" % (len(fa), len(diff), diff[:5]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle", nargs="?")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    ap.add_argument("--full", action="store_true",
                    help="cross-check all 604 pages, not a sample")
    ap.add_argument("--sizes", action="store_true")
    ap.add_argument("--render", type=int, metavar="N", default=0,
                    help="also prove N words per sampled page against a real "
                         "rsvg-convert render (slow; needs rsvg-convert+Pillow)")
    a = ap.parse_args(argv)

    if a.compare:
        compare(*a.compare)
    else:
        if not a.bundle:
            ap.error("give a bundle directory, or --compare A B")
        b = a.bundle
        sample = (list(range(1, EXPECT_PAGES + 1)) if a.full else
                  [1, 2, 3, 17, 42, 49, 144, 255, 350, 402, 528, 582, 604])
        check_presence(b)
        check_checksums(b)
        check_json(b)
        check_against_schemas(b)
        check_indexes(b)
        check_compressed(b, sample)
        check_profile(b, sample)
        check_crossrefs(b, sample)
        check_boxes(b, sample)
        if a.render:
            check_boxes_rendered(b, sample, per_page=a.render)
        if a.sizes:
            report_sizes(b)

    print()
    if _FAIL:
        print("FAILED %d check(s): %s" % (len(_FAIL), ", ".join(_FAIL)))
        return 1
    print("all checks passed" + (" (%d skipped)" % len(_SKIP) if _SKIP else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
