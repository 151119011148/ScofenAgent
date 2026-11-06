# -*- coding: utf-8 -*-
"""v1.5 回写 agent功能手册.html：所有替换必须逐条命中一次，否则报错退出（不落半改）。"""
from pathlib import Path

P = Path("/Users/gaoying/Desktop/study/ai学习/agent功能手册.html")
src = P.read_text(encoding="utf-8")
ops = []


def rep(old, new, n=1):
    ops.append((old, new, n))


# ---- 标题 / §2 ----
rep("功能手册与迭代看板 — v1.4</title>", "功能手册与迭代看板 — v1.5</title>")
rep('<h2 id="s2">2 现状能力面（v1.4，全部实测）</h2>', '<h2 id="s2">2 现状能力面（v1.5，全部实测）</h2>')
rep("wc -l / ls 实测 · 2026-10-29 21:03（本轮）", "wc -l / ls 实测 · 2026-10-29 22:34（本轮）")
rep("<td>893 <span class=\"key\">↑ v1.3:850 ↑ v1.2:462 ↑ v1.1:76 ↑ v1.0:15</span></td>",
    "<td>1,108 <span class=\"key\">↑ v1.4:893 ↑ v1.3:850 ↑ v1.2:462 ↑ v1.1:76 ↑ v1.0:15</span></td>")
rep("<b>会话级记忆隔离：点旧会话能接着聊（V5，进程内）</b>、<b>历史库按题序落库（D6）</b>",
    "<b>会话级记忆隔离：点旧会话能接着聊（V5）</b>、<b>记忆落库：重启进程后模型那一边接着记得（V6）</b>、<b>停止落在待批卡之前不再死停（D7）</b>、<b>历史库按题序落库（D6）</b>")
rep("<b>44,838 B</b>（v1.3 是 41,871 B，v1.2 是 22,562 B）",
    "<b>55,774 B</b>（v1.4 是 44,838 B，v1.3 是 41,871 B）")

# 历史库那一行整行换掉（v1.5 之后事实变了）
old_db = None
for line in src.splitlines():
    if ".agent-history.sqlite3" in line and "<tr><td><code>smolagents/" in line:
        old_db = line
        break
assert old_db, "没找到历史库那一行"
new_db = ('  <tr><td><code>smolagents/.agent-history.sqlite3</code></td><td>单文件</td><td><b>v1.2 新增（V3）</b>：'
          '<b>三张</b>表 <code>sessions</code> / <code>messages</code> / <b><code>memory</code>（v1.5 起，V6）</b>，'
          '侧栏的历史与模型的记忆都在这里。<b>此刻磁盘上有</b>：'
          '<code>40,960 B</code>、2 条会话 / 27 行消息 / 2 行记忆（本轮交付形态实跑攒下的，验收数据要复现请先备份再删）。'
          '<code>my_ui.py:30</code> 按 <code>Path(__file__)</code> 定位，与 cwd 无关；v1.1~v1.4 读不到 <code>memory</code> 表，'
          '<b>留着无害</b>（实测 v1.4 代码在同一份库上读写正常、表原地不动）。'
          '<b>口径</b>：<code>messages</code> 是<b>屏上的话</b>，<code>memory</code> 是<b>模型读的那一串</b>'
          '（<code>{"fmt":"v1","steps":[…]}</code>，只存 <code>to_messages()</code> 用得到的字段，<code>model_input_messages</code> 与图片一律不存）。'
          'D5 已在 v1.4 修掉（连问不覆盖，改为累加），<b>V6 在 v1.5 修掉</b>（重启后模型接着记得）</td></tr>')
rep(old_db, new_db)

rep("<code>max_steps=8</code>，<code>stream_outputs=True</code>。<b>D1 链路关键</b>：<code>:8</code> 从 <code>my_coding_agent</code> import，所以那文件的模块级 <code>mkdir</code> 会执行。<b>v1.2 / v1.3 / v1.4 都没动</b>",
    "<code>max_steps=8</code>，<code>stream_outputs=True</code>。<b>D1 链路关键</b>：<code>:8</code> 从 <code>my_coding_agent</code> import，所以那文件的模块级 <code>mkdir</code> 会执行。<b>v1.2 / v1.3 / v1.4 / v1.5 都没动</b>")
