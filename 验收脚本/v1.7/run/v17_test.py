# -*- coding: utf-8 -*-
"""v1.7 离线断言：V9「本题审批」跨重启读得出 ＋ v1.6 / v1.5 全套回归。

不打网络、不打模型。手法沿用 v1.5 / v1.6：
- 编解码/落库/重启：把 OpsUI._stream_response 换成按真实契约做事的假生成器
  （往 agent.memory 追加 TaskStep/ActionStep、yield 一列 assistant 消息），其余走真代码。
- D7 / V8 / V9 端到端：反过来，用**真的** _stream_response，只把 agent.run 换成假的——
  闸、队列、轮询、卡片、记账、落库全是真的。
- V7：直接驱动事件函数，断言「交出去那一格 radio 的 value 是什么」；再用一条
  「浏览器回声」路径证明 _select_session 不会和流式生成器抢 chatbot 输出。
本轮新加的第七节里还多一手：把 .rollback/v1.6/my_ui.py 当**另一个模块**导进来，
拿 v1 的编码器现编一份，和 v2 的输出逐字比——「没等过的步不涨体积」这句话
不能只写在注释里。数据库一律临时目录，不碰 .agent-history.sqlite3。
"""
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
TMP = Path(tempfile.mkdtemp(prefix="v17-"))

import gradio as gr  # noqa: E402

import my_ui  # noqa: E402

my_ui.DB_PATH = TMP / "hist.sqlite3"

from smolagents import AgentError, AgentParsingError  # noqa: E402
from smolagents.memory import ActionStep, AgentMemory, PlanningStep, TaskStep, ToolCall  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

import faulthandler  # noqa: E402

FAILS = []
# v1.6 那一轮这套件的 5i 挂死过 100 秒以上（把 _stream_response 换回真版本、agent.run
# 却还是等闸的假版本，于是干等 APPROVAL_TIMEOUT=600s）。所以自带一个看门狗：
# 五分钟还没有结果就把所有线程的栈打出来再退出，别让人对着一个不动的终端猜。
faulthandler.dump_traceback_later(300, exit=True)


def ck(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "  <<< " + str(detail)[:400]))
    if not cond:
        FAILS.append(name)


def model_reads(mem):
    """把「模型下一轮读到的那一串」取出来比对：走的是框架自己的 write_memory_to_messages。

    直接改 agent.memory 的引用（_bind_memory 就是这么干的），读完还原。
    """
    ag = my_ui.agent
    old = ag.memory
    ag.memory = mem
    try:
        msgs = ag.write_memory_to_messages(summary_mode=False)
    finally:
        ag.memory = old
    return [(m.role, [p.get("text") for p in (m.content or []) if isinstance(p, dict) and p.get("type") == "text"]) for m in msgs]


def _mkmem(steps):
    m = AgentMemory(my_ui.agent.system_prompt)
    m.steps = list(steps)
    return m


REAL_STREAM = my_ui.OpsUI._stream_response

# =========================== 1) 编解码：存的是模型要读的那一串 =====================
mem = AgentMemory(my_ui.agent.system_prompt)
mem.steps = [
    TaskStep(task="请把数字 73 记住"),
    PlanningStep(
        model_input_messages=[],
        model_output_message=None,
        plan="先复述一遍，再交答案",
        timing=Timing(start_time=1.0, end_time=2.0),
        token_usage=TokenUsage(input_tokens=10, output_tokens=2),
    ),
    ActionStep(
        step_number=1,
        timing=Timing(start_time=2.0, end_time=3.0),
        tool_calls=[ToolCall(name="write_file", arguments={"path": "a.txt", "content": "73"}, id="call_1")],
        model_output="Thought: 我把它写下来\nFinal observation: 73",
        code_action='write_file(path="a.txt", content="73")',
        observations='{"ok": true, "n": 73}',  # 长得像 JSON 的观察值，故意用来抓 make_json_serializable 的坑
        action_output={"ok": True, "n": 73},
        token_usage=TokenUsage(input_tokens=120, output_tokens=15),
        is_final_answer=False,
    ),
    ActionStep(
        step_number=2,
        timing=Timing(start_time=3.0, end_time=4.0),
        error=AgentParsingError("解析失败：模型没按格式吐", my_ui.agent.logger),
        token_usage=TokenUsage(input_tokens=50, output_tokens=5),
    ),
]
blob = my_ui.encode_memory(mem.steps)
back = my_ui.decode_memory(blob)

