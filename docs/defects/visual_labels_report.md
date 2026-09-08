# Visual classification of unlabeled mark signatures

Agent pass, 2026-08-26. Every mark element on all 604 pages whose shape signature was missing from `.cache/marks/labels.json` (or that carried no mark name) was enumerated, rendered in context (target ink in red, surroundings in black), and classified by eye. 332 unlabeled signatures, 3,050 occurrences. Rendered evidence: contact sheets in `.cache/review/visual-labels/sheets/` (one tile per exemplar, labeled `sig n=count page_key`), one PNG per exemplar in `.cache/review/visual-labels/png/`.

PNG file names below live in `.cache/review/visual-labels/png/`.

## How to read this
- **A. APPLIED** — labels I would bet the table on: unmistakable render + a corroborating signal (text budget, position, or an existing convention), then measured (group bisect on a 20-page sample, bench, cmp_pages). Numbers in the Measurements section.
- **B. NEEDS YOUR CONFIRMATION** — my guess is strong but a repo rule forbids the agent from applying it (hamzah-family, dammah lookalikes, composite/waqf caveats).
- **C. NEEDS YOUR DECISION** — genuinely unclear or double-booked signatures.
Sections B and C are also machine-readable in `docs/defects/visual_label_queue.json`.


## A. APPLIED

### letter — 111 signatures, 129 occurrences

**letter** — full-size letters held as marks. All but a handful sit on words ending in an iqlab tanwin (ٌۭ / ٍۢ / ًۭ): the word's own final letter (ب ة ق ر د ن م لا يد و ك ز ت ه) was classified as a mark and named `small_meem`, which no audit counts — so the words sat silently short of a letter. What I saw, per signature, is the word's final letter at letter size (area 95-125 for tall letters, 24-31 for the ة/ه rings), joined to the baseline, exactly where the spelling puts it. The `letter` label forces kind=body at the top of the classifier, pixel-identical output.

