# -*- coding: utf-8 -*-
"""v1.6(1,205) -> v1.7(1,253) 的行映射：逐行等值映射，缺失行用最近邻往下落。"""
import difflib
import json
import pathlib

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
A = (ROOT / ".rollback/v1.6/my_ui.py").read_text(encoding="utf-8").splitlines()
B = (ROOT / "smolagents/my_ui.py").read_text(encoding="utf-8").splitlines()

m = {}
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        for k in range(i2 - i1):
            m[i1 + k + 1] = j1 + k + 1
    else:
        # delete / replace / insert：旧行落在新块起点（没有就落在插入后的下一行）
        tgt = j1 + 1 if j1 < len(B) else len(B)
        for k in range(max(i2 - i1, 0)):
            m[i1 + k + 1] = tgt

# 兜底：任何没被覆盖的行号 = 上一行 + 1
for n in range(1, len(A) + 1):
    if n not in m:
        m[n] = min(m.get(n - 1, 1) + 1, len(B))

json.dump({str(k): v for k, v in sorted(m.items())}, open("/tmp/v17_map16.json", "w"))
moved = sum(1 for k, v in m.items() if v != k)
print("v1.6 %d 行 -> v1.7 %d 行；映射 %d 条，其中行号发生移动 %d 条" % (len(A), len(B), len(m), moved))
print("样例:", [(k, m[k]) for k in (1, 30, 63, 132, 368, 519, 900, 1007, 1183, 1205)])
