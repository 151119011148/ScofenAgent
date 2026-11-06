# 验收脚本

2026-10-30 你点头开的目录（工单：`#6 安装； 开 验收脚本先点；D2 ②；`）。
在此之前，v1.0～v1.7 **八轮**的验收脚本、输出留痕和改写前的整份备份全在 `/tmp`，
记录里每轮都写着同一句「macOS 一重启就没了」——重启之后只能信记录里的数字，命令跑不动。
现在它们在 `~/Desktop/study/ai学习/验收脚本/`，路径已改写到本目录，复跑不再依赖 `/tmp`。

> **本文下面的那些数是 2026-11-01 那场收编的定格读数，不当现状用。** v1.8（11-04）之后本目录又长了两轮：`find . -type f` 现在 **1,726** 个文件 / **105 MB**（2026-11-04 19:05 实测），其中 `run/` 直属留痕 **228** 份、`v1.8/run/chrome-d168/` 那 **1,057** 份是 headless Chrome 缓存（**不是证据，可再生**）。本轮新写的东西在 `v1.8/`：**24** 份 `.py`/`.js`（五套离线断言 `v18_test_{interrupt,plan,p0abc,nochange,dup}.py` ＋ 整版演练 `v18_drill_v18.py` ＋ 零成本回放 `v18_dup_replay.py` ＋ 探针与文档对齐工具）和 `v1.8/run/` 的 **112** 份留痕。**`v1.9/` 那 8 份不属于本轮**，是另一场现场的目录，别按本文的口径去核它。

## 目录怎么分

```
验收脚本/
├── README.md                      本文件
├── manifest-v1.1-v1.7.sha1        收编时的 sha1 清单（320 条）
├── v1.1/ … v1.7/                  按轮次：脚本 ＋ 当时的输出 ＋ run/
├── gate/                          跨轮共用的文档闸工具（Mermaid 渲染器、CDP 客户端、关停判据）
├── servers/                       #6 MCP servers 的安装与冒烟留痕
└── */run/                         一次性产物目录（脚本复跑时写这里，随时可整删）
```

| 目录 | 原件数 | 说明 |
|---|---|---|
| `v1.1/`～`v1.7/` | 305 | 七轮的脚本与留痕（3 / 23 / 25 / 36 / 31 / 68 / **119**），v1.7 最多；**含 15 份带 `.before` 字样的当时快照**（v1.5 1 ／ v1.6 2 ／ v1.7 12，文档改前副本为主），与 `gate/.before-rewrite/` 那 70 份是两回事 |
| `gate/` | 24 | `mmd_extract.py` / `mmd_check.py` / `mmd_run.sh` / `mmd_run2.sh` / `mermaid.min.js`（3.5 MB，离线渲染用）/ `cdp.js` / `agent-win-close.sh(.scpt)` / `agent-win-detach.py` / `agent-ui-start.sh` ＋ 本轮新写的 `rewrite_tmp_paths.py`、`manifest_audit.py` 与它的输出 `manifest_audit_2026-11-01.out` |
| `servers/` | 9 | `npm_ci.out`（395 包那份原始输出）＋ 4 份冒烟脚本 ＋ 暂存库副本 ＋ `mcp-echo-server.mjs` ＋ 供应链盘点 `v17_supply_chain.py`/`.out` |
| `*/run/` | 110 | 改写时按同名铺的副本 98 份 ＋ 11-01 新写的 12 份复跑输出：D2 那 4 份（`v17_test_d2.out`、`v17_d2_assert_d2.out`、`v17_manual_gate_d2_1440.out`／`_1180.out`）＋ 收尾复跑 8 份（`v17_htmlcheck_1101.out`、`v17_scan_1101b.out`、`v17_scan3_1101b.out`、`v17_mmd_extract_1101.out`、`v17_mmd_check_1101.out`、`v17_mmd_neg_1101.out`、`v17_manual_gate_1101b_1440.out`／`_1180.out`），见下节 |
| `gate/.before-rewrite/` | 70 | 70 个被改写脚本的改写前原文 |
| 合计 | **340 原件** ＋ 110 副本 ＋ 70 备份 ＝ **520 个文件**，**20 MB** | 520 用 `find . -type f \| wc -l` 量；340 = 收编 **320**（清单里逐份在册，且逐份仍在——`清单有但已不在 0 份`）＋ 收编之后新写的 **20**：本文件与 `manifest-v1.1-v1.7.sha1` ＋ 这轮写的 18 份 —— 工具 9 份（`gate/rewrite_tmp_paths.py`、`gate/manifest_audit.py`、`v1.7/v17_d2_assert.py`、`v17_manual_d2.py`、`v17_readme_d2.py`、`v17_log_d2.py`、`v17_scan3_d2.py`、`v17_corpus_readme_d2.py`、`v17_corpus_rerun_d2.py`）、留痕 3 份（`servers/v17_supply_chain.py`＋`.out`、`gate/manifest_audit_2026-11-01.out`）、改前备份 6 份（D2 那组的 `v1.7/v17_README.before-d2.md`、`v17_manual.before-d2.html`、`v17_log.before-d2.md` ＋ 收尾体量那组的 `v17_README.before-vol.md`、`v17_manual.before-vol.html`、`v17_log.before-vol.md`）；其余 12 份复跑输出在 `run/`，计进上面那 110 |

