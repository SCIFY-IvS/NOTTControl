const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = 'C:/Users/u0149673/NOTT/NOTTControl/nott-llc/CRYO/HMI/nott_cryo_hmi/nott_cryo_hmi';
const stage = path.join(__dirname, 'files');
const changes = [];
function edit(file, transform) {
    const original = fs.readFileSync(path.join(root, file), 'utf8');
    const updated = transform(original);
    if (updated === original) throw new Error('No change: ' + file);
    const target = path.join(stage, file);
    fs.mkdirSync(path.dirname(target), {recursive:true});
    fs.writeFileSync(target, updated);
    changes.push({file, hash:crypto.createHash('sha256').update(original).digest('hex')});
}
const config = JSON.parse(fs.readFileSync(path.join(root, 'Server/TcHmiSrv/TcHmiSrv.Config.default.json'), 'utf8'));
const compressor = 'ADS-NOTT_CRYO_PLC.ESO_Cryo_HMI_Library.FB_HMI_CRYO_HELIUM_COMPRESSOR';
const alarms = 'ADS-NOTT_CRYO_PLC.ESO_LDC_Cryo_Library.T_CRYO_ALARMS-ShowRecursively';
for (const name of [compressor, alarms]) if (!config.DEFINITIONS.ADS[name]) throw new Error('Missing schema: ' + name);
for (const file of [
    'UserControls/Controls/HeliumCompressor.usercontrol.json',
    'UserControls/Faceplates/Common/HeliumCompressorOnOffAutomaticManual.usercontrol.json',
    'UserControls/Faceplates/HeliumCompressor/HeliumCompressorStatusTab.usercontrol.json',
    'UserControls/Faceplates/HeliumCompressor/HeliumCompressorFaceplateOperateTab.usercontrol.json',
    'UserControls/Faceplates/HeliumCompressor/HeliumCompressorFaceplate.usercontrol.json'
]) edit(file, s => s.replaceAll('tchmi:server#/definitions/PLC1.ESO_Cryo_HMI_Library.FB_HMI_CRYO_HELIUM_COMPRESSOR', 'tchmi:server#/definitions/' + compressor));
edit('UserControls/Faceplates/Common/NoAlarmWarningConfirm.usercontrol.json', s => s.replaceAll('tchmi:server#/definitions/PLC1.ESO_LDC_Cryo_Library.T_CRYO_ALARMS', 'tchmi:server#/definitions/' + alarms));
edit('JavaScript/NOTTFanAction.js', s => s.replace("TcHmi.Functions.registerFunction('NOTTFanAction', NOTTFanAction);", "TcHmi.Functions.NOTT = TcHmi.Functions.NOTT || {};\r\n    TcHmi.Functions.NOTT.NOTTFanAction = NOTTFanAction;\r\n    TcHmi.Functions.registerFunctionEx('NOTTFanAction', 'TcHmi.Functions.NOTT', NOTTFanAction);"));
edit('JavaScript/NOTTFanAction.function.json', s => s.replace('"namespace": null', '"namespace": "TcHmi.Functions.NOTT"'));
for (const suffix of ['Operate', 'Configuration']) edit('UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplate' + suffix + '.usercontrol', s => s.replaceAll('"fn": "TcHmi.Functions.NOTTFanAction"', '"fn": "TcHmi.Functions.NOTT.NOTTFanAction"'));
edit('Pages/EvacuateSequence.content', s => {
    for (const tail of ['evac.stat.sStatus', 'ctrl.bEnable_Evac']) {
        const current = 'ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.' + tail;
        if (!config.SYMBOLS[current]) throw new Error('Missing mapped symbol: ' + current);
        s = s.replaceAll('PLC1.MAIN.pds_cryo_ctrl.' + tail, current);
    }
    return s;
});
edit('tests/NOTTFanAction.test.cjs', s => s.replace('Functions:{registerFunction:(_,fn)=>action=fn}', "Functions:{registerFunctionEx:(name,namespace,fn)=>{assert.equal(name,'NOTTFanAction');assert.equal(namespace,'TcHmi.Functions.NOTT');action=fn;}}"));
for (const {file} of changes) {
    const text = fs.readFileSync(path.join(stage, file), 'utf8');
    if (file.endsWith('.json')) JSON.parse(text);
    for (const match of text.matchAll(/<script\s[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) JSON.parse(match[1]);
}
fs.writeFileSync(path.join(__dirname, 'manifest.json'), JSON.stringify(changes, null, 2));
console.log('Prepared and syntax-validated ' + changes.length + ' HMI files.');
