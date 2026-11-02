"""State of the master profile screen.

It covers the personal details: the five fields the CV cannot print empty plus the
optional contact fields and the photo. Also the skills, because the LinkedIn PDF only
brings the top three. It also keeps which subsection of the screen is open, the language
the profile is shown and edited in, and what is pending in each subsection. The
achievements of each job live in `ExperienceState`, which the Work experience
subsection uses.

Only the profession, among the personal details, has a version per language. The other
details are the same in both, so the form keeps them whatever language is on screen.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from datetime import date
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.app.errors import as_sentence, readable
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.rendering.i18n import available_languages, language_name
from cv_generator.services import skills as skill_operations
from cv_generator.services.photo import MAX_SIZE_BYTES, process_photo, set_photo
from cv_generator.services.preferences import load_content_language, save_content_language, starting_language
from cv_generator.services.profile import PENDING_FIELD, load_profile, save_profile, with_personal
from cv_generator.services.translations import (
    PROFESSION_KEY,
    SILENT_FIELDS,
    TextState,
    after_source_edit,
    confirm,
    other_language,
    pending_by_section,
    save_translation,
    source_text_of,
    state_in,
    text_in,
    text_key,
)

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
    "presentation": "Presentation",
    "experience": "Work experience",
    "education": "Education",
    "skills": "Skills",
    "languages": "Languages",
    "courses": "Courses",
}

# The texts of a skill that have a version per language, with their label on screen.
SKILL_FIELDS: dict[str, str] = {"name": "Name", "category": "Category", "level": "Level"}


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


def text_version(profile: MasterProfile, language: str, key: str, *, silent: bool = False) -> dict[str, str]:
    """One translatable text as a row of My profile shows it in `language`.

    - `text`: what is shown, the other language's text while this one is missing;
    - `own`: this language's own text, empty while missing: an editor starts from it;
    - `state`: "missing", "review" or "" when current. `silent` leaves a missing one
      unmarked: a skill name is usually the same in both languages;
    - `reference` and `reference_language`: the other version and its language's name,
      only while this one is pending, which is when there is something to compare;
    - `copyable`: "yes" when "Use the same text" applies: a pending version in the other
      language whose source has text to copy.

    Text and not bool everywhere: Reflex walks the rows as `dict[str, str]`.
    """
    state = state_in(profile, language, key)
    shown = "" if state is TextState.CURRENT or (silent and state is TextState.MISSING) else state.value
    other = other_language(language)
    text = text_in(profile, language, key)
    copyable = shown and language != profile.source_language and source_text_of(profile, key)
    return {
        "key": key,
        "text": text,
        "own": "" if state is TextState.MISSING else text,
        "state": shown,
        "reference": text_in(profile, other, key) if shown else "",
        "reference_language": language_name(other),
        "copyable": "yes" if copyable else "",
    }


def _form_values(profile: MasterProfile, language: str) -> dict[str, str]:
    """The Contact form for this profile in `language`, field by field.

    In the other language the profession is that language's own text, empty while it is
    missing: the source one is its reference, never its value.
    """
    personal = profile.personal
    values = {field: _without_placeholder(getattr(personal, field)) for field in EDITABLE_FIELDS}
    values["birth_date"] = personal.birth_date.isoformat() if personal.birth_date else ""
    if language != profile.source_language:
        values["profession"] = text_version(profile, language, PROFESSION_KEY)["own"]
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

    # The language the profile is shown and edited in, and the one LinkedIn feeds.
    language: str = ""
    source_language: str = ""
    # Why the switch could not be remembered. It is shown above every subsection.
    language_error: str = ""
    # Pending texts of each subsection in `language`, as text: "" when there are none.
    section_counts: dict[str, str] = dict.fromkeys(PROFILE_SECTIONS, "")

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
    # The profession typed and not saved in a language that is not on screen, by language.
    # Flipping the switch never carries it into the other language's field.
    held_professions: dict[str, str] = {}
    # The profession's version in `language`: "missing", "review" or "" when current; and
    # the other language's text beside it while it is pending.
    profession_state: str = ""
    profession_reference: str = ""

    # The already processed photo, as a data URI: the same string that goes into the CV's `src`.
    photo: str = ""
    uploading_photo: bool = False
    photo_error: str = ""

    # Each skill as `skill_rows` builds it: its name, category and level in `language`.
    skills: list[dict[str, dict[str, str]]] = []
    skills_error: str = ""
    # Part of each row's `key`. It goes up with every operation, so a rejected name shows the
    # saved one again instead of keeping what you typed.
    skills_version: int = 0

    @rx.event
    def start(self) -> None:
        """Loads the profile from disk and fills the form with the personal details."""
        self.section = requested_section(self.router.url.query_parameters.get("section", ""))
        self.error_message = ""
        self.language_error = ""
        self.saved = False

        profile = load_profile(DATA_DIR)
        self.has_profile = profile is not None
        # Read on every open, like Home: the remembered language is the one a page opens in.
        source = profile.source_language if profile is not None else None
        self._move_to(starting_language(load_content_language(DATA_DIR), source))
        if profile is None:
            return

        self._read(profile)
        self.photo = profile.personal.photo or ""
        self.uploading_photo = False
        self.photo_error = ""
        self.skills_error = ""

    def _typed(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in EDITABLE_FIELDS}

    def _fill(self, values: dict[str, str]) -> None:
        for field, value in values.items():
            setattr(self, field, value)

    def _move_to(self, code: str) -> None:
        """Puts the screen in another language. A profession typed and not saved is held
        in the language it was typed in."""
        if code == self.language:
            return
        loaded = self.loaded_fields.get("profession")
        if loaded is not None and self.profession != loaded:
            self.held_professions = {**self.held_professions, self.language: self.profession}
        # Without a loaded profession, `_read` takes the new language's from disk, or the
        # one held for it, instead of keeping the old language's typing in its field.
        self.loaded_fields = {field: value for field, value in self.loaded_fields.items() if field != "profession"}
        self.language = code

    def _read(self, profile: MasterProfile) -> None:
        """Fills the screen from the profile on disk, in the language on screen.

        It keeps what you typed and did not save: the Contact fields (`kept_typing`) and
        the profession held for this language while another one was on screen.
        """
        self.source_language = profile.source_language or ""
        on_disk = _form_values(profile, self.language)
        form = kept_typing(self._typed(), self.loaded_fields, on_disk)
        if self.language in self.held_professions:
            held = dict(self.held_professions)
            form["profession"] = held.pop(self.language)
            self.held_professions = held
        self._fill(form)
        self.loaded_fields = on_disk
        self._show_profession(profile)
        self.skills = skill_rows(profile, self.language)
        self._count(profile)

    def _show_profession(self, profile: MasterProfile) -> None:
        version = text_version(profile, self.language, PROFESSION_KEY)
        self.profession_state = version["state"]
        self.profession_reference = _without_placeholder(version["reference"])

    def _count(self, profile: MasterProfile) -> None:
        counts = pending_by_section(profile, self.language)
        self.section_counts = {name: str(counts[name]) if counts.get(name) else "" for name in PROFILE_SECTIONS}

    @rx.event
    def refresh_counts(self) -> None:
        """Counts again, from disk, what is pending in each subsection.

        The other states of My profile save on their own and return this after each write.
        """
        profile = load_profile(DATA_DIR)
        if profile is not None:
            self._count(profile)

    @rx.event
    def switch_language(self, code: str) -> None:
        """Shows and edits the profile in another language, and remembers the choice.

        What you typed and did not save stays with the language it was typed in.
        """
        if code not in available_languages():
            return
        self.error_message = ""
        self.skills_error = ""
        self.language_error = ""
        self.saved = False
        self._move_to(code)
        # Like Home: the switch stays applied in memory even when the choice cannot be
        # saved, and the message says it will not be remembered.
        try:
            save_content_language(DATA_DIR, code)
        except OSError as error:
            self.language_error = f"The language could not be remembered: {readable(error)}"
        profile = load_profile(DATA_DIR)
        if profile is not None:
            self._read(profile)

    @rx.event
    def show_section(self, name: str) -> rx.event.EventSpec | None:
        """Opens a subsection and adds it to the address bar, as a new step of the history.

        Through the router, with `rx.redirect`, and not with `history.pushState`: the router
        does not see a pushState, and Back to an address it still took for the current one
        ran nothing, leaving the address on one subsection and the screen on another. So
        `start` runs on every click; the Contact form keeps what you typed (`kept_typing`).
        The section is one of the allowlist, so the address is never the browser's text.
        """
        section = requested_section(name)
        if section == self.section:
            return None
        self.section = section
        return rx.redirect(section_url(section))

    # ------------------------------------------------------------------ fields

    @rx.event
    def update(self, field: str, value: str) -> None:
        """Writes a form field and clears the previous saved notice."""
        if field in EDITABLE_FIELDS:
            setattr(self, field, value)
        self.saved = False

    @rx.var
    def profession_required(self) -> bool:
        """Only in the source language: an empty translation prints the source profession."""
        return self.language == self.source_language

    @rx.var
    def reference_language(self) -> str:
        """The name of the other language, which the references are written in."""
        return language_name(other_language(self.language)) if self.language else ""

    @rx.var
    def missing(self) -> list[str]:
        """Labels of the required fields that are still empty."""
        values = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "email": self.email,
        }
        if self.language == self.source_language:
            values["profession"] = self.profession
        return [label for field, label in FIELD_LABELS.items() if field in values and not values[field].strip()]

    def _form_differs(self) -> bool:
        return any(value != self.loaded_fields.get(field, value) for field, value in self._typed().items())

    # The dependencies are named because the body reads the fields by name.
    @rx.var(deps=[*EDITABLE_FIELDS, "loaded_fields", "held_professions"], auto_deps=False)
    def has_unsaved_changes(self) -> bool:
        """Whether the form holds something typed and not saved yet, in any language.

        It survives leaving the subsection and coming back, so the form says so instead of
        passing for saved.
        """
        return self._form_differs() or bool(self.held_professions)

    @rx.var(deps=[*EDITABLE_FIELDS, "loaded_fields", "held_professions", "language"], auto_deps=False)
    def unsaved_languages(self) -> str:
        """The codes of the languages holding unsaved changes, as "EN, ES".

        The form on screen counts as the language on screen: the fields that are the same
        in both languages are saved with it.
        """
        codes = set(self.held_professions)
        if self._form_differs():
            codes.add(self.language)
        return ", ".join(code.upper() for code in sorted(codes))

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
            in_source = self.language == on_disk.source_language
            updated = with_personal(
                on_disk,
                PersonalInfo(
                    first_name=self.first_name.strip(),
                    last_name=self.last_name.strip(),
                    # In the other language the field is a translation: the source
                    # profession stays as it is on disk.
                    profession=self.profession.strip() if in_source else on_disk.personal.profession,
                    phone=self.phone.strip(),
                    email=self.email.strip(),
                    website=self.website.strip() or None,
                    country=self.country.strip() or None,
                    address=self.address.strip() or None,
                    birth_date=self._date_or_none(),
                ),
            )
            if in_source:
                updated = after_source_edit(updated, PROFESSION_KEY, on_disk.personal.profession)
            else:
                # Empty, it writes no translation: the CV prints the source profession.
                updated = save_translation(updated, self.language, PROFESSION_KEY, self.profession)
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.error_message = f"The profile could not be saved: {readable(error)}"
            self.saving = False
            return

        # The form shows what was written, trimmed, and that is what it now compares against.
        self.loaded_fields = _form_values(updated, self.language)
        self._fill(self.loaded_fields)
        self._show_profession(updated)
        self._count(updated)
        self.saved = True
        self.saving = False

    @rx.event
    async def confirm_profession(self) -> None:
        """ "Still good" on a profession pending review: it is current again, as it is.

        It saves right away, unlike the rest of the form, and leaves what you typed alone.
        """
        if self.profession_state != TextState.REVIEW:
            return
        self.error_message = ""
        self.saved = False
        try:
            on_disk = await asyncio.to_thread(load_profile, DATA_DIR)
            if on_disk is None:
                raise ValueError("There is no profile yet. Sync with LinkedIn first.")
            updated = confirm(on_disk, self.language, PROFESSION_KEY)
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.error_message = as_sentence(error)
            return

        self._show_profession(updated)
        self._count(updated)

    @rx.event
    def use_same_profession(self) -> None:
        """ "Use the same text": fills the profession with the source one. Save writes it,
        like anything typed."""
        if self.language == self.source_language:
            return
        profile = load_profile(DATA_DIR)
        if profile is None:
            return
        self.profession = _without_placeholder(profile.personal.profession)
        self.saved = False

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
            self.photo_error = as_sentence(error)
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
            self.photo_error = as_sentence(error)
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
            self.skills_error = as_sentence(error)
            return

        self.skills = skill_rows(updated, self.language)
        self._count(updated)

    @rx.event
    async def add_skill(self, data: dict[str, Any]) -> None:
        name = str(data.get("name", ""))
        await self._change_skills(lambda profile: skill_operations.add_skill(profile, name))

    async def _rename(self, skill_id: str, name: str) -> None:
        """It arrives twice per edit, on Enter and when leaving the field: if the name did
        not change, it does nothing.

        In the source language it renames the skill, with its duplicate check. In the other
        one it writes that language's name only; the field showed the source name while
        that one was missing, so leaving it as it was writes nothing.
        """
        row = next((skill["name"] for skill in self.skills if skill["name"]["id"] == skill_id), None)
        if row is None or name.strip() == row["text"]:
            return
        if self.language == self.source_language:
            await self._change_skills(lambda profile: skill_operations.rename_skill(profile, skill_id, name))
            return
        language, key = self.language, row["key"]
        await self._change_skills(lambda profile: save_translation(profile, language, key, name))

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

    def _skill_field(self, key: str, fields: tuple[str, ...] = tuple(SKILL_FIELDS)) -> dict[str, str] | None:
        """The skill text on screen under this key, or None. The key comes from the browser,
        so it is looked up among the rows and never used to build anything."""
        return next((skill[field] for skill in self.skills for field in fields if skill[field]["key"] == key), None)

    async def _save_skill_field(self, key: str, text: str) -> None:
        """Category or level in the other language. In the source one they have no editor,
        like everything LinkedIn writes; their row is not editable there."""
        row = self._skill_field(key, ("category", "level"))
        if row is None or row["editable"] != "yes" or text.strip() == row["own"]:
            return
        language = self.language
        await self._change_skills(lambda profile: save_translation(profile, language, key, text))

    @rx.event
    async def save_skill_field(self, key: str, text: str) -> None:
        """When leaving the field."""
        await self._save_skill_field(key, text)

    @rx.event
    async def skill_field_from_form(self, data: dict[str, Any]) -> None:
        """When pressing Enter."""
        await self._save_skill_field(str(data.get("key", "")), str(data.get("text", "")))

    @rx.event
    async def confirm_skill_field(self, key: str) -> None:
        """ "Still good" on a skill text pending review, in either language."""
        row = self._skill_field(key)
        if row is None or row["state"] != TextState.REVIEW:
            return
        language = self.language
        await self._change_skills(lambda profile: confirm(profile, language, key))

    @rx.event
    async def same_skill_field(self, key: str) -> None:
        """ "Use the same text": the source text becomes this language's, saved right away."""
        row = self._skill_field(key)
        if row is None or row["copyable"] != "yes":
            return
        language = self.language
        await self._change_skills(
            lambda profile: save_translation(profile, language, key, source_text_of(profile, key))
        )

    @rx.event
    def back_to_home(self) -> rx.event.EventSpec:
        return rx.redirect("/")

    @rx.event
    def go_to_sync(self) -> rx.event.EventSpec:
        return rx.redirect("/sync")


def skill_rows(profile: MasterProfile, language: str) -> list[dict[str, dict[str, str]]]:
    """Each skill with its name, category and level as `text_version` shows them in `language`.

    Each text also carries the skill's `id`, its `label` and whether it is `editable`. The
    name is, in both languages. Category and level are only in the other language, and
    only when the source has text: in the source language nothing writes them by hand.
    """
    in_source = language == profile.source_language
    return [
        {
            field: {
                **text_version(profile, language, text_key(skill.id, field), silent=("skills", field) in SILENT_FIELDS),
                "id": skill.id,
                "label": label,
                "editable": "yes" if field == "name" or (not in_source and getattr(skill, field)) else "",
            }
            for field, label in SKILL_FIELDS.items()
        }
        for skill in profile.skills
    ]
