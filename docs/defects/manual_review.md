# What still needs a person

Everything a rule could settle has been settled. These are the decisions left, and they are of four different kinds — each needs something different from you.

| what | how many | what the decision is |
|---|---|---|
| adjudicated ours | 135 | our ink is wrong and no override could reach it — usually because the fix crosses a line, or the neighbour it would move ink to is one the adjudicator says the reference got wrong |
| unresolved | 28 | we and MushafDatabase disagree and the QCF widths, the joining rules and the text all fail to separate us. You look and say which is right |
| dot cluster | 36 | a cluster where the label, the contour count and the welded-member count are identical between meaning two dots and meaning three. Only the drawn extent separates them |
| too many pieces | 8 | the word draws more connected runs of ink than its spelling allows, so it is provably holding a neighbour's fragment |
| we look right, confirm | 26 | the adjudicator says **MushafDatabase** is wrong here, not us. Worth a glance, because if it is right we have a defect the measure is crediting us for |

Start the platform with `python3 tools/review_server.py`, then follow the links. Restart it and clear `.cache/words-svg/hafs-kfqc` after any pipeline change or it serves a stale build.

## Pages, worst first

### [page 567](http://127.0.0.1:8777/?page=567&step=audit&user=abdullah) — 7 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلۡمَآءُ | `69:11:4` | adjudicated ours | our width is off by 5.57, theirs by 1.35 |
| ٱلسَّمَآءُ | `69:16:2` | adjudicated ours | our width is off by 3.60, theirs by 0.19 |
| بِيَمِينِهِۦ | `69:19:5` | adjudicated ours | we draw 2 pieces, the spelling allows 1 |
| بِيَمِينِهِۦ | `69:19:5` | too many pieces | draws 2 runs of ink, the spelling allows 1 |
| بِشِمَالِهِۦ | `69:25:5` | adjudicated ours | we draw 3 pieces, the spelling allows 2 |
| بِشِمَالِهِۦ | `69:25:5` | too many pieces | draws 3 runs of ink, the spelling allows 2 |
| وَجَآءَ | `69:9:1` | unresolved | width errors 1.66 vs 2.15 are too close |

### [page 350](http://127.0.0.1:8777/?page=350&step=audit&user=abdullah) — 6 to look at

| word | key | what | why |
|---|---|---|---|
| ءَايَٰتِۭ | `24:1:6` | adjudicated ours | our width is off by 6.92, theirs by 1.95 |
| شُهَدَآءَ | `24:4:8` | adjudicated ours | our width is off by 7.84, theirs by 4.81 |
| فَشَهَٰدَةُ | `24:6:10` | adjudicated ours | we hold 7 dot units, the spelling and the reference both say 6 |
| فَشَهَـٰدَةُ | `24:6:10` | dot cluster | holds 7 dot units, the spelling says 6 |
| شُهَدَآءُ | `24:6:7` | we look right, confirm | their width is off by 3.19, ours by 0.28 |
| شَهَٰدَٰتِۭ | `24:8:7` | adjudicated ours | our width is off by 3.93, theirs by 0.90 |

### [page 507](http://127.0.0.1:8777/?page=507&step=audit&user=abdullah) — 6 to look at

| word | key | what | why |
|---|---|---|---|
| ءَامَنُواْ | `47:11:6` | unresolved | width errors 2.20 vs 2.51 are too close |
| ءَامَنُواْ | `47:2:2` | adjudicated ours | our width is off by 5.67, theirs by 0.89 |
| ءَامَنُواْ | `47:3:9` | adjudicated ours | our width is off by 3.11, theirs by 1.25 |
| فِدَآءً | `47:4:16` | adjudicated ours | our width is off by 4.09, theirs by 1.17 |
| يَشَآءُ | `47:4:23` | adjudicated ours | our width is off by 5.30, theirs by 2.53 |
| ءَامَنُوٓاْ | `47:7:3` | unresolved | width errors 2.59 vs 2.12 are too close |

### [page 589](http://127.0.0.1:8777/?page=589&step=audit&user=abdullah) — 6 to look at

| word | key | what | why |
|---|---|---|---|
| كِتَٰبَهُۥ | `84:10:4` | adjudicated ours | we draw 2 pieces, the spelling allows 1 |
| كِتَـٰبَهُۥ | `84:10:4` | too many pieces | draws 2 runs of ink, the spelling allows 1 |
| إِنَّهُۥ | `84:14:1` | adjudicated ours | we draw 3 pieces, the spelling allows 2 |
| إِنَّهُۥ | `84:14:1` | too many pieces | draws 3 runs of ink, the spelling allows 2 |
| يَسۡجُدُونَۤ | `84:21:6` | adjudicated ours | we draw 4 pieces, the spelling allows 3 |
| كِتَـٰبَهُۥ | `84:7:4` | too many pieces | draws 2 runs of ink, the spelling allows 1 |

