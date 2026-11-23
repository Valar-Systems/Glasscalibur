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

## Amendment 4 — TP-1 needs a learned stroke (review, 2026-11-07; appended before the code)

TP-1 does not start unless L1 learned the stroke: before its first command `tp1_run.py`
requires **Open stroke** between 94.0 and 101.0 mm, and stops otherwise. Checked as O3 in
`2026-11-bench-open-guard.md`.

## Amendment 5 — harness: logged values, streamed log, gate margin, clean stop (review, 2026-11-12; before the code)

Branch `bench/tp1-harness`, on top of `bench/heartbeat-retry` (5205da6). Nothing above is edited. What the
harness does from now on:

**A5-1 Warning value.**
- The warning check reads the value the firmware acted on from the device log:
  - its own line "Motor X degC - at or above the warning level (50)";
  - the "'Motor Temperature': Sending state Y" line just before it (full precision).
- Pass: exactly one warning event, and Y (or X when no state line is found) within 50.0-52.0.
- A logged value below 50.0 is a miss.
- Recorded as information only:
  - the last API reading before the event;
  - the first API reading at or after it;
  - the order in which the event and the first reading of 50.0 or more arrived on the API.
- The test build has no way to set a reading (its one injection, "BENCH: trip thermal lockout", runs the lockout
  directly). So that order is taken from the run's own crossing of 50 °C, not from a step before any heat.
- Registered for that crossing:
  - if the event arrives before the state message, the device log shows 50.0 or more;
  - a warning logged below 50.0 is a firmware threshold miss: the run takes the clean stop (A5-5) and reports.

**A5-2 Device log on disk.**
- Every device log line, and every row the script records, is appended to files in the run's folder
  (`device-log.txt`, `tp1-rows.txt`), each line flushed as it is written.

**A5-3 Phase A ends at 56.5 °C.**
- During a phase-A heating move, the first reading of 56.5 or more makes the script send STOP at once.
- If the strokes leave the reading between 55.0 and 56.5 (no stroke may start at 55 or above), the test build's
  heater raises it to 56.5 without motion and is then switched off.

**A5-4 Gate probes.**
- **Covered:** the six cover probes, the scheduled close/open pair, and the Close that should cancel the pending
  open.
- **Precondition:** each is sent only if the latest reading is at least 55.5, checked less than 1 s before sending.
- **Accepted:** any probe the unit accepts (State OPENING or CLOSING within 3 s) is stopped at once.
- **Void:**
  - a probe is void when the device log shows the firmware's latest reading below 55.0 at the probe's own log line
    (its refusal line or its move line);
  - a void probe is not a verdict.
- **Retry:**
  - a void probe, or one whose precondition isn't met, is retried once the reading is back at 55.5 or more;
  - the heater does the reheating without motion when it can within 10 min; otherwise one heating stroke is made
    once the reading is below 55;
  - after 3 tries the probe is "not run".
- **Miss:** a probe accepted while the firmware's reading was 55.0 or more.
- **Overall:** TP-1 reports PASS only when every gate probe has a verdict (none void, none not run).

**A5-5 Clean stop.**
- One path does all of this: STOP, heater off, the no-motion settings put back (A5-6), the files flushed, the report
  written.
- **Taken on:**
  - every FAIL row;
  - the window's end;
  - the guard lost;
  - any unexpected error;
  - an operator request: a file named `STOP` in the run's folder (checked about once a second, also during
    moves), or Ctrl+C.
- The process is ended from outside only if the clean stop itself fails, and that is recorded.

**A5-6 Restore by register value.**
- The saved settings add "IRUN value".
- The restore and the clean stop put back "IRUN value" (a register value, exact) instead of re-entering the
  Motor Current reading. Motor Current is still compared, within 20 mA.

**Simulator (`tp1_sim.py`) additions**, used only by the checks below:
- the warning and "Sending state" log lines;
- the event reaching the API before the state message;
- cooling after a stop, with the driver's mA-to-IRUN conversion (truncating; 957.54 mA full scale) and
  "IRUN value";
- faults:
  - `warn-below-50`: the warning is logged at 49.8;
  - `gate-open`: moves are accepted at 55 or more;
  - `state-lag`: the API reading trails the firmware's by 6 s;
  - `no-reheat`: the heater can't raise the reading, and strokes are refused;
  - `exit-at-600`: the simulated process ends abruptly at virtual 600 s, after writing how many log lines it
    produced;
  - `operator-stop-at-700`: the `STOP` file appears at virtual 700 s, during a move.

## Amendment 5 checks (dry runs; each with its sabotage)
- **A5-1:**
  - Default dry run: the warning check PASSes on the logged value (50.0-52.0), and the information rows give both
    pairings and the order (event first).
  - Sabotage: `warn-below-50` makes the warning check FAIL and the run take the clean stop.
