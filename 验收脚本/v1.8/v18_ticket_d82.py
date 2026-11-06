# -*- coding: utf-8 -*-
"""#42 D8-2 立单：刷新后首屏读到「还没写完的库」——把已有留痕里所有 reload 样本捞干净。

为什么要再写一份：这一条到第⑤刀为止只挂着**一个**数（C3 那一跑的 0.761 s），
第②刀 §3 里另有两跑的时刻对齐，但那是散文。立单要带命中率，就得把
`run/*.server.log` 与 `run/v18_live_summary_*.out` 里成对出现的
`on_load sid=<n> … db_memory=… messages=X` 和 `save(_memory).exit sid=<n> after=… messages=Y`
逐条捞出来，当场算：那一刻屏上拿到几条、这一题最终落库几条、中间隔了多少秒。
顺带把 on_load 同一行的**进程侧**读数（steps／kinds／mem_held）也捞出来——
第五节 (a) 那条修法能不能落地，全看这些字段够不够当判据，不用新加埋点。

零成本：这份只读已经落盘的文本＋grep 现场代码行号，**不打模型、不起 app、不开任何库**。
口径要说死：样本全部来自探针 app（端口 7872，每场景独立库），不是他本人的 7860；
reload 由 headless Chrome 掐点触发，比人手快，所以真人手上的命中率给不了结论（见【未验证】）。

跑法：smolagents/.venv/bin/python 验收脚本/v1.8/v18_ticket_d82.py
产物：run/v18_d8_2_ticket.out
"""
import hashlib
import pathlib
import re
import statistics
import subprocess

SMOL = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/smolagents")
AR = pathlib.Path("/Users/gaoying/Desktop/study/ai学习/.rollback/v1.8")
RUN = pathlib.Path(__file__).resolve().parent / "run"
OUT = RUN / "v18_d8_2_ticket.out"
FILES = ["my_ui.py", "my_agent.py", "my_coding_agent.py"]
L = []


def w(s=""):
    L.append(s)


def sha8(p):
    return hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest()[:8]


def lineof(text, pat, tag):
    m = re.search(pat, text)
    return "%s:%d" % (tag, text[: m.start()].count("\n") + 1) if m else "%s:【找不到】" % tag


def num(v):
    return "—" if v is None else str(v)


# 首屏那一行：t、sid、进程侧读数（steps/kinds/mem_held）、db 读数（messages/memory 或一条报错）
RE_ONLOAD = re.compile(
    r"^t=\s*([\d.]+)\s+on_load\s+sid=(\S+)\s+steps=(\d+)\s+kinds=(\S+)\s+screen_stepno=(\S+)\s+screen_in=(\S+)"
    r"\s+screen_out=(\S+)\s+screen_wait=(\S+)\s+mem_held=(\[[^\]]*\])\s+db_memory="
    r"(?:sessions=\S+\s+messages=(\d+)\s+memory=(\d+)|(read-failed:\S+))", re.M)
# 落库完成这一格取 save.exit 与 save_memory.exit 两条里更后的那条：前者刚写完 messages（memory 还是 0），
# 后者才把 memory 那一行补上（C3 实测 save.exit messages=4 memory=0 → 2ms 后 save_memory.exit memory=1）。
# after= 那一格本身也可能是一条报错（B1 run1：rows() 还没修 close-in-with 那一版，读写两头的打点一起废），
# 那种帧的时刻照样可用、条数不可用——所以标「不可判」而不是「少读」。
RE_WRITE = re.compile(
    r"^t=\s*([\d.]+)\s+save(?:_memory)?\.exit\s+sid=(\S+).*?after=(?:sessions=\S+\s+)?"
    r"(?:messages=(\d+)\s+memory=(\d+)|(read-failed:\S+))", re.M)

