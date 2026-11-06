# -*- coding: utf-8 -*-
"""v1.9 侧栏删除的离线断言：不起进程、不打模型、不碰真库（全部走 tempfile 里的新库）。

三组各管一件事：
  A 存储层（History.delete）：删一条 = 连带它的 messages + memory，别的会话一根毛不动。
  B 复活路径（History.ensure）：拿着一个已被删除的 id 再提问，不炸 IntegrityError，改成新开一条。
    B1 先**把不设防的那一路复现一遍**（直接对已删 id 插 messages），证明这条守卫不是想象的风险。
  C 事件层（OpsUI._delete_session）：六格输出的槽位、生成中不删、第二下才删、换会话/新会话/提问作废。

跑法：smolagents/.venv/bin/python 验收脚本/v1.9/v19_test_delete.py
退出码 0 = 全绿。
"""
import json
import os
import sqlite3
import sys
import tempfile
import types

import os, pathlib, tempfile  # noqa: E402  审计隔离：2026-11-04 23:12 的回归复跑把 62 行
# 测试流量写进了真的 smolagents/.agent-audit.jsonl（那 62 行已挪进 v2.0/run/ 留证）。
# 这一套会构造真 OpsUI／真工具，凡是真跑一步的都要落审计行——所以落点必须在 import 之前
# 就指走。setdefault：外面显式给了 AGENT_AUDIT_PATH 时听外面的。
os.environ.setdefault("AGENT_AUDIT_PATH",
                      str(pathlib.Path(tempfile.mkdtemp(prefix="audit-off-")) / "test.jsonl"))
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr  # noqa: E402

import my_mcp  # noqa: E402
import my_ui  # noqa: E402

FAIL = []
N = 0


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-34s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


def msg(text, role="user"):
    return gr.ChatMessage(role=role, content=text, metadata={"title": "t"})


def raw(path, sql, args=()):
    """绕过 History 直接查库——断言要独立于被测代码的读法。"""
    con = sqlite3.connect(path)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def noop(out):
    """gr.update() 在这个版本是一个 dict：{'__type__': 'update'}，没设过的键根本不出现。
    「这一格不动」= 里面没有 value，也没有 choices。"""
    return isinstance(out, dict) and out.get("__type__") == "update" and "value" not in out and "choices" not in out


def value_of(out):
    return out.get("value") if isinstance(out, dict) else out


def seeded(tmp):
    """两条会话：甲 3 条消息 + 1 份记忆，乙 2 条消息 + 1 份记忆。返回 (hist, 甲, 乙)。"""
    h = my_ui.History(os.path.join(tmp, "h.sqlite3"))
    a, b = h.ensure(None), h.ensure(None)
    h.save(a, [msg("甲问"), msg("甲答", "assistant"), msg("甲问二")])
    h.save(b, [msg("乙问"), msg("乙答", "assistant")])
    h.save_memory(a, json.dumps({"fmt": "v2", "steps": []}))
    h.save_memory(b, json.dumps({"fmt": "v2", "steps": []}))
    return h, a, b


# ---- A 存储层 -------------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="v19_del_a_")
h, a, b = seeded(tmp)
n = h.delete(a)
ok("A1 会话行删除", raw(h.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(0,)])
ok("A2 消息连带清空", raw(h.path, "SELECT count(*) FROM messages WHERE session_id=?", (a,)) == [(0,)])
ok("A3 记忆连带清空", raw(h.path, "SELECT count(*) FROM memory WHERE session_id=?", (a,)) == [(0,)])
ok("A4 别的会话完好", raw(h.path, "SELECT count(*) FROM messages WHERE session_id=?", (b,)) == [(2,)]
   and raw(h.path, "SELECT count(*) FROM memory WHERE session_id=?", (b,)) == [(1,)])
ok("A5 返回的行数如实", n == {"session": 1, "messages": 3, "memory": 1}, str(n))
ok("A6 侧栏不再列出甲", all(v != str(a) for _, v in h.choices()) and any(v == str(b) for _, v in h.choices()))
ok("A7 重复删除不抛", h.delete(a) == {"session": 0, "messages": 0, "memory": 0})
ok("A8 删除不存在的 id", h.delete(9999) == {"session": 0, "messages": 0, "memory": 0})

