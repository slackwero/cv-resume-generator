"""Where the wizard writes the PDF preview.

Reflex serves its upload folder at /_upload to any program on this computer that asks,
and the preview is your CV: its name cannot be guessed, and the previews nobody looks at
any more are deleted.
"""

import os
import re
import time
from pathlib import Path

import pytest

from cv_generator.app.states import wizard_state
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.services.profile import save_profile
from tests import bilingual
from tests.screens import new_state, run

PDF = b"%PDF-1.7 a CV"
DAY = 24 * 60 * 60


@pytest.fixture(autouse=True)
def fast_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """The file is what is tested, not WeasyPrint."""
    monkeypatch.setattr(wizard_state, "render_pdf_and_pages", lambda *_, **__: (PDF, 1))


def _wizard(data_dir: Path) -> WizardState:
    save_profile(data_dir, bilingual.sample_profile())
    state = new_state(WizardState, "/new")
    run(WizardState.start, state)
    return state


def _file(state: WizardState, upload_dir: Path) -> Path:
    return upload_dir / state.pdf_preview.split("?")[0]


def test_each_tab_writes_its_preview_under_a_name_nobody_can_guess(screen_data: Path, upload_dir: Path) -> None:
    tabs = [_wizard(screen_data), _wizard(screen_data)]

    for tab in tabs:
        run(WizardState.preview, tab)

    names = {_file(tab, upload_dir).name for tab in tabs}
    assert len(names) == 2
    for name in names:
        assert re.fullmatch(r"preview-[A-Za-z0-9_-]{22,}\.pdf", name), name
    assert _file(tabs[0], upload_dir).read_bytes() == PDF


def test_a_new_render_overwrites_the_tab_s_preview(screen_data: Path, upload_dir: Path) -> None:
    """One file per tab, not one per render; the counter in the URL skips the browser's cache."""
    wizard = _wizard(screen_data)
    run(WizardState.preview, wizard)
    first = wizard.pdf_preview

    run(WizardState.preview, wizard)

    assert wizard.pdf_preview != first
    assert list(upload_dir.iterdir()) == [_file(wizard, upload_dir)]


def test_opening_the_wizard_deletes_the_previews_left_behind(screen_data: Path, upload_dir: Path) -> None:
    """The fixed names older versions wrote, and the previews of tabs closed long ago."""
    upload_dir.mkdir()
    for name in ("preview.pdf", "previsualizacion.pdf", "preview-closed.pdf", "preview-open.pdf", "other.pdf"):
        (upload_dir / name).write_bytes(PDF)
    two_days_ago = time.time() - 2 * DAY
    os.utime(upload_dir / "preview-closed.pdf", (two_days_ago, two_days_ago))

    _wizard(screen_data)

    assert sorted(path.name for path in upload_dir.iterdir()) == ["other.pdf", "preview-open.pdf"]
