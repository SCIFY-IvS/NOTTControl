const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'manifest.json'),'utf8'));
const names=['outside','inside','inlet','heatexchanger_inlet'].map(n=>'t_thermal_box_'+n);
const sources=manifest.map(item=>({...item,before:fs.readFileSync(item.target,'utf8'),after:fs.readFileSync(item.stage,'utf8')}));
for(const s of sources){assert(!/\bt_thermal_box_[1-4]\b/.test(s.after),s.target);if(s.target.endsWith('.json'))JSON.parse(s.after);}
const enums=sources.find(s=>s.target.endsWith('E_ALL_NOTT_TEMPERATURES.TcDUT')).after;
names.forEach((n,i)=>assert(new RegExp(n+'\\s*:= '+(22+i)+',').test(enums),'Stable enumeration: '+n));
const sensors=sources.find(s=>s.target.endsWith('FB_NOTT_TEMPERATURES.TcPOU')).after;
names.forEach(n=>{
    assert(new RegExp(n+':\\s*FB_METIS_TEMPERATURE').test(sensors));
    assert(sensors.includes("in_sName:='"+n+"'"));
    assert(sensors.includes('ADR('+n+')'));
});
const io=sources.find(s=>s.target.endsWith('.tsproj'));
const links=text=>[...text.matchAll(/<Link\s+VarA="([^"]+)"\s+VarB="([^"]+)"\s*\/>/g)].map(m=>({a:m[1],b:m[2]})).filter(l=>l.a.includes('nott_temp.t_thermal_box_'));
const old=links(io.before),updated=links(io.after);assert.equal(updated.length,old.length);
for(const l of old){const a=l.a.replace(/\bt_thermal_box_([1-4])\b/g,(_,i)=>names[Number(i)-1]);assert(updated.some(n=>n.a===a&&n.b===l.b),'Unchanged physical I/O: '+a);}
assert.equal(old.filter(l=>/t_thermal_box_[1-4]\./.test(l.a)).length,8);
const fan=fs.readFileSync(path.join(root,'POUs/Devices/Fans/FB_NOTT_FAN.TcPOU'),'utf8');
const st=fan.match(/<Implementation>\s*<ST><!\[CDATA\[([\s\S]*?)\]\]>/)[1];
assert.equal((st.match(/cfg\.lrMinRunningDutyPct/g)||[]).length,1,'Threshold is tach-only');
const branch=st.match(/ELSE\s+IF lrDemand <= 0\.0 THEN([\s\S]*?)END_IF\s+END_IF\s+END_IF/)[0];
assert(!branch.includes('lrMinRunningDutyPct'));
// Evaluate the exact steady-state ST branch, not the startup or tach logic.
const executable=branch.replace(/^ELSE\s+/,'').replace(/ELSIF (.*?) THEN/g,'} else if ($1) {').replace(/IF (.*?) THEN/g,'if ($1) {').replace(/ELSE/g,'} else {').replace(/END_IF/g,'}').replace(/:=/g,'=').replace(/cfg\.lrMaxDutyPct/g,'max').replace(/stat\.lrDutyPct/g,'result');
// Use the complete IF/ELSIF/ELSE block up to its own END_IF.
const body=executable.replace(/\}\s*\}\s*$/,'');
const evaluate=new Function('lrDemand','max','let result=0;'+body+';return result;');
for(const demand of [0,0.1,2,4.9,5,20,100])assert.equal(evaluate(demand,100),demand);
assert.equal(evaluate(90,70),70);
assert(st.includes('stat.lrDutyPct := cfg.lrStartDutyPct;'));
console.log('PASS: sensor declarations/names/pointers, stable enum indices, eight unchanged physical channel links, valid HMI JSON, no minimum-duty clamp, direct 2% demand and preserved maximum/startup behavior.');
