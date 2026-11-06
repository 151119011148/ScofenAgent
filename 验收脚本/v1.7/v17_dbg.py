# -*- coding: utf-8 -*-
import sys, pathlib, tempfile, threading, time
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui, gradio as gr, sqlite3
my_ui.DB_PATH = pathlib.Path(tempfile.mkdtemp(prefix="v17dbg-")) / "h.sqlite3"
print("tools:", list(my_ui.agent.tools))
print("gated now:", {k: getattr(v, "_opsui_gated", False) for k, v in my_ui.agent.tools.items() if k in my_ui.GATED_TOOLS})
LOG = []
orig_gated = my_ui.OpsUI._gated_call
def spy(self, name, original, args, kwargs):
    r = orig_gated(self, name, original, args, kwargs)
    LOG.append((name, repr(r)[:80]))
    return r
my_ui.OpsUI._gated_call = spy

def fake_run(task, images=None, stream=True, reset=False):
    from smolagents.memory import ActionStep, ToolCall
    from smolagents.monitoring import Timing, TokenUsage
    mem = my_ui.agent.memory
    mem.steps.append(my_ui.TaskStep(task=task))
    t0 = time.time()
    th = threading.Thread(target=lambda: (time.sleep(0.6), [ap.decide("allowed") for ap in UIREF["ui"]._pending_snapshot()]))
    th.start()
    obs = my_ui.agent.tools["run_python"](code="print(7*7)")
    th.join()
    ap_list = [(a.tool, a.decision, round(a.waited, 3)) for a in UIREF["ui"]._pending_snapshot()]
    print("  [worker] after tool call, pending=", ap_list, "obs=", repr(str(obs))[:60])
    st = ActionStep(step_number=1, timing=Timing(start_time=t0, end_time=time.time()),
                    tool_calls=[ToolCall(name="run_python", arguments={"code": "print(7*7)"}, id="c1")],
                    observations=str(obs), token_usage=TokenUsage(input_tokens=2349, output_tokens=22))
    mem.steps.append(st)
    yield [gr.ChatMessage(role="assistant", content="卡", metadata={"title": "🛠 第 1 步", "status": "done"})]
UIREF = {"ui": None}
my_ui.agent.run = fake_run
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
UIREF["ui"] = ui
print("gated after init:", {k: getattr(v, "_opsui_gated", False) for k, v in my_ui.agent.tools.items() if k in my_ui.GATED_TOOLS})
last = None
for t in ui._respond({"text": "V9 基线"}, None):
    last = t
print("pending_wait after run:", my_ui.OpsUI._pending_wait)
print("step attrs:", [(type(s).__name__, getattr(s, "_opsui_wait", None)) for s in my_ui.agent.memory.steps])
print("_run_wait:", ui._run_wait, "_run_secs:", round(ui._run_secs, 2))
print("stats:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ui._stats().items() if k in ("task_secs", "task_wait", "step_no")})
print("LOG:", LOG)
