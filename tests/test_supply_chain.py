import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", re.MULTILINE)
PINNED = re.compile(r"@[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"#\s*v\d")


def test_every_action_is_pinned_to_a_commit() -> None:
    """A tag like `@v5` can be moved to other code by whoever controls the action's repo,
    and the next CI run executes it here. A commit can't be moved: the comment keeps the
    version readable, and Dependabot proposes the next commit."""
    references = [(path.name, match[1], match[2]) for path in WORKFLOWS for match in USES.finditer(path.read_text())]
    assert references, "no workflow uses an action"

    loose = [
        f"{name}: {reference}"
        for name, reference, comment in references
        if not reference.startswith("./") and not (PINNED.search(reference) and VERSION_COMMENT.search(comment))
    ]

    assert loose == []
