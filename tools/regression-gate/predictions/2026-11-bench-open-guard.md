# Glasscalibur bench: guard every open until the stroke is learned — predictions

Written and committed before the tooling, on branch `bench/open-guard`.
No check below had been run when this file was committed.

- Base: origin/main at #25's merge (the bench build). Bench only; nothing under
  `firmware/` changes.

## The request (review, 2026-11-07)

A fresh unit opens toward 101.0 mm until it has learned its stroke, but the old carriage's
hard stop is about 99.1 mm from the S5 trigger (S4 normally trips at about 95.5 mm). So,
until the stroke is learned: if S4 hasn't tripped by 97 mm, send STOP and record a FAIL.
This covers F1's move and L1's first open on the fresh unit. And TP-1 must not start unless
L1 learned the stroke.

## Design

`tools/bench/open_guard.py --host <address> --mac <MAC>` runs in the background for all of
session 1a. It connects like `tp1_run.py` (it checks the MAC and stops if the unit reports a
different one), sends no command except STOP, and records what it does in its own report.

- While **Open stroke** is unknown (not learned), the cover's 0–100 % is scaled to the
  101.0 mm default, so position × 101.0 is the distance from the S5 trigger.
- **Reference:** distances count only from a close that ended on S5, or from boot with S5
  pressed. An open that starts before the guard has seen S5 pressed is stopped at once
  (FAIL: no reference), because its distance from S5 is unknown.
- **The rule:** during an open with the stroke unknown, at 97.0 mm with S4 not pressed:
  STOP (API) and FAIL "S4 not tripped by 97 mm".
- Once **Open stroke** is learned the guard only records; the open then targets the
  learned stroke + 0.5 mm (about 96.0 mm on the old carriage).

`tp1_run.py`: before any command, it requires **Open stroke** learned (94.0–101.0 mm);
otherwise it stops ("L1 has not learned the stroke").

## Checks (dry runs against `tp1_sim.py`, which gains the limit switches, the learned
stroke, and a hard stop at 99.1 mm that it records as a hard-stop hit)

O1 Old carriage, S4 trips at 95.5 mm: the first open stops on S4 and learns about 95.5 mm;
   the guard sends no STOP and records PASS.
   Sabotage: a simulated S4 that never trips: the guard sends STOP at 97.0–97.5 mm and
   records FAIL; the simulated carriage never reaches 99.1 mm. With the guard off, the same
   simulation reaches the hard stop (recorded as a hard-stop hit).
O2 An open before any S5 reference is stopped at once (FAIL: no reference).
   Sabotage: the same open after a close that ended on S5 is not stopped.
O3 `tp1_run.py` with **Open stroke** unknown stops before its first command (the simulated
   unit receives none); with it learned, the dry run passes as before.
O4 Wording: the push gate passes on the net diff, every commit, the commit messages and
   the PR text.
