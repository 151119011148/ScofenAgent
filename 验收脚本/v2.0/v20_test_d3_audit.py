# -*- coding: utf-8 -*-
"""D3 的离线闸：每一次工具调用是不是真留下一行，那一行说没说清「谁批的」。

全程**不打模型**（Dashscope 这个账户还是 400 Access denied，见 run/v20_eval_auth-blocked.out）：
这里断的是「调用点 → 审计行」这一段，模型那一侧的调用序列由 E1 补。

三条口径先说清，别把审计读成流水账：
  · 审计装在**查重层**（最外面那只），所以「被查重挡掉的两次」也有行——这一份记的是
    「模型发出过什么」，不是「跑成功了什么」。status 一共四档：ran / dup-blocked /
    dup-fused / raised（工具自己抛异常，比如 guarded() 的越界）。
  · `decision` 和 `status` 是两回事：批了没批看 decision（allowed/denied/cancelled/timeout），
    **null = 这一只工具根本不过审批门**（本地只读那五只手）。所以「拒绝了」那一行
    的 status 照旧是 ran——调用走完了，只是没执行，返回的是那句「未产生任何副作用」。
  · 参数只进 sha1（前 16 位）＋前 200 字符：write_file 的正文、fetch 抓回的页面都能几百 KB，
    全文另有其主（.agent-staging/ 和会话记忆），审计只负责定位。

审计文件指到临时目录，不写他那份真的 .agent-audit.jsonl；会话删除那一条用临时 sqlite，
不碰 .agent-history.sqlite3。

跑法：smolagents/.venv/bin/python 验收脚本/v2.0/v20_test_d3_audit.py
产物：run/v20_test_d3_audit.out
"""
import inspect
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import gradio as gr

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

import my_audit  # noqa: E402
import my_mcp  # noqa: E402
import my_ui  # noqa: E402
from my_agent import agent  # noqa: E402
from my_ui import DUP_FUSE_MARK, DUP_MARK, OpsUI  # noqa: E402

FAIL = []
N = 0
TMP = Path(tempfile.mkdtemp(prefix="v20-d3-"))
# 产品默认那份：**按模块位置算**，不读 my_audit.AUDIT_PATH——后者会被 AGENT_AUDIT_PATH 顶掉
# （本套跑在带不带这个变量两种场合下都必须全绿，2026-11-04 第一版就是拿运行时值当默认值，
# 带变量跑时 R27/R28 比的是 /tmp 下那个文件名，当场判错）。
DEFAULT_AUDIT = Path(my_audit.__file__).resolve().parent / ".agent-audit.jsonl"
my_audit.AUDIT_PATH = TMP / "audit.jsonl"
KEYS = {"ts", "iso", "dur_s", "args_sha1", "args_head", "status", "tool", "src",
        "n", "sid", "run", "step", "decision", "wait_s"}


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-46s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def rows():
    p = my_audit.AUDIT_PATH
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def last():
    r = rows()
    return r[-1] if r else {}


def fresh():
    """换题开局：把查重的三格和审批队列清干净（真界面里这段在 _stream_response 的同一把锁里）。"""
    with OpsUI._gate_lock:
        OpsUI._seen_calls.clear()
        OpsUI._dup_blocked = 0
        OpsUI._dup_tripped = False
        OpsUI._pending.clear()


