import pytest

from cv_generator.models.sections import SectionKind
from cv_generator.rendering.i18n import available_languages, default_sections, load_language


def test_declares_the_languages_that_have_a_translation_file() -> None:
    assert sorted(available_languages()) == ["en", "es"]


def test_loads_the_twelve_months_in_spanish() -> None:
    translations = load_language("es")

    assert translations.months[0] == "enero"
    assert translations.months[11] == "diciembre"


def test_loads_the_twelve_months_in_english() -> None:
    translations = load_language("en")

    assert translations.months[2] == "march"


def test_gives_the_default_section_titles_in_spanish() -> None:
    translations = load_language("es")

    assert translations.sections[SectionKind.EXPERIENCE] == "Experiencia laboral"
    assert translations.sections[SectionKind.REFERENCES] == "Referencias personales"


def test_gives_the_default_section_titles_in_english() -> None:
    translations = load_language("en")

    assert translations.sections[SectionKind.EXPERIENCE] == "Work Experience"


@pytest.mark.parametrize("language", available_languages())
def test_every_language_translates_every_section(language: str) -> None:
    translations = load_language(language)

    assert set(translations.sections) == set(SectionKind)


@pytest.mark.parametrize("language", available_languages())
def test_every_language_declares_exactly_twelve_months(language: str) -> None:
    assert len(load_language(language).months) == 12


def test_fails_clearly_for_a_language_without_translation() -> None:
    with pytest.raises(ValueError, match="unsupported language"):
        load_language("fr")


@pytest.mark.parametrize("malicious_code", ["../secrets", "es/../../etc/passwd", "/etc/passwd"])
def test_rejects_language_codes_pointing_outside_the_directory(malicious_code: str) -> None:
    with pytest.raises(ValueError, match="unsupported language"):
        load_language(malicious_code)


def test_builds_the_default_sections_in_a_sensible_order() -> None:
    sections = default_sections("es")

    assert [section.kind for section in sections] == [
        SectionKind.PROFILE,
        SectionKind.EXPERIENCE,
        SectionKind.EDUCATION,
        SectionKind.SKILLS,
        SectionKind.LANGUAGES,
        SectionKind.COURSES,
        SectionKind.HOBBIES,
        SectionKind.REFERENCES,
    ]


def test_default_sections_start_visible_and_numbered_from_one() -> None:
    sections = default_sections("es")

    assert all(section.visible for section in sections)
    assert [section.order for section in sections] == list(range(1, 9))


def test_default_sections_take_the_language_title() -> None:
    assert default_sections("es")[1].title == "Experiencia laboral"
    assert default_sections("en")[1].title == "Work Experience"


def test_default_sections_cover_every_kind() -> None:
    assert {section.kind for section in default_sections("es")} == set(SectionKind)


@pytest.mark.parametrize(
    ("language", "phone", "address"), [("es", "Teléfono", "Dirección"), ("en", "Phone", "Address")]
)
def test_every_language_labels_the_contact_details(language: str, phone: str, address: str) -> None:
    """The templates that label the contact write those words in the CV language."""
    captions = load_language(language).contact

    assert captions.phone == phone
    assert captions.address == address
