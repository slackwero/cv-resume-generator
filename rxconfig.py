import os

import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_components_radix.plugin import RadixThemesPlugin

# In development, Reflex restarts the backend when a file changes in the project
# folders, except for extensions it knows to ignore. It ignores `.json`, but not the
# `.profile.json.tmp` used for atomic saves nor the PDFs in output/, so every save made
# by the app itself restarted it: the running event died halfway (the "Generate" button
# got stuck) and the wizard open in another tab went back to step 1. What the app
# writes is not code, so those folders are not watched. It is set here because Reflex
# reads the variable after loading this file.
os.environ.setdefault("REFLEX_HOT_RELOAD_EXCLUDE_PATHS", "data:output")

config = rx.Config(
    app_name="cv_generator",
    app_module_import="cv_generator.app.app",
    # The world is black glass: light mode was dropped by explicit decision on
    # 2026-09-20. Keeping it that way takes THREE pieces, and none is enough alone:
    #
    #   1. `default_color_mode` (here). It is Reflex's own system and what writes the
    #      class Radix reads to choose a palette. It came as "system", so the interface
    #      followed the operating system no matter what the theme asked for.
    #
    #   2. The theme's `appearance` (further down). It fixes the Radix palette.
    #
    #   3. The <head> script, in cv_generator/app/app.py. It is what wins over a value
    #      already saved in `localStorage`, because Reflex's own reset lives inside
    #      `if (isDevMode)` and NEVER runs in production.
    #
    # With only the second one, everything without an explicit background was drawn light:
    # the bar and the rows came out black because they have their own background, and the rest white.
    default_color_mode="dark",
    # It is a personal tool, not a Reflex showcase.
    show_built_with_reflex=False,
    plugins=[
        RadixThemesPlugin(
            # The amber accent and zero radius align what is still Radix's (checkboxes,
            # radios, dialogs) with the rest of the scheme.
            #
            # `has_background=False` lets `html` paint the floor from style.css, not Radix.
            # It is the dark mode safety net: if the theme class ever resolved to light, the
            # worst that happens is that a Radix control keeps its light palette, not that a
            # white layer covers the whole black glass.
            #
            # The floor is painted by `html` and NOT `body`, on purpose: a `body` with its own
            # background covered its `::before`, and with it the silkscreen pattern. It is
            # explained in assets/style.css, where it is decided.
            theme=rx.theme(
                appearance="dark",
                accent_color="amber",
                gray_color="sand",
                radius="none",
                has_background=False,
            ),
        ),
    ],
    # Single-user local app: it does not need a sitemap.
    disable_plugins=[SitemapPlugin],
)