ck("1a 四步都回来、类型一致", [type(s).__name__ for s in back] == ["TaskStep", "PlanningStep", "ActionStep", "ActionStep"], back)
ck("1b 恢复出的记忆和原记忆等长", len(back) == len(mem.steps))
ck("1c 观察值逐字保留（没被解析成 dict）", back[2].observations == '{"ok": true, "n": 73}', repr(back[2].observations))
ck("1d 文本字段原样：task/plan/model_output/code_action", [back[0].task, back[1].plan, back[2].model_output, back[2].code_action] == [mem.steps[0].task, mem.steps[1].plan, mem.steps[2].model_output, mem.steps[2].code_action])
ck("1e 工具调用还原成真 ToolCall（id/name/arguments 齐）", back[2].tool_calls and back[2].tool_calls[0].id == "call_1" and back[2].tool_calls[0].name == "write_file" and back[2].tool_calls[0].arguments == {"path": "a.txt", "content": "73"}, back[2].tool_calls)
err = back[3].error
ck("1f 报错步类型保住、str() 与 dict() 都对", type(err).__name__ == "AgentParsingError" and str(err) == "解析失败：模型没按格式吐" and err.dict() == {"type": "AgentParsingError", "message": "解析失败：模型没按格式吐"}, (type(err).__name__, getattr(err, "message", None)))
ck("1g 计时与 token 口径不丢（duration 是派生属性）", back[2].timing.duration == 1.0 and (back[2].token_usage.input_tokens, back[2].token_usage.output_tokens) == (120, 15) and back[2].token_usage.total_tokens == 135)
ck("1h is_final_answer 的 False 不被当成 None 丢掉", back[2].is_final_answer is False)
ck("1i 认不出的步类型跳过、不硬存", [s.task for s in my_ui.decode_memory(json.dumps({"fmt": "v1", "steps": [{"_t": "WhateverNewStep"}, {"_t": "TaskStep", "task": "还在"}]}))] == ["还在"])
ck("1j 坏数据一律当没记忆", my_ui.decode_memory(None) == [] and my_ui.decode_memory("{{{") == [] and my_ui.decode_memory('{"fmt":"v0","steps":[]}') == [] and my_ui.decode_memory('[1,2]') == [] and my_ui.decode_memory('{"fmt":"v1","steps":[null,3]}') == [])
BROKEN_ROW = '{"fmt":"v1","steps":[{"_t":"TaskStep","task":"好"},{"_t":"ActionStep","timing":{"start_time":"这不是数"}},{"_t":"TaskStep","task":"还好"}]}'
ck("1k 单条坏了只丢那一条（其余照旧）", [type(x).__name__ for x in my_ui.decode_memory(BROKEN_ROW)] == ["TaskStep", "TaskStep"], my_ui.decode_memory(BROKEN_ROW))
ck("1l 未知报错类型退回 AgentError", type(my_ui._decode_error({"type": "NoSuchError", "message": "x"})).__name__ == "AgentError")
ck("1m 空记忆编出来是空列表", my_ui.decode_memory(my_ui.encode_memory([])) == [])
_m2 = AgentMemory(my_ui.agent.system_prompt)
_m2.steps = back
ck("1n 模型读到的那一串：恢复后与恢复前逐字相同（框架自己的 write_memory_to_messages）", model_reads(mem) == model_reads(_m2), (len(model_reads(mem)), len(model_reads(_m2))))
ck("1o 那一串里确实带着题面与观察值（不是空比对）", any("请把数字 73 记住" in (t or "") for _, parts in model_reads(_m2) for t in parts) and any('{"ok": true, "n": 73}' in (t or "") for _, parts in model_reads(_m2) for t in parts), model_reads(_m2)[:2])
ck("1p 图片类字段不入库（本轮口径：只存文本）", "observations_images" not in blob and "task_images" not in blob)

# =========================== 2) 落库与重启 =====================
TOKENS = {"第一题": (100, 7), "第二题": (200, 11), "第三题": (300, 13), "第四题": (400, 17)}


def fake_stream(self, message, history):  # noqa: ARG001
    text = message if isinstance(message, str) else (message or {}).get("text", "")
    tin, tout = TOKENS.get(text, (1, 1))
    memx = self.agent.memory
    memx.steps.append(TaskStep(task=text))
    memx.steps.append(
        ActionStep(
            step_number=1,
            timing=Timing(start_time=1.0, end_time=2.0),
            observations=f"这是 {text} 的结果",
            token_usage=TokenUsage(input_tokens=tin, output_tokens=tout),
        )
    )
    yield [
        gr.ChatMessage(role="assistant", content=f"card:{text}"),
        gr.ChatMessage(role="assistant", content=f"ans:{text}", metadata={"title": "t", "status": "done"}),
    ]


my_ui.OpsUI._stream_response = fake_stream


def ask(ui, text, sid):
    out = None
    for tup in ui._respond(text, sid):
        out = tup
    return list(out[0]), out[1], out[4]


ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ck("2a 起点：库里没有会话", ui.hist.choices() == [] and ui._mem == {})
m1, h1, s1 = ask(ui, "第一题", None)
pay1 = ui.hist.load_memory(int(s1))
# v1.6 这条期望 fmt=="v1"；v1.7 立了 V9（ActionStep 多一格 wait），版本号升 v2，口径跟着改。
ck("2b 一问之后记忆落了库（v1.7 起 fmt 为 v2）", pay1 is not None and json.loads(pay1)["fmt"] == "v2", pay1)
ck("2b2 没等过审批的一题：payload 里没有 wait 这一格（不写 0，库里体积不涨）",
   '"wait"' not in pay1, pay1[:200])
st1 = my_ui.decode_memory(pay1)
ck("2c 存的就是那两步（Task+Action）", [type(s).__name__ for s in st1] == ["TaskStep", "ActionStep"], st1)
ck("2d 库里存的 observation 与模型看过的一致", st1[1].observations == "这是 第一题 的结果", st1[1].observations)
m2, h2, s2 = ask(ui, "第二题", s1)
st2 = my_ui.decode_memory(ui.hist.load_memory(int(s1)))
ck("2e 连问两题：同一 sid、记忆里四步都在", s2 == s1 and len(st2) == 4 and [s.task for s in st2 if isinstance(s, TaskStep)] == ["第一题", "第二题"], st2)
nrows = sqlite3.connect(str(ui.hist.path)).execute("SELECT count(*) FROM memory WHERE session_id=?", (int(s1),)).fetchone()[0]
ck("2f 一条会话一行（覆盖式，不是越问越多行）", nrows == 1, nrows)

# —— 重启：新进程 = 新 OpsUI，进程内一份记忆都没有 ——
uiB = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ck("2g 重启后进程内记忆是空的", uiB._mem == {} and uiB._mem_sid is None)
uiB._bind_memory(int(s1))
ck("2h 绑定时从库里把那一串读回来了", len(uiB._mem[int(s1)].steps) == 4 and [s.task for s in uiB._mem[int(s1)].steps if isinstance(s, TaskStep)] == ["第一题", "第二题"], uiB._mem)
ck("2i 模型那边接得上：重启后读到的那一串与重启前逐字相同", model_reads(uiB._mem[int(s1)]) == model_reads(ui._mem[int(s1)]), (len(model_reads(uiB._mem[int(s1)])), len(model_reads(ui._mem[int(s1)]))))
m3, h3, s3 = ask(uiB, "第三题", s1)
ck("2j 重启后接着问：屏上三问（D5 没回潮）", [x.content for x in m3] == ["第一题", "card:第一题", "ans:第一题", "第二题", "card:第二题", "ans:第二题", "第三题", "card:第三题", "ans:第三题"], [x.content for x in m3])
st3 = my_ui.decode_memory(uiB.hist.load_memory(int(s1)))
ck("2k 第三题也进了库（六步）", len(st3) == 6 and [s.task for s in st3 if isinstance(s, TaskStep)] == ["第一题", "第二题", "第三题"], st3)
sb = uiB._stats()
ck("2l 重启后「本题累计」的边界没漂（最后一个 TaskStep 之后，不是整段会话）", (sb["task_in"], sb["task_out"]) == (300, 13) and sb["step_no"] == 1, sb)

