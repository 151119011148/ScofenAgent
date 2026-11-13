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

口径 2026-11-13 他改过一次：`dify/`、`langchain4j/`、`servers/` 三份第三方树，和
`验收脚本/**/run/` 里的证据，**也进仓库**。所以这个脚本从「只收可执行的东西」变成
「按白名单收，依赖产物与浏览器登录态永远不收」。无条件不收的四类（tools/prepush_check.py 兜成硬闸）：
  · 真 `.env`（活凭证只在那里；上游 `.env.example` 那种模板照收，11-13 实测 6 个、0 条真值）
  · `node_modules/ .venv/ __pycache__/ site-packages/ target/` —— 这三份树里 226M 是装出来的，不是源码
  · `run/chrome-*/` 三份浏览器用户目录（`Login Data`／`History`／`Cookies`，149M 真人登录态）
  · `*.pem`／`*.key`／`id_rsa` 这类私钥文件

目录名：仓库里那五只原件住在 `scofenAgent/`。工作区那一格**仍叫 `smolagents/`**，改名要付的代价
当场数过：① `import smolagents` 靠 editable 安装里写死旧绝对路径的 .pth；② 验收脚本里 150 处
`ai学习/smolagents/...` 硬编码（含每份脚本头上的跑法行）；③ 尺子里三道题干原文
（`v20_questions.py:76/110/145`，「读一下 smolagents/.env」那一类）——改题干就和 11-06 那条
72.2% 基线不可比，那是把尺子掰弯。所以改名落在**仓库结构＋文档锚点**：形如 `…/smolagents/my_*.py`
的锚点在仓库副本里改写成 `scofenAgent/my_*.py`（11-13 数过 45 处），`my_` 之外不动——
`smolagents/src`、`.env`、`.venv` 写的都是工作区事实。
代码侧**一个字没动**。这里有一次实测出来的撤回：我先把 `my_agent.py:98` 的
`name="smolagents"` 改成 `"scofenAgent"`，`v18_test_dup.py` 的 9a 当场顶红——那个守卫的
`prompt_surface()`（`v18_test_dup.py:464`）用 ast 收 `ToolCallingAgent(...)` 的
`description` 和 **`name`** 两个关键字，因为它认定 agent 名字是模型读得到的提示词面。
把 name 改回去 9a 立刻回绿（因果是这么隔离的：改回去跑一遍 0 FAIL，改回来 1 FAIL，
其余 11 套两次都全绿）。所以这个字段和题干同一性质：动它＝换尺子，34 次 run 那条
72.2% 基线就此不可比。要真换名，得单开一版尺子重跑基线，那是他的决定，不是改名的顺手账。

跑法：
    python3 tools/sync_from_workspace.py             # 复制＋打清单
    python3 tools/sync_from_workspace.py --check     # 只报「仓库和工作区不一致」的项，不写
    python3 tools/sync_from_workspace.py --no-trees  # 跳过三份第三方树（只改文档时用，快）
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

WS = Path.home() / "Desktop/study/ai学习"
REPO = Path.home() / "Desktop/study/ScofenAgent"

WS_AGENT_DIR = "smolagents"       # 工作区里的真名，不动（理由见文件头）
REPO_AGENT_DIR = "scofenAgent"    # 仓库里的目录名

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

# 3) 第三方参考树＋桌面启动器：进仓库，但只进**源码**（依赖产物见 skip_reason）
REFERENCE_TREES = ["dify", "langchain4j", "servers"]
LAUNCHERS = ["Agent链路详解.app"]   # 3 个文件：launcher + Info.plist + app.icns，1.1M

# 4) 收全部扩展名，除了这两样：
#    · mermaid.min.js —— 文档闸用的 3.4M 第三方渲染库，闸跑的时候现取
#    · 嵌套的 .gitignore —— 第三方树自带的那些会让 `git add` 静默跳过**磁盘上存在**的源文件
#      （上游用它挡构建产物，我们已经在 skip_reason 里自己筛过一遍），带上就等于副本少文件
EXCLUDE_NAMES = {"mermaid.min.js", ".gitignore"}