### [page 535](http://127.0.0.1:8777/?page=535&step=audit&user=abdullah) — 5 to look at

| word | key | what | why |
|---|---|---|---|
| بِأَكۡوَابٖ | `56:18:1` | unresolved | width errors 4.85 vs 4.65 are too close |
| وَأَبَارِيقَ | `56:18:2` | we look right, confirm | their width is off by 2.83, ours by 0.25 |
| وَكَأۡسٖ | `56:18:3` | we look right, confirm | their width is off by 15.89, ours by 8.89 |
| يَحۡمُومٖ | `56:43:3` | unresolved | width errors 2.06 vs 2.34 are too close |
| لَّا | `56:44:1` | unresolved | width errors 1.04 vs 0.05 are too close |

### [page 585](http://127.0.0.1:8777/?page=585&step=audit&user=abdullah) — 5 to look at

| word | key | what | why |
|---|---|---|---|
| شَآءَ | `80:12:2` | adjudicated ours | our width is off by 3.80, theirs by 0.42 |
| كِرَامِۭ | `80:16:1` | we look right, confirm | their width is off by 5.23, ours by 0.10 |
| بَرَرَةٖ | `80:16:2` | we look right, confirm | their width is off by 3.03, ours by 1.40 |
| شَآءَ | `80:22:3` | adjudicated ours | our width is off by 3.38, theirs by 0.14 |
| ٱلۡمَآءَ | `80:25:3` | adjudicated ours | our width is off by 7.00, theirs by 3.61 |

### [page 1](http://127.0.0.1:8777/?page=1&step=audit&user=abdullah) — 4 to look at

| word | key | what | why |
|---|---|---|---|
| بِسۡمِ | `1:1:1` | unresolved | width errors 5.54 vs 5.54 are too close |
| ٱللَّهِ | `1:1:2` | unresolved | width errors 4.53 vs 4.55 are too close |
| ٱلرَّحۡمَٰنِ | `1:1:3` | unresolved | width errors 18.88 vs 18.74 are too close |
| ٱلرَّحِيمِ | `1:1:4` | unresolved | width errors 8.81 vs 8.65 are too close |

### [page 126](http://127.0.0.1:8777/?page=126&step=audit&user=abdullah) — 4 to look at

| word | key | what | why |
|---|---|---|---|
| بِإِذۡنِي | `5:110:38` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 3 |
| بِإِذْنِى ۖ | `5:110:38` | dot cluster | holds 2 dot units, the spelling says 3 |
| بِإِذۡنِي | `5:110:46` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 3 |
| بِإِذْنِى ۖ | `5:110:46` | dot cluster | holds 2 dot units, the spelling says 3 |

### [page 371](http://127.0.0.1:8777/?page=371&step=audit&user=abdullah) — 4 to look at

| word | key | what | why |
|---|---|---|---|
| كُنَّا | `26:97:3` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| كُنَّا | `26:97:3` | dot cluster | holds 2 dot units, the spelling says 1 |
| ضَلَـٰلٍۢ | `26:97:5` | dot cluster | holds 4 dot units, the spelling says 1 |
| ضَلَـٰلٍۢ | `26:97:5` | too many pieces | draws 2 runs of ink, the spelling allows 1 |

### [page 478](http://127.0.0.1:8777/?page=478&step=audit&user=abdullah) — 4 to look at

| word | key | what | why |
|---|---|---|---|
| سَمَٰوَاتٖ | `41:12:3` | adjudicated ours | our width is off by 6.53, theirs by 0.82 |
| أَنذَرۡتُكُمۡ | `41:13:4` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 4 |
| أَنذَرْتُكُمْ | `41:13:4` | dot cluster | holds 2 dot units, the spelling says 4 |
| وَكَانُواْ | `41:18:4` | we look right, confirm | their width is off by 13.11, ours by 7.93 |

### [page 4](http://127.0.0.1:8777/?page=4&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| تَتَّقُونَ | `2:21:11` | adjudicated ours | we hold 5 dot units, the spelling and the reference both say 7 |
| تَتَّقُونَ | `2:21:11` | dot cluster | holds 5 dot units, the spelling says 7 |
| بِسُورَةٖ | `2:23:10` | adjudicated ours | our width is off by 4.48, theirs by 2.25 |

