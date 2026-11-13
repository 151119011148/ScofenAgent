# -*- coding: utf-8 -*-
"""文档闸的**共用判据层**（v2.0）：把文档里的行号锚点逐条挑出来，并决定它归哪把尺子。

点扫（`v20_gate_scan.py`）与终点扫（`v20_gate_scan3.py`）必须用**同一套归属口径**，
否则一边说「这条不算我的检查范围」、另一边把它判红，两道闸互相打脸。
判据本体照抄 `验收脚本/v1.8/v18_gate_anchors.py`，**只换尺子、只加断言**，不改判据。

这一版相对 v1.8 的五处变化（每一处都是现实逼出来的）：
  1. **尺子换成五份**：`.rollback/v2.0-现场-20261113/`（`my_ui.py` 2,315／`my_coding_agent.py` 325／
     `my_agent.py` 156／`my_mcp.py` 186／`my_audit.py` 128）。v2.0 新增的两份文件也必须进尺子，
     否则 `my_mcp.py:45-60` 一类锚点会被当成「归外部」整条跳过——闸看着绿，其实没扫。
  2. **开扫前先校 sha1**（`SHA1SUMS.txt`）。v1.8 那把 1,758 行的尺子被演练脚本自己覆盖掉、
     且**不可恢复**（`v18_drill_v18.py:230-233`，见 README 文首第 6 行）。所以这一版把
     「尺子还是不是它自称的那一版」变成**硬前置**：对不上就 exit 2，一个号都不扫。
     五份快照全 `chmod a-w`，但只读位挡不住 `cp` 覆盖，挡得住的是这道校验。
  3. **历史号标记扩到 v1.9**（`HIST_TAG` 从 `v1\\.[0-7]` 改成 `v1\\.[0-9]`）：v1.8／v1.9 现在都是历史。
  4. **范围按「讲现状的节」逐段点名**（`TARGETS`），不再是一整段连号。README 的 §6.3.2~§6.3.10
     与 §9.4 第 1~21 条讲的是**当时那一版**的位置，拿 v2.0 的尺子去量必然全红，那不是缺陷是口径。
  5. **六份文档全纳入**：README、手册、迭代记录、链路图、链路详解、实现原理。后三份是 v2.0 新加的
     （用户点名的那几份），行号口径都是现状，所以整份参与；HTML 的 `<style>`/`<script>` 由
     `_html_skip()` 摘掉，否则 CSS 的 `flex:1` 会被当成行号。**唯一的已知覆盖缺口是手册 §4 看板**：
     那 56 个锚点是**混口径**的——已修工单引的是它修好那一版的号（`my_ui.py:34` 的 `GATED_TOOLS`
     现在是 `:42`），新立工单引的是现状号。把整张看板纳入需要「按行判它属于哪一版」的归属规则，
     本轮**没做**，写在 README §9.3 第 16) 条与手册 §7，不当成「手册全扫过」引用。

`GATE_SKIP` 本轮为空：闸的读数只落 `run/*.out`，往 `迭代记录.md`／手册里写的是**不含行号锚点**的
一句话结论。这是刻意的——v1.7 实测过「每加一行闸记录、计数自己涨一次」（258→260）。
将来若要把逐条读数写进文档，那几行必须同时登记进 `GATE_SKIP`。

跑法：这一份不单独运行，由 `v20_gate_scan.py` / `v20_gate_scan3.py` import。
"""
import hashlib
import io
import os
import re
import sys

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
SNAP = os.path.join(ROOT, u".rollback", u"v2.0-现场-20261113")
CURRENT = u"v2.0"

FILES = {
    u"my_ui.py": os.path.join(SNAP, "my_ui.py"),
    u"my_coding_agent.py": os.path.join(SNAP, "my_coding_agent.py"),
    u"my_agent.py": os.path.join(SNAP, "my_agent.py"),
    u"my_mcp.py": os.path.join(SNAP, "my_mcp.py"),
    u"my_audit.py": os.path.join(SNAP, "my_audit.py"),
}


def _check_ruler():
    """尺子的 sha1 必须与清单逐份相符；对不上就停，别拿一把不知道是哪版的尺子去判红。"""
    man = os.path.join(SNAP, "SHA1SUMS.txt")
    if not os.path.exists(man):
        print(u"尺子清单不在：%s —— 无法确认尺子版本，停。" % man)
        raise SystemExit(2)
    want = {}
    for line in io.open(man, encoding="utf-8").read().splitlines():
        if line.strip():
            h, f = line.split()
            want[f] = h
    bad = []
    for k, path in FILES.items():
        if not os.path.exists(path):
            bad.append(u"%s 不在尺子目录里" % k)
            continue
        got = hashlib.sha1(io.open(path, "rb").read()).hexdigest()
        if want.get(k) != got:
            bad.append(u"%s sha1 %s ≠ 清单 %s" % (k, got[:8], (want.get(k) or u"缺")[:8]))
    if set(want) != set(FILES):
        bad.append(u"清单与尺子文件集合不一致：%s" % sorted(set(want) ^ set(FILES)))
    if bad:
        print(u"---- 尺子校验失败（P2-21：v1.8 那把尺子就是这么丢的）----")
        for b in bad:
            print(u"  " + b)
        raise SystemExit(2)
    return want


