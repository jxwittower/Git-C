const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = 'https://hsk.blcu.edu.cn';
const OUT = path.resolve('hsk_output');
for (const d of ['screenshots','html','data','downloads']) fs.mkdirSync(path.join(OUT,d), {recursive:true});

const now = () => new Date().toISOString();
const slug = (s) => (s || 'page').replace(/[\\/:*?"<>|\s]+/g,'_').replace(/^_+|_+$/g,'').slice(0,90) || 'page';
const ops = [];
let shotNo = 0;

function record(type, data={}) {
  const row = {time: now(), type, ...data};
  ops.push(row);
  fs.appendFileSync(path.join(OUT,'data','operations.jsonl'), JSON.stringify(row)+'\n');
  console.log(`[${type}]`, data.title || data.label || data.query || data.url || '');
}

async function settle(page, ms=1200) {
  await page.waitForLoadState('domcontentloaded').catch(()=>{});
  await page.waitForLoadState('networkidle', {timeout:7000}).catch(()=>{});
  await page.waitForTimeout(ms);
}

async function fullCapture(page, label, extra={}) {
  await settle(page, 700);
  shotNo += 1;
  const n = String(shotNo).padStart(3,'0');
  const title = await page.title().catch(()=> '');
  const url = page.url();
  const base = `${n}_${slug(label)}`;
  const png = path.join(OUT,'screenshots', `${base}.png`);
  const html = path.join(OUT,'html', `${base}.html`);
  await page.screenshot({path:png, fullPage:true, animations:'disabled'}).catch(async()=>{
    await page.screenshot({path:png, fullPage:false, animations:'disabled'});
  });
  fs.writeFileSync(html, await page.content().catch(()=>''));
  const text = (await page.locator('body').innerText().catch(()=>''));
  fs.writeFileSync(path.join(OUT,'data',`${base}.txt`), text.slice(0,200000));
  record('capture',{label,title,url,png:path.basename(png),...extra});
  return {label,title,url,png:path.basename(png),text};
}

async function visibleTexts(page, selector) {
  return await page.locator(selector).evaluateAll(els => els.filter(e => {
    const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
    return r.width>1 && r.height>1 && s.visibility!=='hidden' && s.display!=='none';
  }).map(e => (e.innerText||e.textContent||'').trim()).filter(Boolean).slice(0,200)).catch(()=>[]);
}

async function inspectPage(page, label) {
  const info = await page.evaluate(() => {
    const vis = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e); return r.width>1&&r.height>1&&s.display!=='none'&&s.visibility!=='hidden'; };
    return {
      url: location.href,
      title: document.title,
      links: [...document.querySelectorAll('a')].filter(vis).map(a=>({text:(a.innerText||'').trim(),href:a.href})).filter(x=>x.text||x.href).slice(0,300),
      buttons: [...document.querySelectorAll('button,[role=button],[role=tab],.el-tabs__item,.ant-tabs-tab')].filter(vis).map(b=>(b.innerText||b.textContent||'').trim()).filter(Boolean).slice(0,300),
      inputs: [...document.querySelectorAll('input,textarea,select')].filter(vis).map((e,i)=>({i,tag:e.tagName,type:e.type||'',name:e.name||'',placeholder:e.placeholder||'',value:e.value||'',aria:e.getAttribute('aria-label')||''})).slice(0,100)
    };
  }).catch(()=>({}));
  fs.writeFileSync(path.join(OUT,'data',`${slug(label)}_dom.json`), JSON.stringify(info,null,2));
  return info;
}

async function clickText(page, text, opts={}) {
  const exact = opts.exact !== false;
  const candidates = [
    page.getByText(text,{exact}).filter({visible:true}),
    page.getByRole('tab',{name:text,exact}),
    page.getByRole('button',{name:text,exact}),
    page.getByRole('link',{name:text,exact})
  ];
  for (const loc of candidates) {
    try {
      if (await loc.count()) {
        const el=loc.first();
        if (await el.isVisible()) { await el.click({timeout:5000}); await settle(page); return true; }
      }
    } catch {}
  }
  return false;
}

