"""Small settings that outlive a session: the language the profile is shown in."""

from pathlib import Path

from cv_generator.rendering.i18n import available_languages
from cv_generator.storage.repo import read_json, save_json

# Matches the application's default language (`app/config.py`); services never import `app`.
DEFAULT_LANGUAGE = "en"

SETTINGS_FILE = "settings.json"


def load_content_language(data_dir: Path) -> str | None:
    """The language remembered from the last session, or None when there is none.

    A missing, unreadable or invalid file all mean "nothing remembered": the settings are a
    convenience and must never stop the app from starting.
    """
    try:
        value = read_json(data_dir / SETTINGS_FILE).get("content_language")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def save_content_language(data_dir: Path, language: str) -> None:
    """Remembers the language the profile is shown in."""
    save_json(data_dir / SETTINGS_FILE, {"content_language": language})


def starting_language(remembered: str | None, source: str | None) -> str:
    """The language to open the profile in: the remembered one, else the profile's source."""
    if remembered in available_languages():
        return str(remembered)
    return source or DEFAULT_LANGUAGE
