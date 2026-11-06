# -*- coding: utf-8 -*-
"""文档闸的**共用判据层**（v1.8）：把三份文档里的行号锚点逐条挑出来，并决定它归哪把尺子。

点扫（`v18_gate_scan.py`）与终点扫（`v18_gate_scan3.py`）必须用**同一套归属口径**，
否则一边说「这条不算我的检查范围」、另一边把它判红，两道闸互相打脸。
v1.7 那轮这两份是各写各的正则，这轮合并成一个模块。

口径（四条，都是这一轮的现实逼出来的）：
  1. **尺子 = `.rollback/v1.8/` 的三份快照**（`my_ui.py` 1,758／`my_coding_agent.py` 256／`my_agent.py` 111）。
     现场 `smolagents/my_ui.py` 是 **1,910 行**（另一个会话那 152 行「侧栏删除会话」没归档），
     拿它当尺子会把正确的号判成越界。README 文首第 5 行写的就是这个口径。
  2. **只扫「讲现状」的范围**（`TARGETS`）；§6.x 记录节讲的是当时那一版的位置，不参与。
     追加文档闸那几行填进 `GATE_SKIP`，闸行不参与计数。
  3. **就近归属**：显式写了文件名就用它；bare 号在前面 160 字符里找最后出现的那个文件——
     三把尺子和上游/外部文件（`agents.py`、`tools.py`…）一起比位置，外部文件胜出就整条跳过
     （本轮没有为上游建尺子）。跳过的条数照打，不藏。
  4. **两类冒号不是行号**：
     - 端口/URL：bare 匹配且冒号左边紧挨数字/字母/点号（`127.0.0.1:7860`、`-iTCP:7860`）。
       这一条是 v1.8 第一遍报出 6 条假越界之后加的。
     - 历史号：`.rollback/v…` 点名的别版快照，或 bare 号左 40 字符里标着 `v1.0`~`v1.7`。
       刻意**不豁免**「`my_ui.py:NNN` 前面顺带写一句 v1.3 引入」——那是现行锚点
       （README §9.1 第 30、36 行就是这种，宽松版把它们放过过，已收紧）。
"""
import io
import os
import re

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
SNAP = os.path.join(ROOT, u".rollback", "v1.8")
CURRENT = u"v1.8"

FILES = {
    u"my_ui.py": os.path.join(SNAP, "my_ui.py"),
    u"my_coding_agent.py": os.path.join(SNAP, "my_coding_agent.py"),
    u"my_agent.py": os.path.join(SNAP, "my_agent.py"),
}
SRC = {k: io.open(v, encoding=u"utf-8").read().splitlines() for k, v in FILES.items()}

TARGETS = {
    u"README": (os.path.join(ROOT, "README.md"),
                [(55, 90), (599, 653), (1007, 1023), (1096, 1359), (1362, 1525)]),
    u"手册": (os.path.join(ROOT, u"agent功能手册.html"),
              [(96, 710)]),
    u"迭代记录": (os.path.join(ROOT, u"迭代记录.md"),
                 [(1, 233)]),
}
# 本轮「五道文档闸」那几张表：它们自己引用的就是被纠正的旧号（`:830-883`、`:163-263`…），
# 算进去就会每加一行闸记录、计数自己涨一次（v1.7 实测 258→260）。不参与，见模块开头第 2 条。
GATE_SKIP = {u"迭代记录": [(179, 191)], u"手册": [(675, 678)]}

OTHERS = [u"agents.py", u"gradio_ui.py", u"tools.py", u"memory.py", u"monitoring.py",
          u"utils.py", u"local_python_executor.py", u"model.py", u"agent_ops",
          u"python_interpreter.py", u"chat_interface.py", u"types.py", u"app.py",
          u"docker-compose.yaml", u"workflow_entry.py", u"node_factory.py",
          u"app_dsl_service.py", u"local_py_scripts.py", u"path-validation.ts",
          u"index.ts", u"server.ts", u"chatbot.py", u"ujson",
          u"关闭Agent.command", u".zshrc", u"launcher", u"smolagents.py"]

# 号只吃「数字 + 到下一个数字的连接符」：`-`、`–`、半角 `,`。写成 [\d,，、\-–\s]+ 是错的——
# 中文顿号/逗号/空格也在类里，于是「`my_ui.py:1751-1752`，v1.1 起…」把后面不相干的 70、72 吞进同一个锚点。
NUM = re.compile(r"(my_ui\.py|my_coding_agent\.py|my_agent\.py)?\s*:(\d+(?:[-–,]\d+)*)")
NUMS = re.compile(r"\d+")
PORTY = re.compile(r"[0-9A-Za-z._\-/]+$")          # 端口/URL 的冒号
HIST_TAG = re.compile(r"v1\.[0-7]\b")              # 别一版的叙述
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
    """按文档名产出锚点。每项是一个 dict：ln/target/nums/raw/hist/explicit/ambig_cands。"""
    path, ranges = TARGETS[name]
    lines = io.open(path, encoding=u"utf-8").read().splitlines()
    out = []
    for ln in range(1, len(lines) + 1):
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

    v1.7 那份把「顶格 `# `」一律当下一节开场，本轮三次误报都在这里：
    `my_coding_agent.py:32-36` 与 `my_agent.py:15-29` 引的是**一整段注释**，
    终点是那段注释的**最后一行**（前一行也是 `#`），不是新段的开场。
    所以补一条：前一行还是注释 → 这是续行，放行。`#----` 分隔线不看前一行（它本身就是边界）。
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

    走法沿用记录里那条口径：从 def 行按缩进往下走到「同级或更浅的 def/class/装饰器/注释」，
    末尾空行不记。这张表是**「本轮插进一个新函数、把前一个函数的 `:X-Y` 截短」**唯一的抓法——
    kind 那四档看不见它，因为越过去的终点是新函数正文里的一个非空行
    （v1.7 的实例：`_bind_memory` 写成 `:961-1006`，实到 `:961-986`；
     v1.8 这轮抓到 3 条 7 处：`:830-883`／`:163-263`／`:468-479`，全是两个函数并成一条区间）。
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