# —— 隔离没坏：新会话是另一段记忆，且各存各的行 ——
ns, cb_upd, st_upd, radio_upd = uiB._new_session()
m4, h4, s4 = ask(uiB, "第四题", ns)
ck("2m 新会话另开一条、记忆只有它自己", s4 != s1 and [s.task for s in my_ui.decode_memory(uiB.hist.load_memory(int(s4))) if isinstance(s, TaskStep)] == ["第四题"], (s4, s1))
ck("2n 旧会话那一行没被新会话盖掉", [s.task for s in my_ui.decode_memory(uiB.hist.load_memory(int(s1))) if isinstance(s, TaskStep)] == ["第一题", "第二题", "第三题"])
uiC = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
uiC._bind_memory(int(s4))
ck("2o 重启后点旧会话：读到的还是那条自己的（不串题）", [s.task for s in uiC._mem[int(s4)].steps if isinstance(s, TaskStep)] == ["第四题"], uiC._mem[int(s4)].steps)
ck("2p 库里两条会话两行记忆", sqlite3.connect(str(ui.hist.path)).execute("SELECT count(*) FROM memory").fetchone()[0] == 2)

# —— v1.4 的老会话：有 messages、没有 memory 行 ——
old_sid = uiC.hist.ensure(None)
uiC.hist.save(old_sid, [gr.ChatMessage(role="user", content="v1.4 时代攒下的旧会话"), gr.ChatMessage(role="assistant", content="答", metadata={"status": "done"})])
uiD = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
uiD._bind_memory(int(old_sid))
ck("2q 老会话（库里没记忆行）不崩、读出来是空", len(uiD._mem[int(old_sid)].steps) == 0, uiD._mem[int(old_sid)].steps)
ck("2r 老会话屏上的字照样读得出来（messages 表没动）", [x.content for x in uiD.hist.load(int(old_sid))] == ["v1.4 时代攒下的旧会话", "答"])
mo, ho, so = ask(uiD, "第五题", old_sid)
ck("2s 老会话第一次新问之后也有记忆行了", len(my_ui.decode_memory(uiD.hist.load_memory(int(old_sid)))) == 2, uiD.hist.load_memory(int(old_sid)))

# —— 表结构是加出来的：老库（无 memory 表）直接能用 ——
conn = sqlite3.connect(str(ui.hist.path))
conn.execute("DROP TABLE memory")
conn.execute("DELETE FROM sessions WHERE id=?", (int(s4),))
conn.commit()
conn.close()
hist2 = my_ui.History(ui.hist.path)
ck("2t 没有 memory 表的老库：重建出来、messages 不受影响", hist2.load_memory(int(s1)) is None and [x.content for x in hist2.load(int(s1))][0] == "第一题")
ck("2u 重建后写记忆仍然可用", hist2.save_memory(int(s1), blob) > 0 and my_ui.decode_memory(hist2.load_memory(int(s1)))[0].task == "请把数字 73 记住")

# —— 并发那一路：_mem_sid 不是本条会话时不写库（别把别人的记忆盖过来）——
real_bind = my_ui.OpsUI._bind_memory


def no_bind(self, sid):  # 模拟"这一题没绑上记忆"（并发时 _mem_sid 是别人的会话）
    return None


my_ui.OpsUI._bind_memory = no_bind
mx, hx, sx = ask(uiD, "第六题", None)
ck("2v 没绑定记忆的一题：屏上照常、库里不落记忆行", len(uiD.hist.load_memory(int(sx)) or "") == 0 and [x.content for x in mx][-1] == "ans:第六题", uiD.hist.load_memory(int(sx)))
my_ui.OpsUI._bind_memory = real_bind

# =========================== 3) D7：停止按在待批卡出现之前 =====================
calls = []


def orig_tool(code=""):  # 假「原工具」：被调到就说明副作用真的发生了
    calls.append(code)
    return "原工具跑完了"


def gate_in_thread(uix, kwargs):
    box = {}

    def run():
        t0 = time.time()
        box["obs"] = uix._gated_call("run_python", orig_tool, (), kwargs)
        box["secs"] = time.time() - t0

    th = threading.Thread(target=run, name="fake-worker")
    th.start()
    return th, box


OpsUI = my_ui.OpsUI
# 3a) v1.4 复现的那条：本轮已被标记停止 → 入队即按 cancelled 结算，不挂人
OpsUI._run_seq, OpsUI._cancelled_before = 10, 10
th, box = gate_in_thread(ui, {"code": "print(1)"})
th.join(3)
ck("3a 停止在先：闸不等点按钮就返回了（v1.4 这里是永远不返回）", not th.is_alive() and box.get("secs", 99) < 1.0, box)
ck("3b 交回模型的观察值 = 取消那一句", box.get("obs") == my_ui.DENIED_OBSERVATION["cancelled"], box.get("obs"))
ck("3c 原工具一次都没被调用（没有任何副作用）", calls == [], calls)
ck("3d 没留人：待批列表空、按钮不该亮", ui._unanswered() == [], [a.decision for a in OpsUI._pending])
ck("3d2 已结算的那条留在登记表里也不碍事：下一轮开局整体摘除", ui._unanswered() == [] and "self._pending.clear()" in Path(my_ui.__file__).read_text(encoding="utf-8"))

# 3e) 没标记时，闸照常等人点（不能被修成「问了也白问」）
OpsUI._run_seq, OpsUI._cancelled_before = 11, 10
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(2)"})
time.sleep(0.3)
ck("3e 未标记： worker 挂在闸上等审批（0.3s 后仍未返回）", th.is_alive() and len(ui._unanswered()) == 1, (th.is_alive(), len(ui._unanswered())))
ui._decide("allowed")
th.join(3)
ck("3f 点「允许」后照旧执行、观察值是工具的真返回", not th.is_alive() and calls == ["print(2)"] and box.get("obs") == "原工具跑完了", (calls, box))
ck("3g 允许之后待批清空", ui._unanswered() == [])