### [page 341](http://127.0.0.1:8777/?page=341&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| ٱجۡتَمَعُواْ | `22:73:17` | adjudicated ours | our width is off by 9.09, theirs by 2.95 |
| لَهُۥ | `22:73:18` | unresolved | width errors 6.01 vs 4.95 are too close |
| وَإِن | `22:73:19` | we look right, confirm | their width is off by 8.37, ours by 3.20 |

### [page 399](http://127.0.0.1:8777/?page=399&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| وَمَأۡوَىٰكُمُ | `29:25:22` | adjudicated ours | our width is off by 5.33, theirs by 3.17 |
| بِهَا | `29:28:10` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| بِهَا | `29:28:10` | dot cluster | holds 2 dot units, the spelling says 1 |

### [page 446](http://127.0.0.1:8777/?page=446&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| رَأَوۡاْ | `37:14:2` | unresolved | width errors 1.86 vs 1.41 are too close |
| فَٱلزَّٰجِرَٰتِ | `37:2:1` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 5 |
| فَٱلزَّٰجِرَٰتِ | `37:2:1` | dot cluster | holds 3 dot units, the spelling says 5 |

### [page 481](http://127.0.0.1:8777/?page=481&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| مَّكَانِۭ | `41:44:29` | adjudicated ours | our width is off by 6.73, theirs by 0.45 |
| ءَا۬عۡجَمِيّٞ | `41:44:9` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| ءَا۬عْجَمِىٌّۭ | `41:44:9` | dot cluster | holds 2 dot units, the spelling says 1 |

### [page 485](http://127.0.0.1:8777/?page=485&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| حَرۡثِهِۦ | `42:20:9` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 3 |
| حَرْثِهِۦ ۖ | `42:20:9` | dot cluster | holds 0 dot units, the spelling says 3 |
| وَاقِعُۢ | `42:22:7` | adjudicated ours | our width is off by 5.57, theirs by 0.79 |

### [page 519](http://127.0.0.1:8777/?page=519&step=audit&user=abdullah) — 3 to look at

| word | key | what | why |
|---|---|---|---|
| بِٱلۡوَعِيدِ | `50:28:8` | adjudicated ours | we draw 4 pieces, the spelling allows 3 |
| أَنَا۠ | `50:29:6` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 1 |
| أَنَا۠ | `50:29:6` | dot cluster | holds 0 dot units, the spelling says 1 |

### [page 2](http://127.0.0.1:8777/?page=2&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| يُنفِقُونَ | `2:3:8` | adjudicated ours | we hold 5 dot units, the spelling and the reference both say 7 |
| يُنفِقُونَ | `2:3:8` | dot cluster | holds 5 dot units, the spelling says 7 |

### [page 37](http://127.0.0.1:8777/?page=37&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلۡأٓخِرِ | `2:232:24` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 1 |
| ٱلْـَٔاخِرِ ۗ | `2:232:24` | dot cluster | holds 0 dot units, the spelling says 1 |

### [page 38](http://127.0.0.1:8777/?page=38&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بِٱلۡمَعۡرُوفِ | `2:236:22` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 2 |
| بِٱلْمَعْرُوفِ ۖ | `2:236:22` | dot cluster | holds 1 dot units, the spelling says 2 |

### [page 58](http://127.0.0.1:8777/?page=58&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَٱلۡإِنجِيلُ | `3:65:10` | we look right, confirm | their width is off by 3.95, ours by 2.44 |
| ٱلتَّوۡرَىٰةُ | `3:65:9` | adjudicated ours | our width is off by 10.30, theirs by 1.23 |

### [page 112](http://127.0.0.1:8777/?page=112&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| سَنَةٗ | `5:26:6` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 3 |
| سَنَةًۭ ۛ | `5:26:6` | dot cluster | holds 1 dot units, the spelling says 3 |

### [page 117](http://127.0.0.1:8777/?page=117&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| إِنَّهُمۡ | `5:53:10` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 1 |
| إِنَّهُمْ | `5:53:10` | dot cluster | holds 0 dot units, the spelling says 1 |

### [page 129](http://127.0.0.1:8777/?page=129&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| فَوۡقَ | `6:18:3` | adjudicated ours | our width is off by 8.23, theirs by 1.75 |
| عِبَادِهِۦ | `6:18:4` | we look right, confirm | their width is off by 6.90, ours by 1.56 |

### [page 157](http://127.0.0.1:8777/?page=157&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلۡعَٰلَمِينَ | `7:54:32` | adjudicated ours | we draw 3 pieces, the spelling allows 2 |
| ٱلْعَـٰلَمِينَ | `7:54:32` | too many pieces | draws 3 runs of ink, the spelling allows 2 |

