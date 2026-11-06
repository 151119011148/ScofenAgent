# -*- coding: utf-8 -*-
"""D8 基线①（零模型调用）：把「流式生成器 ＋ 工作线程 ＋ 阻塞审批」这套形状搬到最小 gradio 应用上，
中途刷新页面，只看服务端日志回答三件事：

1. 客户端断开时，gradio 6.30 会不会去 close() 那条正在 yield 的生成器（→ 生成器里收到 GeneratorExit）；
   还是直接把它扔掉（→ finally 永远不跑，直到 GC）。
2. 断开之后，那条 worker 线程还在不在跑（真 app 里它就是 agent.run 的那条线程，继续烧 token）。
3. 挂在 Event.wait() 上的审批，断开后由谁结算——不点按钮就只剩超时这一条路。

用法：python v18_probe_disconnect.py <tag> [port] [approval_timeout] [--auto-allow]
产物：run/v18_probe_<tag>.log（服务端逐事件带时间戳）
"""
import pathlib
import sys
import threading
import time

import gradio as gr

TAG = sys.argv[1] if len(sys.argv) > 1 else "x"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 7871
APPROVAL_TIMEOUT = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0
AUTO_ALLOW = "--auto-allow" in sys.argv

FRAMES = 20          # 生成器一共吐 20 帧
FRAME_SLEEP = 0.3    # 每帧 0.3s → 一条流约 6s
WORKER_SECONDS = 9.0 # worker 比生成器活得久一点，用来区分「断开后线程还在跑」和「线程一起死了」

LOG = pathlib.Path(__file__).resolve().parent / "run" / ("v18_probe_%s.log" % TAG)
LOG.parent.mkdir(parents=True, exist_ok=True)
T0 = time.time()
_lock = threading.Lock()


def log(ev, **kw):
    extra = " ".join("%s=%s" % (k, v) for k, v in kw.items())
    line = "t=%7.3f  %-26s %s" % (time.time() - T0, ev, extra)
    with _lock:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line, flush=True)


class Approval:
    """和 my_ui.Approval 同一把形状：decision ＋ Event ＋ 超时按 timeout 自结算。"""

    def __init__(self, tool):
        self.tool = tool
        self.created = time.time()
        self.decision = "pending"
        self._done = threading.Event()

    def decide(self, d):
        if self.decision == "pending":
            self.decision = d
            self._done.set()
            log("decide", decision=d, waited="%.3f" % (time.time() - self.created))

    def wait(self):
        log("wait.enter", tool=self.tool, timeout=APPROVAL_TIMEOUT)
        if not self._done.wait(APPROVAL_TIMEOUT):
            self.decision = "timeout"
            self._done.set()
            log("wait.timeout", tool=self.tool, after=APPROVAL_TIMEOUT)
        log("wait.exit", decision=self.decision)
        return self.decision


PENDING = []          # 待批队列（对应 my_ui 的 self._pending）
ABANDONED = threading.Event()


def worker(ap):
    """对应 my_ui._worker：先阻塞在审批上，解开之后再干一段活。"""
    decision = ap.wait()
    t_end = time.time() + WORKER_SECONDS
    i = 0
    while time.time() < t_end:
        if ABANDONED.is_set():
            log("worker.abandoned", at=i)
            break
        time.sleep(0.5)
        i += 1
        if i % 4 == 0:
            log("worker.alive", tick=i, decision=decision)
    log("worker.exit", ticks=i, decision=decision)


def gen(message):
    """对应 my_ui._respond ＋ _stream_response：一边推流一边等 worker 的队列。"""
    log("gen.start", message=str(message)[:30])
    ap = Approval("run_python")
    PENDING.append(ap)
    threading.Thread(target=worker, args=(ap,), name="agent-run", daemon=True).start()
    if AUTO_ALLOW:
        threading.Timer(3.0, ap.decide, ["allowed"]).start()
    state = "running"
    n = 0
    try:
        for i in range(FRAMES):
            time.sleep(FRAME_SLEEP)
            n += 1
            yield "<div>第 %d 帧 · 待批 %s</div>" % (n, ap.decision)
        state = "done"
    except GeneratorExit:
        state = "GeneratorExit"
        raise
    except BaseException as exc:
        state = type(exc).__name__
        log("gen.exception", exc=state)
        raise
    finally:
        # 真 app 的 finally 里是 hist.save(sid, last) ＋ save_memory()：这一句跑不跑就是 D8 的整与丢。
        # 注意不在 finally 里 yield——真 app 最后一帧在 try/finally 之外（_respond:1105），这里也不学它，
        # 免得把「生成器在 finally 里再吐一帧」这种 RuntimeError 混进结论。
        log("gen.finally", state=state, frames=n, threads=len(threading.enumerate()))


def on_load(sid):
    log("event.load")
    return sid + 1


def on_close():
    log("event.close")


def on_stop():
    log("event.stop", pending=len([a for a in PENDING if a.decision == "pending"]))
    for a in PENDING:
        a.decide("cancelled")
    ABANDONED.set()


with gr.Blocks() as demo:
    box = gr.Textbox(label="问题")
    btn = gr.Button("发送", variant="primary")
    stop = gr.Button("■ 停止")
    out = gr.HTML()
    sess = gr.State(0)
    btn.click(gen, inputs=[box], outputs=[out])
    stop.click(on_stop, outputs=None)
    demo.load(on_load, inputs=[sess], outputs=[sess])
    demo.close(on_close)

log("boot", port=PORT, frames=FRAMES, approval_timeout=APPROVAL_TIMEOUT, auto_allow=AUTO_ALLOW,
    t0_epoch=round(T0, 3))
demo.launch(share=False, server_name="127.0.0.1", server_port=PORT, quiet=True)
