# -*- coding: utf-8 -*-
"""文档闸·静态闸（v2.0 版）：判据本体照抄 v1.8 那份，**只换期望值、只加断言**。

沿用不改的四条：`<pre>`/`<script>` 里的示例标签先摘掉再判闭合；void 标签与自闭合不算未闭合；
外部资源必须 0（这份手册要离线双击能开）；死锚点必须 0。

v2.0 新加的五条（都是这一轮真踩到或真需要的）：
  · **id 唯一**，且正则收紧成 `(?<![\\w-])id="…"`。v1.8 那份用 `id="([^"]+)"`，会把正文里
    `<code>gr.Markdown(elem_id="planpanel")</code>` 这种**示例代码**当成真 id，于是「重复 id」
    假报一条（本轮实测：`planpanel` 在 §4/§6 的 code 里出现 3 次，真 id 只有 1 个）。
    本轮又踩到同一类的第二脚：正文要讲「`id="s4"` 挂在 h2 上所以那条 CSS 是死的」，
    这句举例也被当成第二个真 id → **id／死锚点／外部资源三项都改在摘掉 `<code>` 的文本上判**。
  · **每行的可见 pill 必须与 `data-st` 相符**：改了状态属性却忘了改那颗胶囊，屏幕上就是
    「筛『已上线』筛不到它、但它看着像已上线」。这一格 v1.8 只在浏览器闸里间接覆盖。
  · **工单号唯一**：53 行就是 53 个号，重号会让「按编号点单」这件事失效。
  · **十个筛选器逐条对得上**：每个 `data-p`／`data-st` 取值都要有对应按钮，`id="cnt"` 必须在。
  · **期望值写死**：53 行 = todo 20 + doing 0 + done 31 + na 2；优先级 D 9 / P0 10 / P1 15 / P2 9 / V 10。

跑法（cwd=ai学习）：python3 验收脚本/v2.0/v20_gate_static.py
退出码 0＝全绿；1＝有红（红条逐条打印）。
第一个参数可指到别的 HTML——只给负控用（`v20_gate_neg.py` 拿故意改坏的副本验这闸会不会红）。
"""
import collections
import io
import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

# ---- v2.0 看板：53 行 = todo 20 + doing 0 + done 31 + na 2；优先级 D 9 / P0 10 / P1 15 / P2 9 / V 10
EXPECT_ROWS = 53
EXPECT_ST = {"todo": 20, "doing": 0, "done": 31, "na": 2}
EXPECT_P = {"D": 9, "P0": 10, "P1": 15, "P2": 9, "V": 10}
FILTERS = ["all", "bug", "p0", "p1", "p2", "v", "todo", "doing", "done", "na"]

src = io.open(PATH, encoding="utf-8").read()

# 示例代码不参与闭合判定：pre / script / style 三种都摘（style 里有 `>` 选择器）
stripped = re.sub(r"<pre>.*?</pre>", "", src, flags=re.S)
stripped = re.sub(r"<script>.*?</script>", "", stripped, flags=re.S)
stripped = re.sub(r"<style>.*?</style>", "", stripped, flags=re.S)
# `<code>` 里的示例属性同样不是真属性：本轮正文要讲「id="s4" 挂在 h2 上所以那条 CSS 是死的」，
# 不摘 code 就把这句举例当成第二个真 id，假报一条重复（与 v1.8 的 elem_id="planpanel" 同一类）。
# 真 id／真 href／真外部资源都在元素属性上，不会住在 code 里，所以摘掉只会去假阳性、不会漏真错。
no_code = re.sub(r"<code>.*?</code>", "", stripped, flags=re.S)

stack, errors = [], []
for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", stripped):
    closing, name, rest = m.group(1), m.group(2).lower(), m.group(3)
    if name in VOID or rest.rstrip().endswith("/"):
        continue
    if not closing:
        stack.append((name, m.start()))
    else:
        if not stack:
            errors.append("多余闭合 </%s> @%d" % (name, m.start()))
        elif stack[-1][0] != name:
            errors.append("错配：期望 </%s>（开于 @%d）实得 </%s> @%d"
                          % (stack[-1][0], stack[-1][1], name, m.start()))
            stack.pop()
        else:
            stack.pop()

ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', no_code)
rows = len(re.findall(r"<tr data-st=", src))
st = {k: len(re.findall(r'data-st="%s"' % k, src)) for k in EXPECT_ST}
p = {k: len(re.findall(r'data-p="%s"' % k, src)) for k in EXPECT_P}
ids = re.findall(r'(?<![\w-])id="([^"]+)"', no_code)
dup_ids = [k for k, v in collections.Counter(ids).items() if v > 1]
dead = [h for h in re.findall(r'href="#([^"]+)"', no_code) if h not in set(ids)]

