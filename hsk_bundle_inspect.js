const fs=require('fs');
const {execFileSync}=require('child_process');
const https=require('https');
function get(url){return new Promise((resolve,reject)=>{https.get(url,{rejectUnauthorized:false,headers:{'User-Agent':'Mozilla/5.0'}},r=>{let chunks=[];r.on('data',d=>chunks.push(d));r.on('end',()=>resolve(Buffer.concat(chunks).toString('utf8')));}).on('error',reject);});}
(async()=>{
 const base='https://hsk.blcu.edu.cn/'; const names=['main.dart.js','main.dart.js_1.part.js','main.dart.js_2.part.js','main.dart.js_3.part.js'];
 let all='';
 for(const n of names){const s=await get(base+n);console.log('FILE',n,'SIZE',s.length);fs.writeFileSync('/tmp/'+n,s);all+='\n'+s;}
 const endpoints=[...new Set((all.match(/\/api\/[A-Za-z0-9_?=&%{}.,:\/\-]+/g)||[]).map(x=>x.replace(/["'`;)>\]}].*$/,'')))].sort();
 const apiContexts=[]; let pos=0; while((pos=all.indexOf('/api/',pos))>=0&&apiContexts.length<1000){apiContexts.push(all.slice(Math.max(0,pos-350),Math.min(all.length,pos+700)).replace(/\s+/g,' '));pos+=5;}
 const zh=[...new Set((all.match(/[\u3400-\u9fff][\u3400-\u9fffA-Za-z0-9（）()、，。；：？！·—_+\-\s]{1,80}/g)||[]).map(s=>s.replace(/\s+/g,' ').trim()).filter(s=>s.length>=2))];
 const focus=zh.filter(s=>/检索|统计|国家|地区|作文|错误|分类|工具|句法|依存|分词|AI|问答|下载|帮助|标注|偏误|词语|搭配|离合|条件|查询|搜索|语料|原始|全文|用户|登录|题目/.test(s));
 console.log('=== ENDPOINTS ==='); endpoints.slice(0,1000).forEach(x=>console.log(x));
 console.log('=== FOCUSED CHINESE STRINGS ==='); focus.slice(0,1500).forEach(x=>console.log(x));
 console.log('=== API CONTEXTS ==='); apiContexts.slice(0,600).forEach((x,i)=>console.log('CTX',i,x));
 fs.mkdirSync('hsk_bundle_report',{recursive:true});fs.writeFileSync('hsk_bundle_report/endpoints.json',JSON.stringify(endpoints,null,2));fs.writeFileSync('hsk_bundle_report/focused_strings.txt',focus.join('\n'));fs.writeFileSync('hsk_bundle_report/api_contexts.txt',apiContexts.join('\n\n'));
})();
