# -*- coding: utf-8 -*-
"""D8 基线的对表面：把四条场景的浏览器侧与服务端侧拉到一张表上读。

只读现成产物，不起进程、不打模型：
  run/v18_live_summary_<tag>.out   （库里行数、计数）
  run/v18_probe_<tag>.server.log   （v18_ui.py 那五层包装打的点，相对 t0 的秒）
  run/v18_live_cdp_<tag>.out       （浏览器侧每步 Date.now() 毫秒）
  run/v18_live_<tag>.sqlite3       （ messages / memory 里到底落了什么）

断开这一路的「刷新那一下 → 生成器收到 GeneratorExit 隔了多久」要两份时钟对表：
服务端日志只给相对秒，绝对锚点是 boot.epoch 那一行的 t0。

用法：python3 v18_baseline_table.py [tag ...]   默认 B0 B1 B2 B3
"""
import json
import pathlib
import re
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
TAGS = sys.argv[1:] or ["B0", "B1", "B2", "B3", "B4"]


def lines(tag):
    p = RUN / ("v18_probe_%s.server.log" % tag)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def grab(ls, key):
    """同名行可能有多条（settle_all 一题里跑两次），取第一条命中的整行。"""
    return next((ln for ln in ls if key in ln), None)


def grab_last(ls, key):
    """取最后一条：刷新一次就有两条 on_load（进页面一条、reload 后又一条），要的是后一条。"""
    hits = [ln for ln in ls if key in ln]
    return hits[-1] if hits else None


def rel(ln):
    m = re.search(r"t=\s*([\d.]+)", ln or "")
    return float(m.group(1)) if m else None


def epoch(ln):
    m = re.search(r"t0=([\d.]+)", ln or "")
    return float(m.group(1)) if m else None


def cdp(tag):
    p = RUN / ("v18_live_cdp_%s.out" % tag)
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8").split("STDERR:")[0]
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"_unparsed": txt[:200]}


def summary_line(tag, needle):
    p = RUN / ("v18_live_summary_%s.out" % tag)
    if not p.exists():
        return "（无 summary）"
    return next((ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if needle in ln), "（无这一行）")


def db(tag):
    p = RUN / ("v18_live_%s.sqlite3" % tag)
    if not p.exists():
        return None
    c = sqlite3.connect(str(p))
    with c:
        n = {t: c.execute("select count(*) from %s" % t).fetchone()[0] for t in ("sessions", "messages", "memory")}
        msgs = c.execute("select role, length(content), substr(content,1,60) from messages order by id").fetchall()
        mem = c.execute("select length(payload), payload from memory").fetchall()
    c.close()
    return n, msgs, mem


out = ["# D8 基线对表（生成于 %s，脚本 v18_baseline_table.py，只读现成产物）" %
       __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
       "# 场景：B0 对照允许跑完 ｜ B1 挂在待批上刷新页面 ｜ B2 挂在待批上 SIGKILL ｜ B3 挂在待批上 SIGINT ｜ B4 挂在待批上按 ■ 停止", ""]

for tag in TAGS:
    ls = lines(tag)
    c = cdp(tag)
    be = grab(ls, "boot.epoch")
    gx = grab(ls, "respond.GeneratorExit")
    fin = grab(ls, "respond.finally")
    st = grab(ls, "stream.finally")
    ses = [ln for ln in ls if "settle_all.enter" in ln]
    se = next((ln for ln in ses if not ln.rstrip().endswith("ids=-")), None) or (ses[0] if ses else None)
    dec = grab(ls, "ap.decide")
    sav = grab(ls, "save.enter")
    smem = grab(ls, "save_memory.enter")
    # 这三行只有**修好之后**的产品才会有：基线那四次跑（2026-11-02）里没有 _mark_interrupted，
    # _on_load 的探针包装也是这一刀才加的，所以旧产物上读到「无」是对的，不是脚本坏了。
    mk_in = grab(ls, "mark.enter")
    mk_out = grab(ls, "mark.exit")
    onload = grab_last(ls, "on_load")
    reload_at = c.get("P8-reload#reloadAt")

    row = ["## %s" % tag,
           "  note            %s" % summary_line(tag, "场景 " + tag),
           "  boot t0         %s" % (be or "（无 boot.epoch 这一行）"),
           "  respond.GX      %s" % (gx or "无（这一路生成器没收到 GeneratorExit）"),
           "  respond.finally %s" % (fin or "无"),
           "  stream.finally  %s" % (st or "无"),
           "  settle_all      %s" % (se or "无"),
           "  ap.decide       %s" % (dec or "无（这一路没人结算，直到超时或进程没）"),
           "  mark.enter      %s" % (mk_in or "无（这一路没走断开收尾：改前产品 / 或不是断开场景）"),
           "  mark.exit       %s" % (mk_out or "无"),
           "  on_load(末次)   %s" % (onload or "无（这一路没有刷新页面，也没有第二次进页面）"),
           "  save.enter      %s" % (sav or "无（一次库都没落）"),
           "  save_memory     %s" % (smem or "无"),
           "  库里            %s" % summary_line(tag, "库里").split("库里")[-1].lstrip("：: "),
           "  屏上·扳机前     %s" % c.get("P6-status-before", "-"),
           "  屏上·措辞前     %s" % c.get("P7b-mark-before", "（这一版剧本还没测措辞）")]
    if reload_at:
        row.append("  屏上·reload 后  %s" % c.get("P11-after-status", "-"))
    elif c.get("P8-stop#click"):
        row.append("  屏上·按停止后    %s" % c.get("P9-await-settled", "-"))
    elif c.get("P8-approve#click"):
        row.append("  屏上·答完后      %s" % c.get("P9-await-done#pred", "-"))
    else:
        row.append("  屏上·扳机后      %s（这一路没有 reload：杀进程前后是同一屏，这条是死屏上最后一帧）"
                   % c.get("P11-after-status", "-"))
    row.append("  屏上·措辞末     %s" % c.get("P12-mark-after", "（同上）"))
    if be and gx and reload_at:
        lag = rel(gx) + epoch(be) - reload_at / 1000.0
        row.append("  断开延迟        %.3f s（reload 点击 %s → 生成器收到 GeneratorExit，两份时钟对表）"
                   % (lag, "%.3f" % (reload_at / 1000.0)))
    elif reload_at:
        row.append("  断开延迟        算不了（这份日志没有 boot.epoch 绝对锚点，只能重测）")
    d = db(tag)
    if d:
        n, msgs, mem = d
        row.append("  落库内容        messages %d 条 / memory %d 条" % (n["messages"], len(mem)))
        for role, ln_, head in msgs:
            row.append("     - %-9s %4d B  %s" % (role, ln_, head.replace("\n", "\\n")))
        for ln_, payload in mem:
            row.append("     o memory  %4d B  %s" % (ln_, payload[:220].replace("\n", "\\n")))
    out.append("\n".join(row))
    out.append("")

print("\n".join(out))
