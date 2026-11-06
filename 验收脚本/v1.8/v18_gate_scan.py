# -*- coding: utf-8 -*-
"""文档闸·第一道扫（v1.8）：行号**点扫**——每个号指到的是不是一行真代码。

判据（尺子、范围、就近归属、端口/历史号的豁免）全在共用层 `v18_gate_anchors.py`，
和终点扫 `v18_gate_scan3.py` 同一套口径。这一份只干一件事：逐号问 `valid()`。

退出码：有越界 → 1。指向空行**不判红**，逐条打出来交人定性
（v1.7 那轮 3 条全是该留的历史号；v1.8 第一遍扫抓到 1 条真错——`_install_plan_gate` 写成
`:830-884`，884 是函数体后面那个空行，三份文档 4 处一起改成 `:830-883`）。

跑法（cwd=ai学习）：python3 验收脚本/v1.8/v18_gate_scan.py
"""
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v18_gate_anchors as A

print(u"尺子（全部来自 %s，即本轮锚点事实源）：" % A.SNAP)
for k in sorted(A.FILES):
    n = len(A.SRC[k])
    print(u"  %-20s %d 行，末行 %s" % (k, n, u"非空" if A.SRC[k][n - 1].strip() else u"空"))
print(u"注意：现场 smolagents/my_ui.py 现在是 1,910 行（另一个会话的「侧栏删除会话」未归档），"
      u"不作尺子——README 文首第 5 行的口径。")

tot = {k: 0 for k in A.FILES}
tot[u"归外部"] = 0
tot[u"端口"] = 0
oob_all, blank_all, hist_all, ambig_all = [], [], [], []

for name in A.TARGETS:
    items = A.anchors(name)
    hits = oob = blank = skipped = porty = hist = ambig = 0
    for it in items:
        if it["kind"] == u"端口":
            porty += 1
            continue
        if it["kind"] == u"归外部":
            skipped += 1
            continue
        for k in it["nums"]:
            hits += 1
            tot[it["target"]] += 1
            if it["hist"]:
                hist += 1
                hist_all.append((name, it["ln"], it["target"], k, it["raw"], it["text"]))
                continue
            if A.valid(it["target"], k):
                continue
            if any(A.valid(c, k) for c in it["cands"]):
                ambig += 1          # 归属挑错了尺子，但候选里有说得通的
                ambig_all.append((name, it["ln"], it["target"], k, it["raw"]))
                continue
            if all(A.oob(c, k) for c in it["cands"]):
                oob += 1
                oob_all.append((name, it["ln"], it["target"], k, it["raw"], it["text"]))
            else:
                blank += 1
                blank_all.append((name, it["ln"], it["target"], k, it["raw"], it["text"]))
    tot[u"归外部"] += skipped
    tot[u"端口"] += porty
    rng = A.TARGETS[name][1]
    print(u"=== %s：范围 %s → 行号 %d 个，越界 %d，指向空行 %d，归外部跳过 %d，端口/URL 不算 %d，历史号放过 %d，归属歧义但可解释 %d"
          % (name, rng, hits, oob, blank, skipped, porty, hist, ambig))

print(u"---- 分尺子的行号数（事实源 .rollback/v1.8/）----")
for k in sorted(A.FILES):
    print(u"  %-20s %d 个" % (k, tot[k]))
print(u"  跳过（上游/外部文件，本轮无尺子） %d 个" % tot[u"归外部"])
print(u"  端口/URL 冒号                      %d 个" % tot[u"端口"])

if oob_all:
    print(u"---- 越界逐条 ----")
    for x in oob_all[:40]:
        print(u"  %s 行%-5d %s :%d（原文 %s）| %s" % x)
if blank_all:
    print(u"---- 指向空行逐条（不判红，交人定性）----")
    for x in blank_all[:40]:
        print(u"  %s 行%-5d %s :%d（原文 %s）| %s" % x)
if ambig_all:
    print(u"---- 归属歧义但可解释逐条 ----")
    for x in ambig_all[:20]:
        print(u"  %s 行%-5d 归到 %s 却指不到，另一把尺子说通 :%d（原文 %s）" % x)
if hist_all:
    print(u"---- 历史号（`.rollback/v…` 点名的别版快照，或 bare 号左 40 字符标着 v1.0~v1.7），不参与判 ----")
    for x in hist_all[:24]:
        print(u"  %s 行%-5d %s :%d（原文 %s）| %s" % x)

print(u"---- 第一道扫结论 ----")
print(u"越界 %d 条 ／ 指向空行 %d 条" % (len(oob_all), len(blank_all)))
raise SystemExit(1 if oob_all else 0)