MANIFEST = _check_ruler()
SRC = {k: io.open(v, encoding=u"utf-8").read().splitlines() for k, v in FILES.items()}

# README 2,050 行那一版；手册 1,855 行；迭代记录 1,390 行。范围＝「讲现状的节」。
TARGETS = {
    u"README": (os.path.join(ROOT, "README.md"),
                [(13, 101),        # §1 全局链路（含两张 mermaid）
                 (620, 711),       # §6.1 / §6.2 / §6.3 标题 / §6.3.1
                 (1084, 1289),     # §6.3.11 v1.9 ＋ §6.3.12 v2.0
                 (1290, 1809),     # §7 跨仓视角 ＋ §8 BDD 现状场景
                 (1812, 1883),     # §9.1 关键代码位置总表（66 行）
                 (1899, 2022),     # §9.3 复现命令
                 (2048, 2063)]),   # §9.4 第 22~27 条（v1.9/v2.0 新立）＋ §9.5
    u"手册": (os.path.join(ROOT, u"agent功能手册.html"),
              [(96, 333)]),        # §1 怎么用 ＋ §2 现状能力面（v2.0）
    u"迭代记录": (os.path.join(ROOT, u"迭代记录.md"),
                 [(13, 334)]),     # v2.0 ＋ v1.9 两节（它们的 my_ui.py 就是现在这把尺子）
    # v2.0 新纳入的三份（用户点名的「链路图／链路详解／实现原理」）。它们的行号口径都是**现状**，
    # 所以整份参与；HTML 里的 <style>/<script> 由 _html_skip() 摘掉——CSS 的 `flex:1`、
    # `grid-template-columns:1fr` 会被 NUM 当成行号，不摘就是一片假红。
    u"链路图": (os.path.join(ROOT, u"agent链路图.html"), [(1, 328)]),
    u"链路详解": (os.path.join(ROOT, u"agent链路详解.html"), [(1, 839)]),
    u"实现原理": (os.path.join(ROOT, u"agent实现原理-一次问话全流程-面试剖析对照.md"),
                 [(1, 769)]),
}
GATE_SKIP = {}


def _html_skip(lines):
    """HTML 里 <style>…</style> 与 <script>…</script> 占的行号集合（含标签本身那两行）。"""
    skip = set()
    open_at = None
    for i, line in enumerate(lines, 1):
        low = line.lower()
        if open_at is None:
            for tag in ("<style", "<script"):
                if tag in low:
                    open_at = i
                    break
        if open_at is not None:
            skip.add(i)
            if "</style>" in low or "</script>" in low:
                open_at = None
    return skip

OTHERS = [u"agents.py", u"gradio_ui.py", u"tools.py", u"memory.py", u"monitoring.py",
          u"utils.py", u"local_python_executor.py", u"model.py", u"agent_ops",
          u"python_interpreter.py", u"chat_interface.py", u"types.py", u"app.py",
          u"docker-compose.yaml", u"workflow_entry.py", u"node_factory.py",
          u"app_dsl_service.py", u"local_py_scripts.py", u"path-validation.ts",
          u"index.ts", u"server.ts", u"chatbot.py", u"ujson",
          u"关闭Agent.command", u".zshrc", u"launcher", u"smolagents.py",
          # v2.0 新增：尺子与演练脚本自己的行号不是被扫对象
          u"v18_drill_v18.py", u"v18_gate_anchors.py", u"v20_eval.py", u"v20_questions.py",
          u"v20_gate_anchors.py", u"v20_test_d3_audit.py", u"models.py"]

# 号只吃「数字 + 到下一个数字的连接符」：`-`、`–`、半角 `,`。写成 [\d,，、\-–\s]+ 是错的——
# 中文顿号/逗号/空格也在类里，于是「`my_ui.py:1751-1752`，v1.1 起…」把后面不相干的 70、72 吞进同一个锚点。
NUM = re.compile(r"(my_ui\.py|my_coding_agent\.py|my_agent\.py|my_mcp\.py|my_audit\.py)?\s*:(\d+(?:[-–,]\d+)*)")
NUMS = re.compile(r"\d+")
PORTY = re.compile(r"[0-9A-Za-z._\-/]+$")          # 端口/URL 的冒号
HIST_TAG = re.compile(r"v1\.[0-9]\b")              # 别一版的叙述（v2.0 起含 v1.8／v1.9）
HIST_PATH = u".rollback/v"
WIN_FILE = 160                                      # 就近归属窗口
WIN_HIST = 40                                       # 历史号标记窗口


def _nearest_file(win):
    best, bestp = None, -1
    for cand in list(FILES) + OTHERS:
        p = win.rfind(cand)
        if p > bestp:
            best, bestp = cand, p
    return best


