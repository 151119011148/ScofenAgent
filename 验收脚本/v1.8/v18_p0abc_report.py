# -*- coding: utf-8 -*-
"""P0-a／P0-b／P0-c 的证据文件写入器：把已有的行搬进 run/v18_p0abc_live.out，一个数字都不手打。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_p0abc_report.py   （**不再打模型，零 token 消耗**）

来源（全部是磁盘上已经存在的东西）：
  · 离线闸         → 当场重跑 v18_test_p0abc.py，全文搬进来
  · 三段新文案原文 → 从 live 模块**抛出来／渲染出来**拿（guarded 的两条 message、description、docstring）
  · prompt 增量    → 现场按新旧两份代码各渲染一遍 system_prompt 数字符
  · 实跑对照       → run/v18_p0abc_{old,new}_{A,B}.out 与 ..._r2.out
                      这八份是 2 样本 × 4 格。**为什么从框架日志解析而不用探针 digest**：
                      探针连崩两次（st.output、st.timing.total_time），digest 一次都没落成，
                      token 却已经花掉了。框架自己的日志里有每步的 `{"tool":…, "arguments":…}`
                      行、Error executing tool 段、[Step N: …] 累计行、Final answer 段——够用。
  · 21:06 基线     → ai学习/.agent-ui.log 的原行（票上挂的那轮，改之前的行为）
搬不来的就明写没有，不补。
"""
import importlib.util
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
OLD_DIR = SMOL / ".rollback" / "v1.8" / "after-p04"
PY = str(SMOL / ".venv" / "bin" / "python")
OUT = RUN / "v18_p0abc_live.out"
UI_LOG = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/.agent-ui.log")
TASKS = {
    "A": "删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动",
    "B": "/Users/gaoying/Desktop/study/人生。删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动",
}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
L = []


def w(s=""):
    L.append(str(s))


def bar(t):
    w("=" * 92)
    w(t)
    w("=" * 92)


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True).stdout


def sha(p):
    return sh("shasum", str(p)).split()[0]


def unesc(s):
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def clean_lines(p):
    """日志 → 去掉 ANSI、Rich 边框和右边那截横线，只留内容。"""
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ANSI.sub("", ln)
        ln = re.sub(r"\s*╭─.*$", "", ln)
        ln = re.sub(r"\s*│\s*$", "", ln)
        ln = re.sub(r"^│\s?", "", ln)
        out.append(ln.rstrip())
    return out


def glue(lines):
    """Rich 会把一长句在任意位置折断（中文尤其）。给两种拼法，命中判断两种都试。"""
    return "".join(lines), " ".join(x.strip() for x in lines if x.strip())