rep("<b>v1.2 / v1.3 / v1.4 都没动</b>（与 <code>.rollback/v1.3</code>、<code>.rollback/v1.4</code> 存档逐字节 <code>cmp</code> 一致）",
    "<b>v1.2 / v1.3 / v1.4 / v1.5 都没动</b>（与 <code>.rollback/v1.4</code>、<code>.rollback/v1.5</code> 存档逐字节 <code>cmp</code> 一致）")
old_rb = ('<td>10 份</td><td><code>my_ui.py</code> 与 <code>my_coding_agent.py</code> 的 <b>v1.0 / v1.1 / v1.2 / v1.3 / v1.4</b> 五版存档'
          '（每版两份，共 10 个文件），回滚靠它（这几份 <code>my_*.py</code> 不在 git 里，见 D3）。'
          'v1.4 演练做了<b>双向</b>：切回 v1.3 存档 → <code>cmp</code> 一致 → 再切回本轮实跑版 → <code>cmp</code> 一致</td>')
assert src.count(old_rb) == 1, "存档行没命中"
rep(old_rb, ('<td>12 份</td><td><code>my_ui.py</code> 与 <code>my_coding_agent.py</code> 的 <b>v1.0 / v1.1 / v1.2 / v1.3 / v1.4 / v1.5</b> 六版存档'
             '（每版两份，共 12 个文件），回滚靠它（这几份 <code>my_*.py</code> 不在 git 里，见 D3）。'
             'v1.5 演练做了<b>双向</b>：切回 v1.4 存档（<b>15</b> 条断言 + 真启动一次）→ 再切回本轮实跑版（<b>13</b> 条）→ <code>cmp</code> 逐字节一致 → 重跑离线 65 条</td>'))

# ---- §2.5 标题与锚点行 ----
rep('<h3>2.5 界面构成、审批、刹车与会话连续性（v1.4 后，实测）</h3>',
    '<h3>2.5 界面构成、审批、刹车与会话连续性（v1.5 后，实测）</h3>')
old_src25 = None
for line in src.splitlines():
    if line.startswith('<div class="src">my_ui.py:529-548 状态条'):
        old_src25 = line
        break
assert old_src25, "§2.5 的 src 行没找到"
rep(old_src25,
    '<div class="src">my_ui.py:721-741 状态条 · :213-332 <code>DARK_CSS</code>（审批键 <code>:266-274</code>）· :642-693 <code>_step_card</code> · :597-621 <code>_approval_card</code> · :527-572 审批闸 · :742-884 线程驱动与流式渲染 · :885-912 <code>_bind_memory</code> · :929-987 <code>_respond</code> · :1038-1108 <code>create_app</code> · :59-211 记忆编解码（V6）· 离线 65 条断言（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_test.py</code>）+ CDP 实采（交付形态 7860 一路、探测口 7861 回滚演练一路，headless Chrome 9333）</div>')

rep("都出自 <code>_stats()</code>（<code>:502</code>）与 <code>_status_html()</code>（<code>:529-548</code>）",
    "都出自 <code>_stats()</code>（<code>:694</code>）与 <code>_status_html()</code>（<code>:721-741</code>）")
rep("<code>STATE_LABEL</code>，<code>:174-181</code>", "<code>STATE_LABEL</code>，<code>:334-343</code>")
rep("（<code>:44-49</code>），不是 <code>is_error</code>", "（<code>:46-51</code>），不是 <code>is_error</code>")
rep("<code>_worker</code>，<code>:550-573</code>", "<code>_worker</code>，<code>:742-766</code>")
rep("<code>_pending</code> 与 <code>_gate_lock</code> 挂<b>类</b>上（<code>:322-323</code>）——闸装在进程唯一的 agent 上，队列也必须是类级",
    "<code>_pending</code> 与 <code>_gate_lock</code> 挂<b>类</b>上（<code>:502-503</code>）——闸装在进程唯一的 agent 上，队列也必须是类级；v1.5 的 <code>_run_seq</code>/<code>_cancelled_before</code>（<code>:507-508</code>）<b>同理必须类级</b>")
