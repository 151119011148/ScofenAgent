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
  const findT = () => { for (const x of document.querySelectorAll("table")) { const h = x.querySelector("th"); if (h && h.innerText.trim()==="ID" && x.rows[0].cells.length === 6) return x; } return null; };
  const t = findT();
  const host = t.parentElement;
  const mc = () => {
    const c = t.cloneNode(true);
    c.style.cssText = "width:min-content;position:absolute;left:-99999px;top:0;";
    host.appendChild(c);
    const w = c.getBoundingClientRect().width;
    const cols = [];
    for (let i = 0; i < 6; i++) {
      const cc = c.cloneNode(true);
      for (let r = 1; r < cc.rows.length; r++) if (cc.rows[r].cells[i]) cc.rows[r].cells[i].style.maxWidth = "0";
      cc.style.cssText = "width:min-content;position:absolute;left:-99999px;top:0;";
      host.appendChild(cc);
      cols.push(0);
      host.removeChild(cc);
    }
    host.removeChild(c);
    return Math.round(w);
  };
  const base = mc();
  const out = ["table min-content (all rows) = " + base, "actual width = " + Math.round(t.getBoundingClientRect().width)];
  // per row: hide row, measure min-content
  for (let r = 1; r < t.rows.length; r++) {
    const id = t.rows[r].cells[0].innerText.trim();
    t.rows[r].style.display = "none";
    out.push("without " + id + " => min-content " + mc());
    t.rows[r].style.display = "";
  }
  // per cell in D8: blank content, measure
  let d8 = null;
  for (let r = 1; r < t.rows.length; r++) if (t.rows[r].cells[0].innerText.trim() === "D8") d8 = t.rows[r];
  if (d8) {
    for (let c = 1; c < 6; c++) {
      const keep = d8.cells[c].innerHTML;
      d8.cells[c].innerHTML = "X";
      out.push("D8 col" + c + " blanked => min-content " + mc());
      d8.cells[c].innerHTML = keep;
    }
  }
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
