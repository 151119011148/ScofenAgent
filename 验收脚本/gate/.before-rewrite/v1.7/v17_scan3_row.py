# -*- coding: utf-8 -*-
import io, sys
W = u"--write" in sys.argv

CELL1 = u"文档闸·第三道扫：区间引用的<b>终点</b>（前两道扫看不见这一类错）<br/>" \
        u"<code>/tmp/v17_scan3.py</code> 定位 · <code>/tmp/v17_scan3_fix.py</code> 落盘 · <code>/tmp/v17_README.before-scan3.md</code> 备份"

CELL2 = (u"前两道扫查的是单点（越界、指向空行），<b>写成 <code>:X-Y</code> 的区间引用，尾部吃进下一节它们查不出来</b>。"
         u"这一道只问一件事：终点那一行是什么——<b>空行</b> / <b>下一个 def 或 class</b> / <b><code># ----</code> 分隔</b> / <b>顶格 <code># </code> 开场注释</b>；"
         u"起点不查（起点是 def 或注释都正常）。<b>真实跨度从源码量</b>：def 行按缩进往下走到同级 <code>def</code>/<code>class</code>/<code># ----</code> 为止、修剪空行。"
         u"<b>覆盖 268 个区间</b>（README 133 ＋ 手册 114 ＋ <code>迭代记录.md</code> 21）。"
         u"<b>改掉 14 处</b>。手册 12：<code>:782-805</code>→<code>:782-803</code>（<code>_status_html</code>，3 处）、"
         u"<code>:961-1006</code>→<code>:961-986</code>（<code>_bind_memory</code>，3 处——v1.6 之前它确实到 1,006，是本轮新加的 <code>_session_steps</code> 把它截短的，"
         u"<span class=\"r\">对齐器只搬单点号，所以这种「区间被后面的插入截短」它一条也没报</span>）、"
         u"<code>:691-748</code>→<code>:691-746</code>、<code>:806-960</code>→<code>:806-958</code>、<code>:831-960</code>→<code>:831-958</code>、"
         u"<code>:63-234</code>→<code>:63-232</code>、<code>:132-230</code>→<code>:132-232</code>；"
         u"<code>:640-689</code> 数字不动、把标签补全成「<code>_approval_card</code> ＋它的两个渲染小工具 <code>_fence</code> <code>_args_text</code>」"
         u"（卡本身是 640-667，669 起是那两个小工具）。README 2：<code>:1162-1179</code>→<code>:1162-1180</code>（<code>_on_load</code> 的 <code>return</code> 在 1,180，原来少一行）。"
         u"<b>这道扫自己的漏检也是它自己暴露的</b>：第一版正则 <code>(?&lt;![\\w.]):X-Y</code> 里那个负向断言把 <code>my_ui.py:782-805</code> 这种"
         u"<b>带文件名的写法整条跳过</b>（<code>py</code> 后面那个点撞了断言）；放开 <code>(?:my_ui\\.py)?</code> 前缀之后覆盖面从 110 / 80 / 9 涨到 133 / 114 / 21，"
         u"多出来的那一类里就有 179 行索引的第一号引用。"
         u"<b>改完复扫剩 13 条，逐条定性，没有一条是真错</b>：6 条是 <code>:69-88</code> 与 <code>:85-88</code>——"
         u"终点 88 正好是 <code>MEM_FIELDS</code> 那段注释的最后一行，区间本来就该写到那儿（<b>本道的假阳性，规则里写明</b>）；"
         u"7 条是历史与被纠正号的引用（<code>:53-172</code> 3 处都带「v1.2 时是」，<code>:988-1005</code> <code>:988-1006</code> 4 处就是本表第三行写下来纠错的那两个号）。"
         u"<b>复跑</b>：README <b>1,445 行 / 144,128 B 一字未涨</b>（改的都是数字）；手册行数因本行 +1，见 §6.1 体量那行。"
         u"四道闸全绿——静态（37 行、<code>data-st {16,0,18,3}</code>、<code>data-p {D8,P0 5,P1 8,P2 7,V 9}</code>、未闭合/配对/外部/死锚四项全 0）· "
         u"浏览器两档（1,440 与 1,180 视口 <code>overflowX=false</code>，<code>rows 37</code>、<code>tables 32</code>，截图 229,146 B 与 218,828 B）· "
         u"第一道扫（README 368 / 0 / 1、手册 258 / 0 / 8）· Mermaid（25 / 25 / 0 且 <code>exit=0</code>，负控 2 / 2 / 1 且 <code>exit=1</code>）")

MD2 = CELL2.replace(u"<code>", u"`").replace(u"</code>", u"`") \
           .replace(u'<span class="r">', u"「").replace(u'</span>', u"」") \
           .replace(u"<b>", u"**").replace(u"</b>", u"**").replace(u"<br/>", u" ").replace(u"&lt;", u"<")

def patch_html(t):
    lines = t.split(u"\n")
    assert lines[646].rstrip().endswith(u"不是回写时才错的</td></tr>"), lines[646][-80:]
    assert lines[647] == u"</table>", repr(lines[647])
    row = u"  <tr><td>" + CELL1 + u"</td><td>" + CELL2 + u"</td></tr>"
    lines.insert(647, row)
    return u"\n".join(lines)

def patch_md(t):
    lines = t.split(u"\n")
    assert lines[85].startswith(u"| **文档闸自己被抓到并当场修掉的三处**"), lines[85][:60]
    row = u"| **文档闸·第三道扫：区间引用的**终点**（前两道扫看不见这一类错）** | " + MD2 + u" |"
    row = row.replace(u"：区间引用的**终点**（", u"：区间引用的「终点」（", 1)
    lines.insert(86, row)
    return u"\n".join(lines)

for path, fn in [(u"agent功能手册.html", patch_html), (u"迭代记录.md", patch_md)]:
    t = io.open(path, encoding="utf-8").read()
    nt = fn(t)
    print(u"%s: %d 行 -> %d 行" % (path, len(t.split(u"\n")), len(nt.split(u"\n"))))
    if W:
        io.open(path, "w", encoding="utf-8").write(nt)
