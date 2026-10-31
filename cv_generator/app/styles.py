"""Interface design system: the normalled jackfield.

The idea behind everything here: in a patch bay, every signal is tied to its default
destination by a jumper. That is called the *normal*. An operator can break it by
hand, and then it stays broken until someone deliberately restores it.

This product does exactly that with your achievements. Each one is tied to the text
LinkedIn brought (`imported_value`). When you edit it, you break the normal. The sync
does not repair it on its own: it respects it and shows it to you broken.

That is why the link rail is the central component and not an ornament. It has SIX
patterns. Four of them are, one by one, the four cases of the reconciliation table in
the README:

    your text == origin, incoming == origin   ->  joined      ---------o
    your text != origin, incoming == origin   ->  broken      ----//---o
    your text == origin, incoming != origin   ->  proposed    - - -----o
    your text != origin, incoming != origin   ->  conflict    - - -(x)-o

The other two are not about reconciling but about what goes into THIS CV, and they are
the pair the wizard uses:

    inside this CV                        ->  folded      =========o
    left out of this CV, on purpose       ->  gap         ---   ---o

The living list, with what each one means in the product's words, is
`RAIL_DIRECTION`, further down in this file.

LAW OF THE WORLD: state is carried by the stroke pattern, never by color. All SIX
patterns use the same amber. This is not an aesthetic preference: it is what keeps the
interface readable for someone who cannot tell red from green, and what forces every
state to also have its label. If a state ever needs another color to stand out, the
pattern is badly drawn and the pattern is what gets fixed.

Hierarchy is carried by SCALE and INVERSION only. A single solid amber plate per
screen, which is always the primary action.
"""

import reflex as rx
from reflex_base.breakpoints import Breakpoints

# --- Tokens ----------------------------------------------------------------------
# The same values live in assets/style.css as custom properties. They are repeated
# here as Python constants because Radix's typed props do not read CSS.

GLASS = "#0a0a0a"
GLASS_ETCHED = "#121110"
GLASS_SUNKEN = "#060606"

AMBER = "#ffb000"
AMBER_FAINT = "#7a5200"
AMBER_INACTIVE = "#3a2600"

RULE_LINE = "rgba(255, 176, 0, 0.26)"
RULE_LINE_STRONG = "rgba(255, 176, 0, 0.55)"

# Secondary prose is tinted with the amber that governs the surface. Neutral gray on a
# colored background is the shortcut that gives away that nobody chose that tone.
TEXT = "#f2e4ce"
TEXT_FAINT = "#b59b72"
TEXT_MUTED = "#9a845e"

CONTENT_WIDTH = "1180px"

# The edge channels are never filled: they are the scheme's breathing room.
CHANNEL = "clamp(12px, 3vw, 28px)"


# --- Typography ------------------------------------------------------------------
# A single variable grotesque. The `wdth` axis does the job usually given to a second
# family: condensed for labels and rail figures, normal for prose.


def display(size: str = "clamp(2.5rem, 6vw, 4.75rem)") -> dict:
    """Headline voice: condensed, heavy, uppercase and very tight."""
    return {
        "font_family": '"Archivo", system-ui, sans-serif',
        "font_stretch": "62%",
        "font_weight": "800",
        "font_size": size,
        "line_height": "0.92",
        # The tracking floor is -0.04em; -0.02em keeps the headline dense without closing it up.
        "letter_spacing": "-0.02em",
        "text_transform": "uppercase",
        "color": AMBER,
        "text_wrap": "balance",
    }


def style_legend(color: str = TEXT_MUTED) -> dict:
    """Scheme label: condensed version, uppercase, generously spaced."""
    return {
        "font_family": '"Archivo", system-ui, sans-serif',
        "font_stretch": "75%",
        "font_weight": "600",
        "font_size": "0.6875rem",
        "letter_spacing": "0.14em",
        "text_transform": "uppercase",
        "color": color,
        "line_height": "1.2",
    }


