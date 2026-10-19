const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const stage=path.join(__dirname,'files');
const source=fs.readFileSync(path.join(stage,'JavaScript/NOTTHeaderStatus.js'),'utf8');
const controls={};for(const name of ['ThermalBox','DetectorPower','Events']){
    const classes=new Set();controls[name]={classes,getId:()=> 'Header_NavigationButton_'+name,
        getElement:()=>({toggleClass:(c,on)=>on?classes.add(c):classes.delete(c)}),setTooltip(t){this.tooltip=t;}};
}
const root={getId:()=> 'Header',getChildren:()=>Object.values(controls)};
const subscriptions=[],unsubscribed=[],handlers=new Map();
const TcHmi={Errors:{NONE:0},Controls:{get:()=>root},Functions:{registerFunctionEx(){}},
    EventProvider:{register(name,cb){handlers.set(name,cb);return()=>handlers.delete(name);}},
    Server:{Events:{Type:{Alarm:1},ConfirmationState:{WaitForConfirmation:2}},
        subscribeEx(commands,interval,options,callback){subscriptions.push({commands,interval,callback});return subscriptions.length;},
        unsubscribeEx(id){unsubscribed.push(id);}}};
vm.runInNewContext(source,{TcHmi,WeakMap,Array});
const action=TcHmi.Functions.NOTT.NOTTHeaderStatus;
action('Header','Attach');assert.equal(subscriptions.length,1);
const sub=subscriptions[0];assert.equal(sub.interval,1000);
const query=sub.commands.find(c=>c.symbol==='ListEvents');assert.equal(query.limit,0);
assert.equal(query.filter[0].value,1);assert.equal(query.filter[2].value,2);
assert(sub.commands.every(c=>!Object.hasOwn(c,'writeValue')));
const [thermal,detector,bits,fuse]=sub.commands.map(c=>c.symbol);
const good={};good[thermal]={bActive:true,bAlarm:false};good[detector]={bPowerOn:true,bAlarm:false,bFuseOperational:true};good[bits]={};good[fuse]={nErrorCode:0};
const respond=(values,count=0,extra=[])=>subscriptions.at(-1).callback({error:0,response:{commands:[...Object.entries(values).map(([symbol,readValue])=>({symbol,readValue})),{symbol:'ListEvents',maxEntries:count},...extra]}});
const has=(name,kind)=>controls[name].classes.has('nott-status-'+kind);
respond(good);assert(has('ThermalBox','active'));assert(has('DetectorPower','active'));assert(!has('Events','alarm'));
respond({[thermal]:{bActive:true,bAlarm:true}},2);assert(has('ThermalBox','alarm'));assert(!has('ThermalBox','active'));assert(has('Events','alarm'));
for(const fault of ['bTripped','bShortCircuit','bOverload','bHardwareProtection','bOvervoltage','bUndervoltage','bError','bTxPDOState']){
    respond({...good,[bits]:{[fault]:true}});assert(has('DetectorPower','alarm'),fault);assert(!has('DetectorPower','active'));
}
respond({...good,[detector]:{bPowerOn:true,bAlarm:true,bFuseOperational:true}});assert(has('DetectorPower','alarm'));
respond({...good,[fuse]:{nErrorCode:1}});assert(has('DetectorPower','alarm'));
respond(good,0);assert(has('DetectorPower','active'));assert(!has('Events','alarm'));assert.equal(controls.Events.tooltip,'Unconfirmed alarms: 0');
respond({...good,[thermal]:{bActive:false,bAlarm:false},[detector]:{bPowerOn:false,bAlarm:false,bFuseOperational:true}});assert(!has('ThermalBox','active'));assert(!has('DetectorPower','active'));
respond(good,1,[{symbol:bits,error:1}]);assert(!has('DetectorPower','active'));assert(has('Events','alarm'));
subscriptions.at(-1).callback({error:1});assert(Object.values(controls).every(c=>c.classes.size===0));
respond(good,2);handlers.get('onServerNotReady')();assert(Object.values(controls).every(c=>c.classes.size===0));
handlers.get('onServerReady')();assert.equal(subscriptions.length,2);assert.equal(unsubscribed[0],1);
respond(good,1);action('Header','Detach');assert.equal(unsubscribed.at(-1),2);assert.equal(handlers.size,0);
sub.callback({error:0,response:{commands:[{symbol:thermal,readValue:{bActive:true,bAlarm:true}}]}});assert(Object.values(controls).every(c=>c.classes.size===0));
action('Header','Attach');action('Header','Attach');assert.equal(unsubscribed.at(-1),3);action('Header','Detach');
for(const file of ['Pages/Header.content','Pages/ThermalBox.content','Pages/DetectorPower.content']){
    const text=fs.readFileSync(path.join(stage,file),'utf8');const ids=[...text.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
    assert.equal(ids.length,new Set(ids).size,file);
    for(const match of text.matchAll(/<script\b[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/g))JSON.parse(match[1]);
}
assert(fs.readFileSync(path.join(stage,'Pages/ThermalBox.content'),'utf8').includes('thermal_box_ctrl.stat::bActive%/s%'));
assert(fs.readFileSync(path.join(stage,'Pages/DetectorPower.content'),'utf8').includes('nott_detector_power.stat::bPowerOn%/s%'));
console.log('PASS: active/inactive LEDs and navigation bindings, alarm priority, eight raw fuse faults, fuse error, count-only unconfirmed alarms, error/disconnect neutral state, reconnect, detach cleanup, stale-callback protection and embedded JSON. No live services accessed.');
