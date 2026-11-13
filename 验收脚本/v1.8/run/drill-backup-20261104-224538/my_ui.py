import copy
import dataclasses
import html
import inspect
import json
import os
import queue
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import gradio as gr
from my_agent import agent
import my_audit
import my_mcp

from smolagents import (
    AgentError,
    AgentMaxStepsError,
    ChatMessageStreamDelta,
    GradioUI,
    PlanningStep,
    agglomerate_stream_deltas,
)
from smolagents.gradio_ui import _clean_model_output, _process_final_answer_step
from smolagents.memory import ActionStep, AgentMemory, FinalAnswerStep, TaskStep, ToolCall
from smolagents.monitoring import Timing, TokenUsage
from smolagents.utils import make_json_serializable

DB_PATH = Path(__file__).resolve().parent / ".agent-history.sqlite3"

# P0-2：只拦「会动东西」的两只手。只读工具（read_file / list_dir / grep_files）不弹审批，
# 否则一次检索三连问点三遍，比不加还慢。
# A2：这一份是**本地**名单。外部 MCP 工具不在这里写死——它们是运行时挂上来的（见 my_mcp.attach），
# 名单由 _gate_names() 在装门那一刻现拼：GATED_TOOLS + 这把桥挂上的每一只。
# 为什么挂上来的全要批，连「读，无副作用」的 get_current_time 也不放过：本地那三只是为了省点击
# 才放行，判据是「这只手只读我这一个根目录」；MCP 工具是**另一个进程**，模型对它的参数没有任何
# 本地约束能兜底，所以一律按「外部动作」算。
GATED_TOOLS = ("write_file", "run_python")
# P0-4：计划审批那张单子的名字。它不是一件工具，这个名字只喂两处显示——状态条上那颗
# 「待批」药丸和审批卡标题（两边都读 ap.tool，见 _status_html / _approval_card）。
PLAN_APPROVAL_NAME = "计划"
# 超时按拒绝处理：题可以重问，worker 线程挂着不放会永远占住 agent。
APPROVAL_TIMEOUT = 600.0
# V8 的显示门槛：不满 0.05 秒的"等待"不值得单列一格。存在这条主要是「入队即随停止取消」
# 那一路（D7）——单子挂上去不到一毫秒就结了算，账上确实有 0.0004 秒，屏上写「审批 0.0s」
# 就纯属噪声了（交付形态实测抓到：⚪ 已取消 · 0.9s · 审批 0.0s）。
APPROVAL_WAIT_MIN = 0.05
DECISION_LABEL = {
    "pending": "等待审批",
    "allowed": "已允许",
    "denied": "已拒绝",
    "cancelled": "随停止取消",
    # D8：断开（刷新/关页面）那一路的措辞。decision 仍是 cancelled，只有界面读数换字，
    # 见 _approval_card 的 shown 参数。
    "cancelled_by_reload": "随中断取消",
    "timeout": "超时未批",
}
DECISION_DOT = {"pending": "🟡", "allowed": "🟢", "denied": "⚪", "cancelled": "⏹",
                "cancelled_by_reload": "⏹", "timeout": "⏳"}
# 拒绝时交回模型的观察值。措辞要让它明白「没执行、别当成已执行」。
DENIED_OBSERVATION = {
    "denied": "用户拒绝执行，未产生任何副作用。请改用只读工具，或直接把结论交出来。",
    "cancelled": "用户按了停止，本次执行已取消，未产生任何副作用。",
    "timeout": f"审批超过 {int(APPROVAL_TIMEOUT)} 秒无人处理，已自动拒绝，未产生任何副作用。",
}
DENIED_VERDICT = {"denied": "已拒绝", "cancelled": "已取消", "timeout": "超时未批"}

# ---- P1-a：重复调用检测与熔断 ----------------------------------------------------------
# 立项数据（验收脚本/v1.8/run/v18_p0abc_live.out 第五、六节）：同一道「删掉某某目录」的题，
# 旧代码两个样本里同名同参重复各 2 次／3 次，list_dir({}) 一个样本里发三遍，8 步用满交不出答案；
# 第④刀把报错文案补了「不要用同一个参数再打一遍」之后，重复数掉到 0／0，**但 8 步照样用满**——
# 只是从原地绕圈变成挨个列子目录绕圈。文案管不住的东西只能靠拦：
#   · 框架的 system_prompt 规则 4 早就写着「Never re-do a tool call that you previously did
#     with the exact same parameters」，实测它照犯——所以这不是补规矩，是执法。
#   · 只读的三只手不在审批名单里（GATED_TOOLS 只写路径那两只），重复调用恰恰全在只读那侧，
#     所以这一层必须套在**所有**工具上，不能只套审批那两只。
DUP_BLOCK_LIMIT = 2
DUP_MARK = "【重复调用未执行"
# 熔断句和警告句共用 DUP_MARK 开头（观察值里同时出现两种很正常：一步并行调用一只撞墙一只没有），
# 所以判「这步里有没有熔断」要认后面那截，不能靠 DUP_MARK 计数。
DUP_FUSE_MARK = "【重复调用未执行·已熔断"
DUP_OBSERVATION = (
    "【重复调用未执行】本题内这已经是第 {n} 次发出**完全一样**的调用（同工具、同参数），"
    "这一次没有真的执行，也不会有任何新信息。请换一个参数／换一个工具，或者直接把答案交出来。"
)
DUP_FUSE_OBSERVATION = (
    "【重复调用未执行·已熔断】本题第 {n} 次发同样的调用，累计挡下 {blocked} 次重复，"
    "已经超过上限 {limit}；这一次同样没有执行，本题到这里结束，不会再有下一步。"
    "要接着做请重新提问，并把参数改一下。"
)

# V6：会话记忆的持久化。上游 AgentMemory 没有 (de)serializer（memory.py:214-232），
# 所以「要存哪些字段」不能凭感觉列，按**下一轮模型真正读到的东西**来定：
# agents.py:767-769 的 write_memory_to_messages 只做两件事——system_prompt.to_messages()
# 加逐条 step.to_messages()。下面这三组字段就是各 step 的 to_messages() 读到的全部（外加
# 卡片/口径要用的 token 与计时），model_input_messages 那种"当时的整段提示词"不存：
# 它只服务于日志回放，存下来会让一条会话膨胀成 O(n²)。
MEM_FMT = "v2"
# V9：v1 -> v2 加的就是 ActionStep 上那一格 wait（审批等待秒数）。升版本必须带兼容读：
# decode_memory 原先见 fmt 不等于 MEM_FMT 就整块当"没有记忆"，只改版本号会让库里
# 已有的会话当场失忆（/tmp/v17_base.py E1 拿真实库的 7 条 payload 演过：v2 strict 全读空）。
# 读兼容 = 认这一组版本号；v1 的步没有 wait，读出来按 0 处理，其余字段两版逐字相同。
MEM_FMT_READ = ("v1", "v2")
MEM_FIELDS = {
    "TaskStep": ("task",),
    "ActionStep": (
        "step_number",
        "timing",
        "tool_calls",
        "error",
        "model_output",
        "code_action",
        "observations",
        "action_output",
        "token_usage",
        "is_final_answer",
    ),
    "PlanningStep": ("plan", "timing", "token_usage"),
}
# 注意 wait 不在上面这张表里：MEM_FIELDS 的口径是"下一轮模型读到的字段"，而审批等待
# 只是界面上的账，to_messages() 不认它。所以它在 encode_memory 里单独走一条路，
# 读回来时挂回 step 对象的私有属性 _opsui_wait——显示层（_stats / _step_card）
# 认的就是这个属性，不用改一行。


def _error_types() -> dict:
    """AgentError 及其全部子类，按类名索引（恢复报错步时要知道原类型）。"""
    out, stack = {}, [AgentError]
    while stack:
        cls = stack.pop()
        out.setdefault(cls.__name__, cls)
        stack.extend(cls.__subclasses__())
    return out


def _decode_error(d):
    """从 {"type","message"} 还原一个 AgentError。

    不能直接 cls(message, logger)——那个构造子第二参数是必需的 AgentLogger，并且会当场
    log_error 一条（memory.py 的 to_messages 只在下一轮把它当文本喂模型，不该在恢复时
    往日志里喷）。所以绕开 __init__，只把 Exception 的 args 和 .message 补齐：
    str(err) 与 err.dict() 的结果和原来一致。
    """
    if not isinstance(d, dict):
        return None
    message = str(d.get("message") or "")
    cls = _error_types().get(str(d.get("type") or ""), AgentError)
    err = cls.__new__(cls)
    Exception.__init__(err, message)
    err.message = message
    return err


def _decode_timing(d):
    if not isinstance(d, dict) or d.get("start_time") is None:
        return None
    return Timing(start_time=float(d["start_time"]), end_time=d.get("end_time"))


def _decode_usage(d):
    # total_tokens 是 init=False 的派生字段（monitoring.py:44），按那两个数重建即可
    if not isinstance(d, dict) or "input_tokens" not in d:
        return None
    return TokenUsage(input_tokens=int(d["input_tokens"]), output_tokens=int(d.get("output_tokens") or 0))


def encode_memory(steps) -> str:
    """把一份 AgentMemory.steps 序列化成 JSON 文本（存进库里，重启后回灌）。"""
    rows = []
    for st in list(steps):
        name = type(st).__name__
        fields = MEM_FIELDS.get(name)
        if fields is None:
            continue  # 框架新加的步类型：下一轮 to_messages 也读不到它，不硬存
        row = {"_t": name}
        for f in fields:
            v = getattr(st, f, None)
            if v is None:
                continue
            if f == "timing":
                row[f] = v.dict()
            elif f == "token_usage":
                row[f] = {"input_tokens": v.input_tokens, "output_tokens": v.output_tokens}
            elif f == "tool_calls":
                row[f] = [tc.dict() for tc in v]
            elif f == "error":
                row[f] = {"type": type(v).__name__, "message": str(getattr(v, "message", v))}
            elif f == "action_output":
                row[f] = make_json_serializable(v)
            else:
                # 剩下这批（task / plan / observations / code_action / model_output /
                # step_number / is_final_answer）是**逐字喂给模型**的文本或标记位，原样存。
                # 过一遍 make_json_serializable 会把长得像 JSON 的观察值（"{...}"）解析成
                # dict（utils.py:146-153），回放时再 str() 出来就是单引号的 Python 字面量，
                # 和模型上一轮看到的不是同一串字——口径上算"记得"，逐字上不算。
                row[f] = v if isinstance(v, (str, int, float, bool)) else make_json_serializable(v)
        # V9：审批等待那一格。_stream_response 领账时把它写在 step._opsui_wait 上，
        # v1.6 时这个属性只活在进程里（落库没人认，重启回灌读作 0，就是看板 V9 那条边界）；
        # 现在它跟着记忆一起进库，只有真等过才写这一格——没等过的步编出来和 v1 逐字相同，库里体积不涨。
        if name == "ActionStep":
            waited = getattr(st, "_opsui_wait", 0.0) or 0.0
            if waited:
                row["wait"] = round(float(waited), 3)
        rows.append(row)
    return json.dumps({"fmt": MEM_FMT, "steps": rows}, ensure_ascii=False)


def decode_memory(blob) -> list:
    """encode_memory 的逆操作。坏数据一律当"没有记忆"，别让它把提问带崩。"""
    try:
        data = json.loads(blob)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("fmt") not in MEM_FMT_READ:
        return []  # 认不出的版本（v0、将来 v3）仍旧整块当没记忆，不猜着读
    steps = []
    for row in data.get("steps") or []:
        if not isinstance(row, dict):
            continue
        kind = row.get("_t")
        try:
            if kind == "TaskStep":
                steps.append(TaskStep(task=str(row.get("task") or "")))
            elif kind == "PlanningStep":
                # 这两个字段在 PlanningStep 上没有默认值（memory.py:151-156），必须显式交；
                # 回放下一步只会用到 plan。
                steps.append(
                    PlanningStep(
                        model_input_messages=[],
                        model_output_message=None,
                        plan=str(row.get("plan") or ""),
                        timing=_decode_timing(row.get("timing")),
                        token_usage=_decode_usage(row.get("token_usage")),
                    )
                )
            elif kind == "ActionStep":
                calls = row.get("tool_calls")
                step = ActionStep(
                    step_number=int(row.get("step_number") or 0),
                    timing=_decode_timing(row.get("timing")),
                    tool_calls=[
                        ToolCall(
                            name=str(c.get("function", {}).get("name") or ""),
                            arguments=c.get("function", {}).get("arguments"),
                            id=str(c.get("id") or ""),
                        )
                        for c in calls
                        if isinstance(c, dict)
                    ]
                    if isinstance(calls, list)
                    else None,
                    error=_decode_error(row.get("error")),
                    model_output=row.get("model_output"),
                    code_action=row.get("code_action"),
                    observations=row.get("observations"),
                    action_output=row.get("action_output"),
                    token_usage=_decode_usage(row.get("token_usage")),
                    is_final_answer=bool(row.get("is_final_answer")),
                )
                # V9：这一格里有多少秒是等人批。v1 的老 payload 没有这个键，读出来就是
                # 0（界面上那一格随之不出现）——不是把整条会话判成没记忆。
                if row.get("wait"):
                    step._opsui_wait = float(row["wait"])
                steps.append(step)
        except (TypeError, ValueError, AttributeError):
            continue  # 单条坏了就丢掉那一条，其余照旧
    return steps

