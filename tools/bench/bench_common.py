"""Shared bench pieces — BENCH ONLY (tools/regression-gate/predictions/2026-11-bench-guard-prompts.md).

- The open guard's heartbeat: open_guard.py writes out/guard-heartbeat.json about twice a second
  (time, connected, watching). guard_ok() reads it.
- MoveGate: no move (Open, Close, Set position, Auto-Calibrate, a bench press that starts motion)
  is sent unless the heartbeat is under 2 s old and says connected and watching; while a move is
  under way every wait checks it, and if it goes stale or says disconnected the script sends STOP
  itself.
- Prompter: prompts that ask Daniel to act, and alerts, open in a window that stays on top of his
  screen (bench_prompt.py) and are spoken by Windows' built-in voice. Dry runs record them instead.
- The sitting record (out/sitting.json), written by bench_session.py.
"""
import asyncio, json, os, pathlib, subprocess, sys, time

OUT = pathlib.Path(__file__).parent / "out"
HEARTBEAT = OUT / "guard-heartbeat.json"
SITTING = OUT / "sitting.json"
MAX_AGE_S = 2.0
# On Windows a file can't be replaced while another process has it open (and a read can collide
# with the replace): retry briefly (2026-11-bench-heartbeat-retry.md).
RETRY_S, REPLACE_TRIES, READ_TRIES = 0.01, 50, 20
MOVING = ("OPENING", "CLOSING")
MOVE_PRESSES = ("Auto-Calibrate", "BENCH: fire scheduled open", "BENCH: fire scheduled close",
                "BENCH: simulate stall")


# ----------------------------------------------------------------------------- heartbeat
def write_heartbeat(connected, watching, carriage, path=HEARTBEAT):
    """True once written. If the replace stays refused, this beat is skipped (False); the next one
    tries again, and a long run of skipped beats reads as stale to the scripts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"t": time.time(), "connected": bool(connected), "watching": bool(watching),
                               "carriage": carriage, "pid": os.getpid()}), encoding="utf-8")
    for _ in range(REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(RETRY_S)
    return False


def guard_ok(path=HEARTBEAT, max_age=MAX_AGE_S, now=time.time):
    """(ok, reason) from the open guard's heartbeat file."""
    for _ in range(READ_TRIES):
        try:
            hb = json.loads(path.read_text(encoding="utf-8"))
            break
        except PermissionError:
            time.sleep(RETRY_S)
        except (OSError, ValueError):
            return False, "no heartbeat from the open guard (is open_guard.py running?)"
    else:
        return False, "the open guard's heartbeat file stayed locked"
    age = now() - hb.get("t", 0)
    if age > max_age:
        return False, f"the open guard's heartbeat is {age:.1f} s old"
    if not hb.get("connected"):
        return False, "the open guard has lost its connection to the unit"
    if not hb.get("watching"):
        return False, "the open guard isn't watching"
    return True, "open guard connected and watching"


class GuardMissing(Exception):
    """A move was not sent: the guard isn't connected and watching."""


class GuardLost(Exception):
    """The guard dropped mid-move: STOP was sent."""


class MoveGate:
    """Wraps a device (tp1_run.RealDevice signature: cover(path, cmd, pos)). check() returns
    (ok, reason); the dry runs pass their own."""

    def __init__(self, dev, check=guard_ok, on_event=None):
        self._dev, self._check, self._on_event = dev, check, on_event or (lambda *a: None)

    def __getattr__(self, name):
        return getattr(self._dev, name)

    def _require(self, what):
        ok, why = self._check()
        if not ok:
            self._on_event("refused", f"{what} not sent: {why}")
            raise GuardMissing(f"{what} not sent: {why}")

    async def cover(self, path, cmd, pos=None):
        if cmd in ("open", "close", "set"):
            self._require(f"cover {cmd}")
        return await self._dev.cover(path, cmd, pos)

    async def press(self, name):
        if name in MOVE_PRESSES:
            self._require(f"press '{name}'")
        return await self._dev.press(name)

    async def sleep(self, s):
        end = self._dev.now() + s
        while True:
            if self._dev.get("State") in MOVING:
                ok, why = self._check()
                if not ok:
                    await self._dev.cover("api", "stop")
                    self._on_event("stop", f"STOP sent mid-move: {why}")
                    raise GuardLost(f"STOP sent mid-move: {why}")
            rest = end - self._dev.now()
            if rest <= 0:
                return
            await self._dev.sleep(min(rest, 0.5))


# ----------------------------------------------------------------------------- prompts
class Prompter:
    """act(): a prompt asking Daniel to do something; alert(): something he must notice;
    info(): a status line. Shown on top of his screen and spoken, or only recorded (dry runs)."""

    def __init__(self, record_only=False, title="Glasscalibur bench"):
        self.record_only, self.title, self.sent, self._proc = record_only, title, [], None

    def _ui(self):
        if self.record_only:
            return None
        if self._proc is None or self._proc.poll() is not None:
            helper = pathlib.Path(__file__).with_name("bench_prompt.py")
            try:
                self._proc = subprocess.Popen([sys.executable, str(helper), self.title], stdin=subprocess.PIPE,
                                              text=True, encoding="utf-8")
            except OSError:
                self._proc = None
        return self._proc

    def _send(self, kind, text, say):
        self.sent.append((kind, text, say))
        print(f">>> [{kind}] {text}", flush=True)
        p = self._ui()
        if p and p.stdin:
            try:
                p.stdin.write(json.dumps({"kind": kind, "text": text, "say": say}) + "\n")
                p.stdin.flush()
            except OSError:
                pass

    def act(self, text, say=None):
        self._send("act", text, say if say is not None else text)

    def alert(self, text, say=None):
        self._send("alert", text, say if say is not None else text)

    def info(self, text):
        self._send("info", text, None)

    async def countdown(self, sleep, call, n=3):
        """Spoken countdown, about a second apart, ending with the call (returns at the call)."""
        words = {3: "three", 2: "two", 1: "one"}
        for k in range(n, 0, -1):
            self._send("act", f"{k}...", words.get(k, str(k)))
            await sleep(1)
        self._send("act", call, call)

    def close(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass


# ----------------------------------------------------------------------------- the sitting
def read_sitting(path=SITTING):
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
        return s if not s.get("ended") else None
    except (OSError, ValueError):
        return None
