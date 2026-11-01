"""The header marks the page you are on."""

from cv_generator.app.components.header import _current_path


def test_the_current_path_ignores_a_trailing_slash() -> None:
    """With /profile/ in the address, "My CVs" was marked: only the root was left to deduce."""
    assert "Rstrip" in str(_current_path())
