import base64, json, pathlib

READ = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_read.js").read_text()
SESS = lambda t: f"""(()=>Array.from(document.querySelectorAll('#sessions label')).find(x=>x.innerText.trim().startsWith('{t}')))()"""
NEWBTN = """(()=>Array.from(document.querySelectorAll('#sidebar button')).find(b=>b.innerText.includes('新会话')))()"""
BTN = lambda label: f"""(()=>Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes({json.dumps(label, ensure_ascii=False)})))()"""


def cfg(url, steps, boot=9000):
    out = []
    for s in steps:
        e = dict(s)
        if e.pop("read", 0):
            e["expr"] = base64.b64encode(READ.encode()).decode()
        if "el" in e:
            e["el"] = base64.b64encode(e["el"].encode()).decode()
        out.append(e)
    return json.dumps({"url": url, "bootWait": boot, "steps": out}, ensure_ascii=False)
