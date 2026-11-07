# Glasscalibur 2.3.0: the limit switches decide the ends; position after a power cut — predictions

Written and committed before any code change on branch `fw/position-truth`.
No check below had been run when this file was committed.

- Base: origin/main at #26's merge (firmware = #25's merge, the 2.2.0 bench build).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.
- This PR stays open until 2.2.0 is tagged from the benched build; it merges after that.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-07)

Principle: the limit switches are the source of truth for the ends. The unit reports
"closed" only while S5 is pressed and "fully open" only while S4 is pressed, at boot and
after every move.
- Boot: a saved end position whose switch isn't pressed is unknown.
- After a move: a close that ends without S5 pressed doesn't report closed; the fault
  stays and the position is unknown, so the next Close runs until S5.
- An open that ends without S4 reports 99 % with the fault. It doesn't seek S4.
1. Saving (option A): write the position at once at every stop; set a move-in-progress
   marker before motion starts, cleared at the stop. Nothing is written while moving. The
   marker covers the one case the switches can't: a move between two middle positions
   cut off by a power cut.
2. While the position is unknown, the cover reports 50 %, with the fault "position
   unknown - close or open fully".
3. Set position while unknown: close to S5 first, then go to the requested position, and
   log it.

Today (verified): positions reach flash only every 60 s (ESPHome's `flash_write_interval`
default; nothing sets `preferences:`), so a power cut or an unplanned restart mid-move, or
within 60 s of a stop, restores a position up to a minute of travel old. Planned reboots
save exactly (on_shutdown 600).

## Design

New globals: `move_marker` (bool, persisted), `pos_unknown` (bool, persisted),
`pending_pos` (float, RAM, -1 = none).

- **`move_begin`** (new script): marker on, stored and flushed to flash at once
  (`update()` + `global_preferences->sync()`). Run by `drive_open`, `drive_close` and
  the proportional branch of `position_action`, before the target is set.
- **`position_commit`** (new script): copies the driver position, clears the marker, and
  stores and flushes the position, the marker and `pos_unknown` at once. Run by
  `motion_halt` (every firmware and user stop: STOP, the switches, stalls, the lockout,
  calibration), at the end of the S4 handler (after its re-sync), and by the 200 ms
  completion poll when a move reaches its target. A stall's back-off is the same move
  continuing: the marker stays set until the back-off ends.
- Nothing is flushed while the motor moves: the 200 ms poll still refreshes the RAM copy
  only. Flash wear: about 3 small writes per move; at 50 moves a day about 12 erase
  cycles per NVS page per year (448 KB NVS, 112 pages; flash rated around 100k cycles).
- **Boot** (on_boot 500, after the existing switch overrides): the position is unknown if
  the marker is set (interrupted move), or it was saved at the close end (<= 0) with S5
  released, or saved at the open end (>= the stroke) with S4 released, or it was already
  unknown; a pressed S5 or S4 makes it known (as today). The marker is then cleared. An
  unknown position raises fault bit 8 and logs why.
- **The cover's position:** 50 % while unknown; 0 % only while S5 is pressed; 100 % only
  while S4 is pressed; otherwise the computed value kept within 1-99 %.
- **While unknown:** `drive_close` targets the current count minus (the stroke + 2 mm),
  so the close runs until S5 (stall detection on: the interlock keeps a detector on);
  `drive_open` targets the current count plus (the stroke + 2 mm) and doesn't learn (the
  fresh-home flag is off). Set position (not 0 / 100 %) closes to S5 first, remembers the
  target in `pending_pos`, logs it, and the S5 handler then moves to it.
- **The switches:** the S5 handler (re-zero) and the S4 handler (re-sync) make the
  position known, clear bit 8, and commit; the S5 handler then runs a pending set
  position.
- **The completion poll:** a close that reaches its target without S5 keeps fault bit 4
  and also makes the position unknown (bit 8); a pending set position is dropped and
  logged. An open that reaches its target without S4 keeps fault bit 2; the cover shows
  99 % (it isn't fully open) and the unit doesn't seek S4.
- **STOP** drops a pending set position; a new Open or Close replaces it.
- **on_shutdown 600** (planned reboot): the stop point is exact, so it also clears the
  marker.
- **Fault text:** bit 8 = "position unknown - close or open fully".
- The 200 ms poll's comment no longer claims a power cut restores where the motor stopped.

## Checks (head vs base: #26's merge)

C1 `esphome config` validates and `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in `position_commit` is refused by the compile.
G1 Entity gate: clean (no entity added, removed or renamed).
   Sabotage: a scratch copy with an entity renamed shows it.
G2 Behaviour gate:
   - CHANGED exactly: `cover:Glasscalibur` lambda, position_action, stop_action;
     `esphome:on_boot :: 500.0`; `esphome:on_shutdown :: 600.0`; `script:drive_open`;
     `script:drive_close`; `script:motion_halt`; `interval:200ms#1`;
     `binary_sensor:Open Limit Switch :: on_press`;
     `binary_sensor:Close Limit Switch :: on_press`; `text_sensor:Fault :: lambda`.
   - NEW exactly: `script:move_begin`; `script:position_commit`.
   - DROPPED: none.
   Sabotage: a scratch head with the base's drive_open does not list it as CHANGED.
R1 Resolved-config facts (head):
   - `move_marker` and `pos_unknown` persist; `pending_pos` doesn't;
   - `move_begin` sets the marker and flushes; it runs in drive_open, drive_close and
     position_action's proportional branch before the target is set;
   - `position_commit` clears the marker and flushes; it runs in motion_halt, the S4
     handler and the completion poll;
   - the only `global_preferences->sync()` calls are in move_begin, position_commit and
     the Speed select (unchanged): none in the 200 ms position refresh;
   - the cover lambda returns 0.5 while unknown, 0.0 only with S5 pressed, 1.0 only with
     S4 pressed, else clamped to 0.01-0.99;
   - the boot step checks the marker and both saved-end cases;
   - the Fault text has "position unknown - close or open fully".
   Sabotage: the base fails these; a scratch head without `move_begin` in drive_open
   fails that fact.
D1 Docs: firmware/README.md's entity reference matches (66 entities), links resolve; the
   README describes the ends rule, the unknown position and the new fault; CHANGELOG has
   a 2.3.0 entry.
W1 Wording: the push gate passes on the net diff, every commit, the commit messages and
   the PR text.

## Bench (2.3.0; Daniel present; power cuts by a switched outlet if there is one)

- PC1 From S5, open at Fast; cut power at about half travel; repower: boot log says the
  move was interrupted, Fault shows "position unknown - close or open fully", the cover
  shows 50 % and Home Assistant offers both Open and Close. Close runs until S5: 0 %,
  fault cleared. Repeat with Open, which runs until S4: 100 %.
- PC2 The same at Slow.
- PC3 Stop mid-travel, cut power 10 s later, repower: the same position comes back, no
  fault.
- PC4 With the bench option that keeps S5 reading released across a restart: saved at
  0 %, S5 released at boot -> unknown, 50 %.
- PC5 Set position (40 %) while unknown: closes to S5 first (logged), then moves to 40 %.
- L3 changes: with S4 dead, the open ends at its target with "open limit switch not
  detected" and the cover shows 99 %, not 100 %.
- L4 changes: with S5 dead, the close ends 0.6 mm past zero with "close limit switch not
  detected", the cover shows 50 % (not closed) and Fault adds "position unknown"; the
  next Close runs on until the stall stop at the bumper (Obstruction event, back-off).
