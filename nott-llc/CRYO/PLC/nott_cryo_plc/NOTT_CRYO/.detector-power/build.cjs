const fs=require('node:fs'),path=require('node:path');
const stage=path.join(__dirname,'files');
const live='C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const lib='C:/Users/u0149673/met-ics/fcs/LCS/METIS_CTRL/SRC/Fuse/Fuse/Fuse/DUTs/Structures';
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json'),'utf8'));
function save(file,text){const dest=path.join(stage,file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,text);if(!manifest.some(x=>x.target===path.join(live,file)))manifest.push({target:path.join(live,file),stage:dest,hash:null});}
const read=f=>fs.readFileSync(path.join(stage,f),'utf8');
const base='ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power',fuse=base+'.fuseDetectorPower';
const s=p=>'%s%'+base+'.'+p+'%/s%';
const f=p=>s('fuseDetectorPower.'+p);
const expr=p=>'%f%'+p+'%/f%';
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
const rights=engineering=>'<script type="application/json" data-tchmi-target-attribute="data-tchmi-access-config">'+JSON.stringify([
    {accessright:'operate',group:'Monitoring',permission:'Deny'},...(engineering?[{accessright:'operate',group:'Operation',permission:'Deny'}]:[])])+'</script>';
function div(id,type,x,y,w,h,attrs={},inner=''){return '<div id="'+id+'" '+Object.entries({'data-tchmi-type':'TcHmi.Controls.'+type,'data-tchmi-left':x,'data-tchmi-top':y,'data-tchmi-width':w,'data-tchmi-height':h,'data-tchmi-left-unit':'px','data-tchmi-top-unit':'px','data-tchmi-width-unit':'px','data-tchmi-height-unit':'px',...attrs}).map(([k,v])=>k+'="'+esc(v)+'"').join(' ')+'>'+inner+'</div>\n';}
const text=(id,x,y,w,label,h=28,size=14)=>div(id,'Beckhoff.TcHmiTextblock',x,y,w,h,{'data-tchmi-text':label,'data-tchmi-text-font-size':size,'data-tchmi-word-wrap':true,'data-tchmi-text-vertical-alignment':'Center'});
function trigger(action,attached=false){return '<script type="application/json" data-tchmi-target-attribute="data-tchmi-trigger">'+JSON.stringify([{event:'%ctx%owner::Id|EventRegistrationMode=Resolve%/ctx%.'+(attached?'onAttached':'onPressed'),actions:[{objectType:'Function',active:true,fn:'TcHmi.Functions.NOTT.DetectorPowerAction',fnParams:[{objectType:'Symbol',valueType:'tchmi:general#/definitions/String',symbolExpression:'%ctx%owner::Id%/ctx%'},{objectType:'StaticValue',valueType:'tchmi:general#/definitions/String',value:action}],asyncWait:true}]}],null,2)+'</script>';}
const button=(id,x,y,w,title,action,engineering=false,enabled='true')=>div(id,'Beckhoff.TcHmiButton',x,y,w,32,{'data-tchmi-text':title,'data-tchmi-tooltip':title,'data-tchmi-is-enabled':enabled},trigger(action)+rights(engineering));
function content(id,body,height=490){return div(id,'System.TcHmiContent',0,0,1280,height,{},body);}
function row(prefix,title,value,x,y,w=580){const label=Math.min(175,Math.floor(w*0.56));return text(prefix+'_Label',x,y,label,title)+text(prefix+'_Value',x+label+10,y,w-label-10,value);}
let main=text('DetectorPower_Title',20,8,350,'Detector Power',34,22);
main+=div('DetectorPower_PowerPath','Beckhoff.TcHmiImage',420,5,830,43,{'data-tchmi-src':'Images/NOTT/DetectorPowerPath.svg'});
for(const [i,title,n] of [[0,'INIT',2],[1,'RESET',1],[2,'STOP',3],[3,'ENABLE',4],[4,'DISABLE',5],[5,'ON',6],[6,'OFF',7]]){
    main+=button('DetectorPower_Command'+n,20+i*102,58,92,title,'Command'+n,false,n===6?expr(s('stat::bPermitOn')+' === true'):'true');
}
main+=button('DetectorPower_ResetTrip',785,58,180,'Reset overcurrent','ResetTrip',false,expr(s('stat::bPermitTripReset')+' === true'));
main+=text('DetectorPower_CommandResult',985,52,275,s('stat::sCommandResult'),46,12);
main+=text('DetectorPower_Feedback',20,96,1240,'',24,12);
const tabs=['Overview','Diagnostics','Configuration'].map(name=>({displayName:name,name,targetFile:{path:'Pages/DetectorPower'+name+'.content',attributes:{}},targetFileHostKeepAlive:false,targetFileHostPreAttach:false,targetFileHostPreload:false}));
main+=div('DetectorPower_Tabs','Beckhoff.TcHmiTabNavigation',0,124,1280,526,{},'<script type="application/json" data-tchmi-target-attribute="data-tchmi-tabs">'+JSON.stringify(tabs,null,2)+'</script>');
save('Pages/DetectorPower.content',content('DetectorPower',main,650));
let overview=text('DetectorPowerOverview_Title',20,8,580,'24 V Fuse and Supply Input',32,18);
const fields=[['State',f('stat::sState')],['Substate',f('stat::sSubstate')],['Status',expr('String('+f('stat::nStatus')+") + ' | ' + "+f('stat::sStatus'))],['Hardware status',expr('String('+f('stat::nHwStatus')+") + ' | ' + "+f('stat::sHwStatus'))],['Error',expr('String('+f('stat::nErrorCode')+") + ' | ' + "+f('stat::sErrorText'))],['RPC result',f('stat::sRPCErrorText')],['Action',f('stat::sActionDesc')],['Event',f('stat::sEventDesc')],['Last command',f('stat::sLastCommand')],['Fuse library version',f('stat::sLibVersion')]];
fields.forEach(([title,value],i)=>overview+=row('DetectorPowerOverview_State'+i,title,value,20,48+i*29));
[['Fuse input [V]','rVoltageIn'],['Fuse output [V]','rVoltageOut'],['Fuse current [A]','rCurrent'],['Load [x nominal]','rLoad']].forEach(([title,field],i)=>overview+=row('DetectorPowerOverview_Power'+i,title,f('stat::'+field),20+(i%2)*310,348+Math.floor(i/2)*30,300));
[['ON time [s]','nTimeOn'],['Total ON [s]','nTimeOnTotal'],['OFF time [s]','nTimeOff']].forEach(([title,field],i)=>overview+=row('DetectorPowerOverview_Timer'+i,title,f('stat::'+field),20+i*205,414,200));
overview+=text('DetectorPowerOverview_CurrentTitle',670,8,590,'Detector-Side Current (5 V Supply Output)',32,18);
overview+=text('DetectorPowerOverview_Current',670,52,590,expr(s('stat::bCurrentValid')+' === true ? Number('+s('stat::lrCurrent_A')+").toFixed(4) + ' A' : 'Unavailable'"),58,34);
overview+=row('DetectorPowerOverview_Enabled','Power feedback',s('stat::bPowerOn'),670,124);
overview+=row('DetectorPowerOverview_Trip','Overcurrent latched',s('stat::bOvercurrentTrip'),670,158);
overview+=row('DetectorPowerOverview_TripLimit','Trip limit [A]',s('cfg::lrCurrentTrip_A'),670,192);
overview+=row('DetectorPowerOverview_TripCurrent','Trip sample [A]',s('stat::lrTripCurrent_A'),670,226);
overview+=row('DetectorPowerOverview_Shutdown','Shutdown unconfirmed',s('stat::bShutdownUnconfirmed'),670,260);
overview+=text('DetectorPowerOverview_Status',670,302,590,s('stat::sStatus'),68);
overview+=text('DetectorPowerOverview_MeterStatus',670,378,590,s('stat::sMeasurementStatus'),70);
overview+=text('DetectorPowerOverview_Feedback',20,455,1240,'',30,12);
save('Pages/DetectorPowerOverview.content',content('DetectorPowerOverview',overview));

