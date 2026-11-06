# -*- coding: utf-8 -*-
"""P0-4 计划可见＋批准动作的离线断言：不起进程、不打模型，喂给门一个假的 _run_stream。

为什么能离线：这一刀的全部新逻辑都长在三个地方——
  ① `_install_plan_gate` / `_plan_gate`（把计划卡在「已生成、还没开工」那一刻），
  ② `_approval_card` / `_step_card` / `_plan_update` / `_last_plan`（四处渲染），
  ③ `_respond` 多出来的那第 8 个产出（面板）。
①②不碰 gradio 事件也不碰真线程；③用一个假的 `_stream_response` 就能把元组位数和
收尾那一档的措辞一起钉住。真界面那一路由 v18_run_live.py 的 P0/P1 两个场景覆盖。

假 `_run_stream` 的形状照抄上游（agents.py:556-562）：交出 PlanningStep 之后才
`_finalize_step` + `memory.steps.append`。这里用一个 `after.append(1)` 代表那两句，
于是「没批准的计划进不了记忆」这条不变式是**可断言**的，不是讲解。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_test_plan.py
退出码 0 = 全绿。
"""
import sys
import threading
import time
import types

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr  # noqa: E402
from smolagents import AgentError, PlanningStep  # noqa: E402
from smolagents.memory import ActionStep, TaskStep  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

import my_mcp  # noqa: E402
import my_ui  # noqa: E402

FAIL = []
PLAN = "Here are the facts I know and the plan of action:\n```\n1. call max_drawdown\n2. call final_answer\n```"


