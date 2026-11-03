"""The placeholder for a required text the importer could not fill, and the rule that spots it.

It lives apart from services/profile.py so translations.py can use it too: profile.py
imports translations.py, so translations.py cannot import profile.py back.
"""

# Placeholder for the required fields the importer cannot fill: LinkedIn does not
# provide the phone. The profile is created anyway and the app asks you to complete it,
# instead of blocking the first sync over a piece of data the source never brings.
PENDING_FIELD = "PENDING"


def is_usable_text(text: str | None) -> bool:
    """True when a text is really written: not empty and not the `PENDING` placeholder."""
    return bool(text) and text != PENDING_FIELD
