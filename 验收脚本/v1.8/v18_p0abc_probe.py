# -*- coding: utf-8 -*-
"""P0-a／P0-c 的实跑对照：同一道 21:06 的题，旧代码一遍、新代码一遍，看模型撞墙之后干什么。

为什么要实跑：这三处全是**给模型读的文案**，离线闸只能证明「判定没变、字在不在」，
证明不了模型读完这些字之后少走了几步弯路。21:06 那轮的实际走向（证据 ai学习/.agent-ui.log）：
  · run A「删除人生目录下的轻量文档文件夹，职业规划下面的东西不要动」：
    Step1 list_dir('人生/') → 旧 FileNotFoundError → Step3 **同名同参**再打一遍 →
    中间 list_dir({}) 打了 3 次 → Step7 又撞 职业规划/ → 8 步用满、Reached max steps 交不出答案。
  · run B 开头带绝对路径 /Users/gaoying/Desktop/study/人生：Step1 撞越界 → Step3 交答案，
    答案是「请联系系统管理员调整权限」——本机没有这个开关，那是旧越界文案没指路时它自己补的。

用法（**两个进程各跑一遍**，别在一个进程里 import 两次同名模块）：
    smolagents/.venv/bin/python 验收脚本/v1.8/v18_p0abc_probe.py <old|new> <A|B>
  old 走 `.rollback/v1.8/after-p04/` 那份代码，new 走 `smolagents/` 当前这份。
规划关着跑（planning_interval=None）：这一刀和 P0-4 无关，两边同档才好比。

落盘：run/v18_p0abc_<old|new>_<A|B>.out（每跑一份，含步序、token、final answer 全文）
"""
import importlib.util
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
SMOL = "/Users/gaoying/Desktop/study/ai学习/smolagents"
OLD = str(pathlib.Path(SMOL) / ".rollback" / "v1.8" / "after-p04")

TASKS = {
    "A": "删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动",
    "B": "/Users/gaoying/Desktop/study/人生。删除人生目录下的 轻量文档文件夹，职业规划下面的东西不要动",
}

which, tag = sys.argv[1], sys.argv[2]
sys.path.insert(0, OLD if which == "old" else SMOL)
import my_agent  # noqa: E402

agent = my_agent.agent
agent.planning_interval = None          # 两边同档：这一刀不比规划
task = TASKS[tag]
print("=== %s / task %s ===" % (which, tag))
print("代码目录:", OLD if which == "old" else SMOL)
print("任务:", task)
print("动作空间:", sorted(agent.tools))
t0 = time.time()
try:
    ans = agent.run(task)
except BaseException as exc:  # noqa: BLE001
    ans = "<<异常>> %s: %s" % (type(exc).__name__, str(exc)[:300])
wall = time.time() - t0

rows = []
for st in agent.memory.steps:
    cls = type(st).__name__
    if cls == "ActionStep":
        # 这一版字段名按 src/smolagents/memory.py:51-64 抄：observations / action_output / is_final_answer。
        # 上一版这里写成 st.output（那是 CodeAgent 那侧的叫法），探针在算完账之前崩了，
        # 四次实跑的 token 白花了一半——记一笔：**digest 只许读数据类里真有的字段，先用 getattr 兜**。
        err = None if st.error is None else str(st.error)
        obs = getattr(st, "observations", None)
        # Timing 上是 `duration` 属性（monitoring.py:58-68），不是 total_time——探针第二次就是崩在这，
        # 四跑的 token 又白花一次。这一段的教训同一个：**digest 里只许 getattr 兜着读**。
        tim = getattr(st, "timing", None)
        secs = getattr(tim, "duration", None) if tim is not None else None
        usage = getattr(st, "token_usage", None)
        rows.append({
            "step": st.step_number, "tool": st.tool_calls[0].name if st.tool_calls else None,
            "args": {k: v for k, v in (st.tool_calls[0].arguments.items() if st.tool_calls else {})},
            "ok": err is None, "err": (err[:400] if err else None),
            "obs": (str(obs)[:260] if obs is not None else None),
            "final": bool(getattr(st, "is_final_answer", False)),
            "in": getattr(usage, "input_tokens", None), "out": getattr(usage, "output_tokens", None),
            "secs": round(secs, 2) if secs is not None else None,
        })
    elif cls == "TaskStep":
        rows.append({"step": 0, "tool": "TASK", "task": str(st.task)[:200]})
    elif cls == "SystemPromptStep":
        rows.append({"tool": "SYSTEM", "chars": len(st.system_prompt)})
    else:
        rows.append({"tool": cls})

acts = [r for r in rows if r.get("tool") and r["tool"] not in ("TASK", "SYSTEM", "SystemPromptStep")]
sigs = [(r["tool"], json.dumps(r["args"], sort_keys=True, ensure_ascii=False)) for r in acts if r["tool"] not in (None, "TASK", "SYSTEM")]
dup = {s: sigs.count(s) for s in set(sigs) if sigs.count(s) > 1}
errs = [r for r in acts if not r["ok"]]
cum_in = sum(r["in"] or 0 for r in acts)   # or 0：字段读不到时不许把整段 digest 带崩
cum_out = sum(r["out"] or 0 for r in acts)
ans_s = str(ans)
print(json.dumps(rows, ensure_ascii=False, indent=1))
print("--- 读数 ---")
print("耗时 %.1fs ｜ 撞 max_steps=%s" % (wall, "Reached max steps" in ans_s or len(acts) >= agent.max_steps))
print("动作数=%d 撞墙=%d 同名同参重复=%s" % (len(acts), len(errs), json.dumps(dup, ensure_ascii=False)))
print("步序:", " ".join("%s(%s)" % (r["tool"], "√" if r["ok"] else "×") for r in acts))
print("单步 in/out:", [ "%s/%s" % (r["in"], r["out"]) for r in acts ])
print("累计口径（各步 in 相加，含被重发的历史）: in=%s out=%s" % (cum_in, cum_out))
try:  # 监控器是**进程级、跨 run 累计**的（同一 agent 对象连着跑好几题会一直往上加），所以只当参照
    print("监控器读数(跨 run 累计口径): %s" % (agent.monitor.get_total_usage(),))
except BaseException as exc:  # noqa: BLE001
    print("监控器读数: 读不到 %s" % type(exc).__name__)
print("final answer 全文:")
print(ans_s)
print("--- 文案命中 ---")
for kw in ["系统管理员", "终端", "删除", "根外", "越界"]:
    print("  final answer 含「%s」: %s" % (kw, kw in ans_s))
print("  撞墙报错里出现新口径（相对路径解释那句话）: %s" % any("我只能把它接到白名单根" in (r["err"] or "") for r in errs))
print("  撞墙报错里出现新指路（没有删除、移动、重命名）: %s" % any("没有删除、移动、重命名" in (r["err"] or "") for r in errs))
