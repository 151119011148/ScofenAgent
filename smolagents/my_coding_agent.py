"""P0：给 agent 五只手 + 一圈边界。

跑法：
    cd ~/Desktop/study/ai学习/smolagents
    .venv/bin/python my_coding_agent.py "final_answer 这个工具是在哪一行注册进 self.tools 的？"

边界（写在代码里，不靠 prompt 求模型自觉）：
    1. 路径白名单：只允许 ROOT 之下的路径，且 .env / .git / .venv / node_modules 一律拒绝
    2. write_file 不落原路径，只落到 .agent-staging/，返回 diff 给人看
    3. run_python 在临时沙箱里跑，env 被清空（模型拿不到 OPENAI_API_KEY），20 秒熔断
    4. 模型调用带 60 秒 read 超时（B1，见下面 MODEL_TIMEOUT_S 那段）：真挂住的请求不再占住半小时
    5. 采样参数默认锁到 temperature=0（P1-4，见下面 MODEL_GENERATION_KWARGS 那段）：不锁则同一题
       跑两遍判分会翻，改前／改后的读数没法归因。锁的是**采样这一项骰子**，不是可复现性——
       同一份 0.0 下 Q9 仍然打出过两种轨迹（证据就写在那段注释里），可用 AGENT_TEMPERATURE 放回
"""

import ast
import difflib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from dotenv import load_dotenv
from smolagents import OpenAIServerModel, ToolCallingAgent, tool

# 显式给 .env 路径，不用无参的 load_dotenv()：后者靠 find_dotenv() 翻调用栈，
# 从管道/stdin 里跑（验收脚本就是这么跑的）会 assert frame.f_back is not None 直接炸。
load_dotenv(Path(__file__).resolve().parent / ".env")

ROOT = Path("~/Desktop/study/ai学习").expanduser().resolve()
STAGING = ROOT / ".agent-staging"
# 必须在导入时就建：run_python 拿它当 tempfile 的 dir，目录不存在会抛裸 FileNotFoundError。
# 原来这行写在 __main__ 里，而 my_ui.py → my_agent.py 是 import 进来用的，根本不会执行。
STAGING.mkdir(parents=True, exist_ok=True)
# 模型这一格改成**可配置的默认值**：服务商整题拒收（2026-11-04 的 400 #overdue-payment）时，
# 换 key／换 provider 应该是改 `.env` 两行，而不是改两个文件里的硬编码再祈祷它们一致
# （改前 my_agent.py 和这里各写了一份同样的字面量，漂移了没人发现）。
# 默认值仍指向百炼的 qwen-plus，不设环境变量时行为和以前逐字相同。
# 可覆盖项：AGENT_MODEL_ID、AGENT_BASE_URL（OPENAI_API_KEY 走 SDK 自己的口径）。
_MODEL_DEFAULT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_MODEL_DEFAULT_ID = "qwen-plus"
BASE_URL = os.environ.get("AGENT_BASE_URL") or _MODEL_DEFAULT_URL
MODEL_ID = os.environ.get("AGENT_MODEL_ID") or _MODEL_DEFAULT_ID

# B1：模型调用的刹车。这里给的是**默认值**，真正在跑的 model 在 my_agent.py:69 那一路。
# 为什么要有这两个数（改前实测，探针读的是 my_agent 那个活对象 `model.client`）：
#   · timeout = Timeout(connect=5.0, read=600) —— openai SDK 的默认 read 是 **600 秒**；
#   · max_retries = 2 —— 也是 SDK 默认，即「1 次原始 + 2 次重试」；
#   · 框架那一层的 retryer（models.py:1174-1178）谓词是 is_rate_limit_error，
#     实测 `is_rate_limit_error(APITimeoutError(...))` → False：**超时不归它重试**（reraise=True 直接抛）。
#   三者乘起来：一个「连得上、不回帧」的请求要占住 600s × 3 ≈ **30 分钟**才失败，
#   而界面在这半小时里一直是「生成中」，删除按钮也被这把锁拒着（v1.9 那条 refusal 文案）。
#   read=60 是「60 秒内没有新帧就算挂」，不是「整题只给 60 秒」——流式输出每个 chunk 都会重置它，
#   所以正常的长答复不受影响，被砍掉的只有真挂住的那一种。
MODEL_TIMEOUT_S = 60.0
MODEL_CONNECT_TIMEOUT_S = 5.0
MODEL_MAX_RETRIES = 2
# connect 单独给 5 秒：SDK 默认就是 5.0，而 `timeout=60.0` 那种写法会把 connect 一起放宽到 60，
# 于是「根本连不上」这种情况反而比改前更慢。要动的只有 read（等帧的那一段）。
MODEL_CLIENT_KWARGS = {
    "timeout": httpx.Timeout(MODEL_TIMEOUT_S, connect=MODEL_CONNECT_TIMEOUT_S),
    "max_retries": MODEL_MAX_RETRIES,
}

