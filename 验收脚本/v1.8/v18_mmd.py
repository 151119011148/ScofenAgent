# -*- coding: utf-8 -*-
"""文档闸·Mermaid 闸（v1.8）：把 README 里每个 ```mermaid 块真渲染一遍，再加**负控**。

沿用 `验收脚本/gate/` 那套判据（headless Chrome ＋ 离线 mermaid.min.js ＋ `--dump-dom`），
但产物全落在本轮自己的目录里（`v1.8/run/mmd18_*`、profile `v1.8/run/chrome-mmd18`），
不去覆盖 `gate/run/mmd_page.html`——那是跨轮共用的文件名，别的会话也在写。

判据（正例）：块数 N ＝ 产出 `<svg>` 数 N ＋ 语法错误 0 ＋ 没有 run 异常，否则 exit=1。
判据（负控 `--neg`）：造一份「两块，其中一块语法坏」的文档，闸门必须**看得见那块坏**
                      （块数 2、语法错误 ≥1，且好的那一块照样 svg 出得来）。
                      注意这一份脚本的退出码方向：`--neg` 跑到 exit=0 ＝「负例被抓到了，闸门是活的」；
                      exit=1 ＝「坏块没报错」，也就是假通过。v1.7 那轮要求过，本轮继续。

跑法（cwd=ai学习）：
    python3 验收脚本/v1.8/v18_mmd.py                 # 正例：README
    python3 验收脚本/v1.8/v18_mmd.py --neg           # 负控
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
RUN = os.path.join(ROOT, u"验收脚本", "v1.8", "run")
MMJS = os.path.join(ROOT, u"验收脚本", "gate", "run", "mermaid.min.js")
CHROME = u"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = os.path.join(RUN, "chrome-mmd18")
NAMES = ["flowchart", "sequenceDiagram", "classDiagram", "stateDiagram", "journey", "gantt",
         "erDiagram", "pie", "C4Context", "requirementDiagram", "gitGraph", "mindmap",
         "timeline", "quadrantChart"]


def blocks_of(md_path):
    txt = open(md_path, encoding="utf-8").read()
    raw = re.findall(r"```mermaid\n(.*?)```", txt, re.S)
    out = []
    for i, b in enumerate(raw, 1):
        first = u""
        for ln in b.splitlines():
            s = ln.strip()
            if s and not s.startswith(u"%%"):
                first = s
                break
        out.append({"i": i, "kind": next((n for n in NAMES if first.startswith(n)), u"?"),
                    "head": first[:60], "text": b})
    return out


def render(blocks, tag):
    """写外壳页 → Chrome 渲染 → 数 svg / 语法错误。"""
    page = os.path.join(RUN, u"mmd18_page_%s.html" % tag)
    parts = [u'<!doctype html><meta charset="utf-8"><body>',
             u'<script src="%s"></script>' % MMJS,
             u'<script>mermaid.initialize({startOnLoad:false, securityLevel:"loose", logLevel:5});</script>']
    for i, d in enumerate(blocks):
        parts.append(u'<div class="d%d">%s</div>' % (i, d["text"]))
    parts.append(u'<script>mermaid.run({querySelector: "[class^=d]"}).catch(e=>{'
                 u'document.body.setAttribute("data-runerr", String(e).slice(0,200));});</script></body>')
    open(page, "w", encoding="utf-8").write(u"\n".join(parts))
    r = subprocess.run([CHROME, u"--headless=new", u"--disable-gpu", u"--no-sandbox",
                        u"--user-data-dir=%s" % PROFILE, u"--virtual-time-budget=40000",
                        u"--dump-dom", u"file://" + page],
                       capture_output=True, text=True, timeout=420)
    dom = r.stdout
    svg = dom.count(u"<svg")
    err = dom.lower().count(u"syntax error") + dom.lower().count(u"error rendering")
    runerr = re.search(r'data-runerr="([^"]*)"', dom)
    return {"page": page, "svg": svg, "err": err, "blocks": len(blocks),
            "error_svgs": dom.count(u"error-icon") + dom.count(u"error-text"),
            "runerr": runerr.group(1) if runerr else None,
            "chrome_exit": r.returncode, "stderr": r.stderr[:200]}


def main():
    neg = u"--neg" in sys.argv
    if neg:
        md = os.path.join(RUN, u"mmd18_neg.md")
        open(md, "w", encoding="utf-8").write(u"\n".join([
            u"# Mermaid 闸的负控文档（合成，不是语料）",
            u"",
            u"```mermaid",
            u"flowchart LR",
            u"  A[好的块] --> B[也应该画出来]",
            u"```",
            u"",
            u"```mermaid",
            u"flowchart LR",
            u"  A[开工] --> (这一行故意缺右括号且节点写法非法",
            u"```",
            u"",
        ]) + u"\n")
        blocks, tag = blocks_of(md), u"neg"
        exp_blocks, want_err = 2, True
    else:
        md = os.path.join(ROOT, "README.md")
        blocks, tag = blocks_of(md), u"readme"
        exp_blocks, want_err = len(blocks), False

    js = json.dumps([{k: d[k] for k in ("i", "kind", "head")} for d in blocks], ensure_ascii=False)
    open(os.path.join(RUN, u"mmd18_blocks_%s.json" % tag), "w", encoding=u"utf-8").write(js)
    res = render(blocks, tag)
    print(u"%s：%s → 块数 %d ／ 产出 svg %d ／ 语法错误 %d ／ 带错误标记的 svg %d ／ Chrome exit %d"
          % (u"负控" if neg else u"正例", md, res["blocks"], res["svg"], res["err"],
             res["error_svgs"], res["chrome_exit"]))
    if res["runerr"]:
        print(u"  run 异常：%s" % res["runerr"])
    for d in blocks:
        print(u"  %3d %-16s %s" % (d["i"], d["kind"], d["head"]))

    bad = []
    if res["blocks"] != exp_blocks:
        bad.append(u"块数 %d，期望 %d" % (res["blocks"], exp_blocks))
    if want_err:
        # 负控：坏的那一块必须被数出来，而且整体判红
        if res["err"] < 1:
            bad.append(u"负控没报错（语法错误 %d 条）——这台校验器是死的" % res["err"])
        if res["svg"] < 1:
            bad.append(u"负控里连好的那块都没画出来（svg %d）" % res["svg"])
    else:
        if res["svg"] < res["blocks"]:
            bad.append(u"svg %d < 块数 %d" % (res["svg"], res["blocks"]))
        if res["err"]:
            bad.append(u"语法错误 %d 条" % res["err"])
        if res["runerr"]:
            bad.append(u"run 异常")
    print(u"---- Mermaid 闸结论：%s ----" % (u"；".join(bad) if bad else
          (u"负控按预期判红" if neg else u"全部通过")))
    raise SystemExit(0 if not bad else 1)


main()
