"""供应链盘点：把 node_modules 里「装完会被 npm 执行的代码」数出来。
只读，不装不改。用法：cd servers && python3 ../验收脚本/servers/v17_supply_chain.py"""
import json
import collections
from pathlib import Path

NM = Path("node_modules")


def is_pkg(p: Path) -> bool:
    """按 npm 的目录约定只认真包：node_modules/<name>/package.json 或 @scope/<name>/package.json。"""
    rel = p.relative_to(NM).parts
    if rel[-1] != "package.json":
        return False
    own = 3 if rel[0].startswith("@") else 2
    return len(rel) == own


pkgs = []
for pj in NM.rglob("package.json"):
    if not is_pkg(pj):
        continue
    try:
        pkgs.append((str(pj.relative_to(NM).parent), json.loads(pj.read_text(encoding="utf-8"))))
    except Exception:
        pass

HOOKS = ("preinstall", "install", "postinstall", "prepare")
count = collections.Counter()
risky, prepares, gyp = [], [], []
for path, d in pkgs:
    s = d.get("scripts") or {}
    for k in HOOKS:
        if k in s:
            count[k] += 1
            (prepares if k == "prepare" else risky).append((path, k, s[k][:60]))
    if d.get("gypfile") is True:
        count["gypfile"] += 1
        gyp.append(path)

print(f"真包 {len(pkgs)} 个")
print(f"钩子分布 {dict(count)}")
print(f"会随安装执行的（pre/install/postinstall）{len(risky)} 条")
for r in risky[:20]:
    print("  ", r)
print(f"gypfile {len(gyp)} 个")
print(f"prepare {len(prepares)} 个，前 8：")
for p in prepares[:8]:
    print("  ", p)
