const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const file='UserControls/Faceplates/NOTT/Fan/README.md';
const root='C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const original=fs.readFileSync(path.join(root,file));
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json'),'utf8'));
manifest.push({file,hash:crypto.createHash('sha256').update(original).digest('hex')});
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
