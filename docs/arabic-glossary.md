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

Buttons and labels take the **verbal noun (المصدر)**; prose instructions take the **imperative**. The
rule and its rationale are in the `arabic-writer` skill (`technical-writing.md` §6).

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
