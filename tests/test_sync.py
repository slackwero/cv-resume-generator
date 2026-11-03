import json
from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.importers.base import PartialPersonalInfo, ProfileDraft
from cv_generator.importers.merge import Change, ChangeKind, compute_diff
from cv_generator.models.profile import FIRST_PROFESSION_ID, Achievement, Experience, MasterProfile, Profession, Skill
from cv_generator.services.achievements import add_achievement_in, edit_achievement
from cv_generator.services.profile import load_profile, load_sync_status, restore_backup, save_profile
from cv_generator.services.sync import (
    analyze_file,
    analyze_pdf,
    apply_sync,
    create_initial_profile,
    language_mismatch,
    preselection,
    profile_unchanged,
    summary_by_kind,
)
from cv_generator.services.translations import TextState, save_translation, state_in, text_key
from tests.bilingual import sample_profile
from tests.test_models_personal import REQUIRED

FIXTURE_TEXT = Path(__file__).parent / "fixtures" / "linkedin_profile.txt"


def _changes_of_each_kind() -> list[Change]:
    return [
        Change(key="a", kind=ChangeKind.NEW, section="achievements", label="one"),
        Change(key="b", kind=ChangeKind.MODIFIED, section="achievements", label="two"),
        Change(key="c", kind=ChangeKind.CONFLICT, section="achievements", label="three"),
        Change(key="d", kind=ChangeKind.UNCHANGED, section="achievements", label="four"),
    ]


def test_preselects_what_is_new_and_what_changed_on_linkedin() -> None:
    assert preselection(_changes_of_each_kind()) == {"a", "b"}


def test_does_not_preselect_a_conflict() -> None:
    """Accepting everything must not silently overwrite a text edited by hand."""
    assert "c" not in preselection(_changes_of_each_kind())


def test_does_not_preselect_what_did_not_change() -> None:
    assert "d" not in preselection(_changes_of_each_kind())


def test_summarizes_how_many_changes_of_each_kind() -> None:
    tally = summary_by_kind(_changes_of_each_kind())

    assert tally[ChangeKind.NEW] == 1
    assert tally[ChangeKind.CONFLICT] == 1
    assert tally[ChangeKind.UNCHANGED] == 1


@pytest.fixture
def pdf_from_linkedin(tmp_path: Path) -> Path:
    from html import escape

    from weasyprint import HTML

    path = tmp_path / "Profile.pdf"
    text = escape(FIXTURE_TEXT.read_text(encoding="utf-8"))
    path.write_bytes(HTML(string=f"<pre style='font-family:sans-serif;font-size:9pt'>{text}</pre>").write_pdf())
    return path


def test_analyzing_a_pdf_against_an_empty_profile_proposes_everything_as_new(
    pdf_from_linkedin: Path,
) -> None:
    profile = MasterProfile(personal=REQUIRED)

    result = analyze_pdf(pdf_from_linkedin, profile)

    assert result.changes
    assert all(c.kind is ChangeKind.NEW for c in result.changes)
    assert result.detected_language in {"es", "en"}


def test_apply_saves_the_profile_and_records_the_sync(tmp_path: Path, pdf_from_linkedin: Path) -> None:
    data = tmp_path / "data"
    profile = MasterProfile(personal=REQUIRED)
    result = analyze_pdf(pdf_from_linkedin, profile)

    apply_sync(
        profile=profile,
        changes=result.changes,
        accepted_items=preselection(result.changes),
        data_dir=data,
        source="linkedin_pdf",
        detected_language=result.detected_language,
    )

    saved = load_profile(data)
    status = load_sync_status(data)
    assert saved is not None and saved.experiences
    assert status is not None and status.source == "linkedin_pdf"
    assert status.imported_items["experiences"] == len(saved.experiences)


