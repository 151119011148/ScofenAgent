import os
from math import inf
from pathlib import Path

from dotenv import load_dotenv

from smolagents import OpenAIServerModel, Tool, ToolCallingAgent

from my_coding_agent import (
    BASE_URL,
    MODEL_CLIENT_KWARGS,
    MODEL_GENERATION_KWARGS,
    MODEL_ID,
    grep_files,
    list_dir,
    read_file,
    run_python,
    write_file,
)

load_dotenv(Path(__file__).resolve().parent / ".env")

# 2026-11-04：这两个常量原来在这里又硬编码了一遍（和 my_coding_agent 那份同样的字面量）。
# 现在只有一个来源（my_coding_agent，可被 .env 的 AGENT_MODEL_ID / AGENT_BASE_URL 覆盖），
# 这里只 import。换服务商不用改代码：`.env` 里加两行就行——
#     AGENT_BASE_URL=https://api.deepseek.com/v1
#     AGENT_MODEL_ID=deepseek-chat

# P0-4：计划可见的地基。框架只在 planning_interval 不为 None 时才产出 PlanningStep
# （agents.py:550-552：第 1 步必出，之后每 interval 步再出一次；step_number 每轮 run 从 1 起，
# 所以「第 1 步」= 每次提问都先规划一遍）。
# 8 = 和 max_steps 同高，所以**每题恰好一份**计划、题内不重规划：下一次落在第 9 步，
# 而 `while step_number <= max_steps` 在第 9 步之前就退出了。
# 设 None 就把这一刀整个关掉：一题一次规划调用都不发，回到 v1.8 之前的行为。
# 代价（同一道 12 日行情题、同一个 qwen-plus，各跑一遍，实测见
# 验收脚本/v1.8/run/v18_plan_probe.out——**单题样本，只当量级看**）：
#   关：7.1s、in 5,260 / out 262 token、2 个 ActionStep、PlanningStep 0 条
#   开：40.1s、in 13,591 / out 1,713 token，PlanningStep 1 条；其中规划那一次单独
#       in 1,188 / out 1,458、耗时 32.9s（占那 40.1s 里的 32.9s），计划正文 6,195 字符；
#       后面每一步的 input 都被这段计划抬高：单步 in 3,957 / 4,138 / 4,308
#       对关着的 2,463 / 2,797。
#       （开的那组只走到第 3 步就交了答案，所以这一跑看不出「题内重规划」长什么样；
#        interval=8 下第 9 步本来就够不着，重规划这条路由 max_steps 直接封掉。）
PLANNING_INTERVAL = 8


class MaxDrawdownTool(Tool):
    name = "max_drawdown"
    description = "计算按时间升序的收盘价序列的最大回撤，返回百分比和发生区间。"
    inputs = {"prices": {"type": "array", "description": "按时间升序排列的收盘价列表"}}
    output_type = "string"

    def forward(self, prices):
        peak, mdd, peak_i, worst = -inf, 0.0, 0, (0, 0)
        for i, p in enumerate(prices):
            if p > peak:
                peak, peak_i = p, i
            dd = (p - peak) / peak
            if dd < mdd:
                mdd, worst = dd, (peak_i, i)
        return (
            f"最大回撤 {mdd:.2%}，区间 第{worst[0] + 1}~{worst[1] + 1}个交易日"
            f"（{prices[worst[0]]:.2f} -> {prices[worst[1]]:.2f}）"
        )


