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
  const W = parseInt(process.argv[3] || "1440", 10);
  await raw("Emulation.setDeviceMetricsOverride",{width:W,height:960,deviceScaleFactor:1,mobile:false});
  await raw("Page.navigate",{url:URL});
  await new Promise(r=>setTimeout(r,2200));
  const b64=Buffer.from(`
(() => {
  const de = document.documentElement, wr = document.querySelector(".wrap");
  let t = null;
  for (const x of document.querySelectorAll("table")) { const h = x.querySelector("th"); if (h && h.innerText.trim()==="ID" && x.rows[0].cells.length === 6) { t = x; break; } }
  return JSON.stringify({inner: de.clientWidth, scrollW: de.scrollWidth, overflowX: de.scrollWidth > de.clientWidth,
    wrapClient: wr.clientWidth, tableW: t ? Math.round(t.getBoundingClientRect().width) : null, rows: t ? t.rows.length : 0});
})()
`,"utf8").toString("base64");
  console.log(process.argv[2].split("/").pop() + " @" + W + " => " + await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
