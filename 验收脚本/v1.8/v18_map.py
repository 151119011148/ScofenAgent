# -*- coding: utf-8 -*-
"""v1.7(1,253) -> v1.8(1,758) 的行映射：逐行等值映射，缺失行用最近邻往下落。

两个方向都从 .rollback 整版存档读，不读现网文件（现网那份已被并发会话改到 1,910 行）。
"""
import difflib
import json
import pathlib

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
V = ROOT / "验收脚本/v1.8"
A = (ROOT / ".rollback/v1.7/my_ui.py").read_text(encoding="utf-8").splitlines()
B = (ROOT / ".rollback/v1.8/my_ui.py").read_text(encoding="utf-8").splitlines()

m = {}
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        for k in range(i2 - i1):
            m[i1 + k + 1] = j1 + k + 1
    else:
        tgt = j1 + 1 if j1 < len(B) else len(B)
        for k in range(max(i2 - i1, 0)):
            m[i1 + k + 1] = tgt

for n in range(1, len(A) + 1):
    if n not in m:
        m[n] = min(m.get(n - 1, 1) + 1, len(B))

json.dump({str(k): v for k, v in sorted(m.items())}, open(str(V / "run/v18_map17.json"), "w"))
moved = sum(1 for k, v in m.items() if v != k)
print("v1.7 %d 行 -> v1.8 %d 行；映射 %d 条，其中行号发生移动 %d 条" % (len(A), len(B), len(m), moved))
print("样例:", [(k, m[k]) for k in (1, 30, 34, 63, 132, 388, 519, 749, 900, 1007, 1183, 1240, 1253)])
