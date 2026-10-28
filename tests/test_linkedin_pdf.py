from pathlib import Path

import pytest

from cv_generator.importers.base import ProfileDraft
from cv_generator.importers.linkedin_pdf import parse_linkedin_profile

FIXTURE = Path(__file__).parent / "fixtures" / "linkedin_profile.txt"


@pytest.fixture
def draft() -> ProfileDraft:
    return parse_linkedin_profile(FIXTURE.read_text(encoding="utf-8"))


def test_extracts_the_name_and_splits_first_and_last_name(draft: ProfileDraft) -> None:
    assert draft.personal.first_name == "Nombre"
    assert draft.personal.last_name == "Apellido"


def test_takes_the_linkedin_headline_as_profession(draft: ProfileDraft) -> None:
    assert draft.personal.profession == "Platform Engineer | SRE | Azure | Linux"


def test_extracts_the_email_and_location(draft: ProfileDraft) -> None:
    assert draft.personal.email == "correo@ejemplo.com"
    assert draft.personal.country == "Área metropolitana de Madrid, Comunidad de Madrid, España"


def test_turns_the_about_section_into_a_profile_text(draft: ProfileDraft) -> None:
    assert len(draft.profile_texts) == 1
    assert draft.profile_texts[0].text.startswith("Ingeniera con diez años")
    assert "automatizacion." in draft.profile_texts[0].text


def test_joins_skills_split_by_column_width(draft: ProfileDraft) -> None:
    names = [skill.name for skill in draft.skills]

    assert "Continuous Integration and Delivery (CI/CD)" in names
    assert "Kubernetes" in names


def test_splits_the_language_from_its_level(draft: ProfileDraft) -> None:
    languages = {language.language: language.level for language in draft.languages}

    assert languages["Español"] == "Native or Bilingual"
    assert languages["Inglés"] == "Professional Working"


def test_recognizes_every_experience(draft: ProfileDraft) -> None:
    assert [experience.role for experience in draft.experiences] == [
        "Platform Engineer - SRE",
        "SRE Lead",
        "Technical Lead",
        "Technical Lead",
        "Full Stack Engineer",
    ]


def test_propagates_the_company_to_the_roles_grouped_under_it(draft: ProfileDraft) -> None:
    companies = [experience.company for experience in draft.experiences]

    assert companies[3] == "Banco Agrupado C.A."
    assert companies[4] == "Banco Agrupado C.A.", "the second position does not repeat the company in the PDF"


def test_converts_spanish_dates_to_year_month(draft: ProfileDraft) -> None:
    first_one = draft.experiences[0]

    assert first_one.start == "2022-04"
    assert first_one.end is None
    assert first_one.current is True


def test_marks_an_experience_with_end_date_as_closed(draft: ProfileDraft) -> None:
    second = draft.experiences[1]

    assert second.start == "2020-10"
    assert second.end == "2022-03"
    assert second.current is False


def test_captures_the_location_without_mistaking_it_for_the_description(draft: ProfileDraft) -> None:
    assert draft.experiences[0].location == "Gran Madrid"
    assert draft.experiences[2].location == "Área metropolitana de Madrid"


def test_turns_each_bullet_into_an_achievement_joining_broken_lines(draft: ProfileDraft) -> None:
    achievements = [achievement.text for achievement in draft.experiences[0].achievements]

    assert achievements == [
        "Lleve los servicios internos a contenedores (AKS and ECS)",
        "Escribi alertas de capacidad con Prometheus",
        "Reduje el tiempo de despliegue a la mitad",
    ]


def test_discards_page_markers(draft: ProfileDraft) -> None:
    everything = " ".join(
        achievement.text for experience in draft.experiences for achievement in experience.achievements
    )

    assert "Page 1 of 3" not in everything
    assert "Page" not in everything


def test_turns_a_prose_description_into_a_single_achievement(draft: ProfileDraft) -> None:
    achievements = draft.experiences[2].achievements

    assert len(achievements) == 1
    assert achievements[0].text == (
        "Coordine el equipo de soporte usando Kanban. Documente los procesos siguiendo la guia interna."
    )


