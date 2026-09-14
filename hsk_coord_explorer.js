const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.resolve('hsk_coord_output');
for (const d of ['screenshots','metadata','texts','network','downloads','results']) fs.mkdirSync(path.join(OUT,d), {recursive:true});
let shotNo = 0, apiNo = 0;
const ops = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const safe = s => (s || 'page').replace(/[\\/:*?"<>|\s]+/g,'_').replace(/^_+|_+$/g,'').slice(0,110) || 'page';
function op(type, data={}) {
  const row = {time:new Date().toISOString(), type, ...data};
  ops.push(row);
  fs.appendFileSync(path.join(OUT,'metadata','operations.jsonl'), JSON.stringify(row)+'\n');
  console.log('OP', type, JSON.stringify(data).slice(0,1200));
}

async function semOn(p) {
  const q=p.locator('flt-semantics-placeholder');
  if(await q.count()) {
    try { await q.first().evaluate(e=>e.click()); }
    catch { try { await q.first().focus(); await p.keyboard.press('Enter'); } catch {} }
    await sleep(450);
  }
}
async function semanticRows(p) {
  return p.locator('flt-semantics').evaluateAll(es=>es.map((e,i)=>{
    const r=e.getBoundingClientRect();
    return {i,role:e.getAttribute('role')||'',label:e.getAttribute('aria-label')||'',text:(e.innerText||'').trim(),value:e.getAttribute('aria-valuetext')||'',x:r.x,y:r.y,w:r.width,h:r.height};
  }).filter(x=>x.w>0&&x.h>0&&(x.text||x.label||x.role))).catch(()=>[]);
}
async function inputRows(p) {
  return p.locator('input,textarea,select').evaluateAll(es=>es.map((e,i)=>{
    const r=e.getBoundingClientRect();
    return {i,tag:e.tagName,type:e.type||'',aria:e.getAttribute('aria-label')||'',ph:e.placeholder||'',value:(e.value||'').slice(0,100),x:r.x,y:r.y,w:r.width,h:r.height};
  }).filter(x=>x.w>0&&x.h>0)).catch(()=>[]);
}
async function capture(p,label,extra={}) {
  await semOn(p); await sleep(250); shotNo++;
  const base=String(shotNo).padStart(3,'0')+'_'+safe(label);
  await p.screenshot({path:path.join(OUT,'screenshots',base+'.png'),fullPage:true,animations:'disabled'}).catch(()=>p.screenshot({path:path.join(OUT,'screenshots',base+'.png'),animations:'disabled'}));
  const sem=await semanticRows(p), ins=await inputRows(p), txt=await p.locator('body').innerText().catch(()=>'');
  fs.writeFileSync(path.join(OUT,'metadata',base+'.json'),JSON.stringify({label,url:p.url(),title:await p.title().catch(()=>''),inputs:ins,semantics:sem,...extra},null,2));
  fs.writeFileSync(path.join(OUT,'texts',base+'.txt'),txt);
  const meta={n:shotNo,label,url:p.url(),title:await p.title().catch(()=>''),png:base+'.png',inputs:ins,...extra};
  fs.appendFileSync(path.join(OUT,'metadata','captures.jsonl'),JSON.stringify(meta)+'\n');
  op('capture',meta);
  return {base,sem,ins,txt};
}
async function typeFlutter(loc,value,delay=40) {
  await loc.click({force:true});
  await loc.press('Control+A').catch(()=>{}); await loc.press('Backspace').catch(()=>{});
  await loc.pressSequentially(value,{delay}); await sleep(150);
  return (await loc.inputValue().catch(()=>'')).length;
}
async function clickRole(p,role,name,exact=true,wait=900) {
  const l=p.getByRole(role,{name,exact});
  if(await l.count()) { const e=l.first(); if(await e.isVisible()) { await e.click({timeout:5000}); await sleep(wait); await semOn(p); return true; } }
  return false;
}
async function clickText(p,name,exact=true,wait=900) {
  const tries=[p.getByRole('button',{name,exact}),p.getByRole('tab',{name,exact}),p.getByRole('radio',{name,exact}),p.getByText(name,{exact}),p.locator('flt-semantics').filter({hasText:name})];
  for(const l of tries){try{if(await l.count()){const e=l.first();if(await e.isVisible()){await e.click({timeout:5000});await sleep(wait);await semOn(p);return true}}}catch{}}
  return false;
}
async function waitCaptchaCode() {
  const f=process.env.HSK_CAPTCHA_FILE;
  for(let i=0;i<900;i++){if(f&&fs.existsSync(f)){const s=fs.readFileSync(f,'utf8').trim();if(s){try{fs.unlinkSync(f)}catch{}return s}}await sleep(1000)}
  throw new Error('CAPTCHA_TIMEOUT');
}
async function login(p,c) {
  await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'domcontentloaded',timeout:30000});
  await sleep(14000); await semOn(p); await capture(p,'01_登录页_实测');
  const em=p.locator('input[aria-label="邮箱"]'), pw=p.locator('input[aria-label="密码"]');
  if(!await em.count()||!await pw.count()) throw new Error('LOGIN_FIELDS_NOT_FOUND');
  if(await typeFlutter(em,c.user)<5 || await typeFlutter(pw,c.pass)<6) throw new Error('LOGIN_TYPING_FAILED');
  await p.getByRole('button',{name:'登录',exact:true}).click(); await sleep(1500); await semOn(p);
  const ci=p.locator('input[aria-label="请输入图片中的字符"]');
  if(await ci.count()) {
    await capture(p,'02_人机验证页面_实测');
    const box=await p.locator('flt-semantics[role="img"]').filter({visible:true}).last().boundingBox().catch(()=>null);
    if(box) await p.screenshot({path:path.join(OUT,'captcha.png'),clip:{x:Math.max(0,box.x-15),y:Math.max(0,box.y-15),width:box.width+30,height:box.height+30}});
    else await p.screenshot({path:path.join(OUT,'captcha.png'),fullPage:true});
    fs.writeFileSync(path.join(OUT,'captcha_ready.txt'),'ready'); console.log('CAPTCHA_READY');
    const code=await waitCaptchaCode(); await typeFlutter(ci,code,60);
    if(!await clickRole(p,'button','验证',true,4200)) throw new Error('CAPTCHA_VERIFY_MISSING');
  }
  await sleep(1800); const a=await capture(p,'03_登录后首页_完整页');
  if(/人机验证|请输入密码|创建新账户/.test(a.txt)) throw new Error('LOGIN_NOT_COMPLETED');
  op('login-success',{url:p.url()});
}

