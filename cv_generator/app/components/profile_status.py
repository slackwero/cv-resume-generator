"""The home page legend strip: the state of the profile everything comes from.

In the scheme this world comes from, the left column is not a decorative panel: it
carries the state the operator needs to keep in front of them at all times. Here it
carries the same — whose profile it is, how much it holds, when it was synced and what
it is missing.

It goes in the strip and not in the body on purpose. The body is the scheme of rails;
the profile is the source they are all cut from, and that is why it stays fixed at the
side while the scheme drifts underneath.
"""

import reflex as rx

from cv_generator.app.states.home_state import HomeState
from cv_generator.app.styles import (
    AMBER,
    BROKEN,
    JOINED,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    legend,
    rail,
    secondary_button,
    touch_target,
)


def _status_row(tally: rx.Var) -> rx.Component:
    """Label on the left, figure on the right, a rule between rows."""
    return rx.el.div(
        legend(tally["caption"], color=TEXT_FAINT),
        rx.el.span(
            tally["value"],
            style={
                "font_stretch": "62%",
                "font_weight": "700",
                "font_size": "1rem",
                "color": TEXT,
                "font_variant_numeric": "tabular-nums",
            },
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "gap": "1rem",
            "padding": "0.5rem 0",
            "border_bottom": f"1px solid {RULE_LINE}",
            "&:last-child": {"border_bottom": "none"},
        },
    )


def _notice(text: rx.Var) -> rx.Component:
    """A notice that also leads to the place where it is solved.

    A notice that names a problem without offering the action forces the user to find
    the screen on their own, and here that screen is the only one that can fix it.

    The rail is broken: a required field the importer did not bring is, literally, a
    normal that was left untied.
    """
    return rx.el.div(
        rx.el.div(
            rail(BROKEN, style={"max_width": "3.5rem", "flex": "0 0 auto"}),
            legend("Untied", color=AMBER),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem", "margin_bottom": "0.5rem"},
        ),
        rx.el.p(
            text,
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "line_height": "1.5",
                "color": TEXT_FAINT,
                "margin_bottom": "0.75rem",
            },
        ),
        secondary_button(
            "Complete",
            on_click=HomeState.go_to_profile,
            style={"min_height": "2.25rem", "padding": "0 0.75rem", "font_size": "0.625rem", "width": "100%"},
        ),
        style={"border": f"1px solid {RULE_LINE}", "padding": "0.875rem"},
    )


def profile_status() -> rx.Component:
    """Who you are, how much your profile holds and when it was synced."""
    return rx.fragment(
        rx.el.div(
            legend("Master profile"),
            rx.el.h2(
                rx.cond(HomeState.has_profile, HomeState.profile_headline, "No profile"),
                style={
                    "font_stretch": "75%",
                    "font_weight": "700",
                    "font_size": "1.125rem",
                    "color": TEXT,
                    "line_height": "1.2",
                    "margin_top": "0.375rem",
                },
            ),
            rx.cond(
                HomeState.content_language != "",
                rx.el.div(
                    legend("Content in ", color=TEXT_MUTED),
                    legend(HomeState.content_language.upper(), color=AMBER),
                    style={"display": "flex", "gap": "0.25rem", "margin_top": "0.375rem"},
                ),
                rx.fragment(),
            ),
            style={"border_bottom": f"1px solid {RULE_LINE}", "padding_bottom": "1rem"},
        ),
        rx.cond(
            HomeState.has_profile,
            rx.el.div(rx.foreach(HomeState.tallies, _status_row)),
            rx.fragment(),
        ),
        # The sync line: its rail says whether the profile is tied to LinkedIn.
        rx.el.div(
            rx.el.div(
                rail(
                    rx.cond(HomeState.synced, JOINED, BROKEN),
                    style={"max_width": "3.5rem", "flex": "0 0 auto"},
                ),
                legend(
                    rx.cond(HomeState.synced, "Tied to LinkedIn", "Never tied"),
                    color=rx.cond(HomeState.synced, TEXT_FAINT, AMBER),
                ),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
            ),
            rx.el.p(
                HomeState.sync_detail,
                style={
                    "font_stretch": "100%",
                    "font_size": "0.75rem",
                    "line_height": "1.5",
                    "color": TEXT_MUTED,
                    "margin_top": "0.5rem",
                },
            ),
            style={"border_top": f"1px solid {RULE_LINE}", "padding_top": "1rem"},
        ),
        rx.foreach(HomeState.notices, _notice),
        rx.cond(
            HomeState.has_profile,
            rx.el.div(
                secondary_button(
                    rx.icon("pencil", size=13, stroke_width=1.75),
                    "My profile",
                    on_click=HomeState.go_to_profile,
                    style={**touch_target(), "flex": "1 1 auto", "font_size": "0.625rem"},
                ),
                secondary_button(
                    rx.icon("refresh_cw", size=13, stroke_width=1.75),
                    "Sync",
                    on_click=HomeState.open_sync,
                    style={**touch_target(), "flex": "1 1 auto", "font_size": "0.625rem"},
                ),
                style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap"},
            ),
            rx.fragment(),
        ),
    )
