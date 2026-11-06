"""第 8 步收口：验收脚本目录自己的 README 改成收工时的实测数，
补上 manifest 复验账目与 2026-11-01 的复跑结果；顺手修一条跑不通的复现命令。"""
import sys
from pathlib import Path

RD = Path(__file__).resolve().parent.parent / "README.md"
lines = RD.read_text(encoding="utf-8").split("\n")
n0 = len(lines)


def patch(idx, old, new):
    cur = lines[idx - 1]
    if cur.count(old) != 1:
        raise AssertionError(f"L{idx}：{old!r} 出现 {cur.count(old)} 次")
    lines[idx - 1] = cur.replace(old, new)
    return idx


t = []
t.append(patch(22, "（3 / 23 / 25 / 36 / 31 / 68 / **107**），v1.7 最多",
               "（3 / 23 / 25 / 36 / 31 / 68 / **115**），v1.7 最多"))
t.append(patch(23, "| `gate/` | 22 |", "| `gate/` | 24 |"))
t.append(patch(23, "＋ 本轮新写的 `rewrite_tmp_paths.py` |",
               "＋ 本轮新写的 `rewrite_tmp_paths.py`、`manifest_audit.py` 与它的输出 "
               "`manifest_audit_2026-11-01.out` |"))
t.append(patch(24, "| `servers/` | 7 |", "| `servers/` | 9 |"))
t.append(patch(24, "＋ 暂存库副本 ＋ `mcp-echo-server.mjs`",
               "＋ 暂存库副本 ＋ `mcp-echo-server.mjs` ＋ 供应链盘点 `v17_supply_chain.py`/`.out`"))
t.append(patch(25, "| `*/run/` | 98 |", "| `*/run/` | 102 |"))
t.append(patch(
    27,
    "| 合计 | **322 原件** ＋ 98 副本 ＋ 70 备份，18 MB | 322 = 收编进来的 320 ＋ 本轮新写的 2 份"
    "（`gate/rewrite_tmp_paths.py`、`v1.7/v17_d2_assert.py`） |",
    "| 合计 | **336 原件** ＋ 102 副本 ＋ 70 备份，**19 MB** | 336 = 收编 **320**（清单里逐份在册）"
    "＋ **16**：本文件与 `manifest-v1.1-v1.7.sha1` ＋ 本轮写的 14 份 —— 工具 8 份"
    "（`gate/rewrite_tmp_paths.py`、`gate/manifest_audit.py`、`v1.7/v17_d2_assert.py`、"
    "`v17_manual_d2.py`、`v17_readme_d2.py`、`v17_log_d2.py`、`v17_scan3_d2.py`、"
    "`v17_corpus_readme_d2.py`）、留痕 2 份（`servers/v17_supply_chain.py`＋`.out`、"
    "`gate/manifest_audit_2026-11-01.out`）、改前备份 3 份（`v1.7/v17_README.before-d2.md`、"
    "`v17_manual.before-d2.html`、`v17_log.before-d2.md`）、本文件 1 份 |",
))

# 复现命令里 mmd_extract.py 少一个参数（无参直接 IndexError），按实测补上
t.append(patch(
    52,
    "./.venv/bin/python ../验收脚本/gate/mmd_extract.py      # Mermaid：从三份文档抽图块",
    "./.venv/bin/python ../验收脚本/gate/mmd_extract.py ../README.md   # Mermaid：抽 README 的图块"
    "（**必须带文件名参数**，无参直接 `IndexError`；只抽给定的那一份，实测 `blocks: 25`）",
))
t.append(patch(
    53,
    "bash ../验收脚本/gate/mmd_run.sh                        # Mermaid：headless Chrome 渲染，跑负控见 §已知边界",
    "./.venv/bin/python ../验收脚本/gate/run/mmd_check.py ../README.md  # Mermaid：真渲染＋语法错误计数，"
    "实测 `块数 25 / 产出 svg 25 / 语法错误 0`、`exit 0`；负控拿 `v1.7/v17_mmd_neg.md` 跑，"
    "`块数 2 / 产出 svg 2 / 语法错误 1`、`exit 1`",
))
lines.insert(51, "./.venv/bin/python ../验收脚本/gate/manifest_audit.py   # 清单复验：320 条拆成 "
                 "246 相同 / 70 改写 / 4 手工 / **意外 0**")
t.append("insert@52")

# 收编一节补第 6 条：清单复验的账目
t.append(patch(
    38,
    "5. **单独手工补的三处**",
    "5. **收工后复验清单**（`gate/manifest_audit.py`，输出 `gate/manifest_audit_2026-11-01.out`）："
    "320 条里 **246 份逐字节相同**、**70 份**被改写过（它们的改前原文在 `gate/.before-rewrite/` 里，"
    "逐份 sha1 对得上清单）、**4 份**是改写之后又手工动过的"
    "（`v1.5/v15_d7.js` 与 `v1.7/v17_delivery.py` 的动态拼路径、"
    "`v1.7/v17_scan.py` 与 `v17_scan3.py` 在 2026-11-01 改扫描范围），"
    "**谁也解释不了的 0 份**。清单本身不回写、不改：它记的是「搬」这一步没搬坏。\n"
    "6. **单独手工补的三处**",
))

print(f"改 {len(set(t))} 处：{sorted(x for x in t if isinstance(x, int))}")
assert len(lines) == n0 + 1, f"行数应 +1（只插了 manifest_audit 那一行）：{n0} -> {len(lines)}"
if "--write" in sys.argv:
    RD.write_text("\n".join(lines), encoding="utf-8")
    print("已写入")
else:
    print("DRY-RUN")
