import json, os, re, hashlib, time
from pathlib import Path
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

OUT = Path('blcu_audit_output')
OUT.mkdir(exist_ok=True)
(OUT/'pages').mkdir(exist_ok=True)

STARTS = [
    'https://yuyanziyuan.blcu.edu.cn/cgpt/yyzy1.htm',
    'https://yuyanziyuan.blcu.edu.cn/cgpt/yyxt1.htm',
    'https://bcc.blcu.edu.cn/',
    'https://hsk.blcu.edu.cn/'
]

records=[]

def safe_name(s):
    s=re.sub(r'https?://','',s)
    s=re.sub(r'[^0-9A-Za-z\u4e00-\u9fff._-]+','_',s)
    return s[:120] or 'page'

def snap(page, base):
    p=OUT/'pages'/f'{base}.png'
    try:
        page.screenshot(path=str(p), full_page=True, timeout=30000)
    except Exception:
        page.screenshot(path=str(p), full_page=False, timeout=30000)
    return str(p)

def extract(page):
    return page.evaluate("""() => ({
      title: document.title,
      text: document.body ? document.body.innerText : '',
      links: [...document.querySelectorAll('a')].map((a,i)=>({i,text:(a.innerText||a.textContent||'').trim(),href:a.href})).filter(x=>x.href),
      inputs: [...document.querySelectorAll('input,textarea')].map((e,i)=>({i,tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',placeholder:e.placeholder||'',value:e.value||'',outer:e.outerHTML.slice(0,800)})),
      selects: [...document.querySelectorAll('select')].map((e,i)=>({i,name:e.name||'',id:e.id||'',value:e.value||'',options:[...e.options].map(o=>({text:o.text,value:o.value,selected:o.selected}))})),
      buttons: [...document.querySelectorAll('button,input[type=button],input[type=submit],a.btn,[role=button]')].map((e,i)=>({i,text:(e.innerText||e.value||e.textContent||'').trim(),tag:e.tagName,id:e.id||'',name:e.name||'',type:e.type||'',outer:e.outerHTML.slice(0,800)})),
      forms: [...document.querySelectorAll('form')].map((e,i)=>({i,action:e.action,method:e.method,id:e.id||'',name:e.name||'',text:(e.innerText||'').slice(0,1500),outer:e.outerHTML.slice(0,5000)}))
    })""")

def visit(context, url, idx, label='page'):
    page=context.new_page()
    rec={'idx':idx,'requested_url':url,'label':label,'ok':False}
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(1500)
        data=extract(page)
        rec.update(data)
        rec['url']=page.url
        rec['ok']=True
        base=f'{idx:03d}_{safe_name(label)}_{hashlib.md5(page.url.encode()).hexdigest()[:8]}'
        rec['screenshot']=snap(page,base)
        (OUT/'pages'/f'{base}.html').write_text(page.content(),encoding='utf-8')
        (OUT/'pages'/f'{base}.txt').write_text(data.get('text',''),encoding='utf-8')
        (OUT/'pages'/f'{base}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception as e:
        rec['error']=repr(e)
        try:
            rec['url']=page.url
            rec['title']=page.title()
            base=f'{idx:03d}_{safe_name(label)}_ERROR'
            rec['screenshot']=snap(page,base)
        except Exception:
            pass
    finally:
        records.append(rec)
        page.close()
    return rec

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN',user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36')
        idx=1
        seed_records=[]
        for u in STARTS:
            r=visit(context,u,idx,'seed'); idx+=1; seed_records.append(r)

        queue=[]; seen=set(STARTS)
        # Official portal/detail links from resource and application pages
        for r in seed_records[:2]:
            for a in r.get('links',[]):
                href=a.get('href','')
                if not href: continue
                host=urlparse(href).netloc.lower()
                if host.endswith('blcu.edu.cn') and href not in seen:
                    queue.append((href, a.get('text') or 'official_link'))
                    seen.add(href)
        # Keep first-level crawl bounded but comprehensive enough for all listed cards
        for href,label in queue[:120]:
            r=visit(context,href,idx,label); idx+=1
            # Any externally linked application URL from detail page
            if r.get('ok'):
                for a in r.get('links',[]):
                    h=a.get('href','')
                    if not h or h in seen: continue
                    host=urlparse(h).netloc.lower()
                    if host.endswith('blcu.edu.cn') and ('info/' in h or 'cgpt/' in h):
                        continue
                    # external system under BLCU domains or explicit http links mentioned in detail pages
                    if host.endswith('blcu.edu.cn'):
                        seen.add(h)
                        rr=visit(context,h,idx,'external_'+(a.get('text') or host)); idx+=1

        # Write compact catalog
        (OUT/'exploration.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        with (OUT/'catalog.tsv').open('w',encoding='utf-8') as f:
            f.write('idx\tok\ttitle\turl\tinputs\tselects\tbuttons\tscreenshot\terror\n')
            for r in records:
                vals=[r.get('idx'),r.get('ok'),r.get('title','').replace('\t',' '),r.get('url',r.get('requested_url','')),len(r.get('inputs',[])),len(r.get('selects',[])),len(r.get('buttons',[])),r.get('screenshot',''),r.get('error','').replace('\t',' ')]
                f.write('\t'.join(map(str,vals))+'\n')
        browser.close()

if __name__=='__main__':
    main()
