const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root='C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const files=['JavaScript/NOTTFanAction.js','Pages/ThermalBox.content','tests/NOTTFanAction.test.cjs','UserControls/Faceplates/NOTT/Fan/README.md'];
const manifest=files.map(file=>{const bytes=fs.readFileSync(path.join(root,file));const dest=path.join(__dirname,'files',file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,bytes);return{file,hash:crypto.createHash('sha256').update(bytes).digest('hex')};});
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
