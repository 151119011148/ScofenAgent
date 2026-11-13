# -*- coding: utf-8 -*-
"""把 §6.3.9（V9）插到 README 的 ### 6.4 之前。"""
import pathlib

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
P = ROOT / "README.md"
txt = P.read_text(encoding="utf-8")

SEC = """#### 6.3.9 v1.7：审批等待跟着记忆进库——重启、点旧会话都读得出那一格（V9）

**范围就一张单。** V9＝6.3.8 边界 ① 自己立下的那单。`my_ui.py` **1,205 → 1,253 行**（63,316 → **67,362 B**，字符 50,717 → 53,019，对 `.rollback/v1.6` 的 `diff` 净 **`+85 / −37`**、15 个 hunk）。`my_coding_agent.py` **204 行 / 8,355 B 未动**，上游源码零改动；**库 schema 也零改动**——`memory` 表还是那三列，本轮只往 payload 那串 JSON 里加一个**可选**键 `wait`。

**基线四条事实决定了写法**（`/tmp/v17_base_v16.py` → `/tmp/v17_base_v16.out`，**被测模块换成归档的 `.rollback/v1.6/my_ui.py`**：上线之后真实库里已经多了一条真 v2 payload，拿现网代码原样重跑会把"缺口复现"跑成"缺口已关"；**13 条全 PASS**）：

- **A 缺口本体**：活进程里那一格看得见（`task_wait 0.61s`、pill 在），但落库那串里**根本没有 `wait` 这个键**——payload 出现过的键就八个（`_t / is_final_answer / observations / step_number / task / timing / token_usage / tool_calls`），`fmt` 仍是 `v1`。
- **B 回灌读不出**：同一个库起第二个 `OpsUI`、`_bind_memory` 回灌之后 `task_secs 0.66`（V6 的口径在）、**`task_wait 0.0`** → 缺口坐实在"只有等待读不出"。**同一节顺手推翻了 v1.6 的一句注释**：屏上那张历史卡**一直带着**「（含审批 …）」（卡片正文走 `messages` 表，实测 4 条消息里 1 条含"含审批"）→ 真缺口只在 `_stats` / 状态条这一串数，不在卡片。
- **C 光进库没有出口**：「点一条旧会话」这条路**不回灌记忆**（`_bind_memory` 只在 `_respond` 开头），切到甲之后状态条仍是 `步数 0/8`。所以 V9 必须同时给状态条一个**读屏幕上这一条**的出口，否则这一格进了库也看不见。
- **D 改动点不在显示层**：只把秒数挂回 step 对象的 `_opsui_wait`，pill、步骤卡标题、正文累计行**三处零改动**就显示（D1/D2 绿）→ 该动的是编解码。

```mermaid
flowchart LR
    subgraph OLD["V8 那条链，本轮一字未动"]
        W1["decide 那一刻记 waited<br/>my_ui.py:390"] --> W2["类级 _pending_wait 过账<br/>门槛 0.05 在此 :609-611"]
        W2 --> W3["ActionStep 到达时一次取干<br/>payload._opsui_wait :897-901"]
    end
    W3 --> E1["encode_memory：真等过才写<br/>row 多一个 wait 键 :162-168"]
    E1 --> DB[("SQLite memory.payload<br/>fmt 升到 v2 :63<br/>v1 的行不会被回写")]
    DB --> D1["decode_memory：fmt 认 v1 与 v2<br/>:179-180 兼容读"]
    D1 --> D2["挂回同一个私有属性<br/>:225-229，v1 没这键就读作 0"]
    D2 --> S1["_stats 的 task_wait :769<br/>（steps 参数是本轮加的 :749-752）"]
    S1 --> UI1["状态条「本题审批」pill<br/>:792-793"]
    SS["_session_steps sid :988-1004<br/>进程有这份就读它的 steps<br/>没有就 decode 库里那一串（只读）"] --> S1
    C1["点旧会话 _select_session :1160"] --> SS
    C2["刷新 _on_load :1178-1180<br/>＝重启后第一次看"] --> SS
```

**六处分工，每一处都只有几行。** ① `MEM_FMT = "v2"`（`:63`）＋ `MEM_FMT_READ = ("v1", "v2")`（`:68`）——升版本必须带兼容读，注释里点名那条反面证据（真实库那 7 条 payload 在 strict v2 下全读空＝基线 E1）。② `MEM_FIELDS`（`:69-84`）**一字未动**，后面补了注释说明为什么：这张表的口径是"下一轮**模型**读到的字段"，而 `wait` 和 `timing`、`token_usage` 同一类——界面用、`to_messages()` 不认（`:85-88`）。③ `encode_memory` 的 ActionStep 分支多写一格（`:162-168`），**只有真等过才写**、0 不占位，所以没审批的会话编出来和 v1.6 逐字相同（只差 `fmt` 那两位），库里体积不涨。④ `decode_memory`：版本判定从 `!= MEM_FMT` 改成 `not in MEM_FMT_READ`（`:179-180`，认不出的 v0／将来的 v3 **仍旧整块当没记忆，不猜着读**），ActionStep 分支从"一路 `append(构造调用)`"改成"先 `step = ActionStep(...)` 再决定挂不挂属性"（`:203-229`）。⑤ `_stats(steps=None)`（`:749-752`）与 `_status_html(state, steps=None)`（`:782`）：**不传参就是原样读 `agent.memory`**（老调用点一个都没动，7r 断言的就是这句），传了就读那一条会话自己的步骤。⑥ 新增 `_session_steps(sid)`（`:988-1004`）→ 接到 `_select_session`（`:1160`）和 `_on_load`（`:1178-1180`）这两个入口上。

**为什么不做成"点旧会话时顺手 `_bind_memory`"**：那条路会把 worker 线程正在读的记忆换掉（`_bind_memory` 上那条"刻意不做"写着的理由），V5 的语义也不该由一次点击改动。所以这一路是**只读**的：`agent.memory`、`_mem`、`_mem_sid` 一个都不碰（7m/7p 断言）。

**兼容读只朝一个方向——本轮唯一"回滚有代价"的地方。** 基线 E1：只改版本号不做兼容读 → 真实库那 **7 条 v1 payload 在 strict v2 下全体读空**（V6 当场作废）。基线 **E1b**（v1.6 原样的代码、不动 `MEM_FMT`）：它读 v1.7 写的 v2 账**同样读空** → 回滚到 v1.6 之后，**v1.7 期间新建的会话在模型那一边变成"没记忆"**（侧栏还在、屏上字还在，追问会答不记得）。库里 **v1 的行不会被回写升级**：交付形态实测真实库旧 7 行 payload 的 sha1 **逐行不变**，`sessions / messages / memory` 由 7/49/7 变 **8/54/8**——**只追加**。

**实测·探测口 7861**（真 qwen-plus，临时库；先用归档的 `.rollback/v1.6` 编码器**现编两条真 v1** payload 种进去：415 B / 414 B、`fmt=v1`、无 wait——不是手写的假 v1）：

| 判据 | 结果 |
|---|---|
| v1 兼容读的第一面 | 新进程打开页面即 `_on_load` 绑最近一条「v1旧记忆-乙」：`本题耗时 12.5s`、**「本题审批」这格不存在**（`pillWait=null`）——读得动，只是不猜 |
| 挂着审批 20 秒 | 2.0s 进「等待审批」；等待期间 `本题耗时 0.0s`、无「本题审批」、pill `待批 run_python` |
| 点允许之后 | `本题耗时 23.0s` ＋ **`本题审批 20.7s`**、步数 `2/8`、本题 `in 4,789 / out 39`、`Final answer: 21` |
| 落库那一串 | sid 3：**`fmt=v2`**、3 步、**`wait=[20.743, 无]`**（领到账那条 ActionStep 有、`final_answer` 那条没有）、`duration=[22.08, 0.97]`、965 B |
| **真重启**（kill → 同一个库重起 → 只做一次页面加载） | `本题耗时 23.0s / 本题审批 20.7s` ← 新进程的 `_mem` 是空的、一个 `_respond` 都没跑过，**这个数只能来自库里那一格** |
| 重启后点两条 v1 旧会话 | 甲 `本题耗时 41.0s`、乙 `12.5s`，两边**都没有**「本题审批」（兼容读不猜）；侧栏高亮跟着点走 → V7 没回潮 |
| 只读路径没换成绑定 | 刷新／点击之后 `agent.memory` 仍是新进程那一份空的；屏上是甲、条上也报甲，但下一次提问仍落进它自己那条 |

**实测·交付形态 7860**（`我的Agent.app` 真启动器 ＋ 真 qwen-plus，库＝**真实的** `smolagents/.agent-history.sqlite3`）：

| 判据 | 结果 |
|---|---|
| 等待单列 ＋ 进库 | 状态条 `本题耗时 23.4s` ＋ **`本题审批 20.7s`**；`🟢 待批 · run_python · 已允许 · 等了 20.7s`；`🛠 第 1 步 · run_python · 🟢 成功 · 22.1s · 审批 20.7s · in 2,355/out 22`；`🛠 第 2 步 · final_answer · 🟢 成功 · 1.3s · in 2,438/out 17`（**没审批的那一步一格都不多**）；进程 `in 4,793 / out 39` |
| 真实库前后对照（只读脚本） | 7/49/7 → **8/54/8**；**旧 7 行 sha1 逐行不变、零丢失**；新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、1,015 B |
| **真重启（走关闭器）** | `关闭Agent.command` → 重开 → 页面第一次加载即 `本题耗时 23.4s / 本题审批 20.7s` |
| 重启后点一条真 v1 旧会话 | 「用 run_python 打印 4*5 的结果…」→ `本题耗时 1.1s`、**无「本题审批」** |
| 四条关停判据（两轮各一次） | 7860 监听 **0** / Agent 专用 Chrome **0** / `who` 只剩 **console** / Terminal 窗口数 **0** |

**验证与回滚。** 离线 `/tmp/v17_test.py`（venv python，`_stream_response` / `agent.run` 打桩、临时库）**115 条全 PASS、`FAILS: 无`、`exit=0`**＝ v1.6 那 92 条原样搬过来全绿 ＋ **V9 新 22 条**。三条按新口径动过：**2b** 期望 `fmt` 从 v1 改 v2、**6n 直接翻转**（v1.6 断言"`_opsui_wait` 进不了库"，V9 之后它必须进得去，键名是 `wait` 而不是私有属性名）、新增 **2b2**（没等过审批的一题 payload 里没有 `wait`）。V9 这 22 条里要紧的：**7a** 没等过审批的步 v2 编出来与归档 v1.6 编码器**逐字相同**（对照模块用 `importlib` 把 `.rollback/v1.6/my_ui.py` 装进来比）、**7b** 真等过才多写、多的正好是 `, "wait": 12.346` 那 16 字节、**7c** 读回来挂回同一个私有属性（显示层一行没改）、**7d** 模型读到的那一串不掺这一格、**7e/7f** 真实库副本 8 条 payload 全读得回且"新读 v1 == v1.6 读自己那一份"逐字段一样、**7g** 八条往返重编长度差 `[0,0,0,0,0,0,0,0]`、**7h** v1 无 wait 读作 0、**7i** `fmt:"v0"/"v3"` 整块拒读、**7l** 换全新 `AgentMemory` ＋ 新 `OpsUI`、只做一次 `_on_load`（就是"重启后刷新"那一下）那一格自己回来、**7m/7p** 全程只读（`agent.memory` 仍是新那份、`_mem == {}`、点旧会话也不改绑定）、**7n/7p** 屏上是甲、条上就报甲（乙那一题不带那一格，别把甲的等待算给乙）、**7q** 换下一题不继承上一题读回来的等待、**7r** `_stats()` 不传参时行为与 v1.6 逐字相同、**7s** V7 回声守卫没回潮。双向回滚 `cmp` 逐字节一致：v1.6 方向 **92 条**、v1.7 方向 **115 条**（第 7 步改掉那三行过时注释之后**整套重跑过一遍**，`/tmp/v17_drill.sh` → `/tmp/v17_drill_rerun.out`）。

**四条边界。** ① **回滚不是无损的**（E1b 那条）：真要长期退回 v1.6，就把 v1.7 建的会话作废，**别手工去改 payload 里的 `fmt`**——那是改数据不是改代码。② **v1 时代的老账永远没有这一格**：那个数从来没进库，本轮不猜、不补；代价是同一个库里两种格式长期并存，`MEM_FMT_READ`（`:68`）得一直带着。③ **点旧会话仍然不换绑定**：屏上／条上一致了，`agent.memory` 却仍停在上一条提问的会话（V5 的语义，本轮有意不动）→ 点甲看了两眼再提问，问题落进的是新起的那条，不是甲。④ **并行多工具时那一格等待挂在"第一个到达的 `ActionStep`"上**（v1.6 §6.3.8 边界 ④ 就写着），本轮所有题仍是单工具【未验证：多工具并行怎么分这两格】。另有一条**实跑暴露的新单 D8**：正在流式（尤其挂在审批闸上等人点）时刷新或关页面，这一题**一行都不落库**——机制【未验证】，写在 6.3.9 之外、看板 D8 那一行。

"""

ANCHOR = "\n### 6.4 `~/Desktop/我的Agent.app`"
assert txt.count(ANCHOR) == 1, txt.count(ANCHOR)
txt = txt.replace(ANCHOR, "\n" + SEC.rstrip("\n") + "\n" + ANCHOR)
P.write_text(txt, encoding="utf-8")
lines = txt.splitlines()
print("插入完成，README 总行数", len(lines))
for i, ln in enumerate(lines, 1):
    if ln.startswith("#### 6.3.9") or ln.startswith("### 6.4 "):
        print(i, ln[:60])
