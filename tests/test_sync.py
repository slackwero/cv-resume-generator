import json
from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.importers.base import PartialPersonalInfo, ProfileDraft
from cv_generator.importers.merge import Change, ChangeKind, compute_diff
from cv_generator.models.profile import Achievement, Experience, MasterProfile, Skill
from cv_generator.services.profile import load_profile, load_sync_status, save_profile
from cv_generator.services.sync import (
    analyze_file,
    analyze_pdf,
    apply_sync,
    preselection,
    summary_by_kind,
)
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
