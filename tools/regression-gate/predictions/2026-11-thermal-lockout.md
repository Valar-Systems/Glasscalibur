# Glasscalibur motor thermal protection and stall-detector interlock — predictions

Written and committed before any code change on branch `fw/thermal-lockout`.
No check below had been run when this file was committed.

- Base: origin/main `a3da69c` (#17 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.
- Target: `firmware/glasscalibur.yaml`.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-06)

Close the open firmware items FW-1, FW-2, FW-3 and FW-5 of the test protocol before
the 2.2.0 bench session. Today the motor-temperature cutoff is a one-shot stop at
80 °C (the motor's case limit is 60 °C); nothing stops a schedule, Home Assistant,
the web UI or Button 1 from restarting a hot motor; a missing sensor (NAN) only
blocks calibration; and both stall detectors can be switched off at once.

1. Thresholds as substitutions (the sensor offset may move them): 50 °C warn (log +
   an event entity like Obstruction); 55 °C refuse to start new motion; 60 °C stop,
   latch a lockout, chirp, fire the event; the lockout clears only below 48 °C (event
   on clear); no valid reading for 15 s (NAN or stale), including after boot until
   the first reading: the same lockout.
2. Check it at the top of every motion path. STOP always works. A stall back-off
   already running may finish.
3. A "Thermal Lockout" diagnostic binary sensor.
4. FW-5: at least one stall detector active whenever closing; the simplest way that
   can't be bypassed, named here.
5. Wording: the web UI's tamper group is renamed "Tamper"; the Child Lock comment
   describes what it does.
6. firmware/README.md, the README feature line and a CHANGELOG 2.2.0 entry.
7. Bench TP-1, TP-2, EN-2 join the 2.2.0 list.

## Design

Thresholds (`firmware/glasscalibur.yaml` substitutions): `thermal_warn_c` 50,
`thermal_start_max_c` 55, `thermal_lockout_c` 60, `thermal_clear_c` 48,
`thermal_stale_s` 15. Comparisons: warn at >= 50, refuse at >= 55, lockout at >= 60,
clear at < 48.

**Deviation from the protocol, recorded as asked:** at 55 °C the protocol drops the
motor current to IRUN 15 mid-move. That would invalidate the StallGuard tune, which
calibration sets at the calibrated current. Instead, 55 °C is a start gate: no new
motion starts at or above it; a move already under way continues (the 60 °C lockout
stops it).

Temperature (`packages/temperature.yaml`, replacing the 80 °C `on_value_range`):
- `on_value` of Motor Temperature: a NAN value is ignored (it does not count as a
  reading). A valid value records the time. >= 60 -> lockout (once). < 48 -> clears
  the lockout (once, event `cleared`) and re-arms the warning. >= 50 with no
  lockout and the warning armed -> one warning (log WARN, event `warning`).
- A 500 ms interval: no valid reading for 15 s -> the same lockout (event
  `sensor_lost`). The clock starts at boot, so a sensor that never reports locks out
  15 s after boot. 500 ms is a new, unique interval period: no existing interval
  anchor changes ordinal.
- The lockout (`thermal_trip`): sets the latch, logs WARN with the cause, fires the
  event (`lockout` for >= 60, `sensor_lost` for no reading), ends a running
  calibration through `cal_thermal_guard` (thermal abort, result 4), halts any
  motion that is not a stall back-off, and chirps the buzzer (4 short 3200 Hz chirps,
  distinct from the calibration and tamper sounds).
- The latch is in RAM. A restart clears it; the start gate below still refuses
  until a valid reading under 55 °C arrives.
- One event entity, **Thermal Alert**, event types `warning`, `lockout`,
  `sensor_lost`, `cleared` (Control group, under Obstruction). One diagnostic binary
  sensor, **Thermal Lockout** (Diagnostics, by Motor Temperature).
- The old 80 °C rule is removed: the 60 °C lockout covers it.

The start gate: motion is refused when the lockout is set, the Motor Temperature
state is NAN (no reading yet after boot, or a failed read), or it is >= 55 °C.
- **Cover open, close and position actions:** the gate is their first step; a refused
  command logs WARN with the reason and does nothing else (a move already running is
  not stopped by a refused command; STOP does that). The web UI, Home Assistant, the
  REST API, Button 1 (click and double click call the cover's close and open) and the
  schedules (`schedule_open` / `schedule_close` call the cover's open and close) all
  reach the motor only through these three actions, so each of them is gated there.
  STOP (`stop_action`) is not gated.
- **Calibration:** `auto_calibrate` refuses during a lockout (new precondition, next
  to the existing 50 °C / NAN one), and `cal_thermal_guard`, run before every
  calibration travel, also stops the run when the lockout is set.
- **Stall back-off:** not a new command; it starts from the stall handler, is not
  gated, and is not halted by the lockout.
- Calibration's own limits become the substitutions: refuse to start above
  `thermal_warn_c`, stop mid-run above `thermal_start_max_c` (same numbers as today).
- Known consequence, not changed here: a scheduled open or close refused by the gate
  is not retried (the shared scheduler fires once per time or sun transition).

FW-5, the method: **an interlock on the two detector switches.** Turning
**StallGuard Enabled** off while **Vibration Stall Detection** is off is refused (it
switches straight back on, logged at WARN), and so is turning vibration off while
StallGuard is off. So at least one detector is on at all times, not only while
closing, whichever interface sets the switch (web UI, Home Assistant, the API).
- Boot: both switches restore from flash before the interlock is armed (on_boot
  priority 490, after the switches' restore). If both were stored off (possible from
  earlier firmware), StallGuard is turned on there, logged at WARN; then the
  interlock arms. Before it arms, the restore itself is never refused.
- Calibration's detector posture is reordered to vibration on first, then StallGuard
  off (today: StallGuard off, then vibration on, which the interlock would refuse on
  a unit with vibration off). The posture itself is unchanged.
- HA and the web UI end showing ON after a refused switch-off: ESPHome notifies them
  after the switch's own triggers, from the switch's current state.

Wording:
- The web UI's tamper group (weight 45) is renamed "Tamper", and its id becomes
  `group_tamper`, in the group list and in the five tamper entities that point to
  it. Group ids are internal to the config; entity names, IDs and Home Assistant
  entity IDs don't change, and the page order is the same (weight 45).
- The Child Lock comment drops the example and says what it does: Button 1 ignores
  presses; remote control (web UI, Home Assistant, the API, schedules) keeps working.
  The entity name stays "Child Lock".
- Stale comments that name the 80 °C cutoff are updated.

## Checks (head vs base a3da69c)

C1 `esphome config` validates and `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in a thermal lambda is refused by the compile.
G1 Entity gate: NEW exactly binary_sensor "Thermal Lockout" and event "Thermal
   Alert"; nothing dropped, renamed or retyped.
   Sabotage: a scratch copy of the head with "Child Lock" renamed shows a rename.
G2 Behaviour gate:
   - CHANGED exactly: `cover:Glasscalibur` open_action, close_action,
     position_action; `script:auto_calibrate`; `script:cal_thermal_guard`.
   - NEW exactly: `script:thermal_trip`, `script:thermal_clear`,
     `script:thermal_warn`, `script:thermal_refused`, `script:thermal_chirp`;
     `interval:500ms`; `esphome:on_boot :: 490.0`; `sensor:Motor Temperature ::
     on_value`; `switch:StallGuard Enabled :: on_turn_off`; `switch:Vibration Stall
     Detection :: on_turn_off`; `binary_sensor:Thermal Lockout :: lambda`.
   - DROPPED exactly: `sensor:Motor Temperature :: on_value_range`.
   Sabotage: a scratch copy of the head with the base's open_action does not list
   open_action as CHANGED.
R1 Resolved-config facts (head): the gate expression is the first step of each of the
   three cover actions; `stop_action` equals the base's; `schedule_open`,
   `schedule_close` and Button 1's handlers equal the base's (they reach motion only
   through the cover actions); the web UI group with weight 45 is named "Tamper"
   with id `group_tamper`, the five tamper entities use that id, and no other group
   has weight 45; no `on_value_range` remains on Motor Temperature.
   Sabotage: the base fails the first and the group facts.
D1 Docs: firmware/README.md's entity reference matches the head's resolved config
   (66 entities: 64 + 2), and every relative link resolves.
   Sabotage: the reference with one row dropped is reported.
W1 Wording: the P8 push scan, the docs claims scan and the local motor-term check
   pass on the full diff, the commit messages and the PR text.
   Sabotage: each is caught by a planted line, as before.

## Bench (not run in this PR; Daniel present for every motion step)

- TP-1 Heat the sensor plate. The warning, the start gate and the stop with lockout
  fire at their set points ±2 °C. Every command path (web UI, Home Assistant, REST,
  Button 1, a schedule, calibration) is refused during the lockout, STOP still
  works, and the lockout clears below 48 °C.
- TP-2 Unplug the temperature board. The unit locks out 15 s after the last valid
  reading (the 500 ms check adds at most 0.5 s), so at most ~15.5 s after the unplug.
- EN-2 Try to set both detector switches off: the second switch-off is refused.
  Then stall a close: a detector still trips.

The 2.2.0 tag also waits on TP-1, TP-2 and EN-2.
