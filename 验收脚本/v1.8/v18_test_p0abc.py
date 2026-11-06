# -*- coding: utf-8 -*-
"""P0-a／P0-b／P0-c 的离线闸：证明这一刀**只改了说什么**，没改任何判定。

三条主线：
  1. 行为面逐条对齐旧代码（`.rollback/v1.8/after-p04/my_coding_agent.py`）：同一张路径表上，
     新旧 `guarded()` 的异常类型、解析出来的那个 Path、成功时返回的 Path，必须一一对上。
     另外单独钉一条：**绝对路径**不存在时新旧报错文案逐字相同——这轮的文案扩张只发生在
     「相对路径 + 不存在」那一条分支和越界那一条分支上，别的地方一个字没动。
  2. 新文案里该有的要素齐不齐（指路、摊口径、不许再拿同参重试、不许编管理员）。
  3. 「哪半句真的进了模型」：把 description 和工具 docstring 分开验——description 里独有的
     穷举串必须**不在** system_prompt 里，工具 docstring 里新增的句子必须**在**。
     这条不是形式主义：21:06 那轮的 agent 是 my_agent 那个，如果只在 description 上写穷举，
     改的就是一个模型读不到的字段。跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_test_p0abc.py
"""
import importlib.util
import pathlib
import re
import sys

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_agent  # noqa: E402
import my_coding_agent as new_mod  # noqa: E402
from smolagents import ToolCallingAgent  # noqa: E402

OLD_PATH = "/Users/gaoying/Desktop/study/ai学习/smolagents/.rollback/v1.8/after-p04/my_coding_agent.py"
ROOT = new_mod.ROOT
FAIL = []