class AnnualizedVolTool(Tool):
    name = "annualized_volatility"
    description = "由收盘价序列计算日收益的年化波动率，返回百分比。"
    inputs = {"prices": {"type": "array", "description": "按时间升序排列的收盘价列表"}}
    output_type = "string"

    def forward(self, prices):
        rets = [
            (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
        ]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        vol = (var**0.5) * (252**0.5)
        return f"年化波动率 {vol:.2%}（基于 {len(rets)} 个日收益）"


# B1：显式超时。改前这里就是 `OpenAIServerModel(model_id=..., api_base=...)` 一行，
# 于是 openai SDK 的默认 read=600s 生效，挂住的请求最长占住半小时（实测与推理链见
# my_coding_agent.py 里 MODEL_TIMEOUT_S 那段注释）。框架层的 retryer 只重试 429，帮不上这个忙。
# P1-4：同一行再加 temperature=0（理由和证据在 MODEL_GENERATION_KWARGS 那段）。
model = OpenAIServerModel(model_id=MODEL_ID, api_base=BASE_URL, client_kwargs=MODEL_CLIENT_KWARGS,
                          **MODEL_GENERATION_KWARGS)

agent = ToolCallingAgent(
    tools=[MaxDrawdownTool(), AnnualizedVolTool(),
           read_file, list_dir, grep_files, write_file, run_python],
    model=model,
    max_steps=8,
    # P0-4：见文件头那段注释。命令行跑 `python my_agent.py` 走的也是这一个 agent 对象，
    # 所以下面 __main__ 那条演示同样会先出一份计划（多一次模型调用，量级见文件头）。
    planning_interval=PLANNING_INTERVAL,
    name="smolagents",
    # P0-b：能力穷举。注意这个字段**模型读不到**——顶层 ToolCallingAgent 的 description 只在
    # describe() 里用，那是给 managed（子）agent 的；实测 `'读代码' in agent.system_prompt` → False。
    # 21:06 那轮死循环发生在**这个** agent 上，所以这里也一并写全（它比 my_coding_agent 多两只手：
    # max_drawdown、annualized_volatility）。真正给模型读的穷举在各工具 docstring 和 guarded() 报错里。
    description=(
        "行情指标计算（max_drawdown、annualized_volatility）＋ 在 ai学习 这一个根目录里读代码、"
        "搜代码、跑验证（read_file、list_dir、grep_files、write_file 只落 .agent-staging、"
        "run_python 在沙箱里跑且拒绝删除类调用）。没有删除／移动／重命名／访问网络／"
        "写根外路径的能力——根外要用户自己在终端执行。"
    ),
    stream_outputs=True,
)


# 一发 1 token 的自检：现在这套 key／provider 到底接不接单。通了返回 None，否则原异常。
# 为什么写成 # 注释而不是 docstring：v1.8 的守卫 v18_test_dup.py 9a 把这两个文件里
# **任何函数 docstring** 都当提示词面（收窄到 @tool 会漏掉 forward 那两只工具的 description，
# 实测试过，守卫反而变松），所以这个模型永远读不到的辅助函数，说明写在外面。
#
# 为什么值得花这一枪（实测 0.34 秒、几十个 token）：账户级拒绝是**整题开工前**就能知道的
# 事实，而它平时要等你打完一句话、走完规划那一次调用才现形——那一枪同样是 400，白等。
# 2026-11-04 就是这样：`400 Access denied … #overdue-payment`，换了一把 key 之后
# 同一句、同一个 0.34 秒（`models.list` 却还是通的，183 只）——拒绝跟着**账户**走，不跟着 key 走。
#
# 读的是 `agent.model.client` 这个活对象，不是新拼一个 OpenAI()：要验的就是他屏幕上那条路，
# 连 B1 那个 60 秒 read 超时一起验。调用方（my_ui.launch）只该在**起界面**时打这一枪：
# 离线套件全都 import 这个模块，谁都不想在构造 OpsUI 时往外发请求。
def model_preflight() -> Exception | None:
    try:
        agent.model.client.chat.completions.create(
            model=agent.model.model_id,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        return None
    except Exception as exc:  # noqa: BLE001 —— 自检的结论就是要把原样带回去给界面分类
        return exc


if __name__ == "__main__":
    prices = [12.80, 13.42, 13.95, 13.61, 12.90, 12.05, 11.48, 11.90, 12.35, 12.02, 12.66, 13.10]

    task = (
        f"某只股票连续 12 个交易日的收盘价是 {prices}。"
        "先分别算出最大回撤和年化波动率，再判断这个回撤属于什么水平，"
        "并给出一句基于这两个数字的结论。结论必须引用工具返回的具体数值。"
    )

    result = agent.run(task)

    print("\n" + "=" * 60)
    print("最终答案:", str(result))
    print("=" * 60)
    steps = agent.memory.steps
    print("步数:", len(steps))
    for i, step in enumerate(steps, 1):
        print(f"--- step {i}: {type(step).__name__}")
        print(str(step)[:400])
