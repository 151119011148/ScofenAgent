# -*- coding: utf-8 -*-
"""P1-5 探针：每题一份计划到底值多少 token、买回多少达标。

为什么要打这一发（不是拍脑袋关参数）：
  · `my_agent.py:34-42` 那条注释记的是 **v1.8 的单题样本**：同一道 12 日行情题，规划开着
    in 13,591／关着 5,260，规划那一次单独 in 1,188 + out 1,458、占 40.1s 里的 32.9s。
    单题只能看量级，撑不起「要不要关」这个决定。
  · E1 全量基线（run/v20_eval_baseline.json，30 次 run）里 planning **20/20 全触发**，
    单题 in 均值 20,064、最高 60,364（Q12），每步 input 3.7K～6.7K——计划正文就在里面。
  · 这一刀和「9.3-8 内存模块只有 Buffer」「1.9 没有压缩函数」是同一件事的两面：
    窗口靠单点截断挡着，成本靠规划抬高。开关就在 planning_interval 这一个参数上。

跑法（**真调模型、真花额度**，两个 arm × 6 题 + 2 发确定性对照）：
    cd ~/Desktop/study/ai学习/smolagents
    ./.venv/bin/python ../验收脚本/v2.0/v20_probe_planning.py --tag p0
    ./.venv/bin/python ../验收脚本/v2.0/v20_probe_planning.py            # 只跑确定性对照，零预算风险

口径（和基线同一把尺子，别混着比）：
  · 判定走 `v20_eval.check`，函数就是基线那一个，不另写一套判分。
  · 题集默认 6 道：Q1／Q6／Q9／Q14 短轨迹、Q16／Q12 长轨迹（Q12 基线里就是撞顶那四题之一，
    单题 in 60,364 是这份基线最贵的一次）。两臂跑**同一批题**，所以差值是同题同参的差值。
    `--ids` 是给额度紧的时候裁的：2026-11-06 这一发用的是 `6,9,12,16`（4 题两臂 ≈20 万 token，
    留一半额度做后手），短长轨迹的对比靠 Q6 vs Q12 仍然成立。
  · **锁温之后 Q9 变脸了**（det-t0 实测：基线 2 步／7,312 → 锁温 6 步／24,342，两发轨迹逐字节相同，
    所以是系统性变化不是抖动）。这条决定了下面那一行口径：本探针的读数**不能**和
    2026-11-06 那份未锁温基线逐题比大小，只能两臂互比。
  · 每个 arm 现场改 `agent.planning_interval`（实例属性，框架每轮读它），改完必须改回：
    这份探针 import 的就是界面那同一个单例。
  · **温度锁定之后**的读数不能和 2026-11-06 那份基线直接比——那份是 temperature 吃服务端默认值
    时打的。两臂之间的对比不受影响，因为两臂都在锁温之后。
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = Path.home() / "Desktop/study/ai学习/smolagents"
IDS = [1, 6, 9, 14, 16, 12]
ARMS = (("planning=8", 8), ("planning=None", None))

sys.path.insert(0, str(HERE))
from v20_eval import check, one_run  # noqa: E402  判定与执行都复用基线那一份实现
from v20_questions import QUESTIONS  # noqa: E402


def summarize(runs: list[dict]) -> dict:
    by: dict[str, list[dict]] = {}
    for r in runs:
        by.setdefault(r["arm"], []).append(r)
    out = {}
    for arm, rs in by.items():
        out[arm] = {
            "n": len(rs),
            "met": sum(1 for r in rs if r["check"]["met"]),
            "ok": sum(1 for r in rs if r["status"] == "ok"),
            "in_total": sum(r["tokens"]["input"] for r in rs),
            "out_total": sum(r["tokens"]["output"] for r in rs),
            "in_mean": round(statistics.mean([r["tokens"]["input"] for r in rs]), 0),
            "planning_steps": sum(r["steps"]["planning"] for r in rs),
            "action_mean": round(statistics.mean([r["steps"]["action"] for r in rs]), 2),
            "lat_mean": round(statistics.mean([r["latency_s"] for r in rs]), 2),
            "lat_total_s": round(sum(r["latency_s"] for r in rs), 1),
            "per_question": {str(r["qid"]): {"in": r["tokens"]["input"], "out": r["tokens"]["output"],
                                             "action": r["steps"]["action"], "planning": r["steps"]["planning"],
                                             "met": r["check"]["met"], "status": r["status"],
                                             "why": r["check"]["why"]}
                             for r in rs},
        }
    if {"planning=8", "planning=None"} <= set(out):
        a, b = out["planning=8"], out["planning=None"]
        out["差值(None 相对 8)"] = {
            "in_total": b["in_total"] - a["in_total"],
            "in_pct": round(100.0 * (b["in_total"] - a["in_total"]) / a["in_total"], 1),
            # 时延按整臂求和再比：单题 lat_mean 会被「某一题恰好走弯路」带偏，
            # 而这一格想回答的是「关规划省不省墙钟时间」。
            "lat_total_s": {"planning=8": a["lat_total_s"], "planning=None": b["lat_total_s"],
                            "pct": round(100.0 * (b["lat_total_s"] - a["lat_total_s"]) / a["lat_total_s"], 1)
                                   if a["lat_total_s"] else None},
            "met": f'{a["met"]} -> {b["met"]}（{a["n"]} 题）',
            "逐题达标翻转": {qid: [a["per_question"][qid]["met"], b["per_question"][qid]["met"]]
                            for qid in a["per_question"]
                            if a["per_question"][qid]["met"] != b["per_question"][qid]["met"]},
        }
    return out


def determinism(agent, q, attempts: int) -> dict:
    """同一题连打两次，比**逐字节**：温度锁住之后，轨迹和答复文本都该一样。

    只比 status／met 不够——那正是基线里 Q9 翻红那一发露出来的洞：判分相同但中间走了不同的路，
    一样会在下一次改动里被算成「改动带来的变化」。
    """
    runs = [one_run(agent, q, i + 1) for i in range(attempts)]
    sig = [json.dumps([{"name": c["name"], "args": c["args"]} for c in r["tool_calls"]],
                      ensure_ascii=False, sort_keys=True) for r in runs]
    ans = [r["answer"] for r in runs]
    return {
        "qid": q["id"], "n": attempts,
        "轨迹逐字节相同": len(set(sig)) == 1,
        "答复逐字节相同": len(set(ans)) == 1,
        "判分相同": len({r["check"]["met"] for r in runs}) == 1,
        "token": [r["tokens"]["input"] for r in runs],
        "first_diff": (next((i for i in range(1, len(sig)) if sig[i] != sig[0]), None)),
        "why_per_attempt": [r["check"]["why"] for r in runs],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--det-only", action="store_true", help="只打确定性对照（2 次同一题），不跑两臂")
    ap.add_argument("--ids", default=",".join(str(i) for i in IDS),
                    help="跑哪些题；额度紧的时候按题号裁（默认 %s）" % IDS)
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",") if x.strip()]

    os.chdir(SMOL)
    sys.path.insert(0, str(SMOL))
    import my_agent  # noqa: E402  界面在跑的就是这一个单例

    agent = my_agent.agent
    qs = [q for q in QUESTIONS if q["id"] in ids]
    det_q = next(q for q in QUESTIONS if q["id"] == 9)
    saved = agent.planning_interval
    out = {"meta": {
        "ts": time.strftime("%F %T"), "tag": a.tag, "det_only": a.det_only,
        "model": f"{type(agent.model).__name__}/{agent.model.model_id}",
        "generation_kwargs": agent.model.kwargs,
        "max_steps": agent.max_steps, "planning_interval_before_probe": saved,
        "ids": ids, "arms": [k for k, _ in ARMS] if not a.det_only else [],
        "gate": "off（裸 agent，不经界面审批门）",
    }, "determinism": None, "runs": [], "summary": None}

    try:
        out["determinism"] = determinism(agent, det_q, 2)
        d = out["determinism"]
        print(f"确定性对照 Q{d['qid']} ×{d['n']}（planning_interval={agent.planning_interval}）："
              f"轨迹相同={d['轨迹逐字节相同']} 答复相同={d['答复逐字节相同']} 判分相同={d['判分相同']} "
              f"in={d['token']}")
        if a.det_only:
            out["summary"] = None
        else:
            rows = []
            for arm, interval in ARMS:
                agent.planning_interval = interval
                for q in qs:
                    r = one_run(agent, q, 1)
                    r["arm"] = arm
                    out["runs"].append(r)
                    rows.append(r)
                    print(f"{arm:<14} Q{r['qid']:<3}[{r['cls']:<8}] {'✓' if r['check']['met'] else '✗':<2} "
                          f"{r['status']:<10} 步={r['steps']['action']} 规划={r['steps']['planning']} "
                          f"in={r['tokens']['input']:<6} out={r['tokens']['output']:<5} {r['latency_s']:>5.1f}s"
                          + ("" if r["check"]["met"] else "  ← " + "; ".join(r["check"]["why"])[:110]))
                    sys.stdout.flush()
            out["summary"] = summarize(rows)
            print("\n=== 汇总 ===\n" + json.dumps(out["summary"], ensure_ascii=False, indent=1))
    finally:
        agent.planning_interval = saved
        print(f"\nplanning_interval 已还原为 {agent.planning_interval}")

    RUN.mkdir(parents=True, exist_ok=True)
    jp = RUN / f"v20_probe_planning_{a.tag}.json"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"产物：{jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
