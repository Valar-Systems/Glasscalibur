#!/usr/bin/env python3
"""Power cuts by hand, PC1-PC6 — BENCH ONLY
(tools/regression-gate/predictions/2026-11-position-truth.md, PC1-PC6 and Amendments 3-4).

    python tools/bench/pc_run.py --host <unit address> --mac <MAC> --window-end HH:MM [--cases PC2,PC3]
    python tools/bench/pc_run.py --sim [--sim-cal Slow|Fast] [--sim-fault NAME] [--cases ...]   # dry run

Daniel cuts the power: when the script counts down to "PULL THE 24 V ADAPTER NOW" he pulls the
unit's 24 V adapter from the wall; the script waits until the unit drops off the network, and
10 s later tells him to plug it back in. USB stays unplugged, so the chip loses power too.
Each case is judged on its registered outcome; where the carriage really stopped is taken from
the recovery move's log lines and reported beside the last position the unit reported.

Like tp1_run.py it sends nothing until the unit reports the requested MAC, checks the MAC again
after every power-up, and keeps no address, MAC or unit-name suffix in its report or log. No case
starts with under 5 minutes of the bench window left (--window-end, Pacific time); when the
window ends the script sends STOP and stops. A case whose speed isn't the unit's calibrated speed
is not run (Auto-Calibrate at that speed first; Daniel's call).
"""
import argparse, asyncio, datetime, pathlib, re, sys, time

SPM = 3066.6667
CASE_SPEED = {"PC1": "Fast", "PC2": "Slow", "PC3": "Slow", "PC4": None, "PC5": "Slow", "PC6": "Slow"}
E_COVER, E_STATE, E_FAULT = "Glasscalibur", "State", "Fault"
E_S5, E_S4, E_STROKE = "Close Limit Switch", "Open Limit Switch", "Open stroke"
E_SPEED, E_LOCK, E_RESTART = "Speed", "Speed Lock", "Restart"
E_S5DEAD = "BENCH: close switch (S5) dead, kept across restarts"
UNKNOWN = "position unknown"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
REDACT = [(re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
          (re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b"), "<mac>"),
          (re.compile(r"(glasscalibur-)[0-9a-fA-F]{6}\b"), r"\1XXXXXX")]
RX_FROM = re.compile(r"closing until S5 .* from (-?\d+) steps")
RX_S5 = re.compile(r"S5 triggered at (-?\d+) steps")
RX_S4 = re.compile(r"S4 triggered at (-?\d+) steps")


def redact(line):
    for rx, rep in REDACT:
        line = rx.sub(rep, line)
    return line


def norm_mac(m):
    return "".join(c for c in str(m or "").lower() if c in "0123456789abcdef")


# ----------------------------------------------------------------------------- real unit
class RealDevice:
    def __init__(self, host, mac):
        self.host, self.want, self.t0 = host, norm_mac(mac), time.monotonic()
        self.states, self.logs, self.keys, self.api, self.mac = {}, [], {}, None, None

    def now(self):
        return time.monotonic() - self.t0

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def start(self):
        from aioesphomeapi import APIClient, LogLevel
        self.api = APIClient(self.host, 6053, None, client_info="glasscalibur-pc")
        await self.api.connect(login=True)
        self.mac = (await self.api.device_info()).mac_address
        infos, _ = await self.api.list_entities_services()
        kinds = {}
        for i in infos:
            self.keys[i.name], kinds[i.key] = i.key, (type(i).__name__, i.name)
        self.states = {}

        def on_state(st):
            kind, name = kinds.get(st.key, ("?", "?"))
            if kind == "CoverInfo":
                self.states[name] = st.position
                # The cover publishes OPENING the moment a move starts (State polls every 500 ms).
                self.states[name + ".op"] = int(getattr(st, "current_operation", 0))
            else:
                self.states[name] = getattr(st, "state", None)

        def on_log(msg):
            m = msg.message.decode("utf-8", "replace") if isinstance(msg.message, bytes) else msg.message
            self.logs.append((self.now(), redact(ANSI.sub("", m))))

        self.api.subscribe_states(on_state)
        self.api.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)

    async def close(self):
        try:
            await asyncio.wait_for(self.api.disconnect(), 5)
        except Exception:
            pass

    def get(self, name):
        return self.states.get(name)

    async def reachable(self):
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection(self.host, 6053), 1.0)
            w.close()
            return True
        except Exception:
            return False

    async def reconnect(self, timeout=120.0):
        await self.close()
        end = self.now() + timeout
        while self.now() < end:
            if await self.reachable():
                try:
                    await self.start()
                    await self.sleep(3)
                    return norm_mac(self.mac) == self.want
                except Exception:
                    pass
            await self.sleep(2)
        return False

    def say(self, text):
        print(f"\a[{time.strftime('%H:%M:%S')}] >>> {text}", flush=True)

    async def cover(self, cmd, pos=None):
        key = self.keys[E_COVER]
        if cmd == "stop":
            self.api.cover_command(key, stop=True)
        else:
            self.api.cover_command(key, position={"open": 1.0, "close": 0.0}.get(cmd, pos))

    async def press(self, name):
        self.api.button_command(self.keys[name])

    async def switch(self, name, on):
        self.api.switch_command(self.keys[name], on)

    async def select(self, name, option):
        self.api.select_command(self.keys[name], option)


