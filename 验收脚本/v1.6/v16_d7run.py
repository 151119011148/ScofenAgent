import base64, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "v1.6"))
from v16_cfg import NEWBTN, READ

Q = "用 run_python 打印 4*5 的结果，最后只回那个数字"
STOP = """(()=>Array.from(document.querySelectorAll('#main button')).find(b=>b.innerText.includes('停止')))()"""
# 按停止之后每 200ms 采一次状态条：D7 的判据是「等待审批」这一帧**从来没出现过**，
# 并且整条流自己收尾（不靠再补一刀 ✖）。采样粒度 200ms，比 v1.5 那轮的 700ms 更细。
SAMPLE = """(async()=>{let awaitSeen=0, runSeen=0, t0=Date.now(), st='';
while(Date.now()-t0<25000){
 const b=document.getElementById('statusbar');
 st=(b?b.innerText:'').replace(/\\s+/g,' ');
 if(/等待审批/.test(st))awaitSeen++;
 if(/生成中/.test(st))runSeen++;
 if(!/生成中|等待审批|停止中/.test(st)&&Date.now()-t0>2000)break;
 await new Promise(r=>setTimeout(r,200));}
return JSON.stringify({awaitSeen, runSeen, endedAfterMs:Date.now()-t0, st:st.slice(0,140)});})()"""

steps = [
    {"name": "1-new", "el": NEWBTN, "wait": 2000},
    {"name": "2-ask", "type": Q},
    {"name": "3-stop", "el": STOP, "wait": 300},
    {"name": "3-sample", "expr": SAMPLE},
    {"name": "4-read", "read": 1},
    {"name": "4-bots", "expr": """(()=>JSON.stringify(Array.from(document.querySelectorAll('#main [data-testid=bot]')).map(b=>b.innerText.replace(/\\s+/g,' ').slice(0,150))))()"""},
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
    out.append(e)

port = sys.argv[1] if len(sys.argv) > 1 else "7860"
pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_d7.json").write_text(
    json.dumps({"url": f"http://127.0.0.1:{port}", "bootWait": 10000, "steps": out}, ensure_ascii=False)
)
print("wrote /Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_d7.json for port", port)
