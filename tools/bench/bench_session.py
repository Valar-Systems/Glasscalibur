#!/usr/bin/env python3
"""A bench sitting — BENCH ONLY (tools/regression-gate/predictions/2026-11-bench-guard-prompts.md).

    python tools/bench/bench_session.py start --host <unit address> --mac <MAC> --window-end HH:MM --carriage old|trimmed
    python tools/bench/bench_session.py end   --host <unit address> --mac <MAC>

start: records the sitting in tools/bench/out/sitting.json (the carriage, as confirmed with Daniel at
the start; the window end; the button lock's current setting) and turns the button lock on (Button
Lock, or Child Lock on 2.2.0), so Button 1 can't start a move by accident. Scripts that need Button 1
(TP-1's lockout press) turn it off just before that step and on again after. end: restores Daniel's
original setting and marks the
sitting ended (the record is kept). Like the other scripts it checks the unit's MAC first and keeps
no address or MAC in the record.
"""
import argparse, asyncio, datetime, json, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bench_common import SITTING, lock_name  # noqa: E402


async def set_button_lock(dev, on, settle=2.0):
    name = lock_name(dev)
    await dev.switch(name, on)
    await dev.sleep(settle)
    return dev.get(name) == on


async def start_sitting(dev, carriage, window_end, path=SITTING):
    original = bool(dev.get(lock_name(dev)))
    rec = {"started": datetime.datetime.now().isoformat(timespec="seconds"), "carriage": carriage,
           "window_end": window_end, "button_lock_original": original, "ended": None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    ok = await set_button_lock(dev, True)
    print(f"Sitting started: carriage {carriage}; window ends {window_end}; {lock_name(dev)} was "
          f"{'on' if original else 'off'}, now {'on' if ok else 'NOT on'}.", flush=True)
    return ok


async def end_sitting(dev, path=SITTING):
    rec = json.loads(path.read_text(encoding="utf-8"))
    ok = await set_button_lock(dev, bool(rec["button_lock_original"]))
    rec["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
    rec["button_lock_restored"] = ok
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    kept = path.with_name(f"sitting-{rec['started'].replace(':', '')}.json")
    os.replace(path, kept)
    print(f"Sitting ended: {lock_name(dev)} {'restored' if ok else 'NOT restored'} to "
          f"{'on' if rec['button_lock_original'] else 'off'}; record kept as {kept.name}.", flush=True)
    return ok


async def main():
    from tp1_run import RealDevice, norm_mac
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start", "end"])
    ap.add_argument("--host", required=True)
    ap.add_argument("--mac", required=True)
    ap.add_argument("--window-end")
    ap.add_argument("--carriage", choices=["old", "trimmed"])
    a = ap.parse_args()
    if a.action == "start" and not (a.window_end and a.carriage):
        ap.error("start needs --window-end and --carriage (confirm the carriage with Daniel first)")
    dev = RealDevice(a.host)
    await dev.start()
    if len(norm_mac(a.mac)) != 12 or norm_mac(dev.mac) != norm_mac(a.mac):
        print("STOP: the unit at this address does not report the requested MAC - nothing changed.")
        await dev.close()
        return 2
    await dev.sleep(3)
    try:
        ok = await (start_sitting(dev, a.carriage, a.window_end) if a.action == "start" else end_sitting(dev))
    finally:
        await dev.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
