# -*- coding: utf-8 -*-
"""文档闸·体量数字写到**不动点**（v1.8）。

要写的数是三份文档自己的行数与字节数，而这句话本身就在文档里——写完它，字节数又变了。
所以不能一次写完，得**读回来→复测→再代**，直到「文档里写着的数 == 当场测到的数」。

定位口径（v1.8 第一版这脚本用 `DOCITER`/`DOCMAN`/`DOCRED` 三个占位符当锚，跑过一次就把它们吃掉了，
第二轮再跑就找不到锚、却还拿内存里的旧值自欺——所以改成读现场）：
两份宿主（`迭代记录.md` §6 第 8 条、手册 §6「体量与档案」）里各有一句「三份文档终值」，
句中按 **迭代记录 → 手册 → README** 的固定顺序出现恰好三串 `N 行 / M B`；
本脚本只在这一行上按位置代这三串，一行上不是三条就停下报错，绝不猜。

口径：行数用 `wc -l` 那一个数（POSIX 换行数，脚本里等价于 `raw.count(b"\\n")`），字节用文件字节长度。
**这两个数会随本轮再改文档而变**，所以每次改完文档都要重跑一遍本脚本 `--write`。

跑法（cwd=ai学习）：
    python3 验收脚本/v1.8/v18_gate_sizefix.py            # 干跑，只看代不代得动
    python3 验收脚本/v1.8/v18_gate_sizefix.py --write     # 写到不动点，逐轮打印
"""
from __future__ import absolute_import, print_function

import io
import os
import re
import sys

ROOT = os.path.expanduser(u"~/Desktop/study/ai学习")
NAMES = [u"迭代记录.md", u"agent功能手册.html", u"README.md"]   # 被量的三份，顺序即句中顺序
HOSTS = [u"agent功能手册.html", u"迭代记录.md"]                 # 那句「三份文档终值」住在这一份一份里
MARK = u"三份文档终值"
NUM = re.compile(r"[\d,]+ 行 / [\d,]+ B")
MAX_TRIPS = 8


def measure(path):
    raw = open(os.path.join(ROOT, path), "rb").read()
    return u"%s 行 / %s B" % (format(raw.count(b"\n"), ","), format(len(raw), ","))


def read_line(host):
    """从宿主文件里真读回那三串（不是内存里的猜测）。"""
    txt = io.open(os.path.join(ROOT, host), encoding=u"utf-8").read()
    hit = [ln for ln in txt.split(u"\n") if MARK in ln]
    if len(hit) != 1:
        print(u"---- 体量闸结论：宿主 %s 里「%s」出现 %d 次，不是 1 次，停下让人看 ----"
              % (host, MARK, len(hit)))
        raise SystemExit(1)
    found = NUM.findall(hit[0])
    if len(found) != len(NAMES):
        print(u"---- 体量闸结论：宿主 %s 那一行上量到 %d 串，应为 %d 串 ----"
              % (host, len(found), len(NAMES)))
        raise SystemExit(1)
    return txt, hit[0], found


def patch(host, old_line, new_line):
    if old_line == new_line:
        return False
    if not WRITE:
        return True
    txt = io.open(os.path.join(ROOT, host), encoding=u"utf-8").read()
    assert txt.count(old_line) == 1, u"%s：那一行不唯一，不敢整行替换" % host
    io.open(os.path.join(ROOT, host), u"w", encoding=u"utf-8").write(
        txt.replace(old_line, new_line))
    return True


WRITE = u"--write" in sys.argv
print(u"体量闸%s｜行数＝`wc -l` 口径，字节＝文件字节数｜锚：宿主里的「%s」那一行"
      % (u"（写到不动点）" if WRITE else u"（干跑，不落盘）", MARK))
for trip in range(1, MAX_TRIPS + 1):
    cur = [measure(n) for n in NAMES]
    stale = []
    for host in HOSTS:
        _, line, found = read_line(host)
        if found != cur:
            stale.append((host, found))
    print(u"  第 %d 轮：现测 %s ｜ %s" % (trip, u" ／ ".join(cur),
          u" ／ ".join(u"%s 写着 %s" % (h, u"·".join(f)) for h, f in stale)
          if stale else u"两份宿主写的都 == 现测"))
    if not stale:
        break
    for host, found in stale:
        _, line, _ = read_line(host)
        it = iter(cur)
        newline = NUM.sub(lambda m: next(it), line)
        patch(host, line, newline)
    if not WRITE:
        print(u"  干跑：不落盘，不做第二轮。加 --write 才写到不动点")
        print(u"---- 体量闸结论：干跑未落盘 ----")
        raise SystemExit(0)
else:
    print(u"---- 体量闸结论：跑满 %d 轮没收敛，停下让人看 ----" % MAX_TRIPS)
    raise SystemExit(1)

# 收敛后再自证一次：文档里写着的数 == 当场测到的数
ok = True
for host in HOSTS:
    _, _, found = read_line(host)
    for n, val in zip(NAMES, found):
        now = measure(n)
        if val != now:
            ok = False
            print(u"  ✗ %s 在 %s 里写着 %s，当场复测是 %s" % (n, host, val, now))
        else:
            print(u"  ✓ %s 在 %s 里写着 %s == 复测" % (n, host, now))
print(u"---- 体量闸结论：%s ----" % (
    u"三份文档的行数/字节写到不动点，两份宿主里写进去的数与当场复测逐串一致" if ok
    else u"没收敛，见上一段"))
raise SystemExit(0 if ok else 1)
