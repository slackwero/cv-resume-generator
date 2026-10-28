"""The six wizard steps, one per function, in the grammar of the jackfield.

This is where the world pays off what it promises. In a patch bay the controls are not
colored ornaments: every item carries its link line, and the stroke pattern says what
state it is in. This step translates that into the product without forcing anything:

    checked achievement     =====o   folded: it goes into this CV
    discarded achievement   --- --o  clean gap: out of this CV, on purpose

And that is why the posting analysis drops the red and the green. A covered term and a
missing one are told apart by the stroke and by their label, never by the tone: that way
someone who cannot tell red from green reads it the same, which was the hole in the
previous version.
"""

from collections.abc import Callable

import reflex as rx

from cv_generator.app.states.wizard_state import WizardState
from cv_generator.app.styles import (
    AMBER,
    AMBER_INACTIVE,
    BROKEN,
    FOLDED,
    GAP,
    GLASS,
    GLASS_ETCHED,
    RULE_LINE,
    RULE_LINE_STRONG,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    field_style,
    figure,
    legend,
    note_text,
    panel,
    primary_button,
    rail,
    secondary_button,
    secondary_link,
    style_legend,
    touch_target,
)

# A4 at 96 dpi: the unit the browser draws a page in.
PAGE_WIDTH_PX = 794
PAGE_HEIGHT_PX = 1123

# The thumbnail fits whole at this factor, and at 151px wide each template's typographic
# texture already stands out from the others.
THUMBNAIL_SCALE = 0.19

# The carousel card measures what its thumbnail does with its 1px rule, plus its padding
# and its own rule. Fixed width: the track snaps card by card and none is left half cut
# when scrolling it.
CARD_PADDING_PX = 12
CARD_WIDTH_PX = round(PAGE_WIDTH_PX * THUMBNAIL_SCALE) + 2 + 2 * CARD_PADDING_PX + 2

# The large view shows a whole A4 page in the frame, and the rest of the CV is seen by
# scrolling it. One scale per breakpoint (mobile, sm, md, lg, xl) and not a single one:
# the available width changes in jumps. At lg the steps strip moves to the side and takes
# almost 300px from the body, which gets them back at xl.
LARGE_VIEW_SCALES = (0.4, 0.52, 0.52, 0.44, 0.6)

# The "Aa" of each font size, in the order of `WizardState.sizes`.
SIZE_SAMPLES = ["0.8125rem", "1.0625rem", "1.375rem"]

TEMPLATE_TRACK_ID = "template-track"
PREVIOUS_ARROW_ID = "previous-templates"
NEXT_ARROW_ID = "more-templates"
LARGE_VIEW_ID = "large-view"


def _script(code: str, **values: str) -> str:
    """Fills the `__NAME__` markers of a script that runs in the browser."""
    for name, value in values.items():
        code = code.replace(f"__{name}__", value)
    return code


# The arrows switch off at the ends of the track, and only the browser knows that: going
# to the server on every scroll event would be one round trip per pixel. It is installed
# when the track mounts, which happens when entering /new (also when navigating from
# another route, without reloading) and when going back to step 1. It measures again
# when the track changes size: when the cards arrive from the server or the window width
# changes.
_WATCH_TRACK = _script(
    """(() => {
  const track = document.getElementById("__TRACK__");
  if (!track || track.dataset.watched) return;
  track.dataset.watched = "1";
  const setOff = (id, off) => {
    const arrow = document.getElementById(id);
    if (arrow) arrow.setAttribute("aria-disabled", off ? "true" : "false");
  };
  const measure = () => {
    const remaining = track.scrollWidth - track.clientWidth - track.scrollLeft;
    setOff("__PREVIOUS__", track.scrollLeft <= 1);
    setOff("__NEXT__", remaining <= 1);
  };
  track.addEventListener("scroll", measure, { passive: true });
  new ResizeObserver(measure).observe(track);
  measure();
})()""",
    TRACK=TEMPLATE_TRACK_ID,
    PREVIOUS=PREVIOUS_ARROW_ID,
    NEXT=NEXT_ARROW_ID,
)

# One view minus one card: the one peeking cut at the edge becomes the first whole one,
# instead of being skipped. No animation if the system asks for reduced motion. Each
# arrow sets the direction (-1 or 1).
_SCROLL_TRACK = _script(
    """(() => {
  const track = document.getElementById("__TRACK__");
  if (!track) return;
  const card = track.firstElementChild;
  const width = card ? card.getBoundingClientRect().width : 0;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  track.scrollBy({
    left: __DIRECTION__ * Math.max(width, track.clientWidth - width),
    behavior: still ? "auto" : "smooth",
  });
})()""",
    TRACK=TEMPLATE_TRACK_ID,
)

# Every style control changes the large view's `srcDoc`, and a new document starts at
# the very top: whoever was looking at the second page to judge the line height went
# back to the first on every click. This remembers where they were and puts them back.
_KEEP_SCROLL = _script(
    """(() => {
  const frame = document.getElementById("__VIEW__");
  if (!frame || frame.dataset.watched) return;
  frame.dataset.watched = "1";
  let offset = 0;
  const restore = () => {
    const win = frame.contentWindow;
    if (!win) return;
    win.scrollTo(0, offset);
    win.addEventListener("scroll", () => { offset = win.scrollY; }, { passive: true });
  };
  frame.addEventListener("load", restore);
  restore();
})()""",
    VIEW=LARGE_VIEW_ID,
)


# --- Shared pieces ---------------------------------------------------------------


def _block(title: str, hint: str, *content: rx.Component) -> rx.Component:
    """One job of the step, with its name above it.

    The last step piles up four different tasks. Stacked without a heading they read as
    one long screen and the user does not know where one ends and the next begins.
    """
    return rx.el.section(
        rx.el.h2(
            title,
            style={
                "font_stretch": "62%",
                "font_weight": "800",
                "font_size": "1.5rem",
                "text_transform": "uppercase",
                "letter_spacing": "-0.01em",
                "color": AMBER,
                "line_height": "1",
            },
        ),
        rx.el.p(
            hint,
            style={
                "font_stretch": "100%",
                "font_size": "0.8125rem",
                "color": TEXT_MUTED,
                "margin": "0.5rem 0 1.25rem",
                "max_width": "62ch",
                "line_height": "1.5",
            },
        ),
        *content,
        style={"width": "100%"},
    )


def _hint(text: str) -> rx.Component:
    return rx.el.p(
        text,
        style={
            "font_stretch": "100%",
            "font_size": "0.875rem",
            "color": TEXT_FAINT,
            "line_height": "1.55",
            "max_width": "68ch",
        },
    )


def _note(text: str, icon_name: str = "info") -> rx.Component:
    """An operator's note: rule, glyph and text. No color fill."""
    return rx.el.div(
        rx.icon(
            icon_name, size=15, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto", "margin_top": "0.125rem"}
        ),
        rx.el.p(
            text,
            style={"font_stretch": "100%", "font_size": "0.8125rem", "color": TEXT_FAINT, "line_height": "1.5"},
        ),
        style={
            "display": "flex",
            "gap": "0.75rem",
            "align_items": "flex-start",
            "border": f"1px solid {RULE_LINE}",
            "padding": "0.75rem 0.875rem",
            "width": "100%",
        },
    )


