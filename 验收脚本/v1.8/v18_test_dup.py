# -*- coding: utf-8 -*-
"""P1-a 重复调用检测与熔断的离线断言：不起进程、不打模型，喂给门一批假工具。

为什么能离线：这一刀的全部新逻辑都长在四个地方——
  ① `_install_dup_gate` / `_dup_call`（查重 + 熔断），
  ② `_bind_args`（从 _gated_call 里搬出来的那份参数归一，审批卡和指纹共用），
  ③ `_step_card` 新加的那一档判定（⚪ 重复未执行 / ⛔ 重复熔断），
  ④ `_respond` 的 `except AgentError` 里「熔断」和「按了 ■ 停止」的分档。
①②只碰 dict 和 threading.Lock；③④喂假的 step / 假的流就能钉住。真跑那一路由
v18_dup_probe.py + v18_run_live.py 覆盖（换题清零这种**只有真两轮才算得准**的，
离线只能断源码位置，见第 5 节那条说明）。

第 2 节那批「第几次挡」的数字全部对着 DUP_BLOCK_LIMIT=2 的语义来：挡下第 1、2 次各回
一句警告，第 3 次（超过 2）才熔断。改这个常量，第 2 节会红——那是故意的，语义和数字
必须一起改。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_test_dup.py
退出码 0 = 全绿。
"""
import ast
import hashlib
import inspect
import json
import sys
import threading
import time
import types
from pathlib import Path

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr  # noqa: E402
from smolagents import AgentError  # noqa: E402
from smolagents.memory import ActionStep, ToolCall  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

import my_mcp  # noqa: E402
import my_ui  # noqa: E402
from my_ui import DUP_BLOCK_LIMIT, DUP_FUSE_MARK, DUP_MARK, OpsUI  # noqa: E402

SMOL = Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
OLD_UI = SMOL / ".rollback/v1.8/after-p0abc/my_ui.py"

FAIL = []