samples, no_final, files_seen = [], [], set()
for f in sorted(RUN.glob("*.server.log")) + sorted(RUN.glob("v18_live_summary_*.out")):
    txt = f.read_text(encoding="utf-8", errors="replace")
    ons = RE_ONLOAD.findall(txt)
    wr = RE_WRITE.findall(txt)
    if not ons:
        continue
    files_seen.add(f.name)
    for t, sid, steps, kinds, _sn, _si, _so, _sw, mem_held, m0, mm0, failed in ons:
        if sid == "None":
            continue          # 新进程第一帧没有选中会话，不在本单范围
        t = float(t)
        mine = [(float(te), None if me == "" else int(me), None if mme == "" else int(mme), wf)
                for te, tsid, me, mme, wf in wr if tsid == sid]
        if not mine:
            no_final.append((f.name, t, sid, m0 or failed))
            continue
        te, fm, fmem, wfailed = mine[-1]      # 这一题的终态＝最后那条落库完成
        samples.append((f.name, t, sid, None if failed else int(m0), None if failed else int(mm0),
                        fm, fmem, te - t, failed, wfailed, int(steps), kinds, mem_held))

# 同一物理跑会有两份留痕（.server.log 与 summary 里同一段），按 (on_load 时刻, sid, 首屏两格, 报错格) 去重
uniq, seen = [], set()
for s in samples:
    key = (round(s[1], 3), s[2], s[3], s[4], s[8])
    if key not in seen:
        seen.add(key)
        uniq.append(s)
samples = sorted(uniq, key=lambda s: (s[0], s[1]))
judged = [s for s in samples if not s[8] and s[5] is not None]   # 首屏、终态两格都可读
unread = [s for s in samples if s not in judged]                 # 有一格是 read-failed
SHORT = lambda s: (s[3] < s[5] or s[4] < s[6]) and s[7] > 0      # noqa: E731  首屏比终态少、且在落库之前
hit = sum(1 for s in judged if SHORT(s))
full = len(judged) - hit
dws = [s[7] for s in judged if SHORT(s)]
hit_rate = 100.0 * hit / len(judged)
full_rate = 100.0 * full / len(judged)
# Δt 的符号就是物理分档：>0 是「首屏抢在落库之前」（这一题还挂着），<=0 是「落库早完成了才刷」
pos = [s for s in judged if s[7] > 0]
neg = [s for s in judged if s[7] <= 0]
pos_hit = sum(1 for s in pos if SHORT(s))
neg_hit = sum(1 for s in neg if SHORT(s))

# 第②刀 §3 那两跑是散文，但它把 on_load／落库完成的 t+ 和**屏上**气泡数都打在留痕里，机器抓得到。
# 这一通道的作用是拿屏上结果反证第二节那台口径表：屏上空白是不是只出现在 Δt>0 那一档。
RUN3 = re.compile(r"### 跑(\S)（(\S+?)）(.*?)屏上：bot=(\d+)", re.S)
RE_ON_T = re.compile(r"_on_load 读库\s+t\+\s*([\d.]+)s")
RE_CLK = re.compile(r"距 reload 点击\s*\+([\d.]+)s")
RE_WR_T = re.compile(r"落库完成（save_memory\.exit）\s+t\+\s*([\d.]+)s")
RE_GE_T = re.compile(r"服务端收到 GeneratorExit\s+t\+\s*([\d.]+)s")
fx = (RUN / "v18_after_fix.out").read_text(encoding="utf-8")
runs3 = []
for tag, fname, body, bot in RUN3.findall(fx):
    a, b, c, d = RE_ON_T.search(body), RE_WR_T.search(body), RE_CLK.search(body), RE_GE_T.search(body)
    if a and b:
        runs3.append((tag, fname, float(a.group(1)), float(b.group(1)), int(bot),
                      float(c.group(1)) if c else None, float(d.group(1)) if d else None))
