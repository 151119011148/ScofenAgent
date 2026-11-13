# -*- coding: utf-8 -*-
"""D3：每一次工具调用落一行 JSONL——谁调的、批没批、跑了多久、结果算不算异常。

为什么要这一份：审批门（P0-2）的读数只活在**当前这一屏**上。关掉页面，「刚才那题里
哪一次调用是我批的、哪一次被拒、模型偷偷试了几遍同一个参数」就全没了——而这三件事恰好是
这台机器最该被追问的：它有一只手能出网（fetch）、有一只手能落文件（write_file）。
会话库（.agent-history.sqlite3）里存的是**显示层**和 agent 的记忆，删一条会话就 CASCADE 掉；
审计要的是反面——**不跟着会话走**，所以单独一个只追加的文件，删会话不动它。

三层门里为什么装在**查重那层**（最外面，见 my_ui._install_dup_gate）：
  · 装在审批层：只读那五只手不进门，它们占的调用就一条都不记——而实测重复调用恰恰全在只读侧。
  · 装在查重层：模型每一次「我真的发出去了一次调用」都留下行，包括被查重挡掉的那两次
    （status=dup-blocked / dup-fused）。这一份审计的用途是「它发过什么」，不是「跑成功了什么」。

参数为什么只留摘要（sha1 + 前 200 字符）不留全文：
  write_file 的 content、fetch 抓回来的正文都可能几百 KB，一次提问几十条调用，
  审计文件会比会话库大两个量级；真要复现那一次，sha1 对得上 + args_head 够定位，
  全文在 .agent-staging/ 和会话记忆里各有其主。

失败不拦路：写审计出任何错都只累 `failures` 计数并把第一手的错打到 stderr——
「审计写不进去」不该变成「这一题跑不下去了」，但也不能悄悄吞掉（界面上 MCP 那格旁边没地方写它，
所以这条只能靠 `stats()` 事后看）。

跑法：这一份不单独运行，由 my_ui 的查重回调用；离线断言见
      验收脚本/v2.0/v20_test_d3_audit.py
"""

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# AGENT_AUDIT_PATH：把审计指到别处。这是**测试隔离**用的，不是给用户配的开关——
# 2026-11-04 第一次复跑 v1.8/v1.9 那几套离线闸时就踩过：它们构造的是真 OpsUI ＋ 真工具，
# 于是 62 行测试流量落进了真的 .agent-audit.jsonl（第一批当场挪进
# 验收脚本/v2.0/run/v20_audit_first-run.jsonl 留证）。问责日志里混进脚本跑的调用，
# 事后翻审计的人分不清哪一条是屏幕上真发生过的事。
AUDIT_PATH = Path(os.environ.get("AGENT_AUDIT_PATH")
                  or Path(__file__).resolve().parent / ".agent-audit.jsonl")
ARGS_HEAD_CHARS = 200

_lock = threading.Lock()
_local = threading.local()  # 一次调用一条线程（查重→审批→执行都在同一条上），所以线程局部就够
_failures = 0
_first_error = ""


def begin(**fields) -> dict:
    """查重层进一次调用就开一条记录；同一时刻每条线程只有一条在飞（begin 之后必跟 end）。

    decision / wait_s 先落成 null 再让审批层覆盖：每行的键集合因此是**定死的**，
    读的人不用先猜「这行没有 decision 这格，还是它压根没过审批门」——两者都是这一格为 null，
    而 status 那一格会告诉他是哪一种（ran 且 decision=null = 本地只读那五只手，不过门）。
    """
    rec = {"_t0": time.time(), "_args": fields.pop("args", {}), "decision": None, "wait_s": None}
    rec.update(fields)
    _local.rec = rec
    return rec


def current() -> dict | None:
    """当前这条线程正在飞的那次调用；不在调用点上（比如计划审批）就是 None。"""
    return getattr(_local, "rec", None)


def annotate(**fields) -> None:
    """审批层把 decision / 等待秒数 / 来源补进来。没有活动记录时静默跳过——
    _plan_gate 也在同一条 worker 线程上，它那张计划单不该盖到上一次工具调用的记录上。"""
    rec = current()
    if rec is not None:
        rec.update(fields)


def _digest(obj) -> tuple[str, str]:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16], raw[:ARGS_HEAD_CHARS]


def end(rec: dict, status: str, **fields) -> None:
    """盖上收尾字段、落盘、把这条线程的活动记录清掉。"""
    if rec is not None:
        _local.rec = None
    args_sha1, args_head = _digest(rec.get("_args", {})) if rec else ("", "")
    t0 = rec.get("_t0", time.time()) if rec else time.time()
    row = {
        "ts": round(t0, 3),
        "iso": datetime.fromtimestamp(t0).astimezone().isoformat(timespec="seconds"),
        "dur_s": round(time.time() - t0, 3),
        "args_sha1": args_sha1,
        "args_head": args_head,
        "status": status,
    }
    for k, v in (rec or {}).items():
        if not k.startswith("_"):
            row[k] = v
    row.update(fields)
    # 不整行截断：截在半截字符串上的 JSONL 会让读这个文件的人**整行 parse 不出来**，
    # 审计也就作废了。长度靠 args_head 那一格自己封顶（200 字符），其余字段全是有界的小字符串。
    line = json.dumps(row, ensure_ascii=False, default=str)
    try:
        with _lock, open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        global _failures, _first_error
        with _lock:
            _failures += 1
            _first_error = _first_error or f"{type(e).__name__}: {e}"
        print(f"[audit] 这一行没写进去（{row.get('tool')}）：{e}", file=sys.stderr)


def stats() -> dict:
    """给状态条/测试读的自检：文件在哪、多少行、写失败过几次。"""
    try:
        with open(AUDIT_PATH, "rb") as f:
            data = f.read()
    except OSError:
        data = b""
    return {
        "path": str(AUDIT_PATH),
        "lines": sum(1 for _ in data.splitlines() if _.strip()),
        "bytes": len(data),
        "failures": _failures,
        "first_error": _first_error,
    }