def _field(
    caption: str,
    placeholder: str,
    value: rx.Var,
    on_change_handler: rx.event.EventHandler,
    hint: str = "",
) -> rx.Component:
    """A field with its scheme label above it."""
    return rx.el.label(
        legend(caption, color=TEXT_FAINT),
        rx.el.input(
            placeholder=placeholder,
            value=value,
            on_change=on_change_handler,
            style={**field_style(), "margin_top": "0.375rem"},
        ),
        rx.cond(
            hint != "",
            rx.el.span(
                hint,
                style={
                    "font_stretch": "100%",
                    "font_size": "0.75rem",
                    "color": TEXT_MUTED,
                    "display": "block",
                    "margin_top": "0.375rem",
                    "line_height": "1.45",
                },
            ),
            rx.fragment(),
        ),
        style={"display": "block", "width": "100%"},
    )


def _checkbox(**props: object) -> rx.Component:
    """The scheme checkbox: square, amber, no radius.

    Radix's `rx.checkbox` is kept instead of a raw input because its keyboard behavior
    and its link with the label are already solved; what changes is the skin.
    """
    style = {
        "--checkbox-indicator-color": GLASS,
        "border_radius": "0",
        "flex": "0 0 auto",
    }
    style.update(props.pop("style", {}))
    return rx.checkbox(color_scheme="amber", high_contrast=True, size="2", style=style, **props)


# --- Step 1: template ------------------------------------------------------------


def _sheet(html: rx.Var, scales: tuple[float, ...], *, scrollable: bool = False, **props: object) -> rx.Component:
    """A really rendered page, scaled down.

    It is the same `render_html` that produces the PDF. The iframe measures one A4 page
    and is scaled down with `transform` inside a box of the already reduced size, which
    is what takes space in the layout. With several scales, one per breakpoint.

    It stays out of the tab order: it is an image of the CV, not a control. The thumbnail
    also receives no pointer events, because what receives the click is the card around
    it; the large view does, so it can be scrolled with the wheel or the trackpad.

    The paper is white and stays white. In this world a foreign image keeps its own color
    inside an amber rule, instead of being tinted to fit in.

    The `sandbox` prevents a script from running inside the CV. Jinja's autoescape
    already keeps the text imported from LinkedIn from being read as HTML; this is the
    second barrier. `allow-same-origin` lets the page keep reading the frame's document,
    which is what the large view uses to keep the scroll position between one render and
    the next.
    """

    def by_scale(value: Callable[[float], str]) -> str | list[str]:
        values = [value(scale) for scale in scales]
        return values if len(values) > 1 else values[0]

    attributes = {"srcDoc": html, "sandbox": "allow-same-origin", "tabIndex": "-1", "aria-hidden": "true"}
    if not scrollable:
        attributes["scrolling"] = "no"
    return rx.el.div(
        rx.cond(
            html != "",
            rx.el.iframe(
                custom_attrs=attributes,
                style={
                    "width": f"{PAGE_WIDTH_PX}px",
                    "height": f"{PAGE_HEIGHT_PX}px",
                    "border": "0",
                    "display": "block",
                    "transform": by_scale(lambda scale: f"scale({scale})"),
                    "transform_origin": "top left",
                    "pointer_events": "auto" if scrollable else "none",
                },
                **props,
            ),
            rx.el.div(
                rx.icon("file_text", size=22, stroke_width=1.5, style={"color": AMBER_INACTIVE}),
                style={"display": "grid", "place_items": "center", "width": "100%", "height": "100%"},
            ),
        ),
        style={
            "width": by_scale(lambda scale: f"{round(PAGE_WIDTH_PX * scale)}px"),
            "height": by_scale(lambda scale: f"{round(PAGE_HEIGHT_PX * scale)}px"),
            "box_sizing": "content-box",
            "flex_shrink": "0",
            "overflow": "hidden",
            "background": "white",
            "border": f"1px solid {RULE_LINE_STRONG}",
        },
    )


def _thumbnail(template: rx.Var) -> rx.Component:
    """The template with the trimmed CV and the style applied, at card size."""
    return _sheet(template["thumbnail"], (THUMBNAIL_SCALE,))


def _ats_badge(template: rx.Var) -> rx.Component:
    """Marks the templates meant to pass an automated filter (`ats` in their meta.json).

    It sits on the thumbnail's corner, in solid amber: it is a fact about the template,
    not a state of the card, so it does not change when it is chosen. The `title`
    explains the acronym to whoever does not know it.
    """
    return rx.cond(
        template["ats"] != "",
        rx.el.span(
            "ATS",
            title="Meant for an applicant tracking system (ATS) to read all of the text",
            style={
                **style_legend(GLASS),
                "position": "absolute",
                "top": "0.375rem",
                "left": "0.375rem",
                "background": AMBER,
                "padding": "0.125rem 0.375rem",
                "letter_spacing": "0.08em",
                "pointer_events": "none",
            },
        ),
        rx.fragment(),
    )


def _template_card(template: rx.Var, index: rx.Var) -> rx.Component:
    """A choosable template in the carousel: the thumbnail on top and the name below.

    It is a real `<button>` and not a `div`: choosing the design is the step's main
    decision and it was out of keyboard reach. A native button already takes focus with
    Tab and activates with Enter and Space, without handling keys by hand.

    The description no longer goes here: the card is compact so several fit in the row,
    and the chosen one's description is read under the large view.
    """
    chosen = WizardState.template == template["slug"]
    return rx.el.button(
        rx.el.span(
            _thumbnail(template),
            _ats_badge(template),
            style={"position": "relative", "display": "block"},
        ),
        rx.el.span(
            rx.el.span(
                (index + 1).to_string(),
                style=figure("1rem", rx.cond(chosen, AMBER, TEXT_MUTED)),
            ),
            rx.el.span(
                template["name"],
                style={
                    "font_stretch": "75%",
                    "font_weight": "700",
                    "font_size": "0.9375rem",
                    "text_transform": "uppercase",
                    "letter_spacing": "0.04em",
                    "color": rx.cond(chosen, AMBER, TEXT),
                    "overflow": "hidden",
                    "text_overflow": "ellipsis",
                    "white_space": "nowrap",
                    "min_width": "0",
                },
            ),
            style={"display": "flex", "align_items": "baseline", "gap": "0.5rem", "margin_top": "0.75rem"},
        ),
        rail(rx.cond(chosen, FOLDED, GAP), style={"margin_top": "0.625rem", "max_width": "7rem"}),
        legend(
            rx.cond(chosen, "Chosen", "Available"),
            color=rx.cond(chosen, AMBER, TEXT_MUTED),
            style={"margin_top": "0.5rem", "display": "block"},
        ),
        type="button",
        role="radio",
        aria_checked=rx.cond(chosen, "true", "false"),
        on_click=WizardState.choose_template(template["slug"]),
        style={
            "flex": "0 0 auto",
            "width": f"{CARD_WIDTH_PX}px",
            "box_sizing": "border-box",
            "scroll_snap_align": "start",
            "display": "flex",
            "flex_direction": "column",
            "padding": f"{CARD_PADDING_PX}px",
            "cursor": "pointer",
            "border": rx.cond(chosen, f"1px solid {AMBER}", f"1px solid {RULE_LINE}"),
            "background": rx.cond(chosen, GLASS_ETCHED, "transparent"),
            "font": "inherit",
            "color": "inherit",
            "text_align": "left",
            "border_radius": "0",
        },
    )


