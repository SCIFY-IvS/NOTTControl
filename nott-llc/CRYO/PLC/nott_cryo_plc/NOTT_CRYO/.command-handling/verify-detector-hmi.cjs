const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('.command-handling/files/JavaScript/DetectorPowerAction.js','utf8');
const base='ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power';
function setup({feedback=true,ack=true,denied=false,refused=false}={}){
    const writes=[],values={};let text='';
    values[base+'.ctrl']={nCommand:0,bExecute:false,bResetOvercurrent:false};
    values[base+'.stat']={nLastCommand:0,sCommandResult:'',bPowerOn:true,bFuseOperational:true};
    values[base+'.fuseDetectorPower.stat']={sState:'OP',sSubstate:'ON'};
    const fb={getId:()=> 'Test_Feedback',setText:t=>text=t};
    const root={getId:()=> 'Test',getType:()=> 'TcHmi.Controls.System.TcHmiContent',getChildren:()=>feedback?[fb]:[],getParent:()=>null};
    const api={Errors:{NONE:0},Controls:{get:()=>root},Functions:{registerFunctionEx(){}},Symbol:{
        writeEx(s,v,cb){writes.push({symbol:s,value:structuredClone(v)});if(denied){cb({error:0,response:{commands:[{error:1001}]}});return;}
            values[s.slice(3,-4)]=structuredClone(v);
            if(ack){values[base+'.ctrl'].bExecute=false;values[base+'.ctrl'].bResetOvercurrent=false;values[base+'.stat'].nLastCommand=v.nCommand;
                values[base+'.stat'].sCommandResult=v.bResetOvercurrent?'Overcurrent reset accepted. Detector remains OFF.':refused?'Fuse rejected request: LOCAL':'Fuse accepted request. Actual state is reported by the fuse.';}
            cb({error:0});},
        readEx2(s,cb){const key=s.slice(3,-4);cb(Object.hasOwn(values,key)?{error:0,value:structuredClone(values[key])}:{error:1});}
    }};
    vm.runInNewContext(source,{TcHmi:api,setTimeout:(fn,ms)=>setTimeout(fn,ms===100?0:ms),clearTimeout,WeakMap,Promise,Number,Object,JSON,Error});
    return{writes,values,get text(){return text;},async run(action){api.Functions.NOTT.DetectorPowerAction('Test',action);for(let i=0;i<80;i++){await new Promise(r=>setTimeout(r,1));if(text!=='Working...')break;}}};
}
(async()=>{
    for(let n=1;n<=7;n++){const t=setup();await t.run('Command'+n);assert.equal(t.writes.length,1);assert.equal(t.writes[0].value.nCommand,n);assert.match(t.text,/Fuse accepted/);assert.match(t.text,/Power feedback: ON/);assert(!t.text.includes('Command requested.'));}
    let t=setup({feedback:false});await t.run('Command7');assert.equal(t.writes.length,1,'No feedback widget must not block OFF');
    t=setup({refused:true});await t.run('Command6');assert.match(t.text,/Fuse rejected request: LOCAL/);
    t=setup({denied:true});await t.run('Command7');assert.match(t.text,/PLC access failed/);
    t=setup({ack:false});await t.run('Command7');assert.match(t.text,/acknowledgement timed out/);
    t=setup();await t.run('ResetTrip');assert.equal(t.writes[0].value.bExecute,false);assert.equal(t.writes[0].value.bResetOvercurrent,true);assert.match(t.text,/reset accepted/);
    t=setup();t.values[base+'.stat'].bFuseOperational=false;await t.run('Command7');assert.match(t.text,/Power feedback: unavailable/);
    console.log('PASS: seven unchanged command numbers, PLC acknowledgements/refusals, unavailable feedback, timeout/access failures, optional feedback control, reset routing, and no claim of physical completion from a successful write.');
})().catch(e=>{console.error(e);process.exitCode=1;});
