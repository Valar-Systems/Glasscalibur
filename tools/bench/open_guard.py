#!/usr/bin/env python3
"""Guard every open until the stroke is learned — BENCH ONLY
(tools/regression-gate/predictions/2026-11-bench-open-guard.md).

    python tools/bench/open_guard.py --host <unit address> --mac <MAC>     # run for all of 1a

A fresh unit opens toward 101.0 mm until it has learned its stroke, but the old carriage's
hard stop is about 99.1 mm from the S5 trigger (S4 trips at about 95.5). While Open stroke
is unknown, the cover's 0-100 % is scaled to 101.0 mm, so position x 101.0 is the distance
from S5. The guard:
- counts distance only from a close that ended on S5 (or boot with S5 pressed): an open
  that starts before it has seen S5 pressed is stopped at once (FAIL: no reference);
- during an open with the stroke unknown, at 97.0 mm with S4 not pressed: STOP, FAIL;
- once Open stroke is learned (94-101 mm) it only records.
It sends no command except STOP, checks the unit's MAC first (like tp1_run.py), and writes
its record to tools/bench/out/<time>/open-guard.md without the address or the MAC.
"""
import argparse, asyncio, datetime, pathlib, sys

LIMIT_MM, DEFAULT_MM = 97.0, 101.0


class Guard:
    def __init__(self, dev):
        self.dev, self.rows = dev, []
        self.referenced = bool(dev.get("Close Limit Switch"))
        self.stopped_this_move, self.last_state = False, None

    def learned(self):
        s = self.dev.get("Open stroke")
        return s is not None and s == s and 94.0 <= s <= 101.0

    def rec(self, verdict, what):
        row = (round(self.dev.now(), 1), verdict, what)
        self.rows.append(row)
        print(f"[{row[0]:8.1f}s] {verdict:5} {what}", flush=True)

    async def poll(self):
        d = self.dev
        state, s4, s5 = d.get("State"), d.get("Open Limit Switch"), d.get("Close Limit Switch")
        if s5:
            self.referenced = True
        if state != self.last_state:
            if state == "OPENING":
                self.stopped_this_move = False
                self.rec("INFO", f"open started, stroke {'learned' if self.learned() else 'NOT learned'}, "
                                 f"S5 reference {'yes' if self.referenced else 'NO'}")
            elif self.last_state == "OPENING":
                mm = (d.get("Glasscalibur") or 0.0) * (d.get("Open stroke") if self.learned() else DEFAULT_MM)
                self.rec("INFO", f"open ended at about {mm:.1f} mm, S4 {'pressed' if s4 else 'released'}")
            self.last_state = state
        if state != "OPENING" or self.learned() or self.stopped_this_move:
            return
        if not self.referenced:
            await d.cover("api", "stop")
            self.stopped_this_move = True
            self.rec("FAIL", "open started with no S5 reference: STOP sent")
            return
        mm = (d.get("Glasscalibur") or 0.0) * DEFAULT_MM
        if mm >= LIMIT_MM and not s4:
            await d.cover("api", "stop")
            self.stopped_this_move = True
            self.rec("FAIL", f"S4 not tripped by {LIMIT_MM:.0f} mm (at {mm:.2f} mm): STOP sent")

    def write(self, out):
        lines = ["# Open guard", "", "| t (s) | verdict | event |", "|---|---|---|"]
        lines += [f"| {t} | {v} | {w} |" for t, v, w in self.rows]
        (out / "open-guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main():
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from tp1_run import RealDevice, norm_mac
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True)
    ap.add_argument("--mac", required=True)
    a = ap.parse_args()
    out = pathlib.Path(__file__).parent / "out" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    dev = RealDevice(a.host)
    await dev.start()
    if norm_mac(dev.mac) != norm_mac(a.mac) or len(norm_mac(a.mac)) != 12:
        print("STOP: the unit at this address does not report the requested MAC - guard not started.")
        await dev.close()
        return 2
    await dev.sleep(3)
    guard = Guard(dev)
    print("Open guard running (Ctrl+C to end).", flush=True)
    try:
        while True:
            await guard.poll()
            await dev.sleep(0.1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        guard.write(out)
        await dev.close()
    return 1 if any(v == "FAIL" for _, v, _ in guard.rows) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