- **A5-2:** with `exit-at-600`, `device-log.txt` holds every line the simulator produced before the exit.
  Sabotage: the same run with writes buffered and not flushed is missing lines.
- **A5-3:**
  - Default dry run: phase A's last heating move ends with the script's STOP less than 1 s after the first reading of
    56.5 or more; or, if the strokes stop between 55.0 and 56.5, the heater reaches 56.5 with no move.
  - Sabotage: the mid-move STOP removed, so no such STOP is recorded.
- **A5-4:**
  - (a) Default dry run: every gate probe is sent less than 1 s after a reading of 55.5 or more, and each is refused,
    with none void. Sabotage: the precondition removed, so at least one probe goes out with the reading below 55.5.
  - (b) `gate-open`: the first probe is accepted, STOP follows within 1 s, the row is a FAIL (a miss) and the run
    takes the clean stop. Sabotage: the at-once STOP removed, so the accepted move runs longer than 1 s.
  - (c) `state-lag`: a probe accepted while the device log shows the firmware below 55.0 is recorded void, stopped,
    retried after reheating, then refused. Sabotage: void detection removed, so it is recorded as a miss.
  - (d) `no-reheat`: a void or not-run probe remains and the run does not report PASS. Sabotage: a verdict that
    ignores void and not-run reports PASS.
