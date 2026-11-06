# -*- coding: utf-8 -*-
"""v1.8 第⑤刀 P1-a 的证据文件写入器：run/v18_p1a_live.out，一个数字都不手打。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_p1a_report.py
本文件几乎不打模型（第五节那次百炼重探除外：一句话、max_tokens=8，把返回值或报错原文当场记下）。
其余每节要么当场重跑（三、四节），要么从磁盘上已有的日志逐行解析（第一节），
要么从源码现场 grep 出行号（第二节）。搬不来的就明写没有，不补。

九节：
  一 立项依据：21:06 那份 .agent-ui.log 按 New run 横幅切成单轮，逐轮走一遍查重口径
  二 结构与层序：现场行号
  三 离线闸：五道当场重跑（本刀那道全文，另四道回归只报统计）
  四 零成本回放：当场重跑 v18_dup_replay.py，全文搬进来
  五 真模型那一路：当场重探百炼 ＋ 搬 23:50 那份 D0 留档 ＋【未验证】清单
  六 行为语义变化清单
  七 体量与成本
  八 回滚演练（双向）全文
  九 边界与待办
"""
import hashlib
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
PY = str(SMOL / ".venv" / "bin" / "python")
BACK = SMOL / ".rollback/v1.8/after-p0abc"
FWD = SMOL / ".rollback/v1.8/after-p1a"
OUT = RUN / "v18_p1a_live.out"
UI_LOG = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/.agent-ui.log")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
L = []


def w(s=""):
    L.append(str(s))


def bar(t):
    w("=" * 92)
    w(t)
    w("=" * 92)


def run(*args, cwd=str(SMOL)):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def sh(*args, cwd=str(SMOL)):
    return run(*args, cwd=cwd)[1]


def stat(p):
    b = p.read_bytes()
    return b.count(b"\n"), len(b), hashlib.sha1(b).hexdigest()


def sha8(p):
    return stat(p)[2][:8]


def unesc(s):
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def clean_lines(p, keep_box=False):
    """日志 → 去 ANSI 和 Rich 的左右框。keep_box=True 时保留 `╭─ New run ─╮` 那行：
    切片要靠它，默认那版会把整条横幅删掉（第一版就栽在这儿，两轮并成了一轮）。"""
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ANSI.sub("", ln)
        if not keep_box:
            ln = re.sub(r"\s*╭─.*$", "", ln)
        ln = re.sub(r"\s*│\s*$", "", ln)
        ln = re.sub(r"^│\s?", "", ln)
        out.append(ln.rstrip())
    return out


class Log:
    """框架自己的日志 → 按 New run 横幅切成「轮」，每轮拿到 (步号, 调用签名) 和累计 token 行。

    步号取自 `━━ Step N ━━` 横幅（不是数出来的）；累计 token 取自
    `[Step N: Duration x seconds| Input tokens: I | Output tokens: O]`。
    一条 `{"tool": ...}` 行会被 Rich 折断，按上一份写入器的办法拼回来。
    """

    def __init__(self, p):
        self.path = p
        self.exists = p.exists()
        lines = clean_lines(p, keep_box=True)
        self.runs = []          # [(题面, [(步号, 签名)])]
        self.cum = []           # [(步号, 秒, 累计in, 累计out)]
        self.n_banner = sum(1 for ln in lines if "New run - smolagents" in ln)
        cur, title = None, ""
        step = None
        awaiting = False
        i = 0
        while i < len(lines):
            ln = lines[i]
            if "New run - smolagents" in ln:
                if cur is not None:
                    self.runs.append((title, cur))
                cur, title, awaiting = [], "", True
                step = None
                i += 1
                continue
            if awaiting:
                s = ln.strip()
                if not s:
                    i += 1
                    continue
                if s.startswith("╰") or s.startswith("━"):
                    awaiting = False
                else:
                    title = s[:120]
                    awaiting = False
            m = re.match(r"^\s*━*\s*Step (\d+)\s*━", ln)
            if m:
                step = int(m.group(1))
                i += 1
                continue
            if ln.startswith('{"tool":'):
                ln = re.sub(r"\s*╭─.*$", "", ln)   # 同一行右边还挂着观察值那个框，先切掉
                lines[i] = ln
                mm = re.match(r'^\{"tool": "([a-z_]+)", "arguments": (.*)$', ln)
                if mm:
                    tool, rest = mm.group(1), mm.group(2)
                    j = i + 1
                    while not rest.rstrip().endswith('}"}') and j < len(lines):
                        nxt = lines[j]
                        if nxt.startswith(('{"tool"', "Observations", "Error executing", "Calling tool",
                                            "Please try again", "Final answer", "[Step", "╭", "╰", "│", "━")):
                            break
                        rest += nxt.strip()
                        j += 1
                    rest = rest.strip()
                    inner = rest[1:-2] if rest.startswith('"') and rest.endswith('"}') else rest
                    if cur is None:
                        cur = []
                    cur.append((step, "%s(%s)" % (tool, unesc(inner))))
                    i = j
                    continue
            m = re.search(r"\[Step (\d+): Duration ([\d.]+) seconds\| Input tokens: ([\d,]+) \| Output tokens: ([\d,]+)\]", ln)
            if m:
                self.cum.append((int(m.group(1)), float(m.group(2)),
                                 int(m.group(3).replace(",", "")), int(m.group(4).replace(",", ""))))
            i += 1
        if cur is not None:
            self.runs.append((title, cur))

    def walk(self, calls, limit):
        """按本刀口径走一遍这一轮：哪一步是重复、第几次被挡、第几步触发熔断。"""
        seen, blocked, fuse = {}, [], None
        for stp, sig in calls:
            seen[sig] = seen.get(sig, 0) + 1
            if seen[sig] > 1:
                blocked.append((stp, sig, seen[sig]))
                if fuse is None and len(blocked) > limit:
                    fuse = stp
        return blocked, fuse

    def cum_at(self, stepno):
        return next((c for c in self.cum if c[0] == stepno), None)


