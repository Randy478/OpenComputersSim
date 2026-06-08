"""Command-line entry point for OpenComputersSim."""

from __future__ import annotations

import argparse
import os
import sys

from .config import MachineConfig


def default_data_dir() -> str:
    env = os.environ.get("OCSIM_DATA")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".opencomputerssim")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opencomputerssim",
        description="Simulate an OpenComputers Tier 3 machine running OpenOS.",
    )
    p.add_argument("--data-dir", default=default_data_dir(),
                   help="Where the emulated hard drives are stored "
                        "(default: ~/.opencomputerssim).")
    p.add_argument("--fresh", action="store_true",
                   help="Wipe the data directory before booting (factory reset).")
    p.add_argument("--font-size", type=int, default=18,
                   help="Font size for the display window (default: 18).")
    p.add_argument("--spec", action="store_true",
                   help="Print the machine hardware specification and exit.")
    p.add_argument("--headless", metavar="CMDS", nargs="?", const="",
                   help="Boot without a window. Optionally run ';'-separated "
                        "OpenOS commands, then print the final screen.")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed for component address generation (reproducible runs).")
    return p


def run_headless(config, data_dir, commands, seed):
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
    m = Machine(config, data_dir=data_dir, display=disp, seed=seed)
    # Safety timeout so headless runs always terminate.
    threading.Thread(
        target=lambda: (time.sleep(t + 6), setattr(disp, "closed", True)),
        daemon=True,
    ).start()
    m.run()
    print(disp.frame_text)


def run_window(config, data_dir, font_size, seed):
    from .machine import Machine
    from .display.pygame_display import PygameDisplay

    disp = PygameDisplay(config, font_size=font_size)
    m = Machine(config, data_dir=data_dir, display=disp, seed=seed)
    m.run()


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = MachineConfig()

    if args.spec:
        print(config.describe())
        return 0

    if args.fresh and os.path.isdir(args.data_dir):
        import shutil

        shutil.rmtree(args.data_dir, ignore_errors=True)
    os.makedirs(args.data_dir, exist_ok=True)

    if args.headless is not None:
        run_headless(config, args.data_dir, args.headless, args.seed)
        return 0

    try:
        run_window(config, args.data_dir, args.font_size, args.seed)
    except Exception as e:
        print(f"Failed to open the display window: {e}", file=sys.stderr)
        print("If you have no graphical display, try: "
              "python -m ocsim --headless 'lshw'", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
