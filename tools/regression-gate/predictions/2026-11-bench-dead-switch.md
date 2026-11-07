# Glasscalibur bench: simulated dead limit switch for L3 / L4 — predictions

Written and committed before the bench change, on branch `bench/dead-switch-sim`.
No check below had been run when this file was committed.

- Base: origin/main `3730b27` (#23 merged). Bench only; nothing under `firmware/` changes.

## The request (review, 2026-11-06)

L3 and L4 unplugged a limit switch, but the switches are soldered to the board. Simulate the
dead switch in the bench build instead: BENCH switches that make S4 or S5 read as never
pressed, as a filter on the product's binary sensor, bench build only. Confirm from the
board schematic what a broken switch or cracked joint really reads (the inputs are
`INPUT`, inverted, no internal pull-up): a pull-up on the board reads released, which this
simulates; if it reads pressed, simulate that instead and tell Daniel; with no pull-up or
pull-down at all, it is a hardware finding (a floating input reads random presses).

## Design

`tools/bench/glasscalibur-bench.yaml` gains two switches, "BENCH: open switch (S4) dead" and
"BENCH: close switch (S5) dead" (default off, never restored on). Each appends a filter to
the product's binary sensor (`limit_switch_1` / `limit_switch_2`) that returns released
while the BENCH switch is on. The product's own filters (S4 `delayed_on: 10ms`; S5
`delayed_on: 10ms`, `delayed_off: 30ms`) stay first and unchanged.

Use: turn a BENCH switch on only while that limit switch is released (mid-travel), because
a binary sensor re-evaluates only on a pin change.

The schematic is not in the repo, and the Drive holds only Gerber and pick-and-place files
for the board, so what a broken switch reads is asked of Daniel. Until he answers, the
simulation is the "released" case (a pull-up on the board).

## Checks

D1 Build: the bench build and the TP-1 test build validate and compile.
   Sabotage: an undefined id in the new filter is refused.
D2 Resolved config (bench build): each limit sensor's filters are the product's, in order,
   then exactly one BENCH lambda; the two BENCH switches exist, default off.
   Sabotage: a scratch copy where the BENCH filter replaced the product's filters fails.
D3 Gates, product build vs bench build: the only differences are BENCH entities and
   anchors (the simulate-stall button and the two new switches); no product anchor
   changed, nothing dropped.
   Sabotage: a scratch copy with a product action altered is flagged.
D4 Wording: the push gate passes on the diff, every commit, the messages and the PR text.

## Bench, changed

- L3 / L4: with the BENCH switch for S4 / S5 on, the expected results are unchanged (open:
  stops at its target, "open limit switch not detected", position unchanged, a close still
  runs; close: stops 0.6 mm past zero, "close limit switch not detected"). No unplugging,
  no power cycles.
- L1-L6 run on the old carriage (the only one on hand): L1's learned stroke doubles as L6's
  reading. When the new carriage arrives, L1, L3 and L4 are rechecked on it.

## Note — the schematic (Daniel, Main-PCB-V6, 2026-11-06; appended, nothing above was edited)

LIMIT-1 (S4) and LIMIT-2 (S5) are the same circuit: a 20 kΩ pull-up to 3V3 on the switch
node, the switch to GND, a 5.1 kΩ series resistor to the ESP32 pin, 100 nF to GND and a
TVS diode. A broken switch or a cracked joint at the switch reads released (pulled up,
inverted), so the simulation stands as designed.

Also noted: if the 5.1 kΩ series resistor's joint cracks, the ESP32 pin is left
unconnected, and with `mode: INPUT` (no internal pull-up) it floats. Enabling the internal
pull-up on GPIO15 and GPIO3 would hold it released; with this circuit a pressed switch
still reads low (about 0.3 V). That is a product change, proposed separately; not in this
bench change.

Correction to the design text above: S4's product filters are `delayed_on: 10ms` and
`delayed_off: 30ms`, like S5's (check D2 compares the lists as resolved, so it is not
affected).
