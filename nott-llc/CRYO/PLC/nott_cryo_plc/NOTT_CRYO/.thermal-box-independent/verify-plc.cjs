const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('POUs/Devices/ThermalBox/FB_NOTT_THERMAL_BOX_CONTROL.TcPOU','utf8');
function method(name) {
    const block = source.split('<Method Name="'+name+'"')[1].split('</Method>')[0];
    return block.match(/<ST><!\[CDATA\[([\s\S]*?)\]\]><\/ST>/)[1];
}
// Execute the coordinator's ST control flow with mocked PID/device calls. This is
// not a TwinCAT compiler or hardware test; it checks the actual edited branches.
function compile(name) {
    let code = method(name).replace(/\/\/[^\n]*/g,'');
    code = code.replace(/(ton\w+)\(IN\s*:=([\s\S]*?),\s*PT\s*:=([\s\S]*?)\);/g,'$1({IN:$2, PT:$3});');
    code = code.replace(/in_sName\s*:=/g,'in_sName:').replace(/in_tCycleTime\s*:=/g,'in_tCycleTime:')
        .replace(/temperatures\s*:=/g,'temperatures:').replace(/in_sAutoSetpointSource\s*:=/g,'in_sAutoSetpointSource:')
        .replace(/in_lrAutoSetpointValue\s*:=/g,'in_lrAutoSetpointValue:').replace(/in_eValveType\s*:=/g,'in_eValveType:')
        .replace(/in_bEnable\s*:=/g,'in_bEnable:');
    code = code.replace(/(nott_t_ctrls\.tc_thermalbox_\w+|fan|valve)\(([^;]*?)\);/g,'$1({$2});');
    code = code.replace(/\bELSIF\s+([\s\S]*?)\s+THEN/g,'} else if ($1) {')
        .replace(/\bIF\s+([\s\S]*?)\s+THEN/g,'if ($1) {').replace(/\bELSE\b/g,'} else {')
        .replace(/\bEND_IF\b/g,'}').replace(/\bTRUE\b/g,'true').replace(/\bFALSE\b/g,'false')
        .replace(/\bAND\b/g,'&&').replace(/\bOR\b/g,'||').replace(/\bNOT\b/g,'!')
        .replace(/\^\./g,'.').replace(/<>/g,'!=').replace(/:=/g,'=').replace(/(?<![<>=!:])=(?!=)/g,'===');
    // Restore assignments, which are distinguishable from comparisons by statement position.
    code = code.replace(/(^|[;{}\n])\s*([\w.]+)\s*===/g,'$1\n$2 =');
    code = code.replace(/T#(\d+)MS/gi,'$1');
    return new Function('ctx','with(ctx){'+code+'}');
}
const run = ['M_CheckCommands','M_CheckSafety','M_ExecuteControllers'].map(compile);
const modes = {NONE:0,AUTO:1,MANUAL:2};
function setup() {
    const c = {ctrl:{bEnable:false,bStop:false,bResetSafety:false,eCtrlMode:0},
        stat:{bConfigValid:true,bSafetyTrip:false,bSensorFaultStopped:false,lrFanAppliedPct:30,lrValveDemandPct:40,
            lrValveCommandPct:40,lrFanDemandPct:30,bConfigured:true},
        cfg:{bAutoCommissioned:true,tSensorFaultHold:30000,tValveClose:120000,lrSetpointOffset:0,
            lrHighTempHysteresis:2,lrTrackingHysteresis:1,lrTrackingWarning:5,tHighTempDelay:0,tTrackingDelay:0,
            bHighTempAlarmEnabled:false,bTrackingWarningEnabled:false,lrCoolantMargin:0},
        in_tCycleTime:10,bLoopsReady:true,bWasActive:false,bWasHolding:false,bWasSafetyTrip:false,
        bStartRequested:false,bStopRequested:false,bClosingValve:false,bFanHold:false,bValveHold:false,
        bFanWasHeld:false,bValveWasHeld:false,bFanStartPending:false,bValveStartPending:false,
        bFanAutoUnavailable:false,bValveAutoUnavailable:false,
        bFanLoopManualOverride:false,bValveLoopManualOverride:false,
        lrHeldFanPct:0,lrHeldValvePct:0,nHeldValveRaw:0,lrHeldValveCommandPct:0,lrFanCommandPct:0,lrValveCommandPct:0,
        bSavedFanHold:false,bSavedValveHold:false,bValvePower:false,
        E_METIS_CTRL_MODE:modes,E_METIS_CRYO_CTRL_VALVE_TYPE:{CHILLER_WATER_COOLING:1},
        LIMIT:(a,b,v)=>Math.min(b,Math.max(a,v)),nott_temps:{},nott_t_ctrls:{}};
    for(let i=1;i<=4;i++) c.nott_temps['t_thermal_box_'+i]={stat:{bValid:true,lrTempK:i<3?290:280}};
    const timer = () => Object.assign(function({IN}){if(!IN){this.Q=false;this.ET=0;}},{Q:false,ET:0});
    for(const name of ['tonSensorFault','tonValveClose','tonHighTemp','tonTracking']) {
        const fn=timer();c[name]=args=>fn.call(fn,args);Object.defineProperties(c[name],{
            Q:{get:()=>fn.Q,set:v=>fn.Q=v},ET:{get:()=>fn.ET,set:v=>fn.ET=v}});
    }
    for(const kind of ['fan','valve']) {
        const loop = Object.assign(function(){
            if(this.ctrl.eCtrlMode!==0)this.stat.eCtrlMode=this.ctrl.eCtrlMode;
            this.ctrl.eCtrlMode=0;this.stat.bCtrlModeIsManual=this.stat.eCtrlMode===2;
            this.lastHold=this.ctrl.bHold;
            if(!this.cfg.bEnabled)this.stat.lrControllerOut=0;
            else if(this.stat.eCtrlMode===2)this.stat.lrControllerOut=this.ctrl.lrManualOut;
        },{cfg:{bEnabled:false,lrKp:-1},ctrl:{eCtrlMode:0,bHold:false,lrManualOut:0},
            stat:{bConfigured:true,bStarted:true,bError:false,eCtrlMode:2,sLastForcedManualCause:'',bCtrlModeIsManual:true,lrControllerOut:kind==='fan'?30:40}});
        loop.M_SetEnable=()=>{loop.cfg.bEnabled=true;loop.ctrl.eCtrlMode=1;};
        loop.M_SetDisable=()=>{loop.cfg.bEnabled=false;loop.ctrl.eCtrlMode=2;};
        c.nott_t_ctrls['tc_thermalbox_'+kind+'_ctrl']=args=>loop.call(loop,args);
        Object.assign(c.nott_t_ctrls['tc_thermalbox_'+kind+'_ctrl'],loop);
        Object.defineProperty(c.nott_t_ctrls['tc_thermalbox_'+kind+'_ctrl'],'lastHold',{get:()=>loop.lastHold});
        c['p'+(kind==='fan'?'Fan':'Valve')+'LoopCfg']=loop.cfg;
        c['p'+(kind==='fan'?'Fan':'Valve')+'LoopCtrl']=loop.ctrl;
    }
    c.fan=Object.assign(function({in_lrAutoSetpointValue}){
        this.stat.bActive=this.ctrl.bEnable;
        this.stat.lrDutyPct=this.ctrl.bEnable?(this.ctrl.bAuto?in_lrAutoSetpointValue:this.ctrl.lrManualDutyPct):0;
        this.stat.lrSpeedRpm=0;this.stat.bStallAlarm=false;this.stat.bTachMeasurementLimited=true;
    },{ctrl:{bAuto:false,bEnable:false,lrManualDutyPct:0},stat:{bActive:false,lrDutyPct:0}});
    const fanFn=c.fan;c.fan=args=>fanFn.call(fanFn,args);Object.assign(c.fan,fanFn);
    c.valve=Object.assign(function({in_bEnable,in_lrAutoSetpointValue}){
        if(this.ctrl.eCtrlMode)this.stat.eCtrlMode=this.ctrl.eCtrlMode;
        this.ctrl.eCtrlMode=0;this.stat.bAuto=this.stat.eCtrlMode===1;this.stat.bManual=!this.stat.bAuto;
        this.stat.bActive=this.stat.bAuto?in_bEnable:this.ctrl.bManualEnable;
        this.stat.lrActSetpoint=this.stat.bAuto?in_lrAutoSetpointValue:this.ctrl.lrManualSetpoint;
        this.io_chiller_water_cooling.q_nSetVoltage=this.stat.bActive?this.stat.lrActSetpoint*100:0;
    },{ctrl:{eCtrlMode:0,bManualEnable:false,lrManualSetpoint:0},
        stat:{eCtrlMode:2,bAuto:false,bManual:true,bActive:false,bError:false,lrActSetpoint:0},
        io_chiller_water_cooling:{q_nSetVoltage:0,q_bEnable:false},i_bOverCurrent:false});
    const valveFn=c.valve;c.valve=args=>valveFn.call(valveFn,args);Object.assign(c.valve,valveFn);
    c.pFanCtrl=c.fan.ctrl;c.pValveCtrl=c.valve.ctrl;c.pValveStat=c.valve.stat;c.pValveIO=c.valve.io_chiller_water_cooling;
    c.scan=()=>run.forEach(fn=>fn(c));
    return c;
}
let c=setup();c.ctrl.bEnable=true;c.scan();assert(c.pFanLoopCfg.bEnabled&&c.pValveLoopCfg.bEnabled);assert(c.pFanCtrl.bAuto);assert(c.valve.stat.bAuto);
c.pFanCtrl.bAuto=false;c.pFanCtrl.lrManualDutyPct=65;c.scan();assert.equal(c.fan.stat.lrDutyPct,65);assert(!c.pFanCtrl.bAuto);assert(c.nott_t_ctrls.tc_thermalbox_fan_ctrl.lastHold);
c.pValveLoopCtrl.eCtrlMode=2;c.pValveLoopCtrl.lrManualOut=55;c.scan();assert.equal(c.valve.stat.lrActSetpoint,55);assert(c.ctrl.bEnable);c.scan();assert(c.nott_t_ctrls.tc_thermalbox_valve_ctrl.stat.bCtrlModeIsManual);
c.ctrl.bStop=true;c.scan();assert(!c.ctrl.bEnable);assert(!c.fan.stat.bActive);assert.equal(c.pValveIO.q_nSetVoltage,0);assert(c.pValveIO.q_bEnable);
c.pFanCtrl.bEnable=true;c.pFanCtrl.lrManualDutyPct=70;c.pValveCtrl.bManualEnable=true;c.pValveCtrl.lrManualSetpoint=60;c.scan();assert.equal(c.fan.stat.lrDutyPct,70);assert.equal(c.valve.stat.lrActSetpoint,60);assert(!c.bClosingValve);
c.ctrl.bStop=true;c.scan();assert(!c.fan.stat.bActive);assert(!c.pValveCtrl.bManualEnable);
c=setup();c.ctrl.bEnable=true;c.scan();c.nott_temps.t_thermal_box_2.stat.bValid=false;c.scan();assert(c.stat.bSensorFaultHold);c.tonSensorFault.Q=true;c.scan();assert(c.stat.bSafetyTrip);assert(!c.ctrl.bEnable);
c.pFanCtrl.bEnable=true;c.pValveCtrl.bManualEnable=true;c.scan();assert(!c.fan.stat.bActive);assert(!c.pValveCtrl.bManualEnable);
c.ctrl.bResetSafety=true;c.scan();assert(c.stat.bSafetyTrip);c.nott_temps.t_thermal_box_2.stat.bValid=true;c.ctrl.bResetSafety=true;c.scan();assert(!c.stat.bSafetyTrip);assert(!c.ctrl.bEnable);assert(!c.fan.stat.bActive);
c=setup();c.stat.bSafetyTrip=true;c.ctrl.bEnable=true;c.ctrl.bResetSafety=true;c.pFanCtrl.bEnable=true;c.pValveCtrl.bManualEnable=true;c.scan();assert(!c.stat.bSafetyTrip);assert(!c.ctrl.bEnable);assert(!c.fan.stat.bActive);assert(!c.pValveCtrl.bManualEnable);
c=setup();c.stat.bSafetyTrip=true;c.ctrl.bEnable=true;c.scan();assert(!c.ctrl.bEnable);assert(!c.fan.stat.bActive);
c=setup();c.nott_temps.t_thermal_box_1.stat.bValid=false;c.pFanCtrl.bEnable=true;c.pFanCtrl.lrManualDutyPct=45;c.scan();assert.equal(c.fan.stat.lrDutyPct,45);assert(!c.stat.bSafetyTrip);
c=setup();c.ctrl.bEnable=true;c.scan();c.valve.i_bOverCurrent=true;c.scan();assert(!c.pValveIO.q_bEnable);assert(c.ctrl.bEnable);
c=setup();c.ctrl.bEnable=true;c.scan();c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.bError=true;c.scan();assert(c.stat.bControllerAlarm);assert(c.ctrl.bEnable);assert(c.valve.stat.bActive);
c=setup();c.pValveCtrl.bManualEnable=true;c.valve.stat.bError=true;c.scan();assert(!c.pValveIO.q_bEnable);
c=setup();c.cfg.bAutoCommissioned=false;c.ctrl.bEnable=true;c.scan();assert(c.ctrl.bEnable);assert(c.pFanLoopCfg.bEnabled);
c=setup();c.pFanLoopCfg.lrKp=1;c.ctrl.bEnable=true;c.scan();assert(c.ctrl.bEnable);assert(c.bFanHold);assert(c.stat.bControllerAlarm);assert.equal(c.fan.stat.lrDutyPct,30);assert(!c.bValveHold);
c.pFanLoopCfg.lrKp=-1;c.scan();assert(!c.bFanHold);assert(c.ctrl.bEnable);
c=setup();c.bLoopsReady=false;c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.bConfigured=false;c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.bStarted=false;c.ctrl.bEnable=true;c.scan();assert(c.ctrl.bEnable);assert(c.bFanStartPending);assert(c.pValveLoopCfg.bEnabled);
c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.bConfigured=true;c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.bStarted=true;c.scan();assert(!c.bFanStartPending);assert(c.pFanLoopCfg.bEnabled);
c=setup();c.nott_temps.t_thermal_box_1.stat.bValid=false;c.ctrl.bEnable=true;c.scan();assert(c.ctrl.bEnable);assert(c.bFanHold&&c.bValveHold);
c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.eCtrlMode=2;c.scan();assert(c.bFanHold);c.pFanLoopCtrl.eCtrlMode=2;c.pFanLoopCtrl.lrManualOut=55;c.scan();assert(!c.bFanHold);assert.equal(c.fan.stat.lrDutyPct,55);
c=setup();c.ctrl.bEnable=true;c.scan();c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.eCtrlMode=2;c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.sLastForcedManualCause='Invalid input temperature';c.scan();assert.equal(c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.eCtrlMode,1);
c.pFanLoopCtrl.eCtrlMode=2;c.scan();c.scan();assert.equal(c.nott_t_ctrls.tc_thermalbox_fan_ctrl.stat.eCtrlMode,2);
assert(!source.includes('pValveStat^.eCtrlMode := E_METIS_CTRL_MODE.AUTO'));
assert(!source.includes('pFanLoopCtrl^.eCtrlMode := eLoopMode'));
assert(source.includes('E_ALL_NOTT_TEMPERATURES.t_thermal_box_2'));
console.log('PASS: actual ST branch simulation for startup, independent device/PID manual, one-shot stop, offline manual restart, sensor hold/trip/reset, and valve overload. TwinCAT compilation is not performed.');
