# -*- coding: utf-8 -*-
"""回滚演练断言：期望哪个版本就说清楚，跑错版本要当场判假。"""
import sys
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
want = sys.argv[1]
import importlib
my_ui = importlib.import_module("my_ui")
import gradio as gr
src = open(my_ui.__file__, encoding="utf-8").read()
lines = src.count("\n") + 1
has_gate = hasattr(my_ui, "GATED_TOOLS")
has_verdict = hasattr(my_ui, "DENIED_VERDICT")
has_step_card = hasattr(my_ui.OpsUI, "_step_card")
has_approval_card = hasattr(my_ui.OpsUI, "_approval_card")
has_stats_msg = hasattr(my_ui.OpsUI, "_stats_message")
has_thread = "threading.Thread" in src
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
app = ui.create_app()
tools = sorted(ui.agent.tools)
gated = [n for n in ("write_file", "run_python") if getattr(ui.agent.tools[n], "_opsui_gated", False)]
print(f"[{want}] my_ui.py 行数={lines} GATED_TOOLS={has_gate} DENIED_VERDICT={has_verdict} "
      f"_step_card={has_step_card} _approval_card={has_approval_card} _stats_message={has_stats_msg} "
      f"thread={has_thread} app={type(app).__name__} 已装闸={gated}")
ok = True
if want == "v1.2":
    ok = (not has_gate) and (not has_step_card) and (not has_approval_card) and has_stats_msg \
        and (not has_thread) and isinstance(app, gr.Blocks) and gated == [] and lines == 463
elif want == "v1.3":
    ok = has_gate and has_verdict and has_step_card and has_approval_card and (not has_stats_msg) \
        and has_thread and isinstance(app, gr.Blocks) and sorted(gated) == ["run_python", "write_file"] \
        and lines == 851
print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
