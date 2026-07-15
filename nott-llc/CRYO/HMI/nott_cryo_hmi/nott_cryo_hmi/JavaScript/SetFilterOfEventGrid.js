// Keep these lines for a best effort IntelliSense of Visual Studio 2017 and higher.
/// <reference path="./../../Packages/Beckhoff.TwinCAT.HMI.Framework.12.760.59/runtimes/native1.12-tchmi/TcHmi.d.ts" />

(function (/** @type {globalThis.TcHmi} */ TcHmi) {
    var Functions;
    (function (/** @type {globalThis.TcHmi.Functions} */ Functions) {
        var MyNamespace;
        (function (MyNamespace) {
            function SetFilterOfEvents(EventGrid, EventClassName, ShowNonClearedOnly, InstanceName) {
                var jsonObj = [{ "path": "domain", "comparator": "==", "value": "TcHmiEventLogger" }]
                //if (EventClassName) {
                //    jsonObj.push({ "logic": "AND" });
                //    jsonObj.push({ "path": "params::eventClassName", "comparator": "==", "value": EventClassName });
                //}

                if (InstanceName) {
                    jsonObj.push({ "logic": "AND" });
                    var jSonObjInstance = []
                    jSonObjInstance.push({ "path": "params::sourceName", "comparator": "==", "value": InstanceName });
                    jSonObjInstance.push({ "logic": "OR" });
                    jSonObjInstance.push({ "path": "text", "comparator": "contains [ignore case]", "value": InstanceName });
                    jsonObj.push(jSonObjInstance);
                }

                if (ShowNonClearedOnly) {
                    jsonObj.push({"logic": "AND"});
                    jsonObj.push([{ "path": "alarmState", "comparator": "==", "value": 0 }, { "logic": "OR" }, { "path": "alarmState", "comparator": "==", "value": 1 }]);
                }

                EventGrid.setFilter(jsonObj);
            }
            MyNamespace.SetFilterOfEvents = SetFilterOfEvents;
        })(MyNamespace = Functions.MyNamespace || (Functions.MyNamespace = {}));
    })(Functions = TcHmi.Functions || (TcHmi.Functions = {}));
})(TcHmi);
TcHmi.Functions.registerFunctionEx('SetFilterOfEvents', 'TcHmi.Functions.MyNamespace', TcHmi.Functions.MyNamespace.SetFilterOfEvents);
