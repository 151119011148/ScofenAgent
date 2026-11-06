# -*- coding: utf-8 -*-
"""README §9.1 补 49/50 两行（V9）、修 48 行那句过时结论；§9.4 修第 13 条尾巴、补 14-17 条。"""
import pathlib

P = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/README.md")
t = P.read_text(encoding="utf-8")

# ---- 9.1：48 行那句「重启后读不出」在 v1.7 不成立 ----
OLD48 = "**它不在 `MEM_FIELDS`（`:69-84`）里**，所以总时长口径不变、重启后这一格读不出（→ V9） |"
NEW48 = ("**它不在 `MEM_FIELDS`（`:69-84`）里**（那张表的口径是\"下一轮**模型**读到的字段\"），"
         "所以总时长口径不变。v1.6 时这一格只活在进程里、重启读不出——**v1.7 的 V9 收掉了这条边界**，"
         "它现在随记忆进库（见 49 行），而显示层一行没改 |")
assert t.count(OLD48) == 1
t = t.replace(OLD48, NEW48)

ROW49 = ("| 49 | `smolagents/my_ui.py:63` + `:68` + `:162-168` + `:225-229` | "
         "**V9 的全部根据是两条读空**：只把 `MEM_FMT` 升 `v2` 而不做兼容读 → 真实库那 **7 条 v1 payload 在 strict v2 下全体读空**（V6 当场作废）；"
         "反过来 v1.6 原样的代码读 v1.7 写的 v2 账**同样读空**（基线 E1b）——所以兼容读写成 `MEM_FMT_READ = (\"v1\", \"v2\")`，"
         "`wait` 是**可选**键（真等过才写，`round(…, 3)`；v1 没这键就读作 0、**不是把整条会话判成没记忆**），认不出的 `v0`／将来的 `v3` 仍旧整块拒读。"
         "**代价**：兼容读只朝一个方向，回滚 v1.6 会让 v1.7 期间新建的会话变成\"没记忆\"；库里 v1 的行**不会被回写升级**（旧 7 行 sha1 逐行不变就是这条的断言），"
         "所以同一个库里两种格式长期并存、`MEM_FMT_READ` 得一直带着 |")
ROW50 = ("| 50 | `smolagents/my_ui.py:988-1004` → `:1160` / `:1178-1180` | "
         "**光进库没有出口**：状态条那串「本题」的数以前从 `self.agent.memory` 读，而那份记忆只在 `_respond` 开头换——"
         "基线实测「点一条旧会话之后步数仍是 `0/8`」（`_bind_memory` 根本不在点击那条路上）。"
         "V9 加 `_session_steps(sid)`：**进程里有这一份就读它的 steps，没有就按 V6 那条路 decode 库里那一串**，然后只接到 `_select_session` 和 `_on_load` 两个入口上。"
         "**刻意不做**的是在这里顺手 `_bind_memory`：那条路会把 worker 线程正在读的记忆换掉，V5 的语义也不该由一次点击改动（代价见 6.3.9 边界 ③） |")

ANCHOR = "\n\n### 9.2 术语中英对照"
assert t.count(ANCHOR) == 1
t = t.replace(ANCHOR, "\n" + ROW49 + "\n" + ROW50 + ANCHOR)

P.write_text(t, encoding="utf-8")
print("9.1 ok，总行数", len(t.splitlines()))
