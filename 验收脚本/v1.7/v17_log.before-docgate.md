# 我的Agent 迭代记录（事实源）

- 对象：`~/Desktop/我的Agent.app` + `~/Desktop/study/ai学习/smolagents`
- 本文件是**事实源**。`agent功能手册.html` 是它的视图，冲突时以本文件为准并立刻重生成 HTML。
- 一条迭代一节，**倒序追加**（新的在上）。
- 版本号：主版本＝交付形态变了；次版本＝新增能力；修订号＝缺陷修复与调参。
- 纪律四条：不许有无数字的形容词；token 口径必须写死（累计 vs 单步）；没验证的标【未验证】；行为语义变了要显式声明。

字段模板见文末「附录 A 空白模板」。

---

## v1.7 · 2026-10-30 · 「本题审批」跟着记忆进库：重启、点旧会话都读得出那一格（V9）

### 1 这次解决什么（为什么现在做）

范围按工单号锁定 **V9**——就是 v1.6 §7 第 1 条自己立下的那单（「本题审批」跨重启读不出来，要让它进库得给记忆格式加字段：`MEM_FMT` 升 v2 ＋ 兼容读旧 payload）。`my_coding_agent.py`、`my_agent.py`、上游源码零改动；库 schema 零改动；审批闸的**判定**、停止的语义、V7 的高亮、V8 的记账链路一行未碰——本轮只在这条链的**末端**多写一格、多读一格。

基线先跑（`/tmp/v17_base_v16.py` → `/tmp/v17_base_v16.out`，**被测模块换成归档的 `.rollback/v1.6/my_ui.py`**：上线之后真实库里已经多了一条真 v2 payload，拿现网代码原样重跑会把"缺口复现"跑成"缺口已关"，数字就不配当基线。13 条全 PASS）：

- **A 缺口本体**：活进程里那一格看得见（`task_wait 0.61s`、pill 在），但落库那串里**根本没有 wait 这个键**——payload 出现过的键就八个（`_t / is_final_answer / observations / step_number / task / timing / token_usage / tool_calls`），`fmt` 仍是 v1。
- **B 重启回灌**：同一个库起第二个 `OpsUI`、`_bind_memory` 回灌之后 `task_secs 0.66`（V6 的口径在）、**`task_wait 0.0`** → 缺口坐实在"只有等待读不出"。同一段还顺手推翻了 v1.6 注释里的一句话：屏上那张历史卡**一直带着**「（含审批 …）」（卡片正文走 `messages` 表，实测 4 条消息里 1 条含"含审批"）——真正读不出的只有状态条/`_stats` 那一串数。
- **D 改动点不在显示层**：只把秒数挂回 step 对象的 `_opsui_wait`，pill、步骤卡标题、正文累计行**三处零改动**就显示（D1/D2 绿）→ 该改的是编解码。
- **C 光进库没有出口**：「点一条旧会话」这条路**不回灌记忆**（`agent.memory` 还是空的那一份，`_bind_memory` 只在 `_respond` 开头），切到甲之后状态条仍是 `步数 0/8`。所以 V9 必须同时给状态条一个**读屏幕上这一条**的出口，否则这一格进了库也看不见。
- **E 升版本的代价**：只把 `MEM_FMT` 改成 v2、不做兼容读 → 真实库里那 **7 条 v1 payload 在 strict v2 下全体读空**（V6 当场作废）。**E1b 反面**（v1.6 原样的代码、不动 `MEM_FMT`）：它读 v1.7 写的 v2 账同样读空 → 兼容读**只朝一个方向**，回滚会把新账变成没记忆（这条进了 §5，是本轮唯一"回滚有代价"的地方）。

**为什么不做成"点旧会话时顺手 `_bind_memory`"**：那条路会把 worker 线程正在读的记忆换掉（`_bind_memory` 上面第二条"刻意不做"写着的理由），V5 的语义也不该由一次点击改动。所以状态条走**只读**路径：进程里有这一份就读它的 steps，没有就按 V6 那条路 decode 库里那一串。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:63` / `:68` | `MEM_FMT = "v1" → "v2"`；新增 `MEM_FMT_READ = ("v1", "v2")`。注释点名那条反面证据（真实库那 7 条 payload 在 strict v2 下全读空＝基线 E1），并写明 v1 的步没有 wait、读出来按 0 处理、其余字段两版逐字相同 | 修改 / 新增 | V9 |
| `my_ui.py:85-88` | `MEM_FIELDS` 之后加注释：**wait 不在这张表里**——表的口径是"下一轮模型读到的字段"，审批等待只是界面上的账，`to_messages()` 不认它；所以它在 `encode_memory` 里单独走一条路，读回来挂回私有属性 | 新增 | V9 |
| `my_ui.py:162-168` | `encode_memory`：ActionStep 分支多写 `row["wait"] = round(_opsui_wait, 3)`，**只有真等过才写**（0 不占位）→ 没审批的会话编出来和 v1.6 逐字相同（只差 `fmt` 那两位），库里体积不涨 | 修改 | V9 |
| `my_ui.py:179-180` | `decode_memory` 的版本判定 `data.get("fmt") != MEM_FMT` → `not in MEM_FMT_READ`；认不出的版本（v0、将来的 v3）**仍旧整块当没记忆，不猜着读** | 修改 | V9 |
| `my_ui.py:203-223` | ActionStep 的解码分支从"一路 `append(构造调用)`"改成"先 `step = ActionStep(...)`，再决定挂不挂属性" | 修改 | V9 |
| `my_ui.py:225-229` | `if row.get("wait"): step._opsui_wait = float(row["wait"])`——v1 的老 payload 没这个键就读作 0、那一格不出现，**不是把整条会话判成没记忆** | 新增 | V9 |
| `my_ui.py:894-896` | 领账那三行注释里的旧口径（"字段白名单不认它，所以**不会进记忆库**"）改成 v1.7 的事实：白名单仍然不认它，但 `encode_memory` 单独认这一格，所以它跟着记忆进库、重启后读得出。**第 7 步回写 README 时发现的**——不改行为、行数不变（三行换三行） | 修改 | V9 |
| `my_ui.py:749-752` / `:782` | `_stats(steps=None)` / `_status_html(state, steps=None)`：不传就是原样读 `agent.memory`（当前绑定那一份），传了就读那一条会话自己的步骤 | 修改 | V9 |
| `my_ui.py:766-769` | `task_wait` 那几行注释重写：V8 写的是"进程内属性、回灌读 0"，现在这一格跟着记忆进库、回灌挂回同一个属性所以读得出；**顺手改掉一处过时的叙述**（"屏幕上那条历史卡也就不带审批那一格"——基线 B3 证明它一直在） | 修改 | V9 |
| `my_ui.py:988-1004` | **新增 `_session_steps(sid)`**：`_mem.get(sid)` 有就直接 `list(mem.steps)`（正在跑的那条账最全），否则 `decode_memory(self.hist.load_memory(sid))`；**只读**——不碰 `agent.memory`、不改绑定。docstring 里记着基线 C3 那条实测（切到甲之后步数仍是 `0/8`） | 新增 | V9 |
| `my_ui.py:1150-1153` / `:1160` | `_select_session` 第二个输出 `_status_html("idle")` → `_status_html("idle", self._session_steps(int(sid)))`。注释写明**不顺手在这里 `_bind_memory`** 的两个理由（worker 线程正在读、V5 语义不该由一次点击改动） | 修改 | V9 |
| `my_ui.py:1175-1180` | `_on_load` 同口径（`shown = self._session_steps(sid) if sid else None`）。注释点死这条是**重启后第一次看**的入口：新进程 `_mem` 是空的，`_session_steps` 只能走库里那一串 → 所以**刷新这一下就是「本题审批」跨重启最干净的验收动作** | 修改 | V9 |
| `ai学习/.rollback/v1.7/` | 新增第八套存档（`my_ui.py` + `my_coding_agent.py`），`.rollback/` 共 **16** 份 / **8** 套 | 新增 | 回滚 |

体量：`my_ui.py` **1,205 → 1,253 行**（**63,316 → 67,362 B**；字符 50,717 → 53,019；`diff` 净 **`+85 / −37`**，15 个 hunk。这三个数是**第 7 步收尾时重算的**：`_stream_response` 里那三行注释按 V9 的事实改过，行数不变、字节 +21，`diff` 因此比初稿的 `+83 / −35` 各多 2）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.6` 一致）。库 schema 零改动——`memory` 表还是那三列，只是 payload 里多一个**可选**键。

### 3 新功能怎么用（用户视角）

1. **重启之后刷新页面**：状态条上「本题审批 X.Xs」自己回来了（v1.6 这时候只剩「本题耗时」，那一格是空的）。
2. **点侧栏任意一条旧会话**：状态条报的就是**那一条**的数。v1.6 这里报的是"上一次提问那条会话"，什么都没提问过时甚至是一份空的 `0/8`——屏上是甲、条上是乙。
3. **v1 时代（v1.6 及更早）攒下的会话**：照读，「本题耗时」「本题 token」「步数」都在，只是**没有**「本题审批」那一格——那个数当年没进库，本轮不猜、不补。
4. **没审批的题**：库里那一串不会多出 `wait` 这个键（往返重编零增长），界面也一格都不多。
5. 「本题耗时 / 步骤总时长」的定义**仍然一字未动**（含等待）；要看纯执行时间还是 `总时长 − 审批`。

### 4 上线验收（当场跑过的真实输出）

离线：`/tmp/v17_test.py`（venv python，`_stream_response` / `agent.run` 打桩、临时库）——**115 条断言全 PASS、`FAILS: 无`、`exit=0`**（`/tmp/v17_drill_forward.out`）。分节：1 编解码 16 / 2 落库与重启 23 / 3 D7 17 / 4 回归 10 / 5 V7 10 / 6 V8 17 / **7 V9 22**。v1.6 那 92 条原样搬过来全绿，其中三条按 V9 的新口径改过：**2b** 期望 `fmt` 从 v1 改成 v2、**6n 直接翻转**（v1.6 断言"`_opsui_wait` 进不了库"，V9 之后它必须进得去，键名是 `wait` 而不是私有属性名）、新增 **2b2**（没等过审批的一题 payload 里没有 `wait`）。第 7 节 22 条里最要紧的几条：**7a** 没等过审批的步 v2 编出来与归档的 v1.6 编码器**逐字相同**（对照模块用 `importlib` 把 `.rollback/v1.6/my_ui.py` 装进来比）、**7b** 真等过的步才多写，多出来的正好是 `, "wait": 12.346` 那 16 字节、**7c** 读回来挂回同一个私有属性（显示层一行没改）、**7d** 模型读到的那一串不掺这一格、**7e/7f** 真实库副本里 8 条 payload 全读得回且"新读 v1 == v1.6 读自己那一份"逐字段一样、**7g** 八条往返重编长度差 `[0,0,0,0,0,0,0,0]`、**7h** v1 无 wait 读作 0、**7i** `fmt:"v0"/"v3"` 整块拒读、**7j~7s** 端到端：真 `_stream_response` ＋ 真闸挂 0.7s → **7j** 活进程里 pill 在 → **7k** 落库 `fmt=v2` 且 `wait` 与进程内那个数一致 → **7l** 换一份全新 `AgentMemory` ＋ 新 `OpsUI`、只做一次 `_on_load`（就是"重启后刷新"那一下），「本题审批」自己回来且秒数就是库里那一格 → **7m/7p** 这一路全程只读（`agent.memory` 仍是新那份空的、`_mem == {}`、`_mem_sid` 没动，点旧会话也不改绑定）→ **7n/7o** 屏上是甲、条上就报甲：乙那一题不带那一格（别把甲的等待算给乙），点回甲「本题审批」又跟着回来 → 换下一题不继承上一题读回来的等待（7q）→ V7 回声守卫没回潮（7s）。

在线·探测口（7861，真 qwen-plus，临时库 `/tmp/v17-live-hist.sqlite3`；库里先用 `/tmp/v17_seed.py` 种两条**真 v1** payload——**用归档的 `.rollback/v1.6` 编码器现编**，415 / 414 字符（UTF-8 425 / 424 B）、`fmt=v1`、无 wait，不是手写的假 v1）：证据 `/tmp/v17_pre.out`、`/tmp/v17_post.out`、`/tmp/v17_dump.py`

| 判据 | 结果 |
|---|---|
| 第一轮之前（v1 兼容读的第一面）| 新进程打开页面即 `_on_load` 绑最近一条「v1旧记忆-乙」：`本题耗时 12.5s`、**`本题审批` 这格不存在**（`pillWait=null`）——读得动，只是不猜 |
| 挂着审批 20 秒 | 2.0s 进「等待审批」；等待期间 `本题耗时 0.0s`、无「本题审批」、pill `待批 run_python` |
| 点允许之后 | `本题耗时 23.0s` ＋ **`本题审批 20.7s`**、步数 `2/8`、本题 `in 4,789 / out 39`、`Final answer: 21` |
| 落库那一串 | sid 3：**`fmt=v2`**、3 步、**`wait=[20.743, 无]`**（领到账的那条 ActionStep 有、`final_answer` 那条没有）、`duration=[22.08, 0.97]`、965 字符（UTF-8 1,013 B）；`messages` 5 条 |
| **真重启**（`kill` → 同一个库重起 → 只做一次页面加载）| 状态条 **`本题耗时 23.0s / 本题审批 20.7s`** ← 新进程的 `_mem` 是空的、一个 `_respond` 都没跑过，这个数只能来自库里那一格 |
| 重启后点两条 v1 旧会话 | 甲 `本题耗时 41.0s`、乙 `12.5s`，两边**都没有**「本题审批」（兼容读不猜）；侧栏高亮跟着点走（`chk` 从第 1 格挪到点的那一格）→ V7 没回潮 |
| 只读路径没换成绑定 | 刷新／点击之后 `agent.memory` 仍是新进程那一份空的（基线 C2 的语义保持）；屏上是甲、条上也报甲，但下一次提问仍落进它自己那条 |

在线·**交付形态**（7860，`我的Agent.app` 真启动器 ＋ 真 qwen-plus，库＝真实的 `smolagents/.agent-history.sqlite3`；`/tmp/v17_delivery.py` 经 CDP 9333 驱动 headless Chrome）：证据 `/tmp/v17_delivery_ask.out`、`/tmp/v17_delivery_post.out`、`/tmp/v17_real_after.py`

| 判据 | 结果 |
|---|---|
| 等待单列 ＋ 进库 | 状态条 `本题耗时 23.4s` ＋ **`本题审批 20.7s`**；卡片 `🟢 待批 · run_python · 已允许 · 等了 20.7s`、`🛠 第 1 步 · run_python · 🟢 成功 · 22.1s · 审批 20.7s · in 2,355/out 22`、`🛠 第 2 步 · final_answer · 🟢 成功 · 1.3s · in 2,438/out 17`（**没审批的那一步一格都不多**）、`Final answer: 21`；进程 `in 4,793 / out 39` |
| **真实库前后对照**（只读；`/tmp/v17_real_before.json` 是本轮开工前抓的 sha1+len+fmt）| 跑之前 `sessions 7 / messages 49 / memory 7 行` → 之后 **`8 / 54 / 8`**；**旧 7 行 sha1 逐行不变、零丢失**（`OLD ROWS CHANGED: 无`、`OLD ROWS GONE: 无`）；新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、967 字符（UTF-8 1,015 B） |
| **真重启（走关闭器）** | `bash ~/Desktop/关闭Agent.command` → 重开 → 页面第一次加载即 `本题耗时 23.4s / 本题审批 20.7s`；四条卡片文字也在（那本来就走 `messages` 表，不是本轮的新能力） |
| 重启后点一条真 v1 旧会话 | 「用 run_python 打印 4*5 的结果…」→ `本题耗时 1.1s`、**无「本题审批」** |
| 四条关停判据（两轮各跑一次）| 7860 监听 **0** / Agent 专用 Chrome（`Application Support/AgentClient`）**0** / `who` 只剩 **console** / System Events `count of windows of process "Terminal"` = **0** |
| 日志零噪声 | 收工时 `.agent-ui.log` **2 行 / 106 B**，`grep -c` 七种模式（`Traceback` / `Error in callback` / `asyncio.exceptions` / `RuntimeError:` / `gradio.exceptions` / `ClosedClient` / `Event loop`）**全 0**。⚠️ 启动器用的是 `tee`（覆盖写），所以这份只留**最后一次**启动；中途那次 21 行的日志已被重开覆盖【未留痕】 |
| **回滚演练（双向）** | ① `cp .rollback/v1.6/my_ui.py → smolagents/`
| **文档闸·README 行号重新对齐**（第 7 步的前半）<br/>`/tmp/v17_map16.json`（difflib v1.6→v1.7 行映射，1,205 个键）＋ `/tmp/v17_readme_align.py`（提议器）＋ `/tmp/v17_readme_apply.py`（落盘器，`OVERRIDE` / `FORCE` / `SKIP` ＋ `--write`）＋ 写入前整份备份 `/tmp/v17_README.before.md`（1,350 行 / 124,886 B）＋ `/tmp/v17_readme.diff` | 提议器逐条判这个号是 v1.6 时代还是更早的号（判据：这句话的标识符/实体与那一版源码块、与 v1.7 目标块的重叠取高者），再按行映射搬到 v1.7，跨度做 def/class 扩展并修剪空行；落盘器按列位置从右往左替换。**四个"讲现状"范围（§6.3 / §8 / §9.1 / §9.4）里 233 条候选引用 → 替换 194 处**，对齐前后**总行数不变 1,350**。判据分布：HIT 181 / other-file 21（讲的是上游那几个文件）/ same-HIT 12 / ZERO 9 / FORCE 5 / SKIP 3 / hist 2。**事后两道扫**（`/tmp/v17_scan.py`，README 讲现状的范围 368 个行号）：越界（`:NNN > 1,253`）**0 条**；指向空行 **1 条**——`:31-36`，是刻意保留的 v1.1 历史号 |
| **文档闸·README 现状 ＋ 手册自身**（第 7 步的后半） | **README**：新增 **§6.3.9**（V9 全节：两条读空、机制图、编解码两侧的改动、验证与回滚边界），§6.3 标题与文首口径改到 **1,253 行**，§8 用**三条 V9 场景**（重启后刷新那一格回来 / 点旧会话状态条跟着屏幕上这一条走且全程只读 / 回滚把 v1.7 的账读成没记忆）替换掉 v1.6 立的「已知边界 → V9」那条，§9.1 补 **49、50** 两行，§9.3 补 **10、11** 两条命令，§9.4 第 12 条改「**八轮**」→ **1,350 → 1,445 行**（124,886 → **144,128 B**，`diff` 67 个 hunk、**+214 / −119**）。**Mermaid：块 24 → 25，`块数 25 / 产出 svg 25 / 语法错误 0`；负控 `块数 2 / 产出 svg 2 / 语法错误 1` 且 `exit=1`**（`/tmp/v17_mmd_readme.out`、`/tmp/v17_mmd_neg.out`）——排除"校验器假通过"。<br/>**手册**（`agent功能手册.html`）：**这一轮第一次给它做机器对齐**（v1.6 只对过 README）——`/tmp/v17_manual_align.py` 提议 ＋ 落盘，**112 条候选引用里替换 85 处**（HIT 62 / FORCE 21 / other-file 12 / SKIP 6 / hist 4 / same-HIT 3 / ZERO 2 / same-ZERO 2），对齐这一步**总行数不变 1,182**；再改 §2 标题与页眉版本 → v1.7、§2.1 三行（`my_ui.py` 1,253 / 库 8-54-8 / `.rollback` 16 份 8 套）、§2.5 新增 V9 行并把状态条那行的旧口径换掉、§4 看板 **36 → 37 行**（V9 转已上线、新立 D8、推荐下一刀改 v1.8）、§6 记录节整体 6.1–6.7 → 6.2–6.8 ＋ 4 处手册内部 `§6.x` 交叉引用跟着挪（README 与 `迭代记录.md` 的 `§6.x` 引用**不跟着挪**，那是另一个文件的编号）、新增 **§6.1 v1.7 全节 92 行** ＋ 本表这三行文档闸 **3 行** → **1,182 → 1,285 行**。**静态闸**：未闭合 `[]`、配对错误 0、外部资源 0、死锚点 `[]`、看板 37 行、`data-st {todo 16, doing 0, done 18, na 3}`、`data-p {D 8, P0 5, P1 8, P2 7, V 9}`。**浏览器闸**（headless Chrome 9333，`/tmp/v17_manual_check_1440.js` / `_1180.js`）：`title` 已是 v1.7、`rows 37`、`tables 32`，十个筛选器 `#cnt` 与可见行数**逐条相符**（`all 37 / bug 8 / p0 5 / p1 8 / p2 7 / v 9 / todo 16 / doing 0 / done 18 / na 3`），`overflowX=false` 在 **1425** 与 **1165** 两档视口都成立，截图 `/tmp/v17-manual.png` **229,146 B**、`/tmp/v17-manual-1180.png` **218,828 B**；输出 `/tmp/v17_manual_gate_1440.out` / `_1180.out`。**手册的事后两道扫**：讲现状的范围（§1–§5、**§6.1 自己这一节**、§7）**260** 个行号，越界 **0** 条，指向空行 **8** 条——逐条定性：3 条讲历史或别的文件（`:171` 讲的是 `my_coding_agent.py`，160 字符归属窗口把它错当成 my_ui，假阳性；`:53-172`、`my_ui.py:450-500` 都带版本号，是历史叙述，刻意保留），另外 5 条**就是这三行里被引用、被纠正的那几个号**（写出来是为了记下它错在哪，不是引用错了位置） |
| **文档闸自己被抓到并当场修掉的三处**（第 7 步的产物，不是上线前的改动） | ① **页眉漏改**：`<title>` 与 `.meta` 那行还写着 **v1.6**、上线的还是「V7 + V8」——浏览器闸把 `title` 打出来才看见。改成 v1.7 / V9。② **D8 那一行把整页顶成横向滚动**：`overflowX=true`，`scrollW` 在 1,440 档 **1,552**、1,180 档 **1,422**，§4.1 缺陷表的 min-content 从 **1,038 涨到 1,358**（容器 `.wrap` 1,080，右边只有 22px 垫冲抵）。根因**不是长单词**（`overflow-wrap:anywhere`、把 `、` 换成空格都毫无效果，`/tmp/v17_wide4.js`），而是 **CJK 行首禁则**：`（` 之后与 `、` 之前都不许断行，于是「（`/tmp/v17_drain.out`、`/tmp/v17_finish.out`、`/tmp/v17_peek.out`）」被粘成**一个原子块**——`/tmp/v17_bisect.js` 逐节点剔除定位，删掉任意一份文件名就回落 150~166px；再叠加状态胶囊 `white-space:nowrap` 的「未开工（v1.7 新立）」比别的行多占 **46px**（`/tmp/v17_wide9.js` 量到那颗 149px）。修法：冒号引出＋空格分隔三份留痕、把「v1.7 新立」挪出胶囊 → min-content 实测回到 **1,038**（与 D8 之前的那一行逐字相同，`/tmp/v17_fixtry2.js`），两档 `overflowX` 都回到 false。**留痕一个文件名都没删**。③ **两处行号 off-by-one**（都由「指向空行」那道扫抓到，不是人眼看出来的）：**a)** `_select_session` 的 V9 注释块写作 `:1149-1153`，而 **1,149 是空行**、注释实际从 **1,150** 起 → `:1150-1153`；**b)** `_session_steps` 两种写法都有（`:988-1005` 与 `:988-1006`），而 **1,005 是空行**、1,006 已是下一节 `# ---- 事件` 的注释 → 函数体实为 `:988-1004`。**手册 7 处 ＋ 本文件 2 处**统一改成这两个号；README 里没有这两个号（它引的是 `:1155-1156` / `:1160` / `:988-1004`），扫过确认。**这条也说明 §2 表里那一行在上线当时就是错的**，不是回写时才写错的 | ＋ `cmp` **逐字节一致** → 跑 **v1.6 那份离线套件 92 条全 PASS**（`/tmp/v17_drill_backward.out`，`exit=0`；文件里 `MEM_FMT` 读回 `"v1"`、1,205 行）② `cp .rollback/v1.7/my_ui.py` 回去 ＋ `cmp` 一致 → 再跑 **v1.7 套件 115 条全 PASS**（`/tmp/v17_drill_forward.out`）。两个方向都只是磁盘上换文件、没有任何手工修；`.agent-history.sqlite3` 没被演练碰过（离线套件全用临时库）；**第 7 步改了那三行注释之后这一整套演练原样重跑过一遍**（`/tmp/v17_drill.sh` → `/tmp/v17_drill_rerun.out`）：v1.6 方向 92 条、v1.7 方向 115 条仍旧全 PASS，v1.7 方向另加两条锚点（注释本身改成「跟着记忆进库」这一句、以及 `_bind_memory` 仍旧没被接到点击路径上），收尾 `cmp` 现场 == `.rollback/v1.7` |