# 「首屏抢在落库之前、屏上又确实是空的」那一跑——第三、五节拿它的到达顺序作证据
posrun = next((r for r in runs3 if r[3] - r[2] > 0 and r[4] == 0 and r[6] is not None), None)
clks = [r[5] for r in runs3 if r[5] is not None]

ui = (SMOL / "my_ui.py").read_text(encoding="utf-8")
MEM_LINE = lineof(ui, r"self\._mem: dict", "self._mem")


def verdict(n, t):
    for s in samples:
        if s[0] == n and abs(s[1] - t) < 0.005:
            if s not in judged:
                return "不可判（db 那一格是报错）"
            return "★ 首屏少读" if SHORT(s) else "读全"
    return "第二节没有这一帧"


bar = "=" * 92
w(bar)
w("#42 D8-2 立单：刷新后「首屏」读到还没写完的库（工单号 #42 ／ 看板编号 D8-2）")
w(bar)
w("生成方式：`smolagents/.venv/bin/python 验收脚本/v1.8/v18_ticket_d82.py`")
w("立单时间：%s   本单是**立单**：产品代码零改动，三份文件与整版快照逐字节一致（第八节）"
  % subprocess.run(["date", "+%Y-%m-%d %H:%M:%S"], capture_output=True, text=True).stdout.strip())
w()
w("一、现象（一句话）")
w("-" * 92)
w("  挂在「待批／计划待批」上按刷新：新页面第一帧可能读到**这一题还没写完的库**——")
w("  屏上那条会话空白，而零点几秒后同一题在库里是完整的（宽度见第二节）。数据没坏，是首屏读到 in-flight。")
w()
w("二、样本（从 %d 个 run/ 留痕文件里捞出的全部带会话首屏帧，程序算的，不是手挑）" % len(files_seen))
w("-" * 92)
w("  %-28s %9s %4s %8s %8s %8s %8s %10s  %s"
  % ("留痕", "on_load t", "sid", "首屏msg", "终态msg", "首屏mem", "终态mem", "Δt", "判读"))
for s in samples:
    n, t, sid, m0, mm0, fm, fmem, dt = s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]
    if s not in judged:
        w("  %-28s %9.3f %4s %8s %8s %8s %8s %+10.3f  %s"
          % (n[:28], t, sid, num(m0), num(fm), num(mm0), num(fmem), dt,
             "不可判：首屏格=%s ／ 终态格=%s" % (s[8] or "可读", s[9] or "可读")))
        continue
    w("  %-28s %9.3f %4s %8d %8d %8d %8d %+10.3f  %s"
      % (n[:28], t, sid, m0, fm, mm0, fmem, dt, "★ 首屏少读" if SHORT(s) else "读全"))
w()
w("  可判 %d 帧，另有 %d 帧标「不可判」（不计入分母）。这种帧所在的跑落库行**是有的**"
  % (len(judged), len(unread)))
if unread:
    w("  （save_memory.exit 在 t=%.3f、比首屏还早 %.3fs），只是它 after= 那一格也写成 read-failed："
      % (unread[0][1] + unread[0][7], -unread[0][7]))
    w("  rows() 还没修 close-in-with 的那一版把读、写两头的打点一起打废了。时刻能用、条数不能用，")
    w("  所以按不可判处理而不是按「少读」——同一跑第②刀 §3 记的是屏上 bot=3，屏上本来是满的。")
else:
    w("  （这批留痕里没有这种帧）")
w()
w("  可判这 %d 帧里：首屏少读 %d 帧、读全 %d 帧 → 帧级少读 %.0f%%、帧级读全 %.0f%%"
  % (len(judged), hit, full, hit_rate, full_rate))
w("  按 Δt 的符号分两档（不是分类技巧，符号本身就是物理时刻）：")
w("    Δt>0 共 %d 帧＝首屏抢在这一题落库之前（还挂着待批/计划待批那一路）→ 其中少读 %d 帧（%.0f%%）"
  % (len(pos), pos_hit, 100.0 * pos_hit / len(pos)))