# P1-4：采样参数锁死。这一份走的是 OpenAIServerModel 的 **kwargs（models.py:1668 那条文档
# 「for instance `temperature`」），不是 client_kwargs——client 那一层装的是连接期的事，
# 采样是每发请求的事。两条路在 _prepare_completion_kwargs 里合流，`self.kwargs` **最后覆盖**
# （models.py:545-550），所以这里写死的东西，agent 那一层传不进来也改不掉。
# 为什么必须锁（证据：验收脚本/v2.0/run/v20_eval_baseline.json，2026-11-06 那份基线）：
#   · 一致性 4/5——同一道 Q9 跑三发，第二发判分从达标翻成不达标，工具调用序列却一样；
#   · 于是「改前 72.2% → 改后 75%」这类对比无法归因：分不清是代码变了还是骰子变了。
#   改前这两个构造点一个采样参数都不传，temperature／top_p 全吃服务端默认值。
# 0 = 贪心解码。要说清它**不等于逐字节可复现**：9.1-15 那条面试追问的诚实答案仍然是
# 「服务端 batching／MoE 路由还会抖」，这一刀压的是噪声底，不是抹掉随机性。
# AGENT_TEMPERATURE 是给探针留的活口（默认 0.0，不设为逐字不变）。为什么留这一格：
# 锁完之后我拿同一道 Q9 打了两次「跑两遍比逐字节」的对照，两次结论互相矛盾——
#   · run/v20_probe_planning_det-t0.json：轨迹／答复／判分三格全同，token 24342 vs 24148；
#   · run/v20_probe_planning_arms4.json 的 determinism：轨迹**不同**、判分**不同**，
#     token 24260 vs 7315（一发 2 步、一发跑到 6 步），first_diff 落在第 1 次调用。
# 四次尝试、三种轨迹、两种判分，temperature 一直是 0.0。所以 P1-4 的结论是**负结果**：
# 锁温该做（它把「采样骰子」这一项从可变因素里划掉了；0.0 确实进了请求体，这一点由
# run/v20_probe_temperature_offline.py 零网络复验——把 client.create 换成记录用的假函数看载荷，
# 不设=0.0、设 0.7=0.7、坏值在导入阶段就报错退出），
# 但它换不来可复现——一致性仍然只能靠 repeat 多次抽样量出来（这就是 v20_questions 里
# repeat 名单从 5 道扩到 7 道的理由）。想复验这段结论，改这个环境变量就能把骰子放回去，
# 不用动源码，也不会污染默认路径。
_MODEL_TEMP_RAW = os.environ.get("AGENT_TEMPERATURE")
# 不用 try/except 包一条自定义错误文案：裸 `float()` 在坏值时同样炸在导入期，
# 而 traceback 那一行就写着 AGENT_TEMPERATURE 和它收到的原文——够用。这里**绝不能**有 fallback：
# 拼错一个字母若静默退回 0.0，就会拿"锁过温"的口径去解释一份其实没锁的读数。
# （另外：写成 try/except raise 会新增一个模块级 ast.Raise 节点，v18_test_dup 的 9a 提示词面守卫
#  按 ast.walk 收所有 Raise，那会把这条守卫变成误报——守卫本身是对的，别为了让它绿去放宽它。）
MODEL_TEMPERATURE = float(_MODEL_TEMP_RAW) if _MODEL_TEMP_RAW else 0.0
MODEL_GENERATION_KWARGS = {"temperature": MODEL_TEMPERATURE}

# 目录名里出现这些就拒绝：凭证、版本库内部、依赖树
# .agent-staging 在这个名单里是**故意的**（2026-10-30 D2 定性：不改行为，只把理由写死）：
# guarded() 读写两侧都挡，于是 staging 的唯一入口是 write_file 里 `staged = STAGING / p.relative_to(ROOT)`
# 那一次拼接，唯一出口是你自己在终端执行的 cp。agent 读不回自己刚暂存的副本，就不会把「等你确认的草稿」
# 当成仓库现状再读一遍、并在同一轮里基于它继续往下推——放开读等于把这个自我确认的闭环重新打开。
DENY_NAMES = {".env", ".git", ".venv", "node_modules", "__pycache__", ".agent-staging"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".agent-staging", ".pytest_cache"}
MAX_LINES = 300
MAX_BYTES = 200_000