async function login(page) {
  await page.goto(`${BASE}/Login`, {waitUntil:'domcontentloaded', timeout:30000}).catch(async()=>{
    await page.goto(BASE, {waitUntil:'domcontentloaded', timeout:30000});
  });
  await settle(page);
  await fullCapture(page,'登录前');
  const user = process.env.HSK_USER || '';
  const pass = process.env.HSK_PASS || '';
  if (!user || !pass) throw new Error('Missing HSK credentials in runtime environment');
  const passLoc = page.locator('input[type=password]').filter({visible:true}).first();
  if (!(await passLoc.count())) {
    const body=await page.locator('body').innerText().catch(()=> '');
    if (!/登录|login/i.test(body)) {
      record('login','Already appears authenticated or public home');
      return;
    }
  }
  let userLoc = page.locator('input[type=email]').filter({visible:true}).first();
  if (!(await userLoc.count())) userLoc = page.locator('input[name*=user i],input[name*=mail i],input[placeholder*=账号],input[placeholder*=邮箱],input[type=text]').filter({visible:true}).first();
  if (await userLoc.count()) await userLoc.fill(user);
  if (await passLoc.count()) await passLoc.fill(pass);
  let clicked=false;
  for (const re of [/登录/,/登\s*录/,/login/i,/sign in/i]) {
    const b=page.getByRole('button',{name:re}).filter({visible:true});
    if (await b.count()) { await b.first().click(); clicked=true; break; }
  }
  if (!clicked) {
    const submit=page.locator('button[type=submit],input[type=submit]').filter({visible:true}).first();
    if(await submit.count()){await submit.click(); clicked=true;}
  }
  await settle(page,1800);
  await fullCapture(page,'登录后首页');
  const pwStill = await page.locator('input[type=password]').filter({visible:true}).count();
  const body = await page.locator('body').innerText().catch(()=> '');
  if (pwStill && /登录/.test(body)) throw new Error('Login appears to have failed; login form still visible.');
  record('login',{url:page.url(),title:await page.title()});
}

async function navCapture(page, label) {
  if (await clickText(page,label)) {
    await fullCapture(page, label);
    return true;
  }
  return false;
}

async function captureStatistics(page) {
  if (!(await clickText(page,'统计'))) return;
  await fullCapture(page,'统计_入口');
  const tabs=['概况','国家和地区','作文题目','错误汇总','错误详情','分类统计'];
  for (const t of tabs) {
    if(await clickText(page,t)) {
      await fullCapture(page,`统计_${t}`);
      const sub=await visibleTexts(page,'[role=tab],.el-tabs__item,.ant-tabs-tab,button');
      for (const s of sub.filter(x=>x && x!==t && x.length<18).slice(0,12)) {
        if(/字分布|词分布|国籍|地区|类型|等级|统计|错误/.test(s)) {
          if(await clickText(page,s)) await fullCapture(page,`统计_${t}_${s}`);
        }
      }
    }
  }
}

const generalQueries=['把','被','了','给','是'];
const sentenceQueries=[
  '我昨天在北京买了一本汉语词典。',
  '他把作业写完了以后就去休息了。',
  '这件事情给我带来了很大的帮助。',
  '如果明天下雨，我们就不去公园了。',
  '虽然汉语很难，但是我越来越喜欢学习汉语。'
];

