#!/bin/bash
T="${1:-}"
[ -n "$T" ] || exit 0
exec /usr/bin/python3 "/tmp/agent-win-detach.py" "$T" "${2:-2}"