| signature | n | seen | exemplars |
|---|---|---|---|
| `f2a5ff7094ebb571` | 7 | the full-size joined final ب of a word ending in iqlab tanwin, wrongly held as a mark | p455 38:42:6 وَشَرَابٌۭ; p252 13:23:15 بَابٍۢ; p477 41:5:14 حِجَابٌۭ |
| `e0d41a6d474ce60c` | 4 | the full-size joined final ب of a word ending in iqlab tanwin, wrongly held as a mark | p571 71:15:7 سَمَـٰوَٰتٍۢ; p530 54:38:4 عَذَابٌۭ; p592 88:14:1 وَأَكْوَابٌۭ |
| `17ac2d8045193807` | 3 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p184 8:60:6 قُوَّةٍۢ; p184 8:56:9 مَرَّةٍۢ; p187 9:1:1 بَرَآءَةٌۭ |
| `cc09cbebef3c9261` | 2 | the full-size joined final ب of a word ending in iqlab tanwin, wrongly held as a mark | p446 37:9:3 عَذَابٌۭ; p350 24:8:7 شَهَـٰدَٰتٍۭ |
| `5c1b49d21dc0da40` | 2 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p557 64:14:17 غَفُورٌۭ; p373 26:148:1 وَزُرُوعٍۢ |
| `40f4a8d8468164ec` | 2 | the full-size joined final د of a word ending in iqlab tanwin, wrongly held as a mark | p582 78:24:4 بَرْدًۭا; p453 38:12:5 وَعَادٌۭ |
| `9d2ee5045f8a17b8` | 2 | the full-size joined final ب of a word ending in iqlab tanwin, wrongly held as a mark | p499 45:11:8 عَذَابٌۭ; p499 45:9:10 عَذَابٌۭ |
| `70071faa3de75bed` | 2 | the full-size joined final ن of a word ending in iqlab tanwin, wrongly held as a mark | p585 80:37:5 شَأْنٌۭ; p569 70:28:5 مَأْمُونٍۢ |
| `124d821ebe6b2661` | 2 | the full-size ة of ٱلْـَٔاخِرَة held as a mark | p351 24:14:8 وَٱلْـَٔاخِرَةِ; p568 69:48:2 لَتَذْكِرَةٌۭ |
| `4aaf1de37ba73af5` | 2 | the full-size ة of ٱلْـَٔاخِرَة held as a mark | p565 68:33:4 ٱلْـَٔاخِرَةِ; p521 51:11:4 غَمْرَةٍۢ |
| `07aed98ccc4aabd5` | 1 | the full-size ق (area 116) of شِقَاقٍۭ held as a mark | p482 41:52:16 شِقَاقٍۭ |
| `3be8859b3dd1023e` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p10 2:69:13 بَقَرَةٌۭ |
| `76ccffb34773cd4d` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p21 2:137:14 شِقَاقٍۢ ۖ |
| `e39f779a89460931` | 1 | the full-size joined final م of a word ending in iqlab tanwin, wrongly held as a mark | p53 3:25:4 لِيَوْمٍۢ |
| `ef9614b0d29b7f4a` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p67 3:136:3 مَّغْفِرَةٌۭ |
| `3ba16cc758c791ad` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p77 4:1:9 وَٰحِدَةٍۢ |
| `fd95b281559b7e73` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p101 4:142:19 قَلِيلًۭا |
| `c376b315bd7af816` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p200 9:82:2 قَلِيلًۭا |
| `39b6a2759222d27f` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p200 9:83:22 مَرَّةٍۢ |
| `1afec7362f2ab258` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p215 10:59:8 رِّزْقٍۢ |
| `7126e0405032a3d2` | 1 | the full-size joined final ك of a word ending in iqlab tanwin, wrongly held as a mark | p220 10:104:7 شَكٍّۢ |
| `9b66a1eca91deb61` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p241 12:47:12 قَلِيلًۭا |
| `43bcaeaecb0a9a9a` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p253 13:34:14 وَاقٍۢ |
| `410a2d5d4b7ecaa2` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p254 13:37:19 وَاقٍۢ |
| `e0bda9cbbcd43bcc` | 1 | the full-size joined final م of a word ending in iqlab tanwin, wrongly held as a mark | p268 16:13:12 لِّقَوْمٍۢ |
| `75fe25aac8c591f0` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p269 16:22:9 مُّنكِرَةٌۭ |
| `333288edd53d294d` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p275 16:76:3 مَثَلًۭا |
| `a284c1fa6cf0ad7f` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p287 17:54:14 وَكِيلًۭا |
| `1f23d32e9c21919d` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p289 17:70:17 تَفْضِيلًۭا |
| `d6edb05db93e2695` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p290 17:80:5 صِدْقٍۢ |
| `4f59b5288b1ba4fd` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p295 18:19:32 بِرِزْقٍۢ |
| `2ae0872ae216cb87` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p297 18:31:20 وَإِسْتَبْرَقٍۢ |
| `65eef9a971d6b971` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p314 20:47:14 بِـَٔايَةٍۢ |
| `b0a71ee0a81c3c49` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p321 20:133:4 بِـَٔايَةٍۢ |
| `520c928fa7531299` | 1 | the full-size joined final و of a word ending in iqlab tanwin, wrongly held as a mark | p332 22:5:68 زَوْجٍۭ |
| `eb8b1a4cdb839a1f` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p338 22:55:6 مِرْيَةٍۢ |
| `7592e33658bcd163` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p342 23:13:5 قَرَارٍۢ |
| `ad944b175ba5ec55` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p343 23:20:1 وَشَجَرَةًۭ |
| `c06be5197e22fae2` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p350 24:2:8 جَلْدَةٍۢ ۖ |
| `9f1ffba8dbcea676` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p350 24:5:10 غَفُورٌۭ |
| `399744f38734fc89` | 1 | the full-size joined final ن+ة of a word ending in iqlab tanwin, wrongly held as a mark | p353 24:29:8 مَسْكُونَةٍۢ |
| `b03828fef8998c0d` | 1 | the full-size joined final ب+ة of a word ending in iqlab tanwin, wrongly held as a mark | p356 24:45:4 دَآبَّةٍۢ |
| `1a7af76f6a94d032` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p360 25:5:9 وَأَصِيلًۭا |
| `b45634986616e192` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p360 25:8:16 رَجُلًۭا |
| `a48c074eaea647ee` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p362 25:24:7 مَقِيلًۭا |
| `0093e8ba6518bf88` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p366 25:70:15 غَفُورًۭا |
| `e7d0e9df8ab986b5` | 1 | the full-size joined final و of a word ending in iqlab tanwin, wrongly held as a mark | p367 26:7:10 زَوْجٍۢ |
| `00da5ce610c7bb53` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p370 26:63:11 فِرْقٍۢ |
| `32700e2606a0d152` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p371 26:84:4 صِدْقٍۢ |
| `086f86edb1af252c` | 1 | the full-size joined final د of a word ending in iqlab tanwin, wrongly held as a mark | p376 26:225:6 وَادٍۢ |
| `3c815160e845d40e` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p379 27:35:4 بِهَدِيَّةٍۢ |
| `5f7a88d7be03e2e6` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p414 31:31:18 صَبَّارٍۢ |
| `cf00bd92166b1be6` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p414 31:31:19 شَكُورٍۢ |
| `abfca5ab79c9de73` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p414 31:32:21 خَتَّارٍۢ |
| `8dda9b47fad30de2` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p414 31:32:22 كَفُورٍۢ |
| `4061d06021dcf6e4` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p414 31:34:22 أَرْضٍۢ |
| `94307d39189badd4` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p418 33:5:27 غَفُورًۭا |
| `b4534c494d3c3509` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p423 33:36:23 ضَلَـٰلًۭا |
| `31b6273fe6a1e6bd` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p424 33:49:22 جَمِيلًۭا |
| `d06637c252ba8117` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p426 33:60:19 قَلِيلًۭا |
| `ef635539e19d681c` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p430 34:22:11 ذَرَّةٍۢ |
| `ba04384605271936` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p433 34:46:24 شَدِيدٍۢ |
| `c8e339cd1f5c3acf` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p435 35:7:5 شَدِيدٌۭ ۖ |
| `588642ed3e5a47df` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p435 35:10:20 شَدِيدٌۭ ۖ |
| `ed4d7a8d4c15bfd6` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p436 35:18:3 وَازِرَةٌۭ |
| `a5a14b3ad9ec7481` | 1 | the full-size joined final د of a word ending in iqlab tanwin, wrongly held as a mark | p446 37:7:5 مَّارِدٍۢ |
| `cd2c9ec2cb0723ee` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p446 37:9:1 دُحُورًۭا ۖ |
| `a5a345c6a0737f15` | 1 | the full-size joined final ز of a word ending in iqlab tanwin, wrongly held as a mark | p446 37:11:12 لَّازِبٍۭ |
| `cd03b3ac2901e65d` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p453 38:2:5 عِزَّةٍۢ |
| `d4c85e6ef3c6296c` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p453 38:2:6 وَشِقَاقٍۢ |
| `f17b228fa7841bff` | 1 | the full-size joined final ن of a word ending in iqlab tanwin, wrongly held as a mark | p453 38:3:6 قَرْنٍۢ |
| `b3e9ec752b50fc85` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p453 38:15:10 فَوَاقٍۢ |
| `d2b9ca3d9f46beff` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p454 38:26:26 شَدِيدٌۢ |
| `efb5c2ab9aa93099` | 1 | the full-size joined final ر of a word ending in iqlab tanwin, wrongly held as a mark | p461 39:22:8 نُورٍۢ |
| `7f8b322b01d8f8d7` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p469 40:21:30 وَاقٍۢ |
| `83203ebf662760e4` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p486 42:26:12 شَدِيدٌۭ |
| `0a98b0dd8e42f193` | 1 | the full-size joined final ية of a word ending in iqlab tanwin, wrongly held as a mark | p491 43:23:7 قَرْيَةٍۢ |
| `611ba4116c0effee` | 1 | the full-size joined final ن of a word ending in iqlab tanwin, wrongly held as a mark | p498 44:52:3 وَعُيُونٍۢ |
| `e9a36e9b9d7d958f` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p498 44:53:4 وَإِسْتَبْرَقٍۢ |
| `a2392d16610c6256` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p499 45:5:10 رِّزْقٍۢ |
| `b36a18c003dce51c` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p513 48:16:10 شَدِيدٍۢ |
| `503786fc72b5f0a8` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p519 50:22:12 حَدِيدٌۭ |
| `4dc3e70a96c7ffc3` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p519 50:30:9 مَّزِيدٍۢ |
| `52e94aee8ce2eca7` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p523 51:57:5 رِّزْقٍۢ |
| `7c0cc3387963a719` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p523 52:3:2 رَقٍّۢ |
| `496964a0f4dccf5b` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p527 53:38:3 وَازِرَةٌۭ |
| `45a91b22b6b930d9` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p533 55:54:6 إِسْتَبْرَقٍۢ ۚ |
| `d1dc35724282758a` | 1 | the full-size joined final د of a word ending in iqlab tanwin, wrongly held as a mark | p535 56:28:3 مَّخْضُودٍۢ |
| `82ba20d43633c4df` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p540 57:20:29 شَدِيدٌۭ |
| `bcb8a02d39ec9323` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p546 59:8:9 فَضْلًۭا |
| `134dcf03be8fb4ad` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p547 59:14:14 شَدِيدٌۭ ۚ |
| `96e250e510c5edb1` | 1 | the full-size joined final يد of a word ending in iqlab tanwin, wrongly held as a mark | p559 65:10:5 شَدِيدًۭا ۖ |
| `ce1c3996ad363c09` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p561 66:10:3 مَثَلًۭا |
| `ea12ed268ca9ccd7` | 1 | the full-size joined final ت of a word ending in iqlab tanwin, wrongly held as a mark | p562 67:3:12 تَفَـٰوُتٍۢ ۖ |
| `beb0a421e8a06bda` | 1 | the full-size joined final لا of a word ending in iqlab tanwin, wrongly held as a mark | p563 67:23:10 قَلِيلًۭا |
| `d822bdd9871b72cc` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p565 68:42:4 سَاقٍۢ |
| `5d9ee0542d1d3318` | 1 | the full-size joined final ية of a word ending in iqlab tanwin, wrongly held as a mark | p566 69:7:15 خَاوِيَةٍۢ |
| `fb9da7b02a38846a` | 1 | the full-size joined final ق of a word ending in iqlab tanwin, wrongly held as a mark | p578 75:27:3 رَاقٍۢ |
| `887eee05146529fa` | 1 | the full-size joined final ب of a word ending in iqlab tanwin, wrongly held as a mark | p583 79:8:1 قُلُوبٌۭ |
| `93d8c6603ba7394c` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p585 80:14:2 مُّطَهَّرَةٍۭ |
| `aace537fcf074045` | 1 | the full-size joined final م of a word ending in iqlab tanwin, wrongly held as a mark | p585 80:16:1 كِرَامٍۭ |
| `8d6ff29f4cea967b` | 1 | the full-size joined final ن of a word ending in iqlab tanwin, wrongly held as a mark | p586 81:22:3 بِمَجْنُونٍۢ |
| `b1c10b603d0aafce` | 1 | the full-size joined final ة of a word ending in iqlab tanwin, wrongly held as a mark | p599 99:8:4 ذَرَّةٍۢ |
| `b41d05cf7ac4f76a` | 1 | a full-size letter (ة/ه/ق) inside a real word, held as an unnamed mark | p113 5:33:32 ٱلْـَٔاخِرَةِ |
| `ef521f49ad1254f9` | 1 | a full-size letter (ة/ه/ق) inside a real word, held as an unnamed mark | p198 9:69:29 وَٱلْـَٔاخِرَةِ ۖ |
| `7d352e86b85320b1` | 1 | a full-size letter (ة/ه/ق) inside a real word, held as an unnamed mark | p260 14:40:4 ٱلصَّلَوٰةِ |
| `97d235135e48afea` | 1 | a full-size letter (ة/ه/ق) inside a real word, held as an unnamed mark | p354 24:35:38 لِنُورِهِۦ |
| `3ef884a76279db86` | 1 | a full-size letter (ة/ه/ق) inside a real word, held as an unnamed mark | p499 45:8:12 فَبَشِّرْهُ |
| `76a0c6516237ea74` | 1 | the full-size joined ه of لِرَبِّهِ held as a mark (its ۦ is drawn separately) | p600 100:6:3 لِرَبِّهِۦ |
| `9a348392065566fc` | 1 | the full-size joined ة of ٱلصَّلَوٰةِ (22:35:12) held as an unnamed mark | p336 22:35:12 ٱلصَّلَوٰةِ |
| `4b02e3a5a4b9e939` | 1 | the full-size joined ة of ٱلْـَٔاخِرَةِ (23:74:5) held as an unnamed mark | p346 23:74:5 بِٱلْـَٔاخِرَةِ |

