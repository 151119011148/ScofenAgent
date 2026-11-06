# -*- coding: utf-8 -*-
"""v2.0 补的这一档：服务商把整题拒掉时，界面上不能说成「你按了停止」。

起因是 2026-11-04 线上真撞到的一条：
  `Error while generating output: Error code: 400 - Access denied, please make sure your
   account is in good standing. ... #overdue-payment [Step 14: Duration 0.32 seconds]`
它以前落进 state="stopped"，卡片写「⏹ 已停止：AgentGenerationError」——可这一题没人按过 ■，
是服务商那头不接。和 D8（刷新页面 ≠ 已停止）、P1-a（绕圈熔断 ≠ 已停止）是同一个毛病第三次犯。

六组：
  A 分类器本身：命中今天这两句原文；顺着 __cause__ 找得到；**负控**——中断、否决计划、
    真正的实现错误、工具报错都必须返回 None（宁可少认一档，也不把别的报错盖成「账户问题」）。
  B 成套：STATE_LABEL 有词条、CSS 有配色、和 st-stopped 不同色、v1.8 那两档的字面锚点没被挪位搞坏。
  C 端到端：真 OpsUI 实例（临时库＋临时审计文件），把 _stream_response 换成「一句话都不 yield，
    直接抛今天这条异常」，看收尾卡片、状态格，以及**落库那一条就是这张卡**。
  D 负控端到端：老两档（■ 停止、否决计划）+ 实现错误，措辞不能被这一刀改坏。
  E 快照负控：.rollback/v1.8 那一份里这一层压根不存在。
  F P0 那一半（换 provider 只需要改配置）：AGENT_MODEL_ID/AGENT_BASE_URL 两个环境变量
    能把 model 对象整个换过去、不设时默认值逐字不变、配置只有一个来源、自检读的就是在跑
    的那个 client；构造期零网络（自检只在 launch 那一次），launch 的结论挂进「模型」那一格。

跑法：smolagents/.venv/bin/python 验收脚本/v2.0/v20_test_model_refusal.py
产物：run/v20_test_model_refusal.out
退出码 0 = 全绿。除了 F05 那两枪（各 1 token，自检 + 直调互校），其余全程不打模型。
F05 不断「一定被拒」也不断「一定通」——账户状态 11-06 已经翻过一次脸（见那一段的注释），
它断的是这两枪说的是同一句话。
"""
import pathlib
import sys
import tempfile
import types

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

TMP = pathlib.Path(tempfile.mkdtemp(prefix="v20-refusal-"))
import os  # noqa: E402

os.environ["AGENT_AUDIT_PATH"] = str(TMP / "audit.jsonl")   # 测试流量不进 .agent-audit.jsonl
import my_audit  # noqa: E402

import my_mcp  # noqa: E402
import my_ui  # noqa: E402

my_ui.DB_PATH = TMP / "hist.sqlite3"                        # 不把测试会话写进他的真历史库
AUDIT = TMP / "audit.jsonl"
my_audit.AUDIT_PATH = AUDIT
from smolagents import AgentError  # noqa: E402
from smolagents.utils import AgentGenerationError  # noqa: E402
from my_agent import agent  # noqa: E402
import my_agent  # noqa: E402  F 段读的是它的配置面（MODEL_ID / BASE_URL / model_preflight）
from my_ui import OpsUI, STATE_LABEL, model_refusal  # noqa: E402

FAIL = []
N = 0
UI = None
# AgentError.__init__ 要一个能 log_error 的 logger（utils.py:96），这里只记账不打屏
LOG = types.SimpleNamespace(log_error=lambda *a, **k: None)

# 今天线上真拿到的两句原文（逐字照抄，不做美化）
ARREARS = ("Error while generating output:\nError code: 400 - Access denied, please make sure "
           "your account is in good standing. For details, see: "
           "https://help.aliyun.com/zh/model-studio/error-code#overdue-payment")
RATELIMIT = ("Error while generating output:\nError code: 429 - You have exceeded your current "
             "request limit. For details, see: https://help.aliyun.com/zh/model-studio/error-code#rate-limit")


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-48s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


# ---- A 分类器 ----------------------------------------------------------------
ok("A01 今天那句 400 认得", (hit := model_refusal(AgentGenerationError(ARREARS, LOG))) is not None
   and "Access denied" in hit, (hit or "")[:56])
