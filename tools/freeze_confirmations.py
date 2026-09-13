"""Write into each confirmation the split it confirmed, so it stops depending on a build.

A confirmation keyed to nothing but (page, wid, text) is only as good as the build it was
given for: three of the 117 had already stopped being exact labels because their run lost
a letter in a later build. This copies the letters build's own paths for the run into the
record. Records whose run the build no longer splits are left alone and listed -- those
are the ones to ask about again.
"""
import json, os, re, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "/home/abdullah/Dev/github.com/AbdullahObaid/quran-svg-pipeline")
from tools import letters_lib as L
from tools import build_letter_labels as B

PATH = os.path.join(L.ROOT, "docs", "defects", "letters_confirmed.jsonl")
_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')


def page_models(page):
    """(wid, letter index) → [path d, …] from the letters build."""
    out = {}
    try:
        words, _ = L.read_words(page, L.LETTERS_SVG)
    except Exception:
        return out
    for w in words:
        for m in _LETTER.finditer(w["inner"]):
            at = L.parse_attrs(m.group(1))
            ds = [L.parse_attrs(pm.group(1)).get("d") for pm in _PATH.finditer(m.group(2))
                  if L.parse_attrs(pm.group(1)).get("data-kind") == "body"]
            ds = [d for d in ds if d]
            if ds:
                out.setdefault((w["wid"], int(at.get("data-index", -1))), []).extend(ds)
    return out


def one(args):
    page, rows = args
    models = page_models(page)
    got = []
    for e in rows:
        words, _ = L.read_words(page)
        w = next((x for x in words if x["wid"] == e["wid"]), None)
        if w is None:
            got.append((e, None)); continue
        try:
            _, runs = B.align_runs(w)
        except Exception:
            got.append((e, None)); continue
        idx = next((i for lig, i in (runs or []) if lig["text"] == e.get("text", "")), None)
        if not idx:
            got.append((e, None)); continue
        ds = [models.get((e["wid"], i)) for i in idx]
        got.append((e, ds if all(ds) else None))
    return got


def main():
    rows = [json.loads(l) for l in open(PATH, encoding="utf-8") if l.strip()]
    by = {}
    for e in rows:
        by.setdefault(e["page"], []).append(e)
    frozen = {}
    missing = []
    with ProcessPoolExecutor(32) as ex:
        for res in ex.map(one, sorted(by.items())):
            for e, ds in res:
                k = (e["page"], e["wid"], e.get("text", ""))
                if ds:
                    frozen[k] = ds
                elif e.get("verdict") == "right":
                    missing.append(k)
    n = 0
    out = []
    for e in rows:
        k = (e["page"], e["wid"], e.get("text", ""))
        if e.get("verdict") == "right" and not e.get("model") and k in frozen:
            e["model"] = frozen[k]; n += 1
        out.append(json.dumps(e, ensure_ascii=False))
    if "--write" in sys.argv:
        import shutil, time
        shutil.copy(PATH, PATH + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
        open(PATH, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("%d of %d confirmations now carry their own split%s"
          % (n, len(rows), "" if "--write" in sys.argv else " (dry run, pass --write)"))
    for k in missing:
        print("   the build no longer splits p%d %s %s -- ask again" % k)


if __name__ == "__main__":
    main()
