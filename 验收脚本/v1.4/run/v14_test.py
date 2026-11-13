# -*- coding: utf-8 -*-
"""v1.4 离线断言：D5 连问累加 + V5 会话级记忆隔离。

不打网络：把 OpsUI._stream_response 换成一个假生成器，它按真实契约做两件事
（往 agent.memory 追加 TaskStep/ActionStep、yield 一列 assistant 消息），
剩下的全走真代码。数据库换到临时文件，别碰 .agent-history.sqlite3。
"""
import dataclasses
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
TMP = Path(tempfile.mkdtemp(prefix="v14-"))

import gradio as gr  # noqa: E402

import my_ui  # noqa: E402

my_ui.DB_PATH = TMP / "hist.sqlite3"

from smolagents.memory import ActionStep, AgentMemory, TaskStep  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

FAILS = []


def ck(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "  <<< " + str(detail)))
    if not cond:
        FAILS.append(name)


# 每题的 token 数固定，便于验「本题累计」边界
TOKENS = {"第一题": (100, 7), "第二题": (200, 11), "第三题": (300, 13), "第四题": (400, 17)}


def fake_stream(self, message, history):  # noqa: ARG001
    text = message if isinstance(message, str) else (message or {}).get("text", "")
    tin, tout = TOKENS.get(text, (1, 1))
    mem = self.agent.memory
    mem.steps.append(TaskStep(task=text))
    mem.steps.append(
        ActionStep(
            step_number=1,
            timing=Timing(start_time=1.0, end_time=2.0),
            observations="ok",
            token_usage=TokenUsage(input_tokens=tin, output_tokens=tout),
        )
    )
    yield [
        gr.ChatMessage(role="assistant", content=f"card:{text}"),
        gr.ChatMessage(role="assistant", content=f"ans:{text}", metadata={"title": "t", "status": "done"}),
    ]


my_ui.OpsUI._stream_response = fake_stream


def ask(ui, text, sid):
    """跑一轮 _respond，返回 (最后一屏的消息列表, 最后一轮的状态 html, 新的 sid)。"""
    out = None
    for tup in ui._respond(text, sid):
        out = tup
    msgs, status_html, radio_upd, box_upd, new_sid, a, d = out
    return list(msgs), status_html, new_sid


ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")

# ---- 0) 起点：干净库 --------------------------------------------------------
ck("0a 临时库生效", str(ui.hist.path) == str(my_ui.DB_PATH), ui.hist.path)
ck("0b 空库无会话", ui.hist.choices() == [])
ck("0c 空库时 _on_load 交出 None sid", ui._on_load()[1] is None)
ck("0d GradioUI 默认 reset=False（换引用才有效）", ui.reset_agent_memory is False)
mon0 = ui.agent.monitor
mon_cnt0 = mon0.get_total_token_counts()

# ---- 1) D5：同一 sid 连问两题，前一题不再消失 -------------------------------
m1, h1, s1 = ask(ui, "第一题", None)
ck("1a 第一题落进会话", s1 is not None and [m.content for m in m1] == ["第一题", "card:第一题", "ans:第一题"], m1)
m2, h2, s2 = ask(ui, "第二题", s1)
ck("1b 第二题仍是同一条会话", s2 == s1, (s2, s1))
got = [m.content for m in m2]
ck("1c 屏上两题都在、顺序对", got == ["第一题", "card:第一题", "ans:第一题", "第二题", "card:第二题", "ans:第二题"], got)
db = [m.content for m in ui.hist.load(int(s1))]
ck("1d 库里也是两题（save 覆盖=追加）", db == got, db)
rows = sqlite3.connect(str(ui.hist.path)).execute(
    "SELECT ord, role FROM messages WHERE session_id=? ORDER BY ord", (int(s1),)
).fetchall()
ck("1e ord 连续无空洞", [r[0] for r in rows] == list(range(6)) and rows[0][1] == "user", rows)
ck("1f 会话数 1、标题仍是第一题", len(ui.hist.choices()) == 1 and ui.hist.choices()[0][0].startswith("第一题"), ui.hist.choices())
ck("1g 状态收尾「完成」", "完成" in h2, h2)

# ---- 2) V5：记忆按会话各存一份 ---------------------------------------------
mem_s1 = ui.agent.memory
ck("2a 记忆按 sid 缓存", ui._mem.get(int(s1)) is mem_s1 and ui._mem_sid == int(s1), ui._mem)
ck("2b 同会话两题都在一份记忆里（真多轮）", [s.task for s in mem_s1.steps if isinstance(s, TaskStep)] == ["第一题", "第二题"], mem_s1.steps)
ui._bind_memory(int(s1))
ck("2c 重复绑定不换对象（幂等）", ui.agent.memory is mem_s1 and len(ui._mem) == 1)

