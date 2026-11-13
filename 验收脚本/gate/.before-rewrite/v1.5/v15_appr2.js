// 接着上一枪：同一个浏览器目标、不重新导航，把仍在等待的那张待批卡点掉。
const PORT = 9333;
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
window.__a = {
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON " + t; b.click(); return "clicked " + t; },
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").replace(/\\n/g, " ").slice(0, 200)),
  vis: () => Array.from(document.querySelectorAll("#statusrow button")).map((b) => (b.innerText || "").trim() + ":" + (b.offsetParent !== null ? "shown" : "hidden")).join(" | "),
};
"ready";`;
const out = (o) => console.log("B " + JSON.stringify(o));

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable");
  await evl(PAGE);
  const t0 = Date.now();
  out({ ev: "before", state: await evl("__a.state()"), vis: await evl("__a.vis()"), bar: await evl("__a.bar()") });
  out({ ev: "approve", clicked: await evl('__a.click("✔ 允许")'), at: new Date().toISOString() });
  let done = null;
  for (let i = 0; i < 150; i++) {
    await sleep(1000);
    const st = String(await evl("__a.state()"));
    if (!/生成中|等待审批|停止中/.test(st)) { done = { st, secs: ((Date.now() - t0) / 1000).toFixed(1) }; break; }
  }
  await sleep(7000);
  out({ ev: "final", done, bar: await evl("__a.bar()"), cards: await evl("__a.cards()").then((c) => c.slice(-3)) });
  const r = await send("Page.captureScreenshot", { format: "png" });
  require("fs").writeFileSync("/tmp/v15-deliver-approve2.png", Buffer.from(r.data, "base64"));
  out({ ev: "shot", path: "/tmp/v15-deliver-approve2.png" });
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