def figure(size: str = "1.5rem", color: str = AMBER) -> dict:
    """Rail number: condensed and tabular, so the columns line up."""
    return {
        "font_family": '"Archivo", system-ui, sans-serif',
        "font_stretch": "62%",
        "font_weight": "700",
        "font_size": size,
        "font_variant_numeric": "tabular-nums",
        "letter_spacing": "0.01em",
        "color": color,
        "line_height": "1",
    }


def prose(color: str = TEXT) -> dict:
    """Running text. The measure is limited where it is used, not here."""
    return {
        "font_stretch": "100%",
        "font_size": "0.9375rem",
        "line_height": "1.55",
        "color": color,
    }


# --- Legend ----------------------------------------------------------------------


# Read by screen readers and not drawn: the usual clip down to one pixel.
VISUALLY_HIDDEN = {
    "position": "absolute",
    "width": "1px",
    "height": "1px",
    "margin": "-1px",
    "padding": "0",
    "border": "0",
    "overflow": "hidden",
    "clip": "rect(0, 0, 0, 0)",
    "white_space": "nowrap",
}


def legend(text: str | rx.Var, color: str = TEXT_MUTED, **props: object) -> rx.Component:
    """A scheme label. For SHORT LABELS, not for sentences.

    Uppercase is read by the shape of the word, and in capitals every word has the same
    shape: a rectangle. Beyond about 25 characters that stops being a label and starts
    being a sentence that is hard to read. That is what `note_text` is for.
    """
    style = {**style_legend(color), **props.pop("style", {})}
    return rx.el.span(text, style=style, **props)


def note_text(text: str | rx.Var, color: str = TEXT_MUTED, **props: object) -> rx.Component:
    """Short secondary text in lowercase: a short sentence, not a label.

    Same visual weight as the legend and the same family, but without the uppercase and
    the wide spacing, which are what make a whole sentence unreadable.
    """
    style = {
        "font_family": '"Archivo", system-ui, sans-serif',
        "font_stretch": "100%",
        "font_weight": "400",
        "font_size": "0.75rem",
        "line_height": "1.5",
        "color": color,
    }
    style.update(props.pop("style", {}))
    return rx.el.span(text, style=style, **props)


# --- The link rail ---------------------------------------------------------------

JOINED = "joined"
BROKEN = "broken"
GAP = "gap"
FOLDED = "folded"
PROPOSAL = "proposed"
CONFLICT = "conflict"

#: What each pattern means, in the product's words. The interface never shows a rail
#: without its label next to it: the stroke is the signal, not the message.
RAIL_DIRECTION = {
    JOINED: "Same as on LinkedIn",
    BROKEN: "You edited it",
    GAP: "Left out of this CV",
    FOLDED: "In this CV",
    PROPOSAL: "Changed on LinkedIn",
    CONFLICT: "Conflict",
}


def _terminal(conflict: bool = False) -> rx.Component:
    """The ring at the end of the rail. Always open; crossed if there is a conflict."""
    ring = rx.el.svg.circle(
        cx="7",
        cy="7",
        r="4.25",
        fill="none",
        stroke="currentColor",
        stroke_width="1.25",
    )
    if not conflict:
        return rx.el.svg(
            ring,
            width="14",
            height="14",
            view_box="0 0 14 14",
            aria_hidden="true",
            class_name="rail__terminal",
        )
    return rx.el.svg(
        ring,
        rx.el.svg.line(x1="4", y1="4", x2="10", y2="10", stroke="currentColor", stroke_width="1.25"),
        rx.el.svg.line(x1="10", y1="4", x2="4", y2="10", stroke="currentColor", stroke_width="1.25"),
        width="14",
        height="14",
        view_box="0 0 14 14",
        aria_hidden="true",
        class_name="rail__terminal",
    )


