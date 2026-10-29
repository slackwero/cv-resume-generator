"""Wizard state: from your master profile to a CV tailored to one application."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

import reflex as rx

from cv_generator.app.config import (
    DATA_DIR,
    DEFAULT_LANGUAGE,
    DEFAULT_TEMPLATE,
    OUTPUT_DIR,
)
from cv_generator.models.cv import CVContent, JobPosting, SelectedExperience, Selection
from cv_generator.models.profile import Achievement, Experience, MasterProfile
from cv_generator.models.sections import Section, SectionKind
from cv_generator.models.style import FontSize, PaletteColor, Style, StyleFont
from cv_generator.rendering.i18n import (
    available_languages,
    default_sections,
    language_name,
    load_language,
)
from cv_generator.rendering.renderer import (
    available_templates,
    load_meta,
    render_html,
    render_pdf_and_pages,
)
from cv_generator.rendering.styles import (
    COLOR_NAMES,
    FONT_NAMES,
    PALETTE,
    SIZE_NAMES,
    line_height_label,
    line_height_step,
)
from cv_generator.services.generation import generate_cv, load_cv
from cv_generator.services.photo import set_photo
from cv_generator.services.profile import load_profile, load_sync_status, pending_fields
from cv_generator.services.system import open_with_viewer
from cv_generator.tailoring.keywords import analyze_coverage, mentioned_terms
from cv_generator.tailoring.resolver import resolve_content

FIRST_STEP = 1
EXPERIENCE_STEP = 4
LAST_STEP = 6

# Where the posting analysis is in view and therefore has to stay up to date.
STEPS_WITH_ANALYSIS = (EXPERIENCE_STEP, LAST_STEP)

# The thumbnail shows the design, not the whole CV: the content is trimmed so the render
# is cheap and the page reads at 150px wide.
THUMBNAIL_EXPERIENCES = 3
THUMBNAIL_ACHIEVEMENTS = 3
THUMBNAIL_ITEMS = 6

# How much of a presentation text is shown before folding it.
PROFILE_SUMMARY_LENGTH = 220

# The preview is always written to the same file and refreshed with a counter in the
# URL: a new name per render would leave an orphan PDF every time.
PREVIEW_FILE = "preview.pdf"

# A4 at 96 dpi, which is the unit the browser draws the PDF viewer in.
PAGE_HEIGHT_PX = 1123

# Viewer cap: above this it stops being a preview inside the step and becomes the
# whole screen.
MAX_VIEWER_HEIGHT = "78vh"

STEP_TITLES = [
    "Template",
    "The application",
    "Presentation",
    "Experience",
    "The rest of your profile",
    "Sections and order",
]

# The style options do not change between sessions: they are built once from the render
# tables, so the interface offers exactly what the render knows how to draw.
COLORS = [{"key": str(color), "name": COLOR_NAMES[color], "sample": PALETTE[color].accent} for color in PaletteColor]
FONTS = [{"key": str(font), "name": FONT_NAMES[font]} for font in StyleFont]
SIZES = [{"key": str(size), "name": SIZE_NAMES[size]} for size in FontSize]


def _achievement_key(experience_id: str, achievement_id: str) -> str:
    return f"{experience_id}|{achievement_id}"


def _achievement_list(profile: MasterProfile) -> list[dict[str, str]]:
    """Every achievement of the profile, in its order, with the job it hangs from."""
    return [
        {
            "key": _achievement_key(experience.id, achievement.id),
            "experience_id": experience.id,
            "text": achievement.text,
        }
        for experience in profile.experiences
        for achievement in experience.achievements
    ]


def vars_from_style(style: Style) -> dict[str, str | float]:
    """A recipe's `Style` in the wizard's style vars.

    `None` ("the template's") becomes "" or 0.0, which is how the controls read it. It is
    the inverse of `style_from_vars`: cloning puts the recipe's style in the controls,
    and the new CV is built from them.
    """
    return {
        "style_color": str(style.color) if style.color else "",
        "style_font": str(style.font) if style.font else "",
        "style_size": str(style.size) if style.size else "",
        "style_line_height": style.line_height or 0.0,
    }


def style_from_vars(*, style_color: str, style_font: str, style_size: str, style_line_height: float) -> Style:
    """The wizard's style vars as the recipe's `Style`; empty stays `None`."""
    return Style(
        color=PaletteColor(style_color) if style_color else None,
        font=StyleFont(style_font) if style_font else None,
        size=FontSize(style_size) if style_size else None,
        line_height=style_line_height or None,
    )


class WizardState(rx.State):
    """Gathers the user's decisions and turns them into a Selection."""

    _profile: MasterProfile | None = None

    step: int = FIRST_STEP
    # How far the user got: they can go back to any step already visited, but not jump
    # forward without going through each one's validations.
    max_step: int = FIRST_STEP
    message: str = ""
    generated_cv: str = ""

    # An action's error is shown next to the button that triggers it, not at the top of the
    # page: on the last step the button is out of the viewport, and a callout in the header
    # is an error the user never sees.
    action_error: str = ""
    # Required fields the importer could not bring. Generating with one pending writes the
    # word PENDING in the PDF and records it forever in the history.
    pending: list[str] = []
    # Which CV this recipe was cloned from. The only hint used to be the " (copy)" stuck to the name.
    cloned_from: str = ""
    generated_cv_id: str = ""
    generating: bool = False
    previewing: bool = False

    templates: list[dict[str, str]] = []
    template: str = DEFAULT_TEMPLATE
    # The templates that draw the photo, according to their meta.json. With the others the
    # switch is disabled: checking it would change nothing in the PDF.
    templates_with_photo: list[str] = []

    # Empty / 0.0 means "the template's": the style only keeps what the user changed, just
    # like `Style`, where `None` keeps the template's value.
    style_color: str = ""
    style_font: str = ""
    style_size: str = ""
    style_line_height: float = 0.0
    colors: list[dict[str, str]] = COLORS
    fonts: list[dict[str, str]] = FONTS
    sizes: list[dict[str, str]] = SIZES
    # Each template's line height, to show the value in effect even if the user touched
    # nothing and to know where each step starts from.
    template_line_heights: dict[str, float] = {}
    # The full CV of the chosen template, with the style applied.
    large_view: str = ""

    has_photo: bool = False
    include_photo: bool = True
    # What answers "I uploaded it" when the profile has no photo yet: without this the click
    # changes nothing on screen and the button seems not to work.
    photo_notice: str = ""

    cv_name: str = ""
    target_role: str = ""
    language: str = DEFAULT_LANGUAGE
    languages: list[dict[str, str]] = []
    header_profession: str = ""

    profile_texts_list: list[dict[str, str]] = []
    profile_text_id: str = ""
    expanded_profile_texts: dict[str, bool] = {}

    experiences: list[dict[str, str]] = []
    achievements: list[dict[str, str]] = []
    marked_achievements: dict[str, bool] = {}

    skills: list[dict[str, str]] = []
    marked_items: dict[str, bool] = {}
    skill_order: list[str] = []

    other_items: list[dict[str, str]] = []

    # Flattened lists for the interface: Reflex cannot filter inside a foreach, so the
    # headings and their items travel in a single list.
    experience_rows: list[dict[str, str]] = []
    other_rows: list[dict[str, str]] = []

    section_order: list[str] = []
    section_titles: dict[str, str] = {}
    visible_sections: dict[str, bool] = {}

    # PDF path inside the uploads folder, with its version to skip the cache. The component
    # builds the full URL: `rx.get_upload_url` is a browser expression and on the server it
    # only produces its text representation.
    pdf_preview: str = ""
    pages: int = 0
    _previous_version: int = 0

    posting_company: str = ""
    posting_url: str = ""
    posting_text: str = ""
    covered_terms: list[dict[str, str]] = []
    missing_terms: list[dict[str, str]] = []
    coverage_percent: int = 0
    has_analysis: bool = False

    # ------------------------------------------------------------------ carga

    @rx.event
    def start(self) -> None:
        """Loads the profile and prepares the wizard, cloning a previous CV if asked."""
        # The session is saved to disk and survives F5 and a server restart. If a render was cut
        # halfway, the flag stayed True and blocked the buttons forever: reloading the page has
        # to be enough to unblock them.
        self.previewing = False
        self.generating = False
        self.message = ""
        self.action_error = ""
        self.generated_cv = ""
        self.generated_cv_id = ""
        self.cloned_from = ""
        self.step = FIRST_STEP
        self.max_step = FIRST_STEP
        self._set_style(Style())
        self.large_view = ""

        profile = load_profile(DATA_DIR)
        if profile is None:
            self.message = (
                "There is no profile to start from yet. Import your LinkedIn export "
                "from the sync screen and come back here."
            )
            return

        self._profile = profile
        self.pending = pending_fields(profile)
        self.languages = [{"code": code, "name": language_name(code)} for code in available_languages()]

        # The language starts as that of the imported content, not LinkedIn's.
        status = load_sync_status(DATA_DIR)
        self.language = status.detected_language if status else DEFAULT_LANGUAGE
        self.header_profession = profile.personal.profession
        self.has_photo = profile.personal.photo is not None
        self.include_photo = True
        self.photo_notice = ""

        self._prepare_lists(profile)
        self._flatten_for_ui(profile)
        self._mark_all(profile)
        self._prepare_sections()
        self._prepare_templates(profile)

        clone_from = self.router.page.params.get("from", "")
        if clone_from:
            self._apply_previous_recipe(clone_from)
            # The thumbnails were drawn with the starting checks; the recipe may have changed them.
            self._refresh_thumbnails()
        self._refresh_large_view()

    def _prepare_templates(self, profile: MasterProfile) -> None:
        """Lists the templates with a real thumbnail of each one.

        Choosing the design by reading prose and seeing it five steps later turns the
        product's most visual decision into an act of faith. The thumbnail is the same
        `render_html` that produces the PDF, with trimmed content.
        """
        sample = self._sample_content(profile)
        self.templates = []
        self.templates_with_photo = []
        self.template_line_heights = {}

        for slug in available_templates():
            meta = load_meta(slug)
            self.template_line_heights[slug] = meta.line_height
            if meta.supports_photo:
                self.templates_with_photo.append(slug)
            self.templates.append(
                {
                    "slug": slug,
                    "name": meta.name,
                    "description": meta.description,
                    # Text and not bool: the whole list is dict[str, str] for Reflex.
                    "ats": "yes" if meta.ats else "",
                    "thumbnail": self._thumbnail(sample, slug),
                }
            )

        installed = [template["slug"] for template in self.templates]
        self.template = DEFAULT_TEMPLATE if DEFAULT_TEMPLATE in installed else next(iter(installed), "")

    def _as_rendered(self, content: CVContent, slug: str) -> CVContent:
        """The content without the photo if the template does not draw it, the rule in `generate_cv`.

        The template hides it anyway, but the HTML travels to the browser on every click:
        with the profile photo, most of what was sent was an image nobody saw.
        """
        if slug in self.templates_with_photo or content.personal.photo is None:
            return content
        return content.model_copy(update={"personal": content.personal.model_copy(update={"photo": None})})

    def _thumbnail(self, sample: CVContent | None, slug: str) -> str:
        if sample is None:
            return ""
        try:
            return render_html(self._as_rendered(sample, slug), slug, language=self.language, style=self._build_style())
        except (KeyError, ValueError, OSError):
            # A broken template cannot take down the whole step: it is left without a thumbnail and
            # the card falls back to its description, as before.
            return ""

    def _refresh_thumbnails(self) -> None:
        """Redraws the thumbnails without touching the chosen template.

        It is only HTML, not paginated: redoing them is cheap, and a thumbnail with a photo
        after asking for the CV without one would be a thumbnail that lies.
        """
        if self._profile is None:
            return
        sample = self._sample_content(self._profile)
        self.templates = [
            {**template, "thumbnail": self._thumbnail(sample, template["slug"])} for template in self.templates
        ]

    def _refresh_large_view(self) -> None:
        """Draws the full CV of the chosen template, with the style applied.

        The trimmed thumbnail is good for comparing designs, but not for deciding a font
        size or a line height: that can only be judged on the whole document.
        """
        self.large_view = ""
        if self._profile is None or not self.template:
            return
        try:
            content = self._as_rendered(resolve_content(self._profile, self._build_selection()), self.template)
            self.large_view = render_html(content, self.template, language=self.language, style=self._build_style())
        except (KeyError, ValueError, OSError):
            # Like the thumbnail: a broken template does not take down the step, it is only left
            # without a view.
            self.large_view = ""

    def _sample_content(self, profile: MasterProfile) -> CVContent | None:
        """A trimmed CV, only for the thumbnails."""
        try:
            full = resolve_content(profile, self._build_selection())
        except (KeyError, ValueError):
            return None

        return full.model_copy(
            update={
                "experiences": [
                    experience.model_copy(update={"achievements": experience.achievements[:THUMBNAIL_ACHIEVEMENTS]})
                    for experience in full.experiences[:THUMBNAIL_EXPERIENCES]
                ],
                "skills": full.skills[:THUMBNAIL_ITEMS],
                "education": full.education[:2],
                "courses": full.courses[:2],
                "languages": full.languages[:2],
                "hobbies": full.hobbies[:2],
                "references": full.references[:1],
            }
        )

    def _prepare_lists(self, profile: MasterProfile) -> None:
        self.experiences = [
            {
                "id": experience.id,
                "role": experience.role,
                "company": experience.company,
                "dates": experience.period(),
            }
            for experience in profile.experiences
        ]
        self.achievements = _achievement_list(profile)
        self.skills = [{"id": h.id, "name": h.name} for h in profile.skills]
        # The full text always travels: choosing the paragraph that heads your CV from a
        # 220-character excerpt is choosing blind. The excerpt is only the folded view, and the
        # user can expand it.
        self.profile_texts_list = [
            {
                "id": p.id,
                "text": p.text,
                "summary": p.text[:PROFILE_SUMMARY_LENGTH].rstrip() + "…"
                if len(p.text) > PROFILE_SUMMARY_LENGTH
                else p.text,
                "largo": "yes" if len(p.text) > PROFILE_SUMMARY_LENGTH else "",
            }
            for p in profile.profile_texts
        ]
        self.profile_text_id = profile.profile_texts[0].id if profile.profile_texts else ""

        self.other_items = [
            *[{"id": e.id, "group": "education", "text": f"{e.title} · {e.institution}"} for e in profile.education],
            *[{"id": c.id, "group": "courses", "text": c.name} for c in profile.courses],
            *[{"id": i.id, "group": "languages", "text": f"{i.language} · {i.level or ''}"} for i in profile.languages],
            *[{"id": h.id, "group": "hobbies", "text": h.text} for h in profile.hobbies],
            *[{"id": r.id, "group": "references", "text": r.name} for r in profile.references],
        ]

    def _flatten_for_ui(self, profile: MasterProfile) -> None:
        """Interleaves each experience with its achievements, and each group with its items."""
        rows: list[dict[str, str]] = []
        for experience in profile.experiences:
            rows.append(
                {
                    "row": "experience",
                    "key": experience.id,
                    "experience_id": experience.id,
                    "role": experience.role,
                    "company": experience.company,
                    "dates": experience.period(),
                    "text": "",
                    # Filled by `guided_experience_rows` against the current analysis.
                    "contributes": "",
                    # Experience rows have no origin, but the key travels anyway: `rx.foreach` walks a
                    # single dict type and does not like some rows carrying keys others do not.
                    "origin": "",
                    "yours": "",
                }
            )
            # Each achievement knows which experience it hangs from: when the experience is
            # unchecked, `_build_selection` drops its achievements, and the interface has to reflect
            # that instead of still showing them checked.
            rows += [
                {
                    "row": "achievement",
                    "key": _achievement_key(experience.id, achievement.id),
                    "experience_id": experience.id,
                    "role": "",
                    "company": "",
                    "dates": "",
                    "text": achievement.text,
                    "contributes": "",
                    # What LinkedIn said, and ONLY when it differs from what it says now.
                    #
                    # It is the default value this achievement is tied to. While they match there is
                    # nothing to show: the normal is intact, and repeating the same text twice only takes
                    # space. When they differ, you broke it, and that is exactly the state the product
                    # promises to respect — until now it was only visible when syncing.
                    "origin": (
                        achievement.imported_value
                        if achievement.imported_value and achievement.imported_value != achievement.text
                        else ""
                    ),
                    # You wrote it, or it is a copy: LinkedIn never brought it. Text and not bool,
                    # like the rest of the row.
                    "yours": "yes" if achievement.imported_value is None else "",
                }
                for achievement in experience.achievements
            ]
        self.experience_rows = rows

        labels = {
            "education": "Education",
            "courses": "Courses",
            "languages": "Languages",
            "hobbies": "Hobbies & interests",
            "references": "References",
        }
        others: list[dict[str, str]] = []
        for group, label in labels.items():
            of_group = [item for item in self.other_items if item["group"] == group]
            if not of_group:
                continue
            others.append({"row": "group", "key": group, "text": label})
            others += [{"row": "item", "key": item["id"], "text": item["text"]} for item in of_group]
        self.other_rows = others

    def _mark_all(self, profile: MasterProfile) -> None:
        """Starts with everything included: discarding is faster than finding and checking.

        Except the copies: a copy next to its original would put the same achievement twice
        in the CV, so it starts unchecked.
        """
        self.marked_achievements = initial_achievement_marks(profile)
        self.marked_items = {
            **{experience.id: True for experience in profile.experiences},
            **{skill.id: True for skill in profile.skills},
            **{item["id"]: True for item in self.other_items},
        }
        self.skill_order = [skill.id for skill in profile.skills]

    def _prepare_sections(self) -> None:
        sections = default_sections(self.language)
        self.section_order = [str(section.kind) for section in sections]
        self.section_titles = {str(section.kind): section.title for section in sections}
        self.visible_sections = {str(section.kind): True for section in sections}

    def _apply_previous_recipe(self, cv_id: str) -> None:
        """Reproduces a previous CV's selection over the current profile."""
        try:
            previous = load_cv(DATA_DIR, cv_id)
        except (FileNotFoundError, ValueError):
            self.message = (
                "The CV you wanted to clone was not found, so this one starts from scratch "
                "with your whole profile checked."
            )
            return

        recipe = previous.selection
        self.cloned_from = previous.cv_name
        self.cv_name = f"{previous.cv_name} (copy)"
        self.target_role = previous.target_role
        self.language = previous.language
        self.template = previous.template
        self.profile_text_id = recipe.profile_text_id or self.profile_text_id
        self.header_profession = recipe.header_profession or self.header_profession
        self.include_photo = recipe.include_photo
        self._set_style(recipe.style)

        chosen_items = {
            _achievement_key(experience.id, achievement_id)
            for experience in recipe.experiences
            for achievement_id in experience.achievements
        }
        self.marked_achievements = {key: key in chosen_items for key in self.marked_achievements}

        experience_ids = {experience.id for experience in recipe.experiences}
        selected = (
            experience_ids
            | set(recipe.skills)
            | set(recipe.education + recipe.courses + recipe.languages + recipe.hobbies + recipe.references)
        )
        self.marked_items = {key: key in selected for key in self.marked_items}
        self.skill_order = [
            *recipe.skills,
            *[i for i in self.skill_order if i not in recipe.skills],
        ]

        if recipe.sections:
            self.section_order = [str(s.kind) for s in recipe.sections]
            self.section_titles = {str(s.kind): s.title for s in recipe.sections}
            self.visible_sections = {str(s.kind): s.visible for s in recipe.sections}

    # ------------------------------------------------------------- navigation

    @rx.var
    def step_map(self) -> list[dict[str, str]]:
        """The six steps with their status, so the user sees where they are and what is left."""
        return [
            {
                "number": str(number),
                "title": title,
                "status": "current" if number == self.step else ("done" if number <= self.max_step else "pending"),
                "reachable": "yes" if number <= self.max_step else "",
            }
            for number, title in enumerate(STEP_TITLES, start=FIRST_STEP)
        ]

    @rx.var
    def has_pending(self) -> bool:
        return len(self.pending) > 0

    @rx.var
    def pending_summary(self) -> str:
        return ", ".join(self.pending)

    @rx.var
    def progress(self) -> int:
        """0% on the first step, 100% only once the CV is generated.

        The denominator is the spans between steps, not the steps: with six steps there
        are five spans, and dividing by six left the last step at 83%.
        """
        if self.generated_cv:
            return 100
        segments = LAST_STEP - FIRST_STEP
        return (self.step - FIRST_STEP) * 100 // segments if segments else 100

    @rx.var
    def guided_experience_rows(self) -> list[dict[str, str]]:
        """The step 4 rows, with what each achievement would close from the posting.

        The analysis said "Terraform" was missing but not which of the fifty achievements
        mentions it, so the user had to look for it by eye. Checking the achievement that
        contributes a term is the decision the analysis exists to inform.
        """
        missing = [term["term"] for term in self.missing_terms]
        if not missing:
            return self.experience_rows

        return [
            {**row, "contributes": ", ".join(mentioned_terms(row["text"], missing))}
            if row["row"] == "achievement"
            else row
            for row in self.experience_rows
        ]

    @rx.var
    def sorted_skills(self) -> list[dict[str, str]]:
        """The skills in the order they will be printed.

        The screen showed `skills`, which keeps the profile order, while the chevrons
        moved `skill_order`. The user pressed up and nothing moved: the list they saw was
        not the one being reordered.
        """
        index = {skill["id"]: skill for skill in self.skills}
        return [index[skill_id] for skill_id in self.skill_order if skill_id in index]

    @rx.var
    def preview_height(self) -> str:
        """The viewer grows with the document, but without pushing the rest of the screen out.

        Sizing it to the whole document avoided nesting one scroll inside another, but
        with three pages it gave more than 3,400px in the same column and pushed
        everything else in the step out of view. The cap brings it back to the window
        height; a PDF viewer that scrolls inside is how a PDF is always read.
        """
        pages = max(self.pages, 1)
        return f"min({pages * PAGE_HEIGHT_PX + 48}px, {MAX_VIEWER_HEIGHT})"

    @rx.var
    def pages_summary(self) -> str:
        if self.pages == 1:
            return "1 page"
        return f"{self.pages} pages"

    @rx.var
    def is_last_step(self) -> bool:
        return self.step >= LAST_STEP

    @rx.var
    def can_advance(self) -> bool:
        if self.step == FIRST_STEP:
            return self.template != ""
        if self.step == 2:  # noqa: PLR2004
            return self.cv_name.strip() != "" and self.target_role.strip() != ""
        return True

    @rx.var
    def missing_to_advance(self) -> str:
        """What prevents moving to the next rail, called by its name.

        `can_advance` decides whether the button is disabled, but does not say why, and a
        dead button with no reason forces you to guess which of the fields on the screen
        is in the way. Returns an empty string when nothing is missing.
        """
        if self.step == FIRST_STEP:
            return "" if self.template != "" else "Choose a template to continue"
        if self.step == 2:  # noqa: PLR2004
            missing = []
            if self.cv_name.strip() == "":
                missing.append("the CV name")
            if self.target_role.strip() == "":
                missing.append("the role you are applying for")
            return f"Missing {' and '.join(missing)}" if missing else ""
        return ""

    @rx.event
    def advance(self) -> None:
        if self.step < LAST_STEP and self.can_advance:
            self.step += 1
            self.max_step = max(self.max_step, self.step)
            self.message = ""
            self.action_error = ""
            if self.step in STEPS_WITH_ANALYSIS:
                self.analyze_posting()

    @rx.event
    def go_to_step(self, target: int) -> None:
        """Jumps to a step already visited.

        `STEP_TITLES` existed in full in the state and only the current step's title was
        shown: the user never saw the map nor could go back in one jump.
        """
        if FIRST_STEP <= target <= self.max_step:
            self.step = target
            self.message = ""
            self.action_error = ""
            if target == FIRST_STEP:
                self._refresh_template_views()
            if target in STEPS_WITH_ANALYSIS:
                self.analyze_posting()

    @rx.event
    def go_back(self) -> None:
        if self.step > FIRST_STEP:
            self.step -= 1
            self.message = ""
            self.action_error = ""
            if self.step == FIRST_STEP:
                self._refresh_template_views()
            if self.step in STEPS_WITH_ANALYSIS:
                self.analyze_posting()

    def _refresh_template_views(self) -> None:
        """Redraws thumbnails and large view with what was decided in the following steps.

        They were drawn when the wizard opened; when going back to step 1 from the rest,
        the CV has to be shown as it ended up (sections, titles, photo), not as it was then.
        """
        self._refresh_thumbnails()
        self._refresh_large_view()

    def _posting_or_none(self) -> JobPosting | None:
        """The posting is only saved if the user wrote something about it."""
        if not any([self.posting_text.strip(), self.posting_company.strip(), self.posting_url.strip()]):
            return None
        return JobPosting(
            company=self.posting_company.strip() or None,
            url=self.posting_url.strip() or None,
            text=self.posting_text.strip(),
        )

    @rx.event
    def back_to_home(self) -> rx.event.EventSpec:
        return rx.redirect("/")

    @rx.event
    def go_to_profile(self) -> rx.event.EventSpec:
        return rx.redirect("/profile")

    @rx.event
    def open_the_pdf(self) -> None:
        """Opens the freshly generated PDF with the system viewer.

        Ending the flow by looking at an absolute path forces you out of the app to see
        what you just produced.
        """
        try:
            open_with_viewer(Path(self.generated_cv), OUTPUT_DIR)
        except FileNotFoundError:
            self.action_error = "The PDF is no longer in output/. Generate it again."
        except ValueError:
            self.action_error = "The PDF path points outside output/ and is not opened, for safety."

    @rx.event
    def clone_generated(self) -> rx.event.EventSpec:
        """Starts the next application with this same recipe."""
        return rx.redirect(f"/new?from={self.generated_cv_id}")

    # --------------------------------------------------------------- selection

    @rx.event
    def update_cv_name(self, value: str) -> None:
        self.cv_name = value

    @rx.event
    def update_target_role(self, value: str) -> None:
        self.target_role = value

    @rx.event
    def update_header_profession(self, value: str) -> None:
        self.header_profession = value
        self._invalidate_preview()

    @rx.event
    def update_posting_company(self, value: str) -> None:
        self.posting_company = value

    @rx.event
    def update_posting_url(self, value: str) -> None:
        self.posting_url = value

    @rx.event
    def update_posting_text(self, value: str) -> None:
        self.posting_text = value

    def _invalidate_preview(self) -> None:
        """Discards the previous render as soon as it stops describing the current selection.

        Without this the user changes a title, looks at the iframe and sees the earlier
        render with no sign that they are looking at something stale.
        """
        self.pdf_preview = ""
        self.pages = 0
        # The generated CV also stops describing the current configuration: keeping the green
        # callout would claim there is a PDF with these changes inside.
        self.generated_cv = ""
        self.generated_cv_id = ""
        # Coverage measures the selection; if the selection changed, the previous number no
        # longer describes it and the "% covered" badge keeps lying.
        if self.step in STEPS_WITH_ANALYSIS:
            self.analyze_posting()

    @rx.event
    def choose_template(self, slug: str) -> None:
        self.template = slug
        self._refresh_large_view()
        self._invalidate_preview()

    @rx.var
    def effective_line_height(self) -> float:
        """The line height that will be seen: the chosen one, or the template's."""
        if self.style_line_height:
            return self.style_line_height
        return self.template_line_heights.get(self.template, 0.0)

    @rx.var
    def line_height_text(self) -> str:
        return line_height_label(self.effective_line_height)

    @rx.var
    def can_decrease_line_height(self) -> bool:
        current = self.effective_line_height
        return current > 0 and line_height_step(current, -1) != current

    @rx.var
    def can_increase_line_height(self) -> bool:
        current = self.effective_line_height
        return current > 0 and line_height_step(current, 1) != current

    @rx.var
    def custom_style(self) -> bool:
        return not self._build_style().empty

    def _build_style(self) -> Style:
        """Translates the style vars into the recipe's `Style`; empty stays `None`.

        It reads each var by name, with no `getattr` loop: `custom_style` depends on this
        method, and Reflex works out those dependencies from the `self.x` it sees.
        """
        return style_from_vars(
            style_color=self.style_color,
            style_font=self.style_font,
            style_size=self.style_size,
            style_line_height=self.style_line_height,
        )

    def _set_style(self, style: Style) -> None:
        """Puts a `Style` in the controls; `Style()` sets them back to the template's."""
        for name, value in vars_from_style(style).items():
            setattr(self, name, value)

    def _change_style(self) -> None:
        """What follows any style change: everything that shows it is redone."""
        self._refresh_thumbnails()
        self._refresh_large_view()
        self._invalidate_preview()

    @rx.event
    def choose_color(self, key: str) -> None:
        if key not in {color.value for color in PaletteColor}:
            return
        self.style_color = key
        self._change_style()

    @rx.event
    def choose_font(self, key: str) -> None:
        """An empty key gives back the template's font."""
        if key and key not in {font.value for font in StyleFont}:
            return
        self.style_font = key
        self._change_style()

    @rx.event
    def choose_size(self, key: str) -> None:
        if key not in {size.value for size in FontSize}:
            return
        self.style_size = key
        self._change_style()

    @rx.event
    def change_line_height(self, direction: int) -> None:
        """Moves the line height one tenth from the value in effect, without leaving the range.

        If the template declares no line height there is nowhere to start from and it is ignored.
        """
        current = self.effective_line_height
        if current <= 0:
            return
        new = line_height_step(current, direction)
        # Going back to the template's value stops being a customization.
        defaults = self.template_line_heights.get(self.template, 0.0)
        self.style_line_height = 0.0 if new == defaults else new
        self._change_style()

    @rx.event
    def reset_style(self) -> None:
        """Sets color, font, size and line height back to the template's."""
        self._set_style(Style())
        self._change_style()

    @rx.var
    def template_shows_photo(self) -> bool:
        return self.template in self.templates_with_photo

    @rx.var
    def template_name(self) -> str:
        return next((p["name"] for p in self.templates if p["slug"] == self.template), self.template)

    @rx.event
    def toggle_photo(self, value: bool) -> None:
        self.include_photo = value
        self._refresh_thumbnails()
        self._refresh_large_view()
        self._invalidate_preview()

    @rx.event
    def fetch_profile_photo(self) -> None:
        """Brings in the photo you uploaded in My profile, opened in another tab.

        My profile opens separately because going back to /new restarts the wizard: step,
        template, style and selection. Only the photo is refreshed from the profile, just
        like `update_skills` only refreshes the skills; nothing else is touched.
        """
        self.photo_notice = ""
        profile = load_profile(DATA_DIR)
        if profile is None or self._profile is None:
            return

        photo = profile.personal.photo
        self.has_photo = photo is not None
        if photo is None:
            self.photo_notice = (
                "Your profile has no photo yet. Upload it in the My profile tab and press “I uploaded it” again."
            )
        # A click that does not bring a different photo leaves no render stale: there is
        # nothing to redraw or invalidate.
        if photo == self._profile.personal.photo:
            return

        self._profile = set_photo(self._profile, photo)
        self._refresh_template_views()
        self._invalidate_preview()

    @rx.event
    def toggle_full_text(self, profile_text_id: str) -> None:
        """Expands or folds a presentation text without changing which one is chosen."""
        self.expanded_profile_texts[profile_text_id] = not self.expanded_profile_texts.get(profile_text_id, False)

    @rx.event
    def choose_profile_text(self, profile_text_id: str) -> None:
        self.profile_text_id = profile_text_id
        self._invalidate_preview()

    @rx.event
    def change_language(self, language: str) -> None:
        """Changing the language translates again the titles you have not customized."""
        previous_items = load_language(self.language).sections
        new_entries = load_language(language).sections
        self.section_titles = {
            kind: new_entries[SectionKind(kind)] if title == previous_items[SectionKind(kind)] else title
            for kind, title in self.section_titles.items()
        }
        self.language = language
        self._refresh_large_view()
        self._invalidate_preview()

    @rx.event
    def toggle_achievement(self, key: str, value: bool) -> None:
        self.marked_achievements[key] = value
        self._invalidate_preview()

    @rx.event
    def toggle(self, key: str, value: bool) -> None:
        self.marked_items[key] = value
        self._invalidate_preview()

    @rx.event
    def toggle_section(self, kind: str, value: bool) -> None:
        self.visible_sections[kind] = value
        self._invalidate_preview()

    @rx.event
    def change_title(self, kind: str, title: str) -> None:
        self.section_titles[kind] = title
        self._invalidate_preview()

    @rx.event
    def move_section(self, kind: str, scroll_offset: int) -> None:
        self.section_order = _move(self.section_order, kind, scroll_offset)
        self._invalidate_preview()

    @rx.event
    def move_skill(self, skill_id: str, scroll_offset: int) -> None:
        self.skill_order = _move(self.skill_order, skill_id, scroll_offset)
        self._invalidate_preview()

    @rx.event
    def skill_first(self, skill_id: str) -> None:
        """Moves a skill to the top in one go.

        With only one-step chevrons, moving skill number thirty up took twenty-nine
        clicks, which is the same as not being able to do it.
        """
        if skill_id not in self.skill_order:
            return
        rest = [item for item in self.skill_order if item != skill_id]
        self.skill_order = [skill_id, *rest]
        self._invalidate_preview()

    @rx.event
    def update_skills(self) -> None:
        """Brings in the skills you added, renamed or removed in My profile.

        My profile opens in another tab because going back to /new restarts the wizard and
        you would lose the half-built CV. New ones come in checked and at the end, and
        everything else you chose is untouched. Only the skills are refreshed from the
        profile: the achievements have their own button, `update_achievements`.
        """
        profile = load_profile(DATA_DIR)
        if profile is None or self._profile is None:
            return

        self._profile = self._profile.model_copy(update={"skills": profile.skills})
        self.skills = [{"id": h.id, "name": h.name} for h in profile.skills]
        new_items = [h.id for h in profile.skills if h.id not in self.skill_order]
        self.skill_order = _order_with_profile(self.skill_order, [h.id for h in profile.skills])
        self.marked_items = {**self.marked_items, **dict.fromkeys(new_items, True)}
        self._invalidate_preview()

    @rx.event
    def update_achievements(self) -> None:
        """Brings in the achievements you edited, duplicated, added or removed in My profile.

        Like `update_skills`, for the step 4 list. Only the achievements of this CV's jobs
        are refreshed: a new one comes in checked, a new copy comes in checked and unchecks
        its original, a removed one leaves the selection and hands its check to the copies
        of it you kept, and every other check stays as you left it.
        """
        profile = load_profile(DATA_DIR)
        if profile is None or self._profile is None:
            return

        previous = self._profile
        self._profile = with_refreshed_achievements(previous, profile)
        self.marked_achievements = refreshed_achievement_marks(self.marked_achievements, previous, self._profile)
        self.achievements = _achievement_list(self._profile)
        self._flatten_for_ui(self._profile)
        self._invalidate_preview()

    # ------------------------------------------------- bulk actions

    @rx.event
    def mark_all_achievements(self, value: bool) -> None:
        """Checks or unchecks at once, so you do not go through dozens of checkboxes by hand.

        The sync screen already offered "Check all" for a shorter list; here, where a
        normal profile brings fifty achievements, there was none.
        """
        self.marked_achievements = dict.fromkeys(self.marked_achievements, value)
        self._invalidate_preview()

    @rx.event
    def mark_all_experiences(self, value: bool) -> None:
        self.marked_items = {
            key: value if any(e["id"] == key for e in self.experiences) else marked
            for key, marked in self.marked_items.items()
        }
        self._invalidate_preview()

    @rx.var
    def achievements_total(self) -> int:
        return len(self.marked_achievements)

    @rx.var
    def chosen_achievements(self) -> int:
        return sum(1 for marked in self.marked_achievements.values() if marked)

    @rx.var
    def achievement_count(self) -> str:
        """How many achievements you have checked, which used to be counted by eye."""
        return f"{self.chosen_achievements} of {self.achievements_total} achievements"

    # ------------------------------------------------------------- result

    def _build_selection(self) -> Selection:
        """Translates the wizard's decisions into the recipe saved in the CV."""
        experiences = [
            SelectedExperience(
                id=experience["id"],
                achievements=[
                    achievement["key"].split("|")[1]
                    for achievement in self.achievements
                    if achievement["experience_id"] == experience["id"]
                    and self.marked_achievements.get(achievement["key"], False)
                ],
            )
            for experience in self.experiences
            if self.marked_items.get(experience["id"], False)
        ]

        def ids_of(group: str) -> list[str]:
            return [
                item["id"]
                for item in self.other_items
                if item["group"] == group and self.marked_items.get(item["id"], False)
            ]

        return Selection(
            profile_text_id=self.profile_text_id or None,
            header_profession=self.header_profession or None,
            include_photo=self.include_photo,
            style=self._build_style(),
            experiences=experiences,
            skills=[i for i in self.skill_order if self.marked_items.get(i, False)],
            education=ids_of("education"),
            courses=ids_of("courses"),
            languages=ids_of("languages"),
            hobbies=ids_of("hobbies"),
            references=ids_of("references"),
            sections=[
                Section(
                    kind=SectionKind(kind),
                    title=self.section_titles.get(kind, kind),
                    visible=self.visible_sections.get(kind, True),
                    order=position,
                )
                for position, kind in enumerate(self.section_order, start=1)
            ],
        )

    def _current_content(self) -> object | None:
        """Resolves the CV as it is configured right now."""
        if self._profile is None:
            return None
        try:
            return resolve_content(self._profile, self._build_selection())
        except (KeyError, ValueError) as error:
            self.action_error = (
                f"The CV could not be built: {error}. Go back to step 4 and check that "
                "at least one experience is checked."
            )
            return None

    @rx.event
    def analyze_posting(self) -> None:
        """Matches the posting text against the CV about to be generated."""
        self.has_analysis = False
        self.covered_terms = []
        self.missing_terms = []
        self.coverage_percent = 0

        if not self.posting_text.strip():
            return

        content = self._current_content()
        if content is None:
            return

        analysis = analyze_coverage(self.posting_text, content)
        self.covered_terms = [{"term": t.term, "times": str(t.frequency)} for t in analysis.covered_terms]
        self.missing_terms = [{"term": t.term, "times": str(t.frequency)} for t in analysis.missing]
        self.coverage_percent = analysis.covered_percent
        self.has_analysis = True

    @rx.event
    async def preview(self) -> AsyncGenerator[None, None]:
        """Shows the real PDF, not the HTML.

        The HTML flows continuously and does not say where each page breaks, which is the
        only thing worth knowing about a CV. It is really paginated, the PDF is written and
        the iframe points to it. The render runs in a thread and the `yield` sends the
        loading state first: on the event loop the spinner would only arrive at the end.
        """
        if self.previewing:
            return

        content = self._current_content()
        if content is None:
            return

        self.previewing = True
        self.action_error = ""
        yield

        try:
            pdf, pages = await asyncio.to_thread(
                render_pdf_and_pages,
                content,
                self.template,
                language=self.language,
                style=self._build_style(),
            )
        except RuntimeError as error:
            self.action_error = str(error)
            self.previewing = False
            return
        except (KeyError, ValueError) as error:
            self.action_error = (
                f"The template '{self.template}' could not be rendered: {error}. Go back to step 1 and try another one."
            )
            self.previewing = False
            return

        try:
            target = rx.get_upload_dir() / PREVIEW_FILE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pdf)
        except OSError as error:
            self.action_error = f"The preview could not be written to disk: {error}"
            self.previewing = False
            return

        self._previous_version += 1
        self.pdf_preview = f"{PREVIEW_FILE}?v={self._previous_version}"
        self.pages = pages
        self.previewing = False

    @rx.event
    async def generate(self) -> AsyncGenerator[None, None]:
        """Writes the PDF and records the CV in the history.

        The `generating` guard is not cosmetic: the PDF never overwrites an earlier one,
        so a second click would leave two files and two permanent entries in the history.
        """
        if self.generating or self._profile is None:
            return

        if self.pending:
            missing_count = ", ".join(self.pending)
            self.action_error = (
                f"Your profile is still missing {missing_count}. The PDF would come out with 'PENDING' "
                "printed there and stay that way forever in the history."
            )
            return

        self.generating = True
        self.action_error = ""
        yield

        try:
            cv = await asyncio.to_thread(
                generate_cv,
                profile=self._profile,
                selection=self._build_selection(),
                cv_name=self.cv_name.strip(),
                target_role=self.target_role.strip(),
                language=self.language,
                template=self.template,
                data_dir=DATA_DIR,
                output_dir=OUTPUT_DIR,
                created=datetime.now(),  # noqa: DTZ005
                posting=self._posting_or_none(),
            )
        except RuntimeError as error:
            # WeasyPrint already states the exact missing command; repeating it would dilute it.
            self.action_error = str(error)
            self.generating = False
            return
        except OSError as error:
            self.action_error = (
                f"The PDF could not be written to output/: {error}. Check that the folder exists and is writable."
            )
            self.generating = False
            return
        except (KeyError, ValueError) as error:
            self.action_error = (
                f"The CV could not be built: {error}. Check that the selection has at least one experience checked."
            )
            self.generating = False
            return

        self.generated_cv = cv.pdf_file
        self.generated_cv_id = cv.cv_id
        self.generating = False


