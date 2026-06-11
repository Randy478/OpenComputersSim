"""Pygame display: a window that looks and behaves like an OpenComputers Tier 3
screen (160x50 cells, per-cell foreground/background colour).

The window stays at the screen's maximum physical resolution; changing the GPU
resolution simply shrinks the active (drawn) area, exactly like the mod.
"""

from __future__ import annotations

import os

from .base import Display
from .keymap import pygame_keymap
from .unifont import Unifont

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "assets", "fonts")
_TTF = os.path.join(_ASSETS, "UbuntuMono-Regular.ttf")
_HEX = os.path.join(_ASSETS, "unifont.hex")


def _rgb(value: int):
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


class PygameDisplay(Display):
    def __init__(self, config, font_size: int = 18, title: str = "OpenComputersSim — Tier 3",
                 font: str = "unifont", scale: int = 0):
        self.config = config
        self.font_size = font_size
        self.title = title
        self.font_kind = font  # "unifont" (authentic) or "ttf"
        self.scale = int(scale)  # 0 = auto-fit to the desktop
        self.screen_addr = None
        self.kb_addr = None
        self._inited = False
        self._last_gen = -1
        self._last_sel = None
        self._glyph_cache: dict = {}
        self._mouse_down = False
        self.unifont = None
        # Text-selection state (for copying to the clipboard). Coordinates are
        # 0-based cell positions; a selection is the rectangle between them.
        self._sel_start = None
        self._sel_end = None
        self._selecting = False

    def attach(self, screen_addr, kb_addr):
        self.screen_addr = screen_addr
        self.kb_addr = kb_addr

    # ----------------------------------------------------------------- setup

    def _init(self, max_w, max_h):
        import pygame

        self.pygame = pygame
        pygame.init()
        pygame.key.set_repeat(400, 35)
        try:
            pygame.scrap.init()
        except Exception:
            pass

        use_unifont = self.font_kind == "unifont" and os.path.exists(_HEX)
        if use_unifont:
            scale = self.scale or self._auto_scale(pygame, max_w, max_h, 8, 16)
            self.unifont = Unifont(pygame, scale=scale)
            self.cell_w = self.unifont.cell_w
            self.cell_h = self.unifont.cell_h
        else:
            if os.path.exists(_TTF):
                self.font = pygame.font.Font(_TTF, self.font_size)
            else:  # fall back to any monospace the host has
                match = pygame.font.match_font(
                    "ubuntumono,dejavusansmono,liberationmono,consolas,couriernew,monospace"
                )
                self.font = pygame.font.Font(match, self.font_size)
            self.cell_w = self.font.size("M")[0]
            self.cell_h = self.font.get_linesize()

        self.win_w = max_w * self.cell_w
        self.win_h = max_h * self.cell_h
        self.surface = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption(self.title)
        self.keymap = pygame_keymap()
        self._inited = True

    @staticmethod
    def _auto_scale(pygame, cols, rows, glyph_w, glyph_h):
        """Pick the largest integer scale whose window fits ~90% of the desktop."""
        try:
            info = pygame.display.Info()
            dw, dh = info.current_w, info.current_h
        except Exception:
            dw, dh = 0, 0
        if dw <= 0 or dh <= 0:
            return 1
        max_w = int(dw * 0.9) // (cols * glyph_w)
        max_h = int(dh * 0.9) // (rows * glyph_h)
        return max(1, min(4, max_w, max_h))

    # ---------------------------------------------------------------- render

    def _glyph(self, ch, fg, bg):
        key = (ch, fg, bg)
        surf = self._glyph_cache.get(key)
        if surf is None:
            surf = self.font.render(ch, True, _rgb(fg), _rgb(bg))
            self._glyph_cache[key] = surf
        return surf

    def render(self, screen, gpu):
        if screen is None:
            return
        buf = screen.buffer
        self.current_screen = screen
        if not self._inited:
            self._init(buf.max_width, buf.max_height)
        sel_key = (self._sel_start, self._sel_end)
        if buf.generation == self._last_gen and sel_key == self._last_sel:
            return
        self._last_gen = buf.generation
        self._last_sel = sel_key
        pg = self.pygame

        self.surface.fill((0, 0, 0))
        cw, ch = self.cell_w, self.cell_h
        uf = self.unifont
        if screen.on:
            for y in range(buf.height):
                row_c = buf.chars[y]
                row_fg = buf.fg[y]
                row_bg = buf.bg[y]
                py = y * ch
                for x in range(buf.width):
                    c = row_c[x]
                    bg = row_bg[x]
                    px = x * cw
                    if uf is not None:
                        if c == "" or (c == " " and bg == 0x000000):
                            continue
                        self.surface.blit(uf.surface(ord(c), row_fg[x], bg), (px, py))
                    else:
                        if bg != 0x000000:
                            self.surface.fill(_rgb(bg), (px, py, cw, ch))
                        if c != " " and c != "":
                            self.surface.blit(self._glyph(c, row_fg[x], bg), (px, py))
        self._draw_selection()
        pg.display.flip()

    def _selection_bounds(self):
        """Return inclusive 0-based (x0, y0, x1, y1) of the current selection."""
        if self._sel_start is None or self._sel_end is None:
            return None
        sx, sy = self._sel_start
        ex, ey = self._sel_end
        return min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey)

    def _draw_selection(self):
        bounds = self._selection_bounds()
        if bounds is None:
            return
        pg = self.pygame
        x0, y0, x1, y1 = bounds
        cw, ch = self.cell_w, self.cell_h
        rect = (x0 * cw, y0 * ch, (x1 - x0 + 1) * cw, (y1 - y0 + 1) * ch)
        overlay = pg.Surface((rect[2], rect[3]), pg.SRCALPHA)
        overlay.fill((90, 140, 255, 90))
        self.surface.blit(overlay, (rect[0], rect[1]))

    # ---------------------------------------------------------------- input

    def _cell_at(self, pos, screen):
        x = pos[0] // self.cell_w + 1
        y = pos[1] // self.cell_h + 1
        buf = screen.buffer
        x = max(1, min(buf.width, x))
        y = max(1, min(buf.height, y))
        return x, y

    def _cell0(self, pos, screen):
        """Like _cell_at but returns 0-based, clamped cell coordinates."""
        x, y = self._cell_at(pos, screen)
        return x - 1, y - 1

    def poll_events(self, timeout):
        if not self._inited:
            return []
        pg = self.pygame
        events = []
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                self.close()
            elif ev.type == pg.KEYDOWN:
                code = self.keymap.get(ev.key, 0)
                ctrl = ev.mod & pg.KMOD_CTRL
                shift = ev.mod & pg.KMOD_SHIFT
                # Copy the on-screen selection to the system clipboard.
                # Ctrl+Shift+C / Ctrl+Insert avoid clobbering Ctrl+C (interrupt).
                if ctrl and (ev.key == pg.K_INSERT or (shift and ev.key == pg.K_c)):
                    self._copy_selection()
                    continue
                # Paste from the system clipboard: Ctrl+V or Shift+Insert.
                if (ev.key == pg.K_v and ctrl) or (ev.key == pg.K_INSERT and shift):
                    text = self._paste()
                    if text:
                        events.append(("clipboard", self.kb_addr, text, None))
                        continue
                # Any other keystroke clears the selection highlight.
                self._clear_selection()
                char = ord(ev.unicode) if ev.unicode else 0
                events.append(("key_down", self.kb_addr, char, code, None))
            elif ev.type == pg.KEYUP:
                code = self.keymap.get(ev.key, 0)
                events.append(("key_up", self.kb_addr, 0, code, None))
            elif ev.type == pg.MOUSEBUTTONDOWN and ev.button in (1, 2, 3):
                # Shift+left-drag selects screen text for copying instead of
                # sending a touch/drag to OpenOS.
                if ev.button == 1 and (pg.key.get_mods() & pg.KMOD_SHIFT):
                    self._selecting = True
                    self._sel_start = self._sel_end = self._cell0(ev.pos, self.current_screen)
                    continue
                self._clear_selection()
                self._mouse_down = True
                x, y = self._cell_at(ev.pos, self.current_screen)
                events.append(("touch", self.screen_addr, x, y, ev.button - 1, None))
            elif ev.type == pg.MOUSEBUTTONUP and ev.button in (1, 2, 3):
                if self._selecting and ev.button == 1:
                    self._sel_end = self._cell0(ev.pos, self.current_screen)
                    self._selecting = False
                    continue
                self._mouse_down = False
                x, y = self._cell_at(ev.pos, self.current_screen)
                events.append(("drop", self.screen_addr, x, y, ev.button - 1, None))
            elif ev.type == pg.MOUSEMOTION and self._selecting:
                self._sel_end = self._cell0(ev.pos, self.current_screen)
            elif ev.type == pg.MOUSEMOTION and self._mouse_down:
                x, y = self._cell_at(ev.pos, self.current_screen)
                events.append(("drag", self.screen_addr, x, y, 0, None))
            elif ev.type == pg.MOUSEWHEEL:
                mx, my = pg.mouse.get_pos()
                x, y = self._cell_at((mx, my), self.current_screen)
                events.append(("scroll", self.screen_addr, x, y, ev.y, None))
        if not events and timeout > 0:
            pg.time.wait(int(min(timeout, 0.03) * 1000))
        return events

    def _paste(self):
        try:
            data = self.pygame.scrap.get(self.pygame.SCRAP_TEXT)
            if data:
                return data.decode("utf-8", "ignore").replace("\x00", "")
        except Exception:
            pass
        return ""

    def _clear_selection(self):
        self._sel_start = self._sel_end = None
        self._selecting = False

    def _selected_text(self):
        """The text inside the current selection rectangle, '\n'-joined."""
        bounds = self._selection_bounds()
        screen = getattr(self, "current_screen", None)
        if bounds is None or screen is None:
            return ""
        x0, y0, x1, y1 = bounds
        buf = screen.buffer
        lines = []
        for y in range(y0, min(y1 + 1, buf.height)):
            row = buf.chars[y]
            chars = []
            for x in range(x0, min(x1 + 1, buf.width)):
                c = row[x]
                chars.append(c if c else " ")
            lines.append("".join(chars).rstrip())
        return "\n".join(lines)

    def _copy_selection(self):
        text = self._selected_text()
        if not text:
            return
        try:
            self.pygame.scrap.put(self.pygame.SCRAP_TEXT, text.encode("utf-8"))
        except Exception:
            pass

    def beep(self, frequency, duration):
        pass