# 3h) 停止落在「卡已经出现之后」——v1.4 就好的那条对照组，别改坏
OpsUI._run_seq, OpsUI._cancelled_before = 12, 10
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(3)"})
time.sleep(0.3)
ui._stop()
th.join(3)
ck("3h 卡出现后按停止：立刻解开（对照组）", not th.is_alive() and box.get("secs", 99) < 1.5 and box.get("obs") == my_ui.DENIED_OBSERVATION["cancelled"], (th.is_alive(), box))
ck("3i 这一按也留了取消号：后续入队不会再挂", OpsUI._cancelled_before == 12, OpsUI._cancelled_before)

# 3j) 取消号不能污染下一轮（新 run 领了号就照常问人）
OpsUI._run_seq += 1  # 13 > _cancelled_before，等价于 _stream_response 开头那次领号
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(4)"})
time.sleep(0.3)
ck("3j 下一轮没被上一按的停止影响：仍等人审批", th.is_alive() and len(ui._unanswered()) == 1)
ui._decide("denied")
th.join(3)
ck("3k 拒绝路径没变（原工具没跑、观察值是拒绝那句）", calls == [] and box.get("obs") == my_ui.DENIED_OBSERVATION["denied"], (calls, box))

# 3l) 端到端：真的 _stream_response + 假 agent.run（0.6s 后调需审批工具），0.2s 时按停止
my_ui.OpsUI._stream_response = REAL_STREAM
from smolagents.memory import FinalAnswerStep  # noqa: E402

fake_state = {"tool_returned": None, "tool_at": None, "start": None}


def fake_run(task, images=None, stream=True, reset=False):  # noqa: ARG001
    ag = my_ui.agent
    fake_state["start"] = time.time()
    ag.memory.steps.append(TaskStep(task=task))
    time.sleep(0.6)  # 让模型"想"一会儿——这段时间里按停止就是 D7 那条路径
    obs = ag.tools["run_python"](code="print(73)")
    fake_state["tool_returned"] = obs
    fake_state["tool_at"] = time.time() - fake_state["start"]
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=time.time(), end_time=time.time()),
        observations=obs,
        token_usage=TokenUsage(input_tokens=111, output_tokens=2),
    )
    ag.memory.steps.append(step)
    yield step
    if ag.interrupt_switch:
        raise AgentError("用户已中断执行", ag.logger)
    yield FinalAnswerStep(output="完成")


my_ui.agent.run = fake_run
e_sid = ui.hist.ensure(None)
gen = ui._respond("把 73 打印出来", e_sid)
threading.Timer(0.2, ui._stop).start()
last = None
ended = None
t0 = time.time()
for tup in gen:
    last = tup
    if time.time() - t0 > 8:
        ended = "超时没结束"
        break
ck("3l 端到端：按停止后整条流在 3s 内自己结束（v1.4 是死停在等待审批）", ended is None and time.time() - t0 < 3.0, (ended, round(time.time() - t0, 2)))
ck("3m 工具那一步没执行、也没等人（观察值=取消那句）", fake_state["tool_returned"] == my_ui.DENIED_OBSERVATION["cancelled"] and fake_state["tool_at"] is not None and fake_state["tool_at"] < 1.0, fake_state)
ck("3n 收尾没有待批、状态不是「等待审批」", ui._unanswered() == [] and "等待审批" not in (last[1] or ""), (last[1] if last else None, len(ui._unanswered())))
ck("3o 半截照样落库、屏上有 ⏹ 那句", [x.content for x in ui.hist.load(int(e_sid))][-1].startswith("⏹ AgentError"), [x.content for x in ui.hist.load(int(e_sid))])
ck("3p 停止那一轮的半截进了记忆库（TaskStep 在、ActionStep 也在）", [type(s).__name__ for s in my_ui.decode_memory(ui.hist.load_memory(int(e_sid)))] == ["TaskStep", "ActionStep"], ui.hist.load_memory(int(e_sid)))

# =========================== 4) 回归：v1.3/v1.4 的口径没被碰坏 =====================
my_ui.OpsUI._stream_response = fake_stream
card = ui._step_card(
    ActionStep(
        step_number=1,
        timing=Timing(start_time=0.0, end_time=1.0),
        observations=my_ui.DENIED_OBSERVATION["cancelled"],
        token_usage=TokenUsage(input_tokens=1, output_tokens=1),
    )
)
ck("4a 步骤卡把「随停止取消」认成 ⚪ 已取消（不是 🟢 成功）", "⚪ 已取消" in card.metadata["title"], card.metadata["title"])
denied = ui._approval_card(my_ui.Approval("run_python", {"code": "x"}), 1.0)
allowed_ap = my_ui.Approval("run_python", {"code": "x"})
allowed_ap.decide("allowed")
ck("4b 审批卡三种状态的 status 仍是 pending/done", denied.metadata["status"] == "pending" and ui._approval_card(allowed_ap, 1.0).metadata["status"] == "done")
r1, h1b, s1b = ask(ui, "第一题", None)
ck("4c D5 累加仍在（新会话一问一答三条）", len(r1) == 3 and h1b and "完成" in h1b, (len(r1), h1b))
ck("4d 库里每条 status 合法（D4 没回潮）", all((getattr(x, "metadata", None) or {}).get("status") in (None, "pending", "done") for x in ui.hist.load(int(s1b))))
ui._sid = None  # v1.6：先假装绑在别处，这一次才算真切换
sel = ui._select_session(str(s1b))
ck("4e _select_session 仍交三个值、第三个是 int sid", len(sel) == 3 and sel[2] == int(s1b), sel[2])
ld = ui._on_load()
ck("4f _on_load 仍交四个值", len(ld) == 4)
my_ui.OpsUI._stream_response = REAL_STREAM
demo = ui.create_app()
by_fn = {}
for entry in list(getattr(demo, "fns", {}).values()):
    fn = getattr(entry, "fn", None) or getattr(entry, "preprocessed_fn", None)
    by_fn.setdefault(getattr(fn, "__name__", "?"), entry)
