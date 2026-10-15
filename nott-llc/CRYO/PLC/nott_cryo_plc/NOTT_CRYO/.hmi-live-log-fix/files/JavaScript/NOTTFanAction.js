(function (TcHmi) {
    'use strict';
    var drafts = new WeakMap();
    var busy = new WeakSet();
    var fields = [
        ['MinDuty', 'lrMinRunningDutyPct', 0, 100, false],
        ['MaxDuty', 'lrMaxDutyPct', 0, 100, false],
        ['StartDuty', 'lrStartDutyPct', 0, 100, false],
        ['BoostTime', 'tStartBoost', 0, 60000, true],
        ['RpmWindow', 'tRpmWindow', 100, 60000, true],
        ['StallDelay', 'tStallDelay', 100, 600000, true],
        ['Pulses', 'nPulsesPerRevolution', 1, 100, true],
        ['FullScale', 'nPwmFullScale', 1, 32767, true]
    ];
    function find(control, suffix) {
        if (!control) return null;
        if (control.getId && control.getId().endsWith(suffix)) return control;
        var children = control.getChildren ? control.getChildren() : [];
        for (var i = 0; i < children.length; i++) {
            var result = find(children[i], suffix);
            if (result) return result;
        }
        return null;
    }
    function scope(owner) {
        var control = TcHmi.Controls.get(owner);
        while (control && !find(control, '_Feedback')) {
            control = control.getParent ? control.getParent() : null;
        }
        return control;
    }
    function feedback(root, message) {
        var target = find(root, '_Feedback');
        if (target) target.setText(message);
    }
    function read(symbol) {
        return new Promise(function (resolve, reject) {
            var timer = setTimeout(function () { reject(new Error('PLC read timed out.')); }, 5000);
            TcHmi.Symbol.readEx2('%s%' + symbol + '%/s%', function (result) {
                clearTimeout(timer);
                if (failed(result) || result.value === undefined || result.value === null) {
                    reject(new Error('PLC symbol unavailable or access denied: ' + symbol));
                } else resolve(result.value);
            });
        });
    }
    function write(symbol, value) {
        return new Promise(function (resolve, reject) {
            var timer = setTimeout(function () { reject(new Error('Write response timed out; verify PLC status before retrying.')); }, 5000);
            TcHmi.Symbol.writeEx('%s%' + symbol + '%/s%', value, function (result) {
                clearTimeout(timer);
                if (failed(result)) reject(new Error('PLC write failed or access denied.'));
                else resolve();
            });
        });
    }
    function failed(result) {
        if (result.error !== TcHmi.Errors.NONE) return true;
        var response = result.response;
        if (!response) return false;
        if (response.error !== undefined && response.error !== TcHmi.Errors.NONE) return true;
        return (response.commands || []).some(function (command) {
            return command.error !== undefined && command.error !== TcHmi.Errors.NONE;
        });
    }
    function setEditors(root, enabled) {
        fields.forEach(function (field) { var c = find(root, '_' + field[0]); if (c) c.setIsEnabled(enabled); });
        ['InvertPwm', 'InvertTach', 'Apply'].forEach(function (id) { var c = find(root, '_' + id); if (c) c.setIsEnabled(enabled); });
    }
    function validate(cfg) {
        fields.forEach(function (field) {
            var n = cfg[field[1]];
            if (typeof n !== 'number' || !Number.isFinite(n) || n < field[2] || n > field[3] ||
                (field[4] && !Number.isInteger(n))) throw new Error('Invalid value: ' + field[1]);
        });
        if (cfg.lrMinRunningDutyPct <= 0 || cfg.lrMinRunningDutyPct > cfg.lrMaxDutyPct)
            throw new Error('Minimum running duty must be above zero and no greater than maximum duty.');
        if (cfg.lrStartDutyPct < cfg.lrMinRunningDutyPct || cfg.lrStartDutyPct > cfg.lrMaxDutyPct)
            throw new Error('Startup duty must lie between minimum and maximum duty.');
        if (cfg.tStallDelay < cfg.tStartBoost)
            throw new Error('Stall delay must be at least the startup boost duration.');
        if (typeof cfg.bInvertPwmOutput !== 'boolean' || typeof cfg.bInvertTachInput !== 'boolean')
            throw new Error('Invalid polarity setting.');
        return cfg;
    }
    function same(a, b) {
        return fields.every(function (f) { return a[f[1]] === b[f[1]]; }) &&
            a.bInvertPwmOutput === b.bInvertPwmOutput && a.bInvertTachInput === b.bInvertTachInput;
    }
    function displayDraft(root, cfg) {
        fields.forEach(function (f) { find(root, '_' + f[0]).setValue(cfg[f[1]]); });
        find(root, '_InvertPwm').setToggleState(cfg.bInvertPwmOutput ? 'Active' : 'Normal');
        find(root, '_InvertTach').setToggleState(cfg.bInvertTachInput ? 'Active' : 'Normal');
        drafts.set(root, Object.assign({}, cfg));
    }
    function editorDraft(root) {
        var cfg = {};
        fields.forEach(function (f) { cfg[f[1]] = find(root, '_' + f[0]).getValue(); });
        cfg.bInvertPwmOutput = find(root, '_InvertPwm').getToggleState() === 'Active';
        cfg.bInvertTachInput = find(root, '_InvertTach').getToggleState() === 'Active';
        return validate(cfg);
    }
    async function perform(root, fan, box, action) {
        if (typeof fan !== 'string' || typeof box !== 'string' || fan !== box + '.fan' ||
            !box.startsWith('ADS.')) throw new Error('Invalid fan/coordinator symbol parameters.');
        // A stop request does not depend on status telemetry being readable.
        if (action === 'Disable') {
            await write(box + '.ctrl::bEnable', false);
            feedback(root, 'Stop requested; verify fan and valve status.');
            return;
        }
        var status = await read(box + '.stat');
        if (action === 'Refresh') {
            var ctrl = await read(box + '.ctrl');
            var input = find(root, '_Demand');
            if (input) input.setValue(ctrl.lrManualFanPct);
            feedback(root, 'Connected');
            return;
        }
        if (action === 'Load') {
            setEditors(root, false);
            var cfg = validate(await read(fan + '.cfg'));
            displayDraft(root, cfg);
            var stopped = status.bActive === false && (await read(fan + '::stat::bActive')) === false;
            setEditors(root, stopped);
            feedback(root, stopped ? 'Configuration loaded' : 'Cooling active. Configuration is read-only.');
            return;
        }
        if (action === 'Apply') {
            setEditors(root, false);
            if (status.bActive !== false || (await read(fan + '::stat::bActive')) !== false)
                throw new Error('Disable thermal box cooling before applying fan configuration.');
            var saved = drafts.get(root);
            if (!saved) throw new Error('Load configuration before applying.');
            var candidate = editorDraft(root);
            var current = validate(await read(fan + '.cfg'));
            if (!same(saved, current)) throw new Error('Configuration changed elsewhere. Cancel to reload.');
            // Write one configuration structure, never the whole fan FB.
            await write(fan + '.cfg', candidate);
            var applied = validate(await read(fan + '.cfg'));
            if (!same(candidate, applied)) throw new Error('Configuration readback differs; reload and inspect.');
            displayDraft(root, applied);
            setEditors(root, true);
            feedback(root, 'Configuration applied and verified');
            return;
        }
        if (action === 'Enable') {
            if (status.bPermitStart !== true) throw new Error('Thermal box start permission is not granted.');
            await write(box + '.ctrl::bEnable', true);
        } else if (action === 'Auto') {
            if (await read(box + '.autoCommissioned') !== true)
                throw new Error('AUTO commissioning approval is required.');
            await write(box + '.ctrl::eCtrlMode', 1);
        } else if (action === 'Manual') {
            await write(box + '.ctrl::eCtrlMode', 2);
        } else if (action === 'SetDemand') {
            if (status.bManual !== true || status.bSensorFaultHold === true)
                throw new Error('Manual fan demand is unavailable in AUTO or sensor-fault hold.');
            var demand = find(root, '_Demand').getValue();
            if (typeof demand !== 'number' || !Number.isFinite(demand) || demand < 0 || demand > 100)
                throw new Error('Fan demand must be between 0 and 100 percent.');
            await write(box + '.ctrl::lrManualFanPct', demand);
        } else throw new Error('Unknown fan action.');
        feedback(root, 'Request sent; operating status is reported by the PLC.');
    }
    function NOTTFanAction(ownerId, fanSymbol, controlSymbol, action) {
        var root = scope(ownerId);
        if (!root || busy.has(root)) return;
        busy.add(root);
        feedback(root, 'Working...');
        perform(root, fanSymbol, controlSymbol, action).catch(function (error) {
            if (action === 'Load' || action === 'Apply') setEditors(root, false);
            feedback(root, error.message || 'Fan action failed.');
        }).finally(function () { busy.delete(root); });
    }
    TcHmi.Functions.NOTT = TcHmi.Functions.NOTT || {};
    TcHmi.Functions.NOTT.NOTTFanAction = NOTTFanAction;
    TcHmi.Functions.registerFunctionEx('NOTTFanAction', 'TcHmi.Functions.NOTT', NOTTFanAction);
})(TcHmi);

