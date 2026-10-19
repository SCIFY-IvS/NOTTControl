const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/u0149673/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=path.join(__dirname,'qa');fs.mkdirSync(out,{recursive:true});
function resolve(s){s=s.replaceAll('&quot;','"').replaceAll('&amp;','&').replaceAll('&lt;','<');
const v=body=>{const k=body.split(/::|\./).pop();return k.startsWith('b')?false:k.startsWith('s')?'Operational':k.startsWith('lr')?1.4:12000;};
if(s.startsWith('%f%')){try{return String(new Function('return ('+s.slice(3,-4).replace(/%s%([\s\S]*?)%\/s%/g,(_,b)=>JSON.stringify(v(b)))+');')());}catch{return 'Preview';}}
return s.replace(/%s%([\s\S]*?)%\/s%/g,(_,b)=>String(v(b)));}
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});
try{for(const name of ['DetectorPower','DetectorPowerOverview','DetectorPowerDiagnostics','DetectorPowerConfiguration']){
const source=fs.readFileSync(path.join(__dirname,'files/Pages',name+'.content'),'utf8');let body='';
for(const m of [...source.matchAll(/<div\b([^>]*)>/g)].slice(1)){
const a=Object.fromEntries([...m[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(x=>[x[1],x[2]]));
const type=a['data-tchmi-type'],w=a['data-tchmi-width'],h=a['data-tchmi-height'];
let text=resolve(a['data-tchmi-text']||''),cls='label';
if(type.endsWith('Button'))cls='button';
if(type.endsWith('Input')){cls='input';text=type.endsWith('NumericInput')?'2.5':'Detector power';}
if(type.endsWith('Checkbox'))text='[ ] '+text;
if(type.endsWith('Image'))text='<img src="'+pathToFileURL(path.join(__dirname,'files',a['data-tchmi-src'])).href+'">';
if(type.endsWith('TabNavigation'))text='Overview | Diagnostics | Configuration';
body+=`<div id="${a.id}" class="${cls}" style="left:${a['data-tchmi-left']}px;top:${a['data-tchmi-top']}px;width:${w}px;height:${h}px;font-size:${a['data-tchmi-text-font-size']||14}px">${text}</div>`;
}
const height=name==='DetectorPower'?650:490,file=path.join(out,name+'.html');
fs.writeFileSync(file,`<html><head><style>body{margin:0;font-family:Arial;color:#20252b}.surface{position:relative;width:1280px;height:${height}px;transform-origin:top left}.surface>div{position:absolute;box-sizing:border-box;display:flex;align-items:center;overflow:hidden;overflow-wrap:anywhere}.button{border:1px solid #8e979c;background:#edf0f2;justify-content:center;border-radius:3px}.input{border:1px solid #8e979c;padding:4px}img{width:100%;height:100%;object-fit:contain}</style></head><body><div class="surface">${body}</div><script>document.querySelector('.surface').style.transform='scale('+Math.min(1,innerWidth/1280)+')';</script></body></html>`);
for(const width of [1280,390]){const page=await browser.newPage({viewport:{width,height:Math.ceil(height*width/1280)}});await page.goto(pathToFileURL(file).href);await page.screenshot({path:path.join(out,name+'-'+width+'.png')});
const clipped=await page.locator('.label,.button').evaluateAll(ns=>ns.filter(n=>n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1).map(n=>n.id));if(clipped.length)throw Error('Clipped: '+clipped);await page.close();}
}console.log('PASS: offline layout previews, no clipped text. This is not native TwinCAT rendering.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
