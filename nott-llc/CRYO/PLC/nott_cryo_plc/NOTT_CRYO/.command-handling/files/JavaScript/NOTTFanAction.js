(function (TcHmi) {
    'use strict';
    var drafts = new WeakMap();
    var busy = new WeakSet();
    var versions = new WeakMap();
    var stopEpochs = new Map();
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
        while (control) {
            if (find(control, '_Feedback')) return control;
            var type = control.getType ? control.getType() : '';
            if (type === 'TcHmi.Controls.System.TcHmiContent' ||
                type === 'TcHmi.Controls.System.TcHmiUserControl') return control;
            var parent = control.getParent ? control.getParent() : null;
            if (!parent) return control;
            control = parent;
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
        if (cfg.lrMinRunningDutyPct <= 0)
            throw new Error('Tach monitoring threshold must be above zero and at most 100%.');
        if (cfg.lrStartDutyPct <= 0 || cfg.lrStartDutyPct > cfg.lrMaxDutyPct)
            throw new Error('Startup duty must be above zero and no greater than maximum duty.');
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
    async function perform(root, fan, box, action, isCurrent) {
        function send(symbol, value) {
            if (!isCurrent()) throw new Error('Request superseded by Stop.');
            return write(symbol, value);
        }
        function report(message) { if (isCurrent()) feedback(root, message); }
        async function confirmRoutine(enabled) {
            for (var attempt = 0; attempt < 20; attempt++) {
                if (!isCurrent()) return;
                var actual = await read(box + '.ctrl');
                var state = await read(box + '.stat');
                if (actual.bEnable === enabled && state.bActive === enabled &&
                    (enabled || actual.bStop === false)) {
                    report(enabled ? 'Thermal box enabled (PLC confirmed).' : 'Thermal box disabled (PLC confirmed).');
                    return;
                }
                if (enabled && state.bSafetyTrip === true) {
                    report('Enable refused by PLC: safety stop latched.');
                    return;
                }
                await new Promise(function (resolve) { setTimeout(resolve, 100); });
            }
            throw new Error('Request sent, but PLC routine state was not confirmed. Check connection and PLC status.');
        }
        if (typeof fan !== 'string' || typeof box !== 'string' || fan !== box + '.fan' ||
            !box.startsWith('ADS.')) throw new Error('Invalid fan/coordinator symbol parameters.');
        // Routine stop and device stop are deliberately separate commands.
        if (action === 'ThermalDisable') {
            // Stop is unconditional; the PLC clears enable and stops both devices.
            await send(box + '.ctrl::bStop', true);
            await confirmRoutine(false);
            return;
        }
        if (action === 'Disable') {
            await send(fan + '.ctrl', {bAuto:false, bEnable:false, lrManualDutyPct:0});
            report('Fan stop requested.');
            return;
        }
        if (action === 'ThermalEnable') {
            await send(box + '.ctrl::bEnable', true);
            await confirmRoutine(true);
            return;
        }
        var status = await read(box + '.stat');
        if (!isCurrent()) return;
        if (action === 'Refresh') {
            var ctrl = await read(fan + '.ctrl');
            var input = find(root, '_Demand');
            if (input) input.setValue(ctrl.lrManualDutyPct);
            report('Connected');
            return;
        }
        if (action === 'Load') {
            setEditors(root, false);
            var cfg = validate(await read(fan + '.cfg'));
            displayDraft(root, cfg);
            var stopped = (await read(fan + '::stat::bActive')) === false;
            setEditors(root, stopped);
            report(stopped ? 'Configuration loaded' : 'Fan active. Configuration is read-only.');
            return;
        }
        if (action === 'Apply') {
            setEditors(root, false);
            if ((await read(fan + '::stat::bActive')) !== false)
                throw new Error('Stop the fan before applying fan configuration.');
            var saved = drafts.get(root);
            if (!saved) throw new Error('Load configuration before applying.');
            var candidate = editorDraft(root);
            var current = validate(await read(fan + '.cfg'));
            if (!same(saved, current)) throw new Error('Configuration changed elsewhere. Cancel to reload.');
            // Write one configuration structure, never the whole fan FB.
            await send(fan + '.cfg', candidate);
            var applied = validate(await read(fan + '.cfg'));
            if (!same(candidate, applied)) throw new Error('Configuration readback differs; reload and inspect.');
            displayDraft(root, applied);
            setEditors(root, true);
            report('Configuration applied and verified');
            return;
        }
        if (action === 'ResetSafety') {
            await send(box + '.ctrl::bResetSafety', true);
        } else if (action === 'ConfirmAlarms') {
            await send(box + '.ctrl::bConfirmAlarms', true);
        } else if (['Enable', 'Auto', 'Manual', 'SetDemand'].includes(action)) {
            if (status.bSafetyTrip !== false) throw new Error('Safety status unavailable or safety stop latched.');
            var fanCtrl = await read(fan + '.ctrl');
            if (action === 'Enable') {
                if (fanCtrl.bAuto !== false) throw new Error('Select fan MANUAL before starting it independently.');
                await send(fan + '.ctrl::bEnable', true);
            } else if (action === 'Auto') {
                fanCtrl.bAuto = true;
                await send(fan + '.ctrl', fanCtrl);
            } else if (action === 'Manual') {
                var fanStatus = await read(fan + '.stat');
                if (fanCtrl.bAuto === true) fanCtrl.lrManualDutyPct = fanStatus.lrDutyPct;
                fanCtrl.bAuto = false;
                await send(fan + '.ctrl', fanCtrl);
                if (isCurrent()) {
                    var editor = find(root, '_Demand');
                    if (editor) editor.setValue(fanCtrl.lrManualDutyPct);
                }
            } else {
            if (fanCtrl.bAuto !== false) throw new Error('Select fan MANUAL before setting its demand.');
            var demand = find(root, '_Demand').getValue();
            if (typeof demand !== 'number' || !Number.isFinite(demand) || demand < 0 || demand > 100)
                throw new Error('Fan demand must be between 0 and 100 percent.');
            await send(fan + '.ctrl::lrManualDutyPct', demand);
            }
        } else throw new Error('Unknown fan action.');
        report('Request sent; operating status is reported by the PLC.');
    }
    function NOTTFanAction(ownerId, fanSymbol, controlSymbol, action) {
        var root = scope(ownerId);
        if (!root) return;
        var isStop = action === 'Disable' || action === 'ThermalDisable';
        if (busy.has(root) && !isStop) return;
        var version = (versions.get(root) || 0) + 1;
        versions.set(root, version);
        var epoch = stopEpochs.get(controlSymbol) || 0;
        if (isStop) { epoch++; stopEpochs.set(controlSymbol, epoch); }
        var isCurrent = function () {
            return versions.get(root) === version && (stopEpochs.get(controlSymbol) || 0) === epoch;
        };
        busy.add(root);
        feedback(root, 'Working...');
        perform(root, fanSymbol, controlSymbol, action, isCurrent).catch(function (error) {
            if (!isCurrent()) return;
            if (action === 'Load' || action === 'Apply') setEditors(root, false);
            feedback(root, error.message || 'Fan action failed.');
        }).finally(function () { if (versions.get(root) === version) busy.delete(root); });
    }
    TcHmi.Functions.NOTT = TcHmi.Functions.NOTT || {};
    TcHmi.Functions.NOTT.NOTTFanAction = NOTTFanAction;
    TcHmi.Functions.registerFunctionEx('NOTTFanAction', 'TcHmi.Functions.NOTT', NOTTFanAction);
})(TcHmi);

