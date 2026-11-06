#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README 现状段的 my_ui.py 锚点：v1.7 那一版 → v1.8 那一版（1,758 行）。

逐行替换，行号必须先对上；每条替换断言"在该行里出现且只出现 1 次"。
6.3.2~6.3.9 各节保留它那一版的行号，本脚本一行都不碰（除 6.3.1 的 :944）。
用法：python3 v18_readme_anchors.py [--write]
"""
import io
import shutil
import sys

DOC = "/Users/gaoying/Desktop/study/ai学习/README.md"
BAK = "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.8/run/v18_README.before-anchors.md"

# (1 基行号, 旧串, 新串)
EDITS = [
    (63, "my_ui.py:1135", "my_ui.py:1670"),
    (63, "my_ui.py:382", "my_ui.py:482"),
    (63, "my_ui.py:546", "my_ui.py:670"),
    (77, "`smolagents/my_ui.py:1198-1201`", "`smolagents/my_ui.py:1751-1752`"),
    (652, "`my_ui.py:944`", "`my_ui.py:1382`"),
    (1390, "`smolagents/my_ui.py:691-746`", "`smolagents/my_ui.py:1085-1158`"),
    (1398, "`smolagents/my_ui.py:806-829`、`:831-958`", "`smolagents/my_ui.py:1218-1241`、`:1243-1396`"),
    (1399, "`smolagents/my_ui.py:50-55`", "`smolagents/my_ui.py:57-62`"),
    (1400, "`my_ui.py:961-986`", "`my_ui.py:1399-1424`"),
    (1401, "`my_ui.py:132-232`", "`my_ui.py:163-263`"),
    (1403, "`smolagents/my_ui.py:1052`、`:1067`", "`smolagents/my_ui.py:1493`、`:1508`"),
    (1404, "`smolagents/my_ui.py:1137`、`:1233`、`:1162`、`:1240`",
           "`smolagents/my_ui.py:1614`、`:1729`、`:1645`、`:1745`"),
    (1405, "`smolagents/my_ui.py:488-491`", "`smolagents/my_ui.py:569-572`"),
    (1406, "`my_ui.py:132-170`，回灌在 `:981-983`", "`my_ui.py:163-201`，回灌在 `:1419-1421`"),
    (1407, "`my_ui.py:69-84`", "`my_ui.py:100-115`"),
    (1409, "`my_ui.py:602-605`", "`my_ui.py:703-706`"),
    (1410, "`smolagents/my_ui.py:535-536`、`:845-846`、`:1130-1135`",
           "`smolagents/my_ui.py:616-617`、`:1267-1268`、`:1607-1612`"),
    (1411, "`smolagents/my_ui.py:1103-1104`", "`smolagents/my_ui.py:1578-1579`"),
    (1412, "`smolagents/my_ui.py:1007-1025` + `:1155-1156`",
           "`smolagents/my_ui.py:1445-1463` + `:1633-1634`"),
    (1412, "（`:1022-1024`）", "（`:1460-1462`）"),
    (1413, "`smolagents/my_ui.py:390`、`:609-611`、`:897-901`、`:40`",
           "`smolagents/my_ui.py:471`、`:710-712`、`:1324-1328`、`:43`"),
    (1413, "MEM_FIELDS`（`:69-84`）", "MEM_FIELDS`（`:100-115`）"),
    (1414, "`smolagents/my_ui.py:63` + `:68` + `:162-168` + `:225-229`",
           "`smolagents/my_ui.py:94` + `:99` + `:193-199` + `:256-260`"),
    (1415, "`smolagents/my_ui.py:988-1004` → `:1160` / `:1178-1180`",
           "`smolagents/my_ui.py:1426-1442` → `:1643` / `:1661-1667`"),
]

lines = io.open(DOC, encoding="utf-8").read().split("\n")
bad = []
for ln, old, new in EDITS:
    text = lines[ln - 1]
    n = text.count(old)
    if n != 1:
        bad.append((ln, n, old))
        continue
    lines[ln - 1] = text.replace(old, new, 1)

print(f"替换 {len(EDITS)} 条 · 不匹配 {len(bad)} 条")
for ln, n, old in bad:
    print(f"  L{ln} 命中 {n} 次：{old[:60]}")
if not bad and "--write" in sys.argv:
    shutil.copy2(DOC, BAK)
    io.open(DOC, "w", encoding="utf-8").write("\n".join(lines))
    print(f"已落盘，改前副本 {BAK}")
