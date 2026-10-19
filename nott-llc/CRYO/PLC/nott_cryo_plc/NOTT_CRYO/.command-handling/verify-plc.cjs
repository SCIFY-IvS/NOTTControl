const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('POUs/Devices/Detector_Power/FB_NOTT_DETECTOR_POWER.TcPOU','utf8');
const library='C:/Users/u0149673/met-ics/fcs/LCS/METIS_CTRL/SRC/Fuse/Fuse/Fuse/';
const fuseSource=fs.readFileSync(library+'POUs/FB_FUSE.TcPOU','utf8');
function compile(text,returns){
    let s=text.replace(/\(\*[\s\S]*?\*\)/g,'').replace(/\/\/[^\n]*/g,'').replace(/\^\./g,'.');
    if(returns)s=s.replace(new RegExp('\\b'+returns+'\\s*:=','g'),'return ');
    s=s.replace(/i_nStatus\s+AND\s+UINT#16#([\dA-F]+)/g,'i_nStatus & 0x$1');
    s=s.replace(/T#(\d+)MS/gi,'$1').replace(/T#(\d+)S/gi,(_,n)=>String(Number(n)*1000));
    s=s.replace(/\b(tonStale|tonShutdown|tonValveClose|trigDetectorPower|fuseDetectorPower|M_ScaleInput)\(([^;]*?)\);/g,(_,f,a)=>f+'({'+a.replace(/(\w+)\s*:=/g,'$1:')+'});');
    s=s.replace(/\bELSIF\s+([\s\S]*?)\s+THEN/g,'} else if ($1) {').replace(/\bIF\s+([\s\S]*?)\s+THEN/g,'if ($1) {').replace(/\bELSE\b/g,'} else {').replace(/\bEND_IF\b/g,'}');
    s=s.replace(/\bCASE ([\w.]+) OF/g,'switch($1){').replace(/^\s*(E_FUSE_COMMAND\.\w+):/gm,'break;case $1:').replace(/END_CASE/g,'break;}').replace(/\{\s*break;case/g,'{case');
    s=s.replace(/\bAND\b/g,'&&').replace(/\bOR\b/g,'||').replace(/\bNOT\b/g,'!').replace(/\bTRUE\b/g,'true').replace(/\bFALSE\b/g,'false').replace(/\bRETURN\b/g,'return')
        .replace(/<>/g,'!=').replace(/:=/g,'=').replace(/(?<![<>=!:])=(?!=)/g,'===').replace(/(^|[;{}\n:])\s*([\w.]+)\s*===/g,'$1\n$2 =');
    if(returns==='M_ScaleInput')s=s.replace(/return\s*true;/,'');
    return new Function('ctx','with(ctx){'+s+'}');
}
function implementations(text){return Object.fromEntries([...text.matchAll(/<Method Name="(\w+)"[\s\S]*?<Implementation>\s*<ST><!\[CDATA\[([\s\S]*?)\]\]>/g)].map(m=>[m[1],m[2]]));}
const methods=implementations(source),native=implementations(fuseSource);
const main=compile(source.match(/<Implementation>\s*<ST><!\[CDATA\[([\s\S]*?)\]\]>/)[1]);
const enums={};for(const name of ['COMMAND','STATE','SUBSTATE','RPC_ERROR']){
    const file=fs.readFileSync(library+'DUTs/Enumerated/E_FUSE_'+name+'.TcDUT','utf8');
    let index=-1;const entries={};
    const body=file.match(/\(\s*([\s\S]*?)\);/)[1].replace(/\(\*[\s\S]*?\*\)/g,'').replace(/\/\/[^\n]*/g,'');
    for(const segment of body.split(',')){const m=segment.trim().match(/^(\w+)(?:\s*:=\s*(-?\d+))?$/);if(m){index=m[2]===undefined?index+1:Number(m[2]);entries[m[1]]=index;}}
    enums['E_FUSE_'+name]=entries;
}
function setup(){
    const c={...enums,time:0,cfg:{lrCurrentTrip_A:2.5,tMeasurementTimeout:5000},ctrl:{nCommand:0,bExecute:false,bResetOvercurrent:false},stat:{},
        i_nActCurrent:1400000,i_nStatus:0x8000,i_nMeterState:8,ABS:Math.abs,DINT_TO_LREAL:Number,LREAL_TO_STRING:String,CONCAT:(a,b)=>a+b,ADR:x=>x,
        TC_EVENTS:{NottCryoSysEventClass:{Critical:1,Warning:2,Error:3}},sEventMessage:'',m_nActCurrent:0};
    for(const m of source.split('</Declaration>')[0].matchAll(/^\s*(\w+)(?: AT %I\*)?:\s*(\w+)/gm))if(!(m[1] in c))c[m[1]]=m[2]==='BOOL'?false:0;
    for(const m of fs.readFileSync('DUTs/Structures/DetectorPower/T_NOTT_DETECTOR_POWER_STAT.TcDUT','utf8').matchAll(/^\s*(\w+):\s*(\w+)/gm))c.stat[m[1]]=m[2]==='BOOL'?false:m[2]==='STRING'?'':0;
    function ton(){let start=null;const fn=({IN,PT})=>{if(!IN){start=null;fn.Q=false;}else{if(start===null)start=c.time;fn.Q=c.time-start>=PT;}};return Object.assign(fn,{Q:false});}
    c.tonStale=ton();c.tonShutdown=ton();let previous=false;c.trigDetectorPower=Object.assign(({CLK})=>{c.trigDetectorPower.Q=CLK&&!previous;previous=CLK;},{Q:false});
    for(const n of ['fbTripAlarm','fbMeterAlarm','fbShutdownAlarm'])c[n]={raises:0,clears:0,CreateEx:()=>0,ipArguments:{Clear(){},AddString(){}},Raise(){this.raises++;},Clear(){this.clears++;}};
    const f=Object.assign(function(){
        // Mock physical plant/library activities, not the wrapper or RPC guards.
        const S=enums.E_FUSE_SUBSTATE,C=enums.E_FUSE_COMMAND;
        if(f.ctrl.bExecute){const n=f.ctrl.nCommand;f.ctrl.bExecute=false;f.ctrl.nCommand=0;f.stat.nLastCommand=n;
            if(n===C.INIT&&f.stat.nState===1)f.stat.nSubstate=S.NOTOP_INITIALIZING;
            if(n===C.ENABLE&&[S.NOTOP_READY_ON,S.NOTOP_READY_OFF].includes(f.stat.nSubstate)){f.stat.nState=2;f.stat.nSubstate=f.i_stStatus.bEnabled?S.OP_ON:S.OP_OFF;}
            if(n===C.ON&&f.stat.nSubstate===S.OP_OFF)f.stat.nSubstate=S.OP_SWITCHING_ON;
            if(n===C.OFF&&f.stat.nSubstate===S.OP_ON)f.stat.nSubstate=S.OP_SWITCHING_OFF;
            if(n===C.DISABLE&&[S.OP_ON,S.OP_OFF].includes(f.stat.nSubstate)){f.stat.nState=1;f.stat.nSubstate=f.i_stStatus.bEnabled?S.NOTOP_READY_ON:S.NOTOP_READY_OFF;}
        }
        f.q_bSwitch=[S.OP_SWITCHING_ON,S.OP_SWITCHING_OFF,S.NOTOP_INITIALIZING].includes(f.stat.nSubstate);
        f.q_bReset=!!c.nativeReset;
        if(c.completeActivity&&f.q_bSwitch){f.i_stStatus.bEnabled=f.stat.nSubstate!==S.OP_SWITCHING_OFF;f.stat.nSubstate=f.stat.nState===1?S.NOTOP_READY_ON:f.i_stStatus.bEnabled?S.OP_ON:S.OP_OFF;}
        c.expectedSwitch=f.q_bSwitch;c.expectedReset=f.q_bReset;
    },{...enums,ctrl:{nCommand:0,bExecute:false},cfg:{sName:'Detector',bAutoOp:false,nTimeout:10000},stat:{nState:2,nSubstate:209,nLastCommand:0,bLocal:false,sRPCErrorText:'OK'},i_stStatus:{bEnabled:true,bTxPDOState:false},i_nCouplerState:8,calls:[]});
    f.M_SetRpcStatus=n=>{f.stat.sRPCErrorText=n===0?'OK':'Native refusal '+n;return n;};
    for(const name of ['Init','Reset','Stop','Enable','Disable','On','Off']){const fn=compile(native['RPC_'+name],'RPC_'+name);f['RPC_'+name]=()=>{f.calls.push(name);return fn(f);};}
    c.fuseDetectorPower=f;
    for(const [n,s]of Object.entries(methods)){const fn=compile(s,n==='M_ScaleInput'?n:undefined);c[n]=args=>{if(args)Object.assign(c,args);return fn(c);};}
    c.scan=(ms=10)=>{c.time+=ms;main(c);assert.equal(f.q_bSwitch,c.expectedSwitch,'Only library owns switch output');assert.equal(f.q_bReset,c.expectedReset,'Only library owns reset output');};
    c.command=n=>{c.ctrl.nCommand=n;c.ctrl.bExecute=true;c.scan();};return c;
}
for(const [n,name]of [[1,'Reset'],[2,'Init'],[3,'Stop'],[4,'Enable'],[5,'Disable'],[6,'On'],[7,'Off']]){let c=setup();c.command(n);assert.equal(c.fuseDetectorPower.calls.at(-1),name);}
let c=setup();c.fuseDetectorPower.stat.nState=1;c.fuseDetectorPower.stat.nSubstate=100;c.command(6);assert.deepEqual(c.fuseDetectorPower.calls,['On']);assert.match(c.stat.sCommandResult,/rejected/);
c=setup();c.fuseDetectorPower.stat.bLocal=true;c.command(7);assert.match(c.stat.sCommandResult,/rejected/);
c=setup();for(let cycle=0;cycle<3;cycle++){c.command(7);c.completeActivity=true;c.scan();c.scan();assert(!c.stat.bPowerOn);c.command(6);c.scan();c.scan();assert(c.stat.bPowerOn);}
c=setup();c.i_nActCurrent=2500000;c.scan();assert(!c.bOvercurrentLatched);c.i_nActCurrent=2500001;c.scan();assert(c.bOvercurrentLatched);assert.equal(c.fuseDetectorPower.stat.nSubstate,207);c.command(6);assert.match(c.stat.sCommandResult,/refused/);assert(!c.fuseDetectorPower.calls.includes('On'));
c.completeActivity=true;c.i_nActCurrent=0;c.scan();c.scan();c.ctrl.bResetOvercurrent=true;c.ctrl.bExecute=true;c.ctrl.nCommand=6;c.scan();assert(!c.bOvercurrentLatched);assert(!c.fuseDetectorPower.i_stStatus.bEnabled);assert.match(c.stat.sCommandResult,/separate/);c.command(6);c.scan();assert(c.stat.bPowerOn);
c=setup();c.fuseDetectorPower.stat.nState=1;c.fuseDetectorPower.stat.nSubstate=104;c.i_nActCurrent=3000000;c.scan();assert.equal(c.fuseDetectorPower.stat.nSubstate,209);c.scan();assert.equal(c.fuseDetectorPower.stat.nSubstate,207);
c=setup();c.fuseDetectorPower.stat.bLocal=true;c.i_nActCurrent=3000000;c.scan();assert.equal(c.fuseDetectorPower.stat.nSubstate,207,'Safety mailbox is not blocked by local GUI ownership');
c=setup();c.fuseDetectorPower.stat.nState=1;c.fuseDetectorPower.stat.nSubstate=101;c.i_nActCurrent=3000000;c.scan();assert.equal(c.fuseDetectorPower.stat.nSubstate,101);c.completeActivity=true;c.scan();c.scan();c.scan();assert.equal(c.fuseDetectorPower.stat.nSubstate,206);assert.equal(c.fuseDetectorPower.calls.length,0);
c=setup();c.i_nActCurrent=3000000;c.scan();c.scan(10010);assert(c.stat.bShutdownUnconfirmed);
for(const invalid of [1,2,8,16,64,128,16384]){c=setup();c.i_nStatus=0x8000|invalid;c.i_nActCurrent=3000000;c.scan();assert(!c.bOvercurrentLatched);assert(c.stat.bWarning);}
assert(!/\b(?:pSwitch|pReset|nOffPulseState|bOnAuthorized|bOffRequested|M_DriveOff)\b/.test(source));
const thermal=implementations(fs.readFileSync('POUs/Devices/ThermalBox/FB_NOTT_THERMAL_BOX_CONTROL.TcPOU','utf8'));
const commandTail=thermal.M_CheckCommands.slice(thermal.M_CheckCommands.indexOf('bStartRequested := FALSE;'));
const stopBlock=thermal.M_ExecuteControllers.match(/IF bStopRequested THEN[\s\S]*?END_IF/)[0];
const checkStop=compile(commandTail),executeStop=compile(stopBlock);
for(const alreadyEnabled of [true,false]){
    let disabled=0;const t={ctrl:{bEnable:alreadyEnabled,bStop:true},stat:{bPermitStart:false,bSafetyTrip:true},bWasActive:alreadyEnabled,bStopRequested:false,bStartRequested:false,
        nott_t_ctrls:{tc_thermalbox_fan_ctrl:{M_SetDisable(){disabled++;}},tc_thermalbox_valve_ctrl:{M_SetDisable(){disabled++;}}},
        pFanLoopCtrl:{lrManualOut:33},pValveLoopCtrl:{lrManualOut:44},pFanCtrl:{bAuto:true,bEnable:true,lrManualDutyPct:33},
        pValveCtrl:{eCtrlMode:2,bManualEnable:true,lrManualSetpoint:44},bClosingValve:false,bFanStartPending:true,bValveStartPending:true,
        E_METIS_CTRL_MODE:{MANUAL:1},tonValveClose(){},cfg:{tValveClose:120000}};
    checkStop(t);executeStop(t);assert(!t.ctrl.bEnable);assert(!t.ctrl.bStop);assert(t.bStopRequested);assert.equal(disabled,2);assert(!t.pFanCtrl.bEnable);assert(!t.pValveCtrl.bManualEnable);assert.equal(t.pValveCtrl.lrManualSetpoint,0);assert(t.bClosingValve);
}
console.log('PASS: actual thermal-box Stop command and stop-action ST, both enabled and already disabled, independent of readiness/safety; both loops/devices stopped and valve closure requested.');
console.log('PASS: actual wrapper ST and actual native RPC guards, with mocked plant/activities: seven direct commands, no ON-to-INIT conversion, repeated OFF/ON, library-only outputs, threshold boundary, reset separation, local/NOTOP/INIT safety paths, timeout and notification-only meter faults. Not TwinCAT compilation.');
