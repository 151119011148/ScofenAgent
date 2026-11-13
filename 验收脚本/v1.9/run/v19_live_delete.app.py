
import os, pathlib, sys
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr
import my_ui

DB = pathlib.Path(os.environ["V19_DB"])
my_ui.DB_PATH = DB                     # 构造 OpsUI 之前指走，真库不参与
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
# 预置两条会话，标题分别带 A/B，浏览器里一眼分得开
h = ui.hist
a, b = h.ensure(None), h.ensure(None)
h.save(a, [gr.ChatMessage(role="user", content="A 号会话的第一问"),
           gr.ChatMessage(role="assistant", content="A 号会话的答复")])
h.save_memory(a, '{"fmt":"v2","steps":[]}')
h.save(b, [gr.ChatMessage(role="user", content="B 号会话的第一问")])
h.save_memory(b, '{"fmt":"v2","steps":[]}')
print("seeded", a, b, flush=True)
open(os.environ["V19_IDS"], "w").write("%s %s" % (a, b))
ui.launch(share=False, server_name="127.0.0.1", server_port=int(os.environ["V19_PORT"]),
          css=my_ui.DARK_CSS)
