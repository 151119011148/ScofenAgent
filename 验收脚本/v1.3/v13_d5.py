# D5 判定：同一页面连问两题（不换会话），历史库里前一轮是不是被覆盖掉了。
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui  # noqa: E402

db = Path(tempfile.mkdtemp()) / "hist.sqlite3"
my_ui.DB_PATH = db

fake_steps = []


def fake_run(task, images=None, stream=True, reset=False):
    def gen():
        from smolagents import ActionStep, FinalAnswerStep  # noqa: F401
        # 只喂最小事件流：一题一步，不调工具
        for ev in _mk(task):
            yield ev
    return gen()


def _mk(task):
    from smolagents.memory import ActionOutput, MemoryStep, SystemPromptStep, TaskStep
    from smolagents.monitors import TokenUsage
    from dataclasses import dataclass, field

    @dataclass
    class S1(MemoryStep):
        def to_chat_messages(self, *a, **k):
            return []

        def dict(self):
            return {"role": "assistant", "content": "x"}

    t = TaskStep(input=task)
    a = ActionStep(0)
    a.token_counts = TokenUsage(input=1000, output=10)
    a.timing = 1.0
    a.model_outputs = ["直接答"]
    a.action = {"type": "final_answer", "name": "final_answer", "arguments": {"answer": task[:10]}}
    a.action_output = [ActionOutput(output="ok", is_error=False)]
    f = FinalAnswerStep("done")
    return [S1(), t, a, f]


ui = my_ui.OpsUI(my_ui.build_agent() if hasattr(my_ui, "build_agent") else None)
print("agent:", type(ui.agent).__name__)
ui.agent.run = fake_run

sid = None
for q in ["第一题", "第二题"]:
    out = None
    for out in ui._respond(q, sid):
        pass
    sid = out[4]
    print("提问", q, "→ sid", sid)

c = sqlite3.connect(db)
print("sessions:", list(c.execute("select id,title from sessions")))
rows = list(c.execute("select session_id,ord,role,substr(content,1,20) from messages order by session_id,ord"))
print("messages:", rows)
titles = [json.loads(m).get("title") for (_, _, _, m) in c.execute("select 1,role,content,meta from messages order by ord")]
print("titles:", titles)
print("D5 结论：", "两题共用一个 sid 且前一题消息被删（D5 成立）"
      if len(list(c.execute("select id from sessions"))) == 1 else "各题独立会话（D5 不成立）")
