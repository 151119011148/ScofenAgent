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

体量：`my_ui.py` **893 → 1,108 行**（44,838 → **55,774 B**，`diff` 净 **`+217 / −2`**）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.4`、`.rollback/v1.5` 双份一致）。上游 `git status --porcelain` 仍只有三个 untracked 的 `my_*.py`，`git diff --name-only` 行数 **0**。

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