def anchors(name):
    """按文档名产出锚点。每项是一个 dict：ln/kind/nums/raw/hist/explicit/cands。"""
    path, ranges = TARGETS[name]
    lines = io.open(path, encoding=u"utf-8").read().splitlines()
    skip = _html_skip(lines) if path.endswith(".html") else set()
    out = []
    for ln in range(1, len(lines) + 1):
        if ln in skip:
            continue
        if not any(a <= ln <= b for a, b in ranges):
            continue
        if any(a <= ln <= b for a, b in GATE_SKIP.get(name, [])):
            continue
        line = lines[ln - 1]
        for m in NUM.finditer(line):
            explicit = m.group(1)
            colon = m.start(2) - 1
            win = line[max(0, colon - WIN_FILE):colon]
            if explicit is None and PORTY.search(win):
                out.append({"ln": ln, "kind": u"端口", "raw": m.group(0), "nums": []})
                continue
            target = explicit
            if target is None:
                near = _nearest_file(win)
                if near is None or near in OTHERS:
                    out.append({"ln": ln, "kind": u"归外部", "raw": m.group(0),
                                "nums": [], "file": near})
                    continue
                target = near
            nums = [int(x) for x in NUMS.findall(m.group(2)) if int(x)]
            if not nums:
                continue
            hwin = line[max(0, colon - WIN_HIST):colon]
            hist = HIST_PATH in hwin or (explicit is None and HIST_TAG.search(hwin) is not None)
            # bare 号的归属会挑错尺子（链式写法 `X:108 / :163` 撞上句中另提一个文件名），
            # 所以给一个兜底候选：my_ui.py 说得通就算通过，只打「歧义」计数。
            cands = [target] if (explicit or target == u"my_ui.py") else [target, u"my_ui.py"]
            out.append({"ln": ln, "kind": u"锚点", "raw": m.group(0), "nums": nums,
                        "target": target, "hist": hist, "explicit": bool(explicit),
                        "cands": cands, "text": line.strip()[:80]})
    return out


def valid(target, k):
    """这条号在这把尺子上指到非空行吗。"""
    src = SRC[target]
    return k <= len(src) and bool(src[k - 1].strip())


def oob(target, k):
    return k > len(SRC[target])


DEF = re.compile(r"^(?P<ind>[ \t]*)(?:async\s+)?(?:def|class)\s+\w")
HEAD = re.compile(u"(async )?def |^class ")
_SPANS = {}


def end_kind(ruler, y):
    """终点这一行是不是「已经越过本节、踩进下一节了」。不是就返回 None。

    「注释续行」豁免沿用 v1.8：引一整段注释时终点是那段的**最后一行**（前一行也是 `#`），
    不是新段的开场。`#----` 分隔线不看前一行（它本身就是边界）。
    """
    src = SRC[ruler]
    line = src[y - 1]
    s = line.strip()
    if not s:
        return u"空行"
    if HEAD.match(s):
        return u"下一个 def/class"
    if u"----" in s and s.startswith(u"#"):
        return u"下一节的分隔注释"
    if s.startswith(u"# ") and line.startswith(u"#"):
        if y >= 2 and src[y - 2].strip().startswith(u"#"):
            return None
        return u"下一节的开场注释"
    return None


def span(ruler):
    """每个 def/class 的真实跨度：{起始行: (缩进, 末行)}。

    这张表是**「插进一个新函数、把前一个函数的 `:X-Y` 截短」**唯一的抓法——
    end_kind 那四档看不见它，因为越过去的终点是新函数正文里的一个非空行。
    v2.0 这一轮尤其需要它：`my_coding_agent.py` 从 256 长到 325 行，
    五只手的 def 全体下移，任何一条没跟着搬的区间都会在这里露出来。
    """
    if ruler in _SPANS:
        return _SPANS[ruler]
    src = SRC[ruler]
    ext = {}
    for i, line in enumerate(src, 1):
        m = DEF.match(line)
        if not m:
            continue
        ind = len(m.group("ind"))
        last = i
        j = i + 1
        while j <= len(src):
            s = src[j - 1]
            t = s.strip()
            if t:
                sind = len(s) - len(s.lstrip())
                if sind <= ind and (DEF.match(s) or t.startswith(u"@")):
                    break
                if sind == ind and t.startswith(u"#"):
                    break
                last = j
            j += 1
        ext[i] = (ind, last)
    _SPANS[ruler] = ext
    return ext


if __name__ == "__main__":
    print(u"尺子 %s（%s）sha1 校验通过：" % (CURRENT, SNAP))
    for k in sorted(FILES):
        print(u"  %-20s %4d 行  %s" % (k, len(SRC[k]), MANIFEST[k][:8]))
    for name in TARGETS:
        print(u"  %-8s 范围 %s → 锚点 %d 条" % (name, TARGETS[name][1], len(anchors(name))))