rep("<code>APPROVAL_TIMEOUT = 600.0</code>（<code>:34</code>）", "<code>APPROVAL_TIMEOUT = 600.0</code>（<code>:36</code>）")
rep("v1.3 追加两枚审批键的配色（<code>:106-115</code>）", "v1.3 追加两枚审批键的配色（<code>:266-274</code>）")
rep("<code>_user_message()</code>，<code>:712-726</code>", "<code>_user_message()</code>，<code>:913-928</code>")
rep("<code>my_ui.py:456-460</code>", "<code>my_ui.py:648-653</code>", 2)

# 会话侧栏那一行：记忆不落库 → 落库
rep('（<code>sessions</code> + <code>messages</code>，<code>ON DELETE CASCADE</code>）。<b>库里的字是屏上的字，不是模型的记忆</b>——v1.4 起两者<b>按会话一一对应</b>',
    '（<code>sessions</code> + <code>messages</code> + <b><code>memory</code>（v1.5）</b>，全 <code>ON DELETE CASCADE</code>）。<b><code>messages</code> 是屏上的字，<code>memory</code> 是模型读的那一串</b>——v1.4 起两者<b>按会话一一对应</b>')
rep('<b>但记忆不落库</b>，重启后字还在、模型不记得（V6）。',
    '<b>v1.5 起记忆也落库</b>（V6）：重启后点回旧会话，模型那一边接着记得（实测答 <b>73</b>、<code>in 2,574</code>）。')

# 刹车行：v1.4 的 D7 例外 → v1.5 已修
old_d7c = ('<span class="key">v1.4 实测出一条例外，记为 D7</span>：停止按在待批卡<b>出现之前</b>（0.2s 那一下）等于空放——'
           '<code>agents.py:470</code> 在新 run 开头把 <code>interrupt_switch</code> 清回 <code>False</code>，后到的那条待批没人结算，'
           '界面死停在 <code>等待审批</code>（实测挂 <b>142.4s</b>，补点 ✖ 拒绝才解开），见 §4.1。')
assert src.count(old_d7c) == 1, "刹车行 D7 那句没命中"
rep(old_d7c, '<span class="key">v1.4 实测出的那条例外（D7）已在 v1.5 修掉</span>：<code>_stop</code> 先给本轮打<b>取消号</b>，'
             '闸在入队那一刻看到号就在<b>同一个临界区</b>里直接按 <code>cancelled</code> 结算'
             '（<code>my_ui.py:564-566</code>、<code>:1007-1008</code>），两种到达顺序都覆盖、窗口关死。'
             'v1.5 在<b>交付形态 7860</b> 复测同一时机（提问后 0.2s 按停止）：<b>从没进过</b>「等待审批」，1.2s 落到已停止、观察 26s 没回潮。见 §4.1。')

# D5 / V5 / D6 三行的锚点
rep("<code>base = self.hist.load(sid)</code>（<code>:730-737</code>）", "<code>base = self.hist.load(sid)</code>（<code>:936</code>）")
rep("<code>last = base + [user_msg] + msgs</code>（<code>:746-747</code>，v1.3 是 <code>[user_msg] + msgs</code>）",
    "<code>last = base + [user_msg] + msgs</code>（<code>:948</code>，v1.3 是 <code>[user_msg] + msgs</code>）")
rep("<code>_bind_memory(sid)</code>（<code>my_ui.py:690-709</code>）把引用换成 <code>self._mem[sid]</code>（<code>:335-338</code>）",
    "<code>_bind_memory(sid)</code>（<code>my_ui.py:885-912</code>）把引用换成 <code>self._mem[sid]</code>（<code>:522-523</code>）")
rep("<code>_select_session</code> 交出第三个值 <code>int(sid)</code>（<code>:799-808</code>）", "<code>_select_session</code> 交出第三个值 <code>int(sid)</code>（<code>:1014-1024</code>）")
rep("<code>_on_load</code> 从闭包提成方法并把 <code>sid</code> 指到侧栏第一条（<code>:810-820</code>）", "<code>_on_load</code> 从闭包提成方法并把 <code>sid</code> 指到侧栏第一条（<code>:1025-1037</code>）")
rep("<span class=\"r\">边界</span>：<code>AgentMemory</code> 没有 (de)serializer（<code>memory.py:214-232</code>），<b>重启即忘</b>——实测重启后屏上 4 行历史都在、模型答「不记得」，见 §4.3 的 V6",
    "<span class=\"r\">边界（v1.4 时）</span>：<code>AgentMemory</code> 没有 (de)serializer（<code>memory.py:214-232</code>），所以 v1.4 <b>重启即忘</b>——<b>v1.5 由 V6 自己补了一层</b>：按 <code>to_messages()</code> 读到的字段清单序列化落库、重启后回灌，见下一行")
