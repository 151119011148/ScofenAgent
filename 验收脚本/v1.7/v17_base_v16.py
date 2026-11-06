# -*- coding: utf-8 -*-
"""v1.7 第①步的**留痕复跑**：V9 基线——但这份跑的是 `.rollback/v1.6/my_ui.py`（改动前那份）。

上线之后真实库里已经多了一条 v2 payload，原样重跑会把「缺口复现」跑成「缺口已关」，
所以这一份把被测模块换成归档的 v1.6：A/B/C/D/E 问的都是**改动前**的代码，
数字才配写进 §4 当基线证据。

要回答四个问题，每个都拿真代码跑：
A 现在这一格等待到底存没存进库？
B 重启（同库第二个 OpsUI）回灌之后，_stats 的 task_wait 能不能算出来？
C 「点旧会话」这条路会不会把那条会话的记忆装进 agent.memory？状态条此刻报的是谁的数？
D 只要把等待挂回 step 对象，界面那三处（pill / 步骤卡 / 累计行）是不是零改动就能显示？
E 升 MEM_FMT 的代价：今天 decode_memory 见 fmt 不符就整块读空——拿真实库里的 payload 演。
"""
import importlib.util as ilu
import json
import pathlib
import shutil
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
TMP = pathlib.Path(tempfile.mkdtemp(prefix="v17-"))

import gradio as gr  # noqa: E402

spec_v16 = ilu.spec_from_file_location("my_ui", "/Users/gaoying/Desktop/study/ai学习/.rollback/v1.6/my_ui.py")
my_ui = ilu.module_from_spec(spec_v16)
sys.modules["my_ui"] = my_ui
spec_v16.loader.exec_module(my_ui)
assert my_ui.MEM_FMT == "v1", my_ui.MEM_FMT

REAL_STREAM = my_ui.OpsUI._stream_response
FAILS = []


def ck(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   <<< " + str(detail)[:400]))
    if not cond:
        FAILS.append(name)


def show(name, val):
    print("      %s: %s" % (name, val))


# ============ A/B/D：真 _stream_response + 假 agent.run（闸、队列、记账、落库全是真的）============
my_ui.DB_PATH = TMP / "hist.sqlite3"
GATE = {"wait": 0.6}


UIREF = {"ui": None}


def fake_run_v1(task, images=None, stream=True, reset=False):  # noqa: ARG001
    """演**真的** agent.run(stream=True) 的契约：yield 的是步骤对象，不是 ChatMessage。

    这样闸、队列、_stream_response 的领账（:876-880）、卡片、落库全是真代码，
    只有模型那一边是假的。
    """
    mem = my_ui.agent.memory
    mem.steps.append(my_ui.TaskStep(task=task))
    from smolagents.memory import ActionStep, FinalAnswerStep, ToolCall
    from smolagents.monitoring import Timing, TokenUsage

    t0 = time.time()
    th = threading.Thread(target=lambda: (time.sleep(GATE["wait"]),
                                         [ap.decide("allowed") for ap in UIREF["ui"]._pending_snapshot()]))
    th.start()
    # 直接调 gated 后的工具实例：走 _gated_call，等闸 -> 攒 OpsUI._pending_wait
    obs = my_ui.agent.tools["run_python"](code="print(7*7)")
    th.join()
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=t0, end_time=time.time()),
        tool_calls=[ToolCall(name="run_python", arguments={"code": "print(7*7)"}, id="call_v9")],
        observations=str(obs),
        token_usage=TokenUsage(input_tokens=2349, output_tokens=22),
    )
    mem.steps.append(step)
    yield step
    yield FinalAnswerStep(output="49")


def ask(ui, text, sid):
    last = None
    for tup in ui._respond({"text": text}, sid):
        last = tup
    return last


my_ui.agent.run = fake_run_v1
ui1 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
UIREF["ui"] = ui1
ui1._new_session()
frame = ask(ui1, "V9 基线：把 7*7 打出来", None)
sid1 = frame[4]
status = frame[1]
pill = "本题审批" in status
wait_in_frame = ui1._stats()["task_wait"]
show("A 落库前：进程内这一格的 task_wait", round(wait_in_frame, 2))
ck("A1 本题审批 pill 在活进程里看得见", pill and wait_in_frame >= 0.5, status[:220])

payload = sqlite3.connect(str(my_ui.DB_PATH)).execute(
    "select payload from memory where session_id=?", (int(sid1),)).fetchone()[0]
show("A2 payload 里出现过的键", sorted({k for row in json.loads(payload)["steps"] for k in row}))
ck("A3 等待**没有**进库（这就是 V9 要关的缺口）",
   not any(("wait" in k or "_w" == k) for row in json.loads(payload)["steps"] for k in row),
   payload[:200])
ck("A4 fmt 仍是 v1", json.loads(payload)["fmt"] == "v1")
wait_secs = round(wait_in_frame, 3)

