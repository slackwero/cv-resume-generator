"""Every registered page has to be evaluable.

Importing `app` is not enough: Reflex evaluates the pages when compiling, not when
importing, so an invalid prop (a list where Radix requires `rx.breakpoints`) goes
unnoticed until the server starts. These tests call each page's function, which is what
the compiler does.
"""

import reflex as rx

from cv_generator.app.pages.home import home_page
from cv_generator.app.pages.profile import profile_page
from cv_generator.app.pages.sync import sync_page
from cv_generator.app.pages.wizard import wizard_page

PAGES = {
    "/": home_page,
    "/new": wizard_page,
    "/profile": profile_page,
    "/sync": sync_page,
}


def test_every_page_is_evaluated() -> None:
    for path, page in PAGES.items():
        assert isinstance(page(), rx.Component), path


def test_every_page_renders() -> None:
    """Evaluating is not rendering: a badly typed prop may only fail when the JSX is emitted."""
    for path, page in PAGES.items():
        assert page().render(), path


def test_the_app_registers_the_four_routes() -> None:
    from cv_generator.app.app import app

    registered = set(app._unevaluated_pages)  # noqa: SLF001
    missing = {path.lstrip("/") or "index" for path in PAGES} - registered

    assert not missing, f"unregistered routes: {missing}"