### [page 196](http://127.0.0.1:8777/?page=196&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| لِلۡفُقَرَآءِ | `9:60:3` | adjudicated ours | our width is off by 9.42, theirs by 0.25 |
| وَٱلۡمَسَٰكِينِ | `9:60:4` | we look right, confirm | their width is off by 4.14, ours by 2.18 |

### [page 202](http://127.0.0.1:8777/?page=202&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| قُرۡبَةٞ | `9:99:18` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 5 |
| قُرْبَةٌۭ | `9:99:18` | dot cluster | holds 3 dot units, the spelling says 5 |

### [page 207](http://127.0.0.1:8777/?page=207&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| مَّرَّةً | `9:126:8` | we look right, confirm | their width is off by 4.85, ours by 1.82 |
| أَوۡ | `9:126:9` | unresolved | width errors 1.64 vs 1.70 are too close |

### [page 210](http://127.0.0.1:8777/?page=210&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| تُتۡلَىٰ | `10:15:2` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 4 |
| تُتْلَىٰ | `10:15:2` | dot cluster | holds 2 dot units, the spelling says 4 |

### [page 216](http://127.0.0.1:8777/?page=216&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| مَرۡجِعُهُمۡ | `10:70:6` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 1 |
| مَرْجِعُهُمْ | `10:70:6` | dot cluster | holds 0 dot units, the spelling says 1 |

### [page 222](http://127.0.0.1:8777/?page=222&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `11:12:26` | adjudicated ours | our width is off by 4.45, theirs by 0.04 |
| مَّعۡدُودَةٖ | `11:8:7` | adjudicated ours | our width is off by 5.03, theirs by 0.28 |

### [page 226](http://127.0.0.1:8777/?page=226&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| مَجۡر۪ىٰهَا | `11:41:6` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| مَجْر۪ىٰهَا | `11:41:6` | dot cluster | holds 2 dot units, the spelling says 1 |

### [page 236](http://127.0.0.1:8777/?page=236&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| تَأۡمَ۬نَّا | `12:11:6` | adjudicated ours | we hold 4 dot units, the spelling and the reference both say 3 |
| تَأْمَ۫نَّا | `12:11:6` | dot cluster | holds 4 dot units, the spelling says 3 |

### [page 254](http://127.0.0.1:8777/?page=254&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| أَهۡوَآءَهُم | `13:37:7` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 0 |
| أَهْوَآءَهُم | `13:37:7` | dot cluster | holds 1 dot units, the spelling says 0 |

### [page 259](http://127.0.0.1:8777/?page=259&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بِأَمۡرِهِۦ | `14:32:22` | unresolved | width errors 6.92 vs 7.19 are too close |
| وَسَخَّرَ | `14:32:23` | unresolved | width errors 2.80 vs 3.91 are too close |

### [page 275](http://127.0.0.1:8777/?page=275&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `16:76:10` | adjudicated ours | our width is off by 7.39, theirs by 2.26 |
| شَيۡءٖ | `16:77:18` | adjudicated ours | our width is off by 7.27, theirs by 2.31 |

### [page 311](http://127.0.0.1:8777/?page=311&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَنَسُوقُ | `19:86:1` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 3 |
| وَنَسُوقُ | `19:86:1` | dot cluster | holds 1 dot units, the spelling says 3 |

### [page 321](http://127.0.0.1:8777/?page=321&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بِٱلصَّلَوٰةِ | `20:132:3` | adjudicated ours | our width is off by 7.89, theirs by 1.67 |
| وَٱصۡطَبِرۡ | `20:132:4` | we look right, confirm | their width is off by 5.03, ours by 0.82 |

### [page 348](http://127.0.0.1:8777/?page=348&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بِمَا | `23:96:8` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| بِمَا | `23:96:8` | dot cluster | holds 2 dot units, the spelling says 1 |

### [page 354](http://127.0.0.1:8777/?page=354&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| لِنُورِهِۦ | `24:35:38` | unresolved | width errors 8.38 vs 6.36 are too close |
| نُورِهِۦ | `24:35:6` | adjudicated ours | our width is off by 2.90, theirs by 1.04 |

### [page 362](http://127.0.0.1:8777/?page=362&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| جَآءَنِي | `25:29:7` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 2 |
| جَآءَنِى ۗ | `25:29:7` | dot cluster | holds 1 dot units, the spelling says 2 |

### [page 367](http://127.0.0.1:8777/?page=367&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بِهِۦ | `26:6:7` | adjudicated ours | we draw 2 pieces, the spelling allows 1 |
| بِهِۦ | `26:6:7` | too many pieces | draws 2 runs of ink, the spelling allows 1 |

