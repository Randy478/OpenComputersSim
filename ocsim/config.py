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

    @property
    def total_memory(self) -> int:
        """Total installed RAM in bytes."""
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
        return "\n".join(lines)
