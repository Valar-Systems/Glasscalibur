# Bench tools: open guard heartbeat file on Windows — predictions

Written and committed before the code change, on branch `bench/heartbeat-retry` (base: origin/main
`96674ca`). No check below had been run when this file was committed.

## What happened (TP-1 sitting, 2026-11-12, 20:02 PT, sealed unit, old carriage)

About 70 s after open_guard.py started, and 10 s into tp1_run.py, open_guard.py exited with
`PermissionError: [WinError 5] Access is denied` from `os.replace(guard-heartbeat.tmp,
guard-heartbeat.json)` in `bench_common.write_heartbeat`. On Windows, replacing a file fails while
another process has it open, and tp1_run.py reads that file before and during every move. With the
guard gone, its heartbeat went stale; tp1_run.py sent STOP mid-move (the 3.6 s stale reading) and
ended INCOMPLETE. The interlock worked; the run gave no TP-1 reading (instrument failure, disclosed).
The reader has the same exposure: `guard_ok` turns a read that collides with a replace into "no
heartbeat", which would also stop a move.
Daniel (2026-11-12, question tool): fix now, register it, dry-run it with a sabotage, and rerun
TP-1 tonight from this branch before it is merged.

## Change (bench_common.py only)

- `write_heartbeat`: if the replace is refused (PermissionError), retry every 10 ms, up to 50 times
  (0.5 s). If it is still refused, skip this beat and return False instead of raising; the guard's
  next beat (0.5 s later) tries again. A long run of skipped beats reads as stale to the scripts,
  which then send no move or STOP (unchanged).
- `guard_ok`: if the read is refused (PermissionError), retry every 10 ms, up to 20 times (0.2 s).
  If it stays refused, return not OK ("the open guard's heartbeat file stayed locked"). Other
  read errors are unchanged ("no heartbeat ...").
- Nothing else changes: thresholds, the heartbeat's contents, open_guard.py, tp1_run.py.

## Checks (on this Windows PC, no unit)

HB1 Stress, two processes for 20 s: a writer calling `write_heartbeat` every 5 ms and a reader
    calling `guard_ok` every 1 ms. Head: the writer raises nothing and skips at most 1 % of its
    beats; every `guard_ok` call returns OK.
    Sabotage: the same run with main's `bench_common.py` (96674ca): the writer raises
    PermissionError, or the reader gets at least one not-OK, within the 20 s.
HB2 Replace always refused (os.replace patched to raise PermissionError): `write_heartbeat`
    returns False within 0.6 s and raises nothing.
    Sabotage: main's version raises PermissionError.
HB3 Read always refused (the read patched to raise PermissionError): `guard_ok` returns not OK,
    with "stayed locked", within 0.3 s.
    Sabotage: a copy that treats a refused read as OK returns OK, and is flagged.
HB4 The TP-1 dry run still comes out as registered: `tp1_run.py --sim` ends PASS, and
    `--sim-guard drop-after-1` ends INCOMPLETE with STOP sent.
D   The push gate passes (scan && commit; the PR comes later).

Then TP-1 reruns on the sealed unit (old carriage, window to 22:00 PT) from this branch's head.

## Results (2026-11-12, head bda6c02, this Windows PC): 8/8 as predicted

- HB1 head: the writer made 1932 beats, skipped 0, raised nothing; the reader made 4397 reads, all OK.
- HB1 sabotage (main's bench_common.py): the writer raised PermissionError after 39 beats; the reader
  then got not-OK in 10751 of 11944 reads (stale heartbeat).
- HB2 head: returned False after 0.51 s, raised nothing. Sabotage: PermissionError raised at once.
- HB3 head: not OK, "the open guard's heartbeat file stayed locked", after 0.21 s. Sabotage: OK returned.
- HB4: `tp1_run.py --sim` ended PASS; `--sim-guard drop-after-1` ended INCOMPLETE with STOP sent.
- The check script (hb_test.py) is kept with the bench evidence; it goes into the PR with this file.

## Amendment 1 — HB5, a writer that stops (review, 2026-11-12; before the check is written)

- The retries must not hide a guard that has stopped writing. None of HB1-HB4 shows that on the
  file path (HB4's drop uses the dry run's own check), so HB5 is added.
- HB5: a writer process using this branch's `write_heartbeat` beats every 0.5 s, then exits
  abruptly after 3 s. A MoveGate over a stand-in device that reports State OPENING calls `sleep`
  until it raises. Predicted: it sends STOP and raises GuardLost with the "... s old" reason, at
  most 2.8 s after the last beat's time stamp (2.0 s age limit, up to 0.5 s between checks, up to
  0.2 s of read retries, 0.1 s slack).
  Sabotage: a copy whose `guard_ok` keeps retrying a stale reading for up to 5 s before reporting
  it. STOP then comes later than 2.8 s, and HB5 reports it.
- The checks (HB1-HB5) move into `tools/bench/heartbeat_check.py` in this PR, so they can be rerun.
- The full set (HB1-HB5, each with its sabotage, and HB4's dry runs) reruns on the new head.

### Amendment 1 results (2026-11-12, head cca0448, this Windows PC): 9/9 as predicted

`python tools/bench/heartbeat_check.py`, one run:
- HB1 head: 1995 beats, 0 skipped; 6249 reads, all OK. Sabotage (no retries): PermissionError after
  51 beats.
- HB2 head: False after 0.52 s, nothing raised. Sabotage: PermissionError at once.
- HB3 head: not OK, "stayed locked", after 0.21 s. Sabotage: OK returned.
- HB4: `--sim` PASS; `--sim-guard drop-after-1` INCOMPLETE with STOP sent.
- HB5 head: STOP and GuardLost 2.07 s after the last beat ("heartbeat is 2.1 s old"). Sabotage
  (stale reading retried 5 s): STOP 7.11 s after the last beat, reported.