### [page 369](http://127.0.0.1:8777/?page=369&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| قَالُوٓاْ | `26:47:1` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 2 |
| قَالُوٓا۟ | `26:47:1` | dot cluster | holds 3 dot units, the spelling says 2 |

### [page 377](http://127.0.0.1:8777/?page=377&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلزَّكَوٰةَ | `27:3:5` | we look right, confirm | their width is off by 11.61, ours by 2.44 |
| وَهُم | `27:3:6` | unresolved | width errors 3.08 vs 2.09 are too close |

### [page 384](http://127.0.0.1:8777/?page=384&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلۡعَزِيزُ | `27:78:7` | we look right, confirm | their width is off by 2.19, ours by 0.12 |
| ٱلۡعَلِيمُ | `27:78:8` | adjudicated ours | our width is off by 2.06, theirs by 0.47 |

### [page 413](http://127.0.0.1:8777/?page=413&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| يَحۡزُنكَ | `31:23:4` | adjudicated ours | our width is off by 9.30, theirs by 0.19 |
| كُفۡرُهُۥٓ | `31:23:5` | we look right, confirm | their width is off by 11.66, ours by 1.36 |

### [page 424](http://127.0.0.1:8777/?page=424&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| خَالِكَ | `33:50:22` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 1 |
| خَالِكَ | `33:50:22` | dot cluster | holds 2 dot units, the spelling says 1 |

### [page 434](http://127.0.0.1:8777/?page=434&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| مَّكَانِۭ | `34:52:8` | unresolved | width errors 0.99 vs 0.88 are too close |
| مَّكَانِۭ | `34:53:9` | adjudicated ours | our width is off by 8.41, theirs by 1.57 |

### [page 441](http://127.0.0.1:8777/?page=441&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| قَالُواْ | `36:16:1` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 2 |
| قَالُوا۟ | `36:16:1` | dot cluster | holds 3 dot units, the spelling says 2 |

### [page 442](http://127.0.0.1:8777/?page=442&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| فَإِذَا | `36:37:7` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 2 |
| فَإِذَا | `36:37:7` | dot cluster | holds 3 dot units, the spelling says 2 |

### [page 455](http://127.0.0.1:8777/?page=455&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| تَجۡرِي | `38:36:4` | unresolved | width errors 3.20 vs 2.28 are too close |
| بِأَمۡرِهِۦ | `38:36:5` | we look right, confirm | their width is off by 7.49, ours by 3.55 |

### [page 456](http://127.0.0.1:8777/?page=456&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| فَلۡيَذُوقُوهُ | `38:57:2` | adjudicated ours | we hold 7 dot units, the spelling and the reference both say 6 |
| فَلْيَذُوقُوهُ | `38:57:2` | dot cluster | holds 7 dot units, the spelling says 6 |

### [page 460](http://127.0.0.1:8777/?page=460&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| دُونِهِۦ | `39:15:5` | adjudicated ours | we hold 0 dot units, the spelling and the reference both say 1 |
| دُونِهِۦ ۗ | `39:15:5` | dot cluster | holds 0 dot units, the spelling says 1 |

### [page 482](http://127.0.0.1:8777/?page=482&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| شِقَاقِۭ | `41:52:16` | adjudicated ours | our width is off by 4.06, theirs by 0.14 |
| شَيۡءٖ | `41:54:11` | adjudicated ours | our width is off by 4.83, theirs by 0.07 |

### [page 487](http://127.0.0.1:8777/?page=487&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَٱلَّذِينَ | `42:38:1` | adjudicated ours | we hold 5 dot units, the spelling and the reference both say 4 |
| وَٱلَّذِينَ | `42:38:1` | dot cluster | holds 5 dot units, the spelling says 4 |

### [page 526](http://127.0.0.1:8777/?page=526&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلۡأٓخِرَةُ | `53:25:2` | adjudicated ours | our width is off by 11.00, theirs by 1.40 |
| وَٱلۡأُولَىٰ | `53:25:3` | we look right, confirm | their width is off by 4.20, ours by 1.75 |

### [page 536](http://127.0.0.1:8777/?page=536&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| مَا | `56:61:7` | adjudicated ours | we hold 1 dot units, the spelling and the reference both say 0 |
| مَا | `56:61:7` | dot cluster | holds 1 dot units, the spelling says 0 |

### [page 546](http://127.0.0.1:8777/?page=546&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَمَآ | `59:7:24` | adjudicated ours | our width is off by 7.87, theirs by 0.11 |
| ءَاتَىٰكُمُ | `59:7:25` | we look right, confirm | their width is off by 9.51, ours by 1.29 |

