const pick = (sel) => Array.from(document.querySelectorAll(sel)).slice(0,6).map(e=>{
  const cs=getComputedStyle(e);
  return {sel, tag:e.tagName, cls:(e.className||'').toString().slice(0,90), text:(e.textContent||'').trim().slice(0,20), bg:cs.backgroundColor, color:cs.color};
});
const out = {};
out.tab = pick('button[role="tab"], .tab-wrapper, .tabitem, [id^="tab_"]');
out.send = Array.from(document.querySelectorAll('button')).filter(b=>/send|submit|stop|▶|➤/i.test(b.className+b.id+b.getAttribute('aria-label')+'')).slice(0,8).map(e=>{const cs=getComputedStyle(e);return{cls:(e.className||'').toString().slice(0,90),aria:e.getAttribute('aria-label'),bg:cs.backgroundColor,color:cs.color};});
out.microphone = pick('.input-row button, .gradio-container footer');
out.html = document.documentElement.className;
out.containerCls = (document.querySelector('.gradio-container')||{}).className;
return JSON.stringify(out,null,1);
