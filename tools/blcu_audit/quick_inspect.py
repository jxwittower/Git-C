import json
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

def attrs(loc, names):
    d={}
    for n in names:
        try: d[n]=loc.get_attribute(n) or ''
        except: d[n]=''
    return d

def metadata(page):
    data={'title':page.title(),'url':page.url}
    try: data['text']=page.locator('body').inner_text(timeout=5000)[:40000]
    except: data['text']=''
    data['inputs']=[]
    locs=page.locator('input,textarea')
    for i in range(min(locs.count(),200)):
        e=locs.nth(i); row={'i':i,'tag':e.evaluate('(e)=>e.tagName')}
        row.update(attrs(e,['type','name','id','placeholder','value','class','aria-label']))
        data['inputs'].append(row)
    data['selects']=[]
    locs=page.locator('select')
    for i in range(min(locs.count(),100)):
        e=locs.nth(i); row={'i':i}; row.update(attrs(e,['name','id','class','aria-label']))
        try: row['options']=e.locator('option').all_inner_texts()
        except: row['options']=[]
        data['selects'].append(row)
    data['buttons']=[]
    locs=page.locator('button,input[type=submit],input[type=button],[role=button]')
    for i in range(min(locs.count(),200)):
        e=locs.nth(i); row={'i':i}
        try: row['text']=(e.inner_text(timeout=1000) or e.get_attribute('value') or '').strip()
        except: row['text']=e.get_attribute('value') or ''
        row.update(attrs(e,['type','name','id','class','aria-label','title']))
        data['buttons'].append(row)
    data['links']=[]
    locs=page.locator('a')
    for i in range(min(locs.count(),800)):
        e=locs.nth(i)
        try: txt=e.inner_text(timeout=500).strip()
        except: txt=''
        href=e.get_attribute('href') or ''
        if href: data['links'].append({'i':i,'text':txt,'href':href})
    return data

def main():
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={'width':1600,'height':1000},ignore_https_errors=True,locale='zh-CN')
        for idx,(name,url) in enumerate(TARGETS,1):
            page=ctx.new_page(); rec={'name':name,'requested':url,'ok':False}
            try:
                page.goto(url,wait_until='domcontentloaded',timeout=25000); page.wait_for_timeout(2000)
                rec.update(metadata(page)); rec['ok']=True
                page.screenshot(path=str(OUT/'shots'/f'{idx:02d}_{name}.png'),full_page=True,timeout=30000)
                (OUT/f'{name}.html').write_text(page.content(),encoding='utf-8')
            except Exception as e:
                rec['error']=repr(e); rec['url']=page.url
                try:
                    rec['title']=page.title(); rec['text']=page.locator('body').inner_text(timeout=3000)[:15000]
                    page.screenshot(path=str(OUT/'shots'/f'{idx:02d}_{name}_ERROR.png'),full_page=False,timeout=10000)
                except: pass
            results.append(rec); page.close()
        browser.close()
    (OUT/'inspect.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'summary.tsv').open('w',encoding='utf-8') as f:
        f.write('name\tok\ttitle\turl\tinputs\tselects\tbuttons\terror\n')
        for r in results:
            f.write('\t'.join(map(str,[r['name'],r.get('ok'),r.get('title','').replace('\t',' '),r.get('url',r.get('requested')),len(r.get('inputs',[])),len(r.get('selects',[])),len(r.get('buttons',[])),r.get('error','').replace('\t',' ')]))+'\n')

if __name__=='__main__': main()
