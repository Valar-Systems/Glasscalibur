"""Dry-run unit for pc_run.py — BENCH ONLY (predictions: 2026-11-position-truth.md, Amendments 4 and 6).

A virtual-time model of the 2.3.0 position rules, close enough to exercise the script's logic:
the move marker, the saved position, the switches (S5 at 0, S4 at the learned stroke), the
unknown position (50 %, Fault line, Close until S5 / Open until S4, Set position via S5), the
calibrated speed (Speed Lock), Restart, the bench option that keeps S5 reading released, and a
power cut by hand: Daniel pulls the adapter a moment after the call, the motor runs on while the
adapter drains, the unit drops off the network, and boots a few seconds after he plugs it back in.

Faults (--sim-fault): no-drop (USB still powers the unit: it never goes off), stays-known (the
old position comes back after a cut), pc6-late (the first PC6 cut comes after S5 has released),
wrong-mac, speed-locked (calibrated at Slow), no-return (the unit doesn't come back after the
plug-in).

The open guard (--sim-guard, Amendment 6 note): ok (its heartbeat reads not connected 2 s after
the unit goes off, and connected again 3 s after the unit is back), late (it reads connected
through a cut and notices only at its first keepalive ping after the unit is back, pings every
20 s, then is back 3 s later), missing (no heartbeat), drop-in-recovery (like ok, then stale from
3 s into the first move after the first power-up), slow-start (no heartbeat until 10 s into the
run, then ok), drop-at-cut (stale from 5 s after the script's first STOP, and stays stale). A Restart closes the connection, so the guard notices it at once. Every move records whether the guard's connection at the send was made after
the unit's last power-up."""
import math
SPM = 3066.6667
SPEEDS = {"Slow": 1200, "Medium": 2600, "Fast": 5500}
UNKNOWN_LINE = "position unknown - close or open fully"
# A switch triggers at its point (S5 at 0, S4 at the stroke) and releases only after the carriage
# has moved this far back off it (hysteresis).
S5_RELEASE_MM, S4_RELEASE_MM = 0.5, 0.25
GUARD_NOTICE_S, GUARD_BACK_S, GUARD_PING_S, GUARD_STALE_AFTER_S = 2.0, 3.0, 20.0, 3.0


