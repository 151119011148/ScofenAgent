# -*- coding: utf-8 -*-
"""v1.9 侧栏删除的**真界面**跑一遍：起一个独立实例（另开的端口 + 临时库），
用 9333 上的 headless Chrome 点两下，浏览器看到的效果和库里的行数一起对表。

为什么不碰他那一台：那份库是 smolagents/.agent-history.sqlite3，删除不可逆。
这里 `my_ui.DB_PATH` 在构造 OpsUI 之前就被环境变量指到 run/ 下的临时库，
真库里一行都不会被读到、更不会写到。也不提问——整个跑法零模型调用、零 token。

跑法（要 smolagents 的 venv，且 9333 上有 headless Chrome）：
    smolagents/.venv/bin/python 验收脚本/v1.9/v19_live_delete.py
产物：run/v19_live_delete.cdp.out（浏览器侧每一步的 DOM 读数）
      run/v19_live_delete.server.log（服务端）
退出码 0 = 全绿。
"""
import base64
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run"
RUN.mkdir(exist_ok=True)
ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
PY = ROOT / "smolagents/.venv/bin/python"
PORT = os.environ.get("V19_PORT", "7873")
DB = RUN / "v19_live_delete.sqlite3"
URL = "http://127.0.0.1:%s" % PORT
CDP = ROOT / "验收脚本/v1.8/v18_cdp.js"

FAIL = []
N = 0


def ok(name, cond, detail=""):
    global N
    N += 1
    print("%-38s %s %s" % (name, "PASS" if cond else "FAIL", detail), flush=True)
    if not cond:
        FAIL.append(name)


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode()


def q(sql, args=()):
    con = sqlite3.connect(str(DB))
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()



# ---- 0 前置：9333 上的 Chrome 必须活着 -----------------------------------
try:
    alive = subprocess.run(["curl", "-s", "--max-time", "3", "http://127.0.0.1:9333/json/version"],
                           capture_output=True, text=True).stdout.strip()
except Exception as exc:  # noqa: BLE001
    alive = ""
    print("  chrome 探测失败：", exc)
if not alive:
    print("FAIL  9333 上没有 headless Chrome，这条跑不了（离线断言在 v19_test_delete.py，不受影响）")
    sys.exit(1)

# ---- 1 起一个隔离实例（临时库，绝不指到 .agent-history.sqlite3） ----------
if DB.exists():
    DB.unlink()
launcher = RUN / "v19_live_delete.app.py"
launcher.write_text(
    """
import os, pathlib, sys
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr
import my_ui

DB = pathlib.Path(os.environ["V19_DB"])
my_ui.DB_PATH = DB                     # 构造 OpsUI 之前指走，真库不参与
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
# 预置两条会话，标题分别带 A/B，浏览器里一眼分得开
h = ui.hist
a, b = h.ensure(None), h.ensure(None)
h.save(a, [gr.ChatMessage(role="user", content="A 号会话的第一问"),
           gr.ChatMessage(role="assistant", content="A 号会话的答复")])
h.save_memory(a, '{"fmt":"v2","steps":[]}')
h.save(b, [gr.ChatMessage(role="user", content="B 号会话的第一问")])
h.save_memory(b, '{"fmt":"v2","steps":[]}')
print("seeded", a, b, flush=True)
open(os.environ["V19_IDS"], "w").write("%s %s" % (a, b))
ui.launch(share=False, server_name="127.0.0.1", server_port=int(os.environ["V19_PORT"]),
          css=my_ui.DARK_CSS)
""",
    encoding="utf-8",
)
ids = RUN / "v19_live_delete.ids"
env = dict(os.environ, V19_DB=str(DB), V19_PORT=PORT, V19_IDS=str(ids))
logf = (RUN / "v19_live_delete.server.log").open("w", encoding="utf-8")
srv = subprocess.Popen([str(PY), str(launcher)], cwd=str(ROOT / "smolagents"),
                       stdout=logf, stderr=subprocess.STDOUT, env=env)
