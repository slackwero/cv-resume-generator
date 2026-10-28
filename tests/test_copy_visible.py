"""Guards on the text the user reads on screen.

A Cyrillic or Greek homoglyph is indistinguishable from its Latin letter at a glance,
gets through human review and the spell checker, and only gives itself away when the
word is searched for or read by a screen reader. It slips in when typing with two
keyboard layouts active.
"""

import ast
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "cv_generator"

# Scripts whose letters have a Latin homoglyph. The interface only needs the Latin script.
FOREIGN_SCRIPTS = ("CYRILLIC", "GREEK", "ARMENIAN")


def _strings(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _homoglyphs(text: str) -> list[str]:
    return [char for char in text if ord(char) > 127 and any(a in unicodedata.name(char, "") for a in FOREIGN_SCRIPTS)]


def _files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in str(p))


@pytest.mark.parametrize("path", _files(), ids=lambda p: p.name)
def test_no_string_mixes_scripts(path: Path) -> None:
    intruders = [
        f"line {line}: {''.join(bad)!r} in {text[:60]!r}" for line, text in _strings(path) if (bad := _homoglyphs(text))
    ]

    assert not intruders, f"characters from another script in {path.name}: " + "; ".join(intruders)


def test_the_detector_recognizes_a_homoglyph() -> None:
    """Without this canary, a failure in the detection would make the test pass vacuously."""
    assert _homoglyphs("identical") == []
    assert _homoglyphs("idеntical") == ["\u0435"]


def test_there_are_files_to_check() -> None:
    assert len(_files()) > 10
