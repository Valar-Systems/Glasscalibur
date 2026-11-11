# Bench scripts: guard reconnect and interlock, prompts Daniel sees and hears, Child Lock during sittings

Ruling 41 (a, b, c), 2026-11-11. Registered before any code. Base: origin/main d707dc5. Branch
bench/guard-prompts. Bench tools only: nothing under `firmware/` changes. Lands before the TP-1
sitting and session 1a.

## Changes
1. **Guard reconnect** (`open_guard.py`): when its connection to the unit drops (a reboot, a
   flash, a power cut), the guard records it, keeps trying, checks the MAC again when the unit is
   back, records the reconnect and resumes watching.
2. **Interlock**: the guard writes a heartbeat file (`tools/bench/out/guard-heartbeat.json`) about
   twice a second: time, connected, watching. A shared gate (`bench_common.py`) used by every bench
   script that moves the unit (`tp1_run.py` now; `pc_run.py` when #27 merges) refuses to send a move
   (Open, Close, Set position, Auto-Calibrate) unless the heartbeat is under 2 s old and says
   connected and watching. While a move is under way the script checks the heartbeat on every wait;
   if it goes stale or says disconnected, the script sends STOP itself and records it.
3. **Prompts Daniel sees and hears** (`bench_common.py` + `bench_prompt.py`): every prompt that asks
   Daniel to act, and the guard's alerts, open in a window that stays on top of his screen and are
   spoken (Windows' built-in voice). The power-cut countdown is spoken ("three, two, one, pull the
   adapter now"). Dry runs record the prompts instead of showing them.
4. **Child Lock during sittings** (`bench_session.py`): `start` records the sitting (carriage, as
   confirmed with Daniel; window end) and Child Lock's current setting, then turns Child Lock on.
   `tp1_run.py` turns it off just before the Button 1 step and on again right after. `end` restores
   Daniel's original setting. The guard refuses to start if its `--trimmed-carriage` flag disagrees
   with the sitting's carriage.

## Checks
B1 All bench scripts compile; the TP-1 dry run and the #29 window and carriage checks still pass.
R1 The guard's connection drops (dry-run fault): within 2 s the heartbeat says disconnected and the
   record has "connection lost"; when the unit is back the guard checks the MAC, records "reconnected"
   and resumes: a later unlearned open past the limit is still stopped. Sabotage: without the
   reconnect, no "reconnected" and the later open isn't stopped.
I1 No heartbeat, a stale one, or one that says disconnected: the gate refuses the move, nothing is
   sent, the refusal is recorded. Sabotage: with the gate bypassed the move is sent.
I2 The heartbeat goes stale mid-move: the script sends STOP within 2 s and records it. Sabotage:
   without the in-move check, no STOP.
P1 TP-1's Button 1 request and the guard's alerts (a FAIL with STOP; connection lost) go through the
   prompter (shown and spoken; recorded in dry runs); the countdown helper speaks three, two, one and
   the call, about a second apart. Sabotage: a prompt that only prints is missing from the record.
P2 On the bench (start of the next sitting, Daniel present): a test prompt appears on top of his
   screen and he hears it.
C1 Dry run: `start` turns Child Lock on and records the original; TP-1 turns it off just before the
   Button 1 step and on right after; `end` restores the original. Sabotage: an `end` that doesn't
   restore is caught.
C2 A sitting recorded as trimmed with the guard started without `--trimmed-carriage` (and the reverse):
   the guard doesn't start.
D  The push gate passes.
