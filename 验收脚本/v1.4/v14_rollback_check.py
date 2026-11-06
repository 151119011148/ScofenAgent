# -*- coding: utf-8 -*-
"""v1.4 回滚演练的断言侧：只做检查，拷贝由外层 bash 命令做（每步都能对上文件）。

用法：python v14_rollback_check.py v13|v14
"""
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
UI = BASE / "my_ui.py"
ROLL = BASE.parent / ".rollback"

want = sys.argv[1]
src = UI.read_text(encoding="utf-8")
lines = len(src.splitlines())
res = []


def ck(name, cond, detail=""):
    res.append((name, bool(cond), detail))


tmp = Path(tempfile.mkdtemp()) / "c.pyc"
py_compile.compile(str(UI), cfile=str(tmp), doraise=True)
ck("py_compile 通过", tmp.exists())
ck("无语法残留（import 后可构造）", subprocess.run(
    [str(BASE / ".venv/bin/python"), "-c", "import sys; sys.path.insert(0,%r); import my_ui; print(type(my_ui.OpsUI.create_app).__name__)" % str(BASE)],
    capture_output=True, text=True, cwd=str(BASE)).returncode == 0)

if want == "v13":
    ck("行数 850（v1.3 落盘）", 845 <= lines <= 855, lines)
    ck("没有 _bind_memory", "_bind_memory" not in src)
    ck("没有会话级记忆缓存", "_mem_sid" not in src and "AgentMemory" not in src)
    ck("_respond 仍从 [user_msg] 起头（D5 未修形态）", "last: list = [user_msg]" in src and "base = self.hist.load" not in src)
    ck("radio.change 只有两个输出（V5 未接线形态）", "outputs=[chatbot, status])" in src)
    ck("_on_load 是闭包且交出 None sid", "def _on_load():" in src and "gr.update(choices=ch), None," in src)
    ck("save() 的 UPDATE 仍带 WHERE title 条件（D6 未修形态）", "WHERE id = ? AND title = '新会话'" in src)
    ck("v1.3 的审批闸还在", "GATED_TOOLS" in src and "_step_card" in src and "_approval_card" in src)
else:
    ck("行数 893（v1.4 落盘）", 885 <= lines <= 900, lines)
    ck("_bind_memory 在", "def _bind_memory(self, sid: int) -> None:" in src)
    ck("会话级记忆缓存在", "_mem_sid" in src and "AgentMemory" in src)
    ck("_respond 以库里那串起头（D5 已修）", "base = self.hist.load(sid)" in src and "last = base + [user_msg] + list(msgs)" in src)
    ck("radio.change 交出第三个输出 sid（V5 已接）", "outputs=[chatbot, status, sid])" in src)
    ck("_on_load 已提成方法并交出 sid", "def _on_load(self):" in src and "int(ch[0][1]) if ch else None" in src)
    ck("save() 每次刷 updated_at、标题有 CASE 保护（D6 已修）", "CASE WHEN title = '新会话'" in src and "AND title = '新会话'" not in src)
    ck("v1.3 的审批闸没被碰坏", "GATED_TOOLS" in src and "_step_card" in src and "_approval_card" in src)

for name, ok, detail in res:
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  <<< " + str(detail)))
print("mode=%s lines=%d bytes=%d" % (want, lines, UI.stat().st_size))
sys.exit(0 if all(ok for _, ok, _ in res) else 1)
