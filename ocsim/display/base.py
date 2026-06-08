"""Display back-end interface.

A display turns the screen's cell buffer into something the user can see, and
turns user input into OpenComputers signals. Signals are tuples of the form
``(name, address, ...)`` matching ``computer.pullSignal`` output, e.g.::

    ("key_down", keyboard_address, char_codepoint, lwjgl_code, player)
    ("key_up",   keyboard_address, char_codepoint, lwjgl_code, player)
    ("clipboard", keyboard_address, text, player)
    ("touch", screen_address, x, y, button, player)
"""

from __future__ import annotations


class Display:
    closed: bool = False

    def render(self, screen, gpu) -> None:
        """Paint the current screen buffer if it changed."""
        raise NotImplementedError

    def poll_events(self, timeout: float) -> list[tuple]:
        """Wait up to ``timeout`` seconds and return new OpenComputers signals."""
        raise NotImplementedError

    def beep(self, frequency: float, duration: float) -> None:
        pass

    def close(self) -> None:
        self.closed = True
