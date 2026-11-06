# -*- coding: utf-8 -*-
"""D8 基线②的运行界面：真 app ＋ 只在**探针侧**加的包装，my_ui.py 一个字没改。

包了十三处（都在这个文件里 monkeypatch，落到实例/类上，源码 sha1 不变；前七处是 D8 那两刀
带的，中间四处随 D8 修复版与 P0-4 逐个加上来，最后两处是 P1-a）：
  History.save        → 打时刻、sid、消息条数、写库前后 messages 表的行数
  History.save_memory → 打时刻、sid、payload 长度
  OpsUI._stream_response / OpsUI._respond → 用外层生成器包一层，专门抓 GeneratorExit，
                        看客户端断开时 gradio 到底关没关这条生成器（基线①的最小探针已经证明
                        最小形状下它会收到 GeneratorExit，真 app 是不是同一回事要在这里量）
  Approval.wait / Approval.decide / OpsUI._settle_all ＋ 一条 1s 轮询线程
                        → 票据第②问：worker 阻塞在 wait() 时断开，那条 pending 到底怎么结算、
                           什么时候结算。界面上看不出来（reload 后状态条是 _on_load 重画的，
                           它不读 _pending），只能在服务端点。
  OpsUI._mark_interrupted / OpsUI._on_load（D8 第②刀之后加的）
                        → 修复有没有真的跑、补进去的 wait 挂到了哪一步、刷新那一下状态条
                           读到的到底是几步。基线里那个「屏上 0/8 vs 库里 step_number:1」
                           的反差就是靠 on_load 这一行解释的。
  OpsUI._plan_gate / OpsUI._plan_update（P0-4 之后加的）
                        → 计划门是不是真的卡在「计划已生成、agent 还没开工」那一刻、
                           落在计划上的四种结局（✔ 允许 / ✖ 拒绝 / ■ 停止 / 超时）各抛出
                           哪一类异常、等了多久；面板那一格每一帧是可见还是隐藏、挂的是哪
                           一份计划。这两条是 P0-4 的现场验收点，界面上只能看到面板变了，
                           看不到「内层生成器有没有被恢复」——那一问只有服务端点得出来。

  OpsUI._install_dup_gate / OpsUI._dup_call（P1-a 之后加的）
                        → 查重这层到底装上了哪几只手（只读那三只必须在内）、每一次判定落在
                           哪一档（kind=run 真往下跑 / warn 挡下并回警告 / fuse 挡下且触熔断）、
                           当时是第几问（run=_run_seq）、累计挡下几次。第⑤刀的三个数
                           （第 n 次／挡下 m 次／上限 2）出函数就不在了，只能在这儿点下来。

用法：python v18_ui.py <port> <db路径> <日志名tag>
"""
import functools
import os
import pathlib
import sqlite3
import sys
import threading
import time

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_ui  # noqa: E402

port = int(sys.argv[1]) if len(sys.argv) > 1 else 7872
db = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.8/run/v18-live-hist.sqlite3")
TAG = sys.argv[3] if len(sys.argv) > 3 else "B"
LOG = pathlib.Path(__file__).resolve().parent / "run" / ("v18_probe_%s.server.log" % TAG)
LOG.parent.mkdir(exist_ok=True)
T0 = time.time()

# 探针侧把审批超时改短，只为 C4 那一跑（超时落在**计划**上等不等得到）。产品里这个常量
# 还是 600，真 app 不动——这里改的是本进程读到的模块全局，`Approval.wait()` 每次调用时
# 现取，所以设一次就生效。没给环境变量时保持 600 原值。
if os.environ.get("V18_TIMEOUT"):
    my_ui.APPROVAL_TIMEOUT = float(os.environ["V18_TIMEOUT"])

