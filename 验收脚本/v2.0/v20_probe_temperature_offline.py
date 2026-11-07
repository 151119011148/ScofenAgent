# -*- coding: utf-8 -*-
"""S1(c) 的零网络复验：AGENT_TEMPERATURE 这条活口三件事，一发请求都不发。

跑法（子进程各起一次，env 单独给）：
  cd smolagents && ./.venv/bin/python ../验收脚本/v2.0/v20_probe_temperature_offline.py

要证明的三件事：
  1. 不设 → MODEL_TEMPERATURE == 0.0，且请求体里真的带 temperature=0.0
     —— "进了 self.kwargs" 只能证明到了对象上，把 client.create 换成记录用的假函数才看得到载荷；
  2. 设 0.7 → 载荷跟着变 0.7（活口是通的，不是只读不用的装饰）；
  3. 设 banana → 导入阶段就 ValueError 退出，**不会**悄悄退回 0.0。
     第 3 条是这条活口唯一真正危险的地方：拼错一个字母就静默回默认，
     然后拿着"锁过温"的口径去解释一份其实没锁的读数。

故意用 http://127.0.0.1:1/v1 当 base_url：就算哪一步没被 fake 拦住，也是立刻 connection refused，
不会走到服务商那里去花钱。（和同目录那份 v20_slow_server.py 是同一口径，2026-11-07 两份一起
挪出 run/——run/ 按约定只放产物，脚本放里面等于「仓库里没有、文档却指着」。）
"""

import os
import subprocess
import sys

SMOL = os.path.expanduser("~/Desktop/study/ai学习/smolagents")

CHILD = r'''
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
import my_coding_agent as mc

print("MODEL_TEMPERATURE=%r" % (mc.MODEL_TEMPERATURE,))
from smolagents import OpenAIServerModel
m = OpenAIServerModel(model_id="no-such-model", api_base="http://127.0.0.1:1/v1",
                      **mc.MODEL_GENERATION_KWARGS)
cap = {}
def fake(**kw):
    cap.update(kw)
    raise RuntimeError("no-net")
m.client.chat.completions.create = fake
try:
    m.generate([{"role": "user", "content": "hi"}])
except Exception:
    pass
print("payload.temperature=%r" % (cap.get("temperature"),))
print("payload.tool_choice=%r" % (cap.get("tool_choice"),))
'''

failures = []
cases = [
    ("不设（默认）", None, ["MODEL_TEMPERATURE=0.0", "payload.temperature=0.0"]),
    ("设 0.7", "0.7", ["MODEL_TEMPERATURE=0.7", "payload.temperature=0.7"]),
    ("设 banana（坏值）", "banana", ["could not convert string to float: 'banana'"]),
]

for label, raw, expects in cases:
    env = {k: v for k, v in os.environ.items() if k != "AGENT_TEMPERATURE"}
    if raw is not None:
        env["AGENT_TEMPERATURE"] = raw
    r = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True,
                       env=env, cwd=SMOL, timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    hit = [e for e in expects if e in out]
    if raw == "banana":
        good = r.returncode != 0 and hit == expects
    else:
        good = r.returncode == 0 and hit == expects
    print("%-18s rc=%s %s" % (label, r.returncode, "PASS" if good else "FAIL"))
    if not good:
        failures.append(label)
        print("  期望 %s\n  实际输出:\n%s" % (expects, out.strip()[-600:]))

print("\n%s" % ("全部通过（0 发网络请求）" if not failures else "失败：%s" % failures))
sys.exit(1 if failures else 0)
