// 采样：一次提问期间，#statusbar 的状态胶囊到底变过哪几档、各停了多久。
// 背景：v1.4 驱动器每 700ms 轮询，两次都没抓到「生成中」（startWait 全是 60.5s 超时），
// 需要判定这是轮询粒度问题，还是 running 帧根本没上过屏。
const PORT = 9333;
const URL = process.env.V14URL || "http://127.0.0.1:7860/";
const Q =
  "调用 final_answer 写一段 400 字左右的话，主题是一个跑在本地的 agent。不要调用任何其他工具。";
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
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result && r.result.value;
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
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    if (await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')")) break;
  }
  // 页内采样器：每 120ms 记一次状态胶囊文本，最多 90 秒，问完由驱动侧取回
  await evl(`
window.__samp = { t0: 0, log: [] };
window.startSample = () => {
  __samp.t0 = performance.now();
  __samp.log = [];
  clearInterval(__samp.iv);
  __samp.iv = setInterval(() => {
    const el = document.querySelector("#statusbar .pill-state i");
    __samp.log.push(Math.round(performance.now() - __samp.t0) + ":" + (el ? el.textContent : "?"));
    if (__samp.log.length > 900) clearInterval(__samp.iv);
  }, 120);
  return "sampling";
};
window.askIt = (q) => {
  const ta = document.querySelector("textarea");
  ta.focus();
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
  set.call(ta, q);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  const b = document.querySelector("button.submit-button");
  if (b) { b.click(); return "clicked"; }
  return "no-submit";
};
"ready";
`);
  console.log(await evl("startSample()"));
  console.log(await evl(`askIt(${JSON.stringify(Q)})`));
  for (let i = 0; i < 120; i++) {
    await sleep(1000);
    const done = await evl(`(document.querySelector("#statusbar .pill-state i")||{}).textContent || "?"`);
    const n = await evl("__samp.log.length");
    if (i > 3 && (done === "完成" || done === "步数用满" || done === "已停止")) { console.log(`settle at ${i}s, state=${done}`); break; }
    if (i % 10 === 9) console.log(`t=${i}s state=${done} samples=${n}`);
  }
  await sleep(2500);
  const log = await evl("__samp.log.join(' ')");
  const seq = [];
  for (const item of log.split(" ")) {
    const st = item.split(":")[1];
    if (!seq.length || seq[seq.length - 1].s !== st) seq.push({ s: st, from: item.split(":")[0], n: 1 });
    else seq[seq.length - 1].n++;
  }
  console.log("STATES " + JSON.stringify(seq));
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