## 收编这一步做了什么（数字都是当场量的）

1. **搬**：`/tmp` 里 `v1*` / `srv_*` / `mcp-*` / `npm_ci*` / `mmd*` / `mermaid.min.js` / `cdp.js` / `agent-win*` 共 **320 个文件**（第一批 299 个 7.07 MB，第二批 gate/ 21 个）搬进来；搬前逐份 `shasum -a 1`，落位后逐份比对，**0 个不匹配**（清单在 `manifest-v1.1-v1.7.sha1`）。
2. **没搬的**：`/tmp` 里剩下的 **18 个目录**（`v17-chrome`、`mmd-profile`、`v15-cdp-doc` 等 Chrome profile 缓存，合计约 186 MB）是可再生缓存，不是证据，原地留着；`find /tmp -maxdepth 1 -name 'v1*' -type f` 现在 **0 个**。
3. **改写**：`gate/rewrite_tmp_paths.py` 把脚本里硬编码的 `/tmp/<名字>` 改成本目录绝对路径。规则只有一条安全边界——**只改「已经收进本目录的文件名」**，其余 `/tmp` 引用原样留着，否则 `gate/mmd_run2.sh` 里那句 `rm -rf /tmp/mmd-profile2` 会被改成指向语料库的删除命令。
   - 扫 124 个可执行文本，**70 个被改写**（第一批 68 ＋ 第二批 2），共 **97 条去重规则**；改写前每份都备份进 `gate/.before-rewrite/`。
   - **只改可执行文件**（`.py .js .mjs .sh .scpt` ＋ mmd 的三个 html 外壳）。证据文件（`.out .log .diff .txt .json .md .png .sqlite3`）里的 `/tmp` 路径**一个字都没动**——那是当时的实录，改了就等于篡改证据，而且会让 manifest 的 sha1 全部失配。
   - 归档的源码快照也不改：`v1.2/v12-ca.py`（当时代码长什么样）。`v1.4/v14_ui.py` / `v1.5/v15_ui.py` 看着像快照、其实是在线探测口的启动器，所以第二轮放开了。
4. **落到 `run/` 而不是轮次目录本身**：脚本里有删自己产物的写法（`v1.6/v16_seed.py` 开局 `db.unlink()`、`v1.3/v13_test.py` 反复 `EFFECT.unlink()`），路径若指向原件就会把归档证据删掉。所以 `run/` 是复跑产物区，轮次目录里的原件一动不动。
5. **收工后复验清单**（`gate/manifest_audit.py`，输出 `gate/manifest_audit_2026-11-01.out`）：320 条里 **246 份逐字节相同**、**70 份**被改写过（它们的改前原文在 `gate/.before-rewrite/` 里，逐份 sha1 对得上清单）、**4 份**是改写之后又手工动过的（`v1.5/v15_d7.js` 与 `v1.7/v17_delivery.py` 的动态拼路径、`v1.7/v17_scan.py` 与 `v17_scan3.py` 在 2026-11-01 改扫描范围），**谁也解释不了的 0 份**。清单本身不回写、不改：它记的是「搬」这一步没搬坏。
6. **单独手工补的三处**（动态拼路径，规则抓不到）：`v1.7/v17_live.py` 与 `v1.7/v17_delivery.py` 的 `"/tmp/v17_%s.json" % phase`、`v1.5/v15_d7.js` 的 `"/tmp/v15-d7-" + TAG + ".png"` → 全改到各自的 `run/`；另有 8 份脚本里的 `sys.path.insert(0, "/tmp")`（为了 `from v16_cfg import …`）改成 `parents[1] / "v1.6"`。

## 复跑命令

离线、零模型调用、零网络的一组（今天全部跑过，见下节实测数）：