ui_src = (SMOL / "my_ui.py").read_text(encoding="utf-8")
agent_src = (SMOL / "my_agent.py").read_text(encoding="utf-8")
LIMIT = int(re.search(r"^DUP_BLOCK_LIMIT = (\d+)", ui_src, re.M).group(1))
MAXSTEPS = re.search(r"max_steps\s*=\s*(\d+)", agent_src).group(1)
log = Log(UI_LOG)
MS = int(MAXSTEPS)
s8, s9 = log.cum_at(MS), log.cum_at(MS + 1)
delta = (f"{s9[2]-s8[2]:,}", f"{s9[3]-s8[3]:,}", s9[1]) if (s8 and s9) else None
saved = ("in %s / out %s、%.2f 秒" % delta) if delta else "【这一轮日志里没实测到】"

bar("v1.8 第⑤刀 P1-a 重复调用检测与熔断：立项／结构／离线闸／零成本回放／真模型那一路")
w("生成方式：`smolagents/.venv/bin/python 验收脚本/v1.8/v18_p1a_report.py`（一次性写入器）")
w("写入时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
w("口径约定：三、四两节是**当场重跑**（不是搬旧文件）；第八节按原文搬本刀改完后那一场演练；")
w("          第五节当场重探一次百炼，再搬 23:50 那份 D0 留档。")
w()
lb, bb, hs = stat(SMOL / "my_ui.py")
lb0, bb0, hs0 = stat(BACK / "my_ui.py")
lb1, bb1, hs1 = stat(FWD / "my_ui.py")
w("被测：live my_ui.py                   %5d 行 / %d B / sha1=%s" % (lb, bb, hs))
w("      改前 .rollback/v1.8/after-p0abc  %5d 行 / %d B / sha1=%s" % (lb0, bb0, hs0))
w("      快照 .rollback/v1.8/after-p1a    %5d 行 / %d B / sha1=%s（现场==快照：%s）"
  % (lb1, bb1, hs1, (SMOL / "my_ui.py").read_bytes() == (FWD / "my_ui.py").read_bytes()))
w("      my_agent.py=%s  my_coding_agent.py=%s（本刀都没碰，见第七节）" % (sha8(SMOL / "my_agent.py"),
                                                                        sha8(SMOL / "my_coding_agent.py")))
w()
w("这刀一句话：给**每一只**工具（final_answer 除外）套一层「本题内同名同参第二次不再执行」，")
w("挡下第 1、2 次各回一句警告，第 %d 次（超过 DUP_BLOCK_LIMIT=%d）熔断收尾。" % (LIMIT + 1, LIMIT))
w("指纹 = (工具名, 按 forward 签名归一后的参数 JSON)，`sort_keys=True`，所以 `{"
  "\"a\":1,\"b\":2}` 和 `{\"b\":2,\"a\":1}` 算同一个；参数归一那份（_bind_args）审批卡和指纹共用。")
w("三本账是**类级**的、每轮开局清零（行号见第二节）——跨题留着就会把上一题查过的路径当成本题的重复")
w("直接挡掉：用户新问一句「列一下 smolagents/」，那是一次真需要执行的调用。")
w()
w("token 口径（本文每个 token 数都按这三档标，别混）：")
w("  · 【实测·累计】框架日志 `[Step N: … Input tokens: I | Output tokens: O]` 那行是监控器**跨题累计**；")
w("  · 【实测·单步】单步 = 相邻两条累计行相减，第一节那两次就是这么算的；")
w("  · 【假数】第四节零成本回放里所有 token 都是剧本设定的假数，那一份只能读次数与形状；")
w("  · 本刀真模型那一路一个 token 都没花出去（百炼 400，第五节当场重探的原文为证）。")
w()

# ---------------------------------------------------------------- 一、立项依据
bar("一、立项依据：把 21:06 那份 transcript 按本刀口径重走一遍")
w("  来源：%s（%d B / %d 行，改于 %s）——这是**你自己那天跑出来的界面日志**，不是我这轮跑的。"
  % (UI_LOG, UI_LOG.stat().st_size, len(clean_lines(UI_LOG)),
     time.strftime("%m-%d %H:%M", time.localtime(UI_LOG.stat().st_mtime))))
w("  切轮依据：日志里 %d 条 `New run - smolagents` 横幅，横幅之间算一轮。每步步号取自 `━━ Step N ━━`。"
  % log.n_banner)
w("  本轮参数：max_steps=%s（my_agent.py 现场读）、DUP_BLOCK_LIMIT=%d（挡 %d 次警告，第 %d 次熔断）。"
  % (MAXSTEPS, LIMIT, LIMIT, LIMIT + 1))
w()
for n, (title, calls) in enumerate(log.runs, 1):
    blocked, fuse = log.walk(calls, LIMIT)
    w("  第 %d 轮｜题面：%s" % (n, title or "【日志里没截到题面行】"))
    w("    调用序列（左＝日志横幅里的步号）：")
    for stp, sig in calls:
        b = [x for x in blocked if x[0] == stp]
        note = ""
        if b:
            note = "  ← 挡下第 %d 次（这个签名的第 %d 遍）" % (len([x for x in blocked if x[0] <= stp]), b[0][2])
            if fuse == stp:
                note += "  ★ 超过上限 %d → 熔断就在这一步" % LIMIT
        w("      步 %-3s %s%s" % (stp, sig[:118], note))
    w("    被挡下 %d 次，落在第 %s 步；熔断位：%s"
      % (len(blocked), ", ".join(str(x[0]) for x in blocked) or "—",
         "第 %s 步" % fuse if fuse else "不触发"))
    w()
w("  两条**独立**的真实记录，形状一样（都是第 %d 次被挡恰好落在第 %s 步=max_steps 边界）："
  % (LIMIT + 1, MAXSTEPS))
bA, fA = log.walk(log.runs[0][1], LIMIT) if log.runs else ([], None)
second = RUN / "v18_p0abc_old_A_r2.out"
s2 = Log(second)
r2 = s2.runs[0][1] if s2.runs else []
b2, f2 = s2.walk(r2, LIMIT)
w("    · 上面第 1 轮（题面：%s）：%d 步、被挡 %d 次（第 %s 步），熔断位=第 %s 步。"
  % (log.runs[0][0][:60] or "【没截到】", len(log.runs[0][1]), len(bA),
     ", ".join(str(x[0]) for x in bA) or "—", fA))
w("    · %s（题 A／old 代码／样本 2，%s 那一轮独立跑出来的，第④刀实跑留档）："
  % (second.name, time.strftime("%m-%d %H:%M", time.localtime(second.stat().st_mtime))))
w("      被挡 %d 次，落在第 %s 步，熔断位=第 %s 步；这一轮 [Step] 累计行 %d 条；"
  % (len(b2), ", ".join(str(x[0]) for x in b2) or "—", f2, len(s2.cum)))
w("      %s 步用满（日志里有 `Reached max steps`）：%s。"
  % (MAXSTEPS, any("Reached max steps" in ln for ln in clean_lines(second))))
w()
w("  反面也得摆出来——不是每一轮都长这样：")
for n, (title, calls) in enumerate(log.runs, 1):
    blocked, fuse = log.walk(calls, LIMIT)
    w("    · 第 %d 轮（%s）：被挡 %d 次 → %s" % (n, (title[:26] or "【没题面】") + "…", len(blocked),
      "熔断（第 %s 步）" % fuse if fuse else
      ("没有同名同参重复，这一层一次都不挡" if not blocked else "只有 %d 句警告，本刀这层不掐它" % len(blocked))))
w("    门槛=%d 的意思就是「绕 %d 圈放过去、绕 %d 圈掐掉」。这是**权衡**不是定理：" % (LIMIT, LIMIT, LIMIT + 1))
w("    改 DUP_BLOCK_LIMIT 会同时改 v18_test_dup.py 第 2 节那批「第几次挡」的数（那里写明了要一起改）。")
w()
w("  熔断落在最后一步时，省掉的到底是哪一次？这一轮日志里有实测（不是估）：")
if delta:
    w("    [Step %d] 累计 in %s / out %s ｜ [Step %d] 累计 in %s / out %s、耗时 %.2fs"
      % (MS, f"{s8[2]:,}", f"{s8[3]:,}", MS + 1, f"{s9[2]:,}", f"{s9[3]:,}", s9[1]))
    w("    → 第 %d 次模型调用（`_handle_max_steps_reached` 里那次收尾补打）"
      "**单步实测 in %s / out %s、%.2f 秒**。" % (MS + 1, delta[0], delta[1], delta[2]))
    w("    注意第 %d 步只有累计行、没有 `━━ Step %d ━━` 横幅——这正是它不是正常一步的痕迹。"
      % (MS + 1, MS + 1))
    w("    而这一轮的第 %d 步本身就是一次重复（上面那张表），所以本刀的 ⛔ 收尾替掉的正是这一次调用。" % MS)
    w("    口径：单样本、监控器累计行相减得到的单步值，只当量级看。")
else:
    w("    【这一轮日志里没同时找到 Step %d/%d 累计行，此项无实测】" % (MS, MS + 1))
w()
sys.path.insert(0, str(SMOL))
import my_agent  # noqa: E402
sp = my_agent.agent.system_prompt
old_a = Log(RUN / "v18_p0abc_old_A.out")
b1 = old_a.walk(old_a.runs[0][1], LIMIT)[0] if old_a.runs else []
new_a_txt = re.sub(r"\s", "", (RUN / "v18_p0abc_new_A.out").read_text(encoding="utf-8", errors="replace"))
old_a_txt = re.sub(r"\s", "", second.read_text(encoding="utf-8", errors="replace"))
SENT = re.sub(r"\s", "", "不要用同一个参数再打一遍")
w("  为什么不能只靠文案：规矩早就写着，实测它照犯——")
w("    渲染出来的 system_prompt（%d 字符，模型每一步都重读这一份）里：" % len(sp))
w("      框架规则「Never re-do a tool call that you previously did with the exact same parameters」→ %s"
  % ("Never re-do a tool call" in sp))
w("    第④刀补在报错文案里的那句「不要用同一个参数再打一遍」：new 样本日志命中 → %s ｜ old 样本 → %s"
  % (SENT in new_a_txt, SENT in old_a_txt))
nb1 = Log(RUN / "v18_p0abc_new_A.out")
nb2 = Log(RUN / "v18_p0abc_new_A_r2.out")
nd1 = len(nb1.walk(nb1.runs[0][1], LIMIT)[0]) if nb1.runs else -1
nd2 = len(nb2.walk(nb2.runs[0][1], LIMIT)[0]) if nb2.runs else -1
w("    可规矩在场照样犯：21:06 那一轮被挡 %d 次（第 %s 步）、%s 那轮 old 样本被挡 %d 次（第 %s 步）——"
  % (len(bA), ", ".join(str(x[0]) for x in bA) or "—",
     time.strftime("%H:%M", time.localtime(second.stat().st_mtime)), len(b1),
     ", ".join(str(x[0]) for x in b1) or "—"))
w("    文案改的是**倾向**（同样按本刀口径走：第④刀之后的 new 两个样本各被挡 %d／%d 次，"
  "old 那两个是 %d／%d 次），管不住的是**上限**。" % (nd1, nd2, len(b1), len(b2)))
w("    所以这一刀不是补规矩，是执法：绕到第 %d 次的时候由门把它掐掉。" % (LIMIT + 1))
w()

# ---------------------------------------------------------------- 二、结构与层序
bar("二、结构与层序（行号是这份写入器现场 grep 出来的，改一行就会跟着变）")


def lineof(text, pat):
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(pat, ln):
            return i
    return None


for label, pat in [
    ("DUP_BLOCK_LIMIT = %d" % LIMIT, r"^DUP_BLOCK_LIMIT = \d+"),
    ("DUP_MARK（警告句／熔断句共用的开头）", r"^DUP_MARK = "),
    ("DUP_FUSE_MARK（认熔断靠它，不能靠 DUP_MARK 计数）", r"^DUP_FUSE_MARK = "),
    ("DUP_OBSERVATION（回给模型的警告句原文）", r"^DUP_OBSERVATION = \("),
    ("DUP_FUSE_OBSERVATION（回给模型的熔断句原文）", r"^DUP_FUSE_OBSERVATION = \("),
    ("类级登记表 _seen_calls", r"^\s*_seen_calls: dict"),
    ("类级计数 _dup_blocked", r"^\s*_dup_blocked: int"),
    ("类级开关 _dup_tripped", r"^\s*_dup_tripped: bool"),
    ("__init__ 里装门（审批之后、计划门之前）", r"self\._install_dup_gate\(\)"),
    ("def _install_dup_gate（套全部工具，final_answer 除外）", r"def _install_dup_gate"),
    ("def _dup_call（算指纹＋记账＋挑文案）", r"def _dup_call"),
    ("def _install_dup_stop（熔断当场收尾那层）", r"def _install_dup_stop"),
    ("_install_dup_gate 末尾顺手装 dup_stop", r"self\._install_dup_stop\(\)"),
    ("收尾判据：只在 ActionStep 之后抛", r"if OpsUI\._dup_tripped and isinstance\(ev, ActionStep\)"),
    ("熔断时同时按下框架的 interrupt()", r"^\s*self\.agent\.interrupt\(\)$"),
    ("def _bind_args（审批卡和指纹共用的参数归一）", r"def _bind_args"),
    ("卡片档位：⚪/⛔ 那一档判定", r'dot = "⛔" if DUP_FUSE_MARK in obs else "⚪"'),
    ("卡片把 挡下/总数 摊在标题上（除以 len(calls) 的理由）", r"dup_hits = obs\.count\(DUP_MARK\)"),
    ("换题清零：_seen_calls.clear()", r"OpsUI\._seen_calls\.clear\(\)"),
    ("状态档：plan_denied / dup_fused / stopped 三选一", r'state = "plan_denied" if denied else'),
    ("熔断认旗（两个都占时认停止）", r"fused = OpsUI\._dup_tripped and OpsUI\._run_seq > OpsUI\._cancelled_before"),
    ("STATE_LABEL 里的「重复熔断」", r'^\s*"dup_fused": "重复熔断",'),
    ("状态条胶囊 CSS st-dup_fused", r"#statusbar\.st-dup_fused"),
]:
    ln = lineof(ui_src, pat)
    w("  my_ui.py:%-5s %s" % (ln if ln else "【找不到】", label))
w()
w("  层序（为什么这么装）：")
w("    `_install_gate()` → `_install_dup_gate()` → `_install_plan_gate()`，__init__ 里就这三行。")
w("    ① 查重必须在审批**之后**装：这里 copy.copy 到的那只，forward 已经是审批那个闭包，")
w("       于是顺序是「先查重，没重复才开审批卡」。反着装会出现一张卡点了 ✔ 允许、")
w("       observation 却是「重复调用未执行」——等于让人批了一件根本没跑的事。")
w("    ② 查重套**全部**工具而不是只套 GATED_TOOLS 那两只：21:06 那批重复全在只读侧")
w("       （list_dir / grep_files），只读侧本来不弹审批，只套写路径等于一层没装上。")
w("    ③ `_install_dup_gate` 末尾顺手装 `_install_dup_stop()`（包**实例**上的 `_run_stream`，")
w("       装法和计划门同一套）。幂等标记 `_opsui_dedup` / `_opsui_dup_stop` 防两个 OpsUI")
w("       把同一次重复记成两笔账——那样第 2 次重复就触发熔断了。")
w()
di = next((ln.strip() for ln in (RUN / "v18_probe_D0.stdout").read_text(encoding="utf-8").splitlines()
           if "dup.install" in ln), "【没找到】")
w("  真 app 里的覆盖面读数（23:50 那份 D0 探针日志的 dup.install 行）：")
w("    %s" % di)
w("    这条能证明的是：门真套到了那 7 只工具上、limit 现场读到 %d；那一轮第 1 步就 400，" % LIMIT)
w("    所以它**不**证明任何重复行为——重复行为看第三、四节。")
w()
w("  一条关键语义：熔断的观察值**仍然交回这一步的 memory**（所以卡片上看得见「为什么这题没了」、")
w("  下一问的记忆里也在），但**本轮的模型读不到它**——收尾就在这一步 yield 之后，不会再有下一次")
w("  generate。这就是第四节两格里「模型被调用次数」那一行差值的直接解释（少的那一次就是收尾补打）。")
w()

# ---------------------------------------------------------------- 三、离线闸
bar("三、离线闸：当场重跑五道（本刀那道全文，另四道是回归）")
rc, gate = run(PY, str(HERE / "v18_test_dup.py"))
for ln in gate.splitlines():
    w("  " + ln)
n_dup = gate.count(" PASS")
w()
w("  v18_test_dup.py：PASS %d 条 / FAIL %d 条 / exit=%d" % (n_dup, gate.count(" FAIL"), rc))
w("  这道闸为什么能离线：这一刀的新逻辑全在四个点上（_install_dup_gate 与 _dup_call、_bind_args、")
w("  _step_card 新档位、_respond 的 except AgentError 分档）。前两个只碰 dict 和 threading.Lock，")
w("  后两个喂假 step / 假流就能钉住。「换题清零」这种只有真两轮才算得准的，这一版不再只钉源码位置，")
w("  第四节连问两遍那格给了它**行为**证据。")
w()
w("  另四道回归（本刀动了 my_ui.py，一起重跑，防止把别的刀改坏）：")
tot = n_dup
for f, what in (("v18_test_nochange.py", "判定面与前三刀锚点没被改坏"),
                ("v18_test_p0abc.py", "第④刀：越界指路／能力穷举／相对路径不猜根"),
                ("v18_test_plan.py", "第③刀：计划可见＋批准动作"),
                ("v18_test_interrupt.py", "第②刀：D8 断开侧（待批卡终态／已中断标记）")):
    r, out = run(PY, str(HERE / f))
    tot += out.count(" PASS")
    tail = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(("全绿", "有红项"))]
    w("    %-24s exit=%d  PASS %2d 条  收尾行：%s  ｜ %s"
      % (f, r, out.count(" PASS"), (tail[-1] if tail else out.splitlines()[-1][:60]), what))
