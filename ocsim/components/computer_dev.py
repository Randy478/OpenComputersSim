"""The 'computer' component node (the case itself), used by lshw and friends."""

from __future__ import annotations

from .base import Component, method


class Computer(Component):
    ctype = "computer"

    def __init__(self, host, address):
        super().__init__(host, address)

    @method("Starts the computer. Returns true if it was off.")
    def start(self):
        return False

    @method("Stops the computer. Returns true if it was on.")
    def stop(self):
        return self.host.shutdown(False)

    @method("Returns whether the computer is running.")
    def isRunning(self):
        return True

    @method("Plays a tone, useful to alert users via audible feedback.")
    def beep(self, frequency=440, duration=0.1):
        return self.host.beep(frequency, duration)

    @method("Collect information on all connected devices.")
    def getDeviceInfo(self):
        return self.host.get_device_info()

    def device_info(self):
        cfg = self.host.config
        return {
            "class": "system",
            "description": "Computer",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "Blocky Mark " + cfg.cpu_tier,
            "capacity": str(cfg.total_memory),
        }
