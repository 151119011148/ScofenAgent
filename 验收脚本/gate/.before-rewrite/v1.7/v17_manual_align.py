# -*- coding: utf-8 -*-
"""按 /tmp/v17_readme_align.py 的判定，把 README 里 my_ui.py 的行号落到 v1.7（1,253 行）。

不带 --write 只出干跑清单。OVERRIDE / SKIP 是人工过提案表的结果，理由写在那儿。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
MD = ROOT / "agent功能手册.html"

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
SECTIONS = [(95, 574), (1122, 1182)]

# 人工改判：v1.6:1132 是 _on_load 的 return 那一行；v1.7 里 return 挪到 1180
# （1179 是本轮新加的 shown = _session_steps(...)），机器按"变更块起点"给了 1179。
OVERRIDE = {}
# 人工补判：这几条前面 160 字符里点过别的文件名（chat_interface.py / agents.py），
# 机器按窗口归属判成了"别的文件"，实际讲的是 my_ui.py；其中 `:584`、`:648-653`
# 是上一轮漏掉的 v1.5 时代号，这里一并落到 v1.7 的真实位置（逐条对过源码内容）。
FORCE = {(147, "my_ui.py:32"): "my_ui.py:34",
         (179, ":546-600"): ":565-621",
         (179, ":64-211"): ":63-234",
         (191, ":913-928"): ":1027-1041",
         (194, ":1098-1116"): ":1137-1160",
         (311, "my_ui.py:730-737"): "my_ui.py:1049-1054",
         (311, ":746-747"): ":1067",
         (311, ":810-820"): ":1162-1180",
         (317, "my_ui.py:291-298"): "my_ui.py:488-491",
         (323, "my_ui.py:507-508"): "my_ui.py:535-536",
         (323, ":1008"): ":1131",
         (323, ":564-566"): ":602-605",
         (323, ":778"): ":846",
         (334, "my_ui.py:49-65"): "my_ui.py:821-829",
         (340, "my_ui.py:32"): "my_ui.py:34",
         (340, ":550-573"): ":806-829",
         (340, ":575-687"): ":831-960",
         (346, "my_ui.py:132-224"): "my_ui.py:401-516",
         (346, ":442"): ":1240",
         (358, "my_ui.py:495-521"): "my_ui.py:749-780",
         (305, "my_ui.py:738"): "my_ui.py:1092"}
# 刻意不动：历史叙述 / 别的文件的行号
SKIP = {(315, "my_ui.py:289-291"),   # 句中写明「旧 my_ui.py:289-291」＝v1.2 时代的位置
        (334, "my_ui.py:306-323"),   # 「v1.2 追加两笔：搬到 :306-323」＝带版本标签的历史链
        (334, ":374"),               # 同上（v1.2 自建停止键）
        (334, "my_ui.py:750-763"),   # 「v1.3 追加第三笔」＝带版本标签的历史链
        (1128, ":198"),              # 讲的是 my_coding_agent.py:198
        (286, ":171")}               # 同上：D1 那条 tempfile.TemporaryDirectory 在 my_coding_agent.py:171


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


B16, B17 = blocks(V16), blocks(V17)


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
    na, nb = M16.get(a), M16.get(b)
    if na is None or nb is None:
        return None, "no-map"
    na, nb = min(na, nb), max(na, nb)
    while nb > na and not V17[nb - 1].strip():
        nb -= 1
    while na < nb and not V17[na - 1].strip():
        na += 1
    src = "\n".join(block_of(V16, B16, a))
    tgt = "\n".join(block_of(V17, B17, na))
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
        tgt = V17[int(re.findall(r"\d+", r[3])[0]) - 1].strip()[:70]
        print("%5d %-18s %-10s -> %-18s | %s" % (r[0], r[1], r[2], r[3], tgt))
    print("替换 %d 处" % nchanges)
    if write:
        MD.write_text("\n".join(lines) + ("\n" if txt.endswith("\n") else ""), encoding="utf-8")
        print("已写入；总行数 %d" % len(lines))
    else:
        print("干跑（未写入）；写后总行数应为 %d" % len(lines))


main()
