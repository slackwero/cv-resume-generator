"""The subsections of My profile, opened from the `section` query value.

The value comes from the browser's address bar, so it is checked against an allowlist:
anything that is not exactly a known section opens Contact.
"""

import pytest

from cv_generator.app.states.profile_state import requested_section


@pytest.mark.parametrize("name", ["contact", "photo", "skills", "experience"])
def test_a_known_section_is_opened(name: str) -> None:
    assert requested_section(name) == name


@pytest.mark.parametrize("name", ["", "Skills", "admin", "../experience", "experience "])
def test_anything_else_opens_contact(name: str) -> None:
    assert requested_section(name) == "contact"
