"""Jackfield page frame: top bar, legend strip and grid.

This world's composition law is three rules, and all three are applied here:

1. A fixed legend strip on the left, under which the grid of rails drifts. The strip
   is not decoration: it carries the state the route needs to keep in view at all
   times.
2. The edge channels are never filled. Nothing takes the full width.
3. Rank is carried by scale and inversion. A single solid amber plate per screen,
   which is the primary action.
"""

import reflex as rx

from cv_generator.app.styles import (
    AMBER,
    CHANNEL,
    CONTENT_WIDTH,
    GLASS,
    GLASS_ETCHED,
    RULE_LINE,
    TEXT,
    TEXT_MUTED,
    display,
    legend,
    style_legend,
    touch_target,
)

# The contract of the chosen direction. It goes as an HTML comment inside the body
# because it has to survive the production build and be auditable with grep against
# the seed; a Python comment evaporates when compiling to React.
CONTRACT = """<!--
THESIS: Every achievement is tied to the text LinkedIn delivered by a line you can
break, and that stays broken. It rejects the card grid where everything weighs the same
and state is a colored badge.
OWN-WORLD: Black glass #0a0a0a and a single signal amber #ffb000. One variable grotesque
(Archivo) from 62% to 100% width, with no second family. Numbered rails under a fixed
legend strip; amber rules, no shadow and no radius. State is drawn by the stroke
pattern, never by color.
STORY: The applicant sees their history as a scheme of rails, deliberately breaks the
normals they want, and sends a CV knowing exactly what it carries inside.
FIRST VIEWPORT: Legend strip on the left with the profile status; on the right the
history as a scheme of numbered rails, each CV with its fixed plate of role, date and
template. A single solid amber plate: GENERATE NEW CV.
FORM: normalled jackfield, the challenger that won both axes; it displaced the assigned
candidate 3 (the typesetter's specimen). Seed 7dca38be.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish
review, the verdict, and DESIGN.md
-->"""


def address_contract() -> rx.Component:
    """Emits the contract in the document body."""
    return rx.html(CONTRACT, style={"display": "none"})


# The three routes reachable from anywhere. `/new` is not here: you start generating
# from the home page or by cloning, and putting it here would invite starting a CV halfway.
TARGETS = (
    ("/", "My CVs", "layout_list"),
    ("/profile", "My profile", "user_round"),
    ("/sync", "Sync", "refresh_cw"),
)

# Every route the application registers, including the one that is not in the bar.
# It is used to work out when the root is the active one; if a route is ever added, it
# goes here, and this is the only place to remember.
ROOTLESS_PATHS = ("/new", "/profile", "/sync")


def _current_path() -> rx.Var:
    return rx.State.router.page.path


def _mark() -> rx.Component:
    """The product name. The accent falls on "CV", the noun that names what the
    application produces, not on the generic word."""
    return rx.link(
        rx.el.span(
            rx.el.span(
                "CV",
                style={
                    "font_stretch": "62%",
                    "font_weight": "800",
                    "font_size": "1.375rem",
                    "letter_spacing": "0.01em",
                    "color": AMBER,
                    "line_height": "1",
                },
            ),
            rx.el.span(
                "Generator",
                style={**style_legend(TEXT_MUTED), "font_size": "0.75rem"},
            ),
            style={"display": "flex", "flex_direction": "column", "gap": "0.125rem"},
        ),
        href="/",
        text_decoration="none",
        aria_label="Go to the home page",
        style={**touch_target(), "display": "flex", "align_items": "center"},
    )


def _target(path: str, label: str, icon_name: str) -> rx.Component:
    """A navigation cell. The active one is underlined in amber.

    It is not inverted into a plate: the solid plate belongs to the primary action, and
    there used to be one per active destination competing with it on every route.
    """
    current = _current_path()
    if path == "/":
        # The root is not detected by comparing, it is DEDUCED: it is the active one when no
        # other route is.
        #
        # Comparing does not work because at the root `router.page.path` does not return "/",
        # nor the empty string — both were tried in the browser and neither matched, while on
        # /profile the same code does mark `aria-current="page"`. The exact value is a Reflex
        # internal detail that is better not pinned here. Deducing it does not depend on that
        # value and does not break if it changes between versions.
        active = current != ROOTLESS_PATHS[0]
        for other in ROOTLESS_PATHS[1:]:
            active = active & (current != other)
    else:
        active = current == path
    return rx.link(
        rx.el.span(
            rx.icon(icon_name, size=15, stroke_width=1.5),
            rx.el.span(label),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
        ),
        href=path,
        # `aria-current` is what announces "you are here" to a screen reader; the underline
        # only tells those who can see it.
        aria_current=rx.cond(active, "page", ""),
        style={
            **style_legend(),
            **touch_target(),
            "display": "flex",
            "align_items": "center",
            "padding": "0 0.75rem",
            "text_decoration": "none",
            "background": "transparent",
            # The active destination is marked with an amber underline, not by inverting the cell.
            # With the cell inverted there were TWO solid plates on screen — the navigation and
            # the primary action — competing in weight. The scheme this world comes from already
            # solves it this way: it underlines the active tab and keeps the solid plate for the
            # action. The plate belongs to the action, not to "where am I".
            "border_bottom": rx.cond(active, f"2px solid {AMBER}", "2px solid transparent"),
            "color": rx.cond(active, AMBER, TEXT_MUTED),
            "_hover": {"color": AMBER, "border_bottom_color": rx.cond(active, AMBER, RULE_LINE)},
        },
    )


