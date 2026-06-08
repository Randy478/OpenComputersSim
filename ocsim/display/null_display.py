"""Headless display: renders the buffer to text and can replay scripted input.

Used for automated tests and for running the machine without a GUI. It detects
when OpenOS goes idle (waiting for input with nothing queued) and, once any
input script is exhausted, shuts the machine down so runs terminate cleanly.
"""

from __future__ import annotations

import time

from .base import Display
from .keymap import OC_KEYS


def string_to_key_signals(kb_addr: str, text: str) -> list[tuple]:
    """Turn a literal string into key_down/key_up signal pairs."""
    out = []
    for ch in text:
        if ch == "\n":
            code = OC_KEYS["enter"]
            cp = 13
        elif ch == "\t":
            code = OC_KEYS["tab"]
            cp = 9
        else:
            code = OC_KEYS.get(ch.lower(), 0)
            cp = ord(ch)
        out.append(("key_down", kb_addr, cp, code, None))
        out.append(("key_up", kb_addr, cp, code, None))
    return out


class NullDisplay(Display):
    def __init__(self, script=None, idle_limit: int = 30, echo: bool = False):
        # script: list of (delay_seconds, text) typed after boot.
        self.script = list(script or [])
        self.idle_limit = idle_limit
        self.echo = echo
        self._idle = 0
        self._kb_addr = None
        self._pending: list[tuple] = []
        self._start = time.monotonic()
        self.frame_text = ""
        self.last_generation = -1

    def attach(self, screen_addr, kb_addr):
        self._kb_addr = kb_addr

    def render(self, screen, gpu):
        if screen is None:
            return
        buf = screen.buffer
        if buf.generation == self.last_generation:
            return
        self.last_generation = buf.generation
        lines = ["".join(buf.chars[y][x] for x in range(buf.width)).rstrip()
                 for y in range(buf.height)]
        # Trim trailing blank lines for compact output.
        while lines and lines[-1] == "":
            lines.pop()
        self.frame_text = "\n".join(lines)
        if self.echo:
            print("\n--- screen ---")
            print(self.frame_text)

    def _queue_script(self):
        elapsed = time.monotonic() - self._start
        ready = [s for s in self.script if s[0] <= elapsed]
        for s in ready:
            self.script.remove(s)
            self._pending.extend(string_to_key_signals(self._kb_addr, s[1]))

    def poll_events(self, timeout):
        self._queue_script()
        if self._pending:
            self._idle = 0
            ev = self._pending.pop(0)
            return [ev]
        # No input available: count idle polls so we can auto-stop.
        if not self.script:
            self._idle += 1
            if self._idle >= self.idle_limit:
                self.closed = True
                return []
        if timeout > 0:
            time.sleep(min(timeout, 0.02))
        return []