const fuseBits=['bEnabled','bTripped','bShortCircuit','bOverload','bHardwareProtection','bOvervoltage','bUndervoltage','bCurrentLevelWarning','bCoolDownLock','bDisabledBySwitch','bDisabledByDI','bDisabledByOutput','bDiag','bTxPDOState','bInputCycleCounterBit0','bInputCycleCounterBit1','bStateDeviceSwitch','bStateDigitalInput','bError','bStateReset','bStateSwitch'];
const human={bTxPDOState:'PDO invalid',bInputCycleCounterBit0:'Input cycle counter bit 0',bInputCycleCounterBit1:'Input cycle counter bit 1',bDiag:'Diagnostic present',bDisabledByDI:'Disabled by digital input'};
const title=k=>human[k]||k.slice(1).replace(/([a-z])([A-Z])/g,'$1 $2');
let diag=text('DetectorPowerDiagnostics_FuseTitle',20,8,600,'EL9227-5500 Hardware Status',32,18);
fuseBits.forEach((bit,i)=>{
    const x=20+Math.floor(i/11)*310,y=54+(i%11)*32;
    const value=f('i_stStatus::'+bit);
    diag+=div('DetectorPowerDiagnostics_Fuse_'+bit,'Beckhoff.TcHmiCheckbox',x,y,300,28,{'data-tchmi-text':title(bit),'data-tchmi-toggle-state':expr(value+" === true ? 'Active' : 'Normal'"),'data-tchmi-is-enabled':false});
});
diag+=text('DetectorPowerDiagnostics_MeterTitle',670,8,590,'ES3681 / EL3681 Current Monitor',32,18);
['bMeterOperational','bCurrentValid','bMeasurementStale','bUnderrange','bOverrange','bExtendedRange','bDataInvalid','bRangeInvalid','bAutorangeDisabled','bConversionError','bCalibrating','bPdoInvalid','bPdoToggle','bConfigValid'].forEach((bit,i)=>{
    diag+=div('DetectorPowerDiagnostics_Meter_'+bit,'Beckhoff.TcHmiCheckbox',670+Math.floor(i/7)*300,54+(i%7)*32,290,28,{'data-tchmi-text':title(bit),'data-tchmi-toggle-state':expr(s('stat::'+bit)+" === true ? 'Active' : 'Normal'"),'data-tchmi-is-enabled':false});
});
diag+=row('DetectorPowerDiagnostics_Raw','Raw meter status',s('stat::nMeterStatus'),670,294);
diag+=text('DetectorPowerDiagnostics_Message',670,338,590,s('stat::sMeasurementStatus'),88);
diag+=text('DetectorPowerDiagnostics_Feedback',20,455,1240,'',30,12);
save('Pages/DetectorPowerDiagnostics.content',content('DetectorPowerDiagnostics',diag));

