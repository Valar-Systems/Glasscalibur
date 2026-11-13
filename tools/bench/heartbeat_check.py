#!/usr/bin/env python3
"""Heartbeat file checks HB1-HB5 — BENCH ONLY (tools/regression-gate/predictions/2026-11-bench-heartbeat-retry.md).

    python tools/bench/heartbeat_check.py

Runs each check on this folder's bench_common.py and on a patched copy (its sabotage), on this PC,
with no unit. Uses its own temporary heartbeat files, never out/guard-heartbeat.json. Prints, per
check, the registered outcome next to the observed one.
"""
import asyncio, json, os, pathlib, shutil, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).parent
PY = sys.executable
SAB = {  # name: [(old, new), ...] applied to a copy of bench_common.py
    "no-retry": [
        ("    for _ in range(REPLACE_TRIES):\n        try:\n            os.replace(tmp, path)\n            return True\n"
         "        except PermissionError:\n            time.sleep(RETRY_S)\n    return False\n",
         "    os.replace(tmp, path)\n    return True\n"),
        ("    for _ in range(READ_TRIES):\n        try:\n            hb = json.loads(path.read_text(encoding=\"utf-8\"))\n"
         "            break\n        except PermissionError:\n            time.sleep(RETRY_S)\n"
         "        except (OSError, ValueError):\n            return False, \"no heartbeat from the open guard (is open_guard.py running?)\"\n"
         "    else:\n        return False, \"the open guard's heartbeat file stayed locked\"\n",
         "    try:\n        hb = json.loads(path.read_text(encoding=\"utf-8\"))\n"
         "    except (OSError, ValueError):\n        return False, \"no heartbeat from the open guard (is open_guard.py running?)\"\n"),
    ],
    "refused-read-ok": [
        ("        except PermissionError:\n            time.sleep(RETRY_S)\n        except (OSError, ValueError):",
         "        except PermissionError:\n            return True, \"refused read taken as OK\"\n        except (OSError, ValueError):"),
    ],
    "stale-retry": [
        ("    age = now() - hb.get(\"t\", 0)\n",
         "    age = now() - hb.get(\"t\", 0)\n    t_end = time.time() + 5.0\n"
         "    while age > max_age and time.time() < t_end:\n        time.sleep(0.1)\n        try:\n"
         "            hb = json.loads(path.read_text(encoding=\"utf-8\"))\n        except (OSError, ValueError):\n"
         "            pass\n        age = now() - hb.get(\"t\", 0)\n"),
    ],
}
results = []


def report(name, predicted, ok, detail):
    got = "PASS" if ok else "FAIL"
    results.append(got == predicted)
    print(f"{'as predicted' if got == predicted else 'MISS        '}  {name}: predicted {predicted}, got {got}  ({detail})",
          flush=True)


def copy_with(sab):
    d = tempfile.mkdtemp(prefix=f"hb-{sab}-")
    src = (HERE / "bench_common.py").read_text(encoding="utf-8")
    for old, new in SAB[sab]:
        assert src.count(old) == 1, f"sabotage {sab}: {src.count(old)} matches"
        src = src.replace(old, new)
    pathlib.Path(d, "bench_common.py").write_text(src, encoding="utf-8")
    return d


WRITER = r"""
import sys, time, json, os, pathlib
sys.path.insert(0, sys.argv[1]); import bench_common as bc
p, end, period, die = pathlib.Path(sys.argv[2]), time.time() + float(sys.argv[3]), float(sys.argv[4]), sys.argv[5] == "die"
n = skipped = 0; err = None
try:
    while time.time() < end:
        if bc.write_heartbeat(True, True, "old", path=p) is False: skipped += 1
        n += 1
        time.sleep(period)
except Exception as e:
    err = f"{type(e).__name__}: {e}"
print(json.dumps({"beats": n, "skipped": skipped, "error": err}), flush=True)
if die: os._exit(0)
"""
READER = r"""
import sys, time, json, pathlib
sys.path.insert(0, sys.argv[1]); import bench_common as bc
p, end = pathlib.Path(sys.argv[2]), time.time() + float(sys.argv[3]) - 0.3
n = bad = 0; first = None; err = None
time.sleep(0.3)
try:
    while time.time() < end:
        ok, why = bc.guard_ok(path=p); n += 1
        if not ok:
            bad += 1; first = first or why
        time.sleep(0.001)
except Exception as e:
    err = f"{type(e).__name__}: {e}"
print(json.dumps({"reads": n, "not_ok": bad, "first": first, "error": err}))
"""


def hb1(code_dir, seconds=20.0):
    p = os.path.join(tempfile.mkdtemp(prefix="hb1-"), "guard-heartbeat.json")
    w = subprocess.Popen([PY, "-c", WRITER, code_dir, p, str(seconds), "0.005", "live"], stdout=subprocess.PIPE, text=True)
    r = subprocess.Popen([PY, "-c", READER, code_dir, p, str(seconds)], stdout=subprocess.PIPE, text=True)
    wo, ro = json.loads(w.communicate()[0]), json.loads(r.communicate()[0])
    ok = wo["error"] is None and wo["skipped"] <= 0.01 * max(wo["beats"], 1) and ro["error"] is None and ro["not_ok"] == 0
    return ok, f"writer {wo}; reader {ro}"


