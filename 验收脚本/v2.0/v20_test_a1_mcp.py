# -*- coding: utf-8 -*-
"""A1＋A2 的离线断言：MCP 工具怎么挂、挡住了什么、真调用通不通、摘得干不干净。

全程**不打模型**（Dashscope 这个账号现在也不给打），所以「模型会不会正确使用这只外部工具」
不在这里断言，那是 E1 的 Q17/Q20 的活。这里断的是管路与闸门：

  A 装载：两个 server 连上、点名清单对上、provenance 贴上、模型清单里看得见、挂与不挂的字符差。
  B 真调用：time 返回的是本机真实时间；fetch 的 SSRF 护栏（回环／元数据地址）在；
          外部调用超时用的是我自己写的常量，不是 mcpadapt 那个不生效的默认值。
  C 摘除：detach 之后工具从 agent 上消失、system_prompt 回到原长、不留子进程。
  D 闸门反面：用一个**假 agent**（SimpleNamespace，只需要 .tools 和 ._mcp_bridge）逐条验
          「没点名不挂／破坏性名字拒收／撞名不覆盖／可执行文件不在只记录不抛」。
          为什么不能拿单例做这一组：attach 的语义是「一个 agent 一把桥」，第二次 attach
          直接返回旧桥（A09 断言的就是这条），拿单例连着 attach 四次只会拿到同一个桥，
          那三条反面用例一条都跑不到——2026-11-04 第一版就是这么红的。

跑法：smolagents/.venv/bin/python 验收脚本/v2.0/v20_test_a1_mcp.py
退出码 0 = 全绿。会起 stdio 子进程，全部由脚本自己收。

子进程计数只看**本进程名下**（pgrep -P getpid）：A1 上了他那个 7860 活应用之后，
应用自己合法持有 time/fetch 两个孩子，按名字全机器数会把别人的进程算成我的残留。
"""
import os
import re
import shutil
import subprocess
import sys
import time
import types
from datetime import datetime
from pathlib import Path

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

import my_mcp  # noqa: E402
from my_agent import agent  # noqa: E402

FAIL = []
N = 0
BRIDGES = []
TIME_EXE = str(my_mcp.SERVERS_DIR / "time/.venv/bin/mcp-server-time")
FS_EXE = my_mcp.SERVERS_DIR / "filesystem/dist/index.js"


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-44s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def attach(servers=None, agt=None):
    agt = agent if agt is None else agt
    b = my_mcp.attach(agt, servers)
    BRIDGES.append(b)
    return b


def fake_agent(*names):
    """假 agent：attach 只碰 .tools 和 ._mcp_bridge 这两样。"""
    return types.SimpleNamespace(tools={n: object() for n in names}, _mcp_bridge=None)


def count_children():
    """只数**本次运行自己起的**子进程。

    原来按名字全机器数：A1 上了他那个 7860 应用之后，活应用自己也合法持有 time/fetch 两个
    孩子，于是 A10「幂等只 2 个」、C05「摘干净剩 0 个」被别人的进程顶红了（2026-11-04 实测）。
    这一条要断的是「我挂的桥有没有把孩子收干净」，判据必须限定在自己名下。
    """
    r = subprocess.run(["pgrep", "-P", str(os.getpid()), "-f",
                        "mcp-server-time|mcp-server-fetch|v20_slow_server"],
                       capture_output=True, text=True)
    return len([x for x in r.stdout.split() if x])


BASE_TOOLS = set(agent.tools)
PROMPT_BASE = len(agent.system_prompt)
print(f"起点：工具 {len(BASE_TOOLS)} 只、system_prompt {PROMPT_BASE} 字符、本进程名下子进程 {count_children()} 个\n")

# ---- A 装载（真单例，挂一次） ----------------------------------------------
b = attach()
ok("A01 两个 server 都连上", set(b.clients) == {"time", "fetch"}, str(list(b.clients)) + str(b.skipped))
ok("A02 挂上三只工具", set(b.added) == {"get_current_time", "convert_time", "fetch"}, str(b.added))
ok("A03 一只都不该被挡下（清单与 server 对得上）", b.denied == [], str(b.denied))
ok("A04 原有工具一只没少", BASE_TOOLS <= set(agent.tools), str(sorted(BASE_TOOLS - set(agent.tools))))
ok("A05 provenance 贴到了工具上",
   agent.tools["fetch"]._mcp_server == "fetch" and "外部网络读" in agent.tools["fetch"]._mcp_risk
   and agent.tools["get_current_time"]._mcp_server == "time")