### [page 549](http://127.0.0.1:8777/?page=549&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| قَالُواْ | `60:4:11` | adjudicated ours | our width is off by 11.25, theirs by 2.42 |
| وَحۡدَهُۥٓ | `60:4:32` | adjudicated ours | our width is off by 4.39, theirs by 0.85 |

### [page 552](http://127.0.0.1:8777/?page=552&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَلَوۡ | `61:9:12` | we look right, confirm | their width is off by 6.46, ours by 1.32 |
| كَرِهَ | `61:9:13` | adjudicated ours | our width is off by 3.22, theirs by 0.94 |

### [page 556](http://127.0.0.1:8777/?page=556&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| بَصِيرٌ | `64:2:11` | adjudicated ours | we hold 2 dot units, the spelling and the reference both say 3 |
| بَصِيرٌ | `64:2:11` | dot cluster | holds 2 dot units, the spelling says 3 |

### [page 569](http://127.0.0.1:8777/?page=569&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| يُصَدِّقُونَ | `70:26:2` | adjudicated ours | we hold 3 dot units, the spelling and the reference both say 5 |
| يُصَدِّقُونَ | `70:26:2` | dot cluster | holds 3 dot units, the spelling says 5 |

### [page 591](http://127.0.0.1:8777/?page=591&step=audit&user=abdullah) — 2 to look at

| word | key | what | why |
|---|---|---|---|
| وَٱلسَّمَآءِ | `86:11:1` | adjudicated ours | our width is off by 7.47, theirs by 4.01 |
| وَٱلسَّمَآءِ | `86:1:1` | adjudicated ours | our width is off by 6.76, theirs by 3.15 |

### [page 24](http://127.0.0.1:8777/?page=24&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِشَيۡءٖ | `2:155:2` | adjudicated ours | our width is off by 6.28, theirs by 2.01 |

### [page 36](http://127.0.0.1:8777/?page=36&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| قُرُوٓءٖ | `2:228:5` | adjudicated ours | our width is off by 4.77, theirs by 1.65 |

### [page 42](http://127.0.0.1:8777/?page=42&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِشَيۡءٖ | `2:255:35` | adjudicated ours | our width is off by 7.87, theirs by 3.39 |

### [page 43](http://127.0.0.1:8777/?page=43&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `2:259:66` | adjudicated ours | our width is off by 6.17, theirs by 1.21 |

### [page 44](http://127.0.0.1:8777/?page=44&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `2:264:31` | adjudicated ours | our width is off by 6.85, theirs by 1.80 |

### [page 59](http://127.0.0.1:8777/?page=59&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| يُؤَدِّهِۦٓ | `3:75:8` | unresolved | width errors 1.21 vs 2.37 are too close |

### [page 71](http://127.0.0.1:8777/?page=71&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بَعۡدِهِۦ | `3:160:14` | adjudicated ours | our width is off by 9.78, theirs by 5.01 |

### [page 77](http://127.0.0.1:8777/?page=77&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَنِسَآءٗ | `4:1:17` | adjudicated ours | our width is off by 4.21, theirs by 0.39 |

### [page 83](http://127.0.0.1:8777/?page=83&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `4:33:18` | adjudicated ours | our width is off by 6.30, theirs by 1.99 |

### [page 93](http://127.0.0.1:8777/?page=93&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| قَوۡمِۭ | `4:92:37` | adjudicated ours | our width is off by 2.79, theirs by 0.16 |

### [page 107](http://127.0.0.1:8777/?page=107&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| لِّإِثۡمٖ | `5:3:57` | adjudicated ours | our width is off by 11.61, theirs by 3.79 |

### [page 110](http://127.0.0.1:8777/?page=110&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `5:17:41` | adjudicated ours | our width is off by 5.80, theirs by 1.04 |

### [page 114](http://127.0.0.1:8777/?page=114&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `5:40:18` | unresolved | width errors 2.46 vs 1.46 are too close |

### [page 123](http://127.0.0.1:8777/?page=123&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِشَيۡءٖ | `5:94:6` | adjudicated ours | our width is off by 6.96, theirs by 2.50 |

### [page 124](http://127.0.0.1:8777/?page=124&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بَحِيرَةٖ | `5:103:5` | unresolved | width errors 1.76 vs 0.95 are too close |

### [page 127](http://127.0.0.1:8777/?page=127&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `5:120:10` | adjudicated ours | our width is off by 7.06, theirs by 2.58 |

### [page 142](http://127.0.0.1:8777/?page=142&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| ٱلسَّمِيعُ | `6:115:10` | we look right, confirm | their width is off by 2.71, ours by 0.18 |