def test_extracts_education(draft: ProfileDraft) -> None:
    assert len(draft.education) == 1
    assert draft.education[0].institution == "Universidad de Ejemplo"
    assert draft.education[0].title == "Ingeniero de Telecomunicaciones, Redes"


FIXTURE_ENGLISH = Path(__file__).parent / "fixtures" / "linkedin_profile_english_content.txt"


def test_normalizes_the_non_breaking_spaces_linkedin_inserts(draft: ProfileDraft) -> None:
    title = draft.education[0].title

    assert " " not in title
    assert title == "Ingeniero de Telecomunicaciones, Redes"


def test_detects_the_content_language_not_the_linkedin_labels_language() -> None:
    draft = parse_linkedin_profile(FIXTURE_ENGLISH.read_text(encoding="utf-8"))

    assert draft.detected_language == "en", "the PDF labels are in Spanish but the content is in English"


def test_detects_spanish_when_the_content_is_in_spanish(draft: ProfileDraft) -> None:
    assert draft.detected_language == "es"


def test_reads_a_pdf_from_disk_and_returns_the_same_draft(tmp_path: Path) -> None:
    from html import escape

    from weasyprint import HTML

    from cv_generator.importers.linkedin_pdf import import_from_pdf

    text = FIXTURE.read_text(encoding="utf-8")
    pdf = tmp_path / "Profile.pdf"
    pdf.write_bytes(HTML(string=f"<pre style='font-family:sans-serif;font-size:9pt'>{escape(text)}</pre>").write_pdf())

    draft = import_from_pdf(pdf)

    assert draft.personal.first_name == "Nombre"
    assert len(draft.experiences) == 5


def test_records_each_achievement_original_text_for_syncing(
    draft: ProfileDraft,
) -> None:
    achievement = draft.experiences[0].achievements[0]

    assert achievement.imported_value == achievement.text, (
        "without the origin, editing an achievement makes LinkedIn reinsert it as a duplicate"
    )


def test_records_the_original_about_text(draft: ProfileDraft) -> None:
    profile = draft.profile_texts[0]

    assert profile.imported_value == profile.text


FIXTURE_BREAKS = Path(__file__).parent / "fixtures" / "linkedin_profile_width_breaks.txt"


def test_joins_lines_broken_right_before_a_proper_name() -> None:
    """It happened with a real PDF: a proper name like "Flux" or "Consul" arrived as a separate achievement."""
    draft = parse_linkedin_profile(FIXTURE_BREAKS.read_text(encoding="utf-8"))

    assert [achievement.text for achievement in draft.experiences[0].achievements] == [
        "Introduced trunk-based development to speed up the releases with Flux",
        "Rotated the service credentials for every internal registry using Vault and Consul",
        "Maintained the team wiki and on-call runbooks (Notion, Miro, Slack)",
        "Tech stack: Azure, Linux, Prometheus, Grafana, Ansible, Go, Rust, Bash, Nginx, Kafka, Redis.",
    ]


FIXTURE_LONG_LOCATION = Path(__file__).parent / "fixtures" / "linkedin_profile_long_location.txt"


def test_recognizes_a_long_location_by_its_place_list_shape() -> None:
    """LinkedIn writes long locations: "Provincia de ..., Comunidad Autónoma de ..., España"."""
    first_one = parse_linkedin_profile(FIXTURE_LONG_LOCATION.read_text(encoding="utf-8")).experiences[0]

    assert first_one.location == "Provincia de Santa Cruz de Tenerife, Comunidad Autónoma de Canarias, España"
    assert [achievement.text for achievement in first_one.achievements] == ["Ran the quarterly capacity reviews"]


def test_does_not_take_a_description_with_commas_for_a_location() -> None:
    second = parse_linkedin_profile(FIXTURE_LONG_LOCATION.read_text(encoding="utf-8")).experiences[1]

    assert second.location is None
    assert [achievement.text for achievement in second.achievements] == [
        "Coordinated the support rotation from planning to review, including on-call analysis, "
        "runbook upkeep, and incident tracking."
    ]


def test_records_the_name_each_skill_came_with(draft: ProfileDraft) -> None:
    """Without the origin, renaming a skill makes LinkedIn propose it again as new."""
    assert draft.skills
    assert all(skill.imported_value == skill.name for skill in draft.skills)