### fathah — 52 signatures, 574 occurrences

**fathah** — plain slanted slash strokes: basmalah/surah-header slashes, tanwin_al_kasr halves under the شَىْءٍ family, ordinary fathahs/kasrahs in real words. The slash families are one stroke named later from position and proximity, so every slash gets the canonical single name `fathah` and the renaming pass does the rest.

| signature | n | seen | exemplars |
|---|---|---|---|
| `0c428bd36f68d8b6` | 222 | a plain slanted slash stroke in fathah position | p597 - ; p594 - ; p453 -  |
| `4f1cc674ba7ccbae` | 220 | a plain slanted slash stroke in fathah position | p496 - ; p305 - ; p602 -  |
| `af80374b955018b1` | 16 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p546 59:6:24 شَىْءٍۢ; p564 67:30:9 بِمَآءٍۢ; p258 14:21:20 شَىْءٍۢ ۚ |
| `6dbd0121c97a3de4` | 11 | one slash of the tanwin_al_kasr pair under a شىء-family word | p286 17:46:4 أَكِنَّةً; p251 13:14:11 بِشَىْءٍ; p240 12:38:14 شَىْءٍۢ ۚ |
| `2664ec1f6409d7a7` | 10 | one slash of the tanwin_al_kasr pair under a شىء-family word | p559 65:12:17 شَىْءٍۢ; p286 17:44:10 شَىْءٍ; p296 18:23:3 لِشَا۟ىْءٍ |
| `1a86d5c57e59f373` | 6 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p318 20:98:11 شَىْءٍ; p275 16:77:18 شَىْءٍۢ; p275 16:77:18 شَىْءٍۢ |
| `1a52809f48b2f1cc` | 4 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p248 12:111:19 شَىْءٍۢ; p248 12:111:19 شَىْءٍۢ; p263 15:19:10 شَىْءٍۢ |
| `906cfd38bd564f19` | 4 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p585 80:18:3 شَىْءٍ; p585 80:18:3 شَىْءٍ; p298 18:45:6 كَمَآءٍ |
| `255bc1e2cb418d85` | 4 | one slash of the tanwin_al_kasr pair under a شىء-family word | p333 22:6:12 شَىْءٍۢ; p333 22:6:12 شَىْءٍۢ; p368 26:30:4 بِشَىْءٍۢ |
| `768a9318a8dd53d5` | 4 | a slash stroke above/below a surah-header title word | p604 - ; p604 - ; p221 -  |
| `f553e15be62af585` | 4 | a slash stroke above/below a surah-header title word | p483 - ; p483 - ; p411 -  |
| `9a66b3b44c0be8fa` | 4 | a slash stroke above/below a surah-header title word | p467 - ; p467 - ; p467 -  |
| `8fdb5502510e8437` | 3 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p260 14:38:13 شَىْءٍۢ; p354 24:35:47 شَىْءٍ; p354 24:35:47 شَىْءٍ |
| `3acced709529673c` | 3 | one slash of the tanwin_al_kasr pair under a شىء-family word | p275 16:75:9 شَىْءٍۢ; p359 25:2:17 شَىْءٍۢ; p359 25:2:17 شَىْءٍۢ |
| `8d981fe573e2e9e2` | 2 | a plain slanted slash stroke in fathah position | p32 2:203:4 أَيَّامٍۢ; p99 4:128:2 ٱمْرَأَةٌ |
| `32b9d970ec38d48a` | 2 | a plain slanted slash stroke in fathah position | p575 - ; p575 -  |
| `f40ccd75f3ad0591` | 2 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p106 - ; p106 -  |
| `f3f2d80135747a35` | 2 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p322 - ; p322 -  |
| `354ca3dcc3370b3c` | 2 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p521 51:30:5 إِنَّهُۥ; p529 54:27:1 إِنَّا |
| `6dc745d92e4856ca` | 2 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p588 83:10:2 يَوْمَئِذٍۢ; p598 96:15:2 لَئِن |
| `347cdf1efae39692` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p272 16:48:8 شَىْءٍۢ; p272 16:48:8 شَىْءٍۢ |
| `be686d2026f3aeb5` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p301 18:70:7 شَىْءٍ; p301 18:70:7 شَىْءٍ |
| `1666bd45b4ce917b` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p304 18:101:5 غِطَآءٍ; p304 18:101:5 غِطَآءٍ |
| `34281bd7a1d687cd` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p356 24:45:6 مَّآءٍۢ ۖ; p356 24:45:6 مَّآءٍۢ ۖ |
| `f5dc9a08f977fc14` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p359 24:64:21 شَىْءٍ; p359 24:64:21 شَىْءٍ |
| `a9e3140cd7479b20` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p377 27:7:14 قَبَسٍۢ; p377 27:7:14 قَبَسٍۢ |
| `94ac9f558c492f55` | 2 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p549 60:4:45 شَىْءٍۢ ۖ; p549 60:4:45 شَىْءٍۢ ۖ |
| `466704ca5fc507d8` | 2 | a slash stroke above/below a surah-header title word | p151 - ; p151 -  |
| `3cc3eec5a9277707` | 2 | a slash stroke above/below a surah-header title word | p151 - ; p151 -  |
| `4aa03f094f35a4b0` | 2 | a slash stroke above/below a surah-header title word | p221 - ; p221 -  |
| `ff4019c722abe25a` | 2 | a slash stroke above/below a surah-header title word | p255 - ; p255 -  |
| `d603569adc6a1751` | 2 | a slash stroke above/below a surah-header title word | p322 - ; p322 -  |
| `ea95acaf3d550ff7` | 2 | a slash stroke above/below a surah-header title word | p558 - ; p558 -  |
| `2ce5108791db6220` | 2 | a slash stroke above/below a surah-header title word | p598 - ; p598 -  |
| `ef940e394a94551f` | 2 | a slash stroke above/below a surah-header title word | p599 - ; p599 -  |
| `2757106d245f6ceb` | 1 | one slash of the tanwin_al_fath pair over فَظًّا — single stroke, canonical slash name | p71 3:159:9 فَظًّا |
| `b1d94e3288f0ec07` | 1 | a plain slanted slash stroke in fathah position | p297 18:28:4 ٱلَّذِينَ |
| `25df7f1835ae677e` | 1 | a plain slanted slash stroke in fathah position | p321 20:127:10 ٱلْـَٔاخِرَةِ |
| `e1fb835e59a63837` | 1 | a plain slanted slash stroke in fathah position | p348 23:90:2 أَتَيْنَـٰهُم |
| `2138ad442d0a62f4` | 1 | a plain slanted slash stroke in fathah position | p453 38:7:6 ٱلْـَٔاخِرَةِ |
| `6c30a671eb605fc6` | 1 | a plain slanted slash stroke in fathah position | p483 42:5:14 أَلَآ |
| `dca1191e2f0ec5f4` | 1 | a plain slanted slash stroke in fathah position | p538 57:4:8 أَيَّامٍۢ |
| `5d3e5ec290618c7c` | 1 | a plain slanted slash stroke in fathah position | p575 73:20:4 أَنَّكَ |
| `2f677f15b43dfadc` | 1 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p49 2:285:12 وَمَلَـٰٓئِكَتِهِۦ |
| `37f2ca6ae9ba7d38` | 1 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p143 6:121:14 إِلَىٰٓ |
| `0109e69d19dcf0b9` | 1 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p327 21:72:3 إِسْحَـٰقَ |
| `e787519e78b50941` | 1 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p356 24:53:5 لَئِنْ |
| `5914cbd8751d40b1` | 1 | a plain slash stroke below its letter (kasrah position); slash family canonical name | p594 89:27:3 ٱلْمُطْمَئِنَّةُ |
| `aacc0b7363cfb3f4` | 1 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p260 14:38:13 شَىْءٍۢ |
| `362c27bb29842c2e` | 1 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p275 16:75:9 شَىْءٍۢ |
| `105065a091e8f30b` | 1 | one slash of the tanwin_al_kasr pair under a شَىْءٍ-family word; single stroke, canonical slash name | p487 42:44:20 سَبِيلٍۢ |
| `feedf4b381cc302c` | 1 | a plain slash over the ن of أَنَا۠ — the ۠ itself is drawn separately as a ring above | p519 50:29:6 أَنَا۠ |

