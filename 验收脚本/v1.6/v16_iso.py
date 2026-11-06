import faulthandler, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
faulthandler.dump_traceback_later(12, exit=True)
import gradio as gr
import my_ui
my_ui.DB_PATH = Path(tempfile.mkdtemp()) / "h.sqlite3"
from smolagents.memory import ActionStep, TaskStep
from smolagents.monitoring import Timing, TokenUsage

def fake_stream(self, message, history):
    memx = self.agent.memory
    memx.steps.append(TaskStep(task="iso"))
    memx.steps.append(ActionStep(step_number=1, timing=Timing(start_time=1.0, end_time=2.0),
                                 observations="o", token_usage=TokenUsage(input_tokens=1, output_tokens=1)))
    yield [gr.ChatMessage(role="assistant", content="card")]

my_ui.OpsUI._stream_response = fake_stream
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
print("on_load:", type(ui._on_load()[0].get("value")), flush=True)
n = 0
for tup in ui._respond("iso题", None):
    n += 1
    print("frame", n, "radio keys:", sorted(k for k in tup[2] if k != "__type__"), flush=True)
print("frames:", n, flush=True)
