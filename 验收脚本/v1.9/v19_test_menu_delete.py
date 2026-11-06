# -*- coding: utf-8 -*-
"""v1.9「⋯ → 删除」的离线断言：不起进程、不打模型、不碰真库（tempfile 新库）。

管的是菜单那条入口独有的六件事，常驻键那一路（_delete_session）由 v19_test_delete.py 管：
  D 通道：payload 的格式与重复投递（同一次点击的 .input/.change 只能算一次）
  E 删邻居：武装→真删，且**屏幕三格不动**（sid/chatbot/plan），只有侧栏重画
  F 删当前选中那条：整段交给 _delete_session，口径不各写一份
  G 生成中：拒绝，措辞和那一路同一句
  H 侧栏是旧的一帧（id 在库里已经没了）：不报错、不闪字，只重画列表
  I 槽位：任何分支都是六格，顺序 [sid, chatbot, status, radio, plan, del_btn]
  J 刷新页面：页内自增号归零，所以 payload 里的「开场号」段不能少——少了那一整页的第一下会被
    当成重复投递**无声**吞掉；而 `_on_load` 同时清了武装，所以正确表现是重新出「确认删除」回执

跑法：smolagents/.venv/bin/python 验收脚本/v1.9/v19_test_menu_delete.py
退出码 0 = 全绿。
"""
import json
import os
import sqlite3
import sys
import tempfile
import types

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
    con = sqlite3.connect(path)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def noop(out):
    return isinstance(out, dict) and out.get("__type__") == "update" and "value" not in out and "choices" not in out


def value_of(out):
    return out.get("value") if isinstance(out, dict) else out


def flash_of(out):
    """status 那一格是整段 HTML，回执就在里面的 <div id="flash">。"""
    return out[2] if isinstance(out[2], str) else ""


def quiet(out):
    """整串输出里既没有回执也没有报错文案 —— 「这一次什么都没发生」的判据。"""
    return all("已删除" not in str(o) and "确认删除" not in str(o) and "不能删除" not in str(o) for o in out)


def ui(tmpdir):
    u = my_ui.OpsUI.__new__(my_ui.OpsUI)
    u._mcp = my_mcp.Bridge()
    os.makedirs(tmpdir, exist_ok=True)
    u.hist = my_ui.History(os.path.join(tmpdir, "ui.sqlite3"))
    u._state = "idle"
    u._sid = None
    u._sid_shown = None
    u._plan_shown = None
    u._armed_del = None
    u._del_nonce = ""
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


def seeded(tmpdir):
    """三条会话：甲（选中那条）、乙（邻居）、丙（用来当"旧一帧"里已被删掉的 id）。"""
    u = ui(tmpdir)
    a, b, c = u.hist.ensure(None), u.hist.ensure(None), u.hist.ensure(None)
    u.hist.save(a, [msg("甲问"), msg("甲答", "assistant")])
    u.hist.save(b, [msg("乙问"), msg("乙答", "assistant"), msg("乙问二")])
    u.hist.save(c, [msg("丙问")])
    u.hist.save_memory(b, json.dumps({"fmt": "v2", "steps": []}))
    u._mem[a] = types.SimpleNamespace(steps=[])
    u._mem[b] = types.SimpleNamespace(steps=[])
    u._mem[c] = types.SimpleNamespace(steps=[])
    u._sid = u._sid_shown = str(a)
    return u, a, b, c


# ---- D 通道：格式与重复投递 -----------------------------------------------
tmp = tempfile.mkdtemp(prefix="v19_menu_d_")
u, a, b, c = seeded(tmp)
out = u._menu_delete("没有@的串")
ok("D0 任何输入都是六格", len(out) == 6, str(len(out)))
ok("D1 缺 @ 整串不认", quiet(out) and all(noop(o) for o in out), str(out[2])[:60])
out = u._menu_delete("abc@1")
ok("D2 id 不是数字不认", quiet(out) and all(noop(o) for o in out))
out = u._menu_delete("")
ok("D3 空 payload 不认", quiet(out) and all(noop(o) for o in out))
out = u._menu_delete(None)
ok("D4 None 也不炸", quiet(out) and all(noop(o) for o in out))

out = u._menu_delete(f"{b}@1")
ok("D5 第一下是武装不是删", "确认删除" in flash_of(out) and "乙问" in flash_of(out), flash_of(out)[-70:])
ok("D6 武装这一帧库里没动", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)]
   and raw(u.hist.path, "SELECT count(*) FROM messages WHERE session_id=?", (b,)) == [(3,)])