# ---- B 复活路径 -----------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="v19_del_b_")
h, a, b = seeded(tmp)
h.delete(a)
con = sqlite3.connect(h.path)
con.execute("PRAGMA foreign_keys = ON")
try:
    con.execute("INSERT INTO messages(session_id, ord, role, content, meta) VALUES (?,?,?,?,'{}')",
                (a, 0, "user", "半截内容"))
    raised = None
except sqlite3.IntegrityError as exc:
    raised = str(exc)
finally:
    con.rollback()
    con.close()
ok("B1 已删 id 插消息确实撞外键", raised is not None, raised or "没抛，CASCADE 前提变了")
new = h.ensure(a)
ok("B2 ensure 认出已删 id 并另开一条", new != a and h.exists(new))
ok("B3 exists 的判断", not h.exists(a) and h.exists(b) and not h.exists(None) and h.ensure(b) == b)
try:
    h.save(new, [msg("新的一题")])
    saved = raw(h.path, "SELECT count(*) FROM messages WHERE session_id=?", (new,)) == [(1,)]
except sqlite3.IntegrityError:
    saved = False
ok("B4 新行照常可存", saved)
ok("B5 另开的那条是干净的新会话", next((t for t, v in h.choices() if v == str(new)), "") == "新的一题")

# ---- C 事件层 -------------------------------------------------------------
def ui(tmpdir):
    """不走 __init__（那会建整个界面、装三道门、连模型）。删除这一刀只需要
    hist + 那几个会话字段 + _status_html 依赖的 _stats 形状。"""
    u = my_ui.OpsUI.__new__(my_ui.OpsUI)
    # v2.0 A2：_status_html 多了 MCP 那一格（self._mcp.describe()）。空桥＝「未配置 server」，
    # 这一格在这里要的正是「没有外部工具」，删除那六格的形状与本闸的口径都不受影响。
    u._mcp = my_mcp.Bridge()
    os.makedirs(tmpdir, exist_ok=True)
    u.hist = my_ui.History(os.path.join(tmpdir, "ui.sqlite3"))
    u._state = "idle"
    u._sid = None
    u._sid_shown = None
    u._plan_shown = None
    u._armed_del = None
    u._mem = {}
    u._mem_sid = None
    u._run_in = u._run_out = 0
    u._run_secs = 0.0
    u._run_wait = 0.0
    u.agent = types.SimpleNamespace(
        max_steps=8,
        model=types.SimpleNamespace(model_id="qwen-plus"),
        memory=types.SimpleNamespace(steps=[]),
        monitor=types.SimpleNamespace(
            get_total_token_counts=lambda: types.SimpleNamespace(input_tokens=0, output_tokens=0)),
        logger=types.SimpleNamespace(log_error=lambda m: None),
    )
    my_ui.OpsUI._pending.clear()
    my_ui.OpsUI._ap_cards.clear()
    return u


tmp = tempfile.mkdtemp(prefix="v19_del_c_")
u = ui(tmp)
a, b = u.hist.ensure(None), u.hist.ensure(None)
u.hist.save(a, [msg("甲问"), msg("甲答", "assistant")])
u.hist.save_memory(a, json.dumps({"fmt": "v2", "steps": []}))
u.hist.save(b, [msg("乙问")])
u._mem[a] = types.SimpleNamespace(steps=[])
u._mem[b] = types.SimpleNamespace(steps=[])

out = u._delete_session(None)
ok("C0 未选中也是六格", len(out) == 6, str(len(out)))
ok("C1 未选中不删任何东西", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)])
ok("C2 未选中的回执", "先在左边点一条会话" in out[2])
ok("C3 未选中不碰屏幕三格", noop(out[1]) and noop(out[3]) and noop(out[4]))

u._state = "running"
out = u._delete_session(str(a))
ok("C4 生成中不删", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)]
   and u._armed_del is None)
ok("C5 生成中的回执", "生成中不能删除" in out[2], out[2][-60:])
ok("C6 生成中的状态格仍是生成中", "st-running" in out[2])
ok("C7 生成中不碰屏幕三格", noop(out[1]) and noop(out[3]) and noop(out[4]))

