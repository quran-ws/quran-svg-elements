# Arabic terminology for this project

The vocabulary for the Arabic demo page and any future Arabic documentation. **Decide each term once
here and use it everywhere** — synonym rotation is a defect in technical Arabic, not variety.

Companion to `docs/arabic-rtl-plan.md`. The language authority is the global `arabic-writer` skill
(`~/.claude/skills/arabic-writer/`); this file only fixes *this project's* nouns.

**This file contains no Quranic text.** Every term below is an ordinary Arabic common noun. Quranic
content in the demo comes only from the verified cached sources — never hand-typed, in Arabic or in
English. That rule is absolute and the translation does not relax it.

---

## 1. Domain terms

| English | Arabic | notes |
|---|---|---|
| mushaf | **المصحف** | The printed volume. `مصحف المدينة النبوية` for the Madinah Mushaf. |
| the print / the printed edition | **الطبعة** | Use where the English says "the print" meaning the physical edition. |
| ayah | **آية** (ج. **آيات**) | |
| surah | **سورة** (ج. **سُوَر**) | |
| juz | **جزء** (ج. **أجزاء**) | |
| hizb | **حزب** (ج. **أحزاب**) | |
| rubʿ | **رُبع** (ج. **أرباع**) | |
| nisf | **نصف** | |
| sajdah sign | **علامة السجدة** | The drawn sign. Bare `سجدة` is the prostration, not the sign — keep `علامة` when the sign is meant. |
| waqf sign | **علامة الوقف** (ج. **علامات الوقف**) | Same distinction: the sign, not the pause. |
| ayah medallion / marker | **علامة رأس الآية** | The decorative circle ending an ayah. Short form `علامة الآية` once introduced. Do **not** call it `فاصلة` — that is the comma. |
| basmalah | **البسملة** | |
| surah header | **عنوان السورة** | |
| iqlab meem | **ميم الإقلاب** | |
| tanween | **تنوين** | |
| fatha / kasra / damma | **فتحة / كسرة / ضمة** | |
| shadda / sukun / maddah | **شدّة / سكون / مدّة** | |
| dagger alef | **الألف الخنجرية** | |
| alef wasla | **ألف الوصل** | |
| hamza | **همزة** | The project distinguishes a hamza that is a diacritic from one that is a letter: **الهمزة علامةً** vs **الهمزة حرفاً**, or gloss with `data-kind`. |

---

## 1a. Qiraa, riwaya and the counting system

The nine new root attributes need these. **Every one of these terms is a technical term of the
Quranic sciences with a settled Arabic form** — there is nothing to coin, and no transliteration is
ever correct in the Arabic text. Use the Arabic; keep the attribute name and value Latin.

| English | Arabic | attribute | notes |
|---|---|---|---|
| qiraa / reading | **قراءة** (ج. **قراءات**) | `data-qiraa` | The reading tradition, named for its imam. Value stays Latin (`asim`); prose says **عاصم**. |
| riwaya / transmission | **رواية** (ج. **روايات**) | `data-riwaya` | The transmission from that imam. Value Latin (`hafs`); prose says **حفص**. |
| Hafs from Asim | **رواية حفص عن عاصم** | — | The full standard formula. Use it in full on first mention; `رواية حفص` after. Note `عن`, not `من`. |
| Warsh from Nafi | **رواية ورش عن نافع** | — | Same pattern, for the portability note. |
| ayah numbering system | **نظام عدّ الآي** | `data-ayah-numbering` | Also **العدّ** alone once introduced. `عدّ الآي` is the established term of the discipline (علم الفواصل); `ترقيم` is a printing word and is weaker here. |
| total ayahs | **إجمالي الآيات** | `data-ayah-total` | |
| edition | **الطبعة** | `data-edition` | |
| ~~mushaf name~~ **riwaya name** | **تسمية الرواية** | `data-mushaf-name-ar` / `-en` | **Corrected 2026-08-30 against the actual data.** An earlier version of this row said `اسم المصحف`, guessing from the attribute's *name*. The attribute does not hold a mushaf name: page 042 carries `data-mushaf-name-ar="حفص عن عاصم"` and `data-mushaf-name-en="Hafs 'an Asim"` — the riwaya formula. Never re-translate the `-ar` value; reproduce it. **The attribute name is misleading and is worth raising against the schema, not papering over in translation.** |
| mushaf | **المصحف** | `data-mushaf` | |
| page | **الصفحة** | `data-page` | |

### The counting systems

