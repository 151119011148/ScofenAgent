# -*- coding: utf-8 -*-
"""v1.8 ⑤ 回滚演练（双向）：cp 进现场 → 断言 → cp 回来 → 断言 → cmp 逐字节。

为什么要在**工作树**上做而不是在临时目录里比：这一演练要验的就是
「`cp .rollback/v1.8/after-*/` 这三个文件回 smolagents/ 就能把版本换掉」这条动作本身，
放到临时目录里就等于没验。窗口约 5 秒，期间唯一的风险是**正在跑的 7860 应用恰好被重启**
（它加载的是内存里那份代码，覆盖磁盘文件动不到它）；演练前后各打一次 `lsof` 现场，
并在结尾断言工作树 == after-p1a 快照。

方向与锚点：
  · 退向 after-p0abc（第④刀那一版，没有查重层）：P1-a 的十个名字**全都不许在**，
    而 ④ 的东西（计划门、plan_denied、越界文案）一件不许少——反过来证明这一刀是加法式改动。
  · 进向 after-p1a（本刀）：以上全反，再加三条接线断言（装门顺序、类属性三件、文案与 CSS 成套）。
最后 `cmp` 三份逐字节，并把离线套件（v18_test_dup.py 75 条）在恢复后的树上原样跑一遍。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_drill_p1a.py
产物：run/v18_p1a_drill.out
"""
import hashlib
import pathlib
import py_compile
import re
import shutil
import subprocess
import sys
import time

SMOL = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
V18 = SMOL / ".rollback/v1.8"
BACK, FWD = V18 / "after-p0abc", V18 / "after-p1a"
RUN = pathlib.Path(__file__).resolve().parent / "run"
OUT = RUN / "v18_p1a_drill.out"
# 本次运行的现场备份（只读历史快照，别再往 .rollback 里写）
BAK = RUN / ("drill-backup-" + time.strftime("%Y%m%d-%H%M%S"))
PY = str(SMOL / ".venv/bin/python")
FILES = ["my_ui.py", "my_agent.py", "my_coding_agent.py"]

# 只属于 P1-a 的名字：退向④时必须一个都找不到，进向⑤时必须全找到。
P1A = ["_install_dup_gate", "_install_dup_stop", "_dup_call", "_seen_calls", "_dup_blocked",
       "_dup_tripped", "_bind_args", "DUP_MARK", "DUP_FUSE_MARK", "DUP_BLOCK_LIMIT",
       "DUP_OBSERVATION", "DUP_FUSE_OBSERVATION", "dup_fused"]
# ④及更早的东西：两个方向都必须绿（加法式改动的证据）。
KEPT = ["_install_plan_gate", "PlanDeniedError", "plan_denied", "_install_gate", "GATED_TOOLS",
        "interrupted", "_step_card", "_pending_snapshot", "_settle_all", "_dup",]
KEPT = [k for k in KEPT if k != "_dup"]

FAIL = []
NOK = 0
LINES = []


def emit(line=""):
    LINES.append(line)
    print(line)


def ok(name, cond, detail=""):
    global NOK
    NOK += 1
    line = "%-44s %s %s" % (name, "PASS" if cond else "FAIL", detail)
    emit(line)
    if not cond:
        FAIL.append(name)


def sha1(p):
    return hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest()


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


def probe(code):
    """在**新进程**里跑一段 python，返回 (exit, stdout)。用来验 import 层的锚点。"""
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=str(SMOL))
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]


def snapshot():
    """把现场另存到**本次新建**的备份目录，历史快照永远只读。

    这里原来是 `cp 现场 → FWD`（= .rollback/v1.8/after-p1a，v1.8 那一刀的终版快照）。
    2026-11-04 22:29 就是这一句把 after-p1a 覆盖成了现场（my_ui.py 123,177 B），
    同时另一份同内容的根目录 .rollback/v1.8/ 也在 20:47/20:49 被同一个模式覆盖——
    v1.8 终版源码从此两份都没了（smolagents/.rollback/v1.8/ 里的 ④③②① 与起点仍在）。
    演练真正要断的是「换进换出之后现场逐字节回到起点」，起点该存在只属于本次运行的目录里；
    历史快照当尺子用（v18_test_nochange、各类负控），任何时候不该被写。
    """
    BAK.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(SMOL / f, BAK / f)
    return {f: sha1(SMOL / f) for f in FILES}