```sh
cd ~/Desktop/study/ai学习/smolagents
./.venv/bin/python ../验收脚本/v1.7/v17_test.py         # 115 条离线断言（V9 那轮）
./.venv/bin/python ../验收脚本/v1.7/v17_d2_assert.py    # 15 条：D2 故意闭环
./.venv/bin/python ../验收脚本/v1.6/v16_test.py         # 92 条（在 v1.7 代码上 90/2，见「已知不等价」）
./.venv/bin/python ../验收脚本/v1.7/v17_scan.py         # 文档闸·行号点扫（越界 / 指向空行）
./.venv/bin/python ../验收脚本/v1.7/v17_scan3.py        # 文档闸·范围端点扫
./.venv/bin/python ../验收脚本/v1.3/v13_htmlcheck.py    # 手册 HTML 静态闸（标签配对＋看板行数）
./.venv/bin/python ../验收脚本/gate/manifest_audit.py   # 清单复验：320 条拆成 246 相同 / 70 改写 / 4 手工 / **意外 0**
./.venv/bin/python ../验收脚本/gate/mmd_extract.py ../README.md   # Mermaid：抽 README 的图块（**必须带文件名参数**，无参直接 `IndexError`；只抽给定的那一份，实测 `blocks: 25`）
./.venv/bin/python ../验收脚本/gate/run/mmd_check.py ../README.md  # Mermaid：真渲染＋语法错误计数，实测 `块数 25 / 产出 svg 25 / 语法错误 0`、`exit 0`；负控拿 `v1.7/v17_mmd_neg.md` 跑，`块数 2 / 产出 svg 2 / 语法错误 1`、`exit 1`
```

需要在浏览器 / 真库上跑的（**跑之前先确认没有并发会话**）：

```sh
# 浏览器闸：先起 9333 上的 headless Chrome（--remote-allow-origins 要加引号），
# 脚本里的 FILE 常量指向 agent功能手册.html，两档视口分别 1,440 与 1,180
node ../验收脚本/v1.7/v17_manual_check_1440.js
node ../验收脚本/v1.7/v17_manual_check_1180.js

# MCP servers 冒烟：cwd 必须在 servers/，靠的是仓库里的 node_modules
cd ~/Desktop/study/ai学习/servers && node --input-type=module < ../验收脚本/servers/srv_smoke.mjs
```

`v17_drill.sh`（双向回滚演练）与三份 `v1*_readme_*` / `v1*_manual_*` 写入器**不要顺手复跑**：
前者会把 `.rollback/` 里的归档 `cp` 回 `my_ui.py`，后者会往现在的 README / 手册里写它们那一轮的内容。
要复跑先把目标改成副本。

## 在新位置复跑的结果（2026-10-30 首轮 ＋ 2026-11-01 第 8 步全部复跑）

