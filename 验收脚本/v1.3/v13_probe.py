"""v1.3 在线探针：真模型 + 真审批，跑在 7861，不动 7860 的日常实例。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path("/Users/gaoying/Desktop/study/ai学习/smolagents")))
import my_ui  # noqa: E402

ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
demo = ui.create_app()
demo.launch(server_name="127.0.0.1", server_port=7861, share=False, css=my_ui.DARK_CSS, quiet=True)
print("PROBE-LAUNCHED 7861", flush=True)
import time  # noqa: E402

while True:
    time.sleep(1)
