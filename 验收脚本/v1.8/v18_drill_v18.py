# -*- coding: utf-8 -*-
"""v1.8 整版回滚演练（双向）：v1.7 基线 ↔ v1.8 现场，三个文件一起换。

和第⑤刀那一场（v18_drill_p1a.py，换 my_ui.py 一份）的区别：
  · 换的是**整版**——`my_ui.py` + `my_agent.py` + `my_coding_agent.py` 三份同进同出。
    v1.8 四刀里第④刀压根没碰 my_ui.py（改的是 my_coding_agent.py 的报错文案与 description、
    my_agent.py 的 description），所以只换一份的演练**测不到那一刀的回滚**。
  · 断言按**四刀**分组，每刀的锚点从归档链（.rollback/v1.8/after-d8|p04|p0abc|p1a）当场导出来，
    不是我手抄的名单。
  · ④那一刀额外给**行为**断言：真调 `my_coding_agent.guarded()`，看报错文案在不在。
    只 grep 源码的话，「文案写进注释里」这种假绿挡不住。

现场在哪：
  · v1.7 基线 = `smolagents/.rollback/v1.8/{my_ui,my_agent,my_coding_agent}.py`
    （第②刀动手前那一次 cp，2026-11-03 21:24）。**另做一份独立交叉核对**：
    `ai学习/.rollback/v1.7/my_ui.py` 与它逐字节相同（同一版本、两套时间、两次落笔）。
  · v1.8 版快照 = 本脚本第一步 cp 出来的 `ai学习/.rollback/v1.8/`（与 v1.0~v1.7 同一侧、同一命名口径）。

窗口与风险：演练期间现场文件会在 v1.7 / v1.8 之间来回覆盖。正在跑的 7860 应用加载的是**内存里**
那份代码，覆盖磁盘动不到它；唯一的风险是这个窗口内**恰好有人重启它**，那它会读到窗口当时那一版。
所以脚本前后各抓一次 `lsof -iTCP:7860`（PID 必须同一个）与真库 `.agent-history.sqlite3` 的
size/mtime（本演练只读它、不打开它），并把窗口秒数当场打出来。异常走 finally 复位到 v1.8。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_drill_v18.py
产物：run/v18_drill_v18.out ＋ ai学习/.rollback/v1.8/（三份，v1.8 版快照）
"""
import hashlib
import pathlib
import py_compile
import re
import shutil
import subprocess
import sys
import time

AI = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
SMOL = AI / "smolagents"
V = SMOL / ".rollback/v1.8"          # v1.7 基线三份 ＋ 分刀链快照
AR = AI / ".rollback/v1.8"           # 本轮新建：v1.8 整版快照（与 v1.0~v1.7 同侧）
RUN = pathlib.Path(__file__).resolve().parent / "run"
OUT = RUN / "v18_drill_v18.out"
PY = str(SMOL / ".venv/bin/python")
FILES = ["my_ui.py", "my_agent.py", "my_coding_agent.py"]
HIST = SMOL / ".agent-history.sqlite3"
# 分刀链快照目录名，按动手先后排（V 根目录下那三份是这条链的起点＝v1.7 基线）
CHAIN = ["after-d8", "after-p04", "after-p0abc", "after-p1a"]

# 每刀独有的名字。**不写死数量**：断言里报「找到几个 / 该有几个」，有几个都由这份清单算。
# 来源：分刀链快照的标识符差集（脚本下面自己会再核一遍，两边不一致就红）。
SLICE_NAMES = {
    "②D8": ["_mark_interrupted", "_ap_cards", "cancelled_by_reload"],
    "③P0-4": ["_install_plan_gate", "PlanDeniedError", "plan_denied", "_opsui_plan_gated",
               "PLANNING_INTERVAL", "_generate_planning_step", "_plan_shown", "_last_plan",
               "PLAN_APPROVAL_NAME", "_finalize_step"],
    "④P0abc": ["这一整套工具（read_file／list_dir／grep_files／write_file／run_python）只服务这一个根",
                "不要用同一个参数再打一遍", "做不到的（别试，也别对用户承诺）",
                "relative = not os.path.isabs(raw)", "没有删除／移动／重命名／访问网络"],
    "⑤P1-a": ["_install_dup_gate", "_install_dup_stop", "_dup_call", "_seen_calls", "_dup_blocked",
              "_dup_tripped", "_bind_args", "DUP_MARK", "DUP_FUSE_MARK", "DUP_BLOCK_LIMIT",
              "DUP_OBSERVATION", "DUP_FUSE_OBSERVATION", "dup_fused"],
}
# 每刀对应的归档链快照目录（第三步用它算「这个名字是哪一刀带进来的」）
SLICE_STEP = {"②D8": "after-d8", "③P0-4": "after-p04", "④P0abc": "after-p0abc", "⑤P1-a": "after-p1a"}
# v1.7 那一版自己的锚点：两个方向都必须绿（证明这是加法式改动，没把老东西改掉）。
KEPT_V17 = ["MEM_FMT", "MEM_FMT_READ", "_session_steps", "encode_memory", "decode_memory",
            "GATED_TOOLS", "_install_gate", "_step_card", "_approval_card", "DARK_CSS",
            "_status_html", "task_wait", "_bind_memory", "_settle_all", "DENY_NAMES",
            "annualized_volatility", "max_drawdown"]

