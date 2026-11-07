#!/bin/sh
# 推送一条龙：消快照漂移 →（有变化就先 commit）→ 过闸 → push。
# 为什么单独有这个脚本：这台机器的 git 凭证走 osxkeychain，而 keychain 里没有 github.com 的条目，
# 认证必须由人在这块终端上输（用户名 + Personal Access Token）——我不代填、也不去翻你存过的凭证。
set -e
cd "$(dirname "$0")/.."
echo "== 1/4 从工作区重复制（消快照漂移）=="
python3 tools/sync_from_workspace.py
echo
echo "== 2/4 有变化就先补一笔 commit（pre-commit 钩子会再跑一次闸）=="
git add -A
if git diff --cached --quiet; then echo "  快照无变化，不用提交"; else git commit -m "推送前的工作区快照同步"; fi
echo
echo "== 3/4 公开仓库硬闸：活凭证 / 禁入路径 / 体积 =="
python3 tools/prepush_check.py --paths
echo
echo "== 4/4 push（下一步会要你的 GitHub 用户名 + PAT）=="
git push -u origin main
echo
echo "推完了。核对：https://github.com/151119011148/ScofenAgent"
