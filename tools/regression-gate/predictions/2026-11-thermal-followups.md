# Glasscalibur thermal follow-ups — predictions

Written and committed before any code change on branch `fw/thermal-followups`.
No check below had been run when this file was committed.

- Base: origin/main `b565d96` (#19 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.
- Target: `firmware/glasscalibur.yaml`.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (ruling, 2026-11-06)

- Lockout not kept across a restart: fine as is (the 55 °C start gate covers a hot
  restart). No change.
- Refused scheduled moves: when the gate refuses a scheduled open or close, keep it
  pending (latest one wins). Run it once the motor reads below 50 °C, if that happens
  within 30 minutes; otherwise drop it and log it. Fire Thermal Alert on every
  refusal so Home Assistant can notify. Manual commands are still not retried.
- TP-2: keep `thermal_stale_s` at 15; its pass line becomes "lockout within 20 s of
  the unplug".
- The `group_tamper` id rename stays.

## Design

New substitutions: `thermal_resume_c` 50 (a pending scheduled move runs below it)
and `thermal_pending_s` 1800 (it is dropped after this long).

- **Thermal Alert gains the event type `refused`**, fired on every thermal refusal:
  the start gate in the cover's open / close / position actions (every manual path),
  a refused scheduled move, and Auto-Calibrate's two thermal refusals (the lockout,
  and above 50 °C / no reading).
- **Scheduled moves:** `schedule_open` / `schedule_close` check the start gate
  themselves before calling the cover. Refused, they log and fire `refused` (as any
  refusal) and keep the move pending: open or close, with the time. A later refused
  scheduled move replaces it (latest wins) and restarts the 30 minutes.
- **Running it:** on each valid Motor Temperature reading below 50 °C, when the start
  gate is open (no lockout, so below 48 °C after a lockout), the pending move is
  cleared and its schedule script runs again (which checks the gate once more). If
  **Schedule Enabled** has been turned off meanwhile, it is dropped and logged
  instead. A calibration running at that moment skips it, as the scheduler's moves
  are skipped today.
- **Dropping it:** the 500 ms thermal interval drops a pending move older than 30
  minutes, logged at WARN.
- **Later commands win (my reading of "latest one wins"):** any later command the
  gate accepts (open, close or set-position from any path) and any STOP cancels a
  pending scheduled move, logged. So a window the user has closed by hand meanwhile
  is not reopened by an old schedule.
- Manual commands refused by the gate are logged and fire `refused`; they are not
  retried.

## Checks (head vs base b565d96)

C1 `esphome config` validates and `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in the new pending lambda is refused by the compile.
G1 Entity gate: clean (no entity added, removed or renamed).
   Sabotage: a scratch copy of the head with "Thermal Alert" renamed is not clean.
G2 Behaviour gate:
   - CHANGED exactly: `cover:Glasscalibur` open_action, close_action,
     position_action, stop_action; `script:schedule_open`; `script:schedule_close`;
     `script:thermal_refused`; `script:auto_calibrate`; `interval:500ms`;
     `sensor:Motor Temperature :: on_value`.
   - NEW exactly: `script:thermal_hold_scheduled`; `script:thermal_cancel_pending`.
   - DROPPED: none.
   Sabotage: a scratch copy of the head with the base's stop_action does not list
   stop_action as CHANGED.
R1 Resolved-config facts (head): Thermal Alert's event types are `warning`,
   `lockout`, `sensor_lost`, `cleared`, `refused`; `thermal_refused` triggers
   `refused`; both schedule scripts check the start-gate expression before calling
   the cover; `stop_action`'s first step is still `motion_halt`; the two new
   substitutions resolve to 50 and 1800 in the lambdas that use them.
   Sabotage: the base fails the event-type, schedule and substitution facts.
D1 Docs: firmware/README.md's entity reference matches the head's resolved config
   (66 entities), and every relative link resolves.
   Sabotage: the reference with one row dropped is reported.
W1 Wording: the P8 push scan, the docs claims scan and the local motor-term check
   pass on the full diff, the commit messages and the PR text.
   Sabotage: each is caught by a planted line, as before.

## Bench

- TP-2 pass line (replaces the one in `2026-11-thermal-lockout.md`, per the ruling):
  **lockout within 20 s of the unplug.** `thermal_stale_s` stays 15.
- The 2.2.0 list is unchanged otherwise: L1–L6, F1–F6, TP-1, TP-2, EN-2, on a build
  of main at this PR's merge commit.

## Amendment 1 — R1 re-registered (ruling, 2026-11-06; appended, nothing above was edited)

The miss is kept on record. R1 registered a base fact that was never true: "stop_action's
first step is still motion_halt". In the base and in the head the first step is the
`logger.log` line and motion_halt is the second. Reading: the head passed 6 of 7 facts
(the stop fact failed); the base, run as the sabotage, failed all 7 (registered: only the
event-type, schedule and substitution facts).

Re-registered fact: `stop_action` runs `motion_halt` before the new pending-move cancel
(`thermal_cancel_pending`), and otherwise keeps the base's steps in order.
Sabotage: a scratch copy of the head with those two steps swapped fails it.
The other six R1 facts and their sabotage are unchanged.
