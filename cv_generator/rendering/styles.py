"""From the chosen style to the CSS variables the templates read.

The style is a closed catalog, and this module is where each option gets its concrete
values. The template is not rewritten: a `:root` block that only declares what was
chosen is appended at the end, and everything else keeps the value the template gives it.
It goes after the template's CSS because, at equal specificity, the last `:root`
declaration wins: placed before, the template's values would override the choice.
"""

import math
from dataclasses import dataclass

from cv_generator.models.style import (
    MAX_LINE_HEIGHT,
    MIN_LINE_HEIGHT,
    FontSize,
    PaletteColor,
    Style,
    StyleFont,
)


@dataclass(frozen=True)
class ColorTones:
    """The four tones a template uses to express a color.

    `accent` is read on white; `background` is a dark block (the sidebar, the bands)
    that `tint` is read on; `rule_line` is just a line, with no text on top.
    """

    accent: str
    background: str
    tint: str
    rule_line: str


@dataclass(frozen=True)
class FontPair:
    """Complete CSS stacks for the headings and for the body text."""

    titles: str
    text: str


# Every text tone meets WCAG AA (4.5:1) against the background it is read on;
# test_every_palette_color_meets_aa checks it. The teal ones come from the `sidebar` template's bar.
PALETTE: dict[PaletteColor, ColorTones] = {
    PaletteColor.TEAL: ColorTones("#00796b", "#00695c", "#d4ece7", "#7fb3ac"),
    PaletteColor.BLUE: ColorTones("#1565c0", "#0d47a1", "#d6e4f5", "#8fb4e3"),
    PaletteColor.RED: ColorTones("#c62828", "#b71c1c", "#fbdcdc", "#e69a9a"),
    PaletteColor.BLACK: ColorTones("#263238", "#1c262b", "#dde3e6", "#90a4ae"),
    PaletteColor.GRAY: ColorTones("#616161", "#424242", "#e6e6e6", "#9e9e9e"),
    PaletteColor.BROWN: ColorTones("#6d4c41", "#4e342e", "#eadcd7", "#b79a90"),
}

# The first family of each stack is the chosen one; the generic one at the end avoids
# falling back to the engine's default font when the chosen one is not installed.
FONTS: dict[StyleFont, FontPair] = {
    StyleFont.CLASSIC: FontPair("Georgia, serif", "Georgia, serif"),
    StyleFont.MODERN: FontPair("'Avenir Next', sans-serif", "'Avenir Next', sans-serif"),
    StyleFont.ELEGANT: FontPair("Baskerville, serif", "Baskerville, serif"),
    StyleFont.TECH: FontPair("Menlo, monospace", "'Helvetica Neue', sans-serif"),
    StyleFont.PROFESSIONAL: FontPair("'Gill Sans', sans-serif", "'Gill Sans', sans-serif"),
}

SCALES: dict[FontSize, float] = {
    FontSize.SMALL: 0.92,
    FontSize.MEDIUM: 1.0,
    FontSize.LARGE: 1.08,
}

COLOR_NAMES: dict[PaletteColor, str] = {
    PaletteColor.TEAL: "Teal",
    PaletteColor.BLUE: "Blue",
    PaletteColor.RED: "Red",
    PaletteColor.BLACK: "Black",
    PaletteColor.GRAY: "Gray",
    PaletteColor.BROWN: "Brown",
}

FONT_NAMES: dict[StyleFont, str] = {
    StyleFont.CLASSIC: "Classic",
    StyleFont.MODERN: "Modern",
    StyleFont.ELEGANT: "Elegant",
    StyleFont.TECH: "Tech",
    StyleFont.PROFESSIONAL: "Professional",
}

SIZE_NAMES: dict[FontSize, str] = {
    FontSize.SMALL: "Small text",
    FontSize.MEDIUM: "Medium text",
    FontSize.LARGE: "Large text",
}


def css_for_style(style: Style) -> str:
    """`:root` block with the variables of the fields that are set; empty if there are none.

    Declaring only what was chosen is what lets each template keep the rest of its
    design, and lets an empty style add not a single character to the CSS.

    When the CV changes the font, the size or the line height, it changes where each line
    falls (small text shortens the text, but a wider font lengthens it), and that is why
    it also lets entries split across pages (`--entry-break`): a long entry that cannot
    be split jumps whole to page 2 and page 1 is left with only the header. When it
    splits, the entry header stays with its first achievement (`--break-after-header`).
    Color moves no line: with only a color, or with no style, the entry paginates the
    way the template draws it, just like in the CVs already generated.
    """
    if style.empty:
        return ""

    variables: list[tuple[str, str]] = []
    if style.color is not None:
        tones = PALETTE[style.color]
        variables += [
            ("--accent", tones.accent),
            ("--background", tones.background),
            ("--tint", tones.tint),
            ("--rule", tones.rule_line),
        ]
    if style.font is not None:
        fonts = FONTS[style.font]
        variables += [("--heading-font", fonts.titles), ("--body-font", fonts.text)]
    if style.size is not None:
        variables.append(("--scale", str(SCALES[style.size])))
    if style.line_height is not None:
        variables.append(("--line-height", str(style.line_height)))
    if style.font is not None or style.size is not None or style.line_height is not None:
        variables += [("--entry-break", "auto"), ("--break-after-header", "avoid")]

    body = "\n".join(f"  {name}: {value};" for name, value in variables)
    return f":root {{\n{body}\n}}"


def line_height_step(current: float, direction: int) -> float:
    """The line height after one step of one tenth towards `direction` (+1 or -1).

    From a template's own value (1.45) the first step goes to the nearest tenth in the
    pressed direction, not to the nearest one overall: that way "+" never goes down and
    "-" never goes up. The tolerance absorbs the floating point error of `current * 10`.
    """
    tenths = current * 10
    target = (math.floor(tenths + 1e-6) + 1) if direction > 0 else (math.ceil(tenths - 1e-6) - 1)
    return round(min(MAX_LINE_HEIGHT, max(MIN_LINE_HEIGHT, target / 10)), 1)


def line_height_label(value: float) -> str:
    """The line height as it reads on screen: with at least one decimal.

    "1.45" and "1.5" come out as they are; 2.0 comes out "2.0" and not "2", which next to
    "1.9" looked like another scale.
    """
    text = f"{value:g}" if value != int(value) else f"{value:.1f}"
    return text
