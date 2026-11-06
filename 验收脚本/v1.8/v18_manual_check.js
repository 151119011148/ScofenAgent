// 文档闸·浏览器闸（v1.8）：把手册真在 Chrome 里打开，读渲染后的看板。
//
// 用法：node 验收脚本/v1.8/v18_manual_check.js <视口宽> <标签> [<被检 HTML 的绝对路径>]
//   node .../v18_manual_check.js 1440 1440   → run/v18_manual_gate_1440.out ＋ run/v18-manual.png
//   node .../v18_manual_check.js 1180 1180   → run/v18_manual_gate_1180.out ＋ run/v18-manual-1180.png
//   第三个参数只给**负控**用（`v18_gate_neg.py` 拿一份故意改坏的副本验「这闸会不会红」）。
//
// 为什么必须真打开：静态闸只能证明标签配对与锚点存在，证不出「点筛选器之后 #cnt 那串字
// 和真正看得见的行数一致」——那一格是 JS 现算的，也是 v1.7 页眉漏改那类错唯一抓得住的地方
// （title 打在浏览器输出里才看得见）。
//
// 表达式送进浏览器的方式沿用 v1.6/v1.7：整段 helpers 先 base64，再 eval(atob(...)) 解开执行。
// 原因是实测踩到的：把带双引号的 CSS 选择器拼进单引号 JS 字符串再送 CDP，
// 同一个表达式换个写法就报 SyntaxError: missing ) after argument list。
// atob 给的是 latin1 字符串，中文会变 mojibake，所以按字节还原成 UTF-8 再 eval。
//
// 端口 9344 ＋ 独立 profile：9333 上是**另一个会话**留着的那台 scratch Chrome（PID 89164），
// 7860 上是他交付形态的 Agent（PID 80159）——两个都不碰，本机所有断言都走自己起的这一台。
const PORT = 9344;
const WIDTH = parseInt(process.argv[2] || "1440", 10);
const TAG = process.argv[3] || String(WIDTH);
const RUN = "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.8/run";
const FILE = process.argv[4] || "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html";
const URL = "file://" + encodeURI(FILE);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 本轮的期望值：41 行看板 ＋ 两分布 ＋ 十个筛选器的可见行数
const EXPECT = {
  version: "v1.8",
  rows: 41,
  st: { todo: 17, doing: 0, done: 21, na: 3 },
  kinds: { all: 41, bug: 9, p0: 6, p1: 10, p2: 7, v: 9, todo: 17, doing: 0, done: 21, na: 3 },
};
const fails = [];
function want(label, got, exp) {
  const ok = JSON.stringify(got) === JSON.stringify(exp);
  if (!ok) fails.push(label + " 期望 " + JSON.stringify(exp) + " 实得 " + JSON.stringify(got));
  console.log((ok ? "  ok  " : "  FAIL ") + label + " = " + JSON.stringify(got) + (ok ? "" : "（期望 " + JSON.stringify(exp) + "）"));
}

