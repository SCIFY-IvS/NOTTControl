(function (TcHmi) {
    'use strict';
    var sessions = new WeakMap();
    var thermal = 'ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl.stat';
    var detector = 'ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power.stat';
    var fuse = 'ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power.fuseDetectorPower';
    var faults = ['bTripped', 'bShortCircuit', 'bOverload', 'bHardwareProtection',
        'bOvervoltage', 'bUndervoltage', 'bError', 'bTxPDOState'];
    function find(root, suffix) {
        if (root.getId().endsWith(suffix)) return root;
        var children = root.getChildren ? root.getChildren() : [];
        for (var i = 0; i < children.length; i++) {
            var result = find(children[i], suffix);
            if (result) return result;
        }
        return null;
    }
    function paint(control, active, alarm, known, label) {
        if (!control) return;
        var element = control.getElement();
        element.toggleClass('nott-status-alarm', alarm === true);
        element.toggleClass('nott-status-active', alarm !== true && known && active === true);
        if (control.setTooltip) control.setTooltip(label + (alarm === true ? ': alarm' :
            !known ? ': status unavailable' : active ? ': enabled' : ': disabled'));
    }
    function update(session) {
        var t = session.values[thermal], d = session.values[detector];
        var bits = session.values[fuse + '.i_stStatus'], f = session.values[fuse + '.stat'];
        var fuseAlarm = bits && faults.some(function (name) { return bits[name] === true; });
        var detectorAlarm = !!((d && d.bAlarm === true) || fuseAlarm ||
            (f && typeof f.nErrorCode === 'number' && f.nErrorCode !== 0));
        paint(find(session.root, '_NavigationButton_ThermalBox'), t && t.bActive,
            t && t.bAlarm, !!t, 'Thermal box');
        paint(find(session.root, '_NavigationButton_DetectorPower'), d && d.bPowerOn,
            detectorAlarm, !!(d && bits && f && d.bFuseOperational === true), 'Detector power');
        var events = find(session.root, '_NavigationButton_Events');
        paint(events, false,
            session.unconfirmed > 0, session.unconfirmed !== null, 'Unconfirmed alarms');
        if (events && events.setTooltip && session.unconfirmed !== null)
            events.setTooltip('Unconfirmed alarms: ' + session.unconfirmed);
    }
    function clear(session) {
        session.values = {};
        session.unconfirmed = null;
        update(session);
    }
    function subscribe(session) {
        var commands = [thermal, detector, fuse + '.i_stStatus', fuse + '.stat'].map(function (symbol) {
            return {symbol: symbol, commandOptions: ['SendErrorMessage']};
        });
        // Same count-only query used by the installed EventGrid's Confirm All control.
        commands.push({symbol: 'ListEvents', commandOptions: ['SendErrorMessage'], limit: 0,
            filter: [{path: 'type', comparator: '==', value: TcHmi.Server.Events.Type.Alarm},
                {logic: 'AND'}, {path: 'confirmationState', comparator: '==',
                    value: TcHmi.Server.Events.ConfirmationState.WaitForConfirmation}]});
        session.subscription = TcHmi.Server.subscribeEx(commands, 1000, null, function (data) {
            if (sessions.get(session.root) !== session) return;
            if (data.error !== TcHmi.Errors.NONE || !data.response || data.response.error ||
                !Array.isArray(data.response.commands)) {
                clear(session); return;
            }
            (data.response.commands || []).forEach(function (command) {
                if (command.symbol === 'ListEvents') {
                    session.unconfirmed = !command.error && typeof command.maxEntries === 'number' ?
                        command.maxEntries : null;
                } else if (command.error || !command.readValue || typeof command.readValue !== 'object') {
                    delete session.values[command.symbol];
                } else session.values[command.symbol] = command.readValue;
            });
            update(session);
        });
    }
    function stop(root) {
        var previous = sessions.get(root);
        if (!previous) return;
        sessions.delete(root);
        previous.disconnect();
        previous.reconnect();
        if (previous.subscription !== null) TcHmi.Server.unsubscribeEx(previous.subscription, null);
        clear(previous);
    }
    function NOTTHeaderStatus(ownerId, action) {
        var root = TcHmi.Controls.get(ownerId);
        if (!root) return;
        stop(root);
        if (action !== 'Attach' || (typeof TCHMI_DESIGNER !== 'undefined' && TCHMI_DESIGNER)) return;
        var session = {root: root, values: {}, unconfirmed: null, subscription: null,
            disconnect: function () {}, reconnect: function () {}};
        sessions.set(root, session);
        session.disconnect = TcHmi.EventProvider.register('onServerNotReady', function () { clear(session); });
        session.reconnect = TcHmi.EventProvider.register('onServerReady', function () {
            if (sessions.get(root) !== session) return;
            if (session.subscription !== null) TcHmi.Server.unsubscribeEx(session.subscription, null);
            clear(session);
            subscribe(session);
        });
        clear(session);
        subscribe(session);
    }
    TcHmi.Functions.NOTT = TcHmi.Functions.NOTT || {};
    TcHmi.Functions.NOTT.NOTTHeaderStatus = NOTTHeaderStatus;
    TcHmi.Functions.registerFunctionEx('NOTTHeaderStatus', 'TcHmi.Functions.NOTT', NOTTHeaderStatus);
})(TcHmi);
