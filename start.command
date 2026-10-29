#!/bin/bash
# Finder opens .command files in Terminal; this one only exists so that a
# double-click works. The real script is start.sh.
exec /bin/bash "$(dirname "$0")/start.sh" "$@"
