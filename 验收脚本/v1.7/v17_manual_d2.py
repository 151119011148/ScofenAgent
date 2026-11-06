"""第 8 步的手册回写：D2 定性 + 验收脚本收编。逐行锚定（同一字符串在历史节里重复出现，
全局替换会误伤 §6.2 的历史原文），断言不过就不落盘。"""
import sys
from pathlib import Path

MAN = Path(__file__).resolve().parents[2] / "agent功能手册.html"
lines = MAN.read_text(encoding="utf-8").split("\n")
n_before = len(lines)
log = []


def set_line(idx, must_contain, new_text):
    """idx 从 1 开始。该行必须含 must_contain，整行换成 new_text。"""
    cur = lines[idx - 1]
    if must_contain not in cur:
        raise AssertionError(f"L{idx} 锚点不匹配：{must_contain!r} 不在 {cur[:120]!r}")
    lines[idx - 1] = new_text
    log.append(idx)


def patch(idx, old, new):
    cur = lines[idx - 1]
    if cur.count(old) != 1:
        raise AssertionError(f"L{idx} 里 {old!r} 出现 {cur.count(old)} 次，不是一次")
    lines[idx - 1] = cur.replace(old, new)
    log.append(idx)


# 1) §4.1 标题：D2 从「待你定性」变成「已定性」
set_line(
    281,
    "D2 待你定性",
    "<h3>4.1 缺陷八条（D1 v1.1、D4 v1.3、D5 + D6 v1.4、D7 v1.5 已上线；"
    "<b>D2 v1.7 已定性：故意闭环，不改行为</b>、D3 未动、<b>D8 v1.7 新立</b>）</h3>",
)

# 2) D2 那一行：证据补注释位置、手段改成「已做」、胶囊改文案（data-st 仍留 na，筛选计数不动）
patch(292,
      "<code>write_file</code> 落盘在 <code>:153</code></td>",
      "<code>write_file</code> 落盘在 <code>:153</code>；名单上方 <code>:32-36</code> "
      "是本轮写的<b>定性注释</b></td>")
set_line(
    294,
    "要么给 staging 开只读例外",
    "    <td>你点了 <b>②</b>：明确「故意闭环」并写进注释 · <b>已做</b>——加 <b>4 行注释、行为零改动</b>"
    "（与 <code>.rollback/v1.7</code> 归档做 <code>ast.dump</code> 同形比对，"
    "<code>验收脚本/v1.7/v17_d2_assert.py</code> <b>15 条全 PASS</b>，负控跑过）</td>",
)
patch(295, "待你定性", "已定性·不改行为")

# 3) §4 末尾推荐区
set_line(
    513,
    "仍挂着等你定性",
    "  <b>D2</b>（staging 副本读不回来）v1.7 已按你点的 ② 定性：<b>故意闭环</b>，理由写进注释、行为零改动。",
)

# 4) §6.1 体量那行（本轮数字见迭代记录 §8）
set_line(
    667,
    "<b>体量</b>：<code>my_ui.py</code> 1,205 → 1,253 行",
    "  <li><b>体量</b>：主轮 <code>my_ui.py</code> 1,205 → 1,253 行、63,316 → <b>67,362 B</b>、净 "
    "<b>+85 / −37</b>；<code>.rollback/</code> 存档 <b>14 → 16 份</b>（7 → 8 套）；看板 <b>36 → 37 条</b>"
    "（V9 转已上线、新立 D8）。<b>第 8 步</b>（你一次点三件：#6 安装 ＋ 开 <code>验收脚本/</code> ＋ D2 ②）"
    "只碰 <code>my_coding_agent.py</code>：204 → <b>208 行</b>、8,355 → <b>8,889 B</b>、净 <b>+4 / −0</b>"
    "（全在注释）；<code>验收脚本/</code> 新建 <b>322 个原件</b>（收编 <b>320</b> ＋ 本轮新写 <b>2</b>）"
    "· <b>98 份</b> <code>run/</code> 副本 · <b>70 份</b>改写前备份 · <b>18 MB</b>；"
    "<code>.rollback/</code> <b>本轮不新增存档</b>（改动只有 4 行注释、AST 同形，回滚面＝删掉那 4 行；"
    "旧 <code>my_coding_agent.py</code> 仍在 <code>.rollback/v1.7/</code> 里，比对就是拿它做的）。</li>",
)

