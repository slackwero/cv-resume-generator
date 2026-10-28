---
name: CV Generator
description: Black glass and a single signal amber; state is drawn by the stroke pattern, never by color.
colors:
  glass: "#0a0a0a"
  glass-etched: "#121110"
  glass-sunken: "#060606"
  amber: "#ffb000"
  amber-faint: "#7a5200"
  amber-inactive: "#3a2600"
  rule: "rgba(255, 176, 0, 0.26)"
  rule-strong: "rgba(255, 176, 0, 0.55)"
  text: "#f2e4ce"
  text-faint: "#b59b72"
  text-muted: "#9a845e"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 6vw, 4.75rem)"
    fontWeight: 800
    lineHeight: 0.92
    letterSpacing: "-0.02em"
  figure:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.01em"
    fontFeature: "'tnum' 1"
  legend:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.14em"
  prose:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  note:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  square: "0"
  focus: "1px"
spacing:
  channel: "clamp(12px, 3vw, 28px)"
  module: "28px"
  row: "1rem 1.125rem"
  compact: "0.25rem 0.5rem"
  section: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.glass}"
    typography: "{typography.legend}"
    rounded: "{rounded.square}"
    padding: "0 1rem"
    height: "2.75rem"
  button-primary-hover:
    backgroundColor: "#ffc233"
    textColor: "{colors.glass}"
  button-primary-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.amber}"
    typography: "{typography.legend}"
    rounded: "{rounded.square}"
    padding: "0 1rem"
    height: "2.75rem"
  button-secondary-hover:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.glass}"
  field:
    backgroundColor: "{colors.glass-sunken}"
    textColor: "{colors.text}"
    rounded: "{rounded.square}"
    padding: "0.625rem 0.75rem"
    height: "2.75rem"
    width: "100%"
  panel:
    backgroundColor: "{colors.glass-etched}"
    textColor: "{colors.text}"
    rounded: "{rounded.square}"
    padding: "{spacing.row}"
  status-mark:
    backgroundColor: "transparent"
    textColor: "{colors.text-faint}"
    typography: "{typography.legend}"
    rounded: "{rounded.square}"
    padding: "{spacing.compact}"
  status-mark-on:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.glass}"
  nav-target:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    typography: "{typography.legend}"
    padding: "0 0.75rem"
    height: "44px"
  nav-target-active:
    backgroundColor: "transparent"
    textColor: "{colors.amber}"
  dialog:
    backgroundColor: "{colors.glass-etched}"
    textColor: "{colors.text}"
    rounded: "{rounded.square}"
    padding: "1.5rem"
    width: "36rem"
  free-rail:
    backgroundColor: "transparent"
    textColor: "{colors.amber-inactive}"
    typography: "{typography.figure}"
    rounded: "{rounded.square}"
    padding: "0.625rem 1.125rem"
  exception-indent:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.square}"
    padding: "0 0 0 0.75rem"
  annotation-field:
    backgroundColor: "{colors.glass-sunken}"
    textColor: "{colors.text}"
    rounded: "{rounded.square}"
    padding: "0.625rem 0.75rem"
    height: "2.25rem"
    width: "100%"
---

# Design System: CV Generator

## Overview

**Creative North Star: "The normalled jackfield"**

In a studio patch bay, every signal arrives tied to its default destination by a jumper:
that is the *normal*. An operator can break it by hand, and then it stays broken until
someone deliberately restores it. This interface draws exactly that. The material is
black glass (`#0a0a0a`) backlit by a single signal amber (`#ffb000`), crossed by a 28px
silkscreen pattern that gives scale to the void. There are no cards, no shadows and no
soft corners: there are one-pixel rules, numbered rails and condensed uppercase labels. A
technical scheme, not a decorated control panel.

Density is high and deliberate. Each row carries its full furniture —who, with which
template, in which language, on which date, in which file— because the artifact this
tool produces is judged months later. Nothing is shown bare, and nothing takes the full
width: the edge channels are never filled, and that breathing room is what keeps the
density from reading as noise. The container is capped at 1180px and the side channel is
`clamp(12px, 3vw, 28px)` — its ceiling is exactly one cell of the background pattern.

