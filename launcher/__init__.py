"""One-click launcher for CV Generator.

It checks what the app needs, offers to install what is missing, installs the app's
packages and opens it in the browser. The shell scripts (`start.sh`, `start.ps1`, ...)
run it with `uv run --no-project --python 3.12 python -m launcher`.

This package imports only the standard library. It runs before the app's packages are
installed (installing them with `uv sync` is part of its job), so anything else it
imported would not be there yet.
"""