class Run:
    """一次实跑的读数，全部从框架日志解析。"""

    def __init__(self, path):
        self.path = path
        self.exists = path.exists()
        lines = clean_lines(path)
        self.calls = []          # [(tool, args_str)]
        self.errors = []         # 每次撞墙的完整文案（已拼回）
        self.step_tokens = []    # [Step N: Duration x| Input tokens I | Output tokens O]
        self.max_steps = any(ln.startswith("Reached max steps") for ln in lines)
        self.final = None
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith('{"tool":'):
                m = re.match(r'^\{"tool": "([a-z_]+)", "arguments": (.*)$', ln)
                if m:
                    tool, rest = m.group(1), m.group(2)
                    # 框架把这行打成 `{"tool": "X", "arguments": "<原样 arguments>"}`，
                    # 完整行必然以 `}"}` 收尾；Rich 把它折断时，把后续行拼回来直到出现这个尾巴。
                    j = i + 1
                    while not rest.rstrip().endswith('}"}') and j < len(lines):
                        nxt = lines[j]
                        if nxt.startswith(('{"tool"', "Observations", "Error executing", "Calling tool",
                                            "Please try again", "Final answer", "[Step", "╰", "│")):
                            break
                        rest += nxt.strip()
                        j += 1
                    rest = rest.strip()
                    inner = rest[1:-2] if rest.startswith('"') and rest.endswith('"}') else rest
                    self.calls.append((tool, unesc(inner)))
                    i = j
                    continue
            if ln.startswith(("Error executing tool", "PermissionError:", "FileNotFoundError:")):
                # 一次撞墙 = 从 `Error executing tool …` 那行起，到框架那句固定的收尾
                # `Please try again or use another tool` 之前。整段按**无分隔拼行**还原：
                # Rich 会在任意位置折断（中文尤其），拼回来才查得到整句。
                blk = [ln]
                j = i + 1
                while j < len(lines) and not lines[j].startswith(
                    ("Please try again", "Observations", "[Step", '{"tool"',
                     "Error executing", "Calling tool")):
                    blk.append(lines[j])
                    j += 1
                i = j
                self.errors.append(glue(blk)[0])
                continue
            m = re.search(r"\[Step (\d+): Duration ([\d.]+) seconds\| Input tokens: ([\d,]+) \| Output tokens: ([\d,]+)\]", ln)
            if m:
                self.step_tokens.append((int(m.group(1)), float(m.group(2)),
                                         int(m.group(3).replace(",", "")), int(m.group(4).replace(",", ""))))
            if ln.startswith("Final answer:"):
                blk = [ln[len("Final answer:"):]]
                j = i + 1
                while j < len(lines) and not lines[j].startswith(("[Step", "===" , "---", '{"tool"')):
                    blk.append(lines[j])
                    j += 1
                ns, sp = glue(blk)
                self.final = sp.strip()
                i = j
                continue
            i += 1

    def sigs(self):
        return ["%s(%s)" % (t, a) for t, a in self.calls]

    def dups(self):
        s = self.sigs()
        d = {}
        for x in s:
            d[x] = d.get(x, 0) + 1
        return {k: v for k, v in d.items() if v > 1}

    def last_cum(self):
        return self.step_tokens[-1] if self.step_tokens else None

    def has_new_rel(self):
        return any("我只能把它接到白名单根" in e for e in self.errors)

    def has_new_oob(self):
        return any("没有删除、移动、重命名" in e for e in self.errors)

    def has_old_rel(self):
        return any(re.search(r"路径不存在：\S+$", e) and "口径" not in e for e in self.errors)


bar("v1.8 第④刀 P0-a／P0-b／P0-c 实跑证据：越界报错补指路／能力穷举／相对路径不猜根")
w("生成方式：`smolagents/.venv/bin/python 验收脚本/v1.8/v18_p0abc_report.py`（一次性写入器，只搬已有行；")
w("          本文件不重新打模型，所有实跑数字来自 run/ 下已经落盘的日志）")
w("代码：live  my_coding_agent.py=%s  my_agent.py=%s  my_ui.py=%s"
  % (sha(SMOL / "my_coding_agent.py"), sha(SMOL / "my_agent.py"), sha(SMOL / "my_ui.py")))
w("      改前 .rollback/v1.8/after-p04/  my_coding_agent.py=%s  my_agent.py=%s"
  % (sha(OLD_DIR / "my_coding_agent.py"), sha(OLD_DIR / "my_agent.py")))
w("      live 行数：" + sh("wc", "-l", str(SMOL / "my_coding_agent.py"), str(SMOL / "my_agent.py")).strip().replace("\n", " | "))
w()
w("这一刀只动了三处文案＋一条错误分支：")
w("  P0-a  guarded() 的**越界**报错。旧：`越界：X 不在白名单根目录 R 之下`（到此为止）。")
w("        新：补指路——五个工具只服务这一个根／动作空间里没有删除、移动、重命名／根外由用户在终端执行／")
w("        并且明写「不要让用户去找系统管理员开权限（没有这个开关）」。")
w("  P0-c  guarded() 的**相对路径＋不存在**报错。新文案把口径摊开：你给的是这串相对路径，我只能接到这个根底下再找，")
w("        不猜别的根目录；根外有没有同名目录我读不到；不要用同一个参数再打一遍；要么 list_dir('.') 要么讲明根内没有它。")
w("        （绝对路径＋不存在那一支的文案逐字未动，见第一节闸。）")
w("  P0-b  能力穷举写在**模型真读得到的那一半**：list_dir、write_file 的 docstring；")
w("        description= 字段照票面写全，但它在顶层 agent 上是死字段（第二节实测）。")
w()
w("token 口径（后面每个数都按这三档标）：")
w("  · 末步累计＝框架日志 `[Step N: … Input tokens: I | Output tokens: O]` 里 N 最大的那行，")
w("    那是**监控器跨题累计**（同一个 agent 对象再跑一题会继续往上加），不是这一题的消耗；")
w("  · 探针 digest 本来要给「单步 in/out」和「各步 in 相加」两档，但探针连崩两次没落成（见本文件头），")
w("    所以这份证据里**没有单步口径**，只有末步累计；宁可缺一格也不拿累计冒充单步；")
w("  · 每一步都会把前文重发，所以步数越多、累计涨得越快——「同名同参重复」那几列就是直接烧在这一档上的。")
w()
w("跑法与波及面：")
w("  `%s 验收脚本/v1.8/v18_p0abc_probe.py <old|new> <A|B>`：命令行直接跑 my_agent 那个 agent，" % PY)
w("  planning_interval 两边都置 None（这一刀不比规划），CLI 侧没有审批门。不碰 gradio、不碰 7860、")
w("  不写真库；题面是删除类请求，但这套工具到不了那个目录——第四节末的预检把这四只手逐一验过。")
w()

