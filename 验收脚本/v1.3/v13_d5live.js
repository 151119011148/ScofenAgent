// D5 实测：同一页面连问两题（不点「＋ 新会话」），历史库里前一轮还在不在。
const PORT = 9333, URL = "http://127.0.0.1:7861/";
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
function send(m, p = {}) { return new Promise(res => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); }); }
async function evl(e) {
  const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result && r.result.value;
}
async function waitFor(e, ms, label) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    let v = null; try { v = await evl(e); } catch (err) { v = null; }
    if (v) return { waited: ((Date.now() - t0) / 1000).toFixed(1), value: v };
    await sleep(700);
  }
  return { timeout: label, waited: ((Date.now() - t0) / 1000).toFixed(1) };
}
const HELPERS = `
window.__v13 = {
  ask: (q) => { const ta = document.querySelector('textarea'); ta.focus();
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta,q);
    ta.dispatchEvent(new Event('input',{bubbles:true}));
    const b=document.querySelector('button.submit-button'); if(b){b.click();return 'clicked';} return 'no-submit'; },
  done: () => ((document.querySelector('#statusbar')||{}).innerText||'').includes('状态') &&
              (((document.querySelector('#statusbar')||{}).innerText||'').match(/状态\\s*\\n?\\s*(完成|已停止|步数用满)/)||[null])[1],
  titles: () => Array.from(document.querySelectorAll('.thought-group')).map(g => (g.innerText||'').split('\\n')[0].slice(0,90)),
  body: () => document.body.innerText.slice(0,400),
}; true;`;

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find(t => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) { await sleep(1000); if (await evl(`!!document.querySelector('textarea') && !!document.querySelector('#statusbar')`)) break; }
  await evl(HELPERS);
  console.log("MARK", await evl(`JSON.stringify({t: new Date().toISOString(), titles: __v13.titles().length})`));
  for (const q of ["1+1 等于几？直接回答，不要调用工具。", "2+2 等于几？直接回答，不要调用工具。"]) {
    console.log("ASK", q);
    console.log("  sent", await evl(`__v13.ask(${JSON.stringify(q)})`));
    const d = await waitFor(`__v13.done()`, 90000, "完成");
    console.log("  state", d.value || d.timeout, "waited", d.waited, "titles", JSON.stringify(await evl(`__v13.titles()`)));
    await sleep(2500);
  }
  console.log("END", await evl(`JSON.stringify({t: new Date().toISOString(), titles: __v13.titles()})`));
  ws.close();
}
main().catch(e => { console.error("ERR", e.message); process.exit(1); });
