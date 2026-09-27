"""GraphTerm — a Windows-friendly command shell around the GraphRAG CLI.

This module is both an importable library and the entry point invoked by
``graphrag_wrapper.cmd``::

    python -m graphrag_wrapper              # interactive shell
    python -m graphrag_wrapper init -d data # one-shot passthrough

Inside the interactive shell you can type any regular ``graphrag``
sub-command (init, index, query, prompt-tune, ...) plus a few built-ins.
Every command line is translated into the equivalent ``graphrag <args>``
invocation and executed in a subprocess, so output streams live to the
console and Ctrl+C behaves as expected.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

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

# Sub-commands that read user input or take a while; purely informational.
LONG_RUNNING = {"index", "query", "prompt-tune"}


def _graphrag_cmd() -> list[str]:
    """Base command used to invoke the GraphRAG CLI."""
    exe = shutil.which("graphrag")
    if exe:
        return [exe]
    # Fall back to `python -m graphrag` inside the current interpreter.
    return [sys.executable, "-m", "graphrag"]


def run_graphrag(args: list[str]) -> int:
    """Run the graphrag CLI with the given argument vector."""
    cmd = _graphrag_cmd() + args
    print(f"[graphrag] {' '.join(shlex.quote(a) for a in cmd)}")
    try:
        proc = subprocess.run(cmd)
        return proc.returncode
    except KeyboardInterrupt:
        print("\n[graphterm] interrupted.")
        return 130
    except FileNotFoundError:
        print("[graphterm] ERROR: could not find the `graphrag` executable nor "
              "a runnable `python -m graphrag`. Is graphrag installed?\n"
              "  Try:  pip install graphrag", file=sys.stderr)
        return 9009  # classic CMD "command not found" code


def _is_project(path: Path) -> bool:
    return (path / "settings.yaml").is_file() or (path / "settings.json").is_file()


def cmd_projects(_: list[str]) -> int:
    here = Path.cwd()
    found: list[Path] = []
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__",
                 ".pytest_cache", "dist", "build"}
    for root, dirs, files in os.walk(here):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        rp = Path(root)
        if _is_project(rp):
            found.append(rp)
            dirs[:] = []  # don't search inside a project we already found
    if not found:
        print("[graphterm] No GraphRAG projects (settings.yaml) found under", here)
        return 0
    print(f"[graphterm] GraphRAG projects under {here}:")
    for p in found:
        try:
            rel = p.relative_to(here)
        except ValueError:
            rel = p
        marker = "  <-- current" if p.resolve() == here.resolve() else ""
        print(f"  {rel}{marker}")
    return 0


def cmd_status(_: list[str]) -> int:
    here = Path.cwd()
    print(f"[graphterm] Working directory : {here}")
    proj = here if _is_project(here) else None
    if proj is None:
        # walk up looking for a project root
        for parent in [here] + list(here.parents):
            if _is_project(parent):
                proj = parent
                break
    if proj:
        print(f"[graphterm] Project root        : {proj}")
        for name in ("settings.yaml", "settings.json", ".env"):
            f = proj / name
            print(f"[graphterm]   {name:<14}: {'present' if f.is_file() else '-'}")
        out = proj / "output"
        if out.is_dir():
            n = sum(1 for _ in out.iterdir())
            print(f"[graphterm]   output/         : {n} entries")
        else:
            print("[graphterm]   output/         : - (not indexed yet)")
    else:
        print("[graphterm] No GraphRAG project here. Run: newproject <name>")
    print(f"[graphterm] GraphRAG CLI        : {' '.join(_graphrag_cmd())}")
    pyver = ".".join(map(str, sys.version_info[:3]))
    print(f"[graphterm] Python              : {sys.executable} ({pyver})")
    return 0


def cmd_newproject(args: list[str]) -> int:
    if not args:
        print("[graphterm] usage: newproject <name>")
        return 2
    name = args[0]
    target = Path(name)
    if target.exists():
        print(f"[graphterm] ERROR: '{name}' already exists.")
        return 1
    target.mkdir(parents=True)
    print(f"[graphterm] Created project folder '{name}'. Running graphrag init...")
    return run_graphrag(["init", "--project", str(target)])


def _split(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=False)
    except ValueError as e:
        print(f"[graphterm] parse error: {e}")
        return []


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _cmd_help(_: list[str]) -> int:
    print(HELP_TEXT)
    return 0


BUILTINS = {
    "help": _cmd_help,
    "projects": cmd_projects,
    "status": cmd_status,
    "newproject": cmd_newproject,
}


def interact() -> int:
    print(BANNER)
    print("Type 'help' for built-ins; anything else runs `graphrag <args>`.\n")
    last_args: list[str] = []
    rc = 0
    while True:
        try:
            line = input("graphterm> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        argv = [_strip_quotes(t) for t in _split(line)]
        if not argv:
            continue
        verb = argv[0].lower()

        if verb in ("exit", "quit"):
            return 0
        if verb == "cls":
            os.system("cls")
            continue
        if verb == "r" and last_args:  # repeat last graphrag command
            argv = last_args
            verb = argv[0].lower()
        if verb == "passthru":
            rc = run_graphrag(argv[1:])
            continue
        builtin = BUILTINS.get(verb)
        if builtin:
            rc = builtin(argv[1:])
            continue

        if verb in LONG_RUNNING:
            print("[graphterm] (long-running command — Ctrl+C to cancel)")
        last_args = argv
        rc = run_graphrag(argv)
        print(f"[graphterm] exit code: {rc}\n")
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="graphrag_wrapper",
        description="Windows wrapper shell for the GraphRAG CLI.",
        epilog="With no arguments, starts the interactive GraphTerm shell. "
               "With arguments, passes them straight through to `graphrag`.",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="Arguments forwarded verbatim to the graphrag CLI.")
    ns = parser.parse_args()
    if ns.args:
        return run_graphrag(list(ns.args))
    return interact()


if __name__ == "__main__":
    sys.exit(main())
