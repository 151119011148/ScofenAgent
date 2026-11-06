# -*- coding: utf-8 -*-
"""把 live 工作区里该进仓库的东西复制进 ScofenAgent/，并打一份清单。

为什么是**复制**而不是就地建仓库（实测，不是猜）：
  `ai学习/smolagents/` 本身是 huggingface/smolagents 的 git clone（origin 指向它，shallow depth=1）。
  git 把「目录里还有 .git」当作子模块边界：在父仓库里 `git add smolagents/my_agent.py` **返回 0、
  却什么都不暂存**（`git status` 仍是 `?? smolagents/`）；`git add smolagents` 则只登记一个
  gitlink，别人 clone 下来拿到的是**空目录**。也就是说「在 ai学习/ 里 init，直接跟踪那五只原件」
  这条路走不通，除非改掉 smolagents/.git——那是别的仓库的状态，不该为打包动它。
  代价要说死：仓库里那份是**快照**，会漂。所以推送前必须重跑本脚本（下面 1 秒都不到），
  漂移由脚本消掉，而不是靠记性。

故意不进仓库的东西（tools/prepush_check.py 会把这几条变成硬闸）：
  · `smolagents/.env`（活凭证，117 字符的 OPENAI_API_KEY 只在这里）
  · `smolagents/.venv`（290M，装依赖是 `uv sync`／`pip install smolagents` 的事，不是提交的事）
  · `smolagents/src|tests|docs`（上游源码，不 fork 到这个名字的仓库里）
  · 任何 `run/` 目录、`*.out`、`*.log`、`*.png`、`*.sqlite3`、`.agent-*`、`.rollback/`
    —— 里面是**证据**：审计 JSONL 有工具入参原文、会话库有历史答复、`v1.8/run/chrome-d168/`
    是一份真 Chrome 用户目录（Login Data 40K、History 昨天还在写）。公开仓库放这些等于交账户。
  · `dify/`、`langchain4j/`、`servers/`（三份工作区里的第三方克隆，共 537M，都不是本仓库的产物）
  · `.idea/`、`*.app`、图标 png

跑法：
    python3 tools/sync_from_workspace.py          # 复制＋打清单
    python3 tools/sync_from_workspace.py --check   # 只报「仓库和工作区已经不一致」的项，不写
"""

import argparse
import hashlib
import sys
from pathlib import Path

WS = Path.home() / "Desktop/study/ai学习"
REPO = Path.home() / "Desktop/study/ScofenAgent"

# 1) 五只原件：只这几只 my_*.py，上游那 1.2M 的 src/ 不要
AGENT_FILES = ["my_agent.py", "my_audit.py", "my_coding_agent.py", "my_mcp.py", "my_ui.py"]

# 2) 根文档：原文件名原样保留——文档正文里到处是「见 README.md」「见 迭代记录.md」的互指，
#    改名或挪进 docs/ 会把这套互指打断。
ROOT_DOCS = [
    "README.md",
    "迭代记录.md",
    "agent实现原理-一次问话全流程-面试剖析对照.md",
    "agent功能手册.html",
    "agent链路图.html",
    "agent链路详解.html",
]

# 3) 验收脚本：只收**可执行的东西**（脚本＋说明），证据产物一律不进
HARNESS_SUFFIXES = {".py", ".sh", ".js", ".md", ".txt"}
HARNESS_EXCLUDE_NAMES = {"mermaid.min.js"}  # 3.5M 第三方库，用时现取
HARNESS_EXCLUDE_PARTS = {"run", "chrome-d168", "__pycache__", "node_modules", ".before-rewrite"}


def harness_files():
    for p in sorted((WS / "验收脚本").rglob("*")):
        if not p.is_file() or p.suffix.lower() not in HARNESS_SUFFIXES:
            continue
        if p.name in HARNESS_EXCLUDE_NAMES:
            continue
        rel_parts = p.relative_to(WS).parts
        if any(part in HARNESS_EXCLUDE_PARTS for part in rel_parts):
            continue
        yield p


def targets():
    for name in AGENT_FILES:
        yield WS / "smolagents" / name, Path("smolagents") / name
    for name in ROOT_DOCS:
        yield WS / name, Path(name)
    for p in harness_files():
        yield p, p.relative_to(WS)


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写")
    a = ap.parse_args()

    changed, same, missing = [], [], []
    for src, rel in targets():
        if not src.is_file():
            missing.append((src, rel))
            continue
        dst = REPO / rel
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            same.append(rel)
            continue
        changed.append((src, rel, "新增" if not dst.exists() else "覆盖"))
        if not a.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())

    verb = "需更新" if a.check else "已复制"
    print("复制清单：%d 个文件（未变 %d ／ %s %d ／ 源缺失 %d）"
          % (len(same) + len(changed), len(same), verb, len(changed), len(missing)))
    for src, rel, kind in changed:
        print("  %-56s %s %s" % (rel, sha1(src), kind))
    for src, rel in missing:
        print("  !! 源文件不存在，跳过：%s" % src)
    if a.check and changed:
        print("\n--check：仓库和工作区不一致，推送前必须重跑本脚本（不带 --check）")
        return 1
    if not a.check:
        print("\n下一步：python3 tools/prepush_check.py 过闸，再 git add / commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