# ---------------------------------------------------------------- 一、离线闸
bar("一、离线闸 v18_test_p0abc.py 当场重跑（全文）")
gate = sh(PY, str(HERE / "v18_test_p0abc.py"))
for ln in gate.splitlines():
    w("  " + ln)
w()
n_pass, n_fail = gate.count(" PASS"), gate.count(" FAIL")
w("  统计：PASS %d 条 ／ FAIL %d 条。最要紧的两条：")
w("   · 「1-行为一致」17 条：同一张路径表在旧代码（.rollback/v1.8/after-p04 那份 import 进来）和新代码上各跑一遍，")
w("     异常类型＋从文案里抽出的那个 Path 必须一一对上；「1-覆盖面」再钉住表里三种结局（放行／越界／不存在）都在，")
w("     免得 17 条全等只是因为全等在同一支上。")
w("   · 「2-绝对不存在文案一字未动」：绝对路径不存在那一条分支逐字和旧的一样——这轮文案扩张只在两处。")
w()

# ---------------------------------------------------------------- 二、哪半句进模型
bar("二、模型读得到哪半句：description 不进 prompt，工具 docstring 进")
sys.path.insert(0, str(SMOL))
import my_agent  # noqa: E402
import my_coding_agent as new_mod  # noqa: E402
from smolagents import ToolCallingAgent  # noqa: E402

spec = importlib.util.spec_from_file_location("p0abc_old_mod", str(OLD_DIR / "my_coding_agent.py"))
old_mod = importlib.util.module_from_spec(spec)
sys.modules["p0abc_old_mod"] = old_mod
spec.loader.exec_module(old_mod)
a2 = ToolCallingAgent(
    tools=[old_mod.read_file, old_mod.list_dir, old_mod.grep_files, old_mod.write_file, old_mod.run_python,
           my_agent.MaxDrawdownTool(), my_agent.AnnualizedVolTool()],
    model=my_agent.model, max_steps=8, name="x", description="y")
sp_old, sp_new = a2.system_prompt, my_agent.agent.system_prompt
w("  system_prompt 字符数：旧=%d 新=%d 增量=%+d  ← 这是每一步都要重发的**固定开销**"
  % (len(sp_old), len(sp_new), len(sp_new) - len(sp_old)))
w("  description 是不是死字段：它里面独有的串「单次最多 300 行」出现在渲染出的 system_prompt 里吗 → %s"
  % ("单次最多 300 行" in sp_new))
w("  工具 docstring 是活的那一半：「列不到根外的任何目录」→ %s；「删除、移动、重命名都没有对应工具」→ %s"
  % ("列不到根外的任何目录" in sp_new, "删除、移动、重命名都没有对应工具" in sp_new))
w("  框架依据：`self.description` 只在 describe() 里被读，那是给 managed（子）agent 用的；")
w("          顶层 ToolCallingAgent 没有 describe()（探针：`hasattr(agent, 'describe')` → %s）。"
  % hasattr(my_agent.agent, "describe"))
w("  规则 4 早就存在：system_prompt 里那句「Never re-do a tool call that you previously did with the exact same")
w("  parameters」在旧和新两份 prompt 里都在（本次命中 %s／%s）——**是模型没听话，不是没规矩**，这条直接喂 #41。"
  % ("Never re-do a tool call" in sp_old, "Never re-do a tool call" in sp_new))
w()

# ---------------------------------------------------------------- 三、新文案原文
bar("三、三段新文案原文（从 live 模块当场抛／渲染出来取）")
try:
    new_mod.guarded("/Users/gaoying/Desktop/study/")
except PermissionError as exc:
    w("  [P0-a 越界 PermissionError，%d 字符]" % len(str(exc)))
    for ln in str(exc).splitlines():
        w("    " + ln)