ok("A02 429 限流也认（同一档：服务商不接，不是代码错）",
   bool(model_refusal(AgentGenerationError(RATELIMIT, LOG))))
wrapped = None
try:
    try:
        raise ValueError(ARREARS)
    except ValueError as inner:
        raise AgentGenerationError("Error while generating output:", LOG) from inner
except AgentGenerationError as e:
    wrapped = e
ok("A03 顺着 __cause__ 找得到（框架那句是包装过的）",
   "Access denied" in (model_refusal(wrapped) or ""), (model_refusal(wrapped) or "")[:50])
ok("A04 负控：■ 停止抛的那句返回 None（仍然是「已停止」）",
   model_refusal(AgentError("Agent interrupted.", LOG)) is None)
ok("A05 负控：否决计划返回 None（走 plan_denied 那一档）",
   model_refusal(my_ui.PlanDeniedError("计划未获批准", LOG)) is None)
ok("A06 负控：真·实现错误返回 None（解析炸了不能算账户问题）",
   model_refusal(AgentGenerationError("Error while generating output:\nKeyError: 'content'", LOG)) is None)
ok("A07 负控：工具自己的报错返回 None",
   model_refusal(AgentError("Error executing tool: divide by zero", LOG)) is None)
ok("A08 命中就压成一行并限长（卡片不被 5KB 正文撑爆）",
   len(model_refusal(AgentGenerationError(ARREARS + "\n" + "x" * 9000, LOG))) <= 400
   and "\n" not in model_refusal(AgentGenerationError(ARREARS + "\n" + "x" * 9000, LOG)))
cyc = AgentError("KeyError: content", LOG)
cyc.__cause__ = cyc  # 人为造一个环：不命中的串要能在第二次停住，不能转圈把界面钉死
ok("A09 __cause__ 成环也不转圈（返回 None，不是挂死）", model_refusal(cyc) is None)

# ---- B 成套：词条、配色、老锚点 ----------------------------------------------
SRC = pathlib.Path(my_ui.__file__).read_text(encoding="utf-8")
ok("B01 状态档有词条", STATE_LABEL["model_refused"] == "模型侧拒绝")
ok("B02 这一档的字不等于「已停止」也不等于「已中断」",
   STATE_LABEL["model_refused"] not in (STATE_LABEL["stopped"], STATE_LABEL["interrupted"]))
ok("B03 状态条有独立配色", "#statusbar.st-model_refused .pill-state i" in SRC)
ok("B04 配色和 st-stopped 那个红不是同一个色",
   "st-model_refused .pill-state i { color: #db61a2; }" in SRC
   and "st-stopped .pill-state i { color: #f85149; }" in SRC)
ok("B05 v1.8 的收尾锚点行没被挪位改坏（v18_drill_p1a 的字面断言）",
   'state = "plan_denied" if denied else ("dup_fused" if fused else "stopped")' in SRC)
ok("B06 dup_fused / plan_denied 两条 CSS 仍在", "st-dup_fused" in SRC and "st-plan_denied" in SRC)
ok("B08 收尾分档在代码里只有一处（这一刀没把它复制成两份）",
   SRC.count('state = "plan_denied" if denied else') == 1
   and SRC.count('state = "model_refused"') == 1, "三选一 1 处 / 新档 1 处")
ok("B07 指纹表只在异常串上判：全项目就定义 1 处、用 1 处", SRC.count("MODEL_REFUSAL_MARKS") == 2,
   str(SRC.count("MODEL_REFUSAL_MARKS")))


# ---- C/D 端到端 --------------------------------------------------------------
def boom(exc):
    """一句话都不 yield，直接抛——模拟「第一次模型调用就被拒」。"""
    if False:
        yield
    raise exc


def drive(exc, question):
    """把真 OpsUI 的 _stream_response 换成 boom(exc)，跑完 _respond 取最后一帧。

    为什么不走真 agent：这一档的判据全在异常文本上，真跑一次要花钱且今天根本跑不动；
    _respond 的收尾（卡片、状态格、落库）是这一刀真正改的地方，必须用真实例测。
    """
    global UI
    if UI is None:
        UI = OpsUI(agent, file_upload_folder=str(TMP))
    UI._stream_response = lambda msg, hist: boom(exc)
    sid = UI.hist.ensure(None)
    frames = list(UI._respond(question, sid))
    msgs = frames[-1][0]
    card = msgs[-1]
    return {
        "state": UI._state,
        "cls": UI._status_html(UI._state),
        "title": getattr(card, "metadata", {}).get("title", ""),
        "card": getattr(card, "content", ""),
        "n_msgs": len(msgs),
        "saved": [getattr(m, "content", "") for m in UI.hist.load(sid)],
        "saved_title": getattr(card, "metadata", {}).get("title", ""),
    }