let cfg=text('DetectorPowerConfiguration_Title',20,8,1200,'Detector Power Configuration',32,18);
cfg+=text('DetectorPowerConfiguration_NameLabel',20,58,200,'Fuse name');
cfg+=div('DetectorPowerConfiguration_Name','Beckhoff.TcHmiTextbox',235,58,355,32,{'data-tchmi-text':''},rights(true));
function number(id,x,y,w,min,max){return div(id,'Beckhoff.TcHmiNumericInput',x,y,w,32,{'data-tchmi-min-value':min,'data-tchmi-max-value':max,'data-tchmi-value':min,'data-tchmi-decimal-digits':id.endsWith('_Limit')?3:0},rights(true));}
cfg+=text('DetectorPowerConfiguration_FuseTimeoutLabel',20,112,200,'Fuse timeout [ms]');cfg+=number('DetectorPowerConfiguration_FuseTimeout',235,112,180,100,600000);
cfg+=div('DetectorPowerConfiguration_Log','Beckhoff.TcHmiCheckbox',20,170,250,32,{'data-tchmi-text':'Fuse event logging'},rights(true));
cfg+=div('DetectorPowerConfiguration_AutoOp','Beckhoff.TcHmiCheckbox',300,170,290,32,{'data-tchmi-text':'Automatic software OP'},rights(true));
cfg+=div('DetectorPowerConfiguration_Local','Beckhoff.TcHmiCheckbox',20,228,250,32,{'data-tchmi-text':'Local PLC GUI control'},rights(true));
cfg+=button('DetectorPowerConfiguration_ApplyLocal',300,228,210,'Apply ownership','ApplyLocal',true);
cfg+=text('DetectorPowerConfiguration_LimitLabel',670,58,270,'Immediate trip limit [A]');cfg+=number('DetectorPowerConfiguration_Limit',960,58,220,0.001,10);
cfg+=text('DetectorPowerConfiguration_StaleTimeLabel',670,112,270,'Measurement timeout [ms]');cfg+=number('DetectorPowerConfiguration_StaleTime',960,112,220,100,600000);
cfg+=button('DetectorPowerConfiguration_Save',670,228,220,'Apply configuration','SaveConfig',true);
cfg+=button('DetectorPowerConfiguration_Reload',920,228,180,'Reload','LoadConfig');
cfg+=row('DetectorPowerConfiguration_TripStatus','Trip latched',s('stat::bOvercurrentTrip'),670,302);
cfg+=row('DetectorPowerConfiguration_Remote','Local control',f('stat::bLocal'),20,302);
cfg+=text('DetectorPowerConfiguration_Result',20,362,1240,s('stat::sCommandResult'),60);
cfg+=text('DetectorPowerConfiguration_Feedback',20,455,1240,'',30,12);
cfg+=trigger('LoadConfig',true);
save('Pages/DetectorPowerConfiguration.content',content('DetectorPowerConfiguration',cfg));

