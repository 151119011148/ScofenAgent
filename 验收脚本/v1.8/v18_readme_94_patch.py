#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 §9.4 的三处改动（14 条状态头、14 条末尾的处置段、新增 17~21 条）从补丁文件落进 README。

补丁文件用 @@NAME@@ / @@END+NAME@@ 包块，脚本只做「块内文本 == 唯一替换」这一件事：
计数不为 1 就一条都不写、退出码 2。为什么不用 heredoc 直接内联：这些段落里有
`{'sessions': 1, ...}` 这种带引号的实测读数，python 字符串字面量会被它自己截断（本轮踩过一次）。

跑法（cwd=ai学习）：
    python3 验收脚本/v1.8/v18_readme_94_patch.py            # 只报能不能落
    python3 验收脚本/v1.8/v18_readme_94_patch.py --write     # 落盘，改前副本进 run/
"""
import io
import os
import re
import sys

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
README = os.path.join(ROOT, "README.md")
PATCH = os.path.join(ROOT, u"验收脚本", "v1.8", "v18_readme_94_patch.txt")
BACKUP = os.path.join(ROOT, u"验收脚本", "v1.8", "run", "v18_README.before-94.md")

BLOCKS = [
    (u"REPL14HEAD", u"END14HEAD"),      # 14 条的抬头：【待补】→【已修 v1.8 #38】
    (u"APPEND14TAIL", u"END14TAIL"),    # 14 条末尾追加处置段
    (u"NEWITEMS", u"ENDNEWITEMS"),      # 16 条之后追加 17~21
]


def read_blocks(path):
    text = io.open(path, encoding="utf-8").read()
    out = {}
    for name, end in BLOCKS:
        m = re.search(u"@@%s@@\\n(.*?)\\n@@%s@@$" % (name, end), text, re.S | re.M)
        if not m:
            raise SystemExit(u"补丁文件里找不到块 %s" % name)
        out[name] = m.group(1)
    return out


def main():
    write = "--write" in sys.argv[1:]
    blocks = read_blocks(PATCH)
    src = io.open(README, encoding="utf-8").read()
    cur = src

    head_old = u"14. 【待补】**D8（v1.7 实跑暴露，两条路都有留痕）**"
    head_new = blocks[u"REPL14HEAD"].strip()
    for label, old, new in [
        (u"14 条抬头", head_old, head_new),
        (u"14 条末尾", TAIL_14, TAIL_14 + blocks[u"APPEND14TAIL"].strip()),
        (u"新增 17~21", ITEM_16_TAIL, ITEM_16_TAIL + u"\n" + blocks[u"NEWITEMS"].strip()),
    ]:
        n = cur.count(old)
        if n != 1:
            print(u"%s：锚点出现 %d 次，不是 1 次 —— 不落盘" % (label, n))
            return 2
        cur = cur.replace(old, new, 1)
        print(u"%s：唯一命中，已替换" % label)

    print(u"README %d 行 / %d B（改前 %d 行 / %d B）" % (
        cur.count(u"\n") + 1, len(cur.encode("utf-8")),
        src.count(u"\n") + 1, len(src.encode("utf-8"))))
    if not write:
        print(u"试运行：没写盘。加 --write 才落。")
        return 0
    io.open(BACKUP, "w", encoding="utf-8").write(src)
    io.open(README, "w", encoding="utf-8").write(cur)
    print(u"已落盘，改前副本 %s" % BACKUP)
    return 0


TAIL_14 = (u"**这是 v1.6 就有的行为，不是 V9 的回归**（v1.7 的两轮干净跑通是因为一整轮只发一份 CDP 剧本，不中途 reload）。")
ITEM_16_TAIL = (u"要长期留痕得把 `tee` 改成 `tee -a` 或按日期分文件——那是改启动器，不在 V9 范围内。")

if __name__ == "__main__":
    sys.exit(main())
