// D7 现场恢复：不刷新页面，直接在当前 DOM 上补点 ✖ 拒绝，看能否解开挂住的 worker。
const PORT = 9333, sleep = (ms) => new Promise(r => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
function send(m, p = {}) { return new Promise(res => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); }); }
async function evl(e) { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0,300)); return r.result && r.result.value; }
async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find(t => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable");
  console.log("State " + await evl(`((document.querySelector("#statusbar .pill-state i")||{}).textContent||"?")`));
  console.log("Bar " + JSON.stringify(await evl(`((document.querySelector("#statusbar")||{}).innerText||"").replace(/\\n/g," / ")`)));
  const b = await evl(`(()=>{const x=Array.from(document.querySelectorAll('button')).find(y=>(y.innerText||'').trim()==='✖ 拒绝');if(!x)return "NO-BUTTON";x.click();return "clicked deny at "+new Date().toISOString();})()`);
  console.log("Click " + b);
  let end = null;
  for (let i = 0; i < 160; i++) { await sleep(500); const st = await evl(`((document.querySelector("#statusbar .pill-state i")||{}).textContent||"?")`); if (st !== "等待审批" && st !== "停止中" && st !== "生成中") { end = { st, afterSecs: (i*0.5).toFixed(1) }; break; } }
  console.log("End " + JSON.stringify(end));
  await sleep(6000);
  console.log("Bar " + JSON.stringify(await evl(`((document.querySelector("#statusbar")||{}).innerText||"").replace(/\\n/g," / ")`)));
  console.log("Cards " + JSON.stringify(await evl("Array.from(document.querySelectorAll('.thought-group')).map(g=>(g.innerText||'').split(String.fromCharCode(10))[0].slice(0,80))")));
  ws.close();
}
main().catch(e => { console.error("ERR", e.message); process.exit(1); });
