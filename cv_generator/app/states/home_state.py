"""Home page state: CV history and profile status."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import reflex as rx

from cv_generator.app.config import DATA_DIR, OUTPUT_DIR
from cv_generator.rendering.i18n import load_language
from cv_generator.services.generation import rewrite_pdf
from cv_generator.services.profile import (
    load_profile,
    load_sync_status,
    pending_fields,
)
from cv_generator.services.system import open_with_viewer
from cv_generator.storage.history import archive_cv, load_history, note_archive_reason
from cv_generator.text import normalize, plural

# How many rows the scheme needs at least to read as a scheme and not as a loose card,
# and how many free rails get labeled at most. The cap keeps an empty history from
# turning into a wall of numbers with no content.
_MIN_RAILS = 9
_MAX_FREE = 6


def _days_since(moment: datetime) -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    return max((now - moment.replace(tzinfo=None)).days, 0)


def _in_words(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def _readable_date(moment: datetime) -> str:
    months = load_language("en").months
    return f"{moment.day} {months[moment.month - 1][:3].capitalize()} {moment.year}"


class HomeState(rx.State):
    """Everything the home page needs to show."""

    history: list[dict[str, str]] = []

    has_profile: bool = False
    profile_headline: str = ""
    profile_summary: str = ""
    # The summary breakdown, row by row, to lay it out as a status table.
    tallies: list[dict[str, str]] = []

    synced: bool = False
    sync_detail: str = ""
    content_language: str = ""

    notices: list[str] = []
    message: str = ""
    notice: str = ""
    search_query: str = ""
    show_archived: bool = False
    # cv_id being rebuilt right now, for that row's loading state.
    regenerating: str = ""

    @rx.event
    def load(self) -> None:
        """Reads profile, sync status and history from disk."""
        self.message = ""
        self._load_profile()
        self._load_sync()
        self._load_history()

    def _load_profile(self) -> None:
        profile = load_profile(DATA_DIR)
        self.has_profile = profile is not None
        self.notices = []

        if profile is None:
            self.profile_headline = ""
            self.profile_summary = ""
            self.tallies = []
            return

        self.profile_headline = f"{profile.personal.first_name} {profile.personal.last_name}"
        achievements = sum(len(experience.achievements) for experience in profile.experiences)
        self.profile_summary = " · ".join(
            [
                plural(len(profile.experiences), "experience", "experiences"),
                plural(achievements, "achievement", "achievements"),
                plural(len(profile.skills), "skill", "skills"),
                plural(len(profile.education), "study", "studies"),
            ]
        )
        # The same numbers, broken down. The legend strip lays them out as a status table,
        # with the label and the figure in columns that line up across rows; an already joined
        # string cannot be aligned.
        self.tallies = [
            {"caption": "Experiences", "value": str(len(profile.experiences))},
            {"caption": "Achievements", "value": str(achievements)},
            {"caption": "Skills", "value": str(len(profile.skills))},
            {"caption": "Studies", "value": str(len(profile.education))},
        ]

        pending = pending_fields(profile)
        if pending:
            missing_count = ", ".join(pending)
            self.notices.append(
                f"The importer could not bring this and it is required: {missing_count}. "
                "Until you complete it in My profile, the CV will print 'PENDING' in its place."
            )

    def _load_sync(self) -> None:
        status = load_sync_status(DATA_DIR)
        self.synced = status is not None

        if status is None:
            self.sync_detail = "Never synced with LinkedIn"
            self.content_language = ""
            return

        sources = {
            "linkedin_pdf": "profile PDF",
            "linkedin_zip": "export ZIP",
        }
        imported = ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in status.imported_items.items())
        self.sync_detail = (
            f"Synced from the {sources.get(status.source, status.source)} · "
            f"{_in_words(_days_since(status.timestamp))} · {imported}"
        )
        self.content_language = status.detected_language

    def _load_history(self) -> None:
        entries = load_history(DATA_DIR)
        # The rail number is assigned ONCE, over the full list and by age: the first CV you
        # generated is rail 01 and stays that way forever. It used to be derived from the
        # index in the already filtered list, so it renumbered just by typing in the search
        # box or showing the archived ones — an anchor that moves is not an anchor. It has two
        # digits because that is what the empty state promises.
        total = len(entries)
        self.history = [
            {
                "cv_id": entry.cv_id,
                "rail": f"{total - position:02d}",
                "name": entry.cv_name,
                "role": entry.target_role,
                "language": entry.language.upper(),
                "template": entry.template,
                # The template and the posting are what decide which one to clone; without them every
                # row looks alike and you have to open the PDFs to tell them apart.
                "posting": "yes" if entry.has_posting else "",
                "date": _readable_date(entry.created),
                "file": Path(entry.pdf_file).name,
                "path": entry.pdf_file,
                "archived": "yes" if entry.archived else "",
                # The exception row: when you took it off the list and why. The date is stamped
                # automatically on archive; you write the reason afterwards, if you want.
                "archived_at": _readable_date(entry.archived_at) if entry.archived_at else "",
                "reason": entry.archive_reason,
            }
            for position, entry in enumerate(entries)
        ]

    @rx.event
    def search(self, text: str) -> None:
        self.search_query = text

    @rx.event
    def clear_search(self) -> None:
        self.search_query = ""

    @rx.event
    def toggle_archived(self, value: bool) -> None:
        self.show_archived = value

    @rx.event
    def archive(self, cv_id: str, archived: bool) -> None:  # noqa: FBT001
        """Hides a CV from the view, or brings it back.

        It does not delete: the snapshot and the PDF stay where they were, because the
        history is only worth something if what you sent can be produced again.
        """
        self.message = ""
        self.notice = ""
        try:
            archive_cv(DATA_DIR, cv_id, archived=archived)
        except (KeyError, OSError) as error:
            self.message = f"That CV could not be archived: {error}"
            return
        self._load_history()

    @rx.var
    def visible_history(self) -> list[dict[str, str]]:
        """The filtered history. From the 20th application on, the list stops being readable."""
        candidates = self.history if self.show_archived else [cv for cv in self.history if not cv["archived"]]
        term = normalize(self.search_query)
        if not term:
            return candidates
        return [cv for cv in candidates if term in normalize(f"{cv['name']} {cv['role']} {cv['template']}")]

    @rx.event
    def note_reason(self, cv_id: str, reason: str) -> None:
        """Saves why you archived a CV, when you leave the field.

        It is written afterwards and on the row itself, not in a dialog before archiving:
        archiving is reversible, and this product saves its ceremony for what is not. But
        six months later the reason is the only thing that explains why that CV is not
        on the list.
        """
        self.message = ""
        try:
            note_archive_reason(DATA_DIR, cv_id, reason)
        except (KeyError, OSError) as error:
            self.message = f"The reason could not be saved: {error}"
            return
        self._load_history()

    @rx.var
    def free_rails(self) -> list[str]:
        """The next rail numbers, still unused.

        With a single CV the scheme ended after one row and left half the viewport black
        and unframed, so it read as a loose card — exactly the scaffolding this design
        rejects. Labeling the free rails brings it back to what it is: a scheme with
        room.

        They are not made-up rows. Numbering goes by age, so the next CV you generate
        will literally take the first of these numbers.

        They disappear when searching: there the list is a result, not a scheme.
        """
        if self.has_search:
            return []
        total = len(self.history)
        missing_count = min(max(_MIN_RAILS - len(self.visible_history), 0), _MAX_FREE)
        return [f"{total + following:02d}" for following in range(1, missing_count + 1)]

    @rx.var
    def archived_total(self) -> int:
        return sum(1 for cv in self.history if cv["archived"])

    @rx.var
    def has_archived(self) -> bool:
        return self.archived_total > 0

    @rx.var
    def archived_summary(self) -> str:
        return f"Show {plural(self.archived_total, 'archived', 'archived')}"

    @rx.var
    def has_search(self) -> bool:
        return self.search_query.strip() != ""

    @rx.var
    def no_results(self) -> bool:
        return self.has_search and len(self.visible_history) == 0

    @rx.var
    def search_summary(self) -> str:
        return plural(len(self.visible_history), "CV found", "CVs found")

    @rx.var
    def history_empty(self) -> bool:
        return len(self.history) == 0

    @rx.event
    def open_pdf(self, path: str) -> None:
        """Opens the PDF of a history CV with the system viewer.

        The two possible failures have different ways out, so they are reported
        separately instead of dumping the exception as is.
        """
        self.message = ""
        try:
            open_with_viewer(Path(path), OUTPUT_DIR)
        except FileNotFoundError:
            self.message = (
                f"The file {Path(path).name} is no longer in output/. "
                "Press Regenerate to rebuild it identical to the one you sent."
            )
        except ValueError:
            self.message = (
                "That CV's path points outside output/ and is not opened, for safety. "
                "If you edited data/history.json by hand, check its pdf_file field."
            )

    @rx.event
    async def regenerate(self, cv_id: str) -> AsyncGenerator[None, None]:
        """Rebuilds the PDF of a history CV over its original path.

        It reproduces the document that was sent —same date, same computed age— instead
        of creating a new one, which is what cloning does.
        """
        if self.regenerating:
            return

        self.regenerating = cv_id
        self.message = ""
        self.notice = ""
        yield

        try:
            target = await asyncio.to_thread(rewrite_pdf, DATA_DIR, OUTPUT_DIR, cv_id)
        except FileNotFoundError:
            self.message = "That CV's record was not found, so it cannot be rebuilt."
        except ValueError as error:
            self.message = f"The PDF could not be rebuilt: {error}"
        except (OSError, KeyError, RuntimeError) as error:
            self.message = f"The PDF could not be rebuilt: {error}"
        else:
            self.notice = f"Done: {target.name} is back in output/."
        self.regenerating = ""

    @rx.event
    def new_cv(self) -> rx.event.EventSpec:
        return rx.redirect("/new")

    @rx.event
    def open_sync(self) -> rx.event.EventSpec:
        return rx.redirect("/sync")

    @rx.event
    def go_to_profile(self) -> rx.event.EventSpec:
        return rx.redirect("/profile")

    @rx.event
    def clone(self, cv_id: str) -> rx.event.EventSpec:
        """Starts a new CV with the same selection as an earlier one."""
        return rx.redirect(f"/new?from={cv_id}")
