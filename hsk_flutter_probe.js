const { chromium } = require('playwright');
const fs=require('fs');
fs.mkdirSync('hsk_flutter_probe',{recursive:true});
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-dev-shm-usage']});
  const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN'});
  const p=await ctx.newPage();
  const net=[];
  p.on('response',r=>{if(r.url().includes('hsk.blcu.edu.cn')){const u=r.url();if(/main\.dart|flutter_service|canvaskit|assets|api|login/i.test(u)) net.push({s:r.status(),u});}});
  p.on('requestfailed',r=>net.push({fail:r.url(),err:r.failure()}));
  p.on('console',m=>console.log('CONSOLE',m.type(),m.text().slice(0,500)));
  p.on('pageerror',e=>console.log('PAGEERROR',String(e)));
  async function snap(name){await p.screenshot({path:`hsk_flutter_probe/${name}.png`,fullPage:true});fs.writeFileSync(`hsk_flutter_probe/${name}.html`,await p.content());console.log('SNAP',name,'url=',p.url(),'content=',(await p.content()).length);}
  await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'domcontentloaded',timeout:30000});
  await p.waitForTimeout(10000); await snap('01_after10s');
  console.log('NET1',JSON.stringify(net.slice(-100),null,2));
  console.log('TAGS1',await p.locator('*').evaluateAll(es=>[...new Set(es.map(e=>e.tagName.toLowerCase()))].filter(x=>x.startsWith('flt')||x==='canvas'||x==='input').slice(0,100)).catch(()=>[]));
  console.log('HTML1',(await p.content()).slice(-5000));
  // Flutter service worker often needs one reload on a clean profile.
  await p.reload({waitUntil:'domcontentloaded',timeout:30000}); await p.waitForTimeout(15000); await snap('02_reload15s');
  console.log('NET2',JSON.stringify(net.slice(-150),null,2));
  console.log('TAGS2',await p.locator('*').evaluateAll(es=>[...new Set(es.map(e=>e.tagName.toLowerCase()))].filter(x=>x.startsWith('flt')||x==='canvas'||x==='input').slice(0,100)).catch(()=>[]));
  const ph=p.locator('flt-semantics-placeholder');
  console.log('SEM_PLACEHOLDER',await ph.count());
  if(await ph.count()) {try{await ph.first().click({force:true});console.log('clicked semantics placeholder');}catch(e){console.log('sem click failed',String(e));}}
  await p.waitForTimeout(3000); await snap('03_semantics');
  const sem=await p.locator('flt-semantics').evaluateAll(es=>es.slice(0,300).map(e=>({role:e.getAttribute('role'),label:e.getAttribute('aria-label'),value:e.getAttribute('aria-valuetext'),text:e.innerText||'',tag:e.tagName,tab:e.getAttribute('tabindex')}))).catch(()=>[]);
  fs.writeFileSync('hsk_flutter_probe/semantics.json',JSON.stringify(sem,null,2));
  console.log('SEMCOUNT',sem.length); console.log('SEM',JSON.stringify(sem.slice(0,100),null,2));
  console.log('BODYTEXT',(await p.locator('body').innerText().catch(()=>'' )).slice(0,10000));
  await browser.close();
})();
