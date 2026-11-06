"""第三道扫抓出来的真错（MEM_FIELDS 的终点）＋ 验收脚本目录进 §5.1 名册。

手册 3 处 `:69-88` 讲的是 `MEM_FIELDS` 那张表，表本身到 `:84` 收口，`:85-88` 是它下面
那段「wait 为什么不在表里」的注释 —— 同一段区间在 README 里写的是 `:69-84`，两份得一致。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAN = ROOT / "agent功能手册.html"
RD = ROOT / "README.md"
LOG = ROOT / "迭代记录.md"
WRITE = "--write" in sys.argv

m = MAN.read_text(encoding="utf-8").split("\n")

# 1) 三处终点改准（数字等长，不动表格排版宽度）
fixed = []
for ln in (196, 486, 502):
    if m[ln - 1].count("<code>:69-88</code>") == 1:
        m[ln - 1] = m[ln - 1].replace("<code>:69-88</code>", "<code>:69-84</code>")
        fixed.append(ln)
    elif m[ln - 1].count("my_ui.py:69-88") == 1:
        m[ln - 1] = m[ln - 1].replace("my_ui.py:69-88", "my_ui.py:69-84")
        fixed.append(ln)
    else:
        raise AssertionError(f"手册 L{ln} 没找到 69-88 的那格")
print("手册 69-88 → 69-84：", fixed)

# 2) §5.1 文件与命名表加一行：验收脚本目录
row = ("  <tr><td><code>ai学习/验收脚本/</code></td><td><b>复跑留痕</b>（2026-10-30 起）："
       "v1.0~v1.7 八轮的脚本与输出按版本号分目录收在这里，<b>一个文件名都没删</b>（逐份 sha1）。"
       "本文与 <code>README.md</code>、<code>迭代记录.md</code> 里写的 <code>/tmp/v1*_…</code> "
       "一律是<b>当时实跑的路径</b>，现在的入口是这个目录；哪些命令还跑得动写在 "
       "<code>验收脚本/README.md</code></td><td>我写，只增不删</td></tr>")
anchor = "  <tr><td><code>smolagents/.agent-history.sqlite3</code></td><td><b>运行数据</b>（v1.2 起）"
hits = [i for i, l in enumerate(m) if anchor in l]
if len(hits) != 1:
    raise AssertionError(f"§5.1 名册锚点 {len(hits)} 处")
idx = hits[0]
m.insert(idx + 1, row)
print(f"手册插入名册行：新 L{idx + 2}（§5.1 表尾）")

MAN_new = "\n".join(m)
print(f"手册行数 {len(m)}")

# 3) README §9.3 标题下加一行路径口径
r = RD.read_text(encoding="utf-8").split("\n")
h = "### 9.3 复现命令清单（都是本机验证过的）"
hi = r.index(h)
note = ("> 下面这些命令里出现的 `/tmp/v1*_…` 是**当时实跑的路径**。2026-10-30 起八轮的脚本"
        "与输出都收在 `ai学习/验收脚本/<版本号>/`（`gate/` 放四道文档闸，`servers/` 放 MCP 冒烟），"
        "文件名一个没改；入口、复跑分组与「哪几条现在跑不得」写在 `验收脚本/README.md`。")
r.insert(hi + 1, note)
RD_new = "\n".join(r)
print(f"README 插入路径口径：新 L{hi + 2}，共 {len(r)} 行")

# 4) 迭代记录：给本轮那条文档回写留痕补一句路径口径
lg = LOG.read_text(encoding="utf-8").split("\n")
tgt = [i for i, l in enumerate(lg) if "第 8 步的文档回写" in l]
if len(tgt) != 1:
    raise AssertionError(f"迭代记录里那条留痕有 {len(tgt)} 处")
lg[tgt[0]] += ("**路径口径也写死**：三份文档里更早的 `/tmp/v1*_…` 保留为当时实跑路径，"
               "现在的入口统一是 `ai学习/验收脚本/`（手册 §5.1 名册已加这一行，README §9.3 标题下加了口径）。")
LOG_new = "\n".join(lg)
print(f"迭代记录补句：L{tgt[0] + 1}")

if not WRITE:
    print("DRY-RUN，没写文件")
else:
    MAN.write_text(MAN_new, encoding="utf-8")
    RD.write_text(RD_new, encoding="utf-8")
    LOG.write_text(LOG_new, encoding="utf-8")
    print("已写入")
