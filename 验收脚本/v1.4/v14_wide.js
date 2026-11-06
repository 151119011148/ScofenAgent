const PORT = 9333;
const URL = "file://" + encodeURI("/Users/gaoying/Desktop/study/ai学习/agent功能手册.html");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
function send(m, p = {}) { return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); }); }
async function evl(e) {
  const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result && r.result.value;
}
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 30; i++) { await sleep(400); if (await evl("document.querySelectorAll('tr[data-st]').length")) break; }
  await sleep(800);
  console.log(await evl(`(function(){
    const de=document.documentElement, out=[];
    out.push('inner='+de.clientWidth+' scrollW='+de.scrollWidth+' bodyW='+document.body.scrollWidth);
    const lim=de.clientWidth;
    const els=document.querySelectorAll('body *');
    const wide=[];
    for (const el of els){ const r=el.getBoundingClientRect(); if (r.right>lim+1||r.width>lim+1){ wide.push(el.tagName+'.'+(el.className||'').toString().slice(0,24)+' w='+Math.round(r.width)+' right='+Math.round(r.right)+' :: '+(el.textContent||'').replace(/\\s+/g,' ').slice(0,70)); } }
    out.push('候选宽元素 '+wide.length);
    out.push(wide.slice(0,12).join('\\n'));
    return out.join('\\n');
  })()`));
  ws.close();
})();
