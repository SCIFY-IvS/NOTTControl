# Detector power control

The page is Pages/DetectorPower.content, with Overview, Diagnostics and
Configuration tabs. It includes every functional field/indicator from the Fuse
GUI template; the duplicated CoolDown indicator is represented once and all
21 fuse status bits are shown, including DisabledByOutput and the raw cycle bits.
Fuse ENABLE/DISABLE are software operational-state commands, not power ON/OFF.

## Command Ownership

The wrapper forwards INIT, RESET, STOP, ENABLE, DISABLE, ON and OFF to the
corresponding native RPC methods. It reports the library's acceptance or refusal
without translating ON into INIT or adding normal-operation readiness checks.
Only FB_FUSE writes q_bSwitch and q_bReset. There is no second toggle-pulse state
machine or output suppression in the detector wrapper.

The fuse library is unchanged. Its automatic startup initialization and explicit
INIT can energize the channel; bAutoOp only governs entry into software OP.
This native behavior is intentionally retained, not an OFF-at-startup guarantee.
HMI command feedback waits for PLC consumption and shows the PLC result plus a
snapshot of native state and power feedback. Acceptance is not physical completion;
the page's bound state and power indicators remain the operating feedback.

## Protection

- cfg.lrCurrentTrip_A defaults to 2.5 A. A valid magnitude strictly above this
  limit latches the trip without an intentional delay. Negative current is also
  protected by magnitude. Exactly 2.5 A does not trip the default configuration.
- The trip inhibits normal commands except OFF and requests shutdown through the
  native command mailbox, including when local GUI ownership is selected. In
  OP_ON it requests OFF. In NOTOP_READY_ON it requests ENABLE (software OP only),
  then OFF on the following eligible scan. During initialization or switching it
  waits for the library to reach a state accepting OFF. It never restarts INIT
  or resets a hardware trip to obtain shutdown.
- No blind physical toggle/retry is used. Feedback remaining ON for 10 seconds,
  or lost fuse communication during a trip, raises shutdown-unconfirmed alarm.
  A later observed ON after an OFF confirmation requests shutdown again.
- Reset requires valid current strictly below the limit, confirmed fuse OFF and
  operational fuse feedback, outside INIT/switching. Reset does not issue a fuse
  command; simultaneous reset/ON is refused. Native startup/INIT behavior remains
  unchanged. The RETAIN latch depends on the configured TwinCAT retain
  storage; verify persistence on the target, including power loss.
- A stale/invalid/range-error/calibrating meter causes notifications only, not
  automatic shutdown. In that situation current protection is unavailable.
  Fresh samples use TxPDO Toggle plus a configurable 5 second timeout and the
  meter's own EtherCAT state. The first sample is invalid until a toggle is seen.
- Critical trip, diagnostic warning and shutdown-unconfirmed alarms use existing
  NottCryoSysEventClass events and the PLC EventLogger, not browser-only logic.

This is supervisory software, not fast hardware protection. Measurement
conversion/filtering, the PLC/EtherCAT cycle, fuse switching, converter output
capacitance and detector load all affect actual power-removal time. OFF feedback
is the 24 V fuse state, not measured detector 5 V. No output-voltage measurement
exists, so the page does not claim to measure 5 V or calculate measured watts.

## I/O Source Changes Requiring Review

The existing detector fuse input links remain unchanged. Added source links are:

| PLC variable | I/O |
| --- | --- |
| fuseDetectorPower.q_bSwitch | EL9227 Channel 1 Control.Switch |
| fuseDetectorPower.q_bReset | EL9227 Channel 1 Control.Reset |
| i_nMeterState | DetectorPowerMeasurement InfoData.State |

The detector meter alone has its unmapped SAI Range output PDO 0x1600 deselected
in the source. Otherwise its default output Mode can override CoE startup
settings. Existing startup settings are Mode 2 (DC current), Range 1 (10 A),
Presentation 2 (one digit per microampere). No live CoE/PDO settings are written.
Confirm the physical 10 A/COM path, DC mode and scaled format before relying on
the limit. Native fuse pulse behavior is taken from the installed library source.

These project-source mappings and PDO changes are NOT an online activation.
Review/build in TwinCAT and inspect resolved links/SM assignments before a
controlled deployment. This work does not compile, restart or activate hardware.

## HMI Access and Commissioning

Operation/Engineering can write only the wrapper command mailbox. Fuse status,
meter status and raw bits are read-only. Engineering can edit both configurations
and local/remote ownership. Monitoring/SystemUsers mappings are read-only.
Configuration Apply requires valid fuse feedback and power OFF, checks for
concurrent edits and verifies both readbacks. The two configuration structures
are separate ADS writes, not a transactional update; inspect both after failures.

Before connection to the detector, test with a dummy load: native startup/INIT
energizing behavior; repeated ON/OFF; all fuse commands, refusals and local
ownership; 2.5 A boundary and 2.500001 A trip; reverse current; notification-only
meter faults; disconnects/stale data; trips during INIT/SWITCHING_ON; OFF feedback
timeout; invalid reset; accepted reset remains OFF; no ON bypass from native GUI
or RPC during a latch; shutdown requests in NOTOP_READY_ON and while initializing;
power-cycle retain behavior. A library state that cannot accept shutdown raises
an alarm rather than being bypassed by a direct output override. Verify actual 5 V decay with
appropriate instrumentation. Never test overcurrent by overloading the detector.
