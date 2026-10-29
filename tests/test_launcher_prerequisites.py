from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TextIO

import pytest

from launcher import prerequisites
from launcher.prerequisites import Prerequisite, folder_problem, required_prerequisites

BREW = "/opt/homebrew/bin/brew"
WINDOWS_BASH = r"C:\msys64\usr\bin\bash.exe"


class Recorder:
    """Stands in for `run_logged`: remembers every command and reports success."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.envs: list[dict[str, str]] = []

    def __call__(self, command: list[str], log: TextIO, *, env: dict[str, str] | None = None, **_: object) -> bool:
        self.commands.append(list(command))
        self.envs.append(dict(env or {}))
        return True


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorded = Recorder()
    monkeypatch.setattr(prerequisites, "run_logged", recorded)
    return recorded


@pytest.fixture
def log(tmp_path: Path) -> TextIO:
    with (tmp_path / "start.log").open("w", encoding="utf-8") as handle:
        yield handle


def named(platform: str, name: str) -> Prerequisite:
    return next(p for p in required_prerequisites(platform) if p.name == name)


def fake_linux(monkeypatch: pytest.MonkeyPatch, manager: str | None, *, root: bool = False) -> None:
    monkeypatch.setattr(prerequisites, "linux_package_manager", lambda: manager)
    monkeypatch.setattr(prerequisites, "is_root", lambda: root)


def tools_missing(monkeypatch: pytest.MonkeyPatch, *missing: str) -> None:
    monkeypatch.setattr(prerequisites.shutil, "which", lambda name: None if name in missing else f"/usr/bin/{name}")


def manual_lines(item: Prerequisite) -> list[str]:
    return [line.strip() for line in item.manual_help.splitlines()]


def test_a_mac_without_homebrew_needs_homebrew_then_pango(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prerequisites, "find_brew", lambda: None)
    monkeypatch.setattr(prerequisites, "macos_pdf_libraries_present", lambda: False)
    missing = [p.name for p in required_prerequisites("darwin") if not p.is_present()]
    assert missing == ["Homebrew", "Pango"]


def test_a_ready_mac_needs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prerequisites, "find_brew", lambda: BREW)
    monkeypatch.setattr(prerequisites, "macos_pdf_libraries_present", lambda: True)
    assert all(p.is_present() for p in required_prerequisites("darwin"))


def test_pango_on_a_mac_comes_from_homebrew(monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO) -> None:
    monkeypatch.setattr(prerequisites, "find_brew", lambda: BREW)
    install = named("darwin", "Pango").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [[BREW, "install", "pango"]]


def test_homebrew_runs_its_official_installer_without_prompts(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO, tmp_path: Path
) -> None:
    monkeypatch.setattr(prerequisites, "fetch_homebrew_installer", lambda folder: tmp_path / "install.sh")
    homebrew = named("darwin", "Homebrew")
    assert homebrew.needs_admin is True
    assert homebrew.install is not None
    assert homebrew.install(log) is True
    assert recorder.commands == [["/bin/bash", str(tmp_path / "install.sh")]]
    assert recorder.envs[0]["NONINTERACTIVE"] == "1"


def test_debian_installs_pango_with_apt(monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO) -> None:
    fake_linux(monkeypatch, "apt-get")
    install = named("linux", "Pango").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [
        ["sudo", "apt-get", "update"],
        [
            "sudo",
            "env",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "install",
            "-y",
            "libpango-1.0-0",
            "libpangoft2-1.0-0",
            "libharfbuzz-subset0",
        ],
    ]


def test_fedora_installs_pango_with_dnf(monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO) -> None:
    fake_linux(monkeypatch, "dnf")
    install = named("linux", "Pango").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [["sudo", "dnf", "install", "-y", "pango"]]


def test_curl_and_unzip_come_from_the_package_manager(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO
) -> None:
    fake_linux(monkeypatch, "dnf")
    install = named("linux", "curl and unzip").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [["sudo", "dnf", "install", "-y", "curl", "unzip"]]


def test_root_installs_without_sudo(monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO) -> None:
    fake_linux(monkeypatch, "apt-get", root=True)
    install = named("linux", "Pango").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands
    assert not any(command[0] == "sudo" for command in recorder.commands)


def test_linux_without_unzip_needs_curl_and_unzip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prerequisites, "linux_pdf_libraries_present", lambda: True)
    monkeypatch.setattr(prerequisites.shutil, "which", lambda name: None if name == "unzip" else f"/usr/bin/{name}")
    missing = [p.name for p in required_prerequisites("linux") if not p.is_present()]
    assert missing == ["curl and unzip"]


def test_an_unknown_linux_explains_instead_of_installing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_linux(monkeypatch, None)
    items = required_prerequisites("linux")
    assert items
    assert all(p.install is None for p in items)
    generic = "On another Linux, install Pango, curl and unzip with your distribution's package manager."
    assert all(generic in manual_lines(p) for p in items)


@pytest.mark.parametrize(
    ("missing", "name", "apt", "dnf"),
    [
        (
            (),
            "Pango",
            "sudo apt-get update && sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0",
            "sudo dnf install -y pango",
        ),
        (
            ("curl", "unzip"),
            "curl and unzip",
            "sudo apt-get update && sudo apt-get install -y curl unzip",
            "sudo dnf install -y curl unzip",
        ),
    ],
)
def test_the_linux_manual_steps_put_each_command_on_a_line_of_its_own(
    monkeypatch: pytest.MonkeyPatch, missing: tuple[str, ...], name: str, apt: str, dnf: str
) -> None:
    """A command the person copies must not end in punctuation that the shell would read."""
    tools_missing(monkeypatch, *missing)
    lines = manual_lines(named("linux", name))
    assert apt in lines
    assert dnf in lines


@pytest.mark.parametrize(
    ("platform", "name", "command"),
    [("darwin", "Pango", "brew install pango"), ("win32", "Pango", "pacman -S mingw-w64-x86_64-pango")],
)
def test_a_command_to_copy_stands_on_a_line_of_its_own(platform: str, name: str, command: str) -> None:
    assert command in manual_lines(named(platform, name))


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_every_manual_step_ends_by_saying_to_start_again(platform: str) -> None:
    for item in required_prerequisites(platform):
        assert manual_lines(item)[-1] == "Then start CV Generator again."


def test_windows_gets_msys2_from_winget(monkeypatch: pytest.MonkeyPatch, recorder: Recorder, log: TextIO) -> None:
    monkeypatch.setattr(prerequisites.shutil, "which", lambda name: "winget" if name == "winget" else None)
    install = named("win32", "MSYS2").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [
        [
            "winget",
            "install",
            "--id",
            "MSYS2.MSYS2",
            "--exact",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    ]


def test_windows_without_winget_explains_how_to_get_msys2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prerequisites.shutil, "which", lambda name: None)
    msys2 = named("win32", "MSYS2")
    assert msys2.install is None
    assert "msys2.org" in msys2.manual_help


def test_windows_gets_pango_from_msys2(recorder: Recorder, log: TextIO) -> None:
    install = named("win32", "Pango").install
    assert install is not None
    assert install(log) is True
    assert recorder.commands == [[WINDOWS_BASH, "-lc", "pacman -Sy --noconfirm --needed mingw-w64-x86_64-pango"]]


def test_a_folder_inside_onedrive_is_refused_on_windows() -> None:
    problem = folder_problem(PureWindowsPath(r"C:\Users\ana\OneDrive\Desktop\cv"), "win32")
    assert problem is not None
    assert "OneDrive" in problem


def test_onedrive_only_matters_on_windows() -> None:
    assert folder_problem(PurePosixPath("/Users/ana/OneDrive/cv"), "darwin") is None
    assert folder_problem(PureWindowsPath(r"C:\Users\ana\Downloads\cv"), "win32") is None


def test_ensure_admin_is_true_for_root_and_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prerequisites, "is_root", lambda: True)
    assert prerequisites.ensure_admin() is True
    monkeypatch.setattr(prerequisites, "is_root", lambda: False)
    monkeypatch.setattr(prerequisites.sys, "platform", "win32")
    assert prerequisites.ensure_admin() is True


def test_is_root_does_not_crash_without_geteuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(prerequisites.os, "geteuid", raising=False)
    assert prerequisites.is_root() is False
