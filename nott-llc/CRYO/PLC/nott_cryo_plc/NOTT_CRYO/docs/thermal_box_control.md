# Thermal box control

The PLC source implements the coordinator in FB_NOTT_THERMAL_BOX_CONTROL.
The shared FB_NOTT_CTRL_TEMPERATURE and its cryostat heater users are unchanged.
The two thermal-box loop instances remain in FB_NOTT_TCTRLs, but only the
coordinator calls them cyclically, after applying configuration and permissions.

## Sensors and target

- t_thermal_box_1: outside temperature, variable setpoint source.
- t_thermal_box_2: inside temperature, process value.
- t_thermal_box_3: coolant inlet, monitoring only.
- t_thermal_box_4: coolant outlet, monitoring only.
- Target: outside temperature + cfg.lrSetpointOffset, in kelvin.
- Neither the thermal-box voter nor cryostat heaters are used by the coordinator.

## Operator controls

ctrl.bEnable requests operation; it is cleared on PLC startup and on a stop fault.
Enable is an operator demand, not a combined automatic-readiness permission.
Both HMI routine buttons are always available to authorized operators. An accepted
Enable requests device AUTO once and requests PID AUTO/enable individually as
each loop completes initialization. Device and PID modes are not overwritten
cyclically. bAutoCommissioned is retained as a legacy commissioning record only.
Uninitialized automatic branches, invalid control sensors, nonnegative cooling
gains and PID errors cause branch hold and diagnostics rather than canceling the
routine enable demand. A healthy branch can run while the other is held.
ctrl.bStop is a one-shot stop that also stops independently operating devices
when the routine is already disabled. Directly clearing ctrl.bEnable stops an
active routine. After Stop, manual fan/valve operation can be started explicitly.
Fan manual operation uses fan.ctrl.bAuto = FALSE, fan.ctrl.bEnable and
fan.ctrl.lrManualDutyPct. The valve uses its standard manual controls. Each PID
retains independent ctrl.eCtrlMode and ctrl.lrManualOut controls. While a device
is manually overridden, its upstream PID is held to avoid integral windup.
The legacy coordinator mode/manual-demand fields are retained but not applied.
PID tuning remains in each loop cfg; the coordinator supplies sensor selection,
variable-setpoint selection and offset. Verify tuning before AUTO commissioning.
After stopping due to a fault, a new operator Enable is required.

## Sensor fault hold

Loss of either control sensor raises the corresponding standard PID sensor
alarm immediately. If cooling was active, the coordinator holds the last applied
fan duty and exact ES4104 raw valve command for cfg.tSensorFaultHold (30 minutes
by default), for paths whose device and PID are both AUTO. Manual device/PID
intervention remains available before expiry and is not overwritten by the hold.
Recovery before expiry releases the hold without changing operator modes. Expiry stops the fan and
commands the valve closed; sensor recovery alone cannot restart operation.
It latches stat.bSafetyTrip, dominant over manual and automatic requests.
ctrl.bResetSafety clears the latch only after control sensors/configuration recover
and valve overload clears. Reset never starts cooling. Invalid sensors prevent a
automatic branch operation, not accepting the routine enable demand or independent
manual device operation. Starting with invalid sensors still starts the configured
fault timeout; expiry latches the safety stop.

The held valve command is not measured valve position: no position feedback is
connected. Fan stall remains an alarm but does not stop water circulation.
Valve diagnostics remain handled by the valve FB and are exposed centrally.
Coolant validity and an inlet temperature not below the target produce warnings
only. Control is never inhibited by coolant monitoring.

## Valve shutdown and I/O

For a normal 0..10 V, increasing-opening TA-Slider configuration:

| PLC signal | Terminal |
| --- | --- |
| valve.io_chiller_water_cooling.q_bEnable | EL2068 channel Output |
| valve.i_bOverCurrent | Same EL2068 channel Overload |
| valve.i_nCouplerState | Relevant coupler/device EtherCAT state (OP = 8) |
| valve.io_chiller_water_cooling.q_nSetVoltage | ES4104 channel Analog output |
| valve.io_chiller_water_cooling.i_bUnderrange / i_bOverrange / i_bWarning / i_bError | Matching ES4104 diagnostics, if present |
| fan.q_nPwmCommand | Configured EL2535 channel command |
| fan.i_bTach | ES1084 tach input |

