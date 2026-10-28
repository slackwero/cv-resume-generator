from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.models.cv import JobPosting, SelectedExperience, Selection
from cv_generator.models.profile import Achievement, Experience, MasterProfile, Skill
from cv_generator.models.style import PaletteColor, Style
from cv_generator.rendering.i18n import default_sections
from cv_generator.services import generation
from cv_generator.services.generation import generate_cv, load_cv, regenerate_pdf
from cv_generator.storage.history import (
    archive_cv,
    load_history,
    note_archive_reason,
    rebuild_history,
)
from tests.test_models_personal import REQUIRED
from tests.test_photo import sample_photo

CREATED = datetime(2026, 3, 15, 10, 30)


@pytest.fixture
def profile() -> MasterProfile:
    return MasterProfile(
        personal=REQUIRED,
        experiences=[
            Experience(
                id="exp-1",
                company="Acme Airlines",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[
                    Achievement(id="achievement-1", text="Cut critical SAST findings by 80%."),
                    Achievement(id="achievement-2", text="Halved the BigQuery cost."),
                ],
            )
        ],
        skills=[Skill(id="skill-1", name="Kubernetes")],
    )


@pytest.fixture
def selection() -> Selection:
    return Selection(
        header_profession="DevSecOps Engineer",
        experiences=[SelectedExperience(id="exp-1", achievements=["achievement-1"])],
        skills=["skill-1"],
        sections=default_sections("es"),
    )


