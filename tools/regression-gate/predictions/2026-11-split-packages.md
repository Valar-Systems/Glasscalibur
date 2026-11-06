# Glasscalibur firmware split into local packages — predictions

Written and committed before any code change on branch `refactor/split-packages`.
No check below had been run when this file was committed.

- Base: origin/main `d35bdc6` (old design removed).
- Toolchain: ESPHome 2026.6.5 in an isolated venv.

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

A pure refactor with zero behaviour change: split `glasscalibur-product.yaml`
(3,128 lines) into local packages by function, keep the board wrapper as the single
entry file in a clean layout, update the CI workflow, tools/bench and
tools/regression-gate paths. valar-core and scheduling stay the pinned remote
packages. Unchanged: device_name, the project name, every entity name and ID,
ota_repo and ota_asset, the external component pins, every substitution value.
Proof: the fully resolved `esphome config` output identical before and after, after
normalising list order where ESPHome reorders merged lists; any remaining
difference explained; entity and behaviour gates; a full compile.

## Layout

- `firmware/glasscalibur.yaml` — the board wrapper (git mv of
  `firmware/esphome/Glasscalibur-esphome.yml`). Unchanged except its `packages:`
  list (the one product include becomes the ten local packages below) and comments.
- `firmware/packages/`, merged in this order after valar_core and scheduling:
  `system` (external components, api, ota, logger, i2c bus, the stop-on-update boot
  hook), `web-ui` (sorting groups), `motion` (cover, motion scripts, speed / accel /
  current, position save and restore, the 200 ms completion poll), `limits` (the two
  limit switches, the learned open stroke), `faults`, `stall` (StallGuard handler,
  vibration stall check, stall response, auto-tune, Obstruction event),
  `calibration` (auto-calibration, its status, the fail-safe speed lock, the 100 ms
  sampler), `temperature` (TMP1075 and the 80 °C cutoff), `tamper` (accelerometer,
  tamper check, buzzer), `buttons` (Button 1, the Wi-Fi / calibrate button, Child
  Lock).
- Each item's text (with its leading comments) moves verbatim; section header
  comments go with the package holding that section's first item.
- `firmware/.gitignore` (moved from `firmware/esphome/`). The docs in
  `firmware/esphome/` stay until the docs PR; their path references are updated.
- CI compiles `firmware/glasscalibur.yaml`; asset names unchanged (the workflow
  names them itself). `tools/bench/glasscalibur-bench.yaml` includes the new path.
  The gate README gains the Glasscalibur command lines.

## Checks (head vs base d35bdc6)

R1 Resolved config, parsed (key order is not stable between `esphome config` runs, so
   text is not compared). Normalisation: every top-level list, and the
   `esphome: on_boot` list, sorted by the canonical JSON of its items; nothing else
   (action lists inside automations are NOT reordered).
   Predicted: identical after normalisation (substitutions, esphome name / project,
   api, ota, logger, web_server, external_components and every component equal).
   Before normalisation the only differences are item order inside these lists:
   globals, binary_sensor, number, switch, button, sensor, text_sensor, script,
   `esphome: on_boot` (a subset of these), and the two `interval: 200ms` blocks keep
   their order (completion poll first, then the vibration check).
   Sabotage A: the head's resolved config with one substitution value changed is
   reported as different. Sabotage B: the head's resolved config with two actions
   swapped inside one script is reported as different (normalisation does not hide
   order inside an automation).
G1 Entity gate: clean.
   Sabotage: a scratch copy with one entity renamed is not clean.
G2 Behaviour gate: clean.
   Sabotage: a scratch copy with the two `interval: 200ms` blocks swapped is not clean
   (the one place merged-list order carries meaning is guarded).
C1 `esphome config` and `esphome compile` of `firmware/glasscalibur.yaml` succeed;
   CI green on the PR head.
   Sabotage: a scratch wrapper naming a missing package file fails `esphome config`.
B1 `esphome config tools/bench/glasscalibur-bench.yaml` succeeds with the new path.
   Sabotage: the old include path fails.
P8 Public-wording scan with an exact-line move rule: a flagged added line counts as
   moved (not a new use) only if the identical line exists in the base's
   `glasscalibur-product.yaml` / `Glasscalibur-esphome.yml`. Predicted: the flagged
   lines are exactly the 22 already in the base (same texts); 0 new uses.
   Sabotage: a planted new line with a flagged word is caught under the move rule.
