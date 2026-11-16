#!/usr/bin/env python3
"""How the bench check scripts read their readings (ruling 77 a; TP-1 Amendment 6 note 3) — BENCH ONLY.

- strip(text): terminal escape codes (CSI and OSC sequences) removed, so a text match sees the words.
- instrument(text): the reason a captured output is an instrument fault, or None. "Filename too long" is one.
- Judge: prints each reading next to its registered outcome. A reading is "as predicted" only when its registered
  reason holds too; an instrument fault is counted neither way and may be rerun with disclosure.

    python tools/bench/check_reading.py --selftest    M1a-M1c
    python tools/bench/check_reading.py --sabotage    each plant, in a copy, turns exactly its row red
"""
import os, re, subprocess, sys, tempfile

_ESC = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_FAULTS = ("Filename too long",)


def strip(text):
    return _ESC.sub("", text or "")


def instrument(text):
    t = strip(text)
    for f in _FAULTS:
        if f in t:
            return f
    return None


class Judge:
    """report(name, predicted, ok, detail, reason=True, fault=None).
    predicted "PASS": as predicted when ok and reason. predicted "FAIL": as predicted when not ok and reason (the
    reading fails for its registered reason). fault: an instrument reason (instrument(), or "no reading")."""

    def __init__(self):
        self.results, self.instruments = [], []

    def report(self, name, predicted, ok, detail, reason=True, fault=None):
        if fault:
            self.instruments.append(name)
            print(f"INSTRUMENT    {name}: {fault} - not a reading  ({detail})", flush=True)
            return
        got = "PASS" if ok else "FAIL"
        good = got == predicted and bool(reason)
        self.results.append(good)
        why = "" if reason else "; registered reason not seen"
        print(f"{'as predicted' if good else 'MISS        '}  {name}: predicted {predicted}, got {got}{why}  ({detail})",
              flush=True)

    def summary(self):
        n = len(self.results)
        print(f"\n{sum(self.results)}/{n} as predicted" + (f"; {len(self.instruments)} instrument fault(s): "
              f"{self.instruments}" if self.instruments else ""))
        return 0 if all(self.results) and not self.instruments else 1


ROWS = (
    ("M1a", "an escape-coded error line is matched after stripping",
     lambda m: "'GC_DRIVER_ENN_GPI' was not declared" in m.strip(
         "src/driver_disabled_at_boot.h:19:44: \x1b[K\x1b[01;31m\x1b[Kerror: \x1b[m\x1b[K'\x1b[01m\x1b[KGC_DRIVER_ENN_GPI"
         "\x1b[m\x1b[K' was not declared in this scope")),
    ("M1b", "'Filename too long' in the output is an instrument fault",
     lambda m: m.instrument("error: unable to create file hardware/x/y.kicad_mod: Filename too long") is not None),
    ("M1c", "clean output is neither stripped of words nor a fault",
     lambda m: m.strip("Couldn't find ID 'pending_pos'.") == "Couldn't find ID 'pending_pos'."
     and m.instrument("Couldn't find ID 'pending_pos'.") is None),
)


def selftest():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m", os.path.abspath(__file__))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ok = True
    for row, label, test in ROWS:
        good = bool(test(m))
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {row} {label}")
    print("check_reading selftest " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


SABOTAGES = {  # the anchors occur once in this file: split so this table holds no second copy
    "S-NOSTRIP": ("    return _ESC.sub(\"\", te" + "xt or \"\")\n", "    return text or \"\"  # SABOTAGE S-NOSTRIP\n", {"M1a"}),
    "S-NOFAULT": ("_FAULTS = (\"Filename too lo" + "ng\",)\n", "_FAULTS = ()  # SABOTAGE S-NOFAULT\n", {"M1b"}),
}


def sabotage():
    src = open(os.path.abspath(__file__), encoding="utf-8").read().replace("\r\n", "\n")
    ok = True
    for name, (anchor, repl, want) in SABOTAGES.items():
        if src.count(anchor) != 1:
            print(f"  FAIL {name}: anchor occurs {src.count(anchor)} times - not planted")
            ok = False
            continue
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "check_reading.py")
            open(p, "w", encoding="utf-8", newline="\n").write(src.replace(anchor, repl))
            r = subprocess.run([sys.executable, "-I", p, "--selftest"], capture_output=True, text=True)
        red = {l.split()[1] for l in r.stdout.splitlines() if l.strip().startswith("FAIL M1")}
        good = r.returncode == 1 and red == want
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {name}: exit {r.returncode}, red {sorted(red)} (want {sorted(want)})")
    print("check_reading SABOTAGE " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--sabotage" in sys.argv:
        sys.exit(sabotage())
    print(__doc__)
