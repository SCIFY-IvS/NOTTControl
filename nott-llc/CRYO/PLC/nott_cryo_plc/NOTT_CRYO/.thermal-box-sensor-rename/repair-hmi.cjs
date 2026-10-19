const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json'),'utf8'));
const item=manifest.find(m=>m.target.endsWith('TcHmiSrv.Config.default.json'));
const names=['outside','inside','inlet','heatexchanger_inlet'].map(s=>'t_thermal_box_'+s);
const text=fs.readFileSync(item.target,'utf8');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const original=JSON.parse(text),reference=JSON.parse(fs.readFileSync(item.stage,'utf8'));
const rename=s=>s.replace(/\bt_thermal_box_([1-4])\b/g,(_,n)=>names[Number(n)-1]);
function walk(value){
    if(typeof value==='string')return rename(value);
    if(Array.isArray(value))return value.map(walk);
    if(!value||typeof value!=='object')return value;
    const result={};for(const [key,v] of Object.entries(value)){
        const next=rename(key);assert(!Object.hasOwn(result,next),'Conflicting renamed key: '+next);
        result[next]=walk(v);
    }return result;
}
const repaired=walk(original);
for(const name of names){
    const key='ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.nott_temp.'+name;
    assert(reference.SYMBOLS[key],'Missing reference mapping: '+key);
    if(!repaired.SYMBOLS[key])repaired.SYMBOLS[key]=reference.SYMBOLS[key];
    assert.equal(repaired.SYMBOLS[key].MAPPING,'NOTT_CRYO_PLC::MAIN::nott_cryo_ctrl::nott_temp::'+name);
    for(const [group,g] of Object.entries(repaired.USERGROUPS)){
        const permission=reference.USERGROUPS[group]?.SYMBOLS?.[key];
        if(g.SYMBOLS&&g.SYMBOLS[key]===undefined&&permission!==undefined)g.SYMBOLS[key]=permission;
    }
    assert(repaired.DEFINITIONS.ADS['ADS-NOTT_CRYO_PLC.FB_NOTT_TEMPERATURES'].properties[name]);
    function checkRefs(v){
        if(!v||typeof v!=='object')return;
        if(typeof v.$ref==='string'&&v.$ref.startsWith('tchmi:server#/definitions/ADS-')){
            const id=v.$ref.split('/definitions/')[1];assert(repaired.DEFINITIONS.ADS[id],'Unresolved schema: '+id);
        }
        Object.values(v).forEach(checkRefs);
    }
    checkRefs(repaired.SYMBOLS[key].SCHEMA);
}
// Unrelated mappings and definition entries must be preserved exactly.
for(const [k,v] of Object.entries(original.SYMBOLS))if(!/\bt_thermal_box_[1-4]\b/.test(k))assert.deepEqual(repaired.SYMBOLS[k],walk(v));
const output=JSON.stringify(repaired,null,4)+'\n';assert(!/\bt_thermal_box_[1-4]\b/.test(output));
const stage=path.join(__dirname,'repaired-TcHmiSrv.Config.default.json');
fs.writeFileSync(stage,output);
fs.writeFileSync(path.join(__dirname,'repair-manifest.json'),JSON.stringify({target:item.target,stage,hash:hash(text)},null,2));
console.log('PASS: prepared current-config repair; four mappings, parent schema, ADS type references and permissions verified; unrelated mappings preserved.');
