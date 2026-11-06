# -*- coding: utf-8 -*-
"""P1-a 的零成本现场回放：真 OpsUI ＋ 真 agent ＋ 真工具 ＋ 假模型（把 21:06 那份调用序列逐字喂回去）。

为什么要有这一份：2026-11-03 深夜起探针跑真模型时，百炼返回
`400 - Access denied, please make sure your account is in good standing`（overdue-payment 那一档，
见 run/v18_probe_D0.stdout），真模型那一路当场测不了。离线闸（v18_test_dup.py，75 条）测的是
一个个孤立的调用点，这份测的是**整条链路**：_respond → worker 线程 → agent.run(stream=True) →
真工具执行 → 查重层 → 熔断 → AgentError → 收尾档位 → 落库。

两格 A/B 用的是同一份剧本，差别只有一处：
  · dup-on（产品代码）：OpsUI 正常装门，查重层在场。
  · dup-off（对照）：构造 OpsUI **之前**先把 agent 自己那份工具副本打上 _opsui_dedup、
    把 agent 打上 _opsui_dup_stop——装门那一步见到幂等标记就整体跳过，于是这一格跑的确实是
    「第④刀那一版、没有查重层」的代码路径（同一个进程、同一份剧本、同一批真工具）。
    工具副本是 make_agent 里 copy.copy 出来的，所以打标只脏这一格自己的对象，
    my_coding_agent 里那批模块级单例从头到尾没被写过（第 A12 条当场验）。

必须说清的口径（别把回放的数当成本）：
  · **token 数是剧本设定的假数**，不是测量值。这份证据里能当结论的只有「模型被调用了几次」
    「工具真的执行了几次」「熔断落在第几步」「收尾档位是哪个」这类**次数与形状**。
  · stream_outputs 关着：ScriptModel 不实现 generate_stream，agents.py:1252-1255 见到
    stream_outputs=True 而没有 generate_stream 直接拒构造。所以这一格不含「逐字 delta 上屏」
    那一段——那一段是 v1.3 起就验过、跟本刀无关的老路，本轮只能标【未验证：真模型流式下的
    熔断帧序】。
  · 模型会不会真的这么走，回放证不了——那要等账户能用时跑 v18_run_live.py D0。
    剧本逐字取自 run/v18_p0abc_live.out 第四节那 11 条里的**第 1～8 条**，而那 8 条正是 21:06
    的 run A 单轮（日志里两条 `New run - smolagents` 横幅之间的 8 步）。按本刀的口径（换题清零）
    重走这 8 步：第 3 步（人生/ 第二次）、第 4 步（{} 第二次）、第 8 步（{} 第三次）= 被挡下第 3 次
    的那一步恰好是第 8 步，也就是 max_steps 的边界——所以「熔断落在最后一步」这个形状是**抄来的**，
    不是我挑出来的最坏情况。同一形状在另一份真实单轮里也成立（v18_p0abc_old_A_r2.out：
    第 3/5/8 步各挡一次，第 3 次同样落在第 8 步）。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_dup_replay.py
产物：run/v18_p1a_replay.out
"""
import copy
import hashlib
import inspect
import json
import pathlib
import re
import sqlite3
import sys
import time

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui  # noqa: E402
from my_ui import DUP_BLOCK_LIMIT, DUP_FUSE_MARK, DUP_MARK, OpsUI  # noqa: E402
from smolagents import (  # noqa: E402
    BaseTool,
    ChatMessage,
    MessageRole,
    Model,
    TokenUsage,
    ToolCallingAgent,
)
from smolagents.memory import ActionStep  # noqa: E402
from smolagents.models import ChatMessageToolCall, ChatMessageToolCallFunction  # noqa: E402

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
RUN = pathlib.Path(__file__).resolve().parent / "run"
OUT = RUN / "v18_p1a_replay.out"
Q = "删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动"

