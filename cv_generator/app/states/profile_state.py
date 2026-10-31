"""State of the master profile screen.

It covers the personal details: the five fields the CV cannot print empty plus the
optional contact fields and the photo. Also the skills, because the LinkedIn PDF only
brings the top three. It also keeps which subsection of the screen is open. The
achievements of each job live in `ExperienceState`, which the Work experience
subsection uses.
"""

import asyncio
import json
from collections.abc import AsyncGenerator, Callable
from datetime import date
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services import skills as skill_operations
from cv_generator.services.photo import MAX_SIZE_BYTES, process_photo, set_photo
from cv_generator.services.profile import PENDING_FIELD, load_profile, save_profile, with_personal

FIELD_LABELS = {
    "first_name": "First name",
    "last_name": "Last name",
    "profession": "Profession",
    "phone": "Phone",
    "email": "Email",
}

# Allowlist of what the form can write. The field name comes from the browser, so it is
# checked against this list and not against the state attributes.
EDITABLE_FIELDS = (
    *FIELD_LABELS,
    "website",
    "country",
    "address",
    "birth_date",
)


# The subsections of the screen, in the order of the side menu. `/profile?section=skills`
# opens one directly.
PROFILE_SECTIONS: dict[str, str] = {
    "contact": "Contact",
    "photo": "Photo",
    "skills": "Skills",
    "experience": "Work experience",
}


def requested_section(value: str) -> str:
    """The subsection to open. The value comes from the address bar: anything that is not
    exactly a known section opens Contact."""
    return value if value in PROFILE_SECTIONS else "contact"


def section_url(section: str) -> str:
    return f"/profile?section={section}"


def _without_placeholder(value: str | None) -> str:
    """A pending field is shown empty, not with the word 'PENDING' inside.

    The placeholder exists so the profile is valid on disk, not so the user has to
    delete it by hand before typing their data.
    """
    return "" if value in (None, PENDING_FIELD) else str(value)


def _form_values(personal: PersonalInfo) -> dict[str, str]:
    """The Contact form for these details, field by field."""
    values = {field: _without_placeholder(getattr(personal, field)) for field in EDITABLE_FIELDS}
    values["birth_date"] = personal.birth_date.isoformat() if personal.birth_date else ""
    return values


def kept_typing(typed: dict[str, str], loaded: dict[str, str], on_disk: dict[str, str]) -> dict[str, str]:
    """The Contact form after reading the profile again.

    A field you changed and did not save keeps what you typed; the rest shows what is on
    disk now. `loaded` is what the form held when it was last read or saved; empty the
    first time, when everything comes from disk.
    """
    return {
        field: typed[field] if field in loaded and typed.get(field) != loaded[field] else value
        for field, value in on_disk.items()
    }