| 命令 | 结果 |
|---|---|
| `v1.7/v17_test.py` | **115 PASS，`FAILS: 无`，exit 0**（临时库，零模型调用） |
| `v1.7/v17_d2_assert.py` | **15 PASS，exit 0**；负控两条：拿未加注释的归档跑，2b/2c/2d 三句定性语都不在 → 会红；把 `MAX_LINES 300→299` 或改任一工具 docstring，1a 的整树 AST 比对立刻红 → 这条断言不是空转 |
| `v1.6/v16_test.py` | 90 PASS ＋ 2 FAIL（见「已知不等价」） |
| `servers/srv_smoke.mjs` | 4/4 握手成功：memory 9 工具 / sequentialthinking 1 / everything 16 / filesystem 14 |
| `gate/rewrite_tmp_paths.py` | 改写脚本本身可重跑，幂等：第二轮只剩 2 个新放开的路径可改 |
| `v1.7/v17_test.py`（11-01 复跑） | **115 PASS、`FAILS: 无`、exit 0** → 输出 `v1.7/run/v17_test_d2.out`（临时库，零模型调用） |
| `v1.7/v17_d2_assert.py`（11-01 复跑） | **15 PASS、exit 0** → `v1.7/run/v17_d2_assert_d2.out` |
| `v1.3/v13_htmlcheck.py`（11-01） | 未闭合 `[]`／配对错误 **0**／外部资源 **0**／死锚点 `[]`／看板 **37** 行；`data-st {todo 16, doing 0, done 18, na 3}`（D2 定性后**仍留在 `na`**，所以一格没动）、`data-p {D 8, P0 5, P1 8, P2 7, V 9}` |
| `v1.7/v17_scan.py`（11-01，范围已按三份文档新行数重推） | README **368 个号 / 越界 0 / 指向空行 1**、手册 **238 / 0 / 2**、迭代记录 **39 / 0 / 0**。那 3 条全是该留的：`:31-36`（v1.1 独立统计卡的历史号）、`:53-172`（v1.2 的 `DARK_CSS`，带版本号）、`my_ui.py:450-500`（v1.4 历史号） |
| `v1.7/v17_scan3.py`（11-01） | README 133 区间 **1** 条、手册 105 **2** 条、迭代记录 17 **1** 条，合计 **4**：`85-88` 本身就是 `MEM_FIELDS` 下面那段注释（终点落在注释开场行是他的判据不看注释），`53-172` 是 v1.2 历史号。**这一轮由它抓出并改掉 3 处真错**——手册 L196 / L486 / L502 把 `MEM_FIELDS` 写成 `:69-88`，表其实到 `:84` 收口 |
| `gate/mmd_extract.py ../README.md` ＋ `gate/run/mmd_check.py ../README.md`（11-01） | **块数 25 / 产出 svg 25 / 语法错误 0**、`exit 0` |
| 负控 `gate/run/mmd_check.py v1.7/v17_mmd_neg.md`（11-01） | **块数 2 / 产出 svg 2 / 语法错误 1**、`exit 1`——不跑负控就不算通过 |
| `v1.7/v17_manual_check_1440.js` / `_1180.js`（11-01） | 两档都 `rows 37`、`tables 32`、十个筛选器与 `#cnt` 逐条相符（`all 37 / bug 8 / p0 5 / p1 8 / p2 7 / v 9 / todo 16 / doing 0 / done 18 / na 3`）、`overflowX=false`（`inner==scrollW`：1425 与 1165）→ 输出 `v1.7/run/v17_manual_gate_d2_1440.out`／`_1180.out`。**截图与 v1.7 归档逐字节相同**（sha1 `e9cef58b…` / `35ef88cc…`）：本轮改的三处都在首屏之下，所以截图本轮的证据价值只有「首屏没被 §5.1 新增那一行挤坏」，宽度证据在上面那两个数里 |
| 体量回写之后再复跑一遍同一组（11-01 收尾） | 静态 `v1.7/run/v17_htmlcheck_1101.out`：未闭合 `[]`／配对 **0**／外部 **0**／死锚 `[]`、看板 **37**、`data-st {16,0,18,3}`；点扫 `v1.7/run/v17_scan_1101b.out`：README **368 / 0 / 1**、手册 **238 / 0 / 2**、迭代记录 **39 / 0 / 0**；端点扫 `v1.7/run/v17_scan3_1101b.out`：区间 **133 ＋ 105 ＋ 17**、剩 **4** 条定性保留、`exit 0`；Mermaid `v1.7/run/v17_mmd_extract_1101.out` ＋ `v1.7/run/v17_mmd_check_1101.out`：**25 / 25 / 0**、`exit 0`，负控 `v1.7/run/v17_mmd_neg_1101.out`：**2 / 2 / 1**、`exit 1`；浏览器 `v1.7/run/v17_manual_gate_1101b_1440.out`／`_1180.out`：`rows 37`、`tables 32`、`overflowX=false`（`inner==scrollW`：1425 与 1165），两张截图与 v1.7 归档 **sha1 仍相同**（`e9cef58b9a00932c225cc1ca8b445054bbf03e2c`／`35ef88cc903f1c53a2b93d4fa2c44ab1481efc4a`） |
| `gate/manifest_audit.py`（11-01） | 320 条 → **246 逐字节相同 / 70 改写（改前原文在 `gate/.before-rewrite/` 且对得上清单）/ 4 改写后手工动过 / 意外 0** |
| `servers/v17_supply_chain.py`（11-01） | **363 个包**、`preinstall/install/postinstall` **0**、`gypfile` **0**、声明 `prepare` 的 30 个；输出 `servers/v17_supply_chain.out` |
| `servers/srv_smoke.mjs`（11-01 没重跑） | 上一轮 **4/4 握手**（memory 9 / sequentialthinking 1 / everything 16 / filesystem 14）；本轮没动 `servers/` 的代码，只补了供应链盘点 |

## 已知不等价（不是坏了，是口径变了）

`v1.6/v16_test.py` 在 v1.7 的 `my_ui.py` 上是 **90 PASS ＋ 2 FAIL**，红的那两条正是 V9 有意翻转的语义：

- **2b** 期望 `json.loads(pay1)["fmt"] == "v1"` —— V9 起写的是 `v2`。
- **6n** 期望 `_opsui_wait` **进不了库** —— V9 起它必须进得去，键名是 `wait`。

v1.7 那轮已经把这两条按新口径改基线并搬进 `v17_test.py`（另加 2b2 与第 7 节 22 条），
所以**别拿 v1.6 套件的绿灯当验收**；它是 v1.6 代码的尺子。回滚演练要的绿灯是：`.rollback/v1.6` 那份代码上 v1.6 套件 92 全绿，`.rollback/v1.7` 那份上 v1.7 套件 115 全绿。

## 还欠的两件事

1. **`run/` 与 `.before-rewrite/` 会随复跑变大**，整删不影响归档证据；删之前先跑 `shasum -a1 -c` 抽验 manifest。
2. **Chrome profile 缓存 18 个目录 ≈ 186 MB 仍在 `/tmp`**（`mmd_run*.sh` 每次重跑会自建），没收进来也不该收；要清就单开一次点头。
