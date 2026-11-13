# -*- coding: utf-8 -*-
"""文档闸的**负控**（v2.0）：故意把锚点、手册、看板改坏，验三道闸会不会红。

为什么要有这一份：一份永远不会红的闸门等于没有闸门。v1.7 起 Mermaid 闸就要求
「正例全过 ＋ 负例必须判红」，v1.8 把这条扩到锚点闸与浏览器闸，本轮再扩到静态闸
（它这一轮新加了五条断言，每一条都得证明自己抓得住对应的坏）。

三类负例：
  A. 锚点（合成一份小文档喂共用判据层，四类缺陷各一条 ＋ 两条正例）。
     四个坏号都是**当场对着 .rollback/v2.0-现场-20261113/ 那把尺子挑的**，不是抄 v1.8：
       `my_ui.py:2400`               越界（尺子 2,315 行）
       `my_ui.py:950`                指向空行（`_install_gate` 实到 949）
       `my_coding_agent.py:111-151`  越过函数末尾（`guarded` 实到 148，151 是 `@tool`）
       `my_audit.py:52-112`          一条区间并了四个函数（`begin` 实到 62）
     正例 `my_coding_agent.py:111-148`／`my_ui.py:920-949` 一条都不许报。
  B. 浏览器闸：手册副本注入三处坏（title 退回 v1.9、一行 done 翻成 todo、
     改掉一个**真被 href 引用的** id 造死锚点），跑 `v20_manual_check.js` 看它判红几条。
  C. 静态闸：另一份副本注入七处坏，一处对应一条断言（外部资源／重复 id／pill 与 data-st
     不符／缺筛选器／删一行看板／工单号重号／死锚点），跑 `v20_gate_static.py <副本>`。

判据：**每一条注入的缺陷都被抓到 ＋ 正例没被误报 ＋ 脚本退出码非 0**，缺一判负控失败。
跑法（cwd=ai学习）：python3 验收脚本/v2.0/v20_gate_neg.py
（B 段要 9344 上那台自己起的 Chrome 活着；没起就先起，别去碰 9457 上另一个会话的。）
"""
from __future__ import absolute_import, print_function

import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v20_gate_anchors as A

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
RUN = os.path.join(ROOT, u"验收脚本", "v2.0", "run")
MANUAL = os.path.join(ROOT, u"agent功能手册.html")

