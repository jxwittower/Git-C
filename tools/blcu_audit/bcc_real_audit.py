import json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('bcc_real_output'); OUT.mkdir(exist_ok=True); (OUT/'shots').mkdir(exist_ok=True); (OUT/'states').mkdir(exist_ok=True)
BASE='https://bcc.blcu.edu.cn/'
TESTS={
 '多领域':['人工智能','高大的n','洗*澡','(v)一(v){$1=$2}','是*的w'],
 '新闻':['人工智能','n改革{pos=标题}','n改革{pos=正文}','把*v过来','打击NP-OBJ[*犯罪]'],
 '文学':['爱情','高大的n','(v)一(v){$1=$2}','把*v过来','喜欢(n){print($1)}'],
 '口语':['我觉得','真的','v得很','喜欢n','洗*澡'],
 '近代汉语':['革命','民主','女子','教育','国家'],
 '古汉语':['天下','君子','仁','礼','道']
}

def safe(s): return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+','_',s)[:80]
def text(page):
 try:return page.locator('body').inner_text(timeout=8000)
 except:return ''
def shot(page,name,full=False):
 p=OUT/'shots'/f'{name}.png'
 try: page.screenshot(path=str(p),full_page=full,timeout=30000)
 except: page.screenshot(path=str(p),full_page=False,timeout=15000)
 return str(p)
def state(page,name):
 d={'name':name,'url':page.url,'title':page.title(),'text':text(page)[:50000]}
 d['inputs']=[]
 for i in range(min(page.locator('input,textarea').count(),60)):
  e=page.locator('input,textarea').nth(i)
  try: val=e.input_value() if e.is_editable() else (e.get_attribute('value') or '')
  except: val=e.get_attribute('value') or ''
  d['inputs'].append({'i':i,'placeholder':e.get_attribute('placeholder') or '', 'value':val, 'type':e.get_attribute('type') or '', 'class':e.get_attribute('class') or ''})
 d['buttons']=[]
 for i in range(min(page.locator('button,[role=button]').count(),100)):
  e=page.locator('button,[role=button]').nth(i)
  try:t=e.inner_text(timeout=500).strip()
  except:t=''
  d['buttons'].append({'i':i,'text':t,'class':e.get_attribute('class') or ''})
 (OUT/'states'/f'{name}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'states'/f'{name}.txt').write_text(d['text'],encoding='utf-8')
 return d

def load_home(page,channel):
 page.goto(BASE,wait_until='domcontentloaded',timeout=35000); page.wait_for_timeout(1400)
 if channel!='多领域':
  loc=page.get_by_text(channel,exact=True)
  if loc.count(): loc.first.click(); page.wait_for_timeout(900)

def run_query(page,channel,q,idx):
 rec={'channel':channel,'query':q,'ok':False}
 try:
  load_home(page,channel)
  inp=page.locator('input[placeholder*="BCC检索式"]').first
  inp.fill(q)
  rec['pre_url']=page.url
  rec['input_screenshot']=shot(page,f'{idx:02d}_{safe(channel)}_{safe(q)}_input',False)
  page.locator('button.search-btn').first.click()
  try: page.wait_for_load_state('domcontentloaded',timeout=8000)
  except: pass
  page.wait_for_timeout(3200)
  rec['url']=page.url; rec['title']=page.title(); rec['text']=text(page)[:35000]
  rec['ok']=True
  rec['result_screenshot']=shot(page,f'{idx:02d}_{safe(channel)}_{safe(q)}_result',True)
  (OUT/'states'/f'{idx:02d}_{safe(channel)}_{safe(q)}.html').write_text(page.content(),encoding='utf-8')
  (OUT/'states'/f'{idx:02d}_{safe(channel)}_{safe(q)}.txt').write_text(rec['text'],encoding='utf-8')
  rec['controls']=state(page,f'{idx:02d}_{safe(channel)}_{safe(q)}_state').get('buttons',[])
 except Exception as e:
  rec['error']=repr(e); rec['url']=page.url
  try: rec['error_screenshot']=shot(page,f'{idx:02d}_{safe(channel)}_{safe(q)}_ERROR',False)
  except: pass
 return rec

def click_feature(page,label,name):
 candidates=page.get_by_text(label,exact=False)
 for i in range(min(candidates.count(),20)):
  e=candidates.nth(i)
  try:
   if e.is_visible():
    e.click(timeout=3000); page.wait_for_timeout(1800)
    return {'label':label,'ok':True,'url':page.url,'screenshot':shot(page,name,True),'text':text(page)[:20000]}
  except: continue
 return {'label':label,'ok':False}

def feature_probe(page):
 feats=[]
 try:
  for label in ['整句','统计','实例统计','二次筛选','筛选','历时','下载','出处']:
   load_home(page,'新闻'); page.locator('input[placeholder*="BCC检索式"]').first.fill('人工智能'); page.locator('button.search-btn').first.click(); page.wait_for_timeout(2600)
   if label=='整句': shot(page,'90_feature_base_result',True)
   feats.append(click_feature(page,label,f'91_feature_{safe(label)}'))
 except Exception as e: feats.append({'fatal':repr(e)})
 return feats

def capture_static(page):
 pages=[('00_home',BASE),('80_help',BASE+'help.html'),('81_download',BASE+'download'),('82_langsc',BASE+'LangSC.html'),('83_personal_bcc',BASE+'build-corpus.html')]
 out=[]
 for name,u in pages:
  try:
   page.goto(u,wait_until='domcontentloaded',timeout=35000); page.wait_for_timeout(1800)
   out.append({'name':name,'url':page.url,'title':page.title(),'screenshot':shot(page,name,True),'state':state(page,name)})
  except Exception as e: out.append({'name':name,'url':u,'error':repr(e)})
 return out

def find_chrome():
 for p in ['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser']:
  if Path(p).exists(): return p
 return None

def main():
 log={'static':[],'queries':[],'features':[]}
 with sync_playwright() as p:
  chrome=find_chrome(); print('chrome=',chrome)
  browser=p.chromium.launch(headless=True,executable_path=chrome,args=['--no-sandbox','--disable-dev-shm-usage']) if chrome else p.chromium.launch(headless=True)
  ctx=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN',accept_downloads=True)
  page=ctx.new_page(); log['static']=capture_static(page)
  idx=1
  for channel,qs in TESTS.items():
   for q in qs: log['queries'].append(run_query(page,channel,q,idx)); idx+=1
  log['features']=feature_probe(page); browser.close()
 (OUT/'audit.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'queries.tsv').open('w',encoding='utf-8') as f:
  f.write('channel\tquery\tok\turl\tresult_screenshot\terror\n')
  for r in log['queries']:
   f.write('\t'.join([r.get('channel',''),r.get('query',''),str(r.get('ok')),r.get('url',''),r.get('result_screenshot',''),r.get('error','').replace('\t',' ')])+'\n')

if __name__=='__main__': main()