What this world rejects is confirmed by the code it replaced: the card grid where
everything weighs the same and state is a colored badge. The previous version told a new
change from a conflict only by the badge's tone —amber, blue, green— and anyone who
cannot separate those colors read a flat list. That system was removed entirely. Here
state is drawn by the stroke pattern, and it always comes with its word.

**Key Characteristics:**

- A single accent: `#ffb000` on `#0a0a0a`. Zero semantic colors.
- State by stroke pattern, hierarchy by scale and inversion.
- Zero radius across the interface; zero shadows across the system.
- A single variable typeface (Archivo), self-hosted, with the `wdth` axis instead of a second family.
- A single dark mode, pinned by three independent pieces.
- A single moment of motion in the whole application: the rails are laid out on load.
- The scheme is drawn to the bottom: after the real rows come the labeled free rails and
  their ellipsis, both `aria-hidden`.

## Colors

A black with three depths and a single amber with five densities. There is no second
accent tone anywhere in the system, and the secondary prose is not neutral gray either:
it is tinted with the amber that governs the surface.

### Primary

- **Signal amber** (`#ffb000`): the single accent. Headlines, rail figures, every rail
  stroke, the focus ring, text selection, the browser's `accent-color` and caret, the
  active navigation underline, the left border rule of a notice, the icon of any message
  and the primary plate.
- **Faint amber** (`#7a5200`): the scrollbar thumb on hover.
- **Inactive amber** (`#3a2600`): what exists but cannot be used — the border of a
  disabled control, the rail of an unreachable step, the scrollbar thumb at rest.

### Neutral

- **Glass** (`#0a0a0a`): the canvas. Painted by `html`, never by `body` (see *The Body
  Without A Floor Rule*). It is also the background of the top bar and the scheme frame,
  and the color of inverted text on an amber plate.
- **Etched glass** (`#121110`): the tonally raised surface — panels, active history rows,
  the active wizard step, the chosen template card, a dialog body, the file drop zone.
- **Sunken glass** (`#060606`): what is lowered — the inside of an input field and the
  scrollbar channel.
- **Rule** (`rgba(255, 176, 0, 0.26)`): the one-pixel border that defines every surface.
  It is the structural substitute for shadow across the system.
- **Strong rule** (`rgba(255, 176, 0, 0.55)`): the border of an element that calls for
  interaction — secondary button, status cell, drop zone, template thumbnail frame.
- **Text** (`#f2e4ce`): main prose. A warm white with the amber inside it.
- **Faint text** (`#b59b72`): secondary prose, labels of an active row, supporting figures.
- **Muted text** (`#9a845e`): scheme labels at rest, help text, field placeholders, and
  all content of an archived row.

### Named Rules

**The One Amber Rule.** The whole system is painted with `#ffb000` and its densities.
There is no error red, success green or information blue, and adding one breaks the
system. A severe error stands out by the **thickness** of its left rule (2px against 1px)
and by its glyph, never by its tone. Test: if a state needs a second color to be read,
the pattern is badly drawn and the pattern is what gets fixed.

**The Tinted Prose Rule.** Secondary prose is never neutral gray. The three text levels
are desaturated ambers (`#f2e4ce` → `#b59b72` → `#9a845e`). A neutral gray on a colored
background is the shortcut that gives away that nobody chose that tone.

**The Foreign Image Rule.** An image that is not ours keeps its own color inside an amber
rule, instead of being tinted to fit in. A PDF template thumbnail is white paper on
`rule-strong`, and it stays white.

## Typography

**Single family:** Archivo variable (with `system-ui, sans-serif` as fallback).
Self-hosted under SIL OFL 1.1 in `assets/fonts/`, in three `woff2` subsets (latin,
latin-ext, vietnamese) with the same `unicode-range` Google Fonts serves. It is
deliberate: the application runs locally and must not ask a CDN for a font to draw
itself.

**Character:** a single grotesque with two axes, `wdth 62–125` and `wght 100–900`. The
width axis does the job usually given to a second family: the same file sets a rail's
condensed label at 62% and an achievement's prose at 100%. The page sets
`font-synthesis-weight: none` so no weight is faked.

### Hierarchy

- **Display** (`wdth 62`, weight 800, `clamp(2.5rem, 6vw, 4.75rem)`, line height 0.92,
  tracking −0.02em, uppercase, amber, `text-wrap: balance`): the headline voice. One `h1`
  per route, always in the same corner; the frame serves it reduced to
  `clamp(2rem, 5vw, 3.25rem)`. The system's tracking floor is −0.04em; −0.02em keeps the
  headline dense without closing it up.