def _track_arrow(identifier: str, icon_name: str, label: str, direction: int) -> rx.Component:
    """Scrolls the track. At its end it switches off, but it stays in the tab order.

    It switches off with `aria-disabled` and not `disabled` because the browser decides
    it (see `_WATCH_TRACK`), and a button that loses focus when switching off leaves the
    keyboard with nowhere to be. It starts off: until it measures there is nothing to promise.
    """
    return secondary_button(
        rx.icon(icon_name, size=16, stroke_width=1.75),
        id=identifier,
        type="button",
        aria_label=label,
        title=label,
        aria_controls=TEMPLATE_TRACK_ID,
        aria_disabled="true",
        on_click=rx.call_script(_script(_SCROLL_TRACK, DIRECTION=str(direction))),
        style={
            **touch_target(),
            "min_height": "2.75rem",
            "min_width": "2.75rem",
            "padding": "0",
            "&[aria-disabled='true']": {
                "opacity": "0.55",
                "color": TEXT_MUTED,
                "border": f"1px solid {AMBER_INACTIVE}",
                "cursor": "not-allowed",
            },
            "&[aria-disabled='true']:hover": {"background": "transparent", "color": TEXT_MUTED},
        },
    )


def _template_carousel() -> rx.Component:
    """The templates in a row that scrolls horizontally.

    The catalog is discovered by folder and is going to grow: a grid of cards pushed the
    large view and the controls further and further down. It scrolls with the arrows,
    the trackpad or the touch gesture, and snaps card by card.
    """
    how_many = WizardState.templates.length()
    return rx.el.div(
        rx.el.div(
            legend(
                "Template · " + how_many.to_string() + rx.cond(how_many == 1, " available", " available"),
                color=AMBER,
            ),
            rx.el.div(style={"flex": "1 1 auto"}),
            _track_arrow(PREVIOUS_ARROW_ID, "chevron_left", "Previous templates", -1),
            _track_arrow(NEXT_ARROW_ID, "chevron_right", "More templates", 1),
            style={"display": "flex", "align_items": "center", "gap": "0.5rem", "width": "100%"},
        ),
        rx.el.div(
            rx.foreach(WizardState.templates, _template_card),
            id=TEMPLATE_TRACK_ID,
            role="radiogroup",
            aria_label="Document template",
            on_mount=rx.call_script(_WATCH_TRACK),
            style={
                "display": "flex",
                "gap": "0.75rem",
                "overflow_x": "auto",
                "overscroll_behavior_x": "contain",
                "scroll_snap_type": "x mandatory",
                # The focus ring sticks out 4px from the card; without this inner margin the track,
                # which clips its content, ate it at the edges.
                "padding": "4px 4px 0.75rem",
                "scroll_padding": "0 4px",
                "width": "100%",
                "margin_top": "0.75rem",
            },
        ),
        style={"width": "100%"},
    )


def _large_view() -> rx.Component:
    """The full CV with the chosen template and the style applied.

    The thumbnail is good for comparing designs, but a font size or a line height can
    only be judged on the whole document. It is continuous HTML: where each page breaks
    is seen in the step 6 preview.
    """
    return rx.el.div(
        _sheet(
            WizardState.large_view,
            LARGE_VIEW_SCALES,
            scrollable=True,
            id=LARGE_VIEW_ID,
            on_mount=rx.call_script(_KEEP_SCROLL),
        ),
        rx.el.div(
            rx.el.span(
                WizardState.template_name,
                style={
                    "font_stretch": "75%",
                    "font_weight": "700",
                    "font_size": "1rem",
                    "text_transform": "uppercase",
                    "letter_spacing": "0.04em",
                    "color": AMBER,
                    "display": "block",
                },
            ),
            rx.foreach(
                WizardState.templates,
                lambda template: rx.cond(
                    template["slug"] == WizardState.template,
                    rx.el.p(
                        template["description"],
                        style={
                            "font_stretch": "100%",
                            "font_size": "0.8125rem",
                            "color": TEXT_FAINT,
                            "line_height": "1.5",
                            "margin_top": "0.375rem",
                        },
                    ),
                    rx.fragment(),
                ),
            ),
            note_text(
                "Continuous text: you see where each page breaks when you preview the PDF in the last step.",
                style={"display": "block", "margin_top": "0.5rem"},
            ),
            # Zero width and a 100% minimum: the text fits the frame width instead of widening the
            # column, which took that space away from the controls.
            style={"margin_top": "0.875rem", "width": "0", "min_width": "100%"},
        ),
        style={"flex": "0 0 auto", "max_width": "100%"},
    )


def _control_state(text: rx.Var | str) -> rx.Component:
    return note_text(text, color=TEXT_FAINT, style={"text_align": "right", "white_space": "nowrap"})


def _chosen_option(options: rx.Var, chosen: rx.Var) -> rx.Component:
    """The name of the option in effect, or that the template's is used.

    It says so in words and not only with the ring or the border: state does not travel
    in color, and with nothing chosen it has to be clear that it is not an oversight.
    """
    return rx.cond(
        chosen == "",
        _control_state("Template default"),
        rx.foreach(
            options,
            lambda option: rx.cond(option["key"] == chosen, _control_state(option["name"]), rx.fragment()),
        ),
    )


def _control_label(caption: str, status: rx.Component) -> rx.Component:
    return rx.el.div(
        legend(caption, color=AMBER),
        status,
        style={"display": "flex", "align_items": "baseline", "justify_content": "space-between", "gap": "0.75rem"},
    )


def _control_group(*children: rx.Component) -> rx.Component:
    return rx.el.div(
        *children,
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "0.625rem",
            "border_top": f"1px solid {RULE_LINE}",
            "padding_top": "1rem",
        },
    )


def _color_swatch(color: rx.Var) -> rx.Component:
    """A palette color. The swatch is round; the click target, square.

    They are the only piece of the interface with a radius, because they are not
    interface: they are the document's color, a foreign image like the thumbnail. The
    chosen one carries an amber ring apart from the swatch, which shows on dark tones too.
    """
    chosen = WizardState.style_color == color["key"]
    return rx.el.button(
        rx.el.span(
            style={
                "display": "block",
                "width": "1.625rem",
                "height": "1.625rem",
                "border_radius": "50%",
                "background": color["sample"],
                "border": f"1px solid {RULE_LINE_STRONG}",
                "outline": rx.cond(chosen, f"2px solid {AMBER}", "2px solid transparent"),
                "outline_offset": "3px",
            },
        ),
        type="button",
        role="radio",
        aria_checked=rx.cond(chosen, "true", "false"),
        aria_label=color["name"],
        title=color["name"],
        on_click=WizardState.choose_color(color["key"]),
        style={
            **touch_target(),
            "min_width": ["44px", "44px", "auto"],
            "display": "inline-grid",
            "place_items": "center",
            "padding": "0.4375rem",
            "background": "transparent",
            "border": "0",
            "border_radius": "0",
            "cursor": "pointer",
        },
    )


