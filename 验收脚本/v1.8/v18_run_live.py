# -*- coding: utf-8 -*-
"""D8 基线②的运行器：真 app ＋ 真 qwen-plus，中途刷新页面，量「这一题到底落没落库」。

用法：python v18_run_live.py <B0|B1|B2|B3|B4|C0|C1|C2|C3|C4|D0>
      B0 对照：允许后跑完 ｜ B1 主测：挂在待批上时刷新页面 ｜ B2：挂在待批上时 SIGKILL 整个进程组
      B3：挂在待批上时 SIGINT（Ctrl-C） ｜ B4：挂在待批上时按 ■ 停止（第②刀的反向回归）
      C0～C4 是 P0-4（计划可见＋批准动作）那五跑：允许／拒绝／停止落在计划上／刷新落在计划上／超时
      D0 是 P1-a（重复调用检测与熔断）那一跑：21:06 原题面连问两遍，第一遍看熔断掐短、
            第二遍看登记表换题清零（和 ④ 的 A 格同条件：planning 在探针侧关掉）
      B 系列现在一律带 V18_PLANNING=off 起进程：开了规划之后每一题先过计划门，B4 按到的停止就不是
      工具审批那一路了，和当时的证据不是同一回事（产品里 planning_interval 仍是 8，没动）。
产物：run/v18_probe_<tag>.server.log（服务端，含 v18_ui.py 那几层包装打的点）
      run/v18_live_cdp_<tag>.out（浏览器侧每步时刻、状态条、气泡措辞命中）
      run/v18_live_summary_<tag>.out（两份对表 ＋ 库里的行数 ＋ 记忆步型 ＋ 正文命中的句子）

要起 smolagents 的 venv（有 gradio / openai / 百炼 Key），本机 python3 跑不了。
浏览器侧靠 9333 上的 headless Chrome（run/chrome-d168），先确认它活着。
"""
import base64
import json
import os
import pathlib
import signal
import sqlite3
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
RUN.mkdir(exist_ok=True)
PY = os.environ.get("V18_PY", "/Users/gaoying/Desktop/study/ai学习/smolagents/.venv/bin/python")
PORT = "7872"
URL = "http://127.0.0.1:%s" % PORT
Q = "用 run_python 打印 3*7 的结果，最后只回那个数字，不要重复调用工具"

NEWBTN = """(()=>Array.from(document.querySelectorAll('#sidebar button')).find(b=>b.innerText.includes('新会话')))()"""
APPROVE = """(()=>document.getElementById('approve-btn'))()"""
DENY = """(()=>document.getElementById('deny-btn'))()"""
# ■ 停止这颗键没有 elem_id（my_ui.py:1287 只给了 variant/scale/min_width），
# 只能按文字在 #statusrow 里找。别按位置取——那颗键左边还有 approve/deny 两个隐藏容器。
STOPBTN = """(()=>Array.from(document.querySelectorAll('#statusrow button')).find(b=>b.innerText.includes('停止')))()"""
STATUS = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');return t.slice(0,180);})()"""
BOTN = """(()=>document.querySelectorAll('#main [data-testid=bot]').length)()"""
# 气泡正文里那几种措辞在不在。两个坑都踩过：
#  1) 用 innerText 会把**收起的**折叠卡读成「没这张卡」（审批卡、已中断卡都是折叠的），所以用 textContent；
#  2) 反过来，折叠卡的**正文**根本不在 DOM 里（gradio 展开时才挂载内容），所以「⏹ 本题已中断」
#     那句正文测不到——测的是卡标题：STATE_LABEL['interrupted']＝「已中断」和标题尾巴「审批空等」
#     都是渲染在标题上的字。B1 第一跑就是按正文断言，结果标着 N，实际屏幕上标题明明是「⏹ 已中断 · 审批空等 5.0s」。
MARK = """(()=>{const b=document.querySelectorAll('#main [data-testid=bot]');
const t=[...b].map(x=>x.textContent).join(' ¶ ');
const has=re=>re.test(t)?'Y':'N';
return 'bot='+b.length+' 已中断标题='+has(/已中断/)+' 空等字样='+has(/审批空等/)+
       ' 随中断取消='+has(/随中断取消/)+' 随停止取消='+has(/随停止取消/)+' 还在等审批='+has(/等待你审批/);})()"""
