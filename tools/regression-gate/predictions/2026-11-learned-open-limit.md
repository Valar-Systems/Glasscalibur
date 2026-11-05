# Glasscalibur learned open limit — predictions

Written and committed before any code change on branch `feature/learned-open-limit`.
No check below had been run when this file was committed.

- Base: origin/main `7fd24b4`.
- Toolchain: ESPHome 2026.6.5 in an isolated venv (local Python 3.13; CI Python 3.11).
- Target: `firmware/esphome/Glasscalibur-esphome.yml`.

Rules, as before. A result that differs from its prediction: stop and report;
neither the prediction nor the code is edited to make it pass. A run that
produces no reading is an instrument failure: it may be rerun, and is reported
as such. Every check has a sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

A new carriage moves the open switch (S4) close to the mechanical hard stop
(window opens ~3.91" instead of ~3.76"). Distances are from the close-switch (S5)
trigger = position 0, at the geared 3066.7 steps/mm (Tr6x1 leadscrew, 12T:23T).
New carriage: S4 at 99.3 mm [98.8-99.8], hard stop 100.6 mm [100.35-100.9], S4 at
least ~0.9 mm before the hard stop on any one unit; closed end: the carriage hits
the front plate 0.7-1.2 mm past the S5 trigger. Old carriage: S4 ~95.5 mm, hard
stop ~99.1 mm. Both must work.

1. Learned open limit: on each S4 trigger during an open that started from a fresh
   S5 home with no stall events, record the step position; accept only 94.0-101.0
   mm, else fault "open switch position out of range" and keep the previous value;
   persist accepted values, writing flash only when the value changes by more
   than 0.05 mm; diagnostic sensor "Open stroke" in mm (2 decimals), logged at
   INFO on every open.
2. Open target = learned + 0.5 mm; before anything is learned, 101.0 mm. The old
   ~111 mm overshoot goes.
3. An open that reaches its target without S4: stop, fault "open limit switch not
   detected", no re-zero from it, closing still allowed.
4. Stop immediately on S4 (no ramp past the switch); log the step count at the
   trigger and after the motor has stopped; coast under 0.3 mm (~920 steps).
5. A close may run at most 0.6 mm past the last calibrated zero; if S5 has not
   triggered by then, stop and fault "close limit switch not detected".
6. StallGuard stall detection defaults ON.
Plus: the new faults in the web UI, a version bump, everything else unchanged.

## Design (as it will be implemented)

Constants (board wrapper, `Mechanical constants`): `steps_per_mm` 3066.6667;
`open_learn_min_mm` 94.0, `open_learn_max_mm` 101.0, `open_default_mm` 101.0,
`open_margin_mm` 0.5, `open_persist_delta_mm` 0.05, `close_overtravel_mm` 0.6,
`coast_limit_mm` 0.3. `max_distance_steps` (341387 = 111.3 mm) and
`max_distance_revs` are removed. In steps (int truncation): 101.0 mm = 309733,
0.5 mm = 1533, 0.6 mm = 1840, 0.05 mm = 153, 0.3 mm = 920.

- `open_stroke_steps` (persisted, 0 = not learned) holds the learned S4 trigger
  position. It is written only when a new accepted value differs from it by more
  than 153 steps (0.05 mm); ESPHome writes a restore_value global to flash only
  when its value changes, so this is the only flash write.
- Position scale (cover 0..1): the learned stroke, or 101.0 mm before learning.
  Open target: learned + 1533 steps, or 309733. Close target: -1840 steps.
  Set-position 100 % runs the open, 0 % runs the close; anything between keeps
  today's proportional move on the new scale.
- "Fresh S5 home": set when S5 re-zeroes the counter (a close or idle press, or
  S5 pressed at boot). Any motion start clears it; an open (drive_open) that
  starts with it set is a learning open. A stall (StallGuard or vibration,
  including calibration's) clears the learning open. So calibration learns on
  its open leg's first attempt only, and only if that attempt reaches S4 cleanly.
- S4 press (direction gate unchanged): record the trigger count, stop at once,
  log `LIMIT 1 PRESSED` and the trigger count at INFO. Learning open: accept or
  fault as in item 1. Not a learning open and a value is learned: re-sync the
  counter to the learned position (drift correction, as today's re-sync to the
  end of travel). Out-of-range learning: no re-sync. 300 ms later log the stopped
  count and the coast (WARN if over 920 steps).
- The 200 ms completion poll raises "open limit switch not detected" when an open
  to the end arrives at its target with S4 released, and "close limit switch not
  detected" when a close to the end arrives at -1840 with S5 released; the motor
  has already stopped at its target; no re-zero; both directions stay allowed.
  Not raised during calibration: there the leg already treats "count arrived, no
  switch" as step loss and escalates, as today. S4 clears the open fault, S5 the
  close fault, an accepted learning the range fault.
- Faults: a new diagnostic text sensor "Fault" (web UI Diagnostics group):
  "None" or the active faults joined by "; ". Each is logged at WARN when raised.
- Calibration keeps its logic; its re-claims and deadlines use the open target
  / 101.0 mm instead of 341387. The back-off clamp and the auto-tune end-zone use
  the new scale.
- "StallGuard Enabled": `restore_mode: RESTORE_DEFAULT_ON` (a unit that already
  stored a state keeps it).
- Coast (item 4): the stop is already immediate (`stepper_deceleration: inf`;
  stop writes VACTUAL 0 at once). Expected coast after the trigger event: a few
  steps (the UART write). Not measurable without the bench; the log lines make it
  visible on the unit.
- Version: CHANGELOG `[Unreleased]` becomes `[2.2.0] - unreleased` with these
  entries added; the tag stays Daniel's call (the version on a unit comes from
  the release tag).

