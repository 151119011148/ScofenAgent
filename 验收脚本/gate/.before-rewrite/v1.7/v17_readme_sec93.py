# -*- coding: utf-8 -*-
"""README §9.3 补 v1.7 两条命令、改掉 #8 那句 v1 口径；§9.4 更新 12/13 两条、补 14-16 条。"""
import pathlib

P = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/README.md")
t = P.read_text(encoding="utf-8")

OLD8 = """#    想看内容：把 payload 交给 python 解析，第一层是 {"fmt":"v1","steps":[…]}
#    回灌没生效的判据是「重启后同一题的 in 回到裸起步 2,363」，肉眼看 token 最快
"""
NEW8 = """#    想看内容：把 payload 交给 python 解析，第一层现在 {"fmt":"v2","steps":[…]}
#    （v1.5~v1.6 攒下的行仍是 "v1"，两边并存、都读得动；库里那一行不会回写升级）
#    回灌没生效的判据是「重启后同一题的 in 回到裸起步」，肉眼看 token 最快
"""
assert t.count(OLD8) == 1
t = t.replace(OLD8, NEW8)

OLD9 = """node /tmp/v15_drive.js                  # CDP 驱动 headless Chrome 跑在线路，需另起 9333 端口
```"""
NEW9 = """node /tmp/v15_drive.js                  # CDP 驱动 headless Chrome 跑在线路，需另起 9333 端口

# 10) v1.7：逐行看 payload 里到底有没有那一格 wait（只读，不改库）
cd ~/Desktop/study/ai学习/smolagents && ./.venv/bin/python /tmp/v17_dump.py
#    输出每条会话的 fmt / wait / duration / 字节数；「真等过才写」的判据就看这里
#    没审批的会话应当**没有** wait 这个键，v1 时代的行应当 fmt 仍是 v1

# 11) 复跑 v1.7 验收与双向回滚演练（同样在 /tmp，见 9.4 第 12 条）
./.venv/bin/python /tmp/v17_test.py     # 离线 115 条（v1.6 那 92 条 ＋ V9 新 22 条），临时库
bash /tmp/v17_drill.sh                  # cp .rollback/v1.6 → 92 条 → cp .rollback/v1.7 → 115 条 → cmp
```"""
assert t.count(OLD9) == 1
t = t.replace(OLD9, NEW9)

OLD12 = "12. 【待补·等你点头】v1.0~v1.6 七轮的验收脚本全在 `/tmp`（`v16_test.py`、`v16_cdp.js`、`v16_delivery.py`、`v16_rollback_check.py`、`v15_test.py`、`v15_drive.js` 等）"
NEW12 = "12. 【待补·等你点头】v1.0~**v1.7 八轮**的验收脚本全在 `/tmp`（`v17_test.py`、`v17_base_v16.py`、`v17_dump.py`、`v17_delivery.py`、`v17_drill.sh`、`v16_test.py`、`v16_cdp.js`、`v16_delivery.py`、`v16_rollback_check.py`、`v15_test.py`、`v15_drive.js` 等；`v16_cdp.js` / `v16_cfg.py` / `v16_read.js` 这三份 CDP 驱动 v1.7 直接复用）"
assert t.count(OLD12) == 1
t = t.replace(OLD12, NEW12)

OLD13 = ("另有一条**写下来的边界**不是待补：「本题审批」跨重启读不出来"
         "（`_opsui_wait` 不进 `MEM_FIELDS`），要收它得升 `MEM_FMT` v2，已立 **V9**。")
NEW13 = ("同一条里那句**写下来的边界**——「本题审批」跨重启读不出来"
         "（`_opsui_wait` 不进 `MEM_FIELDS`）——**已由 v1.7 的 V9 收掉**（`MEM_FMT` 升 v2 ＋ 兼容读 ＋ 状态条读屏幕上这一条）；"
         "收它付出的代价见下面第 15 条。")
assert t.count(OLD13) == 1
t = t.replace(OLD13, NEW13)

FOOT = "\n### 9.5 这套语料的三条下一步"
assert t.count(FOOT) == 1
NEW_ROWS = """
14. 【待补】**D8（v1.7 实跑暴露，两条路都有留痕）**：正在流式（尤其挂在审批闸上等人点）时刷新或关页面，这一题**一行都不落库**——`_respond` 开头已 `hist.ensure` 建了会话行，屏上曾有字，但消息与记忆都没写，那笔审批等待一起蒸发；`待批` 的 pill 挂在已经「空闲」的状态条上、`#approve-btn` reload 后 `NO-ELEMENT`，两次 `until DONE` 分别跑到 **120,353ms** 与 **300,967ms** 超时（`/tmp/v17_drain.out`、`/tmp/v17_finish.out`、`/tmp/v17_peek.out`）。**机制【未验证】**：断开时 `_respond` 的 `finally` 到底跑没跑到（gradio 在客户端断开时是否 `close()` 那条生成器）、阻塞在 `ap.wait()` 的 worker 怎么随断开结算（只能等 `APPROVAL_TIMEOUT=600s` 自己按拒绝结算？）、以及"落半截"和"标已中断"选哪个。v1.5 那句"半截可接受"的前提是半截会落库，实测连半截都没有。**这是 v1.6 就有的行为，不是 V9 的回归**（v1.7 的两轮干净跑通是因为一整轮只发一份 CDP 剧本，不中途 reload）。
15. 【待补】**兼容读只朝一个方向的长期成本**：新代码认 `("v1","v2")`，旧代码只认 `"v1"` → 回滚 v1.6 会把 **v1.7 期间新建的会话读成没记忆**（基线 E1b 实测读空，不是推理）；库里 v1 的行**永远不会**获得 `wait`（旧 7 行 sha1 逐行不变就是这条的断言），同一个库里两种格式长期并存。将来加第三版必须**重演一次 "strict 读空" 的基线**（本轮是 E1）——这不是缺陷，是每次升版本都要付的一次验证。
16. 【待补】**交付形态的日志只留最后一次启动**：启动器用的是 `tee`（覆盖写），本轮收工时 `.agent-ui.log` 只有 2 行 / 106 B，中途那次 21 行已被重开覆盖【未留痕】。要长期留痕得把 `tee` 改成 `tee -a` 或按日期分文件——那是改启动器，不在 V9 范围内。

### 9.5 这套语料的三条下一步"""
t = t.replace(FOOT, NEW_ROWS)
P.write_text(t, encoding="utf-8")
print("ok，总行数", len(t.splitlines()))