# P0-4 的措辞命中。和 MARK 分开的理由：那几条是 B 系列（工具审批）的**反向回归**判据，
# 混在一起出问题时分不清是哪一路。
# 只测**标题**：审批卡、✖ 计划未批准、⏹ 已中断都是带 title 的折叠卡，收起时正文不在 DOM 里
# （上面 MARK 那段注释记过这个坑）。所以「一个工具都没跑」「没有进模型的记忆」这类正文句子
# 不在这里测，改从库里那条消息的 content 里测（下方 phrase_hits，屏幕折起来不代表没落库，
# 库里的 content 是完整的）；面板那一格在 #planpanel 里，由 PLANPANEL 单独测。
PLANMARK = """(()=>{const b=document.querySelectorAll('#main [data-testid=bot]');
const t=[...b].map(x=>x.textContent).join(' ¶ ');
const has=re=>re.test(t)?'Y':'N';
return 'bot='+b.length+' 计划审批卡标题='+has(/待批 · 计划/)+' 未批准卡标题='+has(/计划未批准/)+
       ' 已中断卡标题='+has(/已中断/)+' 工具那路审批卡标题='+has(/待批 · run_python/);})()"""
AWAITING = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /等待审批/.test(t) ? 'YES:'+t.slice(0,160) : 'NO:'+t.slice(0,160);})()"""
# P0-4：待批药丸把那一张单子的名字直接写在屏上（_status_html:1050 就是 a.tool），
# 所以「等的是计划」和「等的是工具」在屏幕上分得出来，不必猜。
# 注意不能只写 /待批.*计划/：* 会跨过中间所有药丸，等到 run_python 时尾巴上的「状态 …」
# 也可能带出「计划」二字。这里挨着的两个药丸之间最多一个空格。
AWAIT_PLAN = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /待批 计划/.test(t) ? 'YES:'+t.slice(0,170) : 'NO:'+t.slice(0,170);})()"""
AWAIT_TOOL = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /待批 (?!计划)/.test(t) ? 'YES:'+t.slice(0,170) : 'NO:'+t.slice(0,170);})()"""
# 计划面板那一格：#planpanel 是聊天框外面那个 gr.Markdown（elem_id 在 create_app 里给的）。
# 收起的折叠卡正文不在 DOM 里，所以「计划到底上没上墙」这一问只能问这块面板，别问气泡。
# MISSING 和 HIDDEN 要分开报：C0 第一跑就发现**提问之前那块压根没有这个元素**（visible=False
# 的 Markdown 在初始 DOM 里不存在），到批准那一帧才被建出来——所以「没上墙」有两种，
# 混成一句就会把「元素还没建」误读成「建了但是空的」。
def _panel_js(with_yes):
    return """(()=>{const p=document.getElementById('planpanel');
if(!p) return '%sNO:DOM 里没有 #planpanel 这个元素（visible=False 时 gradio 不建它）';
const txt=(p.innerText||'').replace(/\\s+/g,' ').trim();
const vis=p.offsetParent!==null && txt.length>0;
if(!vis) return '%sNO:元素在但没画（HIDDEN/空）';
const has=re=>re.test(txt)?'Y':'N';
return '%sYES:panel=VISIBLE 字符='+txt.length+' 等待审批='+has(/等待审批/)+' 已允许='+has(/已允许/)+
       ' 已拒绝='+has(/已拒绝/)+' 已取消='+has(/已取消/)+' 已超时='+has(/已超时/)+
       ' 一个工具都没跑='+has(/一个工具都没跑/)+' 开头=['+txt.slice(0,30)+']';})()""" % (
        "panel=" if not with_yes else "", "panel=" if not with_yes else "",
        "" if with_yes else "panel=")


PLANPANEL = _panel_js(False)
# 给 until 用的那一版：面板一出现在屏上就返回 YES，剧本据此量「从挂起审批到面板上屏隔了多久」。
PLANPANEL_YES = _panel_js(True)
DONE = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
const bot=document.querySelectorAll('#main [data-testid=bot]').length;
const busy=/生成中|等待审批|停止中/.test(t);
return (!busy && bot>0) ? 'YES:bot='+bot+' | '+t.slice(0,150) : 'NO:busy='+busy+'|bot='+bot+'|'+t.slice(0,90);})()"""
# D 系列（P1-a）用：第二问开局前必须先看到「生成中」，否则 DONE 会拿着上一问的静止画面
# 立刻返回 YES，第二问等于没跑。
BUSY = """(()=>{const t=(document.getElementById('statusbar')||{innerText:''}).innerText.replace(/\\s+/g,' ');
return /生成中|等待审批|停止中/.test(t) ? 'YES:'+t.slice(0,150) : 'NO:'+t.slice(0,150);})()"""
# 第⑤刀的两档新判定。**只测标题**：折叠卡正文不在 DOM 里（上面 MARK 那段注释记过这个坑），
# 而 ⚪ 重复未执行 / ⛔ 重复熔断 这两个字是写在 metadata.title 上的（my_ui.py 的 _step_card）。
DUPMARK = """(()=>{const b=document.querySelectorAll('#main [data-testid=bot]');
const t=[...b].map(x=>x.textContent).join(' ¶ ');
const has=re=>re.test(t)?'Y':'N';
return 'bot='+b.length+' 重复未执行='+has(/重复未执行/)+' 重复熔断='+has(/重复熔断/)+
       ' 成功卡='+has(/成功/)+' 报错卡='+has(/报错/);})()"""
