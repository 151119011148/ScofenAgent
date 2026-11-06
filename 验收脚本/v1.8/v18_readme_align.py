#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README 全文里的 my_ui.py 行号锚点从 v1.7 那一版映射到 v1.8 那一版（只读报告）。

映射用整行 difflib 对齐：未改动的行给精确号；落在改动区间的行标 ?CHG 交人判。
锚点只认两种写法：反引号包起来的 `:NNN` / `:NNN-NNN`，和 my_ui.py:NNN。
"""
import difflib
import io
import re

ROOT = "/Users/gaoying/Desktop/study/ai学习"
OLD = f"{ROOT}/.rollback/v1.7/my_ui.py"
NEW = f"{ROOT}/.rollback/v1.8/my_ui.py"
DOC = f"{ROOT}/README.md"

old_lines = io.open(OLD, encoding="utf-8").read().split("\n")
new_lines = io.open(NEW, encoding="utf-8").read().split("\n")

mapping = {}
sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        for k in range(i2 - i1):
            mapping[i1 + k + 1] = j1 + k + 1

PAT = re.compile(r"`:(\d+)(?:-(\d+))?`|my_ui\.py:(\d+)(?:-(\d+))?")
ROW = re.compile(r"^\| (\d+) \|")


def map_one(n):
    if n > len(old_lines):
        return f"{n}>OUT"
    if n in mapping:
        return f"{n}->{mapping[n]}" if mapping[n] != n else f"{n}=ok"
    return f"{n}?CHG"


doc = io.open(DOC, encoding="utf-8").read().split("\n")
rows = []
for idx, line in enumerate(doc, 1):
    if "my_ui.py" not in line:
        continue
    moves = []
    for g in PAT.findall(line):
        for chunk in g:
            if chunk:
                mv = map_one(int(chunk))
                if "->" in mv or "?CHG" in mv or ">OUT" in mv:
                    moves.append(mv)
    if moves:
        r = ROW.match(line)
        rows.append((idx, r.group(1) if r else "-", moves, line[:60]))

print(f"old {len(old_lines)} 行 / new {len(new_lines)} 行 · equal 映射 {len(mapping)} 条")
print(f"待对齐行数 {len(rows)}\n")
for idx, rowno, moves, preview in rows:
    print(f"L{idx} [行号 {rowno}] {' '.join(moves)}  | {preview}")
