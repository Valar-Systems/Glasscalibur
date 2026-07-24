# Glasscalibur firmware — context for working on auto-calibration (v1.3.0)

This file briefs an AI coding agent (Claude Code) working on
`Glasscalibur-esphome.yml`. Read fully before editing. The sections marked
**INVARIANT** are safety-load-bearing; do not change their behavior without
flagging it explicitly to the user.

## 1. What this device is

Glasscalibur is a commercial motorized opener for horizontal sliding windows
(Valar Systems). An aluminum tube sits in the window sill track; a NEMA 8
stepper drives a **non-backdrivable leadscrew** that pushes/pulls the sash.
It ships to non-technical consumers, controls a window a child can reach, and
doubles as a window lock — so obstruction detection, thermal limits, and
"never move silently/unexpectedly" are product-safety requirements, not
preferences.

Firmware: single ESPHome YAML (~2,480 lines), ESP32-C6-MINI-1, esp-idf.
External components: `github://slimcdk/esphome-custom-components`
(tmc2209_hub, tmc2209, stepper) and `github://Valar-Systems/esphome-lis2dh12`.
License GPL v3. Version lives in `substitutions: firmware_version` — bump on
every released change (currently `1.3.0`).

## 2. Hardware facts that constrain code

| Item | Value | Consequence in code |
|---|---|---|
| Motor | Lin X208-047-01, NEMA 8, 0.6 A/phase rated, 8 Ω, 0.058 N·m | irun must be capped at 19 (see math below) |
| Motor max case temp | **60 °C** (datasheet hard limit) | thermal thresholds; cal refuses >50 °C |
| Driver | TMC2209, UART, rsense 0.22 Ω, vsense=false | I_RMS = (CS+1)/32 × 0.9575 A |
| irun→current | 15→0.48 A · 17→0.54 A · **19→0.60 A (rated)** · 25→0.78 A · 31→0.96 A | candidates {12,15,17,19}; never probe above 19 |
| Stall behavior | current-regulated; stall ≠ overcurrent, = violent vibration + skipped steps | position lies during stall; limit switches are truth |
| Leadscrew | not backdrivable | a stall HOLDS clamp force until reverse motion → auto-release exists |
| Temp sensor | TMP1075 @ I2C 0x49, on motor case, `id: motor_temp` | NAN = sensor absent/failed = must refuse, never ignore |
| Accelerometer | LIS2DH12, shared I2C bus with TMP1075 | one bus fault kills both temp + vibration sensing (StallGuard survives — UART) |

GPIO map (comment block near top of YAML is authoritative): GPIO0/1 TMC UART,
GPIO3 close limit, GPIO5 buzzer, GPIO6 INDEX, GPIO8 TMC ENN (strapping pin),
GPIO14 DIAG→on_stall, GPIO15 open limit, GPIO19/20 I2C, GPIO21 calibration /
Wi-Fi-reset button, GPIO23 Button 1.

State machine `global_state`: 0 IDLE · 1 OPENING · 2 CLOSING · 3 TAMPERED.
Cover `open_action` targets `${max_distance_steps}`; `close_action` targets 0.

## 3. What v1.3.0 added (the code you're working on)

All auto-calibration content was originally a separate package, now inlined.
Grep landmarks: `Auto-calibration (v1.3.0)` header doc, `auto_calibrate`
script, `# --- Auto-calibration + stall-release state` in globals.

Entities/IDs added:
- `script: auto_calibrate` (mode: single), `cal_leg` (parameterized
  `opening: bool` — one escalating travel; see §4.5), `cal_beep_ok`,
  `cal_beep_fail`, `stall_release_clear`, `cal_thermal_guard` (called
  before EVERY cal attempt: motor >55 °C or NAN mid-run → ship-safe stop
  with `cal_result = 4`; the 50 °C gate only runs at start, and field
  testing showed 49 → 61.5 °C during a multi-travel search). Abort paths
  must `script.stop` BOTH `auto_calibrate` and `cal_leg` — the former is
  parked in `script.wait: cal_leg` while a leg runs.
- `interval: 100ms` sampler → updates `cal_sg_min` (from
  `id(driver)->read_register(SG_RESULT)`) and `cal_vib_max` (from
  `accel_x/y/z`, formula `fabsf(sqrtf(x²+y²+z²)/9.80665f − 1.0f)`), gated
  on `cal_active && state∈{1,2} && current_position != target_position`
  plus a ramp-aware launch mask (`600 ms + 1000·speed/accel`, capped
  3.1 s). Both gates are load-bearing: the mask keeps acceleration-ramp
  shake out of the free-run baseline, and the position check keeps the
  ≤200 ms software-arrival gap (motor stopped, state still 1/2, TSTEP
  decaying to idle, SG near zero) out of the stats — one tick in that gap
  shipped TCOOLTHRS=37098 and a fake SGmin=32 in field testing.