# 21:06 那道原题面（.agent-ui.log，第④刀的 A 格用的是同一句）。两问一模一样：
# 第二问就是「换题清零」那一刀——第一问发过的调用在第二问必须真的执行。
TASK_D = "删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动"

SCEN = {
    "B0": dict(reload=False, approve=True, kill=False, tail=10, note="对照：正常点允许，跑到答完（证明日志里那几行在正常路上会出现）"),
    "B1": dict(reload=True, approve=False, kill=False, tail=75, note="主测：挂在待批上时刷新页面（D8 的扳机），之后没人点"),
    # B2：没人断开、也没人点——直接把进程杀掉。这一路才是「一行都不落库」。
    "B2": dict(reload=False, approve=False, kill="kill", tail=2, note="挂在待批上时 SIGKILL（强关 App 那一路，不给任何收尾机会）"),
    # 票据原文写的是「关 App / Ctrl-C」，但这两个是不同信号：SIGKILL 必然没有收尾，
    # SIGINT（终端 Ctrl-C）会不会被 gradio 变成一次正常的生成器关闭、从而落半截——当场量。
    "B3": dict(reload=False, approve=False, kill="int", tail=6, note="挂在待批上时 SIGINT（终端 Ctrl-C 那一路）"),
    # B4 是第②刀的**反向**回归：D8 只改「断开」那一路的措辞和收尾，按 ■ 停止的一路必须还是
    # 「随停止取消」、不许长出「⏹ 本题已中断」——那一按是真的有人按了停止，不是页面没了。
    "B4": dict(reload=False, approve=False, stop=True, kill=False, tail=8, note="挂在待批上时按 ■ 停止（回归：这一段措辞和标记都不该变）"),
    # ---- P0-4（计划可见 + 批准动作）那五跑，tag 一律 C 开头 -------------------------------
    # 为什么重跑一遍「允许」而不是只测拒绝：开了 planning_interval 之后，每一题现在**先**过
    # 计划门、**再**过工具门。B0～B4 那五跑的证据是在门只拦工具的时候拍的（run/v18_after_fix.out），
    # 计划这一路加进来会不会把工具那一路的顺序、卡片、账本挤坏，只有真跑一遍才知道。
    "C0": dict(flow="C", act="approve", tail=10,
               note="对照：面板上屏 → ✔ 允许计划 → 工具审批照常 → 跑到答完（两道门串起来走通）"),
    # C1 是这一刀的主测：✖ 拒绝之后**整题不许开工**。屏幕那侧只能看到状态条变了，
    # 「一个工具都没跑」和「计划没进记忆」这两条必须靠服务端与库里证：
    # 日志里没有 plan.gate.allowed、memory 那一行没有 PlanningStep、也没有 ActionStep。
    "C1": dict(flow="C", act="deny", tail=8,
               note="主测：在计划待批上点 ✖ 拒绝 → 状态「计划未批准」，整题不开工、计划不进记忆"),
    # C2 是第②刀（D8 断开侧）落在计划上的反向回归：■ 停止是**人按的**，那一档必须还是
    # 「随停止取消」，不许长出「⏹ 已中断」，也不许把否决的紫色药丸用上。
    "C2": dict(flow="C", act="stop", tail=8,
               note="■ 停止正好落在计划待批上：随停止取消、状态「已停止」，不是「计划未批准」也不是「已中断」"),
    # C3 是 D8 那一刀在计划上的正向回归：刷新页面 → 生成器收到 GeneratorExit → 待批结算 →
    # 「已中断」卡用的是**计划那一句**措辞（「停在 1 份计划的批准这一步就被中断」）。
    # 顺带量一件事：刷新后面板是空的。不是 bug 未修——那份计划没批，压根没进 memory，
    # _on_load 只能从记忆里读，读不到就没得画。这一条要写进已知边界。
    "C3": dict(flow="C", act="reload", tail=15,
               note="刷新页面正好落在计划待批上（D8 扳机 + 计划门）：已中断措辞走计划那一路，刷新后面板读不到计划"),
    # C4：没人点、也没人按停止，就让审批超时。超时这一路走的是 DECISION_LABEL["timeout"]
    # （「已超时」）→ 同 PlanDeniedError → 状态也是「计划未批准」。
    # 超时常量由 v18_ui.py 读环境变量 V18_TIMEOUT 在**探针侧**改短（产品里仍是 600）。
    "C4": dict(flow="C", act="timeout", tail=8,
               note="计划待批一直没人点，等到审批超时（探针侧 V18_TIMEOUT 改短，产品里仍 600）"),
    # ---- P1-a（重复调用检测与熔断）：D 系列 ----------------------------------------------
    # 为什么只有一跑：这一刀的两问都在同一跑里答——
    #   ① 熔断有没有真的把绕圈掐短（第一问：状态「重复熔断」、步数小于 8、日志里 kind=fuse）；
    #   ② 登记表是不是每问开局清干净（第二问：同一道题面，第一问里被挡过的那几个调用这一问
    #      必须 kind=run，而且 dup.call 行里的 blocked 从 0 重新数起）。
    # 条件对齐第④刀的 A 格：planning 在探针侧关掉（V18_PLANNING=off），所以那两格的
    # 「8 步用满、重复 0 次」就是这一跑的直接对照组。
    "D0": dict(flow="D", tail=8,
               note="21:06 原题面连问两遍：第一遍看熔断掐短，第二遍看换题清零"),
}


