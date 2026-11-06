# -*- coding: utf-8 -*-
"""A2 的离线闸：挂上来的外部工具**是不是每一只都过了审批门**，卡上说不说得清它是谁。

这一份测的是「装配顺序 + 显示 + 旁路」，不是协议本身（协议那半在 v20_test_a1_mcp.py，42 条全绿）：

  A 装配事实：MCP 工具带上 _opsui_gated；名单由桥现拼；只读那三只本地手没被误伤；
             第二个 OpsUI 不会把门套成两层。
  B 真批真拒：真起一条 worker 线程去调真 MCP 工具，看它**卡在门上等不等**、
             批了才真跑、拒了返回的就是那句「没有执行」；卡上带来源与风险档；
             同名同参的第二次在**开卡之前**就被查重层挡掉（证明查重套在审批外面）。
  C 摘除：detach 之后工具没了、名单回到只有 GATED_TOOLS、模型清单里读不到 fetch、不留子进程。
  D 旁路：CLI 那条路（import my_agent）一个 MCP 工具都不挂；
          my_coding_agent 里那批模块级原件没被 UI 写过（门是 copy.copy 出来的）。

口径两条，别误读：
  · **不打模型**（Dashscope 这个账户现在还是 400 Access denied，见 run/v20_eval_auth-blocked.out）。
    模型会不会正确用外部工具，是 E1 的 Q17/Q20 的活。
  · OpsUI 一构造就会 attach（这是 A2 的装法：门装在工具挂上之后）。所以这份脚本同时也是
    「UI 起得来吗」这一问的证据——它真的构造了两次 OpsUI。

跑法：smolagents/.venv/bin/python 验收脚本/v2.0/v20_test_a2_gate.py
产物：run/v20_test_a2_gate.out
退出码 0 = 全绿。
"""
import os
import subprocess
import sys
import threading
import time

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

import my_coding_agent  # noqa: E402
import my_mcp  # noqa: E402
import my_ui  # noqa: E402
from my_ui import DENIED_OBSERVATION, DUP_MARK, GATED_TOOLS, OpsUI  # noqa: E402
from my_agent import agent  # noqa: E402

