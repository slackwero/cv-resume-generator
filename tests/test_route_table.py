import json
from types import SimpleNamespace

import pytest

from cv_generator.app.route_table import ROUTES_FILE, RouteTablePlugin, route_table

# What @react-router/fs-routes built from this app's compiled pages under Reflex 0.10.1,
# read with `react-router routes --json` before it was dropped. The plugin has to give
# React Router the same table.
FS_ROUTES_TABLE = [
    {"id": "routes/[profile]._index", "index": True, "path": "profile", "file": "routes/[profile]._index.jsx"},
    {"id": "routes/[sync]._index", "index": True, "path": "sync", "file": "routes/[sync]._index.jsx"},
    {"id": "routes/[new]._index", "index": True, "path": "new", "file": "routes/[new]._index.jsx"},
    {"id": "routes/_index", "index": True, "file": "routes/_index.jsx"},
    {"id": "routes/[404]._index", "path": "*", "file": "routes/[404]._index.jsx"},
]


def exported_table(module: str) -> list[dict[str, object]]:
    """The route table a routes.js written by `route_table` exports."""
    exported = module.split("export default ", 1)[1].strip().removesuffix(";")
    return json.loads(exported)


def by_id(table: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(table, key=lambda entry: str(entry["id"]))


def test_the_table_is_the_one_fs_routes_built() -> None:
    table = exported_table(route_table(["index", "new", "profile", "sync", "404"]))

    assert by_id(table) == by_id(FS_ROUTES_TABLE)


def test_unknown_paths_go_to_the_404_page_even_if_it_is_not_listed() -> None:
    """Reflex compiles its own 404 page when the app has none."""
    table = exported_table(route_table(["index"]))

    assert {"id": "routes/[404]._index", "path": "*", "file": "routes/[404]._index.jsx"} in table


def test_routes_js_no_longer_imports_fs_routes() -> None:
    assert "fs-routes" not in route_table(["index", "new"])


def test_a_dynamic_route_is_refused_instead_of_misrouted() -> None:
    """fs-routes turned `[id]` into `:id`, `[[id]]` into an optional segment and `[...]` into
    a splat; this table knows only literal segments, so a page with any of them stops the
    compile instead of answering the wrong URL."""
    with pytest.raises(ValueError, match=r"post/\[id\]"):
        route_table(["index", "post/[id]"])


def test_the_plugin_writes_routes_js_on_every_compile() -> None:
    saved: list[object] = []
    pages = [SimpleNamespace(route=route) for route in ("index", "new")]

    RouteTablePlugin().pre_compile(
        add_save_task=lambda task, *args, **kwargs: saved.append(task(*args, **kwargs)),
        unevaluated_pages=pages,
    )

    assert saved == [(ROUTES_FILE, route_table(["index", "new"]))]
