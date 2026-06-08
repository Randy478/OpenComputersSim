"""Pygame display: a window that looks and behaves like an OpenComputers Tier 3
screen (160x50 cells, per-cell foreground/background colour).

The window stays at the screen's maximum physical resolution; changing the GPU
resolution simply shrinks the active (drawn) area, exactly like the mod.
"""

from __future__ import annotations

import os

from .base import Display
from .keymap import pygame_keymap

_FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "assets", "fonts", "UbuntuMono-Regular.ttf")


def _rgb(value: int):
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


class PygameDisplay(Display):
    def __init__(self, config, font_size: int = 18, title: str = "OpenComputersSim — Tier 3"):
        self.config = config
        self.font_size = font_size
        self.title = title
        self.screen_addr = None
        self.kb_addr = None
        self._inited = False
        self._last_gen = -1
        self._glyph_cache: dict = {}
        self._mouse_down = False

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

        font_path = os.path.normpath(_FONT)
        if os.path.exists(font_path):
            self.font = pygame.font.Font(font_path, self.font_size)
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
        if buf.generation == self._last_gen:
            return
        self._last_gen = buf.generation
        pg = self.pygame

        self.surface.fill((0, 0, 0))
        cw, ch = self.cell_w, self.cell_h
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
                    if bg != 0x000000:
                        self.surface.fill(_rgb(bg), (px, py, cw, ch))
                    if c != " " and c != "":
                        self.surface.blit(self._glyph(c, row_fg[x], bg), (px, py))
        pg.display.flip()

    # ---------------------------------------------------------------- input

    def _cell_at(self, pos, screen):
        x = pos[0] // self.cell_w + 1
        y = pos[1] // self.cell_h + 1
        buf = screen.buffer
        x = max(1, min(buf.width, x))
        y = max(1, min(buf.height, y))
        return x, y

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
                # Ctrl+V paste -> clipboard signal
                if (ev.key == pg.K_v and (ev.mod & pg.KMOD_CTRL)):
                    text = self._paste()
                    if text:
                        events.append(("clipboard", self.kb_addr, text, None))
                        continue
                char = ord(ev.unicode) if ev.unicode else 0
                events.append(("key_down", self.kb_addr, char, code, None))
            elif ev.type == pg.KEYUP:
                code = self.keymap.get(ev.key, 0)
                events.append(("key_up", self.kb_addr, 0, code, None))
            elif ev.type == pg.MOUSEBUTTONDOWN and ev.button in (1, 2, 3):
                self._mouse_down = True
                x, y = self._cell_at(ev.pos, self.current_screen)
                events.append(("touch", self.screen_addr, x, y, ev.button - 1, None))
            elif ev.type == pg.MOUSEBUTTONUP and ev.button in (1, 2, 3):
                self._mouse_down = False
                x, y = self._cell_at(ev.pos, self.current_screen)
                events.append(("drop", self.screen_addr, x, y, ev.button - 1, None))
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

    def beep(self, frequency, duration):
        pass
