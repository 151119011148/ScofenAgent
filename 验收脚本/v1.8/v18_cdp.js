// v1.8 D8 基线用的 CDP 驱动：v1.6/run/v16_cdp.js 的副本 ＋ 一步 reload（Page.navigate 回同一个 url）。
// 用法：node v18_cdp.js <config.json>
// 为什么另开一份而不改 v1.6 那份：那份已经收进 验收脚本/ 当 v1.6/v1.7 的证据，动了它 sha1 就对不上清单。
// 每一步都带 epoch 毫秒，和服务端日志的 t0_epoch 对表用。
const fs = require("fs");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const BASE = "http://127.0.0.1:9333";

function mk(id, method, params) {
  return JSON.stringify({ id, method, params: params || {} });
}

(async () => {
  const targets = await (await fetch(BASE + "/json/list")).json();
  let t = targets.find((x) => x.type === "page" && x.url === "about:blank");
  if (!t) t = await (await fetch(BASE + "/json/new?about:blank", { method: "PUT" })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) events.push(m);
  };
  const send = (method, params) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(mk(i, method, params)); });
  const evalx = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.error) return { ERR: JSON.stringify(r.error) };
    if (r.result && r.result.exceptionDetails) return { THROWN: JSON.stringify(r.result.exceptionDetails).slice(0, 400) };
    return r.result ? r.result.result.value : r;
  };
  const dec = (b64) => new TextDecoder().decode(Buffer.from(b64, "base64"));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  await send("Page.enable");
  await send("Runtime.enable");
  const out = { "__navigate0": Date.now() };
  await send("Page.navigate", { url: cfg.url });
  await sleep(cfg.bootWait || 6000);

  const mouseClick = async (x, y) => {
    for (const [type, buttons] of [["mousePressed", 1], ["mouseReleased", 0]]) {
      await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1, buttons });
    }
  };
  const realClick = async (exprForEl) => {
    const r = await evalx(`(()=>{const e=(${exprForEl});if(!e)return 'NO-ELEMENT';e.scrollIntoView({block:'center'});const b=e.getBoundingClientRect();return JSON.stringify([b.x,b.y,b.width,b.height]);})()`);
    if (typeof r !== "string" || r === "NO-ELEMENT") return r;
    const [x, y, w, h] = JSON.parse(r);
    await mouseClick(x + w / 2, y + h / 2);
    return `clicked@${Math.round(x + w / 2)},${Math.round(y + h / 2)}`;
  };

  for (const s of cfg.steps) {
    out[s.name + "#at"] = Date.now();
    if (s.el) out[s.name + "#click"] = await realClick(dec(s.el));
    if (s.type)
      out[s.name + "#type"] = await evalx(
        `(()=>{const ta=document.querySelector('textarea');if(!ta)return 'NO-TEXTAREA';ta.focus();` +
          `Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta,${JSON.stringify(s.type)});` +
          `ta.dispatchEvent(new Event('input',{bubbles:true}));` +
          `const btn=document.querySelector('button.submit-button');` +
          `if(btn){btn.click();return 'clicked-submit';}` +
          `ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));return 'sent-enter';})()`
      );
    if (s.expr) out[s.name] = await evalx(dec(s.expr));
    if (s.until) {
      const pred = dec(s.until);
      const lim = s.timeout || 120000;
      const t0 = Date.now();
      let v = null;
      while (Date.now() - t0 < lim) {
        v = await evalx(pred);
        if (typeof v === "string" && v.startsWith("YES")) break;
        await sleep(1000);
      }
      out[s.name + "#waitedMs"] = Date.now() - t0;
      out[s.name + "#pred"] = v;
    }
    // v1.8 新增：中途刷新页面。这就是 D8 的扳机——把正在流式的那一题掐断。
    if (s.reload) {
      out[s.name + "#reloadAt"] = Date.now();
      await send("Page.navigate", { url: cfg.url });
      await sleep(s.reload);
      out[s.name + "#reloadDoneAt"] = Date.now();
      out[s.name + "#urlAfter"] = await evalx("document.location.href");
    }
    if (s.wait) await sleep(s.wait);
  }
  console.log(JSON.stringify(out, null, 1));
  ws.close();
  process.exit(0);
})().catch((e) => { console.log("FATAL", String(e)); process.exit(1); });