sp = agent.system_prompt
ok("A06 三只都出现在模型读得到的清单里",
   all(n in sp for n in b.added), str([n for n in b.added if n not in sp]))
ok("A07 fetch 的 schema 真带过去了（不是空壳）",
   {"url", "max_length", "start_index", "raw"} <= set(agent.tools["fetch"].inputs)
   and len(agent.tools["fetch"].description) > 40, str(sorted(agent.tools["fetch"].inputs)))
DELTA = len(sp) - PROMPT_BASE
ok("A08 挂 MCP 的 prompt 代价在预算内（<3000 字符）", 0 < DELTA < 3000, f"+{DELTA} 字符")
ok("A09 describe 说得清挂了几个", "time×2" in b.describe() and "fetch×1" in b.describe(), b.describe())
ok("A10 重复 attach 幂等：返回同一把桥、不重连", attach() is b and count_children() == 2,
   f"子进程 {count_children()}")

# ---- B 真调用（不经模型） --------------------------------------------------
now = str(agent.tools["get_current_time"].forward(timezone="Asia/Shanghai"))
stamp = re.search(r'"datetime":\s*"([^"]+)"', now)
ok("B01 get_current_time 给的是真时间（与本机相差 <120s）",
   bool(stamp) and abs((datetime.fromisoformat(stamp.group(1))
                        - datetime.now().astimezone()).total_seconds()) < 120,
   stamp.group(1) if stamp else now[:80])
conv = str(agent.tools["convert_time"].forward(source_timezone="Asia/Shanghai", time="12:00",
                                               target_timezone="America/New_York"))
ok("B02 convert_time 会换到别的时区", "America/New_York" in conv and "12:00:00+08:00" in conv,
   conv[:60].replace("\n", " "))
f = agent.tools["fetch"]
loop = str(f.forward(url="http://127.0.0.1:9/x"))
meta = str(f.forward(url="http://169.254.169.254/latest/meta-data/"))
ok("B03 fetch 拒打回环地址（SSRF 护栏在）", "not a public address" in loop, loop[:66])
ok("B04 fetch 拒打云元数据地址", "not a public address" in meta, meta[:66])
ok("B05 server 侧报错是文本不是异常（模型读得到、能改道）", "Error executing tool" in loop)
t0 = time.time()
pub = str(f.forward(url="https://example.com", max_length=200))
ok("B06 公网抓取在 30s 超时内拿到正文", "example.com" in pub and time.time() - t0 < 30,
   f"{time.time() - t0:.1f}s · {pub[:56]}")

# 外部调用的超时：假 server 的 nap 睡 8 秒 + 把常量压到 2 秒 → 必须在 2 秒档断掉。
# 这一条挂到**假 agent** 上而不是单例：attach 的语义是「一个 agent 一把桥」，单例上此刻已经
# 挂着 A 组那把桥（b），再 attach 会原样返回 b——nap 挂不上，而且那次 detach 会把 b 一起拆了，
# C 组读到的 names 就成了空集。2026-11-04 的 B07/B08/C07 三条红是同一个根因。
nap_agent = fake_agent()
my_mcp.MCP_CALL_TIMEOUT_S = 2.0
slow = attach({"napserver": {"argv": [sys.executable,
                                      str(Path(__file__).resolve().parent / "v20_slow_server.py")],
                             "tools": {"nap": "睡"}}}, nap_agent)
ok("B07 假 server 也挂得上（stdio 通道与 server 种类无关）", "nap" in slow.added, str(slow.skipped))
ok("B07b 挂到假 agent 上，没碰单例那把桥", agent._mcp_bridge is b and "nap" not in agent.tools)
if "nap" in slow.added:
    t0 = time.time()
    try:
        nap_agent.tools["nap"].forward(seconds=8)
        ok("B08 挂住的外部调用会被超时砍掉", False, "睡完 8 秒都没断 → 超时没生效")
    except Exception as e:  # noqa: BLE001
        el = time.time() - t0
        ok("B08 挂住的外部调用会被超时砍掉", "Timed out" in str(e) and 1.8 <= el <= 4.0,
           f"{el:.1f}s · {type(e).__name__}")
else:
    ok("B08 挂住的外部调用会被超时砍掉", False, "nap 没挂上")
my_mcp.MCP_CALL_TIMEOUT_S = 30.0
my_mcp.detach(slow)

