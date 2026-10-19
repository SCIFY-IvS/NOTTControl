const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const plc=path.resolve(__dirname,'..');
const hmi=path.resolve(plc,'../../../HMI/nott_cryo_hmi/nott_cryo_hmi');
const names=['t_thermal_box_outside','t_thermal_box_inside','t_thermal_box_inlet','t_thermal_box_heatexchanger_inlet'];
const rename=s=>s.replace(/\bt_thermal_box_([1-4])\b/g,(_,n)=>names[Number(n)-1]);
const files=[
    [plc,'DUTs/Enumerations/TempVote/E_ALL_NOTT_TEMPERATURES.TcDUT'],
    [plc,'POUs/Devices/Temperatures/FB_NOTT_TEMPERATURES.TcPOU'],
    [plc,'POUs/Devices/ThermalBox/FB_NOTT_THERMAL_BOX_CONTROL.TcPOU'],
    [plc,'docs/thermal_box_control.md'],
    [path.dirname(plc),'nott_cryo_plc.tsproj'],
    [hmi,'Pages/ThermalBox.content'],
    [hmi,'UserControls/NOTT/CryogenicController_usercontrol_Temperatures.usercontrol'],
    [hmi,'Server/TcHmiSrv/TcHmiSrv.Config.default.json'],
    [hmi,'UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateConfiguration.usercontrol'],
    [hmi,'JavaScript/NOTTFanAction.js']
];
function transformJson(value){
    if(typeof value==='string')return rename(value);
    if(Array.isArray(value))return value.map(transformJson);
    if(value&&typeof value==='object'){
        const result={};for(const [k,v] of Object.entries(value)){
            const key=rename(k);if(Object.hasOwn(result,key))throw Error('Duplicate renamed JSON key: '+key);
            result[key]=transformJson(v);
        }return result;
    }return value;
}
const manifest=[];
for(const [root,file] of files){
    const target=path.join(root,file),original=fs.readFileSync(target,'utf8');
    let updated=file.endsWith('.json')?JSON.stringify(transformJson(JSON.parse(original)),null,4)+'\n':rename(original);
    if(file==='Pages/ThermalBox.content')updated=updated.replace('data-tchmi-text="Coolant inlet"','data-tchmi-text="Thermal box inlet"').replace('data-tchmi-text="Coolant outlet"','data-tchmi-text="Heat exchanger inlet"');
    if(file.endsWith('NOTTFanFaceplateConfiguration.usercontrol'))updated=updated.replace('Minimum running duty [%]','Tach monitoring threshold [%]');
    if(file==='docs/thermal_box_control.md')updated=updated.replace('The shared FB_NOTT_CTRL_TEMPERATURE and its cryostat heater users are unchanged.','The shared FB_NOTT_CTRL_TEMPERATURE defaults to heating action; both thermal-box\nloops explicitly select cooling action with positive gains.').replace('t_thermal_box_inlet: coolant inlet','t_thermal_box_inlet: thermal box inlet').replace('t_thermal_box_heatexchanger_inlet: coolant outlet','t_thermal_box_heatexchanger_inlet: heat exchanger inlet').replace('nonnegative cooling','nonpositive cooling');
    if(file==='docs/thermal_box_control.md')updated=updated.replaceAll('negative Kp','positive Kp').replaceAll('negative gains','positive gains').replaceAll('nonnegative gain','nonpositive gain')+'\n## Fan demand and sensor naming\n\nAfter the configured startup boost, fan duty follows the PID/manual demand\nwithout a minimum-duty floor, subject to the existing maximum-duty limit.\nThe legacy cfg.lrMinRunningDutyPct field now only sets the tach alarm monitoring\nthreshold; it does not raise the PWM demand. Tach/RPM logic is otherwise unchanged.\n\nSensor enumeration values 22..25 and physical RTD channels 1..4 are unchanged.\nPLC lookup names, I/O symbol paths and HMI mappings use the descriptive names.\nExisting saved sensor configurations or external clients using numbered names\nneed migration/rebinding before deployment; no running PLC files were changed.\nLegacy coordinator status fields named CoolantIn and CoolantOut still refer to\nthe thermal-box inlet and heat-exchanger inlet respectively. Their diagnostics\nand thresholds are unchanged by this naming update.\n';
    if(updated===original&&file!=='JavaScript/NOTTFanAction.js')throw Error('No expected changes: '+target);
    const stage=path.join(__dirname,'staged',String(manifest.length)+'-'+path.basename(file));
    fs.mkdirSync(path.dirname(stage),{recursive:true});fs.writeFileSync(stage,updated);
    manifest.push({target,stage,hash:crypto.createHash('sha256').update(Buffer.from(original)).digest('hex')});
}
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
console.log('Prepared '+manifest.length+' source files; no target files changed.');