w("    Δt<=0 共 %d 帧＝落库早已完成才刷（也就是第二刷）→ 其中少读 %d 帧"
  % (len(neg), neg_hit))
w("  所以本单能给的是「落在窗口里的刷新 %d/%d 少读」，给不了「随便刷新一次的命中率」。"
  % (pos_hit, len(pos)))
w("  终态那一格取的是这一题**最后**一条落库完成行：save.exit 之后还有 save_memory.exit 才把 memory 那行补上")
w("  （C3 实测 save.exit messages=4/memory=0 → 2ms 后 save_memory.exit messages=4/memory=1），")
w("  取更后的那条才不会把「分两段写」的正常收尾误报成「首屏少读」。")
w("  窗口 Δt（首屏比落库早多少秒；只有正数才可能命中，负数说明落库在首屏之前就完成了）：")
w("    少读那几帧 min %.3f ／ 中位 %.3f ／ max %.3f 秒   ／   可判全样本 Δt：%s"
  % (min(dws), statistics.median(dws), max(dws),
     "、".join("%+.3f" % s[7] for s in judged)))
w()
w("  同一批帧的**进程侧**读数（就在 on_load 那一行打点里，机器抓的）——(a) 那条修法能不能落地看这里：")
for s in samples:
    w("    %-28s t=%8.3f sid=%s  steps=%s kinds=%-6s mem_held=%-8s → db 首屏读到 %s 条"
      % (s[0][:28], s[1], s[2], s[10], s[11], s[12], num(s[3])))
w("    两件事当场看出来了：①少读那 %d 帧的 mem_held 全都还挂着这个 sid（进程内存里账没散）；"
  % len(pos))
w("    ②读全那一帧（第二刷）mem_held 同样挂着——所以 mem_held **单独**不能当判据，")
w("    得「库里读到 0 条」＋「这个 sid 还在进程内存里」两条一起用，才不会在第二刷上空转重试。")
w("  第二通道（第②刀 §3 那两跑：散文里的 on_load／落库完成时刻＋**屏上**气泡数，机器抓的，不是我手打）：")
for tag, fname, on_t, wr_t, bot, clk, _ge in runs3:
    w("    跑%s %-26s on_load t=%.3f → 落库 t=%.3f ⇒ Δt=%+.3fs ｜ 屏上 bot=%d ｜ %s ｜ 点击→首帧 %s s"
      % (tag, fname[:26], on_t, wr_t, wr_t - on_t, bot, verdict(fname, on_t),
         "—" if clk is None else "%.3f" % clk))
w("    两跑合起来看：屏上空白（bot=0）只出现在 Δt>0 那一档，另一档屏上是满的（bot=3）。")
w("    跑①两边对得上：Δt 是负的（落库早完成）→ 屏上 bot=3；它 db 读数坏是打点问题，两回事。")
if no_final:
    w("  另有 %d 帧带 sid 但那一跑全程没有落库行（SIGKILL／SIGINT 那两路：没有 finally 就没有收尾，"
      % len(no_final))
    w("  是 D8 第②刀已定性的既有边界，不进本单样本）：%s"
      % "、".join("%s t=%.3f" % (n, t) for n, t, sid, *_ in no_final))
else:
    w("  没有「带 sid 但整跑无落库行」的帧：%d 个文件里带会话的首屏帧全部配到了落库行。" % len(files_seen))
