# -*- coding: utf-8 -*-
"""D8 基线①的运行器：起一次最小 gradio 探针进程 → 用 CDP 按剧本走 → 收服务端日志。

用法：python v18_run_probe.py <A1|A2|A4> [approval_timeout]
产物：run/v18_probe_<tag>.log（服务端逐事件）＋ run/v18_cdp_<tag>.out（浏览器侧每步时刻）
      run/v18_summary_<tag>.out（两份对表之后的结论行）

四种时刻对表用的是探针自己打出来的 t0_epoch（服务端日志 t=0 那一瞬的 epoch 秒）。
"""
import base64
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
RUN.mkdir(exist_ok=True)
PORT = "7871"
URL = "http://127.0.0.1:%s" % PORT
# 探针必须用 smolagents 那个 venv 起（那里才有 gradio 6.30）；本机 python3 是 3.9，没装。
PROBE_PY = os.environ.get("V18_PY", "/Users/gaoying/Desktop/study/ai学习/smolagents/.venv/bin/python")

BTN = lambda label: ("(()=>Array.from(document.querySelectorAll('button'))"
                     ".find(b=>b.innerText.includes(%r)))()" % label)
SETQ = ("(()=>{const ta=document.querySelector('textarea');if(!ta)return 'NO-TEXTAREA';ta.focus();"
        "Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta,'这道题用来测断开');"
        "ta.dispatchEvent(new Event('input',{bubbles:true}));return 'set';})()")
FR = ("(()=>{const d=(document.querySelector('#main')||document.body).innerText;"
      "const m=d.match(/第\\s*(\\d+)\\s*帧/);return m?'YES frame='+m[1]:'NO frame=?';})()")

SCEN = {
    # 对照组：没人断开，3s 时自动点「允许」。这条用来证明日志里那两行（gen.finally / worker.exit）
    # 在正常路上确实会出现——不然 A2 里看不到它们就说明不了任何事。
    "A1": dict(auto_allow=True, reload_at=None, tail=14, note="对照：全程不断开，3s 自动允许"),
    # 主测：流式中途刷新页面（这就是 D8 的扳机）
    "A2": dict(auto_allow=False, reload_at=2.0, tail=34, note="中途刷新：流式第 ~6 帧时 reload，审批没人点"),
    # 次测：审批已经解开、worker 正在干活时刷新 —— 看「半截」这一路丢的是什么
    "A4": dict(auto_allow=True, reload_at=4.5, tail=16, note="允许之后（worker 在干活）再刷新"),
}


def run(tag, ap_timeout):
    s = SCEN[tag]
    log = RUN / ("v18_probe_%s.log" % tag)
    if log.exists():
        log.unlink()
    cmd = [PROBE_PY, str(HERE / "v18_probe_disconnect.py"), tag, PORT, str(ap_timeout)]
    if s["auto_allow"]:
        cmd.append("--auto-allow")
    out = open(RUN / ("v18_probe_%s.stdout" % tag), "w", encoding="utf-8")
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(60):
            time.sleep(1)
            if log.exists() and "boot" in log.read_text(encoding="utf-8"):
                break
        else:
            raise RuntimeError("探针进程 60s 没起来")

        steps = [{"name": "S1-set", "expr": base64.b64encode(SETQ.encode()).decode()},
                 {"name": "S2-send", "el": base64.b64encode(BTN("发送").encode()).decode()},
                 {"name": "S3-first-frame", "until": base64.b64encode(FR.encode()).decode(), "timeout": 15000}]
        if s["reload_at"] is not None:
            steps.append({"name": "S4-pre-reload-peek", "expr": base64.b64encode(FR.encode()).decode()})
            steps.append({"name": "S5-wait", "wait": int(s["reload_at"] * 1000)})
            steps.append({"name": "S6-reload", "reload": 4000})
            steps.append({"name": "S7-after-reload-peek", "expr": base64.b64encode(FR.encode()).decode()})
        else:
            steps.append({"name": "S4-wait-stream", "wait": 8000})
            steps.append({"name": "S5-peek", "expr": base64.b64encode(FR.encode()).decode()})
        cfg = {"url": URL, "bootWait": 7000, "steps": steps}
        cfgp = RUN / ("v18_cdp_%s.json" % tag)
        cfgp.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", str(HERE / "v18_cdp.js"), str(cfgp)],
                           capture_output=True, text=True)
        (RUN / ("v18_cdp_%s.out" % tag)).write_text(r.stdout + ("\nSTDERR:\n" + r.stderr if r.stderr else ""), encoding="utf-8")

        time.sleep(s["tail"])
    finally:
        el = log.read_text(encoding="utf-8") if log.exists() else ""
        t0 = None
        for ln in el.splitlines():
            if "t0_epoch=" in ln:
                t0 = float(ln.split("t0_epoch=")[1].split()[0])
        # 结论要在进程还活着的时候算完，再杀
        summary = []
        summary.append("场景 %s：%s" % (tag, s["note"]))
        summary.append("approval_timeout=%s s | 探针 t0_epoch=%s" % (ap_timeout, t0))
        cdp_p = RUN / ("v18_cdp_%s.out" % tag)
        cdp = json.loads(cdp_p.read_text(encoding="utf-8").split("STDERR:")[0]) if cdp_p.exists() else {}
        if t0:
            for k in sorted({kk.split("#")[0] for kk in cdp if "#" in kk or kk.startswith("S")}):
                for suf in ("#at", "#reloadAt", "#reloadDoneAt"):
                    if k + suf in cdp:
                        summary.append("  浏览器 %-22s t=%7.3f" % (k + suf, cdp[k + suf] / 1000.0 - t0))
        summary.append("  服务端事件（全量）：")
        for ln in el.splitlines():
            summary.append("    " + ln)
        for key in ("gen.finally", "wait.timeout", "worker.exit", "event.close", "event.load", "decide"):
            n = sum(1 for ln in el.splitlines() if key in ln)
            summary.append("  计数 %-14s %d" % (key, n))
        (RUN / ("v18_summary_%s.out" % tag)).write_text("\n".join(summary) + "\n", encoding="utf-8")
        print("\n".join(summary))
        subprocess.run(["pkill", "-TERM", "-P", str(p.pid)])
        os_kill(p.pid)
        out.close()


def os_kill(pid):
    try:
        import os
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception as exc:
        print("kill failed:", exc)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "A2", float(sys.argv[2]) if len(sys.argv) > 2 else 20.0)
