/* mushaf.js — follow a recitation, word by word.
 *
 * The library owns the JOIN and the CLOCK; the caller owns the buttons.
 *
 * Three things here are worth not writing twice:
 *
 *   1. THE GUARD. Word timings come from a different decomposition of the
 *      same text, and two decompositions count words differently — p254
 *      13:37 is 19 words there and 20 here. Zipping the two lists blindly
 *      drifts silently from that word to the end of the ayah. Where the
 *      counts disagree the ayah is followed WHOLE, and the disagreement is
 *      reported rather than hidden.
 *   2. The per-ayah audio files, played back to back with the next one
 *      preloaded, so the seam between ayahs is not a stall.
 *   3. Greying the page once and re-inking the current position, which is
 *      one scoped CSS rule plus one handle swap per tick — not a walk over
 *      a thousand paths.
 *
 * Everything visible is the caller's: play/pause, a progress read-out, the
 * error message. Drive it with play() / pause() and read the handle.
 */

const API = 'https://api.quran.com/api/v4/recitations/';
const CDN = 'https://audio.qurancdn.com/';

/**
 * @param reciter   quran.com recitation id (9 = Minshawi, murattal)
 * @param timings   skip the network entirely: {aid: [url, [[startMs, endMs]…]]}
 * @param onWord    ({aid, index, count, file, files, whole}) on every change
 * @param onEnd     the last ayah finished
 * @param onError   the audio element failed; the handle is dead after this
 * @param paint     false leaves the ink alone and reports position only
 */
export async function followRecitation(page, {
  reciter = 9, endpoint = API, cdn = CDN, timings = null, timeout = 6000,
  grey = '#c9c4b8', ink = '#231f20', paint = true,
  onWord = null, onEnd = null, onError = null
} = {}) {
  const n = page.number;
  if (!n && !timings) throw new Error('followRecitation needs the page number: new MushafPage(svg, {number})');

  let raw = timings;
  if (!raw) {
    const url = `${endpoint}${reciter}/by_page/${n}?fields=segments&per_page=60`;
    const res = await fetch(url, { signal: AbortSignal.timeout(timeout) });
    if (!res.ok) throw new Error('HTTP ' + res.status + ' from ' + url);
    raw = {};
    for (const e of (await res.json()).audio_files) {
      /* segments are [wordIndex, ?, startMs, endMs] and are not always sorted */
      const segs = (e.segments || []).slice().sort((a, b) => a[1] - b[1]);
      raw[e.verse_key] = [e.url, segs.map(s => [s[2], s[3]])];
    }
  }

  const ayahs = [], mismatches = [];
  for (const aid of page.ayahKeys()) {
    if (!raw[aid]) continue;
    const ayah = page.ayah(aid);
    const times = raw[aid][1];
    const perWord = ayah.words().length === times.length;
    if (!perWord) mismatches.push({ aid, ours: ayah.words().length, theirs: times.length });
    ayahs.push({ aid, ayah, url: raw[aid][0], times, perWord });
  }
  if (!ayahs.length) throw new Error('no timings cover page ' + n);

  const view = page.el.ownerDocument.defaultView;
  const theme = paint ? page.theme({ ink: grey }) : null;
  let lit = null;
  function show(a, i) {
    if (lit) { lit.remove(); lit = null; }
    if (!paint || !a) return;
    const target = a.perWord ? a.ayah.words()[i] : a.ayah;
    if (target) lit = page.highlight(target, { fill: ink });
  }

  const audio = new view.Audio(), ahead = new view.Audio();
  audio.preload = 'auto'; ahead.preload = 'auto';
  let file = 0, word = -1, raf = 0, dead = false;

  function load(i) {
    file = i;
    word = -1;
    audio.src = cdn + ayahs[i].url;
    if (ayahs[i + 1]) { ahead.src = cdn + ayahs[i + 1].url; ahead.load(); }
  }

  function frame() {
    raf = view.requestAnimationFrame(frame);
    if (audio.paused) return;
    const a = ayahs[file], ms = audio.currentTime * 1000;
    let i = -1;
    for (let k = 0; k < a.times.length; k++) if (ms >= a.times[k][0]) i = k;
    if (i === word) return;
    word = i;
    show(a, i);
    if (onWord) onWord({ aid: a.aid, index: i, count: a.times.length,
                         file, files: ayahs.length, whole: !a.perWord });
  }

  audio.addEventListener('ended', () => {
    if (file + 1 < ayahs.length) { load(file + 1); audio.play().catch(() => {}); return; }
    show(null);
    if (onEnd) onEnd();
  });
  audio.addEventListener('error', () => {
    if (dead) return;                       /* src='' during remove() fires this */
    if (onError) onError(new Error('the recitation audio could not be loaded'));
  });

  raf = view.requestAnimationFrame(frame);

  return {
    ayahs, mismatches,
    get playing() { return !audio.paused; },
    get file() { return file; },
    get index() { return word; },
    get segments() { return ayahs.reduce((t, a) => t + a.times.length, 0); },
    play() { if (!audio.src) load(0); return audio.play(); },
    pause() { audio.pause(); },
    seek(i) { load(Math.min(ayahs.length - 1, Math.max(0, i))); if (!audio.paused) audio.play().catch(() => {}); },
    remove() {
      dead = true;
      view.cancelAnimationFrame(raf);
      audio.pause(); audio.src = ''; ahead.src = '';
      show(null);
      if (theme) theme.remove();
    }
  };
}
