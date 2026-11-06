#!/bin/bash
rm -rf /tmp/mmd-profile
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --user-data-dir=/tmp/mmd-profile --virtual-time-budget=25000 \
  --dump-dom "file:///Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/mmd_harness.html" 2>/dev/null \
| tr '#' '\n' | grep -E '^[0-9]+ (OK|FAIL)|^TOTAL'
