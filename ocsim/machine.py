"""The simulated OpenComputers machine.

Owns the Lua 5.3 runtime, the emulated components, the signal queue and the
driver loop that bridges host (display/input) events to OpenOS signals. Acts as
the ``host`` bridge object that ``bootstrap.lua`` calls into.
"""

from __future__ import annotations

import collections
import os
import random
import shutil
import time

from lupa.lua53 import LuaRuntime

from .config import MachineConfig
from .components.base import new_address
from .components.computer_dev import Computer
from .components.eeprom import EEPROM
from .components.filesystem import Filesystem
from .components.gpu import GPU
from .components.internet import Internet
from .components.keyboard import Keyboard
from .components.screen import Screen

_HERE = os.path.dirname(os.path.abspath(__file__))
_BOOTSTRAP = os.path.join(_HERE, "lua", "bootstrap.lua")
_OSFILES = os.path.join(_HERE, "osfiles")


class Machine:
    def __init__(self, config: MachineConfig, data_dir: str, display, seed: int | None = None):
        self.config = config
        self.data_dir = os.path.abspath(data_dir)
        self.display = display
        self.rng = random.Random(seed)

        self.components: dict[str, object] = {}
        self.signal_queue: collections.deque = collections.deque()
        self.boot_time = time.monotonic()
        self._shutdown: bool | None = None  # None=running, True=reboot, False=halt

        self.lua: LuaRuntime | None = None
        self.screen: Screen | None = None
        self.gpu: GPU | None = None
        self.eeprom: EEPROM | None = None
        self.computer_addr = new_address(self.rng)

    # ------------------------------------------------------------------ setup

    def _seed_boot_disk(self, root: str):
        """Copy the bundled OpenOS tree onto the boot disk on first run."""
        marker = os.path.join(root, "init.lua")
        if os.path.exists(marker):
            return
        os.makedirs(root, exist_ok=True)
        for name in os.listdir(_OSFILES):
            src = os.path.join(_OSFILES, name)
            dst = os.path.join(root, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    def _build_components(self):
        self.components.clear()
        cfg = self.config

        def add(comp):
            self.components[comp.address] = comp
            return comp

        # CPU / computer node.
        add(Computer(self, self.computer_addr))

        # Screen + GPU + keyboard.
        self.screen = add(Screen(self, cfg.screen_tier))
        self.gpu = add(GPU(self, cfg.gpu_tier))
        kb = add(Keyboard(self, self.screen.address))
        self.screen.keyboards = [kb.address]
        self.keyboard_addr = kb.address
        self.gpu.bind(self.screen.address)
        if hasattr(self.display, "attach"):
            self.display.attach(self.screen.address, kb.address)

        # Hard drives.
        boot_addr = None
        for i, disk in enumerate(cfg.disks):
            root = os.path.join(self.data_dir, f"disk{i}")
            if i == 0:
                self._seed_boot_disk(root)
            fs = Filesystem(
                self,
                root=root,
                capacity=disk.capacity,
                label=disk.label,
                readonly=disk.readonly,
                tier=disk.tier,
            )
            add(fs)
            if i == 0:
                boot_addr = fs.address

        # Temporary (RAM) filesystem.
        tmp_root = os.path.join(self.data_dir, "tmpfs")
        if os.path.isdir(tmp_root):
            shutil.rmtree(tmp_root, ignore_errors=True)
        self.tmpfs = add(
            Filesystem(self, root=tmp_root, capacity=cfg.tmpfs_capacity, label="tmpfs")
        )

        # Internet card.
        if cfg.internet_card:
            add(Internet(self))

        # EEPROM with the boot address baked into its data section.
        self.eeprom = add(EEPROM(self, data=boot_addr or ""))
        self.boot_address = boot_addr

    # -------------------------------------------------------------- host API
    # These methods are invoked from bootstrap.lua via the `host` bridge.

    def totable(self, value):
        if isinstance(value, dict):
            return self.lua.table_from(value)
        if isinstance(value, (list, tuple)):
            t = self.lua.table()
            for i, v in enumerate(value):
                t[i + 1] = v
            return t
        return value

    def _match(self, ctype: str, filter, exact) -> bool:
        if filter is None or filter == "":
            return True
        if exact:
            return ctype == filter
        return filter in ctype

    def list_components(self, filter=None, exact=False):
        out = {}
        for addr, comp in self.components.items():
            if self._match(comp.ctype, filter, exact):
                out[addr] = comp.ctype
        return self.lua.table_from(out)

    def invoke(self, address, method, *args):
        comp = self.components.get(address)
        if comp is None:
            raise RuntimeError("no such component")
        methods = comp.exposed_methods()
        fn = methods.get(method)
        if fn is None:
            raise RuntimeError(
                "no such method '%s' on component '%s'" % (method, comp.ctype)
            )
        return fn(*args)

    def ctype(self, address):
        comp = self.components.get(address)
        return comp.ctype if comp else None

    def slot(self, address):
        comp = self.components.get(address)
        return getattr(comp, "slot", -1) if comp else -1

    def methods(self, address):
        comp = self.components.get(address)
        if not comp:
            return self.lua.table()
        out = {}
        for name, fn in comp.exposed_methods().items():
            out[name] = bool(getattr(fn, "_oc_direct", True))
        return self.lua.table_from(out)

    def doc(self, address, method):
        comp = self.components.get(address)
        if not comp:
            return None
        return comp.docs().get(method)

    def fields(self, address):
        return self.lua.table()

    def field_get(self, address, name):
        return None

    def push_signal(self, name, *args):
        if name is None:
            return False
        self.signal_queue.append((name, *args))
        return True

    def uptime(self):
        return time.monotonic() - self.boot_time

    def real_time(self):
        return time.time()

    def computer_address(self):
        return self.computer_addr

    def tmp_address(self):
        return self.tmpfs.address

    def total_memory(self):
        return float(self.config.total_memory)

    def free_memory(self):
        used = self.lua.eval("collectgarbage('count')") * 1024.0
        free = self.config.total_memory - used
        return float(max(2048, free))

    def energy(self):
        return 5000.0

    def max_energy(self):
        return 5000.0

    def get_boot_address(self):
        return self.eeprom.data or None

    def set_boot_address(self, addr=None):
        self.eeprom.data = addr or ""
        return True

    def beep(self, freq=440, duration=0.1):
        if hasattr(self.display, "beep"):
            try:
                self.display.beep(freq, duration)
            except Exception:
                pass
        return True

    def get_device_info(self):
        out = {}
        for addr, comp in self.components.items():
            info = comp.device_info()
            if info:
                out[addr] = self.lua.table_from(info)
        return self.lua.table_from(out)

    def request_shutdown(self, reboot):
        self._shutdown = bool(reboot)
        return True

    def shutdown(self, reboot):
        self.request_shutdown(reboot)
        return True

    # ---------------------------------------------------------------- driver

    def _signal_to_lua(self, sig):
        t = self.lua.table()
        for i, v in enumerate(sig):
            t[i + 1] = v
        t["n"] = len(sig)
        return t

    def _wait_for_signal(self, timeout):
        """Return one OpenOS signal tuple, or None on timeout."""
        if self.signal_queue:
            return self.signal_queue.popleft()
        deadline = self.uptime() + (timeout if timeout != float("inf") else 1e9)
        while True:
            self.display.render(self.screen, self.gpu)
            remaining = deadline - self.uptime()
            if remaining <= 0:
                # one last poll so input stays responsive at timeout boundaries
                remaining = 0
            events = self.display.poll_events(min(max(remaining, 0.0), 0.05))
            for ev in events:
                self.signal_queue.append(ev)
            if self.display.closed:
                self._shutdown = False
                return None
            if self.signal_queue:
                return self.signal_queue.popleft()
            if self.uptime() >= deadline:
                return None

    def boot_once(self) -> str:
        """Boot the machine once. Returns 'reboot' or 'halt'."""
        self.lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
        self.boot_time = time.monotonic()
        self._shutdown = None
        self.signal_queue.clear()
        self._build_components()

        with open(_BOOTSTRAP, "r", encoding="utf-8") as f:
            src = f.read()
        chunk = self.lua.compile(src)
        module = chunk(self)
        main = module["main"]

        co = main.coroutine()
        send_value = None
        first = True
        while True:
            try:
                if first:
                    yielded = co.send(None)
                    first = False
                else:
                    yielded = co.send(send_value)
            except StopIteration:
                # init.lua returned: machine stopped.
                self._shutdown = self._shutdown if self._shutdown is not None else False
                break
            except Exception as e:  # Lua error escaped the machine
                self.display.render(self.screen, self.gpu)
                raise RuntimeError(f"machine crashed: {e}") from e

            if self._shutdown is not None:
                break

            timeout = yielded if isinstance(yielded, (int, float)) else float("inf")
            sig = self._wait_for_signal(timeout)
            if self._shutdown is not None:
                break
            send_value = self._signal_to_lua(sig) if sig is not None else None

        self.display.render(self.screen, self.gpu)
        return "reboot" if self._shutdown else "halt"

    def run(self):
        while True:
            result = self.boot_once()
            if self.display.closed:
                break
            if result == "halt":
                break
            # reboot: loop and rebuild a fresh VM (RAM cleared, disks persist).