# V2：深色壳。左边这些变量名是 gradio 6.30 自己吐在 :root 上的那批（实测抓的，不是猜的），
# 按同名覆盖就能全站生效；主色 #f97316 保持不动，和 App 图标同色。
DARK_CSS = """
:root {
  color-scheme: dark;
  --body-background-fill: #0d1117;
  --body-text-color: #e6edf3;
  --body-text-color-subdued: #8b949e;
  --block-background-fill: #161b22;
  --block-border-color: #30363d;
  --block-title-text-color: #e6edf3;
  --input-background-fill: #0d1117;
  --input-border-color: #30363d;
  --input-text-color: #e6edf3;
  --border-color-primary: #30363d;
  /* gradio 的 secondary 按钮实测浅灰 rgb(228,228,231) + 黑字，深色底上是块白斑。 */
  --button-secondary-background-fill: #21262d;
  --button-secondary-text-color: #e6edf3;
  --button-border-color: #30363d;
  --spacing-md: 8px;
}
/* gradio 把浅色值硬写在 body 自己的规则里（非 @media），只改 var 覆盖不到它，得直接压。 */
html, body, .gradio-container {
  background: var(--body-background-fill) !important;
  color: var(--body-text-color) !important;
}
footer[aria-label="Gradio footer navigation"] { display: none !important; }
/* 块标题（Chatbot 的 label）gradio 硬编成白底，实测 rgb(255,255,255)。 */
[data-testid="block-label"] {
  background: var(--block-background-fill) !important;
  color: var(--body-text-color-subdued) !important;
  border-color: var(--block-border-color) !important;
}
/* 发送键：gradio 给的是浅灰 rgb(228,228,231)，深色底上像个坏掉的按钮。 */
button.submit-button {
  background: #f97316 !important;
  border-color: #f97316 !important;
  color: #fff !important;
}
/* 停止键在非生成期也一直挂着（实测 idle 时 display:flex），压成"没按下去"的样子。 */
button.stop-button {
  background: #21262d !important;
  border-color: #30363d !important;
  color: #8b949e !important;
}
/* 状态行右侧的自建刹车键：gradio 的 variant="stop" 是大红块，常驻太扎眼。 */
#statusrow button {
  background: #21262d !important;
  border: 1px solid #30363d !important;
  color: #f85149 !important;
  font-size: 13px;
  height: 30px;
}
#statusrow button:active { background: #30363d !important; }
/* P0-2 审批键：平时不可见（visible=False），有待批项时才由后端点亮。 */
#statusrow #approve-btn button {
  background: #238636 !important; border: 1px solid #2ea043 !important;
  color: #fff !important; font-size: 13px; height: 30px;
}
#statusrow #deny-btn button {
  background: #21262d !important; border: 1px solid #f85149 !important;
  color: #f85149 !important; font-size: 13px; height: 30px;
}
/* 审批中的那张卡必须显眼：折叠标题的底色单独上黄边。 */
#statusbar.st-awaiting .pill-state i, #statusbar.st-awaiting .pill-pending i { color: #d29922; }

/* 气泡：gradio 把底色硬编成 rgb(250,250,250)（实测），深色底上就是一排白卡。 */
[data-testid="user"], [data-testid="bot"], .message.user, .message.bot {
  background: var(--block-background-fill) !important;
  color: var(--body-text-color) !important;
  border-color: var(--block-border-color) !important;
}
/* layout="panel" 下浅色底挪到了 .message-row 这一层（实测 user=rgb(255,247,237)、
   bot=rgb(250,250,250)），上面那组选择器盖不住它。 */
.message-row.user-row { background: #1b2430 !important; }
.message-row.bot-row { background: var(--block-background-fill) !important; }
/* 折叠的步卡（🛠️/📝/📊 那几条）gradio 给的也是白底，深色底上文字直接看不见。 */
.thought-group {
  background: var(--block-background-fill) !important;
  border-color: var(--block-border-color) !important;
}
.thought-group summary, .thought-group .label { color: var(--body-text-color) !important; }
/* 输入框外框 gradio 用 rgb(48,54,61)，比正文底亮两档，收一档。 */
#main .form { background: var(--block-background-fill) !important; }
/* 侧栏条目：Radio 的 label 自带浅色底，和侧栏底色对不上。 */
#sessions label { background: transparent !important; }
#main .chatbot { display: block; }

#app { align-items: stretch; gap: 0; }
#sidebar {
  min-width: 208px;
  padding: 12px 10px;
  background: #12171e;
  border-right: 1px solid var(--block-border-color);
}
#brand { display: flex; flex-direction: column; gap: 2px; padding: 2px 4px 10px; }
#brand b { font-size: 15px; color: var(--body-text-color); }
#brand span { font-size: 11px; color: var(--body-text-color-subdued); }
/* 侧栏那一排两个键：gr.Row 默认 gap 在 208px 的栏里会把第二个键挤下去，收一档。
   注意 elem_id 在 gradio 6.30 落在 <button> **自己身上**（实测：document.getElementById('del-btn')
   .tagName === 'BUTTON'），所以写 `#del-btn button` 那条规则永远不命中——直接给 #del-btn。 */
#sessionbtns { gap: 6px; }
#sessionbtns button { font-size: 13px; height: 32px; padding: 0 6px; }
#sessionbtns #del-btn {
  background: #21262d !important; border: 1px solid #30363d !important;
  color: #f85149 !important;
}
#sessionbtns #del-btn:active { background: #30363d !important; }
/* 删除的确认/回执那行字（_flash）。放在状态条下面一行，不占 pill，也不新增状态档。 */
#flash { font-size: 12px; color: #d29922; padding: 2px 0 4px; }
#sessions { gap: 2px; }
#sessions label {
  display: block; padding: 6px 8px; border-radius: 6px; cursor: pointer;
  font-size: 13px; line-height: 1.35; color: var(--body-text-color-subdued);
}
#sessions label:hover { background: #1b222b; color: var(--body-text-color); }
#sessions input[type="radio"] { display: none; }
#sessions label:has(input:checked) {
  background: #1f2937; color: var(--body-text-color);
  box-shadow: inset 2px 0 0 #f97316;
}
#main { padding: 12px 16px; }
#statusbar { display: flex; flex-wrap: wrap; gap: 6px; padding: 2px 0 10px; }
#statusbar .pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 999px; font-size: 12px;
  background: var(--block-background-fill); border: 1px solid var(--block-border-color);
}
#statusbar .pill b { font-weight: 600; color: var(--body-text-color-subdued); }
#statusbar .pill i { font-style: normal; color: var(--body-text-color); font-variant-numeric: tabular-nums; }
#statusbar.st-running .pill-state i { color: #f97316; }
#statusbar.st-stopping .pill-state i, #statusbar.st-maxed .pill-state i { color: #d29922; }
#statusbar.st-stopped .pill-state i { color: #f85149; }
/* P0-4：「计划未批准」不是报错，是人在计划上按的那个 ✖，所以既不跟着 st-stopped 的红，
   也不跟着 st-awaiting 的黄——单独一色，屏上一眼能和「按了停止」分开。 */
#statusbar.st-plan_denied .pill-state i { color: #bc8cff; }
/* P1-a：「重复熔断」单独一色（蓝）。红是给「你按了停止」的，黄是给「步数用满」的，
   这一档谁也没按——是 agent 自己绕圈被拦下，屏上必须和那两档分得开。 */
#statusbar.st-dup_fused .pill-state i { color: #58a6ff; }
/* v2.0：「模型侧拒绝」单独一色（洋红）。红是给「你按了停止」的，这一档你什么都没按，
   是服务商不接这一单——颜色必须离红远一点，屏上才不会读成「我把它停了」。 */
#statusbar.st-model_refused .pill-state i { color: #db61a2; }
/* P0-4：计划面板。实测一份计划 6,195 字符（run/v18_plan_probe.out 的 B 组），
   不封顶会把整个聊天区往下推 200 多行，所以给它一个能滚的高度；面板只在有计划的
   那一题出现（组件本身 visible=False）。 */
#planpanel {
  border: 1px solid var(--block-border-color);
  border-radius: 8px;
  background: var(--block-background-fill);
  padding: 8px 12px;
  max-height: 208px;
  overflow-y: auto;
  font-size: 13px;
}
"""

STATE_LABEL = {
    "idle": "空闲",
    "running": "生成中",
    "awaiting": "等待审批",
    "stopping": "停止中",
    "done": "完成",
    "stopped": "已停止",
    # D8：这一档专供「生成器被客户端关掉」那一路（刷新/关页面）。以前这条路走的是
    # state="stopped"，和「用户按了 ■ 停止」共用一个字——可那一路没人按任何东西，
    # 卡片也从来没被画成终态，事后看就像你把这道题停了。
    "interrupted": "已中断",
    "maxed": "步数用满",
    # P0-4：否决**计划**停在的是这一档，不是「已停止」。两者在屏幕上必须一眼分得开：
    # 前者是「这份计划我不认」，后者是「我按了 ■ 停止」。工具审批那一路没有这个问题
    # （拒一个工具题还在跑），计划审批是本题的第一件事，否掉就等于整题没开工。
    "plan_denied": "计划未批准",
    # P1-a：熔断那一档。它看起来也是「跑不完」，但和 st-stopped 不是一回事：那一档是你按了 ■，
    # 这一档是 agent 自己在绕圈、被拦下来收尾。混成「已停止」就变成用户在告自己的状。
    "dup_fused": "重复熔断",
    # v2.0：服务商整题拒掉（欠费／key／限流）单独一档。理由和上面两档同源——「已停止」这三个字
    # 只有在你真的按过 ■ 的时候才是实话；这一档里这台机器什么都没做错，第一步的模型调用就没进门。
    # 实测（2026-11-04）：`400 Access denied … account is in good standing`，0.32 秒就回来。
    "model_refused": "模型侧拒绝",
}

# 模型侧**整题拒掉**的指纹：命中谁都不算「跑错」，也不算「你按了停止」，是服务商不接这一单。
# 判文本不判异常类型：框架把 SDK 的错误包成 AgentGenerationError（agents.py:1325），
# 类型上和真正的实现错误同名，只有 message 分得开。
# 命中不了就走原来的 ⏹ 那一档——宁可少认一档，不要把别的报错也盖成「账户问题」。
MODEL_REFUSAL_MARKS = (
    "access denied",  # 百炼：账户状态／风控（今天实测到的就是这句，附 #overdue-payment 链接）
    "overdue-payment",
    "arrears",
    "incorrect api key",
    "invalid api key",
    "exceeded your current request limit",  # 429 限流：今天 qwen-turbo 给的是这句
    "quota",
    "region not enabled",
)


def model_refusal(exc: BaseException) -> str | None:
    """是服务商那一侧拒收就返回那一句原文，其余异常返回 None。

    顺着 `__cause__` / `__context__` 往上找：框架抛的是包装过的那条，
    openai 的 BadRequestError 在 `from e` 那一节里。
    """
    seen: set[int] = set()
    node: BaseException | None = exc
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        low = str(node).lower()
        if any(mark in low for mark in MODEL_REFUSAL_MARKS):
            return " ".join(str(node).split())[:400]
        node = node.__cause__ or node.__context__
    return None


class PlanDeniedError(AgentError):
    """P0-4：计划被否决／超时未批之后，从审批门里抛出去的那一条。

    为什么非得抛异常：门包在 `agent._run_stream` 外面（见 _install_plan_gate），
    这份计划还没进模型记忆（agents.py:556-562 是「先 yield、拿到返回值之后才
    `_finalize_step` + `memory.steps.append`」），此时唯一能让 agent 不往下走的办法
    就是不再从这个包装生成器里吐出东西、并把异常交回 `_worker`。
    抛完的后果正是要的语义：那一步永远不进 memory，所以「记忆里有 PlanningStep」
    等价于「这份计划批准过」——重启后从库里读回来的计划一定是批过的。

    【待补】这条决策本身不进模型记忆：下一题重新提问时，模型只看到那个 TaskStep，
    不知道上一份计划被否决过。工具审批那一路是靠 DENIED_OBSERVATION 写进步骤的，
    计划这一路没有对应的落点（框架不给计划审批留观察位）。
    """



class Approval:
    """P0-2 的一条审批单。

    worker 线程在 tool.forward 里 wait()，UI 线程每 0.25 秒轮询渲染这张卡；
    点「允许/拒绝」只改 decision 并置事件，不动会话消息——消息仍由那条流式生成器独占，
    两边不会抢同一个输出。
    """

    def __init__(self, tool: str, args: dict, kind: str = "tool",
                 source: str | None = None, risk: str | None = None):
        self.id = uuid.uuid4().hex[:6]
        self.tool = tool
        self.args = dict(args or {})
        # P0-4：同一套门现在也管「这份计划准不准跑」，不只是工具。kind 决定卡片正文长
        # 什么样（工具那张列参数，计划那张放计划原文），decision 的取值和结算路径一个没多。
        # 默认 "tool"，所以 v1.7 之前所有构造点一字未改。
        self.kind = kind
        # A2：这只手是谁的。source 非空 = 外部 MCP server 里的工具（值 = server 名），
        # risk = 装载白名单里给它写的风险档（见 my_mcp.MCP_SERVERS）。两个都只用于显示与
        # 审计（D3 那行 provenance 读的就是这里），不参与任何判定——批不批还是只看 decision。
        # 默认 None：本地那五只手走的是同一条 _gated_call，不给它们编一个「来源」。
        self.source = source
        self.risk = risk
        self.created = time.time()
        self.decision = "pending"
        # V8：等待时长在 decision 落定那一刻就记好（不是等 worker 线程醒来才记），
        # 这样审批卡第一次画收尾状态时就已经带着这个数。
        self.waited = 0.0
        self._done = threading.Event()

    def decide(self, decision: str) -> None:
        if self.decision == "pending":
            self.decision = decision
            self.waited = time.time() - self.created
            self._done.set()

    def wait(self) -> str:
        if not self._done.wait(APPROVAL_TIMEOUT):
            self.decision = "timeout"
            self.waited = APPROVAL_TIMEOUT
            self._done.set()
        return self.decision