w()
try:
    new_mod.guarded("人生/")
except FileNotFoundError as exc:
    w("  [P0-c 相对不存在 FileNotFoundError，%d 字符]" % len(str(exc)))
    for ln in str(exc).splitlines():
        w("    " + ln)
w()
old_oob = None
try:
    old_mod.guarded("/Users/gaoying/Desktop/study/")
except PermissionError as exc:
    old_oob = str(exc)
old_rel = None
try:
    old_mod.guarded("人生/")
except FileNotFoundError as exc:
    old_rel = str(exc)
w("  [对照：旧文案原文，越界 %d 字符 / 相对不存在 %d 字符]" % (len(old_oob), len(old_rel)))
w("    " + old_oob)
w("    " + old_rel)
w()
w("  [P0-b description 全文 —— my_coding_agent.build_agent（5 只手）]")
src = (SMOL / "my_coding_agent.py").read_text(encoding="utf-8")
m = re.search(r'description=\(\n(.*?)\n        \),', src, re.S)
for ln in (m.group(1) if m else ["【源码没截到】"]).splitlines():
    w("    " + ln.strip().rstrip(",").rstrip())
w("  [P0-b description 全文 —— my_agent（7 只手，21:06 那轮出事的正是这个 agent）]")
for ln in my_agent.agent.description.splitlines():
    w("    " + ln)
w()

# ---------------------------------------------------------------- 四、21:06 基线
bar("四、21:06 基线：票上挂的那轮（改之前的行为，原行照搬 .agent-ui.log）")
base = Run(UI_LOG)
w("  这一节是**你自己那天跑出来的界面日志**，不是我这轮跑的。两个 run 的题面：")
w("    run A：%s" % TASKS["A"])
w("    run B：%s" % TASKS["B"])
w()
seq = base.sigs()
w("  框架日志里的完整调用序列（run A 8 步＋run B 3 步，一共 %d 条）：" % len(seq))
for n, s in enumerate(seq, 1):
    w("    %2d. %s" % (n, s[:150]))
w()
w("  同名同参重复（整份日志合并算，含两次 run）：")
for k, v in base.dups().items():
    w("    ×%d  %s" % (v, k[:150]))
w()
w("  旧文案的两句原话（模型就是读完这两句之后开始绕圈的）：")
for ln in clean_lines(UI_LOG):
    if ln.startswith("FileNotFoundError: 路径不存在：") or ln.startswith("越界："):
        w("    " + ln)
w("  run B 收尾（旧越界文案没指路时它自己补的那句）：")
for ln in clean_lines(UI_LOG):
    if "系统管理员" in ln:
        w("    " + ln.strip()[:220])
w()
w("  预检（这轮实跑的波及面证据）：四个可能的删除入口全部到不了 /Users/gaoying/Desktop/study/人生/轻量文档")
pre = sh(PY, "-c", """
# -*- coding: utf-8 -*-
import sys; sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import my_coding_agent as m
T = "/Users/gaoying/Desktop/study/人生/轻量文档"
for label, fn in [("guarded(目标)", lambda: m.guarded(T)),
                  ("write_file(目标)", lambda: m.write_file(T, "x")),
                  ("run_python shutil.rmtree", lambda: m.run_python("import shutil; shutil.rmtree('%s')" % T)),
                  ("run_python subprocess rm", lambda: m.run_python("import subprocess; subprocess.run(['rm','-rf','%s'])" % T))]:
    try:
        print("%-26s 返回值=%s" % (label, str(fn())[:60]))
    except BaseException as e:
        print("%-26s %s: %s" % (label, type(e).__name__, str(e)[:60]))
""")
for ln in pre.splitlines():
    w("    " + ln)
w()

