# -*- coding: utf-8 -*-
"""把第三道扫（终点扫）抓到的 7 处「区间起点是 def、终点却越过函数末尾」改成单函数跨度。

这一类是记录里那条老坑的复现：**本轮在两个函数之间插了新东西，前面的区间没跟着截短**，
而行号对齐器只搬单点号，一条都不会报。实测边界（尺子 `.rollback/v1.8/my_ui.py`，逐行量缩进）：

    encode_memory 163-201 ／ decode_memory 204-263
    Approval.decide 468-472 ／ Approval.wait 474-479
    _install_plan_gate 830-857 ／ _plan_gate 859-883

文档里原先写的 `:163-263`／`:468-479`／`:830-883` 都是**两个函数并成一个区间**——
`:830-883` 尤其实在：v1.8 之前 `_install_plan_gate` 这一片整块就是计划闸，写成一条看不出结构，
现在 `_plan_gate` 是独立方法（859 行），分开写才知道批准逻辑挂在哪。

一次性：逐条断言唯一命中，替换前整份备份进 `run/`。带 `--write` 才落盘。
"""
import io
import os
import shutil
import sys

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
RUN = os.path.join(ROOT, u"验收脚本", "v1.8", "run")

EDITS = [
    # (文档, 旧串, 新串)
    (u"README.md",
     u"闸这边 `_install_plan_gate`（`:830-883`）包的是",
     u"闸这边 `_install_plan_gate`（`:830-857`，它下面挂的 `_plan_gate` 是 `:859-883`）包的是"),
    (u"README.md",
     u"| 52 | `smolagents/my_ui.py:830-883` ＋ `:1696` |",
     u"| 52 | `smolagents/my_ui.py:830-857`（`_install_plan_gate`）／`:859-883`（`_plan_gate`）＋ `:1696` |"),
    (u"README.md",
     u"所以 v1.5 的 V6 是自己写字段（`my_ui.py:163-263`）",
     u"所以 v1.5 的 V6 是自己写字段（`my_ui.py:163-201` 编、`:204-263` 解）"),
    (u"agent功能手册.html",
     u"<b>计划闸 :830-883</b>",
     u"<b>计划闸 :830-857 ＋ _plan_gate :859-883</b>"),
    (u"agent功能手册.html",
     u"<code>Event</code> 解开才决定跑不跑（<code>:468-479</code>）",
     u"<code>Event</code> 解开才决定跑不跑（<code>decide :468-472</code>／<code>wait :474-479</code>）"),
    (u"agent功能手册.html",
     u"<code>_install_plan_gate()</code>（<code>my_ui.py:830-883</code>）",
     u"<code>_install_plan_gate()</code>（<code>my_ui.py:830-857</code>，它挂上的 <code>_plan_gate</code> 在 <code>:859-883</code>）"),
    (u"agent功能手册.html",
     u"编解码 <code>:163-263</code>",
     u"编解码 <code>:163-201</code>／<code>:204-263</code>"),
    (u"agent功能手册.html",
     u'<tr><td><code>my_ui.py:830-883</code></td>',
     u'<tr><td><code>my_ui.py:830-857</code>（<code>_install_plan_gate</code>）／<code>:859-883</code>（<code>_plan_gate</code>）</td>'),
]

write = u"--write" in sys.argv
texts = {}
for doc, old, new in EDITS:
    if doc not in texts:
        texts[doc] = io.open(os.path.join(ROOT, doc), encoding=u"utf-8").read()
    n = texts[doc].count(old)
    if n != 1:
        print(u"!! %s 命中 %d 次，不是唯一命中，整批不落盘：%s" % (doc, n, old[:60]))
        raise SystemExit(1)
    texts[doc] = texts[doc].replace(old, new)
    print(u"ok %s  唯一命中 → %s" % (doc, new[:66]))

if not write:
    print(u"试运行：一个字都没写（加 --write 落盘）")
    raise SystemExit(0)

for doc in texts:
    shutil.copyfile(os.path.join(ROOT, doc),
                    os.path.join(RUN, u"v18_" + os.path.splitext(os.path.basename(doc))[0] + u".before-spanfix"
                                 + (u".md" if doc.endswith(u".md") else u".html")))
    io.open(os.path.join(ROOT, doc), u"w", encoding=u"utf-8").write(texts[doc])
    print(u"写入 %s（改前原文在 run/v18_*.before-spanfix）" % doc)

for doc in texts:
    lines = texts[doc].split(u"\n")
    print(u"%s 行数=%d 字节=%d" % (doc, len(lines), len(texts[doc].encode(u"utf-8"))))
