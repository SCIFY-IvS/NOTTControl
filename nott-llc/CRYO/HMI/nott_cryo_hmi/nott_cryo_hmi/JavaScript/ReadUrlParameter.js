// Keep these lines for a best effort IntelliSense of Visual Studio 2017 and higher.
/// <reference path="./../../Packages/Beckhoff.TwinCAT.HMI.Framework.12.760.59/runtimes/native1.12-tchmi/TcHmi.d.ts" />

(function (TcHmi) {
    //Register to the global onInitialized event, the anonymous function will be called only one time and will check the parameter of the url and reloads the page depending on the parameter
    let destr = TcHmi.EventProvider.register("onInitialized", function () {
        // This event will be raised only once, so it is nice to cleanup
        destr();

        //Get the complete url from browser and splitting the url at "?" in an array, e.g. http://127.0.0.1:1010/?View=ControlRoom
        let paramArray = window.location.href.split('?');
        //Create temp variables for the path parameter
        let pathParam = "";

        //Search in paramArray of splitted url for 'View=', e.g. "View=View1"
        for (i = 0; i < paramArray.length; i++) {
            if (paramArray[i].indexOf('View=') === 0) {
                pathParam = paramArray[i].split('/').join('');
                break;
            }
        }

        //Setting of viewName depending on pathParam
        if (pathParam === "View=ControlCabinet") {
            TcHmi.View.load('ControlCabinet.view', function (data) {
                //Optional: Callback after the page is loaded
            });
        }
        else if (pathParam === "View=ControlRoom") {
            TcHmi.View.load('ControlRoom.view', function (data) {
                //Optional: Callback after the page is loaded
            });
        }	
    });
})(TcHmi);