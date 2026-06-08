"""Boot the real OpenOS headlessly and exercise a few commands.

These tests need `lupa` (Lua 5.3) but not pygame, so they run anywhere.
"""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ocsim.config import MachineConfig
from ocsim.machine import Machine
from ocsim.display.null_display import NullDisplay


def _run(commands, timeout=12.0):
    script = []
    t = 0.6
    for cmd in commands:
        script.append((t, cmd + "\n"))
        t += 1.0
    disp = NullDisplay(script=script, idle_limit=120)
    with tempfile.TemporaryDirectory() as d:
        m = Machine(MachineConfig(), data_dir=d, display=disp)
        threading.Thread(
            target=lambda: (time.sleep(timeout), setattr(disp, "closed", True)),
            daemon=True,
        ).start()
        m.run()
    return disp.frame_text


def test_boots_to_shell():
    out = _run([])
    assert "OpenOS" in out
    assert "#" in out  # the shell prompt


def test_hardware_spec_reported():
    out = _run(["free"])
    # Four Tier 3.5 sticks = 4 MiB total.
    assert "4194304" in out


def test_file_operations():
    out = _run([
        "mkdir /home/t",
        "echo hello > /home/t/x.txt",
        "cat /home/t/x.txt",
    ])
    assert "hello" in out


def test_lshw_lists_tier3_components():
    out = _run(["lshw"])
    assert "Filesystem" in out
    assert "Graphics controller" in out
    assert "EEPROM" in out


def test_config_totals():
    cfg = MachineConfig()
    assert cfg.total_memory == 4 * 1024 * 1024
    assert len(cfg.disks) == 4
    assert all(d.tier == "3" for d in cfg.disks)
    assert cfg.ram_sticks == ["3.5", "3.5", "3.5", "3.5"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("running", name, "...")
            fn()
            print("  ok")
    print("all tests passed")