### [page 147](http://127.0.0.1:8777/?page=147&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| ذَٰلِكَ | `6:146:24` | unresolved | width errors 3.75 vs 2.45 are too close |

### [page 164](http://127.0.0.1:8777/?page=164&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| يَدَهُۥ | `7:108:2` | adjudicated ours | our width is off by 9.02, theirs by 4.16 |

### [page 186](http://127.0.0.1:8777/?page=186&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| قَوۡمِۭ | `8:72:38` | adjudicated ours | our width is off by 2.17, theirs by 0.08 |

### [page 190](http://127.0.0.1:8777/?page=190&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| كَثِيرَةٖ | `9:25:6` | adjudicated ours | our width is off by 2.65, theirs by 0.80 |

### [page 193](http://127.0.0.1:8777/?page=193&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِجُنُودٖ | `9:40:29` | adjudicated ours | our width is off by 3.06, theirs by 1.24 |

### [page 205](http://127.0.0.1:8777/?page=205&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| مَّوۡعِدَةٖ | `9:114:8` | adjudicated ours | our width is off by 5.90, theirs by 1.31 |

### [page 213](http://127.0.0.1:8777/?page=213&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِسُورَةٖ | `10:38:6` | unresolved | width errors 1.52 vs 0.37 are too close |

### [page 231](http://127.0.0.1:8777/?page=231&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| يَٰقَوۡمِ | `11:88:2` | adjudicated ours | our width is off by 6.56, theirs by 1.27 |

### [page 233](http://127.0.0.1:8777/?page=233&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `11:101:16` | adjudicated ours | our width is off by 6.37, theirs by 1.55 |

### [page 239](http://127.0.0.1:8777/?page=239&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَٰحِدَةٖ | `12:31:11` | adjudicated ours | our width is off by 5.33, theirs by 1.18 |

### [page 240](http://127.0.0.1:8777/?page=240&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| ذَٰلِكَ | `12:38:15` | unresolved | width errors 3.00 vs 2.89 are too close |

### [page 248](http://127.0.0.1:8777/?page=248&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `12:111:19` | adjudicated ours | our width is off by 6.32, theirs by 1.43 |

### [page 251](http://127.0.0.1:8777/?page=251&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `13:16:42` | adjudicated ours | our width is off by 7.23, theirs by 2.88 |

### [page 257](http://127.0.0.1:8777/?page=257&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `14:18:18` | adjudicated ours | our width is off by 6.85, theirs by 2.72 |

### [page 258](http://127.0.0.1:8777/?page=258&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `14:21:20` | adjudicated ours | our width is off by 5.06, theirs by 1.03 |

### [page 260](http://127.0.0.1:8777/?page=260&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `14:38:13` | adjudicated ours | our width is off by 4.93, theirs by 0.19 |

### [page 263](http://127.0.0.1:8777/?page=263&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `15:19:10` | adjudicated ours | our width is off by 5.57, theirs by 1.16 |

### [page 267](http://127.0.0.1:8777/?page=267&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| عِبَادِهِۦٓ | `16:2:10` | adjudicated ours | our width is off by 8.46, theirs by 3.95 |

### [page 338](http://127.0.0.1:8777/?page=338&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شِقَاقِۭ | `22:53:15` | adjudicated ours | our width is off by 7.44, theirs by 0.56 |

### [page 343](http://127.0.0.1:8777/?page=343&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| مَآءَۢ | `23:18:4` | adjudicated ours | our width is off by 2.69, theirs by 0.35 |

### [page 347](http://127.0.0.1:8777/?page=347&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `23:88:6` | adjudicated ours | our width is off by 6.99, theirs by 2.01 |

### [page 355](http://127.0.0.1:8777/?page=355&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| كَسَرَابِۭ | `24:39:4` | adjudicated ours | our width is off by 7.40, theirs by 0.78 |

### [page 356](http://127.0.0.1:8777/?page=356&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `24:45:30` | adjudicated ours | our width is off by 5.45, theirs by 1.03 |

### [page 361](http://127.0.0.1:8777/?page=361&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| مَّكَانِۭ | `25:12:4` | adjudicated ours | our width is off by 6.74, theirs by 0.22 |

### [page 368](http://127.0.0.1:8777/?page=368&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| بِشَيۡءٖ | `26:30:4` | adjudicated ours | our width is off by 8.66, theirs by 4.32 |

### [page 380](http://127.0.0.1:8777/?page=380&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| ءَاتِيكَ | `27:40:8` | unresolved | width errors 2.01 vs 2.95 are too close |

### [page 401](http://127.0.0.1:8777/?page=401&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `29:42:9` | adjudicated ours | our width is off by 4.89, theirs by 0.01 |

