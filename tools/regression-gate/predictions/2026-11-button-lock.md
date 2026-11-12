# Button Lock (2.3.0): the "Child Lock" switch is renamed and its setting carried over — predictions

Rulings 43 d, 46 e, 49 e and 50 e; Daniel (2026-11-12): carry the setting over. Registered 2026-11-12, before
any code. Base: main `96674ca`. Branch `fw/button-lock`, a draft PR that merges after the 2.2.0 tag.

## Change
1. `firmware/packages/buttons.yaml`: the switch's name "Child Lock" becomes "Button Lock" and its id
   becomes `button_lock`; Button 1's single- and double-click checks follow, and the log lines read
   "Button lock …". Comments in `buttons.yaml`, `calibration.yaml` and `system.yaml` follow. Nothing else
   about the switch changes: config category, Control group, sorting weight 4, optimistic,
   `RESTORE_DEFAULT_OFF`.
2. Carry-over, an `esphome: on_boot` step at priority -110 (after every component's setup and after the
   existing -100 step). The switch's saved setting is stored under a key made from its name (ESPHome
   2026.6.5: the object-ID hash; no devices are configured), so a renamed switch would not find it. The step
   opens the old name's key (ESPHome's `fnv1_hash_object_id("Child Lock")` = 2353329421) as a `bool`. If it
   holds ON, it turns Button Lock on, writes OFF to the old key, syncs the preferences to flash and logs one
   line. If the old key is missing or OFF, it does nothing.
3. Docs: a CHANGELOG 2.3.0 section saying the switch is renamed, its entity ID changes from
   `switch.glasscalibur_xxxxxx_child_lock` to `switch.glasscalibur_xxxxxx_button_lock` (update automations
   and dashboards that use it), and the setting carries over. Also the README feature line, the firmware
   README (Button 1 table, entity reference row) and `tools/bench/README.md`.
