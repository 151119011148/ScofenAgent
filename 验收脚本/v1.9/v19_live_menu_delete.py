# -*- coding: utf-8 -*-
"""v1.9「⋯ → 删除」的真界面跑一遍：独立实例 + 临时库（不碰 .agent-history.sqlite3），
用我自己那台 headless Chrome（9344）真指针点，逐帧对表。

**为什么切成三段、每段重新开一页**：库里动没动这件事，必须在它声称的那个时刻去看。
上一版是一趟跑到底、跑完再 sqlite 对表——那时 B 早被删了，「第一下只武装、库里没动」和
「别的会话一根毛不动」两条拿的是终态，判据天然是倒的（断言 11/18 就是这么红的）。
切段之后：段与段之间进程不换（`_armed_del`、`_del_nonce` 这些服务端状态都留着），只换页面，
于是每段跑完都能当场读一次库。段边界本身也是一条用例——**刷新页面会把武装清掉**（`_on_load`
里那一行是故意的：刷新后确认重新开始，一次点击删不掉），而页内自增号同时归零，所以前端的号
必须带「开场号」那一段，不然刷新后那一页的第一下会被当成同一次投递**无声吞掉**（没有回执，
用户以为按钮坏了）。段 2 就照着这个口径验：第一下有「确认删除」回执、库还没动，同页第二下才删。

零模型调用、零 token。现场写在 /tmp/v19_menu_run/（cdp.p1~p3.out、server.log、ids、临时库），
收进本目录的固定一份在 run/v19_live_menu_delete.*。
跑法：smolagents/.venv/bin/python 验收脚本/v1.9/v19_live_menu_delete.py
      （要先有我那台 headless Chrome：--headless=new --remote-debugging-port=9344 --user-data-dir=/tmp/chrome-more）
"""
import json
import os
import pathlib
import subprocess
import sys
import time

RUN = pathlib.Path("/tmp/v19_menu_run")
RUN.mkdir(exist_ok=True)
ROOT = pathlib.Path("/Users/gaoying/Desktop/study/ai学习")
PY = ROOT / "smolagents/.venv/bin/python"
PORT = os.environ.get("V19_MENU_PORT", "7874")
DB = RUN / "menu.sqlite3"
IDS = RUN / "ids"
URL = "http://127.0.0.1:%s" % PORT
CDP = ROOT / "验收脚本/v1.9/v19_cdp_menu.js"

FAIL, N = [], 0


def ok(name, cond, detail=""):
    global N
    N += 1
    print("%-34s %s %s" % (name, "PASS" if cond else "FAIL", str(detail)[:150]), flush=True)
    if not cond:
        FAIL.append(name)


def b64(s):
    import base64
    return base64.b64encode(s.encode("utf-8")).decode()


def q(sql, args=()):
    import sqlite3
    con = sqlite3.connect(str(DB))
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def jget(data, key):
    v = data.get(key)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return {}
    return {} if v is None else v


for p in (DB, IDS):
    if p.exists():
        p.unlink()

launcher = RUN / "app.py"
launcher.write_text(
    """
import os, pathlib, sys, time
sys.path.insert(0, "/Users/gaoying/Desktop/study/ai学习/smolagents")
import gradio as gr
import my_ui

my_ui.DB_PATH = pathlib.Path(os.environ["V19_DB"])      # 构造 OpsUI 之前指走，真库不参与
ui = my_ui.OpsUI(my_ui.agent, file_upload_folder="./data")
h = ui.hist
ids = []
for tag, n in (("A", 2), ("B", 3), ("C", 1)):
    s = h.ensure(None)
    h.save(s, [gr.ChatMessage(role="user", content="%s 号会话的第一问" % tag)] +
               [gr.ChatMessage(role="assistant", content="%s 号答复%d" % (tag, i)) for i in range(n - 1)])
    h.save_memory(s, '{"fmt":"v2","steps":[]}')
    ids.append(s)
    time.sleep(0.05)                                     # 让 updated_at 拉开，侧栏顺序才确定
print("seeded", ids, flush=True)
open(os.environ["V19_IDS"], "w").write(" ".join(str(x) for x in ids))
ui.launch(share=False, server_name="127.0.0.1", server_port=int(os.environ["V19_PORT"]),
          css=my_ui.DARK_CSS)
""",
    encoding="utf-8",
)
env = dict(os.environ, V19_DB=str(DB), V19_PORT=PORT, V19_IDS=str(IDS))
logf = (RUN / "server.log").open("w", encoding="utf-8")
srv = subprocess.Popen([str(PY), str(launcher)], cwd=str(ROOT / "smolagents"),
                       stdout=logf, stderr=subprocess.STDOUT, env=env)

