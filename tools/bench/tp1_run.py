#!/usr/bin/env python3
"""TP-1, automatic — BENCH ONLY (tools/regression-gate/predictions/2026-11-tp1-automatic.md).

Runs TP-1 end to end against the test build (tools/bench/glasscalibur-tp1.yaml, Firmware
Version "dev-tp1") over the native API (Home Assistant's path) and REST (the web UI's path),
keeps the full device log and writes a PASS/FAIL report. Heat comes from full strokes at Slow
and 600 mA; the test package's hold-current heater is the fallback, used only if Slow strokes
peak below 60 °C. The script changes Speed, Motor Current and the calibration only as TP-1
needs, and puts them back at the end.

    python tools/bench/tp1_run.py --host <unit address> [--out DIR]
    python tools/bench/tp1_run.py --sim [--sim-fault NAME]      # dry run against tp1_sim.py

The unit address is given on the command line only; it is not written to the report.
Thresholds: warning 50, gate 55, lockout 60, clear below 48 °C.
"""
import argparse, asyncio, datetime, json, pathlib, re, sys, time, urllib.parse, urllib.request

WARN, GATE, LOCK, CLEAR = 50.0, 55.0, 60.0, 48.0
BACKSTOP_C, STALE_S = 62.0, 10.0
PENDING_LIMIT_S = 30 * 60
ANSI = re.compile(r"\x1b\[[0-9;]*m")

E_TEMP, E_STATE, E_LOCKOUT = "Motor Temperature", "State", "Thermal Lockout"
E_ALERT, E_OBSTRUCTION, E_COVER = "Thermal Alert", "Obstruction", "Glasscalibur"
E_SPEED, E_LOCKTEXT, E_CURRENT = "Speed", "Speed Lock", "Motor Current"
E_CALSTAT, E_CALIBRATED, E_FW = "Calibration Status", "StallGuard calibrated", "Firmware Version"
E_HEATER, E_HEATSTAT, E_KEEP = "BENCH heater", "BENCH heater status", "BENCH heater keepalive"
SNAPSHOT = [E_SPEED, E_LOCKTEXT, E_CURRENT, E_CALSTAT, E_CALIBRATED, "SGTHRS (stall threshold)",
            "TCOOLTHRS", "Vibration Threshold", "StallGuard Enabled", "Vibration Stall Detection",
            "Child Lock"]