# 21:06 run A 的逐步调用序列（v18_p0abc_live.out 第四节那 11 条里的第 1～8 条）。
# content 是当时模型那句思考的压缩版，不参与判定；token_usage 是**假数**（见文件头口径）。
FINAL_TEXT = "这一步我没法执行：目标在根外。"
SCRIPT = [
    {"calls": [("list_dir", {"path": "人生/"})], "in": 2349, "out": 17},
    {"calls": [("list_dir", {})], "in": 2463, "out": 22},
    {"calls": [("list_dir", {"path": "人生/"})], "in": 2571, "out": 24},  # ← 第 1 次重复
    {"calls": [("list_dir", {})], "in": 2680, "out": 26},  # ← 第 2 次重复
    {"calls": [("grep_files", {"pattern": "人生", "path": "."})], "in": 2797, "out": 31},
    {"calls": [("list_dir", {"path": "data/"})], "in": 3102, "out": 35},
    {"calls": [("list_dir", {"path": "职业规划/"})], "in": 3471, "out": 38},
    {"calls": [("list_dir", {})], "in": 3957, "out": 42},  # ← 第 3 次重复：熔断
    # 第 9 条只有对照格会用到：没有查重层时 8 步用满，框架走 _handle_max_steps_reached
    # （agents.py:607）再打**一次**模型要结论。注意那一路只认正文：
    # provide_final_answer 回来之后取的是 final_answer.content（agents.py:627-637），
    # 那一次就算吐 tool_calls 也没人执行——所以这一条的答案写在 content 里。
    # dup-on 那格走不到这里。
    {"calls": [("final_answer", {"answer": FINAL_TEXT})], "content": FINAL_TEXT, "in": 4308, "out": 1458},
]

EXEC = {}  # 工具名 -> 真的进了 forward 的次数（查重层挡掉的不会到这里）


class ScriptModel(Model):
    """假模型：第 i 次 generate() 就吐剧本第 i 条。没有 generate_stream，
    所以 agents.py:1252 那条校验要求我们把 stream_outputs 关掉，_step_stream 走
    self.model.generate() 那一支（agents.py:1309）。"""

    def __init__(self):
        super().__init__(model_id="scripted-replay")
        self.i = 0

    def generate(self, messages, stop_sequences=None, response_format=None,
                 tools_to_call_from=None, **kwargs):
        item = SCRIPT[min(self.i, len(SCRIPT) - 1)]
        self.i += 1
        calls = [
            ChatMessageToolCall(
                id="c%d" % k,
                type="function",
                function=ChatMessageToolCallFunction(
                    name=n, arguments=json.dumps(a, ensure_ascii=False), description=None
                ),
            )
            for k, (n, a) in enumerate(item["calls"])
        ]
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=item.get("content", "（回放剧本第 %d 步）" % self.i),
            tool_calls=calls,
            token_usage=TokenUsage(input_tokens=item["in"], output_tokens=item["out"]),
        )


def make_agent():
    from my_agent import AnnualizedVolTool, MaxDrawdownTool
    from my_coding_agent import grep_files, list_dir, read_file, run_python, write_file

    base = [MaxDrawdownTool(), AnnualizedVolTool(), read_file, list_dir, grep_files, write_file, run_python]
    agent = ToolCallingAgent(
        tools=[copy.copy(t) for t in base],
        model=ScriptModel(),
        max_steps=8,
        stream_outputs=False,      # 见文件头那条口径：ScriptModel 没有 generate_stream
        planning_interval=None,    # 和 ④ 的 A/B 两格同条件：探针侧关规划
    )
    # 计数器装在 OpsUI 之前：之后审批层、查重层各自 copy.copy 时读到的 base.forward 就是
    # 这一层，于是它们套在计数器外面——被挡掉的调用压根到不了计数器，EXEC 数的就是真执行。
    for name, tool in list(agent.tools.items()):
        if name == "final_answer":
            continue
        orig = tool.forward
        EXEC[name] = 0

        def counted(*a, _n=name, _o=orig, **kw):
            EXEC[_n] += 1
            return _o(*a, **kw)

        counted.__signature__ = inspect.signature(orig)
        tool.forward = counted
    return agent


