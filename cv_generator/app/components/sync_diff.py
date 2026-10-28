"""The changes a sync proposes, as a reconciliation of normals.

This is the screen this world was chosen for. In a patch bay, normalling means tying a
signal to its default destination; the operator can break that normal by hand, and then
it stays broken. That is exactly what this product does with your achievements, and the
README table is drawn here without translating anything:

    your text == origin, incoming == origin   unchanged       -------o
    your text == origin, incoming != origin   proposed        - - - -o
    your text != origin, incoming == origin   you broke it    ----//-o
    your text != origin, incoming != origin   conflict        - - -(x)

The amber, blue and green of the previous version are gone. A conflicting change and a
new one were told apart only by the tone of their badge, so anyone who cannot separate
those colors read a flat list. Now the stroke separates them and, above all, the word.
"""

import reflex as rx

from cv_generator.app.states.sync_state import SyncState
from cv_generator.app.styles import (
    AMBER,
    CONFLICT,
    GLASS_ETCHED,
    JOINED,
    PROPOSAL,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    figure,
    legend,
    rail,
    secondary_button,
    touch_target,
)

# A conflict is the only case where both sides moved: the rail says so with the crossed
# ring, which in the source scheme marks the destructive end.
_PATTERN_BY_KIND = [("conflict", CONFLICT), ("modified", PROPOSAL), ("new", PROPOSAL)]


def _pattern(change: rx.Var) -> rx.Var:
    return rx.match(change["kind"], *_PATTERN_BY_KIND, JOINED)


def _checkbox(**props: object) -> rx.Component:
    style = {"border_radius": "0", "flex": "0 0 auto"}
    style.update(props.pop("style", {}))
    return rx.checkbox(color_scheme="amber", high_contrast=True, size="2", style=style, **props)


def _previous_text(change: rx.Var) -> rx.Component:
    """It only makes sense to show it when there is a previous version that would be lost."""
    return rx.cond(
        change["current_text"] != "",
        rx.el.div(
            legend("Your current version", color=AMBER),
            rx.el.p(
                change["current_text"],
                style={
                    "font_stretch": "100%",
                    "font_size": "0.875rem",
                    "line_height": "1.55",
                    "color": TEXT_FAINT,
                    "margin_top": "0.375rem",
                },
            ),
            style={
                "border_left": f"1px solid {RULE_LINE}",
                "padding_left": "0.875rem",
                "width": "100%",
            },
        ),
        rx.fragment(),
    )


