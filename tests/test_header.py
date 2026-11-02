"""The header marks the page you are on."""

from cv_generator.app.components.header import _current_path, language_switch
from cv_generator.app.states.home_state import HomeState


def test_the_current_path_ignores_a_trailing_slash() -> None:
    """With /profile/ in the address, "My CVs" was marked: only the root was left to deduce."""
    assert "Rstrip" in str(_current_path())


def test_the_language_switch_compiles_with_a_button_per_language() -> None:
    rendered = str(language_switch(HomeState.language, HomeState.switch_language))

    assert "content-language-es" in rendered
    assert "content-language-en" in rendered
    assert "Content language" in rendered
