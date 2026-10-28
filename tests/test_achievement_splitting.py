"""How a job description is split into separate achievements.

The underlying rule: the text that comes from LinkedIn is placed as is. Splitting
decides where each achievement starts and ends, but it never rewrites what is inside nor
fabricates sentences by joining lines the user wrote separately.
"""

import pytest

from cv_generator.importers.base import split_into_achievements


def test_one_bullet_per_achievement() -> None:
    assert split_into_achievements(["- Automated the scanning", "- Migrated 40 services"]) == [
        "Automated the scanning",
        "Migrated 40 services",
    ]


@pytest.mark.parametrize("placeholder", ["- ", "• ", "* "])
def test_recognizes_the_three_bullet_markers(placeholder: str) -> None:
    assert split_into_achievements([f"{placeholder}Automated the scanning"]) == ["Automated the scanning"]


def test_a_block_of_its_own_does_not_merge_into_the_previous_achievement() -> None:
    """The case behind the rule: 'Tech stack' showed up glued to the last achievement.

    Merging them produced a sentence that was not on LinkedIn and nobody had written.
    """
    achievements = split_into_achievements(
        [
            "- Migrated 40 services to Kubernetes",
            "Tech stack: Go, Terraform, ArgoCD",
        ]
    )

    assert achievements == ["Migrated 40 services to Kubernetes", "Tech stack: Go, Terraform, ArgoCD"]


def test_prose_keeps_the_lines_the_user_wrote() -> None:
    """In the ZIP export every line break was put there by the user, so it is respected."""
    assert split_into_achievements(["Led the platform team.", "Owned the cloud strategy."]) == [
        "Led the platform team.",
        "Owned the cloud strategy.",
    ]


def test_discards_empty_lines_without_touching_the_rest() -> None:
    assert split_into_achievements(["- One", "", "   ", "- Two"]) == ["One", "Two"]


def test_an_empty_description_produces_no_achievements() -> None:
    assert split_into_achievements([]) == []
    assert split_into_achievements(["", "   "]) == []


def test_does_not_rewrite_the_achievement_text() -> None:
    """Only the margin and the marker are trimmed, nothing else: not case, not punctuation, not accents."""
    original = "- Cut the MTTR by 40 % at the Bogotá office using GitOps (ArgoCD) and CI/CD"

    assert split_into_achievements([original]) == [
        "Cut the MTTR by 40 % at the Bogotá office using GitOps (ArgoCD) and CI/CD"
    ]


# ------------------------------------------------ sources that split by width

# Length of the column's longest line, in characters.
WIDTH = 80


def test_the_pdf_rejoins_a_bullet_split_by_width() -> None:
    """The PDF is extracted from a laid out page: the long sentence arrives in two lines."""
    achievements = split_into_achievements(
        ["- Designed the security architecture", "for 12 product teams"],
        column_width=WIDTH,
    )

    assert achievements == ["Designed the security architecture for 12 product teams"]


def test_not_even_a_width_split_merges_a_block_of_its_own() -> None:
    """It starts with a capital letter, so it opens something new even if the source wraps text."""
    achievements = split_into_achievements(
        ["- Migrated 40 services to Kubernetes", "Tech stack: Go, Terraform"],
        column_width=WIDTH,
    )

    assert achievements == ["Migrated 40 services to Kubernetes", "Tech stack: Go, Terraform"]


def test_a_closed_sentence_does_not_continue_on_the_next_line() -> None:
    achievements = split_into_achievements(
        ["- Led the monolith migration.", "then coordinated the team"],
        column_width=WIDTH,
    )

    assert achievements == ["Led the monolith migration.", "then coordinated the team"]


def test_nothing_is_joined_by_default() -> None:
    """The ZIP must not inherit the fix only the PDF needs."""
    lines = ["- Designed the security architecture", "for 12 product teams"]

    assert len(split_into_achievements(lines)) == 2


def test_a_line_that_reached_the_margin_continues_even_if_the_next_is_capitalized() -> None:
    """In a technical CV the break often falls right before a proper name."""
    achievements = split_into_achievements(
        [
            "- Introduced trunk-based development to speed up the releases with",
            "Flux",
            "- Wrote the on-call handbook for new hires",
        ],
        column_width=WIDTH,
    )

    assert achievements == [
        "Introduced trunk-based development to speed up the releases with Flux",
        "Wrote the on-call handbook for new hires",
    ]


def test_a_short_line_ends_there_even_if_the_sentence_is_open() -> None:
    """If more text fit, the user put the break there: it is a list without bullets."""
    assert split_into_achievements(["Kubernetes", "Terraform"], column_width=WIDTH) == ["Kubernetes", "Terraform"]


def test_a_label_opens_a_block_even_if_the_previous_line_reached_the_margin() -> None:
    """The 'Tech stack' case again, now after a full line that does not close the sentence."""
    achievements = split_into_achievements(
        [
            "- Maintained the team wiki and on-call runbooks (Notion, Miro, Slack)",
            "Tech stack: Azure, Linux, Prometheus, Grafana, Ansible, Go, Rust, Bash,",
            "Nginx, Kafka, Redis.",
        ],
        column_width=WIDTH,
    )

    assert achievements == [
        "Maintained the team wiki and on-call runbooks (Notion, Miro, Slack)",
        "Tech stack: Azure, Linux, Prometheus, Grafana, Ansible, Go, Rust, Bash, Nginx, Kafka, Redis.",
    ]
