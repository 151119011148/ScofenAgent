# -*- coding: utf-8 -*-
"""v1.5 回滚演练的断言侧：只做检查，拷贝由外层 bash 命令做（每步都能对上文件）。

用法：python v15_rollback_check.py v14|v15
"""
import py_compile
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
UI = BASE / "my_ui.py"
LIVE_DB = Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15-live-hist.sqlite3")
res = []
want = sys.argv[1]
src = UI.read_text(encoding="utf-8")
lines = len(src.splitlines())


def ck(name, cond, detail=""):
    res.append((name, bool(cond), detail))


tmp = Path(tempfile.mkdtemp()) / "c.pyc"
py_compile.compile(str(UI), cfile=str(tmp), doraise=True)
ck("py_compile 通过", tmp.exists())
r = subprocess.run(
    [str(BASE / ".venv/bin/python"), "-c",
     "import sys; sys.path.insert(0,%r); import my_ui; print(len(open(my_ui.__file__,encoding='utf-8').read()))" % str(BASE)],
    capture_output=True, text=True, cwd=str(BASE))
# 断言用字符数不是字节数（中文注释 3 字节 1 字符：v1.4 是 44,838 B / 37,365 字符）。
# 顺带把「import 起来的正是磁盘上这一份」钉死：两边字符数必须相等。
ck("import 得起来（venv 3.13 + 真依赖），且就是这份文件",
   r.returncode == 0 and (r.stdout or "").strip() == str(len(src)),
   (r.returncode, (r.stdout or "").strip(), len(src), (r.stderr or "")[-200:]))

if want == "v14":
    ck("行数 893（v1.4 落盘）", 885 <= lines <= 900, lines)
    ck("没有记忆编解码（V6 未做形态）", "def encode_memory" not in src and "def decode_memory" not in src and "MEM_FMT" not in src)
    ck("库里没有 memory 表（V6 未做形态）", "CREATE TABLE IF NOT EXISTS memory" not in src and "def save_memory" not in src and "def load_memory" not in src)
    ck("_bind_memory 只新建、不读库", "def _bind_memory(self, sid: int) -> None:" in src and "load_memory" not in src)
    ck("D7 未修形态：没有轮次取消号", "_run_seq" not in src and "_cancelled_before" not in src)
    ck("D7 未修形态：入队前不判停止", "if OpsUI._run_seq <= OpsUI._cancelled_before" not in src)
    ck("D7 未修形态：_stop 只结算+置中断", "self._settle_all(\"cancelled\")\n        self.agent.interrupt()" in src)
    ck("v1.4 的 D5 还在（起点从库里那一串起）", "base = self.hist.load(sid)" in src and "last = base + [user_msg] + list(msgs)" in src)
    ck("v1.4 的 V5 还在（按会话各存一份，只在进程里）", "_mem: dict[int, AgentMemory]" in src and "_mem_sid" in src)
    ck("v1.4 的 D6 还在（每次刷 updated_at）", "title = CASE WHEN title = '新会话' THEN ? ELSE title END" in src)
    ck("v1.3 的审批闸与步骤卡还在", all(k in src for k in ("GATED_TOOLS", "_step_card", "_approval_card", "_install_gate")))
    # 兼容：v1.4 的代码能不能读 v1.5 写出来的那份库（多出来的 memory 表要不要紧）
    if LIVE_DB.exists():
        copy = Path(tempfile.mkdtemp()) / "compat.sqlite3"
        shutil.copy(str(LIVE_DB), str(copy))
        before = sqlite3.connect(str(copy)).execute("SELECT count(*) FROM messages WHERE session_id=1").fetchone()[0]
        code = (
            "import sys, pathlib, sqlite3\n"
            "sys.path.insert(0, r'{base}')\n"
            "import my_ui\n"
            "p = r'{copy}'\n"
            "h = my_ui.History(pathlib.Path(p))\n"
            "print(len(h.load(1)), len(h.choices()))\n"
            "h.save(2, h.load(2))\n"
            "print(len(h.load(2)))\n"
            "print([q[0] for q in sqlite3.connect(p).execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")])\n"
        ).format(base=str(BASE), copy=str(copy))
        rr = subprocess.run([str(BASE / ".venv/bin/python"), "-c", code], capture_output=True, text=True, cwd=str(BASE))
        out = (rr.stdout or "").strip().splitlines()
        ck("v1.4 代码读 v1.5 写过的库：messages 全在", rr.returncode == 0 and out and out[0].startswith("%d " % before), (rr.returncode, out, before, (rr.stderr or "")[-200:]))
        ck("v1.4 代码不碰 memory 表：表留着、写消息也正常", len(out) > 2 and "memory" in out[2] and rr.returncode == 0, out)
    else:
        ck("v1.4 读 v1.5 库（缺 /tmp 活库）", False, "LIVE_DB 不存在")
else:
    ck("行数 1108（v1.5 落盘）", 1100 <= lines <= 1118, lines)
    ck("记忆编解码在（V6）", "def encode_memory(steps) -> str:" in src and "def decode_memory(blob) -> list:" in src and 'MEM_FMT = "v1"' in src)
    ck("memory 表与读写方法在（V6）", "CREATE TABLE IF NOT EXISTS memory" in src and "def save_memory" in src and "def load_memory" in src)
    ck("_bind_memory 未命中就回灌（V6）", "decode_memory(self.hist.load_memory(sid))" in src and "mem.steps.extend(steps)" in src)
    ck("收尾把记忆落库（V6）", "self.hist.save_memory(sid, encode_memory(mem.steps))" in src)
    ck("落库有会话归属判据（V6）", "if mem is not None and self._mem_sid == sid:" in src)
    ck("D7 已修：轮次取消号是类级", "_run_seq: int = 0" in src and "_cancelled_before: int = 0" in src)
    ck("D7 已修：入队与判停在同一个临界区", "if OpsUI._run_seq <= OpsUI._cancelled_before:\n                ap.decide(\"cancelled\")" in src)
    ck("D7 已修：_stop 先领取消号", "OpsUI._cancelled_before = OpsUI._run_seq" in src)
    ck("D7 已修：开跑先领号", "OpsUI._run_seq += 1" in src)
    ck("D5/V5/D6 与审批闸没被碰坏", all(k in src for k in ("base = self.hist.load(sid)", "_bind_memory", "CASE WHEN title = '新会话'", "GATED_TOOLS", "_step_card")))

print("=== v15_rollback_check 方向:", want, "| my_ui.py", lines, "行 ===")
bad = 0
for name, okk, detail in res:
    print(("PASS  " if okk else "FAIL  ") + name + ("" if okk else "   <<< " + str(detail)[:300]))
    bad += 0 if okk else 1
print("FAILS:", bad if bad else "无")
sys.exit(1 if bad else 0)
