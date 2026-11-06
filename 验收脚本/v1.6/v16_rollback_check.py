# -*- coding: utf-8 -*-
"""v1.6 回滚演练的断言侧：只做检查，拷贝由外层 bash 命令做（每步都能对上文件）。

用法：python v16_rollback_check.py v15|v16
方向 v15 = 已经拿 .rollback/v1.5 覆盖回来了，这一份里**不该**有 V7/V8，但 V6/D7 必须在；
方向 v16 = 已经拿 .rollback/v1.6 恢复回去，V7/V8 必须在，V6/D7 也必须在。
"""
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
RB = BASE.parent / ".rollback"
UI = BASE / "my_ui.py"
AGENT = BASE / "my_coding_agent.py"
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
# 字符数不是字节数（中文注释 3 字节 1 字符），并把「import 起来的正是磁盘上这一份」钉死。
ck("import 得起来（venv 3.13 + 真依赖），且就是这份文件",
   r.returncode == 0 and (r.stdout or "").strip() == str(len(src)),
   (r.returncode, (r.stdout or "").strip(), len(src), (r.stderr or "")[-200:]))

V6 = [
    ("记忆编解码在（V6）", "def encode_memory(steps) -> str:" in src and 'MEM_FMT = "v1"' in src),
    ("memory 表与读写方法在（V6）", "CREATE TABLE IF NOT EXISTS memory" in src and "def save_memory" in src),
    ("_bind_memory 未命中就回灌（V6）", "decode_memory(self.hist.load_memory(sid))" in src and "mem.steps.extend(steps)" in src),
    ("收尾把记忆落库（V6）", "self.hist.save_memory(sid, encode_memory(mem.steps))" in src),
    ("落库有会话归属判据（V6）", "if mem is not None and self._mem_sid == sid:" in src),
]
D7 = [
    ("D7：轮次取消号是类级", "_run_seq: int = 0" in src and "_cancelled_before: int = 0" in src),
    ("D7：入队与判停在同一个临界区", "if OpsUI._run_seq <= OpsUI._cancelled_before:\n                ap.decide(\"cancelled\")" in src),
    ("D7：_stop 先领取消号", "OpsUI._cancelled_before = OpsUI._run_seq" in src),
    ("D7：开跑先领号", "OpsUI._run_seq += 1" in src),
]
OLD = [
    ("D5 连问累加没被碰坏", "base = self.hist.load(sid)" in src and "last = base + [user_msg] + list(msgs)" in src),
    ("V5 会话级记忆隔离没被碰坏", "_mem: dict[int, AgentMemory]" in src and "_mem_sid" in src),
    ("D6 每次刷 updated_at 没被碰坏", "title = CASE WHEN title = '新会话' THEN ? ELSE title END" in src),
    ("v1.3 的审批闸与卡片没被碰坏", all(k in src for k in ("GATED_TOOLS", "_step_card", "_approval_card", "_install_gate"))),
]

if want == "v15":
    ck("行数 1,108（v1.5 落盘）", 1100 <= lines <= 1118, lines)
    # V7 未修形态：高亮还是跟着点击走，服务端不回写 value
    ck("没有 V7 的回写函数（_radio_update 不在）", "def _radio_update" not in src and "self._sid_shown" not in src)
    ck("没有 V7 的绑定镜像（_sid 只在 _bind_memory 的 _mem_sid 里）", "self._sid: str | None = None" not in src)
    ck("没有 V7 的守卫（_select_session 还是只挡空值）",
       "if not sid:\n            return gr.update(), gr.update(), gr.update()" in src
       and "str(sid) == self._sid" not in src)
    ck("新会话那一句不回写高亮（v1.5 的 bug 本体）",
       "return None, [], self._status_html(\"idle\"), gr.update(choices=self.hist.choices())" in src)
    # V8 未做形态：等待没有单列，审批卡结算后标题不带秒数
    ck("没有 V8 的账（_pending_wait / APPROVAL_WAIT_MIN 都不在）",
       "_pending_wait" not in src and "APPROVAL_WAIT_MIN" not in src)
    ck("没有 V8 的挂账（_opsui_wait 不在）", "_opsui_wait" not in src)
    ck("没有 V8 的口径（task_wait / 本题审批 pill 不在）", "task_wait" not in src and "本题审批" not in src)
    ck("Approval 不记等待秒数", "self.waited" not in src)
