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
