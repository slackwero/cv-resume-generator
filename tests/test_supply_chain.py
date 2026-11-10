import re
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
OSV_CONFIG = ROOT / "osv-scanner.toml"
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


def test_every_ignored_advisory_says_why_and_until_when() -> None:
    """The dependency audit lets a known advisory pass only with its reason written down and
    a date when it stops passing, so an exception can't outlive the decision behind it."""
    ignored = tomllib.loads(OSV_CONFIG.read_text()).get("IgnoredVulns", [])

    for entry in ignored:
        assert entry["id"].strip()
        assert entry["reason"].strip(), entry["id"]
        assert isinstance(entry["ignoreUntil"], date), entry["id"]
