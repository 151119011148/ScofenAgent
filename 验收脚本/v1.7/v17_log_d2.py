"""第 8 步：迭代记录里 #6 那条的数字改成可复现的实测号，并补一条「文档回写」留痕。"""
import sys
from pathlib import Path

LOG = Path(__file__).resolve().parents[2] / "迭代记录.md"
lines = LOG.read_text(encoding="utf-8").split("\n")


def patch(idx, old, new):
    cur = lines[idx - 1]
    if cur.count(old) != 1:
        raise AssertionError(f"L{idx} 里 {old!r} 出现 {cur.count(old)} 次")
    lines[idx - 1] = cur.replace(old, new)
    return idx


touched = []

# 1) 体积与包数：换成当场可复跑的三条命令报出的数
touched.append(patch(
    131,
    "exit **0**、新增 **395 包**、`node_modules` **175 MB**（共 403 个包）",
    "exit **0**、`npm ci` 报 **added 395 packages in 1m**、`du -sh node_modules` **169 MB**"
    "（仓库合计 `du -sh .` **175 MB**）、`npm ls --all --parseable | wc -l` **396**（＝395 依赖＋根）",
))

# 2) 供应链那条：原来那句「403 个包 / 只有 prepare（4 workspace ＋ 5 自家 dev 包）」按号不对，
#    重扫一遍落成可复现的口径
touched.append(patch(
    131,
    "供应链面：403 个包里带生命周期脚本的只有 `prepare`（4 个 workspace ＋ 5 个自家 dev 包），"
    "**没有第三方 install/postinstall 代码被执行过**。",
    "供应链面（2026-10-30 下午重扫，脚本 `验收脚本/servers/v17_supply_chain.py`）："
    "`node_modules` 里按 npm 的目录约定认得出 **363 个包**，带 `preinstall`／`install`／`postinstall` 的 "
    "**0 个**，`gypfile`（会拉 node-gyp 编译）的 **0 个**；声明 `prepare` 的 **30 个**——`npm ci` 从 tarball "
    "装依赖不执行依赖自己的 `prepare`，本机唯一真跑过的 lifecycle 是那 4 个 workspace 的 `prepare`"
    "（留痕＝`src/*/dist` 的时间戳 15:06–15:07）【未验证：这条是 npm 语义＋时间戳推断，没有做 strace 级确认】。"
    "整树再拿 `grep -rlE` 扫 `preinstall|postinstall|install` 三种键（脚本与输出见 "
    "`验收脚本/servers/v17_supply_chain.py` / `v17_supply_chain.out`）：命中 **5 个文件**，"
    "其中 4 个是 `.js`／`.mjs`／`.d.ts` 里的字符串（`jju/index.js`、`package-manager-detector/dist/commands.mjs`、"
    "`typescript/lib/lib.webworker.d.ts`、`vite/dist/node/chunks/node.js`），"
    "唯一的 manifest 命中是 `resolve/test/resolver/multirepo/package.json` —— 那是 `resolve` 自带的测试夹具、"
    "不是被安装的包，npm 不会执行它。**结论：第三方 install 钩子代码 0 段。**",
))

# 3) §8 追加一条：三份文档的回写本身也要留痕
bullet = (
    "- **第 8 步的文档回写（三份，全部逐行替换、不增删行）**：**手册 10 行**——§4.1 标题把 D2 从"
    "「待你定性」改成「已定性：故意闭环，不改行为」、D2 那三格（证据补 `:32-36` 注释位置、手段格改成"
    "「已做 ＋ 15 条断言 ＋ AST 同形 ＋ 负控」、胶囊 `已定性·不改行为`——`data-st` 有意**留在 `na`**，"
    "所以筛选计数 `na 3` 一格没动，看板仍是 37 条）、§4 推荐区那句、§6.1 体量、§6.1 遗留两条"
    "（顺手修掉那一行里混进 HTML 的 **2 处 markdown 反引号**——`v17_scan3.py` 抓出来的旧伤）、"
    "§7 那条【待补】改【已收编】；**README 15 行**——§6.1 标题 204 → 208 行、那张三圈闸门图里 **9 处行号**"
    "跟到 `my_coding_agent.py` 现状（其中 `DENY_NAMES :30`、`read_file :49` 这几处比 D2 之前就更旧，"
    "一并对齐）、三圈闸门的实质那句补上 D2 的闭环、§9.3 第 6) 条与 §9.4 第 3、12 条销账；"
    "**本节**加第 10 项与这条。工具脚本 `验收脚本/v1.7/v17_manual_d2.py`、`v17_readme_d2.py`"
    "都是**先断言锚点再落盘**，改前副本 `v17_manual.before-d2.html`、`v17_README.before-d2.md`。"
)
if not any("第 8 步的文档回写" in l for l in lines):
    lines.insert(134, bullet)
    touched.append("insert@135")

print(f"改/插：{touched}")
print(f"总行数 {len(lines)}")
if "--write" in sys.argv:
    LOG.write_text("\n".join(lines), encoding="utf-8")
    print("已写入")
else:
    print("DRY-RUN")
