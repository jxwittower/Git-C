const { chromium } = require('playwright');
const fs=require('fs');
const path=require('path');
const OUT=path.resolve('hsk_auth_probe');
for(const d of ['screenshots','semantics','network']) fs.mkdirSync(path.join(OUT,d),{recursive:true});
const safe=s=>(s||'page').replace(/[\\/:*?"<>|\s]+/g,'_').slice(0,80);
let seq=0;
async function enableSem(p){const ph=p.locator('flt-semantics-placeholder');if(await ph.count()){await ph.first().evaluate(el=>el.click()).catch(async()=>{await ph.first().focus();await p.keyboard.press('Enter');});await p.waitForTimeout(1200);}}
async function dump(p,label){seq++; const pre=String(seq).padStart(3,'0'); await p.waitForTimeout(1000); const file=`${pre}_${safe(label)}`; await p.screenshot({path:path.join(OUT,'screenshots',file+'.png'),fullPage:true,animations:'disabled'}); const sem=await p.locator('flt-semantics').evaluateAll(es=>es.slice(0,1500).map((e,i)=>({i,role:e.getAttribute('role'),label:e.getAttribute('aria-label'),text:(e.innerText||'').trim(),tab:e.getAttribute('tabindex'),rect:(()=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()}))).catch(()=>[]); fs.writeFileSync(path.join(OUT,'semantics',file+'.json'),JSON.stringify(sem,null,2)); fs.writeFileSync(path.join(OUT,'semantics',file+'.txt'),(await p.locator('body').innerText().catch(()=>''))); console.log('CAPTURE',file,'SEM',sem.length,'URL',p.url()); return sem;}
function summarize(sem){return sem.filter(x=>x.text||x.label||x.role).map(x=>({role:x.role,label:x.label,text:(x.text||'').slice(0,120),rect:x.rect}));}
async function clickText(p,text){for(const sel of [p.getByRole('button',{name:text,exact:true}),p.getByText(text,{exact:true}),p.locator('flt-semantics').filter({hasText:text})]){try{if(await sel.count()){const el=sel.first();if(await el.isVisible()){await el.click({timeout:5000});await p.waitForTimeout(1500);return true;}}}catch{}}return false;}
(async()=>{
 const credPath=process.env.HSK_CREDS_FILE; if(!credPath) throw new Error('HSK_CREDS_FILE missing'); const creds=JSON.parse(fs.readFileSync(credPath,'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
 const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN',acceptDownloads:true});
 const p=await ctx.newPage();
 let reqNo=0;
 p.on('response',async r=>{try{const u=r.url(); if(!u.includes('hsk.blcu.edu.cn/api/')) return; reqNo++; const rec={n:reqNo,status:r.status(),method:r.request().method(),url:u,headers:r.headers()}; const ct=(r.headers()['content-type']||''); if(/json|text/.test(ct)){const b=await r.text().catch(()=>null); if(b&&b.length<3000000) rec.body=b;} fs.writeFileSync(path.join(OUT,'network',String(reqNo).padStart(3,'0')+'.json'),JSON.stringify(rec,null,2)); console.log('API',rec.status,rec.method,u);}catch{}});
 await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'domcontentloaded',timeout:30000}); await p.waitForTimeout(13000); await enableSem(p); let sem=await dump(p,'登录页');
 const email=p.locator('input[aria-label="邮箱"]'); const pass=p.locator('input[aria-label="密码"]'); if(!await email.count()||!await pass.count()) throw new Error('Login fields not found'); await email.fill(creds.user); await pass.fill(creds.pass); const lb=p.getByRole('button',{name:'登录',exact:true}); if(!await lb.count()) throw new Error('Login button not found'); await lb.click(); await p.waitForTimeout(5000); await enableSem(p); sem=await dump(p,'登录后首页'); console.log('POSTLOGIN',JSON.stringify(summarize(sem).slice(0,300),null,2));
 const nav=['首页','检索','统计','工具','帮助'];
 for(const item of nav){if(await clickText(p,item)){await enableSem(p); const s=await dump(p,item+'_入口'); console.log('NAV',item,JSON.stringify(summarize(s).slice(0,350),null,2));}}
 // If statistics page exposes known tabs, visit each without changing data.
 if(await clickText(p,'统计')){for(const t of ['概况','国家和地区','作文题目','错误汇总','错误详情','分类统计']){if(await clickText(p,t)){await enableSem(p);const s=await dump(p,'统计_'+t);console.log('STAT',t,JSON.stringify(summarize(s).slice(0,300),null,2));}}}
 await ctx.storageState({path:path.join(OUT,'storage_state.json')});
 fs.writeFileSync(path.join(OUT,'summary.json'),JSON.stringify({screenshots:seq,apiResponses:reqNo,finished:new Date().toISOString()},null,2));
 // do not store credentials
 await browser.close();
})();