# 同样只在探针侧：把 planning_interval 关掉，让 B 系列（D8 那五跑）在 P0-4 之后还能复现
# 当时的条件——开了规划之后每一题**先**过计划门，B4 那条「挂在待批上按 ■ 停止」按到的
# 就是计划单而不是工具单，和 run/v18_after_fix.out 里的证据不是同一回事。
# 关在这里不影响产品（my_agent.py 里仍是 PLANNING_INTERVAL=8），也不影响计划门那段包装：
# 门只在真的交出 PlanningStep 时才响，关着就一次都不响。
if os.environ.get("V18_PLANNING") == "off":
    my_ui.agent.planning_interval = None

_lock = __import__("threading").Lock()


def log(ev, **kw):
    extra = " ".join("%s=%s" % (k, v) for k, v in kw.items())
    line = "t=%7.3f  %-22s %s" % (time.time() - T0, ev, extra)
    with _lock:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line, flush=True)


def rows(db_path, sid=None):
    """读库行数。**探针自己的工具函数**，不参与产品逻辑。

    这一版修了一个低级错：原来 `c.close()` 写在 `with c:` 里面，退出 with 时 sqlite 要
    commit 一条已经关掉的连接，于是每次都是 `ProgrammingError: Cannot operate on a closed
    database.`。基线那份日志里 save.enter / save.exit / save_memory / on_load 四行的
    before=、after=、db_memory= 全是这一句（本轮带上异常消息才看出来）。那几次跑的**结论没
    有依赖这几格**——库里几行是 v18_run_live.py 的 dbcount() 读的，那是另一条正确的连接；
    但从这一跑起，这几格才真的算数据。
    """
    try:
        c = sqlite3.connect(str(db_path))
        try:
            with c:
                if sid is None:
                    n = c.execute("select count(*) from messages").fetchone()[0]
                    m = c.execute("select count(*) from memory").fetchone()[0]
                    s = c.execute("select count(*) from sessions").fetchone()[0]
                else:
                    n = c.execute("select count(*) from messages where session_id=?", (sid,)).fetchone()[0]
                    m = c.execute("select count(*) from memory where session_id=?", (sid,)).fetchone()[0]
                    s = "sid=%s" % sid
            return "sessions=%s messages=%s memory=%s" % (s, n, m)
        finally:
            c.close()
    except Exception as exc:
        return "read-failed:%s: %s" % (type(exc).__name__, str(exc)[:90])


# ---- 包装：落库这一侧 ---------------------------------------------------------------
_save = my_ui.History.save
_save_mem = my_ui.History.save_memory


def save(self, sid, messages):
    log("save.enter", sid=sid, msgs=len(messages), before=rows(self.path, sid))
    try:
        r = _save(self, sid, messages)
    except BaseException as exc:
        log("save.RAISED", sid=sid, exc=type(exc).__name__, msg=str(exc)[:120])
        raise
    log("save.exit", sid=sid, after=rows(self.path, sid))
    return r


def save_memory(self, sid, payload):
    log("save_memory.enter", sid=sid, chars=len(payload))
    n = _save_mem(self, sid, payload)
    log("save_memory.exit", sid=sid, changed_rows=n, after=rows(self.path, sid))
    return n


my_ui.History.save = save
my_ui.History.save_memory = save_memory

# ---- 包装：两条生成器，专门看断开时收到什么 ------------------------------------------
_stream = my_ui.OpsUI._stream_response
_respond = my_ui.OpsUI._respond


@functools.wraps(_stream)
def stream_response(self, message, history):
    inner = _stream(self, message, history)
    n = 0
    log("stream.enter", sid=self._sid)
    try:
        for x in inner:
            n += 1
            yield x
    except GeneratorExit:
        log("stream.GeneratorExit", frames=n)
        raise
    except BaseException as exc:
        log("stream.exception", exc=type(exc).__name__, frames=n)
        raise
    finally:
        log("stream.finally", frames=n)
    log("stream.normal-end", frames=n)


