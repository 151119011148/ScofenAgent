#!/bin/bash
T="${1:-}"
[ -n "$T" ] || exit 0
exec /usr/bin/python3 "/Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/agent-win-detach.py" "$T" "${2:-2}"
