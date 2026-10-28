"""Text normalization shared across the project."""

import unicodedata


def strip_accents(text: str) -> str:
    """Decomposes accented characters and drops the diacritical marks."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def plural(count: int, singular: str, plural_: str) -> str:
    """Makes the noun agree with its count: "1 change", not "1 changes"."""
    return f"{count} {singular if count == 1 else plural_}"


def normalize(text: str) -> str:
    """Canonical form for comparisons: no accents, lowercase and no extra spaces."""
    return " ".join(strip_accents(text).lower().split())
