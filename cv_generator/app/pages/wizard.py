"""Wizard: turns your master profile into a CV tailored to one application.

The six steps are six numbered rails in the left strip. Rails are not a loose metaphor:
the number is the anchor to go back to a step already visited, which is exactly what
the source world does with its lines — you re-enter where it broke, without retracing
the way.

Progress is drawn with six discrete cells and not with a percentage bar. The previous
bar computed (step-1)*100//6 and showed 83% while on the last step; six cells cannot lie
about how many steps there are nor which one you are on.
"""

import reflex as rx

from cv_generator.app.components.header import data_cell, data_group, legend_strip, page
from cv_generator.app.components.wizard_steps import (
    application_step,
    experience_step,
    other_sections_step,
    presentation_step,
    sections_step,
    template_step,
)
from cv_generator.app.states.profile_state import section_url
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.app.styles import (
    AMBER,
    AMBER_INACTIVE,
    BROKEN,
    GAP,
    GLASS_ETCHED,
    JOINED,
    RULE_LINE,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    figure,
    legend,
    note_text,
    primary_button,
    rail,
    secondary_button,
    secondary_link,
    style_legend,
    touch_target,
)


def _step_rail(step: rx.Var) -> rx.Component:
    """A step on the map: rail number, title and its link.

    The visited ones are buttons: going back to step 2 from 6 took four clicks of
    "Back" and there was no way to see how many steps were left.
    """
    current = step["status"] == "current"
    done = step["status"] == "done"
    reachable = step["reachable"] != ""
    return rx.el.button(
        rx.el.span(
            step["number"],
            style=figure("1rem", rx.cond(reachable, AMBER, TEXT_MUTED)),
        ),
        rx.el.span(
            step["title"],
            style={
                **style_legend(),
                "color": rx.cond(current, AMBER, rx.cond(reachable, TEXT, TEXT_MUTED)),
                "text_align": "left",
                "flex": "1 1 auto",
                "min_width": "0",
            },
        ),
        rail(
            rx.cond(done | current, JOINED, GAP),
            style={
                "max_width": "2rem",
                "flex": "0 0 auto",
                "color": rx.cond(reachable, AMBER, AMBER_INACTIVE),
            },
        ),
        type="button",
        disabled=~reachable,
        on_click=WizardState.go_to_step(step["number"].to(int)),
        aria_current=rx.cond(current, "step", ""),
        style={
            **touch_target(),
            "display": "flex",
            "align_items": "center",
            "gap": "0.625rem",
            "width": "100%",
            "padding": "0.5rem 0.625rem",
            "border_radius": "0",
            # The current step is marked with a rule on the left and an etched background, not with
            # the solid plate: the plate belongs to the primary action. The PASSIVE step marker used
            # to carry the screen's only solid amber while "Next" was an outline, so what cannot be
            # clicked weighed more than what can.
            "border": "1px solid transparent",
            "border_left": rx.cond(current, f"2px solid {AMBER}", "2px solid transparent"),
            "background": rx.cond(current, GLASS_ETCHED, "transparent"),
            "cursor": rx.cond(reachable, "pointer", "not-allowed"),
            "font": "inherit",
            "_hover": {"border_color": rx.cond(reachable, RULE_LINE, "transparent")},
        },
    )


def _step_map() -> rx.Component:
    return rx.el.nav(
        legend("Wizard rails"),
        rx.el.div(
            rx.foreach(WizardState.step_map, _step_rail),
            style={"display": "flex", "flex_direction": "column", "gap": "0.125rem", "margin_top": "0.625rem"},
        ),
        aria_label="Wizard steps",
        style={"width": "100%"},
    )


# The two controls of the side strip, its full width.
_STRIP_BUTTON = {"min_height": "2.25rem", "padding": "0 0.75rem", "font_size": "0.625rem", "width": "100%"}


