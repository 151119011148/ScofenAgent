import base64, json, pathlib, sys

sys.path.insert(0, "/tmp")
from v16_cfg import NEWBTN, SESS, READ

# 交付形态（7860，真 qwen-plus）一次跑完 V7 + V8 两条：
#   A) 新会话 → 强制 run_python 的题 → 挂着 20 秒不点 → 允许 → 读卡片与状态条（V8）
#   B) 再点「＋ 新会话」→ 高亮应清空（V7 的前半）→ 点回 A 那条会话 → 屏上应换回它的历史
#      → 追问「刚才 run_python 打印了什么」→ 答 21 才说明这条问题落进了 A 那条会话（V7 后半 + V6）
Q_A = "用 run_python 打印 3*7 的结果，最后只回那个数字"
Q_B = "刚才那次 run_python 打印出来的数字是多少？只回数字"
WAIT = 20
MARK = """(()=>{window.__mb=document.querySelectorAll('#main [data-testid=bot]').length;return 'marked bot='+window.__mb;})()"""
AWAITING = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /等待审批/.test(t) ? 'YES:'+t.slice(0,110) : 'NO:'+t.slice(0,110);})()"""
DONE = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
return (!busy && bot>(window.__mb||0)) ? 'YES:bot->'+bot+' | '+t.slice(0,130) : 'NO:busy='+busy+'|bot='+bot+'|'+t.slice(0,90);})()"""
APPR = """(()=>document.getElementById('approve-btn'))()"""
BOTS = """(()=>JSON.stringify(Array.from(document.querySelectorAll('#main [data-testid=bot]')).map(b=>b.innerText.replace(/\\s+/g,' ').slice(0,150))))()"""

steps = [
    {"name": "A1-new", "el": NEWBTN, "wait": 2000},
    {"name": "A1-read", "read": 1},
    {"name": "A2-mark", "expr": MARK},
    {"name": "A2-ask", "type": Q_A},
    {"name": "A3-card", "until": AWAITING, "timeout": 120000},
    {"name": "A4-hang", "wait": WAIT * 1000},
    {"name": "A5-approve", "el": APPR},
    {"name": "A6-done", "until": DONE, "timeout": 180000},
    {"name": "A6-read", "read": 1},
    {"name": "A6-bots", "expr": BOTS},
    {"name": "B1-new", "el": NEWBTN, "wait": 2500},
    {"name": "B1-read-cleared", "read": 1},
    {"name": "B2-click-A", "el": SESS(Q_A[:12]), "wait": 3000},
    {"name": "B2-read-restored", "read": 1},
    {"name": "B3-mark", "expr": MARK},
    {"name": "B3-ask", "type": Q_B},
    {"name": "B4-done", "until": DONE, "timeout": 180000},
    {"name": "B4-read", "read": 1},
    {"name": "B4-bots", "expr": BOTS},
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

port = sys.argv[1] if len(sys.argv) > 1 else "7860"
pathlib.Path("/tmp/v16_delivery.json").write_text(
    json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 12000, "steps": out}, ensure_ascii=False)
)
print("wrote /tmp/v16_delivery.json for port", port)
