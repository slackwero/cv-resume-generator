"""LinkedIn sync: review the normals before touching them.

Three phases, and the middle one is the heart of the product: nothing is written until
you decide what goes in. The conflict dialog names the text that gets lost instead of
warning in the abstract, and that is kept as is — it was the best thing the previous
interface had.
"""

import reflex as rx

from cv_generator.app.components.header import data_cell, data_group, legend_strip, page
from cv_generator.app.components.sync_diff import change_list, changes_summary
from cv_generator.app.states.sync_state import (
    PHASE_APPLIED,
    PHASE_CHOOSE,
    PHASE_REVIEW,
    UPLOAD_ID,
    SyncState,
)
from cv_generator.app.styles import (
    AMBER,
    CONFLICT,
    GLASS,
    GLASS_ETCHED,
    JOINED,
    PROPOSAL,
    RULE_LINE,
    RULE_LINE_STRONG,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    error_notice,
    legend,
    note_text,
    primary_button,
    rail,
    secondary_button,
    touch_target,
)


def _note(text: str, icon_name: str = "info") -> rx.Component:
    return rx.el.div(
        rx.icon(
            icon_name, size=15, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto", "margin_top": "0.125rem"}
        ),
        rx.el.p(
            text,
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_FAINT,
                "line_height": "1.55",
                "max_width": "72ch",
            },
        ),
        style={
            "display": "flex",
            "gap": "0.75rem",
            "align_items": "flex-start",
            "border": f"1px solid {RULE_LINE}",
            "padding": "0.875rem 1rem",
            "width": "100%",
        },
    )


# --- Phase 1: choose the file ----------------------------------------------------


