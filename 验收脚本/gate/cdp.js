// 零安装 CDP 客户端：用真实视口量宽度、截图。in-app 浏览器视口是 0x0，量不出可信宽度。
const fs = require("fs");
const PORT = 9333;
const URL = process.argv[2] || "http://127.0.0.1:7861/";
const EXPR = process.argv[3] || null;
const SHOT = process.argv[4] || null;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find(t => t.type === "page");
  if (!page) throw new Error("no page target");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  const send = (method, params = {}) => new Promise(res => {
    const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method, params }));
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: URL });
  await sleep(6000);
  if (EXPR) {
    const expr = EXPR.endsWith(".js") ? fs.readFileSync(EXPR, "utf8") : EXPR;
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) console.log("EXC", JSON.stringify(r.exceptionDetails).slice(0, 600));
    console.log(JSON.stringify(r.result, null, 1).slice(0, 6000));
  }
  if (SHOT) {
    const s = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(SHOT, Buffer.from(s.result.data, "base64"));
    console.log("shot ->", SHOT);
  }
  ws.close();
}
main().catch(e => { console.error("ERR", e.message); process.exit(1); });