rep("<code>UPDATE sessions SET updated_at=?, title=CASE WHEN title='新会话' THEN ? ELSE title END</code>（<code>:291-298</code>）",
    "<code>UPDATE sessions SET updated_at=?, title=CASE WHEN title='新会话' THEN ? ELSE title END</code>（<code>:461</code>）")

# §2.5 追加两行（接在 D6 行后面）
d6_tail = "离线 8a~8e 五条断言，其中 8c 是\"老会话一有动作就回到第一\"的正向断言</td></tr>"
assert src.count(d6_tail) == 1, "D6 行尾没命中"
new_rows25 = (
    '  <tr><td><b>记忆持久化</b>（V6，v1.5）</td>'
    '<td><b>关掉再开，选中旧会话接着问，模型那一边真的记得</b>：答 <b>73</b>；<code>run_python</code> 跑出来的 <code>21</code> 隔两次重启还答得出来</td>'
    '<td>库里第三张表 <code>memory</code>（<code>:401</code>，additive）一行一条会话，内容 <code>{"fmt":"v1","steps":[…]}</code>。'
    '<b>存的是 <code>to_messages()</code> 用得到的字段，不是屏幕文字</b>（<code>agents.py:767-769</code>）；'
    '<code>steps</code> 只会出现 <code>TaskStep</code>/<code>ActionStep</code>/<code>PlanningStep</code>——<code>FinalAnswerStep</code> 只 yield（<code>agents.py:609-611</code>）。'
    '<b>四个坑</b>：① <code>AgentError.__init__(message, logger)</code> 会<b>当场</b> <code>log_error</code> → 用 <code>cls.__new__(cls)</code> 造；'
    '② <code>ToolCall</code> 要 <code>tc.dict()</code>（OpenAI function 形状），不是 <code>asdict</code>；'
    '③ <code>Timing.duration</code> 是 property、<code>TokenUsage.total_tokens</code> 是 <code>init=False</code> 派生，只交构造参数；'
    '④ <code>make_json_serializable</code>（<code>utils.py:146-153</code>）会把<b>长得像 JSON 的字符串解析成 dict</b>，所以文本字段一律原样存。'
    '<span class="key">不存的两块</span>：<code>model_input_messages</code>（整段提示词，O(n²)）与图片三兄弟 → <b>带图的观察值重启后进不了模型上下文</b>【多图会话未验证】。'
    '<b>坏数据降级</b>：整块坏＝当作没记忆，单条坏＝只跳那一条。落库时机在 <code>_respond</code> 的 <code>finally</code>，判据 <code>_mem_sid == sid</code>（中途换会话不盖别人），'
    '<b>半截可接受</b>。实测交付形态：<code>in 2,362 → 2,465 →</code>（重启）<code>2,574 → 2,675 →</code>（二次重启）<code>3,091</code>，而新会话恒为 <b>2,363</b></td></tr>\n'
    '  <tr><td><b>停止的取消号</b>（D7，v1.5）</td>'
    '<td>■ 停止按在待批卡出现<b>之前</b>也不再死停：状态走到<b>已停止</b>，✔/✖ 不会一直挂着</td>'
    '<td>类级 <code>_run_seq</code> / <code>_cancelled_before</code>（<code>:507-508</code>）：'
    '<code>_stream_response</code> 起线程<b>之前</b>领号（<code>:778</code>），<code>_stop</code> 把号抬到当前轮（<code>:1008</code>），'
    '<code>_gated_call</code> 在<b>入队那同一个临界区</b>里判号并直接 <code>decide("cancelled")</code>（<code>:564-566</code>）——'
    '闸先到 / 停止先到两种顺序都被覆盖。离线 3a~3l 十七条（含 3l 端到端），交付形态 0.2s 那一路实测 <b>1.2s 落到已停止</b>。'
    '<span class="key">代价</span>：号是<b>类级</b>的，一个标签按停止会让所有在飞的待批一起被取消【未验证，当前仍假设一次一题】</td></tr>\n')