HB2 = r"""
import sys, time, json, pathlib, tempfile
sys.path.insert(0, sys.argv[1]); import bench_common as bc
def refuse(a, b): raise PermissionError(5, "Access is denied")
bc.os.replace = refuse
p = pathlib.Path(tempfile.mkdtemp()) / "guard-heartbeat.json"
t0 = time.time(); err = None; r = None
try:
    r = bc.write_heartbeat(True, True, "old", path=p)
except Exception as e:
    err = type(e).__name__
print(json.dumps({"returned": r, "error": err, "s": round(time.time() - t0, 3)}))
"""
HB3 = r"""
import sys, time, json, pathlib, tempfile
sys.path.insert(0, sys.argv[1]); import bench_common as bc
p = pathlib.Path(tempfile.mkdtemp()) / "guard-heartbeat.json"; p.write_text("{}")
def refuse(self, *a, **k): raise PermissionError(5, "Access is denied")
pathlib.Path.read_text = refuse
t0 = time.time(); ok, why = bc.guard_ok(path=p)
print(json.dumps({"ok": ok, "why": why, "s": round(time.time() - t0, 3)}))
"""
HB5 = r"""
import sys, time, json, asyncio, pathlib, subprocess
sys.path.insert(0, sys.argv[1]); import bench_common as bc
p = pathlib.Path(sys.argv[2])
class Stand:
    def __init__(self): self.stop_at = None
    def now(self): return time.monotonic()
    async def sleep(self, s): await asyncio.sleep(s)
    def get(self, name): return "OPENING" if name == "State" else None
    async def cover(self, path, cmd, pos=None):
        if cmd == "stop" and self.stop_at is None: self.stop_at = time.time()
dev = Stand(); gate = bc.MoveGate(dev, check=lambda: bc.guard_ok(path=p))
time.sleep(1.0)
why = None
try:
    asyncio.run(gate.sleep(30))
except bc.GuardLost as e:
    why = str(e)
last = json.loads(p.read_text(encoding="utf-8"))["t"]
print(json.dumps({"stop_after_last_beat_s": None if dev.stop_at is None else round(dev.stop_at - last, 2), "raised": why}))
"""


def run_snippet(code, *args):
    return json.loads(subprocess.run([PY, "-c", code, *args], capture_output=True, text=True).stdout)


def hb2(code_dir):
    o = run_snippet(HB2, code_dir)
    return o["error"] is None and o["returned"] is False and o["s"] <= 0.6, str(o)


def hb3(code_dir):
    o = run_snippet(HB3, code_dir)
    return (not o["ok"]) and "stayed locked" in o["why"] and o["s"] <= 0.3, str(o)


def hb5(code_dir):
    p = os.path.join(tempfile.mkdtemp(prefix="hb5-"), "guard-heartbeat.json")
    w = subprocess.Popen([PY, "-c", WRITER, str(HERE), p, "3.0", "0.5", "die"], stdout=subprocess.PIPE, text=True)
    o = run_snippet(HB5, code_dir, p)
    w.communicate()
    s = o["stop_after_last_beat_s"]
    return s is not None and s <= 2.8 and o["raised"] is not None and "s old" in o["raised"], str(o)


def hb4():
    out = {}
    for name, extra, want in (("sim", [], "TP-1: PASS"), ("drop", ["--sim-guard", "drop-after-1"], "TP-1: INCOMPLETE")):
        d = tempfile.mkdtemp(prefix=f"hb4-{name}-")
        r = subprocess.run([PY, str(HERE / "tp1_run.py"), "--sim", *extra, "--out", d], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        line = [l for l in r.stdout.splitlines() if l.startswith("TP-1:")]
        stop = "STOP sent" in r.stdout
        out[name] = (bool(line) and line[-1].startswith(want) and (name == "sim" or stop), line[-1][:20] if line else None)
    return all(v[0] for v in out.values()), str({k: v[1] for k, v in out.items()})


if __name__ == "__main__":
    head = str(HERE)
    ok, det = hb1(head); report("HB1 head (stress 20 s)", "PASS", ok, det)
    ok, det = hb1(copy_with("no-retry")); report("HB1 sabotage: no retries", "FAIL", ok, det)
    ok, det = hb2(head); report("HB2 head (replace always refused)", "PASS", ok, det)
    ok, det = hb2(copy_with("no-retry")); report("HB2 sabotage: no retries", "FAIL", ok, det)
    ok, det = hb3(head); report("HB3 head (read always refused)", "PASS", ok, det)
    ok, det = hb3(copy_with("refused-read-ok")); report("HB3 sabotage: refused read taken as OK", "FAIL", ok, det)
    ok, det = hb4(); report("HB4 head (TP-1 dry runs)", "PASS", ok, det)
    ok, det = hb5(head); report("HB5 head (writer stops mid-move)", "PASS", ok, det)
    ok, det = hb5(copy_with("stale-retry")); report("HB5 sabotage: stale reading retried 5 s", "FAIL", ok, det)
    print(f"\n{sum(results)}/{len(results)} as predicted")
    sys.exit(0 if all(results) else 1)
