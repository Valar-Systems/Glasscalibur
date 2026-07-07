# Changelog

All notable changes to the Glasscalibur firmware are documented here. The
version number is the `firmware_version` substitution in
[`firmware/esphome/Glasscalibur-esphome.yml`](firmware/esphome/Glasscalibur-esphome.yml),
which feeds `project.version` (reported to Home Assistant / the ESPHome
dashboard) and the "Firmware Version" diagnostic sensor on the web UI.

This project adheres to [Semantic Versioning](https://semver.org/) and the
format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.2.0] - 2026-06-30

### Added
- **Child Lock** switch (Control group). When ON, the physical Button 1
  (single- and double-click) is ignored so the cover can't be opened, closed,
  or stopped from the on-device button — useful for keeping a child from
  operating it. Remote control is intentionally unaffected: the web UI, Home
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

[1.2.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.2.0
[1.1.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.1.0
[1.0.0]: https://github.com/Valar-Systems/Glasscalibur/releases/tag/v1.0.0
