#!/bin/bash
rm -rf /tmp/mmd-profile2
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --user-data-dir=/tmp/mmd-profile2 --virtual-time-budget=40000 \
  --dump-dom "file:///Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/mmd_render.html" 2>/dev/null \
| tr '#' '\n' | grep -E '^[0-9]+ (RENDER|THINSVG)|^TOTAL'
