"""Every text field the server controls is buffered, so typing fast does not drop letters.

A field with `value=` and `on_change=` sends each key to the server, and the server's echo
rewrites it while you type on: "+34 600 333 444" typed fast became "4" in My profile.
`rx.debounce_input` sends after a pause, on Enter and when you leave the field, and ignores
the echo while you type. Reflex adds it on its own only to `rx.input`, not to `rx.el.input`
or `rx.el.textarea`, which are what this app uses.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "cv_generator" / "app"
TEXT_FIELDS = {"rx.el.input", "rx.el.textarea"}


def _keywords(call: ast.Call) -> set[str]:
    return {keyword.arg for keyword in call.keywords if keyword.arg}


def unbuffered_fields(source: str) -> list[int]:
    """Lines of the text fields with `value=` and `on_change=` that are not the direct child
    of `rx.debounce_input`."""
    tree = ast.parse(source)
    buffered = {
        id(argument)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "rx.debounce_input"
        for argument in node.args
    }
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) in TEXT_FIELDS
        and {"value", "on_change"} <= _keywords(node)
        and id(node) not in buffered
    ]


def test_the_check_finds_an_unbuffered_field_and_accepts_a_buffered_one() -> None:
    bare = "rx.el.input(value=State.name, on_change=State.set_name)"
    wrapped = "rx.debounce_input(rx.el.textarea(value=State.text, on_change=State.set_text))"
    uncontrolled = "rx.el.input(default_value=State.name, on_blur=State.set_name)"

    assert unbuffered_fields(bare) == [1]
    assert unbuffered_fields(wrapped) == []
    assert unbuffered_fields(uncontrolled) == []


def test_every_controlled_text_field_of_the_app_is_buffered() -> None:
    offenders = [
        f"{path.relative_to(APP.parent)}:{line}"
        for path in sorted(APP.rglob("*.py"))
        for line in unbuffered_fields(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
