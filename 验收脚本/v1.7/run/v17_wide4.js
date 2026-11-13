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
  const findT = () => { for (const x of document.querySelectorAll("table")) { const h = x.querySelector("th"); if (h && h.innerText.trim()==="ID" && x.rows.length > 8 && x.rows[0].cells.length === 6) return x; } return null; };
  const t = findT(); if (!t) return "NO-TABLE";
  const de = document.documentElement;
  out.push("FILE-ROWS=" + t.rows.length + " table=" + Math.round(t.getBoundingClientRect().width) + " scrollW=" + de.scrollWidth + " inner=" + de.clientWidth);
  // widest unbreakable inline unit inside col2 / col5 of D8-ish rows
  const span = document.createElement("span");
  span.style.cssText = "position:absolute;left:-9999px;top:0;white-space:nowrap;";
  document.body.appendChild(span);
  const wordW = (el, fontPx, mono) => {
    let best = {w:0,tok:""};
    const cs = getComputedStyle(el);
    span.style.font = cs.font;
    const txt = el.innerText;
    for (const m of txt.match(/[^\\s]+/g) || []) { span.textContent = m; const w = span.getBoundingClientRect().width; if (w > best.w) best = {w: Math.round(w), tok: m.slice(0,60)}; }
    return best;
  };
  for (let r = 1; r < t.rows.length; r++) {
    for (const c of [2,3,4,5]) {
      const cell = t.rows[r].cells[c]; if (!cell) continue;
      const b = wordW(cell);
      if (b.w > 300) out.push("row" + t.rows[r].cells[0].innerText.trim() + " col" + c + " widest-token=" + b.w + " " + b.tok);
    }
  }
  document.body.removeChild(span);
  out.push("--- CSS experiments ---");
  const add = (css) => { const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s); };
  const re = (label) => { const x = findT(); out.push(label + " => table=" + Math.round(x.getBoundingClientRect().width) + " scrollW=" + document.documentElement.scrollWidth); };
  add("#s4 .pill{white-space:normal}"); re("pill nowrap off");
  add("#s4 td{overflow-wrap:anywhere;word-break:break-word}"); re("+ overflow-wrap/word-break");
  add("#s4 td.ev code{white-space:normal;overflow-wrap:anywhere}"); re("+ ev code wrap");
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