w("    五道合计 PASS %d 条（其中「FAIL」字样在收尾行里是「FAIL=0」那种统计行，不是红项）。" % tot)
w()

# ---------------------------------------------------------------- 四、零成本回放
bar("四、零成本现场回放（真 OpsUI＋真 agent＋真工具＋假模型；当场重跑，全文）")
t0 = time.time()
rc_rep, _ = run(PY, str(HERE / "v18_dup_replay.py"))
rep = (RUN / "v18_p1a_replay.out").read_text(encoding="utf-8").rstrip().splitlines()
CT = {}
for mm in re.finditer(r"^\s+(\w+)\s+on=(.+?)\s+off=(.+?)\s*$", "\n".join(rep), re.M):
    CT[mm.group(1)] = (mm.group(2).strip(), mm.group(3).strip())
i2 = next((i for i, ln in enumerate(rep) if "连问两遍" in ln and ln.startswith("==")), None)
db2 = None
if i2 is not None:
    for ln in rep[i2:]:
        if ln.startswith("==") and "连问两遍" not in ln:
            break
        mm = re.search(r"库: messages=(\d+) 行 / memory=(\d+) 行", ln)
        if mm:
            db2 = mm
            break
for ln in rep:
    w("  " + ln)
w()
w("  写入器给这一节补三条口径（回放本体里也有，这里集中说）：")
w("    · 「各步登记的调用数」在报错那几步是 0，不是丢账：工具抛异常时框架走不到")
w("      agents.py:1436 那句 `memory_step.tool_calls = [...]`（它在执行**之后**才赋值），")
w("      所以报错步只有 error、没有 tool_calls。真执行次数看「逐工具真执行次数」那行——")
w("      那组计数器装在 OpsUI 起门**之前**，所以查重层挡掉的不会进它，它数的才是真的进了 forward 的。")
w("    · 两格只差「查重层在不在」这一处：同进程、同剧本、同批真工具。对照格是给第④刀那版代码路径")
w("      拍 X 光（提前在**这一格自己的**工具副本上打幂等标记），不是把 old 代码 import 进来——")
w("      模块级单例互相污染的话，两格就不是两格了（A12 当场验那 5 只模块级工具没被竖过标记）。")
w("    · 这场跑了 %.1f 秒、零 token 成本、exit=%d。它证不了「模型会不会真这么走」。" % (time.time() - t0, rc_rep))
w()

