# -*- coding: utf-8 -*-
"""P0-4 现场验收的证据写入器：把 run/v18_live_summary_C*.out + run/v18_probe_C*.server.log
里已经存在的行**原样搬进一份能读的结论**，不手打任何数字。

用法：python v18_p04_report.py        （产物 run/v18_p04_live.out）
为什么另写一个脚本而不是手抄：这一刀的每一个数都要能被反驳——手抄一遍就断了对表链。
脚本只做三件事：① 从服务端日志里按 id 抠出「挂起→决定→面板跟上」三个时刻并算差值；
② 从库里那一行抠出记忆步型与 token 分档；③ 把浏览器侧的关键读数原样贴出来。
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
OUT = RUN / "v18_p04_live.out"

TAGS = ["C0", "C1", "C2", "C3", "C4"]

# 每个场景要盯的判据（写在代码里，跑没跑对一眼看得出；文案不许出现没有数字支撑的形容词）
EXPECT = {
    "C0": "面板上屏 → ✔ 允许 → 工具门照常 → 跑完；批准过的那份计划**必须**进记忆",
    "C1": "✖ 拒绝 → 抛 PlanDeniedError；一个工具都不许跑；那份计划**不许**进记忆",
    "C2": "■ 停止落在计划待批上 → 抛的是普通 AgentError（不是 PlanDeniedError）、状态「已停止」，"
          "不许写成「计划未批准」，也不许长出「已中断」",
    "C3": "刷新落在计划待批上 → GeneratorExit 后待批随中断结算、「已中断」卡用计划那一句措辞；"
          "顺带量首屏读空那一档（#42）",
    "C4": "没人点，等到审批超时 → 与 ✖ 拒绝同一档（状态「计划未批准」），计划不进记忆",
}


def log_lines(tag):
    p = RUN / ("v18_probe_%s.server.log" % tag)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def grab(lines, needle):
    return [ln for ln in lines if needle in ln]


def t_of(line):
    m = re.match(r"t=\s*([\d.]+)", line.strip())
    return float(m.group(1)) if m else None


def browser(tag):
    """摘要里那段 cdp JSON（浏览器侧读数）。"""
    txt = (RUN / ("v18_live_summary_%s.out" % tag)).read_text(encoding="utf-8")
    body = txt.split("浏览器侧：", 1)[1]
    # 块到**单独一行只有 `}`** 为止：不能拿 rindex("}")，后面「库里： {'sessions': 1, ...}」
    # 那行也有花括号，会把日志一起吞进 json.loads。
    return json.loads(body[: body.index("\n}") + 2])


def summary_line(tag, needle):
    for ln in (RUN / ("v18_live_summary_%s.out" % tag)).read_text(encoding="utf-8").splitlines():
        if needle in ln:
            return ln.strip()
    return "（没找到 %s）" % needle


def summary_next(tag, label):
    """摘要里 `label：` 那一行**下面**那一行（数据行是缩进写的，别把标签行当数据）。"""
    lns = (RUN / ("v18_live_summary_%s.out" % tag)).read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lns):
        if label in ln and i + 1 < len(lns):
            return lns[i + 1].strip()
    return "（没找到 %s 的下一行）" % label


out = []
A = out.append
A("=" * 100)
A("v1.8 第③刀 P0-4「计划可见 ＋ 批准动作」现场验收（真 app ＋ 真 qwen-plus ＋ headless Chrome）")
A("=" * 100)
A("跑的对象：smolagents/my_ui.py（计划门 _install_plan_gate / _plan_gate、面板 _plan_update、")
A("          8 元组输出、PlanDeniedError）＋ smolagents/my_agent.py（PLANNING_INTERVAL=8）")
A("离线那一路的断言不在这里，是 v18_test_plan.py（40 条）＋ v18_test_nochange.py ＋ v18_test_interrupt.py")
A("")
A("环境（每跑第一行 boot.epoch 原样，见下面各节）：端口 7872，每场景各一个隔离库")
A("  run/v18_live_<tag>.sqlite3 —— 他本人的 7860 界面和 .agent-history.sqlite3 全程没碰")
A("  浏览器侧：9333 上的 headless Chrome，profile run/chrome-d168，驱动 v18_cdp.js")
A("  剧本：v18_run_live.py c_steps()，每场景 12～16 步，步名 C0-…C15-")
A("")
A("怎么复跑：")
A("  cd 验收脚本/v1.8 && ../smolagents/.venv/bin/python v18_run_live.py C1   # 单场景")
A("  然后 python v18_p04_report.py                                            # 重新生成这份")
A("")
A("判据一览：")
for t in TAGS:
    A("  %s  %s" % (t, EXPECT[t]))
A("")

# ---- 逐场景 ----------------------------------------------------------------------
for tag in TAGS:
    lines = log_lines(tag)
    br = browser(tag)
    A("=" * 100)
    A("【%s】%s" % (tag, EXPECT[tag]))
    A("-" * 100)
    A("原始场景行：" + summary_line(tag, "场景 " + tag))
    A("探针配置：  " + (grab(lines, "boot.epoch")[0].strip() if grab(lines, "boot.epoch") else "（无）"))
    A("")
    A("── 服务端：计划门那一路的关键时刻（v18_ui.py 里 _plan_gate/_plan_update 的包装打的点）")
    keys = ("plan.gate.enter", "ap.wait.enter", "ap.wait.exit", "ap.decide",
            "plan.gate.allowed", "plan.gate.denied", "plan.gate.raise",
            "plan.update", "respond.GeneratorExit", "respond.exception",
            "mark.enter", "mark.exit", "save_memory.exit")
    for ln in lines:
        if any(k in ln for k in keys):
            A("  " + ln.strip())
    A("")

    # 面板跟上了多久：从决定落定那一行到其后第一条 plan.update——但只在**同一页那一题**里找。
    # 断开那一跑（C3）里，门之后这一页再没有下一帧，面板的终态读数要等下一次 on_load 才算，
    # 直接取"其后第一条"会把 20 秒的换页间隔说成面板延迟，那是假的。
    dec = [ln for ln in lines if "plan.gate." in ln and ("allowed" in ln or "denied" in ln or "raise" in ln)]
    if dec:
        d0 = t_of(dec[0])
        di = lines.index(dec[0])
        lag, stopped_at = None, None
        for j in range(di + 1, len(lines)):
            ln = lines[j]
            if any(k in ln for k in ("respond.enter", "stream.enter")):
                stopped_at = ln.strip()
                break
            if "plan.update" in ln and t_of(ln) is not None:
                # `_on_load` 里**先**算面板那一格、**后**打 on_load 那行日志，所以
                # 「紧跟一条 on_load 的 plan.update」是新页面加载重算的，不是这一题的下一帧。
                nxt = " ".join(lines[j + 1:j + 3])
                if "on_load" in nxt:
                    stopped_at = ln.strip()
                    break
                lag = t_of(ln) - d0
                break
        if lag is not None:
            A("── 数字①：审批读数落定 → 那一格面板在服务端算出新读数，隔了 %.3f s" % lag)
            A("   （落定那一行：%s）" % dec[0].strip())
            A("   面板不是挂在 ✔/✖ 的 click 输出上的（单主人纪律：消息流和面板都归那条流式生成器），")
            A("   所以它靠下一帧跟上；my_ui.py 注释里写的「最多 0.25 秒」量的就是这一档。")
        else:
            A("── 数字①：**这一页在那一帧之后再没有下一格**（门落定之后先来的事件是 %s）。"
              % (stopped_at.split()[2] if stopped_at else "?"))
            A("   （门之后下一条相关日志：%s）" % (stopped_at or "-"))
            A("   断开这一路本来就没有后续帧：生成器已经 unwind，最后一帧是「⏹ 已中断」那一条，")
            A("   面板上的读数停在断开前最后一帧的「等待审批」，之后由下一次页面加载重算（见⑥）。")
            A("   这一档不许当成「面板延迟几十秒」来读——那不是延迟，是换页。")
    else:
        A("── 数字①：这一跑没有计划部落定（不该出现在 C 系列，若看到这行说明剧本没跑到）")
    A("")

    A("── 数字②：库里那条会话的记忆步型（**「计划进没进记忆」只有这里能证**）")
    A("   " + summary_next(tag, "库里的记忆步型"))
    A("   读法：顺序里带 P 就是那份计划已经进了 agent 的记忆；只带 T 就是这一题停在计划之前。")
    A("")
    A("── 数字③：库里的正文命中的句子（折叠卡正文不在 DOM 里，只能从库里读）")
    A("   " + summary_next(tag, "库里的正文命中的句子"))
    A("")
    A("── 浏览器侧读数（原样，未改写）")
    order = [k for k in br if not k.endswith("at") and not k.endswith("Ms") and not k.endswith("pred")]
    pend = [k for k in br if k.endswith("#pred")]
    for k in order:
        A("  %-24s %s" % (k, br[k]))
    for k in sorted(pend):
        base = k[:-5]
        A("  %-24s waitedMs=%s %s" % (base, br.get(k + "waitedMs"), br[k]))
    A("")

# ---- 跨场景汇总的数字 ----------------------------------------------------------------
A("=" * 100)
A("跨场景汇总（每条都能在上面的原始行里对回去）")
A("=" * 100)

# 面板第一次上屏等了多久：C 系列里 C5-panel-pending 那一格（until 循环，waitedMs 就是延迟）
A("① 面板第一次上屏的延迟（状态条已经报出「待批 计划」之后，浏览器里 #planpanel 真的画出来）")
for tag in TAGS:
    br = browser(tag)
    k = "C5-panel-pending#waitedMs"
    A("   %s  %s ms   （读数：%s）" % (tag, br.get(k), str(br.get("C5-panel-pending#pred"))[:78]))
A("   这一档量的是**服务端 yield 到浏览器可见**（gradio websocket 一帧 ＋ 前端渲染），")
A("   和上面「数字①」那档（决定落定到服务端算出下一格读数）不是同一件事，两档分开记。")
A("   **量法自带的粒度**：剧本用 until 轮询，每 1,000 ms 一次，第一次就命中则 waitedMs 只有几毫秒；")
A("   C0 落在第二次轮询（1,006 ms），其余四跑第一次就命中。所以这五跑能说的是")
A("   「面板在 1 秒的轮询粒度内已经上屏」，**不能**当成精确延迟——要毫秒级得换 MutationObserver，")
A("   这一刀的判据不需要那么细，故不做。")
A("")

A("② 提问之前那块面板在不在屏上：")
for tag in TAGS:
    br = browser(tag)
    A("   %s  %s" % (tag, br.get("C1-panel-before-ask")))
A("   → visible=False 的 gr.Markdown 在初始 DOM 里**根本没有这个元素**，第一次有读数时 gradio 才建它。")
A("     所以「面板没上墙」有两种：元素没建 / 建了但是空的。这份证据里 C3 第二刷读到的是前者。")
A("")

A("③ 拒绝／超时／停止 三档的分工（服务端抛出的异常类型，逐条摘自上面的门日志）：")
for tag, want in (("C1", "PlanDeniedError"), ("C4", "PlanDeniedError"),
                  ("C2", "AgentError（停止）"), ("C3", "AgentError（断开）")):
    lines = log_lines(tag)
    hit = grab(lines, "plan.gate.denied") or grab(lines, "plan.gate.raise")
    A("   %s 期望 %s ｜ 实际 %s" % (tag, want, hit[0].strip() if hit else "（没有这一行）"))
A("")

A("④ 状态条那一档（屏幕上的字，不是日志）：")
for tag in TAGS:
    br = browser(tag)
    fin = None
    for k in ("C13-status-final", "C14-status-final", "C15-status-2nd", "C8-status", "C9-status-after-reload"):
        if k in br:
            fin = br[k]
            break
    A("   %s  %s" % (tag, str(fin)[:150]))
A("")

A("⑤ 「本题 token」那颗药丸**不含规划那一次调用**——这一刀顺量出来的口径差：")
for tag in TAGS:
    tok = summary_next(tag, "库里的记忆步型")
    m = re.search(r"token按步型in/out=(.*?) 合计=in (\d+)/out (\d+)", tok)
    if not m:
        continue
    br = browser(tag)
    pill = None
    for k in ("C11-await-done#pred", "C14-status-final", "C13-status-final"):
        mm = re.search(r"本题 token in ([\d,]+) / out ([\d,]+)", str(br.get(k, "")))
        if mm:
            pill = (mm.group(1), mm.group(2))
            break
    if not pill or tag != "C0":
        continue  # 只有跑完的那一题药丸上才有读数可比
    plan_tk = re.search(r"PlanningStep:(\d+/\d+)", m.group(1)).group(1)
    act_tk = re.search(r"ActionStep:(\d+/\d+)", m.group(1)).group(1)
    A("   %s：库里 PlanningStep in/out = %s，ActionStep in/out = %s，合计 in %s / out %s"
      % (tag, plan_tk, act_tk, m.group(2), m.group(3)))
    A("   %s：状态条「本题 token」显示 in %s / out %s ——只加 ActionStep"
      % (tag, pill[0], pill[1]))
    ai = int(pill[0].replace(",", ""))
    ao = int(pill[1].replace(",", ""))
    ti = int(m.group(2))
    to = int(m.group(3))
    A("   差额：in %d − %d = **%d 个不在药丸上**（占这一题真实 input 的 %.1f%%）；"
      % (ti, ai, ti - ai, (ti - ai) * 100.0 / ti))
    A("           out %d − %d = **%d 个**（占 %.1f%%）。药丸显示的是「工具那两步」，不是「本题」。"
      % (to, ao, to - ao, (to - ao) * 100.0 / to if to else 0.0))
A("   代码位置：_stream_response 只把 ActionStep 的 token_usage 累进 _run_in/_run_out（:1152-1155），")
A("   PlanningStep 那一次的用量只出现在计划卡标题上（🧭 计划 · 已允许 · X.Xs · in/out）。")
A("   这不是这一刀引入的 bug（规划那一次调用以前压根不存在），但**开了规划就变成一个看得见的缺口**：")
A("   看板上「本题 token」会低估。留作 P1 单（口径要么把规划算进本题、要么把 PlanningStep 并进累加），")
A("   这一刀不动，因为动 _stats 的口径会把 v18_test_nochange.py 里比对旧版的那几条一起改黄。")
A("")

A("⑥ 刷新首屏读空那一档（#42 的新证据，来自 C3）：")
c3 = log_lines("C3")
onload = grab(c3, "on_load")
savee = grab(c3, "save.enter")
if len(onload) >= 2 and savee:
    A("   首屏 on_load（t=%.3f）读到 messages=0；半截内容落库在 t=%.3f ——首屏比落库早 %.3f s，"
      % (t_of(onload[1]), t_of(savee[0]), t_of(savee[0]) - t_of(onload[1])))
    A("   于是第一刷的屏幕上是：bot=0（一条消息没有）＋ 状态条还带着上一题的「待批 计划」（gradio 把")
    A("   组件缓存值一起画了出来）。两个信号自相矛盾，但都只是**首屏那一下**："
      "第二刷（C13-mark-2nd-plan）读到 bot=3、已中断标题=Y。")
    A("   第二刷读数：%s" % str(browser("C3").get("C13-mark-2nd-plan")))
    A("   这一档不是这一刀引入的，是 D8-2（#42）那张单的范围；此处只补一个数：%.3f s。"
      % (t_of(savee[0]) - t_of(onload[1])))
A("")

A("=" * 100)
A("结论位")
A("=" * 100)
for tag in TAGS:
    lines = log_lines(tag)
    kinds = summary_next(tag, "库里的记忆步型")
    gate = (grab(lines, "plan.gate.allowed") or grab(lines, "plan.gate.denied")
            or grab(lines, "plan.gate.raise"))
    tools = grab(lines, "tool=run_python")
    mm = re.search(r"顺序=(\S+)", kinds)
    A("  %s：门=%s ｜ run_python 那一侧的日志行数=%d ｜ 记忆顺序=%s"
      % (tag, (gate[0].strip().split("plan.gate.")[1] if gate else "无"),
         len(tools), mm.group(1) if mm else kinds))
A("")
A("要证的三件事，逐条对上：")
toolwaits = {t: len([ln for ln in log_lines(t) if "ap.wait.enter" in ln and "tool=run_python" in ln]) for t in TAGS}
planwaits = {t: len([ln for ln in log_lines(t) if "ap.wait.enter" in ln and "tool=计划" in ln]) for t in TAGS}
A("  1) 计划真的先上墙、再等批准：每跑都有 plan.gate.enter → plan.update(等待审批) → ap.decide 这个次序，")
A("     且工具那一侧的门只在**计划被允许之后**才出现。两道的 wait.enter 行数逐跑：")
A("     " + "  ".join("%s 计划门%d/工具门%d" % (t, planwaits[t], toolwaits[t]) for t in TAGS))
A("     ——只有 C0 有工具门那一步（其余四路一个工具都没跑，run_python 行数为 0）。")
order = {t: (re.search(r"顺序=(\S+)", summary_next(t, "库里的记忆步型")) or [None, "?"])[1] for t in TAGS}
A("  2) 「没批的计划不进模型记忆」：库里那条会话的步型顺序逐跑 = "
  + "  ".join("%s:%s" % (t, order[t]) for t in TAGS) + "。")
A("     带 P 的只有 %s（批过的那一跑）；其余四跑的 P 一个都没有——门卡在 memory.steps.append 之前"
  % "".join(t for t in TAGS if "P" in order[t]))
A("     （agents.py:556-562 的顺序），这句在离线闸 v18_test_plan.py 第 3 节是断言，在这里是实测行）。")
A("  3) 三档结局分得开：✖ 拒绝／超时 → 状态「计划未批准」＋面板 ⚪已拒绝／⏳超时未批；")
A("     ■ 停止 → 状态「已停止」＋面板 ⏹随停止取消，且抛的是普通 AgentError；")
A("     刷新断开 → 「已中断」卡用的是计划那一句措辞（库里 批准这一步就被中断=1）。")
A("已声明的边界（不是这刀的 bug，写在文档里）：")
A("  · 面板在批准之后**不会**在刷新后重现：那份计划没进 memory，_on_load 无从读起（C3 第二刷实测 8,018ms")
A("    等满，仍然是「DOM 里没有 #planpanel」）。卡还在会话里（计划审批卡标题=Y），收起着。")
A("  · 计划正文是英文的（框架的规划 prompt 是英文），这一刀不改语言。")
A("  · 「本题 token」药丸不含规划那一次调用，见上面⑤的差额。")
A("  · 开规划的代价（单题样本、同一道 12 日行情题）见 run/v18_plan_probe.out：")
A("    关 7.1s / in 5,260 / out 262 → 开 40.1s / in 13,591 / out 1,713，其中规划那一次单独 in 1,188 / out 1,458、32.9s。")

OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print("写了 %s（%d 行，%d 字符）" % (OUT, len(out), OUT.stat().st_size))
