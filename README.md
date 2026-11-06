# Glasscalibur — Automated Horizontal Window Opener

Glasscalibur is a smart opener for horizontal-sliding windows. A NEMA stepper
motor drives a lead screw that slides your window open and closed, controlled by
an ESP32‑C6 running [ESPHome](https://esphome.io). Control it from **any web
browser** with no app and no cloud account, pair it natively with **Home
Assistant**, or automate it with schedules, sunrise/sunset, or any system that
can send an HTTP request (Node‑RED, scripts, IFTTT‑style webhooks, etc.).

> **Older design:** the original Model‑H (its Arduino firmware, STEP files and media) is kept at the [`legacy-old-design`](https://github.com/Valar-Systems/Glasscalibur/tree/legacy-old-design) tag.

---

## Features

- **Browser control, no cloud** — open `http://glasscalibur-XXXXXX.local` on
  your network and drive the cover, tune the motor, and set schedules. No Home
  Assistant or account required.
- **Native Home Assistant** — auto‑discovered over the ESPHome API as a real
  cover entity (no `command_line`/curl glue).
- **Built‑in scheduling** — open/close at fixed times **or** at sunrise/sunset
  (with minute offsets), all editable from the browser. Survives reboots.
- **Obstruction & stall protection** — TMC2209 **StallGuard** plus an
  accelerometer‑based **vibration‑stall** backstop stop the motor when the
  window jams, is locked, or something gets in the way, and save the position.
- **Over‑temperature cutoff** — an on‑board temperature sensor stops the motor
  if it exceeds 80 °C.
- **Anti‑tamper alarm** — the accelerometer flags if a mounted unit is moved or
  tilted and sounds a buzzer.
- **Over‑the‑air updates** — a one‑click **Update Firmware** button pulls the
  latest release straight from GitHub. No computer needed.
- **Instant manual override** — the whole device lifts off the window in a
  couple of seconds for cleaning or emergencies (see GIF below).

---

## How it works

Glasscalibur uses a **NEMA 17 stepper motor** connected to a **lead screw**. As
the screw turns, a nut travels along it and pushes/pulls the window sash. A
custom PCB with an **ESP32‑C6‑MINI** and a **TMC2209** silent stepper driver
runs the motor over a single‑wire UART link.

Two **limit switches** — one at each end of travel — give the cover a known
absolute position: every time the carriage hits a limit, the firmware
re‑calibrates its step count, so position never drifts. The board also carries:

- a **TMP1075** temperature sensor (motor over‑temp cutoff),
- a **LIS2DH12** 3‑axis accelerometer (vibration‑stall + anti‑tamper),
- a **piezo buzzer** (tamper alarm), and
- physical buttons (a control button and a Wi‑Fi‑reset button).

The firmware is a single ESPHome configuration — see
[`firmware/`](/firmware) (`glasscalibur.yaml` plus `packages/`) for the full, heavily commented config
and a flashing guide.

---

## Safety features

Safety is the primary concern with this device.

**Instant removal.** In an emergency the entire device lifts straight off the
window — no tools, a couple of seconds.

**Obstruction & lock detection.** While moving, the cover watches for a stall
two ways: the TMC2209's StallGuard reads the motor's mechanical load, and the
accelerometer watches for the hard vibration a jammed mechanism produces. If
something gets in the way, or the window is locked, the motor stops and saves
its position. Both detectors have adjustable sensitivity so you can tune them to
your window.

**Over‑temperature cutoff.** If the motor sensor reads above 80 °C, motion stops
automatically.

**Anti‑tamper.** Once armed, the accelerometer learns the device's resting
orientation; if a mounted unit is bumped, tilted, or pried, it raises a Tamper
alert and sounds the buzzer.

---

## Will it work on your window?

Before you build or buy, check that the device fits your window. Window **sill
height** is the main factor.

### Is your window sill the correct height?

The maximum distance from the top of the window frame to the sill is **2 inches**
(red text above). More than that and you'll need to raise the opener — a piece
of wood such as a 1×4 or 2×4 under the whole device works well.

To attach the window mount (white piece above), you need **14 mm** of the lower
sash exposed.

### Is your window wide enough?

The device is just under **22 in** end to end, so your window needs to be at
least **44 in** wide — add 2 in to be safe, so target **46 in**.

### Is your window too heavy?

The motor has been tested up to **40 lb** of window. That's very heavy and can
cause problems; if your window is that heavy, lubricate the track with dry
silicone spray first and see if that helps.

---

## Controlling it

You have several options, and they all work at once:

| Method | How |
| --- | --- |
| **Web browser** | Open `http://glasscalibur-XXXXXX.local` (the `XXXXXX` MAC suffix is printed on the USB serial log at boot). Full control panel — cover, motor tuning, schedule, diagnostics. |
| **Home Assistant** | The device is auto‑discovered over the native ESPHome API as a `cover` entity. No YAML, no curl. |
| **HTTP / REST** | The ESPHome web server exposes a REST API addressed by entity **name**, e.g. `POST http://glasscalibur-XXXXXX.local/cover/Glasscalibur/set?position=0.5` (position is `0.0`=closed … `1.0`=open), and `/cover/Glasscalibur/open`, `/close`, `/stop`. Names are case-sensitive; write a space as `%20` (e.g. `/switch/Schedule%20Enabled/turn_on`). The older lower-case object-ID form is deprecated and stops working in newer ESPHome releases. Drive it from Node‑RED, scripts, or webhooks. |

### Scheduling

Two browser‑editable modes, gated by a master **Schedule Enabled** switch:

- **Fixed times** — set an **Open Time** and **Close Time**.
- **Sunrise/sunset** — turn on **Sun Schedule**, set your **latitude/longitude**,
  and optionally an open/close **offset** in minutes (e.g. `-30` to close 30 min
  before sunset).

### Home automation ideas

Home automation is where this device shines:

1. Use an indoor air‑quality sensor (e.g. Awair) to air out a stuffy room.
2. Poll PurpleAir hourly and close the window when outdoor air goes bad.
3. Compare indoor/outdoor temperature and cool the room when it helps.
4. Check a weather API and close the window when rain is forecast.
5. Open at sunrise to wake up to the birds.

Full step‑by‑step guides for all of the above live in the
[**project wiki**](https://github.com/Valar-Systems/Glasscalibur/wiki).

---

## Repository layout

| Path | Contents |
| --- | --- |
| [`firmware/`](/firmware) | **Current firmware** — the ESPHome entry file `glasscalibur.yaml`, its local `packages/`, and (in `esphome/`) the flashing/release guide. |

---

## How to build it

To keep it affordable, there's a kit — sourcing the screws and hardware
individually gets expensive fast.

Two kit versions are available — one with the 3D‑printed plastics and one
without (print your own):

- [Kit **excluding** 3D‑printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892240955)
- [Kit **including** 3D‑printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892208187)

Full assembly instructions and a build video are in the
[**Assembly Guide**](https://github.com/Valar-Systems/Glasscalibur/wiki/Assembly-Guide).

## How to 3D print it

The STEP files and print platter in this repository were for the old design;
they are kept at the [`legacy-old-design`](https://github.com/Valar-Systems/Glasscalibur/tree/legacy-old-design) tag.

## How to install it

Installation is **fast** — a few minutes of work, then a 24‑hour wait for the
adhesive to cure.

1. Attach the **window mount** (to the sash).
2. Attach the **sill mount**.
3. Wait **24 hours** for the adhesives to set, then start using the opener.

Both mounts are adhesive; if needed you can add a screw into the sill, but that
hasn't been required. Full details are in the
[**Window Installation Guide**](https://github.com/Valar-Systems/Glasscalibur/wiki/Installation-Guide).

---

## Firmware: flashing & updates

- **First flash** of a blank board is over **USB** with the ESPHome CLI
  (`esphome run firmware/glasscalibur.yaml`) or via
  [web.esphome.io](https://web.esphome.io).
- After that, update **over the air**: open the web UI → **Diagnostics** →
  **Update Firmware (GitHub)**, and the device pulls the
  [latest release](https://github.com/Valar-Systems/Glasscalibur/releases/latest)
  and reflashes itself.

The build, release, and OTA process is documented in
[`firmware/esphome/README.md`](/firmware/esphome/README.md).

---

## Documentation

The [**project wiki**](https://github.com/Valar-Systems/Glasscalibur/wiki) has
the full guides:

- [3D Printing](https://github.com/Valar-Systems/Glasscalibur/wiki/3D-Printing-Guide)
- [Assembly](https://github.com/Valar-Systems/Glasscalibur/wiki/Assembly-Guide)
- [Window Installation](https://github.com/Valar-Systems/Glasscalibur/wiki/Installation-Guide)
- [Wi‑Fi Setup](https://github.com/Valar-Systems/Glasscalibur/wiki/WiFi-Setup)
- [Web UI](https://github.com/Valar-Systems/Glasscalibur/wiki/Web-UI-Guide)
- [Motor & Stall Tuning](https://github.com/Valar-Systems/Glasscalibur/wiki/Motor-Setup)
- [Scheduling](https://github.com/Valar-Systems/Glasscalibur/wiki/Scheduling-Guide)
- [Security & Tamper](https://github.com/Valar-Systems/Glasscalibur/wiki/Security-and-Tamper)
- [API](https://github.com/Valar-Systems/Glasscalibur/wiki/API-Guide)
- [Home Assistant](https://github.com/Valar-Systems/Glasscalibur/wiki/Home-Assistant-Guide)
- [Firmware Updates](https://github.com/Valar-Systems/Glasscalibur/wiki/Firmware-Updates)

---

## License

The firmware is licensed under the **GNU GPL v3** — see
[`firmware/LICENSE`](/firmware/LICENSE).

If this project is useful to you, you can support it via
[GitHub Sponsors](https://github.com/sponsors/valar-systems).