rep(d6_tail, d6_tail + "\n" + new_rows25.rstrip("\n"))

# ---- §4 看板 ----
rep('<h2 id="s4">4 缺口看板（33 条，编号即工单号）</h2>', '<h2 id="s4">4 缺口看板（34 条，编号即工单号）</h2>')
rep('<span class="cnt" id="cnt">显示 33 / 33 条</span>', '<span class="cnt" id="cnt">显示 34 / 34 条</span>')
rep('<h3>4.1 缺陷七条（D1 v1.1、D4 v1.3、D5 + D6 v1.4 已上线；D2 待你定性、D3 未动、D7 v1.4 新立）</h3>',
    '<h3>4.1 缺陷七条（D1 v1.1、D4 v1.3、D5 + D6 v1.4、D7 v1.5 已上线；D2 待你定性、D3 未动）</h3>')

d7_open = '  <tr data-st="todo" data-p="D"><td><b>D7</b></td>'
assert src.count(d7_open) == 1
rep(d7_open, '  <tr data-st="done" data-p="D"><td><b>D7</b></td>')
rep('<b>v1.4 复现并定位（未修）</b>。<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_d7.js</code>', '<b>v1.4 复现并定位 · v1.5 已修并复测</b>。<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_d7.js</code>')
d7_fix = '两条修法：① 闸在入队前先查取消标记；② <code>_stop</code> 给本轮打 <code>run_id</code> 取消标记，入队时看到标记直接按 <code>cancelled</code> 结算。几十行 · <b>建议与 V6 同批（v1.5）</b></td>\n    <td><span class="pill todo">未开工（v1.4 新立）</span></td></tr>'
assert src.count(d7_fix) == 1, "D7 手段+状态没命中"
rep(d7_fix, '<b>已做（v1.5）＝第 ② 条</b>：类级 <code>_run_seq</code>/<code>_cancelled_before</code>（<code>my_ui.py:507-508</code>），'
            '<code>_stop</code> 打号（<code>:1008</code>）、闸在<b>入队那同一个临界区</b>判号自结算（<code>:564-566</code>）、开跑先领号（<code>:778</code>）。'
            '几十行 · 与 V6 同批上线</td>\n    <td><span class="pill done">已上线 v1.5</span></td></tr>')
rep('对照组（2.0s 按停止，卡已在屏上）：0.5s 内 <code>⏹ … 随停止取消</code>，正常</td>',
    '对照组（2.0s 按停止，卡已在屏上）：0.5s 内 <code>⏹ … 随停止取消</code>，正常。<b>v1.5 在交付形态 7860 复测 0.2s 那一路</b>：<code>awaitingSeen 0</code>、1.2s <code>已停止</code>、观察 26s 没回潮；离线 3a~3l 十七条（3c 原工具零调用、3m 观察值＝取消那句、3o 半截也落库带 <code>⏹</code>）</td>')

v6_open = '  <tr data-st="todo" data-p="V"><td><b>V6</b></td>'
assert src.count(v6_open) == 1
rep(v6_open, '  <tr data-st="done" data-p="V"><td><b>V6</b></td>')
v6_tail = ('两条路：① 把 <code>AgentMemory</code> 序列化进 SQLite——框架<b>没有 (de)serializer</b>（<code>memory.py:214-232</code> 只有 <code>system_prompt</code> + <code>steps</code> + <code>reset()</code>），'
           '得自己定 <code>Step</code> 各子类的存取格式；② 每轮从库里把对话<b>重放</b>成 <code>TaskStep</code>/<code>ActionStep</code> 灌回去——它要重定"本题累计"的边界，且 <code>in</code> 会随历史线性涨。'
           '<b>需要设计，不是界面活</b>。<b>建议 v1.5 = V6 + D7 同批</b></td>\n    <td><span class="pill todo">未开工（v1.4 新立）</span></td></tr>')