def _size_option(size: rx.Var, index: rx.Var) -> rx.Component:
    """A font size, drawn as "Aa" at that size.

    The chosen one changes its rule and gets a thicker base: the thickness says which
    one it is, not the tone. Its name is also read in the control's label.
    """
    chosen = WizardState.style_size == size["key"]
    return rx.el.button(
        rx.el.span(
            "Aa",
            aria_hidden="true",
            style={
                "font_size": rx.Var.create(SIZE_SAMPLES)[index],
                "font_stretch": "100%",
                "font_weight": "600",
                "line_height": "1",
            },
        ),
        type="button",
        role="radio",
        aria_checked=rx.cond(chosen, "true", "false"),
        aria_label=size["name"],
        title=size["name"],
        on_click=WizardState.choose_size(size["key"]),
        style={
            **touch_target(),
            "min_height": "2.75rem",
            "flex": "1 1 0",
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "padding": "0 0.5rem",
            "cursor": "pointer",
            "font": "inherit",
            "border_radius": "0",
            "color": rx.cond(chosen, AMBER, TEXT_FAINT),
            "background": rx.cond(chosen, GLASS_ETCHED, "transparent"),
            "border": rx.cond(chosen, f"1px solid {AMBER}", f"1px solid {RULE_LINE}"),
            "border_bottom": rx.cond(chosen, f"3px solid {AMBER}", f"1px solid {RULE_LINE}"),
            "_hover": {"border_color": AMBER},
        },
    )


def _line_height_button(icon_name: str, label: str, direction: int, *, possible: rx.Var) -> rx.Component:
    return secondary_button(
        rx.icon(icon_name, size=15, stroke_width=1.75),
        type="button",
        aria_label=label,
        title=label,
        disabled=~possible,
        on_click=WizardState.change_line_height(direction),
        style={**touch_target(), "min_height": "2.75rem", "min_width": "2.75rem", "padding": "0"},
    )


def _style_controls() -> rx.Component:
    """Color, font, size and line height of THIS CV.

    They belong to the CV and not to the template: with another template they stay set,
    and whatever was not touched keeps each template's own value. That is why each
    control says "Template default" when it has not been changed, instead of faking a value.
    """
    return panel(
        legend("Style of this CV", color=TEXT_FAINT),
        note_text(
            "It stays even if you change templates. Whatever you do not touch stays as each template has it.",
            color=TEXT_MUTED,
            style={"display": "block", "margin": "0.375rem 0 1rem"},
        ),
        rx.el.div(
            _control_group(
                _control_label("Color", _chosen_option(WizardState.colors, WizardState.style_color)),
                rx.el.div(
                    rx.foreach(WizardState.colors, _color_swatch),
                    role="radiogroup",
                    aria_label="CV color",
                    style={"display": "flex", "flex_wrap": "wrap", "gap": "0.125rem", "margin_left": "-0.4375rem"},
                ),
            ),
            _control_group(
                rx.el.label(
                    legend("Font", color=AMBER),
                    rx.el.select(
                        rx.el.option("The template's", value=""),
                        rx.foreach(
                            WizardState.fonts,
                            lambda font: rx.el.option(font["name"], value=font["key"]),
                        ),
                        value=WizardState.style_font,
                        on_change=WizardState.choose_font,
                        aria_label="CV font",
                        style={**field_style(), "margin_top": "0.625rem", "cursor": "pointer"},
                    ),
                    style={"display": "block"},
                ),
            ),
            _control_group(
                _control_label("Size", _chosen_option(WizardState.sizes, WizardState.style_size)),
                rx.el.div(
                    rx.foreach(WizardState.sizes, _size_option),
                    role="radiogroup",
                    aria_label="Font size",
                    style={"display": "flex", "gap": "0.375rem"},
                ),
            ),
            _control_group(
                _control_label(
                    "Line height",
                    _control_state(rx.cond(WizardState.style_line_height == 0, "Template default", "Adjusted")),
                ),
                rx.el.div(
                    _line_height_button("minus", "Less line height", -1, possible=WizardState.can_decrease_line_height),
                    rx.el.span(
                        WizardState.line_height_text,
                        aria_live="polite",
                        style={**figure("1.5rem", TEXT), "min_width": "4rem", "text_align": "center"},
                    ),
                    _line_height_button("plus", "More line height", 1, possible=WizardState.can_increase_line_height),
                    style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
                ),
            ),
            _control_group(
                secondary_button(
                    rx.icon("rotate_ccw", size=14, stroke_width=1.75),
                    "Back to the template's values",
                    type="button",
                    on_click=WizardState.reset_style,
                    disabled=~WizardState.custom_style,
                    style={
                        **touch_target(),
                        "min_height": "2.75rem",
                        "padding": "0.5rem 1rem",
                        "width": "100%",
                        "text_align": "center",
                    },
                ),
            ),
            style={"display": "flex", "flex_direction": "column", "gap": "1rem"},
        ),
        style={"flex": "1 1 auto", "min_width": "0", "width": ["100%", "100%", "auto"]},
    )


def template_step() -> rx.Component:
    return rx.el.div(
        _hint(
            "Choose the design and adjust the color, the font and the line height. Every change shows "
            "instantly in your CV and in the thumbnails, which are your CV really rendered."
        ),
        _template_carousel(),
        rx.el.div(
            _large_view(),
            _style_controls(),
            style={
                "display": "flex",
                "flex_direction": ["column", "column", "row"],
                "align_items": "flex-start",
                "gap": "1.5rem",
                "width": "100%",
            },
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.5rem", "width": "100%"},
    )


# --- Step 2: application ---------------------------------------------------------


def _cv_photo() -> rx.Component:
    """Whether this CV carries the profile photo.

    With a template that does not draw a photo, the checkbox shows empty and disabled:
    checked, it would claim the PDF carries it. The note says why and where to change it.
    """
    return rx.el.div(
        legend("Photo", color=AMBER),
        rx.cond(
            WizardState.has_photo,
            rx.el.div(
                rx.el.div(
                    _checkbox(
                        id="include-photo",
                        checked=WizardState.include_photo & WizardState.template_shows_photo,
                        on_change=WizardState.toggle_photo,
                        disabled=~WizardState.template_shows_photo,
                    ),
                    rx.el.label(
                        "Include my photo in this CV",
                        html_for="include-photo",
                        style={
                            "font_stretch": "100%",
                            "font_size": "0.9375rem",
                            "color": rx.cond(WizardState.template_shows_photo, TEXT, TEXT_MUTED),
                            "cursor": rx.cond(WizardState.template_shows_photo, "pointer", "default"),
                        },
                    ),
                    style={"display": "flex", "align_items": "center", "gap": "0.625rem"},
                ),
                rx.cond(
                    WizardState.template_shows_photo,
                    _hint("In some countries, and in many postings in English, a CV without a photo is expected."),
                    note_text(
                        "The "
                        + WizardState.template_name
                        + " template does not show a photo. To include it, go back to step 1 and choose one that does.",
                        color=TEXT_FAINT,
                    ),
                ),
                style={"display": "flex", "flex_direction": "column", "gap": "0.625rem"},
            ),
            rx.el.div(
                _hint(
                    "You do not have a photo in your profile yet. My profile opens in another tab "
                    "so you do not lose this half-built CV: upload it there and come back here."
                ),
                rx.el.div(
                    secondary_link(
                        rx.icon("image_up", size=14, stroke_width=1.75),
                        "Upload a photo in My profile",
                        rx.icon("external_link", size=13, stroke_width=1.75),
                        href="/profile",
                        target="_blank",
                        rel="noopener",
                        style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
                    ),
                    secondary_button(
                        rx.icon("refresh_cw", size=14, stroke_width=1.75),
                        "I uploaded it",
                        type="button",
                        on_click=WizardState.fetch_profile_photo,
                        style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
                    ),
                    style={"display": "flex", "flex_wrap": "wrap", "gap": "0.75rem", "margin_top": "0.75rem"},
                ),
                # Always mounted, even when empty: a `role="status"` that appears together with its
                # text is not always announced by the screen reader.
                note_text(
                    WizardState.photo_notice,
                    color=TEXT_FAINT,
                    role="status",
                    style={
                        "display": "block",
                        "font_size": "0.8125rem",
                        "margin_top": rx.cond(WizardState.photo_notice == "", "0", "0.75rem"),
                    },
                ),
                style={"display": "flex", "flex_direction": "column"},
            ),
        ),
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "0.75rem",
            "border_top": f"1px solid {RULE_LINE}",
            "padding_top": "1.5rem",
            "margin_top": "1.75rem",
        },
    )