def test_apply_does_not_touch_the_given_profile(tmp_path: Path, pdf_from_linkedin: Path) -> None:
    profile = MasterProfile(personal=REQUIRED)
    result = analyze_pdf(pdf_from_linkedin, profile)

    apply_sync(
        profile=profile,
        changes=result.changes,
        accepted_items=preselection(result.changes),
        data_dir=tmp_path / "data",
        source="linkedin_pdf",
        detected_language="es",
    )

    assert profile.experiences == []


def test_an_unaccepted_conflict_keeps_my_text(tmp_path: Path) -> None:
    profile = MasterProfile(
        personal=REQUIRED,
        experiences=[
            Experience(
                company="Northwind",
                role="Platform Engineer",
                start="2020-04",
                current=True,
                achievements=[Achievement(text="My own wording.", imported_value="LinkedIn text.")],
            )
        ],
        skills=[Skill(name="Kubernetes")],
    )
    draft = ProfileDraft(
        personal=PartialPersonalInfo(),
        experiences=[
            Experience(
                company="Northwind",
                role="Platform Engineer",
                start="2020-04",
                current=True,
                achievements=[Achievement(text="Updated LinkedIn text.", imported_value="Updated LinkedIn text.")],
            )
        ],
    )
    changes = compute_diff(profile, draft)

    result = apply_sync(
        profile=profile,
        changes=changes,
        accepted_items=preselection(changes),
        data_dir=tmp_path / "data",
        source="linkedin_pdf",
        detected_language="es",
    )

    assert result.profile.experiences[0].achievements[0].text == "My own wording."


@pytest.fixture
def zip_from_linkedin(tmp_path: Path) -> Path:
    import zipfile

    from tests.test_linkedin_zip import EXPORT

    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in EXPORT.items():
            zf.writestr(name, content)
    return path


def test_recognizes_a_zip_export_by_its_extension(zip_from_linkedin: Path) -> None:
    profile = MasterProfile(personal=REQUIRED)

    result = analyze_file(zip_from_linkedin, profile)

    assert result.source == "linkedin_zip"
    assert any("Platform Engineer" in (c.incoming_text or "") for c in result.changes)


def test_recognizes_a_profile_pdf_by_its_extension(pdf_from_linkedin: Path) -> None:
    profile = MasterProfile(personal=REQUIRED)

    result = analyze_file(pdf_from_linkedin, profile)

    assert result.source == "linkedin_pdf"
    assert result.changes


def test_the_extension_is_case_insensitive(tmp_path: Path, zip_from_linkedin: Path) -> None:
    renamed_one = tmp_path / "EXPORT.ZIP"
    renamed_one.write_bytes(zip_from_linkedin.read_bytes())

    assert analyze_file(renamed_one, MasterProfile(personal=REQUIRED)).source == "linkedin_zip"


def test_rejects_an_unknown_format(tmp_path: Path) -> None:
    path = tmp_path / "profile.docx"
    path.write_bytes(b"no soy ni un pdf ni un zip")

    with pytest.raises(ValueError, match="unsupported format"):
        analyze_file(path, MasterProfile(personal=REQUIRED))


def test_apply_backs_up_the_previous_profile_before_overwriting_it(tmp_path: Path, pdf_from_linkedin: Path) -> None:
    """Accepting a conflict is irreversible on the source of truth; the copy is the way back."""
    data = tmp_path / "data"
    profile = MasterProfile(personal=REQUIRED)
    save_profile(data, profile)
    analysis = analyze_pdf(pdf_from_linkedin, profile)

    result = apply_sync(
        profile=profile,
        changes=analysis.changes,
        accepted_items=preselection(analysis.changes),
        data_dir=data,
        source="linkedin_pdf",
        detected_language="es",
        moment=datetime(2026, 8, 28, 13, 45, 0),  # noqa: DTZ001
    )

    assert result.backup is not None
    assert result.backup.name == "profile.20260828-134500.json"
    backed_up = MasterProfile.model_validate(json.loads(result.backup.read_text(encoding="utf-8")))
    assert backed_up.experiences == []


