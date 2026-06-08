"""Hardware configuration for the simulated OpenComputers machine.

The defaults model exactly the machine requested:

  * 1x Tier 3 CPU
  * 1x Tier 3 GPU
  * 4x Tier 3.5 memory sticks
  * 4x Tier 3 hard drives
  * 1x Tier 3 screen (160x50, 8-bit colour)

All sizes use the same numbers OpenComputers itself uses (see
``application.conf`` in the mod source), so tools like ``free``, ``df`` and
``lshw`` report values a real OpenComputers player would recognise.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


# --- OpenComputers reference values ----------------------------------------

# RAM stick capacities in bytes, indexed by tier (1, 1.5, 2, 2.5, 3, 3.5).
# OpenComputers measures these in KiB; the Lua 5.3 architecture uses a scale
# factor of ~1.8, but to keep `free` readable we report the raw stick sizes.
RAM_SIZES_KB = {
    "1": 192,
    "1.5": 256,
    "2": 384,
    "2.5": 512,
    "3": 768,
    "3.5": 1024,
}

# Hard drive capacities in bytes, indexed by tier.
HDD_SIZES_KB = {
    "1": 1024,
    "2": 2048,
    "3": 4096,
}

# Screen / GPU capabilities by tier: (width, height, colour-depth-bits).
SCREEN_TIERS = {
    "1": (50, 16, 1),
    "2": (80, 25, 4),
    "3": (160, 50, 8),
}

# Per-call component method budget by CPU tier (direct calls / tick).
CPU_CALL_BUDGET = {"1": 0.5, "2": 1.0, "3": 1.5}


@dataclass
class DiskSpec:
    tier: str = "3"
    label: str = "hdd"
    readonly: bool = False
    # Host directory backing this disk (filled in by the machine at runtime).
    path: str | None = None

    @property
    def capacity(self) -> int:
        return HDD_SIZES_KB[self.tier] * 1024


@dataclass
class MachineConfig:
    cpu_tier: str = "3"
    gpu_tier: str = "3"
    screen_tier: str = "3"

    # Four Tier 3.5 memory sticks.
    ram_sticks: list[str] = field(default_factory=lambda: ["3.5", "3.5", "3.5", "3.5"])

    # Four Tier 3 hard drives. The first one is the OpenOS boot disk.
    disks: list[DiskSpec] = field(
        default_factory=lambda: [
            DiskSpec(tier="3", label="OpenOS"),
            DiskSpec(tier="3", label="data1"),
            DiskSpec(tier="3", label="data2"),
            DiskSpec(tier="3", label="data3"),
        ]
    )

    # Tmpfs (RAM filesystem) capacity in bytes.
    tmpfs_capacity: int = 64 * 1024

    # Whether an internet card is installed (enables wget/pastebin).
    internet_card: bool = True

    # Optional hard override for total RAM, in KiB. When set (> 0) it takes
    # precedence over ram_sticks, so you can dial in any capacity you like.
    ram_total_kb_override: int = 0

    @property
    def total_memory(self) -> int:
        """Total installed RAM in bytes."""
        if self.ram_total_kb_override and self.ram_total_kb_override > 0:
            return int(self.ram_total_kb_override) * 1024
        return sum(RAM_SIZES_KB[t] for t in self.ram_sticks) * 1024

    @property
    def screen_size(self) -> tuple[int, int, int]:
        return SCREEN_TIERS[self.screen_tier]

    def describe(self) -> str:
        w, h, depth = self.screen_size
        lines = [
            "OpenComputersSim machine specification",
            f"  CPU      : Tier {self.cpu_tier}",
            f"  GPU      : Tier {self.gpu_tier}  ({w}x{h}, {2 ** depth} colours)",
            f"  Screen   : Tier {self.screen_tier}",
            f"  Memory   : {len(self.ram_sticks)}x Tier "
            + ", ".join(self.ram_sticks)
            + f"  ({self.total_memory // 1024} KiB total)",
            "  Disks    :",
        ]
        for i, d in enumerate(self.disks):
            lines.append(
                f"             [{i}] Tier {d.tier}  {d.capacity // 1024} KiB  "
                f"label={d.label!r}" + ("  (boot)" if i == 0 else "")
            )
        lines.append(f"  Internet : {'yes' if self.internet_card else 'no'}")
        return "\n".join(lines)


@dataclass
class DisplayConfig:
    font: str = "unifont"   # "unifont" (authentic) or "ttf"
    scale: int = 0          # 0 = auto-fit to the desktop
    font_size: int = 18     # only used when font == "ttf"


@dataclass
class SimConfig:
    """Everything the simulator reads at startup. Serialised to machine.json."""

    machine: MachineConfig = field(default_factory=MachineConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict:
        m = self.machine
        return {
            "_comment": "OpenComputersSim machine config. Edit and restart. "
                        "RAM tiers: 1, 1.5, 2, 2.5, 3, 3.5 (KiB: 192/256/384/"
                        "512/768/1024 per stick). Disk tiers: 1, 2, 3 "
                        "(1/2/4 MiB). Set ram_total_kb_override > 0 to force an "
                        "exact RAM capacity regardless of ram_sticks.",
            "cpu_tier": m.cpu_tier,
            "gpu_tier": m.gpu_tier,
            "screen_tier": m.screen_tier,
            "ram_sticks": list(m.ram_sticks),
            "ram_total_kb_override": m.ram_total_kb_override,
            "disks": [{"tier": d.tier, "label": d.label, "readonly": d.readonly}
                      for d in m.disks],
            "tmpfs_capacity_kb": m.tmpfs_capacity // 1024,
            "internet_card": m.internet_card,
            "display": {
                "font": self.display.font,
                "scale": self.display.scale,
                "font_size": self.display.font_size,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimConfig":
        m = MachineConfig()
        m.cpu_tier = str(d.get("cpu_tier", m.cpu_tier))
        m.gpu_tier = str(d.get("gpu_tier", m.gpu_tier))
        m.screen_tier = str(d.get("screen_tier", m.screen_tier))
        if "ram_sticks" in d and d["ram_sticks"]:
            m.ram_sticks = [str(t) for t in d["ram_sticks"]]
        m.ram_total_kb_override = int(d.get("ram_total_kb_override", 0) or 0)
        if "disks" in d and d["disks"]:
            m.disks = [
                DiskSpec(tier=str(x.get("tier", "3")),
                         label=str(x.get("label", f"disk{i}")),
                         readonly=bool(x.get("readonly", False)))
                for i, x in enumerate(d["disks"])
            ]
        if "tmpfs_capacity_kb" in d:
            m.tmpfs_capacity = int(d["tmpfs_capacity_kb"]) * 1024
        m.internet_card = bool(d.get("internet_card", True))

        disp = DisplayConfig()
        dd = d.get("display", {}) or {}
        disp.font = str(dd.get("font", disp.font))
        disp.scale = int(dd.get("scale", disp.scale))
        disp.font_size = int(dd.get("font_size", disp.font_size))

        cfg = cls(machine=m, display=disp)
        cfg.validate()
        return cfg

    def validate(self):
        m = self.machine
        for t in m.ram_sticks:
            if t not in RAM_SIZES_KB:
                raise ValueError(
                    f"invalid RAM tier {t!r}; valid: {sorted(RAM_SIZES_KB)}")
        for d in m.disks:
            if d.tier not in HDD_SIZES_KB:
                raise ValueError(
                    f"invalid disk tier {d.tier!r}; valid: {sorted(HDD_SIZES_KB)}")
        for name, t in (("screen", m.screen_tier), ("gpu", m.gpu_tier)):
            if t not in SCREEN_TIERS:
                raise ValueError(
                    f"invalid {name} tier {t!r}; valid: {sorted(SCREEN_TIERS)}")

    # -- files --------------------------------------------------------------

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")


def load_or_create(path: str) -> SimConfig:
    """Load the config from ``path``; create it with defaults if missing."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return SimConfig.from_dict(json.load(f))
    cfg = SimConfig()
    cfg.save(path)
    return cfg
