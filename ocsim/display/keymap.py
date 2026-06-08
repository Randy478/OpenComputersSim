"""Key translation tables.

OpenComputers reports keyboard scan codes using LWJGL2 (DirectInput) codes,
the same values the mod uses internally. We map host keys onto those codes so
OpenOS sees exactly what it would in Minecraft.
"""

from __future__ import annotations

# name -> LWJGL2 scan code (mirrors loot/openos/lib/core/full_keyboard.lua).
OC_KEYS = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "a": 0x1E, "b": 0x30, "c": 0x2E, "d": 0x20, "e": 0x12, "f": 0x21,
    "g": 0x22, "h": 0x23, "i": 0x17, "j": 0x24, "k": 0x25, "l": 0x26,
    "m": 0x32, "n": 0x31, "o": 0x18, "p": 0x19, "q": 0x10, "r": 0x13,
    "s": 0x1F, "t": 0x14, "u": 0x16, "v": 0x2F, "w": 0x11, "x": 0x2D,
    "y": 0x15, "z": 0x2C,
    "apostrophe": 0x28, "at": 0x91, "back": 0x0E, "backslash": 0x2B,
    "capital": 0x3A, "colon": 0x92, "comma": 0x33, "enter": 0x1C,
    "equals": 0x0D, "grave": 0x29, "lbracket": 0x1A, "lcontrol": 0x1D,
    "lmenu": 0x38, "lshift": 0x2A, "minus": 0x0C, "numlock": 0x45,
    "pause": 0xC5, "period": 0x34, "rbracket": 0x1B, "rcontrol": 0x9D,
    "rmenu": 0xB8, "rshift": 0x36, "scroll": 0x46, "semicolon": 0x27,
    "slash": 0x35, "space": 0x39, "stop": 0x95, "tab": 0x0F,
    "underline": 0x93,
    "up": 0xC8, "down": 0xD0, "left": 0xCB, "right": 0xCD,
    "home": 0xC7, "end": 0xCF, "pageUp": 0xC9, "pageDown": 0xD1,
    "insert": 0xD2, "delete": 0xD3,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "f11": 0x57, "f12": 0x58,
    "numpad0": 0x52, "numpad1": 0x4F, "numpad2": 0x50, "numpad3": 0x51,
    "numpad4": 0x4B, "numpad5": 0x4C, "numpad6": 0x4D, "numpad7": 0x47,
    "numpad8": 0x48, "numpad9": 0x49, "numpadmul": 0x37, "numpaddiv": 0xB5,
    "numpadsub": 0x4A, "numpadadd": 0x4E, "numpaddecimal": 0x53,
    "numpadenter": 0x9C, "numpadequals": 0x8D,
}


def pygame_keymap():
    """Build a {pygame_key_constant: lwjgl_code} mapping. Imports pygame."""
    import pygame as pg

    K = OC_KEYS
    m = {
        pg.K_RETURN: K["enter"], pg.K_KP_ENTER: K["numpadenter"],
        pg.K_BACKSPACE: K["back"], pg.K_TAB: K["tab"], pg.K_SPACE: K["space"],
        pg.K_ESCAPE: 0x01,
        pg.K_LSHIFT: K["lshift"], pg.K_RSHIFT: K["rshift"],
        pg.K_LCTRL: K["lcontrol"], pg.K_RCTRL: K["rcontrol"],
        pg.K_LALT: K["lmenu"], pg.K_RALT: K["rmenu"],
        pg.K_CAPSLOCK: K["capital"], pg.K_NUMLOCK: K["numlock"],
        pg.K_UP: K["up"], pg.K_DOWN: K["down"], pg.K_LEFT: K["left"],
        pg.K_RIGHT: K["right"], pg.K_HOME: K["home"], pg.K_END: K["end"],
        pg.K_PAGEUP: K["pageUp"], pg.K_PAGEDOWN: K["pageDown"],
        pg.K_INSERT: K["insert"], pg.K_DELETE: K["delete"],
        pg.K_MINUS: K["minus"], pg.K_EQUALS: K["equals"],
        pg.K_LEFTBRACKET: K["lbracket"], pg.K_RIGHTBRACKET: K["rbracket"],
        pg.K_BACKSLASH: K["backslash"], pg.K_SEMICOLON: K["semicolon"],
        pg.K_QUOTE: K["apostrophe"], pg.K_BACKQUOTE: K["grave"],
        pg.K_COMMA: K["comma"], pg.K_PERIOD: K["period"], pg.K_SLASH: K["slash"],
    }
    for ch in "abcdefghijklmnopqrstuvwxyz":
        m[getattr(pg, "K_" + ch)] = K[ch]
    for d in "0123456789":
        m[getattr(pg, "K_" + d)] = K[d]
    for n in range(1, 13):
        m[getattr(pg, "K_F%d" % n)] = K["f%d" % n]
    for n in range(10):
        kp = getattr(pg, "K_KP%d" % n, None) or getattr(pg, "K_KP_%d" % n, None)
        if kp is not None:
            m[kp] = K["numpad%d" % n]
    return m
