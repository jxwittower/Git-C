import json, re, hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('blcu_quick_output'); OUT.mkdir(exist_ok=True); (OUT/'shots').mkdir(exist_ok=True)
TARGETS=[
('portal','https://yuyanziyuan.blcu.edu.cn/'),
('resources','https://yuyanziyuan.blcu.edu.cn/cgpt/yyzy1.htm'),
('applications','https://yuyanziyuan.blcu.edu.cn/cgpt/yyxt1.htm'),
('bcc','https://bcc.blcu.edu.cn/'),
('bcc_help','https://bcc.blcu.edu.cn/help.html'),
('hsk','https://hsk.blcu.edu.cn/'),
('qqk','https://qqk.blcu.edu.cn/'),
('belt_road','https://quanqiu.yuyanziyuan.net/'),
('winter_terms','https://owgt.blcu.edu.cn/'),
('cnlp','https://cnlp.blcu.edu.cn/'),
('dialect','https://yuyananquan.cn/'),
('pandemic','https://yuyanziyuan.net/'),
('dictionary','https://dictionary.litmind.ink/'),
('iwriter','https://iwriter.wenmind.net/'),
('overseas_chinese','https://huayu.jnu.edu.cn/')
]

def metadata(page):
 return page.evaluate("""() => ({
 title:document.title,url:location.href,text:(document.body?.innerText||'').slice(0,30000),
 inputs:[...document.querySelectorAll('input,textarea')].map((e,i)=>({i,tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',placeholder:e.placeholder||'',value:e.value||'',class:e.className||'',outer:e.outerHTML.slice(0,1000)})),
 selects:[...document.querySelectorAll('select')].map((e,i)=>({i,id:e.id||'',name:e.name||'',class:e.className||'',options:[...e.options].map(o=>({text:o.text,value:o.value,selected:o.selected}))})),
 buttons:[...document.querySelectorAll('button,input[type=submit],input[type=button],[role=button]')].map((e,i)=>({i,tag:e.tagName,text:(e.innerText||e.value||e.textContent||'').trim(),id:e.id||'',name:e.name||'',class:e.className||'',type:e.type||'',outer:e.outerHTML.slice(0,1000)})),
 links:[...document.querySelectorAll('a')].map((e,i)=>({i,text:(e.innerText||e.textContent||'').trim(),href:e.href})).filter(x=>x.href).slice(0,500)
}))""")

def main():
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  ctx=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN')
  for idx,(name,url) in enumerate(TARGETS,1):
   page=ctx.new_page(); rec={'name':name,'requested':url,'ok':False}
   try:
    page.goto(url,wait_until='domcontentloaded',timeout=20000); page.wait_for_timeout(2500)
    rec.update(metadata(page)); rec['ok']=True
    page.screenshot(path=str(OUT/'shots'/f'{idx:02d}_{name}.png'),full_page=True,timeout=30000)
    (OUT/f'{name}.html').write_text(page.content(),encoding='utf-8')
   except Exception as e:
    rec['error']=repr(e); rec['url']=page.url
    try: page.screenshot(path=str(OUT/'shots'/f'{idx:02d}_{name}_ERROR.png'),full_page=False,timeout=10000)
    except: pass
   results.append(rec); page.close()
  browser.close()
 (OUT/'inspect.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 with (OUT/'summary.tsv').open('w',encoding='utf-8') as f:
  f.write('name\tok\ttitle\turl\tinputs\tselects\tbuttons\terror\n')
  for r in results:
   f.write('\t'.join(map(str,[r['name'],r.get('ok'),r.get('title',''),r.get('url',r.get('requested')),len(r.get('inputs',[])),len(r.get('selects',[])),len(r.get('buttons',[])),r.get('error','')]))+'\n')

if __name__=='__main__': main()
