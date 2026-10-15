# NOTT fan and thermal-box HMI

ThermalBox content owns routine Enable/Disable, safety reset, alarm confirmation,
routine diagnostics, sensor-hold elapsed time and independent PID/device modes.
The fan faceplate owns only fan AUTO/MANUAL, manual start/stop and manual duty.
The existing valve and PID faceplates retain their own controls.

An accepted routine Enable requests AUTO for both devices/PIDs once. Operator
mode changes thereafter persist. Routine Disable stops both devices and closes
the valve; later explicit manual operation is available while the routine is off.
The fan stop action does not stop the thermal-box routine or water circulation.

Fan commands write only fan.ctrl. Thermal-box commands write only the
coordinator ctrl. The default instance is
ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl.fan.
The parent fan mapping is read-only. Its separate ctrl mapping is writable for
Operation/Engineering, read-only for Monitoring. Fan cfg remains Engineering-only.

Manual device operation does not require valid temperature sensors or automatic
commissioning approval, but requires an available, clear PLC safety-trip status.
During the sensor-fault hold, explicit manual intervention remains available.
The timeout latches a safety stop that overrides all modes. Reset is refused by
the PLC until conditions recover; reset never enables cooling.

Configuration is a local draft with validation, concurrent-change detection and
readback verification. Apply requires the fan stopped, not the whole routine off.
Times are milliseconds. Configuration has no new file persistence guarantees.
Recheck the explicit configuration field schema after an ADS schema refresh.

The shared PID implementation is unchanged. The coordinator freezes an upstream
PID during a device manual override. Verify AUTO handback and output transitions
in isolated commissioning; full bumpless actuator tracking is not implemented.
Automatic routine start still requires both initialized PID loops, valid control
sensors, approved commissioning and negative cooling gains. The page displays
the start-inhibit reason rather than hiding it behind fan permissions.

PLC and HMI source changes must be reviewed and deployed together. New safety
status/stop/reset fields do not exist in the previous deployed PLC version.
Unknown safety status disables manual start/mode/demand actions. Routine Disable
retains the legacy bEnable=FALSE write before issuing the new one-shot Stop.

Offline checks cover command routing, access failures, mode separation,
configuration guards, JSON and datatype namespace consistency. Layout previews
use mocked native controls, not a live TwinCAT HMI server. The PLC control-flow
simulation mocks device/PID behavior and is not a substitute for TwinCAT compilation.
No compilation, download, PLC restart or live hardware operation is performed.