const navXY={首页:[80,93],检索:[80,158],统计:[80,224],工具:[80,289],帮助:[80,354]};
async function nav(p,name,label=name){const [x,y]=navXY[name];await p.mouse.click(x,y);await sleep(1500);await semOn(p);return capture(p,label);}
async function resetSearch(p){const b=p.getByRole('button',{name:'重置',exact:true});if(await b.count()){await b.first().click();await sleep(600);await semOn(p)}}
async function submitSearch(p){const b=p.getByRole('button',{name:'检索',exact:true});if(await b.count()){await b.first().click();await sleep(2300);await semOn(p);return true}return false}
async function saveDownloadIfAny(p,label){
  const candidates=[p.getByText('下载',{exact:false}),p.getByText('导出',{exact:false})];
  for(const l of candidates){try{const n=Math.min(3,await l.count());for(let i=0;i<n;i++){const e=l.nth(i);if(!await e.isVisible())continue;try{const w=p.waitForEvent('download',{timeout:5000});await e.click();const d=await w;const fn=safe(label)+'_'+safe(d.suggestedFilename());await d.saveAs(path.join(OUT,'downloads',fn));op('download',{label,file:fn});return fn}catch{}}}catch{}}
  return null;
}
function hitCount(txt){const pats=[/共\s*([0-9,]+)\s*(?:条|篇|个|项)/,/([0-9,]+)\s*条结果/,/总数[:：]?\s*([0-9,]+)/];for(const r of pats){const m=txt.match(r);if(m)return m[1]}return null}
async function recordResult(p,mode,query,index){const c=await capture(p,`检索_${mode}_${index}_结果_${query}`,{mode,query,index,stage:'result'});op('search-result',{mode,query,index,hitCount:hitCount(c.txt),apiNo});return c}
async function captureDetails(p,prefix,max=2){
  const det=p.getByRole('button',{name:'详细',exact:true});
  let count=0;try{count=await det.count()}catch{}
  for(let i=0;i<Math.min(max,count);i++){
    try{const before=p.url();await det.nth(0).click();await sleep(1300);await capture(p,`${prefix}_代表性结果详情_${i+1}`);if(p.url()!==before){await p.goBack({waitUntil:'domcontentloaded',timeout:8000}).catch(()=>{});await sleep(1000)}else{let closed=false;for(const nm of ['关闭','返回','取消']){if(await clickText(p,nm,true,500)){closed=true;break}}if(!closed)await p.keyboard.press('Escape').catch(()=>{});await sleep(700)}}catch(e){op('detail-error',{prefix,index:i+1,error:String(e)})}
  }
}
async function selectPopupOption(p,buttonRegex,option){
  const b=p.getByRole('button',{name:buttonRegex}); if(!await b.count()) return false;
  await b.first().click();await sleep(450);await semOn(p);
  const o=p.getByRole('button',{name:option,exact:true});if(await o.count()){await o.first().click();await sleep(550);return true}
  await p.keyboard.press('Escape').catch(()=>{});return false;
}
async function popupOptions(p,buttonRegex){
  const b=p.getByRole('button',{name:buttonRegex});if(!await b.count())return[];await b.first().click();await sleep(450);await semOn(p);
  const vals=await p.locator('flt-semantics[role="dialog"][aria-label="Popup menu"] flt-semantics[role="button"]').allInnerTexts().catch(()=>[]);
  const vals2=vals.length?vals:await p.locator('flt-semantics[role="button"]').allInnerTexts().catch(()=>[]);
  await p.keyboard.press('Escape').catch(()=>{});await sleep(300);return[...new Set(vals2.map(x=>x.trim()).filter(Boolean))];
}

