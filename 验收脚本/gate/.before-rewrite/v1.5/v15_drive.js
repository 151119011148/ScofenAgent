// v1.5 在线驱动器：在真浏览器里走 V6（重启后记忆还记不记得）三条路 + D7 另开脚本。
// 阶段 A（进程 1）跑 s1、s2；杀进程后同一库重启，阶段 B 跑 s3、s4、s5。
// 页面帮助段用 base64 注入：把带引号/正则的表达式直接拼进 Runtime.evaluate 会踩
// "missing ) after argument list"（v1.3 记录在案），注入一次后每步都探上下文还在不在。
const PORT = 9333;
const URL = process.env.V15URL || "http://127.0.0.1:7861/";
const ONLY = (process.env.V15ONLY || "").split(",").filter(Boolean);
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
const B64 = (s) => Buffer.from(s, "utf8").toString("base64");
const HELPERS = `
eval(new TextDecoder().decode(Uint8Array.from(atob("${B64(`
window.__v15 = {
  ask: (q) => {
    const ta = document.querySelector("textarea");
    ta.focus();
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    set.call(ta, q);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    const btn = document.querySelector("button.submit-button");
    if (btn) { btn.click(); return "clicked-submit"; }
    ta.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
    return "sent-enter";
  },
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\\n/g, " / "),
  running: () => {
    const t = (document.querySelector("#statusbar") || {}).innerText || "";
    return t.indexOf("生成中") >= 0 || t.indexOf("等待审批") >= 0 || t.indexOf("停止中") >= 0;
  },
  rows: () => Array.from(document.querySelectorAll('.message-row, [data-testid="chat-message"]'))
      .map((g) => (g.innerText || "").split("\\n")[0].slice(0, 90)),
  cards: () => Array.from(document.querySelectorAll(".thought-group"))
      .map((g) => (g.innerText || "").split("\\n")[0].slice(0, 120)),
  lastCard: () => {
    const gs = document.querySelectorAll(".thought-group");
    if (!gs.length) return "";
    return (gs[gs.length - 1].innerText || "").slice(0, 900);
  },
  body: () => document.body.innerText,
  has: (s) => document.body.innerText.indexOf(s) >= 0,
  sels: () => Array.from(document.querySelectorAll("#sessions label")).map((l) => (l.innerText || "").trim().slice(0, 40)),
  selChecked: () => Array.from(document.querySelectorAll("#sessions input")).map((i) => (i.checked ? "1" : "0")).join(""),
  clickSel: (needle) => {
    const ls = Array.from(document.querySelectorAll("#sessions label"));
    const hit = ls.find((l) => (l.innerText || "").indexOf(needle) >= 0);
    if (!hit) return "NO-SEL " + ls.map((l) => l.innerText).join(" | ");
    const inp = hit.querySelector("input");
    (inp || hit).click();
    return "sel:" + (hit.innerText || "").trim().slice(0, 40);
  },
  click: (txt) => {
    const b = Array.from(document.querySelectorAll("button")).find((x) => (x.innerText || "").trim() === txt);
    if (!b) return "NO-BUTTON " + txt;
    b.click();
    return "clicked " + txt;
  },
  vis: () => Array.from(document.querySelectorAll("#statusrow button"))
      .map((b) => (b.innerText || "").trim() + ":" + (b.offsetParent !== null ? "shown" : "hidden")).join(" | "),
};
true;`)}"), (c) => c.charCodeAt(0))))`;

