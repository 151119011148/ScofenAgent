# -*- coding: utf-8 -*-
"""手册 HTML 第 4 节看板：D8 新行、V9 转已上线、计数与推荐下一刀。"""
import io

P = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
t = io.open(P, encoding="utf-8").read()


def rep(old, new):
    global t
    n = t.count(old)
    assert n == 1, "count=%d for %r" % (n, old[:60])
    t = t.replace(old, new)


rep(u'<h2 id="s4">4 缺口看板（36 条，编号即工单号）</h2>',
    u'<h2 id="s4">4 缺口看板（37 条，编号即工单号）</h2>')
rep(u'<span class="cnt" id="cnt">显示 36 / 36 条</span>',
    u'<span class="cnt" id="cnt">显示 37 / 37 条</span>')
rep(u'<h3>4.1 缺陷七条（D1 v1.1、D4 v1.3、D5 + D6 v1.4、D7 v1.5 已上线；D2 待你定性、D3 未动）</h3>',
    u'<h3>4.1 缺陷八条（D1 v1.1、D4 v1.3、D5 + D6 v1.4、D7 v1.5 已上线；D2 待你定性、D3 未动、<b>D8 v1.7 新立</b>）</h3>')

D7TAIL = u'''    <td><span class="pill done">已上线 v1.5</span></td></tr>
</table>

<h3>4.2 P0'''
D8 = u'''    <td><span class="pill done">已上线 v1.5</span></td></tr>
  <tr data-st="todo" data-p="D"><td><b>D8</b></td>
    <td><b>正在流式（尤其挂在审批闸上等人点）的时候刷新页面或关页面 → 这一题<u>一行都不落库</u></b>：屏上曾经有字，事后什么都没有</td>
    <td class="ev"><b>v1.7 实跑撞出来的，两条路都有留痕</b>（<code>/tmp/v17_drain.out</code>、<code>/tmp/v17_finish.out</code>、<code>/tmp/v17_peek.out</code>）。CDP 每份剧本开头都会 <code>Page.navigate</code>，中途去 peek 一下就是把正在流式的那一题掐断：进程内状态条仍报 <code>步数 3/8 本题 in 7,334/out 63 本题耗时 25.1s 本题审批 22.1s</code>（另一条 <code>步数 1/8 27.2s / 26.0s</code>），屏上却是 <code>bot=0</code>（一个气泡都没有）；库里那条会话<b>只有 <code>_respond</code> 开头 <code>ensure</code> 建的那一行会话</b>，<code>messages</code> 0 行、<code>memory</code> 没写；<code>待批 run_python</code> 的 pill 挂在状态已经是「空闲」的条上，<code>#approve-btn</code> reload 后 <code>NO-ELEMENT</code>；两次 <code>until DONE</code> 分别跑到 <b>120,353ms</b> 与 <b>300,967ms</b> 超时。<b>这是 v1.6 就有的行为，不是 V9 的回归</b>（改成「一整轮只跑一份剧本」之后探测口与交付形态两轮都干净跑通）</td>
    <td><b>会丢用户内容</b>，而且是看板里唯一还在丢的这一条量级：一屏字 ＋ 那笔审批等待一起蒸发。v1.5 那句「半截可接受」的前提是半截会落库，实测<b>连半截都没有</b></td>
    <td>先问三件事（<span class="r">机制【未验证】</span>）：① 客户端断开时 <code>_respond</code> 的 <code>finally</code> 到底跑没跑到（gradio 会不会 <code>close()</code> 那条生成器）；② worker 正阻塞在 <code>ap.wait()</code> 时那条 <code>pending</code> 怎么随断开结算——现在只能等 <code>APPROVAL_TIMEOUT=600s</code> 自己按拒绝结算；③ 选「落半截」还是「标已中断」。<b>几十行 · 数据完整性优先</b>，<b>建议 v1.8 第一刀</b></td>
    <td><span class="pill todo">未开工（v1.7 新立）</span></td></tr>
</table>

<h3>4.2 P0'''
rep(D7TAIL, D8)

rep(u'    <td class="ev">v1.6 §6.2 立下的边界：<code>_opsui_wait</code> 是 step 对象上的私有属性，<code>encode_memory</code> 的字段白名单不认它 → 回放的老卡片只有「本题耗时」、没有「审批」那一格（离线 6n/6o 两面都断言过，是<b>写下来的边界</b>不是 bug）</td>',
    u'''    <td class="ev">v1.6 §6.3 立下的边界：<code>_opsui_wait</code> 是 step 对象上的私有属性，<code>MEM_FIELDS</code>（<code>:69-88</code>）不认它 → 落库那串里<b>根本没有 wait 这个键</b>（v1.7 基线 A 实测：payload 出现过的键只有八个 <code>_t / is_final_answer / observations / step_number / task / timing / token_usage / tool_calls</code>，<code>fmt</code> 仍是 v1）。<b>基线 B 顺手推翻了 v1.6 注释里的一句话</b>：屏上那张历史卡<b>一直带着</b>「（含审批 …）」（卡片正文走 <code>messages</code> 表，实测 4 条消息里 1 条含「含审批」）→ 真读不出的只有状态条 / <code>_stats</code> 那一串数</td>''')