elif want == "v16":
    ck("行数 1,198~1,210（v1.6 落盘）", 1198 <= lines <= 1215, lines)
    # V7：checked 由 sid 单向驱动
    ck("V7：高亮跟着绑定走的那个函数在", "def _radio_update(self, force: bool = False):" in src)
    ck("V7：只在绑定真的换了时才带 value",
       "if force or self._sid_shown != self._sid:" in src and "return gr.update(choices=ch, value=self._sid)" in src)
    ck("V7：_respond 用的是它，不是裸 gr.update(choices=...)",
       "radio = self._radio_update" in src and "gr.update(choices=self.hist.choices())  # noqa" not in src)
    ck("V7：新会话把高亮清掉（不再留着上一条骗人）",
       "self._sid = None\n        return None, [], self._status_html(\"idle\"), self._radio_update()" in src)
    ck("V7：刷新页面会补那一下（force）", "self._radio_update(force=True)" in src)
    ck("V7：回声守卫挡在 int() 之前、且不动 chatbot",
       "if not sid or str(sid) == self._sid:\n            return gr.update(), gr.update(), gr.update()" in src)
    ck("V7：真切换时两个镜像一起更新", "self._sid_shown = self._sid" in src)
    # V8：等待单列
    ck("V8：Approval 在 decision 落定那一刻记等待",
       "self.waited = 0.0" in src and "self.waited = time.time() - self.created" in src
       and "self.waited = APPROVAL_TIMEOUT" in src)
    ck("V8：门把等待过账，且过门槛才记（毫秒级不算一格）",
       "if ap.waited >= APPROVAL_WAIT_MIN:\n                OpsUI._pending_wait += ap.waited" in src)
    ck("V8：ActionStep 到达时一次取干、挂到 step 上",
       "waited, OpsUI._pending_wait = OpsUI._pending_wait, 0.0" in src and "payload._opsui_wait = waited" in src)
    ck("V8：步骤卡标题单列那一格、总时长口径不动",
       'wait = getattr(step, "_opsui_wait", 0.0) or 0.0' in src and 'f" · 审批 {wait:.1f}s"' in src)
    ck("V8：卡片末行与状态条都跟着单列",
       '（含审批 {self._run_wait:.1f}s）' in src and '"task_wait": sum' in src and '("本题审批", f"{s[\'task_wait\']:.1f}s")' in src)
    ck("V8：审批卡结算后带「等了 X.Xs」", ' · 等了 {ap.waited:.1f}s' in src)
    ck("V8：换题开局把没领走的账清零", "OpsUI._pending_wait = 0.0" in src)
else:
    print("用法：python v16_rollback_check.py v15|v16")
    sys.exit(2)

for name, okk in V6 + D7 + OLD:
    ck(name + "（两个方向都必须在）", okk)

# my_coding_agent.py 本轮没动：两个方向都该和 v1.5 存档逐字节一致
for f, arch in ((UI, None), (AGENT, None)):
    pass
ck("my_coding_agent.py 与 v1.5 存档逐字节一致（本轮只动界面层）",
   (RB / "v1.5" / "my_coding_agent.py").read_bytes() == AGENT.read_bytes())

print("=== v16_rollback_check 方向:", want, "| my_ui.py", lines, "行 /", len(src), "字符 ===")
bad = 0
for name, okk, detail in res:
    print(("PASS  " if okk else "FAIL  ") + name + ("" if okk else "   <<< " + str(detail)[:300]))
    bad += 0 if okk else 1
print("FAILS:", bad if bad else "无")
sys.exit(1 if bad else 0)