SNAP = r"""({items:Array.from(document.querySelectorAll('#sessions label'))
          .map(l=>l.innerText.replace('⋯','').trim().replace(/\s+/g,' ').slice(0,14)),
        checked:(()=>{const r=document.querySelector('#sessions input:checked');return r?r.value:null;})(),
        flash:((document.getElementById('flash')||{}).innerText||''),
        menu:!!document.getElementById('del-menu'),
        menutxt:((document.getElementById('del-menu')||{}).innerText||''),
        more:document.querySelectorAll('#sessions label .row-more').length,
        bubbles:document.querySelectorAll('.message-row, [data-testid=bot], [data-testid=user]').length})"""


def pred(js):
    return b64(r"(()=>{const s=%s;const c=(%s);return (c?'YES ':'NO ')+JSON.stringify(s).slice(0,300);})()"
               % (SNAP, js))


def more(tag):
    return ("(()=>{const l=Array.from(document.querySelectorAll('#sessions label'))"
            ".find(x=>x.innerText.includes('%s 号'));return l&&l.querySelector('.row-more');})()" % tag)


def label(tag):
    return ("(()=>Array.from(document.querySelectorAll('#sessions label'))"
            ".find(x=>x.innerText.includes('%s 号')))()" % tag)


def open_synth(tag):
    return ("(()=>{const l=Array.from(document.querySelectorAll('#sessions label'))"
            ".find(x=>x.innerText.includes('%s 号'));if(!l)return 'NO-ROW';"
            "l.querySelector('.row-more').click();return String(!!document.getElementById('del-menu'));})()" % tag)


SEL_MENU_BTN = "document.querySelector('#del-menu button')"
ARMED = "s.menu===true&&s.menutxt.replace(/\\s/g,'')==='删除'"
HOOK = ("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)));"
        "window.addEventListener('unhandledrejection',e=>window.__errs.push('rej:'+String(e.reason)));"
        "'installed'")