async function runGeneral(p){
  await clickRole(p,'tab','字符串一般检索');const qs=['把','被','了','给','是'];
  for(let i=0;i<qs.length;i++){const q=qs[i];await resetSearch(p);const inp=p.locator('input[aria-label="多个关键词用空格隔开"]');await typeFlutter(inp,q);await capture(p,`检索_字符串一般检索_${i+1}_条件_${q}`,{mode:'字符串一般检索',query:q,index:i+1,stage:'condition'});await submitSearch(p);await recordResult(p,'字符串一般检索',q,i+1);if(i===0){await captureDetails(p,'字符串一般检索_把',3);await saveDownloadIfAny(p,'字符串一般检索_把')}}
}
async function runTerms(p){
  await clickRole(p,'tab','特定条件检索');const qs=[['如果','就'],['虽然','但是'],['因为','所以'],['不但','而且'],['只要','就']];
  for(let i=0;i<qs.length;i++){const [a,b]=qs[i];await resetSearch(p);const ins=p.locator('input').filter({visible:true});const n=await ins.count();if(n<5){op('search-skip',{mode:'特定条件检索',query:a+'…'+b,reason:'inputs<5'});continue}await typeFlutter(ins.nth(0),a);await typeFlutter(ins.nth(4),b);const q=a+'…'+b;await capture(p,`检索_特定条件检索_${i+1}_条件_${q}`,{mode:'特定条件检索',query:q,index:i+1,stage:'condition'});await submitSearch(p);await recordResult(p,'特定条件检索',q,i+1);if(i===0)await saveDownloadIfAny(p,'特定条件检索_'+q)}
}
async function runPairs(p){
  await clickRole(p,'tab','词语搭配检索');const qs=[['学生','主谓关系'],['汉语','定中结构'],['认真','状中结构'],['学习','述宾结构'],['提高','述补结构']];
  for(let i=0;i<qs.length;i++){const [word,rel]=qs[i];await resetSearch(p);const inp=p.locator('input[aria-label="要检索的字或词"]');await typeFlutter(inp,word);let ok=await selectPopupOption(p,/Show menu/,rel);const q=word+' + '+rel;await capture(p,`检索_词语搭配检索_${i+1}_条件_${word}_${rel}`,{mode:'词语搭配检索',query:q,index:i+1,relationSelected:ok,stage:'condition'});await submitSearch(p);await recordResult(p,'词语搭配检索',q,i+1);if(i===0)await saveDownloadIfAny(p,'词语搭配检索_'+word)}
}
async function runWrongJu(p){
  await clickRole(p,'tab','错句检索');let opts=await popupOptions(p,/Show menu/);opts=opts.filter(x=>x!=='不限'&&!x.startsWith('Show menu')).slice(0,5);if(opts.length<5) opts=['把字句','被字句','比字句','是字句','兼语句'];fs.writeFileSync(path.join(OUT,'results','错句检索_测试句型.json'),JSON.stringify(opts,null,2));
  for(let i=0;i<5;i++){const q=opts[i];await resetSearch(p);const ok=await selectPopupOption(p,/Show menu/,q);await capture(p,`检索_错句检索_${i+1}_条件_${q}`,{mode:'错句检索',query:q,index:i+1,selected:ok,stage:'condition'});await submitSearch(p);await recordResult(p,'错句检索',q,i+1);if(i===0)await saveDownloadIfAny(p,'错句检索_'+q)}
}
async function setNationCondition(p,nation){
  const b=p.getByRole('button',{name:'检索条件',exact:true});if(!await b.count())return false;await b.first().click();await sleep(650);await semOn(p);
  const group=p.locator('flt-semantics[role="group"][aria-label*="考生国籍"]');if(!await group.count()){await p.keyboard.press('Escape').catch(()=>{});return false}
  const box=await group.first().boundingBox();if(!box){await p.keyboard.press('Escape').catch(()=>{});return false}
  await p.mouse.click(box.x+70,box.y+42);await sleep(400);await semOn(p);
  const o=p.getByRole('button',{name:nation,exact:true});if(!await o.count()){await p.keyboard.press('Escape').catch(()=>{});await p.keyboard.press('Escape').catch(()=>{});return false}
  await o.first().click();await sleep(450);
  await p.mouse.click(1017,323);await sleep(450);
  await capture(p,`检索条件_考生国籍_${nation}`,{nation,stage:'condition-modal'});
  await p.mouse.click(1038,232);await sleep(600);await semOn(p);return true;
}
async function runConditionOnly(p,tab,mode){
  await clickRole(p,'tab',tab);const nations=['韩国','日本','新加坡','印度尼西亚','泰国'];
  for(let i=0;i<nations.length;i++){const nation=nations[i];await resetSearch(p);const ok=await setNationCondition(p,nation);await capture(p,`检索_${mode}_${i+1}_条件_${nation}`,{mode,query:nation,index:i+1,nationSelected:ok,stage:'condition'});await submitSearch(p);await recordResult(p,mode,nation,i+1);if(i===0){await captureDetails(p,mode+'_'+nation,2);await saveDownloadIfAny(p,mode+'_'+nation)}}
}
async function runSearches(p){
  await nav(p,'检索','检索系统_入口完整页');
  await runGeneral(p);await runTerms(p);await runPairs(p);await runWrongJu(p);await runConditionOnly(p,'错篇检索','错篇检索');await runConditionOnly(p,'全篇检索','全篇检索');
}

