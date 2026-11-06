# Glasscalibur — ESPHome firmware

Wi-Fi window-cover controller (ESP32-C6 + TMC2209 stepper). Control it from any
browser at `http://glasscalibur-XXXXXX.local` (no Home Assistant required), or
pair it with Home Assistant over the native ESPHome API.

The full config lives in [`Glasscalibur-esphome.yml`](Glasscalibur-esphome.yml);
every setting is documented inline in that file.

## Web UI

Open `http://glasscalibur-XXXXXX.local` (the `XXXXXX` MAC suffix is printed on
the serial log at boot). Entities are organized into collapsible groups:

| Group | What's in it |
| --- | --- |
| **Control** | The cover, its live State, and Button 1 |
| **Motion Tuning** | Speed, acceleration, IRUN (motor current) |
| **StallGuard / Stall Detection** | StallGuard + the accelerometer vibration-stall backstop and their thresholds |
| **Security / Tamper** | Tamper detection, threshold, baseline / clear buttons |
| **Schedule** | Fixed open/close times **or** sunrise/sunset, timezone, location |
| **Diagnostics** | Firmware version, **Update Firmware**, **Restart**, temps, Wi-Fi, lifetime counters |

## Scheduling

Two mutually-exclusive modes, both gated by the master **Schedule Enabled** switch:

- **Fixed times** (default): set **Open Time** / **Close Time**.
- **Sunrise/sunset**: turn on **Sun Schedule**, set **Latitude** / **Longitude**,
  and optionally **Sun Open Offset** / **Sun Close Offset** (minutes, signed — e.g.
  `-30` closes 30 min before sunset). Requires a network connection for SNTP time.

## Updating the firmware

Two ways to update once the device is already running this firmware:

- **Over the air, from the device:** open the web UI → **Diagnostics** →
  **Update Firmware (GitHub)**. The device downloads the latest release straight
  from GitHub, flashes itself, and reboots — no computer needed (requires an
  internet connection).
- **Manually:** push a new build with the ESPHome CLI/dashboard
  (`esphome run Glasscalibur-esphome.yml`, pick the network/OTA target), or
  upload the `*.ota.bin` in the device's own **OTA Update** web card.

> The very first flash of a blank chip must be over USB (`esphome run` with the
> serial port) — there's no firmware yet to receive an OTA.

## Publishing a release (maintainers)

The **Update Firmware (GitHub)** button downloads, from this repo's
[latest release](https://github.com/Valar-Systems/Glasscalibur/releases/latest):

```
https://github.com/Valar-Systems/Glasscalibur/releases/latest/download/Glasscalibur.ota.bin
https://github.com/Valar-Systems/Glasscalibur/releases/latest/download/Glasscalibur.ota.bin.md5
```

The asset names are **version-less and stable** (`${ota_asset}` in the YAML, =
`Glasscalibur`) so this `latest/download/` URL never changes. To cut a release:

1. **Bump the version.** Edit `firmware_version` in `Glasscalibur-esphome.yml`
   (it feeds both `project.version` and the *Firmware Version* sensor).
2. **Build the OTA image:**
   ```bash
   esphome compile Glasscalibur-esphome.yml
   ```
   ESPHome writes the OTA image to
   `.esphome/build/glasscalibur/.pioenvs/glasscalibur/firmware.ota.bin`.
3. **Stage the assets with stable names:**
   ```bash
   cp .esphome/build/glasscalibur/.pioenvs/glasscalibur/firmware.ota.bin Glasscalibur.ota.bin
   md5sum Glasscalibur.ota.bin | awk '{print $1}' > Glasscalibur.ota.bin.md5
   ```
   (`md5sum` on Linux/Git-Bash; `md5 -q` on macOS. The `.md5` file must contain
   just the 32-char hex digest — the OTA flash checks the image against it.)
4. **Create a GitHub release** (tag e.g. `v1.1.0`), attach `Glasscalibur.ota.bin`
   and `Glasscalibur.ota.bin.md5`, and make sure it's marked **Latest**.

Until at least one such release exists, the button logs a download error and
leaves the running firmware untouched — it never bricks the device.

> **Tip:** also flash a brand-new board over USB without compiling by attaching
> a `Glasscalibur.factory.bin` (`esphome compile` produces `firmware.factory.bin`
> in the same build folder) and flashing it via [web.esphome.io](https://web.esphome.io).
