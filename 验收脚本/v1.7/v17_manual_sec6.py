# -*- coding: utf-8 -*-
"""把手册 §6.1（v1.7 全节）插到 §6.2 之前。"""
import io

P = u"/Users/gaoying/Desktop/study/ai学习/agent功能手册.html"
t = io.open(P, encoding="utf-8").read()

NEW = u'''<h3>6.1 v1.7 · 2026-10-30 · 「本题审批」跟着记忆进库：重启、点旧会话都读得出那一格（<b>V9</b>）</h3>
<div class="src">范围按工单号锁定 <b>V9</b>（<code>my_coding_agent.py</code>、<code>my_agent.py</code>、上游源码零改动；<b>库 schema 零改动</b>，只是 payload 里多一个可选键；审批闸的<b>判定</b>、停止的语义、V7 的高亮、V8 的记账链路一行未碰——只在这条链的<b>末端</b>多写一格、多读一格）· 全文见 <code>迭代记录.md</code> v1.7 一节</div>

<h4>1 这次解决什么</h4>
<ul class="tight">
  <li><b>基线先跑，被测模块换成归档的 <code>.rollback/v1.6/my_ui.py</code></b>（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_base_v16.py</code> → <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_base_v16.out</code>，13 条全 PASS）。为什么不能用现网代码重跑：上线之后真实库里已经多了一条<b>真 v2</b> payload，拿 v1.7 代码原样跑会把"缺口复现"跑成"缺口已关"，数字就不配当基线。</li>
  <li><b>A 缺口本体</b>：活进程里那一格看得见（<code>task_wait 0.61s</code>、pill 在），但落库那串里<b>根本没有 <code>wait</code> 这个键</b>——payload 出现过的键就八个（<code>_t / is_final_answer / observations / step_number / task / timing / token_usage / tool_calls</code>），<code>fmt</code> 仍是 v1。<b>B 重启回灌</b>：同一个库起第二个 <code>OpsUI</code>、回灌之后 <code>task_secs 0.66</code>（V6 的口径在）而 <b><code>task_wait 0.0</code></b>。<b>B 顺手推翻了 v1.6 注释里的一句话</b>：屏上那张历史卡<b>一直带着</b>「（含审批 …）」（卡片正文走 <code>messages</code> 表，实测 4 条消息里 1 条含「含审批」）→ 真读不出的只有状态条 / <code>_stats</code> 那一串数。</li>
  <li><b>C 光进库没有出口</b>：「点一条旧会话」这条路<b>不回灌记忆</b>（<code>agent.memory</code> 还是空的那一份，<code>_bind_memory</code> 只在 <code>_respond</code> 开头），切到甲之后状态条仍是 <code>步数 0/8</code>。所以 V9 必须同时给状态条一个<b>读屏幕上这一条</b>的出口，否则这一格进了库也看不见。<b>D</b> 只把秒数挂回 step 对象的 <code>_opsui_wait</code>，pill、步骤卡标题、正文累计行<b>三处零改动</b>就显示 → 该改的是编解码。</li>
  <li><b>E 升版本的代价</b>：只把 <code>MEM_FMT</code> 改成 v2、不做兼容读 → 真实库里那 <b>7 条 v1 payload 在 strict v2 下全体读空</b>（V6 当场作废）。<b>E1b 反面</b>（v1.6 原样的代码）读 v1.7 写的 v2 账<b>同样读空</b> → 兼容读<b>只朝一个方向</b>，回滚会把新账变成没记忆。</li>
  <li><b>为什么不做成"点旧会话时顺手 <code>_bind_memory</code>"</b>：那条路会把 worker 线程正在读的记忆换掉（<code>_bind_memory</code> 上面"刻意不做"写着的那条理由），V5 的语义也不该由一次点击改动。所以走<b>只读</b>路径：进程里有这一份就读它的 <code>steps</code>，没有就按 V6 那条路 decode 库里那一串。</li>
</ul>

<h4>2 改动清单（<code>my_ui.py</code> 单文件，v1.7 现行号）</h4>
<table>
  <tr><th>文件:行</th><th>改了什么</th><th>类型</th><th>工单号</th></tr>
  <tr><td><code>my_ui.py:63</code> / <code>:68</code></td><td><code>MEM_FMT = "v1" → "v2"</code>；新增 <code>MEM_FMT_READ = ("v1", "v2")</code>。注释点名那条反面证据（真实库那 7 条在 strict v2 下全读空＝基线 E1），并写明 v1 的步没有 wait、读出来按 0 处理、其余字段两版逐字相同</td><td>修改 / 新增</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:85-88</code></td><td><code>MEM_FIELDS</code> 之后加注释：<b>wait 不在这张表里</b>——表的口径是"下一轮模型读到的字段"，审批等待只是界面上的账，<code>to_messages()</code> 不认它，所以在 <code>encode_memory</code> 里单独走一条路</td><td>新增</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:162-168</code></td><td><code>encode_memory</code> 的 <code>ActionStep</code> 分支多写 <code>row["wait"] = round(_opsui_wait, 3)</code>，<b>只有真等过才写</b>（0 不占位）→ 没审批的会话编出来与 v1.6 逐字相同（只差 <code>fmt</code> 那两位），库里体积不涨</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:179-180</code></td><td><code>decode_memory</code> 的版本判定 <code>data.get("fmt") != MEM_FMT</code> → <code>not in MEM_FMT_READ</code>；认不出的版本（v0、将来的 v3）<b>仍旧整块当没记忆，不猜着读</b></td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:203-223</code></td><td><code>ActionStep</code> 的解码分支从"一路 <code>append(构造调用)</code>"改成"先 <code>step = ActionStep(...)</code>，再决定挂不挂属性"</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:225-229</code></td><td><code>if row.get("wait"): step._opsui_wait = float(row["wait"])</code>——v1 的老 payload 没这个键就读作 0、那一格不出现，<b>不是把整条会话判成没记忆</b></td><td>新增</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:894-896</code></td><td>领账那三行注释里的旧口径（"字段白名单不认它，所以<b>不会进记忆库</b>"）改成 v1.7 的事实。<b>第 7 步回写 README 时发现的</b>——不改行为、行数不变（三行换三行）</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:749-752</code> / <code>:782</code></td><td><code>_stats(steps=None)</code> / <code>_status_html(state, steps=None)</code>：不传就是原样读 <code>agent.memory</code>（当前绑定那一份），传了就读那一条会话自己的步骤</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:766-769</code></td><td><code>task_wait</code> 的注释重写（V8 写的是"进程内属性、回灌读 0"）；<b>顺手改掉一处过时的叙述</b>——"屏幕上那条历史卡也就不带审批那一格"，基线 B3 证明它一直在</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:988-1005</code></td><td><b>新增 <code>_session_steps(sid)</code></b>：<code>_mem.get(sid)</code> 有就直接 <code>list(mem.steps)</code>（正在跑的那条账最全），否则 <code>decode_memory(self.hist.load_memory(sid))</code>；<b>只读</b>——不碰 <code>agent.memory</code>、不改绑定。docstring 里记着基线 C3 那条实测（切到甲之后步数仍是 <code>0/8</code>）</td><td>新增</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:1149-1153</code> / <code>:1160</code></td><td><code>_select_session</code> 第二个输出 <code>_status_html("idle")</code> → <code>_status_html("idle", self._session_steps(int(sid)))</code>。注释写明<b>不顺手在这里 <code>_bind_memory</code></b> 的两个理由</td><td>修改</td><td>V9</td></tr>
  <tr><td><code>my_ui.py:1175-1180</code></td><td><code>_on_load</code> 同口径（<code>shown = self._session_steps(sid) if sid else None</code>）。注释点死这条是<b>重启后第一次看</b>的入口：新进程 <code>_mem</code> 是空的 → <b>刷新这一下就是「本题审批」跨重启最干净的验收动作</b></td><td>修改</td><td>V9</td></tr>
  <tr><td><code>ai学习/.rollback/v1.7/</code></td><td>新增第八套存档（<code>my_ui.py</code> + <code>my_coding_agent.py</code>），<code>.rollback/</code> 共 <b>16</b> 份 / <b>8</b> 套</td><td>新增</td><td>回滚</td></tr>
</table>
<p>体量：<code>my_ui.py</code> <b>1,205 → 1,253 行</b>（63,316 → <b>67,362 B</b>；字符 50,717 → 53,019；<code>diff</code> 净 <b>+85 / −37</b>，15 个 hunk。这三个数是<b>第 7 步收尾时重算的</b>：<code>_stream_response</code> 那三行注释按 V9 的事实改过，行数不变、字节 +21，<code>diff</code> 因此比初稿的 <code>+83 / −35</code> 各多 2）。<code>my_coding_agent.py</code> <b>204 行 / 8,355 B 未动</b>（<code>cmp</code> 与 <code>.rollback/v1.6</code> 一致）。库 schema 零改动——<code>memory</code> 表还是那三列，只是 payload 里多一个<b>可选</b>键。</p>

<h4>3 新功能怎么用</h4>
<ul class="tight">
  <li><b>重启之后刷新页面</b>：状态条上「本题审批 X.Xs」自己回来了（v1.6 这时候只剩「本题耗时」，那一格是空的）。</li>
  <li><b>点侧栏任意一条旧会话</b>：状态条报的就是<b>那一条</b>的数。v1.6 这里报的是"上一次提问那条会话"，什么都没提问过时甚至是一份空的 <code>0/8</code>——屏上是甲、条上是乙。</li>
  <li><b>v1 时代（v1.6 及更早）攒下的会话</b>：照读，「本题耗时」「本题 token」「步数」都在，只是<b>没有</b>「本题审批」那一格——那个数当年没进库，本轮不猜、不补。</li>
  <li><b>没审批的题</b>：库里那一串不会多出 <code>wait</code> 这个键（往返重编零增长），界面也一格都不多。</li>
  <li>「本题耗时 / 步骤总时长」的定义<b>仍然一字未动</b>（含等待）；要看纯执行时间还是 <code>总时长 − 审批</code>。</li>
</ul>

<h4>4 上线验收（当场跑过的真实输出）</h4>
<p>离线 <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_test.py</code>（venv python，<code>_stream_response</code> / <code>agent.run</code> 打桩、临时库）：<b>115 条全 PASS、<code>FAILS: 无</code>、<code>exit=0</code></b>（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drill_forward.out</code>）。分节：1 编解码 16 / 2 落库与重启 23 / 3 D7 17 / 4 回归 10 / 5 V7 10 / 6 V8 17 / <b>7 V9 22</b>。v1.6 那 92 条原样搬过来全绿，其中三条按 V9 的新口径改过：<b>2b</b> 期望 <code>fmt</code> 从 v1 改成 v2、<b>6n 直接翻转</b>（v1.6 断言"<code>_opsui_wait</code> 进不了库"，V9 之后它必须进得去，键名是 <code>wait</code> 而不是私有属性名）、新增 <b>2b2</b>（没等过审批的一题 payload 里没有 <code>wait</code>）。第 7 节里最要紧的几条：<b>7a</b> 没等过审批的步 v2 编出来与归档的 v1.6 编码器<b>逐字相同</b>（对照模块用 <code>importlib</code> 把 <code>.rollback/v1.6/my_ui.py</code> 装进来比）、<b>7b</b> 真等过的步才多写，多出来的正好是 <code>, "wait": 12.346</code> 那 16 字节、<b>7c</b> 读回来挂回同一个私有属性（显示层一行没改）、<b>7d</b> 模型读到的那一串不掺这一格、<b>7e/7f</b> 真实库副本里 8 条 payload 全读得回且"新读 v1 == v1.6 读自己那一份"逐字段一样、<b>7g</b> 八条往返重编长度差 <code>[0,0,0,0,0,0,0,0]</code>、<b>7h</b> v1 无 wait 读作 0、<b>7i</b> <code>fmt:"v0"/"v3"</code> 整块拒读、<b>7j~7s</b> 端到端：<b>7l</b> 换一份全新 <code>AgentMemory</code> ＋ 新 <code>OpsUI</code>、只做一次 <code>_on_load</code>（＝"重启后刷新"那一下），「本题审批」自己回来且秒数就是库里那一格、<b>7m/7p</b> 这一路全程只读（<code>agent.memory</code> 仍是新那份空的、<code>_mem == {}</code>、点旧会话也不改绑定）、<b>7n/7o</b> 屏上是甲、条上就报甲：乙那一题不带那一格（别把甲的等待算给乙）、7q 换下一题不继承上一题读回来的等待、7s V7 回声守卫没回潮。</p>
<table>
  <tr><th>判据（在线·探测口 7861，真 qwen-plus，临时库；库里先用 <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_seed.py</code> 种两条<b>真 v1</b> payload——<b>用归档的 <code>.rollback/v1.6</code> 编码器现编</b>，415 / 414 字符（UTF-8 425 / 424 B）、<code>fmt=v1</code>、无 wait，不是手写的假 v1）</th><th>结果</th></tr>
  <tr><td>第一轮之前（v1 兼容读的第一面）</td><td>新进程打开页面即 <code>_on_load</code> 绑最近一条「v1旧记忆-乙」：<code>本题耗时 12.5s</code>、<b><code>本题审批</code> 这格不存在</b>（<code>pillWait=null</code>）——读得动，只是不猜</td></tr>
  <tr><td>挂着审批 20 秒 → 点允许</td><td>等待期间 <code>本题耗时 0.0s</code>、无「本题审批」、pill <code>待批 run_python</code>；点允许之后 <code>本题耗时 23.0s</code> ＋ <b><code>本题审批 20.7s</code></b>、步数 <code>2/8</code>、本题 <code>in 4,789 / out 39</code>、<code>Final answer: 21</code></td></tr>
  <tr><td>落库那一串</td><td>sid 3：<b><code>fmt=v2</code></b>、3 步、<b><code>wait=[20.743, 无]</code></b>（领到账的那条 <code>ActionStep</code> 有、<code>final_answer</code> 那条没有）、<code>duration=[22.08, 0.97]</code>、965 字符（UTF-8 1,013 B）；<code>messages</code> 5 条</td></tr>
  <tr><td><b>真重启</b>（<code>kill</code> → 同一个库重起 → 只做一次页面加载）</td><td>状态条 <b><code>本题耗时 23.0s / 本题审批 20.7s</code></b> ← 新进程的 <code>_mem</code> 是空的、一个 <code>_respond</code> 都没跑过，<b>这个数只能来自库里那一格</b></td></tr>
  <tr><td>重启后点两条 v1 旧会话</td><td>甲 <code>本题耗时 41.0s</code>、乙 <code>12.5s</code>，两边<b>都没有</b>「本题审批」（兼容读不猜）；侧栏高亮跟着点走（<code>chk</code> 从第 1 格挪到点的那一格）→ V7 没回潮</td></tr>
  <tr><td>只读路径没换成绑定</td><td>刷新／点击之后 <code>agent.memory</code> 仍是新进程那一份空的（基线 C2 的语义保持）；屏上是甲、条上也报甲，但下一次提问仍落进它自己那条</td></tr>
</table>
<table>
  <tr><th>判据（在线·<b>交付形态</b> 7860，<code>我的Agent.app</code> 真启动器 ＋ 真 qwen-plus，库＝真实的 <code>smolagents/.agent-history.sqlite3</code>；<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_delivery.py</code> 经 CDP 9333 驱动 headless Chrome）</th><th>结果</th></tr>
  <tr><td>等待单列 ＋ 进库</td><td>状态条 <code>本题耗时 23.4s</code> ＋ <b><code>本题审批 20.7s</code></b>；审批卡 <code>🟢 待批 · run_python · 已允许 · 等了 20.7s</code>；步骤卡 <code>🛠 第 1 步 · run_python · 🟢 成功 · 22.1s · 审批 20.7s · in 2,355/out 22</code> 与 <code>🛠 第 2 步 · final_answer · 🟢 成功 · 1.3s · in 2,438/out 17</code>（<b>没审批的那一步一格都不多</b>）；<code>Final answer: 21</code>；进程 <code>in 4,793 / out 39</code></td></tr>
  <tr><td><b>真实库前后对照</b>（只读；<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_real_before.json</code> 是开工前抓的 sha1+len+fmt）</td><td>跑之前 <code>sessions 7 / messages 49 / memory 7 行</code> → 之后 <b><code>8 / 54 / 8</code></b>；<b>旧 7 行 sha1 逐行不变、零丢失</b>（<code>OLD ROWS CHANGED: 无</code>、<code>OLD ROWS GONE: 无</code>）；新增 sid 8：<code>fmt=v2</code>、<code>wait=[20.672, 无]</code>、967 字符（UTF-8 1,015 B）</td></tr>
  <tr><td><b>真重启（走关闭器）</b></td><td><code>bash ~/Desktop/关闭Agent.command</code> → 重开 → 页面第一次加载即 <code>本题耗时 23.4s / 本题审批 20.7s</code>；四条卡片文字也在（那本来就走 <code>messages</code> 表，<b>不是</b>本轮的新能力）</td></tr>
  <tr><td>重启后点一条真 v1 旧会话</td><td>「用 run_python 打印 4*5 的结果…」→ <code>本题耗时 1.1s</code>、<b>无「本题审批」</b></td></tr>
  <tr><td>四条关停判据（两轮各跑一次）</td><td>7860 监听 <b>0</b> / Agent 专用 Chrome（<code>Application Support/AgentClient</code>）<b>0</b> / <code>who</code> 只剩 <b>console</b> / System Events <code>count of windows of process "Terminal"</code> = <b>0</b></td></tr>
  <tr><td>日志零噪声</td><td>收工时 <code>.agent-ui.log</code> <b>2 行 / 106 B</b>，<code>grep -c</code> 七种模式（<code>Traceback</code> / <code>Error in callback</code> / <code>asyncio.exceptions</code> / <code>RuntimeError:</code> / <code>gradio.exceptions</code> / <code>ClosedClient</code> / <code>Event loop</code>）<b>全 0</b>。⚠️ 启动器用的是 <code>tee</code>（覆盖写），所以这份只留<b>最后一次</b>启动；中途那次 21 行的日志已被重开覆盖<b>【未留痕】</b></td></tr>
  <tr><td><b>回滚演练（双向）</b></td><td>① <code>cp .rollback/v1.6/my_ui.py → smolagents/</code> ＋ <code>cmp</code> <b>逐字节一致</b> → 跑 v1.6 那份离线套件 <b>92 条全 PASS</b>（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drill_backward.out</code>，<code>exit=0</code>；文件里 <code>MEM_FMT</code> 读回 <code>"v1"</code>、1,205 行）② <code>cp .rollback/v1.7/my_ui.py</code> 回去 ＋ <code>cmp</code> 一致 → 再跑 v1.7 套件 <b>115 条全 PASS</b>。两个方向都只是磁盘上换文件、没有任何手工修；真实库没被演练碰过（离线套件全用临时库）；<b>第 7 步改了那三行注释之后这一整套演练原样重跑过一遍</b>（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drill.sh</code> → <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drill_rerun.out</code>）：两个方向仍旧全绿，v1.7 方向另加两条锚点（注释本身改成「跟着记忆进库」这一句、以及 <code>_bind_memory</code> 仍旧没被接到点击路径上），收尾 <code>cmp</code> 现场 == <code>.rollback/v1.7</code></td></tr>
</table>
<p><b>本轮实测出来的两条机制（决定了写法）</b>：① <b>假的 <code>agent.run</code> 必须 <code>yield</code> step 对象</b>——基线第一版让假 run 直接吐 <code>gr.ChatMessage</code> 列表，结果真 <code>_stream_response</code> 那个 <code>isinstance(payload, ActionStep)</code> 分支根本不进，等待永远领不走 → A/B/D 一片红（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_dbg.py</code> 装的哨兵当场定位）。这既是踩坑，也正是"领账挂在 <code>ActionStep</code> 到达那一刻"这条设计的反证式证据。② <b>CDP 每份剧本开头都会 <code>Page.navigate</code>，中途去 peek 一下就是把正在流式的那一题掐断</b>——前两次跑（7861）就是这么丢的，而且<b>留了痕</b>：<code>bot=0</code>、库里一行消息一行记忆都没落、<code>until DONE</code> 跑到 120,353ms / 300,967ms 超时。<b>这是 v1.6 就有的行为，不是 V9 的回归</b> → 立新单 <b>D8</b>（见 §4.1 与第 7 节）。</p>
<p><b>过程问题五条（如实记下）</b>：① <b>7f 第一次跑红</b>，不是代码错而是<b>样本库被这一轮的实跑改了</b>（真实库多了一条真 v2 payload，v1.6 那份代码读它就是 <code>[]</code>）→ 按事实重新基线：7f 只比 v1 那几条，v2 那条单独立 <b>7f2</b>（旧代码读空＝回滚边界）和 <b>7f3</b>（新代码读出 <code>wait</code>）→ 113 条变 <b>115</b> 条。② 基线脚本同理不能在上线后原样重跑，所以留了 <code>v17_base.py</code> ＋ <code>v17_base_v16.py</code> 两份。③ 在线花销按<b>当时屏上的进程档</b>记，三份都有留痕：被掐断那两个进程 <code>in 7,334 / out 63</code>、探测口干净一轮 <code>4,789 / 39</code>、交付形态 <code>4,793 / 39</code>，合计 <b>≈1.7 万 input / 141 output</b>；离线套件与基线<b>零模型调用</b>。④ 本轮在真实库里<b>只追加</b>（新增会话 8），旧 7 行逐字节未动。⑤ <b>第 7 步回写时抓到的一处单位口径错</b>：<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_dump.py</code> 那行印的是 <code>bytes=%d</code>，实际给的是 <code>len(payload)</code>——payload 是 TEXT，这个数是<b>字符</b>，UTF-8 字节数更大（965 字符 / 1,013 B；967 字符 / 1,015 B）。脚本已改成同时印 <code>chars=</code> 与 <code>utf8=B</code>，文档里两处按实测<b>两个数都写</b>；<code>sha1</code> 走的是 <code>encode()</code> 之后的字节，所以那 7 行逐行不变的断言不受影响。</p>

<h4>5 回滚方法</h4>
<p><code>cp .rollback/v1.6/my_ui.py .rollback/v1.6/my_coding_agent.py smolagents/</code>。行为退回两条：① 重启后旧步骤的「本题审批」又读不出来了（那一格随进程一起没）；② 点旧会话／刷新页面时状态条回到"报上一次提问那条、什么都没问时是 <code>0/8</code>"。V6 落库、V7 高亮、V8 单列、D7 停止、D5/V5/D6、v1.3 审批闸<b>都不受影响</b>——退回后的文件上跑 v1.6 那份 92 条就是绿的（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drill_backward.out</code>）。</p>
<p><span class="r"><b>但这一轮的回滚不是无损的，和 v1.6 那条不一样</b></span>：v1.7 写的 payload <code>fmt</code> 是 <code>"v2"</code>，而 v1.6 的 <code>decode_memory</code> 见 <code>fmt != "v1"</code> 就整块读空（基线 <b>E1b</b> 实测：拿真 v2 账喂 v1.6 代码 → 读回 <code>[]</code>）。所以回滚之后 <b>v1.7 期间新建的会话在模型那一边变成"没记忆"</b>（侧栏还在、屏上字还在，追问会答不记得）；v1 时代的老账两边都不受影响。真要长期退回 v1.6，就把 v1.7 建的会话作废（删掉那几条会话），<b>别手工去改 payload 里的 <code>fmt</code></b>——那是改数据不是改代码。</p>

<h4>6 口径与数据变化</h4>
<ul class="tight">
  <li><b>显式声明一处行为语义变化</b>：记忆格式升 <b>v2</b>，<code>ActionStep</code> 多一个<b>可选</b>键 <code>wait</code>（审批等待秒数，<code>round(…, 3)</code>）。真等过才写，0 不占位。</li>
  <li><b>兼容读只朝一个方向</b>：新代码认 <code>("v1","v2")</code>，旧代码只认 <code>"v1"</code> → 旧读新＝没记忆（见第 5 节）。</li>
  <li><b><code>MEM_FIELDS</code> 白名单一字未动</b>（<code>wait</code> 不在里面）：v1.5 定的"存的是下一轮模型读得到的字段"这条纪律保持住了，7d 断言的就是模型读到的那串逐字不变。所以 <code>wait</code> 是<b>界面上的账随记忆一起存</b>，不是模型上下文的一部分——它和 <code>timing</code>、<code>token_usage</code> 同一类。</li>
  <li><b>体积</b>：每格 12~17 个字符（<code>, "wait": 20.743</code> 这一串是纯 ASCII，<b>字符数＝字节数</b>），只有领到账的那个 <code>ActionStep</code> 才有；真实库 8 条 payload「读进来再编回去」长度差全 0（7g）。基线 E3 数的量级：库里 17 条 <code>ActionStep</code> 全等一遍也就多 ≈200 B。</li>
  <li><b>状态条口径变了（本轮唯一的界面行为变化）</b>：那串「本题」的数现在报的是<b>屏幕上这一条会话</b>，不再报"上一次提问的那条"。同一个数在不同会话之间来回切会跟着变——以前不会。<code>_stats()</code> 不传参时行为与 v1.6 逐字相同（7r 断言），改的只有两个调用点。</li>
  <li><b>「本题耗时 / 步骤总时长」定义仍一字未动</b>（含等待）。</li>
  <li><b>修掉一处过时的注释口径</b>：v1.6 在 <code>_stats</code> 上写"屏幕上那条历史卡也就不带审批那一格"——<b>实测是错的</b>，卡片正文走 <code>messages</code> 表，重启后那句「（含审批 21.0s）」一直都在；真缺口只在 <code>_stats</code>/状态条（基线 B3）。</li>
  <li><b>token 口径未动</b>。同题同步长对照：第 1 步 <code>in 2,355/out 22</code> ＋ 第 2 步 <code>in 2,438/out 17</code> ＝ 本题 <code>4,793/39</code>；裸起步实测 <code>2,349</code>（v1.6 是 <code>2,344 / 2,349</code>，同级；差异仍是模型侧波动）。<b>进程档每次重启归零</b>这条定义没变。</li>
  <li><b>体量</b>：<code>my_ui.py</code> 1,205 → 1,253 行、63,316 → <b>67,362 B</b>、净 <b>+85 / −37</b>；<code>.rollback/</code> 存档 <b>14 → 16 份</b>（7 → 8 套）；看板 <b>36 → 37 条</b>（V9 转已上线，新立 <b>D8</b>）。</li>
</ul>

<h4>7 已知遗留</h4>
<ul class="tight">
  <li><b>新立 D8（本轮实跑暴露，两条路都有留痕，见 §4.1）</b>：正在流式（尤其挂在审批闸上等人点）的时候刷新页面或关页面，这一题<b>一行都不落库</b>——<code>_respond</code> 开头已经 <code>ensure</code> 建了会话行，屏上曾经有字，但消息与记忆都没写，那笔审批等待也一起蒸发。机制<b>【未验证】</b>：断开时 <code>finally</code> 的语义、阻塞中的闸怎么随断开结算（现在只能等 <code>APPROVAL_TIMEOUT=600s</code> 自己按拒绝结算）、以及"落半截"和"标已中断"选哪个。v1.5 那句"半截可接受"的前提是半截会落库，实测连半截都没有。</li>
  <li><b>v1 时代的老账永远没有「本题审批」</b>：那个数从来没进库，本轮不猜、不补。<b>库里 v1 的行不会被回写升级</b>（旧 7 行 sha1 逐行不变就是这条的断言）→ 好处是回滚面小，代价是同一个库里两种格式长期并存，<code>MEM_FMT_READ</code> 得一直带着。</li>
  <li><b>并行多工具时那一格等待挂在"第一个到达的 <code>ActionStep</code>"上</b>（v1.6 就写着这条），本轮所有题仍是单工具【未验证：多工具并行怎么分这两格】。</li>
  <li><b>只读路径不改绑定</b>：点旧会话现在屏上／条上一致了，但 <code>agent.memory</code> 仍停在上一条提问的会话——这是 V5 的语义，本轮有意不动。<b>代价</b>：点甲看了两眼再提问，问题落进的是"新起的那条"而不是甲【未验证：多标签同开时 <code>_sid_shown</code> 的守卫】。真要让点击就换绑定，得先解决 <code>_bind_memory</code> 上面写的那条 worker 竞争。</li>
  <li><b>验收脚本仍在 <code>/tmp</code></b>：本轮新增 <code>v17_base.py</code> / <code>v17_base_v16.py</code> / <code>v17_dbg.py</code> / <code>v17_seed.py</code> / <code>v17_ui.py</code> / <code>v17_live.py</code> / <code>v17_dump.py</code> / <code>v17_delivery.py</code> / <code>v17_real_after.py</code> / <code>v17_test.py</code> / <code>v17_drill.sh</code> ＋ 第 7 步文档闸那批（<code>v17_map16.json</code>、<code>v17_readme_align.py</code>、<code>v17_readme_apply.py</code>、<code>v17_manual_align.py</code>、<code>v17_manual_sec4.py</code>、<code>v17_manual_sec6.py</code>、<code>README.before-v17</code>、<code>v17_readme.diff</code>）＋ 输出 <code>v17_base_v16.out</code> / <code>v17_pre.out</code> / <code>v17_post.out</code> / <code>v17_peek.out</code> / <code>v17_finish.out</code> / <code>v17_drain.out</code> / <code>v17_delivery_ask.out</code> / <code>v17_delivery_post.out</code> / <code>v17_real_before.json</code> / <code>v17_drill_backward.out</code> / <code>v17_drill_forward.out</code> / <code>v17_drill_rerun.out</code>——macOS 一重启就没了，只剩记录里的数字。<b>要不要开 <code>ai学习/验收脚本/</code>（按版本号分目录）收进来，仍然等你点头</b>。</li>
  <li>仍欠点头：dify Docker Compose（#5）、MCP servers <code>npm ci</code>（#6）、<b>百炼 Key 轮换</b>、<code>gradio_ui.py:456</code> 的 <code>.capitalize()</code>、D2、P0-4。</li>
</ul>
<p><b>推荐下一刀 v1.8 = D8 先、P0-4 后</b>：D8 是本轮实跑抓出来的数据完整性问题（一屏字能整轮丢），基线已经写好；P0-4（计划可见）是新功能，地基（v1.3 的线程 ＋ 允许/拒绝键）本来就铺好了，往后排一格不亏。</p>

'''

anchor = u'<h3>6.2 v1.6 · 2026-10-30 · 侧栏高亮跟着绑定走'
assert t.count(anchor) == 1
t = t.replace(anchor, NEW + anchor)
io.open(P, "w", encoding="utf-8").write(t)
print("inserted, lines=%d" % len(t.split("\n")))
