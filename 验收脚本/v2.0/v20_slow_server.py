# -*- coding: utf-8 -*-
"""只给评测用的假 MCP server：一只 nap 工具，睡够再回。用来量客户端侧超时到底管不管用。"""
import time
from mcp.server.fastmcp import FastMCP

m = FastMCP("v20-slow")


@m.tool()
def nap(seconds: int = 30) -> str:
    """睡 seconds 秒再返回，模拟一个卡住的外部工具。"""
    time.sleep(seconds)
    return f"woke after {seconds}s"


m.run(transport="stdio")