def build(dedup):
    """dedup=False 时在**这一格自己的工具副本**上竖幂等标记，让 _install_dup_gate 整体跳过。"""
    agent = make_agent()
    agent.planning_interval = None
    if not dedup:
        # final_answer 不碰：它是 smolagents 模块级共享对象（所有 agent 同一个实例），
        # 打上标记会漏到进程里别的 agent 上；而且查重层本来就按名字跳过它。
        for name, tool in agent.tools.items():
            if name != "final_answer":
                tool._opsui_dedup = True
        agent._opsui_dup_stop = True
    db = RUN / ("v18_p1a_replay_%s.sqlite3" % ("on" if dedup else "off"))
    for p in (db, pathlib.Path(str(db) + "-wal"), pathlib.Path(str(db) + "-shm"),
              pathlib.Path(str(db) + "-journal")):
        p.unlink(missing_ok=True)
    my_ui.DB_PATH = db
    ui = OpsUI(agent, file_upload_folder="./data")
    return ui, agent, db


def rows(db):
    c = sqlite3.connect(str(db))
    try:
        return (c.execute("SELECT count(*) FROM messages").fetchone()[0],
                c.execute("SELECT count(*) FROM memory").fetchone()[0])
    finally:
        c.close()


def digest(ui, agent, db, label, skip=0, base=None):
    """跑完一格之后把「次数与形状」全数出来。返回值第二项是给断言用的结构化字典。

    skip / base 给「连问两遍」那一格用：前一遍的步数与前一遍的执行数要从账里减掉，
    否则第二问的数会连着第一问一起数。
    """
    base = base or {}
    steps = agent.memory.steps[skip:]
    acts = [s for s in steps if isinstance(s, ActionStep)]
    obs = [(s.step_number, (s.observations or ""), (type(s.error).__name__ if s.error else "")) for s in acts]
    dup_steps = [n for n, o, _ in obs if DUP_MARK in o]
    fuse_steps = [n for n, o, _ in obs if DUP_FUSE_MARK in o]
    calls = sum(len(s.tool_calls or []) for s in acts)
    blocked = sum(o.count(DUP_MARK) for _, o, _ in obs)
    last_yield = digest.last_yield
    msgs = last_yield[0] if last_yield else []
    titles = [m.metadata.get("title") for m in msgs
              if isinstance(m, my_ui.gr.ChatMessage) and isinstance(m.metadata, dict) and m.metadata.get("title")]
    state_cls = (re.search(r'class="([^"]+)"', last_yield[1]).group(1) if last_yield else "?")
    # FinalAnswerStep 只 yield、不进 memory（agents.py:609-611 那句没有 append），
    # 所以「这题是不是靠答案收的场」只能看屏幕/库里那串气泡。
    answered = any(FINAL_TEXT[:12] in (m.content or "") for m in msgs if isinstance(m, my_ui.gr.ChatMessage))
    d = {
        "model_calls": agent.model.i,
        "step_types": ",".join(type(s).__name__.replace("Step", "") for s in steps),
        "action_steps": len(acts),
        "calls": calls,
        "calls_per_step": [len(s.tool_calls or []) for s in acts],
        "blocked": blocked,
        "executed": sum(EXEC[n] - base.get(n, 0) for n in EXEC),
        "dup_steps": dup_steps,
        "fuse_steps": fuse_steps,
        "err_steps": [n for n, _, e in obs if e],
        "answered": answered,
        "state": ui._state,
        "state_cls": state_cls,
        "title": titles[-1] if titles else "-",
        "card_titles": titles,
        "db": rows(db),
        "twice": sorted({t for t in titles if titles.count(t) > 1}),
        "tokens_fake": "%d/%d" % (ui._run_in, ui._run_out),
    }
    lines = [
        "== 格 %s ==" % label,
        "  模型被调用次数（剧本被取走几条）: %d / 剧本共 %d 条" % (d["model_calls"], len(SCRIPT)),
        "  memory 步型: %s" % d["step_types"],
        "  ActionStep: %d 步，各步登记的调用数 %s，合计 %d 次；其中 %d 次被查重层挡下（观察值带「%s」），%d 次进了工具函数"
        % (d["action_steps"], d["calls_per_step"], d["calls"], d["blocked"], DUP_MARK, d["executed"]),
        "  重复落在第几步: %s   熔断落在第几步: %s" % (d["dup_steps"] or "-", d["fuse_steps"] or "-"),
        "  带 error 的步: %s   收到了最终答案: %s" % (d["err_steps"] or "-", d["answered"]),
        "  收尾档位: %s   状态条 class: %s" % (d["state"], d["state_cls"]),
        "  收尾气泡标题: %s" % d["title"],
        "  屏上卡片/气泡标题序列: %s" % " | ".join(d["card_titles"]),
        "  同一张卡出现两遍: %s" % (d["twice"] or "无"),
        "  库: messages=%d 行 / memory=%d 行" % d["db"],
        "  状态条 token（**假数**，剧本设定）: in/out=%s" % d["tokens_fake"],
        "  本格逐工具真执行次数: %s" % ", ".join(
            "%s=%d" % (n, EXEC[n] - base.get(n, 0)) for n in sorted(EXEC)),
    ]
    for n, o, e in obs:
        lines.append("    第 %d 步  %s%s" % (n, ("[%s] " % e) if e else "", o.replace("\n", " ")[:66]))
    return "\n".join(lines), d


