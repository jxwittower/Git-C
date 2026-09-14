const { chromium, request } = require('playwright');
const { execSync } = require('child_process');
(async()=>{
 console.log('=== DNS ===');
 try{console.log(execSync('getent hosts hsk.blcu.edu.cn || true',{encoding:'utf8'}))}catch(e){}
 console.log('=== CURL HTTPS ===');
 try{console.log(execSync("curl -vkL --max-time 20 -A 'Mozilla/5.0' https://hsk.blcu.edu.cn/ -o /tmp/hsk.html -D - 2>&1 | tail -100",{encoding:'utf8'}))}catch(e){console.log(String(e.stdout||e))}
 try{console.log('html bytes',require('fs').statSync('/tmp/hsk.html').size);console.log(require('fs').readFileSync('/tmp/hsk.html','utf8').slice(0,3000))}catch(e){console.log('no html',String(e))}
 console.log('=== CURL HTTP ===');
 try{console.log(execSync("curl -vL --max-time 20 -A 'Mozilla/5.0' http://hsk.blcu.edu.cn/ -o /tmp/hskhttp.html -D - 2>&1 | tail -80",{encoding:'utf8'}))}catch(e){console.log(String(e.stdout||e))}
 const browser=await chromium.launch({headless:true}); const p=await browser.newPage();
 p.on('requestfailed',r=>console.log('REQFAIL',r.url(),r.failure()));
 p.on('response',r=>{if(r.url().includes('hsk.blcu.edu.cn'))console.log('RESP',r.status(),r.url(),JSON.stringify(r.headers()).slice(0,1000));});
 p.on('console',m=>console.log('CONSOLE',m.type(),m.text()));
 try{const resp=await p.goto('https://hsk.blcu.edu.cn/',{waitUntil:'networkidle',timeout:30000}); console.log('GOTO',resp&&resp.status(),resp&&resp.headers()); console.log('CONTENTLEN',(await p.content()).length); console.log((await p.content()).slice(0,5000)); console.log('BODYHTML',await p.locator('body').innerHTML().catch(()=>''));}catch(e){console.log('PLAYERR',String(e));}
 await browser.close();
})();
