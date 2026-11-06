const PORT = 9333;
const URL = "file://" + encodeURI("/Users/gaoying/Desktop/study/ai学习/agent功能手册.html");
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
  const measure = (label) => {
    const de = document.documentElement;
    let t = null;
    for (const x of document.querySelectorAll("table")) {
      const h = x.querySelector("th");
      if (h && h.innerText.trim()==="ID" && x.getBoundingClientRect().width > 1100) { t = x; break; }
    }
    const cols = t.rows[0].cells.length, per = [];
    for (let c = 0; c < cols; c++) {
      let best = 0, who = "";
      for (let r = 1; r < t.rows.length; r++) {
        const cell = t.rows[r].cells[c]; if (!cell) continue;
        const p = cell.cloneNode(true);
        p.style.cssText = "position:absolute;left:-9999px;top:0;width:min-content;font:" + getComputedStyle(cell).font + ";padding:" + getComputedStyle(cell).padding + ";";
        document.body.appendChild(p);
        const w = p.getBoundingClientRect().width;
        document.body.removeChild(p);
        if (w > best) { best = w; who = t.rows[r].cells[0].innerText.trim(); }
      }
      per.push(Math.round(best) + "(" + who + ")");
    }
    out.push(label + " | table=" + Math.round(t.getBoundingClientRect().width) + " docScrollW=" + de.scrollWidth + " inner=" + de.clientWidth + " | cols " + per.join(" "));
  };
  measure("BEFORE");
  const st = document.createElement("style");
  st.textContent = "#s4 td{overflow-wrap:anywhere}";
  document.head.appendChild(st);
  measure("AFTER overflow-wrap:anywhere");
  return out.join("\\n");
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
