// Keep these lines for a best effort IntelliSense of Visual Studio 2017 and higher.
/// <reference path="./../../Packages/Beckhoff.TwinCAT.HMI.Framework.12.760.59/runtimes/native1.12-tchmi/TcHmi.d.ts" />

(function (TcHmi) {

    var GetCurrentUsername = function () {
        var user = TcHmi.Server.getCurrentUser().substring(0,17);
        return user;
    };
    
    TcHmi.Functions.registerFunction('GetCurrentUsername', GetCurrentUsername);
})(TcHmi);
