// 一次性探针 2：把 §4 那张撑宽的表克隆到 1px 容器里，量每列的 min-content，
// 再指认最宽那一列里是谁（最长不可断 token）。只读，不改现场文件。
const PORT = 9344, WIDTH = parseInt(process.argv[2] || "1440", 10);
const FILE = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
function raw(m, p = {}) { return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); }); }
async function evl(e) { const m = await raw("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); const r = (m && m.result) || {}; if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 500)); return r.result && r.result.value; }
const H = `
window.__q = () => {
  const de = document.documentElement, lim = de.clientWidth;
  const bad = [];
  for (const t of document.querySelectorAll("table")) {
    const r = t.getBoundingClientRect();
    if (r.right > lim + 1) bad.push(t);
  }
  const out = [];
  for (const t of bad) {
    const box = document.createElement("div");
    box.style.cssText = "position:absolute;left:-99999px;top:0;width:1px;visibility:hidden";
    const c = t.cloneNode(true);
    c.style.width = "1px";
    box.appendChild(c); document.body.appendChild(box);
    const ncol = c.querySelector("tr").children.length;
    const cols = [];
    for (let i = 0; i < ncol; i++) {
      let w = 0;
      for (const row of c.querySelectorAll("tr")) {
        const cell = row.children[i];
        if (cell) w = Math.max(w, cell.getBoundingClientRect().width);
      }
      cols.push(Math.round(w));
    }
    // 最宽列里逐格量 min-content ＋ 最长 token
    const worst = cols.indexOf(Math.max(...cols));
    const cells = [];
    const rows = t.querySelectorAll("tr");
    for (let ri = 0; ri < rows.length; ri++) {
      const cell = rows[ri].children[worst];
      if (!cell) continue;
      const txt = (cell.textContent || "").trim().replace(/\\s+/g, " ");
      const toks = txt.split(/[\\s\\u3000]+/).filter(Boolean);
      let longest = "";
      for (const k of toks) if (k.length > longest.length) longest = k;
      const cb = document.createElement("div");
      cb.style.cssText = "position:absolute;left:-99999px;width:1px;visibility:hidden";
      const cc = cell.cloneNode(true); cb.appendChild(cc); document.body.appendChild(cb);
      const mw = Math.round(cc.getBoundingClientRect().width);
      cb.remove();
      cells.push({ ri, mw, longest: longest.slice(0, 70), txt: txt.slice(0, 60) });
    }
    cells.sort((a, b) => b.mw - a.mw);
    box.remove();
    out.push({ right: Math.round(t.getBoundingClientRect().right), tableW: Math.round(t.getBoundingClientRect().width),
               cols, sum: cols.reduce((a, b) => a + b, 0), worstCol: worst, topCells: cells.slice(0, 6) });
  }
  return JSON.stringify({ lim, scrollW: de.scrollWidth, nbad: bad.length, out }, null, 1);
};
true;`;
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await raw("Runtime.enable"); await raw("Page.enable");
  await raw("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: 960, deviceScaleFactor: 1, mobile: false });
  await raw("Page.navigate", { url: "file://" + encodeURI(FILE) });
  for (let i = 0; i < 40; i++) { await sleep(400); if (await evl("document.querySelectorAll('tr[data-st]').length") > 0) break; }
  const b64 = Buffer.from(H, "utf8").toString("base64");
  await evl("eval(new TextDecoder().decode(Uint8Array.from(atob('" + b64 + "'),(c)=>c.charCodeAt(0))))");
  console.log("视口 " + WIDTH);
  console.log(await evl("__q()"));
  ws.close();
})().catch((e) => { console.error("ERR", e.message); process.exit(1); });