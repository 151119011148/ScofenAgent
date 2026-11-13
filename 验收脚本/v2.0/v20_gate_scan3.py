# -*- coding: utf-8 -*-
"""文档闸·第三道扫（v2.0）：区间引用的**终点**。起点不查（起点是 def 或注释都正常）。

和点扫共用 `v20_gate_anchors.py`：尺子、sha1 前置、范围、就近归属、端口/历史豁免、
`end_kind`、`span` 全在那一层，两道闸不会互相打脸。两档判据：
  1. 终点落进「别的东西里」——空行／下一个 def-class／`#----` 分隔注释／顶格 `# ` 开场注释
     （四档沿用 v1.7/v1.8，含「注释续行」豁免，理由见 `end_kind`）。
  2. 起点是 def 而终点**越过这个函数的真实末尾**（`span`）——插新函数把前面的区间截短了，
     行号对齐器只会搬单点号，这一类一条都不报。**v2.0 这轮的主抓法就是它**：
     `my_coding_agent.py` 256 → 325 行，五只手的 def 全体下移。
多尺子歧义的区间：取「终点指到非空行」的那把尺子来判；一把都说不通的交给点扫报。

退出码：尺子 sha1 对不上 → 2；终点越界 → 1；否则 0。
跑法（cwd=ai学习）：python3 验收脚本/v2.0/v20_gate_scan3.py
"""
from __future__ import absolute_import, print_function

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v20_gate_anchors as A

grand = ranges = 0
for name in A.TARGETS:
    bad, n = [], 0
    for it in A.anchors(name):
        if it["kind"] != u"锚点" or it["hist"] or len(it["nums"]) < 2:
            continue
        x, y = it["nums"][0], it["nums"][-1]
        n += 1
        ok = [c for c in it["cands"] if A.valid(c, y)]
        if not ok:                       # 终点本身就不合格，交给点扫
            continue
        c = ok[0]
        k = A.end_kind(c, y)
        if k:
            bad.append((it["ln"], it["raw"], k, y, c, A.SRC[c][y - 1].strip()[:46], it["text"]))
            continue
        sp = A.span(c)
        if x in sp and y > sp[x][1]:
            bad.append((it["ln"], it["raw"], u"越过函数末尾", y, c,
                        u"该函数实到 %d 行，下一节从 %d 行起" % (sp[x][1], sp[x][1] + 1), it["text"]))
    ranges += n
    grand += len(bad)
    print(u"=== %s：区间 %d 个（终点越进别节／越过函数末尾的 %d 条）" % (name, n, len(bad)))
    for ln, raw, k, y, c, txt, sent in bad:
        print(u"  文档行%-5d %-14s 终点%s 落在 %s 第 %-4d 行：%s | 句子：%s"
              % (ln, raw, k, c, y, txt, sent[:60]))
print(u"---- 第三道扫结论：区间 %d 个，终点越界 %d 条 ----" % (ranges, grand))
raise SystemExit(1 if grand else 0)