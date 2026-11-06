# Glasscalibur: a refused command cancels a pending scheduled move — predictions

Written and committed before any code change on branch `fw/refused-cancels-pending`.
No check below had been run when this file was committed.

- Base: origin/main `893551a` (#21 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (review, 2026-11-06)

Today only accepted commands and STOP cancel a pending scheduled move. Failure case: a
scheduled open is pending because the motor is hot; Home Assistant sends Close (an
"everything closed when I leave" automation); the gate refuses it; the motor cools and
the window opens on its own, against the newest command.

Ruling: any later cover command (Open, Close, Set position, from the web UI, HA/API or
Button 1), accepted or refused, cancels the pending move. STOP still cancels it, and a
later refused scheduled move still replaces it. The bench runs on this PR's merge.

## Design

The refused branch of each of the cover's open, close and position actions runs
`thermal_cancel_pending` before `thermal_refused`, as the accepted branch already does.
Scheduled moves don't pass through these actions when refused (`schedule_open` /
`schedule_close` check the gate first and call `thermal_hold_scheduled`), so a refused
scheduled move still replaces the pending one. Nothing else changes.

## Checks (head vs base 893551a)

C1 `esphome config` validates and `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in the changed actions is refused by the compile.
G1 Entity gate: clean.
   Sabotage: a scratch copy with an entity renamed is not clean.
G2 Behaviour gate: CHANGED exactly `cover:Glasscalibur` open_action, close_action,
   position_action; NEW and DROPPED none.
   Sabotage: a scratch copy of the head with the base's close_action does not list
   close_action as CHANGED.
R1 Resolved-config facts (head):
   - A refused Close cancels a pending scheduled open: close_action's refused branch runs
     `thermal_cancel_pending`, before `thermal_refused`. The same holds for open_action
     and position_action.
   - The accepted branches still run `thermal_cancel_pending` first.
   - `stop_action`, `schedule_open`, `schedule_close` and `thermal_hold_scheduled` equal
     the base's (STOP still cancels; a refused scheduled move still replaces).
   Sabotage: a scratch copy of the head without the cancel in close_action's refused
   branch fails the first fact.
D1 Docs: firmware/README.md's entity reference matches the resolved config (66), links
   resolve; the README, CHANGELOG and wiki lines say that any later cover command,
   accepted or refused, and STOP cancel a pending scheduled move.
   Sabotage: a dropped reference row is reported.
W1 Wording: the push gate (every scan, one exemption list, self-tested) passes on the
   diff, the commit messages and the PR text.

## Bench (2.2.0 list; on this PR's merge commit)

- TP-1 gains a step: hold a scheduled open with heat (refused, pending), send Close
  (refused), let the motor cool below 50 °C, and confirm nothing moves.
