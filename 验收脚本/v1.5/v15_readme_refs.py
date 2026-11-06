# -*- coding: utf-8 -*-
"""v1.5 行号回写：README 里所有 my_ui.py 的行号按 v1.5（1,108 行）重新对齐。

每条 (旧串, 新串) 必须在文中**恰好出现一次**，否则整批不落盘——避免把
"改了个大概"当成"改完了"。跑完再人工看 diff。
"""
import pathlib
import sys

MD = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/README.md")
txt = MD.read_text(encoding="utf-8")
pairs = [
    # 1.3 拓扑图
    ("自建 Blocks · my_ui.py:823<br/>", "自建 Blocks · my_ui.py:1038<br/>"),
    ("会话库 History · my_ui.py:213<br/>", "会话库 History · my_ui.py:373<br/>"),
    ("审批门 · my_ui.py:342", "审批门 · my_ui.py:527"),
    # 6.3.1
    ("`smolagents/my_ui.py:886-889`，v1.1 前在", "`smolagents/my_ui.py:1101-1104`，v1.1 前在"),
    ("launch()<br/>my_ui.py:885", "launch()<br/>my_ui.py:1100"),
    ("127.0.0.1<br/>my_ui.py:886-889", "127.0.0.1<br/>my_ui.py:1101-1104"),
    ("os._exit(0)，my_ui.py:893", "os._exit(0)，my_ui.py:1108"),
    ("交副本给 gradio（`my_ui.py:673`", "交副本给 gradio（`my_ui.py:868`"),
    # 6.3.2
    ("`_step_card`，`:450-500`；标题拼装 `:479-482`，末行 `:495`",
     "`_step_card`，`:642-691`；标题拼装 `:671-675`，末行 `:686-688`"),
    ("`finally`（`:565-573`）", "`finally`（`:757-765`）"),
    ("结算待批（`:678-687`）", "结算待批（`:873-882`）"),
    ("participant O as OpsUI._stream_response<br/>my_ui.py:575-687",
     "participant O as OpsUI._stream_response<br/>my_ui.py:767-882"),
    ("participant W as _worker 线程<br/>my_ui.py:550-573",
     "participant W as _worker 线程<br/>my_ui.py:742-765"),
    # 6.3.4
    ("_respond(message, sid)<br/>my_ui.py:728-781", "_respond(message, sid)<br/>my_ui.py:929-987"),
    ("`create_app()`（`my_ui.py:823-881`）", "`create_app()`（`my_ui.py:1038-1096`）"),
    ("（`_user_message()`，`:712-726`）", "（`_user_message()`，`:913-927`）"),
    ("刹车改由 `:843` 的自建「■ 停止」→ `_stop()`（`:784-797`）",
     "刹车改由 `:1058` 的自建「■ 停止」→ `_stop()`（`:992-1013`）"),
    ("挂 `demo.load`（`:880`，回调 `:810-820`）", "挂 `demo.load`（`:1095`，回调 `:1025-1037`）"),
    ("`History`（`:213-309`）", "`History`（`:373-489`）"),
    ("而不是 cwd | `:28` |", "而不是 cwd | `:30` |"),
    ("| `:277-298`，`DELETE` 在 `:289` |", "| `:442-463`，`DELETE` 在 `:454` |"),
    ("| `:284-285` 取值，`:291-298` 那条", "| `:449-450` 取值，`:460-463` 那条"),
    ("上限 **50** 条 | `:260-265` |", "上限 **50** 条 | `:425-430` |"),
    ("各自一列，`:281-286` 先用", "各自一列，`:446-451` 先用"),
    ("重建 `gr.ChatMessage`（`:274`）", "重建 `gr.ChatMessage`（`:439`）"),
    ("深色壳（`DARK_CSS`，`:53-172`）", "深色壳（`DARK_CSS`，`:213-332`）"),
    ("（`:106-115`：待批胶囊的描边", "（`:265-275`：待批胶囊的描边"),
    # 6.3.5
    ("套法见 `_install_gate`（`:342-365`）", "套法见 `_install_gate`（`:527-550`）"),
    ("换一个新实例再盖（`:356`、`:363`）", "换一个新实例再盖（`:541`、`:548-550`）"),
    ("（`:362`）。不保签名", "（`:547`）。不保签名"),
    ("（`:370`）能把参数还原成字典", "（`:555`）能把参数还原成字典"),
    ("幂等标记 `_opsui_gated`（`:354`）", "幂等标记 `_opsui_gated`（`:539`、`:549`）"),
    ("挂在**类**上（`:322-323`）", "挂在**类**上（`:502-503`）"),
    ("`GATED_TOOLS = (\"write_file\", \"run_python\")`（`:32`）",
     "`GATED_TOOLS = (\"write_file\", \"run_python\")`（`:34`）"),
    ("挪进 `_worker` 线程（`:550-573`）", "挪进 `_worker` 线程（`:742-765`）"),
    ("`_stream_response`（`:575-687`）变成", "`_stream_response`（`:767-882`）变成"),
    ("`q.get(timeout=0.25)`（`:599`）", "`q.get(timeout=0.25)`（`:794`）"),
    ("（`:648-670`），否则待批卡", "（`:843-865`），否则待批卡"),
    ("流式思考气泡（`:604-615`）、审批卡（`:648-670`）、步骤卡（`:616-634`）",
     "流式思考气泡（`:799-810`）、审批卡（`:843-865`）、步骤卡（`:811-829`）"),
    ("存**卡片对象**（`:591-592`）", "存**卡片对象**（`:786`、`:850-851`）"),
    ("`content` / `metadata`（`:663-664`）", "`content` / `metadata`（`:858-859`）"),
    ("（`:617-619`）", "（`:812-814`）"),
    ("（`:667-670`）", "（`:862-865`）"),
    ("`_step_card`（`:450-500`）", "`_step_card`（`:642-691`）"),
    ("和 token（`:479-482`）", "和 token（`:671-675`）"),
    ("本题累计（`:495`）", "本题累计（`:686-688`）"),
    ("`DECISION_LABEL`（`:35-41`）", "`DECISION_LABEL`（`:37-45`）"),
    ("`DENIED_VERDICT`（`:49`）", "`DENIED_VERDICT`（`:51`）"),
    ("`DENIED_OBSERVATION`（`:44-48`）", "`DENIED_OBSERVATION`（`:46-50`）"),
    ("命中哪一条来上色（`:469`）", "命中哪一条来上色（`:661`）"),
    ("的 `finally`（`:678-687`）现在是三件事", "的 `finally`（`:873-882`）现在是三件事"),
    ("换题开局同样先结算再摘除（`:577-580`）", "换题开局同样先结算再摘除（`:770-772`）"),
    ("已改成 `\"done\"`（`:772`）", "已改成 `\"done\"`（`:973`）"),
    ("而按钮只结算**最早**那条（`:385`）", "而按钮只结算**最早**那条（`:584`）"),
    ("`APPROVAL_TIMEOUT = 600.0`（`:34`）", "`APPROVAL_TIMEOUT = 600.0`（`:36`）"),
    ("🧭 卡（`:456-460`）", "🧭 卡（`:648-653`）"),
    # 6.3.6
    ("（`:277-298`，`DELETE` 在 `:289`）——它只有在", "（`:442-463`，`DELETE` 在 `:454`）——它只有在"),
    ("inputs 和 outputs 上（`:866-870`）", "inputs 和 outputs 上（`:1081-1085`）"),
    ("`base = self.hist.load(sid)`，`:735`", "`base = self.hist.load(sid)`，`:936`"),
    ("list(msgs)`，`:747`", "list(msgs)`，`:948`"),
    ("`_bind_memory(sid)`（`:690-709`）", "`_bind_memory(sid)`（`:885-910`）"),
    ("`_mem[sid]`（`:337-338` 那两个字段）", "`_mem[sid]`（`:522-523` 那两个字段）"),
    ("`_stats()`（`:502`）", "`_stats()`（`:694`）"),
    ("只在 `_respond` 开头调（`:731`）", "只在 `_respond` 开头调（`:932`）"),
    ("的 `outputs` 多带 `sid`（`:873`）", "的 `outputs` 多带 `sid`（`:1088`）"),
    ("交出 `int(sid)`（`:808`）", "交出 `int(sid)`（`:1014-1024`）"),
    ("从闭包提成方法（`:810-820`）", "从闭包提成方法（`:1025-1037`）"),
    ("保住（`:291-298`）", "保住（`:460-463`）"),
    # 9.1 表
    ("| `smolagents/my_ui.py:450-500` |", "| `smolagents/my_ui.py:642-691` |"),
    ("| `smolagents/my_ui.py:28` |", "| `smolagents/my_ui.py:30` |"),
    ("（v1.3 `_install_gate`，`my_ui.py:342-365`）", "（v1.3 `_install_gate`，`my_ui.py:527-550`）"),
    ("按钮只结算最早那条（`my_ui.py:385`）", "按钮只结算最早那条（`my_ui.py:584`）"),
    ("| `smolagents/my_ui.py:550-573`、`:575-687` |", "| `smolagents/my_ui.py:742-765`、`:767-882` |"),
    ("| `smolagents/my_ui.py:44-49` |", "| `smolagents/my_ui.py:46-51` |"),
    ("（`my_ui.py:690-709`）", "（`my_ui.py:885-910`）"),
    ("| `smolagents/my_ui.py:735`、`:747` |", "| `smolagents/my_ui.py:936`、`:948` |"),
    ("| `smolagents/my_ui.py:808`、`:873`、`:820`、`:880` |",
     "| `smolagents/my_ui.py:1014`、`:1088`、`:1025`、`:1095` |"),
    ("| `smolagents/my_ui.py:291-298` |", "| `smolagents/my_ui.py:460-463` |"),
]

bad = []
for old, new in pairs:
    n = txt.count(old)
    if n != 1:
        bad.append((n, old[:70]))
        continue
    txt = txt.replace(old, new, 1)

print("配对 %d 条 / 未命中或多次 %d 条" % (len(pairs), len(bad)))
for n, o in bad:
    print("  count=%d  %s" % (n, o))
if bad:
    sys.exit(1)
MD.write_text(txt, encoding="utf-8")
print("已写回 README.md")
