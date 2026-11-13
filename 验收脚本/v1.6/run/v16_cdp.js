// Zero-install CDP driver. Usage: node /Users/gaoying/Desktop/study/ai学习/验收脚本/v1.6/run/v16_cdp.js <config.json>
// config = { url, steps: [ { name, wait, expr } ] }   expr is base64(JS)
const fs = require("fs");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const BASE = "http://127.0.0.1:9333";

const HELPER = `
window.__q = (sel) => document.querySelector(sel);
window.__checked = () => Array.from(document.querySelectorAll('#sessions input[type=radio], [data-testid=radio-group] input[type=radio]')).map(i => i.checked);
window.__labels = () => Array.from(document.querySelectorAll('#sessions label, [data-testid=radio-group] label')).map(l => l.innerText.trim().replace(/\\s+/g,' '));
window.__msgs = () => Array.from(document.querySelectorAll('[data-testid=assistant-message], [data-testid=user-message]')).length;
window.__body = () => document.body.innerText;
`;

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

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Page.navigate", { url: cfg.url });
  await new Promise((r) => setTimeout(r, cfg.bootWait || 6000));
  await evalx(HELPER);

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

  const out = {};
  for (const s of cfg.steps) {
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
    if (s.until) {
      const pred = dec(s.until);
      const lim = s.timeout || 120000;
      const t0 = Date.now();
      let v = null;
      while (Date.now() - t0 < lim) {
        v = await evalx(pred);
        if (typeof v === "string" && v.startsWith("YES")) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
      out[s.name + "#waitedMs"] = Date.now() - t0;
      out[s.name + "#pred"] = v;
    }
    if (s.wait) await new Promise((r) => setTimeout(r, s.wait));
    if (s.expr) out[s.name] = await evalx(dec(s.expr));
  }
  console.log(JSON.stringify(out, null, 1));
  ws.close();
  process.exit(0);
})().catch((e) => { console.log("FATAL", String(e)); process.exit(1); });