# ---- 三段步骤 --------------------------------------------------------------
P1 = [
    {"name": "02-shape", "expr": b64(r"""(()=>{const t=document.getElementById('del-trigger');
      const l=Array.from(document.querySelectorAll('#sessions label'))[0];
      const m=l&&l.querySelector('.row-more');const db=document.getElementById('del-btn');
      return JSON.stringify({
        triggerTag:t&&t.tagName, triggerDisplay:t?getComputedStyle(t).display:null,
        delBtnDisplay:db?getComputedStyle(db).display:null,
        labelPosition:l&&getComputedStyle(l).position, labelPadRight:l&&getComputedStyle(l).paddingRight,
        moreOpacityIdle:m&&getComputedStyle(m).opacity, moreCount:document.querySelectorAll('.row-more').length,
        payloadFmt:(document.getElementById('del-payload')||{}).value,
        checked:(document.querySelector('#sessions input:checked')||{}).value,
        innerW:window.innerWidth});})()""")},
    {"name": "03-hover-b", "hover": b64(label("B")), "wait": 500},
    {"name": "04-hover-opacity", "expr": b64(
        "(()=>{const l=Array.from(document.querySelectorAll('#sessions label')).find(x=>x.innerText.includes('B 号'));"
        "const m=l&&l.querySelector('.row-more');if(!m)return 'NO-ROW';"
        "const b=l.getBoundingClientRect();const u=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);"
        "return JSON.stringify({opacity:getComputedStyle(m).opacity,labelHover:l.matches(':hover'),"
        "under:u&&(u.tagName+(u.className?'.'+String(u.className).split(' ')[0]:''))});})()")},
    {"name": "05-click-more-b", "el": b64(more("B"))},
    {"name": "06-menu-open", "until": pred(ARMED), "timeout": 15000},
    {"name": "07-menu-geometry", "expr": b64(
        "(()=>{const t=document.getElementById('del-menu');if(!t)return 'NO-MENU';"
        "const b=t.getBoundingClientRect();"
        "return JSON.stringify({left:Math.round(b.left),top:Math.round(b.top),w:Math.round(b.width),"
        "h:Math.round(b.height),inView:b.left>=0&&b.right<=window.innerWidth&&b.top>=0&&b.bottom<=window.innerHeight,"
        "parent:t.parentElement===document.body,for:t.dataset.for,"
        "items:Array.from(t.querySelectorAll('button')).map(x=>x.textContent)});})()")},
    {"name": "08-more-click-did-not-select", "expr": b64(
        "JSON.stringify({checked:(document.querySelector('#sessions input:checked')||{}).value,"
        "labels:Array.from(document.querySelectorAll('#sessions input')).map(i=>i.value)})")},
    {"name": "09-click-del", "el": b64(SEL_MENU_BTN)},
    # 点击落地那一刻：payload 有没有写到 window 上、隐藏键在不在
    # （把「前端没送」和「后端没回」分开——上一版就卡在这一格，flash 永远空）
    {"name": "09b-payload-sent", "expr": b64(
        "JSON.stringify({payload:window.__delPayload===undefined?null:window.__delPayload,"
        "trigger:!!document.getElementById('del-trigger')})")},
    {"name": "10-armed", "until": pred("s.flash.indexOf('确认删除')>=0&&s.flash.indexOf('B 号')>=0&&s.items.length===3"),
     "timeout": 20000},
    {"name": "11-menu-closed-after-click", "expr": b64("String(!!document.getElementById('del-menu'))")},
    {"name": "12-screen-untouched", "expr": b64(
        "JSON.stringify({checked:(document.querySelector('#sessions input:checked')||{}).value,"
        "bubbles:document.querySelectorAll('.message-row, [data-testid=bot], [data-testid=user]').length})")},
    {"name": "13-escape-closes", "expr": b64(
        "(()=>{const o=(%s);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
        "return JSON.stringify({opened:o==='true',afterEscape:!!document.getElementById('del-menu')});})()"
        % open_synth("B"))},
    {"name": "14a-reopen-for-outside", "expr": b64(open_synth("B")), "wait": 300},
    {"name": "14-outside-closes", "el": b64("document.getElementById('brand')"), "wait": 400},
    {"name": "15-outside-state", "expr": b64("String(!!document.getElementById('del-menu'))")},
]
P2 = [
    # 段 2 是**新的一页**：`_on_load` 明确把武装清掉（刷新后确认重新开始，一次点击删不掉），
    # 页内自增号也跟着归零。所以要验两件事：这一页的第一下**没有被当成重复投递无声吞掉**
    # （有「确认删除」回执），并且它**只是武装**、库还没动。
    {"name": "16-second-open-b", "el": b64(more("B")), "wait": 500},
    {"name": "17-reopen", "until": pred("s.menu===true"), "timeout": 15000},
    {"name": "18-click-del-2", "el": b64(SEL_MENU_BTN)},
    {"name": "18b-payload-sent-2", "expr": b64("String(window.__delPayload)")},
    {"name": "18c-rearm-feedback",
     "until": pred("s.flash.indexOf('确认删除')>=0&&s.flash.indexOf('B 号')>=0&&s.items.length===3"),
     "timeout": 20000},
    {"name": "19-open-b-3", "el": b64(more("B")), "wait": 500},
    {"name": "19b-menu-3", "until": pred(ARMED), "timeout": 15000},
    {"name": "20-click-del-3", "el": b64(SEL_MENU_BTN)},
    {"name": "21-deleted", "until": pred(
        "s.items.length===2&&s.flash.indexOf('已删除')===0&&s.items.join().indexOf('B 号')<0"), "timeout": 25000},
    {"name": "22-redecorate", "expr": b64(
        "JSON.stringify({rows:document.querySelectorAll('#sessions label').length,"
        "more:document.querySelectorAll('#sessions label .row-more').length,"
        "checked:(document.querySelector('#sessions input:checked')||{}).value,"
        "bubbles:document.querySelectorAll('.message-row, [data-testid=bot], [data-testid=user]').length})")},
]
P3 = [
    # 开菜单那一下当场记一格「点没点上」：整段跑完再对表看不出「开了又自己关上」和「没开成」的差别
    {"name": "30-open-a", "el": b64(more("A"))},
    {"name": "30b-immediate", "expr": b64(
        "JSON.stringify({menu:!!document.getElementById('del-menu'),for:(document.getElementById('del-menu')||{}).dataset||{}})")},
    {"name": "30c-wait", "wait": 500, "expr": b64("'settle'")},
    {"name": "31-menu-for-a", "until": pred(ARMED), "timeout": 15000},
    {"name": "32-del-a-1", "el": b64(SEL_MENU_BTN)},
    {"name": "33-armed-a", "until": pred("s.flash.indexOf('确认删除')>=0&&s.flash.indexOf('A 号')>=0"), "timeout": 20000},
    {"name": "34-open-a-2", "el": b64(more("A")), "wait": 500},
    {"name": "35-reopen-a", "until": pred("s.menu===true"), "timeout": 15000},
    {"name": "36-click-final-a", "el": b64(SEL_MENU_BTN)},
    {"name": "37-deleted-a", "until": pred("s.items.length===1&&s.flash.indexOf('已删除')===0"), "timeout": 25000},
    # 收起的常驻键没有尺寸，真指针点不到（实测 clicked@0,0），所以按另一会话回归测试的写法程序化点
    {"name": "38-hidden-btn-click", "expr": b64("document.getElementById('del-btn').click();'clicked'")},
    {"name": "39-hidden-btn-armed", "until": pred("s.flash.indexOf('确认删除')>=0&&s.items.length===1"), "timeout": 20000},
    # 把上一条的判据当场重放一遍：轮询说 NO 而快照里明明有回执时，这一行就是裁判
    {"name": "39b-replay", "expr": b64(
        "(()=>{const s=%s;return JSON.stringify({hit:s.flash.indexOf('确认删除'),items:s.items.length,"
        "verdict:(s.flash.indexOf('确认删除')>=0&&s.items.length===1)?'YES':'NO'});})()" % SNAP)},
    {"name": "40-hidden-btn-value", "expr": b64("document.getElementById('del-btn').innerText")},
]
PHASES = [
    ("p1", 9000, "s.items.length===3&&s.more===3", P1),
    ("p2", 7000, "s.items.length===3&&s.more===3", P2),
    ("p3", 7000, "s.items.length===2&&s.more===2", P3),
]


