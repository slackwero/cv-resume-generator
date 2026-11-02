from pathlib import Path

from cv_generator.services.preferences import load_content_language, save_content_language, starting_language


def test_a_missing_settings_file_has_no_remembered_language(tmp_path: Path) -> None:
    assert load_content_language(tmp_path) is None


def test_the_saved_language_is_remembered(tmp_path: Path) -> None:
    save_content_language(tmp_path, "es")

    assert load_content_language(tmp_path) == "es"


def test_a_corrupt_settings_file_has_no_remembered_language(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")

    assert load_content_language(tmp_path) is None


def test_a_settings_file_of_another_shape_has_no_remembered_language(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("[1, 2]", encoding="utf-8")

    assert load_content_language(tmp_path) is None


def test_an_unavailable_remembered_language_falls_back_to_the_source() -> None:
    assert starting_language("fr", "es") == "es"
    assert starting_language("es", "en") == "es"


def test_with_nothing_known_it_starts_in_english() -> None:
    assert starting_language(None, None) == "en"
