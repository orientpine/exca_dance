"""PyInstaller runtime hook: set CWD to _MEIPASS so relative asset paths resolve."""

from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)
