# -*- coding: utf-8 -*-
"""把 payload 体积的单位口径（字符 vs UTF-8 字节）在两份文档里写死，并如实记下 dump 脚本那个 label bug。"""
import pathlib

ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")

PAIRS_JL = [
    ("**用归档的 `.rollback/v1.6` 编码器现编**，415 B / 414 B、`fmt=v1`、无 wait，不是手写的假 v1",
     "**用归档的 `.rollback/v1.6` 编码器现编**，415 / 414 字符（UTF-8 425 / 424 B）、`fmt=v1`、无 wait，不是手写的假 v1"),
    ("`duration=[22.08, 0.97]`、965 B；`messages` 5 条",
     "`duration=[22.08, 0.97]`、965 字符（UTF-8 1,013 B）；`messages` 5 条"),
    ("新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、1,015 B",
     "新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、967 字符（UTF-8 1,015 B）"),
    ("4. **体积**：每格 12~17 字节（`, \"wait\": 20.743`）",
     "4. **体积**：每格 12~17 个字符（`, \"wait\": 20.743` 这一串是纯 ASCII，**字符数＝字节数**）"),
    ("④ 本轮在真实库里**只追加**（新增会话 8），旧 7 行逐字节未动。",
     "④ 本轮在真实库里**只追加**（新增会话 8），旧 7 行逐字节未动。"
     "⑤ **第 7 步回写时抓到的一处单位口径错**：`/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_dump.py` 那行印的是 `bytes=%d`，"
     "实际给的是 `len(payload)`——payload 是 TEXT，这个数是**字符**，而 UTF-8 字节数更大"
     "（探测口那条 v2 会话：965 字符 / 1,013 B；交付形态那条：967 字符 / 1,015 B）。"
     "脚本已改成同时印 `chars=` 与 `utf8=B`，上面两处 B 的字样按实测**改成两个数都写**；"
     "`sha1` 走的是 `encode()` 之后的字节，所以那 7 行逐字节不变的断言不受影响。"),
]

PAIRS_MD = [
    ("现编两条**真 v1** payload 种进去：415 B / 414 B、`fmt=v1`、无 wait——不是手写的假 v1",
     "现编两条**真 v1** payload 种进去：415 / 414 字符（UTF-8 425 / 424 B）、`fmt=v1`、无 wait——不是手写的假 v1"),
    ("`duration=[22.08, 0.97]`、965 B |",
     "`duration=[22.08, 0.97]`、965 字符（UTF-8 1,013 B） |"),
    ("新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、1,015 B |",
     "新增 sid 8：`fmt=v2`、`wait=[20.672, 无]`、967 字符（UTF-8 1,015 B） |"),
    ("**7b** 真等过才多写、多的正好是 `, \"wait\": 12.346` 那 16 字节",
     "**7b** 真等过才多写、多的正好是 `, \"wait\": 12.346` 那 16 个字符（纯 ASCII，字符＝字节）"),
]


def apply(path, pairs):
    p = ROOT / path
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert t.count(old) == 1, (path, t.count(old), old[:48])
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print(path, "ok，总行数", len(t.splitlines()))


apply("迭代记录.md", PAIRS_JL)
apply("README.md", PAIRS_MD)
