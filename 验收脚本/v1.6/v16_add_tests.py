# -*- coding: utf-8 -*-
"""把第 5、6 两节插进 /Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_test.py 的收尾打印之前。"""
import pathlib

NEW = '''
# =========================== 5) V7：侧栏高亮跟着绑定走 =====================
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
OpsUI._pending_wait = 0.0
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(8)"})
time.sleep(0.4)
ui._decide("allowed")
th.join(3)
ck("6c 门结算完把这一格等待过账（等下一个到达的 ActionStep 领走）",
   OpsUI._pending_wait >= 0.3, OpsUI._pending_wait)

OpsUI._run_seq, OpsUI._cancelled_before = 21, 21
OpsUI._pending_wait = 0.0
calls.clear()
th, box = gate_in_thread(ui, {"code": "print(9)"})
th.join(3)
ck("6d 入队即按取消：等待记作 0，不给下一步挂上一格没发生过的等待",
   OpsUI._pending_wait < 0.05, OpsUI._pending_wait)

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
threading.Timer(0.5, lambda: ui8._decide("allowed")).start()
frames8 = list(ui8._respond("把 73 打印出来", sid8))
last8 = frames8[-1]
step_cards = [m for m in last8[0] if (m.metadata or {}).get("title", "").startswith("🛠")]
appr_cards = [m for m in last8[0] if "待批" in (m.metadata or {}).get("title", "")]
ck("6e 端到端：真等了 0.5 秒的审批，工具照旧执行",
   state6["returned"] == "原工具跑完了", state6["returned"])
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
ck("6n 等待秒数不进记忆库（字段白名单不认它）：重启后老卡读不出这一格，是本轮的边界",
   "_opsui_wait" not in blob6 and not hasattr(back6[0], "_opsui_wait"), blob6[:160])
ck("6o 但总时长照旧进得去（V6 的口径没被 V8 碰坏）", back6[0].timing.duration == 1.0, back6[0].timing.duration)

'''

p = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_test.py")
t = p.read_text(encoding="utf-8")
marker = '\nprint()\nprint("TMP DB:"'
assert marker in t, "找不到收尾打印"
t = t.replace(marker, NEW + marker, 1)
p.write_text(t, encoding="utf-8")
print("lines:", len(t.splitlines()))
