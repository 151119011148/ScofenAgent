# -*- coding: utf-8 -*-
"""v1.5 在线探测口：跑真 my_ui.py，但历史库指到 /tmp，别碰交付形态的库。"""
import os
import pathlib
import sys

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui  # noqa: E402

my_ui.DB_PATH = pathlib.Path(os.environ.get("V15DB", "/tmp/v15-live-hist.sqlite3"))
print("DB ->", my_ui.DB_PATH, flush=True)

my_ui.OpsUI(my_ui.agent, file_upload_folder="./data").launch(
    share=False,
    server_name="127.0.0.1",
    server_port=7861,
    css=my_ui.DARK_CSS,
)
