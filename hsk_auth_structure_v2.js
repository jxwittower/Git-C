const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT = path.resolve('hsk_structure_output');
for (const d of ['screenshots','semantics','network','texts','metadata']) fs.mkdirSync(path.join(OUT,d), {recursive:true});
let shot = 0, apiNo = 0;
const safe = s => (s || 'page').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0,100);
async function wait(p, ms=1200){ await p.waitForTimeout(ms); }
async function enableSem(p){
  const ph=p.locator('flt-semantics-placeholder');
  if(await ph.count()){
    try{ await ph.first().evaluate(el=>el.click()); }
    catch{ try{ await ph.first().focus(); await p.keyboard.press('Enter'); }catch{} }
    await wait(p,700);
  }
}
async function semRows(p){
  return p.locator('flt-semantics').evaluateAll(es=>es.map((e,i)=>{const r=e.getBoundingClientRect();return {i,role:e.getAttribute('role')||'',label:e.getAttribute('aria-label')||'',text:(e.innerText||'').trim(),value:e.getAttribute('aria-valuetext')||'',x:r.x,y:r.y,w:r.width,h:r.height,tag:e.tagName};}).filter(x=>x.w>0&&x.h>0)).catch(()=>[]);
}
async function inputs(p){
  return p.locator('input,textarea,select').evaluateAll(es=>es.map((e,i)=>{const r=e.getBoundingClientRect();return {i,tag:e.tagName,type:e.type||'',aria:e.getAttribute('aria-label')||'',placeholder:e.placeholder||'',x:r.x,y:r.y,w:r.width,h:r.height};}).filter(x=>x.w>0&&x.h>0)).catch(()=>[]);
}
async function capture(p,label){
  await enableSem(p); shot++;
  const base=String(shot).padStart(3,'0')+'_'+safe(label);
  await p.screenshot({path:path.join(OUT,'screenshots',base+'.png'),fullPage:true,animations:'disabled'});
  const s=await semRows(p), ins=await inputs(p), text=await p.locator('body').innerText().catch(()=>'');
  fs.writeFileSync(path.join(OUT,'semantics',base+'.json'),JSON.stringify({url:p.url(),title:await p.title(),semantics:s,inputs:ins},null,2));
  fs.writeFileSync(path.join(OUT,'texts',base+'.txt'),text);
  fs.appendFileSync(path.join(OUT,'metadata','captures.jsonl'),JSON.stringify({n:shot,label,url:p.url(),title:await p.title(),png:base+'.png',semantics:s.length,inputs:ins})+'\n');
  console.log('CAPTURE',label,'sem=',s.length,'inputs=',JSON.stringify(ins));
  console.log('CONTROLS',JSON.stringify(s.filter(x=>x.text||x.label||x.role).slice(0,250)));
  return {s,ins,text};
}
async function clickText(p,text,partial=false){
  const locs=[p.getByRole('button',{name:text,exact:!partial}),p.getByRole('tab',{name:text,exact:!partial}),p.getByRole('link',{name:text,exact:!partial}),p.getByText(text,{exact:!partial}),p.locator('flt-semantics').filter({hasText:text})];
  for(const loc of locs){
    try{
      const n=Math.min(5,await loc.count());
      for(let i=0;i<n;i++){const e=loc.nth(i);if(await e.isVisible()){await e.click({timeout:5000});await wait(p,1300);await enableSem(p);return true;}}
    }catch{}
  }
  return false;
}
(async()=>{
  const creds=JSON.parse(fs.readFileSync(process.env.HSK_CREDS_FILE,'utf8'));
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
  const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN',acceptDownloads:true});
  const p=await ctx.newPage();
  p.on('response',async r=>{
    try{
      const u=r.url();
      if(!u.includes('hsk.blcu.edu.cn/api/') || u.includes('/login/access-token')) return;
      apiNo++;
      const rec={n:apiNo,status:r.status(),method:r.request().method(),url:u};
      const ct=r.headers()['content-type']||'';
      if(/json|text/.test(ct)){const b=await r.text().catch(()=>null);if(b&&b.length<1500000)rec.body=b;}
      fs.writeFileSync(path.join(OUT,'network',String(apiNo).padStart(4,'0')+'.json'),JSON.stringify(rec,null,2));
    }catch{}
  });
  try{
    await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'domcontentloaded',timeout:30000});
    await wait(p,14000); await enableSem(p); await capture(p,'登录页_实测');
    const em=p.locator('input[aria-label="邮箱"]'), pw=p.locator('input[aria-label="密码"]');
    if(!await em.count()||!await pw.count()) throw new Error('LOGIN_FIELDS_NOT_FOUND');
    await em.fill(creds.user); await pw.fill(creds.pass);
    const btn=p.getByRole('button',{name:'登录',exact:true});
    if(!await btn.count()) throw new Error('LOGIN_BUTTON_NOT_FOUND');
    await btn.click(); await wait(p,7000); await enableSem(p);
    const after=await capture(p,'登录后首页_实测');
    if(/创建新账户/.test(after.text) && /邮箱/.test(after.text)) throw new Error('LOGIN_FAILED');
    for(const nav of ['首页','检索','统计','工具','帮助']){
      if(await clickText(p,nav)){await capture(p,nav+'_入口_实测');}
      else console.log('NAV_MISS',nav);
    }
    if(await clickText(p,'统计')){
      for(const t of ['概况','国家和地区','作文题目','错误汇总','错误详情','分类统计']){
        if(await clickText(p,t,true)) await capture(p,'统计_'+t+'_实测');
        else console.log('STAT_MISS',t);
      }
    }
    if(await clickText(p,'检索')){
      const cur=await capture(p,'检索_结构复核');
      const candidates=[...new Set(cur.s.map(x=>x.text||x.label).filter(Boolean))].filter(t=>/检索|搜索|错句|错篇|全文|词|条件|搭配|句/.test(t)&&t.length<35);
      console.log('SEARCH_CANDIDATES',JSON.stringify(candidates));
      for(const t of candidates.slice(0,20)){
        if(await clickText(p,t,true)){await capture(p,'检索子项_'+t+'_实测');}
      }
    }
    if(await clickText(p,'工具')){
      const cur=await capture(p,'工具_结构复核');
      const candidates=[...new Set(cur.s.map(x=>x.text||x.label).filter(Boolean))].filter(t=>/句法|依存|分词|AI|问答|分析|工具/.test(t)&&t.length<35);
      console.log('TOOL_CANDIDATES',JSON.stringify(candidates));
      for(const t of candidates.slice(0,15)){
        if(await clickText(p,t,true)){await capture(p,'工具子项_'+t+'_实测');}
      }
    }
    fs.writeFileSync(path.join(OUT,'metadata','summary.json'),JSON.stringify({screenshots:shot,apiResponses:apiNo,completedAt:new Date().toISOString()},null,2));
  }catch(e){
    console.error('FATAL',e.stack||String(e));
    try{await capture(p,'异常现场_实测');}catch{}
    process.exitCode=2;
  }finally{await ctx.close().catch(()=>{});await browser.close().catch(()=>{});}
})();
