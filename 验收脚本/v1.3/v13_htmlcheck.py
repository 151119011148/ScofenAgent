# -*- coding: utf-8 -*-
"""手册 HTML 自检：标签配对 + 外部资源 + 看板行统计（不依赖浏览器的那部分）。"""
import re
import sys

path = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
src = open(path, encoding="utf-8").read()
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

# 先把 <pre><code> 里的示例标签摘掉，它们不是真结构
pre_only = re.sub(r"<pre>.*?</pre>", "", src, flags=re.S)
script_only = re.sub(r"<script>.*?</script>", "", pre_only, flags=re.S)

stack = []
errors = []
for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", script_only):
    closing, name, rest = m.group(1), m.group(2).lower(), m.group(3)
    if name in VOID or rest.rstrip().endswith("/"):
        continue
    if not closing:
        stack.append((name, m.start()))
    else:
        if not stack:
            errors.append(f"多余闭合 </{name}> @{m.start()}")
        elif stack[-1][0] != name:
            errors.append(f"错配：期望 </{stack[-1][0]}>（开于 @{stack[-1][1]}）实得 </{name}> @{m.start()}")
            stack.pop()
        else:
            stack.pop()
print("未闭合:", [(n, pos) for n, pos in stack])
print("配对错误:", len(errors))
for e in errors[:10]:
    print("  ", e)

ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', src)
print("外部资源:", len(ext), ext[:5])
print("看板行数:", len(re.findall(r"<tr data-st=", src)))
print("data-st 分布:", {k: len(re.findall(r'data-st="%s"' % k, src)) for k in ("todo", "doing", "done", "na")})
print("data-p 分布:", {k: len(re.findall(r'data-p="%s"' % k, src)) for k in ("D", "P0", "P1", "P2", "V")})
# 锚点自查：所有 href="#x" 的 x 都要有 id
ids = set(re.findall(r'id="([^"]+)"', src))
dead = [h for h in re.findall(r'href="#([^"]+)"', src) if h not in ids]
print("死锚点:", dead)
sys.exit(1 if (errors or stack or ext or dead) else 0)