@functools.wraps(_respond)
def respond(self, message, sid):
    inner = _respond(self, message, sid)
    n = 0
    log("respond.enter", sid=sid)
    # 轮询线程在这里起：**必须待在生成器体内**。前面写过一版把这段放在生成器外面的普通
    # 函数包装里，gradio 就不把 `_respond` 当生成器函数了，直接报
    # `A function (_respond) didn't return enough output values (needed: 7, returned: 1)`，
    # 整个对话一路死掉。这条错本身记一笔口径：**包装流式函数必须保持生成器形状**，`functools.wraps` 挂在普通函数上就够不着 gradio 的判定。
    # （那句 `needed: 7` 是当时 outputs 的条数，P0-4 加了计划面板之后 gradio 会说 `needed: 8`；
    #   留原文不改成 8，是因为这条报错消息本身是证据——它是 P0-4 之前跑出来的。）
    if not INST:
        INST.append(self)
        threading.Thread(target=poller, daemon=True).start()
        log("poller.start", timeout=my_ui.APPROVAL_TIMEOUT)
    try:
        for x in inner:
            n += 1
            yield x
    except GeneratorExit:
        log("respond.GeneratorExit", frames=n)
        raise
    except BaseException as exc:
        log("respond.exception", exc=type(exc).__name__, msg=str(exc)[:90], frames=n)
        raise
    finally:
        log("respond.finally", frames=n, pending=len(self._pending_snapshot()),
            unanswered=len(self._unanswered()))


my_ui.OpsUI._stream_response = stream_response
my_ui.OpsUI._respond = respond

# ---- 包装：审批这一侧（基线②要的正是「断开时那条 pending 怎么结算」） -----------------
# 光看界面无能为力：reload 之后状态条是 _on_load 重画的，它压根不读 _pending，
# 「待批 pill 不见了」只能证明屏幕换了张图，证明不了单子被结算掉。所以在服务端直接点。
_ap_wait = my_ui.Approval.wait
_ap_decide = my_ui.Approval.decide
_settle = my_ui.OpsUI._settle_all


def ap_wait(self):
    log("ap.wait.enter", id=self.id, tool=self.tool, timeout=my_ui.APPROVAL_TIMEOUT)
    d = _ap_wait(self)
    log("ap.wait.exit", id=self.id, tool=self.tool, decision=d, waited=round(self.waited, 3))
    return d


def ap_decide(self, decision):
    before = self.decision
    _ap_decide(self, decision)
    log("ap.decide", id=self.id, tool=self.tool, want=decision,
        before=before, after=self.decision, waited=round(self.waited, 3))


def settle_all(self, decision):
    ids = [ap.id for ap in self._pending_snapshot()]
    log("settle_all.enter", decision=decision, ids=",".join(ids) or "-")
    _settle(self, decision)
    log("settle_all.exit", decision=decision)


my_ui.Approval.wait = ap_wait
my_ui.Approval.decide = ap_decide
my_ui.OpsUI._settle_all = settle_all

# ---- 包装：修复之后新增的两个动作 + 刷新入口（D8 第②刀的现场验收点） --------------------
# 为什么把 _on_load 也包上：基线里那一次「屏上报步数 0/8、库里那行 memory 却带着
# step_number:1 / in 2355 / out 22」我没解释清楚，三次跑两次 0/8、一次 1/8。这一版要在
# 刷新那一下同时记下「_session_steps 读到了几步、每步什么类、_stats 算出什么」，
# 才有资格说这是读回时序还是账本本身的问题（之前的 0.267s 是量 GeneratorExit 的，量不到这里）。
_mark = my_ui.OpsUI._mark_interrupted
_on_load = my_ui.OpsUI._on_load


def mark_interrupted(self, mem, last):
    aps = [ap for ap in self._pending_snapshot() if ap.id in my_ui.OpsUI._ap_cards]
    log("mark.enter", pending=len(self._pending_snapshot()), registered=len(aps),
        mem="None" if mem is None else len(list(mem.steps)),
        steps=",".join(type(s).__name__[0] for s in (mem.steps if mem is not None else [])) or "-",
        last_msgs=len(last))
    out = _mark(self, mem, last)
    waits = [round(getattr(s, "_opsui_wait", 0.0) or 0.0, 3) for s in
             (mem.steps if mem is not None else []) if isinstance(s, my_ui.ActionStep)]
    log("mark.exit", msgs=len(out), wait_per_actionstep=waits,
        tail=str(out[-1].metadata.get("title", ""))[:60] if out else "-")
    return out


