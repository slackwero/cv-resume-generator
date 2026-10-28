"""Term extraction from a posting and coverage against the CV.

Several postings here are in Spanish on purpose: the analysis has to discard the filler of
a Spanish job ad ("buscamos", "equipo", "requisitos"), which lives in i18n/es.json.
"""

import pytest

from cv_generator.models.cv import CVContent
from cv_generator.models.profile import Achievement, Experience, Skill
from cv_generator.tailoring.keywords import (
    analyze_coverage,
    extract_terms,
    mentioned_terms,
)

POSTING = """
Buscamos un DevSecOps Engineer con experiencia en Kubernetes y Terraform para
unirse a nuestro equipo. La persona seleccionada sera responsable de mantener y
mejorar nuestros pipelines de CI/CD en GitLab, y de desplegar servicios en AWS
y en Cloud Run.

Requisitos:
- Experiencia demostrable con Kubernetes en produccion
- Conocimientos de Terraform e infraestructura como codigo
- Manejo de Python para automatizacion
- Familiaridad con herramientas de SAST y analisis de vulnerabilidades

Ofrecemos un equipo excelente y muchas oportunidades de crecimiento profesional.
"""


def _terms(text: str = POSTING) -> list[str]:
    return [term.term for term in extract_terms(text)]


def test_extracts_the_technologies_the_posting_asks_for() -> None:
    terms = [t.lower() for t in _terms()]

    for expected in ["kubernetes", "terraform", "python", "aws", "gitlab", "sast"]:
        assert expected in terms, f"did not extract '{expected}'"


def test_recognizes_terms_with_technical_symbols() -> None:
    assert "CI/CD" in _terms()


def test_recognizes_two_word_terms() -> None:
    assert "Cloud Run" in _terms()


@pytest.mark.parametrize(
    "noise",
    ["buscamos", "experience", "equipo", "requisitos", "ofrecemos", "persona", "para", "con"],
)
def test_discards_the_usual_filler_of_a_posting(noise: str) -> None:
    assert noise not in [t.lower() for t in _terms()]


def test_sorts_by_relevance_and_caps_the_count() -> None:
    terms = extract_terms(POSTING, maximum=5)

    assert len(terms) == 5
    frequencies = [t.frequency for t in terms]
    assert frequencies == sorted(frequencies, reverse=True)


@pytest.fixture
def cv() -> CVContent:
    return CVContent(
        personal={
            "first_name": "Jane",
            "last_name": "Doe",
            "profession": "DevSecOps Engineer",
            "phone": "+1 555 0100",
            "email": "email@example.com",
        },
        profile="Engineer focused on application security.",
        experiences=[
            Experience(
                company="Acme",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[
                    Achievement(text="Migrated 40 services to Kubernetes with zero downtime."),
                    Achievement(text="Automated the pipeline SAST scanning with Python."),
                ],
            )
        ],
        skills=[Skill(name="Terraform")],
    )


def test_marks_as_covered_what_the_cv_already_mentions(cv: CVContent) -> None:
    analysis = analyze_coverage(POSTING, cv)
    covered_terms = [t.term.lower() for t in analysis.covered_terms]

    assert "kubernetes" in covered_terms
    assert "python" in covered_terms
    assert "terraform" in covered_terms, "what is in the skills counts too"


def test_flags_what_the_posting_asks_and_the_cv_does_not_mention(cv: CVContent) -> None:
    analysis = analyze_coverage(POSTING, cv)
    missing = [t.term.lower() for t in analysis.missing]

    assert "aws" in missing
    assert "gitlab" in missing
    assert "kubernetes" not in missing


def test_matching_ignores_case_and_accents(cv: CVContent) -> None:
    cv.skills = [Skill(name="TERRAFORM")]
    cv.experiences[0].achievements = [Achievement(text="Trabajé con Análisis de vulnerabilidades.")]

    analysis = analyze_coverage("Se requiere Terraform y Análisis de Vulnerabilidades.", cv)

    assert [t.term.lower() for t in analysis.missing] == []