r = drive(AgentGenerationError(ARREARS, LOG), "测试：账户拒收时界面该怎么写")
ok("C01 状态落在 model_refused，不是 stopped", r["state"] == "model_refused", r["state"])
ok("C02 状态条 class 带的就是这一档", 'class="st-model_refused"' in r["cls"], r["cls"][-64:])
ok("C03 状态格那一格写的是「模型侧拒绝」", "模型侧拒绝" in r["cls"])
ok("C04 卡片是 🔒 那一档，不是 ⏹", r["title"].startswith("🔒"), r["title"])
ok("C05 卡片明说不是人按的停止", "不是你按了 ■" in r["card"], r["card"][:64].replace("\n", " "))
ok("C06 卡片留着原文（那句里自带厂商的排障链接）",
   "Access denied" in r["card"] and "overdue-payment" in r["card"])
ok("C07 卡片给出要动的两处（账户状态 / key+MODEL_ID）",
   "服务商控制台" in r["card"] and "MODEL_ID" in r["card"] and ".env" in r["card"])
ok("C08 卡片不许诺「什么都没发生」：已批过的工具不回滚这句在", "不会回滚" in r["card"])
ok("C09 收尾卡片进了历史库（不只是屏幕上的临时帧）",
   any("模型侧拒绝" in x and "Access denied" in x for x in r["saved"]), str(len(r["saved"])))
ok("C10 429 那一枪同样落进这一档", drive(AgentGenerationError(RATELIMIT, LOG), "测试：限流")["state"]
   == "model_refused")

r2 = drive(AgentError("Agent interrupted.", LOG), "测试：按停止")
ok("D01 按 ■ 停止仍然是 ⏹ 已停止", r2["state"] == "stopped" and r2["title"].startswith("⏹"),
   "%s · %s" % (r2["state"], r2["title"]))
r3 = drive(AgentGenerationError("Error while generating output:\nKeyError: 'content'", LOG),
           "测试：实现错误")
ok("D02 实现错误仍然是 ⏹ 已停止（没被误判成账户问题）",
   r3["state"] == "stopped" and "模型侧拒绝" not in r3["card"], r3["state"])
r4 = drive(my_ui.PlanDeniedError("计划未获批准：超时未批", LOG), "测试：否决计划")
ok("D03 否决计划仍然是 ✖ 计划未批准", r4["state"] == "plan_denied" and r4["title"].startswith("✖"),
   "%s · %s" % (r4["state"], r4["title"]))
ok("D04 拒收这一档不吃 ■ 停止的旗（两档各写各的）",
   r["state"] == "model_refused" and r2["state"] == "stopped")

# ---- F P0 那一半：换 provider 是改配置，不是改代码；起界面时自己会验 ------------
import subprocess  # noqa: E402

PROBE = ("import sys; sys.path.insert(0, '/Users/gaoying/Desktop/study/ai学习/smolagents');"
         "import my_agent;"
         "print(my_agent.MODEL_ID, my_agent.BASE_URL);"
         "print(my_agent.agent.model.model_id, my_agent.agent.model.client.base_url)")
env_sw = dict(os.environ, AGENT_MODEL_ID="deepseek-chat",
              AGENT_BASE_URL="https://api.deepseek.com/v1")
r_sw = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True,
                      env=env_sw, timeout=180)
env_def = {k: v for k, v in os.environ.items()
           if k not in ("AGENT_MODEL_ID", "AGENT_BASE_URL", "AGENT_TEMPERATURE")}
r_def = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True,
                       env=env_def, timeout=180)
ok("F01 设了 AGENT_MODEL_ID/AGENT_BASE_URL 就整个换过去（含活 model 对象）",
   "deepseek-chat https://api.deepseek.com/v1" in r_sw.stdout.replace("'", "")
   and r_sw.stdout.count("deepseek-chat") == 2, r_sw.stdout.strip()[:110] or r_sw.stderr[-200:])
