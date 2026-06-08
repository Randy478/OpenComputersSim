"""Keyboard component. Key events are pushed by the display as signals whose
address is the keyboard's address."""

from __future__ import annotations

from .base import Component


class Keyboard(Component):
    ctype = "keyboard"

    def __init__(self, host, screen_addr: str, address=None):
        super().__init__(host, address)
        self.screen_addr = screen_addr

    def device_info(self):
        return {
            "class": "input",
            "description": "Keyboard",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "MercuryBoard 0xCAFE",
        }
