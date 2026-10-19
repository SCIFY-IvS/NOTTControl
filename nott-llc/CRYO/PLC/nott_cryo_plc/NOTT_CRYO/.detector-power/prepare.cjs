const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const hmi='C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const files=['Pages/DetectorPower.content','Properties/tchmiconfig.json','nott_cryo_hmi.hmiproj','Server/TcHmiSrv/TcHmiSrv.Config.default.json'];
const manifest=files.map(file=>{const target=path.join(hmi,file),data=fs.readFileSync(target);const stage=path.join(__dirname,'files',file);fs.mkdirSync(path.dirname(stage),{recursive:true});fs.writeFileSync(stage,data);return{target,stage,hash:crypto.createHash('sha256').update(data).digest('hex')};});
const target=path.resolve('../nott_cryo_plc.tsproj'),data=fs.readFileSync(target);fs.writeFileSync(path.join(__dirname,'nott_cryo_plc.tsproj'),data);
manifest.push({target,stage:path.join(__dirname,'nott_cryo_plc.tsproj'),hash:crypto.createHash('sha256').update(data).digest('hex')});
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
