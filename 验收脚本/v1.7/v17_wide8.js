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
  // for each column, find the row whose cell has max min-content, then list its widest line boxes at min-content width
  for (let c = 1; c < 6; c++) {
    let best = {w: 0, row: null, lines: []};
    for (let r = 1; r < t.rows.length; r++) {
      const cell = t.rows[r].cells[c]; if (!cell) continue;
      const clone = cell.cloneNode(true);
      clone.style.cssText = "position:absolute;left:-99999px;top:0;width:0;padding:0;overflow-wrap:" + getComputedStyle(cell).overflowWrap + ";word-break:" + getComputedStyle(cell).wordBreak + ";font:" + getComputedStyle(cell).font + ";letter-spacing:" + getComputedStyle(cell).letterSpacing;
      host.appendChild(clone);
      const w = clone.getBoundingClientRect().width;
      let lines = [];
      if (w > best.w) {
        const range = document.createRange(); range.selectNodeContents(clone);
        for (const rect of range.getClientRects()) lines.push({w: Math.round(rect.width), txt: ""});
        // get text per line by walking client rects of child text nodes is heavy; approximate by child rects
        const rects = [];
        for (const el of clone.querySelectorAll("*")) for (const rr of el.getClientRects()) rects.push(Math.round(rr.width));
      }
      host.removeChild(clone);
      if (w > best.w) {
        const wid = [];
        const probe = clone.cloneNode(true);
        probe.style.width = Math.ceil(w) + "px";
        host.appendChild(probe);
        const rr = [];
        for (const el of probe.querySelectorAll("code,span,b,u")) for (const q of el.getClientRects()) if (q.width > w - 2) rr.push(Math.round(q.width) + ":" + el.innerText.replace(/\\s+/g," ").slice(0,45));
        host.removeChild(probe);
        best = {w: Math.round(w), row: t.rows[r].cells[0].innerText.trim(), wide: rr.slice(0,3)};
      }
    }
    out.push("col" + c + " maxMinContent=" + best.w + " row=" + best.row + " wideFragments=" + JSON.stringify(best.wide));
  }
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