def on_load(self):
    t = time.time()
    r = _on_load(self)
    sid = r[1]
    shown = self._session_steps(sid) if sid else []
    s = self._stats(shown) if sid else {}
    log("on_load", sid=sid, steps=len(shown),
        kinds=",".join(type(x).__name__[0] for x in shown) or "-",
        screen_stepno=s.get("step_no"), screen_in=s.get("task_in"), screen_out=s.get("task_out"),
        screen_wait=round(s.get("task_wait", 0.0), 3), mem_held=sorted(str(k) for k in self._mem),
        db_memory=rows(self.hist.path, sid) if sid else "-", wall=round(t - T0, 3))
    return r


my_ui.OpsUI._mark_interrupted = mark_interrupted
my_ui.OpsUI._on_load = on_load

# ---- 包装：P0-4 的计划门与计划面板 -----------------------------------------------------
# 这一对在答的问题是「拒绝之后内层生成器到底有没有被恢复」。界面上只能看到面板换了读数、
# 聊天框里多了一张卡，看到不了 worker 那一路；而「计划没批准 → 计划不进 memory → 一个工具
# 都没跑」恰恰是这一刀全部的语义。所以门这里在服务端把结局记成三类不同的事件：
# 允许（正常返回）／否决（PlanDeniedError）／落在停止上的取消（AgentError 但不是
# PlanDeniedError）。离线闸 v18_test_plan.py 的第 3 节也断这三类，那是假流；这里跑真 agent。
_plan_gate = my_ui.OpsUI._plan_gate
_plan_update = my_ui.OpsUI._plan_update


def plan_label(self):
    """当前队列里最后一张「计划」单子的读数。

    竞态说明：摘单是 UI 线程每 0.25 秒那一轮干的，门一返回就可能被摘走，所以这一格读到
    '-' 是**正常**的，不是没登记。权威读数是 ap.wait.exit 那一行（tool=计划 decision=…
    waited=…），由下面的包装打，它和摘单无关。
    """
    aps = [a for a in self._pending_snapshot() if a.kind == "plan"]
    return ("%s:%s/%.3fs" % (aps[-1].id, aps[-1].decision, aps[-1].waited)) if aps else "-"


def plan_gate(self, planning_step):
    log("plan.gate.enter", chars=len(planning_step.plan or ""),
        pending=len(self._pending_snapshot()), sid=self._sid)
    try:
        _plan_gate(self, planning_step)
    except my_ui.PlanDeniedError as exc:
        log("plan.gate.denied", label=plan_label(self), msg=str(exc)[:80])
        raise
    except BaseException as exc:
        # 到这里只可能是「停止／换题正好落在计划上」那一路（抛的是普通 AgentError）。
        log("plan.gate.raise", exc=type(exc).__name__, label=plan_label(self))
        raise
    log("plan.gate.allowed", label=plan_label(self))
    # 关键一条：允许之后内层才继续走。这一行打印出来 = _run_stream 真的被恢复了。
    # 与 respond 侧的 plan.after_yield 对表，就能看出「否决」那一跑有没有越过这个点。


my_ui.OpsUI._plan_gate = plan_gate


_plan_frames = []


def plan_update(self, shown=None):
    """面板每一帧的读数。去重后只记变化，否则 0.25s 一轮会把日志刷满。"""
    upd = _plan_update(self, shown)
    vis = upd.get("visible")
    val = upd.get("value") or ""
    key = (bool(vis), val.find("**") + len(val), (val[:28] if vis else ""),
           (val.split("**")[3] if vis and val.count("**") >= 4 else ""))
    if not _plan_frames or _plan_frames[-1][0] != key:
        log("plan.update", visible=bool(vis), chars=len(val),
            reading=key[3] or "-", sid=self._sid)
        _plan_frames.append((key, time.time()))
    return upd


