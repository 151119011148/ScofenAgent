# -*- coding: utf-8 -*-
"""v1.7 第③步：给实跑准备一个**真 v1 时代**的库（兼容读的活样本）。

两条旧会话的记忆 payload 用 .rollback/v1.6/my_ui.py 里那份**旧编码器**现编——
不是手写的假 v1，这样新代码读它读出来的东西才算数（fmt=v1、且没有 wait 这一格）。
"""
import importlib.util as ilu
import pathlib
import sys

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr  # noqa: E402
import my_ui  # noqa: E402
from smolagents.memory import ActionStep, TaskStep, ToolCall  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

DB = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17-live-hist.sqlite3")
for suf in ("", "-wal", "-shm"):
    p = pathlib.Path(str(DB) + suf)
    if p.exists():
        p.unlink()

spec = ilu.spec_from_file_location("my_ui_v16", "/Users/gaoying/Desktop/study/ai学习/.rollback/v1.6/my_ui.py")
old_ui = ilu.module_from_spec(spec)
spec.loader.exec_module(old_ui)
assert old_ui.MEM_FMT == "v1", old_ui.MEM_FMT

hist = my_ui.History(DB)
rows = []
for title, secs, toks in [("v1旧记忆-甲", 41.0, (2349, 22)), ("v1旧记忆-乙", 12.5, (1180, 9))]:
    sid = hist.ensure(None)
    hist.save(sid, [
        gr.ChatMessage(role="user", content=title, metadata={"status": "done"}),
        gr.ChatMessage(role="assistant", content="（v1 时代攒下的答复）", metadata={"status": "done"}),
    ])
    blob = old_ui.encode_memory([
        TaskStep(task="请" + title),
        ActionStep(
            step_number=1,
            timing=Timing(start_time=1.0, end_time=1.0 + secs),
            tool_calls=[ToolCall(name="run_python", arguments={"code": "print(1)"}, id="call_old")],
            observations="exit=0\n1\n",
            token_usage=TokenUsage(input_tokens=toks[0], output_tokens=toks[1]),
        ),
    ])
    hist.save_memory(sid, blob)
    rows.append((sid, title, len(blob), blob[:40]))
for sid, title, n, head in rows:
    print("seeded", sid, title, "payload", n, "B", head)
import sqlite3  # noqa: E402
c = sqlite3.connect(str(DB))
print("fmt in db:", [r[0] for r in c.execute("select json_extract(payload,'$.fmt') from memory")])
print("choices:", hist.choices())
print("新代码读 v1 读回几步:", [len(my_ui.decode_memory(hist.load_memory(sid))) for sid, _, _, _ in rows])