new_sid, chatbot_upd, status_upd, radio_upd = ui._new_session()
m3, h3, s3 = ask(ui, "第三题", new_sid)
ck("2d 新会话另开一条", s3 != s1 and len(ui.hist.choices()) == 2, (s3, s1))
mem_s3 = ui.agent.memory
ck("2e 新会话是另一份 AgentMemory", mem_s3 is not mem_s1 and isinstance(mem_s3, AgentMemory))
ck("2f 新会话只记得自己（旧题一步都没混进来）", [s.task for s in mem_s3.steps if isinstance(s, TaskStep)] == ["第三题"], mem_s3.steps)
ck("2g 旧会话的记忆没被新会话改写", [s.task for s in mem_s1.steps if isinstance(s, TaskStep)] == ["第一题", "第二题"])
ck("2h 旧会话屏上仍是两题", [m.content for m in ui.hist.load(int(s1))] == got)
ck("2i 缓存里两份、按 sid 索引", set(ui._mem) == {int(s1), int(s3)} and ui._mem_sid == int(s3), ui._mem)

# ---- 3) V5：点旧会话能接着聊 -----------------------------------------------
msgs_sel, status_sel, sid_out = ui._select_session(str(s1))
ck("3a _select_session 交出三个值且带 int sid", sid_out == int(s1) and isinstance(sid_out, int), sid_out)
ck("3b 屏上换回旧会话的两题", [m.content for m in msgs_sel] == got, msgs_sel)
m4, h4, s4 = ask(ui, "第四题", sid_out)
ck("3c 提问落进刚选中的旧会话", s4 == s1 and len(ui.hist.choices()) == 2)
ck("3d 记忆接上了旧话题", ui.agent.memory is mem_s1 and [s.task for s in mem_s1.steps if isinstance(s, TaskStep)] == ["第一题", "第二题", "第四题"], mem_s1.steps)
ck("3e 另一条会话不受影响", [s.task for s in mem_s3.steps if isinstance(s, TaskStep)] == ["第三题"])
ck("3f 屏上四题里这条会话的三问全在", [m.content for m in m4] == got + ["第四题", "card:第四题", "ans:第四题"], [m.content for m in m4])

# ---- 4) 口径：本题累计 / 步数 / 进程累计 ------------------------------------
st = ui._stats()
ck("4a 本题累计只算最后一问（记忆变多也没串）", (st["task_in"], st["task_out"]) == (400, 17), st)
ck("4b 步号每题从 1 起（框架 _run_stream 的口径）", st["step_no"] == 1, st["step_no"])
ck("4c 进程累计仍来自 monitor、没被我们清", ui.agent.monitor is mon0 and st["mon_in"] == mon_cnt0.input_tokens, (st["mon_in"], mon_cnt0))
ck("4d 未绑定的 sid 也能建记忆（系统提示词带上）", AgentMemory(my_ui.agent.system_prompt).system_prompt.system_prompt == my_ui.agent.system_prompt)

# ---- 5) 交付形态：接线没接错 -----------------------------------------------
demo = ui.create_app()
ck("5a create_app 仍是 Blocks", isinstance(demo, gr.Blocks))
fns = list(getattr(demo, "fns", {}).values())
by_fn = {}
for entry in fns:
    fn = getattr(entry, "fn", None) or getattr(entry, "preprocessed_fn", None)
    by_fn.setdefault(getattr(fn, "__name__", "?"), entry)
sel = by_fn.get("_select_session")
ck("5b radio.change 输出 3 个（chatbot/status/sid）", sel is not None and len(sel.outputs) == 3, None if sel is None else len(sel.outputs))
respond = by_fn.get("_respond")
ck("5c box.submit 仍交 7 元组", respond is not None and len(respond.outputs) == 7, None if respond is None else len(respond.outputs))
load_fn = by_fn.get("_on_load")
ck("5d demo.load 挂着 _on_load 方法（闭包已提出来可测）", load_fn is not None and len(load_fn.outputs) == 4)
ck("5e 审批闸仍在（v1.3 没被碰坏）", sum(1 for t in ("write_file", "run_python") if ui.agent.tools[t].forward.__dict__.get("_opsui_gated") or getattr(ui.agent.tools[t], "_opsui_gated", False)) == 2)
ui2 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ck("5f 第二个实例不重复套娃", ui2.agent.tools["run_python"] is ui.agent.tools["run_python"])
ck("5g 停止/审批卡片函数都还在", all(hasattr(my_ui.OpsUI, n) for n in ("_step_card", "_approval_card", "_settle_all", "_worker")))

