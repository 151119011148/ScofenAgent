# -*- coding: utf-8 -*-
"""证明「不改的那几档一字未变」：拿 .rollback/v1.8/ 里那份改前代码当参照，逐字比渲染结果。

为什么不用 AST 等价：这一刀确实动了源码（多了 shown 形参、多了两个字典项），AST 不可能逐字相同。
所以改成**按调用形状比结果**——凡是不带 shown 的调用（停止、拒绝、允许、超时四档全在这类里），
新代码必须和旧代码产出完全一样的 content 与 metadata。带 shown 的只有断开收尾那一条，
那是这次唯一的行为变化，由 v18_test_interrupt.py 的 1f/1g 正面断言。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_test_nochange.py
"""
import importlib.util
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
from smolagents.memory import ActionStep, TaskStep  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

LIVE = "/Users/gaoying/Desktop/study/ai学习/smolagents/my_ui.py"
OLD = "/Users/gaoying/Desktop/study/ai学习/smolagents/.rollback/v1.8/my_ui.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


live = load("my_ui_live", LIVE)
old = load("my_ui_old", OLD)
FAIL = []


def ok(n, cond, detail=""):
    print("%-30s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def bare(mod):
    # _step_card 的正文要读本题累计的那几个数（:741），两边给同一组常量才比得出差异。
    u = mod.OpsUI.__new__(mod.OpsUI)
    u._run_in, u._run_out, u._run_secs, u._run_wait = 2355, 22, 6.3, 0.0
    return u


def mk(mod, decision, waited):
    a = mod.Approval("run_python", {"code": "print(3 * 7)"})
    a.created = time.time() - waited
    a.decision = "pending"
    a.decide(decision)
    return a


# ---- 1：审批卡，四档不带 shown 的渲染必须逐字相同 ----------------------------------------
for decision in ("pending", "allowed", "denied", "cancelled", "timeout"):
    for waited in (0.0, 0.04, 5.231, 600.0):
        a_new = mk(live, decision, waited)
        a_old = mk(old, decision, waited)
        c_new = bare(live)._approval_card(a_new, waited)
        c_old = bare(old)._approval_card(a_old, waited)
        same = c_new.content == c_old.content and c_new.metadata == c_old.metadata
        ok("卡 %-9s waited=%-6s" % (decision, waited), same,
           "" if same else "\n   new=%r\n   old=%r" % ((c_new.content[-60:], c_new.metadata),
                                                       (c_old.content[-60:], c_old.metadata)))

# ---- 2：断开收尾那张卡是**唯一**变了样子的一档 ------------------------------------------
a = mk(live, "cancelled", 5.231)
c_new = bare(live)._approval_card(a, 5.231, shown="cancelled_by_reload")
c_old = bare(old)._approval_card(mk(old, "cancelled", 5.231), 5.231)
ok("带 shown 与旧版不同", c_new.content != c_old.content and "随中断取消" in c_new.content,
   repr(c_new.content[-30:]))
ok("带 shown 时 dot 仍是 ⏹", c_new.metadata["title"].startswith("⏹"), c_new.metadata["title"])

# ---- 3：只有新措辞进了字典，老键一个没动、一个没删 --------------------------------------
for k in ("pending", "allowed", "denied", "cancelled", "timeout"):
    ok("LABEL[%s] 未变" % k, live.DECISION_LABEL[k] == old.DECISION_LABEL[k], live.DECISION_LABEL[k])
    ok("DOT[%s]   未变" % k, live.DECISION_DOT[k] == old.DECISION_DOT[k], live.DECISION_DOT[k])
ok("DENIED_OBSERVATION 一字未动（模型可见串）",
   live.DENIED_OBSERVATION == old.DENIED_OBSERVATION)
ok("DENIED_VERDICT 一字未动", live.DENIED_VERDICT == old.DENIED_VERDICT)
# STATE_LABEL 的允许增量：D8 那一刀加 interrupted，P0-4 那一刀加 plan_denied（否决计划
# 不能写成「已停止」），P1-a 那一刀加 dup_fused（绕圈被拦下收尾也不能写成「已停止」——
# 那是用户在告自己的状），v2.0 那一刀加 model_refused（服务商欠费／风控拒收时人也没按任何东西，
# 今天实测 0.32 秒就抛，写成「已停止」同样是用户在自己头上领一件没做过的事）。
# 老键仍然一个没动、一个没删——所以下面这条断言只核对**新增集合**，
# 逐键相等的断言原样保留。
ok("STATE_LABEL 只多 interrupted+plan_denied+dup_fused+model_refused",
   set(live.STATE_LABEL) - set(old.STATE_LABEL)
   == {"interrupted", "plan_denied", "dup_fused", "model_refused"}
   and all(live.STATE_LABEL[k] == old.STATE_LABEL[k] for k in old.STATE_LABEL),
   str(set(live.STATE_LABEL) - set(old.STATE_LABEL)))
ok("plan_denied 不与 stopped 同字（P0-4 的分开要求）",
   live.STATE_LABEL["plan_denied"] != live.STATE_LABEL["stopped"],
   "%s / %s" % (live.STATE_LABEL["plan_denied"], live.STATE_LABEL["stopped"]))
ok("MEM_FIELDS / MEM_FMT 未动",
   live.MEM_FIELDS == old.MEM_FIELDS and live.MEM_FMT == old.MEM_FMT)

# ---- 4：步骤卡（没人改了它）对同一份 step 产出必须逐字相同 -------------------------------
def step(obs=None, err=None, wait=None):
    t0 = time.time() - 6.2566
    from smolagents.memory import ActionStep as A
    s = A(step_number=1, timing=Timing(start_time=t0, end_time=time.time()),
          model_output="我要打印 3*7", code_action="print(3 * 7)",
          observations=obs, error=err, token_usage=TokenUsage(input_tokens=2355, output_tokens=22))
    if wait is not None:
        s._opsui_wait = wait
    return s


for obs in (None, "", live.DENIED_OBSERVATION["cancelled"], live.DENIED_OBSERVATION["denied"],
            live.DENIED_OBSERVATION["timeout"], "21"):
    for wait in (None, 5.231):
        # 同一份 step 对象喂两边，理由见下面第 5 段那条注释（墙钟漂移不是口径差异）。
        shared = step(obs=obs, wait=wait)
        c_new = bare(live)._step_card(shared)
        c_old = bare(old)._step_card(shared)
        same = (c_new is None) == (c_old is None) and (
            c_new is None or (c_new.content == c_old.content and c_new.metadata == c_old.metadata))
        ok("步骤卡 obs=%r wait=%s" % ((obs or "")[:14], wait), same,
           "" if same else "\n   new=%r\n   old=%r" % ((c_new.content[-70:], c_new.metadata),
                                                       (c_old.content[-70:], c_old.metadata)))

# ---- 5：_stats 对同一份 steps 的读数必须一致（补账那条路不改变已有口径） -----------------
def steps_of(wait=None):
    t0 = time.time() - 6.2566
    s = ActionStep(step_number=1, timing=Timing(start_time=t0, end_time=time.time()),
                   token_usage=TokenUsage(input_tokens=2355, output_tokens=22))
    if wait is not None:
        s._opsui_wait = wait
    return [TaskStep(task="q"), s]


for wait in (None, 5.231):
    a = bare(live)
    b = bare(old)
    for m in (a, b):
        m.agent = types.SimpleNamespace(
            max_steps=8, model=types.SimpleNamespace(model_id="qwen-plus"),
            monitor=types.SimpleNamespace(
                get_total_token_counts=lambda: types.SimpleNamespace(input_tokens=0, output_tokens=0)))
    # 一份 step 对象喂两边，不是两边各造一份「看起来一样」的：Timing 的 duration 是
    # end-start 现算的，各造各的就会差到 1e-6 秒（第一版这么写，task_secs 假红过两次——
    # 差的是造对象那一瞬的墙钟，不是两份代码的口径）。两个模块 import 的是同一个
    # smolagents.memory.ActionStep，所以 isinstance 判定在两边都成立，共用对象是安全的。
    shared = steps_of(wait)
    d1, d2 = a._stats(list(shared)), b._stats(list(shared))
    ok("stats wait=%s" % wait, d1 == d2, "" if d1 == d2 else "%r vs %r" % (d1, d2))

print("\n%s  (%d 条失败)" % ("全绿" if not FAIL else "失败：" + ",".join(str(f) for f in FAIL), len(FAIL)))
sys.exit(1 if FAIL else 0)
