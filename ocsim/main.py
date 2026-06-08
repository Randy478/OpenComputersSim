"""Command-line entry point for OpenComputersSim."""

from __future__ import annotations

import argparse
import os
import sys

from .config import load_or_create


def default_data_dir() -> str:
    env = os.environ.get("OCSIM_DATA")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".opencomputerssim")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opencomputerssim",
        description="Simulate an OpenComputers Tier 3 machine running OpenOS. "
                    "Hardware (RAM, disks, tiers, internet card) is configured "
                    "in machine.json; flags below override it for one run.",
    )
    p.add_argument("--data-dir", default=default_data_dir(),
                   help="Where the disks and machine.json live "
                        "(default: ~/.opencomputerssim).")
    p.add_argument("--config", default=None,
                   help="Path to the config file "
                        "(default: <data-dir>/machine.json). Created if missing.")
    p.add_argument("--fresh", action="store_true",
                   help="Wipe the data directory before booting (factory reset).")
    # Display overrides (None => use the config file value).
    p.add_argument("--font", choices=["unifont", "ttf"], default=None,
                   help="Display font: 'unifont' is the authentic OpenComputers "
                        "screen font; 'ttf' uses Ubuntu Mono.")
    p.add_argument("--scale", type=int, default=None,
                   help="Integer pixel scale for the unifont display "
                        "(0 = auto-fit to your screen).")
    p.add_argument("--font-size", type=int, default=None,
                   help="Font size when using --font ttf.")
    # Actions.
    p.add_argument("--spec", action="store_true",
                   help="Print the machine hardware specification and exit.")
    p.add_argument("--print-config", action="store_true",
                   help="Print the resolved config file path and contents, exit.")
    p.add_argument("--headless", metavar="CMDS", nargs="?", const="",
                   help="Boot without a window. Optionally run ';'-separated "
                        "OpenOS commands, then print the final screen.")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed for component address generation (reproducible runs).")
    return p


def run_headless(machine_cfg, data_dir, commands, seed):
    import time
    import threading
    from .machine import Machine
    from .display.null_display import NullDisplay

    script = []
    t = 0.6
    for cmd in [c for c in commands.split(";") if c.strip()]:
        script.append((t, cmd.strip() + "\n"))
        t += 1.0
    disp = NullDisplay(script=script, idle_limit=80)
    m = Machine(machine_cfg, data_dir=data_dir, display=disp, seed=seed)
    # Safety timeout so headless runs always terminate.
    threading.Thread(
        target=lambda: (time.sleep(t + 6), setattr(disp, "closed", True)),
        daemon=True,
    ).start()
    m.run()
    print(disp.frame_text)


def run_window(machine_cfg, display_cfg, data_dir, seed):
    from .machine import Machine
    from .display.pygame_display import PygameDisplay

    disp = PygameDisplay(machine_cfg, font_size=display_cfg.font_size,
                         font=display_cfg.font, scale=display_cfg.scale)
    m = Machine(machine_cfg, data_dir=data_dir, display=disp, seed=seed)
    m.run()


def main(argv=None):
    args = build_parser().parse_args(argv)

    os.makedirs(args.data_dir, exist_ok=True)
    config_path = args.config or os.path.join(args.data_dir, "machine.json")

    try:
        sim = load_or_create(config_path)
    except Exception as e:
        print(f"Error reading config {config_path}: {e}", file=sys.stderr)
        return 1

    # Apply one-off CLI overrides on top of the config file.
    if args.font is not None:
        sim.display.font = args.font
    if args.scale is not None:
        sim.display.scale = args.scale
    if args.font_size is not None:
        sim.display.font_size = args.font_size

    if args.print_config:
        import json
        print(f"# {config_path}")
        print(json.dumps(sim.to_dict(), indent=2))
        return 0

    if args.spec:
        print(sim.machine.describe())
        print(f"\n(edit {config_path} to change this)")
        return 0

    if args.fresh and os.path.isdir(args.data_dir):
        import shutil
        # Preserve the config file across a factory reset.
        keep = None
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                keep = f.read()
        shutil.rmtree(args.data_dir, ignore_errors=True)
        os.makedirs(args.data_dir, exist_ok=True)
        if keep is not None:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(keep)

    if args.headless is not None:
        run_headless(sim.machine, args.data_dir, args.headless, args.seed)
        return 0

    try:
        run_window(sim.machine, sim.display, args.data_dir, args.seed)
    except Exception as e:
        print(f"Failed to open the display window: {e}", file=sys.stderr)
        print("If you have no graphical display, try: "
              "python -m ocsim --headless 'lshw'", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