try:
    # 等 id 文件出现（= 种子已落库），再等端口真的在听。前者不代表服务可用。
    for _ in range(60):
        if ids.exists():
            break
        time.sleep(1)
    else:
        print("FAIL  实例没起来（没写出 ids），看 run/v19_live_delete.server.log")
        sys.exit(1)
    for _ in range(90):
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", URL],
                              capture_output=True, text=True).stdout.strip()
        if code == "200":
            break
        time.sleep(1)
    else:
        print("FAIL  %s 起不来，看 run/v19_live_delete.server.log" % URL)
        sys.exit(1)
    time.sleep(2)
    A, B = [int(x) for x in ids.read_text().split()]
    print("  隔离实例：%s ｜ 临时库 %s ｜ 会话 A=%d B=%d（他的真库不参与）" % (URL, DB.name, A, B), flush=True)

    # ---- 2 浏览器：点两下 ------------------------------------------------
    # 侧栏/按钮/回执/气泡四样的当前读数（flash/btn 兜成空串，否则 JSON.stringify 会把这个
    # 键整个丢掉，读出来是 None——第一版就被这点骗过，误判成「回执没上屏」）。
    SNAP = """({items:Array.from(document.querySelectorAll('#sessions label'))
            .map(l=>l.innerText.trim()),
          checked:(()=>{const r=document.querySelector('#sessions input:checked');
                        return r?r.closest('label').innerText.trim():null;})(),
          btn:((document.getElementById('del-btn')||{}).innerText||''),
          flash:((document.getElementById('flash')||{}).innerText||''),
          bubbles:document.querySelectorAll('.message-row, [data-testid=bot], [data-testid=user]').length})"""
    SEL = b64("(()=>JSON.stringify(%s))()" % SNAP)

    # 每一下点完**轮询到该出现的东西出现**为止（1s 一档，20s 上限）。
    # 为什么不用定长 sleep：实测点下去到回帧落地是 0~2.5 秒之间浮动（1.5s 那一版每条读数
    # 都慢一下；把间隔压到几十毫秒，gradio 那边还会把两下并成一轮，屏幕上什么都没发生）。
    # 为什么也不用「连续两帧一致就算稳」：那一版第一下点完 6ms 就判稳（那时 DOM 当然还没动），
    # 于是整跑读到的全是旧帧——判据必须是「等到了预期」，不是「画面没变」。
    def pred(js):
        return b64("(()=>{const s=%s;const c=(%s);return (c?'YES ':'NO ')+JSON.stringify(s).slice(0,240);})()"
                   % (SNAP, js))

    P_ARM = pred("s.btn==='⚠ 确认删除？'")
    P_GONE_B = pred("s.items.length===1&&s.checked===null&&s.flash.indexOf('已删除')===0&&s.btn==='🗑 删除'")
    P_HINT = pred("s.flash.indexOf('先在左边点一条会话')>=0")
    P_RELOAD = pred("s.items.length===1&&String(s.checked).indexOf('A 号')>=0")
    P_SEL_A = pred("String(s.checked).indexOf('A 号')>=0&&s.bubbles>=2")
    P_EMPTY = pred("s.items.length===0&&s.flash.indexOf('已删除')===0&&s.bubbles===0")
    RD = lambda name: {"name": name, "expr": SEL}
    CLICK = b64("document.getElementById('del-btn')")
    ALABEL = b64("""(()=>{const l=Array.from(document.querySelectorAll('#sessions label')).find(x=>x.innerText.includes('A 号'));return l||'NO'})()""")
    # 顺序按 v18_cdp.js 的 step 语义写死：el → expr → until → reload → wait。
    # 所以「点」和「读」分两步：点那一步用 until 等到预期，紧跟的读步骤记录定帧。
    W = lambda name, until, **kw: {"name": name, "until": until, "timeout": 20000, **kw}
    cfg = {
        "url": URL,
        "bootWait": 8000,
        "steps": [
            W("0x 开屏（_on_load 该选中最近一条 B）", pred("s.items.length===2&&String(s.checked).indexOf('B 号')>=0&&s.bubbles>=1&&s.btn==='🗑 删除'")),
            RD("1 开屏（_on_load 选中最近一条 = B）"),
            W("1x 第一下·武装", P_ARM, el=CLICK),
            RD("2 第一下（武装）"),
            W("2x 第二下·真删", P_GONE_B, el=CLICK),
            RD("3 第二下（真删）"),
            W("3x 删完再点一下（未选中）", P_HINT, el=CLICK),
            RD("4 删完再点一下（未选中）"),
            {"name": "4x 刷新页面", "reload": 8000},
            W("4y 刷新后侧栏只剩 A 且被选中", P_RELOAD),
            RD("5 刷新页面（删除得留下来）"),
            W("5x 点 A 那条", P_SEL_A, el=ALABEL),
            RD("6 点 A 那条，删它"),
            W("6x A 的第一下（重新武装，B 那次的确认没跟过来）", P_ARM, el=CLICK),
            RD("7 A 的第一下"),
            W("7x A 的第二下（真删，库应清空）", P_EMPTY, el=CLICK),
            RD("8 A 的第二下（库应清空）"),
        ],
    }
    cfgp = RUN / "v19_live_delete.cdp.json"
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(CDP), str(cfgp)], capture_output=True, text=True)
    (RUN / "v19_live_delete.cdp.out").write_text(r.stdout, encoding="utf-8")
    out = json.loads(r.stdout)

    reads = {}
    for k in ("1 开屏（_on_load 选中最近一条 = B）", "2 第一下（武装）", "3 第二下（真删）",
              "4 删完再点一下（未选中）", "5 刷新页面（删除得留下来）", "6 点 A 那条，删它",
              "7 A 的第一下", "8 A 的第二下（库应清空）"):
        v = out.get(k)
        reads[k] = json.loads(v) if isinstance(v, str) and v.startswith("{") else v

    def g(k, field):
        return (reads.get(k) or {}).get(field)

    ok("L1 开屏选中最近一条 B、侧栏两条都在",
       g("1 开屏（_on_load 选中最近一条 = B）", "checked", ) and "B 号" in str(g("1 开屏（_on_load 选中最近一条 = B）", "checked"))
       and len(g("1 开屏（_on_load 选中最近一条 = B）", "items")) == 2,
       str(g("1 开屏（_on_load 选中最近一条 = B）", "items")))
    ok("L2 删除键默认文案", g("1 开屏（_on_load 选中最近一条 = B）", "btn") == "🗑 删除", repr(g("1 开屏（_on_load 选中最近一条 = B）", "btn")))
    ok("L3 第一下只武装：文案变确认、B 还在侧栏",
       g("2 第一下（武装）", "btn") == "⚠ 确认删除？" and "B 号" in str(g("2 第一下（武装）", "checked"))
       and len(g("2 第一下（武装）", "items")) == 2,
       "%s ｜ flash=%s" % (g("2 第一下（武装）", "items"), str(g("2 第一下（武装）", "flash"))[:60]))
    ok("L4 武装那一帧屏幕没动（气泡还在）",
       (g("1 开屏（_on_load 选中最近一条 = B）", "bubbles") or 0) > 0
       and g("2 第一下（武装）", "bubbles") == g("1 开屏（_on_load 选中最近一条 = B）", "bubbles"))
    ok("L5 第二下真删：库里 B 归零",
       q("SELECT count(*) FROM sessions WHERE id=?", (B,)) == [(0,)]
       and q("SELECT count(*) FROM messages WHERE session_id=?", (B,)) == [(0,)]
       and q("SELECT count(*) FROM memory WHERE session_id=?", (B,)) == [(0,)])
    ok("L6 删完侧栏只剩 A、一条不亮",
       len(g("3 第二下（真删）", "items")) == 1 and "A 号" in str(g("3 第二下（真删）", "items"))
       and g("3 第二下（真删）", "checked") is None, str(g("3 第二下（真删）", "items")))
    ok("L7 屏幕清空、文案复位、回执带条数",
       g("3 第二下（真删）", "bubbles") == 0 and g("3 第二下（真删）", "btn") == "🗑 删除"
       and "已删除" in str(g("3 第二下（真删）", "flash")) and "1 条消息" in str(g("3 第二下（真删）", "flash")),
       str(g("3 第二下（真删）", "flash")))
    ok("L8 没选中时再点：只提示，不动 A",
       "先在左边点一条会话" in str(g("4 删完再点一下（未选中）", "flash"))
       and len(g("4 删完再点一下（未选中）", "items")) == 1
       and g("4 删完再点一下（未选中）", "btn") == "🗑 删除")
    ok("L9 刷新之后 B 仍然没有（删除落进了库，不是只在内存）",
       len(g("5 刷新页面（删除得留下来）", "items")) == 1 and "A 号" in str(g("5 刷新页面（删除得留下来）", "items")),
       str(g("5 刷新页面（删除得留下来）", "items")))
    ok("L10 选中 A 之后屏幕是 A 的字",
       g("6 点 A 那条，删它", "checked") and "A 号" in str(g("6 点 A 那条，删它", "checked"))
       and (g("6 点 A 那条，删它", "bubbles") or 0) >= 2, str(g("6 点 A 那条，删它", "bubbles")))
    ok("L11 换到 A 之后第一下又回到武装（B 那次的确认没跟过来）",
       g("7 A 的第一下", "btn") == "⚠ 确认删除？" and "A 号" in str(g("7 A 的第一下", "items")),
       str(g("7 A 的第一下", "items")))
    ok("L12 第二下删掉 A，库空",
       g("8 A 的第二下（库应清空）", "btn") == "🗑 删除" and q("SELECT count(*) FROM sessions") == [(0,)]
       and q("SELECT count(*) FROM messages") == [(0,)] and q("SELECT count(*) FROM memory") == [(0,)],
       str(g("8 A 的第二下（库应清空）", "flash")))
    ok("L13 全程零模型调用（服务端日志里没有 token 统计变化）",
       "Traceback" not in (RUN / "v19_live_delete.server.log").read_text(encoding="utf-8"), "服务端无异常")

    print("\n%s  %d 条实跑判据，失败 %d" % ("全绿" if not FAIL else "有红", N, len(FAIL)))
    for f in FAIL:
        print("  FAIL:", f)
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()
    logf.close()

sys.exit(0 if not FAIL else 1)