class ProfileState(rx.State):
    """Reads and writes the personal details of the master profile."""

    has_profile: bool = False
    section: str = "contact"
    saving: bool = False
    error_message: str = ""
    saved: bool = False

    first_name: str = ""
    last_name: str = ""
    profession: str = ""
    phone: str = ""
    email: str = ""

    website: str = ""
    country: str = ""
    address: str = ""
    birth_date: str = ""
    # What the fields held when they were last read from or saved to disk. `start` runs
    # again on Back from another subsection; with this it keeps what you typed and did not
    # save, and the form can say it is not saved yet.
    loaded_fields: dict[str, str] = {}

    # The already processed photo, as a data URI: the same string that goes into the CV's `src`.
    photo: str = ""
    uploading_photo: bool = False
    photo_error: str = ""

    skills: list[dict[str, str]] = []
    skills_error: str = ""
    # Part of each row's `key`. It goes up with every operation, so a rejected name shows the
    # saved one again instead of keeping what you typed.
    skills_version: int = 0

    @rx.event
    def start(self) -> None:
        """Loads the profile from disk and fills the form with the personal details."""
        self.section = requested_section(self.router.url.query_parameters.get("section", ""))
        self.error_message = ""
        self.saved = False

        profile = load_profile(DATA_DIR)
        self.has_profile = profile is not None
        if profile is None:
            return

        personal = profile.personal
        on_disk = _form_values(personal)
        self._fill(kept_typing(self._typed(), self.loaded_fields, on_disk))
        self.loaded_fields = on_disk
        self.photo = personal.photo or ""
        self.uploading_photo = False
        self.photo_error = ""
        self.skills_error = ""
        self.skills = _skill_rows(profile)

    def _typed(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in EDITABLE_FIELDS}

    def _fill(self, values: dict[str, str]) -> None:
        for field, value in values.items():
            setattr(self, field, value)

    @rx.event
    def show_section(self, name: str) -> rx.event.EventSpec | None:
        """Opens a subsection and adds it to the address bar, as a new step of the history.

        `history.pushState` and not `rx.redirect`: a redirect would run `start` on every
        click. Back does run it, and the Contact form keeps what you typed (`kept_typing`).
        The section is one of the allowlist, so the address is never the browser's text.
        """
        section = requested_section(name)
        if section == self.section:
            return None
        self.section = section
        return rx.call_script(f"window.history.pushState(null, '', {json.dumps(section_url(section))})")

    # ------------------------------------------------------------------ fields

    @rx.event
    def update(self, field: str, value: str) -> None:
        """Writes a form field and clears the previous saved notice."""
        if field in EDITABLE_FIELDS:
            setattr(self, field, value)
        self.saved = False

    @rx.var
    def missing(self) -> list[str]:
        """Labels of the required fields that are still empty."""
        values = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "profession": self.profession,
            "phone": self.phone,
            "email": self.email,
        }
        return [FIELD_LABELS[field] for field, value in values.items() if not value.strip()]

    # The dependencies are named because the body reads the fields by name.
    @rx.var(deps=[*EDITABLE_FIELDS, "loaded_fields"], auto_deps=False)
    def has_unsaved_changes(self) -> bool:
        """Whether the form holds something typed and not saved yet.

        It survives leaving the subsection and coming back, so the form says so instead of
        passing for saved.
        """
        return any(value != self.loaded_fields.get(field, value) for field, value in self._typed().items())

    @rx.var
    def can_save(self) -> bool:
        return len(self.missing) == 0

    @rx.var
    def missing_summary(self) -> str:
        return ", ".join(self.missing)

    # ------------------------------------------------------------------ saving

    def _date_or_none(self) -> date | None:
        """Parses the form date. Returns None if it is empty or not valid."""
        if not self.birth_date.strip():
            return None
        try:
            return date.fromisoformat(self.birth_date.strip())
        except ValueError:
            return None

    @rx.event
    async def save(self) -> AsyncGenerator[None, None]:
        """Writes the personal details without touching the rest of the profile.

        It starts from the profile on disk, like the skills: the achievements save on
        their own from this same screen, and the profile loaded when it opened would
        write their old text back.
        """
        if self.saving or not self.can_save:
            return

        self.saving = True
        self.error_message = ""
        self.saved = False
        yield

        try:
            on_disk = await asyncio.to_thread(load_profile, DATA_DIR)
            if on_disk is None:
                raise ValueError("There is no profile yet. Sync with LinkedIn first.")
            updated = with_personal(
                on_disk,
                PersonalInfo(
                    first_name=self.first_name.strip(),
                    last_name=self.last_name.strip(),
                    profession=self.profession.strip(),
                    phone=self.phone.strip(),
                    email=self.email.strip(),
                    website=self.website.strip() or None,
                    country=self.country.strip() or None,
                    address=self.address.strip() or None,
                    birth_date=self._date_or_none(),
                ),
            )
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.error_message = f"The profile could not be saved: {error}"
            self.saving = False
            return

        # The form shows what was written, trimmed, and that is what it now compares against.
        self.loaded_fields = _form_values(updated.personal)
        self._fill(self.loaded_fields)
        self.saved = True
        self.saving = False

    # ------------------------------------------------------------------- photo

    async def _change_photo(self, photo: str | None) -> None:
        """Saves the photo right away, without going through the personal details button.

        It starts from the profile on disk, like the skills: the one on screen may be
        stale if you synced in another tab in the meantime.
        """
        try:
            on_disk = await asyncio.to_thread(load_profile, DATA_DIR)
            if on_disk is None:
                raise ValueError("There is no profile yet. Sync with LinkedIn first.")
            updated = set_photo(on_disk, photo)
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.photo_error = str(error)
            return

        self.photo = photo or ""

    @rx.event
    async def upload_photo(self, files: list[rx.UploadFile]) -> AsyncGenerator[None, None]:
        """Processes the chosen photo and puts it in the profile.

        At most one byte over the limit is read: enough to know it went over, without
        loading a file of any size into memory.
        """
        if self.uploading_photo:
            return

        if not files:
            self.photo_error = "No photo was received. Drag it onto the box or click to choose it."
            return

        self.uploading_photo = True
        self.photo_error = ""
        yield

        try:
            data = await files[0].read(MAX_SIZE_BYTES + 1)
            photo = await asyncio.to_thread(process_photo, data)
        except (ValueError, OSError) as error:
            self.photo_error = str(error)
            self.uploading_photo = False
            return

        await self._change_photo(photo)
        self.uploading_photo = False

    @rx.event
    async def remove_photo(self) -> None:
        """Removes the photo from the profile. CVs already generated keep theirs."""
        self.photo_error = ""
        await self._change_photo(None)

    # ------------------------------------------------------------------ skills

    async def _change_skills(self, operation: Callable[[MasterProfile], MasterProfile]) -> None:
        """Applies an operation on the skills and saves it right away.

        It starts from the profile on disk and not from the one loaded when the screen
        opened: if you synced in another tab in the meantime, saving the old one would
        erase that.
        """
        self.skills_error = ""
        self.skills_version += 1
        try:
            on_disk = await asyncio.to_thread(load_profile, DATA_DIR)
            if on_disk is None:
                raise ValueError("There is no profile yet. Sync with LinkedIn first.")
            updated = operation(on_disk)
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.skills_error = str(error)
            return

        self.skills = _skill_rows(updated)

    @rx.event
    async def add_skill(self, data: dict[str, Any]) -> None:
        name = str(data.get("name", ""))
        await self._change_skills(lambda profile: skill_operations.add_skill(profile, name))

    async def _rename(self, skill_id: str, name: str) -> None:
        """It arrives twice per edit, on Enter and when leaving the field: if the name did
        not change, it does nothing."""
        current = next((row["name"] for row in self.skills if row["id"] == skill_id), None)
        if current is None or name.strip() == current:
            return
        await self._change_skills(lambda profile: skill_operations.rename_skill(profile, skill_id, name))

    @rx.event
    async def rename_skill(self, skill_id: str, name: str) -> None:
        """When leaving the field."""
        await self._rename(skill_id, name)

    @rx.event
    async def rename_from_form(self, data: dict[str, Any]) -> None:
        """When pressing Enter."""
        await self._rename(str(data.get("id", "")), str(data.get("name", "")))

    @rx.event
    async def remove_skill(self, skill_id: str) -> None:
        await self._change_skills(lambda profile: skill_operations.remove_skill(profile, skill_id))

    @rx.event
    def back_to_home(self) -> rx.event.EventSpec:
        return rx.redirect("/")

    @rx.event
    def go_to_sync(self) -> rx.event.EventSpec:
        return rx.redirect("/sync")


def _skill_rows(profile: MasterProfile) -> list[dict[str, str]]:
    return [{"id": skill.id, "name": skill.name} for skill in profile.skills]