def b64(s):
    return base64.b64encode(s.encode()).decode()


def wait_http(limit=240):
    """等 app 真的能服务，再让浏览器进场。

    为什么不再盲等 12 秒：11-03 21:41 那一跑，gradio 到 **31.7s** 才画出首屏（服务端
    on_load 那一行的 wall=31.707），而剧本 bootWait 只有 12s，于是 P1-new／P3-ask 全打在
    还没长出来的页面上——那题压根没提交，日志里连 respond.enter 都没有。把「等 ready」
    改成直接问 app 本人（GET /config 是 gradio 前端的起手请求，它 200 就说明资源和
    Blocks 都就绪了），顺便把等了多久记进证据。
    """
    import urllib.request
    t0 = time.time()
    tries = []
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(URL + "/config", timeout=3) as r:
                body = r.read()
                tries.append((round(time.time() - t0, 1), r.status, len(body)))
                if r.status == 200:
                    return tries
        except Exception as exc:
            tries.append((round(time.time() - t0, 1), type(exc).__name__, str(exc)[:50]))
        time.sleep(2)
    return tries


def dbcount(db):
    if not db.exists():
        return "库不存在"
    c = sqlite3.connect(str(db))
    with c:
        r = {t: c.execute("select count(*) from %s" % t).fetchone()[0] for t in ("sessions", "messages", "memory")}
        per = c.execute("select session_id, count(*) from messages group by session_id order by session_id").fetchall()
    c.close()
    return "%s | messages 按会话 %s" % (r, per)


