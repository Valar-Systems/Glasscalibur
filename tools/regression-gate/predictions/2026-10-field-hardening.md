# Glasscalibur field hardening — predictions

Written and committed before any code change on branch `fix/field-hardening`.
No check below had been run when this file was committed.

- Base: origin/main `e42be0d` (= tag v2.1.0).
- Toolchain: ESPHome 2026.6.5 in an isolated venv (local Python 3.13; CI Python 3.11).
- Release target: `firmware/esphome/Glasscalibur-esphome.yml` ("GC").
- Bench-only target (never built by CI, never on a customer unit): `tools/bench/glasscalibur-bench.yaml`.

Rules. A result that differs from its prediction: stop and report; neither the
prediction nor the code is edited to make it pass. A run that produces no
reading is an instrument failure: it may be rerun, and is reported as such.
Every check has a sabotage that must turn it red; a check that cannot go red
counts as failed.

## Rulings (verbatim)

Source: the reviewer chat, 2026-10-30, pasted into the working session by Daniel.
One paragraph is omitted here at its own instruction; it is recorded outside
this repository.

> The verification is careful and the design is right: one user-STOP path, one shared abort, one shared stall response, and internal stops kept apart from the user's. Go ahead, predictions first (R5), with these rulings.
>
> R1a yes: pin both external components at the shipped commits (slimcdk b5f0e44, esphome-lis2dh12 f9cbb99), shown byte-identical (P1.6).
> R1b yes: fix gate.py first, since part of the item 3 and 4 evidence depends on it.
> R1c yes: the 5 s timer goes; the flag lives until the back-off ends.
> R1d yes.
> R1e yes.
> R1f: defer, on one condition. First state what a user Open, Close or Set-position does today in each calibration phase. If any of them can move the window with the detectors off, or start a motion STOP can't end cleanly, it comes into this PR. Otherwise it's deferred and written up as a known limitation in the calibration doc.
> R1g yes. The bench-only "Simulate stall" is never in a release target: G1 and P5.1 must show it absent from all three release builds.
> R1h yes: document only, with the follow-up named.
> R1i yes.
> R2 yes: one event per stall that stops a motion outside calibration and homing; a jam during the back-off gives a second.
> R3 yes: the real direction during the back-off, with no new state, so Home Assistant users see nothing new, only a correct state.
> R4: the B5 GETs (read-only) and the throwaway workflow_dispatch branch (deleted afterwards) are approved. The bench units, the window and the go to flash are Daniel's.
> R5 yes.
>
> Two additions to this PR:
> - Clamp GC's back-off target to [0, max travel] inside the new stall_response, with its own prediction and sabotage. It's new code anyway, and the limit switch shouldn't be the only thing that stops an over-travel.
> - Write up the position-after-any-reboot-mid-travel problem beside R1h, as a known limitation with its follow-up named (for example, boot marks the position unknown until the next end stop). It's F2's extra, and it applies to power loss, crashes and OTA, not only the 15-minute reboot.
>
> Follow-ups, recorded in this order, not in this PR:
> 1. Ropener at Fast: StallGuard can't arm during homing (TCOOLTHRS about 83 < TSTEP about 125). Say in your first report what homing does at Fast today: stops at its timeout, or keeps pushing.
> 2. R1f's three actions, if deferred.
> 3. Position after an interrupted calibration (R1h) and after a reboot mid-travel.
>
> Then the commits as you list them, one draft PR per repo. Report when CI is green on each head, and wait for approval at a named SHA. No tag or release without Daniel's go.

## R1f — what a user Open / Close / Set-position does today (base e42be0d)

Detector posture during calibration: the StallGuard reaction is forced OFF from
step 3 (after the announce) until calibration ends; vibration stall detection is
forced ON with its threshold raised to max(user value, 0.45 g). Every
open/close/position action resets `motion_start_ms`, so the vibration detector
ignores the first 0.5 s + speed/acceleration (capped at 3 s) of every such move.

