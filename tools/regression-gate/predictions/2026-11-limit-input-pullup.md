# Glasscalibur limit-switch inputs: internal pull-up — predictions

Written and committed before any code change on branch `fw/limit-input-pullup`.
No check below had been run when this file was committed.

- Base: origin/main at #24's merge (firmware unchanged since #22's merge, `40574e3`).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (review, 2026-11-07)

Enable the ESP32-C6's internal pull-up on the two limit-switch inputs, GPIO15 (S4,
open) and GPIO3 (S5, close), before bench session 1a, so the bench runs the final pin
setup. Today they are `mode: INPUT` with no internal pull-up.

Why: the board (Main-PCB-V6) has, on each input, a 20 kΩ pull-up to 3V3 on the switch
node, the switch to GND and a 5.1 kΩ series resistor to the pin. If the series
resistor's joint cracks, the pin is connected to nothing and floats. A floating S5 can
fire a false press while the unit isn't opening, which zeroes the position: the unit
could report closed with the window still open. With the internal pull-up, that pin
reads released, like a dead switch, which the firmware already reports as a fault.

## Design

Both pins become `mode: {input: true, pullup: true}`; `inverted: true`, polling, the
filters and every handler stay as they are. Nothing else changes.

Electrically (from the circuit and the chip's typical ~45 kΩ internal pull-up; not
measured here):
- pressed: the pin sits at about 3.3 V × 5.1 / (5.1 + 45) ≈ 0.34 V (still about 0.48 V
  if the internal pull-up were as low as 30 kΩ), under the 0.825 V low threshold
  (0.25 × 3.3 V): reads pressed;
- released: pulled high by both pull-ups: reads released;
- series resistor open: the internal pull-up holds the pin high: reads released.

## Checks (head vs base: #24's merge)

C1 `esphome config` validates and `esphome compile` succeeds; CI green.
   Sabotage: an invalid pin mode value is refused by the config check.
R1 Resolved config: both limit pins are input, pull-up on, pull-down off, inverted;
   with those two `pullup` values put back to the base's, the head's resolved config
   equals the base's exactly (nothing else changed).
   Sabotage: the base fails the pull-up fact; a scratch head with only one pin changed
   fails it too.
G1 Entity gate: clean.  G2 Behaviour gate: clean.
   Sabotage: a scratch copy with an entity renamed and a step changed is flagged.
D1 Docs: firmware/README.md's pin map says both limit inputs use the internal pull-up;
   the CHANGELOG 2.2.0 entry has one line; the entity reference still matches (66).
W1 Wording: the push gate passes on the net diff, every commit, the commit messages and
   the PR text.

## Bench (session 1a, on this PR's merge)

- PU: both switches read pressed at their ends and released between them (seen in F1,
  L1, L2 and the F moves); L3 / L4 (simulated dead switch) report their faults as
  registered.