`data-ayah-numbering` names which madhhab of ayah-division the edition follows. The Madinah Mushaf
uses the **Kufan** count, which is why the total is 6,236.

| system | Arabic | value |
|---|---|---|
| Kufan | **العدّ الكوفي** | `kufi` |
| Madani first | **العدّ المدني الأول** | `madani-first` |
| Madani last | **العدّ المدني الأخير** | `madani-last` |
| Basran | **العدّ البصري** | `basri` |
| Meccan | **العدّ المكي** | `makki` |
| Damascene | **العدّ الشامي** | `shami` |

**Translated, not transliterated, and here is the reason.** These are ordinary Arabic nisba
adjectives — `كوفي` is simply "of Kufa". Writing `كوفي` is not a translation choice at all, it is the
word. Transliterating the English back (`كوفي` ← *kufi*) would arrive at the same place by a worse
route; treating them as opaque identifiers (`العدّ kufi`) would be wrong. **The attribute values
stay Latin** (`kufi`, `madani-first`) because they are machine keys.

Write the ordinal in `madani-first` / `madani-last` as **الأول** / **الأخير** — not `الثاني`. The
pair is "first" and "last", not "first" and "second".

### The trap here

`قراءة` and `رواية` are **not interchangeable**, and English-language sources routinely blur them —
"the Hafs qiraa" is a common error. A `قراءة` is the reading of one of the imams; a `رواية` is one
transmitter's line from that imam. **Hafs is a riwaya, Asim is the qiraa.** The English demo may
be loose about this; the Arabic must not be, because an Arabic reader will notice immediately.

Likewise `عدّ` (counting the ayahs, a science with named madhhabs) is not `ترقيم` (putting numbers on
them, a printing operation). The attribute is about the former.

---

## 2. Structure terms

| English | Arabic | notes |
|---|---|---|
| page | **صفحة** (ج. **صفحات**) | |
| line | **سطر** (ج. **أسطر**) | A printed line of the mushaf. |
| word | **كلمة** (ج. **كلمات**) | See §4 — the project's "word" is a keyed unit, not always a written word. |
| letter | **حرف** (ج. **حروف**) | |
| mark | **علامة** (ج. **علامات**) | The **superset**: any named non-letter ink — vowels, tanween, waqf and sajdah signs, iqlab meems. |
| diacritic / haraka | **حركة** (ج. **حركات**) | The **vowel subset only**. Not interchangeable with `علامة`. See §4. |
| tashkeel (the system) | **التشكيل** | The practice of vocalisation, not an individual mark. |
| element | **عنصر** (ج. **عناصر**) | |
| group | **مجموعة** | |
| ligature | *see §4 — unresolved* | Do not guess. |
| fragment (of an ayah on one line) | **جزء** / **مقطع** | Prefer `مقطع` — `جزء` already means juz. Say `مقطع من الآية`. |
| reading order | **ترتيب القراءة** | |
| document order | **ترتيب المستند** | |

---

## 3. Technical terms

| English | Arabic | notes |
|---|---|---|
| file | **ملف** (ج. **ملفات**) | `ملفات SVG` — never `الSVGات`. |
| attribute | **سمة** (ج. **سمات**) | The attribute *name* itself is never translated. |
| value | **قيمة** | |
| selector | **مُحدِّد** | Introduce as `مُحدِّد (selector)` once, then `مُحدِّد`. |
| element (DOM) | **عنصر** | |
| browser | **متصفح** | |
| network | **شبكة** | |
| search | **بحث** | |
| index | **فهرس** | |
| bundle | **الحزمة** | |
| highlight | **تظليل** | The band behind the ink. Verb `يُظلِّل`. |
| hit area / tap target | **منطقة اللمس** | |
| spelling / orthography | **الرسم الإملائي** | Careful — see §4 on `رسم`. |
| uthmani spelling | **الرسم العثماني** | Established term; use it. |
| glyph | **الشكل الحرفي (glyph)** | Gloss on first use, then keep the Latin `glyph` if it recurs in a technical sense. |
| ink | **الحبر** | See §4. **Never** `رسم`. |
| artwork | **العمل الفني** / **الرسوم المتجهة** | The source vector artwork. The KFGQPC portal's own wording is `رسم المتجهات المتقدمة`. |
| vector | **متجه** (ج. **متجهات**) | |
| pixel-identical | **مطابق بالبكسل** | |
| decomposition | **التفكيك** | What this project does to a page. |
| audit / gate | **تدقيق** / **بوابة** | |
| recitation | **تلاوة** | The act. `التلاوة` for the section title. |
| reciter | **القارئ** | |
| murattal | **المرتَّل** | The measured style, as against `المجوَّد`. A technical term — do not translate it as "slow" or "simple". |
| al-Minshawi | **الشيخ محمد صدّيق المنشاوي** | Use the reciter's name as Arabic sources write it; do not transliterate back from the English. |
| play / pause | **تشغيل** / **إيقاف مؤقت** | Buttons → maṣdar. |
| follow along | **المتابعة** | |
| tooltip | **تلميح** | |
| word meaning | **معنى الكلمة** | |
| contents | **المحتويات** | The generated section list. `فهرس` is reserved for the search index above — do not use it for both. |
| library | **مكتبة** | |
| plain JS / library toggle | **بدون مكتبة** / **بمكتبة** | Proposed. Avoids transliterating "JS"; the code itself stays Latin either way. |
| polygon | **مضلّع** | The single highlight polygon. |
| completeness rule | **قاعدة الاكتمال** | For the ayah-number stamping rule. |

