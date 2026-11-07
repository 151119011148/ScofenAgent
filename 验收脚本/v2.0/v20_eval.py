# -*- coding: utf-8 -*-
"""E1 评测 runner：把 20 道题打一遍，产出可对比的数字。

跑法（**要真调模型，会花钱、会花时间**，每题一次完整 run）：
    cd ~/Desktop/study/ai学习/smolagents
    ./.venv/bin/python ../验收脚本/v2.0/v20_eval.py --dry          # 零调用：只列题和判定口径
    ./.venv/bin/python ../验收脚本/v2.0/v20_eval.py --ids 1,9,18    # 抽几题试跑，先确认脚本本身没坏
    ./.venv/bin/python ../验收脚本/v2.0/v20_eval.py --tag baseline  # 全量 → run/v20_eval_baseline.json

改前/改后对比（A1、B1 那些刀的证据都从这里出）：
    ./.venv/bin/python ../验收脚本/v2.0/v20_eval.py --tag with-mcp
    ./.venv/bin/python ../验收脚本/v2.0/v20_eval.py --against run/v20_eval_baseline.json --tag with-mcp

口径（写在这儿，免得日后对着数字吵架）：
  · 走的是 `from my_agent import agent` 那**同一个**单例——也就是界面在跑的这套配置
    （max_steps=8 / planning_interval=8 / 7 只工具）。换配置就是换尺子，别混着比。
  · **2026-11-06 那份 `--tag baseline` 的尺子不是界面默认模型**。账户状态门（#overdue-payment）
    把 qwen-plus 挡在门外，基线是命令行临时注入 `AGENT_MODEL_ID=tongyi-xiaomi-analysis-flash`
    打的（写进 `.env` 会让 UI 和另外几套套件跟着换脑，所以没写）。**这只模型是垂直小蜜分析模型**，
    那 72.2% 达标率只代表它自己。以后 A1／B1 的对比必须用同一条注入命令，别拿 qwen-plus 复跑一遍
    再和这份比——那是在比两个脑子。产物 `meta["model"]` 里就记着这一发是谁打的。
    花费：30 次 run 共 in 401,273 / out 17,599 token，全从该模型 100 万免费额度里扣，
    控制台「费用成本」页总消费跑前跑后都是 ￥0.06（0 元，实测不是推断）。
    剩余额度到 2026-11-06 18:45 是 411.72K，到 2026-11-07 00:25 只剩 **148.87K**——中间这 263K
    是上面那两个探针吃掉的，账能对上：det-t0 两发 48,490 ＋ arms4 八发 in/out 合计 178,213
    ＋ arms4 里那对 Q9 determinism 31,575 ＝ 258,278，余下几 K 是今天这发的工具探针。
    **不是别人在用这台账户**。现在再打一份全量必然越界，而这只模型的
    「免费额度用完即停」是**关**的（控制台那格 switch `aria-checked=false`），越界即转后付费：
    官方价 输入 0.2 元/百万、输出 0.4 元/百万，按这个差量算约 ￥0.002 级别，但**会开始产生账单**。
  · **不带审批门**。界面的 _install_gate 是 OpsUI 挂在实例上的，评测直接调裸 agent，
    所以这里量的「非法调用」是模型**想**干什么，含那些界面会拦下来的调用。
  · 每题 `reset=True`：memory 和 monitor 都清零，题与题之间不互相抬 token。
  · 缺口题（cls=gap）基线就该失败，汇总里单列，不进达标率分母。

两份后来量出来的读数（都在这把尺子上，2026-11-07 记）：

  · **温度：锁了，但它不解决一致性问题（负结果）**。P1-4 之后构造点默认带 temperature=0.0，
    同一道 Q9 在**同一个 0.0 下**跑了两次「跑两遍逐字节比」：
      run/v20_probe_planning_det-t0.json → 轨迹／答复／判分三格全同（token 24342 vs 24148）
      run/v20_probe_planning_arms4.json 的 determinism 段 → 轨迹**不同**、判分**不同**
                                          （token 24260 vs 7315，first_diff 在第 1 次调用）
    四次尝试、三种轨迹、两种判分。所以本文件的「一致性」那一栏**仍然只能靠 repeat 多跑来量**，
    不能因为代码里写了 0.0 就当它是可复现的尺子。活口：`AGENT_TEMPERATURE`（不设=0.0；
    坏值在导入阶段直接报错，不会静默退回默认——这点由 v20_probe_temperature_offline.py
    零网络复验，它把 client.create 换成假函数看请求载荷）。
  · **planning_interval 是这份尺子上最贵的一格**。同 4 题两臂对照（run/v20_probe_planning_arms4.json，
    planning=8 vs planning=None）：输入 token 100,963 → 71,258（**-29.4%**），墙钟 29.0s → 23.1s
    （-20.3%），单题最省的是 Q12（41,562 → 15,526，-62%）；达标 4 → 3，**唯一一次翻转落在 Q16**
    （拒绝类，措辞没命中 must_any）。这条翻转不是"规划让门禁变松"，是那一题本来就不稳——
    所以 **repeat 名单从 5 道扩到 7 道（加了 Q15、Q16）**，全量跑次从 30 变 **34**
    （7×3 + 13×1）；别把这份 34 次的汇总和上面 30 次那份直接相减当差值用。
  · **2026-11-07 想换尺子换不成，卡点是账户状态门，不是额度**。候选探测见
    run/v20_probe_ruler_candidates.json：qwen-max／qwen3.7-plus／glm-5／glm-5.1／
    qwen3.5-122b-a10b／qwen3.5-plus-2026-02-15／qwen3.7-max-2026-06-08／qwen-plus
    **八只 1-token 自检全部 400 `#overdue-payment`**，只有 tongyi-xiaomi-analysis-flash 通。
    阿里云「费用与成本/首页」当时的读数是 账户可用额度 **¥-0.05（已欠费）**、总待还款 ¥0。
    所以「状态门是按 commodity 行分的」这个 11-06 的判断要修正为：**垂直那条行不在停服名单里，
    通用大语言模型那几条全被挡**（为什么它不被挡【待确认】，最像的解释是它按 0 元计费、没有可欠的账单）。
    这同时说明：结清欠费之前，**任何**换模型的全量基线都打不出来，和额度剩多少无关。
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = Path.home() / "Desktop/study/ai学习/smolagents"

sys.path.insert(0, str(HERE))
from v20_questions import QUESTIONS  # noqa: E402


# ---- 判定 ------------------------------------------------------------------
NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def numbers(text: str) -> list[float]:
    """从答案里抠数。逗号先去掉，否则 18,446,744,073 会裂成三段。"""
    out = []
    for m in NUM_RE.findall(text.replace(",", "")):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out


def check(q: dict, answer: str, calls: list[str]) -> dict:
    """按 v20_questions 里那套字段判定这一题达没达标。返回逐条理由，不只给 bool。"""
    reasons, met = [], True
    dyn = q.get("must_dyn")
    must = list(q.get("must", [])) + ([dyn()] if callable(dyn) else [])
    for s in must:
        if s not in answer:
            met = False
            reasons.append(f"缺 must:{s!r}")
    if q.get("must_any") and not any(s in answer for s in q["must_any"]):
        met = False
        reasons.append(f"must_any 一个没中（候选 {q['must_any']}）")
    for target, tol in q.get("nums", []):
        ns = numbers(answer)
        # 容差判绝对值：回撤 -17.71% 常被模型写成「17.71% 的回撤」，符号在文字里。
        if not any(abs(abs(n) - abs(target)) <= tol for n in ns):
            met = False
            reasons.append(f"数值对不上：期望 {target}±{tol}，答案里的数 {ns[:12]}")
    for t in q.get("call", []):
        if t not in calls:
            met = False
            reasons.append(f"没调用 {t}")
    for t in q.get("forbid", []):
        if t in calls:
            met = False
            reasons.append(f"不该调用 {t}（调了 {calls.count(t)} 次）")
    if q.get("calls_zero") and calls:
        met = False
        reasons.append(f"不该动手，实际调了 {calls}")
    return {"met": met, "why": reasons}


# ---- 单题执行 ---------------------------------------------------------------
def one_run(agent, q: dict, attempt: int) -> dict:
    t0 = time.time()
    rec = {"qid": q["id"], "cls": q["cls"], "attempt": attempt, "q": q["q"], "gap": bool(q.get("gap"))}
    try:
        res = agent.run(q["q"], stream=False, reset=True, return_full_result=True)
        rec["status"] = {"success": "ok", "max_steps_error": "max_steps"}.get(
            str(getattr(res, "state", "") or ""), "unknown")
        rec["answer"] = str(res.output if hasattr(res, "output") else res)
    except Exception as e:  # noqa: BLE001 —— 评测要把炸掉的那一下如实记下来，不能让它带走整轮
        rec["status"] = "exception"
        rec["exc_type"] = type(e).__name__
        rec["exc"] = str(e)[:600]
        rec["traceback"] = traceback.format_exc(limit=6)
        rec["answer"] = ""
    rec["latency_s"] = round(time.time() - t0, 2)

    # 步级读数：从 agent.memory 里现取（run 已经跑完，这里只是回读，不再调模型）。
    steps = list(agent.memory.steps)
    rec["steps"] = {
        "action": sum(1 for s in steps if type(s).__name__ == "ActionStep"),
        "planning": sum(1 for s in steps if type(s).__name__ == "PlanningStep"),
    }
    calls, errs, tok_in, tok_out = [], [], 0, 0
    for s in steps:
        tu = getattr(s, "token_usage", None)
        if tu:
            tok_in += tu.input_tokens
            tok_out += tu.output_tokens
        for tc in (getattr(s, "tool_calls", None) or []):
            calls.append({"step": getattr(s, "step_number", None), "name": tc.name,
                          "args": json.dumps(tc.arguments, ensure_ascii=False, default=str)[:220]})
        err = getattr(s, "error", None)
        if err is not None and rec["status"] != "max_steps":
            errs.append(f"{type(err).__name__}: {str(err)[:200]}")
        obs = getattr(s, "observations", None) or ""
        for m in re.finditer(r"Unknown tool ([\w\-]+)", obs):
            errs.append(f"UnknownTool: {m.group(1)}")
    rec["tokens"] = {"input": tok_in, "output": tok_out}
    rec["tool_calls"] = calls
    rec["errors"] = errs
    rec["check"] = check(q, rec["answer"], [c["name"] for c in calls if c["name"] != "final_answer"])
    return rec


# ---- 汇总 -------------------------------------------------------------------
def pctl(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 2)


def summarize(runs: list[dict], repeat: int) -> dict:
    """同一条题跑多次时，主指标只算 attempt==1，否则「20 题」的分母会变成 26 次跑动。"""
    main = [r for r in runs if r["attempt"] == 1]
    scored = [r for r in main if not r["gap"]]
    gaps = [r for r in main if r["gap"]]
    calls = sum(len(r["tool_calls"]) for r in main)
    unknown = sum(1 for r in main for e in r["errors"] if e.startswith("UnknownTool"))
    toolerr = sum(1 for r in main for e in r["errors"] if not e.startswith("UnknownTool"))
    lat = [r["latency_s"] for r in main]
    cons = {}
    if repeat > 1:
        by = {}
        for r in runs:
            by.setdefault(r["qid"], []).append(r)
        for qid, rs in sorted(by.items()):
            if len(rs) < 2:
                continue
            cons[qid] = {
                "n": len(rs),
                "same_outcome": len({(x["status"], x["check"]["met"]) for x in rs}) == 1,
                "statuses": [x["status"] for x in rs],
                "met": [x["check"]["met"] for x in rs],
            }
    ok = sum(1 for r in scored if r["status"] == "ok")
    met = sum(1 for r in scored if r["check"]["met"])
    return {
        "n_questions": len(main),
        "交答率": {"ok": ok, "of": len(scored),
                  "pct": round(100.0 * ok / len(scored), 1) if scored else None,
                  "note": "非 gap 题里，在 max_steps 内交出答案的比例（不看对不对）"},
        "达标率": {"met": met, "of": len(scored),
                  "pct": round(100.0 * met / len(scored), 1) if scored else None,
                  "note": "交答 且 期望核对通过"},
        "例外": {"exception": sum(1 for r in main if r["status"] == "exception"),
                 "max_steps": sum(1 for r in main if r["status"] == "max_steps")},
        "非法调用率": {"unknown_tool": unknown, "tool_errors": toolerr, "calls": calls,
                     "pct": round(100.0 * (unknown + toolerr) / calls, 1) if calls else None,
                     "note": "（调了不存在的工具 + 工具报错）/ 工具调用总次数"},
        "步数": {"mean_action": round(statistics.mean([r["steps"]["action"] for r in main]), 2) if main else None,
                 "max_action": max([r["steps"]["action"] for r in main], default=None),
                 "planning_runs": sum(1 for r in main if r["steps"]["planning"] > 0)},
        "token": {"in_total": sum(r["tokens"]["input"] for r in main),
                  "out_total": sum(r["tokens"]["output"] for r in main),
                  "in_mean": round(statistics.mean([r["tokens"]["input"] for r in main]), 0) if main else None,
                  "out_mean": round(statistics.mean([r["tokens"]["output"] for r in main]), 0) if main else None},
        "时延": {"p50": pctl(lat, 0.5), "p95": pctl(lat, 0.95),
                 "mean": round(statistics.mean(lat), 2) if lat else None,
                 "total_s": round(sum(lat), 1), "unit": "秒/题（整题 wall time）"},
        "缺口题": {"n": len(gaps), "ids": [r["qid"] for r in gaps],
                   "基线是否如实失败": {str(r["qid"]): r["check"]["met"] for r in gaps},
                   "note": "cls=gap 的题基线**应当**失败（A1 接完 MCP 后应翻绿），不计入达标率"},
        "一致性": {"repeat": repeat, "per_question": cons,
                   "稳定率": (f"{sum(1 for c in cons.values() if c['same_outcome'])}/{len(cons)}" if cons else "n/a"),
                   "note": "同一题跑 repeat 次，status 与达标都算同一个值才叫稳定"},
        "分档": {},
    }


def by_class(runs: list[dict]) -> dict:
    main = [r for r in runs if r["attempt"] == 1]
    out = {}
    for cls in sorted({r["cls"] for r in main}):
        rs = [r for r in main if r["cls"] == cls]
        out[cls] = {
            "n": len(rs), "ids": [r["qid"] for r in rs],
            "ok": sum(1 for r in rs if r["status"] == "ok"),
            "met": sum(1 for r in rs if r["check"]["met"]),
            "in_tok": sum(r["tokens"]["input"] for r in rs),
            "out_tok": sum(r["tokens"]["output"] for r in rs),
            "lat_s": round(sum(r["latency_s"] for r in rs), 1),
            "calls": sum(len(r["tool_calls"]) for r in rs),
        }
    return out


# ---- 对比（改前 / 改后） -----------------------------------------------------
def diff(base: dict, cur: dict) -> list[str]:
    lines = []
    keys = ["交答率", "达标率", "非法调用率", "步数", "token", "时延"]
    for k in keys:
        a, b = base["summary"].get(k, {}), cur["summary"].get(k, {})
        for f in a:
            if isinstance(a[f], (int, float)) and isinstance(b.get(f), (int, float)) and a[f] != b[f]:
                lines.append(f"{k}.{f}: {a[f]} -> {b[f]}  ({b[f] - a[f]:+g})")
    bm = {r["qid"]: r for r in base["runs"] if r["attempt"] == 1}
    cm = {r["qid"]: r for r in cur["runs"] if r["attempt"] == 1}
    for qid in sorted(set(bm) | set(cm)):
        a, b = bm.get(qid), cm.get(qid)
        if a is None or b is None:
            lines.append(f"Q{qid}: 只在一边跑过")
            continue
        flip = []
        if a["status"] != b["status"]:
            flip.append(f"status {a['status']}->{b['status']}")
        if a["check"]["met"] != b["check"]["met"]:
            flip.append(f"达标 {a['check']['met']}->{b['check']['met']}")
        if flip:
            lines.append(f"Q{qid}[{b['cls']}]: " + "; ".join(flip))
    return lines


# ---- 主流程 -----------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=time.strftime("%Y%m%d-%H%M%S"), help="产物文件名后缀")
    ap.add_argument("--ids", default="", help="只跑这些题号，逗号分隔；默认全 20 题")
    ap.add_argument("--repeat", type=int, default=3, help="打了 repeat 标记的题跑几次（一致性抽样）")
    ap.add_argument("--dry", action="store_true", help="零模型调用：只列题和判定口径")
    ap.add_argument("--against", default="", help="和这份基线 JSON 对比，输出改动前后差异")
    ap.add_argument("--out", default=str(RUN), help="产物目录")
    a = ap.parse_args()

    ids = {int(x) for x in a.ids.split(",") if x.strip()}
    qs = [q for q in QUESTIONS if not ids or q["id"] in ids]

    if a.against:
        cur = json.loads((Path(a.out) / f"v20_eval_{a.tag}.json").read_text(encoding="utf-8"))
        base = json.loads(Path(a.against).read_text(encoding="utf-8"))
        print(f"=== 对比：{a.against} → v20_eval_{a.tag}.json ===")
        ds = diff(base, cur)
        print("\n".join(ds) if ds else "  读数没有变化")
        return 0

    if a.dry:
        print(f"共 {len(qs)} 题。判定口径（不打模型）：")
        for q in qs:
            spec = []
            for f in ("must", "must_any", "nums", "call", "forbid", "calls_zero", "must_dyn", "gap", "repeat"):
                if q.get(f):
                    spec.append(f"{f}={q[f] if f != 'must_dyn' else q[f]()}")
            print(f"  Q{q['id']:<3}[{q['cls']:<8}] {json.dumps(spec, ensure_ascii=False, default=str)}\n      {q['q'][:70]}")
        return 0

    os.chdir(SMOL)
    sys.path.insert(0, str(SMOL))
    from my_agent import agent  # noqa: E402 —— 界面在跑的就是这一个对象

    meta = {
        "ts": time.strftime("%F %T"), "tag": a.tag, "cwd": str(SMOL),
        "model": f"{type(agent.model).__name__}/{agent.model.model_id}",
        "max_steps": agent.max_steps, "planning_interval": agent.planning_interval,
        "tools": sorted(agent.tools),
        "repeat": a.repeat, "n_runs": None,
        "gate": "off（裸 agent，不经界面审批门）",
    }
    print(f"配置：{meta['model']} · tools={len(meta['tools'])} · max_steps={meta['max_steps']} "
          f"· planning_interval={meta['planning_interval']}\n")

    runs = []
    # 预检：账号级错误（欠费／鉴权／风控）会让 26 次跑动全部空烧，第一次撞上就直接停。
    # 2026-11-04 就是这么发现的：`400 Access denied ... account is in good standing`。
    AUTH = re.compile(r"Access denied|api key|incorrect api|arrears|overdue|401|403|429", re.I)
    aborted = False
    for q in qs:
        if aborted:
            break
        n = a.repeat if (q.get("repeat") and a.repeat > 1) else 1
        for attempt in range(1, n + 1):
            r = one_run(agent, q, attempt)
            runs.append(r)
            flag = "✓" if r["check"]["met"] else ("○gap" if r["gap"] else "✗")
            print(f"Q{r['qid']:<3}[{r['cls']:<8}] a{attempt} {flag:<5} {r['status']:<10} "
                  f"{r['latency_s']:>6.1f}s in={r['tokens']['input']:<6} out={r['tokens']['output']:<5} "
                  f"步={r['steps']['action']} 调用={len(r['tool_calls'])}"
                  + ("" if r["check"]["met"] or r["gap"] else "  ← " + "; ".join(r["check"]["why"])))
            sys.stdout.flush()
            if r["status"] == "exception" and AUTH.search(r.get("exc", "")):
                print(f"\n!! 账号级错误，停止跑题（第一次出现在 Q{r['qid']}）：\n{r['exc'][:400]}\n"
                      "   这不是脚本或题目问题：模型侧拒了请求，跑完 20 题只会得到 20 份同一个异常。\n"
                      "   处理：把账号余额／风控恢复后复跑同一条命令即可，基线数字以复跑那份为准。")
                aborted = True
                break

    summary = summarize(runs, a.repeat)
    summary["分档"] = by_class(runs)
    meta["n_runs"] = len(runs)
    meta["aborted_by_auth_error"] = aborted
    out = {"meta": meta, "summary": summary, "runs": runs}

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    jp = outdir / f"v20_eval_{a.tag}.json"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    txt = json.dumps(summary, ensure_ascii=False, indent=1)
    (outdir / f"v20_eval_{a.tag}.summary.out").write_text(txt, encoding="utf-8")

    print("\n=== 汇总 ===\n" + txt)
    print(f"\n产物：{jp}")
    # 没交答的题把异常原文贴出来，否则下一轮无从判断是脚本坏了还是模型坏了
    for r in runs:
        if r["status"] == "exception":
            print(f"\n--- Q{r['qid']} 异常 ---\n{r['exc']}\n{r['traceback']}")
    return 2 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
