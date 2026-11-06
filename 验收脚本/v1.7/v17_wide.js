const PORT = 9333;
const URL = "file://" + encodeURI("/Users/gaoying/Desktop/study/ai学习/agent功能手册.html");
let ws, id = 0; const pending = new Map();
function raw(m, p = {}) { return new Promise(r => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({id:n, method:m, params:p})); }); }
async function evl(e) { const m = await raw("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); if (m.error) throw new Error(JSON.stringify(m.error)); if (m.result.exceptionDetails) throw new Error(JSON.stringify(m.result.exceptionDetails)); return m.result.result.value; }
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find(t => t.type==="page").webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await raw("Runtime.enable"); await raw("Page.enable");
  await raw("Emulation.setDeviceMetricsOverride", {width:1440,height:960,deviceScaleFactor:1,mobile:false});
  await raw("Page.navigate", {url:URL});
  await new Promise(r=>setTimeout(r,2500));
  const b64 = Buffer.from(`
(() => {
  const de = document.documentElement;
  const out = ["inner="+de.clientWidth+" scrollW="+de.scrollW||de.scrollWidth];
  const bodyW = document.body.scrollWidth;
  out.push("body.scrollWidth="+bodyW);
  // widest leaf-ish elements beyond viewport
  const cand = [];
  for (const el of document.querySelectorAll("table, pre, code, td, th, p, h4, li, div")) {
    const r = el.getBoundingClientRect();
    if (r.right > de.clientWidth + 1) cand.push({tag: el.tagName, w: Math.round(r.width), right: Math.round(r.right), txt: (el.innerText||"").replace(/\\s+/g," ").slice(0,60)});
  }
  cand.sort((a,b)=>b.right-a.right);
  out.push("count=" + cand.length);
  for (const c of cand.slice(0,12)) out.push(JSON.stringify(c));
  // tables: which ones are wider than their container
  const tb = [];
  for (const t of document.querySelectorAll("table")) {
    const r = t.getBoundingClientRect();
    tb.push({w: Math.round(r.width), right: Math.round(r.right), head: (t.querySelector("td,th")?.innerText||"").replace(/\\s+/g," ").slice(0,30), lines: (t.closest("h4")?"":Array.from(document.querySelectorAll("h4")).filter(h=>h.compareDocumentPosition(t)&Node.DOCUMENT_POSITION_FOLLOWING).pop()?.textContent||"").slice(0,40)});
  }
  tb.sort((a,b)=>b.w-a.w);
  out.push("--- tables ---");
  for (const t of tb.slice(0,8)) out.push(JSON.stringify(t));
  return out.join("\\n");
})()
`, "utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
