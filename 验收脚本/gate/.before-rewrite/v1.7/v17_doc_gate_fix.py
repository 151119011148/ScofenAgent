# -*- coding: utf-8 -*-
import io, sys

WRITE = "--write" in sys.argv

def sub(t, old, new, name):
    n = t.count(old)
    assert n == 1, u"%s matched %d times" % (name, n)
    return t.replace(old, new)

HTML_ADD = (u'<br/><b>§7 那句「V9 的边界」改写成已上线之后，四个闸全部复跑一遍</b>：'
            u'静态闸（看板 <b>37</b> 行、两分布、未闭合/配对/外部/死锚四项全 0）· '
            u'浏览器闸 <b>1,440</b> 与 <b>1,180</b> 两档（<code>title</code> v1.7、<code>rows 37</code>、'
            u'<code>tables 32</code>、十个筛选器 <code>#cnt</code> 与可见行逐条相符、'
            u'<code>overflowX=false</code>；截图 <b>229,146 B</b> 与 <b>218,828 B</b>）· '
            u'事后两道扫（README <b>368 / 0 / 1</b>、手册 <b>258 / 0 / 8</b>）· '
            u'Mermaid <b>25 / 25 / 0</b> 且 <code>exit=0</code>，负控 <b>2 / 2 / 1</b> 且 <code>exit=1</code>'
            u'（<code>/tmp/v17_mmd_rerun.out</code>、<code>/tmp/v17_mmd_neg.out</code>）。'
            u'<b>行号数从 260 变 258</b>：那一句改写完<b>不再引用任何行号</b>，'
            u'少掉的 2 个正是原句里的 <code>:69-88</code>（一个范围两个号）；越界与空行的判定没变')

MD_ADD = (u'；<b>§7 那句「V9 的边界」改写成已上线之后，四个闸全部复跑</b>'
          u'（静态 37 行/两分布/四项全 0 · 浏览器 1,440 与 1,180 两档 `title` v1.7、`rows 37`、`tables 32`、'
          u'十个筛选器逐条相符、`overflowX=false`、截图 229,146 B 与 218,828 B · '
          u'事后两道扫 README **368/0/1**、手册 **258/0/8** · '
          u'Mermaid **25/25/0 exit=0** ＋ 负控 **2/2/1 exit=1**，'
          u'`/tmp/v17_mmd_rerun.out`、`/tmp/v17_mmd_neg.out`）。'
          u'行号数从 260 变 258 是因为那一句改写完不再引用任何行号，少掉的 2 个正是原句里的 `:69-88`，越界与空行的判定没变')

def patch(path, pairs):
    t = io.open(path, encoding="utf-8").read()
    before = t
    for old, new, name in pairs:
        t = sub(t, old, new, name)
    print(u"%s: %d -> %d chars" % (path, len(before), len(t)))
    if WRITE:
        io.open(path, "w", encoding="utf-8").write(t)

pairs_html = [
    (u'、§7）<b>260</b> 个行号，越界 <b>0</b> 条，指向空行 <b>8</b> 条',
     u'、§7）<b>258</b> 个行号，越界 <b>0</b> 条，指向空行 <b>8</b> 条',
     u"html-260"),
    (u'（写出来是为了记下它错在哪，不是引用错了位置）</td></tr>',
     u'（写出来是为了记下它错在哪，不是引用错了位置）' + HTML_ADD + u'</td></tr>',
     u"html-tail"),
]
pairs_md = [
    (u'、§7）**260** 个行号，越界 **0** 条，指向空行 **8** 条',
     u'、§7）**258** 个行号，越界 **0** 条，指向空行 **8** 条',
     u"md-260"),
    (u'（写出来是为了记下它错在哪，不是引用错了位置） |',
     u'（写出来是为了记下它错在哪，不是引用错了位置）' + MD_ADD + u' |',
     u"md-tail"),
]
patch(u"agent功能手册.html", pairs_html)
patch(u"迭代记录.md", pairs_md)