---

## 3a. Terms settled during the translation

These were **not** in the glossary when the demo was translated; each was decided by a translator and
then reconciled across the whole page. They are binding now. Where two translators disagreed, the
resolution and its reason are recorded.

| English | Arabic | note |
|---|---|---|
| production / dev **profile** | **وضع الإنتاج** / **وضع التطوير** | "both profiles" → `الوضعان معاً`. **Resolved conflict:** one translator used `الصيغة الإنتاجية`, another `وضع الإنتاج`, and the page shipped both. Standardised on `وضع` (mode) so `صيغة` stays free for its ordinary sense of *form* — which the page also needs, in `الصيغة search` and `بصيغة إملائية أخرى`. |
| format (the spec) | **مواصفة الصيغة** | `FORMAT.md`. Distinct concept from profile; no collision now that profile is `وضع`. |
| lab (the interactive box) | **المختبر** | |
| snippet | **مقتطف** | Deliberately **not** `مقطع`, which is reserved for an ayah fragment. |
| stage | **المسرح** | The paper the page is drawn on, beside the editor. |
| contour | **كفاف** | Glossed once as `الكفافات (contours)`. Recurs in the pixel-identity audits. |
| raster comparison | **مقارنة نقطية (raster)** | |
| bounding box | **المربع المحيط** | |
| hit-testing / hit layer | **اختبار الإصابة** / **طبقة اللمس** | Extends the existing `منطقة اللمس`. |
| stroke / fill (SVG) | **الحدّ** / **التعبئة** | |
| halo | **الهالة** | The transparent stroke that widens a tap target. |
| subpath | **مسار فرعي** | |
| antialiasing | **تنعيم الحواف** | |
| seam | **حدّ ظاهر** | |
| leading | **تباعد الأسطر** | |
| crop | **اقتصاص** | |
| payload | **الحمولة** | |
| clipboard | **الحافظة** | |
| caret | **مؤشر الكتابة** | |
| ascenders / descenders | **الصواعد والنوازل** | |
| transform chain | **سلسلة التحويلات** | |
| fallback font | **الخط الاحتياطي** | |
| headless browser | **متصفح بلا واجهة رسومية** | |
| combining marks | **علامات متراكبة** | |
| long vowels | **حروف المدّ** | |
| stroke (of a fatha/kasra) | **شَرطة** | Avoids `رسم`, which is reserved. |
| rosette | **وردة** | `ورود الأرباع`, `وردة حزب`. |
| signature (`data-sig`) | **بصمة شكل** | |
| slider | **منزلق** | |
| preset | **إعداد مسبق** | |
| taxonomy | **تصنيف** | |
| tick (of a clock) | **نبضة** | |
| transport (play/scrub bar) | **شريط التحكم** | |
| memorisation prompt | **مُلقِّن الحفظ** | From `التلقين`, the actual hifz practice. |
| the ground (paper behind ink) | **الأرضية** | |
| furniture (decorative surround) | **الزخرفة** | A printing-trade idiom with no Arabic equivalent; the dry register is lost. |
| fold / normalise (search forms) | **توحيد الصور** | A paraphrase, not a term of art. |
| spelling (one of the five forms) | **الصورة الإملائية** | Deliberately **not** bare `الرسم`. |
| bundler | **المُحزِّم** | |
| paint / recolour | **التلوين** | Never `رسم`. |

**Left in English on purpose:** aligned readout labels inside the output panes (`words`,
`ayah fragments`, `viewBox`, `profile`), because they are a column format in a left-to-right
monospace pane, not prose. Sentences in those same panes **are** translated.

