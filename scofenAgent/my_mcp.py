# -*- coding: utf-8 -*-
"""A1＋A2：外部 MCP 工具进这台机器的**唯一**入口。

为什么不写在 my_agent.py 的模块层：MCP 连接是**运行时资源**（一条 stdio 子进程一个 server），
而 my_agent.py 是被 import 用的——my_ui、评测脚本、他的离线断言脚本都会 import 它。
写在模块层等于「任何人 import 一下就起两个子进程」，那些脚本一个都关不掉。
所以这里只给函数，由 OpsUI 在自己的生命周期里调（attach/detach），CLI 那条路不挂 MCP。

两道门（缺一不可，这就是 A1 和 A2 的分工）：
  1. **装载白名单**（本文件）：server 必须在 MCP_SERVERS 里逐条写死，工具必须逐个点名。
     server 上新长出来的工具、名字像破坏性的，一律不挂——白名单是「加进来的名单」，
     不是「黑名单的反面」。
  2. **运行时审批门**（my_ui._install_gate）：挂上的工具全部进审批名单，每次真调用都要人点
     「✔ 允许」。外部进程做的事不该由模型自己决定要不要做。

实测留痕（2026-11-04，验收脚本/v2.0/run/）：
  · 客户端这边 mcp 只能到 **1.30.0**：mcpadapt 0.1.20 要 `mcp[ws]`，而 mcp 2.3.0 既没有 `ws` 这个
    extra、也没有 `streamablehttp_client`（import 直接炸）。server 那边是 mcp 2.3，两边靠协议版本号
    握手，实测 tool list 与调用都通。
  · 官方 python server（time/fetch）拖 `pyjwt[crypto]` → `cryptography`，而 **49.0.0 起不再出
    Intel macOS 轮子**，这台 x86_64 上只能源码编译，cargo 退出 101。两个 server 的 .venv 都
    用 `cryptography<=48.0.1`（universal2 轮子覆盖 x86_64）单独装，不动上游的 pyproject/uv.lock。
  · fetch server **默认拒绝**私有/回环地址（自带 SSRF 护栏），所以这里不给它加 `--allow-private-ips`。
"""

import re
import shutil
from pathlib import Path

from mcp import StdioServerParameters
from smolagents.mcp_client import MCPClient

SERVERS_DIR = Path("~/Desktop/study/ai学习/servers/src").expanduser()

# 一次外部工具调用最多让 worker 等多久。这条是 B1 那个刹车在**外部工具**这一侧的对应物：
# 模型的超时管不到 MCP 调用，实测差距很硬——
#   · 走 mcpadapt 的默认值：抓 https://example.com 实测 **62.9 秒**才回来（默认值不生效）；
#   · 显式给 5 秒：同一条 URL 3.9 秒成功、第二次在 **5.0 秒**整抛出 McpError「Timed out」；
#   · 拿一个假 server（nap 工具睡 8 秒）验：timeout=2 时 2.0 秒就断，timeout=30 时 6 秒正常返回。
# 30 秒是「慢但还在 progress 的外部抓取」和「把界面钉死」之间给的口子，不是默认值。
MCP_CALL_TIMEOUT_S = 30.0

# 装载白名单：一个 server 一条，argv 用绝对路径（不靠 PATH、不在运行时猜命令）。
# tools 是**逐个点名**的清单，值是这个工具的风险档（写进审计与审批卡给人看）。
MCP_SERVERS = {
    "time": {
        "argv": [str(SERVERS_DIR / "time/.venv/bin/mcp-server-time")],
        "tools": {
            "get_current_time": "读，无副作用",
            "convert_time": "读，无副作用",
        },
    },
    "fetch": {
        "argv": [str(SERVERS_DIR / "fetch/.venv/bin/mcp-server-fetch")],
        "tools": {
            # 出网。正文会整段进模型上下文（max_length 默认 5,000 字符），所以每次都要人批。
            "fetch": "外部网络读；正文进上下文；server 自带 robots.txt 与私有地址拒绝",
        },
    },
}

# 明确**不挂**的，写下来而不是留白：将来有人顺手加一行之前，得先看到当初为什么不加。
REFUSED = {
    "filesystem": "带 delete_files/move_file/写任意允许路径——挂上之后 my_agent 里那句"
                  "「没有删除／移动／重命名能力」和 guarded() 给模型念的那段就成了假话。",
    "memory": "自己落一份 JSON 知识图谱，和 .agent-history.sqlite3 的 memory 表两套账（C 系列再说）。",
    "git": "能改仓库状态，且这一版上游是 python 包、没构建。",
    "sequentialthinking": "纯推理脚手架，不新增任何能力，只把每题 input 抬高。",
    "everything": "官方测试 server，工具名（echo/add…）是给人验协议用的，不是给用户用的。",
}

