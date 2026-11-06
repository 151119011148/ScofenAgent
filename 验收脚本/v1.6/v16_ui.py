import sys, os, pathlib
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui

my_ui.DB_PATH = pathlib.Path(os.environ.get("V16DB", "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16-live-hist.sqlite3"))
my_ui.OpsUI(my_ui.agent, file_upload_folder="./data").launch(
    share=False, server_name="127.0.0.1", server_port=7861, css=my_ui.DARK_CSS
)
