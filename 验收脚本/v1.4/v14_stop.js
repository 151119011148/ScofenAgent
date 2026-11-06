// v1.4 补充实测：在「已经攒了几轮」的旧会话里按 ■ 停止，看累加的内容会不会被半截覆盖掉。
// D5 之后 _respond 的收尾是 base + 半截，v1.3 的停止三条实测都在单题会话上做的，这条没覆盖过。
const PORT = 9333;
const URL = process.env.V14URL || "http://127.0.0.1:7861/";
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
window.__s = {
  ask: (q) => {
    const ta = document.querySelector("textarea"); ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    set.call(ta, q); ta.dispatchEvent(new Event("input", { bubbles: true }));
    const b = document.querySelector("button.submit-button");
    if (b) { b.click(); return "clicked"; } return "no-submit";
  },
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON"; b.click(); return "clicked " + t; },
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]')).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 70)),
  sels: () => Array.from(document.querySelectorAll("#sessions label")).map((l) => (l.innerText || "").trim().slice(0, 30)),
  clickSel: (needle) => {
    const ls = Array.from(document.querySelectorAll("#sessions label"));
    const hit = ls.find((l) => (l.innerText || "").indexOf(needle) >= 0);
    if (!hit) return "NO-SEL"; const inp = hit.querySelector("input"); (inp || hit).click(); return "sel:" + (hit.innerText || "").trim().slice(0, 30);
  },
};
0
`;
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
  console.log("Sels " + JSON.stringify(await evl("__s.sels()")));
  console.log("Select " + await evl(`__s.clickSel("73")`));
  await sleep(3000);
  const before = await evl("__s.rows()");
  console.log("Before " + JSON.stringify(before));
  console.log("Ask " + await evl(`__s.ask("调用 final_answer 写一段 600 字的话，主题是本地沙箱。不要调用其他工具。")`));
  let hit = null;
  for (let i = 0; i < 120; i++) {
    const st = await evl("__s.state()");
    if (st === "生成中") { hit = i; break; }
    await sleep(150);
  }
  console.log("RunningSeen " + hit);
  await sleep(2500);
  const tStop = new Date().toISOString();
  console.log("Stop " + await evl(`__s.click("■ 停止")`) + " at " + tStop);
  for (let i = 0; i < 80; i++) {
    await sleep(700);
    const st = await evl("__s.state()");
    if (st === "已停止" || st === "完成") { console.log("EndState " + st + " after " + i * 0.7 + "s"); break; }
  }
  await sleep(6000);
  console.log("RowsAfterStop " + JSON.stringify(await evl("__s.rows()")));
  console.log("BarAfterStop " + JSON.stringify(await evl(`(document.querySelector("#statusbar")||{}).innerText || ""`)));
  // 停完之后这条会话还能不能接着用
  console.log("Ask2 " + await evl(`__s.ask("调用 final_answer 只回两个字「还能用」。不要调用其他工具。")`));
  for (let i = 0; i < 160; i++) {
    await sleep(1000);
    const st = await evl("__s.state()");
    if ((st === "完成" || st === "已停止") && i > 4) { console.log("Turn2State " + st + " at " + i + "s"); break; }
  }
  await sleep(6000);
  console.log("RowsAfterTurn2 " + JSON.stringify(await evl("__s.rows()")));
  console.log("BarTurn2 " + JSON.stringify(await evl(`(document.querySelector("#statusbar")||{}).innerText || ""`)));
  await send("Page.captureScreenshot", { format: "png" }).then((r) => require("fs").writeFileSync("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14-stop.png", Buffer.from(r.data, "base64"))).catch(() => {});
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
