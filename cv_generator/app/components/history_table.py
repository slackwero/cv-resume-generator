"""The CV history, drawn as the jackfield's scheme of rails.

Every CV sent is a numbered rail. The number is not ornament: the state assigns it once,
by age, over the FULL list —your first CV is rail 01 and stays that way—, it holds when
filtering, and each row carries its `id`, so `#rail-01` is a link that works.

The link rail is NOT drawn here, even though it is this world's emblem. It was there,
and it only repeated what the status cell already said in words: active or archived. A
drawing that duplicates the word next to it is decoration. Tying it to something worth
it —whether the frozen text still matches today's profile— needed data the history does
not keep, and that data is not made up. The rail lives where it says something words do
not say better: My profile, the wizard and the reconciliation.

Every row carries the same fixed furniture (role, template, language, date, file and
whether it was checked against the posting). None is shown bare: the 2026-08-28
critique found that six months later a row did not say what the CV contained.
"""

import reflex as rx

from cv_generator.app.states.home_state import HomeState
from cv_generator.app.styles import (
    AMBER,
    AMBER_INACTIVE,
    BROKEN,
    GLASS,
    GLASS_ETCHED,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    field_style,
    figure,
    legend,
    rail,
    secondary_button,
    status_mark,
    style_legend,
    touch_target,
)

# The scheme grid. The tracks are FIXED on purpose, with no loose `auto` or `fr`: the
# header and the rows are independent grids, and two different grids with `auto` tracks
# each size themselves by THEIR content, so they never line up. With these measures both
# compute the same and the columns really line up.
#
# `4rem` in the first one is what the "RAIL" label takes without wrapping onto two lines.
_GRID = [
    "2.5rem minmax(0, 1fr)",
    "2.5rem minmax(0, 1fr)",
    "2.5rem minmax(0, 1fr)",
    "4rem minmax(0, 1fr) 7.5rem",
]


def _action(icon_name: str, label: str, **props: object) -> rx.Component:
    """Row action: compact outline that inverts on hover."""
    return secondary_button(
        rx.icon(icon_name, size=13, stroke_width=1.75),
        rx.el.span(label, style={"display": ["none", "none", "none", "inline"]}),
        style={
            "min_height": "2.25rem",
            "padding": "0 0.625rem",
            "font_size": "0.625rem",
            **touch_target(),
        },
        **props,
    )


def _exception(cv: rx.Var, archived: rx.Var) -> rx.Component:
    """The exception row: when you took it off the list and why.

    It is the only place in the product where "it stays broken" is seen AT REST. The
    other broken rails only appear while you decide something — when syncing, when
    choosing achievements. An archived CV is a broken normal that has been like that for
    months, and until now the row said neither when nor why.

    The reason is written here and not in a dialog up front: archiving is reversible,
    and this product saves its ceremony for what is not.
    """
    return rx.cond(
        archived,
        rx.el.div(
            rx.el.div(
                rail(BROKEN, style={"max_width": "3rem", "flex": "0 0 auto"}),
                legend("Off the list", color=AMBER),
                rx.cond(
                    cv["archived_at"] != "",
                    legend("since " + cv["archived_at"], color=TEXT_MUTED),
                    rx.fragment(),
                ),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem", "flex_wrap": "wrap"},
            ),
            rx.el.input(
                # No `value=`: the field governs itself and only writes to disk when you leave it.
                # With `value` it would have to save on every keystroke, or keep a draft per row for
                # something that is written once and never touched again.
                default_value=cv["reason"],
                placeholder="Why did you archive it? (optional)",
                on_blur=lambda text: HomeState.note_reason(cv["cv_id"], text),
                aria_label="Reason you archived this CV",
                style={
                    **field_style(),
                    "margin_top": "0.5rem",
                    "font_size": "0.8125rem",
                    "min_height": "2.25rem",
                    "max_width": "38rem",
                },
            ),
            style={
                "border_left": f"1px solid {RULE_LINE}",
                "padding_left": "0.75rem",
                "margin_top": "0.625rem",
            },
        ),
        rx.fragment(),
    )


