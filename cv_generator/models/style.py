"""Visual customization of a CV: color, font, size and line height.

Each template brings its own design and the style only adjusts it; it does not replace it.
That is why every field is optional and `None` means "the template's": an
uncustomized CV renders exactly as always, and recipes and history entries older
than this option (which do not carry the field) are read unchanged.

The values are closed catalogs, not free CSS: the user picks among options tested
for good contrast, and the template translates each one into its variables.
"""

from enum import StrEnum

from pydantic import BaseModel, field_validator

MIN_LINE_HEIGHT = 1.2
MAX_LINE_HEIGHT = 2.0


class PaletteColor(StrEnum):
    """The accent colors on offer."""

    TEAL = "teal"
    BLUE = "blue"
    RED = "red"
    BLACK = "black"
    GRAY = "gray"
    BROWN = "brown"


class StyleFont(StrEnum):
    """The font families on offer."""

    CLASSIC = "classic"
    MODERN = "modern"
    ELEGANT = "elegant"
    TECH = "tech"
    PROFESSIONAL = "professional"


class FontSize(StrEnum):
    """The font sizes on offer, relative to the template's."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Style(BaseModel):
    """What a CV changes from its template; `None` keeps the template's value."""

    color: PaletteColor | None = None
    font: StyleFont | None = None
    size: FontSize | None = None
    line_height: float | None = None

    @field_validator("line_height")
    @classmethod
    def _validate_line_height(cls, value: float | None) -> float | None:
        """Accepts tenths within the range; nothing else has a control that produces it."""
        if value is None:
            return None
        if not MIN_LINE_HEIGHT <= value <= MAX_LINE_HEIGHT:
            raise ValueError(f"The line height must be between {MIN_LINE_HEIGHT} and {MAX_LINE_HEIGHT}.")
        if abs(round(value * 10) - value * 10) >= 1e-6:
            raise ValueError("The line height goes in steps of one tenth.")
        return round(value, 1)

    @property
    def empty(self) -> bool:
        """True if it customizes nothing and the CV uses the template as is."""
        return all(value is None for value in (self.color, self.font, self.size, self.line_height))