ok("F02 不设就是原来的默认值（行为逐字不变）",
   "qwen-plus https://dashscope.aliyuncs.com/compatible-mode/v1" in r_def.stdout
   and r_def.stdout.count("qwen-plus") == 2, r_def.stdout.strip()[:100])
ok("F03 只有一个来源：my_agent 不再自己硬编码第二份",
   "dashscope.aliyuncs.com" not in SRC.split("from my_agent import")[0]
   and pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/my_agent.py")
   .read_text(encoding="utf-8").count("dashscope") == 0
   and my_agent.MODEL_ID == my_agent.agent.model.model_id
   and str(my_agent.agent.model.client.base_url).rstrip("/") == my_agent.BASE_URL.rstrip("/"),
   "my_agent 里 0 处 dashscope 字面量，且活 model 对象 == 那两个常量")
ok("F04 自检读的就是界面在跑的那个 client 对象（不是新拼一个）",
   my_agent.model is my_agent.agent.model and hasattr(my_agent.agent.model, "client"))

# 尺子换了口径，理由记在这儿：11-04 那一版 F05 断的是「当前配置必被拒」，因为那天账户确实欠着。
# 11-06 实测把它打脸了——qwen3.5-omni-plus 一发 1-token 通了（1.13s），同一句 20 分钟后又回 400，
# 短信到：那只「因欠费 0.04 元累计 0.05 元已停止服务」。也就是说**通不通是会变的**，
# 拿某一天的结论当断言，第二天就会自己翻红。现在断的是不随账户状态变的东西：
# 自检的结论 == 同一发 1-token 直接调用的结论（要么都说通，要么都说拒，且拒的是同一句）。
exc = my_agent.model_preflight()
try:
    my_agent.agent.model.client.chat.completions.create(
        model=my_agent.agent.model.model_id,
        messages=[{"role": "user", "content": "ping"}], max_tokens=1)
    direct = None
except Exception as e:  # noqa: BLE001
    direct = e
ok("F05 自检和直接开一枪说的是同一句话（状态怎么变都跟着，不写死某一天的结论）",
   (exc is None) == (direct is None) and
   (exc is None or " ".join(str(exc).split())[:120] == " ".join(str(direct).split())[:120]),
   "自检=%s · 直调=%s" % ("通" if exc is None else type(exc).__name__,
                          "通" if direct is None else type(direct).__name__))
print("    当前状态：%s" % ("✓ 接单（%s）" % my_agent.agent.model.model_id
                           if exc is None else "🔒 拒 · " + (model_refusal(exc) or str(exc))[:70]))

# 构造期必须零网络：把自检换成一颗会炸的雷，构造 OpsUI 不该碰到它
_saved = my_agent.model_preflight
my_agent.model_preflight = lambda: (_ for _ in ()).throw(AssertionError("构造期不许发请求"))
try:
    ui2 = OpsUI(agent, file_upload_folder=str(TMP))
    ok("F06 __init__ 一条网络都不发（自检不在那条路上）", ui2._model_note == "", repr(ui2._model_note))
except AssertionError as e:
    ok("F06 __init__ 一条网络都不发（自检不在那条路上）", False, "构造期被叫到：" + str(e))
finally:
    my_agent.model_preflight = _saved

# launch 必须叫它：把 gradio 的 launch 换成假的，看结论落不落进「模型」那一格。
# 两个分支各喂一个**固定的**返回值（拒 / 通），不拿 F05 那个随账户状态变的结果——
# 否则账户哪天恢复了这一条就自己翻红，而它想证的只是「launch 叫了自检、结论进了那一格」。
calls = []
拒 = AgentGenerationError(ARREARS, LOG)
my_agent.model_preflight = lambda: (calls.append(1), 拒)[1]
_gr_cls = OpsUI.__mro__[1]          # GradioUI：launch 的真身在这层
_gr = _gr_cls.launch
_gr_cls.launch = lambda self, *a, **k: "fake-launch"
try:
    got = ui2.launch(share=False)
    ok("F07 launch 打自检并把结论挂进状态格（拒的那一支）",
       calls == [1] and got == "fake-launch" and ui2._model_note == " 🔒拒"
       and "🔒拒" in ui2._status_html("idle"), "%s · %s" % (calls, ui2._model_note))
finally:
    _gr_cls.launch = _gr
    my_agent.model_preflight = _saved