def test_the_first_sync_backs_up_nothing_because_there_was_no_profile(tmp_path: Path, pdf_from_linkedin: Path) -> None:
    profile = MasterProfile(personal=REQUIRED)
    analysis = analyze_pdf(pdf_from_linkedin, profile)

    result = apply_sync(
        profile=profile,
        changes=analysis.changes,
        accepted_items=preselection(analysis.changes),
        data_dir=tmp_path / "data",
        source="linkedin_pdf",
        detected_language="es",
    )

    assert result.backup is None


# ------------------------------------------------- the profile changed in another tab


def _synced_profile() -> MasterProfile:
    return MasterProfile(
        source_language="en",
        personal=REQUIRED,
        professions=[Profession(id=FIRST_PROFESSION_ID, text=REQUIRED["profession"])],
        experiences=[
            Experience(
                company="Northwind",
                role="Platform Engineer",
                start="2020-04",
                current=True,
                achievements=[
                    Achievement(text="Cut SAST findings by 80%.", imported_value="Cut SAST findings by 80%.")
                ],
            )
        ],
    )


def test_a_profile_read_back_from_disk_is_unchanged(tmp_path: Path) -> None:
    """What apply wrote is compared against what is read back to undo it."""
    profile = _synced_profile()
    save_profile(tmp_path, profile)

    assert profile_unchanged(profile, load_profile(tmp_path))


def test_an_achievement_edited_on_disk_is_a_change() -> None:
    profile = _synced_profile()
    job = profile.experiences[0]

    edited = edit_achievement(profile, job.id, job.achievements[0].id, "Cut SAST findings by 90%.")

    assert not profile_unchanged(profile, edited)


def test_no_profile_before_and_none_now_is_unchanged() -> None:
    assert profile_unchanged(None, None)


def test_a_profile_created_in_the_meantime_is_a_change() -> None:
    assert not profile_unchanged(None, _synced_profile())


# ------------------------------------------------- sync feeds the source language only


def _draft_with(*achievements: Achievement) -> ProfileDraft:
    return ProfileDraft(
        personal=PartialPersonalInfo(),
        experiences=[
            Experience(
                company="Acme Airlines", role="Platform Engineer", start="2022-03", achievements=list(achievements)
            )
        ],
    )


def _sync(profile: MasterProfile, draft: ProfileDraft, data_dir: Path, language: str = "en") -> MasterProfile:
    """The real path: diff, accept what is preselected, apply."""
    changes = compute_diff(profile, draft)
    return apply_sync(
        profile=profile,
        changes=changes,
        accepted_items=preselection(changes),
        data_dir=data_dir,
        source="linkedin_pdf",
        detected_language=language,
    ).profile


def test_a_linkedin_change_puts_the_spanish_of_that_achievement_in_review(tmp_path: Path) -> None:
    profile = sample_profile()
    profile.experiences[0].achievements[0].imported_value = "Cut deploy time by 40%"
    profile = save_translation(profile, "es", text_key("ach-1", "text"), "Redujo el tiempo de despliegue un 40%")
    assert state_in(profile, "es", text_key("ach-1", "text")) is TextState.CURRENT

    draft = _draft_with(Achievement(text="Cut deploy time by 55%", imported_value="Cut deploy time by 55%"))
    synced = _sync(profile, draft, tmp_path)

    assert synced.experiences[0].achievements[0].text == "Cut deploy time by 55%"
    assert state_in(synced, "es", text_key("ach-1", "text")) is TextState.REVIEW


