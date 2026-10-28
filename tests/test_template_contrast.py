"""Contrast of the templates' text against the background it is read on.

The test computes the WCAG ratio instead of comparing against a list of colors: pinning
the concrete hex values would turn the test into a copy of the CSS, and it would pass
just the same if someone replaced a color with another one just as unreadable.
"""

import re
from pathlib import Path

import pytest

from cv_generator.models.style import PaletteColor, Style
from cv_generator.rendering.renderer import TEMPLATES_DIR, available_templates
from cv_generator.rendering.styles import css_for_style

# WCAG 2.1 AA for normal text. The CV paper is white except where the template paints a
# background, like the side bar of `sidebar`.
MIN_AA_RATIO = 4.5
WHITE = (255, 255, 255)

RULE = re.compile(r"([.#][\w_-]+(?:::?[\w-]+)?[^{}]*)\{([^}]*)\}")
# Without the lookbehind, `background-color: #00695c` counted as a text color.
COLOR_VALUE = r"(#[0-9a-fA-F]{3,6}\b|var\(--[\w-]+\))"
COLOR = re.compile(r"(?<![\w-])color:\s*" + COLOR_VALUE)
BACKGROUND = re.compile(r"background(?:-color)?:\s*" + COLOR_VALUE)
ROOT_BLOCK = re.compile(r":root\s*\{([^}]*)\}")
DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")
COLOR_DECLARATION = re.compile(r"(?<![\w-])(?:color|background(?:-color)?)\s*:\s*([^;}]*)")
REFERENCE = re.compile(r"var\((--[\w-]+)\)")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _to_rgb(hexadecimal: str) -> tuple[int, int, int]:
    value = hexadecimal.lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _luminance(color: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        ratio = value / 255
        return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4

    red, green, blue = color
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def _contrast(one: tuple[int, int, int], other_one: tuple[int, int, int]) -> float:
    light, dark = sorted((_luminance(one), _luminance(other_one)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _without_comments(css: str) -> str:
    """The CSS without its comments, which is the only thing the regexes below can read.

    The templates quote selectors in their comments (`.sidebar .section__title`), and read
    as CSS that text opened a fake rule that swallowed the next one.
    """
    return COMMENT.sub("", css)


def _variables(css: str) -> dict[str, str]:
    """The variables the `:root` blocks declare; if one repeats, the last one wins."""
    return {
        name: value.strip()
        for block in ROOT_BLOCK.finditer(_without_comments(css))
        for name, value in DECLARATION.findall(block.group(1))
    }


def _resolve(value: str, variables: dict[str, str]) -> str:
    """The literal value of a `var(--x)`; fails if nobody defines that variable.

    Letting the unresolved reference through would take the rule out of the measurement
    without warning.
    """
    views: list[str] = []
    while reference := REFERENCE.fullmatch(value):
        name = reference.group(1)
        if name not in variables:
            raise ValueError(f"the variable {name} has no value: the rule cannot be measured")
        if name in views:
            raise ValueError(f"the variable {name} refers to itself: {' -> '.join([*views, name])}")
        views.append(name)
        value = variables[name]
    return value


def _require_measurable_var(selector: str, body: str) -> None:
    """Fails if a color or background uses `var()` in a form the regexes do not read.

    With `var(--x, #fff)`, `var( --x )` or another form, COLOR and BACKGROUND capture
    nothing and the rule would silently leave the measurement, which is exactly what this
    test prevents.
    """
    for declaration in COLOR_DECLARATION.finditer(body):
        value = declaration.group(1).removesuffix("!important").strip()
        if "var(" in value and not REFERENCE.fullmatch(value):
            raise ValueError(f"{selector}: `{declaration.group(0).strip()}` cannot be measured; use a plain var(--x)")


def _background_of(selector: str, own: str | None, backgrounds: dict[str, str]) -> tuple[int, int, int]:
    """The background a text rule is read on.

    It is the one the rule itself paints, or that of the closest ancestor that appears in
    the selector and paints one. That is why text on a painted background names that
    ancestor (`.sidebar .section__title`): without naming it, the test would measure it
    against the paper. The values arrive already resolved, without `var()`.
    """
    if own is not None:
        return _to_rgb(own)
    for ancestor in reversed(selector.split()[:-1]):
        if ancestor in backgrounds:
            return _to_rgb(backgrounds[ancestor])
    return WHITE


def _text_and_background(
    css: str, overridden: dict[str, str] | None = None
) -> list[tuple[str, str, tuple[int, int, int]]]:
    """Every rule that colors a text, with the background it is read on.

    The `var()` are resolved with the CSS's own variables and, on top, the `overridden`
    ones: that is what the chosen style's `:root` does over the template.
    """
    css = _without_comments(css)
    variables = _variables(css) | (overridden or {})
    rules = [(rule.group(1).strip(), rule.group(2)) for rule in RULE.finditer(css)]
    for selector, body in rules:
        _require_measurable_var(selector, body)
    backgrounds = {
        selector.strip(): _resolve(background.group(1), variables)
        for selectors, body in rules
        if (background := BACKGROUND.search(body))
        for selector in selectors.split(",")
    }
    return [
        (
            selector,
            _resolve(color.group(1), variables),
            _background_of(selector, _resolve(background.group(1), variables) if background else None, backgrounds),
        )
        for selector, body in rules
        if (color := COLOR.search(body))
        for background in [BACKGROUND.search(body)]
    ]


def _declared_colors(
    slug: str, overridden: dict[str, str] | None = None
) -> list[tuple[str, str, tuple[int, int, int]]]:
    css = (TEMPLATES_DIR / slug / "styles.css").read_text(encoding="utf-8")
    return _text_and_background(css, overridden)


def test_contrast_calculation_recognizes_the_extremes() -> None:
    """Without this, an error in the formula would make the templates test pass vacuously."""
    assert _contrast((0, 0, 0), WHITE) == pytest.approx(21.0, abs=0.05)
    assert _contrast(WHITE, WHITE) == pytest.approx(1.0, abs=0.01)


def test_measures_text_against_its_surrounding_background() -> None:
    """Without this, white text on a dark bar would fail measured against the paper, and
    gray text on that bar would pass for the same reason."""
    css = (
        ".bar { background: #00695c; color: #ffffff; }"
        ".bar .detail { color: #cfe8e2; }"
        ".band { background-color: #eeeeee; }"
        ".loose { color: #333333; }"
    )

    measured = {selector: (color, background) for selector, color, background in _text_and_background(css)}

    assert measured[".bar"] == ("#ffffff", _to_rgb("#00695c"))
    assert measured[".bar .detail"] == ("#cfe8e2", _to_rgb("#00695c"))
    assert measured[".loose"] == ("#333333", WHITE)
    assert ".band" not in measured, "a background is not a text color"


def test_resolves_the_template_variables() -> None:
    css = (
        ":root { --background: #00695c; --accent: #00796b; }"
        ".bar { background: var(--background); color: #ffffff; }"
        ".title { color: var(--accent); }"
    )

    measured = {selector: (color, background) for selector, color, background in _text_and_background(css)}

    assert measured[".bar"] == ("#ffffff", _to_rgb("#00695c"))
    assert measured[".title"] == ("#00796b", WHITE)


def test_overrides_change_what_is_measured() -> None:
    css = ":root { --background: #00695c; } .bar { background: var(--background); color: #ffffff; }"

    measured = {
        selector: background for selector, _, background in _text_and_background(css, {"--background": "#c62828"})
    }

    assert measured[".bar"] == _to_rgb("#c62828")


def test_a_variable_without_value_fails_the_measurement() -> None:
    """Without this, a rule with var() would be left out of the test without anyone noticing."""
    with pytest.raises(ValueError, match="--missing"):
        _text_and_background(".x { color: var(--missing); }")


def test_resolves_variables_that_point_to_other_variables() -> None:
    css = ":root { --base: #00796b; --accent: var(--base); } .title { color: var(--accent); }"

    assert _text_and_background(css) == [(".title", "#00796b", WHITE)]


def test_a_cyclic_or_broken_variable_chain_fails_the_measurement() -> None:
    with pytest.raises(ValueError, match="--a"):
        _text_and_background(":root { --a: var(--b); --b: var(--a); } .x { color: var(--a); }")
    with pytest.raises(ValueError, match="--absent"):
        _text_and_background(":root { --a: var(--absent); } .x { color: var(--a); }")


@pytest.mark.parametrize(
    "declaration",
    ["color: var(--accent, #00796b)", "color: var( --accent )", "background: var(--accent, #fff)"],
)
def test_an_unreadable_var_does_not_silently_leave_the_measurement(declaration: str) -> None:
    with pytest.raises(ValueError, match="cannot be measured"):
        _text_and_background(f":root {{ --accent: #00796b; }} .x {{ {declaration}; }}")


def test_accepts_important_after_a_simple_var() -> None:
    css = ":root { --accent: #00796b; } .x { color: var(--accent) !important; }"

    assert _text_and_background(css) == [(".x", "#00796b", WHITE)]


def test_a_comment_is_not_read_as_a_selector() -> None:
    """The templates quote selectors in their comments, like `.sidebar .section__title`.

    Read as CSS, that text started a fake rule that swallowed the next one: here `.loose`
    would be measured against the background of `.bar`, with a selector that does not exist.
    """
    css = (
        ".bar { background: #00695c; color: #ffffff; }"
        "/* the text on the bar names its container: `.bar .title` */"
        ".loose { color: #333333; }"
    )

    measured = {selector: (color, background) for selector, color, background in _text_and_background(css)}

    assert measured == {".bar": ("#ffffff", _to_rgb("#00695c")), ".loose": ("#333333", WHITE)}


def test_a_comment_before_page_does_not_break_the_measurement() -> None:
    """Without stripping the comments, the `@page` with `var()` in the gradient ended up inside
    the fake rule and the `var()` guard failed over a rule that is not measured."""
    css = (
        ":root { --background: #00695c; }"
        "/* the bar is painted twice, see `.bar` */"
        "@page { background: linear-gradient(to right, var(--background) 64mm, #ffffff 64mm); }"
    )

    assert _text_and_background(css) == []


def test_a_comment_inside_root_does_not_cut_the_variables() -> None:
    css = ":root { /* the accent of the job titles } */ --accent: #00796b; --background: #00695c; }"

    assert _variables(css) == {"--accent": "#00796b", "--background": "#00695c"}


@pytest.mark.parametrize("color", [None, *PaletteColor])
@pytest.mark.parametrize("slug", available_templates())
def test_all_template_text_meets_aa(slug: str, color: PaletteColor | None) -> None:
    overridden = _variables(css_for_style(Style(color=color)))
    unreadable = [
        f"{selector} uses {ink} on {background} ({_contrast(_to_rgb(ink), background):.2f}:1)"
        for selector, ink, background in _declared_colors(slug, overridden)
        if _contrast(_to_rgb(ink), background) < MIN_AA_RATIO
    ]

    assert not unreadable, f"contrast below AA in {slug} with {color}: " + "; ".join(unreadable)


@pytest.mark.parametrize("slug", available_templates())
def test_the_template_declares_some_color(slug: str) -> None:
    """Guard against a regex that stops finding rules and makes the test trivial."""
    assert _declared_colors(slug)


# A template can be sober, but below this there is no hierarchy left: it is a single
# repeated tone. It is the symptom of having pushed every color up to the AA threshold at
# once instead of rearranging the whole scale.
MIN_TONES = 3


@pytest.mark.parametrize("slug", available_templates())
def test_the_template_keeps_its_tonal_scale(slug: str) -> None:
    """A template's identity is the hierarchy between its tones, not a specific tone.

    When fixing contrast it is easy to push every color to the minimum that passes AA; the
    result meets the standard and flattens the gradation that set that template apart.
    """
    tones = {color for _, color, _ in _declared_colors(slug)}

    assert len(tones) >= MIN_TONES, f"the scale of {slug} flattened to {len(tones)} tones: {sorted(tones)}"


def test_no_template_was_left_without_a_stylesheet() -> None:
    for slug in available_templates():
        assert (TEMPLATES_DIR / slug / "styles.css").is_file(), slug


def test_there_are_templates_to_check() -> None:
    """If `available_templates` returned nothing, the parametrized tests would not run."""
    assert len(available_templates()) == len(list(Path(TEMPLATES_DIR).glob("*/meta.json")))
    assert available_templates()


BREAK_RULES = (
    ("orphans", "a stray line at the foot of the page"),
    ("widows", "a stray line at the top of the next one"),
    ("break-after", "a section title hanging at the end of the page"),
    ("break-inside", "a bullet split across two pages"),
)


@pytest.mark.parametrize("slug", available_templates())
@pytest.mark.parametrize(("prop_name", "symptom"), BREAK_RULES)
def test_the_template_controls_page_breaks(slug: str, prop_name: str, symptom: str) -> None:
    """The deliverable is a paginated PDF: without these rules the break falls wherever it falls."""
    css = (TEMPLATES_DIR / slug / "styles.css").read_text(encoding="utf-8")

    assert prop_name in css, f"{slug} does not declare {prop_name}: it allows {symptom}"


@pytest.mark.parametrize("slug", available_templates())
def test_the_template_declares_the_page_size(slug: str) -> None:
    css = (TEMPLATES_DIR / slug / "styles.css").read_text(encoding="utf-8")

    assert "@page" in css and "A4" in css, f"{slug} does not set the page size"
