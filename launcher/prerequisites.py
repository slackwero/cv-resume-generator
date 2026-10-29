"""What each system needs before CV Generator can draw PDFs, and how to get it.

The app itself comes from `uv sync`, but WeasyPrint also needs Pango and friends from the
operating system, and Reflex's bun installer needs `curl` and `unzip` on Linux. This module
only knows what is missing and how to install it; asking the person first is the caller's
job. Every command is a constant of the launcher, never built from input.

The Windows helpers must also run on other systems (they just report "not there"), because
the tests exercise that branch on a Mac: the platform is a parameter, never read at import.
"""

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import TextIO

from launcher.console import run_logged, say

HOMEBREW_INSTALLER_URL = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

# Keep in step with MACOS_LIBRARY_DIRS in cv_generator/native_libs.py (the launcher cannot
# import the app: it runs before the app's dependencies exist).
MACOS_LIBRARY_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")
BREW_CANDIDATES = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")

# The file names are the ones WeasyPrint itself opens (weasyprint/text/ffi.py).
MACOS_LIBRARIES = (
    "libgobject-2.0.0.dylib",
    "libpango-1.0.dylib",
    "libharfbuzz.0.dylib",
    "libfontconfig.1.dylib",
    "libpangoft2-1.0.dylib",
)
LINUX_LIBRARIES = (
    "libgobject-2.0.so.0",
    "libpango-1.0.so.0",
    "libharfbuzz.so.0",
    "libfontconfig.so.1",
    "libpangoft2-1.0.so.0",
)
WINDOWS_LIBRARIES = (
    "libgobject-2.0-0.dll",
    "libpango-1.0-0.dll",
    "libharfbuzz-0.dll",
    "libfontconfig-1.dll",
    "libpangoft2-1.0-0.dll",
)

# WeasyPrint adds this folder as a DLL directory by default on Windows.
MSYS2_BASH = r"C:\msys64\usr\bin\bash.exe"
MSYS2_LIBRARY_DIR = r"C:\msys64\mingw64\bin"

APT_PANGO_PACKAGES = ("libpango-1.0-0", "libpangoft2-1.0-0", "libharfbuzz-subset0")
DNF_PANGO_PACKAGES = ("pango",)
TOOL_PACKAGES = ("curl", "unzip")

HOMEBREW_REASON = (
    "Homebrew is the usual way to install software on a Mac. CV Generator uses it to install the "
    "libraries that draw your PDFs. It asks for your Mac password, and the first time it can take "
    "10 to 20 minutes."
)
PANGO_REASON = "Pango is the set of libraries CV Generator uses to draw your CVs as PDF files."
TOOLS_REASON = (
    "curl and unzip are two small tools CV Generator uses to download and unpack the part that runs its interface."
)
MSYS2_REASON = (
    "MSYS2 is a free collection of tools for Windows. CV Generator uses it to get the libraries that draw your PDFs."
)

# Every command the person may copy stands on a line of its own: punctuation after it on the
# same line ends up in the terminal too ("brew install pango," finds no such package).
_AGAIN = "Then start CV Generator again."
_LINUX_MANUAL = (
    "On Debian or Ubuntu, run:\n"
    "    sudo apt-get update && sudo apt-get install -y {apt}\n"
    "On Fedora, run:\n"
    "    sudo dnf install -y {dnf}\n"
    "On another Linux, install Pango, curl and unzip with your distribution's package manager.\n"
) + _AGAIN


@dataclass(frozen=True)
class Prerequisite:
    """One thing the system must have; `install` is None when this computer cannot do it for the person."""

    name: str
    reason: str
    manual_help: str
    is_present: Callable[[], bool]
    install: Callable[[TextIO], bool] | None
    needs_admin: bool = False


def find_brew() -> str | None:
    """Homebrew's path, also when it is installed but not on this shell's PATH."""
    found = shutil.which("brew")
    if found:
        return found
    return next((candidate for candidate in BREW_CANDIDATES if Path(candidate).exists()), None)


def macos_pdf_libraries_present() -> bool:
    return all(any(Path(folder, name).exists() for folder in MACOS_LIBRARY_DIRS) for name in MACOS_LIBRARIES)


def linux_pdf_libraries_present() -> bool:
    for name in LINUX_LIBRARIES:
        try:
            ctypes.CDLL(name)
        except OSError:
            return False
    return True


def windows_pdf_libraries_present() -> bool:
    return all(Path(MSYS2_LIBRARY_DIR, name).exists() for name in WINDOWS_LIBRARIES)


def linux_package_manager() -> str | None:
    return next((manager for manager in ("apt-get", "dnf") if shutil.which(manager)), None)


def is_root() -> bool:
    """True for the superuser; Windows has no `geteuid` and asks through UAC instead."""
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def fetch_homebrew_installer(folder: Path) -> Path:
    """Saves Homebrew's official install script in `folder` and returns its path."""
    script = folder / "install.sh"
    # The URL is the https constant above, never built from input.
    with urllib.request.urlopen(HOMEBREW_INSTALLER_URL, timeout=60) as response:  # noqa: S310
        script.write_bytes(response.read())
    return script