save('Images/NOTT/DetectorPowerPath.svg','<svg xmlns="http://www.w3.org/2000/svg" width="830" height="43" viewBox="0 0 830 43"><g fill="none" stroke="#56616a" stroke-width="1.5"><path d="M155 22h35m155 0h35m155 0h35"/><path d="m180 17 8 5-8 5m180-10 8 5-8 5m180-10 8 5-8 5"/><rect x="0" y="2" width="155" height="39" rx="3"/><rect x="190" y="2" width="155" height="39" rx="3"/><rect x="380" y="2" width="155" height="39" rx="3"/><rect x="570" y="2" width="155" height="39" rx="3"/></g><g fill="#25313a" font-family="Arial" font-size="13" text-anchor="middle"><text x="77" y="26">EL9227 - 24 V</text><text x="267" y="26">24 V / 5 V DC/DC</text><text x="457" y="26">ES3681 - Current</text><text x="647" y="26">Detector</text></g></svg>');
save('JavaScript/DetectorPowerAction.function.json',JSON.stringify({function:{name:'DetectorPowerAction',namespace:'TcHmi.Functions.NOTT',displayName:'Detector Power Action',description:'Guarded detector power commands and configuration.',waitMode:'Synchronous',category:'NOTT',returnValue:null,visible:true,injectContextObject:false,arguments:['ownerId','action'].map(name=>({name,displayName:name,type:'tchmi:general#/definitions/String',description:name,defaultValue:''}))},$schema:'../../Packages/Beckhoff.TwinCAT.HMI.Framework.14.6.3/runtimes/native1.12-tchmi/Schema/FunctionDescription.Schema.json',apiVersion:1,dependencyFiles:[]},null,2));
// The JavaScript source was authored separately with apply_patch.
const js='JavaScript/DetectorPowerAction.js';if(!manifest.some(x=>x.target===path.join(live,js)))manifest.push({target:path.join(live,js),stage:path.join(stage,js),hash:null});

const config=JSON.parse(read('Server/TcHmiSrv/TcHmiSrv.Config.default.json'));
const defs=config.DEFINITIONS.ADS;
const primitive=t=>({$ref:'tchmi:general#/definitions/'+t});
function schema(file){const src=fs.readFileSync(file,'utf8');const props={};for(const m of src.matchAll(/^\s*(\w+)\s*:\s*(\w+)(?:\((\d+)\))?/gm)){
    const [,name,type,len]=m;if(name==='_padding')continue;
    props[name]=type==='STRING'?{type:'string',maxLength:Number(len||80)}:primitive(['BOOL','BIT'].includes(type)?'Boolean':['LREAL','REAL'].includes(type)?'Number':'Integer');
}return{type:'object',additionalProperties:false,properties:props};}
defs['ADS-NOTT_CRYO_PLC.NOTTDPowerCfg']=schema('DUTs/Structures/DetectorPower/T_NOTT_DETECTOR_POWER_CFG.TcDUT');
defs['ADS-NOTT_CRYO_PLC.NOTTDPowerCtrl']=schema('DUTs/Structures/DetectorPower/T_NOTT_DETECTOR_POWER_CTRL.TcDUT');
defs['ADS-NOTT_CRYO_PLC.NOTTDPowerStat']=schema('DUTs/Structures/DetectorPower/T_NOTT_DETECTOR_POWER_STAT.TcDUT');
defs['ADS-NOTT_CRYO_PLC.NOTTFuseCfg']=schema(path.join(lib,'T_FUSE_CFG.TcDUT'));
defs['ADS-NOTT_CRYO_PLC.NOTTFuseBits']=schema(path.join(lib,'T_FUSE_STATUS.TcDUT'));
defs['ADS-NOTT_CRYO_PLC.NOTTFuseStat']=schema(path.join(lib,'T_FUSE_STAT.TcDUT'));
defs['ADS-NOTT_CRYO_PLC.NOTTFuseStat'].properties.stFuseStatus={$ref:'tchmi:server#/definitions/ADS-NOTT_CRYO_PLC.NOTTFuseBits'};
function mapping(name,type,access,engineering){config.SYMBOLS[name]={ACCESS:access,DOMAIN:'ADS',DYNAMIC:true,MAPPING:name.replace(/^ADS\./,'').replaceAll('.','::'),SCHEMA:typeof type==='string'?{$ref:'tchmi:server#/definitions/ADS-NOTT_CRYO_PLC.'+type}:type,USEMAPPING:true};
    for(const [group,g]of Object.entries(config.USERGROUPS)){
        if(!g.SYMBOLS)continue;g.SYMBOLS[name]=access===3&&((engineering&&group==='Engineering')||(!engineering&&['Operation','Engineering'].includes(group)))?3:1;
    }}
