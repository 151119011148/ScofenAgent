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
  const ta = document.querySelectorAll('#s4 table, table');
  let t = null;
  for (const x of document.querySelectorAll("table")) {
    const h = x.querySelector("th");
    if (h && h.innerText.trim()==="ID" && x.getBoundingClientRect().width > 1100) { t = x; break; }
  }
  if (!t) return "TABLE-NOT-FOUND";
  const cols = t.querySelectorAll("tr")[0].children.length;
  const res = [];
  for (let c = 0; c < cols; c++) {
    let best = {w:0, txt:"", row:-1};
    for (let r = 1; r < t.rows.length; r++) {
      const cell = t.rows[r].cells[c];
      if (!cell) continue;
      // measure min-content of the cell
      const probe = cell.cloneNode(true);
      probe.style.cssText = "position:absolute;left:-9999px;top:0;width:min-content;font:"+getComputedStyle(cell).font+";";
      document.body.appendChild(probe);
      const w = probe.getBoundingClientRect().width;
      document.body.removeChild(probe);
      if (w > best.w) {
        let word = "";
        for (const el of cell.querySelectorAll("code,.pill,td *")) { const q=el.getBoundingClientRect?0:0; }
        const re = /[^\\s，。、；：）)\\u3000]+/g;
        const span = document.createElement("span");
        span.style.cssText="position:absolute;left:-9999px;top:0;white-space:nowrap;font:"+getComputedStyle(cell).font+";";
        document.body.appendChild(span);
        for (const m of cell.innerText.match(re) || []) { span.textContent = m; const ww = span.getBoundingClientRect().width; if (ww > span._b || span._b===undefined) { if (span._b===undefined||ww>span._b){span._b=ww;word=m;} } }
        document.body.removeChild(span);
        best = {w: Math.round(w), txt: cell.innerText.replace(/\\s+/g," ").slice(0,40), word: word, row: r, id: (t.rows[r].cells[0]||{}).innerText};
      }
    }
    res.push("col" + c + " head=" + t.rows[0].cells[c].innerText + " maxMin=" + best.w + " row=" + best.id + " longestWord=" + best.word + " | " + best.txt);
  }
  let sum = 0;
  return res.join("\\n") + "\\nwidth=" + Math.round(t.getBoundingClientRect().width) + " container=" + document.querySelector(".wrap").clientWidth;
})()
`,"utf8").toString("base64");
  console.log(await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('"+b64+"'),c=>c.charCodeAt(0))))"));
  ws.close();
})().catch(e=>{console.error("ERR",e.message);process.exit(1);});
