# Bench tools — BENCH ONLY

Nothing here is ever built by CI, released, or flashed to a customer unit.

| File | What it is |
| --- | --- |
| `glasscalibur-bench.yaml` | The product plus "BENCH: simulate stall" (StallGuard doesn't fire on cue). |
| `glasscalibur-tp1.yaml` | The TP-1 test build: the bench build plus `tp1-bench.yaml`. Reports Firmware Version `dev-tp1`. |
| `tp1-bench.yaml` | The TP-1 test package: a motion backstop at 62 °C, the fallback hold-current heater with its own cutoffs, buttons that fire the schedule scripts, and a button that runs the product's lockout routine. |
| `tp1_run.py` | Runs TP-1 end to end over the native API and REST and writes a PASS/FAIL report. |
| `tp1_sim.py` | A simulated unit for the script's dry run (`--sim`). |

The design and the expected results are in
[`../regression-gate/predictions/2026-11-tp1-automatic.md`](../regression-gate/predictions/2026-11-tp1-automatic.md).

## Running TP-1

1. Flash the test build: `esphome run tools/bench/glasscalibur-tp1.yaml`.
2. Run the script, from the ESPHome environment (it uses `aioesphomeapi`):
   `python tools/bench/tp1_run.py --host <unit address>`.
   It saves the settings it changes (Speed, Motor Current, the calibration), heats the
   motor with full strokes at Slow and 600 mA, runs the checks, and puts the settings back.
   It asks for one Button 1 press during the lockout. The report and the device log go to
   `tools/bench/out/<time>/` (not committed). The unit address is not written to the report.
3. Flash the bench build back and check **Firmware Version**.

Dry run without a unit: `python tools/bench/tp1_run.py --sim`
(`--sim-fault slow-heat` exercises the heater fallback; `rest-close-accepted` and
`refused-close-no-cancel` are faults the script must report as FAIL).

## Rule for edits

Give every interval in a bench package a period no product interval uses (see the top of
`tp1-bench.yaml`). The regression gate anchors intervals by period, so a shared period
makes the product look changed.