def application_step() -> rx.Component:
    return rx.el.div(
        _hint(
            "The target role names the file, and it is what the application remembers "
            "to propose this same selection to you next time."
        ),
        rx.el.div(
            _field("CV name", "DevSecOps at Northwind", WizardState.cv_name, WizardState.update_cv_name),
            _field(
                "Role you are applying for",
                "DevSecOps Engineer",
                WizardState.target_role,
                WizardState.update_target_role,
            ),
            _field(
                "Profession under your name",
                "DevSecOps Engineer",
                WizardState.header_profession,
                WizardState.update_header_profession,
            ),
            style={
                "display": "grid",
                "grid_template_columns": ["1fr", "1fr", "repeat(2, minmax(0, 1fr))"],
                "gap": "1rem",
                "margin_top": "1.25rem",
            },
        ),
        _cv_photo(),
        rx.el.div(
            rx.el.div(
                legend("The posting", color=AMBER),
                legend("Optional"),
                style={"display": "flex", "gap": "0.75rem", "align_items": "center"},
            ),
            _hint(
                "If you paste the ad's text, when choosing your achievements you will see what the posting "
                "asks for and which of it does not appear yet."
            ),
            rx.el.div(
                _field("Company", "Northwind", WizardState.posting_company, WizardState.update_posting_company),
                _field("Posting URL", "https://…", WizardState.posting_url, WizardState.update_posting_url),
                style={
                    "display": "grid",
                    "grid_template_columns": ["1fr", "1fr", "repeat(2, minmax(0, 1fr))"],
                    "gap": "1rem",
                },
            ),
            rx.el.label(
                legend("Job description", color=TEXT_FAINT),
                rx.el.textarea(
                    placeholder="Paste the job description here…",
                    value=WizardState.posting_text,
                    on_change=WizardState.update_posting_text,
                    rows="8",
                    style={**field_style(), "margin_top": "0.375rem", "resize": "vertical", "line_height": "1.55"},
                ),
                style={"display": "block", "width": "100%"},
            ),
            style={
                "display": "flex",
                "flex_direction": "column",
                "gap": "1rem",
                "border_top": f"1px solid {RULE_LINE}",
                "padding_top": "1.5rem",
                "margin_top": "1.75rem",
            },
        ),
        rx.el.div(
            rx.el.label(
                legend("Label language", color=TEXT_FAINT),
                rx.el.select(
                    rx.foreach(
                        WizardState.languages,
                        lambda option: rx.el.option(option["name"], value=option["code"]),
                    ),
                    value=WizardState.language,
                    on_change=WizardState.change_language,
                    aria_label="Label language",
                    style={**field_style(), "margin_top": "0.375rem", "max_width": "20rem"},
                ),
                style={"display": "block"},
            ),
            _hint("It translates the section titles and the month in the file name. You write the content."),
            style={
                "display": "flex",
                "flex_direction": "column",
                "gap": "0.75rem",
                "border_top": f"1px solid {RULE_LINE}",
                "padding_top": "1.5rem",
                "margin_top": "1.75rem",
            },
        ),
        style={"width": "100%"},
    )


# --- Step 3: presentation --------------------------------------------------------


def _profile_option(text: rx.Var) -> rx.Component:
    """A choosable presentation text.

    It only draws the item: the `radio_group.root` that groups it lives in
    `presentation_step`. With one root per option, the screen reader announced "option 1
    of 1" as many times as there were texts and the arrows did not move between them.
    """
    chosen = WizardState.profile_text_id == text["id"]
    expanded = WizardState.expanded_profile_texts[text["id"]]
    return rx.el.div(
        rx.el.div(
            rx.radio_group.item(value=text["id"], color_scheme="amber", high_contrast=True),
            rx.el.div(
                rx.el.p(
                    rx.cond(expanded, text["text"], text["summary"]),
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.6",
                        "color": rx.cond(chosen, TEXT, TEXT_FAINT),
                    },
                ),
                rx.cond(
                    text["largo"] != "",
                    secondary_button(
                        rx.cond(expanded, "Show less", "Show all"),
                        on_click=WizardState.toggle_full_text(text["id"]).stop_propagation,
                        style={
                            "min_height": "2rem",
                            "padding": "0 0.625rem",
                            "font_size": "0.625rem",
                            "margin_top": "0.625rem",
                        },
                    ),
                    rx.fragment(),
                ),
                style={"min_width": "0", "flex": "1 1 auto"},
            ),
            style={"display": "flex", "gap": "0.875rem", "align_items": "flex-start", "width": "100%"},
        ),
        on_click=WizardState.choose_profile_text(text["id"]),
        style={
            "padding": "0.875rem 1rem",
            "border": rx.cond(chosen, f"1px solid {AMBER}", f"1px solid {RULE_LINE}"),
            "background": rx.cond(chosen, GLASS_ETCHED, "transparent"),
            "cursor": "pointer",
            "width": "100%",
        },
    )


def presentation_step() -> rx.Component:
    return rx.el.div(
        _hint("The text at the top of your CV. Choose the one that best fits the application."),
        rx.el.div(
            rx.cond(
                WizardState.profile_texts_list.length() > 0,
                rx.radio_group.root(
                    rx.el.div(
                        rx.foreach(WizardState.profile_texts_list, _profile_option),
                        style={"display": "flex", "flex_direction": "column", "gap": "0.5rem", "width": "100%"},
                    ),
                    value=WizardState.profile_text_id,
                    on_change=WizardState.choose_profile_text,
                    aria_label="CV presentation text",
                ),
                _note("Your profile has no presentation text yet."),
            ),
            style={"margin_top": "1.25rem"},
        ),
        style={"width": "100%"},
    )


# --- Step 4: experience ----------------------------------------------------------


def _term(covered: bool) -> Callable[[rx.Var], rx.Component]:
    """A posting term, as a scheme item with its link.

    Covered carries the folded rail; missing carries the gap. The red and green of the
    previous version are gone: in this world color does not carry state, and anyone who
    cannot tell those two tones apart read two identical lists.
    """

    def render(item: rx.Var) -> rx.Component:
        return rx.el.li(
            rx.el.span(
                item["term"],
                style={
                    "font_stretch": "85%",
                    "font_size": "0.8125rem",
                    "font_weight": "600",
                    "color": rx.cond(covered, TEXT, TEXT_FAINT),
                },
            ),
            rx.cond(
                item["times"] != "1",
                rx.el.span(
                    "×" + item["times"],
                    style={**style_legend(TEXT_MUTED), "margin_left": "0.375rem"},
                ),
                rx.fragment(),
            ),
            rail(
                FOLDED if covered else GAP,
                style={"max_width": "2.5rem", "margin_left": "0.5rem"},
            ),
            style={
                "display": "flex",
                "align_items": "center",
                "border": f"1px solid {RULE_LINE}",
                "padding": "0.3125rem 0.5rem",
                "list_style": "none",
                "background": rx.cond(covered, GLASS_ETCHED, "transparent"),
            },
        )

    return render


