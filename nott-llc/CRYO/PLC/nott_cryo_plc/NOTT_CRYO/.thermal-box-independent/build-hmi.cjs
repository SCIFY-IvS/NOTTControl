const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, 'files');
const box = 'ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl';
const fan = box + '.fan';
const read = f => fs.readFileSync(path.join(root, f), 'utf8');
const save = (f, s) => fs.writeFileSync(path.join(root, f), s);
const esc = s => String(s).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
function control(id, type, x, y, w, h, attrs = {}, inside = '') {
    const all = {'data-tchmi-type':'TcHmi.Controls.'+type, 'data-tchmi-left':x, 'data-tchmi-top':y,
        'data-tchmi-width':w, 'data-tchmi-height':h, 'data-tchmi-left-unit':'px', 'data-tchmi-top-unit':'px',
        'data-tchmi-width-unit':'px', 'data-tchmi-height-unit':'px', ...attrs};
    return '<div id="'+id+'" '+Object.entries(all).map(([k,v])=>k+'="'+esc(v)+'"').join(' ')+'>'+inside+'</div>\r\n';
}
const pp = p => '%pp%'+p+'%/pp%';
const ss = p => '%s%'+box+'.stat::'+p+'%/s%';
const expression = s => '%f%'+s+'%/f%';
function label(id, x, y, w, text, h=28) {
    return control(id, 'Beckhoff.TcHmiTextblock', x,y,w,h, {'data-tchmi-text':text,
        'data-tchmi-text-font-size':14, 'data-tchmi-text-vertical-alignment':'Center', 'data-tchmi-word-wrap':true});
}
function trigger(action, routine=false, attach=false) {
    const arg = value => ({objectType:'StaticValue', valueType:'tchmi:general#/definitions/String', value});
    const sym = symbolExpression => ({objectType:'Symbol', valueType:'tchmi:general#/definitions/String', symbolExpression});
    return '<script data-tchmi-target-attribute="data-tchmi-trigger" type="application/json">'+JSON.stringify([{
        event:'%ctx%owner::Id|EventRegistrationMode=Resolve%/ctx%.'+(attach?'onAttached':'onPressed'),
        actions:[{objectType:'Function', active:true, fn:'TcHmi.Functions.NOTT.NOTTFanAction',
            fnParams:[sym('%ctx%owner::Id%/ctx%'), routine?arg(fan):sym(pp('FanSymbol')),
                routine?arg(box):sym(pp('ControlSymbol')), arg(action)], asyncWait:true}]
    }],null,2)+'</script>';
}
const rights = '<script data-tchmi-target-attribute="data-tchmi-access-config" type="application/json">'+
    '[{"accessright":"operate","group":"Monitoring","permission":"Deny"}]</script>';
function button(id,x,y,w,text,action,enabled,routine=false) {
    return control(id,'Beckhoff.TcHmiButton',x,y,w,34,{'data-tchmi-text':text,
        'data-tchmi-tooltip':text, 'data-tchmi-is-enabled':enabled}, trigger(action,routine)+rights);
}
const manual = expression(pp('FanObject::ctrl::bAuto')+' === false && '+pp('ThermalStatus::bSafetyTrip')+' === false');
let body = label('NOTTFanOperate_Title',20,12,600,'Thermal box fan');
body += label('NOTTFanOperate_Status',20,52,600,expression(pp('FanObject::stat::bActive')+" === true ? 'Fan enabled' : 'Fan stopped'"));
body += button('NOTTFanOperate_Enable',20,98,180,'Start fan','Enable',manual);
body += button('NOTTFanOperate_Disable',220,98,180,'Stop fan','Disable','true');
body += button('NOTTFanOperate_Auto',20,148,110,'AUTO','Auto',expression(pp('ThermalStatus::bSafetyTrip')+' === false'));
body += button('NOTTFanOperate_Manual',145,148,110,'MANUAL','Manual',expression(pp('ThermalStatus::bSafetyTrip')+' === false'));
body += label('NOTTFanOperate_Mode',290,148,320,expression(pp('FanObject::ctrl::bAuto')+" === false ? 'Fan mode: MANUAL' : 'Fan mode: AUTO'"));
for (const [i,title,field] of [[0,'Fan demand [%]','lrDemandPct'],[1,'Applied duty [%]','lrDutyPct'],[2,'Speed [rpm]','lrSpeedRpm']]) {
    body += label('NOTTFanOperate_ReadLabel'+i,20,204+i*36,230,title);
    body += label('NOTTFanOperate_Read'+i,285,204+i*36,300,pp('FanObject::stat::'+field));
}
body += label('NOTTFanOperate_ManualLabel',20,330,245,'Manual fan demand [%]');
body += control('NOTTFanOperate_Demand','Beckhoff.TcHmiNumericInput',285,330,140,34,
    {'data-tchmi-min-value':0,'data-tchmi-max-value':100,'data-tchmi-decimal-digits':1,
        'data-tchmi-value':0,'data-tchmi-is-enabled':manual},rights);
body += button('NOTTFanOperate_SetDemand',450,330,150,'Set fan demand','SetDemand',manual);
body += label('NOTTFanOperate_Safety',20,382,600,expression(pp('ThermalStatus::bSafetyTrip')+" === true ? 'Safety stop latched' : 'Safety stop clear'"));
body += label('NOTTFanOperate_Source',20,420,600,pp('FanObject::stat::sAutoSetpointSource'));
body += label('NOTTFanOperate_Feedback',20,468,600,'',60);
save('UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateOperate.usercontrol',
    control('NOTTFanOperate','System.TcHmiUserControl',0,0,640,550,{},body+trigger('Refresh',false,true)));