assert src.count(v6_tail) == 1, "V6 手段+状态没命中"
v7_row = ('  <tr data-st="todo" data-p="V"><td><b>V7</b></td>\n'
          '    <td><b>侧栏选中态陈旧</b>：点「＋ 新会话」后 radio 仍留着上一条的 <code>checked</code>，于是"点那条高亮着的旧会话"＝空点</td>\n'
          '    <td class="ev">v1.4 记下的是"高亮没跟"（纯界面层）；<b>v1.5 造成了真后果</b>：那一按不触发 change 事件，问题落进了<b>新会话</b>——'
          '探测口实测 <code>in 2,463</code>、答「不记得」，数据没坏、只是进错了门。反证 <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_leg.js</code>：每次点击前先读 <code>before-checked</code>，'
          '<code>before-checked=0</code> 时点击正常（<code>checked#1</code>、屏上换回 6 行、答 <b>73</b>）</td>\n'
          '    <td>不是数据错、是<b>点错门</b>：用户以为在接着聊旧会话，其实模型那边是开局。V6 上线后这条更容易撞上——因为"点旧会话"现在真的会带记忆</td>\n'
          '    <td><code>_new_session</code>（<code>my_ui.py:988-991</code>）把 radio 的值同步成那条新会话（或反过来：<code>checked</code> 由 <code>sid</code> 单向驱动）。'
          '一两句 · 纯界面层 · <b>建议 v1.6</b></td>\n'
          '    <td><span class="pill todo">未开工（v1.5 新立）</span></td></tr>')
rep(v6_tail, '<b>已做（v1.5）＝第 ① 条</b>：字段级序列化（<code>MEM_FIELDS</code> <code>my_ui.py:59-76</code>、编解码 <code>:119-211</code>），'
             '库里第三张表 <code>memory</code>；回灌在 <code>_bind_memory</code>（<code>:905-907</code>）、落库在 <code>_respond</code> 的 <code>finally</code>（<code>:984-985</code>）。'
             '<b>为什么不是 ②</b>：模型读的是 <code>memory.steps</code> 而不是屏幕文字（<code>agents.py:767-769</code> 的 <code>write_memory_to_messages()</code>），'
             '重放屏幕文字要重定"本题累计"边界、<code>in</code> 线性涨。'
             '实测：交付形态跨两次重启答回 <b>73</b> 与 <b>21</b>；新会话仍 <code>不记得</code>（<code>in 2,363</code>）；离线 1n 用<b>框架自己的</b> <code>write_memory_to_messages()</code> 逐字比对回灌前后</td>\n'
             '    <td><span class="pill done">已上线 v1.5</span></td></tr>\n' + v7_row)

# ---- §4.5 推荐卡 ----
old_rec = None
for line in src.splitlines():
    if '<b>我推荐的下一刀（v1.5）：</b>' in line:
        old_rec = line
        break
assert old_rec, "推荐卡没找到"
rep(old_rec, '  <b>我推荐的下一刀（v1.6）：</b><span class="key">V7 侧栏选中态同步 ＋ 把审批等待时长从步骤耗时里单列</span>。')
rep('  V5 在 v1.4 只上到<b>进程内</b>那一半——屏上的字能跨会话读回来，模型的记忆不行（实测重启后同一题 <code>in 3,384</code>、答「不记得」）。\n', '')
rep('  D7 只是闸在入队前少查了一个取消标记，几十行，和本批的会话/记忆改动是同一片代码，顺手一起收。\n',
    '  V6 + D7 已按上一轮的推荐上线为 <b>v1.5</b>（验收见 §6.1）。剩下的两笔都不大但是真硌手：'
    '<b>V7</b> 让"点旧会话"不再点错门（v1.5 撞实了后果）；审批等待现在算进步骤耗时（实测一格 <code>272.9s</code>，真执行 ~1s），单列出来读得住。\n')
rep('  <b>上一轮推荐（D5 + V5）已按此上线为 v1.4</b>，验收见 §6.1；更早三轮（V4 + P0-2、V1+V2+V3、D1+P0-5+P0-1）的"当时的推荐 + 实际走向"记在 §6.2 / §6.3 / §6.4 的遗留里。\n',
    '  <b>更早四轮</b>（D5 + V5、V4 + P0-2、V1+V2+V3、D1+P0-5+P0-1）都按当时的推荐上线，"实际走向"记在 §6.2 / §6.3 / §6.4 / §6.5 的遗留里。\n')

# ---- §5.1 ----
rep('现有 <code>v1.0 / v1.1 / v1.2 / v1.3 / v1.4</code> 五套（共 10 个文件，<code>my_ui.py</code> + <code>my_coding_agent.py</code> 各一份）',
    '现有 <code>v1.0 / v1.1 / v1.2 / v1.3 / v1.4 / v1.5</code> 六套（共 12 个文件，<code>my_ui.py</code> + <code>my_coding_agent.py</code> 各一份）')
