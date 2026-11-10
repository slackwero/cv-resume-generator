"""The frontend's route table, written from the app's own pages.

Reflex's app/routes.js asks @react-router/fs-routes to read the table from the file names
of the compiled pages. fs-routes needs minimatch 10, whose advisory (GHSA-g3hv-75wg-m249)
is fixed only in minimatch 11, and 11 drops the `makeRe` fs-routes imports. Reflex knows
every page when it compiles, so this plugin writes the table fs-routes built, and
rxconfig.py takes fs-routes out of the frontend packages.

Only literal segments are supported. fs-routes also turned `[id]` into `:id`, `[[id]]`
into an optional segment and `[...]` into a splat; no page here uses them, and a page that
does stops the compile instead of answering the wrong URL.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Unpack

from reflex.compiler.utils import get_page_path
from reflex_base.constants.route import Page404
from reflex_base.plugins.base import Plugin, PreCompileContext

# Relative to .web, where Reflex writes every compiled file.
ROUTES_FILE = "app/routes.js"
INDEX_ROUTE = "index"


def _page_file(route: str) -> str:
    """The compiled page's name without extension, as Reflex writes it: `[new]._index`."""
    return Path(get_page_path(route)).stem


def _page_entry(route: str) -> dict[str, object]:
    if "[" in route:
        raise ValueError(f"The page {route} has a dynamic segment, which {__name__} doesn't route.")
    name = _page_file(route)
    entry: dict[str, object] = {"id": f"routes/{name}", "index": True}
    if route != INDEX_ROUTE:
        entry["path"] = route
    entry["file"] = f"routes/{name}.jsx"
    return entry


def route_table(routes: Iterable[str]) -> str:
    """The routes.js module for these page routes, with the entries fs-routes gave them."""
    not_found = _page_file(Page404.SLUG)
    table = [_page_entry(route) for route in routes if route != Page404.SLUG]
    table.append({"id": f"routes/{not_found}", "path": "*", "file": f"routes/{not_found}.jsx"})
    return f"// Written by {__name__} on every compile.\nexport default {json.dumps(table, indent=2)};\n"


def _routes_file(routes: list[str]) -> tuple[str, str]:
    return ROUTES_FILE, route_table(routes)


class RouteTablePlugin(Plugin):
    """Replaces Reflex's routes.js, which needs fs-routes, before every compile."""

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        context["add_save_task"](_routes_file, [page.route for page in context["unevaluated_pages"]])
