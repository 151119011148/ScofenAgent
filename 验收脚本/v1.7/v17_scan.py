# -*- coding: utf-8 -*-
"""文档闸事后两道扫：越界（行号 > 1,253）与指向空行。README 与手册各扫一遍。

只扫"讲现状"的范围；§6.x 那些记录节讲的是当时那一版的位置，不参与对齐、也不该按越界判红。
"""
import pathlib
import re

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
UI = (ROOT / "smolagents/my_ui.py").read_text(encoding="utf-8").splitlines()
N = len(UI)

TARGETS = {
    "README": (ROOT / "README.md", [(633, 1036), (1074, 1446)]),
    "手册": (ROOT / "agent功能手册.html", [(95, 583), (586, 645), (650, 681), (1227, 1287)]),  # 646-649＝四行文档闸自己，不参与
    "迭代记录": (ROOT / "迭代记录.md", [(13, 83), (88, 139)]),  # 139＝§8 第 8 步那一节收口
}

for name, (path, ranges) in TARGETS.items():
    lines = path.read_text(encoding="utf-8").splitlines()
    oob, blank, total = [], [], 0
    for ln, line in enumerate(lines, 1):
        if not any(a <= ln <= b for a, b in ranges):
            continue
        window_used = []
        for m in re.finditer(r"(?<![\w.])(my_ui\.py)?:\d+(?:-\d+)?", line):
            raw = m.group(0)
            col = m.start()
            # 前面 160 字符里点过别的文件名就跳过（和提议器同一口径）
            win = line[max(0, col - 160):col]
            others = ["agents.py", "gradio_ui.py", "utils.py", "local_python_executor.py",
                      "my_coding_agent.py", "my_agent.py", "memory.py", "tools.py",
                      "model.py", "types.py", "python_interpreter.py", "chat_interface.py",
                      "docker-compose.yaml", "workflow_entry.py", "node_factory.py",
                      "app_dsl_service.py", "local_py_scripts.py"]
            last, lasti = None, -1
            for o in others:
                p = win.rfind(o)
                if p > lasti:
                    last, lasti = o, p
            if raw.startswith("my_ui.py"):
                last = None
            if last:
                continue
            nums = [int(x) for x in re.findall(r"\d+", raw)]
            for k in nums:
                total += 1
                if k > N:
                    oob.append((ln, raw))
                elif not UI[k - 1].strip():
                    blank.append((ln, raw, UI[k - 1]))
    print("=== %s（讲现状的范围 %s，my_ui.py 现行 %d 行）===" % (name, ranges, N))
    print("检查过的行号 %d 个；越界 %d 条；指向空行 %d 条" % (total, len(oob), len(blank)))
    for x in oob[:10]:
        print("  越界 %5d %s" % x)
    for x in blank[:10]:
        line_of = lambda L: lines[L-1].strip()[:150]
        print("  空行 %5d %s | 句子: %s" % (x[0], x[1], line_of(x[0])))
