"""Bench prompt window — BENCH ONLY. Started by bench_common.Prompter; reads JSON lines on stdin
({"kind": "act"|"alert"|"info", "text": ..., "say": ...}), shows the latest in a window that stays
on top of the screen, and speaks "say" with Windows' built-in voice (System.Speech via PowerShell).
Closes when stdin closes."""
import json, queue, subprocess, sys, threading

COLOURS = {"act": ("#b00020", "white"), "alert": ("#e65100", "white"), "info": ("#1b5e20", "white")}
SPEAK = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
         "$s.Rate = 1; while (($l = [Console]::In.ReadLine()) -ne $null) { if ($l) { $s.Speak($l) } }")


def main():
    import tkinter as tk
    q = queue.Queue()
    voice = None
    try:
        voice = subprocess.Popen(["powershell", "-NoProfile", "-Command", SPEAK], stdin=subprocess.PIPE,
                                 text=True, encoding="utf-8")
    except OSError:
        pass

    def reader():
        for line in sys.stdin:
            try:
                q.put(json.loads(line))
            except ValueError:
                pass
        q.put(None)

    threading.Thread(target=reader, daemon=True).start()
    root = tk.Tk()
    root.title(sys.argv[1] if len(sys.argv) > 1 else "Bench")
    root.attributes("-topmost", True)
    root.geometry("900x260+40+40")
    label = tk.Label(root, text="Bench prompts appear here", font=("Segoe UI", 28, "bold"),
                     wraplength=860, justify="center", bg="#263238", fg="white")
    label.pack(fill="both", expand=True)

    def poll():
        try:
            while True:
                m = q.get_nowait()
                if m is None:
                    root.destroy()
                    return
                bg, fg = COLOURS.get(m.get("kind"), ("#263238", "white"))
                label.config(text=m.get("text", ""), bg=bg, fg=fg)
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
                if m.get("say") and voice and voice.stdin:
                    try:
                        voice.stdin.write(m["say"].replace("\n", " ") + "\n")
                        voice.stdin.flush()
                    except OSError:
                        pass
        except queue.Empty:
            pass
        root.after(100, poll)

    root.after(100, poll)
    root.mainloop()
    if voice and voice.stdin:
        voice.stdin.close()


if __name__ == "__main__":
    main()