- **UNITS LANDMINE:** the LIS2DH12 sensors publish **m/s²** (ESPHome
  convention); every threshold in the YAML (vibration, tamper) and the
  stored tamper baselines are in **g**. Every consumer divides readings by
  9.80665 before comparing. Omitting the division makes
  `|mag − 1|` ≈ 9 "g" at rest → every sample reads as a stall → any move
  dies the moment the launch mask expires. This shipped as a live bug
  (false-failed every calibration homing; vibration stall detection had
  never actually worked) and was fixed 2026-07-09.
- `button: "Auto-Calibrate"`, `text_sensor: "Calibration Status"`
  (`id: cal_status`, persisted result globals, shows "Calibrating" while
  running, appends STALE if `cal_speed_at != global_max_speed`)
- Globals: `cal_active, cal_sg_min, cal_vib_max, cal_irun_index, cal_done,
  cal_travel_ok, cal_t0_ms, cal_budget_ms, cal_vib_prev, cal_escalate,
  cal_sg_low_count, cal_phase (1 homing/2 open leg/3 close leg — drives the
  per-phase "Calibrating N/3 ..." status text; field 2026-07-10: a user read
  the deliberate homing close as a malfunction and aborted)` (volatile) ·
  `cal_result (0 none/1 ok/2 sticky/3 failed/4 thermal/5 user abort),
  cal_irun_chosen, cal_sgthrs_chosen, cal_sgmin_seen, cal_vibmax_x100,
  cal_speed_at` (persisted) · `stall_release_active`
- Substitutions: `cal_sg_floor: "80"`, `cal_vib_backstop: "0.45"`,
  `stall_release_steps: "24500"` (≈8 mm at 3066.7 steps/mm — measured from
  CAD 2026-07-10: **Tr6×1 leadscrew, 12T:23T motor→screw reduction**,
  stroke 111.3 mm = 341387 steps, ram speed 0.82 mm/s at speed 2500;
  OPEN-2 closed). There is deliberately **no fixed
  travel timeout**: a full travel is `max_distance_steps/global_max_speed`
  (≈228 s at the default 1500 steps/s, speed user-tunable 100..10000), so
  the old `cal_travel_timeout: 90s` expired mid-travel and failed every
  healthy probe. Each travel instead arms `cal_t0_ms`/`cal_budget_ms` from
  the live speed (nominal × 1.5 + 10 s).
- Triggers: GPIO21 **7 quick presses** (on_multi_click, presses ≤0.6 s each —
  deliberately hard to hit by accident, since calibration drives full travel;
  the 3–10 s hold on the same pin is Wi-Fi credential wipe — different timing,
  must not overlap); Button 1 single-click **aborts** a running calibration
  (also restores irun 19 and the saved vibration threshold); Button 1
  double-click, the time schedules, the sun schedule, and the tamper check
  are all gated on `!cal_active` so nothing re-targets the stepper or
  latches tamper mid-sequence
- Stall auto-release blocks in BOTH `on_stall` (StallGuard path) and the
  vibration-stall branch of the interval check
- Vibration-stall detector hardening (shipped with v1.3.0 after a false
  trip ~2 s into a calibration homing travel): launch mask is ramp-aware
  (`500 ms + 1000·speed/accel`, capped 3 s) instead of a fixed 500 ms that
  was shorter than the acceleration ramp, and the leaky counter now counts
  each **distinct** LIS2DH12 sample once (the sensor publishes at 500 ms;
  the 200 ms tick used to count one cached reading 2–3×, so "5 samples"
  tripped on ~2 real readings ≈1 s instead of the documented ~2.5 s)

## 4. Calibration algorithm (as implemented)

1. Preconditions: refuse if `global_state != 0`, tamper latched, already
   calibrating, or `isnan(motor_temp) || motor_temp > 50`.
2. Announce: 3 beeps + 2 s stand-clear delay. No silent motion, ever.
3. Detector posture: `switch.turn_off: stallguard_enabled`, and
   `switch.turn_on: vib_enabled` — the vibration detector is the backstop
   and defaults OFF from the factory, so it must be forced on, not merely
   left alone. Its threshold is raised to `max(current, ${cal_vib_backstop})`
   for the run (the user's value is itself a calibration output and may be
   mistuned); `cal_vib_prev` remembers the original for fail/abort restore.
