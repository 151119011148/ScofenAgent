# -*- coding: utf-8 -*-
"""P0-4 的基线：PlanningStep 到底会不会出现；出现的话长什么样、多贵。

工单原文（手册 §4 看板 P0-4 行）写着「本轮三条实测路都没触发过这个分支【未验证】」，
这一跑就是把那个【未验证】变成有档可查的数。

两次跑同一道题（要两个工具、两个数字，正好够多步），只差一个参数：
  A 组 planning_interval=None  ← 现在产品的形状（my_agent.py:54-62 没传这个参数）
  B 组 planning_interval=4     ← 框架里唯一会产出 PlanningStep 的开关

用法：smolagents/.venv/bin/python v18_plan_probe.py        （要打真模型，走百炼 Key）
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

from dotenv import load_dotenv  # noqa: E402

from my_agent import AnnualizedVolTool, MaxDrawdownTool  # noqa: E402  复用他那两个工具，别自己造价格解析
from my_coding_agent import grep_files, list_dir, read_file, run_python, write_file  # noqa: E402
from smolagents import OpenAIServerModel, ToolCallingAgent  # noqa: E402
from smolagents.memory import PlanningStep  # noqa: E402

load_dotenv("/Users/gaoying/Desktop/study/ai学习/smolagents/.env")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_ID = "qwen-plus"

PRICES = [12.80, 13.42, 13.95, 13.61, 12.90, 12.05, 11.48, 11.90, 12.35, 12.02, 12.66, 13.10]
TASK = (
    f"某只股票连续 12 个交易日的收盘价是 {PRICES}。"
    "先分别算出最大回撤和年化波动率，再判断这个回撤属于什么水平，"
    "并给出一句基于这两个数字的结论。结论必须引用工具返回的具体数值。"
)


def build(planning_interval):
    return ToolCallingAgent(
        tools=[MaxDrawdownTool(), AnnualizedVolTool(), read_file, list_dir, grep_files, write_file, run_python],
        model=OpenAIServerModel(model_id=MODEL_ID, api_base=BASE_URL),
        max_steps=8,
        planning_interval=planning_interval,
        name="计划基线探针",
        description="P0-4 基线：看 PlanningStep 会不会出现",
        stream_outputs=False,
    )


def report(tag, planning_interval):
    agent = build(planning_interval)
    t0 = time.time()
    try:
        answer = str(agent.run(TASK))
        err = None
    except BaseException as exc:  # 报错也要留档，不然只知道没跑完不知道为什么
        answer, err = "", "%s: %s" % (type(exc).__name__, str(exc)[:200])
    secs = time.time() - t0
    steps = agent.memory.steps
    plans = [s for s in steps if isinstance(s, PlanningStep)]
    print("### %s  planning_interval=%s" % (tag, planning_interval))
    print("  跑完 %.1fs ｜ 报错=%s" % (secs, err or "无"))
    print("  步骤序列（%d 步）: %s" % (len(steps), " → ".join(type(s).__name__ for s in steps)))
    print("  PlanningStep 条数: %d" % len(plans))
    for i, p in enumerate(plans, 1):
        print("  --- 计划 %d：timing=%s token=%s" % (i, getattr(p.timing, "duration", None), p.token_usage))
        print("      plan 正文 %d 字符:" % len(p.plan))
        for ln in p.plan.splitlines():
            print("        | %s" % ln[:110])
        print("      to_messages 喂给模型的字段: %s" % str(p.to_messages())[:220].replace("\n", "\\n"))
    ins = [s.token_usage.input_tokens for s in steps if getattr(s, "token_usage", None)]
    outs = [s.token_usage.output_tokens for s in steps if getattr(s, "token_usage", None)]
    print("  单步 token（逐步，不合并）in=%s out=%s" % (ins, outs))
    print("  合计 in=%d out=%d ｜ 平均输出 %d 字符" % (sum(ins), sum(outs), len(answer) // max(1, 1)))
    print("  最终答案: %s" % answer[:200].replace("\n", " "))
    print()
    return plans


if __name__ == "__main__":
    print("P0-4 基线：同一道题两次跑，只差 planning_interval。真模型，百炼 %s。\n" % MODEL_ID)
    a = report("A 组（现在的产品形状）", None)
    b = report("B 组（把开关打开）", 4)
    print("结论位：A 组 PlanningStep=%d 条 ｜ B 组=%d 条" % (len(a), len(b)))
