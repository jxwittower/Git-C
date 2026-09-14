import json, re, time
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

OUT=Path('blcu_portal_output'); OUT.mkdir(exist_ok=True); (OUT/'shots').mkdir(exist_ok=True); (OUT/'text').mkdir(exist_ok=True); (OUT/'html').mkdir(exist_ok=True)
BASE='https://yuyanziyuan.blcu.edu.cn'

PAGES=[
('首页',BASE+'/'),
('中心简介',BASE+'/zxgk/zxjj.htm'),('中心主任',BASE+'/zxgk/zxzr.htm'),('组织架构',BASE+'/zxgk/zzjg.htm'),
('项目首席专家与项目优秀',BASE+'/rcdw/xmsxzj_xmyx_.htm'),('管理团队',BASE+'/rcdw/gltd.htm'),
('重大项目',BASE+'/kxyj/zdxm1.htm'),('学术成果',BASE+'/kxyj/xscg.htm'),('成果转化',BASE+'/kxyj/cgzh.htm'),
('语言资源总览',BASE+'/cgpt/yyzy1.htm'),('应用系统总览',BASE+'/cgpt/yyxt1.htm'),('慕课',BASE+'/cgpt/mk1.htm'),('语言测评',BASE+'/cgpt/yycp.htm'),
('新闻动态',BASE+'/xwgg/xwdt.htm'),('媒体宣传',BASE+'/xwgg/mtxc.htm'),('通知公告',BASE+'/xwgg/tzgg.htm'),('中心通讯',BASE+'/xwgg/zxtx.htm'),
]
RESOURCES=[
('01 世界语言基本信息库','/info/1142/1875.htm'),('02 一带一路国家语言文化核心资源集','/info/1142/1876.htm'),('03 中国周边国家语言资源集','/info/1142/1880.htm'),('04 用于语言识别的世界语言资源集','/info/1142/1878.htm'),('05 海外华语资源库','/info/1142/1879.htm'),('06 俄汉大规模语汇库与句对库','/info/1142/1877.htm'),('07 中阿语言资源集','/info/1142/1881.htm'),('08 中俄日韩英对齐4000词汇库','/info/1142/1882.htm'),('09 汉语方言大数据库资源','/info/1142/1997.htm'),
('10 汉语国际教育优质学习资源','/info/1050/1295.htm'),('11 汉语中介语语音多模态语料库','/info/1050/1296.htm'),('12 全球汉语中介语文本语料库','/info/1050/1297.htm'),('13 用于句法分析的大规模汉语语料库','/info/1050/1298.htm'),('14 中俄经贸合作知识库与双语合同库','/info/1051/1305.htm'),('15 冬奥会多语言术语资源库','/info/1052/1315.htm'),('16 面向冬奥机器翻译的语言资源集','/info/1052/1316.htm'),('17 大规模冬奥项目知识图谱资源集','/info/1052/1317.htm'),('18 中华经典诗词资源集','/info/1053/1325.htm'),('19 汉学研究文献库和人才库','/info/1053/1326.htm'),('20 留学生视频作业选辑','/info/1053/3328.htm'),('21 疫情防控外语通','/info/1162/2005.htm')]
APPS=[
('01 一带一路国家语言文化核心资源展示系统','https://quanqiu.yuyanziyuan.net/',None),
('02 冬奥术语库系统','http://owgt.blcu.edu.cn',BASE+'/info/1052/1315.htm'),
('03 冬奥机器翻译系统',BASE+'/info/1055/1667.htm',BASE+'/info/1052/1316.htm'),
('04 小奥智能问答系统',BASE+'/info/1055/2075.htm',BASE+'/info/1052/1317.htm'),
('05 汉语中介语语料库','https://qqk.blcu.edu.cn/',BASE+'/info/1050/1297.htm'),
('06 HSK动态作文语料库2.0','http://hsk.blcu.edu.cn/',None),
('07 语音纠错系统',BASE+'/info/1055/1670.htm',BASE+'/info/1050/1296.htm'),
('08 汉语语音点查询系统1.0',BASE+'/info/1055/2537.htm',None),
('09 汉语语法点查询系统',BASE+'/info/1055/2538.htm',None),
('10 BCC汉语语料库','https://bcc.blcu.edu.cn/',None),
('11 中俄语商通系统',BASE+'/info/1055/1672.htm',BASE+'/info/1051/1305.htm'),
('12 海外华语资源系统',BASE+'/info/1055/1673.htm',BASE+'/info/1142/1879.htm'),
('13 汉语方言大数据采集与应用系统','https://yuyananquan.cn/',BASE+'/info/1142/1997.htm'),
('14 疫情防控外语通在线查询系统','http://yuyanziyuan.net:9505/',BASE+'/info/1162/2005.htm'),
('15 文心词典','https://dictionary.litmind.ink/',None),
('16 文心写作','http://iwriter.wenmind.net/',None),
]
EXTRA=[
('BCC帮助','https://bcc.blcu.edu.cn/help.html'),('BCC下载中心','https://bcc.blcu.edu.cn/download'),('BCC语言结构计算','https://bcc.blcu.edu.cn/LangSC.html'),('BCC构建个人语料库','https://bcc.blcu.edu.cn/build-corpus.html'),('国际中文智慧教学系统','https://cnlp.blcu.edu.cn/'),
]

