"""A CV's style: what is customized in the template, and its validation."""

import pytest
from pydantic import ValidationError

from cv_generator.app.states.wizard_state import style_from_vars, vars_from_style
from cv_generator.models.cv import Selection
from cv_generator.models.style import FontSize, PaletteColor, Style, StyleFont
from cv_generator.rendering.styles import (
    COLOR_NAMES,
    FONT_NAMES,
    FONTS,
    PALETTE,
    SCALES,
    SIZE_NAMES,
    css_for_style,
    line_height_label,
    line_height_step,
)
from tests.test_template_contrast import WHITE, _contrast, _to_rgb


def test_a_style_without_fields_is_empty() -> None:
    assert Style().empty
    assert not Style(color=PaletteColor.RED).empty


def test_a_recipe_without_style_reads_as_uncustomized() -> None:
    """Recipes and snapshots older than the customization do not carry the field."""
    assert Selection.model_validate({}).style == Style()


@pytest.mark.parametrize("value", [1.2, 1.5, 2.0])
def test_accepts_line_heights_in_range_in_tenths(value: float) -> None:
    assert Style(line_height=value).line_height == value


@pytest.mark.parametrize("value", [1.1, 2.1, 1.45, 0.0])
def test_rejects_line_heights_out_of_range_or_step(value: float) -> None:
    with pytest.raises(ValidationError):
        Style(line_height=value)


def test_normalizes_line_height_to_one_tenth() -> None:
    assert Style(line_height=1.3000000000000003).line_height == 1.3


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        Style.model_validate({"color": "fuchsia"})


def test_an_empty_style_produces_no_css() -> None:
    assert css_for_style(Style()) == ""


def test_overrides_only_what_was_chosen() -> None:
    css = css_for_style(Style(size=FontSize.LARGE))
    assert "--scale: 1.08" in css
    assert "--accent" not in css
    assert "--body-font" not in css
    assert "--line-height" not in css


def test_the_color_writes_its_four_tones() -> None:
    tones = PALETTE[PaletteColor.RED]
    css = css_for_style(Style(color=PaletteColor.RED))
    for variable, value in [
        ("--accent", tones.accent),
        ("--background", tones.background),
        ("--tint", tones.tint),
        ("--rule", tones.rule_line),
    ]:
        assert f"{variable}: {value}" in css


@pytest.mark.parametrize(
    "style",
    [
        Style(size=FontSize.LARGE),
        Style(size=FontSize.SMALL),
        Style(line_height=2.0),
        Style(font=StyleFont.ELEGANT),
        Style(color=PaletteColor.RED, font=StyleFont.CLASSIC),
    ],
)
def test_what_changes_text_flow_lets_entries_split(style: Style) -> None:
    """The font, the size or the line height move where each line falls, and a long entry
    that cannot be split jumps whole to page 2: page 1 is left with the header and the
    profile. A font alone too, because each family has its own width."""
    css = css_for_style(style)

    assert "--entry-break: auto" in css
    assert "--break-after-header: avoid" in css, "once split, the header has to stay with its first achievement"


@pytest.mark.parametrize("style", [Style(), Style(color=PaletteColor.RED)])
def test_what_does_not_change_text_flow_leaves_entry_breaks_alone(style: Style) -> None:
    """Color moves no line: the entry paginates the way the template draws it."""
    css = css_for_style(style)

    assert "--entry-break" not in css
    assert "--break-after-header" not in css


@pytest.mark.parametrize("color", list(PaletteColor))
def test_every_palette_color_meets_aa(color: PaletteColor) -> None:
    tones = PALETTE[color]
    assert _contrast(_to_rgb(tones.accent), WHITE) >= 4.5
    assert _contrast(WHITE, _to_rgb(tones.background)) >= 4.5
    assert _contrast(_to_rgb(tones.tint), _to_rgb(tones.background)) >= 4.5


@pytest.mark.parametrize("font", list(StyleFont))
def test_every_font_stack_ends_in_a_generic_family(font: StyleFont) -> None:
    """Outside the user's Mac, the stack falls back to something readable instead of the engine's default font."""
    for stack in (FONTS[font].titles, FONTS[font].text):
        assert stack.rsplit(",", 1)[-1].strip() in {"serif", "sans-serif", "monospace"}


def test_every_option_has_its_display_name() -> None:
    assert set(COLOR_NAMES) == set(PaletteColor)
    assert set(FONT_NAMES) == set(StyleFont)
    assert set(SIZE_NAMES) == set(FontSize)
    assert set(PALETTE) == set(PaletteColor)
    assert set(FONTS) == set(StyleFont)
    assert set(SCALES) == set(FontSize)


@pytest.mark.parametrize(
    ("current", "direction", "expected"),
    [
        (1.45, 1, 1.5),
        (1.45, -1, 1.4),
        (1.5, 1, 1.6),
        (1.5, -1, 1.4),
        (2.0, 1, 2.0),
        (1.2, -1, 1.2),
        (1.55, 1, 1.6),
        (1.35, -1, 1.3),
    ],
)
def test_line_height_step(current: float, direction: int, expected: float) -> None:
    assert line_height_step(current, direction) == expected


@pytest.mark.parametrize(("value", "text"), [(1.45, "1.45"), (1.5, "1.5"), (2.0, "2.0"), (1.2, "1.2")])
def test_line_height_shows_with_at_least_one_decimal(value: float, text: str) -> None:
    """Next to "1.9", a bare "2" looks like it belongs to another scale."""
    assert line_height_label(value) == text


@pytest.mark.parametrize(
    "style",
    [
        Style(),
        Style(
            color=PaletteColor.BROWN,
            font=StyleFont.TECH,
            size=FontSize.SMALL,
            line_height=1.7,
        ),
    ],
)
def test_clone_copies_the_style(style: Style) -> None:
    """Cloning puts the recipe's style in the wizard controls, and the new CV is built from
    those controls: the round trip has to give back the same one."""
    controls = vars_from_style(style)

    assert style_from_vars(**controls) == style


def test_an_empty_style_leaves_the_controls_at_the_template_values() -> None:
    """Empty and 0.0 are what the wizard reads as "the template's"."""
    assert vars_from_style(Style()) == {
        "style_color": "",
        "style_font": "",
        "style_size": "",
        "style_line_height": 0.0,
    }