async function E(expr) {
  let last = null;
  for (let i = 0; i < 8; i++) {
    try {
      if ((await evl("typeof __v15")) !== "object") await evl(HELPERS);
      return await evl(expr);
    } catch (e) {
      last = e;
      await sleep(2000);
    }
  }
  throw last;
}
async function nav() {
  await send("Page.navigate", { url: URL });
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    const ok = await evl("!!document.querySelector('textarea') && !!document.querySelector('#statusbar')");
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
async function shot(path) {
  try {
    const r = await send("Page.captureScreenshot", { format: "png" });
    require("fs").writeFileSync(path, Buffer.from(r.data, "base64"));
    return path;
  } catch (e) { return "shot-fail " + e.message; }
}

// 一次提问：起跑 -> 收尾，返回屏上快照
async function turn(tag, q, opts) {
  opts = opts || {};
  const t0 = Date.now();
  const sent = await E(`__v15.ask(${JSON.stringify(q)})`);
  const start = await waitFor("__v15.running() ? 'run' : null", 60000, "起跑-" + tag);
  let mid = null;
  if (opts.approve) {
    const pend = await waitFor("__v15.has('等待审批') ? __v15.cards().join(' // ') : null", 120000, "待批-" + tag);
    mid = { pendWait: pend.waited, pendCard: pend.value, visBefore: await E("__v15.vis()") };
    mid.clicked = await E(`__v15.click(${JSON.stringify(opts.approve)})`);
    mid.tClick = new Date().toISOString();
  }
  const done = await waitFor("!__v15.running() ? __v15.bar() : null", 240000, "收尾-" + tag);
  await sleep(6000); // 等 _respond 收尾那一帧落库、落屏
  const snap = {
    tag, sent, startWait: start.waited,
    barEnd: done.value && String(done.value).replace(/\s+/g, " "),
    rows: await E("__v15.rows()"),
    cards: await E("__v15.cards()"),
    lastCard: await E("__v15.lastCard()"),
    vis: await E("__v15.vis()"),
    sels: await E("__v15.sels()"),
    selChecked: await E("__v15.selChecked()"),
    secs: ((Date.now() - t0) / 1000).toFixed(1),
  };
  if (mid) Object.assign(snap, { mid });
  console.log("TURN " + JSON.stringify(snap));
  return snap;
}

async function clickSelWait(needle) {
  const r = await E(`__v15.clickSel(${JSON.stringify(needle)})`);
  await sleep(3500);
  const rows = await E("__v15.rows()");
  console.log("SELECT " + JSON.stringify({ needle, r, rows, sels: await E("__v15.sels()"), selChecked: await E("__v15.selChecked()") }));
  return { r, rows };
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
  console.log("NAV-OK " + JSON.stringify({ title: await E("document.title"), vis: await E("__v15.vis()"), sels: await E("__v15.sels()") }));

  const Q1 = "请把数字 73 记住，然后调用 final_answer 只回一句「记住了」。不要调用其他任何工具。";
  const Q2 = "我刚才让你记住的数字是多少？只回那个数字本身。调用 final_answer，不要调用其他任何工具。";
  // 判据题：答得出 73 = 记忆回来了；答「不记得」= 只恢复了屏幕上的字（v1.4 就是这个结果）
  const Q3 = "我刚才让你记住的数字是多少？如果你没有这段历史，只回「不记得」。调用 final_answer，不要调用其他任何工具。";
  const Q4 = "再把那个数字回给我一次，只回数字。调用 final_answer，不要调用其他任何工具。";

  const run = [];
  if (!ONLY.length || ONLY.includes("s1")) run.push(await turn("s1-首问-记住73", Q1));
  if (!ONLY.length || ONLY.includes("s2")) run.push(await turn("s2-同会话追问-重启前基线", Q2));
  if (!ONLY.length || ONLY.includes("s3")) {
    run.push({ select: await clickSelWait("73") });
    run.push(await turn("s3-重启后选旧会话-还记不记得", Q3));
  }
  if (!ONLY.length || ONLY.includes("s4")) {
    const nb = await E(`__v15.click("＋ 新会话")`);
    await sleep(2500);
    console.log("NEW-SESSION " + JSON.stringify({ nb, rows: await E("__v15.rows()"), sels: await E("__v15.sels()") }));
    run.push(await turn("s4-重启后新会话-必须不记得", Q3));
  }
  if (!ONLY.length || ONLY.includes("s5")) {
    run.push({ select: await clickSelWait("73") });
    run.push(await turn("s5-重启后那条会话继续问", Q4));
  }
  await shot("/tmp/v15-live.png");
  console.log("ALL " + JSON.stringify(run.map((x) => x.tag || "select")));
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