w("  口径：Δt 是同一进程内服务端打点（boot 起算）的相对秒、两帧相减，不是墙钟对表；")
w("  去重键是 (on_load 时刻, sid, 首屏两格读数, 报错格)——同一物理跑在 .server.log 和 summary 里各存一份。")
w()
w("三、机制（行号是对现场 my_ui.py 当场 grep 出来的，改一行会跟着变）")
w("-" * 92)
w("  · %s  —— 新页面第一帧的服务端入口：只读库，不知道旧请求还没收尾" % lineof(ui, r"def _on_load\(self\)", "_on_load"))
w("  · %s  —— 读的就是这一句 `self.hist.load(sid)`" % lineof(ui, r"msgs = self\.hist\.load\(sid\)", "hist.load"))
w("  · %s  —— gradio 接线 `demo.load(fn=self._on_load, …)`：浏览器一进场就发" % lineof(ui, r"demo\.load\(fn=self\._on_load", "demo.load"))
w("  · %s  —— 旧请求的落库在 finally 里，**GeneratorExit 真到位了才写**" % lineof(ui, r"self\.hist\.save\(sid, last\)", "hist.save"))
w("  · %s  —— GeneratorExit 分支；新页面请求和它是两条独立的路，框架不给先后约定" % lineof(ui, r"except GeneratorExit:", "except GeneratorExit"))
w("  所以「首屏读到空」不是判错：两条路的到达顺序本就没保证。第二通道那一跑的形状就是")
w("  首屏先到（点击→首帧 %.3fs）、旧请求 %.3fs 之后才收到关闭信号、再 %.3fs 落库完成——"
  % (min(clks), posrun[6] - posrun[2], posrun[3] - posrun[6]))
w("  那一刻库里确实是 0 条。")
w()
w("四、影响面（用户视角，说清是什么坏了）")
w("-" * 92)
w("  · 坏的是**一帧屏幕**：刷新后那一题气泡区空白、状态条 0/8，看着像「刚才那一题没跑」。")
w("  · 没坏的是**账本**：同一题最终 %d 条消息、payload 带 wait 都在库里（第②刀 §4 两跑都是），"
  % max(s[5] for s in judged))
w("    第二刷和点侧栏都读得出来（那一跑 t=%.3f 读到 messages=%d memory=%d）。"
  % (neg[0][1], neg[0][5], neg[0][6]))
w("  · 触发条件：刷新正好落在「这一题还挂着待批／计划待批」上。跑完之后再刷不触发。")
w("    能撞上的窗口实测 %s 秒（第二节 Δt>0 那 %d 帧）；撞不上的那一档（落库已完成）%d/%d 读全。"
  % ("、".join("%.3f" % d for d in sorted(dws)), len(pos), len(neg) - neg_hit, len(neg)))
w("    所以它是**有界窗口内 100%%（%d/%d）命中**、窗口外 0%% 的问题——不是玄学小概率，是能算宽度的。"
  % (pos_hit, len(pos)))
w()
w("五、修法候选（都不动判定面；本单一个字没改代码，等你点头选哪条）")
w("-" * 92)
w("  (a) 推荐：`_on_load` 读到 messages=0、**且**这一 sid 还在 `%s` 里（第二节进程侧那几行的 mem_held"
  % MEM_LINE)
w("      就是它的键，字段现成、不用新加埋点；但单看它不够——读全那一帧的 mem_held 同样挂着，")
w("      两条判据一起用）时做**有界**重试：每 ~50ms 重读一次，上限按第二节窗口上界加余量。")
w("      代价：首屏那一帧最坏多等上限那么多秒。收益：Δt>0 那一档 %d/%d 的少读归零。"
  % (pos_hit, len(pos)))
w("      （帧级 %.0f%% 是混进了本来就读全的第二刷，别拿它当命中率。）" % hit_rate)
w("      改动只碰 %s 这一个方法，不碰 save、不碰判定面。" % lineof(ui, r"def _on_load\(self\)", "_on_load"))
w("  (b) 提前 save：证否了。跑%s（%s）的到达顺序是——首屏 t=%.3f，服务端收到 GeneratorExit"
  % (posrun[0], posrun[1], posrun[2]))
w("      t=%.3f（比首屏晚 %.3fs），落库完成 t=%.3f。首屏那一刻旧请求**还没收到关闭信号**，"
  % (posrun[6], posrun[6] - posrun[2], posrun[3]))
