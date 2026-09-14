# paced public query test; no CAPTCHA bypass
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('bcc_windows_single'); OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(channel='msedge', headless=True)
    c=b.new_context(viewport={'width':1600,'height':1000}, ignore_https_errors=True, locale='zh-CN', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0')
    pg=c.new_page(); pg.goto('https://bcc.blcu.edu.cn/', wait_until='domcontentloaded', timeout=45000); pg.wait_for_timeout(7000)
    pg.screenshot(path=str(OUT/'01_home.png'), full_page=True)
    inp=pg.locator('input[placeholder*="BCC检索式"]').first; inp.click(); inp.press_sequentially('人工智能', delay=420); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(OUT/'02_typed.png'), full_page=False)
    pg.locator('button.search-btn').first.click(); pg.wait_for_timeout(15000)
    txt=pg.locator('body').inner_text()[:50000]
    pg.screenshot(path=str(OUT/'03_result.png'), full_page=True)
    (OUT/'result.txt').write_text(txt, encoding='utf-8')
    (OUT/'result.json').write_text(json.dumps({'url':pg.url,'title':pg.title(),'text':txt},ensure_ascii=False,indent=2),encoding='utf-8')
    b.close()