def guarded(path: str, must_exist: bool = True) -> Path:
    """把任意用户/模型给的路径收敛到 ROOT 之内，越界即抛错。相对路径一律按 ROOT 解释。

    这两条错误文案是**给模型读的**（observation 原样进下一轮上下文），P0-a／P0-c。
    为什么要在文案里指路，证据在 ai学习/.agent-ui.log（2026-11-03 21:06 那轮，两条 run）：
      · 旧越界文案只说「不在白名单根目录之下」，模型读完下一步写的是
        「请联系系统管理员调整权限」——本机没有这个开关，那是它自己补出来的路径；
      · 旧 FileNotFoundError 只给拼接后的结果（路径不存在：…/ai学习/人生），不给口径，
        模型不知道自己把 `人生/` 接到了哪个根上，于是**同名同参**又把 list_dir('人生/')
        打了一遍（Step 1→Step 3），中间还重复列了 3 次根目录。
    这两处只改说什么，不改任何判定：收敛逻辑、DENY_NAMES、must_exist 的分支顺序一字未动。
    """
    raw = os.path.expanduser(str(path).strip())
    relative = not os.path.isabs(raw)
    p = Path(raw if not relative else ROOT / raw).resolve()
    if not p.is_relative_to(ROOT):
        raise PermissionError(
            f"越界：{p} 不在白名单根目录 {ROOT} 之下。"
            f"这一整套工具（read_file／list_dir／grep_files／write_file／run_python）只服务这一个根，"
            f"根外的路径一个都到不了；而且动作空间里**没有删除、移动、重命名这类工具**——"
            f"所以『把那个目录删掉』不是权限没开，是这套手根本没有这一只，绕路径也绕不出来。"
            f"下一步请直接把这件事讲清楚给用户：ROOT 之外要他自己在终端执行；"
            f"不要再换一条根外路径重试，也不要让用户去找系统管理员开权限（没有这个开关）。"
        )
    if set(p.parts) & DENY_NAMES:
        raise PermissionError(f"拒绝访问凭证或依赖目录：{p}")
    if must_exist and not p.exists():
        if relative:
            raise FileNotFoundError(
                f"路径不存在：{p}。这里把口径摊开：你给的是相对路径 {raw!r}，"
                f"我只能把它接到白名单根 {ROOT} 底下再找，**不会去猜别的根目录**；"
                f"根外有没有同名目录我读不到（工具到不了那里），要用户自己确认。"
                f"如果你要的就是根外那一个，那属于越界，处理办法见上一条。"
                f"不要用同一个参数再打一遍：要么 list_dir(path='.') 看这个根下真实有什么，"
                f"要么在最终答复里讲明『{ROOT} 之下没有 {p.name}』。"
            )
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
    """列出白名单目录内某一层的内容，目录名以 / 结尾。只能列这个根之内，列不到根外的任何目录。

    Args:
        path: 目录路径，默认 ai学习 根目录；相对路径按 ai学习 根解释
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
    这是这套工具里唯一会留下文件的动作，也是**唯一**的写动作：删除、移动、重命名都没有对应工具，
    不要用 write_file 去空内容或者改名来凑——那只会把草稿落进 .agent-staging/，原文件一个字不动。

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
    model = OpenAIServerModel(model_id=MODEL_ID, api_base=BASE_URL, client_kwargs=MODEL_CLIENT_KWARGS,
                              **MODEL_GENERATION_KWARGS)
    return ToolCallingAgent(
        tools=[read_file, list_dir, grep_files, write_file, run_python],
        model=model,
        max_steps=kw.get("max_steps", 8),
        name="代码检索助手",
        # P0-b：能力穷举写死，不给「大概还能删吧」留空隙。
        # **这一份在本机是不给模型读的**（实测见 验收脚本/v1.8/run/v18_p04_live.out 之后
        # 那一档 p0abc 证据）：ToolCallingAgent 是顶层 agent，`self.description` 只在
        # `describe()` 里用，而 describe() 只服务于被上级调用的 managed agent（agents.py:1005）；
        # 渲染出的 system_prompt 4,796 字符里没有这个字段（探针：`'读代码' in agent.system_prompt` → False）。
        # 模型真正读得到的是**每个工具的 docstring**（system_prompt 末尾那份清单）。
        # 所以这一段留作人读的规格＋万一这 agent 被挂成子 agent 时生效；
        # 真正起作用的穷举写在 list_dir／write_file 的 docstring 里，以及 guarded() 那两条报错里。
        description=(
            "在 ai学习 目录里读代码、搜代码、跑验证。能力就这些，没有别的：\n"
            "1) read_file：读这一个根之内的文本文件，带行号，单次最多 300 行；\n"
            "2) list_dir：列这一个根之内某一层目录，默认列根；\n"
            "3) grep_files：在这个根之内按正则搜文件内容，最多 100 条；\n"
            "4) write_file：只往 .agent-staging/ 落一份草稿并给 diff，原文件一概不动；\n"
            "5) run_python：在临时沙箱里跑一段 Python 验证计算，env 清空、20 秒熔断，"
            "代码里出现 rm/rmtree/remove/unlink/subprocess/socket/urllib/requests 直接拒绝。\n"
            "做不到的（别试，也别对用户承诺）：删除、移动、重命名、写根之外的任何路径、"
            "访问网络、执行 shell 命令、读 .env/.git/.venv/node_modules/__pycache__。"
            "根外的文件请用户在自己的终端处理。"
        ),
        stream_outputs=True,
    )


if __name__ == "__main__":
    agent = build_agent()
    task = " ".join(sys.argv[1:]) or "smolagents 里 final_answer 这个工具是在哪一行自动注册进 self.tools 的？把它前后各 3 行读出来给我看。"
    print(f"问题: {task}\n动作空间: {sorted(agent.tools)}\n")
    print("最终答案:", str(agent.run(task)))