### three_dots — 37 signatures, 49 occurrences

**three_dots** — three-dot pyramids riding a ش or ث whose text wants exactly those 3 dots.

| signature | n | seen | exemplars |
|---|---|---|---|
| `5c6bc373b3232049` | 5 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p166 7:137:6 مَشَـٰرِقَ; p73 3:177:3 ٱشْتَرَوُا۟; p184 8:55:2 شَرَّ |
| `c67a62dac223b371` | 3 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p147 6:144:6 ٱثْنَيْنِ ۗ; p42 2:255:23 يَشْفَعُ; p590 85:12:2 بَطْشَ |
| `cc51dd2c81af7b5d` | 2 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p48 2:282:74 ٱلشُّهَدَآءُ; p339 22:60:8 ثُمَّ |
| `549aa25d3d3b8045` | 2 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p257 14:11:8 مِّثْلُكُمْ; p128 6:1:10 ثُمَّ |
| `4ce8ce4a29a8697a` | 2 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p566 68:44:8 حَيْثُ; p178 8:13:3 شَآقُّوا۟ |
| `455352698d199f6a` | 2 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p182 8:41:5 شَىْءٍۢ; p456 38:51:6 كَثِيرَةٍۢ |
| `f2be66539939fa86` | 2 | a three-dot pyramid over ث/ش (pipeline had named it two_dots in one place) | p147 6:143:15 ٱشْتَمَلَتْ; p478 41:13:4 أَنذَرْتُكُمْ |
| `7a1efdc28805cc33` | 2 | a three-dot pyramid over ث/ش (pipeline had named it two_dots in one place) | p162 7:95:1 ثُمَّ; p202 9:99:18 قُرْبَةٌۭ |
| `56f41f1efdb3ad07` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p53 3:26:8 تَشَآءُ |
| `a4e0ded5ca7d28f5` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p89 4:69:14 وَٱلشُّهَدَآءِ |
| `58b9948668ff6b5e` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p97 4:117:10 شَيْطَـٰنًۭا |
| `bdd1998530460464` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p115 5:44:27 وَٱخْشَوْنِ |
| `b77003812b8257c4` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p125 5:106:39 ثَمَنًۭا |
| `2d586663d6e32fd0` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p164 7:111:7 حَـٰشِرِينَ |
| `1c1f61a0e1eac7a4` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p173 7:176:11 فَمَثَلُهُۥ |
| `a3b89bf6f008db92` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p179 8:19:20 كَثُرَتْ |
| `f45bd7f394d5f400` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p188 9:9:1 ٱشْتَرَوْا۟ |
| `9d8831203b6a7368` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p189 9:14:8 وَيَشْفِ |
| `6030ce44f83287b5` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p192 9:34:26 فَبَشِّرْهُم |
| `ffbec936560a6c30` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p193 9:39:11 شَيْـًۭٔا ۗ |
| `3e0f637043763421` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p194 9:46:11 فَثَبَّطَهُمْ |
| `02d228f99e84ed2f` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p228 11:54:10 أُشْهِدُ |
| `48fd1ac06465c234` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p229 11:68:12 لِّثَمُودَ |
| `ddb2e460fefc6287` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p230 11:72:8 شَيْخًا ۖ |
| `46332b919e070a54` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p231 11:85:9 أَشْيَآءَهُمْ |
| `7881011253582735` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p234 11:113:15 ثُمَّ |
| `f84c393faec1ef3e` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p258 14:24:9 كَشَجَرَةٍۢ |
| `df9184c5bdca4d5a` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p259 14:27:18 يَشَآءُ |
| `6ad720b0ec7729a5` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p264 15:36:6 يُبْعَثُونَ |
| `2782a47237efe6c4` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p266 15:87:5 ٱلْمَثَانِى |
| `ccffbc2685d48254` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p383 27:66:9 شَكٍّۢ |
| `3283bbaa32ab28fd` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p414 31:32:2 غَشِيَهُم |
| `4a3ecb0426f7073c` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p492 43:38:9 ٱلْمَشْرِقَيْنِ |
| `10cecf284c6b2659` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p493 43:60:2 نَشَآءُ |
| `305bd1115db4383c` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p504 46:17:15 يَسْتَغِيثَانِ |
| `d9cfb78f2b539da8` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p536 56:54:1 فَشَـٰرِبُونَ |
| `d7e631e5f73d20a2` | 1 | a three-dot pyramid riding over a ش or ث whose text wants 3 dots | p568 69:41:4 شَاعِرٍۢ ۚ |

### two_dots — 6 signatures, 6 occurrences

**two_dots** — horizontal dot pairs over ت/ق whose text wants exactly 2 dots (includes p4 تَتَّقُونَ from the 24-dot-words gap list).

