# RTL conversion plan for the demo page

**Status: plan only. Nothing has been changed.** `docs/demo/template.html` is being rewritten by
another agent as this is written, so this document is keyed to **CSS selectors and mechanisms**, not
to line numbers — the line numbers moved twice while it was being researched and will move again.

Scope: `docs/demo/template.html` (the source of truth; `build.py` produces `index.html` from it).

---

## 1. The one-line summary

`dir="rtl"` on `<html>` flips the block layout for free. It fixes **none** of the four things that
actually matter here: physical CSS properties, code that must stay LTR, inline Latin identifiers
inside Arabic prose, and the pixel-arithmetic in the selection layer. Those are the work.

---

## 2. What `dir="rtl"` does, and what it does not

**Does, automatically:**
- Sets the base paragraph direction. Arabic runs right-to-left.
- Right-aligns text where `text-align` is unset.
- Reverses the visual order of flex and grid items, and of inline-block sequences.
- Reverses list marker side and default block indentation.
- Mirrors paired brackets and bidi-mirrored glyphs at render time. This is the Unicode Bidirectional
  Algorithm and it needs no help.
- Flips the resolution of **logical** CSS properties (`margin-inline-*`, `inset-inline-*`,
  `text-align: start/end`).

**Does not:**
- Touch any **physical** property. `margin-left` is still the left margin. Every physical property in
  the stylesheet is now a latent bug. Section 3 lists them.
- Change the direction of an inline run of Latin text, or fix where the *neutral* characters around
  it land. Section 5.
- Reverse an SVG coordinate system, and must not. Section 6.
- Alter anything computed in viewport pixels by JavaScript. Section 7.
- Change fonts, line-height or letter-spacing. Section 8.

---

## 3. Physical → logical, by selector

Straight conversions. Each is safe and each is required.

| selector | now | becomes |
|---|---|---|
| `.index .toclink` | `margin-left:auto` | `margin-inline-start:auto` |
| `.lab-bar .hint` | `margin-left:auto` | `margin-inline-start:auto` |
| `.toc .n` | `margin-right:7px` | `margin-inline-end:7px` |
| `ul.plain-list` | `padding-left:20px` | `padding-inline-start:20px` |
| `th, td` | `text-align:left` | `text-align:start` |
| `.lab-extra .val` | `text-align:right` | `text-align:end` |
| `.lab-out` | `border-left:3px solid` | `border-inline-start:3px solid` |
| `.lab-out.err`, `.lab-out.ok` | `border-left-color` | `border-inline-start-color` |
| `.q-dead` | `border-left:3px solid` | `border-inline-start:3px solid` |
| `.callout` | `border-left:3px solid var(--gold)` | `border-inline-start:3px solid var(--gold)` |
| `.callout.placeholder` | `border-left-color` | `border-inline-start-color` |
| `.lab-badge` | `right:12px` | `inset-inline-end:12px` |
| `.index a` (if the `border-right` divider survives the rewrite) | `border-right` | `border-inline-end` |

**Sweep rule for whatever the rewrite adds:** after it settles, re-run

```sh
grep -nE '(margin|padding|border)-(left|right)|(^|[;{ ])(left|right):|text-align:[ ]*(left|right)|float:' template.html
```

and triage every hit against sections 3, 4 and 7. Do not assume the list above is complete after the
file changes.

---

## 4. What stays physical on purpose

Converting these is a regression, not a cleanup. **Do not let a blanket physical→logical sweep touch
them.**

| selector / code | keep as | why |
|---|---|---|
| `.q-hits span { transform-origin: left top }` | `left top` | Paired with `s.style.left`, computed from `getBoundingClientRect()`. Both are **viewport-physical** and direction-agnostic. See §7. |
| `figure.code .copy { top:10px; right:10px }` | `right` | The copy button decorates a code block that stays LTR. Its correct home is the block's top-right corner in both directions. |
| `.lab-badge` — *if* it labels the LTR editor | reconsider | Listed in §3 as logical, but if it sits over the `textarea` it should follow the code, not the page. Decide once the rewrite settles; the two are mutually exclusive. |
| `.offstage { left:-99999px }` | `left` | Off-screen hiding. Physical is correct and safe in both directions. |
| `scaleX(...)` in `hitLayer()` | untouched | A **fitting** transform that squeezes a span onto its word's measured width. It is not a mirror and has nothing to do with direction. |

---

## 5. What must stay LTR

A `dir="rtl"` code block is unreadable and reads as a broken page. Pin these to `dir="ltr"` and
`text-align: left` explicitly — do not rely on inheritance.

**Block-level, always LTR:**