# ---------------- A. 锚点负控
NEG_DOC = os.path.join(RUN, "v20_neg_doc.md")
io.open(NEG_DOC, u"w", encoding=u"utf-8").write(u"\n".join([
    u"# 负控文档（合成，专门喂闸门，不是语料）",
    u"",
    u"| 1 | `my_ui.py:2400` | 越界：超出现行尺子末行 |",
    u"| 2 | `my_ui.py:950` | 指向空行：审批闸装配函数之后那一行 |",
    u"| 3 | `my_coding_agent.py:111-151` | 越过函数末尾：终点是下一只手头上的装饰器 |",
    u"| 4 | `my_audit.py:52-112` | 一条区间并了四个函数 |",
    u"| 5 | `my_coding_agent.py:111-148` | 正例，不该报 |",
    u"| 6 | `my_ui.py:920-949` | 正例，不该报 |",
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

want = {3: (u"越界", [(3, 2400)]), 4: (u"空行", [(4, 950)]),
        5: (u"越过函数末尾", [(5, u"my_coding_agent.py:111-151")]),
        6: (u"区间并多函数", [(6, u"my_audit.py:52-112")])}
got = {u"越界": oob, u"空行": blank, u"越过函数末尾": endpoint, u"区间并多函数": endpoint}
print(u"---- A. 锚点负控（合成文档 %s）----" % NEG_DOC)
a_fail = []
for line_no, (label, exp) in sorted(want.items()):
    for e in exp:
        hit = e in got[label]
        print(u"  %s 注入 文档行%d %s → %s 抓到 %s"
              % (u"ok  " if hit else u"FAIL", line_no, e, label, got[label]))
        if not hit:
            a_fail.append((label, e))
fp = [(l, k) for l, k in blank + oob + endpoint if l in (7, 8)]
print(u"  正例（文档行7、行8）误报 = %s" % (fp or u"无"))
if fp:
    a_fail.append((u"正例被误报", fp))

# ---------------- B. 浏览器闸负控
t = io.open(MANUAL, encoding=u"utf-8").read()
bad = t.replace(u"<title>我的Agent 功能手册与迭代看板 — v2.0</title>",
                u"<title>我的Agent 功能手册与迭代看板 — v1.9</title>", 1)
assert bad != t, u"title 没换成 v1.9，负控文档没造出第一条坏"
m = re.search(r'<tr data-st="done"([^>]*data-p="[^"]+")([^>]*)>\s*<td><b>([^<]+)</b>', bad)
assert m, u"没找到可翻的 done 行"
i = bad.index(u'<tr data-st="done"')
bad = bad[:i] + u'<tr data-st="todo"' + bad[i + len(u'<tr data-st="done"'):]
pill_key = m.group(3)
refs = re.findall(r'href="#([^"]+)"', bad)
assert refs, u"手册里没有一个 #锚点"
dead_id = refs[0]
j = bad.index(u'id="%s"' % dead_id)
bad = bad[:j] + u'id="%s-gone"' % dead_id + bad[j + len(u'id="%s"' % dead_id):]
NEG_HTML = os.path.join(RUN, "v20_neg_manual.html")
io.open(NEG_HTML, u"w", encoding=u"utf-8").write(bad)
print(u"---- B. 浏览器闸负控（坏副本 %s；注入：title 回退 v1.9 ＋ %s 那行 done→todo ＋ 死锚点 %s）----"
      % (NEG_HTML, pill_key.strip(), dead_id))
r = subprocess.run([u"node", os.path.join(HERE, "v20_manual_check.js"), u"1440", u"neg", NEG_HTML],
                   capture_output=True, text=True, timeout=300)
out_b = r.stdout + r.stderr
fl = [l for l in out_b.split(u"\n") if l.startswith(u"  FAIL")]
b_fail = []
for probe, why in ((u"title 带本轮版本号", u"title 回退成 v1.9 没被抓"),
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

# ---------------- C. 静态闸负控（七处坏，一处对一条断言）
c = t
inj = []


def sub1(pat, rep, label, text):
    new, n = re.subn(pat, rep, text, count=1, flags=re.S)
    assert n == 1, u"注入失败：%s（ pattern 没命中）" % label
    inj.append(label)
    return new


# C1 外部资源：这份手册要离线双击能开
c = sub1(r"</body>", u'<script src="https://example.com/neg.js"></script>\n</body>', u"外部资源", c)
# C2 重复 id：拿真 id 再写一遍（不是正文 code 里的示例 id）
c = sub1(r'<span class="cnt"', u'<span id="cnt" class="cnt"', u"重复 id", c)
# C3 pill 与 data-st 不符：只翻胶囊，不动属性
mrow = re.search(r'<tr data-st="done" data-p="\w+">.*?</tr>', c, flags=re.S)
assert mrow, u"没找到 done 行可翻胶囊"
c = c[:mrow.start()] + mrow.group(0).replace(u'class="pill done"', u'class="pill todo"', 1) + c[mrow.end():]
inj.append(u"pill 与 data-st 不符")
# C4 缺一个筛选器按钮
c = sub1(r"<button[^>]*filterBoard\('na'[^>]*>.*?</button>", u"", u"缺筛选器 na", c)
# C5 删一行看板（行数与两分布一起错）
mrow2 = re.search(r'[ \t]*<tr data-st="todo" data-p="P2">.*?</tr>\n', c, flags=re.S)
assert mrow2, u"没找到可删的 todo/P2 行"
c = c[:mrow2.start()] + c[mrow2.end():]
inj.append(u"删一行看板")
# C6 工单号重号：把后一行的号改成前一行的号
tks = re.findall(r'<tr data-st="\w+" data-p="\w+">\s*<td><b>([^<]+)</b>', c)
assert len(tks) >= 2, u"看板不足两行，造不出重号"
c = sub1(r'(<tr data-st="\w+" data-p="\w+">\s*<td><b>)%s(</b>)' % re.escape(tks[1]),
         lambda mm: mm.group(1) + tks[0] + mm.group(2), u"工单号重号", c)
# C7 死锚点：改掉一个真被引用的 id
refs2 = re.findall(r'href="#([^"]+)"', c)
assert refs2, u"没有 #锚点可改"
did = refs2[0]
c = sub1(r'id="%s"' % re.escape(did), u'id="%s-gone"' % did, u"死锚点", c)

NEG_STATIC = os.path.join(RUN, "v20_neg_static.html")
io.open(NEG_STATIC, u"w", encoding=u"utf-8").write(c)
print(u"---- C. 静态闸负控（坏副本 %s；注入 %d 处：%s）----"
      % (NEG_STATIC, len(inj), u"／".join(inj)))
r2 = subprocess.run([sys.executable, os.path.join(HERE, "v20_gate_static.py"), NEG_STATIC],
                    capture_output=True, text=True, timeout=120)
out_c = r2.stdout + r2.stderr
rl = [l for l in out_c.split(u"\n") if l.startswith(u"FAIL")]
c_fail = []
for probe, label in ((u"外部资源", u"外部资源"), (u"重复 id", u"重复 id"),
                     (u"pill 与 data-st 不符", u"pill 与 data-st 不符"),
                     (u"筛选器缺", u"缺筛选器 na"), (u"看板行数", u"删一行看板"),
                     (u"工单号重号", u"工单号重号"), (u"死锚点", u"死锚点")):
    hit = any(probe in l for l in rl)
    print(u"  %s 判红里有「%s」（注入：%s）" % (u"ok  " if hit else u"FAIL", probe, label))
    if not hit:
        c_fail.append(label)
print(u"  闸门退出码 = %d（负控要求非 0）" % r2.returncode)
if r2.returncode == 0:
    c_fail.append(u"exit=0，闸门假通过")
print(u"  判红 %d 条原文：" % len(rl) + u" ｜ ".join(x.strip() for x in rl)[:900])

io.open(os.path.join(RUN, "v20_gate_neg.out"), u"w", encoding=u"utf-8").write(
    u"A 漏抓 %d 类：%s\nB 漏抓 %d 类：%s\nC 漏抓 %d 类：%s\n"
    u"---- node 输出全文 ----\n%s\n---- 静态闸输出全文 ----\n%s"
    % (len(a_fail), a_fail, len(b_fail), b_fail, len(c_fail), c_fail, out_b, out_c))
print(u"---- 负控结论：锚点漏抓 %d ／ 浏览器闸漏抓 %d ／ 静态闸漏抓 %d（留痕 run/v20_gate_neg.out）----"
      % (len(a_fail), len(b_fail), len(c_fail)))
raise SystemExit(1 if (a_fail or b_fail or c_fail) else 0)