async function findPrimaryQueryInput(page) {
  const locs=[
    page.locator('textarea').filter({visible:true}),
    page.locator('input[type=search]').filter({visible:true}),
    page.locator('input[placeholder*=检索],input[placeholder*=搜索],input[placeholder*=输入],input[placeholder*=关键词],input[type=text]').filter({visible:true})
  ];
  for(const l of locs){ if(await l.count()) return l.first(); }
  return null;
}
async function clickSearchButton(page) {
  for(const re of [/检索/,/搜索/,/查询/,/分析/,/提交/,/开始/]){
    const b=page.getByRole('button',{name:re}).filter({visible:true});
    if(await b.count()){await b.first().click(); return true;}
  }
  const b=page.locator('button[type=submit]').filter({visible:true}).first();
  if(await b.count()){await b.click(); return true;}
  return false;
}

async function saveDownloads(page, label) {
  const btns=page.getByText(/下载/).filter({visible:true});
  if(!await btns.count()) return;
  for(let i=0;i<Math.min(2,await btns.count());i++){
    try{
      const dlP=page.waitForEvent('download',{timeout:5000});
      await btns.nth(i).click();
      const dl=await dlP;
      const name=slug(label)+'_'+slug(dl.suggestedFilename());
      await dl.saveAs(path.join(OUT,'downloads',name));
      record('download',{label,file:name});
    }catch{}
  }
}

async function captureResultDetails(page, prefix, max=2) {
  const links=page.locator('main a, .content a, table a, .el-table a, [class*=result] a').filter({visible:true});
  const count=Math.min(max,await links.count());
  for(let i=0;i<count;i++){
    try{
      const txt=((await links.nth(i).innerText())||`结果${i+1}`).trim();
      if(/首页|检索|统计|工具|帮助|退出|下载/.test(txt)) continue;
      const before=page.url();
      await links.nth(i).click({timeout:4000});
      await settle(page);
      if(page.url()!==before || (await page.locator('body').innerText()).length>100){
        await fullCapture(page,`${prefix}_详情_${i+1}_${txt}`);
        await page.goBack({waitUntil:'domcontentloaded',timeout:8000}).catch(()=>{}); await settle(page);
      }
    }catch{}
  }
}

async function captureSearch(page) {
  if (!(await clickText(page,'检索'))) return;
  await fullCapture(page,'检索_入口');
  const info=await inspectPage(page,'检索_入口');
  const candidateTabs=[...new Set((info.buttons||[]).filter(t=>/检索|查询|搜索|词|句|篇|搭配|条件|离合|句式|语法/.test(t) && t.length<=24))];
  if(!candidateTabs.length) candidateTabs.push('默认检索');
  const tested=[];
  for(const tab of candidateTabs.slice(0,12)){
    if(tab!=='默认检索') await clickText(page,tab).catch(()=>false);
    await fullCapture(page,`检索项_${tab}`);
    const input=await findPrimaryQueryInput(page);
    if(!input){record('search-skip',{label:tab,reason:'no visible text query input'});continue;}
    for(let i=0;i<5;i++){
      const q=generalQueries[i];
      try{
        await input.fill(q);
        const ok=await clickSearchButton(page);
        if(!ok){await input.press('Enter').catch(()=>{});}
        await settle(page,1200);
        const cap=await fullCapture(page,`检索_${tab}_${i+1}_${q}`,{query:q,searchItem:tab});
        const rows=await page.locator('table tbody tr,.el-table__row,[class*=result-item],[class*=list-item]').filter({visible:true}).count().catch(()=>0);
        record('search',{label:tab,query:q,rows,url:page.url()});
        await saveDownloads(page,`检索_${tab}_${i+1}_${q}`);
        if(i===0) await captureResultDetails(page,`检索_${tab}_${q}`,2);
        tested.push({tab,q,rows,url:page.url(),png:cap.png});
      }catch(e){record('search-error',{label:tab,query:q,error:String(e)});}
    }
  }
  fs.writeFileSync(path.join(OUT,'data','search_cases.json'),JSON.stringify(tested,null,2));
}