def _choose_step() -> rx.Component:
    return rx.el.div(
        _note(
            "Upload the LinkedIn ZIP export (Settings › Data privacy › Get a copy of "
            "your data) or your profile PDF (More › Save to PDF). The ZIP brings "
            "structured data and is more reliable. Nothing is applied until you "
            "review the changes."
        ),
        rx.upload(
            rx.el.div(
                rx.icon("upload", size=24, stroke_width=1.5, style={"color": AMBER}),
                rx.el.p(
                    "Drop the LinkedIn ZIP or PDF here",
                    style={
                        "font_stretch": "85%",
                        "font_weight": "600",
                        "font_size": "1rem",
                        "color": TEXT,
                        "margin_top": "0.875rem",
                    },
                ),
                legend("Or click to choose it", style={"margin_top": "0.375rem", "display": "block"}),
                style={"display": "flex", "flex_direction": "column", "align_items": "center", "text_align": "center"},
            ),
            id=UPLOAD_ID,
            max_files=1,
            accept={"application/pdf": [".pdf"], "application/zip": [".zip"]},
            # The input[type=file] stays hidden behind the box and rx.upload exposes no prop to
            # name it. What receives focus and keyboard is this container (react-dropzone gives it
            # tabIndex=0), so the accessible name goes here.
            custom_attrs={
                "role": "button",
                "aria-label": "Choose the LinkedIn ZIP export or PDF",
            },
            border=f"1px dashed {RULE_LINE_STRONG}",
            border_radius="0",
            padding="3.5rem 1.5rem",
            width="100%",
            background=GLASS_ETCHED,
        ),
        rx.el.div(
            # Only the file name, and only if there is one. With `.to_string()` on the empty list,
            # the screen printed a loose "[]" before anything was chosen.
            rx.cond(
                rx.selected_files(UPLOAD_ID).length() > 0,
                note_text(rx.selected_files(UPLOAD_ID).join(", "), color=TEXT_FAINT),
                rx.fragment(),
            ),
            rx.el.div(style={"flex": "1 1 auto"}),
            primary_button(
                rx.icon("search", size=15, stroke_width=2),
                rx.cond(SyncState.analyzing, "Reading the file…", "Analyze changes"),
                on_click=SyncState.process_file(rx.upload_files(upload_id=UPLOAD_ID)),
                disabled=SyncState.analyzing,
                style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem"},
            ),
            style={"display": "flex", "align_items": "center", "gap": "1rem", "flex_wrap": "wrap", "width": "100%"},
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.25rem", "width": "100%"},
    )


# --- Phase 2: review -------------------------------------------------------------


def _conflict(text: rx.Var) -> rx.Component:
    return rx.el.li(
        rail(CONFLICT, style={"max_width": "2.5rem", "flex": "0 0 auto"}),
        rx.el.span(
            text,
            style={"font_stretch": "100%", "font_size": "0.8125rem", "color": TEXT_FAINT, "line_height": "1.5"},
        ),
        style={
            "display": "flex",
            "gap": "0.625rem",
            "align_items": "flex-start",
            "list_style": "none",
            "padding": "0.5rem 0",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


def _apply_button(**props: object) -> rx.Component:
    """The apply button. Without `on_click` when the confirmation dialog wraps it, since
    the dialog fires the action from its own button."""
    return primary_button(
        "Apply ",
        SyncState.accepted_total.to_string(),
        rx.cond(SyncState.accepted_total == 1, " change", " changes"),
        disabled=(SyncState.accepted_total == 0) | SyncState.applying,
        style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem"},
        **props,
    )


def _confirm_conflicts() -> rx.Component:
    """Before replacing your own text, it names exactly which text gets lost.

    It only appears when there are accepted conflicts: new items destroy nothing, and
    asking for confirmation for them would train the user to close the dialog unread.
    """
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(_apply_button()),
        rx.alert_dialog.content(
            rx.alert_dialog.title(
                rx.el.span(
                    "You are about to replace text you wrote yourself",
                    style={
                        "font_stretch": "62%",
                        "font_weight": "800",
                        "font_size": "1.5rem",
                        "text_transform": "uppercase",
                        "letter_spacing": "-0.01em",
                        "color": AMBER,
                        "line_height": "1.05",
                        "display": "block",
                    },
                ),
            ),
            rx.alert_dialog.description(
                rx.el.span(
                    "",
                    SyncState.accepted_conflicts_total.to_string(),
                    rx.cond(
                        SyncState.accepted_conflicts_total == 1,
                        " text will be replaced with what LinkedIn says:",
                        " texts will be replaced with what LinkedIn says:",
                    ),
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "color": TEXT_FAINT,
                        "line_height": "1.55",
                        "display": "block",
                        "margin_top": "0.75rem",
                    },
                ),
            ),
            rx.el.ul(
                rx.foreach(SyncState.accepted_conflicts, _conflict),
                style={
                    "margin": "1rem 0",
                    "padding": "0 1rem",
                    "list_style": "none",
                    "max_height": "240px",
                    "overflow_y": "auto",
                    "border": f"1px solid {RULE_LINE}",
                    "background": GLASS,
                },
            ),
            legend(
                "A copy of your profile is saved before writing, and you can undo it from the next screen.",
                color=TEXT_MUTED,
                style={"display": "block", "line_height": "1.5", "text_transform": "none", "letter_spacing": "0.04em"},
            ),
            rx.el.div(
                rx.el.div(style={"flex": "1 1 auto"}),
                rx.alert_dialog.cancel(
                    secondary_button("Back to review", style={**touch_target(), "min_height": "2.75rem"}),
                ),
                rx.alert_dialog.action(
                    primary_button(
                        "Replace and apply",
                        on_click=SyncState.apply,
                        style={**touch_target(), "min_height": "2.75rem"},
                    ),
                ),
                style={"display": "flex", "gap": "0.5rem", "margin_top": "1.25rem", "flex_wrap": "wrap"},
            ),
            max_width="36rem",
            style={"background": GLASS_ETCHED, "border": f"1px solid {AMBER}", "border_radius": "0"},
        ),
    )


def _review_step() -> rx.Component:
    return rx.el.div(
        changes_summary(),
        rx.cond(
            SyncState.conflict_count > 0,
            _note(
                "Conflicts arrive unchecked on purpose: they are achievements you rewrote "
                "by hand that also changed on LinkedIn. Accepting them replaces your text.",
                "triangle_alert",
            ),
            rx.fragment(),
        ),
        change_list(),
        rx.cond(
            SyncState.nothing_to_do,
            rx.fragment(),
            rx.el.div(
                rx.el.div(style={"flex": "1 1 auto"}),
                rx.cond(
                    SyncState.has_accepted_conflicts,
                    _confirm_conflicts(),
                    _apply_button(on_click=SyncState.apply),
                ),
                style={
                    "display": "flex",
                    "width": "100%",
                    "border_top": f"1px solid {RULE_LINE}",
                    "padding_top": "1.5rem",
                },
            ),
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.5rem", "width": "100%"},
    )


# --- Phase 3: applied ------------------------------------------------------------


def _undo_sync() -> rx.Component:
    """The way back the conflict dialog promises.

    It asks for confirmation because restoring discards the sync just applied: it is
    symmetrical to the dialog shown to apply it.
    """
    return rx.el.div(
        note_text("Your previous profile was saved in data/" + SyncState.backup_path, color=TEXT_MUTED),
        rx.el.div(style={"flex": "1 1 auto"}),
        # Once refused it would only refuse again: the profile changed after the sync.
        rx.cond(SyncState.undo_refused, rx.fragment(), _undo_dialog()),
        style={"display": "flex", "align_items": "center", "gap": "1rem", "flex_wrap": "wrap", "width": "100%"},
    )


def _undo_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            secondary_button(
                rx.icon("undo_2", size=13, stroke_width=1.75),
                "Undo",
                disabled=SyncState.undoing,
                style={
                    **touch_target(),
                    "min_height": "2.25rem",
                    "padding": "0 0.75rem",
                    "font_size": "0.625rem",
                },
            ),
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title(
                rx.el.span(
                    "Undo this sync",
                    style={
                        "font_stretch": "62%",
                        "font_weight": "800",
                        "font_size": "1.5rem",
                        "text_transform": "uppercase",
                        "letter_spacing": "-0.01em",
                        "color": AMBER,
                        "line_height": "1.05",
                        "display": "block",
                    },
                ),
            ),
            rx.alert_dialog.description(
                rx.el.span(
                    "Your profile will go back to how it was before applying these changes. What "
                    "LinkedIn brought is discarded, and you can sync again whenever you want.",
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "color": TEXT_FAINT,
                        "line_height": "1.55",
                        "display": "block",
                        "margin_top": "0.75rem",
                    },
                ),
            ),
            rx.el.div(
                rx.el.div(style={"flex": "1 1 auto"}),
                rx.alert_dialog.cancel(
                    secondary_button("Leave it as it is", style={**touch_target(), "min_height": "2.75rem"}),
                ),
                rx.alert_dialog.action(
                    primary_button(
                        "Undo",
                        on_click=SyncState.undo,
                        style={**touch_target(), "min_height": "2.75rem"},
                    ),
                ),
                style={"display": "flex", "gap": "0.5rem", "margin_top": "1.5rem", "flex_wrap": "wrap"},
            ),
            max_width="32rem",
            style={"background": GLASS_ETCHED, "border": f"1px solid {AMBER}", "border_radius": "0"},
        ),
    )