def test_achievements_new_from_linkedin_arrive_pending_translation(tmp_path: Path) -> None:
    profile = sample_profile()
    profile.experiences[0].achievements[0].imported_value = "Cut deploy time by 40%"
    draft = _draft_with(
        Achievement(text="Cut deploy time by 40%", imported_value="Cut deploy time by 40%"),
        Achievement(text="Led the SAST rollout", imported_value="Led the SAST rollout"),
    )

    synced = _sync(profile, draft, tmp_path)

    new = next(a for a in synced.experiences[0].achievements if a.text == "Led the SAST rollout")
    assert state_in(synced, "es", text_key(new.id, "text")) is TextState.MISSING


def test_an_achievement_written_only_in_spanish_is_never_matched_by_the_sync(tmp_path: Path) -> None:
    profile = sample_profile()
    profile.experiences[0].achievements[0].imported_value = "Cut deploy time by 40%"
    profile = add_achievement_in(profile, "exp-1", "Escribí esto solo en español", "es")
    only_spanish = next(a for a in profile.experiences[0].achievements if a.id != "ach-1")
    key = text_key(only_spanish.id, "text")
    kept = profile.translations["es"][key].model_copy()

    draft = _draft_with(Achievement(text="Cut deploy time by 40%", imported_value="Cut deploy time by 40%"))
    changes = compute_diff(profile, draft)
    synced = _sync(profile, draft, tmp_path)

    assert all(change.target_id != only_spanish.id for change in changes)
    assert synced.translations["es"][key] == kept


def test_the_first_sync_sets_the_source_language(tmp_path: Path) -> None:
    profile = create_initial_profile(PartialPersonalInfo())
    assert profile.source_language is None

    _sync(profile, _draft_with(), tmp_path, language="es")

    saved = load_profile(tmp_path)
    assert saved is not None and saved.source_language == "es"


def test_the_first_sync_creates_the_list_from_the_headline(tmp_path: Path) -> None:
    profile = create_initial_profile(PartialPersonalInfo(profession="DevSecOps Engineer"))

    synced = _sync(profile, _draft_with(), tmp_path)

    assert [(x.id, x.text) for x in synced.professions] == [("profession-headline", "DevSecOps Engineer")]
    assert profile_unchanged(synced, load_profile(tmp_path))


def test_a_first_sync_without_a_headline_holds_the_placeholder(tmp_path: Path) -> None:
    profile = create_initial_profile(PartialPersonalInfo())

    assert [x.text for x in profile.professions] == ["PENDING"]


def test_a_later_sync_keeps_the_source_language(tmp_path: Path) -> None:
    profile = sample_profile()

    synced = _sync(profile, _draft_with(), tmp_path, language="es")

    assert synced.source_language == "en"
    saved = load_profile(tmp_path)
    assert saved is not None and saved.source_language == "en"


def test_the_mismatch_message_names_both_languages() -> None:
    message = language_mismatch(sample_profile(), "es")

    assert message == (
        "This export is in Spanish, but your profile's LinkedIn content is in English. "
        "The sync only reads the English export, so nothing was compared. "
        "Export your LinkedIn profile in English and upload it again."
    )


def test_no_mismatch_without_a_profile_or_a_source_language_or_with_the_same_language() -> None:
    assert language_mismatch(None, "es") == ""
    assert language_mismatch(MasterProfile(personal=REQUIRED), "es") == ""
    assert language_mismatch(sample_profile(), "en") == ""


def test_restoring_a_schema_1_backup_returns_the_upgraded_profile(tmp_path: Path) -> None:
    """The sync screen keeps what undo returns and later compares it with what load gives."""
    legacy = MasterProfile(personal=REQUIRED).model_dump(mode="json")
    legacy["schema_version"] = 1
    legacy.pop("source_language", None)
    legacy.pop("translations", None)
    (tmp_path / "profile.20260828-134500.json").write_text(json.dumps(legacy), encoding="utf-8")

    restored = restore_backup(tmp_path, "profile.20260828-134500.json")

    loaded = load_profile(tmp_path)
    assert loaded is not None
    assert restored.source_language == loaded.source_language == "en"
    assert profile_unchanged(restored, loaded)