def _free_rail(number: rx.Var) -> rx.Component:
    """A labeled, unused rail.

    It is not a made-up row: numbering goes by age, so the next CV you generate will
    literally take this number. It stays out of the accessibility tree because there is
    nothing to announce — it is the scheme's ruler, not a record.
    """
    return rx.el.li(
        rx.el.span(number, style=figure("1.5rem", AMBER_INACTIVE)),
        rx.el.span(style={"flex": "1 1 auto", "border_top": f"1px solid {RULE_LINE}", "opacity": "0.5"}),
        aria_hidden="true",
        style={
            "display": "flex",
            "align_items": "center",
            "gap": "1rem",
            "padding": "0.625rem 1.125rem",
            "border_bottom": f"1px solid {RULE_LINE}",
            "list_style": "none",
        },
    )


def _row(cv: rx.Var) -> rx.Component:
    archived = cv["archived"] != ""
    # The number comes from the state, assigned once over the full list by age. It is not
    # derived from the position in this list: the list is filtered, and a number that
    # changes when typing in the search box is no use as an anchor.
    number = cv["rail"]

    furniture = rx.el.div(
        legend(cv["template"].upper(), color=TEXT_FAINT),
        legend("·"),
        legend(cv["language"]),
        legend("·"),
        legend(cv["date"]),
        legend("·"),
        rx.cond(
            cv["posting"] != "",
            legend("Checked against the posting", color=TEXT_FAINT),
            legend("No posting"),
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "gap": "0.5rem",
            "flex_wrap": "wrap",
            "margin_top": "0.375rem",
        },
    )

    actions = rx.el.div(
        _action(
            "file_text",
            "Open",
            on_click=HomeState.open_pdf(cv["path"]),
            title="Opens the PDF exactly as it was sent",
        ),
        _action(
            "refresh_cw",
            "Regenerate",
            on_click=HomeState.regenerate(cv["cv_id"]),
            disabled=HomeState.regenerating != "",
            title="Rebuilds the PDF identical to the one you sent, with its original date",
        ),
        _action(
            "copy",
            "Clone",
            on_click=HomeState.clone(cv["cv_id"]),
            title="Starts a new CV from this one",
        ),
        _action(
            rx.cond(archived, "archive_restore", "archive"),
            rx.cond(archived, "Restore", "Archive"),
            on_click=HomeState.archive(cv["cv_id"], ~archived),
            aria_label=rx.cond(archived, "Back to the list", "Archive"),
            title=rx.cond(
                archived,
                "Puts it back on the list",
                "Hides it from the list. The PDF and the record are not touched.",
            ),
        ),
        style={"display": "flex", "gap": "0.375rem", "flex_wrap": "wrap", "flex": "0 0 auto"},
    )

    return rx.el.li(
        # Top line: what identifies the application and what state it is in. It is the one
        # that lines up with the scheme header, so it uses the fixed-track grid.
        rx.el.div(
            # The anchor. Tabular and condensed, like every figure compared vertically.
            rx.el.span(number, style=figure("1.5rem", rx.cond(archived, TEXT_MUTED, AMBER))),
            rx.el.div(
                rx.el.span(
                    cv["name"],
                    style={
                        "font_stretch": "85%",
                        "font_weight": "600",
                        "font_size": "1rem",
                        "color": rx.cond(archived, TEXT_MUTED, TEXT),
                        "line_height": "1.25",
                        "display": "block",
                    },
                ),
                rx.el.span(
                    cv["role"],
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.8125rem",
                        "color": TEXT_FAINT,
                        "display": "block",
                        "margin_top": "0.125rem",
                    },
                ),
                # The furniture and the file name live HERE, in the title column. They were on the line
                # below because they competed with the title for width and split it into three lines;
                # when the link column was removed, that width became free and the row read as two
                # blocks with a 450px void in the middle. Now that gap is exactly where it goes.
                furniture,
                rx.el.span(
                    cv["file"],
                    style={
                        **style_legend(TEXT_MUTED),
                        "font_size": "0.625rem",
                        "letter_spacing": "0.06em",
                        "text_transform": "none",
                        "display": "block",
                        "margin_top": "0.375rem",
                        "overflow_wrap": "anywhere",
                    },
                ),
                _exception(cv, archived),
                style={"min_width": "0"},
            ),
            # A link rail does NOT go here, and it is deliberate.
            #
            # It was there, and it said exactly the same as the status cell next to it: whether the
            # row is active or archived. A drawing that only repeats the word next to it is
            # decoration, even if it is the house drawing. And tying it to something more honest —
            # whether the frozen text still matches today's profile — would require data the
            # history does not keep.
            #
            # The rail stays where it has something to say that words do not say better: in
            # /profile, in the wizard and in the reconciliation.
            status_mark(
                rx.cond(archived, "Archived", "On the list"),
                on=~archived,
                style={
                    "grid_column": ["1 / -1", "1 / -1", "1 / -1", "auto"],
                    "justify_self": "start",
                    "margin_top": ["0.625rem", "0.625rem", "0.625rem", "0"],
                },
            ),
            style={
                "display": "grid",
                "grid_template_columns": _GRID,
                # Top and not centered: the title column is now the tallest, and the rail number must
                # sit at the height of the name, not float mid-row.
                "align_items": "start",
                "gap": "0 1rem",
                "width": "100%",
            },
        ),
        # Bottom line: only the actions, aligned right under the title column.
        rx.el.div(
            rx.el.div(style={"flex": "1 1 auto"}),
            actions,
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "1rem",
                "flex_wrap": "wrap",
                "width": "100%",
                "margin_top": "0.75rem",
                "padding_left": ["0", "0", "0", "5rem"],
            },
        ),
        # The real anchor: the visible number is linkable, `#rail-01`. Without this the number
        # was an ornament shaped like a reference.
        id="rail-" + number,
        style={
            "padding": "1rem 1.125rem",
            "border_bottom": f"1px solid {RULE_LINE}",
            "list_style": "none",
            "background": rx.cond(archived, "transparent", GLASS_ETCHED),
            "scroll_margin_top": "6rem",
            "&:last-child": {"border_bottom": "none"},
        },
    )