---

## 4. The four traps

These are the places where an obvious translation is wrong. Get them right or the Arabic page will
say something the English does not.

### `رسم` is already taken

`data-rasm` is the **uthmani spelling skeleton**, and `الرسم العثماني` is the established Arabic term
for it. The demo's §5 explains exactly this attribute.

So **`رسم` must never be used to translate "ink", "drawing", "artwork" or "rendering."** A reader who
knows the domain will parse it as the spelling skeleton and the sentence will invert its meaning.

- "ink" → **الحبر**
- "what is drawn" → **ما هو مرسوم** / **المرسوم على الصفحة**
- "artwork" → **العمل الفني** or **الرسوم المتجهة**

### `علامة` vs `حركة`

The project's `mark` is a superset: it includes waqf signs, sajdah signs and iqlab meems, none of
which are vowels. `حركة` means a vowel specifically.

- "436,627 named marks" → **علامة**, never **حركة**.
- "Hide the vowel marks" → **إخفاء الحركات** — here `حركة` is correct, because that button really
  does hide the vowels.

Read each English "mark" and decide which one it is. The English word is ambiguous; the Arabic is not,
and that is an improvement worth preserving.

### `ligature` — unresolved, needs Abdullah

In this project a `<g class="ligature">` is **a connected run of letters within a word, as the Arabic
joining rules allow** — one group per piece the word breaks into. That is *not* the typographic
"ligature" (a single glyph standing for two letters, like lām-alif), which is what `الحرف المركب`
would be read as.

Candidates, none adopted:

| candidate | reading | problem |
|---|---|---|
| `الحرف المركب` | typographic ligature | wrong concept — implies a fused glyph |
| `قطعة` | piece | vague, but honest |
| `وصلة` | connection/join | closer to the joining-rule meaning |
| `مقطع خطّي` | calligraphic segment | descriptive, coined |

**Recommendation:** keep the English/attribute name and gloss it —
`مجموعة الوصل (ligature)` on first use, `الوصلة` after. But this is a real terminological decision
about the project's own model and Abdullah should make it, not the translator. **Flagged, not
decided.**

### "word" is a keyed unit, not a written word

The demo already warns that 367 `data-search` values contain a space, and that word `37:130:3` has a
space in its own text. So `كلمة` in the Arabic page means "the unit keyed by `data-wid`", which
occasionally is not one written word.

Where the English relies on this precision, the Arabic must too — `الكلمة` alone is not enough in
those sentences. Use `وحدة الكلمة` or name the key: `الوحدة التي يعرّفها data-wid`.

---

## 5. Never translated

Reproduce byte-for-byte. These are what a reader searches for and what the product actually prints.

- Every attribute name: `data-wid`, `data-aid`, `data-search`, `data-rasm`, `data-imlaei`,
  `data-uthmani`, `data-qpc`, `data-kind`, `data-line`, `data-part`, `data-marker`, `viewBox`.
- The nine root attributes: `data-mushaf`, `data-qiraa`, `data-riwaya`, `data-edition`,
  `data-mushaf-name-ar`, `data-mushaf-name-en`, `data-ayah-numbering`, `data-ayah-total`,
  `data-page` — **and their values**: `asim`, `hafs`, `kufi`, `madani-first`. The Arabic prose names
  the concept (§1a); the attribute keeps the Latin key.
- Every attribute *value* and key: `2:255`, `2:255:4`, `#231f20`.
- Every class name: `g.word`, `g.ayah`, `g.ligature`, `.q-hits`.
- All code: `querySelectorAll`, `getBBox`, `getBoundingClientRect`, `DOMParser`, `fetch`,
  `AbortSignal`, `H.band`, `H.crop`.
- Format and standard names: `SVG`, `CSS`, `HTML`, `JSON`, `DOM`, `API`, `UTF-8`, `KiB`, `MiB`.
- File names, paths, URLs — including `dm.qurancomplex.gov.sa`.
- Key names: `Ctrl`, `⌘`, `Enter`.
- Proper nouns as their owners write them. **King Fahd Glorious Qur'an Printing Complex** has an
  official Arabic name and the demo already carries it —
  `مجمع الملك فهد لطباعة المصحف الشريف`. Use that exact string; do not re-translate from the English.
- `MushafDatabase`, `DigitalKhatt`, `quran.com`, `KFGQPC` — project and product names.

---

## 6. Digits

**Western digits (`0–9`) throughout the prose.** Counts, page numbers, byte sizes, tolerances,
percentages, ayah keys, versions: `604` pages, `77,432` words, `2.0 MiB`, tolerance `24/255`, `2:255`.