def memsteps(db):
    """每条会话的记忆里各有哪些**步类型**、各几条——P0-4 的判据落在这里。

    为什么不能只看 messages 表：屏幕上那张审批卡写着什么，都不证明 agent 那一侧动了没有。
    记忆里有没有 PlanningStep / ActionStep 才是「这份计划批过了」和「这一题开没开工」的
    实物证据（门卡在 memory.steps.append 之前，见 my_ui._install_plan_gate 的注释）。
    """
    if not db.exists():
        return "库不存在"
    c = sqlite3.connect(str(db))
    out = []
    try:
        with c:
            rows = c.execute("select session_id, payload from memory order by session_id").fetchall()
    finally:
        c.close()
    for sid, payload in rows:
        try:
            steps = __import__("json").loads(payload)["steps"]
        except Exception as exc:
            out.append("sid=%s 解析失败:%s" % (sid, type(exc).__name__))
            continue
        kinds = [s.get("_t", "?") for s in steps]
        counts = {}
        for k in kinds:
            counts[k] = counts.get(k, 0) + 1
        # token 按步型分开加总。**这道题的口径必须说清**：状态条上那颗「本题 token」
        # 只加 ActionStep（_stream_response:1152-1155 那段只认 ActionStep），
        # 规划那一次调用的 in/out 不在里面——它是 C0 实测出来的一个差额，见
        # run/v18_p04_live.out 的「本题 token 少算了多少」那一节。
        tok = {}
        for s in steps:
            t = s.get("token_usage") or {}
            d = tok.setdefault(s.get("_t", "?"), [0, 0])
            d[0] += int(t.get("input_tokens") or 0)
            d[1] += int(t.get("output_tokens") or 0)
        total = [sum(v[0] for v in tok.values()), sum(v[1] for v in tok.values())]
        out.append("sid=%s %s 顺序=%s token按步型in/out=%s 合计=in %d/out %d"
                   % (sid, counts, ",".join(k[0] for k in kinds),
                      " ".join("%s:%d/%d" % (k, v[0], v[1]) for k, v in tok.items()),
                      total[0], total[1]))
    return " | ".join(out) if out else "memory 表没有行（这一题一行记忆都没落）"


# 折叠卡正文不在 DOM 里（屏幕测不到），但库里 messages.content 是全文：这几句只能这样验。
PHRASES = ("一个工具都没跑", "没有进模型的记忆", "批准这一步就被中断",
           "等待你批准这份计划", "计划全文")


def phrase_hits(db):
    """库里每条消息正文里出现没有这些句子（命中次数）。"""
    if not db.exists():
        return "库不存在"
    c = sqlite3.connect(str(db))
    try:
        with c:
            txt = " ¶ ".join(r[0] for r in c.execute("select content from messages order by id"))
    finally:
        c.close()
    return " ".join("%s=%d" % (p, txt.count(p)) for p in PHRASES) + " ｜ 全文 %d 字符" % len(txt)


