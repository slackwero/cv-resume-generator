"""The list of professions in My profile → Contact.

Each row is a `translation_field` with its arrows and Delete. Delete asks first, in
place, and is disabled on the only entry: a CV needs a profession. An "Add a profession"
form follows the list. Every change saves right away (`ProfessionState`).
"""

import reflex as rx

from cv_generator.app.components.translation_field import translation_field
from cv_generator.app.states.profession_state import ADD_FORM, ProfessionState
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.app.styles import (
    AMBER,
    BROKEN,
    JOINED,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    VISUALLY_HIDDEN,
    error_notice,
    field_style,
    legend,
    note_text,
    primary_button,
    rail,
    secondary_button,
    style_legend,
    touch_target,
)

# Compact on desktop, a finger's width on touch, like the actions of an achievement.
_SMALL_BUTTON = {"min_height": ["2.75rem", "2.75rem", "2rem"], "padding": "0 0.75rem"}

# Why Delete is disabled on the only entry.
LAST_ONE_REASON = "A CV needs a profession: keep at least one."


def _move_button(direction: str, label: str, offset: int, row: rx.Var) -> rx.Component:
    """Disabled at the ends: an active arrow that does nothing reads as broken.

    The id is what the keyboard comes back to after the move.
    """
    return secondary_button(
        rx.icon(f"chevron_{direction}", size=13, stroke_width=1.75),
        id=f"profession-move-{direction}-" + row["key"],
        type="button",
        on_click=ProfessionState.move(row["key"], offset),
        disabled=row["first"] == "yes" if direction == "up" else row["last"] == "yes",
        aria_label=label,
        title=label,
        style={**_SMALL_BUTTON, "min_width": ["2.75rem", "2.75rem", "2rem"], "padding": "0"},
    )


def _row_error(row: rx.Var) -> rx.Component:
    return rx.cond(
        (ProfessionState.error != "") & (ProfessionState.error_at == row["key"]),
        error_notice(ProfessionState.error, margin_top="0.25rem"),
        rx.fragment(),
    )


def _confirmation(row: rx.Var) -> rx.Component:
    """The keyboard lands on Cancel, the answer that loses nothing, and the group is named
    by its question, so a screen reader reads the question on the way in."""
    question = "profession-confirm-" + row["key"]
    return rx.el.div(
        rx.el.p(
            "Delete this profession in English and in Spanish? CVs you already generated keep it.",
            id=question,
            style={"font_stretch": "100%", "font_size": "0.8125rem", "color": TEXT, "line_height": "1.5"},
        ),
        _row_error(row),
        rx.el.div(
            primary_button(
                "Delete", type="button", on_click=ProfessionState.confirm_delete(row["key"]), style=_SMALL_BUTTON
            ),
            secondary_button(
                "Cancel", type="button", auto_focus=True, on_click=ProfessionState.cancel_delete, style=_SMALL_BUTTON
            ),
            style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "margin_top": "0.5rem"},
        ),
        role="group",
        aria_labelledby=question,
        style={"border_left": f"2px solid {AMBER}", "padding": "0.25rem 0 0.25rem 0.75rem", "margin_top": "0.625rem"},
    )


def _delete_button(row: rx.Var) -> rx.Component:
    only_one = ProfessionState.rows.length() < 2
    return secondary_button(
        "Delete",
        id="profession-delete-" + row["key"],
        type="button",
        on_click=ProfessionState.ask_delete(row["key"]),
        disabled=only_one,
        title=rx.cond(only_one, LAST_ONE_REASON, ""),
        style=_SMALL_BUTTON,
    )


def _profession_row(row: rx.Var) -> rx.Component:
    confirming = ProfessionState.confirming_key == row["key"]
    return rx.el.div(
        rx.el.div(
            _move_button("up", "Move up", -1, row),
            _move_button("down", "Move down", 1, row),
            style={"display": "flex", "flex_direction": "column", "gap": "0.25rem", "flex": "0 0 auto"},
        ),
        rx.el.div(
            translation_field(
                row,
                on_save=ProfessionState.save,
                on_submit=ProfessionState.save_from_form,
                on_confirm=ProfessionState.confirm,
                on_same=ProfessionState.same,
            ),
            rx.cond(confirming, _confirmation(row), _row_error(row)),
            # 12rem and not more: at 390px the field has to fit next to the arrows, and
            # the Delete button is what wraps to the next line.
            style={"flex": "1 1 12rem", "min_width": "0"},
        ),
        rx.cond(
            confirming,
            rx.fragment(),
            rx.el.div(_delete_button(row), style={"margin_left": "auto", "align_self": "flex-start"}),
        ),
        key=row["key"],
        style={
            "display": "flex",
            "align_items": "flex-start",
            "flex_wrap": "wrap",
            "gap": "0.75rem",
            "padding": "0.625rem 0",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


def _live_error() -> rx.Component:
    """The list's only live region: it announces every error once, wherever it is drawn.

    Above the list it only draws the error of a row that is gone or of the whole list; the
    rest are drawn at their row or the add form, so here they are only read out.
    """
    return rx.el.div(
        rx.cond(
            ProfessionState.error != "",
            rx.cond(
                ProfessionState.error_at != "",
                rx.el.span(ProfessionState.error, style=VISUALLY_HIDDEN),
                error_notice(ProfessionState.error, margin_top="0.5rem"),
            ),
            rx.fragment(),
        ),
        aria_live="polite",
    )


def _add_form() -> rx.Component:
    return rx.el.form(
        rx.el.label("Add a profession", html_for="profession-new", style=style_legend(TEXT_FAINT)),
        rx.el.div(
            rx.el.input(
                id="profession-new",
                name="text",
                placeholder="Security Architect",
                style={**field_style(), **touch_target(), "flex": "1 1 auto", "min_width": "0"},
            ),
            secondary_button(
                rx.icon("plus", size=14, stroke_width=1.75),
                "Add",
                type="submit",
                style={"min_height": "2.75rem", "padding": "0 1rem"},
            ),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem", "width": "100%"},
        ),
        rx.cond(
            (ProfessionState.error != "") & (ProfessionState.error_at == ADD_FORM),
            error_notice(ProfessionState.error, margin_top="0.25rem"),
            rx.fragment(),
        ),
        on_submit=ProfessionState.add,
        reset_on_submit=True,
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "0.375rem",
            "width": "100%",
            "margin_top": "0.75rem",
        },
    )


def professions_editor() -> rx.Component:
    """The whole editor: heading with the status of the link, the hint, the rows and the add form."""
    return rx.el.div(
        rx.el.div(
            legend("Profession", color=TEXT_FAINT),
            rx.el.div(style={"flex": "1 1 auto"}),
            # The link tells the truth about the CV: it is untied while no headline has text.
            rail(
                rx.cond(ProfileState.profession_pending, BROKEN, JOINED),
                style={"max_width": "2.75rem", "flex": "0 0 auto"},
            ),
            legend(
                rx.cond(ProfileState.profession_pending, "Untied", "Tied"),
                color=rx.cond(ProfileState.profession_pending, AMBER, TEXT_MUTED),
            ),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem", "margin_bottom": "0.375rem"},
        ),
        note_text("It appears under your name. Each CV picks one.", style={"display": "block"}),
        _live_error(),
        rx.el.div(
            rx.foreach(ProfessionState.rows, _profession_row),
            style={"border_top": f"1px solid {RULE_LINE}", "margin_top": "0.75rem"},
        ),
        _add_form(),
        style={"width": "100%", "min_width": "0"},
    )
