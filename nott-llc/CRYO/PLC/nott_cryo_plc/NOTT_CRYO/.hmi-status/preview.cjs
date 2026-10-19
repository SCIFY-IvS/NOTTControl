const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/u0149673/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=path.join(__dirname,'qa');fs.mkdirSync(out,{recursive:true});
const css=fs.readFileSync(path.join(__dirname,'files/Styles/NOTTStatus.css'),'utf8');
const script=fs.readFileSync(path.join(__dirname,'files/JavaScript/NOTTHeaderStatus.js'),'utf8');
function led(file,id,top){
    const content=fs.readFileSync(path.join(__dirname,'files/Pages',file),'utf8');
    const attrs=name=>Object.fromEntries([...content.match(new RegExp('<div\\b[^>]*id="'+name+'"[^>]*>'))[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(m=>[m[1],m[2]]));
    const a=attrs(id),b=attrs(id+'_Label');
    assert(Number(a['data-tchmi-top'])+20<=top,'Indicator fits its top band');
    return '<div class="band" style="height:'+top+'px"><span style="position:absolute;left:20px;top:35px">'+(file.startsWith('Thermal')?'Thermal Box':'')+'</span>'+[a,b].map((v,i)=>'<div class="'+(i?'ledlabel':'led')+'" style="left:'+v['data-tchmi-left']+'px;top:'+v['data-tchmi-top']+'px;width:'+v['data-tchmi-width']+'px;height:20px">'+(v['data-tchmi-text']||'')+'</div>').join('')+'</div>';
}
const html=`<html><head><style>body{margin:0;font:14px Arial;color:#20252b}.surface{width:1280px;transform-origin:top left}.nav{height:110px;display:flex;gap:15px;padding:8px 20px;box-sizing:border-box;background:#e8ebed}.host{width:110px;height:90px}.tchmi-button{width:100px;height:80px;margin:4px 5px;background:#f3f5f6;color:#20252b;box-sizing:border-box;border:1px solid #8f989d;display:flex;align-items:end;justify-content:center;text-align:center;padding:6px}.tchmi-button.down{background:#c5d5df}.band{position:relative;border-bottom:1px solid #ddd}.band>div{position:absolute;box-sizing:border-box}.led{background:#23a347;border:1px solid #526059}.ledlabel{display:flex;align-items:center}${css}</style></head><body><div class="surface"><div class="nav">${['ThermalBox','Events','DetectorPower'].map(n=>'<div class="host" id="Header_NavigationButton_'+n+'"><div class="tchmi-button down"><span class="tchmi-button-template-content-text">'+({ThermalBox:'Thermal Box',Events:'Events',DetectorPower:'Detector Power'}[n])+'</span></div></div>').join('')}</div>${led('ThermalBox.content','ThermalBox_EnabledLed',70)}${led('DetectorPower.content','DetectorPower_EnabledLed',50)}</div><script>
window.subscriptions=[];const controls={};for(const name of ['ThermalBox','Events','DetectorPower']){const id='Header_NavigationButton_'+name,el=document.getElementById(id);controls[name]={getId:()=>id,getElement:()=>({toggleClass:(c,b)=>el.classList.toggle(c,!!b)}),setTooltip:s=>el.title=s};}
const root={getId:()=> 'Header',getChildren:()=>Object.values(controls)};
const TcHmi={Errors:{NONE:0},Controls:{get:()=>root},Functions:{registerFunctionEx(){}},EventProvider:{register:()=>()=>{}},Server:{Events:{Type:{Alarm:1},ConfirmationState:{WaitForConfirmation:2}},subscribeEx:(commands,interval,opts,callback)=>{subscriptions.push({commands,callback});return 1;},unsubscribeEx(){}}};
${script}
TcHmi.Functions.NOTT.NOTTHeaderStatus('Header','Attach');
window.showState=(alarm,active,count)=>{const s=subscriptions[0],names=s.commands.map(c=>c.symbol);s.callback({error:0,response:{commands:[{symbol:names[0],readValue:{bActive:active,bAlarm:alarm}},{symbol:names[1],readValue:{bPowerOn:active,bAlarm:alarm,bFuseOperational:true}},{symbol:names[2],readValue:{bTripped:alarm}},{symbol:names[3],readValue:{nErrorCode:0}},{symbol:'ListEvents',maxEntries:count}]}});document.querySelectorAll('.led').forEach(l=>l.style.background=active?'#23a347':'#a7acaf');};
document.querySelector('.surface').style.transform='scale('+Math.min(1,innerWidth/1280)+')';</script></body></html>`;
const file=path.join(out,'status-preview.html');fs.writeFileSync(file,html);
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
for(const width of [1280,390]){const page=await browser.newPage({viewport:{width,height:Math.ceil(240*width/1280)}});await page.goto(pathToFileURL(file).href);
for(const [name,alarm,active,count]of [['enabled',false,true,0],['alarm',true,true,2],['disabled',false,false,0]]){
await page.evaluate(([a,b,c])=>showState(a,b,c),[alarm,active,count]);
const colors=await page.locator('.host .tchmi-button').evaluateAll(ns=>ns.map(n=>getComputedStyle(n).backgroundColor));
assert.equal(colors[0],alarm?'rgb(179, 39, 45)':active?'rgb(40, 122, 61)':'rgb(197, 213, 223)');
assert.equal(colors[1],count?'rgb(179, 39, 45)':'rgb(197, 213, 223)');
await page.screenshot({path:path.join(out,name+'-'+width+'.png')});
const clipped=await page.locator('.ledlabel,.tchmi-button-template-content-text').evaluateAll(ns=>ns.filter(n=>n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1).length);assert.equal(clipped,0);
}await page.close();}
console.log('PASS: offline Edge desktop/mobile previews; actual header script and CSS tested for enabled/alarm/disabled states including selected buttons; indicator labels fit. Not native TwinCAT rendering.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
