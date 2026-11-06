# -*- coding: utf-8 -*-
import re, sys, tempfile, pathlib
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui
from my_ui import OpsUI, History
from my_agent import agent

tmp = pathlib.Path(tempfile.mkdtemp()) / "stop.db"
ui = OpsUI(agent, file_upload_folder="./data")
ui.hist = History(tmp)          # 不污染正式库

task = "依次读取 my_agent.py、my_coding_agent.py、monitoring.py、agents.py、gradio_ui.py、memory.py、tools.py 七个文件，每个都 grep 出 class 定义行号，最后汇总"
gen = ui._respond(task, None)
sid = None
n = 0
for msgs, status, radio_upd, box_upd, sid in gen:
    n += 1
    st = re.search(r"状态</b><i>([^<]+)", status).group(1)
    step = re.search(r"步数</b><i>([^<]+)", status).group(1)
    print(f"[yield {n:3d}] bubbles={len(msgs):3d} step={step} state={st}")
    if n == 3:
        print(">>> 点停止（调 agent.interrupt()）")
        ui._stop()
print("=== 终态:", re.search(r"状态</b><i>([^<]+)", status).group(1))
print("=== 末条气泡:", msgs[-1].metadata.get("title"), "|", str(msgs[-1].content)[:80])
print("=== 库里的消息数:", len(ui.hist.load(sid)), "标题:", ui.hist.choices())
