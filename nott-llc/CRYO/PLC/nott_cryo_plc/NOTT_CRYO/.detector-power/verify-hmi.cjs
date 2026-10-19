const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.join(__dirname,'files');
for(const file of ['tchmiconfig.json','Server/Config/TcHmiSrv.Config.json','JavaScript/DetectorPowerAction.function.json']){
    const full=path.join(root,file);if(fs.existsSync(full))JSON.parse(fs.readFileSync(full,'utf8'));
}
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json'),'utf8'));
for(const item of manifest)assert(fs.existsSync(item.stage),item.stage);
const source=fs.readFileSync(path.join(root,'JavaScript/DetectorPowerAction.js'),'utf8');
let writes=[],message='',controls={};
const feedback={getId:()=> 'Test_Feedback',setText:t=>message=t};
const owner={getId:()=> 'Test',getChildren:()=>[feedback,...Object.values(controls)]};
const base='ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power';
const data={};data[base+'.cfg']={lrCurrentTrip_A:2.5,tMeasurementTimeout:5000};
data[base+'.fuseDetectorPower.cfg']={sName:'Detector',nTimeout:10000,bLog:true,bAutoOp:false};
data[base+'.stat']={bPowerOn:false,bFuseOperational:true};data[base+'.fuseDetectorPower.stat']={bLocal:false};
for(const name of ['Limit','StaleTime','Name','FuseTimeout','Log','AutoOp','Local']){
    controls[name]={value:0,getId:()=> 'Test_'+name,getValue(){return this.value;},setValue(v){this.value=v;},getText(){return this.value;},setText(v){this.value=v;},getToggleState(){return this.value;},setToggleState(v){this.value=v;}};
}
const TcHmi={Errors:{NONE:0},Controls:{get:()=>owner},Functions:{registerFunctionEx(){}},Symbol:{
    writeEx(s,v,cb){writes.push({s,v});data[s.slice(3,-4)]=structuredClone(v);cb({error:0});},
    readEx2(s,cb){cb({error:0,value:structuredClone(data[s.slice(3,-4)])});}
}};
vm.runInNewContext(source,{TcHmi,WeakMap,Promise,setTimeout,clearTimeout,Number,JSON,Object,Error});
const act=async a=>{TcHmi.Functions.NOTT.DetectorPowerAction('Test',a);await new Promise(r=>setTimeout(r,5));};
(async()=>{
    assert.equal(writes.length,0);
    for(let n=1;n<=7;n++){await act('Command'+n);assert.equal(writes.at(-1).s,'%s%'+base+'.ctrl%/s%');assert.equal(writes.at(-1).v.nCommand,n);assert.equal(writes.at(-1).v.bExecute,true);}
    await act('ResetTrip');assert.equal(writes.at(-1).v.bExecute,false);assert.equal(writes.at(-1).v.bResetOvercurrent,true);
    await act('LoadConfig');assert.equal(controls.Limit.value,2.5);
    let count=writes.length;controls.Limit.value=0;await act('SaveConfig');assert.equal(writes.length,count);assert.match(message,/Trip limit/);
    controls.Limit.value=2.5;data[base+'.stat'].bPowerOn=true;await act('SaveConfig');assert.equal(writes.length,count);assert.match(message,/power OFF/);
    data[base+'.stat'].bPowerOn=false;await act('SaveConfig');assert.match(message,/verified/);
    controls.Local.value='Active';await act('ApplyLocal');assert.equal(writes.at(-1).s,'%s%'+base+'.fuseDetectorPower.stat.bLocal%/s%');assert.equal(writes.at(-1).v,true);
    for(const name of ['DetectorPower','DetectorPowerOverview','DetectorPowerDiagnostics','DetectorPowerConfiguration']){
        const html=fs.readFileSync(path.join(root,'Pages',name+'.content'),'utf8');
        const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length);
        for(const match of html.matchAll(/<script[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/g))JSON.parse(match[1]);
    }
    console.log('PASS: offline HMI command/reset routing, configuration validation/readback, ownership, unique control IDs and embedded JSON. No live server access.');
})().catch(e=>{console.error(e);process.exitCode=1;});
