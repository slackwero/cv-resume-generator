import ast
import sys
from pathlib import Path

import pytest

from launcher.console import ask, open_log, run_logged


def test_the_launcher_uses_only_the_standard_library() -> None:
    for path in (Path(__file__).parents[1] / "launcher").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                assert top in sys.stdlib_module_names or top == "launcher", f"{path.name} imports {name}"


@pytest.mark.parametrize("answer", ["", "y", "Y", "yes", " YES "])
def test_enter_and_yes_mean_yes(answer: str) -> None:
    assert ask("Install it now?", assume_yes=False, read=lambda _: answer)


@pytest.mark.parametrize("answer", ["n", "N", "no", "No"])
def test_no_means_no(answer: str) -> None:
    assert not ask("Install it now?", assume_yes=False, read=lambda _: answer)


def test_an_unclear_answer_is_asked_again() -> None:
    answers = iter(["maybe", "y"])
    assert ask("Install it now?", assume_yes=False, read=lambda _: next(answers))
    # and both answers were consumed:
    assert next(answers, None) is None


def test_without_a_terminal_the_answer_is_no() -> None:
    def closed(_: str) -> str:
        raise EOFError

    assert not ask("Install it now?", assume_yes=False, read=closed)


def test_assume_yes_never_reads() -> None:
    def must_not_read(_: str) -> str:
        raise AssertionError("read was called")

    assert ask("Install it now?", assume_yes=True, read=must_not_read)


def test_a_successful_command_keeps_its_output_in_the_log(tmp_path: Path) -> None:
    log = open_log(tmp_path)
    assert run_logged([sys.executable, "-c", "print('hello')"], log)
    log.close()
    assert "hello" in (tmp_path / "start.log").read_text(encoding="utf-8")


def test_a_failing_command_is_reported(tmp_path: Path) -> None:
    with open_log(tmp_path) as log:
        assert not run_logged([sys.executable, "-c", "raise SystemExit(3)"], log)


def test_a_missing_program_is_a_failure_not_a_crash(tmp_path: Path) -> None:
    with open_log(tmp_path) as log:
        assert not run_logged(["no-such-program-cv-generator"], log)
    assert "no-such-program-cv-generator" in (tmp_path / "start.log").read_text(encoding="utf-8")


def test_a_long_command_says_it_is_still_working(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with open_log(tmp_path) as log:
        run_logged([sys.executable, "-c", "import time; time.sleep(0.5)"], log, heartbeat_seconds=0.1)
    assert "Still working" in capsys.readouterr().out