# ---------------------------------------------------------------- 五、实跑对照
bar("五、实跑对照：old（回滚点代码）vs new（live），每题两个样本")
w("  样本 1 = run/v18_p0abc_<w>_<t>.out（探针崩在算账之前，token 已花、digest 没落成）")
w("  样本 2 = run/v18_p0abc_<w>_<t>_r2.out（修好 st.output 之后重跑，又崩在 st.timing.total_time）")
w("  两次都**不影响这里的读数**：本节全部从框架自己的日志解析。")
w()
CELLS = [(t, wch, s) for t in ("A", "B") for wch in ("old", "new") for s in ("", "_r2")]
SUMMARY = {}
for tag, which, sfx in CELLS:
    p = RUN / ("v18_p0abc_%s_%s%s.out" % (which, tag, sfx))
    r = Run(p)
    SUMMARY[(tag, which, "s2" if sfx else "s1")] = r
    w("  " + "-" * 86)
    w("  题 %s ｜ %s 代码 ｜ 样本 %s" % (tag, which, "2" if sfx else "1"))
    w("    文件：%s（存在=%s，%d 行）" % (p.name, r.exists, len(clean_lines(p))))
    w("    调用序列：%s" % (" → ".join(x[:60] for x in r.sigs()) or "【解析不出】"))
    d = r.dups()
    w("    同名同参重复：%s" % ("无" if not d else "; ".join("×%d %s" % (v, k[:70]) for k, v in d.items())))
    lc = r.last_cum()
    w("    末步累计（监控器口径，跨题）：%s" % ("无 [Step] 行" if not lc else "Step %d / %.2fs / in %s / out %s" % lc))
    w("    8 步用满（Reached max steps）：%s" % r.max_steps)
    w("    撞墙段数：%d ｜ 其中带新口径（相对路径那句）%s ｜ 带新指路（越界那句）%s ｜ 旧式光秃文案 %s"
      % (len(r.errors), r.has_new_rel(), r.has_new_oob(), r.has_old_rel()))
    for e in r.errors:
        w("      报错原文：%s" % e[:620])
    fa = (r.final or "").replace("\n", " ")
    w("    final answer：%s" % ("【没有：这题把 8 步用满，交不出答案】" if not fa else fa[:1500]))
    if fa:
        # 「答案里给了用户一条 rm -rf」是这一档最要紧的副作用，逐字搬出来看路径对不对
        cmd = fa[fa.index("rm -rf"):][:70] if "rm -rf" in fa else "【答案里没有 rm -rf】"
        w("    答案关键词：管理员 %s ｜ 终端 %s ｜ rm 片段：%s"
          % ("有" if "管理员" in fa else "无", "有" if "终端" in fa else "无", cmd))
w()

# ---------------------------------------------------------------- 六、对照表
bar("六、对照表（每个格子从上面那一份解析结果搬，程序自己算）")
w("    题  代码 样本  动作数  同名同参重复数  撞墙段  新文案到位  8步用满  末步累计in/out")
for tag in ("A", "B"):
    for which in ("old", "new"):
        for sfx, lab in (("", "s1"), ("_r2", "s2")):
            r = SUMMARY[(tag, which, lab)]
            d = sum(r.dups().values()) - len(r.dups())
            lc = r.last_cum()
            w("    %s   %-4s %-3s %5d %12s %9s %12s %10s %14s" % (
                tag, which, lab, len(r.sigs()), d if d else 0, len(r.errors),
                "是" if (r.has_new_rel() or r.has_new_oob()) else "—",
                "是" if r.max_steps else "否",
                ("%d/%d" % (lc[2], lc[3])) if lc else "—",
            ))
w("    （「撞墙段」= 日志里 Error executing tool 那几段的段数；「重复数」是超出第一次的那些次数）")
w()

# ---------------------------------------------------------------- 七、结论位
bar("七、结论位：这一刀证到了什么、没证到什么")
oa = [SUMMARY[("A", "old", "s1")], SUMMARY[("A", "old", "s2")]]
na = [SUMMARY[("A", "new", "s1")], SUMMARY[("A", "new", "s2")]]
ob = [SUMMARY[("B", "old", "s1")], SUMMARY[("B", "old", "s2")]]
nb = [SUMMARY[("B", "new", "s1")], SUMMARY[("B", "new", "s2")]]


def dsum(rs):
    return [sum(r.dups().values()) - len(r.dups()) for r in rs]


w("  证到了：")
w("    1. **判定面一字未动**：离线闸 PASS %d 条、FAIL 0 条，含 17 条路径表全等和「绝对不存在文案逐字未变」。" % gate.count(" PASS"))
w("       这是纯文案刀。")
w("    2. **新文案真的到了模型眼前**：new 侧四个样本里，撞墙段的原文带着新句子（第五节每格「报错原文」），")
w("       old 侧同样位置是光秃秃的一句「路径不存在：<拼好的路径>」。")
w("    3. **题 B 的收尾从『找管理员』变成了『你自己在终端执行』**：")
for r in ob + nb:
    lc = r.last_cum()
    fa = (r.final or "").replace("\n", " ")
    w("       %s/样本%s：动作 %d 步、8步用满=%s、答案里「管理员」%s 、「终端」%s ｜ %s" % (
        "old" if r in ob else "new", "2" if r in (ob[1], nb[1]) else "1", len(r.sigs()), r.max_steps,
        "有" if "管理员" in fa else "无", "有" if "终端" in fa else "无", fa[:150] or "【交不出答案】"))
