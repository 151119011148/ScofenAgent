#!/bin/bash
cd "/Users/gaoying/Desktop/study/ai学习/smolagents" || { echo "进不去 /Users/gaoying/Desktop/study/ai学习/smolagents"; exit 1; }
echo "启动 Agent UI（Ctrl-C 停止）… 日志同时写入 /Users/gaoying/Desktop/study/ai学习/.agent-ui.log"
PYTHONUNBUFFERED=1 .venv/bin/python -u my_ui.py 2>&1 | tee "/Users/gaoying/Desktop/study/ai学习/.agent-ui.log"
case "${PIPESTATUS[0]}" in
  0|130) bash "/Users/gaoying/Desktop/关闭Agent.command" 2>/dev/null || bash "/Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/agent-win-close.sh" "$(tty 2>/dev/null)" ;;   # 正常停或 Ctrl-C：连窗口一起收
  *) echo "服务异常退出（rc=${PIPESTATUS[0]}），窗口给你留着看报错" ;;
esac
