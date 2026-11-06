# -*- coding: utf-8 -*-
"""把「讲现状」的范围（§1–§5 ＋ §7）里 my_ui.py 的行号从 v1.7（1,253）落到 v1.8（1,758）。

两个版本都读 .rollback 整版存档，不读现网 my_ui.py（现网那份已被并发会话改到 1,910 行）。
不带 --write 只出干跑清单；FORCE / SKIP 是人工过提案表的结果，理由写在那儿。
判定与 v1.7 的 v17_manual_align.py 同源，只换了版本、映射表与作用范围。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
MD = ROOT / "agent功能手册.html"
RUN = ROOT / "验收脚本/v1.8/run"

V17 = (ROOT / ".rollback/v1.7/my_ui.py").read_text(encoding="utf-8").splitlines()
V18 = (ROOT / ".rollback/v1.8/my_ui.py").read_text(encoding="utf-8").splitlines()
M17 = {int(k): v for k, v in json.load(open(str(RUN / "v18_map17.json"))).items()}

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
SECTIONS = [(95, 583), (1227, 1287)]

# 人工过提案表后的改判：(行号, 原串) -> 新串。理由逐条写在行尾。
FORCE = {
    (179, ":565-621"): ":670-730",      # 审批闸 def 段：_install_gate 670 / _gated_call 695 / _bind_args 718，732 起是查重闸
    (179, ":640-689"): ":966-1084",     # _approval_card 966 → _step_card 1085 之前；这一段的 v1.8 里多出 _plan_update/_last_plan
    (179, ":806-958"): ":1218-1396",    # _worker 1218 → _bind_memory 1399 之前（线程驱动＋流式渲染）
    (179, ":63-232"): ":94-263",        # 记忆编解码：MEM_FMT 94 → decode_memory 的 return steps 263
    (198, ":382-397"): ":463-478",      # Approval 里记等待那一刻（与 185 行同一处，HIT 已确认）
    (198, ":37-40"): ":40-43",          # APPROVAL_WAIT_MIN 门槛注释段
    (347, ":387-398"): ":468-479",      # Approval.decide
    (300, "my_ui.py:4"): "my_ui.py:15",  # from my_agent import agent 在 15；:4 是 import inspect（v1.7 就带错的号）
    (194, ":1137-1160"): ":1614-1638",  # _select_session；窗口里先点过 gradio_ui.py 才被判成别的文件
}
# 刻意不动：历史叙述 / 别的文件的行号
SKIP = {
    (316, "my_ui.py:289-291"),   # 句中写明「旧 my_ui.py:289-291」＝v1.2 时代的位置
    (341, "my_ui.py:306-323"),   # 「v1.2 追加两笔：搬到 :306-323」＝带版本标签的历史链
    (341, ":374"),               # 同上（v1.2 自建停止键）
    (341, "my_ui.py:750-763"),   # 「v1.3 追加第三笔」＝带版本标签的历史链
    (347, ":405-428"),           # 句中写明「v1.4 行号」
    (358, "my_ui.py:648-653"),   # 同上：v1.4 行号（这一行本轮会被整体改写，先按要求钉住）
    (462, ":53-172"),            # 「v1.2 时是 :53-172」
    (474, "my_ui.py:450-500"),   # 「v1.2 的写法」
    (287, ":178"),               # 讲的是 my_coding_agent.py，本轮单独对（v1.8 量到 :207）
    (1233, ":198"),              # 讲的是 my_coding_agent.py v1.0 那版的位置
    (417, ":910"),               # 讲的是上游 tools.py 的 from_hub
    (164, ":910"),               # 同上
}


def blocks(lines):
    span, starts = {}, []
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
        for j in range(i, end + 1):
            span[j] = (i, end, name)
    return span


B17, B18 = blocks(V17), blocks(V18)


def block_of(lines, span, n):
    s = span.get(n)
    if s:
        return lines[s[0] - 1:s[1]]
    return [lines[n - 1]] if n <= len(lines) else []


def toks(t):
    return {x for x in ENAMES.findall(t) if x not in STOP and not x.isdigit()}


def new_for(line, ln, col, raw):
    window = line[max(0, col - 160):col]
    last, lasti = None, -1
    for o in OTHER:
        p = window.rfind(o)
        if p > lasti:
            last, lasti = o, p
    p = window.rfind("my_ui.py")
    if p > lasti or raw.startswith("my_ui.py"):
        last = "my_ui"
    if (last or "my_ui") != "my_ui":
        return None, "other-file"
    if re.search(r"(v1\.\d|更早|以前|原来)\D{0,12}$", window[-24:]):
        return None, "hist"
    nums = [int(x) for x in re.findall(r"\d+", raw)]
    a, b = nums[0], nums[-1]
    na, nb = M17.get(a), M17.get(b)
    if na is None or nb is None:
        return None, "no-map"
    na, nb = min(na, nb), max(na, nb)
    while nb > na and not V18[nb - 1].strip():
        nb -= 1
    while na < nb and not V18[na - 1].strip():
        na += 1
    src = "\n".join(block_of(V17, B17, a))
    tgt = "\n".join(block_of(V18, B18, na))
    ents = toks(line)
    ov = (len(ents & toks(src)), len(ents & toks(tgt)))
    body = "%d-%d" % (na, nb) if nb > na else "%d" % na
    pre = "my_ui.py:" if raw.startswith("my_ui.py") else ":"
    return pre + body, ("HIT" if ov != (0, 0) else "ZERO")


def main():
    write = "--write" in sys.argv
    txt = MD.read_text(encoding="utf-8")
    lines = txt.splitlines()
    nchanges, rows = 0, []
    for ln, line in enumerate(lines, 1):
        if not any(x <= ln <= y for x, y in SECTIONS):
            continue
        edits = []
        for m in re.finditer(r"(?<![\w.])((?:my_ui\.py)?:\d+(?:-\d+)?)", line):
            raw = m.group(1)
            if (ln, raw) in SKIP:
                rows.append((ln, raw, "SKIP", raw))
                continue
            if (ln, raw) in FORCE:
                new = FORCE[(ln, raw)]
                if new != raw:
                    edits.append((m.start(), m.end(), new))
                    nchanges += 1
                rows.append((ln, raw, "FORCE", new))
                continue
            new, why = new_for(line, ln, m.start(), raw)
            if new is None:
                rows.append((ln, raw, why, raw))
                continue
            new = OVERRIDE.get(raw, new)
            if new != raw:
                edits.append((m.start(), m.end(), new))
                nchanges += 1
                rows.append((ln, raw, why, new))
            else:
                rows.append((ln, raw, "same-" + why, new))
        for a, b, new in sorted(edits, reverse=True):
            line = line[:a] + new + line[b:]
        lines[ln - 1] = line
    for r in rows:
        tgt = V18[int(re.findall(r"\d+", r[3])[0]) - 1].strip()[:70]
        print("%5d %-18s %-10s -> %-18s | %s" % (r[0], r[1], r[2], r[3], tgt))
    print("替换 %d 处" % nchanges)
    if write:
        MD.write_text("\n".join(lines) + ("\n" if txt.endswith("\n") else ""), encoding="utf-8")
        print("已写入；总行数 %d" % len(lines))
    else:
        print("干跑（未写入）；写后总行数应为 %d" % len(lines))


OVERRIDE = {}
main()
