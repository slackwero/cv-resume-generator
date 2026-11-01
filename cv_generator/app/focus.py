"""Where the keyboard goes when a control leaves the page."""

import json

import reflex as rx


def focus_on(element_id: str) -> rx.event.EventSpec | None:
    """Puts the keyboard on a control once the screen has redrawn.

    Closing a form or moving a row takes the focused button out of the page, and the
    browser drops the focus to the top of it: a keyboard user would have to start over.
    Two frames, because the change arrives before React draws it.
    """
    if not element_id:
        return None
    target = json.dumps(element_id)
    return rx.call_script(
        f"requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById({target})?.focus()))"
    )
