# -*- coding: utf-8 -*-
"""文档闸·静态闸（v1.8 版）：与 2026-10-29 那场同一套判据，只把期望值换成 v1.8 的看板。

判据本体照抄 `验收脚本/v1.3/run/v13_htmlcheck.py`（那是 v1.3 起一直在用的那一份，
`<pre>`/`<script>` 里的示例标签先摘掉、void 标签与自闭合不算未闭合）——
**不改判据、只加断言**：v13 那份只打印不判红，本轮要它参与「五道闸全绿」，所以补上
看板行数与两个分布的期望值，并把结论收敛成退出码。

跑法（cwd=ai学习）：
    smolagents/.venv/bin/python 验收脚本/v1.8/v18_gate_static.py
退出码 0＝全绿；1＝有红（红条逐条打印）。
"""
import re
import sys

PATH = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

# ---- v1.8 看板：41 行 = done 21 + todo 17 + na 3 + doing 0；优先级 D 9 / P0 6 / P1 10 / P2 7 / V 9
EXPECT_ROWS = 41
EXPECT_ST = {"todo": 17, "doing": 0, "done": 21, "na": 3}
EXPECT_P = {"D": 9, "P0": 6, "P1": 10, "P2": 7, "V": 9}

src = open(PATH, encoding="utf-8").read()

pre_only = re.sub(r"<pre>.*?</pre>", "", src, flags=re.S)
script_only = re.sub(r"<script>.*?</script>", "", pre_only, flags=re.S)

stack, errors = [], []
for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", script_only):
    closing, name, rest = m.group(1), m.group(2).lower(), m.group(3)
    if name in VOID or rest.rstrip().endswith("/"):
        continue
    if not closing:
        stack.append((name, m.start()))
    else:
        if not stack:
            errors.append("多余闭合 </%s> @%d" % (name, m.start()))
        elif stack[-1][0] != name:
            errors.append("错配：期望 </%s>（开于 @%d）实得 </%s> @%d"
                          % (stack[-1][0], stack[-1][1], name, m.start()))
            stack.pop()
        else:
            stack.pop()

ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', src)
rows = len(re.findall(r"<tr data-st=", src))
st = {k: len(re.findall(r'data-st="%s"' % k, src)) for k in ("todo", "doing", "done", "na")}
p = {k: len(re.findall(r'data-p="%s"' % k, src)) for k in ("D", "P0", "P1", "P2", "V")}
ids = set(re.findall(r'id="([^"]+)"', src))
dead = [h for h in re.findall(r'href="#([^"]+)"', src) if h not in ids]

print("未闭合:", stack)
print("配对错误:", len(errors))
for e in errors[:10]:
    print("  ", e)
print("外部资源:", len(ext), ext[:5])
print("死锚点:", dead)
print("看板行数: %d（期望 %d）" % (rows, EXPECT_ROWS))
print("data-st 分布: %s（期望 %s）" % (st, EXPECT_ST))
print("data-p  分布: %s（期望 %s）" % (p, EXPECT_P))
print("分布合计: st %d / p %d（都应等于看板行数 %d）" % (sum(st.values()), sum(p.values()), rows))

reds = []
if stack:
    reds.append("未闭合 %d 个" % len(stack))
if errors:
    reds.append("标签配对错误 %d 条" % len(errors))
if ext:
    reds.append("外部资源 %d 条（这份手册要离线能打开）" % len(ext))
if dead:
    reds.append("死锚点 %d 个" % len(dead))
if rows != EXPECT_ROWS:
    reds.append("看板行数 %d ≠ %d" % (rows, EXPECT_ROWS))
if st != EXPECT_ST:
    reds.append("data-st 分布不符")
if p != EXPECT_P:
    reds.append("data-p 分布不符")
if sum(st.values()) != rows or sum(p.values()) != rows:
    reds.append("分布合计与看板行数不自洽")

print("---- 静态闸结论 ----")
if reds:
    for r in reds:
        print("FAIL", r)
    print("红 %d 条" % len(reds))
    sys.exit(1)
print("全绿：未闭合 0 / 配对错误 0 / 外部资源 0 / 死锚点 0 / 看板 %d 行 / 两分布自洽" % rows)