def run_phase(tag, boot, ready, body):
    steps = [{"name": "%s-errors-hook" % tag, "expr": b64(HOOK)},
             {"name": "%s-ready" % tag, "until": pred(ready), "timeout": 40000}]
    steps += body
    steps.append({"name": "%s-errors-read" % tag, "expr": b64("JSON.stringify(window.__errs)")})
    cfgp = RUN / ("cdp.%s.cfg.json" % tag)
    cfgp.write_text(json.dumps({"url": URL, "bootWait": boot, "steps": steps}), encoding="utf-8")
    r = subprocess.run(["node", str(CDP), str(cfgp)], capture_output=True, text=True, timeout=900)
    (RUN / ("cdp.%s.out" % tag)).write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    if not r.stdout.strip():
        print("FAIL  段 %s 没有输出：%s" % (tag, r.stderr[-400:]))
        sys.exit(1)
    data = json.loads(r.stdout)
    for k, v in data.items():
        print("   %-28s %s" % (k, str(v)[:230]), flush=True)
    return data


try:
    for _ in range(90):
        if IDS.exists():
            break
        time.sleep(1)
    else:
        print("FAIL  实例没起来（没写出 ids）")
        sys.exit(1)
    for _ in range(90):
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", URL],
                              capture_output=True, text=True).stdout.strip()
        if code == "200":
            break
        time.sleep(1)
    else:
        print("FAIL  %s 起不来" % URL)
        sys.exit(1)
    A, B, C = [int(x) for x in IDS.read_text().split()]
    print("  隔离实例 %s ｜ 临时库 %s ｜ A=%d B=%d C=%d（真库不参与）" % (URL, DB.name, A, B, C), flush=True)

    d1 = run_phase(*PHASES[0])
    shape = jget(d1, "02-shape")
    selected = shape.get("checked")
    geo = jget(d1, "07-menu-geometry")
    ch8 = jget(d1, "08-more-click-did-not-select")
    pay = jget(d1, "09b-payload-sent")
    sc = jget(d1, "12-screen-untouched")

    ok("1 SIDEBAR_JS 真被调用（三行都有⋯）", str(d1.get("p1-ready#pred", "")).startswith("YES"),
       d1.get("p1-ready#pred"))
    ok("2 ⋯ 平时不可见（opacity 0）", shape.get("moreOpacityIdle") == "0", shape.get("moreOpacityIdle"))
    hov = jget(d1, "04-hover-opacity")
    ok("3 指针进来才可见（hover 后 opacity 1）", hov.get("opacity") == "1" and hov.get("labelHover") is True,
       [d1.get("03-hover-b#hover"), d1.get("04-hover-opacity")])
    ok("4 行给⋯留了位（relative + 右内边距 30px）", shape.get("labelPosition") == "relative"
       and shape.get("labelPadRight") == "30px", [shape.get("labelPosition"), shape.get("labelPadRight")])
    ok("5 常驻🗑已收起、隐藏键在 DOM 里", shape.get("delBtnDisplay") == "none"
       and shape.get("triggerTag") == "BUTTON" and shape.get("triggerDisplay") == "none",
       [shape.get("delBtnDisplay"), shape.get("triggerTag"), shape.get("triggerDisplay")])
    ok("6 菜单里只有「删除」一项", str(d1.get("06-menu-open#pred", "")).startswith("YES")
       and geo.get("items") == ["删除"], geo.get("items"))
    ok("7 菜单在视口内且挂 body", geo.get("inView") is True and geo.get("parent") is True, geo)
    ok("8 菜单绑的就是鼠标那一行 B", geo.get("for") == str(B), [geo.get("for"), "B=%d" % B])
    ok("9 点⋯没有把这一行选中", ch8.get("checked") == selected,
       ["checked=%s" % ch8.get("checked"), "开局=%s" % selected, ch8.get("labels")])
    ok("10 点删除时前端确实报了 id@号", str(pay.get("payload", "")).startswith("%d@" % B), pay)
    ok("11 第一下只武装、库里没动", str(d1.get("10-armed#pred", "")).startswith("YES")
       and q("SELECT count(*) FROM sessions WHERE id=?", (B,)) == [(1,)]
       and q("SELECT count(*) FROM messages WHERE session_id=?", (B,)) == [(3,)]
       and q("SELECT count(*) FROM memory WHERE session_id=?", (B,)) == [(1,)],
       [d1.get("10-armed#waitedMs"), str(d1.get("10-armed#pred"))[-80:],
        "B库=%s" % q("SELECT count(*) FROM sessions WHERE id=?", (B,))])
    ok("12 回执写着怎么确认", "再点一次" in str(d1.get("10-armed#pred")), str(d1.get("10-armed#pred"))[-70:])
    ok("13 点完「删除」菜单就收起", d1.get("11-menu-closed-after-click") == "false",
       d1.get("11-menu-closed-after-click"))
    ok("14 武装这一帧屏幕内容没被换掉", (sc.get("bubbles") or 0) >= 1 and sc.get("checked") == selected, sc)
    esc = jget(d1, "13-escape-closes")
    ok("15 Escape 收起菜单（合成 keydown，测的是监听器）",
       esc.get("opened") is True and esc.get("afterEscape") is False, esc)
    ok("16 点外面也收起", d1.get("14a-reopen-for-outside") == "true" and d1.get("15-outside-state") == "false",
       [d1.get("14a-reopen-for-outside"), d1.get("15-outside-state")])
    errs1 = d1.get("p1-errors-read")
    ok("17 段 1 浏览器侧没有未捕获错误", errs1 in ("[]", '"[]"'), errs1)

    d2 = run_phase(*PHASES[1])
    rd = jget(d2, "22-redecorate")
    pay2 = d2.get("18b-payload-sent-2")
    ok("18 刷新后第一下重新武装、不是无声吞掉（号带开场段）",
       pay2 != pay.get("payload") and str(d2.get("18c-rearm-feedback#pred", "")).startswith("YES"),
       [pay2, "段1=%s" % pay.get("payload"), str(d2.get("18c-rearm-feedback#pred"))[-70:]])
    ok("19 同一页第 2 下真删（三张表都清了）",
       str(d2.get("21-deleted#pred", "")).startswith("YES")
       and q("SELECT count(*) FROM sessions WHERE id=?", (B,)) == [(0,)]
       and q("SELECT count(*) FROM messages WHERE session_id=?", (B,)) == [(0,)]
       and q("SELECT count(*) FROM memory WHERE session_id=?", (B,)) == [(0,)],
       str(d2.get("21-deleted#pred"))[-80:])
    ok("20 别的会话一根毛不动", q("SELECT count(*) FROM sessions WHERE id IN (?,?)", (A, C)) == [(2,)]
       and q("SELECT count(*) FROM messages WHERE session_id=?", (C,)) == [(1,)]
       and q("SELECT count(*) FROM messages WHERE session_id=?", (A,)) == [(2,)],
       str(q("SELECT id FROM sessions")))
    ok("21 列表重画后⋯跟着在（两行两个）", rd.get("rows") == 2 and rd.get("more") == 2, rd)
    ok("22 删邻居没动选中那条的高亮与内容", rd.get("checked") == selected and (rd.get("bubbles") or 0) >= 1,
       ["checked=%s" % rd.get("checked"), "开局=%s" % selected, "bubbles=%s" % rd.get("bubbles")])
    ok("23 段 2 浏览器侧没有未捕获错误", d2.get("p2-errors-read") in ("[]", '"[]"'), d2.get("p2-errors-read"))

    d3 = run_phase(*PHASES[2])
    ok("24 A 那条也走满两下才删", q("SELECT count(*) FROM sessions WHERE id=?", (A,)) == [(0,)],
       str(d3.get("37-deleted-a#pred"))[-80:])
    ok("25 只剩 C 那一条", q("SELECT id FROM sessions") == [(C,)], q("SELECT id FROM sessions"))
    ok("26 收起的常驻键仍然点得动（另一会话的回归写法）",
       str(d3.get("39-hidden-btn-armed#pred", "")).startswith("YES"), str(d3.get("39-hidden-btn-armed#pred"))[-80:])
    ok("27 那颗键的文案换成了确认", str(d3.get("40-hidden-btn-value") or "").strip() == "⚠ 确认删除？",
       d3.get("40-hidden-btn-value"))
    ok("28 段 3 浏览器侧没有未捕获错误", d3.get("p3-errors-read") in ("[]", '"[]"'), d3.get("p3-errors-read"))
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    FAIL.append("异常 %r" % (exc,))
finally:
    srv.terminate()
    time.sleep(2)
    if srv.poll() is None:
        srv.kill()
    logf.close()

print()
print("断言 %d 条，失败 %d 条" % (N, len(FAIL)))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
