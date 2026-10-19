const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../../../HMI/nott_cryo_hmi/nott_cryo_hmi');
const files=['JavaScript/NOTTFanAction.js','JavaScript/DetectorPowerAction.js','Pages/ThermalBox.content','tests/NOTTFanAction.test.cjs'];
const manifest=files.map(file=>{
    const target=path.join(root,file),stage=path.join(__dirname,'files',file),bytes=fs.readFileSync(target);
    fs.mkdirSync(path.dirname(stage),{recursive:true});fs.writeFileSync(stage,bytes);
    return{target,stage,hash:crypto.createHash('sha256').update(bytes).digest('hex')};
});
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
console.log('Prepared current HMI sources without changing the targets.');