- **Figure** (`wdth 62`, weight 700, 1.5rem by default, tabular, line height 1): every
  number compared vertically — the rail number, the sync counts, the coverage percentage
  (at 2.75rem). The global stylesheet also forces `tabular-nums` on `table` and `time`.
- **Legend** (`wdth 75`, weight 600, 0.6875rem, tracking 0.14em, uppercase): the scheme
  label. Column headers, field labels, button text, status cells, navigation.
- **Prose** (`wdth 100`, 0.9375rem, line height 1.55): running text. The measure is
  limited where it is used (`52ch` in an empty state, `56ch` in a page's help, `64ch` in a
  group's help), never in the function.
- **Note** (`wdth 100`, weight 400, 0.75rem, line height 1.5, lowercase): the short
  secondary sentence.

### Named Rules

**The Label-Is-Not-A-Sentence Rule.** `legend()` is for **short labels**; `note_text()` is
for **sentences**. Uppercase is read by the shape of the word, and in capitals every word
has the same shape: a rectangle. Beyond about 25 characters that stops being a label and
starts being a sentence that is hard to read. Test: if the text has a conjugated verb, it
is not a legend.

**The One Family Rule.** No second family is loaded. If a register needs to stand out, it
moves along the `wdth` axis (62 / 75 / 85 / 100) before changing family.

## Layout

**The frame.** A centered 1180px container, with a side channel `clamp(12px, 3vw, 28px)`
and `2.5rem` of air on top, `5rem` at the bottom. The top bar is `sticky` at `top: 0` with
`z-index: 10` and a bottom rule; it is identical on the four routes. Under it, each page
opens with its title and actions block, separated from the body by a rule and a `2rem`
margin.

**Strip and grid.** The composition has two columns: a fixed legend strip on the left
(`16rem`, `sticky` at `top: 5.5rem`, with a right rule) and the body drifting to its right
with a `2.5rem` gap. The strip is not decoration: it carries the state the route needs to
keep in view at all times — the profile status on the home page, the map of the six steps
in the wizard, the pattern legend on `/profile` and `/sync`.

**Responsive.** Below 62em (992px) the strip **does not hide**: it goes full width and sits
above the body, because what it carries is state. It loses its right rule and its
`sticky`. The scheme header disappears below that width (stacked, it means nothing), a
row's status cell jumps to `1 / -1`, and the row action labels are hidden, leaving only
the icon.

The width helpers live in `styles.py` and return `rx.breakpoints`, not lists:
`responsive_columns()` (1 column up to md, 2 from md), `header_direction()`,
`header_alignment()` and `row_action_size()`. The effective breakpoints are Reflex's: xs
30em, sm 48em, md 62em, lg 80em, xl 96em.

**Touch target.** `touch_target()` sets a 44px minimum height up to 48em and `auto` from
there. It applies to buttons, navigation links, labeled checkboxes and, by default, to
every input field through `field_style()`.

**The scheme reaches the bottom.** A short list left half the viewport black and unframed,
and the only row read as a loose card —the scaffolding this world rejects—, so the scheme
is completed with two pieces of scale and none of data: the **free rails**
(`HomeState.free_rails`) label the next unused numbers until there are nine rows
(`_MIN_RAILS`) and at most six of them (`_MAX_FREE`), each one as a figure in
`amber-inactive` followed by a rule at 50% opacity; and under them an **ellipsis** (`…`,
figure at 1.25rem) says the numbering continues beyond what is drawn. Both are
`aria-hidden` and **disappear as soon as there is a search**: there the list is a result,
not a scheme.

### Named Rules

**The Untouched Channel Rule.** The edge channels are never filled. Nothing takes the full
width of the viewport. The background pattern exists to give that void scale.

**The Typed-Prop Breakpoint Rule.** Radix's typed props (`direction`, `columns`, `size`)
require `rx.breakpoints(...)`. A plain list only works for style props, and on the rest it
raises `TypeError` at compile time. This was learned by breaking the build; do not
simplify it to a list.

**The Fixed-Track Rule.** The scheme header and its rows are independent CSS grids, so
their tracks are declared **fixed** (`4rem minmax(0, 1fr) 7.5rem`) and never with loose
`auto` or `fr`: two different grids with `auto` tracks each size themselves by their own
content and never line up. Both read the same constant.

**The Labeled-Empty-Lane Rule.** A free rail can only be labeled when its number is a
**verifiable truth**: numbering goes by age over the full list, so the next CV will
literally take the first of those numbers. A gap labeled with a number the product would
never use would be a made-up row, and that is something else. Test: if the number of the
next empty row cannot be predicted, it is not drawn.

**The Elide-The-Empty Rule.** The ellipsis applies to the **free** rails and never to real
records. Eliding the user's CVs would hide their data behind three dots; eliding empty
numbering only says what is already true, that there is no cap. That is why the ellipsis
depends on there being free rails before it: without them there is nothing to elide.

## Elevation & Depth

**This system has no shadows.** There is not a single `box-shadow` or `text-shadow` in the
whole codebase. Depth is carried by two means and only two:

1. **Tonal layers of black.** `#060606` sunken (field interior, scroll channel) →
   `#0a0a0a` canvas → `#121110` etched (panel, active row, active step, dialog).
2. **The one-pixel rule.** An amber border at 26% defines every surface. At 55% it marks
   what calls for interaction. A 2px rule on the left marks what is severe.

Behind everything, a fixed pseudo-element (`body::before`, `inset: 0`, `z-index: -1`, no
pointer events) draws the silkscreen pattern: two 1px linear gradients in
`rgba(255, 176, 0, 0.055)` over a 28×28px grid. It is material, not decoration: it keeps
the black from reading as a flat void.

### Named Rules

**The Body Without A Floor Rule.** `body` **declares no `background`**, on purpose. The
canvas is painted by `html`. If `body` declares its own, that opaque background is painted
*on top of* its own `::before`: in the root stacking context, children with a negative
`z-index` are painted before the in-flow block's background. With `background` there, the
pattern was invisible at any alpha — it was not faint, it was covered. It was measured:
every pixel of the black field gave exactly `(10,10,10)`, with no periodicity. It took two
rounds; it is not "fixed" by adding a background to `body`.

**The Un-Multiplied Alpha Rule.** The pattern carries its alpha in the color (0.055) and
**no `opacity` on top**. The first version multiplied 0.20 by an opacity of 0.12 and left
the pattern at 2.4% effective: silkscreen was promised and there was nothing on screen. A
material you cannot see is not a material.

**The Flat-Forever Rule.** Adding a shadow to any surface breaks the system. What in
another world would ask for a shadow, here asks for a tonal step or a rule.

## Shapes

**Zero radius everywhere.** The Radix theme declares `radius="none"`, and every control
that needs it repeats it explicitly (`border_radius: "0"` on buttons, fields, checkboxes,
template cards, dialogs and the drop zone). The system's only exception is the focus
ring, which carries `border-radius: 1px` so the corner does not look broken.

**The border is the shape.** No surface fill defines a container: its 1px rule does. A
**provisional or empty** container uses the same rule `dashed` (the empty history state,
the file drop zone).

**Rail geometry.** The system's emblem is built from three flexible-width parts plus a
fixed-size terminal, so the ring never deforms when it stretches. The segments are a 1px
`border-top` on a zero-height box; the double segment is a 3px box with a border top and
bottom; the gap is a `flex: 0 0 0.875rem` of clean air. The glyphs are 14×14 SVGs with a
1.25 stroke in `currentColor`: an open ring of radius 4.25 as the terminal, and two slanted
strokes as the crosshair. The favicon is that same piece at 32px, with no letters.

### Named Rules

**The Never-Nested Panel Rule.** A `panel()` is etched glass with a rule, no shadow, no
soft radius and **never nested inside another panel**. It replaces the card.

## Components

### The link rail (signature component)

The system's central component, and its law. Six stroke patterns, **a single amber**. It
is `aria-hidden`: the meaning travels in the text label that goes with it, never only in
the drawing. The interface never shows a rail without its label next to it.

| Pattern | Drawing | What it means in the product | Where it is used |
|---|---|---|---|
| `joined` | segment → ring | "Same as on LinkedIn" / "Tied" | A field with a value on `/profile`; the home page sync line; a done or current wizard step; "All tied" and "Unchanged" on `/sync` |
| `broken` | segment → crosshair → segment → ring | "You edited it" — the normal broke and is respected broken | An empty required field on `/profile`; the "Untied" notice on the home page and in the wizard strip; an archived history row ("Off the list"); a step 4 achievement whose text differs from what LinkedIn brought; the reason "Next" is blocked |
| `gap` | segment → air → segment → ring | "Left out of this CV" | An empty optional field; an unreachable step; an unchosen template; an unchecked achievement; a posting term that does not appear yet |
| `folded` | double parallel line → ring | "In this CV" | The chosen template; a checked achievement; a posting term already covered |
| `proposed` | dashed segment → ring | "Changed on LinkedIn" | *modified* and *new* rows in the reconciliation |
| `conflict` | dashed segment → crossed ring | "Changed on both sides; you decide" | Conflicting rows and their preview list on `/sync` |

The gap is **clean air, not dotted**: a dotted line says "it continues", and the gap says
"it was cut here on purpose". The double segment has to read as two lines, which is why it
is two borders on a 3px box and not one thick border.

**Where it is NOT used, and why.** The history row (`history_table.py`) **draws no status
rail**, even though it is the house emblem. It was there, and it only repeated what the
status cell already said in words: active or archived. A drawing that duplicates the word
next to it is decoration. Tying it to something worth it —whether the frozen text still
matches today's profile— required data the history does not keep, and that data is not
made up. The history's only rail is in the exception indent of an archived row, and it
says something the cell does not say: **since when and why**.

**The broken rail at rest.** Apart from that archived row, a `broken` rail only appears
while you decide something —when syncing, when choosing achievements—. The exception row
is the only place in the product where "it stays broken" is seen **at rest**: an archived
CV is a normal that has been broken for months, and until now the row said neither when
nor why.

**Its legend is mandatory when the stroke is a taxonomy.** `/profile` and `/sync` print in
their strip the stroke next to what it means, each with the three patterns that screen
uses, because there the reader has to **decode** a whole list of different strokes. Where
a rail appears alone with its label stuck to it —the archived row, the edited achievement
in step 4, the reason for the blocked button, the wizard step map—, that label **is** the
legend and is not repeated in the strip. What is never allowed is the stroke without a
word.

*What `/sync` deliberately does not show:* the `broken` pattern. That case —you edited it
by hand and it did not change on LinkedIn— is precisely a NON-change, so it never becomes
a diff row. A legend only shows what its scheme draws.

### The exception indent (signature component)

One block, two appearances, and both say the same: *this left the default path, and here
is the record*. A 1px rule on the left, a `0.75rem` indent, and inside a short `broken`
rail followed by its legend label; below, the content of the exception. It has no
background of its own and no plate: it is a margin note on the record, not an alert.

- **In the history** (`_exception`): an archived row shows the `broken` rail, "Off the
  list" in amber and, if there is one, the date in `text-muted`. Under it, an optional
  field for the reason.
- **In step 4 of the wizard**: an achievement whose text differs from `imported_value`
  shows the `broken` rail with "You edited it · LinkedIn said" and, below, the original
  text in `text-muted` at 0.8125rem. **Only when they differ**: while they match, the
  normal is intact and repeating the same paragraph twice only takes space.

**The annotation field.** The archive reason is the only input in the system that governs
itself: no `value`, with `default_value` and writing to disk when it loses focus
(`on_blur`). It is a 2.25rem field at 0.8125rem —a note, not a form field— with
`max-width: 38rem`.

### The scheme and its free rails

The history scheme is a `ul` framed in a rule on glass, with its header of labels (only
from 62em: stacked, it means nothing) and one row per CV. Each row carries its `id`
(`#rail-01`) and `scroll-margin-top: 6rem`, so the visible number is an anchor that works.
After the real rows come the free rails and the ellipsis, described in *Layout*; both
`aria-hidden`, because there is nothing to announce to a screen reader: they are the
scheme's ruler, not records.

### Buttons

- **Shape:** square (`0`), minimum height 2.75rem, legend typography, a `120ms ease-out`
  transition on background and color.
- **Primary:** solid amber plate, glass text, weight 700, a border of the same amber.
  Hover `#ffc233`. Disabled: it loses the whole plate and becomes an `amber-inactive`
  outline with muted text and `cursor: not-allowed`.
- **Reason it is blocked:** a disabled primary **says what is missing**, stuck to it and
  not in the header. In the wizard, `WizardState.missing_to_advance` returns the sentence
  ("Missing the CV name and the role you are applying for") and it is printed as
  `note_text()` in amber with a short `broken` rail before it. `can_advance` decides
  whether the button switches off; `missing_to_advance` says why. An empty string when
  nothing is missing, and then nothing is drawn.
- **Secondary:** a `rule-strong` outline on transparent, amber text. **It inverts on
  hover** (amber background, glass text) — that is how this world marks what is active.
- **Row action:** the secondary compacted to 2.25rem high, a 0.625rem font and a 13px
  icon; its label is hidden below 62em.

### Chips / Status cells

- **Style:** legend typography, `rule-strong` outline, `0.25rem 0.5rem` padding, no line
  wrapping.
- **State:** **on = solid amber plate** with glass text; **off = outline** with faint
  text. The difference is inversion, not color: both use the same amber.

### Cards / Containers

There is no card. There is `panel()`: etched glass, a 1px rule, `1rem 1.125rem` padding,
zero radius, no shadow and never nested. The top bar's data group is a framed variant
whose cells are separated by inner vertical rules. A dialog (`rx.alert_dialog`) is etched
glass with a **solid 1px amber rule** and zero radius.

### Inputs / Fields

- **Style:** sunken glass, a 1px rule, square, 2.75rem high, 100% wide, placeholder in
  `text-muted`.
- **Focus:** the border turns solid amber and its own `outline` is suppressed; the global
  `:focus-visible` ring (2px amber, 2px offset) covers it on top.
- **Checkbox:** Radix's `rx.checkbox` is kept for its keyboard behavior and its link with
  the label; what changes is the skin — `color_scheme="amber"`, `high_contrast`,
  `size="2"`, zero radius and the indicator in glass.
- Every field carries a real `<label for>` and its own status rail next to the label.

### Navigation

A `sticky` bar with the mark on the left (**CV** at `wdth 62`, weight 800, 1.375rem,
amber, over "Generator" in a muted legend) and three destinations. Each destination is a
legend with a 15px icon and `stroke_width` 1.5.

- **Active:** a 2px amber underline (`border-bottom`) and amber text, plus
  `aria-current="page"`. **It is not inverted into a plate.**
- **Hover:** amber text; the underline of an inactive destination appears in `rule`.
- The root is not detected by comparing the route, it is **deduced**: it is the active one
  when no other one is.

**No counter chips in the navigation, on purpose.** A destination is an icon and a word,
and nothing else. The history count is only loaded by `HomeState` in the `on_load` of `/`;
the other three routes load `WizardState`, `ProfileState` and `SyncState`, so a chip hung
from the bar would show **0** on three of the four screens. A counter that lies is worse
than none. The figures live where they are true: the bar's framed **data group** is
composed by each route with the state that route loads —rails, archived and profile on
`/`; step, template and language on `/new`; status on `/profile`; phase on `/sync`—, and
that is why it never shows a dead number.

### Messages and notices

A rule, a 16px amber glyph and text. No background fill and no second tone. What is severe
stands out by the **thickness of the left rule** (2px against 1px) and by the glyph.

### Named Rules

**The Single Plate Rule.** A single solid amber plate per screen, and it is **the primary
action** — the action that screen exists to offer. In the wizard it is "Next" on steps 1–5
and "Generate the PDF" on step 6; on the home page, "Generate new CV" or, without a
profile, "Import from LinkedIn".

*The nuance the rule needs:* the row status cell (`status_mark`) **is** filled in solid
amber when it is on, and that is right — the source world fills its NORMAL chip that way
and outlines the OUT one. "A single plate per screen" governs the **primary action**, not
the status chips of a list. What the rule forbids is a **passive** element taking the
weight of an action: that is why the active navigation destination is underlined and the
current wizard step is marked with a left rule and an etched background. Both used to be
solid plates and both were removed, because what cannot be clicked weighed more than what
can.

**The Word-Beside-The-Stroke Rule.** No rail appears without its text label next to it.
The stroke is the signal, not the message.

## Do's and Don'ts

### Do:

- **Do** carry state with the **stroke pattern** and always back it with its word. It is
  what keeps the interface readable for someone who cannot separate red from green.
- **Do** carry hierarchy with **scale and inversion**: a single solid amber plate per
  screen, reserved for the primary action.
- **Do** leave `body` without a `background`. The canvas is painted by `html`; putting a
  background on `body` covers the silkscreen pattern (see *The Body Without A Floor
  Rule*).
- **Do** keep the **three** pieces that pin dark mode, because none is enough alone:
  `default_color_mode="dark"` in `rxconfig.py` (it only governs first-time visitors),
  `appearance="dark"` in the Radix theme (it fixes its palette), and the `<head>` script in
  `app.py` (it writes `localStorage` and the `dark` class on `<html>` before React
  hydrates). The third is mandatory: Reflex's own reset lives inside `if (isDevMode)` in
  `utils/react-theme.js` and **never runs in production**, so any browser that had already
  opened the app keeps its previous `"system"`, Radix paints itself with the `light` class
  and covers the black glass in white. `has_background=False` is the safety net: if the
  class resolved to light, the worst that happens is a Radix control with a light palette,
  not a white layer over all the glass.
- **Do** use `rx.breakpoints(...)` in any typed Radix prop (`direction`, `columns`,
  `size`). A plain list only works for style props.
- **Do** declare **fixed** grid tracks when two different grids have to line up column by
  column.
- **Do** set every figure compared vertically as tabular.
- **Do** apply `touch_target()` to any new control, fields included.
- **Do** say **what is missing** next to a disabled primary control, with its `broken`
  rail beside it. Switching the button off with no reason forces you to guess which field
  is in the way.
- **Do** label the free rails when the scheme comes up short, and only with numbers the
  product will really use.
- **Do** show the default value (`imported_value`) **only when it differs** from the
  current text. While they match, the normal is intact and repeating it twice takes space.

### Don't:

- **Don't** introduce a second accent color, an error red or a success green. If a state
  cannot be told apart, fix the **pattern**, not the palette.
- **Don't** add shadows. There are none in the system; depth is made with the three blacks
  and the rule.
- **Don't** round anything. The system's radius is `0`; the only exception is the focus
  ring's `1px`.
- **Don't** invert a **passive** element into a solid plate — an active navigation
  destination, a step marker. The plate belongs to the action, not to "where am I".
- **Don't** nest a `panel()` inside another, nor replace it with a card with a shadow.
- **Don't** draw a rail that only repeats the word next to it. If the stroke does not say
  something words do not say better, the stroke is redundant.
- **Don't** draw a rail without its label. And if a screen forces you to **decode several
  patterns at once**, it does not ship without its legend in the strip; a single rail with
  its label stuck to it already brings its own.
- **Don't** hang a counter chip from the navigation. Only `/` loads the count, so it would
  show 0 on the other three routes: a counter that lies is worse than none. The figure goes
  in the data group of the route that does have it loaded.
- **Don't** elide real records. The ellipsis (`…`) is for the **free** rails; applied to
  the user's CVs it would hide their data behind three dots.
- **Don't** take the "what LinkedIn says" column to `/` or to `/profile`. That data does
  not exist there: `imported_value` lives in `Achievement` and `ProfileText`, not in
  `PersonalInfo`, and drawing the column over the contact fields would promise a provenance
  nobody keeps. Today the build draws it **only in step 4** (achievements); step 3 has the
  field in the model but does not lay it out, so there it is a possible extension, not an
  absence by law.
- **Don't** use `legend()` for a sentence. Beyond ~25 characters in uppercase it stops
  being readable; that is what `note_text()` is for.
- **Don't** animate a rail closing. A broken normal does not repair itself, so a gap or a
  crosshair is never drawn closing.
- **Don't** animate the text or delay the terminal. The rail starts from an already visible
  state (`scaleX(0.35)`, opacity 0.45) and the ring lights up **at the same time** the line
  is laid: the version with `scaleX(0)` and a 680ms delay left a ninth of the status
  indicators blank for seven tenths of a second on every navigation, covering exactly the
  state it exists to show.
- **Don't** tint a foreign image to make it fit. A thumbnail's paper is white and stays
  white, inside its amber rule.
- **Don't** leave a surface the browser draws unthemed. Selection, caret, `accent-color`,
  scrollbars, focus ring and the date picker glyph already are; a system-blue selection
  belongs to no design system.
