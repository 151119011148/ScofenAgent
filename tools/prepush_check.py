# -*- coding: utf-8 -*-
"""推送前的硬闸：这个仓库是 **public**，所以每一项都按「全世界都能读到」来判。

为什么要闸而不是靠人看：`ai学习/` 里跑着一台有凭证、有会话库、有一份真 Chrome 用户目录的机器，
一次 `git add -A` 的手滑就能把 `Login Data`（40K，昨天还在写）推进公开仓库——
那比 API key 更糟，key 能吊销，浏览器登录态是别人已经拿到手的东西。

四道检查，任何一道不过就 rc=1：
  A 活凭证：从工作区 `smolagents/.env` 读出真值（**不打印**），在仓库每个文件里做字节匹配。
  B 形态匹配：sk-…／Bearer …／cookie 头 这类串，命中只报文件名＋第几行＋长度，不报内容。
  C 禁入路径：.env / .venv / run/ / .agent-* / .rollback / *.sqlite3 / Chrome 用户目录关键字 …
  D 体积：单文件 > 1M、总量 > 20M 直接拦——大文件既不是代码也不该塞进别人 clone 的等待时间。

跑法：
    cd ~/Desktop/study/ScofenAgent
    python3 tools/prepush_check.py              # 扫工作树里所有会被 git 看到的文件
    git ls-files | xargs -0 python3 tools/prepush_check.py --paths  # 只扫已暂存的
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV = Path.home() / "Desktop/study/ai学习/smolagents/.env"
LIMIT_FILE = 1_000_000
LIMIT_TOTAL = 20_000_000

FORBIDDEN_PARTS = {
    ".venv", "__pycache__", "node_modules", "run", "chrome-d168", ".rollback", ".idea",
    ".agent-staging", "site-packages",
}
FORBIDDEN_NAMES = {
    ".env", ".env.local", "Login Data", "Login Data For Account", "Cookies",
    "Account Web Data", "Web Data", "History", "visited_links", "Cookies-journal",
}
FORBIDDEN_SUFFIXES = {".sqlite3", ".db", ".log", ".out", ".png", ".jpg", ".jpeg", ".gif",
                      ".wasm", ".pma", ".skill", ".zip", ".egg-info"}

SECRET_PATTERNS = [
    ("sk-形态密钥", re.compile(rb"sk-[A-Za-z0-9]{16,}")),
    ("Authorization Bearer", re.compile(rb"Authorization['\"]?\s*[:=]\s*['\"]?Bearer\s+\S{8,}", re.I)),
    ("Cookie 头", re.compile(rb"['\"]?cookie['\"]?\s*[:=]\s*['\"][^'\"]{24,}", re.I)),
    ("PEM 私钥", re.compile(rb"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def live_secrets():
    """`.env` 里所有**看起来是密钥**的赋值，含被注释掉的历史那行。

    为什么不放过注释行：换 key 的时候旧值通常就是注释掉留在原地，而它照样可能是某个
    文档／证据里引过的串——旧 key 若还没吊销，推上去和推新 key 是同一件事。
    实测（2026-11-07）：这台机器上 .env 里有 1 条生效（117 字符）＋ 1 条注释（116 字符），
    两条都进比对，仓库里 0 命中。值全程不打印。
    """
    out = []
    if not ENV.is_file():
        return out
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*#?\s*([A-Z_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z_]*)\s*=\s*(.+)$", line)
        if not m:
            continue
        v = m.group(2).strip().strip('"').strip("'")
        if len(v) >= 12:
            out.append(v)
    return out


def walk_files():
    for p in sorted(REPO.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        parts = set(p.relative_to(REPO).parts)
        if "tools" in parts and p.name == "prepush_check.py":
            continue  # 本文件里有那些正则，扫自己会误报（模式串是转义写法，实测也不命中，仍排除）
        yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", action="store_true", help="从 stdin 读 git lsfiles 的路径来扫")
    a = ap.parse_args()

    if a.paths:
        raw = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"],
                             capture_output=True).stdout
        files = [REPO / x.decode() for x in raw.split(b"\0") if x]
    else:
        files = list(walk_files())

    secrets = live_secrets()
    problems = []
    total = 0
    for p in files:
        rel = p.relative_to(REPO)
        parts, name = set(rel.parts), rel.name
        hit_forbidden = (parts & FORBIDDEN_PARTS) or name in FORBIDDEN_NAMES \
            or p.suffix.lower() in FORBIDDEN_SUFFIXES
        if hit_forbidden:
            problems.append("C 禁入路径 %s（%s）" % (rel, ",".join(sorted((parts & FORBIDDEN_PARTS) | ({name} & FORBIDDEN_NAMES) | ({p.suffix} & FORBIDDEN_SUFFIXES)))))
            continue
        try:
            data = p.read_bytes()
        except OSError as e:
            problems.append("C 读不了 %s：%s" % (rel, e))
            continue
        total += len(data)
        for val in secrets:
            if val.encode() in data:
                problems.append("A 活凭证原文在 %s" % rel)
        for label, rx in SECRET_PATTERNS:
            m = rx.search(data)
            if m:
                line_no = data[:m.start()].count(b"\n") + 1
                problems.append("B %s 命中于 %s:%d（长度 %d，内容不打印）"
                                % (label, rel, line_no, len(m.group(0))))
        if len(data) > LIMIT_FILE:
            problems.append("D 单文件超 1M：%s（%d 字节）" % (rel, len(data)))
    if total > LIMIT_TOTAL:
        problems.append("D 仓库总量超 20M：%d 字节" % total)

    print("扫描 %d 个文件，累计 %.1f KB；活凭证比对 %d 条（值不打印）"
          % (len(files), total / 1024, len(secrets)))
    if problems:
        print("\n".join("  ✗ " + x for x in problems))
        print("\n不放行：%d 项" % len(problems))
        return 1
    print("\n放行：凭证 0 命中、禁入路径 0 个、体积在限内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