rep(u'    <td>重启后回看一条跑过审批的旧会话，读不出"当时等了多久"。日常影响小，但和 V6 的"跨重启接着记得"放在一起就不自洽</td>',
    u'''    <td>重启后回看一条跑过审批的旧会话，状态条读不出「当时等了多久」；<b>基线 C 又量到一条</b>：点旧会话时状态条报的是「上一次提问那条」，什么都没提问过时是空的 <code>0/8</code>——屏上是甲、条上是乙。日常影响小，但和 V6 的「跨重启接着记得」放在一起就不自洽</td>''')

V9OLD = u'''    <td>白名单加一个字段 + <code>fmt</code> 版本判断，旧 payload 照读。<b>估计几十行 · 纯界面/编解码层</b>；<b>建议 v1.7</b>，P0-4 往后排</td>
    <td><span class="pill todo">未开工（v1.6 新立）</span></td></tr>'''
V9NEW = u'''    <td><b>已做（v1.7）＝编解码多一格 ＋ 只读出口</b>：<code>MEM_FMT="v2"</code> ＋ <code>MEM_FMT_READ=("v1","v2")</code>（<code>:63</code> / <code>:68</code>）、<code>encode_memory</code> 的 <code>ActionStep</code> 分支写 <code>row["wait"]</code>（<code>:162-168</code>，真等过才写）、<code>decode_memory</code> 挂回 <code>step._opsui_wait</code>（<code>:225-229</code>）、新增 <code>_session_steps</code>（<code>:988-1006</code>）喂 <code>_stats(steps=…)</code>（<code>:749-752</code>），调用点是 <code>_select_session</code>（<code>:1160</code>）与 <code>_on_load</code>（<code>:1180</code>）。<b>白名单一个字没动</b>（<code>wait</code> 不在里面，离线 7d 断言模型读到的那串逐字不变）。实测：交付形态真重启后第一次加载即 <code>本题耗时 23.4s / 本题审批 20.7s</code>；库里新增 sid 8 <code>fmt=v2</code>、<code>wait=[20.672, 无]</code>，<b>旧 7 行 sha1 逐行不变</b>；离线 115 条（含 V9 二十二条）。<span class="key">代价</span>：兼容读<b>只朝一个方向</b> → 回滚把 v1.7 的账变成没记忆（§6.1 第 5 节）</td>
    <td><span class="pill done">已上线 v1.7</span></td></tr>'''
rep(V9OLD, V9NEW)

rep(u'  <tr data-st="todo" data-p="V"><td><b>V9</b></td>',
    u'  <tr data-st="done" data-p="V"><td><b>V9</b></td>')

RECOLD = u'''<div class="card ok">
  <b>我推荐的下一刀（v1.7）：</b><span class="key">V9 让审批等待跨重启也读得出（<code>MEM_FMT</code> 升 v2 ＋ 兼容读 v1）</span>。
  V7 + V8 已按上一轮的推荐上线为 <b>v1.6</b>（验收见 §6.1）。剩下的候选：<b>V9</b> 是 v1.6 自己立下的边界，改的是同一处白名单；<b>P0-4</b>（计划可见）的地基已被 v1.3 的线程 + 允许/拒绝键铺好，随时能接。
  <b>更早五轮</b>（D5 + V5、V4 + P0-2、V1+V2+V3、D1+P0-5+P0-1）都按当时的推荐上线，"实际走向"记在 §6.2 ~ §6.6 的遗留里。
  <b>D2</b>（staging 副本读不回来）仍挂着等你定性。
</div>'''
RECNEW = u'''<div class="card ok">
  <b>我推荐的下一刀（v1.8）：</b><span class="key">先 <b>D8</b>（流式中刷新／关页面 → 这一题一行都不落库），再 <b>P0-4</b>（计划可见）</span>。
  D8 是 v1.7 实跑抓出来的<b>数据完整性</b>问题（一屏字能整轮丢，两次超时留痕 <b>120,353ms</b> / <b>300,967ms</b>），基线已经写在 §6.1 第 7 节；P0-4 是<b>新功能</b>，地基（v1.3 的线程 ＋ 允许/拒绝键）本来就铺好了，往后排一格不亏。
  <b>已上线</b>：V7 + V8 → <b>v1.6</b>（验收见 §6.2）、V9 → <b>v1.7</b>（验收见 §6.1）。
  <b>更早五轮</b>（D5 + V5、V4 + P0-2、V1+V2+V3、D1+P0-5+P0-1）都按当时的推荐上线，「实际走向」记在 §6.3 ~ §6.7 的遗留里。
  <b>D2</b>（staging 副本读不回来）仍挂着等你定性。
</div>'''
rep(RECOLD, RECNEW)

io.open(P, "w", encoding="utf-8").write(t)
print("batch3 ok")
