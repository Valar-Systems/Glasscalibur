# Glasscalibur firmware

ESPHome firmware for the Glasscalibur window opener (ESP32‑C6 + TMC2209). Built with
**ESPHome 2026.6.5** (pinned in CI).

| File | What it is |
| --- | --- |
| [`glasscalibur.yaml`](glasscalibur.yaml) | The one entry file to build: board pins, hardware constants, OTA identity, and the package list. |
| [`packages/`](packages) | The product, one local package per function: `system`, `web-ui`, `motion`, `limits`, `faults`, `tamper`, `stall`, `calibration`, `temperature`, `buttons`. |
| valar-core, scheduling | Shared remote packages from [Valar-Systems/valar-motion](https://github.com/Valar-Systems/valar-motion) (pinned `v0.3.0`): the driver, Wi‑Fi, API, OTA, diagnostics and the schedule. |

Every setting is documented inline in those files.

---

## Flashing and updates

USB powers the board for flashing but can't run the motor; the motor needs the
supplied 24 V DC adapter.

**First flash (blank board) — over USB:**

- ESPHome CLI: `esphome run firmware/glasscalibur.yaml` and pick the serial port, or
- [web.esphome.io](https://web.esphome.io) with `Glasscalibur.factory.bin` from a
  [release](https://github.com/Valar-Systems/Glasscalibur/releases).

**Updates — over the air:**

- **From the unit:** web UI → **Diagnostics** → **Update Firmware (GitHub)**. It
  downloads `Glasscalibur.ota.bin` from the latest release, installs it and
  restarts. Without internet or a release it logs an error and keeps the running
  firmware.
- **From a computer:** `esphome run firmware/glasscalibur.yaml` (pick the network
  target), the ESPHome dashboard, or the unit's own web page upload with a
  `Glasscalibur.ota.bin`.
- **The motor stops when an update begins**, however it was started; the position
  is saved at the restart.

**Releases (maintainers).** Pushing a tag `vX.Y.Z` runs
[`build-release.yml`](../.github/workflows/build-release.yml): it compiles with the
version stamped from the tag (the **Firmware Version** sensor reports it) and
attaches the factory and OTA images (`Glasscalibur.factory.bin`,
`Glasscalibur.ota.bin`) to the GitHub release. The asset names never change, so
units in the field always find the update. Branch and local builds report `dev`.
Before a release, run the [regression gate](../tools/regression-gate) against the
previous release.

## First setup

1. **Wi‑Fi.** If the unit has no saved network, or can't reach it, it starts its own
   setup Wi‑Fi network named `glasscalibur-XXXXXX`. Join it from a phone or laptop;
   a setup page opens where you pick your home network. Or connect USB‑C and use
   [web.esphome.io](https://web.esphome.io) (Improv) to send the network.
2. **Open the web UI** at `http://glasscalibur-XXXXXX.local` (`XXXXXX` = the last
   six characters of the MAC address, also printed in the boot log).
3. **Home Assistant** (optional): the ESPHome integration discovers the unit; add
   it. The unit runs on its own without Home Assistant (it does not restart when no
   client is connected).
4. **Calibrate** (below), then close fully and open once if calibration did not
   already teach the open stroke.

To clear the saved Wi‑Fi, hold the **Wi‑Fi / Calibrate** button for 3–10 s; the unit
restarts into setup.

## Buttons

| Button | Gesture | Does |
| --- | --- | --- |
| **Button 1** (GPIO23) | one click (≤ 1 s) | ends a running calibration; otherwise silences a tamper alarm; otherwise stops a moving window; otherwise closes. Ignored while **Button Lock** is on (except ending a calibration). |
| | double click | opens. Ignored while calibrating or with **Button Lock** on. |
| **Wi‑Fi / Calibrate** (GPIO21) | 7 quick presses (each ≤ 0.6 s) | starts **Auto‑Calibrate**. |
| | hold 3–10 s | clears the saved Wi‑Fi and restarts into setup. |

**STOP** from any source — Button 1, the web UI, Home Assistant, the API — also ends a
running calibration, as does a user Open / Close / Set‑position (which then makes
its move).

## Calibration and the speed lock

**Auto‑Calibrate** (Calibration group, or 7 presses on the Wi‑Fi / Calibrate button)
finds the lowest motor current that moves this window reliably and tunes both stall
detectors for it.

1. It refuses if the unit is moving, tampered or already calibrating, during a thermal
   lockout, or if the motor is above 50 °C (or its temperature sensor is missing).
2. Three short beeps, then 2 s before anything moves.
3. Homes to the close switch at full current (skipped if the close switch is already
   pressed).
4. Opens to the open switch starting at the lowest current (IRUN 12) and steps up
   (15, 17, 19) if it stalls, slips or runs out of time; then closes back to validate
   the current over the full travel.
5. On success it sets the StallGuard threshold (SGTHRS = a quarter of the lowest
   SG_RESULT seen, kept within 4–120), TCOOLTHRS (1.5 × the measured cruise TSTEP)
   and the **Vibration Threshold** (3 × the free‑running peak, 0.15–0.45 g), records
   the current and the speed it ran at, and beeps twice. A failure gives three low
   beeps.
6. Above 55 °C it stops ("motor overheated mid‑run"). Cool down, then run again.

**Calibration Status** reports the result: `OK: irun=… SGTHRS=…`, `OK (STICKY
WINDOW)` (needed full current), `FAILED - window did not reach limits. Check track.`,
`FAILED - motor overheated mid-run. Cool 15 min, re-run.`, or `Aborted by user - run
calibration again`.

**Speed lock.**

- **Until a calibration has succeeded**, every move runs at **Fast** (5500 steps/s),
  whatever **Speed** is set to: the driver's default StallGuard settings only detect
  stalls near that speed. **Calibration Notice** reads *Not calibrated - run
  Calibrate* and **Speed Lock** reads *Speed locked to Fast until calibration has
  run*. **StallGuard calibrated** is off.
- **After a successful calibration**, moves run at the speed it was calibrated at.
  If you change **Speed** later, moves keep that calibrated speed and **Speed Lock**
  reads *Speed change needs recalibration - running at …*, and **Calibration Status**
  ends in `STALE`, until a calibration at the new speed succeeds.
- **A calibration that fails or is aborted** keeps the last good one, including its
  motor current, and logs a warning with the reason.
- Units calibrated with an older version keep the speed that calibration recorded.
  Calibration itself always runs at the **Speed** setting, which it tunes for.

Speeds: **Slow** 1200, **Medium** 2600, **Fast** 5500 steps/s (all clear of a
drivetrain resonance near 2900–3300).

## The learned open stroke

Distances are counted from the close switch trigger (position 0) at 3066.7 steps/mm
(Tr6×1 lead screw, 12T:23T).

- **Learning.** A close that ends on the close switch marks a fresh home. The next
  open from there (Open, Set‑position 100 %, a schedule, or calibration's first open
  pass), if nothing stalls on the way, records where the open switch triggers. That
  is accepted between **94.0** and **101.0 mm**, saved, and shown as **Open stroke**
  (mm). Flash is written only when the value moves by more than 0.05 mm.
- **Opens** drive to the learned stroke + **0.5 mm** (101.0 mm before anything is
  learned) and stop on the open switch, at once — the log shows the step count at the
  switch and where the motor stopped (`S4 stop: … coast …`), with a warning above
  0.3 mm.
- **Closes** may run **0.6 mm** past zero; the close switch stops them first.
- The cover's 0–100 % is scaled to the learned stroke. Set‑position 100 % and 0 % run
  the full open and close.
- When an open is not a learning open, the open switch re‑syncs the position to the
  learned stroke (101.0 mm before learning), correcting any drift.

## Faults and what to do

**Fault** (Diagnostics) shows `None` or the active faults; each is also logged as a
warning. A restart clears them.

| Fault | Means | What to do |
| --- | --- | --- |
| **open switch position out of range** | A learning open met the open switch outside 94.0–101.0 mm. The previous value is kept. | Check that the open switch and the carriage are seated, then close fully and open again to re‑learn. |
| **open limit switch not detected** | An open reached its target without the open switch. It stopped there; the position is not re‑zeroed. Closing still works. | Check the open switch and its wiring. Close fully and open again. After updating from an earlier version this can happen once (old position scale): one full close fixes it. |
| **close limit switch not detected** | A close ran 0.6 mm past zero without the close switch. It stopped. | Check the close switch and its wiring. Open fully (the open switch re‑syncs the position), then close. |

Other things you may see:

| Sign | Means | What to do |
| --- | --- | --- |
| **Thermal Alert** `warning` | The motor read 50 °C or more. | Moves still run. Check the window moves freely. |
| A command does nothing, log `… refused - …`, **Thermal Alert** `refused` | The start gate (see [Motor temperature](#motor-temperature)). | Let the motor cool. STOP always works. A refused scheduled move waits (see below). |
| **Thermal Lockout** on, four chirps, **Thermal Alert** `lockout` | The motor read 60 °C or more; motion stopped. | Let it cool: it clears below 48 °C (**Thermal Alert** `cleared`). Check the window moves freely. |
| **Thermal Lockout** on, **Thermal Alert** `sensor_lost` | No valid temperature reading for 15 s. | Check the temperature board and its cable. It clears on a reading below 48 °C. |
| **Obstruction** event, the window backs off ~8 mm | A stall detector stopped a move. | Clear the path. Repeated stops on a clear path: run **Auto‑Calibrate**. |
| **Calibration Status** `FAILED - …` | See above. | Check the track, let the motor cool, run again. The last good calibration stays in use. |
| **Tamper Detected**, buzzer | The armed unit was moved. | Button 1 click or **Clear Tamper Alert**; **Set Tamper Baseline** after re‑mounting. |

## Motor temperature

**Motor Temperature** (TMP1075, every 3 s) drives these set points. They're the
`thermal_*` substitutions in [`glasscalibur.yaml`](glasscalibur.yaml).

| Reading | What happens |
| --- | --- |
| 50 °C or more | A warning in the log and **Thermal Alert** `warning`, once until a reading below 48 °C. |
| 55 °C or more | **Start gate:** no new motion starts. Open, Close and Set‑position (web UI, Home Assistant, the API, Button 1, schedules) and Auto‑Calibrate are refused, logged, and announced with **Thermal Alert** `refused`. A move already under way continues. |
| 60 °C or more | **Thermal lockout:** motion stops (a stall back‑off already under way finishes), a running calibration ends, four chirps, **Thermal Alert** `lockout`, **Thermal Lockout** on. Nothing new starts until a reading below 48 °C clears it (**Thermal Alert** `cleared`). |
| No valid reading for 15 s | The same lockout, with **Thermal Alert** `sensor_lost`. Counted from boot; until the first reading after boot, the start gate refuses. |

**STOP** always works. A restart clears the lockout; the start gate still applies.

**Refused scheduled moves wait.** A scheduled open or close that the gate refuses is
kept pending (a later refused one replaces it) and runs once the motor reads below
50 °C with the gate open, if that happens within 30 minutes; otherwise it is dropped
and logged. It is also dropped if **Schedule Enabled** is off by then. Any later
Open, Close or Set‑position (web UI, Home Assistant, the API or Button 1), whether
the gate accepts or refuses it, and any STOP, cancels it: the newest command wins.
Manual commands are not retried.
The 50 °C and 30 minutes are the `thermal_resume_c` and `thermal_pending_s`
substitutions.

## Stall detection and tamper

- **StallGuard** (TMC2209 load sensing) reacts when **StallGuard Enabled** is on (the
  default). **Vibration Stall Detection** (accelerometer) is off until a calibration
  turns it on. A stall outside calibration stops the motor and backs off about 8 mm
  (24,500 steps); a second stall during that back‑off just stops. **StallGuard
  Auto‑Tune** (off by default) nudges SGTHRS from the vibration evidence.
- **At least one detector stays on.** Switching **StallGuard Enabled** off while
  **Vibration Stall Detection** is off is refused (it switches back on, with a
  warning in the log), and so is switching vibration off while StallGuard is off. A
  unit that stored both off turns StallGuard on at startup.
- **Tamper Detection** (off by default): **Set Tamper Baseline** records the resting
  orientation; a deviation above **Tamper Threshold** (g) while idle raises **Tamper
  Detected** and sounds the buzzer for 60 s. To open the window by hand, lift the
  unit off its mounts; with Tamper Detection on, that sounds the alarm.

## Entity reference

Grouped as on the web page. *Config* and *diagnostic* follow Home Assistant's entity
categories.

**Control**

| Entity | Type | Notes |
| --- | --- | --- |
| Calibration Notice | text | *Not calibrated - run Calibrate* / *Calibrated* |
| Glasscalibur | cover | open / close / stop / position (0 closed … 1 open) |
| State | text | IDLE, OPENING, CLOSING, TAMPERED |
| Button 1 | binary sensor | the unit's button |
| Button Lock | switch (config) | the unit's button ignores presses; remote control keeps working |
| Obstruction | event | `obstructed`, once per stall that stops a move outside calibration |
| Thermal Alert | event | `warning`, `lockout`, `sensor_lost`, `cleared`, `refused` (see [Motor temperature](#motor-temperature)) |

**Motion Tuning**

| Entity | Type | Notes |
| --- | --- | --- |
| Speed | select (config) | Slow / Medium / Fast |
| Speed Lock | text | why the running speed differs from the setting, or *Not locked* |
| Acceleration | number (config) | steps/s² |
| Motor Current | number (config) | mA, up to 600 (IRUN 19) |

**Calibration**

| Entity | Type | Notes |
| --- | --- | --- |
| Auto-Calibrate | button (config) | starts calibration |
| Calibration Status | text (diagnostic) | result, `STALE` after a speed change |

**Stall Detection**

| Entity | Type | Notes |
| --- | --- | --- |
| Vibration Stall Detection | switch (config) | the accelerometer stall check; can't be off while StallGuard is off |
| Vibration Threshold | number (config) | g |
| Vibration Stall Samples | number (config) | how many loud samples (a leaky count, 2–60, default 5) stop the motor |

**Schedule**

| Entity | Type | Notes |
| --- | --- | --- |
| Schedule Enabled | switch (config) | master switch |
| Sun Schedule | switch (config) | sunrise/sunset instead of fixed times |
| Open Time | time (config) | fixed time |
| Close Time | time (config) | fixed time |
| Sun Open Offset | number (config) | minutes |
| Sun Close Offset | number (config) | minutes |
| Latitude | number (config) | for sunrise/sunset |
| Longitude | number (config) | for sunrise/sunset |
| Timezone | text (config) | POSIX TZ string |

**Tamper**

| Entity | Type | Notes |
| --- | --- | --- |
| Tamper Detection | switch (config) | arms the tamper check |
| Tamper Threshold | number (config) | g |
| Set Tamper Baseline | button (config) | records the resting orientation |
| Clear Tamper Alert | button (config) | silences and clears |
| Tamper Detected | binary sensor (diagnostic) | latched until cleared |

**Diagnostics**

| Entity | Type | Notes |
| --- | --- | --- |
| Fault | text (diagnostic) | limit-switch faults, or `None` |
| Open Limit Switch | binary sensor | S4 |
| Close Limit Switch | binary sensor | S5 |
| Firmware Version | text (diagnostic) | release version, or `dev` |
| WiFi Reset | binary sensor | the Wi‑Fi / Calibrate button |
| Board | text (diagnostic) | board name |
| Update Firmware (GitHub) | button (diagnostic) | installs the latest release |
| Motor Temperature | sensor (diagnostic) | °C |
| Thermal Lockout | binary sensor (diagnostic) | on while the thermal lockout holds |
| Restart | button (diagnostic) | restarts the unit |
| Open stroke | sensor (diagnostic) | mm; unknown until learned |
| StallGuard calibrated | binary sensor (diagnostic) | a calibration has succeeded |
| IP Address | text (diagnostic) | |
| Connected SSID | text (diagnostic) | |
| MAC Address | text (diagnostic) | |
| WiFi Signal | sensor (diagnostic) | dBm |
| Uptime | sensor (diagnostic) | s |
| ESP Internal Temperature | sensor (diagnostic) | °C |
| StallGuard Trips | sensor (diagnostic) | lifetime count |
| Vibration Stall Trips | sensor (diagnostic) | lifetime count |
| Tamper Trips | sensor (diagnostic) | lifetime count |
| Reset StallGuard Trips | button (diagnostic) | |
| Reset Vibration Stall Trips | button (diagnostic) | |
| Reset Tamper Trips | button (diagnostic) | |
| Accel X | sensor (diagnostic) | m/s² |
| Accel Y | sensor (diagnostic) | m/s² |
| Accel Z | sensor (diagnostic) | m/s² |

**StallGuard (advanced)**

| Entity | Type | Notes |
| --- | --- | --- |
| StallGuard Enabled | switch (config) | the StallGuard reaction (default on); can't be off while vibration is off |
| SGTHRS (stall threshold) | number (config) | set by calibration |
| TCOOLTHRS | number (config) | set by calibration |
| SG_RESULT | sensor (diagnostic) | live StallGuard reading |
| TSTEP | sensor (diagnostic) | live step period |
| IRUN value | number (config) | raw motor current register (≤ 19) |
| Auto-Tune Adjustments | sensor (diagnostic) | count |
| StallGuard Auto-Tune | switch (config) | default off |
| Speed | number (config) | raw speed in steps/s |

## Pin map

| Signal | GPIO |
| --- | --- |
| TMC2209 UART TX / RX | 1 / 0 |
| TMC2209 enable (ENN) | 8 |
| TMC2209 INDEX / DIAG | 6 / 14 |
| Button 1 | 23 |
| Wi‑Fi / Calibrate button | 21 |
| Open switch (S4) | 15 (input, internal pull-up on) |
| Close switch (S5) | 3 (input, internal pull-up on) |
| Buzzer | 5 |
| I2C SDA / SCL | 19 / 20 (LIS2DH12 at 0x18, TMP1075 at 0x49) |
