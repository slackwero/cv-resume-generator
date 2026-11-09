"""The whole use case: turn a selection into a PDF and leave it recorded.

It is the only place that knows the order of the steps, so neither the interface nor
the command line has to repeat it.
"""

import re
from datetime import datetime
from pathlib import Path

from cv_generator.models.cv import GeneratedCV, JobPosting, Selection
from cv_generator.models.profile import MasterProfile
from cv_generator.rendering.filename import build_filename, resolve_available_path
from cv_generator.rendering.renderer import load_meta, render_pdf
from cv_generator.services.translations import in_language
from cv_generator.storage.history import cvs_dir, register_cv, rename_entry
from cv_generator.storage.repo import read_json, save_json
from cv_generator.tailoring.resolver import resolve_content

# What `GeneratedCV` gives every CV. The id arrives from the browser, and any page can send
# one (`/new?from=` clones what it names): only an id of this form becomes a path.
CV_ID = re.compile(r"cv-[0-9a-f]{12}")


def _snapshot_path(data_dir: Path, cv_id: str) -> Path:
    if not CV_ID.fullmatch(cv_id):
        raise ValueError(f"not a CV id: {cv_id!r}")
    return cvs_dir(data_dir) / f"{cv_id}.json"


def load_cv(data_dir: Path, cv_id: str) -> GeneratedCV:
    """Loads the frozen snapshot of an already generated CV.

    Raises:
        ValueError: if the id is not a CV id, or the snapshot says it is another CV.
        FileNotFoundError: if the CV has no snapshot.
    """
    cv = GeneratedCV.model_validate(read_json(_snapshot_path(data_dir, cv_id)))
    # It is saved back under the id written inside it: a copy that keeps the original's id
    # would overwrite the original when renamed.
    if cv.cv_id != cv_id:
        raise ValueError(f"the snapshot {cv_id} says it is another CV")
    return cv


def save_cv(data_dir: Path, cv: GeneratedCV) -> None:
    """Writes the CV snapshot. Once written, what it says is never modified; only its name can change."""
    cvs_dir(data_dir).mkdir(parents=True, exist_ok=True)
    save_json(_snapshot_path(data_dir, cv.cv_id), cv.model_dump(mode="json"))


def rename_cv(data_dir: Path, cv_id: str, name: str) -> GeneratedCV:
    """Changes the name a CV is listed under, and nothing else.

    The name is how you find it in the history; the PDF does not print it, so what you
    sent stays as it was and Regenerate still produces the same document. It goes to the
    snapshot first, which is where the list is rebuilt from, and then to the list.

    Raises:
        ValueError: if the name is blank.
        FileNotFoundError: if the CV has no snapshot.
        KeyError: if the CV is not in the list.
    """
    new_name = name.strip()
    if not new_name:
        raise ValueError("a CV needs a name")

    cv = load_cv(data_dir, cv_id).model_copy(update={"cv_name": new_name})
    save_cv(data_dir, cv)
    rename_entry(data_dir, cv_id, new_name)
    return cv


def generate_cv(
    *,
    profile: MasterProfile,
    selection: Selection,
    cv_name: str,
    target_role: str,
    language: str,
    template: str,
    data_dir: Path,
    output_dir: Path,
    created: datetime,
    posting: JobPosting | None = None,
) -> GeneratedCV:
    """Resolves the selection, writes the PDF and records the CV in the history.

    The PDF never overwrites an earlier one: if the name already exists a suffix is
    added, because the history is only useful if what you sent is still there.
    """
    # The one place that guarantees a CV is built in its own language: every caller gets it.
    content = resolve_content(in_language(profile, language), selection)
    # The snapshot is what was sent: a photo the template does not draw was not in the
    # PDF. The recipe still keeps that you asked for it, for when you clone it.
    if not load_meta(template).supports_photo:
        content.personal.photo = None

    output_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_available_path(
        output_dir,
        build_filename(
            first_name=content.personal.first_name,
            last_name=content.personal.last_name,
            role=target_role,
            on_date=created.date(),
            language=language,
        ),
    )
    target.write_bytes(render_pdf(content, template, today=created.date(), language=language, style=selection.style))

    cv = GeneratedCV(
        created=created,
        cv_name=cv_name,
        target_role=target_role,
        language=language,
        template=template,
        pdf_file=str(target),
        selection=selection,
        content=content,
        posting=posting,
    )
    save_cv(data_dir, cv)
    register_cv(data_dir, cv)
    return cv


def rewrite_pdf(data_dir: Path, output_dir: Path, cv_id: str) -> Path:
    """Rebuilds the PDF of a history CV and leaves it at its original path.

    It is what is needed when the file was deleted from output/: it reproduces the
    document exactly as it was sent, without creating a new history entry.

    Raises:
        ValueError: if the recorded path points outside the output directory.
    """
    cv = load_cv(data_dir, cv_id)
    target = Path(cv.pdf_file).resolve()
    if not target.is_relative_to(output_dir.resolve()):
        raise ValueError(f"the CV path points outside the output directory: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(regenerate_pdf(data_dir, cv_id))
    return target


def regenerate_pdf(data_dir: Path, cv_id: str) -> bytes:
    """Rebuilds the PDF of a history CV from its snapshot.

    It uses the original creation date, so the resulting document is the same one
    that was sent, including the age shown.
    """
    cv = load_cv(data_dir, cv_id)
    return render_pdf(cv.content, cv.template, today=cv.created.date(), language=cv.language, style=cv.selection.style)
