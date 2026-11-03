"""The professions editor says why Delete is disabled where every kind of user can read it."""

from cv_generator.app.components.professions import LAST_ONE_NOTE_ID, LAST_ONE_REASON, professions_editor


def test_the_reason_for_the_disabled_delete_is_visible_text_the_button_points_at() -> None:
    rendered = str(professions_editor())

    assert LAST_ONE_REASON == "A CV needs a profession: keep at least one."
    assert LAST_ONE_REASON in rendered
    assert f'id:"{LAST_ONE_NOTE_ID}"' in rendered.replace(" ", "")
    assert "aria-describedby" in rendered
    assert LAST_ONE_NOTE_ID in rendered
