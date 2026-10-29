#!/usr/bin/env bash
# Starts CV Generator on macOS and Linux.
#
# This file only gets uv, the one tool the rest depends on, and only after
# asking. Everything else (Python, the app's packages, the system libraries,
# the browser) is done by the Python launcher in launcher/, which uv runs.
# Written for bash 3.2, the /bin/bash of macOS: no associative arrays, no
# ${var,,}, no mapfile.
set -u
set -o pipefail

cd "$(dirname "$0")" || exit 1

# --yes means "do not ask". It is also handed to the launcher, so every
# argument reaches it unchanged.
assume_yes=0
for arg in "$@"; do
    if [ "$arg" = "--yes" ]; then
        assume_yes=1
    fi
done

find_uv() {
    local candidate
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

install_uv() {
    # The installer would otherwise edit the person's shell profile. The path
    # of uv is found again by find_uv, so no profile needs to change.
    export UV_NO_MODIFY_PATH=1
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "CV Generator needs curl or wget to download uv. Install curl with your system's package manager and start it again."
        exit 1
    fi
}

uv="$(find_uv)"
if [ -z "$uv" ]; then
    echo "uv is missing. uv is the tool CV Generator uses to download Python and the app's packages."
    answer="n"
    if [ "$assume_yes" = "1" ]; then
        answer="y"
    else
        printf 'Install it now? [Y/n] '
        # With no terminal, read fails at EOF and the answer stays "no".
        if read -r reply; then
            answer="${reply:-y}"
        else
            echo
        fi
    fi
    case "$answer" in
        [Yy] | [Yy][Ee][Ss]) ;;
        *)
            echo "To install it yourself, follow https://docs.astral.sh/uv/getting-started/installation/ and then start CV Generator again."
            exit 1
            ;;
    esac
    install_uv || {
        echo "Installing uv did not work."
        exit 1
    }
    uv="$(find_uv)"
    if [ -z "$uv" ]; then
        echo "Installing uv did not work."
        exit 1
    fi
fi

echo "Getting ready..."
# exec: this process becomes uv, which forwards SIGTERM and SIGHUP to the
# launcher, so closing the Terminal window stops the app.
exec "$uv" run --no-project --python 3.12 --quiet python -m launcher "$@"
