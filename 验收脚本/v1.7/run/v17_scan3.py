# -*- coding: utf-8 -*-
"""第三道扫：区间引用的**终点**越进到下一节。起点不查（起点是 def 或注释都正常）。"""
import io, re

UI = io.open(u"smolagents/my_ui.py", encoding="utf-8").read().split(u"\n")
N = 1253
SCOPES = [
    (u"README.md",         [(633, 1036), (1074, 1445)]),
    (u"agent功能手册.html", [(95, 582), (585, 644), (649, 680), (1226, 1286)]),
    (u"迭代记录.md",         [(13, 83), (88, 131)]),
]
RE = re.compile(r"(?<![\w.])(?:my_ui\.py)?:([\d]+)-([\d]+)")

def end_kind(ln):
    s = ln.strip()
    if not s:
        return u"空行"
    if re.match(u"(async )?def |^class ", s):
        return u"下一个 def/class"
    if u"----" in s and s.startswith(u"#"):
        return u"下一节的分隔注释"
    if s.startswith(u"# ") and ln.startswith(u"#"):
        return u"下一节的开场注释"
    return None

grand = 0
for path, ranges in SCOPES:
    lines = io.open(path, encoding="utf-8").read().split(u"\n")
    bad, n = [], 0
    for a, b in ranges:
        for i in range(a, min(b, len(lines)) + 1):
            for m in RE.finditer(lines[i-1]):
                x, y = int(m.group(1)), int(m.group(2))
                n += 1
                if y > N:
                    continue
                k = end_kind(UI[y-1])
                if k:
                    bad.append((i, u"%d-%d" % (x, y), k, UI[y-1][:46]))
    grand += len(bad)
    print(u"=== %s：区间 %d 个，终点越进下一节 %d 条" % (path, n, len(bad)))
    seen = set()
    for ln, r, k, txt in bad:
        key = (r, ln)
        if key in seen:
            continue
        seen.add(key)
        print(u"  文档行%-5d %-11s 终点%s 落在源码 %-4d：%s" % (ln, r, k, int(r.split("-")[1]), txt))
print(u"合计 %d 条" % grand)
