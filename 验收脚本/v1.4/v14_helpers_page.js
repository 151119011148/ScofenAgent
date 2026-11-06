
window.__v14 = {
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
  bar: () => ((document.querySelector("#statusbar") || {}).innerText || "").replace(/\n/g, " / "),
  running: () => {
    const t = (document.querySelector("#statusbar") || {}).innerText || "";
    return t.indexOf("生成中") >= 0 || t.indexOf("等待审批") >= 0 || t.indexOf("停止中") >= 0;
  },
  rows: () => Array.from(document.querySelectorAll(".message-row, [data-testid="chat-message"]"))
      .map((g) => (g.innerText || "").split("\n")[0].slice(0, 90)),
  cards: () => Array.from(document.querySelectorAll(".thought-group"))
      .map((g) => (g.innerText || "").split("\n")[0].slice(0, 120)),
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
true;