import json
from datetime import datetime
from pathlib import Path

from cv_generator.models.profile import Achievement, Experience, MasterProfile, PersonalInfo, Profession
from cv_generator.services.profile import (
    PENDING_FIELD,
    SyncStatus,
    available_backups,
    load_profile,
    load_sync_status,
    pending_fields,
    save_profile,
    save_sync_status,
    with_personal,
)
from cv_generator.services.translations import TextState, state_in, text_in
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


def _write_v1_profile(data_dir: Path) -> None:
    (data_dir / "profile.json").write_text(json.dumps({"schema_version": 1, "personal": REQUIRED}))


def test_an_old_profile_takes_its_source_language_from_the_last_sync(tmp_path: Path) -> None:
    _write_v1_profile(tmp_path)
    save_sync_status(tmp_path, SyncStatus(source="zip", timestamp=datetime(2026, 11, 1), detected_language="es"))

    profile = load_profile(tmp_path)

    assert profile is not None
    assert profile.source_language == "es"
    assert profile.schema_version == 3


def test_an_old_profile_never_synced_is_english(tmp_path: Path) -> None:
    _write_v1_profile(tmp_path)

    profile = load_profile(tmp_path)

    assert profile is not None
    assert profile.source_language == "en"


def test_the_first_save_over_an_old_profile_backs_it_up_once(tmp_path: Path) -> None:
    _write_v1_profile(tmp_path)
    profile = load_profile(tmp_path)
    assert profile is not None

    save_profile(tmp_path, profile)
    save_profile(tmp_path, profile)

    backups = available_backups(tmp_path)
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["schema_version"] == 1
    assert json.loads((tmp_path / "profile.json").read_text())["schema_version"] == 3


KEY = "profession-headline.text"


def _write_v2_profile(
    data_dir: Path, *, agreed_text: str | None = None, profession: str = "DevSecOps Engineer"
) -> None:
    entry = {"text": "Ingeniero DevSecOps", "source_text": "DevSecOps Engineer"}
    if agreed_text is not None:
        entry["agreed_text"] = agreed_text
    profile = {
        "schema_version": 2,
        "source_language": "en",
        "personal": {**REQUIRED, "profession": profession},
        "translations": {"es": {"personal.profession": entry}},
    }
    (data_dir / "profile.json").write_text(json.dumps(profile))


def test_a_schema_2_profile_gets_its_profession_as_the_first_entry(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path)

    p = load_profile(tmp_path)

    assert p is not None
    assert p.schema_version == 3
    assert p.professions == [Profession(id="profession-headline", text="DevSecOps Engineer")]
    assert state_in(p, "es", KEY) is TextState.CURRENT
    assert text_in(p, "es", KEY) == "Ingeniero DevSecOps"
    assert "personal.profession" not in p.translations["es"]


def test_a_review_state_survives_the_move(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path, agreed_text="Ingeniero de DevSecOps")

    p = load_profile(tmp_path)

    assert p is not None
    assert p.translations["es"][KEY].agreed_text == "Ingeniero de DevSecOps"
    assert state_in(p, "en", KEY) is TextState.REVIEW


def test_a_schema_1_profile_comes_out_at_schema_3_with_both_upgrades(tmp_path: Path) -> None:
    _write_v1_profile(tmp_path)

    p = load_profile(tmp_path)

    assert p is not None
    assert (p.schema_version, p.source_language) == (3, "en")
    assert [x.text for x in p.professions] == [REQUIRED["profession"]]


def test_a_pending_profession_becomes_a_one_entry_list_holding_the_placeholder(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path, profession=PENDING_FIELD)

    p = load_profile(tmp_path)

    assert p is not None
    assert [x.text for x in p.professions] == [PENDING_FIELD]


def test_a_profile_that_already_has_the_list_is_left_alone(tmp_path: Path) -> None:
    mine = MasterProfile(personal=REQUIRED, professions=[Profession(id="p-1", text="Mine")])
    save_profile(tmp_path, mine)

    p = load_profile(tmp_path)

    assert p is not None
    assert p.professions == [Profession(id="p-1", text="Mine")]


def test_the_first_save_over_a_schema_2_profile_backs_it_up_once(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path)
    p = load_profile(tmp_path)
    assert p is not None

    save_profile(tmp_path, p)
    save_profile(tmp_path, p)

    backups = available_backups(tmp_path)
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["schema_version"] == 2
    assert json.loads((tmp_path / "profile.json").read_text())["schema_version"] == 3


def test_loading_twice_gives_the_same_first_entry_id(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path)

    first, second = load_profile(tmp_path), load_profile(tmp_path)

    assert first is not None and second is not None
    assert first.professions[0].id == second.professions[0].id == "profession-headline"


def test_a_translation_without_a_profession_entry_is_not_invented(tmp_path: Path) -> None:
    _write_v1_profile(tmp_path)

    p = load_profile(tmp_path)

    assert p is not None
    assert p.translations == {}


def test_a_pre_list_profile_with_only_a_spanish_profession_is_not_missing_it(tmp_path: Path) -> None:
    _write_v2_profile(tmp_path, profession=PENDING_FIELD)

    p = load_profile(tmp_path)

    assert p is not None
    assert p.personal.profession == "Ingeniero DevSecOps"
    assert "profession" not in pending_fields(p)