ck("4g 接线没变：submit 7 输出 / radio.change 3 输出 / load 4 输出", len(by_fn["_respond"].outputs) == 7 and len(by_fn["_select_session"].outputs) == 3 and len(by_fn["_on_load"].outputs) == 4)
ck("4h 审批闸仍在、没套成两层", getattr(my_ui.agent.tools["run_python"], "_opsui_gated", False) is True and str(my_ui.agent.tools["run_python"].forward)[:40].startswith("<function") and len([n for n in ("write_file", "run_python") if getattr(my_ui.agent.tools[n], "_opsui_gated", False)]) == 2)
uiE = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ck("4i 第二个实例不重复装门", uiE.agent.tools["run_python"] is my_ui.agent.tools["run_python"])
ck("4j 领号那一句确实在真 _stream_response 里", "OpsUI._run_seq += 1" in Path(my_ui.__file__).read_text(encoding="utf-8"))

# =========================== 5) V7：侧栏高亮跟着绑定走 =====================
# 4) 末尾为了验接线把真流式装回去了，5) 只验事件函数交出去的那一格，重新用假流式
# （假流式不碰 agent.run，也就不会撞上 3) 留下的那个"要等人审批"的假 run）。
my_ui.OpsUI._stream_response = fake_stream
ui7 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ld = ui7._on_load()
ck("5a _on_load 交出的 radio 带着 value，且就是 sid 那一格",
   "value" in ld[0] and ld[0]["value"] == str(ld[1]) and ui7._sid == str(ld[1]), (ld[0].get("value"), ld[1]))
ck("5b 刷新页面后不再是「绑着某条、侧栏一条都不亮」（v1.5 实测 chk 全 false）",
   bool(ld[1]) and ld[0]["value"] is not None, ld[0].get("value"))

sw = ui7._select_session("3")
ck("5c 点一条没亮过的会话：真切换，交回它自己的消息",
   len(sw) == 3 and sw[2] == 3 and sw[0] and ui7._sid == "3", (len(sw), sw[2], len(sw[0] or [])))
echo = ui7._select_session("3")
ck("5d 值没变的那一次（服务端设 value 的回声）三个输出全空、不抢 chatbot",
   all(isinstance(x, dict) and "value" not in x and "choices" not in x for x in echo), echo)
nxt = ui7._radio_update()
ck("5e 点过之后下一帧不必再回送 value（流式期间只刷 choices）", "value" not in nxt, sorted(nxt))

ns = ui7._new_session()
ck("5f 「＋ 新会话」把高亮清掉，而不是留着上一条骗人",
   "value" in ns[3] and ns[3]["value"] is None and ui7._sid is None, ns[3].get("value"))
again = ui7._select_session("3")
ck("5g 新会话之后点「刚才那条」是真切换（v1.5 这里是空点，问题落进新会话）",
   again[2] == 3 and again[0] and ui7._sid == "3", (again[2], len(again[0] or [])))
echo2 = ui7._select_session(None)
ck("5h value=None 的回声不崩（守卫挡在 int() 之前）",
   all(isinstance(x, dict) and "value" not in x for x in echo2), echo2)

frames = list(ui7._respond("第五节这题", None))
vals = [f[2] for f in frames if "value" in f[2]]
ck("5i 提问新建的那条会话当场被点亮", bool(vals) and vals[-1].get("value") == str(frames[-1][4]),
   (vals[-1].get("value") if vals else None, frames[-1][4]))
ck("5j 整题只回送一次 value（其余帧只刷 choices，不给 gradio 每秒空转两次事件）",
   len(vals) == 1, len(vals))

# =========================== 6) V8：审批等待时长单列 =====================
my_ui.OpsUI._stream_response = REAL_STREAM
ap6 = my_ui.Approval("run_python", {"code": "print(1)"})
time.sleep(0.3)
ap6.decide("allowed")
ck("6a 等待秒数在 decision 落定那一刻就记好（卡片第一次画收尾状态就带得上）",
   0.15 <= ap6.waited <= 1.5 and ap6.decision == "allowed", ap6.waited)
ap6b = my_ui.Approval("run_python", {"code": "x"})
old_to = my_ui.APPROVAL_TIMEOUT
my_ui.APPROVAL_TIMEOUT = 0.3
t0 = time.time()
d6b = ap6b.wait()
my_ui.APPROVAL_TIMEOUT = old_to
ck("6b 超时路径也记等待（记的是门槛那一格，不是现场时钟）",
   d6b == "timeout" and ap6b.waited == 0.3 and abs((time.time() - t0) - 0.3) < 0.2, (d6b, ap6b.waited))

OpsUI._run_seq, OpsUI._cancelled_before = 20, 10
with OpsUI._gate_lock:
    OpsUI._pending.clear()
OpsUI._pending_wait = 0.0
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(8)"})
time.sleep(0.4)
ui._decide("allowed")
th.join(3)
ck("6c 门结算完把这一格等待过账（等下一个到达的 ActionStep 领走）",
   OpsUI._pending_wait >= 0.3, OpsUI._pending_wait)

OpsUI._run_seq, OpsUI._cancelled_before = 21, 21
with OpsUI._gate_lock:
    OpsUI._pending.clear()
OpsUI._pending_wait = 0.0
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(9)"})
th.join(3)
ck("6d 入队即按取消：毫秒级的那点等待根本不过账（交付形态实测抓到过「审批 0.0s」这种噪声）",
   OpsUI._pending_wait == 0.0, OpsUI._pending_wait)
ap6d = my_ui.Approval("run_python", {"code": "x"})
ap6d.decide("cancelled")  # waited ≈ 0.0004s
ck("6p 审批卡同一条门槛：没等人就别写「等了 0.0s」",
   "等了" not in ui._approval_card(ap6d, 0.0).metadata["title"], ui._approval_card(ap6d, 0.0).metadata["title"])