# 名字里带这些词的一律拒，哪怕它出现在上面的 tools 清单里：白名单管「谁被点名」，
# 这一条管「点名的人也别把删除类工具念进来」。
DESTRUCTIVE_RX = re.compile(
    r"del|remov|unlink|rmdir|truncate|drop|rename|move|write|edit|patch|apply|publish|revert|reset|format",
    re.I,
)


class Bridge:
    """一次 attach 的全部状态：连了谁、挂上了哪些工具、哪些没挂以及为什么。

    界面上「MCP: 2 server / 3 工具」那一格和审计里那行 provenance 都读这里。
    """

    def __init__(self):
        self.agent = None
        self.clients: dict[str, MCPClient] = {}
        self.added: dict[str, str] = {}  # 工具名 -> server 名
        self.skipped: dict[str, str] = {}  # server 名 -> 原因
        self.denied: list[str] = []  # 被白名单/破坏性/撞名挡下的工具名

    @property
    def gated(self) -> tuple:
        """这些名字要并进料审批门的名单（见 my_ui.OpsUI._install_gate）。"""
        return tuple(self.added)

    def describe(self) -> str:
        if not self.clients:
            if not self.skipped:
                return "未配置 server"
            return "未挂载：" + "、".join(f"{k}（{v}）" for k, v in self.skipped.items())
        parts = [f"{s}×{sum(1 for t in self.added.values() if t == s)}" for s in self.clients]
        if self.denied:
            parts.append(f"挡下 {len(self.denied)} 个工具")
        if self.skipped:
            parts.append("未装：" + "、".join(self.skipped))
        return "、".join(parts)


def attach(agent, servers: dict | None = None) -> Bridge:
    """连上白名单里的每个 server，把点名过的工具装进 agent.tools。

    幂等：同一个 agent 装第二次不会重连也不会重复装（OpsUI 在测试里会被反复实例化，
    而 agent 是进程里那**一个**单例）。
    """
    b = Bridge()
    b.agent = agent
    servers = MCP_SERVERS if servers is None else servers
    if getattr(agent, "_mcp_bridge", None) is not None:
        return agent._mcp_bridge

    for name, spec in servers.items():
        raw = spec["argv"][0]
        # 绝对路径就直接查；`node` / `npx` 这类要靠 PATH 找命令，不做这一步会把官方
        # filesystem server（argv 头一个是 node）当成「可执行文件不在」挡掉——2026-11-04 就红在这。
        exe = Path(raw)
        found = str(exe) if exe.is_absolute() and exe.exists() else shutil.which(raw)
        if not found:
            # 不抛：少了这个 server 不该让界面起不来。原因记下来，界面上如实讲。
            b.skipped[name] = f"可执行文件不在（{raw}）"
            continue
        try:
            client = MCPClient(
                StdioServerParameters(command=found, args=spec["argv"][1:]),
                adapter_kwargs={"client_session_timeout_seconds": MCP_CALL_TIMEOUT_S},
                structured_output=False,
            )
        except Exception as e:  # noqa: BLE001 —— server 起不来／握手失败都不能拖垮界面
            b.skipped[name] = f"{type(e).__name__}: {str(e)[:160]}"
            continue
        b.clients[name] = client
        for tool in client.get_tools():
            tag = f"{name}/{tool.name}"
            if tool.name not in spec["tools"]:
                b.denied.append(f"{tag}（不在点名清单）")
                continue
            if DESTRUCTIVE_RX.search(tool.name):
                b.denied.append(f"{tag}（名字含破坏性动词）")
                continue
            if tool.name in agent.tools:
                b.denied.append(f"{tag}（与已有工具撞名，不覆盖）")
                continue
            # provenance 贴在工具对象上：审批卡和审计行都要靠它说清「这不是我自己的手」。
            tool._mcp_server = name
            tool._mcp_risk = spec["tools"][tool.name]
            agent.tools[tool.name] = tool
            b.added[tool.name] = name

    agent._mcp_bridge = b
    if b.added:
        import atexit

        atexit.register(detach, b)
    return b


def detach(b: Bridge) -> None:
    """断开所有 server 连接（stdio 子进程跟着收），并把挂上的工具从 agent 上摘掉。

    摘工具这一步不能省：连接一断，工具对象还在 agent.tools 里的话，模型下一次就会
    照着清单往里发调用，然后撞在一个已经关掉的会话上——比「根本没有这只工具」难查得多。
    幂等，重复调不炸。
    """
    for name, client in list(b.clients.items()):
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001 —— 退出路径上不抛
            pass
    b.clients.clear()
    if b.agent is not None:
        for tool_name in b.added:
            b.agent.tools.pop(tool_name, None)
        if getattr(b.agent, "_mcp_bridge", None) is b:
            b.agent._mcp_bridge = None
    b.added.clear()