**本轮实测出来的两条机制（决定了写法）**：
1. **假的 `agent.run` 必须 `yield` step 对象**。基线第一版让假 run 直接吐 `gr.ChatMessage` 列表，结果真 `_stream_response` 那个 `isinstance(payload, ActionStep)` 分支根本不进，等待永远领不走 → A/B/D 一片红（`/tmp/v17_dbg.py` 装的哨兵当场定位）。这既是踩坑，也正是"领账挂在 ActionStep 到达那一刻"这条设计的反证式证据。
2. **CDP 每份剧本开头都会 `Page.navigate`，中途去 peek 一下就是把正在流式的那一题掐断**。前两次跑（7861）就是这么丢的，而且**留了痕**（`/tmp/v17_drain.out`、`/tmp/v17_finish.out`、`/tmp/v17_peek.out`）：进程内状态条仍报 `步数 3/8 本题 in 7,334/out 63 本题耗时 25.1s 本题审批 22.1s`（另一条 `步数 1/8 in 2,355/out 21 27.2s / 26.0s`），屏上却是 **`bot=0`**（一个气泡都没有）、库里那条会话**一行消息一行记忆都没落**（只有 `ensure` 建的会话行）；`待批 run_python` 的 pill 挂在状态已经「空闲」的条上，`#approve-btn`  reload 后 `NO-ELEMENT`，两次 `until DONE` 分别跑到 **120,353ms** 与 **300,967ms** 超时。改成一整轮只跑一份剧本之后，两轮（探测口＋交付形态）都干净跑通。**这是 v1.6 就有的行为，不是 V9 的回归** → 立新单 **D8**（§7 第 1 条）。

**要如实记下的过程问题**：① **7f 第一次跑红**，不是代码错而是**样本库被这一轮的实跑改了**：真实库多了一条真 v2 payload，v1.6 那份代码读它就是 `[]`，于是"新读 v1 == v1.6 读自己那一份"这条断言的前提（语料全是 v1）不再成立。按事实重新基线：7f 只比 v1 那几条，v2 那条单独立 **7f2**（旧代码读空＝回滚边界）和 **7f3**（新代码读出 `wait`）→ 113 条变 115 条。② 基线脚本同理不能在上线后原样重跑（见 §1 的说明），所以留了 `v17_base.py`（改动前那份）＋ `v17_base_v16.py`（换成归档代码的复跑）两份。③ 在线花销按**当时屏上的进程档**记，三份都有留痕：被掐断那两个进程累计 `in 7,334 / out 63`、探测口干净一轮 `in 4,789 / out 39`、交付形态 `in 4,793 / out 39`，合计 **≈1.7 万 input / 141 output**；离线套件与基线**零模型调用**（假 run ＋ 真闸）。④ 本轮在真实库里**只追加**（新增会话 8），旧 7 行逐字节未动。⑤ **第 7 步回写时抓到的一处单位口径错**：`/tmp/v17_dump.py` 那行印的是 `bytes=%d`，实际给的是 `len(payload)`——payload 是 TEXT，这个数是**字符**，而 UTF-8 字节数更大（探测口那条 v2 会话：965 字符 / 1,013 B；交付形态那条：967 字符 / 1,015 B）。脚本已改成同时印 `chars=` 与 `utf8=B`，上面两处 B 的字样按实测**改成两个数都写**；`sha1` 走的是 `encode()` 之后的字节，所以那 7 行逐字节不变的断言不受影响。

### 5 回滚方法

```bash
cp ~/Desktop/study/ai学习/.rollback/v1.6/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.6/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

行为退回两条：① 重启后旧步骤的「本题审批」又读不出来了（那一格随进程一起没）；② 点旧会话／刷新页面时状态条回到"报上一次提问那条、什么都没问时是 `0/8`"。V6 落库、V7 高亮、V8 单列、D7 停止、D5/V5/D6、v1.3 审批闸都不受影响——退回后的文件上跑 v1.6 那份 92 条就是绿的（`/tmp/v17_drill_backward.out`）。

**但这一轮的回滚不是无损的，和 v1.6 那条不一样**：v1.7 写的 payload `fmt` 是 `"v2"`，而 v1.6 的 `decode_memory` 见 `fmt != "v1"` 就整块读空（基线 **E1b** 实测：拿真 v2 账喂 v1.6 代码 → 读回 `[]`）。所以回滚之后**v1.7 期间新建的会话在模型那一边变成"没记忆"**（侧栏还在、屏上字还在，追问会答不记得）；v1 时代的老账两边都不受影响。真要长期退回 v1.6，就把 v1.7 建的会话作废（删掉那几条会话），别手工去改 payload 里的 `fmt`——那是改数据不是改代码。

### 6 口径与数据变化

1. **显式声明一处行为语义变化**：记忆格式升 **v2**，`ActionStep` 多一个**可选**键 `wait`（审批等待秒数，`round(…, 3)`）。真等过才写，0 不占位。
2. **兼容读只朝一个方向**：新代码认 `("v1","v2")`，旧代码只认 `"v1"` → 旧读新＝没记忆（见 §5）。
3. **`MEM_FIELDS` 白名单一字未动**（`wait` 不在里面）：v1.5 定的"存的是下一轮模型读得到的字段"这条纪律保持住了，7d 断言的就是模型读到的那一串逐字不变。所以 `wait` 是**界面上的账随记忆一起存**，不是模型上下文的一部分——它和 `timing`、`token_usage` 同一类（界面用、`to_messages()` 不认）。
4. **体积**：每格 12~17 个字符（`, "wait": 20.743` 这一串是纯 ASCII，**字符数＝字节数**），只有领到账的那个 ActionStep 才有；真实库 8 条 payload「读进来再编回去」长度差全 0（7g）。基线 E3 数的量级：库里 17 条 ActionStep 全等一遍也就多 ≈200 B。
5. **状态条口径变了（本轮唯一的界面行为变化）**：那串「本题」的数现在报的是**屏幕上这一条会话**，不再报"上一次提问的那条"。同一个数在不同会话之间来回切会跟着变——以前不会。`_stats()` 不传参时行为与 v1.6 逐字相同（7r 断言），改的只有两个调用点。
6. **「本题耗时 / 步骤总时长」定义仍一字未动**（含等待）。
7. **修掉一处过时的注释口径**：v1.6 在 `_stats` 上写"屏幕上那条历史卡也就不带审批那一格"——**实测是错的**，卡片正文走 `messages` 表，重启后那句「（含审批 21.0s）」一直都在；真缺口只在 `_stats`/状态条。写进 §1 的 B3 里，免得下次又照注释理解。
8. **token 口径未动**。同题同步长对照：第 1 步 `in 2,355/out 22` ＋ 第 2 步 `in 2,438/out 17` ＝ 本题 `4,793/39`；裸起步实测 `2,349`（v1.6 是 `2,344 / 2,349`，同级；差异仍是模型侧波动）。**进程档每次重启归零**这条定义没变。
9. **体量**：`my_ui.py` 1,205 → 1,253 行、63,316 → **67,362 B**、净 **`+85 / −37`**（含第 7 步那三行注释修正）；`.rollback/` 存档 **14 → 16 份**（7 → 8 套）；**三份文档**同步：README **1,350 → 1,445 行**（124,886 → **144,128 B**）、`agent功能手册.html` **1,182 → 1,285 行**、`迭代记录.md` 本节 **115 → 118 行**（§4 表加了三行文档闸）；看板 **36 → 37 条**（V9 转已上线、新立 D8）

### 7 已知遗留（下次的输入）

- **新立 D8（本轮实跑暴露，两条路都有留痕）**：正在流式（尤其挂在审批闸上等人点）的时候刷新页面或关页面，这一题**一行都不落库**——`_respond` 开头已经 `ensure` 建了会话行，屏上曾经有字，但消息与记忆都没写，那笔审批等待也一起蒸发；同时 `待批` 的 pill 挂在已经「空闲」的状态条上、按钮 reload 后就不存在了。**机制【未验证】**：`_respond` 的 `finally` 到底跑没跑到（gradio 在客户端断开时是否 `close()` 那条生成器？worker 线程当时正阻塞在 `ap.wait()`，那条 `pending` 只能等 `APPROVAL_TIMEOUT=600s` 自己按拒绝结算）。下一刀的基线就该问这三件事：断开时 finally 的语义、阻塞中的闸怎么随断开结算、以及"落半截"和"标已中断"选哪个。v1.5 那句"半截可接受"的前提是半截会落库，实测连半截都没有。
- **v1 时代的老账永远没有「本题审批」**：那个数从来没进库，本轮不猜、不补。**库里 v1 的行不会被回写升级**（旧 7 行 sha1 逐行不变就是这条的断言）→ 好处是回滚面小，代价是同一个库里两种格式长期并存，`MEM_FMT_READ` 得一直带着。
- **并行多工具时那一格等待挂在"第一个到达的 `ActionStep`"上**（v1.6 §6.5 就写着这条），本轮所有题仍是单工具【未验证：多工具并行怎么分这两格】。
- **只读路径不改绑定**：点旧会话现在屏上／条上一致了，但 `agent.memory` 仍停在上一条提问的会话——这是 V5 的语义，本轮有意不动。**代价**：点甲看了两眼再提问，问题落进的是"新起的那条"而不是甲【未验证：多标签同开时 `_sid_shown` 的守卫】。真要让点击就换绑定，得先解决 `_bind_memory` 上面写的那条 worker 竞争。
- **`gradio_ui.py:456` 的 `.capitalize()`** 仍未动（等你点头）；**验收脚本仍在 `/tmp`**：本轮新增 `v17_base.py` / `v17_base_v16.py` / `v17_dbg.py` / `v17_seed.py` / `v17_ui.py` / `v17_live.py` / `v17_dump.py` / `v17_delivery.py` / `v17_real_after.py` / `v17_test.py` ＋ 输出 `v17_base_v16.out` / `v17_pre.out` / `v17_post.out` / `v17_peek.out` / `v17_finish.out` / `v17_drain.out` / `v17_delivery_ask.out` / `v17_delivery_post.out` / `v17_real_before.json` / `v17_drill_backward.out` / `v17_drill_forward.out` / `v17_drill.sh` / `v17_drill_rerun.out`（点击与读屏沿用 v1.6 的 `v16_cfg.py` / `v16_cdp.js` / `v16_read.js`）＋ **第 7 步文档闸那批**：`v17_map16.json`（difflib 行映射）`v17_README.before.md`（写入前整份备份）`v17_readme_align.py` `v17_readme_apply.py` `v17_readme_recount.py` `v17_readme_sec8.py` `v17_readme_sec9.py` `v17_readme_sec91.py` `v17_readme_sec93.py` `v17_readme.diff` `v17_readme_full.diff` `v17_manual.before.html` `v17_manual.before-sec6.html` `v17_manual_align.py` `v17_manual_align.dry` `v17_manual_apply.write` `v17_manual_sec4.py` `v17_manual_sec6.py` `v17_manual_fix.py` `v17_manual_gates.py` `v17_log_gates.py` `v17_scan.py` `v17_wide.js`～`v17_wide9.js` `v17_bisect.js` `v17_fixtry.js` `v17_fixtry2.js` `v17_measure.js` `v17_manual_check_1440.js` `v17_manual_check_1180.js` ＋ 输出 `v17_mmd_readme.out` `v17_mmd_neg.out` `v17_manual_gate_1440.out` `v17_manual_gate_1180.out` `v17-manual.png` `v17-manual-1180.png`——macOS 一重启就没了，只剩本记录里的数字。**要不要开 `ai学习/验收脚本/`（按版本号分目录）收进来，仍然等你点头**。
- 仍欠你的点头：dify Docker Compose（#5）、MCP servers `npm ci`（#6）、**百炼 Key 轮换**、`gradio_ui.py:456` 的 `.capitalize()`、D2（staging 副本读不回来）、P0-4。

**推荐下一刀 v1.8 = D8 先、P0-4 后**：D8 是本轮实跑抓出来的数据完整性问题（一屏字能整轮丢），基线已经写好；P0-4（计划可见）是新功能，地基（v1.3 的线程 ＋ 允许/拒绝键）本来就铺好了，往后排一格不亏。

---

## v1.6 · 2026-10-30 · 侧栏高亮跟着绑定走 + 审批等待从步骤耗时里单列（V7 + V8）

### 1 这次解决什么（为什么现在做）

范围按工单号锁定 **V7 + V8**（V7＝v1.5 §7 第 1 条立的那单；V8＝本轮新立，单号同批进手册第 4 节看板）。`my_coding_agent.py`、`my_agent.py`、上游源码零改动；记忆编解码、审批闸的**判定**、停止的语义一行未碰——本轮只从闸那里多读了一个秒数。

- **V7 的根因是「高亮」和「绑定」是两件事**。v1.3 换自建 Blocks 之后，侧栏那条 Radio 的 `checked` 由浏览器自己的点击历史决定，服务端的 `self._sid`（真正决定问题落进哪条会话）却另有三条写路径：`_respond` 建条、`_new_session` 清空、`_on_load` 指到最近一条——这三条**都不回写高亮**。于是点「＋ 新会话」之后屏幕换成空白（绑定＝新会话），radio 却还是上一条亮着；用户照着亮着的那条点＝点了一个**值没变**的 radio → gradio 不派发 `change` → 问题落进新会话。v1.5 记录过后果（探测口 `in 2,463`、答「不记得」），本轮在种子库上把这条链**原地复现**了一遍（§4 的 before/after 表）。
- **为什么不干脆"每帧都带 value"**：本轮实测 gradio 6.30 里**服务端设 `value` 会被算成一次 `.change` 送回后端**（详见 §4 那条"过程发现"）。流式期间每 0.25 秒一帧，那就是每秒两次空转事件，而且送回的那条回调和正在流式的那条会抢同一个 chatbot 输出。所以方向反过来：**`choices` 每帧刷，`value` 只在绑定真的换了那一次给**，同时给 `_select_session` 加"值没变就是回声"的守卫。
- **V8 的由来是 v1.5 §6.9 那句白纸黑字的"本轮没改"**：`第 1 步 · run_python · 🟢 成功 · 272.9s`，真执行约 1 秒——**271 秒是人在喝咖啡**。把等待算进步骤耗时是 v1.3 卡片化时留下的口径，诊断上是误导：看不出到底是模型慢、工具慢，还是没人点按钮。本轮把那一格拆出来，**总时长的定义一个字都不改**（仍是框架的 `timing.duration`，含等待），只是旁边多一格「审批 X.Xs」、状态条多一枚「本题审批」pill、审批卡结算后带「等了 X.Xs」。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:37-40` | `APPROVAL_WAIT_MIN = 0.05`：不满 0.05 秒的"等待"不值得单列一格。注释里写死了它存在的原因——D7 那条"入队即随停止取消"的路，账上确实有 0.0004 秒，屏上写「审批 0.0s」纯属噪声（交付形态实测抓到过 `⚪ 已取消 · 0.9s · 审批 0.0s`） | 新增 | V8 |
| `my_ui.py:363-365` / `368-372` / `374-378` | `Approval`：建单即 `self.waited = 0.0`；`decide()` 在**落定那一刻**记 `time.time() - self.created`；`wait()` 的超时分支记 `APPROVAL_TIMEOUT`。不放在 worker 醒来那一刻，是为了让审批卡第一次画收尾状态时就带得上这个数 | 修改 | V8 |
| `my_ui.py:518-521` | 类级 `_pending_wait: float = 0.0`。注释：记帐的是 worker 线程（`_gated_call` 醒来那一刻），取帐的是 UI 线程（收到 `ActionStep` 那一刻）；和 `_run_seq` 同一个理由——门只装在进程唯一的那个 agent 上，装门的实例和画卡的实例可能不是同一个 | 新增 | V8 |
| `my_ui.py:533-538` | `__init__`：`_run_wait = 0.0`（本题累计里"其中等待"那一格，与 `_run_secs` 同边界）、`_sid`（现在绑的是哪条）、`_sid_shown`（上一次真的推给浏览器的高亮值） | 新增 | V7 / V8 |
| `my_ui.py:588-592` | `_gated_call`：`ap.wait()` 之后在**同一个 `_gate_lock` 临界区**里过账，且 `ap.waited >= APPROVAL_WAIT_MIN` 才记 | 修改 | V8 |
| `my_ui.py:621-632` | `_approval_card` 标题：`pending` 态不加、结算后加 `· 等了 X.Xs`；用 `ap.waited` 而不是现场 `time.time()-created`（后者会把"工具又跑了多久"算进去，且会改掉已结算卡片的标题） | 修改 | V8 |
| `my_ui.py:700-723` | `_step_card`：标题多 `· 审批 X.Xs`（总时长那格不动，`22.1s · 审批 21.0s`）；正文「本步 22.1s（含审批 21.0s）」；末行「本题累计 … 含审批 …」 | 修改 | V8 |
| `my_ui.py:745-748` | `_stats` 新增 `task_wait`：当前会话 steps 上 `_opsui_wait` 之和。注释写明它是**进程内属性**，回放的旧步骤读成 0 | 修改 | V8 |
| `my_ui.py:770-772` | `_status_html`：「本题耗时」pill 之后 `if s["task_wait"]` 才追加「本题审批」pill——没审批就一格都不多 | 修改 | V8 |
| `my_ui.py:816-822` | `_stream_response` 开局：在已有的 `with self._gate_lock:`（`_pending.clear()` 那一段）里加 `OpsUI._pending_wait = 0.0`，并 `self._run_wait = 0.0`——上一题没被领走的账不许漂到新题头上 | 修改 | V8 |
| `my_ui.py:873-880` | `ActionStep` 到达时：`with self._gate_lock: waited, OpsUI._pending_wait = OpsUI._pending_wait, 0.0`（**一次取干**），非零才 `payload._opsui_wait = waited` 并累进 `_run_wait`。注释写明这个私有属性不在 `encode_memory` 的字段白名单里，所以不进记忆库 | 修改 | V8 |
| `my_ui.py:968-986` | **新增 `_radio_update(force=False)`**：`ch = self.hist.choices()` 每帧都给；`force or self._sid_shown != self._sid` 时才带 `value=self._sid`，否则只交 `choices`。docstring 记了三件事：bug 本体、为什么不能每帧带 value（实测的 `.change` 回声）、`force` 是给刷新页面用的 | 新增 | V7 |
| `my_ui.py:1007-1008` / `1023` | `_respond`：`sid = self.hist.ensure(sid)` 之后 `self._sid = str(sid)`；每帧那条 radio 从裸 `gr.update(choices=...)` 改成 `radio = self._radio_update`（可调用，逐帧现算） | 修改 | V7 |
| `my_ui.py:1068-1074` | `_new_session`：`self._sid = None` 并返回 `self._radio_update()`——新会话此刻库里还没有行（第一问下去才 `ensure`），**没有"那一条"可亮，把高亮清掉才是实话** | 修改 | V7 |
| `my_ui.py:1098-1116` | `_select_session`：`if not sid or str(sid) == self._sid: return gr.update(), gr.update(), gr.update()`（守卫挡在 `int()` 之前，且三个输出全空、不抢 chatbot）；真切换时 `_sid` 与 `_sid_shown` **一起**更新 | 修改 | V7 |
| `my_ui.py:1125-1132` | `_on_load`：`self._sid = str(sid) if sid else None` + 返回 `self._radio_update(force=True)`。v1.5 这里是"绑着丙、侧栏一条都不亮" | 修改 | V7 |
| `ai学习/.rollback/v1.6/` | 新增第七套存档（`my_ui.py` + `my_coding_agent.py`），`.rollback/` 共 **14** 份 / **7** 套 | 新增 | 回滚 |