def data_cell(caption: str, value: rx.Var | str) -> rx.Component:
    """A cell of the metadata group: label on top, figure below, a rule around it.

    It is the piece the critique asked for without naming it — the history said how
    many CVs there were but not where the profile stood.
    """
    return rx.el.div(
        legend(caption),
        rx.el.span(
            value,
            style={
                "font_stretch": "75%",
                "font_weight": "700",
                "font_size": "0.875rem",
                "color": TEXT,
                "font_variant_numeric": "tabular-nums",
                "white_space": "nowrap",
            },
        ),
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "0.25rem",
            "padding": "0.5rem 0.875rem",
            "border_right": f"1px solid {RULE_LINE}",
            "&:last-child": {"border_right": "none"},
        },
    )


def data_group(*cells: rx.Component) -> rx.Component:
    """The framed group in the top right corner of the scheme."""
    return rx.el.div(
        *cells,
        style={
            "display": "flex",
            "border": f"1px solid {RULE_LINE}",
            "background": GLASS_ETCHED,
            "flex_wrap": "wrap",
        },
    )


def nav_bar(data: rx.Component | None = None) -> rx.Component:
    """Persistent bar, identical on the four routes."""
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                _mark(),
                rx.el.nav(
                    *[_target(r, e, i) for r, e, i in TARGETS],
                    aria_label="Main navigation",
                    style={"display": "flex", "gap": "0.25rem", "flex_wrap": "wrap"},
                ),
                style={
                    "display": "flex",
                    "align_items": "center",
                    "gap": "1.5rem",
                    "flex_wrap": "wrap",
                },
            ),
            rx.el.div(style={"flex": "1 1 auto", "min_width": "0"}),
            data if data is not None else rx.fragment(),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "1rem",
                "flex_wrap": "wrap",
                "max_width": CONTENT_WIDTH,
                "margin": "0 auto",
                "padding": f"0.75rem {CHANNEL}",
            },
        ),
        style={
            "border_bottom": f"1px solid {RULE_LINE}",
            "background": GLASS,
            "position": "sticky",
            "top": "0",
            "z_index": "10",
        },
    )


def legend_strip(*children: rx.Component) -> rx.Component:
    """The fixed left column. On mobile it sits above the content instead of hiding:
    what it carries is state, not ornament."""
    return rx.el.aside(
        *children,
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "1.25rem",
            "flex": "0 0 auto",
            "width": ["100%", "100%", "100%", "16rem"],
            "border_right": ["none", "none", "none", f"1px solid {RULE_LINE}"],
            "padding_right": ["0", "0", "0", "1.5rem"],
            "align_self": "flex-start",
            "position": ["static", "static", "static", "sticky"],
            "top": "5.5rem",
        },
    )


def page(
    title: str,
    hint: str,
    *body: rx.Component,
    actions: rx.Component | None = None,
    strip: rx.Component | None = None,
    data: rx.Component | None = None,
) -> rx.Component:
    """Frame of a route.

    The title always goes in the same corner and in the headline voice; the actions on
    the right. `strip` is the legend column; `data` the framed group in the bar.
    """
    return rx.fragment(
        address_contract(),
        nav_bar(data),
        rx.el.main(
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.h1(title, style=display("clamp(2rem, 5vw, 3.25rem)")),
                        rx.el.p(
                            hint,
                            style={
                                "font_stretch": "100%",
                                "font_size": "0.9375rem",
                                "line_height": "1.5",
                                "color": TEXT_MUTED,
                                "max_width": "56ch",
                                "margin_top": "0.625rem",
                            },
                        ),
                        style={"min_width": "0"},
                    ),
                    rx.el.div(style={"flex": "1 1 auto", "min_width": "0"}),
                    actions if actions is not None else rx.fragment(),
                    style={
                        "display": "flex",
                        "width": "100%",
                        "gap": "1.5rem",
                        "flex_direction": ["column", "column", "row"],
                        "align_items": ["flex-start", "flex-start", "flex-end"],
                        "padding_bottom": "1.75rem",
                        "border_bottom": f"1px solid {RULE_LINE}",
                        "margin_bottom": "2rem",
                    },
                ),
                rx.el.div(
                    strip if strip is not None else rx.fragment(),
                    rx.el.div(
                        *body,
                        style={
                            "display": "flex",
                            "flex_direction": "column",
                            "gap": "2rem",
                            "flex": "1 1 auto",
                            "min_width": "0",
                        },
                    ),
                    style={
                        "display": "flex",
                        "gap": ["1.75rem", "1.75rem", "1.75rem", "2.5rem"],
                        "flex_direction": ["column", "column", "column", "row"],
                        "align_items": "stretch",
                        "width": "100%",
                    },
                ),
                style={
                    "max_width": CONTENT_WIDTH,
                    "margin": "0 auto",
                    "padding": f"2.5rem {CHANNEL} 5rem",
                },
            ),
        ),
    )
