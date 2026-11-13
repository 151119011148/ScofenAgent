# -*- coding: utf-8 -*-
"""推送前的硬闸：这个仓库是 **public**，所以每一项都按「全世界都能读到」来判。

为什么要闸而不是靠人看：`ai学习/` 里跑着一台有凭证、有会话库、有一份真 Chrome 用户目录的机器，
一次 `git add -A` 的手滑就能把 `Login Data`（40K，昨天还在写）推进公开仓库——
那比 API key 更糟，key 能吊销，浏览器登录态是别人已经拿到手的东西。

四道检查，任何一道不过就 rc=1：
  A 活凭证：从工作区 `smolagents/.env` 读出真值（**不打印**），在仓库**每个**文件里做字节匹配
    ——包括 11-13 新收的三份第三方树和 run/ 证据。这条不因口径变化而放松。
  B 形态匹配：sk-…／Bearer …／cookie 头 这类串，命中只报文件名＋第几行＋长度，不报内容。
    只对**自有文件**跑：11-13 实测 dify/langchain4j 的上游测试夹具里有 6 处天生长得像 key 的假串
    （`sk-123…`／`sk-abc…`／`sk-Iam…`＋1 个假 PEM），对第三方树跑 B 只会让闸永久红、把真信号淹掉。
    第三方树靠 A（真值字节匹配，实测 0 命中）＋C 的私钥文件名那一条兜。
  C 禁入路径：真 `.env`／私钥后缀／Chrome 用户目录（`chrome-*/`、`Login Data`、`History`、
    `Cookies` 这些没后缀的裸文件名）／依赖与产物目录（node_modules、.venv、site-packages、
    __pycache__、target、dist-info）。
  D 体积：单文件 > 8M、总量 > 500M 直接拦。11-13 实测最大单文件是 dify 里 monaco 的 5.5M，
    GitHub 的硬线是 100M（这条撞不上），500M 是「别人 clone 得起不起」的那条线。

2026-11-13 之前 C 里还写着「任何 `run/`、`*.out`、`*.png`、`*.sqlite3` 一律不进」，他改了口径：
证据也要进仓库。放开的只有那三类**产物**，`Login Data`／`History`／`Cookies` 这三个**登录态**
没有放开——它们是这台机器上真浏览器的账号状态，key 能吊销，登录态吊销不了。

跑法：
    cd ~/Desktop/study/ScofenAgent
    python3 tools/prepush_check.py              # 扫工作树里所有会被 git 看到的文件
    python3 tools/prepush_check.py --paths      # 只扫 git 已跟踪的（pre-commit 钩子就这么调）
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV = Path.home() / "Desktop/study/ai学习/smolagents/.env"
LIMIT_FILE = 8_000_000
LIMIT_TOTAL = 500_000_000

# 第三方树：B 形态匹配对它们不跑（理由见文件头）
VENDORED = {"dify", "langchain4j", "servers"}

FORBIDDEN_PARTS = {
    ".venv", "venv", "__pycache__", "node_modules", "site-packages", "target", ".rollback",
    ".idea", ".agent-staging", ".git",
}
FORBIDDEN_NAMES = {
    ".env", ".env.local", "id_rsa", "id_ed25519", "netrc",
    "Login Data", "Login Data For Account", "Cookies", "History", "Web Data",
    "Account Web Data", "Favicons", "Preferences", "Secure Preferences", "visited_links",
    "Login Data-journal", "Cookies-journal", "Login Data For Account-journal", "History-journal",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx", ".pyc"}

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
        if ".git" in parts:
            continue  # 仓库自己的对象库不是内容，扫它只会把 FORBIDDEN_PARTS 里的 .git 变成误报
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
    n_vendored = n_scanned = 0
    for p in files:
        rel = p.relative_to(REPO)
        parts, name = set(rel.parts), rel.name
        bad_parts = {x for x in parts if x in FORBIDDEN_PARTS or x.startswith("chrome-")}
        hit_forbidden = bad_parts or name in FORBIDDEN_NAMES \
            or p.suffix.lower() in FORBIDDEN_SUFFIXES
        if hit_forbidden:
            problems.append("C 禁入路径 %s（%s）" % (rel, ",".join(sorted(
                bad_parts | ({name} & FORBIDDEN_NAMES)
                | ({p.suffix.lower()} & FORBIDDEN_SUFFIXES)))))
            continue
        try:
            data = p.read_bytes()
        except OSError as e:
            problems.append("C 读不了 %s：%s" % (rel, e))
            continue
        total += len(data)
        n_scanned += 1
        for val in secrets:
            if val.encode() in data:
                problems.append("A 活凭证原文在 %s" % rel)
        if rel.parts[0] in VENDORED:
            n_vendored += 1
        else:  # B 只对自有文件跑，理由在文件头
            for label, rx in SECRET_PATTERNS:
                m = rx.search(data)
                if m:
                    line_no = data[:m.start()].count(b"\n") + 1
                    problems.append("B %s 命中于 %s:%d（长度 %d，内容不打印）"
                                    % (label, rel, line_no, len(m.group(0))))
        if len(data) > LIMIT_FILE:
            problems.append("D 单文件超 8M：%s（%d 字节）" % (rel, len(data)))
    if total > LIMIT_TOTAL:
        problems.append("D 仓库总量超 500M：%d 字节" % total)

    print("扫描 %d 个文件（其中第三方树 %d 个，只过 A/C/D 不过 B），累计 %.1f MB；活凭证比对 %d 条（值不打印）"
          % (n_scanned, n_vendored, total / 1048576, len(secrets)))
    if problems:
        print("\n".join("  ✗ " + x for x in problems))
        print("\n不放行：%d 项" % len(problems))
        return 1
    print("\n放行：凭证 0 命中、禁入路径 0 个、体积在限内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