def ensure_admin() -> bool:
    """Gets administrator rights up front, so a long install does not stop at a password prompt."""
    if sys.platform == "win32" or is_root():
        return True  # Windows asks for permission by itself (UAC)
    say("Your computer password is needed to install software. It does not show while you type.")
    try:
        # The terminal stays attached on purpose: that is where sudo shows its prompt.
        return subprocess.run(["sudo", "-v"], check=False).returncode == 0  # noqa: S603, S607 - constant command
    except OSError:
        return False


def folder_problem(folder: PurePath, platform: str = sys.platform) -> str | None:
    """Why CV Generator cannot live in `folder`, or None when it can."""
    if platform == "win32" and "onedrive" in str(folder).lower():
        return (
            "This folder is inside OneDrive, which copies every file to the cloud and gets in the way of "
            "installing the app. Move the CV Generator folder out of OneDrive, for example to "
            f"{Path.home() / 'CV Generator'}, and start it again."
        )
    return None


def _install_homebrew(log: TextIO) -> bool:
    with tempfile.TemporaryDirectory(prefix="cv-generator-") as folder:
        try:
            script = fetch_homebrew_installer(Path(folder))
        except OSError as error:
            log.write(f"Could not download the Homebrew installer: {error}\n")
            log.flush()
            return False
        return run_logged(["/bin/bash", str(script)], log, env={"NONINTERACTIVE": "1"})


def _install_pango_with_brew(log: TextIO) -> bool:
    brew = find_brew()
    return brew is not None and run_logged([brew, "install", "pango"], log)


def _linux_installer(
    manager: str | None, apt_packages: tuple[str, ...], dnf_packages: tuple[str, ...]
) -> Callable[[TextIO], bool] | None:
    """Builds the install step for apt or dnf; None on a distribution we do not know."""
    sudo = [] if is_root() else ["sudo"]

    if manager == "apt-get":

        def with_apt(log: TextIO) -> bool:
            return run_logged([*sudo, "apt-get", "update"], log) and run_logged(
                [*sudo, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *apt_packages], log
            )

        return with_apt
    if manager == "dnf":

        def with_dnf(log: TextIO) -> bool:
            return run_logged([*sudo, "dnf", "install", "-y", *dnf_packages], log)

        return with_dnf
    return None


def _install_msys2(log: TextIO) -> bool:
    command = [
        "winget",
        "install",
        "--id",
        "MSYS2.MSYS2",
        "--exact",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    return run_logged(command, log)


def _install_pango_with_msys2(log: TextIO) -> bool:
    return run_logged([MSYS2_BASH, "-lc", "pacman -Sy --noconfirm --needed mingw-w64-x86_64-pango"], log)


def _tools_present() -> bool:
    return all(shutil.which(tool) for tool in TOOL_PACKAGES)


def _missing_tools() -> tuple[str, ...]:
    """Only the tools that are missing get installed: Fedora ships curl-minimal, and asking dnf
    for curl as well is a conflict."""
    return tuple(tool for tool in TOOL_PACKAGES if not shutil.which(tool))


def required_prerequisites(platform: str = sys.platform) -> list[Prerequisite]:
    """What `platform` needs, in the order it has to be installed."""
    if platform == "darwin":
        return [
            Prerequisite(
                "Homebrew",
                HOMEBREW_REASON,
                f"Install Homebrew from https://brew.sh\n{_AGAIN}",
                lambda: find_brew() is not None,
                _install_homebrew,
                needs_admin=True,
            ),
            Prerequisite(
                "Pango",
                PANGO_REASON,
                f"Open Terminal and run:\n    brew install pango\n{_AGAIN}",
                macos_pdf_libraries_present,
                _install_pango_with_brew,
            ),
        ]
    if platform == "win32":
        has_winget = shutil.which("winget") is not None
        return [
            Prerequisite(
                "MSYS2",
                MSYS2_REASON,
                f"Install MSYS2 from https://www.msys2.org into C:\\msys64\n{_AGAIN}",
                lambda: Path(MSYS2_BASH).exists(),
                _install_msys2 if has_winget else None,
            ),
            Prerequisite(
                "Pango",
                PANGO_REASON,
                f'Open "MSYS2 MINGW64" from the Start menu and run:\n    pacman -S mingw-w64-x86_64-pango\n{_AGAIN}',
                windows_pdf_libraries_present,
                _install_pango_with_msys2,
            ),
        ]
    manager = linux_package_manager()
    manual = _LINUX_MANUAL.format(apt=" ".join(APT_PANGO_PACKAGES), dnf=" ".join(DNF_PANGO_PACKAGES))
    tools = _missing_tools()
    tools_manual = _LINUX_MANUAL.format(apt=" ".join(tools), dnf=" ".join(tools))
    return [
        Prerequisite(
            "curl and unzip",
            TOOLS_REASON,
            tools_manual,
            _tools_present,
            _linux_installer(manager, tools, tools),
            needs_admin=True,
        ),
        Prerequisite(
            "Pango",
            PANGO_REASON,
            manual,
            linux_pdf_libraries_present,
            _linux_installer(manager, APT_PANGO_PACKAGES, DNF_PANGO_PACKAGES),
            needs_admin=True,
        ),
    ]
