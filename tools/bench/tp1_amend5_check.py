#!/usr/bin/env python3
"""TP-1 Amendment 5 dry-run checks (A5-1 to A5-6), each with its sabotage — BENCH ONLY
(tools/regression-gate/predictions/2026-11-tp1-automatic.md, Amendment 5 and notes 1-2).

    python tools/bench/tp1_amend5_check.py

Runs tp1_run.py --sim from this folder (the head) and from patched copies (the sabotages), each in
its own temporary folder, and prints the registered outcome next to the observed one.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).parent
PY = sys.executable
SAB = {  # name: (file, old, new) applied to a copy of this folder
    "pair-api": ("tp1_run.py", "        t_lock = y if y is not None else x\n", "        t_lock = ev[0][3] if ev else None\n"),
    "no-flush": ("tp1_run.py", '    log_f = open(out / "device-log.txt", "a", encoding="utf-8")\n\n    def sink(t, line):\n'
                 '        log_f.write(f"{t:9.1f} {line}\\n")\n        log_f.flush()\n',
                 '    log_f = open(out / "device-log.txt", "a", encoding="utf-8", buffering=1 << 20)\n\n    def sink(t, line):\n'
                 '        log_f.write(f"{t:9.1f} {line}\\n")\n'),
    "no-mid-stop": ("tp1_run.py", "            ok, peak, t_idle = await self.watch_move(400, stop_at=goal if goal < LOCK else None)\n",
                    "            ok, peak, t_idle = await self.watch_move(400, stop_at=None)\n"),
    "no-precondition": ("tp1_run.py", "            if not await self.gate_ready():\n                continue\n            t_chk, v = self.dev.now(), self.T()\n"
                        "            if v is None or v < PROBE_MIN:\n                continue\n",
                        "            t_chk, v = self.dev.now(), self.T()\n"),
    "late-stop": ("tp1_run.py", "            if self.state() in (\"OPENING\", \"CLOSING\"):\n                await self.stop()\n                return True\n",
                  "            if self.state() in (\"OPENING\", \"CLOSING\"):\n                await self.dev.sleep(2.0)\n                await self.stop()\n                return True\n"),
    "no-void": ("tp1_run.py", "            if fw is None or fw < GATE:\n", "            if False:\n"),
    "verdict-ignores-notrun": ("tp1_run.py", 'cut_short = [r for r in self.rows if r["verdict"] == "INCOMPLETE"] or self.gate_notrun',
                               'cut_short = [r for r in self.rows if r["verdict"] == "INCOMPLETE"]'),
    "no-stopfile": ("tp1_run.py", "            if not self.off and self._stop is not None and self._stop.exists():\n",
                    "            if False:\n"),
    "no-stop-on-fail": ("tp1_run.py", '        if verdict == "FAIL" and not self.in_clean_stop:\n', "        if False:\n"),
    "restore-by-ma": ("tp1_run.py", "        if s.get(E_IRUN) is not None:\n            await self.dev.number(E_IRUN, s[E_IRUN])\n",
                      "        if s.get(E_IRUN) is not None:\n            await self.dev.number(E_CURRENT, s[E_CURRENT])\n"),
}
results = []
_copies = {}


def report(name, predicted, ok, detail):
    got = "PASS" if ok else "FAIL"
    results.append(got == predicted)
    print(f"{'as predicted' if got == predicted else 'MISS        '}  {name}: predicted {predicted}, got {got}  ({detail})", flush=True)


def code_dir(sab):
    if sab is None:
        return HERE
    if sab not in _copies:
        d = pathlib.Path(tempfile.mkdtemp(prefix=f"a5-{sab}-"))
        for f in ("tp1_run.py", "tp1_sim.py", "bench_common.py", "bench_prompt.py"):
            shutil.copy(HERE / f, d / f)
        fname, old, new = SAB[sab]
        src = (d / fname).read_text(encoding="utf-8")
        assert src.count(old) == 1, f"sabotage {sab}: {src.count(old)} matches"
        (d / fname).write_text(src.replace(old, new), encoding="utf-8")
        _copies[sab] = d
    return _copies[sab]


def run(fault=None, sab=None):
    out = pathlib.Path(tempfile.mkdtemp(prefix=f"a5-run-{fault or 'default'}-"))
    args = [PY, str(code_dir(sab) / "tp1_run.py"), "--sim", "--out", str(out)] + (["--sim-fault", fault] if fault else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    d = {"rc": p.returncode, "stdout": p.stdout, "out": out}
    try:
        d["report"] = json.loads((out / "tp1-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d["report"] = None
    d["rows"] = [json.loads(l) for l in (out / "tp1-rows.txt").read_text(encoding="utf-8").splitlines()] \
        if (out / "tp1-rows.txt").exists() else []
    d["log"] = (out / "device-log.txt").read_text(encoding="utf-8").splitlines() if (out / "device-log.txt").exists() else []
    d["probes"] = json.loads((out / "probes.json").read_text(encoding="utf-8")) if (out / "probes.json").exists() else []
    d["cmds"] = json.loads((out / "sim-commands.json").read_text(encoding="utf-8")) if (out / "sim-commands.json").exists() else []
    d["result"] = (d["report"] or {}).get("summary", {}).get("result")
    return d


def rows(d, start, verdict=None):
    return [r for r in d["rows"] if r["step"].startswith(start) and (verdict is None or r["verdict"] == verdict)]


def log_times(d, text):
    return [float(l[:9]) for l in d["log"] if text in l]


# ---- checks
def a51(d):
    w = rows(d, "one warning event; the firmware's logged value")
    info = rows(d, "warning: API pairing")
    ok = bool(w) and w[0]["verdict"] == "PASS" and bool(info) and "order: event first" in info[0]["detail"]
    return ok, f"{[r['verdict'] for r in w]}; {info[0]['detail'] if info else None}"


def a51_sab(d):
    w = rows(d, "one warning event; the firmware's logged value")
    stop = rows(d, "miss: one warning event", "INCOMPLETE")
    return bool(w) and w[0]["verdict"] == "PASS" and not stop, f"{[(r['verdict'], r['detail'][:60]) for r in w]}; clean stop rows {len(stop)}"


def a51b(d):
    lk, cl = rows(d, "lockout at the first reading >= 60"), rows(d, "cleared at the first reading below 48")
    ok = bool(lk) and lk[0]["verdict"] == "PASS" and bool(cl) and cl[0]["verdict"] == "PASS"
    return ok, f"lockout {[(r['verdict'], r['detail']) for r in lk]}; clear {[(r['verdict'], r['detail'][:50]) for r in cl]}"


def a52(d):
    try:
        n = int((d["out"] / "sim-exit-count.txt").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "no exit count"
    return len(d["log"]) >= n, f"simulator produced {n} lines; device-log.txt holds {len(d['log'])}; exit code {d['rc']}"


def a53(d):
    st = rows(d, "heating move stopped at 56.5", "INFO")
    heat = rows(d, "reading between 55.0 and 56.5: heater", "INFO")
    gaps = [float(re.search(r"STOP ([\d.]+) s after", r["detail"]).group(1)) for r in st]
    ok = (bool(gaps) and gaps[0] < 1.0) or bool(heat)
    return ok, f"STOP gaps {gaps}; heater-to-56.5 rows {len(heat)}"


def a53_stop(d):
    st = rows(d, "heating move stopped at 56.5", "INFO")
    gaps = [float(re.search(r"STOP ([\d.]+) s after", r["detail"]).group(1)) for r in st]
    return bool(gaps) and gaps[0] < 1.0, f"STOP gaps {gaps}"


VERDICT = r"""
import sys, json, tempfile, pathlib, asyncio
sys.path.insert(0, sys.argv[1])
import tp1_run
from tp1_sim import SimDevice
out = pathlib.Path(tempfile.mkdtemp(prefix="a5-verdict-"))
r = tp1_run.Run(SimDevice(), out)
r.rec("a gate probe that passed", "PASS")
r.gate_notrun.append("api open refused (motor)")
print(json.dumps({"result": r.report()}))
"""


def a54d_verdict(code):
    o = subprocess.run([PY, "-c", VERDICT, str(code)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = [l for l in o.stdout.splitlines() if l.startswith("{")]
    res = json.loads(line[-1])["result"] if line else None
    return res == "INCOMPLETE", f"verdict {res}"


def b4(d, step):
    f = [r for r in d["rows"] if r["verdict"] == "FAIL"]
    miss = rows(d, "miss:", "INCOMPLETE")
    ok = bool(f) and f[0]["step"].startswith(step) and bool(miss) and d["result"] == "FAIL"
    return ok, f"first FAIL {f[0]['step'][:50] if f else None}; clean stop rows {len(miss)}; result {d['result']}"


def a54a(d):
    pr = [p for p in d["probes"]]
    bad = [p for p in pr if p["reading"] is None or p["reading"] < 55.5 or p["check_to_send_s"] >= 1.0]
    void = (d["report"] or {}).get("summary", {}).get("gate_probes", {}).get("void")
    gp = [r for r in d["rows"] if "refused (motor)" in r["step"] or r["step"].startswith(("scheduled close then open", "a refused Close"))]
    refused = all(r["verdict"] == "PASS" for r in gp if "void" not in r["step"] and "not run" not in r["step"])
    return not bad and void == 0 and refused and len(gp) >= 8, f"probes {len(pr)}; sent below 55.5 or late {len(bad)}" + \
        (f" (first {bad[0]})" if bad else "") + f"; void {void}; gate rows {len(gp)}; all refused {refused}"


def a54b(d):
    acc = [p for p in d["probes"] if p["accepted"]]
    t_act = [t for t in log_times(d, "COVER open_action")]
    t_stop = log_times(d, "COVER stop_action")
    first_acc_t = None
    if acc:
        g = [r for r in d["rows"] if r["verdict"] == "FAIL" and "refused (motor)" in r["step"]]
        first_acc_t = g[0]["t_s"] if g else None
    # the accepted probe's move line and the STOP after it
    gap = None
    if first_acc_t is not None:
        moves = [t for t in t_act if t <= first_acc_t]
        if moves:
            m0 = moves[-1]
            nxt = [t for t in t_stop if t >= m0]
            gap = round(nxt[0] - m0, 2) if nxt else None
    miss = rows(d, "miss:", "INCOMPLETE")
    ok = bool(acc) and gap is not None and gap < 1.0 and bool(miss)
    return ok, f"accepted probes {len(acc)}; move-to-STOP {gap} s; clean stop rows {len(miss)}"


def a54c(d):
    void_rows = [r for r in d["rows"] if ": void (firmware reading below" in r["step"]]
    misses = [r for r in d["rows"] if r["verdict"] == "FAIL"]
    if not void_rows:
        return False, f"no void row; FAIL rows {[r['step'][:50] for r in misses]}"
    name = void_rows[0]["step"].split(": void")[0]
    later = [r for r in d["rows"] if r["step"] == name and r["verdict"] == "PASS" and r["t_s"] >= void_rows[0]["t_s"]]
    return bool(later) and not misses, f"void '{name}' at {void_rows[0]['t_s']}; later verdict {[r['verdict'] for r in later]}; FAIL rows {len(misses)}"


def a54d(d):
    gp = (d["report"] or {}).get("summary", {}).get("gate_probes", {})
    left = (gp.get("not_run") or [])
    return d["result"] != "PASS" and bool(left), f"result {d['result']}; not run {left}; void {gp.get('void')}"


def a55a(d):
    op = rows(d, "stopped: operator", "INCOMPLETE")
    t_stop = [t for t in log_times(d, "COVER stop_action") if t >= 700.0]
    heater_off = not any(c[1] == "switch" and c[2] == "BENCH heater" and c[3] for c in d["cmds"] if c[0] >= 700.0)
    rep = (d["out"] / "tp1-report.md").exists()
    ok = bool(op) and bool(t_stop) and t_stop[0] - 700.0 <= 1.5 and rep and heater_off and len(d["log"]) > 0
    return ok, f"operator rows {len(op)}; first STOP after the file at +{round(t_stop[0] - 700.0, 2) if t_stop else None} s; report {rep}"


def a55a_sab(d):
    late = [r for r in d["rows"] if r["t_s"] > 702.0]
    op = rows(d, "stopped: operator", "INCOMPLETE")
    return bool(op) and not late, f"operator rows {len(op)}; rows after 702 s {len(late)}"


def a55b(d):
    f = [r for r in d["rows"] if r["verdict"] == "FAIL"]
    if not f:
        return False, "no FAIL row"
    t_f = f[0]["t_s"]
    after = [c for c in d["cmds"] if c[0] > t_f]
    other = [c for c in after if not ((c[1] == "cover" and c[2] == "stop") or (c[1] == "switch" and c[2] == "BENCH heater" and not c[3])
                                      or (c[1] == "number" and c[2] == "IRUN value"))]
    return bool(after) and not other, f"FAIL '{f[0]['step'][:40]}' at {t_f}; commands after {len(after)}; others {other[:3]}"


def a56(d):
    r = rows(d, "Speed and Motor Current as before")
    return bool(r) and r[0]["verdict"] == "PASS", f"{[(x['verdict'], x['detail']) for x in r]}"


if __name__ == "__main__":
    d0 = run()
    report("A5-1 head (default): warning on the logged value, pairing recorded, event first", "PASS", *a51(d0))
    report("A5-1 sabotage (warn-below-50): warning FAIL and clean stop", "FAIL", *a51_sab(run("warn-below-50")))
    report("A5-1b head (default): lockout and clear on the logged values", "PASS", *a51b(d0))
    report("A5-1b sabotage (lockout paired with the API reading)", "FAIL", *a51b(run(sab="pair-api")))
    report("A5-2 head (exit-at-600): every line on disk", "PASS", *a52(run("exit-at-600")))
    report("A5-2 sabotage (buffered, not flushed)", "FAIL", *a52(run("exit-at-600", "no-flush")))
    report("A5-3 head (default): phase A STOP < 1 s after 56.5, or heater to 56.5", "PASS", *a53(d0))
    report("A5-3 sabotage (no mid-move STOP): no STOP recorded", "FAIL", *a53_stop(run(sab="no-mid-stop")))
    report("A5-4a head (cool-fast): every probe after a reading >= 55.5 < 1 s before, none void, all refused", "PASS", *a54a(run("cool-fast")))
    report("A5-4a sabotage (cool-fast, precondition removed)", "FAIL", *a54a(run("cool-fast", "no-precondition")))
    report("A5-4b head (gate-open): accepted, STOP < 1 s, miss, clean stop", "PASS", *a54b(run("gate-open")))
    report("A5-4b sabotage (gate-open, STOP 2 s late)", "FAIL", *a54b(run("gate-open", "late-stop")))
    report("A5-4c head (state-lag): void, stopped, retried, refused", "PASS", *a54c(run("state-lag")))
    report("A5-4c sabotage (state-lag, void detection removed)", "FAIL", *a54c(run("state-lag", "no-void")))
    report("A5-4d head (no-reheat): a not-run probe left, result not PASS", "PASS", *a54d(run("no-reheat")))
    report("A5-4d verdict head (one probe not run, no FAIL): INCOMPLETE", "PASS", *a54d_verdict(code_dir(None)))
    report("A5-4d verdict sabotage (verdict ignores not-run): PASS", "FAIL", *a54d_verdict(code_dir("verdict-ignores-notrun")))
    report("A5-5a head (operator-stop-at-700)", "PASS", *a55a(run("operator-stop-at-700")))
    report("A5-5a sabotage (STOP-file check removed)", "FAIL", *a55a_sab(run("operator-stop-at-700", "no-stopfile")))
    report("A5-5b head (rest-close-accepted): only STOP and put-backs after the FAIL", "PASS", *a55b(run("rest-close-accepted")))
    report("A5-5b sabotage (no stop on FAIL)", "FAIL", *a55b(run("rest-close-accepted", "no-stop-on-fail")))
    report("A5-6 head (default): IRUN value and Motor Current as before", "PASS", *a56(d0))
    report("B4 head (default): PASS", "PASS", d0["result"] == "PASS", f"result {d0['result']}")
    report("B4 sabotage rest-close-accepted: FAIL at that step, clean stop", "PASS", *b4(run("rest-close-accepted"), "rest close refused (motor)"))
    report("B4 sabotage refused-close-no-cancel: FAIL at that step, clean stop", "PASS", *b4(run("refused-close-no-cancel"), "a refused Close cancels"))
    report("A5-6 sabotage (restore through Motor Current)", "FAIL", *a56(run(sab="restore-by-ma")))
    print(f"\n{sum(results)}/{len(results)} as predicted")
    sys.exit(0 if all(results) else 1)