def _term_list(items: rx.Var, covered: bool) -> rx.Component:
    return rx.el.ul(
        rx.foreach(items, _term(covered)),
        style={
            "display": "flex",
            "flex_wrap": "wrap",
            "gap": "0.375rem",
            "margin": "0",
            "padding": "0",
            "list_style": "none",
        },
    )


def _coverage() -> rx.Component:
    """The posting coverage, as a figure and in cells.

    The off cells are drawn with the same care as the on ones: the absence is the data,
    not a gap where nothing arrived.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.span(WizardState.coverage_percent.to_string(), style=figure("2.75rem")),
            rx.el.span("%", style={**figure("1.25rem"), "color": TEXT_FAINT}),
            style={"display": "flex", "align_items": "baseline", "gap": "0.125rem"},
        ),
        note_text("Of what the posting asks for, already in your CV", color=TEXT_FAINT),
        style={"display": "flex", "flex_direction": "column", "gap": "0.375rem"},
    )


def _missing_while_choosing() -> rx.Component:
    """The posting terms that do not appear yet, next to the list of achievements.

    The analysis used to live only in the last step, on an already closed selection, and
    it ended with "go back and check the achievement": it admitted in writing that it
    came too late. Here the measure is on the same screen as the decision, and it updates
    with every checkbox.
    """
    return rx.cond(
        WizardState.has_analysis & (WizardState.missing_terms.length() > 0),
        panel(
            rx.el.div(
                _coverage(),
                rx.el.div(style={"flex": "1 1 auto"}),
                style={"display": "flex", "align_items": "flex-start", "gap": "1rem", "flex_wrap": "wrap"},
            ),
            rx.el.div(
                legend("Not in your CV yet", color=AMBER),
                _term_list(WizardState.missing_terms, covered=False),
                style={
                    "display": "flex",
                    "flex_direction": "column",
                    "gap": "0.625rem",
                    "margin_top": "1rem",
                    "border_top": f"1px solid {RULE_LINE}",
                    "padding_top": "1rem",
                },
            ),
            style={"width": "100%"},
        ),
        rx.fragment(),
    )


def _achievement_actions() -> rx.Component:
    """Bulk actions and a count, for a list that usually brings dozens of rows.

    The sync screen already offered them for a shorter list; here there were none, and
    no way to know how many achievements you had checked without counting them.
    """
    return rx.el.div(
        legend(WizardState.achievement_count, color=TEXT_FAINT),
        rx.el.div(style={"flex": "1 1 auto"}),
        secondary_button(
            "Check all",
            on_click=WizardState.mark_all_achievements(True),  # noqa: FBT003
            style={**touch_target(), "min_height": "2.25rem", "padding": "0 0.75rem", "font_size": "0.625rem"},
        ),
        secondary_button(
            "Uncheck all",
            on_click=WizardState.mark_all_achievements(False),  # noqa: FBT003
            style={**touch_target(), "min_height": "2.25rem", "padding": "0 0.75rem", "font_size": "0.625rem"},
        ),
        style={"display": "flex", "align_items": "center", "gap": "0.5rem", "flex_wrap": "wrap", "width": "100%"},
    )


def _experience_row(row: rx.Var) -> rx.Component:
    """An experience or one of its achievements.

    The text goes inside a `<label for>` and not loose next to the checkbox: in a list of
    dozens of rows, the only click target was a 16px square.

    The achievement's rail is what says whether it goes into this CV. Folded goes in; gap does not.
    """
    experience_id = "exp-" + row["key"]
    achievement_id = "achievement-" + row["key"]
    inside = WizardState.marked_achievements[row["key"]]
    active = WizardState.marked_items[row["experience_id"]]
    return rx.cond(
        row["row"] == "experience",
        rx.el.div(
            _checkbox(
                id=experience_id,
                checked=WizardState.marked_items[row["key"]],
                on_change=lambda value: WizardState.toggle(row["key"], value),
            ),
            rx.el.label(
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
                    row["company"] + " · " + row["dates"],
                    style={**style_legend(TEXT_MUTED), "display": "block", "margin_top": "0.25rem"},
                ),
                html_for=experience_id,
                style={"cursor": "pointer", "min_width": "0"},
            ),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "0.875rem",
                "width": "100%",
                "padding": "1rem 0 0.625rem",
                "border_bottom": f"1px solid {RULE_LINE}",
                "margin_top": "0.5rem",
            },
        ),
        rx.el.div(
            _checkbox(
                id=achievement_id,
                checked=inside,
                on_change=lambda value: WizardState.toggle_achievement(row["key"], value),
                disabled=~active,
            ),
            rx.el.div(
                rx.el.label(
                    row["text"],
                    html_for=achievement_id,
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.875rem",
                        "line_height": "1.55",
                        "cursor": "pointer",
                        "display": "block",
                        # Dim with a system tone and not with opacity: 0.45 on this body leaves the contrast
                        # well below AA.
                        "color": rx.cond(active, TEXT, TEXT_MUTED),
                    },
                ),
                # What this achievement would close from the posting. It turns the analysis into the
                # selection tool instead of a bulletin at the end of the wizard.
                rx.cond(
                    row["contributes"] != "",
                    rx.el.div(
                        rx.icon("target", size=12, stroke_width=2, style={"color": AMBER}),
                        legend("Contributes " + row["contributes"], color=AMBER),
                        style={"display": "flex", "align_items": "center", "gap": "0.375rem", "margin_top": "0.375rem"},
                    ),
                    rx.fragment(),
                ),
                # The default value this achievement is tied to: what LinkedIn said.
                #
                # It only appears when it differs from your text, which is when it means something —
                # you broke the normal and it stays broken. Until now that was only visible when
                # syncing, that is, only when LinkedIn brought something; here it is seen at rest,
                # which is where the product promises to respect it.
                rx.cond(
                    row["origin"] != "",
                    rx.el.div(
                        rx.el.div(
                            rail(BROKEN, style={"max_width": "2.75rem", "flex": "0 0 auto"}),
                            legend("You edited it · LinkedIn said", color=TEXT_MUTED),
                            style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
                        ),
                        rx.el.p(
                            row["origin"],
                            style={
                                "font_stretch": "100%",
                                "font_size": "0.8125rem",
                                "line_height": "1.5",
                                "color": TEXT_MUTED,
                                "margin_top": "0.375rem",
                            },
                        ),
                        style={
                            "border_left": f"1px solid {RULE_LINE}",
                            "padding_left": "0.75rem",
                            "margin_top": "0.5rem",
                        },
                    ),
                    rx.fragment(),
                ),
                style={"min_width": "0", "flex": "1 1 auto"},
            ),
            rail(
                rx.cond(inside, FOLDED, GAP),
                style={"max_width": "4rem", "flex": "0 0 auto", "opacity": rx.cond(active, "1", "0.45")},
            ),
            style={
                "display": "flex",
                "align_items": "flex-start",
                "gap": "0.875rem",
                "width": "100%",
                "padding": "0.5rem 0 0.5rem 1.5rem",
            },
        ),
    )


def experience_step() -> rx.Component:
    return rx.el.div(
        _missing_while_choosing(),
        _note(
            "Uncheck the achievements that do not help this application. Your master profile is "
            "not touched: what you discard will still be available for the next CV."
        ),
        _achievement_actions(),
        rx.el.div(
            rx.foreach(WizardState.guided_experience_rows, _experience_row),
            style={"border": f"1px solid {RULE_LINE}", "padding": "0.25rem 1.125rem 1rem", "width": "100%"},
        ),
        style={"display": "flex", "flex_direction": "column", "gap": "1.25rem", "width": "100%"},
    )


# --- Step 5: the rest of the profile ---------------------------------------------


def _move_button(
    icon_name: str,
    label: str,
    on_press: rx.event.EventSpec,
    *,
    disabled: rx.Var,
) -> rx.Component:
    """A reorder chevron.

    Without `aria_label` an icon-only button is announced as "button" and does not say
    what it does. And it is disabled at the ends: it used to stay active and nothing
    happened when pressed.
    """
    return secondary_button(
        rx.icon(icon_name, size=13, stroke_width=1.75),
        on_click=on_press,
        disabled=disabled,
        aria_label=label,
        title=label,
        style={"min_height": "2rem", "min_width": "2rem", "padding": "0"},
    )


def _skill_row(skill: rx.Var, index: rx.Var) -> rx.Component:
    control_id = "skill-" + skill["id"]
    return rx.el.div(
        _checkbox(
            id=control_id,
            checked=WizardState.marked_items[skill["id"]],
            on_change=lambda value: WizardState.toggle(skill["id"], value),
        ),
        rx.el.label(
            skill["name"],
            html_for=control_id,
            style={
                "font_stretch": "100%",
                "font_size": "0.875rem",
                "cursor": "pointer",
                "color": TEXT,
                "flex": "1 1 auto",
                "min_width": "0",
            },
        ),
        _move_button(
            "chevrons_up",
            "Move " + skill["name"] + " to the top",
            WizardState.skill_first(skill["id"]),
            disabled=index == 0,
        ),
        _move_button(
            "chevron_up",
            "Move up " + skill["name"],
            WizardState.move_skill(skill["id"], -1),
            disabled=index == 0,
        ),
        _move_button(
            "chevron_down",
            "Move down " + skill["name"],
            WizardState.move_skill(skill["id"], 1),
            disabled=index == WizardState.sorted_skills.length() - 1,
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "gap": "0.5rem",
            "width": "100%",
            "padding": "0.375rem 0",
            "border_bottom": f"1px solid {RULE_LINE}",
        },
    )


def _skills_shortcut() -> rx.Component:
    """Go create or edit skills without losing the half-built CV.

    My profile opens in another tab: going back to /new restarts the wizard. On return,
    "Refresh list" brings in what you changed without touching the rest of your choices.
    """
    return rx.el.div(
        rx.link(
            rx.el.span(
                rx.icon("external_link", size=13, stroke_width=1.75),
                rx.el.span("Add or edit in your profile"),
                style={"display": "flex", "align_items": "center", "gap": "0.375rem"},
            ),
            href="/profile",
            is_external=True,
            style={**style_legend(AMBER), "text_decoration": "underline", "text_underline_offset": "0.2em"},
        ),
        secondary_button(
            rx.icon("refresh_cw", size=13, stroke_width=1.75),
            "Refresh list",
            on_click=WizardState.update_skills,
            style={"min_height": "2rem", "padding": "0 0.75rem", "font_size": "0.625rem"},
        ),
        style={
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "gap": "0.75rem",
            "flex_wrap": "wrap",
            "margin_top": "0.75rem",
        },
    )


def _other_row(row: rx.Var) -> rx.Component:
    return rx.cond(
        row["row"] == "group",
        rx.el.div(
            legend(row["text"], color=AMBER),
            style={"padding": "1rem 0 0.5rem", "border_bottom": f"1px solid {RULE_LINE}"},
        ),
        rx.el.div(
            _checkbox(
                id="other-" + row["key"],
                checked=WizardState.marked_items[row["key"]],
                on_change=lambda value: WizardState.toggle(row["key"], value),
            ),
            rx.el.label(
                row["text"],
                html_for="other-" + row["key"],
                style={
                    "font_stretch": "100%",
                    "font_size": "0.875rem",
                    "cursor": "pointer",
                    "color": TEXT,
                    "min_width": "0",
                },
            ),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "0.75rem",
                "width": "100%",
                "padding": "0.375rem 0",
                "border_bottom": f"1px solid {RULE_LINE}",
            },
        ),
    )


def other_sections_step() -> rx.Component:
    return rx.el.div(
        _hint("Choose what to show. Skills come out in the order of this list."),
        rx.el.div(
            panel(
                legend("Skills", color=AMBER),
                _skills_shortcut(),
                rx.el.div(
                    rx.foreach(WizardState.sorted_skills, _skill_row),
                    style={"margin_top": "0.5rem"},
                ),
            ),
            panel(rx.foreach(WizardState.other_rows, _other_row)),
            style={
                "display": "grid",
                "grid_template_columns": ["1fr", "1fr", "repeat(2, minmax(0, 1fr))"],
                "gap": "0.75rem",
                "width": "100%",
                "align_items": "start",
                "margin_top": "1.25rem",
            },
        ),
        style={"width": "100%"},
    )


# --- Step 6: sections, analysis and generation -----------------------------------


def _section_row(kind: rx.Var, index: rx.Var) -> rx.Component:
    return rx.el.div(
        _checkbox(
            checked=WizardState.visible_sections[kind],
            on_change=lambda value: WizardState.toggle_section(kind, value),
            aria_label="Show the section " + WizardState.section_titles[kind],
        ),
        rx.el.input(
            value=WizardState.section_titles[kind],
            on_change=lambda value: WizardState.change_title(kind, value),
            aria_label="Title of the section " + WizardState.section_titles[kind],
            style={**field_style(), "flex": "1 1 auto", "min_width": "0"},
        ),
        _move_button(
            "chevron_up",
            "Move up the section " + WizardState.section_titles[kind],
            WizardState.move_section(kind, -1),
            disabled=index == 0,
        ),
        _move_button(
            "chevron_down",
            "Move down the section " + WizardState.section_titles[kind],
            WizardState.move_section(kind, 1),
            disabled=index == WizardState.section_order.length() - 1,
        ),
        style={"display": "flex", "align_items": "center", "gap": "0.5rem", "width": "100%", "padding": "0.25rem 0"},
    )


def cv_preview() -> rx.Component:
    """The real PDF, paginated, with its page count.

    The PDF is shown and not the HTML because the HTML flows continuously: it does not
    say how many pages the CV takes nor where it breaks, which is the only thing to know
    before sending it. The viewer is sized to the document so one scroll does not nest
    inside another.

    It is framed and has its solid label bar, which is how this world presents a foreign
    image: the document keeps its white inside the amber rule.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "How it prints",
                style={**style_legend(GLASS), "font_weight": "700"},
            ),
            rx.el.div(style={"flex": "1 1 auto"}),
            rx.el.span(WizardState.pages_summary, style=style_legend(GLASS)),
            rx.el.span("·", style=style_legend(GLASS)),
            rx.el.span("A4", style=style_legend(GLASS)),
            rx.el.span(WizardState.template, style=style_legend(GLASS)),
            style={
                "display": "flex",
                "align_items": "center",
                "gap": "0.5rem",
                "background": AMBER,
                "padding": "0.5rem 0.75rem",
                "flex_wrap": "wrap",
            },
        ),
        rx.el.iframe(
            src=rx.get_upload_url(WizardState.pdf_preview),
            title="CV preview as PDF",
            width="100%",
            height=WizardState.preview_height,
            style={"border": "0", "background": "white", "display": "block"},
        ),
        style={"border": f"1px solid {AMBER}", "width": "100%"},
    )


