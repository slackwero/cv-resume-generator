"""State of the master profile screen.

It covers the personal details: the five fields the CV cannot print empty plus the
optional contact fields and the photo. Also the skills, because the LinkedIn PDF only
brings the top three. Experiences and achievements are not edited here; they come in and
are updated through the sync.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from datetime import date
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services import skills as skill_operations
from cv_generator.services.photo import MAX_SIZE_BYTES, process_photo, set_photo
from cv_generator.services.profile import PENDING_FIELD, load_profile, save_profile

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


def _without_placeholder(value: str | None) -> str:
    """A pending field is shown empty, not with the word 'PENDING' inside.

    The placeholder exists so the profile is valid on disk, not so the user has to
    delete it by hand before typing their data.
    """
    return "" if value in (None, PENDING_FIELD) else str(value)


class ProfileState(rx.State):
    """Reads and writes the personal details of the master profile."""

    _profile: MasterProfile | None = None

    has_profile: bool = False
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
        self.error_message = ""
        self.saved = False

        profile = load_profile(DATA_DIR)
        self._profile = profile
        self.has_profile = profile is not None
        if profile is None:
            return

        personal = profile.personal
        self.first_name = _without_placeholder(personal.first_name)
        self.last_name = _without_placeholder(personal.last_name)
        self.profession = _without_placeholder(personal.profession)
        self.phone = _without_placeholder(personal.phone)
        self.email = _without_placeholder(personal.email)
        self.website = _without_placeholder(personal.website)
        self.country = _without_placeholder(personal.country)
        self.address = _without_placeholder(personal.address)
        self.birth_date = personal.birth_date.isoformat() if personal.birth_date else ""
        self.photo = personal.photo or ""
        self.uploading_photo = False
        self.photo_error = ""
        self.skills_error = ""
        self.skills = _skill_rows(profile)

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
        """Writes the personal details without touching the rest of the profile."""
        if self.saving or self._profile is None or not self.can_save:
            return

        self.saving = True
        self.error_message = ""
        self.saved = False
        yield

        try:
            updated = self._profile.model_copy(deep=True)
            updated.personal = PersonalInfo(
                first_name=self.first_name.strip(),
                last_name=self.last_name.strip(),
                profession=self.profession.strip(),
                phone=self.phone.strip(),
                email=self.email.strip(),
                website=self.website.strip() or None,
                country=self.country.strip() or None,
                address=self.address.strip() or None,
                birth_date=self._date_or_none(),
                photo=self._profile.personal.photo,
            )
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.error_message = f"The profile could not be saved: {error}"
            self.saving = False
            return

        self._profile = updated
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

        self._profile = updated
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

        self._profile = updated
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
