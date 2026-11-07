# Glasscalibur TP-1, automatic — predictions

Written and committed before the bench tooling is written, on branch
`bench/tp1-automatic`. No check below had been run when this file was committed.

- Base: origin/main `40574e3` (#22 merged) = the bench build.
- Toolchain: ESPHome 2026.6.5 in an isolated venv; aioesphomeapi 45.3.1 (the one ESPHome
  installs) for the host script.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (2026-11-06)

TP-1 runs by itself: no product firmware edits, no settings changed on the unit, nothing
for Daniel to switch. A bench-only test build heats the motor with its own hold current,
and a host script on Daniel's PC runs TP-1 end to end over the native API (Home
Assistant's path) and REST (the web UI's path). Daniel powers the unit, stays nearby,
and is asked for one Button 1 press during the lockout.

## Design

**Test build** (bench only; never released, never built by CI):
`tools/bench/glasscalibur-tp1.yaml` = the existing bench wrapper
(`glasscalibur-bench.yaml`: the product plus "BENCH: simulate stall") + one test package,
`tools/bench/tp1-heater.yaml`. Nothing under `firmware/` changes. It reports Firmware
Version `dev-tp1`, so the running build is never ambiguous.

The test package:
- **Heater.** "BENCH heater" (switch, flipped by the script). While on and the motor is
  stopped, it writes IHOLD to the driver: 19 (0.6 A, the motor's rating) first; every
  3 minutes, if the reading rose less than 1 °C and is below 60 °C, +4, up to 31
  (about 0.96 A). It re-writes the level every 5 s while stopped. Off = IHOLD 0.
- **Cutoffs, in firmware, independent of the code under test:** the heater turns itself
  off (IHOLD 0) when the thermal lockout latches; at 62 °C (a backstop; the report
  records FAIL if this, not the lockout, stopped it); on no valid reading for 10 s; after
  45 minutes on; when the script's native-API connection closes (client name contains
  `tp1`); when the script's keepalive (a button the script presses every 5 s) stops for
  30 s; and at reboot (core writes IHOLD 0 at boot; the heater starts off). The 62 °C and
  10 s cutoffs use a second, independent reading of the same TMP1075 ("BENCH motor
  temperature", every 2 s), not the product's sensor or its logic.
- **Schedule path:** "BENCH: fire scheduled open" / "BENCH: fire scheduled close" run
  `schedule_open` / `schedule_close` directly, so no schedule setting changes.
- **Lockout trip on demand:** "BENCH: trip thermal lockout" runs the product's own lockout
  routine (`thermal_trip`, cause = temperature) at room temperature, for the two TP-1
  steps real heat can't reach (below). The next reading under 48 °C clears it.

**Host script** `tools/bench/tp1_run.py` (Daniel's PC): connects over the native API
(client `glasscalibur-tp1`) and REST, keeps the full device log, changes no settings,
and writes a PASS/FAIL report with times and readings. Stages, against warning 50,
gate 55, lockout 60, clear below 48:
- **S0 room temperature:** Open, Close and Set position via the API and via REST are
  accepted (each move is stopped after about 1 s; STOP via both paths works).
  Steps real heat can't reach, covered here with the bench buttons:
  - a move already running when the lockout trips: start a move, trip the lockout
    (button) -> the motor stops (State IDLE within 1 s), Thermal Lockout on, event
    `lockout`; then `cleared` on the next reading;
  - a stall back-off running when the lockout trips: start a move, "BENCH: simulate
    stall" -> back-off starts; trip the lockout -> the back-off finishes (State returns
    to IDLE from the completion poll, not at once), then `cleared`.
- **Phase A, heat to 55, then cool below 50** (the ruling-21 step):
  - at the first reading >= 50: one `warning` event (reading 50.0-52.0); commands via both
    paths still accepted;
  - at >= 55: Open, Close, Set position via both paths refused (six `refused` events,
    log "refused - motor"), no motion; scheduled close fired -> refused, kept pending;
    scheduled open fired -> replaces it (latest wins); Close via the API -> refused and
    the pending scheduled open is cancelled (log "cancelled by a newer command");
  - heater off; cool until the reading is below 49.0 °C and 60 s more: nothing moves
    (State IDLE throughout, no "running the pending" log).
- **Phase B, heat to the lockout, then cool to the clear:**
  - at the first reading >= 60: `lockout` (reading 60.0-62.0), Thermal Lockout on, the
    heater stops itself with reason "lockout", not the 62 °C backstop; no second
    `warning` (it re-arms only below 48);
  - during the lockout: Open, Close, Set position via both paths refused (log "refused -
    thermal lockout"); Auto-Calibrate refused ("CAL: refused - thermal lockout");
    STOP via both paths logged; Daniel asked for one Button 1 press -> "Close refused";
    no press within 60 s = not tested;
  - during cool-down, at a reading below 51.0 °C (lockout still set): scheduled open
    fired -> refused, pending;
  - at the first reading below 48: `cleared`, Thermal Lockout off, and the pending
    scheduled open runs at once (log "running the pending scheduled open", State
    OPENING); the script stops it after about 1 s.
- **S9 after the clear:** one command per path accepted; heater off; report written.

Not covered by the automatic run, and how:
- absolute accuracy of the set points against a reference thermometer (TP-1's ±2 °C
  versus the real plate temperature) — the run checks each event against the unit's
  own reading; the sensor offset is the separate TH-1 item;
- the chirp is audible only; the run records the lockout, Daniel hears it;
- a lockout during a running calibration: starting a calibration changes settings on
  success or abort, so it is not run; covered by #19's resolved-config checks.

## Checks (before the bench)

B1 Build: `esphome config` of the test build validates and it compiles; the branch diff
   touches nothing under `firmware/`.
   Sabotage: an undefined id in the heater lambda is refused by the compile.
B2 Independence: the regression gates, bench build (40574e3) vs test build: entities
   ADDED only the BENCH ones (the existing simulate-stall button and the new ones),
   REMOVED none; behaviour CHANGED none, DROPPED none, NEW only BENCH anchors. So every
   product automation body is identical in the test build.
   Sabotage: a scratch copy of the test build with one product action altered shows a
   CHANGED anchor.
B3 Heater facts (resolved config): start 19, step +4 at 180 s when the rise is below
   1 °C and the reading below 60, cap 31; each cutoff above is present; the heater starts
   off. Sabotage: a scratch copy without the 62 °C cutoff fails.
B4 Script dry run: against a simulated unit that follows the documented behaviour, the
   script runs every stage and reports PASS. Sabotages: a simulated unit whose REST Close
   isn't refused at 55 °C, and one where a refused Close doesn't cancel the pending open,
   each make the script report FAIL at that step.
B5 Wording: the push gate passes on the diff, the commit messages and the PR text.

## Amendment 1 — heat by Slow strokes (review, 2026-11-06; appended before more tooling; nothing above was edited)

The review replaces the heat source and allows the script to change, then restore,
three settings. Everything above stands except where this section says otherwise.

**Heat source: full strokes at Slow and 600 mA.** Moves run at the calibrated speed, so
if the unit isn't calibrated at Slow (Speed Slow, Speed Lock "Not locked", StallGuard
calibrated on), the script, below 50 °C, saves Speed, Motor Current, Calibration Status,
SGTHRS, TCOOLTHRS, Vibration Threshold and the two detector switches, sets Speed to
Slow, runs Auto-Calibrate (waits for "OK"), then sets Motor Current to 600 mA. It then
cycles full strokes. Per move it records the reading at the start, at the end and the
peak after the stop, and counts the moves to 55 and to 60 and any Obstruction event
(a false stop at 600 mA on a clear path).

**The hold-current heater is the fallback**, used only if Slow strokes peak below 60 °C
(its design and cutoffs as above).

**Stages, changed:**
- Phase A (gate at 55, no lockout): once a stroke ends at 50 °C or more, the script
  switches to Set-position moves of 10 % to creep up, so the motor stands still between
  55 and 60 for the gate checks. If one still overshoots past 60, the lockout stages run
  first and phase A runs after the clear, in a second heat cycle (short moves again;
  the heater only if moves can't stop inside 55-60). The report says which happened.
- Phase B (lockout): full Slow strokes from below 55. If a stroke takes the reading past
  60 while the motor is moving, that is the "move still running when it trips" step,
  with real heat (predicted: the motor stops within 1 s of the lockout, State IDLE).
  If the lockout only ever trips at standstill, that step uses the S0 injection
  above instead, and the report says so.
- The S0 back-off step stays an injection (a stall can't be produced on cue).

**Backstops while cycling (new):** the script never starts a stroke at or above 55 °C
(only the refusal probes), and sends STOP at a reading of 62 °C or after 10 s with no
reading. The test package also stops the motor in firmware at 62 °C on its independent
reading, and logs it; either backstop firing is a FAIL.

**Afterwards:** below 50 °C the script puts back the original Speed, runs Auto-Calibrate
at that speed and sets the original Motor Current, and reports old and new calibration
values side by side. Not fully restorable, and reported if it applies: a unit that was
never calibrated stays calibrated (the flag is never cleared), and the restored
calibration's values are re-measured, not copied back.

B4 (script dry run) now covers the Slow-stroke heating, the restore, and the overshoot
branch of phase A.

## Amendment 2 — B2 re-registered (review, 2026-11-06; appended, nothing above was edited)

The miss is kept on record. B2 predicted that, against the bench build, the behaviour
gate would show nothing changed and nothing dropped, only new BENCH anchors. The reading
(entities as predicted: 9 BENCH added, 0 removed):
- CHANGED `esphome:on_boot :: 600.0`: the only difference is the published Firmware
  Version, `dev` -> `dev-tp1`, from the test wrapper's version override (kept: a test
  build never reports a product version).
- DROPPED `interval:1s`, NEW `interval:1s#1` and `#2`: the test package's interval
  shared the tamper check's 1 s period, so the gate numbered both. The tamper interval's
  body is unchanged.

Fix: the test package's interval now uses 1500 ms, a period no product interval uses,
and a rule at the top of `tools/bench/tp1-bench.yaml` says so for later edits.

Re-registered B2: against the bench build, the only product change is the
version-publishing boot step (`dev` -> `dev-tp1`); nothing is dropped; every new anchor
is a BENCH one. Entities: only BENCH ones added, none removed. Same sabotage.

## Amendment 3 — the unit is found by its MAC (Daniel, 2026-11-06; appended before the code)

The bench unit's address can change, and no other Glasscalibur on Daniel's network may
ever get these commands. So the unit is identified by the MAC address the USB flash
reports, never by its name or a remembered address:
- `tools/bench/find_unit.py --mac <MAC>` finds the unit's current address from the PC's
  neighbour table and confirms it by asking the device itself (native API device info).
  It prints the address on Daniel's screen only.
- `tp1_run.py` requires `--mac`. After connecting it compares the unit's own MAC (device
  info) with `--mac` and refuses to send any command if they differ. Neither tool writes
  the MAC or the address into a report or log file.

M1 Dry run: with the simulated unit's MAC the run proceeds as before (PASS).
   Sabotage: with a different `--mac` the script exits before its first command (the
   simulated unit records no command).
M2 `find_unit.py`: given a neighbour table with two units, it returns only the address
   whose device reports the requested MAC. Sabotage: a requested MAC that no device
   reports returns nothing (exit 1). Tested offline with a fake table and fake devices,
   none of it committed.
