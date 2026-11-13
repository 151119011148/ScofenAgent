// v1.4 补测两条：
//  A) 进程重启后选中旧会话接着问 —— 屏上累加还在，模型那侧记得吗？（量【待补】那条遗留）
//  B) 多步任务真按到 ■ 停止：待批卡 → ⏹ 随停止取消 → 已停止，且同会话前几轮不丢
const PORT = 9333;
const URL = process.env.V14URL || "http://127.0.0.1:7861/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((res) => { const n = ++id; pending.set(n, res); ws.send(JSON.stringify({ id: n, method, params })); });
}
async function evl(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("JS " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result && r.result.value;
}
const PAGE = `
window.__t = {
  ask: (q) => {
    const ta = document.querySelector("textarea"); ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    set.call(ta, q); ta.dispatchEvent(new Event("input", { bubbles: true }));
    const b = document.querySelector("button.submit-button");
    if (b) { b.click(); return "clicked"; } return "no-submit";
  },
  state: () => { const el = document.querySelector("#statusbar .pill-state i"); return el ? el.textContent : "?"; },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  click: (t) => { const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === t); if (!b) return "NO-BUTTON " + t; b.click(); return "clicked " + t; },
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]')).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 64)),
  last: () => { const r = document.querySelectorAll('.message-row, [data-testid="chat-message"]'); return r.length ? (r[r.length - 1].innerText || "").slice(0, 400) : ""; },
  cards: () => Array.from(document.querySelectorAll(".thought-group")).map((g) => (g.innerText || "").split("\\n")[0].slice(0, 90)),
  clickSel: (needle) => {
    const ls = Array.from(document.querySelectorAll("#sessions label"));
    const hit = ls.find((l) => (l.innerText || "").indexOf(needle) >= 0);
    if (!hit) return "NO-SEL"; const inp = hit.querySelector("input"); (inp || hit).click(); return "sel:" + (hit.innerText || "").trim().slice(0, 30);
  },
};
"ready";
`;
async function waitState(want, ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const st = await evl("__t.state()");
    if (want.includes(st)) return { st, waited: ((Date.now() - t0) / 1000).toFixed(1) };
    await sleep(400);
  }
  return { timeout: true, waited: ((Date.now() - t0) / 1000).toFixed(1) };
}
async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
  await send("Runtime.enable"); await send("Page.enable");
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) { await sleep(1000); if (await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')")) break; }
  await evl(PAGE);

  // ---- A) 重启后的旧会话 ----
  console.log("A.sels " + JSON.stringify(await evl("Array.from(document.querySelectorAll('#sessions label')).map(l=>l.innerText.trim().slice(0,30))")));
  console.log("A.select " + await evl(`__t.clickSel("73")`));
  await sleep(3000);
  const aBefore = await evl("__t.rows()");
  console.log("A.before rows=" + aBefore.length);
  console.log("A.ask " + await evl(`__t.ask("我最早让你记住的那个数字是多少？只回那个数字；如果你没有这段记忆，只回「不记得」。调用 final_answer，不要调用其他工具。")`));
  await waitState(["完成", "已停止", "步数用满"], 120000);
  await sleep(6000);
  console.log("A.last " + JSON.stringify(await evl("__t.last()")));
  console.log("A.rows " + JSON.stringify(await evl("__t.rows()")));
  console.log("A.bar " + JSON.stringify(await evl("__t.bar()")));

  // ---- B) 多步任务按停止 ----
  console.log("B.ask " + await evl(`__t.ask("必须依次调用 run_python 两次：第一次代码写 print('B1')，第二次代码写 print('B2')。每次都要真正调用工具，不要合并。两步都完成后用 final_answer 把两个返回贴出来。")`));
  let sawRun = false;
  for (let i = 0; i < 400; i++) {
    const st = await evl("__t.state()");
    if (st === "生成中") sawRun = true;
    if (st === "等待审批") { sawRun = true; break; }
    if (st === "完成" || st === "已停止" || st === "步数用满") break;
    await sleep(200);
  }
  const tStop = new Date().toISOString();
  const pendCards = await evl("__t.cards()");
  console.log("B.beforeStop cards=" + JSON.stringify(pendCards) + " sawRun=" + sawRun + " at " + tStop);
  console.log("B.stop " + await evl(`__t.click("■ 停止")`));
  console.log("B.end " + JSON.stringify(await waitState(["已停止", "完成", "步数用满"], 120000)));
  await sleep(7000);
  console.log("B.cards " + JSON.stringify(await evl("__t.cards()")));
  console.log("B.rows " + JSON.stringify(await evl("__t.rows()")));
  console.log("B.bar " + JSON.stringify(await evl("__t.bar()")));
  await send("Page.captureScreenshot", { format: "png" }).then((r) => require("fs").writeFileSync("/tmp/v14-stop2.png", Buffer.from(r.data, "base64"))).catch(() => {});
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
