(() => {
  const chk = Array.from(document.querySelectorAll("#sessions input[type=radio]")).map((i) => i.checked);
  const labs = Array.from(document.querySelectorAll("#sessions label")).map((l) => l.innerText.trim().replace(/\s+/g, " "));
  const bots = Array.from(document.querySelectorAll("#main [data-testid=bot]"));
  const users = Array.from(document.querySelectorAll("#main [data-testid=user]"));
  const bar = document.getElementById("statusbar");
  const pill = (k) => {
    const p = Array.from(document.querySelectorAll("#statusbar .pill")).find((e) => e.innerText.trim().startsWith(k));
    return p ? p.innerText.replace(/\s+/g, " ") : null;
  };
  return JSON.stringify({
    chk: chk,
    labs: labs,
    userN: users.length,
    botN: bots.length,
    last: bots.length ? bots[bots.length - 1].innerText.replace(/\s+/g, " ").slice(0, 200) : null,
    cardTitles: bots.map((b) => (b.querySelector("button, .prose") || {}).innerText || "").filter((x) => x.indexOf("步 ·") >= 0),
    heads: Array.from(document.querySelectorAll("#main [data-testid=bot] button")).map((x) => x.innerText.replace(/\s+/g, " ").slice(0, 130)),
    state: bar ? (bar.innerText.match(/状态\s*([^\s]+)/) || [])[1] : null,
    pillRun: pill("本题耗时"),
    pillWait: pill("本题审批"),
    pillPending: pill("待批"),
  });
})()
