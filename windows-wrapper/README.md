# GraphTerm — a Windows wrapper shell + installable Windows 11 desktop app

GraphTerm wraps the [GraphRAG](https://pypi.org/project/graphrag/) CLI in a
friendly command shell and packages it as a proper per-user Windows 11
desktop application (Start Menu entry, desktop icon, taskbar identity, and an
entry in *Settings → Apps & features*). No admin rights required.

## Files

| File                  | Role |
|-----------------------|------|
| `graphrag_wrapper.py` | The wrapper shell. Interactive REPL (`graphterm>` prompt) that forwards commands to `graphrag`, plus built-ins: `help`, `status`, `projects`, `newproject <name>`, `passthru`, `r` (repeat), `cls`, `exit`. Also works one-shot: `python -m graphrag_wrapper index -v`. |
| `graphrag_wrapper.cmd`| Batch entry point: locates Python (managed venv first), launches the shell. Double-clickable. |
| `graphterm.pyw`       | GUI launcher used by the desktop/Start-menu shortcut. Finds the managed environment, validates `graphrag` is importable, then opens the shell in its own console window (no stray console flash). Shows friendly dialogs on problems. |
| `install.ps1`         | Installer: finds or bootstraps Python 3.10+, creates a managed venv under `%LOCALAPPDATA%\GraphTerm\venv`, pip-installs `graphrag`, copies app files, creates Start Menu + Desktop shortcuts with an AppUserModelID, registers Add/Remove Programs entry. |
| `uninstall.ps1`       | Removes shortcuts, registry entries, and the install folder. |
| `graphterm.ico`       | Multi-size app icon (16–256 px). |

## Install

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
# optional: skip the desktop icon
powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoDesktopIcon
```

Then launch **GraphTerm** from the Start Menu (search "GraphTerm") or the
desktop icon. First run may take a moment while the managed environment is
created; the installer prints progress.

## Use

```
graphterm> newproject myproj          # create folder + graphrag init
graphterm> status                     # project / env diagnostics
graphterm> index --project ./myproj   # forwarded to: graphrag index ...
graphterm> query "main themes?" -m global
graphterm> r                          # repeat last graphrag command
graphterm> projects                   # find settings.yaml projects below cwd
graphterm> exit
```

Any unrecognized command is executed verbatim as `graphrag <args>`, so the
full upstream CLI surface (including future subcommands) works without the
wrapper needing updates.

## How the "desktop app" part works

Windows treats any shortcut with a distinct **Application User Model ID**
(AUMID), icon, and Start Menu entry as an installed desktop app:

1. `install.ps1` writes shortcuts pointing at `pythonw.exe graphterm.pyw`, so
   launching shows only the terminal window owned by the shell.
2. The AUMID `MicrosoftResearch.GraphRAG.GraphTerm` is registered under
   `HKCU\Software\Classes\AppUserModelId`, giving correct taskbar grouping,
   jump-list icon, and notification identity.
3. An `HKCU\...\Uninstall` entry makes GraphTerm appear in *Apps & features*
   with its uninstaller wired up.

If you want a distributable `.msix` instead, the same files can be packaged
with the Windows Application Packaging Tool (`makeappx`/`signtool`) or
converted to an MSIX via the Visual Studio "Windows Application Packaging
Project" — the launcher, venv bootstrap, and icon are already structured for
that.

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\GraphTerm\uninstall.ps1"
```

(or use *Settings → Apps & features → GraphTerm → Uninstall*)

## Notes / limitations

- Requires Python 3.10+ (the installer can fetch it via `winget`).
- The managed venv keeps `graphrag` isolated from system Python; upgrades
  happen by re-running `install.ps1`.
- Tested logic (shell parsing, builtins, forwarding) on Linux CI; the
  PowerShell installer and `.cmd`/`.pyw` launchers require a real Windows
  machine to execute.
