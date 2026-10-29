"""The Work experience subsection of My profile: the achievements of each job, editable.

Each achievement wears a tag that says where it stands against LinkedIn:

    LinkedIn   outlined, muted    the text LinkedIn brought, untouched
    Edited     outlined, amber    you rewrote it; "LinkedIn says" keeps the original
    Yours      solid amber        you wrote it, or it is a copy: the sync never touches it

The tag is a word and not only a tone, the same law as the rails. The role, company and
dates of a job are read-only: they come from LinkedIn.
"""

import reflex as rx

from cv_generator.app.states.experience_state import ExperienceState
from cv_generator.app.styles import (
    AMBER,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    field_style,
    legend,
    note_text,
    panel,
    primary_button,
    secondary_button,
    tag,
    touch_target,
)

# Compact on desktop, a finger's width on touch: a long list of jobs carries many of these.
_SMALL_BUTTON = {"min_height": ["2.75rem", "2.75rem", "2rem"], "padding": "0 0.75rem"}

# Read by screen readers and not drawn: the usual clip down to one pixel.
_VISUALLY_HIDDEN = {
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


def _origin_tag(origin: rx.Var) -> rx.Component:
    return rx.match(
        origin,
        ("linkedin", tag("LinkedIn", TEXT_MUTED)),
        ("edited", tag("Edited")),
        ("yours", tag("Yours", solid=True)),
        rx.fragment(),
    )


def _textarea(**props: object) -> rx.Component:
    """No `value=`: the field governs itself and the text only travels when the form is sent."""
    return rx.el.textarea(
        name="text",
        rows="3",
        auto_focus=True,
        style={**field_style(), "resize": "vertical", "line_height": "1.55"},
        **props,
    )


def _form_buttons(submit: str, on_cancel: rx.event.EventSpec, *extra: rx.Component) -> rx.Component:
    return rx.el.div(
        primary_button(submit, type="submit", style=_SMALL_BUTTON),
        secondary_button("Cancel", type="button", on_click=on_cancel, style=_SMALL_BUTTON),
        *extra,
        style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "margin_top": "0.625rem"},
    )


def _form_box(*children: rx.Component, **props: object) -> rx.Component:
    """The open form, framed in amber so the eye finds it in a long list."""
    return rx.el.form(
        *children,
        style={"border": f"1px solid {AMBER}", "padding": "0.75rem", "margin": "0.5rem 0 0.5rem 1.5rem"},
        **props,
    )


