# -*- coding: utf-8 -*-
import json, re, sys
src = sys.argv[1]
txt = open(src, encoding="utf-8").read()
blocks = re.findall(r"```mermaid\n(.*?)```", txt, re.S)
names = ["flowchart", "sequenceDiagram", "classDiagram", "stateDiagram", "journey", "gantt", "erDiagram", "pie", "C4Context", "requirementDiagram", "gitGraph", "mindmap", "timeline", "quadrantChart"]
out = []
for i, b in enumerate(blocks, 1):
    first = ""
    for ln in b.splitlines():
        s = ln.strip()
        if s and not s.startswith("%%"):
            first = s
            break
    kind = next((n for n in names if first.startswith(n)), "?")
    out.append({"i": i, "kind": kind, "text": b})
json.dump(out, open("/Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/mmd_blocks.json", "w", encoding="utf-8"), ensure_ascii=False)
print("blocks:", len(out))
for d in out:
    print("%3d  %-16s %s" % (d["i"], d["kind"], d["text"].splitlines()[0][:60] if d["text"] else ""))
