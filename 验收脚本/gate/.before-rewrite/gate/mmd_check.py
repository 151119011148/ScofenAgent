#!/usr/bin/env python3
"""把 README 里每个 ```mermaid 块真渲染一遍，验证语法。
用法：python3 /tmp/mmd_check.py <markdown>
判据：headless Chrome + /tmp/mermaid.min.js。每张图应产出一个 <svg>；
      mermaid 遇到语法错误会在对应位置画一个带「Syntax error in text」的 error 图。
"""
import pathlib
import re
import subprocess
import sys

MD = pathlib.Path(sys.argv[1])
MM = re.findall(r"```mermaid\n(.*?)```", MD.read_text(encoding="utf-8"), re.S)
if not MM:
    print("没有找到 mermaid 代码块")
    sys.exit(0)

parts = ['<!doctype html><meta charset="utf-8"><body>',
         '<script src="/tmp/mermaid.min.js"></script>',
         '<script>mermaid.initialize({startOnLoad:false, securityLevel:"loose"});</script>']
for i, b in enumerate(MM):
    parts.append('<div class="d%d">%s</div>' % (i, b))
parts.append('<script>mermaid.run({querySelector: ".mermaid, [class^=d]"}).catch(e=>{'
             'document.body.setAttribute("data-runerr", String(e).slice(0,200));});</script>')
parts.append('</body>')
pathlib.Path("/tmp/mmd_page.html").write_text("\n".join(parts), encoding="utf-8")

r = subprocess.run(
    ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
     "--headless=new", "--disable-gpu", "--no-sandbox",
     "--user-data-dir=/tmp/mmd-chrome-profile", "--virtual-time-budget=25000",
     "--dump-dom", "file:///tmp/mmd_page.html"],
    capture_output=True, text=True, timeout=300)
dom = r.stdout
svg = dom.count("<svg")
err = dom.lower().count("syntax error") + dom.lower().count("error rendering")
runerr = re.search(r'data-runerr="([^"]*)"', dom)
which = re.findall(r'class="d(\d+)"[^>]*aria-id', dom)
print("块数 %d / 产出 svg %d / 语法错误 %d%s" % (
    len(MM), svg, err, (" / run 异常: " + runerr.group(1)) if runerr else ""))
if svg < len(MM) or err:
    bad = []
    for i in range(len(MM)):
        seg = re.search(r'class="d%d"[^>]*>(.{0,400}?)</div>' % i, dom, re.S)
        if seg and ("Syntax error" in seg.group(1) or "error" in seg.group(1).lower()[:120]):
            bad.append(i + 1)
    print("可疑的图号：", bad or "(逐个看 aria-* 计数)")
    sys.exit(1)
print("全部通过")
