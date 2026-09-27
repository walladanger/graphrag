"""GraphTerm launcher — the executable backing the GraphTerm Windows 11 desktop app.

This tiny GUI shim is what Windows Start-menu shortcuts and the Win32 "App
User Model ID" point at. Its jobs:

1. Locate an installed Python environment that has the ``graphrag`` package
   (preferring a per-user managed venv created by install.ps1).
2. Open a console window running the GraphTerm command shell
   (graphrag_wrapper.cmd -> python -m graphrag_wrapper), without flashing a
   second console window of its own.
3. Fail gracefully with a message box if nothing usable is installed.

Run via pythonw.exe so the launcher itself has no console.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

APP_NAME = "GraphTerm"
WRAPPER_CMD = "graphrag_wrapper.cmd"


def _app_root() -> Path:
    """Directory this script lives in (the installed app folder)."""
    return Path(__file__).resolve().parent


def _find_python() -> str | None:
    """Find a Python interpreter to run the wrapper with, or None."""
    candidates: list[Path] = []

    # 1. Managed per-user venv created by install.ps1
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        candidates.append(Path(local_appdata) / APP_NAME / "venv" / "Scripts" / "python.exe")

    # 2. A venv sitting next to the installed app
    root = _app_root()
    candidates.append(root / ".venv" / "Scripts" / "python.exe")
    candidates.append(root / "venv" / "Scripts" / "python.exe")

    # 3. The interpreter running this very script (if graphrag happens to be
    #    installed system-wide this still works)
    candidates.append(Path(sys.executable))

    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _has_graphrag(python_exe: str) -> bool:
    result = subprocess.run(
        [python_exe, "-c", "import graphrag"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def main() -> int:
    root_dir = _app_root()
    cmd_bat = root_dir / WRAPPER_CMD
    if not cmd_bat.is_file():
        # Also accept being launched from the source layout
        alt = root_dir.parent / WRAPPER_CMD
        cmd_bat = alt if alt.is_file() else cmd_bat

    python_exe = _find_python()

    tkroot = tk.Tk()
    tkroot.withdraw()

    if not cmd_bat.is_file():
        messagebox.showerror(
            APP_NAME,
            f"Could not find {WRAPPER_CMD} next to the launcher.\n\n"
            f"Looked in: {root_dir}",
        )
        return 1

    if python_exe is None or not _has_graphrag(python_exe):
        if not messagebox.askyesno(
            APP_NAME,
            "The 'graphrag' Python package was not found in a managed "
            "environment.\n\nThe shell will try to use whatever 'python' is "
            "on your PATH instead, which may fail.\n\nContinue?",
        ):
            return 0

    # Launch a visible console running the wrapper shell. CREATE_NEW_CONSOLE
    # gives us our own terminal window; setting GRAPHTERM_PYTHON pins the
    # interpreter we already validated.
    env = os.environ.copy()
    if python_exe:
        env["GRAPHTERM_PYTHON"] = python_exe

    flags = 0x00000010  # CREATE_NEW_CONSOLE
    subprocess.Popen(
        ["cmd.exe", "/K", str(cmd_bat)],
        cwd=str(root_dir),
        env=env,
        creationflags=flags,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
