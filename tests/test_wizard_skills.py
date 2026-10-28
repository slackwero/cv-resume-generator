"""Bringing into the wizard the skills you changed in My profile without losing your half-built CV."""

from cv_generator.app.states.wizard_state import _order_with_profile


def test_keeps_your_order_drops_removed_and_appends_new_ones() -> None:
    assert _order_with_profile(["python", "go", "bash"], ["go", "python", "terraform"]) == [
        "python",
        "go",
        "terraform",
    ]


def test_without_profile_changes_the_order_stays() -> None:
    assert _order_with_profile(["b", "a"], ["a", "b"]) == ["b", "a"]