4. Home to close limit at irun 19. Homing (and every re-home) first does
   `stepper.report_position: ${max_distance_steps}` — the saved position can
   lie after skipped steps, so claim full-open and let the close command
   cover the whole travel; the limit switch re-syncs to 0 on arrival.
   Skipped entirely when the close limit is already pressed (the switch
   only fires on its press EDGE — closing again from on top of it would
   grind the end-stop for a full travel budget).
5. Single-pass escalating search (`cal_leg` script, `parameters: opening`,
   called twice with `script.wait` between): ONE open travel that starts at
   irun 12 and escalates in place up `{12, 15, 17, 19}`, then ONE close
   travel validating the settled current over the full distance
   (`cal_irun_index` carries over — the close leg may escalate further).
   Escalation triggers, any of: vibration stall (detector stops the motor →
   state 0; its auto-release backs off ~8 mm = run-up for the retry) ·
   SG margin starvation (sampler sets `cal_escalate` at NET 8 low ticks —
   LEAKY +1/−1 counting, never reset-on-good: a skipping stall oscillates
   SG sample-to-sample and consecutive counting sat at zero through a real
   field stall) · software arrival without the switch (silent step loss) ·
   per-attempt deadline (`cal_t0_ms`/`cal_budget_ms`, live speed × 1.5 +
   10 s). The vibration detector's own counter is likewise asymmetric
   (+2 loud/−1 quiet) for the same oscillation reason, and
   `cal_vib_backstop` is 0.45 g — field stall judder alternated 0.6–1.2 g
   violent phases with quiet ones, and a 0.60 backstop missed too many
   samples to ever accumulate.
   - Success oracle = the physical LIMIT SWITCH, never the step counter:
     every attempt first re-claims a full travel of commanded distance via
     `report_position` (a post-stall counter lies).
   - Ladder exhausted (still no switch at 19) = leg failed → run FAILED.
     Never muscle through what might be an obstruction.
   - Replaced the v1.3.0-initial 4-probe × full-travel search (up to ~11
     travels; field run hit 61.5 °C). Worst case is now ~2 travels + a few
     seconds per escalation.
6. Outcome, all from the VALIDATION leg's stats (`cal_sg_min` /
   `cal_vib_max` / `cal_tstep_max` reset per LEG in `cal_leg`, never per
   attempt — per-attempt resets once shipped a tune from an empty bucket
   when the leg escalated 1.2 s before the switch: SGmin=510 → SGTHRS=120,
   trip level above cruise readings):
   - `SGTHRS = clamp(cal_sg_min / 4, 4, 120)` via `tmc2209.stallguard` +
     `global_sgthrs`; skipped (previous value kept) if the leg somehow
     gathered no samples (`cal_sg_min == 510`).
   - Vibration Threshold = `clamp(3 × cal_vib_max, 0.15, 0.45)` g via
     `number.set` (replaces the raised backstop).
   - `TCOOLTHRS = 1.5 × cal_tstep_max` (measured cruise TSTEP; slowest
     unmasked sample). The chip only asserts stalls while
     `TSTEP < TCOOLTHRS`, and the old fixed default (100) sat below the
     ~150 cruise TSTEP at speed 2500 — StallGuard was velocity-gated INERT
     in normal operation on every unit until this derivation existed.
   On failure the pre-cal vibration threshold is restored instead.
7. Always (success or fail): `switch.turn_on` BOTH detectors,
   `cal_active = false`, update `cal_status`.

## 5. INVARIANTS — do not break

1. **SGTHRS = SGmin/4, never SGmin/2.** TMC2209 trips when
   `SG_RESULT ≤ 2×SGTHRS`. SGmin/2 puts the trip level AT the worst
   legitimate reading → instant false stalls (this was the original tuning
   bug). SGmin/4 = trip at half the worst legitimate load.
2. **irun ≤ 19 everywhere.** 19 = rated 0.6 A on this sense-resistor math.
   Higher values overdrive the motor toward its 60 °C case limit
   (irun 25 = 130 %, irun 31 = 160 % / 14.7 W into an 80 g motor).
3. **Limit switches are the probe oracle.** Never replace with
   position-reached or SG-based success.
