"""Tier 3 screen component and its backing cell buffer.

The screen owns the character grid (chars + per-cell foreground/background
colours). The GPU component manipulates the bound screen's buffer. The display
back-ends (pygame / headless) read the buffer to paint pixels.
"""

from __future__ import annotations

from .base import Component, method

WHITE = 0xFFFFFF
BLACK = 0x000000


class CellBuffer:
    """A width x height grid of (char, fg, bg) cells."""

    def __init__(self, width: int, height: int):
        self.max_width = width
        self.max_height = height
        self.width = width
        self.height = height
        # Monotonically increasing counter bumped on every mutation, so the
        # display knows when to repaint.
        self.generation = 0
        self._alloc(width, height)

    def _alloc(self, w: int, h: int):
        self.chars = [[" "] * w for _ in range(h)]
        self.fg = [[WHITE] * w for _ in range(h)]
        self.bg = [[BLACK] * w for _ in range(h)]

    def resize(self, w: int, h: int) -> bool:
        if w < 1 or h < 1 or w > self.max_width or h > self.max_height:
            return False
        if w == self.width and h == self.height:
            return True
        old_chars, old_fg, old_bg = self.chars, self.fg, self.bg
        self._alloc(w, h)
        for y in range(min(h, len(old_chars))):
            for x in range(min(w, len(old_chars[0]) if old_chars else 0)):
                self.chars[y][x] = old_chars[y][x]
                self.fg[y][x] = old_fg[y][x]
                self.bg[y][x] = old_bg[y][x]
        self.width, self.height = w, h
        self.generation += 1
        return True

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def set(self, x: int, y: int, text: str, fg: int, bg: int, vertical: bool = False):
        """Write ``text`` starting at 1-based-converted (x, y)."""
        if vertical:
            for i, ch in enumerate(text):
                yy = y + i
                if self.in_bounds(x, yy):
                    self.chars[yy][x] = ch
                    self.fg[yy][x] = fg
                    self.bg[yy][x] = bg
        else:
            for i, ch in enumerate(text):
                xx = x + i
                if self.in_bounds(xx, y):
                    self.chars[y][xx] = ch
                    self.fg[y][xx] = fg
                    self.bg[y][xx] = bg
        self.generation += 1

    def fill(self, x: int, y: int, w: int, h: int, ch: str, fg: int, bg: int):
        ch = ch[:1] or " "
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if self.in_bounds(xx, yy):
                    self.chars[yy][xx] = ch
                    self.fg[yy][xx] = fg
                    self.bg[yy][xx] = bg
        self.generation += 1

    def copy(self, x: int, y: int, w: int, h: int, tx: int, ty: int):
        # Snapshot the source region first so overlapping copies behave like OC.
        snap = []
        for dy in range(h):
            row = []
            for dx in range(w):
                sx, sy = x + dx, y + dy
                if self.in_bounds(sx, sy):
                    row.append((self.chars[sy][sx], self.fg[sy][sx], self.bg[sy][sx]))
                else:
                    row.append(None)
            snap.append(row)
        for dy in range(h):
            for dx in range(w):
                cell = snap[dy][dx]
                if cell is None:
                    continue
                dxx, dyy = x + dx + tx, y + dy + ty
                if self.in_bounds(dxx, dyy):
                    self.chars[dyy][dxx], self.fg[dyy][dxx], self.bg[dyy][dxx] = cell
        self.generation += 1

    def get(self, x: int, y: int):
        if not self.in_bounds(x, y):
            return " ", WHITE, BLACK
        return self.chars[y][x], self.fg[y][x], self.bg[y][x]


class Screen(Component):
    ctype = "screen"

    def __init__(self, host, tier: str, address=None):
        super().__init__(host, address)
        self.tier = tier
        from ..config import SCREEN_TIERS

        w, h, _ = SCREEN_TIERS[tier]
        self.buffer = CellBuffer(w, h)
        self.on = True
        self.precise = False
        self.touch_inverted = False
        self.keyboards: list[str] = []  # filled in by the machine

    # -- screen API ---------------------------------------------------------

    @method("Returns whether the screen is currently on.")
    def isOn(self):
        return self.on

    @method("Turns the screen on. Returns true if it was off.")
    def turnOn(self):
        was = self.on
        self.on = True
        return not was

    @method("Turns the screen off. Returns true if it was on.")
    def turnOff(self):
        was = self.on
        self.on = False
        return was

    @method("The aspect ratio of the screen, in blocks (width, height).")
    def getAspectRatio(self):
        return 1, 1

    @method("The list of keyboards attached to the screen.")
    def getKeyboards(self):
        return self.table(list(self.keyboards))

    @method("Set whether to use touch mode (true) or drag mode.")
    def setPrecise(self, enabled):
        was = self.precise
        self.precise = bool(enabled)
        return was

    @method("Check whether high-precision mode is enabled.")
    def isPrecise(self):
        return self.precise

    @method("Sets whether touch mode is inverted.")
    def setTouchModeInverted(self, value):
        was = self.touch_inverted
        self.touch_inverted = bool(value)
        return was

    @method("Check whether touch mode is inverted.")
    def isTouchModeInverted(self):
        return self.touch_inverted

    def device_info(self):
        w, h, depth = self.host.config.screen_size
        return {
            "class": "display",
            "description": "Text buffer",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "Black Hole",
            "capacity": str(w * h),
            "width": str(depth),
        }
