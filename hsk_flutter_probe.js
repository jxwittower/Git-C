const { chromium } = require('playwright');
const fs=require('fs');
fs.mkdirSync('hsk_flutter_probe',{recursive:true});
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
  const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN'});
  const p=await ctx.newPage();
  const net=[];
  p.on('response',r=>{if(r.url().includes('hsk.blcu.edu.cn')){const u=r.url();if(/main\.dart|flutter_service|canvaskit|assets|api|login/i.test(u)) net.push({s:r.status(),u});}});
  p.on('requestfailed',r=>net.push({fail:r.url(),err:r.failure()}));
  p.on('console',m=>console.log('CONSOLE',m.type(),m.text().slice(0,500)));
  p.on('pageerror',e=>console.log('PAGEERROR',String(e)));
  async function snap(name){await p.screenshot({path:`hsk_flutter_probe/${name}.png`,fullPage:true,animations:'disabled'});fs.writeFileSync(`hsk_flutter_probe/${name}.html`,await p.content());console.log('SNAP',name,'url=',p.url(),'content=',(await p.content()).length);}
  await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'domcontentloaded',timeout:30000});
  await p.waitForTimeout(15000); await snap('01_login_rendered');
  const ph=p.locator('flt-semantics-placeholder');
  console.log('SEM_PLACEHOLDER',await ph.count());
  if(await ph.count()) {
    try {
      await ph.first().evaluate(el=>el.click());
      console.log('semantics enabled by DOM click');
    } catch(e) {
      console.log('DOM click failed',String(e));
      try {await ph.first().focus(); await p.keyboard.press('Enter'); console.log('semantics enabled by keyboard');} catch(e2){console.log('keyboard enable failed',String(e2));}
    }
  }
  await p.waitForTimeout(2500); await snap('02_semantics_enabled');
  const sem=await p.locator('flt-semantics').evaluateAll(es=>es.slice(0,500).map(e=>({role:e.getAttribute('role'),label:e.getAttribute('aria-label'),value:e.getAttribute('aria-valuetext'),text:e.innerText||'',tag:e.tagName,tab:e.getAttribute('tabindex'),left:e.style.left,top:e.style.top,width:e.style.width,height:e.style.height}))).catch(()=>[]);
  fs.writeFileSync('hsk_flutter_probe/semantics.json',JSON.stringify(sem,null,2));
  console.log('SEMCOUNT',sem.length); console.log('SEM',JSON.stringify(sem.slice(0,200),null,2));
  console.log('INPUTS',JSON.stringify(await p.locator('input,textarea').evaluateAll(es=>es.map(e=>({type:e.type,aria:e.getAttribute('aria-label'),placeholder:e.placeholder,value:e.value,outer:e.outerHTML.slice(0,500)}))).catch(()=>[]),null,2));
  console.log('BODYTEXT',(await p.locator('body').innerText().catch(()=>'' )).slice(0,10000));
  console.log('NET',JSON.stringify(net.slice(-200),null,2));
  await browser.close();
})();