class History:
    """会话侧栏的存储层：存**显示层**的那串消息，一条会话一行行按 ord 存。

    save() 是「整条会话覆盖」（先 DELETE 再按 ord 重插），不是追加——它只有在调用方
    喂进完整列表时才等价于追加，D5 修的就是这个前提（见 _respond 的 base）。
    agent 真正的记忆在 agent.memory，v1.4 起按会话各存一份（见 _bind_memory），
    v1.5 起这一份也落库（memory 表，见 save_memory / load_memory 与 encode_memory）：
    重启后选回旧会话，模型那一边接着记得（看板 V6）。
    """

    def __init__(self, path: Path):
        self.path = str(path)
        with self._tx() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL DEFAULT '新会话',
                  created_at REAL NOT NULL,
                  updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                  ord INTEGER NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  meta TEXT NOT NULL DEFAULT '{}');
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ord);
                CREATE TABLE IF NOT EXISTS memory(
                  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                  payload TEXT NOT NULL,
                  updated_at REAL NOT NULL);
                """
            )

    def _tx(self):
        class _T:
            def __enter__(self2):
                self2.conn = sqlite3.connect(self.path, timeout=10)
                self2.conn.execute("PRAGMA foreign_keys = ON")
                return self2.conn

            def __exit__(self2, exc, val, tb):
                if exc is None:
                    self2.conn.commit()
                else:
                    self2.conn.rollback()
                self2.conn.close()
                return False

        return _T()

    def choices(self, limit: int = 50):
        with self._tx() as c:
            rows = c.execute(
                "SELECT id, title FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [(r[1], str(r[0])) for r in rows]

    def load(self, sid: int):
        with self._tx() as c:
            rows = c.execute(
                "SELECT role, content, meta FROM messages WHERE session_id = ? ORDER BY ord", (sid,)
            ).fetchall()
        out = []
        for role, content, meta in rows:
            out.append(gr.ChatMessage(role=role, content=content, metadata=json.loads(meta)))
        return out

    def save(self, sid: int, messages) -> None:
        rows = []
        title = None
        for i, m in enumerate(messages):
            d = dataclasses.asdict(m) if dataclasses.is_dataclass(m) else dict(m)
            content = str(d.get("content") or "")
            meta = d.get("metadata") or {}
            if d.get("role") == "user" and title is None:
                title = content.strip().replace("\n", " ")[:28] or None
            rows.append((sid, i, d.get("role") or "assistant", content, json.dumps(meta, ensure_ascii=False)))
        with self._tx() as c:
            if rows:
                c.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
                c.executemany("INSERT INTO messages(session_id, ord, role, content, meta) VALUES (?,?,?,?,?)", rows)
            # updated_at 每存一次都要动。v1.2 起这条 UPDATE 挂在 `WHERE title='新会话'` 上，
            # 于是会话一旦有了标题就再也不刷新时间——侧栏按 updated_at 排序就失真了。
            # 以前只影响刷新页面看到哪条，v1.4 起 _on_load 会把 sid 指向排第一的那条，
            # 下一个问题就落进哪条会话，顺序错了等于问错地方，所以在这里一并修（D6）。
            c.execute(
                "UPDATE sessions SET updated_at = ?, title = CASE WHEN title = '新会话' THEN ? ELSE title END WHERE id = ?",
                (time.time(), title or "新会话", sid),
            )

    def save_memory(self, sid: int, payload: str) -> int:
        """整条覆盖这条会话的记忆（一条会话一行，主键就是 session_id）。返回存了多少字符。"""
        blob = payload or ""
        with self._tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO memory(session_id, payload, updated_at) VALUES (?,?,?)",
                (int(sid), blob, time.time()),
            )
        return len(blob)

    def load_memory(self, sid: int):
        with self._tx() as c:
            row = c.execute("SELECT payload FROM memory WHERE session_id = ?", (int(sid),)).fetchone()
        return row[0] if row else None

    def delete(self, sid: int) -> dict:
        """删一条会话，连带它的消息与记忆。三张表都显式删，不赌 CASCADE。

        CASCADE 确实配好了（:504、:511，且 _tx 每次开连接都 `PRAGMA foreign_keys = ON`，:521），
        但那是**当前这个连接**的属性；哪天换个不走 _tx 的入口忘了这句 pragma，依赖它就会
        留下孤儿行。显式三条 DELETE 顺带还能报出各删了几行，删除是**不可逆**的，
        调用方（_delete_session）要把这个数原样上屏，让人知道自己清掉了多少。
        """
        sid = int(sid)
        with self._tx() as c:
            msgs = c.execute("DELETE FROM messages WHERE session_id = ?", (sid,)).rowcount
            mem = c.execute("DELETE FROM memory WHERE session_id = ?", (sid,)).rowcount
            sess = c.execute("DELETE FROM sessions WHERE id = ?", (sid,)).rowcount
        return {"session": sess, "messages": msgs, "memory": mem}

    def exists(self, sid) -> bool:
        if sid is None:
            return False
        with self._tx() as c:
            return c.execute("SELECT 1 FROM sessions WHERE id = ?", (int(sid),)).fetchone() is not None

    def ensure(self, sid):
        if sid and self.exists(sid):
            return int(sid)
        # 传进来的 id 在库里已经没有行了——只可能是它被删过（另一个标签页／上一次加载留下的
        # gr.State）。这一句必须在：save() 走的是 UPDATE sessions ... WHERE id=?，行没了就是
        # 0 行受影响、不会重建，紧接着 INSERT messages 撞外键抛 IntegrityError，而它落在
        # _respond 的 finally 里（:1572），界面上就是一条没人接住的红色报错。
        # 落到这里等于另开一条，标题也重新从这一题取。
        with self._tx() as c:
            now = time.time()
            cur = c.execute(
                "INSERT INTO sessions(title, created_at, updated_at) VALUES ('新会话', ?, ?)", (now, now)
            )
            return int(cur.lastrowid)


class OpsUI(GradioUI):
    """官方 GradioUI 的流式内核 + 自己拼的界面：侧栏会话 / 顶部状态条 / 深色壳。

    不用 gr.ChatInterface 是因为它的 events 在 __init__ 里就接死了
    （chat_interface.py:265 调 _setup_events），构造完再改 additional_outputs 无效，
    状态条和侧栏塞不进去。这里只换外壳，_stream_response 那层 v1.1 验过的逻辑原样复用。
    """

    # 审批登记表放在**类**上：门守的是进程里那一个 agent 的工具（见 _install_gate 的幂等标记，
    # 第一个实例装好门后别人不再重装），所以队列必须共用。放实例上会出现「A 装的门把单子递给
    # A，屏上看单的是 B」——按钮永远不亮。
    _pending: list[Approval] = []
    _gate_lock = threading.Lock()
    # D7：闸是装在进程唯一的那一个 agent 上的，所以"本轮是不是已经被停止了"也必须是类级的，
    # 放实例上会出现「B 按的停止、A 装的门看不见」。run_seq 每开一轮 +1，
    # _stop 把 _cancelled_before 抬到当前这一轮——入队时一看 <= 就直接按取消结算，不再挂人。
    _run_seq: int = 0
    _cancelled_before: int = 0
    # V8：审批等待的秒数在这里过账——记账的是 worker 线程（_gated_call 醒来那一刻），
    # 取账的是 UI 线程（收到 ActionStep 那一刻）。和 _run_seq 同一个理由：门只装在进程
    # 那一个 agent 上，装门的实例和画卡的实例可能不是同一个，放实例上会把账落在没人看的那边。
    _pending_wait: float = 0.0
    # D8：审批单 id -> 画出来的那张卡。断开（刷新/关页面）那一路要靠它把卡改成终态——
    # 那时 _stream_response 的画卡循环已经死了，没人再去改这张卡，它就永远停在
    # 「🟡 等待你审批」上等着一次不会来的点击（实测见 验收脚本/v1.8/run/v18_d8_baseline.out）。
    # 和 _pending 同一个理由放类上：门装在进程唯一的那个 agent 上，装门的实例和收尾的实例
    # 可能不是同一个。每轮开局在 _stream_response 里清空。
    _ap_cards: dict = {}
    # P1-a：本题发过哪些调用，各发了几次。键 = (工具名, 参数 JSON)。
    # 和 _pending 同一个理由放类上：查重这层装在进程唯一那个 agent 的工具上（见
    # _install_dup_gate 的幂等标记），写它的是 worker 线程、每轮换清它的是 UI 线程。
    # 也同一个理由要在 _gate_lock 里动：三个名字一起改，读的人不会看到「清了计数没清表」。
    _seen_calls: dict = {}
    # 本题挡下了几次重复。DUP_BLOCK_LIMIT 是「警告几次才熔断」的门槛：挡下第 1、2 次各回一句
    # 「换参数或交答案」，第 3 次（超过 2）就 interrupt 收尾——再给机会就是让它继续绕。
    _dup_blocked: int = 0
    # 熔断一旦按下就保持到本轮结束：之后所有重复都按「已熔断」回，不再给第二张警告；
    # _respond 也靠它把这一档和「用户按了 ■」分开写。
    _dup_tripped: bool = False
    # D3：审计行里那一格 session id。放类上（和 _pending / _seen_calls 同一个理由）：
    # 写审计的是 worker 线程、闭包抓住的是**第一个装门的实例**，而提问的 sid 落在
    # 当下那个实例的 self._sid 上——用实例属性去读审计就是拿上一屏的会话号记账。
    # 只在 _stream_response 开局那一把锁里换（那里是 UI 线程、也是唯一会起 worker 的地方）。
    _audit_sid: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hist = History(DB_PATH)
        self._state = "idle"
        self._abandoned = threading.Event()
        # 本题累计的三个数由驱动线程自己累加（口径见 _step_card 末行），不读 agent.memory，
        # 免得 UI 线程和 worker 线程同时碰同一份列表。
        self._run_in = 0
        self._run_out = 0
        self._run_secs = 0.0
        # V8：本题累计里「其中审批等待」那一格，和 _run_secs 同边界（见 _step_card 末行）。
        self._run_wait = 0.0
        # V7：侧栏高亮跟着它走，不再由点击历史决定（见 _select_session）。
        self._sid: str | None = None
        # 上一次真的推给浏览器的高亮值。只在它和 _sid 不一致时才带 value（见 _radio_update）。
        self._sid_shown: str | None = None
        # V5：会话 id -> 那份记忆。只在进程里，不落库（AgentMemory 没有 (de)serializer，
        # memory.py:214-232），所以重启后旧会话只剩屏幕上的字。见 _bind_memory。
        self._mem: dict[int, AgentMemory] = {}
        self._mem_sid: int | None = None
        # P0-4：本轮计划面板上要显示的那一份（(计划原文, 审批读数)）。写它的只有
        # _stream_response，读的只有 _respond，两个都在 UI 线程，所以放实例上就够，
        # 不用像 _pending 那样上类（那边是 worker 线程写、UI 线程读）。
        self._plan_shown: tuple | None = None
        # 删除的「第二次确认」：待删会话的 id（字符串，和 _sid 同型才好比）。没有它就是
        # 待命状态，键面写「🗑 删除」。删除不可逆（连带 messages + memory 两张表），
        # 所以一次点击不删东西，只把这一条武装起来（见 _delete_session）。
        self._armed_del: str | None = None
        # A1＋A2：外部工具在这一刻进这台机器——**必须在装审批门之前**。顺序反过来就会出现
        # 一只挂上了却没门禁的 MCP 工具（_install_gate 只遍历它当时看到的名单）。
        # 挂在这条生命周期而不是 my_agent 的模块层，理由见 my_mcp 文件头：my_agent 是被
        # 离线脚本 import 用的，模块层连接等于「谁 import 一下起两个子进程」且没人收。
        self._mcp = my_mcp.attach(self.agent)
        self._install_gate()
        # P1-a：查重这层必须在审批那层**之后**装，它才套在最外面（理由见 _install_dup_gate）。
        self._install_dup_gate()
        self._install_plan_gate()

    # ---- P0-2：审批门 ---------------------------------------------------------------
    def _gate_names(self) -> tuple:
        """这一次要装审批门的工具名：本地写路径那两只 ＋ 当前这把桥挂上的每一只外部工具。

        为什么不并进 GATED_TOOLS 那个常量：MCP 工具是运行时才知道挂没挂上（server 起不来就是空的），
        而 GATED_TOOLS 是**源码里的事实**——把运行时结果写回常量会让下一次构造读到上一轮的名单。
        现拼的代价是零：只在这一步用。
        """
        out = list(GATED_TOOLS)
        for n in self._mcp.gated:
            if n not in out:
                out.append(n)
        return tuple(out)

    def _install_gate(self) -> None:
        """给写路径工具 + 挂上来的外部工具各套一层审批。

        套法是在**实例**上覆盖 forward：BaseTool.__call__（tools.py:246）最后一行就是
        `self.forward(*args, **kwargs)`，实例属性优先于类上的 staticmethod，所以能拦住。
        用 copy.copy 换新实例，不去改 my_coding_agent 里那批模块级对象——命令行跑法
        （my_coding_agent.py __main__）走的还是同一个 agent.tools，不能被我这条 UI 拖累。
        MCP 工具也是 copy.copy：原件（含 _mcp_server/_mcp_risk）留在 my_mcp 那把桥的记录里，
        副本带着同样的属性进 agent.tools，所以摘除时按名字 pop，不拿副本去比对身份。
        """
        for name in self._gate_names():
            base = self.agent.tools.get(name)
            # 幂等标记：多个 OpsUI 实例（测试里反复建、或将来嵌入别的界面）不能把门套成两层，
            # 套两层就是问两遍、点一次「允许」只解开外面那层，里面那条线程永远挂着。
            if base is None or getattr(base, "_opsui_gated", False):
                continue
            wrapped_tool = copy.copy(base)
            original = base.forward
            # 来源在**装门这一刻**从原件上抄进闭包，不在调用时回查 agent.tools：
            # 那一格字典 detach 时会 pop，回查就是把审批卡的文案挂在别的线程的手上。
            source = getattr(base, "_mcp_server", None)
            risk = getattr(base, "_mcp_risk", None)

            def gated(*a, _name=name, _orig=original, _self=self, _src=source, _risk=risk, **kw):
                return _self._gated_call(_name, _orig, a, kw, _src, _risk)

            gated.__signature__ = inspect.signature(original)
            wrapped_tool.forward = gated
            wrapped_tool._opsui_gated = True
            self.agent.tools[name] = wrapped_tool

    def _gated_call(self, name: str, original, args: tuple, kwargs: dict,
                    source: str | None = None, risk: str | None = None) -> str:
        bound = self._bind_args(original, args, kwargs)
        ap = Approval(name, bound, source=source, risk=risk)
        # D7：入队和"本轮已被停止"必须在同一个临界区里判。分开写就有窗口——先查后入队的话，
        # 停止正好落在中间，_stop 那次 _settle_all 看不到单子（实测 0.2s 那一下），
        # 卡片画出来却没人结算，界面死停在「等待审批」（挂了 142.4s，直到手动补 ✖）。
        # 现在的顺序只有两种可能：闸先拿到锁 → 单子已入队，随后 _stop 的 _settle_all 一定看得见；
        # _stop 先拿到锁 → 这里入队时立刻自己判成 cancelled，压根不等人点。
        with self._gate_lock:
            self._pending.append(ap)
            if OpsUI._run_seq <= OpsUI._cancelled_before:
                ap.decide("cancelled")
        decision = ap.wait()  # 只阻塞这条 worker 线程，界面照旧每 0.25 秒刷一次
        # D3：把这一单的结局补进**外层查重**开的那条审计记录（current() 就是它，同一条线程）。
        # 写在 wait() 之后、过账之前：denied/cancelled/timeout 也要留痕——「有人拒绝过」
        # 恰恰是这份审计最该记住的一行。
        my_audit.annotate(decision=decision, wait_s=round(ap.waited, 3))
        # V8：这一格等待不并进「步骤耗时」的定义，而是单独记账，由下一个到达的 ActionStep
        # 领走、在卡片和状态条里单列出来（口径见 _step_card / _stats）。
        with self._gate_lock:
            if ap.waited >= APPROVAL_WAIT_MIN:
                OpsUI._pending_wait += ap.waited
        if decision == "allowed":
            return original(*args, **kwargs)
        return DENIED_OBSERVATION.get(decision, DENIED_OBSERVATION["denied"])

    @staticmethod
    def _bind_args(original, args: tuple, kwargs: dict) -> dict:
        """把这次调用的实参按 forward 的签名归成 {参数名: 值}。

        审批卡（P0-2）和查重指纹（P1-a）要的是同一份东西，所以只写一次。
        非 JSON 的值（客户端传进来的嵌套结构、Path 之类）统一过 make_json_serializable。
        签名对不上（工具被人塞了奇怪的实参）就退化成按位置记，宁可得保守也不要挡不住。
        """
        try:
            bound = dict(inspect.signature(original).bind_partial(*args, **kwargs).arguments)
        except (TypeError, ValueError):
            bound = {"args": list(args), "kwargs": kwargs}
        return make_json_serializable(bound)

    # ---- P1-a：重复调用检测与熔断 -------------------------------------------------------
    def _install_dup_gate(self) -> None:
        """给**每一只**工具（final_answer 除外）套一层「本题内同名同参第二次不再执行」。

        必须在 `_install_gate()` 之后装：这里 copy.copy 到的那只，它的 forward 已经是审批层
        那个 gated 闭包，所以套完的判断顺序是「先查重，没重复才开审批卡」。反着装就会出现
        一张卡点「✔ 允许」、结果 observation 是「重复调用未执行」——让人批了一件根本没跑的事。

        为什么套全部工具而不是只套审批那两只：实测那批重复调用（同名同参 list_dir({}) 一个
        样本里发三遍）全在只读侧，只读侧本来不弹审批，套在 GATED_TOOLS 上等于一层没装上。

        和审批层同一个装法：只覆盖**实例**上的 forward，且用 copy.copy 换新对象，
        不改 my_coding_agent 里那批模块级工具——命令行 `python my_coding_agent.py` 那条跑法
        不经过 UI，也就不会被这层拦。
        """
        for name, base in list(self.agent.tools.items()):
            if name == "final_answer":
                continue
            # 幂等标记：和审批层同一个理由，两个 OpsUI 实例不能把查重套成两层——
            # 套两层就是同一次重复被记两次账，第 2 次重复就触发了熔断。
            if getattr(base, "_opsui_dedup", False):
                continue
            wrapped_tool = copy.copy(base)
            original = base.forward
            # D3：审计要写「这只手是谁的」，所以在装门这一刻把 provenance 抄进闭包
            # （和 _install_gate 同一套理由：调用时不回查 agent.tools）。
            src = "mcp:" + getattr(base, "_mcp_server", "") if getattr(base, "_mcp_server", None) else "local"
            risk = getattr(base, "_mcp_risk", None)

            def dup(*a, _name=name, _orig=original, _self=self, _src=src, _risk=risk, **kw):
                return _self._dup_call(_name, _orig, a, kw, _src, _risk)

            dup.__signature__ = inspect.signature(original)
            wrapped_tool.forward = dup
            wrapped_tool._opsui_dedup = True
            self.agent.tools[name] = wrapped_tool
        self._install_dup_stop()

    def _dup_call(self, name: str, original, args: tuple, kwargs: dict,
                  src: str = "local", risk: str | None = None) -> str:
        bound = self._bind_args(original, args, kwargs)
        key = (name, json.dumps(bound, sort_keys=True, ensure_ascii=False))
        with self._gate_lock:
            n = OpsUI._seen_calls.get(key, 0) + 1
            OpsUI._seen_calls[key] = n
            if n > 1:
                OpsUI._dup_blocked += 1
                if OpsUI._dup_blocked > DUP_BLOCK_LIMIT:
                    OpsUI._dup_tripped = True
            blocked, tripped = OpsUI._dup_blocked, OpsUI._dup_tripped
        # D3：审计开在这一层而不是审批层——只读那五只手不过门，它们占的调用就一条不记了；
        # 而这一层看得见**每一次**发出去的调用，包括被自己挡掉的那两次。
        rec = my_audit.begin(tool=name, src=src, risk=risk, n=n, args=bound,
                            sid=OpsUI._audit_sid, run=OpsUI._run_seq,
                            step=getattr(self.agent, "step_number", 0))
        if n == 1:
            try:
                out = original(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 —— 记完必须原样抛出去，改的是记账不是行为
                my_audit.end(rec, "raised", exc=type(exc).__name__)
                raise
            my_audit.end(rec, "ran")
            return out
        if tripped:
            # 两件事一起做，各管一半：
            #  · interrupt() 是框架自己的开关（agents.py:546-547 在循环体最上面判）；
            #  · 真正当场收掉靠 _install_dup_stop 那层包装——只靠 interrupt 有个洞，见那里。
            # 这句观察值仍然要交回去：它进这一步的 memory（agents.py:600-604 那个 finally），
            # 所以卡片上看得见「为什么这题没了」，下一问的记忆里也在。但**本轮的模型读不到它**
            # ——dup_stop 就在这一步 yield 之后把题收了，不会再有下一次 generate。
            self.agent.interrupt()
            my_audit.end(rec, "dup-fused", blocked=blocked, limit=DUP_BLOCK_LIMIT)
            return DUP_FUSE_OBSERVATION.format(n=n, blocked=blocked, limit=DUP_BLOCK_LIMIT)
        my_audit.end(rec, "dup-blocked", blocked=blocked)
        return DUP_OBSERVATION.format(n=n)

    def _install_dup_stop(self) -> None:
        """熔断之后就在**那一步刚结束**的那一刻收，绝不进下一步。

        为什么 `interrupt()` 不够：agents.py:545-547 那句判 interrupt_switch 写在 while 循环体
        **最上面**，而 `step_number += 1` 在循环体自己的 finally 里（agents.py:604）。于是熔断
        正好落在最后一步（max_steps=8 的第 8 步）时，回到循环先判 `9 <= 8` 为假直接退出，
        那一句压根没机会跑——流程改走 agents.py:607 的 `_handle_max_steps_reached`：**多打一次
        模型**，状态条还会写成「步数用满」，把 ⛔ 那一档吞掉。
        多打这一次既测了次数也测了价：零成本回放里对照格模型被取走 9 条、产品格 8 条
        （验收脚本/v1.8/run/v18_p1a_replay.out 的 A1/A2）；那一次补打的单步花费在 21:06 你自己
        那份日志里有实测——run A 的 `[Step 8] in 23,667 / out 126` 到 `[Step 9] in 25,227 / out 429`
        之间多出的 **in 1,560 / out 303、7.16 秒**（监控器是累计口径，单步=相邻两行相减；单样本，
        只当量级看）。21:06 那份 transcript 的第三次重复恰好就在第 8 步，所以这个洞不是假想。

        装法和计划门同一套（见 _install_plan_gate）：覆盖**实例**上的 `_run_stream`，
        先 yield 再判，所以那一步的卡片照旧画得出来、观察值照旧进记忆。

        但「先 yield」要挑对那一次 yield。一步之内框架吐三类事件（ToolCall、ToolOutput、
        最后才是 ActionStep，见 agents.py:578-580 与 603），在 ToolOutput 后面就抛会把
        这一步留在半截——零成本回放（验收脚本/v1.8/v18_p1a_replay.py）实测过那一版：
        第 8 步的卡片压根没画出来、memory 里那一步 observations 是空的，熔断那句话只活在
        收尾气泡里，屏幕上看不见「它是在哪一步、因为哪一次调用被拦的」。所以判据加上
        isinstance(ev, ActionStep)：那一步齐了才收。
        """
        if getattr(self.agent, "_opsui_dup_stop", False):
            return
        inner = self.agent._run_stream

        def stopped(*a, **kw):
            for ev in inner(*a, **kw):
                yield ev
                if OpsUI._dup_tripped and isinstance(ev, ActionStep):
                    raise AgentError(
                        f"重复调用熔断：本题累计挡下 {OpsUI._dup_blocked} 次同样的调用，"
                        f"超过上限 {DUP_BLOCK_LIMIT}，这一题到此结束。要接着做请重新提问。",
                        self.agent.logger,
                    )

        self.agent._run_stream = stopped
        self.agent._opsui_dup_stop = True

    # ---- P0-4：计划审批门 -------------------------------------------------------------
    def _install_plan_gate(self) -> None:
        """把计划卡在「已经生成、agent 还没开工」那一刻，等人批准。

        装法：在**实例**上覆盖 `_run_stream`。这条路是唯一的——`run(stream=True)` 直接
        `return self._run_stream(task=..., max_steps=..., images=...)`（agents.py:496），
        实例属性优先于类上的方法，所以拦得住，而且一行 src/smolagents/ 都不改。
        包装里只多一句 `_plan_gate`，其余原样转发，连 ChatMessageStreamDelta 也照转
        ——所以计划正文照样在聊天框里一个字一个字流出来，面板是流完之后那份的常驻视图。

        为什么卡在 yield **之后**：agents.py:556-562 是
        `for element in self._generate_planning_step(...): yield element` 然后才
        `_finalize_step(planning_step)` + `memory.steps.append(planning_step)`。
        内层生成器交出 PlanningStep 那一刻就停在 yield 上，那两句还没跑——这是全流程里
        最后一个「计划已经有了、agent 还没动手」的缝。先把它 yield 出去（界面才画得出、
        也才有东西可批），再在这里等人点。
        """
        if getattr(self.agent, "_opsui_plan_gated", False):
            return
        inner = self.agent._run_stream

        def gated(*a, **kw):
            for ev in inner(*a, **kw):
                yield ev
                if isinstance(ev, PlanningStep):
                    self._plan_gate(ev)

        self.agent._run_stream = gated
        self.agent._opsui_plan_gated = True

    def _plan_gate(self, planning_step) -> None:
        """这份计划批不批。阻塞的是 worker 线程（_worker 里那条 for），界面照旧每 0.25 秒刷。

        和 _gated_call 共用一套东西：D7 那个临界区（入队和「本轮已被停止」一起判）、
        V8 的等待过账、decision 的五个取值、以及同一对 ✔/✖ 按钮。不同的只有落场：
        工具被拒本题还在跑，计划被否整题就没开工——所以这里抛异常出去，见 PlanDeniedError。
        """
        ap = Approval(PLAN_APPROVAL_NAME, {"plan": planning_step.plan}, kind="plan")
        with self._gate_lock:
            self._pending.append(ap)
            if OpsUI._run_seq <= OpsUI._cancelled_before:
                ap.decide("cancelled")
        decision = ap.wait()
        with self._gate_lock:
            if ap.waited >= APPROVAL_WAIT_MIN:
                OpsUI._pending_wait += ap.waited
        if decision == "allowed":
            return
        if decision == "cancelled":
            # 停止／换题正好落在计划上：这一档交给 _respond 的 stopped 去说（「已停止」），
            # 消息串和框架自己在步边界抛的那句一致（agents.py:545-547），两条路对得上。
            raise AgentError("Agent interrupted.", self.agent.logger)
        raise PlanDeniedError(
            f"{DECISION_LABEL[decision]}：这一题没有开工，一个工具都没跑。", self.agent.logger
        )

    def _pending_snapshot(self) -> list[Approval]:
        with self._gate_lock:
            return list(self._pending)

    def _unanswered(self) -> list[Approval]:
        return [a for a in self._pending_snapshot() if a.decision == "pending"]

    def _decide(self, decision: str):
        """■ 允许 / 拒绝：只改 decision 并置事件，不碰消息流——消息归那条生成器独占。"""
        un = self._unanswered()
        if un:
            un[0].decide(decision)  # 一次只处理最早的一张，多条待批时按顺序来
        n = len(self._unanswered())
        return (
            self._status_html("awaiting" if n else self._state),
            gr.update(visible=bool(n)),
            gr.update(visible=bool(n)),
        )

    def _settle_all(self, decision: str) -> None:
        """停止 / 换题时把没人管的审批结算掉，否则 worker 线程会一直挂在 wait() 上。"""
        for ap in self._pending_snapshot():
            ap.decide(decision)

    def _mark_interrupted(self, mem, last):
        """D8：断开（刷新页面 / 关页面）这一路的收尾，返回要落库的那一串消息。

        基线实测纠正了工单原文：生成器被关掉时 `_respond` 的 finally **是跑到的**，
        半截内容照落库（B1 三次实测 messages=3、memory 350/352 B 可复现），
        所以这里不补「落库」，补的是落下去之后没人在意的三件账：
          ① 那张审批卡冻在「🟡 等待你审批（已挂起 Ns，超过 600 秒自动拒绝）」——画卡的
             循环已经死了，再没人把它改成终态，于是它在历史里永远等一次不会来的点击；
          ② 没有任何地方写着这题被掐断过，事后重开看着像正常答完；
          ③ 这一笔审批等待（实测 5.231 s）按 V8 的规矩由**下一个** ActionStep 领走，
             断开后再没有下一步，账就漂在 `_pending_wait` 里，换题开局被清零（:837-839），
             于是「本题审批」这一格在这一题上永远读不出来。
        """
        aps = [ap for ap in self._pending_snapshot() if ap.id in OpsUI._ap_cards]
        for ap in aps:
            card = OpsUI._ap_cards[ap.id]
            new = self._approval_card(ap, time.time() - ap.created, shown="cancelled_by_reload")
            # 原地改，不按下标替换（同 :931 那条踩过的理由）。
            card.content = new.content
            card.metadata = new.metadata
        orphan = sum(ap.waited for ap in aps if ap.waited >= APPROVAL_WAIT_MIN)
        if orphan and mem is not None:
            # 挂回最后一个 ActionStep：它的 timing.duration 本来就把这段等待算在内
            # （实测 6.2566s 内含审批 5.231s），所以是「补一格的归属」，不是把账做大。
            # 这一步已经有主了（被下一个 ActionStep 领走过）就不动，绝不重复计。
            with self._gate_lock:
                for st in reversed(list(mem.steps)):
                    if isinstance(st, ActionStep):
                        if not (getattr(st, "_opsui_wait", 0.0) or 0.0):
                            st._opsui_wait = orphan
                        break
        parts = ["⏹ **本题已中断**：页面被刷新或关闭，这一题后面的步骤没有跑。"]
        if aps:
            # P0-4：断开那一路现在也可能停在**计划**审批上，那句话不能写成「对应工具」——
            # 计划被掐断时整题还没开工，一个工具都还没轮到。工具那半句保持逐字不动，
            # 只有队列里真有单子时才多说一行（slice ② 的 B1 实测断言不受影响）。
            plans = [ap for ap in aps if ap.kind == "plan"]
            tools = [ap for ap in aps if ap.kind != "plan"]
            if tools:
                parts.append(f"这一题有 **{len(tools)} 项审批没等来点击**，已随中断取消，对应工具一行代码都没执行。")
            if plans:
                parts.append(
                    f"这一题停在 **{len(plans)} 份计划**的批准这一步就被中断"
                    "——计划没批准，整题没开工，一个工具都没跑。"
                )
        if orphan:
            parts.append(f"其中干等 **{orphan:.1f}s** 在等人点审批。")
        parts.append("想接着做，重新提问即可（这一题的半截内容已经在上面）。")
        return last + [
            gr.ChatMessage(
                role="assistant",
                content="\n\n".join(parts),
                metadata={"title": f"⏹ {STATE_LABEL['interrupted']}" + (f" · 审批空等 {orphan:.1f}s" if orphan else ""),
                          "status": "done"},
            )
        ]

    def _approval_card(self, ap: Approval, waited: float, shown: str | None = None) -> gr.ChatMessage:
        state = ap.decision
        # D8：`shown` 只换**界面上的措辞**，不换 decision 本身。断开这一路结算出来的
        # decision 还是 cancelled（worker 收到的观察值、下一步卡的判定都不动），但话要说对：
        # 「随停止取消」在这一路是假的——没人按过停止，是页面被刷新/关掉了。
        # v1.3 就因为把「停止」和「拒绝」写成同一句被纠正过一次（见 :708 附近注释）。
        key = shown or state
        dot = DECISION_DOT.get(key, DECISION_DOT["pending"])
        label = DECISION_LABEL.get(key, state)
        n = len(self._unanswered())
        title = (
            f"{dot} 待批 · {ap.tool} · {label}"
            + (f" · 共 {n} 项待批" if state == "pending" and n > 1 else "")
            # V8：结算之后标题就固定了（drawn 的键不再变），所以这里用 decide() 那一刻记下的
            # 精确等待秒数，不用现场 time.time()-created——后者会把「工具又跑了多久」也算进来。
            + ("" if state == "pending" or ap.waited < APPROVAL_WAIT_MIN else f" · 等了 {ap.waited:.1f}s")
        )
        if state == "pending":
            hint = (
                f"**🟡 等待你审批**（已挂起 {waited:.0f}s，超过 {int(APPROVAL_TIMEOUT)} 秒自动拒绝）\n"
                "点右侧 **「✔ 允许」** 才真的执行；**「✖ 拒绝」** 则这个工具一行代码都不会跑。"
            )
        else:
            hint = f"**{dot} {label}**" + ("" if state == "allowed" else "——这个工具没有执行，没有任何副作用。")
        if ap.kind == "plan":
            # P0-4：同一张审批卡的两处措辞都要换——批的不是「跑不跑这段代码」，是
            # 「开不开工这一题」。工具那一路拒完题还在跑，计划这一路否掉整题就停了。
            plan = str(ap.args.get("plan") or "")
            if state == "pending":
                hint = (
                    f"**🟡 等待你批准这份计划**（已挂起 {waited:.0f}s，超过 {int(APPROVAL_TIMEOUT)} 秒作废）\n"
                    "点右侧 **「✔ 允许」** agent 才开始动手；**「✖ 拒绝」** 则这一题就地停下、"
                    "一个工具都不跑，这份计划也不进模型的记忆。"
                )
            else:
                hint = f"**{dot} {label}**" + (
                    "——agent 照这份计划开始动手。"
                    if state == "allowed"
                    else "——这一题没有开工，一个工具都没跑，这份计划也没有进模型的记忆。"
                )
            content = (
                f"{hint}\n\n---\n\n"
                f"**计划全文**（{len(plan):,} 字符，和聊天框上方那块面板是同一份）\n\n{plan}"
            )
        else:
            content = (
                f"**工具** `{ap.tool}`\n\n"
                # A2：外部工具要在卡上自报家门——这一只不是 agent 自己的手，是另一个进程。
                # 只读不判：批不批完全看 decision，这里只多给人看一行它的风险档。
                + (
                    f"**来源** 外部 MCP server `{ap.source}`"
                    + (f" · 风险：{ap.risk}" if ap.risk else "")
                    + "\n\n"
                    if ap.source
                    else ""
                )
                + f"**参数**\n{self._fence(self._args_text(ap.args), 'json')}\n\n"
                f"{hint}"
            )
        return gr.ChatMessage(
            role="assistant",
            content=content,
            metadata={"title": title, "status": "pending" if state == "pending" else "done"},
        )

    # ---- P0-4：计划面板 -------------------------------------------------------------
    def _plan_update(self, shown: tuple | None = None):
        """聊天框上方那块常驻面板：本轮那份计划的原文 + 它的审批读数。

        为什么要把计划搬到聊天框外面：带 title 的消息 gradio 一律折成 Accordion，收起时
        正文根本不在 DOM 里（_step_card 开头那条规则，v1.1 就栽过）——而实测这份产出
        有 6,195 字符（run/v18_plan_probe.out 的 B 组），藏在一张收起的卡里等于没上墙。
        卡片继续留在消息流里当**历史**（面板不进库），两处是同一份文本。
        """
        shown = self._plan_shown if shown is None else shown
        if not shown or not shown[0]:
            return gr.update(value="", visible=False)
        text, key, waited = shown
        label = DECISION_LABEL.get(key, key)
        dot = DECISION_DOT.get(key, DECISION_DOT["pending"])
        if key == "pending":
            note = (
                f"{dot} **{label}**"
                + (f"（已挂起 {waited:.0f}s）" if waited else "")
                + "：agent 停在计划上等你。点顶部 **「✔ 允许」** 才开始动手，"
                "**「✖ 拒绝」** 则这一题就地停下、一个工具都不跑。"
            )
        elif key == "allowed":
            note = f"{dot} **{label}**——后面的步骤照这份计划走。"
        else:
            note = f"{dot} **{label}**——这一题没有开工，一个工具都没跑。"
        return gr.update(value=f"**🧭 本轮计划** · {note}\n\n{text}", visible=True)

    @staticmethod
    def _last_plan(steps) -> tuple | None:
        """这条会话记忆里的最后一份计划，用来在刷新／换会话后重画面板。

        「能进 memory 的计划只有批准过的那一份」不是推测：门卡在 `_finalize_step` +
        `memory.steps.append` 之前（agents.py:556-562 的顺序），没批的那份直接被
        PlanDeniedError 截住，永远不会被 append。所以这里的读数固定写 "allowed"。
        """
        for st in reversed(list(steps or [])):
            if isinstance(st, PlanningStep):
                return (st.plan, "allowed", None)
        return None

    # ---- V4：渲染用的两个小工具 -----------------------------------------------------
    @staticmethod
    def _fence(text: str, lang: str = "") -> str:
        marker = "```"
        while marker in text:  # 正文里带反引号时把栅栏加长，避免提前闭合
            marker += "`"
        return f"{marker}{lang}\n{text}\n{marker}"

    @staticmethod
    def _args_text(args, limit: int = 1200) -> str:
        d = args if isinstance(args, dict) else {"value": args}
        slim = {}
        for k, v in d.items():
            if isinstance(v, str) and len(v) > limit:
                slim[k] = v[:limit] + f"…（共 {len(v)} 字，截掉 {len(v) - limit} 字）"
            else:
                slim[k] = v
        try:
            return json.dumps(slim, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(slim)

    def _step_card(self, step) -> gr.ChatMessage | None:
        """一个 step 一张卡：把上游那 5~6 条无差别折叠卡并成一条。

        数字必须写进 metadata.title——带 title 的消息 gradio 会折起来，收起时正文根本不在
        DOM 里，只有标题可见（v1.1 就栽过一次，正文写了半天屏幕上看不见）。
        """
        if isinstance(step, PlanningStep):
            tk = step.token_usage
            secs = step.timing.duration if step.timing else None
            # P0-4：这张卡能画出来就说明计划已经批过了——没批的那份进不了流程
            # （门卡在 memory.append 之前，见 _install_plan_gate），所以标题上「已允许」
            # 不会说谎。字必须和 DECISION_LABEL["allowed"]、和那颗「✔ 允许」按钮同一套，
            # 屏上三个地方说的是同一件事。
            # 以前标题只有「🧭 计划步」四个字：折叠卡的正文不在 DOM 里
            # （见本函数开头那条 gradio 规则），于是这次多花 32.9s、1,188/1,458 token
            # 换来的产出，在屏上就是一个标题。数字和时长得写在标题上才看得见。
            span = f" · {secs:.1f}s" if secs else ""
            toks = f" · in {tk.input_tokens:,}/out {tk.output_tokens:,}" if tk else ""
            return gr.ChatMessage(
                role="assistant",
                content=f"**计划**\n{step.plan}",
                metadata={"title": f"🧭 计划 · {DECISION_LABEL['allowed']}{span}{toks}", "status": "done"},
            )
        if not isinstance(step, ActionStep):
            return None
        calls = list(getattr(step, "tool_calls", None) or [])
        names = "、".join(dict.fromkeys(c.name for c in calls)) if calls else "无工具调用"
        obs = (step.observations or "").strip()
        # 三种「没执行」分开标：拒绝 / 停止 / 超时，卡片和审批卡的说法要对得上
        # （一开始都写成「已拒绝」，实测看着像我把你的停止当成了否决）。
        withheld = next((DENIED_VERDICT[k] for k, v in DENIED_OBSERVATION.items() if v.strip() in obs), None)
        # P1-a：观察值里有几句「重复调用未执行」就挡了几次。为什么要除以 len(calls)：
        # 一步里可以并行发好几个调用（agents.py:1043-1046 是把每只的观察值用换行拼起来的），
        # 只挡其中一个是常事，写成整步「未执行」就是假账——所以把 挡下/总数 直接摊在标题上。
        dup_hits = obs.count(DUP_MARK)
        if step.error is not None:
            dot, verdict = "🔴", "报错"
        elif dup_hits:
            dot = "⛔" if DUP_FUSE_MARK in obs else "⚪"
            verdict = f"{'重复熔断' if dot == '⛔' else '重复未执行'} {dup_hits}/{len(calls) or 1}"
        elif withheld:
            dot, verdict = "⚪", withheld
        else:
            dot, verdict = "🟢", "成功"
        tk = step.token_usage
        secs = step.timing.duration if step.timing else None
        # V8：这一格里有多少是「在等人点审批」。secs 仍是框架量到的整步时长（口径不变），
        # 单列出来的这一格只加不改，读的人第一次就能把「真执行 1s」和「干等 271s」分开看。
        wait = getattr(step, "_opsui_wait", 0.0) or 0.0
        span = f"{secs:.1f}s" + (f"（含审批 {wait:.1f}s）" if wait else "") if secs else ""
        foot = f"本步 {span} · in {tk.input_tokens:,} / out {tk.output_tokens:,}" if (secs and tk) else "本步 计时或 token 未记录"
        title = (
            f"🛠 第 {step.step_number} 步 · {names} · {dot} {verdict}"
            + (f" · {secs:.1f}s" if secs else "")
            + (f" · 审批 {wait:.1f}s" if wait else "")
            + (f" · in {tk.input_tokens:,}/out {tk.output_tokens:,}" if tk else "")
        )
        parts = []
        thought = _clean_model_output(getattr(step, "model_output", "") or "")
        if thought:
            parts.append("**模型思考**\n" + self._fence(thought[:800]))
        for c in calls:
            parts.append(f"**调用** `{c.name}`\n" + self._fence(self._args_text(c.arguments), "json"))
        if obs:
            parts.append("**结果**\n" + self._fence(obs[:4000]))
        if step.error is not None:
            parts.append(f"**报错** {type(step.error).__name__}: {step.error}")
        parts.append(
            f"{foot}\n本题累计（本次提问内）：in {self._run_in:,} / out {self._run_out:,} token · {self._run_secs:.1f}s"
            + (f"（含审批 {self._run_wait:.1f}s）" if self._run_wait else "")
        )
        return gr.ChatMessage(
            role="assistant", content="\n\n".join(parts), metadata={"title": title, "status": "done"}
        )

    # ---- 口径：一份数字，两处显示（聊天气泡里的折叠卡 + 顶部常驻条）-----------------
    def _stats(self, steps=None) -> dict:
        # V9：steps 给的是「只读某一条会话的步骤」（见 _session_steps），不传就是现在这套——
        # 报 agent.memory 那份（= 当前绑定的会话）。
        steps = self.agent.memory.steps if steps is None else steps
        # 本题边界 = 最后一个 TaskStep 之后；monitor 是进程级、跨题不清零，两个口径分开报
        start = max((i for i, s in enumerate(steps) if isinstance(s, TaskStep)), default=0)
        cur = [s for s in steps[start:] if isinstance(s, ActionStep)]
        used = [s.token_usage for s in cur if s.token_usage]
        mon = self.agent.monitor.get_total_token_counts()
        last = cur[-1] if cur else None
        return {
            "model": getattr(self.agent.model, "model_id", "?"),
            "step_no": last.step_number if last else 0,
            "max_steps": self.agent.max_steps,
            "task_in": sum(t.input_tokens for t in used),
            "task_out": sum(t.output_tokens for t in used),
            "task_secs": sum(s.timing.duration for s in cur if s.timing.duration),
            # V8：本题里有多少秒是在等审批。活进程里它挂在 step 对象上（_stream_response
            # 领账那一刻写的）；V9 起这一格跟着记忆进库（payload 里的 wait），回灌时挂回同一个
            # 属性，所以重启后读得出来。v1 的老 payload 没这一格，读作 0、那一格也就不出现。
            "task_wait": sum(getattr(s, "_opsui_wait", 0.0) or 0.0 for s in cur),
            "step_secs": (last.timing.duration or 0.0) if last and last.timing else 0.0,
            "step_in": last.token_usage.input_tokens if last and last.token_usage else 0,
            "step_out": last.token_usage.output_tokens if last and last.token_usage else 0,
            "step_error": bool(cur and cur[-1].error),
            # 用满 max_steps 时框架不抛异常：_handle_max_steps_reached(agents.py:630 附近)
            # 自己补一步「给个结论」，把这一步的 error 标成 AgentMaxStepsError，step_number 到 9。
            # 所以只能从 memory 里认这条错误，别指望 except 接得住。
            "maxed": any(isinstance(getattr(s, "error", None), AgentMaxStepsError) for s in cur),
            "mon_in": mon.input_tokens,
            "mon_out": mon.output_tokens,
        }

    def _mcp_pill(self) -> str:
        """状态条上那一格 MCP 读数：正常时「time×2、fetch×1」，一个没连上时如实讲为什么。

        不另加「N server / M 工具」的汇总——describe() 里每只 server 后面那个乘号就是工具数，
        再报一遍是重复。截到 64 字符是因为 skipped 里装的是异常原文（server 起不来时能到几百字符），
        一行状态条放不下；被截掉的那份全文在 bridge.describe() 里，审计行也带着它。
        """
        d = self._mcp.describe()
        return d if len(d) <= 64 else d[:64] + "…"

    def _status_html(self, state: str, steps=None) -> str:
        s = self._stats(steps)
        un = self._unanswered()
        pills = [
            ("模型", s["model"]),
            # A2：外部工具这一格常驻——挂了谁都写在屏上，一个没挂也要说「未配置 server」。
            # 这行不是装饰：审批卡上那句「来源 外部 MCP server」只有在点开那张卡时才看得见，
            # 而「这台机器现在连着几个外部进程」应该在提问之前就知道。
            ("MCP", self._mcp_pill()),
            ("步数", f"{s['step_no']}/{s['max_steps']}"),
            ("本题 token", f"in {s['task_in']:,} / out {s['task_out']:,}"),
            ("本题耗时", f"{s['task_secs']:.1f}s"),
        ]
        # V8：平时不占一格，只有本题真的等人批过才出现（多数提问一个审批都没有）。
        if s["task_wait"]:
            pills.append(("本题审批", f"{s['task_wait']:.1f}s"))
        pills.append(("进程 token", f"in {s['mon_in']:,} / out {s['mon_out']:,}"))
        if un:
            pills.append(("待批", "、".join(dict.fromkeys(a.tool for a in un))))
        pills.append(("状态", STATE_LABEL[state]))
        inner = "".join(
            f'<span class="pill{" pill-state" if k == "状态" else ""}{" pill-pending" if k == "待批" else ""}">'
            f"<b>{html.escape(k)}</b><i>{html.escape(str(v))}</i></span>"
            for k, v in pills
        )
        return f'<div id="statusbar" class="st-{state}">{inner}</div>'

    def _flash(self, text: str) -> str:
        """状态条下面那行一次性提示（删除的确认与回执都靠它，不新增状态档）。

        为什么不塞进 STATE_LABEL：那一栏是**会话状态机**，`st-{state}` 那串 class 和
        _respond 收尾的账都读它；「已删除」不是一个状态，是上一条操作的回执，
        混进去会让「状态」那一格不再等于 _state。
        """
        return f'<div id="flash">{html.escape(text)}</div>'

    # ---- 驱动：agent 跑在 worker 线程，界面每 0.25 秒取一次队列 -------------------
    def _worker(self, task: str, files, q: queue.Queue) -> None:
        """在别的线程里消费 agent.run(stream=True)。

        为什么非得换线程：审批是**阻塞**的，而 gradio 是把这条生成器同步往前推的——
        工具卡在 forward 里等点按钮，那条生成器就永远 yield 不出审批卡，界面也就永远
        不会出现「允许/拒绝」，死锁。换成线程 + 队列后，阻塞的是 worker，界面照刷。
        """
        inner = self.agent.run(task, images=files, stream=True, reset=self.reset_agent_memory)
        try:
            for ev in inner:
                q.put(("ev", ev))
                if self._abandoned.is_set():
                    break
        except BaseException as exc:  # 线程里抛出去没人接，塞回队列由 UI 侧原样重放
            q.put(("err", exc))
        finally:
            # 内层生成器只能在起它的那条线程里关：上游 _run_stream 的 finally 里还有一次
            # yield（agents.py:599-602），关的时候会顶回来一条 RuntimeError，自己接住，
            # 别让它变成 stderr 上那条 "generator ignored GeneratorExit"。
            try:
                inner.close()
            except RuntimeError:
                pass
            q.put(("done", None))

    def _stream_response(self, message, history):  # noqa: ARG002
        task, files = self._process_message(message)
        # 换题开局：上一题遗留的未批项先结算再摘除。摘除只由 UI 线程做，这里就是 UI 线程。
        self._settle_all("cancelled")
        with self._gate_lock:
            self._pending.clear()
            # D8：登记表跟着换题一起清。留着上一题的卡，断开收尾时就会去改一张
            # 已经不在这一串消息里的对象——不报错，但那一格的账就悄悄记错题了。
            OpsUI._ap_cards.clear()
            # V8：换题开局把上一题没被领走的等待清零。会留下账只有两种情况——停止落在
            # 待批上（那一步压根没生成 ActionStep），或 worker 还挂着；都不该记到新题头上。
            OpsUI._pending_wait = 0.0
            # P1-a：查重登记表跟着换题一起清。跨题留着就是把上一题查过的路径当成本题的重复
            # 直接挡掉——用户新问一句「列一下 smolagents/」，那是一次真需要执行的调用。
            OpsUI._seen_calls.clear()
            OpsUI._dup_blocked = 0
            OpsUI._dup_tripped = False
            # D3：审计行的会话号在这里定格——这是唯一一处「UI 线程已经知道本题 sid、
            # worker 线程还没起」的地方。self._sid 由 _respond 在调进这里之前写好。
            OpsUI._audit_sid = self._sid
        self._abandoned.clear()
        self._run_in = self._run_out = 0
        self._run_secs = 0.0
        self._run_wait = 0.0
        # P0-4：面板也是每题一开的东西——上一题的计划不能留到这一题的屏上。
        self._plan_shown = None
        # D7：先领这一轮的号，再起线程——号没领上就开工的话，闸读到的还是上一轮的号。
        with self._gate_lock:
            OpsUI._run_seq += 1

        q: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, args=(task, files, q), name="agent-run", daemon=True).start()

        msgs: list[gr.ChatMessage] = []
        deltas: list[ChatMessageStreamDelta] = []
        stream_idx: int | None = None
        cards: dict[str, gr.ChatMessage] = {}   # 审批单 id -> 那张卡（存对象，不存下标）
        drawn: dict[str, tuple] = {}            # 审批单 id -> 已画出来的 (decision, 挂起秒数)
        err: BaseException | None = None

        try:
            while True:
                changed, stop = False, False
                try:
                    kind, payload = q.get(timeout=0.25)
                except queue.Empty:
                    kind, payload = "poll", None
                while True:
                    if kind == "ev":
                        if isinstance(payload, ChatMessageStreamDelta):
                            deltas.append(payload)
                            text = agglomerate_stream_deltas(deltas).render_as_markdown()
                            # 模型爱吐 <end_code> 这类标签，不转义会被当 HTML 吃掉一段。
                            text = text.replace("<", r"\<").replace(">", r"\>")
                            msg = gr.ChatMessage(role="assistant", content=text)
                            if stream_idx is None:
                                stream_idx = len(msgs)
                                msgs.append(msg)
                            else:
                                msgs[stream_idx] = msg
                            changed = True
                        elif isinstance(payload, ActionStep | PlanningStep | FinalAnswerStep):
                            if stream_idx is not None:
                                msgs.pop(stream_idx)  # 思考已经并进卡片正文，不留两份
                                stream_idx = None
                            deltas = []
                            if isinstance(payload, FinalAnswerStep):
                                for m in _process_final_answer_step(payload):
                                    msgs.append(gr.ChatMessage(role=m.role, content=m.content, metadata=m.metadata))
                            else:
                                if isinstance(payload, PlanningStep):
                                    # P0-4：面板先上手，别等门里那张单子排进队列（同一毫秒级
                                    # 的事，但少一帧就是屏上闪一下空白）。读数随后由审批循环改成
                                    # 实际 decision，pending 只是这一刻的实话。
                                    self._plan_shown = (payload.plan, "pending", 0.0)
                                if isinstance(payload, ActionStep):
                                    if payload.token_usage:
                                        self._run_in += payload.token_usage.input_tokens
                                        self._run_out += payload.token_usage.output_tokens
                                    if payload.timing and payload.timing.duration:
                                        self._run_secs += payload.timing.duration
                                    # V8：把门那边攒下的等待领到这一步上（一次取干，不留在账上
                                    # 漂到下一步去）。写的是 step 对象的一个私有属性；V9 起
                                    # encode_memory 单独认它，所以这一格跟着记忆进库、重启后读得出。
                                    with self._gate_lock:
                                        waited, OpsUI._pending_wait = OpsUI._pending_wait, 0.0
                                    if waited:
                                        payload._opsui_wait = waited
                                        self._run_wait += waited
                                card = self._step_card(payload)
                                if card is not None:
                                    msgs.append(card)
                            changed = True
                        # 其余事件（ToolCall / ToolOutput）不单独渲染：审批状态由门那边出卡。
                    elif kind == "err":
                        err = payload
                        stop = True
                        break
                    elif kind == "done":
                        stop = True
                        break
                    try:
                        kind, payload = q.get_nowait()
                    except queue.Empty:
                        break

                for ap in self._pending_snapshot():
                    waited = time.time() - ap.created
                    key = (ap.decision, int(waited) if ap.decision == "pending" else -1)
                    if ap.kind == "plan":
                        # P0-4：面板的读数跟着这张单子走。摘单之后循环里就再也看不到它了，
                        # 所以这里是**粘住**的最后一帧——摘单前那一帧的 decision 已是终态
                        # （下面 if ap.decision != "pending" 那句才摘），面板留在最终读数上。
                        self._plan_shown = (
                            str(ap.args.get("plan") or ""),
                            ap.decision,
                            None if ap.decision == "pending" else ap.waited,
                        )
                    if ap.id not in cards:
                        # 也可能是「点得太快，卡片第一次落笔时 decision 已经是 allowed」：
                        # 所以出卡之后要走同一套收尾判定，不能只在更新分支里摘单
                        # （踩过：这种卡画出来了但单子永远留在队列里，越积越多）。
                        cards[ap.id] = self._approval_card(ap, waited)
                        # D8：同一份引用登记一份，断开收尾时靠它把这张卡改成终态。
                        OpsUI._ap_cards[ap.id] = cards[ap.id]
                        msgs.append(cards[ap.id])
                        changed = True
                    elif drawn.get(ap.id) == key:
                        continue
                    # 更新卡是**原地改对象**，不是按下标替换：中途 pop 掉流式泡之后，
                    # 任何存过的下标都不作数了（踩过——写回旧下标把刚生成的步骤卡盖成了审批卡）。
                    new = self._approval_card(ap, waited)
                    cards[ap.id].content = new.content
                    cards[ap.id].metadata = new.metadata
                    drawn[ap.id] = key
                    changed = True
                    if ap.decision != "pending":
                        with self._gate_lock:  # 画上收尾状态了才摘，按钮随之收起
                            if ap in self._pending:
                                self._pending.remove(ap)

                if changed:
                    yield list(msgs)
                if stop:
                    break
            if err is not None:
                raise err
        finally:
            # v1.1 验过的刹车语义，搬进线程版：
            # 1) interrupt_switch 置真，主循环在下一个步边界抛 AgentError（agents.py:546-547），
            #    正在执行的这一步不会被掐断，等它自己返回；
            # 2) 挂在审批上的那条线程必须一并结算，否则「停止」只是把界面停住，
            #    worker 会永远等在 wait() 里；
            # 3) 关生成器那件事挪进 _worker 的 finally——只能在起它的线程里关。
            self._abandoned.set()
            self.agent.interrupt()
            self._settle_all("cancelled")

    # ---- V5：会话级记忆隔离 ---------------------------------------------------------
    def _bind_memory(self, sid: int) -> None:
        """把 agent.memory 换成这条会话自己的那份。

        只需要换引用：agent.run() 走的是 reset=False（GradioUI 的默认，gradio_ui.py:310），
        框架会把新任务**追加**进 self.memory（agents.py:477 还会顺手把 system_prompt 同步过去），
        所以「谁的记忆」等于「起 worker 那一刻 self.memory 指向谁」。

        两个刻意不做的事：
        - 不传 reset=True：那会连 monitor 一起清零（agents.py:478-480），「进程累计」口径就废了。
        - 不在跑到一半换：worker 线程正在读 self.memory.steps，中途换等于把一条会话的历史
          灌进另一条的当前步，_stats() 的本题边界也会跟着错位。所以只在 _respond 开头调。
        """
        if self._mem_sid == sid:
            return
        mem = self._mem.get(sid)
        if mem is None:
            mem = AgentMemory(self.agent.system_prompt)
            # V6：进程里没这一份，就去库里把它读回来。库里那一串是上一轮（或上一个进程）
            # 用 encode_memory 存的整份步骤，逐条 to_messages() 就是模型下一轮看到的上下文，
            # 所以"重启后接着记得"不需要重放屏幕上的字，也不改变本题累计的边界。
            steps = decode_memory(self.hist.load_memory(sid))
            if steps:
                mem.steps.extend(steps)
            self._mem[sid] = mem
        self.agent.memory = mem
        self._mem_sid = sid

    def _session_steps(self, sid: int) -> list:
        """这条会话自己的步骤——**只读**，不碰 agent.memory、不改绑定（V9）。

        为什么要有这一条：状态条上那串「本题」的数一直从 self.agent.memory 读，而那份
        记忆只在 _respond 开头换（不能在跑到一半换，理由见 _bind_memory 上面的注释）。
        于是点一条旧会话：屏上换成了甲的字，条上报的还是乙、甚至是一份空的——v1.7 基线
        实测「切到甲之后步数仍是 0/8」。要跨重启看见「本题审批」，先得让状态条说的是
        屏幕上这一条会话，而不是上一次提问那条。

        进程里有这一份就直接读它的 steps（正在跑的那条账最全）；没有就按 V6 那条路从库里
        decode。库里那一串若是 v1（还没有 wait 这一格），等待读作 0、那一格不出现，
        其余各格照常。
        """
        mem = self._mem.get(sid)
        if mem is not None:
            return list(mem.steps)
        return decode_memory(self.hist.load_memory(sid))

    # ---- 事件 --------------------------------------------------------------
    def _radio_update(self, force: bool = False):
        """侧栏那条 Radio 的更新（V7）：choices 每帧都刷，value 只在绑定真的换了时给。

        为什么必须带上 value：v1.5 的 bug 是"高亮和绑定不是一回事"——点「＋ 新会话」之后
        上一条还亮着，于是"点那条亮着的"＝点了一个值没变的 radio，gradio 不派发 change，
        问题就落进了新会话。现在反过来，亮哪一条由 self._sid 单向决定。

        为什么不能每帧都带：服务端设 value 会被 gradio 当成一次 change 送回后端（本轮实测：
        程序化设值触发 .change、不触发 .input），流式期间每 0.25 秒一帧，那样就是每秒两次
        空转事件；真送回的那一次由 _select_session 的守卫原样退回。

        force 是给 _on_load 用的：刷新页面后浏览器那一侧的 Radio 是全新的（没勾选），
        但服务端这个 OpsUI 对象还是刚才那一个、_sid_shown 没变，不强迫就永远不补那一下。
        """
        ch = self.hist.choices()
        if force or self._sid_shown != self._sid:
            self._sid_shown = self._sid
            return gr.update(choices=ch, value=self._sid)
        return gr.update(choices=ch)

    def _user_message(self, message):
        """把输入框的值转成一条 user 气泡。

        必须自己加：上游 ChatInterface 会替我们把用户消息拼上，换成自建 Blocks 后
        _stream_response 交出来的只有 assistant 那串，不问这句就永远不进会话、也不进库。
        这里只做显示，不碰 _process_message（那句会把上传文件真复制一份）。
        """
        if isinstance(message, str):
            text, files = message, []
        else:
            payload = message or {}
            text, files = payload.get("text", ""), payload.get("files", [])
        if files:
            text = (text + "\n" if text else "") + "（附件：" + "、".join(Path(f).name for f in files) + "）"
        return gr.ChatMessage(role="user", content=text)

    def _respond(self, message, sid):
        """一次提问。产出 8 元组，顺序必须和 outputs 完全一致（v1.8 的 P0-4 从 7 加到 8：
        末尾多的是计划面板。加一位就得同时改 box.submit 的 outputs 和下面两处 yield，
        少改一处 gradio 报的是「didn't return enough output values」，见 v18_ui.py 开头那条）。
        """
        sid = self.hist.ensure(sid)
        # 一题开工，上一轮的删除确认作废（武装只在「站着不动、连点两下」这一口气里有效）。
        self._armed_del = None
        # V7：高亮跟着「现在绑的是哪条」走，不是跟着点击历史走（见 _select_session）。
        self._sid = str(sid)
        self._bind_memory(sid)
        # D5：这一题的消息**追加**在会话已有消息之后，不是从头起。chatbot 的输出是整体替换、
        # History.save() 又是整条会话覆盖，所以起点必须是库里那一串——v1.3 从这里
        # `[user_msg]` 起头，连问两题就把前一题从屏上和历史库里一起抹掉了。
        base = self.hist.load(sid)
        user_msg = self._user_message(message)
        last: list = base + [user_msg]
        cleared = False
        self._state = "running"
        # Radio 的更新只能给 gr.update(choices=...)；直接交一个 choices 列表会被
        # 当成"选中的值"，gradio 在 preprocess 就抛 ValueError（实测喷的就是这条）。
        # V7：连 value 一起给，但只在绑定真的换了那一次给——服务端设 value 会被 gradio
        # 当成一次 change 送回来（本轮实测：程序化设值只触发 .change，不触发 .input），
        # 流式期间每 0.25 秒一帧，每次都设就等于每秒多空转两次事件。
        radio = self._radio_update
        hidden = (gr.update(visible=False), gr.update(visible=False))
        state = "stopped"  # 只有 AgentError（停止、报错）会停在这一档；断开另有 interrupted
        try:
            for msgs in self._stream_response(message, []):
                last = base + [user_msg] + list(msgs)
                box = gr.update(value=None) if not cleared else gr.update()
                cleared = True
                un = bool(self._unanswered())
                vis = gr.update(visible=un)
                yield (
                    last,
                    self._status_html("awaiting" if un else self._state),
                    radio(),
                    box,
                    sid,
                    vis,
                    vis,
                    self._plan_update(),
                )
            state = "maxed" if self._stats()["maxed"] else "done"
        except GeneratorExit:
            # D8：客户端断开（刷新页面 / 关页面）。gradio 6.30 会把正在流的这条生成器
            # close 掉，实测从点刷新到这里 0.267 s（验收脚本/v1.8/run/v18_d8_baseline.out
            # 的 B1，三次复现 frames 9/10/10）。
            # 必须原样抛出去：GeneratorExit 之后再 yield 是 RuntimeError，所以最后一句
            # 「补一帧 done」在这一路根本不会执行，能落库的只有下面这个 finally。
            state = "interrupted"
            raise
        except AgentError as exc:
            # 跑不完也要有交代：中断、模型侧报错都会走到这里，别让 gradio 甩红框。
            # P0-4：计划被否决／超时未批是**另一档**，不能写成「已停止」——那一题是人在
            # 计划上说不，不是按了 ■ 停止；两档的措辞从 v1.3 起就要求分得开（见 :708 注释）。
            denied = isinstance(exc, PlanDeniedError)
            refused = None if denied else model_refusal(exc)
            if refused is not None:
                # v2.0：服务商不接这一单。措辞要办两件事：说清「这不是你按的停止」，
                # 以及**别把它说成「什么都没发生」**——拒绝只挡住下一次模型调用，
                # 这之前已经批过的工具是真做了的，不会跟着回滚。
                state = "model_refused"
                content = (
                    f"🔒 **{STATE_LABEL[state]}**\n\n"
                    f"这一次模型调用被服务商直接拒了，不是你按了 ■，也不是这台机器里的代码。\n\n"
                    f"{refused}\n\n"
                    "要动的两处都在外面：服务商控制台的账户状态（欠费／风控／限流），"
                    "或 `smolagents/.env` 的 key 与 `my_agent.py` 的 `MODEL_ID`。\n\n"
                    "注意这只挡得住**之后的**模型调用：这之前已经批准执行过的工具不会回滚。"
                )
                title = f"🔒 {STATE_LABEL[state]}"
            else:
                fused = False
                if not denied:
                    # P1-a：熔断抛的也是同一条 AgentError（interrupt() → agents.py:547
                    # 「Agent interrupted.」），和按 ■ 停止在异常层完全同名。不认这个旗就会把
                    # 「它自己绕圈被拦下来收尾」写成「你按了停止」——那是用户在告自己的状。
                    # 两个都占时认停止：人先按下去，熔断只是那一下带来的下一步。
                    with self._gate_lock:
                        fused = OpsUI._dup_tripped and OpsUI._run_seq > OpsUI._cancelled_before
                state = "plan_denied" if denied else ("dup_fused" if fused else "stopped")
                if denied:
                    content = f"✖ **{STATE_LABEL[state]}**\n\n{exc}"
                    title = f"✖ {STATE_LABEL[state]}"
                elif fused:
                    content = (
                        f"⛔ **{STATE_LABEL[state]}**\n\n"
                        f"本题挡下的重复调用超过了上限 {DUP_BLOCK_LIMIT} 次，已在步边界收场。\n\n{exc}"
                    )
                    title = f"⛔ {STATE_LABEL[state]}"
                else:
                    content = f"⏹ {type(exc).__name__}: {exc}"
                    # status 只能是 "pending" 或 "done"（chatbot.py:55 的 Literal）。v1.1 写的
                    # "complete" 一直在，只是没人真在停止后去看气泡：gradio postprocess 抛
                    # ValidationError，整条 chatbot 输出被丢掉（本轮实测抓到，见 D4）。
                    title = f"⏹ {STATE_LABEL[state]}：{type(exc).__name__}"
            last = last + [
                gr.ChatMessage(role="assistant", content=content, metadata={"title": title, "status": "done"})
            ]
        finally:
            self._state = state
            if state == "interrupted":
                # 先把没人点的单子结算掉再改卡。decide() 见非 pending 直接跳过，所以和
                # _stream_response 收尾那一句（:958 附近）重复调用是安全的——两条哪个先到
                # 都不影响这里的账。
                self._settle_all("cancelled")
                last = self._mark_interrupted(self._mem.get(sid), last)
            self.hist.save(sid, last)  # 停止时生成器被关掉，这一句保证半截内容也落库
            # V6：记忆跟着这一题一起落库（覆盖式，和 save() 同口径）。两个条件不能省：
            # _mem_sid 不是本条会话说明中途有人换了会话（并发提问，见 §7），这时存下去
            # 会把别人的记忆盖到这条上；worker 线程可能还在跑（页面被刷新的那一路），
            # 于是这一步可能存下半截——下一题结束时再存就整了，所以半截可接受、存错会话不行。
            mem = self._mem.get(sid)
            if mem is not None and self._mem_sid == sid:
                self.hist.save_memory(sid, encode_memory(mem.steps))
        yield last, self._status_html(state), radio(), gr.update(), sid, *hidden, self._plan_update()

    def _new_session(self):
        self._state = "idle"
        # V7：新会话此刻在库里还没有行（第一问下去才 ensure 出来），所以没有"那一条"可亮——
        # 把高亮清掉才是实话。留着上一条的高亮就是这个 bug 本体：用户照着亮着的那条点，
        # 点的却是一个值没变的 radio，change 不派发，问题落进新会话。
        self._sid = None
        # P0-4：面板同理——新会话没有计划，上一题那份不能跟着过来（和 V7 同一个理由）。
        self._plan_shown = None
        # 换会话 = 上一轮的确认作废：不然「武装在甲、选中乙」时乙的第一下点击就直接删了。
        self._armed_del = None
        return None, [], self._status_html("idle"), self._radio_update(), self._plan_update()

    def _stop(self):
        """■ 停止：把 interrupt_switch 置真，停在下一个步边界（agents.py:546-547）。

        不取消正在跑的事件——那条生成器会在边界抛 AgentError，由 _respond 的 except
        收尾、把半截内容落库，并把状态从「停止中」改成「已停止」。所以这个按钮点下去
        到状态变化之间有一段等待，是设计如此，不是没响应。

        P0-2 之后这里多一行 _settle_all：卡在审批上的线程不看到 decision 就永远不返回，
        光置 interrupt 是停不住的（那条 while 循环连步边界都到不了）。按停止 = 没批的都拒。

        D7 补的是另一半：agents.py:470 在每轮 run 开头会把 interrupt_switch 清回 False，
        所以「停止按在待批卡出现之前」等于对着一台空闲的 agent 按——那一按不留任何痕迹，
        后到的那条待批就没人管了。现在 _stop 除了结算眼前的单子，还给本轮领一个取消号，
        闸入队时看到自己的轮次 <= 该号就直接按 cancelled 结算（见 _gated_call）。
        """
        with self._gate_lock:
            OpsUI._cancelled_before = OpsUI._run_seq
        self._settle_all("cancelled")
        self.agent.interrupt()
        self._state = "stopping"
        return self._status_html("stopping")

    def _select_session(self, sid):
        """点旧会话：屏幕换消息，**sid 也一起换**（V5）。

        v1.3 只换消息、不动 sid，于是下一条提问照样落进一条新会话——屏上看着接上了，
        模型那边其实是开局。现在把选中的 id 写回 State，_respond 开头就会 _bind_memory
        到这条会话自己的记忆上，问的才是同一件事。

        V7 加的守卫：这个回调不再只由点击触发。gradio 6.30 里**服务端设 value 也算一次
        change**（本轮实测：程序化 gr.update(value=...) 触发 .change、不触发 .input，
        连 value=None 都会送回一次 None），所以 _respond / _new_session / _on_load 推上去
        的高亮会原样送回后端。值没变的那一次就是回声，必须四个输出全交 gr.update()——
        这条生成器和正在流式的那条会抢同一个 chatbot 输出，抢赢就把刚画出来的步骤卡盖掉。
        （P0-4 之前这里是「三个」，面板加上来变四个，纪律没变。）

        V9：状态条改成报**屏幕上这一条**的数（_session_steps，只读）。以前这里调
        _status_html("idle") 读的是 self.agent.memory，而绑定还留在刚才提问的那条会话上，
        于是"屏上是甲、条上是乙"。不顺手在这里 _bind_memory：那条路会把 worker 线程正在读的
        记忆换掉（见 _bind_memory 的第二条"刻意不做"），V5 的语义也不该由一次点击改动。
        """
        if not sid or str(sid) == self._sid:
            return gr.update(), gr.update(), gr.update(), gr.update()
        self._sid = str(sid)
        # 浏览器那一侧已经是你点的那条了，账跟着记上，下一帧就不必再回送一次 value。
        self._sid_shown = self._sid
        # 换会话 = 删除的确认作废（同 _new_session 那条理由）。按钮文案上可能还挂着
        # 「⚠ 确认删除？」——那是这一格的输出槽没接 del_btn 的代价，改动要连动
        # _select_session / _new_session 两处返回值和两条 wiring，不值当：文案陈旧只会让人
        # 多点一下重新武装（_armed_del 已经不是这一条了），不会把另一条删掉。
        self._armed_del = None
        # P0-4：面板跟着屏幕上这一条走（和 V9 的状态条同一个理由：不能"屏上是甲、
        # 面板上是乙"）。这一步读的是这条会话的记忆，而记忆里的计划一定是批过的
        # （见 _last_plan），所以点旧会话看到的读数是「已批准」。
        steps = self._session_steps(int(sid))
        self._plan_shown = self._last_plan(steps)
        return self.hist.load(int(sid)), self._status_html("idle", steps), int(sid), self._plan_update()

    def _delete_session(self, sid):
        """🗑 删除：删掉侧栏当前选中的那一条会话，连带它的消息与模型记忆。不可逆。

        六格输出，顺序必须和 del_btn.click 的 outputs 完全一致：
        [sid, chatbot, status, radio, plan, del_btn]。

        三条设计决定：

        1. **第二次点击才真删**（`_armed_del`）。库里一删，messages 与 memory 两张表
           一起没（History.delete），重启也回不来，屏幕上也找不回那句「刚才那条会话」。
           确认信息带在按钮自己的文案上，不弹框——gradio 里弹确认要么引第三方组件、
           要么走前端 JS，两条都比这一格文案贵。
        2. **跑着的时候不删**（_state 是 running/stopping）。这不是怕界面上少一块，是真会
           炸：_respond 的 finally 无条件 `self.hist.save(sid, last)`（:1602），行没了
           UPDATE 就是 0 行、不会重建，紧跟着的 INSERT messages 撞外键抛 IntegrityError，
           而它在 finally 里、没人接。也不在这句话里替用户「先停再删」——停止是他按的，
           删除也是他按的，两件事不该由一次点击替他合并。
        3. **删完回到「没有选中」**，而不是自动跳到列表第一条。后者看着贴心，实际是
           把人刚删的那条的邻居顶上屏幕，误以为「删错了、内容还在」；清空才是这条操作
           该给的反馈。新会话那一路同理（见 _new_session）。
        """
        cur = str(sid) if sid else None
        # 槽位写死顺序，不用 `*` 展开元组拼：展开一次错位，gradio 报的是「输出值类型不对」
        # 而不是「你放错了第几格」，六个槽里挑一个错，屏幕上就是状态条跑到 radio 上去。
        # keep = 这一格不动（chatbot / radio / plan 三格在「没删成」的三条分支里都不该动）。
        keep = gr.update()
        if self._state in ("running", "stopping"):
            return (
                sid,
                keep,
                self._status_html(self._state) + self._flash("生成中不能删除：先按 ■ 停止，等状态变成「已停止」再删。"),
                keep,
                keep,
                gr.update(),
            )
        if not cur:
            return (
                sid,
                keep,
                self._status_html("idle") + self._flash("先在左边点一条会话，再按删除。"),
                keep,
                keep,
                gr.update(),
            )

        if self._armed_del != cur:
            self._armed_del = cur
            title = next((c[0] for c in self.hist.choices() if c[1] == cur), "这条会话")
            return (
                sid,
                keep,
                self._status_html("idle")
                + self._flash(f"确认删除「{title}」？这条的消息和模型记忆都会一起清掉，不可恢复。"),
                keep,
                keep,
                gr.update(value="⚠ 确认删除？"),
            )

        title = next((c[0] for c in self.hist.choices() if c[1] == cur), "这条会话")
        n = self.hist.delete(int(cur))
        # 进程里那份记忆必须一起摘：_mem 是 id -> AgentMemory，只删库不删它的话，
        # AUTOINCREMENT 不会复用这个 id，所以那份对象是纯泄漏（再也拿不到，但占着整段历史）。
        self._mem.pop(int(cur), None)
        self._armed_del = None
        self._sid = None
        self._plan_shown = None
        counts = f"{n['messages']} 条消息" + (f"、{n['memory']} 份模型记忆" if n["memory"] else "")
        return (
            None,
            [],
            self._status_html("idle") + self._flash(f"已删除「{title}」（{counts}）。"),
            self._radio_update(),
            self._plan_update(),
            gr.update(value="🗑 删除"),
        )

    def _on_load(self):
        """刷新页面时把库里的会话重新推上屏，并把 sid 指到最近一条。

        gradio 不会重跑 create_app，Radio 的 choices 还是建应用那一刻的空表——
        实测重载后侧栏是空的，所以必须挂 load。
        """
        ch = self.hist.choices()
        sid = int(ch[0][1]) if ch else None
        msgs = self.hist.load(sid) if sid else []
        # sid 也要给：屏上显示的就是这条最近会话，空着的话下一条提问另开一条，
        # 屏幕被整体替换，刚看到的那串字就找不回来了（D5 的另一条路径）。
        # V7：高亮跟着它一起给（force）——v1.5 这里是"绑着丙、侧栏一条都不亮"，
        # 用户看不出自己在哪条会话里，也就有了后面那两次点错门。
        # V9：状态条同样按屏幕上这一条报（和 _select_session 一个口径）。这一条是**重启后
        # 第一次看**的那个入口：新进程的 _mem 是空的，_session_steps 直接走库里那一串，
        # 所以「本题审批」能不能跨重启读出来，刷新这一下就是最干净的验收动作。
        self._sid = str(sid) if sid else None
        # 刷新页同理：重新选中的可能正是刚武装过的那一条，不清就要一次点击就删。
        self._armed_del = None
        shown = self._session_steps(sid) if sid else None
        # P0-4：面板同样从这条会话的记忆里读（MEM_FIELDS["PlanningStep"] 带着 plan 原文，
        # 所以计划能跨重启回来）。挂在这一条上的理由和 V9 那一条一模一样：刷新之后
        # 屏上不能少一块刚才是有的东西。
        self._plan_shown = self._last_plan(shown)
        return self._radio_update(force=True), sid, self._status_html("idle", shown), msgs, self._plan_update()

    # ---- 外壳 --------------------------------------------------------------
    def create_app(self):
        with gr.Blocks(title="我的 Agent", analytics_enabled=False, elem_id="app") as demo:
            sid = gr.State(value=None)
            with gr.Row(elem_id="layout"):
                with gr.Column(scale=1, min_width=208, elem_id="sidebar"):
                    gr.HTML(
                        f'<div id="brand"><b>我的 Agent</b><span>{html.escape(str(getattr(agent, "name", "")))}'
                        f" · {html.escape(str(getattr(agent.model, 'model_id', '?')))} · 本地</span></div>"
                    )
                    with gr.Row(elem_id="sessionbtns"):
                        new_btn = gr.Button("＋ 新会话")
                        # 删除针对的是**当前选中**那一条（sid 这格 State），不是「选中的那条
                        # 里的内容」，所以它和新会话同排；文案里不带会话名，208px 的侧栏放不下。
                        del_btn = gr.Button("🗑 删除", min_width=76, elem_id="del-btn")
                    radio = gr.Radio(choices=self.hist.choices(), show_label=False, container=False, elem_id="sessions")
                with gr.Column(scale=4, elem_id="main"):
                    with gr.Row(elem_id="statusrow"):
                        status = gr.HTML(self._status_html("idle"), scale=5)
                        # 审批键平时不出现，只有队里有待批项时才被点亮（见 _respond 的 vis）。
                        allow_btn = gr.Button("✔ 允许", scale=0, min_width=76, visible=False, elem_id="approve-btn")
                        deny_btn = gr.Button("✖ 拒绝", scale=0, min_width=76, visible=False, elem_id="deny-btn")
                        # 刹车只能自己接：MultimodalTextbox 自带的那个 stop 键是 ChatInterface
                        # 靠前端取消事件流才生效的，换成自建 Blocks 后点了没反应（实测：
                        # 7/8 处点它，照样跑到 9/8 才完）。这里直接调 agent.interrupt()。
                        stop_btn = gr.Button("■ 停止", variant="stop", scale=0, min_width=88)
                    # P0-4：计划面板。它是计划正文**唯一一处看得见**的地方——消息流里那张
                    # 计划卡带着 title，gradio 一律折起来，收起时正文不在 DOM 里
                    # （见 _step_card 开头那条），而实测这份产出有 6,195 字符。
                    # 没有计划的题（含把 PLANNING_INTERVAL 设回 None）这块整个不出现，
                    # 所以关掉开关之后屏幕和 v1.8 之前逐像素一样。
                    plan = gr.Markdown("", elem_id="planpanel", visible=False)
                    chatbot = gr.Chatbot(
                        height=520,
                        show_label=False,
                        # panel = 整行宽的 llm 排布；默认 bubble 会把气泡按内容收缩，
                        # 实测折叠卡被挤成 350px 一条，右侧空掉一大片。
                        layout="panel",
                        placeholder='<div style="text-align:center;color:#6e7681">还没有会话。<br>左边「＋ 新会话」开一局，或直接提问。</div>',
                        latex_delimiters=[
                            {"left": r"$$", "right": r"$$", "display": True},
                            {"left": r"$", "right": r"$", "display": False},
                            {"left": r"\[", "right": r"\]", "display": True},
                            {"left": r"\(", "right": r"\)", "display": False},
                        ],
                    )
                    box = gr.MultimodalTextbox(
                        placeholder="问我一个问题…",
                        file_count="multiple",
                        show_label=False,
                        submit_btn=True,
                        stop_btn=False,
                    )

            box.submit(
                fn=self._respond,
                inputs=[box, sid],
                # P0-4：末尾多了 plan 这一格，_respond 的产出跟着从 7 变 8。
                # 这一行和 _respond 里那两处 yield 必须同时改，少改一处就是
                # `A function (_respond) didn't return enough output values (needed: 8, returned: 7)`。
                outputs=[chatbot, status, radio, box, sid, allow_btn, deny_btn, plan],
            )
            new_btn.click(fn=self._new_session, outputs=[sid, chatbot, status, radio, plan])
            # 删除当前选中那一条。六个槽：sid 必须回写 None——只清高亮不动 State 的话，
            # 下一条提问还带着被删掉的 id 进 _respond（详见 History.ensure 那条注释）。
            # chatbot 这一格由本回调写是安全的：_delete_session 在 running/stopping 直接退回，
            # 走到这一步时那条流式生成器已经收尾了（对比 allow/deny 两个键，它们在生成期
            # 会被点亮，所以刻意不碰 chatbot）。
            del_btn.click(
                fn=self._delete_session,
                inputs=[sid],
                outputs=[sid, chatbot, status, radio, plan, del_btn],
            )
            # 点旧会话要连 sid 一起换，否则下一条提问仍落进新会话（V5）。
            radio.change(fn=self._select_session, inputs=[radio], outputs=[chatbot, status, sid, plan])
            stop_btn.click(fn=self._stop, outputs=[status])
            # 审批键只改 decision + 点亮/收起自己，不碰 chatbot：
            # 那条流式生成器还活着，消息列表由它独占，两边写同一个输出会互相盖掉。
            # P0-4：面板同理不挂在这两个键上——它由那条流式生成器独占。代价是读数晚一帧，
            # 实测这一帧多大：验收脚本/v1.8/run/v18_p04_live.out 里「数字①」那一档，
            # 允许/拒绝/停止/超时四跑分别是 **0.040 / 0.074 / 0.016 / 0.001 s**
            # （C1 那一跑是 0.074s，最坏的一档；上限就是那 0.25 秒的轮询间隔）。
            # 另外两档分开设定，别混着读：
            #   · 断开那一跑（C3）里，这一页在门之后**没有下一帧**了——面板的终态读数
            #     要等下一次页面加载由 _on_load 重算，那不是延迟。
            #   · 「面板第一次上屏」的另一半在浏览器里：until 轮询粒度 1s，五跑分别
            #     1,006 / 2 / 3 / 8 / 2 ms，说的是「1 秒粒度内已上屏」，不是毫秒级延迟。
            allow_btn.click(fn=lambda: self._decide("allowed"), outputs=[status, allow_btn, deny_btn])
            deny_btn.click(fn=lambda: self._decide("denied"), outputs=[status, allow_btn, deny_btn])

            demo.load(fn=self._on_load, outputs=[radio, sid, status, chatbot, plan])
        return demo


if __name__ == "__main__":
    ui = OpsUI(agent, file_upload_folder="./data")
    try:
        ui.launch(
            share=False,
            server_name="127.0.0.1",
            server_port=7860,
            css=DARK_CSS,
        )
    finally:
        # A1 的 atexit 兜不住这一条路：下面那句 os._exit(0) 压根不跑 atexit。
        # 不显式 disconnect，mcp-server-time / mcp-server-fetch 两个子进程就留在系统里
        # （stdio 管道断了它们也不一定立刻退，实测要等客户端把那端 read 关掉）。
        my_mcp.detach(ui._mcp)
    # Ctrl-C 之后 gradio 会关掉端口但留下非守护线程，进程卡住不退出；
    # 启动器的「退出后自收终端窗口」那段就永远轮不到执行。硬退一次。
    os._exit(0)
