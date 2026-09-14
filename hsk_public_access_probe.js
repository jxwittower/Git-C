const { chromium }=require('playwright');
const fs=require('fs');
const path=require('path');
const OUT='hsk_public_access'; fs.mkdirSync(OUT,{recursive:true});
const endpoints=[
 '/api/v1/statistics/all-num','/api/v1/statistics/nation','/api/v1/statistics/title',
 '/api/v1/statistics/wrong/zi','/api/v1/statistics/wrong/ci','/api/v1/statistics/wrong/ju','/api/v1/statistics/wrong/biaodian',
 '/api/v1/statistics/wrong/summary/biaodian','/api/v1/statistics/wrong/summary/pianzhang',
 '/api/v1/statistics/year/zi?page=1&per_page=5&year=1995','/api/v1/statistics/year/ci?page=1&per_page=5&year=1995',
 '/api/v1/nlp/tools/tokenize','/api/v1/sentence/search/keyword'
];
const routeCandidates=['/','/Login','/home','/Home','/search','/Search','/statistics','/Statistics','/tools','/Tools','/help','/Help','/#/statistics','/#/search','/#/tools'];
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-unsafe-swiftshader']}); const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN'}); const p=await ctx.newPage();
 const api=[];
 for(const ep of endpoints){try{let opts={}; if(ep.includes('/tokenize')) opts={method:'POST',data:{sentence:'我学习汉语。'}}; if(ep.includes('/search/keyword')) opts={method:'POST',data:{keyword:'把',page:1,per_page:5}}; const r=await ctx.request.fetch('https://hsk.blcu.edu.cn'+ep,opts); let txt=await r.text(); api.push({ep,status:r.status(),headers:r.headers(),body:txt.slice(0,10000)});console.log('API',ep,r.status(),txt.slice(0,500).replace(/\s+/g,' '));}catch(e){api.push({ep,error:String(e)});}}
 fs.writeFileSync(path.join(OUT,'api.json'),JSON.stringify(api,null,2));
 const routes=[];
 for(let i=0;i<routeCandidates.length;i++){const r=routeCandidates[i];try{await p.goto('https://hsk.blcu.edu.cn'+r,{waitUntil:'domcontentloaded',timeout:30000});await p.waitForTimeout(9000);const ph=p.locator('flt-semantics-placeholder');if(await ph.count()) await ph.first().evaluate(el=>el.click()).catch(()=>{});await p.waitForTimeout(800);const text=(await p.locator('body').innerText().catch(()=>''));const inputs=await p.locator('input').evaluateAll(es=>es.map(e=>({aria:e.getAttribute('aria-label'),type:e.type}))).catch(()=>[]);const rec={requested:r,final:p.url(),text:text.slice(0,10000),inputs};routes.push(rec);await p.screenshot({path:path.join(OUT,String(i+1).padStart(2,'0')+'_'+r.replace(/[^A-Za-z0-9]+/g,'_')+'.png'),fullPage:true});console.log('ROUTE',r,'=>',p.url(),'TEXT',text.slice(0,250).replace(/\s+/g,' '));}catch(e){routes.push({requested:r,error:String(e)});}}
 fs.writeFileSync(path.join(OUT,'routes.json'),JSON.stringify(routes,null,2)); await browser.close();
})();