- **A5-5:**
  - (a) `operator-stop-at-700`: STOP within 1.5 s, heater off, report written ("stopped: operator"), log flushed.
    Sabotage: the `STOP`-file check removed, so the run goes on past 702 s.
  - (b) `rest-close-accepted` (B4's sabotage): after its FAIL row the run sends STOP and puts back the no-motion
    settings, and sends no other command. Sabotage: the stop-on-FAIL removed, so commands continue after the FAIL.
- **A5-6:** default dry run, where the simulated driver truncates mA to IRUN: after the restore, "IRUN value" and the
  Motor Current reading equal the saved ones. Sabotage: the restore made through Motor Current (re-entering the
  reading) ends one IRUN step lower.
- **Full set:** these checks plus the registered dry-run sets, all as registered:
  - B4, with its two sabotages, which now also take the clean stop;
  - W1-W4 and G1-G3 (window guard);
  - O1-O3 (open guard);
  - R1, I1, I2, P1, C1, C2 (guard and prompts);
  - HB1-HB5 (heartbeat).
- **D:** the push gate passes.

### Amendment 5 note 1 — the lockout and clear values read the same way (before that code)

- Found while coding A5-1: with the event reaching the API before its reading (the order A5-1
  records), the two other checks that pair an event with the API reading are exposed the same way:
  "lockout at the first reading >= 60 (60.0-62.0)" and "cleared at the first reading below 48 °C".
  The simulator's first default dry run on the new code paired the lockout with 59.99 and reported
  FAIL (a development run, disclosed, not counted).
- Both now read the firmware's logged value as A5-1 does: "THERMAL LOCKOUT - motor X degC" and
  "Thermal lockout cleared - motor X degC", each with the "Sending state" line just before it
  (full precision). Ranges unchanged: 60.0-62.0, and below 48.0. Both pairings are recorded as
  information, as for the warning.
- Check A5-1b: the default dry run passes both on the logged values. Sabotage: the lockout check
  paired with the API reading again reports FAIL (59.99) on the same run.

### Amendment 5 note 2 — a fast-cooling profile for A5-4a and A5-4c (before those runs)

- Development runs of the default dry run (disclosed, not counted) show the simulated reading
  staying above 55.5 for the whole probe set: the probes take about 4 virtual seconds and the
  simulated drop after a stop is slow. As registered, A5-4a's sabotage and A5-4c's void probe could
  not show on it.
- The simulator gains the profile `cool-fast`: the part of the reading added while moving is 3.0 °C
  and falls away with a 4 s time constant (default 1.5 °C and 8 s), so the reading drops below 55.5
  within seconds of phase A's STOP. `state-lag` uses the same sensor model.
- A5-4a's head and sabotage both run on `cool-fast`. Head: every probe is sent less than 1 s after
  a reading of 55.5 or more (reheating in between), none void. Sabotage: the precondition removed,
  so at least one probe goes out with the reading below 55.5.
- A5-4c as registered, on `state-lag` (now with the fast-cooling sensor).
- Everything else in Amendment 5 is unchanged.

### Amendment 5 note 3 — retry after a void, `no-reheat`, and two check forms (before any counted run)

Found by reading the code against the profiles. No fault profile has been run.

**Retry after a void.**
- The precondition reads the reading as the API delivers it, so under `state-lag` it can trail the firmware.
- After a void probe the retry waits for that reading to go below 55.5 (at most 2 min), then reheats (A5-4) before
  the next try. This is "once the reading is back at 55.5 or more".
- Without the wait, the three tries could all go out while the lagging reading still shows 55.5 or more.

**`no-reheat`.**
- From the first STOP at 56 °C or more until the end of the run, the heater adds no heat and every move is refused.
- The gate probes that need a reheat are therefore "not run".
- Phase B cannot heat either, so the run ends in FAIL. That is "not PASS", as A5-4d's head predicts.

**A5-4d's sabotage** is judged on the verdict alone, because the end-to-end run already ends in FAIL. The report's
verdict is computed for a run with one gate probe not run and no FAIL row:
- head: INCOMPLETE;
- sabotage (the verdict ignores not-run): PASS.

**A5-3's sabotage** is judged on the STOP record alone, as its text says: no STOP less than 1 s after a reading of
56.5 or more is recorded. The head keeps its two alternatives.

**B4.** The two B4 sabotage profiles run in the same check script: each reports FAIL at its step and takes the clean
stop.

### Amendment 5 results (2026-11-12, head da928fe): misses, stopped here

One invocation on da928fe:
- `tp1_amend5_check.py`;
- `heartbeat_check.py`;
- the guard/prompt, window-guard and open-guard dry-run sets.

Before it: two development runs of the default dry run, disclosed in notes 1-2 and not counted.

**A5 and B4: 22 of 26 as predicted.**
- **As predicted:**
  - A5-1, A5-1b, A5-2, A5-3, A5-4a, A5-5a and A5-6, heads and sabotages;
  - A5-4b's head;
  - A5-4c's sabotage;
  - A5-4d's verdict check, head and sabotage;
  - A5-5b's sabotage;
  - B4: the default dry run PASS, and both sabotage profiles FAIL at their step and take the clean stop.
- **Miss: A5-4b's sabotage** (STOP 2 s late) was reported as 0.0 s.
  - Phase A's STOP and the probe's move are logged at the same virtual second (1314.3). The check took the first STOP
    at or after that time, which was phase A's, logged just before the move.
  - In the device log the probe's own STOP came 2.0 s after its move (1314.3 to 1316.3).
  - A check fault.
- **Miss: A5-4c's head** (`state-lag`): no probe was void.
  - All eight probes went out within about 4 virtual seconds of phase A's STOP.
  - The lowest firmware reading at a probe was 55.27 (API reading 56.68).
- **Miss: A5-4d's head** (`no-reheat`): no probe was left not run.
  - All eight probes had their verdicts in the first seconds (firmware 56.23 or more), before any reheat was
    needed.
  - Phase B then could not heat: FAIL, "no progress in 40 moves", and the clean stop.
- **Miss: A5-5b's head** (`rest-close-accepted`): the check counted only commands strictly after the FAIL row's time.
  The clean stop's STOP and "IRUN value" share that time in the simulator, so it counted none. A check fault.

**HB1-HB5:** 9 of 9 as predicted.

**Guard and prompts:** R1, I1, I2, P1, C1, C2, each with its sabotage, as registered.
- B1 had no reading (an instrument fault): the script runs the window-guard checks from its scratch folder, and an
  empty folder was given. The same reading comes from the window-guard set below.

**Window guard:** B1, W1, W2's head, W3, W4, G1-G4 as registered.
- **Miss: W2's sabotage** (no end-of-window STOP) was not caught. Its patch text targets the STOP in the old
  end-of-window code, which Amendment 5 moved into the clean stop. The patch matched nothing, so the "sabotage" copy
  was the head.

**Open guard:** O1 and its two sabotages, and O2, as registered.
- O2's sabotage printed its first variant "NOT red" and its rerun variant "red as predicted", as the script prints
  both.

### Amendment 5 note 4 — check and simulator fixes after the da928fe misses (Daniel, 2026-11-13; before the code)

Daniel ruled on the six fixes below (question tool, 2026-11-13). The da928fe misses stay on record above. Nothing in
the harness's own logic changes.

**The fixes.**
1. **A5-4b's check:** pairs the accepted probe's move line with the first STOP line *after it in the device log*,
   instead of the first STOP at or after its time stamp.
2. **A5-5b's check:** counts the commands at or after the FAIL row's time.
3. **Command delay in the simulator:** it answers every cover open, close or set, and every button press, 0.5 s after
   receiving it, which is closer to the bench (about 2 s per probe in the 2026-11-12 run). STOP, switches, selects
   and numbers stay immediate, so the guard checks' stop distances are unchanged.
4. **W2's sabotage:** removes the clean stop's STOP. Its patch must now match exactly once, or the check reports
   an instrument fault.
5. **The guard/prompt set's B1:** gets the folder that holds the window-guard checks.
6. **`no-reheat`:** uses the fast-cooling sensor, as `state-lag` does.

**Predictions for the rerun** (one head, one invocation, every check with its sabotage):
- **`tp1_amend5_check.py`:** every line as predicted. A5-1, A5-1b, A5-2, A5-3, A5-4a-d (with the verdict pair),
  A5-5a-b, A5-6 and the three B4 lines.
  - A5-4b's head: STOP less than 1 s after the move line. Sabotage: 2 s or more.
  - A5-4c's head: at least one void probe, then a later PASS for the same probe, and no FAIL row.
  - A5-4d's head: at least one probe not run, and the result not PASS.
  - A5-5b's head: only STOP and "IRUN value" at or after the FAIL.
- **HB1-HB5:** 9 of 9.
- **Guard and prompts** (B1, R1, I1, I2, P1, C1, C2): all as registered.
- **Window guard** (B1, W1-W4, G1-G4): all as registered, including W2's sabotage caught.
- **Open guard** (O1-O3): as registered.
- **Then:** TP-1 on the sealed unit (old carriage), from this branch's head, in Daniel's window ending 13:00 PT,
  only if every line above comes out as predicted.

### Amendment 5 note 5 — two tooling fixes after the 2496188 rerun (Daniel, 2026-11-13; before the change)

- The 2496188 rerun: 25 of 26 as predicted in `tp1_amend5_check.py`; HB1-HB5 9 of 9; guard and prompts all as
  registered, including B1, whose window-guard run reported all as registered (W2's sabotage caught); open guard
  as registered. Miss: A5-5b's head. The clean stop sent only STOP and "IRUN value" (at 1328.25), but the check
  compared those times with the FAIL row's time, which rows round to 0.1 s (1328.3), so it counted none. The
  separate window-guard run stopped on a scratch folder left by B1's run (an instrument fault, no reading).
- Fix 1: A5-5b's check counts commands at or after the FAIL row's time minus 0.05 s (the rows' rounding).
- Fix 2: the window-guard checks and the guard/prompt set (whose B1 runs them) each get a new, empty scratch
  folder per invocation (B1's holds a copy of the window-guard script); no folder from an earlier run is reused.
- Predictions: every line as listed in note 4.

### Amendment 5 results, rerun (2026-11-13, head df7bffb): all as predicted

One invocation (18:24:08Z-18:25:32Z): `tp1_amend5_check.py` 26 of 26 as predicted (A5-1 to A5-6 with the verdict
pair, and B4's three lines); HB1-HB5 9 of 9; guard and prompts (B1, R1, I1, I2, P1, C1, C2) all as registered; window
guard (B1, W1-W4, G1-G4) all as registered, W2's sabotage caught; open guard (O1-O3) as registered. TP-1 runs from
this head next (Daniel's ruling, 2026-11-13).

2026-11-13 · TP-1 run 3 (a42d1eb, old carriage): no TP-1 result. Preflight, the command checks, the S0 checks and the warning check came out as registered; the run ended in phase A, before the gate checks. Harness changes and a rerun follow.

## Amendment 6: verdict, data freshness, heater commands, guard data, undelivered STOP (review, 2026-11-14; before the code)

On branch `bench/tp1-harness`. Nothing above is edited. From now on, the harness does the following.

**A6-1 Verdict defaults to INCOMPLETE.**
- The run keeps a list of the phases it must complete:
  - preflight, Slow setup, S0, phase A, the gate probes, the phase A cool-down;
  - phase B, the lockout checks, the cool-down with the pending open, the restore.
- It also keeps a list of the checks registered for those phases.
- PASS needs all three of:
  1. every phase recorded as complete;
  2. every registered check present and PASS;
  3. the run's end delivered: the restore, or the clean stop with its STOP delivered.
- Otherwise the result is FAIL if any check failed, and INCOMPLETE if not.
- An error anywhere, an undelivered STOP, a phase not reached or a missing check never gives PASS.

**A6-2 Data freshness.**
- A reading older than 10 s counts as no reading. Every use of the motor reading goes through one accessor that
  returns "none" when the last state is older than 10 s.
- If there is no reading for 10 s at any point in the run (moving or not), the run takes the clean stop and ends
  INCOMPLETE ("no reading for 10 s").

**A6-3 Heater commands.**
- The heater is switched on, or kept alive, only with a reading at most 2 s old. Otherwise the command is not sent
  and the reheat counts as failed.
- The TP-1 build already has firmware-side limits, so nothing is added there. It stops the heater:
  - after 45 min on;
  - after 30 s with no keepalive;
  - when its own reading reaches 62 °C;
  - when the script's connection closes;
  - when a reading has been missing for 10 s;
  - on a lockout.
  - Source: tp1-bench.yaml, stop codes 1-7.

**A6-4 Guard data.**
- `open_guard.py` reports not watching once no state has come from the unit for 10 s while it is connected. This
  counts the same as a lost connection.
- The heartbeat then reads not OK, so moves are refused or stopped.

**A6-5 Undelivered STOP.**
- If the clean stop's STOP command raises an error, or the unit cannot be reached, the report's first line is
  "unit state unknown - check the unit". The result is INCOMPLETE, or FAIL if a check failed.

**Simulator** (used only by these checks): the fault `data-stop-at-700`, where from virtual 700 s the simulated unit
sends no states and no log lines, and every command after that raises a connection error.

### Checks (dry runs, each with a sabotage)
- **A6-1:**
  - (a) Default dry run: PASS, all phases complete. Sabotage: a phase skipped (the copy skips the gate probes) must
    not give PASS.
  - (b) A check dropped: a copy that never records "lockout at the first reading >= 60" must not give PASS.
  - (c) An exception in the clean stop (`rest-close-accepted`, with a copy whose clean stop raises after STOP) must
    not give PASS. That run's head gives FAIL from its registered miss.
  - Sabotage for (b) and (c): the old verdict rule (PASS when no FAIL row) gives PASS.
- **A6-2:** `data-stop-at-700`: the run takes the clean stop within 10-12 s of the last state, and ends INCOMPLETE
  with "no reading for 10 s". Sabotage: the freshness check removed, so the run keeps going on the stale reading.
- **A6-3:** a copy that makes the reading 3 s old before a heater-on: the heater command is not sent. Sabotage: the
  age check removed, so it is sent.
- **A6-4:** guard dry run against the simulator with `data-stop-at-700`: the heartbeat reads not OK within 12 s of
  the last state. Sabotage: the data-age check removed, so it stays OK.
- **A6-5:** `data-stop-at-700`: the report's first line is "unit state unknown - check the unit". Sabotage: the line
  removed, and it is missing.
- **Full set, all as registered:** these checks; Amendment 5's set and B4; W1-W4 and G1-G4; O1-O3; R1, I1, I2, P1,
  C1, C2; HB1-HB5.
- **D:** the push gate passes.

### Amendment 6 note 1 (before the code): A6-1(c) and A6-3 made checkable

- A6-1(c) runs on `operator-stop-at-700`, not `rest-close-accepted`. That run has no FAIL row, so the old
  rule would give PASS if the clean stop failed before writing its row (as in the 2026-11-13 run). The copy's clean
  stop raises right after sending STOP. Head (new verdict): not PASS. Sabotage (old rule): PASS.
- A6-3: the sensor updates every 3 s, so a heater command first waits up to 4 s for a reading at most 2 s old, and
  is not sent if none comes. Check (unit level, simulator): with the last reading made 3 s old and no new reading
  arriving, the heater-on is not sent. Sabotage: the age check removed, so it is sent.

### Amendment 6 note 2 (before any check run): two instruments follow the code

- W2's sabotage (window-guard checks) removes the clean stop's STOP. That line now sits inside the clean stop's
  error handling, so the sabotage's patch text follows it (still exactly one match, or an instrument fault).
- A5-4d's verdict check builds a run in isolation. Under A6-1 a run with phases or checks missing is INCOMPLETE
  whatever else holds, so the check now first marks every phase done, every registered check PASS and the end
  delivered, then adds one gate probe not run. Head: INCOMPLETE. Sabotage (not-run ignored): PASS. As registered.
- Nothing else changes.

### Amendment 6 results (2026-11-14 PT, head 09f2617): one miss, stopped here

One invocation (2026-11-15 02:42:25Z-02:43:56Z), one script after another:
- `tp1_amend6_check.py`;
- `tp1_amend5_check.py`;
- `heartbeat_check.py`;
- the guard/prompt, window-guard and open-guard dry-run sets, each in a fresh folder.

**A6: 13 of 14 as predicted.**
- **As predicted:**
  - A6-1a, A6-1b and A6-1c, heads and sabotages;
  - A6-2's sabotage;
  - A6-3, A6-4 and A6-5, heads and sabotages.
- **Miss: A6-2's head** (`data-stop-at-700`) reported as outside its window.
  - The run stopped with "stopped: no reading for 10 s" at 709.5 s and ended INCOMPLETE.
  - The registered window is "within 10-12 s of the last state". The check encoded it as fixed times, 710.0 to
    712.5 s, as if the last state came at 700.0 s.
  - In the run's device log the last Motor Temperature state came at 699.0 s (the sensor updates every 3 s), so the
    stop came 10.5 s after it.
  - A check fault, by this reading; the code and the result are not changed until a ruling.

**The rest, all as registered:**
- A5 and B4: 26 of 26.
- HB1-HB5: 9 of 9.
- Guard and prompts (B1, R1, I1, I2, P1, C1, C2).
- Window guard (B1, W1-W4, G1-G4), W2's sabotage caught.
- Open guard: O1 and its two sabotages, and O2.
  - O2's sabotage printed its first variant "NOT red" and its rerun variant "red as predicted", as the script
    prints both.

**Not run in this invocation: O3** (TP-1 with Open stroke unknown stops before its first command). None of these
scripts carries it. It goes into the rerun.

### Amendment 5 rerun record: correction note (ruling 77 a, 2026-11-16)
- The rerun record above says "open guard (O1-O3) as registered". O3 can't be confirmed: no script in that set
  carried O3. The line above is left as it was. O3 now has its own line (Amendment 6 note 3).

### Amendment 6 note 3 (ruling 77 a; before the code and before any rerun)
The A6-2 miss is a check fault (ruling 77 a) and stays on the record. Changes, all in the check scripts:
- **A6-2's window:** measured from the run's own last "Motor Temperature" state line in its device-log.txt. The stop
  row "stopped: no reading for 10 s" comes 10.0-12.0 s after it, and the result is INCOMPLETE. The sabotage is
  unchanged (freshness removed: no such row, and the run goes on past 712.5 s).
- **O3, its own line** (in tp1_amend6_check.py):
  - Head: tp1_run.py --sim --sim-fault fresh (Open stroke not learned). The L1 stroke check is recorded FAIL, the
    simulated unit receives no command, and the result is FAIL.
  - Sabotage: a copy without the early return after the L1 check sends at least one command.
- **Readings must match their registered reason**, not only an outcome or a return code. In every check script of
  the set (tp1_amend6_check.py, tp1_amend5_check.py, heartbeat_check.py, and the private guard/prompt, window-guard
  and open-guard sets), and in the private #35 harness:
  - (1) Captured output is stripped of terminal escape codes (CSI and OSC sequences) before any text match.
  - (2) Captured output containing "Filename too long" makes the reading an instrument fault. It prints
    "INSTRUMENT", is counted neither as predicted nor as a miss, and may be rerun with disclosure.
  - (3) A run that leaves neither a report nor rows is "no reading", an instrument fault the same way.
  - (4) Each sabotage (and each head whose registered outcome is "not PASS") is "as predicted" only with its reason:
    - A6-1a sab: INCOMPLETE with "gate" in phases_missing.
    - A6-1b head: INCOMPLETE with the dropped check in checks_missing. A6-1b sab: PASS.
    - A6-1c head: INCOMPLETE, no clean-stop row, phases missing. A6-1c sab: PASS with no clean-stop row.
    - A6-2 sab: no "no reading" row, and rows after 712.5 s.
    - A6-3 sab: heater-on sent. A6-4 sab: no not-OK beat within 12 s of the last state.
    - A6-5 sab: first line "# TP-1 automatic".
    - O3 sab: at least one command.
    - A5-1 sab: warning row FAIL, plus the "miss: one warning event" clean-stop row.
    - A5-1b sab: lockout row present and FAIL.
    - A5-2 sab: exit count read, and fewer lines on disk.
    - A5-3 sab: no STOP-gap row at all.
    - A5-4a sab: a probe sent below 55.5 or late.
    - A5-4b sab: move-to-STOP gap measured, >= 1.0 s.
    - A5-4c sab: no void row.
    - A5-4d verdict sab: PASS.
    - A5-5a sab: rows after 702 s.
    - A5-5b sab: a FAIL row, then a command other than STOP or a put-back.
    - A5-6 sab: Speed/Current row FAIL naming IRUN value.
    - HB1 sab: writer raised PermissionError. HB2 sab: PermissionError raised. HB3 sab: OK returned, "refused read
      taken as OK". HB5 sab: STOP more than 5 s after the last beat.
    - The private sets' sabotages:
      - R1: no "reconnected", and the open not stopped.
      - I1: the open sent.
      - I2: no STOP.
      - P1: missing from the record.
      - C1: Button Lock left on.
      - W1: no "NOT STARTED", and commands sent.
      - W2: no STOP at the end.
      - G3: no FAIL, firmware target reached.
      - O1: STOP at 97.0-97.5 / hard-stop hit.
      - O2: close ended on S5, not stopped, stroke learned.
    - The C2 heads (exit 4) also need their "NOT STARTED" message.
- **Matcher check M1** (new tools/bench/check_reading.py, which the scripts import):
  - --selftest:
    - M1a: an error line with ESC[K codes around the name is found after stripping;
    - M1b: output with "Filename too long" is an instrument fault;
    - M1c: clean output is neither.
  - --sabotage: a copy whose strip does nothing turns M1a red; a copy without the "Filename too long" rule turns M1b
    red; exactly their rows, each.
- **Full set rerun, once, on one head** (all as registered):
  - A6-1 to A6-5 with O3;
  - Amendment 5's set and B4;
  - HB1-HB5;
  - the guard/prompt, window-guard and open-guard sets;
  - M1 selftest and sabotage.
  - No instrument fault is expected (nothing in this set compiles or clones).
- The #35 harness (dk_checks.py, private) gets the same rules (P-X's sabotage then runs from a short path). It is
  exercised through M1, and not rerun for this merge: #35's results stand as reported.
- Then the push gate, a PR to main, and a squash merge when everything comes out as registered (bench tooling only,
  ruling 77 a). The branch also carries #34's heartbeat retry (HB1-HB5 in this set). #34 is closed as included in
  the merge.

### Amendment 6 note 3 results (2026-11-16, head 57693ff): three misses, stopped here, not merged
One invocation (20:34:25Z-20:36:01Z), one script after another.

**Matcher M1:** selftest M1a-M1c ok. Sabotage: S-NOSTRIP turns M1a red, S-NOFAULT turns M1b red. As predicted.

**A6 with O3: 13 of 16 as predicted.**
- **As predicted:**
  - A6-1a head and sabotage (INCOMPLETE, phases missing ['gate']).
  - A6-1b sabotage (PASS under the old rule).
  - A6-1c head (INCOMPLETE, no clean-stop row, 7 phases missing) and sabotage (PASS, no clean-stop row).
  - A6-2 head: last state 699.0, stop row at 709.5 = +10.5 s, INCOMPLETE.
  - A6-3, A6-4 and A6-5, heads and sabotages.
  - O3 head: L1 FAIL, 0 commands, result FAIL.
- **Miss: A6-1b head.** "Registered reason not seen". The reading is INCOMPLETE with checks missing ['lockout at the
  first reading >= 60']. The check listed is the dropped one, under its registered prefix. The new reason predicate
  looked for the full row name "lockout at the first reading >= 60 (60.0-62.0)". A check fault.
- **Miss: A6-2 sabotage.** "Registered reason not seen".
  - The reading has no "no reading for 10 s" row (as originally registered). But it has no rows after 712.5 s
    either: the run ends at 709.5 s with "stopped: unexpected error ConnectionError", at its next command after the
    simulator's cut-off.
  - Note 3's added reason ("the run goes on past 712.5 s") was wrong in fact.
- **Miss: O3 sabotage.** Predicted "at least one command"; read 0 commands, result FAIL.
  - Removing the early return after L1 changes nothing: since Amendment 5, a FAIL row itself takes the clean stop
    ("miss: L1 has learned the stroke ..." at 5.0 s). The sabotage was ineffective, so O3's sensitivity is not shown.
- **Proposed** (needs a ruling):
  - A6-1b's reason matches the registered prefix;
  - A6-2's sabotage reason is "no 'no reading for 10 s' row" (as first registered), with the stop row's reason
    recorded;
  - O3's sabotage makes the L1 check pass with the stroke unknown (its condition forced true), so the run must
    then send a command.
  - Then the full set reruns once.

**The rest, all as registered:**
- A5 and B4: 26 of 26.
- HB1-HB5: 9 of 9.
- Guard and prompts: 23 lines, ALL PASS, including C1's sabotage "the lock left on" and both C2 lines with "NOT
  STARTED" said.
- Window guard: 17 lines, ALL PASS (W1's sabotage now asserts its patch matches once).
- Open guard: O1 and its two sabotages, O2, and O2's rerun variant.

**No instrument fault.** Background: the run was registered with bgcheck and the check after it read 0 running.

### Amendment 6 note 4 (ruling 82 a; before the code and before any rerun)
The three misses of the note 3 results stay on the record, as check and registration faults in the new code.
- **(1) A6-1b head:** the reason is "INCOMPLETE, with the registered prefix 'lockout at the first reading >= 60' in
  checks_missing" (the prefix as REQUIRED_CHECKS lists it, not the full row name).
- **(2) A6-2 sabotage:** the reason returns to the original registration: no "stopped: no reading for 10 s" row. The
  row that ended the run is recorded alongside, not judged.
- **(3) O3 sabotage:** the copy forces the L1 stroke check's condition true while the stroke is unknown. The run must
  go on and send at least one command (reason: commands > 0).
- **(4) A6-2b, new:** a simulator profile `states-stop-at-700`. From virtual 700 s no states and no log lines reach
  the API, but commands still succeed: run 3's situation while the connection stayed up.
  - Head: the clean stop's "stopped: no reading for 10 s" row comes 10.0-12.0 s after the run's own last Motor
    Temperature state (from its device log), and the result is INCOMPLETE.
  - Sabotage (freshness removed, the A6-2 copy): no such row, and the run goes on past 712 s (rows with t_s > 712.0).
- **Predicate review (82 a), done before the run:** each reason predicate in the scripts is listed against its
  registered wording, in the private record. Any mismatch is fixed before the run, not after.
- **Paths:** the bench branch now lives at E:\gc\wg (owner instruction, 2026-11-16). The private sets and the open
  guard set read the bench folder from there.
- **Then:** the full set reruns once, on one head (A6-1 to A6-5, A6-2b, O3; A5 and B4; HB1-HB5; the guard/prompt,
  window-guard and open-guard sets; M1). If everything comes out as registered: push gate, PR, CI, squash merge
  (bench tooling only), and #34 closed as included.

### Amendment 6 note 4 results (2026-11-17 04:32:05Z-04:33:30Z, head f445e22): one miss, stopped here, not merged
- Predicate review done before the run (private record): two mismatches fixed first (HB1 now reads the writer's
  result only; G3 also needs the firmware target, 101.0 mm).
- **Matcher M1:** selftest and sabotage as predicted.
- **A6 with A6-2b and O3: 17 of 18.**
  - As predicted:
    - A6-1a/1b/1c heads and sabotages (A6-1b head: INCOMPLETE with the prefix in checks_missing);
    - A6-2 head (+10.5 s after the last state at 699.0, INCOMPLETE) and sabotage (no "no reading" row);
    - A6-2b head (states-stop-at-700, commands succeed: stop row at 709.5 = +10.5 s, INCOMPLETE);
    - A6-3, A6-4 and A6-5;
    - O3 head (L1 FAIL, 0 commands, FAIL) and sabotage (L1 forced true: 54 commands).
  - **Miss: A6-2b sabotage** (freshness removed). Registered: "the run goes on past 712 s".
    - Reading: no "no reading for 10 s" row and no rows after 712 s. The run ended at 709.5 s on
      "miss: script backstop: no reading for 10 s while moving", the harness's older in-move backstop
      (tp1_run.py line 314), with result FAIL.
    - The sabotage removes only the A6 freshness check, so the older backstop still stops a run that is moving.
    - My registration fault: I took the outcome from the ruling's wording without checking for the older backstop.
- **The rest, all as registered:** A5 and B4 26/26; HB1-HB5 9/9; guard and prompts ALL PASS; window guard ALL PASS;
  open guard O1, O2 and O2's rerun variant.
- **Proposed** (needs a ruling): either
  - (a) the A6-2b sabotage also removes the in-move backstop, so the run goes on past 712 s as registered; or
  - (b) A6-2b's sabotage is re-registered as "no 'no reading for 10 s' row; the run ends on the in-move backstop (FAIL)
    or goes on past 712 s".
  - Then rerun once and merge if everything comes out as registered.

### Amendment 6 note 5 (registered 2026-11-23, before the change and before the rerun)
- **A6-2b sabotage, re-registered** (option (b) of the note 4 results). Freshness removed: there is no "stopped: no
  reading for 10 s" row, and either
  - (i) the run ends on the in-move backstop: a row whose step starts "miss: script backstop: no reading for 10 s
    while moving", with the run's result FAIL; or
  - (ii) rows go on past 712.0 s.
- The reason predicate is checked against this wording before the run. The row that ended the run is recorded
  alongside, as before.
- Nothing else changes. The whole set reruns once: matcher M1 and its sabotage, A6 with A6-2b and O3, A5 and B4, the
  heartbeat checks, the guard and prompts, the window guard, and the open guard.
- If everything comes out as registered: push and open the PR; #34 closes as included.

### Amendment 6 note 5 results (head 5e1c8f9): everything as registered
- **First attempt (2026-11-23 21:05:46Z-21:06:58Z), an instrument fault:** B1 in the guard-and-prompts set runs
  wg_test.py from its own output folder, and the runner had not put it there ("can't open file"), so B1 had no
  reading. Everything else in that attempt came out as registered, A6 18/18 included. The runner now copies
  wg_test.py first, and the whole set reran once.
- **Rerun (23:26:07Z-23:27:21Z):**
  - matcher M1 selftest and sabotage as predicted;
  - A6 with A6-2b and O3: 18 of 18. The A6-2b sabotage: no "stopped: no reading for 10 s" row; the run ended on
    "miss: script backstop: no reading for 10 s while moving", result FAIL, as note 5 registered;
  - A5 and B4 26/26; HB1-HB5 9/9;
  - guard and prompts ALL PASS (B1 included); window guard ALL PASS;
  - open guard O1, O2 and O2's rerun variant as predicted.
- Next: push and open the PR; #34 closes as included.
