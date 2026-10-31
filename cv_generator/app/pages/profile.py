"""The master profile: the personal details at the top of every CV.

Each field is an item of the scheme with its link, and the link tells the truth about
the field without resorting to color:

    required with value   -------o   tied
    required and empty    ----//-o   untied: the CV will print 'PENDING' here
    optional with value   -------o   tied
    optional and empty    ---  --o   gap: it is simply not used

The distinction matters. An empty optional field is not a problem and must not alarm;
an empty required field is a normal left untied, and it is the only reason a PDF comes
out with 'PENDING' printed inside.
"""

import reflex as rx

from cv_generator.app.components.header import data_cell, data_group, legend_strip, page
from cv_generator.app.components.work_experience import work_experience
from cv_generator.app.states.profile_state import PROFILE_SECTIONS, ProfileState
from cv_generator.app.styles import (
    AMBER,
    AMBER_INACTIVE,
    BROKEN,
    GAP,
    GLASS,
    GLASS_ETCHED,
    JOINED,
    RULE_LINE,
    RULE_LINE_STRONG,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    VISUALLY_HIDDEN,
    field_style,
    legend,
    note_text,
    panel,
    primary_button,
    rail,
    secondary_button,
    style_legend,
    touch_target,
)

# `rx.upload` and `rx.upload_files` are linked by this id; it has to be a literal.
PHOTO_UPLOAD_ID = "photo-upload"


def _field(
    field: str,
    label: str,
    value: rx.Var,
    *,
    required: bool = False,
    hint: str = "",
    kind: str = "text",
    placeholder: str = "",
) -> rx.Component:
    """A form field with its associated label and its rail.

    The label is a real `<label for>` and not loose text above the input: that way the
    screen reader announces the field and clicking the label moves the focus inside.
    """
    field_id = f"profile-{field}"
    filled = value != ""
    # `required` is a Python bool, not a Var: it is resolved at build time.
    when_empty = BROKEN if required else GAP
    return rx.el.div(
        rx.el.div(
            rx.el.label(label, html_for=field_id, style=style_legend(TEXT_FAINT)),
            rx.el.div(style={"flex": "1 1 auto"}),
            rail(
                rx.cond(filled, JOINED, when_empty),
                style={"max_width": "2.75rem", "flex": "0 0 auto"},
            ),
            legend(
                rx.cond(filled, "Tied", "Untied" if required else "Not used"),
                color=rx.cond(filled, TEXT_MUTED, AMBER if required else TEXT_MUTED),
            ),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem", "margin_bottom": "0.375rem"},
        ),
        rx.el.input(
            id=field_id,
            type=kind,
            placeholder=placeholder,
            value=value,
            on_change=lambda new: ProfileState.update(field, new),
            style={**field_style(), **touch_target()},
        ),
        rx.cond(
            hint != "",
            rx.el.p(
                hint,
                style={
                    "font_stretch": "100%",
                    "font_size": "0.75rem",
                    "color": TEXT_MUTED,
                    "line_height": "1.45",
                    "margin_top": "0.375rem",
                },
            ),
            rx.fragment(),
        ),
        style={"width": "100%", "min_width": "0"},
    )


def _grid(*children: rx.Component) -> rx.Component:
    return rx.el.div(
        *children,
        style={
            "display": "grid",
            "grid_template_columns": ["1fr", "1fr", "repeat(2, minmax(0, 1fr))"],
            "gap": "1.25rem",
            "width": "100%",
        },
    )