let status = label('NOTTFanStatus_Title',20,12,600,'Fan diagnostics');
const rows = [['Fan enabled','stat::bActive'],['Running feedback','stat::bRunning'],['Stall alarm','stat::bStallAlarm'],
    ['Tach sampling limited','stat::bTachMeasurementLimited'],['Pulse count','stat::nPulseCount'],
    ['PWM raw command','q_nPwmCommand'],['Power enable command','q_bEnable'],['Automatic mode','ctrl::bAuto']];
rows.forEach(([title,field],i)=>{
    status += label('NOTTFanStatus_Label'+i,20,56+i*40,265,title);
    status += label('NOTTFanStatus_Value'+i,310,56+i*40,300,pp('FanObject::'+field));
});
status += label('NOTTFanStatus_Safety',20,400,600,expression(pp('ThermalStatus::bSafetyTrip')+" === true ? 'Safety stop latched' : 'Safety stop clear'"));
save('UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateStatus.usercontrol',
    control('NOTTFanStatus','System.TcHmiUserControl',0,0,640,550,{},status));

let panel = button('ThermalBox_Enable',350,35,180,'Enable thermal box','ThermalEnable',expression(ss('bPermitStart')+' === true && '+ss('bActive')+' === false'),true);
panel += button('ThermalBox_Disable',550,35,180,'Disable thermal box','ThermalDisable','true',true);
panel += button('ThermalBox_ResetSafety',750,35,170,'Reset safety','ResetSafety',expression(ss('bSafetyTrip')+' === true'),true);
panel += button('ThermalBox_ConfirmAlarms',940,35,180,'Confirm alarms','ConfirmAlarms','true',true);
panel += label('ThermalBox_RoutineStatus',20,78,1240,ss('sStatus'));
panel += label('ThermalBox_TargetStatus',20,110,440,expression("'Target: ' + Number("+ss('lrTargetTempK')+").toFixed(2) + ' K | Inside: ' + Number("+ss('lrInsideTempK')+").toFixed(2) + ' K'"));
panel += label('ThermalBox_StartInhibit',480,110,780,ss('sStartInhibitReason'));
[['Fan device','bFanManual'],['Valve device','bValveManual'],['Fan PID','bFanLoopManual'],['Valve PID','bValveLoopManual']].forEach(([title,field],i)=>{
    panel += label('ThermalBox_Mode'+i,20+i*310,142,300,expression("'"+title+": ' + ("+ss(field)+" === true ? 'MANUAL' : 'AUTO')"));
});
const diagnostics = [
    ['Control sensors valid','bControlSensorsValid'],['Sensor hold active','bSensorFaultHold'],
    ['Safety stop latched','bSafetyTrip'],['Routine alarm','bAlarm'],['Routine warning','bWarning']];
diagnostics.forEach(([title,field],i)=>{
    panel += label('ThermalBox_Diagnostic'+i,935,210+i*25,330,expression("'"+title+": ' + String("+ss(field)+')'),24);
});
panel += label('ThermalBox_SensorHoldTime',935,335,330,expression("'Sensor hold [min]: ' + (Number("+ss('tSensorFaultElapsed')+") / 60000).toFixed(1)"),24);
panel += label('ThermalBox_Feedback',20,637,1240,'',36);
let page = read('Pages/ThermalBox.content');
const previousPanel = page.indexOf('<div id="ThermalBox_Enable"');
if (previousPanel >= 0) page = page.slice(0,previousPanel) + page.slice(page.lastIndexOf('</div>'));
page = page.replace('data-tchmi-width="1280" data-tchmi-height="650"','data-tchmi-width="1280" data-tchmi-height="680"');
const end = page.lastIndexOf('</div>');
save('Pages/ThermalBox.content',page.slice(0,end)+panel+page.slice(end));

const config = JSON.parse(read('Server/TcHmiSrv/TcHmiSrv.Config.default.json'));
const ref = t => ({$ref:'tchmi:general#/definitions/'+t});
const newStatus = Object.fromEntries(['bAutoReady','bSafetyTrip','bFanManual','bValveManual','bFanLoopManual','bValveLoopManual','bMixedMode'].map(k=>[k,ref('BOOL')]));
newStatus.sStartInhibitReason = {allOf:[ref('String'),{maxLength:255}]};
for (const [name, schema] of Object.entries(config.DEFINITIONS.ADS)) {
    if (name.includes('T_NOTT_THERMAL_BOX_STAT') || name.endsWith('.NOTT_FAN_BOX_STAT')) {
        schema.properties = {...schema.properties, ...newStatus};
    }
    if (name.includes('T_NOTT_THERMAL_BOX_CTRL') || name.endsWith('.NOTT_FAN_BOX_CTRL')) {
        schema.properties = {...schema.properties,bStop:ref('BOOL'),bResetSafety:ref('BOOL')};
    }
}
config.SYMBOLS[fan+'.ctrl'] = {ACCESS:3, DOMAIN:'ADS', DYNAMIC:true,
    MAPPING:'NOTT_CRYO_PLC::MAIN::nott_cryo_ctrl::thermal_box_ctrl::fan::ctrl',
    SCHEMA:{$ref:'tchmi:server#/definitions/ADS-NOTT_CRYO_PLC.T_NOTT_FAN_CTRL'}, USEMAPPING:true};
for (const [name, group] of Object.entries(config.USERGROUPS)) {
    if (['Operation','Engineering','Monitoring'].includes(name)) group.SYMBOLS[fan+'.ctrl'] = name==='Monitoring'?1:3;
}
save('Server/TcHmiSrv/TcHmiSrv.Config.default.json',JSON.stringify(config,null,4)+'\n');
console.log('Built independent fan faceplates, routine controls/diagnostics, and scoped HMI mappings.');