def test_writes_the_pdf_with_the_agreed_name(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    pdf = tmp_path / "output" / "jd-devsecops-marzo2026.pdf"
    assert pdf.exists()
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert cv.pdf_file.endswith("jd-devsecops-marzo2026.pdf")


def test_saves_the_frozen_cv_snapshot(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    saved = load_cv(tmp_path / "data", cv.cv_id)

    assert saved.content.experiences[0].achievements[0].text == ("Cut critical SAST findings by 80%.")
    assert len(saved.content.experiences[0].achievements) == 1, "only the selected achievement"


def test_registers_the_cv_in_the_history(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    history = load_history(tmp_path / "data")

    assert len(history) == 1
    assert history[0].cv_name == "DevSecOps at Acme"
    assert history[0].target_role == "DevSecOps"
    assert history[0].language == "es"


def test_history_shows_the_newest_cv_first(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    common = dict(
        profile=profile,
        selection=selection,
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
    )
    generate_cv(cv_name="The old one", target_role="Backend", created=datetime(2025, 1, 5), **common)
    generate_cv(cv_name="The new one", target_role="DevSecOps", created=datetime(2026, 8, 1), **common)

    history = load_history(tmp_path / "data")

    assert [entry.cv_name for entry in history] == ["The new one", "The old one"]


def test_two_cvs_for_the_same_role_and_month_do_not_collide(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    common = dict(
        profile=profile,
        selection=selection,
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )
    first = generate_cv(cv_name="For Acme", **common)
    second_one = generate_cv(cv_name="For Northwind", **common)

    assert first.pdf_file != second_one.pdf_file
    assert Path(first.pdf_file).exists()
    assert Path(second_one.pdf_file).name == "jd-devsecops-marzo2026-2.pdf"


def test_history_can_be_rebuilt_if_the_index_is_lost(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )
    (tmp_path / "data" / "history.json").unlink()

    history = rebuild_history(tmp_path / "data")

    assert [entry.cv_name for entry in history] == ["DevSecOps at Acme"]


def test_rebuild_keeps_what_the_user_set_after_generating(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """Rebuilding recomputes what comes from the snapshot, but it cannot erase your decisions.

    The snapshot knows what you sent; it does not know you archived it on Tuesday nor
    why. The rebuild used to put every archived CV back on the list with its date and
    reason blank, which is not recomputing: it is losing.
    """
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )
    archive_cv(tmp_path / "data", cv.cv_id, archived=True)
    note_archive_reason(tmp_path / "data", cv.cv_id, "The posting closed")
    archived_before = load_history(tmp_path / "data")[0].archived_at

    history = rebuild_history(tmp_path / "data")

    assert len(history) == 1
    assert history[0].archived is True
    assert history[0].archive_reason == "The posting closed"
    assert history[0].archived_at == archived_before


def test_rebuild_does_not_revive_a_cv_whose_snapshot_is_gone(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """That part of the index IS a cache: if the snapshot is gone, the row goes with it."""
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )
    (tmp_path / "data" / "cvs" / f"{cv.cv_id}.json").unlink()

    assert rebuild_history(tmp_path / "data") == []


def test_the_filename_uses_the_cv_language(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="en",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    assert Path(cv.pdf_file).name == "jd-devsecops-march2026.pdf"


def test_saves_the_posting_with_the_cv(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Northwind",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
        posting=JobPosting(
            company="Northwind",
            url="https://example.com/posting/123",
            text="We are looking for a DevSecOps engineer with Kubernetes and Terraform.",
        ),
    )

    saved = load_cv(tmp_path / "data", cv.cv_id)

    assert saved.posting is not None
    assert saved.posting.company == "Northwind"
    assert "Kubernetes" in saved.posting.text


def test_a_cv_without_posting_is_still_valid(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="No posting",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    assert load_cv(tmp_path / "data", cv.cv_id).posting is None


def test_reads_a_snapshot_from_before_postings_existed(tmp_path: Path) -> None:
    """CVs already generated do not have the field and must keep opening."""
    from cv_generator.models.cv import GeneratedCV

    old = {
        "schema_version": 1,
        "cv_id": "cv-old",
        "created": "2026-03-15T10:30:00",
        "cv_name": "An older CV",
        "target_role": "DevSecOps",
        "language": "es",
        "template": "modern",
        "pdf_file": "output/jd-devsecops-marzo2026.pdf",
        "selection": {},
        "content": {"personal": REQUIRED},
    }

    cv = GeneratedCV.model_validate(old)

    assert cv.posting is None
    assert cv.cv_name == "An older CV"


@pytest.mark.parametrize(("template", "keeps_photo"), [("sidebar", True), ("technical", False)])
def test_snapshot_keeps_the_photo_only_if_the_template_prints_it(
    tmp_path: Path, profile: MasterProfile, selection: Selection, template: str, keeps_photo: bool
) -> None:
    """The snapshot is what was sent: a photo the template does not draw was not in the PDF."""
    profile.personal.photo = sample_photo()

    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="With photo",
        target_role="DevSecOps",
        language="es",
        template=template,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    saved = load_cv(tmp_path / "data", cv.cv_id)
    assert (saved.content.personal.photo is not None) is keeps_photo
    assert saved.selection.include_photo is True, "the recipe keeps what you asked for"


def test_regenerate_uses_the_saved_style(
    tmp_path: Path, profile: MasterProfile, selection: Selection, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection.style = Style(color=PaletteColor.RED)
    cv = generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="sidebar",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )
    received: dict[str, object] = {}
    monkeypatch.setattr(generation, "render_pdf", lambda *_a, **k: received.update(k) or b"%PDF-")

    regenerate_pdf(tmp_path / "data", cv.cv_id)

    assert received["style"] == Style(color=PaletteColor.RED)


def test_generate_uses_the_selection_style(
    tmp_path: Path, profile: MasterProfile, selection: Selection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PDF that is sent is the one that has to carry the style, not only the one rebuilt
    later from the history."""
    selection.style = Style(color=PaletteColor.RED)
    received: dict[str, object] = {}
    monkeypatch.setattr(generation, "render_pdf", lambda *_a, **k: received.update(k) or b"%PDF-")

    generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="sidebar",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )

    assert received["style"] == Style(color=PaletteColor.RED)
