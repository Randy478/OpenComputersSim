"""GNU Unifont (.hex) glyph renderer.

This is the exact font OpenComputers uses for its screens. Each glyph is an
8x16 (narrow) or 16x16 (wide) bitmap. We parse the .hex file and rasterise
glyphs into cached pygame surfaces so the display looks pixel-for-pixel like an
in-game OpenComputers screen.
"""

from __future__ import annotations

import os

_FONT_HEX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "fonts", "unifont.hex",
)


def _rgb(value: int):
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


class Unifont:
    HEIGHT = 16

    def __init__(self, pygame, scale: int = 1, path: str = _FONT_HEX):
        self.pygame = pygame
        self.scale = scale
        self.cell_w = 8 * scale
        self.cell_h = 16 * scale
        self.glyphs: dict[int, tuple[int, list[int]]] = {}
        self._cache: dict = {}
        self._load(path)

    def _load(self, path):
        with open(path, "r", encoding="ascii") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                cp_s, bits = line.split(":", 1)
                try:
                    cp = int(cp_s, 16)
                except ValueError:
                    continue
                nbytes = len(bits) // 2
                bpr = max(1, nbytes // 16)  # bytes per row: 1 (narrow) or 2 (wide)
                width = bpr * 8
                rows = []
                step = bpr * 2
                for r in range(16):
                    chunk = bits[r * step:(r + 1) * step]
                    rows.append(int(chunk, 16) if chunk else 0)
                self.glyphs[cp] = (width, rows)

    def glyph_width(self, cp: int) -> int:
        g = self.glyphs.get(cp)
        return (g[0] if g else 8) * self.scale

    def surface(self, cp: int, fg: int, bg: int):
        key = (cp, fg, bg)
        surf = self._cache.get(key)
        if surf is not None:
            return surf
        pg = self.pygame
        g = self.glyphs.get(cp) or self.glyphs.get(0xFFFD) or (8, [0] * 16)
        width, rows = g
        s = self.scale
        surf = pg.Surface((width * s, 16 * s))
        surf.fill(_rgb(bg))
        fg_rgb = _rgb(fg)
        for y, row in enumerate(rows):
            if row == 0:
                continue
            for x in range(width):
                if row & (1 << (width - 1 - x)):
                    surf.fill(fg_rgb, (x * s, y * s, s, s))
        self._cache[key] = surf
        return surf
