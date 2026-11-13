// v1.5 交付形态实跑：审批走 ✔ 允许 -> run_python 真执行 -> 收尾把带观察值的 ActionStep 落库。
// 判据：等待审批出现、点允许后状态走到 完成、卡里能看到工具返回；库里的 payload 里那条观察值还在。
const PORT = 9333;
const URL = process.env.V15URL || "http://127.0.0.1:7860/";
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
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").replace(/\\n/g, " ").slice(0, 160)),
  body: () => document.body.innerText.replace(/\\n/g, " ").slice(-900),
};
"ready";`;
const out = (o) => console.log("A " + JSON.stringify(o));

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
  out({ ev: "nav", sels: await evl("Array.from(document.querySelectorAll('#sessions label')).map(l=>(l.innerText||'').trim().slice(0,26))") });

  const q = "必须调用 run_python 工具一次，代码就写：print(3*7)。然后把工具返回原样贴出来，调用 final_answer。";
  const t0 = Date.now();
  out({ ev: "ask", sent: await evl(`__a.ask(${JSON.stringify(q)})`), at: new Date().toISOString() });

  let pendAt = null;
  for (let i = 0; i < 120; i++) {
    await sleep(500);
    if (await evl("__a.body().indexOf('等待审批') >= 0 || __a.state()==='等待审批'")) { pendAt = ((Date.now() - t0) / 1000).toFixed(1); break; }
    if (!/生成中|等待审批|停止中/.test(String(await evl("__a.state()")))) break;
  }
  out({ ev: "pending", pendAt, cards: await evl("__a.cards()").then(c => c.slice(-2)) });
  const clicked = await evl(`__a.click("✔ 允许")`);
  out({ ev: "approve", clicked, at: new Date().toISOString() });

  let done = null;
  for (let i = 0; i < 240; i++) {
    await sleep(1000);
    const st = String(await evl("__a.state()"));
    if (!/生成中|等待审批|停止中/.test(st)) { done = { st, secs: ((Date.now() - t0) / 1000).toFixed(1) }; break; }
  }
  await sleep(6000);
  out({ ev: "final", done, bar: await evl("__a.bar()"), cards: await evl("__a.cards()").then(c => c.slice(-3)) });
  const r = await send("Page.captureScreenshot", { format: "png" });
  require("fs").writeFileSync("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15-deliver-approve.png", Buffer.from(r.data, "base64"));
  out({ ev: "shot", path: "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.5/run/v15-deliver-approve.png" });
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