Stopping cooling sends zero voltage command while keeping actuator power on for
cfg.tValveClose (provisional default 120 seconds). Then the EL2068 power output
switches off. The same closing sequence runs at PLC initialization to address a
valve potentially left open before restart. This is closing activity, not
automatic cooling enable. Removing power alone is not treated as closure.
An explicit manual valve start after a normal Stop cancels the closing sequence;
a latched safety trip cannot be bypassed this way. Valve overload/error prevents
the coordinator's closing-power override from energizing the actuator.

stat.bValveCloseTimeElapsed reports completion of a timer, not confirmed closure.
Verify closing direction, signal range, actuator startup/calibration delay and
required full closing time before deployment. A power interruption cannot be
guaranteed to close a non-fail-safe actuator.

## Alarms and monitoring

stat exposes individual causes, bAlarm, bWarning, status text, temperatures and
validities, target, fan duty/RPM, valve demand and command, hold elapsed time,
start/stop permissions and closing activity.
Individual fan/valve and PID manual flags and bMixedMode expose mixed operation.
sStartInhibitReason explains automatic availability or the latched safety stop;
it is not the permission for the HMI Enable button.
Routine controls and diagnostics are on ThermalBox content; the fan faceplate
commands only the fan. Controller errors raise alarms and hold the affected
automatic demand rather than aborting the whole routine.

Control-sensor and PID errors use the existing EventLogger alarm handler.
Fan stall and valve errors remain available through their device status; the
coordinator also aggregates them into stat.bAlarm. High-temperature and tracking
conditions have dedicated thermal-box status flags for HMI binding.
ctrl.bConfirmAlarms acknowledges the coordinator's EventLogger alarms; it does
not remove an active cause or reset the operator-enable requirement.

High-temperature alarm and poor-tracking warning are disabled by default until
limits are approved. Suggested commissioning values already in cfg are:

- High temperature: 313.15 K (40 C), 60-second delay, 2 K reset hysteresis.
- Tracking: inside at least 5 K above target for 10 minutes, 1 K reset hysteresis.

These are provisional, not approved electronics limits. Both conditions report
problems while allowing cooling to continue.

## Commissioning checks

No runtime activation is performed by editing this source.

1. Review/compile offline before downloading; review online-change eligibility.
2. Verify I/O mapping, PWM electrical interface/polarity and valve zero-command
   closure. Verify closing time before using timed power removal.
3. Use MANUAL with controlled demands to verify fan duty, valve response and cooling.
4. Verify sensor 1 is outside and sensor 2 is inside, in kelvin.
5. Tune fan and valve loops separately with negative Kp. Prefer a faster fan loop
   and slower valve loop; two integral loops on the same PV can interact.
   Review each loop's existing ramp rates, target-change threshold and maximum
   tracking difference for ambient-temperature regulation; shared ramp logic is
   unchanged. Avoid a zero tracking difference, which can suppress cooling error.
6. Verify tuned negative gains before allowing automatic outputs. Check that a
   nonnegative gain holds only its automatic branch without rejecting Enable.
7. With an isolated test setup, shorten the fault hold and verify both sensor
   failures, frozen commands, recovery before expiry, timeout and operator restart.
   Verify independent PID/device overrides, safety reset refusal while sensors
   are invalid, no restart on reset, and manual operation after a normal Stop.
8. Verify Disable during a hold immediately stops the fan and closes the valve.
9. Verify fan-stall alarm does not disable water circulation; coolant invalidity
   produces only a warning. Verify configured high/tracking hysteresis.
10. Verify cold PLC restart leaves cooling disabled and runs the valve-close sequence.

The fan code flags tach measurement limitations for the current 10 ms task.
Reliable RPM/stall validation requires commissioning the input filtering and
pulse capture; this implementation does not change the fan FB.