| Phase | Open | Close | Set-position |
|---|---|---|---|
| Announce (3 beeps + 2 s, detectors as the user left them) | moves the window; seconds later the script claims full-open and drives a close, reversing it | same, then the script's close takes over | moves; then the script's close takes over |
| 1/3 homing close (StallGuard off) | reverses to opening until the counter reaches full-open or the open switch; then state 0 → script bails out, result 3 FAILED | no change (resets the vibration launch mask) | drives to an unrelated counter position (counter was claimed full-open); then state 0 → FAILED |
| 2/3 open leg, 3/3 close leg (StallGuard off) | same direction: continues, launch mask restarts. Opposite direction: reverses until the far switch or counter target; then state 0 → read as a stall → current raised and the script re-launches the leg 300 ms later | as Open | drives to a counter position; then state 0 → read as a stall → re-launch 300 ms later |
| 300 ms gaps between attempts | starts a move, overridden by the next attempt | same | same |

Against the condition: (1) a user command in phases 1-3 moves the window with the
StallGuard reaction off and the vibration detector blind for up to 3 s, so for
that interval no detector is armed — the condition is met; (2) today the
re-launch that follows is not ended by STOP (item 3). Therefore R1f comes into
this PR: a user Open, Close or Set-position during calibration ends calibration
through the same `cal_abort` as STOP (motor re-targeted at once, detectors back
on, threshold restored, result 5 "Aborted by user"), then carries out the
requested move under the normal detector posture. The schedule keeps its
existing guard (skipped during calibration, does not abort it). Button 1's
double-click stays ignored during calibration (unchanged).

## G. Instruments (run first)

G1 Entity gate with object IDs. Rows: `domain | name | entity_category | object_id`,
   object_id from ESPHome 2026.6.5's own `get_base_entity_object_id`.
   Run gate(base dump, base dump) for GC.
   Predicted: exit 0; both gates "clean".
   Sabotage: copy of the base dump with number "Motor Current" renamed
   "Motor Current X". Predicted: exit 1; exactly 1 REMOVED
   `number | Motor Current | config | motor_current` and 1 ADDED
   `number | Motor Current X | config | motor_current_x`.

G2 Anchor collision. Predicted: the fixed gate lists `interval:200ms#1`
   (completion poll) and `interval:200ms#2` (vibration stall) for GC.
   Sabotage: copy of the base dump with only the completion poll's body
   altered. Predicted: the base (unfixed) gate.py reports BEHAVIOUR GATE clean
   (the blind spot); the fixed gate reports exactly
   `CHANGED interval:200ms#1 :: then`.

G3 Call-site lister (`sites.py`, new). Predicted on the base dump:
   `cover.stop` 8 sites — `binary_sensor:Button 1 :: on_multi_click` ×2,
   `binary_sensor:Open Limit Switch :: on_press`, `binary_sensor:Close Limit Switch :: on_press`,
   `sensor:Motor Temperature :: on_value_range`, `script:auto_calibrate :: then`,
   `script:cal_thermal_guard :: then`, `script:cal_leg :: then`;
   `cover.open` 3 — Button 1 on_multi_click, `script:schedule_open`, `script:cal_leg`;
   `cover.close` 4 — Button 1 on_multi_click, `script:schedule_close`,
   `script:auto_calibrate`, `script:cal_leg`.
   Sabotage: copy of the base dump with one `cover.stop` added to
   `script:tamper_alarm` -> 9 sites, tamper_alarm listed.

## 1. ESPHome pin

P1.1 After the pin commit, build-release.yml installs `esphome==2026.6.5` and has no
   bare `pip install esphome`. Sabotage: same grep on base -> bare install found.
P1.2 The new CI assertion (`esphome version` must print `Version: 2026.6.5`) exits 0
   in the pinned venv. Sabotage: the same line against this machine's global
   ESPHome 2026.5.3 -> exit 1.
P1.3 Base at the pin: `esphome config` and `esphome compile` exit 0; firmware.ota.bin
   contains "ESPHome version 2026.6.5 compiled on". Sabotage: copy with a
   `script.execute: no_such_script` added -> `esphome config` exits non-zero.
P1.4 Reproduction: compile base with `-s fw_version 2.1.0`. Predicted: the config hash
   ESPHome records for the build occurs as 4 little-endian bytes in the shipped
   v2.1.0 Glasscalibur.ota.bin. Sabotage: the base build's hash with
   fw_version "dev" -> not found. (A miss is reported, not explained away.)
P1.5 CI green on the PR head; the install step log shows esphome 2026.6.5.
   Sabotage (R4-approved): workflow_dispatch on a throwaway branch with a broken
   YAML -> red at the compile step; branch deleted afterwards.