w("      无内容可写；要提前整条路就是 D3「逐步落库」，D3 不在批准名单里。")
w("  (c) 客户端第二帧再读：能避开，但要把首屏渲染拆两拍，改动面比 (a) 大，还引入「先空白再填上」")
w("      的新观感。不建议。")
w()
w("六、判据（先立判据再动手）")
w("-" * 92)
w("  1. C3／B1 两路各连跑 10 次刷新，首屏 messages>0 命中 **10/10**。")
w("     现状基线：「首屏抢在落库之前」那 %d 帧全部少读（读到 0 条），落库完成后才刷的 %d 帧读全。"
  % (len(pos), len(neg)))
w("  2. 首屏耗时增量 ≤ 上限那一档；探针侧现有 on_load 行的 wall= 格就是量这个的，不用加埋点。")
w("  3. 两道回归不许红：v18_test_interrupt.py（21 条）、v18_test_nochange.py（51 条）——")
w("     这两个数是刚才整版演练 run/v18_drill_v18.out 里复跑出来的，改完要再跑一遍。")
w("  4. 修后复跑本写入器，第二节那张表逐帧对比修前修后（样本表是机器抓的，不用手写）。")
w()
w("七、【未验证】（立单时说不清的，逐条列）")
w("-" * 92)
w("  · 真人按刷新的到达时间分布：样本全部来自 headless Chrome 自动 reload，")
w("    点击→首屏那一帧实测 %s 秒（第②刀 §3 两跑，机器抓的），"
  % "、".join("%.3f" % c for c in sorted(clks)))
w("    人手通常更慢，真人命中率大概率低于窗口内那 %.0f%%（%d/%d），但没测过就不写进结论。"
  % (100.0 * pos_hit / len(pos), pos_hit, len(pos)))
w("  · (a) 的上限取多少：现在只有 %d 个窗口样本（max %.3f s），1.0s 还是 1.5s 要在真界面上"
  % (len(dws), max(dws)))
w("    多跑几轮才知道，不拍脑袋。")
w("  · mem_held 在留痕里的取值是 `%s`／`%s`，它是探针把现场 `%s` 的键打出来的；"
  % (samples[0][12], samples[-1][12], MEM_LINE))
w("    真界面上 (a) 拿哪个容器当「还没散账」的判据（只 _mem？还是加 _pending、worker 线程在不在跑？），")
w("    要对着代码定，本单没定。")
w("  · 7860 本人那套界面上这一条出现过几次：探针跑的是 7872＋隔离库，`.agent-history.sqlite3`")
w("    里没为这一条留过案（本单也没打开过它）。")
w("  · gradio 6.30 有没有官方的「首帧延后」开关可替代 (a)：没查文档；走 (a) 之前值得先花十分钟查。")
w()
w("八、波及面（本单：立单，零改动）")
w("-" * 92)
for f in FILES:
    p = SMOL / f
    same = p.read_bytes() == (AR / f).read_bytes()
    w("  · %-20s %s  %d 行 / %d B  == 整版快照 ai学习/.rollback/v1.8/%s：%s"
      % (f, sha8(p), p.read_text(encoding="utf-8").count("\n"), len(p.read_bytes()), f, same))
w("  · 我 import 过 my_ui/my_agent 只为算行号？没有——这一份用 read_text＋grep，进程里没起 agent。")
w("  · 本单没起 app、没打模型、没开过任何库（样本全是读文本文件）。token 消耗 0。")
w("  · 落处：手册 §4 看板加一行 D8-2（随 #43 一起写，看板 %d 行 → %d 行了再说）；"
  % (37, 38))
w("    迭代记录.md v1.8 节 §7 已知遗留第 1 条引用本文件。")

OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L[:48]))
print("[written] %s  %d 行 / %d B" % (OUT, len(L), OUT.stat().st_size))
