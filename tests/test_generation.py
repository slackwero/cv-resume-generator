import shutil
from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.models.cv import GeneratedCV, JobPosting, SelectedExperience, Selection
from cv_generator.models.profile import FIRST_PROFESSION_ID, Achievement, Experience, MasterProfile, Skill
from cv_generator.models.style import PaletteColor, Style
from cv_generator.rendering.i18n import default_sections
from cv_generator.services import generation
from cv_generator.services.achievements import add_achievement_in
from cv_generator.services.generation import generate_cv, load_cv, regenerate_pdf, rename_cv, save_cv
from cv_generator.services.professions import add_profession
from cv_generator.services.translations import save_translation, text_key
from cv_generator.storage.history import (
    UnreadableHistoryError,
    archive_cv,
    load_history,
    note_archive_reason,
    rebuild_history,
    rebuild_unreadable_history,
)
from tests.bilingual import sample_profile
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


def _generated(tmp_path: Path, profile: MasterProfile, selection: Selection) -> str:
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
    return cv.cv_id


def test_renaming_changes_the_name_in_the_snapshot_and_the_list(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    cv_id = _generated(tmp_path, profile, selection)

    rename_cv(tmp_path / "data", cv_id, "  Acme, platform team  ")

    assert load_cv(tmp_path / "data", cv_id).cv_name == "Acme, platform team"
    assert [entry.cv_name for entry in load_history(tmp_path / "data")] == ["Acme, platform team"]


def test_renaming_leaves_what_was_sent_untouched(tmp_path: Path, profile: MasterProfile, selection: Selection) -> None:
    """The name is only how the list shows it: the PDF does not print it, so Regenerate still gives the same one."""
    cv_id = _generated(tmp_path, profile, selection)
    before = load_cv(tmp_path / "data", cv_id)
    pdf = Path(before.pdf_file)
    pdf_before = pdf.read_bytes()

    rename_cv(tmp_path / "data", cv_id, "Acme, platform team")

    after = load_cv(tmp_path / "data", cv_id)
    assert after.model_dump(exclude={"cv_name"}) == before.model_dump(exclude={"cv_name"})
    assert pdf.read_bytes() == pdf_before


def test_a_renamed_cv_keeps_its_name_when_the_list_is_rebuilt(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """The list is rebuilt from the snapshots; a name kept only in the list would be lost."""
    cv_id = _generated(tmp_path, profile, selection)
    rename_cv(tmp_path / "data", cv_id, "Acme, platform team")
    (tmp_path / "data" / "history.json").unlink()

    assert [entry.cv_name for entry in rebuild_history(tmp_path / "data")] == ["Acme, platform team"]


def test_a_blank_name_is_refused_and_nothing_changes(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    cv_id = _generated(tmp_path, profile, selection)

    with pytest.raises(ValueError, match="name"):
        rename_cv(tmp_path / "data", cv_id, "   ")

    assert load_cv(tmp_path / "data", cv_id).cv_name == "DevSecOps at Acme"
    assert [entry.cv_name for entry in load_history(tmp_path / "data")] == ["DevSecOps at Acme"]


def test_renaming_a_cv_with_no_snapshot_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rename_cv(tmp_path / "data", "cv-0123456789ab", "Acme")


@pytest.mark.parametrize("cv_id", ["../profile", "cvs/../../profile", "{data}/profile", "cv-ghost", ""])
def test_an_id_that_is_not_a_cv_id_opens_no_file(tmp_path: Path, cv_id: str) -> None:
    """The id comes from the browser, and any page can send one: `/new?from=` clones what it names.

    Turned into a path as it came, "../profile" read data/profile.json, and the validation
    error showed pieces of it on screen.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "profile.json").write_text('{"personal": {"email": "maya@example.com"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="not a CV id") as error:
        load_cv(data_dir, cv_id.format(data=data_dir))

    assert "maya@example.com" not in str(error.value)


def test_a_snapshot_is_never_written_outside_its_folder(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """Renaming saves the snapshot under the id written inside it: a planted snapshot whose id
    climbs out of data/cvs/ would write wherever it points."""
    data_dir = tmp_path / "data"
    cv = load_cv(data_dir, _generated(tmp_path, profile, selection))

    with pytest.raises(ValueError, match="not a CV id"):
        save_cv(data_dir, cv.model_copy(update={"cv_id": "../../planted"}))

    assert not (tmp_path / "planted.json").exists()


def test_a_snapshot_that_says_it_is_another_cv_is_refused(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """A copied snapshot keeps the original's id inside: renaming the copy would overwrite the original."""
    data_dir = tmp_path / "data"
    cv_id = _generated(tmp_path, profile, selection)
    copy = "cv-0123456789ab"
    shutil.copy(data_dir / "cvs" / f"{cv_id}.json", data_dir / "cvs" / f"{copy}.json")

    with pytest.raises(ValueError, match="another CV"):
        load_cv(data_dir, copy)


def _bilingual_selection(achievement_id: str = "ach-1") -> Selection:
    return Selection(
        experiences=[SelectedExperience(id="exp-1", achievements=[achievement_id])],
        skills=["skill-1"],
        sections=default_sections("es"),
    )


def _generate_in(tmp_path: Path, profile: MasterProfile, selection: Selection, language: str) -> GeneratedCV:
    return generate_cv(
        profile=profile,
        selection=selection,
        cv_name="Bilingual",
        target_role="DevSecOps",
        language=language,
        template="modern",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        created=CREATED,
    )


def test_a_spanish_cv_uses_the_spanish_content_and_falls_back_to_english(tmp_path: Path) -> None:
    profile = save_translation(sample_profile(), "es", text_key("ach-1", "text"), "Reduje el despliegue en 40%")
    profile = save_translation(profile, "es", text_key(FIRST_PROFESSION_ID, "text"), "Ingeniera DevSecOps")

    cv = _generate_in(tmp_path, profile, _bilingual_selection(), "es")

    assert cv.content.experiences[0].achievements[0].text == "Reduje el despliegue en 40%"
    assert cv.content.experiences[0].role == "Platform Engineer", "no Spanish role: falls back to English"
    assert cv.content.personal.profession == "Ingeniera DevSecOps"
    assert "translations" not in cv.content.model_dump()


def test_an_empty_spanish_profession_prints_the_english_one(tmp_path: Path) -> None:
    cv = _generate_in(tmp_path, sample_profile(), _bilingual_selection(), "es")

    assert cv.content.personal.profession == "DevSecOps Engineer"


def test_an_english_cv_prints_an_achievement_written_only_in_spanish_with_its_spanish(tmp_path: Path) -> None:
    profile = add_achievement_in(sample_profile(), "exp-1", "Automaticé las revisiones", "es")
    new_id = profile.experiences[0].achievements[-1].id

    cv = _generate_in(tmp_path, profile, _bilingual_selection(new_id), "en")

    assert cv.content.experiences[0].achievements[0].text == "Automaticé las revisiones"


def test_the_chosen_profession_is_printed_in_the_cv_language(tmp_path: Path) -> None:
    profile = add_profession(sample_profile(), "Security Architect", "en")
    chosen = profile.professions[-1].id
    profile = save_translation(profile, "es", text_key(chosen, "text"), "Arquitecta de seguridad")
    selection = _bilingual_selection().model_copy(update={"profession_id": chosen})

    cv = _generate_in(tmp_path, profile, selection, "es")

    assert cv.content.personal.profession == "Arquitecta de seguridad"


def test_a_profession_written_only_in_spanish_prints_its_spanish_in_english(tmp_path: Path) -> None:
    profile = add_profession(sample_profile(), "Arquitecta de seguridad", "es")
    selection = _bilingual_selection().model_copy(update={"profession_id": profile.professions[-1].id})

    cv = _generate_in(tmp_path, profile, selection, "en")

    assert cv.content.personal.profession == "Arquitecta de seguridad"


def _generate_into(data_dir: Path, output_dir: Path, profile: MasterProfile, selection: Selection) -> GeneratedCV:
    return generate_cv(
        profile=profile,
        selection=selection,
        cv_name="DevSecOps at Acme",
        target_role="DevSecOps",
        language="es",
        template="modern",
        data_dir=data_dir,
        output_dir=output_dir,
        created=CREATED,
    )


def test_a_damaged_list_stops_the_cv_before_anything_is_written(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    """Writing first left a PDF in output/ and a copy in data/cvs that no list showed."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "history.json").write_bytes(b'{"entries": [ ')

    with pytest.raises(UnreadableHistoryError):
        _generate_into(data_dir, tmp_path / "output", profile, selection)

    assert not (tmp_path / "output").exists()
    assert not (data_dir / "cvs").exists()


def test_an_unreadable_list_is_rebuilt_from_the_cvs_and_kept_aside(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    data_dir = tmp_path / "data"
    _generate_into(data_dir, tmp_path / "output", profile, selection)
    damaged = b'{"entries": [ '
    (data_dir / "history.json").write_bytes(damaged)

    history, aside = rebuild_unreadable_history(data_dir, datetime(2026, 11, 10, 18, 30, 5))  # noqa: DTZ001

    assert [entry.cv_name for entry in history] == ["DevSecOps at Acme"]
    assert [entry.cv_name for entry in load_history(data_dir)] == ["DevSecOps at Acme"]
    assert aside == data_dir / "history.20261110-183005.json"
    assert aside.read_bytes() == damaged


def test_a_damaged_cv_copy_stops_the_rebuild_and_moves_nothing(
    tmp_path: Path, profile: MasterProfile, selection: Selection
) -> None:
    data_dir = tmp_path / "data"
    cv = _generate_into(data_dir, tmp_path / "output", profile, selection)
    (data_dir / "history.json").write_bytes(b"{")
    (data_dir / "cvs" / f"{cv.cv_id}.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match=rf"^{cv.cv_id}\.json is not valid JSON"):
        rebuild_unreadable_history(data_dir, datetime(2026, 11, 10, 18, 30, 5))  # noqa: DTZ001

    assert (data_dir / "history.json").read_bytes() == b"{"
    assert list(data_dir.glob("history.*.json")) == []
