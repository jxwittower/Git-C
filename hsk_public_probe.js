const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT='hsk_public_output'; fs.mkdirSync(OUT,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const ctx=await browser.newContext({viewport:{width:1600,height:1000},locale:'zh-CN'});
 const p=await ctx.newPage();
 const urls=['https://hsk.blcu.edu.cn/','https://hsk.blcu.edu.cn/Login'];
 const out=[];
 for(const u of urls){
  try{await p.goto(u,{waitUntil:'domcontentloaded',timeout:30000}); await p.waitForTimeout(2000); const body=await p.locator('body').innerText().catch(()=> ''); const links=await p.locator('a').evaluateAll(a=>a.map(x=>({t:(x.innerText||'').trim(),h:x.href})).filter(x=>x.t||x.h).slice(0,200)); const buttons=await p.locator('button,[role=button],[role=tab]').evaluateAll(a=>a.map(x=>(x.innerText||x.textContent||'').trim()).filter(Boolean).slice(0,200)); const rec={requested:u,final:p.url(),title:await p.title(),body:body.slice(0,30000),links,buttons}; out.push(rec); await p.screenshot({path:path.join(OUT,(u.endsWith('Login')?'login':'home')+'.png'),fullPage:true}); fs.writeFileSync(path.join(OUT,(u.endsWith('Login')?'login':'home')+'.html'),await p.content());}catch(e){out.push({requested:u,error:String(e)});}
 }
 fs.writeFileSync(path.join(OUT,'probe.json'),JSON.stringify(out,null,2));
 console.log(JSON.stringify(out.map(x=>({requested:x.requested,final:x.final,title:x.title,body:(x.body||'').slice(0,1000),buttons:x.buttons,links:(x.links||[]).slice(0,30)})),null,2));
 await browser.close();
})();