# ----------------------------------------------------------------------------- real unit
class RealDevice:
    """The unit over aioesphomeapi (client name contains "tp1": the test package's heater
    turns itself off if this connection closes) and REST."""

    def __init__(self, host):
        self.host, self.t0 = host, time.monotonic()
        self.states, self.events, self.logs, self.keys, self.kinds = {}, [], [], {}, {}
        self.seen = {}

    def now(self):
        return time.monotonic() - self.t0

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def start(self):
        from aioesphomeapi import APIClient, LogLevel
        self.api = APIClient(self.host, 6053, None, client_info="glasscalibur-tp1")
        await self.api.connect(login=True)
        infos, _ = await self.api.list_entities_services()
        for i in infos:
            self.keys[i.name], self.kinds[i.key] = i.key, (type(i).__name__, i.name)
        self.api.subscribe_states(self._on_state)
        self.api.subscribe_logs(self._on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)

    def _on_state(self, st):
        kind, name = self.kinds.get(st.key, ("?", "?"))
        self.seen[name] = self.now()
        if kind == "EventInfo":
            self.events.append((self.now(), name, st.event_type, self.get(E_TEMP)))
            return
        if kind == "CoverInfo":
            self.states[name] = st.position
            return
        self.states[name] = getattr(st, "state", None)

    def _on_log(self, msg):
        line = ANSI.sub("", msg.message.decode("utf-8", "replace") if isinstance(msg.message, bytes) else msg.message)
        self.logs.append((self.now(), line))

    def get(self, name):
        return self.states.get(name)

    def last_seen(self, name):
        return self.seen.get(name, -1e9)

    async def close(self):
        await self.api.disconnect()

    def _rest(self, path):
        req = urllib.request.Request(f"http://{self.host}{path}", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status

    async def cover(self, path, cmd, pos=None):
        if path == "api":
            key = self.keys[E_COVER]
            if cmd == "stop":
                self.api.cover_command(key, stop=True)
            else:
                self.api.cover_command(key, position={"open": 1.0, "close": 0.0}.get(cmd, pos))
            return 200
        q = f"/cover/{E_COVER}/" + (f"set?position={pos:.3f}" if cmd == "set" else cmd)
        return await asyncio.get_running_loop().run_in_executor(None, self._rest, q)

    async def press(self, name):
        self.api.button_command(self.keys[name])

    async def switch(self, name, on):
        self.api.switch_command(self.keys[name], on)

    async def select(self, name, option):
        self.api.select_command(self.keys[name], option)

    async def number(self, name, value):
        self.api.number_command(self.keys[name], value)


# ----------------------------------------------------------------------------- the run
class Run:
    def __init__(self, dev, out):
        self.dev, self.out, self.rows, self.moves = dev, out, [], []
        self.heater_used = False
        self.moves_to = {GATE: None, LOCK: None}
        self.snapshot, self.after = {}, {}

    # --- helpers
    def T(self):
        v = self.dev.get(E_TEMP)
        return None if v is None or v != v else float(v)

    def state(self):
        return self.dev.get(E_STATE)

    def rec(self, step, verdict, detail=""):
        t = self.T()
        row = {"t_s": round(self.dev.now(), 1), "step": step, "verdict": verdict, "detail": detail,
               "reading_c": None if t is None else round(t, 2)}
        self.rows.append(row)
        print(f"[{row['t_s']:8.1f}s] {verdict:5} {step}" + (f" — {detail}" if detail else "")
              + (f" ({row['reading_c']} °C)" if t is not None else ""), flush=True)
        return verdict == "PASS"

    def check(self, step, ok, detail=""):
        return self.rec(step, "PASS" if ok else "FAIL", detail)

    def mark(self):
        return len(self.dev.logs), len(self.dev.events)

    def logged(self, m, text):
        return any(text in line for _, line in self.dev.logs[m[0]:])

    def events_of(self, m, etype, name=E_ALERT):
        return [e for e in self.dev.events[m[1]:] if e[1] == name and e[2] == etype]

    async def wait(self, cond, timeout, poll=0.5):
        end = self.dev.now() + timeout
        while self.dev.now() < end:
            if cond():
                return True
            await self.dev.sleep(poll)
        return cond()

    async def stop(self, path="api"):
        await self.dev.cover(path, "stop")
        await self.wait(lambda: self.state() == "IDLE", 5)

    # --- backstops while the motor moves (also checked by the firmware at 62 °C)
    async def watch_move(self, max_s):
        """Wait for the move to end. STOP at 62 °C or after 10 s with no reading (FAIL).
        Returns (ended, peak, t_idle): t_idle = when State was first seen IDLE."""
        peak = self.T() or 0.0
        end = self.dev.now() + max_s
        while self.dev.now() < end:
            t = self.T()
            if t is not None:
                peak = max(peak, t)
            if t is not None and t >= BACKSTOP_C:
                await self.stop()
                self.rec("script backstop: 62 °C while moving", "FAIL", "STOP sent")
                return False, peak, None
            if self.dev.now() - self.dev.last_seen(E_TEMP) > STALE_S:
                await self.stop()
                self.rec("script backstop: no reading for 10 s while moving", "FAIL", "STOP sent")
                return False, peak, None
            if self.state() == "IDLE":
                return True, peak, self.dev.now()
            await self.dev.sleep(0.25)
        await self.stop()
        self.rec("move did not end in time", "FAIL", f"{max_s} s")
        return False, peak, None

    # --- command probes
    async def probe_accepted(self, path, cmd, pos=None):
        m = self.mark()
        await self.dev.cover(path, cmd, pos)
        moving = await self.wait(lambda: self.state() in ("OPENING", "CLOSING"), 3)
        await self.dev.sleep(1.0)
        await self.stop(path)
        return self.check(f"{path} {cmd} accepted", moving and not self.logged(m, "refused"))

    async def probe_refused(self, path, cmd, pos, why):
        m = self.mark()
        pos0 = self.dev.get(E_COVER)
        await self.dev.cover(path, cmd, pos)
        got = await self.wait(lambda: self.logged(m, f"refused - {why}") and self.events_of(m, "refused")
                              or self.state() in ("OPENING", "CLOSING"), 3)
        await self.dev.sleep(1.0)
        still = self.state() == "IDLE" and self.dev.get(E_COVER) == pos0
        if self.state() in ("OPENING", "CLOSING"):    # wrongly accepted while hot: stop it now
            await self.stop()
        got = got and self.logged(m, f"refused - {why}") and bool(self.events_of(m, "refused"))
        return self.check(f"{path} {cmd} refused ({why})", got and still,
                          "log + Thermal Alert refused, no motion" if got and still else
                          f"log/event={bool(got)}, idle-and-still={still}")

    def target_away(self):
        p = self.dev.get(E_COVER) or 0.0
        return round(min(0.9, p + 0.2) if p < 0.5 else max(0.1, p - 0.2), 2)

    # --- settings
    def snap(self):
        return {n: self.dev.get(n) for n in SNAPSHOT}

    async def calibrate(self, why):
        m = self.mark()
        await self.dev.press("Auto-Calibrate")
        ok = await self.wait(lambda: str(self.dev.get(E_CALSTAT) or "").startswith(("OK", "FAILED", "Aborted"))
                             and self.logged(m, "CAL:"), 30 * 60, poll=2)
        stat = str(self.dev.get(E_CALSTAT))
        return self.check(f"Auto-Calibrate ({why})", ok and stat.startswith("OK"), stat)

    def rise_per_stroke(self):
        """Measured rise (peak after the stop minus start) per full stroke, from the moves
        so far (8 °C before any are measured)."""
        r = sorted((mv["peak_after_stop_c"] - mv["start_c"]) / mv["frac"] for mv in self.moves
                   if mv["frac"] >= 0.1 and mv["start_c"] is not None and not mv["lockout_during_move"])
        return max(1.0, r[len(r) // 2]) if r else 8.0

    # --- heat by strokes; returns when the reading reaches `goal` or the lockout latches.
    # From `partial_from` on, each move is sized from the measured rise per stroke to land
    # near AIM (inside 55-60), so the motor stands still in the gate window.
    AIM = 57.5

    async def heat_by_moves(self, goal, partial_from):
        tries = 0
        while True:
            t = self.T()
            if self.dev.get(E_LOCKOUT) or (t is not None and t >= goal):
                return True
            if t is not None and t >= GATE and goal >= LOCK:
                # Phase B: a stroke ended between 55 and 60. Wait to just below 55, then one
                # more full stroke from there; if a stroke started near 55 already peaked
                # below 60, Slow strokes can't reach the lockout: heater fallback.
                if any(mv["start_c"] >= 53.0 and mv["frac"] >= 0.9 and mv["peak_after_stop_c"] < LOCK
                       for mv in self.moves[-1:]):
                    return False
                if not await self.wait(lambda: (self.T() or 99) < 54.8 or self.dev.get(E_LOCKOUT), 30 * 60, poll=1):
                    return False
                continue
            if t is None or t >= GATE:            # never start a stroke at 55 °C or above
                return False
            tries += 1
            if tries > 40:
                self.rec(f"heating toward {goal} °C: no progress in 40 moves", "FAIL")
                return False
            pos = self.dev.get(E_COVER) or 0.0
            if t >= partial_from:
                f = min(1.0, max(0.1, (self.AIM - t) / self.rise_per_stroke()))
                if pos + f <= 1.0:
                    tgt = pos + f
                elif pos - f >= 0.0:
                    tgt = pos - f
                else:
                    tgt = 1.0 if pos < 0.5 else 0.0
                cmd, tgt = "set", round(tgt, 3)
            else:
                cmd, tgt = ("close", 0.0) if pos > 0.5 else ("open", 1.0)
            frac = abs(tgt - pos)
            start = t
            m = self.mark()
            await self.dev.cover("api", cmd, tgt if cmd == "set" else None)
            await self.wait(lambda: self.state() in ("OPENING", "CLOSING"), 3)
            m_lockout_before = self.dev.get(E_LOCKOUT)
            ok, peak, t_idle = await self.watch_move(400)
            lk = self.events_of(m, "lockout")
            # The lockout latched during this move if its event came before the move was seen
            # to end (the firmware stops the motor in the same step, so State reads IDLE at
            # once; the gap is the stop time as seen from here, at most one State poll).
            lock_to_idle = (round(t_idle - lk[0][0], 2) if lk and t_idle is not None and lk[0][0] <= t_idle
                            and not m_lockout_before else None)
            end = self.T()
            after_peak, flat, last = end or 0.0, 0, end or 0.0
            for _ in range(120):                    # peak after the stop: until 3 readings don't rise (max 60 s)
                if self.dev.get(E_LOCKOUT):
                    break
                await self.dev.sleep(0.5)
                now_t = self.T() or 0.0
                if now_t != last:
                    flat = flat + 1 if now_t <= after_peak else 0
                    last = now_t
                after_peak = max(after_peak, now_t)
                if flat >= 3:
                    break
            n = len(self.moves) + 1
            mv = {"n": n, "kind": cmd if cmd != "set" else f"set {tgt}", "frac": round(frac, 3),
                  "start_c": start, "end_c": end,
                  "peak_after_stop_c": round(max(after_peak, peak), 2),
                  "obstruction": bool(self.events_of(m, "obstructed", E_OBSTRUCTION)),
                  "lockout_during_move": lock_to_idle is not None and not m_lockout_before,
                  "lockout_to_idle_s": lock_to_idle}
            self.moves.append(mv)
            for thr in (GATE, LOCK):
                if self.moves_to[thr] is None and mv["peak_after_stop_c"] >= thr:
                    self.moves_to[thr] = n
            print(f"          move {n}: {mv['kind']}, {start:.2f} -> {end} °C, peak {mv['peak_after_stop_c']} °C"
                  + (", OBSTRUCTION" if mv["obstruction"] else ""), flush=True)
            if self.events_of(m, "lockout"):
                return True

    async def heat_with_heater(self, goal):
        """Fallback: the test package's hold-current heater, kept alive every 5 s."""
        self.heater_used = True
        await self.dev.switch(E_HEATER, True)
        await self.dev.sleep(2)
        end, last_ka = self.dev.now() + 46 * 60, -1e9
        while self.dev.now() < end and self.dev.get(E_HEATER):
            if self.dev.get(E_LOCKOUT) or (self.T() or 0) >= goal:
                break
            if self.dev.now() - last_ka >= 5:
                await self.dev.press(E_KEEP)
                last_ka = self.dev.now()
            await self.dev.sleep(1)
        if self.dev.get(E_HEATER) and not self.dev.get(E_LOCKOUT):
            await self.dev.switch(E_HEATER, False)
        self.rec("heater stopped", "INFO", str(self.dev.get(E_HEATSTAT)))
        return bool(self.dev.get(E_LOCKOUT)) or (self.T() or 0) >= goal

    # --- stages
    async def preflight(self):
        fw = self.dev.get(E_FW)
        if not self.check("test build running (Firmware Version dev-tp1)", fw == "dev-tp1", str(fw)):
            return False
        if self.dev.get(E_LOCKOUT):
            self.rec("Thermal Lockout already on at the start", "FAIL")
            return False
        self.snapshot = self.snap()
        self.rec("settings saved", "INFO", json.dumps(self.snapshot))
        if not await self.wait(lambda: (self.T() or 99) < CLEAR, 60 * 60, poll=2):
            self.rec("motor did not cool below 48 °C", "FAIL")
            return False
        return True

    async def setup_slow(self):
        s = self.snapshot
        at_slow = s[E_SPEED] == "Slow" and s[E_LOCKTEXT] == "Not locked" and s[E_CALIBRATED]
        if not at_slow:
            await self.dev.select(E_SPEED, "Slow")
            await self.dev.sleep(2)
            if not await self.calibrate("at Slow, for TP-1"):
                return False
        else:
            self.rec("already calibrated at Slow", "INFO")
        await self.dev.number(E_CURRENT, 600)
        await self.dev.sleep(6)
        return self.check("Motor Current 600 mA", abs((self.dev.get(E_CURRENT) or 0) - 600) <= 20,
                          str(self.dev.get(E_CURRENT)))

    async def s0(self):
        for path in ("api", "rest"):
            await self.probe_accepted(path, "open")
            await self.probe_accepted(path, "close")
            await self.probe_accepted(path, "set", self.target_away())
        # a move running when the lockout trips (injection; real heat may also show it)
        m = self.mark()
        await self.dev.cover("api", "open" if (self.dev.get(E_COVER) or 0) < 0.5 else "close")
        await self.wait(lambda: self.state() in ("OPENING", "CLOSING"), 3)
        await self.dev.sleep(1)
        await self.dev.press("BENCH: trip thermal lockout")
        stopped = await self.wait(lambda: self.state() == "IDLE", 1.5, poll=0.1)
        self.check("S0 injection: a move running when the lockout trips stops within 1.5 s",
                   stopped and bool(self.events_of(m, "lockout")) and bool(self.dev.get(E_LOCKOUT)))
        self.check("S0 injection: the lockout clears on the next reading below 48 °C",
                   await self.wait(lambda: self.events_of(m, "cleared"), 10))
        # a stall back-off running when the lockout trips (injection)
        m = self.mark()
        await self.dev.cover("api", "open" if (self.dev.get(E_COVER) or 0) < 0.5 else "close")
        await self.wait(lambda: self.state() in ("OPENING", "CLOSING"), 3)
        await self.dev.sleep(1.5)
        await self.dev.press("BENCH: simulate stall")
        await self.dev.sleep(0.5)
        await self.dev.press("BENCH: trip thermal lockout")
        kept = not await self.wait(lambda: self.state() == "IDLE", 1.0, poll=0.1)
        ended = await self.wait(lambda: self.state() == "IDLE", 45)
        self.check("S0 injection: a stall back-off running when the lockout trips finishes",
                   kept and ended and bool(self.events_of(m, "obstructed", E_OBSTRUCTION)),
                   f"still moving 1 s after the trip={kept}, ended={ended}")
        await self.wait(lambda: self.events_of(m, "cleared"), 10)

    async def gate_checks(self):
        for path in ("api", "rest"):
            for cmd in ("open", "close", "set"):
                await self.probe_refused(path, cmd, self.target_away() if cmd == "set" else None, "motor")
        m = self.mark()
        await self.dev.press("BENCH: fire scheduled close")
        await self.dev.sleep(1.5)
        await self.dev.press("BENCH: fire scheduled open")
        await self.dev.sleep(1.5)
        self.check("scheduled close then open: refused, the open replaces it (latest wins)",
                   self.logged(m, "Scheduled close kept pending") and self.logged(m, "Scheduled open kept pending")
                   and len(self.events_of(m, "refused")) >= 2)
        m = self.mark()
        await self.dev.cover("api", "close")
        await self.dev.sleep(2)
        return self.check("a refused Close cancels the pending scheduled open",
                          self.logged(m, "refused") and self.logged(m, "Pending scheduled open cancelled"))

    async def phase_a_cooldown(self):
        m = self.mark()
        idle = True
        ok = await self.wait(lambda: (self.T() or 99) < 49.0, 45 * 60, poll=1)
        end = self.dev.now() + 60
        while self.dev.now() < end:
            idle = idle and self.state() == "IDLE"
            await self.dev.sleep(0.5)
        self.check("after the cancel, cooling below 50 °C: nothing moves",
                   ok and idle and not self.logged(m, "running the pending"))

    async def lockout_checks(self, m_lock):
        ev = self.events_of(m_lock, "lockout")
        t_lock = ev[0][3] if ev else None
        self.check("lockout at the first reading >= 60 (60.0-62.0)", t_lock is not None and LOCK <= t_lock <= 62.0,
                   f"reading {t_lock}")
        self.check("Thermal Lockout on", bool(self.dev.get(E_LOCKOUT)))
        if self.heater_used:
            hs = str(self.dev.get(E_HEATSTAT))
            self.check("the heater stopped on the lockout, not the 62 °C backstop", "lockout" in hs, hs)
        for path in ("api", "rest"):
            for cmd in ("open", "close", "set"):
                await self.probe_refused(path, cmd, self.target_away() if cmd == "set" else None, "thermal lockout")
        m = self.mark()
        await self.dev.press("Auto-Calibrate")
        self.check("Auto-Calibrate refused during the lockout",
                   await self.wait(lambda: self.logged(m, "CAL: refused - thermal lockout"), 3))
        for path in ("api", "rest"):
            m = self.mark()
            await self.dev.cover(path, "stop")
            self.check(f"{path} STOP works during the lockout",
                       await self.wait(lambda: self.logged(m, "COVER stop_action"), 3))
        if self.snapshot.get("Child Lock"):
            self.rec("Button 1 during the lockout", "NT", "Child Lock is on; left as it is")
        else:
            m = self.mark()
            print("\a\n>>> Daniel: please press Button 1 once now (60 s). <<<\n", flush=True)
            got = await self.wait(lambda: self.logged(m, "Close refused - thermal lockout"), 60)
            if got:
                self.rec("Button 1 during the lockout: Close refused", "PASS")
            else:
                self.rec("Button 1 during the lockout", "NT", "no press within 60 s")

    async def cooldown_pending(self, m_lock):
        await self.wait(lambda: (self.T() or 99) < 51.0, 60 * 60, poll=1)
        m = self.mark()
        fired = self.dev.now()
        await self.dev.press("BENCH: fire scheduled open")
        await self.dev.sleep(2)
        self.check("during cool-down (lockout on): scheduled open refused and kept pending",
                   self.logged(m, "Scheduled open kept pending") and bool(self.events_of(m, "refused")))
        cleared = await self.wait(lambda: self.events_of(m, "cleared"), PENDING_LIMIT_S, poll=1)
        ev = self.events_of(m, "cleared")
        t_clear = ev[0][3] if ev else None
        self.check("cleared at the first reading below 48 °C", cleared and t_clear is not None and t_clear < CLEAR,
                   f"reading {t_clear}, {self.dev.now() - fired:.0f} s after firing")
        self.check("Thermal Lockout off after the clear", not self.dev.get(E_LOCKOUT))
        ran = await self.wait(lambda: self.logged(m, "running the pending scheduled open")
                              and self.state() in ("OPENING", "CLOSING"), 6)
        self.check("the pending scheduled open runs once the lockout clears", ran)
        await self.stop()

    async def restore(self):
        await self.wait(lambda: (self.T() or 99) < WARN, 60 * 60, poll=2)
        s = self.snapshot
        changed_speed = self.dev.get(E_SPEED) != s[E_SPEED]
        if changed_speed:
            await self.dev.select(E_SPEED, s[E_SPEED])
            await self.dev.sleep(2)
            await self.calibrate(f"restore at {s[E_SPEED]}")
        if s[E_CURRENT] is not None:
            await self.dev.number(E_CURRENT, s[E_CURRENT])
            await self.dev.sleep(6)
        self.after = self.snap()
        same = {k: self.after.get(k) == v for k, v in s.items()}
        self.rec("settings put back", "INFO", json.dumps({"before": s, "after": self.after}))
        self.check("Speed and Motor Current as before", same[E_SPEED] and
                   abs((self.after[E_CURRENT] or 0) - (s[E_CURRENT] or 0)) <= 20)
        if not s[E_CALIBRATED]:
            self.rec("calibration flag", "INFO", "the unit was not calibrated before; it stays calibrated")

    async def run(self):
        if not await self.preflight():
            return
        if not await self.setup_slow():
            return
        await self.s0()
        warn_m = self.mark()
        # Phase A: to 55-60 at standstill, no lockout
        await self.heat_by_moves(GATE, partial_from=WARN)
        w = self.events_of(warn_m, "warning")
        self.check("one warning event at the first reading >= 50 (50.0-52.0)",
                   len(w) == 1 and WARN <= w[0][3] <= 52.0, f"{len(w)} event(s), reading {w[0][3] if w else None}")
        a_done = False
        if not self.dev.get(E_LOCKOUT) and GATE <= (self.T() or 0) < LOCK:
            await self.gate_checks()
            await self.phase_a_cooldown()
            a_done = True
        elif self.dev.get(E_LOCKOUT):
            self.rec("phase A overshot past 60 °C: lockout first, phase A after the clear", "INFO")
        # Phase B: full strokes to the lockout
        m_lock = self.mark()
        if not self.dev.get(E_LOCKOUT):
            reached = await self.heat_by_moves(LOCK, partial_from=99.0)
            if not self.dev.get(E_LOCKOUT):
                self.rec("Slow strokes peaked below 60 °C: hold-current heater (fallback)", "INFO")
                await self.heat_with_heater(LOCK)
        if not await self.wait(lambda: self.dev.get(E_LOCKOUT), 30):
            self.rec("lockout not reached", "FAIL")
            return
        mv_lock = [mv for mv in self.moves if mv.get("lockout_during_move")]
        if mv_lock:
            s = mv_lock[0]["lockout_to_idle_s"]
            self.check("a move still running when the lockout trips stops within 1 s (real heat)",
                       s is not None and s <= 1.0, f"move {mv_lock[0]['n']}, IDLE {s} s after the lockout")
        else:
            self.rec("a move still running when the lockout trips (real heat)", "INFO",
                     "not seen: covered by the S0 injection")
        self.check("no second warning before the clear", len(self.events_of(warn_m, "warning")) <= 1)
        await self.lockout_checks(m_lock)
        await self.cooldown_pending(m_lock)
        if not a_done:
            await self.heat_by_moves(GATE, partial_from=WARN)
            if not self.dev.get(E_LOCKOUT) and GATE <= (self.T() or 0) < LOCK:
                await self.gate_checks()
                await self.phase_a_cooldown()
            else:
                self.rec("phase A (second cycle)", "NT", "could not stop between 55 and 60 °C")
        for path in ("api", "rest"):
            await self.probe_accepted(path, "set", self.target_away())

    def report(self):
        fails = [r for r in self.rows if r["verdict"] == "FAIL"]
        obstructions = sum(1 for mv in self.moves if mv["obstruction"])
        summary = {"result": "FAIL" if fails else "PASS", "moves_to_55": self.moves_to[GATE],
                   "moves_to_60": self.moves_to[LOCK], "false_obstruction_stops": obstructions,
                   "heater_used": self.heater_used, "before": self.snapshot, "after": self.after}
        (self.out / "tp1-report.json").write_text(json.dumps({"summary": summary, "steps": self.rows,
                                                              "moves": self.moves}, indent=2))
        md = [f"# TP-1 automatic — {summary['result']}", "",
              f"- Moves to 55 °C: {summary['moves_to_55']}; to 60 °C: {summary['moves_to_60']}; "
              f"false Obstruction stops at 600 mA: {obstructions}; heater used: {self.heater_used}", "",
              "| t (s) | verdict | step | reading °C | detail |", "|---|---|---|---|---|"]
        md += [f"| {r['t_s']} | {r['verdict']} | {r['step']} | {r['reading_c']} | {r['detail']} |" for r in self.rows]
        md += ["", "| move | kind | start °C | end °C | peak after stop °C | Obstruction |", "|---|---|---|---|---|---|"]
        md += [f"| {m['n']} | {m['kind']} | {m['start_c']} | {m['end_c']} | {m['peak_after_stop_c']} | {m['obstruction']} |"
               for m in self.moves]
        md += ["", "| setting | before | after |", "|---|---|---|"]
        md += [f"| {k} | {self.snapshot.get(k)} | {self.after.get(k)} |" for k in SNAPSHOT]
        (self.out / "tp1-report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        (self.out / "device-log.txt").write_text("\n".join(f"{t:9.1f} {l}" for t, l in self.dev.logs),
                                                 encoding="utf-8")
        print(f"\nTP-1: {summary['result']} — report in {self.out}", flush=True)
        return summary["result"]


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--sim-fault")
    ap.add_argument("--out")
    a = ap.parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = pathlib.Path(a.out or pathlib.Path(__file__).parent / "out" / stamp)
    out.mkdir(parents=True, exist_ok=True)
    if a.sim:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from tp1_sim import SimDevice
        dev = SimDevice(fault=a.sim_fault)
    elif a.host:
        dev = RealDevice(a.host)
    else:
        ap.error("give --host <unit address> or --sim")
    await dev.start()
    await dev.sleep(5)                        # first states
    run = Run(dev, out)
    try:
        await run.run()
        await run.restore()
    finally:
        if dev.get(E_HEATER):
            await dev.switch(E_HEATER, False)
        result = run.report()
        await dev.close()
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