| selector | what it holds |
|---|---|
| `.lab-editor textarea` | the editable lab snippets — JavaScript source |
| `figure.code pre`, `figure.code code` | static code blocks |
| `.lab-out` | JS console/result output |
| `.out` | readout panels printing computed values |
| `.readout dd` | attribute values, keys, byte counts |

Note `.lab-out` and `.q-dead` appear in **both** §3 and here: their **border** becomes logical (it is
page chrome) while their **content** stays LTR. Those are different properties and do not conflict.

**Inline, always LTR — wrap or mark individually:**

| selector | what it holds |
|---|---|
| `code` (inline, in prose) | `viewBox`, `data-wid`, `querySelectorAll`, `2:255` |
| `.shead .sel` | CSS/JS selector strings |
| `.mono`, `td.mono`, `th.mono` | identifiers and keys |
| `kbd` | `Ctrl`, `⌘`, `Enter` — never translated |
| `.chip` | `604`, `77,432` and their labels |
| `.spec-lbl span` | profile names |
| `.q-tip i`, `.q-tip u` | word key and attribute readouts |

A CSS block that covers most of it:

```css
/* code is code in every direction */
code, kbd, samp, pre, textarea,
.mono, .shead .sel, .lab-out, .out, .readout dd, .q-tip i, .q-tip u {
  direction: ltr;
  unicode-bidi: isolate;   /* do not let it reorder the Arabic around it */
  text-align: left;
}
```

`unicode-bidi: isolate` is what stops a code span from dragging the neutral characters beside it —
the trailing full stop after `<code>data-wid</code>` in an Arabic sentence lands on the wrong side
without it.

**Not LTR:** `input#s-all` is an Arabic search box. It should be `dir="auto"` so it follows whatever
the user types, not forced either way.

---

## 6. The artwork — nothing changes, and one hard prohibition

The page SVG is already RTL *content*. Its `viewBox`, its coordinate system, its transforms and its
path data are the print's own geometry and are covered by the pixel-identity guarantee.

**Prohibited, in the demo CSS and anywhere else:**

```css
/* every one of these is a correctness failure, not a layout choice */
.paper svg          { transform: scaleX(-1) }
.paper svg          { transform: scale(-1, 1) }
.paper svg          { transform: rotateY(180deg) }
[dir="rtl"] .paper  { transform: … }   /* any mirroring */
```

Mirroring the artwork would render the mushaf backwards and break the raster-diff gate
(`tools/audit_pixels.py`) on every page. The current template is **clean** — a grep for `scaleX`,
`scale(-1`, `rotateY` and `transform: … -1` finds only the legitimate `scaleX()` width-fit in
`hitLayer()`, which is a fitting transform on an HTML span, not on the artwork.

**Add a guard** so this cannot regress silently: a grep in the demo's build or CI step that fails if
a mirroring transform ever appears on `.paper`, `svg`, or any `g.word` / `g.ayah` selector.

Also unchanged: `data-line`, `data-wid`, `data-aid`, every attribute name and every attribute value.
Direction is a presentation concern; the schema is not.

---

## 7. JavaScript that measures pixels — safe, and why

The selection layer (§7 of the demo) and the tooltip both position absolutely-positioned elements
from `getBoundingClientRect()`:

```js
s.style.left = (b.x0 - origin.left) + 'px';
s.style.top  = (b.y0 - origin.top)  + 'px';
…
const natural = s.getBoundingClientRect().width;
if (natural > 0) s.style.transform = 'scaleX(' + (+s.dataset.w / natural) + ')';
```

`getBoundingClientRect().left` is the **physical** left edge in viewport coordinates and does not
change under `dir="rtl"`. The arithmetic is direction-agnostic and needs no change. Same for
`.q-tip` positioning.

**Three conditions this depends on. Keep all three:**

1. The spans get **no width** (deliberate — the code comment explains why: a fallback font's advances
   overflow the word and steal neighbouring hits). Shrink-to-fit means the base direction of the
   parent cannot shift the box.
2. `s.style.left` and `transform-origin: left top` stay **physical**. Converting either to
   `inset-inline-start` / `logical` origin while the other stays physical mis-registers every span on
   the page.
3. Words are appended in **document order**, which is reading order. The existing comment already
   warns against sorting by x. RTL does not change this and must not tempt anyone to "fix" it.

**Verify after the change** rather than assuming: the demo already reports worst residual span
misalignment (0.016 px across page 3). Re-measure it under `dir="rtl"` and require the same figure.
That is the acceptance test for this section.