def _required() -> rx.Component:
    return panel(
        legend("What the CV needs", color=AMBER),
        rx.el.p(
            "These five fields are printed in every template.",
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 1.25rem",
                "line_height": "1.5",
            },
        ),
        _grid(
            _field("first_name", "First name", ProfileState.first_name, required=True, placeholder="Jane"),
            _field("last_name", "Last name", ProfileState.last_name, required=True, placeholder="Doe"),
        ),
        rx.el.div(
            _field(
                "profession",
                "Profession",
                ProfileState.profession,
                required=True,
                placeholder="DevSecOps Engineer",
                hint="It appears under your name. In each CV you can change it just for that application.",
            ),
            style={"margin_top": "1.25rem"},
        ),
        rx.el.div(
            _grid(
                _field(
                    "phone",
                    "Phone",
                    ProfileState.phone,
                    required=True,
                    kind="tel",
                    placeholder="+1 555 0100",
                    hint="LinkedIn does not provide it, so this is the only place it is written.",
                ),
                _field(
                    "email", "Email", ProfileState.email, required=True, kind="email", placeholder="you@example.com"
                ),
            ),
            style={"margin_top": "1.25rem"},
        ),
        style={"width": "100%", "padding": "1.5rem"},
    )


def _optional() -> rx.Component:
    return panel(
        legend("Optional", color=TEXT_FAINT),
        rx.el.p(
            "Only what you fill in is printed, and only in the templates that support it.",
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 1.25rem",
                "line_height": "1.5",
            },
        ),
        _grid(
            _field("website", "Website", ProfileState.website, placeholder="https://…"),
            _field("country", "Country", ProfileState.country, placeholder="Spain"),
        ),
        rx.el.div(
            _grid(
                _field("address", "Address", ProfileState.address, placeholder="City, district"),
                _field(
                    "birth_date",
                    "Birth date",
                    ProfileState.birth_date,
                    kind="date",
                    hint="It is used to compute the age. The age is never stored, only the date.",
                ),
            ),
            style={"margin_top": "1.25rem"},
        ),
        style={"width": "100%", "padding": "1.5rem"},
    )


def _error_notice(message: rx.Var) -> rx.Component:
    """The error of an action that saves right away, next to the block that triggers it."""
    return rx.cond(
        message != "",
        rx.el.div(
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
                "margin_top": "1rem",
            },
        ),
        rx.fragment(),
    )


def _portrait() -> rx.Component:
    """The photo as it will come out in the CV, already cropped to 3:4; or the gap where it would go."""
    return rx.el.div(
        rx.cond(
            ProfileState.photo != "",
            rx.el.img(
                src=ProfileState.photo,
                alt="Your photo, as it will come out in the CV",
                style={"width": "100%", "height": "100%", "object_fit": "cover", "display": "block"},
            ),
            rx.icon("user_round", size=28, stroke_width=1.25, style={"color": AMBER_INACTIVE}),
        ),
        style={
            "width": "6rem",
            "aspect_ratio": "3 / 4",
            "flex": "0 0 auto",
            "display": "grid",
            "place_items": "center",
            "border": f"1px solid {RULE_LINE_STRONG}",
            "background": GLASS_ETCHED,
            "overflow": "hidden",
        },
    )


