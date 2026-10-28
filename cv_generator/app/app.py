"""Entry point of the Reflex interface.

The theme is configured in rxconfig.py through RadixThemesPlugin.
"""

import reflex as rx

from cv_generator.app.local_only import LocalOnlyMiddleware
from cv_generator.app.pages import home, profile, sync, wizard

# The whole interface is in English: this declares it, so a screen reader reads the
# labels with the right pronunciation.
app = rx.App(
    html_lang="en",
    # The app has no login, so this wraps the whole backend (routes, the websocket and
    # uploads) and refuses what does not come from the app's own page: another host name
    # (DNS rebinding) and other websites open in the browser. See local_only.py.
    api_transformer=LocalOnlyMiddleware,
    # The jackfield stylesheet: it declares the self-hosted typeface, themes the surfaces
    # the browser draws (selection, caret, scrollbars, focus ring) and defines the
    # geometry of the link rail.
    stylesheets=["/style.css"],
    head_components=[
        # Declaring the icon is also what stops the browser from requesting /favicon.ico and
        # getting a 404 on every load: it was the application's only console error.
        rx.el.link(rel="icon", type="image/svg+xml", href="/favicon.svg"),
        # Light mode was dropped on 2026-09-20, and this line is what makes that decision
        # stick.
        #
        # `default_color_mode="dark"` in rxconfig only governs first-time visitors. The theme
        # provider honors the value saved in `localStorage` over the default, so any browser
        # that had already opened the application kept the old "system": Radix paints itself
        # with the `light` class, covers the body's black glass in white, and only the areas
        # with their own background stay dark. That is exactly what showed up when the first
        # round was captured.
        #
        # It goes in the `<head>` so it runs before React hydrates and reads the value, and it
        # also writes the class on <html> right away: with only `localStorage`, the first load
        # of a browser that carried another value managed to paint light before being fixed
        # on the next one. Writing the class here removes that flash.
        #
        # Why it is needed: Reflex's own reset, which reacts to a change of
        # `default_color_mode`, lives inside `if (isDevMode)` in `utils/react-theme.js`. It
        # never runs in production.
        rx.script(
            "try{localStorage.setItem('theme','dark');"
            "localStorage.setItem('last_compiled_theme','dark');"
            "document.documentElement.classList.remove('light');"
            "document.documentElement.classList.add('dark');"
            "document.documentElement.style.colorScheme='dark';}catch(e){}"
        ),
    ],
)

app.add_page(
    home.home_page,
    route="/",
    title="CV Generator",
    on_load=home.HomeState.load,
)
app.add_page(
    wizard.wizard_page,
    route="/new",
    title="New CV",
    on_load=wizard.WizardState.start,
)
app.add_page(
    profile.profile_page,
    route="/profile",
    title="My profile",
    on_load=profile.ProfileState.start,
)
app.add_page(
    sync.sync_page,
    route="/sync",
    title="Sync with LinkedIn",
    on_load=sync.SyncState.start,
)
