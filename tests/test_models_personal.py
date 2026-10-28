from datetime import date

import pytest
from pydantic import ValidationError

from cv_generator.models.profile import PersonalInfo

REQUIRED = {
    "first_name": "Jane",
    "last_name": "Doe",
    "profession": "DevSecOps Engineer",
    "phone": "+1 555 0100",
    "email": "jane.doe@example.com",
}


def test_accepts_a_profile_with_only_required_fields() -> None:
    personal_items = PersonalInfo(**REQUIRED)

    assert personal_items.first_name == "Jane"
    assert personal_items.website is None
    assert personal_items.photo is None


@pytest.mark.parametrize("field", sorted(REQUIRED))
def test_rejects_a_profile_missing_a_required_field(field: str) -> None:
    incomplete = {k: v for k, v in REQUIRED.items() if k != field}

    with pytest.raises(ValidationError):
        PersonalInfo(**incomplete)


@pytest.mark.parametrize("empty_value", ["", "   "])
def test_rejects_a_blank_required_field(empty_value: str) -> None:
    with pytest.raises(ValidationError):
        PersonalInfo(**{**REQUIRED, "profession": empty_value})


def test_derives_age_from_birth_date() -> None:
    personal_items = PersonalInfo(**REQUIRED, birth_date=date(1990, 3, 15))

    assert personal_items.compute_age(today=date(2026, 3, 14)) == 35
    assert personal_items.compute_age(today=date(2026, 3, 15)) == 36


def test_no_age_without_a_birth_date() -> None:
    personal_items = PersonalInfo(**REQUIRED)

    assert personal_items.compute_age(today=date(2026, 3, 15)) is None


def test_accepts_an_embedded_jpeg_photo() -> None:
    photo = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="

    assert PersonalInfo(**REQUIRED, photo=photo).photo == photo


@pytest.mark.parametrize(
    "photo",
    [
        "assets/photo.jpg",
        "file:///etc/passwd",
        "https://tracker.example/pixel.png",
        "data:image/svg+xml;base64,PHN2Zz4=",
        'data:image/jpeg;base64,AAAA" onerror="alert(1)',
    ],
)
def test_rejects_a_photo_that_is_not_an_embedded_jpeg(photo: str) -> None:
    """The photo goes into the template's `src` and WeasyPrint resolves it: a path or a URL
    would make it read a local file or fetch something from the network when generating the PDF."""
    with pytest.raises(ValidationError):
        PersonalInfo(**REQUIRED, photo=photo)