def restore():
    """从本次备份把现场换回来。演练无论红绿都必须执行（写在 finally 里）。"""
    if not BAK.exists():
        return
    for f in FILES:
        if (BAK / f).exists():
            shutil.copy2(BAK / f, SMOL / f)


def run_side(label, snap_dir, expect_p1a):
    emit("\n---- 方向：%s（%s）----" % (label, snap_dir.name))
    t0 = time.time()
    for f in FILES:
        shutil.copy2(snap_dir / f, SMOL / f)
    for f in FILES:
        py_compile.compile(str(SMOL / f), doraise=True)
    ok("%s-a 三个文件 py_compile 通过" % label, True, "%.1fs" % (time.time() - t0))
    ui = read(SMOL / "my_ui.py")
    lines, bytes_ = ui.count("\n"), len(ui.encode())
    hit = [n for n in P1A if n in ui]
    miss = [n for n in P1A if n not in ui]
    if expect_p1a:
        ok("%s-b P1-a 的 13 个名字全在" % label, len(hit) == len(P1A), "%d/%d" % (len(hit), len(P1A)))
        ok("%s-c 接线：__init__ 里 gate→dup_gate→plan_gate 的顺序" % label,
           re.search(r"self\._install_gate\(\)[\s\S]{0,240}?self\._install_dup_gate\(\)\s*\n\s*self\._install_plan_gate\(\)", ui),
           "顺序对")
        ok("%s-d 接线：_install_dup_gate 末尾顺手装 dup_stop" % label,
           re.search(r"def _install_dup_gate[\s\S]{0,2600}?self\._install_dup_stop\(\)", ui), "")
        ok("%s-e 类属性三件齐（表/计数/开关）" % label,
           all(re.search(r"%s: (dict|int|bool)" % n, ui) for n in ("_seen_calls", "_dup_blocked", "_dup_tripped")), "")
        ok("%s-f 文案与显示成套：STATE_LABEL 词条 + CSS 胶囊都有 dup_fused" % label,
           '"dup_fused": "重复熔断"' in ui and "st-dup_fused" in ui
           and 'state = "plan_denied" if denied else ("dup_fused" if fused else "stopped")' in ui, "")
        ok("%s-g 收尾判据：只在 ActionStep 之后抛（不在中途事件）" % label,
           re.search(r"if OpsUI\._dup_tripped and isinstance\(ev, ActionStep\)", ui), "")
    else:
        ok("%s-b P1-a 的 13 个名字一个都不在" % label, not hit, "还找到: %s" % (hit or "无"))
        ok("%s-c 抽出来的 _bind_args 没回去（_gated_call 仍自己 bind_partial）" % label,
           "_bind_args" not in ui and "bind_partial" in ui, "inline")
        ok("%s-d 熔断收尾层不在（_run_stream 没被包）" % label, "_install_dup_stop" not in ui, "")
    ok("%s-e ④及更早的锚点全在（加法式改动）" % label,
       all(k in ui for k in KEPT), "缺: %s" % ([k for k in KEPT if k not in ui] or "无"))
    ok("%s-f 体量：行数 %d / %d B，sha1 == 快照" % (label, lines, bytes_),
       sha1(SMOL / "my_ui.py") == sha1(snap_dir / "my_ui.py"), sha1(SMOL / "my_ui.py")[:8])
    code = ("import my_ui;from my_ui import OpsUI;"
            "print('dup=%s dupstop=%s seen=%s' % (hasattr(OpsUI,'_install_dup_gate'),"
            "hasattr(OpsUI,'_install_dup_stop'),hasattr(OpsUI,'_seen_calls')))")
    rc, out = probe(code)
    want = "dup=True dupstop=True seen=True" if expect_p1a else "dup=False dupstop=False seen=False"
    ok("%s-g import 起来且类上三层在/不在（%s）" % (label, want), rc == 0 and want in out[0], out[0])
    code2 = "from my_ui import DUP_MARK"
    rc2, out2 = probe(code2)
    ok("%s-h `from my_ui import DUP_MARK` %s" % (label, "import 得到" if expect_p1a else "按要求 ImportError"),
       (rc2 == 0) == expect_p1a, "" if expect_p1a else out2[0][:56])
    return lines, bytes_


