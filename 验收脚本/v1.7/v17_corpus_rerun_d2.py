"""验收脚本 README：加 2026-11-01 的复跑账。"""
import sys
from pathlib import Path

RD = Path(__file__).resolve().parent.parent / "README.md"
lines = RD.read_text(encoding="utf-8").split("\n")
n0 = len(lines)

if "2026-11-01" not in lines[73]:
    assert "今天（2026-10-30）" in lines[73], lines[73]
    assert lines[81].startswith("| `gate/rewrite_tmp_paths"), lines[81]
    assert lines[82].strip() == "", repr(lines[82])
    lines[73] = "## 在新位置复跑的结果（2026-10-30 首轮 ＋ 2026-11-01 第 8 步全部复跑）"
else:
    raise AssertionError("标题已经改过了，别重复插行")

rows = [
    "| `v1.7/v17_test.py`（11-01 复跑） | **115 PASS、`FAILS: 无`、exit 0** → 输出 `v1.7/run/v17_test_d2.out`（临时库，零模型调用） |",
    "| `v1.7/v17_d2_assert.py`（11-01 复跑） | **15 PASS、exit 0** → `v1.7/run/v17_d2_assert_d2.out` |",
    "| `v1.3/v13_htmlcheck.py`（11-01） | 未闭合 `[]`／配对错误 **0**／外部资源 **0**／死锚点 `[]`／看板 **37** 行；`data-st {todo 16, doing 0, done 18, na 3}`（D2 定性后**仍留在 `na`**，所以一格没动）、`data-p {D 8, P0 5, P1 8, P2 7, V 9}` |",
    "| `v1.7/v17_scan.py`（11-01，范围已按三份文档新行数重推） | README **368 个号 / 越界 0 / 指向空行 1**、手册 **238 / 0 / 2**、迭代记录 **39 / 0 / 0**。那 3 条全是该留的：`:31-36`（v1.1 独立统计卡的历史号）、`:53-172`（v1.2 的 `DARK_CSS`，带版本号）、`my_ui.py:450-500`（v1.4 历史号） |",
    "| `v1.7/v17_scan3.py`（11-01） | README 133 区间 **1** 条、手册 105 **2** 条、迭代记录 17 **1** 条，合计 **4**：`85-88` 本身就是 `MEM_FIELDS` 下面那段注释（终点落在注释开场行是他的判据不看注释），`53-172` 是 v1.2 历史号。**这一轮由它抓出并改掉 3 处真错**——手册 L196 / L486 / L502 把 `MEM_FIELDS` 写成 `:69-88`，表其实到 `:84` 收口 |",
    "| `gate/mmd_extract.py ../README.md` ＋ `gate/run/mmd_check.py ../README.md`（11-01） | **块数 25 / 产出 svg 25 / 语法错误 0**、`exit 0` |",
    "| 负控 `gate/run/mmd_check.py v1.7/v17_mmd_neg.md`（11-01） | **块数 2 / 产出 svg 2 / 语法错误 1**、`exit 1`——不跑负控就不算通过 |",
    "| `v1.7/v17_manual_check_1440.js` / `_1180.js`（11-01） | 两档都 `rows 37`、`tables 32`、十个筛选器与 `#cnt` 逐条相符（`all 37 / bug 8 / p0 5 / p1 8 / p2 7 / v 9 / todo 16 / doing 0 / done 18 / na 3`）、`overflowX=false`（`inner==scrollW`：1425 与 1165）→ 输出 `v1.7/run/v17_manual_gate_d2_1440.out`／`_1180.out`。**截图与 v1.7 归档逐字节相同**（sha1 `e9cef58b…` / `35ef88cc…`）：本轮改的三处都在首屏之下，所以截图本轮的证据价值只有「首屏没被 §5.1 新增那一行挤坏」，宽度证据在上面那两个数里 |",
    "| `gate/manifest_audit.py`（11-01） | 320 条 → **246 逐字节相同 / 70 改写（改前原文在 `gate/.before-rewrite/` 且对得上清单）/ 4 改写后手工动过 / 意外 0** |",
    "| `servers/v17_supply_chain.py`（11-01） | **363 个包**、`preinstall/install/postinstall` **0**、`gypfile` **0**、声明 `prepare` 的 30 个；输出 `servers/v17_supply_chain.out` |",
    "| `servers/srv_smoke.mjs`（11-01 没重跑） | 上一轮 **4/4 握手**（memory 9 / sequentialthinking 1 / everything 16 / filesystem 14）；本轮没动 `servers/` 的代码，只补了供应链盘点 |",
]
lines[82:82] = rows
RD.write_text("\n".join(lines), encoding="utf-8") if "--write" in sys.argv else None
print(f"标题改 1 行、表插 {len(rows)} 行；{n0} -> {len(lines)}")
print("已写入" if "--write" in sys.argv else "DRY-RUN")