### [page 410](http://127.0.0.1:8777/?page=410&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| قُوَّةٖ | `30:54:16` | adjudicated ours | our width is off by 4.68, theirs by 2.62 |

### [page 445](http://127.0.0.1:8777/?page=445&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `36:83:6` | adjudicated ours | our width is off by 5.36, theirs by 0.42 |

### [page 447](http://127.0.0.1:8777/?page=447&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| لَذَآئِقُونَ | `37:31:6` | adjudicated ours | we draw 5 pieces, the spelling allows 4 |

### [page 465](http://127.0.0.1:8777/?page=465&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَكُنتَ | `39:59:8` | we look right, confirm | their width is off by 13.61, ours by 7.36 |

### [page 467](http://127.0.0.1:8777/?page=467&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَٱلۡأَحۡزَابُ | `40:5:5` | unresolved | width errors 3.56 vs 2.72 are too close |

### [page 474](http://127.0.0.1:8777/?page=474&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `40:62:6` | adjudicated ours | our width is off by 6.00, theirs by 1.45 |

### [page 490](http://127.0.0.1:8777/?page=490&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| مَآءَۢ | `43:11:5` | adjudicated ours | our width is off by 2.96, theirs by 1.04 |

### [page 497](http://127.0.0.1:8777/?page=497&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَمَقَامٖ | `44:26:2` | we look right, confirm | their width is off by 4.09, ours by 1.05 |

### [page 501](http://127.0.0.1:8777/?page=501&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| نَمُوتُ | `45:24:7` | adjudicated ours | our width is off by 4.73, theirs by 0.13 |

### [page 503](http://127.0.0.1:8777/?page=503&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| ٱللَّهِ | `46:8:11` | we look right, confirm | their width is off by 2.11, ours by 0.01 |

### [page 504](http://127.0.0.1:8777/?page=504&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَٱلۡإِنسِ | `46:18:14` | unresolved | width errors 4.60 vs 4.20 are too close |

### [page 513](http://127.0.0.1:8777/?page=513&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `48:21:13` | adjudicated ours | our width is off by 7.89, theirs by 3.00 |

### [page 523](http://127.0.0.1:8777/?page=523&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| دَافِعٖ | `52:8:4` | adjudicated ours | our width is off by 5.70, theirs by 0.56 |

### [page 542](http://127.0.0.1:8777/?page=542&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `58:6:14` | adjudicated ours | our width is off by 5.55, theirs by 1.08 |

### [page 547](http://127.0.0.1:8777/?page=547&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| جُدُرِۭ | `59:14:11` | adjudicated ours | our width is off by 8.71, theirs by 0.75 |

### [page 561](http://127.0.0.1:8777/?page=561&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `66:8:44` | adjudicated ours | our width is off by 5.00, theirs by 0.79 |

### [page 562](http://127.0.0.1:8777/?page=562&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٖ | `67:1:8` | adjudicated ours | our width is off by 6.33, theirs by 1.94 |

### [page 568](http://127.0.0.1:8777/?page=568&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| وَاقِعٖ | `70:1:4` | adjudicated ours | our width is off by 5.30, theirs by 0.67 |

### [page 570](http://127.0.0.1:8777/?page=570&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| دُعَآءِيٓ | `71:6:3` | we look right, confirm | their width is off by 4.31, ours by 0.31 |

### [page 577](http://127.0.0.1:8777/?page=577&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| قَسۡوَرَةِۭ | `74:51:3` | we look right, confirm | their width is off by 2.31, ours by 0.33 |

### [page 582](http://127.0.0.1:8777/?page=582&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَيۡءٍ | `78:29:2` | adjudicated ours | our width is off by 3.64, theirs by 1.11 |

### [page 586](http://127.0.0.1:8777/?page=586&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| شَآءَ | `81:28:2` | adjudicated ours | our width is off by 4.38, theirs by 0.11 |

### [page 588](http://127.0.0.1:8777/?page=588&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| يُكَذِّبُ | `83:12:2` | adjudicated ours | our width is off by 6.57, theirs by 1.71 |

### [page 595](http://127.0.0.1:8777/?page=595&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| فَسَنُيَسِّرُهُۥ | `92:7:1` | adjudicated ours | our width is off by 3.43, theirs by 0.32 |

### [page 600](http://127.0.0.1:8777/?page=600&step=audit&user=abdullah) — 1 to look at

| word | key | what | why |
|---|---|---|---|
| لِرَبِّهِۦ | `100:6:3` | we look right, confirm | their width is off by 15.56, ours by 11.01 |