# ---------------------------------------------------------------- 五、真模型那一路
bar("五、真模型那一路：当场重探百炼 ＋ D0 留档 ＋【未验证】清单")
w("  当场重探（一句话、max_tokens=8，只为知道账户状态；这是本轮唯一一次向百炼发请求）：")
rc_p, out_p = run(PY, "-c", """
# -*- coding: utf-8 -*-
import sys, time
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
from smolagents import ChatMessage, MessageRole
import my_agent
t = time.time()
try:
    r = my_agent.model.generate([ChatMessage(role=MessageRole.USER, content="只回一个字：好")], max_tokens=8)
    print("PROBE-OK %.2fs content=%r usage=%s" % (time.time()-t, str(r.content)[:40], r.token_usage))
except BaseException as e:
    print("PROBE-FAIL %.2fs %s: %s" % (time.time()-t, type(e).__name__, str(e)[:420].replace(chr(10), " ")))
""")
for ln in out_p.splitlines():
    if "PROBE-" in ln:
        w("    " + ln.strip())
if not any("PROBE-" in ln for ln in out_p.splitlines()):
    w("    【探针没打出 PROBE 行，原始尾部】" + out_p.strip().splitlines()[-1][:200])
w()
d0 = (RUN / "v18_probe_D0.stdout").read_text(encoding="utf-8")
d0_mt = time.strftime("%m-%d %H:%M", time.localtime((RUN / "v18_probe_D0.stdout").stat().st_mtime))
summ = (RUN / "v18_live_summary_D0.out").read_text(encoding="utf-8")
m = re.search(r'D6-status-1": "([^"]+)', summ)
w("  D0 场景（21:06 原题面连问两遍：第一遍看熔断掐短，第二遍看换题清零）——留档：")
for f in ("v18_probe_D0.stdout", "v18_probe_D0.server.log", "v18_live_summary_D0.out",
          "v18_live_cdp_D0.json", "v18_live_D0.sqlite3"):
    p = RUN / f
    if f.endswith(".sqlite3"):
        w("    %-30s %6d B（探针专用库，不读行；真库 .agent-history.sqlite3 没被碰）  改于 %s"
          % (f, p.stat().st_size, time.strftime("%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))))
    else:
        w("    %-30s %6d B / %3d 行  改于 %s" % (f, p.stat().st_size,
          len(p.read_bytes().splitlines()), time.strftime("%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))))
w("  波及面（本刀所有落盘都在 run/ 下的探针专用库；真库这份写入器只 stat、不打开）：")
real = SMOL / ".agent-history.sqlite3"
w("    %s" % real)
w("    %d B / mtime %s —— 和你 21:06 那次跑完之后是同一个读数，本刀没写过它。"
  % (real.stat().st_size, time.strftime("%m-%d %H:%M:%S", time.localtime(real.stat().st_mtime))))
w("    回放两格用的是 run/v18_p1a_replay_on.sqlite3（%d B）与 _off.sqlite3（%d B），"
  % ((RUN / "v18_p1a_replay_on.sqlite3").stat().st_size, (RUN / "v18_p1a_replay_off.sqlite3").stat().st_size))
w("    D0 用的是 run/v18_live_D0.sqlite3；7860 那个 app 的进程与端口本刀没碰过。")
w()
w("  那份留档里的报错原文（第一次调用就挡死，一步都没走）：")
for ln in d0.splitlines():
    if "Error code" in ln or "standing" in ln or "overdue-payment" in ln:
        w("    " + ln.strip())
w("  这份留档跑在 %s（早于本刀最后一次改动，即那版还没有「只在 ActionStep 之后收尾」这条判据）：" % d0_mt)
w("    能证明：真 app 起得来、查重层装上了（第二节那条 dup.install）、半截内容照样落库")
w("            （save.enter/exit 那两行 msgs=3）、收尾状态条读数=%s"
  % ("「%s」" % m.group(1)[:70] if m else "【没截到】"))
w("    不能证明：任何一次重复、熔断、⛔ 档位、收尾档位——模型一次都没回过话。")
w()
w("  【未验证】清单（账户恢复后由 `v18_run_live.py D0` 补，逐项列，不含糊）：")
for head, sub in [
    ("模型收到「重复调用未执行」这句观察值之后**会不会换参数**",
     "v18_test_dup.py 第 1 节钉住了两句观察值的原文，但「它进得去下一轮上下文、并且真的改变了下一步」"
     "只有真跑算，剧本假不了这个"),
    ("模型会不会自己走到「第 %d 次同样的调用」" % (LIMIT + 1),
     "21:06 那轮和 23:15 那轮各走过一次，样本是两个；qwen-plus 有温度，步数与走法只能当倾向"),
    ("stream_outputs=True（逐字 delta 上屏）下熔断的帧序",
     "回放里 ScriptModel 没有 generate_stream，agents.py:1252-1255 见到 stream_outputs=True 就拒构造，"
     "所以那一段整个没进回放"),
    ("⛔ 那一档在真浏览器上的呈现",
     "前三刀做过的 CDP 截图口径这一刀没做，因为 app 打不到模型；离线只钉了 state／class／标题三处字符串"),
    ("写路径工具被重复调用时的观感（查重在外层，压根不开审批卡）",
     "离线闸第 1 节有「审批卡不许为重复调用打开」这条断言，它钉的是装门顺序的结果，不是屏幕上的观感"),
]:
    w("    · %s" % head)
    w("      %s" % sub)
w()

# ---------------------------------------------------------------- 六、行为语义变化
bar("六、行为语义变了什么（这刀不是纯文案，动了执行路径，逐条列）")
for k, v in [
    ("工具会不会被执行", "本题内第 2 次起的同名同参调用**不再进 forward**，改为回一句警告；第一次永远照常执行。"),
    ("屏幕上的档位", "步骤卡片新增两档：⚪ 重复未执行 n/m、⛔ 重复熔断 n/m。m 是这一步登记的调用数——"
                 "一步里可以并行发好几个调用，只挡其中一个很正常，写成整步「未执行」就是假账。"),
    ("状态条与收尾气泡", "新增一档状态「重复熔断」（state 值 dup_fused，CSS 胶囊 st-dup_fused 独立配色）。"
                  "收尾气泡标题「⛔ 重复熔断」，正文带「本题挡下的重复调用超过了上限 %d 次，已在步边界收场」。" % LIMIT),
    ("和 ■ 停止抢位", "熔断走的也是框架的 interrupt()，两档在异常层完全同名（agents.py:547「Agent interrupted.」）。"
                 "现在认 _dup_tripped 旗分档；**两个都占时认停止**——人先按下去，熔断只是那一下带来的下一步，"
                 "不能写成「你按了停止」让用户告自己的状。"),
    ("8 步用满那一档", "熔断落在最后一步时**不再走 _handle_max_steps_reached**：状态是 dup_fused 不是 maxed，"
                  "省掉第一节实测的那次 %s 收尾补打；对照格（无查重层）仍旧走 maxed。" % saved),
    ("收尾时机", "只在一步**齐了**（ActionStep 已经 yield）之后抛。早先在 ToolOutput 之后抛的那一版，"
              "回放当场把它拍红了（A4/A5）：第 8 步的卡片压根没画出来、memory 里那一步 observations 是空的，"
              "熔断那句话只活在收尾气泡里，屏幕上看不见「它是在哪一步、因为哪一次调用被拦的」。"),
    ("落库", "熔断题照常落库，只是少掉收尾补打那一步的一条消息；两格的具体行数看下面那张表。"),
    ("下一问", "不受污染：interrupt_switch 与 step_number 由框架每轮重置（agents.py:470 / 543），"
             "三本账由 _stream_response 开局清零。回放里连问两遍那一格给的就是这条行为证据——"
             "第二问的形状与第一问逐格相同，库落在同一条会话上继续追加（D5 语义没被碰坏，行数见下表）。"),
    ("命令行跑法", "不变：门只覆盖实例上的 forward，my_coding_agent 那批模块级工具没被写过（回放 A12）。"
               "`python my_coding_agent.py` 不经过 UI，也就不会被这层拦。"),
]:
    w("  · %s：%s" % (k, v))
w()
w("  回放那两格的读数（第四节对照表原样搬，程序自己抓的，不是我手打）：")
for k in ("model_calls", "action_steps", "calls", "blocked", "executed", "dup_steps", "fuse_steps", "answered", "state", "db"):
    if k in CT:
        w("    %-13s on=%-12s off=%s" % (k, CT[k][0], CT[k][1]))
w("    （第四节那张对照表本来就是 `on=… off=…` 一行一项，这里按同一个顺序原样搬。）")
w("    calls 是 memory 里登记的调用数，和 executed（真进 forward 的次数）不是一回事：")
w("    报错那几步只有 error、没有 tool_calls，差额正好是带 error 的那几步，口径见第四节第一条。")
if db2:
    w("    连问两遍那一格的库：messages=%s 行 / memory=%s 行（第一问：on 格 %s）"
      % (db2.group(1), db2.group(2), CT.get("db", ("?", "?"))[0]))
w()
w("  没变：判定面（哪只在审批名单、路径白名单、DENY 名单）、异常类型、第②③④刀的语义、")
w("  上游 src/smolagents/（第七节 git 现场）。")
w("  你那边要吃到这一刀：**7860 那个 app 得重启**，它加载的是内存里那份 my_ui.py。")
w()

# ---------------------------------------------------------------- 七、体量与成本
bar("七、体量与成本")
d = sh("diff", "-u", str(BACK / "my_ui.py"), str(SMOL / "my_ui.py"))
hunks = len(re.findall(r"^@@", d, re.M))
adds = len([x for x in d.splitlines() if x.startswith("+") and not x.startswith("+++")])
dels = len([x for x in d.splitlines() if x.startswith("-") and not x.startswith("---")])
w("  my_ui.py：%d 行 / %d B（%s）→ %d 行 / %d B（%s）" % (lb0, bb0, hs0[:8], lb, bb, hs[:8]))
w("            %+d 行 / %+d B；diff %d 个 hunk，+%d / -%d 行" % (lb - lb0, bb - bb0, hunks, adds, dels))
w("  行数自洽：%d（旧）+%d（增）-%d（删）=%d，和 wc 读到的 %d %s"
  % (lb0, adds, dels, lb0 + adds - dels, lb, "对得上" if lb0 + adds - dels == lb else "【对不上，去看 diff】"))
w("  另两个文件逐字节未动：")
for f in ("my_agent.py", "my_coding_agent.py"):
    w("    %-20s live=%s  after-p0abc=%s  逐字节相同=%s"
      % (f, sha8(SMOL / f), sha8(BACK / f), (SMOL / f).read_bytes() == (BACK / f).read_bytes()))
w("  上游源码零改动（本刀没碰 smolagents 本体，git 现场）：")
g = sh("git", "status", "--porcelain", "src/smolagents").strip()
w("    `git status --porcelain src/smolagents` → %s" % (g or "（空输出＝一个文件都没改）"))
w("  token 消耗：本轮 %s（百炼 400 在第一次调用就挡死；第四节回放里全是剧本假数，不记账）。"
  % ("0" if not any("PROBE-OK" in ln for ln in out_p.splitlines()) else "非 0：见第五节探针行"))
w("  本写入器的时间成本：三节五道闸＋四节一场回放＋五节一次探针，约 40 秒。")
w()

# ---------------------------------------------------------------- 八、回滚演练
bar("八、回滚演练（双向，本刀改完后跑的那一场，全文照搬）")
for ln in (RUN / "v18_p1a_drill.out").read_text(encoding="utf-8").rstrip().splitlines():
    w("  " + ln)
w()
w("  写入器**没有**再跑一次演练：每跑一次都要在约 5 秒窗口里把 live 的 my_ui.py 覆盖成第④刀那版。")
w("  现场正在跑的 app 读的是内存里那份，覆盖磁盘动不到它，但你恰好在那 5 秒里重启就吃到半截。")
drill = (RUN / "v18_p1a_drill.out").read_text(encoding="utf-8")
dm = re.search(r"现场 my_ui\.py=(\w{8}) (\d+) 行", drill)
w("  对上号：演练起表行记的现场是 sha1=%s / %s 行，本文件「被测」行是 %s / %d 行 —— 同一个文件%s"
  % (dm.group(1), dm.group(2), hs[:8], lb, ("，所以那一场验的就是现在这份代码。"
     if (dm.group(1) == hs[:8] and int(dm.group(2)) == lb) else "【对不上，演练要重跑】")))
w()

# ---------------------------------------------------------------- 九、边界与待办
bar("九、边界与待办")
w("  往下这些都没授权，只报告不动手：")
for x in ["P1-b plan_delete 预览", "P2-a .agent-ui.log/.pid 出 ROOT", "P2-b 非法 JSON arguments",
          "D3 逐步落库", "「cancelled」观察值措辞",
          "#42 D8-2：刷新后首屏读到还没写完的库（已量到 0.761 s 窗口，等你点头立单）"]:
    w("    · %s" % x)
w()
w("  第四节顺带发现的、属于**对照格（步数用满）那一路**的两条（本刀走不到，只记录）：")
w("    · agents.py:606-608 在 _handle_max_steps_reached 之后又 yield 一次同一个 action_step，")
w("      所以「8 步用满」那一路屏上第 8 步的卡会出现两遍（回放对照格实测过那一串标题）。")
w("      要不要给它单开一张收尾卡，等你点头。")
w("    · 那一次补打的模型只认正文（agents.py:627-637 取 final_answer.content），tool_calls 不执行。")
w()
w("  第五节 D0 留档里还有一条不属于本刀的：模型侧 400 抛 AgentGenerationError，界面把它归进")
w("  「已停止」那一档（except AgentError 里非 plan_denied、非熔断就是 stopped），和你按 ■ 停止同名。")
w("  这是 v1.3 起就有的分档，本刀没碰——要不要单开一档「模型侧报错」，等你点头。")
w()
w("  改门槛要一起动的东西：DUP_BLOCK_LIMIT 改一个数，离线闸第 2 节那批「第几次挡」会红（故意的，")
w("  语义和数字必须一起改）；第四节回放剧本的 [3,4,8] 形状不受影响，但 A4/A5 的期望值要重算。")
w()
w("  最后一句边界：这一刀**降低**的是重复调用被真的执行的机会（读侧只多一次模型往返，写侧本来就要过审批）。")
w("  它不保证模型不绕圈——它保证绕到第 %d 次时这一题干净结束，而且屏幕上看得见在哪一步、" % (LIMIT + 1))
w("  因为哪一个签名被拦（第四节 dup-on 那串卡片就是这一条的证据）。")
w()
w("  下一件：#43 v1.8 归档 ＋ 整版回滚演练 ＋ 迭代记录.md v1.8 节 ＋ 手册 §4/§6 ＋ README ＋ 五道文档闸。")

OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("写入 %s：%d 行 / %d 字节" % (OUT.name, len(L), OUT.stat().st_size))
