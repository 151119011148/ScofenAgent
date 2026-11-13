# -*- coding: utf-8 -*-
"""手册 v1.7 收尾三处：标题版本号、页眉版本行、D8 看板行的排版（去掉 CJK 禁则造成的不可断长串 + 状态胶囊拆分）。"""
import io

P = u"/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
t = io.open(P, encoding="utf-8").read()

EDITS = [
    (u"<title>我的Agent 功能手册与迭代看板 — v1.6</title>",
     u"<title>我的Agent 功能手册与迭代看板 — v1.7</title>"),
    (u"版本 <b>v1.6</b> · 建档 <b>2026-10-28</b> · 最近更新 <b>2026-10-30</b>（上线 <b>V7 侧栏选中态同步 + V8 审批等待时长单列</b>；上一轮 V6 记忆落库 + D7 停止竞态）",
     u"版本 <b>v1.7</b> · 建档 <b>2026-10-28</b> · 最近更新 <b>2026-10-30</b>（上线 <b>V9 审批等待进记忆格式：重启、点旧会话都读得出那一格</b>；上一轮 V7 侧栏选中态同步 + V8 审批等待时长单列）"),
    # D8 行·证据：三份留痕文件名原来是「（A、B、C）」——CJK 行首禁则让 与 、 都不许断行，
    # 整串变成一个 159px 级的原子块，把 §4.1 表格的 min-content 顶到 1,358px（容器 1,080）→ 整页横向滚动。
    # 改成冒号 ＋ 空格分隔，断行点回来，min-content 实测回到 1,038（与 D8 之前逐字相符）。
    (u"<b>v1.7 实跑撞出来的，两条路都有留痕</b>（<code>/tmp/v17_drain.out</code>、<code>/tmp/v17_finish.out</code>、<code>/tmp/v17_peek.out</code>）。",
     u"<b>v1.7 实跑撞出来的，两条路都有留痕：</b><code>/tmp/v17_drain.out</code> <code>/tmp/v17_finish.out</code> <code>/tmp/v17_peek.out</code>。"),
    # D8 行·状态：胶囊 white-space:nowrap，「未开工（v1.7 新立）」整颗不可断 → 比别的行多占 46px。
    (u'<td><span class="pill todo">未开工（v1.7 新立）</span></td>',
     u'<td><span class="pill todo">未开工</span> <span class="ev">v1.7 新立</span></td>'),
]

for old, new in EDITS:
    assert t.count(old) == 1, (t.count(old), old[:60])
    t = t.replace(old, new)

io.open(P, "w", encoding="utf-8").write(t)
print("ok, lines=%d" % len(t.split("\n")))
