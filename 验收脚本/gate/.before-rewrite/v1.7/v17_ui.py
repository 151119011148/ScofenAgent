# -*- coding: utf-8 -*-
"""v1.7 实跑用的界面进程：库和端口都从命令行走，方便「杀了再起」演重启。

用法：python v17_ui.py <port> <db路径>
"""
import pathlib
import sys

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui  # noqa: E402

port = int(sys.argv[1]) if len(sys.argv) > 1 else 7861
my_ui.DB_PATH = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/v17-live-hist.sqlite3")
print("[v17_ui] port=%s db=%s MEM_FMT=%s read=%s" % (port, my_ui.DB_PATH, my_ui.MEM_FMT, my_ui.MEM_FMT_READ))
my_ui.OpsUI(my_ui.agent, file_upload_folder="./data").launch(
    share=False, server_name="127.0.0.1", server_port=port, css=my_ui.DARK_CSS
)