P1.6 External components pinned: slimcdk
   `b5f0e44ae8732f68b9bbeaed9e962ca052d04cdb`, esphome-lis2dh12
   `f9cbb99993f8ecee9e224e94e19a23b8aaf8e445`. Predicted: the sources copied into
   the build for tmc2209, tmc2209_hub, stepper, lis2dh12_base and lis2dh12_i2c
   are byte-identical before and after the pin. Sabotage: one byte flipped in a
   scratch copy of one file -> the comparison reports it.

## 2. api reboot_timeout

P2.1 Generated main.cpp: base contains `set_reboot_timeout(900000)`; head contains
   `set_reboot_timeout(0)`; exactly one call each. Sabotage: the base reading is
   red by construction; plus a copy of head with the product `api:` block
   removed -> 900000.

## 3. STOP (and, per R1f, Open/Close/Set-position) end calibration

P3.1 Call sites at head (sites.py):
   `cover.stop` 3 — Button 1 on_multi_click ×2, Motor Temperature on_value_range;
   `cover.open` 2 — Button 1 on_multi_click, schedule_open;
   `cover.close` 2 — Button 1 on_multi_click, schedule_close;
   `script.execute motion_halt` 7 — cover stop_action, Open Limit Switch,
   Close Limit Switch, auto_calibrate, cal_thermal_guard, cal_leg, stall_response;
   `script.execute cal_abort` 4 — cover stop_action, open_action, close_action,
   position_action;
   `script.execute drive_open` 2 — open_action, cal_leg;
   `script.execute drive_close` 3 — close_action, auto_calibrate, cal_leg.
   Sabotage: copy of the head dump with cal_leg's motion_halt replaced by
   `cover.stop` -> 4 cover.stop sites, cal_leg listed.
P3.2 stop_action = log, `motion_halt`, then `if cal_active -> cal_abort`.
   open_action / close_action / position_action each begin with
   `if cal_active -> cal_abort`. cal_abort sets cal_result 5.
   Sabotage: copy with stop_action's cal_active branch removed -> cal_abort
   sites drop to 3, stop_action missing (red).
P3.3 cal_vib_prev is captured before the announce beeps (R1d); the 80 °C cutoff
   runs cal_thermal_guard before cover.stop (result 4, not 5).

## 4. Movement reported until the motor stops

P4.1 stall_response, when not calibrating and no back-off is running: sets
   global_state to the back-off travel direction (stall while CLOSING -> 1,
   otherwise -> 2) and publishes the matching OPENING/CLOSING; resets the
   vibration launch mask and vib_loud_count; keeps stall_release_active set.
   Otherwise (calibrating, or a stall during a back-off) -> motion_halt.
   IDLE is published only by the completion poll on arrival, motion_halt, or
   that else-branch. stall_release_active is cleared by the poll, motion_halt,
   drive_open, drive_close and position_action. `script:stall_release_clear`
   no longer exists. Sabotage: copy with stall_response's
   `global_state = was_closing ? 1 : 2` changed to 0 -> red.
P4.2 Clamp: stall_response's lambda bounds the target to
   `[0, 341387]` (both `if (tgt < 0) tgt = 0;` and `if (tgt > 341387) tgt = 341387;`).
   Sabotage: copy with the upper bound removed -> red.

## 5. Obstruction event

P5.1 Entity gate head vs base: 0 REMOVED, exactly 1 ADDED:
   `event | Obstruction | (none) | obstruction`. No row containing "BENCH" in
   the release build (R1g). Sabotage: the bench target's dump vs base ->
   additionally ADDED `button | BENCH: simulate stall | …` (red for a release).
P5.2 `event.trigger` 1 site — `script:stall_response`, inside `if !cal_active`.
   `script.execute stall_response` 2 sites in the release build —
   `stepper:driver :: on_stall`, `interval:200ms#2 :: then`.
   Sabotage: copy with the `!cal_active` guard removed -> red.

## 6. Docs

P6.1 README at head: 0 occurrences of `/cover/glasscalibur`; uses `/cover/Glasscalibur/`.
   Sabotage: the same grep on base -> 1 hit (README.md:130).
P6.2 Calibration doc at head lists two known limitations, each with its follow-up
   named: position after an interrupted calibration (R1h); position after any
   reboot mid-travel. The resolved entries "No REMOTE abort" and "HA / web-UI
   cover commands are NOT gated" are gone. Sabotage: the same grep on base ->
   the two new entries absent, the old ones present.

## Final gate, head vs base (fixed gate on both dumps)