体量：`my_ui.py` **1,108 → 1,205 行**（**55,774 → 63,316 B**；字符 46,071 → 50,717；`diff` 净 **`+105 / −8`**）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.5`、`.rollback/v1.6` 双份一致）。上游源码零改动，库 schema 零改动。

### 3 新功能怎么用（用户视角）

1. **点「＋ 新会话」之后侧栏一条都不亮**——因为那条会话还不存在（第一问下去才建行），亮着任何一条都是骗人的。
2. **想回刚才那条：直接点它，屏幕和绑定一起回来**。v1.5 这里要点两下（第一下是空点），而且空点那一下会把问题送进新会话。
3. **刷新页面**：亮着的那条就是你现在所在的那条（v1.5 是全部不亮、看不自己在哪）。
4. **提问时新建的会话当场点亮**。
5. **审批跑完，那一格等待单独看得见**：步骤卡从 `272.9s` 变成 `22.1s · 审批 21.0s`；状态条多一枚「本题审批 21.0s」；审批卡结算后带 `已允许 · 等了 21.0s`。
6. **没审批的题/步骤一格都不会多**（标题、正文、状态条都不出现"审批 0.0s"这种噪声）；随「■ 停止」取消的微秒级等待也不过账。
7. 「本题耗时 / 步骤总时长」的定义**没变**，仍然是含等待的那一个数——要看纯执行时间就用 `总时长 − 审批`。
8. 一条边界：**重启后回到旧会话，「本题审批」那格读不出来**（等待是 step 对象上的进程内私有属性，不进记忆库）；「本题耗时」照旧读得出。

### 4 上线验收（当场跑过的真实输出）

离线：`/tmp/v16_test.py`（venv python，`_stream_response` / `agent.run` 打桩、临时库）——**92 条断言全 PASS，`FAILS: 无`**（`/tmp/v16_test3.out`）。组成：v1.5 那 **65 条原样搬过来全绿**（编解码 16 / 落库与重启 22 / D7 17 / 回归 10）＋ 新增 **5 V7 10 条**（5b 刷新后不再是"绑着某条、一条都不亮"、5d 值没变的那次回声三个输出全空、**5g 新会话之后点"刚才那条"是真切换**、5h `value=None` 的回声不崩（守卫挡在 `int()` 之前）、5j 整题只回送一次 value）＋ **6 V8 17 条**（6a 记在 `decide()` 那一刻、6d 入队即取消不过账、6g 两格并存且后者 ≤ 前者、6l 没审批的题一格不多、6m 换题清零、**6n `_opsui_wait` 进不了记忆库**、6o 总时长照旧进得去、6p/6q 审批卡同一条门槛）。

**V7 基线复现 → 同一条链路复跑**（探测口 7861，种子库 3 条会话、**零模型调用**，链路 `/tmp/v16_base.json`，证据 `/tmp/v16_base.before.txt` / `/tmp/v16_base.after.txt`；点击全部走 CDP `Input.dispatchMouseEvent` 真鼠标事件）：

| 步骤 | v1.5（改之前） | v1.6（改之后） |
|---|---|---|
| 0 打开页面 | `chk=[false,false,false]`——**绑着丙却一条都不亮** | `chk=[true,false,false]`——绑谁亮谁 |
| 1 点「甲」 | `chk=[false,false,true]`，屏上 1 问 1 答 | 同（无回归） |
| 2 点「＋ 新会话」 | **`chk=[false,false,true]` 甲还亮着**，屏上已是「还没有会话」 | `chk=[false,false,false]` 全不亮，与屏一致 |
| 3 点那条亮着的「甲」 | **空点**：`chk` 不变、`user/bot` 都不出现（`change` 没派发）→ 下一问落进新会话 | `chk=[false,false,true]`，1 问 1 答回来 |
| 4 对照：点从没亮过的「乙」 | 正常 `chk=[false,true,false]` | 正常，两边一致 → **差别只在"值没变的那一次"** |

真模型复跑（探测口 7861，`/tmp/v16_v7live2.out`）：新会话问「记住一个数字：73」→ 该条**当场点亮**（`chk=[true,false,false,false]`）、`in 2,344 / out 16`、`Final answer: 好`；点「＋ 新会话」→ `chk` 全 false；**再点回那条**（v1.5 这里是空点）→ `userN=1 botN=2`、`Final answer: 好` 回到屏上；在它下面追问 → **`Final answer: 73`**、`in 2,439`、进程 `4,783/33`，侧栏**没有多出一条新会话**（落对门了）。

在线·**交付形态**（7860，真 qwen-plus；`/tmp/v16_delivery.py`、`/tmp/v16_d7b.json` 经 CDP 9333 驱动 headless Chrome；库＝真实的 `smolagents/.agent-history.sqlite3`）：

| 判据 | 结果 |
|---|---|
| **V8 总时长口径不变、等待单列** | 状态条 `本题耗时 22.9s` ＋ **`本题审批 21.0s`**；步骤卡 `第 1 步 · run_python · 🟢 成功 · 22.1s · 审批 21.0s · in 2,349/out 22`；第 2 步 `第 2 步 · final_answer · 🟢 成功 · 0.8s · in 2,433/out 17`（**没审批就没那一格**） |
| **V8 审批卡结算后带等待** | `🟢 待批 · run_python · 已允许 · 等了 21.0s` |
| **V7 新会话把高亮清掉** | 点「＋ 新会话」后 `chk=[false,false,false]`，屏上「还没有会话」，两边一致 |
| **V7 点那条旧的真回来了** | 点 A 会话 → `chk=[true,false,false]`、屏上 1 问 4 气泡、`Final answer: 21` |
| **V7 追问落在对的那条** | 同一条再问「再把那个数字回给我一次」→ `第 1 步 · final_answer · 🟢 成功 · 0.8s · in 2,525/out 17`、`Final answer: 21`；`in 2,525` 说明带着历史，侧栏**没有多出会话** |
| **D7 复测（门槛加完之后）** | 提问后 0.9s 按 ■ 停止：`awaitSeen 0`（**从没进过**「等待审批」）、`runSeen 0`、**2.0s 自己收尾**、状态 `已停止`；卡片 `第 1 步 · run_python · ⚪ 已取消 · 1.1s · in 2,349/out 22` ＋ `⏹ 待批 · run_python · 随停止取消`，**「审批 0.0s」那格不再出现**（`pillWait=null`）。加门槛之前同一条路实测抓到的是 `⚪ 已取消 · 0.9s · 审批 0.0s` |
| **V8 长等待（探测口）** | 7861 挂 **71.0s** 再点允许 → `本题耗时 72.9s` / **`本题审批 71.0s`** / `Final answer: 21`；等待期间 `本题耗时 0.0s`、状态 `等待审批`、pill `待批 run_python`（`/tmp/v16_v8live.out`） |
| 真实库形状（本轮跑动**只追加**，无覆盖） | `sessions 7` / `messages 49` / `memory` 7 行；payload 长度 `[4042, 537, 1422, 536, 88, 537, 537]`（88 那条就是 D7 停在建单之后的半截，只有 `TaskStep`） |
| **回滚演练（双向）** | `cp .rollback/v1.5/* → 断言 → cp .rollback/v1.6/* → 断言 → cmp`：**v1.5 方向 25 条全 PASS**（`py_compile`、`import` 起来且字符数与磁盘一致、行数 1,108、**V7 四个锚点全不在**——含「新会话那句不回写高亮」这条 bug 本体、**V8 六个锚点全不在**、`Approval` 不记等待），**v1.6 方向 31 条全 PASS**（V7 7 条 + V8 8 条 + 同一份共享清单）；两份断言里 **14 条共享清单两个方向都必须绿**（V6 编解码 / memory 表 / `_bind_memory` 回灌 / 落库归属判据、D7 四个锚点、D5、V5、D6、v1.3 审批闸）→ 这两刀都是**加法式**改动。恢复后与 `.rollback/v1.6/` **逐字节一致**（`cmp` 两份），再跑离线 **92 条 `FAILS: 无`** |
| 四条关停判据 | `bash 关闭Agent.command` 之后实测：7860 监听 **0**、Agent 专用 Chrome（`Application Support/AgentClient`）**0**、`who` 只剩 **console**、System Events `count of windows of process "Terminal"` = **0** |
| 日志零噪声 | 收工前 `.agent-ui.log` **14 行 / 1,815 B**，`grep -c` 七种模式（`Traceback` / `Error in callback` / `asyncio.exceptions` / `RuntimeError:` / `gradio.exceptions` / `ClosedClient` / `Event loop`）**全 0** |
| **文档闸·README 行号重新对齐**（第 7 步前半） | 提议器 `/tmp/v16_readme_align.py`：逐条判这个号是 **v1.4 时代**还是 **v1.5 时代**的（判据＝这句话的标识符/实体与那一版源码块、与 v1.6 目标块的重叠，取高者；v1.4/v1.5→v1.6 的行映射由 difflib 生成，`/tmp/v16_map14.json` / `v16_map15.json`），跨度做 def/class 扩展并修剪空行。落盘器 `/tmp/v16_readme_apply.py`：按**列位置**从右往左替换，`OVERRIDE` 记人工改判、`SKIP_LINES` 排除别的文件、不带 `--write` 只出干跑清单。**结果：161 条引用（分布在 97 行上）对齐到 v1.6，98 行改动、总行数不变**；判据分布 HIT **162** / TIE **4** / ZERO **12** / NO-MAP **1** / skip **3**（候选共 182 条，这一份统计是**写入之前**那一轮跑的；本轮新增的 §6.3.8 里那些号本来就是 v1.6，再跑提议器会被当成"v1.5 时代的号"重新映射，所以不作闸用）。人工改判合计 **7 处**进 `OVERRIDE`：`:874`→`:1186`、`:694`→`:730`、`:820`→`:1132`、`:1025-1035`→`:1118-1132`、`:401`→`:410`、`my_ui.py:584`→`:608`、`my_ui.py:564-567`→`:583-586`。**事后两道扫**：越界（`:NNN > 1,205`）在 §6.3 / §8 / §9 范围内 **0** 条（其余 5 条命中全是 `agents.py`、`local_python_executor.py`、dify 的行号）；指向空行 **0** 条（唯一命中 `:31-36` 是刻意保留的 v1.1 历史号）。**刻意不动的历史引用**：`:70-72`、`:310`、`my_ui.py:10` / `:4`、`:31-36`——它们是"哪一版在什么位置"的叙述；别的文件的引用（`:545-547` agents.py、`:1467`、`:1428-1434`、dify/servers、`my_agent` / `关闭Agent.command` 的 629 与 903 行）一律排除 |
| **文档闸·README 现状 + 手册自身**（第 7 步后半） | README 新增 **§6.3.8**（V7 + V8 全节：根因与三条写路径、那条 gradio 实测语义、V8 跨线程机制图、两张实测表、验证与回滚、四条边界），§6.3 标题与文首口径 **1,108 → 1,205 行**，§8 补 **3 个场景**（V7 高亮跟绑定 / V8 等待单列 / 「本题审批」跨重启＝已知边界），§9.1 补 **47、48** 两行，§9.4 补 **13** 条并把第 12 条改成"七轮"→ **1,271 → 1,350 行**（108,336 → **124,886 B**）。**Mermaid 闸：块 `23 → 24`，`块数 24 / 产出 svg 24 / 语法错误 0`「全部通过」；负控 `/tmp/v16_mmd_negative.md` → `语法错误 1` 且 `exit=1`**（排除"校验器假通过"重演）。**静态闸** `/tmp/v13_htmlcheck.py`：未闭合 `[]`、配对错误 **0**、外部资源 **0**、死锚点 `[]`、看板 **36** 行、`data-st {todo 16, doing 0, done 17, na 3}`、`data-p {D 7, P0 5, P1 8, P2 7, V 9}`。**浏览器闸** `/tmp/v16_manual_check.js` + `_1180.js`（无头 Chrome `file://` 真打开）：`rows 36`、`tables 29`，十个筛选器 `#cnt` 与可见行数**逐条相符**（`all 36 / bug 7 / p0 5 / p1 8 / p2 7 / v 9 / todo 16 / doing 0 / done 17 / na 3`），`overflowX=false` 在 **1425** 与 **1165** 两档视口都成立（`inner == scrollW`），状态胶囊 **V7 / V8＝已上线 v1.6**、**V9＝未开工（v1.6 新立）**、V6 / D7 仍为已上线 v1.5，截图 `/tmp/v16-manual.png`（**214,055 B**）。**这两行文档闸自己也被闸抓过一次**：初稿里 `<b>Mermaid：…` 套了一个 `<b>exit=1</b>` 后忘了收外层，静态闸当场报 **6 处配对错**（从 `</td>` 一路串到 `</table>`、`</div>`、`</body>`），修完回到 **未闭合 `[]` / 配对错误 0**——文档闸对文档本身同样管用 |

**本轮实测出来的两条机制（决定了写法，必须留下）**：
1. **gradio 6.30 里服务端 `gr.update(value=...)` 会被当成一次 `.change` 送回后端**——程序化设 `value="B"` 触发 `.change`，设 `value=None` 也送回一次 `None`，但两者都**不**触发 `.input`；只有用户点选才 `.change` / `.input` / `.select` 三件齐发（探测口 `/tmp/v16_semantics.py`，7862）。第一版我把它测成了"程序化设值不触发 change"，原因是**两个事件处理器写同一个 textbox 会互相盖掉**——一个事件一个输出才测得干净。
2. **合成点击在 gradio radio 上不可靠**：`label.click()`、`input.click()`、`dispatchEvent(MouseEvent)` 都不能稳定触发事件（v1.5 那条"反证"就是这么测的），必须用 CDP 的真鼠标 `mousePressed`/`mouseReleased`。本轮所有点击判据都是真鼠标链路。

**要如实记下的过程问题**：① 离线套件在 5i 挂死 100 秒以上，是第 4 节末尾把 `_stream_response` 换回了真版本、而 `agent.run` 还是 D7 那个等闸的假版本；用 `faulthandler` 打栈定位后在第 5 节开头重新装上 `fake_stream`。② 「审批 0.0s」这个噪声**是实跑交付形态时才露出来的**（离线断言当时只测"该出现的地方出现了"，没测"不该出现的时候没出现"），补了 `APPROVAL_WAIT_MIN` 之后 6d/6p/6q 三条才是它的回归断言。③ 本轮在线跑动在真实库里**只追加**了会话（见上表）。token 花销按**当时屏上的进程档**记：探测口那个进程累计 `in 9,563 / out 72`、交付形态那个进程累计 `in 7,307 / out 56`、回滚演练之后补跑的 D7 复测 `in 2,349 / out 22`，这**三份有留痕的**合计 **≈1.9 万 input**；除此之外 10:16~10:22 还有三次 D7 复跑（就是库里会话 4/5/6，门槛加之前那两次露出「审批 0.0s」的路），单题量级 `in ≈2.3~2.4 千`，但**当时只打在终端、没落成文件**【未留痕】——按三条各 ~2.4 千 估，本轮在线总花费 **≈2.6 万 input**。

### 5 回滚方法

```bash
cp ~/Desktop/study/ai学习/.rollback/v1.5/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.5/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

行为退回两条：① 点「＋ 新会话」之后上一条仍亮着，照着那条点＝空点，问题落进新会话（v1.5 §7 那条遗留）；② 审批等待重新并进唯一的时长格（`第 1 步 · … · 272.9s` 那种），状态条没有「本题审批」、审批卡没有「等了 X.Xs」。V6 的记忆落库、D7 的停止竞态、D5/V5/D6、v1.3 审批闸**都不受影响**（§4 那份 14 条共享清单在两个方向都跑绿了）。`my_coding_agent.py` 本轮未动，同拷一份只是让存档自洽；上游源码与库 schema 零改动，无需碰 `.venv`。

**数据不会坏**：本轮没建表、没改字段白名单、没改 `MEM_FMT`——v1.6 写的 payload 和 v1.5 的是**同一个格式**，回滚后照读；v1.6 在屏上多显示的那格等待**从来没进过库**（§6.2），所以也不存在"回滚后读出多余字段"的可能。
**但回滚会把 V7 那个真后果重新打开**：临时办法仍然是点旧会话前先点别的、再点目标那条（绕开"值没变"）。

### 6 口径与数据变化

1. **显式声明一处行为语义变化**：界面上「等待」第一次**单独可观测**。之前（v1.3~v1.5）审批等待只融在"步骤耗时"这一个数里；现在同一件事分三处显示——步骤卡标题 `22.1s · 审批 21.0s`、正文「本步 22.1s（含审批 21.0s）」、状态条「本题审批 21.0s」。**总时长那一格的定义没动**。
2. **等待不进记忆库**：`_opsui_wait` 是挂在 `ActionStep` 对象上的私有属性，`encode_memory` 的字段白名单（`MEM_FIELDS`）不认它 → **重启后回放的旧步骤读不出这一格**（新题照旧单列）。这条和 v1.5 定的"只存 `to_messages()` 读到的字段"是同一条纪律，**是写下来的边界，不是 bug**。离线 6n/6o 就是它的两面断言。
3. **记账时刻与位置**：`waited` 记在 `decide()` 那一刻（点下 ✔/✖、或随停止/超时落定），不是记在 worker 醒来那一刻——这样审批卡第一次画收尾态就带得上这个数，也不会因为现场时钟把已结算卡片的标题改掉。超时路径记 `APPROVAL_TIMEOUT`（600.0），不记现场时钟。
4. **门槛 0.05 秒在两处生效**：`_gated_call` 的**过账点**（不过门槛就不记账，`_pending_wait` 根本不涨）和 `_approval_card` 的标题。所以「本题审批」和「等了 X.Xs」是同一口径，不会出现 pill 上没有、卡片上写 0.0s 的错位。
5. **「一次取干」语义**：`_pending_wait` 由**下一个到达的 `ActionStep`** 领走并清零；`_stream_response` 开局把上一题没领走的账清零。多工具并行仍只处理最早那一条（v1.3 就在），所以那一格等待挂在**第一个到达**的 `ActionStep` 上——并行多工具时两格怎么分【未验证】：本轮所有题都是单工具。
6. **累计边界不变**：`_run_wait` 与 `_run_secs` 同边界（`_respond` 起题归零），`_stats["task_wait"]` 按当前会话的 steps 求和——和「本题耗时」同一口径。
7. **token 口径一字未动**（本轮纯界面层）。同题同步长的对照：`第 1 步 in 2,349/out 22` ＋ `第 2 步 in 2,433/out 17` ＝ 本题 `4,782/39`；追问 `in 2,525/out 17`。裸起步本轮实测 `2,344` / `2,349`（与 v1.5 的 `2,363` 同级，差异来自提示词未变、模型侧波动）。**进程档每次重启归零**，仍是进程统计的定义。
8. **体量**：`my_ui.py` **1,108 → 1,205 行**、**55,774 → 63,316 B**、净 **`+105 / −8`**；`.rollback/` 存档 **12 → 14 份**（6 → 7 套）。

### 7 已知遗留（下次的输入）

- **「本题审批」跨重启读不出来**（§6.2）：要让它进库得给记忆格式加字段（`MEM_FMT` 升 v2 ＋ 兼容读旧 payload）。本轮范围外、也不该顺手做——**建议立 V9**。
- **等待是进程内的账**：`_pending_wait` 类级、`_run_wait` 实例级，换题/刷新就归零。这是"本题"的定义；如果哪天要看「今天总共等人点按钮点了多久」，那是跨题累计，另一张 V 单。
- **V7 的守卫假设"一个窗口"**：`_select_session` 现在按 `str(sid) == self._sid` 拦回声，两个浏览器标签同时开着时，另一个标签的真实切换会被服务端当成"值没变"退回【未验证：本轮全程单标签】。与 v1.5 那条「并发提问共用一个 agent」是同一类限制。
- **新会话不点亮**：因为库里那一刻还没有行。若哪天改成点「＋ 新会话」即建行（而不是第一问下去才 `ensure`），这里必须跟着改成"亮那一条"，否则又是一次高亮/绑定分家。
- **`gradio_ui.py:456` 的 `.capitalize()`** 仍未动（等你点头）；**验收脚本仍在 `/tmp`**：本轮新增 `v16_test.py`、`v16_rollback_check.py`、`v16_seed.py`、`v16_ui.py`、`v16_semantics.py`、`v16_cfg.py`、`v16_cdp.js`、`v16_read.js`、`v16_v7run.py`、`v16_v7live.py`、`v16_v8live.py`、`v16_delivery.py`、`v16_d7run.py`、`v16_iso.py`、`v16_add_tests.py` ＋ **第 7 步文档闸那批**：`v16_map14.json` / `v16_map15.json`（difflib 行映射）、`v16_readme_align.py`（提议器）、`v16_readme_apply.py`（落盘器，`OVERRIDE` / `SKIP_LINES` / `--write`）、`v16_align.out`、`v16_apply.dry` / `v16_apply.write`、`README.before-v16.md`（写入前整份备份）、`v16_readme.diff`、`v16_mmd_negative.md` ＋ 输出 `v16_base.before.txt` / `v16_base.after.txt` / `v16_v7live2.out` / `v16_v8live.out` / `v16_delivery.out` / `v16_d7c.out` / `v16_test3.out`——macOS 一重启就没了，只剩本记录里的数字。**要不要开 `ai学习/验收脚本/`（按版本号分目录）收进来，仍然等你点头**。
- 仍欠你的点头：dify Docker Compose（#5）、MCP servers `npm ci`（#6）、**百炼 Key 轮换**、`gradio_ui.py:456` 的 `.capitalize()`、D2（staging 副本读不回来）、P0-4。

**推荐下一刀 v1.7 = V9（把审批等待写进记忆格式，让重启后的旧步骤也读得出那一格；顺带 `MEM_FMT` 升 v2 的兼容读）**；P0-4（计划可见）继续往后排，「验收脚本入目录」单独等你点头。

---

## v1.5 · 2026-10-29 · 记忆落库：重启后模型那一边接着记得 + 停止落在待批之前不再死停（V6 + D7）

### 1 这次解决什么（为什么现在做）

范围按工单号锁定 **V6 + D7**（`my_coding_agent.py`、`my_agent.py`、上游源码零改动；审批闸、步骤卡、状态条一行未碰）。

- **V6＝V5 的第二半**。v1.4 §7 第 1 条留的实测后果：重启进程后旧会话的字还在屏上（那是从库里读出来的聊天记录），但同样的问题模型答 `Final answer: 不记得`，框架日志 `Step 3: Input tokens 9,015`（−5,631＝本题 **3,384**），说明模型那一边**一个字都没带上**。
- **为什么不是"把屏幕文字重放一遍"**：`agents.py:767-769` 的 `write_memory_to_messages()` ＝ `memory.system_prompt.to_messages()` ＋ 逐条 `step.to_messages()`。模型读的是 `memory.steps`，不是 chatbot 那串给人看的 markdown 卡片。重放屏幕文字有两个代价：得重定「本题累计」的边界，而且 `in` 会随历史**线性涨**。所以存的是**字段本身**。
- **存哪些字段有根据**：`memory.steps` 里只会出现 `TaskStep` / `ActionStep` / `PlanningStep` 三种——`FinalAnswerStep` 只 yield 不 append（`agents.py:609-611`），超步数时 `:636` append 的是**带 `AgentMaxStepsError` 的 ActionStep**。按 `to_messages()` 实际读到的字段清单存，就等于存下"模型下一轮读到的那一串"。
- **D7＝v1.4 复现并定位的那条竞态**：`■ 停止` 落在待批卡**出现之前**（实测 0.2s 那一下）等于空放——`agents.py:470` 在新 run 开头把 `interrupt_switch` 清回 `False`，那一按中断的是**空闲的** agent；随后到的待批没人结算，界面死停 `等待审批`（实测挂 **142.4s**，`APPROVAL_TIMEOUT` 是 600s，不会自己解），要手动补 ✖ 才解开。修法是 v1.4 §7 写下的两条里的第 **②** 条：`_stop` 给本轮打**取消号**，闸在入队那一刻看到号就直接按 `cancelled` 结算。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:17-27` | import 补齐：`memory` 侧加 `ActionStep / FinalAnswerStep / TaskStep / ToolCall`（`AgentMemory` v1.4 已在），新增 `from smolagents.monitoring import Timing, TokenUsage`、`from smolagents.utils import make_json_serializable` | 修改 | V6 |
| `my_ui.py:59-76` | `MEM_FMT = "v1"` + `MEM_FIELDS`：三种 step 各自的字段白名单。注释写明清单来自 `agents.py:767-769` 的 `to_messages()`，`model_input_messages`（整段提示词，O(n²)）**不存** | 新增 | V6 |
| `my_ui.py:78-87` | `_error_types()`：沿 `AgentError.__subclasses__()` 递归，按**类名**索引（类名是唯一能安全落库的形式） | 新增 | V6 |
| `my_ui.py:88-105` | `_decode_error(d)`：用 `cls.__new__(cls)` + `Exception.__init__(err, message)` 造错误对象，再手设 `.message`。不走正常构造是因为 `AgentError.__init__(message, logger)` 的 logger 必需、且会**当场** `log_error` | 新增 | V6 |
| `my_ui.py:106-118` | `_decode_timing()` / `_decode_usage()`：`Timing` 的 `duration` 是 property（`dict()` 会返回 start/end/duration 三键，只能交两个构造参数）；`TokenUsage.total_tokens` 是 `init=False` 派生，同理只交 input/output | 新增 | V6 |
| `my_ui.py:119-150` | **`encode_memory(steps)`**：`timing→dict()`、`token_usage→{input,output}`、`tool_calls→[tc.dict()]`（OpenAI function 形状，**不是** `asdict`）、`error→{"type","message"}`、`action_output→make_json_serializable`；其余文本字段一律**原样存**——`make_json_serializable`（`utils.py:146-153`）会把长得像 JSON 的**字符串解析成 dict**，回放时观察值就变字了 | 新增 | V6 |
| `my_ui.py:153-211` | **`decode_memory(blob)`**：坏 JSON / `fmt` 不符 / 顶层不是 dict → 返回 `[]`（当作没记忆，不报错）；单条坏了 `except (TypeError, ValueError, AttributeError): continue`，**不连坐**；`PlanningStep` 的 `model_input_messages` / `model_output_message` 无默认值，显式交 `[]` / `None` | 新增 | V6 |
| `my_ui.py:373-400` | `History` 文档改口：v1.5 起这一份**也落库**，重启后选回旧会话模型那一边接着记得；DDL 追加 `CREATE TABLE IF NOT EXISTS memory(session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE, payload TEXT NOT NULL, updated_at REAL NOT NULL)`——**additive**，老库直接多一张表就能用 | 修改 | V6 |
| `my_ui.py:465-478` | `save_memory(sid, payload) -> int`（`INSERT OR REPLACE`，返回字符数）/ `load_memory(sid)` | 新增 | V6 |
| `my_ui.py:507-508` | `OpsUI` 类级 `_run_seq: int = 0` / `_cancelled_before: int = 0`。注释：闸装在**进程唯一**的那个 agent 上，所以计数器必须类级、和 `_pending` 同侧 | 新增 | D7 |
| `my_ui.py:552-572` | **`_gated_call`**：入队与判停在**同一个临界区**里——`with self._gate_lock: self._pending.append(ap); if OpsUI._run_seq <= OpsUI._cancelled_before: ap.decide("cancelled")`。两种到达顺序都被覆盖：闸先拿锁 → `_stop` 的 `_settle_all` 必看得见；`_stop` 先拿锁 → 入队即自判 cancelled。**窗口关死** | 修改 | D7 |
| `my_ui.py:767-778` | `_stream_response`：在计数器归零之后、**起 worker 线程之前**`with self._gate_lock: OpsUI._run_seq += 1`（先领这一轮的号） | 修改 | D7 |
| `my_ui.py:885-912` | `_bind_memory`：进程内 `_mem` 未命中时，`steps = decode_memory(self.hist.load_memory(sid))`，非空则 `mem.steps.extend(steps)`——只回灌 steps，`system_prompt` 与 `monitor` 一律不动 | 修改 | V6 |
| `my_ui.py:980-986` | `_respond` 的 `finally`：`mem = self._mem.get(sid)`，**两个条件**才落库——`mem is not None`（没绑定记忆的一题不去建行）且 `self._mem_sid == sid`（中途换了会话就别把别人的记忆盖到这条上）。收尾时 worker 可能还在跑，所以**半截可接受** | 修改 | V6 |
| `my_ui.py:992-1013` | `_stop`：先 `with self._gate_lock: OpsUI._cancelled_before = OpsUI._run_seq`，再 `_settle_all("cancelled")`，最后 `interrupt()`。docstring 补根因（`agents.py:470` 每轮开头清 `interrupt_switch`） | 修改 | D7 |
| `ai学习/.rollback/v1.5/` | 新增第六套存档（`my_ui.py` + `my_coding_agent.py`），`.rollback/` 共 **12** 份 / **6** 套 | 新增 | 回滚 |

体量：`my_ui.py` **893 → 1,108 行**（44,838 → **55,774 B**，`diff` 净 **`+217 / −2`**）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.4`、`.rollback/v1.5` 双份一致）。上游源码零改动：`git diff --name-only` 行数 **0**；`git status --porcelain` 除三个 untracked 的 `my_*.py` 之外，多出一个**应用自己 22:22 建的** `.agent-history.sqlite3`（40,960 B，未被 `.gitignore` 收掉——本轮结束时它已经存在，见 §4 第 2 条过程问题）。

### 3 新功能怎么用（用户视角）

1. **关掉再开，旧会话还记着**：问「请把数字 73 记住」→ 用桌面的「关闭Agent」收工 → 再双击「我的Agent」→ 在侧栏点那条旧会话 → 问「我刚才让你记住的数字是多少」→ 答 **73**（v1.4 这里答「不记得」）。
2. 工具跑过的结果也在记忆里：`run_python` 打印 `21` → 重启 → 问「刚才那次 run_python 打印出来的结果是什么」→ 答 **21**。
3. **点「＋ 新会话」仍然一无所知**：同一个问题答**「不记得」**，本题 `in` 回到裸起步的 **2,363**。持久化只针对**你已经聊过的那条**。
4. 停止落在待批卡之前也不用再补一刀：按 ■ 停止 → 界面走到**已停止**，不会再卡在「等待审批」等人手动点 ✖（v1.4 实测卡 142.4s）。
5. 被那样取消的工具调用**照样留下痕迹**：卡片是 `⏹ 待批 · run_python · 随停止取消` + `⚪ 已取消`，而且这一段也会进记忆——模型下一轮读到的是「用户按了停止，本次执行已取消，未产生任何副作用」。
6. 要知道的两条边界：① **图片**不进持久化记忆（`images` / `image_outputs` / `model_output_images` 一律不存），重启后带图的观察值不会回到模型上下文；② 停在半截时落的是**那一刻**的 steps，下次接着聊就从那一刻的进度继续。

### 4 上线验收（当场跑过的真实输出）

离线：`/tmp/v15_test.py`（venv python，`_stream_response`/`agent.run` 打桩、临时库）——**65 条断言全 PASS，`FAILS: 无`**。分组：**1 编解码 16 条**（1c 观察值 `{"ok": true, "n": 73}` 逐字保留、1f 恢复后 `type(step.error).__name__ == "AgentParsingError"`、**1n 用框架自己的 `write_memory_to_messages()` 逐字比对回灌前后**、1p 图片字段不入库）；**2 落库/重启 22 条**（2h `_bind_memory` 回灌 4 步、2i 重启前后模型读到的那一串相同、**2l 重启后「本题累计」边界仍 300/13**、2t `DROP` memory 表后老库照常用、2v 未绑定记忆的一题不落库且不崩）；**3 D7 17 条**（3a 标记在先 → 1s 内返回、3c 原工具**零调用**、3d/3d2 `_unanswered()==[]` 且下一轮开局 `_pending.clear()`、3e/3f 未标记时仍老实等人、允许后真执行、**3l 端到端**：真 `_stream_response` ＋ 假 `agent.run`（0.6s 后调 gated 工具），0.2s 按停止 → **3s 内自己结束**、3m 观察值＝取消那句、3o 半截也落库且带 `⏹`）；**4 回归 10 条**（4a `⚪ 已取消` 判定、4b/4d 库里 `status` 合法、4g `outputs` 仍 7/3/4、4h 门没套两层）。

在线（**交付形态** 7860，真 qwen-plus；`/tmp/v15_drive.js`、`/tmp/v15_d7.js`、`/tmp/v15_appr.js`、`/tmp/v15_leg_tool.js` 经 CDP 9333 驱动 headless Chrome；库＝真实的 `smolagents/.agent-history.sqlite3`；重启一律走 `bash ~/Desktop/关闭Agent.command`）：

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| **V6 跨重启·记住** | 进程 1：s1 记住 73 → s2 同会话追问 | `in 2,362` → `in 2,465`，进程 `4,827/34`；库里 `Final answer: 73` |
| **V6 跨重启·真的重启了** | `关闭Agent.command` → 再开 `我的Agent.app`（pid 45372 → 46527 → 49146） | 后端 6~8s 回来，屏幕从库里读回 8 行 |
| **V6 回灌生效** | 进程 2 点侧栏旧会话 → 问「如果你没有这段历史，只回不记得」 | 模型 `Final answer: 73`；**本题 `in 2,574`**（裸起步是 2,363，带上了历史）；进程档从 0 重新计到 `4,937/34` |
| **V6 继续聊** | 同一条再问「再把那个数字回给我一次」 | `Final answer: 73`，`in 2,675`，进程 `7,612/51` |
| **V6 工具观察值也带着** | 进程 2 审批跑 `print(3*7)` → 第二次重启（进程 3）问「刚才 run_python 打印了什么」 | 模型 `Final answer: 21`（`in 3,091`、进程归零 `3,091/17`）。库里那条 ActionStep 的观察值是逐字的 `exit=0`⏎`21` |
| **新会话仍然隔离** | 进程 2 点「＋ 新会话」问同一题 | `Final answer: 不记得`，`in 2,363`、进程 `2,363/17` |
| **审批 + 落库同屏** | 强制 `run_python` 题，卡出来后点 ✔ 允许 | `🟢 待批 · run_python · 已允许` → `第 1 步 · run_python · 🟢 成功 · 272.9s · in 2,909/out 21` → `第 2 步 · final_answer · 🟢 成功 · 0.8s · in 2,987/out 17`；本题 `5,896/38`，进程 `16,289/109` |
| **D7 交付形态复测** | `/tmp/v15_d7.js`：提问后 **0.2s** 按 ■ 停止，观察 30s | `awaitingSeen 0`（**从没进过**「等待审批」）、0.7s `停止中` → **1.2s `已停止`**，此后 26s 轨迹全是 `已停止`；v1.4 同一路是死停 **142.4s** 等手动补 ✖ |
| 停止那一轮也进记忆 | `sqlite3` 直查 payload | session 1 里 `run_python {"code": "print('D7')"}` 的 `observations` ＝ `用户按了停止，本次执行已取消，未产生任何副作用。` |
| 库里形状 | `PRAGMA` + `json.loads(payload)` | 4 张表（`sessions/messages/memory/sqlite_sequence`），`memory(session_id,payload,updated_at)`；首轮 2 问之后 session 1 payload **1,029 字符 / 4 步**（`TaskStep, ActionStep, …`），全部跑完 **4,042 字符 / 15 步** |
| **回滚演练（双向）** | `cp .rollback/v1.4/* → 断言 → cp .rollback/v1.5/* → 断言 → cmp` | v1.4 方向 **15** 条全 PASS（`py_compile`、`import` 起来、行数 893、**没有** `encode_memory`/`MEM_FMT`/memory 表 DDL/`_run_seq`/入队判停、`_stop` 只剩 `_settle_all + interrupt`，而 D5/V5/D6/审批闸全在），v1.5 方向 **13** 条全 PASS，恢复后与 `.rollback/v1.5/` **逐字节一致**，再跑离线 **65 条 `FAILS: 无`** |
| **v1.4 代码读 v1.5 写过的库**（回滚会不会踩到新表） | 拷一份库给 v1.4 的 `History` 读写 ＋ **真启动 v1.4 探测口** | `load(1)` 读出 **12 行**不减、`save()` 正常、`memory` 表**原地留着不碰**；v1.4 代码在 7861 上 `HTTP 200`，日志无 `Traceback` |
| 四条关停判据 | `bash 关闭Agent.command` 后实测 | 7860 监听 **0**、Agent 专用 Chrome（`Application Support/AgentClient`）**0**、`who` 只剩 **console**、System Events `count of windows of process "Terminal"` = **0** |
| 日志零噪声 | `.agent-ui.log`（收工时 15 行 / 1,850 B）`grep -c` 七种模式 | `Traceback` / `Error in callback` / `asyncio.exceptions` / `RuntimeError:` / `gradio.exceptions` / `ClosedClient` / `Event loop` **全 0** |
| 采样粒度不是缺陷 | 驱动器 700ms 粒度，`startWait 60.5` | 与 v1.4 同一现象：**等待超时**，不是真等了 60 秒（0.9s 的单步题抓不到起跑帧） |

**两条要如实记下的过程问题**：① 回滚演练 v1.4 方向**首跑有 1 条 FAIL**，是我那条断言把**字节**当成了**字符**——`len(open().read())` 比 `>40000`，而 v1.4 是 44,838 **B** / 37,365 **字符**（中文注释 3 字节 1 字符）。改成「import 打出的字符数必须等于磁盘文件的字符数」后复跑全绿，顺带把"import 起来的正是磁盘上这一份"钉死。② 本轮开始前我用 `sqlite3.connect` 探测交付库路径时，`connect` 的副作用**建了一个 0 字节**的 `smolagents/.agent-history.sqlite3`（该路径原本不存在），当场按文件名 `rm -f` 撤掉；现在那份是应用自己 22:22 建的（首次 24,576 B），**没有既有用户数据被覆盖**。

### 5 回滚方法

```bash
cp ~/Desktop/study/ai学习/.rollback/v1.4/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.4/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

行为退回：重启后旧会话**答「不记得」**（记忆只在进程里），以及 `■ 停止` 落在待批卡之前**会死停**在「等待审批」。`my_coding_agent.py` 本轮未动，同拷一份只是让存档自洽；上游源码零改动，无需碰 `.venv`。

**数据不会坏**：`memory` 表是 additive 建的，v1.4 的代码不认它——实测拿 v1.4 读写 v1.5 写过的库（`messages` 全在、`save()` 正常、表原地留着），并且 v1.4 直接在那份库上启动成功。回滚**不会**删已有 payload；再升回 v1.5 时旧 payload 照读（`fmt` 不符才降级成"没记忆"）。
**但回滚会把 V6 和 D7 一起重新打开**：重启后又不记得了；停止的竞态也回来了（临时办法仍是再补一刀 ✖ 拒绝）。

### 6 口径与数据变化

1. **记忆档位变了**：`agent.memory` 从「每会话一份、只在进程里」→「每会话一份、**落库**」。库里形式：`{"fmt":"v1","steps":[{…},{…}]}`，一行一个 `session_id`。
2. **存的是字段，不是屏幕文字**：只存 `to_messages()` 读到的那些（清单 `MEM_FIELDS`，`my_ui.py:59-76`）。`model_input_messages`（整段提示词，O(n²)）与图片三兄弟（`images` / `image_outputs` / `model_output_images`）**不存** → **带图的观察值重启后进不了模型上下文**【本轮题面全是纯文本，多图会话【未验证】】。
3. **文本一律原样存**：只有 `action_output` 过 `make_json_serializable`。原因：`utils.py:146-153` 会把**长得像 JSON 的字符串解析成 dict**，回放时观察值就变字了（离线 1c 就是这条的回归断言）。
4. **错误对象是"造"出来的不是"构造"的**：`cls.__new__(cls)` + `Exception.__init__` + 手设 `.message`（`AgentError.__init__(message, logger)` 会当场 `log_error`）。`ToolCall` 存的是 OpenAI function 形状（`tc.dict()`），不是 `asdict`。
5. **坏数据的降级路径**：整块坏 → 当作没有记忆、正常开新会话；单条坏 → 跳过那一条、其余照灌。**不会**因为一次异常把整条会话废掉。
6. **token 口径不变**，但跨重启继续往上：`2,362 → 2,465 →`（重启）`2,574 → 2,675 →`（审批那题两步 `2,909 + 2,987`）`→`（二次重启）`3,091`。裸起步恒为 `2,363`。**进程档每次重启归零**（实测 `2,363/17`、`3,091/17`），这是进程统计的定义，不是 bug。
7. **「本题累计」边界不受回灌影响**：回灌进来的是**上一题**的 steps，本题的累计仍从 0 起算（离线 2l 断言 300/13）。
8. **停止的语义扩了一格**：`■ 停止` 现在覆盖"**本轮之后到达的**待批"。判据是类级 `_run_seq` / `_cancelled_before`（闸装在进程唯一的 agent 上，计数器必须同侧）。被取消的调用**照样写进记忆并落库**，模型下一轮读到"未产生任何副作用"。
9. **审批等待时间计入步骤耗时**（实测 `第 1 步 · run_python · 🟢 成功 · 272.9s`，真执行 ~1s；`本题耗时 273.7s` 同）：v1.3 起就是这口径，本轮**没改**。要不要单列「等待时长」另立 V 单。
10. **体量**：`my_ui.py` **893 → 1,108 行**、**44,838 → 55,774 B**、净 **`+217 / −2`**；`.rollback/` 存档 **10 → 12 份**（6 套）。

### 7 已知遗留（下次的输入）

- **侧栏选中态陈旧（v1.4 那条遗留本轮造成了真后果）【建议立 V7】**：点「＋ 新会话」之后，radio 仍保留**上一次**的 `checked`。于是"点那条**高亮着的**旧会话"＝点了一个值没变的 radio → **不触发 change** → 问题落进了新会话（探测口实测：`in 2,463`、答「不记得」，数据没坏、只是进错了门）。反证：`/tmp/v15_leg.js` 每次点击前先读 `before-checked`，`before-checked=0` 时点击一切正常（`checked#1`、屏上换回 6 行、答 **73**）。**本轮范围外，我没擅自改**；修法一句话：`_new_session` 把 radio 的值同步成那条新会话（纯界面层）。
- **半截落库**：worker 可能还在跑时收尾，落的是**那一刻**的 steps（`_respond` 的 `finally`）。下次接着聊从那一刻的进度继续，不影响正确性，但**停在待批上的那一轮**记忆里有 `TaskStep` 而无对应 `ActionStep`——这与 v1.4 的停止语义一致。
- **并发提问共用一个 agent（且取消号是全局的）**：`_cancelled_before` 是**类级**，一个标签按停止会让**所有**在飞的待批按 `cancelled` 结算【未验证：本轮始终一次一题】。当前设计仍假设**一次只问一题**。
- **带图观察值不进持久记忆**（§6.2）；**多工具并行只处理最早一条**（v1.3 就在，本轮未动）。
- **验收脚本还在 `/tmp`**：本轮新增 `v15_test.py`、`v15_ui.py`、`v15_drive.js`、`v15_d7.js`、`v15_leg.js`、`v15_leg_tool.js`、`v15_appr.js`、`v15_appr2.js`、`v15_rollback_check.py`——macOS 一重启这些"复跑命令"就失效，只剩本记录里的输出。v1.0~v1.5 六轮都是这个状态。**要不要在 `ai学习/` 下开一个 `验收脚本/`（按版本号分目录）收进来，仍然等你点头**（属于新增目录，不在本轮 V6+D7 范围内）。
- 仍欠你的点头：dify Docker Compose（#5）、MCP servers `npm ci`（#6）、**百炼 Key 轮换**、`gradio_ui.py:456` 的 `.capitalize()`、D2（staging 副本读不回来）、P0-4。

**推荐下一刀 v1.6 = V7（侧栏选中态同步，一句话改动、真后果）+ 把 `run_python` 的审批等待时长从步骤耗时里单列出来**；P0-4（计划可见）继续往后排。

---

## v1.4 · 2026-10-29 · 连问不再吞前一题 + 会话级记忆隔离（D5 + V5，顺带修 D6）

### 1 这次解决什么（为什么现在做）

范围按工单号锁定 **D5 + V5**（`my_coding_agent.py`、`my_agent.py`、上游源码零改动；审批闸与步骤卡一行未碰）。看板给 D5 的定位是「唯一会丢用户内容的一条」。

- **D5**：同一个页面连问两题、不点「＋ 新会话」，**前一题从屏上和历史库里双双消失**。三处叠加：① `_respond()` 每一轮都从 `last = [user_msg] + msgs` 起，chatbot 的输出是**整体替换**；② `History.save()` 是 `DELETE FROM messages WHERE session_id=?` 的**整条覆盖**，只有调用方喂进完整列表时才等价于追加；③ `sid` 同时挂在 `box.submit` 的 inputs 和 outputs 上，所以第二轮**沿用同一条会话**。v1.3 的实测：连问两题后 `sessions` 只新增 **1** 条（标题仍是**第一题**），`messages` 里只剩**第二题**那 3 行——第一题的 3 行被覆盖掉了。
- **V5**：点侧栏的旧会话只换屏上的字，不换 `agent.memory`（v1.3 是**进程级一份**）。于是「屏上看着接上了，模型那边其实是开局」。v1.3 的 `_select_session` 注释里就写着这条：想接着旧话题问，得先做会话级记忆隔离。
- **为什么同一批**：D5 的两条修法里「消息跨题累加」与 V5 是**同一件事的两面**——屏上累加 + 记忆里累加。只做屏上，第二条提问仍会开一条新会话（v1.3 就是这个形态）；只做记忆，屏上还是会把前一题抹掉。
- **顺带一条 D6**：修 V5 的刷新路径（`_on_load` 要把 `sid` 指到侧栏排第一的那条）时，发现侧栏的 `updated_at` 排序**从 v1.2 起就是失真的**——`History.save()` 那条 UPDATE 挂着 `WHERE title='新会话'`，会话一旦有了标题就再也不刷新时间。以前只影响"刷新页面看到哪条"，现在决定了"下一条提问落进哪条"，顺序错了等于问错地方，所以一起修掉。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:26` | import 多带一个 `AgentMemory`（`smolagents.memory`，类定义在 `memory.py:214-232`） | 修改 | V5 |
| `my_ui.py:214-219` | `History` 的文档改口：`save()` 是整条覆盖、只有喂完整列表才等价于追加（D5 修的就是这个前提）；v1.4 起记忆按会话各存一份，**但只在进程里** | 修改 | D5 / V5 |
| `my_ui.py:291-298` | `save()` 的 `UPDATE sessions` 改成**每次刷 `updated_at`**，标题用 `CASE WHEN title='新会话' THEN ? ELSE title END` 保护 | 修改 | D6 |
| `my_ui.py:335-338` | `__init__` 加 `self._mem: dict[int, AgentMemory] = {}` 与 `self._mem_sid: int \| None = None`（会话 id → 那份记忆；不落库） | 新增 | V5 |
| `my_ui.py:689-709` | **`_bind_memory(sid)`**：把 `agent.memory` 换成这条会话自己的那份。只换引用——`reset=False` 时框架会把新任务**追加**进 `self.memory`（`gradio_ui.py:310` 的默认、`agents.py:477` 顺手同步 system_prompt），所以"谁的记忆"＝"起 worker 那一刻 `self.memory` 指向谁"。刻意不传 `reset=True`（那会连 `monitor` 一起清零，`agents.py:478-480`，「进程累计」口径就废了），也刻意不在跑到一半换（worker 正在读 `self.memory.steps`） | 新增 | V5 |
| `my_ui.py:730-737` | `_respond`：`ensure(sid)` 之后立刻 `_bind_memory(sid)`；起点改成 `base = self.hist.load(sid)` + 本题 user 消息 | 修改 | D5 / V5 |
| `my_ui.py:746-747` | 流式每一帧 `last = base + [user_msg] + list(msgs)`（v1.3 是 `[user_msg] + list(msgs)`） | 修改 | D5 |
| `my_ui.py:799-808` | `_select_session` 交出**第三个值 `int(sid)`**：点旧会话连 State 一起换，下一条提问才落在这条会话上 | 修改 | V5 |
| `my_ui.py:810-820` | `_on_load` 从闭包提成**方法**（可离线测），并把 `sid` 指到侧栏第一条（最近有动作的那条）；空着 `sid` 的话下一条提问另开一条，刚看到的那串字就被整体替换抹掉——D5 的另一条路径 | 修改 | D5 / V5 |
| `my_ui.py:872-873` | `radio.change` 的 `outputs` 多带 `sid` | 修改 | V5 |
| `my_ui.py:880` | `demo.load(fn=self._on_load, ...)` | 修改 | V5 |
| `ai学习/.rollback/v1.4/` | 新增第五套存档（`my_ui.py` + `my_coding_agent.py`），`.rollback/` 共 **10** 份 | 新增 | 回滚 |
| `ai学习/README.md` §6.3.6 | 新增一节「v1.4：屏上的消息列表和 `agent.memory` 都按会话走」：换起点 / 换引用两个动作、为什么刻意不 `reset=True`、刷新与侧栏选中态三条边界，含 1 张新增 flowchart（第 **22** 块 mermaid） | 新增 | D5 / V5 |
| `ai学习/README.md` §8 | 新增一块 Gherkin「功能: 会话连续与记忆隔离」**7 条场景**（连问累加 / 新会话不记得 / 点旧会话接着聊 / 刷新落到最近一条 / 半截也落库 / 记忆只在进程里 / 回滚会重开 D5） | 新增 | D5 / V5 |
| `ai学习/README.md` §9.1 | 加 **35~40** 六行（`agents.py:477` 与 `:478-480`、`memory.py:214-232`、`gradio_ui.py:310`+`:389`、`my_ui.py:735`/`:747`、`:808`/`:873`/`:820`/`:880`、`:291-298`）；§9.2 术语表补「动作空间 7 vs 8」口径行 | 新增 | — |
| `ai学习/README.md` §9.4 + 全篇行号 | §9.4 加第 **9、10** 条【待补】（记忆持久化 / D7 只在探测口复现；累加只测到三问一答）；**72 对**锚点从 v1.3 位置一次性搬到 v1.4（每对唯一匹配，无残留）。README 现 **1,166 行 / 90,426 B / 22 块 mermaid** | 修改 | — |
| `ai学习/agent功能手册.html` | 按本节重生成视图：§2 标题与体量（893 / 44,838 B / 10 份存档）、§2.5 新增三行（连问累加 D5、会话级记忆隔离 V5、历史落库排序 D6）+ 全篇行号刷新、§4 看板 **30 → 33 条**（D5/V5 转 `已上线 v1.4`，新立 **D6 已修 / D7 未修 / V6 记忆持久化**）、§4.5 推荐卡换成 **v1.5 = V6 + D7**、§5.1 五套存档、§7 新增六条待补、§6 插入 **6.1 v1.4** 并把 v1.3→6.2、v1.2→6.3、v1.1→6.4、v1.0→6.5 顺移（含 §6.2 内部两处 `§6.1` 引用跟随）。**120,390 → 155,708 B（847 → 984 行）** | 修改 | — |

体量：`my_ui.py` **850 → 893 行**（41,871 → **44,838 B**，`diff` 净 **`+70 / −27`**）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.3`、`.rollback/v1.4` 双份存档逐字节一致）。
落盘后最后一次改动是**注释里的上游行号**（`agents.py:476` → `:477`、`:477-480` → `:478-480`，实测 `agents.py:476` 是空行），行数与字节数不变，已重新 `cp` 进 `.rollback/v1.4/` 并 `cmp` 确认，改后重跑：离线 53 条断言 + 探测口连问两题（见 §4 的「改注释后复跑」那行）。

### 3 新功能怎么用（用户视角）

1. **连问不用点「＋ 新会话」**：问完第一题直接问第二题，屏上两问两答**都在**，侧栏仍只有**一条**会话（标题是最早那题）。
2. 第一题「请把数字 73 记住」，第二题「我刚才让你记住的数字是多少」→ 答 **73**（v1.3 这里会把第一题整条吞掉）。
3. 点**「＋ 新会话」** → 屏上清空，同样的问题答**「不记得」**：新会话不只是"新页面"，是**另一段记忆**。
4. **点侧栏的旧会话** → 屏上回到那条对话，接着问就接在它的下文里（v1.3 是"屏上像接上了、其实另开一条"）。
5. **刷新页面 / 重开应用** → 侧栏列出历次会话（按最近有动作排），屏上自动回到**最近一条**，直接接着问就落在这条里。
6. 审批照常：累加之后，待批卡和步骤卡排在旧消息**下面**，旧的一条不丢。
7. 要知道的边界：**重启进程后**旧会话的字还在屏上（库里读出来的），但那道题模型答**「不记得」**——记忆只在进程里，见 §7 第 1 条。

### 4 上线验收（当场跑过的真实输出）

离线：`/tmp/v14_test.py`（venv python，`_stream_response` 打桩、临时库、`TokenUsage` 逐题造数）——**53 条断言全 PASS，`FAILS: 无`**。分组：0 安装门没被碰坏 / 1·2 D5 累加（屏上行数、库里行数、`sid` 不变）/ 3 记忆隔离（两份 `AgentMemory` 互不串）/ 4 切会话绑定 / 5 审批闸幂等 / 6 卡片 / 6a 库里 `status` 合法（D4 没回潮）/ 7 刷新路径 / 8 侧栏排序（D6）/ 9 停止的半截也落库 / 10 一步都没跑也不吞历史。

在线（探测口 7861，真 qwen-plus，`/tmp/v14_drive.js` CDP 驱动，库 `/tmp/v14-live-hist.sqlite3`）：

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| **D5 屏上累加** | s1 首问 → s2 同会话第二问 | 屏上 **4** 行（两问两答都在），卡片 `第 1 步 … in 2,362` + `第 1 步 … in 2,464`；模型 `Final answer: 73` |
| **D5 库里累加** | `sqlite3` 直查 | `session 1` 一路长到 **26 行**、标题仍是第一题；`session 2`（新会话）**3 行** |
| **V5 新会话隔离** | s3：点「＋ 新会话」后问同一题 | 模型 `Final answer: 不记得`；本题 `in 2,363`（回到裸起步，没带上文的 100 个 token） |
| **V5 点旧会话接着聊** | s4：侧栏选中 73 那条 → 第三问 | 屏上回到那条的两问两答，第三问的卡 `第 1 步 · final_answer · 🟢 成功 · 0.8s · in 2,564/out 17`（历史越问越厚） |
| **审批 + 累加同屏** | s5：`run_python` 强制题，点 ✔ 允许（`12:19:40.096Z`） | 待批卡出现时屏上**已有 3 张旧步骤卡**；允许后 `🟢 待批 · run_python · 已允许` + `第 1 步 · run_python · 🟢 成功 · 1.5s · in 2,672/out 21` + `第 2 步 · final_answer · 🟢 成功 · 0.8s · in 2,751/out 17`；本题累计 `in 5,423` = 2,672+2,751 |
| **交付形态跑的确实是 v1.4** | `我的Agent.app` → 7860，`V14URL=…:7860` 跑 s1,s2 | `s1 in 2,362` → `s2 in 2,465`、进程 `in 4,827`，屏上两问两答都在 |
| 侧栏选中态 | `__v14.selChecked()` 读 `#sessions input` 的 `checked` | 交出 `sid` 后 `selChecked` 仍是 `"0"` —— **屏和内容接上了、侧栏高亮没跟**，记进 §7（纯界面层） |
| **D6** | 离线 8a/8b/8c/8d/8e | 两条新会话；最新动作那条排第一；**老会话一有动作就回到第一**（v1.2 起的 `WHERE` 条件会漏刷）；后续问题不改标题；空列表 `save()` 不会把标题写成 `NULL` |
| 刷新路径 | 离线 7a/7b/7c | 重载后 `sid` 指向最近一条、屏上是那条会话的**全部三问**、刷新后接着问**不会另开一条** |
| 停止的半截 | 离线 9a~9e、10a/10b | 半截也落库且**前几轮还在**；`⏹` 气泡 `status=done`；状态档=已停止；`sid` 不变；记忆里只多半截（`TaskStep` 进了、`ActionStep` 没进）；一步都没跑也不吞历史 |
| 采样粒度不是缺陷 | `/tmp/v14_state.js` 页内 120ms 采样 | 空闲 121ms → 生成中 722→8,160ms → 完成；驱动器 700ms 粒度抓不到 0.9s 的单步题（`startWait 60.5` 是**等待超时**，不是真等了 60 秒） |
| **记忆只在进程里**（量 §7 第 1 条） | 重启探测口 → 选旧会话问「最早让你记住的数字」 | 屏上 4 行历史都在，模型 `Final answer: 不记得`；框架日志 `Step 3: Input tokens 9,015`（−5,631 = 本题 **3,384**，没有带上会话历史） |
| **D7 复现 + 恢复** | `/tmp/v14_d7.js`（提问后 0.2s 按 ■ 停止）→ `/tmp/v14_d7fix.js`（不刷新，补点 ✖ 拒绝） | 停止落在待批卡**之前**：那一按等于空放，后到的待批无人结算，界面死停 `状态/等待审批` + 胶囊 `待批/run_python`，✔/✖ 一直挂着；挂了 **142.4s**（`APPROVAL_TIMEOUT` 是 600s，不会自己解）。补点 ✖ 拒绝后 0.0s 解开：`⚪ 待批 · run_python · 已拒绝` → `第 1 步 · run_python · ⚪ 已拒绝 · 142.4s · in 2,690/out 20` → `⏹ 已停止：AgentError`，状态 `已停止`。对照组（2.0s 按停止，卡在屏上）：0.5s 内 `⏹ … 随停止取消` + `⚪ 已取消` + `已停止`，按钮收成一枚。**无数据丢失**（库里 14 行、`⏹ AgentError` 气泡也落库） |
| 日志零噪声 | `/tmp/v14b-live.log` `grep -c` 七种模式 | `literal_error` / `ValidationError` / `ComponentProcessingError` / `Exception ignored` / `gradio.live` / `Traceback` / `TypeError` **全 0** |
| 四条关停判据 | `bash ~/Desktop/关闭Agent.command` 后实测 | 7860 监听 **0**、Agent 专用 Chrome（`user-data-dir=…AgentClient`）**0**、`who` 只剩 **console**、System Events `count of windows of process "Terminal"` = **0**、日志 `gradio.live` / `Exception ignored` **0** |
| 回滚演练（**双向**） | `cp .rollback/v1.3/* → 断言 → cp .rollback/v1.4/* → 断言 → cmp` | v1.3 方向 10 条全 PASS：`py_compile`、`import my_ui` 后能构造 `create_app`、行数 **850 / 41,871 B**、**没有** `_bind_memory`/`_mem_sid`/`AgentMemory`、`_respond` 仍从 `[user_msg]` 起、`radio.change` 只有两个输出、`_on_load` 是闭包且交 `None`、`save()` 的 UPDATE 仍带 `WHERE title='新会话'`、v1.3 的审批闸还在。v1.4 方向 10 条全 PASS（行数 **893 / 44,838 B**，以上全反），恢复后与存档**逐字节一致** |
| **改注释后复跑**（最后一刀是行号引用） | 重启探测口（库换 `/tmp/v14b-live-hist.sqlite3`）跑 s1,s2 | `s1 in 2,362` → `s2 in 2,462`、进程 `in 4,824`，模型 `Final answer: 73`；库里 **1 条会话 / 6 行**（两问两答），`rowid` 从 **4** 起——`save()` 是覆盖式重插，顺序看 `ord` 不看 `rowid` |
| **回写后的两道闸**（本轮最后一步） | ① mermaid 闸：`python3 /tmp/mmd_extract.py README.md` → `bash /tmp/mmd_run2.sh`（headless Chrome 逐块渲染，`svg.length > 800` 才算过）② 手册静态自检：`python3 /tmp/v13_htmlcheck.py` | ① `TOTAL 22 BAD 0`，22 块逐块 `RENDER-OK`（14 flowchart + 5 sequenceDiagram + 2 stateDiagram + 1 classDiagram，svg 长度 15,706~57,236）；**负控**给第 20 块追加一行 `X1 -->] 负控破坏行` → `TOTAL 22 BAD 1`，从 README 重抽后回到 `BAD 0`；② 标签配对错误 **0**、未闭合 **0**、外部资源 **0**（仍离线自包含）、死锚点 **[]**，看板 33 行 / 正文 24 张表 |
| **看板筛选器浏览器实点** | `/tmp/v14_board.js`：CDP 9333 驱动 headless Chrome 打开 `file://…/agent功能手册.html`，十枚筛选器逐个 `click()`，每次同时读 `#cnt` 文案与页内 `offsetParent !== null` 的真实可见行数；`/tmp/v14_wide.js` 量正文宽度 | 十档**全部相符**：`all 33/33`、`bug 7`、`p0 5`、`p1 8`、`p2 7`、`v 6`、`todo 17`、`doing 0`、`done 13`、`na 3`；`data-st` 分布 `{done:13, na:3, todo:17}`；状态胶囊逐条读到 `D5 已上线 v1.4`、`D6 已上线 v1.4`、`D7 未开工（v1.4 新立）`、`V5 已上线 v1.4（进程内）`、`V6 未开工（v1.4 新立）`；`document.title` 已是 `— v1.4`；§6 六节顺移到位（6.1 v1.4 … 6.5 v1.0）；`.bar` 仍 `flex-wrap: wrap`；截图 `/tmp/v14-board.png`。**宽度这一栏本轮真的抓到过一次回归**：§7 新增那条【待补】把八个 `/tmp/...` 路径串在同一行里，`scrollWidth` 从 1425 顶到 **1679**（横向溢出）；拆成嵌套 `<ul>` 每行两个 `<code>` 后回到 **1425 = clientWidth**、宽元素候选 **0**。**结论：`overflowX` 必须在每次改完 HTML 后实测，不能只看筛选器** |

### 5 回滚方法

```bash
cp ~/Desktop/study/ai学习/.rollback/v1.3/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.3/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

行为退回"连问两题会吞掉前一题、点旧会话只换屏不换记忆、刷新页面 `sid` 空着"。`my_coding_agent.py` 本轮未动，同拷一份只是让存档自洽。上游源码零改动，无需碰 `.venv`。会话库**表结构未变**，v1.4 累加出来的历史在 v1.3 下照样读得出来。
**但回滚会把 D5 重新打开**：v1.3 的 `save()` 是"整条覆盖 + 起点只留本题"，所以回滚后在同一条会话里再问一题，就会把 v1.4 攒下来的那串**覆盖掉**。回滚后要么每题先点「＋ 新会话」，要么先备份 `.agent-history.sqlite3`。

### 6 口径与数据变化

1. **屏上消息列表**：每一题从**库里那一串**起（`base + 本题 user + 本轮流式输出`）。chatbot 仍是**整体替换**，但替换的内容包含历史——所以"累加"是靠起点变了，不是靠 chatbot 变。
2. **`agent.memory`：进程级一份 → 每会话一份**（`_mem[sid]`）。切会话只换引用，**从不 `reset()`**；`AgentMemory` 不落库（`memory.py:214-232` 没有 (de)serializer）。
3. **行为语义变了（显式声明三处）**：① 点侧栏旧会话＝接着这条聊（v1.3＝另开一条）；② 刷新页面＝回到最近一条且 `sid` 一起指过去（v1.3＝`sid` 空，下一题另开）；③ `History.save()` 每次刷 `updated_at`（v1.3＝只有标题为「新会话」时才刷）。
4. **token 三档口径不变**（本步 / 本题累计 / 进程累计），但**同会话内每题的 `in` 会往上走**：模型每次收到整段会话历史。实测 `2,362 → 2,464 → 2,564`（每题 **+约 100**，等于上一题的一问一答）；点「＋ 新会话」回到 **2,363**。这是记忆隔离的**代价**，不是 bug。
5. **进程累计不变**（`monitor` 不被 reset）：s5 收尾时进程 `in 15,176 / out 106` ＝ 五问之和；本题 `in 5,423`（＝2,672+2,751，`run_python` 那一步 + `final_answer` 那一步）。
6. **交付形态同口径**：7860 上 s1→s2 的 `in` 是 `2,362 → 2,465`（与探测口的 2,464 差 1，属模型侧浮动，不是口径差）。
7. **`History` 的写法语义没变**（仍是整条覆盖），变的是**调用方喂的是完整列表**——所以"覆盖"第一次真正等价于"追加"。副作用：`messages.rowid` 每轮跳号（实测 `1,2,3 → 4..9`，重启后那一段到 `20..33`），**排序与去重一律看 `ord`，别看 `rowid`**。
8. **侧栏排序看得到真动作了**（D6）：`ORDER BY updated_at DESC` 从"只在标题还是『新会话』时刷新"变成"每次 `save()` 都刷"。离线 8c 就是这条的正向断言。
9. **审批、步骤卡、状态条档位：零改动**，v1.3 的七态、`🟢/⚪/🔴` 三档判定、600s 超时语义原样。
10. **体量**：`my_ui.py` **850 → 893 行**、**41,871 → 44,838 B**、净 **`+70 / −27`**；`.rollback/` 存档 **8 → 10 份**。

### 7 已知遗留（下次的输入）

- **记忆只在进程里【待补】**：重启后旧会话的字还在（从库里读），但模型答「不记得」（实测 `in 3,384`、`Final answer: 不记得`）。这是 V5 的**第二半**：要么把 `AgentMemory` 序列化进 SQLite（框架没有 (de)serializer），要么每轮从库里把对话重放成 `TaskStep`/`ActionStep` 灌回去。后者要重定"本题累计"的边界，且 `in` 会随历史线性涨——**需要设计，不是界面活**。
- **D7（本轮复现并定位，未修）**：`■ 停止` 落在待批卡**出现之前**（实测 0.2s 那一下）＝空放——`agents.py:470` 在新 run 开头把 `interrupt_switch` 清回 `False`，所以那一按中断的是**空闲的** agent；随后到的那条待批没人结算，界面死停在 `等待审批`，直到有人点 ✔/✖ 或 600s 超时（实测挂 142.4s，我手动补 ✖ 拒绝才解开）。无数据丢失（那一轮照样落库）。**临时办法**：再点一次 ✖ 拒绝或 ■ 停止。修法两条：闸在入队前先查 `_abandoned`，或 `_stop` 给本轮 `run_id` 打取消标记、入队时看到标记直接按 `cancelled` 结算。
- **侧栏选中态与 `sid` 不同步**：`_select_session`/`_on_load` 交出 `sid` 后，`#sessions input` 的 `checked` 实测仍是 `0`——屏和内容接上了，**高亮没跟**。纯界面层（V 类）。
- **并发提问共用一个 agent**（v1.3 就在，本轮更明显）：`_mem_sid` 也是**单值**，两个标签同时问会互相抢"当前绑到哪条会话"，`monitor` 同样共享。当前设计仍假设**一次只问一题**。
- **多工具并行只处理最早一条**（v1.3 就在）：一步里多个调用时 `agents.py:1361-1437` 走 `ThreadPoolExecutor`，队列里同时躺多条待批，✔/✖ 只对最早那条生效【未验证：本轮题面全是单工具调用】。
- **`生成中` 胶囊在 0.9s 的单步题上抓不到**：驱动器 700ms 粒度（页内 120ms 采样证明状态确实闪过）。不是产品缺陷，是**测试工具的粒度**，下次给驱动器加页内事件缓冲。
- **验收脚本还躺在 `/tmp`**：本节的复跑命令（`/tmp/v14_test.py`、`/tmp/v14_drive.js`、`/tmp/v14_board.js`、`/tmp/v14_state.js`、`/tmp/v14_d7.js`、`/tmp/v14_d7fix.js`、`/tmp/v14_rollback_check.py`、`/tmp/v13_htmlcheck.py`、`/tmp/mmd_*`）没有进语料，**macOS 重启或 /tmp 清理后这些"复跑命令"就失效**，只剩记录里的输出。v1.0~v1.4 五轮都是这个状态。**要不要在 `ai学习/` 下开一个 `验收脚本/`（按版本号分目录）把这些收进来，等你点头**——它属于新增目录，不在本轮 D5+V5 范围内。
- 仍欠你的点头：dify Docker Compose（#5）、MCP servers `npm ci`（#6）、**百炼 Key 轮换**、`gradio_ui.py:456` 的 `.capitalize()`、D2（staging 副本读不回来）、P0-4、**D7**、**记忆持久化**。

**推荐下一刀 v1.5 = 记忆持久化（V5 的第二半：把旧会话的对话重放回 `agent.memory`，重启后也记得）+ D7 一并修**（它只是闸入队前少查了一个标志，几十行）。P0-4（计划可见）继续往后排。

---

## v1.3 · 2026-10-29 · 步骤卡片化 + 工具执行前审批（V4 + P0-2）

### 1 这次解决什么（为什么现在做）

范围按工单号锁定 **V4 + P0-2**，其余一律未动（`my_coding_agent.py`、`my_agent.py`、上游源码零改动）。

- **V4**：v1.2 的消息流里，一步是 gradio 默认拼出的**三张**折叠卡（🛠️ 工具调用 / 📝 执行日志 / 📊 统计），彼此长得一样，**没有状态色**——跑挂的那一步和成功的那一步在屏幕上没有区别，得点开读正文才知道。
- **P0-2**：`run_python` **不问就跑**。唯一的拦阻是 `my_coding_agent.py:165` 那条正则黑名单（禁 `rmtree/socket/urllib/requests/subprocess`），它拦得住"删库"，拦不住"往你磁盘上写文件"；`write_file` 也只是靠 staging 目录**变相**审批——它不给 diff，而是自己造了个"要你自己 `cp`"的流程。
- **为什么同一批**：审批的 UI 正好也要落在这同一片消息流上，先卡片化再挂审批卡，比反过来省一次重写。
- **看板那句"需要设计"指的是什么**：阻塞式审批与流式生成器怎么共存。答案是**不能共存**——gradio 的生成器是被前端**同步推**着走的，生成器里 `event.wait()` 会把整条事件循环卡住（页面连状态条都不刷新）。所以这一步的执行模型必须换：agent 进线程，UI 只轮询队列。见 §6 口径第 1 条。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:32` | `GATED_TOOLS = ("write_file", "run_python")`：**只拦会动东西的两只手**，三个只读工具不弹审批 | 新增 | P0-2 |
| `my_ui.py:34-49` | `APPROVAL_TIMEOUT=600.0` / `DECISION_LABEL` / `DECISION_DOT` / `DENIED_OBSERVATION` / `DENIED_VERDICT`：审批的五种终局、各自的文案、以及交回模型的观察值 | 新增 | P0-2 |
| `my_ui.py:106-115` | `DARK_CSS` 追加：允许键实底绿 `#238636`、拒绝键描边红、待批态文字黄 `#d29922` | 修改 | P0-2 / V4 |
| `my_ui.py:174-181` | `STATE_LABEL` 多一档 `awaiting:"等待审批"`（七态） | 修改 | P0-2 |
| `my_ui.py:185-211` | `class Approval`：`uuid` + `created` + `threading.Event` + `decision`，`wait()` 带超时并把 `timeout` 落进 `decision` | 新增 | P0-2 |
| `my_ui.py:319-320` | `_pending: list` 与 `_gate_lock` 挂在**类**上：闸装在进程唯一的 agent 上，队列也必须是类级；实例级会导致第二次 `OpsUI()` 的队列和闸不是同一个（踩过：审批永远等不到答案） | 新增 | P0-2 |
| `my_ui.py:335-358` | `_install_gate()`：`copy.copy(tool)` 后**只覆盖实例属性 `forward`**（`tools.py:231-249` 的 `__call__` 末行就是 `self.forward(...)`），`__signature__` 手工保留，`_opsui_gated` 标记做幂等 | 新增 | P0-2 |
| `my_ui.py:360-372` | `_gated_call()`：`bind_partial` 出参数 → 入队 → `wait()` → 只有 `allowed` 才调原 `forward`，否则返回观察值 | 新增 | P0-2 |
| `my_ui.py:374-396` | `_pending_snapshot()` / `_unanswered()` / `_decide()` / `_settle_all()` | 新增 | P0-2 |
| `my_ui.py:398-421` | `_approval_card()`：标题 `🟡 待批 · 工具 · 等待审批`，正文是**工具名 + 完整参数**（`_fence` 围栏按正文里最长反引号串升级） | 新增 | P0-2 / V4 |
| `my_ui.py:423-441` | `_fence()` / `_args_text()`（参数超 1,200 字符截断并写明原长） | 新增 | V4 |
| `my_ui.py:443-493` | **`_step_card()`（V4 的主体）**：一步一张卡，标题 `🛠 第 N 步 · 工具 · 判定 · 耗时 · in/out`，判定三档 `🟢 成功 / ⚪ 已拒绝·已取消·超时未批 / 🔴 报错`（`border_left` 同色）；正文四段：模型思考 / 调用+参数 / 结果 / 本步+本题累计 | 新增 | V4 |
| `my_ui.py:495-521` `_stats_message()` | **删除**：v1.1 那张 📊 独立统计卡取消，数字并进步骤卡标题与正文（一张卡一件事） | 删除 | V4 |
| `my_ui.py:522-542` | `_status_html()`：多一颗**「待批」胶囊**（显示被拦的工具名），`st-awaiting` 类名驱动配色 | 修改 | P0-2 |
| `my_ui.py:543-566` | **`_worker()`**：`agent.run(stream=True)` 搬到线程，事件塞进 `queue.Queue`；`_abandoned` 置位就退出；生成器在**它自己的线程**里 `close()` | 新增 | P0-2 |
| `my_ui.py:568-697` | `_stream_response()` **重写**：不再调 `super()`；起线程 → `q.get(timeout=0.25)` 轮询 → 步骤到达摘掉流式泡、换步骤卡 → 审批卡循环（**存对象不存下标**，原地改 `content/metadata`；出卡与更新走同一套收尾判定才摘单）；`finally` 里 `settle_all("cancelled")` + `interrupt()` | 重写 | V4 / P0-2 |
| `my_ui.py:699-744` | `_respond()`：产出 **7 元组**（多了允许、拒绝两键）；`unanswered` 决定按钮可见性与状态条档位；**D4 修复点**：收尾气泡 `metadata.status` 由 `"complete"` 改 `"done"` | 修改 | P0-2 / D4 |
| `my_ui.py:750-763` | `_stop()`：**先 `_settle_all("cancelled")` 再 `interrupt()`**——待批不结算，worker 会永远等在 `Event.wait()` 上 | 修改 | P0-2 |
| `my_ui.py:789-790` `:820-828` | `create_app()`：状态行插入两枚按钮（`elem_id="approve-btn"` / `"deny-btn"`，`visible=False` 起步）；`.click` 只改 decision + 收起自己，**不碰 chatbot**（那条流独占消息列表） | 修改 | P0-2 |
| `ai学习/.rollback/v1.3/` | 新增第四套存档（`my_ui.py` + `my_coding_agent.py`） | 新增 | 回滚 |
| `ai学习/README.md` §6.3 | 新增 **§6.3.5**：审批闸（实例盖 `forward`）+ 线程驱动 + 卡片自绘的实现要点，含 1 张新增 flowchart（第 **21** 块）；§6.3.4 的换壳图重画成现状（含门与 7 元组输出） | 修改 | — |
| `ai学习/README.md` §9.1 | 加 **30~34** 五行（`tools.py:231-249`、`agents.py:1361-1437`、`chatbot.py:55`、`my_ui.py:543-566`/`:568-697`、`DENIED_*` 两字典必须同步）；第 25、29 两行的行号跟随代码刷新 | 修改 | — |
| `ai学习/README.md` 全篇行号 | 一次性把 v1.2 留下的过期行号搬到 v1.3 现状：§1.3 架构图三处、`:74`、§6.3.1 图（`:454/:455-457/:462` → `:842/:843-847/:850`）、§6.3.2 刹车图（`306-323` → `568-697` + 新增 `_worker` 参与者）、§6.3.3 import 行、§6.3.4 四条实现点与 `History` 表、`DARK_CSS :19-127` → `:53-172` | 修改 | — |
| `ai学习/README.md` §8 + §9.4 | 新增一块 Gherkin（审批五条场景：允许 / 没执行的三种说法 / 只读不问 / 命令行不过闸 / 一步一张卡）；§9.4 加第 **8** 条【待补】 | 修改 | — |
| `ai学习/agent功能手册.html` | §2 标题→v1.3、§2.1 体量与 8 份存档（6 → 8）、§2.5 加步骤卡/审批卡/审批键三行、§4 看板 **P0-2 与 V4 转「已上线 v1.3」**、缺陷组加 **D4（已修）/ D5（新发现）**、推荐卡换 v1.4、§6.1 抄本节（v1.2→6.2、v1.1→6.3、v1.0→6.4） | 修改 | — |

`my_ui.py` 462 → **850 行**（22,562 → **41,871 B**，`diff` 净 `+432 / -44`）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.2`、`.rollback/v1.3` 双份存档逐字节一致）。

### 3 新功能怎么用（用户视角）

1. 双击 `我的Agent`。提问后，每一步是**一张**卡：标题一行读完 `🛠 第 1 步 · grep_files · 🟢 成功 · 1.6s · in 2,632/out 39`；成功绿、报错红（左边框同色）、被拦下是灰点。
2. 一旦模型要 `run_python` 或 `write_file`，屏上先出**一张黄色待批卡**：里面写着工具名和**完整参数**（代码全文），同时状态条右侧亮起 **「✔ 允许」「✖ 拒绝」** 两枚键，状态胶囊变**「等待审批」**，并多一颗「待批 · run_python」胶囊。
3. 点**允许**：工具执行，待批卡变 `🟢 … 已允许`，步骤卡正常出结果；点**拒绝**：工具**不执行**，步骤卡 `⚪ 已拒绝`，模型收到"未产生任何副作用"，通常会改用只读工具或直接交结论。
4. **■ 停止在待批时也管用了**：点停止等于拒绝所有待批，卡片写 `⏹ … 随停止取消` + 步骤卡 `⚪ 已取消`，不会出现"按了停止但线程还等着审批"的僵死。
5. 只读工具（`read_file` / `list_dir` / `grep_files`）**不弹审批**——检索三连问不用点三遍。
6. 一直不点：600 秒后自动按拒绝处理（`⏳ 超时未批`），题可以重问，但线程不会永远挂着。
7. 命令行路径（`python my_coding_agent.py "…"`）**没有审批**，闸只装在 UI 实例的 `forward` 上。

### 4 上线验收（当场跑过的真实输出）

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| 闸的装法不污染别的调用方 | `/tmp/v13_test.py`「0 安装门」：断言模块级 `@tool` 对象未包、`read_file` 未包、`forward.__signature__` 与原函数一致、两次 `OpsUI()` 不重复套娃 | 全过。CLI 路径 `my_coding_agent.run()` 拿到的还是未包的工具对象 |
| **允许**这条路有真实副作用（探测口 7861，真 qwen-plus） | `/tmp/v13_drive.js`：注入 `window.__v13` 帮手段，题面强制只调一次 `run_python`（代码里 `open('/tmp/v13-live-allow.txt','w')`） | 待批卡 **2.1s** 出（标题 `🟡 待批 · run_python · 等待审批`）→ 点 ✔ 允许（`2026-10-29T08:04:42.621Z`）→ 磁盘上 `/tmp/v13-live-allow.txt` **存在**，mtime `16:04`；卡变 `🟢 … 已允许`；步骤卡 `🛠 第 1 步 · run_python · 🟢 成功 · 2.2s · in 2,874/out 39`；状态条 `2/8 · in 5,849 / out 62 · 3.3s · 完成` |
| **拒绝**这条路没有副作用 | 同驱动器，点 ✖ 拒绝（`08:04:56.977Z`） | `/tmp/v13-live-deny.txt` **不存在**；卡 `⚪ … 已拒绝`；步骤卡 `⚪ 已拒绝 · 1.3s · in 3,107/out 32`；第 2 步 `final_answer` 正常收尾，状态 `完成` |
| **停止**等于拒绝待批 | 同驱动器，待批出现时点 ■ 停止（`08:05:11.393Z`） | `/tmp/v13-live-stop.txt` **不存在**；卡 `⏹ … 随停止取消`；步骤卡 `⚪ 已取消 · 1.4s · in 3,343/out 31`；气泡 `⏹ 已停止：AgentError`；状态 `已停止`。**worker 线程自己退干净**（离线断言 4a/4b） |
| 按钮只在有待批时出现 | `__v13.vis()` 读 `#statusrow button` 的 `offsetParent` | 三条路 `visBefore` 全是 `✔:shown \| ✖:shown \| ■:shown`，点后全收成一枚 `■ 停止:shown` |
| 一步一张卡（V4 的正题） | 离线断言「6 两步 = 两张卡」+ 在线三张标题数组 | 2 步 → **正好两张**步骤卡，各自标 `第 1 步` / `第 2 步`；最终答案是**独立气泡**，没折进卡里；模型思考不重复出现；📊 卡不再存在 |
| 数字口径没变（累计 vs 单步） | 离线断言 6e + 在线与框架日志逐位比 | 第二张卡的"本题累计"是第一步的两倍（`in 12,440 / out 32` 那类）；在线 `第 1 步 in 2,874` 与框架 `[Step 1: Input tokens: 2,874]` 相符 |
| `write_file` 也被拦 | 离线直调 `agent.tools["write_file"]` | 入队 `('write_file','pending')` → 卡正文含**参数全文** → 允许后只落 `.agent-staging/`，**原路径没有文件**（验证副本已删） |
| 超时按拒绝 | 离线把 `APPROVAL_TIMEOUT` 压到 1 秒 | `decision=timeout`、返回"超过 600 秒无人处理"文案、**文件未生成** |
| **交付形态**跑的确实是 v1.3 | 起 `我的Agent.app` 的 launcher → `curl 127.0.0.1:7860/config` 解析组件树 | 4 枚按钮 = `＋ 新会话` / `✔ 允许(approve-btn, visible=False)` / `✖ 拒绝(deny-btn, visible=False)` / `■ 停止`；`chatbot 1`、`radio sessions`、`row statusrow` 在位；页面上再跑一遍"允许"路：待批卡 2.2s、`🛠 第 1 步 · run_python · 🟢 成功 · 2.3s · in 2,392/out 39`、副作用文件 mtime 16:12 |
| 日志零噪声 | `.agent-ui.log` 与探测口日志本轮切片 `grep -c` | `literal_error` / `ValidationError` / `ComponentProcessingError` / `Exception ignored` / `gradio.live` / `Traceback` **全 0** |
| 四条关停判据 | 双击链路：`bash ~/Desktop/关闭Agent.command` 后实测 | 7860 监听 **0**、7861 **0**、9333 **0**、Agent 专用 Chrome（`user-data-dir=…AgentClient`）**0**、`my_ui`/探测进程 **0**、`who` 只剩 **console**、System Events `count of windows of process "Terminal"` = **0**、日志 `gradio.live`/`Exception ignored` **0**。验证用的 `.agent-history.sqlite3`（本轮自建的 5 条测试会话）已按文件名删除 |
| 回滚演练（**双向**） | `.rollback/v1.2/my_ui.py` → 断言 → `.rollback/v1.3/*` → 断言 → `cmp` | v1.2 方向：`py_compile OK`、`_stats_message` 在、**没有** `GATED_TOOLS`/`_step_card`/`_approval_card`、源码无 `threading.Thread`、闸数 0、行数 463、`create_app()` 返回 `Blocks`。v1.3 方向：以上全反、闸 2 只、行数 851，恢复后与存档 **逐字节一致** |
| README 的图没被改坏（第 7 步的另一半） | README 现有 **21** 个 Mermaid 块，逐块 `mermaid.render`（无头 Chrome + 本地 `mermaid.min.js`），**并跑负控** | `TOTAL 21 BAD 0`，svg 15,706 ~ 57,211 B。负控：故意写坏第 19 块（本轮新增那张 flowchart）→ `TOTAL 21 BAD 1`（`Parse error on line 3`），还原后 `BAD 0`——排除"校验器假通过"重演。块数 20 → 21 只多这一张，其余 20 张是**行号与参与者被搬到现状** |
| 手册 HTML 视图与 md 一致 | `/tmp/v13_htmlcheck.py`（静态：标签配对 / 外部资源 / 死锚点 / `data-st` 分布）+ `/tmp/v13_manual_check.js`（浏览器侧：`file://` 真打开，十个筛选器逐个点、读 `#cnt`、量 `scrollWidth`） | 静态：未闭合 `[]`、配对错误 0、外部资源 0、死锚点 `[]`、看板 30 行。浏览器：`all 30 / bug 5 / p0 5 / p1 8 / p2 7 / v 5 / todo 17 / doing 0 / done 10 / na 3`，十个筛选器的 `#cnt` 与"可见行数"**逐条相符**；`overflowX=false`（视口 1425px）；V4 / P0-2 / D4 三行末列都是「已上线 v1.3」，D5 是「未开工（v1.3 新立）」 |

### 5 回滚方法

```bash
cp ~/Desktop/study/ai学习/.rollback/v1.2/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.2/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

行为退回"每步三张折叠卡 + 📊 统计卡、工具不问就跑、停止只在步边界生效"。`my_coding_agent.py` 本轮未动，同拷一份只是让存档自洽。上游源码零改动，无需碰 `.venv`。会话库不受影响（表结构未变）。

### 6 口径与数据变化

1. **执行模型变了（最重要）**：agent 不再跑在 gradio 的事件线程里，而是跑在**工作线程**上，UI 以 **0.25s** 轮询事件队列。因此"生成中"不再是同步阻塞，页面在等待审批时仍能刷新；代价是多线程与队列，`_pending` 必须类级。
2. **卡片数**：一步从 **3 张折叠卡（🛠️/📝/📊）→ 1 张步骤卡**。📊 独立统计卡**取消**，数字进步骤卡标题（`耗时 · in/out`）与正文（本步 + 本题累计）。状态条的六颗胶囊不变，仍与卡同源（`_stats()`）。
3. **判定三档**：`🟢 成功` / `🔴 报错` / `⚪ 已拒绝·已取消·超时未批`；**被拦下的那一步在框架眼里是一次正常观察值**，所以 `⚪` 不是错误，别当失败读。
4. **停止的语义扩大**：v1.2 的"停止 = 在步边界停"；v1.3 起**停止同时拒绝所有待批**。不改这条的话，待批时点停止会让 worker 永远等在 `Event.wait()`。
5. **审批范围**：仅 `write_file`、`run_python`；只读三件不拦。审批超时 **600s**，按拒绝处理。
6. **状态档位 6 → 7**：新增 `awaiting:"等待审批"`（状态胶囊 + 一颗「待批」胶囊）。
7. **token 口径不变**，仍是"本步 / 本题累计 / 进程累计"三档，累计口径同 v1.1/v1.2。本轮实测同题（强制一次 `run_python`）单步 `in 2,874 / out 39`；**与 v1.2 的同题 A/B 未做**【未验证】——审批本身不额外花 token（观察值替换的是工具输出），但被拒后模型多走一步 `final_answer`，实测多 `in 2,975 / out 23`。
8. **体量**：`my_ui.py` **462 → 850 行**、**22,562 → 41,871 B**；`.rollback/` 存档 **6 → 8 份**（v1.3 两份：`my_ui.py` + `my_coding_agent.py`）。

### 7 已知遗留（下次的输入）

- **D4（本轮发现即修）**：`_respond` 的收尾气泡 `metadata.status` 写的是 `"complete"`，而 gradio 6.30 的 `ChatMessage.metadata.status` 是 `Literal["pending","done"]`（`chatbot.py:55`）。实测抛 `pydantic_core.ValidationError` → `ComponentProcessingError: Could not postprocess output component at index 0 (a chatbot component) of the event handler (named "_respond")`，**整条 chatbot 输出被丢弃**，也就是**停止后屏上看不到「⏹ 已停止」气泡**。这个洞从 **v1.1 就在**，v1.2 的验收只看了状态条数字、没看气泡，所以漏过去了。已改 `"done"` 并补离线回归断言（7 组里的 6f）与在线复验。
- **D5（本轮实测撞上，未修）**：**同一页面连问两题、不点「＋ 新会话」→ 前一题从屏上和历史库里双双消失**。`_respond()` 每次从 `[user_msg]` 起列表，`chatbot` 是整体替换；`History.save()` 又是 `DELETE FROM messages WHERE session_id=?` 整条覆盖，而 `sid` 作为 `inputs`+`outputs` 会**沿用同一条会话**。实测：连问两题后 `sessions` 只有 **1 条新增**（标题仍是**第一题**），`messages` 里只剩**第二题**那 3 行。这条从 v1.2 就在，与 V4/P0-2 无关。修法要么"上一题完成即自动换新 sid"，要么"消息列表跨题累加"——后者与 **V5（点旧会话接着聊）是同一件事**，建议同批做。
- **并发提问共用一个进程级 agent**：两个浏览器标签同时提问，会共享同一个 `_pending` 队列和同一个 agent 状态（`monitor` 也共享）。当前设计假设**一次只问一题**。
- **多工具并行时按钮只处理最早一条**：`agents.py:1361-1437` 的 `process_tool_calls` 在一步里有多个调用时走 `ThreadPoolExecutor`，队列里会同时躺多条待批；允许/拒绝键只对**最早**那条生效，其余要点第二遍（本轮实测题面都是单工具调用，**未覆盖并行多工具**【未验证】）。
- **审批只装在 UI**：命令行 `my_coding_agent.py` 直调工具不过闸（设计如此，见 §3 第 7 条）。
- 仍欠你的点头：dify Docker Compose（#5）、MCP servers `npm ci`（#6）、**百炼 Key 轮换**、`gradio_ui.py:456` 的 `.capitalize()`、D2（staging 副本读不回来）、P0-4、V5。

**推荐下一刀 v1.4 = D5 + V5（同一件事的两面：会话跨题累加 + 切会话时换 `agent.memory`）**。P0-4（计划可见）继续往后排。

---

## v1.2 · 2026-10-29 · 界面换壳：状态条 + 深色 + 会话侧栏（V1 + V2 + V3，顺带关掉 P0-3）

### 1 这次解决什么（为什么现在做）

v1.1 之后功能不缺，缺的是**长得像个产品**。对着截图比对的结论是：差距不在能力，在**信息架构**——v1.1 直接把 `gr.ChatInterface` 交出来，品牌尾巴、浅色底、无状态条、无会话列表，全是它的默认形态。范围按工单号锁定 **V1 + V2 + V3**，其余一律未动。

- **V1**：步数 / token / 模型 / 耗时这些数在 v1.1 只以**每步一张折叠卡**的形式沉在对话流底部，问一题要往下翻才看得全。要一条常驻的状态条。
- **V2**：浅色主题 + 页脚挂着「通过 API 使用 🚀 · 使用 Gradio 构建 🌊 · 设置 ⚙️」。
- **V3（= 看板 P0-3）**：会话列表与历史持久化。v1.1 的 `save_history=True` 把历史存在**浏览器 localStorage**（`gradio/chat_interface.py:145` docstring 原话），服务端没有一份可查的账，换浏览器 / 清缓存即丢，别的工具也读不到。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_ui.py:15` | `DB_PATH = Path(__file__).resolve().parent / ".agent-history.sqlite3"`——按文件定位，不按 cwd，启动器 `cd smolagents` 与否都落在同一处 | 新增 | V3 |
| `my_ui.py:19-127` | `DARK_CSS`：`:root` 变量同名覆盖 + 六处 gradio 硬编浅色的定点压制（见 §4 第 1 行） | 新增 | V2 |
| `my_ui.py:132-224` | `History`：两张表（`sessions` / `messages`）+ `ensure/choices/load/save`，`save` 是**整条覆盖写**，所以半截停止也落库、重复保存不会产生双份 | 新增 | V3 |
| `my_ui.py:241-266` | `_stats()`：把 v1.1 塞在 `_stats_message()` 里的算法抽出来，一份数字两处显示 | 重构 | V1 |
| `my_ui.py:288-304` | `_status_html()`：六颗胶囊（模型 / 步数 / 本题 token / 本题耗时 / 进程 token / 状态） | 新增 | V1 |
| `my_ui.py:306-323` | `_stream_response()`：**v1.1 那段一字未改**，原样搬过来（`finally` 里 `interrupt()` + 主动 `close()` 吃 `RuntimeError`） | 保留 | P0-1 / D2 |
| `my_ui.py:325-339` | `_user_message()`：自建 Blocks 之后**用户那条气泡没人拼了**，得自己拼（首轮实测就是这个漏的，见 §4 第 5 行） | 新增 | V3 |
| `my_ui.py:341-369` | `_respond()`：一次提问的编排，产出 5 元组（chatbot / 状态条 / 侧栏 / 输入框 / sid），异常分「步数用满」和「已停止」两路收尾 | 新增 | V1 / V3 |
| `my_ui.py:374-382` | `_stop()`：自建刹车键的 handler，只置 `interrupt_switch` | 新增 | V1 |
| `my_ui.py:393-455` | `create_app()` 覆盖：不再用 `gr.ChatInterface`，自己拼 `gr.Blocks`（侧栏 \| 主区），`layout="panel"`、`analytics_enabled=False`，并挂 `demo.load` | 重写 | V1 / V2 / V3 |
| `smolagents/.agent-history.sqlite3` | 新文件，首次提问时自动建；单库单文件，备份/清空都只动它 | 新增 | V3 |
| `ai学习/.rollback/v1.2/` | 新增第三套存档（`my_ui.py` + `my_coding_agent.py`），与 v1.0 / v1.1 并列 | 新增 | 回滚 |
| `ai学习/README.md` §6.3 | 新增 **§6.3.4**：`ChatInterface` → 自建 `Blocks` 的换壳链路（含 1 张 flowchart）、`History` 三张约定表、四条实测实现点；§1.3 架构图节点与全篇 `my_ui.py` 行号（`:10/:454/:455-457/:462/:310/:306-323/:268-286`）同步；§9.1 关键代码表加 **26~29** 四行 | 修改 | — |
| `ai学习/agent功能手册.html` | §2.1 体量与文件表（加 `.agent-history.sqlite3`、存档 4→6 份）；§2.4 标题改「接上的、没接的、主动放弃的」并加 `ChatInterface` 一行；§2.5 换壳后的界面构成（10 行）；§3 结尾"五件事"改为"上了三件"；§4 看板 P0-3 转「已上线」并**更正措辞**（见本节第 3 条）、P0-1 / P0-5 补 v1.2 追加的两笔；新增 **§4.5 V 组 5 行**（看板 23 → 28 条，筛选器加「V 界面」）+ 推荐卡换成 v1.3 = V4 + P0-2；§5.1 加会话库文件行；§5.3 第 4 步补"关停走启动器别直接 kill"；§6.1 抄本节（v1.1 顺次变 6.2、v1.0 变 6.3，v1.1 的旧推荐卡改成"当时的推荐 + 实际走向"）；§7 加一条 CDP 视口的【待补】 | 修改 | — |

上游 smolagents 源码**仍是一行未改**；`my_coding_agent.py`、`my_agent.py` 本轮未动（`cmp` 与 `.rollback/v1.1/` 逐字节一致）。`my_ui.py` 76 → **462 行**（3,816 → 22,562 B）。

### 3 新功能怎么用（用户视角）

1. 双击桌面 `我的Agent`。开出来是深色窗口：左边一条会话栏，顶上一排状态胶囊，中间整行宽的消息流，底下输入框带橙色发送键。
2. 直接提问。屏上第一行是**你自己的问题**，然后每步一张折叠卡（和 v1.1 一样），最上面那条状态条实时跟着走。
3. 生成中点状态条右侧的 **■ 停止**。语义同 v1.1：**跑完当前这一步才停**，从点下去到状态变「已停止」之间会等，这是设计不是卡住。
4. 点侧栏任意一条 → 屏幕换成那次的记录，**只是回看**；此时再提问会**新开一条会话**，不会接在旧会话后面（原因见 §6 第 4 条）。
5. 「＋ 新会话」→ 清屏，等你提问才真正建条目（所以点完又什么都不问，不会留一条空会话）。
6. 历史全在 `smolagents/.agent-history.sqlite3` 一个文件里。想清空就删它；换机器带走它，侧栏就跟着过来了。
7. 彻底收摊仍同 v1.1：日志窗 `Ctrl-C`，或双击 `关闭Agent.command`。

### 4 上线验收（当场跑过的真实输出）

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| V2 深色壳**没有浅色残留** | 零安装 CDP（`/tmp/cdp.js`，headless Chrome + Node 22 内置 WebSocket）遍历 `#main *` 读 `getComputedStyle().backgroundColor` | 浅色只剩三处：0 宽的隐藏 `input[data-testid=file-upload]`、我故意留橙色的 `button.submit-button`、自定的 user 行 `#1b2430`。`body` = `rgb(13,17,23)`；`footer[aria-label="Gradio footer navigation"]` = `display:none`。**逐轮定位到的四处 gradio 硬编浅色**：块标题 `rgb(255,255,255)`、secondary 按钮 `rgb(228,228,231)`、折叠卡 `.thought-group` `rgb(255,255,255)`、panel 布局下 `.message-row`（user `rgb(255,247,237)` / bot `rgb(250,250,250)`） |
| 消息流宽度正常 | 同上，量 `[data-testid=bot]` 到 `#main` 的祖先链 | `layout="panel"` 后链路 849→916（容器 950）。默认 `bubble` 布局会把气泡按内容收缩，实测折叠卡只有 **353px**、右边空一大片——这就是第一版截图的样子 |
| V1 状态条与折叠卡**同源不同数** | `_stats()` 一个函数出两处；与框架自己的 `[Step N]` 日志逐位比 | 同题：状态条 `步数 1/8 · in 2,349 / out 19 · 1.1s`，日志 `[Step 1: Duration 1.06 seconds\| Input tokens: 2,349 \| Output tokens: 19]` —— token **逐位相符**，耗时是 1.06 显示成 1.1 |
| V3 历史**跨进程重启还在**（P0-3 的正题） | 跑两轮 → `kill -TERM` 掉服务 → 用启动器同款命令重新拉起 7860 → CDP 读侧栏 | 重启后侧栏 **2 条会话**、自动展开最新一条（**7 个气泡**）。v1.1 这个位置是空的 |
| 「新会话」不产生垃圾条目 | CDP 点「＋ 新会话」前后计数 | 气泡 **34 → 0**，会话数**保持 1**（不建空行），状态条回 `步数 0/8 · 状态 空闲` |
| 下一条提问开新会话 | 新会话后提一题（`1+1`，要求不调工具） | 会话数 **1 → 2**，新条目标题取首问前 28 字：`1+1 等于几？直接回答，不要调用工具` |
| 刹车：停在步边界（**确定性单测**） | `/tmp/v12_stoptest.py`：驱动 `_respond` 生成器，第 3 个 yield 时调 `agent.interrupt()` | 终态 **「已停止」**，末条气泡 `⏹ 已停止：AgentError`，**7 条消息落库**（含用户那句），日志 `Exception ignored` **0** |
| 刹车：真实按钮（7861 探测口） | 跑到 `步数 7/8` 时点「■ 停止」，12 秒后复采 | 步数 / 本题 token / 本题耗时三项**逐位冻结**（`7/8`、`35,256 / 196`、`10.3s` 与点击瞬间一致），状态先转「停止中」 |
| 停止边界的**例外**（实测撞上的） | 同上，那一题正好跨过 `max_steps` | `interrupt` 之后 while 循环已退出，`_handle_max_steps_reached` 在循环**外**又补了一次收尾问答：**36.74s、+9,096 input token**，开关管不到它。已写进 §6 第 7 条 |
| 四条关停判据 | `lsof -nP -iTCP:7860 -sTCP:LISTEN`；`who`；System Events `count of windows of process "Terminal"`；`.agent-ui.log` grep | 关停前 1 个监听（pid 44458）→ 关停后 **0**；终端窗口 **0**；`gradio.live=0`、`Exception ignored=0`。**`who` 这次不干净**：多出一条 ttys000，见 §7 第 6 条 |
| 回滚演练（**双向**都跑过） | `cp .rollback/v1.1/* smolagents/` → 断言 → `cp .rollback/v1.2/* smolagents/` → 断言 → `cmp` | v1.1 方向：`py_compile OK`、`create_app()` 返回 **`ChatInterface`**、模块**没有** `DARK_CSS`。v1.2 方向：`py_compile OK`、返回 **`Blocks`**、`History/DB_PATH` 在位；恢复后与存档**逐字节一致**。演练用的 `.agent-history.sqlite3` 已删除（本轮验证自建的单个文件） |
| 探测环境已收 | `lsof` 7860 / 7861；`pgrep -fl "my_ui\|v12_probe"`；`pgrep -f remote-debugging-port=9333` | 两个端口监听数均 **0**，无残留 python，scratch Chrome 已退 |
| 手册 HTML 视图与 md 一致（上线第 7 步） | 栈式标签配对扫描 + 无头 Chrome（CDP 9333）里**逐筛选器实点**读 `#cnt` | 看板 **28 行**：全部 28 / 缺陷 D 3 / P0 5 / P1 8 / P2 7 / **V 界面 5** / 未开工 18 / 进行中 0 / 已上线 7 / 待你定性 3；`P0-3` 与 `V1~V3` 状态列确认为「已上线 v1.2」、`V4/V5` 为「未开工」；标签**无未闭合、无错配**；正文宽 1080、无横向溢出、外链资源 **0** 条（仍离线自包含） |
| README 的图没被改坏 | 20 个 Mermaid 块逐块 `mermaid.render`，**并跑负控** | `TOTAL 20 BAD 0`，svg 15,706 ~ 57,223 B。负控：故意写坏第 18 块 → `TOTAL 20 BAD 1`（`Parse error on line 2`），改回后 `BAD 0`——排除 v1.0 那次"校验器假通过"重演。与 v1.1 快照逐块 diff：只有我改的 3 块（§1.3 架构图、§6.3.1、§6.3.2）+ 新增 1 块不同，其余全是序号位移，**无连带改动** |

### 5 怎么退回去

```bash
cd ~/Desktop/study/ai学习
cp .rollback/v1.1/my_ui.py .rollback/v1.1/my_coding_agent.py smolagents/   # 退 v1.1
cp .rollback/v1.2/my_ui.py .rollback/v1.2/my_coding_agent.py smolagents/   # 再回到 v1.2
```

回滚**不动** `.agent-history.sqlite3`：v1.1 读不到它，留着不影响，只是侧栏没了。要连数据一起退干净，再 `rm smolagents/.agent-history.sqlite3`（这一个文件，不是目录）。

### 6 口径与数据变化（行为语义变了什么）

1. **状态条和折叠卡是同一份数**：都出自 `_stats()`（`my_ui.py:241`）。以前那种"卡片一个算法、面板另一个算法"的漂移风险已经没有了。
2. **侧栏历史是显示层，不是 agent 的记忆**。agent 的记忆仍是进程级、跨会话不清零（`reset_agent_memory` 仍为 `False`）。点开旧会话只是把当时屏幕上说过话贴回来，**不代表模型还记得**。
3. **状态条反映"当前进程 / 当前题"，不反映所选会话**。看着旧会话时它是 `步数 0/8 · 空闲`——这是对的，不是 bug。
4. **下一条提问永远开新会话**，不会 append 到你正在看的那条旧会话里。要把历史接回上下文，得先做会话级记忆隔离（新单 **V5**）。
5. **步数可以超过 max_steps 显示成 `9/8`**。框架用满 8 步后不抛异常，而是补一步"给个结论"（`agents.py` 的 `_handle_max_steps_reached`），那一步 `step_number=9`、`error=AgentMaxStepsError`。所以状态胶囊这时显示**「步数用满」**（黄），不是「完成」。
6. token 三口径不变：本步 / 本题（最后一个 `TaskStep` 之后）/ 进程（`monitor`，跨题不清零）。
7. **「停止」= 停在步边界**，唯一例外是第 5 条那次收尾问答——它在 while 循环外，`interrupt_switch` 拦不住。撞上时它还会再花 30 秒级 / 数千 token。
8. **v1.1 存在浏览器 localStorage 的旧历史不迁移**（见 §7 第 3 条）。

### 7 已知遗留 / 下一刀建议

- **V4 步骤卡片化**：未开工。消息流现在是 gradio 的 panel 布局，工具调用 / 执行日志 / 统计是三种折叠卡，还没有"一次工具调用一张带状态色的卡"。
- **gradio 自带的 stop 键在自建 Blocks 下是死的**：`MultimodalTextbox(stop_btn=True)` 那个按钮点了没反应（实测：`步数 7/8` 处点它，照样跑到 `9/8` 才完）。根因是它的取消链路只有 `ChatInterface` 会接（`chat_interface.py:371-372` 把 `stop_btn` 摘下来自己管）。已改成自建「■ 停止」+ `stop_btn=False`。
- **P0-3 的措辞更正（v1.0 测绘写错的一条）**：原文写的是「`save_history=True` 只存浏览器本地；**进程重启即空**」。前半句对，后半句不对——localStorage 恰恰**能**活过服务端重启。真正的缺口是：服务端**没有一份可查的账**，换浏览器 / 换 Chrome profile / 清缓存即丢，别的工具读不到，也没法按会话取数。看板 P0-3 那格已按这个改写，状态转「已上线」。
- **v1.1 的 localStorage 老历史还在那个 Chrome profile 里**（`~/Library/Application Support/AgentClient`），没删也没搬。要清就在浏览器里清，别去删 profile。
- **V5（新单）会话级记忆隔离**：切会话时把 `agent.memory` 一起换掉。注意它不是纯界面活——`reset=True` 会连 `monitor` 一起清（`agents.py:478-480`），"进程累计"这个口径就得重定义。
- 侧栏**不搜索、不分组、不分页**，`History.choices()` 上限 50 条。
- panel 布局每条消息带一个复制按钮，视觉噪音，暂留。
- **本次关停判据 2 曾不干净（已清）**：`who` 当时多出一条 `ttys000`（`login -pf gaoying` + `-zsh`，11:11 起）。是我这轮**直接 kill python**、没走启动器收尾链路留下的空闲 shell；Terminal 窗口数当时已经是 0，所以它是幽灵窗口，不是开着没关。12:12 已收：`kill 39636`（`-zsh`，0 个子进程）→ `kill 39635`（挂着 ttys 的 `login`），现在 `who` 只剩 `console`。**教训已写进手册 §5.3 第 4 步**：下次上线验收走 `关闭Agent.command`，让启动器自己收。
- **文档回写这一轮也当场验了**（不是"写完就算"）：见 §4 最后两行。
- 推荐下一刀：**V4（步骤卡片化）+ P0-2（工具执行前审批）**。理由：V4 继续把界面补齐到"能给别人看"，而 P0-2 的审批 UI 正好要落在同一片消息流上，一刀里两件事不打架。D2（`write_file` 暂存副本读不回）仍单独挂着。

---

## v1.1 · 2026-10-29 · 止血 + 成本上墙 + 刹车落地（D1 + P0-5 + P0-1）

### 1 这次解决什么（为什么现在做）

v1.0 测绘出的三条，范围按工单号锁定为 D1 + P0-5 + P0-1，其余一律未动。

- **D1**：走 UI 路径时 `ai学习/.agent-staging` 没人创建，`run_python` 抛裸 `FileNotFoundError`。`STAGING.mkdir()` 原来写在 `my_coding_agent.py` 的 `__main__` 分支里，而 UI 的实际链路是 `my_ui.py → my_agent.py:8 → from my_coding_agent import run_python, …`，是 **import**，`__main__` 永远不执行。
- **P0-5**：界面上看不到"这题跑到第几步、烧了多少 token"。`max_steps=8` 要用满、被 `AgentMaxStepsError`（`agents.py:630`）打断才知道贵。
- **P0-1**：需要一条点了之后**真的能停住服务端**的刹车，而不只是停渲染。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `my_coding_agent.py:26-28` | `STAGING.mkdir(parents=True, exist_ok=True)` 从 `__main__` 提到**模块级**，并写明为什么必须在 import 时执行 | 修改 | D1 |
| `my_coding_agent.py`（原 `:200`） | 删掉 `__main__` 里那份重复的 `mkdir`，避免两份来源互相掩盖 | 删除 | D1 |
| `my_ui.py:10-47` | 新增 `OpsUI(GradioUI)` 与 `_stats_message()`：每步产出一张成本统计卡 | 新增 | P0-5 |
| `my_ui.py:49-65` | `_stream_response()` 包住上游生成器：`finally` 里 `agent.interrupt()` + 主动 `inner.close()` 并吃掉 `RuntimeError` | 新增 | P0-1 |
| `my_ui.py:69` | `GradioUI(agent, …)` → `OpsUI(agent, …)` | 修改 | P0-5 / P0-1 |
| `ai学习/.rollback/v1.0/`、`.rollback/v1.1/` | 新增：被改两份文件的**双版本存档**（2 文件 × 2 版本）；起因见 §7 的 D3 | 新增 | 回滚 |
| `ai学习/README.md` §6.3 | 重写：拆成 6.3.1 / 6.3.2 / 6.3.3，新增**第 19 个 Mermaid 图**（Stop 路径 `sequenceDiagram`）、成本卡三口径表、D1 成对复现 | 修改 | D1 / P0-5 / P0-1 |
| `ai学习/README.md` §9.1 | 追加 5 条承重引用（`agents.py:545-547/:470/:754` 中断三件套、`agents.py:599-602` 的 `finally` 里那次 `yield`、`gradio_ui.py:310`、`monitoring.py:108`、`my_ui.py:31-36`） | 修改 | — |
| `ai学习/README.md` §9.2 + 手册 §2.2 | 统一**"动作空间"口径**：实测 `len(agent.tools) == 8`（你声明 7 项 + `final_answer` 由 `agents.py:402` 自动补）。此前 README 说 8、手册 §2.2 标题说"7 项，不多不少"，两边都没标口径 | 修改 | — |
| `ai学习/README.md` §6.1 标题、`:74` | 体量与行号跟随代码：`my_coding_agent.py` 203 → **204 行**；`my_ui.py:9-11` → `:70-72`；`os._exit` `:13-15` → `:76` | 修改 | — |

上游 smolagents 源码**一行未改**：全部改动都在 `OpsUI` 的子类里，`super()._stream_response` 的内部列表用副本（`list(msgs) + [stats]`）喂给 gradio。

### 3 新功能怎么用（用户视角）

1. 双击桌面 `我的Agent`，照常提问。
2. 每一步之后，对话流底部多一条**折叠栏**，收起状态就能看见标题：`📊 第 3/8 步 · 本题累计 in 12,345 / out 678 token · 本步 4.2s`。本步报错时标题尾部追加 `· 本步报错`。点开是三行明细：本步 / 本题累计 / 进程累计。
3. 生成中点对话框右上的 **Stop**。表现：**正在执行的这一步跑完就停**，不再进下一步，界面不再动，日志的 `[Step …]` 行数不再增长。
4. 停止之后**直接问下一题就行**，不用重启服务。
5. 彻底收摊仍同 v1.0：日志窗 `Ctrl-C`，或双击 `关闭Agent.command`。

### 4 上线验收（当场跑过的真实输出）

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| D1 真的消失（成对复现） | 把 `.agent-staging` 挪开 → `.venv/bin/python -c "import my_agent"` → 调 `run_python("print(42)")` | **v1.0**：`import 后目录存在: False`、`FileNotFoundError [Errno 2] … '.agent-staging/age…'`。**v1.1**：`True`、`run_python: 'exit=0\n42\n'` |
| 统计卡的数字不是我自己算着玩的 | 与框架自己的 `[Step N]` 日志逐位比对 | 进程累计口径与 `monitor.get_total_token_counts()` **逐位相符**（同题 23,134 / 205） |
| 停止真的停住 | 提交一题强迫 `run_python` 里 `time.sleep(30)`；第 12 秒点 Stop；之后每 10 秒采样 `grep -c '\[Step'` | `+36s 15` / `+46s 15` / `+56s 15` —— 30 秒零增长，进程 33993 存活 |
| 停止之后服务还可用 | 同一会话再提交一题（`1+1`，要求不调工具） | 日志重开 `New run` 横幅 → `[Step 16: Duration 1.22 seconds\| Input tokens: 76,021 \| Output tokens: 1,252]` → `Final answer: 2`。`interrupt_switch` 由下一次 `run()` 在 `agents.py:470` 重置，无需重启 |
| 生成器噪声已消 | `grep -c 'Exception ignored' /tmp/v11-ui3.log` | **0**。修 `inner.close()` 之前每次 Stop 都喷一条 `Exception ignored … generator ignored GeneratorExit`（根因：上游 `agents.py:599-602` 在 `finally` 里还有一次 `yield`） |
| 四条关停判据 | `lsof -nP -iTCP:7860 -sTCP:LISTEN`；`who`；System Events `count of windows of process "Terminal"`；两份日志 grep | 关停前 1 个监听（pid 33993）→ 关停后 **0**；`who` 只剩 `console`；终端窗口 **0**；`/tmp/v11-ui3.log` 与正式 `ai学习/.agent-ui.log` 均 `gradio.live=0`、`Exception ignored=0` |
| 文档同步后 19 图仍**解析且渲染** | 逐块 `mermaid.parse` + `mermaid.render`（headless Chrome + 本地 `mermaid.min.js`），并跑**反向对照** | `TOTAL 19 BAD 0`；SVG 字节 15,702 ~ 57,199（新增那张 Stop 序列图 36,612）。反向塞 2 个坏图 → `TOTAL 21 BAD 2`，两条 `FAIL` 带真实解析器报错栈，证明"BAD 0"不是假通过 |
| 手册 HTML 结构完整 + 筛选按钮真能用 | 标签配对统计 + 浏览器里逐个点 `filterBoard` 读 `#cnt` | 13 类标签全平衡；`全部 23/23`、`缺陷 D 3`、`P0 5`、`P1 8`、`P2 7`、`未开工 17`、`已上线 3`、`待你定性 3`（3+5+8+7=23）。**首轮自检抓到我自己写的一个未闭合 `<code>` 和一个重复的 §5.4**，已修 |
| 回滚演练（**双向**都跑过） | `cp .rollback/v1.0/* smolagents/` → 验 v1.0 行为 → `cp .rollback/v1.1/* smolagents/` → 验 v1.1 行为 | 两方向各 `py_compile OK`；上表 D1 那行的成对结果就是这两条命令跑出来的；恢复后 `cmp` 与存档**逐字节一致**；演练时挪开的 `.agent-staging` 已原样还原（`mtime=Oct 29 09:46:27`，内含原 `smolagents/` 空目录） |

### 5 回滚方法

```bash
# 退回 v1.0
cp ~/Desktop/study/ai学习/.rollback/v1.0/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.0/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/

# 再回 v1.1
cp ~/Desktop/study/ai学习/.rollback/v1.1/my_ui.py \
   ~/Desktop/study/ai学习/.rollback/v1.1/my_coding_agent.py \
   ~/Desktop/study/ai学习/smolagents/
```

两条**都已当场演练**（见 §4 最后一行）。这里没有 `git checkout` 可用——见 §7 的 D3。

### 6 口径与数据变化

**行为语义变了两处，显式声明：**

1. **Stop 的语义 = 在步边界停，不打断正在执行的那一步。** 停止点在 `agents.py:545-547`（`while` 条件之后、下一步之前）。上面那次 `sleep(30)` 最终是被 `run_python` **自己的 20 秒沙箱超时**掐掉的（日志 `Observations: 超时 20 秒，已杀掉`），不是被 stop 掐掉的——stop 对这个工具调用本身没有杀伤力。
2. **统计卡的步号是「本题内」，控制台那行 `[Step N]` 是「进程内」。** 前者来自 `agents.py:543`（每次 `_run_stream` 置 1），后者来自 `monitoring.py:108` 的 `len(self.step_durations)`。因为 `GradioUI` 默认 `reset_agent_memory=False`（`gradio_ui.py:310`），**从第二题起这两个数必然不同，不是 bug**。卡里三个口径写死为：本步 / 本题累计（最后一个 `TaskStep` 之后）/ 进程累计（monitor，跨题不清零）。

**前后对比（数字）：** `my_ui.py` **15 行 / 452 B → 76 行 / 3,816 B**（净增 61 行）；`my_coding_agent.py` **202 行 / 8,131 B → 204 行 / 8,355 B**。工具数**一个没增、一个没减**：你自己声明的仍 **7** 项，`len(agent.tools)` 实测仍 **8** 项（第 8 项是 `agents.py:402` 自动补的 `final_answer`）——本轮把这两个口径在 README §9.2 和手册 §2.2 都写死了，此前两处一个说 7 一个说 8 而都没标口径。`max_steps` 仍 **8**、模型仍 **qwen-plus**、端口仍 **7860**。

**新增成本样本（同进程真实值）：**「1+1 等于几、不许调工具」这种最省的题，单步 **input 6,220 / output 16** token、**1.22 s**。底价来自 7 件工具的描述全量进 system prompt。同进程累计：第 15 步 69,801 / 1,236，第 16 步 76,021 / 1,252。

### 7 已知遗留（下次的输入）

- **D3（新）**：`my_agent.py / my_coding_agent.py / my_ui.py` 在 smolagents 克隆里是 **untracked**（`git status --porcelain` → `?? my_agent.py` 等三条）。`git clean -fd`（清克隆时很顺手的一条命令）会把这三份**全删且 git 无法恢复**。本轮已建 `.rollback/` 双版本存档缓解，但存档与克隆**同一个盘、同一个父目录**，一起被清的风险仍在。【未验证】是否该把这三份挪出克隆。
- **P0-1 残余项**：慢工具（大目录 grep、>20 s 的 `run_python`）在点 Stop 之后仍要等它自己返回，本轮实测最长 21.57 s。要"瞬间掐断"得动沙箱执行器，不属 P0-1 范围。
- **纠正 v1.0 看板里两条错判**：(a) P0-1 原写「无原生中断、要自己插桩、代价半天」——**错**。smolagents 原生就有 `agent.interrupt()`（`agents.py:754`）+ `interrupt_switch`（`:470` 置回、`:546` 检查），实际代价是 `my_ui.py` 净增 61 行；(b) gradio 6.30 的 `stop_btn` **默认就是 True**，按钮本来就在，缺的只是"点了真停"。
- **D2** 仍未动：`.agent-staging` 同时出现在 `my_coding_agent.py:30` 的拒绝名单里，agent 写出去的副本自己读不回来。
- 仍欠：**百炼 Key 轮换**（他曾在对话里贴过明文）、`gradio_ui.py:456` 的 `.capitalize()` 标题补丁、dify 部署待点头（#5）、MCP servers `npm ci` 待点头（#6，本机 Node v22.20 < `memory` 要求的 24）。

**推荐下一刀 v1.2 = P0-2（工具执行前审批）+ D2。** 理由：这两条同属**写路径**——`write_file` 现在能直接落盘到 `ai学习`，而它暂存出去的副本又读不回来；一个主题、一刀切完。P0-3（会话历史持久化）和 P0-4（计划面板）是界面活，可以往后排。

---

## v1.0 · 2026-10-28 · 功能基线建档

### 1 这次解决什么（为什么现在做）

agent 已经能跑（7 项工具、`max_steps=8`、双击起、Ctrl-C 停），但没有任何一处写下"它现在是什么、对着成熟产品缺什么"。没有基线，之后的改动无法判断是进步还是漂移。本轮只做**测绘**，**未改动 agent 任何代码**。

### 2 改动清单

| 文件:行 | 改了什么 | 类型 | 工单号 |
|---|---|---|---|
| `ai学习/README.md` | 新建：四仓深度剖析，9 章 / 18 个 Mermaid 图 / 2 块 Gherkin（8 个场景）/ 20 条代码位置表 / 7 条【待补】 | 新增 | — |
| `ai学习/README.md` §6.5 | 纠正事实错误：原文称存在 `Agent链路详解.app` 且两份 HTML "套了手写 bundle"；磁盘上只有两份裸 HTML | 修改 | — |
| `ai学习/agent功能手册.html` | 新建：现状能力面 + WorkBuddy/Qoder 参照 + 22 条缺口看板 + 迭代手册 | 新增 | — |
| `ai学习/迭代记录.md` | 新建：本文件 | 新增 | — |
| `smolagents/my_ui.py:14` | `os._exit(0)`：SIGINT 后 gradio 释放端口但非守护线程挂住进程 | 修改（上一半天） | — |
| `我的Agent.app/…/launcher:50-98` | 生成三个协作文件：`/tmp/agent-win-close.sh.scpt`、`agent-win-detach.py`（fork+setsid 脱离终端会话）、`agent-win-close.sh` | 修改 | — |
| `~/Desktop/关闭Agent.command:52-73` | 第 3 步按 `history` 扫目标 tty 并**排除自身 tty**；第 4 步改为交棒延迟 5 秒的脱离式关闭器，不在前台 `sleep` | 修改 | — |

### 3 新功能怎么用（用户视角）

1. 双击桌面 `我的Agent` → 出现日志终端窗 + 无地址栏的独立 App 窗口（标题 `Smolagents`）。
2. 提问，看流式步骤；答完在日志窗按 **Ctrl-C**，或双击桌面 `关闭Agent.command` —— 两者等价，服务、App 窗口、日志终端窗一起收，**不弹「终止正在运行的进程」警告**，不碰日常 Chrome。
3. 读剖析：`~/Desktop/study/ai学习/README.md`（GitHub / Qoder 预览直接渲染 Mermaid；VS Code 自带预览需装 Mermaid 插件）。
4. 读功能与缺口：双击 `~/Desktop/study/ai学习/agent功能手册.html`，第 4 节看板顶部有筛选按钮（全部 / D / P0 / P1 / P2 / 未开工 / 进行中 / 已上线）。

### 4 上线验收（当场跑过的真实输出）

| 判据 | 命令 / 方法 | 结果 |
|---|---|---|
| 18 个图语法通过**且**真渲染出 SVG | 逐块 `mermaid.parse` + `mermaid.render`（headless Chrome + 本地 `mermaid.min.js`） | `TOTAL 18 BAD 0`；SVG 字节 15,721 ~ 57,235 |
| 校验器能抓到坏图（排除假通过） | 塞入 2 个故意写坏的图重跑 | `91 FAIL` / `92 FAIL`，`TOTAL 20 BAD 2`。**上一版校验器是假通过，本轮修好** |
| 关停彻底 | `lsof -nP -iTCP:7860 -sTCP:LISTEN`；`who \| awk '{print $2}'`；System Events `count of windows`；`tail -40 .agent-ui.log` | 端口 0、Agent 专用 Chrome 进程 0、`who` 只剩 console、窗口 0、日志无 `gradio.live` |
| 承重引用可跳 | 回查 `agents.py:596-598`、`memory.py:138-148`、`utils.py:128`、`dify/api/core/workflow/nodes/agent_v2`、`servers/src/memory/package.json:16`、`~/.zshrc:111/:113` | 全部存在且与文案一致（含 `AgentToolExecutionError` 继承 `AgentError` → 被回灌而非中断） |

### 5 回滚方法

本轮三个新文件均为**新增**，不影响运行链路：

```bash
rm ~/Desktop/study/ai学习/agent功能手册.html ~/Desktop/study/ai学习/迭代记录.md
```

README 的两处改动要退回 v1.0 之前需手工反向编辑（该目录不是 git 仓库，没有 `git checkout` 可用）。关停链路（`my_ui.py` 的 `os._exit(0)` 与 launcher 生成的三个文件）是**上一半天**的成果，本轮未再改动，回滚它等于回到"Ctrl-C 后窗口留着"的旧行为。

### 6 口径与数据变化

无功能变化。基线数字记录在案，供日后 A/B：工具 **7** 项、`max_steps` **8**、模型 **qwen-plus**、会话 **单**、端口 **7860**、`my_ui.py` **15** 行 / `my_agent.py` **82** 行 / `my_coding_agent.py` **202** 行 / `launcher` **132** 行。已知成本样本：同题工具从 2 个增至 7 个，单题**累计** input token **2,375 → 19,399**（累计口径，非单步）。

### 7 已知遗留（下次的输入）

新发现缺陷 2 条，已进看板：**D1**（`run_python` 依赖 `.agent-staging` 预存在，`STAGING.mkdir()` 在 `my_coding_agent.py:198` 的 `__main__` 分支里，走 UI 路径不执行）、**D2**（`.agent-staging` 同时在拒绝名单 `:30`，agent 读不到自己暂存的副本）。缺口清单 20 条（P0×5、P1×8、P2×7）。另欠：百炼 Key 轮换、`gradio_ui.py:456` 的 `.capitalize()` 让标题严格等于 `smolagents`、dify 部署待点头、MCP servers `npm ci` 待点头（本机 Node v22.20 < `memory` 要求的 24）。

**推荐下一刀 v1.1 = D1 + P0-5 + P0-1**（止血 + 一行级 token 上墙 + 唯一的救命刹车）。

---

## 附录 A 空白模板（复制这一节往上追加）

```markdown
## vX.Y · YYYY-MM-DD · 一句话主题

### 1 这次解决什么（为什么现在做）
触发事件：哪条缺口、什么现象、哪次跑挂。不写"优化体验"。

### 2 改动清单
| 文件:行 | 改了什么 | 类型(新增/修改/删除) | 工单号 |

### 3 新功能怎么用（用户视角，不含实现）
双击→点哪儿→看到什么。每步可跟着做。

### 4 上线验收（必须当场跑过的真实输出）
| 判据 | 命令 | 结果 |
没跑过的一律写【未验证】。

### 5 回滚方法
一条命令回到上一版行为。做不出回滚方案的改动不算上线完。

### 6 口径与数据变化
token / 步数 / 工具数量 / 行为语义的前后对比，数字必须同题同步长。口径要写明累计还是单步。

### 7 已知遗留（下次的输入）
没做完的、新发现的缺陷，直接编号进手册第 4 节看板。
```

### 上线动作顺序（每次按这七步）

1. 按工单号确认范围，只动这几条；
2. 改代码 → 读回磁盘确认存在 → 才宣布；
3. 实跑新功能（起 `my_ui.py` 走一遍）；
4. 跑四条验收（`lsof` / `who` / System Events 窗口数 / 日志尾）；
5. 回滚演练一次；
6. 追加本文件一节；
7. 重生成 `agent功能手册.html`（第 4 节状态、第 6 节记录、第 2 节能力面同步）。