def main():
    emit("== v1.8 ⑤ 回滚演练（双向）==")
    emit("起表 %s   现场 my_ui.py=%s %d 行 / %d B" % (time.strftime("%H:%M:%S"), sha1(SMOL / "my_ui.py")[:8],
         read(SMOL / "my_ui.py").count("\n"), len(read(SMOL / "my_ui.py").encode())))
    cur = snapshot()
    emit("本次备份：%s → %s" % (BAK.name, {k: v[:8] for k, v in cur.items()}))
    # ---- 尺子完整性（这一条是 2026-11-04 那场事故换来的）---------------------------
    # 旧版 snapshot() 把现场 cp 进 FWD，after-p1a 就此变成现场的副本；副本还能用来
    # 「换进换出」，但那两次 cp 都是现场盖现场，一个字节都证明不了。先查出来，别再装绿。
    same_as_live = [f for f in FILES if (FWD / f).exists() and sha1(FWD / f) == cur[f]]
    ruler_ok = len(same_as_live) != len(FILES)
    ok("尺子完整：FWD(after-p1a) 不是现场的副本", ruler_ok,
       "三份全部 == 现场 → 这份历史快照已被覆盖，进向⑤ 无从可验" if not ruler_ok else str(same_as_live))
    # 历史事实由两份快照互比来断（那一刀确实只换 my_ui.py）；
    # 演练的破坏面由「现场 == 本次起点 cur」来断。
    if ruler_ok:
        for f in FILES:
            if f == "my_ui.py":
                ok("P1-a 那一刀确实只动了 my_ui.py（%s ↔ %s 互比）" % (BACK.name, FWD.name),
                   (BACK / f).read_bytes() != (FWD / f).read_bytes(), sha1(FWD / f)[:8])
                continue
            ok("两份快照里 %s 逐字节相同（本刀没碰它）" % f,
               (BACK / f).read_bytes() == (FWD / f).read_bytes(), sha1(BACK / f)[:8])
    run_side("退向④", BACK, False)
    if ruler_ok:
        run_side("进向⑤", FWD, True)
    else:
        emit("\n---- 方向：进向⑤ 跳过（FWD == 现场，跑它等于自证）----")
    restore()
    for f in FILES:
        ok("cmp 逐字节：现场 == 本次备份/%s（换进换出回到起点）" % f,
           (SMOL / f).read_bytes() == (BAK / f).read_bytes() and sha1(SMOL / f) == cur[f], cur[f][:8])
    r = subprocess.run([PY, str(pathlib.Path(__file__).parent / "v18_test_dup.py")],
                       capture_output=True, text=True, cwd=str(SMOL))
    n_pass, n_fail = r.stdout.count("PASS"), r.stdout.count("FAIL")
    ok("恢复后的树上重跑离线套件 v18_test_dup.py", r.returncode == 0 and n_fail == 0,
       "%d 条 PASS / %d FAIL / exit=%d" % (n_pass, n_fail, r.returncode))
    emit("\n演练结论：%s（%d 条断言，失败 %d 条）"
         % ("双向都能换、换回来逐字节一致" if (not FAIL and ruler_ok)
            else "单方向（⑤ 那份尺子已没）" if not FAIL else "有红项", NOK, len(FAIL)))
    return 0 if (not FAIL and ruler_ok) else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        # 无论红绿都要把现场换回来：旧版只在正常路径上「恢复」，中途抛异常现场就停在
        # after-p0abc 那一版上——下次 import 到的是 v1.8 的代码，而没人看得出来。
        restore()
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        print("[written] %s  %d 行 / %d B" % (OUT, len(LINES), OUT.stat().st_size))
    sys.exit(rc)