def final_actions() -> rx.Component:
    """Preview and generate, with the action's error stuck to the buttons.

    The notice lives here and not in the page header because this block sits at the
    bottom of the last step: an error drawn at the very top appears outside the viewport
    and the user only sees that nothing happens.
    """
    return rx.el.div(
        rx.el.div(
            secondary_button(
                rx.icon("eye", size=15, stroke_width=1.75),
                rx.cond(WizardState.previewing, "Rendering…", "Preview"),
                on_click=WizardState.preview,
                disabled=WizardState.previewing | WizardState.generating,
                style={**touch_target(), "min_height": "3rem", "padding": "0 1.25rem"},
            ),
            primary_button(
                rx.icon("file_down", size=15, stroke_width=2),
                rx.cond(
                    WizardState.generating,
                    "Generating the PDF…",
                    rx.cond(WizardState.generated_cv != "", "Generate another version", "Generate the PDF"),
                ),
                on_click=WizardState.generate,
                disabled=WizardState.generating | WizardState.previewing | WizardState.has_pending,
                style={**touch_target(), "min_height": "3rem", "padding": "0 1.5rem"},
            ),
            rx.cond(
                WizardState.has_pending,
                rx.el.div(
                    rail(BROKEN, style={"max_width": "3rem"}),
                    note_text("Your profile is missing " + WizardState.pending_summary + "", color=AMBER),
                    style={"display": "flex", "align_items": "center", "gap": "0.5rem"},
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "gap": "0.625rem", "align_items": "center", "flex_wrap": "wrap"},
        ),
        rx.cond(
            WizardState.action_error != "",
            rx.el.div(
                rx.icon("circle_alert", size=15, stroke_width=1.75, style={"color": AMBER, "flex": "0 0 auto"}),
                rx.el.p(
                    WizardState.action_error,
                    style={"font_stretch": "100%", "font_size": "0.875rem", "color": TEXT, "line_height": "1.5"},
                ),
                style={
                    "display": "flex",
                    "gap": "0.75rem",
                    "align_items": "flex-start",
                    "border": f"1px solid {RULE_LINE}",
                    "border_left": f"2px solid {AMBER}",
                    "padding": "0.875rem 1rem",
                    "width": "100%",
                },
            ),
            rx.fragment(),
        ),
        _result(),
        style={"display": "flex", "flex_direction": "column", "gap": "1rem", "width": "100%"},
    )


def _result() -> rx.Component:
    """Confirms the generation, right under the button that triggers it.

    It used to be drawn in the page header, and the button lives at the bottom of the
    last step after the section list, the analysis and the viewer: the confirmation
    appeared outside the viewport and the user perceived that nothing had happened.
    """
    return rx.cond(
        WizardState.generated_cv != "",
        rx.el.div(
            rx.el.div(
                rx.el.span("CV generated", style={**style_legend(GLASS), "font_weight": "700"}),
                rx.el.span(
                    WizardState.generated_cv,
                    style={
                        **style_legend(GLASS),
                        "text_transform": "none",
                        "letter_spacing": "0.04em",
                        "overflow_wrap": "anywhere",
                    },
                ),
                style={
                    "display": "flex",
                    "gap": "0.75rem",
                    "align_items": "center",
                    "background": AMBER,
                    "padding": "0.625rem 0.875rem",
                    "flex_wrap": "wrap",
                },
            ),
            rx.el.div(
                secondary_button(
                    rx.icon("file_text", size=15, stroke_width=1.75),
                    "Open the PDF",
                    on_click=WizardState.open_the_pdf,
                    style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
                ),
                secondary_button(
                    rx.icon("copy", size=15, stroke_width=1.75),
                    "Clone for another application",
                    on_click=WizardState.clone_generated,
                    style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
                ),
                secondary_button(
                    rx.icon("house", size=15, stroke_width=1.75),
                    "Back to the home page",
                    on_click=WizardState.back_to_home,
                    style={**touch_target(), "min_height": "2.75rem", "padding": "0 1rem"},
                ),
                style={"display": "flex", "gap": "0.5rem", "flex_wrap": "wrap", "padding": "0.875rem"},
            ),
            style={"border": f"1px solid {AMBER}", "width": "100%"},
        ),
        rx.fragment(),
    )


def posting_analysis() -> rx.Component:
    """What the ad asks for and which of it is missing from the CV."""
    return rx.cond(
        WizardState.has_analysis,
        _block(
            "Against the posting",
            "The terms the ad repeats, checked against what your CV says.",
            panel(
                _coverage(),
                rx.cond(
                    WizardState.missing_terms.length() > 0,
                    rx.el.div(
                        legend("Not in your CV", color=AMBER),
                        _term_list(WizardState.missing_terms, covered=False),
                        rx.el.p(
                            "If any of them describes something you have done, go back to rail 04 and check "
                            "the achievement that mentions it.",
                            style={
                                "font_stretch": "100%",
                                "font_size": "0.75rem",
                                "color": TEXT_MUTED,
                                "line_height": "1.5",
                            },
                        ),
                        style={
                            "display": "flex",
                            "flex_direction": "column",
                            "gap": "0.625rem",
                            "margin_top": "1.25rem",
                            "border_top": f"1px solid {RULE_LINE}",
                            "padding_top": "1.25rem",
                        },
                    ),
                    rx.el.div(
                        note_text("Your CV mentions everything the posting asks for", color=AMBER),
                        style={
                            "margin_top": "1.25rem",
                            "border_top": f"1px solid {RULE_LINE}",
                            "padding_top": "1.25rem",
                        },
                    ),
                ),
                rx.el.div(
                    legend("Already covered", color=TEXT_FAINT),
                    _term_list(WizardState.covered_terms, covered=True),
                    style={
                        "display": "flex",
                        "flex_direction": "column",
                        "gap": "0.625rem",
                        "margin_top": "1.25rem",
                        "border_top": f"1px solid {RULE_LINE}",
                        "padding_top": "1.25rem",
                    },
                ),
                rx.el.p(
                    "It is a help, not a verdict: it counts word occurrences, it does not understand the text.",
                    style={
                        "font_stretch": "100%",
                        "font_size": "0.75rem",
                        "color": TEXT_MUTED,
                        "font_style": "italic",
                        "margin_top": "1rem",
                        "line_height": "1.5",
                    },
                ),
                style={"width": "100%"},
            ),
        ),
        rx.fragment(),
    )


def sections_step() -> rx.Component:
    return rx.el.div(
        _block(
            "Document sections",
            "Rename the titles, hide what you do not want and reorder.",
            panel(rx.foreach(WizardState.section_order, _section_row), style={"width": "100%"}),
        ),
        posting_analysis(),
        _block(
            "Generate",
            "Preview to see the paginated document before writing the final PDF.",
            final_actions(),
        ),
        rx.cond(WizardState.pdf_preview != "", cv_preview(), rx.fragment()),
        style={"display": "flex", "flex_direction": "column", "gap": "2.5rem", "width": "100%"},
    )
