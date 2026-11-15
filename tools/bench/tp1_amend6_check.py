#!/usr/bin/env python3
"""TP-1 Amendment 6 dry-run checks (A6-1 to A6-5), each with its sabotage — BENCH ONLY
(tools/regression-gate/predictions/2026-11-tp1-automatic.md, Amendment 6 and notes 1-2).

    python tools/bench/tp1_amend6_check.py

Runs tp1_run.py --sim and open_guard.watch from this folder (the head) and from patched copies (the
sabotages), each in its own temporary folder, and prints the registered outcome next to the observed one.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).parent
PY = sys.executable
OLD_RULE = ('        return "PASS" if complete and not cut_short else "INCOMPLETE"\n',
            '        return "INCOMPLETE" if cut_short else "PASS"\n')
SAB = {  # name: [(file, old, new), ...] applied to a copy of this folder
    "skip-gate": [("tp1_run.py", "            await self.gate_checks()\n            self.phases_done.add(\"gate\")\n"
                   "            await self.phase_a_cooldown()\n            self.phases_done.add(\"phase_a_cool\")\n            a_done = True\n",
                   "            await self.phase_a_cooldown()\n            self.phases_done.add(\"phase_a_cool\")\n            a_done = True\n")],
    "drop-check": [("tp1_run.py", '        self.check("lockout at the first reading >= 60 (60.0-62.0)",',
                    '        (lambda *a, **k: None)("lockout at the first reading >= 60 (60.0-62.0)",')],
    "stop-raises": [("tp1_run.py", "        reason = (\"bench window ended\" if isinstance(why, WindowOver) else\n",
                     "        raise RuntimeError(\"clean stop raised\")\n        reason = (\"bench window ended\" if isinstance(why, WindowOver) else\n")],
    "no-freshness": [("tp1_run.py", "            if not self.off and seen > -1e8 and self._dev.now() - seen > STALE_S:\n",
                      "            if False:\n"),
                     ("tp1_run.py", "        if self.dev.now() - self.dev.last_seen(E_TEMP) > STALE_S:\n            return None\n", "")],
    "no-heater-age": [("tp1_run.py", "        if not await self.fresh_reading(HEATER_AGE_S, 4):\n            self.rec(\"heater not switched on: no reading at most 2 s old\", \"INFO\")\n            return False\n", "")],
    "no-guard-data": [("open_guard.py", "            if seen > -1e8 and dev.now() - seen > 10.0:", "            if False:")],
    "no-unknown-line": [("tp1_run.py", '        md = ((["**unit state unknown - check the unit**", ""] if self.stop_undelivered else [])\n',
                         '        md = (([] if self.stop_undelivered else [])\n')],
}
SAB["drop-check+old-rule"] = SAB["drop-check"] + [("tp1_run.py",) + OLD_RULE]
SAB["stop-raises+old-rule"] = SAB["stop-raises"] + [("tp1_run.py",) + OLD_RULE]
results, _copies = [], {}


def report(name, predicted, ok, detail):
    got = "PASS" if ok else "FAIL"
    results.append(got == predicted)
    print(f"{'as predicted' if got == predicted else 'MISS        '}  {name}: predicted {predicted}, got {got}  ({detail})", flush=True)


def code_dir(sab):
    if sab is None:
        return HERE
    if sab not in _copies:
        d = pathlib.Path(tempfile.mkdtemp(prefix=f"a6-{sab}-"))
        for f in ("tp1_run.py", "tp1_sim.py", "bench_common.py", "bench_prompt.py", "open_guard.py"):
            shutil.copy(HERE / f, d / f)
        for fname, old, new in SAB[sab]:
            src = (d / fname).read_text(encoding="utf-8")
            assert src.count(old) == 1, f"INSTRUMENT: sabotage {sab}: {src.count(old)} matches in {fname}"
            (d / fname).write_text(src.replace(old, new), encoding="utf-8")
        _copies[sab] = d
    return _copies[sab]


def run(fault=None, sab=None):
    out = pathlib.Path(tempfile.mkdtemp(prefix=f"a6-run-{fault or 'default'}-"))
    args = [PY, str(code_dir(sab) / "tp1_run.py"), "--sim", "--out", str(out)] + (["--sim-fault", fault] if fault else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    rep = {}
    try:
        rep = json.loads((out / "tp1-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    rows = [json.loads(l) for l in (out / "tp1-rows.txt").read_text(encoding="utf-8").splitlines()] \
        if (out / "tp1-rows.txt").exists() else []
    md = (out / "tp1-report.md").read_text(encoding="utf-8") if (out / "tp1-report.md").exists() else ""
    return {"rc": p.returncode, "stdout": p.stdout, "report": rep, "rows": rows, "md": md,
            "result": rep.get("summary", {}).get("result")}


HEATER = r"""
import sys, json, asyncio, tempfile, pathlib
sys.path.insert(0, sys.argv[1])
import tp1_run
from tp1_sim import SimDevice
dev = SimDevice()
async def main():
    await dev.sleep(10)
    dev.next_read = 1e9                          # no new reading from here on
    dev.seen["Motor Temperature"] = dev.now() - 3.0
    r = tp1_run.Run(dev, pathlib.Path(tempfile.mkdtemp(prefix="a6-heater-")))
    await r.heat_with_heater(56.5, limit_s=5)
    print(json.dumps({"heater_on_sent": any(c[:3] == ("switch", "BENCH heater", True) for c in dev.commands)}))