def c_steps(s):
    """C 系列（P0-4）的浏览器剧本。四种结局共用起手五步，之后各走各的。"""
    steps = [
        {"name": "C0-peek", "expr": b64(BOTN)},
        {"name": "C1-panel-before-ask", "expr": b64(PLANPANEL)},
        {"name": "C2-new", "el": b64(NEWBTN), "wait": 2500},
        {"name": "C3-ask", "type": Q},
        {"name": "C4-await-plan", "until": b64(AWAIT_PLAN), "timeout": 150000},
        # 面板上屏单独等：C0 第一跑在这里读到过「DOM 里没有这个元素」，而服务端早就
        # yield 了 visible=True——所以只读一次会把"渲染晚一轮"误判成"没画"。
        # waitedMs 就是这一问的数：从状态条报出待批到面板真的在屏上隔了多久。
        {"name": "C5-panel-pending", "until": b64(PLANPANEL_YES), "timeout": 15000},
        {"name": "C5b-mark-pending", "expr": b64(PLANMARK)},
        {"name": "C5c-status-pending", "expr": b64(STATUS)},
    ]
    act = s["act"]
    if act == "approve":
        steps += [
            {"name": "C6-approve-plan", "el": b64(APPROVE), "wait": 3000},
            {"name": "C7-panel-allowed", "expr": b64(PLANPANEL)},
            {"name": "C8-await-tool", "until": b64(AWAIT_TOOL), "timeout": 150000},
            {"name": "C9-panel-still", "expr": b64(PLANPANEL)},
            {"name": "C10-approve-tool", "el": b64(APPROVE), "wait": 2000},
            {"name": "C11-await-done", "until": b64(DONE), "timeout": 240000},
            {"name": "C12-panel-final", "expr": b64(PLANPANEL)},
            {"name": "C13-mark-final", "expr": b64(PLANMARK)},
            {"name": "C14-status-final", "expr": b64(STATUS)},
        ]
    elif act == "reload":
        steps += [
            {"name": "C6-reload", "reload": 6000},
            {"name": "C7-panel-after-reload", "expr": b64(PLANPANEL)},
            {"name": "C8-mark-after-reload", "expr": b64(PLANMARK)},
            {"name": "C9-status-after-reload", "expr": b64(STATUS)},
            # 再等 15 秒、**再刷一次**：C3 第一跑就在这一秒读到 bot=0、状态「空闲」，
            # 而服务端日志里 ⏹ 已中断 那张卡是 t=20.680 才 save 进库的（首屏 on_load 在
            # t=20.230，库里那时还是 0 行）。两刷之间差 15 秒就是为了把这个差额摊开：
            # 如果第二刷看得到卡，那问题只是「首屏读空」（就是 #42 那张单）；
            # 第二刷也看不到，才是「这条消息永远上不了墙」。
            {"name": "C10-hold-for-settle", "wait": 15000},
            {"name": "C11-reload-again", "reload": 8000},
            # 这一格预期**等满**：那份计划没批、没进 memory，第二刷的面板就该是空的。
            {"name": "C12-panel-2nd", "until": b64(PLANPANEL_YES), "timeout": 8000},
            {"name": "C13-mark-2nd-plan", "expr": b64(PLANMARK)},
            {"name": "C14-mark-2nd-tool", "expr": b64(MARK)},
            {"name": "C15-status-2nd", "expr": b64(STATUS)},
        ]
    else:
        if act == "deny":
            steps.append({"name": "C6-deny-plan", "el": b64(DENY), "wait": 3000})
        elif act == "stop":
            steps.append({"name": "C6-stop-plan", "el": b64(STOPBTN), "wait": 3000})
        else:  # timeout：什么都不做，等到 V18_TIMEOUT 之后
            steps += [{"name": "C6-hold", "wait": 6000},
                      {"name": "C6b-still-pending", "expr": b64(AWAIT_PLAN)}]
        steps += [
            {"name": "C7-panel", "expr": b64(PLANPANEL)},
            {"name": "C8-status", "expr": b64(STATUS)},
            {"name": "C9-mark", "expr": b64(PLANMARK)},
            {"name": "C10-await-settled", "until": b64(DONE), "timeout": 60000},
            {"name": "C11-panel-final", "expr": b64(PLANPANEL)},
            {"name": "C12-mark-final", "expr": b64(PLANMARK)},
            {"name": "C13-status-final", "expr": b64(STATUS)},
        ]
    return steps


def d_steps(s):
    """D 系列（P1-a）的浏览器剧本：同一道题面连问两遍，中间不点任何东西。

    为什么没人点也算得出这一刀：查重这层套在**所有**工具上，而 21:06 那批重复调用全在
    只读侧（list_dir / grep_files / read_file 本来就不弹审批）。万一模型这回去碰
    write_file/run_python，D5b 那一步会先等出「待批」，剧本就在那儿停住——那也是一种读数
    （审批层没有被这层绕过），所以这里等的是 BUSY 的消失，不是 DONE。
    """
    return [
        {"name": "D0-peek", "expr": b64(BOTN)},
        {"name": "D1-new", "el": b64(NEWBTN), "wait": 2500},
        {"name": "D2-read", "expr": b64(STATUS)},
        {"name": "D3-ask-1", "type": TASK_D},
        {"name": "D4-await-busy-1", "until": b64(BUSY), "timeout": 20000},
        {"name": "D5-await-done-1", "until": b64(DONE), "timeout": 300000},
        {"name": "D6-status-1", "expr": b64(STATUS)},
        {"name": "D7-mark-1", "expr": b64(DUPMARK)},
        # 换题清零那一问：题面一字不改。这一步之前的 dup.call 行属于第一问，之后属于第二问，
        # 两边靠日志里的 run=（_run_seq）分开，第二问那批必须从 kind=run 开头。
        {"name": "D8-ask-2", "type": TASK_D},
        {"name": "D9-await-busy-2", "until": b64(BUSY), "timeout": 20000},
        {"name": "D10-await-done-2", "until": b64(DONE), "timeout": 300000},
        {"name": "D11-status-2", "expr": b64(STATUS)},
        {"name": "D12-mark-2", "expr": b64(DUPMARK)},
    ]


