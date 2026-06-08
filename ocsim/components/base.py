"""Base class and helpers for emulated OpenComputers components."""

from __future__ import annotations

import random
from typing import Callable


def new_address(rng: random.Random | None = None) -> str:
    """Generate a component address that looks like an OpenComputers UUID."""
    r = rng or random
    hexd = "0123456789abcdef"

    def block(n: int) -> str:
        return "".join(r.choice(hexd) for _ in range(n))

    return f"{block(8)}-{block(4)}-{block(4)}-{block(4)}-{block(12)}"


def method(doc: str = "", direct: bool = True):
    """Decorator marking a component method as callable from Lua.

    ``doc`` mirrors OpenComputers' component documentation strings returned by
    ``component.doc``.
    """

    def wrap(fn: Callable) -> Callable:
        fn._oc_exposed = True  # type: ignore[attr-defined]
        fn._oc_doc = doc  # type: ignore[attr-defined]
        fn._oc_direct = direct  # type: ignore[attr-defined]
        return fn

    return wrap


class Component:
    """Base class for all emulated components.

    Subclasses set ``ctype`` and decorate the methods they expose with
    :func:`method`. The host wires ``self.host`` so components can build Lua
    tables and reach machine-wide state.
    """

    ctype: str = "component"

    def __init__(self, host, address: str | None = None, slot: int = -1):
        self.host = host
        self.address = address or new_address(host.rng if host else None)
        self.slot = slot

    # -- method discovery ---------------------------------------------------

    def exposed_methods(self) -> dict[str, Callable]:
        out: dict[str, Callable] = {}
        for name in dir(self):
            if name.startswith("_"):
                continue
            attr = getattr(self, name)
            if callable(attr) and getattr(attr, "_oc_exposed", False):
                out[name] = attr
        return out

    def docs(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, fn in self.exposed_methods().items():
            out[name] = getattr(fn, "_oc_doc", "") or ""
        return out

    # -- helpers ------------------------------------------------------------

    def table(self, value):
        """Convert a Python list/dict into a Lua table via the host runtime."""
        return self.host.totable(value)

    def device_info(self) -> dict | None:
        """Optional entry for ``computer.getDeviceInfo`` / lshw."""
        return None
