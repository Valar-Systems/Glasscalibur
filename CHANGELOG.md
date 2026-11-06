# Changelog

All notable changes to the Glasscalibur firmware are documented here. As of
v2.0.0 the version number comes from the release git tag: the build workflow
stamps it into the `fw_version` substitution (feeding `project.version` reported
to Home Assistant / the ESPHome dashboard and the "Firmware Version" diagnostic
sensor). Local/branch builds report `dev`.

This project adheres to [Semantic Versioning](https://semver.org/) and the
format is based on [Keep a Changelog](https://keepachangelog.com/).

## [2.2.0] - unreleased

### Added
- **Learned open limit.** The open switch position is learned per unit: each
  open that starts from a fresh close-switch home, with no stall on the way,
  records where the open switch triggers (accepted between 94.0 and 101.0 mm
  from the close switch). The open then drives to that position + 0.5 mm
  (101.0 mm before anything is learned) and stops on the switch. Works with
  both the new carriage (switch near 99.3 mm) and the old one (~95.5 mm).
  The learned value is saved, and flash is written only when it moves by more
  than 0.05 mm.
- **Uncalibrated speed lock.** Until a calibration has completed successfully
  on the unit, every move (open, close, Button 1, schedules, Home Assistant)
  runs at the Fast preset whatever the speed setting, because that is where
  the driver's default StallGuard threshold detects stalls. The web UI shows
  **Calibration Notice** ("Not calibrated - run Calibrate") at the top of
  Control and **Speed Lock** ("Speed locked to Fast until calibration has
  run") under the Speed setting; the diagnostic binary sensor **StallGuard
  calibrated** shows the state to Home Assistant. Once a calibration succeeds
  the speed setting applies. A later calibration that fails or is aborted keeps
  the last good one (including its motor current) and logs a warning with the
  reason. Units already calibrated with an earlier version count as calibrated.
  Calibration itself still runs at the speed setting, which it tunes for.
- **Calibrated speed.** Each successful calibration records the speed it ran
  at, since its StallGuard tune is only valid there. If the speed setting is
  changed afterwards, moves keep running at the calibrated speed and **Speed
  Lock** reads "Speed change needs recalibration - running at <speed>" until a
  calibration at the new speed succeeds; Calibration Status shows STALE meanwhile.
  Units calibrated with an earlier version use the speed that calibration
  recorded (logged at startup); only if none was recorded is the current speed
  setting assumed. **Some updated units may therefore go back to the speed they
  were calibrated at** (shown under the Speed control) until they recalibrate at
  their current speed. Nothing in the firmware changes the speed on its own (no
  quiet or night speed; schedules only open and close).
- **Open stroke** diagnostic sensor (mm): the learned open switch position,
  also logged on every open.
- **Fault** diagnostic text sensor: *open switch position out of range*,
  *open limit switch not detected* (an open reached its target without the
  switch: it stops there and the position is not re-zeroed; closing still
  works) and *close limit switch not detected* (a close ran 0.6 mm past zero
  without the switch: it stops). Each is logged as a warning.
- The log shows the step count when the open switch triggers and where the
  motor stopped, so the coast past the switch is visible.
- **Obstruction** event entity (event type `obstructed`): fires each time a
  stall stops a motion outside calibration, whichever detector caught it. Home
  Assistant automations can trigger on it directly. It needs a stall detector
  on (StallGuard now ships on; vibration detection ships off until an
  auto-calibration enables it). The trip counters stay.

### Changed
- Repository: the old Model-H design is removed (kept at the `legacy-old-design`
  tag); the firmware is split into local packages under `firmware/packages/`
  with `firmware/glasscalibur.yaml` as the one entry file (no behaviour change);
  `README.md` and `firmware/README.md` are rewritten for the current design.
- The open no longer drives toward the old fixed 111 mm end of travel; a close
  runs at most 0.6 mm past zero before stopping on the close switch.
- **StallGuard Enabled** now defaults on for units that have never stored a
  setting, as the backstop if a limit switch fails before the open position
  is learned. Units that already stored a setting keep it.
- After updating from an earlier version, the first open may stop short and
  report *open limit switch not detected* (positions saved by older firmware
  used the old 111 mm scale). One full close fixes it; the next open learns
  the open position.
- A **STOP from any source** — web UI, Home Assistant, the API, Button 1 — now
  ends a running auto-calibration, and so does a user Open / Close /
  Set-position (which then makes its move). Calibration is left marked
  "Aborted by user", with both stall detectors on and the vibration threshold
  restored.
- After a stall, the back-off is shown as the movement it is: State and the
  cover report the real direction until the motor stops, then IDLE. The
  back-off target stays inside the travel range, and a stall during a back-off
  just stops.
- The **motor stops when a firmware update begins**, however it was started.
- A reboot mid-travel now keeps the position where the motor stopped, not
  where the travel began.
- Docs: web control URLs use the entity-name form, e.g.
  `/cover/Glasscalibur/open`.
- Build: ESPHome pinned to 2026.6.5 (the version v2.1.0 shipped with) and both
  external components pinned to the commits v2.1.0 used.

### Fixed
- The unit no longer reboots every 15 minutes when no Home Assistant (native
  API client) is connected.

## [2.1.0] - 2026-07-23

### Added
- **Speed presets — Slow / Medium / Fast** (Motion Tuning): 1200 / 2600 / 5500
  steps/s, chosen from an accelerometer resonance sweep of this mechanism. The
  drivetrain has a violent resonance at ~2900–3300 steps/s (worst 3000–3100);
  all three presets stay clear of it (ramps only cross it transiently, which is
  harmless). The max-speed cap was raised 1200 → 5500 — the motor tracks cleanly
  well beyond, but above ~6000 the free-run vibration starts false-tripping the
  stall detector, so 5500 is the ceiling. Fast is ~4.5× the previous top speed.
  The raw Speed slider moves to the advanced group.
- **StallGuard Auto-Tune** switch (advanced group, opt-in, default OFF): a
  self-healing SGTHRS that cross-checks every StallGuard trip against the
  accelerometer. It raises the threshold when vibration catches a stall StallGuard
  missed, and lowers it after a run of quiet mid-travel trips that look like false
  positives. Adjustments are one register step at a time, clamped to a safe band,
  logged, and counted via a new "Auto-Tune Adjustments" diagnostic. A fresh
  Auto-Calibrate always overrides whatever it has drifted to.

### Changed
- **Calibration button gesture: double-click → 7 quick presses** (GPIO21).
  Auto-calibration drives the window through its full travel, so the trigger
  is now deliberately hard to hit by accident; a stray double-tap no longer
  starts it. The 3–10 s hold (Wi-Fi credential wipe) on the same button is
  unchanged, and the two timings still cannot overlap.

## [2.0.0] - 2026-07-22

Major architectural change: the firmware is now built on the shared
**valar-core** + **scheduling** packages (from `Valar-Systems/valar-motion`,
pinned at `v0.3.0`) rather than a single monolithic config. Board infrastructure
(Wi-Fi, API, OTA, web UI, diagnostics, the TMC2209 driver, and the daily/sun
schedule) comes from core; only Glasscalibur's product hardware and logic (cover,
limit switches, LIS2DH12 tamper/vibration, TMP1075, buzzer, child lock, and the
auto-calibration sequence) live in the product layer.

### Added
- **Auto-calibration** (double-click the Wi-Fi/Calibrate button, or the
  "Auto-Calibrate" entity): a 3-phase sequence that homes on the limit switches,
  searches for the minimum viable motor current, and tunes StallGuard (SGTHRS /
  TCOOLTHRS) and the vibration threshold from the measured travel. Result is
  shown in "Calibration Status" and persisted. Includes a stall auto-release
  back-off and a thermal guard.
- **Board** diagnostic sensor (from core), reporting the board identity.

### Changed
- **BREAKING — tuning entity names** now match the shared core across the Valar
  product line. Home Assistant `entity_id`s change accordingly:
  `max_speed` → **Speed**, `acceleration` → **Acceleration**,
  `irun` → **IRUN (motor current)**, `SGTHRS` → **SGTHRS (stall threshold)**,
  and the `TSTEP Sensor` / `SG_RESULT Sensor` diagnostics → **TSTEP** / **SG_RESULT**.
  Motor-current entries are still capped at IRUN 19 (rated 0.6 A).
- Firmware version now comes from the release tag (see note above) instead of a
  hardcoded `firmware_version` substitution.
- The GitHub-OTA "Update Firmware" button, the Restart button, and the
  Firmware Version / network-info diagnostics are now provided by core (the OTA
  asset URL — `Glasscalibur.ota.bin` from the latest release — is unchanged).

## [1.2.0] - 2026-06-30

### Added
- **Child Lock** switch (Control group). When ON, the physical Button 1
  (single- and double-click) is ignored so the cover can't be opened, closed,
  or stopped from the on-device button. Remote control is intentionally
  unaffected: the web UI, Home
  Assistant, and the open/close schedule all keep working, so you can still
  operate the cover and toggle the lock from your phone. The Wi-Fi-reset button
  (GPIO21) is also left active so the device can always be recovered. State
  persists across reboots; defaults OFF so a fresh unit is never locked.

## [1.1.0] - 2026-06-29

### Added
- **GitHub OTA updates**: `http_request` OTA platform plus an "Update Firmware
  (GitHub)" button that pulls the latest release from GitHub and self-flashes.
- **Firmware Version** diagnostic sensor and a **Restart** button.
- **Sunrise/sunset schedule**: latitude/longitude + signed minute offsets and a
  "Sun Schedule" switch (60 s sun poll). The fixed Open/Close-Time triggers are
  suppressed while Sun Schedule is on.

### Changed
- **Grouped web UI** (`web_server` version 3): entities are organized into
  Control / Motion Tuning / StallGuard / Security-Tamper / Schedule /
  Diagnostics groups instead of one alphabetical list.
- Rewrote the firmware README to document the feature set and the
  release-publishing workflow the GitHub OTA button depends on.

## [1.0.0] - 2026-06-09

### Added
- Initial ESPHome firmware for the ESP32-C6 + TMC2209 stepper window cover.
- Cover control (open / close / position) with end-stop limit switches for
  absolute position calibration; position persisted across reboots.
- Browser-based control panel (no Home Assistant required) plus the native
  ESPHome API for optional Home Assistant pairing.
- Daily open/close time schedule with browser-editable times and timezone.
- Anti-tamper detection (LIS2DH12 accelerometer baseline + buzzer alarm).
- Stall detection: TMC2209 StallGuard plus a secondary accelerometer-based
  vibration-stall check.
- Motor over-temperature cutoff (TMP1075, hard stop above 80 °C).
- Wi-Fi provisioning with no hardcoded credentials (fallback hotspot + captive
  portal, Improv over USB serial).

[2.2.0]: https://github.com/Valar-Systems/Glasscalibur/compare/v2.1.0...main
[2.1.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v2.1.0
[2.0.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v2.0.0
[1.2.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.2.0
[1.1.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.1.0
[1.0.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.0.0