4. Bench tools: `bench_common.lock_name(dev)` returns whichever lock switch the unit reports ("Button
   Lock" on 2.3.0, "Child Lock" on 2.2.0). `bench_session.py` and `tp1_run.py` use it, `tp1_run.py`'s
   settings snapshot lists both names, and `tp1_sim.py` can present either name (`--sim-lock-name`).

## Checks
- **C1** `esphome config` valid; compile succeeds; the bench build resolves.
- **G1** entity gate vs the base: exactly one row removed (the switch "Child Lock", config) and one added
  (switch "Button Lock", config, object ID `button_lock`). Nothing else.
- **G2** behaviour gate vs the base:
  - CHANGED exactly `binary_sensor:Button 1 :: on_multi_click`;
  - DROPPED exactly the old switch's `turn_on_action` and `turn_off_action`;
  - NEW exactly `switch:Button Lock :: turn_on_action`, `switch:Button Lock :: turn_off_action` and
    `esphome:on_boot :: -110.0`.
- **R7** resolved-config facts:
  1. the switch "Button Lock" is a template switch with id `button_lock`, config category, optimistic,
     `RESTORE_DEFAULT_OFF`, Control group, weight 4;
  2. Button 1's single- and double-click checks read `id(button_lock).state`, and no lambda in the config
     reads the old id;
  3. the on_boot -110 step opens a `bool` preference whose key equals ESPHome's own
     `fnv1_hash_object_id("Child Lock")` (the checker computes it with ESPHome's helper, it doesn't copy the
     number);
  4. it turns `button_lock` on only inside `if (… load(&…) && …)`;
  5. inside that branch, and nowhere else, it writes `false` to the old key and calls
     `global_preferences->sync()`.
  Sabotages: a head whose key is the hash of "Button Lock" fails fact 3; one without the write of `false`
  fails fact 5; one that turns the lock on without checking the loaded value fails fact 4. The base fails R7.
- **BT** bench tools, dry run (`tp1_sim.py`):
  - with the sim presenting "Child Lock" (BT1) and presenting "Button Lock" (BT2), `bench_session` start
    turns that switch on and end restores it, and `tp1_run`'s Button 1 step switches it off and back on;
  - sabotages: a `lock_name` that knows only "Button Lock" fails BT1; one that knows only "Child Lock" fails
    BT2.
- **D1** docs: entities in the config = rows in the firmware README's entity reference (66 = 66); the
  "Button Lock" row is there and no "Child Lock" row; all links resolve.
- **W** the push gate passes.

## Bench (Daniel present; the open set is enough: motor unplugged, nothing moves)
- **BL1** On the 2.2.0 bench build, set Child Lock ON. Flash the rename bench build over USB (saved
  settings kept). After boot, Button Lock reads ON and the log has the carry-over line. Switch Button Lock
  OFF and power-cycle the board: it stays OFF, because the old key was cleared.
- **BL2** From the 2.2.0 bench build with Child Lock OFF: after the flash, Button Lock reads OFF and there is
  no carry-over line.
- Sabotage: a local build without the carry-over step. From Child Lock ON, Button Lock comes up OFF.
- Note: an ESPHome version that changes how preference keys are made (ESPHome describes a planned second
  key scheme) must re-check the carry-over before it ships.

## Results (2026-11-12, head 6b93c94)
- **C1** `esphome config` valid; compile succeeds (flash 70.8 %, 1,299,896 bytes); the bench build resolves.
- **G1** as predicted: one row removed (switch "Child Lock", config), one added (switch "Button Lock", config,
  `button_lock`).
- **G2** as predicted:
  - CHANGED `binary_sensor:Button 1 :: on_multi_click`;
  - DROPPED the old switch's `turn_on_action` and `turn_off_action`;
  - NEW the new switch's two actions and `esphome:on_boot :: -110.0`.
- **R7** head 5/5; the base fails all 5.
  - The wrong-key head fails fact 3; the head without the write of `false` fails fact 5.
  - The head without the check fails fact 4, and also fact 5. Fact 5 looks inside the conditional branch,
    which that sabotage removes. The registered text named fact 4 and did not say "only".
- **BT** 4/4 as predicted.
  - With the simulated unit presenting "Child Lock" or "Button Lock", the sitting's start and end and
    TP-1's Button 1 step switched that lock and no other.
  - Each one-name sabotage failed on the other name ("the unit reports neither …").
- **D1** 66 entities, 66 reference rows; the "Button Lock" row present, no "Child Lock" row; links resolve.
  The dropped-row sabotage is reported.
- Item 3's wording: the CHANGELOG uses Home Assistant's default entity IDs, `switch.glasscalibur_…` (the
  device's friendly name is "Glasscalibur"), not the `glasscalibur_xxxxxx` form written in item 3.
- **Bench** BL1/BL2 and their sabotage: not yet run (Daniel present; the open set is enough).

## Amendment 1 — the bench steps and the CHANGELOG wording (ruling 52 a, 2026-11-12; before the bench)
The CHANGELOG writes the IDs as the user sees them: `switch.<your device>_child_lock` becomes
`switch.<your device>_button_lock`. This replaces the form in item 3.

The bench replaces BL1/BL2 above. Open set, motor unplugged, nothing moves. Every update is an OTA
upload over the network, as users update (no erase). The MAC is checked before every command. In order:
- **BL-C (control).** From the 2.2.0 bench build with Child Lock OFF, update to this PR's bench build.
  Predicted: Button Lock reads OFF and there is no carry-over line.
- **Back to 2.2.0** (OTA), then set Child Lock ON.
- **Sabotage.** Update to a build of this PR without the carry-over step. Predicted: Button Lock reads OFF.
- **BL1.** Update to this PR's bench build. Predicted: Button Lock reads ON, and the log has the
  carry-over line.
- **BL2.** Switch Button Lock OFF, then restart the board twice, from the web page's Restart button. Each
  time, predicted: Button Lock reads OFF and there is no carry-over line. The carry-over never applies
  again.

## Amendment 1 results: bench, 2026-11-12, all as predicted
Open set, motor unplugged. The board was identified by its USB serial from the port listing before anything was
opened, and its MAC was checked over the API before every command. Every update was an OTA upload. The firmware is
6b93c94's (unchanged since). The board's boot was captured in its USB log each time.
- BL-C: from the 2.2.0 bench build with Child Lock OFF -> Button Lock OFF, no carry-over line.
- Child Lock set ON on 2.2.0. Sabotage (this PR's build without the carry-over step) -> Button Lock OFF.
- BL1: this PR's build -> Button Lock ON; the carry-over line appears once.
- BL2: Button Lock switched OFF, then two restarts (the Restart button) -> OFF both times, no carry-over line.
- Ended on the 2.2.0 bench build, which reads Child Lock OFF (the old setting was written OFF by the carry-over).
