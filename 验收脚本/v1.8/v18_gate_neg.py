# -*- coding: utf-8 -*-
"""文档闸的**负控**：故意把锚点和手册改坏，验两道闸会不会红。

为什么要有这一份：v1.7 那轮 Mermaid 闸要求「正例全过 ＋ 负例必须 exit=1」，
为的是排除**校验器假通过**。锚点闸和浏览器闸同样是校验器，同样有假通过的可能——
一份永远不会红的闸门，等于没有闸门。

两类负例：
  A. 锚点（合成一份只有 5 行的文档喂给共用判据层，四类缺陷各一条 ＋ 一条正例）：
       `my_ui.py:1900`      越界（现行 1,758 行）
       `my_ui.py:884`       指向空行（`_install_plan_gate` 之后那个空行）
       `my_ui.py:830-890`   越过函数末尾（该函数实到 857）
       `my_ui.py:468-479`   两函数并一条区间（decide 实到 472）
       `my_ui.py:830`       正例，不该报
  B. 浏览器闸：拿手册的一份副本注入三处坏（title 退回 v1.7、一行 done 翻成 todo、
     删掉一个 h2 的 id 造死锚点），跑 `v18_manual_check.js` 看它判红几条。

判据：**每一条注入的缺陷都被抓到 ＋ 正例没被误报 ＋ 脚本退出码非 0**，缺一判负控失败。
跑法（cwd=ai学习）：python3 验收脚本/v1.8/v18_gate_neg.py
"""
from __future__ import absolute_import, print_function

import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v18_gate_anchors as A

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
RUN = os.path.join(ROOT, u"验收脚本", "v1.8", "run")
MANUAL = os.path.join(ROOT, u"agent功能手册.html")

# ---------------- A. 锚点负控
NEG_DOC = os.path.join(RUN, "v18_neg_doc.md")
io.open(NEG_DOC, u"w", encoding=u"utf-8").write(u"\n".join([
    u"# 负控文档（合成，专门喂闸门，不是语料）",
    u"",
    u"| 1 | `my_ui.py:1900` | 越界：现行尺子 1,758 行 |",
    u"| 2 | `my_ui.py:884` | 指向空行：`_install_plan_gate` 之后那一行 |",
    u"| 3 | `my_ui.py:830-890` | 越过函数末尾：该函数实到 857 |",
    u"| 4 | `my_ui.py:468-479` | 两个函数并成一条区间：decide 实到 472 |",
    u"| 5 | `my_ui.py:830` | 正例，不该报 |",
    u"",
]) + u"\n")
A.TARGETS = {u"负控": (NEG_DOC, [(1, 10)])}
A.GATE_SKIP = {}

items = A.anchors(u"负控")
oob, blank, endpoint = [], [], []
for it in items:
    if it["kind"] != u"锚点":
        continue
    for k in it["nums"]:
        if not any(A.valid(c, k) for c in it["cands"]):
            (oob if all(A.oob(c, k) for c in it["cands"]) else blank).append((it["ln"], k))
    if len(it["nums"]) >= 2:
        x, y = it["nums"][0], it["nums"][-1]
        ok = [c for c in it["cands"] if A.valid(c, y)]
        if not ok:
            continue
        c = ok[0]
        sp = A.span(c)
        if A.end_kind(c, y) or (x in sp and y > sp[x][1]):
            endpoint.append((it["ln"], it["raw"]))

want = {3: (u"越界", [(3, 1900)]), 4: (u"空行", [(4, 884)]),
        5: (u"越过函数末尾", [(5, u"my_ui.py:830-890")]), 6: (u"区间并两函数", [(6, u"my_ui.py:468-479")])}
got = {u"越界": oob, u"空行": blank, u"越过函数末尾": endpoint, u"区间并两函数": endpoint}
print(u"---- A. 锚点负控（合成文档 %s）----" % NEG_DOC)
a_fail = []
for line_no, (label, exp) in sorted(want.items()):
    for e in exp:
        hit = e in got[label]
        print(u"  %s 注入 文档行%d %s → %s 抓到 %s" % (u"ok  " if hit else u"FAIL",
                                                    line_no, e, label, got[label]))
        if not hit:
            a_fail.append((label, e))
