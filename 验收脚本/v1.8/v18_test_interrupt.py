# -*- coding: utf-8 -*-
"""D8 断开侧修复的离线断言：不起进程、不打模型，只喂 `_mark_interrupted` 它该收到的东西。

为什么能离线：这一刀的全部新逻辑都在 `_mark_interrupted`（改卡 ＋ 补标记 ＋ 补审批等待的账）
和它读的那两个类级登记表上，不碰 gradio 事件、不碰线程。真断开那一路由 v18_run_live.py B1 覆盖。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_test_interrupt.py
退出码 0 = 全绿；任何一条断言失败就打印编号与非零退出。
"""
import pathlib
import sys
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
from smolagents.memory import ActionStep, TaskStep  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

import my_ui  # noqa: E402

FAIL = []


def ok(n, cond, detail=""):
    print("%-4s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def ui():
    """不走 __init__（那会建整个界面）。_mark_interrupted 只读类级登记簿和两个静态方法，
    _stats 额外要一个 agent 的形状——给它一个够用的假壳，不打模型、不起线程。"""
    u = my_ui.OpsUI.__new__(my_ui.OpsUI)
    u.agent = types.SimpleNamespace(
        max_steps=8,
        model=types.SimpleNamespace(model_id="qwen-plus"),
        memory=types.SimpleNamespace(steps=[]),
        monitor=types.SimpleNamespace(
            get_total_token_counts=lambda: types.SimpleNamespace(input_tokens=0, output_tokens=0)),
    )
    return u


def step(n=1, wait=None):
    # Timing 的 duration 是属性（end_time - start_time），不是构造参数
    t0 = time.time() - 6.2566
    st = ActionStep(
        step_number=n,
        timing=Timing(start_time=t0, end_time=time.time()),
        model_output="",
        token_usage=TokenUsage(input_tokens=2355, output_tokens=22),
    )
    if wait is not None:
        st._opsui_wait = wait
    return st


def ap(waited=5.231, decision="cancelled"):
    a = my_ui.Approval("run_python", {"code": "print(3 * 7)"})
    a.created = time.time() - waited
    a.decision = "pending"
    a.decide(decision)
    return a


def pending_card(a):
    """把一张卡冻成「还在等人点」的样子：画的时候 decision=pending。"""
    u = ui()
    was, a.decision = a.decision, "pending"
    card = u._approval_card(a, waited=5.0)
    a.decision = was
    return card


# ---- 1：卡从「等待你审批」改成终态 ------------------------------------------------------
a = ap()
u = ui()
my_ui.OpsUI._pending = [a]
my_ui.OpsUI._ap_cards = {a.id: pending_card(a)}
card = my_ui.OpsUI._ap_cards[a.id]
ok("1a 改前冻在待批", "等待你审批" in card.content and card.metadata["status"] == "pending",
   repr(card.content[-40:]))
last = [gr.ChatMessage(role="user", content="q"), card]
out = u._mark_interrupted(types.SimpleNamespace(steps=[TaskStep(task="q"), step()]), last)
ok("1b 改后没有待批字样", "等待你审批" not in card.content, repr(card.content[-46:]))
ok("1c 卡片 status 转 done", card.metadata["status"] == "done", str(card.metadata["status"]))
ok("1d 标题带上精确等待秒数", "等了 5.2s" in card.metadata["title"], card.metadata["title"])
ok("1e 原有消息一张不丢", out[:2] == last[:2] and len(out) == 3, "len=%d" % len(out))
# 措辞：断开这一路没人按停止，卡上不能写「随停止取消」（v1.3 犯过一次同类错，见 :708 注释）
ok("1f 卡片说的是「随中断取消」", "随中断取消" in card.content and "随停止取消" not in card.content,
   repr(card.content[-40:]))
ok("1g 标题同一条措辞", "随中断取消" in card.metadata["title"], card.metadata["title"])

# ---- 2：已中断标记 ---------------------------------------------------------------------
mark = out[-1]
ok("2a 标记标题是「已中断」而不是「已停止」", mark.metadata["title"].startswith("⏹ 已中断"),
   mark.metadata["title"])
ok("2b 标记里写了这项审批没等来点击", "1 项审批没等来点击" in mark.content)
ok("2c 标记里写了干等多少秒", "5.2s" in mark.content, repr(mark.content[-70:]))
ok("2d 标记 status=done（不会被折成待批气泡）", mark.metadata["status"] == "done")

# ---- 3：那笔没人领走的审批等待补进 payload ---------------------------------------------
st = step()
mem = types.SimpleNamespace(steps=[TaskStep(task="q"), st])
u._mark_interrupted(mem, last[:1])
ok("3a 等待挂回最后一个 ActionStep", abs(getattr(st, "_opsui_wait", 0.0) - 5.231) < 1e-3,
   str(getattr(st, "_opsui_wait", None)))
blob = my_ui.encode_memory(mem.steps)
ok("3b encode 之后 payload 里有 wait 这一格", '"wait": 5.231' in blob, blob[-120:])
back = my_ui.decode_memory(blob)
ok("3c 回灌读得出这一格（重启后仍在）", abs(getattr(back[-1], "_opsui_wait", 0.0) - 5.231) < 1e-6,
   str(getattr(back[-1], "_opsui_wait", None)))
d = ui()._stats(back)
ok("3d 状态条口径 task_wait 跟着读出来", abs(d["task_wait"] - 5.231) < 1e-6, str(d["task_wait"]))

# ---- 4：不重复计账 ----------------------------------------------------------------------
st2 = step(wait=1.5)  # 这一格已经有主（被下一个 ActionStep 领走过）
mem2 = types.SimpleNamespace(steps=[TaskStep(task="q"), st2])
u._mark_interrupted(mem2, last[:1])
ok("4a 已有归属的步不许被改写", abs(st2._opsui_wait - 1.5) < 1e-6, str(st2._opsui_wait))

st3 = step()
mem3 = types.SimpleNamespace(steps=[TaskStep(task="q"), st3])
u._mark_interrupted(mem3, last[:1])
u._mark_interrupted(mem3, last[:1])  # 同一题收尾被叫两次（不该存在，但账不能翻倍）
ok("4b 连跑两次账不翻倍", abs(st3._opsui_wait - 5.231) < 1e-3, str(st3._opsui_wait))

# ---- 5：脱线形状 —— 没有记忆 / 没有卡 / 已允许的卡不在管辖内 -----------------------------
ok("5a mem=None 不炸且照样补标记", len(u._mark_interrupted(None, last[:1])) == 2)
ok("5b 只有 TaskStep（没有 ActionStep）时不挂账",
   len(u._mark_interrupted(types.SimpleNamespace(steps=[TaskStep(task="q")]), last[:1])) == 2)
allowed = ap(decision="allowed")
my_ui.OpsUI._pending = [allowed]
my_ui.OpsUI._ap_cards = {}  # 已结算的卡早在画卡循环里摘走了，这里没有登记
o5 = ui()._mark_interrupted(types.SimpleNamespace(steps=[TaskStep(task="q"), step()]), last[:1])
ok("5c 不在登记表上的单不参与收尾", "项审批" not in o5[-1].content, o5[-1].content[:60])
ok("5d 那种情况下没有空等可报", "空等" not in o5[-1].metadata["title"], o5[-1].metadata["title"])

print("\n%s  (%d 条失败)" % ("全绿" if not FAIL else "失败：" + ",".join(FAIL), len(FAIL)))
sys.exit(1 if FAIL else 0)
