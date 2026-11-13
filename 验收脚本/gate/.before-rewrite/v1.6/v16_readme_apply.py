# -*- coding: utf-8 -*-
"""把 /tmp/v16_readme_align.py 的提案落到 README.md（按行内位置替换，不按字符串）。

为什么不按字符串：`:30`、`:502` 这种串在文中到处都有，replace(old,new) 会改错行。
这里每条都带着 (行号, 列号)，从行尾往行首改，改完把整行新旧打出来人工过一遍。

只改 status=HIT / TIE 且落在我核对过的那几条上的；ZERO / NO-MAP / 历史引用（v1.1 前
在 `:70-72`）/ 别的文件（agents.py、关闭Agent.command、dify…）一概不动。
"""
import json
import pathlib
import re
import sys

MD = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/README.md")
V16 = (pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents/my_ui.py")
       .read_text(encoding="utf-8").splitlines())

# 逐行核对后的例外：机器在两个时代之间打平时，按人话定的那一条
OVERRIDE = {
    ":874": (1186, 1186),        # v1.4 create_app 里的 stop_btn.click，不是 v1.5 那行注释
    ":694": (730, 730),          # v1.5 的 _stats（和 :502 那条指的是同一个函数）
    ":820": (1132, 1132),        # _on_load 的 return，v1.6 被 V7 的注释往下推了
    ":1025-1035": (1118, 1132),  # _on_load 整块，收尾在 :1132
    ":401": (410, 410),          # memory 表 DDL
    "my_ui.py:584": (608, 608),      # _decide 里「一次只结算最早那张」
    "my_ui.py:564-567": (583, 586),  # _gated_call 的入队+判停临界区
}
# 这些行上的 :NNN 不是 my_ui.py 的（脚本文件名判定被中文带偏了），整行跳过
SKIP_LINES = {629, 903, 1162, 1164, 1167, 1177}


def candidates():
    sys.path.insert(0, "/tmp")
    src = pathlib.Path("/tmp/v16_readme_align.py").read_text(encoding="utf-8")
    src = src.replace("\nmain()\n", "\n")
    ns = {"__name__": "align"}
    exec(compile(src, "v16_readme_align.py", "exec"), ns)
    return ns


def main():
    ns = candidates()
    txt = MD.read_text(encoding="utf-8")
    lines = txt.splitlines(keepends=False)
    edits = {}   # ln -> [(col, end, new)]
    log = []
    for ln, col, raw, a, b, kind in ns["ref_sites"](txt):
        if not any(x <= ln <= y for x, y in ns["SECTIONS"]) or ln in SKIP_LINES:
            continue
        if kind == "HIST":
            log.append((ln, raw, "-", "历史引用，不动"))
            continue
        rl = lines[ln - 1]
        cands = sorted([c for c in ((era, ns["score"](rl, a, b, era))
                                   for era in (14, 15)) if c[1]],
                       key=ns["key"], reverse=True)
        if not cands:
            log.append((ln, raw, "-", "NO-MAP（旧号超出那一版文件）"))
            continue
        era, (na, nb, (sh, th), _) = cands[0]
        alt = ns["key"](cands[1]) if len(cands) > 1 else (-1, -1)
        status = "TIE" if ((sh, th) == alt and (sh, th) != (0, 0)) else (
            "HIT" if (sh, th) != (0, 0) else "ZERO")
        if raw in OVERRIDE:
            na, nb = OVERRIDE[raw]
            status = "OVERRIDE"
        elif status == "ZERO":
            log.append((ln, raw, "-", "ZERO：撞不上实体，多半不是 my_ui 的行号"))
            continue
        elif status == "TIE":
            log.append((ln, raw, ":%d-%d" % (na, nb), "TIE 人工核过"))
        new = ("%s:%d-%d" % (raw.split(":")[0], na, nb)) if nb > na else ("%s:%d" % (raw.split(":")[0], na))
        if new == raw:
            log.append((ln, raw, new, "行号未变"))
            continue
        edits.setdefault(ln, []).append((col, col + len(raw), new))
    for ln, items in edits.items():
        old_line = lines[ln - 1]
        new_line = old_line
        for col, end, new in sorted(items, reverse=True):
            new_line = new_line[:col] + new + new_line[end:]
        lines[ln - 1] = new_line
        for col, end, new in sorted(items):
            print("L%-5d %-16s -> %s" % (ln, old_line[col:end], new))
        print("      旧 ‖%s" % old_line.strip()[:150])
        print("      新 ‖%s" % new_line.strip()[:150])
    print("\n改动行数 %d / 改的引用 %d 条" % (len(edits), sum(len(v) for v in edits.values())))
    for ln, raw, new, why in log:
        print("  keep %4d %-16s %-12s %s" % (ln + 1, raw, new, why))
    if "--write" in sys.argv:
        MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("已写回 README.md（%d 行）" % len(lines))


main()