def _crosshair() -> rx.Component:
    """The two slanted marks that say 'the normal was broken here'."""
    return rx.el.svg(
        rx.el.svg.line(x1="3", y1="11", x2="7", y2="3", stroke="currentColor", stroke_width="1.25"),
        rx.el.svg.line(x1="7", y1="11", x2="11", y2="3", stroke="currentColor", stroke_width="1.25"),
        width="14",
        height="14",
        view_box="0 0 14 14",
        aria_hidden="true",
        class_name="rail__glyph",
    )


def _segment(double: bool = False, dashed: bool = False) -> rx.Component:
    css_classes = ["rail__segment"]
    if double:
        css_classes.append("rail__segment--double")
    if dashed:
        css_classes.append("rail__segment--dashed")
    return rx.el.div(class_name=" ".join(css_classes))


def _rail_drawing(status: str) -> list[rx.Component]:
    """The pieces of a pattern. Flexible width in the segments, fixed in the glyphs:
    that way the ring does not deform when the row stretches."""
    if status == BROKEN:
        return [_segment(), _crosshair(), _segment(), _terminal()]
    if status == GAP:
        return [_segment(), rx.el.div(class_name="rail__gap"), _segment(), _terminal()]
    if status == FOLDED:
        return [_segment(double=True), _terminal()]
    if status == PROPOSAL:
        return [_segment(dashed=True), _terminal()]
    if status == CONFLICT:
        return [_segment(dashed=True), _terminal(conflict=True)]
    return [_segment(), _terminal()]


def rail(status: rx.Var | str = JOINED, **props: object) -> rx.Component:
    """The link rail between an item and its default value.

    It accepts a literal or a state Var. It is decorative for assistive technology
    (`aria-hidden`): the meaning travels in the text label that goes with it, never
    only in the drawing.
    """
    if isinstance(status, str):
        content = _rail_drawing(status)
        return rx.el.div(*content, class_name="rail", aria_hidden="true", **props)

    return rx.el.div(
        rx.match(
            status,
            *[(key, rx.fragment(*_rail_drawing(key))) for key in RAIL_DIRECTION],
            rx.fragment(*_rail_drawing(JOINED)),
        ),
        class_name="rail",
        aria_hidden="true",
        **props,
    )


# --- Superficies -----------------------------------------------------------------


def panel(*children: rx.Component, **props: object) -> rx.Component:
    """Etched glass with an amber rule. It replaces the card: no shadow, no soft radius
    and never nested inside another panel."""
    style = {
        "background": GLASS_ETCHED,
        "border": f"1px solid {RULE_LINE}",
        "padding": "1rem 1.125rem",
    }
    style.update(props.pop("style", {}))
    return rx.el.div(*children, style=style, **props)


def status_mark(text: str | rx.Var, on: rx.Var | bool = False, **props: object) -> rx.Component:
    """The scheme's state cell. On is a solid plate; off is an outline.

    The difference is inversion, not color: both use the same amber.
    """
    style = {
        **style_legend(),
        "border": f"1px solid {RULE_LINE_STRONG}",
        "padding": "0.25rem 0.5rem",
        "display": "inline-block",
        "text_align": "center",
        "white_space": "nowrap",
        "background": rx.cond(on, AMBER, "transparent"),
        "color": rx.cond(on, GLASS, TEXT_FAINT),
    }
    style.update(props.pop("style", {}))
    return rx.el.span(text, style=style, **props)


def tag(label: str, color: str = AMBER, *, solid: bool = False) -> rx.Component:
    """Outlined in `color`, or a solid plate of it with the text in glass.

    It says where an achievement comes from ("LinkedIn", "Edited", "Yours"), the same in
    My profile and in the wizard.
    """
    return rx.el.span(
        label,
        style={
            **style_legend(GLASS if solid else color),
            "border": f"1px solid {color}",
            "background": color if solid else "transparent",
            "padding": "0.125rem 0.375rem",
            "white_space": "nowrap",
            "flex": "0 0 auto",
        },
    )