FAIL = []
NOK = 0
LINES = []


def emit(line=""):
    LINES.append(line)
    print(line)


def ok(name, cond, detail=""):
    global NOK
    NOK += 1
    line = "%-46s %s %s" % (name, "PASS" if cond else "FAIL", detail)
    emit(line)
    if not cond:
        FAIL.append(name)
    return bool(cond)


def sha1(p):
    return hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest()


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


def probe(code):
    """新进程里跑一段 python，返回 (exit, 末行)。用来验 import 层与 guarded() 的行为。"""
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=str(SMOL))
    tail = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode, (tail[-1] if tail else "")


def stat(p):
    s = p.stat()
    return s.st_size, time.strftime("%m-%d %H:%M:%S", time.localtime(s.st_mtime))


def lsof7860():
    r = subprocess.run(["lsof", "-nP", "-iTCP:7860", "-sTCP:LISTEN"], capture_output=True, text=True)
    return sorted({c.split()[1] for c in r.stdout.splitlines()[1:]}) if r.returncode == 0 else []


def boundary(step):
    """返回 (这一刀动手前, 这一刀完成后) 两份现场，三份文件都算。
    这一节不看我抄的名单，只用归档链自己证「这个名字确实是这一刀带进来的」：
    判据是子串级的**上一版没有、这一版有**（标识符正则会漏掉 `PlanDeniedError` 这类驼峰名，
    也挡不住「写进注释」的假绿，所以不用它）。"""
    prev_dir = V if step == CHAIN[0] else V / CHAIN[CHAIN.index(step) - 1]
    cur_dir = V / step
    return [(read(prev_dir / f), read(cur_dir / f)) for f in FILES]


def guarded_probe(expect_v18, label_h):
    """真调 guarded()：相对路径不存在 → FileNotFoundError；根外 → PermissionError。
    ④那一刀改的就是这两条文案，所以这是行为断言，不是 grep。"""
    code = (
        "import my_coding_agent as m\n"
        "for arg, tag in [('人生-不存在-演练专用', 'rel'), ('../../演练根外', 'out')]:\n"
        "    try:\n"
        "        m.guarded(arg)\n"
        "        print(tag, 'NO-RAISE')\n"
        "    except Exception as e:\n"
        "        print(tag, type(e).__name__, 'P0A' if '不要用同一个参数' in str(e) else '-',\n"
        "              'P0C' if '不会去猜别的根目录' in str(e) else '-', 'len=%d' % len(str(e)))\n"
    )
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=str(SMOL))
    rel = next((x for x in r.stdout.strip().splitlines() if x.startswith("rel ")), "")
    got = ("P0A" in rel and "P0C" in rel) if expect_v18 else ("P0A" not in rel and "P0C" not in rel)
    ok("%s guarded() 相对路径报错文案%s" % (label_h, "带 P0-a/P0-c 两句" if expect_v18 else "是 v1.7 那一版"),
       r.returncode == 0 and got, rel[:120] or r.stderr.strip()[:120])
    return [x for x in r.stdout.strip().splitlines() if x.startswith(("rel ", "out "))]


