const fs=require('node:fs'),assert=require('node:assert/strict');
const src=fs.readFileSync('POUs/Devices/Detector_Power/FB_NOTT_DETECTOR_POWER.TcPOU','utf8');
function compile(code,name=''){
    code=code.replace(/\/\/[^\n]*/g,'');
    code=code.replace(/p(?:Switch|Reset)\s*:=\s*ADR\([^;]*\);/g,'');
    code=code.replace(/pSwitch\^/g,'output.sw').replace(/pReset\^/g,'output.reset').replace(/\^\./g,'.');
    code=code.replace(/i_nStatus\s+AND\s+UINT#16#([\dA-F]+)/g,'i_nStatus & 0x$1');
    code=code.replace(/T#(\d+)MS/gi,'$1').replace(/T#(\d+)S/gi,(_m,n)=>String(Number(n)*1000));
    code=code.replace(/\b(tonStale|tonShutdown|tpOff|trigDetectorPower|fuseDetectorPower|M_ScaleInput)\(([^;]*?)\);/g,(_m,fn,args)=>fn+'({'+args.replace(/(\w+)\s*:=/g,'$1:')+'});');
    code=code.replace(/\bELSIF\s+([\s\S]*?)\s+THEN/g,'} else if ($1) {').replace(/\bIF\s+([\s\S]*?)\s+THEN/g,'if ($1) {')
        .replace(/\bELSE\b/g,'} else {').replace(/\bEND_IF\b/g,'}');
    let count=0;
    code=code.replace(/\bCASE (\w+) OF/g,'switch($1){').replace(/^\s*(\d+):/gm,(_m,n)=>(count++?'break;':'')+'case '+n+':').replace(/END_CASE/g,'break;}');
    code=code.replace(/\bAND\b/g,'&&').replace(/\bOR\b/g,'||').replace(/\bNOT\b/g,'!').replace(/\bTRUE\b/g,'true').replace(/\bFALSE\b/g,'false')
        .replace(/<>/g,'!=').replace(/:=/g,'=').replace(/(?<![<>=!:])=(?!=)/g,'===')
        .replace(/(^|[;{}\n:])\s*([\w.]+)\s*===/g,'$1\n$2 =');
    if(name)code=code.replace(new RegExp('\\b'+name+'\\s*=.*?;','g'),'');
    return new Function('ctx','with(ctx){'+code+'}');
}
const main=compile(src.split('<Implementation>')[1].match(/<ST><!\[CDATA\[([\s\S]*?)\]\]><\/ST>/)[1]);
const methods={};for(const m of src.matchAll(/<Method Name="(\w+)"[\s\S]*?<Implementation><ST><!\[CDATA\[([\s\S]*?)\]\]><\/ST><\/Implementation>/g))methods[m[1]]=compile(m[2],m[1]);
function setup(){
    const c={time:0,output:{sw:false,reset:false},cfg:{lrCurrentTrip_A:2.5,tMeasurementTimeout:5000},ctrl:{nCommand:0,bExecute:false,bResetOvercurrent:false},stat:{},
        i_nActCurrent:1400000,i_nStatus:0x8000,i_nMeterState:8,ABS:Math.abs,DINT_TO_LREAL:Number,LREAL_TO_STRING:String,CONCAT:(a,b)=>a+b,ADR:x=>x,
        E_FUSE_COMMAND:{NONE:0,RESET:1,INIT:2,STOP:3,ENABLE:4,DISABLE:5,ON:6,OFF:7},E_FUSE_STATE:{OP:2},
        TC_EVENTS:{NottCryoSysEventClass:{Critical:1,Warning:2,Error:3}}};
    for(const m of src.split('</Declaration>')[0].matchAll(/^\s*(\w+)(?: AT %I\*)?:\s*(\w+)/gm)){
        const name=m[1];if(!(name in c))c[name]=m[2]==='BOOL'?false:0;
    }
    for(const m of fs.readFileSync('DUTs/Structures/DetectorPower/T_NOTT_DETECTOR_POWER_STAT.TcDUT','utf8').matchAll(/^\s*(\w+):\s*(\w+)/gm))c.stat[m[1]]=m[2]==='BOOL'?false:m[2]==='STRING'?'':0;
    function ton(){let start=null;const fn=({IN,PT})=>{if(!IN){start=null;fn.Q=false;fn.ET=0;}else{if(start===null)start=c.time;fn.ET=c.time-start;fn.Q=fn.ET>=PT;}};return Object.assign(fn,{Q:false,ET:0});}
    c.tonStale=ton();c.tonShutdown=ton();
    let until=0,last=false;
    c.tpOff=Object.assign(({IN,PT})=>{if(IN&&!last&&c.time>=until)until=c.time+PT;last=IN;c.tpOff.Q=c.time<until;},{Q:false});
    let previous=false;c.trigDetectorPower=Object.assign(({CLK})=>{c.trigDetectorPower.Q=CLK&&!previous;previous=CLK;},{Q:false});
    for(const name of ['fbTripAlarm','fbMeterAlarm','fbShutdownAlarm'])c[name]={raises:0,clears:0,CreateEx:()=>0,ipArguments:{Clear(){},AddString(){}},Raise(){this.raises++;},Clear(){this.clears++;}};
    const f=Object.assign(function(){
        if(f.ctrl.bExecute){f.stat.last=f.ctrl.nCommand;f.ctrl.bExecute=false;}
        // Simulate an INIT sequence trying to energize an OFF channel.
        c.output.sw=!!c.nativePulse;c.output.reset=!!c.nativeReset;
    },{ctrl:{nCommand:0,bExecute:false},cfg:{sName:'Detector fuse',bAutoOp:true,nTimeout:10000},stat:{bLocal:false,nState:2},i_nCouplerState:8,i_stStatus:{bEnabled:true,bTxPDOState:false}});
    c.fuseDetectorPower=f;
    for(const [name,fn] of Object.entries(methods))c[name]=args=>{if(args)Object.assign(c,args);return fn(c);};
    c.scan=(ms=10)=>{c.time+=ms;main(c);};
    c.command=n=>{c.ctrl.nCommand=n;c.ctrl.bExecute=true;c.scan();};
    return c;
}
let c=setup();c.scan();assert(c.stat.bCurrentValid);assert.equal(c.lrActCurrent,1.4);assert(!c.bOvercurrentLatched);
c=setup();c.i_nActCurrent=2500000;c.scan();assert(!c.bOvercurrentLatched);c.i_nActCurrent=2500001;c.scan();assert(c.bOvercurrentLatched);assert(c.output.sw);assert.equal(c.fbTripAlarm.raises,1);
c.ctrl.nCommand=6;c.ctrl.bExecute=true;c.fuseDetectorPower.ctrl.nCommand=6;c.fuseDetectorPower.ctrl.bExecute=true;c.scan();assert(c.bOvercurrentLatched);assert.notEqual(c.fuseDetectorPower.stat.last,6);
c.i_nActCurrent=0;c.fuseDetectorPower.i_stStatus.bEnabled=false;c.ctrl.bResetOvercurrent=true;c.scan();assert(c.bOvercurrentLatched);
for(let i=0;i<15;i++)c.scan();assert(!c.bShutdownInProgress);c.ctrl.bResetOvercurrent=true;c.ctrl.nCommand=6;c.ctrl.bExecute=true;c.nativePulse=true;c.scan();assert(!c.bOvercurrentLatched);assert(!c.bOnAuthorized);assert(!c.output.sw);
c.command(6);assert(c.bOnAuthorized);assert(c.output.sw);
c=setup();c.i_nActCurrent=-2500001;c.scan();assert(c.bOvercurrentLatched);
for(const mask of [1,2,8,16,64,128,16384]){c=setup();c.i_nStatus=0x8000|mask;c.i_nActCurrent=4000000;c.scan();assert(!c.stat.bCurrentValid);assert(!c.bOvercurrentLatched);assert(!c.bOffRequested);assert.equal(c.fbMeterAlarm.raises,1);}
c=setup();c.scan();c.scan();c.scan(5010);assert(c.stat.bMeasurementStale);assert(!c.bOvercurrentLatched);
c=setup();c.i_nStatus=0;c.i_nActCurrent=3000000;c.scan();assert(!c.stat.bCurrentValid);assert(!c.bOvercurrentLatched);c.i_nStatus=0x8000;c.scan();assert(c.bOvercurrentLatched);
c=setup();c.bPreviousSwitch=true;c.i_nActCurrent=3000000;c.nativePulse=true;c.scan();assert(!c.output.sw);assert.equal(c.nOffPulseState,1);c.scan();assert(c.output.sw);c.scan(50);assert(c.output.sw);c.scan(50);assert(!c.output.sw);
c=setup();c.i_nActCurrent=3000000;c.scan();c.scan(10010);assert(c.stat.bShutdownUnconfirmed);assert.equal(c.fbShutdownAlarm.raises,1);
c=setup();c.nativePulse=true;c.fuseDetectorPower.i_stStatus.bEnabled=false;c.scan();assert(!c.output.sw);c.ctrl.nCommand=1;c.ctrl.bExecute=true;c.scan();assert(!c.output.sw);
c=setup();c.command(7);assert(c.bOffRequested);assert(c.output.sw);c.scan(110);assert(!c.output.sw);c.fuseDetectorPower.i_stStatus.bEnabled=false;c.scan();c.scan();assert(!c.bOffRequested);
c=setup();c.fuseDetectorPower.stat.bLocal=true;c.command(6);assert(!c.bOnAuthorized);
console.log('PASS: actual ST control-flow simulation with mocked fuse/timers: threshold boundary, reverse current, no-delay trip, pulse handoff, ON inhibit, reset stays OFF, diagnostic-only faults, stale samples, OFF during transitions and shutdown timeout. Not TwinCAT compilation.');