# --- Controls --------------------------------------------------------------------


def _button_base() -> dict:
    return {
        **style_legend(),
        "display": "inline-flex",
        "align_items": "center",
        "justify_content": "center",
        "gap": "0.5rem",
        "padding": "0 1rem",
        "border_radius": "0",
        "cursor": "pointer",
        "transition": "background 120ms ease-out, color 120ms ease-out",
    }


def primary_button(*children: object, **props: object) -> rx.Component:
    """The solid plate. Only one per screen: it is the action the screen exists to
    offer."""
    style = {
        **_button_base(),
        "background": AMBER,
        "color": GLASS,
        "border": f"1px solid {AMBER}",
        "font_weight": "700",
        "min_height": "2.75rem",
        "_hover": {"background": "#ffc233"},
        "_disabled": {
            "background": "transparent",
            "color": TEXT_MUTED,
            "border": f"1px solid {AMBER_INACTIVE}",
            "cursor": "not-allowed",
        },
    }
    style.update(props.pop("style", {}))
    return rx.el.button(*children, style=style, **props)


def _secondary_style() -> dict:
    return {
        **_button_base(),
        "background": "transparent",
        "color": AMBER,
        "border": f"1px solid {RULE_LINE_STRONG}",
        "min_height": "2.75rem",
        "_hover": {"background": AMBER, "color": GLASS},
        "_disabled": {
            "color": TEXT_MUTED,
            "border": f"1px solid {AMBER_INACTIVE}",
            "cursor": "not-allowed",
            "background": "transparent",
        },
    }


def secondary_button(*children: object, **props: object) -> rx.Component:
    """Outline. It inverts on hover, which is how the world marks what is active."""
    style = _secondary_style()
    style.update(props.pop("style", {}))
    return rx.el.button(*children, style=style, **props)


def secondary_link(*children: object, **props: object) -> rx.Component:
    """The `secondary_button` outline on an `<a>` link.

    What leads to another page is a link even if it looks like a button: it opens in
    another tab with `target`, without the round trip to the server of an event, after
    which the browser may take a `window.open` for a popup and block it.
    """
    style = {**_secondary_style(), "text_decoration": "none"}
    style.update(props.pop("style", {}))
    return rx.el.a(*children, style=style, **props)


def field_style() -> dict:
    """Input box: straight, with an amber rule and the focus as a plate."""
    return {
        "background": GLASS_SUNKEN,
        "border": f"1px solid {RULE_LINE}",
        "border_radius": "0",
        "color": TEXT,
        "font_family": '"Archivo", system-ui, sans-serif',
        "font_size": "0.9375rem",
        "padding": "0.625rem 0.75rem",
        "min_height": "2.75rem",
        "width": "100%",
        "&::placeholder": {"color": TEXT_MUTED},
        "_focus": {"border_color": AMBER, "outline": "none"},
    }


# --- Responsive ------------------------------------------------------------------
# Radix's typed props (direction, columns, size) require `rx.breakpoints`: a plain list
# only works for style props, and on the rest it raises TypeError at compile time. This
# was learned by breaking the build; do not simplify it.


def responsive_columns() -> Breakpoints:
    """A single column up to md: at 390px a two-column grid overflowed the viewport."""
    return rx.breakpoints(initial="1", md="2")


def header_direction() -> Breakpoints:
    return rx.breakpoints(initial="column", md="row")


def header_alignment() -> Breakpoints:
    return rx.breakpoints(initial="start", md="center")


def row_action_size() -> Breakpoints:
    """Bigger on touch, compact on desktop."""
    return rx.breakpoints(initial="2", md="1")


def touch_target() -> dict:
    """Minimum height of a control on a touch screen.

    44px is the minimum a finger hits reliably. The 2026-08-28 critique found this was
    applied only to buttons, leaving nine inputs at 32px; now `field_style` carries it
    by default.
    """
    return {"min_height": ["44px", "44px", "auto"]}
