// Keep these lines for a best effort IntelliSense of Visual Studio 2017 and higher.
/// <reference path="./../../Packages/Beckhoff.TwinCAT.HMI.Framework.12.760.59/runtimes/native1.12-tchmi/TcHmi.d.ts" />

(function (/** @type {globalThis.TcHmi} */ TcHmi) {
    var Functions;
    (function (/** @type {globalThis.TcHmi.Functions} */ Functions) {
        var MyNamespace;
        (function (MyNamespace) {
            function PrintFilterOfEventGrid(EventGrid) {
                var jsonObj = EventGrid.getFilter();
                console.log(jsonObj);
                console.log("--");
                console.log(JSON.stringify(jsonObj));
            }
            MyNamespace.PrintFilterOfEventGrid = PrintFilterOfEventGrid;
        })(MyNamespace = Functions.MyNamespace || (Functions.MyNamespace = {}));
    })(Functions = TcHmi.Functions || (TcHmi.Functions = {}));
})(TcHmi);
TcHmi.Functions.registerFunctionEx('PrintFilterOfEventGrid', 'TcHmi.Functions.MyNamespace', TcHmi.Functions.MyNamespace.PrintFilterOfEventGrid);
