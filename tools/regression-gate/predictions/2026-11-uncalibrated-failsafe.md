# Glasscalibur uncalibrated fail-safe — predictions

Written and committed before any code change on branch `feature/uncalibrated-failsafe`.
No check below had been run when this file was committed.

- Base: origin/main `7d5c8ac` (PR #9 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv (local Python 3.13; CI Python 3.11).
- Target: `firmware/esphome/Glasscalibur-esphome.yml`.

Rules, as before: a result that differs from its prediction stops the work and is
reported; neither is edited to pass. No reading = instrument failure, may be rerun,
reported. Every check has a sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

Keep the driver's default StallGuard threshold; make uncalibrated units fail safe:
1. A persisted "StallGuard calibrated" flag, set only when the existing calibration
   routine completes successfully on this unit, kept across firmware updates.
2. Until it is set, every move (open, close, manual, automation) runs at the Fast
   preset whatever the speed setting; next to the speed control the web UI shows
   "Speed locked to Fast until calibration has run".
3. A persistent "Not calibrated - run Calibrate" notice in the web UI until
   calibration succeeds; "StallGuard calibrated" as a binary sensor in Diagnostics.
4. After a successful calibration, the user's speed setting applies. A later failed
   calibration keeps the last good one (never back to uncalibrated) and logs a WARN
   with the reason.
5. The vibration stall detector is unchanged.
CHANGELOG under 2.2.0 (unreleased).

## Design

- Global `sg_calibrated` (bool, restore_value, initial false). Set in calibration's
  success branch (where `cal_speed_at` is recorded). Never cleared.
- Units calibrated by an earlier firmware: `cal_speed_at` is written only in that
  same success branch and is persisted, so on boot (on_boot 500) a nonzero
  `cal_speed_at` with the flag unset sets the flag once, logged at INFO. (Without
  this every already-calibrated unit would jump to Fast after the update.)
- Effective speed = the user's `global_speed` when calibrated or while a calibration
  runs, else the Fast preset (new substitution `speed_fast` "5500", also used by the
  Speed select). Calibration runs at the user's speed, as today: it measures cruise
  TSTEP there to set TCOOLTHRS, and holds the StallGuard reaction off anyway.
- The effective speed is applied at the start of every move (drive_open,
  drive_close, the cover's position_action — every open, close, Set-position,
  Button 1, schedule and calibration travel goes through these) and after anything
  that sets the driver speed: on_boot 500 (after core's 600 apply), the Speed select
  and core's raw Speed number (extended), and every calibration exit.
- Calibration exits other than success (could not reach the close limit, window never
  reached both limits, thermal stop, aborted by user) run a new script
  `cal_keep_last_good` (parameter: reason) that logs a WARN — "keeping the last good
  calibration" when calibrated, "unit stays uncalibrated - speed locked to Fast"
  when not — and re-applies the effective speed. SGTHRS/TCOOLTHRS are already
  written only on success, so a failure keeps the last good tune.
- New entities: binary sensor "StallGuard calibrated" (DIAGNOSTIC, Diagnostics
  group); text sensor "Speed Lock" next to the Speed select ("Speed locked to Fast
  until calibration has run" / "Not locked"); text sensor "Calibration Notice" at the
  top of the Control group ("Not calibrated - run Calibrate" / "Calibrated").
- Vibration detector: no change.

## Checks (run on the head; base = 7d5c8ac)

C1 `esphome config` validates and `esphome compile` succeeds (2026.6.5); CI green on
   the PR head.
   Sabotage: an undefined id in the new effective-speed lambda in drive_open is
   refused by `esphome compile`.
S1 Resolved head config: global `sg_calibrated` with restore_value true, initial
   'false'.
   Sabotage: the base has no such global.
S2 `sites.py … stepper.set_speed` on the head lists exactly: `esphome:on_boot 600.0`
   (core), `esphome:on_boot 500.0`, `number:Speed set_action` (core + the product's
   extension, one anchor), `select:Speed set_action`, `cover:Glasscalibur
   position_action`, `script:drive_open`, `script:drive_close`,
   `script:auto_calibrate`, `script:cal_keep_last_good`.
   Sabotage: the base lists only `esphome:on_boot 600.0`, `number:Speed set_action`
   and `select:Speed set_action`.
S3 The head's on_boot 500 body contains the seed `cal_speed_at` check.
   Sabotage: the base's on_boot 500 does not.
G1 Entity gate, base -> head: ADDED exactly `binary_sensor StallGuard calibrated`
   (DIAGNOSTIC), `text_sensor Speed Lock` (no category), `text_sensor Calibration
   Notice` (no category); REMOVED none.
   Sabotage: a scratch copy of the head's resolved config with "Speed Lock" renamed
   shows a different ADDED row.
G2 Behaviour gate, base -> head: CHANGED exactly `esphome:on_boot :: 500.0`,
   `cover:Glasscalibur :: position_action`, `select:Speed :: set_action`,
   `number:Speed :: set_action`, `script:drive_open`, `script:drive_close`,
   `script:auto_calibrate`, `script:cal_abort`, `script:cal_thermal_guard` (each
   `:: then`). NEW exactly `script:cal_keep_last_good :: then`,
   `binary_sensor:StallGuard calibrated :: lambda`, `text_sensor:Speed Lock :: lambda`,
   `text_sensor:Calibration Notice :: lambda`. DROPPED none. In particular the
   vibration detector's anchors (`interval:200ms#2`, `switch:Vibration Stall
   Detection`, `number:Vibration Threshold`) are not CHANGED.
   Sabotage: a scratch copy without `cal_keep_last_good` shows a different NEW set.

## Bench (not run in this PR; Daniel present for every motion step)

- F1 Uncalibrated unit set to Slow: a move runs at Fast (TSTEP ~68, not ~312); the
  web UI shows both notices; "StallGuard calibrated" off.
- F2 After a successful calibration: moves at the user's speed; notices clear;
  binary sensor on; survives a reboot and an update.
- F3 A failed / aborted calibration after a good one: flag stays on, WARN with the
  reason; on an uncalibrated unit: stays locked, WARN.
- F4 A unit calibrated on older firmware: calibrated after the update (seeded).