## Checks (run on the head; base = 7fd24b4)

C1 `esphome config` validates and `esphome compile` succeeds (2026.6.5), and CI is
   green on the PR head.
   Sabotage: a scratch copy of the head with an undefined id in the new S4 lambda
   fails `esphome compile`.
S1 `max_distance_steps` and `341387` occur 0 times in `firmware/esphome/*.yaml`
   and `*.yml` on the head.
   Sabotage: the same count on the base is > 0.
S2 Resolved config: the "StallGuard Enabled" switch has `restore_mode:
   RESTORE_DEFAULT_ON` on the head.
   Sabotage: the base resolves to `RESTORE_DEFAULT_OFF`.
S3 The head's substitutions give, by int truncation of mm x steps_per_mm: 309733
   (101.0), 1533 (0.5), 1840 (0.6), 153 (0.05), 920 (0.3).
   Sabotage: the same computation with steps_per_mm 1600 gives other values.
G1 Entity gate, base -> head: ADDED exactly `sensor Open stroke` (DIAGNOSTIC) and
   `text_sensor Fault` (DIAGNOSTIC); REMOVED none.
   Sabotage: a scratch copy of the head's resolved config with "Open stroke"
   renamed shows a different ADDED row.
G2 Behaviour gate, base -> head:
   CHANGED exactly: `binary_sensor:Open Limit Switch :: on_press`,
   `binary_sensor:Close Limit Switch :: on_press`, `esphome:on_boot :: 500`,
   `cover:Glasscalibur :: lambda`, `cover:Glasscalibur :: position_action`,
   `script:motion_halt`, `script:drive_open`, `script:drive_close`,
   `script:auto_calibrate`, `script:cal_leg`, `script:stall_response`,
   `script:sg_autotune_eval` (each `:: then`), `interval:200ms#1 :: then`.
   NEW exactly: `script:s4_coast_report :: then`, `sensor:Open stroke :: lambda`,
   `text_sensor:Fault :: lambda`. DROPPED none.
   Sabotage: a scratch copy of the head's resolved config without
   `s4_coast_report` shows a different NEW set.

## Bench (not run in this PR; needs Daniel present for every motion step)

- L1 Fresh unit, close to S5, open: "Open stroke" appears within 94-101 mm; the
  next open's target is that + 0.5 mm.
- L2 Coast at Fast: the stopped count minus the trigger count is under 920.
- L3 S4 disconnected: the open stops at its target, "open limit switch not
  detected", position unchanged; a close still runs.
- L4 S5 disconnected: the close stops 0.6 mm past zero, "close limit switch not
  detected".
- L5 A reboot keeps the learned value; a repeat open within 0.05 mm logs "not
  saved".
- L6 Old carriage: learns ~95.5 mm and opens to ~96.0 mm.

## Amendment 1 — self-review fixes, before the code changes (appended; nothing above was edited)

The checks above were run on the first implementation (results in the PR). A
review of that code found two defects in the design as written; both are fixed
before the PR opens, and the checks re-run on the fixed head.

1. A learning open could teach from the wrong press. `learn_this_open` survived
   a user STOP and an arrival without S4, so a later S4 press while idle (an
   intermittent switch at the 101.0 mm target, say) would have been taken as the
   stroke, and 101.0 mm is inside the accepted range. Fix: learning needs the S4
   press to come while OPENING (captured before the stop), every S4 press ends
   the learning open, and the completion poll clears it on arrival.
2. Before anything is learned, an S4 press that is not a learning open left the
   counter as it was. A unit whose counter is low (a fresh unit with counter 0
   while the window is part-open, for example) then ran a close short of S5 and
   raised a false "close limit switch not detected" mid-travel. Fix: with
   nothing learned, S4 re-syncs the counter to open_default_mm (101.0 mm), as
   today's S4 re-syncs to 341387. That over-estimates the position, so a close
   runs long and S5 stops it; the next open from that home learns.

Known behaviour after an update from older firmware (documented, not changed):
the saved counter was kept on the old 111 mm scale (S4 re-synced to 341387), so
until the first full close an open can stop short and report "open limit switch
not detected". One full close re-zeroes it.

Checks: C1, S1-S3, G1, G2 re-run on the fixed head with unchanged predictions
(the fixes stay inside anchors already listed as CHANGED; one new global).
