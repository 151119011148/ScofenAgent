const PORT = 9333;
const FILE = process.argv[2];
const URL = "file://" + encodeURI(FILE);
let ws, id = 0; const pending = new Map();
function raw(m,p={}){return new Promise(r=>{const n=++id;pending.set(n,r);ws.send(JSON.stringify({id:n,method:m,params:p}));});}
async function evl(e){const m=await raw("Runtime.evaluate",{expression:e,returnByValue:true,awaitPromise:true});if(m.error)throw new Error(JSON.stringify(m.error));if(m.result.exceptionDetails)throw new Error(JSON.stringify(m.result.exceptionDetails));return m.result.result.value;}
(async()=>{
  const list=await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws=new WebSocket(list.find(t=>t.type==="page").webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
  await raw("Runtime.enable");await raw("Page.enable");
  await raw("Emulation.setDeviceMetricsOverride",{width:1440,height:960,deviceScaleFactor:1,mobile:false});
  await raw("Page.navigate",{url:URL});
  await new Promise(r=>setTimeout(r,2200));
  const b64=Buffer.from(`
(() => {
  const out = [];
  const t = (() => { for (const x of document.querySelectorAll("table")) { const h = x.querySelector("th"); if (h && h.innerText.trim()==="ID" && x.rows[0].cells.length === 6) return x; } })();
  const host = t.parentElement;
  const mc = () => { const c = t.cloneNode(true); c.style.cssText="width:min-content;position:absolute;left:-99999px;top:0;"; host.appendChild(c); const w = Math.round(c.getBoundingClientRect().width); host.removeChild(c); return w; };
  const live = () => { const b = Math.round(t.getBoundingClientRect().width); host.appendChild(Object.assign(document.createElement("div"), {})); return b; };
  let d8 = null; for (let r = 1; r < t.rows.length; r++) if (t.rows[r].cells[0].innerText.trim()==="D8") d8 = t.rows[r];
  const k2 = d8.cells[2].innerHTML, k5 = d8.cells[5].innerHTML;
  const OLD = '<b>v1.7 实跑撞出来的，两条路都有留痕</b>（<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drain.out</code>、<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_finish.out</code>、<code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_peek.out</code>）。';
  const NEW = '<b>v1.7 实跑撞出来的，两条路都有留痕：</b><code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_drain.out</code> <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_finish.out</code> <code>/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_peek.out</code>。';
  out.push("OLD-in-HTML? " + (k2.indexOf(OLD) >= 0));
  d8.cells[2].innerHTML = k2.replace(OLD, NEW);
  d8.cells[5].innerHTML = '<span class="pill todo">未开工</span> <span class="ev">v1.7 新立</span>';
  const m = mc();
  t.style.maxWidth = "none";
  out.push("with final wording + pill split => min-content " + m);
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