ap6e = my_ui.Approval("run_python", {"code": "x"})
ap6e.created -= 7.0
ap6e.decide("denied")
ck("6q 真等了 7 秒的（被拒绝也一样）要写出「等了 7.0s」",
   "等了 7.0s" in ui._approval_card(ap6e, 7.0).metadata["title"], ui._approval_card(ap6e, 7.0).metadata["title"])

state6 = {"returned": None}


def fake_run_wait(task, images=None, stream=True, reset=False):  # noqa: ARG001
    ag = my_ui.agent
    ag.memory.steps.append(TaskStep(task=task))
    time.sleep(0.2)
    t0 = time.time()
    obs = ag.tools["run_python"](code="print(73)")  # 卡在这里等人点「允许」
    state6["returned"] = obs
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=t0, end_time=time.time()),
        observations=obs,
        token_usage=TokenUsage(input_tokens=111, output_tokens=2),
        code_action="print(73)",
        tool_calls=[ToolCall(id="call_9", name="run_python", arguments={"code": "print(73)"})],
    )
    ag.memory.steps.append(step)
    yield step
    yield FinalAnswerStep(output="完成")


my_ui.agent.run = fake_run_wait
ui8 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
sid8 = ui8.hist.ensure(None)
OpsUI._pending_wait = 0.0
def approve_when_seen():
    # 不用固定延时：worker 线程先要起起来、模型要"想" 0.2 秒，闸才把单子挂上。
    # 按死的 0.5 秒点空了一次，这条流就要干等到 APPROVAL_TIMEOUT（600s）才算超时。
    for _ in range(200):
        if ui8._unanswered():
            time.sleep(0.5)  # 真的等半秒：这一格等待就是要被单列出来的那个数
            ui8._decide("allowed")
            return
        time.sleep(0.05)


threading.Thread(target=approve_when_seen, name="fake-click", daemon=True).start()
frames8 = list(ui8._respond("把 73 打印出来", sid8))
last8 = frames8[-1]
step_cards = [m for m in last8[0] if (m.metadata or {}).get("title", "").startswith("🛠")]
appr_cards = [m for m in last8[0] if "待批" in (m.metadata or {}).get("title", "")]
ck("6e 端到端：等了 0.5 秒的审批点了「允许」，工具就真跑了（观察值是 run_python 的返回）",
   "exit=0" in (state6["returned"] or "") and "73" in (state6["returned"] or ""), state6["returned"])
ck("6f 步骤卡标题多出「审批 X.Xs」这一格（总时长那格口径不变）",
   bool(step_cards) and "审批 " in step_cards[-1].metadata["title"],
   step_cards[-1].metadata["title"] if step_cards else None)
import re
title6 = step_cards[-1].metadata["title"] if step_cards else ""
m6 = re.search(r"· ([\d.]+)s · 审批 ([\d.]+)s", title6)
ck("6g 标题里两格并存：总时长（框架口径不变）在前、审批等待单列在后，且后者 <= 前者",
   m6 and float(m6.group(2)) >= 0.3 and float(m6.group(1)) >= float(m6.group(2)), title6)
ck("6h 正文末行「本题累计」写明含审批多少", bool(step_cards) and "（含审批" in step_cards[-1].content,
   step_cards[-1].content[-160:] if step_cards else None)
ck("6i 审批卡结算后标题带着「等了 X.Xs」", bool(appr_cards) and "等了 " in appr_cards[-1].metadata["title"],
   appr_cards[-1].metadata["title"] if appr_cards else None)
ck("6j 状态条多出「本题审批」那一格", "本题审批" in (last8[1] or ""), (last8[1] or "")[:200])
w6 = next((getattr(s, "_opsui_wait", 0.0) for s in reversed(my_ui.agent.memory.steps)
           if isinstance(s, ActionStep) and getattr(s, "_opsui_wait", 0.0)), 0.0)
ck("6k 等待挂到了那个 step 对象上、_run_wait 也累加了", w6 >= 0.3 and ui8._run_wait >= 0.3, (w6, ui8._run_wait))


def fake_run_plain(task, images=None, stream=True, reset=False):  # noqa: ARG001
    ag = my_ui.agent
    ag.memory.steps.append(TaskStep(task=task))
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=time.time(), end_time=time.time() + 1.0),
        observations="没有工具调用",
        token_usage=TokenUsage(input_tokens=10, output_tokens=1),
    )
    ag.memory.steps.append(step)
    yield step
    yield FinalAnswerStep(output="完成")


my_ui.agent.run = fake_run_plain
OpsUI._pending_wait = 7.7  # 上一题没被领走的账，开局必须清掉
sid9 = ui8.hist.ensure(None)
frames9 = list(ui8._respond("第六节第二题", sid9))
last9 = frames9[-1]
card9 = [m for m in last9[0] if (m.metadata or {}).get("title", "").startswith("🛠")][-1]
ck("6l 没有审批的一题：标题/正文/状态条都不多出那一格",
   "审批" not in card9.metadata["title"] and "含审批" not in card9.content and "本题审批" not in (last9[1] or ""),
   card9.metadata["title"])
ck("6m 换题开局把上一题没领走的账清零（7.7s 不会漂到新题头上）",
   OpsUI._pending_wait == 0.0 and ui8._run_wait == 0.0, (OpsUI._pending_wait, ui8._run_wait))

st6 = my_ui.ActionStep(step_number=1, timing=Timing(start_time=0.0, end_time=1.0),
                       observations="x", token_usage=TokenUsage(input_tokens=1, output_tokens=1))
st6._opsui_wait = 9.9
blob6 = my_ui.encode_memory([st6])
back6 = my_ui.decode_memory(blob6)
# 6n 在 v1.6 记的是「本轮边界：等待不进库」；v1.7（V9）把它写进库了，口径翻过来。
ck("6n V9 翻转：等待那一格跟着记忆进库（键名是 wait，不是私有属性名），回灌挂回同一个属性",
   '"wait": 9.9' in blob6 and getattr(back6[0], "_opsui_wait", 0.0) == 9.9 and "_opsui_wait" not in blob6,
   blob6[:220])
