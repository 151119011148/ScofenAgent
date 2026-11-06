(() => {
  const rows = document.querySelectorAll('tr[data-st]');
  const btns = [...document.querySelectorAll('.bar button')];
  const label = b => b.textContent.trim();
  const res = { 标题: document.title, 行数: rows.length, 按钮: btns.map(label), 计数: {} };
  for (const b of btns) { b.click(); res.计数[label(b)] = document.getElementById('cnt').textContent.trim(); }
  btns[0].click();
  const st = {}, gp = {};
  rows.forEach(r => { st[r.dataset.st] = (st[r.dataset.st] || 0) + 1; gp[r.dataset.p] = (gp[r.dataset.p] || 0) + 1; });
  res.状态 = st; res.分组 = gp;
  const rowOf = id => [...rows].find(r => r.querySelector('b') && r.querySelector('b').textContent.trim() === id);
  res.逐条 = {};
  ["P0-1","P0-3","V1","V2","V3","V4","V5","D1","D3"].forEach(id => {
    const r = rowOf(id);
    res.逐条[id] = r ? (r.dataset.st + " | " + r.lastElementChild.textContent.trim()) : "查无此行";
  });
  res.结构 = {
    h2: [...document.querySelectorAll('h2')].map(h => h.id).join(","),
    看板小节: [...document.querySelectorAll('#s4 h3')].map(h => h.textContent.slice(0, 6)).join(","),
    记录小节: [...document.querySelectorAll('#s6 h3')].map(h => h.textContent.slice(0, 5)).join(","),
    正文宽: Math.round(document.querySelector('.wrap').getBoundingClientRect().width),
    横向溢出: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    外部资源: [...document.querySelectorAll('link[href],script[src]')].map(e => e.src || e.href).join(",") || "无"
  };
  return res;
})()
