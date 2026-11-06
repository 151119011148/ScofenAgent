// v1.3 在线驱动器：在真浏览器里走「审批 → 允许 / 拒绝 / 停止」三条路，抓 DOM 上真正可见的标题。
const PORT = 9333;
const URL = process.env.V13URL || "http://127.0.0.1:7861/";
const ONLY = (process.env.V13ONLY || "").split(",").filter(Boolean);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws, id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((res) => {
    const n = ++id;
    pending.set(n, res);
    ws.send(JSON.stringify({ id: n, method, params }));
  });
}
async function evl(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result && r.result.value;
}
async function nav() {
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    const ok = await evl(`!!document.querySelector('textarea') && !!document.querySelector('#statusbar')`);
    if (ok) return true;
  }
  throw new Error("页面没起来");
}
async function waitFor(expr, ms, label) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    let v = null;
    try { v = await E(expr); } catch (e) { v = null; }
    if (v) return { waited: ((Date.now() - t0) / 1000).toFixed(1), value: v };
    await sleep(700);
  }
  return { timeout: label || expr, waited: ((Date.now() - t0) / 1000).toFixed(1) };
}

// gradio 的重连逻辑会在后端抖动时把整页 reload 掉，reload 之后 window.__v13 就没了
// （踩过：驱动器只在开头注入一次，第二个场景直接 ReferenceError: __v13 is not defined）。
// 所以每次求值前探一下上下文还在不在，不在就重新注入。
async function E(expr) {
  let last = null;
  for (let i = 0; i < 8; i++) {
    try {
      if ((await evl(`typeof __v13`)) !== "object") await evl(HELPERS);
      return await evl(expr);
    } catch (e) {
      last = e;
      await sleep(2000);
    }
  }
  throw last;
}

const HELPERS = `
window.__v13 = {
  ask: (q) => {
    const ta = document.querySelector('textarea');
    ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    set.call(ta, q);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    const btn = document.querySelector('button.submit-button');
    if (btn) { btn.click(); return 'clicked-submit'; }
    ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
    return 'sent-enter';
  },
  titles: () => Array.from(document.querySelectorAll('.thought-group'))
      .map((g) => (g.innerText || '').split('\\n')[0].slice(0, 170)),
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]'))
      .map((g) => (g.innerText || '').split('\\n')[0].slice(0, 120)),
  bar: () => (document.querySelector('#statusbar') || {}).innerText || '',
  click: (txt) => {
    const b = Array.from(document.querySelectorAll('button')).find((x) => x.innerText.trim() === txt);
    if (!b) return 'NO-BUTTON ' + txt;
    b.click();
    return 'clicked ' + txt;
  },
  vis: () => Array.from(document.querySelectorAll('#statusrow button'))
      .map((b) => b.innerText.trim() + ':' + (b.offsetParent !== null ? 'shown' : 'hidden')).join(' | '),
  has: (s) => document.body.innerText.includes(s),
  body: () => document.body.innerText.length,
};
true;
`;

async function shot(path) {
  try {
    const r = await send("Page.captureScreenshot", { format: "png" });  // send() 已经把 .result 拆出来了
    require("fs").writeFileSync(path, Buffer.from(r.data, "base64"));
    return path;
  } catch (e) { return "shot-fail " + e.message; }
}

async function scenario(tag, question, button, needle) {
  const t0 = Date.now();
  const sent = await E(`__v13.ask(${JSON.stringify(question)})`);
  const pend = await waitFor(
    `__v13.has('等待审批') ? __v13.titles().filter(t=>t.includes('待批')).join(' // ') : null`,
    120000,
    "等待审批卡-" + tag
  );
  const visBefore = await E(`__v13.vis()`);
  const barBefore = await E(`__v13.bar()`);
  const tClick = new Date().toISOString();
  const clicked = await E(`__v13.click(${JSON.stringify(button)})`);
  const done = await waitFor(
    `__v13.titles().find(t => t.includes(${JSON.stringify(needle)})) || null`,
    150000,
    "步骤卡-" + tag
  );
  await sleep(8000);  // 等 _respond 的收尾一帧（⏹ 气泡 / 最终答案）落地再抓
  const visAfter = await E(`__v13.vis()`);
  const titles = await E(`__v13.titles()`);
  const barAfter = await E(`__v13.bar()`);
  return {
    tag, sent, clicked, tClick,
    pendWait: pend.waited, pendTitle: pend.value, needle,
    visBefore, visAfter, barBefore: barBefore.replace(/\n/g, " / "), barAfter: barAfter.replace(/\n/g, " / "),
    stepDoneWait: done.waited, stepDone: done.value,
    titles, rowsAfter: await E(`__v13.rows()`), secs: ((Date.now() - t0) / 1000).toFixed(1),
  };
}

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  };
  await send("Runtime.enable");
  await send("Page.enable");
  await nav();
  await evl(HELPERS);
  console.log("NAV-OK", JSON.stringify(await E(`({title: document.title, tools: !!document.querySelector('#statusrow')})`)));

  const out = [];
  const push = async (p) => { const r = await p; out.push(r); console.log("SCN " + JSON.stringify(r)); return r; };
  if (!ONLY.length || ONLY.includes("allow")) await push(scenario(
    "allow",
    "必须调用 run_python 工具，代码就写：open('/tmp/v13-live-allow.txt','w').write('ran'); print('V13ALLOW')。不要自己心算，直接照我给的代码调工具，然后把工具返回原样贴出来。",
    "✔ 允许", "🟢 成功"
  ));
  await shot("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.3/run/v13-allow.png");
  await sleep(4000);
  if (!ONLY.length || ONLY.includes("deny")) await push(scenario(
    "deny",
    "必须调用 run_python 工具，代码就写：open('/tmp/v13-live-deny.txt','w').write('ran')。只做这一次工具调用，然后告诉我工具返回了什么。",
    "✖ 拒绝", "⚪ 已拒绝"
  ));
  await shot("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.3/run/v13-deny.png");
  await sleep(4000);
  if (!ONLY.length || ONLY.includes("stop")) await push(scenario(
    "stop",
    "必须调用 run_python 工具，代码就写：open('/tmp/v13-live-stop.txt','w').write('ran')。只做这一次工具调用。",
    "■ 停止", "随停止取消"
  ));
  await shot("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.3/run/v13-stop.png");
  console.log("ALL " + JSON.stringify(out.map(x => x.tag)));
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