rep('侧栏的会话与消息，单文件。<b>不是代码、不进存档</b>；回滚只回代码，这个文件要不要留由你定（v1.1 读不到它，留着也无害）',
    '侧栏的会话与消息，<b>加模型的记忆</b>（v1.5 的第三张表 <code>memory</code>），单文件。<b>不是代码、不进存档</b>；回滚只回代码，这个文件要不要留由你定（v1.1~v1.4 读不到 <code>memory</code> 表，留着也无害，实测过）')

# ---- §6 引用与标题顺移（先改引用，再改标题；从高到低避免撞车）----
rep('这是有意为之，见 §6.3 口径第 2、4 条。', '这是有意为之，见 §6.4 口径第 2、4 条。')
rep('于是 v1.3 照此上线，验收见 §6.2。', '于是 v1.3 照此上线，验收见 §6.3。')
rep('§6.1 那批复跑命令用的脚本——', '§6.1 / §6.2 两批复跑命令用的脚本——')
rep('<h3>6.5 v1.0 ·', '<h3>6.6 v1.0 ·')
rep('<h3>6.4 v1.1 ·', '<h3>6.5 v1.1 ·')
rep('<h3>6.3 v1.2 ·', '<h3>6.4 v1.2 ·')
rep('<h3>6.2 v1.3 ·', '<h3>6.3 v1.3 ·')
rep('<h3>6.1 v1.4 ·', '<h3>6.2 v1.4 ·')

# ---- §7 待补条目 ----
rep('  <li>【待补】<b>记忆只在进程里</b>（V6 的那一半）：v1.4 实测——重启探测口 → 选中旧会话问「最早让你记住的数字」，屏上 4 行历史都在、模型答 <code>Final answer: 不记得</code>，本题 <code>in 3,384</code>（框架日志 <code>Step 3: Input tokens 9,015</code>，差额正好是没带上会话历史）。<b>序列化格式、重放边界、"本题累计"怎么重新定义，都还没设计</b>。</li>',
    '  <li>【已上线 v1.5，剩两块没测】<b>记忆持久化（V6）</b>：序列化格式、回灌路径、"本题累计"边界都已实测（离线 65 条 + 交付形态跨两次重启）。'
    '<b>仍缺的</b>：① <b>带图的观察值</b>故意不入库，多图会话重启后到底缺什么<b>没有数据</b>；② <code>PlanningStep</code> 那条分支（<code>my_ui.py:169-180</code>）'
    '在 v1.5 的编解码里是<b>照字段写了</b>，但 qwen-plus 到现在没在这些题面上产出过计划步 → <b>计划步的存取往返【未验证】</b>。')
rep('  <li>【待补】<b>D7 只在探测口 7861 复现过</b>（提问后 0.2s 按 ■ 停止 → 死停 <code>等待审批</code> 142.4s）；<b>交付形态 7860 上没试过这个时机</b>。而且"线上真等满 600 秒会怎样"仍然没有数据。</li>',
    '  <li>【已修 v1.5，仍欠一条】<b>D7</b> 在<b>交付形态 7860</b> 上复测过 0.2s 那一路：从没进过「等待审批」、1.2s 落到已停止。'
    '<b>"线上真等满 600 秒会怎样"仍然没有数据</b>（只做过把常量压到 1 秒的离线验证）。</li>')
rep('  <li>【待补】v1.4 的累加只测到<b>三问一答</b>的规模（<code>in 2,362 → 2,464 → 2,564</code>，每题约 +100）。十几问、或中间夹多步工具调用之后 <code>in</code> 的增长曲线、以及它什么时候开始挤到上下文上限，<b>没有数据</b>。</li>',
    '  <li>【待补】累加与持久化的<b>规模上限</b>：v1.5 最长的一条跑到<b>五问 / 15 步 / payload 4,042 字符</b>（<code>in 2,362 → 2,465 → 2,574 → 2,675 → 3,091</code>，其中含一次多步工具调用）。'
    '十几问之后 <code>in</code> 的曲线、什么时候挤到上下文上限、<code>payload</code> 会不会胀到拖慢启动，<b>仍然没有数据</b>。</li>')
