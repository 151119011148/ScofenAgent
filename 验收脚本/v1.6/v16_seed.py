import sys, pathlib
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui, gradio as gr

db = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16-live-hist.sqlite3")
if db.exists():
    db.unlink()
h = my_ui.History(db)
for i, title in enumerate(["V7基线-甲", "V7基线-乙", "V7基线-丙"], start=1):
    sid = h.ensure(None)
    h.save(sid, [gr.ChatMessage(role="user", content=title, metadata={"status": "done"}),
                 gr.ChatMessage(role="assistant", content=f"第 {i} 条会话的答复", metadata={"status": "done"})])
print(h.choices())
