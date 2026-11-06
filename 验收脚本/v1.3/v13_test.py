"""v1.3 离线判定测试：不打网络，用假 run() 驱动 OpsUI 的线程版生成器。

覆盖：V4 一 step 一卡 / P0-2 允许·拒绝·停止·超时四条出口 / 门只套在写路径上。
"""

import faulthandler
import pathlib
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

import my_coding_agent as M  # noqa: E402
import my_ui as U  # noqa: E402
from smolagents import AgentError  # noqa: E402
from smolagents.agent_types import AgentText  # noqa: E402
from smolagents.memory import ActionStep, FinalAnswerStep, ToolCall  # noqa: E402
from smolagents.models import ChatMessageStreamDelta  # noqa: E402
from smolagents.monitoring import Timing, TokenUsage  # noqa: E402

faulthandler.enable()
faulthandler.dump_traceback_later(40, repeat=True)  # 挂住时把所有线程栈打到 stderr
U.DB_PATH = Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.3/run/v13-history.sqlite3")
agent = U.agent

fails = []


def check(name, cond, detail=""):
    print(("  ok  " if cond else "  FAIL") + f" {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def titles(msgs):
    return [ (m.metadata or {}).get("title", "") for m in msgs ]


def step_cards(msgs):
    return [t for t in titles(msgs) if t.startswith("🛠")]


def pend_cards(msgs):
    return [t for t in titles(msgs) if "待批" in t]


EFFECT = Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.3/run/v13-effect.txt")


def make_run(tool_kwargs, steps=1, raise_after=None):
    """假的 agent.run：在**消费它的那条线程**（= worker）里真调工具。"""

    def run(task, images=None, stream=False, reset=False, additional_args=None):
        def gen():
            for n in range(1, steps + 1):
                yield ChatMessageStreamDelta(content="先看")
                yield ChatMessageStreamDelta(content="一眼")
                t0 = time.time() - 3.4
                obs = str(agent.tools["run_python"](code=tool_kwargs["code"])).strip()
                yield ActionStep(
                    step_number=n,
                    timing=Timing(t0, time.time()),
                    model_output="我要跑一段代码 ```python\nprint(1)\n```",
                    tool_calls=[ToolCall(name="run_python", arguments={"code": tool_kwargs["code"]}, id=f"c{n}")],
                    observations=obs,
                    token_usage=TokenUsage(6220, 16),
                )
            if raise_after is not None:
                raise raise_after
            yield FinalAnswerStep(output=AgentText("结论已给"))

        return gen()

    return run


def drive(ui, frames):
    """消费生成器，把每帧存下来；返回 (frames, 抛出的异常或 None)。"""
    err = None
    try:
        for msgs in ui._stream_response("跑一下", []):
            frames.append(list(msgs))
    except BaseException as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        err = exc
    return err


def fresh_ui():
    return U.OpsUI(agent, file_upload_folder="/tmp/v13-uploads")


# ---- 0. 门只套在写路径上，且没改动模块级工具对象 ---------------------------------
print("0 安装门")
ui0 = fresh_ui()
check("run_python 被换成副本", agent.tools["run_python"] is not M.run_python)
check("write_file 被换成副本", agent.tools["write_file"] is not M.write_file)
check("模块级 run_python.forward 未被改写", "gated" not in repr(M.run_python.forward))
check("只读工具 read_file 没套门", agent.tools["read_file"] is M.read_file)
check("重复安装不会再套一层（幂等标记）", getattr(agent.tools["run_python"], "_opsui_gated", False) is True)
fresh_ui(); fresh_ui()
check("三个实例后仍然只有一层门", getattr(agent.tools["run_python"], "_opsui_gated", False) is True)
check("签名保留（审批卡要按它展开参数）", "code" in str(__import__("inspect").signature(agent.tools["run_python"].forward)))

print("1 允许执行（正式路径：先起线程点按钮）")
EFFECT.unlink(missing_ok=True)
agent.run = make_run({"code": "open(%r,'w').write('ran')" % str(EFFECT)})
ui = fresh_ui()
frames = []
clicked = []


def click_later():
    for _ in range(400):
        if ui._unanswered():
            ui._decide("allowed")
            clicked.append(time.time())
            return
        time.sleep(0.02)
    clicked.append(None)


import threading  # noqa: E402

th = threading.Thread(target=click_later, daemon=True)
th.start()
err = drive(ui, frames)
th.join(timeout=5)
check("2a 没有异常冒出", err is None, repr(err))
check("2b 按钮真的被点到（审批出现过）", clicked != [None], str(clicked))
flat = frames[-1] if frames else []
check("2c 一 step 一张卡", len(step_cards(flat)) == 1, str(titles(flat)))
check("2d 成功卡带 🟢", any("🟢 成功" in t for t in step_cards(flat)), str(step_cards(flat)))
check("2e 标题带步数·工具·耗时·token", all(("第 1 步" in t and "run_python" in t and "in 6,220" in t) for t in step_cards(flat)), str(step_cards(flat)))
check("2f 允许后副作用真的发生（文件落盘）", EFFECT.exists())
check("2g 审批卡收尾成 🟢 已允许", any("已允许" in t for t in pend_cards(flat)) or not any("等待审批" in t for t in pend_cards(flat)), str(pend_cards(flat)))
check("2h 待批队列已清空", not ui._pending, str([(a.tool, a.decision, round(time.time() - a.created, 1)) for a in U.OpsUI._pending]))
check("2i 思考只出现一次（流式泡已被卡片取代）", not any("先看一眼" in str(m.content) and not (m.metadata or {}).get("title") for m in flat), str(titles(flat)))
check("2j 正文里 ``` 围栏没被内容里的三反引号打断", any("````python" in str(m.content) or "```python" in str(m.content) for m in flat))

# ---- 3. 拒绝 ---------------------------------------------------------------------
print("3 拒绝执行")
EFFECT.unlink(missing_ok=True)
agent.run = make_run({"code": "open(%r,'w').write('ran')" % str(EFFECT)})
ui = fresh_ui()
frames = []


def click_deny():
    for _ in range(400):
        if ui._unanswered():
            ui._decide("denied")
            return
        time.sleep(0.02)


th = threading.Thread(target=click_deny, daemon=True)
th.start()
err = drive(ui, frames)
th.join(timeout=5)
flat = frames[-1] if frames else []
check("3a 无异常", err is None, repr(err))
check("3b 卡上标 ⚪ 已拒绝", any("⚪ 已拒绝" in t for t in step_cards(flat)), str(step_cards(flat)))
check("3c 模型收到「用户拒绝执行」的观察值", any("用户拒绝执行" in str(m.content) for m in flat))
check("3d 拒绝后一行代码都没跑（文件不存在）", not EFFECT.exists())

# ---- 4. 停止：卡在审批上时按停止，必须能解开 --------------------------------------
print("4 停止时结算审批")
EFFECT.unlink(missing_ok=True)
agent.run = make_run({"code": "open(%r,'w').write('ran')" % str(EFFECT)}, raise_after=AgentError("Agent interrupted.", agent.logger))
ui = fresh_ui()
frames = []


def click_stop():
    for _ in range(400):
        if ui._unanswered():
            ui._stop()
            return
        time.sleep(0.02)


th = threading.Thread(target=click_stop, daemon=True)
th.start()
err = drive(ui, frames)
th.join(timeout=5)
alive = [t for t in threading.enumerate() if t.name == "agent-run"]
check("4a AgentError 被原样重放到 UI 侧", isinstance(err, AgentError), repr(err))
check("4b 停止后 worker 线程已退出（没挂在审批上）", not alive, str(alive))
check("4c 待批项已结算", not ui._unanswered())
flat = frames[-1] if frames else []
check("4c2 步骤卡写「已取消」而不是「已拒绝」", any("⚪ 已取消" in t for t in step_cards(flat)), str(step_cards(flat)))
check("4c3 状态字面量只允许 pending/done", all((m.metadata or {}).get("status") in (None, "pending", "done") for m in flat), str([(m.metadata or {}).get("status") for m in flat]))
check("4d 停止后未执行（文件不存在）", not EFFECT.exists())
check("4e 卡上写「随停止取消」", any("随停止取消" in (str(m.content) + str((m.metadata or {}).get("title", ""))) for m in flat), str(titles(flat)))

# ---- 5. 超时自动拒绝 --------------------------------------------------------------
print("5 超时自动拒绝")
old = U.APPROVAL_TIMEOUT
U.APPROVAL_TIMEOUT = 1.0
EFFECT.unlink(missing_ok=True)
agent.run = make_run({"code": "open(%r,'w').write('ran')" % str(EFFECT)})
ui = fresh_ui()
frames = []
t0 = time.time()
err = drive(ui, frames)
U.APPROVAL_TIMEOUT = old
flat = frames[-1] if frames else []
check("5a 无人审批时线程自己解开（1 秒超时）", time.time() - t0 < 20, f"{time.time() - t0:.1f}s")
check("5b 超时按拒绝处理", any("超时未批" in str(m.content) for m in flat))
check("5c 超时未批 = 未执行（文件不存在）", not EFFECT.exists())

# ---- 6. 多步：一步一卡，不重复 ----------------------------------------------------
print("6 两步 = 两张卡")
EFFECT.unlink(missing_ok=True)
agent.run = make_run({"code": "open(%r,'w').write('ran')" % str(EFFECT)}, steps=2)
ui = fresh_ui()
frames = []


def click_all():
    for _ in range(1200):
        if ui._unanswered():
            ui._decide("allowed")
        time.sleep(0.02)


th = threading.Thread(target=click_all, daemon=True)
th.start()
err = drive(ui, frames)
th.join(timeout=1)
flat = frames[-1] if frames else []
check("6a 无异常", err is None, repr(err))
check("6b 正好两张步骤卡", len(step_cards(flat)) == 2, str(step_cards(flat)))
check("6c 两张卡各标第 1/第 2 步", "第 1 步" in step_cards(flat)[0] and "第 2 步" in step_cards(flat)[1], str(step_cards(flat)))
check("6d 最终答案是独立气泡（没折进卡里）", any("结论已给" in str(m.content) and not (m.metadata or {}).get("title") for m in flat), str(titles(flat)))
check("6e 本题累计在第二张卡里是两倍", any("in 12,440 / out 32" in str(m.content) for m in flat), str([str(m.content)[-160:] for m in flat]))

# ---- 7. _fence 的对抗样例 --------------------------------------------------------
print("7 围栏")
check("6f ⏹ 收尾气泡的 status 也是合法字面量", U.OpsUI._stream_response is not None and chr(34) + "status" + chr(34) + ": " + chr(34) + "complete" + chr(34) not in pathlib.Path("my_ui.py").read_text(), "my_ui.py 里还有 status: complete")
check("7a 正文含 ``` 时栅栏加长", "````\na\n```b\n````" == U.OpsUI._fence("a\n```b"))
check("7b 普通正文用三反引号", U.OpsUI._fence("plain") == "```\nplain\n```")
check("7c 长参数截断并写明原长", "截掉" in U.OpsUI._args_text({"content": "x" * 5000}, 1200))

faulthandler.cancel_dump_traceback_later()
print("\nRESULT", "PASS" if not fails else f"FAIL {len(fails)}: {fails}")
sys.exit(1 if fails else 0)