def run(tag):
    s = SCEN[tag]
    log_p = RUN / ("v18_probe_%s.server.log" % tag)
    if log_p.exists():
        log_p.unlink()
    db = RUN / ("v18_live_%s.sqlite3" % tag)
    for f in (db,):
        f.unlink(missing_ok=True)
    out = open(RUN / ("v18_probe_%s.stdout" % tag), "w", encoding="utf-8")
    env = dict(os.environ)
    is_c = s.get("flow") == "C"
    is_d = s.get("flow") == "D"
    if tag == "C4":
        # 只有这一跑把超时改短（探针侧，产品常量不动）。20s：够面板把「已挂起」画出来、
        # 又不用干等十分钟。C6-hold 6s + 前面的读数约 2s，再加这一档，落在 20s 之后。
        env["V18_TIMEOUT"] = "20"
    if not is_c:
        # B 系列（D8 那五跑）关掉规划，条件才和 run/v18_after_fix.out 当时一致
        env["V18_PLANNING"] = "off"
    p = subprocess.Popen([PY, str(HERE / "v18_ui.py"), PORT, str(db), tag],
                         stdout=out, stderr=subprocess.STDOUT, start_new_session=True, env=env)
    steps = (c_steps(s) if is_c else d_steps(s) if is_d else [
        {"name": "P0-peek", "expr": b64(BOTN)},
        {"name": "P1-new", "el": b64(NEWBTN), "wait": 2500},
        {"name": "P2-read", "expr": b64(STATUS)},
        {"name": "P3-ask", "type": Q},
        {"name": "P4-await", "until": b64(AWAITING), "timeout": 150000},
        {"name": "P5-hold", "wait": 4000},
        {"name": "P6-status-before", "expr": b64(STATUS)},
        {"name": "P7-bot-before", "expr": b64(BOTN)},
        {"name": "P7b-mark-before", "expr": b64(MARK)},
    ])
    if not is_c and not is_d:
        if s["reload"]:
            steps.append({"name": "P8-reload", "reload": 5000})
        if s["approve"]:
            steps.append({"name": "P8-approve", "el": b64(APPROVE)})
            steps.append({"name": "P9-await-done", "until": b64(DONE), "timeout": 180000})
        if s.get("stop"):
            steps.append({"name": "P8-stop", "el": b64(STOPBTN)})
            steps.append({"name": "P9-await-settled", "expr": b64(MARK), "wait": 3000})
            steps.append({"name": "P9b-await-done", "until": b64(DONE), "timeout": 120000})
        steps.append({"name": "P10-after-peek-bot", "expr": b64(BOTN)})
        steps.append({"name": "P11-after-status", "expr": b64(STATUS)})
        steps.append({"name": "P12-mark-after", "expr": b64(MARK)})
    cfg = {"url": URL, "bootWait": 6000, "steps": steps}
    cfgp = RUN / ("v18_live_cdp_%s.json" % tag)
    cfgp.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    ready = wait_http()
    ready_note = "app 就绪 %.1fs（/config %s）" % (
        ready[-1][0], "200 %dB" % ready[-1][2] if len(ready) and ready[-1][1] == 200 else "一直不成功 %s" % ready[-1][1:])
    t_start = time.time()
    kill_at = None
    kill_note = "未杀（这一路是刷新页面或正常跑完，进程归收尾的 SIGTERM 处理）"
    r = None
    try:
        r = subprocess.run(["node", str(HERE / "v18_cdp.js"), str(cfgp)], capture_output=True, text=True)
        (RUN / ("v18_live_cdp_%s.out" % tag)).write_text(r.stdout + ("\nSTDERR:\n" + r.stderr if r.stderr else ""), encoding="utf-8")
        time.sleep(s["tail"])
        if s.get("kill"):
            # 走到这里这一题还挂在待批上（没人刷新、没人点、没人断）。
            # 必须**先杀再读**：这一路要量的就是「进程没了，库里到底有没有这一题」，
            # 读早了读到的是还活着的进程自己写下的东西。
            # 超时保持真值 600s 不动：这一路压根没有等待超时这一回事，进程直接没了。
            sig = signal.SIGKILL if s["kill"] == "kill" else signal.SIGINT
            kill_at = time.time()
            os.killpg(os.getpgid(p.pid), sig)
            time.sleep(s["tail"])
            # 进程是不是真的死了要单独报：worker 线程还阻塞在 Event.wait() 上，
            # 若它不是 daemon，主线程退出后进程照样挂着，待批会一直挂到 600s 超时。
            still_alive = p.poll() is None
            kill_note = "杀掉之后 %.1fs：进程仍存活（p.poll() is None）" % (time.time() - kill_at) if still_alive \
                else "杀掉之后 %.1fs：进程已退出，returncode=%s" % (time.time() - kill_at, p.poll())
    finally:
        el = log_p.read_text(encoding="utf-8") if log_p.exists() else ""
        db_now = dbcount(db)
        counters = [("respond.enter",), ("respond.GeneratorExit",), ("respond.finally",),
                    ("stream.GeneratorExit",), ("save.enter",), ("save.exit",),
                    ("save_memory.enter",), ("save.RAISED",),
                    ("mark.enter",), ("mark.exit",), ("on_load",)]
        if is_d:
            # 装了哪几只手、每一次判定落在哪一档。fuse 那一档必须恰好 1 行（触熔断那次），
            # 而第二问的 kind=run 行是「换题清零」的唯一现场证据。
            counters += [("dup.install",), ("dup.call",), ("dup.call kind=run",),
                         ("dup.call kind=warn",), ("dup.call kind=fuse",),
                         ("ap.wait.enter",)]
        if is_c:
            # 计划这一路的计数。ap.wait.exit 那行带着 tool=计划，和工具那一路分开数：
            # 两个都数才能证明「C0 那跑真的过了两道门」而不是只过了一道。
            # 一格写成**若干个必须同时出现的子串**（用 tuple），不能拼成一整串：日志的行是
            # `ap.wait.exit    id=15b203 tool=计划 ...`，事件名后面有一串对齐空格，
            # 拿 "ap.wait.exit tool=计划" 去 in 一行永远是 0（C0 第一跑就被数成了 0）。
            counters += [("plan.gate.enter",), ("plan.gate.allowed",), ("plan.gate.denied",),
                         ("plan.gate.raise",), ("plan.update",),
                         ("ap.wait.enter", "tool=计划"), ("ap.wait.exit", "tool=计划"),
                         ("ap.wait.enter", "tool=run_python"), ("ap.wait.exit", "tool=run_python"),
                         ("respond.exception",)]
        summ = ["场景 %s：%s" % (tag, s["note"]),
                ready_note,
                "起点 epoch %.3f ｜ 杀掉时刻 %s" % (t_start, ("%s @ %.3f（跑完 cdp 剧本之后）" % ("SIGKILL" if s.get("kill") == "kill" else "SIGINT", kill_at)) if kill_at else "未杀"),
                kill_note,
                "探针配置（boot.epoch）：",
                "  " + "\n  ".join(ln for ln in el.splitlines() if "boot.epoch" in ln),
                "浏览器侧：", (r.stdout.strip() if r else "（cdp 没跑起来）"),
                "", "服务端（v18_ui.py 的包装）：", el.strip() or "（空）",
                "", "%s库里： %s" % ("杀进程之后： " if kill_at else "跑完之后： ", db_now),
                "库里的记忆步型：", "  " + memsteps(db),
                "库里的正文命中的句子：", "  " + phrase_hits(db),
                "计数：",
                "\n".join("  %-30s %d" % ("+".join(k), sum(1 for ln in el.splitlines()
                                                           if all(p in ln for p in k)))
                          for k in counters)]
        (RUN / ("v18_live_summary_%s.out" % tag)).write_text("\n".join(summ) + "\n", encoding="utf-8")
        print("\n".join(summ))
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception as exc:
            print("kill failed（B2 已经 SIGKILL 过，这里报 ESRCH 属正常）:", exc)
        out.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "B0")
