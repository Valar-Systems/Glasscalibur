"""A simulated Glasscalibur for the TP-1 dry run (B4) — BENCH ONLY, not a firmware model.

It follows the documented 2.2.0 behaviour (firmware/README.md "Motor temperature") closely
enough to exercise tools/bench/tp1_run.py end to end on a virtual clock, with the same log
lines the firmware writes. Faults for the B4 sabotages:
  --sim-fault rest-close-accepted      REST Close is not refused by the start gate
  --sim-fault refused-close-no-cancel  a refused Close leaves the pending scheduled move
Profile (not a fault): --sim-fault slow-heat  Slow strokes peak below 60 °C (exercises the
heater fallback). The default profile follows Daniel's bench note: about four strokes to 60.
"""
import math

AMBIENT, TAU_S, LAG_S = 22.0, 2400.0, 30.0
K_MOVE, K_HEAT = 0.050, 0.012          # °C/s at 600 mA moving / at IHOLD 19 standing
STROKE_STEPS, BACKOFF_STEPS = 310_000, 24_500
SPEEDS = {"Slow": 1200, "Medium": 2600, "Fast": 5500}


class SimDevice:
    def __init__(self, fault=None):
        self.fault, self.t = fault, 0.0
        self.k_move = 0.022 if fault == "slow-heat" else K_MOVE
        self.logs, self.events, self.seen = [], [], {}
        self.core = self.sens = 30.0
        self.reading, self.next_read, self.next_bench = 30.0, 0.0, 0.0
        self.pos, self.target, self.state = 0.3, None, "IDLE"
        self.stall_release = False
        self.speed, self.cal_speed, self.calibrated = "Medium", "Medium", True
        self.current, self.cal_status = 450.0, "OK: irun=14 SGTHRS=31"
        self.vals = {"SGTHRS (stall threshold)": 31, "TCOOLTHRS": 210, "Vibration Threshold": 0.21}
        self.cal_until = None
        self.lockout = self.warned = False
        self.pending, self.pending_t = 0, 0.0
        self.heat_on, self.ihold, self.heat_start, self.ka, self.stop_code = False, 0, 0.0, 0.0, 0
        self.step_t, self.step_c, self.backstop = 0.0, 0.0, False

    # ---- interface used by tp1_run.Run
    def now(self):
        return self.t

    async def start(self):
        self.log("[I][app]: Glasscalibur dev-tp1 (simulated)")

    async def close(self):
        if self.heat_on:
            self.heater_stop(5)

    async def sleep(self, s):
        end = self.t + s
        while self.t < end - 1e-9:
            self.tick(min(0.25, end - self.t))

    def last_seen(self, name):
        return self.seen.get(name, -1e9)

    def get(self, name):
        lock_text = ("Not locked" if self.calibrated and self.cal_speed == self.speed else
                     ("Speed locked to Fast until calibration has run" if not self.calibrated else
                      f"Speed change needs recalibration - running at {self.cal_speed}"))
        hs = ("BACKSTOP FIRED (62 C, motor moving)" if self.backstop else
              f"on IHOLD {self.ihold}" if self.heat_on else
              "off" + {0: "", 1: ": lockout", 2: ": 62 C backstop", 3: ": no reading 10 s", 4: ": 45 min limit",
                       5: ": script disconnected", 6: ": keepalive lost", 7: ": switched off"}[self.stop_code])
        return {"Motor Temperature": self.reading, "State": self.state, "Thermal Lockout": self.lockout,
                "Glasscalibur": round(self.pos, 4), "Speed": self.speed, "Speed Lock": lock_text,
                "Motor Current": self.current, "Calibration Status": self.cal_status,
                "StallGuard calibrated": self.calibrated, "Firmware Version": "dev-tp1",
                "StallGuard Enabled": True, "Vibration Stall Detection": True, "Child Lock": False,
                "BENCH heater": self.heat_on, "BENCH heater status": hs, **self.vals}.get(name)

    async def cover(self, path, cmd, pos=None):
        what = {"open": "Open", "close": "Close", "set": "Set position"}.get(cmd)
        if cmd == "stop":
            self.log("[D][main]: COVER stop_action")
            self.halt()
            self.cancel_pending()
            return 200
        accepted_by_fault = self.fault == "rest-close-accepted" and path == "rest" and cmd == "close"
        if self.blocked() and not accepted_by_fault:
            if not (self.fault == "refused-close-no-cancel" and cmd == "close"):
                self.cancel_pending()
            self.refused(what)
            return 200
        self.cancel_pending()
        self.log(f"[D][main]: COVER {cmd if cmd != 'set' else 'position'}_action")
        self.move_to({"open": 1.0, "close": 0.0}.get(cmd, pos))
        return 200

    async def press(self, name):
        if name == "BENCH heater keepalive":
            self.ka = self.t
        elif name in ("BENCH: fire scheduled open", "BENCH: fire scheduled close"):
            which = 1 if name.endswith("open") else 2
            self.schedule(which)
        elif name == "BENCH: trip thermal lockout":
            self.trip(1)
        elif name == "BENCH: simulate stall":
            if self.state in ("OPENING", "CLOSING"):
                self.log("[I][main]: BENCH: simulated stall")
                back = BACKOFF_STEPS / STROKE_STEPS
                tgt = self.pos + back if self.state == "CLOSING" else self.pos - back
                self.stall_release = True
                self.target = min(1.0, max(0.0, tgt))
                self.state = "OPENING" if self.target > self.pos else "CLOSING"
                self.event("Obstruction", "obstructed")
        elif name == "Auto-Calibrate":
            if self.state != "IDLE" or self.cal_until:
                self.log("[I][main]: CAL: refused - busy, tampered, or already calibrating")
            elif self.lockout:
                self.log("[W][main]: CAL: refused - thermal lockout (clears below 48 degC)")
                self.event("Thermal Alert", "refused")
            elif self.reading is None or self.reading > 50.0:
                self.log(f"[W][main]: CAL: refused - motor temp {self.reading:.1f} degC (limit 50, NAN = sensor absent)")
                self.event("Thermal Alert", "refused")
            else:
                self.log("[I][main]: CAL: starting - keep the window path clear")
                self.cal_status, self.cal_until = "Calibrating...", self.t + 600

    async def switch(self, name, on):
        if name == "BENCH heater":
            if on and not self.heat_on and not self.lockout and self.reading < 62:
                self.heat_on, self.ihold, self.stop_code = True, 19, 0
                self.heat_start = self.step_t = self.ka = self.t
                self.step_c = self.reading
                self.log(f"[W][bench]: heater ON - IHOLD 19 at {self.reading:.2f} degC")
            elif not on:
                self.heater_stop(7)

    async def select(self, name, option):
        if name == "Speed":
            self.speed = option

    async def number(self, name, value):
        if name == "Motor Current":
            self.current = float(value)

    # ---- firmware behaviour (documented)
    def log(self, line):
        self.logs.append((self.t, line))

    def event(self, entity, etype):
        self.events.append((self.t, entity, etype, self.reading))

    def blocked(self):
        return self.lockout or self.reading is None or self.reading >= 55.0

    def refused(self, what):
        if self.lockout:
            self.log(f"[W][thermal]: {what} refused - thermal lockout (clears below 48 degC)")
        else:
            self.log(f"[W][thermal]: {what} refused - motor {self.reading:.1f} degC (no new moves at or above 55)")
        self.event("Thermal Alert", "refused")

    def cancel_pending(self):
        if self.pending:
            self.log(f"[I][thermal]: Pending scheduled {'open' if self.pending == 1 else 'close'} cancelled by a newer command")
            self.pending = 0

    def schedule(self, which):
        name = "open" if which == 1 else "close"
        self.log(f"[I][main]: BENCH: firing schedule_{name}")
        if self.blocked():
            self.refused(f"Scheduled {name}")
            self.pending, self.pending_t = which, self.t
            self.log(f"[W][thermal]: Scheduled {name} kept pending - it runs once the motor reads below 50 degC, "
                     "if that happens within 30 min")
        else:
            self.log(f"[I][main]: Schedule: {'opening' if which == 1 else 'closing'} cover")
            self.cancel_pending()
            self.move_to(1.0 if which == 1 else 0.0)

    def move_to(self, tgt):
        if abs(tgt - self.pos) < 1e-6:
            return
        self.target, self.stall_release = tgt, False
        self.state = "OPENING" if tgt > self.pos else "CLOSING"

    def halt(self):
        self.target, self.state, self.stall_release = None, "IDLE", False

    def trip(self, cause):
        if self.lockout:
            return
        self.lockout = True
        self.log(f"[W][thermal]: THERMAL LOCKOUT - motor {self.reading:.1f} degC (limit 60); clears below 48 degC")
        self.event("Thermal Alert", "sensor_lost" if cause == 2 else "lockout")
        if self.state in ("OPENING", "CLOSING") and not self.stall_release:
            self.halt()
        if self.heat_on:
            self.heater_stop(1)

    def heater_stop(self, code):
        if self.heat_on:
            self.heat_on, self.stop_code = False, code
            self.log(f"[W][bench]: heater OFF (code {code}) at {self.reading:.2f} degC")

    def on_reading(self, x):
        if x >= 60.0:
            self.warned = True
            self.trip(1)
        elif x < 48.0:
            self.warned = False
            if self.lockout:
                self.lockout = False
                self.log(f"[W][thermal]: Thermal lockout cleared - motor {x:.1f} degC")
                self.event("Thermal Alert", "cleared")
        elif x >= 50.0 and not self.warned and not self.lockout:
            self.warned = True
            self.log(f"[W][thermal]: Motor {x:.1f} degC - at or above the warning level (50)")
            self.event("Thermal Alert", "warning")
        if self.pending and x < 50.0 and not self.blocked():
            w, self.pending = self.pending, 0
            self.log(f"[W][thermal]: Motor {x:.1f} degC - running the pending scheduled {'open' if w == 1 else 'close'}")
            self.schedule(w)

    def tick(self, dt):
        self.t += dt
        moving = self.state in ("OPENING", "CLOSING")
        if moving:
            sp = SPEEDS[self.cal_speed if self.calibrated else "Fast"]
            step = sp / STROKE_STEPS * dt * (1 if self.state == "OPENING" else -1)
            self.pos += step
            if (step > 0 and self.pos >= self.target) or (step < 0 and self.pos <= self.target):
                self.pos = self.target
                self.halt()
        heat = (self.k_move * (self.current / 600.0) ** 2 if moving else 0.0) + \
               (K_HEAT * (self.ihold / 19.0) ** 2 if self.heat_on and not moving else 0.0)
        self.core += (heat - (self.core - AMBIENT) / TAU_S) * dt
        self.sens += (self.core - self.sens) * dt / LAG_S
        if self.t >= self.next_read:                                  # product sensor, 3 s
            self.next_read += 3.0
            self.reading = round(self.sens, 2)
            self.seen["Motor Temperature"] = self.t
            self.on_reading(self.reading)
        if self.cal_until and self.t >= self.cal_until:               # calibration result
            self.cal_until, self.calibrated, self.cal_speed = None, True, self.speed
            self.current = 420.0 if self.speed == "Slow" else 450.0
            self.vals = {"SGTHRS (stall threshold)": 27 if self.speed == "Slow" else 31,
                         "TCOOLTHRS": 480 if self.speed == "Slow" else 210, "Vibration Threshold": 0.19}
            self.cal_status = f"OK: irun=14 SGTHRS={self.vals['SGTHRS (stall threshold)']}"
            self.log("[I][main]: CAL: done")
        if self.pending and self.t - self.pending_t >= 1800:
            self.log("[W][thermal]: Pending scheduled move dropped - the motor did not read below 50 degC within 30 min")
            self.pending = 0
        if self.t >= self.next_bench:                                 # test package, 1.5 s
            self.next_bench += 1.5
            if moving and self.reading >= 62.0:
                self.backstop = True
                self.log(f"[E][bench]: BACKSTOP: {self.reading:.2f} degC with the motor moving - driver stopped")
                self.halt()
            if self.heat_on:
                code = (1 if self.lockout else 2 if self.reading >= 62.0 else
                        4 if self.t - self.heat_start >= 2700 else 6 if self.t - self.ka >= 30 else 0)
                if code:
                    self.heater_stop(code)
                elif self.t - self.step_t >= 180:
                    if self.reading < 60.0 and self.reading - self.step_c < 1.0 and self.ihold < 31:
                        self.ihold = min(31, self.ihold + 4)
                    self.step_t, self.step_c = self.t, self.reading
