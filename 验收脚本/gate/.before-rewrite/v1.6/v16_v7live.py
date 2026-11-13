import base64, json, pathlib, sys

sys.path.insert(0, "/tmp")
from v16_cfg import NEWBTN, SESS, READ

Q1 = "记住一个数字：73。只回一个字：好"
Q2 = "如果你没有这段历史，只回「不记得」；否则把那个数字回给我，只回数字"
MARK = """(()=>{window.__mb=document.querySelectorAll('#main [data-testid=bot]').length;return 'marked bot='+window.__mb;})()"""
# 交出去的那一刻先记底数，再等「bot 变多 且 不在生成中/等待审批/停止中」——
# 只看状态词会立刻命中上一题留下的「空闲」，v1.6 第一次跑就栽在这里。
IDLE = """(()=>{const b=document.getElementById('statusbar');const t=(b?b.innerText:'').replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
const base=window.__mb||0;
return (!busy && bot>base) ? 'YES:bot '+base+'->'+bot+' | '+t.slice(0,120) : 'NO:busy='+busy+'|bot='+bot+'<='+base+'|'+t.slice(0,80);})()"""

steps = [
    {"name": "1-new", "el": NEWBTN, "wait": 2000},
    {"name": "1-read", "read": 1},
    {"name": "2-mark", "expr": MARK},
    {"name": "2-ask1", "type": Q1},
    {"name": "2-answer1", "until": "P", "timeout": 180000},
    {"name": "2-read", "read": 1},
    {"name": "3-new-again", "el": NEWBTN, "wait": 2500},
    {"name": "3-read", "read": 1},
    {"name": "4-click-old", "el": SESS(Q1[:10]), "wait": 3000},
    {"name": "4-read", "read": 1},
    {"name": "5-mark", "expr": MARK},
    {"name": "5-ask2", "type": Q2},
    {"name": "5-answer2", "until": "P", "timeout": 180000},
    {"name": "5-read", "read": 1},
]

out = []
for s in steps:
    e = dict(s)
    if e.pop("read", 0):
        e["expr"] = base64.b64encode(READ.encode()).decode()
    else:
        e["expr"] = base64.b64encode(e["expr"].encode()).decode() if "expr" in e else None
        if "expr" in e and e["expr"] is None:
            e.pop("expr")
    if "el" in e:
        e["el"] = base64.b64encode(e["el"].encode()).decode()
    if e.get("until") == "P":
        e["until"] = base64.b64encode(IDLE.encode()).decode()
    out.append(e)

port = sys.argv[1] if len(sys.argv) > 1 else "7861"
pathlib.Path("/tmp/v16_v7live.json").write_text(
    json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 9000, "steps": out}, ensure_ascii=False)
)
print("wrote /tmp/v16_v7live.json for port", port)