# 锚点改写：`[任意路径前缀]smolagents/` 且紧接 `my_` → `scofenAgent/`
ANCHOR = re.compile(r"[\w.~/-]*/?smolagents/(?=my_)")

DEP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "site-packages", "target",
            ".git", ".idea", ".agent-staging", ".rollback"}
# 浏览器登录态：Chrome 用户目录里那几样是**没有后缀的裸文件名**，所以按名字逐个拦
BROWSER_NAMES = {"Login Data", "Login Data For Account", "Cookies", "History", "Web Data",
                 "Account Web Data", "Favicons", "Preferences", "Secure Preferences",
                 "visited_links", "Login Data-journal", "Cookies-journal",
                 "Login Data For Account-journal", "History-journal"}
SECRET_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", "netrc"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx"}
MAX_FILE = 8_000_000  # 单文件上限。现值最大是 dify 里 monaco 的 tsWorker.js 5.5M（11-13 实测）


def skip_reason(p: Path, root: Path):
    """这个文件为什么不进仓库；None = 收。"""
    if p.name in EXCLUDE_NAMES:
        return "第三方渲染库（闸用时现取）"
    for part in p.relative_to(root).parts[:-1]:
        if part in DEP_DIRS or part.endswith(".egg-info") or part.startswith("chrome-"):
            return "依赖/产物/浏览器目录 %s/" % part
    if p.name.startswith("chrome-"):
        # 浏览器演练那一格的东西：整目录是登录态（149M），目录外还有两份 Chrome 自己的
        # stderr（chrome-d168.log 388K／chrome-gate18.log 12K，实测内容是 clients2.google.com/cr/report
        # 崩溃上报的碎碎念）。两者都不是本仓库的产物，且闸（prepush_check）按前缀一样拦，
        # 所以这里也一律不收，别出现「sync 复制了、闸门不放行」那种自相矛盾。
        return "浏览器演练产物"
    if p.name in BROWSER_NAMES:
        return "浏览器登录态文件"
    if p.name in SECRET_NAMES or p.suffix.lower() in SECRET_SUFFIXES:
        return "凭证/私钥类文件"
    if p.suffix.lower() == ".pyc":
        return "字节码"
    try:
        if p.stat().st_size > MAX_FILE:
            return "单文件 >8M"
    except OSError as exc:
        return "读不了：%s" % exc
    return None


def targets(include_trees=True):
    for name in AGENT_FILES:
        yield WS / WS_AGENT_DIR / name, Path(REPO_AGENT_DIR) / name, False
    for name in ROOT_DOCS:
        yield WS / name, Path(name), True          # 文档副本要做锚点改写
    roots = ["验收脚本"] + (REFERENCE_TREES if include_trees else [])
    roots += [x for x in LAUNCHERS if (WS / x).is_dir()]
    for sub in roots:
        for p in sorted((WS / sub).rglob("*")):
            if p.is_file() and not skip_reason(p, WS):
                yield p, p.relative_to(WS), False


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写")
    ap.add_argument("--no-trees", action="store_true", help="跳过三份第三方树")
    a = ap.parse_args()

    changed, same, missing, rewritten = [], [], [], 0
    for src, rel, do_anchor in targets(include_trees=not a.no_trees):
        if not src.is_file():
            missing.append((src, rel))
            continue
        data = src.read_bytes()
        if do_anchor:
            text = data.decode("utf-8", errors="replace")
            new = ANCHOR.sub(REPO_AGENT_DIR + "/", text)
            if new != text:
                rewritten += 1
                data = new.encode("utf-8")
        dst = REPO / rel
        if dst.is_file() and dst.read_bytes() == data:
            same.append(rel)
            continue
        changed.append((src, rel, "新增" if not dst.is_file() else "覆盖"))
        if not a.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)

    verb = "需更新" if a.check else "已复制"
    print("复制清单：%d 个文件（未变 %d ／ %s %d ／ 源缺失 %d ／ 锚点改写 %d 份文档）"
          % (len(same) + len(changed), len(same), verb, len(changed), len(missing), rewritten))
    for src, rel, kind in changed[:30]:
        print("  %-56s %s %s" % (rel, sha1(src), kind))
    if len(changed) > 30:
        print("  …另外 %d 项" % (len(changed) - 30))
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
