"""P0：给 agent 五只手 + 一圈边界。

跑法：
    cd ~/Desktop/study/ai学习/smolagents
    .venv/bin/python my_coding_agent.py "final_answer 这个工具是在哪一行注册进 self.tools 的？"

边界（写在代码里，不靠 prompt 求模型自觉）：
    1. 路径白名单：只允许 ROOT 之下的路径，且 .env / .git / .venv / node_modules 一律拒绝
    2. write_file 不落原路径，只落到 .agent-staging/，返回 diff 给人看
    3. run_python 在临时沙箱里跑，env 被清空（模型拿不到 OPENAI_API_KEY），20 秒熔断
"""

import ast
import difflib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from smolagents import OpenAIServerModel, ToolCallingAgent, tool

ROOT = Path("~/Desktop/study/ai学习").expanduser().resolve()
STAGING = ROOT / ".agent-staging"
# 必须在导入时就建：run_python 拿它当 tempfile 的 dir，目录不存在会抛裸 FileNotFoundError。
# 原来这行写在 __main__ 里，而 my_ui.py → my_agent.py 是 import 进来用的，根本不会执行。
STAGING.mkdir(parents=True, exist_ok=True)
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_ID = "qwen-plus"

# 目录名里出现这些就拒绝：凭证、版本库内部、依赖树
DENY_NAMES = {".env", ".git", ".venv", "node_modules", "__pycache__", ".agent-staging"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".agent-staging", ".pytest_cache"}
MAX_LINES = 300
MAX_BYTES = 200_000


def guarded(path: str, must_exist: bool = True) -> Path:
    """把任意用户/模型给的路径收敛到 ROOT 之内，越界即抛错。相对路径一律按 ROOT 解释。"""
    raw = os.path.expanduser(str(path).strip())
    p = Path(raw if os.path.isabs(raw) else ROOT / raw).resolve()
    if not p.is_relative_to(ROOT):
        raise PermissionError(f"越界：{p} 不在白名单根目录 {ROOT} 之下")
    if set(p.parts) & DENY_NAMES:
        raise PermissionError(f"拒绝访问凭证或依赖目录：{p}")
    if must_exist and not p.exists():
        raise FileNotFoundError(f"路径不存在：{p}")
    return p


@tool
def read_file(path: str, start_line: int = 1, lines: int = 200) -> str:
    """读取白名单目录内的文本文件，返回带行号的片段。

    Args:
        path: 文件或目录的绝对路径，也可以是相对 ai学习 的路径
        start_line: 起始行号，从 1 开始
        lines: 最多返回多少行，上限 300
    """
    p = guarded(path)
    if not p.is_file():
        return f"不是文件：{p}（列目录请用 list_dir）"
    text = p.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    n = max(1, min(int(lines), MAX_LINES))
    s = max(1, int(start_line))
    chunk = all_lines[s - 1 : s - 1 + n]
    out = [f"{s + i:>5}| {ln}" for i, ln in enumerate(chunk)]
    tail = ""
    if s - 1 + n < len(all_lines):
        tail = f"\n… 共 {len(all_lines)} 行，本次到第 {s - 1 + n} 行，继续读请传 start_line={s + n}"
    return f"文件 {p.relative_to(ROOT)}\n" + "\n".join(out) + tail


@tool
def list_dir(path: str = ".") -> str:
    """列出白名单目录内某一层的内容，目录名以 / 结尾。

    Args:
        path: 目录路径，默认 ai学习 根目录
    """
    p = guarded(path)
    if not p.is_dir():
        return f"不是目录：{p}（读文件请用 read_file）"
    rows = []
    for e in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if e.name in SKIP_DIRS:
            rows.append(f"  {e.name}/  [已跳过]")
            continue
        rows.append(f"  {e.name}/" if e.is_dir() else f"  {e.name}  {e.stat().st_size}B")
    return f"{p.relative_to(ROOT) or '.'} 共 {len(rows)} 项\n" + "\n".join(rows)


