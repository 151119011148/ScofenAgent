# -*- coding: utf-8 -*-
"""README 里指向 my_ui.py 的行号：v1.6(1,205) -> v1.7(1,253) 重新对齐，只出提案表，不落盘。

判定「这条引用指哪一处」沿用 v1.6 那一套：拿 README 这句话点名的标识符/实体去撞
v1.6 那一行的代码块与 v1.7 目标块，撞得上的优先。本轮只有一代映射（v1.6 那批号是
上一轮刚对齐过的），所以没有 era 竞争。

输出：README 行号、旧串、命中的 v1.7 新串、状态、撞上的代码、上下文。
"""
import difflib
import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
MD = ROOT / "README.md"
V16 = (ROOT / ".rollback/v1.6/my_ui.py").read_text(encoding="utf-8").splitlines()
V17 = (ROOT / "smolagents/my_ui.py").read_text(encoding="utf-8").splitlines()
M16 = {int(k): v for k, v in json.load(open("/tmp/v17_map16.json")).items()}

OTHER = ("agents.py", "gradio_ui.py", "utils.py", "local_python_executor.py",
         "my_coding_agent.py", "my_agent.py", "memory.py", "tools.py", "huggingface_hub",
         "model.py", "monitor.py", "types.py", "python_interpreter.py",
         "chat_interface.py", "chatbot.py", "docker-compose.yaml", "launcher",
         "DefaultAiServices.java", "ToolSpecifications.java",
         "DefaultRetrievalAugmentor.java", "workflow_entry.py", "node_factory.py",
         "app_dsl_service.py", "path-validation.ts", "index.ts", "local_py_scripts.py")

ENAMES = re.compile(r"[A-Za-z_][A-Za-z_0-9]{2,}")
STOP = set("""def class return self None True False int str list dict float bool import from
with while yield raise except try elif else for and or not is as pass assert
gradio python async await lambda global local""".split())

# 本轮 README 里哪些区段在讲 my_ui.py（其余 :NNN 属于别的文件/别处叙述）
SECTIONS = [(633, 939), (1012, 1220), (1223, 1275), (1291, 1329)]


def blocks(lines):
    span = {}
    starts = []
    for i, ln in enumerate(lines, 1):
        m = re.match(r"(\s*)(?:def|class)\s+([A-Za-z_][\w]*)", ln)
        if m:
            starts.append((i, len(m.group(1)), m.group(2)))
    for idx, (i, ind, name) in enumerate(starts):
        end = len(lines)
        nxt = [s for s in starts[idx + 1:] if s[1] <= ind]
        if nxt:
            end = nxt[0][0] - 1
        while end > i and not lines[end - 1].strip():
            end -= 1
        j = i
        while j <= end:
            span[j] = (i, end, name)
            j += 1
    return span


B16, B17 = blocks(V16), blocks(V17)


def block_of(lines, span, n):
    s = span.get(n)
    if s:
        return lines[s[0] - 1:s[1]]
    return [lines[n - 1]] if n <= len(lines) else []


def ctx_tokens(text):
    return {t for t in ENAMES.findall(text) if t not in STOP and not t.isdigit()}


def ref_sites(txt):
    out = []
    for ln, line in enumerate(txt.splitlines(), 1):
        for m in re.finditer(r"(?<![\w.])((?:my_ui\.py)?:\d+(?:-\d+)?)", line):
            a = m.start()
            window = line[max(0, a - 160):a]
            last, lasti = None, -1
            for o in OTHER:
                p = window.rfind(o)
                if p > lasti:
                    last, lasti = o, p
            p = window.rfind("my_ui.py")
            if p > lasti or m.group(1).startswith("my_ui.py"):
                last = "my_ui"
            who = last or "my_ui"
            if who != "my_ui":
                continue
            hist = bool(re.search(r"(v1\.\d|更早|以前|原来)\D{0,12}$", window[-24:]))
            raw = m.group(1)
            nums = re.findall(r"\d+", raw)
            out.append((ln, a, raw, int(nums[0]), int(nums[-1]), "HIST" if hist else "cur", who))
    return out


def score(readme_line, a, b):
    na, nb = M16.get(a), M16.get(b)
    if na is None or nb is None:
        return None
    na, nb = min(na, nb), max(na, nb)
    while nb > na and not V17[nb - 1].strip():
        nb -= 1
    while na < nb and not V17[na - 1].strip():
        na += 1
    src = "\n".join(block_of(V16, B16, a))
    tgt = "\n".join(block_of(V17, B17, na))
    ents = ctx_tokens(readme_line)
    return na, nb, (len(ents & ctx_tokens(src)), len(ents & ctx_tokens(tgt)))


def main():
    txt = MD.read_text(encoding="utf-8")
    lines = txt.splitlines()
    rows = []
    changed = 0
    for ln, col, raw, a, b, kind, who in ref_sites(txt):
        if not any(x <= ln <= y for x, y in SECTIONS):
            continue
        rl = lines[ln - 1]
        if kind == "HIST":
            rows.append((ln, raw, kind, "skip", raw, "", rl[max(0, col - 46):col + 34]))
            continue
        s = score(rl, a, b)
        if s is None:
            rows.append((ln, raw, kind, "NO-MAP", raw, "", rl[max(0, col - 46):col + 34]))
            continue
        na, nb, ov = s
        new = ":%d-%d" % (na, nb) if nb > na else ":%d" % na
        status = "HIT" if ov != (0, 0) else "ZERO"
        if raw.split(":")[-1] != new.split(":")[-1]:
            status = ("MOVE-" if new != raw else "") + status
        rows.append((ln, raw, kind, status, new,
                     "[ov=%d/%d] \u2316%s\u2316 -> \u2316%s\u2316" % (
                         ov[0], ov[1], V16[a - 1].strip()[:52], V17[na - 1].strip()[:52]),
                     rl[max(0, col - 46):col + 34]))
        if new != raw:
            changed += 1
    print("候选 %d 条，其中号要动 %d 条" % (len(rows), changed),
          dict(Counter(r[3] for r in rows)))
    cur = None
    for r in rows:
        if r[0] != cur:
            print("--- L%d" % r[0])
            cur = r[0]
        print("   %-8s %-14s -> %-14s %-8s %s" % (r[3], r[1], r[4], r[2], r[5]))
        print("      ctx \u2016%s\u2016" % r[6])


main()
