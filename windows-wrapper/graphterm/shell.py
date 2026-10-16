# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

# ruff: file-ignore[print, start-process-with-a-shell, start-process-with-partial-path, subprocess-without-shell-equals-true, suspicious-subprocess-import]



"""Core logic for the GraphTerm wrapper shell, importable and unit-testable.

All console I/O goes through an injectable :class:`Io` object so the shell can
be tested headlessly on any platform (Linux CI included). This is a console
application, so ``print`` is the intended output mechanism.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

BANNER = r"""
  ____                 _____                    _
 / ___|_ __ __ _ _ __ |_   _|__ _ __ _ __ ___ (_)_ __ ___
| |   | '__/ _` | '_ \  | |/ _ \ '__| '_ ` _ \| | '_ ` _ \
| |___| | | (_| | |_) | | |  __/ |  | | | | | | | | | | | |
 \____|_|  \__,_| .__/  |_|\___|_|  |_| |_| |_|_|_| |_| |_|
                |_|  GraphRAG command shell for Windows
"""

HELP_TEXT = """\
Built-in commands:
  help                 Show this help.
  projects             List GraphRAG projects (folders containing settings.yaml)
                       under the current directory tree.
  status               Show config + environment info for the current project.
  newproject <name>    Create <name>/ and run `graphrag init -d <name>`.
  passthru <args...>   Run raw `graphrag <args...>` exactly as given.
  cls                  Clear the screen.
  exit / quit          Leave GraphTerm.

Anything else is forwarded to the GraphRAG CLI, e.g.:
  init --project ./myproj
  index -v
  query "who are the main characters?" --method global
  prompt-tune -o entity_knowledge