def _photo() -> rx.Component:
    """The profile photo. Like the skills, it saves right away.

    It uploads when dropped on the box, with no confirm button: choosing the file is
    already the decision, and the preview next to it shows the crop that will be printed.
    """
    return panel(
        legend("Photo", color=AMBER),
        rx.el.p(
            "It is cropped to 3:4 and saved right away, without the location data it brings "
            "from the phone. Only the templates that show a photo print it, and in each CV "
            "you choose whether it goes. Changing it does not alter CVs already generated.",
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 1.25rem",
                "line_height": "1.5",
            },
        ),
        rx.el.div(
            _portrait(),
            rx.el.div(
                rx.upload(
                    rx.el.div(
                        rx.icon("image_up", size=20, stroke_width=1.5, style={"color": AMBER}),
                        rx.el.p(
                            rx.cond(
                                ProfileState.uploading_photo,
                                "Processing the photo…",
                                rx.cond(ProfileState.photo != "", "Drop another photo here", "Drop your photo here"),
                            ),
                            style={
                                "font_stretch": "85%",
                                "font_weight": "600",
                                "font_size": "0.9375rem",
                                "color": TEXT,
                                "margin_top": "0.625rem",
                            },
                        ),
                        legend("JPG or PNG · or click to choose it", style={"margin_top": "0.25rem"}),
                        style={
                            "display": "flex",
                            "flex_direction": "column",
                            "align_items": "center",
                            "text_align": "center",
                        },
                    ),
                    id=PHOTO_UPLOAD_ID,
                    max_files=1,
                    multiple=False,
                    accept={"image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"]},
                    disabled=ProfileState.uploading_photo,
                    on_drop=ProfileState.upload_photo(rx.upload_files(upload_id=PHOTO_UPLOAD_ID)),
                    # Same reason as in the sync: this container receives the focus and not the hidden
                    # input, so the name goes here.
                    custom_attrs={"role": "button", "aria-label": "Choose a JPG or PNG photo"},
                    border=f"1px dashed {RULE_LINE_STRONG}",
                    border_radius="0",
                    padding="1.75rem 1rem",
                    width="100%",
                    background=GLASS_ETCHED,
                    cursor="pointer",
                ),
                rx.cond(
                    ProfileState.photo != "",
                    secondary_button(
                        rx.icon("trash_2", size=14, stroke_width=1.75),
                        "Remove photo",
                        type="button",
                        on_click=ProfileState.remove_photo,
                        disabled=ProfileState.uploading_photo,
                        style={"min_height": "2.75rem", "padding": "0 1rem", "align_self": "flex-start"},
                    ),
                    rx.fragment(),
                ),
                style={
                    "display": "flex",
                    "flex_direction": "column",
                    "gap": "0.75rem",
                    "flex": "1 1 16rem",
                    "min_width": "0",
                },
            ),
            style={"display": "flex", "gap": "1.25rem", "align_items": "flex-start", "flex_wrap": "wrap"},
        ),
        _error_notice(ProfileState.photo_error),
        style={"width": "100%", "padding": "1.5rem"},
    )


def _skill_row(skill: rx.Var) -> rx.Component:
    """A skill editable in place.

    It saves when leaving the field or on Enter, like the history's archive reason:
    without `value=` the field governs itself and does not write to disk on every keystroke.
    """
    return rx.el.form(
        rx.el.input(type="hidden", name="id", value=skill["id"]),
        rx.el.input(
            name="name",
            default_value=skill["name"],
            on_blur=lambda name: ProfileState.rename_skill(skill["id"], name),
            aria_label="Skill name " + skill["name"],
            style={**field_style(), **touch_target(), "flex": "1 1 auto", "min_width": "0"},
        ),
        secondary_button(
            rx.icon("trash_2", size=14, stroke_width=1.75),
            type="button",
            on_click=ProfileState.remove_skill(skill["id"]),
            aria_label="Remove " + skill["name"],
            title="Remove " + skill["name"],
            # At the height of the field next to it, on desktop too.
            style={"min_height": "2.75rem", "min_width": "2.75rem", "padding": "0"},
        ),
        # The id travels in a hidden field: Reflex compiles the `on_submit` outside the
        # `foreach`, and a reference to `skill` there blows up in the browser when pressing Enter.
        on_submit=ProfileState.rename_from_form,
        key=skill["id"] + "-" + ProfileState.skills_version.to_string(),
        style={"display": "flex", "align_items": "center", "gap": "0.5rem", "width": "100%"},
    )


def _new_skill() -> rx.Component:
    return rx.el.form(
        rx.el.input(
            name="name",
            placeholder="Kubernetes",
            aria_label="New skill",
            style={**field_style(), **touch_target(), "flex": "1 1 auto", "min_width": "0"},
        ),
        secondary_button(
            rx.icon("plus", size=14, stroke_width=1.75),
            "Add",
            type="submit",
            style={"min_height": "2.75rem", "padding": "0 1rem"},
        ),
        on_submit=ProfileState.add_skill,
        reset_on_submit=True,
        style={
            "display": "flex",
            "align_items": "center",
            "gap": "0.5rem",
            "width": "100%",
            "border_top": f"1px solid {RULE_LINE}",
            "padding_top": "1rem",
        },
    )