Entity: 0 removed, 1 added (event Obstruction).
Behaviour:
  CHANGED  binary_sensor:Button 1 :: on_multi_click
  CHANGED  binary_sensor:Close Limit Switch :: on_press
  CHANGED  binary_sensor:Open Limit Switch :: on_press
  CHANGED  cover:Glasscalibur :: close_action
  CHANGED  cover:Glasscalibur :: open_action
  CHANGED  cover:Glasscalibur :: position_action
  CHANGED  cover:Glasscalibur :: stop_action
  CHANGED  interval:200ms#1 :: then
  CHANGED  interval:200ms#2 :: then
  CHANGED  script:auto_calibrate :: then
  CHANGED  script:cal_leg :: then
  CHANGED  script:cal_thermal_guard :: then
  CHANGED  sensor:Motor Temperature :: on_value_range
  CHANGED  stepper:driver :: on_stall
  DROPPED  script:stall_release_clear :: then
  NEW      script:cal_abort :: then
  NEW      script:drive_close :: then
  NEW      script:drive_open :: then
  NEW      script:motion_halt :: then
  NEW      script:stall_response :: then
  (14 changed, 1 dropped, 5 new.) Everything else identical.
Every commit: `esphome config` and `esphome compile` exit 0 at 2026.6.5.

## Bench plan (hardware)

Nothing here runs without Daniel present and his go for that specific test, in a
window announced in Pacific time. Bench unit only. For B1 the unit must have no
native-API client (disabled in HA; no `esphome logs` over Wi-Fi, which is an API
client); logs over USB serial or the web UI.

B1 (no motion) Head build idle 20 min. Expected: Uptime >= 1200 s, no
   "No clients; rebooting". Sabotage: base build -> that line, Uptime resets ~900 s.

B2 (motion) Calibration ends on user commands. Path clear, Daniel at the window,
   Child Lock off, Vibration Threshold 0.30 g beforehand. One run each:
   a. web STOP during the beeps; b. web STOP in 1/3 homing; c. web STOP in the
   2/3 open leg; d. HA STOP in the 3/3 close leg; e. Button 1 single-click in
   the open leg; f. web Close in the open leg.
   Expected a-e: motor stops within 0.2 s and stays stopped 10 s.
   Expected f: no further open-leg launch; the window closes to the close limit.
   Expected all: no "CAL: … leg at irun=" line after the command; log
   "CAL: aborted by user"; 3 low beeps; Calibration Status "Aborted by user -
   run calibration again"; StallGuard Enabled ON; Vibration Stall Detection ON;
   Vibration Threshold 0.30 g; Motor Current ~600 mA.
   Sabotage: base build, cases c and f -> the leg re-launches; log
   "CAL: open leg at irun=15".

B3 (motion) Back-off. Bench build, Speed Medium.
   1. Close from fully open; "BENCH: simulate stall" at ~50 %. Expected: reverses
      at once; State OPENING and cover OPENING for the whole back-off (~9-10 s),
      then IDLE; position about +7 % from the stall point; exactly 1
      Obstruction event.
   2. Repeat; Button 1 during the back-off -> stops at once, IDLE.
   3. Repeat; simulate again during the back-off -> stops at once, IDLE, a 2nd
      Obstruction event, no second back-off.
   4. Speed Slow; simulate again 8 s into a back-off -> stops at once; no
      reverse toward the first stall point.
   5. Set position 95 %; Close; simulate within 2 s -> log
      "backing off to 341387"; window ends fully open.
   Sabotage: (1) bench build at the commit before the item-4 commit -> State
   IDLE while still reversing; (5) local bench build without the upper clamp ->
   logged target above 341387.
   Optional real stall (Daniel's call): foam block in the closing path, after a
   good calibration. Expected: vibration stall within ~3 s of contact, then as
   step 1. If nothing trips in 5 s Daniel presses STOP; that is a detector
   result, not an item-4/5 result.

B4 The Obstruction event is visible in HA and the web UI with B3's timestamps.

B5 (no motion, R4-approved; any unit on 2026.6.5) GET /cover/Glasscalibur -> 200
   JSON with "name_id":"cover/Glasscalibur"; GET /cover/glasscalibur -> 200 and a
   "Deprecated URL format" log line; GET /switch/Schedule%20Enabled -> 200.
   Sabotage: GET /cover/NoSuchCover -> 404.