def test_computes_the_coverage_percentage(cv: CVContent) -> None:
    analysis = analyze_coverage(POSTING, cv)

    assert 0 < analysis.covered_percent < 100  # noqa: PLR2004
    assert analysis.covered_percent == round(
        100 * len(analysis.covered_terms) / (len(analysis.covered_terms) + len(analysis.missing))
    )


def test_an_empty_posting_produces_no_analysis(cv: CVContent) -> None:
    analysis = analyze_coverage("   ", cv)

    assert analysis.covered_terms == []
    assert analysis.missing == []
    assert analysis.covered_percent == 0


def test_does_not_mistake_a_word_for_a_fragment_of_another(cv: CVContent) -> None:
    """ "Java" must not count as covered because the CV mentions "JavaScript"."""
    cv.skills = [Skill(name="JavaScript")]
    cv.experiences[0].achievements = [Achievement(text="Built interfaces with JavaScript.")]

    analysis = analyze_coverage("We require Java and Spring Boot.", cv)

    assert "java" in [t.term.lower() for t in analysis.missing]


REALISTIC_POSTING = """
Buscamos un Cloud Security Engineer para unirse a nuestro equipo de plataforma.

Requisitos:
- Experiencia solida con Kubernetes y Docker en produccion
- Manejo de Terraform para infraestructura como codigo
- Conocimientos de AWS y GCP, especialmente Cloud Run y Lambda
- Automatizacion con Python
- Herramientas de SAST y analisis de dependencias: SonarQube, Trivy, Checkov
- Experiencia con Datadog para observabilidad
- Deseable: certificacion CKA y conocimientos de Rust

Ofrecemos un equipo excelente y oportunidades de crecimiento.
"""


@pytest.mark.parametrize(
    "technology",
    ["Kubernetes", "Docker", "Terraform", "AWS", "GCP", "Datadog", "CKA", "Rust", "SAST"],
)
def test_keeps_the_technologies_of_a_realistic_posting(technology: str) -> None:
    assert technology in _terms(REALISTIC_POSTING)


@pytest.mark.parametrize(
    "noise",
    [
        "plataforma",
        "solida",
        "infraestructura",
        "code",
        "especialmente",
        "automatizacion",
        "herramientas",
        "analysis",
        "dependencias",
        "observabilidad",
        "certificacion",
        "conocimientos",
        "deseable",
    ],
)
def test_discards_common_words_that_say_nothing_about_the_job(noise: str) -> None:
    """A list of missing terms full of filler gets ignored, and drags the percentage down."""
    assert noise not in [t.lower() for t in _terms(REALISTIC_POSTING)]


def test_a_lowercase_word_is_kept_if_the_posting_insists_on_it() -> None:
    """Capitalization is the main signal, but repeating something is one too."""
    text = "We work with kubernetes every day. The team deploys on kubernetes."

    assert "kubernetes" in [t.lower() for t in _terms(text)]


@pytest.mark.parametrize("tool", ["SonarQube", "Trivy", "Checkov"])
def test_keeps_the_items_of_a_comma_separated_list(tool: str) -> None:
    """A comma separates the items of a list, not sentences.

    If it were treated as the end of a sentence, every listed tool would look capitalized
    by grammar and would be discarded as filler.
    """
    assert tool in _terms(REALISTIC_POSTING)


def test_flags_the_terms_an_achievement_mentions() -> None:
    achievement = "Automated vulnerability scanning with Terraform and SonarQube"

    assert mentioned_terms(achievement, ["terraform", "sonarqube", "kubernetes"]) == [
        "terraform",
        "sonarqube",
    ]


def test_flags_nothing_when_the_achievement_contributes_nothing() -> None:
    assert mentioned_terms("Led the monolith migration", ["terraform"]) == []


