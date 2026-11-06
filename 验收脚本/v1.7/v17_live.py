# -*- coding: utf-8 -*-
"""v1.7 第③步的 CDP 剧本：一次「挂着审批不点 → 点允许」，再一次「重启后刷新」。

用法：python v17_live.py <phase: pre|post> <port>
    pre  —— 起进程后的第一轮：读基线 → 新会话 → 提问 → 审批挂 WAIT 秒 → 允许 → 读状态条
    post —— **杀掉界面进程、用同一个库重起**之后的一轮：只看刷新（_on_load）读到谁、
            「本题审批」那一格还在不在，再点两条 v1 时代的旧会话看兼容读
产物：/tmp/v17_<phase>.json（给 node /Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_cdp.js 吃）
"""
import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "v1.6"))
from v16_cfg import NEWBTN, SESS, READ  # noqa: E402

Q = "用 run_python 打印 3*7 的结果，最后只回那个数字，不要重复调用工具"
WAIT = 20  # 审批故意挂这么久：V9 要验的就是这一格能不能跨过重启活下来

MARK = """(()=>{window.__mb=document.querySelectorAll('#main [data-testid=bot]').length;return 'marked bot='+window.__mb;})()"""
AWAITING = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /等待审批/.test(t) ? 'YES:'+t.slice(0,120) : 'NO:'+t.slice(0,120);})()"""
DONE = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
return (!busy && bot>(window.__mb||0)) ? 'YES:bot->'+bot+' | '+t.slice(0,140) : 'NO:busy='+busy+'|bot='+bot+'|'+t.slice(0,90);})()"""
APPR = """(()=>document.getElementById('approve-btn'))()"""

phase = sys.argv[1] if len(sys.argv) > 1 else "pre"
port = sys.argv[2] if len(sys.argv) > 2 else "7861"

if phase == "pre":
    # 一整轮只在**同一个页面**里跑完：中途不能刷新（CDP 每跑一份剧本都会 navigate 一次，
    # 中途那两次 peek 就是把这一轮打断、连同屏幕字和记忆一起丢掉的原因——已实测记录）。
    steps = [
        {"name": "P0-read-baseline", "read": 1},
        {"name": "P1-new", "el": NEWBTN, "wait": 2000},
        {"name": "P1-read", "read": 1},
        {"name": "P2-mark", "expr": MARK},
        {"name": "P2-ask", "type": Q},
        {"name": "P3-wait-card", "until": AWAITING, "timeout": 150000},
        {"name": "P3-read-pending", "read": 1},
        {"name": "P4-hang", "wait": WAIT * 1000},
        {"name": "P4-read-still-waiting", "read": 1},
        {"name": "P5-approve", "el": APPR, "wait": 2000},
        {"name": "P5-read-after-first", "read": 1},
        # 模型这一题可能连着调两三次工具（v1.6 实测过 qwen-plus 会重复调用）。
        # 每一次「等到出现待批 → 点允许」都必须留在同一个页面里：CDP 每份剧本开头都
        # 会 Page.navigate，中途去 peek 一下就是把这一轮掐断（实测丢过整轮的字和记忆）。
    ] + [
        step
        for i in range(1, 7)
        for step in ({"name": "P6-maybe-%d" % i, "until": AWAITING, "timeout": 9000},
                     {"name": "P6-approve-%d" % i, "el": APPR, "wait": 2500},
                     {"name": "P6-read-%d" % i, "read": 1})
    ] + [
        {"name": "P8-wait-done", "until": DONE, "timeout": 300000},
        {"name": "P8-read-after", "read": 1},
    ]
elif phase == "peek":
    steps = [{"name": "X-read", "read": 1, "wait": 800}, {"name": "X-read2", "read": 1}]
elif phase == "drain":
    # qwen-plus 这一题连着四次要调 run_python（每次参数都是 13*13 那一类），
    # 一次次点「允许」把它喂到收尾；点不到按钮就是那一瞬间没有卡，NO-ELEMENT 无害。
    steps = [
        {"name": "D0-read", "read": 1},
    ] + [
        {"name": f"D{i}-approve", "el": APPR, "wait": 6000} for i in range(1, 7)
    ] + [
        {"name": "D7-wait-done", "until": DONE, "timeout": 120000},
        {"name": "D8-read", "read": 1},
    ]
elif phase == "finish":
    # 模型这道题调了两次 run_python，剧本只点了一次「允许」，第二条待批还挂在闸上
    # （APPROVAL_TIMEOUT=600s 才会自己超时）。这一轮把它点完，让这题真跑到最终回答。
    steps = [
        {"name": "F0-read", "read": 1},
        {"name": "F1-approve", "el": APPR, "wait": 2000},
        {"name": "F2-maybe-again", "until": AWAITING, "timeout": 30000},
        {"name": "F3-approve-again", "el": APPR, "wait": 2000},
        {"name": "F4-wait-done", "until": DONE, "timeout": 300000},
        {"name": "F5-read", "read": 1},
    ]
else:
    steps = [
        {"name": "S0-read-on-load", "read": 1, "wait": 1500},
        {"name": "S1-read-again", "read": 1},
        {"name": "S2-click-v1-甲", "el": SESS("v1旧记忆-甲"), "wait": 2000},
        {"name": "S2-read-甲", "read": 1},
        {"name": "S3-click-v1-乙", "el": SESS("v1旧记忆-乙"), "wait": 2000},
        {"name": "S3-read-乙", "read": 1},
    ]

out = []
for s in steps:
    e = dict(s)
    if e.pop("read", 0):
        e["expr"] = base64.b64encode(READ.encode()).decode()
    elif "expr" in e:
        e["expr"] = base64.b64encode(e["expr"].encode()).decode()
    if "el" in e:
        e["el"] = base64.b64encode(e["el"].encode()).decode()
    if "until" in e:
        e["until"] = base64.b64encode(e["until"].encode()).decode()
    out.append(e)

dst = pathlib.Path(__file__).resolve().parent / "run" / ("v17_%s.json" % phase)
dst.write_text(json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 9000, "steps": out}, ensure_ascii=False))
print("wrote", dst, "for port", port, "| 审批挂着等", WAIT, "s")