ok("D7 武装只动状态条", noop(out[1]) and noop(out[3]) and noop(out[4]) and noop(out[5]) and out[0] == str(a))
ok("D8 回执教的是怎么确认", "再点一次这一行的「⋯ → 删除」" in flash_of(out), flash_of(out)[-40:])

# 同一次点击的第二次投递（.input 之后 .change 也来了）：必须整格退回
out = u._menu_delete(f"{b}@1")
ok("D9 同号重复投递吞掉", all(noop(o) for o in out), str(out)[:80])
ok("D10 吞掉之后库里还是没动", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)])

# ---- E 删邻居：第二下真删，屏幕不动 --------------------------------------
out = u._menu_delete(f"{b}@2")
ok("E1 第二下删干净", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(0,)]
   and raw(u.hist.path, "SELECT count(*) FROM messages WHERE session_id=?", (b,)) == [(0,)]
   and raw(u.hist.path, "SELECT count(*) FROM memory WHERE session_id=?", (b,)) == [(0,)])
ok("E2 别的会话一根毛不动", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id IN (?,?)", (a, c)) == [(2,)]
   and raw(u.hist.path, "SELECT count(*) FROM messages WHERE session_id=?", (a,)) == [(2,)])
ok("E3 回执报的是这条的数量", "已删除" in flash_of(out) and "3 条消息" in flash_of(out)
   and "1 份模型记忆" in flash_of(out), flash_of(out)[-70:])
ok("E4 删邻居不动屏幕", out[0] == str(a) and noop(out[1]) and noop(out[4]), f"sid={out[0]!r} chatbot={out[1]!r}")
ok("E5 只有侧栏重画", isinstance(out[3], dict) and "choices" in out[3]
   and all(v != str(b) for _, v in u.hist.choices()), str(out[3].get("value")))
ok("E6 进程里那份记忆一起摘", b not in u._mem and a in u._mem and c in u._mem)
ok("E7 武装状态清空", u._armed_del is None and u._del_nonce == f"{b}@2")
ok("E8 常驻键的文案没被带跑", noop(out[5]), str(out[5]))
ok("E9 绑定与会话对象都没变", u._sid == str(a) and u._plan_shown is None)

# 删完紧接着删第三条：号必须是新的，武装重新开始，不许一次点完
out = u._menu_delete(f"{c}@2")
ok("E10 换一个号才会重新武装", "确认删除" in flash_of(out) and "丙问" in flash_of(out), flash_of(out)[-60:])
ok("E11 同一次点击的重复投递照样吞", all(noop(o) for o in u._menu_delete(f"{c}@2")))
out = u._menu_delete(f"{c}@3")
ok("E12 第三条件也删得掉", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (c,)) == [(0,)]
   and "已删除" in flash_of(out), flash_of(out)[-60:])

# ---- F 删的正是当前选中那条：整段走 _delete_session ------------------------
tmp = tempfile.mkdtemp(prefix="v19_menu_f_")
u, a, b, c = seeded(tmp)
out = u._menu_delete(f"{a}@1")
ok("F1 第一下由那一路武装", "确认删除" in flash_of(out) and "甲问" in flash_of(out), flash_of(out)[-70:])
ok("F2 六格槽位是那一路的（按钮换文案）", value_of(out[5]) == "⚠ 确认删除？", str(out[5]))
out = u._menu_delete(f"{a}@2")
ok("F3 第二下删掉选中那条", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(0,)])
ok("F4 删完回到没有选中", out[0] is None and out[1] == [], f"sid={out[0]!r} chatbot={out[1]!r}")
ok("F5 按钮文案复位", value_of(out[5]) == "🗑 删除", str(out[5]))
ok("F6 绑定与计划一起清", u._sid is None and u._armed_del is None and u._plan_shown is None)

# ---- G 生成中不删 ----------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="v19_menu_g_")
u, a, b, c = seeded(tmp)
u._state = "running"
out = u._menu_delete(f"{b}@1")
ok("G1 生成中不删任何东西", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)])
ok("G2 回执和常驻键同一句", "生成中不能删除" in flash_of(out) and "先按 ■ 停止" in flash_of(out), flash_of(out)[-60:])
ok("G3 状态条跟着这一档染色", "st-running" in out[2], out[2][:60])
ok("G4 不碰屏幕三格", noop(out[1]) and noop(out[3]) and noop(out[4]))
u._state = "stopping"
out = u._menu_delete(f"{b}@2")
ok("G5 停止中同样不删", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)]
   and "生成中不能删除" in flash_of(out))