def _order_with_profile(order: list[str], profile_ids: list[str]) -> list[str]:
    """Keeps the order you chose, drops what is gone and appends what is new."""
    present_items = [item for item in order if item in profile_ids]
    return [*present_items, *[item for item in profile_ids if item not in order]]


def _original_in_its_job(achievement: Achievement, experience: Experience) -> str | None:
    """The id of the achievement it was duplicated from, if that one is still in the same job."""
    if any(other.id == achievement.copy_of for other in experience.achievements):
        return achievement.copy_of
    return None


def initial_achievement_marks(profile: MasterProfile) -> dict[str, bool]:
    """Everything checked, except a copy whose original is still in the same job.

    A copy says nearly what its original says: with both checked, the CV would repeat
    the same achievement twice. If the original is gone, the copy is all that is left.
    """
    return {
        _achievement_key(experience.id, achievement.id): _original_in_its_job(achievement, experience) is None
        for experience in profile.experiences
        for achievement in experience.achievements
    }


def with_refreshed_achievements(current: MasterProfile, on_disk: MasterProfile) -> MasterProfile:
    """This CV's jobs with the achievements they have on disk now.

    A job that is new on disk is not added: the experience list was chosen with the
    profile as it was, and only the achievements are refreshed. A job that is gone from
    disk keeps what it had.
    """
    achievements = {experience.id: experience.achievements for experience in on_disk.experiences}
    return current.model_copy(
        update={
            "experiences": [
                experience.model_copy(update={"achievements": achievements[experience.id]})
                if experience.id in achievements
                else experience
                for experience in current.experiences
            ]
        }
    )