# ---- C 摘除与残留 ----------------------------------------------------------
names = set(b.added)
my_mcp.detach(b)
after = set(agent.tools)
ok("C01 detach 后外部工具从 agent 上摘干净", not (names & after))
ok("C02 原有工具一只没丢", BASE_TOOLS <= after, str(sorted(BASE_TOOLS - after)))
ok("C03 system_prompt 回到原长", len(agent.system_prompt) == PROMPT_BASE,
   f"{PROMPT_BASE} → 挂上 {PROMPT_BASE + DELTA} → 摘掉 {len(agent.system_prompt)}")
ok("C04 agent 上那把桥的记号也清了", getattr(agent, "_mcp_bridge", None) is None)
time.sleep(1.0)
ok("C05 不留子进程", count_children() == 0, f"残留 {count_children()} 个")
my_mcp.detach(b)
ok("C06 重复 detach 不炸", True)
ok("C07 摘掉之后还能再挂上（桥记号真的清了）", set(attach().added) == names,
   f"期望 {sorted(names)}")
my_mcp.detach(BRIDGES[-1])

# ---- D 闸门反面（每个用例一把桥，全用假 agent） ------------------------------
d1 = attach({"time": {"argv": [TIME_EXE], "tools": {"convert_time": "读"}}}, fake_agent())
ok("D01 server 有、清单没点名的工具不挂",
   set(d1.added) == {"convert_time"} and any("get_current_time" in x and "点名" in x for x in d1.denied),
   str(d1.denied))
my_mcp.detach(d1)

d2 = attach({"time": {"argv": ["/nonexistent/bin/mcp-server-time"], "tools": {"get_current_time": "读"}}},
            fake_agent())
ok("D02 可执行文件不在 → 记录原因，不抛",
   "time" in d2.skipped and "可执行文件不在" in d2.skipped["time"] and not d2.added, str(d2.skipped))
ok("D03 缺 server 时 describe 会如实讲", "未装" in d2.describe() or "可执行文件" in d2.describe(),
   d2.describe())
my_mcp.detach(d2)

d3 = attach({"time": {"argv": [TIME_EXE], "tools": {"get_current_time": "读", "convert_time": "读"}}},
            fake_agent("get_current_time"))
ok("D04 与已有工具撞名就不覆盖（哪怕清单点了名）",
   "get_current_time" not in d3.added and any("get_current_time" in x and "撞名" in x for x in d3.denied)
   and "convert_time" in d3.added, str(d3.denied))
my_mcp.detach(d3)

for bad in ("delete_file", "remove_path", "move_note", "write_note", "reset_all"):
    ok(f"D05 破坏性词根 {bad} 进不了工具表", bool(my_mcp.DESTRUCTIVE_RX.search(bad)))
for good in ("get_current_time", "fetch", "nap", "search_docs"):
    ok(f"D06 正常名字 {good} 不误伤", not my_mcp.DESTRUCTIVE_RX.search(good))

if FS_EXE.exists() and shutil.which("node"):
    d4 = attach({"filesystem": {"argv": ["node", str(FS_EXE), str(Path(__file__).resolve().parent / "run")],
                                "tools": {"read_file": "读", "write_file": "写", "move_file": "移动"}}},
                fake_agent("read_file"))
    destructive = [x for x in d4.denied if "破坏性" in x]
    collide = [x for x in d4.denied if "撞名" in x]
    ok("D07 真 filesystem server：write_file/move_file 被拒收",
       len(destructive) == 2 and not ({"write_file", "move_file"} & set(d4.added)),
       "; ".join(destructive) or str(d4.skipped))
    ok("D08 真 filesystem server：它的 read_file 因撞名不覆盖我那只",
       len(collide) == 1 and set(d4.added) == set(),
       "; ".join(collide) or str(d4.skipped))
    ok("D09 filesystem 的其它工具（目录/搜索类）没被点名，一只都不挂",
       all("点名" in x for x in d4.denied if "不覆盖" not in x and "破坏性" not in x),
       str([x for x in d4.denied if "不覆盖" not in x and "破坏性" not in x])[:200])
    my_mcp.detach(d4)
else:
    print("D07/D08/D09 跳过：没有 node 或 filesystem 未构建")

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for x in FAIL:
    print("  FAIL:", x)
for bb in BRIDGES:
    my_mcp.detach(bb)
print(f"收尾子进程：{count_children()} 个")
sys.exit(0 if not FAIL and count_children() == 0 else 1)