asyncio.run(main())
"""

GUARD = r"""
import sys, json, asyncio
sys.path.insert(0, sys.argv[1])
import open_guard
from tp1_sim import SimDevice
dev = SimDevice(fault="data-stop-at-700")
beats = []
async def main():
    g = open_guard.Guard(dev)
    await open_guard.watch(dev, g, lambda d: 1e9 if d.now() < 760 else 0,
                           beat=lambda c, w: beats.append((round(dev.now(), 2), bool(c), bool(w))))
asyncio.run(main())
bad = [b for b in beats if b[0] >= 690 and not (b[1] and b[2])]
print(json.dumps({"first_not_ok": bad[0][0] if bad else None, "last_state": dev.last_seen("Motor Temperature")}))
"""


def snippet(code, sab):
    p = subprocess.run([PY, "-c", code, str(code_dir(sab))], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    line = [l for l in p.stdout.splitlines() if l.startswith("{")]
    return json.loads(line[-1]) if line else {"error": (p.stderr or p.stdout)[-300:]}


def a62(d):
    r = [x for x in d["rows"] if x["step"].startswith("stopped: no reading for 10 s") and x["verdict"] == "INCOMPLETE"]
    return bool(r) and 710.0 <= r[0]["t_s"] <= 712.5 and d["result"] == "INCOMPLETE", \
        f"rows {[(x['t_s'], x['step'][:30]) for x in r]}; result {d['result']}"


if __name__ == "__main__":
    d0 = run()
    report("A6-1a head (default): PASS, every phase complete", "PASS",
           d0["result"] == "PASS" and not d0["report"].get("summary", {}).get("phases_missing"),
           f"result {d0['result']}; phases missing {d0['report'].get('summary', {}).get('phases_missing')}; "
           f"checks missing {d0['report'].get('summary', {}).get('checks_missing')}")
    dk = run(sab="skip-gate")
    report("A6-1a sabotage (gate probes skipped): PASS", "FAIL", dk["result"] == "PASS", f"result {dk['result']}")
    db = run(sab="drop-check")
    report("A6-1b head (a check dropped): not PASS", "PASS", db["result"] != "PASS", f"result {db['result']}")
    dbo = run(sab="drop-check+old-rule")
    report("A6-1b sabotage (old rule): not PASS", "FAIL", dbo["result"] != "PASS", f"result {dbo['result']}")
    dc = run("operator-stop-at-700", "stop-raises")
    report("A6-1c head (clean stop raises after STOP): not PASS", "PASS", dc["result"] not in ("PASS", None),
           f"result {dc['result']}")
    dco = run("operator-stop-at-700", "stop-raises+old-rule")
    report("A6-1c sabotage (old rule): not PASS", "FAIL", dco["result"] not in ("PASS", None), f"result {dco['result']}")
    dd = run("data-stop-at-700")
    report("A6-2 head (data-stop-at-700): clean stop 10-12 s after the last state, INCOMPLETE", "PASS", *a62(dd))
    report("A6-2 sabotage (freshness removed)", "FAIL", *a62(run("data-stop-at-700", "no-freshness")))
    h = snippet(HEATER, None)
    report("A6-3 head: reading 3 s old, heater-on not sent", "PASS", h.get("heater_on_sent") is False, str(h))
    hs = snippet(HEATER, "no-heater-age")
    report("A6-3 sabotage (age check removed): sent", "FAIL", hs.get("heater_on_sent") is False, str(hs))
    g = snippet(GUARD, None)
    ok = g.get("first_not_ok") is not None and g["first_not_ok"] - (g.get("last_state") or 0) <= 12.0
    report("A6-4 head: guard heartbeat not OK within 12 s of the last state", "PASS", ok, str(g))
    gs = snippet(GUARD, "no-guard-data")
    oks = gs.get("first_not_ok") is not None and gs["first_not_ok"] - (gs.get("last_state") or 0) <= 12.0
    report("A6-4 sabotage (data-age check removed)", "FAIL", oks, str(gs))
    first = lambda d: (d["md"].splitlines() or [""])[0]
    report("A6-5 head (data-stop-at-700): first report line 'unit state unknown'", "PASS",
           "unit state unknown - check the unit" in first(dd), first(dd)[:60])
    ds = run("data-stop-at-700", "no-unknown-line")
    report("A6-5 sabotage (line removed)", "FAIL", "unit state unknown - check the unit" in first(ds), first(ds)[:60])
    print(f"\n{sum(results)}/{len(results)} as predicted")
    sys.exit(0 if all(results) else 1)