ck("6o 但总时长照旧进得去（V6 的口径没被 V8 碰坏）", back6[0].timing.duration == 1.0, back6[0].timing.duration)


# =========================== 7) V9：等待进库 + 兼容读旧 payload + 跨重启看得见 =====================
# 7.1 编解码：把 .rollback/v1.6/my_ui.py 当另一个模块导进来，拿 v1 的编码器现编一份做对照
import importlib.util as _ilu  # noqa: E402
import shutil  # noqa: E402

_spec7 = _ilu.spec_from_file_location(
    "my_ui_v16", "/Users/gaoying/Desktop/study/ai学习/.rollback/v1.6/my_ui.py")
old_ui = _ilu.module_from_spec(_spec7)
_spec7.loader.exec_module(old_ui)  # my_coding_agent 已在 sys.modules 里，不会把模型再建一遍
ck("7z0 对照模块导进来了：它自己那份的 MEM_FMT 仍是 v1、读集合也只有一个版本",
   old_ui.MEM_FMT == "v1" and old_ui.decode_memory('{"fmt":"v2","steps":[]}') == [],
   (old_ui.MEM_FMT,))

pair = [
    TaskStep(task="V9 第七节"),
    ActionStep(
        step_number=1,
        timing=Timing(start_time=0.0, end_time=2.0),
        observations="没等审批",
        token_usage=TokenUsage(input_tokens=5, output_tokens=2),
    ),
]
new_blob = my_ui.encode_memory(pair)
old_blob = old_ui.encode_memory(pair)
ck("7a 没等过审批的步：v2 编出来和 v1.6 编码器逐字相同（只差 fmt 那两位）",
   new_blob.replace('"v2"', '"v1"') == old_blob, (new_blob[-90:], old_blob[-90:]))

pair[1]._opsui_wait = 12.3456
b2 = my_ui.encode_memory(pair)
ck("7b 真等过的步才多写这一格，多出来的就是那一段（键名用 wait，不写私有属性名）",
   '"wait": 12.346' in b2 and len(b2) - len(new_blob) == len(', "wait": 12.346'), (len(b2), len(new_blob)))
back_w = my_ui.decode_memory(b2)
ck("7c 读回来挂回 step._opsui_wait：显示层（_stats / _step_card）本来就认这个属性，一行没改",
   getattr(back_w[1], "_opsui_wait", 0.0) == 12.346 and back_w[1].timing.duration == 2.0,
   vars(back_w[1]).get("_opsui_wait"))
ck("7d 模型读到的那一串不掺进这一格（wait 只是界面上的账，to_messages 不认）",
   model_reads(_mkmem(back_w)) == model_reads(_mkmem(pair)),
   model_reads(_mkmem(back_w))[:1])

# 7.2 兼容读：拿真实库里那些 v1 payload 演（不写库，只读一份副本）
REAL7 = Path("/Users/gaoying/Desktop/study/ai学习/smolagents/.agent-history.sqlite3")
copy7 = TMP / "real-copy.sqlite3"
shutil.copy(REAL7, copy7)
rows7 = sqlite3.connect(str(copy7)).execute("select session_id, payload from memory").fetchall()
readable7 = sum(1 for _, p in rows7 if my_ui.decode_memory(p))
ck("7e 真实库里的 payload（实跑攒下的 v1 旧账 ＋ 已经带 wait 的 v2）在新代码下全部读得回（升版本不失忆）",
   len(rows7) > 0 and readable7 == len(rows7), (readable7, len(rows7)))


def _shape(steps):
    return [(type(s).__name__, getattr(s, "task", None), getattr(s, "observations", None),
             s.timing.duration if getattr(s, "timing", None) else None,
             getattr(getattr(s, "token_usage", None), "input_tokens", None)) for s in steps]


v1rows7 = [(s, p) for s, p in rows7 if json.loads(p)["fmt"] == "v1"]
v2rows7 = [(s, p) for s, p in rows7 if json.loads(p)["fmt"] == "v2"]
ck("7f 逐条对得上：新代码读**库里那几条 v1 旧账**的结果，和 v1.6 代码读自己那一份一模一样（兼容读不是只读个壳）",
   bool(v1rows7) and all(_shape(my_ui.decode_memory(p)) == _shape(old_ui.decode_memory(p)) for _, p in v1rows7),
   [len(my_ui.decode_memory(p)) for _, p in v1rows7])
# 库里出现了真 v2（这一轮实跑写进去的）：老代码认不得它，读回空——这正是 MEM_FMT_READ
# 必须存在的原因，也是"只升版本号不做兼容读"那条反面证据的另一面。
ck("7f2 库里的真 v2 只有新代码读得回（v1.6 那份读它就是没记忆）",
   all(my_ui.decode_memory(p) and not old_ui.decode_memory(p) for _, p in v2rows7) and bool(v2rows7),
   [(s, len(my_ui.decode_memory(p)), len(old_ui.decode_memory(p))) for s, p in v2rows7])
ck("7f3 v2 那一条读回来时 wait 也回来了（重启后不靠进程内的账）",
   all(any(getattr(s, "_opsui_wait", 0.0) for s in my_ui.decode_memory(p)) for _, p in v2rows7),
   [[getattr(s, "_opsui_wait", None) for s in my_ui.decode_memory(p)] for _, p in v2rows7])
grow7 = sum(len(my_ui.encode_memory(my_ui.decode_memory(p))) - len(p) for _, p in rows7)
print("      7g 真实库 %d 条会话「读进来再编回去」的长度差（字节）：" % len(rows7),
      [len(my_ui.encode_memory(my_ui.decode_memory(p))) - len(p) for _, p in rows7])
ck("7g 重编往返零增长（v2 只给真有等待的步加那一格，不预先占位）", grow7 == 0, grow7)