| signature | n | seen | exemplars |
|---|---|---|---|
| `67c6888a92bfb9be` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p4 2:21:11 تَتَّقُونَ |
| `7acf79b0cfab4778` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p188 9:13:17 تَخْشَوْهُ |
| `c7af024b335f5214` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p210 10:15:2 تُتْلَىٰ |
| `00ef329b2446257a` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p280 16:112:4 قَرْيَةًۭ |
| `2a4ae5da2b3ae7f8` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p311 19:86:1 وَنَسُوقُ |
| `1e10a972d7157d39` | 1 | a horizontal two-dot pair over ت/ق whose text wants 2 dots | p569 70:26:2 يُصَدِّقُونَ |

### hizb — 23 signatures, 1498 occurrences

**hizb** — petals, teardrops and centre dots of the ۞ hizb rosette, seen in place in the rosette in every exemplar. 23 signatures, 1,498 occurrences — the single largest unlabeled family.

| signature | n | seen | exemplars |
|---|---|---|---|
| `3b9fbd634914b2fe` | 199 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p319 - ; p37 - ; p324 -  |
| `ac810c318ac736c4` | 199 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p204 - ; p336 - ; p270 -  |
| `394298c1fd373060` | 198 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p29 - ; p104 - ; p256 -  |
| `c6b95341b2f3c482` | 197 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p7 - ; p488 - ; p442 -  |
| `e6cf4ea18475b4e9` | 133 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p51 - ; p488 - ; p132 -  |
| `57a56085b2df9b9a` | 108 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p69 - ; p196 - ; p201 -  |
| `97f6acb393ca2664` | 92 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p526 - ; p284 - ; p259 -  |
| `21c74f795f60a8ae` | 91 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p499 - ; p104 - ; p464 -  |
| `2ceb9831fabd26a1` | 75 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p354 - ; p124 - ; p112 -  |
| `3a0d2864458ed08a` | 72 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p22 - ; p29 - ; p529 -  |
| `5f4982bfdcb75a75` | 36 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p34 - ; p134 - ; p124 -  |
| `9a72913eec0cb480` | 27 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p249 - ; p87 - ; p479 -  |
| `a5a9c8d1c9e23cb5` | 19 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p179 - ; p32 - ; p299 -  |
| `e0e7b7ec90ca0154` | 13 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p429 - ; p126 - ; p484 -  |
| `d8abca74e833f94b` | 12 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p167 - ; p456 - ; p444 -  |
| `82e845567c6a35ed` | 6 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p496 - ; p297 - ; p554 -  |
| `78a94eff5c8d42ad` | 5 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p369 - ; p472 - ; p547 -  |
| `ba0dbc08369a8b74` | 4 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p87 - ; p89 - ; p270 -  |
| `5f44f5e3727c338b` | 3 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p100 - ; p242 - ; p17 -  |
| `bf106fd18a52c950` | 3 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p162 - ; p575 - ; p402 -  |
| `6be8fd5eeea25550` | 3 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p324 - ; p194 - ; p569 -  |
| `a6399428f5540904` | 2 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p74 - ; p217 -  |
| `37294c7904016a15` | 1 | a petal/teardrop/centre piece of the 8-petal hizb rosette, seen in place in the rosette | p112 -  |

### small_meem — 13 signatures, 15 occurrences

**small_meem** — small detached م floating clear of the baseline at an iqlab position (areas 22-33, against ~98 for a real final م). The word's text carries ۭ/ۢ in every exemplar.

| signature | n | seen | exemplars |
|---|---|---|---|
| `2b230e47f996c508` | 2 | a small detached م floating clear of the baseline at an iqlab position | p590 84:25:9 مَمْنُونٍۭ; p602 106:4:7 خَوْفٍۭ |
| `78db55471472a3e0` | 2 | a small detached م under the ح of كَلَمْحٍۭ | p531 54:50:5 كَلَمْحٍۭ; p332 22:5:68 زَوْجٍۭ |
| `30910648c4cbdc54` | 1 | a small detached م floating clear of the baseline at an iqlab position | p407 30:32:8 حِزْبٍۭ |
| `766d967dc3337518` | 1 | a small detached م floating clear of the baseline at an iqlab position | p434 34:54:15 مُّرِيبٍۭ |
| `3ca90a532cbde72d` | 1 | a small detached م floating clear of the baseline at an iqlab position | p458 38:88:4 حِينٍۭ |
| `104265bff58faba7` | 1 | a small detached م floating clear of the baseline at an iqlab position | p500 45:22:8 نَفْسٍۭ |
| `fc14b76b6b9b4ede` | 1 | a small detached م floating clear of the baseline at an iqlab position | p506 46:35:21 نَّهَارٍۭ ۚ |
| `d569d870a7ea28ed` | 1 | a small detached م floating clear of the baseline at an iqlab position | p564 67:30:10 مَّعِينٍۭ |
| `0178c2fc5fdf4fd9` | 1 | a small detached م floating clear of the baseline at an iqlab position | p601 105:5:3 مَّأْكُولٍۭ |
| `88df5365d0cf4ec9` | 1 | a small detached م floating clear of the baseline at an iqlab position | p294 18:15:10 بِسُلْطَـٰنٍۭ |
| `20167b1cd805623e` | 1 | a small detached م floating clear of the baseline at an iqlab position | p97 4:114:14 إِصْلَـٰحٍۭ |
| `dc3f5427e32389c1` | 1 | a small detached م floating clear of the baseline at an iqlab position | p255 14:3:15 ضَلَـٰلٍۭ |
| `5a778bc68c5821af` | 1 | a small م (area 22.8 vs ~98 for real final meems) at the iqlab position of قَوْمٍۭ — the detached iqlab meem | p92 4:90:5 قَوْمٍۭ |

### waqf — 13 signatures, 23 occurrences

**waqf** — stop signs riding above their word with clear separation: the ج sign and its tiny dot pieces, the صلى and قلى signs, and the rare shapes Abdullah asked about — the small-seen ۜ at 2:245 وَيَبْصُۜطُ and 83:14 بَلْ ۜ, and the small-high-meem ۘ at 3:181, 5:51 and 74:53. Each was applied only where the rendered sign rides above the word as a stop sign AND the KFGQPC text carries the sign.