def call_tool(name, decision="allowed", timeout=8.0, **kw):
    """在另一条线程里点一只工具；过审批门的会等出一张单，按下给的 decision 结算。

    返回 (结果格, 那张单或 None, 这一行审计)。
    """
    before = len(OpsUI._pending)
    box = {}

    def run():
        try:
            box["out"] = str(agent.tools[name](**kw))
        except BaseException as e:  # noqa: BLE001
            box["exc"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    ap = None
    if name in GATED:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if len(OpsUI._pending) > before:
                ap = OpsUI._pending[before]
                break
            time.sleep(0.02)
        if ap is not None and decision is not None:
            ap.decide(decision)
    t.join(40)
    return box, ap, last()


# OpsUI 一构造就 attach + 装三门（A2 的装法）；这一份因此也是「带 MCP 的 UI 起得来」的证据。
OpsUI._run_seq += 1  # 不抬这一格，D7 那个临界区会把每张单直接判成 cancelled
ui = OpsUI(agent, file_upload_folder="./data")
GATED = set(ui._gate_names())
print(f"起点：工具 {len(agent.tools)} 只 · 过门的 {sorted(GATED)} · 审计 {my_audit.stats()['lines']} 行 "
      f"→ {my_audit.AUDIT_PATH}\n")

# ---- R1 每一次调用都留一行 --------------------------------------------------
fresh()
box, ap, r = call_tool("read_file", path="smolagents/my_agent.py", lines=3)
ok("R01 本地只读工具也落一行（它可不过审批门）", r.get("tool") == "read_file" and r.get("status") == "ran",
   json.dumps({k: r.get(k) for k in ("tool", "src", "status", "decision")}, ensure_ascii=False))
ok("R02 不过门的工具 decision 是 null，不是空串", "decision" in r and r["decision"] is None, repr(r.get("decision")))
ok("R03 来源这一格分得清本地／外部：本地是 local", r.get("src") == "local", r.get("src"))
ok("R04 参数只进摘要：sha1 16 位＋head，正文不进审计",
   len(r.get("args_sha1", "")) == 16 and "my_agent" in r.get("args_head", ""), r.get("args_sha1"))
ok("R05 一次调用恰好一行", len(rows()) == 1, f"{len(rows())} 行")

# ---- R6 sid / run / step 三格是真的从当前那一轮取的 ---------------------------
fresh()
agent.step_number = 5
OpsUI._audit_sid = "77"
call_tool("list_dir", path="smolagents")
r = last()
ok("R06 审计行带着会话 id 与本轮号（worker 线程读的是类级那一格）",
   r.get("sid") == "77" and r.get("run") == OpsUI._run_seq, json.dumps({k: r.get(k) for k in ("sid", "run")}))
ok("R07 step 取的是框架那个实时属性（agent.step_number，agents.py:543）",
   r.get("step") == 5, f"set 5 → row {r.get('step')}")
agent.step_number = 0

# ---- R8 外部工具：来源、风险档、批没批 ---------------------------------------
fresh()
if "get_current_time" in GATED:
    box, ap, r = call_tool("get_current_time", decision="allowed", timezone="Asia/Shanghai")
    ok("R08 外部工具那一行写着 mcp:<server> 和风险档",
       r.get("src") == "mcp:time" and r.get("risk") == "读，无副作用", json.dumps({k: r.get(k) for k in ("src", "risk")}))
    ok("R09 批过的行带着 decision=allowed 与等待秒数",
       r.get("decision") == "allowed" and isinstance(r.get("wait_s"), float) and r["wait_s"] >= 0.0,
       f"{r.get('decision')} / {r.get('wait_s')}")
    ok("R10 真时间确实回来了", "datetime" in box.get("out", ""), box.get("out", "")[:40].replace("\n", " "))

    fresh()
    box, ap, r = call_tool("fetch", decision="denied", url="https://example.com")
    ok("R11 拒了的行照样在，decision=denied", r.get("decision") == "denied" and r.get("status") == "ran",
       json.dumps({k: r.get(k) for k in ("tool", "src", "status", "decision")}, ensure_ascii=False))
    ok("R12 拒绝那一路没有真的出网（回来的就是那句「没有副作用」）",
       "未产生任何副作用" in box.get("out", ""), box.get("out", "")[:40])
else:
    ok("R08 外部工具那一行写着 mcp:<server> 和风险档", False, "MCP 没挂上：get_current_time 不在门名单里")
    for x in ("R09", "R10", "R11", "R12"):
        ok(f"{x} 外部工具审计", False, "同上")

# ---- R13 被挡下的调用也有行 ---------------------------------------------------
# 档位是「警告两次、第三次重复才熔断」，所以四道调用才有熔断那一行：
# n=1 执行 · n=2 挡（blocked 1）· n=3 挡（blocked 2，还没超上限）· n=4 挡（blocked 3 > 2 → 熔）。
fresh()
call_tool("list_dir", path=".")
box, ap, r = call_tool("list_dir", path=".")
ok("R13 同名同参第二次：有行、status=dup-blocked、没执行所以 decision 还是 null",
   r.get("status") == "dup-blocked" and r.get("n") == 2 and r.get("blocked") == 1
   and r.get("decision") is None and DUP_MARK in box.get("out", ""),
   json.dumps({k: r.get(k) for k in ("status", "n", "blocked", "decision")}, ensure_ascii=False))
box, ap, r = call_tool("list_dir", path=".")
ok("R13b 第三次重复还在警告（blocked=2 没超过上限 2）",
   r.get("status") == "dup-blocked" and r.get("n") == 3 and r.get("blocked") == 2,
   json.dumps({k: r.get(k) for k in ("status", "n", "blocked")}, ensure_ascii=False))
box, ap, r = call_tool("list_dir", path=".")
ok("R14 第四次＝第三次重复超上限：status=dup-fused，带上挡了几次和上限",
   r.get("status") == "dup-fused" and r.get("n") == 4 and r.get("blocked") == 3 and r.get("limit") == 2
   and DUP_FUSE_MARK in box.get("out", ""),
   json.dumps({k: r.get(k) for k in ("status", "n", "blocked", "limit")}, ensure_ascii=False))
agent.interrupt_switch = False  # 熔断调过 interrupt()，不留到下一条用例

# ---- R15 工具抛异常                                                           ----
fresh()
box, ap, r = call_tool("read_file", path="/etc/passwd")
ok("R15 越界那一路：异常记成 raised＋异常类名，然后原样抛出去",
   r.get("status") == "raised" and r.get("exc") == "PermissionError" and isinstance(box.get("exc"), PermissionError),
   json.dumps({k: r.get(k) for k in ("status", "exc")}, ensure_ascii=False))
ok("R16 记完审计还照旧抛（改的是记账不是行为）", "exc" in box, type(box.get("exc")).__name__)

# ---- R17 文件本身 ------------------------------------------------------------
all_rows = rows()
ok("R17 每一行都是合法 JSON（没有整行截断）", all(isinstance(x, dict) for x in all_rows), f"{len(all_rows)} 行")
ok("R18 每行的必备键都在（缺哪格读的人一眼看得出）",
   all(KEYS <= set(x) for x in all_rows),
   str(sorted({k for x in all_rows for k in KEYS - set(x)})))
ok("R19 每行都带 iso 本地时间与 dur_s（审计能排时间线）",
   all("+08:00" in x.get("iso", "") and isinstance(x.get("dur_s"), float) for x in all_rows),
   all_rows[-1].get("iso") if all_rows else "")
before_bytes = my_audit.AUDIT_PATH.read_bytes()
fresh()
call_tool("grep_files", pattern="PLANNING_INTERVAL", path="smolagents")
txt = my_audit.AUDIT_PATH.read_text(encoding="utf-8")
ok("R20 只追加：已有那些行一个字节没被改过", txt.encode("utf-8")[: len(before_bytes)] == before_bytes)
ok("R21 又追加了一行", len(rows()) == len(all_rows) + 1, f"{len(all_rows)} → {len(rows())}")

# ---- R22 写不进去也不能拦路 ---------------------------------------------------
fresh()
real_path = my_audit.AUDIT_PATH
f0 = my_audit.stats()["failures"]
my_audit.AUDIT_PATH = TMP / "没有这个目录" / "audit.jsonl"
box, ap, r = call_tool("read_file", path="smolagents/my_agent.py", lines=1)
st = my_audit.stats()
ok("R22 审计写失败时工具照旧返回结果（审计不拦路）", "my_agent" in box.get("out", "") or "文件" in box.get("out", ""),
   box.get("out", "")[:36].replace("\n", " "))
ok("R23 失败不静默：计数在涨、第一手的错留得下来",
   st["failures"] > f0 and "No such file" in st["first_error"], f"{st['failures'] - f0} 次 · {st['first_error'][:48]}")
my_audit.AUDIT_PATH = real_path

# ---- R24 删会话不动审计 --------------------------------------------------------
fresh()
n0 = len(rows())
hist = my_ui.History(TMP / "t.sqlite3")
sid = hist.ensure(None)
hist.save(sid, [gr.ChatMessage(role="user", content="d3 临时会话")])
hist.save_memory(sid, '{"fmt":"v2","steps":[]}')
audit_bytes = my_audit.AUDIT_PATH.read_bytes()
gone = hist.delete(sid)
ok("R24 删会话真的删掉了库里的三张表", gone.get("session") == 1 and gone.get("messages") == 1
   and gone.get("memory") == 1, str(gone))
ok("R25 删会话之后审计文件一个字节没变（审计不跟着会话走）",
   my_audit.AUDIT_PATH.read_bytes() == audit_bytes,
   f"{len(audit_bytes)}B · 会话前 {n0} 行 / 现在 {len(rows())} 行")
src = inspect.getsource(my_ui.History)
ok("R26 History 里没有任何一处提审计（不是「恰好没删到」，是压根不认识）",
   "audit" not in src.lower())
ok("R27 产品里审计和会话库同目录、不同文件（备份/回滚时才分得清）",
   DEFAULT_AUDIT.parent == my_ui.DB_PATH.parent and DEFAULT_AUDIT != my_ui.DB_PATH,
   f"{DEFAULT_AUDIT.name} vs {my_ui.DB_PATH.name}")

# ---- R28 真实文件没被这个脚本写过 ----------------------------------------------
ok("R28 他那份真的 .agent-audit.jsonl 没被这条脚本碰过", not DEFAULT_AUDIT.exists(),
   f"{DEFAULT_AUDIT} 不存在；本脚本写在 {my_audit.AUDIT_PATH}")

# ---- R29 测试隔离那个环境变量 ---------------------------------------------------
# 2026-11-04 的现场教训：v1.8/v1.9 那几套复跑时构造真 OpsUI＋真工具，62 行测试流量
# 直接落进了真的 .agent-audit.jsonl（当场挪进 run/v20_audit_first-run.jsonl 留证）。
# 这一条断的是那个口子真的接得上：换了环境变量的子进程写的是指定的那份，不是产品默认那份。
iso = TMP / "env-audit.jsonl"
env = dict(os.environ, AGENT_AUDIT_PATH=str(iso))
r = subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0, '/Users/gaoying/Desktop/study/ai学习/smolagents');"
                    "import my_audit; my_audit.begin(tool='t', src='local', n=1, args={'a': 1});"
                    "my_audit.end(my_audit.current() or {}, 'ran');"
                    "print(my_audit.AUDIT_PATH)"],
                   capture_output=True, text=True, env=env, timeout=60)
ok("R29 AGENT_AUDIT_PATH 指到哪儿就写到哪儿（回归跑的测试流量不进问责日志）",
   r.stdout.strip() == str(iso) and iso.exists() and json.loads(iso.read_text())["tool"] == "t",
   r.stdout.strip()[-60:] + " | " + r.stderr.strip()[:60])
ok("R30 不设变量时，落点就是产品目录里那份 .agent-audit.jsonl",
   subprocess.run([sys.executable, "-c",
                   "import sys; sys.path.insert(0, '/Users/gaoying/Desktop/study/ai学习/smolagents');"
                   "import my_audit; print(my_audit.AUDIT_PATH)"],
                  capture_output=True, text=True, timeout=60,
                  env={k: v for k, v in os.environ.items() if k != "AGENT_AUDIT_PATH"}
                  ).stdout.strip() == str(DEFAULT_AUDIT), str(DEFAULT_AUDIT))
my_mcp.detach(ui._mcp)

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for x in FAIL:
    print("  FAIL:", x)
print(f"审计文件 {my_audit.stats()['path']} · {my_audit.stats()['lines']} 行 · 写失败 {my_audit.stats()['failures']} 次")
sys.exit(0 if not FAIL else 1)
