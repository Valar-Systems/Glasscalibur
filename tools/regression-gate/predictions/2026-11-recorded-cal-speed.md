# Glasscalibur recorded calibration speed — predictions

Written and committed before any code change on branch `feature/recorded-cal-speed`.
No check below had been run when this file was committed.

- Base: origin/main `af0115b` (PR #11 merged).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.
- Target: `firmware/esphome/Glasscalibur-esphome.yml`.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

For units calibrated on older firmware, the calibrated speed is the speed the old
calibration recorded, not the current setting (which would recreate the mismatch the
lock prevents: calibrated at Medium, switched to Slow, running Slow on a Medium tune).
1. A recorded speed is the calibrated speed; if it differs from the setting, it is an
   ordinary mismatch: run at it, Speed Lock "Speed change needs recalibration -
   running at <speed>", Calibration Status STALE.
2. Only with no recorded speed, fall back to the current setting and log that it was
   assumed.
3. A bench check for: a pre-2.2 calibration recorded at Medium, setting at Slow ->
   after the update it runs at Medium and shows the notice.
4. CHANGELOG: some updated units may go back to the speed they were calibrated at
   until they recalibrate.

## Design

Only the boot migration in on_boot 500 changes. A calibrated unit with `cal_speed` 0:
- `cal_speed_at` != 0 (older firmware recorded it in the same success branch) ->
  `cal_speed` = `cal_speed_at`, logged at INFO with both values;
- otherwise -> `cal_speed` = the saved setting, logged at WARN as assumed.
The lock, Speed Lock and STALE already compare the setting with `cal_speed`, so a
recorded speed that differs from the setting is handled as any mismatch (the boot WARN
"Speed setting … differs from the calibrated speed …" also fires).

Note: PR #10's seed sets `sg_calibrated` only from a nonzero `cal_speed_at`, and every
success writes `cal_speed_at`, so the fallback branch is reached only if
`sg_calibrated` is set with `cal_speed_at` 0, which today's code paths do not
produce. It is kept as the request asks.

## Checks (head vs base af0115b)

C1 `esphome config` validates, `esphome compile` succeeds; CI green.
   Sabotage: an undefined id in the new migration lambda is refused.
S1 The head's on_boot 500 body contains `id(cal_speed) = id(cal_speed_at)` and,
   in the fallback, `id(cal_speed) = id(global_speed)` with the word "assumed".
   Sabotage: the base's on_boot 500 has no `id(cal_speed) = id(cal_speed_at)`.
G1 Entity gate: clean.
   Sabotage: a scratch copy of the head with "Speed Lock" renamed is not clean.
G2 Behaviour gate: CHANGED exactly `esphome:on_boot :: 500.0`; NEW and DROPPED none.
   Sabotage: a scratch copy of the head with the base's on_boot 500 shows a clean
   behaviour gate (no CHANGED).

## Bench (not run in this PR; Daniel present for every motion step)

- F6 A unit calibrated on firmware before 2.2 at Medium, setting later changed to
  Slow (Calibration Status STALE there), updated to this firmware: the boot log names
  2600 as the calibrated speed; moves run at Medium (TSTEP ~144); Speed Lock reads
  "Speed change needs recalibration - running at Medium (2600 steps/s)"; Calibration
  Status STALE. A calibration at Slow clears both.