my_ui.OpsUI._plan_update = plan_update

# ---- P1-a：查重这一层的现场点（第⑤刀） -----------------------------------------------
# 界面上只能看到「这一步没跑」，看不到第几次、挡下几次、有没有触熔断——那三个数只在
# OpsUI._dup_call 里存在过，出函数就没了。所以这里包一层，把每一次判定原样点下来。
# 装在**类**上（不是实例）：门里的 `_self._dup_call` 是调用时才查名字的，已经装好的工具照样走这条包装。
_install_dup = my_ui.OpsUI._install_dup_gate


def install_dup(self):
    """装了哪几只手，一条装几只就够——只读那三只必须在里面（重复调用恰恰全在只读侧）。"""
    before = sorted(n for n, t in self.agent.tools.items() if getattr(t, "_opsui_dedup", False))
    _install_dup(self)
    after = sorted(n for n, t in self.agent.tools.items() if getattr(t, "_opsui_dedup", False))
    log("dup.install", new=",".join(set(after) - set(before)) or "-",
        already=",".join(before) or "-", total=len(after), limit=my_ui.DUP_BLOCK_LIMIT)


my_ui.OpsUI._install_dup_gate = install_dup

_dup = my_ui.OpsUI._dup_call


def dup_call(self, name, original, args, kwargs):
    """一次判定一行。kind 三档：run=真的往下走了 / warn=挡下并回警告 / fuse=挡下且已触熔断。

    计数读的是**这次调用之后**的类级账（_dup_call 里已经落定），所以和日志对表时
    注意 blocked 是「含本次」的累计值。
    """
    seq = my_ui.OpsUI._run_seq
    r = _dup(self, name, original, args, kwargs)
    blocked = my_ui.OpsUI._dup_blocked
    tripped = my_ui.OpsUI._dup_tripped
    kind = "run" if not r.startswith(my_ui.DUP_MARK) else ("fuse" if my_ui.DUP_FUSE_MARK in r else "warn")
    log("dup.call", run=seq, tool=name, kind=kind, blocked=blocked, tripped=tripped,
        args=str(sorted((my_ui.OpsUI._bind_args(original, args, kwargs) or {}).items()))[:90])
    return r


my_ui.OpsUI._dup_call = dup_call

# ---- 每秒轮一次待批队列：断点前后的结算时刻靠它对表 ---------------------------------
INST = []
_polled = []


def poller():
    while True:
        time.sleep(1.0)
        ui = INST[0] if INST else None
        if ui is None:
            continue
        aps = ui._pending_snapshot()
        log("poll.pending", n=len(aps),
            state=",".join("%s:%s" % (a.id, a.decision) for a in aps) or "-",
            unanswered=len(ui._unanswered()))


# 绝对时刻锚点：浏览器侧（cdp 报的是 Date.now() 毫秒）和这份日志（相对 T0 的秒）要对表，
# 差多少毫秒才算得出「刷新那一下到生成器收到 GeneratorExit 之间隔了多久」。没有这一行只能靠
# 1 秒一轮询的近似（上一轮我那样推过一版「55ms」，那种推法站不住，这一版当场量）。
log("boot.epoch", t0=time.time(), pid=__import__("os").getpid(), timeout=my_ui.APPROVAL_TIMEOUT,
    gradio=__import__("gradio").__version__, planning=my_ui.agent.planning_interval)
print("[v18_ui] port=%s db=%s log=%s" % (port, db, LOG))
my_ui.DB_PATH = db
my_ui.OpsUI(my_ui.agent, file_upload_folder="./data").launch(
    share=False, server_name="127.0.0.1", server_port=port, css=my_ui.DARK_CSS
)
