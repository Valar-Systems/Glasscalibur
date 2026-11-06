# Glasscalibur firmware — context for working on auto-calibration (v1.3.0)

This file briefs an AI coding agent (Claude Code) working on
`firmware/glasscalibur.yaml` (calibration lives in `firmware/packages/calibration.yaml`). Read fully before editing. The sections marked
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
Cover `open_action` targets the learned open stroke + 0.5 mm (101.0 mm before
anything is learned) and stops on the open switch; `close_action` targets
-0.6 mm and stops on the close switch (see "Learned open limit" below).

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
  CAD stroke 111.3 mm (the old fixed `max_distance_steps` 341387, removed
  in favour of the learned open limit), ram speed 0.82 mm/s at speed 2500;
  OPEN-2 closed). There is deliberately **no fixed
  travel timeout**: a full travel is (101.0 mm × steps_per_mm)/global_speed
  (≈228 s at the default 1500 steps/s, speed user-tunable 100..10000), so
  the old `cal_travel_timeout: 90s` expired mid-travel and failed every
  healthy probe. Each travel instead arms `cal_t0_ms`/`cal_budget_ms` from
  the live speed (nominal × 1.5 + 10 s).
- Triggers: GPIO21 **7 quick presses** (on_multi_click, presses ≤0.6 s each —
  deliberately hard to hit by accident, since calibration drives full travel;
  the 3–10 s hold on the same pin is Wi-Fi credential wipe — different timing,
  must not overlap); a STOP from any source — Button 1 single-click, the
  web UI, Home Assistant, the API, the 80 °C cutoff — **aborts** a running
  calibration through `cal_abort` (also restores irun 19 and the saved
  vibration threshold), and so does a user Open / Close / Set-position (which
  then makes its move); Button 1
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
   `stepper.report_position:` the open target — the saved position can
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
- (Done: the open stroke is now measured and learned — see "Learned open
  limit". The old fixed `max_distance_steps` (341387) overshoot is gone.)
- (Resolved: TCOOLTHRS is now derived from measured cruise TSTEP by
  calibration — see §4.6.)
- Calibration refusals (busy/tamper/hot) are log-only — no beep or status
  feedback for a user standing at the device.
- (Resolved: a STOP from any source, and any user Open / Close /
  Set-position, now end a running calibration through `cal_abort`; the
  firmware's own stops go through `motion_halt` and never end it.)
- **Position after an interrupted calibration.** When a calibration is cut
  short (STOP, a user move, a thermal stop, or a failed run), the step
  counter may be off: each attempt of a leg re-claims a full travel from
  wherever the previous attempt stopped. The counter is corrected the next
  time the window reaches an end stop; until then a Close can stop short of
  fully closed while reporting closed. Follow-up: after any interrupted
  calibration, mark the position unknown and drive the next Open / Close to
  its limit switch before trusting the counter.
- **Position after a reboot mid-travel.** A soft reboot (Restart button, the
  end of a firmware update) saves the stop point through `on_shutdown`, and
  the saved position is refreshed every 200 ms while moving. A power cut,
  crash or watchdog reset runs no shutdown, so it keeps only what ESPHome
  last flushed to flash (at most once a minute): the restored position can
  be up to a minute of travel old. Follow-up: after an unclean reset, boot
  with the position marked unknown until the next end stop.
- `cal_vib_prev` is volatile: a reboot mid-calibration leaves the raised
  0.60 g backstop in the Vibration Threshold number (still a working, just
  laxer, detector). Persist it (plus an in-cal flag) if this matters.
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

- Validate: `esphome config firmware/glasscalibur.yaml` (passes on ESPHome
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

## Learned open limit (v2.2.0)

All distances are from the close switch (S5) trigger = 0, at `steps_per_mm`
3066.6667 (Tr6×1 leadscrew, 12T:23T). Constants live in the board wrapper.

- **Learning.** S5 re-zeroing the counter marks a *fresh home*. The next open
  (`drive_open`: Open, Set-position 100 %, a schedule, or calibration's open
  leg on its first attempt) is a *learning open* unless a stall (StallGuard or
  vibration) happens first. When S4 triggers on a learning open, its count is
  the stroke: accepted only between `open_learn_min_mm` 94.0 and
  `open_learn_max_mm` 101.0 mm, else the fault *open switch position out of
  range* and the previous value stays. An accepted value is stored in
  `open_stroke_steps` (persisted) only when it moves by more than
  `open_persist_delta_mm` 0.05 mm, so routine opens don't write flash.
- **Targets.** Open = stroke + `open_margin_mm` 0.5 mm (`open_default_mm`
  101.0 mm before anything is learned). Close = −`close_overtravel_mm` 0.6 mm.
  The cover's 0..1 position is scaled to the stroke (101.0 mm before learning).
- **S4 press.** Stops at once (deceleration `inf`: VACTUAL 0, no ramp), logs the
  trigger count, then learns — only a press that comes *while opening* on a
  learning open — or re-syncs the counter to the learned stroke (drift
  correction; to `open_default_mm` before anything is learned, which can only
  over-estimate the position, so a following close runs long and S5 stops it).
  An out-of-range learning does not re-sync. 300 ms later `s4_coast_report` logs
  where the motor stopped and the coast — WARN above `coast_limit_mm` 0.3 mm.
- **After an update from older firmware** the saved counter is still on the
  old 111 mm scale (S4 used to re-sync to 341387), so until the first full
  close an open can stop short and report *open limit switch not detected*.
  One full close re-zeroes it; the next open learns the stroke.
- **Faults** (diagnostic text sensor **Fault**, each logged at WARN): *open
  switch position out of range*; *open limit switch not detected* (an open
  reached its target with S4 released — stopped there, no re-zero, closing
  still allowed); *close limit switch not detected* (a close reached −0.6 mm
  with S5 released — stopped). Not raised during calibration, whose legs treat
  "count arrived, no switch" as step loss and escalate. Cleared by the next
  accepted learning / S4 press / S5 press; a reboot clears all.
- **Logs** (tag `limit`): `Open stroke … ; open target …` at INFO on every
  open; `S4 triggered at N steps (X mm)`; `Open stroke learned / confirmed …`;
  `S4 re-sync: counter A -> B steps`; `S4 stop: motor stopped at N steps,
  coast C steps (X mm)`.
- **Diagnostic sensor** **Open stroke** (mm, 2 decimals; unknown until learned).
- **StallGuard Enabled** now defaults ON (the backstop if a switch dies before
  the stroke is learned). Caveat: with core's default TCOOLTHRS (100) the chip
  only reports stalls near the Fast preset (cruise TSTEP ≈ 375000/speed: Slow
  ≈ 312, Medium ≈ 144, Fast ≈ 68) until an auto-calibration sets TCOOLTHRS.

## Uncalibrated fail-safe (v2.2.0)

`sg_calibrated` (persisted, never cleared) is set in the success branch of
`auto_calibrate`, next to `cal_speed_at`. A unit calibrated by an earlier
firmware is recognised at boot (on_boot 500): `cal_speed_at` is only ever
written by that success branch, so a nonzero value sets the flag once.

- **Speed lock.** Until the flag is set, every move runs at `speed_fast` (5500,
  the Fast preset): `drive_open`, `drive_close` and the cover's partial
  `position_action` apply the effective speed before setting the target, and so
  do on_boot 500 (after core's 600 apply), the Speed select and core's raw Speed
  number (extended). Effective speed = `global_speed` when calibrated or while a
  calibration runs, else `speed_fast`. Calibration runs at the user's speed: it
  measures cruise TSTEP there to set TCOOLTHRS, and holds the StallGuard
  reaction off anyway. The driver's default threshold (TCOOLTHRS 100) only
  reports stalls near Fast (cruise TSTEP ≈ 375000/speed ≈ 68).
- **Failed / aborted calibration** (could not home, never reached both limits,
  too hot, aborted by user): `cal_keep_last_good` logs a WARN with the reason,
  puts the last good chosen motor current back (rated 19 if never calibrated)
  and re-applies the effective speed. SGTHRS / TCOOLTHRS are only written on
  success, so the last good tune stays.
- **Web UI / HA:** *Calibration Notice* (top of Control), *Speed Lock* (under the
  Speed select), *StallGuard calibrated* (binary sensor, Diagnostics).

## Calibrated speed (v2.2.0)

`cal_speed` (persisted, 0 = not recorded) holds the speed the last successful
calibration ran at — the only speed its StallGuard tune is valid for. It is set
in the success branch next to `cal_speed_at`; a failed calibration keeps it. A
calibrated unit with `cal_speed` 0 (calibrated by older firmware) takes the speed
that calibration recorded (`cal_speed_at`) at boot, logged at INFO — a setting
changed since is then an ordinary mismatch (runs at the recorded speed, Speed
Lock notice, STALE). Only with no recorded speed is the current setting assumed
(logged at WARN).

The effective speed (substitution `effective_speed`, every speed setter): the
setting while a calibration runs; Fast until calibrated; otherwise `cal_speed`.
So changing the setting after a calibration keeps moves at the calibrated speed;
**Speed Lock** reads "Speed change needs recalibration - running at <name> (<n>
steps/s)" and Calibration Status appends STALE (now compared with `cal_speed`),
until a calibration at the new setting succeeds.

Speed writers (surveyed for this): the Speed select and core's raw Speed number,
both user actions. Nothing changes the speed on its own, so there is one
calibrated speed rather than one per preset.