@tool
def grep_files(pattern: str, path: str = ".", max_hits: int = 40) -> str:
    """在白名单目录内按正则搜索文本内容，返回 文件:行号:内容。

    Args:
        pattern: Python re 正则，例如 final_answer\\(|class \\w+Tool
        path: 搜索起点目录，默认 ai学习 根目录
        max_hits: 最多返回多少条命中，上限 100
    """
    root = guarded(path)
    rx = re.compile(pattern)
    limit = max(1, min(int(max_hits), 100))
    hits, scanned = [], 0
    base = root if root.is_dir() else root.parent
    for f in base.rglob("*"):
        if not f.is_file() or set(f.parts) & SKIP_DIRS or DENY_NAMES & set(f.parts):
            continue
        if f.stat().st_size > MAX_BYTES:
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        break_out = False
        for i, ln in enumerate(lines, 1):
            if rx.search(ln):
                hits.append(f"{f.relative_to(ROOT)}:{i}: {ln.strip()[:160]}")
                break_out = len(hits) >= limit
                if break_out:
                    break
        if break_out:
            break
    return f"命中 {len(hits)} 条（扫了 {scanned} 个文件，上限 {limit}）\n" + "\n".join(hits[:limit])


@tool
def write_file(path: str, content: str) -> str:
    """生成新文件内容并给出 diff 预览。注意：不会改原文件，只落到 .agent-staging/ 等你确认。

    Args:
        path: 目标文件路径（白名单内）
        content: 要写入的完整文件内容
    """
    p = guarded(path, must_exist=False)
    if not p.parent.exists():
        return f"父目录不存在，先确认路径：{p.parent}"
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    diff = "\n".join(
        difflib.unified_diff(
            old.splitlines(), content.splitlines(),
            fromfile=f"a/{p.name}", tofile=f"b/{p.name}", lineterm="",
        )
    )
    staged = STAGING / p.relative_to(ROOT)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(content, encoding="utf-8")
    if not diff:
        return f"{p.relative_to(ROOT)} 内容无变化"
    return (
        f"【未写入原文件】diff 如下，副本已暂存到 {staged.relative_to(ROOT)}\n"
        f"确认无误后由你自己在终端执行：cp \"{staged}\" \"{p}\"\n\n{diff[:6000]}"
    )


@tool
def run_python(code: str) -> str:
    """在临时沙箱目录里执行一段 Python，返回 stdout/stderr。只用于验证计算或解析文件。

    Args:
        code: 要执行的 Python 源码，禁止网络请求和删除类操作
    """
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"语法错误，没执行：{e}"
    banned = re.search(r"\brm\b|shutil\.rmtree|os\.remove|os\.unlink|subprocess|socket\.|urllib|requests\.", code)
    if banned:
        return f"拒绝执行：代码里含被禁用的调用 {banned.group(0)!r}"
    with tempfile.TemporaryDirectory(prefix="agent-sbx-", dir=str(STAGING)) as td:
        script = Path(td) / "main.py"
        script.write_text(code, encoding="utf-8")
        env = {"PATH": "/usr/bin:/bin", "HOME": td, "PYTHONIOENCODING": "utf-8",
               "PYTHONUTF8": "1", "LANG": "C.UTF-8"}
        try:
            r = subprocess.run([sys.executable, str(script)], cwd=td, env=env,
                               capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return "超时 20 秒，已杀掉"
        out = (r.stdout or "")[-4000:] + (("\n[stderr]\n" + r.stderr[-2000:]) if r.stderr else "")
        return f"exit={r.returncode}\n{out or '(无输出)'}"


def build_agent(**kw) -> ToolCallingAgent:
    model = OpenAIServerModel(model_id=MODEL_ID, api_base=BASE_URL)
    return ToolCallingAgent(
        tools=[read_file, list_dir, grep_files, write_file, run_python],
        model=model,
        max_steps=kw.get("max_steps", 8),
        name="代码检索助手",
        description="在 ai学习 目录里读代码、搜代码、跑验证",
        stream_outputs=True,
    )


if __name__ == "__main__":
    agent = build_agent()
    task = " ".join(sys.argv[1:]) or "smolagents 里 final_answer 这个工具是在哪一行自动注册进 self.tools 的？把它前后各 3 行读出来给我看。"
    print(f"问题: {task}\n动作空间: {sorted(agent.tools)}\n")
    print("最终答案:", str(agent.run(task)))