# 5) §6.1 遗留：验收脚本那条（含两处 markdown 反引号混进 HTML，一并修掉）
set_line(
    676,
    "验收脚本仍在 <code>/tmp</code>",
    "  <li><b>验收脚本已经不在 <code>/tmp</code> 了</b>（2026-10-30 你点头「开 验收脚本先点」）："
    "v1.0~v1.7 <b>八轮</b>的脚本与输出整体搬进 <code>ai学习/验收脚本/</code>，按版本号分目录，"
    "<b>一个文件名都没删</b>，搬前搬后逐份 sha1 比对 <b>0 不匹配</b>。落进去的可执行文本里，"
    "指向已收编产物的 <code>/tmp/xxx</code> 路径改写为 <code>验收脚本/&lt;版本&gt;/run/xxx</code>"
    "（<b>70 个文件被改、去重后 97 条规则</b>；改写前备份在 <code>gate/.before-rewrite/</code>）。"
    "复跑命令与已知不等价写在 <code>验收脚本/README.md</code>。<b>仍然留在 <code>/tmp</code> 的只有 "
    "18 个 Chrome profile 目录</b>（约 <b>186 MB</b>，那是浏览器闸的现场而不是产物）。"
    "<b>本轮新增</b>：<code>v17_d2_assert.py</code>（D2 的 15 条断言）、"
    "<code>gate/rewrite_tmp_paths.py</code>（搬家的工具，DRY-RUN 默认）。</li>",
)

# 6) §6.1 遗留：欠点头那条——只改这一行，L765 那条同文的 §6.2 历史原文不动
set_line(
    677,
    "仍欠点头：dify Docker Compose（#5）",
    "  <li>仍欠点头：dify Docker Compose（#5）、<b>百炼 Key 轮换</b>、"
    "<code>gradio_ui.py:456</code> 的 <code>.capitalize()</code>、P0-4、<b>装 node 24</b>"
    "（<code>servers/package.json</code> 要 <code>&gt;=24</code>，本机 <code>22.20.0</code>）。"
    "<b>已销两条</b>：MCP servers <code>npm ci</code>（#6，装完 4/4 起得来、功能调用通）"
    "与 D2（②已做）。</li>",
)

# 7) §7 的【待补】那条：脚本已进语料
set_line(
    1244,
    "【待补】<b>验收脚本还躺在 <code>/tmp</code>，没进语料</b>",
    "  <li>【已收编 2026-10-30】<b>验收脚本已进语料</b>：下面三批复跑脚本原先躺在 <code>/tmp</code>，"
    "现已整体搬入 <code>ai学习/验收脚本/&lt;版本号&gt;/</code>，<b>文件名一个没改</b>（逐份 sha1，0 不匹配）。"
    "清单里保留 <code>/tmp/…</code> 写法，因为那记录的是当时实跑的路径；现在的入口与复跑命令见 "
    "<code>验收脚本/README.md</code>。",
)
set_line(
    1254,
    "要不要在",
    "    <b>2026-10-30 你点了「开 验收脚本先点」，这条已经办完</b>：v1.0~v1.7 <b>八轮</b>的脚本与输出"
    "整体收进 <code>ai学习/验收脚本/</code>（按版本号分目录，一个文件名没删，逐份 sha1 0 不匹配），"
    "复跑命令与「哪几条现在跑不得」写在 <code>验收脚本/README.md</code>。"
    "搬完之后 <code>run/</code> 目录会在原件旁边长出来（复跑产物只覆盖 <code>run/</code> 里的同名副本，"
    "<b>原件不再被复跑写坏</b>）；已收编的旧输出按字节冻结，清单校验仍然过。</li>",
)

if len(lines) != n_before:
    raise AssertionError(f"总行数变了：{n_before} -> {len(lines)}")

DRY = "--write" not in sys.argv
print(f"改 {len(log)} 行（去重 {len(set(log))} 处）：{sorted(set(log))}")
print("DRY-RUN，没写文件" if DRY else "已写入")
if not DRY:
    MAN.write_text("\n".join(lines), encoding="utf-8")
