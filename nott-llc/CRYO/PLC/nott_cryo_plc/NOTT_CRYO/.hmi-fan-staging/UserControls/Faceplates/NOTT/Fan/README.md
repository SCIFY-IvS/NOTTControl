# NOTT fan HMI controls

## Files and bindings

- UserControls/Controls/NOTT/Fan/NOTTFanUserControl.usercontrol: compact fan symbol.
- UserControls/Faceplates/NOTT/Fan/NOTTFanFaceplate.usercontrol: tabbed popup.
- Operate, Status and Configuration tabs have their own usercontrol metadata.
- JavaScript/NOTTFanAction.js: checked coordinator commands and draft configuration.
- Images/NOTT: fan running/stopped symbols and water/air heat exchanger.
- Pages/ThermalBox.content: fan host, exchanger and four sensor role labels.

All controls take FanObject, ThermalStatus, FanSymbol and ControlSymbol parameters.
The default instance is MAIN.nott_cryo_ctrl.thermal_box_ctrl.fan.
Enable/Disable operate both thermal-box cooling devices through the coordinator.
AUTO/MANUAL requests also go to the coordinator. Manual fan demand writes only
ctrl.lrManualFanPct, never the fan FB's overwritten local ctrl members.

## Configuration

Configuration is a local draft. Apply writes only the fan cfg structure, after
checking both cooling and fan are disabled, validating the draft and detecting
changes by another client. It then verifies the readback. Cancel reloads the PLC.
Nothing writes automatically when a popup opens or a tab is selected.

Times are entered in milliseconds. Min/max duty, startup duty, timing, pulses per
revolution, PWM scaling and inversion are validated before writing.
These are runtime settings. The existing fan FB has no configuration-file
persistence; this HMI does not promise persistence across a PLC cold restart.
The missing fan cfg properties are defined in the HMI server schema and mapped
explicitly to the existing ADS cfg symbol. No PLC source attributes are changed.

## Access

The fan FB's parent mapping is read-only. A separate cfg mapping is writable for
Engineering. Operation can write the coordinator ctrl mapping; Monitoring and
the baseline SystemUsers mappings are read-only. The UI follows the project's
Monitoring/Operation access-config pattern and server permissions protect writes.

AUTO requests require the mapped cfg.bAutoCommissioned flag. Invalid/missing
symbols reject start, mode or demand requests; configuration editors remain
disabled after a failed load. Stop requests do not require readable status.
Sensor-fault hold prevents changing manual fan demand.

## Verification and deployment

Offline checks cover command routing, permission checks, unavailable symbols,
commissioning gating, sensor hold, invalid values, drafts, cancel, stale drafts,
configuration while running, write denial, project includes and JSON syntax.
The preview screenshots use mocked native-control rendering, not a live HMI server.

Reload the HMI project in engineering, verify symbols against the deployed PLC,
and test the native popup and user permissions in an isolated commissioning setup.
A schema refresh may replace hand-maintained cached type definitions; preserve
or recheck the explicit cfg mapping and its field schema after refresh.

The existing voter and two PID controls on ThermalBox retain their original
baseplate bindings, as requested. No existing page controls are moved.
No PLC compilation, download, HMI server restart or runtime deployment is performed.

