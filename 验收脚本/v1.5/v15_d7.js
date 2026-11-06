// D7 在线复测：■ 停止落在待批卡出现**之前**（0.2s 那一路），界面还会不会死停在「等待审批」。
// 判据不是"有没有出现卡片"，而是：状态轨迹里有没有 等待审批、多久落到 已停止、
// ✔/✖ 两枚按钮收没收。只读屏 + 点按钮，不改代码。
const PORT = 9333;
const URL = process.env.V15URL || "http://127.0.0.1:7861/";
const WAIT = Number(process.env.V15WAIT || 0.2); // 提问后隔多久按停止（秒）
const OBS = Number(process.env.V15OBS || 25); // 按完停止观察多久（秒）
const TAG = process.env.V15TAG || "stop-at-0.2s";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method, params })); });
}
async function evl(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result && r.result.value;
}
const PAGE = `
window.__d = {
  ask: (q) => {
    const ta = document.querySelector("textarea"); ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    set.call(ta, q); ta.dispatchEvent(new Event("input", { bubbles: true }));
    const b = document.querySelector("button.submit-button");
    if (b) { b.click(); return "clicked"; } return "no-submit";
  },
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON " + t; b.click(); return "clicked " + t; },
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 90)),
  vis: () => Array.from(document.querySelectorAll("#statusrow button")).map((b) => (b.innerText || "").trim() + ":" + (b.offsetParent !== null ? "shown" : "hidden")).join(" | "),
};
"ready";`;
const out = (o) => console.log("D " + JSON.stringify(o));

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) { await sleep(1000); if (await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')")) break; }
  await evl(PAGE);

  const q = "先调用 run_python 一次，代码写 print('D7')，等到工具返回后再用 final_answer 把返回贴出来。";
  const t0 = Date.now();
  out({ tag: TAG, ev: "ask", sent: await evl(`__d.ask(${JSON.stringify(q)})`), at: new Date().toISOString() });
  await sleep(WAIT * 1000);
  out({ ev: "beforeStop", state: await evl("__d.state()"), cards: await evl("__d.cards()"), vis: await evl("__d.vis()"), secs: ((Date.now() - t0) / 1000).toFixed(1) });
  out({ ev: "stop", r: await evl(`__d.click("■ 停止")`), at: new Date().toISOString() });

  const traj = [], seenAwaiting = [];
  let settledAt = null;
  for (let i = 0; i < OBS * 2; i++) {
    await sleep(500);
    const st = await evl("__d.state()");
    const cs = await evl("__d.cards()");
    const secs = Number(((Date.now() - t0) / 1000).toFixed(1));
    const last = traj[traj.length - 1];
    if (!last || last.state !== st || secs - last.secs >= 5) traj.push({ secs, state: st, late: cs.filter((c) => c.indexOf("待批") >= 0).length });
    if (st === "等待审批") seenAwaiting.push(secs);
    if (settledAt === null && st !== "等待审批" && st !== "停止中" && st !== "生成中" && secs > WAIT + 0.4) settledAt = secs;
  }
  out({
    tag: TAG, ev: "final", settledAt, awaitingSeen: seenAwaiting.length, awaitingAt: seenAwaiting.slice(0, 6),
    state: await evl("__d.state()"), bar: await evl("__d.bar()"),
    cards: await evl("__d.cards()"), vis: await evl("__d.vis()"),
  });
  out({ tag: TAG, ev: "traj", traj });
  await send("Page.captureScreenshot", { format: "png" }).then((r) => require("fs").writeFileSync("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15-d7-" + TAG + ".png", Buffer.from(r.data, "base64"))).catch(() => {});
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
