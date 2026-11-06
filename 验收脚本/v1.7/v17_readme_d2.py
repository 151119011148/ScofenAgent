"""第 8 步的 README 回写：§6.1 那张三圈闸门图的行号跟到 D2 之后的实文件、
204→208 行、D2 定性一句话、以及 §9.3/§9.4 里 #6 与验收脚本两条待补销账。"""
import sys
from pathlib import Path

RD = Path(__file__).resolve().parents[2] / "README.md"
lines = RD.read_text(encoding="utf-8").split("\n")
n_before = len(lines)
log = []


def patch(idx, old, new):
    cur = lines[idx - 1]
    if cur.count(old) != 1:
        raise AssertionError(f"L{idx} 里 {old!r} 出现 {cur.count(old)} 次，不是一次")
    lines[idx - 1] = cur.replace(old, new)
    log.append(idx)


# 1) §6.1 标题：文件行数
patch(599, "（204 行）", "（208 行）")

# 2) 三圈闸门图：逐个行号跟到 my_coding_agent.py 现状（D2 的 4 行注释在 DENY_NAMES 上方，
#    所以 32 行以后全部 +4；图中另有几处是更早版本的号，一并对齐）
patch(605, "guarded() :36-46", "guarded() :43-53")
patch(608, "DENY_NAMES? :30", "DENY_NAMES? :37")
patch(611, "read_file :49", "read_file :57")
patch(612, "grep_files :92", "grep_files :100")
patch(613, "write_file :128 → 不落原路径<br/>只写 .agent-staging/ 并回 unified diff :140-154",
      "write_file :136 → 不落原路径<br/>只写 .agent-staging/（:153-155）并回 unified diff :147-152")
patch(614, "run_python :157", "run_python :165")
patch(615, "ast.parse 语法预检 :164-167", "ast.parse 语法预检 :171-174")
patch(616, "requests :168-170", "requests :175-177")
patch(617, "OPENAI_API_KEY :171-175", "OPENAI_API_KEY :178-182")
patch(618, "stdout/stderr 截断 :176-182", "stdout/stderr 截断 :184-189")

# 3) 三圈闸门的实质：把 D2 定性的闭环写进现状描述
patch(621, "（`.agent-staging/`，要你自己 `cp` 才生效）",
      "（`.agent-staging/`，要你自己 `cp` 才生效；`.agent-staging` 同在一进的拒绝名单里，"
      "所以 agent 读不回自己刚暂存的副本——这个闭环是**定性过的**，理由写在 `my_coding_agent.py:32-36`）")

# 4) §9.3 第 6) 条：装过了，注释改成实测口径
patch(1393, "  # 注意 memory 要求 Node >= 24，本机 v22.20",
      "  # 已装：395 包 / node_modules 169 MB；四个 server 各自 package.json 要 node>=24，本机 22.20.0 "
      "只出 EBADENGINE 警告，装与跑都不拦")

# 5) §9.4 第 3 条：体积与 everything 握手已实测
patch(1425, "3. 【待补】MCP servers `npm ci` 之后的体积与 `everything` server 在本机的握手测试。",
      "3. 【已测 2026-10-30】MCP servers 装完：`npm ci` **added 395 packages in 1m**、`node_modules` "
      "**169 MB**、仓库合计 **175 MB**；`npm run build` 后四个 `src/*/dist/` 都在；**4/4 server 起得来并握手**"
      "（`everything` 要传 `stdio` 参数），功能调用四条全通。留痕在 `验收脚本/servers/`"
      "（`npm_ci.out` 2,427 B ＋ `srv_smoke.mjs` / `srv_call*.mjs`）。**没跑**的是 `npm run local:gate`"
      "（那条要联网装依赖并跑全量测试，不在 #6 这一格里）。")

# 6) §9.4 第 12 条：验收脚本已收编
patch(1434, "12. 【待补·等你点头】",
      "12. 【已收编 2026-10-30·你点的「开 验收脚本先点」】",)
patch(1434, "要不要在 `ai学习/` 下开一个 `验收脚本/` 目录按版本号收进来，属于你的决定（新增目录，不落在任何一张工单里）。",
      "现在已经在 **`ai学习/验收脚本/`** 里了：按版本号分目录（`v1.1`~`v1.7` ＋ `gate/` ＋ `servers/`），"
      "**322 个原件**（收编 320 ＋ 本轮新写 2）、**98 份 `run/` 副本**、**70 份**改写前备份、**18 MB**；"
      "**一个文件名都没删**，搬前搬后逐份 sha1 比对 **0 不匹配**。复跑命令按「离线组 / 要浏览器的组」"
      "分在 `验收脚本/README.md`，那里同时写着**哪几条现在跑不得**（v1.6 那套断言在 v1.7 代码上是 "
      "90 PASS ＋ 2 FAIL，红的两条正是 V9 有意改的编解码口径）。")

if len(lines) != n_before:
    raise AssertionError(f"总行数变了：{n_before} -> {len(lines)}")

print(f"改 {len(set(log))} 行：{sorted(set(log))}")
if "--write" not in sys.argv:
    print("DRY-RUN，没写文件")
else:
    RD.write_text("\n".join(lines), encoding="utf-8")
    print("已写入")