"""

#: Sub-commands that read user input or take a while; purely informational.
LONG_RUNNING = {"index", "query", "prompt-tune"}

#: Classic CMD "command not found" exit code used when the CLI is missing.
EXIT_NOT_FOUND = 9009


@dataclass
class Io:
    """Console abstraction so the shell is testable without a TTY."""

    write: Callable[[str], None] | None = None
    readline: Callable[[str], str] | None = None
    clear: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        """Fill in real-console defaults for any callback left unset."""
        if self.write is None:
            self.write = lambda text: print(text)
        if self.readline is None:
            self.readline = lambda prompt: input(prompt)
        if self.clear is None:
            self.clear = _default_clear


def _default_clear() -> None:
    """Clear the terminal using an OS-appropriate control sequence."""
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()


def graphrag_cmd() -> list[str]:
    """Return the base command vector used to invoke the GraphRAG CLI."""
    exe = shutil.which("graphrag")
    if exe:
        return [exe]
    # Fall back to `python -m graphrag` inside the current interpreter.
    return [sys.executable, "-m", "graphrag"]


def run_graphrag(args: list[str], io: Io | None = None) -> int:
    """Run the graphrag CLI with the given argument vector, live-streaming output."""
    io = io or Io()
    cmd = graphrag_cmd() + args
    io.write(f"[graphrag] {' '.join(shlex.quote(a) for a in cmd)}")
    try:
        proc = subprocess.run(cmd)
    except KeyboardInterrupt:
        io.write("\n[graphterm] interrupted.")
        return 130
    except FileNotFoundError:
        io.write(
            "[graphterm] ERROR: could not find the `graphrag` executable nor"
            " a runnable `python -m graphrag`. Is graphrag installed?\n"
            "  Try:  pip install graphrag"
        )
        return EXIT_NOT_FOUND
    return proc.returncode


def is_project(path: Path) -> bool:
    """Check whether *path* looks like a GraphRAG project root."""
    return (path / "settings.yaml").is_file() or (path / "settings.json").is_file()


_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


def find_projects(here: Path) -> list[Path]:
    """Find GraphRAG project roots at or below *here* (does not descend into found projects)."""
    found: list[Path] = []
    for root, dirs, _files in os.walk(here):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        rp = Path(root)
        if is_project(rp):
            found.append(rp)
            dirs[:] = []  # don't search inside a project we already found
    return found


def find_project_root(start: Path) -> Path | None:
    """Walk up from *start* looking for the nearest GraphRAG project root."""
    for parent in (start, *start.parents):
        if is_project(parent):
            return parent
    return None


def split_line(line: str, io: Io | None = None) -> list[str]:
    """Tokenise a shell line the way CMD would (quotes preserved, then stripped)."""
    try:
        return [strip_quotes(t) for t in shlex.split(line, posix=False)]
    except ValueError as e:
        (io or Io()).write(f"[graphterm] parse error: {e}")
        return []


def strip_quotes(s: str) -> str:
    """Remove a matching pair of surrounding quotes from *s*."""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def cmd_projects(io: Io, _: list[str]) -> int:
    """List GraphRAG projects under the current directory."""
    here = Path.cwd()
    found = find_projects(here)
    if not found:
        io.write(f"[graphterm] No GraphRAG projects (settings.yaml) found under {here}")
        return 0
    io.write(f"[graphterm] GraphRAG projects under {here}:")
    for p in found:
        with contextlib.suppress(ValueError):
            p = p.relative_to(here)
        marker = "  <-- current" if p.resolve() == here.resolve() else ""
        io.write(f"  {p}{marker}")
    return 0


def cmd_status(io: Io, _: list[str]) -> int:
    """Print configuration and environment information for the current project."""
    here = Path.cwd()
    io.write(f"[graphterm] Working directory : {here}")
    proj = find_project_root(here)
    if proj:
        io.write(f"[graphterm] Project root        : {proj}")
        for name in ("settings.yaml", "settings.json", ".env"):
            f = proj / name
            state = "present" if f.is_file() else "-"
            io.write(f"[graphterm]   {name:<14}: {state}")
        out = proj / "output"
        if out.is_dir():
            n = sum(1 for _ in out.iterdir())
            io.write(f"[graphterm]   output/         : {n} entries")
        else:
            io.write("[graphterm]   output/         : - (not indexed yet)")
    else:
        io.write("[graphterm] No GraphRAG project here. Run: newproject <name>")
    io.write(f"[graphterm] GraphRAG CLI        : {' '.join(graphrag_cmd())}")
    pyver = ".".join(map(str, sys.version_info[:3]))
    io.write(f"[graphterm] Python              : {sys.executable} ({pyver})")
    return 0


def cmd_newproject(io: Io, args: list[str]) -> int:
    """Create a new project folder and initialize it with `graphrag init`."""
    if not args:
        io.write("[graphterm] usage: newproject <name>")
        return 2
    name = args[0]
    target = Path(name)
    if target.exists():
        io.write(f"[graphterm] ERROR: '{name}' already exists.")
        return 1
    target.mkdir(parents=True)
    io.write(f"[graphterm] Created project folder '{name}'. Running graphrag init...")
    return run_graphrag(["init", "--project", str(target)], io)


def _cmd_help(io: Io, _: list[str]) -> int:
    """Print the built-in command help text."""
    io.write(HELP_TEXT)
    return 0


BUILTINS: dict[str, Callable[[Io, list[str]], int]] = {
    "help": _cmd_help,
    "projects": cmd_projects,
    "status": cmd_status,
    "newproject": cmd_newproject,
}


def handle_line(line: str, io: Io, state: ShellState) -> tuple[int, bool]:
    """Process one input line.

    Returns ``(exit_code, should_quit)``.
    """
    argv = split_line(line, io)
    if not argv:
        return 0, False
    verb = argv[0].lower()

    if verb in ("exit", "quit"):
        return 0, True
    if verb == "cls":
        io.clear()
        return 0, False
    if verb == "r" and state.last_args:  # repeat last graphrag command
        argv = list(state.last_args)
        verb = argv[0].lower()
    if verb == "passthru":
        return run_graphrag(argv[1:], io), False

    builtin = BUILTINS.get(verb)
    if builtin is not None:
        return builtin(io, argv[1:]), False

    if verb in LONG_RUNNING:
        io.write("[graphterm] (long-running command - Ctrl+C to cancel)")
    state.last_args = argv
    rc = run_graphrag(argv, io)
    io.write(f"[graphterm] exit code: {rc}")
    return rc, False


@dataclass
class ShellState:
    """Mutable state carried between interactive lines."""

    last_args: list[str] = field(default_factory=list)


def interact(io: Io | None = None) -> int:
    """Run the interactive GraphTerm REPL until the user exits."""
    io = io or Io()
    state = ShellState()
    io.write(BANNER)
    io.write("Type 'help' for built-ins; anything else runs `graphrag <args>`.")
    rc = 0
    while True:
        try:
            line = io.readline("graphterm> ")
        except (EOFError, KeyboardInterrupt):
            io.write("")
            return 0
        line = line.strip()
        if not line:
            continue
        rc, quit_ = handle_line(line, io, state)
        if quit_:
            return 0
    return rc  # pragma: no cover - unreachable


def main(argv: list[str] | None = None, io: Io | None = None) -> int:
    """Entry point: no arguments starts the shell, otherwise pass through to graphrag."""
    import argparse

    io = io or Io()
    parser = argparse.ArgumentParser(
        prog="graphrag_wrapper",
        description="Windows wrapper shell for the GraphRAG CLI.",
        epilog=(
            "With no arguments, starts the interactive GraphTerm shell. "
            "With arguments, passes them straight through to `graphrag`."
        ),
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded verbatim to the graphrag CLI.",
    )
    ns = parser.parse_args(argv)
    if ns.args:
        return run_graphrag(list(ns.args), io)
    return interact(io)