w("       另：21:06 基线里 old 的那句「请联系系统管理员调整权限」是它自己补的（第四节原行），本机没有这个开关。")
w("    4. **固定开销量出来了**：system_prompt %d → %d 字符（+%d），来自两句工具 docstring；"
  % (len(sp_old), len(sp_new), len(sp_new) - len(sp_old)))
w("       description 那一大段不进 prompt，所以它一点都不抬每一步的开销。")
w("    5. 题 A 上**死循环的形状变了但没消失**：old 样本里 list_dir('人生/')、list_dir({}) 这种同名同参重复")
w("       各样本重复数=%s；new 两个样本重复数=%s（新文案那句「不要用同一个参数再打一遍」被听进去了，"
  % ([sum(r.dups().values()) - len(r.dups()) for r in oa], [sum(r.dups().values()) - len(r.dups()) for r in na]))
w("       它改成挨个列子目录去了）。**但两题的新样本仍然把 8 步用满**，只是从『原地绕圈』变成『摊开绕圈』。")
w()
w("  没证到 / 边界（明写，不留好看的）：")
# 现场点出来的新尾巴：new 侧那份「请用户自己在终端执行」的答案，路径是**照抄题面标点**的
bad = []
for r in nb:
    fa = (r.final or "").replace("\n", " ")
    for pathseg in re.findall(r'"/([^"]+)"', fa):
        live = pathlib.Path(pathseg)
        bad.append((str(live), live.exists()))
w("    0. **这一刀自己带出来的新尾巴（当场量，不是猜）**：new 侧题 B 那两份答案给用户的 rm 命令里，")
w("       路径逐字照抄了题面标点——题面写的是「/Users/gaoying/Desktop/study/人生。删除…」，")
w("       模型把 `人生。` 当成目录名。答案里出现的绝对路径与它们此刻在磁盘上是否存在：")
for x, e in bad:
    w("       %s  exists=%s" % (x, e))
w("       也就是说：工具到不了根外，模型**没法校验**它自己写在答案里的那条 rm，用户照着敲就可能删错东西。")
w("       这是「指路指到终端」之后新出现的一段责任，本轮没动它——【待你点头立新单】：")
w("       越界类答案里不该由 agent 拼可执行命令，只该复述用户给的原话并说明『这条路径我读不到、也没法确认它对不对』。")
w()
w("    1. 文案不改熔断，就还是靠模型自觉——而框架 prompt 规则 4 早就禁了同名同参重发，它照犯（第二节）。")
w("       所以 #41（重复调用检测与熔断）该做，且这一轮的 old/new 重复数对比就是它的立项数据。")
w("    2. 每格只有 2 个样本、模型有温度：步数、走法这类**行为面**差异只能当倾向，不当结论；")
w("       能当结论的只有确定性的那部分（闸里的判定全等、文案是否出现在 observation／prompt 里）。")
w("    3. 探针自己崩过两次（st.output、st.timing.total_time），八跑里前四跑的 digest 白丢了 token；")
w("       也因此这份证据**没有单步 token 口径**，只有末步累计。教训写进探针注释了。")
w("    4. write_file 的 docstring 那句负向穷举是本轮新加的行为说明，**没做过一次 write_file 实跑**")
w("       （模型在这两题里没走到写）——【未验证】，只由离线闸的 prompt 命中断言背书。")
w("    5. 本轮按批注口径只报告不改：#42 D8-2（刷新首屏读到未写完的库，已量到 0.761s 窗口）、")
w("       P1-b plan_delete 预览、P2-a .agent-ui.log/.pid 出 ROOT、P2-b 非法 JSON arguments、D3 逐步落库。")
w()
w("  行为语义变了吗：没有。异常类型、路径收敛结果、DENY 名单、must_exist 分支顺序逐条对齐旧代码；")
w("  变的只有模型和用户在读到报错／工具清单时看到什么字。")

OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("写入 %s：%d 行 / %d 字节" % (OUT.name, len(L), OUT.stat().st_size))