digest.last_yield = None


def run(dedup):
    global EXEC
    EXEC = {}
    ui, agent, db = build(dedup)
    gen = ui._respond(Q, None)
    out = None
    for out in gen:
        pass
    digest.last_yield = out
    return digest(ui, agent, db, "dup-on（产品代码，有查重层）" if dedup else "dup-off（对照：第④刀那版，无查重层）")


def drain(ui, sid=None):
    out = None
    for out in ui._respond(Q, sid):
        pass
    return out


def run_twice():
    """同一进程、同一个 OpsUI 连问两遍（D0 那两问的零成本版）。

    验的是离线闸第 5 节只能钉源码位置的那件事：**换题清零**。第一题熔断之后，类级那张
    登记表、挡下次数、熔断开关都得跟着换题一起清，interrupt_switch 也要由 agent.run()
    自己复位（agents.py:470）——否则第二问开局就被当成重复调用挡掉，或者一步就
    「Agent interrupted」。这一格只跑 dup-on 那一路（对照格没有查重层，谈不上清零）。
    """
    global EXEC
    EXEC = {}
    ui, agent, db = build(True)
    first = drain(ui)                                # 第一问：sid=None → 库里新开一条会话
    digest.last_yield = first                        # 先算第一问那一格，别让它读到第二问的屏
    cell1 = digest(ui, agent, db, "dup-on 第一问（同一格，账从 0 起）", 0, {})
    seq1 = OpsUI._run_seq
    sid = ui._sid
    skip, base = len(agent.memory.steps), dict(EXEC)
    n_base = len(ui.hist.load(sid))                   # 第二问的屏上起点：第一问那一串
    agent.model = ScriptModel()                       # 换一个假模型：剧本从头再放一遍
    out = drain(ui, sid)                              # 第二问：题面一字不改
    # 卡片序列只截第二问新长出来的那一段，不然「同一张卡两遍」会把第一问也算进来。
    digest.last_yield = (list(out[0])[n_base:], out[1])
    run_twice.seqs = (seq1, OpsUI._run_seq)
    return cell1, digest(ui, agent, db, "dup-on 连问两遍：第二问的账（第一问已减掉）", skip, base)


CHECKS = []


def chk(name, ok, detail):
    CHECKS.append((name, bool(ok), detail))
    return ok


