import sys
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
from my_ui import OpsUI, DARK_CSS
from my_agent import agent
OpsUI(agent, file_upload_folder="./data").launch(
    share=False, server_name="127.0.0.1", server_port=7861, css=DARK_CSS)