def ok(n, cond, detail=""):
    print("%-34s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def logger_stub():
    """AgentError.__init__ 只做一件事：logger.log_error(message)（utils.py:94-97）。
    这里不要 rich 往终端喷，接住即可。"""
    return types.SimpleNamespace(log_error=lambda msg: None)


def plan_step(text=None):
    # timing 是 PlanningStep 的必需位置参数（memory.py:151-156 那一段），上游在交出事件
    # 之前就把这一次模型调用的计时填好了（agents.py:741-746 的 Timing(start,end)）——
    # 所以门里拿到的是带计时的计划，_step_card 那句 step.timing.duration 不会踩空。
    t0 = time.time() - 32.886
    return PlanningStep(
        model_input_messages=[],
        plan=PLAN if text is None else text,
        model_output_message=types.SimpleNamespace(content=PLAN if text is None else text),
        token_usage=TokenUsage(input_tokens=1188, output_tokens=1458),
        timing=Timing(start_time=t0, end_time=time.time()),
    )


def action_step(n=1):
    """ActionStep 的 timing 同样是必需位置参数（照 3.13 的签名，不是可省的默认）。"""
    t0 = time.time() - 2.62
    return ActionStep(step_number=n, timing=Timing(start_time=t0, end_time=time.time()),
                      token_usage=TokenUsage(input_tokens=3957, output_tokens=95))


def ui(with_stream=True):
    """不走 __init__（那会建整个界面、装真工具门）。门的依赖只有：
    agent 的 _run_stream/logger、_gate_lock 与那几个类级账，加上渲染要的 _stats 形状。"""
    u = my_ui.OpsUI.__new__(my_ui.OpsUI)
    # v2.0 A2：_status_html 多了 MCP 那一格，读的是 self._mcp.describe()。空桥 = 「未配置 server」，
    # 这一格在这里要的正是「没有外部工具」这个前提。
    u._mcp = my_mcp.Bridge()
    u._plan_shown = None
    u.agent = types.SimpleNamespace(
        max_steps=8,
        model=types.SimpleNamespace(model_id="qwen-plus"),
        memory=types.SimpleNamespace(steps=[]),
        monitor=types.SimpleNamespace(
            get_total_token_counts=lambda: types.SimpleNamespace(input_tokens=0, output_tokens=0)),
        logger=logger_stub(),
    )
    if with_stream:
        def fake(task, max_steps, images=None):     # noqa: ARG001
            yield plan_step()
            after.append("appended")                # = 上游的 _finalize_step + memory.append
            # ActionStep 和 PlanningStep 一样，timing 是必需位置参数（memory.py 那两个类）：
            # 少交一个就把这条假流变成了 TypeError，测试会把它当成"下一步没跑"读错。
            t0 = time.time() - 2.62
            yield ActionStep(step_number=1, timing=Timing(start_time=t0, end_time=time.time()),
                             token_usage=TokenUsage(input_tokens=3957, output_tokens=95))
        u.agent._run_stream = fake
        u.agent._opsui_plan_gated = False
        u._after = after = []
    my_ui.OpsUI._pending.clear()
    my_ui.OpsUI._ap_cards.clear()
    my_ui.OpsUI._pending_wait = 0.0
    return u


def run_seq():
    """每轮开局该做的两件事（_stream_response 里的那两句），离线要自己补。"""
    with my_ui.OpsUI._gate_lock:
        my_ui.OpsUI._run_seq += 1
        my_ui.OpsUI._cancelled_before = 0


def drain(gen, box):
    """把「门放行之后还能拿到下一个事件」这件事搬到别的线程里做。"""
    try:
        box.append(next(gen))
    except BaseException as exc:                     # noqa: BLE001
        box.append(exc)


# ---- 1：包装的形状——先交事件、后等人，中间那一句都不能少 -------------------------------
u = ui()
run_seq()
u._install_plan_gate()
ok("1a 门装在实例上且幂等", getattr(u.agent, "_opsui_plan_gated", False) is True)
g = u.agent._run_stream(task="q", max_steps=8, images=None)   # 上游就是这么按关键字调的（agents.py:496）
ev = next(g)
ok("1b 第一个事件是 PlanningStep", isinstance(ev, PlanningStep))
ok("1c 交出事件那一刻还没入队", my_ui.OpsUI._pending == [], str(my_ui.OpsUI._pending))
box = []
t = threading.Thread(target=drain, args=(g, box))
t.start()
for _ in range(60):
    if my_ui.OpsUI._pending:
        break
    time.sleep(0.02)
ok("1d 门把计划登记成一张待批单", len(my_ui.OpsUI._pending) == 1,
   str([(a.tool, a.kind, a.decision) for a in my_ui.OpsUI._pending]))
ok("1e 单子挂在那儿、agent 没往下走", box == [] and u._after == [], "%r / %r" % (box, u._after))

# ---- 2：✔ 允许 → 放行，计划照常进记忆 ----------------------------------------------------
ap = my_ui.OpsUI._pending[0]
time.sleep(0.06)   # 过 V8 那道显示门槛（APPROVAL_WAIT_MIN=0.05）：秒级以下的等待本来就不记账
ap.decide("allowed")
t.join(3)
ok("2a 允许之后内层被续跑", u._after == ["appended"], str(u._after))
ok("2b 下一个事件是 ActionStep", box and isinstance(box[0], ActionStep), repr(box[0])[:70])
ok("2c 等待照样过账（V8 口径）", abs(my_ui.OpsUI._pending_wait - ap.waited) < 1e-9,
   "%s / %s" % (my_ui.OpsUI._pending_wait, ap.waited))

# ---- 3：✖ 拒绝 → 整题停在这道门上，那份计划一个字节都没进记忆 ------------------------------
u = ui()
run_seq()
u._install_plan_gate()
g = u.agent._run_stream(task="q", max_steps=8, images=None)
next(g)
# 分两句写，不要 `box, t = [], threading.Thread(args=(g, box))`：右边的表达式在左边的
# 名字绑定**之前**求值，那种写法喂给线程的还是上一段那个旧 box（第一跑就是这么把 3a
# 读成「box 是空的」的，看着像门没抛异常）。
box = []
t = threading.Thread(target=drain, args=(g, box))
t.start()
for _ in range(60):
    if my_ui.OpsUI._pending:
        break
    time.sleep(0.02)
my_ui.OpsUI._pending[0].decide("denied")
t.join(3)
ok("3a 拒绝抛出 PlanDeniedError", isinstance(box[0], my_ui.PlanDeniedError), repr(box[0])[:60])
ok("3b 抛出去就没有下一步", u._after == [], str(u._after))
ok("3c 话里说清「没开工」", "一个工具都没跑" in str(box[0]), str(box[0])[:70])

# ---- 4：超时未批走同一档（措辞是「超时未批」） --------------------------------------------
u = ui()
run_seq()
u._install_plan_gate()
old_timeout, my_ui.APPROVAL_TIMEOUT = my_ui.APPROVAL_TIMEOUT, 0.05
try:
    g = u.agent._run_stream(task="q", max_steps=8, images=None)
    next(g)
    box = []
    t = threading.Thread(target=drain, args=(g, box))
    t.start()
    t.join(3)
finally:
    my_ui.APPROVAL_TIMEOUT = old_timeout
ok("4a 超时也是 PlanDeniedError", isinstance(box[0], my_ui.PlanDeniedError), repr(box[0])[:50])
ok("4b 措辞是超时未批", "超时未批" in str(box[0]), str(box[0])[:60])
ok("4c 超时同样不进记忆", u._after == [], str(u._after))

# ---- 5：D7 那一路——停止先落到门上的号，计划入队即结算、照样停 ------------------------------
u = ui()
run_seq()
u._install_plan_gate()
with my_ui.OpsUI._gate_lock:
    my_ui.OpsUI._cancelled_before = my_ui.OpsUI._run_seq      # 相当于本轮按过 ■ 停止
g = u.agent._run_stream(task="q", max_steps=8, images=None)
next(g)
box = []
drain(g, box)                                                 # 不用线程：入队即结算，不该挂人
ok("5a 入队即随停止结算", my_ui.OpsUI._pending[0].decision == "cancelled")
ok("5b 停的是 AgentError 不是否决", isinstance(box[0], AgentError) and not isinstance(box[0], my_ui.PlanDeniedError),
   repr(box[0])[:50])
ok("5c 这一路不进记忆", u._after == [], str(u._after))

# ---- 6：审批卡（kind=plan）的措辞；工具那张的措辞由 v18_test_nochange.py 钉住 --------------
u = ui(with_stream=False)
a = my_ui.Approval(my_ui.PLAN_APPROVAL_NAME, {"plan": PLAN}, kind="plan")
a.created = time.time() - 5.231
c = u._approval_card(a, 5.231)
ok("6a 待批标题带「计划」", c.metadata["title"].startswith("🟡 待批 · 计划 · "), c.metadata["title"])
ok("6b 正文有字符数", f"{len(PLAN):,} 字符" in c.content, "")
ok("6c 说的是批计划不是跑代码", "批准这份计划" in c.content and "这一题就地停下" in c.content)
a.decide("denied")
c2 = u._approval_card(a, 5.231)
ok("6d 否决后写「没进模型的记忆」", "没有进模型的记忆" in c2.content, c2.content[-70:].replace("\n", "\\n"))
ok("6e 标题带精确等待", "等了 5.2s" in c2.metadata["title"], c2.metadata["title"])

# ---- 7：面板与计划卡 --------------------------------------------------------------------
u = ui(with_stream=False)
ok("7a 没计划时面板不出现", u._plan_update().get("visible") is False, str(u._plan_update()))
u._plan_shown = (PLAN, "pending", 12.4)
p = u._plan_update()
ok("7b 待批面板带挂起秒数", p.get("visible") is True and "等待审批" in p["value"] and "已挂起 12s" in p["value"],
   p["value"][:80].replace("\n", "\\n"))
ok("7c 面板正文就是计划原文", PLAN in p["value"])
u._plan_shown = (PLAN, "allowed", 4.9)
ok("7d 已允许面板", "已允许" in u._plan_update()["value"] and "照这份计划走" in u._plan_update()["value"])
u._plan_shown = (PLAN, "denied", None)
ok("7e 否决面板", "已拒绝" in u._plan_update()["value"] and "一个工具都没跑" in u._plan_update()["value"])

card = u._step_card(plan_step())
ok("7f 计划卡标题写明已允许", card.metadata["title"].startswith("🧭 计划 · 已允许"), card.metadata["title"])
ok("7g 标题带这一拍的耗时与 token", "32.9s" in card.metadata["title"]
   and "in 1,188/out 1,458" in card.metadata["title"], card.metadata["title"])
ok("7h 正文仍是计划全文", PLAN in card.content)

# ---- 8：从记忆里读回最后一份计划（刷新／换会话／重启那一路） --------------------------------
ok("8a 无计划读空", u._last_plan([TaskStep(task="q"), action_step()]) is None)
lp = u._last_plan([TaskStep(task="q"), plan_step(), action_step()])
ok("8b 读到那份计划", lp is not None and lp[0] == PLAN, str(lp)[:40])
ok("8c 读数固定 allowed（能进库的都批过）", lp[1] == "allowed", str(lp[1]))
# 两份不同正文的计划才测得出「取最后一份」——两份正文一样的话这条断言恒真。
ok("8d 多份计划取最后一份",
   u._last_plan([plan_step("第一份"), plan_step("第二份")])[0] == "第二份",
   str(u._last_plan([plan_step("第一份"), plan_step("第二份")])[:20]))
ok("8e steps=None 不炸", u._last_plan(None) is None)

# ---- 9：_respond 的产出位数（面板是第 8 格）＋ 否决收尾那一档 -------------------------------
class FakeHist:
    def ensure(self, sid):
        return 1

    def load(self, sid):
        return []

    def save(self, sid, messages):
        FakeHist.saved = messages

    def save_memory(self, sid, payload):
        pass


def responder(stream):
    u = ui(with_stream=False)
    u.hist = FakeHist()
    u._bind_memory = lambda sid: None
    u._radio_update = lambda force=False: gr.update()
    u._mem = {}
    u._mem_sid = None
    u._stream_response = stream
    return u


def one_frame(message, history):                                        # noqa: ARG001
    yield [gr.ChatMessage(role="assistant", content="一帧")]


u = responder(one_frame)
u._plan_shown = (PLAN, "allowed", 2.0)
frames = list(u._respond("q", 1))
ok("9a 每帧都是 8 元组", all(len(f) == 8 for f in frames), str([len(f) for f in frames]))
ok("9b 面板在第 8 格", frames[-1][7].get("visible") is True and PLAN in frames[-1][7]["value"])
ok("9c 收尾状态是完成", "完成" in frames[-1][1], frames[-1][1][-90:])


def denied_frame(message, history):                                     # noqa: ARG001
    yield [gr.ChatMessage(role="assistant", content="计划卡")]
    raise my_ui.PlanDeniedError("已拒绝：这一题没有开工，一个工具都没跑。", logger_stub())


u = responder(denied_frame)
u._plan_shown = (PLAN, "denied", 5.2)
frames = list(u._respond("q", 1))
tail = frames[-1][0]
ok("9d 否决帧也是 8 元组", len(frames[-1]) == 8)
titles = [getattr(m, "metadata", {}).get("title", "") for m in tail]
ok("9e 收尾卡片标题「✖ 计划未批准」", any(t.startswith("✖ 计划未批准") for t in titles), str(titles[-1]))
ok("9f 没写成「已停止」", not any("已停止" in t for t in titles), str(titles[-1]))
ok("9g 状态条那一格是计划未批准", "计划未批准" in frames[-1][1], frames[-1][1][-80:])
ok("9h 面板这时还在（读数是已拒绝）",
   frames[-1][7].get("visible") is True and "已拒绝" in frames[-1][7]["value"])

print("\n%s  (%d 条失败)" % ("全绿" if not FAIL else "失败：" + ",".join(str(f) for f in FAIL), len(FAIL)))
sys.exit(1 if FAIL else 0)