async function scrollShots(p,prefix,steps=4,dy=720){for(let i=1;i<=steps;i++){await p.mouse.move(1100,820);await p.mouse.wheel(0,dy);await sleep(700);await capture(p,`${prefix}_滚动${i}`)}await p.mouse.wheel(0,-10000);await sleep(600)}
async function statOverview(p){await clickRole(p,'tab','概况');await capture(p,'统计_概况_字分布');await clickRole(p,'radio','词分布');await capture(p,'统计_概况_词分布');await p.mouse.wheel(0,650);await sleep(600);await capture(p,'统计_概况_字词级别区域');await clickRole(p,'radio','词级别');await capture(p,'统计_概况_词级别分布');await p.mouse.wheel(0,-5000);await sleep(500)}
async function statNations(p){await clickRole(p,'tab','国家和地区');for(const v of ['表格','柱状图','折线图','饼图']){const ok=await clickRole(p,'radio',v);if(!ok)await clickText(p,v,true);await capture(p,'统计_国家和地区_'+v)} }
async function statTopics(p){await clickRole(p,'tab','作文题目');await capture(p,'统计_作文题目_表格顶部');await scrollShots(p,'统计_作文题目_表格',5,650)}
async function switchMenuCapture(p,tab,prefix){await clickRole(p,'tab',tab);await capture(p,prefix+'_默认');const btn=p.getByRole('button',{name:/^Show menu/});if(!await btn.count())return;await btn.first().click();await sleep(450);await semOn(p);const buttons=await p.locator('flt-semantics[role="dialog"][aria-label="Popup menu"] flt-semantics[role="button"]').allInnerTexts().catch(()=>[]);const opts=[...new Set(buttons.map(x=>x.trim()).filter(Boolean))];await capture(p,prefix+'_类型菜单');await p.keyboard.press('Escape').catch(()=>{});for(const o of opts.slice(0,8)){try{const b=p.getByRole('button',{name:/^Show menu/});if(await b.count())await b.first().click();await sleep(300);const v=p.getByRole('button',{name:o,exact:true});if(await v.count()){await v.first().click();await sleep(1000);await capture(p,prefix+'_'+o)}}catch(e){op('stat-switch-error',{tab,option:o,error:String(e)})}}
}
async function statClassify(p){await clickRole(p,'tab','分类统计');for(const t of ['按国家和地区统计','按证书级别统计','按标点统计','按年份统计']){const ok=await clickRole(p,'tab',t);if(ok){await capture(p,'统计_分类统计_'+t);await scrollShots(p,'统计_分类统计_'+t,2,650)}}}
async function runStats(p){await nav(p,'统计','统计系统_入口完整页');await statOverview(p);await statNations(p);await statTopics(p);await switchMenuCapture(p,'错误汇总','统计_错误汇总');await switchMenuCapture(p,'错误详情','统计_错误详情');await statClassify(p)}