def ok(n, cond, detail=""):
    print("%-34s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def logger_stub():
    """AgentError.__init__ 只做一件事：logger.log_error(message)（utils.py:94-97）。"""
    return types.SimpleNamespace(log_error=lambda msg: None)


class FakeTool:
    """一只会把自己被跑过记进 sink 的工具。copy.copy 复制 __dict__，sink 是共享的那条。"""

    def __init__(self, name, sink):
        self.name, self.sink = name, sink

    def forward(self, path=".", content=""):
        self.sink.append((self.name, path, content))
        return f"executed {self.name}"


def tools(sink):
    return {n: FakeTool(n, sink) for n in
            ("list_dir", "read_file", "grep_files", "write_file", "run_python", "final_answer")}


def ui(sink=None):
    """不走 __init__（那会建整个界面、连上真 agent）。门要的依赖只有 tools 字典、
    _gate_lock 那几个类级账，和渲染用的 _stats 形状。"""
    u = OpsUI.__new__(OpsUI)
    # v2.0 A2：_install_gate 现在要先问「桥上挂了哪些外部工具」（_gate_names），_status_html
    # 也要读那一格。给一个**空桥**：gated=() 于是门名单还是 GATED_TOOLS 那两只，本闸的口径不变。
    u._mcp = my_mcp.Bridge()
    u._plan_shown = None
    u._run_in = u._run_out = 0
    u._run_secs = u._run_wait = 0.0
    u._state = "idle"
    u._sid = None
    sink = sink if sink is not None else []
    u.interrupted = []
    u.agent = types.SimpleNamespace(
        tools=tools(sink),
        # 空流：_install_dup_gate 现在还会顺手装「熔断当场收尾」那层（_install_dup_stop），
        # 它装的时候要读 agent._run_stream。第 2B 节会把这个位置换成假流。
        _run_stream=lambda *a, **kw: iter(()),
        max_steps=8,
        interrupt_switch=False,
        model=types.SimpleNamespace(model_id="qwen-plus"),
        memory=types.SimpleNamespace(steps=[]),
        monitor=types.SimpleNamespace(
            get_total_token_counts=lambda: types.SimpleNamespace(input_tokens=0, output_tokens=0)),
        logger=logger_stub(),
        interrupt=lambda: (u.interrupted.append(1), setattr(u.agent, "interrupt_switch", True)),
    )
    u._sink = sink
    reset_run()
    return u


def reset_run():
    """换题开局该做的清零：_stream_response 里那一句的离线等价物（第 5 节断言它真的在源头）。"""
    with OpsUI._gate_lock:
        OpsUI._run_seq += 1
        OpsUI._cancelled_before = 0
        OpsUI._seen_calls.clear()
        OpsUI._dup_blocked = 0
        OpsUI._dup_tripped = False
        OpsUI._pending.clear()
        OpsUI._ap_cards.clear()
        OpsUI._pending_wait = 0.0


def call(u, name, **kw):
    """按框架的方式打这只工具：BaseTool.__call__ 最后一句就是 self.forward(**arguments)。"""
    return u.agent.tools[name].forward(**kw)


def dup_lines(text):
    return text.count(DUP_MARK)


# ---- 1：装法与覆盖面 -------------------------------------------------------------------
u = ui()
u._install_gate()
u._install_dup_gate()
ok("1a 除 final_answer 全被套上",
   all(getattr(t, "_opsui_dedup", False) == (n != "final_answer") for n, t in u.agent.tools.items()),
   str(sorted((n, getattr(t, "_opsui_dedup", False)) for n, t in u.agent.tools.items())))
ok("1b 只读那侧也在里面", getattr(u.agent.tools["list_dir"], "_opsui_dedup", False) is True)
ok("1c 审批那两只仍带着审批层",
   getattr(u.agent.tools["write_file"], "_opsui_gated", False) is True)
tools_before = {n: id(t) for n, t in u.agent.tools.items()}
u2 = OpsUI.__new__(OpsUI)
u2.agent = u.agent
u2._mcp = my_mcp.Bridge()
u2._install_gate()
u2._install_dup_gate()
ok("1d 二次安装不套第二层（幂等）",
   all(id(u.agent.tools[n]) == v for n, v in tools_before.items()),
   str([(n, id(u.agent.tools[n]) == v) for n, v in tools_before.items()]))
u._sink.clear()
call(u, "read_file", path="a.py")
ok("1e 二次安装后一次调用只跑一遍", len(u._sink) == 1, str(u._sink))

# 顺序（查重在审批外层）用行为证：第 4 节。

# ---- 2：第几次挡，挡到哪一步熔断 -------------------------------------------------------
# DUP_BLOCK_LIMIT 的语义就靠这一段钉死，所以先确认它现在是 2。
ok("2a 上限当前是 2（下面四档按它写）", DUP_BLOCK_LIMIT == 2, str(DUP_BLOCK_LIMIT))
u = ui()
u._install_gate()
u._install_dup_gate()
r1 = call(u, "list_dir", path="smolagents/")
ok("2b 第一次真的执行", u._sink == [("list_dir", "smolagents/", "")] and r1 == "executed list_dir", str(u._sink))
r2 = call(u, "list_dir", path="smolagents/")
ok("2c 第二次不执行、回警告",
   len(u._sink) == 1 and r2.startswith(DUP_MARK) and "第 2 次" in r2, r2[:36])
ok("2d 第二次还没熔断", u.interrupted == [] and OpsUI._dup_tripped is False,
   "%r / %r" % (u.interrupted, OpsUI._dup_tripped))
r3 = call(u, "list_dir", path="smolagents/")
ok("2e 第二次重复仍只警告（挡下 2 次）",
   r3.startswith(DUP_MARK) and "第 3 次" in r3 and u.interrupted == [], r3[:36])
r4 = call(u, "list_dir", path="smolagents/")
ok("2f 第三次重复触发熔断", r4.startswith(DUP_FUSE_MARK) and u.interrupted == [1], r4[:36])
ok("2g 熔断句里带着三个数",
   "第 4 次" in r4 and "累计挡下 3 次" in r4 and "上限 2" in r4, r4[:120])
ok("2h 熔断写进了登记表", OpsUI._dup_tripped is True and OpsUI._dup_blocked == 3,
   "%r / %r" % (OpsUI._dup_tripped, OpsUI._dup_blocked))
ok("2i 熔断后换参数照常执行（这层只挡重复）",
   call(u, "list_dir", path="dify/").startswith("executed") and len(u._sink) == 2, str(u._sink))
r5 = call(u, "list_dir", path="smolagents/")
ok("2j 熔断后同类重复仍报已熔断", r5.startswith(DUP_FUSE_MARK) and u.interrupted == [1, 1], r5[:36])

# ---- 2B：熔断当场收尾（_install_dup_stop） ----------------------------------------------
# 只靠框架的 interrupt() 有个洞：agents.py:545-547 那句判 interrupt_switch 写在 while 循环体
# 最上面，而 step_number 在循环体自己的 finally 里才 +1（agents.py:604）。所以熔断落在**最后一步**
# （max_steps=8 的第 8 步，21:06 那份 transcript 的第三次重复恰好就在这一步）时，循环条件先为假
# 直接退出，压根走不到那一句——流程改走 _handle_max_steps_reached：多打一次模型、
# 状态条写「步数用满」，⛔ 那一档被吞掉。这一节钉的就是这个收尾层。
def fused_stream(tripped, pre_events=0):
    """假 _run_stream：第 8 步带着熔断观察值，后面本来还有第 9 步。

    先把假流挂上再装门：_install_dup_stop 装的时候读的就是 self.agent._run_stream，
    反过来装会把包装套在真流上、假流永远进不来。

    pre_events 是**同一步的中途事件**（框架一步里先吐 ToolCall/ToolOutput，最后才吐
    ActionStep，agents.py:578-580 与 603）。零成本回放第一版就在中途事件后面抛的，结果
    第 8 步的卡片没画、memory 里那一步 observations 是空的——所以「只在 ActionStep
    之后收」这条得单独钉住。
    """
    u = ui()
    seen = []

    def inner(task, max_steps, images=None):                                 # noqa: ARG001
        for k in range(pre_events):
            seen.append("mid%d" % k)
            yield ToolCall(id="t%d" % k, name="list_dir", arguments={})
        t0 = time.time() - 1.4
        yield ActionStep(step_number=8, timing=Timing(start_time=t0, end_time=time.time()),
                         token_usage=TokenUsage(input_tokens=4308, output_tokens=95),
                         observations=my_ui.DUP_FUSE_OBSERVATION.format(n=5, blocked=3, limit=2))
        seen.append("step9")
        t1 = time.time() - 1.4
        yield ActionStep(step_number=9, timing=Timing(start_time=t1, end_time=time.time()),
                         token_usage=TokenUsage(input_tokens=4400, output_tokens=40))

    u.agent._run_stream = inner
    u._seen = seen
    u._install_gate()
    u._install_dup_gate()
    with OpsUI._gate_lock:
        OpsUI._dup_tripped = tripped
        OpsUI._dup_blocked = 3 if tripped else 0
    return u


u = fused_stream(True)
ok("2B-a 装完就带着收尾层", getattr(u.agent, "_opsui_dup_stop", False) is True)
g = u.agent._run_stream(task="q", max_steps=8, images=None)
first = next(g)
ok("2B-b 那一步本身照样先交出来（卡片画得出来）",
   isinstance(first, ActionStep) and first.step_number == 8, repr(first)[:60])
raised = None
try:
    next(g)
except BaseException as exc:                                                 # noqa: BLE001
    raised = exc
ok("2B-c 交出之后当场抛 AgentError", isinstance(raised, AgentError) and not isinstance(raised, my_ui.PlanDeniedError),
   repr(raised)[:60])
ok("2B-d 第 9 步没跑（省掉那一次模型调用）", u._seen == [], str(u._seen))
ok("2B-e 抛的话里带着挡下几次和上限",
   "挡下 3 次" in str(raised) and "上限 2" in str(raised), str(raised)[:90])

u = fused_stream(False)
got = list(u.agent._run_stream(task="q", max_steps=8, images=None))
ok("2B-f 没熔断时原样透传", len(got) == 2 and u._seen == ["step9"], "%d 个 / %r" % (len(got), u._seen))

u = fused_stream(False)
fn_before = u.agent._run_stream
u._install_dup_gate()
ok("2B-g 二次安装不套两层收尾", u.agent._run_stream is fn_before,
   "%s / %s" % (fn_before.__name__, u.agent._run_stream.__name__))

u = fused_stream(True, pre_events=2)
got, raised = [], None
try:
    for ev in u.agent._run_stream(task="q", max_steps=8, images=None):
        got.append(ev)
except BaseException as exc:                                                 # noqa: BLE001
    raised = exc
ok("2B-h 中途事件不收尾：两步 ToolCall 先过，第 8 步走完才抛",
   len(got) == 3 and all(isinstance(e, ToolCall) for e in got[:2])
   and isinstance(got[2], ActionStep) and isinstance(raised, AgentError),
   "%d 个 / %s" % (len(got), repr(raised)[:34]))
ok("2B-i 抛出去时那一步的观察值是完整的（卡片有 ⛔、记忆里有原话）",
   bool(got) and DUP_FUSE_MARK in (got[-1].observations or ""), str((got[-1].observations or "")[:16]))
ok("2B-j 收尾仍然拦住了第 9 步", u._seen == ["mid0", "mid1"], str(u._seen))

# ---- 3：指纹的口径 ---------------------------------------------------------------------
# 这一段**只装查重层**：写了 run_python 这种审批名单里的工具，第一次调用会挂在那里
# 等人点按钮（APPROVAL_TIMEOUT=600s），离线跑就等于卡死。外层顺序是第 4 节单独测的。
u = ui()
u._install_dup_gate()
a1 = call(u, "read_file", path="my_ui.py", content="")
a2 = call(u, "read_file", path="my_ui.py")          # 少给一个默认参数
ok("3a 省略默认参数算同一次", a1.startswith("executed") and dup_lines(a2) == 0, "%r / %r" % (a1, a2[:30]))
b1 = call(u, "read_file", path="my_agent.py")
ok("3b 参数不同就是两次调用", b1.startswith("executed") and len(u._sink) == 3, str(len(u._sink)))
c1 = call(u, "list_dir", path=Path("/tmp/x"))
c2 = call(u, "list_dir", path="/tmp/x")
ok("3c 非 JSON 实参不炸且能对上", c1.startswith("executed") and dup_lines(c2) == 1, "%r / %r" % (c1[:20], c2[:20]))
d1 = call(u, "grep_files", path='{"a": 1, "b": [2, 3]}')
d2 = call(u, "grep_files", path='{"a":1,"b":[2,3]}')
ok("3d 同一段 JSON 的两种写法算同一个", d1.startswith("executed") and dup_lines(d2) == 1, d2[:24])
ok("3e 空参数那种重复也挡得住（21:06 的 list_dir({})）",
   call(u, "run_python").startswith("executed") and dup_lines(call(u, "run_python")) == 1)
e1 = OpsUI._bind_args(FakeTool("x", []).forward, ("pos",), {"content": "c"})
ok("3f 位置参数与关键字参数同键", e1 == {"path": "pos", "content": "c"}, str(e1))


def weird_forward(path):        # 故意签名对不上
    pass


ok("3g 签名对不上时退化成按位置记",
   OpsUI._bind_args(weird_forward, (), {"nope": 1}) == {"args": [], "kwargs": {"nope": 1}},
   str(OpsUI._bind_args(weird_forward, (), {"nope": 1})))

# ---- 4：查重在审批**外层**（重复调用不开卡、不批空单） -----------------------------------
u = ui()
u._install_gate()
u._install_dup_gate()
box = []
t = threading.Thread(target=lambda: box.append(call(u, "write_file", path="a.txt", content="hi")))
t.start()
for _ in range(60):
    if OpsUI._pending:
        break
    time.sleep(0.02)
ok("4a 第一次调用开了审批卡", len(OpsUI._pending) == 1, str(len(OpsUI._pending)))
r = call(u, "write_file", path="a.txt", content="hi")     # 同名同参，另起一次
ok("4b 重复调用没开第二张卡", len(OpsUI._pending) == 1 and dup_lines(r) == 1,
   "%d 张 / %s" % (len(OpsUI._pending), r[:28]))
ok("4c 重复也没进原 forward", u._sink == [], str(u._sink))
ap0 = OpsUI._pending[0]
ap0.decide("allowed")
t.join(3)
ok("4d 那张卡批下去之后真的跑了", u._sink == [("write_file", "a.txt", "hi")], str(u._sink))
with OpsUI._gate_lock:
    OpsUI._pending.remove(ap0)          # 真界面里这一步是画卡循环做的，离线得自己摘
box = []
t = threading.Thread(target=lambda: box.append(call(u, "write_file", path="b.txt", content="hi")))
t.start()
for _ in range(60):
    if [a for a in OpsUI._pending if a.decision == "pending"]:
        break
    time.sleep(0.02)
pend = [a for a in OpsUI._pending if a.decision == "pending"]
ok("4e 换参数就照常开新卡（不是一律不开）", len(pend) == 1, str(len(pend)))
pend[0].decide("denied")
t.join(3)
with OpsUI._gate_lock:
    OpsUI._pending.clear()

# ---- 5：换题清零：离线只能钉源码位置（行为由 v18_dup_probe.py 的两轮真跑覆盖） -----------
src = inspect.getsource(OpsUI._stream_response)
lock_blk = src.split("with self._gate_lock:", 1)
ok("5a 开局临界区里有那个 with 块", len(lock_blk) == 2)
head = lock_blk[1].split("self._abandoned.clear()", 1)[0] if len(lock_blk) == 2 else ""
ok("5b 三句清零都在临界区内",
   all(s in head for s in ("OpsUI._seen_calls.clear()", "OpsUI._dup_blocked = 0", "OpsUI._dup_tripped = False")),
   head.replace("\n", " ")[:120])
ok("5c 清零在起线程之前", src.index("OpsUI._seen_calls.clear()") < src.index("threading.Thread("))
ok("5d 和 _ap_cards 那张登记表同一处清", "OpsUI._ap_cards.clear()" in head)

# ---- 6：步骤卡的判定 -------------------------------------------------------------------
def action_step(n, obs, calls=None, error=None):
    t0 = time.time() - 1.5
    return ActionStep(step_number=n, timing=Timing(start_time=t0, end_time=time.time()),
                      token_usage=TokenUsage(input_tokens=2463, output_tokens=76),
                      observations=obs, tool_calls=calls or [], error=error)


def tc(name, args):
    return ToolCall(id="x", name=name, arguments=args)


u = ui()
title_of = lambda st: u._step_card(st).metadata["title"]

st = action_step(1, my_ui.DUP_OBSERVATION.format(n=2), [tc("list_dir", {"path": "人生/"})])
t6 = title_of(st)
ok("6a 挡下来标 ⚪ 重复未执行", "⚪ 重复未执行 1/1" in t6, t6)
ok("6b 不写成成功", "🟢 成功" not in t6, t6)
st = action_step(2, my_ui.DUP_FUSE_OBSERVATION.format(n=4, blocked=3, limit=2), [tc("list_dir", {})])
ok("6c 熔断标 ⛔", "⛔ 重复熔断 1/1" in title_of(st), title_of(st))
mixed = my_ui.DUP_OBSERVATION.format(n=2) + "\n" + "正常观察值"
st = action_step(3, mixed, [tc("list_dir", {"path": "a"}), tc("read_file", {"path": "b"})])
t6 = title_of(st)
ok("6d 一步里只挡掉一只 → 摊开 1/2", "重复未执行 1/2" in t6 and "⚪" in t6, t6)
ok("6e 不谎称整步未执行", "重复未执行 1/1" not in t6, t6)
st = action_step(4, "命中 3 条", [tc("grep_files", {"pattern": "x"})])
ok("6f 正常那一路没被动（🟢 成功）", "🟢 成功" in title_of(st), title_of(st))
st = action_step(5, my_ui.DENIED_OBSERVATION["denied"], [tc("run_python", {"code": "print(1)"})])
ok("6g 审批拒绝仍标 ⚪ 已拒绝", "⚪ 已拒绝" in title_of(st), title_of(st))
st = action_step(6, my_ui.DUP_OBSERVATION.format(n=2) + "\nboom", [tc("list_dir", {})],
                 error=AgentError("boom", logger_stub()))
ok("6h 有报错仍优先标 🔴", "🔴 报错" in title_of(st), title_of(st))
body = u._step_card(action_step(7, my_ui.DUP_OBSERVATION.format(n=2), [tc("list_dir", {"path": "人生/"})])).content
ok("6i 正文里那句观察值看得见", DUP_MARK in body, body[-90:].replace("\n", " ")[:90])

# ---- 7：_respond 的收尾档位 ------------------------------------------------------------
class FakeHist:
    def ensure(self, sid):
        return 1

    def load(self, sid):
        return []

    def save(self, sid, messages):
        FakeHist.saved = messages

    def save_memory(self, sid, payload):
        pass


def responder(exc):
    u = ui()
    u.hist = FakeHist()
    u._bind_memory = lambda sid: None
    u._radio_update = lambda force=False: gr.update()
    u._mem, u._mem_sid = {}, None

    def stream(message, history):                                    # noqa: ARG001
        yield [gr.ChatMessage(role="assistant", content="一帧")]
        raise exc

    u._stream_response = stream
    return u


def tail_titles(frames):
    return [getattr(m, "metadata", {}).get("title", "") for m in frames[-1][0]]


def respond(exc, tripped=False, cancelled=False):
    """先造 responder 再竖旗：responder 里那句 ui() 自带一次 reset_run()，
    反过来写会把刚竖起的 _dup_tripped 又清成 False（第一跑 7a/7b/7c 就是这么假绿）。"""
    r = responder(exc)
    with OpsUI._gate_lock:
        OpsUI._dup_tripped = tripped
        if cancelled:
            OpsUI._cancelled_before = OpsUI._run_seq      # 相当于本轮按过 ■ 停止
    return list(r._respond("q", 1))


frames = respond(AgentError("Agent interrupted.", logger_stub()), tripped=True)
ok("7a 熔断收尾标「重复熔断」", "重复熔断" in frames[-1][1] and "已停止" not in frames[-1][1], frames[-1][1][-70:])
ok("7b 卡片标题是 ⛔ 重复熔断", any(t.startswith("⛔ 重复熔断") for t in tail_titles(frames)), str(tail_titles(frames)))
ok("7c 收尾文案带上限数字", str(DUP_BLOCK_LIMIT) in frames[-1][0][-1].content, frames[-1][0][-1].content[-80:])
ok("7d 帧仍是 8 元组（P0-4 回归）", all(len(f) == 8 for f in frames), str([len(f) for f in frames]))

frames = respond(AgentError("Agent interrupted.", logger_stub()), tripped=True, cancelled=True)
ok("7e 停止优先于熔断", "已停止" in frames[-1][1] and "重复熔断" not in frames[-1][1], frames[-1][1][-70:])

frames = respond(AgentError("Model exploded.", logger_stub()))
ok("7f 普通报错仍写已停止（回归）", "已停止" in frames[-1][1], frames[-1][1][-70:])

frames = respond(my_ui.PlanDeniedError("已拒绝：这一题没有开工。", logger_stub()))
ok("7g 计划否决仍是计划未批准（回归）",
   "计划未批准" in frames[-1][1] and "重复熔断" not in frames[-1][1], frames[-1][1][-70:])

# ---- 8：文案与显示的成套性 -------------------------------------------------------------
ok("8a 熔断句以警告句开头（第 6 节计数的前提）",
   my_ui.DUP_FUSE_OBSERVATION.startswith(DUP_MARK) and DUP_FUSE_MARK.startswith(DUP_MARK))
ok("8b 两句都说清「没有执行」",
   "没有真的执行" in my_ui.DUP_OBSERVATION and "同样没有执行" in my_ui.DUP_FUSE_OBSERVATION)
ok("8c 熔断句说了「到此结束」", "到这里结束" in my_ui.DUP_FUSE_OBSERVATION)
ok("8d 警告句给了出路", "换一个参数" in my_ui.DUP_OBSERVATION and "把答案交出来" in my_ui.DUP_OBSERVATION)
ok("8e STATE_LABEL 有这一档", my_ui.STATE_LABEL["dup_fused"] == "重复熔断")
ok("8f 状态条有对应配色", "st-dup_fused" in my_ui.DARK_CSS)
for ph in ("{n}", "{blocked}", "{limit}"):
    ok("8g 占位符 %s 都填得上" % ph, ph in my_ui.DUP_FUSE_OBSERVATION)
ok("8h format 不会喷 KeyError",
   my_ui.DUP_FUSE_OBSERVATION.format(n=4, blocked=3, limit=2).count("{") == 0)

# ---- 9：这一刀的提示词成本＝零 ---------------------------------------------------------
def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def prompt_surface(path):
    """这两个文件里**模型真读得到的**那批字符串：工具 docstring、agent 的 description/name、
    guarded() 念给模型的那几条 raise 原文。整文件哈希守不了本节想守的东西——
    v2.0 的 B1 改了这两个文件（超时常量＋注释＋import），提示词面一字没动，
    而整文件哈希会把这条守卫变成「谁都不许碰这两个文件」，那是另一回事。

    口径 2026-11-04 动过一次又改回来了：v2.0 的 model_preflight()（1-token 自检，模型读不到）
    的 docstring 把这条顶红，我一度把收集范围收窄到 @tool 装饰的那几只——实测那样会把
    my_agent.py 里 max_drawdown / annualized_volatility 两只工具的 docstring 一起漏掉
    （它们是类的 forward 方法，没有 @tool 装饰），守卫反而松了。所以范围维持原样：
    **这两个文件里任何函数 docstring 都算提示词面**。要加说明就写 # 注释。"""
    out = []
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            d = ast.get_docstring(n)
            if d:
                out.append(("doc:" + n.name, d))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "ToolCallingAgent":
            for k in n.keywords:
                if k.arg in ("description", "name"):
                    out.append(("kw:" + k.arg, ast.unparse(k.value)))
        elif isinstance(n, ast.Raise):
            out.append(("raise", ast.unparse(n)))
    return out


for f in ("my_agent.py", "my_coding_agent.py"):
    now, snap = prompt_surface(SMOL / f), prompt_surface(SMOL / ".rollback/v1.8/after-p0abc" / f)
    ok("9a %s 提示词面与快照逐字一致（不改提示词）" % f, now == snap,
       f"{len(now)} 段 · 文件本身 sha1 {sha1(SMOL / f)[:8]}（v2.0 B1 改了常量与注释，故不比整文件）")
    if now != snap:
        for x in sorted(set(snap) - set(now), key=str):
            print("   只在快照:", x[0], str(x[1])[:70])
        for x in sorted(set(now) - set(snap), key=str):
            print("   只在工作区:", x[0], str(x[1])[:70])
ok("9b 命令行跑法不经过这层", "import my_ui" not in (SMOL / "my_agent.py").read_text(encoding="utf-8"))

# ---- 10：负控——回滚那份根本没有这一层 --------------------------------------------------
old_src = OLD_UI.read_text(encoding="utf-8")
ok("10a 快照里没有查重门", "_install_dup_gate" not in old_src)
ok("10b 快照里没有登记表", "_seen_calls" not in old_src)
ok("10c 快照的步骤卡没有这一档", "dup_hits" not in old_src)
ok("10d 快照的收尾只有已停止/计划未批准两档", '"dup_fused"' not in old_src)
ok("10e 快照的 _gated_call 自己绑参数（没抽公共 helper）",
   "bind_partial" in old_src and "_bind_args" not in old_src)

print("\n%s  (%d 条失败)" % ("全绿" if not FAIL else "失败：" + ",".join(str(f) for f in FAIL), len(FAIL)))
sys.exit(1 if FAIL else 0)
