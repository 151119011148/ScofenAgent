// 手册 HTML 的浏览器侧自检：逐筛选器实点读 #cnt，量正文宽度，读状态胶囊。
// 表达式怎么送进浏览器：整段 helpers 先 base64，再用 eval(atob('…')) 解开执行。
// 原因是实测踩到的：把带双引号的 CSS 选择器拼进单引号 JS 字符串再送 CDP，
// 同一个表达式换个写法就报 SyntaxError: missing ) after argument list；
// 走 base64 就没有任何引号打架的可能。
const PORT = 9333;
const FILE = "/Users/gaoying/Desktop/study/ai学习/agent功能手册.html";
const URL = "file://" + encodeURI(FILE);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
function raw(m, p = {}) {
  return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method: m, params: p })); });
}
async function evl(expr) {
  // raw() 递回的是整条 CDP 报文，值在 msg.result.result.value，别按 msg.result.value 取
  const msg = await raw("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (msg && msg.error) throw new Error("CDP " + JSON.stringify(msg.error).slice(0, 300));
  const r = (msg && msg.result) || {};
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result && r.result.value;
}
async function call(name, ...args) {
  return evl("__v16m." + name + "(" + args.map((a) => JSON.stringify(a)).join(",") + ")");
}
async function inject() {
  const b64 = Buffer.from(HELPERS, "utf8").toString("base64");
  // atob 给的是 latin1 字符串，中文会变mojibake，所以按字节还原成 UTF-8 再 eval
  return evl("eval(new TextDecoder().decode(Uint8Array.from(atob('" + b64 + "'),(c)=>c.charCodeAt(0))))");
}

const HELPERS = `
window.__v16m = {
  kinds: ["all","bug","p0","p1","p2","v","todo","doing","done","na"],
  filters: () => {
    const out = [];
    for (const k of __v16m.kinds) {
      const b = document.querySelector('.bar button[onclick*=' + JSON.stringify(k) + ']');
      if (!b) { out.push(k + " : NO-BUTTON"); continue; }
      b.click();
      let shown = 0;
      for (const r of document.querySelectorAll("tr[data-st]")) if (r.offsetParent !== null) shown++;
      const c = document.getElementById("cnt");
      out.push((k + "     ").slice(0, 5) + " | cnt=" + (c ? c.textContent.trim() : "no-#cnt") + " | 可见行=" + shown);
    }
    return out.join("\\n");
  },
  layout: () => {
    const de = document.documentElement, bar = document.querySelector(".bar");
    return JSON.stringify({
      title: document.title,
      rows: document.querySelectorAll("tr[data-st]").length,
      tables: document.querySelectorAll("table").length,
      inner: de.clientWidth, scrollW: de.scrollWidth,
      overflowX: de.scrollWidth > de.clientWidth,
      barWrap: bar ? getComputedStyle(bar).flexWrap : "no-bar",
    });
  },
  stcount: () => {
    const m = {};
    for (const r of document.querySelectorAll("tr[data-st]")) { const k = r.getAttribute("data-st"); m[k] = (m[k] || 0) + 1; }
    return JSON.stringify(m);
  },
  pill: (key) => {
    for (const r of document.querySelectorAll("tr[data-st]")) {
      const t0 = r.querySelector("td");
      if (t0 && t0.innerText.trim().indexOf(key) === 0) {
        const last = r.querySelector("td:last-child");
        return (key + "    ").slice(0, 5) + " | data-st=" + r.getAttribute("data-st") + " | 末列=" + (last ? last.innerText.trim() : "none");
      }
    }
    return key + " : ROW-NOT-FOUND";
  },
  sec6: () => Array.from(document.querySelectorAll("h3"))
      .filter((h) => h.textContent.trim().indexOf("6.") === 0)
      .map((h) => h.textContent.trim().slice(0, 60)).join("\\n"),
  anchors: () => {
    const bad = [];
    for (const a of document.querySelectorAll('a[href^="#"]')) {
      const idv = a.getAttribute("href").slice(1);
      if (!document.getElementById(idv)) bad.push(idv);
    }
    return JSON.stringify(bad);
  },
};
true;
`;

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  ws = new WebSocket(list.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await raw("Runtime.enable");
  await raw("Page.enable");
  await raw("Emulation.setDeviceMetricsOverride",
    { width: 1180, height: 900, deviceScaleFactor: 1, mobile: false });
  await raw("Page.navigate", { url: URL });
  let ready = 0;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    ready = await evl("document.querySelectorAll('tr[data-st]').length");
    if (ready > 0) break;
  }
  console.log("URL", URL, "| rows", ready);
  if (!ready) throw new Error("页面没渲染出看板行");
  await inject();
  console.log("LAYOUT", await call("layout"));
  console.log("STCOUNT", await call("stcount"));
  console.log("FILTERS\n" + (await call("filters")));
  console.log("PILLS");
  for (const k of ["V7", "V8", "V9", "V6", "D7", "P0-4"]) console.log("  " + (await call("pill", k)));
  console.log("SEC6\n" + (await call("sec6")));
  console.log("DEAD-ANCHORS", await call("anchors"));
  const s = await raw("Page.captureScreenshot", { format: "png" });
  require("fs").writeFileSync("/tmp/v16-manual.png", Buffer.from((s.result || s).data, "base64"));
  console.log("SHOT /tmp/v16-manual.png");
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
