"""把验收脚本里硬编码的 /tmp 路径改写成本目录 run/ 子目录的绝对路径。

只改可执行文件（.py/.js/.mjs/.sh/.scpt 和 mmd 的三个 html 外壳）。证据文件（.out/.log/.diff/
.txt/.json/.png/.sqlite3/.md）一律不碰——里面的 /tmp 路径是当时的实录，改了就等于篡改证据，
而且会让 manifest 的 sha1 全部失配。

落到 run/ 而不是轮次目录本身：这些脚本里有 unlink/rm 自己产物的写法（v16_seed.py 开局删库、
v13_test.py 反复 unlink 夹具），指向原件会把归档证据删掉。run/ 是一次性目录，随时可整删。

只搬「已经收进本目录的文件名」；其余 /tmp 引用（Chrome profile 缓存等）原样留着，
否则 mmd_run2.sh 里的 rm -rf /tmp/mmd-profile2 会变成指向语料库目录的删除命令。

用法：
    python3 gate/rewrite_tmp_paths.py          # dry-run，只打印将要发生的替换
    python3 gate/rewrite_tmp_paths.py --write  # 真写：先建 run/ 并铺好副本，再改写，原文备份到 gate/.before-rewrite/
"""

import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DRY = "--write" not in sys.argv
BACKUP = ROOT / "gate" / ".before-rewrite"
# 只改可执行的东西。证据文件（.out/.log/.diff/.txt/.json/.png/.sqlite3/.md 备份）一律不碰——
# 那些 /tmp 路径是当时的实录，改了就是篡改证据。
TEXT_SUFFIXES = {".py", ".js", ".mjs", ".sh", ".scpt"}
HARNESS = {"mmd_harness.html", "mmd_render.html", "mmd_page.html"}
# 归档的源码快照（当时代码长什么样是证据），不改。
# v14_ui.py / v15_ui.py 看着像快照，其实是在线探测口的启动器（把 DB_PATH 指到临时库），所以不在这里。
ARCHIVED_SOURCES = {"v12-ca.py"}
SKIP_DIRS = {"run", ".before-rewrite"}
# 先长后短，避免 v17 前缀吃掉 v17a 之类的名字
TOKEN = re.compile(r"/tmp/([A-Za-z0-9][A-Za-z0-9._\-]*)")


def main():
    known = {}
    for sub in ROOT.iterdir():
        if not sub.is_dir() or sub.name in SKIP_DIRS:
            continue
        for f in sub.iterdir():
            if f.is_file():
                known.setdefault(f.name, sub)
    hits, touched, files = {}, [], 0
    for f in sorted(ROOT.rglob("*")):
        if not f.is_file() or BACKUP in f.parents or any(p.name in SKIP_DIRS for p in f.parents):
            continue
        if f.suffix not in TEXT_SUFFIXES and f.name not in HARNESS:
            continue
        if f.name in ARCHIVED_SOURCES:
            continue
        files += 1
        text = f.read_text(encoding="utf-8", errors="strict")
        found = [(m.group(1), m.group(0)) for m in TOKEN.finditer(text)]
        subs = {}
        for name, whole in found:
            dest = known.get(name)
            if dest is None:
                continue
            subs[whole] = str(dest / "run" / name)
        if not subs:
            continue
        touched.append(str(f.relative_to(ROOT)))
        for old, new in subs.items():
            hits[(old, new)] = hits.get((old, new), 0) + 1
            text = text.replace(old, new)
        if not DRY:
            BACKUP.mkdir(parents=True, exist_ok=True)
            dst = BACKUP / f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            f.write_text(text, encoding="utf-8")
    # run/ 铺副本：脚本之间会互相调用（v17_drill.sh 里跑 v17_dump.py），
    # 改写后的路径指向 run/，所以这里把原件按同名复制过去。轮次目录里的原件一动不动。
    seeded = 0
    if not DRY:
        for (old, new), _ in hits.items():
            src = known.get(pathlib.Path(old).name)
            if src is None:
                continue
            dst_dir = pathlib.Path(new).parent
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / pathlib.Path(old).name
            if not dst.exists():
                shutil.copy2(src / pathlib.Path(old).name, dst)
                seeded += 1
    print(f"扫了 {files} 个可执行文本，{len(touched)} 个含可改写的 /tmp 引用，"
          f"去重后 {len(hits)} 条改写规则，run/ 铺了 {seeded} 份副本")
    for t in touched:
        print(f"  待改 {t}")
    for (old, new), n in sorted(hits.items()):
        print(f"  {n:>3}x  {old}  ->  {new}")
    print("DRY-RUN，没写文件" if DRY else "已写入")


main()
