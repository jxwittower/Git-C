import json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('blcu_public_interactions'); OUT.mkdir(exist_ok=True); (OUT/'shots').mkdir(exist_ok=True); (OUT/'text').mkdir(exist_ok=True)

def safe(s): return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+','_',s)[:100]
def bt(p):
 try:return p.locator('body').inner_text(timeout=5000)
 except:return ''
def snap(p,name):
 path=OUT/'shots'/f'{name}.png'
 try:p.screenshot(path=str(path),full_page=True,timeout=30000)
 except:
  try:p.screenshot(path=str(path),full_page=False,timeout=10000)
  except:return ''
 return str(path)
def record(p,name,action,status='ok',error=''):
 d={'name':name,'action':action,'status':status,'url':p.url,'title':p.title(),'text':bt(p)[:30000],'screenshot':snap(p,name),'error':error}
 (OUT/'text'/f'{name}.txt').write_text(d['text'],encoding='utf-8')
 return d

def click_text(p,label,name,wait=1600):
 loc=p.get_by_text(label,exact=False)
 for i in range(min(loc.count(),30)):
  e=loc.nth(i)
  try:
   if e.is_visible():
    e.click(timeout=4000); p.wait_for_timeout(wait); return record(p,name,'click '+label)
  except:pass
 return record(p,name,'click '+label,'not_found')

def cnlp(ctx,logs):
 p=ctx.new_page(); p.goto('https://cnlp.blcu.edu.cn/',wait_until='domcontentloaded',timeout=30000); p.wait_for_timeout(2200)
 logs.append(record(p,'01_cnlp_home','open CNLP'))
 for num,label in enumerate(['教师入口','学生入口','视频指南','下载','帮助中心'],2):
  try:
   p.goto('https://cnlp.blcu.edu.cn/',wait_until='domcontentloaded',timeout=30000); p.wait_for_timeout(1500)
   logs.append(click_text(p,label,f'{num:02d}_cnlp_{safe(label)}'))
  except Exception as e: logs.append(record(p,f'{num:02d}_cnlp_{safe(label)}','click '+label,'error',repr(e)))
 # public student experience if visible; do not authenticate
 try:
  p.goto('https://cnlp.blcu.edu.cn/',wait_until='domcontentloaded',timeout=30000); p.wait_for_timeout(1600)
  if p.get_by_text('学生入口',exact=False).count(): click_text(p,'学生入口','20_cnlp_student_tab',800)
  logs.append(click_text(p,'在此处直接体验','21_cnlp_direct_experience',2400))
 except Exception as e: logs.append(record(p,'21_cnlp_direct_experience','public direct experience','error',repr(e)))
 p.close()

def qqk(ctx,logs):
 p=ctx.new_page(); p.goto('https://qqk.blcu.edu.cn/',wait_until='domcontentloaded',timeout=30000); p.wait_for_timeout(2200)
 logs.append(record(p,'30_qqk_login','open QQK'))
 for n,label in [(31,'用户注册'),(32,'注册账户'),(33,'取消')]:
  try:
   if n>31:
    p.goto('https://qqk.blcu.edu.cn/',wait_until='domcontentloaded',timeout=30000);p.wait_for_timeout(1200)
   logs.append(click_text(p,label,f'{n}_qqk_{safe(label)}',1500))
  except Exception as e: logs.append(record(p,f'{n}_qqk_{safe(label)}','click '+label,'error',repr(e)))
 p.close()

def hsk(ctx,logs):
 for n,url in [(40,'http://hsk.blcu.edu.cn/'),(41,'https://hsk.blcu.edu.cn/')]:
  p=ctx.new_page()
  try:
   p.goto(url,wait_until='domcontentloaded',timeout=30000);p.wait_for_timeout(6000);logs.append(record(p,f'{n}_hsk_entry','open '+url))
  except Exception as e: logs.append(record(p,f'{n}_hsk_entry','open '+url,'error',repr(e)))
  p.close()

def misc(ctx,logs):
 targets=[(50,'一带一路展示','https://quanqiu.yuyanziyuan.net/'),(51,'汉语方言系统','https://yuyananquan.cn/'),(52,'疫情防控外语通','http://yuyanziyuan.net:9505/'),(53,'文心词典','https://dictionary.litmind.ink/'),(54,'文心写作','http://iwriter.wenmind.net/')]
 for n,label,url in targets:
  p=ctx.new_page()
  try:p.goto(url,wait_until='domcontentloaded',timeout=22000);p.wait_for_timeout(4000);logs.append(record(p,f'{n}_{safe(label)}','open '+url))
  except Exception as e:logs.append(record(p,f'{n}_{safe(label)}','open '+url,'error',repr(e)))
  p.close()

def main():
 logs=[]
 with sync_playwright() as pw:
  chrome=next((x for x in ['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser'] if Path(x).exists()),None)
  browser=pw.chromium.launch(headless=True,executable_path=chrome,args=['--no-sandbox','--disable-dev-shm-usage']) if chrome else pw.chromium.launch(headless=True)
  ctx=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN')
  cnlp(ctx,logs);qqk(ctx,logs);hsk(ctx,logs);misc(ctx,logs);browser.close()
 (OUT/'interactions.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'interactions.tsv').open('w',encoding='utf-8') as f:
  f.write('name\taction\tstatus\ttitle\turl\tscreenshot\terror\n')
  for r in logs:f.write('\t'.join([r.get('name',''),r.get('action',''),r.get('status',''),r.get('title','').replace('\t',' '),r.get('url',''),r.get('screenshot',''),r.get('error','').replace('\t',' ')])+'\n')

if __name__=='__main__':main()
