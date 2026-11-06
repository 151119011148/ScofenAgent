# -*- coding: utf-8 -*-
"""README 里所有指向 my_ui.py 的行号，按 v1.6（1,205 行）重新对齐并给出提案表。

判定「这条引用指的是哪一处」用的是标识符/实体重叠，不是跨度自相似：
README 那句话里通常会点名一个 def / 类名 / 关键变量（`_respond`、`demo.load`、
`DELETE`），拿它去和候选行所在的代码块对撞。块只对 def/class 展开（多行赋值如
DARK_CSS 用展开会把整段吞进来，之前踩过），模块级赋值直接沿用逐行映射的落点。

输出：每条 = README 行号、旧串、谁的文件、时代、提案新串、命中的代码、重叠分。
不落盘。人工过完这张表再手写 (旧, 新) 配对清单（沿用 v1.5 那套一次性命中的做法）。
"""
import difflib
import json
import pathlib
import re

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
MD = ROOT / "README.md"
V14 = (ROOT / ".rollback/v1.4/my_ui.py").read_text(encoding="utf-8").splitlines()
V15 = (ROOT / ".rollback/v1.5/my_ui.py").read_text(encoding="utf-8").splitlines()
V16 = (ROOT / "smolagents/my_ui.py").read_text(encoding="utf-8").splitlines()
M14 = {int(k): v for k, v in json.load(open("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_map14.json")).items()}
M15 = {int(k): v for k, v in json.load(open("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_map15.json")).items()}

# 其它文件的行号：不属本轮对齐范围
OTHER = ("agents.py", "gradio_ui.py", "utils.py", "local_python_executor.py",
         "my_coding_agent.py", "my_agent.py", "memory.py", "tools.py", "huggingface_hub",
         "model.py", "monitor.py", "types.py", "python_interpreter.py")

ENAMES = re.compile(r"[A-Za-z_][A-Za-z_0-9]{2,}")
STOP = set("""def class return self None True False int str list dict float bool import from
with while return yield raise except try if elif else for in and or not is as pass assert
gradio python async await lambda global local""".split())


def blocks(lines):
    """行号 -> 该 def/class 的跨度（含装饰器行下方到下一个同/更浅缩进结束）。"""
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
        # 去掉尾部空行
        while end > i and not lines[end - 1].strip():
            end -= 1
        j = i
        while j <= end:
            span[j] = (i, end, name)
            j += 1
    return span


B14, B15, B16 = blocks(V14), blocks(V15), blocks(V16)


def block_of(lines, span, n):
    s = span.get(n)
    if s:
        return lines[s[0] - 1:s[1]]
    return [lines[n - 1]] if n <= len(lines) else []


def ctx_tokens(text):
    return {t for t in ENAMES.findall(text) if t not in STOP and not t.isdigit()}


def ref_sites(txt):
    """返回 [(readme_line_no, col, raw, a, b, who)]；who=='my_ui' 才进本轮范围。

    归属判定：往回看 160 个字符，最后一次点名的文件名就是这个 ref 的文件；没点名
    就默认 my_ui（本轮那些表格/散文都在讲 my_ui）。历史引用（「v1.1 前在 :70-72」）
    标 HIST，不改。
    """
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
            out.append((ln, a, raw, int(nums[0]), int(nums[-1]), "HIST" if hist else "cur"))
    return out


def score(readme_line, a, b, era):
    """把 era 里的 [a,b] 映到 v1.6，返回 (new_a, new_b, overlap, code_sample)"""
    M, L, B = (M14, V14, B14) if era == 14 else (M15, V15, B15)
    na = M.get(a)
    nb = M.get(b)
    if na is None or nb is None:
        return None
    na, nb = min(na, nb), max(na, nb)
    while nb > na and not V16[nb - 1].strip():
        nb -= 1
    while na < nb and not V16[na - 1].strip():
        na += 1
    code = "\n".join(block_of(L, B, a))
    tgt = "\n".join(block_of(V16, B16, na))
    # 用 README 行里点名的实体去撞
    ents = ctx_tokens(readme_line)
    src_hit = len(ents & ctx_tokens(code))
    tgt_hit = len(ents & ctx_tokens(tgt))
    return na, nb, (src_hit, tgt_hit), tgt[:100].replace("\n", " ⏎ ")


def key(c):
    era, (na, nb, (sh, th), _) = c
    return (sh, th)


# 只有这些区段在讲 my_ui.py，别处的 :NNN 属于别的仓库/别的文件，一律不碰
SECTIONS = [(54, 80), (625, 911), (1147, 1197)]


def main():
    txt = MD.read_text(encoding="utf-8")
    lines = txt.splitlines()
    rows = []
    for ln, col, raw, a, b, kind in ref_sites(txt):
        if not any(x <= ln <= y for x, y in SECTIONS):
            continue
        rl = lines[ln - 1]
        if kind == "HIST":
            rows.append((ln, raw, kind, "skip", "", "", rl[max(0, col - 46):col + 30]))
            continue
        s14 = score(rl, a, b, 14)
        s15 = score(rl, a, b, 15)
        cands = sorted([(era, s) for era, s in ((14, s14), (15, s15)) if s],
                       key=key, reverse=True)
        if not cands:
            rows.append((ln, raw, kind, "NO-MAP", "", "", rl[max(0, col - 46):col + 30]))
            continue
        best_era, best = cands[0]
        kb = key(cands[0])
        ka = key(cands[1]) if len(cands) > 1 else (-1, -1)
        status = "TIE" if (kb == ka and kb != (0, 0)) else ("HIT" if kb != (0, 0) else "ZERO")
        na, nb = best[0], best[1]
        rows.append((ln, raw, kind, status, ":%d-%d" % (na, nb) if nb > na else ":%d" % na,
                     "[v%d ov=%s] src=\u2316%s\u2316 tgt=\u2316%s\u2316 %s\u2316%s" % (
                         best_era, kb, (V14 if best_era == 14 else V15)[a - 1].strip()[:60],
                         (V14 if best_era == 14 else V15)[b - 1].strip()[:60],
                         V16[na - 1].strip()[:60], V16[nb - 1].strip()[:60]),
                     rl[max(0, col - 46):col + 30]))
    from collections import Counter
    print("候选 %d 条" % len(rows), dict(Counter(r[3] for r in rows)))
    for r in rows:
        print("%4d %-6s %-18s -> %-14s %-6s %s" % (r[0], r[3], r[1], r[4], r[2], r[5]))
        print("        ctx \u2016%s\u2016" % r[6])


main()
