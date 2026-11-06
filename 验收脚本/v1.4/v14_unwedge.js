// 接上一条实测的现场：■ 停止 落在待批卡出现之前，队列里留了一条没人结算的待批。
// 这里补点 ✖ 拒绝，看它能不能把那条挂住的 worker 解出来、并且停在步边界。
const PORT = 9333;
const URL = "http://127.0.0.1:7861/";
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
async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) { await sleep(1000); if (await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')")) break; }
  await evl(`window.__u = {
  vis: () => Array.from(document.querySelectorAll("#statusrow button")).map((b) => (b.innerText || "").trim() + ":" + (b.offsetParent !== null ? "shown" : "hidden")).join(" | "),
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON " + t; b.click(); return "clicked " + t + " at " + new Date().toISOString(); },
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 80)),
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]')).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 60)),
}; "ready";`);
  await sleep(2500);
  console.log("Vis " + await evl("__u.vis()"));
  console.log(await evl(`__u.click("✖ 拒绝")`));
  let end = null;
  for (let i = 0; i < 200; i++) {
    await sleep(500);
    const st = await evl("__u.state()");
    if (st !== "等待审批" && st !== "停止中" && st !== "生成中") { end = { st, after: i * 0.5 }; break; }
  }
  console.log("End " + JSON.stringify(end));
  await sleep(6000);
  console.log("Cards " + JSON.stringify(await evl("__u.cards()")));
  console.log("Bar " + JSON.stringify(await evl("__u.bar()")));
  console.log("Rows " + JSON.stringify(await evl("__u.rows()")));
  await send("Page.captureScreenshot", { format: "png" }).then((r) => require("fs").writeFileSync("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.4/run/v14-deny-after-stop.png", Buffer.from(r.data, "base64"))).catch(() => {});
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
