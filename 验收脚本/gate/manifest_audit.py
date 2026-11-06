"""清单复验：manifest 记的是「搬」那一步的字节；本脚本把它和现在的文件、
以及 gate/.before-rewrite/ 里的改前原文三方对一遍。

判定不是「全绿」，而是「对不上的每一份都能点名」。用法：cd 验收脚本 && python3 gate/manifest_audit.py
"""
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAN = ROOT / "manifest-v1.1-v1.7.sha1"
BACKUP = ROOT / "gate/.before-rewrite"

# 改写之后又手工动过的：两份动态拼路径（规则抓不到）＋ 11-01 改扫描范围的两道扫
KNOWN = {
    "v1.5/v15_d7.js": "手工补的动态拼路径 /tmp/v15-d7-<TAG>.png",
    "v1.7/v17_delivery.py": "手工补的动态拼路径 /tmp/v17_<phase>.json",
    "v1.7/v17_scan.py": "2026-11-01 改三份文档的行号扫描范围",
    "v1.7/v17_scan3.py": "2026-11-01 改三份文档的范围端点扫描范围",
}


def sha1(p: pathlib.Path):
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else None


entries = {}
for ln in MAN.read_text(encoding="utf-8").splitlines():
    h, rest = ln.split("  ", 1)
    entries[re.sub(r"\s+\([\d,]+ B\)$", "", rest)] = h

same, rewritten, known, surprise = [], [], [], []
for rel, want in sorted(entries.items()):
    if sha1(ROOT / rel) == want:
        same.append(rel)
    elif sha1(BACKUP / rel) == want:
        rewritten.append(rel)
    elif rel in KNOWN:
        known.append(rel)
    else:
        surprise.append(rel)

print(f"清单 {len(entries)} 条")
print(f"  逐字节相同            {len(same)}")
print(f"  改写、改前原文在备份里 {len(rewritten)}")
print(f"  改写后又手工动过       {len(known)}")
for x in known:
    print(f"    - {x}：{KNOWN[x]}")
print(f"  **谁也解释不了**        {len(surprise)}")
for x in surprise:
    print(f"    ! {x}  当前 sha1 {sha1(ROOT / x)}  备份{'在' if (BACKUP / x).exists() else '不在'}")
print("判定：" + ("意外 0 份，账对得上" if not surprise else f"有 {len(surprise)} 份对不上，先别看绿灯"))
