# -*- coding: utf-8 -*-
"""把第 7 步的两行「文档闸」写进 迭代记录.md v1.7 的 §4 表（紧跟「回滚演练（双向）」那行之后）。

所有数字都来自本轮留下的证据文件，写之前逐条对着文件核过：
/tmp/v17_readme_recount.out（对齐器在写入前那份 README 上的重跑）、/tmp/v17_readme_full.diff、
/tmp/v17_scan.py（事后两道扫）、/tmp/v17_manual_apply.write、/tmp/v13_htmlcheck.py、
/tmp/v17_manual_gate_1440.out、/tmp/v17_manual_gate_1180.out、/tmp/v17_mmd_readme.out、/tmp/v17_mmd_neg.out。
"""
import io

P = u"/Users/gaoying/Desktop/study/ai学习/迭代记录.md"
t = io.open(P, encoding="utf-8").read()

ANCHOR = u"| **回滚演练（双向）** | ① `cp .rollback/v1.6/my_ui.py → smolagents/`"
assert t.count(ANCHOR) == 1

ROW_A = u"""| **文档闸·README 行号重新对齐**（第 7 步的前半）<br/>`/tmp/v17_map16.json`（difflib v1.6→v1.7 行映射，1,205 个键）＋ `/tmp/v17_readme_align.py`（提议器）＋ `/tmp/v17_readme_apply.py`（落盘器，`OVERRIDE` / `FORCE` / `SKIP` ＋ `--write`）＋ 写入前整份备份 `/tmp/v17_README.before.md`（1,350 行 / 124,886 B）＋ `/tmp/v17_readme.diff` | 提议器逐条判这个号是 v1.6 时代还是更早的号（判据：这句话的标识符/实体与那一版源码块、与 v1.7 目标块的重叠取高者），再按行映射搬到 v1.7，跨度做 def/class 扩展并修剪空行；落盘器按列位置从右往左替换。**四个"讲现状"范围（§6.3 / §8 / §9.1 / §9.4）里 233 条候选引用 → 替换 194 处**，对齐前后**总行数不变 1,350**。判据分布：HIT 181 / other-file 21（讲的是上游那几个文件）/ same-HIT 12 / ZERO 9 / FORCE 5 / SKIP 3 / hist 2。**事后两道扫**（`/tmp/v17_scan.py`，README 讲现状的范围 368 个行号）：越界（`:NNN > 1,253`）**0 条**；指向空行 **1 条**——`:31-36`，是刻意保留的 v1.1 历史号 |"""