# ---- B：同库第二个 OpsUI（模拟重启）----
my_ui.agent.memory = my_ui.AgentMemory(my_ui.agent.system_prompt)
ui2 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ui2._bind_memory(int(sid1))
back_stats = ui2._stats()
show("B 重启回灌后：steps 类型", [type(s).__name__ for s in my_ui.agent.memory.steps])
show("B task_wait / task_secs", (round(back_stats["task_wait"], 2), round(back_stats["task_secs"], 2)))
ck("B1 回灌能读出本题耗时（V6 的口径在）", back_stats["task_secs"] > 0, back_stats)
ck("B2 但「本题审批」读不出来＝0（缺口复现）", back_stats["task_wait"] == 0.0, back_stats["task_wait"])
n_text = sqlite3.connect(str(my_ui.DB_PATH)).execute(
    "select count(*) from messages where session_id=? and content like '%含审批%'", (int(sid1),)).fetchone()[0]
show("B 库里消息条数 / 含「含审批」的条数",
    (sqlite3.connect(str(my_ui.DB_PATH)).execute("select count(*) from messages where session_id=?", (int(sid1),)).fetchone()[0], n_text))
ck("B3 屏上那张历史卡反而带着文字（卡片正文走 messages 表，含审批那句重启后也在）", n_text >= 1)

# ---- D：只补"挂回 step 对象"这一手，界面零改动 ----
for s in my_ui.agent.memory.steps:
    if type(s).__name__ == "ActionStep":
        s._opsui_wait = wait_secs
d_stats = ui2._stats()
d_status = ui2._status_html("idle")
ck("D1 挂回去之后 pill 立刻读得出（不用改 _stats/_status_html）",
   d_stats["task_wait"] == round(wait_secs, 3) and "本题审批" in d_status, (d_stats["task_wait"], d_status[:200]))
card = ui2._step_card(my_ui.agent.memory.steps[-1])
ck("D2 步骤卡标题也能带这一格（_step_card 读的就是同一个属性）",
   "审批" in str(card.metadata.get("title")), card.metadata)

# ---- C：「点旧会话」到底会不会绑记忆 ----
my_ui.agent.memory = my_ui.AgentMemory(my_ui.agent.system_prompt)
ui3 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
sid_a = ask(ui3, "会话甲：把 7*7 打出来", None)[4]
mem_after_ask = my_ui.agent.memory
ui3._new_session()
sid_b = ask(ui3, "会话乙：随便一问", None)[4]
ck("C1 两条会话各有各的记忆（V5 在）",
   ui3._mem[int(sid_a)] is not ui3._mem[int(sid_b)])
my_ui.agent.memory = my_ui.AgentMemory(my_ui.agent.system_prompt)
before = my_ui.agent.memory
ui3._select_session(int(sid_a))
ck("C2 **点旧会话不回灌记忆**：agent.memory 还是空的那一份（_bind_memory 只在 _respond 开头）",
   my_ui.agent.memory is before and len(my_ui.agent.memory.steps) == 0,
   len(my_ui.agent.memory.steps))
status_a = ui3._status_html("idle")
show("C3 此刻状态条报的是谁的数（屏上已切到甲）", status_a[:170])

# ---- E：升 MEM_FMT 的代价，拿真实库里的 payload 演 ----
REAL = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/.agent-history.sqlite3")
sample = TMP / "real-copy.sqlite3"
shutil.copy(REAL, sample)
rows = [(sid, p) for sid, p in sqlite3.connect(str(sample)).execute("select session_id, payload from memory")]
v1rows = [(sid, p) for sid, p in rows if json.loads(p)["fmt"] == "v1"]
ck("E0 真实库里有 v1 时代的记忆行可当样本", len(v1rows) > 0, (len(v1rows), len(rows)))
old_fmt = my_ui.MEM_FMT
try:
    my_ui.MEM_FMT = "v2"
    readable = sum(1 for _, p in v1rows if my_ui.decode_memory(p))
    ck("E1 **只升版本号不做兼容读＝库里那几条 v1 旧账全体读空**（V6 当场作废）",
       readable == 0, "v2 strict 下那 %d 条 v1 还能读出 %d 条" % (len(v1rows), readable))
finally:
    my_ui.MEM_FMT = old_fmt
# 反面（这回不动 MEM_FMT，就问 v1.6 那份原样的代码）：v1.7 写进去的 v2 账它认不得 →
# 读回空。这就是**回滚之后**会发生的事：新会话还在侧栏、字还在，但模型那一边没记忆了。
v2rows = [(sid, p) for sid, p in rows if json.loads(p)["fmt"] == "v2"]
ck("E1b v1.6 原样的代码读 v1.7 写的 v2 账＝整块读空（回滚后的边界，要写进 §7）",
   bool(v2rows) and all(not my_ui.decode_memory(p) for _, p in v2rows),
   [(sid, len(my_ui.decode_memory(p))) for sid, p in v2rows])
sizes = [len(p) for _, p in rows]
show("E2 真实 payload 体积（字节）", sorted(sizes))
n_actions = sum(1 for _, p in rows for r in json.loads(p)["steps"] if r.get("_t") == "ActionStep")
show("E3 真实库里 ActionStep 条数 / 每格 wait 大约多写", (n_actions, len('"wait":21.0,') ))

print("\nTMP:", TMP)
print("FAILS:", FAILS or "无")
sys.exit(1 if FAILS else 0)