| signature | n | seen | exemplars |
|---|---|---|---|
| `64021459b9bc0b6d` | 5 | the tiny dot piece of the ج stop sign, at words whose KFGQPC text carries the sign | p104 4:170:11 لَّكُمْ ۚ; p114 5:41:50 شَيْـًٔا ۚ; p251 13:17:22 مِّثْلُهُۥ ۚ |
| `3eeb660659f2821c` | 4 | a small ج riding above the word as a stop sign, clearly separated | p350 24:4:16 أَبَدًۭا ۚ; p350 24:3:14 مُشْرِكٌۭ ۚ; p567 69:17:3 أَرْجَآئِهَا ۚ |
| `77eeeabbc6599441` | 2 | the tiny dot piece of the ج stop sign, at words whose KFGQPC text carries the sign | p507 47:3:13 رَّبِّهِمْ ۚ; p507 47:4:20 أَوْزَارَهَا ۚ |
| `ffc3110539a39415` | 2 | a small ج riding above the word as a stop sign, clearly separated | p350 24:3:14 مُشْرِكٌۭ ۚ; p350 24:4:16 أَبَدًۭا ۚ |
| `90815405083e2544` | 2 | a small ج riding above the word as a stop sign, clearly separated | p507 47:3:13 رَّبِّهِمْ ۚ; p507 47:4:20 أَوْزَارَهَا ۚ |
| `a9a50fad0014337c` | 1 | a small ج riding above the word as a stop sign, clearly separated | p510 47:30:5 بِسِيمَـٰهُمْ ۚ |
| `da39dc1bced8a65f` | 1 | the small س sign (ۜ) riding clear above يَبْصُۜطُ / بَلْ ۜ — the rare small-seen stop | p39 2:245:14 وَيَبْصُۜطُ |
| `d87308a7a23e7842` | 1 | the small س sign (ۜ) riding clear above يَبْصُۜطُ / بَلْ ۜ — the rare small-seen stop | p588 83:14:2 بَلْ ۜ |
| `f2b91a63b30ff50b` | 1 | a small م riding above the word at a ۘ position (3:181, 5:51, 74:53) — the rare small-high-meem stop | p74 3:181:11 أَغْنِيَآءُ ۘ |
| `0565ae88d5cfc527` | 1 | a small م riding above the word at a ۘ position (3:181, 5:51, 74:53) — the rare small-high-meem stop | p117 5:51:8 أَوْلِيَآءَ ۘ |
| `5e6bc15210e216e6` | 1 | a small م riding above the word at a ۘ position (3:181, 5:51, 74:53) — the rare small-high-meem stop | p577 74:53:1 كَلَّا ۖ |
| `640a81d80826d822` | 1 | the صلى sign riding above the word | p366 25:77:7 دُعَآؤُكُمْ ۖ |
| `433cf5b5a6471865` | 1 | the قلى sign riding above the word | p507 47:4:30 بِبَعْضٍۢ ۗ |

### shaddah — 3 signatures, 354 occurrences

**shaddah** — the three-toothed shaddah crown: over رّ of الرَّحِيم/الرَّحْمَٰن in every surah-header basmalah (2 sigs, n=352+2) and over نّ of إِنَّهُمْ (p117). The pipeline had been calling the basmalah one `fathah`.

| signature | n | seen | exemplars |
|---|---|---|---|
| `2aa6c3f0dcbe8b58` | 350 | a three-toothed shaddah crown directly over the ر of الرَّحِيم/الرَّحْمَٰن in the surah-header basmalah | p262 - ; p428 - ; p496 -  |
| `eaa32fb3f9767f8d` | 2 | the three-toothed shaddah crown over the ذ of الذَّارِيَات header | p520 - ; p520 -  |
| `c7c47ddcad164b86` | 2 | a three-toothed shaddah over the نّ of إِنَّهُمْ | p117 5:53:10 إِنَّهُمْ; p309 19:58:27 خَرُّوا۟ |

### dot — 2 signatures, 223 occurrences

**dot** — diamond letter-dots: the ب dot of بِسْمِ in every header basmalah (n=222, the pipeline had called it `kasrah`), and the ج dot of مَرْجِعُهُمْ p216.

| signature | n | seen | exemplars |
|---|---|---|---|
| `6ba0771f866131b8` | 222 | the diamond letter_dot below the ب of بِسْمِ in the surah-header basmalah | p566 - ; p600 - ; p601 -  |
| `17bb026e5da235cf` | 1 | the diamond dot below the ج of مَرْجِعُهُمْ | p216 10:70:6 مَرْجِعُهُمْ |

### small_yaa — 3 signatures, 4 occurrences

**small_yaa** — the curled ۦ suffix mark after هِ where the text spells ـهِۦ.

| signature | n | seen | exemplars |
|---|---|---|---|
| `bc4bcbe3ab5b533a` | 2 | the curled ۦ suffix mark after هِ, where the text spells ـهِۦ | p567 69:19:5 بِيَمِينِهِۦ; p567 69:25:5 بِشِمَالِهِۦ |
| `232f8e292d3ebf0c` | 1 | the curled ۦ suffix mark after هِ, where the text spells ـهِۦ | p367 26:6:7 بِهِۦ |
| `a418a276f2ae0e53` | 1 | the curled ۦ suffix mark after هِ, where the text spells ـهِۦ | p569 70:12:1 وَصَـٰحِبَتِهِۦ |

### small_waw — 2 signatures, 6 occurrences

**small_waw** — the small ۥ suffix mark after هُ where the text spells ـهُۥ.

| signature | n | seen | exemplars |
|---|---|---|---|
| `3678ca3506173ef9` | 5 | the small ۥ suffix mark after هُ, where the text spells ـهُۥ | p589 84:15:3 رَبَّهُۥ; p589 84:10:4 كِتَـٰبَهُۥ; p589 84:13:1 إِنَّهُۥ |
| `d3ccd05aa180deea` | 1 | the small ۥ suffix mark after هُ, where the text spells ـهُۥ | p350 24:10:5 وَرَحْمَتُهُۥ |

### maddah — 2 signatures, 2 occurrences

**maddah** — the long wave over يَـٰٓأَيُّهَا (p101) and صَلَّىٰٓ (p597).

| signature | n | seen | exemplars |
|---|---|---|---|
| `7589b593c99c5460` | 1 | the long wavy maddah over يَـٰٓأَيُّهَا / صَلَّىٰٓ | p101 4:144:1 يَـٰٓأَيُّهَا |
| `6404acd6394836f9` | 1 | the long wavy maddah over يَـٰٓأَيُّهَا / صَلَّىٰٓ | p597 96:10:3 صَلَّىٰٓ |

### tanwin_al_damm — 1 signatures, 3 occurrences

**tanwin_al_damm** — the curled tanwin form over سُورَةٌ and حَكِيمٌ (p350), matching the 11 existing tanwin_al_damm entries; the text carries ٌ with no plain dammah nearby.

| signature | n | seen | exemplars |
|---|---|---|---|
| `a02644084784c752` | 3 | the curled tanwin form ٌ above سُورَةٌ / حَكِيمٌ whose text carries tanwin_al_damm and no plain dammah nearby | p350 24:10:9 حَكِيمٌ; p350 24:10:8 تَوَّابٌ; p350 24:1:1 سُورَةٌ |

### ignore — 3 signatures, 3 occurrences

**ignore** — degenerate zero-area contours that draw nothing (matches the existing 'degenerate sliver' convention).

| signature | n | seen | exemplars |
|---|---|---|---|
| `e717243a05820027` | 1 | a degenerate zero-area contour that draws nothing | p77 4:3:28 تَعُولُوا۟ |
| `f12a01cc0390aeac` | 1 | a degenerate zero-area contour that draws nothing | p90 4:75:4 تُقَـٰتِلُونَ |
| `641a18dfa9860c41` | 1 | a degenerate zero-area contour that draws nothing | p152 7:15:1 قَالَ |


## B. NEEDS ABDULLAH'S CONFIRMATION — 47 signatures

Strong guesses the rules forbid me to apply. Each row: look at the PNG, confirm or override.