# 通的那一支：喂 None，后缀必须是 " ✓"（这一支同样不许碰账户状态）
calls2 = []
my_agent.model_preflight = lambda: (calls2.append(1), None)[1]
_gr_cls.launch = lambda self, *a, **k: "fake-launch"
try:
    ui2.launch(share=False)
finally:
    _gr_cls.launch = _gr
    my_agent.model_preflight = _saved
ok("F07b 自检说通就写 ✓（这一支不许冒出 🔒）",
   calls2 == [1] and ui2._model_note == " ✓" and "🔒" not in ui2._status_html("idle"),
   ui2._model_note)
ok("F08 没起过服务就没有后缀（离线套件的「模型」格口径不变）",
   UI._model_note == "" and "🔒" not in UI._status_html("idle"))
# 尺子和 E 段同一份：v1.8 最后一版没被演练覆盖的整版（after-p0abc）。
old_agent_src = pathlib.Path(
    "/Users/gaoying/Desktop/study/ai学习/smolagents/.rollback/v1.8/after-p0abc/my_agent.py"
).read_text(encoding="utf-8")
ok("F09 负控：v1.8 快照里的 my_agent.py 既没有自检，模型配置也只能改代码",
   "model_preflight" not in old_agent_src and "AGENT_MODEL_ID" not in old_agent_src
   and "dashscope" in old_agent_src,
   "%d 行 · 硬编码 BASE_URL=%s" % (old_agent_src.count("\n"), "dashscope" in old_agent_src))

# ---- E 快照负控 --------------------------------------------------------------
# 尺子本来想用 after-p1a（v1.8 最后一版），但今天跑 v18_drill_p1a.py 之后那份已经等于现场
# （它的 snapshot() 是 cp 现场 → 快照目录，见该脚本 78-82 行；损害与处置写在 22:40 那一轮的报告里）。
# 现在用仍然完整的 **after-p0abc**：它是 v1.8 里最后一份没被演练覆盖的整版，
# 断言的口径跟着改成「④ 那一版没有 v2.0 的这三样」——dup_fused 是 P1-a 加的，
# 不在这一组的证明范围里（它由 v18_test_dup.py 的 10a-10e 用同一份快照继续证）。
old_src = (pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/.rollback/v1.8/after-p0abc/my_ui.py")
           .read_text(encoding="utf-8"))
ok("E00 尺子完整：after-p0abc 与现场不同版",
   old_src != SRC and "model_refusal" not in old_src, "%d 行 vs 现场 %d 行"
   % (old_src.count("\n"), SRC.count("\n")))
ok("E01 那一版没有分类器", "model_refusal" not in old_src)
ok("E02 那一版没有这一档", "model_refused" not in old_src)
ok("E03 那一版没有这组指纹", "MODEL_REFUSAL_MARKS" not in old_src)
ok("E04 那一版没有第四色", "st-model_refused" not in old_src)
# 尺子换了两次，理由都写在被换掉的那一版里：
#   原来比的是「after-p1a == 现场」，那是 22:29 覆盖事故刚过时抓到的现行——现场一直在改，
#   这个等式今天已经不再成立，断一条会随现场漂移自己翻红的东西没有意义。
#   现在断的是不随现场动的事实：那份快照里带着 v2.0 才有的 _mcp_pill（A1 那一刀），
#   v1.8 的 my_ui.py 里不可能有它——所以它确实是现场副本，不是历史。
_a1 = (pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/.rollback/v1.8/after-p1a/my_ui.py")
       .read_text(encoding="utf-8"))
ok("E05 after-p1a 那份是现场副本，不是 v1.8 历史（不得当尺子用）",
   "_mcp_pill" in _a1 and "def _mcp_pill" in _a1,
   "_mcp_pill %d 处 / %d 行（v1.8 那版没有这只方法）" % (_a1.count("_mcp_pill"), _a1.count("\n")))

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for x in FAIL:
    print("  FAIL:", x)
audit_lines = len(AUDIT.read_text(encoding="utf-8").splitlines()) if AUDIT.exists() else 0
print("临时库 %d 字节 · 测试审计行 %d 条 · 测试流量没进真审计文件=%s"
      % (my_ui.DB_PATH.stat().st_size, audit_lines,
         not (pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/.agent-audit.jsonl").exists())))
my_mcp.detach(UI._mcp)
sys.exit(0 if not FAIL else 1)