class SimDevice:
    def __init__(self, fault=None, cal="Slow", stroke_mm=99.3, guard="ok"):
        self.fault, self.t = fault, 0.0
        self.mac = "0a1b2c3d4e5f" if fault != "wrong-mac" else "0a1b2c3d4e60"
        self.cal = "Slow" if fault == "speed-locked" else cal
        self.stroke = int(stroke_mm * SPM)
        self.true = 0                      # where the carriage really is (steps from S5)
        self.count, self.target, self.dir = 0, 0, 0
        self.saved, self.marker, self.unknown = 0, False, False
        self.speed_sel, self.s5_dead_kept = self.cal, False
        self.powered, self.up, self.motor_on_until = True, True, None
        self.cut_at = self.plug_at = self.boot_at = None
        self.pc6_cuts, self.pending = 0, None
        self.logs, self.state = [], "IDLE"
        self.calls = []                    # every command sent, for the checks
        self.s5_on, self.s4_on = True, False
        self.cache = {}
        # the open guard
        self.guard = guard
        self.g_conn, self.g_since, self.g_lost_at, self.g_back_at, self.g_stale_from = True, 0.0, None, None, None
        self.booted_at, self.off_by_cut, self.cut_boots = 0.0, False, 0
        self.moves, self.timed = [], []    # (t, cmd, guard fresh, cut power-ups so far); (t, what, ...)
        self.sampler, self.sample_next = None, 0.0
        if guard == "slow-start":                  # no heartbeat until 10 s into the run, then ok
            self.g_conn, self.g_back_at = False, 10.0

    # --- interface used by pc_run.py
    def now(self):
        return self.t

    async def start(self):
        pass

    async def close(self):
        pass

    async def sleep(self, s):
        end = self.t + s
        while self.t < end - 1e-9:
            self._tick(min(0.05, end - self.t))
        self.t = max(self.t, end)          # end exactly on time: a caller that sleeps the rest would wait forever

    def get(self, name):
        if self.up:
            self.cache = self._snapshot()
        return self.cache.get(name)

    def _snapshot(self):
        s5, s4 = self._s5(), self._s4()
        return {
            "Glasscalibur": self._cover(s5, s4), "State": self.state,
            "Glasscalibur.op": {"OPENING": 1, "CLOSING": 2}.get(self.state, 0),
            "Fault": UNKNOWN_LINE if self.unknown else "None",
            "Close Limit Switch": s5, "Open Limit Switch": s4,
            "Open stroke": self.stroke / SPM, "Speed": self.speed_sel, "Speed Lock": self._lock(),
            "BENCH: close switch (S5) dead, kept across restarts": self.s5_dead_kept,
        }

    async def reachable(self):
        return self.up

    async def reconnect(self, timeout=120.0):
        end = self.t + timeout
        while self.t < end:
            if self.up:
                await self.sleep(1.0)
                return True
            await self.sleep(1.0)
        return False

    def sample_every(self, fn, period=0.2):
        self.sampler, self.sample_period, self.sample_next = fn, period, self.t

    def hear(self, kind, text, say):
        """The bench hears a prompt (pc_run's Prompter): Daniel pulls the adapter a moment after
        the call and plugs it back in when told."""
        self.timed.append((self.t, "prompt", kind, text, say))
        if text.startswith("PULL THE 24 V ADAPTER"):
            self.calls.append(("prompt", "pull"))
            if self.fault != "no-drop":
                late = self.fault == "pc6-late" and self.pc6_next and self.pc6_cuts == 0
                self.cut_at = self.t + (1.8 if late else 0.5)
                if self.pc6_next:
                    self.pc6_cuts += 1
        elif text.startswith("PLUG THE 24 V ADAPTER"):
            self.calls.append(("prompt", "plug"))
            if self.fault != "no-return":
                self.plug_at = self.t + 1.0

    pc6_next = False                       # set by the script around a PC6 cut (sim only)

    def guard_check(self):
        """The open guard's heartbeat, as bench_common.guard_ok() would read it: (ok, reason)."""
        if self.guard == "missing":
            return False, "no heartbeat from the open guard (is open_guard.py running?)"
        if self.g_stale_from is not None and self.t >= self.g_stale_from:
            return False, "the open guard's heartbeat is stale"
        if not self.g_conn:
            return False, "the open guard has lost its connection to the unit"
        return True, "open guard connected and watching"

    def _guard_unit_off(self, closed):
        """The unit went off: a Restart closes the connection (noticed at once); after a power cut
        the guard notices from its keepalive (ok: 2 s; late: at its first ping after the unit is back)."""
        if closed:
            if self.g_conn:
                self.g_conn = False
                self.timed.append((self.t, "guard", "lost"))
        elif self.guard != "late":
            self.g_lost_at = self.t + GUARD_NOTICE_S

    def _guard_tick(self):
        if self.g_lost_at is not None and self.t >= self.g_lost_at:
            self.g_lost_at = None
            if self.g_conn:
                self.g_conn = False
                self.timed.append((self.t, "guard", "lost"))
        if not self.g_conn and self.up and self.g_back_at is None:
            self.g_back_at = self.t + GUARD_BACK_S
        if self.g_back_at is not None and self.t >= self.g_back_at:
            self.g_back_at = None
            if self.up:
                self.g_conn, self.g_since = True, self.t
                self.timed.append((self.t, "guard", "back"))

    async def cover(self, cmd, pos=None):
        self.calls.append(("cover", cmd, pos))
        if cmd == "stop":
            self.timed.append((self.t, "stop"))
            if self.guard == "drop-at-cut" and self.g_stale_from is None:
                self.g_stale_from = self.t + 5.0
        else:
            fresh = self.guard_check()[0] and self.g_since >= self.booted_at
            self.moves.append((self.t, cmd, fresh, self.cut_boots))
            if self.guard == "drop-in-recovery" and self.cut_boots >= 1 and self.g_stale_from is None:
                self.g_stale_from = self.t + GUARD_STALE_AFTER_S
        if not self.powered:
            return                         # the chip is off: the command is lost
        if cmd == "stop":
            self._halt()
        elif cmd == "open":
            self._open()
        elif cmd == "close":
            self._close()
        elif cmd == "set":
            self._set(pos)

    async def press(self, name):
        self.calls.append(("press", name))
        if name == "Restart" and self.up:
            self._halt()                   # on_shutdown: halt, then save
            self.up, self.boot_at = False, self.t + 6.0
            self._guard_unit_off(closed=True)

    async def switch(self, name, on):
        self.calls.append(("switch", name, on))
        if name.startswith("BENCH: close switch (S5) dead"):
            was = self._s5()
            self.s5_dead_kept = bool(on)
            if not was and self._s5():
                self._on_s5()

    async def select(self, name, option):
        self.calls.append(("select", name, option))
        if name == "Speed":
            self.speed_sel = option

    # --- model
    def _lock(self):
        if self.cal is None:
            return "Speed locked to Fast until calibration has run"
        if self.speed_sel != self.cal:
            return f"Speed change needs recalibration - running at {self.cal} ({SPEEDS[self.cal]} steps/s)"
        return "Not locked"

    def _speed(self):
        return SPEEDS["Fast" if self.cal is None else self.cal]

    def _switches(self):
        if self.s5_on and self.true > S5_RELEASE_MM * SPM:
            self.s5_on = False
        elif not self.s5_on and self.true <= 0:
            self.s5_on = True
        if self.s4_on and self.true < self.stroke - S4_RELEASE_MM * SPM:
            self.s4_on = False
        elif not self.s4_on and self.true >= self.stroke:
            self.s4_on = True

    def _s5(self):
        return self.s5_on and not self.s5_dead_kept

    def _s4(self):
        return self.s4_on

    def _cover(self, s5, s4):
        if self.unknown:
            return 0.5
        if s5:
            return 0.0
        if s4:
            return 1.0
        return min(0.99, max(0.01, self.count / self.stroke))

    def log(self, line):
        self.logs.append((self.t, line))

    def _commit(self):
        self.saved, self.marker = self.count, False

    def _halt(self):
        self.dir, self.target, self.state = 0, self.count, "IDLE"
        self._commit()

    def _begin(self, target, state):
        self.marker = True                 # move_begin: marker saved before the move
        self.target, self.state = target, state
        self.dir = 1 if target > self.count else -1

    def _open(self):
        if self.unknown and self._s4():
            self.count, self.unknown = self.stroke, False
            self.log("Open with the position unknown: S4 already pressed - fully open, no move")
            self._halt()
            return
        if self.unknown:
            self.log("Position unknown: opening until S4 (at most the stroke + 2.0 mm)")
            self._begin(self.count + self.stroke + int(2.0 * SPM), "OPENING")
        else:
            self._begin(self.stroke + int(0.5 * SPM), "OPENING")

    def _close(self):
        self.pending = None
        if self.unknown and self._s5():
            self.count, self.unknown = 0, False
            self.log("Close with the position unknown: S5 already pressed - closed, no move")
            self._halt()
            return
        if self.unknown:
            self.log(f"Position unknown: closing until S5 (at most the stroke + 2.0 mm) from {self.count} steps")
            self._begin(self.count - self.stroke - int(2.0 * SPM), "CLOSING")
        else:
            self._begin(-int(0.6 * SPM), "CLOSING")

    def _set(self, pos):
        if pos >= 1.0:
            return self._open()
        if pos <= 0.0:
            return self._close()
        if self.unknown:
            self.log(f"Position unknown: closing to S5 first, then to {pos * 100:.0f} %")
            self._close()
            self.pending = pos
            return
        t = int(pos * self.stroke)
        self._begin(t, "OPENING" if t > self.count else "CLOSING")

    def _on_s5(self):
        if self.state == "OPENING":
            return
        self.log(f"S5 triggered at {self.count} steps ({self.count / SPM:.2f} mm)")
        self.count, self.unknown = 0, False
        self._halt()
        if self.pending is not None:
            p, self.pending = self.pending, None
            self.log(f"Position known at S5 - moving to the requested {p * 100:.0f} %")
            self._set(p)

    def _on_s4(self):
        if self.state != "OPENING":
            return
        self.log(f"S4 triggered at {self.count} steps ({self.count / SPM:.2f} mm)")
        self.count, self.unknown = self.stroke, False
        self._halt()

    def _boot(self):
        self.booted_at = self.t
        if self.off_by_cut:
            self.off_by_cut, self.cut_boots = False, self.cut_boots + 1
            if self.guard == "late" and self.g_conn:    # noticed at its first ping after the unit is back
                self.g_lost_at = math.ceil(self.t / GUARD_PING_S) * GUARD_PING_S
        self.count, self.dir, self.state, self.pending = self.saved, 0, "IDLE", None
        if self.marker and self.fault != "stays-known":
            self.unknown = True
        if not self._s5() and self.saved <= 0 and self.fault != "stays-known":
            self.unknown = True
        if not self._s4() and self.saved >= self.stroke and self.fault != "stays-known":
            self.unknown = True
        if self._s5():
            self.count, self.unknown = 0, False
        elif self._s4():
            self.count, self.unknown = self.stroke, False
        self.up, self.boot_at = True, None

    def _tick(self, dt):
        self.t += dt
        if self.up:
            self.cache = self._snapshot()
        if self.cut_at is not None and self.t >= self.cut_at:
            self.cut_at, self.powered = None, False
            self.motor_on_until = self.t + 0.2          # the adapter drains
            self.drop_at = self.t + 0.3
        if not self.powered and getattr(self, "drop_at", None) is not None and self.t >= self.drop_at:
            self.up, self.drop_at, self.off_by_cut = False, None, True
            self._guard_unit_off(closed=False)
        if self.plug_at is not None and self.t >= self.plug_at:
            self.plug_at, self.powered = None, True
            self.boot_at = self.t + 6.0
            self.dir = 0
        if self.boot_at is not None and self.t >= self.boot_at:
            self._boot()
        self._guard_tick()
        if self.sampler and self.t >= self.sample_next:
            self.sample_next = self.t + self.sample_period
            self.sampler()
        running = self.dir != 0 and (self.powered or (self.motor_on_until and self.t < self.motor_on_until))
        if not running:
            if not self.powered:
                self.dir = 0
            return
        step = int(self._speed() * dt) * self.dir
        self.true = max(-int(0.9 * SPM), min(self.stroke + int(2.2 * SPM), self.true + step))
        self._switches()
        if not self.powered:
            return                                     # the chip is off: nothing counts or reacts
        self.count += step
        if self.dir < 0 and self._s5():
            self._on_s5()
        elif self.dir > 0 and self._s4():
            self._on_s4()
        elif (self.dir > 0 and self.count >= self.target) or (self.dir < 0 and self.count <= self.target):
            if self.state == "CLOSING" and not self._s5():
                self.unknown = True
            self._halt()
