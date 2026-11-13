// V6 补一条腿：重启后**刷新页面**（走 _on_load 那条自动指最近一条的路径），再点侧栏的 73 那条旧会话，
// 问「再把那个数字回一次」——问题必须落进那条旧会话，且答 73。
// 顺带把 v1.4 记在案的那条「侧栏选中态与 sid 不同步」量清楚：每次点击前后都读每个 label 的 checked。
const PORT = 9333;
const URL = process.env.V15URL || "http://127.0.0.1:7861/";
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
const SRC = `
window.__L = {
  ask: (q) => {
    const ta = document.querySelector("textarea"); ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    set.call(ta, q); ta.dispatchEvent(new Event("input", { bubbles: true }));
    const b = document.querySelector("button.submit-button");
    if (b) { b.click(); return "clicked"; } return "no-submit";
  },
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  running: () => { const t = (document.querySelector("#statusbar") || {}).innerText || ""; return t.indexOf("生成中") >= 0 || t.indexOf("等待审批") >= 0 || t.indexOf("停止中") >= 0; },
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]')).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 60)),
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 90)),
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON " + t; b.click(); return "clicked " + t; },
  selDetail: () => Array.from(document.querySelectorAll("#sessions label")).map((l) => {
      const i = l.querySelector("input");
      return "[" + (l.innerText || "").trim().slice(0, 12) + "]" + (i ? (i.checked ? "checked" : "-") : "?") + (i && i.checked ? "#" + i.value : "");
    }).join(" "),
  clickSel: (needle) => {
    const ls = Array.from(document.querySelectorAll("#sessions label"));
    const hit = ls.find((l) => (l.innerText || "").indexOf(needle) >= 0);
    if (!hit) return "NO-SEL " + ls.map((l) => l.innerText.trim().slice(0, 12)).join(" | ");
    const was = (hit.querySelector("input") || {}).checked;
    (hit.querySelector("input") || hit).click();
    return "click[" + hit.innerText.trim().slice(0, 12) + "] before-checked=" + (was ? "1" : "0");
  },
};
true;`;
const B64 = Buffer.from(SRC, "utf8").toString("base64");
const INJECT = `eval(new TextDecoder().decode(Uint8Array.from(atob("${B64}"),(c)=>c.charCodeAt(0))))`;
const out = (o) => console.log("L " + JSON.stringify(o));
async function E(expr) {
  if ((await evl("typeof __L")) !== "object") await evl(INJECT);
  return evl(expr);
}
async function waitDone(ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await sleep(1200);
    if (!(await E("__L.running() ? 1 : 0"))) { await sleep(4000); return ((Date.now() - t0) / 1000).toFixed(1); }
  }
  return "timeout";
}
async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) { await sleep(1000); if (await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')")) break; }
  await evl(INJECT);
  out({ ev: "load", bar: await E("__L.bar()"), sel: await E("__L.selDetail()"), rows: await E("__L.rows()") });
  out({ ev: "click-73", r: await E(`__L.clickSel(${JSON.stringify("73")})`), after: await sleep(4000).then(() => E("__L.selDetail()")), rows: await E("__L.rows()") });
  const t0 = Date.now();
  out({ ev: "ask", sent: await E(`__L.ask(${JSON.stringify("再把那个数字回给我一次，只回数字。调用 final_answer，不要调用其他任何工具。")})`), waited: await waitDone(120000) });
  out({ ev: "final", secs: ((Date.now() - t0) / 1000).toFixed(1), bar: await E("__L.bar()"), cards: await E("__L.cards()"), rows: await E("__L.rows()"), sel: await E("__L.selDetail()") });
  await send("Page.captureScreenshot", { format: "png" }).then((r) => require("fs").writeFileSync("/tmp/v15-leg.png", Buffer.from(r.data, "base64"))).catch(() => {});
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
