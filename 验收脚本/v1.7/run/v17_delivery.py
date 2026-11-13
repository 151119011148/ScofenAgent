# -*- coding: utf-8 -*-
"""v1.7 交付形态（7860 + 真实库 + 真 qwen-plus）的一轮剧本。

V9 要看的三件事，都在**同一个页面**里跑完（CDP 每份剧本开头都 Page.navigate，
中途 peek 会把这一轮掐断——v1.7 实跑时实测丢过整轮，见迭代记录）：
  A) 新会话 → 强制 run_python 的题 → 审批挂 20 秒 → 允许 → 状态条出现「本题审批」
  B) 一整轮只做一次 navigate，所以轮子跑完时屏上的数就是这一题的数
产物：/tmp/v17_delivery.json（post 阶段那份是重启后的只读验收，见 --post）
"""
import base64
import json
import pathlib
import sys

sys.path.insert(0, "/tmp")
from v16_cfg import NEWBTN, SESS, READ  # noqa: E402

Q = "用 run_python 打印 3*7 的结果，最后只回那个数字，不要重复调用工具"
WAIT = 20
MARK = """(()=>{window.__mb=document.querySelectorAll('#main [data-testid=bot]').length;return 'marked bot='+window.__mb;})()"""
AWAITING = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /等待审批/.test(t) ? 'YES:'+t.slice(0,110) : 'NO:'+t.slice(0,110);})()"""
DONE = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
return (!busy && bot>(window.__mb||0)) ? 'YES:bot->'+bot+' | '+t.slice(0,150) : 'NO:busy='+busy+'|bot='+bot+'|'+t.slice(0,90);})()"""
APPR = """(()=>document.getElementById('approve-btn'))()"""
BOTS = """(()=>JSON.stringify(Array.from(document.querySelectorAll('#main [data-testid=bot]')).map(b=>b.innerText.replace(/\\s+/g,' ').slice(0,170))))()"""

phase = sys.argv[1] if len(sys.argv) > 1 else "ask"
port = sys.argv[2] if len(sys.argv) > 2 else "7860"

if phase == "ask":
    steps = [
        {"name": "A0-read-before", "read": 1},
        {"name": "A1-new", "el": NEWBTN, "wait": 2000},
        {"name": "A1-read", "read": 1},
        {"name": "A2-mark", "expr": MARK},
        {"name": "A2-ask", "type": Q},
        {"name": "A3-card", "until": AWAITING, "timeout": 150000},
        {"name": "A3-read-pending", "read": 1},
        {"name": "A4-hang", "wait": WAIT * 1000},
        {"name": "A4-read-waiting", "read": 1},
        {"name": "A5-approve", "el": APPR, "wait": 2000},
    ] + [
        step
        for i in range(1, 6)
        for step in ({"name": "A6-maybe-%d" % i, "until": AWAITING, "timeout": 9000},
                     {"name": "A6-approve-%d" % i, "el": APPR, "wait": 2500})
    ] + [
        {"name": "A7-done", "until": DONE, "timeout": 240000},
        {"name": "A7-read", "read": 1},
        {"name": "A7-bots", "expr": BOTS},
    ]
else:
    # 重启后只看两件事：刷新（_on_load）这一格回没回来；点一条 v1 时代的旧会话读不读得动
    steps = [
        {"name": "C0-read-onload", "read": 1, "wait": 1500},
        {"name": "C0-bots", "expr": BOTS},
        # 4*5 那几条是 v1.6 留下的真 v1 payload（库里 fmt=v1、没有 wait 这一格）：
        # 点它们 = 兼容读的活样本。不能点 3*7 那条，它的标题和我这一轮的题**同前缀**。
        {"name": "C1-click-v1", "el": SESS("用 run_python 打印 4*5"), "wait": 2500},
        {"name": "C1-read-v1", "read": 1},
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

dst = pathlib.Path("/tmp/v17_delivery_%s.json" % phase)
dst.write_text(json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 12000, "steps": out},
                          ensure_ascii=False))
print("wrote", dst, "phase=%s port=%s 审批挂 %ds" % (phase, port, WAIT))