# ----------------------------------------------------------------------------- the run
class WindowOver(Exception):
    pass


class Run:
    def __init__(self, dev, out, window_end):
        self.dev, self.out, self.window_end, self.rows = dev, out, window_end, []
        self.verdicts = {}

    # --- helpers
    def rec(self, case, step, verdict, detail=""):
        self.rows.append((round(self.dev.now(), 1), case, step, verdict, detail))
        if verdict in ("FAIL", "NOT RUN", "INSTRUMENT", "NOT A RESULT"):
            self.verdicts.setdefault(case, set()).add(verdict)
        elif verdict == "PASS":
            self.verdicts.setdefault(case, set()).add("PASS")
        print(f"[{self.dev.now():8.1f}s] {case:4} {verdict:12} {step}" + (f" - {detail}" if detail else ""), flush=True)

    def check(self, case, step, ok, detail=""):
        self.rec(case, step, "PASS" if ok else "FAIL", detail)
        return ok

    def minutes_left(self):
        return self.window_end(self.dev) if self.window_end else 1e9

    async def guard(self):
        if self.minutes_left() <= 0:
            try:
                await self.dev.cover("stop")
            except Exception:
                pass
            raise WindowOver()

    async def wait(self, cond, timeout, step=0.2):
        end = self.dev.now() + timeout
        while self.dev.now() < end:
            await self.guard()
            if cond():
                return True
            await self.dev.sleep(step)
        return cond()

    def g(self, name):
        return self.dev.get(name)

    def at(self, value):
        c = self.g(E_COVER)
        return c is not None and abs(c - value) < 1e-3

    def unknown(self):
        return UNKNOWN in str(self.g(E_FAULT) or "")

    def stroke_mm(self):
        s = self.g(E_STROKE)
        return s if s is not None and s == s and 90.0 <= s <= 102.0 else None

    def travel_s(self, speed):
        return 101.0 * SPM / {"Slow": 1200, "Medium": 2600, "Fast": 5500}.get(speed or "Fast", 1200) + 30

    def mark(self):
        return len(self.dev.logs)

    def lines(self, m):
        return [l for _, l in self.dev.logs[m:]]

    async def speed_ok(self, case):
        want = CASE_SPEED[case]
        if want is None:
            return True
        await self.dev.select(E_SPEED, want)
        await self.dev.sleep(6)                         # Speed Lock updates every 5 s
        lock = str(self.g(E_LOCK) or "")
        runs = "Fast" if "until calibration" in lock else (
            next((n for n in ("Slow", "Medium", "Fast") if f"running at {n}" in lock), want))
        if runs != want:
            self.rec(case, "speed", "NOT RUN", f"the unit runs at {runs}; Auto-Calibrate at {want} first")
            return False
        return True

    async def to_s5(self, case, speed):
        if self.g(E_S5) and not self.unknown():
            return True
        await self.dev.cover("close")
        ok = await self.wait(lambda: self.g(E_S5) and self.g(E_STATE) == "IDLE", self.travel_s(speed) + 30)
        if not ok:
            self.rec(case, "back to S5", "FAIL", "S5 not reached")
        return ok

    async def open_to(self, frac, speed):
        await self.dev.cover("open")
        return await self.wait(lambda: (self.g(E_COVER) or 0) >= frac, self.travel_s(speed))

    async def cut(self, case, at_call=None, open_delay=0.0):
        """Countdown, the call, then wait for the unit to drop off the network.
        Returns (dropped, last cover position reported, whether OPENING was reported)."""
        for n in (3, 2, 1):
            self.dev.say(f"Get ready to pull the 24 V adapter from the wall: {n}")
            await self.dev.sleep(1)
        if at_call and not open_delay:
            await at_call()
        self.dev.say("PULL THE 24 V ADAPTER FROM THE WALL NOW")
        if at_call and open_delay:
            await self.dev.sleep(open_delay)
            try:
                await at_call()
            except Exception:
                pass                                   # already off: the run is not a result
        last, opening, fails, t0 = self.g(E_COVER), False, 0, self.dev.now()
        while self.dev.now() - t0 < 60:
            if self.g(E_STATE) == "OPENING" or self.g(E_COVER + ".op") == 1:
                opening = True
            if self.g(E_COVER) is not None:
                last = self.g(E_COVER)
            if await self.dev.reachable():
                fails = 0
            else:
                fails += 1
                if fails >= 3:
                    self.rec(case, "power cut", "INFO", f"unit off the network {self.dev.now() - t0:.1f} s after the call")
                    return True, last, opening
            await self.dev.sleep(1)
        try:
            await self.dev.cover("stop")
        except Exception:
            pass
        self.rec(case, "power cut", "INSTRUMENT", "the unit was still on the network 60 s after the call "
                 "(USB still plugged in?); STOP sent - not a result, may be rerun")
        return False, last, opening

    async def wait_drop(self, timeout):
        end, fails = self.dev.now() + timeout, 0
        while self.dev.now() < end:
            fails = 0 if await self.dev.reachable() else fails + 1
            if fails >= 3:
                return True
            await self.dev.sleep(1)
        return False

    async def power_back(self, case):
        await self.dev.sleep(10)
        self.dev.say("PLUG THE 24 V ADAPTER BACK INTO THE WALL NOW")
        if not await self.dev.reconnect(120):
            self.rec(case, "power back", "INSTRUMENT", "the unit (with the requested MAC) did not come back within 120 s")
            return False
        await self.dev.sleep(3)
        return True

    def stop_point_close(self, m):
        n = [int(x.group(1)) for x in map(RX_FROM.search, self.lines(m)) if x]
        t = [int(x.group(1)) for x in map(RX_S5.search, self.lines(m)) if x]
        return (n[0] - t[0]) / SPM if n and t else None

    def stop_point_open(self, m, start_count=0):
        t = [int(x.group(1)) for x in map(RX_S4.search, self.lines(m)) if x]
        st = self.stroke_mm()
        return st - (t[0] - start_count) / SPM if t and st else None

    def report_stop(self, case, where, last):
        st = self.stroke_mm()
        last_mm = f"{last * st:.2f} mm" if last is not None and st else "n/a"
        self.rec(case, "where it stopped", "INFO",
                 f"{where:.2f} mm from S5 (last position the unit reported: {last_mm})" if where is not None
                 else f"stop point not in the log (last position the unit reported: {last_mm})")

    async def check_unknown_after_cut(self, case):
        self.check(case, "after power-up: Fault shows position unknown", self.unknown(), str(self.g(E_FAULT)))
        self.check(case, "after power-up: cover 50 %", self.at(0.5), f"{self.g(E_COVER)}")

    # --- cases
    async def pc12(self, case):
        speed = CASE_SPEED[case]
        for half, recover in (("A", "close"), ("B", "open")):
            if not await self.to_s5(case, speed):
                return
            await self.open_to(0.45, speed)
            dropped, last, _ = await self.cut(case)
            if not dropped or not await self.power_back(case):
                return
            await self.check_unknown_after_cut(case)
            m = self.mark()
            if recover == "close":
                await self.dev.cover("close")
                ok = await self.wait(lambda: self.g(E_S5) and self.g(E_STATE) == "IDLE", self.travel_s(speed) + 30)
                self.check(case, f"{half}: Close runs until S5, 0 %", ok and self.at(0.0), f"cover {self.g(E_COVER)}")
                self.check(case, f"{half}: position unknown cleared", not self.unknown(), str(self.g(E_FAULT)))
                self.report_stop(case, self.stop_point_close(m), last)
            else:
                await self.dev.cover("open")
                ok = await self.wait(lambda: self.g(E_S4) and self.g(E_STATE) == "IDLE", self.travel_s(speed) + 30)
                self.check(case, f"{half}: Open runs until S4, 100 %", ok and self.at(1.0), f"cover {self.g(E_COVER)}")
                self.check(case, f"{half}: position unknown cleared", not self.unknown(), str(self.g(E_FAULT)))
                self.report_stop(case, self.stop_point_open(m), last)
        await self.to_s5(case, speed)

    async def pc3(self, case):
        if not await self.to_s5(case, "Slow"):
            return
        await self.open_to(0.40, "Slow")
        await self.dev.cover("stop")
        await self.wait(lambda: self.g(E_STATE) == "IDLE", 5)
        p = self.g(E_COVER)
        self.rec(case, "stopped mid-travel", "INFO", f"cover {p}")
        await self.dev.sleep(10)
        dropped, _, _ = await self.cut(case)
        if not dropped or not await self.power_back(case):
            return
        self.check(case, "after power-up: same position", p is not None and abs((self.g(E_COVER) or -1) - p) < 0.005,
                   f"before {p}, after {self.g(E_COVER)}")
        self.check(case, "after power-up: no position unknown", not self.unknown(), str(self.g(E_FAULT)))
        await self.to_s5(case, "Slow")

    async def pc4(self, case):
        if not await self.to_s5(case, "Slow"):
            return
        await self.dev.switch(E_S5DEAD, True)
        await self.dev.sleep(2)
        await self.dev.press(E_RESTART)
        await self.wait_drop(30)                          # the restart takes it off the network
        if not await self.dev.reconnect(120):
            self.rec(case, "restart", "INSTRUMENT", "the unit did not come back within 120 s")
            return
        await self.dev.sleep(3)
        self.check(case, "saved at 0 %, S5 released at boot: position unknown", self.unknown(), str(self.g(E_FAULT)))
        self.check(case, "cover 50 %", self.at(0.5), f"{self.g(E_COVER)}")
        await self.dev.switch(E_S5DEAD, False)
        ok = await self.wait(lambda: self.g(E_S5) and not self.unknown(), 5)
        self.rec(case, "bench option off: S5 pressed, known again", "INFO" if ok else "FAIL", f"cover {self.g(E_COVER)}")

    async def pc5(self, case):
        if not await self.to_s5(case, "Slow"):
            return
        await self.open_to(0.45, "Slow")
        dropped, last, _ = await self.cut(case)
        if not dropped or not await self.power_back(case):
            return
        await self.check_unknown_after_cut(case)
        m = self.mark()
        await self.dev.cover("set", 0.40)
        ok = await self.wait(lambda: any("Position known at S5" in l for l in self.lines(m)), self.travel_s("Slow") + 30)
        self.check(case, "Set 40 % closes to S5 first (logged)",
                   ok and any("closing to S5 first" in l for l in self.lines(m)))
        ok = await self.wait(lambda: self.g(E_STATE) == "IDLE" and not self.g(E_S5), self.travel_s("Slow") + 30)
        self.check(case, "then moves to 40 %", ok and abs((self.g(E_COVER) or 0) - 0.40) <= 0.01, f"cover {self.g(E_COVER)}")
        self.report_stop(case, self.stop_point_close(m), last)
        await self.to_s5(case, "Slow")

    async def pc6(self, case):
        # Run 1 sends Open with the call; each rerun makes the call earlier than the Open.
        for attempt, lead in enumerate((0.0, 0.3, 0.6), 1):
            if not await self.to_s5(case, "Slow"):
                return
            setattr(self.dev, "pc6_next", True)
            dropped, last, opening = await self.cut(case, at_call=lambda: self.dev.cover("open"), open_delay=lead)
            setattr(self.dev, "pc6_next", False)
            if not dropped or not await self.power_back(case):
                return
            s5 = bool(self.g(E_S5))
            if not opening:
                self.rec(case, f"run {attempt}", "NOT A RESULT", "the unit didn't report OPENING before it went off")
                continue
            if not s5:
                self.rec(case, f"run {attempt}", "NOT A RESULT", "S5 released at boot: rerun with the call earlier")
                continue
            self.check(case, f"run {attempt}: boots with S5 pressed: 0 %", self.at(0.0), f"cover {self.g(E_COVER)}")
            self.check(case, f"run {attempt}: no position unknown", not self.unknown(), str(self.g(E_FAULT)))
            return
        self.rec(case, "runs", "NOT A RESULT", "3 runs without a valid PC6 cut")

    async def run(self, cases):
        table = {"PC1": self.pc12, "PC2": self.pc12, "PC3": self.pc3, "PC4": self.pc4, "PC5": self.pc5, "PC6": self.pc6}
        try:
            for case in cases:
                if self.minutes_left() < 5:
                    self.rec(case, "start", "NOT RUN", f"{self.minutes_left():.1f} min of the window left (under 5)")
                    continue
                if not await self.speed_ok(case):
                    continue
                self.rec(case, "start", "INFO", f"speed {CASE_SPEED[case] or 'any'}")
                await table[case](case)
        except WindowOver:
            self.rec("-", "window", "NOT RUN", "the bench window ended: STOP sent, nothing more run")

    def report(self, cases):
        out = ["# Power cuts by hand (PC1-PC6) — bench report", "",
               "| t (s) | case | step | verdict | detail |", "|---|---|---|---|---|"]
        out += [f"| {t} | {c} | {s} | {v} | {d} |" for t, c, s, v, d in self.rows]
        out += ["", "## Result per case", ""]
        overall = "PASS"
        for c in cases:
            v = self.verdicts.get(c, set())
            r = ("FAIL" if "FAIL" in v else "NOT RUN" if "NOT RUN" in v else
                 "INSTRUMENT" if "INSTRUMENT" in v else "PASS" if "PASS" in v else "NOT A RESULT")
            out.append(f"- {c}: {r}")
            if r != "PASS":
                overall = "FAIL" if r == "FAIL" or overall == "FAIL" else "INCOMPLETE"
        out += ["", f"**{overall}**"]
        (self.out / "pc-report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
        (self.out / "pc-device.log").write_text("\n".join(f"{t:9.2f} {l}" for t, l in self.dev.logs) + "\n",
                                                encoding="utf-8")
        print(f"Report: {self.out / 'pc-report.md'} -> {overall}")
        return overall


def window_from(arg):
    """--window-end HH:MM, Pacific time, today."""
    if not arg:
        return None
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Los_Angeles")
    h, m = map(int, arg.split(":"))
    end = datetime.datetime.now(tz).replace(hour=h, minute=m, second=0, microsecond=0)
    return lambda dev: (end - datetime.datetime.now(tz)).total_seconds() / 60.0


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host")
    ap.add_argument("--mac", help="the unit's MAC, as the USB flash reported it")
    ap.add_argument("--window-end", help="end of the bench window, HH:MM Pacific (required with --host)")
    ap.add_argument("--cases", default="PC1,PC2,PC3,PC4,PC5,PC6")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--sim-fault")
    ap.add_argument("--sim-cal", default="Slow")
    ap.add_argument("--sim-window-left", type=float, help="sim only: minutes of window left at the start")
    ap.add_argument("--out")
    a = ap.parse_args()
    cases = [c.strip().upper() for c in a.cases.split(",") if c.strip()]
    if any(c not in CASE_SPEED for c in cases):
        ap.error(f"cases are {', '.join(CASE_SPEED)}")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = pathlib.Path(a.out or pathlib.Path(__file__).parent / "out" / f"pc-{stamp}")
    out.mkdir(parents=True, exist_ok=True)
    if a.sim:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from pc_sim import SimDevice
        dev = SimDevice(fault=a.sim_fault, cal=a.sim_cal)
        want = norm_mac(a.mac) if a.mac else "0a1b2c3d4e5f"
        left = a.sim_window_left
        window = (lambda d: left - d.now() / 60.0) if left is not None else None
    elif a.host:
        if not a.mac or not a.window_end:
            ap.error("--mac and --window-end are required with --host")
        dev, want, window = RealDevice(a.host, a.mac), norm_mac(a.mac), window_from(a.window_end)
    else:
        ap.error("give --host <unit address> --mac <MAC> --window-end HH:MM, or --sim")
    await dev.start()
    if len(want) != 12 or norm_mac(dev.mac) != want:
        print("STOP: the unit at this address does not report the requested MAC - no command sent.")
        (out / "pc-report.md").write_text("# Not run: the unit did not report the requested MAC\n", encoding="utf-8")
        await dev.close()
        return 2
    print("Unit identity: the unit reports the requested MAC. USB must be unplugged for these tests.", flush=True)
    await dev.sleep(3)
    run = Run(dev, out, window)
    try:
        await run.run(cases)
    finally:
        result = run.report(cases)
        await dev.close()
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