def main():
    t0 = time.time()
    src = (ROOT / "my_ui.py").read_bytes()
    head = [
        "v1.8 ⑤ P1-a 重复调用检测与熔断 —— 零成本现场回放（假模型 + 真 OpsUI/agent/工具）",
        "跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_dup_replay.py",
        "起表时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "被测：my_ui.py sha1=%s 行数=%d" % (hashlib.sha1(src).hexdigest(), src.count(b"\n")),
        "剧本：run/v18_p0abc_live.out 第四节 11 条里的第 1~8 条（=21:06 的 run A 单轮，两条 New run 横幅之间）。"
        "按换题清零口径重走：第 3/4/8 步各挡一次，第 3 次恰落在第 8 步=max_steps 边界",
        "口径：token 是剧本假数，只能读次数与形状；stream_outputs=False，不含逐字 delta 上屏那一段；",
        "      「模型会不会真这么走」【未验证】，账户恢复后由 v18_run_live.py D0 补。",
        "",
    ]
    on_txt, on = run(True)
    off_txt, off = run(False)
    (tw1_txt, t1), (tw2_txt, t2) = run_twice()      # 同一格连问两遍：两问各一份账

    # A 组断言：这一份证据自己判对错，红了就不该写进 run/
    chk("A1 dup-on 模型调用 8 次（熔断掐掉了第 9 次）", on["model_calls"] == 8, "实得 %d" % on["model_calls"])
    chk("A2 dup-off 模型调用 9 次（用满 8 步后 _handle_max_steps_reached 再打一次）",
        off["model_calls"] == 9, "实得 %d" % off["model_calls"])
    chk("A3 dup-on ActionStep 8 步全在（熔断发生在步边界，不吞这一步的观察值）",
        on["action_steps"] == 8, "实得 %d" % on["action_steps"])
    chk("A4 dup-on 挡下 3 次重复（2 警告 + 1 熔断），落在第 %s 步" % on["dup_steps"],
        on["blocked"] == 3 and on["dup_steps"] == [3, 4, 8], "blocked=%s steps=%s" % (on["blocked"], on["dup_steps"]))
    chk("A5 dup-on 熔断只在第 8 步出现一次", on["fuse_steps"] == [8], "实得 %s" % on["fuse_steps"])
    chk("A6 dup-on 真执行 5 次 vs dup-off 8 次", on["executed"] == 5 and off["executed"] == 8,
        "on=%d off=%d" % (on["executed"], off["executed"]))
    chk("A7 档位分开：dup-on=dup_fused，dup-off=maxed",
        on["state"] == "dup_fused" and off["state"] == "maxed", "on=%s off=%s" % (on["state"], off["state"]))
    chk("A8 状态条 class 带上 st-dup_fused（⛔ 那一档没被「步数用满」吞掉）",
        "st-dup_fused" in on["state_cls"], "实得 %s" % on["state_cls"])
    chk("A9 收尾气泡：on 认「重复熔断」，off 那一格不带这五个字",
        "重复熔断" in on["title"] and "重复熔断" not in off["title"],
        "on=%r off=%r" % (on["title"], off["title"]))
    chk("A10 dup-on 没交出最终答案（不是靠答案收的场），dup-off 是靠答案收的",
        (not on["answered"]) and off["answered"],
        "on=%s off=%s" % (on["answered"], off["answered"]))
    chk("A10b 熔断那一步的卡片画出来了（屏上有 ⛔ 那一档，不是只有收尾气泡）",
        any("⛔" in t and "第 8 步" in t for t in on["card_titles"]),
        " | ".join(on["card_titles"][-3:]))
    chk("A11 两格都落了库（messages>0 且 memory=1）",
        on["db"][0] > 0 and on["db"][1] == 1 and off["db"][0] > 0 and off["db"][1] == 1,
        "on=%s off=%s" % (on["db"], off["db"]))
    # 对照格打标记只打在副本上，模块级单例必须干净——否则下一格、下一次进程外复用都会被污染
    import my_coding_agent

    mods = {n: t for n, t in vars(my_coding_agent).items() if isinstance(t, BaseTool)}
    leak = [n for n, t in mods.items() if getattr(t, "_opsui_dedup", False) or getattr(t, "_opsui_gated", False)]
    chk("A12 模块级工具没被竖过幂等标记（查 %d 只：%s）" % (len(mods), ",".join(sorted(mods))),
        not leak and len(mods) >= 5, "脏的: %s / 查到 %d 只" % (leak or "无", len(mods)))
    # 连问两遍那一格：换题清零的**行为**证据（离线闸第 5 节只能钉源码位置）
    chk("A13 换题清零生效：第二问的形状与第一问逐格相同（挡下 3 次、落在 %s 步）" % t2["dup_steps"],
        t2["blocked"] == 3 and t2["dup_steps"] == t1["dup_steps"] == [3, 4, 8]
        and t2["executed"] == t1["executed"] == 5,
        "一：blocked=%s steps=%s exec=%d 二：blocked=%s steps=%s exec=%d"
        % (t1["blocked"], t1["dup_steps"], t1["executed"], t2["blocked"], t2["dup_steps"], t2["executed"]))
    chk("A14 第二问没被第一问的 interrupt 毒死：模型照打 8 次、8 步全在",
        t2["model_calls"] == 8 and t2["action_steps"] == 8,
        "model=%d steps=%d" % (t2["model_calls"], t2["action_steps"]))
    chk("A15 第二问的收尾档位与卡片仍走 dup_fused／⛔ 那一档",
        t2["state"] == "dup_fused" and any("⛔" in x and "第 8 步" in x for x in t2["card_titles"]),
        "%s / %s" % (t2["state"], " | ".join(t2["card_titles"][-2:])[:70]))
    chk("A16 第二问落在**同一条会话**上追加（D5 语义没被这一刀碰坏）",
        t2["db"][0] > t1["db"][0] and t2["db"][1] == 1, "库：%s → %s" % (t1["db"], t2["db"]))

    body = []
    for n, ok, detail in CHECKS:
        body.append("%s %s%s" % ("PASS" if ok else "FAIL", n, "" if ok else "  ← " + detail))
    text = "\n".join(head) + (
        "耗时 %.1f s\n\n" % (time.time() - t0)
        + off_txt + "\n\n" + on_txt + "\n\n" + tw1_txt + "\n\n" + tw2_txt
        + "\n\n（连问两遍那一格里，_run_seq 从 %d 走到 %d；类级登记表由 _stream_response 开局清零，"
          "第 5 节离线闸只钉了源码位置，这里给出它的行为证据。）\n" % (run_twice.seqs[0], run_twice.seqs[1])
        + "\n对照（差在哪，只有这些是结论。calls=memory 里登记的调用数，"
          "报错那几步只有 error、没有 tool_calls，口径见 agents.py:1436）：\n"
        + "\n".join("  %-26s on=%-10s off=%s" % (k, on[k], off[k])
                    for k in ("model_calls", "action_steps", "calls", "blocked", "executed",
                              "dup_steps", "fuse_steps", "answered", "state", "db"))
        + "\n\n断言 %d 条：%d 绿 %d 红\n" % (len(CHECKS), sum(c[1] for c in CHECKS), sum(not c[1] for c in CHECKS))
        + "\n".join(body) + "\n"
        + "\n顺带发现（本刀范围外，只记录不动手）：\n"
        + "  · 对照格「步数用满」那一路收尾时第 8 步的卡在屏上出现两遍（本格实得 %s）——\n"
        % (off["twice"] or "无")
        + "    agents.py:606-608 在 _handle_max_steps_reached 之后又 yield 了一次同一个 action_step。\n"
        + "    dup-on 格走不到那一句，本刀不受影响；要不要单开一张卡，等他点头。\n"
        + "  · 那一次补打的模型只认正文（agents.py:627-637 取 final_answer.content），tool_calls 不执行。\n"
    )
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print("[written] %s  %d 行 / %d B" % (OUT, text.count("\n"), OUT.stat().st_size))
    return 0 if all(c[1] for c in CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
