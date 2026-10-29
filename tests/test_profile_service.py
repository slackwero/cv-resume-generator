from datetime import datetime
from pathlib import Path

from cv_generator.models.profile import Achievement, Experience, MasterProfile, PersonalInfo
from cv_generator.services.profile import (
    SyncStatus,
    load_profile,
    load_sync_status,
    save_profile,
    save_sync_status,
    with_personal,
)
from tests.test_models_personal import REQUIRED

PHOTO = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="


def test_without_saved_profile_returns_none(tmp_path: Path) -> None:
    assert load_profile(tmp_path) is None


def test_saves_and_loads_the_profile(tmp_path: Path) -> None:
    save_profile(tmp_path, MasterProfile(personal=REQUIRED))

    recovered = load_profile(tmp_path)

    assert recovered is not None
    assert recovered.personal.first_name == "Jane"


def test_without_previous_sync_returns_none(tmp_path: Path) -> None:
    assert load_sync_status(tmp_path) is None


def test_remembers_when_and_from_where_it_synced(tmp_path: Path) -> None:
    save_sync_status(
        tmp_path,
        SyncStatus(
            source="linkedin_pdf",
            timestamp=datetime(2026, 8, 27, 17, 0),
            ok=True,
            detected_language="en",
            imported_items={"experiences": 7},
        ),
    )

    status = load_sync_status(tmp_path)

    assert status is not None
    assert status.source == "linkedin_pdf"
    assert status.detected_language == "en"
    assert status.imported_items["experiences"] == 7


def test_reads_the_sync_status_already_on_disk(tmp_path: Path) -> None:
    """The file written by the initial import must remain readable."""
    (tmp_path / "sync_state.json").write_text(
        '{"source": "linkedin_pdf", "timestamp": "2026-08-27T17:40:00", "ok": true,'
        ' "detected_language": "en", "imported_items": {"experiences": 7}}',
        encoding="utf-8",
    )

    status = load_sync_status(tmp_path)

    assert status is not None and status.ok


def _profile_with_photo_and_achievements() -> MasterProfile:
    return MasterProfile(
        personal=PersonalInfo(**REQUIRED, photo=PHOTO),
        experiences=[
            Experience(
                company="Northwind",
                role="Platform Engineer",
                start="2020-04",
                current=True,
                achievements=[Achievement(text="Designed a RAG pipeline over runbooks.")],
            )
        ],
    )


def test_saving_the_contact_details_keeps_the_achievements_and_the_photo() -> None:
    """The form only knows the contact fields: the rest comes from the profile on disk."""
    on_disk = _profile_with_photo_and_achievements()

    updated = with_personal(on_disk, PersonalInfo(**{**REQUIRED, "first_name": "Janet"}))

    assert updated.personal.first_name == "Janet"
    assert updated.personal.photo == PHOTO
    assert updated.experiences == on_disk.experiences


def test_saving_the_contact_details_does_not_touch_the_given_profile() -> None:
    on_disk = _profile_with_photo_and_achievements()
    before = on_disk.model_dump()

    with_personal(on_disk, PersonalInfo(**{**REQUIRED, "first_name": "Janet"}))

    assert on_disk.model_dump() == before
