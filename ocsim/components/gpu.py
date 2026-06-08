"""Tier 3 GPU component.

Operates on the cell buffer of whichever screen it is bound to. Colours are
kept as 24-bit RGB; because the host display is true-colour we skip the 8-bit
deflation a real OpenComputers screen would apply, which only ever makes the
output look slightly crisper.
"""

from __future__ import annotations

from .base import Component, method
from .screen import BLACK, WHITE

# Default 16-entry palette for a Tier 3 GPU: sixteen shades of grey.
DEFAULT_T3_PALETTE = [
    (0xFF * (i + 1) // 17) * 0x010101 for i in range(16)
]


class GPU(Component):
    ctype = "gpu"

    def __init__(self, host, tier: str, address=None):
        super().__init__(host, address)
        self.tier = tier
        self.screen_addr: str | None = None
        self.fg = WHITE
        self.bg = BLACK
        self.fg_palette: int | None = None
        self.bg_palette: int | None = None
        from ..config import SCREEN_TIERS

        _, _, self.max_depth_bits = SCREEN_TIERS[tier]
        self.depth_bits = self.max_depth_bits
        self.palette = list(DEFAULT_T3_PALETTE)

    # -- helpers ------------------------------------------------------------

    @property
    def screen(self):
        if self.screen_addr is None:
            return None
        comp = self.host.components.get(self.screen_addr)
        return comp

    @property
    def buf(self):
        s = self.screen
        return s.buffer if s else None

    # -- binding ------------------------------------------------------------

    @method("Binds the GPU to the screen with the specified address.")
    def bind(self, address, reset=True):
        if address not in self.host.components:
            return None, "invalid address"
        if self.host.components[address].ctype != "screen":
            return None, "not a screen"
        self.screen_addr = address
        if reset:
            buf = self.buf
            if buf:
                buf.resize(buf.max_width, buf.max_height)
                self.fg, self.bg = WHITE, BLACK
                self.fg_palette = self.bg_palette = None
        return True

    @method("Get the address of the screen the GPU is bound to.")
    def getScreen(self):
        return self.screen_addr

    # -- resolution ---------------------------------------------------------

    @method("Get the maximum supported resolution.")
    def maxResolution(self):
        buf = self.buf
        if not buf:
            return 0, 0
        return buf.max_width, buf.max_height

    @method("Get the current screen resolution.")
    def getResolution(self):
        buf = self.buf
        if not buf:
            return 0, 0
        return buf.width, buf.height

    @method("Set the screen resolution. Returns true if it changed.")
    def setResolution(self, w, h):
        buf = self.buf
        if not buf:
            return None, "no screen"
        changed = (buf.width, buf.height) != (int(w), int(h))
        if not buf.resize(int(w), int(h)):
            return None, "unsupported resolution"
        if changed:
            self.host.push_signal("screen_resized", self.screen_addr, int(w), int(h))
        return changed

    @method("Get the current viewport resolution.")
    def getViewport(self):
        return self.getResolution()

    @method("Set the viewport resolution.")
    def setViewport(self, w, h):
        return self.setResolution(w, h)

    # -- colour depth -------------------------------------------------------

    @method("Get the maximum supported colour depth.")
    def maxDepth(self):
        return self.max_depth_bits

    @method("Get the currently set colour depth.")
    def getDepth(self):
        return self.depth_bits

    @method("Set the colour depth. Returns the previous depth name.")
    def setDepth(self, bits):
        names = {1: "OneBit", 4: "FourBit", 8: "EightBit"}
        prev = names.get(self.depth_bits, "EightBit")
        self.depth_bits = int(bits)
        return prev

    # -- colours ------------------------------------------------------------

    def _resolve(self, value, is_palette):
        value = int(value)
        if is_palette:
            idx = value & 0xF
            return self.palette[idx], idx
        return value & 0xFFFFFF, None

    @method("Set the background colour. Returns the old colour (and palette index).")
    def setBackground(self, value, is_palette=False):
        old, old_idx = self.bg, self.bg_palette
        self.bg, self.bg_palette = self._resolve(value, is_palette)
        if old_idx is not None:
            return old, old_idx
        return old

    @method("Get the current background colour.")
    def getBackground(self):
        if self.bg_palette is not None:
            return self.bg, True
        return self.bg, False

    @method("Set the foreground colour. Returns the old colour (and palette index).")
    def setForeground(self, value, is_palette=False):
        old, old_idx = self.fg, self.fg_palette
        self.fg, self.fg_palette = self._resolve(value, is_palette)
        if old_idx is not None:
            return old, old_idx
        return old

    @method("Get the current foreground colour.")
    def getForeground(self):
        if self.fg_palette is not None:
            return self.fg, True
        return self.fg, False

    @method("Get the palette colour at the specified index.")
    def getPaletteColor(self, index):
        index = int(index)
        if 0 <= index < len(self.palette):
            return self.palette[index]
        return None, "invalid palette index"

    @method("Set the palette colour at the specified index. Returns the old colour.")
    def setPaletteColor(self, index, value):
        index = int(index)
        if not (0 <= index < len(self.palette)):
            return None, "invalid palette index"
        old = self.palette[index]
        self.palette[index] = int(value) & 0xFFFFFF
        return old

    # -- drawing ------------------------------------------------------------

    @method("Write a string to the screen at the given coordinates.")
    def set(self, x, y, value, vertical=False):
        buf = self.buf
        if not buf:
            return False
        buf.set(int(x) - 1, int(y) - 1, str(value), self.fg, self.bg, bool(vertical))
        return True

    @method("Get the character and colours at the given coordinates.")
    def get(self, x, y):
        buf = self.buf
        if not buf:
            return None, "no screen"
        ch, fg, bg = buf.get(int(x) - 1, int(y) - 1)
        return ch, fg, bg, None, None

    @method("Fill a rectangle with the specified character.")
    def fill(self, x, y, w, h, ch):
        buf = self.buf
        if not buf:
            return False
        buf.fill(int(x) - 1, int(y) - 1, int(w), int(h), str(ch), self.fg, self.bg)
        return True

    @method("Copy a rectangle of the screen to another location.")
    def copy(self, x, y, w, h, tx, ty):
        buf = self.buf
        if not buf:
            return False
        buf.copy(int(x) - 1, int(y) - 1, int(w), int(h), int(tx), int(ty))
        return True

    def device_info(self):
        return {
            "class": "display",
            "description": "Graphics controller",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "MPG3000 GTZ",
            "capacity": str(self.buf.max_width * self.buf.max_height if self.buf else 0),
            "width": str(self.depth_bits),
            "clock": "2000/2000/2000/2000/2000/2000",
        }
