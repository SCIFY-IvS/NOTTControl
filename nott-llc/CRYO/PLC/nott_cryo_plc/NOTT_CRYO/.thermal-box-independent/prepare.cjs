const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = 'C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const files = ['JavaScript/NOTTFanAction.js', 'JavaScript/NOTTFanAction.function.json',
    'Pages/ThermalBox.content', 'UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateOperate.usercontrol',
    'UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplateStatus.usercontrol',
    'Server/TcHmiSrv/TcHmiSrv.Config.default.json', 'tests/NOTTFanAction.test.cjs'];
const manifest = files.map(file => {
    const original = fs.readFileSync(path.join(root, file));
    const dest = path.join(__dirname, 'files', file);
    fs.mkdirSync(path.dirname(dest), {recursive:true});
    fs.copyFileSync(path.join(root, file), dest);
    return {file, hash:crypto.createHash('sha256').update(original).digest('hex')};
});
fs.writeFileSync(path.join(__dirname, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log('Staged current HMI files with concurrency guards.');