def _notice(message: rx.Var, **style: str) -> rx.Component:
    """An error, drawn like the notices of the other subsections of My profile."""
    return rx.el.div(
        rx.icon("circle_alert", size=15, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
        rx.el.p(
            message,
            style={"font_stretch": "100%", "font_size": "0.875rem", "color": TEXT, "line_height": "1.5"},
        ),
        style={
            "display": "flex",
            "gap": "0.75rem",
            "align_items": "flex-start",
            "border": f"1px solid {RULE_LINE}",
            "border_left": f"2px solid {AMBER}",
            "padding": "0.875rem 1rem",
            **style,
        },
    )


def _form_error() -> rx.Component:
    """The error of the open form, right above its buttons, where the eye already is.

    Only one form is open at a time, so it is this one's. It is not a live region:
    `_error_notice` announces it, once.
    """
    return rx.cond(
        (ExperienceState.error != "") & ExperienceState.error_in_form,
        _notice(ExperienceState.error, margin_top="0.625rem"),
        rx.fragment(),
    )


# --- Job -------------------------------------------------------------------------


def _job(row: rx.Var) -> rx.Component:
    """The job's heading, which folds and unfolds its achievements.

    It is one button with `aria-expanded`, so the screen reader says whether the list
    below is open. The details are not editable: there is no field to click into.
    """
    opened = ExperienceState.open_jobs[row["experience_id"]]
    return rx.el.button(
        rx.cond(
            opened,
            rx.icon("chevron_down", size=16, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
            rx.icon("chevron_right", size=16, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
        ),
        rx.el.span(
            rx.el.span(
                row["role"],
                style={
                    "font_stretch": "75%",
                    "font_weight": "700",
                    "font_size": "0.9375rem",
                    "text_transform": "uppercase",
                    "letter_spacing": "0.03em",
                    "color": TEXT,
                    "display": "block",
                },
            ),
            rx.el.span(
                legend(row["company"] + " · " + row["dates"]),
                note_text("From LinkedIn", style={"margin_left": "0.5rem"}),
                style={"display": "block", "margin_top": "0.25rem"},
            ),
            style={"flex": "1 1 auto", "min_width": "0"},
        ),
        legend(row["count"], color=TEXT_FAINT, style={"flex": "0 0 auto", "white_space": "nowrap"}),
        type="button",
        on_click=ExperienceState.toggle_job(row["experience_id"]),
        aria_expanded=rx.cond(opened, "true", "false"),
        style={
            **touch_target(),
            "display": "flex",
            "align_items": "center",
            "gap": "0.75rem",
            "width": "100%",
            "text_align": "left",
            "background": "transparent",
            "border": "none",
            "border_bottom": f"1px solid {RULE_LINE}",
            "padding": "1rem 0 0.625rem",
            "margin_top": "0.5rem",
            "cursor": "pointer",
            "color": TEXT,
            "font_family": "inherit",
        },
    )


# --- Achievement -----------------------------------------------------------------


def _move_button(icon_name: str, label: str, offset: int, row: rx.Var, *, disabled: rx.Var) -> rx.Component:
    """Disabled at the ends: an active arrow that does nothing reads as broken."""
    return secondary_button(
        rx.icon(icon_name, size=13, stroke_width=1.75),
        type="button",
        on_click=ExperienceState.move(row["key"], offset),
        disabled=disabled,
        aria_label=label,
        title=label,
        style={**_SMALL_BUTTON, "min_width": ["2.75rem", "2.75rem", "2rem"], "padding": "0"},
    )


def _confirmation(row: rx.Var) -> rx.Component:
    """Delete asks first, in place. What it says depends on where the achievement came from:
    only a LinkedIn one is remembered so the sync does not offer it again."""
    return rx.el.div(
        rx.el.p(
            "Delete this achievement? CVs you already generated keep it.",
            rx.cond(row["origin"] != "yours", " The LinkedIn sync will not offer it again.", ""),
            style={"font_stretch": "100%", "font_size": "0.8125rem", "color": TEXT, "line_height": "1.5"},
        ),
        _form_error(),
        rx.el.div(
            primary_button(
                "Delete", type="button", on_click=ExperienceState.confirm_delete(row["key"]), style=_SMALL_BUTTON
            ),
            secondary_button("Cancel", type="button", on_click=ExperienceState.cancel_delete, style=_SMALL_BUTTON),
            style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "margin_top": "0.5rem"},
        ),
        style={"border_left": f"2px solid {AMBER}", "padding": "0.25rem 0 0.25rem 0.75rem", "margin_top": "0.625rem"},
    )


def _actions(row: rx.Var) -> rx.Component:
    return rx.el.div(
        secondary_button("Edit", type="button", on_click=ExperienceState.start_edit(row["key"]), style=_SMALL_BUTTON),
        secondary_button(
            "Duplicate", type="button", on_click=ExperienceState.duplicate(row["key"]), style=_SMALL_BUTTON
        ),
        secondary_button("Delete", type="button", on_click=ExperienceState.ask_delete(row["key"]), style=_SMALL_BUTTON),
        style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap", "margin_left": "auto"},
    )


def _achievement(row: rx.Var) -> rx.Component:
    """An achievement at rest: arrows, tag, text and its actions, or the delete question."""
    confirming = ExperienceState.confirming_key == row["key"]
    return rx.el.div(
        rx.el.div(
            _move_button("chevron_up", "Move up", -1, row, disabled=row["first"] == "yes"),
            _move_button("chevron_down", "Move down", 1, row, disabled=row["last"] == "yes"),
            style={"display": "flex", "flex_direction": "column", "gap": "0.25rem", "flex": "0 0 auto"},
        ),
        rx.el.div(
            rx.el.div(
                _origin_tag(row["origin"]),
                rx.el.p(
                    row["text"],
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.55",
                        "color": TEXT,
                        "min_width": "0",
                        "overflow_wrap": "break-word",
                    },
                ),
                style={"display": "flex", "align_items": "baseline", "gap": "0.625rem"},
            ),
            rx.cond(confirming, _confirmation(row), rx.fragment()),
            # 12rem and not more: at 390px the text has to fit next to the arrows, and the
            # actions are what wraps to the next line.
            style={"flex": "1 1 12rem", "min_width": "0"},
        ),
        rx.cond(confirming, rx.fragment(), _actions(row)),
        style={
            "display": "flex",
            "align_items": "flex-start",
            "flex_wrap": "wrap",
            "gap": "0.75rem",
            "padding": "0.625rem 0 0.625rem 1.5rem",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


def _editor(row: rx.Var) -> rx.Component:
    """The achievement opened in place, with LinkedIn's text below when it has one.

    A rejected save leaves it open with what you typed, so you can fix it.
    """
    return _form_box(
        rx.el.div(_origin_tag(row["origin"]), style={"display": "flex", "margin_bottom": "0.5rem"}),
        _textarea(
            default_value=row["text"],
            aria_label="Achievement text",
            key=row["key"],
        ),
        rx.cond(
            row["linkedin_text"] != "",
            note_text(
                "LinkedIn says: " + row["linkedin_text"],
                style={"display": "block", "margin_top": "0.375rem"},
            ),
            rx.fragment(),
        ),
        _form_error(),
        _form_buttons(
            "Save",
            ExperienceState.cancel_edit,
            rx.cond(
                row["origin"] == "edited",
                secondary_button(
                    "Restore LinkedIn text",
                    type="button",
                    on_click=ExperienceState.restore(row["key"]),
                    style=_SMALL_BUTTON,
                ),
                rx.fragment(),
            ),
        ),
        on_submit=ExperienceState.save_edit,
    )


# --- Add -------------------------------------------------------------------------


def _add(row: rx.Var) -> rx.Component:
    """The end of a job: the button, or the form it opens. What you add is yours and goes last."""
    return rx.cond(
        ExperienceState.adding_to == row["experience_id"],
        _form_box(
            _textarea(placeholder="What did you do, and what came of it?", aria_label="New achievement"),
            _form_error(),
            _form_buttons("Add", ExperienceState.cancel_add),
            on_submit=ExperienceState.add,
        ),
        rx.el.div(
            secondary_button(
                "+ Add achievement",
                type="button",
                on_click=ExperienceState.start_add(row["experience_id"]),
                style=_SMALL_BUTTON,
            ),
            style={"padding": "0.5rem 0 0.5rem 1.5rem"},
        ),
    )


def _row(row: rx.Var) -> rx.Component:
    """One row of the flat list. A job's achievements and its add row hide while it is folded.

    The `key` is the row's own and not its position, as React wants for a list that
    reorders: otherwise `foreach` keys each row by its index.
    """
    opened = ExperienceState.open_jobs[row["experience_id"]]
    return rx.fragment(
        rx.match(
            row["row"],
            ("job", _job(row)),
            (
                "achievement",
                rx.cond(
                    opened,
                    rx.cond(ExperienceState.editing_key == row["key"], _editor(row), _achievement(row)),
                    rx.fragment(),
                ),
            ),
            ("add", rx.cond(opened, _add(row), rx.fragment())),
            rx.fragment(),
        ),
        key=row["key"],
    )


def _error_notice() -> rx.Component:
    """The list's only live region: it announces every error once, wherever it is drawn.

    Above the list it draws the errors of the actions that have no form (move, duplicate)
    and of a form whose row is gone. The error of an open form is drawn inside that form,
    next to its buttons, so here it is only read out. It is not pinned to the bottom of
    the window: there it covered the buttons of an editor opened near the bottom.
    """
    return rx.el.div(
        rx.cond(
            ExperienceState.error != "",
            rx.cond(
                ExperienceState.error_in_form,
                rx.el.span(ExperienceState.error, style=_VISUALLY_HIDDEN),
                _notice(ExperienceState.error, margin_bottom="0.5rem"),
            ),
            rx.fragment(),
        ),
        aria_live="polite",
    )


def work_experience() -> rx.Component:
    """The jobs in profile order, each with its achievements. Every change saves right away."""
    return panel(
        legend("Work experience", color=AMBER),
        rx.el.p(
            "What you write here is offered to every CV you make from now on. "
            "CVs you already generated keep their own text.",
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 0.75rem",
                "line_height": "1.5",
            },
        ),
        _error_notice(),
        # Nothing until the profile is read: otherwise the empty line flashes on every load.
        rx.cond(
            ExperienceState.has_profile,
            rx.cond(
                ExperienceState.rows.length() > 0,
                rx.el.div(rx.foreach(ExperienceState.rows, _row), style={"width": "100%"}),
                note_text("There are no jobs in your profile yet. They come in from the LinkedIn sync."),
            ),
            rx.fragment(),
        ),
        style={"width": "100%", "padding": "1.5rem"},
    )