def _applied_step() -> rx.Component:
    return rx.el.div(
        # The result goes in a panel with a rule, not in a full-width solid plate. The plate
        # belongs to the primary action and there can only be one per screen; a solid banner
        # confirming something already done competed with it without being clickable.
        rx.el.div(
            rail(JOINED, style={"max_width": "4rem", "flex": "0 0 auto"}),
            rx.el.span(
                SyncState.result_summary,
                style={
                    "font_stretch": "100%",
                    "font_size": "0.9375rem",
                    "font_weight": "600",
                    "color": TEXT,
                    "line_height": "1.5",
                },
            ),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "0.875rem",
                "flex_wrap": "wrap",
                "border": f"1px solid {RULE_LINE}",
                "border_left": f"2px solid {AMBER}",
                "background": GLASS_ETCHED,
                "padding": "1rem 1.125rem",
                "width": "100%",
            },
        ),
        rx.cond(
            (SyncState.backup_path != "") & ~SyncState.undone,
            _undo_sync(),
            rx.fragment(),
        ),
        rx.el.div(
            secondary_button(
                "Back to the home page",
                on_click=SyncState.back_to_home,
                style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
            ),
            secondary_button(
                "Review my profile",
                on_click=SyncState.go_to_profile,
                style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
            ),
            secondary_button(
                "Sync again",
                on_click=SyncState.start,
                style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
            ),
            style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap"},
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.5rem", "width": "100%"},
    )


