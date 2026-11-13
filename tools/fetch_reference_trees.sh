#!/bin/sh
# 三份「语料」的**来源**在这个脚本里：pin 坐标、怎么取、怎么核。
# 2026-11-13 口径变了一次：他要求三份也进仓库，所以 dify/ langchain4j/ servers/ 现在是
# **仓库里的源码副本**（tools/sync_from_workspace.py 从工作区复制，依赖产物不进）。
# 这个脚本因此从「取回」变成「复现／对账」：换一台机器没有工作区时，用它按同一枚 pin
# 重新取一份，和仓库里那份 diff —— 版本坐标是当场核过的，不是照着版本号猜的。
#
# 当时量过的事实（保留，因为它们决定了仓库里那份的可信度）：
#   · 体积：dify 166M ＋ langchain4j 56M ＋ servers 315M = 537M；其中 **226M 是装出来的**
#     （node_modules 17 个、dist 154 个、__pycache__ 156 个、.venv 2 个、target 3 个），
#     纯源码是 dify 134M／langchain4j 42M／servers 4M（11-13 逐文件走一遍加总的字节数）。
#   · 归属：三份都是别人的源码树。dify/langchain4j 连 .git 都没有（是 tarball/拷贝下来的阅读副本，
#     `git -C dify` 直接 fatal: not a git repository）；servers 是 modelcontextprotocol/servers 的
#     clone，HEAD ef9808f71090d0db3eda99e2af2ba78f1086f4fb，本地只有 1 处漂移
#     （`src/time/uv.lock`，跑 uv 时自己重写的，不是人改的）。三份各带 LICENSE（Apache-2.0／
#     Apache-2.0／MIT），随源码一起进仓库。
#   · 引用计数：README.md／迭代记录.md／面试剖析对照.md／agent功能手册.html 里
#     `dify/` 11 处、`langchain4j/` 11 处、`servers/` 20 处。
#
# 为什么走 codeload tarball 而不是 git clone（同一分钟内的对照实测）：
#   · `git fetch` 走 github.com 这次直接 `fatal: unable to access ... SSL connection timeout`；
#   · 同一时刻 `curl https://codeload.github.com/...` 返回 200，servers 那一份 1,138,414 字节、
#     46.6 秒（24KB/s）拿完 —— 这台机器到 GitHub 的链路一直在 dead↔~35KB/s 之间抖，
#     codeload 是实测能通的那条。三条统一走这一条路，不留第二种代码路径。
#   · 内容等价性是核过的，不是假设的：把 servers 的 pin 包解出来和工作区那份
#     `diff -rq --exclude=.git --exclude=node_modules`，总共只有 7 行差异，其中
#     1 行是 `src/time/uv.lock`（就是那处已知漂移），6 行是 `Only in 工作区: dist / .venv`
#     —— 编译产物和虚拟环境，本来就在 .gitignore 里。也就是说 pin 包和工作区同源。
#
# 用法：
#   cd ~/Desktop/study/ScofenAgent
#   ./tools/fetch_reference_trees.sh servers      # 只取一份（取到 dify/ langchain4j/ servers/）
#   ./tools/fetch_reference_trees.sh --print all  # 只打印将要执行的命令，不下任何东西
# 已存在的目录会跳过不覆盖（要对账就先把它挪开，别直接删仓库里那份）。
#
# 注意：这是**源码**树，不含 node_modules/dist/.venv。文档是按源码行号引的，够用；
# 真要跑这三份里的东西（比如起一个 MCP server），依赖得自己装 —— 那不属于「取回语料」这一步。
set -e
cd "$(dirname "$0")/.."

PRINT=""
case "${1:-}" in
  --print) PRINT=1; shift ;;
esac

run() {
  if [ -n "$PRINT" ]; then echo "  [print] $*"; else echo "  → $*"; "$@"; fi
}

# 参数：目录名 / codeload URL。
# 先落 .tgz.part，解完再删：中途断了不会留下半个目录被下面「已存在」当成取好了。
fetch() {
  dir=$1; url=$2
  if [ -d "$dir" ]; then echo "$dir/ 已存在，跳过"; return; fi
  run curl -sS --fail --retry 3 -o "$dir.tgz.part" "$url"
  run sh -c "mkdir -p $dir && tar xzf $dir.tgz.part --strip-components=1 -C $dir"
  if [ -z "$PRINT" ]; then
    run rm -f "$dir.tgz.part"
    echo "$dir/ 取回完成：$(find "$dir" -type f | wc -l | tr -d ' ') 个文件，$(du -sh "$dir" | cut -f1)"
  fi
}

# 上游 tag/sha 的存在性都是 2026-11-07 用 GitHub API 当场核过的，不是照着版本号猜的。

# dify：工作区 dify/web/package.json 的 version = 1.18.0；上游 refs/tags/1.18.0 存在（API 实测）。
# dify 无 .git，所以这个 tag 是**推**出来的对齐；若文档里的行号跳偏了，以工作区那份为准【待确认】。
DIFY=https://codeload.github.com/langgenius/dify/tar.gz/refs/tags/1.18.0

# langchain4j：工作区 pom.xml 的 <version> = 1.23.0-beta33-SNAPSHOT，是**开发态快照**，和上游
# 最近的发布 tag 1.23.0 不是同一份内容。这条不是脚本的 bug，是原始语料本身没带可复现的坐标 ——
# 文档里引到 langchain4j 的行号在取回来的机器上可能偏几行【待确认】。
LC4J=https://codeload.github.com/langchain4j/langchain4j/tar.gz/refs/tags/1.23.0

# servers：工作区 .git 的 HEAD 是完整 40 位 sha，这一份是精确坐标，取回来和工作区同源
# （等价性见文件头那段 diff -rq）。
SERVERS=https://codeload.github.com/modelcontextprotocol/servers/tar.gz/ef9808f71090d0db3eda99e2af2ba78f1086f4fb

case "${1:-all}" in
  dify)        fetch dify "$DIFY" ;;
  langchain4j) fetch langchain4j "$LC4J" ;;
  servers)     fetch servers "$SERVERS" ;;
  all)         fetch dify "$DIFY"; fetch langchain4j "$LC4J"; fetch servers "$SERVERS" ;;
  *) echo "参数不认识：$1（可用 dify / langchain4j / servers / all，前面可加 --print）"; exit 2 ;;
esac

echo
echo "取回后 git status 应该仍然干净（这三份在 .gitignore 里）："
git status --porcelain | head -5
echo "(上面空=干净)"
