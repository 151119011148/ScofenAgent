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
  await new Promise(r=>setTimeout(r,2500));
  const b64=Buffer.from(`
(() => {
  const out = [];
  const t = (() => { for (const x of document.querySelectorAll("table")) { const h = x.querySelector("th"); if (h && h.innerText.trim()==="ID" && x.rows[0].cells.length === 6) return x; } })();
  const host = t.parentElement;
  const minw = (el, cssText) => {
    const c = el.cloneNode(true);
    c.style.cssText = (cssText||"") + "position:absolute;left:-99999px;top:0;width:min-content;";
    host.appendChild(c);
    const w = Math.round(c.getBoundingClientRect().width);
    host.removeChild(c);
    return w;
  };
  const rows = [];
  for (let r = 1; r < t.rows.length; r++) rows.push([r, t.rows[r].cells[0].innerText.trim()]);
  for (const [r, name] of rows) {
    for (let c = 1; c < 6; c++) {
      const cell = t.rows[r].cells[c];
      const cm = minw(cell, "padding:" + getComputedStyle(cell).padding + ";font:" + getComputedStyle(cell).font + ";");
      let bw = 0, bt = "";
      for (const el of cell.querySelectorAll("code,span,b,u")) {
        const w = minw(el, "display:inline-block;font:" + getComputedStyle(el).font + ";padding:" + getComputedStyle(el).padding + ";white-space:" + getComputedStyle(el).whiteSpace + ";");
        if (w > bw) { bw = w; bt = el.tagName + " " + el.innerText.replace(/\\s+/g," ").slice(0,42); }
      }
      out.push(name + " col" + c + " cellMin=" + cm + " widestInline=" + bw + " [" + bt + "]");
    }
  }
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