fp = [(l, k) for l, k in blank + oob if l == 7]
print(u"  正例（文档行7 `my_ui.py:830`）误报 = %s" % (fp or u"无"))
if fp:
    a_fail.append((u"正例被误报", fp))

# ---------------- B. 浏览器闸负控
t = io.open(MANUAL, encoding=u"utf-8").read()
bad = t.replace(u"<title>我的Agent 功能手册与迭代看板 — v1.8</title>",
                u"<title>我的Agent 功能手册与迭代看板 — v1.7</title>", 1)
assert bad != t, u"title 没换成 v1.7，负控文档没造出第一条坏"
# 第二条坏：把第一条 done 行翻成 todo（st 分布 ＋ todo/done 两个筛选器计数一起错）
m = re.search(r'<tr data-st="done"([^>]*data-p="[^"]+")([^>]*)>\s*<td><b>([^<]+)</b>', bad)
assert m, u"没找到可翻的 done 行"
i = bad.index(u'<tr data-st="done"')
bad = bad[:i] + u'<tr data-st="todo"' + bad[i + len(u'<tr data-st="done"'):]
pill_key = m.group(3)
# 第三条坏：造一个死锚点——挑**真被 href 引用的那个 id** 改掉，改一个没人引的 id 是造不出坏的
refs = re.findall(r'href="#([^"]+)"', bad)
assert refs, u"手册里没有一个 #锚点"
dead_id = refs[0]
j = bad.index(u'id="%s"' % dead_id)
bad = bad[:j] + u'id="%s-gone"' % dead_id + bad[j + len(u'id="%s"' % dead_id):]
NEG_HTML = os.path.join(RUN, "v18_neg_manual.html")
io.open(NEG_HTML, u"w", encoding=u"utf-8").write(bad)
print(u"---- B. 浏览器闸负控（坏副本 %s；注入：title 回退 v1.7 ＋ %s 那行 done→todo ＋ 死锚点 %s）----"
      % (NEG_HTML, pill_key.strip(), dead_id))
r = subprocess.run([u"node", os.path.join(HERE, "v18_manual_check.js"), u"1440", u"neg", NEG_HTML],
                   capture_output=True, text=True, timeout=300)
out = r.stdout + r.stderr
fl = [l for l in out.split(u"\n") if l.startswith(u"  FAIL")]
b_fail = []
for probe, why in ((u"title 带本轮版本号", u"title 回退成 v1.7 没被抓"),
                   (u"data-st 分布", u"done→todo 那行没被分布抓到"),
                   (u"cnt=", u"done→todo 那行没被逐个筛选器的 #cnt 抓到"),
                   (u"死锚点", u"改掉 id 造的死锚点没被抓")):
    hit = any(probe in l for l in fl)
    print(u"  %s 判红里有「%s」（%s）" % (u"ok  " if hit else u"FAIL", probe, why))
    if not hit:
        b_fail.append(probe)
print(u"  闸门退出码 = %d（负控要求非 0）" % r.returncode)
if r.returncode == 0:
    b_fail.append(u"exit=0，闸门假通过")
print(u"  判红 %d 条原文：" % len(fl) + u" ｜ ".join(x.strip() for x in fl)[:700])

io.open(os.path.join(RUN, "v18_gate_neg.out"), u"w", encoding=u"utf-8").write(
    u"A 漏抓 %d 类：%s\nB 漏抓 %d 类：%s\nnode 输出全文：\n%s"
    % (len(a_fail), a_fail, len(b_fail), b_fail, out))
print(u"---- 负控结论：锚点漏抓 %d 条 ／ 浏览器闸漏抓 %d 条（留痕 run/v18_gate_neg.out）----"
      % (len(a_fail), len(b_fail)))
raise SystemExit(1 if (a_fail or b_fail) else 0)
