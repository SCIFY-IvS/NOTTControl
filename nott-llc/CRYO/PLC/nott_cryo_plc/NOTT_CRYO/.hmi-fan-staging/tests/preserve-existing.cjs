'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const stage=path.resolve(__dirname,'..'),hmi=process.argv[2];
const before=JSON.parse(fs.readFileSync(path.join(hmi,'Server/TcHmiSrv/TcHmiSrv.Config.default.json'),'utf8'));
const after=JSON.parse(fs.readFileSync(path.join(stage,'Server/TcHmiSrv/TcHmiSrv.Config.default.json'),'utf8'));
for(const [key,value]of Object.entries(before)){
    if(!['DEFINITIONS','SYMBOLS','USERGROUPS'].includes(key))assert.deepEqual(after[key],value,'Unrelated config changed: '+key);
}
for(const [domain,defs]of Object.entries(before.DEFINITIONS)){
    for(const [name,def]of Object.entries(defs)){
        if(name!=='ADS-NOTT_CRYO_PLC.T_NOTT_FAN_CFG')assert.deepEqual(after.DEFINITIONS[domain][name],def,'Existing definition changed: '+name);
    }
}
const fan='ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl.fan';
for(const [name,symbol]of Object.entries(before.SYMBOLS)){
    const expected=structuredClone(symbol);
    if(name===fan)expected.ACCESS=1;
    assert.deepEqual(after.SYMBOLS[name],expected,'Existing symbol changed: '+name);
}
for(const [name,group]of Object.entries(before.USERGROUPS)){
    for(const [key,value]of Object.entries(group)){
        if(key!=='SYMBOLS')assert.deepEqual(after.USERGROUPS[name][key],value);
        else for(const [symbol,access]of Object.entries(value))assert.equal(after.USERGROUPS[name].SYMBOLS[symbol],access,'Existing permission changed: '+symbol);
    }
}
const norm=s=>s.replace(/\r\n/g,'\n');
const pageBefore=norm(fs.readFileSync(path.join(hmi,'Pages/ThermalBox.content'),'utf8'));
const pageAfter=norm(fs.readFileSync(path.join(stage,'Pages/ThermalBox.content'),'utf8'));
assert.equal(pageAfter.slice(0,pageAfter.indexOf('<div id="ThermalBox_HeatExchanger"')),pageBefore.slice(0,pageBefore.lastIndexOf('</div>')),'Existing content or bindings changed');
const projectBefore=norm(fs.readFileSync(path.join(hmi,'nott_cryo_hmi.hmiproj'),'utf8'));
let projectAfter=norm(fs.readFileSync(path.join(stage,'nott_cryo_hmi.hmiproj'),'utf8'));
projectAfter=projectAfter.replace(/    <Content Include="(?:UserControls\\(?:Controls\\NOTT\\Fan|Faceplates\\NOTT\\Fan)\\NOTTFan[^"]+|Images\\NOTT\\(?:FanRunning|FanStopped|HeatExchanger)\.svg|JavaScript\\NOTTFanAction[^"]+)">\n[\s\S]*?    <\/Content>\n/g,'');
assert.equal(projectAfter.trimEnd(),projectBefore.trimEnd(),'Existing project content changed');
console.log('PASS: all existing HMI page content, project entries, server settings, definitions, symbol mappings and permissions preserved except the intended read-only fan parent mapping.');