u._state = "idle"
out = u._menu_delete(f"{b}@3")
ok("G6 停了之后这一路还能删", "确认删除" in flash_of(out))

# ---- H 侧栏是旧的一帧（id 已经不在库里）-----------------------------------
tmp = tempfile.mkdtemp(prefix="v19_menu_h_")
u, a, b, c = seeded(tmp)
u.hist.delete(b)                       # 别的页面先删了
u._armed_del = None
out = u._menu_delete(f"{b}@7")
ok("H1 已不存在的行不报错", all("已删除" not in str(o) and "确认删除" not in str(o) for o in out), str(out[2])[:80])
ok("H2 也不误删当前这条", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (a,)) == [(1,)]
   and out[0] == str(a) and noop(out[1]))
ok("H3 只重画侧栏（旧行就此消失）", isinstance(out[3], dict) and "choices" in out[3]
   and all(v != str(b) for _, v in u.hist.choices()))
u._armed_del = str(b)
out = u._menu_delete(f"{b}@8")
ok("H4 行没了就把武装一起清", u._armed_del is None)
out = u._menu_delete(f"{b}@9")
ok("H5 连点两下都只有重画、没有回执", noop(out[2]) and "choices" in out[3] and out[0] == str(a), str(out[2])[:60])

# ---- I 槽位与那一路同型 ----------------------------------------------------
tmp = tempfile.mkdtemp(prefix="v19_menu_i_")
u, a, b, c = seeded(tmp)
u._sid = u._sid_shown = None
out = u._menu_delete(f"{b}@1")
ok("I1 没选中时删邻居照样走得通", "确认删除" in flash_of(out) and out[0] is None, str(out[0]))
out = u._menu_delete(f"{b}@2")
ok("I2 第二下真删且不碰屏幕", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(0,)]
   and out[0] is None and noop(out[1]))
ok("I3 六格里没有 gr.update 之外的意外类型",
   all(isinstance(o, (dict, str, list, type(None), int)) for o in out), str([type(o).__name__ for o in out]))
ok("I4 模块里两条入口都在", hasattr(my_ui.OpsUI, "_delete_session") and hasattr(my_ui.OpsUI, "_menu_delete"))
ok("I5 SIDEBAR_JS 是个箭头函数串",
   my_ui.SIDEBAR_JS.lstrip().startswith("()") and my_ui.SIDEBAR_JS.count("{") == my_ui.SIDEBAR_JS.count("}"),
   str(my_ui.SIDEBAR_JS.lstrip()[:12]))

# ---- J 刷新页面后的两次点击 -----------------------------------------------
# 页内自增号会随刷新归零：串里若只有「第几次点击」，刷新前武装的那次和刷新后第一次点击会撞成
# 同一串，后端按重复投递吞掉——界面表现为「刷新后按删除没反应」。注意刷新同时走 `_on_load`，
# 那里**故意**把武装清掉（刷新后确认重新开始，一次点击删不掉），所以正确的口径是：新页第一下
# 该重新给出「确认删除」回执，而不是被无声吞掉，更不是直接删。
tmp = tempfile.mkdtemp(prefix="v19_menu_j_")
u, a, b, c = seeded(tmp)
out = u._menu_delete(f"{b}@aaa-1")
ok("J1 刷新前先把这一行武装", "确认删除" in flash_of(out) and u._armed_del == str(b), flash_of(out)[-40:])
u._armed_del = None                      # 照着 _on_load 那一行做：刷新把武装清掉，nonce 留着
out = u._menu_delete(f"{b}@aaa-1")
ok("J2 撞号的串确实会被当重复投递吞掉（旧前端的毛病）",
   all(noop(o) for o in out) and u._armed_del is None, str(out)[:80])
out = u._menu_delete(f"{b}@bbb-1")
ok("J3 换了开场号就重新武装、有回执", "确认删除" in flash_of(out) and u._armed_del == str(b), flash_of(out)[-60:])
ok("J4 回执这一帧库里还没动", raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(1,)])
out = u._menu_delete(f"{b}@bbb-2")
ok("J5 同页第二下才真删", "已删除" in flash_of(out)
   and raw(u.hist.path, "SELECT count(*) FROM sessions WHERE id=?", (b,)) == [(0,)], flash_of(out)[-60:])
ok("J6 前端送的是两段号（开场号＋页内第几次）",
   "+ '@' + boot" in my_ui.SIDEBAR_JS and "Date.now().toString(36)" in my_ui.SIDEBAR_JS
   and "(++seq)" in my_ui.SIDEBAR_JS)

print()
print("断言 %d 条，失败 %d 条" % (N, len(FAIL)))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
