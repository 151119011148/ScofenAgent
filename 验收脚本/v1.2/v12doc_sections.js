(() => {
  const h2 = [...document.querySelectorAll('h2')];
  const section = start => {
    const i = h2.indexOf(start);
    const stop = i + 1 < h2.length ? h2[i+1] : null;
    const out = [];
    let el = start.nextElementSibling;
    while (el && el !== stop) {
      if (el.tagName === 'H3') out.push(el.textContent.trim().slice(0, 26));
      el = el.nextElementSibling;
    }
    return out;
  };
  const byId = id => h2.find(h => h.id === id);
  return {
    第四节小节: section(byId('s4')),
    第六节小节: section(byId('s6')),
    第二节小节: section(byId('s2')),
    第五节小节: section(byId('s5')),
    第45存在: !![...document.querySelectorAll('#s4 ~ * , h3')].find(h => h.textContent.includes('4.5')),
    表格数: document.querySelectorAll('table').length,
    卡片数: document.querySelectorAll('.card').length
  };
})()
