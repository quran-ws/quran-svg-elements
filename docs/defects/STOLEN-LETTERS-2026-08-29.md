# Stolen-letter hunt — 2026-08-29 — NEGATIVE RESULT

**Bottom line: this did NOT find new thefts.** The three confirmed by eye
(p384 ٱلْعَزِيزُ and ٱلْعَلِيمُ, p579 ٱللَّهُ) are still the only ones. Everything
below is the record of what was measured and why it failed, so the next
attempt starts from here instead of repeating it.

## What was being hunted

A word whose `<g class="ligature">` holds NO letter ink while a neighbour on
the same line draws a detached stroke in the gap. This is the one family every
currently-green audit is blind to: a stolen BODY piece leaves every mark count
perfect, and the territory audit and both position laws inspect only marks.

## The signature, measured on the three confirmed cases

| page | word | stroke | ink ratio to holder |
|---|---|---|---|
| 384 | ٱلْعَزِيزُ 27:78:7 | 2.4 x 15.0 | 0.09 |
| 384 | ٱلْعَلِيمُ 27:78:8 | 3.0 x 15.8 | 0.06 |
| 579 | ٱللَّهُ 76:11:2 | 2.7 x 14.9 | 0.07 |

A narrow tall stroke carrying 6-9% of its holder's ink, touching both words.

## Why it cannot be made proof-class

The ink-ratio distribution over all 456 candidates has **NO EMPTY BAND** — it
decays smoothly from 0.03 to >=1 with no gap. By this project's rule that
makes it a graded prior only, never a proof.

Worse, the top of the ranking is dominated by an ORTHOGRAPHIC PATTERN, not by
defects. Two spot-checks, read group by group:

- **p188 9:11:3 وَأَقَامُوا۟** — its final group is the silent alef of واو
  الجماعة and is empty. The alif-shaped stroke my filter blamed the neighbour
  for is ٱلصَّلَوٰةَ's OWN wasla alif at 245.0-247.9, correctly owned. The
  silent alef simply is not drawn as separate ink; it is fused into the
  preceding "مو" run. A CUT question, not a theft.
- **p231 11:85:2 أَوْفُوا۟** — identical shape; the stroke is
  ٱلْمِكْيَالَ's own alif at 300.6-303.3.

66 of the 456 rows are that pattern outright, and 15 of the 57 best-ranked
ones. Since the confirmed thefts sit at 0.06-0.09 — inside the same range —
the quantity cannot separate them.

## Three wrong versions, recorded so they are not rebuilt

1. Read `atom["seg"]`, inheriting the `audit_ligatures` index-pairing bug;
   reported بِمَا as missing "بما", the whole word. 1074 rows.
2. Accepted "the neighbour covers the gap" — meaningless for a word-initial
   or word-final letter, because the gap is then an invented 22u window that
   the next word fills by simply existing. 493 rows.
3. Accepted any detached stroke, which let the holder's ENTIRE WORD (18-35u
   wide) qualify. 204 rows.

## What would actually reach this family

Not geometry from inside our own decomposition — the confirmed cases and the
fused silent alef are geometrically identical. It needs an OUTSIDE opinion at
the LIGATURE CUT level: DigitalKhatt or MushafDatabase saying how many runs
this word draws and where they start. Nobody has compared at that level, and
it needs no repetition of the word-form (which is why `audit_formshape`
cannot reach p71/p413/p546 either — those forms occur 2-5 times).

## The ranked list (a PRIOR — do not treat as defects)