ROW_B = u"""| **文档闸·README 现状 ＋ 手册自身**（第 7 步的后半） | **README**：新增 **§6.3.9**（V9 全节：两条读空、机制图、编解码两侧的改动、验证与回滚边界），§6.3 标题与文首口径改到 **1,253 行**，§8 用**三条 V9 场景**（重启后刷新那一格回来 / 点旧会话状态条跟着屏幕上这一条走且全程只读 / 回滚把 v1.7 的账读成没记忆）替换掉 v1.6 立的「已知边界 → V9」那条，§9.1 补 **49、50** 两行，§9.3 补 **10、11** 两条命令，§9.4 第 12 条改「**八轮**」→ **1,350 → 1,445 行**（124,886 → **144,128 B**，`diff` 67 个 hunk、**+214 / −119**）。**Mermaid：块 24 → 25，`块数 25 / 产出 svg 25 / 语法错误 0`；负控 `块数 2 / 产出 svg 2 / 语法错误 1` 且 `exit=1`**（`/tmp/v17_mmd_readme.out`、`/tmp/v17_mmd_neg.out`）——排除"校验器假通过"。<br/>**手册**（`agent功能手册.html`）：**这一轮第一次给它做机器对齐**（v1.6 只对过 README）——`/tmp/v17_manual_align.py` 提议 ＋ 落盘，**112 条候选引用里替换 85 处**（HIT 62 / FORCE 21 / other-file 12 / SKIP 6 / hist 4 / same-HIT 3 / ZERO 2 / same-ZERO 2），对齐这一步**总行数不变 1,182**；再改 §2 标题与页眉版本 → v1.7、§2.1 三行（`my_ui.py` 1,253 / 库 8-54-8 / `.rollback` 16 份 8 套）、§2.5 新增 V9 行并把状态条那行的旧口径换掉、§4 看板 **36 → 37 行**（V9 转已上线、新立 D8、推荐下一刀改 v1.8）、§6 记录节整体 6.1–6.7 → 6.2–6.8 ＋ 4 处手册内部 `§6.x` 交叉引用跟着挪（README 与 `迭代记录.md` 的 `§6.x` 引用**不跟着挪**，那是另一个文件的编号）、新增 **§6.1 v1.7 全节 92 行** → **1,182 → 1,282 行**。**静态闸**：未闭合 `[]`、配对错误 0、外部资源 0、死锚点 `[]`、看板 37 行、`data-st {todo 16, doing 0, done 18, na 3}`、`data-p {D 8, P0 5, P1 8, P2 7, V 9}`。**浏览器闸**（headless Chrome 9333，`/tmp/v17_manual_check_1440.js` / `_1180.js`）：`title` 已是 v1.7、`rows 37`、`tables 32`，十个筛选器 `#cnt` 与可见行数**逐条相符**（`all 37 / bug 8 / p0 5 / p1 8 / p2 7 / v 9 / todo 16 / doing 0 / done 18 / na 3`），`overflowX=false` 在 **1425** 与 **1165** 两档视口都成立，截图 `/tmp/v17-manual.png` **229,146 B**、`/tmp/v17-manual-1180.png` **218,828 B**；输出 `/tmp/v17_manual_gate_1440.out` / `_1180.out`。**手册的事后两道扫**：讲现状的范围（§1–§5、§7）214 个行号，越界 **0** 条，指向空行 **3** 条——`:171` 讲的是 `my_coding_agent.py`（160 字符归属窗口把它错当成 my_ui，假阳性）、`:53-172` 与 `my_ui.py:450-500` 都带版本号、是历史叙述，刻意保留 |"""

ROW_C = u"""| **文档闸自己被抓到并当场修掉的三处**（第 7 步的产物，不是上线前的改动） | ① **页眉漏改**：`<title>` 与 `.meta` 那行还写着 **v1.6**、上线的还是「V7 + V8」——浏览器闸把 `title` 打出来才看见。改成 v1.7 / V9。② **D8 那一行把整页顶成横向滚动**：`overflowX=true`，`scrollW` 在 1,440 档 **1,552**、1,180 档 **1,422**，§4.1 缺陷表的 min-content 从 **1,038 涨到 1,358**（容器 `.wrap` 1,080，右边只有 22px 垫冲抵）。根因**不是长单词**（`overflow-wrap:anywhere`、把 `、` 换成空格都毫无效果，`/tmp/v17_wide4.js`），而是 **CJK 行首禁则**：`（` 之后与 `、` 之前都不许断行，于是「（`/tmp/v17_drain.out`、`/tmp/v17_finish.out`、`/tmp/v17_peek.out`）」被粘成**一个原子块**——`/tmp/v17_bisect.js` 逐节点剔除定位，删掉任意一份文件名就回落 150~166px；再叠加状态胶囊 `white-space:nowrap` 的「未开工（v1.7 新立）」比别的行多占 **46px**（`/tmp/v17_wide9.js` 量到那颗 149px）。修法：冒号引出＋空格分隔三份留痕、把「v1.7 新立」挪出胶囊 → min-content 实测回到 **1,038**（与 D8 之前的那一行逐字相同，`/tmp/v17_fixtry2.js`），两档 `overflowX` 都回到 false。**留痕一个文件名都没删**。③ **一处行号 off-by-one**：`_select_session` 的 V9 注释块三处都写着 `:1149-1153`，而 1,149 是空行、注释实际从 **1,150** 起（`:1150-1153`）——「指向空行」那道扫抓到的，README / 手册 / 本节 §2 的改动清单一起改了。**这条也说明 §2 表里那一行在上线当时就是错的**，不是回写时才写错的 |"""

t = t.replace(ANCHOR, ANCHOR + u"\n" + ROW_A + u"\n" + ROW_B + u"\n" + ROW_C, 1)
io.open(P, "w", encoding="utf-8").write(t)
print("ok lines=%d" % len(t.split("\n")))
