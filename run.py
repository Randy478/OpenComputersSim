#!/usr/bin/env python3
"""Launch OpenComputersSim.

    python run.py              # open the Tier 3 display window
    python run.py --spec       # print the machine specification
    python run.py --headless "lshw; df"   # boot without a GUI

See README.md for details.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocsim.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