async function captureTools(page) {
  if (!(await clickText(page,'工具'))) return;
  await fullCapture(page,'工具_入口');
  const info=await inspectPage(page,'工具_入口');
  const known=['依存句法分析','句法关系检索','分词工具','AI问答'];
  const discovered=[...(info.buttons||[]),...(info.links||[]).map(x=>x.text)].filter(t=>t&&/句法|依存|分词|AI|问答|工具|分析/.test(t)&&t.length<25);
  const tools=[...new Set([...known,...discovered])];
  for(const tool of tools.slice(0,12)){
    if(!(await clickText(page,tool))) continue;
    await fullCapture(page,`工具_${tool}`);
    const input=await findPrimaryQueryInput(page);
    if(!input) continue;
    const qs=/问答|AI/i.test(tool)?[
      '如何检索“把”字句？',
      '如何按国家和地区统计作文？',
      '语料库目前有多少篇作文？',
      '怎样下载检索结果？',
      'HSK动态作文语料库适合研究哪些问题？'
    ]:sentenceQueries;
    for(let i=0;i<5;i++){
      try{
        await input.fill(qs[i]);
        const ok=await clickSearchButton(page);
        if(!ok) await input.press('Enter').catch(()=>{});
        await settle(page,1600);
        await fullCapture(page,`工具_${tool}_${i+1}`,{query:qs[i],tool});
        record('tool-case',{label:tool,query:qs[i],url:page.url()});
      }catch(e){record('tool-error',{label:tool,query:qs[i],error:String(e)});}
    }
  }
}

async function captureHelp(page) {
  if(!(await clickText(page,'帮助'))) return;
  await fullCapture(page,'帮助_入口');
  const info=await inspectPage(page,'帮助_入口');
  const candidates=[...(info.links||[]).map(x=>x.text),...(info.buttons||[])].filter(t=>t&&t.length<40&&!/首页|检索|统计|工具|退出/.test(t));
  let n=0;
  for(const t of [...new Set(candidates)]){
    if(n>=15) break;
    try{
      if(await clickText(page,t)) {await fullCapture(page,`帮助_${t}`);n++;}
    }catch{}
  }
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({
    viewport:{width:1600,height:1000},
    acceptDownloads:true,
    locale:'zh-CN',
    userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36'
  });
  const page=await context.newPage();
  page.on('console',m=>{ if(['error','warning'].includes(m.type())) record('browser-console',{label:m.type(),text:m.text().slice(0,1000)}); });
  page.on('pageerror',e=>record('pageerror',{error:String(e)}));
  try{
    await login(page);
    await inspectPage(page,'登录后首页');
    await navCapture(page,'首页');
    await captureSearch(page);
    await captureStatistics(page);
    await captureTools(page);
    await captureHelp(page);
    // Return home and capture any version-description links/cards.
    await clickText(page,'首页').catch(()=>false); await settle(page);
    const homeInfo=await inspectPage(page,'首页_最终');
    for(const text of [...new Set([...(homeInfo.links||[]).map(x=>x.text),...(homeInfo.buttons||[])])].filter(t=>/说明|2\.0|3\.0|版本/.test(t)).slice(0,10)){
      if(await clickText(page,text)) await fullCapture(page,`首页_${text}`);
    }
  } catch(e) {
    record('fatal',{error:String(e),stack:e&&e.stack?e.stack:''});
    await fullCapture(page,'发生错误时页面').catch(()=>{});
    process.exitCode=2;
  } finally {
    const summary={generated_at:now(),base:BASE,screenshot_count:shotNo,operations:ops.length,final_url:page.url()};
    fs.writeFileSync(path.join(OUT,'data','summary.json'),JSON.stringify(summary,null,2));
    fs.writeFileSync(path.join(OUT,'README.txt'),`HSK动态作文语料库自动遍历结果\n生成时间: ${summary.generated_at}\n截图数量: ${shotNo}\n操作记录: data/operations.jsonl\n结构化摘要: data/summary.json\n`);
    await context.close().catch(()=>{}); await browser.close().catch(()=>{});
  }
})();