def _skills() -> rx.Component:
    """The master profile skills, which the LinkedIn PDF only half brings.

    They are separate from the personal details and save right away, without the button above.
    """
    return panel(
        legend("Skills", color=AMBER),
        rx.el.p(
            "The LinkedIn PDF only brings your top three skills: complete the rest "
            "here. They save right away. The ones you remove do not come back when syncing, and "
            "CVs already generated do not change.",
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 1.25rem",
                "line_height": "1.5",
            },
        ),
        rx.cond(
            ProfileState.skills.length() > 0,
            rx.el.div(
                rx.foreach(ProfileState.skills, _skill_row),
                style={"display": "flex", "flex_direction": "column", "gap": "0.5rem", "margin_bottom": "1rem"},
            ),
            note_text("You have no skills yet. Add the first one below.", style={"margin_bottom": "1rem"}),
        ),
        _new_skill(),
        _error_notice(ProfileState.skills_error),
        style={"width": "100%", "padding": "1.5rem"},
    )


def _without_profile() -> rx.Component:
    """Empty state: it says what the real next step is, not just that there is nothing."""
    return rx.el.div(
        rx.el.p(
            "There is no profile to edit yet",
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
        rx.el.p(
            "The profile is created when you import your LinkedIn export. Then you come back here to "
            "complete the phone and whatever the importer could not bring.",
            style={"color": TEXT_FAINT, "max_width": "54ch", "line_height": "1.55", "margin_bottom": "1.5rem"},
        ),
        primary_button(
            rx.icon("refresh_cw", size=16, stroke_width=2),
            "Import from LinkedIn",
            on_click=ProfileState.go_to_sync,
            style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem"},
        ),
        style={"border": f"1px dashed {RULE_LINE}", "padding": "3rem 1.5rem"},
    )


def _contact() -> rx.Component:
    """The personal details. Unlike the other subsections, they save together with the button."""
    return rx.el.div(
        _required(),
        _optional(),
        rx.el.div(
            primary_button(
                rx.icon("save", size=15, stroke_width=2),
                rx.cond(ProfileState.saving, "Saving…", "Save changes"),
                on_click=ProfileState.save,
                disabled=~ProfileState.can_save | ProfileState.saving,
                style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem"},
            ),
            rx.cond(
                ProfileState.can_save,
                rx.fragment(),
                rx.el.div(
                    rail(BROKEN, style={"max_width": "3rem"}),
                    note_text("Still missing: " + ProfileState.missing_summary, color=AMBER),
                    style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
                ),
            ),
            rx.cond(
                ProfileState.has_unsaved_changes & ~ProfileState.saving,
                note_text("You have changes that are not saved yet.", color=AMBER),
                rx.fragment(),
            ),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "1rem",
                "flex_wrap": "wrap",
                "border_top": f"1px solid {RULE_LINE}",
                "padding_top": "1.5rem",
            },
        ),
        rx.cond(
            ProfileState.saved,
            rx.el.div(
                rx.el.span(
                    "Saved. The next CVs you generate will use these details.",
                    style={**style_legend(GLASS), "text_transform": "none", "letter_spacing": "0.04em"},
                ),
                style={"background": AMBER, "padding": "0.75rem 1rem"},
            ),
            rx.fragment(),
        ),
        rx.cond(
            ProfileState.error_message != "",
            rx.el.div(
                rx.icon("circle_alert", size=15, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
                rx.el.p(
                    ProfileState.error_message,
                    style={"font_stretch": "100%", "font_size": "0.875rem", "color": TEXT, "line_height": "1.5"},
                ),
                style={
                    "display": "flex",
                    "gap": "0.75rem",
                    "align_items": "flex-start",
                    "border": f"1px solid {RULE_LINE}",
                    "border_left": f"2px solid {AMBER}",
                    "padding": "0.875rem 1rem",
                },
            ),
            rx.fragment(),
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.5rem", "width": "100%"},
    )


def _unsaved_mark() -> rx.Component:
    """The dot on Contact while it holds changes not saved, seen from any subsection."""
    return rx.cond(
        ProfileState.has_unsaved_changes,
        rx.el.span(
            rx.el.span("●", aria_hidden="true", style={"color": AMBER, "margin_left": "0.5rem"}),
            rx.el.span(" (not saved)", style=VISUALLY_HIDDEN),
            title="Changes not saved yet",
        ),
        rx.fragment(),
    )


def _section_item(name: str, label: str) -> rx.Component:
    """An entry of the side menu. The open one is marked like the wizard's current step:
    an amber rule on the left and an etched background, never the solid plate."""
    current = ProfileState.section == name
    return rx.el.button(
        label,
        _unsaved_mark() if name == "contact" else rx.fragment(),
        type="button",
        on_click=ProfileState.show_section(name),
        aria_current=rx.cond(current, "true", ""),
        style={
            **style_legend(),
            **touch_target(),
            "color": rx.cond(current, AMBER, TEXT_MUTED),
            "text_align": "left",
            "white_space": "nowrap",
            "padding": "0.625rem 0.75rem",
            "border_radius": "0",
            "border": "1px solid transparent",
            "border_left": rx.cond(current, f"2px solid {AMBER}", "2px solid transparent"),
            "background": rx.cond(current, GLASS_ETCHED, "transparent"),
            "cursor": "pointer",
            # The left rule stays amber on the open one, or hovering it would erase the mark.
            "_hover": {
                "color": AMBER,
                "border_color": RULE_LINE,
                "border_left_color": rx.cond(current, AMBER, RULE_LINE),
            },
        },
    )


def _side_menu() -> rx.Component:
    """The four subsections. On a narrow window the entries wrap above the content."""
    return rx.el.nav(
        *[_section_item(name, label) for name, label in PROFILE_SECTIONS.items()],
        aria_label="Profile sections",
        style={
            "display": "flex",
            "flex_direction": ["row", "row", "row", "column"],
            "flex_wrap": "wrap",
            "gap": "0.125rem",
            "flex": "0 0 auto",
            "width": ["100%", "100%", "100%", "11rem"],
            "align_self": "flex-start",
        },
    )


def _form() -> rx.Component:
    return rx.el.div(
        _side_menu(),
        rx.el.div(
            rx.match(
                ProfileState.section,
                ("photo", _photo()),
                ("skills", _skills()),
                ("experience", work_experience()),
                _contact(),
            ),
            style={"flex": "1 1 auto", "min_width": "0"},
        ),
        style={
            "display": "flex",
            "flex_direction": ["column", "column", "column", "row"],
            "gap": ["1rem", "1rem", "1rem", "1.5rem"],
            "width": "100%",
        },
    )


def _strip() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            legend("Where this data comes from"),
            rx.el.p(
                "The phone never comes from LinkedIn: it is the only field that only exists "
                "here. The rest comes in through the sync and you correct it.",
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
            legend("What the link means"),
            rx.el.div(
                _direction(JOINED, "Tied", "The field has a value."),
                _direction(BROKEN, "Untied", "Required and empty: the PDF will print 'PENDING'."),
                _direction(GAP, "Not used", "Optional and empty. That is fine."),
                style={"display": "flex", "flex_direction": "column", "gap": "0.75rem", "margin_top": "0.75rem"},
            ),
        ),
        secondary_button(
            rx.icon("refresh_cw", size=13, stroke_width=1.75),
            "Sync again",
            on_click=ProfileState.go_to_sync,
            style={**touch_target(), "width": "100%", "font_size": "0.625rem"},
        ),
    )


def _direction(status: str, title: str, explanation: str) -> rx.Component:
    """A scheme legend entry: the stroke next to what it means.

    Without this the pattern is a pretty drawing that has to be guessed. A scheme always
    comes with its legend printed next to it.
    """
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


def profile_page() -> rx.Component:
    """Editing of the master profile, in four subsections: contact, photo, skills and the
    achievements of each job."""
    return page(
        "My profile",
        "Your contact details, your photo, your skills and the achievements of each job. "
        "The jobs themselves come in and are updated from the LinkedIn sync.",
        rx.cond(ProfileState.has_profile, _form(), _without_profile()),
        strip=rx.cond(ProfileState.has_profile, legend_strip(_strip()), rx.fragment()),
        data=data_group(
            data_cell(
                "Status",
                rx.cond(ProfileState.can_save, "Complete", "Incomplete"),
            ),
        ),
    )