def ok(name, cond, detail=""):
    print("%-34s %s %s" % (name, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(name)


def load_old():
    spec = importlib.util.spec_from_file_location("p0abc_old", OLD_PATH)
    m = importlib.util.module_from_spec(spec)
    sys.modules["p0abc_old"] = m
    spec.loader.exec_module(m)
    return m


old_mod = load_old()


def call(mod, path, must_exist=True):
    """跑一遍 guarded，返回 (类型, 值)。值：成功时是 Path，异常时是**从文案里抽出的那个路径**——
    抽路径而不是比全文，是因为这一刀改了全文；剩下的那半截（判定结果）必须一字不差。"""
    try:
        return ("ok", mod.guarded(path, must_exist))
    except BaseException as exc:  # noqa: BLE001
        msg = str(exc)
        m = re.search(r"越界：(.+?) 不在白名单根目录", msg) or re.search(r"路径不存在：(\S+?)。", msg + "。")
        return (type(exc).__name__, m.group(1) if m else msg)


# ---- 1：行为面，一张表跑新旧两遍 ------------------------------------------------------
TABLE = [
    ("smolagents/my_ui.py", True),
    (".", True),
    ("", True),
    ("  smolagents  ", True),
    (str(ROOT), True),
    ("smolagents", True),
    ("smolagents/nope-does-not-exist.txt", False),
    ("/Users/gaoying/Desktop/study/", True),
    ("/Users/gaoying/Desktop/study", True),
    ("/tmp", True),
    ("~/Desktop", True),
    ("~/Desktop/study/ai学习/../../etc/passwd", True),
    ("人生/", True),
    ("职业规划/", True),
    ("smolagents/.env", True),
    (str(ROOT / "smolagents" / ".venv" / "bin"), True),
    ("/Users/gaoying/Desktop/study/ai学习/不存在-绝对路径", True),
]
for path, must in TABLE:
    o = call(old_mod, path, must)
    n = call(new_mod, path, must)
    ok("1-行为一致 %s" % (path[:20] or "<空>"), o == n, "old=%s new=%s" % (o, n))

# 同一张表跑出来的值域本身也得覆盖到三类结局，否则上面 17 条全等可能只是因为全等在同一支上
kinds = {}
for path, must in TABLE:
    kinds.setdefault(call(new_mod, path, must)[0], 0)
    kinds[call(new_mod, path, must)[0]] += 1
ok("1-覆盖面(三种结局都在表里)", set(kinds) == {"ok", "FileNotFoundError", "PermissionError"}, str(kinds))

# ---- 2：绝对路径不存在那条分支文案逐字未动（只扩了相对分支和越界） ----------------------
ABS_MISSING = str(ROOT / "不存在-绝对路径")
e_old = None
try:
    old_mod.guarded(ABS_MISSING)
except FileNotFoundError as exc:
    e_old = str(exc)
try:
    new_mod.guarded(ABS_MISSING)
except FileNotFoundError as exc:
    e_new = str(exc)
ok("2-绝对不存在文案一字未动", e_old == e_new, repr(e_new))

# ---- 3：新文案要素齐不齐 ----------------------------------------------------------------
oob = None
try:
    new_mod.guarded("/Users/gaoying/Desktop/study/")
except PermissionError as exc:
    oob = str(exc)
for kw, label in [(str(ROOT), "报出根"), ("没有删除、移动、重命名", "穷举没有的手"),
                  ("终端", "指路到用户终端"), ("系统管理员", "堵住『找管理员开权限』"),
                  ("不要再换一条根外路径重试", "不许换路径重试")]:
    ok("3-越界含「%s」" % label, kw in oob, "")

rel = None
try:
    new_mod.guarded("人生/")
except FileNotFoundError as exc:
    rel = str(exc)
for kw, label in [("人生/", "原样回显给的是模型自己写的那串"),
                  (str(ROOT / "人生"), "拼接结果"),
                  ("不会去猜别的根目录", "不猜根"),
                  ("根外有没有同名目录我读不到", "承认读不到根外"),
                  ("不要用同一个参数再打一遍", "堵住同参重试"),
                  ("list_dir(path='.')", "给一条能走的路")]:
    ok("3-相对不存在含「%s」" % label, kw in rel, "")
ok("3-相对分支仍是不存在那一支", rel.startswith("路径不存在：" + str(ROOT / "人生"))
   and "我只能把它接到白名单根 " + str(ROOT) in rel,
   "「越界」三个字在新文案里是指路，不是改判：走的仍是 FileNotFoundError 这一支")

# ---- 4：DENY 名单与 must_exist=False 分支没被文案带跑 -----------------------------------
denied = None
try:
    new_mod.guarded("smolagents/.env")
except PermissionError as exc:
    denied = str(exc)
ok("4-凭证目录仍拒且文案未改", denied == "拒绝访问凭证或依赖目录：%s" % (ROOT / "smolagents" / ".env"), repr(denied))
try:
    new_mod.guarded(".agent-staging", must_exist=False)
    ok("4-staging 仍拒", False, "竟然放行了")
except PermissionError:
    ok("4-staging 仍拒", True, "")

# ---- 5：哪半句真的进了模型 --------------------------------------------------------------
sp_new = my_agent.agent.system_prompt
a2 = ToolCallingAgent(
    tools=[old_mod.read_file, old_mod.list_dir, old_mod.grep_files, old_mod.write_file, old_mod.run_python,
           my_agent.MaxDrawdownTool(), my_agent.AnnualizedVolTool()],
    model=my_agent.model, max_steps=8, name="x", description="y",
)
sp_old = a2.system_prompt
# description 里独有的穷举串（docstring 里没这句）——必须读不到，这才是「模型读不到 description」的正面证据
DEAD_IN_DESC = "单次最多 300 行"
ok("5-description 穷举不进 prompt", DEAD_IN_DESC not in sp_new,
   "my_coding_agent.description 里的独有串不在 system_prompt")
ok("5-description 老串也不进 prompt", "在 ai学习 目录里读代码、搜代码、跑验证" not in sp_old, "")
# 工具 docstring 是模型看得见的那一半
for kw, label in [("列不到根外的任何目录", "list_dir docstring"),
                  ("唯一会留下文件的动作", "write_file docstring"),
                  ("删除、移动、重命名都没有对应工具", "write_file docstring 负向穷举")]:
    ok("5-进了 prompt：%s" % label, kw in sp_new, "")
delta = len(sp_new) - len(sp_old)
ok("5-prompt 增量 = 146 字符", delta == 146, "old=%d new=%d delta=%+d" % (len(sp_old), len(sp_new), delta))
# 越界／不存在的两条新文案不进 prompt：它们只在模型真的撞上去之后才出现，不抬高每一步的固定开销
ok("5-报错文案不占固定开销", "不在白名单根目录" not in sp_new, "")

# ---- 6：my_agent 那个 agent（21:06 那轮出事的正是它）的 description 也写全了 -------------
d = my_agent.agent.description
for kw in ["max_drawdown", "annualized_volatility", "read_file", "list_dir", "grep_files",
           "write_file", "run_python", "没有删除／移动／重命名"]:
    ok("6-my_agent description 全", kw in d, kw)

print("\n%s  FAIL=%d" % ("全绿" if not FAIL else "有红", len(FAIL)))
if FAIL:
    print("红的这几条：", FAIL)
    sys.exit(1)