4. **Vibration detector stays enabled during calibration** — forced ON at
   start (it defaults OFF from the factory), threshold raised to
   `${cal_vib_backstop}` for the run and restored/replaced at exit. Only
   the SG *reaction* is gated off (its threshold is what's being tuned).
5. **Both detectors forced ON at every exit path** (success, fail, abort).
6. **Abort check precedes Child Lock** in Button 1's single-click tree.
   Stopping an autonomous multi-travel sequence is a safety control; it
   must never be lockable.
7. **3 beeps + 2 s delay before first calibration motion.**
8. **Auto-release reads `global_state` BEFORE it is zeroed** (direction:
   CLOSING→back off toward open, OPENING→toward close, clamp ≥0).
   One release per event via `stall_release_active`; `stall_release_clear`
   (mode: restart) clears the flag and re-saves position after 5 s. A second
   stall during release just stops. Release must exist in BOTH stall paths.
9. **NAN temperature = refuse**, in the cal gate and any future thermal
   logic. Sensor absent means protection absent.
10. **GPIO21 gestures must not overlap:** 7 quick presses (≤0.6 s each) =
    calibrate; 3–10 s hold = Wi-Fi wipe.
11. **Limit-switch presses are direction-gated.** A switch press acts
    (resync position + stop) only when travel is toward that switch or the
    drive is idle; a press while moving AWAY is logged and ignored. Field
    2026-07-10: leaving the fully-open stop, drive-force build-up racks the
    sash and re-flicks the open switch for ~150 ms about 1 s into the close
    — ungated, that blip stopped the motor, re-claimed position as fully
    open, and burned three close-leg ladder rungs in 3 s (cal FAILED with a
    cold motor). 150 ms is a real contact — debounce cannot filter it, only
    the direction gate can. Never "simplify" the handlers back to
    unconditional stop-on-press.

## 6. Known gaps / sanctioned next work

From test protocol GC-TP-001 Rev A.1 (separate doc), still unimplemented:
- **FW-1/2/3:** thermal thresholds warn 50 °C / derate 55 / hard-stop 60 with
  persistent motion lockout + hysteresis (<48 resume), NAN/stale-reading
  lockout for NORMAL motion (cal gate already exists), and using the TMP1075
  **ALERT pin (GPIO18, wired, unused)** as an interrupt backstop.
- Possible: auto-recalibrate suggestion when rolling SG stats drift.
- Possible: measure TRUE close→open travel during a no-escalation open leg
  (capture `current_position` in limit_1's on_press before the resync) and
  report it — the configured `max_distance_steps` (341387) overshoots the
  physical travel by ~2-3k steps on the test unit, and that overshoot is
  what ground the end-stop through the dead-switch era (suspected origin of
  the leadscrew end-zone damage found 2026-07-10).
- (Resolved: TCOOLTHRS is now derived from measured cruise TSTEP by
  calibration — see §4.6.)
- Calibration refusals (busy/tamper/hot) are log-only — no beep or status
  feedback for a user standing at the device.
- No REMOTE abort: Button 1 is the only way to stop a running calibration.
  A user watching from HA/web UI cannot stop the sequence (cover.stop only
  fails the current probe; the script continues). Consider an "Abort
  Calibration" button entity.
- `cal_vib_prev` is volatile: a reboot mid-calibration leaves the raised
  0.60 g backstop in the Vibration Threshold number (still a working, just
  laxer, detector). Persist it (plus an in-cal flag) if this matters.
- HA / web-UI cover commands are NOT gated during calibration (the template
  cover actions can't tell the calibration script's own commands from a
  user's). A mid-cal slider drag fails the probe safely via the limit-switch
  oracle, but wastes minutes.
- Accel readings quantize at ≈0.31–0.32 m/s² (~32 mg/LSB), which matches
  8-bit low-power output — NOT the 12-bit/2 mg "high resolution" the config
  requests (`resolution: high`). Suspect the Valar LIS2DH12 fork isn't
  applying CTRL_REG1/CTRL_REG4 mode bits correctly. Detection still works
  (a real stall is ≫0.1 g) but thresholds only have ~5 LSB of headroom at
  the 0.15 g clamp floor — investigate in the fork.

Resolved in v1.3.0 (was listed here): irun number entity capped at 19
(`max_value`, fresh-boot initial 19, on_boot clamp for values restored from
older firmware).

## 7. Build / validation workflow

- Validate: `esphome config Glasscalibur-esphome.yml` (passes on ESPHome
  2026.5.3/2026.6.5). Compile: `esphome compile`, flash: `esphome run`.
- Expected pre-existing warnings (not yours): slimcdk `register_action`
  synchronous-parameter notices; strapping-pin warnings for GPIO5/8/15.
- File is LF line endings. Bump `firmware_version` on released changes.
- ESPHome quirks in this codebase: `on_value_range` fires on crossings only;
  gpio binary_sensors are polled (`use_interrupt: false` — interrupts missed
  events in testing); scripts can't be externally interrupted except
  `script.stop`; `deceleration: inf` (instant stop) is intentional;
  `ihold: 0` + `standstill_mode: freewheeling` is intentional (zero idle
  heating) — never add holding current.