| signature | n | my guess | options | what I saw | first exemplar | PNG |
|---|---|---|---|---|---|---|
| `725bf6c3424444ac` | 6 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p128 -  | 725bf6c3424444ac_128_-_1575.png |
| `82c409aeebbdbd12` | 6 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p393 28:63:10 أَغْوَيْنَـٰهُمْ | 82c409aeebbdbd12_162_7-88-19_260.png |
| `9c598c7381df35fa` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p591 86:6:3 مَّآءٍۢ | 9c598c7381df35fa_591_86-6-3_2677.png |
| `6c43bc2832fa02df` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p77 -  | 6c43bc2832fa02df_077_-_1367.png |
| `1cc257d93bf79599` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p77 -  | 1cc257d93bf79599_077_-_1374.png |
| `363b4d12c06677d6` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p128 -  | 363b4d12c06677d6_128_-_1545.png |
| `016b1e0c0d2962ad` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p151 -  | 016b1e0c0d2962ad_151_-_1579.png |
| `89e2b8d21cbd89ff` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p255 -  | 89e2b8d21cbd89ff_255_-_1727.png |
| `79f80025a7bac5ee` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p322 -  | 79f80025a7bac5ee_322_-_1592.png |
| `cce48203ae4539ec` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p367 -  | cce48203ae4539ec_367_-_1333.png |
| `52d78b2f4f1e887a` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p418 -  | 52d78b2f4f1e887a_418_-_1567.png |
| `fcdef4823e3a24c8` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p483 -  | fcdef4823e3a24c8_483_-_1512.png |
| `71b9efe1459feed4` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p578 -  | 71b9efe1459feed4_578_-_1700.png |
| `57e3842c28106e30` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p457 38:79:3 فَأَنظِرْنِىٓ | 57e3842c28106e30_457_38-79-3_2319.png |
| `46fa70949be2ca41` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p276 16:87:2 إِلَى | 46fa70949be2ca41_276_16-87-2_309.png |
| `8abe218cb6c018d0` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p282 -  | 8abe218cb6c018d0_282_-_1366.png |
| `f01e236eb613884d` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p375 26:205:2 إِن | f01e236eb613884d_375_26-205-2_3267.png |
| `fec4e33ad260f82a` | 2 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p567 69:25:1 وَأَمَّا | fec4e33ad260f82a_567_69-25-1_3211.png |
| `14c09cb852c4068f` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p303 18:84:9 شَىْءٍۢ | 14c09cb852c4068f_303_18-84-9_860.png |
| `d6c97b5d3d42cb36` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p307 19:28:7 سَوْءٍۢ | d6c97b5d3d42cb36_307_19-28-7_868.png |
| `f5662d69238b800b` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p377 27:11:8 سُوٓءٍۢ | f5662d69238b800b_377_27-11-8_2515.png |
| `eb79ed47a924f140` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p582 78:14:4 مَآءًۭ | eb79ed47a924f140_582_78-14-4_2548.png |
| `017177baf5342fae` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p590 85:9:9 شَىْءٍۢ | 017177baf5342fae_590_85-9-9_1303.png |
| `d3ef647249414bef` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline (the spelled ء of شىء/سوء/ماء/قرءان) — hamzah vs letter_hamzah cannot be chosen from ink | p215 10:61:9 قُرْءَانٍۢ | d3ef647249414bef_215_10-61-9_217.png |
| `7e8b5a322f567f14` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p233 11:101:18 جَآءَ | 7e8b5a322f567f14_233_11-101-18_2236.png |
| `1d0eb0fdc2217098` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline in a surah-header title (atop/below the alef of الأنفال/الأعراف/إبراهيم or the ء of النساء/الشعراء) — hamzah vs letter_hamzah cannot be chosen from ink | p582 78:27:2 كَانُوا۟ | 1d0eb0fdc2217098_582_78-27-2_87.png |
| `f321c7f285ee653e` | 1 | **waqf** | waqf/ignore | a piece of the قلى sign at 47:4:30 (same spot as 433cf5b5) but not visibly distinct in the render — near-certain waqf, confirm. | p507 47:4:30 بِبَعْضٍۢ ۗ | f321c7f285ee653e_507_47-4-30_1775.png |
| `a4591229873032ab` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline atop the و seat of ءَابَآؤُكُم — hamzah family, cannot label from ink | p159 7:71:14 وَءَابَآؤُكُم | a4591229873032ab_159_7-71-14_449.png |
| `066486bc38b725fe` | 1 | **dammah** | dammah/hamzah | a dammah-shaped curl above أُ of أُو۟لَـٰٓئِكَ / أُوتِيَ — text wants dammah, but dammah/hamzah-curl lookalikes need a human | p342 23:7:5 فَأُو۟لَـٰٓئِكَ | 066486bc38b725fe_342_23-7-5_2611.png |
| `7f62ddef9e4deb24` | 1 | **dammah** | dammah/hamzah | a dammah-shaped curl above أُ of أُو۟لَـٰٓئِكَ / أُوتِيَ — text wants dammah, but dammah/hamzah-curl lookalikes need a human | p567 69:25:3 أُوتِىَ | 7f62ddef9e4deb24_567_69-25-3_2858.png |
| `7958f348d6513fd7` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p92 4:90:29 إِلَيْكُمُ | 7958f348d6513fd7_092_4-90-29_2947.png |
| `da84703607315d34` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p260 14:34:6 وَإِن | da84703607315d34_260_14-34-6_1248.png |
| `8e26ff526443c953` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p265 15:64:3 وَإِنَّا | 8e26ff526443c953_265_15-64-3_1386.png |
| `b19402f391b74aaa` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p319 20:100:2 أَعْرَضَ | b19402f391b74aaa_319_20-100-2_2465.png |
| `9dcf9ca6b74cffee` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p323 21:13:4 إِلَىٰ | 9dcf9ca6b74cffee_323_21-13-4_2206.png |
| `4c71c4c79444b117` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p327 21:58:7 إِلَيْهِ | 4c71c4c79444b117_327_21-58-7_974.png |
| `b04c23233cc9af73` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p327 21:68:5 إِن | b04c23233cc9af73_327_21-68-5_480.png |
| `ddb859b599d1d6f0` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p345 23:53:2 أَمْرَهُم | ddb859b599d1d6f0_345_23-53-2_2099.png |
| `2d58f24dccb47721` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p350 24:3:11 إِلَّا | 2d58f24dccb47721_350_24-3-11_2761.png |
| `82e8b81a30ce5334` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p367 26:10:5 أَنِ | 82e8b81a30ce5334_367_26-10-5_1758.png |
| `312d286ce1c8d395` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p371 26:95:3 أَجْمَعُونَ | 312d286ce1c8d395_371_26-95-3_2876.png |
| `59b22ba90abd91ec` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p377 27:6:1 وَإِنَّكَ | 59b22ba90abd91ec_377_27-6-1_2424.png |
| `f69525f74d786600` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p431 34:23:17 رَبُّكُمْ ۖ | f69525f74d786600_431_34-23-17_1884.png |
| `3e08397a46167956` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p457 38:76:2 أَنَا۠ | 3e08397a46167956_457_38-76-2_2225.png |
| `c8ec13f842cdc88e` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p481 41:39:3 أَنَّكَ | c8ec13f842cdc88e_481_41-39-3_2566.png |
| `aec07d89759fe3bc` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p567 69:17:3 أَرْجَآئِهَا ۚ | aec07d89759fe3bc_567_69-17-3_1867.png |
| `f574573f9b426d1a` | 1 | **letter_hamzah** | hamzah/letter_hamzah | a hamzah outline, nearly always seated on/under an alef the text spells with أ/إ — hamzah vs letter_hamzah cannot be chosen from ink | p567 69:19:1 فَأَمَّا | f574573f9b426d1a_567_69-19-1_592.png |


## C. NEEDS ABDULLAH'S DECISION — 14 signatures