# 逐行：data-st ↔ 可见 pill、工单号唯一
row_blocks = re.findall(r"<tr data-st=\"(\w+)\" data-p=\"(\w+)\">(.*?)</tr>", src, flags=re.S)
pill_bad, tickets = [], []
for stv, pv, body in row_blocks:
    m = re.search(r'class="pill (\w+)"', body)
    if not m:
        pill_bad.append(u"%s 行没有 pill" % stv)
    elif m.group(1) != stv:
        pill_bad.append(u"data-st=%s 但 pill=%s" % (stv, m.group(1)))
    # 号后面常跟 <br/><span class="ev">出处</span>，所以不能要求 </b> 紧接 </td>（17 行是这种）
    t = re.search(r"<td><b>([^<]+)</b>", body)
    tickets.append(t.group(1).strip() if t else u"<无号>")
dup_tickets = [k for k, v in collections.Counter(tickets).items() if v > 1]
no_ticket = [i for i, t in enumerate(tickets, 1) if t == u"<无号>"]

buttons = re.findall(r"filterBoard\('(\w+)'", src)
missing_filters = [f for f in FILTERS if f not in buttons]
has_cnt = "cnt" in set(ids)

print("未闭合:", stack)
print("配对错误:", len(errors))
for e in errors[:10]:
    print("  ", e)
print("外部资源:", len(ext), ext[:5])
print("死锚点:", dead)
print("id: %d 个，重复 %s" % (len(ids), dup_ids))
print("看板行数: %d（期望 %d）" % (rows, EXPECT_ROWS))
print("data-st 分布: %s（期望 %s）" % (st, EXPECT_ST))
print("data-p  分布: %s（期望 %s）" % (p, EXPECT_P))
print("分布合计: st %d / p %d（都应等于看板行数 %d）" % (sum(st.values()), sum(p.values()), rows))
print("逐行解析: %d 行；pill 与 data-st 不符 %d 条；工单号 %d 个，重号 %s，无号行 %s"
      % (len(row_blocks), len(pill_bad), len(tickets), dup_tickets, no_ticket))
print("筛选器: 实得 %s；缺 %s；id=cnt %s" % (buttons, missing_filters, has_cnt))

reds = []
if stack:
    reds.append("未闭合 %d 个" % len(stack))
if errors:
    reds.append("标签配对错误 %d 条" % len(errors))
if ext:
    reds.append("外部资源 %d 条（这份手册要离线能打开）" % len(ext))
if dead:
    reds.append("死锚点 %d 个" % len(dead))
if dup_ids:
    reds.append("重复 id %d 个：%s" % (len(dup_ids), dup_ids))
if rows != EXPECT_ROWS:
    reds.append("看板行数 %d ≠ %d" % (rows, EXPECT_ROWS))
if st != EXPECT_ST:
    reds.append("data-st 分布不符：%s ≠ %s" % (st, EXPECT_ST))
if p != EXPECT_P:
    reds.append("data-p 分布不符：%s ≠ %s" % (p, EXPECT_P))
if sum(st.values()) != rows or sum(p.values()) != rows:
    reds.append("分布合计与看板行数不自洽")
if len(row_blocks) != rows:
    reds.append("逐行解析只拿到 %d 行，与 <tr data-st= 的 %d 行不符（有行没闭合？）"
                % (len(row_blocks), rows))
if pill_bad:
    reds.append("pill 与 data-st 不符 %d 条：%s" % (len(pill_bad), pill_bad[:6]))
if dup_tickets:
    reds.append("工单号重号 %d 个：%s" % (len(dup_tickets), dup_tickets))
if no_ticket:
    reds.append("有 %d 行取不到工单号（行序 %s）" % (len(no_ticket), no_ticket[:6]))
if missing_filters:
    reds.append("筛选器缺 %s" % missing_filters)
if not has_cnt:
    reds.append('id="cnt" 不在（筛选计数没地方写）')

print("---- 静态闸结论 ----")
if reds:
    for r in reds:
        print("FAIL", r)
    print("红 %d 条" % len(reds))
    sys.exit(1)
print("全绿：未闭合 0 / 配对错误 0 / 外部资源 0 / 死锚点 0 / 重复 id 0 / 看板 %d 行 / "
      "两分布自洽 / pill 逐行相符 / 工单号唯一 / 十个筛选器齐" % rows)