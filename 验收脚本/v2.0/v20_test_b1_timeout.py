# -*- coding: utf-8 -*-
"""B1 的离线断言：模型超时/重试真的落地了吗。不打付费接口、不起界面、不碰真库。

两组：
  静态组：活对象 `my_agent.model.client` 上的 timeout/max_retries 是不是我们写的那两个数，
          以及「改前有多糟」——用 openai SDK 自己的 DEFAULT_TIMEOUT 和框架的 retry 谓词作证。
  注入组：本机起一个「收下请求、永远不回答」的黑洞服务，把 api_base 指过去，
          量**真的多久报错**。非流式和流式两条路都要断（界面走的是流式）。
          注入用 timeout=1.0，1 秒量一次机制；再用 max_retries=2 复现「挂三次」那种放大。

跑法：smolagents/.venv/bin/python 验收脚本/v2.0/v20_test_b1_timeout.py
退出码 0 = 全绿。全程 < 15 秒。
"""
import socket
import sys
import threading
import time

sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")

import openai  # noqa: E402
from smolagents.models import OpenAIServerModel, is_rate_limit_error  # noqa: E402

import my_coding_agent as mca  # noqa: E402
from my_agent import agent, model  # noqa: E402

FAIL = []
N = 0


def ok(n, cond, detail=""):
    global N
    N += 1
    print("%-38s %s %s" % (n, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(n)


class Blackhole:
    """accept 之后一个字都不回。记录连接数和请求首行，供「重试了几次」用。"""

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(8)
        self.port = self.s.getsockname()[1]
        self.conns, self.lines, self.stop = [], [], False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        while not self.stop:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            self.conns.append(c)
            try:
                c.settimeout(0.5)
                data = b""
                while b"\r\n" not in data:
                    chunk = c.recv(2048)
                    if not chunk:
                        break
                    data += chunk
                self.lines.append(data.split(b"\r\n")[0].decode(errors="replace"))
            except OSError:
                self.lines.append("(no first line)")
            # 关键：不 recv 也不 close，让客户端只能等到自己的 read timeout。

    def halt(self):
        self.stop = True
        for c in self.conns:
            try:
                c.close()
            except OSError:
                pass
        self.s.close()


def mkmodel(bh, **ck):
    return OpenAIServerModel(
        model_id="does-not-matter",
        api_base=f"http://127.0.0.1:{bh.port}",
        api_key="sk-not-a-real-key",
        client_kwargs=ck,
    )


MSGS = [{"role": "user", "content": "ping"}]

# ---- 静态组：真对象上的读数 ----------------------------------------------
to = model.client.timeout
ok("B1-01 活 model 的 read 超时=60s", getattr(to, "read", None) == 60.0, repr(to))
ok("B1-02 connect 仍是 5s（没被我顺手放宽）", getattr(to, "connect", None) == 5.0)
ok("B1-03 活 model 的 max_retries=2", model.client.max_retries == 2,
   f"实际 {model.client.max_retries}")
ok("B1-04 常量读数",
   mca.MODEL_TIMEOUT_S == 60.0 and mca.MODEL_CONNECT_TIMEOUT_S == 5.0
   and mca.MODEL_MAX_RETRIES == 2
   and mca.MODEL_CLIENT_KWARGS["max_retries"] == 2
   and mca.MODEL_CLIENT_KWARGS["timeout"].read == 60.0)
ok("B1-05 my_agent 用的是同一份常量",
   model.client_kwargs["timeout"] is mca.MODEL_CLIENT_KWARGS["timeout"]
   and model.client_kwargs["max_retries"] == mca.MODEL_MAX_RETRIES,
   str({k: v for k, v in model.client_kwargs.items() if k in ("timeout", "max_retries")}))
sub = mca.build_agent()
ok("B1-06 my_coding_agent 那一路也带上刹车",
   sub.model.client.timeout.read == 60.0 and sub.model.client.max_retries == 2)
sub.model.client.close()

# 改前有多糟：不是估的，是 SDK 自己写的默认值。
ok("B1-07 改前默认 read=600s（这就是那半小时）",
   openai._constants.DEFAULT_TIMEOUT.read == 600.0, repr(openai._constants.DEFAULT_TIMEOUT))
plain = openai.OpenAI(api_key="sk-nope", base_url="http://127.0.0.1:1")
ok("B1-08 不写 client_kwargs 时 SDK 默认 max_retries=2（共三次尝试）",
   plain.max_retries == 2, f"实际 {plain.max_retries}")
plain.close()
ok("B1-09 框架 retryer 不重试超时", is_rate_limit_error(openai.APITimeoutError(request=None)) is False)
ok("B1-10 框架 retryer 管的是 429",
   is_rate_limit_error(RuntimeError("Error code: 429 - Rate limit reached")) is True)
ok("B1-11 retryer 读数（3 次 / 60s 间隔）只作用于限流",
   agent.model.retryer.max_attempts == 3 and agent.model.retryer.wait_seconds == 60)

# ---- 注入组：真的多久报错 ---------------------------------------------------
bh = Blackhole()
try:
    m = mkmodel(bh, timeout=1.0, max_retries=0)
    t0 = time.time()
    try:
        m.generate(MSGS)
        raised = None
    except Exception as e:  # noqa: BLE001
        raised = e
    el = time.time() - t0
    ok("B1-12 非流式：挂住的请求会自己死", isinstance(raised, openai.APITimeoutError),
       f"{type(raised).__name__}: {str(raised)[:60]}")
    ok("B1-13 用的就是我给的 1 秒（不是 600 秒）", 0.9 <= el <= 3.0, f"耗时 {el:.2f}s")
    ok("B1-14 max_retries=0 → 只打了一次", len(bh.conns) == 1, f"连接 {len(bh.conns)}")
    ok("B1-15 请求确实到了 /v1/chat/completions",
       any("/chat/completions" in ln for ln in bh.lines), str(bh.lines)[:80])
    m.client.close()

    # 流式：界面走的就是这一条（agent.stream_outputs=True → generate_stream）。
    bh2 = Blackhole()
    m2 = mkmodel(bh2, timeout=1.0, max_retries=0)
    t0 = time.time()
    try:
        for _ in m2.generate_stream(MSGS):
            pass
        raised = None
    except Exception as e:  # noqa: BLE001
        raised = e
    el2 = time.time() - t0
    ok("B1-16 流式同样自己死", isinstance(raised, openai.APITimeoutError),
       f"{type(raised).__name__}: {str(raised)[:60]}")
    ok("B1-17 流式耗时也在 1 秒档", 0.9 <= el2 <= 3.0, f"耗时 {el2:.2f}s")
    m2.client.close()
    bh2.halt()

    # 放大效应：同一黑洞 + 改前那个重试次数（2），看它打了几个连接、最后仍如实抛出。
    bh3 = Blackhole()
    m3 = mkmodel(bh3, timeout=1.0, max_retries=2)
    t0 = time.time()
    try:
        m3.generate(MSGS)
        raised3 = None
    except Exception as e:  # noqa: BLE001
        raised3 = e
    el3 = time.time() - t0
    ok("B1-18 重试到最后照样抛 APITimeoutError（不会静默成功）",
       isinstance(raised3, openai.APITimeoutError), f"{type(raised3).__name__}")
    ok("B1-19 max_retries=2 → 3 个连接、每个各等一个 read timeout",
       len(bh3.conns) == 3 and 2.6 <= el3 <= 4.5, f"连接 {len(bh3.conns)}、耗时 {el3:.2f}s")
    ok("B1-20 按改前 read=600 推：600s×3 = 30 分钟",
       openai._constants.DEFAULT_TIMEOUT.read * 3 == 1800.0)
    m3.client.close()
    bh3.halt()
finally:
    bh.halt()

print("\n%s  %d 条断言，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(0 if not FAIL else 1)