mapping(base+'.stat','NOTTDPowerStat',1);mapping(base+'.ctrl','NOTTDPowerCtrl',3,false);mapping(base+'.cfg','NOTTDPowerCfg',3,true);
mapping(fuse+'.stat','NOTTFuseStat',1);mapping(fuse+'.cfg','NOTTFuseCfg',3,true);mapping(fuse+'.i_stStatus','NOTTFuseBits',1);
mapping(fuse+'.stat.bLocal',primitive('Boolean'),3,true);
save('Server/TcHmiSrv/TcHmiSrv.Config.default.json',JSON.stringify(config,null,4)+'\n');
const tchmi=JSON.parse(read('Properties/tchmiconfig.json'));
if(!tchmi.dependencyFiles.some(x=>x.name===js))tchmi.dependencyFiles.push({name:js,description:'Detector power commands',type:'JavaScript'});
if(!tchmi.userFunctions.some(x=>x.url===js))tchmi.userFunctions.push({url:js});
for(const name of ['Overview','Diagnostics','Configuration']){const url='Pages/DetectorPower'+name+'.content';if(Array.isArray(tchmi.content)&&!tchmi.content.some(x=>x.url===url))tchmi.content.push({url});}
// Content registry is named "content" or "contents" depending on the project version.
for(const name of ['Overview','Diagnostics','Configuration']){
    const url='Pages/DetectorPower'+name+'.content';
    if(Array.isArray(tchmi.contents)&&!tchmi.contents.some(x=>x.url===url))tchmi.contents.push({url});
}
save('Properties/tchmiconfig.json',JSON.stringify(tchmi,null,2)+'\n');
let project=read('nott_cryo_hmi.hmiproj');
const newFiles=manifest.filter(x=>x.hash===null).map(x=>path.relative(live,x.target).replaceAll('/','\\')).filter(x=>!x.startsWith('tests\\'));
const entries=newFiles.filter(file=>!project.includes('Include="'+file+'"')).map(file=>'    <Content Include="'+file+'" />').join('\r\n');
if(entries)project=project.replace('</Project>','  <ItemGroup>\r\n'+entries+'\r\n  </ItemGroup>\r\n</Project>');
save('nott_cryo_hmi.hmiproj',project);

let system=fs.readFileSync(path.join(__dirname,'nott_cryo_plc.tsproj'),'utf8');
const marker='<OwnerB Name="TIID^Device 1 (EtherCAT)^-A2^A2-N12_Det_Pwr_Fuse (EL9227-5500)">';
const links='\n\t\t\t\t<Link VarA="PlcTask Outputs^MAIN.nott_detector_power.fuseDetectorPower.q_bSwitch" VarB="OCP Outputs Channel 1^Control^Switch"/>\n\t\t\t\t<Link VarA="PlcTask Outputs^MAIN.nott_detector_power.fuseDetectorPower.q_bReset" VarB="OCP Outputs Channel 1^Control^Reset"/>';
if(!system.includes(marker))throw new Error('Fuse mapping owner missing');if(!system.includes('VarA="PlcTask Outputs^MAIN.nott_detector_power.fuseDetectorPower.q_bSwitch"'))system=system.replace(marker,marker+links);
const meter='<OwnerB Name="TIID^Device 1 (EtherCAT)^-A2^DetectorPowerMeasurement (EL3681)">';
if(!system.includes(meter))throw new Error('Meter mapping owner missing');if(!system.includes('VarA="PlcTask Inputs^MAIN.nott_detector_power.i_nMeterState"'))system=system.replace(meter,meter+'\n\t\t\t\t<Link VarA="PlcTask Inputs^MAIN.nott_detector_power.i_nMeterState" VarB="InfoData^State"/>');
fs.writeFileSync(path.join(__dirname,'nott_cryo_plc.tsproj'),system);
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
console.log('Built detector power page, three tabs, commands, schemas, and source-only I/O links.');
