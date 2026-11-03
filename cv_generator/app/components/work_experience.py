"""The Work experience subsection of My profile: the achievements of each job, editable.

Each achievement wears a tag that says where it stands against LinkedIn:

    LinkedIn   outlined, muted    the text LinkedIn brought, untouched
    Edited     outlined, amber    you rewrote it; "LinkedIn says" keeps the original
    Yours      solid amber        you wrote it, or it is a copy: the sync never touches it

The tag is a word and not only a tone, the same law as the rails. It describes the text
LinkedIn feeds, so it shows in that language only; in the other one the achievement wears
its pending mark, if any (see `translation_field`).

The company and dates of a job are read-only: they come from LinkedIn. So are its role
and location in the language LinkedIn feeds; in the other one they are translated here.
"""

import reflex as rx

from cv_generator.app.components.translation_field import (
    pending_mark,
    reference_line,
    translation_field,
    version_actions,
)
from cv_generator.app.states.experience_state import JOB_FIELDS, ExperienceState
from cv_generator.app.styles import (
    AMBER,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    VISUALLY_HIDDEN,
    error_notice,
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


def _origin_tag(origin: rx.Var) -> rx.Component:
    return rx.match(
        origin,
        ("linkedin", tag("LinkedIn", TEXT_MUTED)),
        ("edited", tag("Edited")),
        ("yours", tag("Yours", solid=True)),
        rx.fragment(),
    )


def _textarea(key: rx.Var, saved_text: rx.Var | str, **props: object) -> rx.Component:
    """No `value=`: the field governs itself and the text travels when the form is sent.

    It also travels as a draft: when you leave the field, which arrives before the click
    that closes the form, and half a second after you stop typing, for Back with a
    gesture or a reload. It opens with that draft when there is one.
    """
    return rx.el.textarea(
        name="text",
        rows="3",
        auto_focus=True,
        default_value=rx.cond(ExperienceState.drafts.contains(key), ExperienceState.drafts[key], saved_text),
        on_blur=lambda text: ExperienceState.keep_draft(key, text),
        on_change=lambda text: ExperienceState.keep_draft(key, text).debounce(500),
        style={**field_style(), "resize": "vertical", "line_height": "1.55"},
        **props,
    )


def _draft_note(key: rx.Var, text: str) -> rx.Component:
    """Says that a closed form keeps something you typed and did not save."""
    return rx.cond(
        ExperienceState.drafts.contains(key),
        note_text(text, color=AMBER, style={"display": "block", "margin_top": "0.375rem"}),
        rx.fragment(),
    )


def _held_draft_note(key: rx.Var, what: str) -> rx.Component:
    """Says that a language not on screen holds something you typed here and did not send.

    It names that language by its code, like Contact's unsaved mark: the switch is the way
    back to it.
    """
    codes = ExperienceState.held_draft_languages[key]
    return rx.cond(
        ExperienceState.held_draft_languages.contains(key),
        note_text(
            what + " in " + codes + ". Switch to " + codes + " to finish it.",
            color=AMBER,
            style={"display": "block", "margin_top": "0.375rem"},
        ),
        rx.fragment(),
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


def _row_error(row: rx.Var) -> rx.Component:
    """The error of this row's action, where the eye already is: inside its open form, right
    above the buttons, or under the achievement for move and duplicate.

    It is not a live region: `_error_notice` announces it, once.
    """
    return rx.cond(
        (ExperienceState.error != "") & (ExperienceState.error_at == row["key"]),
        error_notice(ExperienceState.error, margin_top="0.625rem"),
        rx.fragment(),
    )


# --- Job -------------------------------------------------------------------------


def _job(row: rx.Var) -> rx.Component:
    """The job's heading, which folds and unfolds its achievements.

    It is one button with `aria-expanded`, so the screen reader says whether the list
    below is open. Nothing in it is editable: where the role and location can be
    translated, their fields go below it (`_job_texts`). While folded, the role's pending
    mark goes next to the role, so a text standing in for it is marked even then.
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
                rx.el.span(
                    row["role"]["text"],
                    style={
                        "font_stretch": "75%",
                        "font_weight": "700",
                        "font_size": "0.9375rem",
                        "text_transform": "uppercase",
                        "letter_spacing": "0.03em",
                        "color": TEXT,
                    },
                ),
                rx.cond(opened, rx.fragment(), pending_mark(row["role"]["state"])),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem", "flex_wrap": "wrap"},
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


def _job_texts(row: rx.Var) -> rx.Component:
    """The role and location of an unfolded job, in the language on screen.

    Short texts: "Use the same text" copies the source one.
    """
    return rx.el.div(
        *[
            translation_field(
                row[field],
                on_save=ExperienceState.save_job_field,
                on_submit=ExperienceState.job_field_from_form,
                on_confirm=ExperienceState.confirm_job_field,
                on_same=ExperienceState.same_job_field,
            )
            for field in JOB_FIELDS
        ],
        _row_error(row),
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "0.75rem",
            "padding": "0.75rem 0 0.75rem 1.5rem",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


# --- Achievement -----------------------------------------------------------------


def _marks(row: rx.Var) -> rx.Component:
    """Where the achievement stands: against LinkedIn in the language it feeds, and
    against the other language in either one."""
    return rx.fragment(
        rx.cond(ExperienceState.in_source, _origin_tag(row["origin"]), rx.fragment()),
        pending_mark(row["state"]),
    )


def _move_button(direction: str, label: str, offset: int, row: rx.Var, *, disabled: rx.Var) -> rx.Component:
    """Disabled at the ends: an active arrow that does nothing reads as broken.

    The id is what the keyboard comes back to after the move (`focus_after_move`).
    """
    return secondary_button(
        rx.icon(f"chevron_{direction}", size=13, stroke_width=1.75),
        id=f"move-{direction}-" + row["key"],
        type="button",
        on_click=ExperienceState.move(row["key"], offset),
        disabled=disabled,
        aria_label=label,
        title=label,
        style={**_SMALL_BUTTON, "min_width": ["2.75rem", "2.75rem", "2rem"], "padding": "0"},
    )


def _confirmation(row: rx.Var) -> rx.Component:
    """Delete asks first, in place. What it says depends on where the achievement came from:
    only a LinkedIn one is remembered so the sync does not offer it again.

    The keyboard lands on Cancel, the answer that loses nothing, and the group is named
    by its question, so a screen reader reads the question on the way in.
    """
    question = "confirm-" + row["key"]
    return rx.el.div(
        rx.el.p(
            "Delete this achievement? CVs you already generated keep it.",
            rx.cond(row["origin"] != "yours", " The LinkedIn sync will not offer it again.", ""),
            id=question,
            style={"font_stretch": "100%", "font_size": "0.8125rem", "color": TEXT, "line_height": "1.5"},
        ),
        _row_error(row),
        rx.el.div(
            primary_button(
                "Delete", type="button", on_click=ExperienceState.confirm_delete(row["key"]), style=_SMALL_BUTTON
            ),
            secondary_button(
                "Cancel",
                type="button",
                auto_focus=True,
                on_click=ExperienceState.cancel_delete,
                style=_SMALL_BUTTON,
            ),
            style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "margin_top": "0.5rem"},
        ),
        role="group",
        aria_labelledby=question,
        style={"border_left": f"2px solid {AMBER}", "padding": "0.25rem 0 0.25rem 0.75rem", "margin_top": "0.625rem"},
    )


def _actions(row: rx.Var) -> rx.Component:
    """The ids are what the keyboard comes back to when the editor or the question closes."""
    return rx.el.div(
        secondary_button(
            "Edit",
            id="edit-" + row["key"],
            type="button",
            on_click=ExperienceState.start_edit(row["key"]),
            style=_SMALL_BUTTON,
        ),
        secondary_button(
            "Duplicate", type="button", on_click=ExperienceState.duplicate(row["key"]), style=_SMALL_BUTTON
        ),
        secondary_button(
            "Delete",
            id="delete-" + row["key"],
            type="button",
            on_click=ExperienceState.ask_delete(row["key"]),
            style=_SMALL_BUTTON,
        ),
        style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap", "margin_left": "auto"},
    )


def _achievement(row: rx.Var) -> rx.Component:
    """An achievement at rest: arrows, tag, text and its actions, or the delete question."""
    confirming = ExperienceState.confirming_key == row["key"]
    return rx.el.div(
        rx.el.div(
            _move_button("up", "Move up", -1, row, disabled=row["first"] == "yes"),
            _move_button("down", "Move down", 1, row, disabled=row["last"] == "yes"),
            style={"display": "flex", "flex_direction": "column", "gap": "0.25rem", "flex": "0 0 auto"},
        ),
        rx.el.div(
            rx.el.div(
                _marks(row),
                rx.el.p(
                    row["text"],
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.55",
                        # The other language's text, standing in, reads fainter; its mark says why.
                        "color": rx.cond(row["state"] == "missing", TEXT_FAINT, TEXT),
                        "min_width": "0",
                        "overflow_wrap": "break-word",
                    },
                ),
                style={"display": "flex", "align_items": "baseline", "gap": "0.625rem", "flex_wrap": "wrap"},
            ),
            # Only in review: while missing, the text above is already the other language's,
            # marked, and its reference would say it twice. The editor shows it either way.
            rx.cond(
                row["state"] == "review",
                rx.el.div(
                    reference_line(row["reference_language"], row["reference"]),
                    # Long texts are translated, not copied: no "Use the same text" here.
                    version_actions(
                        can_confirm=row["state"] == "review", on_confirm=ExperienceState.confirm(row["key"])
                    ),
                    style={"display": "flex", "flex_direction": "column", "gap": "0.375rem", "margin_top": "0.25rem"},
                ),
                rx.fragment(),
            ),
            _draft_note(row["key"], "You have an unsaved change here. Press Edit to finish it."),
            _held_draft_note(row["key"], "You have an unsaved change here"),
            rx.cond(confirming, _confirmation(row), _row_error(row)),
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
    """The achievement opened in place, in the language on screen.

    It starts from this language's own text: empty while it is missing, with the other
    language's below as the reference. In the language LinkedIn feeds, LinkedIn's text
    goes below too, when it has one. A rejected save leaves it open with what you typed,
    so you can fix it.
    """
    return _form_box(
        rx.cond(
            ExperienceState.in_source | (row["state"] != ""),
            rx.el.div(_marks(row), style={"display": "flex", "gap": "0.5rem", "margin_bottom": "0.5rem"}),
            rx.fragment(),
        ),
        _textarea(row["key"], row["own"], aria_label="Achievement text"),
        rx.cond(
            row["reference"] != "",
            rx.el.div(reference_line(row["reference_language"], row["reference"]), style={"margin_top": "0.375rem"}),
            rx.fragment(),
        ),
        rx.cond(
            ExperienceState.in_source & (row["linkedin_text"] != ""),
            note_text(
                "LinkedIn says: " + row["linkedin_text"],
                style={"display": "block", "margin_top": "0.375rem"},
            ),
            rx.fragment(),
        ),
        _row_error(row),
        _form_buttons(
            "Save",
            ExperienceState.cancel_edit,
            rx.cond(
                ExperienceState.in_source & (row["origin"] == "edited"),
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
            _textarea(
                row["key"], "", placeholder="What did you do, and what came of it?", aria_label="New achievement"
            ),
            _row_error(row),
            _form_buttons("Add", ExperienceState.cancel_add),
            on_submit=ExperienceState.add,
        ),
        rx.el.div(
            secondary_button(
                "+ Add achievement",
                id="add-" + row["experience_id"],
                type="button",
                on_click=ExperienceState.start_add(row["experience_id"]),
                style=_SMALL_BUTTON,
            ),
            _draft_note(row["key"], "You started a new achievement here. Press + Add achievement to finish it."),
            _held_draft_note(row["key"], "You started a new achievement here"),
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
            ("job", rx.fragment(_job(row), rx.cond(opened, _job_texts(row), rx.fragment()))),
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

    Above the list it only draws the error of a row that is gone. The rest are drawn at
    their row (`_row_error`), so here they are only read out. It is not pinned to the
    bottom of the window: there it covered the buttons of an editor opened near the bottom.
    """
    return rx.el.div(
        rx.cond(
            ExperienceState.error != "",
            rx.cond(
                ExperienceState.error_at != "",
                rx.el.span(ExperienceState.error, style=VISUALLY_HIDDEN),
                error_notice(ExperienceState.error, margin_bottom="0.5rem"),
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
