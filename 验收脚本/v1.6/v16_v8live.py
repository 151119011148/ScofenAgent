import base64, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "v1.6"))
from v16_cfg import NEWBTN, READ

Q = "用 run_python 打印 3*7 的结果，最后只回那个数字"
WAIT = 70  # 故意让审批挂着这么久，单列出来的那一格才好读
MARK = """(()=>{window.__mb=document.querySelectorAll('#main [data-testid=bot]').length;return 'marked bot='+window.__mb;})()"""
AWAITING = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /等待审批/.test(t) ? 'YES:'+t.slice(0,110) : 'NO:'+t.slice(0,110);})()"""
DONE = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
return (!busy && bot>(window.__mb||0)) ? 'YES:bot->'+bot+' | '+t.slice(0,130) : 'NO:busy='+busy+'|bot='+bot+'|'+t.slice(0,90);})()"""
APPR = """(()=>document.getElementById('approve-btn'))()"""

steps = [
    {"name": "1-new", "el": NEWBTN, "wait": 2000},
    {"name": "1-read", "read": 1},
    {"name": "2-mark", "expr": MARK},
    {"name": "2-ask", "type": Q},
    {"name": "3-wait-card", "until": AWAITING, "timeout": 120000},
    {"name": "3-read-pending", "read": 1},
    {"name": "4-hang", "wait": WAIT * 1000},
    {"name": "4-read-still-waiting", "read": 1},
    {"name": "5-approve", "el": APPR, "wait": 1500},
    {"name": "6-wait-done", "until": DONE, "timeout": 180000},
    {"name": "6-read", "read": 1},
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

port = sys.argv[1] if len(sys.argv) > 1 else "7861"
pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_v8live.json").write_text(
    json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 9000, "steps": out}, ensure_ascii=False)
)
print("wrote /Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_v8live.json for port", port, "| 挂着等", WAIT, "s")
