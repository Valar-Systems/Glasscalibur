# Glasscalibur calibrated speed — predictions

Written and committed before any code change on branch `feature/calibrated-speed`.
No check below had been run when this file was committed, except the speed-writer
survey (S0), which was read first because item 3 makes the design depend on it.

- Base: origin/main `7c21ac5` (PR #10 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.
- Target: `firmware/esphome/Glasscalibur-esphome.yml`.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

PR #10's three decisions stay. Calibration tunes StallGuard for the speed it ran
at, so a unit calibrated at one speed and then switched to another runs with a
threshold tuned for the wrong speed.
1. Save the speed each successful calibration ran at, with the calibration. Units
   carried over from older firmware: their currently saved speed is the calibrated
   speed, logged.
2. If the speed setting differs from the calibrated speed, every move runs at the
   calibrated speed; under the Speed control: "Speed change needs recalibration -
   running at <calibrated speed>". A successful calibration at the new speed clears it.
3. First check whether anything switches speed on its own (quiet/night speed,
   schedule). If so, store a calibration per used preset instead of locking.
Bench check F5.

## S0 — speed-writer survey (read before this file; it decides item 3)

Writers of `global_speed` in the product, core (valar-motion v0.3.0) and the
scheduling mixin: the Speed select's set_action and core's raw Speed number
set_action — both user actions (web UI / Home Assistant). No quiet or night speed,
no schedule, calibration or auto-tune path writes the speed. So: the lock (item 2),
no per-preset storage. (A user's own Home Assistant automation could still change
the setting; the lock then holds the calibrated speed.)

## Design

- New persisted global `cal_speed` (int, 0 = not recorded): the speed (steps/s) of
  the last successful calibration, written in calibration's success branch next to
  `cal_speed_at`. Never cleared; a failed calibration keeps it (PR #10).
- Boot (on_boot 500, after PR #10's seed): a calibrated unit with `cal_speed` 0 was
  calibrated before this was recorded -> `cal_speed` = the saved speed setting,
  logged at INFO with the value.
- Effective speed (one expression, substitution `effective_speed`): during a
  calibration the setting (calibration tunes for it); uncalibrated -> Fast (PR #10);
  calibrated -> `cal_speed` (which equals the setting unless it was changed since).
  Applied at the same nine sites as PR #10.
- "Speed Lock" (under the Speed select): uncalibrated -> "Speed locked to Fast until
  calibration has run"; calibrated and setting != `cal_speed` -> "Speed change needs
  recalibration - running at <name> (<n> steps/s)" (name = Slow / Medium / Fast for
  a preset value, else the number alone); otherwise "Not locked".
- "Calibration Status": its STALE suffix compares the setting with `cal_speed`
  (the calibrated speed now in force) instead of `cal_speed_at`, so a carried-over
  unit is not shown STALE for the speed it is now treated as calibrated at.
- `cal_keep_last_good`'s WARN for a calibrated unit names the calibrated speed.

## Checks (head vs base 7c21ac5)

C1 `esphome config` validates, `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in the effective-speed substitution is refused.
S1 Resolved head: global `cal_speed`, restore_value true, initial '0'.
   Sabotage: base has none.
S2 `sites.py … stepper.set_speed`: the same 9 anchors as on the base (no site added
   or lost), and every product site's speed lambda (all except core's on_boot 600 and
   core's own number:Speed action) reads `cal_speed`: 8 product lambdas.
   Sabotage: on the base, 0 speed lambdas read `cal_speed`.
S3 Head: on_boot 500 sets `cal_speed` from `global_speed` for a calibrated unit with
   `cal_speed` 0, and auto_calibrate's success branch sets `cal_speed`.
   Sabotage: neither on the base.
G1 Entity gate: clean (0 added, 0 removed).
   Sabotage: a scratch copy of the head with "Speed Lock" renamed shows 1 removed,
   1 added.
G2 Behaviour gate: CHANGED exactly `esphome:on_boot :: 500.0`,
   `cover:Glasscalibur :: position_action`, `select:Speed :: set_action`,
   `number:Speed :: set_action`, `script:drive_open`, `script:drive_close`,
   `script:auto_calibrate`, `script:cal_keep_last_good` (each `:: then`),
   `text_sensor:Speed Lock :: lambda`, `text_sensor:Calibration Status :: lambda`.
   NEW none. DROPPED none.
   Sabotage: a scratch copy with the base's Calibration Status lambda shows a
   different CHANGED set.

## Bench (not run in this PR; Daniel present for every motion step)

- F5 Calibrated at Medium: switch the setting to Slow -> moves still run at Medium
  (TSTEP ~144, not ~312) and Speed Lock reads "Speed change needs recalibration -
  running at Medium (2600 steps/s)"; Calibration Status shows STALE. Recalibrate at
  Slow -> moves at Slow, Speed Lock "Not locked", no STALE; survives a reboot. A unit
  calibrated on older firmware: after the update the log names its saved speed as the
  calibrated speed and it runs at its setting.

## Note, 2026-11-06 (appended before the bench; nothing above was edited)

F5's last sentence ("A unit calibrated on older firmware: after the update the log names
its saved speed as the calibrated speed and it runs at its setting") is out of date: #12
(`2026-11-recorded-cal-speed.md`) made such a unit run at the speed its calibration
recorded, not its setting. On the bench, F5 runs without that sentence and F6 covers the
older-firmware case.