let ws, id = 0;
const pending = new Map();
function raw(m, p = {}) {
  return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); });
}
async function evl(expr) {
  // raw() 递回的是整条 CDP 报文，值在 msg.result.result.value，别按 msg.result.value 取
  const msg = await raw("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (msg && msg.error) throw new Error("CDP " + JSON.stringify(msg.error).slice(0, 300));
  const r = (msg && msg.result) || {};
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result && r.result.value;
}
async function call(name, ...args) {
  return evl("__v18m." + name + "(" + args.map((a) => JSON.stringify(a)).join(",") + ")");
}
async function inject() {
  const b64 = Buffer.from(HELPERS, "utf8").toString("base64");
  return evl("eval(new TextDecoder().decode(Uint8Array.from(atob('" + b64 + "'),(c)=>c.charCodeAt(0))))");
}

const HELPERS = `
window.__v18m = {
  kinds: ["all","bug","p0","p1","p2","v","todo","doing","done","na"],
  filters: () => {
    const out = [];
    for (const k of __v18m.kinds) {
      const b = document.querySelector('.bar button[onclick*=' + JSON.stringify(k) + ']');
      if (!b) { out.push(JSON.stringify([k, "NO-BUTTON", -1, -1])); continue; }
      b.click();
      let shown = 0;
      for (const r of document.querySelectorAll("tr[data-st]")) if (r.offsetParent !== null) shown++;
      const c = document.getElementById("cnt");
      out.push(JSON.stringify([k, c ? c.textContent.trim() : "no-#cnt", shown,
                               document.querySelectorAll("tr[data-st]").length]));
    }
    return "[" + out.join(",") + "]";
  },
  layout: () => {
    const de = document.documentElement, bar = document.querySelector(".bar");
    return JSON.stringify({
      title: document.title,
      rows: document.querySelectorAll("tr[data-st]").length,
      tables: document.querySelectorAll("table").length,
      inner: de.clientWidth, scrollW: de.scrollWidth,
      overflowX: de.scrollWidth > de.clientWidth,
      barWrap: bar ? getComputedStyle(bar).flexWrap : "no-bar",
    });
  },
  stcount: () => {
    const m = { todo: 0, doing: 0, done: 0, na: 0 };
    for (const r of document.querySelectorAll("tr[data-st]")) { const k = r.getAttribute("data-st"); m[k] = (m[k] || 0) + 1; }
    return JSON.stringify(m);
  },
  pcount: () => {
    const m = {};
    for (const r of document.querySelectorAll("tr[data-st]")) { const k = r.getAttribute("data-p"); m[k] = (m[k] || 0) + 1; }
    return JSON.stringify(m);
  },
  pill: (key) => {
    for (const r of document.querySelectorAll("tr[data-st]")) {
      const t0 = r.querySelector("td");
      if (t0 && t0.innerText.trim().indexOf(key) === 0) {
        const last = r.querySelector("td:last-child");
        return JSON.stringify([key, r.getAttribute("data-st"), r.getAttribute("data-p"),
                               last ? last.innerText.trim().replace(/\\s+/g, " ").slice(0, 60) : "none"]);
      }
    }
    return JSON.stringify([key, "ROW-NOT-FOUND"]);
  },
  sec6: () => JSON.stringify(Array.from(document.querySelectorAll("h3"))
      .filter((h) => h.textContent.trim().indexOf("6.") === 0)
      .map((h) => h.textContent.trim().slice(0, 46))),
  anchors: () => {
    const bad = [];
    for (const a of document.querySelectorAll('a[href^="#"]')) {
      const idv = a.getAttribute("href").slice(1);
      if (!document.getElementById(idv)) bad.push(idv);
    }
    return JSON.stringify(bad);
  },
};
true;
`;

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await raw("Runtime.enable");
  await raw("Page.enable");
  await raw("Emulation.setDeviceMetricsOverride",
    { width: WIDTH, height: 960, deviceScaleFactor: 1, mobile: false });
  await raw("Page.navigate", { url: URL });
  let ready = 0;
  for (let i = 0; i < 40; i++) {
    await sleep(500);
    ready = await evl("document.querySelectorAll('tr[data-st]').length");
    if (ready > 0) break;
  }
  console.log("视口 " + WIDTH + "｜URL " + URL + "｜rows " + ready);
  if (!ready) throw new Error("页面没渲染出看板行");
  await inject();

  const layout = JSON.parse(await call("layout"));
  console.log("LAYOUT " + JSON.stringify(layout));
  want("title 带本轮版本号", layout.title.indexOf(EXPECT.version) >= 0, true);
  want("看板行数", layout.rows, EXPECT.rows);
  want("横向滚动 overflowX", layout.overflowX, false);
  want("筛选器不换行挤爆（barWrap 允许 wrap）", layout.barWrap === "wrap", true);

  want("data-st 分布", JSON.parse(await call("stcount")), EXPECT.st);
  const p = JSON.parse(await call("pcount"));
  console.log("  info  data-p 分布 = " + JSON.stringify(p)
              + "（合计 " + Object.values(p).reduce((a, b) => a + b, 0) + "）");
  want("data-p 合计等于行数", Object.values(p).reduce((a, b) => a + b, 0), EXPECT.rows);

  console.log("FILTERS");
  for (const row of JSON.parse(await call("filters"))) {
    const [k, cnt, shown, total] = row;
    const expShown = EXPECT.kinds[k];
    const expCnt = "显示 " + expShown + " / " + EXPECT.rows + " 条";
    const ok = shown === expShown && cnt === expCnt;
    if (!ok) fails.push("筛选器 " + k + " 可见行 " + shown + "（期望 " + expShown
                        + "）／#cnt「" + cnt + "」（期望「" + expCnt + "」）");
    console.log((ok ? "  ok  " : "  FAIL ") + (k + "     ").slice(0, 5) + " | cnt=「" + cnt + "」 | 可见行=" + shown
                + " | 期望 " + expShown);
  }

  console.log("PILLS（只记录，状态由工单那边判）");
  for (const k of ["D8", "D8-2", "P0-4", "P1-22", "P1-23", "V9", "V8"]) console.log("  " + (await call("pill", k)));
  console.log("SEC6 " + (await call("sec6")));
  want("死锚点", JSON.parse(await call("anchors")), []);

  const s = await raw("Page.captureScreenshot", { format: "png" });
  const shot = RUN + "/v18-manual" + (TAG === "1440" ? "" : "-" + TAG) + ".png";
  require("fs").writeFileSync(shot, Buffer.from((s.result || s).data, "base64"));
  console.log("SHOT " + shot + " " + require("fs").statSync(shot).size + " B");
  ws.close();
  if (fails.length) {
    console.log("---- 浏览器闸判红 " + fails.length + " 条 ----");
    for (const f of fails) console.log("  " + f);
    process.exit(1);
  }
  console.log("---- 浏览器闸全绿（视口 " + WIDTH + "）----");
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