# --- The strip: the scheme's legend ----------------------------------------------


def _direction(status: str, title: str, explanation: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rail(status, style={"max_width": "3rem", "flex": "0 0 auto"}),
            legend(title, color=TEXT),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
        ),
        rx.el.p(
            explanation,
            style={
                "font_stretch": "100%",
                "font_size": "0.75rem",
                "color": TEXT_MUTED,
                "line_height": "1.45",
                "margin_top": "0.25rem",
            },
        ),
    )


def _strip() -> rx.Component:
    """The reconciliation legend, printed at the side like in any scheme.

    It is the README's four-case table, drawn. Without it the stroke pattern has to be
    guessed, and a scheme without a legend is not a scheme.
    """
    return rx.fragment(
        rx.el.div(
            legend("How it reconciles"),
            rx.el.p(
                "Syncing never overwrites or deletes: it proposes and you decide. Each achievement "
                "keeps the text as it came from LinkedIn, and these four cases come from that.",
                style={
                    "font_stretch": "100%",
                    "font_size": "0.8125rem",
                    "color": TEXT_FAINT,
                    "line_height": "1.55",
                    "margin_top": "0.625rem",
                },
            ),
            style={"border_bottom": f"1px solid {RULE_LINE}", "padding_bottom": "1.25rem"},
        ),
        rx.el.div(
            _direction(JOINED, "Unchanged", "Your text and LinkedIn's match."),
            _direction(PROPOSAL, "Proposed", "LinkedIn brings something different, or something new."),
            _direction(CONFLICT, "Conflict", "It changed on both sides. It arrives unchecked."),
            # The "you broke it" pattern is NOT shown here.
            #
            # That case —you edited it by hand and it did not change on LinkedIn— is precisely a
            # NON-change: nothing is proposed, so it never appears as a row on this screen. The
            # previous legend showed it anyway, promising a stroke the diff cannot draw. A legend
            # only shows what its scheme draws. The pattern is still alive where it is visible: in
            # My profile.
            style={"display": "flex", "flex_direction": "column", "gap": "0.875rem"},
        ),
    )


def sync_page() -> rx.Component:
    """LinkedIn sync screen."""
    return page(
        "Sync with LinkedIn",
        "Bring in what is on your LinkedIn profile and decide what goes in. Nothing is written until you approve it.",
        rx.cond(SyncState.notice != "", _note(SyncState.notice), rx.fragment()),
        rx.cond(SyncState.error_message != "", error_notice(SyncState.error_message), rx.fragment()),
        rx.match(
            SyncState.phase,
            (PHASE_CHOOSE, _choose_step()),
            (PHASE_REVIEW, _review_step()),
            (PHASE_APPLIED, _applied_step()),
            _choose_step(),
        ),
        strip=legend_strip(_strip()),
        data=data_group(
            data_cell(
                "Phase",
                rx.match(
                    SyncState.phase,
                    (PHASE_CHOOSE, "Choose file"),
                    (PHASE_REVIEW, "Review"),
                    (PHASE_APPLIED, "Applied"),
                    "Choose file",
                ),
            ),
        ),
    )