def run_side(label, src_dir, expect_v18):
    emit("\n---- 方向：%s（%s）----" % (label, src_dir))
    t0 = time.time()
    for f in FILES:
        shutil.copy2(src_dir / f, SMOL / f)
    for f in FILES:
        py_compile.compile(str(SMOL / f), doraise=True)
    ok("%s-a 三份文件 py_compile 通过" % label, True, "%.1fs" % (time.time() - t0))

    ui, ag, ca = read(SMOL / "my_ui.py"), read(SMOL / "my_agent.py"), read(SMOL / "my_coding_agent.py")
    # 1) 四刀锚点逐刀判
    for s, names in sorted(SLICE_NAMES.items()):
        hit = [n for n in names if n in ui] if s != "④P0abc" else [n for n in names if n in ui or n in ca or n in ag]
        miss = [n for n in names if n not in hit]
        if expect_v18:
            ok("%s-b %s 的 %d 个锚点全在" % (label, s, len(names)), len(hit) == len(names),
               "缺: %s" % (miss or "无"))
        else:
            ok("%s-b %s 的 %d 个锚点一个都不在" % (label, s, len(names)), not hit, "还找到: %s" % (hit or "无"))
    # 2) v1.7 老锚点两个方向都要在（这一组跨三份文件：DENY_NAMES 在 coding agent，
    #    max_drawdown／annualized_volatility 在那两份的工具备注里）
    allsrc = ui + ag + ca
    miss = [k for k in KEPT_V17 if k not in allsrc]
    ok("%s-c v1.7 的 %d 个锚点全在（三份文件合起来看；加法式改动）" % (label, len(KEPT_V17)),
       not miss, "缺: %s" % (miss or "无"))
    # 3) 体量与逐字节
    n, b = ui.count("\n"), len(ui.encode())
    ok("%s-d my_ui.py 行数/字节 == 该方向快照（%d 行 / %d B）" % (label, n, b),
       sha1(SMOL / "my_ui.py") == sha1(src_dir / "my_ui.py"), sha1(SMOL / "my_ui.py")[:8])
    for f in FILES[1:]:
        ok("%s-e %s 逐字节 == 该方向快照" % (label, f),
           (SMOL / f).read_bytes() == (src_dir / f).read_bytes(), "%d 行 / %d B" % (
               read(SMOL / f).count("\n"), len(read(SMOL / f).encode())))

    # 4) import 层：三层门 + 计划门在不在，由这一版的代码自己回答
    code = ("import my_agent, my_ui\n"
            "from my_ui import OpsUI\n"
            "print('dup=%s plan=%s mark=%s seen=%s pi=%s memfmt=%s'\n"
            "      % (hasattr(OpsUI, '_install_dup_gate'), hasattr(OpsUI, '_install_plan_gate'),\n"
            "         hasattr(OpsUI, '_mark_interrupted'), hasattr(OpsUI, '_seen_calls'),\n"
            "         my_agent.agent.planning_interval, my_ui.MEM_FMT))\n")
    rc, out = probe(code)
    want = "dup=True plan=True mark=True seen=True pi=8" if expect_v18 else "dup=False plan=False mark=False seen=False pi=None"
    ok("%s-f import 起来，门与计划层在/不在（%s）" % (label, want), rc == 0 and want in out, out[:110])
    # 5) 只有 v1.8 才 import 得到的两个名字
    for nm in ("DUP_MARK", "PlanDeniedError"):
        rc2, out2 = probe("from my_ui import %s" % nm)
        ok("%s-g `from my_ui import %s` %s" % (label, nm, "import 得到" if expect_v18 else "按要求 ImportError"),
           (rc2 == 0) == expect_v18, "" if expect_v18 else out2[:56])
    # 6) ④ 的行为探针
    guarded_probe(expect_v18, label)
    # 7) v1.8 方向额外验接线（层序与「熔断收尾挂在查重层末尾」）
    if expect_v18:
        ok("%s-h 接线：__init__ 里 gate→dup_gate→plan_gate 的顺序" % label,
           re.search(r"self\._install_gate\(\)[\s\S]{0,240}?self\._install_dup_gate\(\)\s*\n\s*self\._install_plan_gate\(\)", ui), "")
        ok("%s-i 接线：_install_dup_gate 末尾顺手装 dup_stop" % label,
           re.search(r"def _install_dup_gate[\s\S]{0,2600}?self\._install_dup_stop\(\)", ui), "")
        ok("%s-j 收尾时机：只在 ActionStep 之后抛" % label,
           re.search(r"if OpsUI\._dup_tripped and isinstance\(ev, ActionStep\)", ui), "")
    return n, b