const depSents=['我昨天在北京买了一本汉语词典。','他把作业写完了以后就去休息了。','这件事情给我带来了很大的帮助。','如果明天下雨，我们就不去公园了。','虽然汉语很难，但是我越来越喜欢学习汉语。'];
const tokSents=['我喜欢学习汉语。','北京语言大学有丰富的语言资源。','提高汉语水平需要长期练习。','他把作业写完以后去休息了。','国际中文教育正在快速发展。'];
const aiQs=['如何检索“把”字句？','如何按国家和地区统计作文？','语料库目前有多少篇作文？','怎样下载检索结果？','HSK动态作文语料库适合研究哪些问题？'];
async function runTextTool(p,tab,buttonName,cases,prefix){await clickRole(p,'tab',tab);for(let i=0;i<cases.length;i++){const q=cases[i];const area=p.locator('textarea[aria-label="请输入"]');await typeFlutter(area,q,25);await capture(p,`${prefix}_${i+1}_输入`,{tool:tab,query:q,index:i+1,stage:'input'});await clickRole(p,'button',buttonName,true,2200);await capture(p,`${prefix}_${i+1}_结果`,{tool:tab,query:q,index:i+1,stage:'result'})}}
async function runAI(p){await clickRole(p,'tab','AI问答');for(let i=0;i<aiQs.length;i++){const q=aiQs[i];const inp=p.locator('input[aria-label="输入消息..."]');if(!await inp.count())throw new Error('AI_INPUT_NOT_FOUND');await typeFlutter(inp,q,25);await capture(p,`工具_AI问答_${i+1}_输入`,{tool:'AI问答',query:q,index:i+1,stage:'input'});await inp.press('Enter');await sleep(5500);await capture(p,`工具_AI问答_${i+1}_回答`,{tool:'AI问答',query:q,index:i+1,stage:'result'})}}
async function runTools(p){await nav(p,'工具','工具系统_入口完整页');await runTextTool(p,'依存句法分析','分析',depSents,'工具_依存句法分析');await runTextTool(p,'分词工具','分词',tokSents,'工具_分词');await runAI(p)}
async function runHelp(p){await nav(p,'帮助','帮助系统_入口完整页');for(const tab of ['使用说明','标注说明']){await clickRole(p,'tab',tab);await capture(p,'帮助_'+tab+'_顶部');await scrollShots(p,'帮助_'+tab,5,720)}}
async function runHome(p){await nav(p,'首页','首页_说明顶部');await scrollShots(p,'首页_说明',6,720)}

(async()=>{
  const creds=JSON.parse(fs.readFileSync(process.env.HSK_CREDS_FILE,'utf8'));
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
  const ctx=await browser.newContext({viewport:{width:1640,height:1000},ignoreHTTPSErrors:true,locale:'zh-CN',acceptDownloads:true});
  const p=await ctx.newPage();
  p.on('response',async r=>{try{const u=r.url();if(!u.includes('hsk.blcu.edu.cn/api/')||u.includes('/login/access-token'))return;apiNo++;const rq=r.request();const rec={n:apiNo,time:new Date().toISOString(),status:r.status(),method:rq.method(),url:u,postData:rq.postData()};const ct=r.headers()['content-type']||'';if(/json|text/.test(ct)){const body=await r.text().catch(()=>null);if(body&&body.length<4000000)rec.body=body}fs.writeFileSync(path.join(OUT,'network',String(apiNo).padStart(4,'0')+'.json'),JSON.stringify(rec,null,2))}catch{}});
  p.on('pageerror',e=>op('pageerror',{error:String(e)}));
  try { await login(p,creds); await runHome(p); await runSearches(p); await runStats(p); await runTools(p); await runHelp(p); await nav(p,'首页','最终_首页完整页'); }
  catch(e){op('fatal',{error:String(e),stack:e.stack});console.error('FATAL',e.stack||e);try{await capture(p,'异常现场_完整页')}catch{}process.exitCode=2}
  finally {fs.writeFileSync(path.join(OUT,'metadata','summary.json'),JSON.stringify({generatedAt:new Date().toISOString(),screenshots:shotNo,apiResponses:apiNo,operations:ops.length},null,2));await ctx.close().catch(()=>{});await browser.close().catch(()=>{})}
})();
