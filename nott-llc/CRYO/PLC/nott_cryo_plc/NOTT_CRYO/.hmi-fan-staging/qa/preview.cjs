'use strict';
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/u0149673/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const stage=path.resolve(__dirname,'..');
const output=path.join(stage,'qa');
const base=process.argv[2];
const values={'FanObject::stat::lrDutyPct':43.5,'FanObject::stat::lrSpeedRpm':2820,'FanObject::stat::lrDemandPct':43.5,'FanObject::stat::bRunning':true,'FanObject::stat::bActive':true,'FanObject::stat::bStallAlarm':false,'FanObject::stat::bTachMeasurementLimited':true,'FanObject::stat::nPulseCount':48023,'FanObject::stat::sAutoSetpointSource':'Thermal box control','ThermalStatus::bManual':true,'ThermalStatus::bPermitStart':true,'ThermalStatus::bPermitStop':true,'ThermalStatus::bSensorFaultHold':false,'ThermalStatus::bControlSensorsValid':true,'ThermalStatus::bClosingValve':false,'ThermalStatus::bAlarm':false,'ThermalStatus::bWarning':true,'ThermalStatus::tSensorFaultElapsed':0,'ThermalStatus::lrTargetTempK':294.35,'ThermalStatus::lrInsideTempK':295.2,'ThermalStatus::sStatus':'MANUAL. Fan and valve demands set by operator.'};
function evaluate(raw){
    if(!raw)return '';
    let replaced=raw.replace(/%pp%([^%]+)%\/pp%/g,(_,key)=>JSON.stringify(values[key]??'--'));
    if(replaced.startsWith('%f%')){try{return Function('return ('+replaced.slice(3,-4)+')')();}catch{return '--';}}
    if(raw.startsWith('%pp%'))return values[raw.slice(4,-5)]??'--';
    return raw;
}
function make(file){
    let html=fs.readFileSync(path.join(stage,file),'utf8').replace(/<script[\s\S]*?<\/script>/g,'');
    if(file==='Pages/ThermalBox.content'){
        const fan=fs.readFileSync(path.join(stage,'UserControls/Controls/NOTT/Fan/NOTTFanUserControl.usercontrol'),'utf8').replace(/<script[\s\S]*?<\/script>/g,'');
        html=html.replace(/(<div id="ThermalBox_NOTTFan"[^>]*>)(<\/div>)/,'$1'+fan+'$2');
    }
    return html;
}
(async()=>{
    fs.mkdirSync(output,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'msedge'});
    try{
    const page=await browser.newPage({viewport:{width:1280,height:720}});
    for(const [name,file,width,height] of [
        ['thermalbox','Pages/ThermalBox.content',1280,650],
        ['fan-operate','UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateOperate.usercontrol',640,550],
        ['fan-status','UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateStatus.usercontrol',640,550],
        ['fan-configuration','UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateConfiguration.usercontrol',640,550]
    ]){
        await page.setViewportSize({width,height});
        await page.setContent('<style>*{box-sizing:border-box}body{margin:0;font:14px Arial;background:#f5f7f8;color:#26333b}div[data-tchmi-type]{position:absolute}input{font:14px Arial;border:1px solid #98a5ad;border-radius:2px;padding:5px;width:100%;height:100%}button{font:14px Arial;width:100%;height:100%;border:1px solid #8e9ba4;border-radius:2px;background:#e8edf0;color:#26333b}img{width:100%;height:100%;object-fit:contain}.text{display:flex;align-items:center;white-space:normal}</style>'+make(file));
        const rendered=await page.evaluate(({values,stage,base})=>{
            function value(raw){
                if(!raw)return '';
                if(raw.startsWith('%f%')){
                    const src=raw.slice(3,-4).replace(/%pp%([^%]+)%\/pp%/g,(_,k)=>JSON.stringify(values[k]??null));
                    try{return Function('return ('+src+')')();}catch{return '--';}
                }
                if(raw.startsWith('%pp%'))return values[raw.slice(4,-5)]??'--';
                return raw;
            }
            const boxes=[];
            for(const el of document.querySelectorAll('div[data-tchmi-type]')){
                const a=n=>el.getAttribute('data-tchmi-'+n);
                for(const p of ['left','top','width','height'])if(a(p)!==null)el.style[p]=a(p)+'px';
                const type=a('type').split('.').pop();
                if(type==='TcHmiTextblock'){
                    el.classList.add('text');el.textContent=String(value(a('text')));
                    el.style.fontSize=(a('text-font-size')||14)+'px';el.style.fontWeight=a('text-font-weight')||'Normal';
                    if(a('text-horizontal-alignment')==='Center')el.style.justifyContent='center';
                }else if(type==='TcHmiButton'){
                    el.innerHTML='';const b=document.createElement('button');b.textContent=a('text')||'';el.append(b);
                }else if(type==='TcHmiNumericInput'){
                    el.innerHTML='';const input=document.createElement('input');input.type='number';input.value=a('value')||'0';el.append(input);
                }else if(type==='TcHmiCheckbox'){
                    el.innerHTML='';const label=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.style.width='18px';input.style.height='18px';label.append(input,document.createTextNode(' '+(a('text')||'')));el.append(label);
                }else if(type==='TcHmiImage'){
                    const img=document.createElement('img');const src=String(value(a('src')));img.src='file:///'+stage.replace(/\\/g,'/')+'/'+src;el.append(img);
                }else if(type==='TcHmiUserControlHost'&&!el.children.length){
                    el.style.border='1px solid #a6b2b8';el.style.background='#eef1f3';
                    el.textContent=(a('mettempobject')||'').includes('t_thermal_box')?'294.35 K':a('ctrlvalveobject')?'Valve':a('tctrlobject')?'PID':'Vote';
                }else if(type==='TcHmiLine'){el.style.background='#237eaf';if(a('x1')===a('x2')&&a('y1')!==a('y2'))el.style.width=(a('stroke-thickness')||2)+'px';else el.style.height=(a('stroke-thickness')||2)+'px';}
                const rect=el.getBoundingClientRect();
                if(type==='TcHmiTextblock'&&(el.scrollHeight>rect.height+2||el.scrollWidth>rect.width+2))boxes.push({id:el.id,w:rect.width,h:rect.height,scrollW:el.scrollWidth,scrollH:el.scrollHeight});
            }
            return boxes;
        },{values,stage,base});
        // Set local SVG images to data URLs for the isolated static preview.
        const imgs=await page.locator('img').all();
        for(const img of imgs){
            const src=await img.getAttribute('src');
            const local=src.replace('file:///','').replace(/\//g,path.sep);
            if(fs.existsSync(local))await img.evaluate((el,data)=>el.src=data,'data:image/svg+xml;base64,'+fs.readFileSync(local).toString('base64'));
        }
        await page.screenshot({path:path.join(output,name+'.png')});
        if(rendered.length)throw new Error('Text overflow in '+name+': '+JSON.stringify(rendered));
        console.log('Layout OK: '+name);
    }
    }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

