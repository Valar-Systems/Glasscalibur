# Bench scripts: window-end guard and the trimmed-carriage guard limit

Rulings 37 (a, c) and 38, 2026-11-11. Registered before any code. Base: origin/main b71d38e.
Branch bench/window-guard. Lands before session 1a (open_guard.py runs in 1a), after approval at
its head. Bench tools only: nothing under `firmware/` changes.

## Changes
1. **Window-end guard** (`tp1_run.py`, `open_guard.py`): `--window-end HH:MM` (Pacific time),
   required with `--host`.
   - Neither starts with under 5 minutes of the window left: tp1_run sends no command; the guard
     doesn't start.
   - When the window ends, tp1_run sends STOP, turns the heater off and puts back only what needs
     no motion (Motor Current); its report says the window ended and names anything not put back
     (Speed, and a calibration at the original speed). The guard sends STOP if an open is under
     way, writes its record and exits.
   - Dry run: `tp1_run.py --sim --sim-window-left N` (minutes of window at the start, virtual time).
2. **Trimmed carriage** (`open_guard.py`): `--trimmed-carriage` sets the limit to 100.5 mm; without
   it the limit stays 97.0 mm (old carriage). The record's first row names the carriage and the
   limit. A wrong flag only costs a rerun. On a fresh unit the first open runs at Fast, where the
   guard's polling lag can carry the carriage past 100.5 mm before STOP lands; on the trimmed
   carriage the firmware's own 101.0 mm unlearned target (0.41 mm short of the 101.41 mm stop) is
   the real backstop, and the guard mainly records the FAIL.
3. **README**: both options, and at the start of every sitting: confirm with Daniel which carriage
   is fitted, set the flag to match, and log it (ruling 38).
4. **tp1_sim.py**: a trimmed geometry for the guard checks (S4 at 99.3 mm, hard stop 101.41 mm):
   profiles `fresh-trimmed` and `fresh-trimmed-s4-never`.

## Checks
B1 All bench scripts compile; the TP-1 dry run (default profile) still passes; the old-carriage
   guard checks still hold: `fresh` learns 95.5 with no STOP; `fresh-s4-never` is stopped at
   97.0-97.5 mm with no hard-stop hit.
W1 `tp1_run.py --sim --sim-window-left 4`: not started, no command sent. Sabotage: a copy with the
   start check removed starts.
W2 `tp1_run.py --sim --sim-window-left 30` (the dry run needs about 72 virtual minutes): at the end
   of the window STOP is sent, the heater is off, Motor Current is put back, the report says the
   window ended and names Speed and the calibration as not put back. Sabotage: a copy that skips
   the end-of-window STOP is caught (no STOP in the commands).
W3 The guard with 4 minutes left: not started.
W4 The window ends during an open: the guard sends STOP, writes its record, exits.
G1 Trimmed flag: `fresh-trimmed` learns 99.3 with no STOP and no hard-stop hit;
   `fresh-trimmed-s4-never` is stopped at 100.5-101.0 mm with no hard-stop hit (FAIL recorded).
G2 Wrong flag (trimmed carriage, no flag): STOP at 97.0-97.5 mm, FAIL recorded, no hard-stop hit;
   a rerun with the flag learns.
G3 Sabotage: with the limit forced to 102 mm, `fresh-trimmed-s4-never` records no FAIL (the
   firmware's 101.0 target stops it), so G1's FAIL check turns red.
G4 The record's first row names the carriage and the limit, flag or no flag.
D  The push gate passes on the diff, the commits, the messages and the PR text.