old_sel = None
for line in src.splitlines():
    if '侧栏选中态与 <code>sid</code> 不同步' in line and line.strip().startswith("<li>"):
        old_sel = line
        break
assert old_sel, "侧栏选中态那条没找到"
rep(old_sel, '  <li><b>【已立单 V7，见 §4.5】侧栏选中态与 <code>sid</code> 不同步</b>：v1.4 只当"高亮没跟"，'
             '<b>v1.5 撞出真后果</b>——点「＋ 新会话」后 radio 仍留着上一条的 <code>checked</code>，再点那条高亮的旧会话＝点了个没变的值，'
             '<b>不触发 change</b>，问题落进新会话（实测 <code>in 2,463</code>、答「不记得」，数据没坏、只是进错门）。本轮范围外，未改。</li>')
rep('  <li>【待补】<b>并发提问</b>：两个标签同时问会共用同一个 agent，而 <code>_mem_sid</code> 是<b>单值</b>——两边会互相抢"当前绑到哪条会话"，<code>monitor</code> 同样共享。当前设计仍假设<b>一次只问一题</b>，这条从没实测过。</li>',
    '  <li>【待补】<b>并发提问</b>：两个标签同时问会共用同一个 agent，<code>_mem_sid</code> 是<b>单值</b>，v1.5 起 <code>_run_seq</code>/<code>_cancelled_before</code> 也是<b>类级</b>——'
    '一个标签按停止会让<b>所有</b>在飞的待批一起被结算。当前设计仍假设<b>一次只问一题</b>，这条从没实测过。</li>')
rep('  <li>【未验证】<b>审批超时 600 秒</b>只做过离线验证',
    '  <li>【未验证】<b>审批等待算进耗时</b>（v1.5 实测一格 <code>272.9s</code>，真执行约 1s，因为含挂在卡上的时间）——口径要不要把"等待"单列，见推荐的第二件。\n'
    '  <li>【未验证】<b>审批超时 600 秒</b>只做过离线验证')
rep('      <li><code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_test.py</code>（离线 53 条断言）· <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_ui.py</code>（探测口装配）</li>',
    '      <li><code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_test.py</code>（离线 <b>65</b> 条）· <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_ui.py</code>（探测口装配）· <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_rollback_check.py</code>（双向 + 跨版本读库）</li>\n'
    '      <li><code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_drive.js</code>（s1~s5）· <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_d7.js</code> · <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_leg.js</code> / <code>v15_leg_tool.js</code> · <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_appr.js</code> / <code>v15_appr2.js</code></li>\n'
    '      <li><code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_test.py</code>（离线 53 条断言）· <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14_ui.py</code>（探测口装配）</li>')
rep('    重启或 <code>/tmp</code> 清理后，只剩记录里的输出、命令跑不动。v1.0~v1.4 五轮都是这个状态。<b>要不要在 <code>ai学习/</code> 下开一个 <code>验收脚本/</code>（按版本号分目录）收进来，等你点头</b>——新增目录不在本轮 D5+V5 范围内。</li>',
    '    重启或 <code>/tmp</code> 清理后，只剩记录里的输出、命令跑不动。v1.0~v1.5 <b>六轮</b>都是这个状态。<b>要不要在 <code>ai学习/</code> 下开一个 <code>验收脚本/</code>（按版本号分目录）收进来，等你点头</b>——新增目录不在本轮 V6+D7 范围内。</li>')

# ---- 页脚 ----
rep('  v1.4 · 建档 2026-10-28 · 回写 2026-10-29 ·', '  v1.5 · 建档 2026-10-28 · 回写 2026-10-29 ·')

for old, new, n in ops:
    c = src.count(old)
    assert c == n, "命中 %d 次（期望 %d）：%.70s" % (c, n, old)
    src = src.replace(old, new)

# 插入新 §6.1（放在 §6.2 v1.4 标题之前）
anchor = '<h3>6.2 v1.4 ·'
assert src.count(anchor) == 1
block = Path("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15_record.html").read_text(encoding="utf-8")
src = src.replace(anchor, block + anchor)

P.write_text(src, encoding="utf-8")
print("写入完成：%d 行 / %d B" % (len(src.splitlines()), len(src.encode())))