def test_respects_word_boundaries_like_the_coverage() -> None:
    """Java is not contributed by an achievement that only mentions JavaScript."""
    assert mentioned_terms("Migrated services in JavaScript", ["java"]) == []


def test_recognizes_terms_with_symbols() -> None:
    """A term can carry slashes, and \\b would not work to delimit it."""
    assert mentioned_terms("I maintain the CI/CD pipelines", ["ci/cd"]) == ["ci/cd"]


def test_ignores_accents_and_case_when_matching() -> None:
    assert mentioned_terms("Automation with TERRAFORM", ["terraform"]) == ["terraform"]


def test_what_an_achievement_contributes_counts_as_covered(cv: CVContent) -> None:
    """The interface cannot promise a term the analysis later does not count.

    That is why both use the same matching: if they diverged, step 4 would say "this
    achievement contributes Kubernetes" and step 6 would still list it as missing.
    """
    text = cv.experiences[0].achievements[0].text
    contributed = mentioned_terms(text, ["kubernetes", "terraform"])
    assert contributed == ["kubernetes"], "the fixture achievement mentions Kubernetes and not Terraform"

    analysis = analyze_coverage(" ".join(contributed), cv)

    assert [t.term for t in analysis.missing] == []


# ------------------------------------------------------- compound terms


def test_a_compound_is_covered_even_if_the_cv_says_it_split(cv: CVContent) -> None:
    """The posting asks for "DevSecOps Engineer" and the CV says "Platform Engineer - DevSecOps".

    Requiring the literal phrase left the term among the missing ones forever: no CV
    writes the job title exactly like the ad, so it dragged the percentage down with
    nothing the user could do.
    """
    analysis = analyze_coverage("We are looking for a DevSecOps Engineer.", cv)

    assert [t.term for t in analysis.missing] == []


def test_a_compound_is_still_missing_with_only_one_of_its_words() -> None:
    """The rule's guard: split up cannot mean "as long as something appears"."""
    content = CVContent(
        personal={
            "first_name": "Jane",
            "last_name": "Doe",
            "profession": "DevSecOps Engineer",
            "phone": "+1 555 0100",
            "email": "email@example.com",
        },
        experiences=[
            Experience(
                company="Acme",
                role="Engineer",
                start="2022-03",
                achievements=[Achievement(text="Automated pipelines with Power Automate.")],
            )
        ],
    )

    analysis = analyze_coverage("We need Power BI for the team.", content)

    assert [t.term for t in analysis.missing] == ["Power BI"]


def test_a_single_word_is_not_covered_by_parts() -> None:
    """The rule is only for compounds: "JavaScript" does not cover "Java"."""
    content = CVContent(
        personal={
            "first_name": "Jane",
            "last_name": "Doe",
            "profession": "Developer",
            "phone": "+1 555 0100",
            "email": "email@example.com",
        },
        experiences=[
            Experience(
                company="Acme",
                role="Developer",
                start="2022-03",
                achievements=[Achievement(text="Migrated services written in JavaScript.")],
            )
        ],
    )

    analysis = analyze_coverage("We are looking for someone with Java and Java.", content)

    assert [t.term for t in analysis.missing] == ["Java"]


# ---------------------------------------------------- capitalized by grammar


def test_a_word_that_only_opens_sentences_forms_no_compound() -> None:
    """ "Pipelines" at the start of a line is the common word, not a technology.

    It formed "Pipelines CI/CD", which no CV writes that way, and it also took out the
    standalone "CI/CD", which is a real term that can be covered.
    """
    terms = [t.term for t in extract_terms("Pipelines CI/CD on GitLab.")]

    assert "Pipelines CI/CD" not in terms
    assert "CI/CD" in terms


def test_a_legitimate_compound_survives_mid_sentence() -> None:
    """The guard of the previous fix: it cannot take out real compounds."""
    terms = [t.term for t in extract_terms("Knowledge of GCP, especially Cloud Run and Lambda.")]

    assert "Cloud Run" in terms
