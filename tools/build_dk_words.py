#!/usr/bin/env python3
"""Build a word cache from the DigitalKhatt layout of the KFGQPC V2 1421H print.

quran.com's mushaf-2 layout is wrong about which words are on the page for 25
pages (reported.json item 21; 18 of them in juz 29-30 — the juz-30 mechanism).
The DigitalKhatt DBs (QUL export, .cache/digitalkhatt/) model this exact print
and agree with MushafDatabase on every disputed page, so PAGE and LINE
membership come from them; the diacritic TEXT stays quran.com's uthmani
(measured best, CLAUDE.md ground rules), joined by location.

Output: .cache/words-dk/page-NNN.json in the exact shape page_words() reads
from cache, so the pipeline runs unchanged with cache_dir pointed here.

Location mapping: DigitalKhatt segments بَعْدَ مَا as TWO words (the print's
own segmentation), so in 13:37 its positions run one ahead of quran.com's
from position 9 on. The uthmani join maps through that shift; the two halves
of the compound take the split texts بَعْدَ and مَا directly.

    python3 tools/build_dk_words.py            # writes all 604 pages
    python3 tools/build_dk_words.py 599 600    # a range
"""
import json, os, sqlite3, sys, unicodedata

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DK = os.path.join(ROOT, ".cache", "digitalkhatt")
OUT = os.path.join(ROOT, ".cache", "words-dk")
SRC = os.path.join(ROOT, ".cache", "words")


def load_qc_text():
    """location -> (uthmani, imlaei) from the existing quran.com caches.
    Global, because on the 25 bad pages the right words live in NEIGHBOURING
    page files."""
    out = {}
    for pg in range(1, 605):
        f = os.path.join(SRC, "page-%03d.json" % pg)
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        for v in d["verses"]:
            for w in v["words"]:
                if w.get("char_type_name") != "word":
                    continue
                out["%s:%s" % (v["verse_key"], w["position"])] = (
                    w.get("text_uthmani", ""), w.get("text_imlaei", ""))
    return out


def qc_location(loc):
    """DigitalKhatt location -> quran.com location (the 13:37 بعد/ما shift)."""
    s, a, p = (int(x) for x in loc.split(":"))
    if (s, a) == (13, 37) and p >= 9:
        return "%d:%d:%d" % (s, a, p - 1), p == 9
    return loc, False


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    os.makedirs(OUT, exist_ok=True)
    lay = sqlite3.connect(os.path.join(DK, "digital-khatt-15-lines.db"))
    wdb = sqlite3.connect(os.path.join(DK, "digital-khatt-v2.db"))
    words = {int(r[0]): (r[1], r[2]) for r in
             wdb.execute("SELECT id, location, text FROM words")}
    qc = load_qc_text()

    missing = 0
    for pg in range(a, b + 1):
        rows = lay.execute(
            "SELECT line_number, line_type, CAST(first_word_id AS INT),"
            " CAST(last_word_id AS INT) FROM pages WHERE page_number=?"
            " ORDER BY line_number", (pg,)).fetchall()
        verses = {}
        for ln, ltype, lo, hi in rows:
            if ltype != "ayah":
                continue                      # surah frames / basmalah lines
            for wid in range(lo, hi + 1):
                if wid not in words:
                    continue
                loc, dk_text = words[wid]
                s, ay = (int(x) for x in loc.split(":")[:2])
                vk = "%d:%d" % (s, ay)
                if dk_text.startswith("۝") or dk_text.startswith("۝"):
                    # the ayah-end medallion: keep as 'end' so downstream
                    # consumers see the same shape quran.com files have
                    verses.setdefault(vk, []).append({
                        "position": int(loc.split(":")[2]),
                        "char_type_name": "end", "line_number": ln,
                        "text_uthmani": dk_text, "text_imlaei": dk_text})
                    continue
                qloc, is_split_second = qc_location(loc)
                ut = im = None
                if (13, 37) == (s, ay) and int(loc.split(":")[2]) in (8, 9):
                    # the print's two halves of بَعْدَ مَا: take the split
                    # texts directly (quran.com fuses them into one word)
                    fused = qc.get("13:37:8", ("", ""))
                    halves = fused[0].split(" ") if " " in fused[0] else None
                    if halves and len(halves) == 2:
                        ut = halves[0] if not is_split_second else halves[1]
                        im = ut
                if ut is None:
                    pair = qc.get(qloc)
                    if pair:
                        ut, im = pair
                    else:
                        ut = im = unicodedata.normalize("NFC", dk_text)
                        missing += 1
                verses.setdefault(vk, []).append({
                    "position": int(loc.split(":")[2]),
                    "char_type_name": "word", "line_number": ln,
                    "text_uthmani": ut, "text_imlaei": im})
        data = {"verses": [{"verse_key": vk, "words": ws}
                           for vk, ws in sorted(
                               verses.items(),
                               key=lambda kv: tuple(int(x) for x in
                                                    kv[0].split(":")))],
                "source": "digitalkhatt-1421H layout + uthmani text"}
        json.dump(data, open(os.path.join(OUT, "page-%03d.json" % pg), "w",
                             encoding="utf-8"), ensure_ascii=False)
    print("wrote pages %d-%d to %s | words with no uthmani join (kept "
          "DigitalKhatt text): %d" % (a, b, OUT, missing))


if __name__ == "__main__":
    main()
