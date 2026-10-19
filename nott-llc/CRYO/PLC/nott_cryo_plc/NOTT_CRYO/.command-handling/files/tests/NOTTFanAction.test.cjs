'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname,'..');
const live = 'C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const read = file => fs.readFileSync(fs.existsSync(path.join(root,file))?path.join(root,file):path.join(live,file),'utf8');
const source = read('JavaScript/NOTTFanAction.js');
const box = 'ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl';
const fan = box+'.fan';
const defaults = {lrMinRunningDutyPct:20,lrMaxDutyPct:100,lrStartDutyPct:100,tStartBoost:2000,tRpmWindow:1000,tStallDelay:5000,nPulsesPerRevolution:2,nPwmFullScale:32767,bInvertPwmOutput:false,bInvertTachInput:false};
const names = {MinDuty:'lrMinRunningDutyPct',MaxDuty:'lrMaxDutyPct',StartDuty:'lrStartDutyPct',BoostTime:'tStartBoost',RpmWindow:'tRpmWindow',StallDelay:'tStallDelay',Pulses:'nPulsesPerRevolution',FullScale:'nPwmFullScale'};
function setup(overrides={}) {
    let action;
    const values=Object.assign({[box+'.ctrl']:{bEnable:false,bStop:false},[box+'.stat']:{bActive:false,bPermitStart:true,bSafetyTrip:false},
        [fan+'.ctrl']:{bAuto:false,bEnable:false,lrManualDutyPct:15},[fan+'.stat']:{bActive:false,lrDutyPct:37},
        [fan+'::stat::bActive']:false,[fan+'.cfg']:{...defaults}},overrides);
    const writes=[],controls={};
    const pane={getId:()=> 'Pane',getParent:()=>null,getChildren:()=>Object.values(controls)};
    function control(id) {return controls[id]={value:0,text:'',state:'Normal',enabled:false,getId:()=>id,getChildren:()=>[],
        getParent:()=>pane,getValue(){return this.value;},setValue(v){this.value=v;},setText(v){this.text=v;},
        setIsEnabled(v){this.enabled=v;},getToggleState(){return this.state;},setToggleState(v){this.state=v;}};}
    Object.keys(names).forEach(n=>control('Test_'+n));
    ['InvertPwm','InvertTach','Apply','Cancel','Feedback','Demand'].forEach(n=>control('Test_'+n));
    controls.Test_Demand.value=42;
    const api={Errors:{NONE:0},Controls:{get:()=>pane},Functions:{registerFunctionEx:(name,namespace,fn)=>{
        assert.equal(name,'NOTTFanAction');assert.equal(namespace,'TcHmi.Functions.NOTT');action=fn;
    }},Symbol:{readEx2(expr,cb){const key=expr.slice(3,-4);queueMicrotask(()=>cb(key in values?{error:0,value:structuredClone(values[key])}:{error:1}));},
        writeEx(expr,value,cb){const key=expr.slice(3,-4);writes.push({key,value:structuredClone(value)});
            if(!api.denyWrites){
                values[key]=structuredClone(value);
                if(key===box+'.ctrl::bStop'){
                    values[box+'.ctrl']={bEnable:false,bStop:false};
                    if(values[box+'.stat'])values[box+'.stat'].bActive=false;
                }
                if(key===box+'.ctrl::bEnable'){
                    const enabled=value===true&&values[box+'.stat']?.bSafetyTrip!==true;
                    values[box+'.ctrl']={bEnable:enabled,bStop:false};
                    if(values[box+'.stat'])values[box+'.stat'].bActive=enabled;
                }
            }
            queueMicrotask(()=>cb(api.denyWrites?{error:0,response:{commands:[{error:1001}]}}:{error:0}));}}};
    vm.runInNewContext(source,{TcHmi:api,WeakMap,WeakSet,Promise,setTimeout,clearTimeout,Number,Object,Error});
    return {values,writes,controls,api,fire(name){action('test',fan,box,name);},async run(name){action('test',fan,box,name);for(let i=0;i<15;i++)await new Promise(r=>setImmediate(r));}};
}
(async()=>{
    let t=setup();await t.run('ThermalEnable');assert.equal(t.writes[0].key,box+'.ctrl::bEnable');assert.equal(t.writes[0].value,true);
    t=setup({[box+'.stat']:{bPermitStart:false,bSafetyTrip:false}});await t.run('ThermalEnable');assert.equal(t.writes[0].key,box+'.ctrl::bEnable');
    t=setup();delete t.values[box+'.stat'];await t.run('ThermalEnable');assert.equal(t.writes[0].key,box+'.ctrl::bEnable');
    t=setup({[box+'.stat']:{bSafetyTrip:true}});await t.run('ThermalEnable');assert.equal(t.writes[0].key,box+'.ctrl::bEnable');
    t=setup();delete t.values[box+'.stat'];await t.run('ThermalDisable');assert.equal(t.writes.length,1);assert.equal(t.writes[0].key,box+'.ctrl::bStop');assert.equal(t.writes[0].value,true);
    t=setup();delete t.controls.Test_Feedback;await t.run('ThermalDisable');assert.equal(t.writes[0].key,box+'.ctrl::bStop');
    t=setup();await t.run('ThermalEnable');assert.match(t.controls.Test_Feedback.text,/PLC confirmed/);await t.run('ThermalDisable');assert.match(t.controls.Test_Feedback.text,/disabled \(PLC confirmed\)/);
    t=setup();delete t.values[box+'.stat'];await t.run('Disable');assert.equal(t.writes[0].key,fan+'.ctrl');assert.equal(t.writes[0].value.bEnable,false);
    t=setup();let release;const reader=t.api.Symbol.readEx2;t.api.Symbol.readEx2=(expr,cb)=>{release=()=>reader(expr,cb);};
    t.fire('Enable');await t.run('Disable');release();await new Promise(r=>setImmediate(r));assert.equal(t.writes.length,1);assert.equal(t.writes[0].key,fan+'.ctrl');
    t=setup();await t.run('Enable');assert.equal(t.writes[0].key,fan+'.ctrl::bEnable');assert(!t.values[box+'.stat'].bActive);
    t=setup({[fan+'.ctrl']:{bAuto:true,bEnable:true,lrManualDutyPct:0}});await t.run('Enable');assert.equal(t.writes.length,0);
    t=setup();await t.run('Auto');assert.equal(t.writes[0].key,fan+'.ctrl');assert.equal(t.writes[0].value.bAuto,true);
    t=setup({[fan+'.ctrl']:{bAuto:true,bEnable:true,lrManualDutyPct:0}});await t.run('Manual');assert.equal(t.writes[0].value.bAuto,false);assert.equal(t.writes[0].value.lrManualDutyPct,37);
    t=setup();await t.run('SetDemand');assert.equal(t.writes[0].key,fan+'.ctrl::lrManualDutyPct');assert.equal(t.writes[0].value,42);
    t=setup({[box+'.stat']:{bSafetyTrip:false,bSensorFaultHold:true}});await t.run('SetDemand');assert.equal(t.writes.length,1);
    for(const trip of [true,undefined])for(const action of ['Enable','Auto','Manual','SetDemand']){
        t=setup({[box+'.stat']:{bSafetyTrip:trip}});await t.run(action);assert.equal(t.writes.length,0);
    }
    t=setup();t.controls.Test_Demand.value=NaN;await t.run('SetDemand');assert.equal(t.writes.length,0);
    t=setup();await t.run('ResetSafety');assert.equal(t.writes[0].key,box+'.ctrl::bResetSafety');
    t=setup();await t.run('ConfirmAlarms');assert.equal(t.writes[0].key,box+'.ctrl::bConfirmAlarms');
    t=setup();await t.run('Refresh');assert.equal(t.controls.Test_Demand.value,15);
    t=setup({[box+'.stat']:{bActive:true,bSafetyTrip:false}});await t.run('Load');assert(t.controls.Test_Apply.enabled);
    t.controls.Test_MinDuty.value=25;await t.run('Apply');assert.equal(t.writes[0].key,fan+'.cfg');assert.equal(t.writes[0].value.lrMinRunningDutyPct,25);
    t=setup();await t.run('Load');t.values[fan+'::stat::bActive']=true;await t.run('Apply');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.controls.Test_MinDuty.value=80;t.controls.Test_MaxDuty.value=50;await t.run('Apply');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.values[fan+'.cfg'].lrMinRunningDutyPct=30;await t.run('Apply');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.api.denyWrites=true;await t.run('Apply');assert.match(t.controls.Test_Feedback.text,/denied/);
    const config=JSON.parse(read('Server/TcHmiSrv/TcHmiSrv.Config.default.json'));
    assert.equal(config.SYMBOLS[fan+'.ctrl'].ACCESS,3);
    for(const group of ['Operation','Engineering'])assert.equal(config.USERGROUPS[group].SYMBOLS[fan+'.ctrl'],3);
    assert.equal(config.USERGROUPS.Monitoring.SYMBOLS[fan+'.ctrl'],1);
    for(const [namespace,defs] of Object.entries(config.DEFINITIONS))for(const name of Object.keys(defs))assert(name.startsWith(namespace+'.')||name.startsWith(namespace+'-'));
    const pages=['Pages/ThermalBox.content',...['','Operate','Status','Configuration'].map(n=>'UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplate'+n+'.usercontrol')];
    for(const file of pages){
        const html=read(file);const ids=[...html.matchAll(/<div\s[^>]*\bid="([^"]+)"/g)].map(m=>m[1]);
        assert.equal(ids.length,new Set(ids).size,'Duplicate IDs: '+file);
        for(const script of html.matchAll(/<script\s[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/g))JSON.parse(script[1]);
        if(file.endsWith('.usercontrol'))JSON.parse(read(file+'.json'));
    }
    const operate=read(pages[2]);assert(!operate.includes('Enable thermal box'));assert(!operate.includes('Disable thermal box'));
    assert(read(pages[0]).includes('Enable thermal box'));assert(read(pages[0]).includes('bFanLoopManual'));
    for(const id of ['ThermalBox_Enable','ThermalBox_Disable']){
        const tag=read(pages[0]).match(new RegExp('<div id="'+id+'"[^>]*>'))[0];
        assert(tag.includes('data-tchmi-is-enabled="true"'));
    }
    console.log('PASS: independent fan commands, routine stop/start/reset, fail-closed safety, sensor-hold manual override, fan-only stopped configuration, draft/conflict/access checks, JSON and namespaces.');
})().catch(e=>{console.error(e);process.exitCode=1;});