# ---- 6) 显示层回归：metadata.status 只能是 pending/done --------------------
bad = []
for m in ui.hist.load(int(s1)):
    md = m.metadata or {}
    if "status" in md and md["status"] not in ("pending", "done"):
        bad.append(md)
ck("6a 库里每条消息的 status 合法（D4 没回潮）", not bad, bad)

# ---- 7) 刷新页面这条路径（D5 的另一半） ------------------------------------
upd, sid_load, status_load, msgs_load = ui._on_load()
ck("7a 重载后 sid 指向最近一条会话", sid_load == int(s1), (sid_load, s1))
ck("7b 重载后屏上是那条会话的全部三问", [m.content for m in msgs_load][-3:] == ["第四题", "card:第四题", "ans:第四题"], [m.content for m in msgs_load])
m5, h5, s5 = ask(ui, "第二题", sid_load)
ck("7c 刷新后接着问不会另开一条", s5 == s1 and len(ui.hist.choices()) == 2)

# ---- 8) D6：updated_at 每次都刷、标题不被后题改掉 ---------------------------
s_a = ask(ui, "第一题", None)[2]  # 又开一条（sid=None）
s_b = ask(ui, "第一题", None)[2]
ck("8a 两条新会话", s_a != s_b and int(s_b) > int(s_a), (s_a, s_b))
ck("8b 最新动作的那条排第一", ui.hist.choices()[0][1] == str(s_b), ui.hist.choices())
ask(ui, "第二题", s_a)
ck("8c 老会话一有动作就回到第一（v1.2 的 WHERE 条件会漏刷）", ui.hist.choices()[0][1] == str(s_a), ui.hist.choices())
t_a = ui.hist.choices()[0][0]
ask(ui, "第四题", s_a)
ck("8d 后续问题不改标题", ui.hist.choices()[0][0] == t_a == "第一题", (ui.hist.choices()[0][0], t_a))
s_c = ui.hist.ensure(None)
ui.hist.save(s_c, [])
titles = [t for t, i in ui.hist.choices() if i == str(s_c)]
ck("8e 空列表 save 不会把标题写成 NULL", titles == ["新会话"], titles)

# ---- 9) 停止/报错路径在「已有历史」的会话里也不能吞掉前几轮 ------------------
from smolagents import AgentError  # noqa: E402


def half_stream(self, message, history):  # noqa: ARG001
    text = message if isinstance(message, str) else (message or {}).get("text", "")
    self.agent.memory.steps.append(TaskStep(task=text))
    yield [gr.ChatMessage(role="assistant", content=f"card:{text}")]
    raise AgentError("打断", ui.agent.logger)


my_ui.OpsUI._stream_response = half_stream
before9 = [m.content for m in ui.hist.load(int(s1))]
m9, h9, s9 = ask(ui, "第三题", s1)
after9 = [m.content for m in ui.hist.load(int(s9))]
ck("9a 半截也落库、且前几轮还在", after9 == before9 + ["第三题", "card:第三题"] + [after9[-1]] and after9[: len(before9)] == before9, after9[-2:])
ck("9b 停止收尾气泡带 ⏹ 且 status=done", after9[-1].startswith("⏹ AgentError")
   and (([m.metadata for m in ui.hist.load(int(s9))][-1] or {}).get("status") == "done"), after9[-1])
ck("9c 状态档=已停止", "已停止" in h9, h9)
ck("9d sid 不变（还在同一条会话）", s9 == s1)
ck("9e 记忆里这条只多了半截（TaskStep 进了、ActionStep 没进）", [s.task for s in ui.agent.memory.steps if isinstance(s, TaskStep)][-1] == "第三题")


def boom_stream(self, message, history):  # noqa: ARG001
    raise AgentError("一步都没跑", ui.agent.logger)
    yield  # noqa: B018 —— 让它成为生成器


my_ui.OpsUI._stream_response = boom_stream
m10, h10, s10 = ask(ui, "第四题", s1)
after10 = [m.content for m in ui.hist.load(int(s10))]
ck("10a 一步没跑也不吞历史", after10[: len(before9)] == before9 and after10[-2] == "第四题" and after10[-1].startswith("⏹ AgentError"), after10[-2:])
ck("10b 状态档=已停止", "已停止" in h10, h10)

print()
print("DB:", ui.hist.path)
print("sessions:", ui.hist.choices())
print("mem cache keys:", sorted(ui._mem), "| bound:", ui._mem_sid)
print("FAILS:", FAILS if FAILS else "无")
sys.exit(1 if FAILS else 0)