def main():
    emit("== v1.8 整版回滚演练（v1.7 ↔ v1.8，双向）==")
    emit("起表 %s   7860 监听 PID=%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), lsof7860() or "无"))
    live = {f: sha1(SMOL / f) for f in FILES}
    emit("   现场：" + "  ".join("%s=%s %d行/%dB" % (f, live[f][:8], read(SMOL / f).count("\n"),
                                                    len(read(SMOL / f).encode())) for f in FILES))
    pid0, hist0 = lsof7860(), stat(HIST)
    emit("   波及面起点：真库 %s/.agent-history.sqlite3 = %d B / mtime %s（本演练只 stat，不打开）"
         % (SMOL, hist0[0], hist0[1]))

    # 第一步：把整版快照落到 ai学习/.rollback/v1.8/（v1.0~v1.7 同一侧、同一口径）
    # 但**只在还没有历史的时候落一次**。2026-11-04 20:47/22:29 这两次重跑，就是把
    # 「v1.8 交付版快照」当成本次运行的现场另存了一遍——v1.8 终版从此没了，
    # 而根目录 .rollback/vN.N 是全项目唯一的回滚目标与负控尺子（v18_test_nochange 就讀它）。
    if any((AR / f).exists() and (AR / f).read_bytes() != (SMOL / f).read_bytes() for f in FILES):
        emit("!! %s 已有内容且与现场不同 → 那是**已交付版本的历史快照**，本次不覆盖" % AR)
        for f in FILES:
            emit("   %s：快照 %s ≠ 现场 %s" % (f, sha1(AR / f)[:8], live[f][:8]))
        ok("尺子仍是历史版本（快照三份里至少一份与现场不同字节）",
           any((AR / f).read_bytes() != (SMOL / f).read_bytes() for f in FILES),
           "重跑演练不会把它刷成现场")
        emit("!! 要重取整版快照请显式换目录名（例如 .rollback/v2.0），别覆写 v1.8 那一格。")
    else:
        AR.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            shutil.copy2(SMOL / f, AR / f)
        for f in FILES:
            ok("快照 ai学习/.rollback/v1.8/%s 与现场逐字节一致" % f,
               (AR / f).read_bytes() == (SMOL / f).read_bytes(), sha1(AR / f)[:8])
    ok("快照目录份数 == 3（my_ui/my_agent/my_coding_agent）",
       sorted(p.name for p in AR.glob("*.py")) == sorted(FILES), " ".join(sorted(p.name for p in AR.glob("*.py"))))

    # 第二步：两套独立归档互核（v1.7 那一版）
    emit("\n---- 基线互核：本轮 cp 的 v1.7 现场 vs v1.7 交付档 ----")
    b_ui = V / "my_ui.py"
    v17_ui = AI / ".rollback/v1.7/my_ui.py"
    ok("smolagents/.rollback/v1.8/my_ui.py == ai学习/.rollback/v1.7/my_ui.py（两份独立落笔）",
       b_ui.read_bytes() == v17_ui.read_bytes(), "%s == %s" % (sha1(b_ui)[:8], sha1(v17_ui)[:8]))
    b_ca, v17_ca = V / "my_coding_agent.py", AI / ".rollback/v1.7/my_coding_agent.py"
    same_ca = b_ca.read_bytes() == v17_ca.read_bytes()
    emit("   my_coding_agent.py：本轮基线 %d 行 / v1.7 交付档 %d 行 → %s"
         % (read(b_ca).count("\n"), read(v17_ca).count("\n"),
            "逐字节相同" if same_ca else "不同（D2 ② 那 4 行注释在交付档之后才加，见迭代记录 v1.7 §7）"))
    emit("   所以「退向 v1.7」用的是本轮动手前那份现场（my_coding_agent.py %d 行），不是 10-30 的交付档；"
         % read(b_ca).count("\n") + "行数差 %d 行。" % (read(b_ca).count("\n") - read(v17_ca).count("\n")))
    emit("   my_agent.py：v1.7 交付档里没有这一份（那一版没改它），本轮基线 %d 行——基线口径以本轮 21:24 那次 cp 为准。"
         % read(V / "my_agent.py").count("\n"))

    # 第三步：锚点来源核对＋分刀体量表（全部由归档链现场算）
    emit("\n---- 锚点来源核对（每刀名单 vs 归档链前后两版）----")
    for s in sorted(SLICE_NAMES):
        step = SLICE_STEP[s]
        pairs = boundary(step)
        bad = []
        for n in SLICE_NAMES[s]:
            in_cur = any(n in cur for _, cur in pairs)
            in_prev = any(n in prev for prev, _ in pairs)
            if not (in_cur and not in_prev):
                bad.append("%s(这一版%s/上一版%s)" % (n[:22], "有" if in_cur else "无",
                                                    "有" if in_prev else "无"))
        ok("%s 的 %d 个锚点确为「%s」这一刀带进来的" % (s, len(SLICE_NAMES[s]), step), not bad,
           "不合判据: %s" % (bad or "无"))
    emit("\n---- 分刀体量（归档链前后两版当场算，不是抄证据文件）----")
    emit("   %-10s %-22s %s" % ("刀", "快照", "my_ui.py / my_agent.py / my_coding_agent.py"))
    tot = {f: 0 for f in FILES}
    for step in CHAIN:
        pairs = boundary(step)
        cells = []
        for f, (prev, cur) in zip(FILES, pairs):
            dl = cur.count("\n") - prev.count("\n")
            db = len(cur.encode()) - len(prev.encode())
            tot[f] += db
            cells.append("%+d行/%+dB" % (dl, db))
        emit("   %-10s %-22s %s" % (next(k for k, v in SLICE_STEP.items() if v == step), step, "  ".join(cells)))
    live_sizes = {f: (read(SMOL / f).count("\n"), len(read(SMOL / f).encode())) for f in FILES}
    base_sizes = {f: (read(V / f).count("\n"), len(read(V / f).encode())) for f in FILES}
    emit("   整版：基线 %s → v1.8 %s；净增 %s（三份文件相加 %d B）"
         % ("、".join("%s %d行" % (f, base_sizes[f][0]) for f in FILES),
            "、".join("%s %d行" % (f, live_sizes[f][0]) for f in FILES),
            "、".join("%+d行" % (live_sizes[f][0] - base_sizes[f][0]) for f in FILES),
            sum(live_sizes[f][1] - base_sizes[f][1] for f in FILES)))

    # 第四步：双向
    t_swap = time.time()
    try:
        run_side("退向v1.7", V, False)
        run_side("进向v1.8", AR, True)
    finally:
        for f in FILES:
            shutil.copy2(AR / f, SMOL / f)
    window = time.time() - t_swap

    # 第五步：恢复后的现场与逐字节
    emit("\n---- 恢复后现场 ----")
    for f in FILES:
        ok("cmp 逐字节：现场 == ai学习/.rollback/v1.8/%s" % f,
           (SMOL / f).read_bytes() == (AR / f).read_bytes() and sha1(SMOL / f) == live[f], live[f][:8])
    ok("现场 == 演练开始前那次读数（三份 sha1 全对）",
       {f: sha1(SMOL / f) for f in FILES} == live, " ".join(live[f][:8] for f in FILES))

    # 第六步：五道离线闸在恢复后的树上原样重跑
    emit("\n---- 恢复后的树上重跑 v1.8 五道离线闸 ----")
    tot_p = tot_f = 0
    for s in ["v18_test_interrupt.py", "v18_test_plan.py", "v18_test_p0abc.py",
              "v18_test_nochange.py", "v18_test_dup.py"]:
        r = subprocess.run([PY, str(pathlib.Path(__file__).parent / s)],
                           capture_output=True, text=True, cwd=str(SMOL))
        # 红项计数只认「判决位」上的 FAIL（后面不跟 = 或字母数字）：
        # v18_test_p0abc.py 的收尾行印的是「全绿  FAIL=0」，那是统计行不是红项。
        # 主判据是这套件自己的 exit code（五套都是 sys.exit(1 if FAIL else 0)）。
        p = len(re.findall(r"\bPASS\b", r.stdout))
        f = len(re.findall(r"FAIL(?![=\w])", r.stdout))
        tot_p += p
        tot_f += f
        ok("五道闸之一 %s" % s, r.returncode == 0 and f == 0, "PASS %d / FAIL %d / exit=%d" % (p, f, r.returncode))
    ok("五道合计 FAIL == 0", tot_f == 0, "合计 PASS %d / FAIL %d" % (tot_p, tot_f))

    # 第七步：7860 与真库没被动过
    pid1, hist1 = lsof7860(), stat(HIST)
    emit("\n---- 波及面收口 ----")
    ok("7860 监听 PID 演练前后同一个（应用没被这演练碰到）", pid0 == pid1, "%s → %s" % (pid0 or "无", pid1 or "无"))
    ok("真库 .agent-history.sqlite3 size+mtime 演练前后一致（只 stat 过）",
       hist0 == hist1, "%d B / %s" % hist1)
    ok("上游 src/smolagents/ 零改动（git status --porcelain 空）",
       subprocess.run(["git", "-C", str(SMOL), "status", "--porcelain", "src/smolagents"],
                      capture_output=True, text=True).stdout.strip() == "", "")
    emit("   现场被覆盖的窗口：%.1f 秒（退向＋进向两场断言都在窗口内跑；7860 那 1 个进程全程在listen，"
         "它读的是内存里那份代码，窗口内**别重启它**）" % window)

    emit("\n演练结论：%s（%d 条断言，失败 %d 条；窗口 %.1f 秒；整版快照 3 份已落 %s）"
         % ("双向都能换、换回来逐字节一致" if not FAIL else "有红项：" + "、".join(FAIL),
            NOK, len(FAIL), window, AR))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        print("[written] %s  %d 行 / %d B" % (OUT, len(LINES), OUT.stat().st_size))
    sys.exit(rc)
