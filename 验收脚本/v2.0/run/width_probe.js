// 一次性探针：谁把手册撑出横向滚动条。连自己起的 9344，不碰 9457。
const PORT = 9344, WIDTH = parseInt(process.argv[2] || "1440", 10);
const FILE = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
function raw(m, p = {}) { return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); }); }
async function evl(e) { const m = await raw("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); const r = (m && m.result) || {}; if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400)); return r.result && r.result.value; }
const H = `
window.__p = () => {
  const de = document.documentElement, lim = de.clientWidth;
  const head = (el) => { let n = el; while (n) { let p = n.previousElementSibling;
      while (p) { if (/^H[1-4]$/.test(p.tagName)) return p.textContent.trim().slice(0, 40);
        const q = p.querySelector && p.querySelector("h1,h2,h3,h4"); if (q) return q.textContent.trim().slice(0,40); p = p.previousElementSibling; }
      n = n.parentElement; } return "?"; };
  const wide = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.right > lim + 1 || el.scrollWidth > lim + 1) {
      const cs = getComputedStyle(el);
      wide.push({ tag: el.tagName, cls: (el.className || "").toString().slice(0, 24),
        right: Math.round(r.right), sw: el.scrollWidth, cw: el.clientWidth,
        ws: cs.whiteSpace, wb: cs.wordBreak, ow: cs.overflowWrap,
        sec: head(el), txt: (el.textContent || "").trim().replace(/\\s+/g, " ").slice(0, 90) });
    }
  }
  wide.sort((a, b) => b.right - a.right);
  return JSON.stringify({ lim, scrollW: de.scrollWidth, n: wide.length, top: wide.slice(0, 14) }, null, 1);
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
  console.log(await evl("__p()"));
  ws.close();
})().catch((e) => { console.error("ERR", e.message); process.exit(1); });