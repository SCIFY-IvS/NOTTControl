(function (TcHmi) {
    'use strict';
    var base = 'ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power';
    var fuse = base + '.fuseDetectorPower';
    var drafts = new WeakMap();
    function find(root, suffix) {
        if (!root) return null;
        if (root.getId && root.getId().endsWith(suffix)) return root;
        var children = root.getChildren ? root.getChildren() : [];
        for (var i=0;i<children.length;i++) { var c=find(children[i],suffix); if(c)return c; }
        return null;
    }
    function scope(id) {
        var root=TcHmi.Controls.get(id);
        while(root && !find(root,'_Feedback')) root=root.getParent?root.getParent():null;
        return root;
    }
    function failed(r) {
        return r.error!==TcHmi.Errors.NONE || (r.response &&
            ((r.response.error!==undefined && r.response.error!==TcHmi.Errors.NONE) ||
            (r.response.commands||[]).some(function(c){return c.error!==undefined&&c.error!==TcHmi.Errors.NONE;})));
    }
    function access(symbol, value, writing) {
        return new Promise(function(resolve,reject){
            var timer=setTimeout(function(){reject(new Error('PLC response timed out; verify status before retrying.'));},5000);
            var callback=function(r){clearTimeout(timer);if(failed(r))reject(new Error('PLC access failed: '+symbol));else resolve(r.value);};
            if(writing)TcHmi.Symbol.writeEx('%s%'+symbol+'%/s%',value,callback);
            else TcHmi.Symbol.readEx2('%s%'+symbol+'%/s%',callback);
        });
    }
    function read(s){return access(s,undefined,false);}
    function write(s,v){return access(s,v,true);}
    function command(n,reset){return write(base+'.ctrl',{nCommand:n,bExecute:!reset,bResetOvercurrent:!!reset});}
    async function perform(root,action) {
        if(/^Command[1-7]$/.test(action)){
            await command(Number(action.slice(7)),false);return 'Command requested. Check PLC command result and power feedback.';
        }
        if(action==='ResetTrip'){await command(0,true);return 'Trip reset requested. Power ON is a separate action.';}
        if(action==='ApplyLocal'){
            await write(fuse+'.stat.bLocal',find(root,'_Local').getToggleState()==='Active');
            return 'Local/remote ownership change requested.';
        }
        if(action==='LoadConfig'){
            var c=await read(base+'.cfg'),f=await read(fuse+'.cfg'),s=await read(fuse+'.stat');
            find(root,'_Limit').setValue(c.lrCurrentTrip_A);
            find(root,'_StaleTime').setValue(c.tMeasurementTimeout);
            find(root,'_Name').setText(f.sName);
            find(root,'_FuseTimeout').setValue(f.nTimeout);
            find(root,'_Log').setToggleState(f.bLog?'Active':'Normal');
            find(root,'_AutoOp').setToggleState(f.bAutoOp?'Active':'Normal');
            find(root,'_Local').setToggleState(s.bLocal?'Active':'Normal');
            drafts.set(root,{c:c,f:f});return 'Configuration loaded.';
        }
        if(action==='SaveConfig'){
            var saved=drafts.get(root);if(!saved)throw new Error('Load configuration first.');
            var stat=await read(base+'.stat');
            if(stat.bPowerOn!==false||stat.bFuseOperational!==true)throw new Error('Confirmed power OFF and valid fuse feedback required.');
            var limit=find(root,'_Limit').getValue(),stale=find(root,'_StaleTime').getValue(),timeout=find(root,'_FuseTimeout').getValue();
            var name=find(root,'_Name').getText();
            if(!Number.isFinite(limit)||limit<=0||limit>10)throw new Error('Trip limit must be above zero and at most 10 A.');
            if(!Number.isInteger(stale)||stale<100||stale>600000||!Number.isInteger(timeout)||timeout<100||timeout>600000)
                throw new Error('Timeouts must be integer milliseconds between 100 and 600000.');
            if(typeof name!=='string'||name.length<1||name.length>80)throw new Error('Name must contain 1 to 80 characters.');
            var current=await read(base+'.cfg'),native=await read(fuse+'.cfg');
            if(JSON.stringify(current)!==JSON.stringify(saved.c)||JSON.stringify(native)!==JSON.stringify(saved.f))
                throw new Error('Configuration changed elsewhere. Reload before applying.');
            var c={lrCurrentTrip_A:limit,tMeasurementTimeout:stale};
            var f=Object.assign({},native,{sName:name,nTimeout:timeout,
                bLog:find(root,'_Log').getToggleState()==='Active',bAutoOp:find(root,'_AutoOp').getToggleState()==='Active'});
            // Recheck power immediately before writing; the PLC always owns the trip latch.
            stat=await read(base+'.stat');if(stat.bPowerOn!==false||stat.bFuseOperational!==true)throw new Error('Power state changed. Configuration not applied.');
            await write(base+'.cfg',c);await write(fuse+'.cfg',f);
            var a=await read(base+'.cfg'),b=await read(fuse+'.cfg');
            if(JSON.stringify(a)!==JSON.stringify(c)||JSON.stringify(b)!==JSON.stringify(f))throw new Error('Configuration readback differs; reload and inspect both configurations.');
            drafts.set(root,{c:a,f:b});return 'Configuration applied and verified.';
        }
        throw new Error('Unknown detector-power action.');
    }
    function DetectorPowerAction(ownerId,action){
        var root=scope(ownerId);if(!root)return;
        var feedback=find(root,'_Feedback');feedback.setText('Working...');
        perform(root,action).then(function(text){feedback.setText(text);},function(e){feedback.setText(e.message||'Detector-power action failed.');});
    }
    TcHmi.Functions.NOTT=TcHmi.Functions.NOTT||{};
    TcHmi.Functions.NOTT.DetectorPowerAction=DetectorPowerAction;
    TcHmi.Functions.registerFunctionEx('DetectorPowerAction','TcHmi.Functions.NOTT',DetectorPowerAction);
})(TcHmi);