Reasons, all of them binding here: the keys must match `data-wid` and `data-aid` exactly or they stop
being copy-pasteable; the numbers appear beside Latin identifiers; and they must match what the code
in the lab snippets prints.

**The one exception — and it is content, not a number the document is asserting:** the **artwork's own
ayah numerals are Arabic-Indic**, because that is what the print draws. Never restyle, replace or
"normalise" them. If the Arabic prose describes them, describe them as
`الأرقام العربية الهندية` and reproduce any example from the cached sources rather than typing it.

Do not mix the two systems anywhere else.

---

## 7. Punctuation

`،` (U+060C) · `؛` (U+061B) · `؟` (U+061F) in Arabic prose. The full stop is the ordinary `.`.

**Punctuation inside code stays as the code has it.** A `;` in a JavaScript snippet, a `,` in JSON, a
`:` in `2:255` — none of these become Arabic marks. The lab snippets are executable; converting a
character inside one breaks it.

Every inline `code` span in Arabic prose needs bidi isolation so its neighbouring punctuation does not
jump sides — the CSS for that is in `docs/arabic-rtl-plan.md` §5 and §9.

---

## 8. UI strings

Buttons, labels and tooltips take the **verbal noun (المصدر)**. A **step list** takes a lead-in plus
maṣdar (`يمكنك اتّباع الخطوات التالية:`), not a run of imperatives. A **flowing prose instruction**
may use the imperative. The rule and its sources are in the `arabic-writer` skill
(`technical-writing.md` §6).

The demo has several numbered procedures, so the step-list row is the one that will come up — do not
render those as strings of imperatives.

| English | Arabic | form |
|---|---|---|
| Highlight the first ayah | **تظليل الآية الأولى** | button → مصدر |
| Hide the vowel marks | **إخفاء الحركات** | button → مصدر |
| Show me the code | **عرض الشيفرة** | button → مصدر |
| What you get | **ما تحصل عليه** | link |
| Attribute reference | **مرجع السمات** | link |
| Reset | **إعادة تعيين** | button → مصدر |
| Copy | **نسخ** | button → مصدر |
| Search | **بحث** | button → مصدر |
| Run | **تشغيل** | button → مصدر |
| theme | **السمة** | Note the collision with `سمة` = attribute. Use **المظهر** for the colour theme instead. |
| Change the page number and run it again | **غيّر رقم الصفحة وشغّله مرة أخرى** | prose → أمر |
| Parse it and it answers questions | **حلّله فيجيب عن الأسئلة** | prose |
| Do not sort by geometry | **لا تُرتّب حسب الهندسة** | prose |

Note `أجاب عن` in that last block, not `أجاب على` — the guide's table §أ.

---

## 9. Open decisions for Abdullah

1. **`ligature`** — §4. The only genuinely undecided term, and it recurs throughout the demo.
2. **`theme`** — `السمة` collides with `سمة` (attribute), which the page uses constantly. Proposed
   `المظهر`. Confirm.
3. **Licence wording** — the demo carries a licence placeholder. Leave it a marked placeholder in
   Arabic too; do not state terms.
4. **Whether the Arabic page is a translation or an edition.** If it is a translation it tracks the
   English exactly and drifts whenever the English changes. If it is an Arabic edition it can drop
   English-reader framing that an Arabic reader does not need. This changes the amount of ongoing
   work and should be decided before the translation starts, not after.
5. **`plain JS` / `library` toggle labels** — §3 proposes `بدون مكتبة` / `بمكتبة` to avoid
   transliterating "JS". Confirm, or supply preferred wording.
6. **If the English says "the Hafs qiraa" anywhere, that is an error worth fixing in the English
   too** — Hafs is a riwaya. See §1a. The Arabic cannot reproduce the mistake, so the two pages
   would silently disagree unless the English is corrected.

---

## 10. Keeping this current

The English demo is still growing. **This file is the long pole for the translation**, so extend it
as sections land rather than at translation time — consistency across a long technical page comes
from the glossary, not from care while translating.

When a new section appears, add its recurring nouns here **before** translating it, and decide for
each: translated, kept Latin, or glossed once and then Arabic. Record the reason, as the rows above
do. A term decided twice is a term that will appear two ways on the page.

The language authority for everything except this vocabulary is the global `arabic-writer` skill
(`~/.claude/skills/arabic-writer/`), whose `SOURCES.md` carries the citations and a list of
plausible-sounding rules that failed verification.