u._state = "idle"
u._sid = str(a)
u._sid_shown = str(a)
out = u._delete_session(str(a))
ok("C8 第一下没删", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)]
   and raw(u.hist.path, "SELECT count(*) FROM memory WHERE session_id=?", (a,)) == [(1,)])
ok("C9 武装记的是这一条", u._armed_del == str(a))
ok("C10 按钮换成确认文案", value_of(out[5]) == "⚠ 确认删除？", repr(value_of(out[5])))
ok("C11 回执带着会话标题", "甲问" in out[2] and "不可恢复" in out[2], out[2][-70:])
ok("C12 武装这一帧不碰屏幕", noop(out[1]) and noop(out[4]) and out[0] == str(a))

out = u._delete_session(str(a))
ok("C13 第二下删干净", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(0,)]
   and raw(u.hist.path, "SELECT count(*) FROM messages WHERE session_id=?", (a,)) == [(0,)])
ok("C14 槽位：sid 归 None、屏幕清空", out[0] is None and out[1] == [])
ok("C15 侧栏刷新且不再含甲", "choices" in out[3] and all(v != str(a) for _, v in u.hist.choices()))
ok("C16 进程里那份记忆一起摘", a not in u._mem and b in u._mem)
ok("C17 按钮文案复位", value_of(out[5]) == "🗑 删除", repr(value_of(out[5])))
ok("C18 回执报的是这条的数量", "已删除" in out[2] and "2 条消息" in out[2] and "1 份模型记忆" in out[2], out[2][-70:])
ok("C19 高亮与绑定一起清", u._sid is None and u._armed_del is None and u._plan_shown is None)
ok("C20 乙没被牵连", raw(u.hist.path, "SELECT count(*) FROM messages WHERE session_id=?", (b,)) == [(1,)])
ok("C21 删完再点一下：未选中，不删乙", "先在左边点一条会话" in u._delete_session(None)[2]
   and raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)])

# C22..C25 武装之后换会话：作废，且两下落在**换到的那一条**上
u = ui(tmp + "/c2")
a, b = u.hist.ensure(None), u.hist.ensure(None)
u.hist.save(a, [msg("甲问")])
u.hist.save(b, [msg("乙问")])
u._mem[a] = types.SimpleNamespace(steps=[])
u._select_session(str(a))
u._delete_session(str(a))
ok("C22 武装在甲", u._armed_del == str(a))
u._select_session(str(b))
ok("C23 换会话即作废", u._armed_del is None)
u._delete_session(str(b))
ok("C24 对乙的第一下只是重新武装", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)]
   and u._armed_del == str(b))
u._delete_session(str(b))
ok("C25 第二下删的是乙、甲完好", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(0,)]
   and raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)])

# C26 武装后点「＋ 新会话」：作废
u = ui(tmp + "/c3")
a = u.hist.ensure(None)
u.hist.save(a, [msg("甲问")])
u._sid = str(a)
u._delete_session(str(a))
out = u._new_session()
ok("C26 新会话作废武装、甲还在", u._armed_del is None
   and raw(u.hist.path, "SELECT count(*) FROM sessions") == [(1,)] and out[0] is None and len(out) == 5)

# C27 武装后提问（同一题跑完）：作废。假流不让它真起 worker 线程。
u = ui(tmp + "/c4")
a = u.hist.ensure(None)
u.hist.save(a, [msg("甲问")])
u._mem[a] = types.SimpleNamespace(steps=[])
u._sid = str(a)
u._delete_session(str(a))
u._stream_response = lambda message, history: iter(())
frame = next(u._respond("再问一句", str(a)))
ok("C27 提问开局作废武装", u._armed_del is None and u._state == "done" and len(frame) == 8)
ok("C28 这一问之后删甲仍需两下", u._delete_session(str(a)) and u._armed_del == str(a)
   and raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)])
ok("C29 第二下才真删", (u._delete_session(str(a)) or True)
   and raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(0,)])

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(0 if not FAIL else 1)
