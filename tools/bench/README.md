# Bench tools — BENCH ONLY

Nothing here is ever built by CI, released, or flashed to a customer unit.

| File | What it is |
| --- | --- |
| `glasscalibur-bench.yaml` | The product plus "BENCH: simulate stall" (StallGuard doesn't fire on cue) and "BENCH: open switch (S4) dead" / "BENCH: close switch (S5) dead" (the switches are soldered, so L3 / L4 simulate a dead one: the sensor reads released, as a broken switch does with the board's pull-up), and "BENCH: close switch (S5) dead, kept across restarts" (2.3.0 bench PC4). |
| `glasscalibur-tp1.yaml` | The TP-1 test build: the bench build plus `tp1-bench.yaml`. Reports Firmware Version `dev-tp1`. |
| `tp1-bench.yaml` | The TP-1 test package: a motion backstop at 62 °C, the fallback hold-current heater with its own cutoffs, buttons that fire the schedule scripts, and a button that runs the product's lockout routine. |
| `tp1_run.py` | Runs TP-1 end to end over the native API and REST and writes a PASS/FAIL report. |
| `tp1_sim.py` | A simulated unit for the script's dry run (`--sim`). |
| `find_unit.py` | Finds the bench unit's current address by its MAC, confirmed by the unit itself. |
| `open_guard.py` | Runs in the background until the stroke is learned: stops any open that passes 97 mm without S4, or that starts with no S5 reference. |

The design and the expected results are in
[`../regression-gate/predictions/2026-11-tp1-automatic.md`](../regression-gate/predictions/2026-11-tp1-automatic.md).

## Finding the unit

Its address can change, and no other unit on the network may get bench commands, so find it
by the MAC the USB flash reported: `python tools/bench/find_unit.py --mac <MAC>`. It accepts
an address only if the device there reports that MAC, and prints it on screen only.

## Until the stroke is learned (a fresh unit)

A fresh unit opens toward 101.0 mm, past the old carriage's hard stop (about 99.1 mm). Leave
the unit closed on S5 before wiping it, then run
`python tools/bench/open_guard.py --host <unit address> --mac <MAC>` for the whole session.
It sends STOP (and records a FAIL) if an open passes 97 mm with S4 released, or starts
before it has seen S5 pressed. Once **Open stroke** is learned it only records. TP-1 won't
start until the stroke is learned.

## Running TP-1

1. Flash the test build: `esphome run tools/bench/glasscalibur-tp1.yaml`.
2. Run the script, from the ESPHome environment (it uses `aioesphomeapi`):
   `python tools/bench/tp1_run.py --host <unit address> --mac <MAC>`. Before its first
   command it checks that the unit reports that MAC, and stops if not.
   It saves the settings it changes (Speed, Motor Current, the calibration), heats the
   motor with full strokes at Slow and 600 mA, runs the checks, and puts the settings back.
   It asks for one Button 1 press during the lockout. The report and the device log go to
   `tools/bench/out/<time>/` (not committed). Neither the address nor the MAC is written to
   them; the kept device log has addresses, MACs and name suffixes masked.
3. Flash the bench build back and check **Firmware Version**.

Dry run without a unit: `python tools/bench/tp1_run.py --sim`
(`--sim-fault slow-heat` exercises the heater fallback; `rest-close-accepted` and
`refused-close-no-cancel` are faults the script must report as FAIL).

## Power cuts by hand (2.3.0, PC1-PC6)

`pc_run.py` runs the power-cut cases in
[`2026-11-position-truth.md`](../regression-gate/predictions/2026-11-position-truth.md)
(PC1-PC6, Amendments 3-4) on the 2.3.0 bench build, with Daniel present.

1. Unplug the unit's USB cable, so the chip loses power with the motor.
2. `python tools/bench/pc_run.py --host <unit address> --mac <MAC> --window-end HH:MM`
   (Pacific time; `--cases PC2,PC3` runs a subset). It checks the MAC before its first
   command and after every power-up. No case starts with under 5 minutes of the window
   left; at the end of the window it sends STOP and stops.
3. At "PULL THE 24 V ADAPTER FROM THE WALL NOW" (after a 3-second countdown) pull the
   adapter from the wall. The script waits until the unit drops off the network, then says
   when to plug it back in.
4. A case whose speed isn't the unit's calibrated speed isn't run: Auto-Calibrate at that
   speed first (PC1 runs at Fast; PC2, PC3, PC5 and PC6 at Slow), then run those cases.

Each case is judged on its registered outcome. Where the carriage really stopped comes from
the recovery move's log lines and is reported beside the last position the unit reported.
The report and the device log go to `tools/bench/out/pc-<time>/` without the address or the MAC.

Dry run without a unit: `python tools/bench/pc_run.py --sim --sim-cal Slow --cases PC2,PC3,PC4,PC5,PC6`
and `--sim --sim-cal Fast --cases PC1` (`--sim-fault no-drop`, `stays-known`, `pc6-late`,
`wrong-mac` and `speed-locked` are faults the script must report).

## Rule for edits

Give every interval in a bench package a period no product interval uses (see the top of
`tp1-bench.yaml`). The regression gate anchors intervals by period, so a shared period
makes the product look changed.