def _strip_notices() -> rx.Component:
    """What you need to know before generating, fixed at the side and not at the very top."""
    return rx.fragment(
        rx.cond(
            WizardState.has_pending,
            rx.el.div(
                rx.el.div(
                    rail(BROKEN, style={"max_width": "3rem", "flex": "0 0 auto"}),
                    legend("Untied", color=AMBER),
                    style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
                ),
                rx.el.p(
                    "Your profile has no " + WizardState.pending_summary + ". Without it the CV "
                    "prints 'PENDING' in its place. My profile opens in another tab, so this CV is kept.",
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.8125rem",
                        "line_height": "1.5",
                        "color": TEXT_FAINT,
                        "margin": "0.5rem 0 0.75rem",
                    },
                ),
                # A link and not a redirect: going back to /new would restart the wizard.
                secondary_link(
                    "Complete in My profile",
                    rx.icon("external_link", size=13, stroke_width=1.75),
                    href=section_url("contact"),
                    target="_blank",
                    rel="noopener",
                    style={**_STRIP_BUTTON, "gap": "0.375rem"},
                ),
                secondary_button(
                    rx.icon("refresh_cw", size=13, stroke_width=1.75),
                    "Check again",
                    type="button",
                    on_click=WizardState.fetch_contact_details,
                    style={**_STRIP_BUTTON, "gap": "0.375rem", "margin_top": "0.5rem"},
                ),
                # Always mounted: a `role="status"` that appears together with its text is not
                # always announced.
                note_text(
                    WizardState.contact_notice,
                    color=TEXT_FAINT,
                    role="status",
                    style={
                        "display": "block",
                        "margin_top": rx.cond(WizardState.contact_notice == "", "0", "0.625rem"),
                    },
                ),
                style={
                    "border": f"1px solid {RULE_LINE}",
                    "padding": "0.875rem",
                    "border_top": f"1px solid {RULE_LINE}",
                },
            ),
            rx.fragment(),
        ),
        rx.cond(
            WizardState.cloned_from != "",
            rx.el.div(
                legend("Cloned from", color=AMBER),
                rx.el.p(
                    WizardState.cloned_from,
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.8125rem",
                        "color": TEXT,
                        "margin_top": "0.375rem",
                        "line_height": "1.45",
                    },
                ),
                rx.el.p(
                    "Adjust what changed and generate.",
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.75rem",
                        "color": TEXT_MUTED,
                        "margin_top": "0.375rem",
                    },
                ),
                style={"border": f"1px solid {RULE_LINE}", "padding": "0.875rem"},
            ),
            rx.fragment(),
        ),
    )


def _body() -> rx.Component:
    """Shows the active step."""
    return rx.match(
        WizardState.step,
        (1, template_step()),
        (2, application_step()),
        (3, presentation_step()),
        (4, experience_step()),
        (5, other_sections_step()),
        (6, sections_step()),
        template_step(),
    )


def _navigation() -> rx.Component:
    return rx.el.div(
        secondary_button(
            rx.icon("chevron_left", size=15, stroke_width=1.75),
            "Back",
            on_click=WizardState.go_back,
            disabled=WizardState.step <= 1,
            style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
        ),
        rx.el.div(style={"flex": "1 1 auto"}),
        # The reason it is blocked, stuck to the button it blocks. A disabled button with no
        # reason forces you to guess which of the fields on the screen is in the way.
        rx.cond(
            WizardState.missing_to_advance != "",
            rx.el.div(
                rail(BROKEN, style={"max_width": "3rem", "flex": "0 0 auto"}),
                note_text(WizardState.missing_to_advance, color=AMBER),
                style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
            ),
            rx.fragment(),
        ),
        rx.cond(
            WizardState.is_last_step,
            rx.fragment(),
            # The screen's solid plate. On steps 1 to 5 the primary action is moving forward; on
            # step 6 it disappears and "Generate the PDF" inherits it.
            primary_button(
                "Next",
                rx.icon("chevron_right", size=15, stroke_width=2),
                on_click=WizardState.advance,
                disabled=~WizardState.can_advance,
                style={**touch_target(), "min_height": "2.75rem", "padding": "0 1.25rem"},
            ),
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "width": "100%",
            "gap": "0.75rem",
            "border_top": f"1px solid {RULE_LINE}",
            "padding_top": "1.5rem",
        },
    )


def wizard_page() -> rx.Component:
    """Generation wizard screen."""
    return page(
        "New CV",
        "Choose what goes into this CV and for which application. Your master profile is not touched.",
        rx.cond(
            WizardState.message != "",
            rx.el.div(
                rx.icon("circle_alert", size=16, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
                rx.el.p(
                    WizardState.message,
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
        _body(),
        _navigation(),
        strip=legend_strip(_step_map(), _strip_notices()),
        data=data_group(
            data_cell("Rail", WizardState.step.to_string() + " / 6"),
            data_cell("Template", WizardState.template),
            data_cell("Language", WizardState.language.upper()),
        ),
    )