v1ish = '{"fmt":"v1","steps":[{"_t":"ActionStep","step_number":1,"timing":{"start_time":0.0,"end_time":3.0}}]}'
st_v1ish = my_ui.decode_memory(v1ish)
ck("7h v1 的 payload 里没有 wait：读出来是 0（那一格不出现），不是把整条会话判成没记忆",
   len(st_v1ish) == 1 and getattr(st_v1ish[0], "_opsui_wait", 0.0) == 0.0
   and st_v1ish[0].timing.duration == 3.0,
   (len(st_v1ish), getattr(st_v1ish[0], "_opsui_wait", None)))
ck("7i 认不出的版本号仍旧整块拒读（v0、将来的 v3 不猜着读）",
   my_ui.decode_memory('{"fmt":"v3","steps":[{"_t":"TaskStep","task":"还在"}]}') == []
   and my_ui.decode_memory('{"fmt":"v0","steps":[]}') == [], "")

# ---- 7.3 端到端：真的 _stream_response + 真的闸，等出来的那一格落库；换新 OpsUI（=重启）看得见 ----
def fake_run_wait7(task, images=None, stream=True, reset=False):  # noqa: ARG001
    ag = my_ui.agent
    ag.memory.steps.append(TaskStep(task=task))
    time.sleep(0.2)
    t0 = time.time()
    obs = ag.tools["run_python"](code="print(7*7)")  # 卡在这里等人点「允许」
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=t0, end_time=time.time()),
        observations=str(obs),
        code_action="print(7*7)",
        tool_calls=[ToolCall(id="call_v9", name="run_python", arguments={"code": "print(7*7)"})],
        token_usage=TokenUsage(input_tokens=2349, output_tokens=22),
    )
    ag.memory.steps.append(step)
    yield step
    yield FinalAnswerStep(output="49")


my_ui.agent.run = fake_run_wait7
ui10 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
sid10 = ui10.hist.ensure(None)
OpsUI._pending_wait = 0.0


def approve7():
    for _ in range(300):
        if ui10._unanswered():
            time.sleep(0.7)  # 真的等 0.7 秒再点：这一格就是要单列出来、也要进库的那个数
            ui10._decide("allowed")
            return
        time.sleep(0.05)


threading.Thread(target=approve7, name="fake-click-v9", daemon=True).start()
frames10 = list(ui10._respond("第七节：把 7*7 打出来", sid10))
live_wait = ui10._stats()["task_wait"]
pay10 = json.loads(ui10.hist.load_memory(int(sid10)))
ck("7j 端到端第一步（v1.6 的 V8 没回潮）：活进程里状态条有「本题审批」",
   "本题审批" in frames10[-1][1] and live_wait >= 0.5, (frames10[-1][1][:200], live_wait))
ck("7k 落库那一串：fmt=v2，等过的那条 ActionStep 带着和进程内一致的 wait",
   pay10["fmt"] == "v2"
   and [r.get("wait") for r in pay10["steps"] if r.get("_t") == "ActionStep"] == [round(live_wait, 3)],
   pay10)

# 重启：换一个全新的 agent.memory（新进程没有 _mem），再建一个 OpsUI 读同一个库
fresh7 = AgentMemory(my_ui.agent.system_prompt)
my_ui.agent.memory = fresh7
ui11 = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
ld11 = ui11._on_load()
ck("7l **重启后刷新页面这一下就是验收动作**：状态条上「本题审批」自己回来了，数就是那一格的秒数",
   str(ld11[1]) == str(sid10) and "本题审批" in ld11[2] and ("%.1fs" % live_wait) in ld11[2],
   ld11[2][:300])
ck("7m 走的是只读那条路：agent.memory 没被换、绑定也没动（V5 语义一字未改）",
   my_ui.agent.memory is fresh7 and len(fresh7.steps) == 0 and ui11._mem_sid is None and ui11._mem == {},
   (ui11._mem_sid, len(fresh7.steps)))

# 屏上是甲、条上不能报乙：先开一条没审批的乙，再点回甲
my_ui.agent.run = fake_run_plain
sid11b = ui11.hist.ensure(None)
fb = list(ui11._respond("第七节乙：这题不用工具", sid11b))
ck("7n 乙这一题没有审批：状态条不该带那一格（别把甲的等待算给乙）",
   "本题审批" not in fb[-1][1], fb[-1][1][:200])
sw = ui11._select_session(str(sid10))
ck("7o 点旧会话：状态条报的是**屏幕上这一条**，「本题审批」跟着回来了",
   "本题审批" in sw[1] and ("%.1fs" % live_wait) in sw[1], sw[1][:300])
ck("7p 这一按不改绑定：_mem_sid 还是乙、agent.memory 里只有乙自己的题面",
   ui11._mem_sid == int(sid11b)
   and [s.task for s in my_ui.agent.memory.steps if isinstance(s, TaskStep)] == ["第七节乙：这题不用工具"],
   (ui11._mem_sid, [s.task for s in my_ui.agent.memory.steps if isinstance(s, TaskStep)]))

# 接着在甲上问一题没审批的：回灌进来的老等待不能漂到新题头上
OpsUI._pending_wait = 0.0
frames12 = list(ui11._respond("第七节：甲上再问一句（这题没审批）", sid10))
st12 = ui11._stats()
ck("7q 旧会话里接着问：本题边界仍是最后一个 TaskStep 之后，回灌的老步骤不并入本题",
   st12["task_wait"] == 0.0 and "本题审批" not in frames12[-1][1], (st12["task_wait"], frames12[-1][1][:200]))
ck("7r _stats() 不传参时行为不变（老调用点一个都没动）",
   ui11._stats() == ui11._stats(my_ui.agent.memory.steps))
echo7 = ui11._select_session(str(sid10))
ck("7s V7 没回潮：值没变的那一次仍旧三个输出全空、不碰 chatbot",
   all(isinstance(x, dict) and "value" not in x and "choices" not in x for x in echo7), echo7)

print()
faulthandler.cancel_dump_traceback_later()
print("TMP DB:", ui.hist.path, "| sessions:", len(ui.hist.choices()))
print("memory rows:", sqlite3.connect(str(ui.hist.path)).execute("SELECT session_id, length(payload) FROM memory ORDER BY session_id").fetchall())
print("FAILS:", FAILS if FAILS else "无")
sys.exit(1 if FAILS else 0)