def _outline_header() -> rx.Component:
    """The scheme's legend row. Desktop only: stacked, it means nothing."""
    return rx.el.div(
        legend("Rail", style={"white_space": "nowrap"}),
        legend("Application"),
        legend("Status"),
        style={
            "display": ["none", "none", "none", "grid"],
            # The same fixed-track string the rows use, so they line up.
            "grid_template_columns": _GRID[3],
            "gap": "0 1rem",
            "padding": "0.625rem 1.125rem",
            "border_bottom": f"1px solid {RULE_LINE}",
            "align_items": "center",
        },
    )


def _empty() -> rx.Component:
    """Empty state that names the real next step.

    With a profile, the next step is generating; without one, generating is out of reach
    and promising it here contradicts the header button, which leads to importing.
    """
    return rx.el.div(
        rx.el.p(
            "The scheme is empty",
            style={
                "font_stretch": "62%",
                "font_weight": "800",
                "font_size": "1.75rem",
                "text_transform": "uppercase",
                "letter_spacing": "-0.01em",
                "color": AMBER,
                "margin_bottom": "0.75rem",
            },
        ),
        rx.cond(
            HomeState.has_profile,
            rx.el.p(
                "You have not generated any CV yet. Generate the first one and it will stay here "
                "as rail 01, with what you sent frozen inside.",
                style={"color": TEXT_FAINT, "max_width": "52ch", "line_height": "1.55"},
            ),
            rx.el.p(
                "There is no profile to start from yet. Import yours from LinkedIn and, "
                "from then on, every CV you generate will open its own rail here.",
                style={"color": TEXT_FAINT, "max_width": "52ch", "line_height": "1.55"},
            ),
        ),
        style={
            "border": f"1px dashed {RULE_LINE}",
            "padding": "3rem 1.5rem",
            "text_align": "left",
        },
    )


