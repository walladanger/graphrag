# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

# ruff: file-ignore[print, start-process-with-a-shell, start-process-with-partial-path, subprocess-without-shell-equals-true, suspicious-subprocess-import]



"""GraphTerm desktop launcher for Windows 11.

This is the executable backing the Start-menu / desktop shortcut. Its jobs:

1. Locate an installed Python environment that has the ``graphrag`` package
   (preferring a per-user managed venv created by install.ps1).
2. Open a console window running the GraphTerm command shell
   (graphrag_wrapper.cmd -> python -m graphterm), without flashing a second
   console window of its own.
3. Fail gracefully with a message box if nothing usable is installed.

Run via pythonw.exe so the launcher itself has no console. On non-Windows
systems (e.g. CI) the GUI/console-launch parts degrade to plain prints so the
module stays importable and testable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "GraphTerm"
WRAPPER_CMD = "graphrag_wrapper.cmd"
CREATE_NEW_CONSOLE = 0x00000010


def app_root() -> Path:
    """Return the directory this script lives in (the installed app folder)."""
    return Path(__file__).resolve().parent


def find_python(root: Path | None = None) -> str | None:
    """Find a Python interpreter to run the wrapper with, or None if absent."""
    root = root or app_root()
    candidates: list[Path] = []

    # 1. Managed per-user venv created by install.ps1
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        candidates.append(
            Path(local_appdata) / APP_NAME / "venv" / "Scripts" / "python.exe"
        )

    # 2. A venv sitting next to the installed app
    candidates.append(root / ".venv" / "Scripts" / "python.exe")
    candidates.append(root / "venv" / "Scripts" / "python.exe")

    # 3. The interpreter running this very script (works if graphrag is
    #    installed system-wide)
    candidates.append(Path(sys.executable))

    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def has_graphrag(python_exe: str) -> bool:
    """Check whether *python_exe* can import the graphrag package."""
    result = subprocess.run(
        [python_exe, "-c", "import graphrag"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def resolve_cmd_bat(root: Path) -> Path:
    """Locate graphrag_wrapper.cmd next to the launcher or one level up."""
    cmd_bat = root / WRAPPER_CMD
    if not cmd_bat.is_file():
        alt = root.parent / WRAPPER_CMD
        cmd_bat = alt if alt.is_file() else cmd_bat
    return cmd_bat


def launch_console(cmd_bat: Path, python_exe: str | None) -> subprocess.Popen:
    """Open a new console window running the wrapper shell."""
    env = os.environ.copy()
    if python_exe:
        env["GRAPHTERM_PYTHON"] = python_exe
    return subprocess.Popen(
        ["cmd.exe", "/K", str(cmd_bat)],
        cwd=str(cmd_bat.parent),
        env=env,
        creationflags=CREATE_NEW_CONSOLE,
    )


def _messagebox_error(title: str, text: str) -> None:
    """Show an error dialog on Windows; print to stderr elsewhere."""
    if sys.platform == "win32":
        import tkinter as tk
        from tkinter import messagebox

        with tk.Tk() as root:
            root.withdraw()
            messagebox.showerror(title, text)
    else:
        print(f"{title}: {text}", file=sys.stderr)


def _messagebox_askyesno(title: str, text: str) -> bool:
    """Ask a yes/no question on Windows; assume yes elsewhere."""
    if sys.platform == "win32":
        import tkinter as tk
        from tkinter import messagebox

        with tk.Tk() as root:
            root.withdraw()
            answer = messagebox.askyesno(title, text)
        return bool(answer)
    print(f"{title}: {text}", file=sys.stderr)
    return True


def main() -> int:
    """Entry point for the desktop launcher."""
    root_dir = app_root()
    cmd_bat = resolve_cmd_bat(root_dir)
    python_exe = find_python(root_dir)

    if not cmd_bat.is_file():
        _messagebox_error(
            APP_NAME,
            f"Could not find {WRAPPER_CMD} next to the launcher.\n\n"
            f"Looked in: {root_dir}",
        )
        return 1

    env_ok = python_exe is not None and has_graphrag(python_exe)
    if not env_ok and not _messagebox_askyesno(
        APP_NAME,
        "The 'graphrag' Python package was not found in a managed "
        "environment.\n\nThe shell will try to use whatever 'python' is "
        "on your PATH instead, which may fail.\n\nContinue?",
    ):
        return 0

    launch_console(cmd_bat, python_exe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