def _change_row(change: rx.Var) -> rx.Component:
    """A proposed change, with its checkbox.

    The text block goes inside a `<label for>`: without it, in a review of dozens of
    rows the only click target was the checkbox's 16px square.
    """
    control_id = "change-" + change["key"]
    return rx.el.div(
        _checkbox(
            id=control_id,
            checked=SyncState.accepted_items[change["key"]],
            on_change=lambda value: SyncState.toggle(change["key"], value),
            style={"margin_top": "0.25rem"},
        ),
        rx.el.label(
            rx.el.div(
                legend(change["kind_label"], color=TEXT),
                rail(_pattern(change), style={"max_width": "3.5rem", "flex": "0 0 auto"}),
                rx.el.div(style={"flex": "1 1 auto"}),
                legend(change["section"]),
                style={
                    "display": "flex",
                    "align_items": "center",
                    "gap": "0.625rem",
                    "width": "100%",
                    "flex_wrap": "wrap",
                },
            ),
            _previous_text(change),
            rx.el.div(
                rx.cond(
                    change["current_text"] != "",
                    legend("What LinkedIn brings", color=TEXT_FAINT),
                    rx.fragment(),
                ),
                rx.el.p(
                    change["incoming_text"],
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.55",
                        "color": TEXT,
                        "margin_top": "0.375rem",
                    },
                ),
                style={"width": "100%"},
            ),
            html_for=control_id,
            style={
                "cursor": "pointer",
                "display": "flex",
                "flex_direction": "column",
                "align_items": "flex-start",
                "gap": "0.75rem",
                "width": "100%",
                "min_width": "0",
            },
        ),
        style={
            "display": "flex",
            "align_items": "flex-start",
            "gap": "0.875rem",
            "width": "100%",
            "padding": "1rem 1.125rem",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


def _group_heading(row: rx.Var) -> rx.Component:
    """Separates the review blocks and says what each one is about."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                row["title"],
                style={
                    "font_stretch": "62%",
                    "font_weight": "800",
                    "font_size": "1.125rem",
                    "text_transform": "uppercase",
                    "letter_spacing": "0.01em",
                    "color": AMBER,
                },
            ),
            rx.el.span(row["tally"], style=figure("1rem", TEXT_FAINT)),
            style={"display": "flex", "align_items": "baseline", "gap": "0.625rem", "flex_wrap": "wrap"},
        ),
        rx.el.p(
            row["hint"],
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "line_height": "1.5",
                "margin_top": "0.375rem",
                "max_width": "64ch",
            },
        ),
        style={
            "padding": "1.5rem 1.125rem 0.75rem",
            "border_bottom": f"1px solid {RULE_LINE}",
            "background": GLASS_ETCHED,
        },
    )


def _row(row: rx.Var) -> rx.Component:
    return rx.cond(row["row"] == "group", _group_heading(row), _change_row(row))


def _count_cell(tally: rx.Var, singular: str, plural: str) -> rx.Component:
    """A counter at zero is not drawn: it takes space to deny something nobody asked."""
    return rx.cond(
        tally > 0,
        rx.el.div(
            rx.el.span(tally.to_string(), style=figure("1.5rem")),
            legend(rx.cond(tally == 1, singular, plural), color=TEXT_FAINT),
            style={
                "display": "flex",
                "flex_direction": "column",
                "gap": "0.25rem",
                "padding": "0.625rem 0.875rem",
                "border": f"1px solid {RULE_LINE}",
                "min_width": "7rem",
            },
        ),
        rx.fragment(),
    )


def changes_summary() -> rx.Component:
    """How many changes there are of each kind."""
    return rx.el.div(
        _count_cell(SyncState.conflict_count, "In conflict", "In conflict"),
        _count_cell(SyncState.modified_count, "Changed on LinkedIn", "Changed on LinkedIn"),
        _count_cell(SyncState.new_count, "New", "New"),
        _count_cell(SyncState.unchanged_count, "Unchanged", "Unchanged"),
        rx.cond(
            SyncState.detected_language != "",
            rx.el.div(
                rx.el.span(SyncState.detected_language.upper(), style=figure("1.5rem")),
                legend("Detected language", color=TEXT_FAINT),
                style={
                    "display": "flex",
                    "flex_direction": "column",
                    "gap": "0.25rem",
                    "padding": "0.625rem 0.875rem",
                    "border": f"1px solid {RULE_LINE}",
                    "min_width": "7rem",
                },
            ),
            rx.fragment(),
        ),
        style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "width": "100%"},
    )


def change_list() -> rx.Component:
    """The actionable changes, with the conflicts on top."""
    return rx.cond(
        SyncState.nothing_to_do,
        rx.el.div(
            rx.el.div(
                rail(JOINED, style={"max_width": "4rem", "flex": "0 0 auto"}),
                legend("All tied", color=AMBER),
                style={"display": "flex", "align_items": "center", "gap": "0.625rem"},
            ),
            rx.el.p(
                "Your profile is already up to date: LinkedIn brings nothing you do not have.",
                style={
                    "font_stretch": "100%",
                    "font_size": "0.875rem",
                    "color": TEXT_FAINT,
                    "line_height": "1.55",
                    "margin_top": "0.5rem",
                },
            ),
            style={"border": f"1px solid {RULE_LINE}", "padding": "1.25rem"},
        ),
        rx.el.div(
            rx.el.div(
                secondary_button(
                    "Check all",
                    on_click=SyncState.mark_all,
                    style={
                        **touch_target(),
                        "min_height": "2.25rem",
                        "padding": "0 0.75rem",
                        "font_size": "0.625rem",
                    },
                ),
                secondary_button(
                    "Uncheck all",
                    on_click=SyncState.unmark_all,
                    style={
                        **touch_target(),
                        "min_height": "2.25rem",
                        "padding": "0 0.75rem",
                        "font_size": "0.625rem",
                    },
                ),
                secondary_button(
                    "Back to the suggestion",
                    on_click=SyncState.restore_suggestion,
                    style={
                        **touch_target(),
                        "min_height": "2.25rem",
                        "padding": "0 0.75rem",
                        "font_size": "0.625rem",
                    },
                ),
                style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap"},
            ),
            rx.el.div(
                rx.foreach(SyncState.change_rows, _row),
                style={"border": f"1px solid {RULE_LINE}", "width": "100%", "margin_top": "1rem"},
            ),
            style={"width": "100%"},
        ),
    )
