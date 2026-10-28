"""Home: the scheme of rails of what you already sent, with the profile fixed at the side."""

import reflex as rx

from cv_generator.app.components.header import data_cell, data_group, legend_strip, page
from cv_generator.app.components.history_table import history_table
from cv_generator.app.components.profile_status import profile_status
from cv_generator.app.states.home_state import HomeState
from cv_generator.app.styles import (
    AMBER,
    RULE_LINE,
    TEXT,
    primary_button,
    touch_target,
)


def _primary_action() -> rx.Component:
    """The screen's only solid amber plate.

    Without a profile nothing can be generated, so the primary action is the one that
    unblocks it: promising "generate" here would contradict the scheme, which would be
    empty for a reason generating does not solve.
    """
    return rx.cond(
        HomeState.has_profile,
        primary_button(
            rx.icon("plus", size=16, stroke_width=2),
            "Generate new CV",
            on_click=HomeState.new_cv,
            style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem", "font_size": "0.75rem"},
        ),
        primary_button(
            rx.icon("download", size=16, stroke_width=2),
            "Import from LinkedIn",
            on_click=HomeState.open_sync,
            style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem", "font_size": "0.75rem"},
        ),
    )


def _message(text: rx.Var, icon_name: str, *, severe: bool = False) -> rx.Component:
    """A scheme notice: rule, glyph and text. No fill and no second tone.

    What is severe stands out by the THICKNESS of the rule and by the glyph, never by
    color. This used to take a tone, and the error came in a hand-written red, which
    contradicted the law of the world — state is carried by the stroke — and left out
    anyone who cannot tell that red from the amber.
    """
    return rx.el.div(
        rx.icon(icon_name, size=16, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
        rx.el.p(text, style={"font_stretch": "100%", "font_size": "0.875rem", "color": TEXT, "line_height": "1.5"}),
        style={
            "display": "flex",
            "align_items": "flex-start",
            "gap": "0.75rem",
            "border": f"1px solid {RULE_LINE}",
            "border_left": f"{'2px' if severe else '1px'} solid {AMBER}",
            "padding": "0.875rem 1rem",
        },
    )


def home_page() -> rx.Component:
    """Start screen: the full scheme of applications sent."""
    return page(
        "My CVs",
        "Every CV you generate opens its own rail and stays frozen exactly as you sent it.",
        rx.cond(HomeState.notice != "", _message(HomeState.notice, "circle_check"), rx.fragment()),
        rx.cond(HomeState.message != "", _message(HomeState.message, "circle_alert", severe=True), rx.fragment()),
        history_table(),
        actions=_primary_action(),
        strip=legend_strip(profile_status()),
        data=data_group(
            data_cell("Rails", HomeState.history.length().to_string()),
            data_cell("Archived", HomeState.archived_total.to_string()),
            data_cell(
                "Profile",
                rx.cond(HomeState.has_profile, "Tied", "Untied"),
            ),
        ),
    )