def safe(s): return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+','_',s)[:110]

def body_text(page):
 try:return page.locator('body').inner_text(timeout=6000)
 except:return ''

def screenshot(page,path,full=True):
 try: page.screenshot(path=str(path),full_page=full,timeout=30000); return True
 except Exception:
  try: page.screenshot(path=str(path),full_page=False,timeout=12000); return True
  except: return False

def inventory(page):
 d={'inputs':[],'buttons':[],'links':[]}
 loc=page.locator('input,textarea,select')
 for i in range(min(loc.count(),100)):
  e=loc.nth(i); d['inputs'].append({'i':i,'tag':e.evaluate('(e)=>e.tagName'),'type':e.get_attribute('type') or '','id':e.get_attribute('id') or '','name':e.get_attribute('name') or '','placeholder':e.get_attribute('placeholder') or '','aria_label':e.get_attribute('aria-label') or ''})
 loc=page.locator('button,[role=button],input[type=button],input[type=submit]')
 for i in range(min(loc.count(),100)):
  e=loc.nth(i)
  try:t=(e.inner_text(timeout=500) or e.get_attribute('value') or '').strip()
  except:t=e.get_attribute('value') or ''
  d['buttons'].append({'i':i,'text':t,'id':e.get_attribute('id') or '','class':e.get_attribute('class') or ''})
 loc=page.locator('a')
 for i in range(min(loc.count(),500)):
  e=loc.nth(i); href=e.get_attribute('href') or ''
  if not href:continue
  try:t=e.inner_text(timeout=400).strip()
  except:t=''
  d['links'].append({'i':i,'text':t,'href':href})
 return d

def visit(ctx,label,url,idx,kind):
 p=ctx.new_page(); rec={'idx':idx,'kind':kind,'label':label,'requested_url':url,'ok':False}
 try:
  p.goto(url,wait_until='domcontentloaded',timeout=22000); p.wait_for_timeout(1800)
  rec['url']=p.url; rec['title']=p.title(); rec['text']=body_text(p)[:50000]; rec['ok']=True
  rec.update(inventory(p))
  name=f'{idx:03d}_{safe(kind)}_{safe(label)}'
  rec['screenshot']=str(OUT/'shots'/f'{name}.png'); screenshot(p,OUT/'shots'/f'{name}.png',True)
  (OUT/'text'/f'{name}.txt').write_text(rec['text'],encoding='utf-8')
  (OUT/'html'/f'{name}.html').write_text(p.content(),encoding='utf-8')
 except Exception as e:
  rec['error']=repr(e); rec['url']=p.url
  try:
   rec['title']=p.title(); rec['text']=body_text(p)[:15000]
   name=f'{idx:03d}_{safe(kind)}_{safe(label)}_ERROR'; rec['screenshot']=str(OUT/'shots'/f'{name}.png'); screenshot(p,OUT/'shots'/f'{name}.png',False)
  except: pass
 finally:p.close()
 return rec

def main():
 records=[]; idx=1
 with sync_playwright() as pw:
  chrome=None
  for x in ['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser']:
   if Path(x).exists():chrome=x;break
  browser=pw.chromium.launch(headless=True,executable_path=chrome,args=['--no-sandbox','--disable-dev-shm-usage']) if chrome else pw.chromium.launch(headless=True)
  ctx=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN')
  for label,url in PAGES: records.append(visit(ctx,label,url,idx,'portal')); idx+=1
  for label,rel in RESOURCES: records.append(visit(ctx,label,urljoin(BASE,rel),idx,'resource')); idx+=1
  for label,url,fallback in APPS:
   records.append(visit(ctx,label,url,idx,'application')); idx+=1
   if fallback and fallback!=url:
    records.append(visit(ctx,label+' 官方成果说明',fallback,idx,'application_fallback')); idx+=1
  for label,url in EXTRA: records.append(visit(ctx,label,url,idx,'extra')); idx+=1
  browser.close()
 (OUT/'traversal.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'traversal.tsv').open('w',encoding='utf-8') as f:
  f.write('idx\tkind\tlabel\tok\ttitle\turl\tinputs\tbuttons\tscreenshot\terror\n')
  for r in records:
   f.write('\t'.join(map(str,[r.get('idx'),r.get('kind'),r.get('label'),r.get('ok'),r.get('title','').replace('\t',' '),r.get('url',r.get('requested_url','')),len(r.get('inputs',[])),len(r.get('buttons',[])),r.get('screenshot',''),r.get('error','').replace('\t',' ')]))+'\n')

if __name__=='__main__': main()