def refreshed_achievement_marks(
    marks: dict[str, bool], previous: MasterProfile, profile: MasterProfile
) -> dict[str, bool]:
    """Your checks over the refreshed achievements: kept, dropped when gone, new ones checked.

    A new copy comes in checked and unchecks its original: you duplicated it to tailor it,
    and the CV would otherwise say the same thing twice. A key that is gone is dropped, or
    the selection would name an achievement that no longer exists.

    A checked one that is gone hands its check to the copies of it left in the job: you
    deleted the original to keep the copy you adapted, and its place in this CV stays.
    Only `previous`, the profile before the refresh, still says which copies pointed to it:
    deleting an achievement makes them point elsewhere.
    """
    remaining = {
        _achievement_key(experience.id, achievement.id)
        for experience in profile.experiences
        for achievement in experience.achievements
    }
    heirs: set[str] = set()
    for experience in previous.experiences:
        for achievement in experience.achievements:
            if achievement.copy_of is None:
                continue
            original = _achievement_key(experience.id, achievement.copy_of)
            if original not in remaining and marks.get(original, False):
                heirs.add(_achievement_key(experience.id, achievement.id))

    refreshed: dict[str, bool] = {}
    copied_originals: list[str] = []
    for experience in profile.experiences:
        for achievement in experience.achievements:
            key = _achievement_key(experience.id, achievement.id)
            refreshed[key] = key in heirs or marks.get(key, True)
            original = _original_in_its_job(achievement, experience)
            if key not in marks and original is not None:
                copied_originals.append(_achievement_key(experience.id, original))
    # Unchecked after the walk and not during it: in My profile a copy can be moved above
    # its original, and the original's own pass would put its old check back.
    for key in copied_originals:
        refreshed[key] = False
    return refreshed


def _move(elements: list[str], element: str, scroll_offset: int) -> list[str]:
    """Returns the list with the element moved one position, without going out of bounds."""
    if element not in elements:
        return elements

    current = elements.index(element)
    target = max(0, min(len(elements) - 1, current + scroll_offset))
    if target == current:
        return elements

    reordered = [item for item in elements if item != element]
    reordered.insert(target, element)
    return reordered