FAIL = []
N = 0
MCP_NAMES = {"get_current_time", "convert_time", "fetch"}
LOCAL_RO = ("read_file", "list_dir", "grep_files")


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-46s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def wait_pending(before, timeout=8.0):
    """等到队列里出现第 before+1 张单子，返回那张（超时返回 None）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = OpsUI._pending
        if len(snap) > before:
            return snap[before]
        time.sleep(0.02)
    return None


def gated_call(name, deadline=8.0, **kw):
    """在**另一条线程**里点一只已装门的工具，返回 (线程, 结果格, 那张审批单或 None)。

    为什么要开线程：门的语义就是「阻塞调用方直到有人点按钮」，在本线程直接调就是自己等自己。
    真界面里调用方是 _worker 那条线程，点按钮的是 UI 线程——这里照这个分工摆。
    """
    box = {}
    before = len(OpsUI._pending)

    def run():
        try:
            box["out"] = str(agent.tools[name](**kw))
        except BaseException as e:  # noqa: BLE001
            box["exc"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, box, wait_pending(before, deadline)


# _gated_call 在入队那一刻判「本轮是不是已经被停止了」（D7 那个临界区）：
# _run_seq <= _cancelled_before 就直接算取消、压根不开卡。真界面里这一格由 _respond:1381 抬，
# 本脚本不走 _respond，所以手动抬一次——不抬的话下面每一条 B 组都会「没人批也秒回」。
OpsUI._run_seq += 1

ui = OpsUI(agent, file_upload_folder="./data")
print(f"起点：工具 {len(agent.tools)} 只 · 桥 {ui._mcp.describe()} · 门名单 {sorted(ui._gate_names())}\n")

# ---- A 装配 ---------------------------------------------------------------
ok("A01 三只外部工具都进了审批门",
   all(getattr(agent.tools[n], "_opsui_gated", False) for n in MCP_NAMES),
   str([n for n in MCP_NAMES if not getattr(agent.tools.get(n, object()), "_opsui_gated", False)]))
ok("A02 同一只上也套了查重（两层都在）",
   all(getattr(agent.tools[n], "_opsui_dedup", False) for n in MCP_NAMES))
ok("A03 门名单 = 本地两只 + 桥上现挂的，没有旁路",
   set(ui._gate_names()) == set(GATED_TOOLS) | set(ui._mcp.added), str(ui._gate_names()))
ok("A04 本地只读那三只没被误伤（还是不打扰人）",
   not any(getattr(agent.tools[n], "_opsui_gated", False) for n in LOCAL_RO))
ok("A05 桥上挂了多少，门就套多少（gated 是 added 的投影）",
   set(ui._mcp.gated) == set(ui._mcp.added) and len(ui._mcp.gated) == 3, str(ui._mcp.gated))
ok("A06 状态条上有 MCP 这一格",
   "MCP" in ui._status_html("idle") and "time×2、fetch×1" in ui._status_html("idle"),
   ui._mcp_pill())

wrapped_before = {n: id(agent.tools[n]) for n in MCP_NAMES | set(GATED_TOOLS)}
ui2 = OpsUI(agent, file_upload_folder="./data")
ok("A07 第二个 OpsUI 没把门套成两层（同一只工具还是同一个对象）",
   all(id(agent.tools[n]) == wrapped_before[n] for n in wrapped_before),
   str([n for n in wrapped_before if id(agent.tools[n]) != wrapped_before[n]]))
ok("A08 第二个 OpsUI 复用同一把桥，没有重连出第二批子进程",
   ui2._mcp is ui._mcp and ui._mcp.clients == ui2._mcp.clients)

# ---- B 真批 / 真拒（真 MCP server，真子进程） --------------------------------
t, box, ap = gated_call("get_current_time", timezone="Asia/Shanghai")
ok("B01 外部工具真会卡在门上等人（不是默默跑完）",
   ap is not None and not box, "" if ap else "卡没开出来，调用直接返回了：" + str(box))
ok("B02 单子上带着来源与风险档（这就是审批卡上那一行）",
   ap is not None and ap.tool == "get_current_time" and ap.source == "time"
   and ap.risk == "读，无副作用", f"{getattr(ap, 'source', None)!r} / {getattr(ap, 'risk', None)!r}")
card = ui._approval_card(ap, 0.1) if ap else None
ctext = str(card.content) if card else ""
ok("B03 卡片正文写着「外部 MCP server」＋server 名",
   "**来源** 外部 MCP server `time`" in ctext and "风险：读，无副作用" in ctext, ctext[:70].replace("\n", " "))
ok("B04 卡片仍留着原来那两格（工具 / 参数），只是多一行来源",
   ctext.startswith("**工具** `get_current_time`") and "**参数**" in ctext)
if ap:
    ap.decide("allowed")
t.join(15)
ok("B05 点了「✔ 允许」才真的执行，拿回的是真时间",
   "datetime" in box.get("out", "") and not box.get("exc"), box.get("out", "")[:56])

t, box, ap = gated_call("get_current_time", timezone="Europe/Berlin")
if ap:
    ap.decide("denied")
t.join(15)
ok("B06 点了「✖ 拒绝」：返回的是「没有执行」那句，server 那边没跑",
   box.get("out") == DENIED_OBSERVATION["denied"] and ap is not None and ap.decision == "denied",
   box.get("out", "")[:56])

t, box, ap = gated_call("fetch", url="http://127.0.0.1:9/x")
if ap:
    ap.decide("allowed")
t.join(30)
ok("B07 批了之后外部 server 的报错是文本回去的（模型读得到）",
   "not a public address" in box.get("out", ""), box.get("out", "")[:60])

before = len(OpsUI._pending)
t, box, ap2 = gated_call("fetch", url="http://127.0.0.1:9/x", deadline=2.0)
ok("B08 同名同参第二次**在开卡之前**就被查重挡掉（查重套在审批外）",
   DUP_MARK in box.get("out", "") and len(OpsUI._pending) == before,
   box.get("out", "")[:52] + f" | 队列 {before}→{len(OpsUI._pending)}")
t.join(5)

wf = agent.tools["write_file"]
t, box, ap3 = gated_call("write_file", path="笔记/a2.txt", content="hi")
card3 = ui._approval_card(ap3, 0.1) if ap3 else None
ok("B09 本地工具的卡片不写来源（source 是 None，不是空串）",
   ap3 is not None and ap3.source is None and "来源" not in str(card3.content),
   str(card3.content)[:56].replace("\n", " ") if card3 else "没开出卡")
if ap3:
    ap3.decide("denied")
t.join(15)

# ---- C 摘除 ---------------------------------------------------------------
my_mcp.detach(ui._mcp)
ok("C01 detach 后外部工具从 agent 上消失", not (MCP_NAMES & set(agent.tools)),
   str(sorted(MCP_NAMES & set(agent.tools))))
ok("C02 门名单回到只有本地那两只（名单跟着桥走，不是写死的）",
   set(ui._gate_names()) == set(GATED_TOOLS), str(ui._gate_names()))
ok("C03 模型的清单里读不到 fetch 了", "fetch" not in agent.system_prompt)
ok("C04 本地七只手一只没少",
   {"read_file", "list_dir", "grep_files", "write_file", "run_python",
    "max_drawdown", "annualized_volatility", "final_answer"} <= set(agent.tools))
time.sleep(1.0)
# 只数本进程名下的孩子：他那个 7860 活应用合法持有自己的 time/fetch 两个子进程，
# 全机器按名字数会把别人的进程算成我的残留（2026-11-04 就红在这）。
r = subprocess.run(["pgrep", "-P", str(os.getpid()), "-f", "mcp-server-time|mcp-server-fetch"],
                   capture_output=True, text=True)
ok("C05 摘除不留本进程名下的子进程", not r.stdout.split(), f"残留 {len(r.stdout.split())} 个")

# ---- D 旁路：CLI 那条路一个外部工具都不挂 --------------------------------
code = ("import os, subprocess, sys; sys.path.insert(0, '/Users/gaoying/Desktop/study/ai学习/smolagents');"
        "import my_agent; print(sorted(my_agent.agent.tools));"
        "print(hasattr(my_agent.agent, '_mcp_bridge'));"
        "print(len(subprocess.run(['pgrep', '-P', str(os.getpid()), '-f',"
        " 'mcp-server-time|mcp-server-fetch'], capture_output=True, text=True).stdout.split()))")
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
names = r.stdout.splitlines()[-2] if len(r.stdout.splitlines()) >= 2 else r.stdout
ok("D01 命令行那条路（import my_agent）不连 MCP：工具表里还是七只",
   "get_current_time" not in names and "fetch" not in names and "True" not in r.stdout.splitlines()[-1],
   names[:110] + " | _mcp_bridge=" + r.stdout.splitlines()[-1])
ok("D02 my_agent 那一侧也没起子进程（数的是那个子进程自己名下）",
   len(r.stdout.splitlines()) >= 3 and r.stdout.splitlines()[-1] == "0",
   "孩子数=" + (r.stdout.splitlines()[-1] if r.stdout.splitlines() else "无输出"))
ok("D03 门套在副本上：my_coding_agent 的模块级原件没被写过",
   not hasattr(my_coding_agent.write_file, "_opsui_gated")
   and not hasattr(my_coding_agent.run_python, "_opsui_gated"))

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for x in FAIL:
    print("  FAIL:", x)
sys.exit(0 if not FAIL else 1)