- `f0bd6b45e7fdf5ce` (n=73, areas [21.27, 99.99], pipeline called it ['', 'small_meem']) — One signature, two meanings: 72 occurrences are the full-size final ن (area ~100) of words ending نٌۭ/نٍۢ, and 1 occurrence (p329 21:88:7 نُـۨجِى, area 21) is the small high noon ۨ. A single table label cannot serve both; small_noon is not in _DUAL_SIZE_CAP, so even the size-gate mechanism cannot carry it today. Recommend: letter + a rule-side size cap, decided by Abdullah/the rules agent. First exemplar p329 21:88:7 نُـۨجِى. PNGs: f0bd6b45e7fdf5ce_190_9-21-5_1136.png, f0bd6b45e7fdf5ce_329_21-88-7_1947.png, f0bd6b45e7fdf5ce_532_55-26-4_928.png
- `448337c0c4b14f73` (n=3, areas [1.43, 1.55], pipeline called it ['', 'waqf']) — Rendered evidence: a tiny dot appearing both beside a ۗ sign (4:141) and inside نُـۨجِى (21:88) — mixed contexts. First exemplar p101 4:141:29 ٱلْقِيَـٰمَةِ ۗ. PNGs: 448337c0c4b14f73_101_4-141-29_2234.png, 448337c0c4b14f73_329_21-88-7_1960.png
- `d3fddfa7a740f3b9` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: bbox degenerate (area 0.0) yet a piece renders — needs a closer look at لَوَٰقِحَ p263. First exemplar p263 15:22:3 لَوَٰقِحَ. PNGs: d3fddfa7a740f3b9_263_15-22-3_2924.png
- `6a025720b9a38dfa` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p262 15:4:6 وَلَهَا. PNGs: 6a025720b9a38dfa_262_15-4-6_2449.png
- `58479c4cb8f9c0c4` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p346 23:61:6 لَهَا. PNGs: 58479c4cb8f9c0c4_346_23-61-6_1554.png
- `5e3072c168f5aa06` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p346 23:63:13 لَهَا. PNGs: 5e3072c168f5aa06_346_23-63-13_3150.png
- `4fa102d4d8466bf3` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p350 24:2:26 ٱلْمُؤْمِنِينَ. PNGs: 4fa102d4d8466bf3_350_24-2-26_2761.png
- `2d2575c85ad2b7ae` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p370 26:71:5 لَهَا. PNGs: 2d2575c85ad2b7ae_370_26-71-5_1708.png
- `4bce971866bcd297` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p437 35:24:3 بِٱلْحَقِّ. PNGs: 4bce971866bcd297_437_35-24-3_684.png
- `3e54d0d060541c86` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p453 38:15:8 لَهَا. PNGs: 3e54d0d060541c86_453_38-15-8_3179.png
- `5ea400f4888e086d` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p519 50:26:5 إِلَـٰهًا. PNGs: 5ea400f4888e086d_519_50-26-5_653.png
- `5e468c388a190b7d` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p523 51:52:2 مَآ. PNGs: 5e468c388a190b7d_523_51-52-2_2651.png
- `5e2573a020369bdc` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p529 54:27:6 فَٱرْتَقِبْهُمْ. PNGs: 5e2573a020369bdc_529_54-27-6_1344.png
- `d50d5aab27472231` (n=1, areas [0.0, 0.0], pipeline called it ['']) — Rendered evidence: the highlighted piece was not visibly distinct in the rendered window (tiny sliver or occluded) — needs a closer look. First exemplar p590 85:11:6 لَهُمْ. PNGs: d50d5aab27472231_590_85-11-6_288.png


## Findings that are NOT label problems (for the rules channel)

- **Round-7 waqf deficits are partition/kind defects, not label gaps.** p49 وَأَطَعْنَاۖ draws its ۖ but the element is `kind=body` with an EMPTY mark name — its signature `f5581079d942b4` is already labeled `waqf` in the table. p42 خَلْفَهُمْۖ, p91 تَقُولُۖ, p399 لُوطٌۘ, p525 ٱلْمُصَۣيْطِرُونَ hold no waqf ink at all in their own elements — the sign's ink is owned elsewhere. No table entry can fix either case.
- **The muʿānaqah ۛ dots share the plain letter_dot signature** (`d2506e4f8b4e28`, labeled `dot`): p2/p112/p114 name those occurrences `waqf` from position (waqf_places), so the label is right and position naming does the rest — same class as Abdullah's 9514d0381190 note.
- **The iqlab final-letter steal.** 100+ words ending ٌۭ/ٍۢ/ًۭ had their final letter read as a mark named small_meem. The letter labels above repair every observed word, but whatever pass makes that classification will do it again to any new shape; worth a rule-side look.

## Measurements

All applied labels went through `tools/apply_labels.py` (backup kept: `.cache/marks/labels.json.20260826-233403.bak`), measured group-at-a-time on a 20-page audit sample (the label_bisect 11 pages + 9 pages where the new labels concentrate: 33, 51, 74, 117, 190, 414, 507, 525, 588), then bench and a before/after page comparison.

**Group measurement** (flag delta on the 20-page sample, each group applied alone against the pre-change table; baseline 19 flags):

| group | sigs | delta | pages worse |
|---|---|---|---|
| hizb | 23 | +0 | none |
| dot-family (dot/two_dots/three_dots) | 45 | +0 | none |
| shaddah | 3 | +0 | none |
| slash (fathah) | 52 | **-2** | none |
| small_meem | 13 | +0 | none |
| letter | 111 | +0 | none |
| misc (maddah/tanwin_al_damm/ignore) | 6 | +0 | none |
| waqf | 13 | **-3** | none |
| suffix (small_waw/small_yaa) | 5 | +0 | none |

No group made any page worse, so the whole set was applied — no signature had to be reverted.

**Whole set applied, same 20 pages:** 19 flags -> 14 (**-5**), no page worse:
p74 1->0 (the ۘ at 3:181), p117 1->0 (the ۘ at 5:51), p286 1->0, p588 2->0 (the ۜ at 83:14 + a tanwin_al_kasr half).

**Bench** — identical before and after the labels, measured both ways on the same build:
`budget-mismatch words: 5/1399 | width bad 1/1399 mean 0.0597 | pixelfail 0 | FAILURES: none | SCORE: 79`

The `letter` group's +0 on the audit sample is expected: the misread final letters had been NAMED `small_meem`, which no audit counts, so the words sat silently broken. The labels repair the decomposition (the letter ink returns to the word body) without moving any counted number; the words they fix are visible in the emitted SVG, not in these audit counts.

**Note on sweep-dir baselines:** `.cache/sweeps/final` and `base2` predate other work in flight and count more than this audit's rows, so they are not an apples-to-apples "before" for a label-only change; the before/after above was measured on identical code with only the table swapped.

## Reference corroboration (MushafDatabase)

After applying, `tools/sig_labels_from_ref.py` was run over the 258 exemplar pages to read what MushafDatabase calls the same ink (registration to ~0.01u, IoU >= 0.35):

- **letter** — of the 111 applied letter signatures, the reference names **110 as `text/...`** and 1 as `kaf-hamzah` (also a text glyph on their side). Zero called a diacritic. This independently confirms the whole iqlab final-letter family.
- **waqf** — the rare signs came back `waqf lazim`, `waqf sali`, and `diacritic/small seen` (their name for ۜ, which this repo counts under `waqf` — TEXT_WANT includes U+06DC/U+06E3). Consistent.
- **slash halves / small iqlab meems** — mostly "(nothing there)": the reference draws the tanwin_al_kasr pair and the fused tanwin+meem as one path offset from our half-strokes, so no overlapping piece exists. Not a contradiction.
- **hamzah queue (section B)** — the reference splits them: 8 signatures it calls `text/ء`, 21 it calls `diacritic/hamzah`. Each queue item in `visual_label_queue.json` now carries a `mushafdatabase_calls_it` field, so most of section B can be settled by reading that field against the exemplar.

No applied label was contradicted by the reference; nothing was reverted.
