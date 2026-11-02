"""One translatable text of My profile, in the language the switch shows.

A version that is not current says so in words, never by color alone:

    Pending translation   outlined, muted   nothing written in this language yet: the
                                            other language's text stands in for it
    Pending review        outlined, amber   written, but the other language changed after it

While pending, the other language's text goes under it as the reference
("In English: …"). "Still good" makes a version in review current as it is; "Use the
same text" copies the source text into a short field of the other language.

`translation_field` is the whole field, for the rows of a list. The pieces it is built
from (`pending_mark`, `reference_line`, `version_actions`, `translation_notes`) are for
the fields that keep a layout of their own, like the profession and a skill's name.
"""

from collections.abc import Callable

import reflex as rx

from cv_generator.app.styles import (
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    field_style,
    legend,
    note_text,
    secondary_button,
    style_legend,
    tag,
    touch_target,
)

# Compact on desktop, a finger's width on touch, like the actions of an achievement.
_SMALL_BUTTON = {"min_height": ["2.75rem", "2.75rem", "2rem"], "padding": "0 0.75rem"}

# A handler called with the row's key, such as "Still good".
OnKey = Callable[[rx.Var], rx.event.EventSpec]


def pending_mark(state: rx.Var) -> rx.Component:
    """The mark of a version that is not current. Nothing for a current one."""
    return rx.match(
        state,
        ("missing", tag("Pending translation", TEXT_MUTED)),
        ("review", tag("Pending review")),
        rx.fragment(),
    )


def reference_line(language: rx.Var | str, text: rx.Var) -> rx.Component:
    """The other language's version, to translate from or check against. Nothing without one."""
    return rx.cond(
        text != "",
        note_text("In " + language + ": " + text, style={"display": "block", "overflow_wrap": "break-word"}),
        rx.fragment(),
    )


def version_actions(
    *,
    can_confirm: rx.Var,
    on_confirm: rx.event.EventSpec,
    can_copy: rx.Var | bool = False,
    on_same: rx.event.EventSpec | None = None,
) -> rx.Component:
    """ "Still good" while `can_confirm`; "Use the same text" while `can_copy`, if given."""
    still_good = secondary_button("Still good", type="button", on_click=on_confirm, style=_SMALL_BUTTON)
    if on_same is None:
        return rx.cond(can_confirm, rx.el.div(still_good, style={"display": "flex"}), rx.fragment())
    same = secondary_button("Use the same text", type="button", on_click=on_same, style=_SMALL_BUTTON)
    return rx.cond(
        can_confirm | can_copy,
        rx.el.div(
            rx.cond(can_confirm, still_good, rx.fragment()),
            rx.cond(can_copy, same, rx.fragment()),
            style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap"},
        ),
        rx.fragment(),
    )


def _row_actions(row: rx.Var, on_confirm: OnKey, on_same: OnKey | None) -> rx.Component:
    return version_actions(
        can_confirm=row["state"] == "review",
        on_confirm=on_confirm(row["key"]),
        can_copy=row["copyable"] == "yes",
        on_same=on_same(row["key"]) if on_same is not None else None,
    )


def translation_notes(row: rx.Var, *, on_confirm: OnKey, on_same: OnKey | None = None) -> rx.Component:
    """Under a field with a layout of its own: the mark, the reference and the actions.
    Nothing while the version is current."""
    return rx.cond(
        row["state"] != "",
        rx.el.div(
            rx.el.div(
                pending_mark(row["state"]),
                reference_line(row["reference_language"], row["reference"]),
                style={"display": "flex", "align_items": "baseline", "gap": "0.5rem", "flex_wrap": "wrap"},
            ),
            _row_actions(row, on_confirm, on_same),
            style={"display": "flex", "flex_direction": "column", "gap": "0.375rem"},
        ),
        rx.fragment(),
    )


def translation_field(
    row: rx.Var,
    *,
    on_save: Callable[[rx.Var, rx.Var], rx.event.EventSpec],
    on_submit: rx.event.EventHandler,
    on_confirm: OnKey,
    on_same: OnKey | None = None,
    multiline: bool = False,
) -> rx.Component:
    """A translatable text: its label and mark, the field or the read-only text, the
    reference and the actions. It works inside `rx.foreach`.

    `row` is a `dict[str, str]` Var as `profile_state.text_version` builds it (`key`,
    `text`, `own`, `state`, `reference`, `reference_language`, `copyable`), plus `label`
    and `editable` ("yes" or ""). The handlers belong to the state that owns the rows:

    - `on_save(key, text)` when leaving the field;
    - `on_submit(data)` on Enter, with `data["key"]` and `data["text"]`. The key travels
      in a hidden field: Reflex compiles `on_submit` outside the `foreach`, and a
      reference to the row there blows up in the browser;
    - `on_confirm(key)` for "Still good", on a version in review;
    - `on_same(key)` for "Use the same text", offered while `copyable`. Leave it out for
      a long text: that one is translated, not copied.

    `multiline` makes the field a textarea. The field is uncontrolled: it starts from
    `own`, empty while missing, and saves when you leave it. Its key carries the saved
    text, the state and the language, so a save or a switch draws it again from the row.
    A read-only text that is empty shows nothing at all: there is nothing to translate.
    """
    editable = row["editable"] == "yes"
    field_id = "translation-" + row["key"]
    props = {
        "id": field_id,
        "name": "text",
        "default_value": row["own"],
        "on_blur": lambda text: on_save(row["key"], text),
    }
    field = (
        rx.el.textarea(rows="3", **props, style={**field_style(), "resize": "vertical", "line_height": "1.55"})
        if multiline
        else rx.el.input(**props, style={**field_style(), **touch_target()})
    )
    return rx.cond(
        editable | (row["text"] != ""),
        rx.el.div(
            rx.el.div(
                rx.cond(
                    editable,
                    rx.el.label(row["label"], html_for=field_id, style=style_legend(TEXT_FAINT)),
                    legend(row["label"], color=TEXT_FAINT),
                ),
                pending_mark(row["state"]),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem", "flex_wrap": "wrap"},
            ),
            rx.cond(
                editable,
                rx.el.form(
                    rx.el.input(type="hidden", name="key", value=row["key"]),
                    field,
                    on_submit=on_submit,
                    key=row["key"] + "|" + row["reference_language"] + "|" + row["state"] + "|" + row["own"],
                ),
                rx.el.p(
                    row["text"],
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.55",
                        # The fallback reads fainter, and its mark says why.
                        "color": rx.cond(row["state"] == "missing", TEXT_FAINT, TEXT),
                        "overflow_wrap": "break-word",
                    },
                ),
            ),
            reference_line(row["reference_language"], row["reference"]),
            _row_actions(row, on_confirm, on_same),
            style={"display": "flex", "flex_direction": "column", "gap": "0.375rem", "width": "100%", "min_width": "0"},
        ),
        rx.fragment(),
    )