def _search_box() -> rx.Component:
    """Filters the history by name, role or template.

    Without this, from the twenty-fifth application on the scheme is a wall of scroll
    where "the Northwind one" can no longer be found.
    """
    return rx.el.div(
        rx.el.div(
            rx.icon(
                "search",
                size=15,
                stroke_width=1.75,
                style={
                    "position": "absolute",
                    "left": "0.75rem",
                    "top": "50%",
                    "transform": "translateY(-50%)",
                    "color": TEXT_MUTED,
                },
            ),
            rx.el.input(
                placeholder="Search by name, role or template",
                value=HomeState.search_query,
                on_change=HomeState.search,
                aria_label="Search the history",
                style={**field_style(), "padding_left": "2.25rem"},
            ),
            style={"position": "relative", "flex": "1 1 20rem", "max_width": "26rem", "min_width": "0"},
        ),
        rx.cond(
            HomeState.has_search,
            rx.el.div(
                legend(HomeState.search_summary, color=TEXT_FAINT),
                secondary_button(
                    "Clear",
                    on_click=HomeState.clear_search,
                    style={"min_height": "2.25rem", "padding": "0 0.75rem", "font_size": "0.625rem"},
                ),
                style={"display": "flex", "align_items": "center", "gap": "0.625rem"},
            ),
            rx.fragment(),
        ),
        rx.el.div(style={"flex": "1 1 auto"}),
        # The toggle only exists if something is archived: with nothing archived, offering it
        # forces understanding a concept that is not needed yet.
        rx.cond(
            HomeState.has_archived,
            rx.el.label(
                rx.el.input(
                    type="checkbox",
                    checked=HomeState.show_archived,
                    on_change=HomeState.toggle_archived,
                    style={"accent_color": AMBER, "width": "1rem", "height": "1rem", "cursor": "pointer"},
                ),
                rx.el.span(HomeState.archived_summary, style=style_legend(TEXT_FAINT)),
                style={
                    **touch_target(),
                    "display": "flex",
                    "align_items": "center",
                    "gap": "0.5rem",
                    "cursor": "pointer",
                },
            ),
            rx.fragment(),
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "gap": "1rem",
            "flex_wrap": "wrap",
            "width": "100%",
        },
    )


def _no_results() -> rx.Component:
    return rx.el.p(
        "No rail matches what you are looking for.",
        style={
            **style_legend(TEXT_FAINT),
            "border": f"1px solid {RULE_LINE}",
            "padding": "0.875rem 1.125rem",
        },
    )


def history_table() -> rx.Component:
    """The scheme of rails: one CV sent per rail, from newest to oldest."""
    return rx.cond(
        HomeState.history_empty,
        _empty(),
        rx.el.div(
            _search_box(),
            rx.cond(HomeState.no_results, _no_results(), rx.fragment()),
            rx.el.div(
                _outline_header(),
                rx.el.ul(
                    rx.foreach(HomeState.visible_history, _row),
                    # The rails nobody occupies yet, labeled. They carry the scheme to the bottom so a
                    # single row reads as a scheme with room and not as a loose card, which is the
                    # scaffolding this design rejects. They disappear when searching.
                    rx.foreach(HomeState.free_rails, _free_rail),
                    style={"margin": "0", "padding": "0", "list_style": "none"},
                ),
                # The scheme's ellipsis: it says the numbering continues beyond what is drawn, which is
                # true — there is no CV cap. It only appears if there are labeled free rails before it.
                rx.cond(
                    HomeState.free_rails.length() > 0,
                    rx.el.div(
                        rx.el.span("…", style=figure("1.25rem", AMBER_INACTIVE)),
                        aria_hidden="true",
                        style={"padding": "0.5rem 1.125rem 0.875rem", "line_height": "1"},
                    ),
                    rx.fragment(),
                ),
                style={
                    "border": f"1px solid {RULE_LINE}",
                    "background": GLASS,
                    "width": "100%",
                    # A flex child starts with min-width:auto and would grow to the width of its content
                    # instead of letting it reflow.
                    "min_width": "0",
                },
            ),
            style={
                "display": "flex",
                "flex_direction": "column",
                "gap": "1.25rem",
                "width": "100%",
                "min_width": "0",
            },
        ),
    )