One genuine risk to re-check by eye: the `.index ol` horizontal scroller. Under RTL, `scrollLeft`
origin conventions differ across engines. The current template uses no `scrollLeft`, so there is
nothing to fix today — but if the rewrite adds scroll-position logic to the sticky index, it needs
testing in both directions.

---

## 8. Type

**Font stack.** No new external dependency: the page already loads Google Fonts, and
`Noto Sans Arabic` and `IBM Plex Sans Arabic` are both served from the same `fonts.googleapis.com`
stylesheet the page already requests. `IBM Plex Sans Arabic` is the better pick — the page already
uses `IBM Plex Mono`, so the technical voice stays coherent.

Add to the existing `css2?family=…` request (one stylesheet, no second host):

```
&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700
```

```css
body[dir="rtl"] {
  font-family: "IBM Plex Sans Arabic", "Noto Sans Arabic", "Segoe UI", Tahoma, sans-serif;
  line-height: 1.85;          /* Latin sits at 1.6 */
}
[dir="rtl"] h1, [dir="rtl"] h2, [dir="rtl"] h3 {
  font-family: "IBM Plex Sans Arabic", "Noto Sans Arabic", serif;
  line-height: 1.35;
}
```

`Spectral` has no Arabic coverage, so headings need the substitution above or they fall back
silently and inconsistently.

**Leave `.ar` and `.quote` alone.** They set `font-family:"Amiri"` with `direction:rtl` for Quranic
and classical text. Amiri is a Naskh face and is the right choice there; the UI face is wrong for
scripture. Their `direction:rtl` becomes redundant under a global RTL document but is harmless and
keeps those spans correct if reused in an LTR context.

**Three rules the design must respect:**

- **`letter-spacing: 0` on all Arabic.** Arabic letters join; spacing them breaks the joins and
  renders words wrong. The page currently sets `letter-spacing` on `.eyebrow`, `.sec-eyebrow`,
  `.index a`, `.panel h3`, `.callout h3`, `th` and `.spec-lbl`. **Every one of those must be zeroed
  for Arabic** — this is the single most common way an Arabic page is visibly botched.
- **`text-transform: uppercase` does nothing in Arabic.** The same selectors use it for hierarchy.
  Arabic has no letter case, so that signal vanishes entirely and those labels flatten into the body
  text. Replace with weight, size or colour before translating, or the visual hierarchy collapses.
- **No italic on Arabic.** `.mast h1 em`, `.quote-en` and `.q-tip`-adjacent italics need a different
  emphasis mechanism. Faux-oblique Arabic is a rendering artefact.

**Expansion.** Arabic runs longer than English. `.mast h1 { max-width:20ch }`, `.plain
{ max-width:64ch }`, `.callout p { max-width:72ch }` and the `min-width` on buttons and `.lbl` are all
sized to English. Re-check them against real Arabic, not by converting the numbers.

---

## 9. Bidi in the prose itself

The failure this page will hit constantly: an Arabic sentence containing a Latin identifier, where
the punctuation between them lands on the wrong side.

- Every inline `code` span gets `unicode-bidi: isolate` (already in §5's CSS block). That covers the
  authored cases.
- Every **interpolated** value — anything JavaScript writes into prose, such as a word's text, a
  `data-wid`, a search hit, a file name in an error message — goes in `<bdi>`, or a container with
  `dir="auto"`. This is what `<bdi>` exists for and it is the difference between a page that holds
  together and one that scrambles for certain inputs.
- Where markup is not available — an `aria-label`, a `title`, a `placeholder`, an alt text — use
  Unicode isolates `U+2066`–`U+2069` rather than the older embedding characters, per W3C guidance.
- Numbers in Arabic prose use Western digits (see the glossary), and digits inside a number always
  run LTR by the algorithm. That is already correct and needs no markup.

---

## 10. Order of work, once the English settles

1. Add `IBM Plex Sans Arabic` to the existing font request.
2. Land the §5 LTR block **first**, before `dir="rtl"` goes on. It is direction-neutral and it means
   the code never scrambles at any point during the conversion.
3. Zero `letter-spacing` and replace `text-transform: uppercase` hierarchy for Arabic.
4. Do the §3 physical→logical conversions.
5. Only then set `dir="rtl"` and `lang="ar"` on `<html>`.
6. Run the §6 mirroring grep guard.
7. Re-measure the §7 span alignment figure and require parity.
8. Check every lab snippet still runs and still reads left-to-right.
9. Then translate, using the `arabic-writer` skill and the glossary in
   `docs/arabic-glossary.md`.

Steps 1–8 are mechanical and can be verified without a single word of Arabic being final. Step 9 is
the only one that has to wait.
