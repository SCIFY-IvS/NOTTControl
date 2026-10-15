'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'JavaScript/NOTTFanAction.js'), 'utf8');
const fan = 'ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl.fan';
const box = fan.slice(0, -4);
const defaults = {lrMinRunningDutyPct:20,lrMaxDutyPct:100,lrStartDutyPct:100,tStartBoost:2000,tRpmWindow:1000,tStallDelay:5000,nPulsesPerRevolution:2,nPwmFullScale:32767,bInvertPwmOutput:false,bInvertTachInput:false};
const names = {MinDuty:'lrMinRunningDutyPct',MaxDuty:'lrMaxDutyPct',StartDuty:'lrStartDutyPct',BoostTime:'tStartBoost',RpmWindow:'tRpmWindow',StallDelay:'tStallDelay',Pulses:'nPulsesPerRevolution',FullScale:'nPwmFullScale'};
function setup(overrides = {}) {
    let action;
    const values = Object.assign({[box+'.stat']:{bActive:false,bPermitStart:true,bManual:true,bSensorFaultHold:false},[box+'.ctrl']:{lrManualFanPct:15},[box+'.autoCommissioned']:false,[fan+'::stat::bActive']:false,[fan+'.cfg']:{...defaults}}, overrides);
    const writes = [];
    const controls = {};
    function control(id, initial) {
        const c = {value:initial, enabled:false, text:'',state:'Normal',getId:()=>id,getChildren:()=>[],getParent:()=>pane,getValue(){return this.value;},setValue(v){this.value=v;},setText(v){this.text=v;},setIsEnabled(v){this.enabled=v;},getToggleState(){return this.state;},setToggleState(v){this.state=v;}};
        controls[id]=c;
        return c;
    }
    const pane = {getId:()=> 'NOTTFanConfig',getParent:()=>null,getChildren:()=>Object.values(controls)};
    const feedback=control('Test_Feedback','');
    Object.keys(names).forEach(n=>control('Test_'+n,0));
    ['InvertPwm','InvertTach','Apply','Cancel'].forEach(n=>control('Test_'+n,0));
    const demand=control('Test_Demand',42);
    const api={Errors:{NONE:0},Controls:{get:()=>pane},Functions:{registerFunction:(_,fn)=>action=fn},Symbol:{
        readEx2(expr,cb) {
            const key=expr.slice(3,-4);
            queueMicrotask(()=>cb(key in values?{error:0,value:structuredClone(values[key])}:{error:1}));
        },
        writeEx(expr,value,cb) {
            const key=expr.slice(3,-4);
            writes.push({key,value:structuredClone(value)});
            if (!api.denyWrites) values[key]=structuredClone(value);
            queueMicrotask(()=>cb(api.denyWrites?{error:0,response:{commands:[{error:1001}]}}:{error:0}));
        }
    }};
    vm.runInNewContext(source,{TcHmi:api,WeakMap,WeakSet,Promise,setTimeout,clearTimeout,Number,Object,Error});
    async function run(name){action('test',fan,box,name);for(let i=0;i<12;i++)await new Promise(r=>setImmediate(r));}
    return {run,values,writes,controls,feedback,demand,api};
}
(async()=>{
    let t=setup(); await t.run('Enable');assert.equal(t.writes[0].key,box+'.ctrl::bEnable');assert.equal(t.writes[0].value,true);
    t=setup({[box+'.stat']:{bPermitStart:false}});await t.run('Enable');assert.equal(t.writes.length,0);
    t=setup();delete t.values[box+'.stat'];await t.run('Disable');assert.equal(t.writes[0].value,false);
    t=setup();delete t.values[box+'.stat'];await t.run('Enable');assert.equal(t.writes.length,0);
    t=setup();await t.run('Auto');assert.equal(t.writes.length,0);t.values[box+'.autoCommissioned']=true;await t.run('Auto');assert.equal(t.writes[0].value,1);
    t=setup();await t.run('Manual');assert.equal(t.writes[0].value,2);
    t=setup();await t.run('SetDemand');assert.equal(t.writes[0].key,box+'.ctrl::lrManualFanPct');assert.equal(t.writes[0].value,42);
    t=setup();t.values[box+'.stat'].bSensorFaultHold=true;await t.run('SetDemand');assert.equal(t.writes.length,0);
    t=setup();t.demand.value=NaN;await t.run('SetDemand');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');assert.equal(t.controls.Test_Apply.enabled,true);assert.equal(t.writes.length,0);
    t.controls.Test_MinDuty.value=25;await t.run('Apply');assert.equal(t.writes.length,1);assert.equal(t.writes[0].key,fan+'.cfg');assert.equal(t.writes[0].value.lrMinRunningDutyPct,25);assert.match(t.feedback.text,/verified/);
    t=setup();await t.run('Load');t.controls.Test_MinDuty.value=70;t.controls.Test_MaxDuty.value=50;await t.run('Apply');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.controls.Test_Pulses.value=1.5;await t.run('Apply');assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.values[fan+'.cfg'].lrMinRunningDutyPct=25;await t.run('Apply');assert.equal(t.writes.length,0);assert.match(t.feedback.text,/elsewhere/);
    t=setup();await t.run('Load');t.controls.Test_MinDuty.value=35;await t.run('Load');assert.equal(t.controls.Test_MinDuty.value,20);assert.equal(t.writes.length,0);
    t=setup();await t.run('Load');t.values[box+'.stat'].bActive=true;await t.run('Apply');assert.equal(t.writes.length,0);assert.equal(t.controls.Test_Apply.enabled,false);
    t=setup({[fan+'.cfg']:{}});await t.run('Load');assert.equal(t.controls.Test_Apply.enabled,false);
    t=setup();await t.run('Load');t.api.denyWrites=true;await t.run('Apply');assert.match(t.feedback.text,/denied/);assert.equal(t.controls.Test_Apply.enabled,false);
    assert(t.writes.every(w=>!w.key.includes('fan::ctrl')));
    const config=JSON.parse(fs.readFileSync(path.join(root,'Server/TcHmiSrv/TcHmiSrv.Config.default.json'),'utf8'));
    assert.equal(Object.keys(config.DEFINITIONS.ADS['ADS-NOTT_CRYO_PLC.T_NOTT_FAN_CFG'].properties).length,10);
    for(const [namespace,definitions] of Object.entries(config.DEFINITIONS)){
        for(const name of Object.keys(definitions))assert(name.startsWith(namespace+'.')||name.startsWith(namespace+'-'),'Definition outside namespace: '+namespace+'/'+name);
    }
    for(const name of ['ADS-NOTT_CRYO_PLC.NOTT_FAN_BOX_STAT','ADS-NOTT_CRYO_PLC.NOTT_FAN_BOX_CTRL']){
        assert(config.DEFINITIONS.ADS[name],'Missing namespaced fan definition: '+name);
    }
    assert.equal(config.SYMBOLS[fan].ACCESS,1);
    assert.equal(config.USERGROUPS.Operation.SYMBOLS[fan+'.cfg'],1);
    assert.equal(config.USERGROUPS.Engineering.SYMBOLS[fan+'.cfg'],3);
    assert.equal(config.USERGROUPS.Monitoring.SYMBOLS[box+'.ctrl'],1);
    assert.equal(config.USERGROUPS.Operation.SYMBOLS[box+'.ctrl'],3);
    const pages = ['UserControls/Controls/NOTT/Fan/NOTTFanUserControl.usercontrol',...['','Operate','Status','Configuration'].map(n=>'UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplate'+n+'.usercontrol'),'Pages/ThermalBox.content'];
    for(const file of pages){
        const html=fs.readFileSync(path.join(root,file),'utf8');
        const ids=[...html.matchAll(/<div\s[^>]*\bid="([^"]+)"/g)].map(m=>m[1]);
        assert.equal(new Set(ids).size,ids.length,'Duplicate ID in '+file);
        for(const script of html.matchAll(/<script\s[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/g))JSON.parse(script[1]);
        if(file.endsWith('.usercontrol'))JSON.parse(fs.readFileSync(path.join(root,file+'.json'),'utf8'));
    }
    const originalRoot=process.argv[2];
    if(originalRoot){
        const before=fs.readFileSync(path.join(originalRoot,'Pages/ThermalBox.content'),'utf8');
        const after=fs.readFileSync(path.join(root,'Pages/ThermalBox.content'),'utf8');
        for(const match of before.matchAll(/<div\b[^>]*>/g)) assert(after.includes(match[0]),'Existing page element changed');
    }
    console.log('PASS: guarded commands, unavailable symbols, commissioning gate, sensor hold, draft validation, conflict detection, cancel, stopped-only configuration, denied writes, role permissions, JSON, unique IDs, and existing page elements.');
})().catch(error=>{console.error(error);process.exitCode=1;});

