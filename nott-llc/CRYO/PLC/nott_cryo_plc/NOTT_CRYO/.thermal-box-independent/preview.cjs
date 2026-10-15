const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('C:/Users/u0149673/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = path.join(__dirname,'files');
const live = 'C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const out = path.join(__dirname,'qa');fs.mkdirSync(out,{recursive:true});
const mock = {bActive:true,bPermitStart:false,bSafetyTrip:false,bControlSensorsValid:true,bSensorFaultHold:false,
    bAlarm:false,bWarning:true,bFanManual:true,bValveManual:false,bFanLoopManual:false,bValveLoopManual:true,
    tSensorFaultElapsed:0,lrInsideTempK:292.2,lrTargetTempK:291.5,sStatus:'Enabled. Mixed device/PID modes; see individual faceplates.',
    sStartInhibitReason:'',bAuto:false,lrDutyPct:65,lrDemandPct:65,lrSpeedRpm:1400,lrManualDutyPct:65,
    bRunning:true,bStallAlarm:false,bTachMeasurementLimited:true,nPulseCount:54000,q_nPwmCommand:21299,q_bEnable:true,
    sAutoSetpointSource:'Thermal box control'};
function value(s) {
    s=s.replace(/&quot;/g,'"').replace(/&amp;/g,'&');
    const resolve = (_all, body) => JSON.stringify(mock[body.split(/::|\./).pop()] ?? '');
    if(s.startsWith('%f%')) {
        const expr=s.slice(3,-4).replace(/%(?:s|pp)%([\s\S]*?)%\/(?:s|pp)%/g,resolve);
        try{return String(new Function('return ('+expr+');')());}catch{return 'Preview';}
    }
    return s.replace(/%(?:s|pp)%([\s\S]*?)%\/(?:s|pp)%/g,(_all,body)=>String(mock[body.split(/::|\./).pop()]??'290.0'));
}
function render(file,width,height) {
    const html=fs.readFileSync(path.join(root,file),'utf8');
    const nodes=[...html.matchAll(/<div\b([^>]*)>/g)].map(m=>Object.fromEntries([...m[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(x=>[x[1],x[2]])));
    let content='';
    for(const a of nodes.slice(1)){
        const id=a.id,type=a['data-tchmi-type'];
        const x=Number(a['data-tchmi-left']||0),y=Number(a['data-tchmi-top']||0),w=Number(a['data-tchmi-width']||50),h=Number(a['data-tchmi-height']||28);
        const style=`left:${x}px;top:${y}px;width:${w}px;height:${h}px;font-size:${a['data-tchmi-text-font-size']||14}px;`;
        let body=value(a['data-tchmi-text']||'');let klass='label';
        if(type.endsWith('TcHmiButton'))klass='button';
        else if(type.endsWith('TcHmiNumericInput')){klass='input';body='65.0';}
        else if(type.endsWith('TcHmiImage')){klass='image';body='<img src="'+pathToFileURL(path.join(live,a['data-tchmi-src'])).href+'">';}
        else if(type.endsWith('TcHmiLine')){klass='line';body='';}
        else if(type.endsWith('TcHmiUserControlHost')){klass='symbol';body=id.includes('Fan')?'Fan':id.includes('Controller')?'PID':'290.0 K';}
        content+=`<div id="${id}" class="${klass}" style="${style}">${body}</div>`;
    }
    return `<!doctype html><html><head><style>body{margin:0;background:#e7e9ec;font-family:Arial;color:#20252b}.surface{position:relative;width:${width}px;height:${height}px;background:white;transform-origin:top left}.surface>div{position:absolute;box-sizing:border-box;display:flex;align-items:center;overflow:hidden}.label{padding:0 2px}.button{border:1px solid #8d969e;background:#f3f5f6;justify-content:center;border-radius:3px}.input{border:1px solid #969fa6;padding:8px}.symbol{border:1px solid #929ca4;background:#edf5f8;justify-content:center}.image img{width:100%;height:100%;object-fit:contain}.line{border-top:4px solid #699bb3}</style></head><body><div class="surface">${content}</div><script>document.querySelector('.surface').style.transform='scale('+Math.min(1,innerWidth/${width})+')';</script></body></html>`;
}
(async()=>{
    const browser=await chromium.launch({headless:true,channel:'msedge'});
    for(const [name,file,w,h] of [['thermal','Pages/ThermalBox.content',1280,680],['fan','UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateOperate.usercontrol',640,550]]){
        const preview=path.join(out,name+'.html');fs.writeFileSync(preview,render(file,w,h));
        for(const mobile of [false,true]){
            const page=await browser.newPage({viewport:{width:mobile?390:w,height:mobile?Math.ceil(h*390/w):h}});
            await page.goto(pathToFileURL(preview).href);
            await page.screenshot({path:path.join(out,name+(mobile?'-mobile':'-desktop')+'.png')});
            if(!mobile){
                const clipped=await page.locator('.button,.label').evaluateAll(nodes=>nodes.filter(n=>n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1).map(n=>n.id));
                if(clipped.length)throw new Error('Clipped labels: '+clipped.join(', '));
            }
            await page.close();
        }
    }
    await browser.close();
    console.log('PASS: offline desktop/mobile layout previews; no clipped labels/buttons. Native TwinCAT rendering not exercised.');
})().catch(e=>{console.error(e);process.exitCode=1;});