| page | word key | word | letter | held by | stroke | ratio |
|---|---|---|---|---|---|---|
| 231 | 11:85:2 | أَوْفُوا۟ | ا | ٱلْمِكْيَالَ | 2.7x14.4 | 0.031 |
| 475 | 40:67:27 | أَجَلࣰا | ا | وَلِتَبْلُغُوٓا۟ | 2.7x15.0 | 0.035 |
| 201 | 9:91:4 | وَلَا | و | ٱلضُّعَفَآءِ | 5.3x6.1 | 0.039 |
| 437 | 35:22:4 | وَلَا | و | ٱلْأَحْيَآءُ | 5.3x6.1 | 0.041 |
| 92 | 4:90:28 | وَأَلْقَوْا۟ | ا | إِلَيْكُمُ | 3.0x14.7 | 0.043 |
| 111 | 5:23:12 | فَإِذَا | ا | دَخَلْتُمُوهُ | 5.4x7.6 | 0.043 |
| 148 | 6:151:16 | أَوْلَٰدَكُم | ا | تَقْتُلُوٓا۟ | 2.7x15.0 | 0.043 |
| 227 | 11:46:20 | أَن | ا | أَعِظُكَ | 4.7x6.5 | 0.044 |
| 124 | 5:100:9 | ٱلْخَبِيثِۚ | ا | كَثْرَةُ | 4.6x6.4 | 0.045 |
| 282 | 17:7:18 | أَوَّلَ | ا | دَخَلُوهُ | 4.7x6.5 | 0.047 |
| 92 | 4:91:22 | أَيْدِيَهُمْ | ا | وَيَكُفُّوٓا۟ | 3.3x16.1 | 0.048 |
| 124 | 5:97:9 | ٱلْحَرَامَ | ا | وَٱلشَّهْرَ | 2.9x15.8 | 0.048 |
| 188 | 9:12:11 | أَئِمَّةَ | ا | فَقَٰتِلُوٓا۟ | 2.9x15.8 | 0.048 |
| 123 | 5:92:9 | أَنَّمَا | ا | فَٱعْلَمُوٓا۟ | 3.0x16.3 | 0.049 |
| 273 | 16:64:8 | ٱلَّذِى | ى | ٱخْتَلَفُوا۟ | 3.0x16.3 | 0.049 |
| 188 | 9:11:3 | وَأَقَامُوا۟ | ا | ٱلصَّلَوٰةَ | 2.9x15.8 | 0.050 |
| 544 | 58:13:14 | فَأَقِيمُوا۟ | ا | ٱلصَّلَوٰةَ | 2.7x14.4 | 0.050 |
| 155 | 7:38:20 | إِذَا | ا | ٱدَّارَكُوا۟ | 5.4x7.6 | 0.051 |
| 436 | 35:12:2 | يَسْتَوِى | ى | ٱلْبَحْرَانِ | 2.6x16.4 | 0.051 |
| 548 | 59:21:3 | هَٰذَا | ا | ٱلْقُرْءَانَ | 2.9x15.8 | 0.052 |
| 47 | 2:277:6 | وَأَقَامُوا۟ | ا | ٱلصَّلَوٰةَ | 2.9x15.8 | 0.053 |
| 95 | 4:103:12 | فَأَقِيمُوا۟ | ا | ٱلصَّلَوٰةَۚ | 2.9x15.8 | 0.053 |
| 568 | 70:3:3 | ذِى | ى | ٱلْمَعَارِجِ | 3.0x16.3 | 0.053 |
| 30 | 2:196:70 | أَنَّ | ا | وَٱعْلَمُوٓا۟ | 2.9x15.8 | 0.054 |
| 586 | 81:2:1 | وَإِذَا | ا | ٱلنُّجُومُ | 2.7x15.0 | 0.055 |
| 260 | 14:37:14 | لِيُقِيمُوا۟ | ا | ٱلصَّلَوٰةَ | 2.9x15.8 | 0.056 |
| 323 | 21:16:4 | وَٱلْأَرْضَ | وا | ٱلسَّمَآءَ | 5.3x6.1 | 0.056 |
| 479 | 41:26:6 | لِهَٰذَا | ا | ٱلْقُرْءَانِ | 2.9x15.8 | 0.057 |
| 270 | 16:27:14 | أُوتُوا۟ | ا | ٱلْعِلْمَ | 3.0x16.3 | 0.059 |
| 385 | 27:92:2 | أَتْلُوَا۟ | ا | ٱلْقُرْءَانَۖ | 2.7x15.0 | 0.059 |
| 407 | 30:25:6 | وَٱلْأَرْضُ | و | ٱلسَّمَآءُ | 5.3x6.1 | 0.059 |
| 242 | 12:62:9 | إِذَا | ا | ٱنقَلَبُوٓا۟ | 2.9x15.8 | 0.061 |
| 362 | 25:30:7 | هَٰذَا | ا | ٱلْقُرْءَانَ | 3.1x16.8 | 0.061 |
| 588 | 83:31:1 | وَإِذَا | ا | ٱنقَلَبُوٓا۟ | 3.0x16.3 | 0.061 |
| 168 | 7:147:5 | ٱلْـَٔاخِرَةِ | ا | وَلِقَآءِ | 5.3x6.1 | 0.062 |
| 300 | 18:54:4 | هَٰذَا | ا | ٱلْقُرْءَانِ | 3.1x17.0 | 0.062 |
| 41 | 2:251:14 | وَلَوْلَا | و | يَشَآءُۗ | 5.3x6.1 | 0.063 |
| 283 | 17:9:2 | هَٰذَا | ا | ٱلْقُرْءَانَ | 3.0x16.3 | 0.063 |
| 197 | 9:63:3 | أَنَّهُۥ | ا | يَعْلَمُوٓا۟ | 2.9x15.8 | 0.064 |
| 267 | 15:91:2 | جَعَلُوا۟ | ا | ٱلْقُرْءَانَ | 3.0x16.3 | 0.064 |
| 278 | 16:94:10 | وَتَذُوقُوا۟ | ا | ٱلسُّوٓءَ | 2.7x15.0 | 0.064 |
| 399 | 29:24:7 | قَالُوا۟ | ا | ٱقْتُلُوهُ | 3.0x16.3 | 0.065 |
| 446 | 37:4:1 | إِنَّ | ا | ذِكْرًا | 2.6x14.5 | 0.065 |
| 235 | 12:3:9 | هَٰذَا | ا | ٱلْقُرْءَانَ | 3.1x16.8 | 0.068 |
| 469 | 40:25:6 | قَالُوا۟ | ا | ٱقْتُلُوٓا۟ | 3.1x16.8 | 0.073 |
| 118 | 5:60:18 | وَٱلْخَنَازِيرَ | و | ٱلْقِرَدَةَ | 5.4x7.6 | 0.074 |
| 387 | 28:18:7 | ٱلَّذِى | ى | ٱسْتَنصَرَهُۥ | 2.9x15.8 | 0.074 |
| 506 | 46:32:13 | دُونِهِۦٓ | نه | أَوْلِيَآءُۚ | 2.9x15.8 | 0.074 |
| 185 | 8:62:11 | بِنَصْرِهِۦ | ه | وَبِٱلْمُؤْمِنِينَ | 9.9x10.8 | 0.087 |
| 47 | 2:279:16 | وَلَا | و | تَظْلِمُونَ | 9.7x10.3 | 0.088 |
| 143 | 6:120:8 | ٱلْإِثْمَ | ا | يَكْسِبُونَ | 9.7x10.3 | 0.089 |
| 35 | 2:224:8 | وَتَتَّقُوا۟ | ا | وَتُصْلِحُوا۟ | 9.9x10.8 | 0.091 |
| 242 | 12:56:14 | وَلَا | و | نَّشَآءُۖ | 5.3x6.1 | 0.092 |
| 248 | 12:110:14 | وَلَا | و | نَّشَآءُۖ | 5.3x6.1 | 0.092 |
| 341 | 22:77:3 | ءَامَنُوا۟ | ا | ٱرْكَعُوا۟ | 9.3x9.5 | 0.096 |
| 180 | 8:28:9 | أَجْرٌ | ا | عِندَهُۥٓ | 4.4x5.9 | 0.098 |
| 237 | 12:21:2 | ٱلَّذِى | ى | ٱشْتَرَىٰهُ | 2.9x15.8 | 0.099 |
