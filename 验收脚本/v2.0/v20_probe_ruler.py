# -*- coding: utf-8 -*-
"""S2：给评测尺子换一只「还有整份额度、且用完即停是开的」模型。

为什么要换（证据：验收脚本/v2.0/run/v20_eval_baseline.json 的口径段）：
  2026-11-06 那份基线打的是 tongyi-xiaomi-analysis-flash，一份全量走掉 401,273 in / 17,599 out，
  到 18:45 那只模型只剩 411.72K——**再打一份全量就越界**，而那只模型的「用完即停」是**关**的，
  越界直接转后付费。所以在这只模型上重跑全量不是"贵一点"，是"会开始产生账单"。

这一份挑候选的硬条件（按重要性排）：
  1. 免费额度**整份 1M 没用过**——全量一份估 475K（34 次 run，比 30 次那份多 4 次），留一倍余量；
  2. **用完即停 = 开**（控制台那格 switch aria-checked=true）。这条是 0 元的**结构保证**：
     额度打完服务商直接停（403），而不是继续记账。没有它，"预估 0 元"只是预估。
  3. 通用对话模型，不是垂直模型——垂直小蜜模型的 72.2% 只代表它自己，换脑要能说清换成了谁。
  4. 支持 `tool_choice="required"`：ToolCallingAgent 每一发都强制 required（agents.py 那条
     stop_sequences + tools_to_call_from 路径），不支持的模型在第一发就 400，整题跑不起来。
     **这一条只能实测**，文档里写"支持 function calling"和"接受 required"不是一回事。

跑法（**会真调模型**，每只 1 发 1-token 自检；支持性那一档每题多几发小请求）：
    cd ~/Desktop/study/ai学习/smolagents
    ./.venv/bin/python ../验收脚本/v2.0/v20_probe_ruler.py               # 全候选 × 两档
    ./.venv/bin/python ../验收脚本/v2.0/v20_probe_ruler.py --preflight   # 只打 1-token 自检
    ./.venv/bin/python ../验收脚本/v2.0/v20_probe_ruler.py --only qwen-max,glm-5.1
产物：run/v20_probe_ruler_<tag>.json（每只的 rc / 错误原文 / 支持性 / 用量）
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = Path.home() / "Desktop/study/ai学习/smolagents"

# 候选名单 + 两只对照。控制台读数取自 2026-11-07 00:20 那一屏（免费额度页，北京）：
# 下面 7 只全是「剩 1M / 共 1M、到期 2027/01/27、状态已开启、用完即停 switch=true」。
# 对照旧尺子那只的 switch 是 **false**——这就是为什么它不能再用第二次。
CANDIDATES = [
    "qwen-max", "qwen3.7-plus", "glm-5.1", "glm-5",
    "qwen3.5-122b-a10b", "qwen3.5-plus-2026-02-15", "qwen3.7-max-2026-06-08",
]
CONTROLS = ["qwen-plus", "tongyi-xiaomi-analysis-flash"]

PREFLIGHT = r'''
# -*- coding: utf-8 -*-
import json, sys, time
sys.path.insert(0, ".")
import my_agent
out = {"model": my_agent.agent.model.model_id}
t0 = time.time()
try:
    r = my_agent.agent.model.client.chat.completions.create(
        model=my_agent.agent.model.model_id,
        messages=[{"role": "user", "content": "ping"}], max_tokens=1)
    out["preflight"] = "ok"
    u = getattr(r, "usage", None)
    out["usage"] = (u.model_dump() if hasattr(u, "model_dump")
                    else (dict(u) if isinstance(u, dict) else str(u))) if u else None
except Exception as e:
    out["preflight"] = "FAIL"
    out["error"] = " ".join(str(e).split())[:300]
out["lat_s"] = round(time.time() - t0, 2)
print("@@" + json.dumps(out, ensure_ascii=False))
'''

TOOLS_OK = r'''
# -*- coding: utf-8 -*-
import json, sys, time
sys.path.insert(0, ".")
import my_agent
from smolagents import ChatMessage
m = my_agent.agent.model
tools = [t for t in my_agent.agent.tools.values()]
out = {"model": m.model_id, "n_tools": len(tools)}
t0 = time.time()
try:
    cm = m.generate(
        [ChatMessage(role="user", content="12.80, 13.42 这两个数里哪个大？用工具回答。")],
        stop_sequences=["Observation:"],
        tools_to_call_from=tools)
    out["tool_required"] = "ok"
    out["tool_calls"] = [tc.function.name for tc in (cm.tool_calls or [])]
    u = getattr(cm, "token_usage", None)
    out["usage"] = {k: getattr(u, k, None) for k in ("input_tokens", "output_tokens", "total_tokens")} if u else None
except Exception as e:
    out["tool_required"] = "FAIL"
    out["error"] = " ".join(str(e).split())[:400]
out["lat_s"] = round(time.time() - t0, 2)
print("@@" + json.dumps(out, ensure_ascii=False))
'''


def run_child(code: str, model_id: str, timeout: int = 120) -> dict:
    env = dict(os.environ, AGENT_MODEL_ID=model_id)
    env.pop("AGENT_TEMPERATURE", None)  # 候选探测走默认锁温，别被外层环境污染
    r = subprocess.run([str(SMOL / ".venv/bin/python"), "-c", code], capture_output=True,
                       text=True, env=env, cwd=str(SMOL), timeout=timeout)
    for line in reversed((r.stdout or "").splitlines()):
        if line.startswith("@@"):
            try:
                return json.loads(line[2:])
            except json.JSONDecodeError:
                pass
    return {"crash": True, "rc": r.returncode,
           "error": " ".join((r.stderr or r.stdout or "").split())[-400:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="candidates")
    ap.add_argument("--preflight", action="store_true", help="只打 1-token 自检，不发工具那发")
    ap.add_argument("--only", default="", help="逗号分隔的模型名，默认全候选＋两只对照")
    a = ap.parse_args()

    ids = [x.strip() for x in a.only.split(",") if x.strip()] or (CANDIDATES + CONTROLS)
    out = {"meta": {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tag": a.tag,
                    "ids": ids, "preflight_only": a.preflight,
                    "base_url": os.environ.get("AGENT_BASE_URL") or "(.env/默认 dashscope)"},
           "results": []}
    for mid in ids:
        rec = {"model_id": mid}
        rec["preflight"] = run_child(PREFLIGHT, mid)
        if not a.preflight and rec["preflight"].get("preflight") == "ok":
            rec["tool_required"] = run_child(TOOLS_OK, mid, timeout=180)
        elif not a.preflight:
            rec["tool_required"] = {"skipped": "自检没过，不发工具那一发"}
        out["results"].append(rec)
        pf, tr = rec["preflight"], rec.get("tool_required", {})
        print("%-30s 自检=%-6s %-58s 工具required=%-6s %s" % (
            mid, pf.get("preflight"), (pf.get("error") or "")[:58],
            tr.get("tool_required", tr.get("skipped", "-")), (tr.get("error") or "")[:60]))

    RUN.mkdir(exist_ok=True)
    path = RUN / ("v20_probe_ruler_%s.json" % a.tag)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n→ %s（%d 只）" % (path, len(out["results"])))


if __name__ == "__main__":
    main()
